r"""Author the cone tip gear, MHA-DT-37: T006 with its spigot and pivot.

Owner decision C1 keyed (2026-11-09, PR #1992): T006 leaves the MHA-DT-03
family for its own part. Its six leaves are the family's T006, cut the
family's way (``build_dt_cone_gear``): an extruded blank at the ruled tip
diameter, one finite DT6-FORM1 gap of equation curves
(``native_gap_segments``) cut through it, patterned six times about the
Top x Right axis, and the family's construction-only inspection sketches for
the circular tooth thickness, the root envelope and the tip diameter. Then
two turned features: the Ø.0625 spigot, extruded south off the Front Plane
(the leaves' south face), and the Ø.0625 pivot, extruded north off
``LeavesNorthPlane`` (their north face); each diameter and length is a named,
banded model dimension.

The frame is a dt-cone-gear configuration's (``dt_cone_tip_gear_spec``), so
the drive train mates the part like the family: ``Axis1`` coaxial, the Front
Plane's axial seat, the Right Plane's anti-spin. Every step is checked against
its analytic volume, and the finished part's centre of mass and length prove
the stems stand on their own sides. One configuration, "Default", and its
derived "Default Simplified" (teeth suppressed) for assembly line views.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_tip_gear.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound
from _cone_gear_native import (
    _author_blank_dia_reference,
    _author_gap_floor_reference,
    _author_tooth_thickness_reference,
    native_gap_segments,
)
from _dimensions import drive_dimension, name_dimensions
from _document_units import apply_package_model_units
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_prefix import set_dimension_prefix
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _feature_tree import name_last_feature
from _fit_deviations import deviations
from _gear import equation_curve, pattern_about_z
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _rebuild import force_rebuild
from _session import run_build
from _simplified_part import save_simplified_part
from _sketch import SketchDims, blank_reference_sketches, ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from dt_cone_gear_notes import BLANK_DIA_REFERENCE_SKETCH
from dt_cone_tip_gear_notes import custom_cutter_detail, gear_data, sheet_notes
from dt_cone_tip_gear_spec import (
    BLANK_DIA_BAND,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FACE_WIDTH_BAND,
    FLOOR_DEVIATIONS_MM,
    FLOOR_DIA,
    GAP_FLOOR_SKETCH,
    LEAVES_NORTH_PLANE,
    MM_PER_IN,
    OVERALL_LENGTH_MM,
    PATTERN_AXIS,
    PIVOT_DIA_BAND,
    PIVOT_LENGTH_MM,
    PROFILE,
    REFERENCE_SKETCHES,
    SIMPLIFIED_FEATURES,
    SPIGOT_DIA_BAND,
    SPIGOT_LENGTH_MM,
    STEM_DIA_MM,
    SURFACE_FINISHES,
    TEETH,
    TOOTH_FEATURES,
    TOOTH_REFERENCE_SKETCH,
    TOOTH_THICKNESS_BAND,
    UNIT,
)
from involute_gear import set_global

PART_NAME = "dt-cone-tip-gear"

# The family's appearance; the title block prints the C67500 specification.
MATERIAL = "Brass"
_TOL_LIMIT = 3  # swTolType_e.swTolLIMIT
_STEM_AREA_MM2 = math.pi * (STEM_DIA_MM / 2.0) ** 2


def _set_gap_floor_limits(adapter: Any) -> None:
    """Store the printed root-envelope limits on FloorDia as a LIMIT pair (the
    family's per-configuration form, in this part's one configuration)."""
    _display, dimension = _named_dimension(adapter, GAP_FLOOR_SKETCH, "FloorDia")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = _TOL_LIMIT
    lower, upper = FLOOR_DEVIATIONS_MM
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(
            f"FloorDia: SetValues rejected the limits {FLOOR_DEVIATIONS_MM} mm"
        )
    if int(tolerance.Type) != _TOL_LIMIT:
        raise RuntimeError("FloorDia: LIMIT tolerance type did not persist")
    observed = (
        float(tolerance.GetMinValue()) * 1000.0,
        float(tolerance.GetMaxValue()) * 1000.0,
    )
    if any(abs(o - e) > 1e-6 for o, e in zip(observed, FLOOR_DEVIATIONS_MM)):
        raise RuntimeError(
            f"FloorDia: limits read {observed} mm, expected {FLOOR_DEVIATIONS_MM}"
        )
    _telemetry.success(f"FloorDia: LIMIT {FLOOR_DEVIATIONS_MM} mm")


def _assert_one_body(adapter: Any) -> None:
    """The stems join the leaves: one solid body, not three."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())  # swSolidBody
    if len(bodies) != 1:
        raise RuntimeError(f"{PART_NAME}: {len(bodies)} solid bodies, expected 1")


