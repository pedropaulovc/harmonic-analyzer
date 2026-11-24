r"""Reproduction script: transgear knob bush (MHA-PD-28; ch. 23; 1 used).

The turned steel bush pressed into the MHA-PD-19 arm plate (owner ruling
2026-11-20 (Pedro), #2425): its hub stands in front of face A as the
shoulder, the MHA-PD-15 thrust ring's seat; its press, turned to the
plate's measured hole, runs through the
plate and on to the rear face, the MHA-PD-16 cup's thrust face; its bore is
reamed through after pressing for the MHA-PD-08 knob shaft's journal
(``pd_transgear_knob_bush_geometry``).

Layout: one turned half-section on the Front plane, revolved about local +Y:
rear face, the axis, hub face, hub Ø, shoulder, the shoulder root's
tangent arc and the press Ø, so both diameters, both lengths and the root's
radius are its driving dimensions and all print on the drawing's axial
section (a fillet feature's radius does not import there: farm r3).  The
reamed bore is a Top-plane circle cut through, so its Ø prints on the face
view, where the bore is a circle (the spec's DRAWING_DIMENSIONS).  The hub
face is the Top Plane (y = 0), the shoulder y = HUB_LENGTH, the rear face
y = LENGTH.  ``Axis1`` is the bush axis (Front Plane ∩ Right Plane).  The
paper-drive assembly mates ``Axis1`` to the knob axis K and the shoulder to
the plate's face A.

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
from _dimensions import drive_dimension, set_global
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
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _document_units import apply_package_model_units
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
    SHOULDER_ROOT_R_MAX_MM,
)
from pd_transgear_knob_bush_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    PRESS_DIA_TEXT_PREFIX,
    PRESS_DIA_TEXT_SUFFIX,
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
V_TURNED = math.pi * (HUB_R**2 * HUB_LENGTH + PRESS_R**2 * (LENGTH - HUB_LENGTH))
V_BUSH = V_TURNED - math.pi * BORE_R**2 * LENGTH
# The bore's mid-plane cut from the hub face (the Top plane): half of it
# reaches past the rear face, the other half cuts air.
BORE_CUT_DEPTH = 2.0 * (LENGTH + 1.0)
# The root arc fills the square outside a quarter disk beside the press:
# section r^2(1 - pi/4), its first moment about the press line r^3(5/6 - pi/4)
# (Pappus, as build_dt_crank_handle_butt_cup's pocket corner).
V_ROOT = (
    2.0
    * math.pi
    * (
        PRESS_R * SHOULDER_ROOT_R_MAX_MM**2 * (1.0 - math.pi / 4.0)
        + SHOULDER_ROOT_R_MAX_MM**3 * (5.0 / 6.0 - math.pi / 4.0)
    )
)


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
    display, dimension = _named_dimension(adapter, "BushProfile", "ShoulderR")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = SHOULDER_ROOT_TOL_TYPE
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(2, SHOULDER_ROOT_SUFFIX)  # swDimensionTextSuffix
    if (
        int(tolerance.Type) != SHOULDER_ROOT_TOL_TYPE
        or str(display.GetText(2) or "") != SHOULDER_ROOT_SUFFIX
    ):
        raise RuntimeError("ShoulderR: the MAX single limit did not persist")


@_telemetry.traced("part.knob_bush.press_dia_reference")
def _press_dia_reference(adapter) -> None:
    """PressDia as the reference "(Ø.4385)": the step is turned to the
    plate's measured hole, so it carries no native tolerance and prints in
    parentheses (build_pd_transgear_pin's press land)."""
    display, dimension = _named_dimension(adapter, "BushProfile", "PressDia")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 0  # swTolType_e.swTolNONE
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(1, PRESS_DIA_TEXT_PREFIX)  # swDimensionTextPrefix
    display.SetText(2, PRESS_DIA_TEXT_SUFFIX)  # swDimensionTextSuffix
    if (
        int(tolerance.Type) != 0
        or str(display.GetText(1) or "") != PRESS_DIA_TEXT_PREFIX
        or str(display.GetText(2) or "") != PRESS_DIA_TEXT_SUFFIX
    ):
        raise RuntimeError("PressDia: the reference form did not persist")


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

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
        ("ShoulderR", SHOULDER_ROOT_R_MAX_MM),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Turned half-section about local +Y: rear face, the axis, hub face, hub
    # Ø, shoulder, then the root's tangent arc (concave, centred off the
    # part, beyond the shoulder and the press) and the press Ø back to the
    # rear face, so every outside diameter and the root radius are profile
    # dimensions that print on the axial section (rule 11).
    root_r = SHOULDER_ROOT_R_MAX_MM
    root_center = (PRESS_R + root_r, HUB_LENGTH + root_r)
    root_on_press = (PRESS_R, HUB_LENGTH + root_r)
    root_on_shoulder = (PRESS_R + root_r, HUB_LENGTH)
    profile = SketchDims()
    check("create_sketch bush profile", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    axis = check("bush axis", adapter.add_centerline(0.0, 0.0, 0.0, LENGTH))
    points = [
        (PRESS_R, LENGTH),
        (0.0, LENGTH),
        (0.0, 0.0),
        (HUB_R, 0.0),
        (HUB_R, HUB_LENGTH),
        root_on_shoulder,
    ]
    lines = add_line_chain(adapter, points, close=False)
    # add_arc is CCW: from the press tangent (180 deg about the centre) to
    # the shoulder tangent (270 deg) is the 90-degree arc, opposite the
    # chain's traversal (build_dt_crank_handle_butt_cup's floor round).
    root_arc = check(
        "shoulder root arc",
        adapter.add_arc(*root_center, *root_on_press, *root_on_shoulder),
    )
    (press,) = add_line_chain(adapter, [root_on_press, points[0]], close=False)
    set_sketch_direct_db(adapter, False)
    rear_face, axis_edge, hub_face, hub_od, shoulder = lines
    for line, (u0, v0), (u1, v1) in (
        *zip(lines, points, points[1:], strict=False),
        (press, root_on_press, points[0]),
    ):
        relation = "horizontal" if v0 == v1 else "vertical"
        check(
            f"bush profile {relation} {line}",
            adapter.add_sketch_constraint(line, None, relation),
        )
    check("bush axis vertical", adapter.add_sketch_constraint(axis, None, "vertical"))
    anchor_point_to_origin(adapter, f"{axis}.start", 0.0, 0.0, "bush axis origin")
    # The profile's axis edge closes it on the axis (the MHA-PD-08 journal's
    # profile); its hub-face end is the origin.
    anchor_point_to_origin(
        adapter, f"{axis_edge}.end", 0.0, 0.0, "bush profile axis edge origin"
    )
    add_diametric_linear_dimension(
        adapter, axis, hub_od, (HUB_R + 4.0, HUB_LENGTH / 2.0), "HubDia"
    )
    profile.record("HubDia", '"HubDia"')
    check(
        "bush hub length",
        adapter.add_sketch_dimension(hub_od, None, "linear", HUB_LENGTH),
    )
    profile.record("HubLength", '"HubLength"')
    add_diametric_linear_dimension(
        adapter,
        axis,
        press,
        (PRESS_R + 4.0, (HUB_LENGTH + LENGTH) / 2.0),
        "PressDia",
    )
    profile.record("PressDia", '"PressDia"')
    # The overall length between the faces' outer corners, so its extension
    # lines rise from the part's outline, not across the cut bore.
    dimension_between(
        adapter,
        f"{hub_face}.end",
        f"{rear_face}.start",
        "vertical_distance",
        LENGTH,
        "bush length",
    )
    profile.record("BushLength", '"BushLength"')
    # No length on the centreline: its ends are the axis edge's, so a second
    # length there is redundant, comes back driven and cannot take an
    # equation (farm r7: "a driven or reference dimension is not selectable
    # as the dependent variable").  The MHA-PD-08 journal's profile likewise.
    check(
        "shoulder root radius",
        adapter.add_sketch_dimension(root_arc, None, "radial", root_r),
    )
    profile.record("ShoulderR", '"ShoulderR"')
    for first, second, label in (
        (shoulder, root_arc, "shoulder"),
        (root_arc, press, "press"),
    ):
        check(
            f"shoulder root tangent to the {label}",
            adapter.add_sketch_constraint(first, second, "tangent"),
        )
    ensure_fully_defined(adapter, "bush profile")
    check("exit_sketch bush profile", adapter.exit_sketch())
    name_last_feature(adapter, "BushProfile")
    drive_jobs += profile.apply(adapter, "BushProfile")
    check("revolve bush", adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "BushBody")
    volume_check(adapter, "turned bush", V_TURNED + V_ROOT, 0.005 * V_TURNED)
    bbox_extent_check(adapter, "bush length", "y", LENGTH)
    bbox_extent_check(adapter, "bush hub O.D.", "x", HUB_DIA)

    # The reamed bore: one on-axis circle on the hub face, cut through both
    # ways, so its diameter is a circle's and prints where the bore is one.
    bore = SketchDims()
    check("create_sketch bush bore", adapter.create_sketch("Top"))
    define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "bush bore",
        dims=bore,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    ensure_fully_defined(adapter, "bush bore sketch")
    check("exit_sketch bush bore", adapter.exit_sketch())
    name_last_feature(adapter, "BoreSketch")
    drive_jobs += bore.apply(adapter, "BoreSketch")
    check(
        "cut bush bore",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=BORE_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BoreCut")
    volume_check(adapter, "bored bush", V_BUSH + V_ROOT, 0.005 * V_BUSH)

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
    # The hub station and the overall length carry their stack bands.  The
    # press Ø is made to the plate's measured hole: a reference, no model
    # band.  The reamed running bore prints the reamer's size and no band
    # (rule 4); the hub Ø is governed by its places (the spec's
    # DRAWING_PRECISION): no model band.
    _press_dia_reference(adapter)
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
