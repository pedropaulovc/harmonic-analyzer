r"""Build the rocker arm's strap shim stack (MHA-CH-006-TL-11; shop fixture).

One of four supports the rocker blank stands on in S1 and S4: a piece of O1
ground flat stock on a steel shim pack at the nominal gap
(``ch_rocker_arm_tl_strap_shim_stack_spec``).

Layout (the inventory's fixture frame): the shim pack is an origin-centred
Front-plane rectangle extruded +Z by its thickness; the ground piece, a
second body (merge off), is the same rectangle extruded +Z from an offset
start at the pack's top, so the stack's underside is Z0 and its bearing face
is the piece's top.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_strap_shim_stack.py
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_rectangle import define_centered_rectangle
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_strap_shim_stack_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    SHIM_THICK,
    STACK_HEIGHT,
    STACK_LENGTH,
    STACK_WIDTH,
    STRIP_THICK,
)

PART_NAME = "ch-rocker-arm-tl-strap-shim-stack"
MATERIAL = (
    "Plain Carbon Steel"  # the registry row names the O1 ground flat and steel shim
)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

V_SHIM = STACK_LENGTH * STACK_WIDTH * SHIM_THICK
V_STRIP = STACK_LENGTH * STACK_WIDTH * STRIP_THICK


def _body_boxes(adapter) -> list[tuple[float, ...]]:
    return [
        tuple(
            float(value) * 1000.0 for value in _early_bound(body, "IBody2").GetBodyBox()
        )
        for body in _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False)
        or ()
    ]


def _require_layers(adapter, *, label: str) -> None:
    """Two bodies: the pack Z0..SHIM_THICK under the piece SHIM_THICK..STACK_HEIGHT.
    The offset start must run +Z: flipped, the piece would sit below Z0 with
    the same volume. IBody2.GetBodyBox is approximate, so 0.05 mm."""
    boxes = sorted(_body_boxes(adapter), key=lambda box: box[2])
    expected = ((0.0, SHIM_THICK), (SHIM_THICK, STACK_HEIGHT))
    if len(boxes) != 2 or any(
        abs(box[2] - low) > 0.05 or abs(box[5] - high) > 0.05
        for box, (low, high) in zip(boxes, expected, strict=True)
    ):
        raise RuntimeError(
            f"{label}: expected bodies spanning Z {expected}, found {boxes}"
        )


async def _profile(adapter, label: str, feature: str) -> list[tuple[str, str]]:
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter,
        STACK_LENGTH / 2.0,
        STACK_WIDTH / 2.0,
        label,
        dims=dims,
        name_width="StackLength",
        name_depth="StackWidth",
        drive_width='"StackLength"',
        drive_depth='"StackWidth"',
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "StackLength", f"{STACK_LENGTH}mm")
    await set_global(adapter, "StackWidth", f"{STACK_WIDTH}mm")
    await set_global(adapter, "StripThick", f"{STRIP_THICK}mm")
    await set_global(adapter, "ShimThick", f"{SHIM_THICK}mm")

    drive_jobs = await _profile(adapter, "shim pack", "ShimProfile")
    check(
        "extrude shim pack",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHIM_THICK)),
    )
    name_last_feature(adapter, "ShimPack")
    drive_jobs.append(
        (name_dimensions(adapter, "ShimPack", ["ShimThick"])[0], '"ShimThick"')
    )
    volume = await volume_check(adapter, "shim pack", V_SHIM, 0.005 * V_SHIM)

    # The ground piece: one separate solid on the pack.
    drive_jobs += await _profile(adapter, "ground piece", "StripProfile")
    extrude_at_offset(adapter, STRIP_THICK, SHIM_THICK, merge_result=False)
    name_last_feature(adapter, "Strip")
    # Offset bosses expose depth first and start offset second.
    strip_thick, strip_seat = name_dimensions(
        adapter, "Strip", ["StripThick", "StripSeat"]
    )
    drive_jobs += [(strip_thick, '"StripThick"'), (strip_seat, '"ShimThick"')]
    volume = await volume_check(adapter, "stack", volume + V_STRIP, 0.005 * V_STRIP)
    _require_layers(adapter, label="stack")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven stack (equations neutral)", volume, 0.002 * volume
    )
    _require_layers(adapter, label="driven stack")

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
