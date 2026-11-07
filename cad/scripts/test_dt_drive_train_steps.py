"""The step registry matches the numbers MHA-DT-00 prints (SolidWorks-free)."""

from __future__ import annotations

import re
from fractions import Fraction

from _assembly_contract import assembly_contract
from _test_assembly_steps import step_structure_violations
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
    assert "IF IT IS SHORT, REMAKE ITS THINNEST GEAR" in stack


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
    # The block is placed by its hold-down, squared and doweled (rule-23
    # retention, owner ruling 2026-11-07 (MHA-DT-00 rubric sample, PR
    # #2248)): nothing is set against it, and the post is left free to turn.
    placed = _step_body("post-and-tip-block")
    assert "RUN MHA-DT-VN-60 UP THRU THE MHA-DT-20 COUNTERBORE" in placed
    assert "FEELER" not in placed
    assert "RUN BOTH MHA-DT-VN-61 IN, LOOSE ENOUGH TO TURN MHA-DT-05" in placed


def test_the_printed_shaft_end_play_is_the_band_the_stacks_book() -> None:
    """The collar-to-block air and the adjuster's embed window book
    cone_stack_end_play.SHAFT_END_PLAY; the sheet prints that band, rounded
    inward to the thousandth."""
    match = re.search(
        r"DIAL-INDICATE THE MHA-DT-04 END PLAY AT THE SHAFT END: (\.\d{3})-(\.\d{3})",
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
    # Rubric sample round 6 (rule 22): the stock is the BOM row's, not step 2's.
    assert (
        f"{screw.THREAD} X {screw.STOCK_LENGTH_MM / 25.4:g} FILLISTER STOCK, MSC {screw.SKU}"
        == drawing.BOM_DESCRIPTIONS["dt-vn-post-mount-screw"]
    )
    assert f"MSC {screw.SKU}" not in fitup
    places = screw.DRAWING_PRECISION_BY_NAME[screw.CUT_LENGTH_DIMENSION]
    assert f"({sheet.inch_text(screw.CUT_LENGTH_MM, places)}) REF LONG" in fitup
    # The step prints the part sheet's exact maximum short, never a wider one.
    printed_short = float(re.search(r"FLUSH TO (\d*\.\d+) SHORT", fitup).group(1))
    assert printed_short * 25.4 == pytest.approx(screw.POST_SCREW_CUT_TO_FIT_SHORT, abs=1e-9)
    assert "CUT EACH MHA-DT-VN-61 TO FIT" in fitup and "UNDERSIDE, NEVER PROUD" in fitup
    assert "DEBURR THE CUT ENDS" in fitup
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
        "SLIDE MHA-DT-10 ON WITHOUT ITS PIN",
        f"SET MHA-DT-10 {sheet.inch_text(pinion.SEAT_FEELER_MM, sheet.FEELER_PLACES)} OFF",
        "PUSH MHA-DT-10 AND T120 TOWARD EACH OTHER",
        f"A {sheet.T120_FITUP_FEELER_TEXT} FEELER PASSES ALL ROUND",
        "BETWEEN THE MHA-DT-10 BAND AND THE T120 TIPS",
        "BETWEEN THE MHA-DT-10 SHOULDER AND THE T120 FRONT FACE",
        "IF IT STOPS AT THE BAND, TURN MHA-DT-10'S BAND DOWN",
        f"Ø{sheet.inch_min_text(pinion.TURNED_DIA_FITUP_MIN, 3)} MIN",
        "IF IT STOPS AT THE SHOULDER, FACE THE SHOULDER BACK",
        f"{sheet.inch_min_text(pinion.SHOULDER_LENGTH_FITUP_MIN, 3)} MIN",
        "REPEAT 4E-4J",
        "TURN MHA-DT-07 ONE FULL REVOLUTION BY HAND: IT MUST NEVER BIND",
        "MATCH-DRILL THE MHA-DT-10",
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
    assert "MHA-DT-07 CLEARS THE UNRELIEVED MHA-DT-20 TOP THROUGH THAT TURN" in checks
    assert "RELIEF THROUGHOUT" not in checks
    # Owner ruling 2026-11-07 (engineerguy video 4): forward is clockwise in
    # the FRONT view, the platen feeds away from the crank, and the sine notch
    # stops on the MHA-DT-01 side.
    assert "THE MHA-DT-12 FINISHING CLOCKWISE TO TAKE UP PLAY" in checks
    assert "CRANK FORWARD IS CLOCKWISE IN THE SHEET 1 FRONT VIEW" in checks
    assert "THE PLATEN FEEDS AWAY FROM THE CRANK" in checks
    assert "LEVEL ON THE MHA-DT-01 SIDE (LEFT IN THE FRONT VIEW)" in checks
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
        "HOLD MHA-DT-11'S COLLAR HARD ON THE MHA-DT-05 BOSS, NO WASHER",
        f"SET MHA-DT-10 {sheet.inch_text(pinion.SEAT_FEELER_MM, sheet.FEELER_PLACES)} "
        "OFF THE BOSS BACK FACE WITH A FEELER",
        "MATCH-DRILL THE MHA-DT-10",
        f"END STANDS {drawing.inch_envelope((least, most), 3)} PROUD OF MHA-DT-10.",
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
        body.index("HOLD MHA-DT-11'S COLLAR HARD ON THE MHA-DT-05 BOSS"),
        body.index("OFF THE BOSS BACK FACE WITH A FEELER"),
        body.index("MATCH-DRILL THE MHA-DT-10"),
    ]
    assert positions == sorted(positions)


