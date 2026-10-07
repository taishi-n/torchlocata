# First PyPI release plan

## Target and current status

The first public release will include the reader, dataset path configuration,
and a completed, explicitly invoked LOCATA downloader. The code license will be
Apache-2.0. Keep the distribution name `locata-torch`, import name `locata_torch`,
and CLI name `locata-torch`.

Reviewed on 2026-10-07. The reader, root lookup, explicit downloader, CLI,
Apache-2.0 license, package metadata, and validation/publication workflows are
implemented. The `0.1.0rc1` TestPyPI rehearsal passed, including public artifact
hashes and an independent installed consumer. Package metadata is set to `0.1.0`
for the stable release. The target repository is `taishi-n/torchlocata`, and the
PyPI owner is `taishi-n`. The owner confirmed both pending publishers; TestPyPI
OIDC has succeeded. The [validation record](validation.md) separates executed
checks from the stable publication and consumer checks that follow tagging.
[Release notes](releases.md) describe the release.
The [getting-started guide](getting-started.md) gives the pip/uv installation and
usage instructions intended for the completed release.

## Ideas from existing tools

These comparisons inform the proposed design; no external reader or downloader
code has been copied. Rolling documentation was checked on 2026-10-07.

| Reference | Observed pattern | Proposed use in locata-torch |
| --- | --- | --- |
| [Torchvision CIFAR10, 0.29](https://docs.pytorch.org/vision/stable/generated/torchvision.datasets.CIFAR10.html) | Explicit `root`, opt-in `download=False`, and reuse of downloaded data | Keep familiar explicit paths and reuse; expose downloading as a separate operation before creating workers |
| [TensorFlow Datasets, API page updated 2024-04-26](https://www.tensorflow.org/datasets/api_docs/python/tfds/load) | `data_dir`, `TFDS_DATA_DIR`, versioned datasets, and separate preparation and reading steps | Provide an environment setting, a stable dataset release identity, and a preparation step; keep Dataset construction read-only |
| [Hugging Face Hub, current cache guide](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache) | Shared local storage with revision-specific snapshots | Reuse one downloaded release across projects and virtual environments; a simple release directory is sufficient for two archives |
| [Pooch, 1.9.0](https://www.fatiando.org/pooch/latest/api/generated/pooch.create.html) | File registries with known hashes, environment-controlled storage, and retries | Pin official URLs, sizes, and checksums; use a dataset release ID rather than the Python package version as the storage key |

The upstream code licenses checked were
[Torchvision: BSD-3-Clause](https://raw.githubusercontent.com/pytorch/vision/main/LICENSE),
[TensorFlow Datasets: Apache-2.0](https://raw.githubusercontent.com/tensorflow/datasets/master/LICENSE),
[Hugging Face Hub: Apache-2.0](https://raw.githubusercontent.com/huggingface/huggingface_hub/main/LICENSE),
and [Pooch: BSD-3-Clause](https://raw.githubusercontent.com/fatiando/pooch/v1.9.0/LICENSE.txt).
Pooch's license is version-pinned; the others are upstream branch snapshots
checked on the review date, not licenses assigned to this library.

Pooch is a useful alternative for ordinary whole-file downloads. Its documented
[HTTP downloader](https://www.fatiando.org/pooch/latest/api/generated/pooch.HTTPDownloader.html)
does not promise persistent partial-file resume. The proposed first implementation
uses focused standard-library HTTP, hashing, and ZIP code to control resume and
installation, rather than assuming Pooch supplies those guarantees. No generic
download backend or corpus plugin interface is needed.

Add [platformdirs](https://platformdirs.readthedocs.io/en/latest/api.html#platformdirs.user_data_path)
as a small runtime dependency for platform-standard persistent storage. Keep
cross-process locking with [filelock](https://py-filelock.readthedocs.io/en/latest/)
in the optional `download` extra. HTTP, hashing, ZIP64 extraction, and the CLI can
use `urllib.request`, `hashlib`, `zipfile`, and `argparse`. Current upstream
[platformdirs](https://raw.githubusercontent.com/tox-dev/platformdirs/main/LICENSE)
and [filelock](https://raw.githubusercontent.com/tox-dev/filelock/main/LICENSE)
license files state MIT. The minimum platformdirs 4.3.8 and resolved 4.12.3 are
MIT. Filelock 3.20.0, the minimum, is Unlicense; resolved 4.0.12 is MIT. Reader
use requires no download extra; filelock is imported by the downloader only.

## Dataset path contract

Lookup for `LocataDataset(root=None, ...)`:

1. An explicit `root`, including `str` or `Path`.
2. `LOCATA_ROOT`, pointing directly to an unpacked root containing `dev/` or
   `eval/`.
3. The managed final-release root beneath the configured storage directory.

An explicitly supplied or environment-supplied invalid path must raise a useful
error; it must not silently fall back. An empty environment value is invalid.
Expand `~`, resolve the selected path once in the constructor, and retain the
absolute path for pickling and spawned workers. Do not search the working
directory or guess a user's existing corpus location.

Managed storage has a separate meaning and lookup:

1. `data_dir` passed to `download_locata`, or CLI `--data-dir`.
2. `LOCATA_DATA_DIR`.
3. `platformdirs.user_data_path("locata-torch", appauthor=False,
   ensure_exists=False)`.

`LOCATA_ROOT` never redirects a download into an existing corpus. The downloader
returns its actual installed root, which can be passed explicitly to the reader.
An existing challenge-era root remains usable without a managed manifest.
When using the default managed root, requested splits must have completed
installation records. Missing managed data produces an error with the download
command, without creating directories or performing network I/O. User-provided
roots retain the reader's existing WAV-based selection behavior.

For an existing shared dataset:

```sh
export LOCATA_ROOT=/path/to/LOCATA
```

```python
from locata_torch import LocataDataset

dataset = LocataDataset(split="dev", arrays=("eigenmike",))
```

For another Python tool after publication:

```sh
uv add "locata-torch[download]"
export LOCATA_DATA_DIR=/path/to/locata-store
uv run locata-torch download --split dev
uv run locata-torch path
```

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
```

Reader-only consumers install `locata-torch` without an extra.
`download_locata(split="dev", *, data_dir=None) -> Path` accepts `"dev"`, `"eval"`,
or a nonempty sequence of those names; it returns the common root after all
requested splits succeed. CLI `--split` may be repeated. `locata-torch path`
prints the resolved reader root to stdout and reports errors to stderr. Calling
the downloader without its extra gives an installation instruction. There is no
implicit download option on the Dataset constructor.

## Distribution and storage

Download only the pinned [official final release](https://zenodo.org/records/3630471),
v1 dated 2020-01-31, DOI `10.5281/zenodo.3630471`. Its
[metadata API](https://zenodo.org/api/records/3630471) supplies these byte sizes,
MD5 checksums, and HTTPS file URLs:

| Split | Archive bytes | Official MD5 |
| --- | ---: | --- |
| dev | 6,207,354,195 | `d5a5417c3f6b2ed0e43581dd06f504e6` |
| eval | 13,045,105,034 | `46709713350bc16c106e788920d30a8b` |

Bounded HTTP range reads of the official ZIP64 end records and central directories
confirmed the `dev/` and `eval/` top-level paths. Their declared uncompressed
sizes were 27,136,519,350 and 57,426,914,435 bytes. Keeping both ZIPs and extracted
splits needs about 103.8 GB before filesystem overhead; recommend at least 120 GB
free for a fresh installation. These are directory-metadata observations, not
validation of audio or annotation contents. Full archives were not downloaded.

The observed file lists include VAD in both splits, unlike the local challenge
snapshot. This release uses the existing snapshot for reader integration and
local HTTP/synthetic ZIP fixtures for downloader validation. No real dataset
download is performed during verification. Final-release audio/VAD payload
validation remains a documented limitation rather than a publication gate.
Downloading transfers an entire split; reader task/array filters do not reduce
network transfer.

Storage, entirely outside a user-provided corpus:

```text
<data_dir>/
├── archives/zenodo-3630471/     # Verified dev.zip/eval.zip and resumable .part files
├── datasets/zenodo-3630471/    # Returned LOCATA root, containing complete splits
├── state/zenodo-3630471/       # Per-split installation and attribution manifests
├── staging/                   # Incomplete extraction, outside the readable root
└── locks/                     # Per-split process locks
```

The release key is independent of the library version, so upgrading the library
does not duplicate the corpus. Downloaded archives are retained for offline
re-extraction. The initial API does not delete data or provide automatic repair.
Manifests record the DOI, exact URLs, expected and observed checksums, sizes,
installation state, inventory, and dataset citation/license information. The
reader writes no indexes, caches, locks, or manifests beneath a dataset root.

The dataset metadata identifies [ODC-BY 1.0](https://opendatacommons.org/licenses/by/1-0/).
Keep dataset attribution and license notices in the download record and
documentation, separate from Apache-2.0 for this code. Fetch official archives
directly; do not bundle dataset assets in wheels or maintain a redistributed
mirror.

## Download and extraction requirements

1. Validate the split and destination before network activity. Check available
   space using pinned size information, then the verified ZIP directory before
   extraction. Acquire one lock per split and install multiple splits in a fixed
   order. Use finite timeouts, bounded retries, and progress reporting to stderr.
2. Stream to a persistent `.part` file with bounded memory, recording its release,
   URL, and expected hash. Request identity encoding so offsets refer to archive
   bytes. Resume with HTTP
   `Range` only after checking `206`, the exact `Content-Range`, and total size.
   A server returning `200` must cause a safe restart of the owned partial file,
   never append a whole response. Validate truncated/oversized responses and
   handle `416`, rate limits, and interrupted transfers explicitly. Range support
   was observed, but must be checked on every response; it is not guaranteed.
3. Rehash retained bytes when resuming. Verify the final file's exact size and
   official MD5 before renaming it to a verified archive. MD5 is the publisher's
   integrity check; HTTPS and the pinned source remain necessary. A mismatch must
   fail before extraction and leave the installed dataset untouched.
4. Use [Python's ZIP64-capable zipfile](https://docs.python.org/3.10/library/zipfile.html)
   with streamed member reads and CRC validation. Before writing, reject absolute
   paths, traversal, symlinks, unexpected top-level paths, and duplicate or
   case-colliding destinations. Preserve file contents; do not repair clocks,
   preprocess WAVs, or remove optional files.
5. Extract into a new owned staging directory on the destination filesystem.
   Publish a complete split with an atomic rename, then commit its manifest
   atomically. Record the prepared state first so a crash between these operations
   can be recovered by verifying the inventory without overwriting data. Failed
   extraction remains invisible to the default reader; retries can reuse the
   verified archive.
6. Repeated requests reuse completed managed installations after inventory checks.
   Unknown existing directories, altered installations, or incompatible manifests
   produce an error. Never merge into or overwrite an existing dataset, and do not
   silently redownload, replace, or delete user files. Successful splits remain
   usable if a later requested split fails.

## Implementation sequence and acceptance criteria

Each implementation step follows specification, failing tests, minimal code,
and checks. Update the README and API reference as proposed features become real.

| Step | Deliverable | Acceptance criteria |
| --- | --- | --- |
| 1. Paths and licensing | Apache-2.0 `LICENSE` and SPDX metadata; optional `root`; storage resolution; `path` CLI | Tests cover explicit/env/default priority, invalid and empty settings, `~`, no implicit I/O, and consistent paths under spawn. The base install works without download dependencies |
| 2. Downloading | Pinned archive registry; public download function and CLI; streaming, resume, hashes, locks | Synthetic HTTP-server tests cover interrupted transfers, correct and ignored ranges, bad range/size/hash, HTTP failures, retries, reuse, and concurrent calls. Tests make no external requests |
| 3. Installation | ZIP64 extraction, space checks, staging, manifests, and crash recovery | Tiny forced-ZIP64 fixtures cover corrupt members, unsafe paths, collisions, insufficient space, interrupted extraction, existing directories, and byte-for-byte preservation. No partial split becomes readable |
| 4. Existing-data integration | Read-only verification of the available dev/eval snapshot | Read representative static, multiple-source, moving-source, and moving-array recordings; verify partial reads, clocks, collation, missing files, and spawn. Use local fixtures for transport/ZIP/VAD tests; do not download official archives. Clearly record unverified final-release payloads |
| 5. Distribution and automation | Complete package metadata and URLs; tested wheel/sdist; validation and publication workflows | Install built artifacts outside the checkout in fresh base and download-extra environments; test the CLI, import, sample reading, and spawn. Run supported-Python checks, lint, format, ty, build, strict Zensical, and link checks; inspect artifacts and README rendering |
| 6. Release | TestPyPI rehearsal, then first PyPI publication | Check version/tag agreement and the recorded validation boundaries. Publish only the artifact set that passed validation; confirm an independent consumer can install and use the published package |

Keep routine CI offline with small WAV/TXT/HTTP/ZIP fixtures. Extend the current
Python 3.10/3.12 checks with supported-version and minimum-dependency coverage;
test platform-specific paths, locking, and spawn on Linux, macOS, and Windows.
The configured matrix covers Python 3.10–3.14, macOS/Windows spawn and locking,
and Python 3.10 with minimum direct dependencies. CPU PyTorch builds avoid CUDA
dependencies on Linux test runners. Locked quality/build checks run on macOS.
No official archives are downloaded in this release's verification or CI.
Synthetic VAD tests do not count as real final-release VAD validation.

## PyPI release operation

Package metadata identifies `taishi-n` and the repository, issue tracker, and
planned hosted documentation URL; keep dataset citation distinct from authorship. Retain
`py.typed`, declare the download extra and CLI entry point, and include `LICENSE`
in wheel and sdist. Recheck name availability immediately before setup: PyPI's
JSON endpoint returned `404` for `locata-torch` on 2026-10-07, which does not reserve
the name.

Follow the official [uv packaging guide](https://docs.astral.sh/uv/guides/package/)
and [Python packaging metadata guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
Use `uv build --no-sources`, inspect both artifacts, and verify installation
without checkout-local imports. For a TestPyPI rehearsal, install dependencies
from their normal index and the exact test artifact with `--no-deps`, avoiding a
mixed-index dependency search.

Use prerelease versions for TestPyPI rehearsals and a stable `v0.1.0` tag for
the first PyPI release. Route prerelease and stable tags explicitly; do not let
every `v*` tag publish to PyPI. Use a tag-triggered validation job and a separate
publish job that consumes its already tested artifacts. Configure
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
with GitHub OIDC, `id-token: write` only in the publish job, and a protected `pypi`
environment. A manual validation run should not publish. For the first project,
a [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
requires the actual repository owner/name, workflow filename, and environment.
TestPyPI needs its own configuration. Avoid storing a long-lived upload token.

### Account configuration

The public repository `taishi-n/torchlocata` and local `origin` now exist. Package
environments `pypi`/`testpypi` are restricted to `v*` tags and require review by
`taishi-n`; `github-pages` allows `v*` tags and `main` for explicit documentation
updates. GitHub Pages is enabled with source
**GitHub Actions** and HTTPS. The site inherits the account's existing custom
domain, making its canonical target `https://taishi.org/torchlocata/`; it is not
yet deployed. No account-wide domain setting was changed.

Register a pending publisher independently on
[PyPI](https://pypi.org/manage/account/publishing/) and
[TestPyPI](https://test.pypi.org/manage/account/publishing/):

| Field | Value |
| --- | --- |
| Project name | `locata-torch` |
| Owner | `taishi-n` |
| Repository | `torchlocata` |
| Workflow filename | `release.yml` |
| Environment | `pypi` on PyPI; `testpypi` on TestPyPI |

PyPI ownership is under `taishi-n`. TestPyPI is a separate service and requires
its own account and publisher configuration; a PyPI account does not create it.
No upload token is stored in this repository. See the official
[new-project publisher instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

### Release steps

1. Finish local validation and record results. Commit reviewed changes and push
   `main`; require all remote CI jobs to pass.
2. Set the package version to `0.1.0rc1`, update the lockfile/release notes, and
   tag the matching commit `v0.1.0rc1`. The release workflow reruns the full CI,
   builds one artifact set, inspects metadata/contents/hashes, and exercises
   fresh base, download-extra, and sdist installations. Only those validated
   artifacts reach TestPyPI after environment approval.
3. Rehearse a consumer outside this checkout. Install normal dependencies from
   PyPI, then install the exact TestPyPI version without dependency resolution:

   ```sh
   python -m pip install torch numpy soundfile platformdirs filelock
   python -m pip install --index-url https://test.pypi.org/simple/ --no-deps "locata-torch[download]==0.1.0rc1"
   locata-torch --help
   ```

   Point it at existing data using `LOCATA_ROOT=/path/to/LOCATA` and run the
   recording/window/spawn examples. Do not fetch the corpus during rehearsal.
4. Set the stable version to `0.1.0`, update release records, and create the
   matching `v0.1.0` tag. The separately validated stable artifact set goes to
   PyPI after environment approval; the same built documentation is deployed to
   Pages after publication succeeds. Do not rebuild distributions in publish jobs.
5. Verify PyPI's exact version and wheel hash, install it in an independent
   environment, and run the documented existing-data workflow. Mark publication
   complete only after these checks. Commit the completed validation record and
   use the manual `docs.yml` workflow to deploy the updated documentation from
   `main`; this does not rebuild or republish package artifacts.

`scripts/check_release.py` rejects version/tag mismatches, unsupported prerelease
types, corpus/generated assets, missing licenses or typing metadata, and incorrect
dependencies. It records SHA-256 for the wheel/sdist; the publish job checks those
hashes again. A manual workflow run validates without publishing. Account setup,
remote execution, and public installation must be recorded as pending until
actually verified.
