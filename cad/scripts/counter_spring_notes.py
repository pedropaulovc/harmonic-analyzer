"""Purchased reference-sheet data for the 1330K524 counter spring."""

from __future__ import annotations

from counter_spring_spec import (
    FREE_LENGTH_MM,
    INITIAL_TENSION_N,
    INSTALLED_LENGTH_MM,
    MAXIMUM_LOAD_N,
    MAX_LENGTH_MM,
    SPRING_RATE_N_PER_MM,
)


DRAWING_NOTES = "\n".join(
    (
        "PURCHASED EXTENSION SPRING - REFERENCE DATA",
        f"  FREE LENGTH ....... {FREE_LENGTH_MM:.2f} MM INSIDE LOOPS",
        f"  CATALOG MAX ....... {MAX_LENGTH_MM:.2f} MM AT {MAXIMUM_LOAD_N:.3f} N",
        f"  NOMINAL RATE ...... {SPRING_RATE_N_PER_MM:.4f} N/MM",
        f"  INITIAL TENSION ... {INITIAL_TENSION_N:.3f} N",
        f"  ILLUSTRATED LENGTH  {INSTALLED_LENGTH_MM:.2f} MM INSIDE LOOPS",
        "  SUPPLIER RATE / INITIAL-TENSION TOLERANCES",
        "  UNSPECIFIED; MEASURE FORCE CURVE",
        "  FOR CALIBRATION.",
        "  CAD COILS: REFERENCE GEOMETRY ONLY;",
        "  DO NOT DERIVE FORCE FROM THE COILS.",
    )
)
