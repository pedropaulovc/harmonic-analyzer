"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import math
from pathlib import Path

import rocker_arm_notes
import rocker_arm_spec
import draw_rocker_arm as drawing
import build_rocker_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_installation import MECHANISM_X_SHIFT


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_arm_spec.ROD_HOLE_X,
        rocker_arm_spec.TOP_END_Y,
    )
    assert rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    # The tip corner the overall is picked at is the build's rod tip.
    assert math.isclose(rocker_arm_spec.ROD_TIP_X, arm.ROD_TIP_X, abs_tol=1e-12)
    assert math.isclose(rocker_arm_spec.ROD_TIP_Y, arm.ROD_TIP_Y, abs_tol=1e-12)
    assert (drawing.ROD_TIP_X, drawing.ROD_TIP_Y) == (
        rocker_arm_spec.ROD_TIP_X,
        rocker_arm_spec.ROD_TIP_Y,
    )


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The note-only radii and what fixes them: their common centre on the
    # pivot's vertical centreline (the seesaw's mirror line) and its height.
    assert "R800" in notes
    assert "R816" in notes
    assert "VERTICAL C/L THROUGH THE PIVOT BORE" in notes
    assert "808.00 ABOVE THE PIVOT AXIS" in notes
    assert "SYMMETRIC ABOUT THAT C/L" in notes
    assert "END SHOWN ONLY" in notes
    assert max(len(line) for line in lines) <= 60
    # The ends are VIEW dimensions now (arc-end x, tip face, overall), the pin
    # drill rides its callout, REAM rides the bore dimension, and the bore's
    # Ra is a symbol -- never a second copy in prose.
    assert "292.10" not in notes
    assert "266.70" not in notes
    assert "5.59" not in notes
    assert "LAND" not in notes
    assert "#47" not in notes
    assert "DRILL" not in notes
    assert "REAM" not in notes
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # Nothing the title block or a dimension already says, no GD&T prose.
    for banned in (
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "+0.03", "DATUM", "BASIC",
        "WITHIN", "Ra ", "REF", "MHA-", "BA ",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: the rod-pin hole is an X/Y
    # coordinate pair from the pivot bore that the block tolerance holds on
    # all 20 rockers, so the rocker uses none of its one-control allowance.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(rocker_arm_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(rocker_arm_spec, "GEOMETRIC_CONTROLS")
    assert "import math" not in source


def test_ends_are_dimensioned_on_the_view() -> None:
    # Each arc's end x from the pivot C/L plus the radial tip face fix both
    # ends (symmetric); the tip-to-tip overall is a REFERENCE sheet dimension
    # between the two tip corners (machinist review 2026-09-02).
    for name in ("TopRodX", "BottomRodX", "RodTipLen"):
        assert name in rocker_arm_notes.DRAWING_DIMENSIONS["StrapProfile"], name
        assert name in drawing.FRONT_KEEP, name
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="overall length"' in source
    assert 'entity_types=("VERTEX", "VERTEX")' in source
    assert source.count("set_reference_dimension(") == 1
    assert "p0=_sheet_xy(-ROD_TIP_X, ROD_TIP_Y)" in source
    assert "p1=_sheet_xy(ROD_TIP_X, ROD_TIP_Y)" in source
    # The overall stands above the arc-end stack, the bottom-arc end (the
    # shorter of the two x dims below the arm) sits nearer the arm than the
    # rod-pin X it nearly equals.
    assert drawing.OVERALL_TEXT_XY[1] > drawing.FRONT_KEEP["TopRodX"][1]
    assert drawing.FRONT_KEEP["BottomRodX"][1] > 0.138


def test_rod_pin_and_section_are_ordinary_sheet_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_edge_dimension(") == 4
    for label in (
        "rod-pin X location",
        "rod-pin Y location",
        "strap thickness",
        "overall length",
    ):
        assert f'label="{label}"' in source, label
    assert source.count('orientation="horizontal"') == 2
    assert source.count('orientation="vertical"') == 1
    assert source.count("edge_xy=rod_rim") == 1


def test_hole_callouts_state_size_and_process() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"PivotDia": "REAM THRU"}
    # The reamed running bore prints three decimals; nothing else does.
    assert drawing.DIMENSION_PRECISION == {"PivotDia": 3}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 1
    assert 'process="#47 DRILL"' in source
    assert "set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)" in source
    assert "set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_large_radius_values_are_note_only() -> None:
    assert drawing.NOTE_ONLY_DIMENSIONS == {"TopRadius", "BottomRadius"}
    assert "R800" in rocker_arm_notes.DRAWING_NOTES
    assert "R816" in rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "AISI 1018 cold-rolled steel strap"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    # The rocker swings on the pivot shaft in service, so the bore keeps its
    # roughness symbol (drawing-simplicity-policy.md rule 5) -- the one Ra on
    # the sheet.
    (control,) = rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")'
        in sheet_source
    )
    assert "roughness_ra=" not in sheet_source
    assert Path(drawing.__file__).read_text(encoding="utf-8").count(
        "add_surface_finish("
    ) == 1
