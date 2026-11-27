"""Drawing-only text of the complete-machine fitter package (MHA-HA-00).

The BOM descriptions, balloon targets, setting callouts and setting table the sheets print,
and the integration steps and checks the release's ASSEMBLY.md prints
(ha_assembly_package, #2889). Only draw_ha_harmonic_analyzer_assembly,
ha_assembly_package (and their tests) import this module; no assembly
builder may (``test_assembly_sheet_isolation`` pins it), so a wording edit
here does not rebuild the complete-machine assembly. No SolidWorks.
"""

from __future__ import annotations

import _config
import fr_frame_assembly_steps as fr_steps
import ha_build_sequence as build
import ha_harmonic_analyzer_assembly_steps as steps
import mg_magnifier_assembly_steps as mg_steps
import pd_paper_drive_assembly_steps as pd_steps
import pd_transgear_removable_spec as removable
import _sprocket_seat_geometry as seat_geometry
import ch_vn_spring_hook_spec
import fr_top_frame_spec
from ha_harmonic_analyzer_assembly_spec import (
    BAR_HEIGHT_DIMENSION,
    BOM_ORDER,
    MEASURING_STICK,
    STUD_DROP_DIMENSION,
)
from _printed_tolerance import angular_band_deg
from _recording_geometry import PEN_PAPER_CLEARANCE_MM
from _title_block_units import render_number

DRAWING_NUMBER = steps.DRAWING_NUMBER

BOM_DESCRIPTIONS: dict[str, str] = {
    "fr-frame": "FRAME: BASE, COLUMNS AND TOP FRAME",
    "dt-drive-train": "DRIVE TRAIN: CONES, CRANK AND CYLINDERS",
    "ch-channel": "CHANNEL BANK: RODS, ROCKERS, LEVERS, SPRINGS",
    "sm-summing": "SUMMING LEVER, KNIFE MOUNTS AND GOOSENECK",
    "mg-magnifier": "MAGNIFIER: WHEEL BAR, WHEEL AND BRACKET",
    "pn-pen": "PEN CARRIAGE AND HANGER",
    "pd-paper-drive": "PAPER DRIVE: PLATEN, SUPPORT BAR, TRANSGEAR",
    MEASURING_STICK: "MEASURING STICK WITH CLAMPED STOP",
}
if set(BOM_DESCRIPTIONS) != set(BOM_ORDER):
    raise AssertionError("every BOM row needs exactly one description")

# Each row's balloon lands on one leaf part of its subassembly that the
# exploded isometric shows: the top-level BOM resolves a nested part's
# balloon to its subassembly's row. Every stem lives in exactly one
# subassembly, so the balloon names one row. The channel row lands on the
# front channel's lever (ch-channel-lever-1, nearest the viewer): the
# fulcrum shaft that first held it is buried in the lever hubs (r2 leaf: no
# visible edge).
BALLOON_PARTS: dict[str, str] = {
    # The base, nearest the viewer: the top frame's leader crossed the frame.
    "fr-frame": "fr-harmonic-base",
    "dt-drive-train": "dt-crank-handle",
    "ch-channel": "ch-channel-lever",
    "sm-summing": "sm-summing-lever",
    "mg-magnifier": "mg-magnifying-wheel",
    "pn-pen": "pn-pen-hanger",
    "pd-paper-drive": "pd-platen",
    MEASURING_STICK: "ms-stick",
}
if set(BALLOON_PARTS) != set(BOM_ORDER) or len(set(BALLOON_PARTS.values())) != len(
    BALLOON_PARTS
):
    raise AssertionError("one distinct balloon part per BOM row")

