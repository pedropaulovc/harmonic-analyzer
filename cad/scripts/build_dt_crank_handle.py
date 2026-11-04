r"""Reproduction script: crank handle (book ch. 11, pp. 12-15).

The pear-shaped wooden handle (stained black) that rotates on the crank-arm
pivot -- the book calls it "a smooth piece of wood ... well-suited for a firm
grip" (p.12).  User ruling 2026-09-29 (the ch11 p.14/p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-DT-34 and the
bright disc at the butt a steel cup MHA-DT-35, so this oak body ends in a turned
tenon (the ferrule's seat) and a counterbore (the cup's seat).

User rulings 2026-09-30 (ch30 eight-views-4 side view, approved CadQuery
concept v4): five tangent arcs span the wood -- a concave flare from the
ferrule's OD down to a slim waist, an S-curve (concave then convex) up to the
Ø21 swell, a dome, and an end round cresting on the flat oak end round the
cup.  Circumferentially smooth after the revolve.

Layout: handle axis along +X; x=0 is the ferrule's arm face (the handle's
seat on the arm), so the oak starts at the tenon end, short of it.  One
revolve carries the tenon, its 45-degree root relief into the shoulder (owner
ruling 2026-10-24, #1900), the reamed bore, the grip and the counterbore, the
tenon root and the counterbore's floor corner rounded in the profile to their
single-limit R.012 MAX (owner ruling A on #1661).  The profile is defined by
what the sheet prints -- stations from the tenon end face, the shoulder,
waist, swell and crest diameters and the end round -- with the waist and
swell centres on their stations; the tangencies fix the other four radii,
which are driven references.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_handle.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties

PART_NAME = "dt-crank-handle"
MATERIAL = "Oak"  # see _appearance.apply_material docstring

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print).
from dt_crank_handle_spec import (  # noqa: E402
    COUNTERBORE_DEPTH,
    COUNTERBORE_DIA,
    COUNTERBORE_FLOOR_X,
    COUNTERBORE_R,
    CREST_DIA,
    DOME_CENTER,
    DOME_END,
    DOME_R,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    END_ROUND_CENTER,
    END_ROUND_R,
    FERRULE_LENGTH,
    FLARE_CENTER,
    FLARE_R,
    INFLECTION,
    INSIDE_CORNER_R_BAND,
    INSIDE_CORNER_R_MAX,
    INSIDE_CORNER_R_TOL_TYPE,
    ISOMETRIC_VIEW_NOTE,
    OAK_END_X,
    PEAK_R,
    PEAK_X,
    PIVOT_BORE_DIA,
    S_CONCAVE_CENTER,
    S_CONCAVE_R,
    S_CONVEX_CENTER,
    S_CONVEX_R,
    SHOULDER_R,
    SHOULDER_X,
    TENON_DIA,
    TENON_LENGTH,
    TENON_R,
    TENON_ROOT_RELIEF,
    TENON_ROOT_RELIEF_TOL,
    TENON_ROOT_ROUND_REACH,
    TENON_X0,
    WAIST_R,
    WAIST_X,
    WOOD_LENGTH,
    profile_radius,
    UNIT,
)

# The tenon root (owner ruling 2026-10-24, #1900): a 45-degree relief cone
# cut into the shoulder, from the shoulder face TENON_ROOT_RELIEF out from the
# tenon OD down to the tenon TENON_ROOT_RELIEF behind the face, its corner
# with the tenon rounded at INSIDE_CORNER_R_MAX.  That round meets the tenon
# TENON_ROOT_ROUND_REACH (R (1 + sqrt 2)) back from the corner and the cone
# R (1 + sqrt 2) along it, R / sqrt 2 off the corner's centre each way.
RELIEF_TOP = (SHOULDER_X, TENON_R + TENON_ROOT_RELIEF)
_ROOT_CORNER = (SHOULDER_X + TENON_ROOT_RELIEF, TENON_R)
ROOT_ON_TENON = (_ROOT_CORNER[0] - TENON_ROOT_ROUND_REACH, TENON_R)
ROOT_CENTER = (ROOT_ON_TENON[0], TENON_R + INSIDE_CORNER_R_MAX)
ROOT_ON_RELIEF = (
    ROOT_CENTER[0] + INSIDE_CORNER_R_MAX / math.sqrt(2.0),
    ROOT_CENTER[1] + INSIDE_CORNER_R_MAX / math.sqrt(2.0),
)
# The relief line's run from the root round to the shoulder face, by equation
# from the leg and the round so the cone stays at 45 degrees.
RELIEF_RUN = ROOT_ON_RELIEF[0] - SHOULDER_X
_RELIEF_RUN_EXPR = '"TenonRootRelief" - "InsideCornerR" * 1.7071067812'
# The root round turns 135 degrees, from the tenon OD to the 45-degree relief.
ROOT_ARC_LENGTH = INSIDE_CORNER_R_MAX * 3.0 * math.pi / 4.0


def _spandrel(
    corner: tuple[float, float],
    along: tuple[tuple[float, float], tuple[float, float]],
    radius: float,
) -> tuple[float, float]:
    """Area and centroid height of the material a fillet of ``radius`` adds
    in the corner at ``corner`` between the faces running off it along the
    unit vectors ``along``: the kite between the corner, the two tangent
    points and the centre, less the arc's sector."""
    (ax, ay), (bx, by) = along
    half = math.acos(ax * bx + ay * by) / 2.0
    reach = radius / math.tan(half)
    bisector = math.hypot(ax + bx, ay + by)
    centre_y = corner[1] + radius / math.sin(half) * (ay + by) / bisector
    kite = reach * radius
    kite_y = (
        2.0 * corner[1]
        + (corner[1] + reach * ay)
        + (corner[1] + reach * by)
        + 2.0 * centre_y
    ) / 6.0
    sweep = math.pi - 2.0 * half
    sector = radius**2 * sweep / 2.0
    sector_y = (
        centre_y
        - (4.0 * radius * math.sin(sweep / 2.0) / (3.0 * sweep)) * (ay + by) / bisector
    )
    area = kite - sector
    return area, (kite * kite_y - sector * sector_y) / area


