r"""Shared involute-gear authoring helpers (fixed tooth count).

The tooth-gap technique is the cone gear's live-validated recipe (see
``build_dt_cone_gear.py`` for the involute derivation and the SW 2026 parser
facts): six ``CreateEquationSpline2`` curves -- two involute flanks, base
chord, two radial extensions, outer clearance arc -- cut through a disc
blank and circular-patterned about the gear axis. Here the expressions are
literal numerics (document units = inches, trig in radians), which is all a
non-configured gear needs; ``build_dt_cone_gear.py`` keeps its own global-
variable variant for the configuration-driven cone set, and
``build_pd_transgear_removable.py`` reuses that variant for its 3 configurations.

Every step is volume-asserted against the exact analytic expectation
(``gap_area_in_disc`` Green's-theorem integration), so a regeneration or
unit-dialect regression fails the build instead of silently saving bad
geometry.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any, NamedTuple

import _telemetry

from _check import check
from _com import _early_bound
from _feature_tree import name_last_feature
from _part_checks import volume_check
from _paths import IN
from _sketch import dimension_between, ensure_fully_defined
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from involute_gear import PA_DEG, gear_facts

if TYPE_CHECKING:
    from stock_form_cutter import StockFormProfile

__all__ = [
    "ToothedDisc",
    "assert_stock_screw_sweep_phase",
    "build_fixed_gear",
    "build_stock_form_gear",
    "cut_tooth_gap",
    "gap_area_in_disc_ext",
    "pattern_about_z",
    "volume_check",
]

# Cut clearance radius (inches -- document units): beyond the largest tip
# radius in the machine (120T OD/2 = 2.033") so gap profiles always close
# outside the blank.
R_CLEAR_IN = 60.0 / 25.4


class ToothedDisc(NamedTuple):
    """``build_fixed_gear``'s volume-checked disc and the features that form
    its teeth (seed gap cut or tooth sweep, then the pattern) -- what a
    ``_simplified_part`` configuration suppresses."""

    volume: float
    tooth_features: tuple[str, ...]


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


def _root_start_parameter(base_r_in: float, root_r_in: float | None) -> float:
    """Start on the physical root circle only when it lies above the base."""
    if root_r_in is None:
        return 0.0
    if not math.isfinite(root_r_in) or root_r_in <= 0.0:
        raise ValueError("gear root radius must be positive and finite")
    if root_r_in <= base_r_in:
        return 0.0
    return math.sqrt((root_r_in / base_r_in) ** 2 - 1.0)


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
    ``root_r_in`` (inches) replaces the base-chord floor with a root arc.
    Below the base circle, radial extensions join that arc to the involute;
    above it, the involute starts on the root circle itself. All offsets
    fold into the curve literals; the involute expression shape is the cone
    gear's live-validated recipe. (NB a blind cut from a sketch on an
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
    tmin = _root_start_parameter(facts["Rb"], root_r_in)
    if tmin >= facts["Tmax"]:
        raise ValueError("gear root must leave a nonzero involute below the tip")
    foot_inv = tmin - math.atan(tmin)
    u = f"({fmt(tmin)} + {fmt(facts['Tmax'] - tmin)} * t)"
    # NB the lower flank is the MIRRORED involute (its y is negated relative
    # to the upper's form), so an azimuth offset enters its phase with the
    # OPPOSITE sign: azimuth(t=0) = -(phase(0)). Lower lands at Delta-eps+rho,
    # upper at Gamma-Delta+eps+rho.
    ph_low = f"({u} - {fmt(facts['Delta'] - eps + rho)})"
    ph_up = f"({u} + {fmt(facts['Gamma'] - facts['Delta'] + eps + rho)})"
    a1 = facts["Delta"] - foot_inv - eps + rho
    a2 = facts["Gamma"] - facts["Delta"] + foot_inv + eps + rho
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
        if root_r_in < facts["Rb"]:
            gap_curves.append(
                await equation_curve(
                    adapter,
                    "upper root extension A2->A2r",
                    f"({rb} + t * ({rr} - {rb})) * {fmt(math.cos(a2))}",
                    f"({rb} + t * ({rr} - {rb})) * {fmt(math.sin(a2))}",
                )
            )
        gap_curves.append(
            await equation_curve(
                adapter,
                "root arc A2r->A1r",
                f"{rr} * cos({fmt(a2)} + t * ({fmt(a1)} - {fmt(a2)}))",
                f"{rr} * sin({fmt(a2)} + t * ({fmt(a1)} - {fmt(a2)}))",
            )
        )
        if root_r_in < facts["Rb"]:
            gap_curves.append(
                await equation_curve(
                    adapter,
                    "lower root extension A1r->A1",
                    f"({rr} + t * ({rb} - {rr})) * {fmt(math.cos(a1))}",
                    f"({rr} + t * ({rb} - {rr})) * {fmt(math.sin(a1))}",
                )
            )
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

    Creates a Top x Right reference axis and selects that reference feature by
    its returned name. Point selection projects through the graphics view and
    is not a reliable way to select a buried reference axis.
    """
    from solidworks_mcp.adapters.base import CircularPatternParameters, CreateAxisParameters

    axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    features = [seed_feature] if isinstance(seed_feature, str) else list(seed_feature)
    pattern = check(
        f"circular pattern about {axis.name}",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=axis.name,
                features=features,
                count=count,
                geometry_pattern=True,
            )
        ),
    )
    # Hidden once the pattern owns it, so it does not print in renders.
    blank_reference_geometry(adapter, ((axis.name, "AXIS"),))
    return pattern


