# Data model

`LocataSample` is a public `TypedDict`. All dataset tensors reside on the CPU.
Waveforms use the selected float32 or float64 dtype; timestamps and geometry use
float64; flags and VAD use bool.

`T` denotes audio frames, `C` WAV channels, and `P` rows in a particular annotation
table. Annotation tables can have different row counts. Audio sample numbers
and annotation row numbers are never treated as corresponding indexes.

## Recording and window samples

| Field | Shape or type | Meaning |
| --- | --- | --- |
| `waveform` | `[C, T]`, float32 or float64 | Original WAV amplitude and channel order |
| `sample_rate` | `int` | Sample rate in Hz, from the WAV header |
| `audio_time` | `[T]`, float64 | Array-audio timestamps in relative seconds |
| `time_origin` | `CalendarTime` | First array-audio timestamp of the whole recording |
| `required_time` | `RequiredTime` | Requested estimation times and independent validity flags |
| `array_pose` | `ArrayPose` | Array reference point, orientation, and microphone geometry |
| `sources` | `dict[str, Source]` | Per-source pose, optional audio, and optional VAD |
| `metadata` | `RecordingMetadata` | Identity, file path, frame interval, and time bounds |

`CalendarTime` is `(year, month, day, hour, minute, second)`, with five integers and
a float for fractional seconds. All clocks share this origin, including source
audio clocks. See [time and windows](time-and-windows.md) for calendar conversion
and interval boundaries.

`RecordingMetadata` contains `id`, `split`, `task`, `recording`, `array`, `path`,
`start_frame`, `stop_frame`, `num_frames`, and `time_bounds`. The ID is
`split/taskN/recordingN/array`; `path` is the array directory as a `Path`.
`num_frames` describes the whole array WAV, while `[start_frame, stop_frame)`
describes this item's frames. `time_bounds` is a pair of relative seconds.

## Required estimation times

| Field | Shape | Meaning |
| --- | --- | --- |
| `time` | `[P]`, float64 | The `required_time.txt` clock in relative seconds |
| `valid_flag` | `[P]`, bool | Original 0/1 validity values |

`valid_flag` is independent of VAD. Invalid rows are retained without automatic
filtering or conversion to activity labels.

## Poses and microphone positions

`Pose` represents one source pose table. `ArrayPose` adds microphone positions.

| Field | Shape | Meaning |
| --- | --- | --- |
| `time` | `[P]` | This position file's relative clock |
| `time_origin` | Calendar tuple | The sample's shared origin |
| `position` | `[P, 3]` | Reference-point world xyz, in metres |
| `ref_vec` | `[P, 3]` | Dimensionless reference vector in world coordinates |
| `rotation` | `[P, 3, 3]` | Local-to-world rotation, indexed by row and column |
| `microphone_position` | `[P, C, 3]` | Array only: world xyz of each microphone, in metres |

The OptiTrack world axes are East, North, and Up, relative to the calibration
reference for each recording. World origins are not necessarily shared across
recordings. Rotations preserve the `rotation_ij` columns. Microphones follow
`mic1` through `micC` in WAV channel order. The [geometry guide](geometry.md)
defines the explicit world-to-array conversion.

Geometry NaNs remain present in raw samples. The caller decides how to use
validity flags and timestamps; DOA helpers reject nonfinite geometry.

## Multiple sources and optional audio

Source IDs are discovered from available pose, audio, timestamp, and recognized
VAD filenames. Their original strings and natural numeric order are preserved.
The reader supports multiple sources and reads available ground truth in either
split. If no source files exist, `sources` is an empty dict.

Each `sources[id]` contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `pose` | `Pose` or `None` | Available source position and orientation |
| `audio` | `SourceAudio` or `None` | Source WAV data, read only when requested |
| `audio_available` | `bool` | Whether the source WAV exists, even if loading is disabled |
| `vad` | `SourceVAD` | Separate array-aligned and source-aligned VAD |

`SourceAudio` contains `waveform [C_source, T_source]`, `sample_rate`,
`audio_time [T_source]`, `start_frame`, and `stop_frame`. Its WAV header and clock
are independent of the array audio. Its timestamps use the sample's shared
origin. Source audio is not guaranteed to be anechoic clean speech.

## Voice activity

`SourceVAD` has `array` and `source` entries. Each is a `TimedVAD` with
`time [T_vad]` in relative seconds and `values [T_vad]` in bool, or `None`.

- `array` reads `VAD_{array}_{id}.txt` against the array-audio clock.
- `source` reads `VAD_source_{id}.txt` against that source's audio clock.

VAD TXT files must be tab-separated with a `VAD` column containing 0 or 1. WAV,
timestamp, and VAD row counts must match. A source VAD requires its source WAV and
timestamp file, but reading that WAV payload is still optional.

## Missing, empty, and inactive data

| Representation | Interpretation |
| --- | --- |
| `None` | An annotation is unavailable, or source audio loading is disabled |
| `audio_available=True`, `audio=None` | Source audio exists but was not requested |
| Empty tensor with the documented trailing shape | The file exists, but this window contains no matching rows or audio frames |
| VAD value `False` | Known inactivity at an available VAD timestamp |
| `valid_flag=False` | An invalid estimation time, independent of activity |

Missing ground truth and VAD are never replaced with zero labels. An available
silent source remains distinct from an absent annotation. See
[collation](io-and-dataloader.md#collation) for batch shapes and padding masks.
