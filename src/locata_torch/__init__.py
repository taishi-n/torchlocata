"""Read LOCATA using map-style PyTorch datasets and explicit clock contracts."""

from ._download import download_locata
from ._tables import LocataError
from .analysis_types import (
    DOATrack,
    EvaluationResult,
    GroundTruth,
    Metric,
    MusicResult,
    PeriodResult,
    SourceResult,
    STFTResult,
    TruthSource,
)
from .annotations import activity_periods, align_vad, prepare_ground_truth
from .collate import collate_locata
from .dataset import LocataDataset, LocataWindowDataset, MissingAudioWarning
from .evaluation import EvaluationConfig, evaluate_locata, validate_tracks
from .geometry import locata_doa, world_to_array
from .music import MusicConfig, music_localize, music_stft
from .plotting import plot_doa, plot_evaluation, plot_scene
from .results import (
    ResultBundle,
    aggregate_results,
    read_results,
    write_results,
    write_submission,
)
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
    "download_locata",
    "locata_doa",
    "world_to_array",
    "DOATrack",
    "EvaluationConfig",
    "EvaluationResult",
    "GroundTruth",
    "Metric",
    "MusicConfig",
    "MusicResult",
    "PeriodResult",
    "SourceResult",
    "STFTResult",
    "TruthSource",
    "activity_periods",
    "align_vad",
    "evaluate_locata",
    "music_localize",
    "music_stft",
    "prepare_ground_truth",
    "validate_tracks",
    "ResultBundle",
    "aggregate_results",
    "read_results",
    "write_results",
    "write_submission",
    "plot_doa",
    "plot_evaluation",
    "plot_scene",
]
