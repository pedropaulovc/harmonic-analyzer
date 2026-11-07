"""The step registry matches the numbers MHA-DT-00 prints (SolidWorks-free)."""

from __future__ import annotations

import re
from fractions import Fraction

from _assembly_contract import assembly_contract
import _config
import dt_cone_gear_stack
import cone_stack_end_play
import draw_dt_drive_train_assembly as drawing
import dt_drive_train_assembly_sheet as sheet
import dt_drive_train_steps as steps
import pinion_rig_tip_gap as tip_gap
import pytest

SEQUENCE_BLOCKS = (
    drawing.CONE_CRANK_STEPS,
    drawing.BANK_STEPS,
    drawing.rig_steps(pivot_blocks=2, cams=2, slotted=4),
)
TIP_GAP_FEELER = f"{tip_gap.TIP_GAP_SETTING_TEXT} FEELER"
STEP_HEAD = re.compile(r"^\s*(\d+)\. ", re.MULTILINE)


def _step_body(key: str) -> str:
    """The printed text of one step, from its head to the next head."""
    text = "\n".join(SEQUENCE_BLOCKS)
    heads = list(STEP_HEAD.finditer(text))
    number = steps.step_number(key)
    index = next(i for i, head in enumerate(heads) if int(head.group(1)) == number)
    end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
    return " ".join(text[heads[index].end() : end].split())


def test_the_printed_step_heads_are_the_registry_in_order() -> None:
    printed = [int(n) for block in SEQUENCE_BLOCKS for n in STEP_HEAD.findall(block)]
    assert printed == list(range(1, len(steps.SEQUENCE) + 1))


def test_a_key_resolves_to_its_position_and_prints_a_pointer() -> None:
    for index, key in enumerate(steps.SEQUENCE, start=1):
        assert steps.step_number(key) == index
        assert steps.step_ref(key) == f"{assembly_contract('dt-drive-train').number} STEP {index}"
    with pytest.raises(KeyError):
        steps.step_number("no-such-step")


@pytest.mark.parametrize(
    ("text", "key", "phrase"),
    ((drawing.CHECKS, "rig-located", TIP_GAP_FEELER),),
)
def test_each_typed_step_cite_names_the_step_that_does_it(
    text: str, key: str, phrase: str
) -> None:
    """Until the drawing's cites read the registry, each typed "STEP n" (or
    its lettered sub-step) must be the step that sets the condition it points at."""
    assert re.search(rf"STEP {steps.step_number(key)}[A-HJ-NP-Z]?\)", " ".join(text.split()))
    assert phrase in _step_body(key)


def test_the_cone_stack_step_prints_measured_limits() -> None:
    """The fitter accepts the touching gear stack before setting the tip."""
    low, high = dt_cone_gear_stack.STACK_L20_ACCEPT
    stack = _step_body("cone-gears-stacked")
    assert "MHA-DT-07" in stack and "MHA-DT-03" in stack
    assert "T120 FIRST THROUGH T006" in stack
    assert "EACH FLAT TO FLAT AND AGAINST THE LAST" in stack
    # The decimal-inch window rounds inward, a thousandth inside each limit.
    printed = re.search(r"T006 BACK FACE: ACCEPT (\d*\.\d{3})-(\d*\.\d{3})\.", stack)
    assert printed is not None
    first, last = (float(value) * 25.4 for value in printed.groups())
    assert low <= first < low + 0.0254 and high - 0.0254 < last <= high
    # The remedy is its own sub-step after the check (rule 22).
    assert stack.index("ACCEPT") < stack.index("IF THE STACK IS LONG, RE-FACE ITS THICKEST GEAR")
    assert "IF SHORT, REMAKE ITS THINNEST GEAR" in stack


def test_the_tip_step_sets_the_collar_before_the_end_play() -> None:
    """User ruling 2026-09-29: the collar is set to T006 over the feeler and
    locked first, so the stack's float is fixed on the shaft before the cup
    screw sets MHA-DT-04's end play and the pinch screw locks it."""
    fitup = _step_body("tip-adjuster-set")
    # The tip's lateral error is taken up by turning MHA-DT-05 on its screws
    # (build_drive_train_assembly.TIP_LATERAL_CAPACITY_MM), so the post stays
    # turnable until the tip is centred in the cup, and is locked before the
    # end play is set (Codex P1 on #1136).
    order = (
        f"PUSH {_config.parts('dt-vn-cone-tip-collar')['number']} ONTO A "
        f"{sheet.inch_text(cone_stack_end_play.COLLAR_FEELER, sheet.FEELER_PLACES)} FEELER ON T006",
        "LOCK ITS SET SCREW",
        "THREAD MHA-DT-VN-55 INTO MHA-DT-21",
        "TURN MHA-DT-05 ON ITS SCREWS UNTIL THE TIP CENTRES IN THE CUP",
        "TIGHTEN BOTH MHA-DT-VN-61",
        "JUST STOPS SHUTTLING",
        "TIGHTEN MHA-DT-VN-56",
    )
    positions = [fitup.find(phrase) for phrase in order]
    assert -1 not in positions, positions
    assert positions == sorted(positions)
    # The block is placed by its hold-down alone: nothing is set against it,
    # and the post is left free to turn.
    placed = _step_body("post-and-tip-block")
    assert "MHA-DT-VN-60 UP FROM UNDER THE PLATE" in placed
    assert "FEELER" not in placed
    assert "LEAVE MHA-DT-VN-61 LOOSE ENOUGH TO TURN MHA-DT-05" in placed


