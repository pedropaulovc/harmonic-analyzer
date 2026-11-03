r"""Build one purchased ANSI #25 chain native with its two physical members.

InnerLink contains two inner plates and two bored bushings; OuterLink contains
two outer plates and two solid pins. Each member preserves the inherited
four-body geometry and local frame. Common hidden Axis1/Axis2 references stay
at x=0 and x=LINK_PITCH for the connected-linkage chain pattern.

The installed chain has 34 inner and 33 outer members, closed by the separate
connecting link. Configuration quantities describe those physical occurrences;
the inherited cut-to-length notes retain the chain's order-by-the-foot logic.
There is no Default alias or Simplified configuration.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sh_vn_chain_link.py
"""

from __future__ import annotations

import sys
from typing import Any

import _chain_link
import _config
from _chain import LINK_PITCH, PLATE_HALF_H, PLATE_THICK
from _appearance import BAR_STEEL, apply_color, apply_material
from _check import check
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _drawing_marks import apply_drawing_properties
from _part_checks import bbox_extent_check, report_mass_properties
from _part_properties import part_drawing_unit
from _purchased_part_variants import (
    activate_member,
    apply_member_properties,
    assert_member_properties,
    assert_member_suppression,
    create_member_configurations,
    require_member_bodies,
    require_member_colour,
    require_member_configurations,
    save_member_part,
    select_member_features,
    set_member_suppression,
)
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _visibility import assert_reference_geometry_hidden
from _supplier_chain_stock import add_chain_stock_references
from sh_vn_chain_link_spec import (
    CONFIGURATIONS,
    INNER_LINK,
    INNER_LINK_BOM_DESCRIPTION,
    INNER_LINK_CONFIGURATION,
    OUTER_LINK,
    OUTER_LINK_BOM_DESCRIPTION,
    OUTER_LINK_CONFIGURATION,
)

PART_NAME = "sh-vn-chain-link"
MATERIAL = "Plain Carbon Steel"

_MEMBER_DELTAS = {
    INNER_LINK_CONFIGURATION: INNER_LINK,
    OUTER_LINK_CONFIGURATION: OUTER_LINK,
}
_MEMBER_DESCRIPTIONS = {
    INNER_LINK_CONFIGURATION: INNER_LINK_BOM_DESCRIPTION,
    OUTER_LINK_CONFIGURATION: OUTER_LINK_BOM_DESCRIPTION,
}
_MEMBER_REFERENCES = ("Axis1", "Axis2")


async def build(adapter: Any) -> dict[str, str]:
    require_member_configurations(PART_NAME, CONFIGURATIONS)
    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # Author before cloning configurations so every member inherits the same
    # station plane and the same two hidden, unsuppressed path-link axes.
    await _chain_link.author_link_references(adapter)
    await create_member_configurations(adapter, PART_NAME, CONFIGURATIONS)

    member_features: dict[str, tuple[str, ...]] = {}
    for configuration in CONFIGURATIONS:
        await activate_member(adapter, configuration)
        # New members must not merge with, or acquire dependencies on, solids
        # belonging to a previously authored member in the same document.
        for features in reversed(tuple(member_features.values())):
            set_member_suppression(adapter, features, suppressed=True)
        member_features[configuration] = await _chain_link.author_link_geometry(
            adapter, **_MEMBER_DELTAS[configuration]
        )

    stock = _chain_link.stock_properties(PART_NAME)
    row = _config.parts(PART_NAME)
    default_configuration = str(row["default_configuration"])
    note_properties = {
        f"{configuration} Manufacturing Notes": _chain_link.DRAWING_NOTES[configuration]
        for configuration in CONFIGURATIONS
    }
    apply_custom_properties(adapter, {"Number": str(row["number"]), **stock})
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": _chain_link.DRAWING_NOTES[default_configuration],
            **note_properties,
        },
    )
    member_properties = {
        configuration: {
            **stock,
            "Manufacturing Notes": _chain_link.DRAWING_NOTES[configuration],
        }
        for configuration in CONFIGURATIONS
    }

    async def _readback(current_adapter: Any, configuration: str) -> None:
        """Check native member state without repairing or saving the document."""
        assert_member_suppression(current_adapter, configuration, member_features)
        require_member_bodies(current_adapter, configuration, 4, _MEMBER_REFERENCES)
        require_member_colour(current_adapter, configuration, BAR_STEEL)
        delta = _MEMBER_DELTAS[configuration]
        _chain_link._gate_volume(
            await _chain_link._volume(current_adapter),
            delta["plate_hole_r"],
            delta["body_outer_r"],
            delta["body_bore_r"],
            delta["body_half_len"],
        )
        await bbox_extent_check(
            current_adapter,
            f"{configuration} pitch envelope",
            "x",
            LINK_PITCH + 2.0 * PLATE_HALF_H,
        )
        await bbox_extent_check(
            current_adapter,
            f"{configuration} axial envelope",
            "z",
            2.0 * max(delta["plate_z"] + PLATE_THICK / 2.0, delta["body_half_len"]),
        )
        assert_member_properties(
            current_adapter,
            PART_NAME,
            configuration,
            _MEMBER_DESCRIPTIONS[configuration],
            member_properties[configuration],
        )
        require_saved_drawing_properties(
            current_adapter, (*_chain_link.DRAWING_PROPERTIES, *note_properties)
        )
        assert_reference_geometry_hidden(
            current_adapter, f"{PART_NAME}--{configuration}"
        )

    # Features added after a configuration was created may inherit a native
    # suppression state. Write and read the complete matrix for every member.
    for configuration in CONFIGURATIONS:
        await select_member_features(adapter, configuration, member_features)
        await apply_material(adapter, MATERIAL)
        await apply_color(adapter, BAR_STEEL)
        apply_member_properties(
            adapter,
            PART_NAME,
            configuration,
            _MEMBER_DESCRIPTIONS[configuration],
            member_properties[configuration],
        )
        await report_mass_properties(adapter)

    # Reference-only construction state; existing member solids and suppression
    # matrices are independently compared before returning to the active member.
    await add_chain_stock_references(adapter)

    return await save_member_part(
        adapter,
        PART_NAME,
        CONFIGURATIONS,
        material=MATERIAL,
        readback=_readback,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
