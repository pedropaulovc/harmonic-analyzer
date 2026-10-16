"""Manufacturing controls for the modified McMaster 9489T111 anchor.

The anchor threads down through the summing lever's coefficient plate and is
locked by the MHA-CH-014 round jam nut run up its cut end and jammed against
the plate's underside (rule 23: the anchor rides the rocking lever under a
cycling spring, and per-channel calibration turns it, so a seated thread
alone is not a lock).

Two facts set the finished length.  The anchor's Ø3.175 unthreaded neck
cannot enter a #6-32 tap, so the neck shoulders on the plate's TOP face --
the hard down-stop, where the installed thread starts.  Per-channel
calibration then backs the anchor out up to ``ADJUSTMENT_TURNS`` counted
turns (``ADJUSTMENT_TRAVEL_MM``) to trim the spring preload -- one turn is
worth 0.139 N of the 2.71 N installed load, 5% of preload -- which lifts the
cut end.  So the shank must cross the plate, carry the nut, and still show
``FULL_THREADS_PAST_NUT`` full turns below the nut at the worst case: the
shortest in-band anchor (title-block 1-place band) under the thickest in-band
nut, its deburr at the adverse corner of its band, backed out the whole
budget.

The tap is engaged over its whole length at every pose (``THREAD_ENGAGEMENT_MM``
is the plate plus its underside spring pad): backing out only lifts the neck
off the plate top, it no longer trades engagement for eye lift.

The fitter holds the eye at its clocking while the nut is tightened, so the
trim survives the lock; re-trimming means slackening the nut first.  The
step text the top-level assembly prints is ``ANCHOR_INSTALL_STEP``.
"""

import math

import _config
import sm_summing_lever_spec
import ch_anchor_jam_nut_spec as jam_nut
from _hole_spec import blind_cut_dia_mm
from _printed_tolerance import printed_band_mm
from stock_anchor_geom import ANCHOR_9489T111, trim

_PITCH = ANCHOR_9489T111.thread_pitch_mm

# The tap is engaged over its whole length (plate plus underside pad) at
# every calibration pose.
THREAD_ENGAGEMENT_MM = sm_summing_lever_spec.SPRING_SEAT_T
FINISHED_OVERALL_TOLERANCE_MM = _config.title_block("linear_1pl")["value_in"] * 25.4
CHAMFER_WIDTH_MM = ANCHOR_9489T111.end_chamfer_mm
# At the short chamfer limit the cut end's flat (major radius - chamfer) must
# still pass the #6-32 tap drill it enters, which allows 0.0556 mm below the
# factory 0.455676 -- so the deburr is a 2-place control, not a 0.25 band.
CHAMFER_WIDTH_TOLERANCE_MM = 0.05
MIN_CHAMFER_WIDTH_MM = (
    ANCHOR_9489T111.thread_major_dia_mm - blind_cut_dia_mm(sm_summing_lever_spec.HOLE_SPEC)
) / 2.0
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]
# The deburr's longest axial run: widest leg at the steepest in-band angle.
CHAMFER_AXIAL_MAX_MM = (CHAMFER_WIDTH_MM + CHAMFER_WIDTH_TOLERANCE_MM) / math.tan(
    math.radians(CHAMFER_ANGLE_DEG - CHAMFER_ANGLE_TOLERANCE_DEG)
)

