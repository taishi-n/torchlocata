"""Explicit GT/VAD preparation based on LOCATA get_truth/read_ground_truth.m.

Timestamp matching and coverage-aware VAD replace the reference's row-index and
fixed-48-kHz assumptions. See docs/analysis.md and NOTICE for provenance.
"""

from collections.abc import Sequence

import torch
from torch import Tensor

from ._tables import TIME_ATOL
from .analysis_types import GroundTruth, TruthSource
from .geometry import locata_doa
from .types import ArrayPose, LocataSample, Pose, TimedVAD

TIME_TOLERANCE = 1e-9


def _vector(value: Tensor, name: str, *, finite: bool = True) -> Tensor:
    if value.ndim != 1 or value.device.type != "cpu":
        raise ValueError(f"{name} must be a one-dimensional CPU tensor")
    value = value.to(torch.float64)
    if finite and not torch.isfinite(value).all():
        raise ValueError(f"{name} must be finite")
    return value


def _clock(value: Tensor, name: str, *, strict: bool = False) -> Tensor:
    value = _vector(value, name)
    delta = value[1:] - value[:-1]
    if (delta <= 0).any() if strict else (delta < 0).any():
        raise ValueError(f"{name} must be {'strictly ' if strict else ''}increasing")
    return value


def _activity(value: Tensor) -> Tensor:
    value = _vector(value, "VAD activity", finite=False)
    if not ((value == 0) | (value == 1) | torch.isnan(value)).all():
        raise ValueError("VAD activity must be binary (0/1) or NaN for unknown")
    return value


def align_vad(vad: TimedVAD, time: Tensor, *, sample_rate: int) -> Tensor:
    """Sample VAD on its own clock with previous-sample hold and NaN outside.

    Args:
        vad: Boolean audio activity and strictly increasing relative seconds.
        time: Target relative seconds sharing the same calendar origin.
        sample_rate: Actual corresponding WAV rate, used for final coverage.

    Returns:
        CPU float64 `[T]` values in 0/1/NaN. No extrapolation is performed.
    """
    if (
        isinstance(sample_rate, bool)
        or not isinstance(sample_rate, int)
        or sample_rate <= 0
    ):
        raise ValueError("sample_rate must be a positive integer")
    clock = _clock(vad["time"], "VAD clock", strict=True)
    query = _vector(time, "target time")
    values = _activity(vad["values"])
    if len(clock) != len(values) or torch.isnan(values).any():
        raise ValueError("VAD clock and binary values must have equal lengths")
    output = torch.full_like(query, torch.nan)
    if len(clock):
        indices = torch.searchsorted(clock, query, right=True) - 1
        next_index = (indices + 1).clamp(max=len(clock) - 1)
        coincident = torch.abs(clock[next_index] - query) <= TIME_ATOL
        indices = torch.where(coincident, next_index, indices)
        # A clock gap does not turn an unobserved interval into held activity.
        last_covered = clock[indices.clamp(min=0)] + 1 / sample_rate
        known = (indices >= 0) & (query < last_covered - TIME_ATOL)
        output[known] = values[indices[known]]
    return output


def activity_periods(activity: Tensor) -> Tensor:
    """Return int64 `[K, 2]` half-open indices of contiguous known activity.

    Initial/final activity is retained; NaNs break periods without implying
    known silence. Evaluation separately rejects incomplete activity labels.
    """
    active = _activity(activity) == 1
    padded = torch.cat((torch.tensor([False]), active, torch.tensor([False])))
    edges = padded[1:].to(torch.int64) - padded[:-1].to(torch.int64)
    return torch.stack((torch.where(edges == 1)[0], torch.where(edges == -1)[0]), dim=1)


