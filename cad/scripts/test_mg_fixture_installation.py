"""Offline installation proof for the photographed fixture and its wire departure."""

from __future__ import annotations

import math

import build_mg_magnifier_assembly as assembly
import mg_lever_wire_geom as wire
import mg_output_fixture_geom as fixture
from _mcmaster_91882a221 import HEAD_STACK_LEN, SHANK_LEN, THUMB_SPEC
from mg_magnifying_vertical_rod_geom import ROD_DIA


def _segment_distance(x: float, r: float, x0: float, x1: float, radius: float) -> float:
    nearest_x = min(x1, max(x0, x))
    return math.hypot(x - nearest_x, r - radius)


def _cylinder_distance(x: float, r: float, x0: float, x1: float, radius: float) -> float:
    """Distance to a capped cylinder; negative if the centreline enters its solid."""
    dx = max(x0 - x, 0.0, x - x1)
    dr = max(r - radius, 0.0)
    if dx == dr == 0.0:
        return -min(x - x0, x1 - x, radius - r)
    return math.hypot(dx, dr)


def fixture_wire_clearances(samples: int = 20001) -> dict[str, float]:
    """Sweep a wire-radius sphere down the actual installed centreline.

    Distance to each axisymmetric surface is exact in its axial/radial
    meridian. Hex stock and screw chamfers/knurls use enclosing cylinders,
    conservative for clearance. Half a sample interval is deducted using the
    1-Lipschitz distance bound, so a passing lower bound proves the unsampled
    portions clear too. The native farm gate remains the installed-solid proof.
    """
    if samples < 2:
        raise ValueError("at least two samples are required")
    rows = assembly.FIXTURE_ROWS
    delta_world = tuple(e - s for s, e in zip(wire.WIRE_START, wire.WIRE_END, strict=True))
    delta = tuple(sum(d * row[k] for k, d in enumerate(delta_world)) for row in rows)
    spigot_r = fixture.SPIGOT_DIA / 2.0
    groove_centre_r = fixture.GROOVE_ROOT_DIA / 2.0 + fixture.GROOVE_RADIUS
    theta_max = math.asin(fixture.GROOVE_HALF_OPENING / fixture.GROOVE_RADIUS)
    mouth0 = fixture.GROOVE_X - fixture.GROOVE_HALF_OPENING
    mouth1 = fixture.GROOVE_X + fixture.GROOVE_HALF_OPENING
    screw_tip = ROD_DIA / 2.0
    collar0 = screw_tip + SHANK_LEN
    head0 = collar0 + THUMB_SPEC["collar_h"]
    minima = {name: math.inf for name in ("groove", "spigot", "hex", "screw_shank", "screw_collar", "screw_head")}
    for index in range(samples):
        fraction = index / (samples - 1)
        x, y, z = (p + fraction * d for p, d in zip(fixture.HOOK_LOCAL, delta, strict=True))
        r = math.hypot(y, z)
        theta = math.atan2(x - fixture.GROOVE_X, groove_centre_r - r)
        theta = min(theta_max, max(-theta_max, theta))
        gx = fixture.GROOVE_X + fixture.GROOVE_RADIUS * math.sin(theta)
        gr = groove_centre_r - fixture.GROOVE_RADIUS * math.cos(theta)
        distances = {
            "groove": math.hypot(x - gx, r - gr),
            "spigot": min(
                _segment_distance(x, r, fixture.SHOULDER_X, mouth0, spigot_r),
                _segment_distance(x, r, mouth1, fixture.SPIGOT_FACE_X, spigot_r),
                _segment_distance(r, x, 0.0, spigot_r, fixture.SPIGOT_FACE_X),
            ),
            "hex": _cylinder_distance(x, r, -fixture.ROD_STATION, fixture.SHOULDER_X, fixture.HEX_AF / math.sqrt(3.0)),
            "screw_shank": _cylinder_distance(x, r, screw_tip, collar0, THUMB_SPEC["major_r"]),
            "screw_collar": _cylinder_distance(x, r, collar0, head0, THUMB_SPEC["collar_r"]),
            "screw_head": _cylinder_distance(x, r, head0, screw_tip + SHANK_LEN + HEAD_STACK_LEN, THUMB_SPEC["head_r"]),
        }
        for name, distance in distances.items():
            minima[name] = min(minima[name], distance - wire.WIRE_DIA / 2.0)
    interval = math.hypot(*delta_world) / (samples - 1)
    minima["minimum"] = min(minima.values())
    minima["proven_lower_bound"] = minima["minimum"] - interval / 2.0
    return minima


