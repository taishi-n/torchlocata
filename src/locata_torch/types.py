"""Public CPU tensor schemas; shapes and units are defined in the data model."""

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from torch import Tensor

CalendarTime = tuple[int, int, int, int, int, float]


@dataclass(frozen=True)
class RecordingInfo:
    """One existing array WAV, indexed without loading its payload."""

    split: str
    task: int
    recording: int
    array: str
    path: Path
    num_frames: int
    sample_rate: int
    num_channels: int

    @property
    def id(self) -> str:
        return f"{self.split}/task{self.task}/recording{self.recording}/{self.array}"

    @property
    def audio_path(self) -> Path:
        return self.path / f"audio_array_{self.array}.wav"


class Pose(TypedDict):
    """Timed world pose: xyz, reference vector, and local-to-world rotation."""

    time: Tensor
    time_origin: CalendarTime
    position: Tensor
    ref_vec: Tensor
    rotation: Tensor


class ArrayPose(Pose):
    """Array pose with microphone world positions in WAV channel order."""

    microphone_position: Tensor


class RequiredTime(TypedDict):
    """Requested estimation times and validity flags, independent of VAD."""

    time: Tensor
    valid_flag: Tensor


class SourceAudio(TypedDict):
    """Optional source waveform and its independent, shared-origin clock."""

    waveform: Tensor
    sample_rate: int
    audio_time: Tensor
    start_frame: int
    stop_frame: int


class TimedVAD(TypedDict):
    """Known boolean voice activity and its corresponding audio timestamps."""

    time: Tensor
    values: Tensor


class SourceVAD(TypedDict):
    """Optional array-aligned and source-aligned VAD for one source ID."""

    array: TimedVAD | None
    source: TimedVAD | None


class Source(TypedDict):
    """Independent source pose, opt-in audio, availability, and optional VAD."""

    pose: Pose | None
    audio: SourceAudio | None
    audio_available: bool
    vad: SourceVAD


class RecordingMetadata(TypedDict):
    """Recording identity and half-open frame and relative-time boundaries."""

    id: str
    split: str
    task: int
    recording: int
    array: str
    path: Path
    start_frame: int
    stop_frame: int
    num_frames: int
    time_bounds: tuple[float, float]


class LocataSample(TypedDict):
    """One recording or window, preserving independent annotation clocks."""

    waveform: Tensor
    sample_rate: int
    audio_time: Tensor
    time_origin: CalendarTime
    required_time: RequiredTime
    array_pose: ArrayPose
    sources: dict[str, Source]
    metadata: RecordingMetadata


class LocataBatch(TypedDict):
    """Padded audio and masks with original annotation lists per sample."""

    waveform: Tensor
    lengths: Tensor
    audio_mask: Tensor
    sample_rate: int
    audio_time: list[Tensor]
    time_origin: list[CalendarTime]
    required_time: list[RequiredTime]
    array_pose: list[ArrayPose]
    sources: list[dict[str, Source]]
    metadata: list[RecordingMetadata]


class DOA(TypedDict):
    """Array-frame vector, LOCATA azimuth, inclination from +z, and range."""

    vector: Tensor
    azimuth: Tensor
    inclination: Tensor
    range: Tensor
