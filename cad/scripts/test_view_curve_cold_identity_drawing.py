"""Cold CurveTag metadata needs native persistent EDGE identity, not equal shape."""

from pathlib import Path
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _view_curve_cold_identity as cold


def raw(tag=537446):
    return (
        "intersection_curve",
        {"identity": 3004, "trim": {"CurveTag": tag}, "coefficient": 0.125},
    )


def bank(value):
    return {
        "explicit": {
            "cross-hole": {
                "key": ("Drawing View2", "DetailItem"),
                "kind": 1,
                "geometry": value,
            }
        },
        "coordinate_picked": {},
    }


@pytest.fixture
def scene(monkeypatch, tmp_path):
    monkeypatch.setattr(cold, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(cold.persistent, "byte_variant", lambda value: value)
    extension = NS(
        GetPersistReference3=Mock(return_value=memoryview(b"edge")),
        IsSamePersistentID=Mock(return_value=1),
    )
    model = NS(
        GetType=lambda: 3,
        GetPathName=lambda: str(tmp_path / "owned.SLDDRW"),
        Extension=extension,
    )
    return NS(
        adapter=NS(currentModel=model),
        extension=extension,
        witness=cold.ColdIntersectionIdentities(),
        model=model,
    )


def capture(scene, phase, value, evidence=None):
    return scene.witness.observe(
        scene.adapter,
        "cross-hole",
        ("Drawing View2", "DetailItem"),
        object(),
        value,
        phase=phase,
        evidence={} if evidence is None else evidence,
    )


def test_raw_tag_difference_survives_but_native_same_edge_allows_cold_metadata(scene):
    first, last = raw(), raw(539344)
    capture(scene, "built", first)
    capture(scene, "reopened", last)
    assert bank(first) != bank(last)
    result = scene.witness.compare(bank(first), bank(last))
    assert result["status"] == "passed" and result["rejected"] == []
    assert result["curve_tag_observations"][0]["before"] == 537446
    assert result["curve_tag_observations"][0]["after"] == 539344
    assert scene.extension.IsSamePersistentID.call_count == 3


@pytest.mark.parametrize("result", [0, -1, True, None])
def test_cross_cold_unknown_or_different_identity_fails_even_with_identical_bytes(
    scene, result
):
    capture(scene, "built", raw())
    scene.extension.IsSamePersistentID.side_effect = [1, result]
    evidence = {}
    with pytest.raises(RuntimeError, match="persistent"):
        capture(scene, "reopened", raw(539344), evidence)
    assert evidence["cross_cold_result"] is result


@pytest.mark.parametrize("value", [None, b"", [256], [True], "edge"])
def test_invalid_native_reference_fails_without_comparison(scene, value):
    scene.extension.GetPersistReference3.return_value = value
    with pytest.raises(RuntimeError):
        capture(scene, "built", raw())
    scene.extension.IsSamePersistentID.assert_not_called()


@pytest.mark.parametrize(
    "damage", ["coefficient", "tag_type", "other_path", "bank_type", "unobserved"]
)
def test_no_unobserved_geometry_type_or_other_tag_change_is_waived(scene, damage):
    first, last = raw(), raw(539344)
    capture(scene, "built", first)
    capture(scene, "reopened", last)
    before, after = bank(first), bank(last)
    if damage == "coefficient":
        after["explicit"]["cross-hole"]["geometry"][1]["coefficient"] += 1e-16
    if damage == "tag_type":
        after["explicit"]["cross-hole"]["geometry"][1]["trim"]["CurveTag"] = 539344.0
    if damage == "other_path":
        before["coordinate_picked"]["CurveTag"] = 1
        after["coordinate_picked"]["CurveTag"] = 2
    if damage == "bank_type":
        after["explicit"]["cross-hole"]["key"] = list(
            after["explicit"]["cross-hole"]["key"]
        )
    if damage == "unobserved":
        scene.witness = cold.ColdIntersectionIdentities()
    assert scene.witness.compare(before, after)["status"] == "failed"


def test_different_persistent_bytes_can_be_native_same_and_bank_is_detached(scene):
    first, last = raw(), raw(539344)
    capture(scene, "built", first)
    scene.extension.GetPersistReference3.return_value = b"new encoding"
    capture(scene, "reopened", last)
    assert scene.witness.compare(bank(first), bank(last))["status"] == "passed"
    first[1]["trim"]["CurveTag"] += 1
    assert scene.witness.compare(bank(first), bank(last))["status"] == "failed"


def test_changed_drawing_path_refuses_before_cold_identity_query(scene):
    capture(scene, "built", raw())
    scene.model.GetPathName = lambda: str(Path("C:/other.SLDDRW"))
    with pytest.raises(RuntimeError, match="drawing"):
        capture(scene, "reopened", raw(539344))
    assert scene.extension.GetPersistReference3.call_count == 1


def test_closed_old_model_never_used_on_cold_capture(scene):
    capture(scene, "built", raw())
    path = scene.model.GetPathName()
    scene.model.GetPathName = Mock(
        side_effect=AssertionError("closed document queried")
    )
    scene.adapter.currentModel = NS(
        GetType=lambda: 3, GetPathName=lambda: path, Extension=scene.extension
    )
    capture(scene, "reopened", raw(539344))
    assert scene.witness.compare(bank(raw()), bank(raw(539344)))["status"] == "passed"


@pytest.mark.parametrize(
    "kind,path",
    [
        (1, "C:/part.SLDPRT"),
        (True, "C:/drawing.SLDDRW"),
        (3, ""),
        (3, "relative.SLDDRW"),
    ],
)
def test_non_drawing_or_unsaved_identity_refused_before_reference_read(
    scene, kind, path
):
    scene.model.GetType = lambda: kind
    scene.model.GetPathName = lambda: path
    with pytest.raises(RuntimeError, match="saved drawing"):
        capture(scene, "built", raw())
    scene.extension.GetPersistReference3.assert_not_called()


@pytest.mark.parametrize(
    "geometry",
    [
        ("line", (0.0,) * 3),
        ("intersection_curve", {"identity": 3005}),
        ("intersection_curve", {"identity": True}),
    ],
)
def test_only_exact_intersection_curve_can_receive_cold_identity_policy(
    scene, geometry
):
    with pytest.raises(ValueError, match="INTERSECTION_TYPE"):
        capture(scene, "built", geometry)
    scene.extension.GetPersistReference3.assert_not_called()


@pytest.mark.parametrize("result", [0, -1, True, None])
def test_self_identity_refusal_cannot_publish_comparison_permission(scene, result):
    scene.extension.IsSamePersistentID.return_value = result
    evidence = {}
    with pytest.raises(RuntimeError, match="self-comparison"):
        capture(scene, "built", raw(), evidence)
    assert evidence["self_result"] is result
    assert scene.witness.compare(bank(raw()), bank(raw(539344)))["status"] == "failed"


def test_native_exception_does_not_publish_a_cold_proof(scene):
    capture(scene, "built", raw())
    scene.extension.IsSamePersistentID.side_effect = [1, RuntimeError("native failure")]
    with pytest.raises(RuntimeError, match="native failure"):
        capture(scene, "reopened", raw(539344))
    assert scene.witness.compare(bank(raw()), bank(raw(539344)))["status"] == "failed"


def test_retained_actual_crankshaft_delta_is_only_tag_and_not_native_identity_proof(
    scene,
):
    fixture = json.loads(
        (
            Path(__file__).with_name("fixtures")
            / "crankshaft-cold-curve-tag-7vmq0092.json"
        ).read_text()
    )
    banks = []
    for phase in ("built", "reopened"):
        row = fixture[phase]
        # JSON has no tuple type; restore these two explicit runtime boundaries.
        row["key"] = tuple(row["key"])
        row["geometry"] = tuple(row["geometry"])
        banks.append({"explicit": {fixture["label"]: row}, "coordinate_picked": {}})
    before, after = banks
    assert before != after
    unproved = scene.witness.compare(before, after)
    assert unproved["status"] == "failed"
    assert unproved["rejected"] == [
        {
            "path": "/explicit/cross-hole true position/geometry/1/trim/CurveTag",
            "kind": "numeric",
            "before": 537446,
            "after": 539344,
            "delta": 1898,
        }
    ]
    # This is a UNIT native-double success, not an assertion that the original
    # receipt contained PID evidence. That receipt remains a native failure.
    for phase in ("built", "reopened"):
        row = fixture[phase]
        scene.witness.observe(
            scene.adapter,
            fixture["label"],
            row["key"],
            object(),
            row["geometry"],
            phase=phase,
            evidence={},
        )
    assert scene.witness.compare(before, after)["status"] == "passed"
