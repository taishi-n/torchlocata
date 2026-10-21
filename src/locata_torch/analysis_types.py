"""Typed analysis results; see docs/analysis.md for shapes, units, and provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from torch import Tensor

from .types import DOA, ArrayPose, CalendarTime, RecordingMetadata

if TYPE_CHECKING:
    from .evaluation import EvaluationConfig
    from .music import MusicConfig


class TruthSource(TypedDict):
    """Source DOA and array activity (0/1/NaN); absent annotations remain None."""

    doa: DOA | None
    activity: Tensor | None


class GroundTruth(TypedDict):
    """Explicitly selected required times, matched poses, and source annotations."""

    time: Tensor
    time_origin: CalendarTime
    array_pose: ArrayPose
    sources: dict[str, TruthSource]
    metadata: RecordingMetadata


class DOATrack(TypedDict):
    """One estimated track; NaN azimuth means no detection, not a zero direction."""

    id: str
    time: Tensor
    time_origin: CalendarTime
    azimuth: Tensor
    inclination: Tensor | None


class STFTResult(TypedDict):
    """Complex128 [frames, frequencies, channels], seconds, and frequencies in Hz."""

    spectrum: Tensor
    time: Tensor
    frequencies: Tensor


class MusicResult(TypedDict):
    """Single-source MUSIC track plus the pre-interpolation block estimates."""

    track: DOATrack
    block_time: Tensor
    block_azimuth: Tensor
    block_inclination: Tensor
    config: MusicConfig
    elapsed_seconds: float


class Metric(TypedDict):
    """A scalar and its sufficient statistics; zero denominator means unavailable."""

    value: float | None
    numerator: float
    denominator: float
    unit: str


class PeriodResult(TypedDict):
    """One known voice-active period, using a half-open annotation index interval."""

    source_id: str
    start_index: int
    stop_index: int
    start_time: float
    stop_time: float
    duration_seconds: float
    active_frames: int
    detected_frames: int
    swaps: int
    fragments: int
    latency_seconds: float | None
    azimuth_error_sum_degrees: float
    azimuth_error_count: int
    inclination_error_sum_degrees: float
    inclination_error_count: int


class SourceResult(TypedDict):
    """Per-source sufficient statistics without reducing away the source identity."""

    source_id: str
    metrics: dict[str, Metric]


class EvaluationResult(TypedDict):
    """Per-recording diagnostics and metrics under the documented metric profile."""

    metadata: RecordingMetadata
    time: Tensor
    time_origin: CalendarTime
    source_ids: tuple[str, ...]
    track_ids: tuple[str, ...]
    config: EvaluationConfig
    metric_profile: str
    activity: Tensor
    association: Tensor
    azimuth_error: Tensor
    inclination_error: Tensor
    missed: Tensor
    false_tracks: Tensor
    track_swaps: Tensor
    ospa: Tensor
    metrics: dict[str, Metric]
    sources: list[SourceResult]
    periods: list[PeriodResult]
