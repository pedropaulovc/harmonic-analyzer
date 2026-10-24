"""Offline contracts for the transgear knob cup (MHA-PD-16) drawing."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

import _config
import build_pd_transgear_knob_cup as part
import draw_pd_transgear_knob_cup as drawing
import pd_transgear_knob_cup_spec as spec
import pd_vn_transgear_knob_cup_pin_spec as pin
import pd_transgear_knob_shaft_spec as knob_shaft
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


def _band(places: int) -> float:
    """The +/- the title block prints for ``places`` (what the shop reads)."""
    return printed_band_mm(places)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-knob-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-knob-cup.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_knob_cup"].script
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


def test_the_section_cuts_the_cup_axis_across_the_face_view() -> None:
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert y0 == y1 == drawing.FACE_CENTER[1]
    assert x0 < drawing.FACE_CENTER[0] - drawing.HALF_OD
    assert x1 > drawing.FACE_CENTER[0] + drawing.HALF_OD


def test_bore_callout_names_its_journal_and_clears_the_border_and_centreline() -> None:
    """Machinist review: the 0.012 band named no mate, and the old block's
    last line, centred at x 60 mm, was struck by the bore's centreline."""
    from _layout_geometry import estimate_text_box

    shaft = _config.parts("pd-transgear-knob-shaft")["number"]
    assert drawing.BORE_CALLOUT == (
        f"REAM THRU; SLIDES ON\n{shaft} JOURNAL,\n0.004-0.024\nDIAMETRAL CLEARANCE"
    )
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == drawing.BORE_CALLOUT
    assert "PIN HOLE" not in drawing.BORE_CALLOUT

    anchor = drawing.FACE_KEEP["BoreDia"]
    for line in drawing.BORE_CALLOUT.splitlines():
        box = estimate_text_box(line, anchor=anchor, height=0.0035, reference=5)
        assert box is not None
        # The larger of the generic estimate and the 2.45 mm a character
        # draw_mg_magnifying_wheel measured on a farm render.
        half = max(box.xmax - anchor[0], len(line) * 0.00245 / 2.0)
        assert anchor[0] - half > 0.0127 + 0.003
        assert anchor[0] + half < drawing.FACE_CENTER[0] - 0.005


def test_pin_hole_note_stands_apart_and_cites_the_assembly_step() -> None:
    import pd_paper_drive_assembly_steps as steps

    note = drawing.PIN_HOLE_NOTE
    assert note.startswith("NO CROSS HOLE ON THIS PART")
    assert _config.parts("pd-vn-transgear-knob-cup-pin")["number"] in note
    assert steps.step_ref("knob-stack-fitted") in note
    # Below the face view (and its section labels), inside the left border.
    assert (
        drawing.PIN_HOLE_NOTE_XY[1] < drawing.FACE_CENTER[1] - drawing.HALF_OD - 0.010
    )
    assert drawing.PIN_HOLE_NOTE_XY[0] > 0.0127 + 0.003


def test_front_finish_caption_names_the_plate_boss() -> None:
    plate = _config.parts("pd-transgear-arm-plate")["number"]
    assert drawing.FRONT_FINISH_CAPTION == f"THRUST FACE ON\n{plate} REAR BOSS"
    assert drawing.FRONT_FINISH_CAPTION_XY[1] > drawing.FRONT_FINISH[1][1]


def test_cup_od_text_and_line_clear_the_native_section_scale_caption() -> None:
    """4e9a4df PNG: SCALE 4:1 occupied y 126 .. 131 mm, across the OD line."""
    from _layout_geometry import estimate_text_box

    caption_bottom, caption_top = 0.126, 0.142

    def clear(anchor):
        box = estimate_text_box("Ø19.0", anchor=anchor, height=0.0035, reference=2)
        assert box is not None
        return box.ymax + 0.003 < caption_bottom and anchor[1] < caption_bottom - 0.003

    assert clear(drawing.SECTION_KEEP["CupDia"])
    assert not clear((0.200, 0.130))
    assert caption_top < drawing.SECTION_CENTER[1] - spec.LENGTH * drawing._S / 2000.0
    assert drawing.SECTION_KEEP["CupDia"][0] == drawing.SECTION_CENTER[0]
    assert drawing.SECTION_KEEP["CupDia"][1] > 0.0127 + 0.003