def gap_area_in_disc_ext(
    teeth: int,
    dp: float,
    pa_deg: float = PA_DEG,
    widen_rad: float = 0.0,
    root_r_in: float | None = None,
    samples: int = 2000,
    *,
    addendum_extra_in: float = 0.0,
) -> float:
    """In-blank area of one tooth gap (in^2) with the widen/root extensions.

    The plain (widen 0, base-chord floor) case reduces exactly to
    ``involute_gear.gap_area_in_disc`` (asserted by ``check:math``'s import
    of both). Same Green's-theorem boundary walk as the live curves in
    ``cut_tooth_gap``: lower flank (rotated -widen), rim arc at Ra, upper
    flank reversed (rotated +widen), then the floor -- base chord or root arc
    with radial extensions only below the base circle. A whole-gap rotation
    never changes the area, so the sliced-helix twist reuses this expectation
    per slice. ``addendum_extra_in`` moves the rim arc exactly as it moves
    ``gear_facts``' tip radius.
    Above-base roots close directly on their physical root arc, using the
    same clipped involute and root-foot phases as the native cut and sweep.
    """
    f = gear_facts(teeth, dp, pa_deg, addendum_extra_in=addendum_extra_in)
    rb, ra = f["Rb"], f["Ra"]
    tmax, delta, gamma = f["Tmax"], f["Delta"], f["Gamma"]
    eps = widen_rad
    th_l, th_u = f["ThetaL"] - eps, f["ThetaU"] + eps
    tmin = _root_start_parameter(rb, root_r_in)
    if tmin >= tmax:
        raise ValueError("gear root must leave a nonzero involute below the tip")
    foot_inv = tmin - math.atan(tmin)
    a1, a2 = delta - foot_inv - eps, gamma - delta + foot_inv + eps
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank (mirrored involute, -eps)
        t = tmin + (tmax - tmin) * i / samples
        ph = t - delta + eps  # mirror flips the offset sign; azimuth(0) = a1
        pts.append((
            rb * (math.cos(ph) + t * math.sin(ph)),
            rb * (t * math.cos(ph) - math.sin(ph)),
        ))
    for i in range(1, samples + 1):  # rim arc ThetaL' -> ThetaU'
        th = th_l + (th_u - th_l) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank, reversed (+eps)
        t = tmin + (tmax - tmin) * (samples - i) / samples
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
    else:  # root arc, with radial extensions only below the base circle
        rr = root_r_in
        if root_r_in < rb:
            pts.append((rr * math.cos(a2), rr * math.sin(a2)))
        for i in range(1, samples):
            th = a2 + (a1 - a2) * i / samples
            pts.append((rr * math.cos(th), rr * math.sin(th)))
        if root_r_in < rb:
            pts.append((rr * math.cos(a1), rr * math.sin(a1)))
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


