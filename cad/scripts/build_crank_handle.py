r"""Reproduction script: crank handle (book ch. 11, pp. 12-15).

The pear-shaped wooden handle (stained black) that rotates on the crank-arm
pivot -- the book calls it "a smooth piece of wood ... well-suited for a firm
grip" (p.12).  User ruling 2026-09-29 (the ch11 p.14/p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-150 and the
bright disc at the butt a flanged steel cup MHA-153, so this oak body ends in
a turned tenon (the ferrule's seat) and a trimmed butt face with a
counterbore (the cup's seat).

Two internally-tangent circular arcs span the wood body: a long, gentle front
arc swells from the neck to the maximum diameter, and a tighter rear arc
rounds off toward the butt, trimmed where the cup flange seats.  The arcs
share a horizontal tangent at the swell, so the wood reads as one continuous
curve.  Circumferentially smooth after the revolve.

Dimensions: crank_handle_spec (2026-09-02 user re-read of ch11 p.14 + the
ch30 p002 front view) -- 58 basic from the ferrule's arm face to the cup's
flange face x Ø21 max at the swell; photo-scaled (low).

Layout: handle axis along +X; x=0 is the ferrule's arm face (the handle's
seat on the arm), so the oak starts at the tenon end, short of it.  One
revolve carries the tenon, the pear and the counterbore.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_handle.py
"""

from __future__ import annotations

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
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _saved_part_guard import require_saved_drawing_properties

PART_NAME = "crank-handle"
MATERIAL = "Oak"  # see _common.apply_material docstring

# Primitive nominals come from the drawing spec (single source of truth shared
# with the manufacturing print).
from crank_handle_spec import (  # noqa: E402
    COUNTERBORE_DEPTH,
    COUNTERBORE_DIA,
    COUNTERBORE_DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FERRULE_LENGTH,
    FRONT_PROFILE_R,
    HANDLE_MAX_DIA,
    ISOMETRIC_VIEW_NOTE,
    NECK_R,
    PEAK_X,
    PIVOT_BORE_BAND,
    PIVOT_BORE_DIA,
    REAR_PROFILE_CY,
    REAR_PROFILE_R,
    SHOULDER_X,
    TENON_DIA,
    TENON_DIA_TOL,
    TENON_LENGTH,
    TENON_X0,
    TRIM_R,
    TRIM_X,
    WOOD_LENGTH,
    WOOD_LENGTH_BAND,
)

PEAK_R = HANDLE_MAX_DIA / 2.0
TENON_R = TENON_DIA / 2.0
COUNTERBORE_R = COUNTERBORE_DIA / 2.0
COUNTERBORE_FLOOR_X = TRIM_X - COUNTERBORE_DEPTH

