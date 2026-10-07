# Release process

This guide is for maintainers publishing new versions of `locata-torch`.
For package installation and dataset preparation, see [getting started](getting-started.md)
and [paths and storage](storage.md). Published versions are listed in the
[release notes](releases.md).

## Publication workflow

`.github/workflows/release.yml` calls the full CI workflow, then publishes the
validated wheel and sdist through GitHub OIDC. Package metadata and the tag must
match exactly.

| Trigger | Destination | Documentation deployment |
| --- | --- | --- |
| Stable tag `vX.Y.Z` | PyPI, environment `pypi` | After successful package publication |
| Release-candidate tag `vX.Y.ZrcN` | TestPyPI, environment `testpypi` | None |
| Manual `release.yml` run | Validation only | None |

Versions must use canonical `X.Y.Z` or `X.Y.ZrcN` spelling. Other prerelease
forms are rejected. Pushing a matching version tag starts the publication
workflow; the protected package environment requires maintainer approval.

Validation covers Python 3.10–3.14, Linux/macOS/Windows, minimum direct
dependencies, lint, formatting, types, package contents, README rendering,
isolated installed consumers, and strict documentation builds. Mandatory tests
use synthetic WAV/TXT files, local HTTP servers, and small ZIP64 archives.
CI never downloads LOCATA archives.

The publisher consumes the artifact set produced by validation, verifies its
`SHA256SUMS`, and uploads without rebuilding or checking out source code.
`scripts/check_release.py` checks tag/version agreement, dependencies, license
metadata, `py.typed`, the CLI entry point, and exclusion of corpus and generated
assets. It writes the SHA-256 inventory for the newly built distributions.

## Trusted Publishing and environments

PyPI and TestPyPI have separate publisher registrations for this repository:

| Field | Value |
| --- | --- |
| Project | `locata-torch` |
| GitHub owner | `taishi-n` |
| Repository | `torchlocata` |
| Workflow | `release.yml` |
| PyPI environment | `pypi` |
| TestPyPI environment | `testpypi` |

The `pypi` and `testpypi` GitHub environments require review by `taishi-n` and
allow `v*` tags. The package publishing job receives `id-token: write`; no
long-lived upload token is stored in the repository. Keep publisher registrations aligned with
workflow and environment names when changing release infrastructure. See
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
for the account-side configuration.

GitHub Pages uses **GitHub Actions** as its source. The `github-pages` environment
allows `v*` tags and `main` documentation deployments. The canonical
site is `https://taishi.org/torchlocata/`; retain this URL in package metadata and
README links.

## Prepare a release candidate

1. Finish the intended changes and update the documented contracts and release
   notes. Run the [development checks](development.md#install-and-run-checks).
   Record synthetic and optional real-data results separately.
2. Set `[project].version` in `pyproject.toml` to the candidate version and run
   `uv lock`. Build and validate the matching artifacts. For example, after
   setting version `0.2.0rc1`:

   ```sh
   uv build --no-sources --clear
   uv run twine check --strict dist/*.whl dist/*.tar.gz
   uv run python scripts/check_release.py --tag v0.2.0rc1
   ```

3. Commit the reviewed candidate, push the branch, and require all CI jobs to
   pass. Create and push the matching signed tag, such as `v0.2.0rc1`.
4. Review the release workflow's validation results and artifact inventory, then
   approve the `testpypi` environment. Confirm the exact candidate appears on
   TestPyPI.
5. Install the candidate in a fresh environment outside the checkout. Resolve
   dependencies from PyPI first, then install the exact TestPyPI distribution
   without dependency resolution:

   ```sh
   python -m pip install torch numpy soundfile platformdirs filelock
   python -m pip install --index-url https://test.pypi.org/simple/ --no-deps "locata-torch[download]==0.2.0rc1"
   locata-torch --help
   ```

   These commands illustrate the candidate version above; use the version being
   released. Check that imports resolve to the independent environment's
   `site-packages`. Exercise recording reads, window slices, padding, CLI path
   lookup, and two spawn workers. Use synthetic data or an existing
   `LOCATA_ROOT=/path/to/LOCATA`; no corpus download is required for this check.

## Publish a stable version

1. Set the matching stable version, update the lockfile and release notes, and
   rerun the required checks. Commit and push the reviewed changes, require CI
   to pass, then create and push the matching signed `vX.Y.Z` tag.
2. Review the separately validated stable artifacts and approve the `pypi`
   environment. The workflow publishes those artifacts and deploys its validated
   documentation after publication succeeds.
3. Check the exact PyPI version, metadata, wheel and sdist hashes against the
   original validated artifact inventory. Preserve that inventory: invoking
   `scripts/check_release.py` writes a new one and is not a substitute for
   comparing the original release hashes.
4. Verify installation in an independent pip environment and uv project. Run
   the [getting-started example](getting-started.md) and spawn-worker checks
   against synthetic or existing data. Record what actually ran in
   [validation](validation.md), including any unverified dataset payloads.

Use the official [uv packaging guide](https://docs.astral.sh/uv/guides/package/)
and [Python packaging metadata guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
when changing build configuration. Package versions and the pinned LOCATA data
release are independent; upgrading the library does not replace the corpus.

## Deploy documentation changes

For changes to the documentation after a package release, validate locally:

```sh
uv run --group docs zensical build --clean --strict
uv run python scripts/check_docs_links.py site
```

After the changes are committed and pushed to `main`, deploy through the manual
workflow:

```sh
gh workflow run docs.yml --ref main --repo taishi-n/torchlocata
```

This workflow builds and validates the site, then deploys to Pages. It does not
publish Python packages. The README embedded in an existing PyPI distribution
belongs to that release; source documentation changes appear in newly built
releases, while the hosted site can be updated independently.
