"""Offline manufacturing contracts for the connecting-rod drawing."""

from __future__ import annotations

from pathlib import Path

import _config
import build_connecting_rod as rod
import connecting_rod_notes
import connecting_rod_spec
import draw_connecting_rod as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
import rod_pivot_spec as pivot


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["connecting_rod"].script == Path(drawing.__file__).resolve()


def test_every_marked_model_dimension_has_one_native_view_authority() -> None:
    assert rod.DRAWING_DIMENSIONS is connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*connecting_rod_notes.DRAWING_DIMENSIONS.values())
    front = set(drawing.FRONT_KEEP)
    section = set(drawing.SECTION_KEEP)
    assert front.isdisjoint(section)
    assert front | section == marked
    assert connecting_rod_notes.DRAWING_DIMENSIONS == {
        "RingDiscProfile": {"RingOuterDia"},
        "StrapBoreProfile": {"StrapBoreDia"},
        "ShankProfile": {"ShankWidthDim"},
        "HeadProfile": {"HeadCrownR", "HeadShoulderRiseR"},
        "ForkFlareProfile": {"FlareAxialRise", "FlareLength"},
        "ForkRootProfile": {"RootDiameter"},
        "ForkSlotProfile": {"SlotWidth"},
    }


def test_front_and_section_use_third_angle_projected_alignment() -> None:
    assert drawing.SECTION_CENTER[0] < drawing.FRONT_CENTER[0]
    assert drawing.SECTION_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


def test_draw_view_math_matches_the_part_and_pivot_contracts() -> None:
    assert drawing.CENTER_DISTANCE == connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert drawing.HEAD_TOP_Y == connecting_rod_spec.HEAD_TOP_Y
    assert drawing.HEAD_WIDTH == connecting_rod_spec.HEAD_WIDTH == rod.HEAD_WIDTH
    assert drawing.HEAD_HEIGHT == connecting_rod_spec.HEAD_HEIGHT == rod.HEAD_HEIGHT
    assert drawing.RING_THICKNESS == connecting_rod_spec.RING_THICKNESS
    assert drawing.SHANK_THICKNESS == connecting_rod_spec.SHANK_THICKNESS
    assert drawing.FORK_SLOT_NOMINAL == pivot.FORK_SLOT_NOMINAL
    assert drawing.FORK_CHEEK_THICKNESS == pivot.FORK_CHEEK_THICKNESS
    assert drawing.FORK_OUTER_THICKNESS == pivot.FORK_OUTER_THICKNESS
    assert drawing.FORK_ROOT_RADIUS == pivot.FORK_ROOT_RADIUS
    assert drawing.PIN_HOLE_SPEC is connecting_rod_spec.PIN_HOLE_SPEC
    assert drawing._PIN_HOLE_DIA == blind_cut_dia_mm(pivot.FORK_HOLE_SPEC)


def test_fit_authority_is_not_duplicated_in_free_text() -> None:
    notes = connecting_rod_notes.DRAWING_NOTES
    assert notes.splitlines() == [
        "MATES WITH ROCKER ARM MHA-071.",
        "FINAL SIDEPLAY AND FREE PIVOT PER MHA-132.",
    ]
    assert connecting_rod_notes.DIMENSION_CALLOUTS == {
        "StrapBoreDia": "RUNNING FIT WITH CYLINDER-GEAR CAM",
        "RootDiameter": "ROUND SLOT ROOT",
        "SlotWidth": "DESIGN NOMINAL; FINISH MATCHED SLOT",
    }
    forbidden = (
        "ONE MIDPLANE",
        "SHANK AND HEAD 2.50",
        "THREAD",
        "RECESS",
        "SPACER",
        "0.010",
        "0.025",
        "0.02",
        "0.05",
    )
    assert all(text not in notes.upper() for text in forbidden)
    assert connecting_rod_notes.DIMENSION_PRECISION["SlotWidth"] == 3
    assert connecting_rod_notes.DIMENSION_PRECISION["RootDiameter"] == 3


def test_only_size_tolerance_and_surface_finish_metadata_survive() -> None:
    assert not hasattr(connecting_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    assert connecting_rod_spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)"
    }
    (control,) = connecting_rod_spec.SURFACE_FINISHES
    assert control.key == "strap_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == connecting_rod_spec.RING_BORE_DIA


def test_title_block_metadata_remains_make_ready() -> None:
    spec = _config.parts("connecting-rod")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == (
        "BLACK ENAMEL; MASK STRAP BORE, PIVOT BORES AND INNER FORK FACES; "
        "OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 20
