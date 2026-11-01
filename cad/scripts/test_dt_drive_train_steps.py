"""The step registry matches the numbers MHA-DT-00 prints (SolidWorks-free)."""

from __future__ import annotations

import re
from fractions import Fraction

from _assembly_contract import assembly_contract
import _config
import dt_cone_gear_stack
import cone_stack_end_play
import draw_dt_drive_train_assembly as drawing
import dt_drive_train_steps as steps
import pinion_rig_tip_gap as tip_gap
import pytest

SEQUENCE_BLOCKS = (
    drawing.CONE_CRANK_STEPS,
    drawing.BANK_STEPS,
    drawing.rig_steps(pivot_blocks=2, cams=2, slotted=4),
)
TIP_GAP_FEELER = f"{tip_gap.TIP_GAP_FEELER:.2f} FEELER"
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
    """Until the drawing's cites read the registry, each typed "STEP n" must
    be the step that sets the condition it points at."""
    assert f"STEP {steps.step_number(key)})" in " ".join(text.split())
    assert phrase in _step_body(key)


def test_the_cone_stack_step_prints_measured_limits() -> None:
    """The fitter accepts the touching gear stack before setting the tip."""
    low, high = dt_cone_gear_stack.STACK_L20_ACCEPT
    stack = _step_body("cone-gears-stacked")
    assert "MHA-DT-07" in stack and "MHA-DT-03" in stack
    assert "T120 FIRST THROUGH T006" in stack
    assert "EACH FLAT TO FLAT AND AGAINST THE LAST" in stack
    assert f"{low:.3f}-{high:.3f}" in stack
    assert "RE-FACE A LONG STACK" in stack
    assert "REMAKE THE THINNEST GEAR OF A SHORT ONE" in stack


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
        f"{cone_stack_end_play.COLLAR_FEELER:.2f} FEELER ON T006",
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
    cone_stack_end_play.SHAFT_END_PLAY; the sheet prints exactly that band."""
    match = re.search(r"END PLAY (\d+\.\d+)-(\d+\.\d+)", _step_body("tip-adjuster-set"))
    assert match is not None
    printed = tuple(float(value) for value in match.groups())
    assert printed == cone_stack_end_play.SHAFT_END_PLAY
    assert 0.0 < printed[0] < printed[1]


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
    assert f"({screw.CUT_LENGTH_MM:.{places}f}) REF CUT LENGTH" in fitup
    # The step never understates the short the part sheet allows.
    printed_short = float(re.search(r"FLUSH TO (\d+\.\d+) SHORT", fitup).group(1))
    assert 0.0 <= printed_short - screw.POST_SCREW_CUT_TO_FIT_SHORT < 0.01
    assert "CUT TO FIT" in fitup and "UNDERSIDE, NEVER PROUD" in fitup
    assert "DEBURR ENDS" in fitup
    assert screw.FIXED_CUT_LENGTH_EXISTS is False
    assert screw.STOCK_LENGTH_MM >= screw.FIXED_LENGTH_ENGAGEMENT_MIN_MM
    assert (
        0.0
        <= screw.FLUSH_LENGTH_MM - screw.CUT_LENGTH_MM
        <= screw.POST_SCREW_CUT_TO_FIT_SHORT
    )
    assert drawing.POST_MOUNT_ENGAGEMENT_ASSEMBLY_FACT in fitup


def test_crank_fit_reads_t120_before_the_full_turn_and_retention_drilling() -> None:
    import dt_crank_pinion_spec as pinion

    fitup = _step_body("crank-mesh-checked")
    order = (
        "SLIDE MHA-DT-10 ON UNPINNED",
        f"SET MHA-DT-10 {pinion.SEAT_FEELER_MM:.2f} OFF",
        "PUSH MHA-DT-10 AND T120 TOWARD EACH OTHER",
        f"READING A {pinion.T120_FITUP_FEELER_MM:.2f} FEELER ALL ROUND",
        "MHA-DT-10 BAND TO T120 TIPS: IF THE FEELER STOPS",
        "TURN THE MHA-DT-10 BAND DOWN",
        f"Ø{pinion.TURNED_DIA_FITUP_MIN:.{pinion.TURNED_DIA_PLACES}f} MIN",
        "MHA-DT-10 SHOULDER TO T120 SOUTH FACE: IF THE FEELER STOPS",
        "FACE THE MHA-DT-10 SHOULDER BACK",
        f"{pinion.SHOULDER_LENGTH_FITUP_MIN:.{pinion.SHOULDER_LENGTH_PLACES}f} MIN",
        "RESET, RECHECK",
        "TURN MHA-DT-07 ONE FULL REVOLUTION; IT MUST NEVER BIND",
        "THEN MATCH-DRILL THROUGH THE MHA-DT-10",
        "RE-CHECK NO BINDING",
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
    assert "FINISHING IN THE CYLINDERS' RUNNING DIRECTION TO TAKE UP PLAY" in checks
    assert "BINDING THROUGH ONE FULL MHA-DT-07 TURN" in " ".join(
        drawing.FIT_PLACEHOLDER.split()
    )


def test_crank_end_fit_holds_the_collar_on_the_boss_and_leaves_the_end_proud() -> None:
    # Owner ruling D1 (2026-10-15): no crank-seat washer.  The collar bears on
    # the boss, the feeler is the end play, and the shaft end is left proud.
    import dt_crank_pinion_spec as pinion
    import dt_crankshaft_spec as crankshaft

    fitup = " ".join(drawing.CRANK_END_FIT_NOTES.split())
    least, most = crankshaft.SHAFT_END_PROUD_RANGE
    assert least >= 0.0
    order = (
        "MHA-DT-11 COLLAR REAR FACE HARD ON THE MHA-DT-05 BOSS SOUTH FACE",
        f"MHA-DT-10 ON THE {pinion.SEAT_FEELER_MM:.2f} FEELER OFF THE BOSS NORTH FACE",
        "MATCH-DRILL AND REAM FOR MHA-DT-29",
        "END PLAY = THE FEELER",
        f"END STANDS {least:.2f}-{most:.2f} PROUD OF MHA-DT-10 NORTH FACE",
        "DO NOT FACE",
    )
    positions = [fitup.index(phrase) for phrase in order]
    assert positions == sorted(positions)
    assert f"(STEP {steps.step_number('crank-mesh-checked')})" in fitup
    assert "SHIM" not in fitup and "MHA-CH-VN-57" not in fitup


def test_step_four_holds_the_collar_before_the_feeler_and_the_pin() -> None:
    body = _step_body("crank-mesh-checked")
    positions = [
        body.index("HOLD THE MHA-DT-11 COLLAR HARD ON THE BOSS SOUTH FACE"),
        body.index("OFF THE MHA-DT-05 BOSS NORTH FACE WITH A FEELER"),
        body.index("MATCH-DRILL THROUGH THE MHA-DT-10"),
    ]
    assert positions == sorted(positions)


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: RIG SET sets the rig along the bank, not its tip gap."""
    assert TIP_GAP_FEELER not in _step_body("rig-set")



