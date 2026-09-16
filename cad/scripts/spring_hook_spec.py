"""Manufacturing controls for the modified McMaster 9489T111 anchor.

The anchor threads into the summing lever's coefficient plate and must STOP
inside it: the plate's underside is the channel bank's working space, so a
stock 19.05 mm shank hangs 10.795 mm into it.

Two facts set the finished length.  The anchor's Ø3.175 unthreaded neck cannot
enter a #6-32 tap, so the neck shoulders on the plate's TOP face -- that is the
hard down-stop, and the installed thread therefore starts at the plate top.
Per-channel calibration then unscrews the anchor to raise the eye, which lifts
the cut end further inside the hole.  So the finished shank is the neck plus
the engaged depth, cut ``PLATE_RECESS_MM`` short of the underside: the end
never projects, and the recess is free adjustment room under any pose.

The remaining engagement (``THREAD_ENGAGEMENT_MM``) is ~4.4 threads of #6-32
against a 4.49 N spring, so the band is the title block's general 1-place row
(as on the counter anchor, ``boss_hook_spec``): even at the long limit the end
stays 0.8 mm inside the plate, and at the short limit >2 threads remain.
"""

import _config
import summing_lever_spec
from _hole_spec import blind_cut_dia_mm
from stock_anchor_geom import ANCHOR_9489T111, trim

# 1/16 in of adjustment room between the cut end and the plate's underside.
PLATE_RECESS_MM = 25.4 / 16.0
THREAD_ENGAGEMENT_MM = summing_lever_spec.PLATE_T - PLATE_RECESS_MM
SHANK_LENGTH_MM = round(
    ANCHOR_9489T111.unthreaded_shank_length_mm + THREAD_ENGAGEMENT_MM, 4
)
TRIM = trim(ANCHOR_9489T111, SHANK_LENGTH_MM)
FINISHED_OVERALL_MM = ANCHOR_9489T111.eye_od_mm / 2 - TRIM.shank_end_y_mm
FINISHED_OVERALL_TOLERANCE_MM = _config.title_block("linear_1pl")["value_in"] * 25.4
CHAMFER_WIDTH_MM = ANCHOR_9489T111.end_chamfer_mm
# At the short chamfer limit the cut end's flat (major radius - chamfer) must
# still pass the #6-32 tap drill it enters, which allows 0.0556 mm below the
# factory 0.455676 -- so the deburr is a 2-place control, not a 0.25 band.
CHAMFER_WIDTH_TOLERANCE_MM = 0.05
MIN_CHAMFER_WIDTH_MM = (
    ANCHOR_9489T111.thread_major_dia_mm - blind_cut_dia_mm(summing_lever_spec.HOLE_SPEC)
) / 2.0
CHAMFER_ANGLE_DEG = 45.0
CHAMFER_ANGLE_TOLERANCE_DEG = _config.title_block("angular")["value_deg"]

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
DRAWING_NOTES = (
    "FINISHED OVERALL TO EYE CROWN IS THE ACCEPTANCE SIZE;\n"
    "THE CUT END SEATS INSIDE THE SUMMING LEVER PLATE AND MUST NOT PROJECT.\n"
    "DISCARD THE SUPPLIED HEX NUT; NO NUT IS INSTALLED.\n"
    "UNDIMENSIONED PURCHASED GEOMETRY IS REFERENCE."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 3:1"