# Import-time tripwire: with no extensions, the two independent area paths
# must agree. These arbitrary tooth-count/pitch samples exercise the generic
# identity, not the configured cone or crank tooth systems.
from involute_gear import gap_area_in_disc as _gap_area_plain  # noqa: E402

for _t, _dp in ((16, 24.74), (64, 24.74), (12, 12.7)):
    _a, _b = gap_area_in_disc_ext(_t, dp=_dp), _gap_area_plain(_t, dp=_dp)
    if abs(_a - _b) > 1e-9:
        raise AssertionError(f"gap_area_in_disc_ext drifted at T{_t}: {_a} vs {_b}")


# Helical-tooth sweep constants, both live-arbitrated on the crank-drive
# gear (the volume gates + the STL band audit re-prove them on any drift):
# the tooth root EMBEDS into the blank so the boss union is robust -- and so
# a flipped sweep path fails LOUD (a disjoint tooth keeps its embedded
# sliver: ~+0.1 mm^2 x face x teeth over the analytic expectation).
_TOOTH_EMBED_MM = 0.3
# The stock helical recipe floors each gap on the foot-radius cylinder, not
# the translated root arc. 0.005 mm radial is 3 % of the 0.157/P = 0.166 mm
# standard clearance of the coarsest stock helical cutter here (24 DP), so the
# substitute floor cannot eat the mating tip's clearance (the 64T's arc and
# cylinder differ by 0.0007 mm).
_ROOT_CYLINDER_BOUND_MM = 0.005
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
    rho, eps = rotate_rad, widen_rad
    rb, ra = fmt(facts["Rb"]), fmt(facts["Ra"])
    tmin = _root_start_parameter(facts["Rb"], root_r_in)
    if tmin >= facts["Tmax"]:
        raise ValueError("gear root must leave a nonzero involute below the tip")
    if root_r_in <= _TOOTH_EMBED_MM / IN:
        raise ValueError("embedded tooth root radius must be positive")
    rr_embed = fmt(root_r_in - _TOOTH_EMBED_MM / IN)
    gamma = facts["Gamma"]
    theta_lo = facts["ThetaU"] + eps + rho          # tip arc start (flank A @ Ra)
    theta_hi = gamma + facts["ThetaL"] - eps + rho  # tip arc end (flank B @ Ra)
    a_lo = facts["Gamma"] - facts["Delta"] + eps + rho  # flank A base azimuth
    a_hi = gamma + facts["Delta"] - eps + rho           # flank B base azimuth
    foot_inv = tmin - math.atan(tmin)
    foot_r = fmt(max(facts["Rb"], root_r_in))
    foot_lo, foot_hi = a_lo + foot_inv, a_hi - foot_inv
    u = f"({fmt(tmin)} + {fmt(facts['Tmax'] - tmin)} * t)"
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
            f"({foot_r} + t * ({rr_embed} - {foot_r})) * {fmt(math.cos(foot_hi))}",
            f"({foot_r} + t * ({rr_embed} - {foot_r})) * {fmt(math.sin(foot_hi))}",
        ),
        await equation_curve(
            adapter,
            "embedded root arc B->A",
            f"{rr_embed} * cos({fmt(foot_hi)} + t * ({fmt(foot_lo)} - {fmt(foot_hi)}))",
            f"{rr_embed} * sin({fmt(foot_hi)} + t * ({fmt(foot_lo)} - {fmt(foot_hi)}))",
        ),
        await equation_curve(
            adapter,
            "lower root extension embed->A",
            f"({rr_embed} + t * ({foot_r} - {rr_embed})) * {fmt(math.cos(foot_lo))}",
            f"({rr_embed} + t * ({foot_r} - {rr_embed})) * {fmt(math.sin(foot_lo))}",
        ),
    ]
    await ensure_fully_defined(
        adapter, "tooth sketch", fix_entities=tooth_curves, allow_fix_escalation=True
    )
    check("exit_sketch tooth", await adapter.exit_sketch())
    return await _sweep_tooth_sketch(adapter, face_width, twist_deg=twist_deg)


