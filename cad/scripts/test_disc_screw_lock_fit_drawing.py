"""Ruling R9-47, parts (1) and (2): the MHA-PD-VN-55 disc screws cut to fit and the
platen's float faced to fit, each judged at the printed worst case.

Each test recomputes the worst corner from the catalogue and the printed
bands, not from the specs' derived constants, then holds the spec to it; the
negative controls exec a fresh copy of the owning module against a perturbed
input and show its import-time assert refuses it.
"""

from __future__ import annotations

import importlib.util

import pytest

import pd_paper_drive_assembly_steps as steps
import pd_platen_guide_spec as guide
import pd_rack_pinion_spec as disc
import pd_transgear_disc_hub_spec as hub
import pd_vn_transgear_disc_screw_spec as screw
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


def _mm_window(text: str) -> tuple[float, ...]:
    """A printed mm window (``0.00-0.20``) as millimetres."""
    return tuple(float(v) for v in text.split("-"))


def _inside(printed: tuple[float, ...], limits: tuple[float, float], step: float) -> None:
    """The mm sheet prints the inch window rounded inward by under one step."""
    assert limits[0] <= printed[0] < limits[0] + step
    assert limits[1] - step < printed[1] <= limits[1]


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
    with pytest.raises(AssertionError, match="MHA-PD-VN-55 disc screw .* worst engagement"):
        _exec_fresh(screw)


def test_a_stock_screw_stopping_short_of_the_window_is_refused(monkeypatch) -> None:
    # A disc that may run .016 thick leaves the shortest stock .013 inside:
    # no cut can bring it back into the window.
    monkeypatch.setattr(disc, "FACE_WIDTH_MAX", FACE + 0.016 * IN)
    with pytest.raises(AssertionError, match="MHA-PD-VN-55 disc screw tip .* shortest"):
        _exec_fresh(screw)


def test_platen_float_fitted_to_keep_the_disc_clear_of_the_platen() -> None:
    """The platen yaws about the bar end, so its float reaches the disc
    multiplied by k = 226/(226 - 80.892); the disc rear stands 2.2 - 1.0262
    off the platen front before it (R9-47 design stack). At the old 0.31 max
    the stack behind the disc (m 0.20, cluster float 0.40, tilt 0.081,
    squareness 0.05) runs negative; at the fitted .009 (0.2286) it clears."""
    k = 226.0 / (226.0 - 80.892)
    behind = 0.20 + 0.40 + (40.7735 - 4.1) * 0.050 / 22.55 + 0.05

    def air(fit_max: float) -> float:
        return 2.2 - 1.0262 - fit_max * k - behind

    assert k == pytest.approx(1.5575, abs=1e-4)
    assert air(0.31) < 0.0
    assert guide.LOCK_GAP_FIT == pytest.approx((0.002 * IN, 0.009 * IN))
    assert air(guide.LOCK_GAP_FIT[1]) == pytest.approx(0.087, abs=1e-3)
    # As made, the shallowest rail on the deepest bar floats .011: every
    # rail's seats are faced down into the window, none is short of it.
    as_made_min = (0.40 - 0.010) * IN - 9.6266
    assert as_made_min == pytest.approx(0.2794)
    assert as_made_min >= guide.LOCK_GAP_FIT[1]


def test_a_float_window_the_rails_cannot_reach_is_refused(monkeypatch) -> None:
    import build_pd_platen_guide

    monkeypatch.setattr(guide, "LOCK_GAP_FIT", (0.05, 0.40))
    with pytest.raises(AssertionError, match="as-made lock gap under the fitted"):
        _exec_fresh(build_pd_platen_guide)


def test_fit_up_adjustments_are_complete_and_ordered_before_installation() -> None:
    """Facing/cutting limits and checks belong to one ordered assembly step,
    regardless of how many physical text lines the print needs."""
    import re

    import draw_pd_paper_drive_assembly as drawing

    seq = steps.SEQUENCE
    assert seq.index("lock-seats-faced") == seq.index("guide-locks-set") + 1
    assert (
        seq.index("disc-cluster-assembled")
        < seq.index("disc-taps-transferred")
        < seq.index("disc-screws-cut")
        < seq.index("disc-cluster-hung")
    )
    # Only ordering/facing prose is under test; this is not a release window.
    from types import SimpleNamespace

    text = drawing._step_text(
        operating_domain=SimpleNamespace(axis_from_left_end_limits_mm=(0.0, 1.0))
    )
    printed = drawing._step_column("", steps.SEQUENCE, text)

    def printed_step(key: str) -> str:
        match = re.search(
            rf"^{steps.step_number(key)}\. (.*?)(?=^\d+\. |\Z)",
            printed,
            re.MULTILINE | re.DOTALL,
        )
        assert match is not None, key
        return " ".join(match.group(1).split())

    lock_step = printed_step("lock-seats-faced")
    float_window = re.search(
        r"\bIS (\d*\.\d+-\d*\.\d+): THE PLATEN'S FORE-AFT FLOAT\b",
        lock_step,
    )
    assert float_window is not None
    _inside(_mm_window(float_window.group(1)), guide.LOCK_GAP_FIT, 0.001)
    assert re.search(r"\bELSE\b.*\bSTOP\b.*\bREPORT\b", lock_step)

    cut_step = printed_step("disc-screws-cut")
    assert drawing.BOM_PART_NUMBERS["pd-vn-transgear-disc-screw"] in cut_step
    tip_window = re.search(
        r"\bCUT\b.*\bTIPS (\d*\.\d+-\d*\.\d+) BELOW DISC REAR FACE\b",
        cut_step,
    )
    assert tip_window is not None
    _inside(_mm_window(tip_window.group(1)), screw.TIP_BELOW_REAR_FACE, 0.01)
    # The cut end's break is the title block's edge break, so no limit here.
    assert re.search(r"\bBREAK THE CUT END\.", cut_step)
    assert " IN " not in f" {cut_step} " and " IN " not in f" {lock_step} "
