r"""Reproduction script: transgear knob bush (MHA-PD-28; ch. 23; 1 used).

The turned steel bush pressed into the MHA-PD-19 arm plate (owner ruling
2026-11-20 (Pedro), #2425): its hub stands in front of face A as the
shoulder, the MHA-PD-15 thrust ring's seat; its FN2 press runs through the
plate and on to the rear face, the MHA-PD-16 cup's thrust face; its bore is
reamed through after pressing for the MHA-PD-08 knob shaft's journal
(``pd_transgear_knob_bush_geometry``).

Layout: one turned half-section on the Front plane, revolved about local +Y:
hub face, hub Ø, shoulder, press Ø, rear face, then back along the bore, so
both diameters, the bore and both lengths are its driving dimensions and all
print on the drawing's axial section.  The hub face is the Top Plane
(y = 0), the shoulder y = HUB_LENGTH, the rear face y = LENGTH; a native
fillet rounds the shoulder root.  ``Axis1`` is the bush axis (Front Plane ∩
Right Plane).  The paper-drive assembly mates ``Axis1`` to the knob axis K
and the shoulder to the plate's face A.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_bush.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _document_units import apply_package_model_units
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from pd_transgear_knob_bush_geometry import (
    BORE_DIA,
    HUB_DIA,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    LENGTH,
    LENGTH_BAND,
    PRESS_DIA,
    PRESS_DIA_BAND,
    SHOULDER_ROOT_R_MAX_MM,
)
from pd_transgear_knob_bush_spec import (
    BORE_BAND,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SHOULDER_FILLET,
    SHOULDER_ROOT_SUFFIX,
    SHOULDER_ROOT_TOL_TYPE,
    SURFACE_FINISHES,
    UNIT,
)

PART_NAME = "pd-transgear-knob-bush"
MATERIAL = "Plain Carbon Steel"  # AISI 1018; see _appearance.apply_material

HUB_R = HUB_DIA / 2.0
PRESS_R = PRESS_DIA / 2.0
BORE_R = BORE_DIA / 2.0
V_BUSH = math.pi * (
    HUB_R**2 * HUB_LENGTH + PRESS_R**2 * (LENGTH - HUB_LENGTH) - BORE_R**2 * LENGTH
)
# The root fillet adds (1 - pi/4) r^2 of section round the press: well inside
# the volume gate, so the gate still proves the profile.
V_ROOT = (1.0 - math.pi / 4.0) * SHOULDER_ROOT_R_MAX_MM**2 * 2.0 * math.pi * PRESS_R


@_telemetry.traced("dim.pd_transgear_knob_bush_callouts")
def _author_dimension_callouts(adapter) -> None:
    """Persist the sheet's callout rows on the source dimensions.

    The drawing imports them and only reads them back: text set from the
    drawing writes through to the built part (fleet issue #1942).
    """
    for feature, callouts in DIMENSION_CALLOUTS.items():
        for name, text in callouts.items():
            display, _dimension = _named_dimension(adapter, feature, name)
            # swDimensionTextCalloutBelow; the native value stays visible.
            display.SetText(4, text)
            if str(display.GetText(4) or "").replace("\r\n", "\n") != text:
                raise RuntimeError(f"{name}@{feature}: callout did not persist")


@_telemetry.traced("part.knob_bush.shoulder_root_max")
def _shoulder_root_max_limit(adapter) -> None:
    """ShoulderR as the single limit "R.005 MAX": no native tolerance, " MAX"
    its suffix (build_dt_cone_gear_tl_keyed_arbor._shoulder_root_max_limit),
    since swTolMAX prints a lowercase "max."."""
    display, dimension = _named_dimension(adapter, SHOULDER_FILLET, "ShoulderR")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = SHOULDER_ROOT_TOL_TYPE
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(2, SHOULDER_ROOT_SUFFIX)  # swDimensionTextSuffix
    if (
        int(tolerance.Type) != SHOULDER_ROOT_TOL_TYPE
        or str(display.GetText(2) or "") != SHOULDER_ROOT_SUFFIX
    ):
        raise RuntimeError("ShoulderR: the MAX single limit did not persist")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("HubDia", HUB_DIA),
        ("HubLength", HUB_LENGTH),
        ("PressDia", PRESS_DIA),
        ("BushLength", LENGTH),
        ("BoreDia", BORE_DIA),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Turned half-section about local +Y: hub face, hub Ø, shoulder, press Ø,
    # rear face, then back along the bore, so every diameter is a profile
    # dimension that prints on the axial section (rule 11).
    profile = SketchDims()
    check("create_sketch bush profile", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("bush axis", adapter.add_centerline(0.0, 0.0, 0.0, LENGTH))
    points = [
        (BORE_R, 0.0),
        (HUB_R, 0.0),
        (HUB_R, HUB_LENGTH),
        (PRESS_R, HUB_LENGTH),
        (PRESS_R, LENGTH),
        (BORE_R, LENGTH),
    ]
    lines = add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        p0 = points[index]
        p1 = points[(index + 1) % len(points)]
        relation = "horizontal" if p0[1] == p1[1] else "vertical"
        check(
            f"bush profile {relation} {line}",
            adapter.add_sketch_constraint(line, None, relation),
        )
    check("bush axis vertical", adapter.add_sketch_constraint(axis, None, "vertical"))
    anchor_point_to_origin(adapter, f"{axis}.start", 0.0, 0.0, "bush axis origin")
    check(
        "bush hub face on the Top plane",
        adapter.add_sketch_constraint(
            f"{lines[0]}.start", "origin", "horizontal_points"
        ),
    )
    add_diametric_linear_dimension(
        adapter, axis, lines[1], (HUB_R + 4.0, HUB_LENGTH / 2.0), "HubDia"
    )
    profile.record("HubDia", '"HubDia"')
    check(
        "bush hub length",
        adapter.add_sketch_dimension(lines[1], None, "linear", HUB_LENGTH),
    )
    profile.record("HubLength", '"HubLength"')
    add_diametric_linear_dimension(
        adapter,
        axis,
        lines[3],
        (PRESS_R + 4.0, (HUB_LENGTH + LENGTH) / 2.0),
        "PressDia",
    )
    profile.record("PressDia", '"PressDia"')
    # The overall length between the faces' outer corners, so its extension
    # lines rise from the part's outline, not across the cut bore.
    dimension_between(
        adapter,
        f"{lines[0]}.end",
        f"{lines[4]}.start",
        "vertical_distance",
        LENGTH,
        "bush length",
    )
    profile.record("BushLength", '"BushLength"')
    check(
        "bush axis length",
        adapter.add_sketch_dimension(axis, None, "linear", LENGTH),
    )
    profile.record("AxisLength", '"BushLength"')
    add_diametric_linear_dimension(
        adapter, axis, lines[5], (BORE_R - 1.5, LENGTH / 2.0), "BoreDia"
    )
    profile.record("BoreDia", '"BoreDia"')
    ensure_fully_defined(adapter, "bush profile")
    check("exit_sketch bush profile", adapter.exit_sketch())
    name_last_feature(adapter, "BushProfile")
    drive_jobs += profile.apply(adapter, "BushProfile")
    check("revolve bush", adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "BushBody")
    volume_check(adapter, "turned bush", V_BUSH, 0.005 * V_BUSH)
    bbox_extent_check(adapter, "bush length", "y", LENGTH)
    bbox_extent_check(adapter, "bush hub O.D.", "x", HUB_DIA)

    # The shoulder root: the full circle where the press meets the shoulder,
    # picked at -X, off the revolve's seam in the +X sketch plane.
    check(
        "fillet shoulder root",
        adapter.add_fillet(
            SHOULDER_ROOT_R_MAX_MM,
            [[-PRESS_R, HUB_LENGTH, 0.0]],
            propagate=False,
        ),
    )
    name_last_feature(adapter, SHOULDER_FILLET)
    name_dimensions(adapter, SHOULDER_FILLET, ["ShoulderR"])
    volume_check(adapter, "shoulder root", V_BUSH + V_ROOT, 0.005 * V_BUSH)

    # The mate axis: the first reference axis, so it is Axis1.
    bush_axis = name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "bush axis"
    )
    if bush_axis != "Axis1":
        raise RuntimeError(f"bush axis came back {bush_axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven bush (equations neutral)", V_BUSH + V_ROOT, 0.005 * V_BUSH
    )

    apply_material(adapter, MATERIAL)
    report_mass_properties(adapter)
    # The H7 running bore and the FN2 press carry their fit bands; the hub
    # station and the overall length their stack bands.  The hub Ø is
    # governed by its places (the spec's DRAWING_PRECISION): no model band.
    set_dimension_bilateral_tolerance(
        adapter,
        "BushProfile",
        "BoreDia",
        *deviations(BORE_BAND),
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "BushProfile",
        "PressDia",
        *deviations(PRESS_DIA_BAND),
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter, "BushProfile", "HubLength", HUB_LENGTH_BAND, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "BushProfile", "BushLength", LENGTH_BAND, display_unit=UNIT
    )
    _shoulder_root_max_limit(adapter)
    _author_dimension_callouts(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Datum A (shoulder), the bore's frame to it, and the bore's and both
    # thrust faces' finishes, resolved by outward normal and offset.
    author_part_pmi(
        adapter,
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        surface_finishes=SURFACE_FINISHES,
    )
    apply_drawing_properties(adapter, PART_NAME)
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
