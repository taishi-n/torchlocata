# Validation record

Checks were run on 2026-10-07 with macOS arm64 and Python 3.12.8. A local LOCATA
snapshot was used read-only. Its local path is omitted; paths in commands are
placeholders. Local results below are distinct from remote GitHub Actions
execution.

## Initial implementation: synthetic tests and development checks

| Check | Result |
| --- | --- |
| `uv run pytest -q`, without `LOCATA_ROOT` | 62 passed, 12 optional integration tests skipped |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed, 17 Python files |
| `uv run ty check` | Passed for source and examples |
| `uv build` | Wheel and sdist generated |
| Wheel and sdist inspection | `py.typed` included; no real data, PDFs, ZIPs, virtual environment, or caches |
| README Python example | Passed with only the corpus path replaced by a temporary fixture |

Mandatory fixtures are small synthetic DOUBLE WAV and TXT files in temporary
directories. No real data was copied into the repository. Specifications and
tests preceded implementation: four import collection errors were confirmed
before the package existed. Duplicate annotation times found in real data also
received a documented regression test that failed before the implementation fix.

Synthetic tests cover numeric index order, multiple arrays and source IDs,
optional absence, corrupt mandatory files, dtype, and agreement with original
waveforms. They exercise independent clocks, the 4 ms offset, date rollover,
duplicate pose times, validity flags, rotations, and angle boundaries.

Window tests cover hops, short recordings, tails, annotation boundaries, empty
source intervals, partial WAV frame counts, sparse TXT index reuse, and cache
limits. Loader tests cover padding, masks, Subset, samplers, shuffle, spawn with
two workers, pickling, and no writes beneath the dataset root. VAD verification
uses synthetic data and does not validate actual final-release VAD files.

## Real-data integration

The integration run passed all 12 tests. With a placeholder for the actual root,
the command was `LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration -v`.
Header indexing found 72 dev and 154 eval array WAVs. The checked headers had
15 dicit, 4 dummy, 32 eigenmike, and 12 benchmark2 channels, at 48 kHz.
The integration run checked the index and the following representative recordings,
not every waveform payload.

| Recording | Checked source IDs and configuration |
| --- | --- |
| `dev/task1/recording1/benchmark2` | `loudspeaker1`, static single source |
| `dev/task2/recording1/dicit` | `loudspeaker3`, `loudspeaker4`, multiple sources |
| `dev/task3/recording2/dummy` | `hendrik`, moving source and duplicate pose times |
| `dev/task5/recording1/eigenmike` | `christine`, moving array |
| `dev/task6/recording3/benchmark2` | `christine`, `hendrik`, moving array and multiple sources |
| `eval/task1/recording1/eigenmike` | No source ground truth, source audio, or VAD |
| `eval/task4/recording3/dummy` | No source files |
| `eval/task6/recording3/benchmark2` | Moving array, no source files |

For each representative recording, partial waveforms matched an independent
SoundFile read. Channel counts, clocks, microphone positions, and available source
audio and poses were checked. The static reference recording was also read in
full: 155072 samples, 389 pose rows, audio beginning at `15:40:25.068`, and pose
and required times beginning at `15:40:25.064`. Relative times were `0` and
`-0.004` seconds, without a fixed correction. Full-waveform slices exactly matched
window reads. Its DataLoader passed with zero workers and explicit spawn with two.

The WAV-less `eval/task4/recording4/dicit` and `eval/task6/recording5/dicit`
directories were excluded and surfaced through warnings and `missing_audio`.
Input sizes and modification times matched before and after index construction
and representative reads.

The real-data spawn test transferring large tensors stalled inside the sandbox;
it was interrupted and the same read-only check passed outside the sandbox.
Synthetic spawn checks also passed inside the sandbox.

## Executable examples

