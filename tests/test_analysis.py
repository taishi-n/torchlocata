import itertools
import math

import numpy as np
import pytest
import torch

from locata_torch import (
    EvaluationConfig,
    LocataDataset,
    activity_periods,
    align_vad,
    evaluate_locata,
    prepare_ground_truth,
    validate_tracks,
)
from locata_torch._assignment import minimum_assignment

ORIGIN = (2017, 1, 25, 23, 59, 59.996)


def ground_truth(activity=None, azimuth=None, times=None):
    time = torch.tensor([0.0, 1, 2, 3] if times is None else times)
    time = time.to(torch.float64)
    if activity is None:
        activity = {"source1": [1.0] * len(time)}
    sources = {}
    for name, values in activity.items():
        angles = [0.0] * len(time) if azimuth is None else azimuth[name]
        sources[name] = {
            "doa": {
                "azimuth": torch.tensor(angles, dtype=torch.float64),
                "inclination": torch.full_like(time, math.pi / 2),
                "range": torch.ones_like(time),
                "vector": torch.ones((len(time), 3), dtype=torch.float64),
            },
            "activity": torch.tensor(values, dtype=torch.float64),
        }
    return {
        "time": time,
        "time_origin": ORIGIN,
        "array_pose": {},
        "sources": sources,
        "metadata": {
            "id": "eval/task1/recording1/dummy",
            "split": "eval",
            "task": 1,
            "recording": 1,
            "array": "dummy",
        },
    }


def track(angles, *, name="track1", times=None, inclination=None):
    return {
        "id": name,
        "time_origin": ORIGIN,
        "time": torch.tensor(
            list(range(len(angles))) if times is None else times, dtype=torch.float64
        ),
        "azimuth": torch.tensor(angles, dtype=torch.float64),
        "inclination": None
        if inclination is None
        else torch.tensor(inclination, dtype=torch.float64),
    }


def test_vad_clock_boundaries_unknown_and_periods():
    vad = {
        "time": torch.tensor([0.004, 0.006, 0.008], dtype=torch.float64),
        "values": torch.tensor([True, False, True]),
    }
    query = torch.tensor([0, 0.004, 0.005, 0.006, 0.009, 0.01], dtype=torch.float64)
    values = align_vad(vad, query.to(torch.float64), sample_rate=500)
    torch.testing.assert_close(
        values,
        torch.tensor([math.nan, 1, 1, 0, 1, math.nan], dtype=torch.float64),
        equal_nan=True,
    )
    assert activity_periods(values).tolist() == [[1, 3], [4, 5]]
    assert activity_periods(torch.ones(2)).tolist() == [[0, 2]]
    assert activity_periods(torch.zeros(0)).shape == (0, 2)


def test_vad_rejects_invalid_labels_and_clocks():
    with pytest.raises(ValueError, match="VAD|binary"):
        activity_periods(torch.tensor([2.0]))
    with pytest.raises(ValueError, match="increas"):
        align_vad(
            {"time": torch.tensor([1.0, 0]), "values": torch.tensor([True, False])},
            torch.tensor([0.0]),
            sample_rate=100,
        )


def test_vad_does_not_hold_across_unobserved_clock_gap():
    values = align_vad(
        {
            "time": torch.tensor([0.0, 0.01], dtype=torch.float64),
            "values": torch.tensor([True, False]),
        },
        torch.tensor([0.001, 0.005, 0.01], dtype=torch.float64),
        sample_rate=500,
    )
    torch.testing.assert_close(
        values, torch.tensor([1.0, math.nan, 0.0], dtype=torch.float64), equal_nan=True
    )


def test_ground_truth_selects_times_instead_of_rows(make_recording, tmp_path):
    make_recording(sources=("talker1",), source_pose=False)
    sample = LocataDataset(tmp_path)[0]
    # Required rows intentionally differ from array rows in the fixture.
    sample["required_time"]["valid_flag"][:] = False
    sample["required_time"]["valid_flag"][[0, 2, 3]] = True
    original = sample["array_pose"]["time"].clone()
    truth = prepare_ground_truth(sample)
    torch.testing.assert_close(truth["time"], original[[0, 2, 3]])
    assert truth["time"][0].item() == pytest.approx(-0.004)
    assert truth["time_origin"] == sample["time_origin"]
    assert truth["sources"]["talker1"]["doa"] is None
    assert truth["sources"]["talker1"]["activity"] is None
    torch.testing.assert_close(sample["array_pose"]["time"], original)
    sample["required_time"]["time"][0] += 0.0001
    with pytest.raises(ValueError, match="pose.*time|timestamp"):
        prepare_ground_truth(sample)


