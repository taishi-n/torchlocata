# locata-torch

Read LOCATA audio and independent annotations with PyTorch's map-style `Dataset`
and `DataLoader`. Install [locata-torch from PyPI](https://pypi.org/project/locata-torch/)
and import `locata_torch` in your application. Python 3.10 or later is required.

The library provides recording datasets, fixed-length windows, padded batches,
LOCATA coordinate helpers, and an optional downloader. All returned tensors are
on the CPU. It supports tasks 1–6 and the `benchmark2`, `dicit`, `dummy`, and
`eigenmike` arrays, including multiple sources and moving arrays.

## Start here

| Goal | Guide |
| --- | --- |
| Install with pip or uv and load your first batch | [Getting started](getting-started.md) |
| Share existing data across applications or download a split | [Paths and storage](storage.md) |
| Find a class, function, or typed schema | [API reference](api.md) |
| Use multiple workers, samplers, or variable-length batches | [I/O and DataLoader](io-and-dataloader.md) |

An existing unpacked root has this structure:

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

Available WAV files determine the index. Channel counts, sample rates, and frame
counts come from their headers. Source poses, source audio, and VAD are optional;
file presence determines availability in either split.

## Work with annotations

[Data model](data-model.md) defines tensor shapes, units, source IDs, and missing
values. [Time and windows](time-and-windows.md) explains independent clocks,
calendar origins, and window boundaries. [Geometry and DOA](geometry.md) defines
world-to-array rotation and the LOCATA angle convention.

The reader preserves amplitudes, channel order, timestamps, and invalid annotation
rows. It performs no implicit silence removal, resampling, normalization,
interpolation, or dense-label conversion. Missing ground truth remains missing;
validity flags and voice activity remain separate.

## Project information

Library code is Apache-2.0; LOCATA data uses separate ODC-BY 1.0 attribution
requirements. The [reference record](references.md) identifies reviewed sources,
licenses, and design decisions. The [validation record](validation.md) describes
the tested configurations and unverified final-release payloads.

See [release notes](releases.md) for version history,
[development](development.md) to contribute or build the documentation, and the
[release process](release-plan.md) for maintainer operations. Corpus repair,
RIR synthesis, model training, official evaluation metrics, and other corpora
are outside the library's scope. It has no TorchRIR dependency.
