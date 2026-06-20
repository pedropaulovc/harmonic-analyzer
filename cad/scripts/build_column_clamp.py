r"""Reproduction script: column clamp (book ch. 21/22, pp. 50-55).

The green cast collar that clamps each output support bar to a front
column: a ring sliding on the Ø25.4 column (OD rederived from the ch30
8-views, M6.11) with an open channel across its
front face that the 10-square bar lies in -- the bars run tangent IN
FRONT of the columns (p3 90-degree view: bar band z -129..-139 vs column
line z -112). M6.10 fasteners pass: an O3.2 radial hole through the back
wall (local -X, machine +Z after the assembly's Ry90) takes the pinch
screw that locks the collar to the column; the screw is placed BACKED
OUT in magnifier.SLDASM / paper-drive.SLDASM (tip 0.2 inside the hole, clear of the column).

Layout: collar axis +Y (column vertical) through the origin at the bar's
centre height; the bar channel runs along local Z at x 16.8..27.0 (bar
centre 21.9 = column-to-bar offset), floor at y -5.1 so the bar centres
on y 0 with 0.1 clearances all around. The assembly rotates the clamp
about Y per column so local +X points machine -Z. Dimensions:
cad/DIMENSIONS.md ch. 21/22 (M6.4, low/derived).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_column_clamp.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "column-clamp"
MATERIAL = "Gray Cast Iron"  # green casting

COLLAR_OD = 48.0  # DIMENSIONS.md ch21 (low)
COLLAR_BORE = 25.6  # slides on the Ø25.4 column (0.2 slip; OD rederived from 8-views)
COLLAR_HALF_H = 8.0  # 16 tall
CHANNEL_X = (16.8, 27.0)  # bar channel walls (bar 16.9..26.9, 0.1 margins)
CHANNEL_FLOOR_Y = -5.1  # bar bottom -5.0 rests 0.1 above
PINCH_HOLE_DIA = 3.2  # M6.10: radial pinch-screw hole in the back wall


def _channel_removed_volume() -> float:
    """Annulus material removed by the channel cut (x >= wall, y above
    floor): circular-segment areas, full z."""
    def seg(radius: float, d: float) -> float:
        if d >= radius:
            return 0.0
        return radius * radius * math.acos(d / radius) - d * math.sqrt(
            radius * radius - d * d
        )

    area = seg(COLLAR_OD / 2.0, CHANNEL_X[0]) - seg(COLLAR_BORE / 2.0, CHANNEL_X[0])
    return area * (COLLAR_HALF_H - CHANNEL_FLOOR_Y)


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Collar ring.
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, COLLAR_OD / 2.0, "collar OD")
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    check(
        "extrude collar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * COLLAR_HALF_H, both_directions=True)
        ),
    )
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, COLLAR_BORE / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * COLLAR_HALF_H, both_directions=True)
        ),
    )
    expected = (
        math.pi
        * ((COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE / 2.0) ** 2)
        * 2.0
        * COLLAR_HALF_H
    )
    vol = await _volume(adapter)
    print(f"  volume after collar: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"collar volume {vol:.1f} != {expected:.1f}")

    # Bar channel: one rectangular cut through the collar front, from the
    # floor up past the top (Top sketch footprint, offset cut upward).
    check("create_sketch channel", await adapter.create_sketch("Top"))
    channel_rect = [
        (CHANNEL_X[0], -COLLAR_OD),
        (CHANNEL_X[1], -COLLAR_OD),
        (CHANNEL_X[1], COLLAR_OD),
        (CHANNEL_X[0], COLLAR_OD),
    ]
    channel = await add_line_chain(adapter, channel_rect)
    await define_rectilinear_chain(adapter, channel, channel_rect, label="channel")
    await ensure_fully_defined(adapter, "channel sketch")
    check("exit_sketch channel", await adapter.exit_sketch())
    # Cut occupies y CHANNEL_FLOOR_Y .. +COLLAR_HALF_H + 2 (clears the top):
    # mid-plane trick is unusable (asymmetric), so cut a boss-extruded
    # region via cut-extrude at a start offset.
    from _common import feature_name_by_type
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select channel sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureCut4(
        True,  # Sd: single direction
        False,  # Flip side to cut
        True,  # Dir: flip -- the default cut direction from a Top sketch
        # points -Y (verified live: the un-flipped cut removed only the
        # floor..collar-bottom band)
        0, 0,  # T1, T2: blind
        (COLLAR_HALF_H + 2.0 - CHANNEL_FLOOR_Y) / 1000.0,  # D1
        0.0,  # D2
        False, False, False, False,  # Dchk/Ddir
        0.0, 0.0,  # Dang
        False, False,  # OffsetReverse
        False, False,  # TranslateSurface
        False,  # NormalCut
        False, True,  # UseFeatScope, UseAutoSelect
        False, False, False,  # AssemblyFeatureScope, AutoSelectComponents, PropagateFeatureToParts
        3,  # T0: swStartOffset
        CHANNEL_FLOOR_Y / 1000.0,  # StartOffset
        False,  # FlipStartOffset
        True,  # OptimizeGeometry
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("channel cut: FeatureCut4 returned None")
    print(f"  OK  channel cut at offset {CHANNEL_FLOOR_Y}")
    expected -= _channel_removed_volume()
    vol = await _volume(adapter)
    print(f"  volume after channel: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"channel volume {vol:.1f} != {expected:.1f}")

    # Pinch-screw hole: radial along X at (y 0, z 0). A mid-plane cut from
    # the Right plane removes only the back wall -24..-17.6 -- the bore is
    # air and the front side at y 0 was already channel-cut.
    check("create_sketch pinch hole", await adapter.create_sketch("Right"))
    await define_circle(adapter, 0.0, 0.0, PINCH_HOLE_DIA / 2.0, "pinch hole")
    await ensure_fully_defined(adapter, "pinch hole sketch")
    check("exit_sketch pinch hole", await adapter.exit_sketch())
    check(
        "cut pinch hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * COLLAR_OD, both_directions=True)
        ),
    )
    expected -= (
        math.pi * (PINCH_HOLE_DIA / 2.0) ** 2 * (COLLAR_OD - COLLAR_BORE) / 2.0
    )
    vol = await _volume(adapter)
    print(f"  volume after pinch hole: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"pinch hole volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