def test_ground_truth_pose_and_vad_match(make_recording, tmp_path):
    make_recording(sources=("talker1",), vad=True)
    sample = LocataDataset(tmp_path)[0]
    ap = sample["array_pose"]
    sample["required_time"] = {
        "time": ap["time"][1:3].clone(),
        "valid_flag": torch.tensor([True, True]),
    }
    source = sample["sources"]["talker1"]
    source["pose"] = {
        **{k: v for k, v in ap.items() if k != "microphone_position"},
        "position": ap["position"] + torch.tensor([-1.0, 0, 0]),
    }
    truth = prepare_ground_truth(sample)
    assert truth["sources"]["talker1"]["activity"].tolist() == [0, 0]
    torch.testing.assert_close(
        truth["sources"]["talker1"]["doa"]["azimuth"],
        torch.zeros(2, dtype=torch.float64),
    )
    # Conflicting duplicate annotation timestamps must not select an arbitrary row.
    ap["time"][2] = ap["time"][1]
    ap["position"][2, 0] += 1
    with pytest.raises(ValueError, match="duplicate|conflict|timestamp"):
        prepare_ground_truth(sample)


def test_quantized_timestamp_multiplicity_preserves_order(make_recording, tmp_path):
    make_recording()
    sample = LocataDataset(tmp_path)[0]
    ap = sample["array_pose"]
    ap["time"][0] = ap["time"][1]
    ap["position"][1, 0] += 0.01
    sample["required_time"] = {
        "time": ap["time"][:3].clone(),
        "valid_flag": torch.ones(3, dtype=torch.bool),
    }
    result = prepare_ground_truth(sample)
    torch.testing.assert_close(result["array_pose"]["position"], ap["position"][:3])
    # With unequal multiplicity, a conflicting duplicate is ambiguous.
    sample["required_time"] = {
        "time": ap["time"][:1].clone(),
        "valid_flag": torch.ones(1, dtype=torch.bool),
    }
    with pytest.raises(ValueError, match="duplicate|multiplicity|ambiguous"):
        prepare_ground_truth(sample)


def test_explicit_audio_bounds_preserve_unknown_default(make_recording, tmp_path):
    make_recording(sources=("talker1",), source_pose=False, vad=True)
    sample = LocataDataset(tmp_path)[0]
    sample["required_time"] = {
        "time": sample["array_pose"]["time"].clone(),
        "valid_flag": torch.ones(6, dtype=torch.bool),
    }
    truth = prepare_ground_truth(sample)
    assert torch.isnan(truth["sources"]["talker1"]["activity"][0])
    cropped = prepare_ground_truth(
        sample, time_bounds=sample["metadata"]["time_bounds"]
    )
    assert len(cropped["time"]) == 4
    assert torch.isfinite(cropped["sources"]["talker1"]["activity"]).all()


@pytest.mark.parametrize("rows,cols", [(0, 3), (1, 4), (2, 3), (3, 2), (4, 4)])
def test_assignment_matches_exhaustive_minimum(rows, cols):
    rng = np.random.default_rng(42)
    for _ in range(8):
        cost = rng.integers(0, 9, size=(rows, cols)).astype(float)
        r, c = minimum_assignment(cost)
        if not min(rows, cols):
            assert len(r) == len(c) == 0
            continue
        if rows <= cols:
            expected = min(
                sum(cost[i, p[i]] for i in range(rows))
                for p in itertools.permutations(range(cols), rows)
            )
        else:
            expected = min(
                sum(cost[p[j], j] for j in range(cols))
                for p in itertools.permutations(range(rows), cols)
            )
        assert cost[r, c].sum() == pytest.approx(expected)
        assert len(set(r)) == len(set(c)) == min(rows, cols)


def test_multisource_evaluation_and_inactive_competitor():
    truth = ground_truth(
        {"one": [1, 1, 0, 1], "two": [0, 1, 1, 0]},
        {"one": [0] * 4, "two": [math.pi / 2] * 4},
    )
    tracks = [
        track([0, 0, math.nan, math.nan], name="A"),
        track([math.nan, math.pi / 2, math.pi / 2, 0], name="B"),
    ]
    result = evaluate_locata(truth, tracks)
    assert result["association"].tolist() == [[0, -1], [0, 1], [-1, 1], [1, -1]]
    assert result["metrics"]["probability_of_detection"]["value"] == 1
    assert result["metrics"]["azimuth_error_degrees"]["value"] == 0
    assert result["metrics"]["inclination_error_degrees"]["value"] is None
    # Source identity persists through speech inactivity, as in measures.m.
    assert result["track_swaps"].sum() == 1
    assert not result["ospa"].any()
    # The inactive source is closer, but must not steal this track.
    truth = ground_truth(
        {"active": [1] * 4, "inactive": [0] * 4},
        {"active": [math.radians(20)] * 4, "inactive": [0] * 4},
    )
    result = evaluate_locata(truth, [track([0] * 4)])
    assert result["metrics"]["azimuth_error_degrees"]["value"] == pytest.approx(20)
    assert result["ospa"][:, 0].tolist() == pytest.approx([20] * 4)


