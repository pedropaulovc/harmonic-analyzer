"""Offline contracts for the crank-pin keeper ring (MHA-DT-027) part and drawing.

A ``visual_noncritical`` formed-wire ring under ``cad/docs/drawing-guidelines.md``
(#1076): three native model dimensions whose places the PART owns -- the
inside diameter from a blanked reference sketch in the ring's plane, and the
wire and the solder bead as REFERENCE -- every one at the title block's one
place, no GD&T, no roughness symbol, and at most four note lines.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_pin_ring as part
import dt_crank_pin_ring_notes as notes
import dt_crank_pin_ring_spec as spec
import draw_dt_crank_pin_ring as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-pin-ring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-pin-ring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-pin-ring_drawing.png")
    entry = DRAWINGS_BY_NAME["dt_crank_pin_ring"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "dt_crank_pin_ring"
    assert part.PART_NAME == entry.artifact_stem == "dt-crank-pin-ring"


def test_printed_sizes_derive_from_the_ring_spec() -> None:
    assert notes.RING_ID == pytest.approx(2.0 * spec.MEAN_R - spec.WIRE_DIA)
    assert notes.RING_ID == pytest.approx(9.0)
    # The bead is bigger than the wire it joins, so it reads on the sheet.
    assert spec.JOINT_DIA > spec.WIRE_DIA


def test_marked_dimension_set_lives_in_the_notes_module() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert notes.DRAWING_DIMENSIONS == {
        "WireProfile": {"WireDia"},
        "RingReference": {"RingID"},
        "JointProfile": {"JointDia"},
    }
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) == marked
    assert not set(drawing.TOP_KEEP) & set(drawing.FRONT_KEEP)
    assert notes.REFERENCE_DIMENSIONS == {"WireDia", "JointDia"}
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    # Drawing-only data stays out of the spec the drive train imports.
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "DRAWING_NOTES"):
        assert not hasattr(spec, name), name


def test_precision_is_authored_on_the_part_at_the_title_block_place() -> None:
    assert notes.DRAWING_PRECISION_BY_NAME == {"WireDia": 1, "RingID": 1, "JointDia": 1}
    assert "draw_dt_crank_pin_ring.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert "hidden_sketches.curate_view_dimensions(" in source
    # Native diameters: the plural helper keeps their glyph inside "( )".
    assert (
        "set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)" in source
    )
    build = _build_source()
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in build
    assert "require_saved_drawing_properties(" in build
    # visual_noncritical: no model-authored band anywhere.
    assert model_toleranced_dimensions(part) == {}


def test_ring_reference_sketch_carries_the_inside_diameter() -> None:
    build = "".join(_build_source().split())
    assert 'create_sketch("Top")' in build
    assert 'names=("RingCx",None,"RingID")' in build
    assert 'drives=(None,None,\'2*"MeanR"-"WireDia"\')' in build
    assert 'name_last_feature(adapter,"RingReference")' in build
    assert 'blank_reference_sketches(adapter,("RingReference",))' in build
    # The bead prints as the diameter the spec names.
    assert 'add_sketch_dimension(arc,None,"diameter",JOINT_DIA)' in build
    assert 'joint.record("JointDia")' in build
    assert 'joint.apply(adapter,"JointProfile")' in build
    assert '"radial"' not in build


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
    assert "for view in (top, front, iso):\n        set_hidden_lines_removed" in source
    assert '"*Isometric"' in source


def test_notes_are_few_and_carry_no_values() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4  # drawing-guidelines.md rule 7
    for number, line in enumerate(lines, start=1):
        assert line.startswith(f"{number}. "), line
    text = notes.DRAWING_NOTES
    for value in ("\u00b1", "+/-", "\u00d8", "MM", "1.0", "1.3", "9.0", "10"):
        assert value not in text, value
    assert "SILVER-SOLDERED" in text
    assert "MHA-DT-009" in text and "CROSS-HOLE" in text
    for callout in notes.DIMENSION_CALLOUTS.values():
        assert not any(ch.isdigit() for ch in callout), callout
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_number_in_the_notes_is_live() -> None:
    assert _config.parts("dt-crank-pin")["number"] == "MHA-DT-009"


def test_views_are_in_projection_and_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    assert _source().count("scale=VIEW_SCALE") == 3
    # Third-angle: the top view above the front view, on one vertical.
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] - drawing.HALF_OD > drawing.FRONT_CENTER[1] + 0.020
    assert drawing.TOP_CENTER[0] + drawing.HALF_OD < drawing.ISO_CENTER[0] - 0.050
    for x, y in (
        *drawing.TOP_KEEP.values(),
        *drawing.FRONT_KEEP.values(),
        drawing.NOTES_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    # Every label sits outside the ring it names.
    for x, y in drawing.TOP_KEEP.values():
        assert math.dist((x, y), drawing.TOP_CENTER) > drawing.HALF_OD
    wire_x, _ = drawing.FRONT_KEEP["WireDia"]
    assert wire_x < drawing.FRONT_CENTER[0] - drawing.HALF_OD


def test_part_registry_row() -> None:
    config = _config.parts("dt-crank-pin-ring")
    assert config["number"] == "MHA-DT-027"
    assert config["tolerance_class"] == "visual_noncritical"
    assert int(config["quantity"]) == 1
    assert "brass wire" in str(config["material_specification"]).lower()
    assert len(str(config["material_specification"])) <= 36
