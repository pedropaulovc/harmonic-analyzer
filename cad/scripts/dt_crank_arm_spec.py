r"""Crank-arm dimensional contract -- the single source of truth shared by the
part build (``build_dt_crank_arm.py``) and its manufacturing drawing
(``draw_dt_crank_arm.py``).

REFERENCE for the ``<part>_spec.py`` split. PURE DATA, no SolidWorks/COM imports:
the nominal geometry (the "editable knobs"), the derived spans the drawing needs
for its view math, and the marked-dimension -> kept-dimension NAME map. Keeping
this in ONE module means a rename or a nominal change is a single edit that reaches
both scripts, so the part-side ``mark_dimensions_for_drawing`` set and the
drawing-side ``keep`` maps cannot silently drift apart.

Build-graph consequence (intended): both ``build_dt_crank_arm`` and ``draw_dt_crank_arm``
``from dt_crank_arm_spec import ...``, so ``module_deps_of`` folds THIS file into BOTH
recipe digests -- an edit here rebuilds the part AND the drawing (the coupling you
want). But the drawing no longer imports ``build_dt_crank_arm``, so a pure build-logic
edit that leaves this spec (and the .SLDPRT geometry) untouched does NOT force a
drawing rebuild; a geometry change still re-renders the drawing via its .SLDPRT
``file_dep``. The correct asymmetry -- part change => drawing rebuilds; drawing
change =/> part rebuilds -- falls straight out of the DAG.

The offline lockstep test (``test_dt_crank_arm_drawing.py``) asserts the part marks
and the drawing keeps EXACTLY ``DRAWING_DIMENSIONS`` -- the drift alarm, run
without SolidWorks in ~1 s.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec
from _surface_finish import SurfaceFinishControl
from dt_crank_handle_pivot_screw_spec import THREAD_SIZE as PIVOT_SCREW_THREAD_SIZE
from dt_crank_hub_geometry import (
    ARM_STOCK_THICKNESS,
    ARM_STOCK_THICKNESS_IN,
    ARM_THICKNESS,
    ARM_WIDTH,
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    EDGE_BREAK_MAX_MM,
    FIDUCIAL_MODEL_DEPTH,
    FIDUCIAL_MODEL_DIA,
    GENERAL_1PL_TOL_MM,
    HUB_SEAT_DIA,
    HUB_SEAT_DIA_MAX_GENERAL,
    MM_PER_IN,
    WALL_TARGET_MM,
)


# --- Nominal geometry -------------------------------------------------------
ARM_C2C = 75.0
# User ruling 2026-09-29 (ch11 p.14 photo re-check): the handle end is a full
# semicircle concentric with the handle pivot, the same R12.7 as the hub end,
# not the former square end 10.0 past the pivot.  The crank radius stays 75, so
# the arm grows 2.7 to 87.7 from the hub axis.
END_RADIUS = ARM_WIDTH / 2.0
# The bar is left at its as-supplied thickness, so that stock must read as the
# printed 8.0 inside the title block's .X band.
if abs(ARM_STOCK_THICKNESS - ARM_THICKNESS) > GENERAL_1PL_TOL_MM:
    raise AssertionError(
        f"arm stock {ARM_STOCK_THICKNESS:.3f} is outside the printed {ARM_THICKNESS:.1f}'s .X band"
    )
# U33: the MHA-DT-32 slotted shoulder screw threads through the arm and carries
# the handle.  The end arc shares the pivot's centre, so its tapped web to the
# end is judged at the .X worst case of the end radius alone (U27).
HANDLE_PIVOT_HOLE_SPEC = HoleSpec("tapped", PIVOT_SCREW_THREAD_SIZE)
_PIVOT_THREAD_R = THREAD_MAJOR_MM[HANDLE_PIVOT_HOLE_SPEC.size] / 2.0
PIVOT_END_WEB_NOMINAL = END_RADIUS - _PIVOT_THREAD_R
PIVOT_END_WEB_WORST = PIVOT_END_WEB_NOMINAL - GENERAL_1PL_TOL_MM
if PIVOT_END_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"handle-pivot thread leaves {PIVOT_END_WEB_WORST:.2f} mm to the arm end"
    )

# The axial MHA-DT-VN-59 groove is match-drilled in the assembled arm/hub.  Its
# centre rides the hub-seat interface at six o'clock (toward the hanging handle);
# the 4-mm length is shared as exactly half the 8-mm arm thickness.
AXIAL_PIN_X = AXIAL_PIN_RADIUS_FROM_AXIS
AXIAL_PIN_Y = 0.0

# The arm owns one shallow punched alignment witness; the matching mark is on
# the crankshaft (MHA-DT-11) dome, and the drive-train assembly lines the two up
# before the taper ream.  Its diameter and depth are a visual representation,
# never printed; its centre prints as two ordinates from the hub-seat axis.
#
# The centre must land on the flat outboard face at every accepted part
# (codjiflo P2 on #2005: the first band was checked against the nominal bore).
# That face's worst-case annulus runs from the seat bore's .X upper limit plus
# its edge break out to the boss end's .X lower limit less its break.
FIDUCIAL_FACE_RADII = (
    HUB_SEAT_DIA_MAX_GENERAL / 2.0 + EDGE_BREAK_MAX_MM,
    ARM_WIDTH / 2.0 - GENERAL_1PL_TOL_MM - EDGE_BREAK_MAX_MM,
)
# The mark stands at 135 degrees on that annulus's mid-radius, each ordinate
# rounded to its printed .X place.
_FIDUCIAL_AXIS = round(sum(FIDUCIAL_FACE_RADII) / 2.0 / math.sqrt(2.0), 1)
FIDUCIAL_X = -_FIDUCIAL_AXIS
FIDUCIAL_Y = _FIDUCIAL_AXIS
# A square ordinate band +/-t reaches sqrt(2)(a -/+ t) from the axis at its
# near and far corners.  The title block's .X +/-0.8 would let the centre into
# the bore (9.9 against 10.35), so the ordinates carry their own +/-0.4: as
# loose as the 1.3-mm annulus allows at one place, still enough to scribe and
# hand-punch.
FIDUCIAL_ORDINATE_TOL = 0.4
FIDUCIAL_RADIAL_LIMITS = (
    math.sqrt(2.0) * (_FIDUCIAL_AXIS - FIDUCIAL_ORDINATE_TOL),
    math.sqrt(2.0) * (_FIDUCIAL_AXIS + FIDUCIAL_ORDINATE_TOL),
)
if not (
    FIDUCIAL_FACE_RADII[0]
    < FIDUCIAL_RADIAL_LIMITS[0]
    < FIDUCIAL_RADIAL_LIMITS[1]
    < FIDUCIAL_FACE_RADII[1]
):
    raise AssertionError(
        f"punch witness band reaches {FIDUCIAL_RADIAL_LIMITS} from the hub-seat axis, "
        f"off the worst-case flat face {FIDUCIAL_FACE_RADII}"
    )

# Keeper-ring anchor (ch11 p.14): a small slotted screw in the arm's outboard
# face clamps the brass eyelet that once tethered removable pin MHA-DT-09.
# Tapped THRU the 5/16 bar (drawing-guidelines.md rule 17 (walls and webs), audit W7): a blind 6.5 drill left
# its point 0.76 from the inboard face nominal and through it at the printed
# band; through, the screw has 7.94 of thread (2.79D) and nothing to bottom on.
ANCHOR_SCREW_X = 20.0
ANCHOR_SCREW_Y = 4.5
ANCHOR_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# MHA-DT-31 is a light press in MHA-DT-06 and pinned; nothing runs in this part.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived spans.
ARM_END_X = ARM_C2C + END_RADIUS
HALF_WIDTH = ARM_WIDTH / 2.0

# The thickness prints as a reference, (8.0), under the stock line's "AS
# SUPPLIED": the bar's mill tolerance governs it, not the title block's .X
# band, which would accept a 7.2 arm and a 1.02D MHA-DT-32 engagement (Codex
# #892; the U41 platform precedent).
REFERENCE_DIMENSIONS = {"Depth"}

# Marked dimensions imported by the drawing.  The axial seam groove is an
# assembly-match feature, so its representation geometry carries no
# independent size or location dimension; the punch witness prints only its
# location from the hub-seat axis.
# The two end radii are concentric with the hub seat and the handle pivot, so
# they locate both on the arm's mid-width axis; the former common-axis offset
# restated that and is gone with the square end.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"BossRadius", "EndRadius"},
    "FiducialProfile": {"FiducialX", "FiducialY"},
    "Arm": {"Depth"},
    "HubSeatProfile": {"HubSeatDia"},
    "StationReference": {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "Width",
    },
}

# Decimal places are authored on the model.  The hub seat bore is a one-place
# .X size: it is bored first, and MHA-DT-31 is turned to suit it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ArmOutline": {"BossRadius": 1, "EndRadius": 1},
    "FiducialProfile": {"FiducialX": 1, "FiducialY": 1},
    "Arm": {"Depth": 1},
    "HubSeatProfile": {"HubSeatDia": 1},
    "StationReference": {
        "PivotStation": 1,
        "AnchorStation": 1,
        "AnchorOffset": 1,
        "Width": 1,
    },
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

# The one sheet-derived dimension: the parenthesised extreme-to-extreme
# overall, a read-only sum of the two end radii and the pivot station with no model
# dimension to import. Its places are still specification, so the sheet
# reads them here instead of typing a literal (drawing-simplicity-policy.md `How the repository implements the guidelines`).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 1}

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): at most four short lines, each under ~75 characters so the
# block stays left of the title block.  The section line is a requirement,
# not a convenience: the U29 cheek around the hub seat reaches 2 mm only at
# the mill's width tolerance, not at the .X band.  The #4-40 handle pivot
# (user ruling 2026-09-30) clears the 1.5D engagement rule, so the sheet no
# longer states the #8-32's named exception.  The fiducial and the pivot
# tap's mouth limit are flagged at their features (dt_crank_arm_notes).
STOCK_NOTE = (
    f"{ARM_WIDTH:.1f} x {ARM_THICKNESS:.1f} SECTION: "
    f"{ARM_WIDTH / MM_PER_IN:g} x {ARM_STOCK_THICKNESS_IN} IN CF FLAT BAR AS SUPPLIED."
)
DRAWING_NOTES = STOCK_NOTE
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
