"""Offline installation proof for the photographed fixture and its wire departure."""

from __future__ import annotations

import math

import pytest

import build_mg_magnifier_assembly as assembly
import vn_lever_wire_geom as wire
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
    assert math.isclose(
        assembly.VROD_Z, fixture.VROD_Z, rel_tol=0.0, abs_tol=1e-9
    )
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
    from _interference_contracts import (
        _MG_FIXTURE_THREAD_TRIPLE_MM,
        _MG_LEVER_PRESS_TRIPLE_MM,
        allowed_interference_pairs,
    )
    from _hole_spec import TAP_DRILL_MM
    from _mcmaster_91882a221 import SHANK_DIA
    from mg_lever_press_fit_geom import COLLAR_BORE_DIA, COLLAR_ENGAGEMENT_MAX, PRESS_ZONE_DIA

    # Shared runtime contracts must stay independent of the pose-bearing owners.
    # Pin the literals here instead of importing those owners into every assembly.
    owned_thread = (SHANK_DIA, TAP_DRILL_MM["#4-40"], fixture.TAP_LENGTH)
    owned_press = (PRESS_ZONE_DIA, COLLAR_BORE_DIA, COLLAR_ENGAGEMENT_MAX)
    # The nominal cylinder stays 7; the independently pinned print envelope
    # includes the partial hemisphere still larger than the collar bore.
    for literal, owned in (
        (_MG_FIXTURE_THREAD_TRIPLE_MM, owned_thread),
        (_MG_LEVER_PRESS_TRIPLE_MM, owned_press),
    ):
        assert all(
            math.isclose(a, b, rel_tol=0.0, abs_tol=1e-12)
            for a, b in zip(literal, owned, strict=True)
        )
    assert _MG_LEVER_PRESS_TRIPLE_MM == (6.0, 5.986, 7.2078194326718075)
    pairs = allowed_interference_pairs("mg-magnifier")
    top = allowed_interference_pairs("ha-harmonic-analyzer")
    expected = {
        pair: 1.10 * math.pi * (major**2 - bore**2) * length / 4.0
        for pair, (major, bore, length) in (
            (frozenset(("vn-thumb-screw-2", "mg-output-fixture-1")), owned_thread),
            (
                frozenset(("mg-magnifying-lever-1", "mg-magnifying-bracket-1")),
                owned_press,
            ),
        )
    }
    for pair, limit in expected.items():
        assert math.isclose(pairs[pair], limit, abs_tol=1e-12)
        qualified = frozenset(f"mg-magnifier-1/{name}" for name in pair)
        assert math.isclose(top[qualified], limit, abs_tol=1e-12)
    press_pair = frozenset(("mg-magnifying-lever-1", "mg-magnifying-bracket-1"))
    assert pairs[press_pair] == pytest.approx(
        1.0449337917515231, rel=0.0, abs=1e-12
    )
    top_press_pair = frozenset(f"mg-magnifier-1/{name}" for name in press_pair)
    assert top[top_press_pair] == pytest.approx(
        1.0449337917515231, rel=0.0, abs=1e-12
    )
    assert frozenset(("vn-thumb-screw-2", "mg-magnifying-vertical-rod-1")) not in pairs


_PRESS_BUDGET_KEYS = {
    "interference_nominal",
    "interference_min",
    "interference_max",
    "engagement",
    "strength_outer_diameter_mm",
    "strength_contact_pressure_mpa",
    "collar_hoop_mpa",
    "collar_von_mises_mpa",
    "force_outer_diameter_mm",
    "contact_pressure_mpa",
    "press_force_min_n",
    "press_force_max_n",
}


