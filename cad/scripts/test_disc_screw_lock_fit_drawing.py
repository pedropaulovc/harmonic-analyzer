"""Ruling R9-47, parts (1) and (2): the MHA-SH-VN-59 DiscScrew disc screws cut to fit and the
platen's float faced to fit, each judged at the printed worst case.

Each test recomputes the worst corner from the catalogue and the printed
bands, not from the specs' derived constants, then holds the spec to it; the
negative controls exec a fresh copy of the owning module against a perturbed
input and show its import-time assert refuses it.
"""

from __future__ import annotations

import importlib.util

import pytest

import pd_platen_guide_spec as guide
import pd_rack_pinion_spec as disc
import pd_transgear_disc_hub_spec as hub
import pd_transgear_disc_screw_spec as screw
from _printed_tolerance import printed_band_mm

IN = 25.4
# 91794A055: #0-80 x 1/4 under the head; ASME B18.6.3 length band +0/-0.03 in.
SHANK_LEN = 0.25 * IN
LENGTH_MINUS = 0.03 * IN
MAJOR = 0.060 * IN
PITCH = IN / 80.0
# MHA-PD-17 flange .094 (title block 3-place +/-.005); MHA-PD-06 face .118 +/-.005.
FLANGE = 0.094 * IN
FACE = 0.118 * IN
THREE_PLACE = printed_band_mm(3, unit="in")
# MHA-PD-06's tap mouths: a .004 burr break on each, its loss counted from the
# tap drill (rack_pinion_spec, as printed on its sheet; R9-63).
MOUTH_BREAK = 0.004 * IN


def _exec_fresh(module) -> None:
    spec = importlib.util.spec_from_file_location(
        f"_{module.__name__}_perturbed", module.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)


def test_uncut_stock_tip_stands_proud_of_the_disc_rear_face() -> None:
    """Negative control on the old joint: the longest stock on the thinnest
    flange and disc stands .048 proud of the disc's rear face, into the
    platen's path; the shortest on the thickest stops .002 inside."""
    proud = SHANK_LEN - (FLANGE - THREE_PLACE) - (FACE - THREE_PLACE)
    inside = (FLANGE + THREE_PLACE) + (FACE + THREE_PLACE) - (SHANK_LEN - LENGTH_MINUS)
    assert proud == pytest.approx(0.048 * IN, abs=1e-9)
    assert inside == pytest.approx(0.002 * IN, abs=1e-9)
    assert screw.STOCK_TIP_PROUD_MAX == pytest.approx(proud)
    assert screw.STOCK_TIP_INSIDE_REAR_MAX == pytest.approx(inside)
    # Proud stock is outside the cut window; the shortest needs no cut.
    assert not screw.TIP_BELOW_REAR_FACE[0] <= -proud
    assert screw.TIP_BELOW_REAR_FACE[0] <= inside <= screw.TIP_BELOW_REAR_FACE[1]


def test_cut_tips_sit_inside_the_disc_and_keep_one_and_a_half_d() -> None:
    """Cut .000-.008 below the rear face, the end broken to the title block's
    .010 chamfer max: the rear loses the deepest cut plus its break, or the
    shortest uncut stock's inside stand-off plus its incomplete first thread,
    whichever is more."""
    assert screw.TIP_BELOW_REAR_FACE == pytest.approx((0.0, 0.008 * IN))
    assert screw.CUT_END_BREAK_MAX == pytest.approx(0.010 * IN)
    inside = (FLANGE + THREE_PLACE) + (FACE + THREE_PLACE) - (SHANK_LEN - LENGTH_MINUS)
    rear_loss = max(MOUTH_BREAK, 0.008 * IN + 0.010 * IN, inside + PITCH)
    worst = (FACE - THREE_PLACE) - MOUTH_BREAK - rear_loss
    assert worst == pytest.approx(0.091 * IN, abs=1e-9)
    assert worst / MAJOR == pytest.approx(1.5167, abs=5e-4)
    assert worst >= 1.5 * MAJOR
    assert screw.ENGAGEMENT_WORST == pytest.approx(worst)
    assert screw.ENGAGEMENT_WORST_D >= disc.ENGAGEMENT_FLOOR_D == 1.5
    # The model is the installed screw, mid-window.
    assert screw.CUT_LENGTH == pytest.approx(FLANGE + FACE - 0.004 * IN)
    assert screw.LENGTH == screw.CUT_LENGTH
    assert hub.FLANGE_THICK == pytest.approx(FLANGE)
    assert disc.FACE_WIDTH == pytest.approx(FACE)


