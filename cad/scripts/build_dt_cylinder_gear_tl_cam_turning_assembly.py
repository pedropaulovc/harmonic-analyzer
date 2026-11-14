r"""Reproduction script: dt-cylinder-gear-tl-cam-turning.SLDASM (MHA-DT-12-TL-00).

The cylinder gears' cam turning fixture kit, a shop fixture (issue #2361):
the fixture body dt-cylinder-gear-tl-cam-fixture (MHA-DT-12-TL-01) with the
stub dowel and clock pin pressed in it, and the clamp screw and washer that
hold each MHA-DT-12 gear while its cam is turned. Every part is fixed
(0 DOF) at the pose ``dt_cylinder_gear_tl_cam_fixture_spec`` gives it; the
gear is the workpiece and is not placed, so the washer and screw stand where
a nominal gear holds them. The ``_tl_`` stem keeps the kit out of every
machine assembly and BOM (``_buildgraph.is_shop_fixture``).

The kit frame stands the body's front face up (body +Z to kit +Y): the
bought parts keep their own +Y axes, and the top view looks from the
tailstock with the cam lobe up.

Run only through the supervised farm launcher:
``assembly:dt_cylinder_gear_tl_cam_turning``.
"""

from __future__ import annotations

import sys

from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    save_assembly_and_images,
)
from _assembly_contract import assembly_contract
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY
from _dt_cylinder_gear_tl_cam_turning_interference import ALLOWED_PAIRS
from _session import run_build
from _transforms import IDENTITY, ROT_X_NEG90, euler_from_rows
from dt_cylinder_gear_tl_cam_fixture_spec import (
    PIN_BASE,
    SCREW_SEAT,
    STUB_BASE,
    WASHER_BASE,
)

ASM_NAME = "dt-cylinder-gear-tl-cam-turning"


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )

    # The body: its +Z (the register axis, front face out) to the kit's +Y.
    body_rows = [list(row) for row in ROT_X_NEG90]
    await place_component(
        adapter,
        "dt-cylinder-gear-tl-cam-fixture",
        [0.0, 0.0, 0.0],
        euler_from_rows(body_rows),
        body_rows,
    )
    # The bought parts keep their part frames: axis +Y, pressed or bearing
    # face at their local origin.
    rows = [list(row) for row in IDENTITY]
    await place_component(
        adapter,
        "dt-cylinder-gear-tl-vn-cam-stub",
        list(STUB_BASE),
        euler_from_rows(rows),
        rows,
    )
    await place_component(
        adapter,
        "dt-cylinder-gear-tl-vn-cam-clock-pin",
        list(PIN_BASE),
        euler_from_rows(rows),
        rows,
    )
    await place_component(
        adapter,
        "dt-cylinder-gear-tl-vn-cam-clamp-washer",
        list(WASHER_BASE),
        euler_from_rows(rows),
        rows,
    )
    await place_component(
        adapter,
        "dt-cylinder-gear-tl-vn-cam-clamp-screw",
        list(SCREW_SEAT),
        euler_from_rows(rows),
        rows,
    )
    assert_components_fully_defined(adapter)
    # The two presses and the screw's thread in the stub's tap are the only
    # overlaps (_dt_cylinder_gear_tl_cam_turning_interference).
    check_no_interference(adapter, allowed_pairs=ALLOWED_PAIRS)

    # Title-block identity for the fitter sheet
    # (draw_dt_cylinder_gear_tl_cam_turning_assembly.py); material and finish
    # belong to each component's own drawing.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
