import pytest
import torch
from conftest import write_pose

from locata_torch import LocataDataset, LocataError


def test_duplicate_pose_times_preserve_every_row(make_recording, tmp_path):
    directory, _ = make_recording(sources=("s",), source_audio=False)
    write_pose(directory / "position_source_s.txt", [-0.003, 0.001, 0.001, 0.009])
    write_pose(
        directory / "position_array_dummy.txt",
        [-0.004, 0, 0.004, 0.004, 0.008, 0.01],
        2,
    )
    sample = LocataDataset(tmp_path)[0]
    assert len(sample["sources"]["s"]["pose"]["time"]) == 4
    assert (
        sample["sources"]["s"]["pose"]["time"][1]
        == sample["sources"]["s"]["pose"]["time"][2]
    )
    window = LocataDataset(tmp_path).windows(num_samples=4)[1]
    torch.testing.assert_close(
        window["array_pose"]["time"],
        torch.full((2,), 0.004, dtype=torch.float64),
        rtol=0,
        atol=1e-12,
    )


def test_backwards_pose_times_are_not_sorted_or_dropped(make_recording, tmp_path):
    directory, _ = make_recording(sources=("s",), source_audio=False)
    write_pose(directory / "position_source_s.txt", [0.001, -0.003])
    with pytest.raises(LocataError, match="position_source_s.txt"):
        LocataDataset(tmp_path)[0]
