r"""Reproduction script: rocker arm support (book ch. 14 / ch. 30 views; 2 used).

Solid green-painted cast-iron tapered frustum carrying the rocker-pivot
shaft: base 88.9 x 63.5 tapering to 20 x 16.9 at the apex over 177.8 (7")
tall. A ball mount (separate part) seats on the apex and holds the
Ø6.35 pivot shaft at 25.2 above it, putting the pivot axis at machine
y = 228.6 + 25.2 = 253.8. Two stand at (x, z) = (-72.9, +/-101.6).

M6.3 REFUTES the legacy windowed-square-frame `rocker-arm-support`
(184 wide with a 127 square window): no such face appears in any ch. 30
view - the front view shows a plain solid triangle (base spans x
-130..-44, apex at -81 +/- 6) and the side views the old trapezoid
silhouette. Only the legacy side taper (2.5" -> 2/3") and 7" height
survive into this re-authoring. The third leg of the legacy "3 used"
count was the output-end support - a different casting, deferred to M6.4.

Dimensions: cad/DIMENSIONS.md ch. 14 "Rocker pivot & supports layout"
(photo + legacy height, med); mounting holes legacy 5/16" (low).

Built as the side-view trapezoid extruded across X, then two Front-plane
wedge cuts forming the X-taper - NOT a loft: the offset plane a loft's
top profile needs is side-ambiguous live, while the Front-plane sketch
mapping (x, y) -> global (X, Y) is exact. The Right-plane trapezoid is
symmetric in sketch x, so that plane's handedness does not matter.

Layout: origin at the base centre, height +Y, base 88.9 along X / 63.5
along Z. Mounting holes are Ø7.9 x 25 sockets up from the base underside
(hold-down screws come up through the wooden base; fasteners not
modeled), cut mid-plane so the cut direction never matters.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rocker_arm_support.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "rocker-arm-support"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

TOTAL_HEIGHT = 7.00 * IN  # 177.8  DIMENSIONS.md ch14 layout: legacy height kept (med)
BASE_X = 3.50 * IN  # 88.9   ch14 layout: front-view triangle base (photo, med)
BASE_Z = 2.50 * IN  # 63.5   ch14 layout: side-view trapezoid base (legacy, med)
TOP_X = 20.0  # ch14 layout: apex width under the ball-mount foot (photo, med)
TOP_Z = 16.9  # ch14 layout: side-view trapezoid top (legacy 2/3", med)
MOUNTING_HOLE_DIA = 0.3125 * IN  # 7.94  legacy 5/16" hold-down (low)
MOUNTING_HOLE_SPACING = 2.5 * IN  # 63.5  legacy hole pitch across X (low)
MOUNTING_HOLE_DEPTH = 25.0  # socket depth up from the base underside (low)

WEDGE_CUT_DEPTH = BASE_Z * 2.5  # mid-plane total; > base depth
HOLE_CUT_DEPTH = 2.0 * MOUNTING_HOLE_DEPTH  # mid-plane total about y = 0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Side-view trapezoid (Z taper), extruded mid-plane across X.
    check("create_sketch trapezoid", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(
        adapter,
        [
            (-BASE_Z / 2.0, 0.0),
            (BASE_Z / 2.0, 0.0),
            (TOP_Z / 2.0, TOTAL_HEIGHT),
            (-TOP_Z / 2.0, TOTAL_HEIGHT),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "trapezoid sketch", fix_entities=lines)
    check("exit_sketch trapezoid", await adapter.exit_sketch())
    check(
        "extrude trapezoid",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BASE_X, both_directions=True)
        ),
    )
    v_slab = (BASE_Z + TOP_Z) / 2.0 * TOTAL_HEIGHT * BASE_X
    volume = await volume_check(adapter, "trapezoid slab", v_slab, 0.005 * v_slab)

    # X taper: two wedge cuts on the Front plane (mapping (x, y) -> (X, Y)
    # is exact - no handedness probe needed).
    check("create_sketch wedges", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    margin = 15.0  # wedge outer edge clear of the base corner
    left = await add_line_chain(
        adapter,
        [
            (-BASE_X / 2.0, 0.0),
            (-TOP_X / 2.0, TOTAL_HEIGHT),
            (-BASE_X / 2.0 - margin, TOTAL_HEIGHT),
            (-BASE_X / 2.0 - margin, 0.0),
        ],
    )
    right = await add_line_chain(
        adapter,
        [
            (BASE_X / 2.0, 0.0),
            (TOP_X / 2.0, TOTAL_HEIGHT),
            (BASE_X / 2.0 + margin, TOTAL_HEIGHT),
            (BASE_X / 2.0 + margin, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "wedges sketch", fix_entities=[*left, *right])
    check("exit_sketch wedges", await adapter.exit_sketch())
    check(
        "cut wedges",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=WEDGE_CUT_DEPTH, both_directions=True)
        ),
    )
    # Frustum volume via the prismatoid integral: w(s) = BASE_X..TOP_X,
    # d(s) = BASE_Z..TOP_Z linear in s; V = H * integral(w * d).
    a0 = BASE_X * BASE_Z
    a1 = BASE_X * (TOP_Z - BASE_Z) + BASE_Z * (TOP_X - BASE_X)
    a2 = (TOP_X - BASE_X) * (TOP_Z - BASE_Z)
    v_frustum = TOTAL_HEIGHT * (a0 + a1 / 2.0 + a2 / 3.0)
    volume = await volume_check(adapter, "frustum", v_frustum, 0.005 * v_frustum)

    # Hold-down screw sockets up from the base underside; mid-plane cut
    # about y = 0 so only the +Y half removes material.
    check("create_sketch holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        -MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole left",
    )
    await define_circle(
        adapter,
        MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole right",
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut mounting holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HOLE_CUT_DEPTH, both_directions=True)
        ),
    )
    v_holes = 2.0 * math.pi * (MOUNTING_HOLE_DIA / 2.0) ** 2 * MOUNTING_HOLE_DEPTH
    await volume_check(adapter, "mounting holes", volume - v_holes, 0.01 * v_holes + 5.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
