import pickle
from pathlib import Path

import pytest
import soundfile as sf
import torch
from torch.utils.data import Dataset

from locata_torch import LocataDataset, LocataError, MissingAudioWarning


def test_numeric_index_and_selectors(make_recording, tmp_path):
    for task, rec, array in [
        (2, 10, "dicit"),
        (1, 10, "dummy"),
        (1, 2, "dummy"),
        (1, 2, "dicit"),
    ]:
        make_recording(task=task, recording=rec, array=array)
    make_recording(split="eval")
    (tmp_path / "results").mkdir()
    (tmp_path / "root.zip").write_bytes(b"ignored")
    dataset = LocataDataset(tmp_path, split=("eval", "dev"), tasks=(2, 1))
    assert isinstance(dataset, Dataset)
    assert [(r.split, r.task, r.recording, r.array) for r in dataset.index] == [
        ("dev", 1, 2, "dicit"),
        ("dev", 1, 2, "dummy"),
        ("dev", 1, 10, "dummy"),
        ("dev", 2, 10, "dicit"),
        ("eval", 1, 1, "dummy"),
    ]
    selected = LocataDataset(tmp_path, tasks=(1,), recordings=(10,), arrays=("dummy",))
    assert len(selected) == 1
    assert selected[0]["metadata"]["recording"] == 10
    assert selected[0]["metadata"]["id"] == "dev/task1/recording10/dummy"
    assert len(LocataDataset(tmp_path, recordings=(99,))) == 0
    with pytest.raises(IndexError):
        selected[1]
    assert selected[-1]["metadata"] == selected[0]["metadata"]


@pytest.mark.parametrize("dtype", [torch.float32, torch.float64])
def test_raw_waveform_and_geometry(make_recording, tmp_path, dtype):
    directory, original = make_recording(channels=3, sources=("speaker10", "speaker2"))
    sample = LocataDataset(tmp_path, dtype=dtype)[0]
    assert sample["waveform"].shape == (3, 10)
    assert sample["waveform"].dtype == dtype
    assert sample["waveform"].device.type == "cpu"
    torch.testing.assert_close(
        sample["waveform"], torch.tensor(original.T.copy(), dtype=dtype), rtol=0, atol=0
    )
    assert sample["sample_rate"] == 1000
    assert sample["array_pose"]["position"].dtype == torch.float64
    assert sample["array_pose"]["microphone_position"].shape == (6, 3, 3)
    assert sample["array_pose"]["microphone_position"][0, 2].tolist() == [30, 31, 32]
    assert list(sample["sources"]) == ["speaker2", "speaker10"]
    assert sample["sources"]["speaker2"]["audio_available"] is True
    assert sample["sources"]["speaker2"]["audio"] is None
    assert sample["metadata"]["path"] == directory


def test_independent_times_fractional_seconds_and_midnight(make_recording, tmp_path):
    make_recording(sources=("talker",))
    sample = LocataDataset(tmp_path, load_source_audio=True)[0]
    assert sample["time_origin"][:5] == (2017, 1, 25, 23, 59)
    assert sample["time_origin"][5] == pytest.approx(59.996)
    assert sample["audio_time"].dtype == torch.float64
    torch.testing.assert_close(
        sample["audio_time"],
        torch.arange(10, dtype=torch.float64) / 1000,
        rtol=0,
        atol=3e-11,
    )
    assert sample["array_pose"]["time"][0] == pytest.approx(-0.004, abs=3e-11)
    assert sample["required_time"]["time"][0] == pytest.approx(-0.004, abs=3e-11)
    assert sample["sources"]["talker"]["pose"]["time"][0] == pytest.approx(
        -0.003, abs=3e-11
    )
    assert sample["sources"]["talker"]["audio"]["audio_time"][0] == pytest.approx(
        -0.002, abs=3e-11
    )
    assert sample["sources"]["talker"]["audio"]["sample_rate"] == 500
    assert sample["required_time"]["valid_flag"].tolist() == [
        True,
        False,
        True,
        True,
        False,
        True,
    ]
    assert sample["array_pose"]["time_origin"] == sample["time_origin"]


def test_missing_optional_and_eval_gt_by_presence(make_recording, tmp_path):
    make_recording(split="eval")
    no_gt = LocataDataset(tmp_path, split="eval")[0]
    assert no_gt["sources"] == {}
    make_recording(
        split="eval", recording=2, sources=("only_pose",), source_audio=False
    )
    sample = LocataDataset(tmp_path, split="eval")[1]
    source = sample["sources"]["only_pose"]
    assert source["pose"] is not None
    assert source["audio"] is None
    assert source["audio_available"] is False
    assert source["vad"] == {"array": None, "source": None}


def test_source_audio_without_pose_and_zero_vad_is_known(make_recording, tmp_path):
    directory, _ = make_recording(sources=("s",), source_pose=False, vad=True)
    (directory / "VAD_dummy_s.txt").write_text("VAD\n" + "0\n" * 10)
    sample = LocataDataset(tmp_path, load_source_audio=True)[0]
    source = sample["sources"]["s"]
    assert source["pose"] is None
    assert source["audio"]["waveform"].shape == (1, 8)
    assert source["vad"]["array"]["values"].tolist() == [False] * 10
    torch.testing.assert_close(
        source["vad"]["source"]["time"], source["audio"]["audio_time"]
    )


