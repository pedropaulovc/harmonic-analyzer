r"""Build MHA-160, the transgear hub cap (contract §2.2, ruling R9-5).

A brass cap nut on the stud's #6-32 front thread; its plain rear face seats
on the stud's journal shoulder.  Dimensions and the derived fit facts live in
``transgear_hub_cap_spec``.

Layout: axis local +Z toward the machine front, origin on the rear face (the
Front Plane).

* ``CapProfile``: one revolve on the Right plane with the 45° front O.D.
  break in the profile.
* ``ThreadBore``: #6-32 UNC-2B through, Hole Wizard from the rear face.
* ``Countersink``: the 90° front entry countersink, a revolved cut.
* ``SpannerHoles``: two drilled blind holes on local ±Y, cut from the
  ``FrontFace`` plane.

``FrontFace`` (z 5.80) and ``Axis1`` serve the assembly mates; the rear face
is the Front Plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_hub_cap.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    _named_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _fit_limits import deviations
from _holes import wizard_holes
from _visibility import blank_reference_geometry
from transgear_hub_cap_spec import (
    CAP_DIA,
    CAP_LENGTH,
    CSK_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FRONT_CHAMFER,
    FRONT_CHAMFER_BAND,
    FRONT_CHAMFER_TOL_TYPE,
    ISOMETRIC_VIEW_NOTE,
    SPANNER_HOLE_DEPTH,
    SPANNER_HOLE_DIA,
    SPANNER_HOLE_R,
    SPANNER_HOLE_SPACING,
    TAP_DRILL_DIA,
    TAP_SPEC,
)

PART_NAME = "transgear-hub-cap"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

CAP_R = CAP_DIA / 2.0
CSK_R = CSK_DIA / 2.0
DRILL_R = TAP_DRILL_DIA / 2.0
HOLE_R = SPANNER_HOLE_DIA / 2.0
# How far the countersink cutter runs past the front face into air.
_CSK_OVERRUN = 1.0

V_PROFILE = math.pi * CAP_R**2 * CAP_LENGTH - math.pi * FRONT_CHAMFER**2 * (
    CAP_R - FRONT_CHAMFER / 3.0
)
V_THREAD = math.pi * DRILL_R**2 * CAP_LENGTH
# The cone r = s (s from the apex, 0..CSK_R) less what the drill already took.
V_CSK = math.pi * (CSK_R**3 - DRILL_R**3) / 3.0 - math.pi * DRILL_R**2 * (
    CSK_R - DRILL_R
)
V_SPANNER_HOLES = 2.0 * math.pi * HOLE_R**2 * SPANNER_HOLE_DEPTH
V_TOTAL = V_PROFILE - V_THREAD - V_CSK - V_SPANNER_HOLES


def _chamfer_max_limit(adapter) -> None:
    """FrontChamfer as a MAX single limit carrying the band's deviations."""
    lower, upper = deviations(FRONT_CHAMFER_BAND)
    _, dimension = _named_dimension(adapter, "CapProfile", "FrontChamfer")
    label = "FrontChamfer@CapProfile"
    # Driven by a global the build writes in inches to 8 decimals, so match at
    # the 1e-9 m every other readback uses.
    value = float(dimension.SystemValue)
    if not math.isclose(value, FRONT_CHAMFER / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {value * 1000.0:.7f} is not the band's max {FRONT_CHAMFER}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = FRONT_CHAMFER_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != FRONT_CHAMFER_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {FRONT_CHAMFER:g} MAX")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())
    # The mm suffix is load-bearing: the equation manager reads bare numbers in
    # document units (see build_crankshaft).
    for name, value in (
        ("CapDia", CAP_DIA),
        ("CapLength", CAP_LENGTH),
        ("FrontChamfer", FRONT_CHAMFER),
        ("SpannerHoleDia", SPANNER_HOLE_DIA),
        ("SpannerHoleSpacing", SPANNER_HOLE_SPACING),
        ("SpannerHoleDepth", SPANNER_HOLE_DEPTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Body: one revolve with the front O.D. break ------------------------
    # Right sketch (u, v) maps to model (-Z, Y): the rear face sits on the
    # origin and negative u runs toward the front face (model +Z).
    points = [
        (0.0, 0.0),
        (0.0, CAP_R),
        (-(CAP_LENGTH - FRONT_CHAMFER), CAP_R),
        (-CAP_LENGTH, CAP_R - FRONT_CHAMFER),
        (-CAP_LENGTH, 0.0),
    ]
    profile = SketchDims()
    check("create_sketch cap profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "cap axis centerline", await adapter.add_centerline(0.0, 0.0, -CAP_LENGTH, 0.0)
    )
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    rear_face, outline, chamfer, front_face, axis_edge = lines
    for line, relation in (
        (rear_face, "vertical"),
        (outline, "horizontal"),
        (front_face, "vertical"),
        (axis_edge, "horizontal"),
    ):
        check(
            f"cap profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await dimension_between(
        adapter,
        f"{rear_face}.start",
        f"{front_face}.end",
        "horizontal_distance",
        CAP_LENGTH,
        "cap CapLength",
    )
    profile.record("CapLength", '"CapLength"')
    # The chamfer's axial leg prints; its radial leg equals it by equation.
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        FRONT_CHAMFER,
        "cap FrontChamfer",
    )
    profile.record("FrontChamfer", '"FrontChamfer"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "vertical_distance",
        FRONT_CHAMFER,
        "cap front chamfer rise",
    )
    profile.record("FrontChamferRise", '"FrontChamfer"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-CAP_LENGTH / 2.0, CAP_R + 4.0), "CapDia"
    )
    profile.record("CapDia", '"CapDia"')
    await anchor_point_to_origin(
        adapter, f"{rear_face}.start", 0.0, 0.0, "cap rear face centre"
    )
    await ensure_fully_defined(adapter, "cap profile sketch")
    check("exit_sketch cap profile", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += profile.apply(adapter, "CapProfile")
    check("revolve cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cap")
    volume = await volume_check(adapter, "chamfered cap", V_PROFILE, 0.005 * V_PROFILE)

    # --- #6-32 UNC-2B through, from the plain rear face ---------------------
    # Drilled while the front face is still whole, so the removed volume is
    # the plain tap-drill cylinder.
    thread = wizard_holes(
        adapter,
        TAP_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, 0.0, -1.0),
        f"hub cap thread ({TAP_SPEC.size} through)",
        name="ThreadBore",
        expect_dia_mm=TAP_DRILL_DIA,
        placement_dims=[((None, None), (None, None))],
    )
    drive_jobs += thread.placement_drive_jobs
    volume = await volume_check(
        adapter, "tapped through", volume - V_THREAD, 0.02 * V_THREAD
    )

    # --- 90° front entry countersink: one revolved cut ----------------------
    # The region in front of the cone z = apex + r, apex on the axis CSK_R
    # behind the front face; the triangle's far edge lies in air.
    reach = CSK_R + _CSK_OVERRUN
    apex_u = -(CAP_LENGTH - CSK_R)
    csk = [
        (apex_u, 0.0),
        (apex_u - reach, reach),
        (apex_u - reach, 0.0),
    ]
    check("create_sketch countersink", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check(
        "countersink axis",
        await adapter.add_centerline(apex_u, 0.0, apex_u - reach, 0.0),
    )
    csk_lines = await add_line_chain(adapter, csk)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, csk_lines, csk, label="front countersink")
    await ensure_fully_defined(adapter, "countersink profile")
    check("exit_sketch countersink", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkProfile")
    check(
        "revolve countersink",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Countersink")
    volume = await volume_check(
        adapter, "front countersink", volume - V_CSK, 0.03 * V_CSK + 0.05
    )

    # --- Front face station and the spanner holes ----------------------------
    check(
        f"create_plane FrontFace (Front Plane + {CAP_LENGTH:g})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=CAP_LENGTH
            )
        ),
    )
    name_last_feature(adapter, "FrontFace")
    front_offset = name_dimensions(adapter, "FrontFace", ["FrontFaceOffset"])
    drive_jobs.append((front_offset[0], '"CapLength"'))
    blank_reference_geometry(adapter, (("FrontFace", "PLANE"),))

    # Two blind drilled holes on local ±Y (the Right plane, so the axial
    # section cuts both), spaced centre to centre; a Front-parallel sketch
    # reads (x, y) = (X, Y).  A cut's default runs opposite the sketch normal,
    # i.e. from the front face back into the cap (the volume gate fails loud
    # on a wrong-side cut).
    holes = SketchDims()
    check("create_sketch spanner holes", await adapter.create_sketch("FrontFace"))
    lower = await define_circle(
        adapter,
        0.0,
        -SPANNER_HOLE_R,
        HOLE_R,
        "spanner hole -Y",
        dims=holes,
        names=(None, "SpannerHoleHalf", "SpannerHoleDia"),
        drives=(None, '"SpannerHoleSpacing" / 2', '"SpannerHoleDia"'),
    )
    set_sketch_direct_db(adapter, True)
    upper = check(
        "spanner hole +Y",
        await adapter.add_circle(0.0, SPANNER_HOLE_R, HOLE_R),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "spanner holes on one diameter",
        await adapter.add_sketch_constraint(
            f"{upper}.center", f"{lower}.center", "vertical_points"
        ),
    )
    check(
        "spanner holes equal",
        await adapter.add_sketch_constraint(upper, lower, "equal"),
    )
    await dimension_between(
        adapter,
        f"{lower}.center",
        f"{upper}.center",
        "vertical_distance",
        SPANNER_HOLE_SPACING,
        "spanner hole spacing",
    )
    holes.record("SpannerHoleSpacing", '"SpannerHoleSpacing"')
    await ensure_fully_defined(adapter, "spanner hole sketch")
    check("exit_sketch spanner holes", await adapter.exit_sketch())
    name_last_feature(adapter, "SpannerHoleProfile")
    drive_jobs += holes.apply(adapter, "SpannerHoleProfile")
    check(
        "cut spanner holes",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SPANNER_HOLE_DEPTH)),
    )
    name_last_feature(adapter, "SpannerHoles")
    depth_dim = name_dimensions(adapter, "SpannerHoles", ["SpannerHoleDepth"])
    drive_jobs.append((depth_dim[0], '"SpannerHoleDepth"'))
    volume = await volume_check(
        adapter, "spanner holes", volume - V_SPANNER_HOLES, 0.05 * V_SPANNER_HOLES
    )

    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "cap axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cap (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )

    # The chamfer's single MAX limit keeps its inner edge off the spanner
    # holes (the spec's CHAMFER_INNER_EDGE_R_MIN check).
    _chamfer_max_limit(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
