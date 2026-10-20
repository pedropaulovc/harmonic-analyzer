"""Keeper chain (MHA-DT-VN-65) and loop link (MHA-DT-VN-66) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import pytest

import _config
import dt_crank_arm_spec as arm
import dt_crank_hub_geometry as hub_geometry
import dt_crank_hub_spec as hub
import dt_crank_pin_ring_spec as ring
import dt_crank_pin_spec as pin
import dt_vn_keeper_chain_spec as chain


def test_every_link_is_one_pitch() -> None:
    assert max(chain.pitch_errors()) < 1e-9


def test_chain_clears_every_part_it_passes() -> None:
    worst = chain.clearance_report()
    assert min(worst.values()) >= 0.0, {k: v for k, v in worst.items() if v < 0.0}
    # The wraps bear on the wire through the rod, with the solve's air.
    assert worst["rod-eye"] == pytest.approx(chain.AIR, abs=2e-3)
    assert worst["rod-ring"] == pytest.approx(chain.AIR, abs=2e-3)


def test_each_strand_reaches_the_withdrawn_pin() -> None:
    # Drawing the pin out pulls both strands straight side by side.
    assert chain.INNER_LENGTH >= chain.INNER_REACH + chain.PITCH
    assert chain.OUTER_LENGTH >= chain.OUTER_REACH + chain.PITCH
    # The pin comes all the way out of the hub, not just loose in it.
    assert chain.PIN_X0 + chain.PIN_LENGTH - chain.PIN_WITHDRAWAL < -chain.HUB_R


def _band(places: int) -> float:
    return float(str(_config.title_block(f"linear_{places}pl")["display"]).lstrip("±"))


def _corner_air(
    hole_x: float, pin_z: float, mean_r: float, crown: float
) -> tuple[float, tuple[float, float]]:
    """A ring in the A1 plane (y = 0) against the arm's -X inboard corner
    edge, in closed form: its air and the wire-centreline point nearest it."""
    cx, cz = hole_x - (mean_r - crown), pin_z
    qx, qz = -arm.HALF_WIDTH, arm.ARM_THICKNESS
    reach = math.hypot(qx - cx, qz - cz)
    nearest = (cx + mean_r * (qx - cx) / reach, cz + mean_r * (qz - cz) / reach)
    return reach - mean_r - ring.WIRE_DIA / 2.0, nearest


def _flat_side_air(swing_deg: float, mean_r: float, crown: float) -> float:
    """The nominal ring swung toward -Y against the arm's straight -X side
    and its inboard face, from 3600 points of its centreline. (The few points
    past the hole axis, at +Y, are the crown's, high over the face.)"""
    a = math.radians(swing_deg)
    least = math.inf
    for k in range(3600):
        t = 2.0 * math.pi * k / 3600
        out = mean_r - crown + mean_r * math.cos(t)  # along the hang
        x = chain.RING_X - math.cos(a) * out
        z = chain.PIN_Z + mean_r * math.sin(t)
        side = max(0.0, -arm.HALF_WIDTH - x)
        above = max(0.0, z - arm.ARM_THICKNESS)
        least = min(least, math.hypot(side, above))
    return least - ring.WIRE_DIA / 2.0


def test_pin_station_reads_the_hub_print() -> None:
    station = hub.DRAWING_PRECISION["ServicePinStationReference"]
    places = station["ServicePinFromShoulder"]
    shoulder = arm.ARM_THICKNESS  # the hub's shoulder is the arm's inboard face
    from_shoulder = hub_geometry.SERVICE_PIN_FROM_SHOULDER
    assert chain.PIN_Z == pytest.approx(shoulder + from_shoulder)
    assert chain.PIN_Z_ARMWARD == pytest.approx(chain.PIN_Z - _band(places))


def test_ring_crowned_hub_side_touches_the_arm_at_the_adverse_corner() -> None:
    # Codex xhigh, PR #1466 round 3: the largest accepted ring, crowned 0.50
    # hub-side in a hole at its station's hub-side limit, on a pin at the
    # hub's arm-side station limit, meets the arm's corner in the A1 plane.
    mean_r = (ring.RING_ID_MAX + ring.WIRE_DIA) / 2.0
    hole_x = chain.RING_X + _band(2)
    air, nearest = _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, 0.50)
    # The nearest wire point is outboard of the arm and above its face, so the
    # corner edge is the arm's nearest point and the closed form is exact.
    assert nearest[0] < -arm.HALF_WIDTH and nearest[1] > arm.ARM_THICKNESS
    assert air < 0.0
    helper = chain.ring_arm_air(0.0, mean_r, 0.50, hole_x, chain.PIN_Z_ARMWARD)
    assert helper == pytest.approx(air, abs=1e-3)
    # At the nominal station the same ring clears: the station is what bites.
    assert _corner_air(hole_x, chain.PIN_Z, mean_r, 0.50)[0] > 0.0


