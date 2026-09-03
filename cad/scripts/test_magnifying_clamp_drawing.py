"""Offline contracts for the magnifying-clamp drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a thumb-screwed clamp
block is not on the GD&T allowlist and nothing runs on its bores, so it carries
no datum, frame, roughness symbol or basic dimension; every bore axis is
located from a block face (the rod bore's depth station is a marked model
dimension, the lever bore's width station a drawing-added one), the #4-40 tap
is a native hole callout carrying the tap-from-the-top instruction, and the
note is one MATES WITH line.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_clamp as part
import draw_magnifying_clamp as drawing
import magnifying_clamp_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-clamp.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-clamp.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-clamp_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_clamp"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_clamp_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_clamp_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # The rod bore's depth station (6 from the front face) locates the common
    # rod-bore / tap centreline through the 12 thickness on the top view.
    assert "RodBoreZ" in magnifying_clamp_spec.DRAWING_DIMENSIONS["RodBoreProfile"]
    assert "RodBoreZ" in drawing.TOP_KEEP
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The block depth + bore stations the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import magnifying_clamp_geom as geom

    assert (geom.BLOCK_WIDTH, geom.BLOCK_HEIGHT, geom.BLOCK_DEPTH) == (20.0, 26.0, 12.0)
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from magnifying_clamp_geom import" in assembly
    assert "from build_magnifying_clamp import" not in assembly


def test_notes_are_one_mates_with_line() -> None:
    notes = magnifying_clamp_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) == 1
    assert notes == (
        "MATES WITH THE Ø6.0 LEVER ROD AND THE Ø5.0 VERTICAL ROD (SLIP FITS)."
    )
    # The tap direction rides the hole callout, the bore sizes and stations the
    # dimensions; nothing the views already show, nothing the title block says.
    for banned in (
        "#4-40",
        "TAP",
        "Ø6.2",
        "Ø5.2",
        "DRILL",
        "WITHOUT TOUCHING",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "MHA-",
        "BRASS",
        "C36000",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_bore_callouts_state_the_process_only() -> None:
    # The DRILLED HOLES title-block row governs a DRILL callout; the slip fit
    # is the size, not prose.
    assert drawing.DIMENSION_CALLOUTS == {
        "LeverBoreDiaDim": "DRILL THRU",
        "RodBoreDiaDim": "DRILL THRU",
    }


def test_thumb_screw_tap_is_a_native_hole_callout_with_the_tap_direction() -> None:
    # The tap-drill circle the callout picks mirrors the Hole Wizard table.
    assert magnifying_clamp_spec.THUMB_SCREW_TAP_DRILL_DIA == TAP_DRILL_MM["#4-40"]
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'label="thumb-screw tap"' in source
    assert "THUMB_SCREW_TAP_DRILL_DIA * _S / 2.0" in source
    # The concise wording retains both the entry face and destination while
    # keeping the associative callout inside the sheet border.
    assert drawing.THUMB_SCREW_PROCESS == "TOP-FACE TAP INTO LEVER BORE:"
    assert len(drawing.THUMB_SCREW_PROCESS) <= 30
    assert "process=THUMB_SCREW_PROCESS" in source
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("tapped", "#4-40")' in build_source


def test_lever_bore_is_located_from_the_side_face() -> None:
    # The lever bore (and the tap on the same centreline) sit on the block's X
    # axis, so no model dim exists: a drawing-added horizontal from the side
    # face to the bore axis (arc endpoint re-anchored to the centre), stacked
    # nearest under the front view with the 20.00 width outside it.
    source = _source()
    assert 'label="lever-bore width station"' in source
    assert 'orientation="horizontal"' in source
    assert "set_arc_endpoints_to_center(adapter, station" in source
    assert "find_edge_near(" in source
    assert drawing.SIDE_FACE_PICK[0] == drawing._front_x(-drawing.BLOCK_WIDTH / 2.0)
    rim_y = drawing._front_y(drawing.LEVER_BORE_Y) + drawing.LEVER_BORE_DIA * drawing._S / 2.0
    assert drawing.LEVER_BORE_RIM == (drawing._front_x(0.0), rim_y)
    bottom = drawing._front_y(0.0)
    assert bottom > drawing.LEVER_BORE_X_TEXT[1] > drawing.FRONT_KEEP["Width"][1]


def test_layout_clears_the_title_block_and_the_view_gap() -> None:
    # The 12.00 depth stands ABOVE the right view (under it is the title
    # block); the 6.50 rod-bore station is the only dimension in the gap
    # between the top and front views, so no extension line crosses another
    # dimension; both bore callouts sit 10+ mm off their outlines.
    source = _source()
    assert "RIGHT_CENTER[1] + RIGHT_HALF_Y + 0.012" in source
    top_bottom = drawing.TOP_CENTER[1] - drawing.BLOCK_DEPTH / 2.0 * drawing._S
    front_top = drawing._front_y(drawing.BLOCK_HEIGHT)
    assert front_top < drawing.TOP_KEEP["RodBoreXDim"][1] < top_bottom
    assert drawing.FRONT_KEEP["Width"][1] < drawing._front_y(0.0)
    assert drawing.FRONT_KEEP["LeverBoreDiaDim"][1] >= front_top + 0.010
    top_top = drawing.TOP_CENTER[1] + drawing.BLOCK_DEPTH / 2.0 * drawing._S
    assert drawing.TOP_KEEP["RodBoreDiaDim"][1] >= top_top + 0.015
    # Pull the 6.50 text left of the model-owned #4-40 annotation.
    assert drawing.TOP_KEEP["RodBoreXDim"][0] <= drawing.TOP_CENTER[0] - 0.018
    # Notes drop under the 20.00 row, still above the sheet border.
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.032)' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # Policy rules 3-5: not on the allowlist; nothing runs on the bores.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(magnifying_clamp_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(magnifying_clamp_spec, "GEOMETRIC_CONTROLS")
    assert magnifying_clamp_spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in Path(part.__file__).read_text(
        encoding="utf-8"
    )
    # Block depth across the right view + the lever-bore station: two
    # drawing-added dimensions.
    assert source.count("add_edge_dimension(") == 2


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-clamp")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