def _lame_steel_collar_on_brass_rod(
    interference: float, outer_diameter: float
) -> tuple[float, float, float]:
    """Independent oracle: free-axial Lamé, solid Ø6 brass rod (E 97000, nu
    0.34) in a 1018 steel collar (E 200000, nu 0.29). Returns the contact
    pressure, the bore hoop stress and the bore von Mises stress, MPa."""
    d, od = 6.0, outer_diameter
    ratio = (od**2 + d**2) / (od**2 - d**2)
    pressure = interference / (d * ((1.0 - 0.34) / 97000.0 + (ratio + 0.29) / 200000.0))
    hoop, radial = pressure * ratio, -pressure
    return pressure, hoop, math.sqrt(hoop**2 + radial**2 - hoop * radial)


def _hemisphere_contact_length(
    collar_length: float, rod_dia: float, bore_dia: float
) -> float:
    """Independent physical-part oracle from the dome's circular meridian.

    At the bore crossing, its radial projection is R*cos(angle) = bore/2,
    so the axial extension past the cylinder tangent is R*sin(angle).
    One rod radius governs both the cylinder length and this partial dome.
    """
    radius = rod_dia / 2.0
    angle = math.acos(bore_dia / rod_dia)
    return collar_length - radius + radius * math.sin(angle)


def test_dome_contact_exceeds_cylinder_only_bound_at_printed_corners() -> None:
    import mg_lever_press_fit_geom as press

    # This is one physical tight-corner rod, not the independent-radius envelope.
    tight_contact = _hemisphere_contact_length(10.0, 6.0, 5.986)
    assert tight_contact == pytest.approx(7.204819432671807, rel=0.0, abs=1e-12)
    assert 7.003 < tight_contact < press.COLLAR_ENGAGEMENT_MAX
    assert tight_contact <= press.PRESS_FIT_BUDGET["engagement"]

    # All eight coupled corners retain partial-dome contact. The independently
    # combined min-radius cylinder / max-radius dome must bound every one.
    contacts = [
        _hemisphere_contact_length(length, rod, bore)
        for length in (9.95, 10.0)
        for rod in (5.994, 6.0)
        for bore in (5.986, 5.992)
    ]
    assert max(contacts) == pytest.approx(tight_contact, rel=0.0, abs=1e-12)
    assert all(contact <= press.COLLAR_ENGAGEMENT_MAX for contact in contacts)
    assert all(contact <= press.PRESS_FIT_BUDGET["engagement"] for contact in contacts)
    assert press.COLLAR_ENGAGEMENT_MAX == pytest.approx(
        7.2078194326718075, rel=0.0, abs=1e-12
    )


