r"""Reproduction script: measuring stick stop (book ch. 16, pp. 34-37).

The sliding stop of the amplitude gauge (ch16 p.34, page001_img04,
page002_img01/img05): a small square black steel block windowed for the
8 x 3 brass stick, clamped wherever the operator sets it by a knurled
thumbscrew. 2026-09-02 user re-read of ch16 p.34: the block is a SQUARE
black cube with the KNURLED THUMBSCREW UNDERNEATH -- a vertical screw below
the block -- not a bright head on the block's side/top. The block therefore
wraps the bar fully: the stick passes through a CLOSED 8.4 x 3.4 window
(floor SLOT_FLOOR above the block bottom) and the thumbscrew screws UP
through the floor to pinch the bar; only the screw's knurled head is bright
below the block.

Layout: block centred on the origin in X (along the stick) and Z (across it),
block bottom face at y = 0, top at BLOCK_HEIGHT; SLOT_W x SLOT_H through-window
along X at y SLOT_FLOOR..SLOT_FLOOR + SLOT_H; knurled thumbscrew head (plain
cylinder here) merged UNDER the block bottom (y -HEAD_H..0), centred. Black
block, bright head (face-level finish).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_measuring_stick_stop.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

import _telemetry

PART_NAME = "measuring-stick-stop"
MATERIAL = "Plain Carbon Steel"  # blackened steel block, bright thumbscrew

# ch16 p.34 (2026-09-02 user re-read): a 12 mm square black cube.
BLOCK_LENGTH = 12.0  # along the stick (X)
BLOCK_HEIGHT = 12.0  # Y, block bottom (thumbscrew side) to top face
BLOCK_DEPTH = 12.0  # across the stick (Z)
SLOT_W = 8.4  # across the stick: 0.2 each side of the 8.0 bar (Z)
SLOT_H = 3.4  # 0.4 over the 3.0 bar thickness (Y)
SLOT_FLOOR = 4.0  # solid floor under the window: the thumbscrew threads up through it
SLOT_ROOF = BLOCK_HEIGHT - SLOT_FLOOR - SLOT_H  # 4.6 of material above the window
HEAD_DIA = 7.0  # knurled thumbscrew head, below the block
HEAD_H = 3.5

# The head must merge into the SOLID floor, not the window opening.
assert SLOT_FLOOR > 0.0 and SLOT_ROOF > 0.0, (SLOT_FLOOR, SLOT_ROOF)
assert HEAD_DIA < min(BLOCK_LENGTH, BLOCK_DEPTH), (HEAD_DIA, BLOCK_LENGTH, BLOCK_DEPTH)

V_BLOCK = BLOCK_LENGTH * BLOCK_HEIGHT * BLOCK_DEPTH
V_SLOT = BLOCK_LENGTH * SLOT_H * SLOT_W
V_HEAD = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
V_TOTAL = V_BLOCK - V_SLOT + V_HEAD


def _com_get(obj, name: str):
    """Zero-argument COM member that late-bound dispatch may expose as a
    method or a value (the ``'tuple' object is not callable`` trap)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


async def _paint_head_bright(adapter) -> None:
    """Face-level bright finish on the thumbscrew head under the black block:
    every face whose bounding box lies at or below the block bottom (y <= 0)
    and spans no more than the head diameter in x/z (the block's own 12 x 12
    bottom face is wider, so it stays black). Fails loud if nothing matches."""
    from solidworks_mcp.adapters.com_variant import double_array

    bright = double_array([*POLISHED_STEEL, 1.0, 1.0, 0.5, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    n = 0
    for body in part_h.GetBodies2(0, True) or []:
        for face in _com_get(body, "GetFaces") or []:
            box = _com_get(face, "GetBox")
            if not box:
                continue
            ymax = float(box[4])
            xs = (float(box[3]) - float(box[0])) * 1000.0
            zs = (float(box[5]) - float(box[2])) * 1000.0
            if ymax <= 1e-6 and xs <= HEAD_DIA + 0.3 and zs <= HEAD_DIA + 0.3:
                face.MaterialPropertyValues = bright
                n += 1
    if n < 2:
        raise RuntimeError(f"thumbscrew head faces not found ({n} matched)")
    _telemetry.info(f"measuring-stick-stop: {n} head faces bright")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "BlockLength", f"{BLOCK_LENGTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    await set_global(adapter, "SlotH", f"{SLOT_H}mm")
    await set_global(adapter, "SlotFloor", f"{SLOT_FLOOR}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "HeadH", f"{HEAD_H}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Block: Front-plane rectangle x -L/2..L/2, y 0..H, extruded symmetrically
    # about z (both directions, BLOCK_DEPTH total). Anchor vertex 0 at
    # (-L/2, 0): x non-zero, y zero -> width, height, anchor x.
    half_l = BLOCK_LENGTH / 2.0
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    rect = [(-half_l, 0.0), (half_l, 0.0), (half_l, BLOCK_HEIGHT), (-half_l, BLOCK_HEIGHT)]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="block", dims=block,
        names=["BlockLength", "BlockHeight", "BlockAnchorX"],
        drives=['"BlockLength"', '"BlockHeight"', '"BlockLength" / 2'],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BLOCK_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    expected = V_BLOCK
    await volume_check(adapter, "block", expected, 0.005 * V_BLOCK)

    # Stick window: a CLOSED through-window along X (overshoot 1 each end),
    # SLOT_H tall from the SLOT_FLOOR station, SLOT_W across (both directions
    # about z = 0). Anchor vertex 0 at (-L/2 - 1, SLOT_FLOOR): both coordinates
    # non-zero -> length, height, anchor x, anchor y (the floor station).
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("Front"))
    s_rect = [
        (-half_l - 1.0, SLOT_FLOOR),
        (half_l + 1.0, SLOT_FLOOR),
        (half_l + 1.0, SLOT_FLOOR + SLOT_H),
        (-half_l - 1.0, SLOT_FLOOR + SLOT_H),
    ]
    s_lines = await add_line_chain(adapter, s_rect)
    await define_rectilinear_chain(
        adapter, s_lines, s_rect, label="slot", dims=slot,
        names=["SlotLength", "SlotHeight", "SlotAnchorX", "SlotAnchorZ"],
        drives=['"BlockLength" + 2', '"SlotH"', '"BlockLength" / 2 + 1', '"SlotFloor"'],
    )
    await ensure_fully_defined(adapter, "slot sketch")
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SLOT_W, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Slot")
    expected -= V_SLOT
    await volume_check(adapter, "slot window", expected, 0.01 * V_SLOT)

    # Thumbscrew head UNDER the block: Top-plane circle at the origin (the
    # block bottom face, y = 0), boss extruded -Y (reverse_direction) so the
    # head hangs y -HEAD_H..0 and merges into the solid SLOT_FLOOR web.
    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head",
        dims=head, names=("HeadCx", "HeadCz", "HeadDia"), drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HEAD_H, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Head")
    expected += V_HEAD
    await volume_check(adapter, "thumbscrew head", expected, 0.01 * V_HEAD)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stop (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await _paint_head_bright(adapter)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