def test_fixture_hook_is_the_rotated_front_tangent() -> None:
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(assembly._HOOK_EXPECTED, wire.WIRE_START, strict=True))
    assert wire.HOOK_Z == fixture.HOOK_TARGET_Z
    assert wire.HOOK_Y == fixture.FIXTURE_AXIS_Y
    assert wire.HOOK_X < wire.CLAMP_X
    assert assembly.FIXTURE_ROWS[0][0] < 0.0
    assert assembly.FIXTURE_ROWS[0][2] > 0.0


def test_fixture_screw_tip_is_tangent_and_collar_is_backed_out() -> None:
    outer = assembly.FIXTURE_SCREW_OUTER_X
    assert math.isclose(outer - SHANK_LEN - HEAD_STACK_LEN, ROD_DIA / 2.0, abs_tol=1e-9)
    assert math.isclose(assembly.FIXTURE_SCREW_STANDOFF, ROD_DIA / 2.0 + SHANK_LEN - fixture.SPIGOT_FACE_X, abs_tol=1e-9)
    assert assembly.FIXTURE_SCREW_STANDOFF > 0.0
    for screw_row, fixture_row in zip(assembly.FIXTURE_SCREW_ROWS[0], assembly.FIXTURE_ROWS[0], strict=True):
        assert math.isclose(screw_row, -fixture_row, abs_tol=1e-9)


def test_departing_wire_clears_groove_flanks_spigot_and_screw() -> None:
    clearances = fixture_wire_clearances()
    print(f"fixture wire clearance mm: {clearances}")
    assert clearances["proven_lower_bound"] >= 0.0
    assert clearances["minimum"] >= wire.CLEARANCE - 1e-9


def test_new_overlap_pairs_are_exact_and_shared_with_top_assembly() -> None:
    from _interference_contracts import allowed_interference_pairs, _smooth_annulus_limit_mm3
    from _hole_spec import TAP_DRILL_MM
    from _mcmaster_91882a221 import SHANK_DIA
    from mg_lever_press_fit_geom import COLLAR_BORE_DIA, COLLAR_ENGAGEMENT, PRESS_ZONE_DIA

    pairs = allowed_interference_pairs("mg-magnifier")
    top = allowed_interference_pairs("ha-harmonic-analyzer")
    expected = {
        frozenset(("vn-thumb-screw-2", "mg-output-fixture-1")):
            _smooth_annulus_limit_mm3(SHANK_DIA, TAP_DRILL_MM["#4-40"], fixture.SPIGOT_FACE_X - ROD_DIA / 2.0),
        frozenset(("mg-magnifying-lever-1", "mg-magnifying-bracket-1")):
            _smooth_annulus_limit_mm3(PRESS_ZONE_DIA, COLLAR_BORE_DIA, COLLAR_ENGAGEMENT),
    }
    for pair, limit in expected.items():
        assert math.isclose(pairs[pair], limit, abs_tol=1e-12)
        qualified = frozenset(f"mg-magnifier-1/{name}" for name in pair)
        assert math.isclose(top[qualified], limit, abs_tol=1e-12)
    assert frozenset(("vn-thumb-screw-2", "mg-magnifying-vertical-rod-1")) not in pairs