def test_the_printed_shaft_end_play_is_the_band_the_stacks_book() -> None:
    """The collar-to-block air and the adjuster's embed window book
    cone_stack_end_play.SHAFT_END_PLAY; the sheet prints that band, rounded
    inward to the thousandth."""
    match = re.search(
        r"END PLAY WITH A DIAL INDICATOR ON THE SHAFT END, PUSHING THE SHAFT BACK AND "
        r"FORTH ALONG ITS AXIS: (\.\d{3})-(\.\d{3})",
        _step_body("tip-adjuster-set"),
    )
    assert match is not None
    low, high = (float(value) * 25.4 for value in match.groups())
    least, most = cone_stack_end_play.SHAFT_END_PLAY
    assert least <= low < least + 0.0254 and most - 0.0254 < high <= most
    assert 0.0 < low < high


def test_post_screws_keep_spec_owned_stock_and_cut_to_fit_acceptance() -> None:
    import dt_vn_post_mount_screw_spec as screw

    row = _config.parts("dt-vn-post-mount-screw")
    fitup = _step_body("post-and-tip-block")
    assert row["number"] == drawing.BOM_PART_NUMBERS["dt-vn-post-mount-screw"]
    assert row["supplier_skus"][0] == screw.SKU
    assert f"MSC {screw.SKU}" in drawing.BOM_DESCRIPTIONS["dt-vn-post-mount-screw"]
    assert (
        f"MSC {screw.SKU}, {screw.THREAD} X {screw.STOCK_LENGTH_MM / 25.4:g} IN STOCK"
        in fitup
    )
    places = screw.DRAWING_PRECISION_BY_NAME[screw.CUT_LENGTH_DIMENSION]
    assert f"({sheet.inch_text(screw.CUT_LENGTH_MM, places)}) REF CUT LENGTH" in fitup
    # The step prints the part sheet's exact maximum short, never a wider one.
    printed_short = float(re.search(r"FLUSH TO (\d*\.\d+) SHORT", fitup).group(1))
    assert printed_short * 25.4 == pytest.approx(screw.POST_SCREW_CUT_TO_FIT_SHORT, abs=1e-9)
    assert "CUT EACH MHA-DT-VN-61 TO FIT" in fitup and "UNDERSIDE, NEVER PROUD" in fitup
    assert "DEBURR THE ENDS" in fitup
    assert screw.FIXED_CUT_LENGTH_EXISTS is False
    assert screw.STOCK_LENGTH_MM >= screw.FIXED_LENGTH_ENGAGEMENT_MIN_MM
    assert (
        0.0
        <= screw.FLUSH_LENGTH_MM - screw.CUT_LENGTH_MM
        <= screw.POST_SCREW_CUT_TO_FIT_SHORT
    )
    assert drawing.POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT in fitup
    from machinist_exceptions import load_exceptions

    declared = {
        entry.id: entry
        for entry in load_exceptions(_config.CONFIG_DIR, "dt_drive_train_assembly", "assembly")
    }
    assert declared["DT-02"].kind == "minor"
    assert drawing.POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT in declared["DT-02"].where


