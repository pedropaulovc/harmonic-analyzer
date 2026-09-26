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

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec
from _surface_finish import SurfaceFinishControl
from crank_handle_pivot_screw_spec import FULL_THREAD_WORST_DIAMETERS_PRINTED
from crank_handle_pivot_screw_spec import THREAD_SIZE as PIVOT_SCREW_THREAD_SIZE
from crank_hub_geometry import (
    ARM_FIDUCIAL_RADIUS,
    ARM_STOCK_THICKNESS,
    ARM_STOCK_THICKNESS_IN,
    ARM_THICKNESS,
    ARM_WIDTH,
    AXIAL_PIN_DIA,
    AXIAL_PIN_LENGTH,
    AXIAL_PIN_RADIUS_FROM_AXIS,
    FIDUCIAL_MODEL_DEPTH,
    FIDUCIAL_MODEL_DIA,
    GENERAL_1PL_TOL_MM,
    HUB_SEAT_DIA,
    MM_PER_IN,
    WALL_TARGET_MM,
)


# --- Nominal geometry -------------------------------------------------------
ARM_C2C = 75.0
SQUARE_END_OVERHANG = 10.0
# The bar is left at its as-supplied thickness, so that stock must read as the
# printed 8.0 inside the title block's .X band.
if abs(ARM_STOCK_THICKNESS - ARM_THICKNESS) > GENERAL_1PL_TOL_MM:
    raise AssertionError(
        f"arm stock {ARM_STOCK_THICKNESS:.3f} is outside the printed {ARM_THICKNESS:.1f}'s .X band"
    )
# U33: the MHA-139 slotted shoulder screw threads through the arm and carries
# the handle.  Its tapped web to the square end is judged at the .X worst case
# of both stations (U27).
HANDLE_PIVOT_HOLE_SPEC = HoleSpec("tapped", PIVOT_SCREW_THREAD_SIZE)
_PIVOT_THREAD_R = THREAD_MAJOR_MM[HANDLE_PIVOT_HOLE_SPEC.size] / 2.0
PIVOT_END_WEB_NOMINAL = SQUARE_END_OVERHANG - _PIVOT_THREAD_R
PIVOT_END_WEB_WORST = PIVOT_END_WEB_NOMINAL - 2.0 * GENERAL_1PL_TOL_MM
if PIVOT_END_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"handle-pivot thread leaves {PIVOT_END_WEB_WORST:.2f} mm to the arm end"
    )

# The axial MHA-138 groove is match-drilled in the assembled arm/hub.  Its
# centre rides the hub-seat interface at six o'clock (toward the hanging handle);
# the 4-mm length is shared as exactly half the 8-mm arm thickness.
AXIAL_PIN_X = AXIAL_PIN_RADIUS_FROM_AXIS
AXIAL_PIN_Y = 0.0

# Restrained visual representation of the two alignment witnesses.  The arm
# owns one shallow punched mark; the matching mark is on the crankshaft dome.
# Neither diameter nor depth is a manufacturing dimension on the print.
_FIDUCIAL_AXIS = ARM_FIDUCIAL_RADIUS / math.sqrt(2.0)
FIDUCIAL_X = -_FIDUCIAL_AXIS
FIDUCIAL_Y = _FIDUCIAL_AXIS

# Keeper-ring anchor (ch11 p.14): a small slotted screw in the arm's outboard
# face clamps the brass eyelet that once tethered removable pin MHA-024.
# Tapped THRU the 5/16 bar (policy rule 12, audit W7): a blind 6.5 drill left
# its point 0.76 from the inboard face nominal and through it at the printed
# band; through, the screw has 7.94 of thread (2.79D) and nothing to bottom on.
ANCHOR_SCREW_X = 20.0
ANCHOR_SCREW_Y = 4.5
ANCHOR_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# MHA-137 is a light press in MHA-020 and pinned; nothing runs in this part.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived spans.
ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG
HALF_WIDTH = ARM_WIDTH / 2.0

# The thickness prints as a reference, (8.0), under the stock line's "AS
# SUPPLIED": the bar's mill tolerance governs it, not the title block's .X
# band, which would accept a 7.2 arm and a 1.02D MHA-139 engagement (Codex
# #892; the U41 platform precedent).
REFERENCE_DIMENSIONS = {"Depth"}

# Marked dimensions imported by the drawing.  The punch and axial seam groove
# are assembly-match features, so their representation geometry carries no
# independent size or location dimension.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ArmOutline": {"ArmEndX", "BossRadius"},
    "Arm": {"Depth"},
    "HubSeatProfile": {"HubSeatDia"},
    "StationReference": {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "AxisOffset",
        "Width",
    },
}

# Decimal places are authored on the model.  The hub seat bore is a one-place
# .X size: it is bored first, and MHA-137 is turned to suit it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ArmOutline": {"ArmEndX": 1, "BossRadius": 1},
    "Arm": {"Depth": 1},
    "HubSeatProfile": {"HubSeatDia": 1},
    "StationReference": {
        "PivotStation": 1,
        "AnchorStation": 1,
        "AnchorOffset": 1,
        "AxisOffset": 1,
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

# The one sheet-derived dimension: the parenthesised boss-extreme-to-arm-end
# overall, a read-only sum of the boss radius and ArmEndX with no model
# dimension to import. Its places are still specification, so the sheet
# reads them here instead of typing a literal (policy rule 2).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 1}

# Policy rule 6: at most four short lines, each under ~75 characters so the
# block stays left of the title block.  The section line is a requirement,
# not a convenience: the U29 cheek around the hub seat reaches 2 mm only at
# the mill's width tolerance, not at the .X band.  The third line states the
# MHA-139 named exception on the sheet that is tapped for it (user ruling
# 2026-09-25, MHA-020 review B2), with the worst case the screw spec derives
# from the stock thickness -- the same line and number MHA-139 prints.
STOCK_NOTE = (
    f"{ARM_WIDTH:.1f} x {ARM_THICKNESS:.1f} SECTION: "
    f"{ARM_WIDTH / MM_PER_IN:g} x {ARM_STOCK_THICKNESS_IN} IN CF FLAT BAR AS SUPPLIED."
)
PIVOT_ENGAGEMENT_EXCEPTION = (
    f"{HANDLE_PIVOT_HOLE_SPEC.size} THREAD ENGAGEMENT "
    f"{FULL_THREAD_WORST_DIAMETERS_PRINTED:.2f}D MIN: NAMED EXCEPTION TO RULE 12."
)
DRAWING_NOTES = "\n".join(
    (
        "PUNCH FIDUCIAL MARK WHERE SHOWN; LOCATE BY EYE.",
        STOCK_NOTE,
        PIVOT_ENGAGEMENT_EXCEPTION,
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