# MHA-PD-00 stores its spare chain wheel flat and loose on the base deck,
# its own sheet 1 says so; at this level it lies beside item 7's group on
# sheet 3 and on the deck on sheet 2. Machinist review of 5bca52e13 (r1, r2)
# could not tell which row supplies it or where it stays: sheet 3 labels it
# and the paper-drive step names its supplier and its place. The spare is the
# one removable configuration neither wheel mounts, read the way the drawing
# finds it in the source (never an allocator-numbered instance).
PAPER_DRIVE = "pd-paper-drive"
SPARE_SPROCKET_STEM = "pd-transgear-removable"
(SPARE_SPROCKET_CONFIG,) = tuple(
    name
    for name, _teeth in removable.CONFIGS
    if name not in {removable.CRANK_CONFIG, removable.KNOB_CONFIG}
)
# Literal row name: a dynamic _config.parts read would widen this drawing's
# config dependency to every part row (test_dodo_recipe foreign-row guard).
SPARE_SPROCKET_NUMBER = str(_config.parts("pd-transgear-removable")["number"])
PAPER_DRIVE_ITEM = str(BOM_ORDER.index(PAPER_DRIVE) + 1)
# The label's leader tip: a point on the spare's upper plate face, part
# millimetres (plate local z 0..PLATE), on the local x axis between the
# drive-pin circle (pins on local y) and the tooth roots.
SPARE_SPROCKET_TIP_MM = (12.0, 0.0, seat_geometry.PLATE)
if not (
    seat_geometry.PIN_CIRCLE_RADIUS + seat_geometry.PIN_HOLE_DIA
    < SPARE_SPROCKET_TIP_MM[0]
    < removable.bottom_dia(removable.TEETH[SPARE_SPROCKET_CONFIG]) / 2.0 - 1.0
):
    raise AssertionError("the spare label's tip must land on the solid plate face")

# The parked nib's feeler, in the sheet's decimal inch (#290): the modelled
# 0.25 gap prints as the stock .010 leaf (0.254), three places as a feeler
# size reads; the next step closes the gap, so the 0.004 is immaterial.
NIB_CLEARANCE_PLACES = 3
NIB_CLEARANCE_TEXT = render_number(
    round(PEN_PAPER_CLEARANCE_MM / 25.4, NIB_CLEARANCE_PLACES), "in", NIB_CLEARANCE_PLACES
)
# Each setting's printed callout names what it sets and the step that sets
# it; the step text points back to the sheet-1 dimension, so the value lives
# only on the associative model dimension.
# Both callouts stay short: the bar-height text stands wholly left of the
# front view, the stud-drop text in the narrow strip between the right-hand
# column and the crank-side view, so it names only its step (the extension
# lines show it runs from the bar top to the stud head). The bar height runs
# from the raised deck top (ha_harmonic_analyzer_assembly_spec.DECK_TOP_Y),
# whose extension line ends at the left column short of that deck, so its
# callout and step name the surface (#2060), in short lines.
SETTING_CALLOUTS = {
    BAR_HEIGHT_DIMENSION: (
        "BAR TOP ABOVE\nRAISED DECK TOP\n"
        f"(STEP {steps.step_number('magnifier-bar-clamped')})"
    ),
    STUD_DROP_DIMENSION: f"STEP {steps.step_number('pen-wire-tied')}",
}

# --- Fitter package text ----------------------------------------------------
CHANNEL_ANCHORS = 20
# Rule 22: a step does one thing. A keyed step that needs several actions
# prints them as lettered sub-steps (5A, 5B, ...) under its own number, so the
# numbers other sheets cite (MHA-CH-00 cites the anchor step) never move. I
# and O never letter a sub-step.
SUB_STEP_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
# The title block's angular row is the level acceptance, read with a digital
# angle gauge (as MHA-SM-00 sets its plate).
LEVEL_TOLERANCE_DEG = angular_band_deg()
LEVEL_ACCEPTANCE = f"LEVEL WITHIN \u00b1{LEVEL_TOLERANCE_DEG:g}\u00b0"
_AMPLITUDE_BAR = str(_config.parts("ch-amplitude-bar")["number"])
_ANCHOR = str(_config.parts("ch-vn-spring-hook")["number"])
_SUMMING_PLATE = str(_config.parts("sm-summing-lever")["number"])

# Rule 22: the plate's level and the parked nib's feeler gap are measurable
# settings, so they print on sheet 1 though their steps and check print in
# ASSEMBLY.md (machinist review of main 67ba11bf1a, R5, and of the first
# proof of this table, which found the .010 in a prose note only). An
# angle-gauge reading and a feeler leaf are no model dimension, so each prints
# as a row of a native setting table (_general_table), from the constants its
# step prints, and the step (and check 4) cites the table.
SETTING_TABLE_TITLE = "SETTING TABLE"
SETTING_TABLE_REF = "SETTING TABLE, SHEET 1"
SETTING_TABLE_HEADER = ("STEP", "SETTING", "CONDITION", "ACCEPT", "CHECK WITH")