def test_a_cite_to_the_wrong_step_is_caught() -> None:
    """Positive control: RIG SET sets the rig along the bank, not its tip gap."""
    assert TIP_GAP_FEELER not in _step_body("rig-set")



def _defined_codes() -> list[str]:
    """The short codes MHA-DT-00 defines: each cone gear's configuration
    (the BOM's "T006-T120 BY 6") and the chain wheel the interface notes name."""
    cone = re.search(r"\bT(\d+)-T(\d+) BY (\d+)\b", drawing.BOM_DESCRIPTIONS["dt-cone-gear"])
    assert cone, drawing.BOM_DESCRIPTIONS["dt-cone-gear"]
    first, last, step = (int(value) for value in cone.groups())
    gears = {f"T{teeth:03d}" for teeth in range(first, last + 1, step)}
    named = set(re.findall(r"\bT\d+\b", drawing.INTERFACE_NOTES))
    assert named, "the interface notes name the T12 chain wheel"
    return [re.escape(code) for code in sorted(gears | named)]


def _direction_key() -> str:
    """The sheet's direction definitions: the direction notes and check 5's
    running sense."""
    checks = " ".join(drawing.CHECKS.split())
    forward = re.search(r"CRANK FORWARD IS CLOCKWISE IN THE SHEET 1 FRONT VIEW", checks)
    assert forward, "check 5 defines the running sense"
    return f"{drawing.DIRECTION_NOTES}\n{forward.group(0)}"


def test_every_step_and_check_is_one_short_action_with_its_codes_defined() -> None:
    """Drawing-guidelines rule 22, offline (rubric sample round 9: the review
    re-sampled chained steps every round): each printed step or check is at
    most six lines and one action, a check and its remedy are separate steps,
    every lettered or numbered cite names a printed head, and every short code
    and direction word is defined on the sheet.  No step is allowlisted."""
    violations = step_structure_violations(
        {"STEP": SEQUENCE_BLOCKS, "CHECK": (drawing.CHECKS,)},
        reference_kinds={"STEP": "STEP", "CHECK": "CHECK"},
        defined_codes=_defined_codes(),
        direction_key=_direction_key(),
    )
    assert violations == [], "\n".join(violations)


def test_the_fits_are_named_never_a_diametral_band() -> None:
    """Rule 4 (d870c66): a fit is named; any clearance or interference band
    prints only as REF."""
    printed = "\n".join((*SEQUENCE_BLOCKS, drawing.CHECKS))
    assert "DIAMETRAL" not in printed
    for band in re.findall(r"(?:CLEARANCE|INTERFERENCE)[^()]*\)?", " ".join(printed.split())):
        assert band.endswith("REF)"), band


