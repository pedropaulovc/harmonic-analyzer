r"""Reproduction script: gooseneck set screw (book ch. 19, pp. 44-45).

The square-head screw that "pinches the post in its socket" (p. 45). On the
machine it threads radially through the top frame's east rail into the Ø17
gooseneck socket -- there is NO clamp block; the socket and its tapped passage
are cast into the frame itself (build_top_frame), and the square head sits
proud on the rail's outer face. Clearly visible in ch19 page001_img04, and its
head shows as a small square nub on the casting flank in the ch30 p003 view.

Layout: authored axis-along-X so the summing assembly seats it at IDENTITY on
the frame's -X outer rail face. The under-head plane is the ORIGIN plane:
square head x -6..0, shank x 0..+8.5 -- long enough to reach the socket wall
(rail half-width 17 minus the Ø17 socket's 8.5 radius) and stop there, leaving
the 0.5 slip between socket and Ø16 post as the interference margin rather than
driving the tip into the post.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_gooseneck_screw.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing
from _fastener_catalog import fastener

PART_NAME = "gooseneck-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

SHANK_DIA = SPEC.model_diameter_mm  # 6.35 (1/4-20 major, threads not modeled)
HEAD_HALF = 5.0  # 10 x 10 square head (ch19 p.44, vs the Ø16 post beside it)
HEAD_T = 6.0  # head thickness
# Shank stops ON the socket wall: rail half-width minus the socket radius.
from frame_anchors import RAIL_HALF
SOCKET_R = 17.0 / 2.0  # build_top_frame GOOSENECK_BORE_DIA / 2
SHANK_LEN = RAIL_HALF - SOCKET_R  # 8.5
assert abs(SHANK_LEN - SPEC.length_mm) < 1e-9, (
    f"catalog length {SPEC.length_mm} != geometric {SHANK_LEN}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 6.35 = 6.35 in, 25.4x too big).
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{SHANK_LEN}mm")
    await set_global(adapter, "HeadHalf", f"{HEAD_HALF}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shank: a Right-plane circle on the origin (both centre coords are origin
    # relations, so define_circle records only the diameter), extruded +X.
    shank = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank,
        names=("ShankCz", "ShankCy", "ShankDiaDim"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHANK_LEN)),
    )
    name_last_feature(adapter, "Shank")
    v = math.pi * (SHANK_DIA / 2.0) ** 2 * SHANK_LEN
    await volume_check(adapter, "shank", v, 0.005 * v)

    # Square head on the other side of the under-head plane.
    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Right"))
    await define_centered_rectangle(
        adapter, HEAD_HALF, HEAD_HALF, "head square", dims=head,
        name_width="Width", drive_width='2 * "HeadHalf"',
        name_depth="Depth", drive_depth='2 * "HeadHalf"',
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_T, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Head")
    # The head is square and the shank round, so the head adds its full block
    # minus the shank disc it swallows over the under-head plane -- nothing:
    # the shank starts AT that plane and runs the other way.
    v += (2.0 * HEAD_HALF) ** 2 * HEAD_T
    await volume_check(adapter, "head", v, 0.005 * v)

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven screw (equations neutral)", v, 0.005 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    apply_drawing_properties(adapter, PART_NAME, {})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