def test_light_press_budget_is_the_lame_collar_inside_strength() -> None:
    import build_mg_magnifying_bracket as bracket
    import mg_lever_press_fit_geom as press
    import mg_magnifying_bracket_spec as bracket_spec
    from _printed_tolerance import printed_band_mm

    # The approved LIGHT PRESS and its physics inputs, pinned.
    assert press.PRESS_ZONE_DIA == 6.0
    assert press.PRESS_ZONE_DIA_BAND == (0.0, -0.006)
    assert press.COLLAR_BORE_DIA == 5.986
    assert press.COLLAR_BORE_BAND == (0.006, 0.0)
    assert press.COLLAR_ENGAGEMENT == 7.0
    assert press.COLLAR_LENGTH == 10.0
    assert press.COLLAR_LENGTH_BAND == (0.0, -0.05)
    assert press.PRESS_ZONE_LENGTH_BAND == (0.0, -0.05)
    assert press.COLLAR_ENGAGEMENT_MAX == pytest.approx(
        7.2078194326718075, rel=0.0, abs=1e-12
    )
    assert press.PRESS_INTERFERENCE_MAX_FN2 == pytest.approx(0.0254)
    assert press.COLLAR_OD == 12.0
    assert bracket.COLLAR_OD == press.COLLAR_OD  # the Lamé section is the modelled collar
    # CollarOd prints at two places with no native band, so its band is the
    # title block's inherited .XX row, restated (config-free) by the owner.
    od_places = bracket_spec.DRAWING_PRECISION["CollarProfile"]["CollarOd"]
    assert od_places == 2
    assert press.COLLAR_OD_BAND == (printed_band_mm(od_places), -printed_band_mm(od_places))
    assert press.COLLAR_OD_BAND == (0.51, -0.51)
    assert press.COLLAR_OD_MIN == pytest.approx(12.0 - 0.51, abs=1e-12)
    assert press.COLLAR_OD_MAX == pytest.approx(12.0 + 0.51, abs=1e-12)
    assert (press.ROD_E_MPA, press.ROD_POISSON) == (97000.0, 0.34)
    assert (press.COLLAR_E_MPA, press.COLLAR_POISSON) == (200000.0, 0.29)
    assert press.COLLAR_YIELD_MPA == 370.0
    assert press.STRENGTH_UTILIZATION == 0.9
    assert press.COLLAR_STRESS_LIMIT_MPA == pytest.approx(333.0)
    assert press.PRESS_FRICTION == (0.10, 0.15)

    budget = press.PRESS_FIT_BUDGET
    assert budget == press.press_fit_budget()
    assert set(budget) == _PRESS_BUDGET_KEYS
    assert all(type(value) is float for value in budget.values())

    # Corners restated from the printed limits, not from the owner's arithmetic.
    loosest = (6.000 - 0.006) - (5.986 + 0.006)
    tightest = 6.000 - 5.986
    assert budget["interference_nominal"] == pytest.approx(0.014, abs=1e-12)
    assert budget["interference_min"] == pytest.approx(loosest, abs=1e-12)
    assert budget["interference_max"] == pytest.approx(tightest, abs=1e-12)
    assert budget["interference_min"] == pytest.approx(0.002, abs=1e-12)
    assert budget["interference_max"] == pytest.approx(0.014, abs=1e-12)
    # Independent radius corners: longest cylinder at Rmin, longest dome at
    # Rmax in the smallest bore, not the coupled contact of one physical rod.
    contact_envelope = (
        10.0 - (6.0 - 0.006) / 2.0
        + math.sqrt((6.0 / 2.0)**2 - (5.986 / 2.0)**2)
    )
    assert budget["engagement"] == pytest.approx(contact_envelope, rel=0.0, abs=1e-12)

    # Independently conservative OD corners, each at the tightest interference:
    # the thinnest wall for bore stress, the stiffest wall for pressure/force.
    strength_od, force_od = 12.0 - 0.51, 12.0 + 0.51
    assert budget["strength_outer_diameter_mm"] == pytest.approx(strength_od, abs=1e-12)
    assert budget["force_outer_diameter_mm"] == pytest.approx(force_od, abs=1e-12)
    strength_pressure, hoop, von_mises = _lame_steel_collar_on_brass_rod(tightest, strength_od)
    pressure, _, _ = _lame_steel_collar_on_brass_rod(tightest, force_od)
    seat_area = math.pi * 6.0 * contact_envelope
    dome_normal = pressure * math.pi * ((6.0 / 2.0)**2 - (5.986 / 2.0)**2)
    assert budget["strength_contact_pressure_mpa"] == pytest.approx(strength_pressure, rel=1e-12)
    assert budget["collar_hoop_mpa"] == pytest.approx(hoop, rel=1e-12)
    assert budget["collar_von_mises_mpa"] == pytest.approx(von_mises, rel=1e-12)
    assert budget["contact_pressure_mpa"] == pytest.approx(pressure, rel=1e-12)
    assert budget["press_force_min_n"] == pytest.approx(
        0.10 * pressure * seat_area + dome_normal, rel=1e-12
    )
    assert budget["press_force_max_n"] == pytest.approx(
        0.15 * pressure * seat_area + dome_normal, rel=1e-12
    )
    # Hand-worked values, so a shared slip in both formulas still fails.
    assert budget["engagement"] == pytest.approx(
        7.2078194326718075, rel=0.0, abs=1e-12
    )
    assert budget["strength_contact_pressure_mpa"] == pytest.approx(137.227951, abs=1e-6)
    assert budget["collar_hoop_mpa"] == pytest.approx(240.127370, abs=1e-6)
    assert budget["collar_von_mises_mpa"] == pytest.approx(330.824502, abs=1e-6)
    assert budget["contact_pressure_mpa"] == pytest.approx(143.663360, abs=1e-6)
    assert budget["press_force_min_n"] == pytest.approx(
        1970.80450425121, rel=0.0, abs=1e-9
    )
    assert budget["press_force_max_n"] == pytest.approx(
        2946.7398471054526, rel=0.0, abs=1e-9
    )

    # Across the whole inherited OD band, no diameter beats either corner:
    # bore stress peaks at the thinnest wall, contact pressure at the stiffest.
    sweep = [
        _lame_steel_collar_on_brass_rod(tightest, strength_od + (force_od - strength_od) * i / 200)
        for i in range(201)
    ]
    assert max(row[2] for row in sweep) == pytest.approx(budget["collar_von_mises_mpa"], rel=1e-12)
    assert max(row[0] for row in sweep) == pytest.approx(budget["contact_pressure_mpa"], rel=1e-12)
    assert budget["strength_contact_pressure_mpa"] < budget["contact_pressure_mpa"]

    # Every guard holds at the printed fit.
    assert budget["interference_min"] > 0.0
    assert budget["interference_max"] <= 0.0010 * 25.4
    assert budget["collar_von_mises_mpa"] < 0.9 * 370.0
    assert 0.9 * 370.0 - budget["collar_von_mises_mpa"] == pytest.approx(2.175498, abs=1e-6)
    press.check_press_fit_budget(budget)
    assert press.PRESS_FORCE_MAX_KN == 3.0
    assert budget["press_force_max_n"] <= 1000.0 * press.PRESS_FORCE_MAX_KN


