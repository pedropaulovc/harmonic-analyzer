"""The oblique-trammel calculator's derived numbers (rocker route v3).

Every number pinned below is computed by ``ch_rocker_arm_tl_oblique_trammel_spec``
from its inputs. The source check makes sure none of them is typed into the
calculator as a literal, so a changed input (cutter, radius, top-edge band)
moves every output together.
"""

from __future__ import annotations

import ast
import math
import tomllib
from pathlib import Path

import pytest

import _process_plans as plans
import ch_rocker_arm_spec as rocker
import _rocker_interface as rocker_interface
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
from _inch_wall_limits import WALL_TARGET_MM

# Calculator outputs that hang only on R800/R816, the cutters and ALPHA; the
# hub radius (and so HUB_OFFSET, RISER_HUB_CHECK, CL/CR) follows the rocker's
# top-edge band and is checked physically below.
PINNED = {
    "R_C1": (trammel.R_C1, 795.238),
    "R_C2": (trammel.R_C2, 820.763),
    "D1": (trammel.D1, 450.135),
    "D2": (trammel.D2, 464.584),
    "H1": (trammel.H1, 762.724),
    "A2.x": (trammel.A2[0], -232.292),
    "A2.y": (trammel.A2[1], 24.481),
    "B2.x": (trammel.B2[0], 232.292),
    "RISER_INNER_RADIUS": (trammel.RISER_INNER_RADIUS, 802.381),
    "RISER_OUTER_RADIUS": (trammel.RISER_OUTER_RADIUS, 813.619),
    "RISER_SAGITTA.inner": (trammel.RISER_SAGITTA[0], 14.145),
    "RISER_SAGITTA.outer": (trammel.RISER_SAGITTA[1], 13.947),
    "PART_SAGITTA.inner": (trammel.PART_SAGITTA[0], 14.188),
    "PART_SAGITTA.outer": (trammel.PART_SAGITTA[1], 13.905),
}


@pytest.mark.parametrize("name", sorted(PINNED))
def test_calculator_outputs(name: str) -> None:
    value, expected = PINNED[name]
    # Within half a unit of the third place: 795.2375 prints 795.238 half-up.
    assert abs(value - expected) <= 0.0005 + 1e-9


def test_outputs_are_derived_not_typed() -> None:
    tree = ast.parse(Path(trammel.__file__).read_text(encoding="utf-8"))
    literals = {
        round(node.value, 3)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, float)
    }
    typed = {
        name for name, (_v, expected) in PINNED.items() if abs(expected) in literals
    }
    assert not typed, f"calculator outputs typed as literals: {sorted(typed)}"


def test_inputs_come_from_the_rocker_spec() -> None:
    # The book radii about a centre raised by the arcs' mid-zone shift.
    shift = rocker_interface.PROFILE_MID_ZONE_SHIFT
    assert (trammel.R_INNER, trammel.R_OUTER) == (800.0, 816.0)
    assert (rocker.R_TOP + shift, rocker_interface.R_BOTTOM + shift) == pytest.approx((800.0, 816.0))
    assert rocker.TOP_EDGE_ABOVE_PIVOT == pytest.approx(rocker_interface.PIVOT_MID_Y + shift)
    # The hub aims at the middle of the strap's top-edge band.
    low, high = sorted(rocker.TOP_EDGE_BAND)
    assert trammel.HUB_TO_TOP_EDGE == pytest.approx(
        rocker.TOP_EDGE_ABOVE_PIVOT + (low + high) / 2.0
    )
    assert (
        rocker.TOP_EDGE_ABOVE_PIVOT + low
        < trammel.HUB_TO_TOP_EDGE
        < rocker.TOP_EDGE_ABOVE_PIVOT + high
    )
    assert trammel.ALPHA_DEG == 16.4405


def test_both_cutters_are_on_hand_as_four_flute_end_mills() -> None:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    sizes = inventory["tools"]["endmills-lms-6784"]["sizes_in"]["2_and_4_flute"]
    assert 4 in inventory["tools"]["endmills-lms-6784"]["flutes"]
    assert {trammel.PART_CUTTER_IN, trammel.RISER_CUTTER_IN} <= set(sizes)
    assert trammel.PART_CUTTER_DIA == pytest.approx(0.375 * 25.4)
    assert trammel.RISER_CUTTER_DIA == pytest.approx(0.5625 * 25.4)


