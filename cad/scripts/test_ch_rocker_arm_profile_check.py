"""Offline contracts for the rocker arm's surface-profile check (plan S7 op 97)."""

from __future__ import annotations

import copy
import importlib
import math
import re
import tomllib

import pytest

import _process_plans as plans
import _rocker_interface as rocker_interface
import ch_rocker_arm_profile_check as check
import ch_rocker_arm_spec as rocker
import export_features

STEM = "ch_rocker_arm"
_SHOP = tomllib.loads(
    (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
)
_INVENTORY = _SHOP["gauges"]


def _printed_zones() -> dict[str, tuple[float, float]]:
    """Each profiled feature's printed (t, U), from the exported manifest."""
    features = export_features.requirement_manifest(STEM)["features"]
    return {
        name: (fields["surface_profile"], fields["surface_profile_u"])
        for name, fields in features.items()
        if "surface_profile" in fields
    }


def _guard(point, normal) -> float:
    resolution = _INVENTORY["dti"]["resolution_in"]["value"] * 25.4
    return check.clocking_error(point, normal) + resolution


def _violations(windows: dict) -> list[str]:
    """Stations where an accepted reading, widened by the guard, could leave
    the printed zone (or touch its edge)."""
    zones = _printed_zones()
    found = []
    for name, segment in check.SEGMENTS.items():
        accept = windows[name]["accept"]
        for feature in segment["features"]:
            t, u = zones[feature]
            for point, normal in check.samples(name):
                tau = segment["tau"]((abs(point[0]), point[1]))
                low, high = tau - (t - u), tau + u
                guard = _guard(point, normal)
                if not (low < accept[0] - guard and accept[1] + guard < high):
                    found.append(f"{name} {feature} at {point}")
    return found


def test_plan_op_97_reads_every_profile_with_the_computed_procedure() -> None:
    plan = tomllib.loads(plans.plan_path(STEM).read_text(encoding="utf-8"))
    (op,) = [
        op
        for setup in plan["setups"]
        if setup["id"] == "S7"
        for op in setup["ops"]
        if op["op"] == 97
    ]
    assert op["checks"] == {"surface_profile": "dti"}
    assert sorted(op["feature"]) == sorted(_printed_zones())
    covered = {feature for s in check.SEGMENTS.values() for feature in s["features"]}
    assert covered == set(_printed_zones())
    assert op["inspection_methods"]["surface_profile"] == check.method_steps()


def test_op_97_uses_only_the_inventory_dti_and_height_gauge() -> None:
    assert _INVENTORY["dti"]["kind"] == "dial_test_indicator"
    assert check.DTI_RESOLUTION_MM == pytest.approx(0.0005 * 25.4)
    text = " ".join(check.method_steps())
    assert "gauges.dti" in text and "gauges.height-gauge" in text
    assert "AUTHOR'S CHOICE" in text


def test_every_accept_window_lies_strictly_inside_its_zone_after_the_guard() -> None:
    assert _violations(check.WINDOWS) == []
    for window in check.WINDOWS.values():
        # A tool-filed edge on the template's line, and the reject limits
        # outside the accept window.
        assert window["reject"][0] < window["accept"][0] < 0.0 < window["accept"][1]
        assert window["accept"][1] < window["reject"][1]


def test_window_check_goes_red_without_the_guard(monkeypatch) -> None:
    monkeypatch.setattr(check, "guard", lambda _point, _normal: 0.0)
    unguarded = {name: check.window(name) for name in check.SEGMENTS}
    assert _violations(unguarded)


def test_window_check_goes_red_with_a_wider_zone(monkeypatch) -> None:
    monkeypatch.setattr(check, "ZONE_MM", check.ZONE_MM + 0.1)
    widened = {name: check.window(name) for name in check.SEGMENTS}
    assert _violations(widened)


def test_the_template_edge_is_mid_zone_on_every_segment() -> None:
    """The windows are centred because the template aims at mid-zone: its
    edge sits half the zone in from either side, less the arcs' residual."""
    half = check.ZONE_MM / 2.0
    for name in check.SEGMENTS:
        for point, _normal in check.samples(name):
            low, high = check.zone_readings(name, point)
            assert low == pytest.approx(-half, abs=0.005)
            assert high == pytest.approx(half, abs=0.005)


# The outline template's own geometry and pin registration, which the guard
# above rests on (inventory gauges.arm-outline-template).

_ROCKER_BOT_END_Y = rocker_interface.CENTER_Y - rocker_interface.R_BOTTOM * math.cos(
    rocker._ALPHA_BOT
)
_ROCKER_TIP_Y = rocker.TOP_END_Y - rocker.TIP_FACE * math.cos(rocker._ALPHA_TOP)
# The rocker's BASIC +X outline corners and arc centre, in the template frame.
_ROCKER_TOP_END = (rocker.TOP_END_X, rocker.TOP_END_Y - rocker_interface.PIVOT_MID_Y)
_ROCKER_TIP = (rocker.ROD_TIP_X, _ROCKER_TIP_Y - rocker_interface.PIVOT_MID_Y)
_ROCKER_BOT_END = (rocker.BOT_END_X, _ROCKER_BOT_END_Y - rocker_interface.PIVOT_MID_Y)
_ROCKER_CENTRE_Y = rocker_interface.CENTER_Y - rocker_interface.PIVOT_MID_Y
_ZONE = rocker.TOP_EDGE_BAND[0] - rocker.TOP_EDGE_BAND[1]
_MID_ZONE = _ZONE / 2.0
# #1545 (approved 2026-10-15): of the rocker's half-zone either side of
# the aim, filing to the scribed line keeps at least this much.
_FILING_RESIDUAL = 0.09


def _into_material(point, start, end) -> float:
    """``point``'s offset from the rocker line start -> end, + into the arm."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    normal = (-dy / length, dx / length)
    middle = (0.0, _ROCKER_CENTRE_Y - (rocker.R_TOP + rocker_interface.R_BOTTOM) / 2.0)
    if (middle[0] - start[0]) * normal[0] + (middle[1] - start[1]) * normal[1] < 0.0:
        normal = (-normal[0], -normal[1])
    return (point[0] - start[0]) * normal[0] + (point[1] - start[1]) * normal[1]


@pytest.mark.parametrize(
    ("template_line", "rocker_line"),
    [
        (
            ((check.TOP_END_X, check.TOP_END_Y), (check.TIP_X, check.TIP_Y)),
            (_ROCKER_TOP_END, _ROCKER_TIP),
        ),
        (
            ((check.TIP_X, check.TIP_Y), (check.BOT_END_X, check.BOT_END_Y)),
            (_ROCKER_TIP, _ROCKER_BOT_END),
        ),
    ],
    ids=["tip land", "tapered end"],
)
def test_template_straight_edges_sit_mid_zone_along_their_own_normals(
    template_line, rocker_line
) -> None:
    """The lower outline's 0.5 Ⓤ0 zone lies wholly inside the material, so
    each land and taper aims half the zone in along its own normal. The old
    rigid +Y shift left the near-vertical land 0.045 OUTSIDE the zone."""
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        point = tuple(
            a + fraction * (b - a) for a, b in zip(*template_line, strict=True)
        )
        # Three-place stations and the radial land: 2 microns at most.
        assert math.isclose(
            _into_material(point, *rocker_line), _MID_ZONE, abs_tol=0.002
        )


def test_template_arcs_stay_on_the_trammel_radii_about_the_raised_centre() -> None:
    """Both arcs keep the trammel's radii about a centre raised by half the
    zone: mid-zone on the mirror line, short of it by half the zone times
    (1 - cos phi) off it."""
    trammel = _SHOP["tools"]["rocker-trammel"]["members"]
    assert (check.R_TOP, check.R_BOTTOM) == (
        trammel["R800"]["length_mm"]["value"],
        trammel["R816"]["length_mm"]["value"],
    )
    assert math.isclose(check.CENTER_Y - _ROCKER_CENTRE_Y, _MID_ZONE, abs_tol=1e-9)
    for radius, end_x in (
        (check.R_TOP, check.TOP_END_X),
        (check.R_BOTTOM, check.BOT_END_X),
    ):
        worst = 0.0
        for step in range(11):
            x = end_x * step / 10.0
            y = check.CENTER_Y - math.sqrt(radius**2 - x**2)
            # + toward the arcs' centre: outside the top edge, inside the bottom.
            residual = _MID_ZONE - (radius - math.hypot(x, y - _ROCKER_CENTRE_Y))
            assert residual >= -1e-9
            worst = max(worst, residual)
        phi = math.asin(end_x / radius)
        assert math.isclose(worst, _MID_ZONE * (1.0 - math.cos(phi)), abs_tol=1e-5)
        assert worst < check.DTI_ACCEPTANCE


def test_template_outline_corners_lie_on_their_arcs() -> None:
    def radius(x: float, y: float) -> float:
        return math.hypot(x, y - check.CENTER_Y)

    assert math.isclose(
        radius(check.TOP_END_X, check.TOP_END_Y), check.R_TOP, abs_tol=1e-9
    )
    assert math.isclose(
        radius(check.BOT_END_X, check.BOT_END_Y), check.R_BOTTOM, abs_tol=1e-9
    )
    # The tip land is radial, so its foot lies TIP_FACE beyond the top arc.
    assert math.isclose(
        radius(check.TIP_X, check.TIP_Y), check.R_TOP + check.TIP_FACE, abs_tol=1e-9
    )
    # The tapered end runs inward and down from the tip to the bottom arc's end.
    assert check.BOT_END_X < check.TIP_X and check.BOT_END_Y < check.TIP_Y


def test_pivot_pin_registration_and_acceptance_fit_a_quarter_of_the_rocker_zone() -> (
    None
):
    """The pin's worst-case play in BOTH bores (template and rocker, each at
    its largest, the pin at its smallest) moves the template off the arm's
    pivot; with the template's own DTI acceptance it stays inside the
    quarter of the rocker's arc zone the gauge may spend, centred on the aim."""
    hole = (check.PIVOT_HOLE_DIA, check.PIVOT_HOLE_DIA + check.PIVOT_HOLE_BAND[0])
    assert hole == pytest.approx((6.5024, 6.51764))
    rocker_bore = (
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1],
        rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[0],
    )
    assert check.PIN_GAUGE_MAX < hole[0]
    assert check.PIN_GAUGE_MAX < rocker_bore[0]
    registration = (hole[1] - check.PIN_GAUGE_MIN) / 2.0 + (
        rocker_bore[1] - check.PIN_GAUGE_MIN
    ) / 2.0
    assert check.LOCATOR_REGISTRATION_MAX >= registration
    assert check.LOCATOR_REGISTRATION_MAX == pytest.approx(0.0265)
    assert check.DTI_ACCEPTANCE + registration <= 0.25 * _ZONE / 2.0 + 1e-9


