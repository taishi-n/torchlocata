"""Optional, read-only analysis on the explicitly selected existing corpus."""

import os
from pathlib import Path

import pytest
import torch

from locata_torch import (
    LocataDataset,
    MusicConfig,
    evaluate_locata,
    music_localize,
    prepare_ground_truth,
    read_results,
    write_results,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "task,array",
    [
        (1, "benchmark2"),
        (2, "dicit"),
        (3, "dummy"),
        (4, "eigenmike"),
        (5, "eigenmike"),
        (6, "benchmark2"),
    ],
)
def test_real_analysis_clock_activity_and_storage(task, array, tmp_path):
    value = os.environ.get("LOCATA_ROOT")
    if not value:
        pytest.skip("set LOCATA_ROOT explicitly for real-data analysis")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        pytest.fail("LOCATA_ROOT does not exist")
    dataset = LocataDataset(
        root, split="eval", tasks=(task,), recordings=(1,), arrays=(array,)
    )
    if not dataset:
        pytest.skip("selected representative recording is not in this snapshot")
    windows = dataset.windows(num_samples=48000, drop_last=False)
    sample = windows[len(windows) // 2]
    before = {
        p: (p.stat().st_size, p.stat().st_mtime_ns)
        for p in dataset.index[0].path.iterdir()
        if p.is_file()
    }
    truth = prepare_ground_truth(sample)
    config = MusicConfig(
        azimuth_degrees=tuple(float(x) for x in range(-180, 181, 30)),
        inclination_degrees=(30.0, 60.0, 90.0, 120.0, 150.0),
    )
    estimate = music_localize(sample, config=config)
    torch.testing.assert_close(estimate["track"]["time"], truth["time"])
    assert torch.isfinite(estimate["block_azimuth"]).any()
    complete = bool(truth["sources"]) and all(
        source["doa"] is not None
        and source["activity"] is not None
        and torch.isfinite(source["activity"]).all()
        for source in truth["sources"].values()
    )
    if complete:
        oracle = []
        for source_id, source in truth["sources"].items():
            oracle.append(
                {
                    "id": source_id,
                    "time": truth["time"],
                    "time_origin": truth["time_origin"],
                    "azimuth": torch.where(
                        source["activity"].bool(), source["doa"]["azimuth"], torch.nan
                    ),
                    "inclination": source["doa"]["inclination"],
                }
            )
        perfect = evaluate_locata(truth, oracle)
        assert perfect["metrics"]["azimuth_error_degrees"]["value"] in (None, 0.0)
        assert not perfect["false_tracks"].any()
        result = evaluate_locata(truth, [estimate["track"]])
        write_results(
            [result],
            tmp_path / "results",
            corpus_roots=(root,),
            include_frame_arrays=True,
        )
        assert len(read_results(tmp_path / "results").frames) == 1
    else:
        with pytest.raises(ValueError, match="GT|ground truth|VAD|activity"):
            evaluate_locata(truth, [])
    assert before == {
        p: (p.stat().st_size, p.stat().st_mtime_ns)
        for p in dataset.index[0].path.iterdir()
        if p.is_file()
    }