def test_carrier_stock_and_new_riser_blank_requirements() -> None:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    (carrier,) = [
        row for row in inventory["stock"]
        if "OnlineMetals 1173" in row.get("note", "")
        and "TL-21 carrier" in row.get("note", "")
    ]
    (former_riser,) = [
        row for row in inventory["stock"] if "8663K55" in row.get("note", "")
    ]
    assert carrier["on_hand"] is True
    import ch_rocker_arm_tl_oblique_carrier_spec as carrier_spec
    import ch_rocker_arm_tl_oblique_riser_spec as riser_spec

    assert carrier["section_mm"][0] >= carrier_spec.PLATE_WIDTH
    assert carrier["section_mm"][1] > carrier_spec.THICKNESS
    assert carrier["length_mm"] >= carrier_spec.PLATE_LENGTH
    # Keep the real acetal order as provenance; do not invent a 6061 purchase.
    assert former_riser["material"] == "Acetal (Delrin)"
    assert "ordered 2026-11-03" in former_riser["note"]
    assert "unallocated stock" in former_riser["note"]
    assert 1.75 * 25.4 > riser_spec.BLANK_WIDTH
    assert 0.25 * 25.4 > riser_spec.THICKNESS
    assert riser_spec.BLANK_LENGTH == 13.80 * 25.4
    assert riser_spec.BLANK_WIDTH == pytest.approx(1.69 * 25.4, rel=0.0, abs=1e-12)


def test_strap_blank_is_the_bought_one_and_a_half_inch_strap_stock() -> None:
    """Preserve the procured 4807 stock and its existing source datum."""
    import ch_rocker_arm_tl_oblique_blank_spec as blank
    import ch_rocker_arm_tl_oblique_riser_spec as riser
    from _mcmaster_91251a197 import DIMS as common_screw

    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    (strap,) = [
        row
        for row in inventory["stock"]
        if "(MHA-CH-13)" in row.get("note", "") and "BLANK_WIDTH" in row.get("note", "")
    ]
    width, thick = strap["section_mm"]
    assert blank.BLANK_WIDTH == trammel.BLANK_WIDTH == width == pytest.approx(1.5 * 25.4)
    assert thick > trammel.STRAP_THICK == rocker.ARM_THICKNESS
    # Five blanks in each 72 in length, short by four 1/8 in cut bands.
    assert 5 * trammel.BLANK_LENGTH + 4 * 0.125 * 25.4 < strap["length_mm"]
    # The strap spans R800's tip-land ends to R816's apex across the blank,
    # and the blank leaves at least the .080 wall of waste beyond each edge.
    low, high = trammel.STRAP_SPAN_Y
    assert low == pytest.approx(
        trammel.R_INNER * math.cos(trammel.TIP_ANGLE) + trammel.ARC_CENTRE[1]
    )
    assert high == pytest.approx(trammel.R_OUTER + trammel.ARC_CENTRE[1])
    assert trammel.BLANK_EDGE_WASTE == pytest.approx(
        (trammel.BLANK_WIDTH - (high - low)) / 2.0
    )
    assert trammel.BLANK_EDGE_WASTE >= WALL_TARGET_MM
    # Both common #8 heads remain wholly in end waste on the procured blank.
    # The exact transferred-hole/setup certificate is in holding_spec.
    edge_low, edge_high = blank.RAW_Y_MIN, blank.RAW_Y_MAX
    head_r = common_screw.head_dia / 2.0
    for point in (trammel.CL, trammel.CR):
        assert edge_low + WALL_TARGET_MM <= point[1] - head_r
        assert point[1] + head_r <= edge_high - WALL_TARGET_MM
    assert riser.BLANK_ORIGIN[1] < low < high < riser.BLANK_ORIGIN[1] + riser.BLANK_WIDTH


