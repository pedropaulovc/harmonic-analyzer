"""Static ownership contracts for the first surface-finish migration cohort."""

from __future__ import annotations

import inspect

import alignment_pinion_spec
import arbor_pedestal_spec
import build_alignment_pinion
import build_arbor_pedestal
import build_cone_gear
import build_cone_gear_shaft
import build_cone_pivot_screw
import build_cone_tip_bushing
import build_connecting_rod
import build_crank_drive_gear
import build_crank_pinion
import build_crankshaft
import build_cylinder_gear
import build_cylinder_gear_shaft
import cone_gear_shaft_spec
import cone_gear_spec
import cone_pivot_screw_spec
import cone_tip_bushing_spec
import connecting_rod_spec
import crank_drive_gear_spec
import crank_pinion_spec
import crankshaft_spec
import cylinder_gear_shaft_spec
import cylinder_gear_spec
import draw_alignment_pinion
import draw_arbor_pedestal
import draw_cone_gear
import draw_cone_gear_shaft
import draw_cone_pivot_screw
import draw_cone_tip_bushing
import draw_connecting_rod
import draw_crank_drive_gear
import draw_crank_pinion
import draw_crankshaft
import draw_cylinder_gear
import draw_cylinder_gear_shaft
from _gtol_spec import CylinderFace
from _surface_finish import GROUND_UM, MACHINED_UM, SurfaceFinishControl


CASES = (
    (
        alignment_pinion_spec,
        build_alignment_pinion,
        draw_alignment_pinion,
        (
            SurfaceFinishControl(
                "drum_bore", MACHINED_UM, CylinderFace(alignment_pinion_spec.BORE_DIA)
            ),
        ),
    ),
    (
        arbor_pedestal_spec,
        build_arbor_pedestal,
        draw_arbor_pedestal,
        (
            SurfaceFinishControl(
                "arbor_bore",
                MACHINED_UM,
                CylinderFace(
                    arbor_pedestal_spec.BORE_DIA,
                    contains_y_mm=arbor_pedestal_spec.BORE_HEIGHT,
                ),
            ),
        ),
    ),
    (
        cone_gear_spec,
        build_cone_gear,
        draw_cone_gear,
        (
            SurfaceFinishControl(
                "cone_gear_bore",
                MACHINED_UM,
                CylinderFace(cone_gear_spec.BORE_DIA),
                native_attachment="model",
            ),
        ),
    ),
    (
        cone_gear_shaft_spec,
        build_cone_gear_shaft,
        draw_cone_gear_shaft,
        (
            SurfaceFinishControl(
                "pivot_journal",
                MACHINED_UM,
                CylinderFace(cone_gear_shaft_spec.JOURNAL_DIA),
            ),
            SurfaceFinishControl(
                "tip_journal",
                MACHINED_UM,
                CylinderFace(
                    cone_gear_shaft_spec.SECTION_DIAS[-1], tolerance_mm=0.01
                ),
            ),
        ),
    ),
    (
        cone_pivot_screw_spec,
        build_cone_pivot_screw,
        draw_cone_pivot_screw,
        (
            SurfaceFinishControl(
                "ground_shoulder",
                GROUND_UM,
                CylinderFace(
                    cone_pivot_screw_spec.SHOULDER_DIA,
                    contains_y_mm=-cone_pivot_screw_spec.SHOULDER_LEN / 2.0,
                ),
            ),
        ),
    ),
    (
        cone_tip_bushing_spec,
        build_cone_tip_bushing,
        draw_cone_tip_bushing,
        (
            SurfaceFinishControl(
                "bushing_bore",
                MACHINED_UM,
                CylinderFace(
                    cone_tip_bushing_spec.BORE_DIA,
                    contains_y_mm=cone_tip_bushing_spec.LENGTH / 2.0,
                ),
            ),
        ),
    ),
    (
        connecting_rod_spec,
        build_connecting_rod,
        draw_connecting_rod,
        (
            SurfaceFinishControl(
                "strap_bore",
                MACHINED_UM,
                CylinderFace(connecting_rod_spec.RING_BORE_DIA),
            ),
        ),
    ),
    # crank_arm: no finish controls -- the arm is pinned to its shaft, nothing
    # runs on the bore (drawing-simplicity-policy.md rule 5); its empty tuple is
    # pinned by test_crank_arm_drawing.
    (
        crank_drive_gear_spec,
        build_crank_drive_gear,
        draw_crank_drive_gear,
        (
            SurfaceFinishControl(
                "crank_drive_gear_bore",
                MACHINED_UM,
                CylinderFace(crank_drive_gear_spec.BORE_DIA),
            ),
        ),
    ),
    (
        crank_pinion_spec,
        build_crank_pinion,
        draw_crank_pinion,
        (
            SurfaceFinishControl(
                "crank_pinion_bore",
                MACHINED_UM,
                CylinderFace(crank_pinion_spec.BORE_DIA),
            ),
        ),
    ),
    (
        crankshaft_spec,
        build_crankshaft,
        draw_crankshaft,
        (
            SurfaceFinishControl(
                "bearing_journal",
                MACHINED_UM,
                CylinderFace(
                    crankshaft_spec.JOURNAL_DIA,
                    contains_y_mm=(
                        crankshaft_spec.JOURNAL_START
                        + crankshaft_spec.JOURNAL_LENGTH / 2.0
                    ),
                ),
                production_method="BEARING JOURNAL",
            ),
        ),
    ),
    (
        cylinder_gear_spec,
        build_cylinder_gear,
        draw_cylinder_gear,
        (
            SurfaceFinishControl(
                "cylinder_gear_bore",
                MACHINED_UM,
                CylinderFace(cylinder_gear_spec.BORE_DIA),
            ),
        ),
    ),
    (
        cylinder_gear_shaft_spec,
        build_cylinder_gear_shaft,
        draw_cylinder_gear_shaft,
        (
            SurfaceFinishControl(
                "arbor_bearing",
                MACHINED_UM,
                CylinderFace(
                    cylinder_gear_shaft_spec.SHAFT_DIA,
                    contains_y_mm=cylinder_gear_shaft_spec.SHAFT_LENGTH / 2.0,
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
