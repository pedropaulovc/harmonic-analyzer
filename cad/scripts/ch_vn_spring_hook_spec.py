"""Manufacturing controls for the modified McMaster 9489T111 anchor.

The anchor threads down through the summing lever's coefficient plate and is
locked by the MHA-CH-14 round jam nut run up its cut end and jammed against
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
is the uniform coefficient-plate thickness): backing out only lifts the neck
off the plate top, it no longer trades engagement for eye lift.

The fitter holds the eye at its clocking while the nut is tightened, so the
trim survives the lock; re-trimming means slackening the nut first.  The
step text the top-level assembly prints is ``ANCHOR_INSTALL_STEP``.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  The two
shop controls (the finished overall and the restored deburr) are authored as
the exact millimetre decimals of their printed inch values; the eye, thread
and as-supplied sizes are the vendor's, unchanged.
"""

import math

import _config
import sm_summing_lever_spec
import ch_anchor_jam_nut_spec as jam_nut
from _hole_spec import blind_cut_dia_mm
from _package_units import drawing_unit
from _printed_tolerance import angular_band_deg, printed_band_mm
from stock_anchor_geom import ANCHOR_9489T111, trim
from _supplier_screw_reference_names import FEATURE_BY_PLANE

UNIT = drawing_unit("parts/ch-vn-spring-hook", _config.parts("ch-vn-spring-hook"))
# The coefficient plate's thickness band is the lever's own printed .XX row.
_LEVER_UNIT = drawing_unit("parts/sm-summing-lever", _config.parts("sm-summing-lever"))

_PITCH = ANCHOR_9489T111.thread_pitch_mm

