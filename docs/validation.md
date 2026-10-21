# Validation record

## Unreleased MATLAB-based analysis update: 2026-10-21

These checks apply to the current source changes, not a new PyPI release.
The [analysis guide](analysis.md) records the exact MATLAB commits, formulas,
intentional corrections, and the `locata-torch-v1` metric profile.
[NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) is
included in both distribution formats. All corpus operations were read-only;
no LOCATA archive was downloaded for this update.

| Check | Observed result |
| --- | --- |
| Mandatory synthetic suite | 184 passed; 18 integration cases deselected. The plot extra was installed, so rendering tests executed. One intentional duplicate-ZIP-name fixture warning remained. |
| Existing challenge-era snapshot | 16 integration cases passed; 2 new representative selections were absent and skipped. The original 12 reader integration cases passed, including spawn workers and the 4 ms regression. |
| Existing managed final-release eval | 10 integration cases passed; 8 dev-only cases skipped because this root contains eval only. All 6 new task/array analysis cases executed. |
| Numeric references | Independent NumPy STFT framing and MUSIC block-peak comparisons, analytic angular/tracking cases, and exhaustive small rectangular assignment checks passed. |
| Quality and distribution | Ruff lint/format, ty, wheel/sdist build, strict metadata checks, and NOTICE/optional-dependency checks passed. |
| Documentation | Strict Zensical build and local page/fragment/asset checks passed. |
| Installed consumer | A wheel installed into an independent environment passed reading, analysis, JSON/CSV/NPZ round-trip, official-style export, CLI, and two spawn workers without requiring Matplotlib. |
| End-to-end example | Full final-eval task 1, recording 1, benchmark2 completed coarse-grid MUSIC, evaluation, bundle/submission export, and PNG generation. This is an execution check, not a baseline accuracy benchmark. |

Local tools: Python 3.12.8, Torch 2.14.1, NumPy 2.5.3, SoundFile 0.14.0,
Matplotlib 3.11.2, Ruff 0.16.10, ty 0.0.85, and Zensical 0.0.68 on macOS arm64.
The configured multi-platform CI matrix was updated to install the plot extra;
that remote matrix has not been run for this update.

The new real-data cases use recording 1 of each eval task: benchmark2, dicit,
dummy, eigenmike, eigenmike, and benchmark2 for tasks 1–6, respectively. They
analyze a middle one-second window, including multiple sources and moving arrays.
Final-release cases exercise actual source poses and array VAD, oracle-track
consistency, MUSIC, and portable storage. Legacy cases exercise the absence of
eval source labels without inventing silence. File size/mtime checks around the
tested operations matched. No recordings were copied into the repository.

Real data exposed repeated quantized timestamps with different poses and valid
required rows outside audio/VAD coverage. Tests now cover ordered timestamp
multiplicity and explicit audio-bound selection; the default retains unknown
labels. These corrections were verified after the initial failing cases.

MATLAB/Octave was not executed. No numerical execution equivalence or historical
leaderboard reproduction is claimed. Final-release integration is representative,
not an exhaustive payload check of every recording. The historical limits below
describe the earlier release and are superseded only for the cases above.

## Published 0.1.0 validation

