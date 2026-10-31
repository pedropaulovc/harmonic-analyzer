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

import _config
from _hole_spec import THREAD_MAJOR_MM, HoleSpec
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_deviations
from _surface_finish import SurfaceFinishControl
from dt_crank_handle_pivot_screw_spec import THREAD_SIZE as PIVOT_SCREW_THREAD_SIZE
from dt_crank_hub_geometry import (
    ARM_THICKNESS,  # noqa: F401 -- re-exported to the build and the drive train
    ARM_WIDTH,
    AXIAL_PIN_DIA,  # noqa: F401 -- re-exported to the build and drawing
    AXIAL_PIN_LENGTH,  # noqa: F401 -- re-exported to the build
    AXIAL_PIN_RADIUS_FROM_AXIS,
    FIDUCIAL_MODEL_DEPTH,  # noqa: F401 -- re-exported to the build
    FIDUCIAL_MODEL_DIA,  # noqa: F401 -- re-exported to the build and drawing
    HUB_SEAT_DIA,
)

# Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Lengths
# stay physical millimetres, each arm-owned nominal the exact decimal of its
# printed inch value.
UNIT = drawing_unit("parts/dt-crank-arm", _config.parts("dt-crank-arm"))
EDGE_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)


# --- Nominal geometry -------------------------------------------------------
ARM_C2C = 74.93  # 2.95
# User ruling 2026-09-29 (ch11 p.14 photo re-check): the handle end is a full
# semicircle concentric with the handle pivot, the same R.50 as the hub end.
END_RADIUS = ARM_WIDTH / 2.0
# U33: the MHA-DT-32 slotted shoulder screw threads through the arm and carries
# the handle.  The end arc shares the pivot's centre, so its tapped web to the
# end is judged at the printed worst case of the end radius alone (U27).
HANDLE_PIVOT_HOLE_SPEC = HoleSpec("tapped", PIVOT_SCREW_THREAD_SIZE)
_PIVOT_THREAD_R = THREAD_MAJOR_MM[HANDLE_PIVOT_HOLE_SPEC.size] / 2.0
_END_RADIUS_LOWER, _END_RADIUS_UPPER = printed_deviations(END_RADIUS, 2, unit=UNIT)
PIVOT_END_WEB_NOMINAL = END_RADIUS - _PIVOT_THREAD_R
PIVOT_END_WEB_WORST = PIVOT_END_WEB_NOMINAL + _END_RADIUS_LOWER
if PIVOT_END_WEB_WORST < WALL_TARGET_MM:
    raise AssertionError(
        f"handle-pivot thread leaves {PIVOT_END_WEB_WORST:.2f} mm to the arm end"
    )

# The axial MHA-DT-VN-59 groove is match-drilled in the assembled arm/hub.  Its
# centre rides the hub-seat interface at six o'clock (toward the hanging handle);
# its length is shared as exactly half the arm thickness.
AXIAL_PIN_X = AXIAL_PIN_RADIUS_FROM_AXIS
AXIAL_PIN_Y = 0.0

# The arm owns one shallow punched alignment witness; the matching mark is on
# the crankshaft (MHA-DT-11) dome, and the drive-train assembly lines the two up
# before the taper ream.  Its diameter and depth are a visual representation,
# never printed; its centre prints as two ordinates from the hub-seat axis.
#
# The centre must land on the flat outboard face at every accepted part
# (codjiflo P2 on #2005: the first band was checked against the nominal bore).
# That face's worst-case annulus runs from the seat bore's printed upper limit
# plus its edge break out to the boss end's printed lower limit less its break.
FIDUCIAL_FACE_RADII = (
    (HUB_SEAT_DIA + printed_deviations(HUB_SEAT_DIA, 2, unit=UNIT)[1]) / 2.0
    + EDGE_BREAK_MAX_MM,
    END_RADIUS + _END_RADIUS_LOWER - EDGE_BREAK_MAX_MM,
)
# The mark stands at 135 degrees near that annulus's mid-radius, each ordinate
# .31 at the title block's .XX: anywhere in that square band the centre stays
# on the face.
_FIDUCIAL_AXIS = 7.874  # .31
FIDUCIAL_X = -_FIDUCIAL_AXIS
FIDUCIAL_Y = _FIDUCIAL_AXIS
FIDUCIAL_RADIAL_LIMITS = tuple(
    2.0**0.5 * (_FIDUCIAL_AXIS + deviation)
    for deviation in printed_deviations(_FIDUCIAL_AXIS, 2, unit=UNIT)
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
# Tapped THRU the 5/16 bar (drawing-guidelines.md rule 17 (walls and webs),
# audit W7): through, the screw has the whole bar of thread and nothing to
# bottom on.
ANCHOR_SCREW_X = 20.066  # .79
ANCHOR_SCREW_Y = 4.572  # .18
ANCHOR_HOLE_SPEC = HoleSpec("tapped", "#4-40")

# MHA-DT-31 is a light press in MHA-DT-06 and pinned; nothing runs in this part.
SURFACE_FINISHES: tuple[SurfaceFinishControl, ...] = ()

# Derived spans.
ARM_END_X = ARM_C2C + END_RADIUS
HALF_WIDTH = ARM_WIDTH / 2.0

# The thickness prints as a reference under the stock line's "AS SUPPLIED":
# the bar's mill tolerance governs it, not a title-block band, which would
# accept a thinner arm and a short MHA-DT-32 engagement (Codex #892; the U41
# platform precedent).  The width is the same bar's as-rolled 1 in, printed
# as the supplier's fraction (STOCK_FRACTION_DENOMINATOR).
REFERENCE_DIMENSIONS = {"Depth"}
STOCK_FRACTION_DENOMINATOR = 16
STOCK_FRACTION_DIMENSIONS = {"Width": ARM_WIDTH}

# Marked dimensions imported by the drawing.  The axial seam groove is an
# assembly-match feature, so its representation geometry carries no
# independent size or location dimension; the punch witness prints only its
# location from the hub-seat axis.
# The two end radii are concentric with the hub seat and the handle pivot, so
# they locate both on the arm's mid-width axis.
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

# Decimal places are authored on the model: every arm dimension takes the
# title block's .XX.  The hub seat bore is made first at that band, and
# MHA-DT-31 is turned to suit it.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: dict.fromkeys(names, 2) for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

# The one sheet-derived dimension: the parenthesised extreme-to-extreme
# overall, a read-only sum of the two end radii and the pivot station with no model
# dimension to import. Its places are still specification, so the sheet
# reads them here instead of typing a literal (drawing-simplicity-policy.md `How the repository implements the guidelines`).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 2}

# drawing-guidelines.md rule 7 (notes: few, flagged, never a method): one
# short line.  The section line is a requirement, not a convenience: the U29
# cheek around the hub seat reaches its wall only at the mill's width
# tolerance.  The fiducial and the pivot tap's mouth limit are flagged at
# their features (dt_crank_arm_notes).
STOCK_NOTE = "WIDTH AND THICKNESS: CF FLAT BAR AS SUPPLIED."
DRAWING_NOTES = STOCK_NOTE
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
