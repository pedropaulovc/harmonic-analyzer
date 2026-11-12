r"""Reproduction script: dt-cone-tip-gear-tl-cutter.SLDASM (MHA-DT-37-TL-00).

The cone tip gear's fly cutter as set up, a shop fixture (issue #2358): the
bar dt-cone-tip-gear-tl-cutter-bar (MHA-DT-37-TL-02), the DT6-FORM1 bit
dt-cone-tip-gear-tl-form-cutter (MHA-DT-37-TL-01) in its cross hole at the
nominal stick-out, face leading, and the bought set screw
sh-vn-arbor-set-screw (MHA-SH-VN-54) seated on the bit, each fixed (0 DOF) at
``dt_cone_tip_gear_tl_cutter_spec``'s pose. The ``_tl_`` stem keeps the
fixture out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_gear_tl_cutter_assembly.py
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
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY
from _dt_cone_tip_gear_tl_cutter_interference import ALLOWED_PAIRS
from _session import run_build
from _transforms import euler_from_rows
from dt_cone_tip_gear_tl_cutter_spec import (
    BAR_POSITION,
    BAR_ROWS,
    BIT_POSITION,
    BIT_ROWS,
    CONTRACT,
    SET_SCREW_POSITION,
    SET_SCREW_ROWS,
)

ASM_NAME = "dt-cone-tip-gear-tl-cutter"


def _rows(frozen: tuple[tuple[float, ...], ...]) -> list[list[float]]:
    return [list(row) for row in frozen]


async def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", await adapter.create_assembly())
    apply_package_model_units(adapter, CONTRACT.drawing_unit, label=ASM_NAME)

    # The bar keeps its part frame; the bit lies through its cross hole, face
    # leading; the screw stands on the axis below the bit, cup on its shank.
    rows = _rows(BAR_ROWS)
    await place_component(
        adapter,
        "dt-cone-tip-gear-tl-cutter-bar",
        list(BAR_POSITION),
        euler_from_rows(rows),
        rows,
    )
    rows = _rows(BIT_ROWS)
    await place_component(
        adapter,
        "dt-cone-tip-gear-tl-form-cutter",
        list(BIT_POSITION),
        euler_from_rows(rows),
        rows,
    )
    rows = _rows(SET_SCREW_ROWS)
    await place_component(
        adapter,
        "sh-vn-arbor-set-screw",
        list(SET_SCREW_POSITION),
        euler_from_rows(rows),
        rows,
    )
    assert_components_fully_defined(adapter)
    # Only the set screw's thread envelope in the bar's tap may overlap; the
    # bit's slip fit and the screw's cup on the bit are clearance and contact.
    check_no_interference(adapter, allowed_pairs=ALLOWED_PAIRS)

    # Title-block identity for the fitter sheet
    # (draw_dt_cone_tip_gear_tl_cutter_assembly.py); material and finish
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
