"""Pure 93585A190 vendor dimensions; keep mechanical specs off recipe closures."""

import math

# --- Sketch1 driving dimensions (mm) -----------------------------------------
MAJOR_R = 3.175  # Thread Size 6.35 / 2
PITCH = 1.27
LENGTH = 19.05  # stud under the head
HEAD_R = 7.9375  # Head Diameter 15.875 / 2, over the knurl crests
HEAD_H = 12.7
RIM_CHAMFER = 0.79375  # Sketch37 45-deg rim triangle leg

# --- vendor equations ---------------------------------------------------------
TIP_CHAMFER = PITCH * 0.75  # D1@Chamfer2
CORE_R = HEAD_R * 0.98  # D1@Sketch21 = HD * .98
BAND_H = HEAD_H * 0.05  # D4@Sketch1 = HH * .05 (bands, Chamfer3/4)
KNURL_COUNT = 131  # D1@CirPattern1 = HD[in] * 3.14 / .015
KNURL_CREST_W = 0.127  # D3@Sketch26
KNURL_FLANK_DEG = 20.0  # D1@Sketch26 = D2@Sketch26
RUNOUT_DEPTH = 2.54  # Boss-Extrude7 dir1
RUNOUT_DRAFT_DEG = 45.0

H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_R - 0.75 * H_SHARP  # 2.350111
