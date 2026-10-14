r"""Reproduction script: pen hanger (book ch. 24, pp. 60-63).

The black tapered strap bolted to the wheel support bar that hangs the
pen rod's upper guide: a flat 1/8 strap tapering 5/8 -> 3/8 wide,
lying on the bar's front face and descending to a deep guide block with
a 7/32 square channel the 3/16-square pen rod slides in -- the rod is
VERTICAL, so the channel is cut along Y through the block (an M6.4 fix:
the first build wrongly tunnelled it along Z). The block reaches
forward (-Z in the machine) so the pen rod hangs clear of the platen
paper plane while the strap stays flush on the bar. The M6.10 fastener pass
adds a #8-32 tap near the strap top (local (HANGER_SCREW_LOCAL_X,
SCREW_HOLE_XY[1]) = the wheel-bar screw axis: placed IDENTITY at the pen
rod line, locals map directly)
for the hanger-screw shank coming through the bar FROM BEHIND (the
magnifying wheel's rim back face passes just in front of the strap, so no
front-side head fits).

Layout: origin at the guide block centre (machine (PEN_ROD_X, 19-7/8 in,
PEN_Z_MID)); block z BLOCK_Z (back face flush with the wheel-bar front),
strap in the STRAP_Z band rising +Y to the bar band.
The part is authored MACHINE-handed and placed
IDENTITY, so local axes are machine axes (the strap's sideways lean, its
only x-asymmetric feature, runs toward machine east = local -x).
Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low), authored in inch fractions.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_hanger.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
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
from _sketch_chains import define_polygon_chain
from _sketch_rectangle import define_centered_rectangle
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM, HoleSpec, wizard_holes
from _inch import inch
from vn_hanger_screw_spec import SHANK_DIA as HANGER_SCREW_DIA
from mg_wheel_bar_geom import (
    BAR_SIDE as WHEEL_BAR_SIDE,
    HANGER_SCREW_LOCAL_X,
    HANGER_STRAP_TOP_LEFT_X,
)
from pn_pen_hanger_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    FRONT_VIEW_NOTE,
    ISOMETRIC_VIEW_NOTE,
    TOP_VIEW_NOTE,
)

import _telemetry

PART_NAME = "pn-pen-hanger"
MATERIAL = "Plain Carbon Steel"  # black hardware

BLOCK_HALF = inch(1, 4)  # guide block 1/2 x 1/2 (low)
# Deep block: front face 3/16 ahead of the rod line; back face on the bar front
# (derived: wheel-bar front z - PEN_Z_MID). The rod line sits forward of the bar
# (build_pn_pen_assembly PEN_Z_MID) so the 45-degree v-block clears the paper,
# and the block deepens to keep the strap flush on the bar.
BLOCK_Z = (-inch(3, 16), 17.4625)  # -139.7 - -157.1625
# 7/32 square channel the 3/16-square pen rod slides in (1/32: the nearest 1/16,
# 3/16, is line-to-line on the rod).
GUIDE_HOLE_HALF = inch(7, 64)
# 3/32 flat strap: the 1/8 nearest-1/16 strap would eat the whole stock #8-32 x
# 1/2 shank in the 3/8 wheel bar + strap stack (zero thread protrusion).
STRAP_T = inch(3, 32)
STRAP_Z = (round(BLOCK_Z[1] - STRAP_T, 6), BLOCK_Z[1])  # flush with the block back
# M6.10: the selected hanger screw threads into the strap near its top through
# an exact #8-32 tapped Hole Wizard feature, on the wheel-bar axis line
# (derived: WHEEL_BAR_Y - the guide block's machine y, asserted by
# build_pn_pen_assembly).
SCREW_TAP_SPEC = HoleSpec("tapped", "#8-32")
SCREW_HOLE_XY = (HANGER_SCREW_LOCAL_X, 71.4375)
# The strap runs up to the bar top (the bar is centred on the screw axis).
STRAP_TOP_Y = round(SCREW_HOLE_XY[1] + WHEEL_BAR_SIDE / 2.0, 6)
STRAP_TOP_X = (HANGER_STRAP_TOP_LEFT_X, 0.0)  # 5/8 wide at the bar (low)
STRAP_BOT_X = (-inch(3, 16), inch(3, 16))  # 3/8 wide at the block (low)
# Exact tapered-land bounds at the tap centre. The clearance bore's bar-end
# ligament is checked in build_mg_wheel_bar; the receiver uses the thread major
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

    # 1. Solid guide block: an origin-centred 1/2 x 1/2 square -- use
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
    # The +-GUIDE_HOLE_HALF footprint stays inside the block's BLOCK_Z band and
    # well clear of the strap's STRAP_Z band, so a through cut
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

    # 3. Native #8-32 through tap in the deepened hanger's 1/8 strap.
    # Drill from local z STRAP_Z[0], outward normal -Z; the screw
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
