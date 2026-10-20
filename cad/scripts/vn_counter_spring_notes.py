"""Purchased reference-sheet notes for the 1330K524 counter spring.

The sheet's footer holds at most three note lines (drawing-guidelines rule 7).
The isometric preserves the installed pose; labelled native configurations
supply the separate free and maximum states. Catalogue force data remain
reference values because the supplier states no tolerance on them. Machine
calibration against the spring's own force curve remains an assembly matter.
"""

from __future__ import annotations

from vn_counter_spring_spec import (
    INITIAL_TENSION_N,
    SPRING_RATE_N_PER_MM,
)


DRAWING_NOTES = "\n".join(
    (
        "ISOMETRIC SHOWS INSTALLED POSE; SUPPLIER STATES ARE LABELLED.",
        f"CATALOG RATE ({SPRING_RATE_N_PER_MM:.3f} N/MM) AND INITIAL TENSION "
        f"({INITIAL_TENSION_N:.1f} N) ARE REF;",
        "THE SUPPLIER STATES NO TOLERANCE ON EITHER.",
    )
)
