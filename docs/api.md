# API reference

Public objects are imported from `locata_torch`. The reference below is generated
from the package source by mkdocstrings; private parsing helpers are excluded.

Read [getting started](getting-started.md) for constructor defaults and selection,
[data model](data-model.md) for shapes and missing values, [time and
windows](time-and-windows.md) for clock semantics, and [I/O and
DataLoader](io-and-dataloader.md) for caching, collation, and worker behavior.

::: locata_torch
    options:
      members:
        - LocataDataset
        - download_locata
        - LocataWindowDataset
        - collate_locata
        - world_to_array
        - locata_doa
        - LocataError
        - MissingAudioWarning
        - RecordingInfo
        - CalendarTime
        - RecordingMetadata
        - LocataSample
        - LocataBatch
        - RequiredTime
        - Pose
        - ArrayPose
        - Source
        - SourceAudio
        - SourceVAD
        - TimedVAD
        - DOA
        - prepare_ground_truth
        - align_vad
        - activity_periods
        - music_stft
        - music_localize
        - MusicConfig
        - validate_tracks
        - evaluate_locata
        - EvaluationConfig
        - plot_scene
        - plot_doa
        - plot_evaluation
        - aggregate_results
        - write_results
        - read_results
        - write_submission
        - ResultBundle
        - GroundTruth
        - TruthSource
        - DOATrack
        - STFTResult
        - MusicResult
        - EvaluationResult
        - SourceResult
        - PeriodResult
        - Metric