def test_assembly_places_the_cut_tip_inside_the_disc_rear_face() -> None:
    import build_pd_paper_drive_assembly as assembly

    tip = assembly.DISC_SCREW_Z0 + screw.LENGTH
    assert assembly.DISC_Z0 + assembly.DISC_FACE - tip == pytest.approx(0.004 * IN)


def test_a_disc_too_thin_for_the_cut_screw_is_refused(monkeypatch) -> None:
    # A .102 face at its printed min leaves the cut screw under 1.5D.
    monkeypatch.setattr(disc, "FACE_WIDTH_MIN", 0.102 * IN)
    with pytest.raises(AssertionError, match="MHA-SH-VN-59 DiscScrew in .* worst engagement"):
        _exec_fresh(screw)


def test_a_stock_screw_stopping_short_of_the_window_is_refused(monkeypatch) -> None:
    # A disc that may run .016 thick leaves the shortest stock .013 inside:
    # no cut can bring it back into the window.
    monkeypatch.setattr(disc, "FACE_WIDTH_MAX", FACE + 0.016 * IN)
    with pytest.raises(AssertionError, match="MHA-SH-VN-59 DiscScrew tip .* shortest"):
        _exec_fresh(screw)


def test_platen_float_checked_by_leaves_keeps_the_disc_clear_of_the_platen() -> None:
    """Owner ruling 2026-11-24, audit part 2 question C4: "(b) Rails .387
    +.000/-.007; check "A .004 LEAF ENTERS AND A .017 LEAF DOES NOT". Air 0.067
    mm at the widest gap; no seat is ever milled." The air is the assembly's
    statistical disc-to-platen stack with the float at the .017 leaf (0.0508
    at Q5's form (c), where his 0.067 was read at form (b))."""
    import build_pd_paper_drive_assembly as assembly

    assert guide.LOCK_GAP_FIT == pytest.approx((0.004 * IN, 0.017 * IN))
    platen = assembly.PLATEN_AIR
    assert platen.terms["platen float at the near lock"] == pytest.approx(
        guide.LOCK_GAP_FIT[1] * assembly.PLATEN_YAW_LEVER
    )
    assert assembly.DISC_PLATEN_AIR >= assembly.DISC_PLATEN_AIR_MIN
    assert assembly.DISC_PLATEN_AIR == pytest.approx(0.0508, abs=5e-4)
    # As made, rail .380-.387 on bar .371-.375 (#1563 option C): .005 to
    # .016, inside the two leaves on every part the sheets allow.
    as_made = ((0.387 - 0.007) * IN - 0.375 * IN, 0.387 * IN - 0.371 * IN)
    assert as_made == pytest.approx((0.005 * IN, 0.016 * IN))
    assert guide.LOCK_GAP_FIT[0] < as_made[0] <= as_made[1] < guide.LOCK_GAP_FIT[1]


def test_a_leaf_check_the_rails_cannot_meet_is_refused(monkeypatch) -> None:
    import build_pd_platen_guide

    monkeypatch.setattr(guide, "LOCK_GAP_FIT", (0.05, 0.40))
    with pytest.raises(AssertionError, match="as-made lock gap .* outside the leaf"):
        _exec_fresh(build_pd_platen_guide)
