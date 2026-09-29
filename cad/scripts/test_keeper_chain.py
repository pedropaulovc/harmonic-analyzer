"""Keeper chain (MHA-149/150) contracts, SolidWorks-free."""

from __future__ import annotations

import math

import pytest

import keeper_chain_spec as chain


def test_every_link_is_one_pitch() -> None:
    assert max(chain.pitch_errors()) < 1e-9


def test_chain_clears_every_part_it_passes() -> None:
    worst = chain.clearance_report()
    assert min(worst.values()) >= 0.0, {k: v for k, v in worst.items() if v < 0.0}
    # The wraps bear on the wire through the rod, with the solve's air.
    assert worst["rod-eye"] == pytest.approx(chain.AIR, abs=2e-3)
    assert worst["rod-ring"] == pytest.approx(chain.AIR, abs=2e-3)


def test_chain_reaches_the_withdrawn_pin() -> None:
    run = (len(chain.RUN_BEADS) - 1) * chain.PITCH
    assert run >= chain.WITHDRAWAL_REACH + chain.PITCH
    # The pin comes all the way out of the hub, not just loose in it.
    assert chain.PIN_X0 + chain.PIN_LENGTH - chain.PIN_WITHDRAWAL < -chain.HUB_R


def test_chain_ends_are_captured_by_their_links() -> None:
    beads = chain.BEAD_CENTRES
    for end, running, link in (
        (beads[0], beads[len(chain.EYE_LOOP) - 1], chain.EYE_LINK),
        (beads[-1], beads[-len(chain.RING_LOOP)], chain.RING_LINK),
    ):
        assert running == link
        assert end[0] - link[0] == pytest.approx(chain.SPLICE_END_BEAD_X)
        assert end[1:] == pytest.approx(link[1:])
        assert chain.SPLICE_END_BEAD_X + chain.BEAD_R < chain.SPLICE_LENGTH / 2.0


def test_run_hangs_below_both_links() -> None:
    low = min(p[1] for p in chain.RUN_BEADS)
    assert low < min(chain.EYE_LINK[1], chain.RING_LINK[1]) - chain.PITCH
    assert chain.RUN_LOW_Y < chain.EYE_LINK[1]


def test_splice_envelope_volume_is_a_tube_less_its_cross_hole() -> None:
    a, b = chain.SPLICE_OD / 2.0, chain.SPLICE_BORE / 2.0
    tube = math.pi * (a * a - b * b) * chain.SPLICE_LENGTH
    plugs = 2.0 * math.pi * (chain.SPLICE_CROSS_HOLE / 2.0) ** 2 * (a - b)
    assert chain.splice_volume() == pytest.approx(tube - plugs, rel=0.02)


def test_purchased_parts_name_their_skus() -> None:
    import _config

    assert _config.parts("keeper-chain")["supplier_skus"] == [chain.CHAIN_SKU]
    assert _config.parts("keeper-chain-splice")["supplier_skus"] == [chain.SPLICE_SKU]
    assert int(_config.parts("keeper-chain-splice")["quantity"]) == len(chain.SPLICE_ORIGINS)


def test_frozen_balloon_anchor_sits_on_a_rod_bead_edge() -> None:
    from _drive_train_balloon_anchors import DRIVE_TRAIN_BALLOON_ANCHORS

    point = DRIVE_TRAIN_BALLOON_ANCHORS["cone-crank"]["keeper-chain"].point_mm
    assert point is not None
    bead, toward = chain.BEAD_CENTRES[24], chain.BEAD_CENTRES[25]
    u = [(t - b) / chain.PITCH for b, t in zip(bead, toward)]
    h0 = math.sqrt(chain.BEAD_R**2 - chain.ROD_R**2)
    rel = [p - b for p, b in zip(point, bead)]
    along = sum(r * a for r, a in zip(rel, u))
    radial = math.sqrt(sum(r * r for r in rel) - along * along)
    # On the circle where the rod leaves the bead (4-decimal literal).
    assert along == pytest.approx(h0, abs=2e-4)
    assert radial == pytest.approx(chain.ROD_R, abs=2e-4)
    # On the side facing the *Isometric viewer.
    view = [1.0 / math.sqrt(3.0)] * 3
    assert sum(r * v for r, v in zip(rel, view)) > 0.0
