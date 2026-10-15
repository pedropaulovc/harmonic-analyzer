r"""Column-clamp pair fit budget -- the limits the two arc sheets share.

PURE DATA over the two arcs' drawing-free geometry; no SolidWorks/COM and no
drawing imports.  The FRONT arc (MHA-SH-001) and the BACK arc (MHA-SH-002)
close on one Ø25.4 frame column (MHA-FR-003) with two #8-32 clamp screws:
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
(``fr_tube_frame_spec.OUTER_DIA``; MHA-FR-003 prints its OD as a reference
only), so the bores are MATCHED to the column they clamp: each sheet prints
its bore as a reference nominal with this diametral-clearance acceptance on
MHA-FR-003, never a free-standing size band (drawing-guidelines.md rule 4,
matched pairs).  The walls are judged on the largest bore that acceptance
admits on the largest tube A513 admits (``COLUMN_OD_MAX``).
"""

from __future__ import annotations

import math

from _hole_spec import blind_cut_dia_mm
from fr_tube_frame_spec import MM_PER_IN, OUTER_DIA as COLUMN_DIA
from sh_column_clamp_back_geom import GRIP_OFFSET
from sh_column_clamp_front_geom import COLUMN_BORE, EAR_HOLE_SPEC
from vn_clamp_screw_spec import SHANK_DIA as CLAMP_SCREW_MAJOR

COLUMN_MATE = "MHA-FR-003 COLUMN"

# (min, max) diametral clearance of EITHER arc's bore on its column. Centred
# on the model's own 0.2 (COLUMN_BORE on COLUMN_DIA); the 0.1 floor keeps the
# slide, the 0.3 ceiling is what the grip budget below can spend per bore.
BORE_DIAMETRAL_CLEARANCE = (0.10, 0.30)
# +/- on the back arc's mating-face offset from its bore axis.
GRIP_OFFSET_BAND = 0.1
# +/- on each ear-hole station from its arc's bore axis (both arcs).
EAR_STATION_BAND = 0.1
# +/- on each ear-hole height off its arc's bottom face (both arcs): the
# stations' fastener budget, so each tap's position zone is the same on both
# axes.
EAR_HEIGHT_BAND = 0.1

_MODEL_CLEARANCE = COLUMN_BORE - COLUMN_DIA
if not BORE_DIAMETRAL_CLEARANCE[0] < _MODEL_CLEARANCE < BORE_DIAMETRAL_CLEARANCE[1]:
    raise AssertionError(
        f"model bore clearance {_MODEL_CLEARANCE:.3f} lies outside the printed "
        f"acceptance {BORE_DIAMETRAL_CLEARANCE}"
    )

# Least face gap with both bores at their loosest and the offset at its least.
# Positive means the screws seat both bores before the faces meet.
GRIP_GAP_MIN = (GRIP_OFFSET - GRIP_OFFSET_BAND) - BORE_DIAMETRAL_CLEARANCE[1]
# Most face gap: the screw stack's extra length past the as-modelled 0.5.
GRIP_GAP_MAX = (GRIP_OFFSET + GRIP_OFFSET_BAND) - BORE_DIAMETRAL_CLEARANCE[0]
if GRIP_GAP_MIN <= 0.0:
    raise AssertionError(
        f"clamp faces close before the bores grip ({GRIP_GAP_MIN:.3f})"
    )

# Radial float of the screw major in the front ear's clearance hole (least
# hole: the DRILLED HOLES row's minus is 0), and what the two printed ear
# stations spend of it at worst (one arc's +band against the other's -band).
# The remainder (0.12 after the height mismatch below) is under the 0.18 the
# two ear holes' full-depth EAR_DRILL_WANDER_DEG can add: pending owner ruling
# with the walls (PR #1467 round-3 review).
SCREW_FLOAT = (blind_cut_dia_mm(EAR_HOLE_SPEC) - CLAMP_SCREW_MAJOR) / 2.0
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
BORE_RADIUS_MAX = (COLUMN_OD_MAX + BORE_DIAMETRAL_CLEARANCE[1]) / 2.0  # 12.9135

# drawing-guidelines.md rule 17 (walls and webs): realistic drill wander on
# the 15-18.4 deep ear holes, the repository's 0.3 deg angular allowance
# (fr_top_frame_spec.KEEPER_TAP_DRILL_WANDER_DEG), charged over each hole's
# full printed depth in every direction: the shop may enter from either face.
EAR_DRILL_WANDER_DEG = 0.3
EAR_DRILL_DRIFT_PER_MM = math.tan(math.radians(EAR_DRILL_WANDER_DEG))  # 0.00524

# drawing-guidelines.md rule 17: wall target and hard floor.
WALL_TARGET = 2.0
WALL_FLOOR = 1.5
