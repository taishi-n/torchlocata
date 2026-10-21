# Release notes

## 0.2.0 — 2026-10-21

### Features {#features-020}

- Add MATLAB-based ground-truth preparation, array-aligned VAD processing,
  single-source MUSIC localization, and track evaluation. The analysis guide
  maps each algorithm to the pinned official MATLAB sources and documents the
  `locata-torch-v1` metric profile and its deliberate corrections.
- Add diagnostic plots through the optional `plot` extra. Importing the reader
  does not require Matplotlib.
- Add portable JSON/CSV result bundles, optional numeric NPZ arrays, recording
  and pooled aggregation, and a separate official submission writer.
- Preserve ordered occurrences of repeated annotation timestamps and require
  explicit time bounds when evaluation should use only audio coverage.

### Documentation

- Organize the README and getting-started guide around installing the published
  package with pip or uv and using it from an application.
- Consolidate dataset paths, storage requirements, and download behavior in the
  storage guide.
- Document the maintainer release process and published-version validation.
- Group documentation navigation into usage, project information, and
  contributor guides.
- Add a Japanese README and all 15 guides, with Zensical's standard header
  language selector, localized navigation, and a search index for each language.
- Remove machine-specific paths and local environment inventories from public
  documentation.

### Validation and limits {#validation-and-limits-020}

The mandatory suite passed 193 synthetic tests. Both language builds, local
links, quality checks, and wheel/sdist validation passed. Existing-data analysis
checks cover representative challenge-era and final-release eval recordings;
no LOCATA archive download was needed. See [validation](validation.md) for
the separate synthetic and integration results.

The reader and downloader contracts are unchanged from 0.1.0. Analysis is
explicit, uses CPU tensors, and preserves missing annotations. MUSIC remains a
single-source baseline. MATLAB execution equivalence and historical leaderboard
reproduction have not been established.

## 0.1.0 — 2026-10-07

Available on [PyPI](https://pypi.org/project/locata-torch/0.1.0/).
Install with `python -m pip install locata-torch` or `uv add locata-torch`.
Use `locata-torch[download]` to include download support.

### Features {#features-010}

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

### Validation and limits {#validation-and-limits-010}

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
