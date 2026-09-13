"""Purchased reference-sheet data for the 9432K31 channel spring."""

from __future__ import annotations

import _config
from channel_spring_installed_spec import (
    FREE_LENGTH_MM,
    INITIAL_TENSION_N,
    INITIAL_TENSION_TOLERANCE_N,
    INSTALLED_LENGTH_MM,
    MAXIMUM_LOAD_N,
    MAX_LENGTH_MM,
    SPRING_RATE_N_PER_MM,
    SPRING_RATE_TOLERANCE_FRACTION,
)
from spring_mount_geom import channel_force_n


DRAWING_DIMENSIONS: dict[str, set[str]] = {}

_QC_LENGTH_1_MM = 60.0
_QC_LENGTH_2_MM = 80.0
_QC_PIN_DIA_MM = 2.0
_QC_FORCE_1_N = channel_force_n(_QC_LENGTH_1_MM)
_QC_FORCE_2_N = channel_force_n(_QC_LENGTH_2_MM)
_MATCH_TOLERANCE_PERCENT = float(
    _config._doc("error_budget")["critical_features"]["spring_rate"]["tolerance"]
)

DRAWING_NOTES = "\n".join(
    (
        "PURCHASED EXTENSION SPRING - REFERENCE DATA",
        "  SUPPLIER / SKU .... McMASTER-CARR / 9432K31",
        "  END TYPE .......... MACHINE-HOOK ENDS",
        f"  FREE LENGTH ....... {FREE_LENGTH_MM:.2f} MM INSIDE HOOKS",
        f"  CATALOG MAX ....... {MAX_LENGTH_MM:.2f} MM AT {MAXIMUM_LOAD_N:.3f} N",
        f"  NOMINAL RATE ...... {SPRING_RATE_N_PER_MM:.4f} N/MM "
        f"(+/-{100.0 * SPRING_RATE_TOLERANCE_FRACTION:.0f}% CATALOG)",
        f"  INITIAL TENSION ... {INITIAL_TENSION_N:.3f} N "
        f"(+/-{INITIAL_TENSION_TOLERANCE_N:.6f} N)",
        f"  ILLUSTRATED LENGTH  {INSTALLED_LENGTH_MM:.2f} MM INSIDE HOOKS",
        "  CAD COILS ARE REFERENCE GEOMETRY; DO NOT DERIVE FORCE FROM THEM.",
        f"SET QC: USE Ø{_QC_PIN_DIA_MM:.2f} MM PINS; PIN C-C = "
        f"{_QC_LENGTH_1_MM - _QC_PIN_DIA_MM:.2f}/"
        f"{_QC_LENGTH_2_MM - _QC_PIN_DIA_MM:.2f} MM.",
        f"  THIS REPRESENTS {_QC_LENGTH_1_MM:.2f}/{_QC_LENGTH_2_MM:.2f} MM "
        "INSIDE-HOOK LENGTHS.",
        f"  NOMINAL F60/F80 = {_QC_FORCE_1_N:.3f}/{_QC_FORCE_2_N:.3f} N; "
        "RATE = (F80-F60)/20.00 MM.",
        "  READ EACH FORCE 30 S AFTER LOADING.",
        f"  ALL 20 WITHIN +/-{_MATCH_TOLERANCE_PERCENT:.2f}% OF THE SET MEAN; "
        "USE ONE COMMON SET MEAN.",
        f"  CATALOG +/-{100.0 * SPRING_RATE_TOLERANCE_FRACTION:.0f}% "
        "DOES NOT MEET THE SET-MATCH LIMIT.",
        "  RECORD THE COMMON RATE MEAN AND EACH EXTRAPOLATED INITIAL TENSION",
        "  FOR COUNTERSPRING AND MAGNIFIER CALIBRATION.",
    )
)

ISOMETRIC_VIEW_NOTE = "ISOMETRIC REFERENCE VIEW SCALE 1:1"
