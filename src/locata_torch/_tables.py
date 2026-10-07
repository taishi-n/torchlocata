"""Read-only TSV parsing and sparse seek indices, without clock approximation."""

import io
from datetime import date
from itertools import islice
from pathlib import Path
from typing import BinaryIO, Literal

import numpy as np
from numpy.typing import NDArray

from .types import CalendarTime

FloatArray = NDArray[np.float64]
TIME_COLUMNS = ("year", "month", "day", "hour", "minute", "second")
BLOCK_ROWS = 4096
TIME_ATOL = 1e-12  # Boundary comparisons only; returned clock values are untouched.


class LocataError(RuntimeError):
    """Invalid LOCATA input, configuration, or preparation, with its path and cause."""


def _header(stream: BinaryIO, path: Path) -> tuple[str, ...]:
    try:
        names = tuple(stream.readline().decode("utf-8-sig").rstrip("\r\n").split("\t"))
    except UnicodeError as exc:
        raise LocataError(f"{path}: invalid UTF-8 header: {exc}") from exc
    if not all(names) or len(set(names)) != len(names):
        raise LocataError(f"{path}: empty or duplicate column names")
    return names


def columns(names: tuple[str, ...], required: tuple[str, ...], path: Path) -> list[int]:
    missing = set(required) - set(names)
    if missing:
        raise LocataError(f"{path}: missing columns {sorted(missing)}")
    return [names.index(name) for name in required]


def _rows(data: bytes, names: tuple[str, ...], path: Path) -> FloatArray:
    try:
        result = np.loadtxt(io.BytesIO(data), delimiter="\t", comments=None, ndmin=2)
    except (ValueError, UnicodeError) as exc:
        raise LocataError(f"{path}: malformed numeric rows: {exc}") from exc
    if result.shape[1] != len(names):
        raise LocataError(
            f"{path}: expected {len(names)} columns, got {result.shape[1]}"
        )
    return result


def relative_seconds(calendar: FloatArray, origin: CalendarTime) -> FloatArray:
    """Subtract within-day values separately from ordinal days (no epoch float)."""
    if not np.isfinite(calendar).all():
        raise ValueError("calendar timestamps must be finite")
    if not np.equal(calendar[:, :5], np.floor(calendar[:, :5])).all():
        raise ValueError("year, month, day, hour, minute must be integers")
    if (
        (calendar[:, 3:5] < 0).any()
        or (calendar[:, 3] >= 24).any()
        or (calendar[:, 4] >= 60).any()
        or (calendar[:, 5] < 0).any()
        or (calendar[:, 5] >= 60).any()
    ):
        raise ValueError("invalid time of day (leap seconds are not supported)")
    dates, inverse = np.unique(calendar[:, :3], axis=0, return_inverse=True)
    ordinals = np.array([date(*(int(v) for v in row)).toordinal() for row in dates])
    origin_day = date(*origin[:3]).toordinal()
    whole_seconds = (
        (ordinals[inverse] - origin_day) * 86400.0
        + (calendar[:, 3] - origin[3]) * 3600
        + (calendar[:, 4] - origin[4]) * 60
    )
    return (whole_seconds - origin[5]) + calendar[:, 5]


def times(
    data: FloatArray,
    names: tuple[str, ...],
    path: Path,
    origin: CalendarTime,
    *,
    strict: bool = False,
) -> FloatArray:
    try:
        result = relative_seconds(data[:, columns(names, TIME_COLUMNS, path)], origin)
    except (ValueError, OverflowError) as exc:
        raise LocataError(f"{path}: invalid calendar timestamp: {exc}") from exc
    differences = np.diff(result)
    if (differences < 0).any() or (strict and (differences == 0).any()):
        order = "strictly increasing" if strict else "nondecreasing"
        raise LocataError(f"{path}: timestamps must be {order}")
    return result


def binary_values(
    data: FloatArray, names: tuple[str, ...], column: str, path: Path
) -> NDArray[np.bool_]:
    values = data[:, columns(names, (column,), path)[0]]
    if not np.isin(values, (0, 1)).all():
        raise LocataError(f"{path}: {column} must contain only 0 or 1")
    return values.astype(np.bool_)


