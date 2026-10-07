# locata-torch

An independent Python library for reading LOCATA recordings, timestamps, and
position annotations with PyTorch `Dataset` and `DataLoader`. Import it as
`locata_torch`. It returns CPU tensors and does not depend on TorchRIR.

## Scope and installation

Python 3.10 or later is supported. Runtime dependencies are PyTorch, NumPy,
SoundFile, and platformdirs. The reader uses an existing dataset at
`root/{dev,eval}/task{1..6}/recording{number}/{array}/` and supports `benchmark2`,
`dicit`, `dummy`, and `eigenmike`. Channel counts, sample rates, and frame counts
come from WAV headers.

The code is licensed under Apache-2.0, separately from the LOCATA data license.
The first PyPI release includes explicit downloading and extraction; release
validation is tracked in the [release plan](docs/release-plan.md). Repairing data, RIR
synthesis, model training, official evaluation metrics, and other corpora remain
outside the scope.

### Install after PyPI publication

These commands target the first PyPI release; publication is pending.
Choose the command for your Python environment:

| Environment | Read an existing dataset | Include download support |
| --- | --- | --- |
| pip | `python -m pip install locata-torch` | `python -m pip install "locata-torch[download]"` |
| Existing uv project | `uv add locata-torch` | `uv add "locata-torch[download]"` |

