r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the two-plate cast base, four fluted
columns at the corners, four corner brackets hugging the columns, the two
tapered support frustums that carry the rocker-pivot shaft, and the
top-frame ring clamping the columns just below their tops.

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28 cm
depth):

* harmonic-base fixed at the origin, top face at Y = 50.8.
* tube-frame x4 standing on the base top face near the top-plate corners,
  centres at (+/-197, +/-112) — 25.25/21.35 mm inset from the top-plate
  edges (eight views: columns sit at the extreme corners).
* corner-bracket x4 beside each column on its inboard-X side, upright
  plate tangent to the column, foot toward the machine centre (ch. 30
  views 1/8 show the green tabs against the column bases).
* rocker-arm-support x1 (solid tapered frustum, M6.3 re-authoring) at
  (X, Z) = (-72.9, +101.6) - the BACK support only: its apex carries the
  north pivot ball mount (channel.SLDASM) and its east-flank boss clamps
  the cylinder-arbor north end (drive-train.SLDASM). Outer face flush
  with the top-plate edge (133.35 - 63.5/2 = 101.6). The CHANNEL AXIS
  runs along Z. M6.5 photo audit REFUTES the former south instance: the
  calibrated v3 side view shows no frustum at the front; the south pivot
  ball is gripped by the transgear A-frame's clevis at z -111
  (output.SLDASM, build_a_frame.py). The M6.1 windowed-gate placement at
  X = 0 was already superseded: the pivot x = arbor -47.5 minus the 25.4
  rod lever = -72.9 (DIMENSIONS.md ch. 14 layout).
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).

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
    component_transform,
    log,
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
COLUMN_Z = 112.0
COLUMN_RADIUS = 1.375 * IN / 2.0  # tube-frame OD/2
BRACKET_PLATE_T = 0.3 * IN  # corner-bracket upright plate
BRACKET_X = COLUMN_X - COLUMN_RADIUS - BRACKET_PLATE_T / 2.0  # plate tangent
SUPPORT_X = -72.9  # rocker pivot x: arbor -47.5 - 25.4 rod lever (M6.3)
SUPPORT_Z = 133.35 - 63.5 / 2.0  # 101.6: outer face flush w/ top plate edge
TOP_FRAME_MID_Y = 1020.2  # ring mid-plane: rails y 999.7..1040.7 (M6.3)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_Y_NEG90 = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(f"missing part {path}; run build_{name.replace('-', '_')}.py first")
    return str(path)


async def _plane_mate(
    adapter,
    comp_name: str,
    comp_plane: str,
    base_plane: str,
    base_name: str,
    distance: float,
    target_origin: list[float],
) -> None:
    """Plane-plane mate with wrong-side flip recovery.

    The component is inserted at its exact final transform, so a correctly
    solved mate must not move it; any move beyond tolerance means the
    distance mate picked the far-side solution and is re-added flipped.
    """
    from solidworks_mcp.adapters.base import (
        AddMateParameters,
        MateEntityRef,
        MateRefParameters,
    )

    label = f"mate {comp_plane}@{comp_name} <-> {base_plane}@{base_name} d={distance:g}"
    entities = [
        MateEntityRef(entity_type="PLANE", name=f"{comp_plane}@{comp_name}"),
        MateEntityRef(entity_type="PLANE", name=f"{base_plane}@{base_name}"),
    ]

    async def _add(flip: bool):
        kind = "distance" if abs(distance) > 1e-9 else "coincident"
        return await adapter.add_mate(
            AddMateParameters(
                mate_type=kind,
                entities=entities,
                distance=abs(distance),
                flip=flip,
            )
        )

    res = check(label, await _add(flip=False))
    array = component_transform(adapter, comp_name)
    moved = max(
        abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3)
    )
    if moved <= 0.5:
        return
    mate_name = res.get("name", "")
    log(f"{label}: moved {moved:.2f} mm -> re-adding flipped")
    check(
        f"{label} (delete wrong side)",
        await adapter.delete_mate(MateRefParameters(name=mate_name)),
    )
    check(f"{label} (flipped)", await _add(flip=True))
    array = component_transform(adapter, comp_name)
    moved = max(abs(array[9 + i] * 1000.0 - target_origin[i]) for i in range(3))
    if moved > 0.5:
        raise RuntimeError(f"{label}: component still off target by {moved:.2f} mm")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    bracket_path = _part("corner-bracket")
    support_path = _part("rocker-arm-support")
    top_frame_path = _part("top-frame")

    check("create_assembly", await adapter.create_assembly())

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
        await _plane_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, COLUMN_X, target
        )
        await _plane_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, COLUMN_Z, target
        )
        await _plane_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # Corner brackets: plate tangent to the column inboard side, foot toward
    # the machine centre. +X side needs Ry(-90) (+Z_part -> -X), -X side
    # Ry(+90).
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        target = [sx * BRACKET_X, BASE_TOP_Y, sz * COLUMN_Z]
        rotation = [0.0, -90.0 * sx, 0.0]
        rows = ROT_Y_NEG90 if sx > 0 else ROT_Y_POS90
        res = await adapter.insert_component(
            InsertComponentParameters(
                file_path=bracket_path, position=target, rotation=rotation
            )
        )
        check(f"insert_component corner-bracket @ {target}", res)
        name = res.data["name"]
        await _plane_mate(
            adapter, name, "Front Plane", "Right Plane", base_name, BRACKET_X, target
        )
        await _plane_mate(
            adapter, name, "Right Plane", "Front Plane", base_name, COLUMN_Z, target
        )
        await _plane_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
        )
        assert_component_placed(adapter, name, target, rows)

    # Rocker-pivot support frustum at the BACK channel-stack end (north
    # only, M6.5), apex under the pivot shaft at x = -72.9.
    target = [SUPPORT_X, BASE_TOP_Y, SUPPORT_Z]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=support_path, position=target)
    )
    check(f"insert_component rocker-arm-support @ {target}", res)
    name = res.data["name"]
    await _plane_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, SUPPORT_X, target
    )
    await _plane_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, SUPPORT_Z, target
    )
    await _plane_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Top-frame ring clamped around the four columns, mid-plane y 1020.2.
    target = [0.0, TOP_FRAME_MID_Y, 0.0]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=top_frame_path, position=target)
    )
    check(f"insert_component top-frame @ {target}", res)
    name = res.data["name"]
    await _plane_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, 0.0, target
    )
    await _plane_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, 0.0, target
    )
    await _plane_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, TOP_FRAME_MID_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