async def _sweep_tooth_sketch(
    adapter: Any, face_width: float, *, twist_deg: float
) -> str:
    """Sweep the current closed tooth sketch along the existing +Z axis path."""
    from solidworks_mcp.adapters.base import SweepParameters


    # Path: a fully-defined line up the gear axis (origin coincidence +
    # vertical + one length dim -- the build_vn_boss_hook recipe).
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
    pa_deg: float = PA_DEG,
    *,
    helix_deg: float = 0.0,
    backlash_mm: float = 0.0,
    root_relief: bool = False,
    depth_dp: float | None = None,
    long_addendum_mm: float = 0.0,
    dedendum: float = 1.157,
    profile_shift: float = 0.0,
) -> ToothedDisc:
    """Build a toothed disc on the active new part.

    Gear axis = Z through the origin, disc z = 0..face_width (mm). Returns
    the volume-checked toothed-disc volume in mm^3 and the tooth features'
    names as created (seed, then pattern).

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
    chord to a root arc at pitch_r - dedendum/depth_dp --
    REQUIRED on any gear meshing a small pinion (and by the helix path,
    whose additive area algebra needs the arc floor): the stock base-circle
    floor leaves a 16T's mate 0.7 mm shy of working depth.
    ``depth_dp`` is the DP whose standard addendum (1/depth_dp) and dedendum
    (dedendum/depth_dp) set the tooth depth; it defaults to ``dp``. A helical
    gear cut by a normal-plane cutter passes its TRANSVERSE ``dp`` and
    ``pa_deg`` (they place the involute) and the cutter's DP here: the cutter
    cuts its own depth whichever plane the profile is read in.
    ``long_addendum_mm`` turns the blank's tip that much over the standard
    addendum and leaves the root where the cutter's depth puts it.
    ``dedendum`` is the root-relief depth below the pitch circle in units of
    1/depth_dp: the legacy 14.5-degree 1.157, or an explicit 1.25 for the
    standard 20-degree train and the feed-pinion sleeve.
    ``profile_shift`` is the generating-rack coefficient x: it thickens the
    reference-circle tooth by 2*x*m*tan(PA) and raises both tip and root by
    x*m, with m = 1/depth_dp. It is not a centre-distance-only correction.
    """
    depth_dp = dp if depth_dp is None else depth_dp
    shift_in = profile_shift / depth_dp
    addendum_extra_in = 1.0 / depth_dp - 1.0 / dp + long_addendum_mm / IN + shift_in
    facts = gear_facts(teeth, dp, pa_deg, addendum_extra_in=addendum_extra_in)
    ra_mm = facts["Ra"] * IN
    pitch_r_in = teeth / dp / 2.0
    shift_thickness_in = 2.0 * shift_in * math.tan(math.radians(pa_deg))
    widen_rad = (backlash_mm / IN - shift_thickness_in) / (2.0 * pitch_r_in)
    root_r_in = (pitch_r_in - dedendum / depth_dp + shift_in) if root_relief else None
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
        teeth, dp=dp, pa_deg=pa_deg, widen_rad=widen_rad, root_r_in=root_r_in,
        addendum_extra_in=addendum_extra_in,
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

    pattern = await pattern_about_z(adapter, seeds, teeth, ra_mm, face_width / 2.0)
    volume = await volume_check(adapter, "toothed disc", v_gear, 0.01 * v_gear)
    return ToothedDisc(volume, (*seeds, str(pattern.name)))


