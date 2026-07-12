r"""Crank-arm dimensional contract -- the single source of truth shared by the
part build (``build_crank_arm.py``) and its manufacturing drawing
(``draw_crank_arm.py``).

REFERENCE for the ``<part>_spec.py`` split. PURE DATA, no SolidWorks/COM imports:
the nominal geometry (the "editable knobs"), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. Keeping
this in ONE module means a rename or a nominal change is a single edit that reaches
both scripts, so the part-side ``mark_dimensions_for_drawing`` set and the
drawing-side ``keep`` maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_crank_arm`` and ``draw_crank_arm``
``from crank_arm_spec import ...``, so ``module_deps_of`` folds THIS file into BOTH
recipe digests -- an edit here rebuilds the part AND the drawing (the coupling you
want). But the drawing no longer imports ``build_crank_arm``, so a pure build-logic
edit that leaves this spec (and the .SLDPRT geometry) untouched does NOT force a
drawing rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``. The correct asymmetry -- part change => drawing rebuilds; drawing
change =/> part rebuilds -- falls straight out of the DAG.

The offline lockstep test (``test_crank_arm_drawing.py``) asserts the part marks
and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm, run
without SolidWorks in ~1 s.
"""

from __future__ import annotations

# inch -> mm. Mirrors ``_common.IN`` but kept local so the spec pulls in NO COM
# module (importing ``_common`` would drag the SolidWorks adapter back into the
# drawing's recipe closure -- the very coupling this split removes).
MM_PER_IN = 25.4

# --- Nominal geometry (DIMENSIONS.md "Chapter 11", photo-scaled low unless noted).
# These drive the part's named equation globals AND the drawing's coordinate math. ---
ARM_C2C = 66.0  # shaft-to-handle-pivot centres -- REDERIVED from the ch30 eight-views
# (angle-90 side view, scaled to the 280 mm base depth): the crank hangs straight
# down, handle pivot 66 mm below the crankshaft axis, landing the handle ~10 mm above
# the base top. The former 150 (cone-axial scaled, low) was >2x too long -- a
# down-pointing 150 arm would drive the handle below the table (med).
ARM_WIDTH = 16.0  # arm width (low)
ARM_THICKNESS = 8.0  # ~half the arm width, p.12 photo (low)
SQUARE_END_OVERHANG = 10.0  # square end past the pivot (low)
SHAFT_BORE_DIA = 0.375 * MM_PER_IN  # 9.525: 3/8" crankshaft (med); the legacy 9.5
# rounding left the bore 0.025 smaller than the shaft (caught in M6.2)
DIMPLE_DIA = 8.0  # fiducial indentation (low)
DIMPLE_DEPTH = 0.5  # fiducial indentation (low)
DIMPLE_X = 30.0  # on the arm near the boss (low)

# Derived spans (equations of the primitives above).
ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG  # 76.0: square end past the shaft-bore origin
HALF_WIDTH = ARM_WIDTH / 2.0  # 8.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_crank_arm`` marks exactly these; ``draw_crank_arm`` keeps
# exactly their union across its per-view ``keep`` maps. The offline test enforces
# ``union(marks) == union(keeps)`` so a rename in one script that isn't mirrored in
# the other fails before any SolidWorks build. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"ArmEndX", "BossRadius"},
    "Arm": {"Depth"},
    "ShaftBoreProfile": {"ShaftBoreDia"},
    "DimpleProfile": {"DimpleX", "DimpleDia"},
}

# True free-text instructions only. Geometry, datum structure, form/orientation,
# and roughness live in native dimensions / datum tags / FCFs / surface symbols.
# The part build stamps these strings into the SLDPRT; the drawing displays only
# $PRPSHEET links, so the print cannot silently diverge from its source model.
DRAWING_NOTES = "\n".join(
    (
        "UOS: LINEAR +/-0.25; ANGLES +/-0.5 DEG.",
        "HOLE CENTRES +/-0.10; DRILLED DIAMETERS +/-0.10.",
        "DEBURR; BREAK EDGES 0.2 MAX.",
        "HANDLE PIVOT: 15/64 DRILL THRU.",
        "CROSS-PIN: #9 DRILL; TAPER-REAM WITH SHAFT FOR NO. 2 TAPER PIN,",
        "1:48, LARGE END OUTBOARD.",
        "DIMPLE: O8 FLAT-BOTTOM; LOCATION AND DEPTH +/-0.5.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
