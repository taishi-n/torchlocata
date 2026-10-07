# Release notes

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

Candidate publication and consumer rehearsal are pending. Validation uses small
synthetic fixtures and the existing read-only LOCATA snapshot. No official
archive is downloaded during release verification. Real final-release audio/VAD
payloads remain unverified; see the [validation record](validation.md).