def _clock_indices(
    clock: Tensor, query: Tensor, values: Sequence[Tensor], *, tolerance: float
) -> Tensor:
    """Match timestamps and ordered duplicates; -1 denotes an absent timestamp."""
    if not len(clock):
        return torch.full((len(query),), -1, dtype=torch.int64)
    right = torch.searchsorted(clock, query).clamp(max=len(clock) - 1)
    left = (right - 1).clamp(min=0)
    choose_left = torch.abs(clock[left] - query) < torch.abs(clock[right] - query)
    indices = torch.where(choose_left, left, right)
    indices[torch.abs(clock[indices] - query) > tolerance] = -1
    duplicate_times = torch.unique(clock[:-1][clock[1:] == clock[:-1]])
    for stamp in duplicate_times:
        targets = torch.where(torch.abs(query - stamp) <= tolerance)[0]
        if not len(targets):
            continue
        start = int(torch.searchsorted(clock, stamp))
        stop = int(torch.searchsorted(clock, stamp, right=True))
        conflicting = any(
            not torch.allclose(
                value[start:stop],
                value[start].expand_as(value[start:stop]),
                rtol=0,
                atol=0,
                equal_nan=True,
            )
            for value in values
        )
        if conflicting:
            if len(targets) != stop - start:
                raise ValueError(
                    "conflicting duplicate timestamp multiplicity is ambiguous"
                )
            indices[targets] = torch.arange(start, stop)
    return indices


def _pose_indices(pose: Pose, query: Tensor) -> Tensor:
    clock = _clock(pose["time"], "pose time")
    fields = [pose["position"], pose["rotation"], pose["ref_vec"]]
    microphones = pose.get("microphone_position")
    if isinstance(microphones, Tensor):
        fields.append(microphones)
    if any(value.device.type != "cpu" or len(value) != len(clock) for value in fields):
        raise ValueError("pose geometry must match its CPU clock")
    indices = _clock_indices(clock, query, fields, tolerance=TIME_TOLERANCE)
    if (indices < 0).any():
        raise ValueError("pose timestamp does not match a valid required time")
    return indices


def _select_pose(pose: Pose, query: Tensor, origin) -> Pose:
    if pose["time_origin"] != origin:
        raise ValueError("pose and sample time origins must match")
    indices = _pose_indices(pose, query)
    return {
        "time": query.clone(),
        "time_origin": pose["time_origin"],
        "position": pose["position"][indices].clone(),
        "rotation": pose["rotation"][indices].clone(),
        "ref_vec": pose["ref_vec"][indices].clone(),
    }


def prepare_ground_truth(
    sample: LocataSample, *, time_bounds: tuple[float, float] | None = None
) -> GroundTruth:
    """Select valid required times and explicitly match independent pose clocks.

    Based on `get_truth.m` and `read_ground_truth.m`. Missing source pose/VAD
    remains None; unobserved VAD times remain NaN. Source-aligned VAD is not used
    as a substitute for array VAD. No rotation or position interpolation occurs.
    """
    required = sample["required_time"]
    time = _clock(required["time"], "required time")
    flags = required["valid_flag"]
    if flags.dtype != torch.bool or flags.shape != time.shape:
        raise ValueError("valid_flag must be bool and match required time")
    selection = flags.clone()
    if time_bounds is not None:
        start, stop = time_bounds
        if not torch.isfinite(torch.tensor([start, stop])).all() or stop <= start:
            raise ValueError("time_bounds must be finite and increasing")
        selection &= (time >= start - TIME_ATOL) & (time < stop - TIME_ATOL)
    query = time[selection].clone()
    ap = sample["array_pose"]
    selected = _select_pose(ap, query, sample["time_origin"])
    indices = _pose_indices(ap, query)
    array_pose: ArrayPose = {
        **selected,
        "microphone_position": ap["microphone_position"][indices].clone(),
    }
    sources: dict[str, TruthSource] = {}
    for source_id, source in sample["sources"].items():
        pose = source["pose"]
        vad = source["vad"]["array"]
        sources[source_id] = {
            "doa": None
            if pose is None
            else locata_doa(
                array_pose, _select_pose(pose, query, sample["time_origin"])
            ),
            "activity": None
            if vad is None
            else align_vad(vad, query, sample_rate=sample["sample_rate"]),
        }
    return {
        "time": query,
        "time_origin": sample["time_origin"],
        "array_pose": array_pose,
        "sources": sources,
        "metadata": sample["metadata"].copy(),
    }