`examples/read_locata.py` ran against the real root with zero workers and spawn
with two workers. Both returned `[4, 32, 48000]` batches at 48 kHz. Shuffled
recordings included tasks 3, 4, 5, and 6 and multiple sources.

The initial checks used Torch 2.14.1, NumPy 2.5.3, SoundFile 0.14.0, pytest 9.1.1,
Ruff 0.16.10, and ty 0.0.85.

## English documentation and Zensical migration

The documentation migration was checked separately on 2026-10-07. README and all
documentation sources are English, including public API docstrings. The existing
English `AGENTS.md` was preserved. Zensical 0.0.68, mkdocstrings-python 2.0.9, and
mkdocstrings 1.0.6 were installed through the optional `docs` dependency group;
runtime dependency versions remained unchanged.

| Check | Result |
| --- | --- |
| `uv run pytest -q`, without `LOCATA_ROOT` | 71 passed, 12 optional integration tests skipped |
| README and getting-started examples | Both executed unchanged except for the synthetic fixture root |
| Link-checker regression tests | Passed for page/asset references, fragments, missing targets, directory URLs, and escaping paths |
| `uv run ruff check .` and `uv run ruff format --check .` | Passed |
| `uv run ty check` | Passed for source, examples, and the documentation checker |
| `uv run --group docs zensical build --clean --strict` | Passed without warnings; 10 documentation pages |
| `uv run python scripts/check_docs_links.py site` | All local page, HTML-fragment, and asset references resolved |
| Skill-provided direct-file link checker | Passed for all 10 documentation pages |
| `uv run --group docs zensical serve` | Started the local preview at `http://localhost:8000` |
| Safari local-file preview | Sidebar navigation opened the API reference; the overview's content link opened the tutorial; API content and tutorial code rendered |
| Safari local-file search | Query `inclination` returned the API and angle-convention sections |
| `uv build` and archive inspection | Wheel and sdist built; `py.typed` present; generated `site/`, `.cache/`, and virtual-environment files excluded |
| Source language audit | No Japanese characters found in Markdown, Python, TOML, or workflow sources |

The new tutorial and link-checker tests were run before their files were added,
confirming the expected missing-file failures. The documentation-only change did
not rerun the real-data integration suite; those 12 passed checks are the earlier
implementation results recorded above. Documentation checks are included in CI,
but remote CI and site publication have not been performed.

## Release planning and placeholder roots

The release plan and documentation path changes were checked on 2026-10-07.
README and tutorial examples use `/path/to/LOCATA`. Their execution tests first
failed because the old fixture substitution no longer matched, then passed after
the substitution was updated to the placeholder. The production reader API was
not changed.

| Check | Result |
| --- | --- |
| `uv run pytest -m 'not integration' -q` | 71 passed, 12 integration tests deselected |
| `uv run ruff check .` and `uv run ruff format --check .` | Passed |
| `uv run ty check` | Passed |
| `uv build --no-sources` | Wheel and sdist built |
| `uv run --group docs zensical build --clean --strict` | Passed; 11 documentation pages |
| `uv run python scripts/check_docs_links.py site` | All local page, fragment, and asset references resolved |
| Documentation language and path audit | English sources; no user-specific dataset paths |

Official archive sizes and checksums were read from Zenodo metadata. Bounded HTTP
range requests inspected only ZIP64 end records and central directories, including
declared expanded sizes and VAD filenames. No complete archive or audio/VAD payload
was fetched. Dataset contents were not modified, and real-data integration was
not rerun. These checks do not validate the planned downloader or release workflow.

## Published-package usage instructions

The README and getting-started guide now describe pip/uv installation after
publication, use from an application, shared roots, and the planned download
API/CLI. Current reader examples are distinguished from pending release features.

The README/tutorial execution and link-checker tests passed: 10 tests. Strict
Zensical build, generated-site link checks, and `uv build --no-sources` passed.
Documentation remained English with placeholder dataset paths. PyPI installation
commands were not executed; environment lookup and downloader examples require
the planned implementation. The library code and dependencies were unchanged.

