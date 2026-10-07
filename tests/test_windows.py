import numpy as np
import pytest
import soundfile as sf
import torch

from locata_torch import LocataDataset, LocataError, LocataWindowDataset


def test_hop_tail_bounds_and_annotation_edges(make_recording, tmp_path):
    make_recording(sources=("s",), vad=True)
    dataset = LocataDataset(tmp_path, load_source_audio=True)
    windows = dataset.windows(num_samples=4, hop_samples=3)
    assert isinstance(windows, LocataWindowDataset)
    assert len(windows) == 3
    assert [
        (s["metadata"]["start_frame"], s["metadata"]["stop_frame"]) for s in windows
    ] == [(0, 4), (3, 7), (6, 10)]
    first = windows[0]
    assert first["array_pose"]["time"].tolist() == [0.0]
    assert first["required_time"]["valid_flag"].tolist() == [False]
    assert first["sources"]["s"]["pose"]["time"].tolist() == pytest.approx(
        [0.001], abs=3e-11
    )
    assert first["sources"]["s"]["audio"]["start_frame"] == 1
    assert first["sources"]["s"]["audio"]["stop_frame"] == 3
    tail = dataset.windows(num_samples=4, hop_samples=3, drop_last=False)
    assert len(tail) == 4
    assert tail[-1]["waveform"].shape == (2, 1)
    assert tail[-1]["metadata"]["time_bounds"] == pytest.approx(
        (0.009, 0.010), abs=3e-11
    )
    assert tail[1]["time_origin"] == first["time_origin"]
    assert tail[1]["audio_time"][0] == pytest.approx(0.003, abs=3e-11)
    assert tail[-1]["array_pose"]["time"].numel() == 0
    assert tail[-1]["array_pose"]["microphone_position"].shape == (0, 2, 3)
    with pytest.raises(IndexError):
        windows[3]


def test_partial_io_matches_full_and_seeks(make_recording, tmp_path, monkeypatch):
    make_recording(frames=30, sources=("s",))
    dataset = LocataDataset(tmp_path, load_source_audio=True)
    full = dataset[0]
    original = sf.SoundFile.read
    calls = []

    def read(file, frames=-1, *args, **kwargs):
        calls.append((str(file.name), file.tell(), frames))
        return original(file, frames, *args, **kwargs)

    monkeypatch.setattr(sf.SoundFile, "read", read)
    sample = dataset.windows(num_samples=5, hop_samples=4)[1]
    torch.testing.assert_close(
        sample["waveform"], full["waveform"][:, 4:9], rtol=0, atol=0
    )
    torch.testing.assert_close(
        sample["audio_time"], full["audio_time"][4:9], rtol=0, atol=0
    )
    source = sample["sources"]["s"]["audio"]
    torch.testing.assert_close(
        source["waveform"],
        full["sources"]["s"]["audio"]["waveform"][
            :, source["start_frame"] : source["stop_frame"]
        ],
    )
    array_calls = [call for call in calls if call[0].endswith("audio_array_dummy.wav")]
    assert array_calls == [
        (str(full["metadata"]["path"] / "audio_array_dummy.wav"), 4, 5)
    ]
    assert all(frames >= 0 for _, _, frames in calls)


def test_short_recording_and_gap_hop(make_recording, tmp_path):
    make_recording(frames=3)
    dataset = LocataDataset(tmp_path)
    assert len(dataset.windows(num_samples=4)) == 0
    assert len(dataset.windows(num_samples=4, drop_last=False)) == 1
    assert len(dataset.windows(num_samples=1, hop_samples=10, drop_last=False)) == 1
    with pytest.raises(IndexError):
        dataset.windows(num_samples=4)[0]


def test_multiple_recording_window_mapping(make_recording, tmp_path):
    make_recording(frames=3, recording=1)
    make_recording(frames=9, recording=2)
    windows = LocataDataset(tmp_path).windows(num_samples=4)
    assert len(windows) == 2
    assert windows[0]["metadata"]["recording"] == 2
    assert windows[1]["metadata"]["start_frame"] == 4