# The tap is engaged over the whole coefficient-plate thickness at every
# calibration pose.
THREAD_ENGAGEMENT_MM = sm_summing_lever_spec.COEFFICIENT_T
# The lever's 7.00 prints under the title block's .XX band, so its underside
# moves the jam-nut seat (code review C10: sizing at nominal thickness left
# only 1.09 of full thread past the nut at the thickest limit, under the
# 1.5875 floor). The trim is sized at the thickest plate; the cut end hangs
# deepest under the thinnest.
SEAT_BAND_MM = printed_band_mm(2, unit=_LEVER_UNIT)
SEAT_T_MAX_MM = THREAD_ENGAGEMENT_MM + SEAT_BAND_MM
SEAT_T_MIN_MM = THREAD_ENGAGEMENT_MM - SEAT_BAND_MM
# The finished overall is a functional length (the past-nut budget reads its
# band), so it prints .XX, never the .X row.
OVERALL_PLACES = 2
FINISHED_OVERALL_TOLERANCE_MM = printed_band_mm(OVERALL_PLACES, unit=UNIT)
# Owner ruling (C10): one more step of the printed overall's grid (.01) as
# thread over the floor at that worst corner.
PAST_NUT_MARGIN_MM = 0.254  # .01
# The restored factory deburr (0.4557) on the .XXX grid.
CHAMFER_WIDTH_MM = 0.4572  # .018
# At the short chamfer limit the cut end's flat (major radius - chamfer) must
# still pass the #6-32 tap drill it enters, which allows .0022 below the
# .018 nominal -- so the deburr is a 3-place control, not the title block's.
CHAMFER_WIDTH_TOLERANCE_MM = 0.0508  # .002
MIN_CHAMFER_WIDTH_MM = (
    ANCHOR_9489T111.thread_major_dia_mm - blind_cut_dia_mm(sm_summing_lever_spec.HOLE_SPEC)
) / 2.0
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = angular_band_deg(unit=UNIT)
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
# The band the fitter reads on the printed overall.
LENGTH_BAND_WORST_MM = FINISHED_OVERALL_TOLERANCE_MM
# Cut end below the thread start (= plate top when seated), nominal part,
# seated: the thickest plate, thickest nut, two full turns and the ruled
# margin, the deburr, then the back-out budget and the band the shortest
# in-band part may give up.
_END_BELOW_THREAD_START_MM = (
    SEAT_T_MAX_MM
    + jam_nut.THICKNESS_MAX
    + FULL_THREADS_PAST_NUT * _PITCH
    + PAST_NUT_MARGIN_MM
    + CHAMFER_AXIAL_MAX_MM
    + ADJUSTMENT_TRAVEL_MM
    + LENGTH_BAND_WORST_MM
)
_SHANK_REQUIRED_MM = (
    ANCHOR_9489T111.unthreaded_shank_length_mm + _END_BELOW_THREAD_START_MM
)
# The overall prints at two inch places, so it is rounded UP to the .01 grid:
# the printed number is the model's, and rounding never eats the thread.
_OVERALL_REQUIRED_MM = ANCHOR_9489T111.eye_od_mm / 2 - trim(
    ANCHOR_9489T111, _SHANK_REQUIRED_MM
).shank_end_y_mm
_OVERALL_IN = math.ceil(round(_OVERALL_REQUIRED_MM / 25.4 * 100.0, 6)) / 100.0
SHANK_LENGTH_MM = round(
    _SHANK_REQUIRED_MM + _OVERALL_IN * 25.4 - _OVERALL_REQUIRED_MM, 6
)
TRIM = trim(ANCHOR_9489T111, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = round(ANCHOR_9489T111.eye_od_mm / 2 - TRIM.shank_end_y_mm, 6)
# The modelled, seated cut end below the nominal plate underside.
PROTRUSION_MM = (
    SHANK_LENGTH_MM - ANCHOR_9489T111.unthreaded_shank_length_mm - THREAD_ENGAGEMENT_MM
)
# Deepest the cut end can hang below the plate underside: the longest part,
# seated under the thinnest in-band plate. The band's upper half stops at the
# uncut 9489T111 shank, the longest part the stock can give. The
# under-plate envelope (lever ribs, magnifier bracket flange) is checked
# against this and the nut.
PROTRUSION_MAX_MM = (
    min(SHANK_LENGTH_MM + LENGTH_BAND_WORST_MM, ANCHOR_9489T111.shank_length_mm)
    - ANCHOR_9489T111.unthreaded_shank_length_mm
    - SEAT_T_MIN_MM
)


def full_threads_past_nut_mm(
    backed_out_mm: float, band_mm: float, seat_t_mm: float = SEAT_T_MAX_MM
) -> float:
    """Full-form thread below the thickest in-band nut for a part ``band_mm``
    off nominal (negative = short), backed out ``backed_out_mm`` from the
    seated neck, through a plate ``seat_t_mm`` thick (default: the thickest
    in-band plate)."""
    end_below_thread_start = (
        SHANK_LENGTH_MM
        + band_mm
        - ANCHOR_9489T111.unthreaded_shank_length_mm
        - backed_out_mm
    )
    return (
        end_below_thread_start
        - seat_t_mm
        - jam_nut.THICKNESS_MAX
        - CHAMFER_AXIAL_MAX_MM
    )


# Two full pitches (1.5875 mm) below the thickest nut at the worst case,
# plus the ruled margin.
PAST_NUT_FLOOR_MM = FULL_THREADS_PAST_NUT * _PITCH
if (
    full_threads_past_nut_mm(ADJUSTMENT_TRAVEL_MM, -LENGTH_BAND_WORST_MM)
    < PAST_NUT_FLOOR_MM + PAST_NUT_MARGIN_MM - 1e-9
):
    raise ValueError("the shortest in-band anchor loses its threads past the nut")
# The cut shank must come out of the purchased 9489T111: the coefficient-plate
# tap length sets how much of it the anchor needs.
if SHANK_LENGTH_MM >= ANCHOR_9489T111.shank_length_mm:
    raise ValueError("the anchor's cut shank no longer fits the 9489T111 stock")

DRAWING_DIMENSIONS = {
    "StockTrimProfile": {"FinishedOverall"},
    "StockDeburrProfile": {"ChamferWidth", "ChamferAngle"},
}
DIMENSION_PRECISION = {
    "FinishedOverall": OVERALL_PLACES,
    "ChamferWidth": 3,
    "ChamferAngle": 0,
}
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

# McMaster 9489T111 engineering drawing (2026-04-08):
# https://www.mcmaster.com/mvC/Library/CAD2/20260408/6323B365/9489T111_Routing%20Eyebolt%20with%20Nut%20-%20Not%20for%20LiftingX.GIF
# Eye contours survive the trim. Original source lengths belong only to the
# as-supplied bolt-body configuration; wire diameter is not a source size.
SUPPLIER_EYE_MM = {
    "EyeOD": ANCHOR_9489T111.eye_od_mm,
    "EyeID": ANCHOR_9489T111.eye_id_mm,
}
SUPPLIER_REFERENCE_PRECISION = {
    "EyeOD": 1, "EyeID": 2,
    "SupplierStockShank": 2, "SupplierStockThread": 3, "SupplierStockOverall": 2,
    "SupplierThreadMajor": 3,
}
SUPPLIER_STOCK_CONFIGURATION = "AsSuppliedStock"
SUPPLIER_STOCK_FEATURE = "SupplierStockAxis"
SUPPLIER_STOCK_AXIS_MM = (
    (0.0, ANCHOR_9489T111.eye_od_mm / 2.0),
    (0.0, ANCHOR_9489T111.advertised_shank_start_y_mm),
    (0.0, ANCHOR_9489T111.thread_start_y_mm),
    (0.0, ANCHOR_9489T111.shank_end_y_mm),
)
SUPPLIER_STOCK_MM = {
    "SupplierStockShank": ANCHOR_9489T111.shank_length_mm,
    "SupplierStockThread": ANCHOR_9489T111.thread_length_mm,
    "SupplierStockOverall": ANCHOR_9489T111.overall_length_mm,
}
SUPPLIER_STOCK_DIMENSIONS = {SUPPLIER_STOCK_FEATURE: set(SUPPLIER_STOCK_MM)}
SUPPLIER_THREAD = ANCHOR_9489T111.thread_size
SUPPLIER_THREAD_MAJOR_MM = ANCHOR_9489T111.thread_major_dia_mm
SUPPLIER_THREAD_FEATURE = FEATURE_BY_PLANE["Front"]
SUPPLIER_THREAD_DIMENSIONS = {SUPPLIER_THREAD_FEATURE: {"SupplierThreadMajor"}}
SUPPLIER_THREAD_START_MM = (
    -SUPPLIER_THREAD_MAJOR_MM / 2.0,
    (ANCHOR_9489T111.thread_start_y_mm + TRIM.shank_end_y_mm) / 2.0,
)
# Saved hidden; reference views explicitly reveal only the owner they dimension.
REFERENCE_SKETCHES = (SUPPLIER_STOCK_FEATURE, SUPPLIER_THREAD_FEATURE)

_ANCHOR_NUMBER = _config.parts("ch-vn-spring-hook")["number"]
_LEVER_NUMBER = _config.parts("sm-summing-lever")["number"]
# The top-level (MHA-HA-00) step that installs and locks the 20 anchors,
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