def test_crank_fit_reads_t120_before_the_full_turn_and_retention_drilling() -> None:
    import dt_crank_pinion_spec as pinion

    fitup = _step_body("crank-mesh-checked")
    order = (
        "SLIDE MHA-DT-10 ON, UNPINNED",
        f"SET MHA-DT-10 {sheet.inch_text(pinion.SEAT_FEELER_MM, sheet.FEELER_PLACES)} OFF",
        "PUSH MHA-DT-10 AND T120 TOWARD EACH OTHER",
        f"A {sheet.T120_FITUP_FEELER_TEXT} FEELER PASSES ALL ROUND",
        "BETWEEN THE MHA-DT-10 BAND AND THE T120 TIPS",
        "BETWEEN THE MHA-DT-10 SHOULDER AND THE T120 FRONT FACE",
        "IF THE FEELER STOPS AT THE BAND, TURN THE MHA-DT-10 BAND DOWN",
        f"Ø{sheet.inch_min_text(pinion.TURNED_DIA_FITUP_MIN, 3)} MIN",
        "AT THE SHOULDER, FACE THE MHA-DT-10 SHOULDER BACK",
        f"{sheet.inch_min_text(pinion.SHOULDER_LENGTH_FITUP_MIN, 3)} MIN",
        "REPEAT 4C-4G",
        "TURN MHA-DT-07 ONE FULL REVOLUTION BY HAND: IT MUST NEVER BIND",
        "MATCH-DRILL THROUGH THE MHA-DT-10",
        "TURN MHA-DT-07 ONE FULL REVOLUTION AGAIN: NO BINDING",
    )
    positions = [fitup.index(phrase) for phrase in order]
    assert positions == sorted(positions)
    assert "FLUSH BOTH SIDES" in fitup
    assert "BACKLASH" not in fitup
    assert "WORST-CASE" not in fitup


def test_full_turn_checks_use_the_spec_ratio_and_clear_the_unrelieved_platform() -> None:
    import dt_crank_drive_gear_spec as gear64
    import dt_crank_pinion_spec as pinion

    checks = " ".join(drawing.CHECKS.split())
    ratio = Fraction(pinion.TEETH, gear64.TEETH)
    assert f"CONE SET {ratio} TURN ({pinion.TEETH}T:{gear64.TEETH}T)" in checks
    assert "WITHOUT BINDING THROUGH ONE FULL MHA-DT-07 TURN" in checks
    assert "MHA-DT-07 CLEAR OF THE UNRELIEVED MHA-DT-20 TOP THROUGHOUT" in checks
    assert "RELIEF THROUGHOUT" not in checks
    assert "FINISHING IN THE RUNNING DIRECTION TO TAKE UP PLAY" in checks
    assert "TURN THE CRANK FORWARD (CLOCKWISE, SHEET 1 FRONT VIEW)" in checks
    # The crank mesh's free turn is check 2; the step-4 turn is the same test.
    assert "TURN MHA-DT-07 ONE FULL REVOLUTION BY HAND: IT MUST NEVER BIND" in _step_body(
        "crank-mesh-checked"
    )


def test_step_four_holds_the_collar_on_the_boss_and_leaves_the_end_proud() -> None:
    # Owner ruling D1 (2026-10-15): no crank-seat washer.  The collar bears on
    # the boss, the feeler is the end play, and the shaft end is left proud.
    import dt_crank_pinion_spec as pinion
    import dt_crankshaft_spec as crankshaft

    fitup = _step_body("crank-mesh-checked")
    least, most = crankshaft.SHAFT_END_PROUD_RANGE
    assert least >= 0.0
    order = (
        "MHA-DT-11 COLLAR REAR FACE HARD ON THE MHA-DT-05 BOSS FRONT FACE, NO WASHER",
        f"SET MHA-DT-10 {sheet.inch_text(pinion.SEAT_FEELER_MM, sheet.FEELER_PLACES)} "
        "OFF THE BOSS BACK FACE WITH A FEELER: END PLAY = THE FEELER",
        "MATCH-DRILL THROUGH THE MHA-DT-10",
        f"END STANDS {drawing.inch_envelope((least, most), 3)} PROUD OF THE MHA-DT-10 BACK FACE",
        "DO NOT FACE",
    )
    positions = [fitup.index(phrase) for phrase in order]
    assert positions == sorted(positions)
    # A stack result the fitter cannot adjust: every accepted part set,
    # including both extremes, must fall inside the printed range.
    printed = fitup.split("END STANDS ", 1)[1].split(" PROUD", 1)[0]
    low, high = (float(limit) * 25.4 for limit in printed.split("-"))
    assert low <= least and most <= high
    assert "SHIM" not in fitup and "MHA-CH-VN-57" not in fitup


def test_step_four_holds_the_collar_before_the_feeler_and_the_pin() -> None:
    body = _step_body("crank-mesh-checked")
    positions = [
        body.index("HOLD THE MHA-DT-11 COLLAR REAR FACE HARD ON THE MHA-DT-05 BOSS FRONT"),
        body.index("OFF THE BOSS BACK FACE WITH A FEELER"),
        body.index("MATCH-DRILL THROUGH THE MHA-DT-10"),
    ]
    assert positions == sorted(positions)


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: RIG SET sets the rig along the bank, not its tip gap."""
    assert TIP_GAP_FEELER not in _step_body("rig-set")



