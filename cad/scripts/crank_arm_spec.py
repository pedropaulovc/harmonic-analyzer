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
SQUARE_END_OVERHANG = 10.0  # stock end past the pivot (low); the ch11 photos
# show the end FULL-ROUNDED -- modeled as two corner fillets on the stock end
# (END_ROUND_R below), so ArmEndX keeps dimensioning the 76 stock span.
END_ROUND_R = 7.98  # a hair under ARM_WIDTH/2: the two corner fillets meet at
# the centreline within 0.02 without the degenerate exact-tangency case
HUB_DIA = 16.0  # rear hub boss = the boss circle carried through (ch11
# page002_img03: hub reads the arm's own width)
HUB_LEN = 9.2  # north face (-167) to 0.3 clear of the crankshaft's SeatT12
# datum (-157.5) where the T12 chain wheel's boss seats (machine z)
PIN_HOLE_Z = -4.0  # pin cross-hole station: 4.0 behind the plate's north face
# (machine z -163) -- matches build_crankshaft.PIN_HOLE_HEIGHT 12 exactly
KEEPER_X = 13.0  # keeper screw station down the arm edge (photo: just clear
# of the hub flank, ch11 page002_img03)
KEEPER_PROUD = 1.2  # under-head face proud of the edge: the brass chain
# eyelet's wire hangs on the exposed shank band
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
        "SHAFT BORE AND HANDLE PIVOT CENTRED ACROSS 16 WIDTH.",
        "FULL-ROUND THE HANDLE END (R8).",
        "REAR HUB BOSS <MOD-DIAM>16 X 9.2 LONG, COAXIAL WITH SHAFT BORE.",
        "HANDLE PIVOT: 15/64 DRILL THRU.",
        "TAPER PIN CROSS-HOLE: #14 DRILL PILOT AT ASSEMBLY THROUGH HUB AND",
        "SHAFT-BORE AXIS, 4.0 BEHIND HUB-SIDE FACE; TAPER-REAM WITH SHAFT 1:48,",
        "LARGE END OUTBOARD (HOLE AS-REAMED IN MODEL).",
        "KEEPER: 1/8 DRILL 3.4 DEEP IN EDGE AT 13.0 FOR THE EYELET SCREW.",
        "DIMPLE: <MOD-DIAM>8 FLAT-BOTTOM, 0.50 +0.20/-0.10 DEEP; LOCATION +/-0.25.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
