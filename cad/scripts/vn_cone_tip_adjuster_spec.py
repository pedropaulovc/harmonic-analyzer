r"""Pure McMaster 94025A164 #10-32 x 3/8 cup-tip adjuster geometry.

The supplier-model dump owns these raw nominal dimensions in mm. The native
``diagnostics/diag_build_94025A164.py`` recipe and its build wrapper consume
this spec; shaft, assembly and global-pose readers import this spec directly.

Sketch2's cup rim radius is 1.2065 and its apex lies 1.2065 inside the end
face (SS_HALF - SS_CONE_Y). CUP_DIA/CUP_DEPTH describe that nominal 90-degree
cone only. Supplier cup/length tolerances are unprovided, represented by
None, not zero deviations or a manufactured title-block grade. The verified
UNF-2A thread limits below constrain the threaded material envelope, not the
cup profile. Nominal cup geometry alone cannot certify a supplied-stock fit.
"""

SOURCE = "cad/out/reports/mcmaster-94025A164-dump.json"
THREAD_FIT_SOURCE = "https://www.mcmaster.com/94025A164/ (live product page, 2026-10-08)"
THREAD_LIMITS_SOURCE = (
    "https://www.steelmasters.co.nz/wp-content/uploads/2022/03/"
    "External___Internal_Thread_Dimensions_for_UNF_Screw_Thread_2016.pdf"
)

SS_MAJOR_R = 2.413  # Screw Size Decimal Equivalent@Sketch1 / 2
SS_LEN = 9.525  # Length@Sketch1 (full, slot face to cup rim)
SS_HALF = SS_LEN / 2.0  # Vendor origin sits mid-length; recipe frame does too
SS_PITCH = 0.79375  # Pitch@Sketch1 (#10-32: 25.4/32)
SS_REVS = 14.0  # Vendor 13 from the face; +1 lead-in rev in air
SS_CHAM_R = 2.155222  # Slot-end rim chamfer inner radius (Sketch2 Line1)
SS_CHAM_H = 4.7625 - 4.582002  # Its axial extent (0.180498)
SS_TIP_R = 1.2065  # Tip cone end radius = cup rim radius (Sketch2)
SS_CONE_Y = 3.556  # Tip cone start / cup apex |y| (Sketch2 Line7)
SS_SLOT_W = 0.804333  # D3@Sketch1 (slot width = major / 6)
SS_SLOT_D = 0.79375  # Drive Depth@Sketch1 (slot depth = P)
# Vendor Sketch7 UN cutter: capped at 15P/16 with a P/8 root flat.
SS_CUT_TOP_R = 2.455963
SS_CUT_TOP_W = 0.744141
SS_CUT_ROOT_R = 1.897444
SS_CUT_ROOT_W = 0.099219
SS_CUT_CY = SS_HALF + SS_PITCH + 7.0 * SS_PITCH / 16.0
SS_CUP_DEPTH = SS_HALF - SS_CONE_Y
assert abs(SS_CUP_DEPTH - SS_TIP_R) < 1e-9

THREAD = "#10-32"
THREAD_CLASS = "2A"
# Steelmasters external UNF table, No 10 / 32 TPI / 2A row, inches -> mm.
# These are thread-form limits, not a tolerance assigned to the nominal cup.
THREAD_MAJOR_MAX_MM = 0.1891 * 25.4
EXTERNAL_PITCH_DIA_MIN_MM = 0.1658 * 25.4
BODY_DIA = 2.0 * SS_MAJOR_R
BODY_LEN = SS_LEN
CUP_DIA = 2.0 * SS_TIP_R
CUP_DEPTH = SS_CUP_DEPTH
BODY_DIA_BAND = None  # Unknown supplier tolerance, not a zero-width band.
BODY_LEN_BAND = None
CUP_DIA_BAND = None
CUP_DEPTH_BAND = None
