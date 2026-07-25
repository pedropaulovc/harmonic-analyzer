"""Offline contracts for the cone-swing-platform drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_cone_swing_platform as part
import cone_swing_platform_spec
import draw_cone_swing_platform as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_common import _gtol_frame_xml


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
    assert "AXIS PERPENDICULARITY TO A: SEE FCF" in notes
    assert "24.50 +/-0.10 WEST AND 190.10 +/-0.10 SOUTH" in notes
    assert "2X 1/4-20 UNC-2B THRU" in notes
    assert "235.901 +/-0.10 SOUTH OF PIVOT" in notes
    assert "26.887" in notes
    assert "12.5182 +/-0.10 DEG NORTH OF WEST" in notes
    assert "7.35 +/-0.10 DEG NORTH" in notes
    assert "FULL-R CLOSED END (R4.000 REF)" in notes
    assert "VIRTUAL-SHARP INTERSECTIONS" in notes
    assert "DATUM B IS THE" in notes
    assert "PIVOT-HOLE AXIS" in notes
    assert "DATUM C IS THE NORTH END PLANE" in notes
    assert "CENTRELINE THROUGH B NORMAL TO C" in notes
    assert "LONG STRAIGHT PLAN-EDGE FORM: SEE STRAIGHTNESS FCF" in notes
    assert "OPEN THROUGH EDGE" in notes
    assert "NE R10.00, NW R8.00, SW R10.00, SE R12.00" in notes
    assert "CRANK-GEAR RELIEF: CYLINDRICAL SCALLOP R34.130" in notes
    assert "39.718 BASIC ABOVE A" in notes
    assert "176.100 BASIC SOUTH OF PIVOT" in notes
    assert "LEAVE 5.588 MIN PLATE THICKNESS" in notes
    assert "FINISHED THICKNESS 6.35 +/-0.10" in notes
    assert "OPPOSITE-FACE PARALLELISM: SEE END VIEW" in notes
    assert "AS MODELLED" not in notes
    assert "SEE PLAN" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "pivot_center = _add_cone_axis_centerline(adapter, top)" in source
    assert "view.ModelToViewTransform" in source
    assert "view.GetVisibleEntities2" in source
    assert "blind_cut_dia_mm(PIVOT_HOLE_SPEC)" in source
    assert "curve.CircleParams" in source
    assert "pivot_centers" in source
    assert "view.GetOutline()" in source
    assert "projected pivot center" in source
    assert "drawing.EditSheet()" in source
    assert "drawing.EditSketch()" not in source
    assert "_visible_broad_face_edges(adapter, end)" in source
    assert "_visible_plan_controls(" in source
    assert 'label="pivot-hole size"' in source and "edge=pivot_edge" in source
    assert 'label="v2 post-mount tapped holes"' in source
    assert "edge=mount_edge" in source
    assert 'datum="B"' in source
    assert 'label="pivot-hole cylindrical datum feature"' in source
    assert "symbol_xy=(pivot_center[0] - 0.010, pivot_center[1])" in source
    assert "entity=pivot_edge" in source
    assert "shoulder=True" in source
    assert (
        '        label="pivot-hole cylindrical datum feature",\n'
        "        entity=pivot_edge,\n"
        "        shoulder=True,\n"
        "        position_tolerance_m=0.004,"
        in source
    )
    assert source.count("position_tolerance_m=0.004") == 1
    assert "annotation=pivot_callout.GetAnnotation()" not in source
    assert 'datum="C"' in source and "entity=north_edge" in source
    assert "symbol_xy=(0.100, 0.135)" in source
    assert 'characteristic="profile_surface"' not in source
    assert 'characteristic="straightness"' in source
    assert 'quantity="2X LONG STRAIGHT PLAN EDGES"' in source
    assert 'characteristic="perpendicularity"' in source
    assert 'quantity="PIVOT-HOLE AXIS"' in source
    assert "diameter=True" in source
    assert 'datums=("A",)' in source
    assert 'characteristic="flatness"' in source
    assert 'characteristic="parallelism"' in source
    assert '{"PlateLenDim": "+/-0.25"}' in source


def test_v2_post_foot_and_mount_pattern_cascade() -> None:
    assert part.PLATE_LEN == 266.0
    assert part.EAST_HALF_S == 24.0
    assert part.POST_STATION == -39.90136099793
    assert part.PIVOT_STATION == 196.0
    assert math.isclose(part.POST_LOCAL_Z, -235.90136099793, abs_tol=1e-12)
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
    assert 'name_last_feature(adapter, "CrankGearRelief")' in source
    assert 'name_last_feature(adapter, axis_name)' in source
    assert '("post mount west", POST_MOUNT_WEST_XZ)' in source
    assert '("post mount east", POST_MOUNT_EAST_XZ)' in source


def test_v2_crank_gear_relief_covers_the_swept_envelope() -> None:
    assert math.isclose(part.GEAR_RELIEF_CENTER_Z, -176.1, abs_tol=1e-12)
    assert math.isclose(part.GEAR_RELIEF_WIDTH, 10.5, abs_tol=1e-12)
    assert math.isclose(part.GEAR_RELIEF_AXIS_Y, 39.718, abs_tol=1e-12)
    assert math.isclose(part.GEAR_RELIEF_MAX_DEPTH, 0.762355699, abs_tol=1e-6)
    assert part.GEAR_RELIEF_RESIDUAL_THICKNESS > 5.5
    assert part.GEAR_RELIEF_SOUTH_Z < part.GEAR_RELIEF_CENTER_Z
    assert part.GEAR_RELIEF_NORTH_Z > part.GEAR_RELIEF_CENTER_Z


def test_straightness_uses_native_gdt_symbol() -> None:
    xml = _gtol_frame_xml("straightness", "0.25")
    assert "GTOL-STRAIGHT" in xml
    assert "DatumCompartment" not in xml


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 2)") == 2
    assert source.count("scale=(1, 3)") == 1
    assert cone_swing_platform_spec.PLAN_VIEW_NOTE == "PLAN VIEW SCALE 1:2"
    assert (
        cone_swing_platform_spec.ISOMETRIC_VIEW_NOTE
        == "ISOMETRIC VIEW SCALE 1:3"
    )
    assert cone_swing_platform_spec.END_VIEW_NOTE == "END VIEW SCALE 1:2"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-swing-platform")
    assert config["material"] == config["material_specification"]
    assert "astm a830/a830m gr 1018 hr steel plate" in str(
        config["material_specification"]
    ).lower()
    assert "5/16 in minimum stock" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "mil-dtl-13924 class 1" in finish
    assert "oil seal" in finish
    assert int(config["quantity"]) == 1
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "dia_tolerance_mm=(0.0, 0.10)" in part_source
