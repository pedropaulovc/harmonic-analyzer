"""Purchased reference-sheet notes for the 1330K524 counter spring.

The sheet's footer holds at most three note lines (drawing-guidelines rule 7).
"Installed length" is the one term for the stretched state the views show; the
catalogue force data are reference values because the supplier states no
tolerance on them. How the machine is set against the spring's own force
curve is an assembly matter, not a note on the part (machinist review r4).
"""

from __future__ import annotations

from sm_vn_counter_spring_spec import (
    FREE_LENGTH_MM,
    INITIAL_TENSION_N,
    INSTALLED_LENGTH_MM,
    SPRING_RATE_N_PER_MM,
)


DRAWING_NOTES = "\n".join(
    (
        f"SHOWN AT INSTALLED LENGTH ({INSTALLED_LENGTH_MM:.1f}) INSIDE LOOPS; "
        f"FREE LENGTH ({FREE_LENGTH_MM:.1f}).",
        f"CATALOG RATE ({SPRING_RATE_N_PER_MM:.3f} N/MM) AND INITIAL TENSION "
        f"({INITIAL_TENSION_N:.1f} N) ARE REF;",
        "THE SUPPLIER STATES NO TOLERANCE ON EITHER.",
    )
)
