r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the two-plate cast base, four smooth
polished columns at the corners, the north tapered support frustum that
carries the back end of the rocker-pivot shaft, and the top-frame ring
capping the columns -- column tops flush with the ring's top face at
1040.7 (M6.8 8-view pass: no stub above).

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28 cm
depth):

* harmonic-base fixed at the origin, top face at Y = 50.8.
* tube-frame x4 standing on the base top face near the top-plate corners,
  centres at (+/-197, +/-112) — 25.25/21.35 mm inset from the top-plate
  edges (eight views: columns sit at the extreme corners).
* rocker-arm-support x1 (solid tapered frustum, M6.3 re-authoring;
  M6.9 side depth 40 -> 20 per ch30 p008) at (X, Z) = (+72.9, +101.6) -
  the BACK support only: its apex carries the north pivot ball mount
  (channel.SLDASM) and its west-flank boss clamps the cylinder-arbor
  north end (drive-train.SLDASM). Z anchored by the pivot ball at
  +101.6. The CHANNEL AXIS runs along Z. The frustum is the NORTH
  upright of the rocker-support portal frame the ch30 p008 view shows
  (M6.9): the SOUTH upright is the transgear A-frame at z -111, which
  grips the south pivot ball and carries the frame's top/foot rails
  (output.SLDASM, build_a_frame.py). M6.5's refutation of a second
  free-standing south frustum stands. The M6.1 windowed-gate placement
  at X = 0 was already superseded: the pivot x = arbor 47.5 plus the
  25.4 rod lever = 72.9 (DIMENSIONS.md ch. 14 layout, M6.8-mirrored).
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).
* lag-screw x2 (M6.10 fasteners): the rocker-arm-support hold-downs,
  coming UP through the base from below -- heads recessed in the base
  underside's counterbores (y 0.5..4.5 in the O15 x 4.5 pockets), O7.8
  shanks through the base's O8.2 holes and 19.7 into the support's
  O7.94 x 25 sockets (tips at y 70.5).

Every component is fixed (base) or fully defined by three orthogonal
plane-plane mates against the base part's principal planes; distance-mate
flips are caught by reading back ``Transform2`` after each mate and
re-adding the mate flipped. Final asserts: every component fixed or
``swFullyConstrained``, and zero interferences (tangent/coincident contact
allowed).

The 20-channel pitch stations live in the channel subassembly.

Dimensions: cad/DIMENSIONS.md ch. 6 (base/column), ch. 14 layout
(supports), "Channel & top-frame layout" (top frame); placements
photo-derived (med).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_frame_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    OUT_SLDPRT,
    assert_component_placed,
    assert_components_fully_defined,
    check,
    check_no_interference,
    plane_distance_mate,
    run_build,
    save_assembly_and_images,
    set_isometric_view,
)

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
COLUMN_Z = 112.0
SUPPORT_X = 72.9  # rocker pivot x: arbor 47.5 + 25.4 rod lever (M6.3, M6.8 mirror)
SUPPORT_Z = 133.35 - 63.5 / 2.0  # 101.6: outer face flush w/ top plate edge
LAG_SCREW_X = (SUPPORT_X - 31.75, SUPPORT_X + 31.75)  # 41.15 / 104.65: the
# support's mounting-hole pitch (base HOLE_XZ[2:] / counterbores match)
LAG_SCREW_Y = 4.5  # under-head face = counterbore top; head 0.5..4.5
TOP_FRAME_MID_Y = 1020.2  # ring mid-plane: rails y 999.7..1040.7 (M6.3)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(f"missing part {path}; run build_{name.replace('-', '_')}.py first")
    return str(path)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    support_path = _part("rocker-arm-support")
    top_frame_path = _part("top-frame")

    check("create_assembly", await adapter.create_assembly())
    set_isometric_view(adapter)

    # Base: first insert is auto-fixed by SolidWorks.
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=base_path)
    )
    check("insert_component harmonic-base (auto-fixed)", res)
    base_name = res.data["name"]
    if not res.data.get("fixed"):
        raise RuntimeError("base component was not auto-fixed")

    # Columns at the four top-plate corners.
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        target = [sx * COLUMN_X, BASE_TOP_Y, sz * COLUMN_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=column_path, position=target)
        )
        check(f"insert_component tube-frame @ {target}", res)
        name = res.data["name"]
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, COLUMN_X, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, COLUMN_Z, target
        )
        await plane_distance_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # Rocker-pivot support frustum at the BACK channel-stack end (north
    # only, M6.5), apex under the pivot shaft at x = +72.9 (M6.8 mirror;
    # the part's boss is on its west flank, so identity placement holds).
    target = [SUPPORT_X, BASE_TOP_Y, SUPPORT_Z]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=support_path, position=target)
    )
    check(f"insert_component rocker-arm-support @ {target}", res)
    name = res.data["name"]
    await plane_distance_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, SUPPORT_X, target
    )
    await plane_distance_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, SUPPORT_Z, target
    )
    await plane_distance_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Support hold-down lag screws (M6.10): authored axis +Y with the
    # under-head face on the part's Top plane, so the column-style
    # plane-mate triple pins them exactly.
    lag_path = _part("lag-screw")
    for lx in LAG_SCREW_X:
        target = [lx, LAG_SCREW_Y, SUPPORT_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=lag_path, position=target)
        )
        check(f"insert_component lag-screw @ {target}", res)
        name = res.data["name"]
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, lx, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, SUPPORT_Z, target
        )
        await plane_distance_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, LAG_SCREW_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # Top-frame ring clamped around the four columns, mid-plane y 1020.2.
    target = [0.0, TOP_FRAME_MID_Y, 0.0]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=top_frame_path, position=target)
    )
    check(f"insert_component top-frame @ {target}", res)
    name = res.data["name"]
    await plane_distance_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, 0.0, target
    )
    await plane_distance_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, 0.0, target
    )
    await plane_distance_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, TOP_FRAME_MID_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
