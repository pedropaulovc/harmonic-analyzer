r"""Reproduction script: platen guide rail (book ch. 22, pp. 54-55; 2 used).

One of the two black guide rails screwed across the FULL width of the platen
back, above and below the bright wear band where the support bar slides --
the platen HANGS on the bar by these. Each is fastened by a row of 5 screws
whose heads show on the platen front (ch22 front photo; counterbored flush so
the paper lies flat, shanks threading into the rail) and carries 2 lock
plates (build_guide_lock.py) that bridge behind the bar so the platen cannot
fall off. 10 deep so the lock plates clear the 9-deep bar.

Layout: length along +X, height along +Y from the origin corner, depth
extruded +Z (the assembly seats local z 0 on the platen back). The 4 lock
screw holes run through along Z at the two lock stations (x 60/240 +- 7).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_guide.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_custom_properties,
    apply_material,
    blank_sketch,
    check,
    define_circle,
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
    set_sketch_direct_db,
    volume_check,
    _dim_owner_feature,
    _feature_by_name,
    _iter_features,
    _read_member,
)
import _config
import _telemetry
from _hole_wizard import BA6, TapEnd, create_tapped_pattern

PART_NAME = "platen-guide"
MATERIAL = "Plain Carbon Steel"

GUIDE_LENGTH = 300.0  # = platen width (ch22 back photo: full-width rails)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (60.0, 240.0)  # lock-plate centres (2 per guide)
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre
THREAD = BA6

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# Blind holes on the FRONT face (mid-height) where the row of 5 fastening
# screws threads in: the platen counterbores its heads (build_platen), so the
# O2.9 shanks reach 2.4 past the platen back into the rail. Stations = the
# platen's GUIDE_HOLE_X (pinned by an assert in the assembly module).
SCREW_STATION_X = (30.0, 90.0, 150.0, 210.0, 270.0)
SCREW_HOLE_DEPTH = 3.0
SCREW_THREAD_DEPTH = 2.4


def _mark_dimensions_for_drawing(
    adapter, feature_name: str, dimension_names: set[str]
) -> None:
    """Mark only this part's explicit manufacturing dimensions for insertion."""
    feature = _feature_by_name(adapter, feature_name)
    marked: set[str] = set()
    display = _read_member(feature, "GetFirstDisplayDimension")
    for _ in range(1000):
        if not display:
            break
        dimension = display.GetDimension2(0)
        name = str(_read_member(dimension, "Name"))
        if _dim_owner_feature(dimension) == feature_name and name in dimension_names:
            display.MarkedForDrawing = True
            if not bool(_read_member(display, "MarkedForDrawing")):
                raise RuntimeError(f"{name}@{feature_name}: mark-for-drawing failed")
            marked.add(name)
        display = feature.GetNextDisplayDimension(display)
    missing = dimension_names - marked
    if missing:
        raise RuntimeError(
            f"{feature_name}: dimensions not marked for drawing: {sorted(missing)}"
        )
    _telemetry.success(
        f"marked for drawing {feature_name}: {', '.join(sorted(marked))}"
    )


def _clear_dimensions_for_drawing(adapter) -> None:
    cleared = 0
    for feature in _iter_features(adapter):
        display = _read_member(feature, "GetFirstDisplayDimension")
        for _ in range(1000):
            if not display:
                break
            if bool(_read_member(display, "MarkedForDrawing")):
                display.MarkedForDrawing = False
                cleared += 1
            display = feature.GetNextDisplayDimension(display)
    _telemetry.success(f"cleared {cleared} model-dimension drawing marks")


