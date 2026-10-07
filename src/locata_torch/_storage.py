"""Pinned release metadata and read-only path resolution."""

import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from platformdirs import user_data_path

from ._tables import LocataError

RELEASE = "zenodo-3630471"
DOI = "10.5281/zenodo.3630471"


@dataclass(frozen=True)
class Archive:
    """An exact official archive, independent of the Python package version."""

    split: str
    url: str
    size: int
    md5: str
    expanded_size: int

    def identity(self) -> dict[str, str | int]:
        return {"url": self.url, "bytes": self.size, "md5": self.md5}


ARCHIVES = {
    "dev": Archive(
        "dev",
        "https://zenodo.org/api/records/3630471/files/dev.zip/content",
        6207354195,
        "d5a5417c3f6b2ed0e43581dd06f504e6",
        27136519350,
    ),
    "eval": Archive(
        "eval",
        "https://zenodo.org/api/records/3630471/files/eval.zip/content",
        13045105034,
        "46709713350bc16c106e788920d30a8b",
        57426914435,
    ),
}


def select_splits(split: str | Sequence[str]) -> tuple[str, ...]:
    values = (split,) if isinstance(split, str) else tuple(split)
    if not values or any(value not in ARCHIVES for value in values):
        raise ValueError("split must select dev and/or eval")
    return tuple(sorted(set(values)))


def _configured_path(value: str | Path, label: str) -> Path:
    if isinstance(value, str) and not value.strip():
        raise LocataError(f"{label}: path must not be empty")
    return Path(value).expanduser().resolve()


def data_directory(data_dir: str | Path | None = None) -> Path:
    """Resolve persistent storage without creating it."""
    if data_dir is not None:
        return _configured_path(data_dir, "data_dir")
    if "LOCATA_DATA_DIR" in os.environ:
        return _configured_path(os.environ["LOCATA_DATA_DIR"], "LOCATA_DATA_DIR")
    return user_data_path(
        "locata-torch", appauthor=False, ensure_exists=False
    ).resolve()


def dataset_directory(store: Path) -> Path:
    return store / "datasets" / RELEASE


def manifest_path(store: Path, split: str) -> Path:
    return store / "state" / RELEASE / f"{split}.json"


def relative_parts(name: str) -> tuple[str, ...]:
    """Accept portable relative member paths without normalizing unsafe input."""
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or ":" in name
        or PurePosixPath(name).is_absolute()
        or PureWindowsPath(name).drive
        or any(part in ("", ".", "..") for part in name.split("/"))
        or any(
            part.endswith((".", " "))
            or any(ord(character) < 32 or character in '<>"|?*' for character in part)
            or re.fullmatch(
                r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", part.split(".")[0], re.I
            )
            for part in name.split("/")
        )
    ):
        raise LocataError(f"unsafe archive or inventory path: {name!r}")
    return tuple(name.split("/"))


def read_manifest(store: Path, split: str) -> dict[str, Any] | None:
    path = manifest_path(store, split)
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("manifest is a symlink or exceeds 2 MiB")
        data = json.loads(path.read_text())
        if (
            not isinstance(data, dict)
            or data.get("schema") != 1
            or data.get("release") != RELEASE
            or data.get("split") != split
            or data.get("source") != ARCHIVES[split].identity()
            or data.get("observed_md5") != ARCHIVES[split].md5
            or data.get("state") not in ("prepared", "complete")
            or not isinstance(data.get("files"), dict)
            or not data["files"]
            or not isinstance(data.get("directories"), list)
        ):
            raise ValueError("incompatible or incomplete installation manifest")
        for name, entry in data["files"].items():
            relative_parts(name)
            if not isinstance(entry, dict) or any(
                type(entry.get(key)) is not int or entry[key] < 0
                for key in ("size", "crc")
            ):
                raise ValueError("invalid file inventory")
            if entry["crc"] > 0xFFFFFFFF:
                raise ValueError("invalid CRC32 inventory")
        for name in data["directories"]:
            relative_parts(name)
        return data
    except (OSError, ValueError, TypeError, LocataError) as exc:
        raise LocataError(f"{path}: invalid manifest: {exc}") from exc


def resolve_root(
    root: str | Path | None = None, splits: Sequence[str] = ("dev",)
) -> Path:
    """Resolve and validate a reader root, without network or filesystem writes."""
    if root is not None:
        selected = _configured_path(root, "root")
        label = "root"
    elif "LOCATA_ROOT" in os.environ:
        selected = _configured_path(os.environ["LOCATA_ROOT"], "LOCATA_ROOT")
        label = "LOCATA_ROOT"
    else:
        store = data_directory()
        selected = dataset_directory(store)
        for split in splits:
            state = read_manifest(store, split)
            if (
                state is None
                or state["state"] != "complete"
                or not (selected / split).is_dir()
                or (selected / split).is_symlink()
            ):
                raise LocataError(
                    f"{selected / split}: managed split is not complete; "
                    f"run locata-torch download --split {split}"
                )
        label = "managed root"
    if not selected.is_dir():
        raise LocataError(f"{selected}: {label} is not a dataset root directory")
    return selected
