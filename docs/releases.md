# Release notes

## 0.1.1 — Unreleased

### Documentation

- Organize the README and getting-started guide around installing the published
  package with pip or uv and using it from an application.
- Consolidate dataset paths, storage requirements, and download behavior in the
  storage guide.
- Replace the initial release plan with maintainer release instructions and
  consolidate the published-version validation record.
- Group documentation navigation into usage, project information, and
  contributor guides.

The reader and downloader APIs and dependencies are unchanged from 0.1.0.

## 0.1.0 — 2026-10-07

Available on [PyPI](https://pypi.org/project/locata-torch/0.1.0/).
Install with `python -m pip install locata-torch` or `uv add locata-torch`.
Use `locata-torch[download]` to include download support.

### Features

- Recording and fixed-window PyTorch datasets for tasks 1–6 and all four LOCATA
  arrays, with deterministic indexing and partial WAV reads.
- Typed CPU samples with independent clocks, array/source geometry, preserved
  source IDs, optional source audio, and optional VAD.
- Padded collation with waveform lengths and masks, plus Subset, sampler, shuffle,
  and spawn-worker support.
- Explicit LOCATA world-to-array conversion, azimuth, and inclination helpers
  that require aligned pose clocks.
- Shared dataset configuration through explicit roots, `LOCATA_ROOT`, or
  completed managed storage; Dataset construction remains read-only.
- An optional downloader for the pinned official release with checked resume,
  archive hashes, ZIP64 extraction, process locks, installation inventories, and
  prepared-state recovery.
- The `locata-torch` CLI, Apache-2.0 code licensing, and English documentation.

### Validation and limits

The release passed 147 synthetic tests across the configured Python 3.10–3.14
and Linux/macOS/Windows matrix, including minimum direct dependencies. Published
wheel and sdist hashes matched validated artifacts. Independent pip and uv
consumers passed, including spawn workers; all 12 existing-data integration tests
passed with the pip-installed package.

The official final-release audio, annotation, and VAD payloads have not been
validated through a full download. Transport and extraction tests use synthetic
archives; real-data integration uses an existing challenge-era snapshot. See the
[validation record](validation.md) for the exact tested scope and artifact hashes.

## 0.1.0rc1 — 2026-10-07

Published to [TestPyPI](https://test.pypi.org/project/locata-torch/0.1.0rc1/) as the
release candidate for 0.1.0, with the same reader and downloader API. The candidate
passed the CI matrix and an independent installed-package rehearsal before the
stable release.
