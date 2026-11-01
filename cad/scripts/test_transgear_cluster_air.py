"""The disc cluster's printed stack (#2038): lengths, end float, recess and
the two air stacks, re-derived from their source specs."""

from __future__ import annotations

import math

import pytest

import build_pd_paper_drive_assembly as ASSEMBLY
import pd_cluster_air as AIR
import pd_rack_pinion_spec as DISC
import pd_transgear_disc_hub_spec as HUB
import pd_transgear_front_bushing_spec as FRONT_BUSHING
import pd_transgear_rear_bushing_spec as REAR_BUSHING
import transgear_cluster_fit as FIT
from pd_cluster_stack_band import PRINTED_LENGTH_BAND, PRINTED_LENGTH_BAND_IN

TIGHTENED = (FIT.PH, FIT.TR, FIT.FW, FIT.GS, FIT.OL, FIT.TL, FIT.SP)
PRINTED_LENGTHS = (FIT.LHUB, FIT.LFB, FIT.LRB)


def _worst(chain, sign):
    return sum(s * nominal - sign * band for (_, nominal, band), s in chain)


def test_ruled_lengths_print_at_the_cluster_band():
    assert PRINTED_LENGTH_BAND == pytest.approx(0.02)
    assert PRINTED_LENGTH_BAND_IN == pytest.approx(0.01778)  # .0007 in
    assert (FIT.HUB_LENGTH, FIT.FRONT_BUSHING_LENGTH, FIT.REAR_BUSHING_LENGTH) == (
        pytest.approx(13.6906),  # .539
        pytest.approx(5.6388),  # .222
        pytest.approx(5.6388),  # .222
    )
    for label, _, band in (*TIGHTENED, *PRINTED_LENGTHS):
        assert band in (
            pytest.approx(PRINTED_LENGTH_BAND), pytest.approx(PRINTED_LENGTH_BAND_IN)
        ), label
    assert HUB.HUB_LENGTH == FIT.HUB_LENGTH
    assert FRONT_BUSHING.LENGTH == FIT.FRONT_BUSHING_LENGTH
    assert REAR_BUSHING.LENGTH == FIT.REAR_BUSHING_LENGTH
    for spec in (FRONT_BUSHING, REAR_BUSHING):
        assert spec.LENGTH_PLACES == 4
        assert not spec.REFERENCE_DIMENSIONS
    assert HUB.HUB_LENGTH_PLACES == 4
    assert not HUB.REFERENCE_DIMENSIONS


def test_end_float_holds_at_the_worst_case():
    least = _worst(FIT.END_FLOAT_CHAIN, 1)
    most = _worst(FIT.END_FLOAT_CHAIN, -1)
    assert FIT.END_FLOAT_RANGE == pytest.approx((least, most))
    assert least >= FIT.END_FLOAT_MIN
    assert FIT.END_FLOAT_RANGE == pytest.approx((0.2032, 0.5334))


def test_hub_never_stands_proud_of_the_nose():
    least = _worst(FIT.RECESS_CHAIN, 1)
    assert FIT.RECESS_RANGE[0] == pytest.approx(least)
    assert least >= -1e-9


def test_collar_air_is_the_statistical_stack():
    stack = AIR.COLLAR_AIR
    clearances = sum(
        v for k, v in stack.terms.items() if k in AIR.IN_SERVICE_CLEARANCES
    )
    tolerances = [v for k, v in stack.terms.items() if k in AIR.INDEPENDENT_TOLERANCES]
    assert len(tolerances) + sum(
        k in AIR.IN_SERVICE_CLEARANCES for k in stack.terms
    ) == len(stack.terms)
    expected = stack.nominal_mm - clearances - math.sqrt(sum(v * v for v in tolerances))
    assert stack.statistical_mm == pytest.approx(expected)
    assert stack.nominal_mm == pytest.approx(FIT.M_FWD_NOMINAL)
    assert stack.statistical_mm >= AIR.COLLAR_AIR_MIN
    # The study's caveats are budgeted, not left out.
    for source in (
        "hub rock on the sleeve boss",
        "sleeve cocking on the pin",
        "knob journal tilt in the plate bore",
        "pin S projected axis zone",
        "knob K projected axis zone",
    ):
        assert stack.terms[source] > 0.0, source
    for label, _, band in (term for term, _ in FIT.M_FWD_CHAIN):
        assert stack.terms[label] == band
    # Service motions add arithmetically; only made sizes are RSS'd.
    assert "arm plate loaded-seat change" in AIR.IN_SERVICE_CLEARANCES


