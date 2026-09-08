r"""Reproduction script: pen hanger (book ch. 24, pp. 60-63).

The black tapered strap bolted to the wheel support bar that hangs the
pen rod's upper guide: a flat strap (3 thick) tapering 16 -> 10 wide,
lying on the bar's front face and descending to a deep guide block with
a 5.4 square channel the 5-square pen rod slides in -- the rod is
VERTICAL, so the channel is cut along Y through the block (an M6.4 fix:
the first build wrongly tunnelled it along Z). The block reaches
forward (-Z in the machine) so the pen rod hangs clear of the platen
paper plane while the strap stays flush on the bar. The M6.10 fastener pass
adds a #8-32 tap near the strap top (local (-6, 70.7) = machine
(-3, 575.7): placed IDENTITY at machine x +3, locals map directly)
for the hanger-screw shank coming through the bar FROM BEHIND (the
magnifying wheel's rim back face passes 1.0 in front of the strap, so no
front-side head fits).

Layout: origin at the guide block centre (machine (+3, 505, -157));
block z -4..+18.1 (back face flush with the bar front at machine
z -138.9), strap in the z = 15.1..18.1 band rising +Y to the bar band.
The part is authored MACHINE-handed and placed
IDENTITY, so local axes are machine axes (the strap's sideways lean, its
only x-asymmetric feature, runs toward machine east = local -x).
Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_hanger.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM, HoleSpec, wizard_holes
from build_hanger_screw import SHANK_DIA as HANGER_SCREW_DIA
from wheel_bar_geom import (
    HANGER_SCREW_LOCAL_X,
    HANGER_STRAP_TOP_LEFT_X,
)
from pen_hanger_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    TOP_VIEW_NOTE,
)

import _telemetry

PART_NAME = "pen-hanger"
MATERIAL = "Plain Carbon Steel"  # black hardware

BLOCK_HALF = 6.0  # guide block 12 x 12 (low)
BLOCK_Z = (-4.0, 18.1)  # deep block: back face on the bar front (derived); the
# rod line moved 5.5 forward of the bar (build_pen_assembly PEN_Z_MID) so the
# 45-degree v-block clears the paper, and the block deepens to keep the strap
# flush on the bar
GUIDE_HOLE_HALF = 2.7  # 5.4 square: the 5-square pen rod slides (derived)
STRAP_Z = (15.1, 18.1)  # strap 3 thick, flush with the block back (derived)
STRAP_TOP_Y = 75.7  # machine 580.7: bar top after the ch30 p002 wheel-bar
# re-anchor (y 575.7) -- the strap stretches up to the raised bar while the
# guide block stays put on the pen line (the pen geometry did not move)
STRAP_TOP_X = (HANGER_STRAP_TOP_LEFT_X, 0.0)  # 16 wide at the bar (low)
STRAP_BOT_X = (-5.0, 5.0)  # 10 wide at the block (low)
# M6.10: the selected hanger screw threads into the strap near its top through
# an exact #8-32 tapped Hole Wizard feature.
SCREW_TAP_SPEC = HoleSpec("tapped", "#8-32")
SCREW_HOLE_XY = (HANGER_SCREW_LOCAL_X, 70.7)
# Exact tapered-land bounds at the tap centre. The clearance bore's bar-end
# ligament is checked in build_wheel_bar; the receiver uses the thread major
# diameter here, not the tap-drill diameter.

_STRAP_RISE = STRAP_TOP_Y - BLOCK_HALF
_STRAP_T = (SCREW_HOLE_XY[1] - BLOCK_HALF) / _STRAP_RISE
_STRAP_LEFT_X = STRAP_BOT_X[0] + _STRAP_T * (STRAP_TOP_X[0] - STRAP_BOT_X[0])
_STRAP_RIGHT_X = STRAP_BOT_X[1] + _STRAP_T * (STRAP_TOP_X[1] - STRAP_BOT_X[1])
# Perpendicular distances to the four straight edges, not horizontal slices:
# a circular thread envelope must remain inside the whole tapered polygon.
HANGER_THREAD_STRAP_WALL = min(
    (SCREW_HOLE_XY[0] - _STRAP_LEFT_X)
    / math.hypot(1.0, (STRAP_TOP_X[0] - STRAP_BOT_X[0]) / _STRAP_RISE),
    (_STRAP_RIGHT_X - SCREW_HOLE_XY[0])
    / math.hypot(1.0, (STRAP_TOP_X[1] - STRAP_BOT_X[1]) / _STRAP_RISE),
    SCREW_HOLE_XY[1] - BLOCK_HALF,
    STRAP_TOP_Y - SCREW_HOLE_XY[1],
) - HANGER_SCREW_DIA / 2.0
if HANGER_THREAD_STRAP_WALL <= 0.0:
    raise AssertionError("stock #8 hanger thread breaks through the tapered strap")


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing: this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 65 = 65 in, a 25.4x in-plane blow-up). The strap-edge X knobs and
    # the screw-hole X hold SIGNED machine coordinates; the dims they drive are
    # UNSIGNED distances, so the drive expressions below negate / difference them
    # so each evaluates POSITIVE.
    await set_global(adapter, "BlockHalf", f"{BLOCK_HALF}mm")
    await set_global(adapter, "GuideHoleHalf", f"{GUIDE_HOLE_HALF}mm")
    await set_global(adapter, "StrapTopY", f"{STRAP_TOP_Y}mm")
    await set_global(adapter, "StrapBotXMin", f"{STRAP_BOT_X[0]}mm")
    await set_global(adapter, "StrapBotXMax", f"{STRAP_BOT_X[1]}mm")
    await set_global(adapter, "StrapTopXMin", f"{STRAP_TOP_X[0]}mm")
    await set_global(adapter, "StrapTopXMax", f"{STRAP_TOP_X[1]}mm")
    await set_global(adapter, "ScrewHoleX", f"{SCREW_HOLE_XY[0]}mm")
    await set_global(adapter, "ScrewHoleY", f"{SCREW_HOLE_XY[1]}mm")
    # (The old ScrewHoleDia/ScrewHoleX/ScrewHoleY knobs are gone: the hole is
    # now a native Hole Wizard #8-32 tapped feature placed by point.)

    # Drive equations collected as dims are recorded, applied in one deferred
    # batch after the whole model + a rebuild exists (every target must resolve).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Solid guide block: an origin-centred 12 x 12 square -- use
    # define_centered_rectangle (width/depth/corner named directly).
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BLOCK_HALF, BLOCK_HALF, "block", dims=block,
        name_width="BlockWidth", drive_width='2 * "BlockHalf"',
        name_depth="BlockDepth", drive_depth='2 * "BlockHalf"',
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    extrude_at_offset(adapter, BLOCK_Z[1] - BLOCK_Z[0], BLOCK_Z[0])
    name_last_feature(adapter, "Block")
    expected = (2.0 * BLOCK_HALF) ** 2 * (BLOCK_Z[1] - BLOCK_Z[0])
    vol = await _volume(adapter)
    _telemetry.info(f"volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 1b. Square rod channel cut along Y (the pen rod hangs vertically).
    # The +-2.7 footprint stays inside the block's z -4..18.1 band (BLOCK_Z) and
    # well clear of the strap's z 15.1..18.1 band (STRAP_Z), so a through cut
    # is safe.
    channel = SketchDims()
    check("create_sketch channel", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, GUIDE_HOLE_HALF, GUIDE_HOLE_HALF, "channel", dims=channel,
        name_width="ChannelWidth", drive_width='2 * "GuideHoleHalf"',
        name_depth="ChannelDepth", drive_depth='2 * "GuideHoleHalf"',
    )
    await ensure_fully_defined(adapter, "channel sketch")
    check("exit_sketch channel", await adapter.exit_sketch())
    name_last_feature(adapter, "ChannelProfile")
    drive_jobs += channel.apply(adapter, "ChannelProfile")
    check(
        "cut channel",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * BLOCK_HALF, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Channel")
    expected -= (2.0 * GUIDE_HOLE_HALF) ** 2 * 2.0 * BLOCK_HALF
    vol = await _volume(adapter)
    _telemetry.info(f"volume after channel: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"channel volume {vol:.1f} != {expected:.1f}")

    # 2. Tapered strap rising to the support bar. Polygon-chain emission order:
    # anchor vertex 0 = (STRAP_BOT_X[0], BLOCK_HALF) is off both axes -> 2 anchor
    # dims (x then z), THEN the kept segments' offsets in line order (the segment
    # ending at the anchor vertex is skipped, closure supplies it):
    #   seg0 (bottom edge, axis-aligned) -> 1 dim (bottom width)
    #   seg1 (right taper, general)      -> 2 dims (dx, dy)
    #   seg2 (top edge, axis-aligned)    -> 1 dim (top run)
    # = 6 display dims. Anchor/segment dims are UNSIGNED distances; the strap-edge
    # X knobs are signed, so the drives below difference/negate them to positive.
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap_pts = [
        (STRAP_BOT_X[0], BLOCK_HALF),
        (STRAP_BOT_X[1], BLOCK_HALF),
        (STRAP_TOP_X[1], STRAP_TOP_Y),
        (STRAP_TOP_X[0], STRAP_TOP_Y),
    ]
    strap_lines = await add_line_chain(adapter, strap_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, strap_lines, strap_pts, label="strap", dims=strap,
        names=["StrapAnchorX", "StrapAnchorZ", "StrapBotWidth",
               "StrapTaperDx", "StrapTaperDy", "StrapTopRun"],
        drives=['-"StrapBotXMin"', '"BlockHalf"',
                '"StrapBotXMax" - "StrapBotXMin"',
                '"StrapBotXMax" - "StrapTopXMax"',
                '"StrapTopY" - "BlockHalf"',
                '"StrapTopXMax" - "StrapTopXMin"'],
    )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    extrude_at_offset(adapter, STRAP_Z[1] - STRAP_Z[0], STRAP_Z[0])
    name_last_feature(adapter, "Strap")
    bot_w = STRAP_BOT_X[1] - STRAP_BOT_X[0]
    top_w = STRAP_TOP_X[1] - STRAP_TOP_X[0]
    v_strap = (
        (bot_w + top_w) / 2.0 * (STRAP_TOP_Y - BLOCK_HALF) * (STRAP_Z[1] - STRAP_Z[0])
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(f"volume after strap: {vol:.1f} mm^3 (+{added:.1f}, solid {v_strap:.1f})")
    if abs(added - v_strap) > 0.02 * v_strap:
        raise RuntimeError(f"strap: added {added:.1f}, expected {v_strap:.1f}")
    expected = vol

    # 3. Native #8-32 through tap in the deepened hanger's 3-mm strap.
    # Drill from local z STRAP_Z[0] (15.1), outward normal -Z; the screw
    # enters from behind the bar through the opposite face at STRAP_Z[1].
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
                ("ScrewY", '"ScrewHoleY"'),
            )
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    expected -= math.pi * (screw_dia / 2.0) ** 2 * (STRAP_Z[1] - STRAP_Z[0])
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
    # ch21 p.52 (img03) / ch30 plates: the hanger strap is BLACK-oxide steel
    # (the dark bar the brass pen rod runs beside), not bright.
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
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
