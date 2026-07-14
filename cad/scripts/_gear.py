r"""Shared involute-gear authoring helpers (fixed tooth count).

The tooth-gap technique is the cone gear's live-validated recipe (see
``build_cone_gear.py`` for the involute derivation and the SW 2026 parser
facts): six ``CreateEquationSpline2`` curves -- two involute flanks, base
chord, two radial extensions, outer clearance arc -- cut through a disc
blank and circular-patterned about the gear axis. Here the expressions are
literal numerics (document units = inches, trig in radians), which is all a
non-configured gear needs; ``build_cone_gear.py`` keeps its own global-
variable variant for the configuration-driven cone set, and
``build_transgear_removable.py`` reuses that variant for its 3 configurations.

Every step is volume-asserted against the exact analytic expectation
(``gap_area_in_disc`` Green's-theorem integration), so a regeneration or
unit-dialect regression fails the build instead of silently saving bad
geometry.
"""

from __future__ import annotations

import math
from typing import Any

from _common import (
    IN,
    check,
    define_circle,
    dimension_between,
    ensure_fully_defined,
    name_last_feature,
    volume_check,
)
from build_cone_gear import gear_facts

import _telemetry

__all__ = [
    "build_fixed_gear",
    "cut_tooth_gap",
    "gap_area_in_disc_ext",
    "pattern_about_z",
    "volume_check",
]

# Cut clearance radius (inches -- document units): beyond the largest tip
# radius in the machine (120T OD/2 = 2.033") so gap profiles always close
# outside the blank.
R_CLEAR_IN = 60.0 / 25.4


def fmt(value: float) -> str:
    """Literal for a curve expression (document units = inches, radians)."""
    return f"{value:.12g}"


async def equation_curve(adapter: Any, label: str, x_expr: str, y_expr: str) -> str:
    """Add a parametric equation curve over t in [0, 1]; return its entity ID."""
    from solidworks_mcp.adapters.base import CreateEquationCurveParameters

    res = await adapter.create_equation_driven_curve(
        CreateEquationCurveParameters(
            x_expression=x_expr,
            y_expression=y_expr,
            range_start="0",
            range_end="1",
        )
    )
    return check(f"curve {label}", res)


