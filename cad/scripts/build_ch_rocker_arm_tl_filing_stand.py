r"""Build the rocker arm filing stand (MHA-CH-006-TL-12; shop fixture).

Two steel end blocks and a steel pedestal standing loose on the fitting bench:
the blocks carry the raw blank ends and the pedestal the lower hub face while
the rocker arm is sawn free and filed (``ch_rocker_arm_tl_filing_stand_spec``).

Layout (the spec's SolidWorks frame, +Y up, origin on the bench top under the
pedestal axis): each block outline is its own Top-plane sketch, centred on
Z0, extruded +Y by the block height, so the left block alone carries the
printed sizes; the pedestal is a Front-plane half profile revolved about the
Y axis, so the elevation carries its diameter and length. The part is the
loose set, three bodies laid out side by side for the sheet.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_filing_stand.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_filing_stand_spec import (
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BLOCK_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LAYOUT_BLOCK_WEST_X,
    PEDESTAL_DIA,
    PEDESTAL_LENGTH,
)

PART_NAME = "ch-rocker-arm-tl-filing-stand"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 offcuts
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)
BODY_COUNT = 3  # two end blocks and the pedestal

V_BLOCK = BLOCK_LENGTH * BLOCK_WIDTH * BLOCK_HEIGHT
V_PEDESTAL = math.pi / 4.0 * PEDESTAL_DIA**2 * PEDESTAL_LENGTH


def _require_bodies(adapter, count: int, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != count:
        raise RuntimeError(
            f"{label}: expected {count} solid bodies, found {len(bodies)}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "BlockLength", f"{BLOCK_LENGTH}mm")
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "PedestalDia", f"{PEDESTAL_DIA}mm")
    await set_global(adapter, "PedestalLength", f"{PEDESTAL_LENGTH}mm")

    # One sketch and extrusion per block, each anchored at its south-west
    # corner; the right block's sizes follow the same three globals.
    drive_jobs = []
    volume = 0.0
    for count, (side, west_x) in enumerate(
        zip(("Left", "Right"), LAYOUT_BLOCK_WEST_X, strict=True), start=1
    ):
        profile = SketchDims()
        check(f"create_sketch {side} block", await adapter.create_sketch("Top"))
        south_y = -BLOCK_WIDTH / 2.0  # Top-plane sketch y is model -Z
        points = [
            (west_x, south_y),
            (west_x + BLOCK_LENGTH, south_y),
            (west_x + BLOCK_LENGTH, south_y + BLOCK_WIDTH),
            (west_x, south_y + BLOCK_WIDTH),
        ]
        lines = await add_line_chain(adapter, points)
        prefix = "" if side == "Left" else side
        await define_rectilinear_chain(
            adapter,
            lines,
            points,
            label=f"{side.lower()} end block",
            dims=profile,
            names=[
                f"{prefix}BlockLength",
                f"{prefix}BlockWidth",
                f"{side}BlockX",
                f"{side}BlockY",
            ],
            drives=['"BlockLength"', '"BlockWidth"', None, None],
        )
        await ensure_fully_defined(adapter, f"{side.lower()} end-block profile")
        check(f"exit_sketch {side} block", await adapter.exit_sketch())
        name_last_feature(adapter, f"{side}BlockProfile")
        drive_jobs += profile.apply(adapter, f"{side}BlockProfile")
        check(
            f"extrude {side} block",
            await adapter.create_extrusion(
                ExtrusionParameters(depth=BLOCK_HEIGHT, merge_result=False)
            ),
        )
        name_last_feature(adapter, f"{side}Block")
        drive_jobs.append(
            (
                name_dimensions(adapter, f"{side}Block", [f"{prefix}BlockHeight"])[0],
                '"BlockHeight"',
            )
        )
        volume = await volume_check(
            adapter,
            f"{side.lower()} end block",
            count * V_BLOCK,
            0.002 * count * V_BLOCK,
        )
        _require_bodies(adapter, count, label=f"{side.lower()} end block")

    # Half profile about the Y axis on the Front plane (sketch = model X, Y).
    radius = PEDESTAL_DIA / 2.0
    pedestal = SketchDims()
    check("create_sketch pedestal", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "pedestal axis", await adapter.add_centerline(0.0, 0.0, 0.0, PEDESTAL_LENGTH)
    )
    points = [
        (0.0, 0.0),
        (radius, 0.0),
        (radius, PEDESTAL_LENGTH),
        (0.0, PEDESTAL_LENGTH),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        p0 = points[index]
        p1 = points[(index + 1) % len(points)]
        relation = "horizontal" if p0[1] == p1[1] else "vertical"
        check(
            f"pedestal profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "pedestal axis vertical",
        await adapter.add_sketch_constraint(axis, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "pedestal origin"
    )
    await add_diametric_linear_dimension(
        adapter, axis, lines[1], (radius + 4.0, PEDESTAL_LENGTH / 2.0), "PedestalDia"
    )
    pedestal.record("PedestalDia", '"PedestalDia"')
    check(
        "pedestal length",
        await adapter.add_sketch_dimension(lines[1], None, "linear", PEDESTAL_LENGTH),
    )
    pedestal.record("PedestalLength", '"PedestalLength"')
    await ensure_fully_defined(adapter, "pedestal profile")
    check("exit_sketch pedestal", await adapter.exit_sketch())
    name_last_feature(adapter, "PedestalProfile")
    drive_jobs += pedestal.apply(adapter, "PedestalProfile")
    check(
        "revolve pedestal",
        await adapter.create_revolve(
            RevolveParameters(angle=360.0, merge_result=False)
        ),
    )
    name_last_feature(adapter, "Pedestal")
    volume = await volume_check(
        adapter, "pedestal", volume + V_PEDESTAL, 0.002 * (2.0 * V_BLOCK + V_PEDESTAL)
    )
    _require_bodies(adapter, BODY_COUNT, label="filing stand")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven filing stand (equations neutral)", volume, 0.002 * volume
    )
    _require_bodies(adapter, BODY_COUNT, label="driven filing stand")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
