# locata-torch

English | [日本語](https://github.com/taishi-n/torchlocata/blob/main/README.ja.md)

Read LOCATA recordings, timestamps, and position annotations with PyTorch
`Dataset` and `DataLoader`. [locata-torch](https://pypi.org/project/locata-torch/)
is available on PyPI; import it as `locata_torch` in your own application.

The library provides recording datasets, fixed-length window views, padded
batches, coordinate helpers, an explicit localization/evaluation layer, and an
optional downloader for the official LOCATA release. It returns CPU tensors and
works independently of TorchRIR.

## Installation

Use Python 3.10 or later. Choose the command for your application's environment:

| Environment | Read an existing dataset | Include download support |
| --- | --- | --- |
| pip | `python -m pip install locata-torch` | `python -m pip install "locata-torch[download]"` |
| uv project | `uv add locata-torch` | `uv add "locata-torch[download]"` |

Runtime dependencies are PyTorch, NumPy, SoundFile, and platformdirs. The
`download` extra adds filelock. The LOCATA corpus is installed separately.

## Quick start

Use an unpacked root containing `dev/` or `eval/`:

```python
from locata_torch import LocataDataset, collate_locata
from torch.utils.data import DataLoader

dataset = LocataDataset(
    root="/path/to/LOCATA",
    split="dev",
    tasks=(1, 2, 3, 4, 5, 6),
    arrays=("eigenmike",),
)
sample = dataset[0]
waveform = sample["waveform"]  # [channels, samples], CPU float32
windows = dataset.windows(num_samples=48000, hop_samples=24000, drop_last=True)
loader = DataLoader(
    windows,
    batch_size=4,
    shuffle=True,
    num_workers=0,
    collate_fn=collate_locata,
)
batch = next(iter(loader))
waveforms = batch["waveform"]  # [batch, channels, padded_samples]
```

Replace `/path/to/LOCATA` with your dataset root. Window sizes are WAV frame
counts; 48000 frames represent one second only at 48 kHz. The reader uses the
actual WAV header and preserves amplitudes, channel order, and sample rate.

One recording item represents `(split, task, recording, array)`. Select recordings
with `split`, `tasks`, `recordings`, and `arrays`. Tasks 1–6 and the `benchmark2`,
`dicit`, `dummy`, and `eigenmike` arrays are supported. Index order is deterministic,
with numeric task and recording order. Both dataset views support `Subset`,
standard samplers, and shuffle.

Waveforms default to `torch.float32`; pass `dtype=torch.float64` to change this.
Available source audio is loaded only with `load_source_audio=True`.
For multiple workers, use `spawn` and a `__main__` guard as shown in the
[DataLoader guide](https://taishi.org/torchlocata/io-and-dataloader.html#multiple-workers-and-samplers).

## Share an existing dataset

Set one root for applications that use the same corpus:

```sh
export LOCATA_ROOT=/path/to/LOCATA
locata-torch path
```

Then omit `root`: `LocataDataset(split="dev", arrays=("eigenmike",))`.
Root lookup uses an explicit `root`, then `LOCATA_ROOT`, then a completed managed
installation. Invalid configured paths raise an error. `~` is expanded, and
reader construction performs no downloads or filesystem writes.

## Download LOCATA

Install the `download` extra and prepare data before creating DataLoader workers:

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
```

Alternatively, configure a shared managed store and use the installed CLI:

```sh
export LOCATA_DATA_DIR=/path/to/locata-store
locata-torch download --split dev --split eval
```

In a uv project, prefix CLI commands with `uv run`. `LOCATA_DATA_DIR` selects
managed storage; `LOCATA_ROOT` points directly to an unpacked corpus. Without a
storage setting, downloads use the platform's persistent user data directory.

The downloader supports the [official final release](https://zenodo.org/records/3630471),
DOI `10.5281/zenodo.3630471`. It transfers whole splits, verifies archive sizes and
MD5 checksums, resumes identified partial downloads, and installs through staged
ZIP64 extraction. Repeated requests verify and reuse completed installations.
Both retained ZIPs and extracted splits occupy about 103.8 GB; allow at least
120 GB free for a fresh installation. See [paths and storage](https://taishi.org/torchlocata/storage.html)
for per-split sizes, integrity checks, and recovery behavior.

## Data contract

Each item is a `LocataSample` typed dict containing:

- `waveform`, `sample_rate`, and per-frame `audio_time`.
- `time_origin`: the recording's first array-audio calendar timestamp, retaining
  fractional seconds; all clocks use relative seconds from this origin.
- `required_time`: requested estimation times and `valid_flag`.
- `array_pose`: world position, reference vector, rotation, microphone positions,
  and their own timestamps.
- `sources`: original source IDs mapped to optional poses, audio, and VAD.
- `metadata`: recording identity, path, frame interval, and time bounds.

Timestamps and geometry use float64; flags use bool. Audio and annotation clocks
remain independent. Missing annotations are `None`, while an available table
with no rows in a window has empty tensors. File presence determines source
availability in both splits. `valid_flag` and VAD are separate signals; missing
ground truth is never filled with zero labels. Source audio is not guaranteed to
be anechoic clean speech.

Windows read only the requested WAV frames, retain the recording's time origin,
and crop each annotation clock to a half-open time interval. With
`drop_last=False`, short tails remain short until `collate_locata` pads them.
Batches contain `lengths` and a padding-only `audio_mask`; annotations and source
mappings remain lists per sample. Collation requires a common array, sample rate,
channel count, and waveform dtype.

Geometry helpers use LOCATA's `R.T @ (h - p)` convention. `locata_doa` requires
matched pose clocks and returns azimuth from +y in `[-pi, pi)`, inclination from
+z in `[0, pi]`, and range in metres. Angles are radians.

## Localization and evaluation

The localization and evaluation APIs require version 0.2.0 or later.
Install the `plot` extra to include diagnostic plotting:

```sh
python -m pip install "locata-torch[plot]>=0.2.0"
```

The explicit analysis APIs are based on the organizers' MATLAB
[I/O framework](https://github.com/cevers/sap_locata_io/tree/632468f49b13ca5a9f2f51c064d91183c06622fa)
and [evaluation framework](https://github.com/cevers/sap_locata_eval/tree/2787cdabf21bc96453c0d4f3c66db9c9c9f40434).
They do not change Dataset outputs. See [MATLAB provenance and analysis](https://taishi.org/torchlocata/analysis.html)
for the function mapping, units, formulas, corrections, and verification limits.

```python
from locata_torch import (
    MusicConfig,
    evaluate_locata,
    music_localize,
    prepare_ground_truth,
)

truth = prepare_ground_truth(sample, time_bounds=sample["metadata"]["time_bounds"])
estimate = music_localize(sample, config=MusicConfig())
# Evaluation requires source poses and known array-aligned VAD at every
# selected time. Missing annotations raise an error rather than imply silence.
result = evaluate_locata(truth, [estimate["track"]])
metrics = result["metrics"]  # Per-recording metrics, with explicit denominators.
```

`prepare_ground_truth` selects valid required times and matches pose timestamps;
it never pairs annotation rows by their indices or interpolates rotations.
`align_vad` explicitly samples array VAD on its own clock with a previous-sample
hold. Uncovered target times remain NaN; a missing VAD remains `None`.
`activity_periods` returns half-open index intervals of known activity.

`music_stft` reproduces the reference framing and symmetric Hamming window.
`music_localize` provides the reference single-source MUSIC baseline, including
explicit microphone selection, block processing, and interpolation of estimates.
It reports block estimates and a validated `DOATrack`; it does not use source
ground truth. `validate_tracks` checks IDs, clocks, shapes, radians, and NaN
estimates before evaluation. `EvaluationConfig` makes gating and OSPA parameters
explicit. Unavailable scalar metrics are `None`; unavailable per-frame errors
are NaN, never artificial zero errors.

The `plot` extra enables `plot_scene`, `plot_doa`, and `plot_evaluation`. These
return Matplotlib figures without displaying or saving them. Matplotlib is
optional and is not imported when the library is imported. The
[analysis example](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py)
demonstrates localization, evaluation, export, and plotting from a source checkout.

`aggregate_results` requires explicit grouping and weighting (`recording` or
`pooled`). `write_results` and `read_results` exchange versioned JSON metadata,
CSV tables, and optional non-pickled NPZ frame arrays. `write_submission` is a
separate adapter for the official tab-separated result format. All writers use
an explicitly supplied output directory and reject paths inside corpus roots.
See the [portable results design](https://taishi.org/torchlocata/results-design.html) for missing values,
denominators, units, and interchange contracts. Corpus writing and MATLAB
workspace conversion remain outside the reader's scope.

## Documentation and support

Documentation is available in [English](https://taishi.org/torchlocata/) and
[Japanese](https://taishi.org/torchlocata/ja/index.html). Zensical's header language
selector opens each language's homepage. Both languages can also be read from
the generated HTML files.
The guides include
[getting started](https://taishi.org/torchlocata/getting-started.html), the
[API reference](https://taishi.org/torchlocata/api.html), and detailed contracts for
[data shapes](https://taishi.org/torchlocata/data-model.html),
[time and windows](https://taishi.org/torchlocata/time-and-windows.html), and
[geometry](https://taishi.org/torchlocata/geometry.html).

The reader performs no implicit silence removal, resampling, normalization,
interpolation, or invalid-row filtering. Analysis transforms are opt-in. Corpus
repair, RIR synthesis, model training, and other corpora are outside its scope.
The [validation record](https://taishi.org/torchlocata/validation.html) distinguishes
synthetic tests and existing-data integration from unverified final-release
payloads. Report problems through the [issue tracker](https://github.com/taishi-n/torchlocata/issues).

Library code is [Apache-2.0](https://github.com/taishi-n/torchlocata/blob/main/LICENSE),
with MATLAB attribution in [NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE).
LOCATA data has separate ODC-BY 1.0 attribution requirements; no corpus files are
bundled in the package. See the
[reference and license record](https://taishi.org/torchlocata/references.html).
To contribute, follow the [development guide](https://taishi.org/torchlocata/development.html).
