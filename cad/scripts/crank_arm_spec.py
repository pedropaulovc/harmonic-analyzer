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
from _hole_spec import HoleSpec

from _surface_finish import SurfaceFinishControl

# inch -> mm. Mirrors ``_common.IN`` but kept local so the spec pulls in NO COM
# module (importing ``_common`` would drag the SolidWorks adapter back into the
# drawing's recipe closure -- the very coupling this split removes).
MM_PER_IN = 25.4

# --- Nominal geometry (DIMENSIONS.md "Chapter 11", photo-scaled low unless noted).
# These drive the part's named equation globals AND the drawing's coordinate math. ---
ARM_C2C = 75.0  # shaft-to-handle-pivot centres -- 2026-09 re-derive from the ch30
# FRONT view (p002, registered pair: the arm reads 107 px hub-to-pivot against the
# model's 92 px at 66 -> 77, less ~2% perspective for the crank standing 60 mm
# nearer the camera than the columns) and the ch11 p.13 studio photo (~78 at the
# arm-width scale). The earlier 66 came from the angle-90 side view, where the
# crank is the closest thing to the camera and the base depth it was scaled to
# sits 200 mm behind it. The crank hangs straight down; the handle axis lands
# 4.0 mm above the base top and the handle itself hangs in front of the base
# (its grip runs -Z, south of the base front). The former 150 (cone-axial
# scaled, low) was >2x too long (med).
ARM_WIDTH = 16.0  # arm width (low)
ARM_THICKNESS = 8.0  # ~half the arm width, p.12 photo (low)
SQUARE_END_OVERHANG = 10.0  # square end past the pivot (low)
SHAFT_BORE_DIA = 0.375 * MM_PER_IN  # 9.525: 3/8" crankshaft (med); the legacy 9.5
# rounding left the bore 0.025 smaller than the shaft (caught in M6.2).  Three
# DISPLAYED places because the nominal is an exact inch conversion the callout
# cites, not because the bore is held tighter than the title block: the arm is
# PINNED to its shaft, so this is no running fit and it carries no local band
# (cad/docs/tolerance-policy.md -- the drilled-hole row, +0.10/0, governs).
PIN_HOLE_SPEC = HoleSpec("drilled_number", "#14")
HANDLE_PIVOT_HOLE_SPEC = HoleSpec("drilled_fractional", "15/64")
DIMPLE_DIA = 8.0  # fiducial indentation (low)
DIMPLE_DEPTH = 0.5  # fiducial indentation (low)
DIMPLE_X = 30.0  # on the arm near the boss (low)
# Keeper-ring anchor (2026-09-02, ch11 p.14 page001_img02): a small slotted
# screw in the arm's FRONT (operator) face between the hub and the dimple,
# near one edge, clamping a brass wire eyelet that hangs toward the handle
# (the chain to the pin's ring is lost -- only the eye remains). The dimple
# is on that same face in the photo.
ANCHOR_SCREW_X = 20.0  # along the arm from the shaft axis (low)
ANCHOR_SCREW_Y = 4.5  # off the arm centreline toward the local +y edge (machine -X
# once placed; low). Kept POSITIVE: a driven placement dim is a magnitude.
ANCHOR_THREAD_DEPTH = 5.5  # full #4-40 thread for 5.33 stock-screw insertion
ANCHOR_DRILL_DEPTH = 6.5  # cylindrical depth; bottoming tap leaves 1.0 lead room
ANCHOR_HOLE_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=ANCHOR_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": ANCHOR_THREAD_DEPTH},
)
# The 118-degree drill point extends another 0.679: back-face wall is 0.821.

# No roughness callouts: the arm is pinned to its crankshaft, so nothing runs
# on the bore; every face is "as cast/machined" per the title block
# (cad/docs/drawing-simplicity-policy.md rule 5).
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived spans (equations of the primitives above).
ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG  # 85.0: square end past the shaft-bore origin
HALF_WIDTH = ARM_WIDTH / 2.0  # 8.0

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows. ``build_crank_arm`` marks exactly these; ``draw_crank_arm`` keeps
# exactly their union across its per-view ``keep`` maps. The offline test enforces
# ``union(marks) == union(keeps)`` so a rename in one script that isn't mirrored in
# the other fails before any SolidWorks build.
#
# ``StationReference`` and ``PinStationReference`` are hidden construction
# sketches whose one job is to OWN the locations the sheet prints but no
# feature dimension carries (policy rule 2): the pivot and anchor stations from
# the shaft-bore axis, the anchor's offset from the top long edge, the stock
# width, and the cross-hole's station from the broad face. A Hole Wizard
# placement sketch measures from the origin and cannot start on the long edge,
# so the print imports these instead of building them from view picks. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"ArmEndX", "BossRadius"},
    "Arm": {"Depth"},
    "ShaftBoreProfile": {"ShaftBoreDia"},
    "DimpleProfile": {"DimpleX", "DimpleDia"},
    "StationReference": {"PivotStation", "AnchorStation", "AnchorOffset", "Width"},
    "PinStationReference": {"PinStation"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule 2),
# so the MODEL owns them: build_crank_arm applies this map to the .SLDPRT and
# draw_crank_arm only reads it back. Three places on the bore alone, because
# 9.525 is the exact 3/8 in conversion its callout cites -- not because the
# bore is held tighter than the title block (the arm is pinned to its shaft).
# Every other feature on a hand-crank lever is noncritical and prints one
# place, so the title block's .X row governs it (cad/docs/tolerance-policy.md).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ArmOutline": {"ArmEndX": 1, "BossRadius": 1},
    "Arm": {"Depth": 1},
    "ShaftBoreProfile": {"ShaftBoreDia": 3},
    "DimpleProfile": {"DimpleX": 1, "DimpleDia": 1},
    "StationReference": {
        "PivotStation": 1,
        "AnchorStation": 1,
        "AnchorOffset": 1,
        "Width": 1,
    },
    "PinStationReference": {"PinStation": 1},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
):
    raise AssertionError("DRAWING_PRECISION names a dimension the part never marks")
if any(
    name not in {name for names in DRAWING_PRECISION.values() for name in names}
    for names in DRAWING_DIMENSIONS.values()
    for name in names
):
    raise AssertionError("a marked dimension prints without part-authored places")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# The one sheet-derived dimension: the parenthesised boss-extreme-to-arm-end
# overall, a read-only sum of the boss radius and ArmEndX with no model
# dimension to import. Its places are still specification, so the sheet
# reads them here instead of typing a literal (policy rule 2).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 1}

# Notes: at most four short lines of part-specific facts a machinist cannot
# read off the views, never a dimension and never a method
# (drawing-simplicity-policy.md rule 6).  The anchor tap's thread and drill
# depths are on its hole callout, and both hole positions are dimensioned on
# the print, so neither needs a line here.  The first line backs the drawn
# arm centreline the bore, dimple and pivot centre marks sit on (no cross-width
# location dimension exists for them to carry).
DRAWING_NOTES = "\n".join(
    (
        "SHAFT BORE, DIMPLE AND PIVOT HOLE ARE ON THE ARM CENTRELINE.",
        "CROSS-HOLE AXIS INTERSECTS SHAFT BORE AXIS.",
        "DIMPLE AND ANCHOR TAP ARE CUT IN THE HANDLE-SIDE FACE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
