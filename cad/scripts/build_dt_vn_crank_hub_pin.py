r"""Build the MHA-DT-VN-59 axial crank-arm-to-hub seam pin.

The flat-ended cylinder runs on local +Z from the outboard face.  In the drive
train +Z is parallel to the crankshaft and the pin sits at six o'clock, half in
the arm and half in the hub-seat seam.  Its length is shared geometry:
``ARM_THICKNESS / 2``. The seam hole is blind, so the pin is a pull-dowel:
a native #0-80 UNF THRU Hole Wizard tap starts at the flush outboard end.
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _holes import _KINDS, _standard, _verify_tap_metadata, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from dt_vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    PIN_DIA,
    PIN_LEN,
    PULL_THREAD_HOLE,
    PULL_THREAD_TAP_DRILL,
)


PART_NAME = "dt-vn-crank-hub-pin"
MATERIAL = "Plain Carbon Steel"
PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN
TAP_R = PULL_THREAD_TAP_DRILL / 2.0
V_TAP = math.pi * TAP_R**2 * PIN_LEN
# Local +Z runs inboard. Select the opposite-facing plane at station zero,
# not the inaccessible pin end at +PIN_LEN, for the extraction screw entry.
PULL_THREAD_ENTRY_POINT = (0.0, 0.0, 0.0)
PULL_THREAD_ENTRY_NORMAL = (0.0, 0.0, -1.0)


def _require_pull_thread_definition(definition: Any) -> None:
    """Prove the committed feature is the specified inch tap and #56 cut."""
    _verify_tap_metadata(definition, PULL_THREAD_HOLE, "MHA-VN-029 built pull thread")
    for member, expected in (
        ("Standard2", _standard(PULL_THREAD_HOLE.kind)),
        ("FastenerType2", _KINDS[PULL_THREAD_HOLE.kind][1]),
        ("FastenerSize", PULL_THREAD_HOLE.size),
    ):
        actual = getattr(definition, member)
        if actual != expected:
            raise RuntimeError(
                f"MHA-VN-029 native extraction {member} {actual!r} != {expected!r}"
            )
    if not math.isclose(
        float(definition.ThruTapDrillDiameter) * 1000.0,
        PULL_THREAD_TAP_DRILL,
        rel_tol=0.0,
        abs_tol=0.005,
    ):
        raise RuntimeError(
            f"MHA-VN-029 native tap drill is not #56 ({PULL_THREAD_TAP_DRILL:.4f} mm)"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline", await adapter.add_centerline(0.0, 0.0, -PIN_LEN, 0.0)
    )
    points = [(0.0, 0.0), (0.0, PIN_R), (-PIN_LEN, PIN_R), (-PIN_LEN, 0.0)]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (_, y0), (_, y1) = points[index], points[(index + 1) % len(lines)]
        relation = "horizontal" if y0 == y1 else "vertical"
        check(
            f"pin {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    outline = lines[1]
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        PIN_LEN,
        "pin length",
    )
    pin.record("PinLen", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-PIN_LEN / 2.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", 0.0, 0.0, "pin anchor"
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs = pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    await volume_check(adapter, "axial seam pin", V_PIN, 0.005 * V_PIN)

    # The native feature owns both the real tap-drill cut and the associative
    # through-thread callout. Do not fake a blind ThreadDepth equal to the pin
    # length: the tap must run clear of the far end to complete its lead.
    pull_thread = wizard_holes(
        adapter,
        PULL_THREAD_HOLE,
        [PULL_THREAD_ENTRY_POINT],
        PULL_THREAD_ENTRY_NORMAL,
        "MHA-VN-029 extraction thread",
        name="PullThread",
        expect_dia_mm=PULL_THREAD_TAP_DRILL,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += pull_thread.placement_drive_jobs
    if not math.isclose(
        pull_thread.hole_dia_mm, PULL_THREAD_TAP_DRILL, rel_tol=0.0, abs_tol=0.005
    ):
        raise RuntimeError(
            f"MHA-VN-029 native tap drill is not {PULL_THREAD_TAP_DRILL:.4f} mm"
        )
    volume = await volume_check(
        adapter, "native through pull tap", V_PIN - V_TAP, 0.005 * V_PIN
    )

    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven axial pin", volume, 0.005 * V_PIN)
    feature = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName(
        pull_thread.name
    )
    if feature is None:
        raise RuntimeError("MHA-VN-029 native pull-thread feature is missing")
    definition = _early_bound(
        _early_bound(feature, "IFeature").GetDefinition(), "IWizardHoleFeatureData2"
    )
    _require_pull_thread_definition(definition)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature, dimensions in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, dimensions)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
