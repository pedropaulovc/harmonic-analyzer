r"""Reproduction script: pen hanger (book ch. 24, pp. 60-63; engineerguy 4/4
9:15-10:34).

The black tapered strap bolted to the wheel support bar that guides the pen
rod: a flat strap (3 thick) tapering 16 -> 10 wide, lying on the bar's front
face and running 170 down from the bar top to just above the platen, with two
thin open U guide plates brazed across its front face 40 apart.  Each plate's
slot opens forward (-Z), so the square pen rod hangs on its wire inside both
slots and lifts straight out of them; the slot sides are the rod's only
lateral guide.  The lower plate is flush with the strap's bottom end.  A #8-32
tap near the strap top takes the hanger screw coming through the bar FROM
BEHIND (the magnifying wheel's rim passes in front of the strap, so no
front-side head fits).

Layout: origin at the strap's top-right BACK corner -- on the bar's front
face, level with the bar top, on the rod line's x (machine ``HANGER_POS``;
all of the geometry lives in ``pn_pen_hanger_spec``).  The part is authored
MACHINE-handed and placed IDENTITY, so local axes are machine axes: the strap
occupies y -170..0, z -3..0, its top edge leaning toward machine east (-x);
the rod axis is local (0, ., ROD_AXIS_Z).
Dimensions: cad/DIMENSIONS.md ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_hanger.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_polygon_chain, define_rectilinear_chain
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _holes import TAP_DRILL_MM, wizard_holes
from pn_pen_hanger_spec import (
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FRONT_VIEW_NOTE,
    GUIDE_PLATE_DROPS,
    GUIDE_PLATE_T,
    GUIDE_PLATE_WIDTH,
    ISOMETRIC_VIEW_NOTE,
    PLATE_FRONT_Z,
    PLATE_REACH,
    SCREW_HOLE_XY,
    SCREW_TAP_SPEC,
    SLOT_BOTTOM,
    SLOT_DEPTH,
    SLOT_WIDTH,
    STRAP_BOT_X,
    STRAP_OUTLINE,
    STRAP_RISE,
    STRAP_T,
    STRAP_TOP_X,
    STRAP_Z,
    TOP_VIEW_NOTE,
)

import _telemetry

PART_NAME = "pn-pen-hanger"
MATERIAL = "Plain Carbon Steel"  # black hardware


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def _guide_plate(adapter, prefix: str, drop: float) -> list[tuple[str, str]]:
    """One open U plate: a Top-plane outline ((u, v) = model (x, -z)) extruded
    down from ``drop`` below the strap top.  Emission (rectilinear chain):
    slot width, slot depth, right arm, right reach, plate width, left reach,
    then the slot-bottom-left anchor (x, then the strap-back-face distance);
    the left arm and the slot's left side close the chain."""
    v_back, v_bot, v_front = -STRAP_Z[0], SLOT_BOTTOM, -PLATE_FRONT_Z
    half_slot, half_plate = SLOT_WIDTH / 2.0, GUIDE_PLATE_WIDTH / 2.0
    points = [
        (-half_slot, v_bot),
        (half_slot, v_bot),
        (half_slot, v_front),
        (half_plate, v_front),
        (half_plate, v_back),
        (-half_plate, v_back),
        (-half_plate, v_front),
        (-half_slot, v_front),
    ]
    sketch = SketchDims()
    check(f"create_sketch {prefix} guide", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, lines, points, label=f"{prefix} guide", dims=sketch,
        names=["SlotWidth", "SlotDepth", "ArmWidth", "PlateReach",
               "PlateWidth", "PlateReachLeft", "SlotX", "SlotBottom"],
        drives=['"SlotWidth"',
                '"PlateReach" + "StrapThick" - "SlotBottom"',
                '("PlateWidth" - "SlotWidth") / 2',
                '"PlateReach"',
                '"PlateWidth"',
                '"PlateReach"',
                '"SlotWidth" / 2',
                '"SlotBottom"'],
    )
    await ensure_fully_defined(adapter, f"{prefix} guide sketch")
    check(f"exit_sketch {prefix} guide", await adapter.exit_sketch())
    profile = f"{prefix}GuideProfile"
    name_last_feature(adapter, profile)
    jobs = sketch.apply(adapter, profile)
    extrude_at_offset(adapter, GUIDE_PLATE_T, drop, flip=True)
    feature = f"{prefix}Guide"
    name_last_feature(adapter, feature)
    thick, offset = name_dimensions(
        adapter, feature, ["PlateThick", f"{prefix}PlateDrop"]
    )
    return [*jobs, (thick, '"PlateThick"'), (offset, f'"{prefix}PlateDrop"')]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing: this is an INCH
    # document and the equation manager reads BARE numbers in document units.
    # The strap-edge and screw-hole knobs hold SIGNED local coordinates; the dims
    # they drive are UNSIGNED distances, so the drives negate them positive.
    await set_global(adapter, "StrapTopLeftX", f"{STRAP_TOP_X[0]}mm")
    await set_global(adapter, "StrapBotHalf", f"{STRAP_BOT_X[1]}mm")
    await set_global(adapter, "StrapRise", f"{STRAP_RISE}mm")
    await set_global(adapter, "StrapThick", f"{STRAP_T}mm")
    await set_global(adapter, "ScrewHoleX", f"{SCREW_HOLE_XY[0]}mm")
    await set_global(adapter, "ScrewHoleY", f"{SCREW_HOLE_XY[1]}mm")
    await set_global(adapter, "PlateThick", f"{GUIDE_PLATE_T}mm")
    await set_global(adapter, "PlateWidth", f"{GUIDE_PLATE_WIDTH}mm")
    await set_global(adapter, "PlateReach", f"{PLATE_REACH}mm")
    await set_global(adapter, "SlotWidth", f"{SLOT_WIDTH}mm")
    await set_global(adapter, "SlotBottom", f"{SLOT_BOTTOM}mm")
    await set_global(adapter, "LowerPlateDrop", f"{GUIDE_PLATE_DROPS[0]}mm")
    await set_global(adapter, "UpperPlateDrop", f"{GUIDE_PLATE_DROPS[1]}mm")

    # Drive equations collected as dims are recorded, applied in one deferred
    # batch after the whole model + a rebuild exists (every target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Tapered strap from the origin corner. Polygon-chain emission order
    # (anchor vertex 0 on the origin -> no anchor dims): seg0 top run, seg1
    # (general) taper dx then rise, seg2 bottom width; the closing right edge
    # is supplied by closure.
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap_lines = await add_line_chain(adapter, list(STRAP_OUTLINE))
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, strap_lines, list(STRAP_OUTLINE), label="strap", dims=strap,
        names=["StrapTopRun", "StrapTaperDx", "StrapRise", "StrapBotWidth"],
        drives=['-"StrapTopLeftX"',
                '-"StrapBotHalf" - "StrapTopLeftX"',
                '"StrapRise"',
                '2 * "StrapBotHalf"'],
    )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    # Reversed: from the bar seat (z 0) forward to the strap front face (-3).
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=STRAP_T, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Strap")
    drive_jobs.append(
        (name_dimensions(adapter, "Strap", ["StrapThick"])[0], '"StrapThick"')
    )
    top_w = STRAP_TOP_X[1] - STRAP_TOP_X[0]
    bot_w = STRAP_BOT_X[1] - STRAP_BOT_X[0]
    v_strap = (top_w + bot_w) / 2.0 * STRAP_RISE * STRAP_T
    vol = await volume_check(adapter, "strap", v_strap, 0.002 * v_strap)

    # 2. The two guide plates, each butting the strap front face.
    v_plate = GUIDE_PLATE_T * (
        GUIDE_PLATE_WIDTH * PLATE_REACH - SLOT_WIDTH * SLOT_DEPTH
    )
    for prefix, drop in zip(("Lower", "Upper"), GUIDE_PLATE_DROPS, strict=True):
        drive_jobs += await _guide_plate(adapter, prefix, drop)
        vol = await volume_check(
            adapter, f"{prefix.lower()} guide plate", vol + v_plate, 0.01 * v_plate
        )

    # 3. Native #8-32 through tap in the strap, drilled from its front face
    # (outward normal -Z); the screw enters from behind the bar through the
    # back face.
    screw_dia = TAP_DRILL_MM[SCREW_TAP_SPEC.size]
    screw_cut = wizard_holes(
        adapter,
        SCREW_TAP_SPEC,
        [[SCREW_HOLE_XY[0], SCREW_HOLE_XY[1], STRAP_Z[0]]],
        (0.0, 0.0, -1.0),
        "hanger-screw tapped hole (#8-32)",
        name="ScrewHole",
        placement_dims=[
            (
                ("ScrewX", '-"ScrewHoleX"'),
                ("ScrewY", '-"ScrewHoleY"'),
            )
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    expected = vol - math.pi * (screw_dia / 2.0) ** 2 * STRAP_T
    vol = await _volume(adapter)
    _telemetry.info(f"volume after screw hole: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 1.0:
        raise RuntimeError(f"screw hole volume {vol:.1f} != {expected:.1f}")

    await name_bore_axis(
        adapter,
        "Right Plane",
        SCREW_HOLE_XY[0],
        "Top Plane",
        SCREW_HOLE_XY[1],
        "hanger-screw hole",
    )
    name_last_feature(adapter, "HangerScrewAxis")

    # Apply the deferred drive equations after the model + a rebuild exists, then
    # re-check neutrality: every equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pen hanger (equations neutral)", vol, 1.0)

    await apply_material(adapter, MATERIAL)
    # ch21 p.52 (img03) / ch30 plates: the hanger is BLACK-oxide steel (the
    # dark strap the brass pen rod runs beside), not bright.
    await apply_color(adapter, PANEL_BLACK)
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
            "Front View Note": FRONT_VIEW_NOTE,
            "Top View Note": TOP_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