async def _centre_of_mass_check(adapter: Any, expected_z: float, label: str) -> None:
    """A stem extruded the wrong way keeps its volume; it moves the centroid."""
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"{label}: get_mass_properties failed: {mass.error}")
    centre = [float(value) for value in mass.data.center_of_mass]
    tol = 0.05  # mm: a wrong-way stem moves it millimetres
    if (
        abs(centre[0]) > tol
        or abs(centre[1]) > tol
        or abs(centre[2] - expected_z) > tol
    ):
        raise RuntimeError(
            f"{label}: centre of mass {centre}, expected (0, 0, {expected_z:.4f}) mm"
        )
    _telemetry.success(f"{label}: centre of mass z {centre[2]:.4f} mm")


async def _turn_stem(
    adapter: Any,
    *,
    plane: str,
    profile: str,
    feature: str,
    length: float,
    reverse: bool,
    label: str,
) -> None:
    """One integral stem: an origin-centred Ø circle on ``plane`` with a
    driving diameter, extruded ``length``; diameter and length named for the
    drawing (``<feature>Dia``, ``<feature>Length``)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(
        adapter,
        0.0,
        0.0,
        STEM_DIA_MM / 2.0,
        label,
        dims=dims,
        names=(None, None, f"{feature}Dia"),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    dims.apply(adapter, profile)
    check(
        f"extrude {label}",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=length, reverse_direction=reverse)
        ),
    )
    name_last_feature(adapter, feature)
    name_dimensions(adapter, feature, [f"{feature}Length"])


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    drive_jobs: list[tuple[str, str]] = []
    check("create_part", await adapter.create_part())
    # The row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The globals the family's inspection sketches drive from (inch document:
    # bare values are inches).
    ra_mm = PROFILE.blank_radius_mm
    await set_global(adapter, "ToothCount", str(TEETH), TEETH)
    await set_global(adapter, "DP", f"{DIAMETRAL_PITCH:.17g}", DIAMETRAL_PITCH)
    for name, value in (
        ("Ra", ra_mm / MM_PER_IN),
        ("ToothThickness", PROFILE.pitch_tooth_thickness_mm / MM_PER_IN),
        ("FloorDia", FLOOR_DIA / MM_PER_IN),
    ):
        await set_global(adapter, name, f"{value:.17g}", value)

    # ------------------------------------------------------------------
    # Leaves. The blank: an origin-snapped circle at the tip radius with a
    # driving diameter (2 * "Ra"), extruded north from the Front Plane by the
    # face width (the family's recipe, so the Front Plane is the south face).
    # ------------------------------------------------------------------
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        ra_mm,
        "blank",
        dims=blank,
        names=(None, None, "BlankDia"),
        drives=(None, None, '2 * "Ra"'),
    )
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    name_last_feature(adapter, "BlankProfile")
    drive_jobs += blank.apply(adapter, "BlankProfile")
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=FACE_WIDTH)),
    )
    name_last_feature(adapter, "Blank")
    name_dimensions(adapter, "Blank", ["FaceWidth"])
    blank_volume = math.pi * ra_mm**2 * FACE_WIDTH
    await volume_check(adapter, "blank", blank_volume, 0.005 * blank_volume)
    await _centre_of_mass_check(adapter, FACE_WIDTH / 2.0, "blank faces north")

    # One finite DT6-FORM1 gap, a through cut, the six-gap pattern.
    gap_sketch, gap_cut, gap_pattern = TOOTH_FEATURES
    check("create_sketch gap", await adapter.create_sketch("Front"))
    curves = [
        await equation_curve(adapter, f"T006 {label}", x, y)
        for label, x, y in native_gap_segments(TEETH)
    ]
    await ensure_fully_defined(
        adapter, "T006 finite gap", fix_entities=curves, allow_fix_escalation=True
    )
    check("exit_sketch gap", await adapter.exit_sketch())
    name_last_feature(adapter, gap_sketch)
    check(
        "cut T006 finite gap",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 1.0)),
    )
    name_last_feature(adapter, gap_cut)
    removed = PROFILE.gap_area_mm2 * FACE_WIDTH
    area_error = PROFILE.gap_area_error_bound_mm2 * FACE_WIDTH
    await volume_check(
        adapter, "T006 single gap", blank_volume - removed, 0.01 * removed - area_error
    )
    await pattern_about_z(adapter, gap_cut, TEETH, ra_mm, FACE_WIDTH / 2.0)
    name_last_feature(adapter, gap_pattern)
    # The stems' gates below stand on the measured leaves, not on the gap
    # area's analytic error bound.
    leaves_volume = await volume_check(
        adapter,
        "T006 six gaps",
        blank_volume - TEETH * removed,
        TEETH * (0.01 * removed - area_error),
    )
    part = _early_bound(adapter.currentModel, "IPartDoc")
    if part.FeatureByName(PATTERN_AXIS) is None:
        raise RuntimeError(f"{PART_NAME}: the pattern axis is not {PATTERN_AXIS!r}")

    # ------------------------------------------------------------------
    # Stems, turned with the leaves between centres: the spigot south off the
    # Front Plane, the pivot north off the leaves' north face (a named plane
    # the drive train seats the MHA-DT-38 bushing on, its offset owned by
    # FaceWidth).
    # ------------------------------------------------------------------
    await _turn_stem(
        adapter,
        plane="Front",
        profile="SpigotProfile",
        feature="Spigot",
        length=SPIGOT_LENGTH_MM,
        reverse=True,
        label="spigot",
    )
    stem_volume = _STEM_AREA_MM2 * SPIGOT_LENGTH_MM
    await volume_check(
        adapter, "spigot", leaves_volume + stem_volume, 0.005 * stem_volume
    )
    check(
        f"create_plane {LEAVES_NORTH_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=FACE_WIDTH
            )
        ),
    )
    name_last_feature(adapter, LEAVES_NORTH_PLANE)
    station = name_dimensions(adapter, LEAVES_NORTH_PLANE, ["LeavesNorthStation"])
    drive_jobs += [(station[0], '"FaceWidth@Blank"')]
    await _turn_stem(
        adapter,
        plane=LEAVES_NORTH_PLANE,
        profile="PivotProfile",
        feature="Pivot",
        length=PIVOT_LENGTH_MM,
        reverse=False,
        label="pivot",
    )
    # Hidden, not removed: the drive train seats the bushing on it by name,
    # and shown it would render in every assembly that places the gear.
    blank_reference_geometry(adapter, ((LEAVES_NORTH_PLANE, "PLANE"),))
    pivot_volume = _STEM_AREA_MM2 * PIVOT_LENGTH_MM
    volume = leaves_volume + stem_volume + pivot_volume
    volume = await volume_check(
        adapter, "pivot", volume, 0.005 * (stem_volume + pivot_volume)
    )
    _assert_one_body(adapter)
    centroid = (
        leaves_volume * FACE_WIDTH / 2.0
        - stem_volume * SPIGOT_LENGTH_MM / 2.0
        + pivot_volume * (FACE_WIDTH + PIVOT_LENGTH_MM / 2.0)
    ) / volume
    await _centre_of_mass_check(adapter, centroid, "stems on their own sides")
    await bbox_extent_check(adapter, "spigot end to pivot end", "z", OVERALL_LENGTH_MM)

    # ------------------------------------------------------------------
    # The family's construction-only inspection witnesses, volume-neutral.
    # ------------------------------------------------------------------
    tooth_reference = await _author_tooth_thickness_reference(adapter, teeth=TEETH)
    name_last_feature(adapter, TOOTH_REFERENCE_SKETCH)
    drive_jobs += tooth_reference.apply(adapter, TOOTH_REFERENCE_SKETCH)
    floor_reference = await _author_gap_floor_reference(adapter, teeth=TEETH)
    name_last_feature(adapter, GAP_FLOOR_SKETCH)
    drive_jobs += floor_reference.apply(adapter, GAP_FLOOR_SKETCH)
    blank_reference = await _author_blank_dia_reference(adapter, ra_mm)
    drive_jobs += blank_reference.apply(adapter, BLANK_DIA_REFERENCE_SKETCH)

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven tip gear (equations neutral)", volume, 0.001 * volume
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Bands on the model dimensions (millimetres; UNIT prints them in decimal
    # inch at the nominal's places), then the part-owned places.
    for feature, name, band in (
        (BLANK_DIA_REFERENCE_SKETCH, "BlankDia", BLANK_DIA_BAND),
        ("Blank", "FaceWidth", FACE_WIDTH_BAND),
        (TOOTH_REFERENCE_SKETCH, "ToothThickness", TOOTH_THICKNESS_BAND),
        ("SpigotProfile", "SpigotDia", SPIGOT_DIA_BAND),
        ("PivotProfile", "PivotDia", PIVOT_DIA_BAND),
    ):
        set_dimension_bilateral_tolerance(
            adapter,
            feature,
            name,
            *deviations(band),
            places=DRAWING_PRECISION[feature][name],
            display_unit=UNIT,
        )
    _set_gap_floor_limits(adapter)
    # A diametric linear size prints bare in the side view; the model carries
    # SolidWorks' own Ø token (the family's witness).
    set_dimension_prefix(adapter, BLANK_DIA_REFERENCE_SKETCH, "BlankDia", "<MOD-DIAM>")
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature, names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Gear Data": gear_data(),
            "Manufacturing Notes": sheet_notes(),
            "Cutter Profile": custom_cutter_detail(),
        },
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    return await save_simplified_part(adapter, PART_NAME, SIMPLIFIED_FEATURES)


if __name__ == "__main__":
    sys.exit(run_build(build))
