"""Portable JSON/CSV/NPZ results, explicit aggregation, and submission export.

The interchange schema is an original design. The submission adapter follows
LOCATA results2csv.m; see docs/results-design.md, docs/analysis.md, and NOTICE.
"""

import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from numpy.typing import NDArray

from .analysis_types import DOATrack, EvaluationResult
from .annotations import _clock
from .evaluation import MATLAB_REFERENCES, validate_tracks
from .types import CalendarTime, RequiredTime

Scalar = str | int | float | None
Row = dict[str, Scalar]
IDENTITY = [
    "recording_id",
    "split",
    "task",
    "recording",
    "array",
    "algorithm",
    "corpus_release",
    "metric_profile",
    "config_key",
]
METRICS = ["metric", "value", "numerator", "denominator", "unit", "missing_reason"]
PERIODS = [
    "source_id",
    "start_index",
    "stop_index",
    "start_time",
    "stop_time",
    "duration_seconds",
    "active_frames",
    "detected_frames",
    "swaps",
    "fragments",
    "latency_seconds",
    "azimuth_error_sum_degrees",
    "azimuth_error_count",
    "inclination_error_sum_degrees",
    "inclination_error_count",
]
TABLES = {
    "recordings.csv": IDENTITY + METRICS,
    "sources.csv": IDENTITY + ["source_id"] + METRICS,
    "periods.csv": IDENTITY + PERIODS,
}
INT_COLUMNS = {
    "task",
    "recording",
    "start_index",
    "stop_index",
    "active_frames",
    "detected_frames",
    "swaps",
    "fragments",
    "azimuth_error_count",
    "inclination_error_count",
}
FLOAT_COLUMNS = {
    "value",
    "numerator",
    "denominator",
    "start_time",
    "stop_time",
    "duration_seconds",
    "latency_seconds",
    "azimuth_error_sum_degrees",
    "inclination_error_sum_degrees",
}
FRAME_KEYS = (
    "time",
    "activity",
    "association",
    "azimuth_error",
    "inclination_error",
    "missed",
    "false_tracks",
    "track_swaps",
    "ospa",
)


@dataclass
class ResultBundle:
    """Portable tables and optional numeric frame arrays loaded without pickle.

    Tables use the documented long schema, with None for empty numeric CSV cells.
    Frame arrays are keyed by original recording ID, never an ID-derived path.
    """

    manifest: dict[str, Any]
    recordings: list[Row]
    sources: list[Row]
    periods: list[Row]
    frames: dict[str, dict[str, NDArray[Any]]] = field(default_factory=dict)


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _number(value: Scalar) -> float:
    if value is None:
        raise ValueError("required metric statistic cannot be missing")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("metric statistics must be finite")
    return number


def _result_rows(
    results: Sequence[EvaluationResult], provenance: Mapping[str, Any]
) -> tuple[list[Row], list[Row], list[Row]]:
    recordings, sources, periods = [], [], []
    seen: set[str] = set()
    for result in results:
        metadata = result["metadata"]
        key = metadata["id"]
        if key in seen:
            raise ValueError(f"duplicate recording ID: {key}")
        seen.add(key)
        identity: Row = {
            "recording_id": key,
            "split": metadata["split"],
            "task": metadata["task"],
            "recording": metadata["recording"],
            "array": metadata["array"],
            "algorithm": str(provenance.get("algorithm", "unspecified")),
            "corpus_release": str(provenance.get("corpus_release", "unspecified")),
            "metric_profile": result["metric_profile"],
            "config_key": hashlib.sha256(
                _canonical(asdict(result["config"])).encode()
            ).hexdigest(),
        }
        for name, metric in result["metrics"].items():
            recordings.append(
                {
                    **identity,
                    "metric": name,
                    **metric,
                    "missing_reason": "no eligible observations"
                    if metric["value"] is None
                    else "",
                }
            )
        for source in result["sources"]:
            for name, metric in source["metrics"].items():
                sources.append(
                    {
                        **identity,
                        "source_id": source["source_id"],
                        "metric": name,
                        **metric,
                        "missing_reason": "no eligible observations"
                        if metric["value"] is None
                        else "",
                    }
                )
        for period in result["periods"]:
            periods.append({**identity, **period})
    return recordings, sources, periods


