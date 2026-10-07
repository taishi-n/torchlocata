"""Read LOCATA using map-style PyTorch datasets and explicit clock contracts."""

from ._tables import LocataError
from .collate import collate_locata
from .dataset import LocataDataset, LocataWindowDataset, MissingAudioWarning
from .geometry import locata_doa, world_to_array
from .types import (
    DOA,
    ArrayPose,
    CalendarTime,
    LocataBatch,
    LocataSample,
    Pose,
    RecordingInfo,
    RecordingMetadata,
    RequiredTime,
    Source,
    SourceAudio,
    SourceVAD,
    TimedVAD,
)

__all__ = [
    "ArrayPose",
    "CalendarTime",
    "DOA",
    "LocataBatch",
    "LocataDataset",
    "LocataError",
    "LocataSample",
    "LocataWindowDataset",
    "MissingAudioWarning",
    "Pose",
    "RecordingInfo",
    "RecordingMetadata",
    "RequiredTime",
    "Source",
    "SourceAudio",
    "SourceVAD",
    "TimedVAD",
    "collate_locata",
    "locata_doa",
    "world_to_array",
]
