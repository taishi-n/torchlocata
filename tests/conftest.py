from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

TIME_COLUMNS = ["year", "month", "day", "hour", "minute", "second"]
POSE_COLUMNS = ["x", "y", "z"] + [f"ref_vec_{axis}" for axis in "xyz"]
POSE_COLUMNS += [f"rotation_{i}{j}" for i in range(1, 4) for j in range(1, 4)]
ROTATION = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])


def calendar(offset: float) -> list[float]:
    seconds = Decimal("86399.996") + Decimal(str(float(offset)))
    days = int(seconds // 86400)
    day = date(2017, 1, 25) + timedelta(days=days)
    seconds -= days * 86400
    hour = int(seconds // 3600)
    minute = int((seconds - hour * 3600) // 60)
    second = seconds - hour * 3600 - minute * 60
    return [day.year, day.month, day.day, hour, minute, float(second)]


def write_table(path: Path, columns: Sequence[str], rows: Sequence[Sequence[float]]):
    path.write_text(
        "\t".join(columns)
        + "\n"
        + "".join("\t".join(format(v, ".17g") for v in row) + "\n" for row in rows)
    )


def write_pose(path: Path, offsets: Sequence[float], channels: int = 0):
    columns = TIME_COLUMNS + POSE_COLUMNS
    columns += [f"mic{mic}_{axis}" for mic in range(1, channels + 1) for axis in "xyz"]
    position = [1.0, 2.0, 3.0] if channels else [1.0, 3.0, 3.0]
    rows = [
        calendar(t)
        + position
        + ROTATION[:, 1].tolist()
        + ROTATION.reshape(-1).tolist()
        + [
            float(mic * 10 + axis)
            for mic in range(1, channels + 1)
            for axis in range(3)
        ]
        for t in offsets
    ]
    write_table(path, columns, rows)


@pytest.fixture
def make_recording(tmp_path):
    def make(
        *,
        split="dev",
        task=1,
        recording=1,
        array="dummy",
        frames=10,
        channels=2,
        sample_rate=1000,
        sources=(),
        source_audio=True,
        source_pose=True,
        vad=False,
        audio_offsets=None,
    ):
        directory = tmp_path / split / f"task{task}" / f"recording{recording}" / array
        directory.mkdir(parents=True, exist_ok=True)
        waveform = np.arange(frames * channels, dtype=np.float64).reshape(
            frames, channels
        )
        waveform = waveform / 7  # Values above 1 must remain unchanged.
        sf.write(
            directory / f"audio_array_{array}.wav",
            waveform,
            sample_rate,
            subtype="DOUBLE",
        )
        if audio_offsets is None:
            audio_offsets = np.arange(frames) / sample_rate
        write_table(
            directory / f"audio_array_timestamps_{array}.txt",
            TIME_COLUMNS,
            [calendar(float(t)) for t in audio_offsets],
        )
        write_pose(
            directory / f"position_array_{array}.txt",
            [-0.004, 0, 0.004, 0.006, 0.008, 0.01],
            channels,
        )
        write_table(
            directory / "required_time.txt",
            TIME_COLUMNS + ["valid_flag"],
            [
                calendar(t) + [v]
                for t, v in zip(
                    [-0.004, 0.001, 0.004, 0.006, 0.009, 0.012],
                    [1, 0, 1, 1, 0, 1],
                    strict=True,
                )
            ],
        )
        for source in sources:
            if source_pose:
                write_pose(
                    directory / f"position_source_{source}.txt",
                    [-0.003, 0.001, 0.005, 0.009],
                )
            if source_audio:
                data = np.arange(8, dtype=np.float64) / 20
                sf.write(
                    directory / f"audio_source_{source}.wav",
                    data,
                    500,
                    subtype="DOUBLE",
                )
                write_table(
                    directory / f"audio_source_timestamps_{source}.txt",
                    TIME_COLUMNS,
                    [calendar(t) for t in np.arange(8) / 500 - 0.002],
                )
            if vad:
                write_table(
                    directory / f"VAD_{array}_{source}.txt",
                    ["VAD"],
                    [[i % 2] for i in range(frames)],
                )
                if source_audio:
                    write_table(
                        directory / f"VAD_source_{source}.txt",
                        ["VAD"],
                        [[i % 2] for i in range(8)],
                    )
        return directory, waveform

    return make
