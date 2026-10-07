"""Map-style recording and fixed-window datasets for an existing LOCATA root."""

import os
import re
import warnings
from bisect import bisect_right
from collections import OrderedDict
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
import torch
from torch import Tensor
from torch.utils.data import Dataset

from ._tables import (
    TIME_ATOL,
    LocataError,
    SparseTable,
    binary_values,
    columns,
    read_table,
    times,
)
from .types import (
    ArrayPose,
    CalendarTime,
    LocataSample,
    Pose,
    RecordingInfo,
    RequiredTime,
    Source,
    TimedVAD,
)

ARRAYS = frozenset(("benchmark2", "dicit", "dummy", "eigenmike"))
POSE_COLUMNS = ("x", "y", "z", "ref_vec_x", "ref_vec_y", "ref_vec_z") + tuple(
    f"rotation_{i}{j}" for i in range(1, 4) for j in range(1, 4)
)


class MissingAudioWarning(UserWarning):
    """An existing array directory has no matching array WAV."""


def _positive(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _index(index: int, length: int) -> int:
    if index < 0:
        index += length
    if not 0 <= index < length:
        raise IndexError("dataset index out of range")
    return index


def _info(path: Path):
    try:
        info = sf.info(path)
    except (RuntimeError, OSError) as exc:
        raise LocataError(f"{path}: invalid WAV header: {exc}") from exc
    if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
        raise LocataError(f"{path}: WAV must have frames, a positive rate and channels")
    return info


def _audio(path: Path, start: int, stop: int, dtype: torch.dtype) -> Tensor:
    try:
        with sf.SoundFile(path) as stream:
            stream.seek(start)
            data = stream.read(
                stop - start,
                dtype="float32" if dtype == torch.float32 else "float64",
                always_2d=True,
            )
    except (RuntimeError, OSError) as exc:
        raise LocataError(f"{path}: audio read failed: {exc}") from exc
    if len(data) != stop - start:
        raise LocataError(f"{path}: short audio read in [{start}, {stop})")
    return torch.from_numpy(data.T.copy())


def _selection(time: np.ndarray, bounds: tuple[float, float] | None) -> slice:
    if bounds is None:
        return slice(None)
    return slice(
        int(np.searchsorted(time, bounds[0] - TIME_ATOL)),
        int(np.searchsorted(time, bounds[1] - TIME_ATOL)),
    )


def _pose(path: Path, origin: CalendarTime, bounds: tuple[float, float] | None) -> Pose:
    names, data = read_table(path)
    time = times(data, names, path, origin)
    selection = _selection(time, bounds)
    values = data[selection][:, columns(names, POSE_COLUMNS, path)]
    return {
        "time": torch.from_numpy(time[selection].copy()),
        "time_origin": origin,
        "position": torch.from_numpy(values[:, :3].copy()),
        "ref_vec": torch.from_numpy(values[:, 3:6].copy()),
        "rotation": torch.from_numpy(values[:, 6:].reshape(-1, 3, 3).copy()),
    }


def _array_pose(
    path: Path, channels: int, origin: CalendarTime, bounds: tuple[float, float] | None
) -> ArrayPose:
    # Parse the array table once, including microphones in WAV channel order.
    names, data = read_table(path)
    time = times(data, names, path, origin)
    selection = _selection(time, bounds)
    mic_columns = tuple(
        f"mic{mic}_{axis}" for mic in range(1, channels + 1) for axis in "xyz"
    )
    if {name for name in names if re.fullmatch(r"mic\d+_[xyz]", name)} != set(
        mic_columns
    ):
        raise LocataError(
            f"{path}: microphone columns must match {channels} WAV channels"
        )
    values = data[selection][:, columns(names, POSE_COLUMNS + mic_columns, path)]
    return {
        "time": torch.from_numpy(time[selection].copy()),
        "time_origin": origin,
        "position": torch.from_numpy(values[:, :3].copy()),
        "ref_vec": torch.from_numpy(values[:, 3:6].copy()),
        "rotation": torch.from_numpy(values[:, 6:15].reshape(-1, 3, 3).copy()),
        "microphone_position": torch.from_numpy(
            values[:, 15:].reshape(-1, channels, 3).copy()
        ),
    }


def _required(
    path: Path, origin: CalendarTime, bounds: tuple[float, float] | None
) -> RequiredTime:
    names, data = read_table(path)
    time = times(data, names, path, origin)
    flags = binary_values(data, names, "valid_flag", path)
    selection = _selection(time, bounds)
    return {
        "time": torch.from_numpy(time[selection].copy()),
        "valid_flag": torch.from_numpy(flags[selection].copy()),
    }


def _source_ids(path: Path, array: str) -> list[str]:
    patterns = [
        r"position_source_(.+)\.txt",
        r"audio_source_(.+)\.wav",
        r"audio_source_timestamps_(.+)\.txt",
        r"VAD_source_(.+)\.txt",
        rf"VAD_{array}_(.+)\.txt",
    ]
    ids = {
        match[1]
        for file in path.iterdir()
        if file.is_file()
        for pattern in patterns
        if (match := re.fullmatch(pattern, file.name))
    }
    return sorted(
        ids,
        key=lambda name: tuple(
            int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)
        ),
    )