# A fitter counts whole turns; one turn of back-out is the calibration budget.
ADJUSTMENT_TURNS = 1
ADJUSTMENT_TRAVEL_MM = ADJUSTMENT_TURNS * _PITCH
# Full-form thread showing below the jam nut at the worst case, so the nut's
# last thread is never on the deburr.
FULL_THREADS_PAST_NUT = 2
# The fitter reads the printed .X band (+/-0.8), a hair wider than the
# title block's 0.03 in the tolerance itself carries: size to the wider.
LENGTH_BAND_WORST_MM = max(FINISHED_OVERALL_TOLERANCE_MM, printed_band_mm(1))
# Cut end below the thread start (= plate top when seated), nominal part,
# seated: plate, thickest nut, two full turns, the deburr, then the back-out
# budget and the band the shortest in-band part may give up.
_END_BELOW_THREAD_START_MM = (
    THREAD_ENGAGEMENT_MM
    + jam_nut.THICKNESS_MAX
    + FULL_THREADS_PAST_NUT * _PITCH
    + CHAMFER_AXIAL_MAX_MM
    + ADJUSTMENT_TRAVEL_MM
    + LENGTH_BAND_WORST_MM
)
_SHANK_REQUIRED_MM = (
    ANCHOR_9489T111.unthreaded_shank_length_mm + _END_BELOW_THREAD_START_MM
)
# The overall prints at one place, so it is rounded UP to the 0.1 grid: the
# printed number is the model's, and rounding never eats the thread.
_OVERALL_REQUIRED_MM = ANCHOR_9489T111.eye_od_mm / 2 - trim(
    ANCHOR_9489T111, _SHANK_REQUIRED_MM
).shank_end_y_mm
SHANK_LENGTH_MM = round(
    _SHANK_REQUIRED_MM
    + math.ceil(round(_OVERALL_REQUIRED_MM * 10.0, 6)) / 10.0
    - _OVERALL_REQUIRED_MM,
    6,
)
TRIM = trim(ANCHOR_9489T111, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = round(ANCHOR_9489T111.eye_od_mm / 2 - TRIM.shank_end_y_mm, 6)
# Deepest the cut end can hang below the plate underside: the longest in-band
# part, seated.  The under-plate envelope (lever ribs, magnifier bracket
# flange) is checked against this and the nut.
PROTRUSION_MAX_MM = (
    SHANK_LENGTH_MM
    + LENGTH_BAND_WORST_MM
    - ANCHOR_9489T111.unthreaded_shank_length_mm
    - THREAD_ENGAGEMENT_MM
)


def full_threads_past_nut_mm(backed_out_mm: float, band_mm: float) -> float:
    """Full-form thread below the thickest in-band nut for a part ``band_mm``
    off nominal (negative = short), backed out ``backed_out_mm`` from the
    seated neck."""
    end_below_thread_start = (
        SHANK_LENGTH_MM
        + band_mm
        - ANCHOR_9489T111.unthreaded_shank_length_mm
        - backed_out_mm
    )
    return (
        end_below_thread_start
        - THREAD_ENGAGEMENT_MM
        - jam_nut.THICKNESS_MAX
        - CHAMFER_AXIAL_MAX_MM
    )


# Two full pitches (1.5875 mm) below the thickest nut at the worst case.
PAST_NUT_FLOOR_MM = FULL_THREADS_PAST_NUT * _PITCH
if (
    full_threads_past_nut_mm(ADJUSTMENT_TRAVEL_MM, -LENGTH_BAND_WORST_MM)
    < PAST_NUT_FLOOR_MM - 1e-9
):
    raise ValueError("the shortest in-band anchor loses its threads past the nut")
# The cut shank must come out of the purchased 9489T111: the lever's padded
# tap length sets how much of it the anchor needs.
if SHANK_LENGTH_MM >= ANCHOR_9489T111.shank_length_mm:
    raise ValueError("the anchor's cut shank no longer fits the 9489T111 stock")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DIMENSION_PRECISION = {"FinishedOverall": 1, "ChamferWidth": 2, "ChamferAngle": 0}
# The overall length and the 45 deg leg defer to the title block (swTolGeneral);
# the deburr width prints its own symmetric band.
DIMENSION_TOLERANCE_TYPES = {
    "FinishedOverall": 11,
    "ChamferWidth": 4,
    "ChamferAngle": 11,
}
_NUT_NUMBER = _config.parts("ch-anchor-jam-nut")["number"]
DRAWING_NOTES = (
    "FINISHED OVERALL TO EYE CROWN IS THE ACCEPTANCE SIZE.\n"
    f"DISCARD THE SUPPLIED HEX NUT; {_NUT_NUMBER} LOCKS THIS ANCHOR.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 3:1"

_ANCHOR_NUMBER = _config.parts("vn-spring-hook")["number"]
_LEVER_NUMBER = _config.parts("sm-summing-lever")["number"]
# The top-level (MHA-HA-000) step that installs and locks the 20 anchors,
# without its step number; ANCHOR_INSTALL_CHECK is its acceptance.
ANCHOR_INSTALL_STEP = (
    f"THREAD EACH {_ANCHOR_NUMBER} DOWN INTO ITS {_LEVER_NUMBER} PLATE TAP UNTIL "
    f"THE NECK SEATS ON THE PLATE TOP. TO SET THE CHANNEL PRELOAD, BACK IT OUT "
    f"NO MORE THAN {ADJUSTMENT_TURNS} TURN, FINISHING WITH THE EYE OPENING IN "
    f"THE SPRING PULL PLANE. HOLDING THE EYE THERE, RUN ONE {_NUT_NUMBER} UP "
    "THE SHANK WITH A SHOP-MADE FORKED DRIVER AND JAM IT AGAINST THE PLATE "
    "UNDERSIDE."
)
ANCHOR_INSTALL_CHECK = (
    f"EVERY {_ANCHOR_NUMBER} EYE STANDS IN ITS SPRING PULL PLANE AND CANNOT BE "
    f"TURNED BY HAND; ITS {_NUT_NUMBER} IS TIGHT ON THE PLATE UNDERSIDE WITH "
    "FULL THREAD SHOWING BELOW IT."
)
