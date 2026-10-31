r"""Reproduction script: pinion lift cam (book ch. 25; 2 used, PR8).

The eccentric steel collar pinned to the lift rod at each strap station
(``page001_img01`` back-tail close-up): the strap's follower pin RESTS
ON its OD from above, so turning the lever (rod + both cams spin as
one) raises the surface under the pin and swings the drum into mesh.

U28 (user, 2026-09-23): Ø14.6 OD, eccentricity 2.0 (4.0 full lift), so the
thin side keeps 2.11 of wall over the Ø.2510 bore (#290; .07975 in at the
printed worst case, owner minor RV-01 under the .080 target).  The former
raised set-pin dome is gone -- a pad proud of a turned OD cannot be turned --
and a #2-56 set screw sits sub-flush in the 6.1-thick heavy side, which never
meets the follower.

Layout: bore axis Z through the ORIGIN (rides the rod), authored in the
PARK pose -- collar centre at (0, -ECC), heavy side and the set-screw
hole straight DOWN, so the OD top is at its lowest (disengaged rest).
Collar z 0..9; native radial tap enters at -Y, z SET_SCREW_Z = 4.1.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_pinion_cam.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _holes import wizard_hole_on_cylinder
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _single_limit_tolerance import set_single_limit
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from dt_pinion_cam_geometry import (
    BORE,
    CAM_LEN,
    CAM_OD,
    ECC,
    SET_SCREW_HOLE_SPEC,
    SET_SCREW_Z,
    TAP_DRILL_DIA,
)
from _named_views import name_octant_views
from dt_pinion_cam_spec import (
    BORE_BAND,
    COLLAR_AXIS_TOLERANCE_MM,
    COLLAR_OD_TOLERANCE_MM,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    SURFACE_FINISHES,
    THIN_WALL_MIN_BAND,
    THIN_WALL_MIN_MM,
    THIN_WALL_MIN_TOL_TYPE,
    UNIT,
)

PART_NAME = "dt-pinion-cam"
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
# The tap drill enters from the OD's lowest tangent plane (heavy side down).
_TAP_PLANE_Y = -(ECC + CAM_R)  # -9.3

V_COLLAR = math.pi * (CAM_R**2 - BORE_R**2) * CAM_LEN


def _tap_drill_removed() -> float:
    """Volume from the OD surface through to the existing rod bore: Simpson
    over x in [-tap_r, tap_r] of chord(x) * (bore wall - OD surface)."""
    tap_r = TAP_DRILL_DIA / 2.0
    n = 2000
    h = 2.0 * tap_r / n

    def f(x: float) -> float:
        chord = 2.0 * math.sqrt(max(tap_r**2 - x * x, 0.0))
        bore_wall_y = -math.sqrt(max(BORE_R**2 - x * x, 0.0))
        surface_y = -(ECC + math.sqrt(max(CAM_R**2 - x * x, 0.0)))
        return chord * (bore_wall_y - surface_y)

    s = f(-tap_r) + f(tap_r)
    s += 4.0 * sum(f(-tap_r + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-tap_r + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


V_TAP_DRILL = _tap_drill_removed()


async def _thin_wall_reference(adapter) -> list[tuple[str, str]]:
    """RV-01's accepted wall, stated on the sheet natively (rule 20): a hidden
    construction line up the thin side (+Y) from the bore's top, as long as
    the printed minimum, so its driving dimension prints ".0797 MIN" once
    set_single_limit types it.  Returns the deferred drive jobs (the length,
    then its anchor to the bore's top)."""
    check("create_sketch thin wall reference", await adapter.create_sketch("Front"))
    # Direct-to-DB: the line lies on the sketch's vertical axis, where
    # creation-time inference would over-define it.
    set_sketch_direct_db(adapter, True)
    line = check(
        "thin wall reference line",
        await adapter.add_line(0.0, BORE_R, 0.0, BORE_R + THIN_WALL_MIN_MM),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(
            "thin-wall reference line did not take the construction flag"
        )
    check(
        "thin wall reference vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        THIN_WALL_MIN_MM,
        "thin wall reference",
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", 0.0, BORE_R, "thin wall reference"
    )
    await ensure_fully_defined(adapter, "thin-wall reference sketch")
    check("exit_sketch thin wall reference", await adapter.exit_sketch())
    name_last_feature(adapter, "ThinWallReference")
    full = name_dimensions(
        adapter, "ThinWallReference", ["ThinWallMin", "ThinWallBore"]
    )
    return list(zip(full, ('"ThinWallMin"', '"BoreDia" / 2'), strict=True))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "CamOd", f"{CAM_OD}mm")
    await set_global(adapter, "CamLen", f"{CAM_LEN}mm")
    await set_global(adapter, "Ecc", f"{ECC}mm")
    await set_global(adapter, "BoreDia", f"{BORE}mm")
    await set_global(adapter, "SetScrewZ", f"{SET_SCREW_Z}mm")
    await set_global(adapter, "TapDrillDia", f"{TAP_DRILL_DIA}mm")
    # RV-01's printed thin-side wall minimum: a limit, not geometry, so only
    # the hidden reference line carries it.
    await set_global(adapter, "ThinWallMin", f"{THIN_WALL_MIN_MM}mm")

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
    # 5.188 < CAM_R).
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

    # Retain the drawing-owned tap-drill diameter and axial station in a
    # hidden, construction-only reference sketch. Top (u, v) -> (X, -Z).
    # The native radial Hole Wizard below, not this circle, cuts the tap.
    check(
        "create_plane tap drill at OD tangent",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Top Plane",
                offset=_TAP_PLANE_Y,
            )
        ),
    )
    tap_plane_name = name_last_feature(adapter, "TapDrillPlane")
    tap = SketchDims()
    check(
        "create_sketch tap drill",
        await adapter.create_sketch(tap_plane_name),
    )
    tap_circle = await define_circle(
        adapter,
        0.0,
        -SET_SCREW_Z,
        TAP_DRILL_DIA / 2.0,
        "tap drill",
        dims=tap,
        names=("TapCx", "TapCz", "TapDrillDia"),
        drives=(None, '"SetScrewZ"', '"TapDrillDia"'),
    )
    segment = _early_bound(adapter._sketch_entities[tap_circle], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(
            "tap-drill reference circle did not take the construction flag"
        )
    await ensure_fully_defined(adapter, "tap-drill sketch")
    check("exit_sketch tap drill", await adapter.exit_sketch())
    name_last_feature(adapter, "TapDrillProfile")
    drive_jobs += tap.apply(adapter, "TapDrillProfile")
    drive_jobs += await _thin_wall_reference(adapter)
    blank_reference_sketches(adapter, ("TapDrillProfile", "ThinWallReference"))

    # One native #2-56 UNC-2B tap, radially inward from the heavy-side OD
    # through to the next surface (the rod bore), never through the far wall.
    # Front-offset station plane fixes Z; Right Plane clocks the mouth to -Y.
    check(
        "create_plane SetScrewStationPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=SET_SCREW_Z
            )
        ),
    )
    name_last_feature(adapter, "SetScrewStationPlane")
    station_dim = name_dimensions(adapter, "SetScrewStationPlane", ["SetScrewZ"])
    drive_jobs += [(station_dim[0], '"SetScrewZ"')]
    wizard_hole_on_cylinder(
        adapter,
        SET_SCREW_HOLE_SPEC,
        [0.0, _TAP_PLANE_Y, SET_SCREW_Z],
        "heavy-side set-screw tap (#2-56)",
        name="SetScrewTap",
        point_planes=("SetScrewStationPlane", "Right Plane"),
    )
    volume -= V_TAP_DRILL
    await volume_check(adapter, "#2-56 radial tap", volume, 0.05 * V_TAP_DRILL)

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

    # Manufacturing drawing support: the bands and decimal places live on the
    # model dimensions (drawing-simplicity-policy.md `How the repository implements the guidelines` -- the places are the tolerance, so the
    # sheet reads them back instead of rewriting them); mark exactly the
    # print's dimensions and stamp the make-critical title-block properties.
    # The bands are millimetres; UNIT prints them in inches.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_BAND), display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "CollarProfile",
        "CollarOd",
        COLLAR_OD_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "CollarProfile",
        "CollarCy",
        COLLAR_AXIS_TOLERANCE_MM,
        display_unit=UNIT,
    )
    set_single_limit(
        adapter,
        "ThinWallReference",
        "ThinWallMin",
        limit=THIN_WALL_MIN_MM,
        band=THIN_WALL_MIN_BAND,
        tol_type=THIN_WALL_MIN_TOL_TYPE,
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    name_octant_views(adapter, label=PART_NAME)
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
        (
            ("TapDrillPlane", "PLANE"),
            ("SetScrewStationPlane", "PLANE"),
            (cam_bore_axis, "AXIS"),
        ),
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