async def build_stock_form_gear(
    adapter: Any,
    profile: StockFormProfile,
    face_width: float,
    *,
    rotate_rad: float | None = None,
    screw_sweep_bound_mm: float | None = None,
) -> ToothedDisc:
    """Author a disc from its actual finite translated stock-tool profile.

    Spur profiles cut one gap through the blank. Helical profiles sweep the
    complete material sector, including the translated root-floor lobes.
    Both routes pattern the physical count and consume the core area oracle.
    ``rotate_rad`` locates the gap bisector at mid-face; its default pi/N
    retains a tooth centred on +X. This is the nominal normal-section screw
    sweep, not a claim about the envelope of a finite disc cutter.
    Helical callers must pass ``screw_sweep_bound_mm``, the native flank
    distance their own spec derives from its documented error budget; the
    shared tier owns no tolerance.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    if profile.helix_angle_deg:
        if screw_sweep_bound_mm is None:
            raise ValueError("helical stock-form gear requires screw_sweep_bound_mm")
        return await _build_helical_stock_form_gear(
            adapter, profile, face_width, rotate_rad=rotate_rad,
            sweep_bound_mm=screw_sweep_bound_mm,
        )
    if not math.isfinite(face_width) or face_width <= 0.0:
        raise ValueError("stock-form gear face width must be positive and finite")
    rotation = math.pi / profile.teeth if rotate_rad is None else rotate_rad
    cosine, sine = fmt(math.cos(rotation)), fmt(math.sin(rotation))
    radius = profile.blank_radius_mm
    clearance = max(R_CLEAR_IN * IN, radius + 1.0)
    # Main's cut_tooth_gap creation order and fix escalation, role for role.
    segments = profile.cut_order_native_segments(
        unit_scale=1.0 / IN, clearance_radius_mm=clearance
    )
    gap_area = profile.gap_area_mm2
    blank_area = math.pi * radius**2
    if not 0.0 < profile.teeth * gap_area < blank_area:
        raise ValueError("stock-form gaps must leave positive toothed-disc material")

    check("create_sketch stock blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, radius, "gear blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch stock blank", await adapter.exit_sketch())
    check(
        "extrude stock blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=face_width)),
    )
    blank_volume = blank_area * face_width
    await volume_check(adapter, "blank", blank_volume, 0.005 * blank_volume)

    check("create_sketch stock gap", await adapter.create_sketch("Front"))
    gap_curves = []
    for segment in segments:
        gap_curves.append(
            await equation_curve(
                adapter,
                segment.name,
                f"({segment.x}) * {cosine} - ({segment.y}) * {sine}",
                f"({segment.x}) * {sine} + ({segment.y}) * {cosine}",
            )
        )
    await ensure_fully_defined(
        adapter, "stock gap sketch", fix_entities=gap_curves, allow_fix_escalation=True
    )
    check("exit_sketch stock gap", await adapter.exit_sketch())
    seed = check(
        "cut stock tooth gap",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=face_width + 1.0)),
    )
    seeded_volume = blank_volume - gap_area * face_width
    expected_volume = blank_volume - profile.teeth * gap_area * face_width
    await volume_check(adapter, "seeded tooth/gap", seeded_volume, 1.0)
    pattern = await pattern_about_z(
        adapter, seed.name, profile.teeth, radius, face_width / 2.0
    )
    volume = await volume_check(
        adapter, "toothed disc", expected_volume, 0.01 * expected_volume
    )
    return ToothedDisc(volume, (seed.name, str(pattern.name)))


async def _build_helical_stock_form_gear(
    adapter: Any,
    profile: StockFormProfile,
    face_width: float,
    *,
    rotate_rad: float | None,
    sweep_bound_mm: float,
) -> ToothedDisc:
    """Sweep one actual finite stock tooth onto a cylinder through its feet.

    Farm run 20261009T214825987Z: the whole-pitch material sector made each
    patterned copy share its twisted seam faces with both neighbours, and
    the circular pattern failed. Main's helical recipe (``boss_tooth_swept``)
    patterns a tooth that never touches its neighbours; this does the same
    with the stock profile. The gap floor between teeth becomes the
    foot-radius cylinder instead of the translated root arc, so refuse when
    the two differ by more than ``_ROOT_CYLINDER_BOUND_MM``.
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    if not math.isfinite(face_width) or face_width <= 0.0:
        raise ValueError("stock-form gear face width must be positive and finite")
    root_spread = profile.root_radius_max_mm - profile.root_radius_min_mm
    if root_spread > _ROOT_CYLINDER_BOUND_MM:
        raise ValueError(
            f"stock root arc departs {root_spread:.4f} mm from a cylinder;"
            f" the swept-tooth recipe allows {_ROOT_CYLINDER_BOUND_MM} mm"
        )
    base_radius = profile.foot_radius_mm
    gap_area = profile.gap_area_mm2
    blank_area = math.pi * profile.blank_radius_mm**2
    base_area = math.pi * base_radius**2
    tooth_area = (blank_area - base_area) / profile.teeth - gap_area
    if not math.isfinite(tooth_area) or tooth_area <= 0.0:
        raise ValueError("stock-form tooth must leave positive material")
    twist_rad = (
        face_width * math.tan(math.radians(profile.helix_angle_deg))
        / profile.pitch_radius_mm
    )
    midface_phase = (
        0.0 if rotate_rad is None else rotate_rad - math.pi / profile.teeth
    )
    segments = profile.tooth_body_segments(
        unit_scale=1.0 / IN,
        embed_radius_mm=base_radius - _TOOTH_EMBED_MM,
        rotate_rad=midface_phase - twist_rad / 2.0,
    )
    check("create_sketch stock base", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, base_radius, "gear blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch stock base", await adapter.exit_sketch())
    check(
        "extrude stock base",
        await adapter.create_extrusion(ExtrusionParameters(depth=face_width)),
    )
    base_volume = base_area * face_width
    await volume_check(adapter, "blank", base_volume, 0.005 * base_volume)

    check("create_sketch stock tooth", await adapter.create_sketch("Front"))
    curves = [
        await equation_curve(adapter, segment.name, segment.x, segment.y)
        for segment in segments
    ]
    await ensure_fully_defined(
        adapter, "stock tooth", fix_entities=curves, allow_fix_escalation=True
    )
    check("exit_sketch stock tooth", await adapter.exit_sketch())
    name_last_feature(adapter, "StockToothProfile")
    seed = await _sweep_tooth_sketch(
        adapter, face_width, twist_deg=math.degrees(twist_rad)
    )
    # gap_area below the foot circle (the root dip) is at most root_spread
    # deep over one gap: < 0.005 mm * 2 mm * face, far inside the 1 mm^3 gate.
    seeded_volume = base_volume + tooth_area * face_width
    await volume_check(adapter, "seeded tooth/gap", seeded_volume, 1.0)
    assert_stock_screw_sweep_phase(
        adapter, profile, face_width, midface_tooth_phase_rad=midface_phase,
        tolerance_mm=sweep_bound_mm,
    )
    pattern = await pattern_about_z(
        adapter, seed, profile.teeth, profile.blank_radius_mm, face_width / 2.0
    )
    expected_volume = (blank_area - profile.teeth * gap_area) * face_width
    volume = await volume_check(
        adapter, "toothed disc", expected_volume, 0.01 * expected_volume
    )
    return ToothedDisc(volume, (seed, str(pattern.name)))


