"""Purchased reference-sheet prose for the 1330K524 counter spring.

The footer prints four lines (drawing-guidelines rule 7): one note line, the
supplier-data heading and one data row the generic footer adds, and its
purchased-part general line. Every fact is stated once: "installed length" is
the one term for the stretched state the views show; the three lengths share
the catalogue's inside-loop convention; the catalogue force data are reference
values the supplier states no tolerance on, under the heading that already
calls them reference. The coil OD and wire sizes ride in the catalogue
designation on the ITEM row. How the machine is set against the spring's own
force curve is an assembly matter, not a note on the part (machinist review r4).
"""

from __future__ import annotations

from sm_vn_counter_spring_spec import (
    FREE_LENGTH_MM,
    INITIAL_TENSION_N,
    INSTALLED_LENGTH_MM,
    MAX_LENGTH_MM,
    SPRING_RATE_N_PER_MM,
    SUPPLIER_COIL_OD_MM,
    SUPPLIER_PRECISION,
    SUPPLIER_WIRE_DIA_MM,
)


MM_PER_IN = 25.4
N_PER_LBF = 4.4482216


def _inch(value_mm: float, name: str) -> str:
    """The inch figure at the catalogue's own places for source dimension ``name``."""
    text = f"{value_mm / MM_PER_IN:.{SUPPLIER_PRECISION[name]}f}"
    return text[1:] if text.startswith("0.") else text


# The footer's ITEM row: the catalogue designation in plain text, with the
# catalogue's coil and wire sizes.
ITEM = (
    "DOUBLE-LOOP EXTENSION SPRING, "
    f"COIL OD (Ø{_inch(SUPPLIER_COIL_OD_MM, 'SupplierCoilOD')}), "
    f"WIRE (Ø{_inch(SUPPLIER_WIRE_DIA_MM, 'SupplierWireDiameter')})"
)

# The inch sheet prints the catalogue's own inch figures; the installed length
# at the free length's places.
DRAWING_NOTES = (
    f"SHOWN AT INSTALLED LENGTH ({_inch(INSTALLED_LENGTH_MM, 'SupplierFreeLength')}); "
    f"FREE ({_inch(FREE_LENGTH_MM, 'SupplierFreeLength')}), "
    f"MAX ({_inch(MAX_LENGTH_MM, 'SupplierMaximumLength')}), ALL INSIDE LOOPS."
)

# The catalogue's inch-pound force data, one row under the generic footer's
# "SUPPLIER OPERATING DATA (REFERENCE):" heading.
SUPPLIER_DATA = (
    f"RATE ({SPRING_RATE_N_PER_MM * MM_PER_IN / N_PER_LBF:.2f} LBF/IN) "
    f"AND INITIAL TENSION ({INITIAL_TENSION_N / N_PER_LBF:.2f} LBF) UNTOLERANCED",
)