def test_pivot_pin_is_the_bought_inventory_gauge() -> None:
    assert check.PIN_GAUGE_MAX == pytest.approx(check.PIN_GAUGE_IN * 25.4)
    pin = _INVENTORY["vermont-class-x-2558-minus"]
    assert pin["kind"] == "pin_gauge" and pin["make"] == "Vermont Gage"
    assert pin["dia_in"]["value"] == check.PIN_GAUGE_IN
    assert "Class X minus" in pin["name"] + pin["note"]


def test_rod_slot_is_radial_at_the_rockers_rod_pin_hole() -> None:
    """The slot sits at the rocker's rod-pin hole (its datum C), to three
    places, and runs radially from the pivot."""
    station = (
        rocker_interface.ROD_HOLE_X,
        rocker_interface.ROD_HOLE_Y - rocker_interface.PIVOT_MID_Y,
    )
    assert math.dist((check.ROD_SLOT_X, check.ROD_SLOT_Y), station) <= (
        math.sqrt(2.0) * 0.0005
    )
    assert check.ROD_SLOT_AXIS == pytest.approx(
        (
            check.ROD_SLOT_X / check.ROD_SLOT_LEVER,
            check.ROD_SLOT_Y / check.ROD_SLOT_LEVER,
        )
    )


def test_rod_slot_width_is_a_matched_fit_on_a_pin_the_shop_owns() -> None:
    pins = _INVENTORY["pin-gauges"]
    assert "class ZZ minus" in pins["note"]
    low, high = pins["range_mm"]
    assert low <= check.ROD_PIN_MAX <= high
    step = pins["resolution_in"]["value"]
    assert math.isclose(
        check.ROD_PIN_GAUGE_IN / step, round(check.ROD_PIN_GAUGE_IN / step)
    )
    # The pin enters the rocker's #47 hole at its smallest; the next size up
    # in the set would not.
    assert check.ROD_PIN_MAX < 1.994 < (check.ROD_PIN_GAUGE_IN + step) * 25.4
    clearance = (
        check.ROD_SLOT_WIDTH_MIN - check.ROD_PIN_MAX,
        check.ROD_SLOT_WIDTH_MAX - check.ROD_PIN_MIN,
    )
    # The fit the shop works to: 0.001-0.017 diametral clearance on the pin.
    assert 0.001 <= clearance[0] and clearance[1] <= 0.017


