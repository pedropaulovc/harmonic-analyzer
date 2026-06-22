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

from _common import IN, check, define_circle, ensure_fully_defined, volume_check
from build_cone_gear import gap_area_in_disc, gear_facts

import _telemetry

__all__ = ["build_fixed_gear", "cut_tooth_gap", "pattern_about_z", "volume_check"]

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
    adapter: Any, facts: dict[str, float], depth: float
) -> Any:
    """Cut one involute tooth gap through a blank (Front-plane sketch, +Z)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    rb, ra = fmt(facts["Rb"]), fmt(facts["Ra"])
    th_l, th_u = fmt(facts["ThetaL"]), fmt(facts["ThetaU"])
    rc = fmt(R_CLEAR_IN)
    u = f"({fmt(facts['Tmax'])} * t)"
    ph_low = f"({u} - {fmt(facts['Delta'])})"
    ph_up = f"({u} + {fmt(facts['Gamma'] - facts['Delta'])})"
    a1, a2 = facts["Delta"], facts["Gamma"] - facts["Delta"]
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
            "base chord A2->A1",
            f"{rb} * ((1 - t) * {fmt(math.cos(a2))} + t * {fmt(math.cos(a1))})",
            f"{rb} * ((1 - t) * {fmt(math.sin(a2))} + t * {fmt(math.sin(a1))})",
        ),
        await equation_curve(
            adapter,
            "lower radial extension B1->clearance",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.cos(facts['ThetaL']))}",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.sin(facts['ThetaL']))}",
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
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.cos(facts['ThetaU']))}",
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.sin(facts['ThetaU']))}",
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
    adapter: Any, seed_feature: str, count: int, radius_mm: float, z_mm: float
) -> Any:
    """Circular-pattern a seed feature about the Z axis through the origin.

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
    for point in candidates:
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point, features=[seed_feature], count=count
            )
        )
        if res.is_success:
            _telemetry.success(f"circular pattern axis via point {point}")
            return res
        _telemetry.debug(f"axis candidate {point} failed: {res.error}")
    raise RuntimeError("circular pattern: no axis candidate selectable")


async def build_fixed_gear(
    adapter: Any,
    teeth: int,
    face_width: float,
    dp: float = 30.0,
    pa_deg: float = 14.5,
) -> float:
    """Build a toothed disc (blank + gap + pattern) on the active new part.

    Gear axis = Z through the origin, disc z = 0..face_width (mm). Returns
    the volume-checked toothed-disc volume in mm^3.
    """
    facts = gear_facts(teeth, dp, pa_deg)
    ra_mm = facts["Ra"] * IN

    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, ra_mm, "gear blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=face_width)),
    )
    v_blank = math.pi * ra_mm**2 * face_width
    await volume_check(adapter, "blank", v_blank, 0.005 * v_blank)

    gap_cut = await cut_tooth_gap(adapter, facts, face_width + 1.0)
    await pattern_about_z(adapter, gap_cut.data.name, teeth, ra_mm, face_width / 2.0)

    v_gear = v_blank - teeth * gap_area_in_disc(teeth, dp=dp, pa_deg=pa_deg) * IN**2 * face_width
    return await volume_check(adapter, "toothed disc", v_gear, 0.01 * v_gear)
