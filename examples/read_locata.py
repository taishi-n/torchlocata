"""Print one LOCATA window batch. Safe to launch with spawn workers."""

import argparse

from torch.utils.data import DataLoader

from locata_torch import LocataDataset, collate_locata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--split", choices=("dev", "eval"), default="dev")
    parser.add_argument(
        "--array",
        choices=("benchmark2", "dicit", "dummy", "eigenmike"),
        default="eigenmike",
    )
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--source-audio", action="store_true")
    args = parser.parse_args()
    dataset = LocataDataset(
        args.root,
        split=args.split,
        arrays=(args.array,),
        load_source_audio=args.source_audio,
    )
    windows = dataset.windows(num_samples=48000, hop_samples=24000, drop_last=False)
    if not windows:
        parser.error("no array WAVs match this selection")
    loader = DataLoader(
        windows,
        batch_size=4,
        shuffle=True,
        num_workers=args.workers,
        collate_fn=collate_locata,
        multiprocessing_context="spawn" if args.workers else None,
    )
    # The iterator owns the workers; release it after this one-batch example.
    iterator = iter(loader)
    batch = next(iterator)
    del iterator
    print("waveform:", tuple(batch["waveform"].shape))
    print("sample rate:", batch["sample_rate"])
    print("lengths:", batch["lengths"].tolist())
    for metadata, sources in zip(batch["metadata"], batch["sources"], strict=True):
        print(
            metadata["id"],
            "frames",
            (metadata["start_frame"], metadata["stop_frame"]),
            "sources",
            list(sources),
        )


if __name__ == "__main__":
    main()
