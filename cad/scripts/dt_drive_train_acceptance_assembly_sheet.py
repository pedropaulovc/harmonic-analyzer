"""MHA-DT-00 sheet 16: the setting table's fits and acceptances.

R5 machinist review (rule 22, 3/3 runs): every measurable fit and acceptance
a step or check makes prints in a setting-table row, not only in its step.
None is a single model dimension a setting view could carry (stack results,
end plays, gaps, flush and pin-depth limits, the spring-foot station inside
#1037's centred window, engagements read as the lesser of two records), so each
is a row the drawing numbers on from sheet 15's rows and places with the
shared general-table helper; its step cites the row in place of the number.

Every cell is a spec symbol or names the instrument; the drawing only numbers
and places the rows (test_drawing_specification_purity).  Drawing-only: no
builder imports this module (test_assembly_sheet_isolation), and
ha_assembly_package reads its instruments into the ASSEMBLY.md tool list.
"""

from __future__ import annotations

from cone_set_stack import (
    LAND_2_ASSEMBLED_RUNOUT_TIR_MM,
    PIVOT_RUNOUT_TIR_MM,
)
from cone_stack_end_play import SHAFT_END_PLAY
import cylinder_bank_layout as bank
import dt_cone_gear_spec as cone_gear
from dt_cone_gear_stack import STACK_L20_ACCEPT
import dt_crank_handle_pivot_screw_spec as handle_screw
from dt_crank_pin_ring_spec import BUTT_GAP_BAND as RING_BUTT_GAP_BAND
from dt_drive_train_assembly_sheet import (
    FEELER_PLACES,
    inch_floor_mm,
    inch_max_text,
    inch_text,
    inch_window,
)
import dt_drive_train_steps as steps
from dt_pinion_arbor_collar_spec import (
    PIN_END_DEPTH_SPREAD_TEXT as COLLAR_PIN_DEPTH_SPREAD,
)
from dt_pinion_spring_section import SCREW_EAST_OF_PIVOT as SPRING_SCREW_EAST_OF_PIVOT
from dt_swing_stop_screw_spec import MIN_USEFUL_ENGAGEMENT_TEXT as STOP_SCREW_ENGAGEMENT
from dt_vn_cone_pivot_screw_spec import (
    MIN_USEFUL_ENGAGEMENT_TEXT as PIVOT_SCREW_ENGAGEMENT,
)
from dt_vn_pinion_strap_pin_spec import PIN_SUB_FLUSH_MAX as STRAP_PIN_SUB_FLUSH_MAX
import dt_vn_post_mount_screw_spec as post_screw
from pinion_rig_layout import FLUSH_SET_ERROR
import pinion_rig_tip_gap as TIP_GAP


def _step_ref(key: str, letter: str = "") -> str:
    return f"{steps.step_number(key)}{letter}"


