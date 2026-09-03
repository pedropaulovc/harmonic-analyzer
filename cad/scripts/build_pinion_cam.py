r"""Reproduction script: pinion lift cam (book ch. 25; 2 used, PR8).

The eccentric steel collar pinned to the lift rod at each strap station
(``page001_img01`` back-tail close-up): the strap's follower pin RESTS
ON its OD from above, so turning the lever (rod + both cams spin as
one) raises the surface under the pin and swings the drum into mesh.
Photo reads at 9.45 px/mm against the Ø6.35 rods: collar OD ~9.5, a
~Ø3.2 set-pin dome proud of the OD (locks the collar to the rod and
stops axial drift -- review item 8b), pin-on-collar tangency at park.

Eccentricity 1.4 after the v2 drive-line closure provides 2.8 full lift.  The
low-confidence photo OD is reclosed to 10.32 so that the thin side retains the
stated 0.575-mm wall over the Ø6.37 bore; the former Ø9.2 literal left only
0.015 mm and was not manufacturable.

Layout: bore axis Z through the ORIGIN (rides the rod), authored in the
PARK pose -- collar centre at (0, -ECC), heavy side and the set-pin
boss straight DOWN, so the OD top is at its lowest (disengaged rest).
Collar z 0..9; boss along -Y at z 2.5, 2.0 proud of the OD.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_cam.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pinion_cam_geometry import (
    BORE,
    BOSS_DIA,
    BOSS_PROUD,
    BOSS_Z,
    CAM_LEN,
    CAM_OD,
    ECC,
    TAP_DRILL_DIA,
)
from pinion_cam_spec import (
    BORE_BAND,
    BOSS_DIA_TOLERANCE_MM,
    BOSS_PROJECTION_TOLERANCE_MM,
    COLLAR_DEPTH_TOLERANCE_MM,
    COLLAR_OD_TOLERANCE_MM,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    SURFACE_FINISHES,
)

PART_NAME = "pinion-cam"
MATERIAL = "Plain Carbon Steel"  # bright steel collar (img01)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

CAM_R = CAM_OD / 2.0
BORE_R = BORE / 2.0
BOSS_R = BOSS_DIA / 2.0
# Boss tip y and an anchor INSIDE the collar at every boss radius: the collar
# surface below the centre (0, -ECC) along the boss axis plane spans
# y = -ECC - sqrt(CAM_R^2 - x^2) for |x| <= BOSS_R -- deepest -5.75, shallowest
# -ECC - sqrt(CAM_R^2 - BOSS_R^2) = -5.47.
_BOSS_TIP_Y = -(ECC + CAM_R + BOSS_PROUD)  # -7.75
_BOSS_TOP_Y = -4.0  # fully inside the collar for all |x| <= BOSS_R

V_COLLAR = math.pi * (CAM_R**2 - BORE_R**2) * CAM_LEN


def _boss_added() -> float:
    """Boss volume OUTSIDE the collar OD: Simpson over x in [-BOSS_R, BOSS_R]
    of chord(x) * (surface(x) - tip), chord = the boss disc's z-extent."""
    n = 2000
    h = 2.0 * BOSS_R / n

    def f(x: float) -> float:
        chord = 2.0 * math.sqrt(max(BOSS_R**2 - x * x, 0.0))
        surface = -(ECC + math.sqrt(max(CAM_R**2 - x * x, 0.0)))
        return chord * (surface - _BOSS_TIP_Y)

    s = f(-BOSS_R) + f(BOSS_R)
    s += 4.0 * sum(f(-BOSS_R + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-BOSS_R + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


V_BOSS = _boss_added()  # ~17.5


def _tap_drill_removed() -> float:
    """Volume from the boss tip through to the existing rod bore."""
    tap_r = TAP_DRILL_DIA / 2.0
    n = 2000
    h = 2.0 * tap_r / n

    def f(x: float) -> float:
        chord = 2.0 * math.sqrt(max(tap_r**2 - x * x, 0.0))
        bore_wall_y = -math.sqrt(max(BORE_R**2 - x * x, 0.0))
        return chord * (bore_wall_y - _BOSS_TIP_Y)

    s = f(-tap_r) + f(tap_r)
    s += 4.0 * sum(f(-tap_r + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-tap_r + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


V_TAP_DRILL = _tap_drill_removed()


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "CamOd", f"{CAM_OD}mm")
    await set_global(adapter, "CamLen", f"{CAM_LEN}mm")
    await set_global(adapter, "Ecc", f"{ECC}mm")
    await set_global(adapter, "BoreDia", f"{BORE}mm")
    await set_global(adapter, "BossDia", f"{BOSS_DIA}mm")
    await set_global(adapter, "BossProjection", f"{BOSS_PROUD}mm")
    await set_global(adapter, "TapDrillDia", f"{TAP_DRILL_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Collar: circle centred ECC below the bore/origin, extruded z 0..CAM_LEN.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        -ECC,
        CAM_R,
        "collar",
        dims=collar,
        names=("CollarCx", "CollarCy", "CollarOd"),
        drives=(None, '"Ecc"', '"CamOd"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=CAM_LEN)),
    )
    name_last_feature(adapter, "Collar")
    depth_dim = name_dimensions(adapter, "Collar", ["Depth"])
    drive_jobs += [(depth_dim[0], '"CamLen"')]
    v_solid = math.pi * CAM_R**2 * CAM_LEN
    volume = await volume_check(adapter, "collar", v_solid, 0.005 * v_solid)

    # Rod bore on the origin axis (fully inside the collar: ECC + BORE_R =
    # 4.175 < CAM_R).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "bore",
        dims=bore,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * CAM_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", V_COLLAR, 0.005 * V_COLLAR)

    # Set-pin boss (item 8b): a radial stub straight DOWN the heavy side,
    # 2.0 proud of the OD -- the img01 dome. Top sketch (u, v) -> (X, -Z);
    # extruded -Y from an anchor plane fully inside the collar.
    boss = SketchDims()
    check("create_sketch boss", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -BOSS_Z,
        BOSS_R,
        "set-pin boss",
        dims=boss,
        names=("BossCx", "BossCz", "BossDia"),
        drives=(None, None, '"BossDia"'),
    )
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProfile")
    drive_jobs += boss.apply(adapter, "BossProfile")
    boss_root_y = -(ECC + CAM_R)
    extrude_at_offset(adapter, _BOSS_TOP_Y - boss_root_y, boss_root_y)
    name_last_feature(adapter, "SetPinBossRoot")

    # A second, coaxial extrusion carries only the projection beyond the OD's
    # lowest tangent plane. Its depth is therefore the actual make-critical
    # projection, not prose derived from the full embedded boss length.
    projection = SketchDims()
    check("create_sketch boss projection", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -BOSS_Z,
        BOSS_R,
        "set-pin boss projection",
        dims=projection,
        names=("ProjectionCx", "ProjectionCz", "ProjectionDia"),
        drives=(None, None, '"BossDia"'),
    )
    await ensure_fully_defined(adapter, "boss projection sketch")
    check("exit_sketch boss projection", await adapter.exit_sketch())
    name_last_feature(adapter, "BossProjectionProfile")
    drive_jobs += projection.apply(adapter, "BossProjectionProfile")
    extrude_at_offset(adapter, BOSS_PROUD, _BOSS_TIP_Y)
    name_last_feature(adapter, "SetPinBossProjection")
    projection_dim = name_dimensions(
        adapter, "SetPinBossProjection", ["BossProjection"]
    )
    drive_jobs += [(projection_dim[0], '"BossProjection"')]
    volume = await volume_check(adapter, "set-pin boss", volume + V_BOSS, 0.1 * V_BOSS)

    # M2.5 x 0.45 tap drill, cut from the boss tip into the existing rod bore.
    # The drawing releases the final 6H thread and minimum full-thread length;
    # this pilot geometry makes the machining operation part of the model too.
    check(
        "create_plane tap drill at boss tip",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=_BOSS_TIP_Y,
            )
        ),
    )
    tap_plane_name = name_last_feature(adapter, "TapDrillPlane")
    tap = SketchDims()
    check(
        "create_sketch tap drill",
        await adapter.create_sketch(tap_plane_name),
    )
    await define_circle(
        adapter,
        0.0,
        -BOSS_Z,
        TAP_DRILL_DIA / 2.0,
        "tap drill",
        dims=tap,
        names=("TapCx", "TapCz", "TapDrillDia"),
        drives=(None, None, '"TapDrillDia"'),
    )
    await ensure_fully_defined(adapter, "tap-drill sketch")
    check("exit_sketch tap drill", await adapter.exit_sketch())
    name_last_feature(adapter, "TapDrillProfile")
    drive_jobs += tap.apply(adapter, "TapDrillProfile")
    check(
        "cut M2.5 tap drill to bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=-_BOSS_TIP_Y,
            )
        ),
    )
    name_last_feature(adapter, "M2.5TapDrill")
    volume -= V_TAP_DRILL
    await volume_check(adapter, "M2.5 tap drill", volume, 0.05 * V_TAP_DRILL)

    # Named bore axis for the rod mate (Axis1).
    cam_bore_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "cam bore axis"
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cam (equations neutral)", volume, 0.01 * V_COLLAR
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "CollarProfile", "CollarOd", COLLAR_OD_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "Collar", "Depth", COLLAR_DEPTH_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "BossProfile", "BossDia", BOSS_DIA_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "SetPinBossProjection",
        "BossProjection",
        BOSS_PROJECTION_TOLERANCE_MM,
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_geometry(
        adapter,
        (("TapDrillPlane", "PLANE"), (cam_bore_axis, "AXIS")),
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