Import `locata_torch` in your own application and use the quick start below with
your dataset root. For the download API, CLI, and shared path settings,
see the [published-package tutorial](docs/getting-started.md).
Command syntax follows the official [pip installation guide](https://pip.pypa.io/en/stable/user_guide/#installing-packages)
and [uv project guide](https://docs.astral.sh/uv/guides/projects/).

### Install from the checkout

For local development, run this inside the repository:

```sh
uv sync --python 3.12
```

## Quick start

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

Replace `/path/to/LOCATA` with your dataset root; `~` is also expanded.
One recording item represents
`(split, task, recording, array)`. `split`, `tasks`, `recordings`, and `arrays`
select recordings. The index sorts split and array names lexically, and task and
recording numbers numerically. Standard `Subset` and samplers work with both
recording and window datasets.

## Dataset paths and explicit preparation

`LocataDataset(root=None, ...)` resolves an explicit root first, then `LOCATA_ROOT`,
then the managed final-release root. An invalid or empty configured path raises an
error instead of falling back. The selected absolute path is retained for workers.
Construction never downloads data or creates directories. Explicit and
environment-supplied roots need no managed installation manifest.

Managed storage is selected by `download_locata(..., data_dir=...)`, then
`LOCATA_DATA_DIR`, then the platform-standard persistent user data directory.
`LOCATA_ROOT` points to an unpacked corpus and never redirects a download.
Only completed managed splits can be selected through the default root lookup.

```sh
export LOCATA_ROOT=/path/to/LOCATA
locata-torch path
```

Download once before constructing DataLoader workers:

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
```

Install the `download` extra for process locking. The download API accepts `dev`,
`eval`, or a nonempty sequence of these splits; CLI `--split` can be repeated.
Transfers are streamed, resumable, and checked against the pinned official size
and MD5. ZIP64 contents are validated and extracted to staging outside the readable
root. Completed splits are installed atomically, and subsequent requests verify
and reuse them. Existing or altered installations are never overwritten or repaired.
Archives, manifests, partial transfers, and locks live outside the dataset root.
The reader continues to use only bounded in-memory timestamp caches.

```sh
export LOCATA_DATA_DIR=/path/to/locata-store
locata-torch download --split dev --split eval
```

The pinned data release is DOI `10.5281/zenodo.3630471`, independent of the library
version. Both archives and extracted splits require about 103.8 GB; allow 120 GB
for a fresh installation. Download and extraction are verified with synthetic
archives; final-release audio and VAD payloads remain unverified. A download does
not resample, normalize, trim, repair,
or generate labels. Dataset attribution and ODC-BY 1.0 notices are retained in the
installation record; dataset assets are excluded from package distributions.

Waveforms default to `torch.float32`; choose `dtype=torch.float64` explicitly.
Source audio is opt-in with `load_source_audio=True`. The reader preserves channel
order and amplitude, without silence removal, resampling, normalization,
interpolation, or removal of invalid annotation rows.

## Data contract

`LocataSample` is a public `TypedDict`. Waveforms have shape `[channels, samples]`;
timestamps and geometry use float64, and flags use bool. Each item contains:

- `waveform`, `sample_rate`, and an independent `audio_time` for every sample.
- `time_origin`: the first array-audio calendar timestamp, including fractional
  seconds. All independent clocks use relative seconds from this shared origin.
- `required_time`: timestamps and `valid_flag`, independent of voice activity.
- `array_pose`: world position, reference vector, local-to-world rotation,
  microphone positions, and their own timestamps.
- `sources`: original source IDs mapped to optional pose, audio, and VAD.
- `metadata`: recording identity, path, half-open frame interval, and time bounds.

Missing annotations are `None`; an available annotation with no rows in a window
is an empty tensor. Missing ground truth and VAD are never filled with zero
labels. Source availability is determined by files, including in `eval`. Source
audio is a playback or close-talking signal, without a guarantee of anechoic
clean speech.

Windows read only the requested WAV frames. They retain the recording's time
origin and crop each independent annotation clock to the window's half-open time
interval. Short tails are returned with `drop_last=False` and padded by
`collate_locata`, which returns `lengths` and a padding-only `audio_mask`.
Collation requires the same array, sample rate, channel count, and dtype;
variable annotations and source counts remain lists per sample.

The geometry helpers use LOCATA's `R.T @ (h - p)` convention. `locata_doa` requires
exactly matched pose clocks, returns azimuth measured from +y in `[-pi, pi)`, and
uses `inclination` from +z in `[0, pi]`. Angles are radians and distance is metres.

See the detailed [data model](docs/data-model.md), [time and window
contract](docs/time-and-windows.md), [geometry](docs/geometry.md), and [I/O and
DataLoader contract](docs/io-and-dataloader.md).

## Documentation

The English documentation is built with Zensical. Install documentation tools
separately from runtime dependencies:

```sh
uv sync --group docs
uv run --group docs zensical serve
```

Build a static site and check its local links:

```sh
uv run --group docs zensical build --clean --strict
uv run python scripts/check_docs_links.py site
```

Open `site/index.html` directly or use the preview server. The site includes a
source-generated API reference, tutorials, the complete data contract, development
instructions, and the [reference and license record](docs/references.md). Generated
HTML is ignored by version control.

## Development and verification

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2
```

Install development, download-test, documentation, and release tools with
`uv sync --extra download --group docs --group release`. CI tests supported Python
versions, minimum direct dependencies, Linux/macOS/Windows, and fresh artifact
installations. No LOCATA archive is downloaded by CI.

The release workflow validates one wheel/sdist set before publishing it with
GitHub OIDC. An exact stable `vX.Y.Z` tag publishes to PyPI; an exact
`vX.Y.ZrcN` tag publishes to TestPyPI. The tag must match package metadata.
Manual validation never publishes. Artifacts include the Apache-2.0 license and
`py.typed`, and exclude corpus files and generated sites. See the
[release plan](docs/release-plan.md) for account configuration and remaining steps.

Mandatory tests create small synthetic WAV and TXT files in temporary directories.
Real-data tests run only with an explicit `LOCATA_ROOT`. The multiple-worker example
uses `spawn` and a `__main__` guard. Dataset files remain read-only; the library
writes no index or cache inside the corpus.

Read the [documentation overview](docs/index.md), [development
guide](docs/development.md), and [validation record](docs/validation.md) for
commands, executed checks, and remaining limitations.
