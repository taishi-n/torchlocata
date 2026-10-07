# locata-torch

Read LOCATA recordings and independent annotations through PyTorch's map-style
`Dataset` and `DataLoader`. The `locata_torch` package returns CPU tensors and
requires only PyTorch, NumPy, and SoundFile at runtime.

## Start reading data

[Get started](getting-started.md) with a recording dataset, a fixed-length window
view, and a padded batch. Both dataset views support PyTorch `Subset`, standard
samplers, and shuffle. Source audio is loaded only when requested.

The reader accepts an existing LOCATA root with this structure:

```text
LOCATA/
├── dev/
│   └── task1/
│       └── recording1/
│           └── benchmark2/
│               ├── audio_array_benchmark2.wav
│               ├── audio_array_timestamps_benchmark2.txt
│               ├── position_array_benchmark2.txt
│               └── required_time.txt
└── eval/
    └── task1/...
```

It supports tasks 1–6 and the `benchmark2`, `dicit`, `dummy`, and `eigenmike`
arrays. Available WAV files determine the index; the reader obtains frame counts,
channel counts, and sample rates from their headers.

## Understand the contract

| Guide | What it defines |
| --- | --- |
| [Data model](data-model.md) | Tensor shapes, units, source IDs, and missing values |
| [Time and windows](time-and-windows.md) | Independent clocks, calendar origin, frame intervals, and annotation boundaries |
| [Geometry and DOA](geometry.md) | World-to-array rotation and LOCATA angle conventions |
| [I/O and DataLoader](io-and-dataloader.md) | Lazy reads, bounded caches, errors, collation, and workers |
| [API reference](api.md) | Public classes, functions, and typed schemas from the source |

The default reader preserves amplitudes, channel order, clocks, and invalid
annotation rows. It does not remove silence, resample, normalize, interpolate,
or create dense labels. Missing ground truth remains missing, independently of
the split name.

## Scope and evidence

Downloading or extracting archives, repairing the corpus, synthesizing RIRs,
training models, porting official metrics, and supporting other corpora are
outside the initial scope. This is an independent implementation without a
TorchRIR dependency.

The [reference record](references.md) identifies the official specifications,
compared readers, versions, licenses, and unresolved assumptions. The
[validation record](validation.md) separates synthetic tests from checks on the
local LOCATA snapshot. See [development](development.md) to run checks or build
this documentation.
