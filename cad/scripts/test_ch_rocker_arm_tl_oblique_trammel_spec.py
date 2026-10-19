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

import _config
import _process_plans as plans
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_oblique_trammel_spec as trammel

PINNED = {
    "R_C1": (trammel.R_C1, 795.238),
    "R_C2": (trammel.R_C2, 820.763),
    "D1": (trammel.D1, 450.135),
    "D2": (trammel.D2, 464.584),
    "H1": (trammel.H1, 762.724),
    "A2.x": (trammel.A2[0], -232.292),
    "A2.y": (trammel.A2[1], 24.481),
    "B2.x": (trammel.B2[0], 232.292),
    "HUB_OFFSET": (trammel.HUB_OFFSET, 13.013),
    "RISER_INNER_RADIUS": (trammel.RISER_INNER_RADIUS, 802.381),
    "RISER_OUTER_RADIUS": (trammel.RISER_OUTER_RADIUS, 813.619),
    "RISER_SAGITTA.inner": (trammel.RISER_SAGITTA[0], 14.145),
    "RISER_SAGITTA.outer": (trammel.RISER_SAGITTA[1], 13.947),
    "PART_SAGITTA.inner": (trammel.PART_SAGITTA[0], 14.188),
    "PART_SAGITTA.outer": (trammel.PART_SAGITTA[1], 13.905),
    "RISER_HUB_CHECK": (trammel.RISER_HUB_CHECK, 5.869),
    # The jig stack: BEARING_SHOULDER 4 (r4) makes the pivot block 24 high.
    "PIVOT_BLOCK_HEIGHT": (trammel.PIVOT_BLOCK_HEIGHT, 24.0),
    "PIVOT_BLOCK_TOP_Z": (trammel.PIVOT_BLOCK_TOP_Z, 64.7),
    "CARRIER_UNDERSIDE_Z": (trammel.CARRIER_UNDERSIDE_Z, 67.7),
    "CARRIER_TOP_Z": (trammel.CARRIER_TOP_Z, 79.7),
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
    assert trammel.R_INNER == rocker.R_TOP == 800.0
    assert trammel.R_OUTER == rocker.R_BOTTOM == 816.0
    assert rocker.TOP_EDGE_ABOVE_PIVOT == rocker.PIVOT_MID_Y
    assert trammel.HUB_TO_TOP_EDGE == pytest.approx(8.25)
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


def test_jig_stock_requirements_preserve_finished_geometry_without_claiming_ownership() -> None:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    (carrier,) = [
        row for row in inventory["stock"] if "MHA-CH-006-TL-21" in row.get("note", "")
    ]
    (riser,) = [
        row for row in inventory["stock"] if "MHA-CH-006-TL-24" in row.get("note", "")
    ]
    assert carrier["on_hand"] is riser["on_hand"] is False
    assert carrier["section_mm"] == pytest.approx(
        [5.5 * trammel.INCH, 0.5 * trammel.INCH]
    )
    assert carrier["length_mm"] == pytest.approx(21.0 * trammel.INCH)
    assert carrier["section_mm"][1] - trammel.CARRIER_THICK == pytest.approx(0.7)
    assert 0.25 * trammel.INCH - trammel.RISER_THICK == pytest.approx(0.35)
    # There is no selected riser blank envelope: its 40 x 340 are finished
    # dimensions, not a fabricated supplier cut or a purchased-stock claim.
    assert not {"section_mm", "length_mm", "dia_mm"} & set(riser)
    assert (trammel.CARRIER_THICK, trammel.RISER_THICK) == (12.0, 6.0)
    assert (trammel.RISER_BLANK_WIDTH, trammel.RISER_BLANK_LENGTH) == (40.0, 340.0)
    carrier_row = _config.parts("ch-rocker-arm-tl-oblique-carrier")
    riser_row = _config.parts("ch-rocker-arm-tl-oblique-riser")
    assert "1/2 in" in carrier_row["material_specification"]
    assert "6061-T651" in carrier_row["material_specification"]
    assert "1250" in carrier_row["material_specification"]
    assert "1/4 in" in riser_row["material_specification"]


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
    assert edge_band == pytest.approx(rocker.ARM_DEPTH)


def test_in_situ_hub_and_end_holes_lie_on_the_hub_radius() -> None:
    for point in (trammel.HUB, trammel.CL, trammel.CR):
        assert math.dist(point, trammel.ARC_CENTRE) == pytest.approx(trammel.HUB_RADIUS)
    assert f"{trammel.HUB_RADIUS:.2f}" == "808.25"
    # CL/CR sit in the end waste: past the tip land, inside the 350 blank.
    tip_x = trammel.HUB_RADIUS * math.sin(trammel.TIP_ANGLE)
    assert tip_x < trammel.CR[0] < trammel.BLANK_LENGTH / 2.0
    assert f"{trammel.CR[0]:.3f}" == "160.895"
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
    assert f"{inner:.3f}" == "2.066"
    assert min(trammel.RISER_SCREW_WALLS) >= 2.0


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
    # C3 radial play, unmounted worst case, on the cut radius.
    assert f"{trammel.RADIUS_FROM_BEARING_PLAY:.3f}" == "0.041"


def test_hold_down_studs_land_on_t_slots_inside_the_table() -> None:
    far_x = abs(trammel.rail_point(1, *trammel.HOLD_DOWN_STUDS[1])[0])
    assert far_x < trammel.TABLE_LENGTH / 2.0 - trammel.TSLOT_WIDTH
    middle = trammel.TABLE_CENTRE_Y
    assert trammel.STUD_Y[0] - middle == pytest.approx(trammel.TSLOT_PITCH)
    assert middle - trammel.STUD_Y[1] == pytest.approx(trammel.TSLOT_PITCH)


def test_base_bar_is_half_by_six_with_its_column_edge_three_and_a_half_out() -> None:
    """The user's 2026-10-17 ruling (a): 1/2 x 6 bar, the column-side edge
    at lateral +88.9 so the TL-28 brackets stand on bar 1; the rail sits off
    the bar's centreline and both hold-down studs stay on the bar."""
    assert trammel.BASE_BAR_WIDTH == pytest.approx(152.4)
    assert trammel.BASE_BAR_COLUMN_EDGE == pytest.approx(88.9)
    assert trammel.BASE_BAR_OPERATOR_EDGE == pytest.approx(-63.5)
    assert (
        trammel.BASE_BAR_COLUMN_EDGE - trammel.BASE_BAR_OPERATOR_EDGE
        == pytest.approx(trammel.BASE_BAR_WIDTH)
    )
    for _s, lateral in trammel.HOLD_DOWN_STUDS:
        assert trammel.BASE_BAR_OPERATOR_EDGE < lateral < trammel.BASE_BAR_COLUMN_EDGE
