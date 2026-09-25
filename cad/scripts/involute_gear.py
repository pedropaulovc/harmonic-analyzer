r"""Involute gear math and equation-manager helpers shared by the gear builders.

The cone gear, cylinder gear, alignment pinion, removable transgear and the
``_gear`` fixed-gear helper all cut the same tooth system: involute flanks at
the train's diametral pitch and 14.5 deg pressure angle, closed by a chord at
the base circle.  This module owns that math (``gear_facts`` mirrors the
equation-manager globals; ``gap_area_in_disc`` is the exact volume
expectation) and the SolidWorks equation-manager helpers that round-trip it,
so a gear builder no longer imports another gear's part script.

Lengths are INCHES: the configured part template is IPS, and the equation
manager evaluates trig in DEGREES (see ``build_cone_gear`` for the live
probes).

``thicken_in`` and ``addendum_extra_in`` default to the standard full-depth
proportions.  The cone gear uses them for its deepened mesh: an oversize tip
circle (long addendum) and a thicker circular tooth at the standard pitch
circle, which moves both flanks outward about the tooth centre.

The gap floor joins the two flank feet.  ``tmin`` starts the flanks at that
involute parameter instead of on the base circle, which raises the floor;
``floor_dip_in`` bows the floor below the straight chord by that much at the
gap centre, as a parabola through both feet.  Both default to 0: the plain
base-circle chord.
"""

from __future__ import annotations

import math
from typing import Any

import _config
import _telemetry
from _common import _early_bound, _read_member, check

DP = _config.machine("gear_train", "diametral_pitch")  # cad/config/machine.yaml (DIMENSIONS.md ch12)
PA_DEG = 14.5  # pressure angle, period-typical assumption (low)

PI_LIT = "3.14159265358979"  # literal pi for equation-manager expressions


def gear_facts(
    teeth: int,
    dp: float = DP,
    pa_deg: float = PA_DEG,
    *,
    thicken_in: float = 0.0,
    addendum_extra_in: float = 0.0,
    tmin: float = 0.0,
    floor_dip_in: float = 0.0,
) -> dict[str, float]:
    """Python mirror of the equation-manager globals (lengths in inches).

    ``ToothThickness`` is the circular tooth thickness at the standard pitch
    circle; ``Delta`` is half the tooth's angular thickness at the base circle,
    ``ToothThickness / (2 r) + inv(PA)`` with ``r = teeth / (2 dp)``.
    """
    pa = math.radians(pa_deg)
    rb = teeth / dp * math.cos(pa) / 2.0
    ra = (teeth + 2.0) / dp / 2.0 + addendum_extra_in
    tmax = math.sqrt((ra / rb) ** 2 - 1.0)
    thickness = math.pi / (2.0 * dp) + thicken_in
    delta = thickness * dp / teeth + math.tan(pa) - pa
    gamma = 2.0 * math.pi / teeth
    return {
        "PArad": pa,
        "ToothThickness": thickness,
        "Rb": rb,
        "Ra": ra,
        "Tmax": tmax,
        "Delta": delta,
        "Gamma": gamma,
        "ThetaL": math.atan(tmax) - tmax + delta,
        "ThetaU": tmax - math.atan(tmax) - delta + gamma,
        "Tmin": tmin,
        "FloorDip": floor_dip_in,
    }


def involute_point(
    facts: dict[str, float], u: float, *, upper: bool
) -> tuple[float, float]:
    """Point at involute parameter ``u`` on a gap flank (inches).

    The lower flank is tooth 0's upper flank (mirrored involute from angle
    ``+Delta``); the upper flank is tooth 1's lower flank.
    """
    rb, delta = facts["Rb"], facts["Delta"]
    if upper:
        ph = u - delta + facts["Gamma"]
        return (
            rb * (math.cos(ph) + u * math.sin(ph)),
            rb * (math.sin(ph) - u * math.cos(ph)),
        )
    ph = u - delta
    return (
        rb * (math.cos(ph) + u * math.sin(ph)),
        rb * (u * math.cos(ph) - math.sin(ph)),
    )


def floor_point(facts: dict[str, float], s: float) -> tuple[float, float]:
    """Gap-floor point, ``s`` in [0, 1] from the upper foot to the lower foot."""
    upper = involute_point(facts, facts["Tmin"], upper=True)
    lower = involute_point(facts, facts["Tmin"], upper=False)
    dip = 4.0 * s * (1.0 - s) * facts["FloorDip"]
    half_gamma = facts["Gamma"] / 2.0
    return (
        (1.0 - s) * upper[0] + s * lower[0] - dip * math.cos(half_gamma),
        (1.0 - s) * upper[1] + s * lower[1] - dip * math.sin(half_gamma),
    )