def _n(key: str) -> int:
    return steps.step_number(key)


def sub_step(key: str, index: int) -> str:
    """The printed head of ``key``'s ``index``-th sub-step (0-based): ``5A``."""
    if len(_STEP_TEXT[key]) == 1:
        raise ValueError(f"{key} prints as one step, not sub-steps")
    return f"{_n(key)}{SUB_STEP_LETTERS[index]}"


# MHA-SM-00's last step before its own AT FINAL ASSEMBLY step (that sheet
# imports this package's step numbers, so the number is stated here and
# test_ha_assembly_package holds it to the MHA-SM-00 sequence).
SM_LAST_BENCH_STEP = "8G"
# MHA-MS-00's in-use steps that set a bar with the stick (#2434, delegated
# ruling 2026-11-17, no precedent, option 2, owner review on #2144), stated
# as SM_LAST_BENCH_STEP is and held to
# the MHA-MS-00 sequence by test_ha_assembly_package.
MS_SETTING_STEPS = "11-13A"
# Steps 1, 2 and 4 print the master build order (ha_build_sequence, #2391):
# the sub-assembly sheets' own steps in runs, the frame apart from MHA-FR-00's
# drilling lift until the mill work on MHA-FR-01 and MHA-FR-02 is done.
# The frame parts the steps name, by their registry numbers (rule 4: each
# mate named by number; ENFORCE review on #2822 and two earlier PRs).
_COLUMN = _config.parts("fr-tube-frame")["number"]
_TOP_FRAME = _config.parts("fr-top-frame")["number"]
_FRAME_REERECTED = (
    f"FIT THE {_COLUMN} COLUMNS AND MHA-FR-02 BACK ON MHA-FR-01 PER "
    f"{build.FRAME_ERECTED.text}."
)
_BUILT_APART = (
    f"DRIVE TRAIN: BUILD {build.DT_BENCH.text} AT THE BENCH.",
    f"BUILD {build.CH_BENCH.text} AT THE BENCH.",
    f"BUILD {build.DT_BASE_ON_MILL.text}, MHA-FR-01 ON THE MILL.",
    f"BUILD {build.CH_BASE_ON_MILL.text}, MHA-FR-01 STILL ON THE MILL.",
    "SET MHA-FR-01 ON A FLAT BENCH.",
    f"BUILD {build.CH_TOP_FRAME_ON_MILL.text}, MHA-FR-02 ON THE MILL.",
    _FRAME_REERECTED,
    f"CHECK THE FRAME PER {build.FRAME_CHECKED.text}.",
)
_REERECTED_HEAD = (
    f"{_n('drive-train-built')}{SUB_STEP_LETTERS[_BUILT_APART.index(_FRAME_REERECTED)]}"
)
_STEP_TEXT: dict[str, tuple[str, ...]] = {
    "frame-built": (
        f"FRAME: FIT {build.FRAME_FITTED.text} ON A FLAT BENCH.",
        f"LEAVE THE {_COLUMN} COLUMNS AND MHA-FR-02 OFF MHA-FR-01 ONCE "
        f"{fr_steps.step_ref(build.FRAME_LIFTED_KEY)} LIFTS THEM, UNTIL "
        f"{_REERECTED_HEAD}.",
        f"FIT {build.LOOSE_CASTINGS.text} NOW, ON THE LOOSE MHA-FR-01 AND "
        "MHA-FR-02, AHEAD OF ITS "
        f"{build.FRAME_ERECTED.text.removeprefix(fr_steps.DRAWING_NUMBER + ' ')}.",
    ),
    "drive-train-built": _BUILT_APART,
    "summing-hung": (
        f"SUMMING LEVER: BUILD MHA-SM-00 STEPS 1-{SM_LAST_BENCH_STEP} (ASSEMBLY.MD) UNDER THE "
        "TOP-FRAME CROSSBAR, THE MHA-SM-01 POST OUT OF ITS HUB.",
    ),
    "channel-built": (
        f"CHANNEL BANK: BUILD {build.CH_ON_FRAME.text} ON THE FRAME, EACH "
        "MHA-CH-VN-50 SPRING HANGING FROM ITS LEVER WITH ITS BOTTOM LOOP FREE.",
    ),
    "channel-anchors-set": (
        f"DISCARD THE HEX NUT SUPPLIED WITH EACH OF THE {CHANNEL_ANCHORS} {_ANCHOR} "
        "ANCHORS.",
        f"THREAD EACH {_ANCHOR} DOWN INTO ITS {_SUMMING_PLATE} PLATE TAP UNTIL ITS "
        "NECK SEATS ON THE PLATE TOP.",
        f"TURN EACH {_ANCHOR} BACK, NO MORE THAN "
        f"{ch_vn_spring_hook_spec.ADJUSTMENT_TURNS} TURN, TO BRING ITS EYE OPENING "
        "IN LINE WITH ITS SPRING.",
        "HOOK EACH SPRING'S BOTTOM LOOP INTO ITS ANCHOR EYE.",
    ),
    "summing-levelled": (
        f"DROP THE MHA-SM-01 POST INTO THE {_TOP_FRAME} TOP FRAME'S GOOSENECK HUB.",
        "HOOK THE MHA-SM-VN-51 LOWER LOOP INTO THE MHA-SM-VN-50 EYE.",
        f"SET EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR TO ZERO WITH MHA-MS-00, PER "
        f"ITS STEPS {MS_SETTING_STEPS} (ASSEMBLY.MD).",
        "SLIDE THE POST IN ITS HUB UNTIL A DIGITAL ANGLE GAUGE ACROSS THE "
        f"MHA-SM-03 PLATE TOP READS {LEVEL_ACCEPTANCE} ({SETTING_TABLE_REF}).",
        # One printed line (the columns are full): the bare leg's set-screw
        # limit (owner rulings 2026-11-08 (Pedro), #2315).
        "TIGHTEN MHA-FR-VN-52 SNUG ON THE POST, "
        f"{fr_top_frame_spec.SET_SCREW_TORQUE_MAX_IN_LB:g} IN-LB MAX.",
        "CHECK: UNDER FIRM HAND PRESSURE THE POST DOES NOT TURN OR SLIDE IN "
        "ITS HUB.",
        "IF THE POST MOVES, SLACKEN THE SET SCREW AND REPEAT "
        f"{_n('summing-levelled')}D-{_n('summing-levelled')}E.",
    ),
    "paper-drive-built": (
        f"PAPER DRIVE: BUILD MHA-PD-00 ON THE FRONT {_COLUMN} COLUMNS, ITS STEPS "
        f"1-{len(pd_steps.SEQUENCE)} IN ORDER.",
        f"LAY THE LOOSE {SPARE_SPROCKET_NUMBER} {SPARE_SPROCKET_CONFIG} SPARE "
        "SPROCKET SUPPLIED WITH MHA-PD-00 (LABELLED ON SHEET 3) FLAT ON THE "
        "BASE DECK WHERE SHEET 2 SHOWS IT.",
    ),
    # The clamp arcs close round a plumb round column, so MHA-MG-08 has two
    # freedoms there: its height along the column (the sheet 1 dimension)
    # and its heading about it. Level is not one of them. The pen hangs from
    # the bar (step "pen-hung"), so the heading swings the MHA-MG-05 wheel
    # and the pen together and moves neither the pen wire on the rim nor the
    # pen rod in its guides. It moves the MHA-MG-10 drum off the lever wire's
    # plane, which MHA-MG-01 fixes from MHA-SM-03 (sh_vn_music_wire_lever_geom
    # option A1: the hook and the drum share one depth), and the pen carriage
    # toward or away from the paper (pn_pen_carriage_geom: the rigid carriage
    # rides its stand-off off the paper, and no other setting moves it). Both
    # are laid out on the bar's front face parallel to the paper plane: the
    # pen-rod line is set off the paper, and the wheel plane and the drum lane
    # derive from it. So the heading sub-step sets that datum against the
    # MHA-PD-02 platen face, which the paper-drive step has already placed.
    # Sight alone cannot hold the carriage's stand-off on a bar this long, and
    # the carriage's printed worst case leaves the heading nothing, so the
    # heading is the fit-up adjustment that covers that stack (rule 19). Its
    # acceptance is where the stack closes: once the nib is on the paper
    # ("nib-on-paper"), only the nib touches it, else the bar turns away from
    # the paper. Check 8 accepts the drum.
    "magnifier-bar-clamped": (
        "MAGNIFIER BAR: CLOSE THE MHA-SH-01/MHA-SH-02 CLAMP ARCS SUPPLIED WITH "
        f"MHA-MG-00 ROUND THE LEFT FRONT {_COLUMN} COLUMN, THE MHA-MG-08 BAR RUNNING TO "
        "THE RIGHT (FRONT VIEW), BOTH MHA-SH-VN-53 CLAMP SCREWS LOOSE.",
        "SET THE MHA-MG-08 BAR TOP TO ITS HEIGHT ABOVE THE RAISED DECK TOP "
        "(SHEET 1), READ WITH A RULE FROM THE DECK TOP.",
        "TURN THE BAR ON THE COLUMN UNTIL, SEEN FROM ABOVE, ITS FRONT FACE RUNS "
        "PARALLEL TO THE MHA-PD-02 PLATEN FACE. THIS IS A FIRST SETTING; "
        f"{_n('nib-on-paper')}E IS ITS ACCEPTANCE.",
        "TIGHTEN BOTH CLAMP SCREWS EVENLY.",
        "CHECK: UNDER FIRM HAND PRESSURE THE BAR DOES NOT SLIP OR TURN ON THE "
        "COLUMN.",
        "IF THE BAR MOVES, SLACKEN BOTH SCREWS AND REPEAT "
        f"{_n('magnifier-bar-clamped')}B-{_n('magnifier-bar-clamped')}D.",
    ),
    "magnifier-bracket-screwed": (
        "MAGNIFIER BRACKET: SEAT THE MHA-MG-01 BRACKET FLANGE ON ITS SEATS ON "
        "MHA-SM-03.",
        "DRIVE BOTH MHA-MG-VN-53 #2-56 SCREWS UNTIL THE HEADS TOUCH THE FLANGE.",
        # Owner ruling 2026-11-08 (Pedro), #2144 item 11.1, via FoMg: the
        # joint's friction cannot hold JOINT_MZ, so the flange is settled
        # nose down onto the shanks before tightening
        # (mg_magnifying_bracket_arm_check). Setting and tightening are
        # separate sub-steps, and a hold check with its remedy follows, as
        # every other retention on these sheets does (rule 22; review of
        # the pd DETAIL rename). Each takes one printed line.
        "ROTATE MHA-MG-01 NOSE DOWN UNTIL BOTH SCREWS BEAR.",
        "TIGHTEN BOTH SCREWS.",
        "CHECK: FIRM HAND PRESSURE DOES NOT MOVE MHA-MG-01.",
        "IF IT MOVES, SLACKEN BOTH SCREWS AND REPEAT "
        f"{_n('magnifier-bracket-screwed')}C-{_n('magnifier-bracket-screwed')}D.",
    ),
    # MHA-MG-00's fit-up steps print in the release's ASSEMBLY.md, not on its
    # sheets (#2889): cite them by number there.
    "lever-wire-fitted": (
        f"LEVER WIRE: FIT IT PER {mg_steps.DRAWING_NUMBER} STEPS "
        f"{mg_steps.step_number(mg_steps.WIRE_HOOKED_KEY)}-"
        f"{mg_steps.step_number(mg_steps.WIRE_TIED_KEY)} (ASSEMBLY.MD).",
    ),
    "pen-hung": (
        "PEN: HANG MHA-PN-00 FROM THE MHA-MG-08 BAR.",
        "LOCK ITS MHA-PN-VN-50 HANGER SCREW WITH THE MHA-PN-VN-54 NUT AND "
        "MHA-PN-VN-55 JAM NUT PER THE MHA-PN-00 HANGER SCREW LOCK STEP (ASSEMBLY.MD).",
    ),
    # The wrap follows mg_wheel_group (PEN_WIRE_WRAP_DEG: from the right-hand
    # tangent counter-clockwise, up over the top, to the rim's radial wire tie
    # hole drawn on the MHA-MG-05 sheet, under one turn).
    "pen-wire-tied": (
        f"PEN WIRE, WITH THE PLATE TOP LEVEL ({_n('summing-levelled')}D): LEAD "
        "THE UPPER END OF MHA-SH-VN-56 (SUPPLIED WITH MHA-PN-00) INTO THE "
        "MHA-MG-05 RIM GROOVE AT ITS RIGHT-HAND TANGENT (FRONT VIEW).",
        "WRAP THE WIRE COUNTERCLOCKWISE (FRONT VIEW) UP OVER THE TOP, LESS THAN "
        "ONE FULL TURN, TO THE RADIAL WIRE TIE HOLE IN THE MHA-MG-05 RIM.",
        "PASS THE WIRE THROUGH THE HOLE AND DRAW IT UNTIL THE MHA-PN-07 STUD "
        "HEAD TOP HANGS THE SHEET 1 DROP BELOW THE MHA-MG-08 BAR TOP.",
        "KNOT THE WIRE INSIDE THE RIM AT THAT DROP ROUND A SHORT OFFCUT OF "
        "THE WIRE LAID ACROSS THE HOLE.",
        "CHECK: THE KNOT DOES NOT SLIP UNDER A LIGHT PULL BY HAND.",
        "TRIM THE TAIL.",
    ),
    # The parked, as-modelled nib: the views show it here, a feeler's gap
    # off the paper (PEN_PAPER_CLEARANCE_MM). Nothing on the carriage brings
    # it nearer -- it hangs plumb and CG-balanced on the wire, the rod
    # guided -- so "nib-on-paper" closes the gap by sliding the marker on in
    # the V (code review C08).
    "nib-set": (
        "NIB PARKED, WITH PAPER CLIPPED ON THE PLATEN: SLACKEN THE MHA-PN-VN-51 "
        "THUMB SCREW.",
        f"SLIDE THE MHA-PN-VN-56 MARKER UNTIL A {NIB_CLEARANCE_TEXT} FEELER JUST "
        f"DRAGS BETWEEN NIB AND PAPER ({SETTING_TABLE_REF}).",
        "TIGHTEN THE THUMB SCREW FINGER-TIGHT.",
        "CHECK: PUSHED LIGHTLY ALONG ITS AXIS, THE MARKER DOES NOT SLIDE.",
    ),
    "nib-on-paper": (
        "NIB ON PAPER, BEFORE RUNNING: SLACKEN THE MHA-PN-VN-51 THUMB SCREW.",
        "PUSH THE MHA-PN-VN-56 MARKER ALONG ITS AXIS UNTIL THE NIB JUST TOUCHES "
        "THE PAPER.",
        "TIGHTEN THE THUMB SCREW FINGER-TIGHT.",
        "CHECK: PUSHED LIGHTLY ALONG ITS AXIS, THE MARKER DOES NOT SLIDE.",
        "CHECK: ONLY THE NIB TOUCHES THE PAPER.",
        # Rule 22: one action a step (machinist review of main 67ba11bf1a,
        # R5: the remedy slackened, turned and repeated in one step). The
        # branch is its own step, so the remedy steps after it run only when
        # the check fails (codjiflo on #3034: split, they read unconditional).
        "IF ONLY THE NIB TOUCHES, GO ON TO STEP "
        f"{_n(steps.SEQUENCE[steps.SEQUENCE.index('nib-on-paper') + 1])}.",
        "OTHERWISE SLACKEN BOTH MHA-SH-VN-53 CLAMP SCREWS.",
        "TURN THE MHA-MG-08 BAR AWAY FROM THE PAPER UNTIL NO OTHER PART OF "
        "MHA-PN-00 TOUCHES.",
        f"REPEAT {_n('magnifier-bar-clamped')}B, "
        f"{_n('magnifier-bar-clamped')}D-{_n('magnifier-bar-clamped')}E AND "
        f"{_n('nib-set')}A-{_n('nib-on-paper')}E.",
    ),
    "stick-parked": (
        "MEASURING STICK: PARK MHA-MS-00 ON THE MHA-FR-01 AS-CAST TOP BETWEEN "
        f"THE RIGHT EDGE OF THE RAISED DECK AND THE RIGHT-HAND {_COLUMN} COLUMNS (FRONT "
        "VIEW), AS SHEET 2 SHOWS IT: STICK FRONT TO REAR AND CENTRED, "
        "THUMBSCREW ON TOP.",
    ),
}
if set(_STEP_TEXT) != set(steps.SEQUENCE):
    raise AssertionError("every integration step needs exactly one text")