def test_missing_wav_is_reported_but_broken_required_is_error(make_recording, tmp_path):
    directory, _ = make_recording()
    missing = directory.parent / "dicit"
    missing.mkdir()
    with pytest.warns(MissingAudioWarning, match="dicit"):
        dataset = LocataDataset(tmp_path)
    assert len(dataset) == 1
    assert dataset.missing_audio == (missing,)
    (directory / "required_time.txt").unlink()
    with pytest.raises(LocataError, match="required_time.txt"):
        LocataDataset(tmp_path, arrays=("dummy",))


@pytest.mark.parametrize(
    "name",
    [
        "required_time.txt",
        "position_array_dummy.txt",
        "audio_array_timestamps_dummy.txt",
    ],
)
def test_corrupt_required_file_has_path(make_recording, tmp_path, name):
    directory, _ = make_recording()
    (directory / name).write_text("bad\nnot a number\n")
    dataset = LocataDataset(tmp_path)
    with pytest.raises(LocataError, match=name):
        dataset[0]


def test_corrupt_wav_has_path(make_recording, tmp_path):
    directory, _ = make_recording()
    (directory / "audio_array_dummy.wav").write_bytes(b"bad wav")
    with pytest.raises(LocataError, match="audio_array_dummy.wav"):
        LocataDataset(tmp_path)


@pytest.mark.parametrize(
    "kind", ["count", "decrease", "bad_date", "nan", "flag", "mic"]
)
def test_invalid_content_is_not_dropped(make_recording, tmp_path, kind):
    directory, _ = make_recording()
    name = "audio_array_timestamps_dummy.txt"
    if kind == "flag":
        name = "required_time.txt"
    elif kind == "mic":
        name = "position_array_dummy.txt"
    path = directory / name
    lines = path.read_text().splitlines()
    if kind == "count":
        lines.pop()
    elif kind == "decrease":
        lines[2] = lines[1]
    elif kind == "bad_date":
        fields = lines[1].split("\t")
        fields[1] = "13"
        lines[1] = "\t".join(fields)
    elif kind == "nan":
        fields = lines[1].split("\t")
        fields[5] = "nan"
        lines[1] = "\t".join(fields)
    elif kind == "flag":
        fields = lines[1].split("\t")
        fields[-1] = "2"
        lines[1] = "\t".join(fields)
    else:
        lines = ["\t".join(row.split("\t")[:-3]) for row in lines]
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(LocataError, match=name):
        LocataDataset(tmp_path)[0]


def test_nan_geometry_and_invalid_rows_are_retained(make_recording, tmp_path):
    directory, _ = make_recording()
    path = directory / "position_array_dummy.txt"
    text = path.read_text().splitlines()
    fields = text[2].split("\t")
    fields[6] = "nan"
    text[2] = "\t".join(fields)
    path.write_text("\n".join(text) + "\n")
    sample = LocataDataset(tmp_path)[0]
    assert len(sample["array_pose"]["time"]) == 6
    assert torch.isnan(sample["array_pose"]["position"][1, 0])


def test_construction_and_windows_do_not_read_payload(
    make_recording, tmp_path, monkeypatch
):
    make_recording(sources=("s",))
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        if path.suffix == ".txt":
            raise AssertionError("TXT must be lazy")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(
        sf.SoundFile, "read", lambda *a, **k: pytest.fail("waveform must be lazy")
    )
    dataset = LocataDataset(tmp_path)
    assert len(dataset.windows(num_samples=4)) == 2


def test_optional_source_audio_is_lazy(make_recording, tmp_path, monkeypatch):
    directory, _ = make_recording(sources=("s",))
    (directory / "audio_source_s.wav").write_bytes(b"unread until requested")
    (directory / "audio_source_timestamps_s.txt").write_text("bad")
    sample = LocataDataset(tmp_path)[0]
    assert sample["sources"]["s"]["audio_available"]
    with pytest.raises(LocataError, match="audio_source_s.wav"):
        LocataDataset(tmp_path, load_source_audio=True)[0]


def test_pickle_and_no_dataset_writes(make_recording, tmp_path):
    make_recording(sources=("s",), vad=True)
    before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")}
    dataset = LocataDataset(tmp_path)
    first = dataset[0]
    restored = pickle.loads(pickle.dumps(dataset))
    torch.testing.assert_close(restored[0]["waveform"], first["waveform"])
    after = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in tmp_path.rglob("*")}
    assert before == after


@pytest.mark.parametrize(
    "kwargs",
    [
        {"split": "bad"},
        {"split": ()},
        {"tasks": (7,)},
        {"tasks": ()},
        {"arrays": ("bad",)},
        {"arrays": ()},
        {"recordings": (0,)},
        {"dtype": torch.int16},
        {"cache_size": -1},
        {"cache_bytes": -1},
    ],
)
def test_invalid_options(tmp_path, kwargs):
    with pytest.raises(ValueError):
        LocataDataset(tmp_path, **kwargs)


def test_missing_root(tmp_path):
    with pytest.raises(LocataError, match="absent"):
        LocataDataset(tmp_path / "absent")


def test_array_vad_alone_identifies_a_source(make_recording, tmp_path):
    make_recording(
        sources=("vad_only",), source_audio=False, source_pose=False, vad=True
    )
    source = LocataDataset(tmp_path)[0]["sources"]["vad_only"]
    assert source["pose"] is None
    assert source["audio"] is None
    assert source["audio_available"] is False
    assert source["vad"]["array"]["values"].numel() == 10
    assert source["vad"]["source"] is None


def test_source_vad_requires_a_source_clock_and_wav(make_recording, tmp_path):
    directory, _ = make_recording()
    (directory / "VAD_source_s.txt").write_text("VAD\n0\n")
    with pytest.raises(LocataError, match="VAD_source_s.txt"):
        LocataDataset(tmp_path)[0]