def test_both_cutter_circles_share_the_arc_centre() -> None:
    centre = trammel.ARC_CENTRE
    for name, radius in (
        ("A1", trammel.R_C1),
        ("B1", trammel.R_C1),
        ("A2", trammel.R_C2),
        ("B2", trammel.R_C2),
    ):
        pin = trammel.PIN_HOLES[name]
        # Each pin sits on its cutter-centre circle at ALPHA from the apex.
        assert math.dist(pin, centre) == pytest.approx(radius)
    edge_band = (trammel.R_C2 - trammel.PART_CUTTER_DIA / 2) - (
        trammel.R_C1 + trammel.PART_CUTTER_DIA / 2
    )
    assert edge_band == pytest.approx(rocker_interface.ARM_DEPTH)


def test_in_situ_hub_and_end_holes_lie_on_the_hub_radius() -> None:
    for point in (trammel.HUB, trammel.CL, trammel.CR):
        assert math.dist(point, trammel.ARC_CENTRE) == pytest.approx(trammel.HUB_RADIUS)
    assert trammel.HUB_RADIUS == pytest.approx(trammel.R_INNER + trammel.HUB_TO_TOP_EDGE)
    assert trammel.HUB_OFFSET == pytest.approx(trammel.HUB_RADIUS - trammel.R_C1)
    # The HUB stands outboard of the riser's self-cut inner edge.
    assert trammel.RISER_HUB_CHECK == pytest.approx(
        trammel.HUB_RADIUS - trammel.RISER_INNER_RADIUS
    )
    assert trammel.RISER_HUB_CHECK > 0.0
    # CL/CR sit in the end waste: past the tip land, inside the 350 blank.
    tip_x = trammel.HUB_RADIUS * math.sin(trammel.TIP_ANGLE)
    assert tip_x < trammel.CR[0] < trammel.BLANK_LENGTH / 2.0
    # Angularly midway between the tip land and the blank's square end.
    blank_end = math.asin(trammel.BLANK_LENGTH / 2.0 / trammel.HUB_RADIUS)
    cr_angle = math.atan2(trammel.CR[0], trammel.CR[1] - trammel.ARC_CENTRE[1])
    assert cr_angle == pytest.approx((trammel.TIP_ANGLE + blank_end) / 2.0)
    assert trammel.CL == (-trammel.CR[0], trammel.CR[1])


def test_riser_screws_ride_the_self_cut_band_centreline() -> None:
    mid = (trammel.RISER_INNER_RADIUS + trammel.RISER_OUTER_RADIUS) / 2.0
    assert trammel.RISER_SCREW_RADIUS == pytest.approx(mid)
    assert f"{trammel.RISER_SCREW_RADIUS:.3f}" == "808.000"
    for point in trammel.RISER_SCREWS:
        assert math.dist(point, trammel.ARC_CENTRE) == pytest.approx(mid)
    # 40 and 120 of arc either side of the apex.
    assert [(f"{x:.3f}", f"{y:.3f}") for x, y in trammel.RISER_SCREWS] == [
        ("-39.984", "44.287"),
        ("39.984", "44.287"),
        ("-119.559", "36.382"),
        ("119.559", "36.382"),
    ]


def test_riser_countersink_walls_hold_rule_17_at_worst_case() -> None:
    """B18.6.3 #4 head (Ø0.225 in max); the countersink mouth at its 2-place
    band's top and the station at its 3-place X and Y band edges, pushed
    radially, to both self-cut edges (TrammelJig, jig-r5)."""
    assert trammel.RISER_SCREW_HEAD_DIA == pytest.approx(0.225 * trammel.INCH)
    assert trammel.RISER_CSK_DIA > trammel.RISER_SCREW_HEAD_DIA
    inner, outer = trammel.RISER_SCREW_WALLS
    assert inner == pytest.approx(outer)
    assert inner >= WALL_TARGET_MM


