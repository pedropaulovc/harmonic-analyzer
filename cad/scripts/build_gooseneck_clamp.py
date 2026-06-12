r"""Reproduction script: gooseneck clamp (book ch. 19, pp. 44-45).

The green cast block on the east end of the top frame that grips the
gooseneck post: a vertical O16.5 bore the O16 tube slides in (spring
tension adjustment), pinched by a square-head screw from the side --
"a square-head screw [that] pinches the post in its socket" (p. 45).
The screw is merged into this part as just the square head on the block
face -- the shank band between head and bore wall is solid block
material, so a shank feature would be a zero-volume no-op
(simplification; the assembled tube does not interfere).

Layout: origin at the block's base centre on the bore axis (machine
(197, 1040.7, 0) -- on the east rail/crossbar end). Block +Y, bore
along Y, screw along +Z. Dimensions: cad/DIMENSIONS.md ch. 19 (low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_gooseneck_clamp.py
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
)

PART_NAME = "gooseneck-clamp"
MATERIAL = "Gray Cast Iron"  # green casting

BLOCK_HALF_X = 15.0  # DIMENSIONS.md ch19: clamp block (low)
BLOCK_HEIGHT = 29.0
BLOCK_HALF_Z = 12.0
BORE_DIA = 16.5  # slides on the O16 gooseneck (derived)
HEAD_HALF = 5.0  # square screw head 10 x 10 x 6 (low)
HEAD_Z = (12.0, 18.0)  # on the block face; the shank is implicit -- the
# band between the head and the bore wall (8.25) is solid block material
SCREW_Y = 15.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def _assert_volume(adapter, label: str, expected: float, rel_tol: float) -> None:
    vol = await _volume(adapter)
    print(f"  volume after {label}: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > rel_tol * expected:
        raise RuntimeError(f"{label}: volume {vol:.1f} != {expected:.1f}")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Block (Front sketch, mid-plane in Z).
    check("create_sketch block", await adapter.create_sketch("Front"))
    outline = await add_line_chain(
        adapter,
        [
            (-BLOCK_HALF_X, 0.0),
            (BLOCK_HALF_X, 0.0),
            (BLOCK_HALF_X, BLOCK_HEIGHT),
            (-BLOCK_HALF_X, BLOCK_HEIGHT),
        ],
    )
    await ensure_fully_defined(adapter, "block sketch", fix_entities=outline)
    check("exit_sketch block", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * BLOCK_HALF_Z, both_directions=True)
        ),
    )
    expected = 2.0 * BLOCK_HALF_X * BLOCK_HEIGHT * 2.0 * BLOCK_HALF_Z
    await _assert_volume(adapter, "block", expected, 0.005)

    # Vertical bore.
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BLOCK_HEIGHT + 10.0, both_directions=True)
        ),
    )
    expected -= math.pi * (BORE_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    await _assert_volume(adapter, "bore", expected, 0.005)

    # Square screw head (+Z face).
    check("create_sketch head", await adapter.create_sketch("Front"))
    head = await add_line_chain(
        adapter,
        [
            (-HEAD_HALF, SCREW_Y - HEAD_HALF),
            (HEAD_HALF, SCREW_Y - HEAD_HALF),
            (HEAD_HALF, SCREW_Y + HEAD_HALF),
            (-HEAD_HALF, SCREW_Y + HEAD_HALF),
        ],
    )
    await ensure_fully_defined(adapter, "head sketch", fix_entities=head)
    check("exit_sketch head", await adapter.exit_sketch())
    extrude_at_offset(adapter, HEAD_Z[1] - HEAD_Z[0], HEAD_Z[0])
    expected += (2.0 * HEAD_HALF) ** 2 * (HEAD_Z[1] - HEAD_Z[0])
    await _assert_volume(adapter, "head", expected, 0.005)

    # No shank feature: the head sits on the block face (z 12) and the bore
    # wall is at z 8.25, so the whole shank band lies inside solid block
    # material -- a shank extrude is a zero-volume no-op (caught live: the
    # +70.7 mm^3 expectation passed only via the 0.5% tolerance).

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
