"""Static ownership contracts for the first surface-finish migration cohort."""

from __future__ import annotations

import inspect

import dt_alignment_pinion_spec
import dt_arbor_pedestal_spec
import build_dt_alignment_pinion
import build_dt_arbor_pedestal
import build_dt_cone_gear
import build_dt_cone_gear_shaft
import build_dt_cone_swing_platform
import build_ch_connecting_rod
import build_dt_crank_drive_gear
import build_dt_crank_pinion
import build_dt_crankshaft
import build_dt_cylinder_gear_shaft
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec
import dt_cone_swing_platform_spec
import ch_connecting_rod_spec
import dt_crank_drive_gear_spec
import dt_crank_pinion_spec
import dt_crankshaft_spec
import dt_cylinder_gear_shaft_spec
import draw_dt_alignment_pinion
import draw_dt_arbor_pedestal
import draw_dt_cone_gear
import draw_dt_cone_gear_shaft
import draw_dt_cone_swing_platform
import draw_ch_connecting_rod
import draw_dt_crank_drive_gear
import draw_dt_crank_pinion
import draw_dt_crankshaft
import draw_dt_cylinder_gear_shaft
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _surface_finish import MACHINED_UM, SEAT_UM, SurfaceFinishControl


CASES = (
    (
        dt_alignment_pinion_spec,
        build_dt_alignment_pinion,
        draw_dt_alignment_pinion,
        (
            SurfaceFinishControl(
                "drum_bore", MACHINED_UM, CylinderFace(dt_alignment_pinion_spec.BORE_DIA)
            ),
        ),
    ),
    (
        dt_arbor_pedestal_spec,
        build_dt_arbor_pedestal,
        draw_dt_arbor_pedestal,
        (
            SurfaceFinishControl(
                "arbor_bore",
                MACHINED_UM,
                CylinderFace(
                    dt_arbor_pedestal_spec.BORE_DIA,
                    contains_y_mm=dt_arbor_pedestal_spec.BORE_HEIGHT,
                ),
            ),
            SurfaceFinishControl(
                "foot_seat",
                SEAT_UM,
                PlanarFace((0, -1, 0), 0.0),
            ),
        ),
    ),
    (
        dt_cone_gear_spec,
        build_dt_cone_gear,
        draw_dt_cone_gear,
        (
            SurfaceFinishControl(
                "cone_gear_bore",
                MACHINED_UM,
                CylinderFace(dt_cone_gear_spec.BORE_DIA),
                native_attachment="model",
            ),
        ),
    ),
    (
        dt_cone_gear_shaft_spec,
        build_dt_cone_gear_shaft,
        draw_dt_cone_gear_shaft,
        (
            SurfaceFinishControl(
                "pivot_journal",
                MACHINED_UM,
                CylinderFace(dt_cone_gear_shaft_spec.JOURNAL_DIA),
            ),
            SurfaceFinishControl(
                "tip_land",
                MACHINED_UM,
                CylinderFace(dt_cone_gear_shaft_spec.SECTION_DIAS[-1], tolerance_mm=0.01),
            ),
        ),
    ),
    (
        dt_cone_swing_platform_spec,
        build_dt_cone_swing_platform,
        draw_dt_cone_swing_platform,
        (
            SurfaceFinishControl(
                "post_seat",
                SEAT_UM,
                PlanarFace((0, 1, 0), dt_cone_swing_platform_spec.PLATE_THICKNESS),
            ),
            SurfaceFinishControl("base_slide", MACHINED_UM, PlanarFace((0, -1, 0), 0.0)),
        ),
    ),
    (
        ch_connecting_rod_spec,
        build_ch_connecting_rod,
        draw_ch_connecting_rod,
        (
            SurfaceFinishControl(
                "strap_bore",
                MACHINED_UM,
                CylinderFace(ch_connecting_rod_spec.RING_BORE_DIA),
            ),
        ),
    ),
    # crank_arm: no finish controls -- the arm is pinned to its shaft, nothing
    # runs on the bore (drawing-simplicity-policy.md rule 5); its empty tuple is
    # pinned by test_crank_arm_drawing.
    (
        dt_crank_drive_gear_spec,
        build_dt_crank_drive_gear,
        draw_dt_crank_drive_gear,
        (
            SurfaceFinishControl(
                "crank_drive_gear_bore",
                MACHINED_UM,
                CylinderFace(dt_crank_drive_gear_spec.BORE_DIA),
            ),
        ),
    ),
    (
        dt_crank_pinion_spec,
        build_dt_crank_pinion,
        draw_dt_crank_pinion,
        (
            SurfaceFinishControl(
                "crank_pinion_bore",
                MACHINED_UM,
                CylinderFace(dt_crank_pinion_spec.BORE_DIA),
            ),
        ),
    ),
    (
        dt_crankshaft_spec,
        build_dt_crankshaft,
        draw_dt_crankshaft,
        (
            SurfaceFinishControl(
                "outboard_journal",
                MACHINED_UM,
                CylinderFace(
                    dt_crankshaft_spec.JOURNAL_DIA,
                    contains_y_mm=(
                        dt_crankshaft_spec.JOURNAL_START + dt_crankshaft_spec.RELIEF_START
                    )
                    / 2.0,
                ),
            ),
            SurfaceFinishControl(
                "inboard_journal",
                MACHINED_UM,
                CylinderFace(
                    dt_crankshaft_spec.JOURNAL_DIA,
                    contains_y_mm=(dt_crankshaft_spec.RELIEF_END + dt_crankshaft_spec.JOURNAL_END)
                    / 2.0,
                ),
            ),
            SurfaceFinishControl(
                "collar_rear_face",
                MACHINED_UM,
                PlanarFace((0, 1, 0), dt_crankshaft_spec.COLLAR_REAR),
            ),
        ),
    ),
    (
        dt_cylinder_gear_shaft_spec,
        build_dt_cylinder_gear_shaft,
        draw_dt_cylinder_gear_shaft,
        (
            SurfaceFinishControl(
                "arbor_bearing",
                MACHINED_UM,
                CylinderFace(
                    dt_cylinder_gear_shaft_spec.SHAFT_DIA,
                    contains_y_mm=dt_cylinder_gear_shaft_spec.ARBOR_BEARING_PROBE_Y_MM,
                ),
            ),
        ),
    ),
)


def test_specs_own_exact_surface_finish_controls() -> None:
    for spec, _build, _drawing, expected in CASES:
        assert spec.SURFACE_FINISHES == expected


def test_builds_author_and_drawings_consume_spec_owned_finishes() -> None:
    for _spec, build, drawing, controls in CASES:
        build_source = inspect.getsource(build)
        drawing_source = inspect.getsource(drawing)
        assert "surface_finishes=SURFACE_FINISHES" in build_source
        assert "roughness_ra=" not in drawing_source
        assert "production_method=" not in drawing_source
        for control in controls:
            assert (
                f'control=surface_finish_by_key(SURFACE_FINISHES, "{control.key}")'
                in drawing_source
            )
