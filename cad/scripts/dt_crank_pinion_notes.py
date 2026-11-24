"""Drawing-only text for the straight crank pinion: gear data, numbered notes
and the callouts that link them.

Geometry and exact stock tangent-span limits remain in dt_crank_pinion_spec,
which the crankshaft, its pin and the drive train also import; the pinion
sheet's words live here so editing them re-keys only the pinion.
"""

from __future__ import annotations

import dt_crank_drive_gear_notes as mate_notes
import dt_crank_pinion_spec as spec
from dt_crank_drive_gear_spec import inch_text
from stock_form_cutter import TOOTH_FORM_NOTE


# The cone gear whose 120-tooth gear (T120 on the MHA-DT-00 sheet) the turned
# band and the shoulder clear.
CONE_GEAR_120T = f"120T CONE GEAR {spec.CONE_GEAR_NUMBER}"
# The sheet's numbered notes (DRAWING_NOTES, below), each linked by "SEE NOTE
# n" from every dimension it serves (drawing-guidelines.md rule 7).
MESH_NOTE_NUMBER = 1
BORE_FIT_NOTE_NUMBER = 2
PIN_FIT_NOTE_NUMBER = 3
# The pin hole's callout hangs under its reference Ø: the process with its
# mate, then the link (rule 26: size, process; rule 7: at most two lines of
# words). The pin's fit and acceptance are note 3; the flush ends are
# MHA-DT-00 step 4's (an assembly instruction on a part sheet, rule 7). The
# spec's PIN_FIT_LINES still feed that step and the crankshaft's property.
# The cross hole runs through both walls of the boss and the shaft, so the
# process row says THRU (rules 9 and 26; fan-out r3: no depth read); matched
# with the crankshaft, it is drilled at assembly, which note 3 and MHA-DT-00's
# pin step carry.
PIN_HOLE_CALLOUT = "\n".join(
    (
        f"MATCH DRILL AND REAM THRU WITH {spec.CRANKSHAFT_NUMBER}",
        f"SEE NOTE {PIN_FIT_NOTE_NUMBER}",
    )
)
# Three short lines (drawing-guidelines.md rule 7). Note 1 names the two
# mates the tip diameter, the turned band and the banded shoulder and
# face-width lengths serve, once (rule 4: a mate serving several features is
# named once): their short limits keep full tips in the 64T mesh, their long
# ones the 120T gear's clearance (build_dt_drive_train_assembly proves both).
# The turned band's fit-up note is gone (fit audit 2026-11-23 part 2, B9: the
# band keeps 1.67 mm to T120 at print worst, so MHA-DT-00 looks for daylight
# and no assembly cut remains to permit). Note 2 names the mate made to the
# reamed bore, which carries the fit's acceptance on its own sheet (fit audit
# 2026-11-23, MHA-DT-10.bore: the acceptance prints once, on the member made
# last); the bore slides onto the crankshaft to its seat feeler and is then
# pinned, so it neither runs nor presses. Note 3 is the pin's fit and its
# acceptance (rule 4: a matched fit states one).
DRAWING_NOTES = "\n".join(
    (
        f"{MESH_NOTE_NUMBER}. MESH WITH CRANK DRIVE GEAR {spec.MESH_GEAR_NUMBER}; "
        f"CLEARANCE TO {CONE_GEAR_120T}.",
        f"{BORE_FIT_NOTE_NUMBER}. CRANKSHAFT {spec.CRANKSHAFT_NUMBER} SEAT IS TURNED "
        "TO THIS BORE.",
        f"{PIN_FIT_NOTE_NUMBER}. DRIVE FIT ON PIN {spec.PIN_NUMBER}; NOT REMOVABLE BY HAND.",
    )
)