def aggregate_results(
    results: Sequence[EvaluationResult] | ResultBundle,
    *,
    group_by: Sequence[str],
    weighting: Literal["recording", "pooled"],
) -> list[Row]:
    """Aggregate long per-recording metrics using an explicit grouping/weight.

    `recording` averages eligible recording values; `pooled` divides summed
    numerators by summed denominators. Missing groups remain None. Mixing splits,
    corpus releases, algorithms, metric profiles, or evaluation configs raises.
    Returned rows retain numerator, denominator, eligible/missing counts, and unit.
    """
    if weighting not in ("recording", "pooled"):
        raise ValueError("weighting must be recording or pooled")
    if (
        not group_by
        or len(set(group_by)) != len(group_by)
        or any(key not in IDENTITY for key in group_by)
    ):
        raise ValueError("group_by must select distinct recording identity columns")
    rows = (
        results.recordings
        if isinstance(results, ResultBundle)
        else _result_rows(results, {})[0]
    )
    for key in ("split", "corpus_release", "algorithm", "metric_profile", "config_key"):
        if len({row[key] for row in rows}) > 1:
            raise ValueError(
                f"incompatible {key}; aggregate separate experiments explicitly"
            )
    context = (
        {
            key: rows[0][key]
            for key in (
                "split",
                "corpus_release",
                "algorithm",
                "metric_profile",
                "config_key",
            )
        }
        if rows
        else {}
    )
    seen: set[tuple[Scalar, Scalar]] = set()
    groups: dict[tuple[Scalar, ...], list[Row]] = defaultdict(list)
    for row in rows:
        identity = (row["recording_id"], row["metric"])
        if identity in seen:
            raise ValueError("duplicate recording metric")
        seen.add(identity)
        groups[
            tuple(row[key] for key in group_by) + (row["metric"], row["unit"])
        ].append(row)
    output: list[Row] = []
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        eligible = [row for row in members if row["value"] is not None]
        if weighting == "pooled":
            numerator = sum(_number(row["numerator"]) for row in eligible)
            denominator = sum(_number(row["denominator"]) for row in eligible)
        else:
            numerator = sum(_number(row["value"]) for row in eligible)
            denominator = float(len(eligible))
        output.append(
            {
                **context,
                **dict(zip(group_by, key[:-2], strict=True)),
                "metric": key[-2],
                "unit": key[-1],
                "weighting": weighting,
                "value": numerator / denominator if denominator else None,
                "numerator": numerator,
                "denominator": denominator,
                "recordings": len(members),
                "eligible": len(eligible),
                "missing": len(members) - len(eligible),
            }
        )
    return output


