r"""Pure supplier geometry and stock bands for McMaster 91829A560.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure. The harvested nominal dimensions in mm are the per-SKU vendor source
(``_mcmaster_91829a560.py``, SolidWorks-free at import), which the native
recipe also reads; base, platform and pose readers never import that recipe
or a build wrapper.

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
from _mcmaster_91829a560 import (
    HEAD_DIA,
    HEAD_T,
    SHOULDER_DIA,
    SHOULDER_LEN,
    THREAD_LEN,
    THREAD_MAJOR,
    UNDERHEAD_LEN,
)

SOURCE = "https://www.mcmaster.com/91829A560/ (live product page, 2026-10-08)"
MODEL_SOURCE = "cad/out/reports/mcmaster-91829A560-dump2.json"
THREAD_FIT_SOURCE = SOURCE
THREAD_LIMITS_SOURCE = (
    "https://www.steelmasters.co.nz/wp-content/uploads/2022/03/"
    "External_Thread_Dimensions_for_UNC_Screw_Thread_2016.pdf"
)

# Supplier deviations in mm, ordered (upper, lower), as in _fit_deviations.
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
