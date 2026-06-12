r"""Reproduction script: A-frame (book ch. 14 pp. 26-29 + ch. 30 views).

The green cast stand on the base's front-west corner: the SOUTH upright
of the rocker-support portal frame. M6.5 photo audit: the calibrated
ch. 30 front view shows this casting's apex clevis gripping the SOUTH
PIVOT BALL at (-72.9, 253.8) - the A-frame doubles as the front
rocker-shaft support. The ch. 30 p008 side view (brightened) shows the
full casting is a WINDOWED PORTAL FRAME: this upright + the north
frustum (build_rocker_arm_support.py) joined by a TOP RAIL under the
ball-mount seats and a FOOT RAIL on the base - reinstating the legacy
windowed-frame reading that M6.3/M6.5 wrongly refuted (the -x side view
hides the frame behind the cone/drum; the +x view shows it plainly,
window ~127 matching the legacy part). Both rails are modeled HERE so
the two-part split survives; they stop 0.25 short of the frustum faces
(separate components - the real machine is one casting, documented
simplification). The pivot-ball-mount (channel.SLDASM) seats on the
saddle top at machine y 228.6 between the clevis ears; the transgear
pinion bar starts just east of the clevis.

Plate thickness: p008 reads ~28-30 along Z, but the band is pinned by
neighbours to 18.5: front face machine z -117.5 (0.5 clear of the parked
measuring stick at z <= -118, output.SLDASM) and back face machine
z -99.0 (the ch25 handle cross-rod plane assert in
build_drive_train_assembly.py needs HANDLE_Z - 3 = -98 behind it).

Layout: local x = MACHINE x (the script is authored machine-handed and
declared "x0" in MIRROR_PLANE - the part lost its local-z symmetry to
the one-sided rails, so the old "z" Ry180 stand-in would flip the rails
to the south), local y 0 = base top (machine 50.8), local z 0 = clevis
mid-plane (machine z -111). Plate foot x +45..+115 tapering
to the apex x +59..+87 at the ball-mount seat y 177.8 (machine 228.6);
ears rise 20 above the seat, gap 16.2 flanking the mount's diameter-16
base. The diameter-6.35 pivot shaft (bottom 250.65) clears the ear tops
(248.6) by 2. Top rail 20 x 16 (y 161.8..177.8 = machine 212.6..228.6,
matching the photo window top) runs to machine z +90.45; foot rail
30 x 20 on the base runs to machine z +81.35 (frustum faces minus 0.25).
Dimensions: cad/DIMENSIONS.md ch. 14 + ch. 23 layout (M6.9, low/med).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_a_frame.py
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
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "a-frame"
MATERIAL = "Gray Cast Iron"  # green casting

FOOT_X = (45.0, 115.0)  # foot span on the base top, machine x (med)
APEX_X = (59.0, 87.0)  # 28-wide top centred near the pivot machine x +72.9 (med)
SEAT_Y = 177.8  # ball-mount seat: machine 228.6 = pivot 253.8 - ball rise 25.2
PLATE_Z = (-6.5, 12.0)  # machine -117.5..-99.0: stick / ch25-handle pinch (docstring)
EAR_HALF_GAP = 8.1  # ears flank the ball mount's diameter-16 base + 0.1 clearance
EAR_HALF_Z = 11.1  # ears 3 thick
EAR_HEIGHT = 20.0  # ear tops at 197.8 (machine 248.6): shaft clears by 2
SADDLE_Y0 = 158.0  # saddle block bridges the plate to the wider clevis ears

# Portal-frame rails (ch30 p008 side view): both spring from the plate
# back face (machine z -99) and stop 0.25 short of the north frustum
# (build_rocker_arm_support.py at machine z +101.6, BASE_Z 40 / TOP_Z 20).
RAIL_Z0 = PLATE_Z[1]  # rails' net volume starts at the plate back face
RAIL_OVERLAP = 2.0  # sketch offset 2 inside the plate so the solids merge
TOP_RAIL_X = (62.9, 82.9)  # = frustum apex span (20), inside the 28 apex
TOP_RAIL_DEPTH = 16.0  # y 161.8..177.8 (machine 212.6..228.6 = photo window top)
TOP_RAIL_Z1 = 201.45  # machine +90.45: frustum apex face 90.70 at rail bottom - 0.25
FOOT_RAIL_X = (59.75, 89.75)  # 30 wide, west face 0.25 east of the
# arbor-pedestal block (machine x +35.5..+59.5, drive-train.SLDASM)
FOOT_RAIL_H = 20.0  # photo: bolted foot flange ~20 tall
FOOT_RAIL_Z1 = 192.35  # machine +81.35: frustum base face +81.6 - 0.25

# Foot-rail hold-down bolt holes (M6.10, ch30 p008 hex heads): O8.2 for
# the 5/16" hex-bolt shanks, on the rail centreline. The bolt heads'
# worst hex corner stays 2.6 clear of the cylinder-train tip circles
# (r 51.65 about machine (47.5, 126.8)) and 3.2 of cone gear j=1.
BOLT_HOLE_DIA = 8.2
BOLT_HOLE_X = (FOOT_RAIL_X[0] + FOOT_RAIL_X[1]) / 2.0  # 74.75
BOLT_HOLE_Z = (57.0, 147.0)  # machine z -54 / +36 (quarter points, low)


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Tapered plate (Front sketch trapezoid, offset extrude along +Z:
    # asymmetric about the clevis mid-plane, see docstring).
    check("create_sketch plate", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    plate = await add_line_chain(
        adapter,
        [
            (FOOT_X[0], 0.0),
            (FOOT_X[1], 0.0),
            (APEX_X[1], SEAT_Y),
            (APEX_X[0], SEAT_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "plate sketch", fix_entities=plate)
    check("exit_sketch plate", await adapter.exit_sketch())
    plate_t = PLATE_Z[1] - PLATE_Z[0]
    extrude_at_offset(adapter, plate_t, PLATE_Z[0])
    foot_w = FOOT_X[1] - FOOT_X[0]
    apex_w = APEX_X[1] - APEX_X[0]
    v_plate = (foot_w + apex_w) / 2.0 * SEAT_Y * plate_t
    expected = v_plate
    await volume_check(adapter, "plate", expected, 0.005 * expected)

    # Saddle block at the apex: full clevis width, bridging the plate to
    # the FRONT ear (the ear band z -11.1..-8.1 sits ahead of the plate
    # front face -6.5 and would otherwise be a detached body).
    check("create_sketch saddle", await adapter.create_sketch("Top"))
    saddle = await add_line_chain(
        adapter,
        [
            (APEX_X[0], -EAR_HALF_Z),
            (APEX_X[1], -EAR_HALF_Z),
            (APEX_X[1], EAR_HALF_Z),
            (APEX_X[0], EAR_HALF_Z),
        ],
    )
    await ensure_fully_defined(adapter, "saddle sketch", fix_entities=saddle)
    check("exit_sketch saddle", await adapter.exit_sketch())
    extrude_at_offset(adapter, SEAT_Y - SADDLE_Y0, SADDLE_Y0)
    plate_in_saddle = min(PLATE_Z[1], EAR_HALF_Z) - max(PLATE_Z[0], -EAR_HALF_Z)
    v_saddle = apex_w * (SEAT_Y - SADDLE_Y0) * (2.0 * EAR_HALF_Z - plate_in_saddle)
    expected += v_saddle
    await volume_check(adapter, "saddle", expected, 0.02 * v_saddle)

    # Clevis ears flanking the ball mount's base (Top sketch, offset extrude).
    check("create_sketch ears", await adapter.create_sketch("Top"))
    ears: list[str] = []
    for side in (1.0, -1.0):
        ears += await add_line_chain(
            adapter,
            [
                (APEX_X[0], side * EAR_HALF_GAP),
                (APEX_X[1], side * EAR_HALF_GAP),
                (APEX_X[1], side * EAR_HALF_Z),
                (APEX_X[0], side * EAR_HALF_Z),
            ],
        )
    await ensure_fully_defined(adapter, "ears sketch", fix_entities=ears)
    check("exit_sketch ears", await adapter.exit_sketch())
    extrude_at_offset(adapter, EAR_HEIGHT, SEAT_Y)
    v_ears = 2.0 * apex_w * (EAR_HALF_Z - EAR_HALF_GAP) * EAR_HEIGHT
    expected += v_ears
    await volume_check(adapter, "ears", expected, 0.02 * v_ears)

    # Top rail: under the ball-mount seats, spanning to the north frustum
    # apex (Front sketch cross-section, offset extrude along +Z).
    check("create_sketch top rail", await adapter.create_sketch("Front"))
    top_rail = await add_line_chain(
        adapter,
        [
            (TOP_RAIL_X[0], SEAT_Y - TOP_RAIL_DEPTH),
            (TOP_RAIL_X[1], SEAT_Y - TOP_RAIL_DEPTH),
            (TOP_RAIL_X[1], SEAT_Y),
            (TOP_RAIL_X[0], SEAT_Y),
        ],
    )
    await ensure_fully_defined(adapter, "top rail sketch", fix_entities=top_rail)
    check("exit_sketch top rail", await adapter.exit_sketch())
    z0 = RAIL_Z0 - RAIL_OVERLAP
    extrude_at_offset(adapter, TOP_RAIL_Z1 - z0, z0)
    v_top_rail = (
        (TOP_RAIL_X[1] - TOP_RAIL_X[0]) * TOP_RAIL_DEPTH * (TOP_RAIL_Z1 - RAIL_Z0)
    )
    expected += v_top_rail
    await volume_check(adapter, "top rail", expected, 0.02 * v_top_rail)

    # Foot rail: on the base top, spanning to the north frustum base
    # (the photo's bolted flange; hex-bolts placed in output.SLDASM, M6.10).
    check("create_sketch foot rail", await adapter.create_sketch("Front"))
    foot_rail = await add_line_chain(
        adapter,
        [
            (FOOT_RAIL_X[0], 0.0),
            (FOOT_RAIL_X[1], 0.0),
            (FOOT_RAIL_X[1], FOOT_RAIL_H),
            (FOOT_RAIL_X[0], FOOT_RAIL_H),
        ],
    )
    await ensure_fully_defined(adapter, "foot rail sketch", fix_entities=foot_rail)
    check("exit_sketch foot rail", await adapter.exit_sketch())
    extrude_at_offset(adapter, FOOT_RAIL_Z1 - z0, z0)
    v_foot_rail = (
        (FOOT_RAIL_X[1] - FOOT_RAIL_X[0]) * FOOT_RAIL_H * (FOOT_RAIL_Z1 - RAIL_Z0)
    )
    expected += v_foot_rail
    await volume_check(adapter, "foot rail", expected, 0.02 * v_foot_rail)

    # Hold-down bolt holes through the foot rail (M6.10): Top sketch
    # (x, y) -> global (X, -Z), mid-plane cut so the direction never
    # matters (below y 0 is outside the part).
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch bolt holes", await adapter.create_sketch("Top"))
    for z in BOLT_HOLE_Z:
        await define_circle(
            adapter, BOLT_HOLE_X, -z, BOLT_HOLE_DIA / 2.0, f"bolt hole z{z:.0f}"
        )
    await ensure_fully_defined(adapter, "bolt holes sketch")
    check("exit_sketch bolt holes", await adapter.exit_sketch())
    check(
        "cut bolt holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * FOOT_RAIL_H, both_directions=True)
        ),
    )
    v_holes = 2.0 * math.pi * (BOLT_HOLE_DIA / 2.0) ** 2 * FOOT_RAIL_H
    expected -= v_holes
    await volume_check(adapter, "bolt holes", expected, 0.02 * v_holes)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
