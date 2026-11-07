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

# LINEAR_BAND is re-exported for test_ch_vn_spring_hook_drawing (the bracket
# side's millimetre .XX row); the lever's own plate band is
# COEFFICIENT_T_DEVIATIONS.
from magnifying_bracket_joint_layout import LINEAR_BAND as LINEAR_BAND
from sm_summing_lever_spec import COEFFICIENT_T, COEFFICIENT_T_DEVIATIONS, HOLE_SPEC

# --- Marked-dimension contract.  build_sm_summing_lever marks exactly these. ---
# Every cast contour is sized on the views: the uniform coefficient plate,
# the counter web's side radius, the common positive rib profile, the boss,
# and the trunnion envelope, length and knife-edge radius. The title block
# controls inside-corner R.040 MAX; modeled rib blends remain native controls.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {"PlateWidth", "PlateThickness"},
    "CoefficientsPlate": {"PlateLength"},
    "CylinderReference": {"CylinderDia"},
    "SummationAnchorProfile": {"AnchorOuterDia"},
    "SummationAnchor": {"AnchorHeight"},
    "SummationPlateProfile": {"SummationArcRadius"},
    "SummationPlate": {"WebThickness"},
    "EdgeRibFrontProfile": {"EdgeRibFrontArcR", "RibReach"},
    "EdgeRibFront": {"EdgeRibThickness"},
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
    ("EdgeRibFront", "EdgeRibThickness"): "3X ",
    ("EdgeRibFrontProfile", "RibReach"): "3X ",
    ("EdgeRibFrontProfile", "EdgeRibFrontArcR"): "3X R",
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

# Drawing-side callout text keyed on the parametric dimension name.  Novice
# rubric (fan-out of #2223, rules 4, 7 and 26): a location or size carries
# its value and band only, counts replace "ALL RIBS" words (the 3X prefixes
# above), and project labels (COEFFICIENT TOP, POSITIVE RIBS, MID RIB) do
# not print.  Every callout hangs below its value.  Each summation-web side
# arc rises from the boss's
# quadrant and meets axis A at the plate end inside the cylinder; the
# radius's text has room only for its value (inside the arc, clear of the
# trunnion stub), so the boss's diameter names both ends (owner RV-03).  The
# three receiver coordinates are one bracket hole pattern whose mate the tap
# callout names once (rule 7: a location carries no words).  The
# ridge-to-side pair, the flank-to-side angle and the vertex height hold the
# knife edge for the trunnion's worst-case free rock in the knife mount's
# bore (``build_sm_summing_assembly.KNIFE_FREE_ROCK_WORST_DEG``, code review
# C09): one feature, so each links one numbered note naming its seat once
# (rule 4).  Detail D carries the whole knife envelope, its ridge round and
# datum A together at 10:1.  Both stubs are one prism, so their side faces
# share two planes (``build_sm_summing_lever._hex_knife``), which ties the +Z
# ridge to datum A on the -Z ridge within
# ``sm_summing_lever_spec.KNIFE_STUB_RIDGE_OFFSET_MAX``; the 2X counts say
# both stubs, and the two ridge-to-side limits state the symmetry.
KNIFE_SEAT_NOTE = 1
KNIFE_SEAT_NOTE_LINK = f"SEE NOTE {KNIFE_SEAT_NOTE}"
DRAWING_NOTES = f"{KNIFE_SEAT_NOTE}. KNIFE-EDGE SEAT IN {KNIFE_MOUNT_NUMBER}"
DIMENSION_CALLOUTS_BELOW: dict[str, str] = {
    "RidgeFromLeft": KNIFE_SEAT_NOTE_LINK,
    "RidgeFromRight": KNIFE_SEAT_NOTE_LINK,
    "FlankToSide": KNIFE_SEAT_NOTE_LINK,
    "HexHeight": KNIFE_SEAT_NOTE_LINK,
    "AnchorOuterDia": "WEB ARCS RUN\nFROM QUADRANTS\nTO AXIS A AT ENDS",
}

