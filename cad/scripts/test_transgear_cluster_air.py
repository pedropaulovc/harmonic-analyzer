"""The disc cluster's stack and shim fit-up (#2124): lengths, end float,
recess and the two air stacks, re-derived from their source specs."""

from __future__ import annotations

import math

import pytest

import build_pd_paper_drive_assembly as ASSEMBLY
import pd_cluster_air as AIR
import pd_rack_pinion_spec as DISC
import pd_transgear_disc_hub_spec as HUB
import pd_transgear_front_bushing_spec as FRONT_BUSHING
import pd_transgear_rear_bushing_spec as REAR_BUSHING
import pd_vn_transgear_cluster_shim_spec as SHIM
import transgear_cluster_fit as FIT
from _printed_tolerance import printed_band_mm
from pd_cluster_stack_band import FIT_LENGTH_BAND_IN

FIT_LENGTHS = (
    FIT.PH, FIT.TR, FIT.FW, FIT.GS, FIT.OL, FIT.TL, FIT.SP, FIT.LHUB, FIT.LFB,
)


def _worst(chain, sign):
    return sum(s * nominal - sign * band for (_, nominal, band), s in chain)


def test_stack_lengths_print_their_bands():
    """The knob train and the lengths that set the collar air or the recess
    print +/-.001; the rear bushing, which only feeds the shimmed end float,
    prints at the title block."""
    assert FIT_LENGTH_BAND_IN == pytest.approx(0.0254)  # .001 in
    for label, _, band in FIT_LENGTHS:
        assert band == pytest.approx(FIT_LENGTH_BAND_IN), label
    assert FIT.LRB[2] == printed_band_mm(3, unit=REAR_BUSHING.UNIT)
    assert (FIT.HUB_LENGTH, FIT.FRONT_BUSHING_LENGTH, FIT.REAR_BUSHING_LENGTH) == (
        pytest.approx(13.6906),  # .539
        pytest.approx(5.6388),  # .222
        pytest.approx(5.4356),  # .214
    )
    assert HUB.HUB_LENGTH == FIT.HUB_LENGTH
    assert FRONT_BUSHING.LENGTH == FIT.FRONT_BUSHING_LENGTH
    assert REAR_BUSHING.LENGTH == FIT.REAR_BUSHING_LENGTH
    for spec in (FRONT_BUSHING, REAR_BUSHING):
        assert spec.LENGTH_PLACES == 3
        assert not spec.REFERENCE_DIMENSIONS
    assert HUB.HUB_LENGTH_PLACES == 3
    assert not HUB.REFERENCE_DIMENSIONS


def test_unshimmed_ring_gap_never_closes_under_the_floor():
    least = _worst(FIT.RING_FLOAT_CHAIN, 1)
    most = _worst(FIT.RING_FLOAT_CHAIN, -1)
    assert FIT.UNSHIMMED_FLOAT_RANGE == pytest.approx((least, most))
    assert least >= FIT.END_FLOAT_MIN


def test_shims_close_every_cluster_into_the_window():
    """Shims go on while the ring gap less the next one clears the floor:
    every unshimmed gap from the shortest to the longest ends in the window,
    with a count inside SHIM_COUNT_RANGE, whatever each shim's catalogue
    thickness; the disc's end float is that gap plus the recess."""
    low, high = FIT.RING_FLOAT_RANGE
    assert low == FIT.END_FLOAT_MIN
    assert high == pytest.approx(FIT.END_FLOAT_MIN + SHIM.THICKNESS_MAX)
    for thickness in (SHIM.THICKNESS_MIN, SHIM.THICKNESS_MAX):
        for unshimmed in FIT.UNSHIMMED_FLOAT_RANGE:
            gap, count = unshimmed, 0
            while gap - thickness >= FIT.END_FLOAT_MIN:
                gap, count = gap - thickness, count + 1
            assert low <= gap < high
            assert FIT.SHIM_COUNT_RANGE[0] <= count <= FIT.SHIM_COUNT_RANGE[1]
    model = FIT.UNSHIMMED_FLOAT_NOMINAL - FIT.SHIM_COUNT_MODEL * SHIM.THICKNESS
    assert FIT.RING_FLOAT_MODEL == pytest.approx(model)
    assert low <= model < high
    assert model - SHIM.THICKNESS < FIT.END_FLOAT_MIN
    assert FIT.END_FLOAT_RANGE == pytest.approx(
        (low + FIT.RECESS_RANGE[0], high + FIT.RECESS_RANGE[1])
    )
    assert FIT.END_FLOAT_RANGE[0] >= FIT.END_FLOAT_MIN


def test_hub_never_stands_proud_of_the_nose():
    least = _worst(FIT.RECESS_CHAIN, 1)
    assert FIT.RECESS_RANGE[0] == pytest.approx(least)
    assert least >= -1e-9


