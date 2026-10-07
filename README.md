# locata-torch

Read LOCATA recordings, timestamps, and position annotations with PyTorch
`Dataset` and `DataLoader`. [locata-torch](https://pypi.org/project/locata-torch/)
is available on PyPI; import it as `locata_torch` in your own application.

The library provides recording datasets, fixed-length window views, padded
batches, coordinate helpers, and an optional downloader for the official LOCATA
release. It returns CPU tensors and works independently of TorchRIR.

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

## Documentation and support

The [documentation](https://taishi.org/torchlocata/) includes
[getting started](https://taishi.org/torchlocata/getting-started.html), the
[API reference](https://taishi.org/torchlocata/api.html), and detailed contracts for
[data shapes](https://taishi.org/torchlocata/data-model.html),
[time and windows](https://taishi.org/torchlocata/time-and-windows.html), and
[geometry](https://taishi.org/torchlocata/geometry.html).

The reader performs no implicit silence removal, resampling, normalization,
interpolation, or invalid-row filtering. Corpus repair, RIR synthesis, model
training, official evaluation metrics, and other corpora are outside its scope.
The [validation record](https://taishi.org/torchlocata/validation.html) distinguishes
synthetic tests and existing-data integration from unverified final-release
payloads. Report problems through the [issue tracker](https://github.com/taishi-n/torchlocata/issues).

Library code is Apache-2.0. LOCATA data has separate ODC-BY 1.0 attribution
requirements; no corpus files are bundled in the package. See the
[reference and license record](https://taishi.org/torchlocata/references.html).
To contribute, follow the [development guide](https://taishi.org/torchlocata/development.html).