# The two blind taps fasten the magnifying bracket and are spotted through
# its holes at assembly (delegated ruling sm Q7, 2026-11-07 (Main), no
# precedent; owner review #2144; MHA-SM-00 carries the step): their stations
# print REF (build_sm_summing_lever._receiver_coordinate_dimensions).  Their
# native callout owns the pilot and full-thread depths; no additional cavity
# or wall limit prints.
BRACKET_TAP_CALLOUT_PROCESS = f"SPOT THRU {BRACKET_NUMBER} AT ASSEMBLY\n"

# --- Decimal places, #290. ---
# The spring pattern's BASIC row X, start Z and pitch are calibrated stations
# (1.5689 / .5022 / .2778): four places hold them to under .00005 in.  They
# are native model dimensions of the part's hidden SpringRowCoordinates
# sketch, which owns their BASIC type, places and 19X count.  The drawing's
# own boss-top (.28) and knife-ridge (.10) locations of the coefficient top
# follow the document's .XX, as do the 3.00 anchor X/Z: their printed limits
# stay inside every check (sm_summing_lever_profile.PLATE_TOP_Y_ALLOWANCE).
BASIC_PLACES = 4
SPRING_ROW_LOCATORS = ("SpringRowX", "SpringStartZ", "SpringPitch")
# Every Hole Wizard drill diameter prints .XXX, the #36 and #25 tap drills
# too (.107, .150).  Both are THRU ALL taps, whose native drill variable is
# <hw-thrutapdrldia>; only the blind bracket taps carry <hw-tapdrldia> and
# the two depth lengths.  A callout does not inherit the part's places, so the
# drawing writes these: declared exception RV-04 in sm-summing-lever.yaml.
SPRING_TAP_PRECISION = {"hw-thrutapdrldia": 3}
COUNTER_TAP_PRECISION = {"hw-thrutapdrldia": 3}
# The blind bracket taps' routine drill depth prints .XX (rule 3); its
# diameter and the full-thread MIN keep three places.
BRACKET_TAP_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": 2,
    "hw-threaddepth": 3,
}
# The receiver stations (1.120 / .581 / .128, REF) sit on the .001 grid; the
# lever's taps are modelled there (magnifying_bracket_joint_layout).
RECEIVER_COORDINATE_PLACES = 3

# --- Joint proofs the print relies on (drawing-guidelines rules 18 and 20). ---
# The plate's worst-case thickness at its printed .XX limit, less 1.5
# incomplete threads, must retain at least 1.5D of full #6-32 thread.
if HOLE_SPEC.size != "#6-32":
    raise AssertionError(
        f"spring-anchor engagement assumes #6-32, not {HOLE_SPEC.size}"
    )
SPRING_TAP_MAJOR_DIA = 0.138 * 25.4
SPRING_TAP_PITCH = 25.4 / 32.0
SPRING_TAP_ENGAGEMENT_MIN = (
    COEFFICIENT_T + COEFFICIENT_T_DEVIATIONS[0] - 1.5 * SPRING_TAP_PITCH
)
if SPRING_TAP_ENGAGEMENT_MIN < 1.5 * SPRING_TAP_MAJOR_DIA:
    raise AssertionError(
        f"20X {HOLE_SPEC.size} keeps {SPRING_TAP_ENGAGEMENT_MIN:.3f} of full "
        f"thread, under 1.5D"
    )

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"
# Sheet 2 looks from +X/-Y/-Z: the existing pictorial shows the coefficient
# backing from below and the receiver end, instead of repeating the top view.
RECEIVER_ISOMETRIC_OCTANT = (1, -1, -1)
RECEIVER_ISOMETRIC_VIEW_NOTE = "UNDERSIDE ISOMETRIC VIEW SCALE 1:4"
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
# A removed view at the sheet's scale: its letter only (rule 9).
FRONT_VIEW_NOTE = f"VIEW {FRONT_VIEW_LETTER}"
