r"""Build MHA-DT-03-TL-08, the round arbor's backing collar (shop tooling, #2356).

One disc (``dt_cone_gear_tl_round_arbor_collar_spec``): the keyed arbor
collar's member recipe (``build_dt_cone_gear_tl_arbor_collar``) without
members, the annulus on the Front Plane extruded +Z by the collar's length.

Frame: axis +Z; the face on the blank at z = 0, the face under the nut at
z = LENGTH.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_gear_tl_round_arbor_collar.py
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
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from diagnostics.diag_mcmaster_lib import no_sketch_inference
import dt_cone_gear_tl_round_arbor_collar_spec as spec

PART_NAME = "dt-cone-gear-tl-round-arbor-collar"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring
_V_TOL = 0.005


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    for name, value in spec.GLOBALS.items():
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []
    dims = SketchDims()
    label = "round arbor collar"
    check(f"create_sketch {label}", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        define_circle(
            adapter,
            0.0,
            0.0,
            spec.OUTER_DIA / 2.0,
            f"{label} outside",
            dims=dims,
            names=(None, None, "OuterDia"),
            drives=(None, None, '"CollarOD"'),
        )
        define_circle(
            adapter,
            0.0,
            0.0,
            spec.BORE / 2.0,
            f"{label} bore",
            dims=dims,
            names=(None, None, "BoreDia"),
            drives=(None, None, '"CollarBore"'),
        )
    ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, spec.PROFILE)
    drive_jobs += dims.apply(adapter, spec.PROFILE)
    check(
        f"extrude {label}",
        adapter.create_extrusion(ExtrusionParameters(depth=spec.LENGTH)),
    )
    name_last_feature(adapter, spec.COLLAR)
    (length,) = name_dimensions(adapter, spec.COLLAR, ["Length"])
    drive_jobs.append((length, '"CollarLength"'))
    volume_check(adapter, label, spec.V_COLLAR, _V_TOL * spec.V_COLLAR)

    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(
        adapter,
        f"driven {label} (equations neutral)",
        spec.V_COLLAR,
        _V_TOL * spec.V_COLLAR,
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
