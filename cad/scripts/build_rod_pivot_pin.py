"""Installed peened pivot, centered on Z=0 with two plain formed heads.

Default is the unchanged finished assembly envelope. OneHeadedBlank contains
one preformed head and a plain 1 mm upset tail instead of the second head.
The allowance is a reconstruction design size; no forming operation is claimed.
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims, _early_bound, _feature_by_name, apply_material, check,
    define_circle, ensure_fully_defined,
    extrude_at_offset, force_rebuild, name_dimensions, name_last_feature,
    run_build, save_part_and_images, volume_check,
)
from _drawing_marks import (
    apply_drawing_properties, clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from rod_pivot_pin_notes import DRAWING_NOTES
import rod_pivot_spec as pivot

PART_NAME = "rod-pivot-pin"
MATERIAL = "Plain Carbon Steel"


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreateConfigurationParameters, ExtrusionParameters
    from solidworks_mcp.adapters.com_variant import null_variant

    check("create pivot pin", await adapter.create_part())
    for feature, diameter, length, offset, flip in (
        ("Journal", pivot.PIN_JOURNAL_DIA, pivot.PIN_GRIP_LENGTH, None, False),
        ("FormedHeadLeft", pivot.PIN_HEAD_DIA, pivot.PIN_HEAD_THICKNESS,
         pivot.PIN_GRIP_LENGTH / 2.0, True),
        ("FormedHeadRight", pivot.PIN_HEAD_DIA, pivot.PIN_HEAD_THICKNESS,
         pivot.PIN_GRIP_LENGTH / 2.0, False),
    ):
        dims = SketchDims()
        check(f"sketch {feature}", await adapter.create_sketch("Front"))
        await define_circle(
            adapter, 0.0, 0.0, diameter / 2.0, feature, dims=dims,
            names=(None, None, "Diameter"),
        )
        await ensure_fully_defined(adapter, feature)
        check(f"exit {feature}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{feature}Profile")
        dims.apply(adapter, f"{feature}Profile")
        if offset is None:
            check(f"extrude {feature}", await adapter.create_extrusion(
                ExtrusionParameters(depth=length, both_directions=True)
            ))
        else:
            extrude_at_offset(adapter, length, offset, flip=flip)
        name_last_feature(adapter, feature)
        # Offset heads also carry a native start-offset dimension; their profile
        # diameter and actual axial feature dimensions remain native/editable.
        if offset is None:
            name_dimensions(adapter, feature, ["GripLength"])

    await force_rebuild(adapter)
    volume = math.pi / 4.0 * (
        pivot.PIN_JOURNAL_DIA**2 * pivot.PIN_GRIP_LENGTH
        + 2.0 * pivot.PIN_HEAD_DIA**2 * pivot.PIN_HEAD_THICKNESS
    )
    await volume_check(adapter, "installed peened pivot", volume, 0.002 * volume)

    # A real alternate physical state, not an annotation pretending the
    # installed two-headed pin can be inserted through the fork.
    check("create one-headed blank configuration", await adapter.create_configuration(
        CreateConfigurationParameters(
            name=pivot.PIN_BLANK_CONFIGURATION,
            description="One preformed head; plain upset stock before assembly",
        )
    ))
    check("activate blank", await adapter.set_active_configuration(pivot.PIN_BLANK_CONFIGURATION))

    def suppress(feature_name: str, state: int) -> None:
        feature = _early_bound(_feature_by_name(adapter, feature_name), "IFeature")
        # swSuppressFeature=0 / swUnSuppressFeature=1; swThisConfiguration=1.
        if not feature.SetSuppression2(state, 1, null_variant()):
            raise RuntimeError(f"cannot set suppression of {feature_name}")

    suppress("FormedHeadRight", 0)
    check("sketch upset tail", await adapter.create_sketch("Front"))
    tail_dims = SketchDims()
    await define_circle(
        adapter, 0.0, 0.0, pivot.PIN_JOURNAL_DIA / 2.0, "upset tail",
        dims=tail_dims, names=(None, None, "TailDiameter"),
    )
    await ensure_fully_defined(adapter, "upset tail")
    check("exit upset tail", await adapter.exit_sketch())
    name_last_feature(adapter, "UpsetTailProfile")
    tail_dims.apply(adapter, "UpsetTailProfile")
    extrude_at_offset(adapter, pivot.PIN_UPSET_ALLOWANCE, pivot.PIN_GRIP_LENGTH / 2.0)
    name_last_feature(adapter, "UpsetTail")
    await force_rebuild(adapter)
    name_dimensions(adapter, "UpsetTail", ["UpsetAllowance", "TailStartOffset"])
    blank_volume = math.pi / 4.0 * (
        pivot.PIN_JOURNAL_DIA**2 * (pivot.PIN_GRIP_LENGTH + pivot.PIN_UPSET_ALLOWANCE)
        + pivot.PIN_HEAD_DIA**2 * pivot.PIN_HEAD_THICKNESS
    )
    await volume_check(adapter, "one-headed pivot blank", blank_volume, 0.002 * blank_volume)

    check("restore installed configuration", await adapter.set_active_configuration("Default"))
    suppress("UpsetTail", 0)
    suppress("FormedHeadRight", 1)
    await force_rebuild(adapter)
    await volume_check(adapter, "restored installed peened pivot", volume, 0.002 * volume)
    clear_dimensions_for_drawing(adapter)
    mark_dimensions_for_drawing(adapter, "Journal", ["GripLength"])
    mark_dimensions_for_drawing(adapter, "UpsetTail", ["UpsetAllowance"])
    for feature in ("Journal", "FormedHeadLeft", "FormedHeadRight"):
        mark_dimensions_for_drawing(adapter, f"{feature}Profile", ["Diameter"])
    await apply_material(adapter, MATERIAL)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