_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# Smooth pear silhouette = two circular arcs that meet at the swell (PEAK_X,
# PEAK_R) with a common horizontal tangent (both centres sit directly below
# the swell on x = PEAK_X), so the join is curvature-side-consistent and the
# wood is tangent-continuous from neck to butt.
#   front arc: through the neck at the tenon shoulder (SHOULDER_X, NECK_R).
#   rear arc : through the swell, trimmed at the butt face (TRIM_X, TRIM_R).
FRONT_R = FRONT_PROFILE_R
FRONT_CY = PEAK_R - FRONT_R
REAR_R = REAR_PROFILE_R
REAR_CY = REAR_PROFILE_CY
# Both circles pass through the swell apex (their common top point) and share
# x = PEAK_X centres -> they are internally tangent there (|ΔCY| == ΔR):
assert abs(abs(FRONT_CY - REAR_CY) - abs(FRONT_R - REAR_R)) < 1e-6
# The peak-station witness stands inside the swell, clear of the profile.
_WITNESS_Y0, _WITNESS_Y1 = 2.0, 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the handle's design constants as named
    # globals driving the dimensions below. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units, so an unsuffixed 90 would be read as 90 inches and blow the
    # part up 25.4x. The two arc radii/centres are a non-trivial closed form of
    # these knobs (R = (dx^2 + dh^2) / 2dh); their depths stay static.
    for name, value in (
        ("FerruleLength", FERRULE_LENGTH),
        ("TenonLength", TENON_LENGTH),
        ("TenonDia", TENON_DIA),
        ("NeckR", NECK_R),
        ("PeakX", PEAK_X),
        ("WoodLength", WOOD_LENGTH),
        ("CounterboreDia", COUNTERBORE_DIA),
        ("CounterboreDepth", COUNTERBORE_DEPTH),
        ("PivotBoreDia", PIVOT_BORE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    # Per-sketch SketchDims records each dim in emission order; apply() renames
    # them and collects the drive jobs run in one deferred batch at the end (every
    # equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the shallow front arc / tenon
    # shoulder to auto relations (see crank pin lesson).
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(TENON_X0, 0.0, COUNTERBORE_FLOOR_X, 0.0),
    )
    # Tenon: end face -> OD -> shoulder step up to the neck.
    tenon_end, tenon_top, shoulder = await add_line_chain(
        adapter,
        [
            (TENON_X0, 0.0),
            (TENON_X0, TENON_R),
            (SHOULDER_X, TENON_R),
            (SHOULDER_X, NECK_R),
        ],
        close=False,
    )
    # add_arc draws CCW from start to end; order each so the CCW sweep is the
    # minor (silhouette) arc over the top of its big circle.
    front_arc = check(
        "front swell arc",
        await adapter.add_arc(PEAK_X, FRONT_CY, PEAK_X, PEAK_R, SHOULDER_X, NECK_R),
    )
    rear_arc = check(
        "rear butt arc",
        await adapter.add_arc(PEAK_X, REAR_CY, TRIM_X, TRIM_R, PEAK_X, PEAK_R),
    )
    # Butt trim face -> counterbore wall -> counterbore floor -> axis closure.
    butt_face, counterbore_wall, counterbore_floor, _closure = await add_line_chain(
        adapter,
        [
            (TRIM_X, TRIM_R),
            (TRIM_X, COUNTERBORE_R),
            (COUNTERBORE_FLOOR_X, COUNTERBORE_R),
            (COUNTERBORE_FLOOR_X, 0.0),
            (TENON_X0, 0.0),
        ],
        close=False,
    )
    # Construction-only witness line inside the visible swell.  Keep both ends
    # clear of the profile and axis: a line that touches the already-constrained
    # arc join or axis inherits coincident relations and makes its peak-station
    # dimension redundant/over-defining in SolidWorks.
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
        ("butt face", butt_face, "vertical"),
        ("counterbore wall", counterbore_wall, "horizontal"),
        ("counterbore floor", counterbore_floor, "vertical"),
        ("peak station", peak_station, "vertical"),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    # Dimensions in creation order; SketchDims renames them by that order.
    # The tenon's end sits TenonLength short of the shoulder, FerruleLength from
    # the arm face at x=0.
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
        await adapter.add_sketch_dimension(shoulder, None, "linear", NECK_R - TENON_R),
    )
    profile.record("ShoulderStep", '"NeckR" - "TenonDia" / 2')
    # Wood from the shoulder's outer corner to the butt face's outer corner:
    # both on the silhouette, so the print's extension lines leave real edges.
    await dimension_between(
        adapter,
        f"{shoulder}.end",
        f"{butt_face}.start",
        "horizontal_distance",
        WOOD_LENGTH,
        "wood length from the tenon shoulder",
    )
    profile.record("WoodLength", '"WoodLength"')
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
    # The peak station prints from the tenon shoulder (datum B).
    await anchor_point_to_point(
        adapter,
        f"{shoulder}.end",
        f"{peak_station}.start",
        PEAK_X - SHOULDER_X,
        _WITNESS_Y0 - NECK_R,
        "peak station from the tenon shoulder",
    )
    profile.record("PeakStation", '"PeakX" - "FerruleLength"')
    profile.record(None, None)
    check(
        "peak witness construction length",
        await adapter.add_sketch_dimension(
            peak_station, None, "linear", _WITNESS_Y1 - _WITNESS_Y0
        ),
    )
    profile.record(None, None)
    # Each arc centre is off-axis (PEAK_X != 0, *_CY < 0): anchor_point_to_origin
    # emits a horizontal then a vertical distance dim. The horizontal span is
    # PEAK_X (clean knob -> "PeakX"); the vertical span is the arc-centre depth
    # |*_CY|, a non-trivial closed form of several knobs with no single-global
    # expression, so it stays auto-named/static (None). The depth is a NEGATIVE
    # coordinate displayed as its magnitude -- recorded with no drive, so the
    # unsigned-distance trap (a negative drive failing at equation-add) can't bite.
    await anchor_point_to_origin(
        adapter, f"{front_arc}.center", PEAK_X, FRONT_CY, "front arc centre"
    )
    profile.record("FrontArcCx", '"PeakX"')
    profile.record(None, None)
    await anchor_point_to_origin(
        adapter, f"{rear_arc}.center", PEAK_X, REAR_CY, "rear arc centre"
    )
    profile.record("RearArcCx", '"PeakX"')
    profile.record(None, None)
    check(
        "swell tangent",
        await adapter.add_sketch_constraint(front_arc, rear_arc, "tangent"),
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
            ExtrusionParameters(depth=2.5 * TRIM_X, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotBore")

    # Capture the as-built volume as the neutrality reference (the bored,
    # revolved twin-arc silhouette has no tidy closed form), then apply the deferred drive
    # equations after the model + a rebuild exists so every target resolves. Each
    # equation evaluates to the value just built, so the geometry must not move.
    mass = await adapter.get_mass_properties()
    v_handle = float(mass.data.volume)
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven crank handle (equations neutral)", v_handle, 0.001 * v_handle
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "handle axis")

    # Manufacturing drawing support: the model owns every printed band (policy
    # rule 2) -- the wood length, the two epoxy-fit diameters and the reamed
    # bore -- and the places they print with.
    set_dimension_bilateral_tolerance(
        adapter, "HandleProfile", "WoodLength", *deviations(WOOD_LENGTH_BAND)
    )
    set_dimension_symmetric_tolerance(adapter, "HandleProfile", "TenonDia", TENON_DIA_TOL)
    set_dimension_bilateral_tolerance(
        adapter, "HandleProfile", "CounterboreDia", *deviations(COUNTERBORE_DIA_BAND)
    )
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
    # black, satin); the bright ferrule and cup are their own parts now.
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
