r"""Column-clamp pair fit budget -- the limits the two arc sheets share.

PURE DATA over the two arcs' drawing-free geometry; no SolidWorks/COM and no
drawing imports.  The FRONT arc (MHA-SH-01) and the BACK arc (MHA-SH-02)
close on one Ø25.4 frame column (MHA-FR-03) with two #8-32 clamp screws:
bar -> front arc (#8 clearance) -> back arc (tapped).  Three things must hold
at the printed worst case, and each sheet prints its share:

* **Grip.** The clamp grips only while the two mating faces stay apart with
  both half-bores seated on the column.  Seated, the front bore's axis sits
  ``c_front / 2`` short of the column's, the back's ``c_back / 2`` past it, so
  the face gap is ``GRIP_OFFSET - (c_front + c_back) / 2`` (the front's mating
  face is on its bore axis; the back's stops GRIP_OFFSET short of it).
* **Slide.** Each bore slips on the column to set the bar height before the
  screws are tightened (draw_pd_paper_drive_assembly step text), so each
  diametral clearance stays positive.
* **Screw line.** Each screw threads into the back ear and must pass the
  front ear's #8 clearance hole: the two ears' worst-case mismatch, station
  and height together, must stay inside that hole's radial float on the
  screw's major diameter.

The column is purchased 1 x .120 in ASTM A513 Type 5 (DOM) tube
(``fr_tube_frame_spec.OUTER_DIA``; MHA-FR-03 prints its OD as a reference
only), so the bores are MATCHED to the column they clamp: each sheet prints
its bore as a reference nominal with this diametral-clearance acceptance on
MHA-FR-03, never a free-standing size band (drawing-guidelines.md rule 4,
matched pairs).  The walls are judged on the largest bore that acceptance
admits on the largest tube A513 admits (``COLUMN_OD_MAX``).
"""

from __future__ import annotations

import math

import _config
from _hole_spec import blind_cut_dia_mm
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_deviations
from fr_tube_frame_spec import MM_PER_IN, OUTER_DIA as COLUMN_DIA
from sh_column_clamp_back_geom import BLOCK_DEPTH, GRIP_OFFSET
from _column_clamp_interface import ARC_DEPTH
from sh_column_clamp_front_geom import COLUMN_BORE, EAR_HOLE_SPEC
from sh_vn_clamp_screw_spec import SHANK_DIA as CLAMP_SCREW_MAJOR

# Both arc sheets print the front row's unit; the matched pair shares one.
UNIT = drawing_unit(
    "parts/sh-column-clamp-front", _config.parts("sh-column-clamp-front")
)
assert (
    drawing_unit("parts/sh-column-clamp-back", _config.parts("sh-column-clamp-back"))
    == UNIT
)

COLUMN_MATE = "MHA-FR-03 COLUMN"

# Owner rulings 2026-10-15 (PR #1467 round-3 review), drawing-guidelines.md
# rule 20, each a stated shortfall with no geometry change, declared as kind
# "minor" machinist_exceptions in the package's config YAML, restated in inch
# for #290 (rulings B2/B3, 2026-10-31):
# * the front arc's ear-to-bore web, .072 against the .080 wall target
#   (sh-column-clamp-front RV-01, sh_column_clamp_front_spec.EAR_WALL_NOTE);
# * the screw line, which can come up to 0.053 mm short of the front hole's
#   screw float once both ear holes' drill wander is added
#   (sh-column-clamp-front RV-02, SCREW_LINE_SHORTFALL below and
#   sh_column_clamp_front_spec.SCREW_LINE_NOTE).
# The back arc's back-wall shortfall (sh-column-clamp-back RV-01) retired: at
# the inch bands every back-arc wall meets the .080 target.

# Places a stated shortfall prints at, in inch (the sheets' .XXX class).
NOTE_PLACES = 3


def stated_min(value: float) -> float:
    """A minimum (mm) as the sheet states it in inch: rounded DOWN, never
    overstated."""
    scale = 10**NOTE_PLACES
    return math.floor(value / MM_PER_IN * scale + 1e-9) / scale


def stated_max(value: float) -> float:
    """A maximum (mm) as the sheet states it in inch: rounded UP, never
    understated."""
    scale = 10**NOTE_PLACES
    return math.ceil(value / MM_PER_IN * scale - 1e-9) / scale


def note_text(value_in: float) -> str:
    """A stated inch value as the sheet prints it: ``.072``."""
    text = f"{value_in:.{NOTE_PLACES}f}"
    return text[1:] if text.startswith("0.") else text