def _output_directory(
    output_dir: str | Path, corpus_roots: Sequence[str | Path]
) -> tuple[Path, Path]:
    if not corpus_roots:
        raise ValueError(
            "corpus_roots must explicitly list the read-only dataset roots"
        )
    target = Path(output_dir).expanduser().resolve()
    for value in corpus_roots:
        root = Path(value).expanduser().resolve()
        if target == root or target.is_relative_to(root):
            raise ValueError(f"output {target} is inside read-only corpus {root}")
    if target.exists():
        raise FileExistsError(f"output directory already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    return target, staging


def _write_table(
    path: Path, columns: list[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            for value in row.values():
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError(f"nonfinite table scalar in {path.name}; use None")
            writer.writerow(row)


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_results(
    results: Sequence[EvaluationResult],
    output_dir: str | Path,
    *,
    corpus_roots: Sequence[str | Path],
    include_frame_arrays: bool = False,
    provenance: Mapping[str, Any] | None = None,
) -> Path:
    """Atomically write versioned JSON, long CSV tables, and optional numeric NPZ.

    Requires corpus roots to protect the input dataset, refuses existing outputs,
    and never serializes Python objects or absolute recording paths. Caller
    provenance can identify algorithm configuration and the corpus release.
    """
    provenance = {} if provenance is None else dict(provenance)
    _canonical(provenance)  # Validate JSON before creating output.
    recordings, sources, periods = _result_rows(results, provenance)
    target, staging = _output_directory(output_dir, corpus_roots)
    try:
        for name, rows in zip(TABLES, (recordings, sources, periods), strict=True):
            _write_table(staging / name, TABLES[name], rows)
        inventory = []
        for result in results:
            key = result["metadata"]["id"]
            frame_path = None
            if include_frame_arrays:
                (staging / "details").mkdir(exist_ok=True)
                frame_path = f"details/{hashlib.sha256(key.encode()).hexdigest()}.npz"
                arrays = {
                    name: result[name].detach().cpu().numpy() for name in FRAME_KEYS
                }
                if any(array.dtype.hasobject for array in arrays.values()):
                    raise ValueError("frame arrays cannot contain Python objects")
                np.savez_compressed(staging / frame_path, **arrays)
            inventory.append(
                {
                    "recording_id": key,
                    "time_origin": result["time_origin"],
                    "source_ids": result["source_ids"],
                    "track_ids": result["track_ids"],
                    "evaluation_config": asdict(result["config"]),
                    "metric_profile": result["metric_profile"],
                    "frame_path": frame_path,
                }
            )
        files = {
            path.relative_to(staging).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sorted(staging.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "schema_version": 1,
            "package": "locata-torch",
            "package_version": version("locata-torch"),
            "matlab_references": MATLAB_REFERENCES,
            "provenance": provenance,
            "angle_convention": (
                "azimuth from +y; inclination from +z; radians in arrays"
            ),
            "missing": (
                "JSON null and empty CSV numeric cells; NaN in documented NPZ fields"
            ),
            "frame_shapes": {
                "time": "[T] seconds",
                "activity": "[T,S] bool",
                "association": "[T,S] int64, -1 unmatched",
                "azimuth_error": "[T,S] radians",
                "inclination_error": "[T,S] radians",
                "missed": "[T,S] bool",
                "false_tracks": "[T] int64",
                "track_swaps": "[T,S] int64",
                "ospa": "[T,P] degrees",
            },
            "recordings": inventory,
            "files": files,
        }
        _write_manifest(staging / "manifest.json", manifest)
        if target.exists():
            raise FileExistsError(target)
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target


def _member(root: Path, name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"invalid bundle member: {name}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"bundle member escapes directory: {name}")
    return resolved


def _read_table(path: Path, columns: list[str]) -> list[Row]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError(f"{path}: incompatible CSV schema")
        output: list[Row] = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}: malformed CSV row")
            parsed: Row = {}
            for key, value in row.items():
                if key in INT_COLUMNS | FLOAT_COLUMNS:
                    number = (
                        None
                        if value == ""
                        else (int(value) if key in INT_COLUMNS else float(value))
                    )
                    if number is not None and not math.isfinite(number):
                        raise ValueError(f"{path}: nonfinite CSV scalar")
                    parsed[key] = number
                else:
                    parsed[key] = value
            output.append(parsed)
    return output


def _check_frame_shapes(
    arrays: dict[str, NDArray[Any]], record: Mapping[str, Any]
) -> None:
    time = arrays["time"]
    if (
        time.ndim != 1
        or time.dtype.kind != "f"
        or not np.isfinite(time).all()
        or (np.diff(time) < 0).any()
    ):
        raise ValueError("invalid frame time schema")
    t, s, p = (
        len(time),
        len(record["source_ids"]),
        len(record["evaluation_config"]["ospa_orders"]),
    )
    shapes = {
        "time": ((t,), "f"),
        "activity": ((t, s), "b"),
        "association": ((t, s), "i"),
        "azimuth_error": ((t, s), "f"),
        "inclination_error": ((t, s), "f"),
        "missed": ((t, s), "b"),
        "false_tracks": ((t,), "i"),
        "track_swaps": ((t, s), "i"),
        "ospa": ((t, p), "f"),
    }
    for name, (shape, kind) in shapes.items():
        value = arrays[name]
        if value.shape != shape or value.dtype.kind != kind:
            raise ValueError(f"invalid {name} frame shape/dtype schema")
        if kind != "b" and value.dtype.itemsize != 8:
            raise ValueError(f"{name} must use 64-bit frame storage")
        if kind == "f" and np.isinf(value).any():
            raise ValueError(f"infinite {name} frame value")
    association = arrays["association"]
    if (association < -1).any() or (association >= len(record["track_ids"])).any():
        raise ValueError("invalid frame association indices")
    if not np.isfinite(arrays["ospa"]).all() or (arrays["ospa"] < 0).any():
        raise ValueError("invalid OSPA frame values")


def read_results(output_dir: str | Path) -> ResultBundle:
    """Read and hash-check a schema-v1 result bundle, with NPZ pickle disabled.

    Returns portable tables and optional frame arrays, not a fabricated complete
    EvaluationResult when the diagnostics were not saved.
    """
    root = Path(output_dir).expanduser().resolve()
    manifest = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant {value}")
        ),
    )
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported result schema_version")
    files = manifest.get("files")
    if not isinstance(files, dict) or not set(TABLES).issubset(files):
        raise ValueError("result manifest has no complete file inventory")
    for name, expected in files.items():
        path = _member(root, name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"bundle checksum mismatch: {name}")
    recordings, sources, periods = [
        _read_table(root / name, columns) for name, columns in TABLES.items()
    ]
    frames: dict[str, dict[str, NDArray[Any]]] = {}
    identities: set[str] = set()
    for record in manifest["recordings"]:
        identity = record["recording_id"]
        if identity in identities:
            raise ValueError("duplicate recording ID in result manifest")
        identities.add(identity)
        frame_path = record["frame_path"]
        if frame_path is None:
            continue
        if frame_path not in files:
            raise ValueError("frame file is absent from inventory")
        with np.load(_member(root, frame_path), allow_pickle=False) as archive:
            if set(archive.files) != set(FRAME_KEYS):
                raise ValueError("incompatible frame-array schema")
            arrays = {name: archive[name].copy() for name in FRAME_KEYS}
        _check_frame_shapes(arrays, record)
        frames[identity] = arrays
    return ResultBundle(manifest, recordings, sources, periods, frames)


def _calendar(origin: CalendarTime, elapsed: float) -> list[str]:
    total = (
        Decimal(str(origin[5]))
        + Decimal(str(elapsed))
        + Decimal(origin[3] * 3600 + origin[4] * 60)
    )
    days = int((total / 86400).to_integral_value(rounding=ROUND_FLOOR))
    stamp = date(origin[0], origin[1], origin[2]) + timedelta(days=days)
    within = total - days * 86400
    hour = int(within // 3600)
    minute = int((within - hour * 3600) // 60)
    second = within - hour * 3600 - minute * 60
    return [
        str(stamp.year),
        str(stamp.month),
        str(stamp.day),
        str(hour),
        str(minute),
        format(second, "f"),
    ]


def write_submission(
    tracks: Sequence[DOATrack],
    output_dir: str | Path,
    *,
    required_time: RequiredTime,
    corpus_roots: Sequence[str | Path],
    elapsed_seconds: float,
) -> Path:
    """Write official-style source_N.txt TSV files from validated aligned tracks.

    Follows results2csv.m's time/angle fields, with original string IDs, exact
    fractional calendar arithmetic, no placeholder zero angles, and a manifest.
    Supply the full recording's raw RequiredTime, including invalid rows, so
    numeric timestamps use the MATLAB origin (first raw required timestamp).
    Tracks must cover all valid requested rows. elapsed_seconds is measured
    algorithm wall time. Writes telapsed.txt without a fabricated placeholder.
    """
    validate_tracks(tracks)
    raw_time = _clock(required_time["time"], "required time")
    flags = required_time["valid_flag"]
    if not len(raw_time) or flags.dtype != torch.bool or flags.shape != raw_time.shape:
        raise ValueError("required_time must include its bool valid_flag and raw rows")
    if not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be measured nonnegative finite seconds")
    time = raw_time[flags]
    origin = tracks[0]["time_origin"] if tracks else None
    for track in tracks:
        if track["time_origin"] != origin or not torch.equal(
            track["time"].to(torch.float64), time
        ):
            raise ValueError(
                "submission tracks must share origin and exactly match required_time"
            )
    target, staging = _output_directory(output_dir, corpus_roots)
    try:
        for index, track in enumerate(tracks, 1):
            columns = [
                "year",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "timestamps",
                "azimuth",
            ]
            if track["inclination"] is not None:
                columns.append("elevation")
            columns.append("ID")
            with (staging / f"source_{index}.txt").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.writer(stream, delimiter="\t")
                writer.writerow(columns)
                for row, seconds in enumerate(time.tolist()):
                    values = _calendar(track["time_origin"], seconds) + [
                        format(seconds - float(raw_time[0]), ".17g"),
                        format(float(track["azimuth"][row]), ".17g"),
                    ]
                    if track["inclination"] is not None:
                        values.append(format(float(track["inclination"][row]), ".17g"))
                    writer.writerow([*values, track["id"]])
        (staging / "telapsed.txt").write_text(
            format(elapsed_seconds, ".17g") + "\n", encoding="utf-8"
        )
        _write_manifest(
            staging / "manifest.json",
            {
                "schema_version": 1,
                "format": "locata-submission",
                "matlab_references": MATLAB_REFERENCES,
                "time_origin": origin,
                "timestamp_origin": float(raw_time[0]),
                "tracks": [track["id"] for track in tracks],
            },
        )
        if target.exists():
            raise FileExistsError(target)
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return target
