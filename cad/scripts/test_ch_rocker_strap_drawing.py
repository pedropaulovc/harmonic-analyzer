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
import export_features
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry
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
        # The hub hole prints REAM with no band (owner ruling 2026-11-24, fit
        # audit question 2): MHA-CH-12 is turned to it.
        ("StrapProfile", "TopAbovePivot"): "*deviations(TOP_EDGE_BAND)",
        ("StrapProfile", "BottomBelowPivot"): "*deviations(BOTTOM_EDGE_BAND)",
    }
    assert spec.ARM_THICKNESS_BAND == rocker.ARM_THICKNESS_BAND == (0.0254, -0.0254)
    assert spec.TOP_EDGE_BAND == rocker.TOP_EDGE_BAND
    # The bottom edge's band is the arm's: the lower profile zone's halves.
    assert spec.BOTTOM_EDGE_BAND == rocker.BOTTOM_EDGE_BAND == pytest.approx((0.254, -0.254))
    assert notes.DIMENSION_CALLOUTS["HoleDia"] == notes.HOLE_CALLOUT
    assert notes.HOLE_CALLOUT.splitlines() == [
        "REAM THRU",
        "MHA-CH-12 IS TURNED TO THIS HOLE",
        "BOTH EDGES SHARP, NO BURR",
    ]
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


_FEATURE_KINDS = {
    "hub_hole": "hole",
    "broad_face_pos_z": "face",
    "broad_face_neg_z": "face",
    "top_arc": "profile",
    "bottom_arc": "profile",
    "tip_land_pos_x": "face",
    "tip_land_neg_x": "face",
    "end_face_pos_x": "face",
    "end_face_neg_x": "face",
}


def _plane(normal: tuple[float, ...], point_mm: tuple[float, float, float]):
    length = math.hypot(*normal)
    unit = tuple(value / length for value in normal)
    return FaceGeometry(None, 4001, (*unit, *(v / 1000 for v in point_mm)), unit, ())


def _cylinder(radius_mm: float, centre_y_mm: float):
    axis = (0.0, centre_y_mm / 1000, 0.0, 0.0, 0.0, 1.0)
    return FaceGeometry(None, 4002, (*axis, radius_mm / 1000), None, ())


def _owners(geometry: FaceGeometry) -> list[str]:
    selectors = export_features.feature_selectors("ch_rocker_strap")
    return [
        name
        for name, specs in selectors.items()
        if any(selector.matches(geometry) for selector in specs)
    ]


def test_the_strap_is_a_feature_export_part_with_one_feature_per_face() -> None:
    assert "ch_rocker_strap" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("ch_rocker_strap")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == []
    assert manifest["material"]["thickness"] == rocker.ARM_THICKNESS
    # Every face of the native solid (both broad faces, the hole, both arcs,
    # both radial lands and both tapered ends) has exactly one owner; the
    # lands lie on the top arc's radius through their inner end.
    t = rocker.ARM_THICKNESS / 2.0
    expected = {
        "broad_face_pos_z": _plane((0.0, 0.0, 1.0), (0.0, 0.0, t)),
        "broad_face_neg_z": _plane((0.0, 0.0, -1.0), (0.0, 0.0, -t)),
        "hub_hole": _cylinder(spec.HOLE_DIA / 2.0, spec.PIVOT_MID_Y),
        "top_arc": _cylinder(spec.R_TOP, spec.CENTER_Y),
        "bottom_arc": _cylinder(spec.R_BOTTOM, spec.CENTER_Y),
    }
    radial = (spec.TOP_END_X, spec.TOP_END_Y - spec.CENTER_Y)
    taper = (spec.BOT_END_X - spec.ROD_TIP_X, spec.BOT_END_Y - spec.ROD_TIP_Y)
    for side, suffix in ((1, "pos_x"), (-1, "neg_x")):
        land_end = (side * spec.TOP_END_X, spec.TOP_END_Y, 0.0)
        foot = (side * spec.BOT_END_X, spec.BOT_END_Y, 0.0)
        land_normal = (side * -radial[1], radial[0], 0.0)
        expected[f"tip_land_{suffix}"] = _plane(land_normal, land_end)
        expected[f"end_face_{suffix}"] = _plane((side * -taper[1], taper[0], 0.0), foot)
    assert set(expected) == set(_FEATURE_KINDS)
    for name, geometry in expected.items():
        assert _owners(geometry) == [name], name


def test_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("ch_rocker_strap")["features"]
    hole = features["hub_hole"]
    assert hole["dia"] == [spec.HOLE_DIA, spec.HOLE_DIA + fit.STRAP_HOLE_BAND[0]]
    assert hole["at"] == [0.0, spec.PIVOT_MID_Y, 0.0] and hole["thru"] is True
    assert hole["precision"] == {"dia": notes.DRAWING_PRECISION_BY_NAME["HoleDia"]}
    for side in ("pos_z", "neg_z"):
        face = features[f"broad_face_{side}"]
        assert face["thickness"] == pytest.approx(
            [rocker.ARM_THICKNESS - 0.0254, rocker.ARM_THICKNESS + 0.0254]
        )
    assert features["top_arc"]["height_above_pivot"] == pytest.approx(
        [spec.TOP_EDGE_ABOVE_PIVOT - 0.254, spec.TOP_EDGE_ABOVE_PIVOT + 0.254]
    )
    assert features["bottom_arc"]["height_below_pivot"] == pytest.approx(
        [spec.BOTTOM_EDGE_BELOW_PIVOT - 0.254, spec.BOTTOM_EDGE_BELOW_PIVOT + 0.254]
    )
    # General rows qualify the printed inch nominal: R31.5, 5.75, 5.22, .22.
    assert features["top_arc"]["radius"] == pytest.approx([797.56, 802.64])
    land = features["tip_land_pos_x"]
    assert land["corner_station"] == pytest.approx([145.796, 146.304])
    assert land["land_length"] == pytest.approx([5.334, 5.842])
    assert land["land_angle_deg"] == pytest.approx([9.4, 11.4])
    end = features["end_face_neg_x"]
    assert end["foot_station"] == pytest.approx([132.334, 132.842])
    assert end["overall_length_ref"] == pytest.approx(2.0 * spec.ROD_TIP_X)
