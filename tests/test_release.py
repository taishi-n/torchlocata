import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def release():
    path = Path(__file__).parents[1] / "scripts/check_release.py"
    spec = importlib.util.spec_from_file_location("check_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("version", "tag", "index"),
    [
        ("0.1.0", "v0.1.0", "pypi"),
        ("0.1.0rc1", "v0.1.0rc1", "testpypi"),
        ("0.1.0", None, ""),
    ],
)
def test_release_routing(release, version, tag, index):
    assert release.release_index(version, tag) == index


@pytest.mark.parametrize(
    ("version", "tag"),
    [
        ("0.1.0", "v0.2.0"),
        ("0.1.0", "0.1.0"),
        ("0.1.0", "v0.1.0rc1"),
        ("0.1.0a1", "v0.1.0a1"),
        ("0.1.0.post1", "v0.1.0.post1"),
        ("0.1.0+local", "v0.1.0+local"),
        ("0.1.0.dev1", "v0.1.0.dev1"),
        ("0.1.0rc1", "v0.1.0rc01"),
        ("0.1", "v0.1"),
        ("0.1.0", "v0.1.0\nindex=pypi"),
    ],
)
def test_invalid_release_never_selects_an_index(release, version, tag):
    with pytest.raises(ValueError, match="version|tag"):
        release.release_index(version, tag)


@pytest.fixture
def distributions(tmp_path):
    info = "locata_torch-0.1.0.dist-info"
    metadata = (
        "Metadata-Version: 2.4\nName: locata-torch\nVersion: 0.1.0\n"
        "Requires-Python: >=3.10\nLicense-Expression: Apache-2.0\n"
        "License-File: LICENSE\nProvides-Extra: download\n"
        "Requires-Dist: torch>=2.4\nRequires-Dist: numpy>=1.26\n"
        "Requires-Dist: soundfile>=0.12\nRequires-Dist: platformdirs>=4.3.8\n"
        'Requires-Dist: filelock>=3.20.0; extra == "download"\n'
    )
    wheel_files = {
        f"{info}/METADATA": metadata,
        f"{info}/licenses/LICENSE": "Apache License\nVersion 2.0",
        f"{info}/entry_points.txt": (
            "[console_scripts]\nlocata-torch = locata_torch.cli:main\n"
        ),
        "locata_torch/py.typed": "",
        "locata_torch/__init__.py": "",
    }
    sdist_files = {
        "PKG-INFO": metadata,
        "LICENSE": "Apache License\nVersion 2.0",
        "pyproject.toml": '[project]\nname = "locata-torch"\nversion = "0.1.0"\n',
        "src/locata_torch/py.typed": "",
        "src/locata_torch/__init__.py": "",
    }

    def write(*, extra=None, version="0.1.0", missing_license=False):
        wheel = tmp_path / "locata_torch-0.1.0-py3-none-any.whl"
        files = dict(wheel_files)
        files[f"{info}/METADATA"] = metadata.replace(
            "Version: 0.1.0", f"Version: {version}"
        )
        if extra:
            files[extra] = "unwanted"
        if missing_license:
            del files[f"{info}/licenses/LICENSE"]
        with zipfile.ZipFile(wheel, "w") as archive:
            for name, value in files.items():
                archive.writestr(name, value)
        sdist = tmp_path / "locata_torch-0.1.0.tar.gz"
        with tarfile.open(sdist, "w:gz") as archive:
            for name, value in sdist_files.items():
                data = value.encode()
                member = tarfile.TarInfo(f"locata_torch-0.1.0/{name}")
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return wheel, sdist

    return tmp_path, write


def test_distribution_contract_and_hashes(release, distributions):
    directory, write = distributions
    files = write()
    assert release.check_distributions(directory, "0.1.0") == files
    release.write_hashes(directory, files)
    contents = (directory / "SHA256SUMS").read_text()
    assert all(path.name in contents for path in files)


@pytest.mark.parametrize(
    "extra", ["data.wav", "dev.zip", "site/index.html", ".venv/config"]
)
def test_distribution_excludes_corpus_and_generated_output(
    release, distributions, extra
):
    directory, write = distributions
    write(extra=extra)
    with pytest.raises(ValueError, match="excluded|asset"):
        release.check_distributions(directory, "0.1.0")


def test_metadata_mismatch_and_missing_license_fail(release, distributions):
    directory, write = distributions
    write(version="0.2.0")
    with pytest.raises(ValueError, match="version"):
        release.check_distributions(directory, "0.1.0")
    write(missing_license=True)
    with pytest.raises(ValueError, match="license|LICENSE"):
        release.check_distributions(directory, "0.1.0")
