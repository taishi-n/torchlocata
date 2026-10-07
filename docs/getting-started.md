# Getting started

## Install from the repository

Use Python 3.10 or later and an existing LOCATA dataset. For local development:

```sh
uv sync --python 3.12
```

The package name is `locata-torch`; the import name is `locata_torch`. The library
does not download or modify the corpus.

## Read a recording and a batch

```python
from locata_torch import LocataDataset, collate_locata
from torch.utils.data import DataLoader

dataset = LocataDataset(
    root="~/dataset/LOCATA",
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

Replace the root with your path. `~` is expanded; no local path is hard-coded.
`num_samples` and `hop_samples` are frame counts, so a 48000-frame window is one
second only for a 48 kHz recording. The reader does not resample.

## Select recordings

One recording item corresponds to `(split, task, recording, array)`. Constructor
filters have the following contracts:

| Parameter | Default | Accepted values |
| --- | --- | --- |
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
    root="~/dataset/LOCATA",
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

```sh
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 0
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2
```

The example uses an explicit `spawn` context and a `__main__` guard. Read the
[I/O and DataLoader guide](io-and-dataloader.md) before using multiple workers,
and the [data model](data-model.md) for the full sample and batch schemas.
