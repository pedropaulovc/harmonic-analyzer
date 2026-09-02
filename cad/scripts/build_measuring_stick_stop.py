r"""Reproduction script: measuring stick stop (book ch. 16, pp. 34-37).

The sliding stop of the amplitude gauge (ch16 page001_img04, page002_img01/
img05): a small black steel block slotted for the 8 x 3 brass stick, clamped
wherever the operator sets it by a bright knurled thumbscrew. In use the
block rides the stick with its screw underneath (page002_img01); on the base
top the block straddles the stick from above with the screw up, so the slot
opens through the seat face (the photo's 2 mm lip under the slot is dropped
so the stop can sit on the deck with the stick).

Layout: block centred on the origin in X (along the stick) and Z (across it),
seat face at y = 0, SLOT_W x SLOT_H slot through the seat along X; knurled
thumbscrew head (plain cylinder here) on the top face. Black block, bright
head (face-level finish).

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
    extrude_at_offset,
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

BLOCK_LENGTH = 14.0  # along the stick (X); ch16 page001_img04 photo-scaled (low)
BLOCK_HEIGHT = 11.0  # Y, seat to top face
BLOCK_DEPTH = 14.0  # across the stick (Z)
SLOT_W = 8.4  # across the stick: 0.2 each side of the 8.0 bar (Z)
SLOT_H = 3.4  # 0.4 over the 3.0 bar thickness (Y), open at the seat
HEAD_DIA = 9.0  # knurled thumbscrew head
HEAD_H = 3.0

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
    """Face-level bright finish on the thumbscrew head over the black block:
    every face whose bounding box lies above the block top (y >= BLOCK_HEIGHT)
    and spans the head diameter in x/z. Fails loud if nothing matches."""
    from solidworks_mcp.adapters.com_variant import double_array

    bright = double_array([*POLISHED_STEEL, 1.0, 1.0, 0.5, 0.31, 0.0, 0.0])
    part_h = _early_bound(adapter.currentModel, "IPartDoc")
    n = 0
    y_top = BLOCK_HEIGHT / 1000.0
    for body in part_h.GetBodies2(0, True) or []:
        for face in _com_get(body, "GetFaces") or []:
            box = _com_get(face, "GetBox")
            if not box:
                continue
            ymin = float(box[1])
            xs = (float(box[3]) - float(box[0])) * 1000.0
            zs = (float(box[5]) - float(box[2])) * 1000.0
            if ymin >= y_top - 1e-6 and xs <= HEAD_DIA + 0.3 and zs <= HEAD_DIA + 0.3:
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

    # Stick slot: through the seat face along X (overshoot 1 each end), SLOT_H
    # tall, SLOT_W across (both directions about z = 0).
    slot = SketchDims()
    check("create_sketch slot", await adapter.create_sketch("Front"))
    s_rect = [
        (-half_l - 1.0, -1.0),
        (half_l + 1.0, -1.0),
        (half_l + 1.0, SLOT_H),
        (-half_l - 1.0, SLOT_H),
    ]
    s_lines = await add_line_chain(adapter, s_rect)
    await define_rectilinear_chain(
        adapter, s_lines, s_rect, label="slot", dims=slot,
        names=["SlotLength", "SlotHeight", "SlotAnchorX", "SlotAnchorZ"],
        drives=['"BlockLength" + 2', '"SlotH" + 1', '"BlockLength" / 2 + 1', "1"],
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
    await volume_check(adapter, "slot", expected, 0.01 * V_SLOT)

    # Thumbscrew head on the top face: Top-plane circle at the origin, boss
    # extruded +Y from the block top.
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
    extrude_at_offset(adapter, HEAD_H, BLOCK_HEIGHT)
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
