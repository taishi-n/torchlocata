# Release notes

## 0.1.0

The first stable version promotes the verified TestPyPI candidate to PyPI. Its
reader and downloader API is the same as `0.1.0rc1`. Installation instructions
use `pip install locata-torch` or `uv add locata-torch`, with the optional
`download` extra for explicit dataset preparation.

Published to [PyPI](https://pypi.org/project/locata-torch/0.1.0/) on 2026-10-07.
Both public distribution hashes matched validated CI artifacts. Independent pip
and uv installations passed, including the existing-data integration suite and
spawn checks. [English documentation](https://taishi.org/torchlocata/) is hosted
on GitHub Pages.

## 0.1.0rc1

The first release candidate includes:

- Recording and fixed-window PyTorch datasets, partial WAV reads, typed CPU
  samples, and padded collation with lengths and masks.
- Independent clocks, array/source geometry, optional source audio and VAD,
  preserved source IDs, and explicit LOCATA coordinate conversion.
- Shared dataset paths through explicit roots, environment settings, or managed
  storage, with read-only Dataset construction.
- An optional pinned-release downloader with checked resume, hashes, ZIP64
  extraction, locks, inventories, and prepared-state crash recovery. Original
  ZIP names are checked even when Python normalizes or truncates them.
- A CLI, Apache-2.0 code license, English Zensical documentation, and validated
  wheel/sdist publication through GitHub OIDC.

Published to TestPyPI on 2026-10-07. CI passed on Python 3.10–3.14 and
Linux/macOS/Windows, including minimum dependencies. An independent TestPyPI
installation passed synthetic checks, the existing-data integration suite, and
the spawn example. Validation uses small fixtures and the read-only LOCATA
snapshot; no official archive is downloaded during release verification. Real
final-release audio/VAD payloads remain unverified; see the
[validation record](validation.md).