async def cut_tooth_gap(
    adapter: Any,
    facts: dict[str, float],
    depth: float,
    *,
    rotate_rad: float = 0.0,
    widen_rad: float = 0.0,
    root_r_in: float | None = None,
) -> Any:
    """Cut one involute tooth gap through a blank (+Z from the Front plane).

    ``rotate_rad`` spins the whole gap profile CCW about the gear axis;
    ``widen_rad`` is a symmetric backlash: each flank backs off the gap
    centre by that angle (circumferential widening = 2*widen_rad*R_pitch).
    ``root_r_in`` (inches) replaces the base-chord floor with radial flank
    extensions down to a root arc at that radius -- the deepened-dedendum
    relief a small-pinion mate needs (the stock floor sits AT the base
    circle, so a 16T's mate bottoms out 0.7 mm early). All offsets fold
    into the curve literals; the expression SHAPE is the cone gear's
    live-validated recipe, unchanged. (NB a blind cut from a sketch on an
    OFFSET plane defaults back toward the base plane -- the retired K-slice
    helix stack tripped it; see memory/solidworks-modeling-pitfalls.md.)
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    rho, eps = rotate_rad, widen_rad
    rb, ra = fmt(facts["Rb"]), fmt(facts["Ra"])
    theta_l = facts["ThetaL"] - eps + rho
    theta_u = facts["ThetaU"] + eps + rho
    th_l, th_u = fmt(theta_l), fmt(theta_u)
    rc = fmt(R_CLEAR_IN)
    u = f"({fmt(facts['Tmax'])} * t)"
    # NB the lower flank is the MIRRORED involute (its y is negated relative
    # to the upper's form), so an azimuth offset enters its phase with the
    # OPPOSITE sign: azimuth(t=0) = -(phase(0)). Lower lands at Delta-eps+rho,
    # upper at Gamma-Delta+eps+rho.
    ph_low = f"({u} - {fmt(facts['Delta'] - eps + rho)})"
    ph_up = f"({u} + {fmt(facts['Gamma'] - facts['Delta'] + eps + rho)})"
    a1 = facts["Delta"] - eps + rho
    a2 = facts["Gamma"] - facts["Delta"] + eps + rho
    check("create_sketch gap", await adapter.create_sketch("Front"))
    gap_curves = [
        await equation_curve(
            adapter,
            "lower flank (tooth 0 upper, mirrored involute)",
            f"{rb} * (cos{ph_low} + {u} * sin{ph_low})",
            f"{rb} * ({u} * cos{ph_low} - sin{ph_low})",
        ),
        await equation_curve(
            adapter,
            "upper flank (tooth 1 lower involute)",
            f"{rb} * (cos{ph_up} + {u} * sin{ph_up})",
            f"{rb} * (sin{ph_up} - {u} * cos{ph_up})",
        ),
        await equation_curve(
            adapter,
            "lower radial extension B1->clearance",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.cos(theta_l))}",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.sin(theta_l))}",
        ),
        await equation_curve(
            adapter,
            "outer clearance arc",
            f"{rc} * cos({th_l} + t * ({th_u} - {th_l}))",
            f"{rc} * sin({th_l} + t * ({th_u} - {th_l}))",
        ),
        await equation_curve(
            adapter,
            "upper radial extension clearance->B2",
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.cos(theta_u))}",
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.sin(theta_u))}",
        ),
    ]
    if root_r_in is None:
        gap_curves.append(await equation_curve(
            adapter,
            "base chord A2->A1",
            f"{rb} * ((1 - t) * {fmt(math.cos(a2))} + t * {fmt(math.cos(a1))})",
            f"{rb} * ((1 - t) * {fmt(math.sin(a2))} + t * {fmt(math.sin(a1))})",
        ))
    else:
        rr = fmt(root_r_in)
        gap_curves += [
            await equation_curve(
                adapter,
                "upper root extension A2->A2r",
                f"({rb} + t * ({rr} - {rb})) * {fmt(math.cos(a2))}",
                f"({rb} + t * ({rr} - {rb})) * {fmt(math.sin(a2))}",
            ),
            await equation_curve(
                adapter,
                "root arc A2r->A1r",
                f"{rr} * cos({fmt(a2)} + t * ({fmt(a1)} - {fmt(a2)}))",
                f"{rr} * sin({fmt(a2)} + t * ({fmt(a1)} - {fmt(a2)}))",
            ),
            await equation_curve(
                adapter,
                "lower root extension A1r->A1",
                f"({rr} + t * ({rb} - {rr})) * {fmt(math.cos(a1))}",
                f"({rr} + t * ({rb} - {rr})) * {fmt(math.sin(a1))}",
            ),
        ]
    # Equation-driven curves are the whitelist class for fix (no free
    # endpoints to dimension); B3 attempts a semantic scheme before keeping
    # this escalation (cad/FIX_MIGRATION.md).
    await ensure_fully_defined(
        adapter, "gap sketch", fix_entities=gap_curves, allow_fix_escalation=True
    )
    check("exit_sketch gap", await adapter.exit_sketch())
    gap_cut = await adapter.create_cut_extrude(ExtrusionParameters(depth=depth))
    check("cut tooth gap", gap_cut)
    return gap_cut


async def pattern_about_z(
    adapter: Any, seed_feature: str | list[str], count: int,
    radius_mm: float, z_mm: float
) -> Any:
    """Circular-pattern seed feature(s) about the Z axis through the origin.

    Creates a Top x Right reference axis, then walks candidate selection
    points (axis selection by view-projected point is flaky -- live-caught
    on the cone gear): the origin axis point first, then OD-face points at
    angles away from the seed gap near angle 0.
    """
    from solidworks_mcp.adapters.base import CircularPatternParameters, CreateAxisParameters

    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    adapter._zoom_to_fit(adapter.currentModel)
    candidates = [[0.0, 0.0, z_mm]]
    for angle_deg in (-45.0, -90.0, -135.0, 135.0, 45.0):
        a = math.radians(angle_deg)
        candidates.append([radius_mm * math.cos(a), radius_mm * math.sin(a), z_mm])
    features = [seed_feature] if isinstance(seed_feature, str) else list(seed_feature)
    for point in candidates:
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point, features=features, count=count
            )
        )
        if res.is_success:
            _telemetry.success(f"circular pattern axis via point {point}")
            return res
        _telemetry.debug(f"axis candidate {point} failed: {res.error}")
    raise RuntimeError("circular pattern: no axis candidate selectable")


def gap_area_in_disc_ext(
    teeth: int,
    dp: float,
    pa_deg: float = 14.5,
    widen_rad: float = 0.0,
    root_r_in: float | None = None,
    samples: int = 2000,
) -> float:
    """In-blank area of one tooth gap (in^2) with the widen/root extensions.

    The plain (widen 0, base-chord floor) case reduces exactly to
    ``build_cone_gear.gap_area_in_disc`` (asserted by ``check:math``'s import
    of both). Same Green's-theorem boundary walk as the live curves in
    ``cut_tooth_gap``: lower flank (rotated -widen), rim arc at Ra, upper
    flank reversed (rotated +widen), then the floor -- base chord, or radial
    extensions + root arc when ``root_r_in`` is set. A whole-gap rotation
    never changes the area, so the sliced-helix twist reuses this expectation
    per slice.
    """
    f = gear_facts(teeth, dp, pa_deg)
    rb, ra = f["Rb"], f["Ra"]
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    eps = widen_rad
    th_l, th_u = f["ThetaL"] - eps, f["ThetaU"] + eps
    a1, a2 = delta - eps, gamma - delta + eps
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank (mirrored involute, -eps)
        t = tmax * i / samples
        ph = t - delta + eps  # mirror flips the offset sign; azimuth(0) = a1
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (t * math.cos(ph) - math.sin(ph)),
        ))
    for i in range(1, samples + 1):  # rim arc ThetaL' -> ThetaU'
        th = th_l + (th_u - th_l) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank, reversed (+eps)
        t = tmax * (samples - i) / samples
        ph = t - delta + gamma + eps
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (math.sin(ph) - t * math.cos(ph)),
        ))
    if root_r_in is None:  # base chord A2 -> A1
        for i in range(1, samples):
            s = i / samples
            pts.append((
                rb * ((1 - s) * math.cos(a2) + s * math.cos(a1)),
                rb * ((1 - s) * math.sin(a2) + s * math.sin(a1)),
            ))
    else:  # radial in at a2, root arc, radial out at a1
        rr = root_r_in
        pts.append((rr * math.cos(a2), rr * math.sin(a2)))
        for i in range(1, samples):
            th = a2 + (a1 - a2) * i / samples
            pts.append((rr * math.cos(th), rr * math.sin(th)))
        pts.append((rr * math.cos(a1), rr * math.sin(a1)))
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


# Import-time tripwire: at defaults the extended area must reduce to the cone
# gear's exact expectation (same boundary, different code path) -- a drifted
# copy would silently skew every _gear volume gate.
from build_cone_gear import gap_area_in_disc as _gap_area_plain  # noqa: E402

for _t, _dp in ((16, 26.57), (64, 26.57), (12, 12.7)):
    _a, _b = gap_area_in_disc_ext(_t, dp=_dp), _gap_area_plain(_t, dp=_dp)
    if abs(_a - _b) > 1e-9:
        raise AssertionError(f"gap_area_in_disc_ext drifted at T{_t}: {_a} vs {_b}")


# Helical-tooth sweep constants, both live-arbitrated on the crank-drive
# gear (the volume gates + the STL band audit re-prove them on any drift):
# the tooth root EMBEDS into the blank so the boss union is robust -- and so
# a flipped sweep path fails LOUD (a disjoint tooth keeps its embedded
# sliver: ~+0.1 mm^2 x face x teeth over the analytic expectation).
_TOOTH_EMBED_MM = 0.3
# Top-plane sketch -y maps to world +Z on this template (live-arbitrated:
# the +y first try left the tooth disjoint below the disc -- the seeded-tooth
# gate read exactly +1 embedded sliver), and a positive
# InsertProtrusionSwept4 twist turns CCW about the +Z path -- the +INCLINE
# hand (gap azimuth advancing CCW toward +z).
_SWEEP_PATH_Y = -1.0
_TWIST_CCW = 1.0


async def boss_tooth_swept(
    adapter: Any,
    facts: dict[str, float],
    face_width: float,
    *,
    twist_deg: float,
    rotate_rad: float,
    widen_rad: float,
    root_r_in: float,
) -> str:
    """Boss-sweep ONE involute tooth along +Z with constant twist; return the
    sweep feature's name (the circular-pattern seed).

    The profile is the exact complement of ``cut_tooth_gap``'s gap between
    two adjacent gaps -- same involute flank expressions, tip arc at Ra, root
    closure at ``root_r_in`` (extended ``_TOOTH_EMBED_MM`` into the blank) --
    so mesh conjugacy and the seed convention (tooth centred on azimuth 0)
    are IDENTICAL to the cut recipe. ``rotate_rad`` pre-rotates the profile
    to the z=0 helix phase (-half twist), so mid-face stays the design
    azimuth; ``widen_rad`` thins each flank by the backlash angle (the same
    +-eps the gap curves widen by).
    """
    from solidworks_mcp.adapters.base import SweepParameters

    rho, eps = rotate_rad, widen_rad
    rb, ra = fmt(facts["Rb"]), fmt(facts["Ra"])
    rr_embed = fmt(root_r_in - _TOOTH_EMBED_MM / IN)
    gamma = facts["Gamma"]
    theta_lo = facts["ThetaU"] + eps + rho          # tip arc start (flank A @ Ra)
    theta_hi = gamma + facts["ThetaL"] - eps + rho  # tip arc end (flank B @ Ra)
    a_lo = facts["Gamma"] - facts["Delta"] + eps + rho  # flank A base azimuth
    a_hi = gamma + facts["Delta"] - eps + rho           # flank B base azimuth
    u = f"({fmt(facts['Tmax'])} * t)"
    ph_a = f"({u} + {fmt(a_lo)})"
    ph_b = f"({u} - {fmt(a_hi)})"
    check("create_sketch tooth", await adapter.create_sketch("Front"))
    tooth_curves = [
        await equation_curve(
            adapter,
            "tooth lower flank (gap 0 upper involute)",
            f"{rb} * (cos{ph_a} + {u} * sin{ph_a})",
            f"{rb} * (sin{ph_a} - {u} * cos{ph_a})",
        ),
        await equation_curve(
            adapter,
            "tip arc at Ra",
            f"{ra} * cos({fmt(theta_lo)} + t * ({fmt(theta_hi)} - {fmt(theta_lo)}))",
            f"{ra} * sin({fmt(theta_lo)} + t * ({fmt(theta_hi)} - {fmt(theta_lo)}))",
        ),
        await equation_curve(
            adapter,
            "tooth upper flank (gap 1 lower, mirrored involute)",
            f"{rb} * (cos{ph_b} + {u} * sin{ph_b})",
            f"{rb} * ({u} * cos{ph_b} - sin{ph_b})",
        ),
        await equation_curve(
            adapter,
            "upper root extension B->embed",
            f"({rb} + t * ({rr_embed} - {rb})) * {fmt(math.cos(a_hi))}",
            f"({rb} + t * ({rr_embed} - {rb})) * {fmt(math.sin(a_hi))}",
        ),
        await equation_curve(
            adapter,
            "embedded root arc B->A",
            f"{rr_embed} * cos({fmt(a_hi)} + t * ({fmt(a_lo)} - {fmt(a_hi)}))",
            f"{rr_embed} * sin({fmt(a_hi)} + t * ({fmt(a_lo)} - {fmt(a_hi)}))",
        ),
        await equation_curve(
            adapter,
            "lower root extension embed->A",
            f"({rr_embed} + t * ({rb} - {rr_embed})) * {fmt(math.cos(a_lo))}",
            f"({rr_embed} + t * ({rb} - {rr_embed})) * {fmt(math.sin(a_lo))}",
        ),
    ]
    await ensure_fully_defined(
        adapter, "tooth sketch", fix_entities=tooth_curves, allow_fix_escalation=True
    )
    check("exit_sketch tooth", await adapter.exit_sketch())

    # Path: a fully-defined line up the gear axis (origin coincidence +
    # vertical + one length dim -- the build_boss_hook recipe).
    check("create_sketch tooth path", await adapter.create_sketch("Top"))
    line = check(
        "tooth path line",
        await adapter.add_line(0.0, 0.0, 0.0, _SWEEP_PATH_Y * face_width),
    )
    check("path vertical", await adapter.add_sketch_constraint(line, None, "vertical"))
    check(
        "path start -> origin",
        await adapter.add_sketch_constraint(f"{line}.start", "origin", "coincident"),
    )
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        face_width, "tooth path length",
    )
    await ensure_fully_defined(adapter, "tooth path sketch")
    check("exit_sketch tooth path", await adapter.exit_sketch())
    name_last_feature(adapter, "ToothPath")

    sweep = check(
        "sweep tooth (twisted)",
        await adapter.create_sweep(SweepParameters(
            path="ToothPath",
            twist_along_path=True,
            twist_angle=_TWIST_CCW * twist_deg,
            merge_result=True,
        )),
    )
    return sweep.name


def _blank_ref_plane(adapter: Any, name: str) -> None:
    """Hide a reference plane (shown ref geometry renders in the part PNG and
    every assembly instance -- the fix_shown_sketches BlankRefGeom idiom,
    applied at build; see build_lever_wire/_output_fixture)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"blank ref plane: cannot select {name!r}")
    model.BlankRefGeom()
    model.ClearSelection2(True)


