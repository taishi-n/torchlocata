import csv
import hashlib
import json
import math

import numpy as np
import pytest
import torch
from test_analysis import ground_truth, track

from locata_torch import (
    aggregate_results,
    evaluate_locata,
    read_results,
    write_results,
    write_submission,
)


def results():
    first = evaluate_locata(ground_truth(), [track([0, math.nan, 0, 0])])
    truth = ground_truth(times=[0, 1])
    truth["metadata"]["recording"] = 2
    truth["metadata"]["id"] = "eval/task1/recording2/dummy"
    second = evaluate_locata(truth, [])
    return [first, second]


def test_explicit_aggregation_weighting_and_denominators():
    recordings = aggregate_results(
        results(), group_by=("split", "task", "array"), weighting="recording"
    )
    pooled = aggregate_results(
        results(), group_by=("split", "task", "array"), weighting="pooled"
    )
    a = next(row for row in recordings if row["metric"] == "probability_of_detection")
    b = next(row for row in pooled if row["metric"] == "probability_of_detection")
    assert a["value"] == pytest.approx(0.375)
    assert b["value"] == pytest.approx(0.5)
    assert b["denominator"] == 6
    assert b["recordings"] == 2
    missing = next(
        row for row in pooled if row["metric"] == "inclination_error_degrees"
    )
    assert missing["value"] is None
    assert missing["missing"] == 2
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_results([results()[0]] * 2, group_by=("task",), weighting="pooled")
    with pytest.raises(ValueError, match="weight"):
        aggregate_results(results(), group_by=("task",), weighting="arbitrary")


def test_json_csv_npz_roundtrip_without_pickle(tmp_path):
    output = tmp_path / "result"
    write_results(
        results(),
        output,
        corpus_roots=(tmp_path / "corpus",),
        include_frame_arrays=True,
        provenance={"algorithm": "trial", "corpus_release": "synthetic"},
    )
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema_version"] == 1
    assert "2787cdab" in json.dumps(manifest)

    def reject_constant(value):
        pytest.fail(f"nonstandard JSON numeric constant: {value}")

    json.loads((output / "manifest.json").read_text(), parse_constant=reject_constant)
    bundle = read_results(output)
    assert len(bundle.frames) == 2
    assert all(
        array.dtype != object
        for values in bundle.frames.values()
        for array in values.values()
    )
    assert any(
        np.isnan(values["azimuth_error"]).any() for values in bundle.frames.values()
    )
    summary = aggregate_results(bundle, group_by=("task", "array"), weighting="pooled")
    probability = next(
        row for row in summary if row["metric"] == "probability_of_detection"
    )
    assert probability["value"] == 0.5
    with (output / "recordings.csv").open(newline="") as stream:
        assert any(row["value"] == "" for row in csv.DictReader(stream))
    with pytest.raises(FileExistsError):
        write_results(results(), output, corpus_roots=(tmp_path / "corpus",))


def test_storage_missing_details_unusual_ids_and_integrity(tmp_path):
    source_id = '../source,"\n音源'
    value = evaluate_locata(ground_truth({source_id: [1] * 4}), [track([0] * 4)])
    output = tmp_path / "result"
    write_results([value], output, corpus_roots=(tmp_path / "corpus",))
    bundle = read_results(output)
    assert bundle.frames == {}
    assert bundle.sources[0]["source_id"] == source_id
    manifest = output / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["schema_version"] = 99
    manifest.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="schema"):
        read_results(output)


def test_result_reader_checks_hashes_and_frame_shapes(tmp_path):
    output = tmp_path / "result"
    write_results(
        results(),
        output,
        corpus_roots=(tmp_path / "corpus",),
        include_frame_arrays=True,
    )
    path = next((output / "details").glob("*.npz"))
    with np.load(path, allow_pickle=False) as archive:
        values = {name: archive[name].copy() for name in archive.files}
    values["ospa"] = values["ospa"][:, :1]
    np.savez_compressed(path, **values)
    with pytest.raises(ValueError, match="checksum"):
        read_results(output)
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["files"][path.relative_to(output).as_posix()] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="shape|schema"):
        read_results(output)


def test_writer_protects_corpus_and_symlinks(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(corpus, target_is_directory=True)
    for output in (corpus / "results", link / "results"):
        with pytest.raises(ValueError, match="corpus|dataset"):
            write_results(results(), output, corpus_roots=(corpus,))
    assert not (corpus / "results").exists()
    with pytest.raises(ValueError, match="corpus_roots"):
        write_results(results(), tmp_path / "out", corpus_roots=())


def test_submission_calendar_rollover_precision_and_track_ids(tmp_path):
    t = track([0, math.nan, 1], name="track/α", times=[0, 0.004, 0.008])
    output = tmp_path / "submission"
    write_submission(
        [t],
        output,
        required_time={
            "time": t["time"],
            "valid_flag": torch.ones(3, dtype=torch.bool),
        },
        corpus_roots=(tmp_path / "corpus",),
        elapsed_seconds=0.125,
    )
    with (output / "source_1.txt").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert rows[0]["ID"] == "track/α"
    assert float(rows[0]["second"]) == pytest.approx(59.996)
    assert rows[1]["day"] == "26"
    assert float(rows[1]["second"]) == pytest.approx(0, abs=1e-12)
    assert float(rows[2]["second"]) == pytest.approx(0.004, abs=1e-12)
    assert rows[1]["azimuth"].lower() == "nan"
    assert float((output / "telapsed.txt").read_text()) == 0.125
    assert json.loads((output / "manifest.json").read_text())["tracks"] == ["track/α"]


def test_submission_uses_first_raw_required_time_including_invalid_rows(tmp_path):
    t = track([0, 0], times=[0.0, 0.004])
    write_submission(
        [t],
        tmp_path / "submission",
        corpus_roots=(tmp_path / "corpus",),
        required_time={
            "time": torch.tensor([-0.004, 0.0, 0.004], dtype=torch.float64),
            "valid_flag": torch.tensor([False, True, True]),
        },
        elapsed_seconds=0.1,
    )
    with (tmp_path / "submission" / "source_1.txt").open(newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert [float(row["timestamps"]) for row in rows] == pytest.approx([0.004, 0.008])


def test_aggregation_rejects_incompatible_configs():
    from locata_torch import EvaluationConfig

    values = results()
    values[1] = evaluate_locata(
        ground_truth(times=[0, 1]), [], config=EvaluationConfig(gate_degrees=10)
    )
    values[1]["metadata"]["id"] += "-other"
    with pytest.raises(ValueError, match="config|incompatible"):
        aggregate_results(values, group_by=("task",), weighting="pooled")
