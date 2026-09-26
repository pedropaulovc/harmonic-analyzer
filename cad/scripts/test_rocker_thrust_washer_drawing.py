"""Offline contracts for the rocker-bank thrust washer (MHA-148) drawing."""

from __future__ import annotations

import ast
from pathlib import Path

import _config
import build_rocker_thrust_washer as part
import draw_rocker_thrust_washer as drawing
import rocker_thrust_washer_drawing_spec as drawing_spec
import rocker_thrust_washer_spec as spec
from _surface_finish import MACHINED_UM
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-thrust-washer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-thrust-washer.pdf")
    assert (
        DRAWINGS_BY_NAME["rocker_thrust_washer"].script
        == Path(drawing.__file__).resolve()
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }


def test_only_the_bore_is_banded() -> None:
    """The end-play leaf is set against this washer, so its thickness sits in
    no datum chain: routine .XX, judged at that grade by the bar clearance
    (test_rocker_bank_layout)."""
    assert model_toleranced_dimensions(part) == {
        ("RingProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    assert spec.BORE_BAND[1] == 0.0
    assert spec.BORE_DIA - 6.35 > 0.0


def test_registry_row_is_the_turned_mha_148() -> None:
    row = _config.parts("rocker-thrust-washer")
    assert row["number"] == "MHA-148"
    assert int(row["quantity"]) == 1
    assert "turned" in str(row["process"])


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """r743-p1s-A: the MHA-148 drawing refused its source part, which carried
    no Material Specification, Finish or Quantity: the build never stamped
    them. The properties the part carries are the save's own set
    (part_properties) plus, when the build calls it before saving,
    apply_drawing_properties' set; every property the drawing requires must be
    among them and non-blank."""
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    build_calls = _calls(part.__file__)
    stamp = build_calls.get("apply_drawing_properties")
    if stamp is not None:
        assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
        assert stamp.lineno < build_calls["save_part_and_images"].lineno
        stamped = {}
        monkeypatch.setattr(
            _drawing_marks,
            "apply_custom_properties",
            lambda _adapter, props: stamped.update(props),
        )
        _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
        carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []


def test_both_running_faces_carry_the_machined_finish() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRSOM): the washer runs on rocker 0's hub
    on one face and on the south ear on the other, so each face owns a
    MACHINED finish. The controls live in the drawing spec, never in the
    placement spec the channel assembly reads."""
    by_key = {control.key: control for control in drawing_spec.SURFACE_FINISHES}
    assert set(by_key) == {"hub_face", "ear_face"}
    assert {control.roughness_um for control in by_key.values()} == {MACHINED_UM}
    assert by_key["hub_face"].face.normal == (0, 0, 1)
    assert by_key["hub_face"].face.offset_mm == spec.THICKNESS
    assert by_key["ear_face"].face.normal == (0, 0, -1)
    assert by_key["ear_face"].face.offset_mm == 0.0
    assert not hasattr(spec, "SURFACE_FINISHES")


def test_the_part_authors_and_the_drawing_projects_every_finish() -> None:
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in build_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "control = surface_finish_by_key(SURFACE_FINISHES, key)" in drawing_source
    calls = [
        node
        for node in ast.walk(ast.parse(drawing_source))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "add_surface_finish"
    ]
    assert len(calls) == 1
    (control,) = [k.value for k in calls[0].keywords if k.arg == "control"]
    assert ast.unparse(control) == "control"
    assert set(drawing.FINISH_PLACEMENT) == {
        c.key for c in drawing_spec.SURFACE_FINISHES
    }


def test_finish_symbols_sit_off_the_edge_view_and_its_dimension() -> None:
    scale = drawing.VIEW_SCALE[0] / drawing.VIEW_SCALE[1] / 1000.0
    half_w = spec.THICKNESS * scale / 2.0
    half_h = spec.OD * scale / 2.0
    for key, (symbol_xy, attach_xy) in drawing.FINISH_PLACEMENT.items():
        # The leader lands on its own face's line in the edge-on right view:
        # +Z (the hub face) draws on the left, -Z on the right.
        side = -1.0 if key == "hub_face" else 1.0
        assert attach_xy[0] == drawing.RIGHT_CENTER[0] + side * half_w
        assert abs(attach_xy[1] - drawing.RIGHT_CENTER[1]) < half_h
        assert abs(symbol_xy[0] - drawing.RIGHT_CENTER[0]) > half_w + 0.010
        dim = drawing.RIGHT_KEEP["DiscThick"]
        assert abs(symbol_xy[0] - dim[0]) > 0.010 or abs(symbol_xy[1] - dim[1]) > 0.010
        front_right = drawing.FRONT_CENTER[0] + half_h
        assert symbol_xy[0] > front_right + 0.010