def _nominal_volume() -> float:
    """Revolved volume of the nominal profile, less the bore: the check that
    every arc was swept on the side the spec means (Simpson's rule)."""

    def solid(x0: float, x1: float, radius) -> float:
        n = 2000
        h = (x1 - x0) / n
        total = radius(x0) ** 2 + radius(x1) ** 2
        for i in range(1, n):
            total += (4 if i % 2 else 2) * radius(x0 + i * h) ** 2
        return math.pi * total * h / 3.0

    grip = solid(SHOULDER_X, OAK_END_X, profile_radius)
    tenon = math.pi * TENON_R**2 * TENON_LENGTH
    counterbore = math.pi * COUNTERBORE_R**2 * COUNTERBORE_DEPTH
    bore = math.pi * (PIVOT_BORE_DIA / 2.0) ** 2 * (COUNTERBORE_FLOOR_X - TENON_X0)
    # The relief turns a right triangle of legs c out of the shoulder at the
    # tenon OD, its centroid c/3 above it: pi c^2 (r + c/3).
    relief = math.pi * TENON_ROOT_RELIEF**2 * (TENON_R + TENON_ROOT_RELIEF / 3.0)
    # Pappus: each inside corner's fillet adds its spandrel -- the tenon root
    # in the relief's 45-degree corner, the counterbore's floor corner square.
    diagonal = 1.0 / math.sqrt(2.0)
    corners = 0.0
    for corner, along in (
        (_ROOT_CORNER, ((-1.0, 0.0), (-diagonal, diagonal))),
        ((COUNTERBORE_FLOOR_X, COUNTERBORE_R), ((1.0, 0.0), (0.0, -1.0))),
    ):
        area, centroid_y = _spandrel(corner, along, INSIDE_CORNER_R_MAX)
        corners += 2.0 * math.pi * area * centroid_y
    return grip + tenon - relief - counterbore - bore + corners


V_HANDLE = _nominal_volume()

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)


