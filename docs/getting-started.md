# Getting started

## Install the package

Use Python 3.10 or later. The PyPI distribution is
[`locata-torch`](https://pypi.org/project/locata-torch/); its import name is
`locata_torch`.

In your application's Python environment:

```sh
python -m pip install locata-torch
```

In a uv project, add it as an application dependency:

```sh
uv add locata-torch
```

To use the downloader, install the optional extra instead:

```sh
python -m pip install "locata-torch[download]"
```

Or, with uv:

```sh
uv add "locata-torch[download]"
```

To reproduce version 0.1.0, use `"locata-torch==0.1.0"` or
`"locata-torch[download]==0.1.0"` in these commands. The package installation does
not include the LOCATA corpus. Use an existing unpacked root or explicitly
[download a split](#download-a-split).

## Read a recording and a batch

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
print(waveforms.shape, batch["lengths"], sample["sample_rate"])
```

Replace `/path/to/LOCATA` with the unpacked directory containing `dev/` or
`eval/`. Save the example as `read_locata.py` in your application and run it in
the environment where you installed the package:

```sh
python read_locata.py
```

For a uv project:

```sh
uv run python read_locata.py
```

`dataset[0]` reads one complete recording. The window view reads only the
requested WAV frames. `num_samples` and `hop_samples` are frame counts, so a
48000-frame window is one second only for a 48 kHz WAV. Short tails are excluded
with `drop_last=True`; use `False` to include and pad them at collation.

Waveforms stay on the CPU. Move `batch["waveform"]` to your chosen device in the
calling application. Annotations keep their own timestamps and remain lists in
a batch; the loader does not create dense training labels.

## Share an existing dataset

Configure one corpus root for multiple applications. In a macOS/Linux shell:

```sh
export LOCATA_ROOT=/path/to/LOCATA
locata-torch path
```

In PowerShell, use `$env:LOCATA_ROOT = "/path/to/LOCATA"`, replacing the placeholder
with a Windows path. Prefix CLI commands with `uv run` in a uv project.
Then you can omit the constructor's `root`:

```python
from locata_torch import LocataDataset

dataset = LocataDataset(split="dev", arrays=("eigenmike",))
sample = dataset[0]
```

Root lookup uses an explicit `root`, then `LOCATA_ROOT`, then a completed managed
installation. Explicit roots take priority when selecting another corpus. `~`
is expanded; empty or invalid configured paths raise errors. Reader construction
never downloads data or creates directories.

## Download a split

This operation requires the `download` extra. Prepare data before creating
DataLoader workers.

### Python API

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
sample = dataset[0]
```

Replace `/path/to/locata-store` with a managed storage directory, separate from
an existing unpacked corpus. Passing the returned root explicitly selects this
installation even when `LOCATA_ROOT` is set to another dataset.

To prepare and read both splits, pass `split=("dev", "eval")` to the downloader
and to `LocataDataset`.

### Command-line interface

For a pip installation:

```sh
locata-torch download --split dev --data-dir /path/to/locata-store
```

For a uv project:

```sh
uv run locata-torch download --split dev --data-dir /path/to/locata-store
```

The command prints the unpacked root. Pass that path as the Dataset's `root`.
Repeat `--split`, as in `--split dev --split eval`, to prepare both splits.

For persistent shared storage, set `LOCATA_DATA_DIR=/path/to/locata-store` in your
application environment and omit `--data-dir`. PowerShell uses
`$env:LOCATA_DATA_DIR = "/path/to/locata-store"`. With `LOCATA_ROOT` unset, the
reader finds completed data in this store automatically; `locata-torch path`
prints the resolved root. If neither storage option is set, downloads use the
platform's persistent user data directory.

`LOCATA_DATA_DIR` selects managed storage; `LOCATA_ROOT` points directly to an
unpacked corpus. Repeated downloads verify and reuse a completed installation.
The [official archives](https://zenodo.org/records/3630471) contain whole splits:
reader task and array filters do not reduce transfer size. Allow at least 120 GB
free to retain both ZIPs and extracted splits. See [paths and storage](storage.md)
for sizes, resume, integrity checks, and recovery.

## Select recordings

One item corresponds to `(split, task, recording, array)`:

| Parameter | Default | Accepted values |
| --- | --- | --- |
| `root` | `None` | Unpacked root as `str` or `Path`, or configured lookup |
| `split` | `"dev"` | `"dev"`, `"eval"`, or a sequence of these names |
| `tasks` | `(1, 2, 3, 4, 5, 6)` | A nonempty sequence of integers from 1 to 6 |
| `recordings` | `None` | All, or a nonempty sequence of positive recording numbers |
| `arrays` | `None` | All supported arrays, or a nonempty sequence of their names |
| `dtype` | `torch.float32` | `torch.float32` or `torch.float64` |
| `load_source_audio` | `False` | Whether to read available source WAV payloads |
| `cache_size` | `16` | Maximum cached timestamp/VAD indexes per worker; zero disables caching |
| `cache_bytes` | `16777216` | Estimated cached index bytes per worker; zero disables caching |

Recording-number filters apply across all selected tasks. A valid selection with
no matching WAV files has length zero. An empty window view can also result when
all recordings are shorter than the requested window with `drop_last=True`.

`dataset.index` is a tuple of immutable `RecordingInfo` objects, ordered by split
name, numeric task, numeric recording, and array name. Original source IDs use
natural numeric ordering within each sample. An existing array directory without
its WAV is reported through `dataset.missing_audio` and `MissingAudioWarning`.
Malformed mandatory files for an existing WAV raise an error with the path and
cause; they are not silently excluded.

## Load source audio or use float64

```python
import torch
from locata_torch import LocataDataset

dataset = LocataDataset(
    root="/path/to/LOCATA",
    split=("dev", "eval"),
    tasks=(1, 2),
    recordings=(1,),
    arrays=("benchmark2",),
    dtype=torch.float64,
    load_source_audio=True,
)
```

Source poses and VAD are returned when available, independently of source-audio
loading. File presence determines availability in either split. Source audio
can be a loudspeaker playback or close-talking recording; it is not guaranteed
to be anechoic clean speech. Missing annotations remain `None`.

## Use multiple workers

The [DataLoader guide](io-and-dataloader.md#multiple-workers-and-samplers) provides
a complete two-worker example with explicit `spawn` and a `__main__` guard.
Save it as a script in your application and run it with `python read_locata.py`
or `uv run python read_locata.py`.

Continue with the [data model](data-model.md), [time and windows](time-and-windows.md),
and [API reference](api.md) for the complete sample, batch, and geometry contracts.