if max(map(len, _STEP_TEXT.values())) > len(SUB_STEP_LETTERS):
    raise AssertionError("a step outgrows its sub-step letters")


def _table_sub_step(key: str) -> str:
    """The one sub-step of ``key`` that cites the setting table."""
    (index,) = (
        index for index, text in enumerate(_STEP_TEXT[key]) if SETTING_TABLE_REF in text
    )
    return sub_step(key, index)


# The setting table's rows: the plate-level step and the parked nib's feeler
# step, each from the constants its step prints.
SETTING_TABLE_ROWS: tuple[tuple[str, ...], ...] = (
    (
        _table_sub_step("summing-levelled"),
        f"{_SUMMING_PLATE} PLATE TOP",
        f"EVERY {_AMPLITUDE_BAR} BAR AT 0",
        f"LEVEL \u00b1{LEVEL_TOLERANCE_DEG:g}\u00b0",
        "DIGITAL ANGLE GAUGE",
    ),
    (
        _table_sub_step("nib-set"),
        "NIB TO PAPER",
        "PARKED, PAPER ON PLATEN",
        NIB_CLEARANCE_TEXT,
        "FEELER JUST DRAGS",
    ),
)


def _printed(key: str) -> tuple[str, ...]:
    texts = _STEP_TEXT[key]
    if len(texts) == 1:
        return (f"{_n(key)}. {texts[0]}",)
    return tuple(f"{sub_step(key, index)}. {text}" for index, text in enumerate(texts))


