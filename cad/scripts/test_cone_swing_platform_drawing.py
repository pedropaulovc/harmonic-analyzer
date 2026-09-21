"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import inspect
import math
from pathlib import Path

import _config
import build_cone_pivot_screw
import build_cone_swing_platform as part
import cone_pivot_post_spec
import cone_swing_platform_spec as spec
import draw_cone_swing_platform as drawing
import pytest
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_spec import PlanarFace
from _hole_spec import blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-swing-platform.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-swing-platform.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-swing-platform_drawing.png")
    assert DRAWINGS_BY_NAME["cone_swing_platform"].script == Path(
        drawing.__file__
    ).resolve()


def test_every_marked_model_dimension_has_one_view_and_native_precision() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    view_sets = (
        set(drawing.PROFILE_KEEP),
        set(drawing.FEATURE_KEEP),
        set(drawing.NOTCH_KEEP),
        set(drawing.SECTION_KEEP),
    )
    kept = set().union(*view_sets)
    assert kept == marked
    assert sum(len(names) for names in view_sets) == len(kept)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 1
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}


def test_pivot_preserves_native_close_clearance_hole() -> None:
    assert spec.PIVOT_HOLE_SPEC.kind == "clearance"
    assert spec.PIVOT_HOLE_SPEC.size == "1/4"
    assert spec.PIVOT_HOLE_SPEC.fit == "close"
    assert spec.PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_HOLE_DIA == blind_cut_dia_mm(spec.PIVOT_HOLE_SPEC)
    assert spec.PIVOT_HOLE_DIA == pytest.approx(6.756)
    assert spec.PIVOT_HOLE_DIA > build_cone_pivot_screw.SHOULDER_DIA
    build_source = inspect.getsource(part)
    drawing_source = inspect.getsource(drawing)
    assert "PIVOT_HOLE_SPEC" in build_source
    assert 'name="PivotHole"' in build_source
    assert "dia_tolerance_mm=(0.0, 0.10)" in build_source
    assert 'label="pivot close-clearance hole"' in drawing_source


def test_post_mount_pattern_is_derived_from_its_mating_post() -> None:
    assert spec.POST_ATTACHMENT_SPACING == cone_pivot_post_spec.ATTACHMENT_SPACING
    assert spec.POST_BLOCK_DIA == cone_pivot_post_spec.BLOCK_DIA
    assert part.POST_MOUNT_HALF_PITCH == spec.POST_ATTACHMENT_SPACING / 2.0
    assert math.isclose(
        math.hypot(
            part.POST_MOUNT_WEST_XZ[0] - part.POST_MOUNT_EAST_XZ[0],
            part.POST_MOUNT_WEST_XZ[1] - part.POST_MOUNT_EAST_XZ[1],
        ),
        spec.POST_ATTACHMENT_SPACING,
    )
    assert spec.POST_MOUNT_SPEC.kind == "tapped"
    assert spec.POST_MOUNT_SPEC.size == "1/4-20"
    assert spec.POST_MOUNT_SPEC.end == "through_all"
    assert spec.POST_MOUNT_TAP_DIA == blind_cut_dia_mm(spec.POST_MOUNT_SPEC)


def test_only_sliding_and_locating_surfaces_carry_roughness() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"post_seat", "base_slide"}
    assert by_key["post_seat"].roughness_um == SEAT_UM
    assert by_key["post_seat"].face == PlanarFace(
        (0, 1, 0), spec.PLATE_THICKNESS
    )
    assert by_key["base_slide"].roughness_um == MACHINED_UM
    assert by_key["base_slide"].face == PlanarFace((0, -1, 0), 0.0)
    build_source = inspect.getsource(part)
    drawing_source = inspect.getsource(drawing)
    assert "surface_finishes=SURFACE_FINISHES" in build_source
    assert "roughness_ra=" not in drawing_source
    for key in by_key:
        assert (
            f'control=surface_finish_by_key(SURFACE_FINISHES, "{key}")'
            in drawing_source
        )


def test_plate_and_nonfit_features_remain_at_general_grade() -> None:
    registry = _config.parts("cone-swing-platform")
    assert registry["tolerance_class"] == "machined_block"
    assert "steel plate" in str(registry["material_specification"]).lower()
    assert "5/16 in minimum stock" in str(registry["material_specification"]).lower()
    assert "mil-dtl-13924 class 1" in str(registry["finish"]).lower()
    assert "oil seal" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
    assert spec.DRAWING_PRECISION["Plate"]["PlateThk"] == 2
    assert spec.DRAWING_PRECISION["PivotBearingRelief"]["PivotBearingReliefDepth"] == 2
    assert spec.DRAWING_PRECISION["PostMountHoles"] == {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    }


def test_sheet_has_no_gdt_or_dimension_bearing_notes() -> None:
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "DRAWING_NOTES")
    source = inspect.getsource(drawing)
    assert "add_datum_feature" not in source
    assert "add_feature_control_frame" not in source
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source


def test_pivot_section_exposes_thickness_and_relief_depth() -> None:
    assert set(drawing.SECTION_KEEP) == {"PlateThk", "PivotBearingReliefDepth"}
    assert len({drawing.PROFILE_CENTER, drawing.FEATURE_CENTER, drawing.NOTCH_CENTER}) == 3
    assert spec.SECTION_VIEW_NOTE == "SCALE 2:1"
    assert spec.PROFILE_VIEW_NOTE == "PLATE PROFILE — SCALE 1:2"
    assert spec.FEATURE_VIEW_NOTE == "HOLE LOCATIONS — SCALE 1:2"
    assert spec.NOTCH_VIEW_NOTE == "LOCK NOTCH — SCALE 1:2"
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:3"
    assert drawing.SHEET_SCALE == (1.0, 3.0)


def test_geometry_cascade_and_interference_guards_stay_explicit() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert part.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert part.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert part.POST_MAIN_DIA == spec.POST_BLOCK_DIA
    assert part.POST_FOOT_CONTAINMENT >= 0.25
    assert spec.PIVOT_BEARING_RELIEF_DIAMETER == pytest.approx(10.50)
    assert part.PLATE_T - spec.PIVOT_BEARING_THICKNESS == pytest.approx(
        spec.PIVOT_BEARING_RELIEF_DEPTH
    )
    assert spec.CRANK_GEAR_PLATFORM_CLEARANCE > 0.5
