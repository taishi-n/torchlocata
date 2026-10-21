# Development

## Repository structure

| Path | Purpose |
| --- | --- |
| [src/locata_torch/](https://github.com/taishi-n/torchlocata/tree/main/src/locata_torch) | Dataset views, collation, geometry, typed schemas, storage, downloader, and CLI |
| [tests/](https://github.com/taishi-n/torchlocata/tree/main/tests) | Synthetic fixtures and explicitly enabled real-data integration tests |
| [examples/read_locata.py](https://github.com/taishi-n/torchlocata/blob/main/examples/read_locata.py) | Command-line example with spawn workers and a main guard |
| [examples/analyze_locata.py](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py) | Explicit localization, evaluation, result export, and plotting example |
| [docs/](https://github.com/taishi-n/torchlocata/tree/main/docs) | English guides, with matching Japanese pages in `docs/ja/` |
| [zensical.toml](https://github.com/taishi-n/torchlocata/blob/main/zensical.toml) | Documentation navigation, theme, and API-generation settings |
| [zensical.ja.toml](https://github.com/taishi-n/torchlocata/blob/main/zensical.ja.toml) | Japanese navigation and site settings |
| [scripts/check_docs_links.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/check_docs_links.py) | Local-page, anchor, and asset validation for generated HTML |
| [scripts/check_release.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/check_release.py) | Distribution metadata, contents, version routing, and hashes |
| [scripts/smoke_installed.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/smoke_installed.py) | Installed-package reading, CLI, and spawn checks |
| `site/` | Generated documentation; ignored by version control |

[README.md](https://github.com/taishi-n/torchlocata/blob/main/README.md) introduces
the API and links to the detailed contracts. The
[AGENTS.md](https://github.com/taishi-n/torchlocata/blob/main/AGENTS.md) contributor
guide remains at the repository root.

## Install and run checks

Clone the repository first. Run the development commands from its root:

```sh
git clone https://github.com/taishi-n/torchlocata.git
cd torchlocata
uv sync --locked --python 3.12 --extra download --extra plot --group docs --group release
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
download extra; Matplotlib belongs to the plot extra. Documentation and release
tools are dependency groups. CI installs the plot extra so figure tests execute.

Update the documented contract first, write behavioral tests and confirm the
expected failure, then implement the smallest change and reconcile code and
documentation. Keep one public API for each supported operation.

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
See [validation](validation.md) for the tested snapshot, platform matrix, and
remaining verification limits. Run the repository example against your own data:

```sh
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 0
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2
```

## Preview and build documentation

English pages retain their existing URLs. Japanese pages live under `ja/`, with
the same filenames. Zensical's `theme.language` localizes each site's interface;
`extra.alternate` provides the header selector linking to each language's homepage.
Each language has its own navigation and search index, with the same API and examples.
API signatures and source docstrings are generated from the shared Python code.

Install the `docs` dependency group, then build and check both languages:

```sh
uv sync --group docs
uv run zensical build --clean --strict --config-file zensical.toml
uv run zensical build --clean --strict --config-file zensical.ja.toml
uv run python scripts/check_docs_links.py site --multilingual
```

Open `site/index.html` or `site/ja/index.html`, or serve the combined site:

```sh
uv run python -m http.server --directory site 8000
```

The preview is served at `http://localhost:8000`. Zensical sets one canonical
language per project, so the build uses `zensical.toml` for English and
`zensical.ja.toml` for Japanese. Build English first: its clean build recreates
`site/`, then the Japanese build adds `site/ja/`. The standard language selector
uses the published homepage URLs. For a local preview, open `/index.html` or
`/ja/index.html` on the preview server, or the matching files under `site/`.
When adding or changing a guide, update both languages and keep API names,
numeric values, examples, and validation limits consistent.

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
work when rendered on PyPI outside this checkout. Link repository files outside
`docs/` through their public GitHub `blob/main/` or `tree/main/` URLs. Use
`/path/to/LOCATA` and `/path/to/experiment` as configurable path placeholders;
never embed a contributor's machine paths or `file://` links in public prose.

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
to publish documentation changes independently of a package release:

```sh
gh workflow run docs.yml --ref main --repo taishi-n/torchlocata
```

See the [release process](release-plan.md) for publisher and
protected-environment configuration.

## Contributions

Recent history uses Conventional Commits, such as `feat: add ...` and
`chore: release ...`. Use focused subjects with `feat`, `fix`, `docs`, or `chore`
and describe the resulting change. Pull requests should state
the resulting behavior, relevant documentation updates, executed checks, and
remaining limitations, with related issues linked when applicable. Commit, push,
and publication require a separate explicit request.
