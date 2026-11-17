"""Offline contracts for the rocker strap (MHA-CH-13) drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm as rocker_part
import build_ch_rocker_strap as part
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import ch_rocker_hub_fit as fit
import _rocker_interface as rocker_interface
import ch_rocker_strap_notes as notes
import ch_rocker_strap_spec as spec
import draw_ch_rocker_strap as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-strap.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-strap.pdf")
    assert (
        DRAWINGS_BY_NAME["ch_rocker_strap"].script == Path(drawing.__file__).resolve()
    )
    assert "draw_ch_rocker_strap.py" in PRECISION_MIGRATED_DRAWINGS


def test_outline_is_the_finished_rocker_strap() -> None:
    # Same frame and the same vertices as MHA-CH-06's strap profile.
    assert spec.HOLE_DIA == rocker.HUB_DIA
    assert spec.PIVOT_MID_Y == rocker_interface.PIVOT_MID_Y
    assert spec.ROD_TIP_X == rocker.ROD_TIP_X
    assert spec.BOT_END_X == rocker.BOT_END_X
    assert spec.BOT_END_Y == pytest.approx(
        rocker_interface.CENTER_Y
        - math.sqrt(rocker_interface.R_BOTTOM**2 - rocker.BOT_END_X**2)
    )
    assert spec.ROD_TIP_Y < spec.TOP_END_Y
    # The tip land runs along the top arc's radius.
    tip_radius = math.hypot(spec.ROD_TIP_X, spec.ROD_TIP_Y - spec.CENTER_Y)
    assert tip_radius == pytest.approx(rocker.R_TOP + rocker.TIP_FACE)
    assert spec.strap_area() == pytest.approx(rocker_part._strap_area(), rel=1e-9)
    assert part.V_STRAP == pytest.approx(
        (spec.strap_area() - math.pi * (spec.HOLE_DIA / 2.0) ** 2)
        * rocker.ARM_THICKNESS
    )
    # The hub hole's walls (rule 17), each edge at the worst end of its band
    # against the reamed hole's top limit: both edges are held from the hole,
    # so the radii never stack into the wall (r1 machinist review: .031).
    hole_radius_max = (spec.HOLE_DIA + fit.STRAP_HOLE_BAND[0]) / 2.0
    top_wall = spec.TOP_EDGE_ABOVE_PIVOT + spec.TOP_EDGE_BAND[1] - hole_radius_max
    bottom_wall = (
        spec.BOTTOM_EDGE_BELOW_PIVOT + spec.BOTTOM_EDGE_BAND[1] - hole_radius_max
    )
    assert min(top_wall, bottom_wall) >= WALL_TARGET_MM
    # The bottom edge sits where MHA-CH-06's R816 puts it on the axis.
    assert spec.BOTTOM_EDGE_BELOW_PIVOT == pytest.approx(
        rocker_interface.PIVOT_MID_Y
        - (rocker_interface.CENTER_Y - rocker_interface.R_BOTTOM)
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    assert notes.DRAWING_PRECISION_BY_NAME["StrapThickness"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["TopAbovePivot"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["BottomBelowPivot"] == 3
    # TailTipLen is the RodTipLen's mirror: it prints once, as 2X, and so
    # does the land's angle from vertical (r4: "RADIAL" named no centre).
    assert "TailTipLen" not in marked
    assert notes.TIP_LAND_PREFIX == notes.TIP_LAND_ANGLE_PREFIX == "2X "
    assert "TipLandAngle" in notes.DRAWING_DIMENSIONS["StrapProfile"]
    assert notes.DRAWING_PRECISION_BY_NAME["TipLandAngle"] == 1


def test_every_band_is_native_and_names_its_mate() -> None:
    assert model_toleranced_dimensions(part) == {
        ("Strap", "StrapThickness"): "strap_upper",
        ("StrapProfile", "HoleDia"): "*deviations(STRAP_HOLE_BAND)",
        ("StrapProfile", "TopAbovePivot"): "*deviations(TOP_EDGE_BAND)",
        ("StrapProfile", "BottomBelowPivot"): "*deviations(BOTTOM_EDGE_BAND)",
    }
    assert spec.ARM_THICKNESS_BAND == rocker.ARM_THICKNESS_BAND == (0.0254, -0.0254)
    assert spec.TOP_EDGE_BAND == rocker.TOP_EDGE_BAND
    # The bottom edge's band is the arm's: the lower profile zone's halves.
    assert spec.BOTTOM_EDGE_BAND == rocker.BOTTOM_EDGE_BAND == pytest.approx((0.254, -0.254))
    assert notes.DIMENSION_CALLOUTS["HoleDia"] == notes.HOLE_CALLOUT
    assert notes.DIMENSION_CALLOUTS["StrapThickness"] == rocker_notes.STRAP_FIT_CALLOUT


def test_no_rod_pin_hole_and_no_finished_bore_on_the_strap() -> None:
    printed = " ".join(notes.DIMENSION_CALLOUTS.values())
    assert "#47" not in printed
    assert f"{rocker.PIVOT_HOLE_DIA / 25.4:.3f}".removeprefix("0") not in printed


def test_drawing_quality_and_no_gdt() -> None:
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert drawing.ISO_SCALE == (1, 2)


def test_overall_length_is_a_one_place_reference_and_enforced() -> None:
    # ENFORCE r3: the overall printed only as two tip offsets (rule 10).
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert spec.DRAWING_REFERENCE_PRECISION == {"OverallLength": 1}
    tip_x_in = spec.ROD_TIP_X / 25.4
    offsets = 2 * round(tip_x_in, notes.DRAWING_PRECISION_BY_NAME["RodTipX"])
    overall = round(2 * tip_x_in, spec.DRAWING_REFERENCE_PRECISION["OverallLength"])
    # One place, so the reference agrees with the offsets' printed sum.
    assert overall == pytest.approx(round(offsets, 1))
    # Outermost: above the offsets' row.
    assert drawing.OVERALL_LINE_Y > drawing.TIP_LINE_Y


def test_registry_row() -> None:
    row = _config.parts("ch-rocker-strap")
    assert row["number"] == spec.NUMBER == "MHA-CH-13"
    assert row["component_of"] == "ch-rocker-arm"
    assert int(row["quantity"]) == int(_config.parts("ch-rocker-arm")["quantity"])
    # Owner ruling 2026-11-03: the title-block MATERIAL row names the grade.
    assert row["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert "1018" in str(row["material_specification"])
    assert len(str(row["material_specification"])) <= 36
    assert len(str(row["finish"])) <= 36
    assert part.MATERIAL == "Plain Carbon Steel"


def test_the_strap_stays_flat_by_its_route_not_by_a_frame() -> None:
    """#2340: the strap's bow is bounded by its thickness band and, once
    joined, MHA-CH-06's strap position zone (the fork and bar-foot gaps spend
    those), so this sheet carries no frame; the registry route skims both
    faces of the bought 1/8 flat equally, and the figure it states is the
    model's."""
    row = _config.parts("ch-rocker-strap")
    assert "1/8 x 1-1/2" in str(row["material_specification"])
    per_face = (0.125 * 25.4 - spec.ARM_THICKNESS) / 2.0 / 25.4
    assert f"{per_face:.4f}".lstrip("0") in row["process"]
