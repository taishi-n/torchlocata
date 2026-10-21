"""Optional figures based on LOCATA plot_results.m and measures.m plot sections.

Figures are returned without display or output side effects. See NOTICE and the
analysis guide for MATLAB provenance and the explicit inclination convention.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import torch

from .analysis_types import DOATrack, EvaluationResult, GroundTruth
from .evaluation import validate_tracks
from .types import LocataSample

if TYPE_CHECKING:
    from matplotlib.figure import Figure


def _figure(*, height: float = 6, width: float = 9) -> Figure:
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError as exc:
        raise ImportError("install locata-torch[plot] to use plotting") from exc
    figure = Figure(figsize=(width, height), layout="constrained")
    FigureCanvasAgg(figure)
    return figure


def plot_scene(sample: LocataSample) -> Figure:
    """Return a world-coordinate scene figure with trajectories and numbered mics."""
    figure = _figure(width=13)
    figure.set_layout_engine(None)
    figure.subplots_adjust(left=0.02, right=0.92, top=0.91, bottom=0.08, wspace=0.14)
    axis = figure.add_subplot(121, projection="3d")
    mic_axis = figure.add_subplot(122, projection="3d")
    position = sample["array_pose"]["position"].numpy()
    axis.plot(
        position[:, 0],
        position[:, 1],
        position[:, 2],
        "o-",
        markersize=2,
        label="array",
    )
    for source_id, source in sample["sources"].items():
        if source["pose"] is not None:
            xyz = source["pose"]["position"].numpy()
            axis.plot(
                xyz[:, 0], xyz[:, 1], xyz[:, 2], "x-", markersize=3, label=source_id
            )
    microphones = sample["array_pose"]["microphone_position"]
    if len(microphones):
        for index, xyz in enumerate(microphones[0].tolist(), 1):
            axis.scatter(xyz[0], xyz[1], xyz[2], color="0.35")
            mic_axis.scatter(xyz[0], xyz[1], xyz[2], color="0.35")
            mic_axis.text(xyz[0], xyz[1], xyz[2], str(index))
    axis.set(
        xlabel="x [m]",
        ylabel="y [m]",
        zlabel="z [m]",
        title="Scene (world coordinates)",
    )
    mic_axis.set(
        xlabel="x [m]",
        ylabel="y [m]",
        zlabel="z [m]",
        title="Microphones at first pose (world; WAV channel numbers)",
    )
    axis.legend()
    return figure


def plot_doa(truth: GroundTruth, tracks: Sequence[DOATrack] = ()) -> Figure:
    """Return azimuth/inclination versus time, preserving missing-data gaps."""
    validate_tracks(tracks)
    figure = _figure()
    axes = figure.subplots(2, 1, sharex=True)
    for source_id, source in truth["sources"].items():
        if source["doa"] is not None:
            for axis, name in zip(axes, ("azimuth", "inclination"), strict=True):
                axis.plot(
                    truth["time"],
                    torch.rad2deg(source["doa"][name]),
                    label=f"GT {source_id}",
                )
    for track in tracks:
        if track["time_origin"] != truth["time_origin"]:
            raise ValueError("track and ground-truth origins must match for plotting")
        for axis, name in zip(axes, ("azimuth", "inclination"), strict=True):
            values = track[name]
            if values is not None:
                axis.plot(track["time"], torch.rad2deg(values), ".", label=track["id"])
    axes[0].set(ylabel="Azimuth from +y [deg]", ylim=(-180, 180))
    axes[1].set(
        ylabel="Inclination from +z [deg]", ylim=(0, 180), xlabel="Relative time [s]"
    )
    for axis in axes:
        axis.grid(True)
        if axis.lines:
            axis.legend()
    return figure


def plot_evaluation(result: EvaluationResult) -> Figure:
    """Return activity, angular-error, miss, false-track, swap, and OSPA panels."""
    figure = _figure(height=12)
    axes = figure.subplots(6, 1, sharex=True)
    time = result["time"]
    for column, source_id in enumerate(result["source_ids"]):
        axes[0].step(time, result["activity"][:, column], where="post", label=source_id)
        axes[1].plot(
            time, torch.rad2deg(result["azimuth_error"][:, column]), label=source_id
        )
    axes[2].step(time, result["missed"].sum(dim=1), where="post")
    axes[3].step(time, result["false_tracks"], where="post")
    axes[4].step(time, result["track_swaps"].sum(dim=1), where="post")
    for column, order in enumerate(result["config"].ospa_orders):
        axes[5].plot(time, result["ospa"][:, column], label=f"p={order:g}")
    for axis, label in zip(
        axes,
        (
            "Voice activity",
            "Azimuth error [deg]",
            "Missed sources",
            "False tracks",
            "Track swaps",
            "OSPA [deg]",
        ),
        strict=True,
    ):
        axis.set_ylabel(label)
        axis.grid(True)
    axes[-1].set_xlabel("Relative time [s]")
    axes[0].legend()
    axes[-1].legend()
    return figure