def _stock_flank_samples(profile: Any) -> tuple[tuple[int, float, tuple[float, float]], ...]:
    """Sample the core's actual blank-clipped finite flank, never extrapolate it."""
    low = profile.flank_parameter_min
    high = profile.flank_parameter_max
    if high <= low:
        raise ValueError("stock screw sweep has no active finite flank interval")
    return tuple(
        (side, parameter, profile.flank_point(parameter, side=side))
        for side in (-1, 1)
        for parameter in (
            low + (high - low) / 4.0,
            low + 3.0 * (high - low) / 4.0,
        )
    )


def assert_stock_screw_sweep_phase(
    adapter: Any,
    profile: Any,
    face_width: float,
    *,
    midface_tooth_phase_rad: float = 0.0,
    tolerance_mm: float,
) -> None:
    """Measure actual solid flank points at quarter/mid-face stations.

    Volume cannot distinguish the wrong hand, no twist, or a wrong phase.
    Query trimmed native faces, not the input sketch or sweep's option bag.
    ``tolerance_mm`` is the caller's native sweep-fidelity bound (the twisted
    sweep's surface sag), not a machining band. A wrong hand, missing twist or
    wrong phase displaces the quarter-face flank by tenths of a millimetre.
    """
    if not math.isfinite(tolerance_mm) or tolerance_mm <= 0.0:
        raise ValueError("stock screw-sweep tolerance must be positive and finite")
    if not math.isfinite(face_width) or face_width <= 0.0:
        raise ValueError("stock screw-sweep face width must be positive and finite")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())
    if len(bodies) != 1:
        raise RuntimeError(f"stock screw sweep requires one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    faces = tuple(_early_bound(face, "IFace2") for face in (body.GetFaces() or ()))
    if not faces:
        raise RuntimeError("stock screw sweep has no native faces")
    twist_per_mm = (
        math.tan(math.radians(profile.helix_angle_deg)) / profile.pitch_radius_mm
    )
    samples = _stock_flank_samples(profile)
    records = []
    mismatches = []
    for fraction in (0.25, 0.5, 0.75):
        z = face_width * fraction
        phase = midface_tooth_phase_rad + (z - face_width / 2.0) * twist_per_mm
        for side, parameter, (x, y) in samples:
            # A seed tooth lies between two gaps: its lower flank is the
            # upper flank of gap -pi/N, and conversely for its upper flank.
            angle = phase - side * math.pi / profile.teeth
            cosine, sine = math.cos(angle), math.sin(angle)
            expected = (x * cosine - y * sine, x * sine + y * cosine, z)
            nearest = None
            distance = math.inf
            for face in faces:
                raw = face.GetClosestPointOn(*(value / 1000.0 for value in expected))
                if raw is None or len(raw) != 5:
                    raise RuntimeError("stock screw-sweep native closest-point query failed")
                candidate = tuple(float(value) * 1000.0 for value in raw[:3])
                if not all(math.isfinite(value) for value in candidate):
                    raise RuntimeError("stock screw-sweep native closest point is nonfinite")
                candidate_distance = math.dist(expected, candidate)
                if candidate_distance < distance:
                    distance, nearest = candidate_distance, candidate
            records.append(
                {
                    "face_fraction": fraction,
                    "flank_side": side,
                    "flank_parameter": parameter,
                    "expected_xyz_mm": expected,
                    "native_xyz_mm": nearest,
                    "distance_mm": distance,
                }
            )
            if distance > tolerance_mm:
                mismatches.append(
                    f"z/face={fraction:g}, side={side}, u={parameter:.9g}: "
                    f"native flank distance {distance:.9g} mm"
                )
    _telemetry.info(
        "crank.stock_screw_sweep_phase "
        + json.dumps(
            {
                "physical_teeth": profile.teeth,
                "reference_teeth": profile.template.reference_teeth,
                "helix_angle_deg": profile.helix_angle_deg,
                "tolerance_mm": tolerance_mm,
                "points": records,
            },
            sort_keys=True,
        )
    )
    if mismatches:
        raise RuntimeError("stock screw-sweep phase mismatch: " + "; ".join(mismatches))