# The front arc's Depth prints .685 at three places (it sets the clamp screws'
# engagement, and .685 is off the .01 grid); the back arc's .59 Depth prints
# the title block's .XX, the back wall and the tap's wander taking its +/-.01.
# Both arcs' Hole Wizard callouts print their drill diameters at three places
# (the front's Ø.196, the back's .136).
FRONT_DEPTH_PLACES = 3
BACK_DEPTH_PLACES = 2
EAR_HOLE_CALLOUT_PLACES = 3

# (min, max) diametral clearance of EITHER arc's bore on its column,
# .004-.012 in. The model's own .008 (COLUMN_BORE on COLUMN_DIA) sits inside;
# the .004 floor keeps the slide, the .012 ceiling is what the grip budget
# below can spend per bore.
BORE_DIAMETRAL_CLEARANCE = (0.1016, 0.3048)
# The acceptance as both sheets' bore callouts print it: ".004-.012".
BORE_CLEARANCE_TEXT = "-".join(
    note_text(limit / MM_PER_IN) for limit in BORE_DIAMETRAL_CLEARANCE
)
# +/- on the back arc's mating-face offset from its bore axis, .004.
GRIP_OFFSET_BAND = 0.1016
# +/- on each ear-hole station from its arc's bore axis (both arcs), .004.
EAR_STATION_BAND = 0.1016
# +/- on each ear-hole height off its arc's bottom face (both arcs), .004: the
# stations' fastener budget, so each tap's position zone is the same on both
# axes.
EAR_HEIGHT_BAND = 0.1016

_MODEL_CLEARANCE = COLUMN_BORE - COLUMN_DIA
if not BORE_DIAMETRAL_CLEARANCE[0] < _MODEL_CLEARANCE < BORE_DIAMETRAL_CLEARANCE[1]:
    raise AssertionError(
        f"model bore clearance {_MODEL_CLEARANCE:.3f} lies outside the printed "
        f"acceptance {BORE_DIAMETRAL_CLEARANCE}"
    )

# Least face gap with both bores at their loosest and the offset at its least.
# Positive means the screws seat both bores before the faces meet.
GRIP_GAP_MIN = (GRIP_OFFSET - GRIP_OFFSET_BAND) - BORE_DIAMETRAL_CLEARANCE[1]
# Most face gap: the screw stack's extra length past the as-modelled .020.
GRIP_GAP_MAX = (GRIP_OFFSET + GRIP_OFFSET_BAND) - BORE_DIAMETRAL_CLEARANCE[0]
if GRIP_GAP_MIN <= 0.0:
    raise AssertionError(
        f"clamp faces close before the bores grip ({GRIP_GAP_MIN:.3f})"
    )

# Radial float of the screw major in the front ear's clearance hole (the least
# printed hole, Ø.196: the DRILLED HOLES row's minus is 0), and what the two
# printed ear stations spend of it at worst (one arc's +band against the
# other's -band).  The ears' drill wander is charged on top in
# SCREW_LINE_DEMAND below.
_EAR_HOLE_DIA = blind_cut_dia_mm(EAR_HOLE_SPEC)
_EAR_HOLE_DEV = printed_deviations(
    _EAR_HOLE_DIA, EAR_HOLE_CALLOUT_PLACES, (0.0, 0.0), unit=UNIT
)
EAR_HOLE_DIA_MIN = _EAR_HOLE_DIA + _EAR_HOLE_DEV[0]
SCREW_FLOAT = (EAR_HOLE_DIA_MIN - CLAMP_SCREW_MAJOR) / 2.0  # 0.4064 (.016)
EAR_STATION_MISMATCH_MAX = 2.0 * EAR_STATION_BAND
if EAR_STATION_MISMATCH_MAX >= SCREW_FLOAT:
    raise AssertionError(
        f"ear-station mismatch {EAR_STATION_MISMATCH_MAX:.3f} uses all of the "
        f"{SCREW_FLOAT:.3f} screw float"
    )

