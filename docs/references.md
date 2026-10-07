# References and design decisions

## Primary sources reviewed

The following sources were inspected read-only on 2026-10-07. External readers
were used to compare specifications; their code was not copied, translated, or
moved into this library. The implementation is independent and does not
redistribute LOCATA data. The new package's own publication license is not yet set.

| Source | Reviewed version | License and use |
| --- | --- | --- |
| [LOCATA Datasets](https://www.locata.lms.tf.fau.de/datasets/) | Content checked on 2026-10-07 | Final-release and dev-correction notices reviewed; the page's reuse license is unconfirmed |
| [LOCATA final release](https://zenodo.org/records/3630471) | v1, 2020-01-31, DOI 10.5281/zenodo.3630471 | The [metadata API](https://zenodo.org/api/records/3630471) gives license ID `odc-by`; data conditions are not assigned to this implementation |
| [Final Release Documentation](https://www.locata.lms.tf.fau.de/files/2020/01/Documentation_LOCATA_final_release_V1.pdf) | Version 1.0, 2020-01-31 | Final dev/eval source ground truth, VAD naming, and world/local coordinates reviewed; the PDF's own reuse conditions are unconfirmed |
| [cevers/sap_locata_io](https://github.com/cevers/sap_locata_io/tree/632468f49b13ca5a9f2f51c064d91183c06622fa) | Commit `632468f49b13ca5a9f2f51c064d91183c06622fa` | Reviewed MATLAB headers state ODC-BY 1.0; specifications and formulas consulted without code reuse |
| [Cross3D reader](https://github.com/DavidDiazGuerra/Cross3D/blob/2532cf57160aef67f7fdedccc7452aa422ea7a24/acousticTrackingDataset.py) | Commit `2532cf57160aef67f7fdedccc7452aa422ea7a24` | Repository LICENSE is AGPL-3.0; task 1/3/5 restriction, pandas/webrtcvad/gpuRIR dependencies, resampling, silence removal, and interpolation reviewed; no code reused |
| [SRP-DNN reader](https://github.com/BingYang-20/SRP-DNN/blob/e67c2a9d24d8707048f38e09146fb2d3cbc9be8d/code/Dataset.py) | Commit `e67c2a9d24d8707048f38e09146fb2d3cbc9be8d` | MIT, Copyright 2023 BingYang; multiple-source enumeration and the `VAD` column consulted; preprocessing, mandatory VAD, and extra dependencies were not adopted; no code reused |
| [PyTorch torch.utils.data](https://docs.pytorch.org/docs/2.9/data.html) | Version-pinned 2.9 documentation | Map-style Dataset, samplers, custom collation, spawn, and pickling requirements reviewed; PyTorch has a BSD-style license; documentation examples were not copied |

The MATLAB files reviewed were `utils/load_data.m`, `struct2time.m`,
`struct2position.m`, `get_truth.m`, and `mycart2sph.m`. Even the repository
advertising the final release retains an old `is_dev` source-loading restriction.
That branch is not part of this reader's contract.

The implementation follows `get_truth.m`'s `R'*(h-p)` formula and
`mycart2sph.m`'s azimuth and inclination definitions. No execution comparison
against MATLAB has been performed.

## Local snapshot

`~/datasets/LOCATA` did not exist; `~/dataset/LOCATA` was present. This is a user
input path, not a default embedded in the implementation. Local
`documentation_v2.pdf` (Version 2.0, 2018-04-05), `documentation_v3.pdf`
(Version 3.0, 2018-04-17), and the same five `matlab_v2` functions were reviewed.
These are challenge-era files and are distinguished from the final release.

| Checked file | SHA-256 |
| --- | --- |
| Final release documentation v1, obtained for inspection | `05c2b6948b5783ffcf59126a238ce14b4c29b072d3472189f5d5ffd320654c25` |
| `documentation_v2.pdf` | `84747303cb4a4dac0d7e850f12c105c8cca5f73ca7d6b21bf1aef3caf9811f31` |
| `documentation_v3.pdf` | `0679e408963c529d61e83a19c6f0a32133df67da07fb9e3581689670f00c698b` |
| `matlab_v2/utils/load_data.m` | `6636167192bd2f21079b9d55241815cea49f6c54cc00f2eda447dd90aa3f9e9d` |
| `matlab_v2/utils/struct2time.m` | `703242dec2087f78c7465e2bbb84744709ef13594c57bd720e1cde690954c1d0` |
| `matlab_v2/utils/struct2position.m` | `b7f78cdaa3336d85e53e6372e9da4eb741fb75c3ee2464086af99f8b9185657c` |
| `matlab_v2/utils/get_truth.m` | `ed77f68076e316b673e7a1dac26bdcc96f62ab65cc901c1facf28fa7d3a2e8f1` |
| `matlab_v2/utils/mycart2sph.m` | `0625681763e3303490a716562dd8ea182ce83782c49b583f7947411af5d789ea` |

The four functions other than `load_data.m` matched the referenced GitHub commit
byte for byte. The snapshot had 72 dev and 154 eval array WAVs. These existing
eval directories contained no WAV:

- `eval/task4/recording4/dicit`
- `eval/task6/recording5/dicit`

Dev contained source audio and poses; eval had no source files, and neither split
had VAD files. Counts and missing paths are not hard-coded. These observations
do not constitute integration validation of the final-release archive.

## Design decisions and constraints

- Recording and window views are separate datasets. The recording index reads
  headers only; the window view stores cumulative counts per recording.
- Validated sparse TXT indexes preserve the original clocks. First access needs a
  full stream scan per worker. Indexes are bounded in memory, not shared between
  workers, and never written under the corpus.
- Window annotations use actual, half-open time intervals. Array and source audio
  need not share sample rates or start times.
- Missing annotations use `None`; an existing empty interval uses empty tensors.
  Validity flags remain independent of VAD.
- DOA requires exactly matched clocks. Temporal and rotation interpolation are
  outside the initial scope.
- Nonuniform clocks remain unchanged. Only the endpoint after the last audio
  sample uses the nominal `1/fs` period.
- Boundary comparisons alone use a `1e-12` second tolerance to avoid including an
  end row due to floating-point error. Raw timestamps and the 4 ms offset remain.
- The raw reader retains nonfinite world geometry and invalid rows. DOA helpers
  accept only finite geometry.
- Duplicate source-pose timestamps were found locally: 53 pairs for hendrik in
  `dev/task3/recording2/dummy`, 210 for christine in
  `dev/task5/recording1/eigenmike`, and 115 for christine in
  `dev/task6/recording3/benchmark2`. Annotation clocks may be nondecreasing;
  audio clocks must strictly increase. All annotation rows are retained.
- No real VAD files are available locally. Naming and values are based on official
  documentation, the SRP-DNN `VAD` column, and synthetic fixtures. Final-release
  VAD integration remains unverified.
- No dense-label conversion, training-transform framework, general plugin system,
  or compatibility aliases are provided.
- Development checks use pytest, Ruff, and ty. Zensical and mkdocstrings are
  isolated in the optional `docs` dependency group. Documentation is English;
  generated HTML is not tracked. No publishing or release workflow is configured.

The package does not guarantee that source audio is a perfect clean training
target and is not a replacement for the official evaluation tools.

## Documentation tooling

The migration follows the official [Zensical configuration](https://zensical.org/docs/setup/basics/),
[offline usage](https://zensical.org/docs/setup/offline/), and
[mkdocstrings compatibility](https://zensical.org/docs/compatibility/mkdocs/plugins/)
guides, with Python API collection configured according to
[mkdocstrings-python](https://mkdocstrings.github.io/python/usage/).
Installed tool versions and the executed documentation checks are recorded in
[validation](validation.md). These tools are used to build documentation, not
imported by the runtime library.