def test_press_guard_rejects_a_fit_that_yields_the_collar() -> None:
    import mg_lever_press_fit_geom as press

    # The superseded medium press (Ø5.976 +0.008/0 bore on a 0/-0.008 rod),
    # evaluated through the owner's keyword inputs: its constants stay put.
    heavy = press.press_fit_budget(
        press_zone_dia_band=(0.0, -0.008),
        collar_bore_dia=5.976,
        collar_bore_band=(0.008, 0.0),
    )
    # It clears the slip and FN2 guards, so only strength can refuse it.
    assert heavy["interference_min"] == pytest.approx(0.008, abs=1e-12)
    assert heavy["interference_max"] == pytest.approx(0.024, abs=1e-12)
    heavy_contact_envelope = (
        10.0 - (6.0 - 0.008) / 2.0
        + 3.0 * math.sin(math.acos(5.976 / 6.0))
    )
    assert heavy["engagement"] == pytest.approx(
        heavy_contact_envelope, rel=0.0, abs=1e-12
    )
    assert heavy["interference_max"] <= 0.0010 * 25.4
    # Judged at the inherited band's thinnest-wall strength corner, Ø11.49.
    assert heavy["strength_outer_diameter_mm"] == pytest.approx(12.0 - 0.51, abs=1e-12)
    _, _, von_mises = _lame_steel_collar_on_brass_rod(6.000 - 5.976, 12.0 - 0.51)
    assert heavy["collar_von_mises_mpa"] == pytest.approx(von_mises, rel=1e-12)
    assert von_mises == pytest.approx(567.128, abs=1e-3)
    assert von_mises >= 0.9 * 370.0
    with pytest.raises(AssertionError, match="yield"):
        press.check_press_fit_budget(heavy)

    # Each of the other guards refuses on its own key.
    slips = {**press.PRESS_FIT_BUDGET, "interference_min": 0.0}
    with pytest.raises(AssertionError, match="loosest"):
        press.check_press_fit_budget(slips)
    over_fn2 = {**press.PRESS_FIT_BUDGET, "interference_max": 0.0255}
    with pytest.raises(AssertionError, match="FN2"):
        press.check_press_fit_budget(over_fn2)

    # Probing candidates left the printed budget untouched.
    assert press.PRESS_FIT_BUDGET == press.press_fit_budget()
    assert press.PRESS_FIT_BUDGET["interference_max"] == pytest.approx(0.014, abs=1e-12)