def test_every_pin_stays_on_its_rail_over_both_passes() -> None:
    for name, radius in trammel.PASS_RADIUS.items():
        theta_max = trammel.SWEEP[name]
        for step in range(-10, 11):
            theta = theta_max * step / 10.0
            pose = trammel.carrier_pose(name, theta)
            s_a, s_b = trammel.pin_station(radius, theta)
            for pin, rail, s in zip(trammel.pin_pair(name), (1, 2), (s_a, s_b)):
                assert (
                    math.dist(pose.to_machine(pin), trammel.rail_point(rail, s)) < 1e-9
                )
                carriage = s - trammel.PIN_OFFSET
                lo, hi = trammel.CARRIAGE_S_RANGE
                assert lo <= carriage <= hi
                assert carriage <= hi - trammel.RAIL_LENGTH_BAND


def test_trimmed_rails_retain_full_travel_at_shortest_bar_length() -> None:
    assert trammel.RAIL_LENGTH == trammel.BASE_BAR_LENGTH
    assert trammel.RAIL_SUPPLY_LENGTH == 450.0
    assert trammel.RAIL_TRIM_PER_END == pytest.approx(5.036)
    assert trammel.CARRIAGE_S_RANGE == pytest.approx((45.7, 424.228))
    # Centring the pivot moves the carriage interval 32 mm toward the near end.
    assert trammel.PIN_OFFSET == 0.0
    assert trammel.CARRIAGE_END_MARGINS_WORST == pytest.approx(
        (29.515018839, 34.607559206), abs=0.001
    )


def test_the_sweep_carries_the_part_cutter_past_both_tip_lands() -> None:
    for name, radius in trammel.PASS_RADIUS.items():
        past = radius * (trammel.SWEEP[name] - trammel.TIP_ANGLE)
        assert past == pytest.approx(trammel.PART_CUTTER_DIA / 2.0 + trammel.RUN_OUT)


def test_rail_alignment_targets_sit_on_the_pin_lines() -> None:
    for s, readings in trammel.ALIGNMENT_TARGETS.items():
        (x1, y1), (x2, y2) = readings["rail 1"], readings["rail 2"]
        assert x1 == -x2 and y1 == y2
        assert math.hypot(x1, y1) == pytest.approx(s)
        assert math.degrees(math.atan2(-y2, x2)) == pytest.approx(
            trammel.ALPHA_DEG / 2.0
        )


def test_sensitivities_match_the_brief() -> None:
    assert f"{trammel.RADIUS_PER_TENTH_DEG:.1f}" == "4.7"
    # A spacing error of 0.1 changes R by about 0.18.
    assert f"{0.1 * trammel.RADIUS_PER_SPACING:.2f}" == "0.18"
    import ch_rocker_arm_tl_oblique_carrier_spec as carrier

    # The carrier's REAM_SLIDE pin hole on the bought shoulder.
    assert trammel.SHOULDER_CARRIER_CLEARANCE == pytest.approx(
        (carrier.PIN_CLEARANCE_MIN, carrier.PIN_CLEARANCE_MAX)
    )
    assert trammel.RADIUS_FROM_SHOULDER_CLEARANCE == pytest.approx(
        trammel.RADIUS_PER_SPACING * carrier.PIN_CLEARANCE_MAX
    )


def test_carriage_play_and_shoulder_clearance_share_half_the_top_edge_band() -> None:
    """The kit carriages are accepted by a fit-up play check, not by preload:
    the play the check admits moves the cut radius 1:1, and with the shoulder
    clearance it must stay inside half the strap's top-edge band (the hub aims
    at its middle)."""
    assert trammel.CARRIAGE_PLAY_TIR_MAX == 0.02
    assert trammel.CARRIAGE_PLAY_RADIUS_PER_PLAY == 1.0
    assert trammel.CARRIAGE_PLAY_RADIUS == pytest.approx(
        1.0 * trammel.CARRIAGE_PLAY_TIR_MAX
    )
    low, high = sorted(rocker.TOP_EDGE_BAND)
    half_band = (high - low) / 2.0
    assert trammel.TOP_EDGE_HALF_BAND == pytest.approx(half_band) == pytest.approx(0.254)
    assert trammel.CARRIAGE_PLAY_RADIUS <= trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    budget = trammel.CARRIAGE_PLAY_RADIUS + trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    assert budget <= half_band
    # .020 + .112 leaves .122 here; the complete carrier stack also charges
    # HUB setting/rounding and the correlated pin error against that same HUB.
    assert half_band - budget == pytest.approx(0.122, abs=5e-4)


