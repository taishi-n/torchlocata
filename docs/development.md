# Development

## Repository structure

| Path | Purpose |
| --- | --- |
| `src/locata_torch/` | Dataset views, collation, geometry, typed schemas, and private TXT parsing |
| `tests/` | Synthetic fixtures and explicitly enabled real-data integration tests |
| `examples/read_locata.py` | Command-line example with spawn workers and a main guard |
| `docs/` | English documentation sources |
| `zensical.toml` | Documentation navigation, theme, and API-generation settings |
| `scripts/check_docs_links.py` | Local-page, anchor, and asset validation for generated HTML |
| `site/` | Generated documentation; ignored by version control |

`README.md` introduces the API and links to the detailed contracts. The existing
`AGENTS.md` contributor guide remains at the repository root.

## Install and run checks

```sh
uv sync --python 3.12 --extra download --group docs --group release
uv run pytest -m "not integration"
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build --no-sources --clear
uv run twine check --strict dist/*.whl dist/*.tar.gz
uv run python scripts/check_release.py
```

Ruff applies an 88-column Python style with four-space indentation. Use
`snake_case` for functions and modules, `PascalCase` for classes, and public type
annotations. `uv run ruff format .` applies formatting. Keep runtime dependencies
focused on PyTorch, NumPy, SoundFile, and platformdirs. Filelock belongs to the
download extra; documentation and release tools are dependency groups.

Update the documented contract first, write behavioral tests and confirm the
expected failure, then implement the smallest change and reconcile code and
documentation. Do not add compatibility aliases, migration code, or a general
plugin framework.

## Test boundaries

Pytest creates small WAV and tab-separated TXT fixtures in temporary directories.
Use `test_*.py` files and `test_*` functions. Test observable behavior, independent
clocks, missing-data distinctions, partial I/O, and loader behavior. No numeric
coverage threshold is configured.

Real-data tests require an explicit root and remain read-only:

```sh
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration -v
```

Without `LOCATA_ROOT`, integration tests skip. Do not report skipped checks as
executed, copy real audio into the repository, or write caches beneath the corpus.
See [validation](validation.md) for the tested snapshot and unverified platforms.

## Preview and build documentation

Documentation tools are an optional `docs` dependency group, separate from the
library's runtime dependencies and the `dev` group:

```sh
uv sync --group docs
uv run --group docs zensical serve
```

The preview is served at `http://localhost:8000`. To generate a static site:

```sh
uv run --group docs zensical build --clean --strict
uv run python scripts/check_docs_links.py site
```

The configuration sets `use_directory_urls=false`, so pages link to concrete
HTML files and can be opened from `site/index.html`. Offline mode enables local
search; the theme may fetch its iframe-worker polyfill from the CDN when browsing
local files. Navigation and page content do not require a preview server.

Write internal Markdown links to source files, such as `[Data model](data-model.md)`.
Avoid root-relative paths and generated HTML paths in source Markdown. Public API
content is generated from `src/locata_torch` using mkdocstrings. Build in strict
mode and run the link checker after documentation changes. The checker validates
local pages, fragments, and assets; it does not probe external websites.
The repository README uses absolute hosted documentation URLs so its links also
work when rendered on PyPI outside this checkout.

CI runs tests across Python 3.10–3.14 and Linux/macOS/Windows, plus minimum direct
dependencies on Python 3.10. It runs Ruff, ty, package/metadata/content checks,
isolated wheel/sdist consumers, strict documentation builds, and local link
validation. Mandatory download tests use only a local HTTP server and synthetic
ZIP64 archives. CI never fetches LOCATA data.

`.github/workflows/release.yml` calls the same validation workflow, then publishes
validated artifacts through OIDC. Matching stable tags route to PyPI and RC tags
to TestPyPI. Manual runs only validate; stable releases deploy documentation after
publication. The manual `docs.yml` workflow rebuilds and validates documentation
from `main`, then deploys it to Pages without publishing Python packages. Use it
to update post-publication verification records:

```sh
gh workflow run docs.yml --ref main --repo taishi-n/torchlocata
```

See [release operations](release-plan.md#pypi-release-operation) for publisher and
protected-environment configuration.

## Contributions

The initial commit uses a concise imperative subject. Continue focused messages
that describe the change. Pull requests should state
the resulting behavior, relevant documentation updates, executed checks, and
remaining limitations, with related issues linked when applicable. Commit, push,
and publication require a separate explicit request.