def read_table(path: Path) -> tuple[tuple[str, ...], FloatArray]:
    try:
        with path.open("rb") as stream:
            names = _header(stream, path)
            data = stream.read()
        if not data.strip():
            raise LocataError(f"{path}: table has no data rows")
        return names, _rows(data, names, path)
    except OSError as exc:
        raise LocataError(f"{path}: {exc}") from exc


class SparseTable:
    """Validate once in bounded chunks, retain a file offset every BLOCK_ROWS."""

    def __init__(self, path: Path, kind: Literal["clock", "vad"], expected_rows: int):
        self.path = path
        self.kind = kind
        offsets: list[int] = []
        checkpoints: list[float] = []
        self.origin: CalendarTime = (1, 1, 1, 0, 0, 0.0)
        count = 0
        previous = -np.inf
        try:
            with path.open("rb") as stream:
                self.names = _header(stream, path)
                time_columns = (
                    columns(self.names, TIME_COLUMNS, path) if kind == "clock" else []
                )
                if kind == "vad":
                    columns(self.names, ("VAD",), path)
                while True:
                    offset = stream.tell()
                    lines = list(islice(stream, BLOCK_ROWS))
                    if not lines:
                        break
                    if any(not line.strip() for line in lines):
                        raise LocataError(
                            f"{path}: blank row near data row {count + 1}"
                        )
                    data = _rows(b"".join(lines), self.names, path)
                    if kind == "clock":
                        if count == 0:
                            row = data[0, time_columns]
                            # Validate before converting the integer fields.
                            times(
                                data[:1],
                                self.names,
                                path,
                                (1, 1, 1, 0, 0, 0.0),
                                strict=True,
                            )
                            self.origin = (
                                int(row[0]),
                                int(row[1]),
                                int(row[2]),
                                int(row[3]),
                                int(row[4]),
                                float(row[5]),
                            )
                        clock = times(data, self.names, path, self.origin, strict=True)
                        if clock[0] <= previous:
                            raise LocataError(
                                f"{path}: timestamps must be strictly increasing "
                                f"near row {count + 1}"
                            )
                        previous = float(clock[-1])
                        checkpoints.append(float(clock[0]))
                    else:
                        binary_values(data, self.names, "VAD", path)
                    offsets.append(offset)
                    count += len(data)
        except OSError as exc:
            raise LocataError(f"{path}: {exc}") from exc
        if count != expected_rows:
            raise LocataError(
                f"{path}: {count} rows, expected {expected_rows} WAV frames"
            )
        self.count = count
        self.offsets = np.array(offsets, dtype=np.int64)
        self.checkpoints = np.array(checkpoints, dtype=np.float64)

    @property
    def nbytes(self) -> int:
        return (
            self.offsets.nbytes
            + self.checkpoints.nbytes
            + sum(map(len, self.names))
            + 256
        )

    def read(self, start: int, stop: int) -> FloatArray:
        if not 0 <= start <= stop <= self.count:
            raise IndexError(f"{self.path}: invalid row range [{start}, {stop})")
        if start == stop:
            return np.empty((0, len(self.names)), dtype=np.float64)
        block = start // BLOCK_ROWS
        try:
            with self.path.open("rb") as stream:
                stream.seek(int(self.offsets[block]))
                for _ in range(start - block * BLOCK_ROWS):
                    stream.readline()
                data = _rows(
                    b"".join(islice(stream, stop - start)), self.names, self.path
                )
        except OSError as exc:
            raise LocataError(f"{self.path}: {exc}") from exc
        if len(data) != stop - start:
            raise LocataError(f"{self.path}: file changed after index construction")
        return data

    def clock(self, start: int, stop: int, origin: CalendarTime) -> FloatArray:
        return times(self.read(start, stop), self.names, self.path, origin, strict=True)

    def lower_bound(self, value: float, origin: CalendarTime) -> int:
        """First row at or after a time in the recording's common clock."""
        origin_offset = relative_seconds(
            np.array([self.origin], dtype=np.float64), origin
        )[0]
        local_value = value - origin_offset - TIME_ATOL
        block = max(
            0, int(np.searchsorted(self.checkpoints, local_value, side="right")) - 1
        )
        start = block * BLOCK_ROWS
        stop = min(start + BLOCK_ROWS, self.count)
        clock = self.clock(start, stop, origin)
        return start + int(np.searchsorted(clock, value - TIME_ATOL, side="left"))
