r"""Reproduction script: magnifying wheel (book ch. 21, pp. 50-53).

A gray cast-iron spider: a turned Ø100 rim on six tapered cast spokes and a
turned Ø25 hub boss. The boss carries an integral Ø14.5 spigot on its front
(pen) side, on which the MHA-MG-010 brass drum is pressed. The lever wire wraps
the drum, the pen wire runs in the rim's U-groove: the wire-centre radii
49.2 / 9.85 give the wheel's 5x magnification. TIE 1 (lever wire) is an axial
hole through the boss on the drum's wire-centre radius; TIE 2 (pen wire) is a
radial hole from the groove bottom to the rim bore.

Layout: wheel axis = local Z through the origin, the origin on the spokes' and
rim's mid-plane (``mg_magnifying_wheel_geom``). The hub profile and the groove
are revolved on the Right plane (sketch x -> model -Z).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_magnifying_wheel.py
"""

from __future__ import annotations

import math
import sys

from _appearance import PANEL_BLACK, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import measure_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle

import _telemetry
from _drawing_marks import (
    add_angular_reference_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _visibility import blank_reference_geometry
from mg_magnifying_wheel_geom import (
    BORE_BAND,
    BORE_DIA,
    CAST_ROUND_BAND,
    CAST_ROUND_R,
    GROOVE_BOTTOM_BAND,
    GROOVE_BOTTOM_DIA,
    GROOVE_R,
    GROOVE_R_BAND,
    HUB_BACK_Z,
    HUB_DIA,
    HUB_DIA_BAND,
    HUB_FILLET_R,
    HUB_FRONT_Z,
    HUB_LEN,
    HUB_LEN_BAND,
    HUB_STEP_Z,
    RIM_AXIAL,
    RIM_FILLET_R,
    RIM_INNER_DIA,
    RIM_OUTER_DIA,
    RIM_RING_RADIAL,
    SPIGOT_BAND,
    SPIGOT_DIA,
    SPIGOT_LEN,
    SPIGOT_LEN_BAND,
    SPOKE_AXIAL,
    SPOKE_COUNT,
    SPOKE_OVERLAP,
    SPOKE_ROOT_WIDTH,
    SPOKE_TIP_WIDTH,
    SPOKE_X0,
    SPOKE_X1,
    TIE1_CLOCK_DEG,
    TIE1_R,
    TIE2_CLOCK_DEG,
    TIE_HOLE_BAND,
    TIE_HOLE_DIA,
    TIE_POSITION_TOL,
    clock_to_local_deg,
    fillet_area,
    fillets_volume,
    side_meets_circle,
    spoke_half_width,
)
from mg_magnifying_wheel_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    SECTION_VIEW_NOTE,
)

PART_NAME = "mg-magnifying-wheel"
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

# Wheel nominals live in mg_magnifying_wheel_geom (imported above).

# --- WIRE-1 yoke point (the coupling mate's wheel-side geometry) --------------
# ``WireYokePoint``: a reference point on the hub PITCH circle (groove radius +
# wire radius) at the lever-wire's tangency azimuth, in the wheel mid-plane. The
# magnifier assembly holds it COINCIDENT to the lever-wire's YokePlane, tying the
# wheel's spin to the lever group's travel along the wire (the linearized
# inextensible-wire constraint -- see build_mg_lever_wire's docstring). The azimuth
# is layout-derived, so it is imported from mg_lever_wire_geom: a layout move
# re-tangents the wire AND re-stamps this point in one rebuild.
from mg_lever_wire_geom import (  # noqa: E402
    WHEEL_BAR_Y as _YOKE_WHEEL_Y,
    WHEEL_X as _YOKE_WHEEL_X,
    YOKE_POINT as _YOKE_POINT,
)

# The wheel is placed at IDENTITY, so the yoke point's local offset IS the
# machine offset from the wheel centre. (Pre-#151 this was authored x-NEGATED
# to survive the chirality mirror's double flip -- the imported tangency
# azimuth was itself in the mirrored frame, so the two negations cancelled to
# the same +10.1225 the machine-handed layout gives directly.)
YOKE_LOCAL_X = _YOKE_POINT[0] - _YOKE_WHEEL_X
YOKE_LOCAL_Y = _YOKE_POINT[1] - _YOKE_WHEEL_Y

# --- Feature volumes (mm^3), one gate per feature ---------------------------------
_RIM_R = RIM_OUTER_DIA / 2.0
_RIM_IN_R = RIM_INNER_DIA / 2.0
_HUB_R = HUB_DIA / 2.0
_SPIGOT_R = SPIGOT_DIA / 2.0
_BORE_R = BORE_DIA / 2.0
_TIE_R = TIE_HOLE_DIA / 2.0
_GROOVE_CENTRE_R = GROOVE_BOTTOM_DIA / 2.0 + GROOVE_R  # 49.4
# The groove walls run past the rim OD so the cut opens cleanly.
_GROOVE_TOP_R = _RIM_R + 0.5
_BOSS_LEN = HUB_LEN - SPIGOT_LEN  # 10.6, back face to the step


