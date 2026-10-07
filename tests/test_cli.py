import pytest

import locata_torch.cli as cli
from locata_torch.cli import main


def test_path_cli(make_recording, tmp_path, monkeypatch, capsys):
    make_recording()
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path))
    assert main(["path"]) == 0
    assert capsys.readouterr().out == str(tmp_path.resolve()) + "\n"


def test_path_cli_missing_data(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("LOCATA_ROOT", raising=False)
    monkeypatch.setenv("LOCATA_DATA_DIR", str(tmp_path / "absent"))
    assert main(["path"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "locata-torch download" in captured.err


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "path" in capsys.readouterr().out


def test_download_cli_passes_split_and_storage(tmp_path, monkeypatch, capsys):
    calls = []

    def download(*, split, data_dir):
        calls.append((split, data_dir))
        return tmp_path / "installed"

    monkeypatch.setattr(cli, "download_locata", download)
    assert (
        main(
            [
                "download",
                "--split",
                "eval",
                "--split",
                "dev",
                "--data-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert calls == [(["eval", "dev"], str(tmp_path))]
    assert capsys.readouterr().out == str(tmp_path / "installed") + "\n"
