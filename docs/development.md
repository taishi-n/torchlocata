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
uv sync --python 3.12
uv run pytest -m "not integration"
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build
```

Ruff applies an 88-column Python style with four-space indentation. Use
`snake_case` for functions and modules, `PascalCase` for classes, and public type
annotations. `uv run ruff format .` applies formatting. Keep runtime dependencies
limited to PyTorch, NumPy, and SoundFile.

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

CI runs tests, Ruff, ty, package builds, strict documentation builds, and local
link validation. It does not publish the site or package.

## Contributions

No Git history is available to establish a repository commit convention. Use
concise imperative messages that describe the change. Pull requests should state
the resulting behavior, relevant documentation updates, executed checks, and
remaining limitations, with related issues linked when applicable. Commit, push,
and publication require a separate explicit request.
