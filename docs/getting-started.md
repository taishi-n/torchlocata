# Getting started

## Install from PyPI after publication

Use Python 3.10 or later. The distribution name is `locata-torch`; the Python
import name is `locata_torch`.

These instructions target the first PyPI release; publication is pending. Root
lookup, the `download` extra, and the API/CLI described here are implemented.

### With pip

In your application's Python environment, install the reader:

```sh
python -m pip install locata-torch
```

For downloading, install the extra instead:

```sh
python -m pip install "locata-torch[download]"
```

`python -m pip` installs into the selected Python interpreter's environment; see
the official [pip guide](https://pip.pypa.io/en/stable/user_guide/#installing-packages).

### In an existing uv project

From your own project's directory, add the reader dependency:

```sh
uv add locata-torch
```

To include download support:

```sh
uv add "locata-torch[download]"
```

Run application scripts and installed CLI commands with `uv run`. `uv add`
records the dependency in your `pyproject.toml` and updates the project environment
and lockfile; see the official [uv project guide](https://docs.astral.sh/uv/guides/projects/).
After version `0.1.0` is published, pin that release when needed with
`python -m pip install "locata-torch==0.1.0"` or `uv add "locata-torch==0.1.0"`.

The Python package installation does not include the LOCATA corpus. Supply an
existing unpacked root, or explicitly prepare data using the workflow below.

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

Replace `/path/to/LOCATA` with your path, or omit `root` after configuring
`LOCATA_ROOT` or preparing managed data. `~` is expanded; no local path is hard-coded.
`num_samples` and `hop_samples` are frame counts, so a 48000-frame window is one
second only for a 48 kHz recording. The reader does not resample.

Save this code as `read_locata.py` in your application. Run it in the same
environment used for installation:

```sh
python read_locata.py
```

For a uv project:

```sh
uv run python read_locata.py
```

Use the same imports from any Python application. Waveforms are CPU tensors;
transfer a batch to a GPU explicitly in the calling application when needed.

## Configure a shared existing root

The reader resolves paths in this order: an explicit `root`,
then `LOCATA_ROOT`, then the managed downloaded root. Configure one existing
corpus for multiple projects in a macOS/Linux shell:

```sh
export LOCATA_ROOT=/path/to/LOCATA
```

In Windows PowerShell, use `$env:LOCATA_ROOT = "/path/to/LOCATA"`, replacing the
placeholder with your Windows path. With this setting, the API
allows the root to be omitted:

```python
from locata_torch import LocataDataset

dataset = LocataDataset(split="dev", arrays=("eigenmike",))
sample = dataset[0]
```

`LOCATA_ROOT` identifies the unpacked directory containing `dev/` or `eval/`.
Invalid explicit paths and empty or invalid environment settings raise errors.
The reader never starts network activity or creates directories.

## Download and read data

This section requires the `download` extra.
The downloader prepares an official split and returns an unpacked root; create
datasets and DataLoader workers after that operation completes.

### From Python

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
sample = dataset[0]
print(sample["waveform"].shape, sample["sample_rate"])
```

Passing the returned root explicitly selects this installation even when
`LOCATA_ROOT` points to a different corpus. Replace `/path/to/locata-store` with
your storage directory. Download both splits with `split=("dev", "eval")`, then
read them with `LocataDataset(root=root, split=("dev", "eval"))`.

### From the CLI

With `LOCATA_ROOT` unset, configure the managed storage directory in a macOS/Linux
shell. For a pip installation:

```sh
export LOCATA_DATA_DIR=/path/to/locata-store
locata-torch download --split dev
locata-torch path
```

For a uv project:

```sh
export LOCATA_DATA_DIR=/path/to/locata-store
uv run locata-torch download --split dev
uv run locata-torch path
```

In PowerShell, set `$env:LOCATA_DATA_DIR = "/path/to/locata-store"` instead of
`export`. Either paste the root printed by `locata-torch path` into the explicit-root
example, or use `LocataDataset(split="dev", arrays=("eigenmike",))`
lookup. Add `--split eval` to the download command to prepare both splits.
Then run your configured script with `python read_locata.py` or
`uv run python read_locata.py`.

`LOCATA_DATA_DIR` is a managed storage base, while `LOCATA_ROOT` is an unpacked
corpus root. If no storage directory is configured, the downloader uses
the platform-standard persistent data directory. Repeated downloads reuse a
completed managed installation. Reading never starts a download automatically.

The [official archives](https://zenodo.org/records/3630471) are about 6.2 GB for
dev and 13.0 GB for eval. Downloads operate on whole splits; selecting an array or
task in the reader does not reduce the transfer. Archive-directory inspection
found about 103.8 GB for both retained ZIPs and extracted splits; allow at least
120 GB free for that workflow. See the [release plan](release-plan.md) for the
storage estimate, integrity checks, and separate dataset license and attribution.
The [storage guide](storage.md) defines resume, recovery, and reuse behavior.

## Select recordings

One recording item corresponds to `(split, task, recording, array)`. Constructor
filters have the following contracts:

| Parameter | Default | Accepted values |
| --- | --- | --- |
| `root` | `None` | Existing unpacked root, or explicit/env/managed lookup |
| `split` | `"dev"` | `"dev"`, `"eval"`, or a sequence of these names |
| `tasks` | `(1, 2, 3, 4, 5, 6)` | A nonempty sequence of integers from 1 to 6 |
| `recordings` | `None` | All, or a nonempty sequence of positive recording numbers |
| `arrays` | `None` | All supported arrays, or a nonempty sequence of their names |
| `dtype` | `torch.float32` | `torch.float32` or `torch.float64` |
| `load_source_audio` | `False` | Whether to read available source WAV payloads |
| `cache_size` | `16` | Maximum cached timestamp/VAD indexes per worker; zero disables caching |
| `cache_bytes` | `16777216` | Estimated cached index bytes per worker; zero disables caching |

Recording-number filters apply across all selected tasks. Empty selections,
unknown splits or arrays, and invalid numbers raise errors. A valid selection
with no matching WAV files produces a dataset of length zero.

`dataset.index` is a tuple of immutable `RecordingInfo` objects. It sorts by split
name, numeric task, numeric recording, and array name. Source IDs keep their
original strings and use natural numeric ordering within each sample. Array
directories without a WAV are reported through `dataset.missing_audio` and
`MissingAudioWarning`.

## Opt into source audio or float64

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

Source poses and available VAD are returned independently of the source-audio
option. File presence determines availability, including in `eval`. A source
signal can be a loudspeaker playback or close-talking recording; it is not
guaranteed to be anechoic clean speech.

## Run the multiple-worker example

The [I/O and DataLoader guide](io-and-dataloader.md#multiple-workers-and-samplers) contains
a complete example with two workers, explicit `spawn`, and a `__main__` guard.
Save that example as `read_locata.py` in your application, replace the placeholder
root, and run `python read_locata.py` or `uv run python read_locata.py`.

For development from this checkout, the repository also includes:

```sh
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 0
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2
```

Read the [data model](data-model.md) for the full sample and batch schemas.

## Develop from the repository

Inside a source checkout, install development dependencies with:

```sh
uv sync --python 3.12 --extra download --group docs --group release
```

See the [development guide](development.md) for tests, type checks, and
documentation commands.
