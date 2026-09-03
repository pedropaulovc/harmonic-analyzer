"""Offline contracts for the cone-swing-platform drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_cone_swing_platform as part
import cone_swing_platform_spec
import draw_cone_swing_platform as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-swing-platform.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-swing-platform.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-swing-platform_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_swing_platform"].script
        == Path(drawing.__file__).resolve()
    )


def test_unavailable_detail_dimensions_are_replaced_by_build_derived_note() -> None:
    assert part.DRAWING_DIMENSIONS is cone_swing_platform_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_swing_platform_spec.DRAWING_DIMENSIONS.values())
    unavailable = {
        "NorthHalfW",
        "NorthOverhangDim",
        "NorthEdge",
        "CornerNER",
        "CornerNWR",
    }
    imported = set(drawing.TOP_KEEP) | set(drawing.END_KEEP)
    assert imported == marked - unavailable
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert all(name not in source for name in unavailable)
    assert 'view_label="detail"' not in source
    assert cone_swing_platform_spec.DRAWING_DIMENSIONS["LockNotchCapEProfile"] == {
        "CapECx",
        "CapECz",
        "CapEDia",
    }
    assert drawing.END_KEEP == {
        "PlateT": (drawing.END_CENTER[0] + 0.026, drawing.END_CENTER[1])
    }
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Plate", ["PlateT"])' in part_source
    assert 'name_dimensions(adapter, f"Corner{lbl}", [f"Corner{lbl}R"])' in part_source


def test_pivot_end_detail_retains_geometry_and_uses_a_spec_note() -> None:
    # DETAIL A remains because it clarifies the pivot profile, but the native
    # hole callout stays on the main plan's model rim: the derived detail does
    # not expose that rim through SolidWorks' visible-entity API.
    assert drawing.DETAIL_SCALE == (1, 1)
    assert drawing.DETAIL_MODEL_RADIUS > part.HALF_WIDTH_N + part.NORTH_OVERHANG
    north_radii = {
        label: radius
        for label, _x, _z, radius in part._CORNERS
        if label in {"NE", "NW"}
    }
    assert drawing.PIVOT_END_GEOMETRY_NOTE == "\n".join(
        (
            "DETAIL A PIVOT-END PROFILE",
            (
                f"FROM PIVOT C/L: EAST {part.HALF_WIDTH_N:.2f}; "
                f"NORTH {part.NORTH_OVERHANG:.2f}"
            ),
            (
                f"NORTH EDGE {part.HALF_WIDTH_N + part.WEST_HALF_N:.2f}; "
                f"NE R{north_radii['NE']:.1f}; NW R{north_radii['NW']:.1f}"
            ),
        )
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'detail_label="A"' in source
    assert "for view in (top, end, detail):\n        set_hidden_lines_visible" in source
    assert "add_note(adapter, PIVOT_END_GEOMETRY_NOTE" in source
    assert "edge=pivot_edge" in source
    assert "adapter,\n        top,\n        callout_xy=PIVOT_CALLOUT_XY" in source
    assert "edge=_pivot_rim(adapter, detail)" not in source


def test_manufacturing_notes_orient_the_reader_and_carry_no_dimension() -> None:
    notes = cone_swing_platform_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "PIVOT END IS NORTH; NOTCH SIDE IS WEST" in notes
    assert "STATIONS ARE FROM THE PIVOT HOLE" in notes
    # The one value the sketch does not dimension, the notch axis angle,
    # prints ONE place from the seat coordinates the build cuts from; the
    # old note's 8.23 was not atan(27.5 / 175).
    assert "LOCK NOTCH AXIS 8.9 DEG NORTH OF WEST" in notes
    assert cone_swing_platform_spec.LOCK_NOTCH_ANGLE_DEG == pytest.approx(
        math.degrees(math.atan2(27.5, 175.0))
    )
    assert part.SLOT_E_X == cone_swing_platform_spec.LOCK_NOTCH_SEAT_X == 27.5
    assert part.SLOT_E_Z == cone_swing_platform_spec.LOCK_NOTCH_SEAT_Z == -175.0
    # Imported stations, offsets, south radii and thickness remain native.
    # The separate pivot-end geometry note owns only the five unavailable
    # values.
    for banned in (
        "12.00 E",
        "16.00 E",
        "8.00 W",
        "24.00 E",
        "37.00 W",
        "7.00 SOUTH",
        "192.174",
        "26.887",
        "12.518",
        "8.23",
        "R10",
        "R8",
        "R12",
        "6.35",
        "HOLE TABLE",
        "MACHINE BOTH BROAD FACES",
        "VIRTUAL-SHARP",
        "+/-",
        "WITHIN",
        "HOLD",
        "DATUM",
        "FCF",
        "REF",
        "STEEL PLATE",
        "BLACK OXIDE",
        "DEBURR",
        "UOS",
        "X.XX",
        "UNC",
    ):
        assert banned not in notes, banned
    assert drawing.NOTES_XY == (0.016, 0.088)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025' in source


def test_axis_centerline_and_controls_come_from_the_model() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
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
    assert (
        "pivot_edge, west_edge, east_edge = _visible_plan_controls(adapter, top)"
        in source
    )


def test_hole_callouts_state_size_and_process() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Harvey #13: the pivot callout says DRILL; 1/4 close clearance is the H drill.
    assert 'process="H DRILL"' in source
    assert round(0.266 * 25.4, 3) == round(part.PIVOT_HOLE_DIA, 3)
    # Two native callouts: the pivot (in the detail) and the 2X post-mount
    # taps (on the plan, the fleet-wide through-tap fix makes it read THRU).
    assert source.count("add_native_hole_callout(") == 2
    assert 'label="v2 post-mount tapped holes"' in source and "edge=west_edge" in source
    assert 'remove_notes_matching(adapter, "Tapped Hole")' in source
    # No hole table: it anchors only on a vertex, and the pivot is a hole.
    assert "insert_hole_table" not in source


def test_post_mounts_are_located_from_the_pivot_by_entity_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Four entity-selected rim-to-rim dimensions: the east hole's offset
    # across the axis, the pair's pitch, and each hole's station along the
    # axis from the pivot -- the DRO frame the notes name.
    assert source.count("    _entity_dimension(\n") == 4
    for label in (
        'label="east mount offset from the axis"',
        'label="mount pitch across the axis"',
        'label="west mount station from the pivot"',
        'label="east mount station from the pivot"',
    ):
        assert label in source, label
    assert "set_arc_endpoints_to_center(adapter, display, label=label)" in source
    # Stations on their own side of the plate, offsets above the south end
    # under the notch offset and the south edge (shortest nearest).
    assert drawing.WEST_STATION_TEXT_XY[0] > drawing._SW[0]
    assert drawing.EAST_STATION_TEXT_XY[0] < drawing._SE[0]
    assert (
        drawing._SOUTH_Y
        < drawing.EAST_OFFSET_TEXT_XY[1]
        < drawing.PITCH_TEXT_XY[1]
        < drawing.TOP_KEEP["CapECx"][1]
        < drawing.TOP_KEEP["SouthEdge"][1]
    )


def test_notch_closed_end_is_dimensioned_beside_the_notch() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"CapEDia": "NOTCH WIDTH"}
    assert "CapECx" in drawing.TOP_KEEP and "CapECz" in drawing.TOP_KEEP
    assert "CapEDia" in drawing.TOP_KEEP
    # The notch station reads on the west side, nearer than the west mount's.
    assert (
        drawing._SW[0] < drawing.TOP_KEEP["CapECz"][0] < drawing.WEST_STATION_TEXT_XY[0]
    )
    # The notch diameter and the south radii are leadered from above the
    # station dimensions' spans (their tops are at the features), never
    # across them.
    assert drawing.TOP_KEEP["CapEDia"][0] > drawing.WEST_STATION_TEXT_XY[0]
    assert drawing.TOP_KEEP["CapEDia"][1] > drawing._W_HOLE[1]
    assert drawing.TOP_KEEP["CornerSWR"][1] > drawing._SOUTH_Y
    assert drawing.TOP_KEEP["CornerSER"][1] > drawing._SOUTH_Y
    assert drawing.TOP_KEEP["CornerSER"][0] < drawing._SE[0]
    assert drawing.TOP_KEEP["CornerSWR"][0] > drawing._SW[0]


def test_south_radii_print_one_place_and_nothing_is_banded() -> None:
    assert drawing.DIMENSION_PRECISION == {
        "CornerSWR": 1,
        "CornerSER": 1,
    }
    # The 223.35 length used to carry +/-0.25: a non-mating extent under the
    # title block now, and the model carries no band (the pivot hole's fit
    # rides its wizard feature).
    assert not hasattr(cone_swing_platform_spec, "PLATE_LENGTH_TOLERANCE_MM")
    assert model_toleranced_dimensions(part) == {}
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "dia_tolerance_mm=(0.0, 0.10)" in part_source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "datum=",
        "characteristic=",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_swing_platform_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(cone_swing_platform_spec, "SURFACE_FINISHES")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (top, end, detail):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_v2_post_foot_and_mount_pattern_cascade() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert part.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert part.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert part.WEST_HALF_N == 8.0
    assert part.EAST_HALF_S == 24.0
    assert part.SLOT_E_X == 27.5
    assert part.POST_STATION == -39.90136099793
    assert part.PIVOT_STATION == 152.27232594770453
    assert math.isclose(part.POST_LOCAL_Z, -192.17368694563453, abs_tol=1e-12)
    assert part.POST_MAIN_DIA == 42.011
    assert part.POST_FOOT_CONTAINMENT >= 0.25

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
    assert "scale=DETAIL_SCALE" in source


def test_plan_layout_stays_inside_the_sheet_zones() -> None:
    assert drawing.TOP_CENTER == (0.115, 0.172)
    assert drawing.DETAIL_CENTER == (0.240, 0.150)
    assert drawing.ISO_CENTER == (0.355, 0.225)
    assert drawing.END_CENTER == (0.340, 0.095)
    # Sheet map of the plan: the pivot end (north, +z) is at the BOTTOM.
    pivot = drawing._plan_xy(0.0, 0.0)
    south = drawing._plan_xy(0.0, part.PLATE_SOUTH_Z)
    assert pivot[1] < south[1]
    assert drawing.TOP_KEEP["SouthEdge"][1] < 0.2667  # inside the top border
    assert drawing.TOP_KEEP["PlateLenDim"][0] >= 0.020  # inside the frame margin
    assert drawing.TOP_KEEP["WestTaperDx"][1] < drawing._NORTH_Y
    assert drawing.MOUNT_CALLOUT_XY[0] > drawing.WEST_STATION_TEXT_XY[0]
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
