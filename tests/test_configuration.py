import json
import pickle
from pathlib import Path

import pytest
from torch.utils.data import DataLoader

from locata_torch import LocataDataset, LocataError, _storage, collate_locata


def test_explicit_root_wins_and_no_store_is_created(
    make_recording, tmp_path, monkeypatch
):
    make_recording()
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path / "absent"))
    store = tmp_path / "unused-store"
    monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
    dataset = LocataDataset(tmp_path)
    assert len(dataset) == 1
    assert dataset.root == tmp_path.resolve()
    assert not store.exists()


def test_environment_root_and_home_expansion(make_recording, tmp_path, monkeypatch):
    make_recording()
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path))
    dataset = LocataDataset()
    assert dataset.root == tmp_path.resolve()
    import os

    relative = os.path.relpath(tmp_path, Path.home())
    assert LocataDataset("~/" + relative).root == tmp_path.resolve()


@pytest.mark.parametrize("value", ["", "/path/to/nonexistent-locata-root"])
def test_invalid_environment_root_does_not_fall_back(tmp_path, monkeypatch, value):
    monkeypatch.setenv("LOCATA_ROOT", value)
    monkeypatch.setenv("LOCATA_DATA_DIR", str(tmp_path))
    with pytest.raises(LocataError, match="LOCATA_ROOT"):
        LocataDataset()


def test_invalid_explicit_root_does_not_fall_back(
    make_recording, tmp_path, monkeypatch
):
    make_recording()
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path))
    with pytest.raises(LocataError, match="absent"):
        LocataDataset(tmp_path / "absent")


def test_missing_managed_root_is_read_only(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCATA_ROOT", raising=False)
    store = tmp_path / "store"
    monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
    with pytest.raises(LocataError, match="locata-torch download"):
        LocataDataset()
    assert not store.exists()


def test_platform_storage_and_empty_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCATA_DATA_DIR", raising=False)
    calls = []

    def standard_path(appname, **kwargs):
        calls.append((appname, kwargs))
        return tmp_path / "standard-store"

    monkeypatch.setattr(_storage, "user_data_path", standard_path)
    assert _storage.data_directory() == (tmp_path / "standard-store").resolve()
    assert calls == [("locata-torch", {"appauthor": False, "ensure_exists": False})]
    assert not (tmp_path / "standard-store").exists()
    monkeypatch.setenv("LOCATA_DATA_DIR", "")
    with pytest.raises(LocataError, match="LOCATA_DATA_DIR"):
        _storage.data_directory()
    assert _storage.data_directory(tmp_path) == tmp_path.resolve()


def test_default_root_rejects_incomplete_state(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCATA_ROOT", raising=False)
    monkeypatch.setenv("LOCATA_DATA_DIR", str(tmp_path))
    root = _storage.dataset_directory(tmp_path)
    (root / "dev").mkdir(parents=True)
    state = _storage.manifest_path(tmp_path, "dev")
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"state": "prepared"}))
    with pytest.raises(LocataError, match="dev|manifest"):
        LocataDataset()


@pytest.mark.parametrize("workers", [0, 2])
def test_resolved_root_is_retained_for_spawn(
    make_recording, tmp_path, monkeypatch, workers
):
    make_recording(frames=100, sample_rate=1000)
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path))
    dataset = LocataDataset()
    monkeypatch.setenv("LOCATA_ROOT", str(tmp_path / "absent"))
    restored = pickle.loads(pickle.dumps(dataset))
    assert restored.root == tmp_path.resolve()
    loader = DataLoader(
        restored.windows(num_samples=20),
        batch_size=2,
        collate_fn=collate_locata,
        num_workers=workers,
        multiprocessing_context="spawn" if workers else None,
        timeout=30 if workers else 0,
    )
    assert sum(len(batch["lengths"]) for batch in loader) == 5