def test_rod_slot_clocking_keeps_every_outline_edge_inside_the_template_share() -> None:
    assert _MID_ZONE - check.END_STATION_SHARE >= _FILING_RESIDUAL - 1e-9
    worst = max(check.outline_clocking_errors())
    assert worst == pytest.approx(check.ROD_CLOCKING_WORST)
    assert worst <= check.END_STATION_SHARE


def test_a_round_rod_hole_would_not_clock_the_template_closely_enough() -> None:
    """A round hole in place of the slot takes the rocker hole's radial
    position error across it too: the tail end then leaves the share."""
    round_hole = check.ROD_HOLE_RADIAL + check.ROD_HOLE_PLAY + check.ROD_SLOT_PLAY
    assert max(check.outline_clocking_errors(round_hole)) > check.END_STATION_SHARE


def test_template_acceptance_is_the_inventory_records() -> None:
    """The inventory record's profile acceptance, DTI stations about the
    pivot and the rod slot with pins in both, is the guard's."""
    note = _INVENTORY["arm-outline-template"]["note"]
    match = re.search(
        r"DTI within \+/-(\d+\.\d+) of nominal about the pivot and rod slot"
        r" \(pins in both; the slot's pin is the (\d\.\d{4}) in from"
        r" gauges\.pin-gauges\) at (\d+) stations",
        note,
    )
    assert match, note
    assert float(match.group(1)) == check.DTI_ACCEPTANCE
    assert float(match.group(2)) == check.ROD_PIN_GAUGE_IN