def _apply_drawing_properties(adapter) -> None:
    spec = _config.parts(PART_NAME)
    apply_custom_properties(
        adapter,
        {
            "Material Specification": str(spec["material_specification"]),
            "Finish": str(spec["finish"]),
            "Quantity": str(spec["quantity"]),
        },
    )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "GuideLength", f"{GUIDE_LENGTH}mm")
    await set_global(adapter, "GuideHeight", f"{GUIDE_HEIGHT}mm")
    await set_global(adapter, "GuideDepth", f"{GUIDE_DEPTH}mm")
    await set_global(adapter, "ThreadMajorDia", f"{THREAD.major_diameter_mm}mm")
    await set_global(adapter, "TapDrillDia", f"{THREAD.tap_diameter_mm}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rail outline: corner-at-origin rectangle, length along X, height along Y.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (GUIDE_LENGTH, 0.0),
        (GUIDE_LENGTH, GUIDE_HEIGHT),
        (0.0, GUIDE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="guide outline", dims=outline,
        names=["Length", "Height"],
        drives=['"GuideLength"', '"GuideHeight"'],
    )
    await ensure_fully_defined(adapter, "guide outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "GuideProfile")
    drive_jobs += outline.apply(adapter, "GuideProfile")
    check(
        "extrude guide",
        await adapter.create_extrusion(ExtrusionParameters(depth=GUIDE_DEPTH)),
    )
    name_last_feature(adapter, "Guide")
    depth_dim = name_dimensions(adapter, "Guide", ["Depth"])
    drive_jobs += [(depth_dim[0], '"GuideDepth"')]
    v_rail = GUIDE_LENGTH * GUIDE_HEIGHT * GUIDE_DEPTH
    await volume_check(adapter, "guide rail", v_rail, 0.005 * v_rail)

    # The lock plates sit on the back face (z=10); their screws enter there and
    # thread through the guide.  A native BSI Hole Wizard feature is the model
    # source for the drawing's 4X 6 BA THRU callout.
    lock_taps = await create_tapped_pattern(
        adapter,
        name="LockPlateTaps",
        points_xy=tuple((x, GUIDE_HEIGHT / 2.0) for x in HOLE_X),
        z_face_mm=GUIDE_DEPTH,
        normal_sign=1,
        end=TapEnd.THROUGH,
    )
    tap_drill = SketchDims()
    check("create_sketch 6 BA through tap drills", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, x in enumerate(HOLE_X):
        await define_circle(
            adapter,
            x,
            GUIDE_HEIGHT / 2.0,
            THREAD.tap_diameter_mm / 2.0,
            f"6 BA through tap drill x{x:.0f}",
            dims=tap_drill,
            names=(f"T{n}X", f"T{n}Y", f"T{n}Dia"),
            drives=(None, None, '"TapDrillDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "6 BA through tap drill sketch")
    check("exit_sketch 6 BA through tap drills", await adapter.exit_sketch())
    name_last_feature(adapter, "ThroughTapDrillProfile")
    drive_jobs += tap_drill.apply(adapter, "ThroughTapDrillProfile")
    check(
        "calibrate 6 BA through tap drills",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * GUIDE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ThroughTapDrillCalibration")
    v_holes = (
        len(HOLE_X)
        * math.pi
        * (lock_taps.tap_diameter_mm / 2.0) ** 2
        * GUIDE_DEPTH
    )
    await volume_check(adapter, "guide with holes", v_rail - v_holes, 0.02 * v_holes)

    # The five platen screws enter the front face and need 2.4 mm of full thread
    # in a 3.0 mm bottoming hole.  Keep this as a second Hole Wizard feature so
    # the drawing can distinguish its blind callout from the rear through taps.
    blind_pre = await adapter.get_mass_properties()
    mount_taps = await create_tapped_pattern(
        adapter,
        name="PlatenMountTaps",
        points_xy=tuple((x, GUIDE_HEIGHT / 2.0) for x in SCREW_STATION_X),
        z_face_mm=0.0,
        normal_sign=-1,
        end=TapEnd.BOTTOMING,
        hole_depth_mm=SCREW_HOLE_DEPTH,
        thread_depth_mm=SCREW_THREAD_DEPTH,
    )
    cylinder_min = (
        len(SCREW_STATION_X)
        * math.pi
        * (mount_taps.tap_diameter_mm / 2.0) ** 2
        * SCREW_HOLE_DEPTH
    )
    cylinder_max = (
        len(SCREW_STATION_X)
        * math.pi
        * (mount_taps.thread_diameter_mm / 2.0) ** 2
        * SCREW_HOLE_DEPTH
    )
    blind_post = await adapter.get_mass_properties()
    v_screws = blind_pre.data.volume - blind_post.data.volume
    if not 0.98 * cylinder_min <= v_screws <= 1.02 * cylinder_max:
        raise RuntimeError(
            "6 BA blind taps removed "
            f"{v_screws:.1f} mm^3, outside {cylinder_min:.1f}..{cylinder_max:.1f}"
        )
    v_final = v_rail - v_holes - v_screws
    await volume_check(adapter, "guide with screw holes", v_final, 0.02 * v_screws)

    # Hidden drawing-only locator sketch. Hole Wizard location dimensions are
    # imported as an all-or-nothing group by SolidWorks, which also pulls every
    # redundant 2.5 ordinate. This marked sketch carries only the five blind-hole
    # baselines needed on the manufacturing drawing and changes no solid geometry.
    blind_locators = SketchDims()
    check("create_sketch blind drawing locators", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, x in enumerate(SCREW_STATION_X):
        await define_circle(
            adapter,
            x,
            GUIDE_HEIGHT / 2.0,
            THREAD.tap_diameter_mm / 2.0,
            f"blind drawing locator x{x:.0f}",
            dims=blind_locators,
            names=(f"B{n}X", f"B{n}Y", f"B{n}Dia"),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "blind drawing locator sketch")
    check("exit_sketch blind drawing locators", await adapter.exit_sketch())
    name_last_feature(adapter, "BlindDrawingLocatorProfile")
    blind_locators.apply(adapter, "BlindDrawingLocatorProfile")
    blank_sketch(adapter, "BlindDrawingLocatorProfile")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven guide (equations neutral)", v_final, 0.02 * v_holes
    )

    _clear_dimensions_for_drawing(adapter)
    _mark_dimensions_for_drawing(adapter, "GuideProfile", {"Length", "Height"})
    _mark_dimensions_for_drawing(adapter, "Guide", {"Depth"})
    _mark_dimensions_for_drawing(
        adapter, "ThroughTapDrillProfile", {"T0X", "T1X", "T2X", "T3X", "T0Y"}
    )
    _mark_dimensions_for_drawing(
        adapter,
        "BlindDrawingLocatorProfile",
        {"B0X", "B1X", "B2X", "B3X", "B4X"},
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    _apply_drawing_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
