r"""Reproduction script: summing lever (book ch. 18, pp. 42-43).

The cast-iron pivoted lever that sums the pull of the 20 channel springs:
coefficients plate (20 spring holes), full-length pivot cylinder, edge
ribs at both plate ends, the tapering summation plate, the anchor boss at
its tip, and the diamond middle rib. Re-authors the legacy
SummingLever.cs (geometry uncontradicted by the book; ch. 18 table is the
numeric source).

Layout matches the legacy part: pivot cylinder axis = global Z through
the origin; coefficients plate extends -X (Top-plane sketch, (x, y) ->
global (X, -Z)); summation plate extends +X; plate/rib thicknesses are
mid-plane extrudes. The edge ribs sit at z = +-(L/2 - rib) via the
_common.extrude_at_offset raw-COM stopgap (start-offset extrudes are
Phase 3 surface).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_summing_lever.py
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
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "summing-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# DIMENSIONS.md ch18 (legacy SummingLever.cs values, uncontradicted; med)
PLATE_WIDTH = 1.75 * IN  # 44.45  coefficients plate width (X)
PLATE_LENGTH = 6.0 * IN  # 152.4  coefficients plate length (Z)
PLATE_THICKNESS = 0.2 * IN  # 5.08
CYLINDER_RADIUS = 0.5 * IN  # 12.7  pivot cylinder
RIB_THICKNESS = 0.2 * IN  # 5.08
RIB_PADDING = 0.1 * IN  # 2.54  rib arc stands proud of the cylinder
SUMMATION_HEIGHT = 3.0 * IN  # 76.2  summation plate reach (+X)
SUMMATION_CURVATURE = 0.3 * IN  # 7.62  side-arc sag
ANCHOR_RADIUS = 0.375 * IN  # 9.525
ANCHOR_HEIGHT = 0.75 * IN  # 19.05
HOLE_COUNT = 20
HOLE_RADIUS = 0.02 * IN  # 0.508  spring holes
HOLE_MARGIN = 0.2 * IN  # 5.08

ARC_TOP = CYLINDER_RADIUS + RIB_PADDING  # 15.24 rib/middle-rib arc radius
HOLE_X = -PLATE_WIDTH + HOLE_MARGIN
HOLE_SPAN = PLATE_LENGTH - 2 * HOLE_MARGIN - 2 * RIB_THICKNESS
HOLE_SPACING = HOLE_SPAN / (HOLE_COUNT - 1)
HOLE_Y0 = -(PLATE_LENGTH / 2 - HOLE_MARGIN - RIB_THICKNESS)
RIB_OFFSET = PLATE_LENGTH / 2 - RIB_THICKNESS


def _circumcenter(
    p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]
) -> tuple[float, float]:
    ax, ay = p1
    bx, by = p2
    cx, cy = p3
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    return ux, uy


async def _arc_through(adapter, start, interior, end, label: str) -> str:
    """Add a CCW arc through three points (start -> interior -> end)."""
    cx, cy = _circumcenter(start, interior, end)
    # add_arc draws CCW from start to end; flip if the interior point lies
    # on the CW side.
    a_start = math.atan2(start[1] - cy, start[0] - cx)
    a_int = (math.atan2(interior[1] - cy, interior[0] - cx) - a_start) % (2 * math.pi)
    a_end = (math.atan2(end[1] - cy, end[0] - cx) - a_start) % (2 * math.pi)
    if a_int > a_end:
        start, end = end, start
    return check(
        f"add_arc {label}",
        await adapter.add_arc(cx, cy, start[0], start[1], end[0], end[1]),
    )


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Coefficients plate with the 20 spring holes (nested contours).
    check("create_sketch plate", await adapter.create_sketch("Top"))
    outline = await add_line_chain(
        adapter,
        [
            (-PLATE_WIDTH, -PLATE_LENGTH / 2),
            (0.0, -PLATE_LENGTH / 2),
            (0.0, PLATE_LENGTH / 2),
            (-PLATE_WIDTH, PLATE_LENGTH / 2),
        ],
    )
    # Direct-to-DB: inference around the freshly dimensioned neighbour
    # makes CreateCircleByRadius fail from the second small hole on.
    set_sketch_direct_db(adapter, True)
    for i in range(HOLE_COUNT):
        await define_circle(
            adapter, HOLE_X, HOLE_Y0 + i * HOLE_SPACING, HOLE_RADIUS, f"hole {i + 1}"
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "plate sketch", fix_entities=outline)
    check("exit_sketch plate", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_THICKNESS, both_directions=True)
        ),
    )
    print(f"  volume after plate: {await _volume(adapter):.1f} mm^3")

    # Pivot cylinder along Z.
    check("create_sketch cylinder", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, CYLINDER_RADIUS, "pivot cylinder")
    await ensure_fully_defined(adapter, "cylinder sketch")
    check("exit_sketch cylinder", await adapter.exit_sketch())
    check(
        "extrude cylinder",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_LENGTH, both_directions=True)
        ),
    )
    print(f"  volume after cylinder: {await _volume(adapter):.1f} mm^3")

    # Edge ribs: triangle + wrap arc, offset to each plate end (raw-COM
    # start-offset extrude; Front sketches grow +Z, flip mirrors to -Z).
    for flip, side in ((False, "front"), (True, "back")):
        check(f"create_sketch rib {side}", await adapter.create_sketch("Front"))
        set_sketch_direct_db(adapter, True)
        l1 = check(
            f"rib {side} line 1",
            await adapter.add_line(0.0, ARC_TOP, -PLATE_WIDTH, 0.0),
        )
        l2 = check(
            f"rib {side} line 2",
            await adapter.add_line(-PLATE_WIDTH, 0.0, 0.0, -ARC_TOP),
        )
        arc = check(
            f"rib {side} arc",
            await adapter.add_arc(0.0, 0.0, 0.0, -ARC_TOP, 0.0, ARC_TOP),
        )
        set_sketch_direct_db(adapter, False)
        await ensure_fully_defined(adapter, f"rib {side} sketch", fix_entities=[l1, l2, arc])
        check(f"exit_sketch rib {side}", await adapter.exit_sketch())
        extrude_at_offset(adapter, RIB_THICKNESS, RIB_OFFSET, flip=flip)
        print(f"  volume after rib {side}: {await _volume(adapter):.1f} mm^3")

    # Summation plate: tapering tongue with curved sides, +X to the anchor.
    base_half = PLATE_LENGTH / 4  # legacy: base = plate length / 2
    check("create_sketch summation", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    left = check(
        "summation left edge",
        await adapter.add_line(0.0, -base_half, 0.0, base_half),
    )
    arc_up = await _arc_through(
        adapter,
        (0.0, base_half),
        (SUMMATION_HEIGHT / 2, base_half / 2 - SUMMATION_CURVATURE),
        (SUMMATION_HEIGHT, ANCHOR_RADIUS),
        "summation upper side",
    )
    tip = check(
        "summation tip edge",
        await adapter.add_line(SUMMATION_HEIGHT, ANCHOR_RADIUS, SUMMATION_HEIGHT, -ANCHOR_RADIUS),
    )
    arc_dn = await _arc_through(
        adapter,
        (SUMMATION_HEIGHT, -ANCHOR_RADIUS),
        (SUMMATION_HEIGHT / 2, -base_half / 2 + SUMMATION_CURVATURE),
        (0.0, -base_half),
        "summation lower side",
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "summation sketch", fix_entities=[left, arc_up, tip, arc_dn]
    )
    check("exit_sketch summation", await adapter.exit_sketch())
    check(
        "extrude summation",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_THICKNESS, both_directions=True)
        ),
    )
    print(f"  volume after summation plate: {await _volume(adapter):.1f} mm^3")

    # Anchor boss with wire hole at the summation tip.
    # Fix-only pattern: fixing/dimensioning inside direct-DB mode leaves the
    # solver unrun, so GetConstrainedStatus reads swUnknownConstraint after
    # the toggle. Bare circles in DB mode + fix escalation outside solves it.
    check("create_sketch anchor", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    outer = check(
        "anchor outer circle",
        await adapter.add_circle(SUMMATION_HEIGHT, 0.0, ANCHOR_RADIUS),
    )
    hole = check(
        "anchor wire hole circle",
        await adapter.add_circle(SUMMATION_HEIGHT, 0.0, 2 * HOLE_RADIUS),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "anchor sketch", fix_entities=[outer, hole])
    check("exit_sketch anchor", await adapter.exit_sketch())
    check(
        "extrude anchor",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ANCHOR_HEIGHT, both_directions=True)
        ),
    )
    print(f"  volume after anchor: {await _volume(adapter):.1f} mm^3")

    # Middle rib: lines tangent to the r=ARC_TOP circle from both lever
    # tips, joined by arcs (exact tangent points computed here).
    check("create_sketch middle rib", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities: list[str] = []
    r = ARC_TOP
    points = {}
    for label, px in (("left", -PLATE_WIDTH), ("right", SUMMATION_HEIGHT)):
        tx = r * r / px
        ty = r * math.sqrt(1.0 - (r / px) ** 2)
        points[label] = (tx, ty)
    lx, ly = points["left"]
    rx, ry = points["right"]
    entities.append(
        check("mid-rib line 1", await adapter.add_line(-PLATE_WIDTH, 0.0, lx, ly))
    )
    # Upper arc: CCW from the right tangent point to the left one (through
    # the top of the circle).
    entities.append(
        check("mid-rib upper arc", await adapter.add_arc(0.0, 0.0, rx, ry, lx, ly))
    )
    entities.append(
        check("mid-rib line 2", await adapter.add_line(rx, ry, SUMMATION_HEIGHT, 0.0))
    )
    entities.append(
        check("mid-rib line 3", await adapter.add_line(SUMMATION_HEIGHT, 0.0, rx, -ry))
    )
    entities.append(
        check("mid-rib lower arc", await adapter.add_arc(0.0, 0.0, lx, -ly, rx, -ry))
    )
    entities.append(
        check("mid-rib line 4", await adapter.add_line(lx, -ly, -PLATE_WIDTH, 0.0))
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "middle rib sketch", fix_entities=entities)
    check("exit_sketch middle rib", await adapter.exit_sketch())
    check(
        "extrude middle rib",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIB_THICKNESS, both_directions=True)
        ),
    )
    print(f"  volume after middle rib: {await _volume(adapter):.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