async def build_fixed_gear(
    adapter: Any,
    teeth: int,
    face_width: float,
    dp: float = 30.0,
    pa_deg: float = 14.5,
    *,
    helix_deg: float = 0.0,
    backlash_mm: float = 0.0,
    root_relief: bool = False,
) -> float:
    """Build a toothed disc on the active new part.

    Gear axis = Z through the origin, disc z = 0..face_width (mm). Returns
    the volume-checked toothed-disc volume in mm^3.

    Straight gears (``helix_deg`` 0): tip-radius blank + one gap cut +
    pattern (the cone gear's live-validated recipe). ``helix_deg`` builds a
    TRUE helix instead (tooth azimuth advancing ``(z - face/2)*tan(helix)/
    R_pitch`` CCW with +z -- the crank-drive gear's crossed-axis
    accommodation): a root-cylinder blank + ONE involute tooth boss-swept
    along the axis with constant twist + pattern. Smooth helicoid flanks --
    this superseded the K-slice cut stack, whose facets consumed ~0.2 mm of
    the mesh clearance and read as machining marks in every render.
    ``backlash_mm`` widens each gap / thins each tooth by that
    circumferential allowance at the pitch radius (split +-eps onto the two
    flank phases). ``root_relief`` deepens the gap floor from the base
    chord to a root arc at pitch_r - 1.157*addendum (standard dedendum) --
    REQUIRED on any gear meshing a small pinion (and by the helix path,
    whose additive area algebra needs the arc floor): the stock base-circle
    floor leaves a 16T's mate 0.7 mm shy of working depth.
    """
    facts = gear_facts(teeth, dp, pa_deg)
    ra_mm = facts["Ra"] * IN
    pitch_r_in = teeth / dp / 2.0
    widen_rad = (backlash_mm / 2.0) / (pitch_r_in * IN)
    root_r_in = (pitch_r_in - 1.157 / dp) if root_relief else None
    if helix_deg and root_r_in is None:
        raise ValueError("helix_deg requires root_relief=True (additive tooth "
                         "area algebra assumes the root-arc floor)")

    from solidworks_mcp.adapters.base import ExtrusionParameters

    blank_r_mm = (root_r_in * IN) if helix_deg else ra_mm
    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, blank_r_mm, "gear blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=face_width)),
    )
    v_blank = math.pi * blank_r_mm**2 * face_width
    await volume_check(adapter, "blank", v_blank, 0.005 * v_blank)

    gap_area = gap_area_in_disc_ext(
        teeth, dp=dp, pa_deg=pa_deg, widen_rad=widen_rad, root_r_in=root_r_in
    )
    if not helix_deg:
        gap_cut = await cut_tooth_gap(
            adapter, facts, face_width + 1.0,
            widen_rad=widen_rad, root_r_in=root_r_in,
        )
        seeds: list[str] = [gap_cut.data.name]
        # Coverage tripwire BEFORE patterning: the seed cut must have removed
        # exactly one full gap column. The final 1% disc gate is too loose to
        # see a partial cut (the retired K-slice stack's direction flip left
        # +148 mm^3 on the 64T -- 0.5%, inside tolerance).
        v_seeded = v_blank - gap_area * IN**2 * face_width
        v_gear = v_blank - teeth * gap_area * IN**2 * face_width
    else:
        twist_deg = math.degrees(
            face_width * math.tan(math.radians(helix_deg)) / (pitch_r_in * IN))
        seeds = [await boss_tooth_swept(
            adapter, facts, face_width,
            twist_deg=twist_deg,
            rotate_rad=-math.radians(twist_deg) / 2.0,  # z=0 phase: mid-face = design azimuth
            widen_rad=widen_rad, root_r_in=root_r_in,
        )]
        # One tooth must add exactly the annulus-sector complement of the gap
        # (a twisted sweep keeps the profile area per Cavalieri; the embedded
        # root sliver lies inside the blank so the union gains none of it --
        # and a flipped sweep path keeps the sliver as a disjoint body,
        # overshooting this gate loud).
        tooth_area = (
            math.pi * (facts["Ra"] ** 2 - root_r_in**2) / teeth - gap_area
        )
        v_seeded = v_blank + tooth_area * IN**2 * face_width
        v_gear = v_blank + teeth * tooth_area * IN**2 * face_width
    await volume_check(adapter, "seeded tooth/gap", v_seeded, 1.0)

    await pattern_about_z(adapter, seeds, teeth, ra_mm, face_width / 2.0)
    return await volume_check(adapter, "toothed disc", v_gear, 0.01 * v_gear)