def test_inventory_template_solids_are_the_checked_geometry() -> None:
    """The shop-made gauge's inline solids (no CAD owner) are the plate's
    outline envelope with the pivot hole and rod-slot pin seat as voids, in
    the frame this check reads."""
    record = _INVENTORY["arm-outline-template"]
    assert "cad" not in record
    plate, hole, slot = record["solids"]
    xs, ys = zip(*check.outline_points(), strict=True)
    low = (min(xs), min(ys), 0.0)
    high = (max(xs), max(ys), check.THICK)
    assert plate["shape"] == "box" and plate["supply"] == "made"
    for axis in range(3):
        assert math.isclose(plate["at_mm"][axis], low[axis], abs_tol=1e-3)
        assert math.isclose(
            plate["at_mm"][axis] + plate["size_mm"][axis], high[axis], abs_tol=1e-3
        )
    assert hole["void"] is True and hole["shape"] == "cylinder"
    assert hole["at_mm"] == [0.0, 0.0, 0.0] and hole["axis"] == [0.0, 0.0, 1.0]
    assert hole["dia_mm"] == check.PIVOT_HOLE_DIA and hole["length_mm"] == check.THICK
    assert slot["void"] is True and slot["shape"] == "cylinder"
    assert slot["at_mm"] == [check.ROD_SLOT_X, check.ROD_SLOT_Y, 0.0]
    assert slot["dia_mm"] == check.ROD_SLOT_WIDTH and slot["length_mm"] == check.THICK


def _reload_with_rod_position(position_dia: str) -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(
            rocker.GEOMETRIC_TOLERANCES_MM, "rod-pin hole position", position_dia
        )
        try:
            importlib.reload(check)
        finally:
            patch.undo()
            importlib.reload(check)


def test_the_slot_absorbs_radial_rod_hole_error_without_moving_the_windows() -> None:
    """Up to the slot's admission limit the rod hole's radial position error
    slides the pin along the radial slot: the accept/reject windows hold."""
    baseline = copy.deepcopy(check.WINDOWS)
    observed = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(rocker.GEOMETRIC_TOLERANCES_MM, "rod-pin hole position", "0.24")
        try:
            importlib.reload(check)
            observed = copy.deepcopy(check.WINDOWS)
        finally:
            patch.undo()
            importlib.reload(check)
    assert observed == baseline


def test_the_module_refuses_a_rod_hole_error_the_slot_run_cannot_admit() -> None:
    with pytest.raises(AssertionError):
        _reload_with_rod_position("0.25")
