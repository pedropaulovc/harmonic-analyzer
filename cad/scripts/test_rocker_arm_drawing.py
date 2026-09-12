"""Offline manufacturing contracts for the rocker-arm drawing."""

from __future__ import annotations

import math
from pathlib import Path

import _config
import build_rocker_arm as arm
import draw_rocker_arm as drawing
import rocker_arm_notes
import rocker_arm_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from cone_pivot_post_installation import MECHANISM_X_SHIFT
import rod_pivot_spec as pivot


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_every_marked_model_dimension_has_one_native_view_authority() -> None:
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert drawing.RIGHT_KEEP == {}
    assert rocker_arm_notes.DRAWING_DIMENSIONS == {
        "StrapProfile": {"BottomRodX", "RodTipLen"},
        "PivotHoleProfile": {"PivotDia", "PivotZ"},
        "HubProfile": {"HubDia"},
    }


def test_orthographic_views_are_projected_in_third_angle_alignment() -> None:
    assert drawing.RIGHT_CENTER[0] > drawing.FRONT_CENTER[0]
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"


def test_draw_view_math_matches_the_part_and_plain_pivot_contract() -> None:
    assert drawing.ARM_THICKNESS == rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert drawing.R_TOP == rocker_arm_spec.R_TOP
    assert drawing.R_BOTTOM == rocker_arm_spec.R_BOTTOM
    assert drawing.ROD_HOLE_X == rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert drawing.ROD_HOLE_Y == rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y
    assert drawing.ROD_HOLE_SPEC is rocker_arm_spec.ROD_HOLE_SPEC is pivot.ROCKER_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(pivot.ROCKER_HOLE_SPEC)
    assert math.isclose(
        rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )


def test_plain_rod_end_and_final_joint_authority_are_unambiguous() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    assert notes.splitlines() == [
        "PROFILE SYMMETRIC ABOUT PIVOT-BORE AXIS.",
        "ROD END MATES WITH CONNECTING ROD MHA-017.",
        "FINAL SIDEPLAY AND FREE PIVOT PER MHA-132.",
    ]
    assert rocker_arm_notes.DIMENSION_CALLOUTS == {
        "PivotDia": "REAM THRU",
        "RodTipLen": "2X ENDS",
    }
    forbidden = (
        "THREAD",
        "TAP",
        "RECESS",
        "SPACER",
        "COUNTERBORE",
        "0.010",
        "0.025",
        "0.02",
        "0.05",
    )
    assert all(text not in notes.upper() for text in forbidden)


def test_pivot_bore_tolerance_is_native_and_gdt_is_absent() -> None:
    assert rocker_arm_spec.PIVOT_BORE_DIA_BAND == (0.03, 0.00)
    assert not hasattr(rocker_arm_spec, "GEOMETRIC_TOLERANCES_MM")
    assert model_toleranced_dimensions(arm) == {
        ("PivotHoleProfile", "PivotDia"): "*deviations(PIVOT_BORE_DIA_BAND)"
    }
    assert rocker_arm_notes.DIMENSION_PRECISION["PivotDia"] == 2


def test_surface_finish_and_title_block_metadata_remain_make_ready() -> None:
    (control,) = rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == rocker_arm_spec.PIVOT_HOLE_DIA
    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20