def _spoke_area(r_in: float, r_out: float, steps: int = 20000) -> float:
    """Seed-spoke trapezoid area between the circles ``r_in`` and ``r_out``."""
    dx = (SPOKE_X1 - SPOKE_X0) / steps
    area = 0.0
    for i in range(steps):
        x = SPOKE_X0 + (i + 0.5) * dx
        half = spoke_half_width(x)
        y_out = math.sqrt(max(0.0, r_out * r_out - x * x))
        y_in = math.sqrt(max(0.0, r_in * r_in - x * x))
        area += 2.0 * max(0.0, min(half, y_out) - y_in) * dx
    return area


def _tie2_volume(steps: int = 400) -> float:
    """Rim material the radial TIE 2 hole removes: groove floor to rim bore,
    over the hole's disc (tangential u, axial v)."""
    d = TIE_HOLE_DIA / steps
    total = 0.0
    for i in range(steps):
        u = -_TIE_R + (i + 0.5) * d
        for j in range(steps):
            v = -_TIE_R + (j + 0.5) * d
            if u * u + v * v > _TIE_R * _TIE_R:
                continue
            floor = _GROOVE_CENTRE_R - math.sqrt(GROOVE_R * GROOVE_R - v * v)
            outer = math.sqrt(floor * floor - u * u)
            inner = math.sqrt(_RIM_IN_R * _RIM_IN_R - u * u)
            total += max(0.0, outer - inner) * d * d
    return total


V_RIM = math.pi * (_RIM_R**2 - _RIM_IN_R**2) * RIM_AXIAL
V_SPOKE_FREE = SPOKE_AXIAL * _spoke_area(0.0, _RIM_IN_R)  # before the hub exists
V_SPOKE_WEB = SPOKE_AXIAL * _spoke_area(_HUB_R, _RIM_IN_R)  # outside the hub
V_HUB = math.pi * (_HUB_R**2 * _BOSS_LEN + _SPIGOT_R**2 * SPIGOT_LEN)
V_BORE = math.pi * _BORE_R**2 * HUB_LEN
V_HUB_FILLETS = 2 * SPOKE_COUNT * SPOKE_AXIAL * fillet_area(_HUB_R, HUB_FILLET_R, True)
V_RIM_FILLETS = (
    2 * SPOKE_COUNT * SPOKE_AXIAL * fillet_area(_RIM_IN_R, RIM_FILLET_R, False)
)
if abs(V_HUB_FILLETS + V_RIM_FILLETS - fillets_volume()) > 1e-6:
    raise AssertionError("fillet gates do not sum to the geom's fillets_volume()")
# Each R1 round removes a spandrel (1 - pi/4) R^2 swept about the axis at its
# centroid, 0.2234 R in from the rim-bore corner (Pappus).
_SPANDREL_OFFSET = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi) * CAST_ROUND_R
V_ROUNDS = (
    2
    * (1.0 - math.pi / 4.0)
    * CAST_ROUND_R**2
    * 2.0
    * math.pi
    * (_RIM_IN_R + _SPANDREL_OFFSET)
)
# The U-groove: the band from its centre circle to the OD plus the round
# bottom's half disc, each swept about the axis at its centroid (Pappus).
_GROOVE_BAND = 2.0 * GROOVE_R * (_RIM_R - _GROOVE_CENTRE_R)
_GROOVE_HALF_DISC = math.pi * GROOVE_R**2 / 2.0
V_GROOVE = (
    2.0
    * math.pi
    * (
        _GROOVE_BAND * (_RIM_R + _GROOVE_CENTRE_R) / 2.0
        + _GROOVE_HALF_DISC * (_GROOVE_CENTRE_R - 4.0 * GROOVE_R / (3.0 * math.pi))
    )
)
V_TIE1 = math.pi * _TIE_R**2 * _BOSS_LEN
V_TIE2 = _tie2_volume()

