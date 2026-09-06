"""Offline controls for exact source BASIC ownership and persistence witnesses."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_source_basic_dimensions as probe


@pytest.fixture(autouse=True)
def simple_binding(monkeypatch):
    monkeypatch.setattr(probe, "_early_bound", lambda value, interface: value)


def test_modern_tolerance_readback_matches_legacy_positive_control():
    dimension = SimpleNamespace(
        Tolerance=SimpleNamespace(Type=1), GetToleranceType=lambda: 1
    )
    assert probe.tolerance(dimension) == {"tolerance_type": 1, "designation": "basic"}
    dimension.GetToleranceType = lambda: 0
    with pytest.raises(RuntimeError, match="getters disagree"):
        probe.tolerance(dimension)


@pytest.mark.parametrize("result", [False, (False, 1, 0), (True, 8, 0), (True, 0)])
def test_in_place_save_requires_document_and_native_success(tmp_path, result):
    path = tmp_path / "unique.SLDPRT"
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetPathName=lambda: str(path), Save3=Mock(return_value=result)
        )
    )
    with pytest.raises(RuntimeError, match="Save3 failed"):
        probe.save_part(adapter, path)
    adapter.currentModel.Save3.assert_called_once_with(1, 0, 0)


def test_wrong_active_part_never_saves(tmp_path):
    save = Mock()
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetPathName=lambda: str(tmp_path / "original.SLDPRT"), Save3=save
        )
    )
    with pytest.raises(RuntimeError, match="wrong active native"):
        probe.save_part(adapter, tmp_path / "copy.SLDPRT")
    save.assert_not_called()


def test_in_place_save_records_nonfatal_native_warnings(tmp_path):
    path = tmp_path / "unique.SLDPRT"
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            GetPathName=lambda: str(path), Save3=lambda *args: (True, 0, 2)
        )
    )
    assert probe.save_part(adapter, path) == {
        "success": True,
        "errors": 0,
        "warnings": 2,
    }


def test_missing_native_tolerance_interface_is_not_a_nonbasic_dimension():
    with pytest.raises(RuntimeError, match="no native tolerance"):
        probe.tolerance(SimpleNamespace(Tolerance=None))


def test_part_value_cannot_change_when_basic_is_authored():
    before = {"Dim@Feature": {"value_system": 0.127, "tolerance_type": 0}}
    after = {"Dim@Feature": {"value_system": 0.127, "tolerance_type": 1}}
    probe.assert_part(before, after, "author", 1)
    after["Dim@Feature"]["value_system"] = 0.128
    with pytest.raises(RuntimeError, match="actual dimension value changed"):
        probe.assert_part(before, after, "author", 1)


def dimension_rows():
    return {
        name: {
            "name": name,
            "full_name": f"{name}@LeverOutline@source.Part",
            "kind": "model_dimension",
            "tolerance_type": 0,
            "owner_type": 0,
            "visibility": 1,
        }
        for name in probe.TARGETS["LeverOutline"]
    }


def test_drawing_gate_requires_every_exact_feature_target_and_basic(monkeypatch):
    monkeypatch.setattr(probe.attachments, "compare", Mock())
    before = {"semantics": {}, "dimensions": dimension_rows()}
    after = deepcopy(before)
    for row in after["dimensions"].values():
        row["tolerance_type"] = 1
        row["full_name"] = row["full_name"].replace("@source.Part", "@copied.Part")
    probe.assert_drawing(before, after, "relink", 1)
    after["dimensions"]["TipRadius"]["tolerance_type"] = 0
    with pytest.raises(RuntimeError, match="tolerance 0 != 1"):
        probe.assert_drawing(before, after, "relink", 1)
    after["dimensions"]["TipRadius"]["tolerance_type"] = 1
    after["dimensions"]["TipRadius"]["full_name"] = (
        "TipRadius@DifferentFeature@copied.Part"
    )
    with pytest.raises(RuntimeError, match="tolerance 1 != 0|target coverage"):
        probe.assert_drawing(before, after, "relink", 1)


def test_drawing_local_basic_designation_must_remain_basic(monkeypatch):
    monkeypatch.setattr(probe.attachments, "compare", Mock())
    before = {"semantics": {}, "dimensions": dimension_rows()}
    before["dimensions"]["RD1"] = {
        "name": "RD1",
        "full_name": "RD1@Drawing View1@source.Drawing",
        "kind": "drawing_reference",
        "tolerance_type": 1,
        "owner_type": 0,
        "visibility": 1,
    }
    after = deepcopy(before)
    for row in after["dimensions"].values():
        row["tolerance_type"] = 1
    probe.assert_drawing(before, after, "relink", 1)
    after["dimensions"]["RD1"]["tolerance_type"] = 0
    with pytest.raises(RuntimeError, match="RD1: tolerance 0 != 1"):
        probe.assert_drawing(before, after, "relink", 1)


def test_duplicate_imported_target_is_rejected_even_if_baseline_has_it(monkeypatch):
    monkeypatch.setattr(probe.attachments, "compare", Mock())
    rows = dimension_rows()
    rows["different_view/NoseRadius"] = deepcopy(rows["NoseRadius"])
    snapshot = {"semantics": {}, "dimensions": rows}
    with pytest.raises(RuntimeError, match="duplicate target coverage"):
        probe.assert_drawing(snapshot, snapshot, "baseline")


def test_canonicalization_only_normalizes_verified_part_owner(tmp_path):
    path = tmp_path / "copy.SLDPRT"
    source = {
        "models": {"view": {"path": str(path)}},
        "dimensions": {
            "dim": {
                "kind": "model_dimension",
                "components": [{"qualified_name": "NoseRadius@LeverOutline@copy.Part"}],
            }
        },
    }
    result = probe.canonical_semantics(source, path)
    assert (
        result["dimensions"]["dim"]["components"][0]["qualified_name"]
        == "NoseRadius@LeverOutline@<source-part>"
    )
    assert source["models"]["view"]["path"] == str(path)
    source["models"]["view"]["path"] = str(tmp_path / "wrong.SLDPRT")
    with pytest.raises(RuntimeError, match="unexpectedly references"):
        probe.canonical_semantics(source, path)
