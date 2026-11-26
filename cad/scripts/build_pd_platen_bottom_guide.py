r"""Reproduction script: the platen's bottom guide rail, MHA-PD-27.

Owner rulings 2026-11-13 (#2410): MHA-PD-11's .40-deep black steel section,
grown downward until its underside seats the MHA-PD-26 feed rack, which is
screwed to it with four stock #0-80 fillisters. It carries two lock plates
(build_pd_guide_lock.py) like MHA-PD-11 and is screwed to the platen by its
lower row of five platen screws.

Layout: length along +X, height along +Y from the underside, depth extruded
-Z so native Front looks directly at the platen-mating face (as MHA-PD-11).
Four #4-40 lock taps THROUGH from the rear face (printed), five #4-40
platen-screw taps THROUGH from the front face (transferred from MHA-PD-02
at MHA-PD-00), four counterbored #51 rack-screw holes down from the top face
(struck from MHA-PD-26 at MHA-PD-00).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_bottom_guide.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _com import _bind, _com_invoke, _early_bound
from _dimensions import (
    _feature_display_dimensions,
    drive_dimension,
    name_dimensions,
    set_global,
)
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import _set_tolerance_precision
from _feature_tree import _feature_by_name, name_last_feature
from _fit_deviations import deviations
from _hole_spec import blind_cut_dia_mm
from _holes import SharedCoordinate, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from pd_platen_bottom_guide_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GUIDE_DEPTH,
    GUIDE_DEPTH_BAND,
    GUIDE_DEPTH_PLACES,
    GUIDE_HEIGHT,
    GUIDE_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    LOCK_LOCATION_NAMES,
    LOCK_TAP_SPEC,
    LOCK_TAP_X,
    LOCK_TAP_Y,
    PLATEN_TAP_SPEC,
    PLATEN_TAP_X,
    PLATEN_TAP_Y,
    SCREW_CBORE_DEPTH,
    SCREW_CBORE_DEPTH_BAND,
    SCREW_CBORE_DIA,
    SCREW_CBORE_DIA_BAND,
    SCREW_HOLE_DIA,
    SCREW_HOLE_SPEC,
    SCREW_HOLE_X,
    SCREW_HOLE_Z,
    UNIT,
)

PART_NAME = "pd-platen-bottom-guide"
MATERIAL = "Plain Carbon Steel"

_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT
_TOL_BILATERAL = 2  # swTolType_e.swTolBILAT


def _depth_limits(adapter) -> None:
    """The depth's one-sided band as native LIMITs (.40/.39), as MHA-PD-11
    prints it (build_pd_platen_guide._depth_limits)."""
    label = "Depth@Guide"
    display, dimension = _named_dimension(adapter, "Guide", "Depth")
    lower, upper = deviations(GUIDE_DEPTH_BAND)
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = _TOL_LIMIT
    if tolerance.SetValues(lower / 1000.0, upper / 1000.0) is not True:
        raise RuntimeError(f"{label}: LIMIT deviations were rejected")
    if (
        int(tolerance.Type) != _TOL_LIMIT
        or abs(float(tolerance.GetMinValue()) - lower / 1000.0) > 1e-12
        or abs(float(tolerance.GetMaxValue()) - upper / 1000.0) > 1e-12
    ):
        raise RuntimeError(f"{label}: LIMIT tolerance readback changed")
    _set_tolerance_precision(
        display,
        (lower, upper),
        display_unit=UNIT,
        label=label,
        places=GUIDE_DEPTH_PLACES,
    )


def _band_rack_screw_counterbores(adapter) -> None:
    """Put the counterbore's printed bands (owner ruling 2026-11-25, #3620:
    Ø.110 +.004/-.000 and depth .469 ±.005; SCREW_CBORE_DIA_BAND,
    SCREW_CBORE_DEPTH_BAND) on the RackScrewHoles Hole Wizard feature's
    counterbore diameter and depth IN THE PART, so the sheet's native callout
    displays them (build_ch_fulcrum_keeper._band_foot_counterbore); the
    drawing sets only their places. Each dimension is the one on the feature
    equal to SCREW_CBORE_DIA or SCREW_CBORE_DEPTH, and its band is read
    back."""
    feature = _feature_by_name(adapter, "RackScrewHoles")
    seen = []
    dimensions = []
    for display in _feature_display_dimensions(feature):
        raw = _com_invoke(display, "IDisplayDimension", "GetDimension2", 0)
        value = float(_com_invoke(raw, "IDimension", "SystemValue")) * 1000.0
        seen.append((str(_com_invoke(raw, "IDimension", "FullName")), value))
        dimensions.append((value, raw))
    for label, nominal, (lower, upper) in (
        ("diameter", SCREW_CBORE_DIA, deviations(SCREW_CBORE_DIA_BAND)),
        ("depth", SCREW_CBORE_DEPTH, deviations(SCREW_CBORE_DEPTH_BAND)),
    ):
        matches = [raw for value, raw in dimensions if abs(value - nominal) < 1e-4]
        if len(matches) != 1:
            raise RuntimeError(
                f"RackScrewHoles: {len(matches)} dimensions read the counterbore "
                f"{label} {nominal} mm, not 1; dimensions {seen!r}"
            )
        dimension = _bind(matches[0], "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = _TOL_BILATERAL
        if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
            raise RuntimeError(
                f"RackScrewHoles counterbore {label}: SetValues rejected "
                f"{lower}/{upper} mm"
            )
        if (
            int(tolerance.Type) != _TOL_BILATERAL
            or abs(float(tolerance.GetMinValue()) * 1000.0 - lower) > 1e-6
            or abs(float(tolerance.GetMaxValue()) * 1000.0 - upper) > 1e-6
        ):
            raise RuntimeError(
                f"RackScrewHoles counterbore {label}: band did not persist"
            )
        _telemetry.info(
            f"RackScrewHoles counterbore {label} {dimension.FullName}: "
            f"band {lower}/{upper} mm"
        )


def lock_placement_dims() -> list:
    """The lock taps' stations from the left end and their shared row from
    the underside, named for the sheet (rear-face placement sketch)."""
    names = LOCK_LOCATION_NAMES
    dims: list = [((names[0], None), (names[-1], None))]
    for name in names[1:-1]:
        dims.append(((name, None), SharedCoordinate(0)))
    return dims


def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    set_global(adapter, "GuideLength", f"{GUIDE_LENGTH}mm")
    set_global(adapter, "GuideHeight", f"{GUIDE_HEIGHT}mm")
    set_global(adapter, "GuideDepth", f"{GUIDE_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rail outline: corner-at-origin rectangle, length along X, height along Y.
    outline = SketchDims()
    check("create_sketch outline", adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (GUIDE_LENGTH, 0.0),
        (GUIDE_LENGTH, GUIDE_HEIGHT),
        (0.0, GUIDE_HEIGHT),
    ]
    lines = add_line_chain(adapter, rect)
    define_rectilinear_chain(
        adapter,
        lines,
        rect,
        label="bottom guide outline",
        dims=outline,
        names=["Length", "Height"],
        drives=['"GuideLength"', '"GuideHeight"'],
    )
    ensure_fully_defined(adapter, "bottom guide outline")
    check("exit_sketch outline", adapter.exit_sketch())
    name_last_feature(adapter, "GuideProfile")
    drive_jobs += outline.apply(adapter, "GuideProfile")
    check(
        "extrude guide",
        adapter.create_extrusion(
            ExtrusionParameters(depth=GUIDE_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Guide")
    depth_dim = name_dimensions(adapter, "Guide", ["Depth"])
    drive_jobs += [(depth_dim[0], '"GuideDepth"')]
    v_rail = GUIDE_LENGTH * GUIDE_HEIGHT * GUIDE_DEPTH
    volume_check(adapter, "bottom guide rail", v_rail, 0.005 * v_rail)

    # Lock-screw receivers: ONE native Hole Wizard #4-40 tapped THROUGH
    # feature (4 points) from the REAR face (local z=-depth, outward normal
    # -Z), located for the sheet from the left end and the underside.
    lock = wizard_holes(
        adapter,
        LOCK_TAP_SPEC,
        [[x, LOCK_TAP_Y, -GUIDE_DEPTH] for x in LOCK_TAP_X],
        (0.0, 0.0, -1.0),
        f"lock-screw tapped receivers ({LOCK_TAP_SPEC.size})",
        name="LockHoles",
        placement_dims=lock_placement_dims(),
    )
    drive_jobs += lock.placement_drive_jobs
    v_lock = (
        len(LOCK_TAP_X)
        * math.pi
        * (blind_cut_dia_mm(LOCK_TAP_SPEC) / 2.0) ** 2
        * GUIDE_DEPTH
    )
    volume_check(adapter, "bottom guide with lock taps", v_rail - v_lock, 0.05 * v_lock)

    # Platen-screw receivers: ONE native #4-40 tapped THROUGH feature
    # (5 points) from the front face, on MHA-PD-02's lower row as transferred
    # at MHA-PD-00 (no printed location).
    wizard_holes(
        adapter,
        PLATEN_TAP_SPEC,
        [[x, PLATEN_TAP_Y, 0.0] for x in PLATEN_TAP_X],
        (0.0, 0.0, 1.0),
        f"platen-screw tapped receivers ({PLATEN_TAP_SPEC.size})",
        name="PlatenScrewHoles",
    )
    v_platen = (
        len(PLATEN_TAP_X)
        * math.pi
        * (blind_cut_dia_mm(PLATEN_TAP_SPEC) / 2.0) ** 2
        * GUIDE_DEPTH
    )
    v_taps = v_rail - v_lock - v_platen
    volume_check(
        adapter, "bottom guide with platen taps", v_taps, 0.05 * (v_lock + v_platen)
    )

    # Rack-screw holes: ONE native counterbored feature (4 points) down from
    # the top face (outward normal +Y), #51 through, Ø.110 counterbore to the
    # rack spec's floor; struck from MHA-PD-26 at MHA-PD-00 (no location).
    wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[x, GUIDE_HEIGHT, -SCREW_HOLE_Z] for x in SCREW_HOLE_X],
        (0.0, 1.0, 0.0),
        f"rack-screw counterbored holes ({SCREW_HOLE_SPEC.size})",
        name="RackScrewHoles",
    )
    v_screws = len(SCREW_HOLE_X) * math.pi / 4.0 * (
        SCREW_CBORE_DIA**2 * SCREW_CBORE_DEPTH
        + SCREW_HOLE_DIA**2 * (GUIDE_HEIGHT - SCREW_CBORE_DEPTH)
    )
    v_final = v_taps - v_screws
    volume_check(adapter, "bottom guide with rack-screw holes", v_final, 0.05 * v_screws)

    # Deferred drive equations, then re-check neutrality.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven bottom guide (equations neutral)", v_final, 0.02 * v_lock
    )

    _band_rack_screw_counterbores(adapter)
    _depth_limits(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    apply_material(adapter, MATERIAL)
    apply_color(adapter, PANEL_BLACK)
    report_mass_properties(adapter)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    return save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
