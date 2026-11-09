r"""Reproduction script: dt-cone-gear-tl-indexing.SLDASM (MHA-DT-03-TL-00).

The cone gears' shop kit, a shop fixture: the custom index plate
dt-cone-gear-tl-index-plate (MHA-DT-03-TL-01) that lets the PM BS-0 dividing
head (40:1 worm) index the 96, 102 and 114 tooth cone gears, and the tip
gears' phasing comb dt-cone-gear-tl-phasing-comb (MHA-DT-03-TL-02) that
MHA-DT-00 step 1 engages while the tip gears' bonds grab. The head and the
plate screws it already carries are the owner's equipment and are not
modelled, so the kit holds the two parts, each fixed (0 DOF). The ``_tl_``
stem keeps the kit out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``); it exists so its parts belong to a
registered assembly (test_part_coverage.py) and carry a fitter sheet.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_indexing_assembly.py
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
from _transforms import IDENTITY, euler_from_rows

ASM_NAME = "dt-cone-gear-tl-indexing"
# The comb's model origin (mm) in the kit frame: under the plate's rim.
COMB_POSITION_MM = (-11.0, -62.0, 0.0)


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )

    # The plate keeps its part frame: the countersunk face, which seats the
    # head's flat-head plate screws, faces +Z (the sheet's front view).
    rows = [list(row) for row in IDENTITY]
    await place_component(
        adapter,
        "dt-cone-gear-tl-index-plate",
        [0.0, 0.0, 0.0],
        euler_from_rows(rows),
        rows,
    )
    # The comb lies in the plate's front plane, below the plate (its model
    # frame: x along its length, y up, its thickness about z0), centred
    # under the bore, so the front view balloons it beside the plate.
    await place_component(
        adapter,
        "dt-cone-gear-tl-phasing-comb",
        list(COMB_POSITION_MM),
        euler_from_rows(rows),
        rows,
    )
    assert_components_fully_defined(adapter)

    # Title-block identity for the fitter sheet
    # (draw_dt_cone_gear_tl_indexing_assembly.py); material and finish belong
    # to the plate's own drawing.
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
