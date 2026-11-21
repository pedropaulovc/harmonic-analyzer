"""MHA-FR-00's printed settings, setting table, bench acceptances and fit-up steps.

The values are the parts' and the frame's (fr_frame_attachment_spec,
fr_frame_setting_bands, the castings' far-wall stacks, fr_tube_frame_spec);
this drawing-only module composes the text from them: the settings and the
setting table the fitter sheets print (draw_fr_frame_assembly places them and
owns none of it, test_drawing_specification_purity) and the fit-up steps the
release's ASSEMBLY.md prints (ha_assembly_package, #2889).
"""

from __future__ import annotations

from fractions import Fraction
import math

import _config
from _assembly_contract import assembly_contract
from _title_block_units import render_number
import fr_frame_assembly_steps as steps
from fr_frame_attachment_spec import (
    TOP_AXIS_HEIGHT_PLACES,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from fr_frame_cross_screw import FAR_WALL_ENGAGEMENT_FLOOR_MM, NEAR_WALL_CLEARANCE_DIAMETER
from fr_frame_setting_bands import TOP_AXIS_HEIGHT_BAND_MM
from fr_harmonic_base_fasteners import base_cross_screw_far_wall_start_max_mm
from fr_top_frame_spec import TOP_CROSS_SCREW_FAR_WALL_START_MAX
from fr_tube_frame_spec import SUPPLY_LENGTH_MIN_IN as COLUMN_SUPPLY_LENGTH_MIN_IN
from fr_vn_frame_cross_screw_spec import SHANK_LEN as CROSS_SCREW_SHANK_LEN
import ha_harmonic_analyzer_assembly_steps as ha_steps

# The fitter sheets print decimal inch (fr-frame.yaml ``drawing_unit``).
UNIT = assembly_contract("fr-frame").drawing_unit
# The top cross-bore axis height (fr_frame_attachment_spec TOP_AXIS_*) prints
# three places, 40.075, with its rule-read band (+/-.030). TOP_AXIS_SET_KEY
# sets all four corners' axes to this one absolute height from the base
# underside before the upper tube holes are transferred, so the frame's own
# .72 tap station off its rail top cannot carry it. MHA-FR-02's faced
# underside sits on the inch-grid plane (top_frame_plane, 39.358) the summing
# knife mounts clamp to, which puts its rail top (40.795) and this axis on the
# .001 grid. The setting step names the height and its band itself: the
# sheet-1 dimension carries its value and band and nothing else (rule 7).
TOP_AXIS_HEIGHT_TEXT = (
    f"{render_number(TOP_SCREW_Y / 25.4, UNIT, TOP_AXIS_HEIGHT_PLACES)} "
    f"±{render_number(TOP_AXIS_HEIGHT_BAND_MM / 25.4, UNIT, TOP_AXIS_HEIGHT_PLACES)}"
)
# The installed cross screw's far-wall engagement (rule 18), made checkable at
# the bench before the screw goes in (delegated ruling, machinist review
# 20261107T081227004Z): each MHA-FR-VN-53's full thread must reach from under
# its head past the print-worst start of full far-wall thread in either
# casting by the 1.5D floor. The base governs (its front pad chain); the
# limit rounds UP to the printed .001, so a screw that passes it engages at
# least 1.5D however its tip is chamfered.
CROSS_SCREW_FAR_WALL_START_MAX_MM = max(
    TOP_CROSS_SCREW_FAR_WALL_START_MAX,
    *(base_cross_screw_far_wall_start_max_mm(front=front) for front in (True, False)),
)
CROSS_SCREW_FULL_THREAD_MIN_IN = (
    math.ceil(
        (CROSS_SCREW_FAR_WALL_START_MAX_MM + FAR_WALL_ENGAGEMENT_FLOOR_MM) / 25.4 * 1000.0
        - 1e-9
    )
    / 1000.0
)
CROSS_SCREW_FULL_THREAD_MIN_TEXT = render_number(CROSS_SCREW_FULL_THREAD_MIN_IN, UNIT, 3)
CROSS_SCREW_FULL_THREAD_LIMIT_TEXT = f"{CROSS_SCREW_FULL_THREAD_MIN_TEXT} MIN"
if CROSS_SCREW_FULL_THREAD_MIN_IN * 25.4 >= CROSS_SCREW_SHANK_LEN:
    raise AssertionError("the cross-screw thread check exceeds the stock screw's length")
# The rough cut is the column's own supply length (fr_tube_frame_spec,
# printed on its sheet as SUPPLY n.nn MIN): round 1 review, "LONG" gave no
# length to cut to.
COLUMN_ROUGH_CUT_LENGTH_TEXT = f"{COLUMN_SUPPLY_LENGTH_MIN_IN:.2f} MIN"

# The tube match holes' finished drill, as the hole steps print it (.197).
CROSS_HOLE_TEXT = render_number(TUBE_CROSS_HOLE_DIAMETER / 25.4, UNIT, 3)
# #2388: each tube's cross hole is spotted through its casting's Ø.206 near-wall
# clearance hole with the largest stock transfer punch that enters it, then
# drilled straight through both tube walls on the mill: no drill runs near the
# tapped far wall, which an unguided pilot (.050 of slop in the clearance hole)
# could cut. The punch's radial play is the spot's error.
TRANSFER_PUNCH = Fraction(13, 64)
TRANSFER_PUNCH_TEXT = f"{TRANSFER_PUNCH.numerator}/{TRANSFER_PUNCH.denominator}"
if not 0.0 < NEAR_WALL_CLEARANCE_DIAMETER / 25.4 - TRANSFER_PUNCH <= 0.005:
    raise AssertionError(
        "the transfer punch must enter the clearance hole with little play"
    )
# The BOM's item numbers, as the native table numbers the families (component
# order in the source assembly); _validate_frame_bom proves the inserted table
# prints exactly these. Steps name parts by item (drawing-guidelines.md rule
# 22); parts outside this BOM keep their drawing numbers.
BASE = "fr-harmonic-base"
COLUMN = "fr-tube-frame"
SUPPORT = "fr-rocker-arm-support"
SUPPORT_SCREW = "fr-vn-lag-screw"
TOP_FRAME = "fr-top-frame"
CAP = "fr-vn-tube-frame-cap"
NAMEPLATE = "fr-nameplate"
NAMEPLATE_SCREW = "sh-vn-brass-fillister-screw"
CROSS_SCREW = "fr-vn-frame-cross-screw"
SET_SCREW = "fr-vn-gooseneck-set-screw"
ITEM_NUMBERS = {
    BASE: 1,
    COLUMN: 2,
    SUPPORT: 3,
    SUPPORT_SCREW: 4,
    TOP_FRAME: 5,
    CAP: 6,
    NAMEPLATE: 7,
    NAMEPLATE_SCREW: 8,
    CROSS_SCREW: 9,
    SET_SCREW: 10,
}
# The summing gooseneck (cad/config/parts/sm-gooseneck.yaml): its post drops
# into the top frame's post bore, where item 10 grips it at MHA-HA-00.
GOOSENECK_POST_NUMBER = "MHA-SM-01"
# The MHA-HA-00 step that slides the post to level and tightens item 10 on it.
HA_SET_SCREW_TIGHTENED_REF = ha_steps.step_ref("summing-levelled")


def _item(stem: str) -> str:
    return f"ITEM {ITEM_NUMBERS[stem]}"


def _step(key: str) -> str:
    return f"STEP {steps.step_number(key)}"


_BASE, _COLUMN, _SUPPORT = _item(BASE), _item(COLUMN), _item(SUPPORT)
# A literal row read, so the drawing's config dependency keeps this row.
_BASE_NUMBER = _config.parts("fr-harmonic-base")["number"]
_SUPPORT_SCREW, _TOP, _CAP = _item(SUPPORT_SCREW), _item(TOP_FRAME), _item(CAP)
_PLATE, _PLATE_SCREW = _item(NAMEPLATE), _item(NAMEPLATE_SCREW)
_CROSS, _SET = _item(CROSS_SCREW), _item(SET_SCREW)
_POST_BORE = f"THE {GOOSENECK_POST_NUMBER} POST BORE OF {_TOP}"
_LIFT_OFF = f"TAKE {_TOP} AND THE COLUMNS OFF {_BASE}."
# --- sheet 1: the setting table ----------------------------------------------
# R5 machinist review (rule 22): the columns' rough-cut length and the cross
# screws' full-thread acceptance printed only in their ASSEMBLY.md steps.
# Neither is one model dimension (a stock minimum the modeled cut length does
# not carry; a far-wall stack bound checked on a purchased screw), so each is
# a row of a native general table (draw_dt_drive_train_assembly's SETTING
# TABLE columns, less MEASURE FIRST: nothing here is measured first) and its
# step cites the row. Sheet 1 also carries the native setting dimensions.
SETTING_TABLE_SHEET_NUMBER = 1
SETTING_TABLE_TITLE = "SETTING TABLE"
SETTING_TABLE_HEADER = ("ROW", "STEP", "SETTING", "SET TO / ACCEPT", "CHECK WITH")
_SETTINGS = (
    # (step key, setting, accept, instrument)
    (
        steps.COLUMNS_ROUGH_CUT_KEY,
        f"{_COLUMN} ROUGH-CUT LENGTH",
        COLUMN_ROUGH_CUT_LENGTH_TEXT,
        "STEEL RULE",
    ),
    (
        "cross-screws-measured",
        f"{_CROSS} FULL THREAD UNDER HEAD",
        CROSS_SCREW_FULL_THREAD_LIMIT_TEXT,
        "CALIPER",
    ),
)
SETTING_TABLE_ROWS = tuple(
    (str(row), str(steps.step_number(key)), setting, accept, instrument)
    for row, (key, setting, accept, instrument) in enumerate(_SETTINGS, start=1)
)
_SETTING_ROW = {key: row for row, (key, *_rest) in enumerate(_SETTINGS, start=1)}


def setting_row(key: str) -> str:
    """How a step cites its setting table row."""
    return f"SETTING TABLE ROW {_SETTING_ROW[key]} (SHEET {SETTING_TABLE_SHEET_NUMBER})"


# One entry per step key (fr_frame_assembly_steps.SEQUENCE). Only what exists
# at assembly: matched socket fits, tube cross holes spotted through each
# casting's clearance hole and drilled on the mill (only the casting wall
# opposite is tapped), the columns match-cut to the cap stack, and checks
# against the actual purchased parts. Each step does one thing; a check and
# its remedy are their own steps (rule 22). Sides and ends name physical
# features or a lettered view, never a compass or the machine's front and
# back (rule 26).
STEP_TEXT = {
    # Owner-accepted fit-up, declared as fr-frame RV-01 (#1468). It comes
    # first so the bare base goes on the mill for the drilling and tapping
    # (#2390), not under the erected frame.
    steps.NAMEPLATE_SET_KEY: (
        f"SET {_PLATE} ETCHED FACE UP ON THE TOP FACE OF {_BASE}, CENTRED ACROSS "
        "ITS WIDTH, PARALLEL TO THE NEAREST END OF THAT FACE AND INSET FROM IT BY "
        "THE SECTION B-B DIMENSION (SHEET 1)."
    ),
    "nameplate-clamped": f"CLAMP {_PLATE} THERE.",
    steps.NAMEPLATE_SPOTTED_KEY: f"SPOT {_BASE} THROUGH THE FOUR HOLES OF {_PLATE}.",
    "nameplate-lifted": f"UNCLAMP AND LIFT OFF {_PLATE}.",
    steps.NAMEPLATE_SEATS_TAPPED_KEY: (
        f"WITH {_BASE} ON THE MILL, DRILL AND TAP EACH SPOT PER THE TRANSFER "
        f"CALLOUT ON DRAWING {_BASE_NUMBER}."
    ),
    steps.NAMEPLATE_SCREWED_KEY: (
        f"SCREW {_PLATE} DOWN WITH THE FOUR {_PLATE_SCREW} SCREWS UNTIL EVERY HEAD "
        "SEATS."
    ),
    "nameplate-flat-checked": f"CHECK {_PLATE} LIES FLAT ON {_BASE}.",
    "nameplate-heads-checked": f"CHECK EVERY {_PLATE_SCREW} HEAD BEARS ON {_PLATE}.",
    # The rough cut is the column's own supply length (fr_tube_frame_spec,
    # printed on its sheet as SUPPLY n.nn MIN, and in the setting table):
    # round 1 review, "LONG" gave no length to cut to. The final length is
    # COLUMNS_CUT_KEY's alone (rule 22 proof review: a step that cuts "to the
    # length" and defers "to length" reads as two cuts).
    steps.COLUMNS_ROUGH_CUT_KEY: (
        f"ROUGH-CUT FOUR {_COLUMN} COLUMNS TO "
        f"{setting_row(steps.COLUMNS_ROUGH_CUT_KEY)}."
    ),
    "base-sockets-fitted": (
        f"WITH {_BASE} TOP FACE UP, FIT EACH OF ITS SOCKETS TO ITS OWN {_COLUMN}: "
        "IT SLIDES IN BY HAND TO FULL DEPTH, NO ROCK."
    ),
    "base-match-marked": (
        f"MATCH-MARK EACH {_COLUMN} AND ITS {_BASE} SOCKET ACROSS THE JOINT, SO IT "
        "GOES BACK IN THE SAME CORNER, TURNED THE SAME WAY."
    ),
    steps.LOWER_HOLES_MARKED_KEY: (
        f"WITH THE COLUMNS SEATED, SPOT EACH COLUMN THROUGH THE CLEARANCE HOLE "
        f"OF ITS {_BASE} SOCKET WITH A {TRANSFER_PUNCH_TEXT} TRANSFER PUNCH."
    ),
    "lower-columns-lifted": f"LIFT THE COLUMNS OUT OF {_BASE}.",
    # The Ø.197 hole floats the .190 screw only .0035 a side, less than the
    # punch's play, the drill's start and the casting's screw line off its
    # socket axis can add up to (codjiflo review of PR #2552): the seated
    # check and a file close that stack at assembly (rule 19), as the screw
    # is what the hole must pass. The screw's thread marks the edge it bears
    # on, which is the side to file. .197 stays because opening the tube hole
    # (fr_frame_attachment_spec) re-keys both castings and every assembly
    # above them; #2561 carries it to the next casting change.
    # The title block's REMOVE BURRS covers the drilled holes (rule 22: one
    # action a step).
    steps.LOWER_HOLES_DRILLED_KEY: (
        f"ON THE MILL, DRILL EACH COLUMN Ø{CROSS_HOLE_TEXT} AT ITS SPOT THROUGH BOTH "
        "WALLS, SQUARE TO AND THROUGH THE TUBE AXIS."
    ),
    steps.COLUMNS_RESEATED_KEY: f"RESEAT EACH {_COLUMN} IN {_BASE} ON ITS MATCH MARK.",
    steps.LOWER_HOLES_CHECKED_KEY: (
        f"CHECK ONE {_CROSS} PASSES BOTH TUBE HOLES OF EACH SEATED COLUMN AND "
        "STARTS BY HAND IN THE TAPPED SOCKET WALL."
    ),
    # No casting named: upper-holes-reworked repeats this step with the
    # columns in the top frame (codjiflo review of PR #3024).
    "lower-holes-reworked": (
        f"IF IT DOES NOT START, TAKE THAT {_COLUMN} OUT AND ROUND-FILE THE TUBE "
        f"HOLE THE {_CROSS} THREAD MARKED, UNTIL "
        f"{_step(steps.LOWER_HOLES_CHECKED_KEY)} PASSES."
    ),
    "lower-tap-chased": (
        "IF NEITHER TUBE HOLE IS MARKED, CHASE THE TAPPED SOCKET WALL WITH A "
        f"#10-32 BOTTOMING TAP UNTIL {_step(steps.LOWER_HOLES_CHECKED_KEY)} PASSES."
    ),
    "top-frame-lowered": (
        f"LOWER {_TOP} OVER THE COLUMNS, TURNED AS SECTION B-B (SHEET 1) SHOWS."
    ),
    "top-sockets-fitted": (
        f"FIT EACH {_TOP} SOCKET TO ITS OWN {_COLUMN}: IT SLIDES ON BY HAND, NO ROCK."
    ),
    "top-match-marked": f"MATCH-MARK EACH {_COLUMN} AND ITS {_TOP} SOCKET THE SAME WAY.",
    # #2389: no mate needs this height closer than a rule reads
    # (fr_frame_setting_bands), so the base stands on the bench it is built
    # on and a steel rule stands on that bench, read at the hole centre.
    steps.TOP_AXIS_SET_KEY: (
        f"SET EACH {_TOP} SOCKET CROSS-HOLE AXIS TO THE {TOP_AXIS_HEIGHT_TEXT} HEIGHT "
        f"ABOVE THE UNDERSIDE OF {_BASE} (SHEET 1), {_BASE} ON A FLAT BENCH: READ "
        "WITH A STEEL RULE STOOD ON THE BENCH, AT THE CENTRE OF THE HOLE."
    ),
    steps.TOP_FRAME_CLAMPED_KEY: f"CLAMP {_TOP} TO THE COLUMNS AT THAT HEIGHT.",
    "columns-marked": (
        f"MARK EACH {_COLUMN} FOR LENGTH, SO AN {_CAP} PUSHED ONTO ITS TOP END "
        f"REACHES ITS INSIDE SEAT WITH ITS SKIRT CLEAR OF THE RECESS FLOOR IN {_TOP}."
    ),
    "frame-lifted-for-cut": _LIFT_OFF,
    steps.COLUMNS_CUT_KEY: f"CUT EACH {_COLUMN} AT ITS MARK. DO NOT TRIM THE {_CAP} CAPS.",
    "columns-chamfered": f"CHAMFER THE CUT END OF EACH {_COLUMN}.",
    steps.FRAME_RESEATED_KEY: (
        f"RESEAT THE COLUMNS AND {_TOP} ON {_BASE}, ALL ON THEIR MATCH MARKS."
    ),
    "top-axis-reset": (
        f"REPEAT STEPS {steps.step_number(steps.TOP_AXIS_SET_KEY)} AND "
        f"{steps.step_number(steps.TOP_FRAME_CLAMPED_KEY)}."
    ),
    "upper-holes-marked": (
        f"SPOT EACH COLUMN THROUGH THE CLEARANCE HOLE OF ITS {_TOP} SOCKET AS "
        f"{_step(steps.LOWER_HOLES_MARKED_KEY)}."
    ),
    "frame-lifted-for-drill": _LIFT_OFF,
    "upper-holes-drilled": (
        f"DRILL THE NEW SPOTS AS {_step(steps.LOWER_HOLES_DRILLED_KEY)}."
    ),
    "frame-reassembled": (
        f"RESEAT THE COLUMNS AND {_TOP} AS {_step(steps.FRAME_RESEATED_KEY)}."
    ),
    steps.UPPER_HOLES_CHECKED_KEY: (
        f"REPEAT THE {_step(steps.LOWER_HOLES_CHECKED_KEY)} CHECK AT EACH {_TOP} "
        "SOCKET."
    ),
    "upper-holes-reworked": (
        f"IF IT DOES NOT START, REWORK AS STEPS {steps.step_number('lower-holes-reworked')}"
        f"-{steps.step_number('lower-tap-chased')} WITH {_TOP} AND THE COLUMNS OFF "
        f"{_BASE}, UNTIL {_step(steps.UPPER_HOLES_CHECKED_KEY)} PASSES."
    ),
    # The far-wall engagement accepted at the bench, before the screw goes in
    # (CROSS_SCREW_FULL_THREAD_MIN_IN, its setting table row): the installed
    # thread is out of sight.
    "cross-screws-measured": (
        f"CHECK EACH {_CROSS} WITH A CALIPER: ITS FULL THREAD FROM UNDER THE HEAD "
        f"MEETS {setting_row('cross-screws-measured')}."
    ),
    "cross-screws-replaced": f"REPLACE ANY {_CROSS} THAT READS SHORT.",
    steps.CROSS_SCREWS_DRIVEN_KEY: (
        f"DRIVE THE EIGHT {_CROSS} SCREWS, EACH IN THROUGH ITS CLEARANCE HOLE, "
        "ONLY UNTIL ITS HEAD SEATS."
    ),
    "cross-screw-heads-checked": f"CHECK EVERY {_CROSS} HEAD SEATS.",
    "cross-screw-taps-chased": (
        "IF ONE DOES NOT, CHASE ITS TAPPED HOLE WITH A #10-32 BOTTOMING TAP UNTIL "
        f"IT SEATS AS {_step(steps.CROSS_SCREWS_DRIVEN_KEY)}."
    ),
    "cap-recesses-checked": (
        f"CHECK EACH CAP RECESS IN {_TOP} CLEARS THE SKIRT OF ITS {_CAP}."
    ),
    "caps-pushed-on": (
        f"PUSH AN {_CAP} ONTO EACH CHAMFERED COLUMN END UNTIL THE TUBE REACHES THE "
        "CAP'S INSIDE SEAT."
    ),
    "caps-checked": (
        f"CHECK EACH {_CAP} SITS ON ITS INSIDE SEAT, ITS SKIRT CLEAR OF THE RECESS "
        "FLOOR."
    ),
    # The cap's push-on grip is its only axial retention (rule 23, R7
    # machinist review): accepted by hand at the bench, and a loose stock cap
    # is replaced, not bonded.
    "caps-retained-checked": f"CHECK EACH {_CAP} DOES NOT PULL OFF OR TURN BY HAND.",
    "caps-replaced": (
        f"IF ONE PULLS OFF OR TURNS BY HAND, REPLACE IT WITH A NEW {_CAP}, PUSHED ON AS "
        f"{_step('caps-pushed-on')}, UNTIL {_step('caps-retained-checked')} PASSES."
    ),
    "column-ends-checked": f"CHECK NO {_COLUMN} END IS DISTORTED BY ITS CAP.",
    "support-seated": (
        f"SEAT {_SUPPORT} ON THE TOP FACE OF {_BASE}, ITS WINDOWS FACING THE SHORT "
        f"ENDS OF {_BASE}."
    ),
    steps.SUPPORT_SCREWED_KEY: (
        f"DRIVE THE FOUR {_SUPPORT_SCREW} SCREWS DOWN THROUGH {_SUPPORT} INTO "
        f"{_BASE}, EVENLY, UNTIL EVERY HEAD SEATS."
    ),
    "support-flat-checked": f"CHECK {_SUPPORT} LIES FLAT ON {_BASE}.",
    "support-heads-checked": f"CHECK EVERY {_SUPPORT_SCREW} HEAD BEARS ON {_SUPPORT}.",
    # Rule 23 at the package boundary: the set screw's only job is to grip the
    # summing post, which MHA-HA-00 slides to level and tightens it on.
    steps.GOOSENECK_STARTED_KEY: (
        f"START {_SET} IN THE TAPPED HOLE INTO {_POST_BORE}, CUP POINT CLEAR OF THE BORE; "
        f"{HA_SET_SCREW_TIGHTENED_REF} TIGHTENS IT ON THE POST."
    ),
    "post-bore-checked": f"CHECK {_POST_BORE} IS CLEAR OF THE CUP POINT OF {_SET}.",
    "columns-seated-checked": f"CHECK EVERY {_COLUMN} IS FULLY SEATED IN {_BASE}.",
    "match-marks-checked": "CHECK EVERY MATCH MARK ALIGNS.",
    "top-axis-checked": (
        f"CHECK EVERY {_TOP} SOCKET CROSS-HOLE AXIS STILL MEETS THE "
        f"{_step(steps.TOP_AXIS_SET_KEY)} HEIGHT."
    ),
}
if tuple(STEP_TEXT) != steps.SEQUENCE:
    raise AssertionError("STEP_TEXT must follow fr_frame_assembly_steps.SEQUENCE")
# The sequence prints in titled groups, each opening at its first key.
STEP_GROUPS = (
    (f"NAMEPLATE ON {_BASE}", steps.NAMEPLATE_SET_KEY),
    (f"COLUMNS IN {_BASE}", steps.COLUMNS_ROUGH_CUT_KEY),
    (f"{_TOP} ON THE COLUMNS", "top-frame-lowered"),
    ("COLUMNS CUT TO LENGTH", "columns-marked"),
    (f"TUBE HOLES AT {_TOP}", "upper-holes-marked"),
    ("FASTENING AND CAPS", "cross-screws-measured"),
    (f"SUPPORT ON {_BASE}", "support-seated"),
    ("SET SCREW AND FINAL CHECKS", steps.GOOSENECK_STARTED_KEY),
)
if STEP_GROUPS[0][1] != steps.SEQUENCE[0] or [
    steps.step_number(key) for _title, key in STEP_GROUPS
] != sorted({steps.step_number(key) for _title, key in STEP_GROUPS}):
    raise AssertionError("the step groups must open the sequence in order")

# The sections ASSEMBLY.md prints (ha_assembly_package, #2889): each group
# title over its numbered steps. The checks are steps of their own (rule 22).
_GROUP_STARTS = [steps.step_number(key) - 1 for _title, key in STEP_GROUPS]
STEP_SECTIONS = tuple(
    (
        title,
        tuple(
            f"{steps.step_number(key)}. {STEP_TEXT[key]}"
            for key in steps.SEQUENCE[start:end]
        ),
    )
    for (title, _key), start, end in zip(
        STEP_GROUPS, _GROUP_STARTS, [*_GROUP_STARTS[1:], len(steps.SEQUENCE)], strict=True
    )
)
ASSEMBLY_CHECKS: tuple[str, ...] = ()
EXPLODED_CAPTION = "EXPLODED VIEW - FIT-UP STEPS IN ASSEMBLY.MD"
