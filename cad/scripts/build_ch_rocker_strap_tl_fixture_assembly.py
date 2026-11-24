r"""Reproduction script: ch-rocker-strap-tl-fixture.SLDASM (MHA-CH-13-TL-00).

The rocker-strap sub-plate fixture, a shop fixture (owner ask 2026-11-17;
``ch_rocker_strap_tl_fixture_spec``): the sub-plate, the hub plug, the hub
washer, four Pitbull edge clamps and the hub screw, each fixed at its kit
pose in the plate's frame, the strap programs' G54 (0 DOF). The ``_tl_``
stem keeps the kit out of every machine assembly and BOM
(``_buildgraph.is_shop_fixture``). The fitting sheet prints no reference
dimension: every place is a feature of item 1, dimensioned on its sheet
(rule 24).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_fixture_assembly.py
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
from _ch_rocker_strap_tl_fixture_interference import ALLOWED_PAIRS
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import DRAWN_BY
from _session import run_build
from _transforms import euler_from_rows
import ch_rocker_strap_tl_fixture_spec as spec

ASM_NAME = "ch-rocker-strap-tl-fixture"
if ASM_NAME != spec.ASM_NAME:
    raise AssertionError("the builder's contract and the kit spec disagree")


def build(adapter) -> dict[str, str]:
    # Free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    check("create_assembly", adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )
    # Inserted in BOM order (spec.BOM_ORDER): the fitting steps and the screw
    # schedule cite the BOM's item numbers. Literal stems, so the build graph
    # reads the sources.
    rows = [list(row) for row in spec.IDENTITY_ROWS]
    euler = euler_from_rows(rows)
    place_component(
        adapter, "ch-rocker-strap-tl-sub-plate", [0.0, 0.0, 0.0], euler, rows
    )
    place_component(
        adapter, "ch-rocker-strap-tl-hub-plug", list(spec.PLUG_POSITION), euler, rows
    )
    place_component(
        adapter,
        "ch-rocker-strap-tl-vn-hub-washer",
        list(spec.WASHER_POSITION),
        euler,
        rows,
    )
    for position in spec.CLAMP_POSITIONS:
        place_component(
            adapter, "ch-rocker-strap-tl-vn-edge-clamp", list(position), euler, rows
        )
    place_component(
        adapter,
        "ch-rocker-strap-tl-vn-hub-screw",
        list(spec.SCREW_POSITION),
        euler,
        rows,
    )
    assert_components_fully_defined(adapter)
    # Only the clamp and hub screws' thread envelopes in their tapped holes
    # may overlap the plate; every other pair is clearance or contact.
    check_no_interference(adapter, allowed_pairs=ALLOWED_PAIRS)

    # Title-block identity for the fitting sheet
    # (draw_ch_rocker_strap_tl_fixture_assembly.py); material and finish
    # belong to the component drawings.
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
    return save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
