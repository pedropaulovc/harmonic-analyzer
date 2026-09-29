r"""Purchased splicing link for the keeper chain: McMaster-Carr 3606T813 (MHA-150).

McMaster gives no dimensions for the brass trade-size-3 splicing link, so it
is modelled as the envelope named in ``keeper_chain_spec``: a tube whose bore
takes a bead at either end, cross-drilled at mid-length for the running
chain's rod. The axis is local X and the cross-hole local Y, both centred on
the origin; the drive train places two links with an identity rotation.

Run with SolidWorks open::

    uv run python cad\scripts\build_keeper_chain_splice.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)
from keeper_chain_spec import (
    SPLICE_BORE,
    SPLICE_CROSS_HOLE,
    SPLICE_LENGTH,
    SPLICE_OD,
    splice_volume,
)

PART_NAME = "keeper-chain-splice"
MATERIAL = "Brass"


async def _circle_on(adapter, plane: str, dia: float, label: str) -> None:
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(adapter, 0.0, 0.0, dia / 2.0, label, dims=SketchDims())
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # Right Plane's normal is X: mid-plane extrusions run the tube along X.
    await _circle_on(adapter, "Right", SPLICE_OD, "tube")
    name_last_feature(adapter, "TubeProfile")
    check(
        "extrude tube",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SPLICE_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Tube")
    v_tube = math.pi * (SPLICE_OD / 2.0) ** 2 * SPLICE_LENGTH
    await volume_check(adapter, "tube", v_tube, 0.005 * v_tube)

    await _circle_on(adapter, "Right", SPLICE_BORE, "bore")
    name_last_feature(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SPLICE_LENGTH + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")

    # Top Plane's normal is Y: the cross-hole runs along Y through both walls.
    await _circle_on(adapter, "Top", SPLICE_CROSS_HOLE, "cross hole")
    name_last_feature(adapter, "CrossHoleProfile")
    check(
        "cut cross hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SPLICE_OD + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    v = splice_volume()
    await volume_check(adapter, "splice link", v, 0.01 * v)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
