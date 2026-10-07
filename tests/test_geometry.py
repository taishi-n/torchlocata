import math

import pytest
import torch

from locata_torch import locata_doa, world_to_array


def pose(position, rotation=None, time=None):
    position = torch.tensor(position, dtype=torch.float64)
    n = len(position)
    return {
        "time": torch.arange(n, dtype=torch.float64) if time is None else time,
        "time_origin": (2017, 1, 25, 0, 0, 0.0),
        "position": position,
        "ref_vec": torch.tensor([[0.0, 1.0, 0.0]] * n, dtype=torch.float64),
        "rotation": torch.eye(3, dtype=torch.float64).expand(n, 3, 3)
        if rotation is None
        else rotation,
    }


def test_nontrivial_world_to_array_rotation():
    rotation = torch.tensor([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=torch.float64)
    p = torch.tensor([3.0, 4, 5], dtype=torch.float64)
    h = p + rotation @ torch.tensor([1.0, 2, 3], dtype=torch.float64)
    torch.testing.assert_close(
        world_to_array(h, p, rotation), torch.tensor([1.0, 2, 3], dtype=torch.float64)
    )


def test_doa_axes_wrap_and_inclination():
    directions = [[0, 1, 0], [1, 0, 0], [-1, 0, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
    result = locata_doa(pose([[0, 0, 0]] * 6), pose(directions))
    torch.testing.assert_close(
        result["azimuth"],
        torch.tensor(
            [0, -math.pi / 2, math.pi / 2, -math.pi, -math.pi / 2, -math.pi / 2],
            dtype=torch.float64,
        ),
    )
    torch.testing.assert_close(
        result["inclination"],
        torch.tensor([math.pi / 2] * 4 + [0, math.pi], dtype=torch.float64),
    )
    torch.testing.assert_close(result["range"], torch.ones(6, dtype=torch.float64))
    near = locata_doa(pose([[0, 0, 0]] * 2), pose([[1e-6, -1, 0], [-1e-6, -1, 0]]))
    assert near["azimuth"][0] < -3
    assert near["azimuth"][1] > 3


def test_pose_rotation_and_alignment_contract():
    rotation = torch.tensor([[[0.0, -1, 0], [1, 0, 0], [0, 0, 1]]], dtype=torch.float64)
    array = pose([[3, 4, 5]], rotation=rotation)
    source = pose([[2, 4, 5]])
    assert locata_doa(array, source)["azimuth"].item() == pytest.approx(0)
    source["time"] += 0.004
    with pytest.raises(ValueError, match="time"):
        locata_doa(array, source)
    source["time"] = array["time"]
    source["time_origin"] = (2018, 1, 25, 0, 0, 0.0)
    with pytest.raises(ValueError, match="origin"):
        locata_doa(array, source)


def test_undefined_or_invalid_geometry():
    with pytest.raises(ValueError, match="distance"):
        locata_doa(pose([[0, 0, 0]]), pose([[0, 0, 0]]))
    with pytest.raises(ValueError, match="finite"):
        locata_doa(pose([[0, 0, 0]]), pose([[float("nan"), 1, 0]]))
    with pytest.raises(ValueError, match="rotation"):
        world_to_array(torch.zeros(3), torch.zeros(3), torch.ones(3, 3))
    with pytest.raises(ValueError, match="shape"):
        world_to_array(torch.zeros(2), torch.zeros(3), torch.eye(3))
