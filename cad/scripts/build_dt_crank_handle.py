r"""Reproduction script: crank handle (book ch. 11, pp. 12-15).

The pear-shaped wooden handle (stained black) that rotates on the crank-arm
pivot -- the book calls it "a smooth piece of wood ... well-suited for a firm
grip" (p.12).  User ruling 2026-09-29 (the ch11 p.14/p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-DT-034 and the
bright disc at the butt a steel cup MHA-DT-035, so this oak body ends in a turned
tenon (the ferrule's seat) and a counterbore (the cup's seat).

User rulings 2026-09-30 (ch30 eight-views-4 side view, approved CadQuery
concept v4): five tangent arcs span the wood -- a concave flare from the
ferrule's OD down to a slim waist, an S-curve (concave then convex) up to the
Ø21 swell, a dome, and an end round that runs out on the counterbore mouth,
turned across the bonded cup at assembly.  Circumferentially smooth after the
revolve.

Layout: handle axis along +X; x=0 is the ferrule's arm face (the handle's
seat on the arm), so the oak starts at the tenon end, short of it.  One
revolve carries the tenon, the grip and the counterbore.  Every arc centre is
anchored, each tangency fixes the next radius, and the oak's overall from the
tenon end fixes where the end round meets the counterbore.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_crank_handle.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    apply_color,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties

PART_NAME = "dt-crank-handle"
MATERIAL = "Oak"  # see _common.apply_material docstring

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print).
from dt_crank_handle_spec import (  # noqa: E402
    COUNTERBORE_DEPTH,
    COUNTERBORE_DIA,
    COUNTERBORE_FLOOR_X,
    COUNTERBORE_R,
    DOME_CENTER,
    DOME_END,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    END_ROUND_CENTER,
    FERRULE_LENGTH,
    FLARE_CENTER,
    INFLECTION,
    ISOMETRIC_VIEW_NOTE,
    OAK_END_X,
    PEAK_R,
    PEAK_X,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
    S_CONCAVE_CENTER,
    S_CONVEX_CENTER,
    SHOULDER_R,
    SHOULDER_X,
    TENON_DIA,
    TENON_LENGTH,
    TENON_R,
    TENON_X0,
    WAIST_R,
    WAIST_X,
    WOOD_LENGTH,
    profile_radius,
)

# The peak-station witness stands inside the swell, clear of the profile.
_WITNESS_Y0, _WITNESS_Y1 = 2.5, 3.5


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
    return grip + tenon - counterbore - bore


V_HANDLE = _nominal_volume()

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.  The arc centres are closed forms of several knobs, so
    # their coordinates stay static.
    for name, value in (
        ("FerruleLength", FERRULE_LENGTH),
        ("TenonLength", TENON_LENGTH),
        ("TenonDia", TENON_DIA),
        ("ShoulderR", SHOULDER_R),
        ("PeakX", PEAK_X),
        ("WoodLength", WOOD_LENGTH),
        ("CounterboreDia", COUNTERBORE_DIA),
        ("CounterboreDepth", COUNTERBORE_DEPTH),
        ("PivotBoreDia", PIVOT_BORE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    shoulder_pt = (SHOULDER_X, SHOULDER_R)
    waist_pt = (WAIST_X, WAIST_R)
    peak_pt = (PEAK_X, PEAK_R)
    oak_end_pt = (OAK_END_X, COUNTERBORE_R)
    crest_pt = (OAK_END_X, END_ROUND_CENTER[1])

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the shallow arcs to auto relations.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(TENON_X0, 0.0, COUNTERBORE_FLOOR_X, 0.0),
    )
    # Tenon: end face -> OD -> shoulder step up to the ferrule's OD.
    tenon_end, tenon_top, shoulder = await add_line_chain(
        adapter,
        [(TENON_X0, 0.0), (TENON_X0, TENON_R), (SHOULDER_X, TENON_R), shoulder_pt],
        close=False,
    )
    # add_arc sweeps CCW from start to end; each is ordered so the sweep is the
    # minor arc on the silhouette side.  Concave arcs (centre above) run left
    # to right under their centre; convex ones (centre below) right to left.
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
    # Crest -> flat oak end face -> counterbore wall -> counterbore floor ->
    # axis closure.
    oak_end_face, counterbore_wall, counterbore_floor, _closure = await add_line_chain(
        adapter,
        [
            crest_pt,
            oak_end_pt,
            (COUNTERBORE_FLOOR_X, COUNTERBORE_R),
            (COUNTERBORE_FLOOR_X, 0.0),
            (TENON_X0, 0.0),
        ],
        close=False,
    )
    # Construction-only witness line inside the swell, clear of the profile
    # and the axis so it inherits no relations.
    peak_station = check(
        "peak station construction line",
        await adapter.add_centerline(PEAK_X, _WITNESS_Y0, PEAK_X, _WITNESS_Y1),
    )
    set_sketch_direct_db(adapter, False)

    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    for label, entity, relation in (
        ("tenon end", tenon_end, "vertical"),
        ("tenon OD", tenon_top, "horizontal"),
        ("tenon shoulder", shoulder, "vertical"),
        ("oak end face", oak_end_face, "vertical"),
        ("counterbore wall", counterbore_wall, "horizontal"),
        ("counterbore floor", counterbore_floor, "vertical"),
        ("peak station", peak_station, "vertical"),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    # Dimensions in creation order; SketchDims renames them by that order.
    await anchor_point_to_origin(
        adapter, f"{tenon_end}.start", TENON_X0, 0.0, "tenon end on the axis"
    )
    profile.record("TenonStart", '"FerruleLength" - "TenonLength"')
    check(
        "tenon length",
        await adapter.add_sketch_dimension(tenon_top, None, "linear", TENON_LENGTH),
    )
    profile.record("TenonLength", '"TenonLength"')
    await add_diametric_linear_dimension(
        adapter,
        centerline,
        tenon_top,
        ((TENON_X0 + SHOULDER_X) / 2.0, TENON_R + 4.0),
        "TenonDia",
    )
    profile.record("TenonDia", '"TenonDia"')
    check(
        "shoulder step",
        await adapter.add_sketch_dimension(shoulder, None, "linear", SHOULDER_R - TENON_R),
    )
    profile.record("ShoulderStep", '"ShoulderR" - "TenonDia" / 2')
    # The oak overall, tenon end face to the oak's end at the counterbore
    # mouth: every axial station reads from the tenon end, the one faced end.
    await dimension_between(
        adapter,
        f"{tenon_end}.end",
        f"{counterbore_wall}.start",
        "horizontal_distance",
        OAK_END_X - TENON_X0,
        "oak overall from the tenon end",
    )
    profile.record("OverallLength", '"TenonLength" + "WoodLength"')
    check(
        "counterbore depth",
        await adapter.add_sketch_dimension(
            counterbore_wall, None, "linear", COUNTERBORE_DEPTH
        ),
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
    # The peak station prints from the tenon end face too.
    await anchor_point_to_point(
        adapter,
        f"{tenon_end}.end",
        f"{peak_station}.start",
        PEAK_X - TENON_X0,
        _WITNESS_Y0 - TENON_R,
        "peak station from the tenon end",
    )
    profile.record("PeakStation", '"PeakX" - "FerruleLength" + "TenonLength"')
    profile.record(None, None)
    check(
        "peak witness construction length",
        await adapter.add_sketch_dimension(
            peak_station, None, "linear", _WITNESS_Y1 - _WITNESS_Y0
        ),
    )
    profile.record(None, None)
    # Arc centres: each anchored by a horizontal and a vertical distance from
    # the origin.  The two swell centres sit on the peak station ("PeakX"); the
    # rest are closed forms of several knobs and stay static.  The end round's
    # centre is anchored in height only: its tangency to the dome and the oak's
    # end point fix the rest.
    for arc, center, label, x_drive in (
        (flare, FLARE_CENTER, "flare centre", None),
        (s_concave, S_CONCAVE_CENTER, "S concave centre", None),
        (s_convex, S_CONVEX_CENTER, "S convex centre", '"PeakX"'),
        (dome, DOME_CENTER, "dome centre", '"PeakX"'),
    ):
        await anchor_point_to_origin(adapter, f"{arc}.center", *center, label)
        profile.record(None if x_drive is None else f"{label.title().replace(' ', '')}X", x_drive)
        profile.record(None, None)
    await dimension_between(
        adapter,
        f"{tenon_end}.start",
        f"{end_round}.center",
        "vertical_distance",
        END_ROUND_CENTER[1],
        "end round centre height",
    )
    profile.record(None, None)
    for first, second, label in (
        (flare, s_concave, "waist"),
        (s_concave, s_convex, "inflection"),
        (s_convex, dome, "swell"),
        (dome, end_round, "end round"),
        (end_round, oak_end_face, "end round crest"),
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

    # Axial running bore through the grip. The Right plane is normal to the
    # handle's +X turning axis, so this cut is coaxial with the revolve and its
    # true-circle end view gives the drawing an inspectable bore callout.
    bore = SketchDims()
    check("create_sketch pivot bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        PIVOT_BORE_DIA / 2.0,
        "pivot bore",
        dims=bore,
        names=("PivotBoreCy", "PivotBoreCz", "PivotBoreDia"),
        drives=(None, None, '"PivotBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pivot bore sketch")
    check("exit_sketch pivot bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotBoreProfile")
    drive_jobs += bore.apply(adapter, "PivotBoreProfile")
    check(
        "cut pivot bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * OAK_END_X, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotBore")
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

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "handle axis")

    # Manufacturing drawing support: the model owns the one printed band
    # (policy rule 2), the reamed bore, and the places every mark prints with.
    # The tenon and the counterbore are fitted to the parts they take.
    set_dimension_bilateral_tolerance(
        adapter,
        "PivotBoreProfile",
        "PivotBoreDia",
        *deviations(PIVOT_BORE_BAND),
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    await apply_material(adapter, MATERIAL)
    # ch11 pp.20-21 + ch30 plates: the pear grip is EBONIZED (painted/stained
    # black, satin); the bright ferrule and cup are their own parts.
    await apply_color(adapter, PANEL_BLACK)
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