def test_mha_pd_00_feels_the_air_its_feeler_accepted_sources_close():
    """Owner rulings 2026-11-08 (#2144 items 3.2 and 4.1) and the MHA-PD-10
    step face route: the hub spigot end, the sleeve step face and MHA-PD-18's
    pin bore S print ⊥ .001, and their collar-air terms are accepted by
    MHA-PD-00's .004 feeler (re-face the step if short, which sets back a
    disc on a tilted S too), so the stack gate drops them; with them the air
    is under the floor, which is why the feeler check carries it."""
    import paper_drive_arm_registration as registration

    assert AIR.ASSEMBLY_ACCEPTED_COLLAR_SOURCES == {
        "sleeve step face perpendicularity",
        "hub spigot end perpendicularity",
        "pin S projected axis zone",
    }
    every = AIR.COLLAR_AIR_UNACCEPTED
    assert set(every.terms) - set(AIR.COLLAR_AIR.terms) == AIR.ASSEMBLY_ACCEPTED_COLLAR_SOURCES
    assert every.terms["hub spigot end perpendicularity"] == pytest.approx(
        AIR.SPIGOT_SLOPE * AIR.Q_FROM_DISC_AXIS
    )
    assert AIR.S_ZONE_TILT == pytest.approx(
        math.atan(registration.S_AXIS_ZONE_DIAMETER_MM / registration.S_PROJECTED_HEIGHT_MM)
    )
    assert every.terms["pin S projected axis zone"] == pytest.approx(
        AIR.S_ZONE_TILT * AIR.DISC_TILT_LEVER
    )
    assert every.statistical_mm < AIR.COLLAR_AIR_MIN
    assert AIR.COLLAR_AIR.statistical_mm >= AIR.COLLAR_AIR_MIN
    assert AIR.COLLAR_AIR_MIN == pytest.approx(0.004 * 25.4)


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
    # The study's caveats are budgeted, not left out: the gated stack charges
    # the first four, and the S zone stands in the every-source stack MHA-PD-00's
    # feeler accepts.
    for source in (
        "hub rock on the sleeve boss",
        "sleeve cocking on the pin",
        "knob journal tilt in the plate bore",
        "knob K projected axis zone",
    ):
        assert stack.terms[source] > 0.0, source
    assert AIR.COLLAR_AIR_UNACCEPTED.terms["pin S projected axis zone"] > 0.0
    for label, _, band in (term for term, _ in FIT.M_FWD_CHAIN):
        assert stack.terms[label] == band
    # Service motions add arithmetically; only made sizes are RSS'd.
    assert "arm plate loaded-seat change" in AIR.IN_SERVICE_CLEARANCES


def test_forward_stop_chain_pivots_on_the_pin_load_wall():
    # The loose front bushing and its retaining ring cock together about the
    # load wall's broken edge; the disc pivots on its least broken contact.
    brk = 0.254  # the inch title block's .010 break
    hub_face = (
        min(
            HUB.HUB_DIA - printed_band_mm(HUB.HUB_DIA_PLACES, unit=HUB.UNIT),
            FRONT_BUSHING.OD
            - printed_band_mm(FRONT_BUSHING.OD_PLACES, unit=FRONT_BUSHING.UNIT),
        )
        / 2.0
        - brk
    )
    nose = (FIT.SLEEVE.BOSS_DIA + min(FIT.SLEEVE.BOSS_DIA_BAND)) / 2.0 - brk
    assert AIR.HUB_FACE_STOP_R == pytest.approx(hub_face)
    assert AIR.NOSE_STOP_R == pytest.approx(nose)
    assert AIR.DISC_STOP_R == pytest.approx(min(HUB.SEAT_CONTACT_R, hub_face, nose))
    cock = math.atan(
        FIT.BORE_DIAMETRAL_CLEARANCE[1]
        / (FRONT_BUSHING.LENGTH - FIT_LENGTH_BAND_IN - 2.0 * brk)
    )
    wall = FRONT_BUSHING.PIN.DIA_MIN / 2.0 - brk
    term = AIR.COLLAR_AIR.terms["front bushing and ring cocking on the pin"]
    assert term == pytest.approx(cock * (max(hub_face, nose) - wall))
    assert "front bushing and ring cocking on the pin" in AIR.IN_SERVICE_CLEARANCES


def test_platen_air_budgets_the_pin_zone_and_governs():
    platen = ASSEMBLY.PLATEN_AIR
    assert platen.terms["pin S projected axis zone"] > 0.0
    # Cluster rearward, the step stands off the ring's load wall by the
    # forward chain, the tooth length and the shimmed ring gap: the shims
    # replace the rear bushing in the stack.
    window = FIT.RING_FLOAT_RANGE[1] - FIT.RING_FLOAT_RANGE[0]
    assert platen.terms[FIT.SHIM_WINDOW_LABEL] == pytest.approx(window)
    for label, _, band in (FIT.GS, FIT.AT, FIT.RT, FIT.LFB, FIT.OL, FIT.TL, FIT.SP):
        assert platen.terms[label] == pytest.approx(band), label
    assert FIT.LRB[0] not in platen.terms
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
