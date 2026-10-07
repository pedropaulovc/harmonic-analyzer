r"""Build the rocker inspection box (MHA-CH-006-TL-08; bought box parallel, reworked).

The bought Suburban Tool BXP-050505-G box parallel with the shop's rework:
two clamp windows through the left wall, an access window through the back
wall and two #8-32 taps for the C stop bar in the front wall
(``ch_rocker_arm_tl_inspection_box_spec``).

Layout (model frame, +Y up, +Z out of the front face): the bought tube is a
Top-plane outer and core square (sketch y = model -Z) extruded +Y; the clamp
windows are Right-plane rectangles (sketch x = model -Z) cut mid-plane by
twice the wall, so exactly the left wall opens; the back window is a
Front-plane square cut from inside the core through the back wall; the taps
enter the front face.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_inspection_box.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _holes import blind_hole_volume_mm3, wizard_holes
from _visibility import blank_reference_geometry
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_inspection_box_spec import (
    BACK_WINDOW,
    BACK_WINDOW_X0,
    BACK_WINDOW_Y0,
    BOX,
    CORE,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    TAP_DRILL_DIA,
    TAP_SPEC,
    TAP_X,
    TAP_Y,
    WALL,
    WINDOW_FRONT,
    WINDOW_H,
    WINDOW_LOW_BASE,
    WINDOW_UP_BASE,
    WINDOW_W,
)

PART_NAME = "ch-rocker-arm-tl-inspection-box"
MATERIAL = "Gray Cast Iron"  # the bought box parallel's cast iron
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_TUBE = BOX * (BOX * BOX - CORE * CORE)
V_CLAMP_WINDOWS = 2.0 * WINDOW_W * WINDOW_H * WALL
V_BACK_WINDOW = BACK_WINDOW * BACK_WINDOW * WALL
_BACK_PLANE_Z = BOX - WALL / 2.0


def _rectangle(x0: float, y0: float, w: float, h: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def _chain(adapter, points, label, dims, names, drives) -> None:
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter, lines, points, label=label, dims=dims, names=names, drives=drives
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "Box", f"{BOX}mm")
    await set_global(adapter, "Wall", f"{WALL}mm")
    await set_global(adapter, "WindowW", f"{WINDOW_W}mm")
    await set_global(adapter, "WindowH", f"{WINDOW_H}mm")
    await set_global(adapter, "WindowFront", f"{WINDOW_FRONT}mm")
    await set_global(adapter, "WindowLowBase", f"{WINDOW_LOW_BASE}mm")
    await set_global(adapter, "WindowUpBase", f"{WINDOW_UP_BASE}mm")
    await set_global(adapter, "BackWindow", f"{BACK_WINDOW}mm")

    # --- Bought box parallel: one vertical through core ---------------------
    tube = SketchDims()
    check("create_sketch tube", await adapter.create_sketch("Top"))
    await _chain(
        adapter, _rectangle(0.0, 0.0, BOX, BOX), "box outline", tube,
        ["BoxW", "BoxD"], ['"Box"', '"Box"'],
    )
    await _chain(
        adapter, _rectangle(WALL, WALL, CORE, CORE), "box core", tube,
        ["CoreW", "CoreD", "CoreX0", "CoreY0"],
        ['"Box" - 2 * "Wall"', '"Box" - 2 * "Wall"', '"Wall"', '"Wall"'],
    )
    await ensure_fully_defined(adapter, "box section")
    check("exit_sketch tube", await adapter.exit_sketch())
    name_last_feature(adapter, "BoxSection")
    drive_jobs = tube.apply(adapter, "BoxSection")
    check("extrude tube", await adapter.create_extrusion(ExtrusionParameters(depth=BOX)))
    name_last_feature(adapter, "BoxParallel")
    drive_jobs.append((name_dimensions(adapter, "BoxParallel", ["BoxH"])[0], '"Box"'))
    volume = await volume_check(adapter, "box parallel", V_TUBE, 0.002 * V_TUBE)

    # --- Clamp windows through the left wall -------------------------------
    windows = SketchDims()
    check("create_sketch clamp windows", await adapter.create_sketch("Right"))
    await _chain(
        adapter, _rectangle(WINDOW_FRONT, WINDOW_LOW_BASE, WINDOW_W, WINDOW_H),
        "lower clamp window", windows,
        ["WinLowW", "WinLowH", "WinLowFront", "WinLowBase"],
        ['"WindowW"', '"WindowH"', '"WindowFront"', '"WindowLowBase"'],
    )
    await _chain(
        adapter, _rectangle(WINDOW_FRONT, WINDOW_UP_BASE, WINDOW_W, WINDOW_H),
        "upper clamp window", windows,
        ["WinUpW", "WinUpH", "WinUpFront", "WinUpBase"],
        ['"WindowW"', '"WindowH"', '"WindowFront"', '"WindowUpBase"'],
    )
    await ensure_fully_defined(adapter, "clamp windows")
    check("exit_sketch clamp windows", await adapter.exit_sketch())
    name_last_feature(adapter, "ClampWindowProfile")
    drive_jobs += windows.apply(adapter, "ClampWindowProfile")
    check(
        "cut clamp windows",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * WALL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ClampWindows")
    volume = await volume_check(
        adapter, "clamp windows", volume - V_CLAMP_WINDOWS, 0.005 * V_CLAMP_WINDOWS
    )

    # --- Access window through the back wall -------------------------------
    back = SketchDims()
    # Sketched on a plane mid-way through the back wall and cut both ways
    # by more than the wall, so only the back wall opens.
    check(
        "create_plane BackWallPlane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=-_BACK_PLANE_Z)
        ),
    )
    name_last_feature(adapter, "BackWallPlane")
    blank_reference_geometry(adapter, (("BackWallPlane", "PLANE"),))
    check("create_sketch back window", await adapter.create_sketch("BackWallPlane"))
    await _chain(
        adapter, _rectangle(BACK_WINDOW_X0, BACK_WINDOW_Y0, BACK_WINDOW, BACK_WINDOW),
        "back window", back,
        ["BackW", "BackH", "BackX0", "BackY0"],
        ['"BackWindow"', '"BackWindow"', '("Box" - "BackWindow") / 2', '("Box" - "BackWindow") / 2'],
    )
    await ensure_fully_defined(adapter, "back window")
    check("exit_sketch back window", await adapter.exit_sketch())
    name_last_feature(adapter, "BackWindowProfile")
    drive_jobs += back.apply(adapter, "BackWindowProfile")
    check(
        "cut back window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WALL + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BackWindow")
    volume = await volume_check(
        adapter, "back window", volume - V_BACK_WINDOW, 0.005 * V_BACK_WINDOW
    )

    # --- C stop bar taps in the front face ---------------------------------
    taps = wizard_holes(
        adapter,
        TAP_SPEC,
        [[x, TAP_Y, 0.0] for x in TAP_X],
        (0.0, 0.0, 1.0),
        "C stop bar taps (#8-32 blind)",
        name="BarTaps",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[
            (("TapLeftX", None), ("TapY", None)),
            (("TapRightX", None), ("TapRightY", None)),
        ],
    )
    drive_jobs += taps.placement_drive_jobs
    v_taps = 2.0 * blind_hole_volume_mm3(TAP_DRILL_DIA, TAP_SPEC.depth_mm)
    volume = await volume_check(adapter, "bar taps", volume - v_taps, 0.02 * v_taps)
    _require_one_solid_body(adapter, label="box")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven box (equations neutral)", volume, 0.002 * V_TUBE)
    _require_one_solid_body(adapter, label="driven box")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
        )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