def test_forward_stop_chain_pivots_on_the_pin_load_wall():
    # The loose front bushing and its retaining ring cock together about the
    # load wall's broken edge; the disc pivots on its least broken contact.
    brk = 0.254  # the inch title block's .010 break
    # Hub .520 at .XXX (±.005), front bushing .47 at .XX (±.01).
    hub_face = min(HUB.HUB_DIA - 0.127, FRONT_BUSHING.OD - 0.254) / 2.0 - brk
    nose = (FIT.SLEEVE.BOSS_DIA + min(FIT.SLEEVE.BOSS_DIA_BAND)) / 2.0 - brk
    assert AIR.HUB_FACE_STOP_R == pytest.approx(hub_face)
    assert AIR.NOSE_STOP_R == pytest.approx(nose)
    assert AIR.DISC_STOP_R == pytest.approx(min(HUB.SEAT_CONTACT_R, hub_face, nose))
    cock = math.atan(
        FIT.BORE_DIAMETRAL_CLEARANCE[1]
        / (FRONT_BUSHING.LENGTH - PRINTED_LENGTH_BAND_IN - 2.0 * brk)
    )
    wall = FRONT_BUSHING.PIN.DIA_MIN / 2.0 - brk
    term = AIR.COLLAR_AIR.terms["front bushing and ring cocking on the pin"]
    assert term == pytest.approx(cock * (max(hub_face, nose) - wall))
    assert "front bushing and ring cocking on the pin" in AIR.IN_SERVICE_CLEARANCES


def test_platen_air_budgets_the_pin_zone_and_governs():
    platen = ASSEMBLY.PLATEN_AIR
    assert platen.terms["pin S projected axis zone"] > 0.0
    assert platen.nominal_mm == pytest.approx(
        ASSEMBLY.PLATE_FRONT_Z - (FIT.DISC_FRONT_Z + DISC.FACE_WIDTH)
    )
    method = ASSEMBLY.CLUSTER_AIRS["method"]
    assert ASSEMBLY.DISC_PLATEN_AIR == pytest.approx(platen.air_mm(method))
    assert ASSEMBLY.DISC_PLATEN_AIR >= AIR.PLATEN_AIR_MIN
    assert ASSEMBLY.DISC_PLATEN_AIR_WORST == pytest.approx(platen.arithmetic_mm)
    assert ASSEMBLY.CLUSTER_AIRS["collar_air"] >= AIR.COLLAR_AIR_MIN


def test_air_stacks_reject_unclassified_or_negative_sources():
    with pytest.raises(ValueError):
        AIR.AirStack("probe", 1.0, {"unlisted source": 0.1}, 0.0)
    with pytest.raises(ValueError):
        AIR.AirStack("probe", 1.0, {"MHA-PD-20 spacer length": -0.1}, 0.0)
    shut = AIR.AirStack("probe", 0.05, {"MHA-PD-20 spacer length": 0.05}, 0.03)
    with pytest.raises(AssertionError):
        AIR.require_air(shut)


def test_hub_slides_forward_on_the_boss_by_the_end_float():
    slide = FIT.END_FLOAT_RANGE[1]
    sleeve_min = FIT.OL[1] - FIT.OL[2]
    tooth_max = FIT.TL[1] + FIT.TL[2]
    assert HUB.FLAT_DRIVE_LENGTH_MIN <= HUB.HUB_LENGTH_MIN - HUB.SPIGOT_LENGTH_MAX
    assert (
        HUB.FLAT_DRIVE_LENGTH_MIN
        <= sleeve_min - tooth_max - slide - HUB.SPIGOT_LENGTH_MAX
    )
    assert HUB.ROUND_ENGAGEMENT_MIN <= sleeve_min - tooth_max - slide
    assert HUB.ROCK_ANGLE_MAX == pytest.approx(
        HUB.BOSS_CLEARANCE / HUB.ROUND_ENGAGEMENT_MIN
    )


def test_disc_stays_in_full_mesh_with_the_15t_over_its_float():
    m_max = FIT.M_FWD_NOMINAL + FIT.M_FWD_BAND + FIT.END_FLOAT_RANGE[1]
    pinion_min = FIT.FW[1] - FIT.FW[2]
    assert pinion_min - m_max >= DISC.FACE_WIDTH_MAX
