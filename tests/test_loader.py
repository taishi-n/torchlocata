import pickle

import pytest
import torch
from torch.utils.data import DataLoader, SequentialSampler, Subset

from locata_torch import LocataDataset, collate_locata


def test_padding_lengths_mask_and_optional_lists(make_recording, tmp_path):
    make_recording(frames=10, recording=1, sources=("s",), vad=True)
    make_recording(frames=3, recording=2)
    dataset = LocataDataset(tmp_path)
    samples = [dataset[0], dataset[1]]
    batch = collate_locata(samples)
    assert batch["waveform"].shape == (2, 2, 10)
    assert batch["lengths"].tolist() == [10, 3]
    assert batch["audio_mask"].dtype == torch.bool
    assert batch["audio_mask"].tolist() == [[True] * 10, [True] * 3 + [False] * 7]
    assert torch.equal(batch["waveform"][1, :, 3:], torch.zeros(2, 7))
    assert isinstance(batch["sources"], list)
    assert batch["sources"][1] == {}
    assert len(batch["audio_time"][1]) == 3
    assert batch["sample_rate"] == 1000
    assert pickle.loads(pickle.dumps(collate_locata)) is collate_locata


@pytest.mark.parametrize("difference", ["array", "rate", "channels", "dtype"])
def test_mixed_batch_errors(make_recording, tmp_path, difference):
    make_recording()
    kwargs = {"recording": 2}
    if difference == "array":
        kwargs["array"] = "dicit"
    elif difference == "rate":
        kwargs["sample_rate"] = 2000
    elif difference == "channels":
        kwargs["channels"] = 3
    make_recording(**kwargs)
    dataset = LocataDataset(tmp_path)
    samples = [dataset[0], dataset[1]]
    if difference == "dtype":
        samples[1]["waveform"] = samples[1]["waveform"].double()
    with pytest.raises(ValueError):
        collate_locata(samples)


def test_empty_batch_error():
    with pytest.raises(ValueError, match="empty"):
        collate_locata([])


@pytest.mark.parametrize("workers", [0, 2])
def test_subset_sampler_shuffle_and_spawn(make_recording, tmp_path, workers):
    make_recording(frames=11, sources=("s",), vad=True)
    dataset = LocataDataset(tmp_path, load_source_audio=True)
    dataset[0]  # Worker serialization must not retain the parent's cache.
    windows = dataset.windows(num_samples=4, hop_samples=3, drop_last=False)
    subset = Subset(windows, [3, 0, 2])
    args = {"multiprocessing_context": "spawn"} if workers else {}
    loader = DataLoader(
        subset,
        batch_size=2,
        num_workers=workers,
        collate_fn=collate_locata,
        sampler=SequentialSampler(subset),
        **args,
    )
    batches = list(loader)
    assert [m["start_frame"] for b in batches for m in b["metadata"]] == [9, 0, 6]
    shuffle = DataLoader(
        subset,
        batch_size=2,
        num_workers=workers,
        collate_fn=collate_locata,
        shuffle=True,
        generator=torch.Generator().manual_seed(5),
        **args,
    )
    assert sorted(m["start_frame"] for b in shuffle for m in b["metadata"]) == [0, 6, 9]