def test_every_printed_ring_has_a_pose_clear_of_the_arm() -> None:
    # The largest ring governs: slid outboard in the hole as far as the hole's
    # outboard edges (on the pin's fattest printed section) let it, it clears
    # the arm at the adverse corner, so the arm cannot clamp it.
    mean_r = (ring.RING_ID_MAX + ring.WIRE_DIA) / 2.0
    pin_r = ring.PIN_DIA_AT_HOLE_MAX / 2.0
    hole_r = pin.RING_HOLE_DIA / 2.0
    wire_r = ring.WIRE_DIA / 2.0

    def outboard_edge_air(crown: float) -> float:
        return mean_r - math.hypot(mean_r - crown - hole_r, pin_r) - wire_r

    low, high = 0.0, hole_r - wire_r  # crown on the axis, crown on the hub-side wall
    assert outboard_edge_air(low) < 0.0 <= outboard_edge_air(high)
    for _ in range(60):
        mid = (low + high) / 2.0
        low, high = (mid, high) if outboard_edge_air(mid) < 0.0 else (low, mid)
    crown = high
    # The hole admits that pose: the hub-side edges stay outside the arc.
    assert math.hypot(mean_r - crown + hole_r, pin_r) - mean_r >= wire_r
    hole_x = chain.RING_X + _band(2)
    air, nearest = _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, crown)
    assert nearest[0] < -arm.HALF_WIDTH and nearest[1] > arm.ARM_THICKNESS
    assert air >= 0.0
    assert chain.RING_FREE_AIR_WORST == pytest.approx(air, abs=5e-3)
    # Crowned against the hub-side wall instead it touches: the slide is the proof.
    assert _corner_air(hole_x, chain.PIN_Z_ARMWARD, mean_r, hole_r - wire_r)[0] < 0.0


def test_arm_is_the_ring_swing_stop_and_withdrawal_lifts_it_off() -> None:
    crown = ring.ARC_SAGITTA / 2.0
    # Hanging plumb, the nominal ring's plane is x = RING_X, inside the arm's
    # half-width, and its low arc dips below the arm's inboard face: under its
    # own weight it comes to rest on the arm.
    assert abs(chain.RING_X) < arm.HALF_WIDTH
    assert chain.PIN_Z - ring.MEAN_R < arm.ARM_THICKNESS
    assert 0.0 < chain.RING_STOP_SWING_DEG < 90.0
    assert _flat_side_air(chain.RING_STOP_SWING_DEG - 1.0, ring.MEAN_R, crown) > 0.0
    assert _flat_side_air(chain.RING_STOP_SWING_DEG + 1.0, ring.MEAN_R, crown) < 0.0
    # No accepted ring reaches the arm's mid-plane x = 0: its hub-most point is
    # the oversize hole's hub-side wall at the station's hub-side limit. So
    # the arm's outward normal at any contact points -X or along its face.
    drilled_plus = float(_config.title_block("drilled_hole")["plus_mm"])
    reach = chain.RING_X + _band(2) + (pin.RING_HOLE_DIA + drilled_plus) / 2.0
    assert chain.RING_REACH_X_MAX == pytest.approx(reach)
    assert reach < 0.0


def test_nominal_ring_threads_the_hole_edges_in_its_posed_plane() -> None:
    # In the pin's axial plane the wire leaves the hole along the pin's top
    # line, so the hole's edges are tighter than its wall.
    assert 0.0 < chain.A1_HOLE_AIR < ring.HOLE_AIR


