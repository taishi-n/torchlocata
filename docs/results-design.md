# Portable result storage and aggregation

Per-recording evaluation returns typed dictionaries and CPU tensors.
Persistence uses versioned JSON, CSV, and optional
NPZ; plotting returns figures, leaving the destination to the caller.

## Goals

JSON and CSV make results readable from Python, MATLAB, R, Julia, and command-line
tools. The files retain source and track IDs, clock origins, units, missing values,
evaluation parameters, grouping, and metric denominators for later reanalysis.
Outputs are stored separately from the read-only LOCATA corpus.

## Bundle layout

```text
experiment/
  manifest.json
  recordings.csv
  sources.csv
  periods.csv
  details/<recording-key>.npz   # Optional large frame-level arrays
```

The UTF-8 JSON manifest contains a schema version, package version, MATLAB
reference commits, metric-definition identifier, corpus release identity,
algorithm configuration, coordinate convention, units, and caller-supplied
provenance. Recordings are identified by split/task/recording/array, not machine
paths. Calendar origins retain fractional seconds. JSON uses `null` for missing
scalars and rejects NaN/Infinity. Arrays are not embedded in the manifest.

CSV files use a documented header, one observation per row, stable string IDs,
and SI units named in columns. Empty numeric cells mean unavailable, never zero.
Reason columns and eligible/observed counts explain missing values. Per-source and per-period
tables retain sufficient statistics for later aggregation. No spreadsheet
formulas, Python object representations, or nested dict strings are written.

Optional compressed NPZ files contain only numeric and boolean arrays, with
`allow_pickle=False` on read. JSON describes shapes and units. NaN is allowed
only in arrays with documented unknown/error semantics. NPZ is convenient for
large Python workflows; the CSV tables remain the interchange baseline for
tools without an NPZ reader. Frame-level CSV export is not available.
No MAT, HDF5, or Parquet dependency is required.

## Aggregation contract

Group explicitly by corpus release, split, task, array, algorithm configuration,
and metric-definition identifier. Reject incompatible evaluation configurations.
Never silently mix dev/eval, gate thresholds, or angle conventions.

Choose equal recording weight (`recording`) or pooled eligible observations
(`pooled`). Each summary records the choice. Pooled detection probability uses
hits/opportunities, false-alarm rate uses false-track counts/duration, and angular
error uses error sums/associated-frame counts. Speech-active duration and recording
duration remain separate. Latency excludes completely missed
periods from its mean while reporting their count and detection probability.
Undefined values are omitted with an explicit denominator and missing count;
an all-missing group remains missing. Do not average precomputed means without
their weights. Repeated recording IDs must be rejected or explicitly treated as
separate trials.

`recordings.csv` has one row per recording/metric; `sources.csv` adds source ID.
Both contain identity columns, metric name, value, numerator, denominator, unit,
and missing reason. `periods.csv` contains onset/end times, half-open row indices,
activity/detection counts, swaps, fragments, latency, and azimuth/inclination
error sums and counts. These sufficient statistics permit external utterance
weighting without relying on the original MATLAB MAT workspaces.

Aggregation returns ordinary dictionaries. Every row retains its weighting,
unit, numerator, denominator, eligible/missing recording counts, and invariant
split, algorithm, corpus-release, metric-profile, and evaluation-config identity.
Direct evaluation results cannot infer an algorithm or corpus release; callers
must keep such inputs consistent. Bundles retain the caller's explicit provenance.

```python
from locata_torch import aggregate_results, read_results, write_results

write_results(
    [result],
    "/path/to/experiment/results",
    corpus_roots=("/path/to/LOCATA",),
    include_frame_arrays=True,
    provenance={"algorithm": "my-method", "corpus_release": "zenodo-3630471"},
)
bundle = read_results("/path/to/experiment/results")
summary = aggregate_results(
    bundle, group_by=("split", "task", "array"), weighting="pooled"
)
```

The returned summary is directly serializable with standard `json.dump` or
`csv.DictWriter`; no pandas conversion or MAT export is required.

## Alternatives and compatibility

JSON plus CSV is recommended for inspection and broad interchange. NPZ adds
compact frame diagnostics without changing the tabular schema. Parquet is useful
for much larger studies but adds Arrow and should be an optional future adapter.
HDF5 supports large arrays but introduces a dependency and a schema that still
needs documentation. MAT files match the original environment but are unsuitable
as the main cross-tool contract.

`write_submission` writes the organizers' tab-separated DOA source files from
validated tracks. It preserves calendar seconds and track IDs and writes only
beneath a caller-provided output directory, with measured `telapsed.txt`.
The full raw required-time table determines the numeric timestamp origin;
invalid rows are retained when choosing this origin but excluded from estimates.
This format is separate from internal result storage. Corpus regeneration and
MATLAB workspace conversion remain outside the reader's responsibilities.

## API surface

These functions are importable from `locata_torch`:

```python
write_results(results, output_dir, *, corpus_roots, include_frame_arrays=False)
read_results(output_dir)
aggregate_results(results, *, group_by, weighting)
write_submission(tracks, output_dir, *, required_time, corpus_roots, elapsed_seconds)
```

The official submission adapter is included. Frame-level CSV is deferred: NPZ
retains dense diagnostics and the smaller CSV tables remain fully portable.
Writers require the actual corpus roots even if they differ from environment
configuration, reject symlink-resolved destinations inside those roots, and
refuse to replace a populated destination. `read_results` returns a
`ResultBundle` containing manifest, recording/source/period tables, and optional
frame arrays; it does not fabricate a full `EvaluationResult` from scalar CSV.
`aggregate_results` also accepts a `ResultBundle` for reanalysis without NPZ.
