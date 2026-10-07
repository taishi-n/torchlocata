# Time and windows

## Independent clocks and a shared origin

Array audio, array pose, `required_time`, source pose, and source audio each use
their own timestamp table. Calendar columns are `year`, `month`, `day`, `hour`,
`minute`, and `second`. Fractional seconds and date changes are retained.

Every clock is converted to seconds relative to the first array-audio timestamp
of the recording. The original calendar origin remains available as
`time_origin`, including in window samples and pose schemas. Conversion uses
calendar differences without subtracting large floating-point Unix epochs.
Files contain no timezone information, so the reader does not assume UTC.

For `dev/task1/recording1/benchmark2` in the checked snapshot, array audio starts
at `15:40:25.068`, while pose and `required_time` start at `15:40:25.064`.
Their first relative times are `0.0` and `-0.004` seconds. This difference is
measured from the files, with no fixed correction applied to other recordings.
The WAV has 155072 frames and the pose has 389 rows; these are separate clocks.

All calendar values must be finite and valid. Audio clocks must strictly
increase. Pose and required-time clocks must be nondecreasing: duplicate
annotation timestamps found in the local snapshot are retained in their original
order. The reader does not sort, deduplicate, interpolate, or remove invalid rows.
Leap-second calendars are not supported.

## Construct a window view

`dataset.windows(num_samples=..., hop_samples=None, drop_last=True)` returns a
map-style `LocataWindowDataset`. Window length and hop are positive integers in
WAV frames. The default hop equals the window length.

Windows start at `0, hop, 2*hop, ...`. Each frame interval is half-open:
`[start_frame, stop_frame)`.

| Setting | Included starts | Tail behavior |
| --- | --- | --- |
| `drop_last=True` | Only starts with a full window inside the recording | A shorter recording contributes no windows |
| `drop_last=False` | Every start before the end of the recording | Short tails remain short until collation |

With overlapping windows, more than one short tail can occur. A hop greater
than the window length leaves gaps. For a 10-frame recording, a 6-frame window
with hop 4 gives `[0,6)` and `[4,10)` when dropping tails; keeping tails also gives
`[8,10)`.

The view stores cumulative window counts per recording rather than enumerating
every window. It inherits the recording selection, dtype, source-audio option,
and cache settings of the parent dataset.

## Determine time boundaries

`metadata["time_bounds"] = (a, b)` uses the actual timestamp of `start_frame` and
the actual timestamp of `stop_frame`. If the stop equals the WAV frame count, the
end boundary is the last actual timestamp plus `1 / sample_rate`. Nonuniform
clocks remain unchanged; only this final endpoint uses the nominal sample period.

Each window crops pose, required times, source audio, and VAD using that field's
own clock and the half-open interval `a <= time < b`. The reader adds no surrounding
pose rows and keeps the recording's origin, so the window's first timestamp need
not be zero. An existing table with no selected rows returns empty tensors of the
documented shapes.

Boundary comparisons use a `1e-12` second tolerance: values within this distance
of a boundary are treated as lying on it. A start-boundary row is included and an
end-boundary row is excluded. Returned timestamps are not rounded or corrected;
the 4 ms start difference remains intact.

A recording-level item returns every row of each available annotation table and
source audio, including rows outside the array-audio interval. Do not assume that
two returned pose tables describe simultaneous rows. The
[DOA helper](geometry.md#time-alignment) requires explicitly matched clocks.
