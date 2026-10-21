"""LOCATA-based localization/tracking metrics; see NOTICE and docs/analysis.md.

Metric profile locata-torch-v1 fixes documented reference edge cases rather than
claiming historical MATLAB leaderboard equivalence. No implicit label synthesis.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import torch
from torch import Tensor

from ._assignment import minimum_assignment
from .analysis_types import (
    DOATrack,
    EvaluationResult,
    GroundTruth,
    Metric,
    PeriodResult,
    SourceResult,
)
from .annotations import _activity, _clock, _clock_indices, _vector, activity_periods

METRIC_PROFILE = "locata-torch-v1"
MATLAB_REFERENCES = {
    "sap_locata_io": "632468f49b13ca5a9f2f51c064d91183c06622fa",
    "sap_locata_eval": "2787cdabf21bc96453c0d4f3c66db9c9c9f40434",
}


@dataclass(frozen=True)
class EvaluationConfig:
    """Azimuth gate/cutoff in degrees, OSPA orders, and time tolerance in seconds."""

    gate_degrees: float = 30
    ospa_cutoff_degrees: float = 30
    ospa_orders: tuple[float, ...] = (1.0, 1.5, 2.0, 5.0)
    time_tolerance_seconds: float = 1e-9

    def __post_init__(self) -> None:
        if not math.isfinite(self.gate_degrees) or not 0 < self.gate_degrees <= 180:
            raise ValueError("gate_degrees must be in (0, 180]")
        if (
            not math.isfinite(self.ospa_cutoff_degrees)
            or not 0 < self.ospa_cutoff_degrees <= 180
        ):
            raise ValueError("OSPA cutoff must be in (0, 180]")
        if (
            not self.ospa_orders
            or len(set(self.ospa_orders)) != len(self.ospa_orders)
            or any(not math.isfinite(p) or p < 1 for p in self.ospa_orders)
        ):
            raise ValueError("OSPA orders must be unique finite numbers >= 1")
        if (
            not math.isfinite(self.time_tolerance_seconds)
            or self.time_tolerance_seconds < 0
        ):
            raise ValueError("time tolerance must be nonnegative and finite")


def validate_tracks(tracks: Sequence[DOATrack]) -> None:
    """Validate track IDs, CPU clocks, shapes, angles, and duplicate consistency.

    Missing estimates use NaN azimuth. Missing inclination uses None. No angle
    wrapping or timestamp interpolation is performed as a side effect.
    """
    ids: set[str] = set()
    for track in tracks:
        name = track["id"]
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("track IDs must be nonempty unique strings")
        ids.add(name)
        time = _clock(track["time"], f"track {name} time")
        for field, lower, upper in (
            ("azimuth", -math.pi, math.pi),
            ("inclination", 0, math.pi),
        ):
            values = track[field]
            if values is None:
                if field == "azimuth":
                    raise ValueError("azimuth cannot be None")
                continue
            values = _vector(values, f"track {name} {field}", finite=False)
            if values.shape != time.shape or torch.isinf(values).any():
                raise ValueError(
                    f"track {name} {field} must match time and contain no infinity"
                )
            valid = torch.isfinite(values)
            outside = (values < lower) | (
                (values >= upper) if field == "azimuth" else (values > upper)
            )
            if (valid & outside).any():
                raise ValueError(f"track {name} {field} is outside its radian range")
        origin = track["time_origin"]
        if len(origin) != 6 or not all(math.isfinite(v) for v in origin):
            raise ValueError("track time_origin must be a finite calendar tuple")


def _metric(numerator: float, denominator: float, unit: str) -> Metric:
    return {
        "value": numerator / denominator if denominator > 0 else None,
        "numerator": float(numerator),
        "denominator": float(denominator),
        "unit": unit,
    }


def _error_metric(error: Tensor) -> Metric:
    values = torch.rad2deg(error[torch.isfinite(error)])
    return _metric(float(values.sum()), float(values.numel()), "degree")


def _duration(time: Tensor, activity: Tensor) -> float:
    return sum(
        float(time[b - 1] - time[a]) for a, b in activity_periods(activity).tolist()
    )


def _source_metrics(
    time: Tensor,
    active: Tensor,
    association: Tensor,
    azimuth_error: Tensor,
    inclination_error: Tensor,
    periods: list[PeriodResult],
) -> dict[str, Metric]:
    detected = active & (association >= 0)
    latencies = [
        p["latency_seconds"] for p in periods if p["latency_seconds"] is not None
    ]
    duration = sum(p["duration_seconds"] for p in periods)
    return {
        "probability_of_detection": _metric(
            float(detected.sum()), float(active.sum()), "ratio"
        ),
        "azimuth_error_degrees": _error_metric(azimuth_error),
        "inclination_error_degrees": _error_metric(inclination_error),
        "track_latency_seconds": _metric(sum(latencies), len(latencies), "s"),
        "track_fragmentation_rate": _metric(
            sum(p["fragments"] for p in periods), duration, "1/s"
        ),
        "track_swap_rate": _metric(sum(p["swaps"] for p in periods), duration, "1/s"),
        "missed_periods": _metric(
            sum(p["detected_frames"] == 0 for p in periods), 1, "count"
        ),
        "active_periods": _metric(len(periods), 1, "count"),
    }


def evaluate_locata(
    truth: GroundTruth,
    tracks: Sequence[DOATrack],
    *,
    config: EvaluationConfig | None = None,
) -> EvaluationResult:
    """Evaluate active-source DOA tracks using documented LOCATA-based metrics.

    Requires complete source DOA and known array VAD at all selected times.
    Matching uses gated azimuth and maximum-cardinality minimum-cost assignment.
    Returns frame diagnostics, period/source statistics, and scalar sufficient
    statistics. See docs/analysis.md for denominators and MATLAB corrections.
    """
    config = EvaluationConfig() if config is None else config
    validate_tracks(tracks)
    time = _clock(truth["time"], "ground truth time")
    if not len(time) or not truth["sources"]:
        raise ValueError(
            "evaluation requires times and source GT; absence is not silence"
        )
    source_ids = tuple(truth["sources"])
    T, S, N = len(time), len(source_ids), len(tracks)
    activity = torch.empty((T, S), dtype=torch.bool)
    true_az = torch.empty((T, S), dtype=torch.float64)
    true_inc = torch.empty_like(true_az)
    for column, source_id in enumerate(source_ids):
        source = truth["sources"][source_id]
        doa, vad = source["doa"], source["activity"]
        if doa is None:
            raise ValueError(f"{source_id}: missing source DOA ground truth")
        if vad is None:
            raise ValueError(f"{source_id}: missing array VAD activity")
        vad = _activity(vad)
        if len(vad) != T or torch.isnan(vad).any():
            raise ValueError(
                f"{source_id}: unknown activity or incomplete VAD coverage"
            )
        activity[:, column] = vad.bool()
        for name in ("azimuth", "inclination"):
            value = _vector(doa[name], f"{source_id} {name}", finite=False)
            if len(value) != T or not torch.isfinite(value[vad.bool()]).all():
                raise ValueError(f"{source_id}: invalid active-source {name}")
        true_az[:, column], true_inc[:, column] = doa["azimuth"], doa["inclination"]
    estimated_az = torch.full((T, N), torch.nan, dtype=torch.float64)
    estimated_inc = torch.full_like(estimated_az, torch.nan)
    for column, track in enumerate(tracks):
        if track["time_origin"] != truth["time_origin"]:
            raise ValueError("track and ground-truth time origins must match")
        clock = track["time"].to(torch.float64)
        if not len(clock):
            continue
        fields = [track["azimuth"]]
        if track["inclination"] is not None:
            fields.append(track["inclination"])
        nearest = _clock_indices(
            clock, time, fields, tolerance=config.time_tolerance_seconds
        )
        valid = nearest >= 0
        estimated_az[valid, column] = track["azimuth"][nearest[valid]].to(torch.float64)
        if track["inclination"] is not None:
            estimated_inc[valid, column] = track["inclination"][nearest[valid]].to(
                torch.float64
            )
    association = torch.full((T, S), -1, dtype=torch.int64)
    az_error = torch.full((T, S), torch.nan, dtype=torch.float64)
    inc_error = torch.full_like(az_error, torch.nan)
    false_tracks = torch.zeros(T, dtype=torch.int64)
    ospa = torch.zeros((T, len(config.ospa_orders)), dtype=torch.float64)
    ungated: list[float] = []
    for t in range(T):
        src = torch.where(activity[t])[0]
        trk = torch.where(torch.isfinite(estimated_az[t]))[0]
        ns, nt = len(src), len(trk)
        false_tracks[t] = nt
        if not ns or not nt:
            if ns or nt:
                ospa[t, :] = config.ospa_cutoff_degrees
            continue
        diff = true_az[t, src, None] - estimated_az[t, trk][None, :]
        cost = torch.rad2deg(
            torch.abs(torch.remainder(diff + math.pi, 2 * math.pi) - math.pi)
        ).numpy()
        if S == 1:
            ungated.extend(cost.flatten().tolist())
        # Dummies make unmatched rows possible and prioritize match cardinality.
        penalty = (min(ns, nt) + 1) * (config.gate_degrees + 1)
        allowed = cost <= config.gate_degrees + 1e-12
        gated = np.where(allowed, cost, 2 * penalty)
        padded = np.concatenate((gated, np.full((ns, ns), penalty)), axis=1)
        rows, columns = minimum_assignment(padded)
        matched = [
            (r, c)
            for r, c in zip(rows.tolist(), columns.tolist(), strict=True)
            if c < nt and allowed[r, c]
        ]
        false_tracks[t] -= len(matched)
        for r, c in matched:
            s, k = int(src[r]), int(trk[c])
            association[t, s] = k
            az_error[t, s] = math.radians(float(cost[r, c]))
            inc_error[t, s] = torch.abs(true_inc[t, s] - estimated_inc[t, k])
        clipped = np.minimum(cost / config.ospa_cutoff_degrees, 1.0)
        for p_index, order in enumerate(config.ospa_orders):
            powered = clipped**order
            r, c = minimum_assignment(powered)
            ospa[t, p_index] = config.ospa_cutoff_degrees * (
                (float(powered[r, c].sum()) + abs(ns - nt)) / max(ns, nt)
            ) ** (1 / order)
    swaps = torch.zeros((T, S), dtype=torch.int64)
    periods: list[PeriodResult] = []
    source_results: list[SourceResult] = []
    for column, source_id in enumerate(source_ids):
        source_periods: list[PeriodResult] = []
        previous = -1
        for start, stop in activity_periods(activity[:, column]).tolist():
            for t in range(start, stop):
                current = int(association[t, column])
                if current >= 0:
                    swaps[t, column] = int(previous >= 0 and current != previous)
                    previous = current
            detected = association[start:stop, column] >= 0
            detections = torch.where(detected)[0]
            swap_count = int(swaps[start:stop, column].sum())
            fragments = int(((~detected[:-1]) & detected[1:]).sum()) + swap_count
            period_az = _error_metric(az_error[start:stop, column])
            period_inc = _error_metric(inc_error[start:stop, column])
            period: PeriodResult = {
                "source_id": source_id,
                "start_index": start,
                "stop_index": stop,
                "start_time": float(time[start]),
                "stop_time": float(time[stop - 1]),
                "duration_seconds": float(time[stop - 1] - time[start]),
                "active_frames": stop - start,
                "detected_frames": int(detected.sum()),
                "swaps": swap_count,
                "fragments": fragments,
                "latency_seconds": float(time[start + int(detections[0])] - time[start])
                if len(detections)
                else None,
                "azimuth_error_sum_degrees": period_az["numerator"],
                "azimuth_error_count": int(period_az["denominator"]),
                "inclination_error_sum_degrees": period_inc["numerator"],
                "inclination_error_count": int(period_inc["denominator"]),
            }
            source_periods.append(period)
        periods.extend(source_periods)
        source_results.append(
            {
                "source_id": source_id,
                "metrics": _source_metrics(
                    time,
                    activity[:, column],
                    association[:, column],
                    az_error[:, column],
                    inc_error[:, column],
                    source_periods,
                ),
            }
        )
    metrics = _source_metrics(
        time, activity.flatten(), association.flatten(), az_error, inc_error, periods
    )
    duration = float(time[-1] - time[0])
    any_active = activity.any(dim=1)
    metrics["false_alarm_rate"] = _metric(
        float(false_tracks.sum()), duration, "track-frame/s"
    )
    metrics["false_alarm_rate_active"] = _metric(
        float(false_tracks[any_active].sum()),
        _duration(time, any_active),
        "track-frame/s",
    )
    metrics["ungated_azimuth_error_degrees"] = _metric(
        sum(ungated), len(ungated), "degree"
    )
    for p_index, order in enumerate(config.ospa_orders):
        metrics[f"ospa_degrees_p{order:g}"] = _metric(
            float(ospa[:, p_index].sum()), T, "degree"
        )
    return {
        "metadata": truth["metadata"].copy(),
        "time": time.clone(),
        "time_origin": truth["time_origin"],
        "source_ids": source_ids,
        "track_ids": tuple(track["id"] for track in tracks),
        "config": config,
        "metric_profile": METRIC_PROFILE,
        "activity": activity,
        "association": association,
        "azimuth_error": az_error,
        "inclination_error": inc_error,
        "missed": activity & (association < 0),
        "false_tracks": false_tracks,
        "track_swaps": swaps,
        "ospa": ospa,
        "metrics": metrics,
        "sources": source_results,
        "periods": periods,
    }