# Across the bar's height the arcs' bottom faces need not meet -- each slides
# on the column -- but both screws share that one sliding offset, so a screw
# sees at worst half the two arcs' ear-to-ear height spreads (2 bands each)
# set against each other.  The station and height mismatches are square to
# each other, so a screw spends their resultant of the float.
EAR_HEIGHT_MISMATCH_MAX = (2.0 * EAR_HEIGHT_BAND + 2.0 * EAR_HEIGHT_BAND) / 2.0
EAR_SCREW_MISMATCH_MAX = math.hypot(EAR_STATION_MISMATCH_MAX, EAR_HEIGHT_MISMATCH_MAX)
if EAR_SCREW_MISMATCH_MAX >= SCREW_FLOAT:
    raise AssertionError(
        f"ear-hole mismatch {EAR_SCREW_MISMATCH_MAX:.3f} uses all of the "
        f"{SCREW_FLOAT:.3f} screw float"
    )

# The largest incoming column: ASTM A513 round tubing, Types 5/6 (DOM), OD
# 0.500-1.699 in: +0.005 / -0.000 in.  At a .120 wall (12 % of OD, over the
# table's 3 % threshold) the ovality lies inside that band, so no diameter of
# the tube exceeds it.  Read 2026-10-15 from the A513 table as republished by
# Boyer Steel (https://www.boyersteel.com/resource-astm-specifications/a513-t-5-d-o-m/)
# and Amardeep Steel (https://www.amardeepsteel.com/a513-dom-tubing.html);
# the material row is cad/config/parts/fr-tube-frame.yaml.
COLUMN_OD_PLUS_IN = 0.005
COLUMN_OD_MAX = COLUMN_DIA + COLUMN_OD_PLUS_IN * MM_PER_IN  # 25.527
# Largest seated bore radius: the largest column's bore at the loosest
# accepted clearance.
BORE_RADIUS_MAX = (COLUMN_OD_MAX + BORE_DIAMETRAL_CLEARANCE[1]) / 2.0  # 12.9159

# drawing-guidelines.md rule 17 (walls and webs): realistic drill wander on
# the .59-.69 deep ear holes, the repository's 0.3 deg angular allowance
# (fr_top_frame_spec.KEEPER_TAP_DRILL_WANDER_DEG), charged over each hole's
# full printed depth in every direction: the shop may enter from either face.
EAR_DRILL_WANDER_DEG = 0.3
EAR_DRILL_DRIFT_PER_MM = math.tan(math.radians(EAR_DRILL_WANDER_DEG))  # 0.00524
# Each ear hole runs through its arc: the front's clearance hole over the
# arc's deepest printed Depth, the back's tap over the block's.
FRONT_EAR_WANDER = EAR_DRILL_DRIFT_PER_MM * (
    ARC_DEPTH + printed_deviations(ARC_DEPTH, FRONT_DEPTH_PLACES, unit=UNIT)[1]
)  # 0.0918
BACK_EAR_WANDER = EAR_DRILL_DRIFT_PER_MM * (
    BLOCK_DEPTH + printed_deviations(BLOCK_DEPTH, BACK_DEPTH_PLACES, unit=UNIT)[1]
)  # 0.0798

# The screw line at its worst: the printed ear mismatch plus both holes'
# wander, in any direction, against the front hole's float.  Owner-ruled
# short (above, sh-column-clamp-front RV-02) at up to 0.053 mm: ruled on the
# 17.9 mm arc as 0.283 + 0.096 + 0.081 = 0.460 against 0.407.  At the inch
# bands (+/-.004 on the ear stations and heights, the front Depth at .XXX and
# the back's at .XX) it is 0.2874 + 0.0918 + 0.0798 = 0.4590 against 0.4064,
# i.e. 0.0525 mm; the front sheet states it as .003 at its three places
# (rounded up).  The floor still holds -- the printed bands alone never bind
# the screw (EAR_SCREW_MISMATCH_MAX < SCREW_FLOAT above) -- and the shortfall
# may not grow past the ruled value.
SCREW_LINE_DEMAND = EAR_SCREW_MISMATCH_MAX + FRONT_EAR_WANDER + BACK_EAR_WANDER
SCREW_LINE_SHORTFALL = SCREW_LINE_DEMAND - SCREW_FLOAT  # 0.0525
SCREW_LINE_SHORTFALL_RULED = 0.053
if not 0.0 < round(SCREW_LINE_SHORTFALL, 3) <= SCREW_LINE_SHORTFALL_RULED:
    raise AssertionError(
        f"screw-line shortfall {SCREW_LINE_SHORTFALL:.4f} is not the owner-ruled "
        f"(0, {SCREW_LINE_SHORTFALL_RULED}]"
    )

# drawing-guidelines.md rule 17: wall target (.080) and hard floor (.060).
WALL_TARGET = WALL_TARGET_MM
WALL_FLOOR = WALL_FLOOR_MM