def test_plain_pivot_stack_sets_the_carrier_height() -> None:
    # Each fabricated height prints exactly on its inch grid (#290).
    for height, places in (
        (trammel.BASE_BAR_THICK, trammel.BASE_BAR_THICK_PLACES),
        (trammel.PIVOT_BLOCK_HEIGHT, 2),
        (trammel.CARRIER_THICK, trammel.CARRIER_THICK_PLACES),
        (trammel.RISER_THICK, trammel.RISER_THICK_PLACES),
    ):
        inches = height / trammel.INCH
        assert inches == pytest.approx(round(inches, places), abs=1e-9)
    # The stack stands on the faced base bar (owner ruling 2026-10-30).
    assert trammel.RAIL_SEAT_Z == trammel.BASE_BAR_THICK < trammel.BASE_BAR_STOCK_THICK
    assert trammel.PIVOT_SUPPORT_HEIGHT == pytest.approx(
        trammel.PIVOT_SHIM_PACK + trammel.PIVOT_SPACER_LENGTH
    )
    assert trammel.CARRIER_UNDERSIDE_Z == pytest.approx(
        trammel.BASE_BAR_THICK
        + trammel.CARRIAGE_HEIGHT
        + trammel.PIVOT_BLOCK_HEIGHT
        + trammel.PIVOT_SUPPORT_HEIGHT
    )
    for retired in (
        "BEARING_RADIAL_PLAY", "RADIUS_FROM_BEARING_PLAY", "BEARING_BORE",
        "BEARING_OD", "BEARING_WIDTH", "BEARINGS_PER_PIN", "BEARING_RECESS",
        "BEARING_SHOULDER", "PIN_COLLAR_PROUD", "PIN_COLLAR_HEIGHT",
    ):
        assert not hasattr(trammel, retired)


def test_hold_down_studs_land_on_t_slots_inside_the_table() -> None:
    far_x = abs(trammel.rail_point(1, *trammel.HOLD_DOWN_STUDS[1])[0])
    assert far_x < trammel.TABLE_LENGTH / 2.0 - trammel.TSLOT_WIDTH
    middle = trammel.TABLE_CENTRE_Y
    assert trammel.STUD_Y[0] - middle == pytest.approx(trammel.TSLOT_PITCH)
    assert middle - trammel.STUD_Y[1] == pytest.approx(trammel.TSLOT_PITCH)


def test_base_bar_stock_fits_the_vise_with_its_column_edge_three_and_a_half_out() -> (
    None
):
    """The finished bar fits the 6 in vise's stock hard jaws, and the owned
    stock (owner ruling #2083: both bars from the owned 1173 1/2 x 6 bar) is
    wide, thick and long enough to mill both bars from it. The column-side
    edge stays at lateral +88.9 (2026-10-17 ruling a) so the TL-28 brackets
    stand on bar 1; both hold-down studs stay on the bar."""
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    vise_opening = inventory["fixtures"]["vise-pm-6"]["opening_in"]["value"] * 25.4
    assert trammel.BASE_BAR_WIDTH <= vise_opening
    (stock,) = [
        row for row in inventory["stock"] if "OnlineMetals 1173," in row.get("note", "")
    ]
    assert stock["on_hand"]
    width, thickness = stock["section_mm"]
    assert trammel.BASE_BAR_WIDTH < width
    assert trammel.BASE_BAR_THICK < thickness
    assert thickness == pytest.approx(trammel.BASE_BAR_STOCK_THICK)
    assert stock["length_mm"] >= 2 * trammel.BASE_BAR_LENGTH
    assert trammel.BASE_BAR_COLUMN_EDGE == pytest.approx(88.9)
    assert (
        trammel.BASE_BAR_COLUMN_EDGE - trammel.BASE_BAR_OPERATOR_EDGE
        == pytest.approx(trammel.BASE_BAR_WIDTH)
    )
    for _s, lateral in trammel.HOLD_DOWN_STUDS:
        assert trammel.BASE_BAR_OPERATOR_EDGE < lateral < trammel.BASE_BAR_COLUMN_EDGE
