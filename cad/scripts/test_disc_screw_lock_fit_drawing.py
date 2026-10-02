"""Ruling R9-47, parts (1) and (2): the MHA-161 disc screws cut to fit and the
platen's float faced to fit, each judged at the printed worst case.

Each test recomputes the worst corner from the catalogue and the printed
bands, not from the specs' derived constants, then holds the spec to it; the
negative controls exec a fresh copy of the owning module against a perturbed
input and show its import-time assert refuses it.
"""

from __future__ import annotations

import importlib.util

import pytest

import paper_drive_assembly_steps as steps
import platen_guide_spec as guide
import rack_pinion_spec as disc
import transgear_disc_hub_spec as hub
import transgear_disc_screw_spec as screw

IN = 25.4
# 91794A055: #0-80 x 1/4 under the head; ASME B18.6.3 length band +0/-0.03 in.
SHANK_LEN = 0.25 * IN
LENGTH_MINUS = 0.03 * IN
MAJOR = 0.060 * IN
PITCH = IN / 80.0
# MHA-159 flange 2.40 (title block 3-place +/-0.13); MHA-070 face 3.00 +/-0.13.
FLANGE = 2.4
FACE = 3.0
THREE_PLACE = 0.13
# MHA-070's tap mouths: a 0.10 burr break on each, its loss counted from the
# tap drill (rack_pinion_spec, as printed on its sheet; R9-63).
MOUTH_BREAK = 0.10


def _exec_fresh(module) -> None:
    spec = importlib.util.spec_from_file_location(
        f"_{module.__name__}_perturbed", module.__file__
    )
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)


def test_uncut_stock_tip_stands_proud_of_the_disc_rear_face() -> None:
    """Negative control on the old joint: the longest stock on the thinnest
    flange and disc stands 1.21 proud of the disc's rear face, into the
    platen's path; the shortest on the thickest stops 0.072 inside."""
    proud = SHANK_LEN - (FLANGE - THREE_PLACE) - (FACE - THREE_PLACE)
    inside = (FLANGE + THREE_PLACE) + (FACE + THREE_PLACE) - (SHANK_LEN - LENGTH_MINUS)
    assert proud == pytest.approx(1.21, abs=1e-9)
    assert inside == pytest.approx(0.072, abs=1e-9)
    assert screw.STOCK_TIP_PROUD_MAX == pytest.approx(proud)
    assert screw.STOCK_TIP_INSIDE_REAR_MAX == pytest.approx(inside)
    # Proud stock is outside the cut window; the shortest needs no cut.
    assert not screw.TIP_BELOW_REAR_FACE[0] <= -proud
    assert screw.TIP_BELOW_REAR_FACE[0] <= inside <= screw.TIP_BELOW_REAR_FACE[1]


def test_cut_tips_sit_inside_the_disc_and_keep_one_and_a_half_d() -> None:
    """Cut 0.00-0.20 below the rear face, end broken 0.1 max: the rear loses
    the deepest cut plus its break, or the shortest uncut stock's inside
    stand-off plus its incomplete first thread, whichever is more."""
    assert screw.TIP_BELOW_REAR_FACE == (0.0, 0.2)
    assert screw.CUT_END_BREAK_MAX == 0.1
    assert screw.TIP_BELOW_REAR_FACE_TEXT == "0.00-0.20"
    assert screw.CUT_END_BREAK_TEXT == "0.1 MAX"
    inside = (FLANGE + THREE_PLACE) + (FACE + THREE_PLACE) - (SHANK_LEN - LENGTH_MINUS)
    rear_loss = max(MOUTH_BREAK, 0.2 + 0.1, inside + PITCH)
    worst = (FACE - THREE_PLACE) - MOUTH_BREAK - rear_loss
    assert worst == pytest.approx(2.3805, abs=1e-9)
    assert worst / MAJOR == pytest.approx(1.562, abs=5e-4)
    assert worst >= 1.5 * MAJOR
    assert screw.ENGAGEMENT_WORST == pytest.approx(worst)
    assert screw.ENGAGEMENT_WORST_D >= disc.ENGAGEMENT_FLOOR_D == 1.5
    # The model is the installed screw, mid-window.
    assert screw.CUT_LENGTH == pytest.approx(FLANGE + FACE - 0.1)
    assert screw.LENGTH == screw.CUT_LENGTH
    assert hub.FLANGE_THICK == FLANGE and disc.FACE_WIDTH == FACE


