"""Explicit, bounded-memory installation of the pinned LOCATA release."""

import hashlib
import http.client
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ._storage import (
    ARCHIVES,
    DOI,
    RELEASE,
    Archive,
    data_directory,
    dataset_directory,
    manifest_path,
    read_manifest,
    relative_parts,
    select_splits,
)
from ._tables import LocataError

_CHUNK = 1024 * 1024
_RETRY_DELAY = 1.0
_ATTEMPTS = 3


def _regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise LocataError(f"{path}: expected a regular file, not a symlink")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Commit a small record atomically on the destination filesystem."""
    if path.is_symlink():
        raise LocataError(f"{path}: refusing to replace a symlink")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _check_store(store: Path) -> None:
    if any((store / split).is_dir() for split in ARCHIVES):
        raise LocataError(f"{store}: existing unpacked root cannot be a data_dir")
    for relative in (
        "",
        "archives",
        f"archives/{RELEASE}",
        "datasets",
        f"datasets/{RELEASE}",
        "state",
        f"state/{RELEASE}",
        "staging",
        "locks",
    ):
        path = store / relative
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise LocataError(f"{path}: storage namespace is not a regular directory")


def _space(path: Path, required: int) -> None:
    existing = path
    while not existing.exists():
        existing = existing.parent
    # Include modest filesystem overhead without reserving another full archive.
    needed = required + max(_CHUNK, required // 100)
    if shutil.disk_usage(existing).free < needed:
        raise LocataError(f"{path}: insufficient free space; need {needed} bytes")


def _verify_archive(path: Path, spec: Archive) -> None:
    _regular(path)
    if path.stat().st_size != spec.size:
        raise LocataError(f"{path}: archive size differs from {spec.size} bytes")
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        while chunk := stream.read(_CHUNK):
            digest.update(chunk)
    if digest.hexdigest() != spec.md5:
        raise LocataError(f"{path}: MD5 checksum differs from {spec.md5}")


def _response_offset(response: Any, offset: int, spec: Archive) -> int:
    encoding = response.headers.get("Content-Encoding", "identity").lower()
    if encoding != "identity":
        raise LocataError(f"{spec.url}: unsupported content encoding {encoding!r}")
    if response.status == 200:
        start = 0
    elif response.status == 206:
        expected = f"bytes {offset}-{spec.size - 1}/{spec.size}"
        if response.headers.get("Content-Range") != expected:
            raise LocataError(f"{spec.url}: invalid range; expected {expected!r}")
        start = offset
    else:
        raise LocataError(f"{spec.url}: unexpected HTTP status {response.status}")
    length = response.headers.get("Content-Length")
    if length is not None:
        try:
            valid = int(length) == spec.size - start
        except ValueError:
            valid = False
        if not valid:
            raise LocataError(f"{spec.url}: invalid response size {length!r}")
    return start


class _Truncated(Exception):
    pass


def _transfer(part: Path, spec: Archive) -> None:
    last_error: Exception | None = None
    for attempt in range(_ATTEMPTS):
        offset = part.stat().st_size
        if offset == spec.size:
            return
        if offset > spec.size:
            raise LocataError(f"{part}: partial size exceeds the pinned archive")
        headers = {"Accept-Encoding": "identity", "User-Agent": "locata-torch/0.1"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(spec.url, headers=headers)
        delay = _RETRY_DELAY * (2**attempt)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                start = _response_offset(response, offset, spec)
                written = start
                reported = time.monotonic()
                # A server ignoring Range restarts only our identified partial.
                with part.open("ab" if start else "wb") as stream:
                    while chunk := response.read(_CHUNK):
                        if written + len(chunk) > spec.size:
                            raise LocataError(
                                f"{spec.url}: response exceeds pinned size"
                            )
                        stream.write(chunk)
                        written += len(chunk)
                        if time.monotonic() - reported >= 5:
                            print(
                                f"LOCATA {spec.split}: {written}/{spec.size} bytes",
                                file=sys.stderr,
                            )
                            reported = time.monotonic()
                if written != spec.size:
                    raise _Truncated(f"short/truncated response at {written} bytes")
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                exc.close()
                raise LocataError(
                    f"{spec.url}: HTTP {exc.code}; cannot resume"
                ) from exc
            retry_after = exc.headers.get("Retry-After", "")
            if re.fullmatch(r"\d+", retry_after):
                delay = min(30.0, float(retry_after))
            exc.close()
            last_error = exc
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            ConnectionError,
            TimeoutError,
            _Truncated,
        ) as exc:
            last_error = exc
        if attempt + 1 < _ATTEMPTS:
            print(f"LOCATA {spec.split}: retry after {last_error}", file=sys.stderr)
            time.sleep(delay)
    raise LocataError(
        f"{spec.url}: transfer failed after {_ATTEMPTS} attempts: {last_error}"
    )


def _fetch(store: Path, spec: Archive) -> Path:
    directory = store / "archives" / RELEASE
    archive = directory / f"{spec.split}.zip"
    if archive.exists() or archive.is_symlink():
        _verify_archive(archive, spec)
        return archive
    part = directory / f"{spec.split}.zip.part"
    sidecar = directory / f"{spec.split}.zip.part.json"
    identity = {"release": RELEASE, "source": spec.identity()}
    if sidecar.exists() or sidecar.is_symlink():
        _regular(sidecar)
        if sidecar.stat().st_size > 4096 or json.loads(sidecar.read_text()) != identity:
            raise LocataError(
                f"{sidecar}: partial identity does not match this release"
            )
    elif part.exists() or part.is_symlink():
        raise LocataError(f"{part}: unknown partial file; refusing to overwrite")
    else:
        _write_json(sidecar, identity)
    if part.exists() or part.is_symlink():
        _regular(part)
    else:
        part.touch(exist_ok=False)
    _transfer(part, spec)
    # Read all retained and newly transferred bytes, including a resumed prefix.
    _verify_archive(part, spec)
    part.rename(archive)
    sidecar.unlink()
    return archive


def _zip_inventory(
    archive: zipfile.ZipFile, spec: Archive
) -> tuple[list[zipfile.ZipInfo], dict[str, dict[str, int]], list[str]]:
    members = archive.infolist()
    names: dict[str, tuple[str, bool]] = {}
    explicit: set[str] = set()
    files: dict[str, dict[str, int]] = {}
    directories: set[str] = set()
    for member in members:
        # ZipInfo can replace Windows separators or truncate a NUL-bearing name.
        if member.orig_filename != member.filename:
            raise LocataError(f"{member.orig_filename!r}: unsafe original ZIP name")
        name = member.filename[:-1] if member.is_dir() else member.filename
        parts = relative_parts(name)
        if parts[0] != spec.split or (len(parts) == 1 and not member.is_dir()):
            raise LocataError(f"{name!r}: unexpected archive top-level path")
        kind = stat.S_IFMT(member.external_attr >> 16)
        if (
            kind not in (0, stat.S_IFREG, stat.S_IFDIR)
            or (kind == stat.S_IFDIR and not member.is_dir())
            or (kind == stat.S_IFREG and member.is_dir())
        ):
            raise LocataError(f"{name!r}: unsafe ZIP type or symlink")
        if member.flag_bits & 1:
            raise LocataError(f"{name!r}: encrypted ZIP members are unsupported")
        if name.casefold() in explicit:
            raise LocataError(f"{name!r}: duplicate or case-colliding ZIP destination")
        explicit.add(name.casefold())
        for length in range(1, len(parts) + 1):
            prefix = "/".join(parts[:length])
            is_dir = length < len(parts) or member.is_dir()
            key = prefix.casefold()
            previous = names.get(key)
            if previous is not None and previous != (prefix, is_dir):
                raise LocataError(f"{name!r}: ZIP destination collision")
            names[key] = (prefix, is_dir)
            if length > 1 and is_dir:
                directories.add("/".join(parts[1:length]))
        if not member.is_dir():
            files["/".join(parts[1:])] = {"size": member.file_size, "crc": member.CRC}
    if (
        not files
        or sum(entry["size"] for entry in files.values()) != spec.expanded_size
    ):
        raise LocataError(
            f"{spec.split}: ZIP expanded size differs from pinned metadata"
        )
    return members, files, sorted(directories)


def _extract(archive_path: Path, staging: Path, spec: Archive) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path, allowZip64=True) as archive:
        members, files, directories = _zip_inventory(archive, spec)
        _space(staging, spec.expanded_size)
        for member in members:
            destination = staging.joinpath(*relative_parts(member.filename.rstrip("/")))
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target, _CHUNK)
    return {
        "schema": 1,
        "release": RELEASE,
        "split": spec.split,
        "source": spec.identity(),
        "observed_md5": spec.md5,
        "state": "prepared",
        "staging": staging.name,
        "files": files,
        "directories": directories,
        "doi": DOI,
        "license": {
            "id": "ODC-BY-1.0",
            "url": "https://opendatacommons.org/licenses/by/1-0/",
        },
        "citation": (
            "Evers et al., The LOCATA Challenge: Acoustic Source Localization "
            "and Tracking, dataset v1 (2020). https://doi.org/" + DOI
        ),
    }


def _verify_inventory(root: Path, manifest: dict[str, Any]) -> None:
    if root.is_symlink() or not root.is_dir():
        raise LocataError(f"{root}: installed split is missing or altered")
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise LocataError(f"{path}: altered inventory contains a symlink")
        if path.is_dir():
            directories.add(name)
            continue
        files.add(name)
        entry = manifest["files"].get(name)
        _regular(path)
        if entry is None or path.stat().st_size != entry["size"]:
            raise LocataError(f"{path}: altered file inventory or size")
        crc = 0
        with path.open("rb") as stream:
            while chunk := stream.read(_CHUNK):
                crc = zlib.crc32(chunk, crc)
        if crc != entry["crc"]:
            raise LocataError(f"{path}: installed CRC differs from verified ZIP")
    if files != set(manifest["files"]) or directories != set(manifest["directories"]):
        raise LocataError(f"{root}: altered installation inventory")


def _recover(store: Path, split: str, manifest: dict[str, Any]) -> None:
    target = dataset_directory(store) / split
    stage: Path | None = None
    if manifest["state"] == "prepared":
        name = manifest.get("staging")
        if (
            not isinstance(name, str)
            or len(relative_parts(name)) != 1
            or not name.startswith(f"{RELEASE}-{split}-")
        ):
            raise LocataError(
                f"{manifest_path(store, split)}: invalid staging identity"
            )
        stage = store / "staging" / name
        if stage.is_symlink():
            raise LocataError(f"{stage}: staging directory is a symlink")
    if target.exists() or target.is_symlink():
        _verify_inventory(target, manifest)
    elif stage is not None:
        _verify_inventory(stage / split, manifest)
        (stage / split).rename(target)
    else:
        raise LocataError(f"{target}: completed installation is missing")
    if manifest["state"] == "prepared":
        _write_json(
            manifest_path(store, split),
            {**manifest, "state": "complete", "staging": None},
        )
        # Remove only an empty, recorded staging directory; never arbitrary contents.
        if stage is not None and stage.is_dir() and not any(stage.iterdir()):
            stage.rmdir()


def _install(store: Path, spec: Archive) -> None:
    archive = _fetch(store, spec)
    stage = Path(
        tempfile.mkdtemp(prefix=f"{RELEASE}-{spec.split}-", dir=store / "staging")
    )
    prepared = False
    moved = False
    try:
        manifest = _extract(archive, stage, spec)
        _write_json(manifest_path(store, spec.split), manifest)
        prepared = True
        target = dataset_directory(store) / spec.split
        if target.exists() or target.is_symlink():
            raise LocataError(f"{target}: refusing to overwrite an existing split")
        (stage / spec.split).rename(target)
        moved = True
        _write_json(
            manifest_path(store, spec.split),
            {**manifest, "state": "complete", "staging": None},
        )
    finally:
        if not prepared or moved:
            shutil.rmtree(stage)


def download_locata(
    split: str | Sequence[str] = "dev", *, data_dir: str | Path | None = None
) -> Path:
    """Install dev/eval from the pinned official release and return its root.

    Storage lookup is ``data_dir``, then ``LOCATA_DATA_DIR``, then the platform
    user-data directory. ``LOCATA_ROOT`` does not affect downloads. Each split
    is verified and installed independently. Existing managed data is checked
    and reused; unknown or altered data raises :class:`LocataError`.

    Requires ``locata-torch[download]``. This explicit operation performs network
    I/O; Dataset construction never downloads. Call it before starting workers.
    """
    splits = select_splits(split)
    try:
        from filelock import FileLock, Timeout
    except ImportError as exc:
        raise LocataError(
            'install "locata-torch[download]" to enable downloading'
        ) from exc
    store = data_directory(data_dir)
    try:
        _check_store(store)
        required = 0
        for value in splits:
            manifest = read_manifest(store, value)
            target = dataset_directory(store) / value
            if manifest is None:
                if target.exists() or target.is_symlink():
                    raise LocataError(
                        f"{target}: unknown existing split without a manifest"
                    )
                spec = ARCHIVES[value]
                cached = store / "archives" / RELEASE / f"{value}.zip"
                retained = (
                    spec.size
                    if cached.is_file()
                    and not cached.is_symlink()
                    and cached.stat().st_size == spec.size
                    else 0
                )
                required += spec.size - retained + spec.expanded_size
        if required:
            _space(store, required)
        for relative in (
            f"archives/{RELEASE}",
            f"datasets/{RELEASE}",
            f"state/{RELEASE}",
            "staging",
            "locks",
        ):
            (store / relative).mkdir(parents=True, exist_ok=True)
        for value in splits:
            lock_path = store / "locks" / f"{RELEASE}-{value}.lock"
            if lock_path.is_symlink():
                raise LocataError(f"{lock_path}: lock file is a symlink")
            with FileLock(lock_path, timeout=60):
                _check_store(store)
                manifest = read_manifest(store, value)
                if manifest is not None:
                    _recover(store, value, manifest)
                else:
                    target = dataset_directory(store) / value
                    if target.exists() or target.is_symlink():
                        raise LocataError(f"{target}: unknown existing split")
                    _install(store, ARCHIVES[value])
        return dataset_directory(store)
    except (OSError, ValueError, zipfile.BadZipFile, Timeout) as exc:
        raise LocataError(f"{store}: LOCATA installation failed: {exc}") from exc
