"""Native controls for the turned-and-threaded McMaster 91247A720 hanger stud."""

from __future__ import annotations

import knife_hanger_interface as joint
from diagnostics.diag_build_91247A720 import GB_LEN, GB_WASHER_T

# Stepped turned stud (user decision, 2026-09-22): the purchased 1/2 hex bolt
# keeps its head and Ø12.7 shank through the casting holes; a shoulder seats on
# the knife-mount top face (joint.SHOULDER_SEAT_Y) over a turned #10-24 tip.
# Every joint number comes from knife_hanger_interface, the knife mount's
# module; none is restated here.
STOCK_UNDERHEAD_MM = GB_LEN - GB_WASHER_T

# The shoulder's distance under the washer bearing face is the fit-to-stack
# reference L = T + W + G (MHA-A07 sheet 4): crossbar 36.5 + washer 2.4765 +
# mount gap 0.25 in the summing assembly. A literal here, so a top-frame or
# washer edit cannot re-key this part; test_knife_hanger_stud_drawing
# cross-checks it against those sources and the interface.
SHOULDER_UNDERHEAD_MM = 39.2265

# The tip: shoulder face to the faced end is the ONE engagement-critical
# length, banded by the interface. The tip is turned to the thread's major
# diameter and die-cut; its runout next to the shoulder is the interface's
# relief, so there is no groove.
TIP_THREAD = joint.THREAD
TIP_DIA_MM = joint.THREAD_MAJOR_DIA_MM
TIP_LENGTH_MM = joint.STUD_TIP_LENGTH_MM
TIP_LENGTH_DEVIATIONS_MM = joint.STUD_TIP_LENGTH_DEVIATIONS_MM
TIP_CHAMFER_MM = joint.STUD_TIP_CHAMFER_MAX_MM

# The purchased bolt is first cut to the faced end: bearing face to end.
FINISHED_UNDERHEAD_MM = SHOULDER_UNDERHEAD_MM + TIP_LENGTH_MM
TRIM_LENGTH_MM = STOCK_UNDERHEAD_MM - FINISHED_UNDERHEAD_MM
if not 0.0 < TRIM_LENGTH_MM < GB_LEN:
    raise ValueError("the turned stud must be cut from the purchased bolt")

# The interface bounds the tip chamfer from above only; at one place the title
# block would read .X +/-0.8 and let it grow past that limit, so it prints
# "0.5 MAX" (swTolType_e.swTolMAX) with its angle, which the part proves by
# equal radial and axial legs.
TIP_CHAMFER_TOLERANCE_TYPE = 6
TIP_CHAMFER_CALLOUT_SUFFIX = " X 45°"

DRAWING_DIMENSIONS = {"StudTurnProfile": {"TipLength", "TipChamfer"}}
# Decimal places carry the band (policy rule 2): the tip length prints its
# interface band's places, the chamfer and the stack reference one place.
DIMENSION_PRECISION = {"FinishedOverall": 1, "TipLength": 2, "TipChamfer": 1}
# Rule 2's one exception (see top_frame_spec): the (overall) length is a
# DRAWING reference between the drawn bearing face and the drawn faced end --
# the model FinishedOverall's legs are a datum point on the axis and a trim
# cutter corner -- so no model dimension carries its places.
DRAWING_REFERENCE_PRECISION = {
    "FinishedOverall": DIMENSION_PRECISION["FinishedOverall"]
}
DRAWING_NOTES = (
    "FIT SHOULDER TO STACK PER MHA-A07 SHEET 4, HANGER FIT + INSPECTION, DETAIL B.\n"
    "MARK EACH BOLT FRONT/REAR AND KEEP WITH ITS MHA-037/MHA-131 HANGER "
    "POSITION.\n"
    "UNDIMENSIONED PURCHASED HEAD/THREAD GEOMETRY IS REFERENCE.\n"
    "1/2-13 UNC THREAD PER McMASTER-CARR 91247A720."
)
ISOMETRIC_VIEW_NOTE = "ISO SCALE 1.5:1"