def test_only_the_bore_carries_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*deviations(BORE_BAND)",
    }
    assert spec.BORE_DIA == pytest.approx(6.000)
    assert spec.BORE_BAND == pytest.approx((0.012, 0.0))
    assert min(spec.BORE_BAND) == 0.0


def test_walls_hold_at_the_worst_case_the_sheet_prints() -> None:
    """Every wall round the assembly-drilled pin hole, recomputed from the
    printed bands, stays at or above the 2.0 mm floor."""
    hole_r = (pin.HOLE_DIA + max(pin.HOLE_BAND)) / 2.0  # 0.825
    station = spec.PIN_HOLE_FROM_FRONT + spec.PIN_HOLE_STATION_TOL
    od_min = spec.OD - _band(spec.OD_PLACES)
    length_min = spec.LENGTH - _band(spec.LENGTH_PLACES)
    bore_max = spec.BORE_DIA + max(spec.BORE_BAND)
    walls = {
        "journal": (knob_shaft.JOURNAL_DIA_MIN - 2.0 * hole_r) / 2.0,
        "front": spec.PIN_HOLE_FROM_FRONT - spec.PIN_HOLE_STATION_TOL - hole_r,
        "end": knob_shaft.JOURNAL_REAR_EXTENSION_MIN - station - hole_r,
        "ring": (od_min - bore_max) / 2.0,
        "rear": length_min - station - hole_r,
    }
    assert walls["journal"] == pytest.approx((5.988 - 1.65) / 2.0, abs=1e-9)
    assert walls["front"] == pytest.approx(3.0 - 0.10 - 0.825, abs=1e-9)
    assert walls["ring"] == pytest.approx((18.2 - 6.012) / 2.0, abs=1e-9)
    assert {k: w for k, w in walls.items() if w < spec.WALL_FLOOR} == {}
    assert spec.JOURNAL_PIN_WALL_WORST == pytest.approx(walls["journal"])
    assert spec.FRONT_PIN_WALL_WORST == pytest.approx(walls["front"])
    assert spec.END_PIN_WALL_WORST == pytest.approx(walls["end"])
    assert spec.RADIAL_WALL_WORST == pytest.approx(walls["ring"])
    assert spec.REAR_PIN_WALL_WORST == pytest.approx(walls["rear"])


def test_the_longest_pin_stays_inside_the_smallest_od() -> None:
    od_min = spec.OD - _band(spec.OD_PLACES)
    longest = pin.PIN_LEN + pin.PIN_LEN_BAND
    assert (od_min - longest) / 2.0 > 0.0
    assert spec.PIN_END_INSIDE_OD_WORST == pytest.approx((od_min - longest) / 2.0)
    # The shortest pin still reaches through both cup walls.
    assert pin.PIN_LEN - pin.PIN_LEN_BAND > spec.BORE_DIA + max(spec.BORE_BAND)


def test_the_reamed_bore_slides_on_the_journal_over_the_full_bands() -> None:
    tightest = (spec.BORE_DIA + min(spec.BORE_BAND)) - (
        knob_shaft.JOURNAL_DIA + max(knob_shaft.JOURNAL_DIA_BAND)
    )
    loosest = (spec.BORE_DIA + max(spec.BORE_BAND)) - knob_shaft.JOURNAL_DIA_MIN
    assert 0.0 < tightest <= loosest
    assert spec.BORE_JOURNAL_CLEARANCE == pytest.approx((tightest, loosest))


def test_cup_bore_refuses_binding_on_the_actual_journal(monkeypatch) -> None:
    assert spec.BORE_JOURNAL_CLEARANCE == pytest.approx((0.004, 0.024))
    monkeypatch.setattr(knob_shaft, "JOURNAL_DIA_BAND", (0.020, 0.0))
    fresh_spec = importlib.util.spec_from_file_location("_cup_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(fresh_spec)
    with pytest.raises(AssertionError, match="bore binds"):
        fresh_spec.loader.exec_module(fresh)


def test_the_journal_end_stays_inside_the_shortest_cup() -> None:
    length_min = spec.LENGTH - _band(spec.LENGTH_PLACES)
    assert length_min - knob_shaft.JOURNAL_REAR_EXTENSION_MAX > 0.0


def test_registry_row_is_the_turned_brass_mha_157() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-16"
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
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
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
