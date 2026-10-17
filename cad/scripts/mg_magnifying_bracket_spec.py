r"""Magnifying-bracket dimensional contract -- the single source of truth shared
by the part build (``build_mg_magnifying_bracket.py``) and its manufacturing
drawing (``draw_mg_magnifying_bracket.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else imports this bracket's
nominals -- the magnifier assembly places it BY NAME and mates it by named
references (never a Python constant), so one ``_spec`` module is right here (no
``_geom`` split, unlike the magnifying LEVER whose knife-axis station an
assembly imports).  The offline lockstep test asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.

The bracket is a three-feature fitting: an extruded COLLAR tube (Ø12 OD, 10
long about local X) whose bore is the PRESS seat for the Ø6 magnifying lever
(nominal and bands from ``mg_lever_press_fit_geom``, the joint's one read
point), a rectangular ARM cantilevering +Z to the summing plate, and a mounting
FLANGE whose +Z face butts the plate's front face.  The two plan rectangles
carry the auto-importable marked dimensions (the flange thickness at the
title block's .XXX band, the screws' grip); the collar's end-view circles
carry the OD and the bore, a REFERENCE nominal whose callout states the
matched fit on the MHA-MG-003 lever, and its extrude the banded length,
which names the lever's press zone it matches; the blanked ``ArmSection``
witness carries the arm's section and the bore axis's one datum chain (the
mounting face and the arm's end, both from the axis) in the side view.  A
native plain clearance-hole callout names the summing lever's tapped holes
the banded hole pattern matches.  ``ArmRootFillet`` breaks the arm-to-flange
inside corners at a single MAX radius (drawing-guidelines.md rule 16).
"""

from __future__ import annotations

import _config

from magnifying_bracket_joint_layout import (
    ENGAGEMENT_MIN,
    FLANGE_THICKNESS_BAND,
    GRIP_BAND,
    LINEAR_BAND,
    POSITION_BAND,
    SCREW_MAJOR_DIA,
    SCREW_TIP_GAP_MIN,
)
from mg_lever_press_fit_geom import (
    COLLAR_LENGTH,
    COLLAR_LENGTH_BAND,
    PRESS_FIT_BUDGET,
    PRESS_ZONE_DIA,
    PRESS_ZONE_DIA_BAND,
    PRESS_ZONE_LENGTH,
    PRESS_ZONE_LENGTH_BAND,
    check_press_fit_budget,
    press_fit_budget,
)

# Arm-to-flange inside corners (drawing-guidelines.md rule 16): the three
# concave edges where the arm leaves the flange's front (-Z) face are filleted
# AT the largest radius the print allows, a single MAX limit, so the shop may
# leave any smaller corner a Ø2 end mill cuts.  One place: rule 3, no extra
# places on a radius.  The build proves the fillet leaves the flange's front
# face a flat beside the arm on both sides.
ARM_ROOT_R_PLACES = 1
ARM_ROOT_R_MAX = 1.0
ARM_ROOT_R_BAND = (0.0, -ARM_ROOT_R_MAX)  # (upper, lower)
# swTolType_e.swTolMAX: a corner radius prints as one limit, "R1.0 MAX".
RADIUS_TOL_TYPE = 6

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The two extruded PLAN rectangles auto-import to the front view
# exactly like column_clamp_front's BlockProfile; the arm and flange chains are
# NAME-DISAMBIGUATED in the build (ArmWidth/ArmDepth vs FlangeWidth/FlangeDepth)
# because a shared bare "Width"/"Depth" would collide in the front view's keep
# map.  The arm's depth (its Z extent from a start buried inside the collar)
# stays unmarked: the arm's end is located from the bore axis instead
# (mreview09 blocker 3, two origins for the collar).  The collar's annulus
# sketch (Right plane) imports to the side view -- the OD and the press-seat
# bore, a reference nominal under its matched-fit callout -- and the mid-plane
# extrude's one dimension, the collar length with its band (COLLAR_LENGTH_BAND:
# the press contact is the collar's length less the lever's dome), to the
# front view.  The blanked
# ArmSection witness (Right plane) imports to the same side view: the arm's
# face nearest the bore axis (Y -3 versus the other face at Y +4.5,
# controlling ArmBelowAxis), the flange's mounting face
# from the bore axis and the arm's end past that face -- the ONE toleranced
# chain along Z (mreview10 blocker 2); its thickness and offset copies and
# its closing dimension (the flange above the arm) stay unmarked.  The
# blanked ArmFootprint witness (Front plane) imports to the BOTTOM view,
# where the arm's end face prints face-on inside the flange's outline: the
# arm's thickness and its lower face from the flange's hole-datum edge (both
# controlling: the arm face is the machinist's measurable datum for the
# holes' row, mreview10 blocker 1), toleranced where the footprint is seen,
# not edge-on.  The arm-to-flange inside corners' fillet radius (ArmRootFillet)
# imports to the front view, where the corner at the arm's west face prints
# as an arc. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarBore"},
    "Collar": {"CollarLen"},
    "ArmProfile": {"ArmWidth"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
    "ArmSection": {"ArmBelowAxis", "SeatToAxis", "ArmPastSeat"},
    "ArmFootprint": {"FootprintThickness", "FootprintOffset"},
    "ArmRootFillet": {"ArmRootR"},
}

