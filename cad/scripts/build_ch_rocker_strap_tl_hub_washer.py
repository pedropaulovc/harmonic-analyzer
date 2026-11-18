r"""Build MHA-CH-13-TL-03, the rocker strap's hub washer (shop tooling).

The flat washer under the hub screw's head (``ch_rocker_strap_tl_hub_washer_
spec``). Layout (the arbor collar's frame): ``WasherProfile``, the annulus
(OD and bore) on the Front Plane, extruded +Z by the thickness (``Washer``).
Axis +Z, centred; z = 0 the face on the strap. ``Axis1`` is the washer axis
(Top Plane x Right Plane).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_hub_washer.py
"""

from __future__ import annotations

import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimensions, apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from diagnostics.diag_mcmaster_lib import no_sketch_inference
import ch_rocker_strap_tl_hub_washer_spec as spec

PART_NAME = "ch-rocker-strap-tl-hub-washer"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
# The registry row: low-carbon steel round.
MATERIAL = "Plain Carbon Steel"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)
_V_TOL = 0.005


@_telemetry.traced("part.dimension_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist each printed callout below its source dimension
    (build_sm_gooseneck_end_plug's recipe)."""
    # swDimensionTextCalloutBelow = 4.
    for feature, callouts in spec.DIMENSION_CALLOUTS.items():
        resolved = _named_dimensions(adapter, feature, set(callouts))
        for name, text in callouts.items():
            display, _dimension = resolved[name]
            display.SetText(4, text)
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: callout did not persist")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global. The mm
    # suffix is load-bearing: the equation manager reads bare numbers in
    # document units.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # "Thickness" is refused as a global name by the equation manager (farm
    # 20261117T234245842Z: "Failed to add equation"), so the global carries
    # the part's name; the model dimension keeps the plain name.
    for name, value in (
        ("OuterDia", spec.OUTER_DIA),
        ("BoreDia", spec.BORE_DIA),
        ("WasherThickness", spec.THICKNESS),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []
    dims = SketchDims()
    check("create_sketch hub washer", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        define_circle(
            adapter,
            0.0,
            0.0,
            spec.OUTER_DIA / 2.0,
            "hub washer outside",
            dims=dims,
            names=(None, None, "OuterDia"),
            drives=(None, None, '"OuterDia"'),
        )
        define_circle(
            adapter,
            0.0,
            0.0,
            spec.BORE_DIA / 2.0,
            "hub washer bore",
            dims=dims,
            names=(None, None, "BoreDia"),
            drives=(None, None, '"BoreDia"'),
        )
    ensure_fully_defined(adapter, "hub washer sketch")
    check("exit_sketch hub washer", adapter.exit_sketch())
    name_last_feature(adapter, spec.PROFILE)
    drive_jobs += dims.apply(adapter, spec.PROFILE)
    check(
        "extrude hub washer",
        adapter.create_extrusion(ExtrusionParameters(depth=spec.THICKNESS)),
    )
    name_last_feature(adapter, spec.WASHER)
    (thickness,) = name_dimensions(adapter, spec.WASHER, ["Thickness"])
    drive_jobs.append((thickness, '"WasherThickness"'))
    volume_check(adapter, "hub washer", spec.V_WASHER, _V_TOL * spec.V_WASHER)

    # Axis1: the washer axis, model Z, for the fixture assembly's mates.
    name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "hub washer axis")

    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(
        adapter,
        "driven hub washer (equations neutral)",
        spec.V_WASHER,
        _V_TOL * spec.V_WASHER,
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # Every size takes the title block's row for its places: OD and thickness
    # .XX, the bore the DRILLED HOLES row.
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    _author_dimension_callouts(adapter)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": spec.ISOMETRIC_VIEW_NOTE}
    )
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
