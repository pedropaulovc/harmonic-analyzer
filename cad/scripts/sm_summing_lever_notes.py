r"""Summing-lever drawing prose -- the view labels the part build stamps into
the SLDPRT, the mate-naming dimension callouts, the marked-dimension contract
and the joint proofs that let the print state no shortfall.

Split OUT of ``summing_lever_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``build_summing_assembly`` and ``build_knife_mount``
import the lever's geometry constants, so drawing prose living in that import
closure made every notes edit full-rebuild the summing assembly and knife
mount.  Imported ONLY by ``build_sm_summing_lever``, its drawing and the
offline drawing test.
"""

from __future__ import annotations

from magnifying_bracket_joint_layout import LINEAR_BAND, SCREW_THREAD
from sm_summing_lever_spec import COEFFICIENT_T, HOLE_SPEC

# --- Marked-dimension contract.  build_sm_summing_lever marks exactly these. ---
# Every cast contour is sized on the views: the uniform coefficient plate,
# the counter web's side radius, the common positive rib profile and its root
# blend, the boss, and the trunnion envelope, length and knife-edge radius.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateThickness"},
    "CoefficientsPlate": {"PlateLength"},
    "CylinderReference": {"CylinderDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
    "SummationAnchor": {"AnchorHeight"},
    "SummationPlateProfile": {"SummationArcRadius"},
    "SummationPlate": {"WebThickness"},
    "EdgeRibFrontProfile": {"EdgeRibFrontArcR", "RibReach", "EdgeRibFrontUpperBlendR"},
    "EdgeRibFront": {"EdgeRibThickness"},
    "MiddleRib": {"MiddleRibThickness"},
    "KnifeStubReference": {"KnifeStubLength"},
    "KnifeRidgeFillet": {"KnifeRidgeRadius"},
    "KnifeEnvelopeReference": {
        "HexWidth",
        "HexHeight",
        "RidgeFromLeft",
        "RidgeFromRight",
        "FlankToSide",
    },
}

# Model-owned text the part writes onto its own dimensions (prefix compartment).
# The summation web's two sides share one radius; both trunnions one length,
# one knife-edge radius and one hexagon (Detail D shows the -Z one), whose two
# upper flanks each make the one flank-to-side angle.  A radial prefix
# replaces the native R, so a radius prefix carries its own; the width's
# opening parenthesis marks it a reference (its suffix closes it).
DIMENSION_PREFIXES: dict[tuple[str, str], str] = {
    ("SummationPlateProfile", "SummationArcRadius"): "2X R",
    ("KnifeStubReference", "KnifeStubLength"): "2X ",
    ("KnifeRidgeFillet", "KnifeRidgeRadius"): "2X R",
    ("KnifeEnvelopeReference", "HexWidth"): "2X (",
    ("KnifeEnvelopeReference", "HexHeight"): "2X ",
    ("KnifeEnvelopeReference", "RidgeFromLeft"): "2X ",
    ("KnifeEnvelopeReference", "RidgeFromRight"): "2X ",
    ("KnifeEnvelopeReference", "FlankToSide"): "4X ",
    # A linear dimension across the plan's cylinder band prints no Ø itself.
    ("CylinderReference", "CylinderDia"): "<MOD-DIAM>",
    ("EdgeRibFrontProfile", "EdgeRibFrontUpperBlendR"): "R",
}

# The pivot cylinder's diameter is sized in the plan, across the band its
# two lines draw (machinist review r10: in the end views the R15.24 rib
# outline hides it, so the old Ø25.40 leader landed on a rib slant).
# Both plates merge with the cylinder, so no silhouette sizes it there: a
# hidden Top-plane reference line spans the diameter at this world Z, between
# the mid rib and the +Z end rib, where the dimension prints.  The line lies
# under the dimension line, which prints 2.8 sheet mm below its text (farm r11
# 2026-10-16: at Z 40, under the text, the line printed as a stray dashed
# line over the Ø25.40, machinist review r11).
CYLINDER_REFERENCE_Z = 45.6

