"""Offline contracts for the transgear knob cup (MHA-157) drawing."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

import _config
import build_transgear_knob_cup as part
import draw_transgear_knob_cup as drawing
import transgear_knob_cup_spec as spec
import transgear_knob_retaining_screw_spec as screw
import transgear_knob_shaft_spec as knob_shaft
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


def _band(places: int) -> float:
    """The +/- the title block prints for ``places`` (what the shop reads)."""
    return printed_band_mm(places)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-knob-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-knob-cup.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_knob_cup"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FACE_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FACE_KEEP)


def test_the_floor_is_one_dimension_from_the_front_face_in_the_section() -> None:
    """Contract §1.8 default c: the floor prints once, from the front face,
    and on solid cut edges -- the section carries it with the length, both
    from the same face, and no counterbore depth from the rear competes."""
    profile = spec.DRAWING_DIMENSIONS["CupProfile"]
    assert {"FloorDepth", "CupLength"} <= profile
    assert "FloorDepth" in drawing.SECTION_KEEP
    assert not any("Depth" in name for name in profile - {"FloorDepth"})
    # The cut passes through the cup axis, across the whole face view.
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.FACE_CENTER[1]
    assert x0 < drawing.FACE_CENTER[0] - drawing.HALF_OD
    assert x1 > drawing.FACE_CENTER[0] + drawing.HALF_OD


def test_only_the_bore_carries_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    assert min(spec.BORE_BAND) == 0.0 < max(spec.BORE_BAND)


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    floor = spec.FLOOR - _band(spec.FLOOR_PLACES)
    wall = (
        (spec.OD - _band(spec.OD_PLACES))
        - (spec.COUNTERBORE_DIA + _band(spec.COUNTERBORE_PLACES))
    ) / 2.0
    for worst in (floor, wall):
        assert worst >= spec.WALL_FLOOR
    assert spec.FLOOR_WORST == pytest.approx(floor, abs=0.01)
    assert spec.COUNTERBORE_WALL_WORST == pytest.approx(wall, abs=0.01)


def test_the_pan_head_enters_the_smallest_counterbore() -> None:
    smallest = spec.COUNTERBORE_DIA - _band(spec.COUNTERBORE_PLACES)
    assert smallest > screw.HEAD_DIA
    # Seated at the nominal floor, the head stands below the rear face.
    assert spec.FLOOR + screw.HEAD_H < spec.LENGTH


def test_the_diameters_print_at_the_coarsest_row_their_walls_allow() -> None:
    """Policy rule 12: nothing fits on the O.D. or in the counterbore beyond
    the pan head's entry, so both print at the title block's .X row once the
    wall, the floor ligament the head bears on and the head's entry all hold
    there."""
    coarse = _band(1)
    wall = ((spec.OD - coarse) - (spec.COUNTERBORE_DIA + coarse)) / 2.0
    ligament = (
        (spec.COUNTERBORE_DIA - coarse) - (spec.BORE_DIA + max(spec.BORE_BAND))
    ) / 2.0
    assert min(wall, ligament) >= spec.WALL_FLOOR
    assert spec.COUNTERBORE_DIA - coarse > screw.HEAD_DIA
    assert spec.OD_PLACES == spec.COUNTERBORE_PLACES == 1
    assert spec.FLOOR_LIGAMENT_WORST == pytest.approx(ligament, abs=0.01)


def test_the_screw_engages_1_5_d_at_the_thickest_printed_floor() -> None:
    """The shortest screw ASME B18.6.3 allows (+0/-0.03 in) reaches past the
    front face by its length less the floor; the thickest floor the sheet
    accepts, less the incomplete first thread, still leaves 1.5 D before the
    shaft's own entry terms."""
    thickest = spec.FLOOR + _band(spec.FLOOR_PLACES)
    reach = screw.SHANK_LEN - 0.03 * 25.4 - thickest - screw.PITCH
    assert reach >= 1.5 * screw.SHANK_DIA
    assert spec.ENGAGEMENT_OWN_WORST == pytest.approx(reach, abs=0.01)
    # With the shaft's largest tap countersink the joint still holds 1.5 D.
    shaft_side = reach - (knob_shaft.TAP_CSK_DIA + 0.10 - knob_shaft.TAP_MAJOR) / 2.0
    assert shaft_side >= 1.5 * screw.SHANK_DIA
    assert knob_shaft.ENGAGEMENT_WORST == pytest.approx(shaft_side, abs=0.01)


def _cup_spec_with(monkeypatch, name: str, value):
    monkeypatch.setattr(screw, name, value)
    fresh_spec = importlib.util.spec_from_file_location("_cup_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_engagement_gate_refuses_the_shorter_screw(monkeypatch) -> None:
    """Contract Q-cup: 90283A192 (3/8) was replaced by 90283A193 (7/16)
    because the shorter screw falls under 1.5 D at the .XX floor."""
    # Positive control: the supplied length re-executes clean.
    fresh = _cup_spec_with(monkeypatch, "SHANK_LEN", screw.SHANK_LEN)
    assert fresh.ENGAGEMENT_OWN_WORST == pytest.approx(spec.ENGAGEMENT_OWN_WORST)
    with pytest.raises(AssertionError, match="engages"):
        _cup_spec_with(monkeypatch, "SHANK_LEN", 3.0 / 8.0 * 25.4)


def test_registry_row_is_the_turned_brass_mha_157() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-157"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
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
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
