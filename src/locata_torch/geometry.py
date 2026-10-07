"""Explicit LOCATA coordinate operations, without temporal interpolation."""

import math

import torch
from torch import Tensor

from .types import DOA, Pose


def world_to_array(
    source_position: Tensor, array_position: Tensor, array_rotation: Tensor
) -> Tensor:
    """Apply R.T @ (h - p) to simultaneous, broadcastable Cartesian positions.

    Args:
        source_position: World xyz in metres, with trailing shape `[3]`.
        array_position: Array origin in world metres, with trailing shape `[3]`.
        array_rotation: Local-to-world rotation with trailing shape `[3, 3]`.

    Returns:
        Float64 array-frame vectors with broadcast leading dimensions.

    Raises:
        ValueError: Shapes, finiteness, or proper-rotation checks fail.
    """
    if (
        source_position.shape[-1:] != (3,)
        or array_position.shape[-1:] != (3,)
        or array_rotation.shape[-2:] != (3, 3)
    ):
        raise ValueError("position shape must end in 3 and rotation shape in (3, 3)")
    h, p, rotation = (
        tensor.to(dtype=torch.float64)
        for tensor in (source_position, array_position, array_rotation)
    )
    if not all(bool(torch.isfinite(tensor).all()) for tensor in (h, p, rotation)):
        raise ValueError("geometry must be finite")
    identity = torch.eye(3, dtype=torch.float64, device=rotation.device)
    if not torch.allclose(
        rotation.transpose(-1, -2) @ rotation,
        identity.expand_as(rotation),
        atol=1e-5,
        rtol=1e-5,
    ) or not torch.allclose(
        torch.linalg.det(rotation),
        torch.ones_like(torch.linalg.det(rotation)),
        atol=1e-5,
        rtol=1e-5,
    ):
        raise ValueError("rotation must be an orthonormal matrix with determinant +1")
    try:
        return (rotation.transpose(-1, -2) @ (h - p).unsqueeze(-1)).squeeze(-1)
    except RuntimeError as exc:
        raise ValueError(
            "geometry shapes must be broadcastable on the same device"
        ) from exc


def locata_doa(array_pose: Pose, source_pose: Pose) -> DOA:
    """Derive angles only for poses sharing exactly the same origin and times.

    Args:
        array_pose: Array world position and local-to-world rotation.
        source_pose: Source world position at exactly matching timestamps.

    Returns:
        Float64 vectors in metres, azimuth in `[-pi, pi)` measured from +y,
        inclination in `[0, pi]` measured from +z, and range in metres.
        Angles use radians; no temporal interpolation is performed.

    Raises:
        ValueError: Clocks or shapes differ, geometry is invalid, or distance
            is zero.
    """
    if array_pose["time_origin"] != source_pose["time_origin"]:
        raise ValueError("pose time origins must match")
    if not torch.equal(array_pose["time"], source_pose["time"]):
        raise ValueError("pose times must match exactly; align them explicitly")
    rows = len(array_pose["time"])
    if (
        array_pose["position"].shape != (rows, 3)
        or source_pose["position"].shape != (rows, 3)
        or array_pose["rotation"].shape != (rows, 3, 3)
    ):
        raise ValueError("pose shape must match its time rows")
    vector = world_to_array(
        source_pose["position"], array_pose["position"], array_pose["rotation"]
    )
    distance = torch.linalg.vector_norm(vector, dim=-1)
    if (distance == 0).any():
        raise ValueError("DOA is undefined at zero distance")
    azimuth = torch.atan2(vector[:, 1], vector[:, 0]) - math.pi / 2
    return {
        "vector": vector,
        "azimuth": torch.remainder(azimuth + math.pi, 2 * math.pi) - math.pi,
        "inclination": torch.acos((vector[:, 2] / distance).clamp(-1, 1)),
        "range": distance,
    }
