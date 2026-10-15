"""Keeper chain (MHA-VN-035) and loop link (MHA-VN-036) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import pytest

import _config
import dt_crank_pin_ring_spec as ring
import dt_crank_pin_spec as pin
import vn_keeper_chain_spec as chain


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


def test_ring_swung_outboard_clears_the_arm_at_its_worst_printed_reach() -> None:
    # Owner ruling 2026-10-15 A1: the ring reaches outboard (-X) past the
    # pin's big end. Hung toward -Y along the arm, as first placed, the
    # nominal ring's low arc ran into the arm's inboard face.
    nominal_crown = ring.ARC_SAGITTA / 2.0
    assert chain.RING_HANG == (-1.0, 0.0, 0.0)
    assert chain.ring_arm_air(90.0, ring.MEAN_R, nominal_crown, chain.RING_X) < 0.0
    assert chain.RING_ARM_AIR_NOMINAL == pytest.approx(
        chain.ring_arm_air(0.0, ring.MEAN_R, nominal_crown, chain.RING_X)
    )
    # The largest ring the title block accepts, crowned against the hole's
    # hub-side wall with the hole at its .XX station's hub-side limit, clears
    # the arm across the swing a worst-printed ring rests in.
    ring_id_max = round(ring.RING_ID, ring.RING_ID_PLACES) + _band(ring.RING_ID_PLACES)
    assert ring.RING_ID_MAX == pytest.approx(ring_id_max)
    worst = min(
        chain.ring_arm_air(
            float(swing),
            (ring_id_max + ring.WIRE_DIA) / 2.0,
            (pin.RING_HOLE_DIA - ring.WIRE_DIA) / 2.0,
            chain.RING_X + _band(2),
        )
        for swing in range(-25, 26)
    )
    assert worst == pytest.approx(chain.RING_ARM_AIR_WORST)
    assert worst >= chain.RING_ARM_AIR > 0.0
    assert worst < chain.RING_ARM_AIR_NOMINAL


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
    assert _config.parts("vn-keeper-chain")["supplier_skus"] == [chain.CHAIN_SKU]
    assert _config.parts("vn-keeper-chain-link")["supplier_skus"] == [chain.LINK_SKU]
    assert int(_config.parts("vn-keeper-chain-link")["quantity"]) == 1