def test_empty_tracks_silence_and_missing_labels_are_distinct():
    truth = ground_truth()
    result = evaluate_locata(truth, [])
    assert result["metrics"]["probability_of_detection"]["value"] == 0
    assert result["metrics"]["azimuth_error_degrees"]["value"] is None
    assert result["metrics"]["track_latency_seconds"]["value"] is None
    assert result["ospa"][:, 0].tolist() == pytest.approx([30] * 4)
    truth["sources"]["source1"]["activity"][:] = 0
    silent = evaluate_locata(truth, [])
    assert silent["metrics"]["probability_of_detection"]["value"] is None
    assert not silent["ospa"].any()
    false = evaluate_locata(truth, [track([0] * 4)])
    assert false["metrics"]["false_alarm_rate"]["value"] == pytest.approx(4 / 3)
    truth["sources"]["source1"]["activity"] = None
    with pytest.raises(ValueError, match="VAD|activity"):
        evaluate_locata(truth, [])
    truth["sources"]["source1"]["activity"] = torch.tensor([math.nan] * 4)
    with pytest.raises(ValueError, match="unknown|coverage|activity"):
        evaluate_locata(truth, [])


def test_swaps_fragmentation_latency_and_inclination():
    result = evaluate_locata(
        ground_truth(),
        [
            track([0, math.nan, math.nan, math.nan], name="A", inclination=[1] * 4),
            track([math.nan, math.nan, 0, 0], name="B", inclination=[1] * 4),
        ],
    )
    assert result["track_swaps"].sum() == 1
    assert result["periods"][0]["fragments"] == 2
    assert result["metrics"]["track_latency_seconds"]["value"] == 0
    assert result["metrics"]["probability_of_detection"]["value"] == 0.75
    assert result["metrics"]["inclination_error_degrees"]["value"] == pytest.approx(
        90 - math.degrees(1)
    )
    late = evaluate_locata(ground_truth(), [track([math.nan, math.nan, 0, 0])])
    assert late["metrics"]["track_latency_seconds"]["value"] == 2


def test_wrapping_gate_boundary_and_ospa_cardinality():
    truth = ground_truth(azimuth={"source1": [math.radians(179)] * 4})
    result = evaluate_locata(truth, [track([math.radians(-179)] * 4)])
    assert result["metrics"]["azimuth_error_degrees"]["value"] == pytest.approx(2)
    truth = ground_truth()
    result = evaluate_locata(truth, [track([math.pi / 6] * 4)])
    assert result["metrics"]["probability_of_detection"]["value"] == 1
    result = evaluate_locata(truth, [track([0] * 4), track([0] * 4, name="extra")])
    assert result["ospa"][:, 0].tolist() == pytest.approx([15] * 4)
    assert result["ospa"][:, 2].tolist() == pytest.approx([30 / math.sqrt(2)] * 4)


def test_track_validation_and_time_contract():
    validate_tracks([track([0, 0], times=[1, 1])])
    with pytest.raises(ValueError, match="duplicate|conflict"):
        evaluate_locata(ground_truth(times=[1, 2]), [track([0, 1], times=[1, 1])])
    with pytest.raises(ValueError, match="unique|ID|id"):
        validate_tracks([track([0]), track([0])])
    with pytest.raises(ValueError, match="azimuth|range"):
        validate_tracks([track([math.pi])])
    t = track([0] * 4)
    t["time_origin"] = (2017, 1, 26, 0, 0, 0)
    with pytest.raises(ValueError, match="origin"):
        evaluate_locata(ground_truth(), [t])
    sparse = evaluate_locata(ground_truth(), [track([0], times=[2])])
    assert sparse["metrics"]["probability_of_detection"]["value"] == 0.25
    with pytest.raises(ValueError, match="gate"):
        EvaluationConfig(gate_degrees=0)


def test_gating_maximizes_cardinality_before_distance():
    truth = ground_truth(
        {"a": [1] * 4, "b": [1] * 4}, {"a": [0.0] * 4, "b": [math.radians(20)] * 4}
    )
    result = evaluate_locata(
        truth,
        [track([math.radians(19)] * 4), track([math.radians(45)] * 4, name="other")],
    )
    assert result["association"].tolist() == [[0, 1]] * 4
    assert not result["missed"].any()


def test_estimates_preserve_quantized_timestamp_occurrences():
    truth = ground_truth(
        azimuth={"source1": [0.0, 1.0, 0.0, 0.0]}, times=[0.0, 0.0, 1.0, 2.0]
    )
    result = evaluate_locata(
        truth, [track([0.0, 1.0, 0.0, 0.0], times=[0.0, 0.0, 1.0, 2.0])]
    )
    assert result["metrics"]["azimuth_error_degrees"]["value"] == 0