The following record describes the published [0.1.0 release](https://pypi.org/project/locata-torch/0.1.0/),
verified on 2026-10-07. Signed tag `v0.1.0` identifies commit `23cf99c`.
Synthetic tests, existing-data integration, and public installation checks are
reported separately. Dataset paths in commands are placeholders.

## Automated release checks

The [stable CI run](https://github.com/taishi-n/torchlocata/actions/runs/37613092362)
and [release workflow](https://github.com/taishi-n/torchlocata/actions/runs/37613092841)
passed the configured checks before publication.

| Check | Result |
| --- | --- |
| Mandatory synthetic suite | 147 passed in each configured test job; 12 integration tests deselected |
| Python/platform matrix | Linux Python 3.10–3.14, macOS Python 3.12, Windows Python 3.12 passed |
| Minimum direct dependencies | Linux Python 3.10 passed with Torch 2.4.0, NumPy 1.26.0, SoundFile 0.12.0, platformdirs 4.3.8, and filelock 3.20.0 |
| Quality checks | Ruff lint and formatting, ty, and lockfile validation passed |
| Distributions | Wheel and sdist built; metadata, license, typing marker, entry point, and asset checks passed |
| README rendering | `twine check --strict` passed for both distributions |
| Installed consumers | Fresh base-wheel, download-extra-wheel, and sdist consumers passed outside the checkout, including two spawn workers |
| Documentation | Strict Zensical build and local page, fragment, and asset checks passed |

Local release checks used macOS arm64 and Python 3.12.8 with Torch 2.14.1,
NumPy 2.5.3, SoundFile 0.14.0, platformdirs 4.12.3, and filelock 4.0.12.
Documentation tools were Zensical 0.0.68, mkdocstrings-python 2.0.9, and
mkdocstrings 1.0.6. These versions describe the tested environments rather than
all possible dependency combinations.

### Synthetic coverage

Mandatory tests create small WAV and tab-separated TXT files in temporary
directories. They cover deterministic numeric indexing, multiple arrays and
source IDs, optional absence, malformed files, waveform values and dtypes,
independent clocks, fractional seconds, date rollover, duplicate annotation
times, validity flags, nontrivial rotations, and angle boundaries.

Window and loader tests cover hops, tails, short recordings, annotation
boundaries, partial reads, bounded sparse TXT caches, padding, masks, Subset,
samplers, shuffle, pickle, and explicit spawn with two workers. README and
tutorial examples execute with only the placeholder root replaced by a fixture.

Downloader tests use local HTTP servers and synthetic ZIP64 archives. They cover
resume, ignored and invalid ranges, response sizes, retries, hashes, process
locking, space limits, unsafe original ZIP names, CRC errors, staged installation,
inventories, and prepared-state crash recovery. These tests do not access official
LOCATA archives or validate their audio/VAD payloads.

## Existing-data integration

All 12 read-only integration tests passed against an existing challenge-era
LOCATA snapshot, including with the pip-installed 0.1.0 package. The command,
using a placeholder root, is:

```sh
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration -v
```

Header indexing found 72 dev and 154 eval array WAVs. Checked headers had 15 dicit,
4 dummy, 32 eigenmike, and 12 benchmark2 channels at 48 kHz. These counts describe
this snapshot; they are not assumptions embedded in the library. Representative
payloads were tested rather than every recording.

| Recording | Checked configuration |
| --- | --- |
| `dev/task1/recording1/benchmark2` | Static source `loudspeaker1` |
| `dev/task2/recording1/dicit` | Multiple sources `loudspeaker3`, `loudspeaker4` |
| `dev/task3/recording2/dummy` | Moving source `hendrik`, duplicate pose times |
| `dev/task5/recording1/eigenmike` | Moving array, source `christine` |
| `dev/task6/recording3/benchmark2` | Moving array, sources `christine`, `hendrik` |
| `eval/task1/recording1/eigenmike` | No source ground truth, source audio, or VAD |
| `eval/task4/recording3/dummy` | No source files |
| `eval/task6/recording3/benchmark2` | Moving array, no source files |

Partial waveforms matched independent SoundFile reads. Checks covered microphone
geometry, clocks, and available source poses and audio. The static reference
recording was also read in full: 155072 frames and 389 pose rows. Audio starts at
`15:40:25.068`; pose and required times start at `15:40:25.064`. Their relative
starts are `0` and `-0.004` seconds, preserving the measured offset without a
fixed correction. Full-waveform slices exactly matched window reads.

The WAV-less `eval/task4/recording4/dicit` and `eval/task6/recording5/dicit`
directories were excluded and reported through warnings and `missing_audio`.
Input sizes and modification times matched before and after the representative
reads. No corpus file was copied into the repository or modified.

The real-data example returned `[4, 32, 48000]` batches at 48 kHz with both zero
workers and two explicit spawn workers.

## Published distributions and independent consumers

PyPI reported Apache-2.0, Python `>=3.10`, and the canonical documentation URL.
Public wheel and sdist SHA-256 values matched the original validated release
inventory and the downloaded distribution bytes:

| Artifact | SHA-256 |
| --- | --- |
| `locata_torch-0.1.0-py3-none-any.whl` | `611a166915b28ffab0a4dec93a2ae73c5ebb2dfc0ad2463b28ca3f382eaf2fb5` |
| `locata_torch-0.1.0.tar.gz` | `9a5440b772f0306ea7d9daa9daeeedbadea1f7023b9674655155340e0b3a9af9` |

| Consumer check | Result |
| --- | --- |
| Fresh Python 3.12.8 environment | `python -m pip install "locata-torch==0.1.0"` installed the public package and dependencies |
| Import location | Resolved to the independent environment's `site-packages` |
| Installed smoke check | Waveforms, clocks, padding, CLI, and two spawn workers passed |
| Existing snapshot with the pip-installed package | All 12 integration tests passed |
| Documented real-data example | Zero-worker and two-worker batches matched the expected shape and sample rate |
| Separate uv project, Python 3.13.1 | `uv add "locata-torch[download]"` installed 0.1.0; installed smoke and spawn checks passed |

The [0.1.0rc1 TestPyPI rehearsal](https://github.com/taishi-n/torchlocata/actions/runs/37611388927)
also passed the matrix and independent installation checks before the stable
release. Both index uploads used GitHub OIDC.

The hosted overview, tutorial, and API reference returned HTTP 200 at
`https://taishi.org/torchlocata/`. The
[post-release CI](https://github.com/taishi-n/torchlocata/actions/runs/37614741244)
and [documentation deployment](https://github.com/taishi-n/torchlocata/actions/runs/37614811737)
passed. Hosted documentation can be updated independently of the tagged package
artifacts through the [release process](release-plan.md#deploy-documentation-changes).

## Limits of the original release verification

- No complete official LOCATA archive was downloaded during verification.
  Final-release audio, annotation, and VAD payloads remain unverified. Bounded
  ZIP64 directory inspection established paths, filenames, and expanded sizes;
  it did not validate member contents.
- The existing snapshot has no VAD files and no eval source files. Synthetic
  fixtures cover VAD and eval ground truth; they do not replace integration with
  those final-release files.
- Geometry formulas were checked against the official source and synthetic axis
  and rotation tests. No execution comparison against MATLAB has been performed.

See [references](references.md) for the inspected corpus versions and source
fingerprints, and [paths and storage](storage.md#release-and-disk-space) for the
pinned archive metadata. The raw reader still performs no implicit interpolation,
resampling, dense-label generation, or evaluation. The explicit analysis APIs
added later are described above and in the [analysis guide](analysis.md).
