"""Offline contracts for the cone-tip-block drawing."""

from __future__ import annotations

import re
from pathlib import Path

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import CLEARANCE_MM, TAP_DRILL_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert DRAWINGS_BY_NAME["cone_tip_block"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.RIGHT_KEEP)
    # PinchZ is marked and remains part-owned, but SolidWorks does not import
    # that Hole Wizard placement dimension into the end view. The sheet creates
    # the foot-to-pinch-axis height natively instead.
    assert kept | {"PinchZ"} == marked
    assert marked == {
        "Width",
        "Depth",
        "BlockHt",
        "PassageDiaDim",
        "PassageZ",
        "PinchZ",
        "SlitW",
        "SlitDepth",
    }
    assert part.ADJUSTER_AXIS_HEIGHT == cone_tip_block_spec.ADJUSTER_AXIS_HEIGHT
    # The slit depth is a named extrude depth the elevation shows natively.
    assert 'name_dimensions(adapter, "TopSlit", ["SlitDepth"])' in Path(
        part.__file__
    ).read_text(encoding="utf-8")
    assert "SlitDepth" in drawing.FRONT_KEEP


def test_non_bearing_tip_passage_replaces_the_fictional_journal() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "JournalBore" not in source
    assert "BoreDiaDim" not in source
    assert 'name_last_feature(adapter, "ShaftPassage")' in source
    assert part.SHAFT_PASSAGE_DIA == cone_tip_block_spec.SHAFT_PASSAGE_DIA == 2.0
    assert drawing.DIMENSION_CALLOUTS == {"PassageDiaDim": "DRILL THRU"}


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_tip_block_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "ONE SETUP" in notes
    assert "SLIT MAY BREAK INTO THE PINCH HOLE" in notes
    # The taps and the pinch drill ride their own view callouts now; a note
    # never restates a hole, a face direction or the title block.
    for banned in (
        "5/16-18",
        "#3-48",
        "#32 DRILL",
        "+X FACE",
        "+/-",
        "DATUM",
        "FRAME",
        "SIMULTANEOUS",
        "MATERIAL",
        "OXIDE",
        "X.XX",
        "UOS",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", 0.020, 0.088, char_height=0.0025' in source


def test_pinch_hole_is_flagged_from_the_drawn_entry_face() -> None:
    # The right view IS the +X face the pinch is drilled from: a leader note on
    # the clearance rim names the through jaw and the tapped jaw, sourced from
    # the spec (#3 normal clearance 2.946 = 0.1160 in is exactly the #32 drill).
    note = cone_tip_block_spec.PINCH_HOLE_NOTE
    assert note.startswith("#32 DRILL <MOD-DIAM>2.95 THRU THIS JAW")
    assert "TAP #3-48 THRU FAR JAW" in note
    assert cone_tip_block_spec.PINCH_CLEARANCE_DIA == CLEARANCE_MM[("#3", "normal")]
    assert round(0.116 * 25.4, 3) == cone_tip_block_spec.PINCH_CLEARANCE_DIA
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "text=PINCH_HOLE_NOTE" in source
    assert "entity=pinch_entity" in source
    assert 'label="pinch hole"' in source
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PinchClearance"' in part_source
    assert '"clearance", "#3", end="blind"' in part_source
    assert "depth_mm=(BLOCK_X - SLIT_W) / 2.0" in part_source


def test_adjuster_tap_has_a_native_callout_on_its_entry_face() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # One native Hole Wizard callout (thread, thread depth, tap-drill depth)
    # attached by ENTITY to the tap rim in the front view (the north face).
    assert source.count("add_native_hole_callout(") == 1
    assert "edge=tap_entity" in source
    assert "radius_mm=TAP_DRILL_MM[ADJUSTER_THREAD] / 2.0" in source
    assert TAP_DRILL_MM[cone_tip_block_spec.ADJUSTER_THREAD] == 6.528
    # Explicit import exposes the redundant generic thread note so exactly one
    # is removed before annotation placement can cross the plan dimensions.
    importer = re.search(r"import_cosmetic_threads\(\s*adapter,\s*front\s*\)", source)
    remover = 'remove_notes_matching(adapter, "Tapped Hole")'
    assert importer is not None
    assert remover in source
    assert source.index(remover) > importer.start()
    assert "if removed_tap_notes != 1:" in source
    # The complete native callout is beside the front view, below the plan's
    # axis-location lane, so its leader never crosses the 12.00 plan depth.
    assert drawing.TAP_CALLOUT_XY == (0.175, 0.198)
    front_right = drawing.FRONT_CENTER[0] + drawing.BLOCK_X / 2.0 * drawing._S
    assert drawing.TAP_CALLOUT_XY[0] >= front_right + 0.060
    assert (
        drawing._front_y(drawing.ADJUSTER_AXIS_HEIGHT)
        < drawing.TAP_CALLOUT_XY[1]
        < drawing.AXIS_LOCATION_Y
    )


def test_every_hole_axis_is_located_from_a_drawn_face() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Three entity-selected edge-to-centre dimensions: adjuster axis across the
    # width (front), pinch height from the foot and pinch station across the
    # depth (right).
    assert source.count("    _entity_dimension(\n") == 3
    for label in (
        'label="adjuster-axis lateral location"',
        'label="pinch-axis height"',
        'label="pinch-axis depth station"',
    ):
        assert label in source, label
    assert "set_arc_endpoints_to_center(adapter, display, label=label)" in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a clamp block is not on the GD&T
    # allowlist and nothing runs in its passage.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_note(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_tip_block_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(cone_tip_block_spec, "SURFACE_FINISHES")


def test_nothing_on_the_block_is_fitted() -> None:
    # The block height used to carry +0.05/0 with three decimals; nothing fits
    # on it (the shaft tip has 0.6 mm radial air in the passage), so every
    # dimension prints two places under the title block and the model carries
    # no band at all.
    assert drawing.DIMENSION_PRECISION == {"PassageZ": 2, "BlockHt": 2}
    assert not hasattr(cone_tip_block_spec, "BLOCK_HEIGHT_BAND")
    assert model_toleranced_dimensions(part) == {}


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (front, top, right):\n        set_hidden_lines_visible" in source
    )
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 4  # elevation + plan + side + pictorial


def test_slit_width_sits_clear_of_the_plan_outline() -> None:
    # The 1.20 slit width used to print on the slot's projected lines; it now
    # sits below the plan with a bare value (the depth is native on the
    # elevation, so the "WIDE X 8.00 DEEP" callout is gone).
    assert drawing.TOP_KEEP["SlitW"] == (drawing.TOP_CENTER[0], 0.221)
    assert "SlitW" not in drawing.DIMENSION_CALLOUTS


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
