r"""Reproduction script: dt-cone-gear-tl-arbor.SLDASM (MHA-DT-03-TL-05).

The keyed cutting arbor kit, a shop fixture (issue #2465;
``dt_cone_gear_tl_arbor_assembly_spec``): the arbor, its bonded key, the three
backing collars and the nut, each fixed at its kit pose (0 DOF). The ``_tl_``
stem keeps the kit out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``). The fitting sheet prints no reference
dimension: the blank's place is item 1's own shoulder and seat, part
dimensions on its sheet (rule 24).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_arbor_assembly.py
"""

from __future__ import annotations

import sys

from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    place_component,
    save_assembly_and_images,
)
from _assembly_contract import assembly_contract
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY
from _session import run_build
from _transforms import euler_from_rows
import dt_cone_gear_tl_arbor_assembly_spec as spec

ASM_NAME = "dt-cone-gear-tl-arbor"
if ASM_NAME != spec.ASM_NAME:
    raise AssertionError("the builder's contract and the kit spec disagree")


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )
    # Inserted in BOM order (spec.BOM_ORDER): the fitting steps cite the BOM's
    # item numbers. Literal stems, so the build graph reads the sources.
    rows = [list(row) for row in spec.IDENTITY_ROWS]
    euler = euler_from_rows(rows)
    collars = spec.collar.CONFIGURATIONS
    await place_component(
        adapter,
        "dt-cone-gear-tl-keyed-arbor",
        list(spec.POSITIONS[spec.ARBOR]),
        euler,
        rows,
    )
    for configuration in collars:
        await place_component(
            adapter,
            "dt-cone-gear-tl-arbor-collar",
            list(spec.POSITIONS[spec.member(configuration)]),
            euler,
            rows,
            configuration=configuration,
            label=spec.member(configuration),
        )
    await place_component(
        adapter,
        "dt-cone-gear-tl-arbor-key",
        list(spec.POSITIONS[spec.KEY]),
        euler,
        rows,
    )
    await place_component(
        adapter,
        "dt-cone-gear-tl-vn-arbor-nut",
        list(spec.POSITIONS[spec.NUT]),
        euler,
        rows,
    )
    assert_components_fully_defined(adapter)

    # Title-block identity for the fitting sheet
    # (draw_dt_cone_gear_tl_arbor_assembly.py); material and finish belong
    # to the component drawings.
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
