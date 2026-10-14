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
  front ear's #8 clearance hole: the two ear stations' worst-case mismatch
  must stay inside that hole's radial float on the screw's major diameter.

The column is purchased 1 in DOM tube with no band in the repository
(``fr_tube_frame_spec.OUTER_DIA``), so the bores are MATCHED to the column
they clamp: each sheet prints its bore as a reference nominal with this
diametral-clearance acceptance on MHA-FR-003, never a free-standing size band
(drawing-guidelines.md rule 4, matched pairs).
"""

from __future__ import annotations

from _hole_spec import blind_cut_dia_mm
from fr_tube_frame_spec import OUTER_DIA as COLUMN_DIA
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
# The remainder is left for drill wander down the 15-17.9 deep ear holes.
SCREW_FLOAT = (blind_cut_dia_mm(EAR_HOLE_SPEC) - CLAMP_SCREW_MAJOR) / 2.0
EAR_STATION_MISMATCH_MAX = 2.0 * EAR_STATION_BAND
if EAR_STATION_MISMATCH_MAX >= SCREW_FLOAT:
    raise AssertionError(
        f"ear-station mismatch {EAR_STATION_MISMATCH_MAX:.3f} uses all of the "
        f"{SCREW_FLOAT:.3f} screw float"
    )

# Largest seated bore radius on a nominal column (the column's own size is the
# purchased tube's, matched by both bores).
BORE_RADIUS_MAX = (COLUMN_DIA + BORE_DIAMETRAL_CLEARANCE[1]) / 2.0