def floor_radius(facts: dict[str, float]) -> float:
    """Minimum radius of the gap floor: its point on the gap centre line."""
    return math.hypot(*floor_point(facts, 0.5))


def gap_area_in_disc(
    teeth: int,
    samples: int = 2000,
    dp: float = DP,
    pa_deg: float = PA_DEG,
    *,
    thicken_in: float = 0.0,
    addendum_extra_in: float = 0.0,
    tmin: float = 0.0,
    floor_dip_in: float = 0.0,
) -> float:
    """Exact in-blank area of one tooth gap (in^2), by Green's theorem.

    Boundary: lower flank A1->B1, blank-rim arc B1->B2 at ``Ra`` (the
    beyond-rim part of the cut profile removes nothing), upper flank B2->A2
    reversed, gap floor A2->A1 -- the same parametrisations as the live
    equation curves, so the expected volume validates the involute shape,
    not just that "some" cut happened.
    """
    f = gear_facts(
        teeth,
        dp,
        pa_deg,
        thicken_in=thicken_in,
        addendum_extra_in=addendum_extra_in,
        tmin=tmin,
        floor_dip_in=floor_dip_in,
    )
    ra, tmax = f["Ra"], f["Tmax"]
    span = tmax - tmin
    pts: list[tuple[float, float]] = []
    for i in range(samples + 1):  # lower flank (mirrored involute)
        pts.append(involute_point(f, tmin + span * i / samples, upper=False))
    for i in range(1, samples + 1):  # rim arc ThetaL -> ThetaU
        th = f["ThetaL"] + (f["ThetaU"] - f["ThetaL"]) * i / samples
        pts.append((ra * math.cos(th), ra * math.sin(th)))
    for i in range(1, samples + 1):  # upper flank, reversed
        pts.append(
            involute_point(f, tmin + span * (samples - i) / samples, upper=True)
        )
    for i in range(1, samples):  # gap floor A2 -> A1
        pts.append(floor_point(f, i / samples))
    area = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


async def set_global_read(adapter: Any, name: str, expression: str) -> float:
    """Upsert a global variable and return the value SolidWorks evaluated."""
    from solidworks_mcp.adapters.base import SetGlobalVariableParameters

    res = await adapter.set_global_variable(
        SetGlobalVariableParameters(name=name, expression=expression)
    )
    data = check(f"global {name} = {expression}", res)
    value = data.get("value")
    if value is None:
        raise RuntimeError(f"global {name}: no evaluated value returned")
    return float(value)


async def set_global(adapter: Any, name: str, expression: str, expected: float) -> None:
    """Upsert a global variable and assert SolidWorks evaluated it correctly.

    The value round-trip is the live test of the equation parser (trig in
    DEGREES -- probed live, see ``build`` -- ``sqr`` = square root, literal-pi
    arithmetic); a mismatch means the expression dialect is wrong and every
    downstream curve would be silently bogus.
    """
    value = await set_global_read(adapter, name, expression)
    tol = max(1e-9, abs(expected) * 1e-6)
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"global {name}: SolidWorks evaluated {value!r}, expected "
            f"{expected:.9g} -- equation-parser dialect mismatch"
        )


async def equation_curve(
    adapter: Any, label: str, x_expr: str, y_expr: str
) -> str:
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


def pattern_count_dimension(adapter: Any, feature_name: str, expected: float) -> str:
    """Find the pattern's instance-count dimension name (``D?@<feature>``).

    The circular-pattern dimension layout (which of D1/D2 is the count vs
    the angle) is not documented stably across releases, so probe by value:
    the count dimension is the one reading ``expected`` (the seed count must
    differ from the 360-degree angle for this to be unambiguous).
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    for dim in ("D1", "D2", "D3", "D4"):
        full = f"{dim}@{feature_name}"
        param = adapter._attempt(lambda f=full: model.Parameter(f), default=None)
        if param is None:
            continue
        try:
            value = float(_read_member(param, "Value"))
        except (TypeError, ValueError):
            continue
        _telemetry.debug(f"{full} reads {value:g}")
        if abs(value - expected) < 1e-9:
            return full
    raise RuntimeError(
        f"no dimension of {feature_name} reads {expected:g} -- cannot link "
        "the instance count to ToothCount"
    )


def read_dimension(adapter: Any, full_name: str) -> float:
    """Read a dimension's value in the active configuration."""
    param = adapter._attempt(
        lambda: adapter.currentModel.Parameter(full_name), default=None
    )
    if param is None:
        raise RuntimeError(f"cannot read dimension {full_name}")
    return float(_read_member(param, "Value"))


