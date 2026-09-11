"""Offline behavioral and geometry contracts for the summing-lever drawing."""

from __future__ import annotations

from pathlib import Path

import build_summing_lever as lever
import draw_summing_lever as drawing
import summing_lever_notes
import summing_lever_spec
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths_and_portrait_layout() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/summing-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/summing-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/summing-lever_drawing.png")
    registered = DRAWINGS_BY_NAME["summing_lever"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.PORTRAIT


def test_marked_dimensions_are_consumed_once_by_the_manufacturing_views() -> None:
    assert lever.DRAWING_DIMENSIONS is summing_lever_notes.DRAWING_DIMENSIONS
    marked = set().union(*summing_lever_notes.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.TOP_KEEP)
        | set(drawing.CYLINDER_SECTION_KEEP)
        | set(drawing.KNIFE_SECTION_KEEP)
        | set(drawing.RIGHT_KEEP)
    )
    assert kept == marked
    assert "AnchorBoreDia" in drawing.TOP_KEEP
    assert "CylDia" in drawing.CYLINDER_SECTION_KEEP
    assert "HexKnifeFrontS1dy" in drawing.KNIFE_SECTION_KEEP
    assert "HexKnifeFrontTopY" not in kept


def test_draw_view_math_matches_authoritative_geometry() -> None:
    assert (drawing.PLATE_W, drawing.TIP_X) == (
        summing_lever_spec.PLATE_W,
        summing_lever_spec.TIP_X,
    )
    assert summing_lever_spec.CYL_R == lever.CYL_R
    assert summing_lever_spec.ANCHOR_R == lever.ANCHOR_R
    assert summing_lever_spec.ANCHOR_H == lever.ANCHOR_H
    assert summing_lever_spec.PLATE_W == lever.PLATE_W
    assert summing_lever_spec.PLATE_T == lever.PLATE_T
    assert summing_lever_spec.HEX_W == lever.HEX_W
    assert summing_lever_spec.HEX_H == lever.HEX_H
    assert summing_lever_spec.HEX_DEPTH == lever.HEX_DEPTH
    assert summing_lever_spec.HOLE_X == lever.HOLE_X
    assert summing_lever_spec.HOLE_COUNT == lever.HOLE_COUNT
    assert summing_lever_spec.CHANNEL_PITCH == lever.CHANNEL_PITCH
    assert lever.HOLE_SPEC is summing_lever_spec.HOLE_SPEC
    assert drawing.HOLE_DIA == blind_cut_dia_mm(summing_lever_spec.HOLE_SPEC)

def test_third_angle_projection_and_useful_scales() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1.0, 3.0)
    assert drawing.TOP_CENTER[0] == drawing.FRONT_CENTER[0]
    assert drawing.TOP_CENTER[1] > drawing.FRONT_CENTER[1]
    assert drawing._top_xy(0.0, 10.0)[1] < drawing.TOP_CENTER[1]
    assert summing_lever_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:3"


def test_notes_fit_the_policy_specific_note_block() -> None:
    notes = summing_lever_notes.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4


def test_part_stamps_make_critical_title_properties() -> None:
    import _config

    spec = _config.parts("summing-lever")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == (
        "GREEN ENAMEL; MASK KNIFE EDGES AND ANCHOR BORE; "
        "OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 1


def test_surface_finish_is_part_owned_and_targets_the_knife_ridge() -> None:
    (control,) = summing_lever_spec.SURFACE_FINISHES
    assert control.key == "knife_edge_ridge"
    assert control.roughness_um == 1.6
    assert control.face.normal == summing_lever_spec.KNIFE_FACE_NORMAL
    assert control.face.offset_mm == summing_lever_spec.KNIFE_FACE_OFFSET
    assert (lever.HEX_W, lever.HEX_H) == (
        summing_lever_spec.HEX_W,
        summing_lever_spec.HEX_H,
    )
