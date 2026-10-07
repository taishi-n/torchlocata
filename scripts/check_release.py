"""Validate release routing, distribution metadata, contents, and hashes."""

import argparse
import hashlib
import re
import tarfile
import zipfile
from email.parser import BytesParser
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import Version


def release_index(package_version: str, tag: str | None) -> str:
    """Return pypi/testpypi only for an exact, matching stable/RC tag."""
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:rc[1-9]\d*)?", package_version):
        raise ValueError(f"unsupported release version: {package_version!r}")
    parsed = Version(package_version)
    if str(parsed) != package_version:
        raise ValueError(f"version is not canonical: {package_version!r}")
    if not tag:
        return ""
    if tag != f"v{package_version}":
        raise ValueError(f"tag {tag!r} does not match version {package_version!r}")
    return "testpypi" if parsed.is_prerelease else "pypi"


def _check_members(names: list[str]) -> None:
    for name in names:
        parts = PurePosixPath(name).parts
        if (
            name.startswith("/")
            or ".." in parts
            or set(parts) & {"site", ".venv", ".cache", "__pycache__", ".git"}
            or PurePosixPath(name).suffix.lower() in {".wav", ".zip", ".pdf", ".pyc"}
        ):
            raise ValueError(f"excluded distribution asset: {name}")


def _metadata(raw: bytes, expected_version: str) -> None:
    metadata = BytesParser().parsebytes(raw)
    if (
        canonicalize_name(metadata.get("Name", "")) != "locata-torch"
        or metadata.get("Version") != expected_version
    ):
        raise ValueError("distribution name/version differs from the project")
    if metadata.get("Requires-Python") != ">=3.10":
        raise ValueError("distribution requires the wrong Python range")
    if metadata.get("License-Expression") != "Apache-2.0" or metadata.get_all(
        "License-File"
    ) != ["LICENSE"]:
        raise ValueError("distribution license metadata is incomplete")
    requirements = [
        Requirement(value) for value in metadata.get_all("Requires-Dist", [])
    ]
    base = {
        canonicalize_name(req.name)
        for req in requirements
        if req.marker is None or req.marker.evaluate({"extra": ""})
    }
    download = {
        canonicalize_name(req.name)
        for req in requirements
        if req.marker is None or req.marker.evaluate({"extra": "download"})
    }
    if (
        base != {"torch", "numpy", "soundfile", "platformdirs"}
        or download != base | {"filelock"}
        or metadata.get_all("Provides-Extra") != ["download"]
    ):
        raise ValueError("distribution runtime/download dependencies are incorrect")


def check_distributions(dist: Path, expected_version: str) -> tuple[Path, Path]:
    """Inspect exactly one pure-Python wheel and one matching source archive."""
    wheels, sdists = sorted(dist.glob("*.whl")), sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError(f"{dist}: expected exactly one wheel and one sdist")
    wheel, sdist = wheels[0], sdists[0]
    name, parsed, _, tags = parse_wheel_filename(wheel.name)
    if (
        name != "locata-torch"
        or str(parsed) != expected_version
        or {str(tag) for tag in tags} != {"py3-none-any"}
        or parse_sdist_filename(sdist.name) != (name, parsed)
    ):
        raise ValueError("distribution filenames/tags differ from project version")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        _check_members(names)
        info = f"locata_torch-{expected_version}.dist-info"
        for required in ("locata_torch/py.typed", f"{info}/licenses/LICENSE"):
            if required not in names:
                raise ValueError(f"wheel missing {required}")
        _metadata(archive.read(f"{info}/METADATA"), expected_version)
        entry_points = archive.read(f"{info}/entry_points.txt").decode()
        if "locata-torch = locata_torch.cli:main" not in entry_points:
            raise ValueError("wheel is missing its CLI entry point")
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        _check_members(names)
        root = sdist.name.removesuffix(".tar.gz")
        for required in ("LICENSE", "pyproject.toml", "src/locata_torch/py.typed"):
            if f"{root}/{required}" not in names:
                raise ValueError(f"sdist missing {required}")
        stream = archive.extractfile(f"{root}/PKG-INFO")
        if stream is None:
            raise ValueError("sdist is missing package metadata")
        with stream:
            _metadata(stream.read(), expected_version)
    return wheel, sdist


def write_hashes(dist: Path, files: tuple[Path, Path]) -> None:
    rows = []
    for path in files:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        rows.append(f"{digest.hexdigest()}  {path.name}\n")
    (dist / "SHA256SUMS").write_text("".join(rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag", default=None)
    parser.add_argument("--output", type=Path, help="GitHub Actions output file")
    args = parser.parse_args()
    package_version = version("locata-torch")
    try:
        index = release_index(package_version, args.tag)
        files = check_distributions(args.dist, package_version)
        write_hashes(args.dist, files)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    if args.output:
        with args.output.open("a", encoding="utf-8") as stream:
            stream.write(f"index={index}\nversion={package_version}\n")
    print(f"Validated {package_version}; destination: {index or 'validation only'}")


if __name__ == "__main__":
    main()