def _make_driven(adapter, dimension_id: str, label: str) -> None:
    """Turn a just-made sketch dimension into a DRIVEN (reference) one
    (build_mg_magnifying_vertical_rod._make_driven)."""
    display = _early_bound(adapter._sketch_entities[dimension_id], "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(dimension.DrivenState) != 1:
        raise RuntimeError(f"{label}: dimension did not become driven")


# The two R.012 MAX inside corners as solved: the counterbore's floor round
# turns 90 degrees and the tenon root 135 degrees, into the relief's corner.
INSIDE_CORNER_ARC_LENGTHS = tuple(
    sorted((INSIDE_CORNER_R_MAX * math.pi / 2.0, ROOT_ARC_LENGTH))
)


def _check_root_arc_sweep(adapter) -> None:
    """Read the rebuilt HandleProfile's inside-corner arcs back and require the
    floor round's quarter and the tenon root's 135-degree sweep."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    feature = _early_bound(part.FeatureByName("HandleProfile"), "IFeature")
    sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
    lengths = []
    for raw in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw, "ISketchSegment")
        if int(segment.GetType()) != 1:  # swSketchSegments_e.swSketchARC
            continue
        arc = _early_bound(raw, "ISketchArc")
        radius = float(arc.GetRadius()) * 1000.0
        if math.isclose(radius, INSIDE_CORNER_R_MAX, abs_tol=1e-6):
            lengths.append(float(segment.GetLength()) * 1000.0)
    lengths.sort()
    if len(lengths) != 2 or not all(
        math.isclose(got, want, abs_tol=1e-4)
        for got, want in zip(lengths, INSIDE_CORNER_ARC_LENGTHS, strict=True)
    ):
        raise RuntimeError(
            f"HandleProfile R{INSIDE_CORNER_R_MAX:g} arcs are {lengths} long, not the "
            f"floor round's and tenon root's {list(INSIDE_CORNER_ARC_LENGTHS)}"
        )
    _telemetry.success(f"inside-corner arc sweeps read back: {lengths}")


def _inside_corner_max_limit(adapter, dimension_name: str) -> None:
    """An inside corner's radius as a MAX single limit carrying the band's
    deviations (build_pn_pen_rod._shoulder_fillet_max_limit's recipe)."""
    lower, upper = deviations(INSIDE_CORNER_R_BAND)
    _, dimension = _named_dimension(adapter, "HandleProfile", dimension_name)
    label = f"{dimension_name}@HandleProfile"
    value = float(dimension.SystemValue)
    if not math.isclose(value, INSIDE_CORNER_R_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max "
            f"{INSIDE_CORNER_R_MAX}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = INSIDE_CORNER_R_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != INSIDE_CORNER_R_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {INSIDE_CORNER_R_MAX:g} MAX")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("FerruleLength", FERRULE_LENGTH),
        ("TenonLength", TENON_LENGTH),
        ("TenonDia", TENON_DIA),
        ("ShoulderR", SHOULDER_R),
        ("WaistX", WAIST_X),
        ("WaistDia", 2.0 * WAIST_R),
        ("InflectionX", INFLECTION[0]),
        ("PeakX", PEAK_X),
        ("PeakDia", 2.0 * PEAK_R),
        ("CrestDia", CREST_DIA),
        ("EndRoundR", END_ROUND_R),
        ("WoodLength", WOOD_LENGTH),
        ("CounterboreDia", COUNTERBORE_DIA),
        ("CounterboreDepth", COUNTERBORE_DEPTH),
        ("PivotBoreDia", PIVOT_BORE_DIA),
        ("InsideCornerR", INSIDE_CORNER_R_MAX),
        ("TenonRootRelief", TENON_ROOT_RELIEF),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    bore_r = PIVOT_BORE_DIA / 2.0
    tenon_corner = (TENON_X0, TENON_R)
    shoulder_pt = (SHOULDER_X, SHOULDER_R)
    waist_pt = (WAIST_X, WAIST_R)
    peak_pt = (PEAK_X, PEAK_R)
    oak_end_pt = (OAK_END_X, COUNTERBORE_R)
    crest_pt = (OAK_END_X, END_ROUND_CENTER[1])
    # The two inside corners, each an arc of INSIDE_CORNER_R_MAX tangent to its
    # faces: the tenon root turns from the tenon OD into the shoulder relief
    # (owner ruling 2026-10-24, #1900), the counterbore's floor corner from its
    # wall into its floor.
    corner_r = INSIDE_CORNER_R_MAX
    floor_round_start = (COUNTERBORE_FLOOR_X + corner_r, COUNTERBORE_R)
    floor_round_end = (COUNTERBORE_FLOOR_X, COUNTERBORE_R - corner_r)
    floor_round_center = (COUNTERBORE_FLOOR_X + corner_r, COUNTERBORE_R - corner_r)

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the shallow arcs to auto relations.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, COUNTERBORE_FLOOR_X, 0.0),
    )
    # Tenon: end face (from the reamed bore) -> OD, running on behind the
    # shoulder face -> the root round -> the 45-degree relief back out to the
    # shoulder face -> the shoulder up to the ferrule's OD.
    tenon_end, tenon_top = await add_line_chain(
        adapter, [(TENON_X0, bore_r), tenon_corner, ROOT_ON_TENON], close=False
    )
    # add_arc sweeps CCW from start to end; each is ordered so the sweep is the
    # minor arc on the silhouette side.  Concave arcs (centre above) run left
    # to right under their centre; convex ones (centre below) right to left.
    tenon_root = check(
        "tenon root arc",
        await adapter.add_arc(*ROOT_CENTER, *ROOT_ON_TENON, *ROOT_ON_RELIEF),
    )
    relief, shoulder = await add_line_chain(
        adapter, [ROOT_ON_RELIEF, RELIEF_TOP, shoulder_pt], close=False
    )
    flare = check(
        "flare arc", await adapter.add_arc(*FLARE_CENTER, *shoulder_pt, *waist_pt)
    )
    s_concave = check(
        "S-curve concave arc",
        await adapter.add_arc(*S_CONCAVE_CENTER, *waist_pt, *INFLECTION),
    )
    s_convex = check(
        "S-curve convex arc",
        await adapter.add_arc(*S_CONVEX_CENTER, *peak_pt, *INFLECTION),
    )
    dome = check("dome arc", await adapter.add_arc(*DOME_CENTER, *DOME_END, *peak_pt))
    end_round = check(
        "end round arc", await adapter.add_arc(*END_ROUND_CENTER, *crest_pt, *DOME_END)
    )
    # Crest -> flat oak end face -> counterbore wall -> the floor round ->
    # counterbore floor -> the reamed bore back to the tenon end face: the
    # bore is part of the revolve, so its diameter prints on the section with
    # the rest.
    oak_end_face, counterbore_wall = await add_line_chain(
        adapter, [crest_pt, oak_end_pt, floor_round_start], close=False
    )
    floor_round = check(
        "counterbore floor round arc",
        await adapter.add_arc(
            *floor_round_center, *floor_round_start, *floor_round_end
        ),
    )
    counterbore_floor, bore_wall = await add_line_chain(
        adapter,
        [floor_round_end, (COUNTERBORE_FLOOR_X, bore_r), (TENON_X0, bore_r)],
        close=False,
    )
    set_sketch_direct_db(adapter, False)

    check(
        "axis on the origin",
        await adapter.add_sketch_constraint(f"{centerline}.start", "origin", "coincident"),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    check(
        "axis ends at the counterbore floor",
        await adapter.add_sketch_constraint(
            f"{centerline}.end", f"{counterbore_floor}.end", "vertical_points"
        ),
    )
    for label, entity, relation in (
        ("tenon end", tenon_end, "vertical"),
        ("tenon OD", tenon_top, "horizontal"),
        ("tenon shoulder", shoulder, "vertical"),
        ("oak end face", oak_end_face, "vertical"),
        ("counterbore wall", counterbore_wall, "horizontal"),
        ("counterbore floor", counterbore_floor, "vertical"),
        ("reamed bore", bore_wall, "horizontal"),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    # Horizontal tangents at the waist and the swell: each centre stands on
    # its station.
    for arc, point, label in (
        (flare, f"{flare}.end", "waist"),
        (s_convex, f"{s_convex}.start", "swell"),
    ):
        check(
            f"{label} centre on its station",
            await adapter.add_sketch_constraint(f"{arc}.center", point, "vertical_points"),
        )
    # Dimensions in creation order; SketchDims renames them by that order.
    # The tangencies fix these four radii: each is made while the sketch is
    # still free (so it never over-defines) and turned driven at once, a
    # reference the drawing parenthesizes.
    for arc, radius, name in (
        (flare, FLARE_R, "FlareR"),
        (s_concave, S_CONCAVE_R, "SConcaveR"),
        (s_convex, S_CONVEX_R, "SConvexR"),
        (dome, DOME_R, "DomeR"),
    ):
        reference = check(
            f"{name} reference radius",
            await adapter.add_sketch_dimension(arc, None, "radial", radius),
        )
        _make_driven(adapter, reference, name)
        profile.record(name)
    await dimension_between(
        adapter,
        f"{tenon_end}.start",
        "origin",
        "horizontal_distance",
        TENON_X0,
        "tenon end from the arm face",
    )
    profile.record("TenonStart", '"FerruleLength" - "TenonLength"')
    await add_diametric_linear_dimension(
        adapter,
        centerline,
        bore_wall,
        ((TENON_X0 + COUNTERBORE_FLOOR_X) / 2.0, bore_r + 3.0),
        "PivotBoreDia",
    )
    profile.record("PivotBoreDia", '"PivotBoreDia"')
    # To the shoulder face, where the relief leaves it: the tenon OD runs on
    # behind the face to the root round in the relief.
    await dimension_between(
        adapter,
        f"{tenon_end}.end",
        f"{shoulder}.start",
        "horizontal_distance",
        TENON_LENGTH,
        "tenon length",
    )
    profile.record("TenonLength", '"TenonLength"')
    # The root relief's leg on the shoulder face, up from the tenon OD at the
    # tenon end's corner, so the dimension stands off the part's left end; the
    # relief line's run to the root round holds it at 45 degrees.
    await dimension_between(
        adapter,
        f"{tenon_end}.end",
        f"{relief}.end",
        "vertical_distance",
        TENON_ROOT_RELIEF,
        "tenon root relief leg",
    )
    profile.record("TenonRootRelief", '"TenonRootRelief"')
    await dimension_between(
        adapter,
        f"{relief}.start",
        f"{relief}.end",
        "horizontal_distance",
        RELIEF_RUN,
        "tenon root relief run",
    )
    profile.record("TenonRootReliefRun", _RELIEF_RUN_EXPR)
    # To the tenon end face's corner, not the OD line: the drawing hangs the
    # diameter's shelf on the side its text stands from the measured point, so
    # the fitted tenon's long callout can run right, into the sheet.
    await add_diametric_linear_dimension(
        adapter,
        centerline,
        f"{tenon_end}.end",
        ((TENON_X0 + SHOULDER_X) / 2.0, TENON_R + 4.0),
        "TenonDia",
    )
    profile.record("TenonDia", '"TenonDia"')
    await add_diametric_linear_dimension(
        adapter,
        centerline,
        f"{shoulder}.end",
        (SHOULDER_X - 1.0, SHOULDER_R + 4.0),
        "ShoulderDia",
    )
    profile.record("ShoulderDia", '"ShoulderR" * 2')
    # The stations print from the tenon end face, the one faced end.
    station = '"FerruleLength" + "TenonLength"'
    for point, x, name, knob in (
        (f"{flare}.end", WAIST_X, "WaistStation", '"WaistX"'),
        (f"{s_concave}.end", INFLECTION[0], "InflectionStation", '"InflectionX"'),
        (f"{s_convex}.start", PEAK_X, "PeakStation", '"PeakX"'),
    ):
        await dimension_between(
            adapter,
            f"{tenon_end}.end",
            point,
            "horizontal_distance",
            x - TENON_X0,
            f"{name} from the tenon end",
        )
        profile.record(name, f"{knob} - {station}")
    for point, x, radius, name in (
        (f"{flare}.end", WAIST_X, WAIST_R, "WaistDia"),
        (f"{s_convex}.start", PEAK_X, PEAK_R, "PeakDia"),
        (f"{end_round}.start", OAK_END_X + 3.0, END_ROUND_CENTER[1], "CrestDia"),
    ):
        await add_diametric_linear_dimension(
            adapter, centerline, point, (x, radius + 4.0), name
        )
        profile.record(name, f'"{name}"')
    # The S-curve's tangent point, where the inflection station ends: the
    # tangencies fix its diameter, so like the four radii it is made while the
    # sketch is still free and turned driven at once, a reference the drawing
    # parenthesizes (MHA-DT-08 machinist review of 69eda6e4c: the turner reads
    # the template point instead of working it out from tangency).
    inflection_dia = await add_diametric_linear_dimension(
        adapter,
        centerline,
        f"{s_concave}.end",
        (INFLECTION[0], INFLECTION[1] + 4.0),
        "InflectionDia",
    )
    inflection_dimension = _early_bound(inflection_dia.GetDimension2(0), "IDimension")
    inflection_dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(inflection_dimension.DrivenState) != 1:
        raise RuntimeError("InflectionDia: dimension did not become driven")
    if not math.isclose(
        float(inflection_dimension.SystemValue) * 1000.0,
        2.0 * INFLECTION[1],
        abs_tol=1e-4,
    ):
        raise RuntimeError(
            f"InflectionDia: measures {float(inflection_dimension.SystemValue) * 1000.0}"
            f" mm, not the tangent point's Ø{2.0 * INFLECTION[1]}"
        )
    profile.record("InflectionDia")
    check(
        "end round radius",
        await adapter.add_sketch_dimension(end_round, None, "radial", END_ROUND_R),
    )
    profile.record("EndRoundR", '"EndRoundR"')
    # The inside corners at their single limit, both from the one knob.
    for arc, name, label in (
        (tenon_root, "TenonRootRadius", "tenon root radius"),
        (floor_round, "CounterboreFloorRadius", "counterbore floor radius"),
    ):
        check(
            label,
            await adapter.add_sketch_dimension(
                arc, None, "radial", INSIDE_CORNER_R_MAX
            ),
        )
        profile.record(name, '"InsideCornerR"')
    # The oak overall, tenon end face to the oak's end at the counterbore
    # mouth.
    await dimension_between(
        adapter,
        f"{tenon_end}.end",
        f"{counterbore_wall}.start",
        "horizontal_distance",
        OAK_END_X - TENON_X0,
        "oak overall from the tenon end",
    )
    profile.record("OverallLength", '"TenonLength" + "WoodLength"')
    # From the oak end to the floor below the floor round, the wall line
    # stopping short of the floor by the round.
    await dimension_between(
        adapter,
        f"{counterbore_wall}.start",
        f"{counterbore_floor}.start",
        "horizontal_distance",
        COUNTERBORE_DEPTH,
        "counterbore depth",
    )
    profile.record("CounterboreDepth", '"CounterboreDepth"')
    await add_diametric_linear_dimension(
        adapter,
        centerline,
        counterbore_wall,
        (COUNTERBORE_FLOOR_X + COUNTERBORE_DEPTH / 2.0, COUNTERBORE_R + 4.0),
        "CounterboreDia",
    )
    profile.record("CounterboreDia", '"CounterboreDia"')
    for first, second, label in (
        (flare, s_concave, "waist"),
        (s_concave, s_convex, "inflection"),
        (s_convex, dome, "swell"),
        (dome, end_round, "end round"),
        (end_round, oak_end_face, "end round crest"),
        (tenon_top, tenon_root, "tenon root on the tenon OD"),
        (tenon_root, relief, "tenon root on the relief"),
        (counterbore_wall, floor_round, "floor round on the counterbore wall"),
        (floor_round, counterbore_floor, "floor round on the counterbore floor"),
    ):
        check(
            f"{label} tangent",
            await adapter.add_sketch_constraint(first, second, "tangent"),
        )
    await ensure_fully_defined(adapter, "handle profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HandleProfile")
    drive_jobs += profile.apply(adapter, "HandleProfile")

    check(
        "revolve handle",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Handle")

    await volume_check(adapter, "crank handle", V_HANDLE, 0.002 * V_HANDLE)

    # Deferred drive equations after the model + a rebuild exist, so every
    # target resolves.  Each equation evaluates to the value just built, so
    # the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven crank handle (equations neutral)", V_HANDLE, 0.002 * V_HANDLE
    )
    # The volume gate cannot tell the root round's 135-degree sweep from its
    # 225-degree complement (about one revolved inside-corner disk, inside
    # 0.2 %), so read the saved profile's root arc back after the
    # equation-driven rebuild (codjiflo on PR #1989).
    _check_root_arc_sweep(adapter)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "handle axis")

    # Manufacturing drawing support: the model owns every printed band
    # (drawing-simplicity-policy.md `How the repository implements the guidelines`):
    # the root relief's, which keeps the root round behind the ferrule's seat
    # face and the ferrule its shoulder; and the places every mark prints
    # with.  The reamed bore, the tenon and the counterbore print as
    # references under their fit callouts; the two inside corners carry their
    # single MAX limit.
    set_dimension_symmetric_tolerance(
        adapter,
        "HandleProfile",
        "TenonRootRelief",
        TENON_ROOT_RELIEF_TOL,
        places=3,
        display_unit=UNIT,
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for name in ("TenonRootRadius", "CounterboreFloorRadius"):
        _inside_corner_max_limit(adapter, name)

    await apply_material(adapter, MATERIAL)
    # ch11 pp.20-21 + ch30 plates: the pear grip is EBONIZED (painted/stained
    # black, satin); the bright ferrule and cup are their own parts.
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
