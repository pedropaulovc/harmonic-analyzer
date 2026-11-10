"""Pure 91794A558 fillister dimensions; isolate each SKU's cache inputs.

McMaster-Carr 91794A558, 18-8 stainless fillister head slotted screw,
1/4"-28 x 5/8": the stock of MHA-DT-39, the cone tip end screw.  The product
page, read live 2026-11-09 (https://www.mcmaster.com/91794A558/), states:
thread 1/4"-28 UNF, Unified Standard Class 2A, right hand, fully threaded,
flat tip; fillister head, high narrow profile, height 0.237", diameter
0.414"; length 5/8"; ASME B18.6.3.  Head height and diameter equal the ASME
B18.6.3 1/4 fillister maxima, as on the 1/4-20 MSC 40923906 row.  The driver
slot follows the shared fillister family law (diag_mcmaster_fillister), not a
supplier dimension.
"""

from __future__ import annotations

IN = 25.4

SKU = "91794A558"
THREAD = "1/4-28"
THREAD_CLASS = "2A"
SOURCE = "https://www.mcmaster.com/91794A558/ (live product page, 2026-11-09)"
THREAD_FIT_SOURCE = SOURCE
THREAD_LIMITS_SOURCE = (
    "https://www.steelmasters.co.nz/wp-content/uploads/2022/03/"
    "External___Internal_Thread_Dimensions_for_UNF_Screw_Thread_2016.pdf"
)

SHANK_DIA = 0.250 * IN  # 6.35, "Screw Size Decimal Equivalent 0.250"
SHANK_LEN = 0.625 * IN  # 15.875, 5/8 under the head
HEAD_H = 0.237 * IN  # 6.0198
HEAD_DIA = 0.414 * IN  # 10.5156
PITCH = IN / 28.0
FILLISTER_SIZE = (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH)

# Steelmasters external UNF table, 1/4" / 28 TPI / 2A row, inches -> mm.
# Thread-form limits, not a tolerance assigned to the nominal model.
THREAD_MAJOR_MAX_MM = 0.2490 * IN
EXTERNAL_PITCH_DIA_MIN_MM = 0.2225 * IN
# The table publishes only the UNR minor MAXIMUM (reference).  DERIVED
# ESTIMATE of the minimum, the repo's deepest-root construction
# (pd_vn_transgear_pivot_screw_spec): a full basic half-depth 0.649519 P below
# the 2A pitch-diameter minimum, 0.2225 - 0.649519/28 = 0.1993 in.
THREAD_MINOR_UNR_MAX_MM = 0.2064 * IN
THREAD_MINOR_MIN_MM = (0.2225 - 0.649519 / 28.0) * IN
