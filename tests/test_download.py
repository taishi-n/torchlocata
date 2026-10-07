import builtins
import hashlib
import io
import json
import stat
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from locata_torch import (
    LocataDataset,
    LocataError,
    _download,
    _storage,
    download_locata,
)


@pytest.fixture
def archives(make_recording, tmp_path, monkeypatch):
    payloads = {}
    originals = {}
    for split in ("dev", "eval"):
        directory, _ = make_recording(split=split, sources=("s1", "s2"), vad=True)
        originals[split] = {
            p.relative_to(tmp_path / split).as_posix(): p.read_bytes()
            for p in directory.iterdir()
        }
        stream = io.BytesIO()
        with monkeypatch.context() as patch:
            patch.setattr(zipfile, "ZIP64_LIMIT", 0)
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, contents in originals[split].items():
                    archive.writestr(f"{split}/{name}", contents)
        payloads[split] = stream.getvalue()
        assert b"PK\x06\x06" in payloads[split]
    return payloads, originals


@pytest.fixture
def http_archives(monkeypatch):
    @contextmanager
    def serve(payloads, *, modes=("ok",), delay=0):
        state = SimpleNamespace(requests=[], modes=list(modes))

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                split = self.path.split("/")[-1].removesuffix(".zip")
                payload = payloads[split]
                count = len(state.requests)
                header = self.headers.get("Range")
                state.requests.append(
                    (split, header, self.headers.get("Accept-Encoding"))
                )
                mode = state.modes[min(count, len(state.modes) - 1)]
                if delay:
                    threading.Event().wait(delay)
                if mode in ("fail", "rate", "416"):
                    self.send_response({"fail": 503, "rate": 429, "416": 416}[mode])
                    self.send_header("Content-Length", "0")
                    self.send_header("Retry-After", "0")
                    self.end_headers()
                    return
                start = (
                    int(header.removeprefix("bytes=").removesuffix("-"))
                    if header
                    else 0
                )
                ranged = bool(header) and mode != "ignore"
                if not ranged:
                    start = 0
                self.send_response(206 if ranged else 200)
                if ranged:
                    declared_start = start + (mode == "bad-range")
                    total = len(payload) + (mode == "bad-total")
                    self.send_header(
                        "Content-Range",
                        f"bytes {declared_start}-{len(payload) - 1}/{total}",
                    )
                length = len(payload) - start
                if mode != "oversize":
                    self.send_header(
                        "Content-Length", str(length + (mode == "bad-size"))
                    )
                if mode == "encoding":
                    self.send_header("Content-Encoding", "gzip")
                self.end_headers()
                body = payload[start:]
                if mode == "oversize":
                    body += b"unexpected tail"
                if mode == "short":
                    body = body[: max(1, len(body) // 2)]
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        for split, payload in payloads.items():
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                expanded = sum(member.file_size for member in archive.infolist())
            monkeypatch.setitem(
                _storage.ARCHIVES,
                split,
                _storage.Archive(
                    split,
                    f"http://127.0.0.1:{server.server_port}/{split}.zip",
                    len(payload),
                    hashlib.md5(payload).hexdigest(),
                    expanded,
                ),
            )
        monkeypatch.setattr(_download, "_RETRY_DELAY", 0)
        try:
            yield state
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    return serve


def partial(store, split, payload):
    spec = _storage.ARCHIVES[split]
    directory = store / "archives" / _storage.RELEASE
    directory.mkdir(parents=True)
    (directory / f"{split}.zip.part").write_bytes(payload)
    (directory / f"{split}.zip.part.json").write_text(
        json.dumps({"release": _storage.RELEASE, "source": spec.identity()})
    )


def test_download_zip64_and_read_every_optional_field(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, originals = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        root = download_locata(split=("eval", "dev", "dev"), data_dir=store)
        assert root == _storage.dataset_directory(store)
        assert [row[0] for row in server.requests] == ["dev", "eval"]
        assert all(row[2] == "identity" for row in server.requests)
        for split in ("dev", "eval"):
            for name, data in originals[split].items():
                assert (root / split / name).read_bytes() == data
            manifest = json.loads(_storage.manifest_path(store, split).read_text())
            assert manifest["state"] == "complete"
            assert manifest["license"]["id"] == "ODC-BY-1.0"
            assert manifest["doi"] == _storage.DOI
            assert manifest["observed_md5"] == _storage.ARCHIVES[split].md5
        monkeypatch.delenv("LOCATA_ROOT", raising=False)
        monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
        dataset = LocataDataset(split=("dev", "eval"), load_source_audio=True)
        assert len(dataset) == 2
        for sample in dataset:
            assert list(sample["sources"]) == ["s1", "s2"]
            for source in sample["sources"].values():
                assert source["audio"] is not None
                assert source["pose"] is not None
                assert source["vad"]["array"] is not None
                assert source["vad"]["source"] is not None
        before = {p: p.stat().st_mtime_ns for p in root.rglob("*")}
        assert download_locata(split=("dev", "eval"), data_dir=store) == root
        assert len(server.requests) == 2
        assert before == {p: p.stat().st_mtime_ns for p in root.rglob("*")}
        assert not list((store / "staging").iterdir())


def test_eval_only_installation_path_and_reader(
    archives, http_archives, tmp_path, monkeypatch, capsys
):
    from locata_torch.cli import main

    payloads, _ = archives
    store = tmp_path / "store"
    monkeypatch.delenv("LOCATA_ROOT", raising=False)
    monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
    with http_archives(payloads) as server:
        root = download_locata(split="eval", data_dir=store)
        assert main(["path"]) == 1
        assert "--split dev" in capsys.readouterr().err
        assert main(["path", "--split", "eval"]) == 0
        assert capsys.readouterr().out.strip() == str(root)
        assert len(LocataDataset(split="eval")) == 1
        assert len(server.requests) == 1


@pytest.mark.parametrize("mode", ["ok", "ignore"])
def test_resume_and_ignored_range(archives, http_archives, tmp_path, mode):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads, modes=(mode,)) as server:
        offset = len(payloads["dev"]) // 2
        partial(store, "dev", payloads["dev"][:offset])
        root = download_locata(data_dir=store)
        assert root.is_dir()
        assert server.requests[0][1] == f"bytes={offset}-"
        cached = store / "archives" / _storage.RELEASE / "dev.zip"
        assert cached.read_bytes() == payloads["dev"]
        assert not cached.with_suffix(".zip.part").exists()


def test_truncated_transfer_retries_from_retained_offset(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    with http_archives(payloads, modes=("short", "ok")) as server:
        assert download_locata(data_dir=tmp_path / "store").is_dir()
        assert len(server.requests) == 2
        assert server.requests[1][1] is not None


@pytest.mark.parametrize("mode", ["fail", "rate"])
def test_retry_transient_http_errors(archives, http_archives, tmp_path, mode):
    payloads, _ = archives
    with http_archives(payloads, modes=(mode, "ok")) as server:
        assert download_locata(data_dir=tmp_path / "store").is_dir()
        assert len(server.requests) == 2


@pytest.mark.parametrize(
    "mode", ["bad-range", "bad-total", "bad-size", "encoding", "416"]
)
def test_reject_invalid_responses_without_installing(
    archives, http_archives, tmp_path, mode
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads, modes=(mode,)):
        partial(store, "dev", payloads["dev"][:100])
        with pytest.raises(LocataError, match="range|size|encoding|416"):
            download_locata(data_dir=store)
        assert not (_storage.dataset_directory(store) / "dev").exists()


def test_retry_limit_and_partial_is_retained(archives, http_archives, tmp_path):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads, modes=("short",)) as server:
        with pytest.raises(LocataError, match="short|truncated"):
            download_locata(data_dir=store)
        assert len(server.requests) == 3
        assert (store / "archives" / _storage.RELEASE / "dev.zip.part").is_file()


def test_oversized_response_is_rejected(archives, http_archives, tmp_path):
    payloads, _ = archives
    with http_archives(payloads, modes=("oversize",)):
        with pytest.raises(LocataError, match="size"):
            download_locata(data_dir=tmp_path / "store")
        assert not (_storage.dataset_directory(tmp_path / "store") / "dev").exists()


def test_wrong_checksum_never_extracts(archives, http_archives, tmp_path, monkeypatch):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads):
        spec = _storage.ARCHIVES["dev"]
        monkeypatch.setitem(
            _storage.ARCHIVES,
            "dev",
            _storage.Archive(
                spec.split, spec.url, spec.size, "0" * 32, spec.expanded_size
            ),
        )
        with pytest.raises(LocataError, match="MD5|checksum"):
            download_locata(data_dir=store)
        assert not (_storage.dataset_directory(store) / "dev").exists()


def test_completed_partial_is_verified_without_request(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        partial(store, "dev", payloads["dev"])
        assert download_locata(data_dir=store).is_dir()
        assert not server.requests


def test_unknown_partial_and_cached_corruption_are_not_overwritten(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        directory = store / "archives" / _storage.RELEASE
        directory.mkdir(parents=True)
        file = directory / "dev.zip.part"
        file.write_bytes(b"unknown")
        with pytest.raises(LocataError, match="partial"):
            download_locata(data_dir=store)
        assert file.read_bytes() == b"unknown"
        file.unlink()
        file = directory / "dev.zip"
        file.write_bytes(b"bad-cache")
        with pytest.raises(LocataError, match="size|MD5|checksum"):
            download_locata(data_dir=store)
        assert file.read_bytes() == b"bad-cache"
        assert not server.requests


def test_existing_corpus_and_unknown_target_are_preserved(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    with http_archives(payloads) as server:
        with pytest.raises(LocataError, match="existing.*root|unpacked"):
            download_locata(data_dir=tmp_path)
        store = tmp_path / "store"
        target = _storage.dataset_directory(store) / "dev"
        target.mkdir(parents=True)
        sentinel = target / "existing.txt"
        sentinel.write_text("preserve")
        with pytest.raises(LocataError, match="existing|unknown"):
            download_locata(data_dir=store)
        assert sentinel.read_text() == "preserve"
        assert not server.requests


def test_inventory_detects_same_size_corruption_and_added_files(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        root = download_locata(data_dir=store)
        file = next((root / "dev").rglob("*.wav"))
        original = file.read_bytes()
        file.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with pytest.raises(LocataError, match="CRC|altered"):
            download_locata(data_dir=store)
        file.write_bytes(original)
        (root / "dev" / "extra.txt").write_text("unknown")
        with pytest.raises(LocataError, match="inventory|altered"):
            download_locata(data_dir=store)
        assert len(server.requests) == 1


def test_insufficient_space_before_request(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    with http_archives(payloads) as server:
        monkeypatch.setattr(
            _download.shutil, "disk_usage", lambda _: SimpleNamespace(free=0)
        )
        store = tmp_path / "store"
        with pytest.raises(LocataError, match="space"):
            download_locata(data_dir=store)
        assert not server.requests
        assert not store.exists()


def test_parallel_requests_install_once(archives, http_archives, tmp_path):
    payloads, _ = archives
    with http_archives(payloads, delay=0.1) as server:
        store = tmp_path / "store"
        with ThreadPoolExecutor(max_workers=2) as executor:
            roots = list(
                executor.map(lambda _: download_locata(data_dir=store), range(2))
            )
        assert roots[0] == roots[1]
        assert len(server.requests) == 1


def test_prepared_manifest_recovers_after_rename(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    store = tmp_path / "store"
    original = _download._write_json

    def fail_commit(path, data):
        if data.get("state") == "complete":
            raise OSError("simulated crash after rename")
        return original(path, data)

    with http_archives(payloads) as server:
        monkeypatch.setattr(_download, "_write_json", fail_commit)
        with pytest.raises(LocataError, match="simulated crash"):
            download_locata(data_dir=store)
        monkeypatch.delenv("LOCATA_ROOT", raising=False)
        monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
        with pytest.raises(LocataError, match="not complete"):
            LocataDataset()
        monkeypatch.setattr(_download, "_write_json", original)
        assert download_locata(data_dir=store).is_dir()
        assert len(LocataDataset()) == 1
        assert len(server.requests) == 1


def test_prepared_manifest_recovers_before_rename(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    store = tmp_path / "store"
    original = type(store).rename

    def fail_rename(path, target):
        if path.name == "dev":
            raise OSError("simulated crash before rename")
        return original(path, target)

    with http_archives(payloads) as server:
        monkeypatch.setattr(type(store), "rename", fail_rename)
        with pytest.raises(LocataError, match="before rename"):
            download_locata(data_dir=store)
        assert not (_storage.dataset_directory(store) / "dev").exists()
        assert len(list((store / "staging").iterdir())) == 1
        monkeypatch.setattr(type(store), "rename", original)
        root = download_locata(data_dir=store)
        assert len(LocataDataset(root)) == 1
        assert len(server.requests) == 1
        assert not list((store / "staging").iterdir())


def test_later_split_failure_keeps_completed_split(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads, modes=("ok", "fail")) as server:
        with pytest.raises(LocataError, match="503"):
            download_locata(split=("dev", "eval"), data_dir=store)
        monkeypatch.delenv("LOCATA_ROOT", raising=False)
        monkeypatch.setenv("LOCATA_DATA_DIR", str(store))
        assert len(LocataDataset()) == 1
        with pytest.raises(LocataError, match="not complete"):
            LocataDataset(split="eval")
        before = len(server.requests)
        download_locata(data_dir=store)
        assert len(server.requests) == before


def test_namespace_symlink_does_not_write_to_existing_corpus(
    archives, http_archives, tmp_path
):
    payloads, _ = archives
    store = tmp_path / "store"
    store.mkdir()
    outside = tmp_path / "existing-corpus"
    outside.mkdir()
    try:
        (store / "datasets").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this environment cannot create directory symlinks")
    with http_archives(payloads) as server:
        with pytest.raises(LocataError, match="namespace"):
            download_locata(data_dir=store)
        assert not server.requests
        assert not list(outside.iterdir())


def test_cached_archive_needs_only_extraction_space(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        spec = _storage.ARCHIVES["dev"]
        directory = store / "archives" / _storage.RELEASE
        directory.mkdir(parents=True)
        (directory / "dev.zip").write_bytes(payloads["dev"])
        required = spec.expanded_size + max(_download._CHUNK, spec.expanded_size // 100)
        monkeypatch.setattr(
            _download.shutil, "disk_usage", lambda _: SimpleNamespace(free=required)
        )
        assert download_locata(data_dir=store).is_dir()
        assert not server.requests


def test_extraction_failure_cleans_only_owned_staging(
    archives, http_archives, tmp_path, monkeypatch
):
    payloads, _ = archives
    store = tmp_path / "store"
    with http_archives(payloads) as server:
        original = _download._extract

        def fail(*_):
            raise OSError("simulated interrupted extraction")

        monkeypatch.setattr(_download, "_extract", fail)
        with pytest.raises(LocataError, match="interrupted extraction"):
            download_locata(data_dir=store)
        assert not (_storage.dataset_directory(store) / "dev").exists()
        monkeypatch.setattr(_download, "_extract", original)
        assert download_locata(data_dir=store).is_dir()
        assert len(server.requests) == 1


@pytest.mark.parametrize(
    "names",
    [
        ("../escape",),
        ("/absolute",),
        ("dev/../escape",),
        ("dev/C:/escape",),
        ("dev\\escape",),
        ("dev/null\x00tail",),
        ("eval/wrong",),
        ("dev/a", "dev/a"),
        ("dev/A", "dev/a"),
        ("dev/a", "dev/a/b"),
        ("dev/CON.txt",),
        ("dev/trailing.",),
        ("dev/invalid?name",),
    ],
)
def test_unsafe_members_are_rejected_before_publish(http_archives, tmp_path, names):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name in names:
            member = zipfile.ZipInfo(name)
            # Preserve raw names instead of letting Windows replace backslashes.
            member.filename = name
            archive.writestr(member, b"data")
    with http_archives({"dev": stream.getvalue()}):
        with pytest.raises(LocataError, match="unsafe|collision|duplicate|top-level"):
            download_locata(data_dir=tmp_path / "store")
    assert not (tmp_path / "escape").exists()
    assert not (_storage.dataset_directory(tmp_path / "store") / "dev").exists()


def test_symlink_member_is_rejected(http_archives, tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        member = zipfile.ZipInfo("dev/link")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, b"../../outside")
    with http_archives({"dev": stream.getvalue()}):
        with pytest.raises(LocataError, match="symlink|unsafe"):
            download_locata(data_dir=tmp_path / "store")


def test_corrupt_zip_member_never_publishes(http_archives, tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("dev/payload", b"unique-payload")
    data = stream.getvalue().replace(b"unique-payload", b"broken-payload")
    with http_archives({"dev": data}):
        with pytest.raises(LocataError, match="CRC|ZIP|zip"):
            download_locata(data_dir=tmp_path / "store")


def test_invalid_split_and_missing_download_dependency(tmp_path, monkeypatch):
    for split in ((), "other", ("dev", "other")):
        with pytest.raises(ValueError, match="split"):
            download_locata(split=split, data_dir=tmp_path / "store")
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "filelock":
            raise ImportError("missing optional dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    with pytest.raises(LocataError, match=r"locata-torch\[download\]"):
        download_locata(data_dir=tmp_path / "store")
    assert not (tmp_path / "store").exists()