class LocataDataset(Dataset[LocataSample]):
    """One item per existing (split, task, recording, array) WAV.

    Payloads are read lazily. Source audio is opt-in; geometry and available VAD
    are returned independently. All returned tensors are on the CPU. See the
    data model and time-and-windows guides for detailed shapes and clock contracts.

    Args:
        root: Existing LOCATA root; user-home expansion is supported.
        split: One split name, or a sequence selecting dev and/or eval.
        tasks: Task numbers from 1 through 6.
        recordings: Positive recording numbers across selected tasks, or all.
        arrays: Supported array names, or all available arrays.
        dtype: Waveform dtype, either torch.float32 or torch.float64.
        load_source_audio: Read available source WAV payloads when true.
        cache_size: Maximum cached sparse TXT indexes per worker.
        cache_bytes: Maximum estimated cached index bytes per worker.

    Attributes:
        index (tuple[RecordingInfo, ...]): Immutable recording information,
            sorted by split, numeric task,
            numeric recording, and array name.
        missing_audio (tuple[Path, ...]): Existing selected array directories
            without an array WAV.

    Raises:
        LocataError: The root, a WAV header, or a mandatory input is invalid.
        ValueError: A selection, dtype, or cache limit is invalid.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        split: str | Sequence[str] = "dev",
        tasks: Sequence[int] = (1, 2, 3, 4, 5, 6),
        recordings: Sequence[int] | None = None,
        arrays: Sequence[str] | None = None,
        dtype: torch.dtype = torch.float32,
        load_source_audio: bool = False,
        cache_size: int = 16,
        cache_bytes: int = 16777216,
    ):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise LocataError(f"{self.root}: dataset root is not a directory")
        splits = (split,) if isinstance(split, str) else tuple(split)
        if not splits or not set(splits) <= {"dev", "eval"}:
            raise ValueError("split must select dev and/or eval")
        if not tasks or any(_positive(task, "task") > 6 for task in tasks):
            raise ValueError("tasks must select integers from 1 through 6")
        if recordings is not None and (
            not recordings or any(_positive(rec, "recording") < 1 for rec in recordings)
        ):
            raise ValueError("recordings must select positive integers")
        chosen_arrays = ARRAYS if arrays is None else frozenset(arrays)
        if not chosen_arrays or not chosen_arrays <= ARRAYS:
            raise ValueError(f"arrays must select from {sorted(ARRAYS)}")
        if dtype not in (torch.float32, torch.float64):
            raise ValueError("dtype must be torch.float32 or torch.float64")
        if any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0
            for v in (cache_size, cache_bytes)
        ):
            raise ValueError("cache_size and cache_bytes must be nonnegative integers")
        self.dtype = dtype
        self.load_source_audio = load_source_audio
        self.cache_size = cache_size
        self.cache_bytes = cache_bytes
        self._cache: OrderedDict[Path, SparseTable] = OrderedDict()
        self._cache_pid = os.getpid()
        index: list[RecordingInfo] = []
        missing: list[Path] = []
        for split_name in sorted(set(splits)):
            for task in sorted(set(tasks)):
                task_path = self.root / split_name / f"task{task}"
                if not task_path.is_dir():
                    continue
                candidates = [
                    (int(match[1]), directory)
                    for directory in task_path.iterdir()
                    if directory.is_dir()
                    and (match := re.fullmatch(r"recording(\d+)", directory.name))
                ]
                for rec, directory in sorted(candidates):
                    if recordings is not None and rec not in recordings:
                        continue
                    for array in sorted(chosen_arrays):
                        path = directory / array
                        if not path.is_dir():
                            continue
                        audio_path = path / f"audio_array_{array}.wav"
                        if not audio_path.is_file():
                            missing.append(path)
                            continue
                        info = _info(audio_path)
                        for name in (
                            f"audio_array_timestamps_{array}.txt",
                            f"position_array_{array}.txt",
                            "required_time.txt",
                        ):
                            if not (path / name).is_file():
                                raise LocataError(
                                    f"{path / name}: required file is missing"
                                )
                        index.append(
                            RecordingInfo(
                                split_name,
                                task,
                                rec,
                                array,
                                path,
                                info.frames,
                                info.samplerate,
                                info.channels,
                            )
                        )
        self.index = tuple(index)
        self.missing_audio = tuple(missing)
        if missing:
            warnings.warn(
                "Array directories without WAV: " + ", ".join(map(str, missing)),
                MissingAudioWarning,
                stacklevel=2,
            )

    def __len__(self) -> int:
        return len(self.index)

    def __getstate__(self) -> dict[str, object]:
        state = self.__dict__.copy()
        state["_cache"] = OrderedDict()
        state["_cache_pid"] = None
        return state

    def _table(
        self, path: Path, kind: Literal["clock", "vad"], rows: int
    ) -> SparseTable:
        if self._cache_pid != os.getpid():
            self._cache.clear()
            self._cache_pid = os.getpid()
        if path in self._cache:
            self._cache.move_to_end(path)
            return self._cache[path]
        table = SparseTable(path, kind, rows)
        if self.cache_size and table.nbytes <= self.cache_bytes:
            self._cache[path] = table
            while (
                len(self._cache) > self.cache_size
                or sum(item.nbytes for item in self._cache.values()) > self.cache_bytes
            ):
                self._cache.popitem(last=False)
        return table

    def _vad(
        self,
        path: Path,
        clock: SparseTable,
        start: int,
        stop: int,
        origin: CalendarTime,
    ) -> TimedVAD | None:
        if not path.is_file():
            return None
        table = self._table(path, "vad", clock.count)
        return {
            "time": torch.from_numpy(clock.clock(start, stop, origin)),
            "values": torch.from_numpy(
                binary_values(table.read(start, stop), table.names, "VAD", path)
            ),
        }

    def __getitem__(self, index: int) -> LocataSample:
        record = self.index[_index(index, len(self))]
        return self._sample(record, 0, record.num_frames, window=False)

    def _sample(
        self, record: RecordingInfo, start: int, stop: int, *, window: bool
    ) -> LocataSample:
        path = record.path
        clock = self._table(
            path / f"audio_array_timestamps_{record.array}.txt",
            "clock",
            record.num_frames,
        )
        origin = clock.origin
        audio_time = clock.clock(start, min(stop + 1, record.num_frames), origin)
        end = (
            float(audio_time[-1])
            if stop < record.num_frames
            else float(audio_time[-1]) + 1 / record.sample_rate
        )
        bounds = (float(audio_time[0]), end)
        annotation_bounds = bounds if window else None
        sources: dict[str, Source] = {}
        for source_id in _source_ids(path, record.array):
            source_path = path / f"audio_source_{source_id}.wav"
            pose_path = path / f"position_source_{source_id}.txt"
            source_vad_path = path / f"VAD_source_{source_id}.txt"
            source: Source = {
                "pose": _pose(pose_path, origin, annotation_bounds)
                if pose_path.is_file()
                else None,
                "audio": None,
                "audio_available": source_path.is_file(),
                "vad": {
                    "array": self._vad(
                        path / f"VAD_{record.array}_{source_id}.txt",
                        clock,
                        start,
                        stop,
                        origin,
                    ),
                    "source": None,
                },
            }
            if source_vad_path.is_file() or (
                self.load_source_audio and source_path.is_file()
            ):
                if not source_path.is_file():
                    raise LocataError(
                        f"{source_vad_path}: source WAV {source_path} is required"
                    )
                info = _info(source_path)
                source_clock = self._table(
                    path / f"audio_source_timestamps_{source_id}.txt",
                    "clock",
                    info.frames,
                )
                a, b = (
                    (
                        source_clock.lower_bound(bounds[0], origin),
                        source_clock.lower_bound(bounds[1], origin),
                    )
                    if window
                    else (0, info.frames)
                )
                if self.load_source_audio:
                    source["audio"] = {
                        "waveform": _audio(source_path, a, b, self.dtype),
                        "sample_rate": info.samplerate,
                        "audio_time": torch.from_numpy(
                            source_clock.clock(a, b, origin)
                        ),
                        "start_frame": a,
                        "stop_frame": b,
                    }
                source["vad"]["source"] = self._vad(
                    source_vad_path, source_clock, a, b, origin
                )
            sources[source_id] = source
        return {
            "waveform": _audio(record.audio_path, start, stop, self.dtype),
            "sample_rate": record.sample_rate,
            "audio_time": torch.from_numpy(audio_time[: stop - start].copy()),
            "time_origin": origin,
            "required_time": _required(
                path / "required_time.txt", origin, annotation_bounds
            ),
            "array_pose": _array_pose(
                path / f"position_array_{record.array}.txt",
                record.num_channels,
                origin,
                annotation_bounds,
            ),
            "sources": sources,
            "metadata": {
                "id": record.id,
                "split": record.split,
                "task": record.task,
                "recording": record.recording,
                "array": record.array,
                "path": record.path,
                "start_frame": start,
                "stop_frame": stop,
                "num_frames": record.num_frames,
                "time_bounds": bounds,
            },
        }

    def windows(
        self,
        *,
        num_samples: int,
        hop_samples: int | None = None,
        drop_last: bool = True,
    ) -> "LocataWindowDataset":
        """Create a partial-read window view with the recording's time origin.

        Args:
            num_samples: Positive window length in WAV frames.
            hop_samples: Positive hop in frames, or the window length if omitted.
            drop_last: Keep only complete windows when true; retain short tails
                without padding when false.

        Returns:
            A map-style view cropping independent annotations to half-open
            window time bounds.
        """
        return LocataWindowDataset(
            self, num_samples=num_samples, hop_samples=hop_samples, drop_last=drop_last
        )


class LocataWindowDataset(Dataset[LocataSample]):
    """Fixed-frame view; every waveform read seeks directly to its window.

    Prefer constructing this view with `LocataDataset.windows`.

    Args:
        dataset: Parent recording dataset and its I/O options.
        num_samples: Positive window length in WAV frames.
        hop_samples: Positive frame hop, or the window length if omitted.
        drop_last: Exclude incomplete tails when true. Otherwise return each
            start inside the recording, with the final frames left unpadded.

    Raises:
        ValueError: The window length or hop is not a positive integer.
    """

    def __init__(
        self,
        dataset: LocataDataset,
        *,
        num_samples: int,
        hop_samples: int | None = None,
        drop_last: bool = True,
    ):
        self.dataset = dataset
        self.num_samples = _positive(num_samples, "num_samples")
        self.hop_samples = (
            num_samples
            if hop_samples is None
            else _positive(hop_samples, "hop_samples")
        )
        self.drop_last = drop_last
        self._ends = [0]
        for record in dataset.index:
            n = record.num_frames
            count = (
                max(0, (n - num_samples) // self.hop_samples + 1)
                if drop_last
                else (n - 1) // self.hop_samples + 1
            )
            self._ends.append(self._ends[-1] + count)

    def __len__(self) -> int:
        return self._ends[-1]

    def __getitem__(self, index: int) -> LocataSample:
        index = _index(index, len(self))
        recording = bisect_right(self._ends, index) - 1
        record = self.dataset.index[recording]
        start = (index - self._ends[recording]) * self.hop_samples
        stop = min(start + self.num_samples, record.num_frames)
        return self.dataset._sample(record, start, stop, window=True)
