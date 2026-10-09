r"""Pure supplier geometry and stock bands for McMaster 91829A560.

This module owns the harvested nominal dimensions in mm. The native
``diagnostics/diag_build_91829A560.py`` recipe consumes them; base, platform
and pose readers never import that recipe or a build wrapper.

Only the shoulder diameter and length have supplied tolerance bands here,
verified on the live product page on 2026-10-08. The harvested head, slot,
chamfer and thread-profile dimensions are vendor-model nominals, not
title-block manufactured grades or proof of unprovided supplier limits.
The qualified UNC-2A limits constrain only the supplied thread form.
MIN_USEFUL_ENGAGEMENT_MM is a functional installed-joint inspection with
the shoulder fully seated, not a supplier thread-tail/tip tolerance or a
thread-to-shoulder coaxiality grade.
Its two-place MIN callout is spec-owned so assembly drawings consume the
installed-joint requirement without choosing or reformatting its limit.
"""

from __future__ import annotations

from math import ceil

from _hole_spec import TAP_DRILL_MM

SOURCE = "https://www.mcmaster.com/91829A560/ (live product page, 2026-10-08)"
MODEL_SOURCE = "cad/out/reports/mcmaster-91829A560-dump2.json"
THREAD_FIT_SOURCE = SOURCE
THREAD_LIMITS_SOURCE = (
    "https://www.steelmasters.co.nz/wp-content/uploads/2022/03/"
    "External_Thread_Dimensions_for_UNC_Screw_Thread_2016.pdf"
)

# Vendor-model dimensions (mm), preserving the harvested scalars exactly.
HEAD_DIA = 9.525  # Head Diameter@Sketch1
HEAD_T = 4.7625  # Head Height@Sketch1
SHOULDER_DIA = 6.35  # Shoulder Diameter@Sketch1
SHOULDER_LEN = 6.35  # Shoulder Length@Sketch1
THREAD_MAJOR = 4.826  # Screw Size Decimal Equivalent@Sketch1
THREAD_LEN = 9.525  # Thread Length@Sketch1
UNDERHEAD_LEN = SHOULDER_LEN + THREAD_LEN
SLOT_W = 1.524  # D1@Sketch8
SLOT_D = 1.905  # D1@Cut-Extrude2
HEAD_CHAMFER = 0.309563  # D1@Chamfer1 (45 deg)
TIP_CHAMFER = 0.43434  # D1@Chamfer2 (45 deg)
UC_LAND_DIA = 3.3528  # CADA@Sketch5 (diametric)
UC_W = 1.6002  # CADB@Sketch5 (fillet + land; split-plane offset)
PITCH = 1.058333  # Pitch@Helix/Spiral2; preserve the vendor's rounded pitch
REVS = 9.0  # 9000@Helix/Spiral2

# Supplier deviations in mm, ordered (upper, lower), as in _fit_limits.
# SOURCE quotes shoulder diameter +0/-0.001 in and length +0.002/0 in.
SHOULDER_DIA_BAND = (0.0, -0.0254)
SHOULDER_LEN_BAND = (0.0508, 0.0)
HEAD_DIA_BAND = None  # Unknown supplier tolerance, not a zero-width band.
HEAD_H_BAND = None

__all__ = [
    "HEAD_DIA",
    "HEAD_H",
    "SHOULDER_DIA",
    "SHOULDER_LEN",
    "SHOULDER_DIA_BAND",
    "SHOULDER_LEN_BAND",
    "SOURCE",
    "HEAD_DIA_BAND",
    "HEAD_H_BAND",
    "THREAD",
    "THREAD_CLASS",
    "THREAD_FIT_SOURCE",
    "THREAD_LIMITS_SOURCE",
    "THREAD_MAJOR_MAX_MM",
    "EXTERNAL_PITCH_DIA_MIN_MM",
    "MIN_USEFUL_ENGAGEMENT_MM",
    "MIN_USEFUL_ENGAGEMENT_SOURCE",
    "MIN_USEFUL_ENGAGEMENT_TEXT",
    "THREAD_SOLID_DIA",
    "THREAD_TAIL_LEN",
    "THREAD_TAP_DRILL_DIA",
    "UNDERHEAD_LEN",
]

THREAD = "#10-24"
THREAD_CLASS = "2A"
# Steelmasters external UNC table, No 10 / 24 TPI / 2A row, inches -> mm.
THREAD_MAJOR_MAX_MM = 0.1890 * 25.4
EXTERNAL_PITCH_DIA_MIN_MM = 0.1586 * 25.4
HEAD_H = HEAD_T
THREAD_TAIL_LEN = THREAD_LEN
THREAD_SOLID_DIA = THREAD_MAJOR
THREAD_TAP_DRILL_DIA = TAP_DRILL_MM[THREAD]
# Actual installed full-form engagement is inspected with the shoulder seated.
# This is an engineering >=1D floor, not a supplied tail/tip dimension band.
MIN_USEFUL_ENGAGEMENT_MM = ceil(THREAD_SOLID_DIA * 100.0) / 100.0
MIN_USEFUL_ENGAGEMENT_SOURCE = (
    "Functional installation inspection: full-form pivot thread engagement "
    "at least 1D, rounded upward to 0.01 mm; shoulder fully seated"
)
MIN_USEFUL_ENGAGEMENT_TEXT = f"{MIN_USEFUL_ENGAGEMENT_MM:.2f} MIN"
