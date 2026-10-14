"""Offline contracts for the keeper-chain anchor eye (MHA-DT-028) part and drawing.

A ``visual_noncritical`` formed-wire eye under ``cad/docs/drawing-guidelines.md``
(#1076): three native model dimensions whose places the PART owns -- the
loop's inside diameter and the tail's length from a blanked reference sketch
in the eye's plane, and the wire as REFERENCE -- every one at the title
block's one place, no GD&T, no roughness symbol, and at most four note lines.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_pin_eye as part
import dt_crank_pin_eye_notes as notes
import dt_crank_pin_eye_spec as spec
import draw_dt_crank_pin_eye as drawing
import vn_keeper_chain_spec as chain
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-pin-eye.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-pin-eye.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-pin-eye_drawing.png")
    entry = DRAWINGS_BY_NAME["dt_crank_pin_eye"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "dt_crank_pin_eye"
    assert part.PART_NAME == entry.artifact_stem == "dt-crank-pin-eye"


def test_printed_sizes_derive_from_the_eye_spec() -> None:
    assert notes.LOOP_ID == pytest.approx(2.0 * spec.LOOP_R - spec.WIRE_DIA)
    assert notes.LOOP_ID == pytest.approx(3.0)
    # The loop's callout says the bead chain passes: at nominal it does.
    assert notes.LOOP_ID > chain.BEAD_DIA


def test_marked_dimension_set_lives_in_the_notes_module() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert notes.DRAWING_DIMENSIONS == {
        "WireProfile": {"WireDia"},
        "EyeReference": {"LoopID", "TailLen"},
    }
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.TOP_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.TOP_KEEP)
    assert notes.REFERENCE_DIMENSIONS == {"WireDia"}
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "DRAWING_NOTES"):
        assert not hasattr(spec, name), name


def test_precision_is_authored_on_the_part_at_the_title_block_place() -> None:
    assert notes.DRAWING_PRECISION_BY_NAME == {"WireDia": 1, "LoopID": 1, "TailLen": 1}
    assert "draw_dt_crank_pin_eye.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert "hidden_sketches.curate_view_dimensions(" in source
    assert (
        "set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)" in source
    )
    build = _build_source()
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build
    assert "require_saved_drawing_properties(" in build
    assert model_toleranced_dimensions(part) == {}


def test_eye_reference_sketch_carries_loop_and_tail() -> None:
    build = "".join(_build_source().split())
    assert 'create_sketch("Right")' in build
    assert 'names=("LoopCx",None,"LoopID")' in build
    assert 'drives=(\'"LoopR"\',None,\'2*"LoopR"-"WireDia"\')' in build
    # The tail is measured from the loop centre to its end, along its axis.
    assert (
        'f"{loop_inside}.center",f"{tail_axis}.end","vertical_distance",TAIL_LEN'
        in build
    )
    assert 'ref.record("TailLen",\'"TailLen"\')' in build
    assert 'name_last_feature(adapter,"EyeReference")' in build
    assert 'blank_reference_sketches(adapter,("EyeReference",))' in build


def test_side_view_geometry_matches_the_part_frame() -> None:
    # Right view: sheet x runs along model -Z, so the loop centre (Z = -LoopR)
    # is right of the tail (Z = 0) by LoopR, and the tail's end is TailLen
    # above the loop centre.
    s = drawing._S
    assert drawing.LOOP_CENTER_XY[0] - drawing.TAIL_END_XY[0] == pytest.approx(
        spec.LOOP_R * s
    )
    assert drawing.TAIL_END_XY[1] - drawing.LOOP_CENTER_XY[1] == pytest.approx(
        spec.TAIL_LEN * s
    )
    assert drawing.LOOP_CENTER_XY[0] == pytest.approx(drawing.SIDE_CENTER[0])


def test_print_carries_no_gdt_roughness_or_hole_callouts() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert "for view in (side, top, iso):\n        set_hidden_lines_removed" in source
    assert '"*Isometric"' in source


def test_notes_are_few_and_carry_no_values() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4  # drawing-guidelines.md rule 7
    for number, line in enumerate(lines, start=1):
        assert line.startswith(f"{number}. "), line
    text = notes.DRAWING_NOTES
    for value in ("\u00b1", "+/-", "\u00d8", "MM", "1.0", "3.0", "4.0"):
        assert value not in text, value
    assert "MHA-DT-006" in text and "MHA-VN-006" in text
    assert "MHA-VN-035" in notes.DIMENSION_CALLOUTS["LoopID"]
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_are_live() -> None:
    assert _config.parts("dt-crank-arm")["number"] == "MHA-DT-006"
    assert _config.parts("vn-fillister-screw")["number"] == "MHA-VN-006"
    assert _config.parts("vn-keeper-chain")["number"] == "MHA-VN-035"


def test_views_are_in_projection_and_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert drawing.TOP_CENTER[0] == drawing.SIDE_CENTER[0]
    assert drawing.TOP_ANGLE == pytest.approx(-math.pi / 2.0)
    assert "_turn_top_view(adapter, drawing_model, side, top)" in _source()
    for x, y in (
        *drawing.SIDE_KEEP.values(),
        *drawing.TOP_KEEP.values(),
        drawing.NOTES_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    loop_x, loop_y = drawing.SIDE_KEEP["LoopID"]
    assert math.dist((loop_x, loop_y), drawing.LOOP_CENTER_XY) > drawing.HALF_OD
    tail_x, tail_y = drawing.SIDE_KEEP["TailLen"]
    assert tail_x < drawing.TAIL_END_XY[0]
    assert drawing.LOOP_CENTER_XY[1] < tail_y < drawing.TAIL_END_XY[1]


def test_part_registry_row() -> None:
    config = _config.parts("dt-crank-pin-eye")
    assert config["number"] == "MHA-DT-028"
    assert config["tolerance_class"] == "visual_noncritical"
    assert int(config["quantity"]) == 1
    assert "brass wire" in str(config["material_specification"]).lower()
    assert len(str(config["material_specification"])) <= 36