def test_irregular_clock_is_preserved(make_recording, tmp_path):
    offsets = [0, 0.001, 0.003, 0.006, 0.01]
    make_recording(frames=5, audio_offsets=offsets)
    dataset = LocataDataset(tmp_path)
    np.testing.assert_allclose(dataset[0]["audio_time"].numpy(), offsets, atol=3e-11)
    window = dataset.windows(num_samples=2)[1]
    assert window["metadata"]["time_bounds"] == pytest.approx((0.003, 0.01), abs=3e-11)
    assert window["array_pose"]["time"].tolist() == pytest.approx(
        [0.004, 0.006, 0.008], abs=3e-11
    )


@pytest.mark.parametrize(
    "kwargs",
    [{"num_samples": 0}, {"num_samples": 2, "hop_samples": 0}, {"num_samples": 2.5}],
)
def test_invalid_windows(tmp_path, kwargs):
    with pytest.raises(ValueError):
        LocataDataset(tmp_path).windows(**kwargs)


@pytest.mark.parametrize("name", ["VAD_dummy_s.txt", "VAD_source_s.txt"])
def test_vad_bad_count_and_values(make_recording, tmp_path, name):
    directory, _ = make_recording(sources=("s",), vad=True)
    path = directory / name
    path.write_text("VAD\n0\n1\n")
    with pytest.raises(LocataError, match=name):
        LocataDataset(tmp_path)[0]
    rows = 10 if name == "VAD_dummy_s.txt" else 8
    path.write_text("VAD\n" + "0\n" * (rows - 1) + "2\n")
    with pytest.raises(LocataError, match=name):
        LocataDataset(tmp_path)[0]


def test_timestamp_and_vad_cache_reuses_full_scan(
    make_recording, tmp_path, monkeypatch
):
    from locata_torch import _tables

    make_recording(frames=9000, sources=("s",), source_audio=False, vad=True)
    builds = []
    original = _tables.SparseTable.__init__

    def counted(self, path, *args, **kwargs):
        builds.append(path.name)
        original(self, path, *args, **kwargs)

    monkeypatch.setattr(_tables.SparseTable, "__init__", counted)
    windows = LocataDataset(tmp_path).windows(num_samples=4, hop_samples=4100)
    for i in (0, 1, 2, 1):
        sample = windows[i]
        assert sample["waveform"].shape == (2, 4)
    assert builds.count("audio_array_timestamps_dummy.txt") == 1
    assert builds.count("VAD_dummy_s.txt") == 1


def test_lru_has_process_and_byte_bounds(make_recording, tmp_path):
    make_recording(frames=100, recording=1)
    make_recording(frames=100, recording=2)
    dataset = LocataDataset(tmp_path, cache_size=1, cache_bytes=4096)
    dataset[0]
    dataset[1]
    assert len(dataset._cache) <= 1
    assert sum(index.nbytes for index in dataset._cache.values()) <= 4096
    dataset._cache_pid = -1
    dataset[0]
    assert len(dataset._cache) <= 1
    uncached = LocataDataset(tmp_path, cache_size=0, cache_bytes=0)
    uncached[0]
    assert not uncached._cache


def test_empty_source_interval_is_present_and_not_missing(make_recording, tmp_path):
    make_recording(frames=30, sources=("s",), vad=True)
    sample = LocataDataset(tmp_path, load_source_audio=True).windows(num_samples=4)[5]
    source = sample["sources"]["s"]
    assert source["audio_available"] is True
    assert source["audio"]["waveform"].shape == (1, 0)
    assert source["audio"]["audio_time"].numel() == 0
    assert source["pose"]["position"].shape == (0, 3)
    assert source["vad"]["source"]["values"].numel() == 0