## Path configuration, downloader, and release preparation

The release implementation was checked on 2026-10-07. Documentation and new tests
preceded implementation: configuration/CLI imports and the download API initially
failed collection, and the release validator initially failed because its file
did not exist. Cache-space, portable-path, and eval-only CLI regressions also
failed before their fixes.

| Check | Result |
| --- | --- |
| Synthetic tests, Python 3.12.8, current dependencies | 146 passed; 12 integration tests deselected |
| Synthetic tests, Python 3.10.16, minimum direct dependencies | 146 passed; 12 integration tests deselected; installed wheel, not editable source |
| Existing-data integration, Python 3.12.8 | All 12 tests passed again, including zero/spawn workers |
| Reader path configuration | Explicit/env/managed priority, empty/invalid settings, no implicit writes/network, expansion, pickle, and spawn passed |
| Downloader and installation | Local HTTP and forced ZIP64 fixtures passed for resume, retries, response sizes/ranges, hashes, concurrent locking, inventories, byte preservation, space limits, unsafe paths, CRC errors, and both prepared-state crash boundaries |
| CLI | Existing-root path, missing-data error, download argument selection, and an eval-only managed installation passed |
| Release validator | Stable/RC routing, manual no-publish behavior, exact tag/version matching, licenses, dependencies, typing markers, excluded assets, and artifact hashes passed |
| Ruff lint/format and ty | Ruff passed for all Python files, including tests; ty passed for source, examples, and scripts; 40 formatted files |
| `uv lock --check` | Passed |
| `uv build --no-sources --clear` | Wheel and sdist built with Apache-2.0 license and `py.typed`; no corpus or generated site assets |
| `twine check --strict` | Both artifacts passed, including README rendering |
| Isolated base wheel, download-extra wheel, and sdist consumers | Passed outside the checkout on Python 3.13; each checked waveform/clock agreement, CLI, padding, and spawn with two workers |
| Strict Zensical and generated link checks | Passed; 12 pages and 1,407 local page/fragment/asset references |
| GitHub workflow syntax, actionlint 1.7.12 | Passed |

Current dependencies were Torch 2.14.1, NumPy 2.5.3, SoundFile 0.14.0,
platformdirs 4.12.3, and filelock 4.0.12. Minimum direct versions were Torch
2.4.0, NumPy 1.26.0, SoundFile 0.12.0, platformdirs 4.3.8, and filelock 3.20.0.
Uv 0.11.20 is pinned in the workflows. The minimum-dependency run and real-data
spawn run required execution outside the sandbox because its shared-memory
restriction rejected Torch/OpenMP; the same checks passed there.

No official LOCATA archive was downloaded for these checks. All download traffic
went to a temporary local HTTP server with synthetic bytes. Existing corpus
files stayed read-only. Real final-release VAD/audio/annotation payloads are
unverified; passing synthetic transport/VAD tests does not validate them.

The public target repository `taishi-n/torchlocata` and local `origin` were created.
`pypi` and `testpypi` environments require `taishi-n` approval and version tags;
`github-pages` is tag-restricted. The owner confirmed PyPI/TestPyPI pending
publisher registration; the OIDC upload will verify that configuration. Push,
remote CI, TestPyPI rehearsal, PyPI publication, and Pages deployment are pending.

## Remaining verification scope

Final-release payloads, execution against MATLAB, Linux/Windows execution, and
full-suite Python 3.11/3.13/3.14 runs remain unverified locally. The CI matrix
covers Python 3.10–3.14 and Linux/macOS/Windows, but remote results must be
recorded separately after execution. Archive-directory inspection in the
[release plan](release-plan.md) does not replace payload validation.

Interpolation, resampling, dense ground truth, and official evaluation remain
outside scope. The initial reader/documentation commit is `c44f923`. Public
package installation has not been verified because publication is still pending.
