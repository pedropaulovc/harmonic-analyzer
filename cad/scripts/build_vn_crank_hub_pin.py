r"""Build MHA-VN-029 from McMaster 91585A377 stock geometry.

The vendor's chamfered 18-8 pin runs on local +Z from the flush outboard face.
In the drive train +Z is parallel to the crankshaft, at six o'clock on the
arm/hub seam. Its stock 4-mm overall still equals ``ARM_THICKNESS / 2``.
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _fastener_catalog import fastener
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
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
from _drawing_tolerances import set_dimension_bilateral_tolerance
from vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    PIN_CHAMFER_AXIAL,
    PIN_CHAMFER_ANGLE_DEG,
    PIN_DIA,
    PIN_DIA_BAND,
    PIN_END_RADIUS,
    PIN_FULL_DIA_LENGTH,
    PIN_LEN,
)


PART_NAME = "vn-crank-hub-pin"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material
PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * (
    PIN_R**2 * PIN_FULL_DIA_LENGTH
    + 2.0
    * PIN_CHAMFER_AXIAL
    * (PIN_R**2 + PIN_R * PIN_END_RADIUS + PIN_END_RADIUS**2)
    / 3.0
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")
    await set_global(adapter, "PinChamferAxial", f"{PIN_CHAMFER_AXIAL}mm")
    await set_global(adapter, "PinChamferAngleDeg", str(PIN_CHAMFER_ANGLE_DEG))
    await set_global(
        adapter,
        "PinEndRadius",
        '"PinDia" / 2 - "PinChamferAxial" * tan("PinChamferAngleDeg")',
    )

    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "axis centerline", await adapter.add_centerline(0.0, 0.0, -PIN_LEN, 0.0)
    )
    points = [
        (0.0, 0.0),
        (0.0, PIN_END_RADIUS),
        (-PIN_CHAMFER_AXIAL, PIN_R),
        (-(PIN_LEN - PIN_CHAMFER_AXIAL), PIN_R),
        (-PIN_LEN, PIN_END_RADIUS),
        (-PIN_LEN, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (x0, y0), (x1, y1) = points[index], points[(index + 1) % len(lines)]
        if y0 == y1:
            relation = "horizontal"
        elif x0 == x1:
            relation = "vertical"
        else:
            continue  # Source-grounded lead offsets determine these slopes.
        check(
            f"pin {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "equal pin end radii",
        await adapter.add_sketch_constraint(lines[0], lines[4], "equal"),
    )
    outline = lines[2]
    await dimension_between(
        adapter,
        f"{lines[5]}.start",
        f"{lines[5]}.end",
        "horizontal_distance",
        PIN_LEN,
        "pin length",
    )
    pin.record("PinLen", '"PinLen"')
    await dimension_between(
        adapter,
        f"{lines[0]}.start",
        f"{lines[0]}.end",
        "vertical_distance",
        PIN_END_RADIUS,
        "stock end radius",
    )
    pin.record("PinEndRadius", '"PinEndRadius"')
    for index, name in ((1, "OutboardLead"), (3, "InboardLead")):
        await dimension_between(
            adapter,
            f"{lines[index]}.start",
            f"{lines[index]}.end",
            "horizontal_distance",
            PIN_CHAMFER_AXIAL,
            f"stock {name}",
        )
        pin.record(name, '"PinChamferAxial"')
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
    volume = await volume_check(adapter, "axial seam pin", V_PIN, 0.005 * V_PIN)

    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven axial pin", volume, 0.005 * V_PIN)
    await bbox_extent_check(adapter, "supplier pin true end span", "z", PIN_LEN, 1e-6)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature, dimensions in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, dimensions)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "PinDia", *PIN_DIA_BAND, places=3
    )
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Stock Name": SPEC.stock_name,
            "Supplier": SPEC.supplier,
            "Supplier SKUs": ", ".join(SPEC.skus),
            "Manufacturing Notes": DRAWING_NOTES,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
