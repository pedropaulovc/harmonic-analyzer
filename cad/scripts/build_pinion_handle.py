r"""Build the separate MHA-058 pinion grip crossrod.

The registry slug remains ``pinion-handle`` for the operator-grip component.
The part is now exactly one cold-finished rod body; MHA-102 owns the integral
turned head, neck, arbor shaft, and match-reamed cross-hole.
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from pinion_handle_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    ROD_DIA,
    ROD_DOWN,
    ROD_SPAN,
    SURFACE_FINISHES,
)

PART_NAME = "pinion-handle"
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)
ROD_R = ROD_DIA / 2.0
V_ROD = math.pi * ROD_R**2 * ROD_SPAN


def _require_one_solid_body(adapter, *, label: str) -> None:
    """Refuse to release a crossrod that is empty or accidentally multibody."""
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodSpan", f"{ROD_SPAN}mm")
    await set_global(adapter, "RodDown", f"{ROD_DOWN}mm")

    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        ROD_R,
        "grip crossrod",
        dims=rod,
        names=("RodCx", "RodCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    await ensure_fully_defined(adapter, "grip-crossrod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs = rod.apply(adapter, "RodProfile")

    extrude_at_offset(adapter, ROD_SPAN, -ROD_DOWN)
    name_last_feature(adapter, "Rod")
    drive_jobs.append((name_dimensions(adapter, "Rod", ["RodSpan"])[0], '"RodSpan"'))
    await volume_check(adapter, "grip crossrod", V_ROD, 0.005 * V_ROD)
    _require_one_solid_body(adapter, label="grip crossrod")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven grip crossrod (equations neutral)", V_ROD, 0.005 * V_ROD
    )
    _require_one_solid_body(adapter, label="driven grip crossrod")

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
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