# --- TIE 2 profile: a half rectangle beside its radial axis, revolve-cut -------
# The axis runs radially at TIE2_CLOCK_DEG from inside the rim bore out past the
# groove floor. Its inner end runs HORIZONTAL (in the air inside the rim bore)
# so the hole's angle reads off it on the face view.
_TIE2_LOCAL = math.radians(clock_to_local_deg(TIE2_CLOCK_DEG))
_TIE2_U = (math.cos(_TIE2_LOCAL), math.sin(_TIE2_LOCAL))
_TIE2_W = (-_TIE2_U[1], _TIE2_U[0])
_TIE2_IN_R = _RIM_IN_R - 1.5  # the full bore starts inside the rim bore
_TIE2_OUT_R = _GROOVE_CENTRE_R + 0.1  # ends in the groove's air
_TIE2_ANGLE = math.degrees(math.atan2(abs(_TIE2_U[1]), abs(_TIE2_U[0])))
if abs(_TIE2_U[1]) < 1e-6 or abs(_TIE2_U[0]) < 1e-6:
    raise AssertionError("TIE 2 must run oblique to the sketch axes")
# The driven angle's text sits inside the ACUTE sector at P_in, between the
# axis (outward, along U) and the horizontal ray on the same x side as U --
# SolidWorks picks which of the four angles to report from the text point.
_TIE2_ANGLE_TEXT_R = 2.5
_TIE2_BISECTOR = (_TIE2_U[0] + math.copysign(1.0, _TIE2_U[0]), _TIE2_U[1])
_TIE2_ANGLE_TEXT = (
    _TIE2_IN_R * _TIE2_U[0]
    + _TIE2_ANGLE_TEXT_R * _TIE2_BISECTOR[0] / math.hypot(*_TIE2_BISECTOR),
    _TIE2_IN_R * _TIE2_U[1]
    + _TIE2_ANGLE_TEXT_R * _TIE2_BISECTOR[1] / math.hypot(*_TIE2_BISECTOR),
)


def _tie2_profile() -> list[tuple[float, float]]:
    """[P_in, P_out, Q_out, Q_in]: the axis, the outer end square to it, the
    hole's wall, and the horizontal inner end back to the axis."""
    p_in = (_TIE2_IN_R * _TIE2_U[0], _TIE2_IN_R * _TIE2_U[1])
    p_out = (_TIE2_OUT_R * _TIE2_U[0], _TIE2_OUT_R * _TIE2_U[1])
    q_out = (p_out[0] + _TIE_R * _TIE2_W[0], p_out[1] + _TIE_R * _TIE2_W[1])
    # The wall line meets the horizontal through P_in at t along U.
    t = -_TIE_R * _TIE2_W[1] / _TIE2_U[1]
    q_in = (
        p_in[0] + _TIE_R * _TIE2_W[0] + t * _TIE2_U[0],
        p_in[1] + _TIE_R * _TIE2_W[1] + t * _TIE2_U[1],
    )
    if math.hypot(*q_in) > _RIM_IN_R - 0.5:
        raise AssertionError("TIE 2's inner end must stay inside the rim bore")
    return [p_in, p_out, q_out, q_in]


async def _relate(adapter, rows) -> None:
    """Apply ``(label, first, second, relation)`` sketch relations."""
    for label, first, second, relation in rows:
        check(label, await adapter.add_sketch_constraint(first, second, relation))


async def _fillet(adapter, radius: float, picks, name: str, dim: str) -> None:
    check(f"fillet {name}", await adapter.add_fillet(radius, picks, propagate=False))
    name_last_feature(adapter, name)
    name_dimensions(adapter, name, [dim])