@pytest.mark.parametrize("bore_dia", (6.0, 6.010))
def test_candidate_slip_guard_handles_zero_or_absent_dome_contact(bore_dia: float) -> None:
    import mg_lever_press_fit_geom as press

    # Equal/oversize bores still produce a budget for the existing slip guard;
    # no partial dome exists and no negative square-root argument is evaluated.
    slips = press.press_fit_budget(collar_bore_dia=bore_dia)
    assert slips["interference_min"] < 0.0
    assert slips["interference_max"] <= 0.0
    assert slips["engagement"] == pytest.approx(7.003, rel=0.0, abs=1e-12)
    seat_area = math.pi * press.PRESS_ZONE_DIA * slips["engagement"]
    for friction, force_key in zip(
        press.PRESS_FRICTION, ("press_force_min_n", "press_force_max_n"), strict=True
    ):
        # The absent dome contributes no normal term, even for rejected fits.
        assert slips[force_key] == pytest.approx(
            friction * slips["contact_pressure_mpa"] * seat_area, rel=0.0, abs=1e-9
        )
    with pytest.raises(AssertionError, match="loosest"):
        press.check_press_fit_budget(slips)
    assert press.PRESS_FIT_BUDGET == press.press_fit_budget()


def test_total_press_force_includes_dome_axial_normal_bound() -> None:
    """Total press force includes full-envelope friction plus the full-pressure
    projected-dome axial normal bound, both within the derived shop ceiling."""
    import mg_lever_press_fit_geom as press

    radius_max = (press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[0]) / 2.0
    bore_radius_min = (press.COLLAR_BORE_DIA + press.COLLAR_BORE_BAND[1]) / 2.0
    projected_area = math.pi * (radius_max**2 - bore_radius_min**2)
    budget = press.PRESS_FIT_BUDGET
    axial_normal_bound = budget["contact_pressure_mpa"] * projected_area
    friction_bound = (
        press.PRESS_FRICTION[1] * budget["contact_pressure_mpa"]
        * math.pi * press.PRESS_ZONE_DIA * budget["engagement"]
    )
    total_force_bound = friction_bound + axial_normal_bound
    assert friction_bound == pytest.approx(
        2927.806028562728, rel=0.0, abs=1e-9
    )
    assert axial_normal_bound == pytest.approx(
        18.933818542724424, rel=0.0, abs=1e-9
    )
    assert total_force_bound == pytest.approx(
        2946.7398471054526, rel=0.0, abs=1e-9
    )
    assert budget["press_force_max_n"] == pytest.approx(
        total_force_bound, rel=0.0, abs=1e-9
    )
    assert press.PRESS_FORCE_MAX_KN == 3.0
    assert total_force_bound <= 1000.0 * press.PRESS_FORCE_MAX_KN


def test_press_instruction_rounds_force_up_and_keeps_the_rod_out_of_column_loading() -> None:
    import mg_lever_press_fit_geom as press

    maximum_kn = press.PRESS_FIT_BUDGET["press_force_max_n"] / 1000.0
    assert maximum_kn <= press.PRESS_FORCE_MAX_KN < maximum_kn + 0.1
    assert press.PRESS_FORCE_MAX_KN == 3.0
    lines = press.PRESS_INSTALLATION_NOTES.splitlines()
    assert len(lines) == 3
    assert "COLLAR ONTO LEVER; HOLD ROD NEAR END" in lines[0]
    assert "END FLUSH WITH OUTER FACE" in lines[1]
    assert f"{press.PRESS_FORCE_MAX_KN:.1f} kN MAX AT TIGHT FIT" in lines[1]
    assert "LOCTITE 638" in lines[2]
    assert "ALTERNATIVE: SOFT SOLDER OR BRAZE" in lines[2]