# Every printed step, in order, each led by its head (``7.`` or ``7B.``).
ASSEMBLY_STEPS: tuple[str, ...] = tuple(
    line for key in steps.SEQUENCE for line in _printed(key)
)


def step_lines(key: str) -> tuple[str, ...]:
    """The printed step lines of ``key``: one, or its lettered sub-steps."""
    return _printed(key)


# The section ASSEMBLY.md prints (ha_assembly_package, #2889).
STEP_SECTIONS = (("INTEGRATION SEQUENCE", ASSEMBLY_STEPS),)


# The checks before running: one acceptance each.
ASSEMBLY_CHECKS: tuple[str, ...] = (
    "1. THE MHA-MG-08 BAR TOP READS ITS SHEET 1 HEIGHT.",
    "2. THE MHA-PN-07 STUD DROP READS AS SHEET 1.",
    "3. THE NIB TOUCHES THE PAPER.",
    f"4. WITH EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR AT ZERO, THE MHA-SM-03 PLATE "
    f"TOP READS {LEVEL_ACCEPTANCE} ({SETTING_TABLE_REF}).",
    f"5. WITH EVERY {_AMPLITUDE_BAR} AMPLITUDE BAR AT ZERO, TWO CRANK TURNS DRAW "
    "A STRAIGHT LINE ALONG THE PAPER.",
    "6. THROUGH TWO CRANK TURNS NOTHING BINDS OR RUBS.",
    "7. THROUGH TWO CRANK TURNS THE CHAIN STAYS ON BOTH WHEELS.",
    "8. THROUGH TWO CRANK TURNS BOTH WIRES STAY IN THEIR GROOVES.",
)

EXPLODED_CAPTION = "EXPLODED VIEW - INTEGRATION STEPS IN ASSEMBLY.MD"
ORIENTATION_NOTE = "FRONT VIEW: THE PAPER SIDE. THE CRANK IS AT THE RIGHT."
# The model holds the pen parked (step "nib-set"); running needs it on the
# paper (step "nib-on-paper"). The parked gap prints in the setting table.
NIB_PARKED_NOTE = (
    f"VIEWS SHOW THE NIB PARKED OFF THE PAPER (STEP {_n('nib-set')}); "
    f"STEP {_n('nib-on-paper')} SETS IT ON."
)
# Sheet 3's label on the spare, beside item 7's group (its leader ends on the
# spare's plate face).
SPARE_SPROCKET_LABEL = "\n".join(
    (
        f"{SPARE_SPROCKET_NUMBER} {SPARE_SPROCKET_CONFIG}",
        "SPARE SPROCKET",
        f"(ITEM {PAPER_DRIVE_ITEM}, STEP {_n('paper-drive-built')})",
    )
)
