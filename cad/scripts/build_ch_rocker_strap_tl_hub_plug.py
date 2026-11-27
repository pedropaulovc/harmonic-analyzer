r"""Build MHA-CH-13-TL-02, the rocker strap's hub plug (shop tooling).

The stepped plug of the rocker-strap sub-plate fixture
(``ch_rocker_strap_tl_hub_plug_spec``): a body that drops into
MHA-CH-13-TL-01's hub counterbore, a pilot that clears the strap blank's
reamed hub hole, a drilled bore for the hub screw and a 45 deg lead-in on the
pilot.

Layout (the arbor collar's frame): axis +Z, centred. ``BodyProfile`` is the
body's annulus (Ø and bore) on the Front Plane, extruded +Z by the body
length (``Body``); ``PilotProfile`` is the pilot's annulus on the same plane,
extruded +Z by the overall length (``Pilot``), merging with the body, so the
overall length is one native dimension. ``PilotChamfer`` breaks the pilot's
top outside edge. ``Axis1`` is the plug axis (Top Plane x Right Plane).

The PART owns the print: every dimension's places (each size at the title
block's row) and each callout below its value; the drawing only places and
reads them back.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_strap_tl_hub_plug.py
"""

from __future__ import annotations

import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
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
import ch_rocker_strap_tl_hub_plug_spec as spec

PART_NAME = "ch-rocker-strap-tl-hub-plug"
if PART_NAME != spec.PART_NAME:
    raise AssertionError("the builder's PART_NAME and its spec disagree")
# The registry row: 6061 aluminum round.
MATERIAL = "6061 Alloy"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)
_V_TOL = 0.005


def _annulus(
    adapter,
    drive_jobs: list[tuple[str, str]],
    *,
    label: str,
    sketch: str,
    feature: str,
    outer: tuple[float, str, str],
    bore_name: str,
    depth: float,
    depth_name: str,
    depth_drive: str,
) -> None:
    """One annulus on the Front Plane, extruded +Z by ``depth``."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dia, dia_name, dia_drive = outer
    dims = SketchDims()
    check(f"create_sketch {label}", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        define_circle(
            adapter,
            0.0,
            0.0,
            dia / 2.0,
            f"{label} outside",
            dims=dims,
            names=(None, None, dia_name),
            drives=(None, None, dia_drive),
        )
        define_circle(
            adapter,
            0.0,
            0.0,
            spec.BORE_DIA / 2.0,
            f"{label} bore",
            dims=dims,
            names=(None, None, bore_name),
            drives=(None, None, '"PlugBore"'),
        )
    ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    drive_jobs += dims.apply(adapter, sketch)
    check(
        f"extrude {label}", adapter.create_extrusion(ExtrusionParameters(depth=depth))
    )
    name_last_feature(adapter, feature)
    (length,) = name_dimensions(adapter, feature, [depth_name])
    drive_jobs.append((length, depth_drive))


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
    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global. The mm
    # suffix is load-bearing: the equation manager reads bare numbers in
    # document units.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    for name, value in (
        ("BodyDia", spec.BODY_DIA),
        ("PilotDia", spec.PILOT_DIA),
        ("PlugBore", spec.BORE_DIA),
        ("BodyLength", spec.BODY_LENGTH),
        ("OverallLength", spec.OVERALL_LENGTH),
        ("ChamferSize", spec.CHAMFER),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []
    _annulus(
        adapter,
        drive_jobs,
        label="hub plug body",
        sketch=spec.BODY_PROFILE,
        feature=spec.BODY,
        outer=(spec.BODY_DIA, "BodyDia", '"BodyDia"'),
        bore_name="BoreDia",
        depth=spec.BODY_LENGTH,
        depth_name="BodyLength",
        depth_drive='"BodyLength"',
    )
    volume_check(adapter, "hub plug body", spec.V_BODY, _V_TOL * spec.V_BODY)
    # The pilot from the same plane through the body to the top: merged, the
    # solid is the body plus the pilot above it.
    _annulus(
        adapter,
        drive_jobs,
        label="hub plug pilot",
        sketch=spec.PILOT_PROFILE,
        feature=spec.PILOT,
        outer=(spec.PILOT_DIA, "PilotDia", '"PilotDia"'),
        bore_name="PilotBore",
        depth=spec.OVERALL_LENGTH,
        depth_name="OverallLength",
        depth_drive='"OverallLength"',
    )
    v_stepped = spec.V_BODY + spec.V_PILOT
    volume_check(adapter, "stepped hub plug", v_stepped, _V_TOL * v_stepped)

    # The pilot's lead-in: one pick on its top outside edge.
    check(
        "chamfer the pilot's top edge",
        adapter.add_chamfer(
            spec.CHAMFER, [[spec.PILOT_DIA / 2.0, 0.0, spec.OVERALL_LENGTH]]
        ),
    )
    name_last_feature(adapter, spec.PILOT_CHAMFER)
    (chamfer,) = name_dimensions(adapter, spec.PILOT_CHAMFER, ["ChamferSize"])
    drive_jobs.append((chamfer, '"ChamferSize"'))
    volume_check(adapter, "chamfered hub plug", spec.V_PLUG, _V_TOL * spec.V_PLUG)

    # Axis1: the plug axis, model Z, for the fixture assembly's mates.
    name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "hub plug axis")

    force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        drive_dimension(adapter, dimension_name, expression)
    force_rebuild(adapter)
    volume_check(
        adapter,
        "driven hub plug (equations neutral)",
        spec.V_PLUG,
        _V_TOL * spec.V_PLUG,
    )
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"hub plug: expected one solid body, found {len(bodies)}")

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # Every size takes the title block's row for its places.
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
