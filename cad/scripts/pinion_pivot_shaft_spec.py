r"""Pure-data dimensional contract shared by the pinion strap torque shaft and
its manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A plain Ø6.35 turned steel shaft with a
shallow spherical crown at each end -- the pivot the two swing straps rock on.
The nominals drive the part's named equation globals AND the drawing's
coordinate math; the marked-dimension map keeps the part marks and the drawing
keeps in lockstep (``test_pinion_pivot_shaft_drawing.py``).
"""

from __future__ import annotations

SHAFT_DIA = 6.35  # 1/4 in: rides both pivot blocks' east bores and the straps
SHAFT_LEN = 192.0  # ends flush with the pivot blocks' outer faces
CAP_SAG = 1.2  # shallow spherical crown height at each end
CAP_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + CAP_SAG**2) / (2.0 * CAP_SAG)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "Shaft": {"Depth"},
}

DRAWING_NOTES = "\n".join(
    (
        "CYLINDRICAL BODY HAS NO FLATS OR STEPS.",
        "DATUM A IS THE CYLINDRICAL BODY'S DERIVED AXIS.",
        "BOTH SPHERICAL CROWN SURFACES: PROFILE 0.05, FORM ONLY (NO DATUM);",
        "  EACH CROWN IS INSPECTED INDEPENDENTLY.",
        f"  SR{CAP_RADIUS:.2f}+/-0.05 GOVERNS SIZE; ({CAP_SAG:.2f}) REF AXIAL HEIGHT",
        "  FROM EACH CROWN ROOT CIRCLE.",
        "CROWN ROOT CIRCLES ARE SHARP THEORETICAL PROFILE BREAKS;",
        "  EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
END_VIEW_NOTE = "END VIEW SCALE 4:1"
# The isometric renders at ISO_SCALE (1, 2) while the sheet/title block reads
# 1:1, so without this the pictorial is silently half scale.  Mirrors
# fulcrum-shaft / cylinder-gear-shaft, whose identical 1:2 iso carry the note.
ISO_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