# Wizard callout precision is applied in the build through observed native
# dimension names; those identifiers must never be renamed for this contract.
DRAWING_PRECISION = {
    "CollarProfile": {"CollarOd": 2, "CollarBore": 3},
    "Collar": {"CollarLen": 2},
    "ArmProfile": {"ArmWidth": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
    "ArmSection": {"ArmBelowAxis": 2, "SeatToAxis": 2, "ArmPastSeat": 2},
    "ArmFootprint": {"FootprintThickness": 2, "FootprintOffset": 2},
    "ArmRootFillet": {"ArmRootR": ARM_ROOT_R_PLACES},
}
# The pure SHEET-derived reference is SeatToAxis + ArmPastSeat (arm end).
# It reads actual model entities and prints in parentheses; its places remain
# spec-owned under drawing-simplicity-policy.md `How the repository implements the guidelines`.  FootprintOffset + ArmBelowAxis already
# locate the bore axis from the lower flange edge without a duplicate REF.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {
    "arm end from bore axis": 2,
}
# The collar's length band is read by the build straight from
# mg_lever_press_fit_geom (COLLAR_LENGTH_BAND) onto the extrude's CollarLen.
DRAWING_POSITION_BAND = POSITION_BAND

# Dimension callouts that state a manufacturing fact (the mate, the fit) are
# derived here from the fit contract, never typed on the sheet
# (_drawing_contract's spec-string rule).
#
# The bore is a matched fit to the finished MHA-MG-003 lever's press zone
# (drawing-guidelines.md rule 4, matched pairs): its nominal prints as a
# REFERENCE and the callout states the acceptance -- the fit budget's own
# diametral interference range.  The lever's press zone keeps its printed
# limits, so a pair made to the stated interference is one the budget bounds:
# at the tightest interference, on either limit of the lever's zone, the
# matched pair's press force and collar stress stay inside the budget the
# MHA-MG-000 assembly's press step is bounded by.
for _rod in (
    PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[1],
    PRESS_ZONE_DIA + PRESS_ZONE_DIA_BAND[0],
):
    _matched = press_fit_budget(
        press_zone_dia_band=(_rod - PRESS_ZONE_DIA, _rod - PRESS_ZONE_DIA),
        collar_bore_dia=_rod - PRESS_FIT_BUDGET["interference_max"],
        collar_bore_band=(0.0, 0.0),
    )
    check_press_fit_budget(_matched)
    for _key in ("press_force_max_n", "collar_von_mises_mpa", "engagement"):
        if _matched[_key] > PRESS_FIT_BUDGET[_key] * (1.0 + 1e-12):
            raise AssertionError(
                f"a matched collar bore exceeds the press budget's {_key}"
            )
# The bore runs through the collar (rule 12: the callout says what to do and
# how far), so the process row says THRU.
COLLAR_BORE_CALLOUT = (
    f"REAM OR BORE THRU: {PRESS_FIT_BUDGET['interference_min']:.3f}-"
    f"{PRESS_FIT_BUDGET['interference_max']:.3f}\n"
    "DIAMETRAL INTERFERENCE ON\n"
    "MHA-MG-003 LEVER"
)
# The collar's length band sets a stack: the lever's end sits flush with the
# collar's outer face, so the collar spans exactly the lever's banded press
# zone, and its length bounds the press contact (COLLAR_ENGAGEMENT_MAX, the
# press force).  The callout names that zone.
if (COLLAR_LENGTH, COLLAR_LENGTH_BAND) != (PRESS_ZONE_LENGTH, PRESS_ZONE_LENGTH_BAND):
    raise AssertionError(
        "the collar length must equal the lever's press zone, band and all"
    )
COLLAR_LENGTH_CALLOUT = "COLLAR LENGTH\nALONG BORE AXIS =\nMHA-MG-003 LEVER PRESS ZONE"

# The flange's thickness is the bracket screws' (MHA-VN-050) grip: it sets how
# far each screw reaches into the summing lever's blind #2-56 thread.  It
# prints three places so the title block's .XXX band (FLANGE_THICKNESS_BAND,
# ±0.13) holds the grip: worst-case engagement ENGAGEMENT_MIN 3.305 >= 1.5D
# 3.2766 and screw-tip gap SCREW_TIP_GAP_MIN 0.0075 > 0.  At .XX (±0.51) the
# thick flange would leave 2.925 engagement (< 1.5D) and the thin one would
# bottom the screws 0.3725 deep, so the third place is the function, named
# at the dimension (machinist review r2: a .XXX size with no stated job).
SCREW_NUMBER = _config.parts("vn-magnifying-bracket-screw")["number"]
_XX_GRIP_LOSS = LINEAR_BAND - GRIP_BAND
if GRIP_BAND != FLANGE_THICKNESS_BAND or not _XX_GRIP_LOSS > 0.0:
    raise AssertionError("the flange's .XXX band must be the screws' grip band")
if (
    ENGAGEMENT_MIN - _XX_GRIP_LOSS >= 1.5 * SCREW_MAJOR_DIA
    and SCREW_TIP_GAP_MIN - _XX_GRIP_LOSS > 0.0
):
    raise AssertionError("the flange depth no longer needs its third place")
FLANGE_DEPTH_CALLOUT = f"FLANGE DEPTH\n{SCREW_NUMBER}\nSCREW GRIP"

# No note block (drawing-guidelines.md rule 7): every requirement is a native
# dimension or a callout at its feature.  The press and its force limit are
# assembly steps, carried by the MHA-MG-000 assembly
# (mg_lever_press_fit_geom.PRESS_INSTALLATION_NOTES), not this part.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
