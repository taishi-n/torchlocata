"""Analyze one full recording and save results outside the read-only corpus."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from locata_torch import (
    LocataDataset,
    MusicConfig,
    aggregate_results,
    evaluate_locata,
    music_localize,
    plot_doa,
    plot_evaluation,
    plot_scene,
    prepare_ground_truth,
    read_results,
    write_results,
    write_submission,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--split", choices=("dev", "eval"), default="eval")
    parser.add_argument("--task", type=int, default=1)
    parser.add_argument("--recording", type=int, default=1)
    parser.add_argument("--array", default="benchmark2")
    parser.add_argument("--coarse-grid", action="store_true")
    parser.add_argument("--corpus-release", default="unspecified")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    dataset = LocataDataset(
        args.root,
        split=args.split,
        tasks=(args.task,),
        recordings=(args.recording,),
        arrays=(args.array,),
    )
    if not dataset:
        parser.error("no recording matches the selection")
    sample = dataset[0]
    config = (
        MusicConfig(
            azimuth_degrees=tuple(float(x) for x in range(-180, 181, 30)),
            inclination_degrees=(30.0, 60.0, 90.0, 120.0, 150.0),
        )
        if args.coarse_grid
        else MusicConfig()
    )
    estimate = music_localize(sample, config=config)
    tracks = [estimate["track"]]
    truth = (
        prepare_ground_truth(sample, time_bounds=sample["metadata"]["time_bounds"])
        if args.evaluate or args.plot
        else None
    )
    result = (
        evaluate_locata(truth, tracks) if args.evaluate and truth is not None else None
    )
    write_submission(
        tracks,
        args.output / "submission",
        required_time=sample["required_time"],
        corpus_roots=(dataset.root,),
        elapsed_seconds=estimate["elapsed_seconds"],
    )
    if result is not None:
        write_results(
            [result],
            args.output / "results",
            corpus_roots=(dataset.root,),
            include_frame_arrays=True,
            provenance={
                "algorithm": "reference-single-source-MUSIC",
                "corpus_release": args.corpus_release,
                "music_config": asdict(config),
            },
        )
        summary = aggregate_results(
            read_results(args.output / "results"),
            group_by=("split", "task", "array"),
            weighting="pooled",
        )
        print(json.dumps(summary, indent=2, allow_nan=False))
    if args.plot:
        assert truth is not None
        plot_scene(sample).savefig(args.output / "scene.png")
        plot_doa(truth, tracks).savefig(args.output / "doa.png")
        if result is not None:
            plot_evaluation(result).savefig(args.output / "evaluation.png")


if __name__ == "__main__":
    main()
