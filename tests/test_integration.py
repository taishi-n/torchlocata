"""Optional checks on the explicitly configured, read-only LOCATA snapshot."""

import os
import warnings
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch
from torch.utils.data import DataLoader, Subset

from locata_torch import LocataDataset, MissingAudioWarning, collate_locata, locata_doa

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def locata_root():
    value = os.environ.get("LOCATA_ROOT")
    if not value:
        pytest.skip("set LOCATA_ROOT explicitly to enable real-data tests")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        pytest.fail(f"LOCATA_ROOT is not a directory: {root}")
    return root


def test_real_index_and_missing_directories(locata_root):
    before = {
        p: (p.stat().st_size, p.stat().st_mtime_ns) for p in locata_root.rglob("*")
    }
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always", MissingAudioWarning)
        dataset = LocataDataset(locata_root, split=("dev", "eval"))
    assert len(dataset) > 0
    expected = {
        p
        for p in locata_root.glob("*/task*/recording*/*/audio_array_*.wav")
        if p.parent.name in {"benchmark2", "dicit", "dummy", "eigenmike"}
    }
    assert {r.audio_path for r in dataset.index} == expected
    assert all(
        not (p / f"audio_array_{p.name}.wav").is_file() for p in dataset.missing_audio
    )
    assert bool(dataset.missing_audio) == bool(emitted)
    after = {
        p: (p.stat().st_size, p.stat().st_mtime_ns) for p in locata_root.rglob("*")
    }
    assert before == after


@pytest.mark.parametrize(
    "split,task,recording,array",
    [
        ("dev", 1, 1, "benchmark2"),
        ("dev", 2, 1, "dicit"),
        ("dev", 3, 2, "dummy"),
        ("dev", 5, 1, "eigenmike"),
        ("dev", 6, 3, "benchmark2"),
        ("eval", 1, 1, "eigenmike"),
        ("eval", 4, 3, "dummy"),
        ("eval", 6, 3, "benchmark2"),
    ],
)
def test_real_representative_partial_reads(locata_root, split, task, recording, array):
    dataset = LocataDataset(
        locata_root,
        split=split,
        tasks=(task,),
        recordings=(recording,),
        arrays=(array,),
        load_source_audio=True,
    )
    if not dataset:
        pytest.skip("representative recording not in this snapshot")
    record = dataset.index[0]
    before = {
        p: (p.stat().st_size, p.stat().st_mtime_ns) for p in record.path.iterdir()
    }
    windows = dataset.windows(num_samples=4800, hop_samples=2400, drop_last=False)
    sample = windows[min(1, len(windows) - 1)]
    a, b = sample["metadata"]["start_frame"], sample["metadata"]["stop_frame"]
    with sf.SoundFile(record.audio_path) as stream:
        stream.seek(a)
        direct = stream.read(b - a, dtype="float32", always_2d=True)
    torch.testing.assert_close(
        sample["waveform"], torch.from_numpy(direct.T.copy()), atol=0, rtol=0
    )
    assert sample["waveform"].shape == (record.num_channels, b - a)
    assert sample["sample_rate"] == record.sample_rate
    assert sample["audio_time"].numel() == b - a
    assert sample["array_pose"]["microphone_position"].shape[1] == record.num_channels
    for source in sample["sources"].values():
        if source["pose"] is not None and torch.equal(
            source["pose"]["time"], sample["array_pose"]["time"]
        ):
            doa = locata_doa(sample["array_pose"], source["pose"])
            assert torch.isfinite(doa["inclination"]).all()
        if source["audio"] is not None:
            assert (
                len(source["audio"]["audio_time"])
                == source["audio"]["waveform"].shape[1]
            )
    if split == "dev" and task in (2, 6):
        assert len(sample["sources"]) > 1
    if task in (5, 6):
        position = np.loadtxt(
            record.path / f"position_array_{array}.txt", skiprows=1, delimiter="\t"
        )[:, 6:9]
        assert np.linalg.norm(position[-1] - position[0]) > 1e-3
    assert before == {
        p: (p.stat().st_size, p.stat().st_mtime_ns) for p in record.path.iterdir()
    }


def test_real_four_millisecond_regression(locata_root):
    dataset = LocataDataset(
        locata_root, tasks=(1,), recordings=(1,), arrays=("benchmark2",)
    )
    if not dataset:
        pytest.skip("reference recording not present")
    sample = dataset[0]
    # Regression for this challenge-era snapshot, not a corpus-wide constant.
    if dataset.index[0].num_frames != 155072:
        pytest.skip("reference snapshot has a different WAV length")
    assert sample["waveform"].shape == (12, 155072)
    assert len(sample["array_pose"]["time"]) == 389
    assert sample["time_origin"][3:] == pytest.approx((15, 40, 25.068))
    assert sample["array_pose"]["time"][0] == pytest.approx(-0.004, abs=1e-12)
    assert sample["required_time"]["time"][0] == pytest.approx(-0.004, abs=1e-12)
    partial = dataset.windows(num_samples=4800)[1]
    torch.testing.assert_close(
        partial["waveform"], sample["waveform"][:, 4800:9600], rtol=0, atol=0
    )


@pytest.mark.parametrize("workers", [0, 2])
def test_real_loader(locata_root, workers):
    dataset = LocataDataset(
        locata_root, tasks=(1,), recordings=(1,), arrays=("benchmark2",)
    )
    if not dataset:
        pytest.skip("reference recording not present")
    windows = Subset(dataset.windows(num_samples=4800), [0, 1, 2])
    args = {"multiprocessing_context": "spawn"} if workers else {}
    loader = DataLoader(
        windows,
        batch_size=2,
        collate_fn=collate_locata,
        num_workers=workers,
        timeout=30 if workers else 0,
        **args,
    )
    assert sum(len(batch["metadata"]) for batch in loader) == 3