def _spoke_edge_picks(circle_r: float) -> list[list[float]]:
    """Mid-height points on each spoke side's junction edge with the circle."""
    x, y = side_meets_circle(circle_r)
    picks = []
    for k in range(SPOKE_COUNT):
        a = math.radians(k * 360.0 / SPOKE_COUNT)
        for py in (y, -y):
            picks.append(
                [
                    x * math.cos(a) - py * math.sin(a),
                    x * math.sin(a) + py * math.cos(a),
                    0.0,
                ]
            )
    return picks


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 100 = 100 in). SPOKE_COUNT is a pattern
    # instance count, not a sketch length, so it stays a Python constant.
    await set_global(adapter, "RimOuterDia", f"{RIM_OUTER_DIA}mm")
    await set_global(adapter, "RimRingRadial", f"{RIM_RING_RADIAL}mm")
    await set_global(adapter, "RimInnerDia", '"RimOuterDia" - 2 * "RimRingRadial"')
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "HubLength", f"{HUB_LEN}mm")
    await set_global(adapter, "HubBackZ", f"{HUB_BACK_Z}mm")
    await set_global(adapter, "SpigotDia", f"{SPIGOT_DIA}mm")
    await set_global(adapter, "SpigotLength", f"{SPIGOT_LEN}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "SpokeAxial", f"{SPOKE_AXIAL}mm")
    await set_global(adapter, "SpokeOverlap", f"{SPOKE_OVERLAP}mm")
    await set_global(adapter, "SpokeRootWidth", f"{SPOKE_ROOT_WIDTH}mm")
    await set_global(adapter, "SpokeTipWidth", f"{SPOKE_TIP_WIDTH}mm")
    await set_global(adapter, "SpokeX0", '"HubDia" / 2 - "SpokeOverlap"')
    await set_global(adapter, "SpokeX1", '"RimInnerDia" / 2 + "SpokeOverlap"')
    await set_global(adapter, "GrooveR", f"{GROOVE_R}mm")
    await set_global(adapter, "GrooveBottomDia", f"{GROOVE_BOTTOM_DIA}mm")
    await set_global(adapter, "TieHoleDia", f"{TIE_HOLE_DIA}mm")
    await set_global(adapter, "Tie1R", f"{TIE1_R}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rim ring (annulus, mid-plane symmetric). Two on-axis circles: each emits
    # only its diameter dim.
    rim_sd = SketchDims()
    check("create_sketch rim", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        _RIM_R,
        "rim OD",
        dims=rim_sd,
        names=("RimOdCx", "RimOdCz", "RimOuterDiaDim"),
        drives=(None, None, '"RimOuterDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        _RIM_IN_R,
        "rim ID",
        dims=rim_sd,
        names=("RimIdCx", "RimIdCz", "RimInnerDiaDim"),
        drives=(None, None, '"RimInnerDia"'),
    )
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    drive_jobs += rim_sd.apply(adapter, "RimProfile")
    check(
        "extrude rim",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIM_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Rim")
    volume = await volume_check(adapter, "rim", V_RIM, 0.002 * V_RIM)

    # Named wheel axis (local Z = Top x Right): the spoke pattern rotates about
    # it, and the M6 assembly mates the wheel on the axle by it. Created before
    # the pattern so the pattern selects it by name.
    wheel_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "wheel axis"
    )

    # Seed spoke along +X, tapering from the root (inside the hub's circle) to
    # the tip (inside the rim). Record each display dim in CREATION order: the
    # two end widths, then the root and tip corner anchors (x, then y).
    spoke_sd = SketchDims()
    check("create_sketch spoke", await adapter.create_sketch("Front"))
    h0 = SPOKE_ROOT_WIDTH / 2.0
    h1 = SPOKE_TIP_WIDTH / 2.0
    bottom, tip, _top, root = await add_line_chain(
        adapter, [(SPOKE_X0, -h0), (SPOKE_X1, -h1), (SPOKE_X1, h1), (SPOKE_X0, h0)]
    )
    await _relate(
        adapter,
        (
            ("spoke root vertical", root, None, "vertical"),
            ("spoke tip vertical", tip, None, "vertical"),
        ),
    )
    check(
        "spoke root width",
        await adapter.add_sketch_dimension(root, None, "linear", SPOKE_ROOT_WIDTH),
    )
    spoke_sd.record("SpokeRootWidth", '"SpokeRootWidth"')
    check(
        "spoke tip width",
        await adapter.add_sketch_dimension(tip, None, "linear", SPOKE_TIP_WIDTH),
    )
    spoke_sd.record("SpokeTipWidth", '"SpokeTipWidth"')
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", SPOKE_X0, -h0, "spoke root"
    )
    spoke_sd.record("SpokeX0", '"SpokeX0"')
    spoke_sd.record("SpokeRootY", '"SpokeRootWidth" / 2')  # unsigned half-width
    await anchor_point_to_origin(adapter, f"{tip}.start", SPOKE_X1, -h1, "spoke tip")
    spoke_sd.record("SpokeX1", '"SpokeX1"')
    spoke_sd.record("SpokeTipY", '"SpokeTipWidth" / 2')
    await ensure_fully_defined(adapter, "spoke sketch")
    check("exit_sketch spoke", await adapter.exit_sketch())
    name_last_feature(adapter, "SpokeProfile")
    drive_jobs += spoke_sd.apply(adapter, "SpokeProfile")
    check(
        "extrude spoke",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SPOKE_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Spoke")
    spoke_depth = name_dimensions(adapter, "Spoke", ["SpokeAxial"])
    drive_jobs.append((spoke_depth[0], '"SpokeAxial"'))

    # Pattern the spoke BEFORE the stepped hub revolve: circular patterns on
    # stepped revolved bodies fail to create (_features reeding probe), while
    # this body is still extrusions only. The spokes already join through the
    # rim, so the pattern is one body.
    check(
        f"circular pattern {SPOKE_COUNT} spokes",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=wheel_axis,
                features=["Spoke"],
                count=SPOKE_COUNT,
            )
        ),
    )
    name_last_feature(adapter, "SpokePattern")
    volume = await volume_check(
        adapter,
        "rim + spokes",
        volume + SPOKE_COUNT * V_SPOKE_FREE,
        0.002 * (volume + SPOKE_COUNT * V_SPOKE_FREE),
    )

    # Hub: ONE stepped half-profile on the Right plane (sketch x -> model -Z):
    # the Ø25 boss from its back face to the step, then the Ø14.5 spigot to its
    # front face, revolved about the axis line.
    hub_sd = SketchDims()
    back_x, step_x, front_x = -HUB_BACK_Z, -HUB_STEP_Z, -HUB_FRONT_Z
    check("create_sketch hub", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    hub_axis = check(
        "hub axis centerline", await adapter.add_centerline(back_x, 0.0, front_x, 0.0)
    )
    back, boss, step, spigot, front, axis_line = await add_line_chain(
        adapter,
        [
            (back_x, 0.0),
            (back_x, _HUB_R),
            (step_x, _HUB_R),
            (step_x, _SPIGOT_R),
            (front_x, _SPIGOT_R),
            (front_x, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    for line, direction in (
        (back, "vertical"),
        (boss, "horizontal"),
        (step, "vertical"),
        (spigot, "horizontal"),
        (front, "vertical"),
        (axis_line, "horizontal"),
    ):
        check(
            f"hub {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    # The back face sits HUB_BACK_Z above the spokes' mid-plane (the origin).
    await anchor_point_to_origin(adapter, f"{back}.start", back_x, 0.0, "hub back face")
    hub_sd.record("HubBackZ", '"HubBackZ"')
    await dimension_between(
        adapter,
        f"{back}.start",
        f"{front}.end",
        "horizontal_distance",
        HUB_LEN,
        "HubLength",
    )
    hub_sd.record("HubLength", '"HubLength"')
    await dimension_between(
        adapter,
        f"{step}.start",
        f"{front}.end",
        "horizontal_distance",
        SPIGOT_LEN,
        "SpigotLength",
    )
    hub_sd.record("SpigotLength", '"SpigotLength"')
    await add_diametric_linear_dimension(
        adapter, hub_axis, boss, (back_x + 3.0, _HUB_R + 4.0), "HubDia"
    )
    hub_sd.record("HubDia", '"HubDia"')
    await add_diametric_linear_dimension(
        adapter, hub_axis, spigot, (front_x - 3.0, _SPIGOT_R + 4.0), "SpigotDia"
    )
    hub_sd.record("SpigotDia", '"SpigotDia"')
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub_sd.apply(adapter, "HubProfile")
    check("revolve hub", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "HubBody")
    v_spoke_in_hub = SPOKE_COUNT * (V_SPOKE_FREE - V_SPOKE_WEB)
    volume = await volume_check(
        adapter, "hub", volume + V_HUB - v_spoke_in_hub, 0.002 * V_HUB
    )

    # Axle bore through the boss and spigot. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        _BORE_R,
        "bore",
        dims=bore_sd,
        names=("BoreCx", "BoreCz", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_sd.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * -HUB_FRONT_Z + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", volume - V_BORE, 0.02 * V_BORE)

    # Cast fillets where each spoke side meets the boss (R3) and the rim (R4),
    # picked mid-height on every junction edge; then the R1 rounds on the rim
    # bore's two edges, picked between the 0 and 60 deg spokes.
    await _fillet(
        adapter, HUB_FILLET_R, _spoke_edge_picks(_HUB_R), "HubFillets", "HubFilletR"
    )
    volume = await volume_check(
        adapter, "hub fillets", volume + V_HUB_FILLETS, 0.02 * V_HUB_FILLETS
    )
    await _fillet(
        adapter, RIM_FILLET_R, _spoke_edge_picks(_RIM_IN_R), "RimFillets", "RimFilletR"
    )
    volume = await volume_check(
        adapter, "rim fillets", volume + V_RIM_FILLETS, 0.02 * V_RIM_FILLETS
    )
    between = math.radians(180.0 / SPOKE_COUNT)
    round_xy = [_RIM_IN_R * math.cos(between), _RIM_IN_R * math.sin(between)]
    await _fillet(
        adapter,
        CAST_ROUND_R,
        [[*round_xy, RIM_AXIAL / 2.0], [*round_xy, -RIM_AXIAL / 2.0]],
        "RimRounds",
        "CastRoundR",
    )
    volume = await volume_check(
        adapter, "rim rounds", volume - V_ROUNDS, 0.02 * V_ROUNDS
    )

    # Pen-wire U-groove, revolve-cut on the Right plane: two quarter arcs meet
    # at the groove bottom (a vertex the bottom diameter dimensions to), then
    # straight walls run out past the OD. The axis is the crimp idiom
    # (build_vn_keeper_chain_link): a short centerline from the origin.
    groove_sd = SketchDims()
    check("create_sketch groove", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    groove_axis = check("groove axis", await adapter.add_centerline(0.0, 0.0, 1.0, 0.0))
    bottom_r = GROOVE_BOTTOM_DIA / 2.0
    left_arc = check(
        "groove left arc",
        await adapter.add_arc(
            0.0, _GROOVE_CENTRE_R, -GROOVE_R, _GROOVE_CENTRE_R, 0.0, bottom_r
        ),
    )
    right_arc = check(
        "groove right arc",
        await adapter.add_arc(
            0.0, _GROOVE_CENTRE_R, 0.0, bottom_r, GROOVE_R, _GROOVE_CENTRE_R
        ),
    )
    set_sketch_direct_db(adapter, False)
    _right_wall, groove_top, _left_wall = await add_line_chain(
        adapter,
        [
            (GROOVE_R, _GROOVE_CENTRE_R),
            (GROOVE_R, _GROOVE_TOP_R),
            (-GROOVE_R, _GROOVE_TOP_R),
            (-GROOVE_R, _GROOVE_CENTRE_R),
        ],
        close=False,
    )
    check(
        "groove axis horizontal",
        await adapter.add_sketch_constraint(groove_axis, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{groove_axis}.start", 0.0, 0.0, "groove axis"
    )
    check(
        "groove axis length",
        await adapter.add_sketch_dimension(groove_axis, None, "linear", 1.0),
    )
    groove_sd.record(None)
    await _relate(
        adapter,
        (
            (
                "groove arcs concentric",
                f"{left_arc}.center",
                f"{right_arc}.center",
                "coincident",
            ),
            (
                "groove centre on the mid-plane",
                f"{right_arc}.center",
                "origin",
                "vertical_points",
            ),
            (
                "groove bottom under the centre",
                f"{right_arc}.start",
                f"{right_arc}.center",
                "vertical_points",
            ),
            (
                "groove right wall foot",
                f"{right_arc}.end",
                f"{right_arc}.center",
                "horizontal_points",
            ),
            (
                "groove left wall foot",
                f"{left_arc}.start",
                f"{right_arc}.center",
                "horizontal_points",
            ),
            ("groove right wall vertical", _right_wall, None, "vertical"),
            ("groove left wall vertical", _left_wall, None, "vertical"),
            ("groove top horizontal", groove_top, None, "horizontal"),
        ),
    )
    check(
        "groove radius",
        await adapter.add_sketch_dimension(right_arc, None, "radial", GROOVE_R),
    )
    groove_sd.record("GrooveR", '"GrooveR"')
    await add_diametric_linear_dimension(
        adapter,
        groove_axis,
        f"{right_arc}.start",
        (4.0, bottom_r - 4.0),
        "GrooveBottomDia",
    )
    groove_sd.record("GrooveBottomDia", '"GrooveBottomDia"')
    await dimension_between(
        adapter,
        f"{groove_top}.start",
        "origin",
        "vertical_distance",
        _GROOVE_TOP_R,
        "groove overrun",
    )
    groove_sd.record(None)
    await ensure_fully_defined(adapter, "groove sketch")
    check("exit_sketch groove", await adapter.exit_sketch())
    name_last_feature(adapter, "GrooveProfile")
    drive_jobs += groove_sd.apply(adapter, "GrooveProfile")
    check(
        "revolve-cut groove",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Groove")
    volume = await volume_check(adapter, "groove", volume - V_GROOVE, 0.02 * V_GROOVE)

    # TIE 1: the lever-wire tie hole, axial through the boss on the drum's
    # wire-centre radius at TIE1_CLOCK_DEG (on the Y axis: one centre dim).
    tie1_local = math.radians(clock_to_local_deg(TIE1_CLOCK_DEG))
    tie1_x, tie1_y = TIE1_R * math.cos(tie1_local), TIE1_R * math.sin(tie1_local)
    tie1_sd = SketchDims()
    check("create_sketch tie 1", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        tie1_x,
        tie1_y,
        _TIE_R,
        "tie 1",
        dims=tie1_sd,
        names=("Tie1X", "Tie1Y", "Tie1HoleDia"),
        drives=(None, '"Tie1R"', '"TieHoleDia"'),
    )
    await ensure_fully_defined(adapter, "tie 1 sketch")
    check("exit_sketch tie 1", await adapter.exit_sketch())
    name_last_feature(adapter, "Tie1Profile")
    drive_jobs += tie1_sd.apply(adapter, "Tie1Profile")
    check(
        "cut tie 1",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (HUB_BACK_Z + 1.0), both_directions=True)
        ),
    )
    name_last_feature(adapter, "Tie1")
    volume = await volume_check(adapter, "tie 1", volume - V_TIE1, 0.02 * V_TIE1)

    # TIE 2: the pen-wire tie hole, radial from the groove bottom to the rim
    # bore at TIE2_CLOCK_DEG -- a half rectangle beside its radial axis,
    # revolve-cut. build_pd_latch_hook's pin-hole recipe, relation for
    # relation: both axis ends anchored by x/y distances, the profile's axis
    # edge coincident with the axis ENDS, the far side square/parallel to it.
    # The farm's first native run (1b6b007ff) left this sketch under-defined
    # with the axis pinned instead by an origin-on-line coincidence, an
    # outer-reach distance and an adapter "angular" dimension; none of those has
    # a native precedent in the repo. The angle is therefore a DRIVEN
    # reference here (the NotchPhase / BoreFlatClock precedent); the anchors
    # are computed on the radial, so the axis still passes the origin.
    # DOF: axis 4 + profile 4 lines 8 = 12 = 4 anchor dims + 2x2 end
    # coincidences + square + parallel + inner end horizontal + diameter.
    tie2_sd = SketchDims()
    profile = _tie2_profile()
    check("create_sketch tie 2", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    tie2_axis = check(
        "tie 2 axis", await adapter.add_centerline(*profile[0], *profile[1])
    )
    set_sketch_direct_db(adapter, False)
    on_axis, outer_end, wall, inner_end = await add_line_chain(adapter, profile)
    await _relate(
        adapter,
        (
            (
                "tie 2 profile on the axis, start",
                f"{tie2_axis}.start",
                f"{on_axis}.start",
                "coincident",
            ),
            (
                "tie 2 profile on the axis, end",
                f"{tie2_axis}.end",
                f"{on_axis}.end",
                "coincident",
            ),
            ("tie 2 outer end square to the axis", outer_end, on_axis, "perpendicular"),
            ("tie 2 wall parallel to the axis", wall, on_axis, "parallel"),
            ("tie 2 inner end horizontal", inner_end, None, "horizontal"),
        ),
    )
    for end_ref, point, label in (
        (f"{tie2_axis}.start", profile[0], "tie 2 axis inner end"),
        (f"{tie2_axis}.end", profile[1], "tie 2 axis outer end"),
    ):
        await anchor_point_to_origin(adapter, end_ref, *point, label)
        tie2_sd.record(None)
        tie2_sd.record(None)
    text = (
        profile[2][0] + 3.0 * _TIE2_W[0] + 3.0 * _TIE2_U[0],
        profile[2][1] + 3.0 * _TIE2_W[1] + 3.0 * _TIE2_U[1],
    )
    await add_diametric_linear_dimension(adapter, tie2_axis, wall, text, "Tie2HoleDia")
    tie2_sd.record("Tie2HoleDia", '"TieHoleDia"')
    await add_angular_reference_dimension(
        adapter,
        inner_end,
        on_axis,
        _TIE2_ANGLE_TEXT,
        "tie 2 angle",
        expected_degrees=_TIE2_ANGLE,
    )
    tie2_sd.record("Tie2Angle")
    await ensure_fully_defined(adapter, "tie 2 sketch")
    check("exit_sketch tie 2", await adapter.exit_sketch())
    name_last_feature(adapter, "Tie2Profile")
    drive_jobs += tie2_sd.apply(adapter, "Tie2Profile")
    check(
        "revolve-cut tie 2",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Tie2")
    volume = await volume_check(adapter, "tie 2", volume - V_TIE2, 0.05 * V_TIE2)

    await apply_material(adapter, MATERIAL)
    # Black-painted casting (p.51 photo); the brass drum is its own part.
    await apply_color(adapter, PANEL_BLACK)

    # The rim OD (book-annotated Ø100) and the boss Ø25 at its back face.
    await measure_check(
        adapter,
        "rim OD (annotated 100)",
        [{"entity_type": "EDGE", "point": [_RIM_R, 0.0, RIM_AXIAL / 2.0]}],
        "diameter",
        RIM_OUTER_DIA,
    )
    await measure_check(
        adapter,
        "boss dia",
        [{"entity_type": "EDGE", "point": [_HUB_R, 0.0, HUB_BACK_Z]}],
        "diameter",
        HUB_DIA,
    )

    # WIRE-1 yoke point (see the module-level YOKE_LOCAL_* block): one raw
    # sketch point on the Front plane (mid-plane, exact coords, inference OFF)
    # promoted to a named REFERENCE POINT feature the assembly's coupling mate
    # selects. The carrier sketch is blanked (unabsorbed sketches render SHOWN
    # in every assembly instance); the point's coords are re-read and asserted
    # after the final rebuild -- it is undimensioned, so drift must fail loud.
    check("create_sketch yoke", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    model = adapter.currentModel
    sk_point = model.SketchManager.CreatePoint(
        YOKE_LOCAL_X / 1000.0, YOKE_LOCAL_Y / 1000.0, 0.0)
    if sk_point is None:
        raise RuntimeError("yoke sketch point creation failed")
    set_sketch_direct_db(adapter, False)
    check("exit_sketch yoke", await adapter.exit_sketch())
    name_last_feature(adapter, "WireYokeSketch")
    blank_sketch(adapter, "WireYokeSketch")
    _make_yoke_ref_point(adapter)

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value:
    # the geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven magnifying wheel (equations neutral)", volume, 0.001 * volume
    )

    _assert_yoke_point(adapter)
    await report_mass_properties(adapter)

    # Drawing-simplicity rule 2: the tight bands sit on the model dimensions,
    # the places on every marked one.
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "HubDia", *deviations(HUB_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "HubLength", *deviations(HUB_LEN_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "SpigotDia", *deviations(SPIGOT_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "SpigotLength", *deviations(SPIGOT_LEN_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "GrooveProfile", "GrooveR", *deviations(GROOVE_R_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "GrooveProfile", "GrooveBottomDia", *deviations(GROOVE_BOTTOM_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDiaDim", *deviations(BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Tie1Profile", "Tie1HoleDia", *deviations(TIE_HOLE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Tie2Profile", "Tie2HoleDia", *deviations(TIE_HOLE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RimRounds", "CastRoundR", *deviations(CAST_ROUND_BAND)
    )
    set_dimension_symmetric_tolerance(adapter, "Tie1Profile", "Tie1Y", TIE_POSITION_TOL)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Section View Note": SECTION_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


def _yoke_sketch_points(adapter):
    """The ISketchPoint list of WireYokeSketch (exactly one expected).

    COM members read via ``_read_member`` -- pywin32 late binding exposes
    FirstFeature/Name/GetNextFeature as methods on some builds and properties
    on others (the fix_shown_sketches walk idiom)."""
    model = adapter.currentModel
    feat = _read_member(model, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        if str(_read_member(feat, "Name")) == "WireYokeSketch":
            sketch = _read_member(feat, "GetSpecificFeature2")
            return list(_read_member(sketch, "GetSketchPoints2") or [])
        feat = _read_member(feat, "GetNextFeature")
    raise RuntimeError("WireYokeSketch not found")


def _make_yoke_ref_point(adapter) -> None:
    """Promote the yoke sketch point to a named reference-point FEATURE
    (``WireYokePoint``) via raw COM -- the adapter's reference-point modes are
    edge/face-based only; ``InsertReferencePoint(swRefPointSketchPoint=7)``
    works from a selected sketch point (the adapter has no writer, same
    raw-COM precedent as the Part D custom properties)."""
    model = adapter.currentModel
    pts = _yoke_sketch_points(adapter)
    if len(pts) != 1:
        raise RuntimeError(f"WireYokeSketch: expected 1 point, found {len(pts)}")
    model.ClearSelection2(True)
    # Select2(Append, Mark): the late-binding-safe select -- Select4's
    # ISelectData arg raises "Type mismatch" under the adapter's forced late
    # binding (the _assembly batch-fix comment documents the same trap).
    if not pts[0].Select2(False, 0):
        raise RuntimeError("cannot select the yoke sketch point")
    feat = model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)  # 7 = sketch point
    model.ClearSelection2(True)
    if isinstance(feat, tuple):  # late binding marshals the object return boxed
        feat = next((f for f in feat if f is not None), None)
    if feat is None:
        raise RuntimeError("InsertReferencePoint(sketch point) returned null")
    feat.Name = "WireYokePoint"
    if str(_read_member(feat, "Name")) != "WireYokePoint":
        raise RuntimeError("reference point rename failed")
    # Hidden but still selectable by name for the WIRE-1 yoke mate.
    blank_reference_geometry(adapter, (("WireYokePoint", "DATUMPOINT"),))
    _telemetry.success("WireYokePoint reference point created")


def _assert_yoke_point(adapter) -> None:
    """Fail loud if the (undimensioned, hidden) yoke sketch point drifted from
    its authored coords across the rebuilds -- the coupling mate's geometry
    must stay exact."""
    pts = _yoke_sketch_points(adapter)
    x_mm = float(_read_member(pts[0], "X")) * 1000.0
    y_mm = float(_read_member(pts[0], "Y")) * 1000.0
    if abs(x_mm - YOKE_LOCAL_X) > 1e-3 or abs(y_mm - YOKE_LOCAL_Y) > 1e-3:
        raise RuntimeError(
            f"yoke point drifted: ({x_mm:.4f}, {y_mm:.4f}) != "
            f"({YOKE_LOCAL_X:.4f}, {YOKE_LOCAL_Y:.4f})"
        )
    _telemetry.success(f"yoke point holds at ({x_mm:.4f}, {y_mm:.4f})")


if __name__ == "__main__":
    sys.exit(run_build(build))