# The span's exact stock limits are .0007 wide, narrower than the shop
# table's milled-thickness row, so they print as the cut's reference and the
# mesh is accepted against the made MHA-DT-07 on its fixed centres by turning
# free by hand at assembly (owner ruling 2026-11-24, fit audit question 16:
# the .002-.007 class could not be met by this crossed mesh); the backlash
# that mesh gives at print worst prints as REF, worded as the 64T's own row
# (drawing-guidelines.md rule 7: a gear data block carries the mesh; rule 25:
# both sheets agree).
SPAN_LABEL = f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH (REF)"
BACKLASH_LABEL = f"TRANSVERSE BACKLASH WITH {spec.MESH_GEAR_NUMBER} (REF)"
# Delegated ruling 2026-11-17 on #2481 (option B; precedent #2365 and #2416;
# owner reviews it after the fact on #2144): the fixed-centre mesh is accepted
# by hand at assembly, MHA-DT-00's full turn before the pin is drilled, not by
# the prints' tightest corner. The ruling's reference line rides the mate row
# as a plain REF fact (rule 20 keeps governance words off the sheet; the part
# sheet names no step, rule 7): machinist review of #3090 (3 of 3 runs) read a
# separate MESH WITH row as a fourth naming of the mate and a second
# acceptance beside the backlash row.
MATE_ROW = (
    "MATES WITH",
    f"CRANK DRIVE GEAR {spec.MESH_GEAR_NUMBER}, 64T; TURNS FREE BY HAND (REF)",
)
# Section A-A cuts through a tooth, so the band reads as a solid ring and the
# spaces seem to stop against it (machinist review of the stack build). They
# do not: the band is the teeth turned down, and the spaces run the whole face
# width out over the boss, turned to the root (BOSS_DIA = ROOT_DIA_MIN), which
# is where the form cutter runs out. The boss's .X band allows it above the
# root, so a cutter mark on the boss is permitted, not a reject. A tooth fact,
# so it reads with the teeth, as the tooth edges do. Short enough to end
# clear of the Ø.743 callout (fan-out r1 printed its OK under the Ø).
TOOTH_RUNOUT = "FULL LENGTH OF TURNED BAND; CUTTER RUNOUT INTO BOSS OK"

# The spur's normal and transverse sections coincide. Its physical tooth
# count selects a different stock cutter from the inclined mate's virtual count.
GEAR_DATA = mate_notes.gear_data_note(
    [
        ("NUMBER OF TEETH", f"{spec.TEETH}"),
        (
            "DIAMETRAL PITCH, NORMAL = TRANSVERSE (CUTTER)",
            f"{spec.DIAMETRAL_PITCH:.2f}",
        ),
        # The cutter by number and range, as the handbook lists it.  The
        # template's 14-tooth design count printed as "14T REFERENCE", a
        # private phrase (farm r6 196fd7720d, 3 of 3 runs; the 64T's row
        # dropped the same count).
        (
            "FORM CUTTER",
            f"#{spec.CUTTER_NUMBER}, {spec.CUTTER_TEETH_RANGE[0]}-{spec.CUTTER_TEETH_RANGE[1]}T",
        ),
        ("PRESSURE ANGLE, NORMAL = TRANSVERSE", f"{spec.PRESSURE_ANGLE_DEG:.1f} DEG"),
        ("PITCH DIAMETER (REF)", inch_text(spec.PITCH_DIA, 3)),
        # One REF cut depth: on this spur NORMAL = TRANSVERSE, so a separate
        # NORMAL TOOL PLUNGE row printed the same depth a second time, .0001
        # apart (machinist review of #3090, 2 of 3 runs, judge-confirmed).
        (
            "ACTUAL ROOT DIA MIN-MAX / MAX CUT DEPTH (REF)",
            f"{inch_text(spec.ROOT_DIA_MIN, 4)}-{inch_text(spec.ROOT_DIA_MAX, 4)} / "
            f"{inch_text(spec.WHOLE_DEPTH, 4)}",
        ),
        (SPAN_LABEL, mate_notes.accept_limits_text(spec.BASE_TANGENT_SPAN_LIMITS_MM, 4)),
        (BACKLASH_LABEL, mate_notes.accept_limits_text(mate_notes.MESH_BACKLASH_REF_MM, 4)),
        (
            "ACTUAL CIRCULAR PITCH THICKNESS (REF)",
            inch_text(spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS, 4),
        ),
        (
            # A finished-part acceptance, not a setup, worded as the 64T's own
            # row (machinist review of #3090, 3 of 3 runs: ACCEPT AT SETUP is
            # method; the 64T's row answered the same finding on PR #2331
            # round 9; rule 25).
            "TOOTH RUNOUT TO BORE",
            f"{inch_text(spec.TOOTH_RUNOUT_TIR_MM, 3)} TIR MAX, SETS BACKLASH WITH "
            f"{spec.MESH_GEAR_NUMBER}",
        ),
        ("TOOTH FORM", TOOTH_FORM_NOTE),
        ("TEETH", TOOTH_RUNOUT),
        # The title block's edge break would erase these fine teeth; the
        # requirement is a tooth fact, so it reads with them, as on the 64T.
        ("TOOTH EDGES", "DO NOT BREAK OR CHAMFER FLANKS, TIPS OR ROOTS"),
        # The 64T's tooth line prints on its own sheet; it changes nothing
        # this spur is cut to (machinist review on #2482, rule 26).
        MATE_ROW,
    ]
)
