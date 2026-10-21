# MATLAB-based localization and evaluation

These explicit analysis functions are algorithmic reimplementations based on the
LOCATA organizers' MATLAB tools. They are not implicit Dataset preprocessing and
use the documented metric profile rather than claim historical leaderboard
equivalence. The raw
reader keeps its original clocks, invalid rows, and missing annotations.

## Provenance

| Python functionality | MATLAB basis |
| --- | --- |
| `prepare_ground_truth`, `locata_doa` | [`get_truth.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/get_truth.m), [`mycart2sph.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/mycart2sph.m) |
| `align_vad`, `activity_periods` | [`read_ground_truth.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/read_ground_truth.m) |
| `music_stft`, `music_localize`, `MusicConfig` | [`stft.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/stft.m), [`MUSIC.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/MUSIC.m), [`init.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/init.m) |
| `validate_tracks` | [`check_results.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/check_results.m) |
| `evaluate_locata`, `EvaluationConfig` | [`measures.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/measures.m) |
| `plot_scene`, `plot_doa`, `plot_evaluation` | [`plot_results.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/plot_results.m), plotting sections of `measures.m` |
| `write_submission` | [`results2csv.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/results2csv.m) |
| `aggregate_results`, portable bundles | [`measures_statistics.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/measures_statistics.m) motivates the purpose; the [portable schema](results-design.md) is a new design |

Reviewed IO commit: `632468f49b13ca5a9f2f51c064d91183c06622fa` (2020-01-31).
Reviewed evaluation commit: `2787cdabf21bc96453c0d4f3c66db9c9c9f40434`
(2020-02-06). Review date: 2026-10-21. Relevant MATLAB headers identify Christine
Evers and Heiner Löllmann and state ODC-BY 1.0.
[NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) retains this attribution.
The Python implementation uses independently written tensor/array algorithms;
MATLAB files and the bundled third-party Hungarian/Munkres implementations are
not redistributed or translated. This library's source license is Apache-2.0.
See [references](references.md) for the corpus license and original publications.

## Ground truth and voice activity

`prepare_ground_truth(sample, time_bounds=None)` returns `GroundTruth`: `time` is float64 `[T]`,
selected by `required_time.valid_flag`; `array_pose` is selected by timestamp;
`sources` preserves source IDs and maps each to `doa: DOA | None` and
`activity: Tensor | None`. `metadata` retains recording identity. Pose lookup
requires a matching timestamp within 1 ns. Quantized timestamps may repeat with
different measured poses. When the queried multiplicity agrees, ordered
occurrences are matched and retained. Conflicting duplicates with unequal
multiplicity raise as ambiguous; identical duplicate poses may be reused.
Required timestamps and their duplicates remain in their original order.
Missing source pose remains `None`. Missing/mismatched array poses raise.

Optional `time_bounds=(start, stop)` explicitly intersects valid required rows
with a half-open interval in shared-origin seconds. The default does not crop.
For full recordings whose annotations begin before audio, use
`time_bounds=sample["metadata"]["time_bounds"]` to evaluate within audio coverage.
This explicit selection never turns unavailable VAD into silence. Submission
export still receives the original full required-time table.

`align_vad(vad, time, sample_rate=...)` returns float64 `[T]` containing 0, 1, or
NaN. It uses previous-sample hold on the VAD's actual audio timestamps, including
an exact sample boundary in the new sample's interval. Coverage ends one actual
sample period after the last timestamp. Outside coverage is NaN, not silence.
Clock gaps remain unknown once the previous sample's single-period coverage
ends. Boundary comparisons use a 1 ps tolerance without changing returned times.
Only array-aligned VAD is used by `prepare_ground_truth`: close-talking VAD is a
different clock and propagation reference and is not silently substituted.
`activity_periods(activity)` returns int64 `[K, 2]` start/stop indices, with stop
exclusive; unknown values break known activity. Initial/final activity is kept.

## Single-source MUSIC

`MusicConfig` defaults follow the MATLAB baseline: symmetric 30 ms Hamming
window, quarter-window hop, requested FFT size 1024, 100 frames per block, block
step 10, strict 800–1400 Hz frequency selection, sound speed 340 m/s, azimuth
grid every 5 degrees and inclination grid every 10 degrees. DICIT uses zero-based
channels `(5, 6, 8)` (MATLAB `(6, 7, 9)`); other arrays use every WAV channel.
Explicit channel selections and alternative grids/framing are configurable.

`music_stft` returns `STFTResult`: complex128 `[frames, frequencies, channels]`,
float64 frame times in relative seconds, and float64 frequencies in Hz. Framing
matches `stft.m`, including its leading/trailing zeros, next-power-of-two FFT,
centered FFT padding, and times based on `fft_size/2`. If FFT size is shorter
than the window, MATLAB's truncation is preserved. This is why the default
48 kHz framing has a 1440-sample window and a 1024-point transform.

`music_localize(sample, config=...)` uses valid required timestamps and array
pose only, never source poses or VAD. Audio clocks must be uniform and agree
with the WAV rate; gaps raise. STFT times retain the window's start offset from
the recording origin. Geometry for each block uses the nearest array pose
within the selected pose support; no extrapolation or rotation interpolation is
performed. Blocks outside pose support remain unavailable.

For each frequency, the spatial covariance is `X.T @ X.conj()`. The largest
eigenvector spans the one-dimensional signal space; the remaining vectors span
noise. Steering vectors use world microphone positions and rotated LOCATA
directions. The inverse noise projection is summed across frequencies. Work is
bounded by one covariance block/grid spectrum, not a frequency/grid/block
four-dimensional tensor. Zero-energy blocks produce NaN estimates, not an
arbitrary direction. Grid ties choose the first flattened grid point.

`MusicResult` contains `track`, block times/azimuth/inclination, the config, and
measured `elapsed_seconds` (algorithm wall time, excluding Dataset loading).
Estimates are interpolated only between two adjacent finite blocks, with azimuth
unwrapped along the shortest arc. Gaps and out-of-range targets stay NaN. This
changes the reference's direct interpolation across the azimuth branch cut.
No waveform trimming, resampling, or normalization occurs.

## Tracks and evaluation

`DOATrack` contains `id: str`, `time_origin`, float64 `time: [N]`,
`azimuth: [N]`, and optional `inclination: [N]`. Angles are radians, azimuth is
in `[-pi, pi)`, and inclination from +z is in `[0, pi]`. NaN azimuth means no
estimate at that time. Missing inclination is `None`. IDs must be nonempty and
unique. Repeated quantized times use ordered occurrences when multiplicities
agree with ground truth. Conflicting duplicates with unequal multiplicities
raise; identical repeated estimates may be reused. Track time origins must match ground truth. A timestamp absent from a
track means no detection; evaluation does not interpolate estimates.

`evaluate_locata(truth, tracks, config=...)` requires source DOA and complete,
known array VAD. It rejects missing labels or uncovered times. Activity and
`valid_flag` are distinct. Matching uses only active sources and finite tracks,
wrapped azimuth distance, and a default inclusive 30-degree gate. Assignment
maximizes the number of valid pairs, then minimizes their total angular error.
The independently written rectangular assignment solver has no SciPy dependency.
Inclination error is measured for the azimuth-associated pairs that supply it.

OSPA uses ungated, clipped azimuth distance in degrees, cutoff 30 degrees and
orders `(1, 1.5, 2, 5)`, with one-to-one minimum-cost assignment and the standard
cardinality penalty. Empty/empty has distance zero; one empty set has the cutoff.
Angles in per-frame error tensors remain radians; reported scalar errors and
OSPA are degrees. Track association indices use `-1` for no association.

Per-recording metrics contain `value`, `numerator`, `denominator`, and `unit`.
Undefined values are `None` with denominator zero. Detection probability is
matched active source frames / active source frames. False-alarm rate is false
track-frame count / recording duration, matching the reference counter's units
of track-frames/s. Its speech-active variant divides by the total duration of
speech-active intervals. Angular error pools finite associated observations.
OSPA averages frame distances, including zero-distance empty frames.

Recording duration is last minus first evaluation time. Each active period's
duration is last minus first time in that period; a one-row period has zero
duration. Track latency is first detection minus period start. Completely missed
periods have unavailable latency and remain in detection/missed-period counts.
Track swaps compare each new association to the source's last assigned track,
including across misses and speech inactivity, as in the MATLAB reference.
Fragmentation
counts missed-to-detected transitions, including delayed acquisition, plus
swaps, as in `measures.m`. Rates pool counts over active-source-period duration.
`sources` and `periods` preserve the corresponding sufficient statistics.

## Deliberate changes from the MATLAB evaluator

This is metric profile `locata-torch-v1`, not a claim of historical leaderboard
equivalence. Corrections are explicit and tested:

- Respect independent audio clocks, actual sample rate, and VAD coverage instead
  of a fixed 48 kHz zero-based clock and repeated final VAD labels.
- Match pose timestamps instead of assuming equal annotation row indices.
- Restrict association and OSPA to voice-active sources. `measures.m` constructs
  some distance matrices over every source, including inactive ones.
- Keep the rectangular OSPA matrix; the reference passes a flattened matrix to
  `Hungarian` in one branch.
- Compute true inclination errors; the reference assigns azimuth errors into
  `error_el_ss` in one branch.
- Compute onset latency from the first detection. The reference's search over
  `this_miss` does not consistently implement that definition.
- Handle initial/final active periods, empty tracks, silence, deterministic
  assignment ties, missing inclination, and undefined rates explicitly.
- Do not export the reference's nonstandard `MOTA` variable as standard MOTA.
- Preserve frame-level sufficient statistics instead of silently applying the
  reference's utterance/source/recording mean-of-means. Period CSV rows retain
  angular-error sums/counts for alternative, explicitly chosen weighting.

## Plotting and persistence

The `plot` extra adds Matplotlib. Importing `locata_torch` does not import it.
Plot helpers create figures using the noninteractive Figure API, label units,
retain NaN gaps, and neither save nor show figures. Scene plots include source
trajectories, array trajectory, and numbered microphones. DOA plots label the
second angle as inclination. Evaluation plots show activity, azimuth error,
misses, false tracks, swaps, and OSPA.

See [portable results](results-design.md) for accepted JSON/CSV/NPZ storage,
explicit weighting, and the separate official submission adapter.

`write_submission` requires the raw `RequiredTime` table, including invalid rows,
and measured `elapsed_seconds`. It writes `telapsed.txt` and source TSV files.
Numeric submission `timestamps` use the first raw required timestamp as origin,
as in MATLAB `main.m`; calendar columns retain the shared audio-origin mapping.
For a complete recording's submission, supply its full required table and tracks
covering all valid rows. A cropped window is not a complete Challenge submission.
The adapter supports DOA (azimuth, optional inclination) and stable string IDs;
range/Cartesian estimate fields and Challenge participant spreadsheets are not
provided. The runtime manifest is additional provenance, not a Challenge field.

## End-to-end use

The new APIs are unreleased. Clone the
[source repository](https://github.com/taishi-n/torchlocata), then run the
[analysis example](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py)
from its root with the optional plot extra installed:

```sh
git clone https://github.com/taishi-n/torchlocata.git
cd torchlocata
uv sync --extra download --extra plot --group docs
uv run python examples/analyze_locata.py --root /path/to/LOCATA \
  --split eval --task 1 --recording 1 --array benchmark2 \
  --output /path/to/experiment --evaluate --plot --coarse-grid
```

This example reads one full recording, uses an explicitly coarser MUSIC grid,
and saves a portable bundle, official-style source files, and PNG diagnostics
outside the corpus. Omit `--coarse-grid` for the reference grid. Evaluation
requires source positions and known array VAD; omit `--evaluate` for recordings
without them. A single-source baseline is not a multi-source tracker.

For window-based analysis, call `music_localize(window)` and
`prepare_ground_truth(window)` directly. Save its per-window result separately;
do not pool overlapping windows as independent recordings or overwrite the
recording ID. Use a caller-chosen trial/window ID for such experiments.

## Validation limits

Synthetic tests use analytic cases, a separate scalar NumPy STFT/MUSIC reference,
and exhaustive small assignment checks. Integration tests are optional and read
explicit `LOCATA_ROOT` only. MATLAB/Octave execution is not available in the
development environment; source-based reference tests must not be described as
MATLAB execution parity. See [validation](validation.md) for executed checks.