KNIFE_MOUNT_NUMBER = "MHA-SM-02"  # sm-knife-mount: the knife-edge seat
BRACKET_NUMBER = "MHA-MG-01"  # mg-magnifying-bracket
BRACKET_SCREW_NUMBER = "MHA-MG-VN-53"  # mg-vn-magnifying-bracket-screw

# Drawing-side callout text keyed on the parametric dimension name: each tight
# band names its mate and function (drawing-guidelines rule 4), and the rib
# dimensions say which ribs share them (one outline in the end views).  A
# vertical dimension whose text stands above its span takes its callout above
# the value, one whose text hangs below takes it below, so the dimension line
# never runs through its own callout.  Callouts above are single lines: a
# multi-line one never printed (farm r4/r5 2026-10-16, text-unmatched).
# The mid rib runs tangent from the boss axis to the rib arc; the boss axis is
# located by the 76.20s in the plan, so the rib arc's callout in the front
# profile, where those tangents show, gives its apex words, not a third 76.20.
# Each summation-web side arc rises from the boss's quadrant and meets axis A
# at the plate end inside the cylinder; the radius's text has room only for
# its value (inside the arc, clear of the trunnion stub), so the boss's
# diameter names both ends.  The three receiver coordinates are one bracket
# hole pattern, each tight station naming the mate and that the pattern
# locates it (rule 7: flagged where it applies; machinist review r14 could
# not tell from MATCHES whether the screws locate or only clamp).  The two
# left of VIEW F have room for one line only. The ridge-to-side pair and the
# flank-to-side angle hold the knife edge for the trunnion's worst-case free
# rock in the knife mount's bore
# (``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``, code review C09).
# Each names that seat, as the vertex height does. Detail D carries the whole
# knife envelope, its ridge round and datum A together at 10:1.
# Both stubs are one prism, so their side faces share two planes
# (``build_sm_summing_lever._hex_knife``), which ties the -Z ridge to datum A
# within ``sm_summing_lever_spec.KNIFE_STUB_RIDGE_OFFSET_MAX``.  The model
# carries that; the print carries the owner's C09 wording, KNIFE EDGE
# SYMMETRIC TO SIDES, BOTH STUBS, split across the pair, and no coplanarity
# requirement of its own (machinist review bdc033f13: "SIDES IN ONE PLANE"
# stated a requirement with no limit).  Lines of at most
# RIDGE_CALLOUT_MAX_CHARS keep each ridge block outside its dimension span.
# Back reverses the model sides: the longer BOTH STUBS block is on sheet
# left, so its unchanged wording wraps across three short callout lines.
RIDGE_CALLOUT_MAX_CHARS = 30
DIMENSION_CALLOUTS_ABOVE: dict[str, str] = {
    "RibReach": "ALL POSITIVE RIBS",
    "ReceiverY0": f"LOCATES {BRACKET_NUMBER}",
}
DIMENSION_CALLOUTS_BELOW: dict[str, str] = {
    "RidgeFromLeft": f"{KNIFE_MOUNT_NUMBER} SEAT;\nSYMMETRIC TO SIDES",
    "RidgeFromRight": f"KNIFE-EDGE SEAT\nIN {KNIFE_MOUNT_NUMBER};\nBOTH STUBS",
    "FlankToSide": f"{KNIFE_MOUNT_NUMBER} SEAT",
    "HexHeight": f"VERTEX UP\nKNIFE-EDGE SEAT\nIN {KNIFE_MOUNT_NUMBER}",
    "EdgeRibFrontUpperBlendR": "RIB SIDE ROOTS\nAND PROFILE BLENDS",
    "EdgeRibFrontArcR": "ALL RIBS\nMID RIB APEX\nAT BOSS AXIS",
    "AnchorOuterDia": "WEB ARCS RUN\nFROM QUADRANTS\nTO AXIS A AT ENDS",
    "ReceiverX0": f"LOCATES {BRACKET_NUMBER}\n{SCREW_THREAD} SCREW PATTERN",
    "ReceiverX1": f"LOCATES {BRACKET_NUMBER}",
    # The plan's 152.40 is the body's end-face span, not the part's overall:
    # the stubs stand 2X 21.72 past it (machinist review 20261018 read it
    # as the overall; drawing-guidelines: nothing reads like an overall that
    # is not one).  Short lines: the block stands 14 mm from the border.
    "PlateLength": "BODY\nEND FACES",
}

