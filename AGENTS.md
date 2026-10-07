# Repository Guidelines

## Project Structure & Module Organization

`src/locata_torch/` contains the library: `dataset.py` implements recording and window datasets, `collate.py` batches samples, `geometry.py` handles coordinate operations, `types.py` defines public schemas, and `_tables.py` parses TSV files. Export public APIs through `__init__.py`; retain `py.typed`.

`tests/` contains pytest tests and synthetic fixtures. `examples/read_locata.py` demonstrates DataLoader usage. `README.md` defines the API contract; `docs/references.md` records sources and decisions, and `docs/validation.md` records verification. `dist/` is generated output. Keep corpus assets outside the repository.

## Development Workflow

Update the README specification first, add tests and confirm the expected failure, implement the smallest change, then run checks and reconcile documentation. Keep one current API without compatibility aliases, migration code, or plugin infrastructure. Keep this library independent of TorchRIR.

## Build, Test, and Development Commands

```sh
uv sync --python 3.12                 # Install project and development dependencies
uv run pytest -m "not integration"    # Run mandatory synthetic tests
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration
uv run ruff check .                   # Check lint and imports
uv run ruff format .                  # Format Python files
uv run ruff format --check .          # Verify formatting without edits
uv run ty check                       # Check src and examples types
uv build                             # Build wheel and sdist
```

Run the example with `uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2`.

## Coding Style & Naming Conventions

Target Python 3.10+, use four-space indentation and Ruff's 88-character line length. Use `snake_case` for functions and modules, `PascalCase` for classes, and explicit type annotations for public interfaces. Keep dependencies centered on PyTorch, NumPy, and SoundFile.

## Testing Guidelines

Name tests `test_*.py` and functions `test_*`. Create small WAV/TSV fixtures under pytest temporary directories. Cover behavior changes, timing boundaries, missing annotations, partial reads, and spawn-worker serialization; no numeric coverage threshold is configured. Mark real-data tests `integration`, require explicit `LOCATA_ROOT`, and report skipped checks separately. Use a `__main__` guard in multiprocessing examples.

## Data Contracts & Configuration

Treat corpus files as read-only; never write caches beneath the dataset root. Preserve independent clocks, source IDs, CPU tensors, and documented dtypes. Represent missing annotations as `None`; keep `valid_flag` distinct from VAD. Avoid implicit preprocessing or mismatched-time DOA calculations.

## Commit & Pull Request Guidelines

This checkout has no Git history establishing commit conventions. Use concise, imperative subjects for focused changes. PR descriptions should explain changed behavior, documentation updates, test results, and limitations. Link relevant issues when available. Commit, push, or publish only when explicitly requested.