def test_assembly_places_the_cut_tip_inside_the_disc_rear_face() -> None:
    import build_paper_drive_assembly as assembly

    tip = assembly.DISC_SCREW_Z0 + screw.LENGTH
    assert assembly.DISC_Z0 + assembly.DISC_FACE - tip == pytest.approx(0.1)


def test_a_disc_too_thin_for_the_cut_screw_is_refused(monkeypatch) -> None:
    # A 2.6 face at its printed min leaves the cut screw under 1.5D.
    monkeypatch.setattr(disc, "FACE_WIDTH_MIN", 2.6)
    with pytest.raises(AssertionError, match="MHA-161 disc screw .* worst engagement"):
        _exec_fresh(screw)


def test_a_stock_screw_stopping_short_of_the_window_is_refused(monkeypatch) -> None:
    # A disc that may run 0.40 thick leaves the shortest stock 0.342 inside:
    # no cut can bring it back into the window.
    monkeypatch.setattr(disc, "FACE_WIDTH_MAX", FACE + 0.40)
    with pytest.raises(AssertionError, match="MHA-161 disc screw tip .* shortest"):
        _exec_fresh(screw)


def test_platen_float_fitted_to_keep_the_disc_clear_of_the_platen() -> None:
    """The platen yaws about the bar end, so its float reaches the disc
    multiplied by k = 226/(226 - 80.892); the disc rear stands 2.2 - 1.0262
    off the platen front before it (R9-47 design stack). At the old 0.31 max
    the stack behind the disc (m 0.20, cluster float 0.40, tilt 0.081,
    squareness 0.05) runs negative; at 0.25 it clears."""
    k = 226.0 / (226.0 - 80.892)
    behind = 0.20 + 0.40 + (40.7735 - 4.1) * 0.050 / 22.55 + 0.05

    def air(fit_max: float) -> float:
        return 2.2 - 1.0262 - fit_max * k - behind

    assert k == pytest.approx(1.5575, abs=1e-4)
    assert air(0.31) < 0.0
    assert guide.LOCK_GAP_FIT == (0.05, 0.25)
    assert guide.LOCK_GAP_FIT_TEXT == "0.05-0.25"
    assert air(guide.LOCK_GAP_FIT[1]) == pytest.approx(0.053, abs=1e-3)
    # As made, the shallowest rail on the thickest bar floats 0.37: every
    # rail's seats are faced down into the window, none is short of it.
    as_made_min = (10.0 - 0.50) - (9.0 + 0.13)
    assert as_made_min == pytest.approx(0.37)
    assert as_made_min >= guide.LOCK_GAP_FIT[1]


def test_a_float_window_the_rails_cannot_reach_is_refused(monkeypatch) -> None:
    import build_platen_guide

    monkeypatch.setattr(guide, "LOCK_GAP_FIT", (0.05, 0.40))
    with pytest.raises(AssertionError, match="as-made lock gap under the fitted"):
        _exec_fresh(build_platen_guide)


def test_both_fit_ups_are_one_line_a06_steps_in_order() -> None:
    import draw_paper_drive_assembly as drawing

    seq = steps.SEQUENCE
    assert seq.index("lock-seats-faced") == seq.index("guide-locks-set") + 1
    assert (
        seq.index("disc-cluster-assembled")
        < seq.index("hub-faced-to-nose")
        < seq.index("disc-taps-transferred")
        < seq.index("disc-screws-cut")
        < seq.index("disc-cluster-hung")
    )
    text = drawing._step_text()
    assert guide.LOCK_GAP_FIT_TEXT in text["lock-seats-faced"]
    assert "STOP AND REPORT" in text["lock-seats-faced"]
    cut = text["disc-screws-cut"]
    assert screw.TIP_BELOW_REAR_FACE_TEXT in cut and screw.CUT_END_BREAK_TEXT in cut
    column = drawing.FITUP_STEPS.splitlines()
    for key in ("lock-seats-faced", "disc-screws-cut"):
        (line,) = [ln for ln in column if ln.startswith(f"{steps.step_number(key)}. ")]
        assert line.endswith(text[key]), line