# Leads the 2-56 receiver callout: the rib contains the drill with an ordinary
# bounded .XX depth band. The lower limit clears the unchanged screw and
# two-pitch tap lead; the upper limit keeps its point inside the rib.
# The native depth callout and source-model blind-depth proof remain authoritative.
BRACKET_TAP_CALLOUT_PROCESS = (
    "DRILL ENDS IN RIB TO RETAIN PLATE WALLS\n"
    f"DRILL CLEARS {BRACKET_SCREW_NUMBER} TIP AND TAP LEAD\n"
)
# Under the plan's boss Z location (datum B to the boss axis): the mid rib
# is centred on the same station.
BOSS_Z_CALLOUT = "BOSS AXIS AND\nMID RIB CENTRE"
# The 20X 6-32 threads run through the uniform coefficient plate.
SPRING_TAP_CALLOUT_PROCESS = "THREAD THRU COEFFICIENT PLATE\n"

# --- Joint proofs the print relies on (drawing-guidelines rules 18 and 20). ---
# The plate's worst-case thickness at the title block's .XX band, less 1.5
# incomplete threads, must retain at least 1.5D of full #6-32 thread.
if HOLE_SPEC.size != "#6-32":
    raise AssertionError(
        f"spring-anchor engagement assumes #6-32, not {HOLE_SPEC.size}"
    )
SPRING_TAP_MAJOR_DIA = 0.138 * 25.4
SPRING_TAP_PITCH = 25.4 / 32.0
SPRING_TAP_ENGAGEMENT_MIN = COEFFICIENT_T - LINEAR_BAND - 1.5 * SPRING_TAP_PITCH
if SPRING_TAP_ENGAGEMENT_MIN < 1.5 * SPRING_TAP_MAJOR_DIA:
    raise AssertionError(
        f"20X {HOLE_SPEC.size} keeps {SPRING_TAP_ENGAGEMENT_MIN:.3f} of full "
        f"thread, under 1.5D"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# Sheet 2's view looks at the -Z end face (the bracket receiver): sheet 1's
# plan carries a lettered viewing arrow onto that face, and the view is
# named by the letter (machinist review r10 read "BACK VIEW" as looking from
# below). A and B are datums; D is the complete knife detail. The view is
# SolidWorks' Back view, +Y up; projected from the plan's arrow it would keep
# the plan's X (boss left) with +Y towards the plan, so it is the projection
# turned half a turn and says so (machinist review bdc033f13: boss on the
# right against the front view and VIEW G).  Drawn as projected, every
# sheet-2 dimension and callout would have to be re-placed upside down.
BACK_VIEW_LETTER = "F"
BACK_VIEW_NOTE = f"VIEW {BACK_VIEW_LETTER} SCALE 1:1 ROTATED 180°"
# Sheet 1's end profile looks at the +Z end face (datum B) but stands above
# the plan, out of third-angle order (machinist review r15 read it as the
# -Z end, so as VIEW F's mirror missing its taps): it is a removed view too,
# named by a letter arrow onto the +Z end.
FRONT_VIEW_LETTER = "G"
FRONT_VIEW_NOTE = f"VIEW {FRONT_VIEW_LETTER} SCALE 1:2"
