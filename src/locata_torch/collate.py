"""Homogeneous audio batches with ragged, unmodified annotation lists."""

from collections.abc import Sequence

import torch

from .types import LocataBatch, LocataSample


def collate_locata(samples: Sequence[LocataSample]) -> LocataBatch:
    """Right-pad audio; retain annotations and optional sources per sample.

    Args:
        samples: Nonempty samples sharing array, sample rate, channels, and dtype.

    Returns:
        CPU audio `[B, C, T_max]`, int64 lengths, a boolean padding-only mask,
        and lists of unmodified clocks, annotations, sources, and metadata.

    Raises:
        ValueError: Samples are empty, heterogeneous, or have non-CPU waveforms.
    """
    if not samples:
        raise ValueError("cannot collate an empty batch")
    first = samples[0]
    waveform = first["waveform"]
    signature = (
        first["metadata"]["array"],
        first["sample_rate"],
        waveform.shape[0],
        waveform.dtype,
    )
    for sample in samples:
        audio = sample["waveform"]
        if audio.ndim != 2 or audio.device.type != "cpu":
            raise ValueError("waveform must be a CPU tensor [channels, samples]")
        if (
            sample["metadata"]["array"],
            sample["sample_rate"],
            audio.shape[0],
            audio.dtype,
        ) != signature:
            raise ValueError(
                "batch must share array, sample rate, channel count and dtype"
            )
    lengths = torch.tensor([s["waveform"].shape[1] for s in samples], dtype=torch.int64)
    maximum = int(lengths.max())
    padded = waveform.new_zeros(len(samples), waveform.shape[0], maximum)
    for row, sample in enumerate(samples):
        padded[row, :, : sample["waveform"].shape[1]] = sample["waveform"]
    return {
        "waveform": padded,
        "lengths": lengths,
        "audio_mask": torch.arange(maximum).unsqueeze(0) < lengths.unsqueeze(1),
        "sample_rate": first["sample_rate"],
        "audio_time": [s["audio_time"] for s in samples],
        "time_origin": [s["time_origin"] for s in samples],
        "required_time": [s["required_time"] for s in samples],
        "array_pose": [s["array_pose"] for s in samples],
        "sources": [s["sources"] for s in samples],
        "metadata": [s["metadata"] for s in samples],
    }
