r"""Build MHA-DT-03-TL-06, the keyed arbor's key (shop tooling, #2465).

The 1/16 square undersized key-stock section (``dt_cone_gear_tl_arbor_key_spec``)
on the Front Plane, extruded +Z by the cut length. The section's two sizes
(``KeyProfile``) are marked as the stock's reference; the length
(``CutLength`` on ``KeyBody``) is the one made size, at the title block's .XX.

Frame (MHA-DT-VN-71's): origin at the key's shoulder end on its bottom face,
mid-width; height along +X, width centred on the Top Plane, length along +Z.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_arbor_key.py
"""

from __future__ import annotations

import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from diagnostics.diag_mcmaster_lib import no_sketch_inference
import dt_cone_gear_tl_arbor_key_spec as spec

PART_NAME = "dt-cone-gear-tl-arbor-key"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    set_global(adapter, "KeySize", f"{spec.SIZE}mm")
    set_global(adapter, "KeyLength", f"{spec.LENGTH}mm")

    size, half = spec.SIZE, spec.SIZE / 2.0
    dims = SketchDims()
    check("create_sketch key section", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        # Front sketch (x, y) is model (X, Y): height along +X, width about y = 0.
        bottom, side, top, face = add_line_chain(
            adapter, [(0.0, -half), (size, -half), (size, half), (0.0, half)]
        )
        for line, relation in (
            (bottom, "horizontal"),
            (side, "vertical"),
            (top, "horizontal"),
            (face, "vertical"),
        ):
            check(
                f"key section {relation} {line}",
                adapter.add_sketch_constraint(line, None, relation),
            )
        anchor_point_to_origin(
            adapter, f"{bottom}.start", 0.0, -half, "key section corner"
        )
        dims.record("KeyHalfWidth", '"KeySize" / 2')
        dimension_between(
            adapter,
            f"{side}.start",
            f"{side}.end",
            "vertical_distance",
            size,
            "key width",
        )
        dims.record("KeyWidth", '"KeySize"')
        dimension_between(
            adapter,
            f"{bottom}.start",
            f"{bottom}.end",
            "horizontal_distance",
            size,
            "key height",
        )
        dims.record("KeyHeight", '"KeySize"')
        ensure_fully_defined(adapter, "key section")
    check("exit_sketch key section", adapter.exit_sketch())
    name_last_feature(adapter, "KeyProfile")
    drive_jobs = dims.apply(adapter, "KeyProfile")
    check(
        "extrude key",
        adapter.create_extrusion(ExtrusionParameters(depth=spec.LENGTH)),
    )
    name_last_feature(adapter, "KeyBody")
    (length,) = name_dimensions(adapter, "KeyBody", ["CutLength"])
    drive_jobs.append((length, '"KeyLength"'))
    volume = size * size * spec.LENGTH
    volume_check(adapter, "arbor key", volume, 0.005 * volume)
    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(adapter, "driven arbor key", volume, 0.005 * volume)

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Manufacturing Notes": spec.DRAWING_NOTES}
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
