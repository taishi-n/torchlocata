"""Exercise an installed distribution with a tiny, temporary LOCATA recording."""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from torch.utils.data import DataLoader

import locata_torch
from locata_torch import LocataDataset, collate_locata


def _fixture(root: Path) -> np.ndarray:
    directory = root / "dev/task1/recording1/dummy"
    directory.mkdir(parents=True)
    waveform = np.arange(20, dtype=np.float64).reshape(10, 2) / 7
    sf.write(directory / "audio_array_dummy.wav", waveform, 1000, subtype="DOUBLE")
    header = "year\tmonth\tday\thour\tminute\tsecond"
    clock = "".join(
        f"2017\t1\t25\t15\t40\t{25.068 + i / 1000:.3f}\n" for i in range(10)
    )
    (directory / "audio_array_timestamps_dummy.txt").write_text(header + "\n" + clock)
    columns = ["x", "y", "z"] + [f"ref_vec_{axis}" for axis in "xyz"]
    columns += [f"rotation_{i}{j}" for i in range(1, 4) for j in range(1, 4)]
    columns += [f"mic{i}_{axis}" for i in (1, 2) for axis in "xyz"]
    pose = [0, 0, 0, 0, 1, 0] + np.eye(3).reshape(-1).tolist() + [0, 0, 0, 1, 0, 0]
    (directory / "position_array_dummy.txt").write_text(
        header
        + "\t"
        + "\t".join(columns)
        + "\n"
        + "2017\t1\t25\t15\t40\t25.064\t"
        + "\t".join(map(str, pose))
        + "\n"
    )
    (directory / "required_time.txt").write_text(
        header + "\tvalid_flag\n2017\t1\t25\t15\t40\t25.064\t0\n"
    )
    return waveform


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    module = Path(locata_torch.__file__).resolve()
    if module.is_relative_to(project / "src"):
        raise RuntimeError(f"smoke test imported the checkout: {module}")
    with tempfile.TemporaryDirectory(prefix="locata-consumer-") as temporary:
        root = Path(temporary)
        expected = _fixture(root)
        dataset = LocataDataset(root, dtype=torch.float64)
        sample = dataset[0]
        torch.testing.assert_close(sample["waveform"], torch.from_numpy(expected.T))
        assert abs(float(sample["array_pose"]["time"][0]) + 0.004) < 1e-12
        assert sample["sources"] == {}
        windows = dataset.windows(num_samples=4, hop_samples=3, drop_last=False)
        loader = DataLoader(
            windows,
            batch_size=3,
            collate_fn=collate_locata,
            num_workers=args.workers,
            multiprocessing_context="spawn" if args.workers else None,
        )
        batches = list(loader)
        assert sum(len(batch["lengths"]) for batch in batches) == len(windows)
        assert batches[-1]["lengths"].tolist() == [1]
        cli = Path(sys.executable).parent / (
            "locata-torch.exe" if sys.platform == "win32" else "locata-torch"
        )
        resolved = subprocess.check_output(
            [str(cli), "path", "--root", str(root)], text=True
        )
        assert resolved.strip() == str(root.resolve())
        help_text = subprocess.check_output([str(cli), "--help"], text=True)
        assert "download" in help_text
    print(f"Installed consumer passed: {module}, spawn workers={args.workers}")


if __name__ == "__main__":
    main()
