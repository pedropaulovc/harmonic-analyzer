"""Offline contracts for the cone-swing-platform drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_cone_swing_platform as part
import cone_swing_platform_spec
import draw_cone_swing_platform as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-swing-platform.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-swing-platform.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-swing-platform_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_swing_platform"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_swing_platform_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_swing_platform_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_describe_pivot_notch_and_wedge() -> None:
    notes = cone_swing_platform_spec.DRAWING_NOTES
    assert "STEEL PLATE" not in notes
    assert "BLACK OXIDE" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "PIVOT HOLE" in notes
    assert "LOCK NOTCH" in notes
    assert "PIVOT HOLE SIZE PER PLAN-VIEW CALLOUT" in notes
    assert "HOLD THE AXIS PERPENDICULAR TO THE" in notes
    assert "33.00 +/-0.10 WEST AND 205.808 +/-0.10 SOUTH" in notes
    assert "2X 1/4-20 UNC-2B THRU" in notes
    assert "192.174 +/-0.10 SOUTH OF PIVOT" in notes
    assert "26.887" in notes
    assert "12.5182 +/-0.10 DEG NORTH OF WEST" in notes
    assert "9.11 +/-0.10 DEG NORTH" in notes
    assert "FULL-R CLOSED END (R4.000 REF)" in notes
    assert "VIRTUAL-SHARP INTERSECTIONS" in notes
    assert "PIVOT-HOLE AXIS" in notes
    assert "CENTRELINE THROUGH THE PIVOT-HOLE AXIS NORMAL TO THE NORTH END" in notes
    assert "STRAIGHT WITHIN 0.25" in notes
    # No GD&T on this sheet: the notes are the sole tolerance carrier, so
    # nothing may point at a datum tag or a control frame.
    assert "DATUM" not in notes
    assert "FCF" not in notes
    assert "OPEN THROUGH EDGE" in notes
    assert "NE R10.00, NW R8.00, SW R5.00, SE R12.00" in notes
    assert "CRANK-GEAR SWEPT OD CLEARS THE LOWER BROAD FACE" in notes
    assert "KEEP THE PLATE FULL THICKNESS" in notes
    assert "FINISHED THICKNESS 6.35 +/-0.10" in notes
    assert (
        f"TOP RELIEF DIA {part.PIVOT_BEARING_RELIEF_DIAMETER:.2f} X "
        f"{part.PIVOT_BEARING_RELIEF_DEPTH:.2f} DEEP"
    ) in notes
    assert (
        f"LOCAL BEARING THICKNESS {part.PIVOT_BEARING_THICKNESS:.2f} +/-0.05"
    ) in notes
    assert (
        "HOLD EACH BROAD FACE FLAT WITHIN 0.10 AND THE TWO PARALLEL WITHIN 0.10"
        in notes
    )
    assert "AS MODELLED" not in notes
    assert "SEE PLAN" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", 0.016, 0.100, char_height=0.0025' in source
    assert "_add_cone_axis_centerline(adapter, top)" in source
    assert "view.ModelToViewTransform" in source
    assert "view.GetVisibleEntities2" in source
    assert "blind_cut_dia_mm(PIVOT_HOLE_SPEC)" in source
    assert "curve.CircleParams" in source
    assert "pivot_centers" in source
    assert "view.GetOutline()" in source
    assert "projected pivot center" in source
    assert "drawing.EditSheet()" in source
    assert "drawing.EditSketch()" not in source
    assert "_visible_plan_controls(" in source
    assert 'label="pivot-hole size"' in source and "edge=pivot_edge" in source
    assert 'label="v2 post-mount tapped holes"' in source
    assert "edge=mount_edge" in source
    # GD&T removed from this sheet -- no datum tags, no control frames.
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert "datum=" not in source
    assert "characteristic=" not in source
    assert "set_dimension_callouts" not in source


def test_v2_post_foot_and_mount_pattern_cascade() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert part.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert part.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert part.WEST_HALF_N == 8.0
    assert part.EAST_HALF_S == 24.0
    assert part.SLOT_E_X == 33.0
    assert part.POST_STATION == -39.90136099793
    assert part.PIVOT_STATION == 152.27232594770453
    assert math.isclose(part.POST_LOCAL_Z, -192.17368694563453, abs_tol=1e-12)
    assert part.SLOT_E_Z < part.POST_LOCAL_Z
    assert part.POST_MAIN_DIA == 42.011
    assert part.POST_FOOT_CONTAINMENT >= 0.25
    assert part.PIVOT_BEARING_RELIEF_DIAMETER == pytest.approx(10.50)
    assert part.PIVOT_HEAD_RADIAL_CLEARANCE == pytest.approx((10.50 - 9.525) / 2.0)
    assert part.PIVOT_BEARING_RELIEF_DEPTH == pytest.approx(0.25)
    assert part.PIVOT_BEARING_THICKNESS == pytest.approx(6.10)
    assert part.PLATE_T - part.PIVOT_BEARING_THICKNESS == pytest.approx(
        part.PIVOT_BEARING_RELIEF_DEPTH
    )

    half = part.POST_MOUNT_HALF_PITCH
    west_x, west_z = part.POST_MOUNT_WEST_XZ
    east_x, east_z = part.POST_MOUNT_EAST_XZ
    assert math.isclose(west_x, half * math.cos(math.radians(part.INCLINE_DEG)))
    assert math.isclose(east_x, -west_x)
    assert math.isclose(west_z - part.POST_LOCAL_Z, part.POST_MOUNT_DZ)
    assert math.isclose(east_z - part.POST_LOCAL_Z, -part.POST_MOUNT_DZ)
    assert math.isclose(math.hypot(west_x - east_x, west_z - east_z), 2.0 * half)
    assert part.POST_MOUNT_SPEC.kind == "tapped"
    assert part.POST_MOUNT_SPEC.size == cone_swing_platform_spec.POST_MOUNT_THREAD
    assert part.POST_MOUNT_SPEC.end == "through_all"

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PostMountHoles"' in source
    assert 'name_last_feature(adapter, "CrankGearRelief")' not in source
    assert 'name_last_feature(adapter, "PivotBearingRelief")' in source
    assert '("PivotBearingTop", "PLANE")' in source
    assert "name_last_feature(adapter, axis_name)" in source
    assert '("post mount west", POST_MOUNT_WEST_XZ)' in source
    assert '("post mount east", POST_MOUNT_EAST_XZ)' in source


def test_recentered_crank_gear_clears_the_full_thickness_platform() -> None:
    assert cone_swing_platform_spec.CRANK_GEAR_PLATFORM_CLEARANCE > 0.5


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 2)") == 2
    assert source.count("scale=(1, 3)") == 1


def test_rederived_plate_layout_stays_inside_the_sheet_zones() -> None:
    assert drawing.TOP_CENTER == (0.115, 0.195)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "callout_xy=(0.170, 0.135)" in source
    assert "callout_xy=(0.175, 0.225)" in source
    assert '"Manufacturing Notes", 0.016, 0.100, char_height=0.0025' in source
    assert cone_swing_platform_spec.PLAN_VIEW_NOTE == "PLAN VIEW SCALE 1:2"
    assert cone_swing_platform_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:3"
    assert cone_swing_platform_spec.END_VIEW_NOTE == "END VIEW SCALE 1:2"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-swing-platform")
    assert config["material"] == config["material_specification"]
    assert (
        "astm a830/a830m gr 1018 hr steel plate"
        in str(config["material_specification"]).lower()
    )
    assert "5/16 in minimum stock" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "mil-dtl-13924 class 1" in finish
    assert "oil seal" in finish
    assert int(config["quantity"]) == 1
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "dia_tolerance_mm=(0.0, 0.10)" in part_source