def test_one_closed_loop_through_both_wires() -> None:
    beads = chain.BEAD_CENTRES
    # The two ends are the link's end beads, a joint's spacing apart on its axis.
    ends = beads[0], beads[-1]
    assert chain._dist(*ends) == pytest.approx(chain.LINK_BEAD_SPACING)
    for end in ends:
        axial, radial, _ = chain._link_local(end)
        assert abs(axial) == pytest.approx(chain.LINK_END_BEAD_X)
        assert radial == pytest.approx(0.0, abs=1e-9)
    # The rods leave the domes along the axis.
    for end, next_bead in ((beads[0], beads[1]), (beads[-1], beads[-2])):
        _, radial, _ = chain._link_local(next_bead)
        assert radial == pytest.approx(0.0, abs=1e-9)
        assert chain._dist(end, next_bead) == pytest.approx(chain.PITCH)
    # It wraps both the eye and the ring, a bead either side of each wire.
    for outer, inner in ((chain.EYE_OUTER, chain.EYE_INNER), (chain.RING_OUTER, chain.RING_INNER)):
        index = beads.index(inner)
        assert outer in (beads[index - 1], beads[index + 1])


def test_strands_nest_without_crossing() -> None:
    # The inner strand hangs below the outer one, so the two U's never cross.
    inner_bottom = min(p[1] for p in chain.INNER_BEADS)
    assert inner_bottom <= chain.OUTER_BOTTOM_Y - chain.STRAND_GAP
    assert chain.INNER_SIDE_X - chain.OUTER_SIDE_X >= chain.BEAD_DIA


def test_link_goes_on_and_holds_its_end_beads() -> None:
    # Each dome's side mouth is narrower than a bead: the end bead snaps in as
    # the wall flexes and cannot fall back out, while its rod rides the slot
    # to the tip hole. Axially the tip hole and the far dome hold it too.
    assert chain.LINK_MOUTH_WIDTH < chain.BEAD_DIA
    assert chain.LINK_MOUTH_LENGTH < chain.BEAD_DIA
    assert chain.ROD_DIA < chain.LINK_SLOT_WIDTH
    assert chain.LINK_TIP_HOLE < chain.BEAD_DIA
    assert chain.ROD_DIA < chain.LINK_TIP_HOLE
    assert chain.LINK_END_BEAD_X + chain.BEAD_R < chain.LINK_LENGTH / 2.0
    assert chain.LINK_OD / 2.0 - chain.LINK_WALL > chain.BEAD_R
    # The crimp is modelled as an outside groove; it leaves wall under it.
    assert chain.LINK_WALL - chain.LINK_CRIMP_DEPTH >= 0.1


def test_link_volume_matches_its_shape() -> None:
    ro, ri = chain.LINK_OD / 2.0, chain.LINK_OD / 2.0 - chain.LINK_WALL
    e = chain.LINK_END_BEAD_X
    shell = math.pi * (ro**2 - ri**2) * 2.0 * e + 4.0 / 3.0 * math.pi * (ro**3 - ri**3)
    # Grooves, tip holes, the bead mouths and the rod slot come off the shell.
    assert 0.7 * shell < chain.link_volume() < shell


def test_chain_edges_fit_the_balloon_walk() -> None:
    # Its beads draw only silhouettes, so the drawings balloon the chain from
    # its rod/bead circles, two per link; the walk samples at most this many.
    from _drawing_balloons import _VISIBLE_EDGES_PER_INSTANCE

    assert 2 * (chain.BEAD_COUNT - 1) <= _VISIBLE_EDGES_PER_INSTANCE


def test_purchased_parts_name_their_skus() -> None:
    assert _config.parts("dt-vn-keeper-chain")["supplier_skus"] == [chain.CHAIN_SKU]
    assert _config.parts("dt-vn-keeper-chain-link")["supplier_skus"] == [chain.LINK_SKU]
    assert int(_config.parts("dt-vn-keeper-chain-link")["quantity"]) == 1