# The fit-up modules' own wordings of three limits, which the drawing also
# reads to find the step text each row replaces.
FLUSH_SET_TEXT = f"±{inch_max_text(FLUSH_SET_ERROR, 3)}"
STRAP_PIN_DEPTH_TEXT = f"0 TO {inch_max_text(STRAP_PIN_SUB_FLUSH_MAX, 3)}"
POST_SCREW_SHORT_TEXT = inch_max_text(
    post_screw.POST_SCREW_CUT_TO_FIT_SHORT, post_screw.CUT_TO_FIT_SHORT_PLACES
)
(_LAND_2_TEETH,) = cone_gear.LAND_2_TEETH
# (key, step, setting, set to / accept, check with), in step order, then rows
# added later appended so no earlier row (which other records cite by number)
# renumbers.
ACCEPTANCES = (
    (
        "cone-stack",
        _step_ref("cone-gears-stacked", "F"),
        "T120 FRONT TO MHA-DT-37 TEETH' BACK, DRY STACK",
        inch_window(STACK_L20_ACCEPT, 3),
        # Codjiflo on #3023: the owned 6 in calipers read the ~5.87 in
        # stack; the shop's micrometers stop at 3 in.
        "CALIPERS",
    ),
    (
        "post-screw-cut",
        _step_ref("post-and-tip-block", "K"),
        "EACH MHA-DT-VN-61 CUT END TO THE MHA-DT-20 UNDERSIDE",
        f"FLUSH TO {POST_SCREW_SHORT_TEXT} SHORT",
        # Owner ruling 2026-11-23, tool audit Q4: "Print CALIPER DEPTH ROD;
        # no depth micrometer". The owned calipers read .0005 (shop
        # gauges.calipers) inside each of these four windows (.005, .008,
        # .040 wide).
        "CALIPER DEPTH ROD",
    ),
    (
        "shaft-end-play",
        _step_ref("end-play-set", "C"),
        "MHA-DT-04 END PLAY AT THE SHAFT END",
        inch_window(SHAFT_END_PLAY, 3),
        "DIAL INDICATOR",
    ),
    (
        "ring-butt-gap",
        _step_ref("crank-hub-fitted", "P"),
        "MHA-DT-27 BUTT GAP, CLOSED",
        "0-" + f"{RING_BUTT_GAP_BAND[1] / 25.4:.3f}".removeprefix("0"),
        "FEELERS",
    ),
    (
        "handle-end-play",
        _step_ref("crank-handle-fitted", "H"),
        "MHA-DT-08 END PLAY ON MHA-DT-32",
        inch_window(handle_screw.END_PLAY_RANGE, 3),
        "FEELERS",
    ),
    (
        "arbor-dome",
        _step_ref("cylinder-bank-located", "T"),
        "EACH MHA-DT-13 DOME PROUD OF ITS MHA-DT-02 OUTER FACE",
        inch_text(bank.ARBOR_DOME_HEIGHT, 2),
        "CALIPER DEPTH ROD",
    ),
    (
        "collar-pin-ends",
        _step_ref("arbor-collar-pinned", "A"),
        "MHA-DT-VN-63 END DEPTHS BELOW THE MHA-DT-33 OD",
        f"WITHIN {COLLAR_PIN_DEPTH_SPREAD} OF EACH OTHER",
        "CALIPER DEPTH ROD",
    ),
    (
        "shaft-rear-flush",
        _step_ref("straps-pinned-to-torque-shaft", "C"),
        "MHA-DT-19 REAR END TO THE MHA-DT-18 REAR FACE",
        f"FLUSH {FLUSH_SET_TEXT}",
        "CALIPER DEPTH ROD",
    ),
    (
        "strap-pin-ends",
        _step_ref("straps-pinned-to-torque-shaft", "E"),
        "MHA-DT-VN-63 PIN ENDS BELOW THE MHA-DT-14 EDGES",
        STRAP_PIN_DEPTH_TEXT,
        "CALIPER DEPTH ROD",
    ),
    (
        "spring-foot",
        _step_ref("rig-located", "A"),
        "MHA-DT-24 FOOT HOLE CENTRE RIGHT OF THE MHA-DT-19 AXIS",
        inch_text(SPRING_SCREW_EAST_OF_PIVOT, 2),
        "CALIPERS",
    ),
    (
        "tip-gap",
        f"{_step_ref('rig-located', 'E')}, CHECK 7",
        "PARKED TIP GAP AT GEAR 0 AND AT GEAR 19",
        inch_window(TIP_GAP.TIP_GAP_ACCEPT, FEELER_PLACES),
        f"{TIP_GAP.TIP_GAP_FEELER_TEXT} SNUG",
    ),
    (
        "lift-rod-rear-flush",
        _step_ref("cam-collars-set", "A"),
        "MHA-DT-17 REAR END TO THE MHA-DT-18 REAR FACE",
        f"FLUSH {FLUSH_SET_TEXT}",
        "CALIPER DEPTH ROD",
    ),
    # Attempt 1 review (run 20261117T133225781Z, rule 22): checks 4W and 4Y
    # printed their engagement minimums only in check text.  Each is the lesser
    # of two recorded readings (step 23's depth gauge and calipers), never one
    # model dimension.
    (
        "pivot-screw-engagement",
        "CHECK 4W",
        "MHA-DT-VN-52 FULL-FORM THREAD ENGAGEMENT",
        PIVOT_SCREW_ENGAGEMENT,
        f"LESSER OF {_step_ref('other-base-mounting', 'J')}, "
        f"{_step_ref('other-base-mounting', 'K')}",
    ),
    (
        "stop-screw-engagement",
        "CHECK 4Y",
        "MHA-SH-VN-52 SWING STOP FULL-FORM THREAD ENGAGEMENT",
        STOP_SCREW_ENGAGEMENT,
        f"LESSER OF {_step_ref('other-base-mounting', 'N')}, "
        f"{_step_ref('other-base-mounting', 'P')}",
    ),
    # #3292 (owner ruling 2026-11-21, options 2 + 4): T024 is centred to this
    # row while its bond is wet (1S); after cure it is recorded (1W: owner
    # ruling 2026-11-24, audit part 2 C5, "the after-cure readings become a
    # record only"), read in every space with the part sheets' over-pins
    # pin; cone_set_stack books the limit, floored onto the printed places.
    # MHA-DT-04 stands on its journal end in a V-block, so it turns on the
    # journal's axis and 1T clips the comb in that same setup (Codjiflo
    # review of #3324); the pin names the pin-gauge row of the tool list as
    # MHA-PD-00's tooth-space rows do.  The cells hold the table's widest
    # SETTING and ACCEPT widths (reference-view keep-out).
    (
        "t024-runout",
        f"{_step_ref('cone-gears-stacked', 'S')}, {_step_ref('cone-gears-stacked', 'W')}",
        f"T{_LAND_2_TEETH:03d}, "
        f"\u00d8{inch_text(cone_gear.over_pins_pin_dia_mm(_LAND_2_TEETH), 3)} GAUGE PIN, "
        "MHA-DT-04 ON END ON A V-BLOCK",
        f"{inch_text(inch_floor_mm(LAND_2_ASSEMBLED_RUNOUT_TIR_MM, 4), 4)} TIR MAX EACH SPACE",
        "TEST INDICATOR",
    ),
    # #2473 (owner ruling 2026-11-22, option G): MHA-DT-37's pivot is tapped
    # true to this row while the tip's bonds are wet (2B) and recorded after
    # cure (2E, audit part 2 C5), before the post is assembled, over a full
    # turn in T024's setup; cone_set_stack books the limit as the running
    # axis's offset from MHA-DT-04's.
    (
        "pivot-runout",
        f"{_step_ref('post-and-tip-block', 'B')}, {_step_ref('post-and-tip-block', 'E')}",
        "MHA-DT-37 PIVOT, MHA-DT-04 ON END ON A V-BLOCK",
        f"{inch_text(inch_floor_mm(PIVOT_RUNOUT_TIR_MM, 4), 4)} TIR MAX",
        "TEST INDICATOR",
    ),
    # #2473 (owner ruling 2026-11-22): "Add an after-cure reading of the 12-
    # and 18-tooth gears in the same setup: Ø.040 pin in each tooth space,
    # shaft on end on the V-block, .0030 TIR MAX (as the 24-tooth already
    # has)". Owner ruling 2026-11-24, audit part 2 C5: "the after-cure
    # readings become a record only; strip and re-bond only if a gear
    # hesitates in the 80-turn running check", so the row records (nothing
    # is set to it) and the hesitation in check 4R accepts.
    (
        "spigot-gear-runout",
        _step_ref("post-and-tip-block", "E"),
        f"{' AND '.join(f'T{teeth:03d}' for teeth in cone_gear.SPIGOT_TEETH)}, "
        f"\u00d8{inch_text(cone_gear.over_pins_pin_dia_mm(cone_gear.SPIGOT_TEETH[0]), 3)} GAUGE PIN, "
        f"SETUP AS T{_LAND_2_TEETH:03d}",
        "RECORD EACH SPACE",
        "TEST INDICATOR",
    ),
)
