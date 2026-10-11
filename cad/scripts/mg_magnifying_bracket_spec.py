r"""Magnifying-bracket dimensional contract -- the single source of truth shared
by the part build (``build_mg_magnifying_bracket.py``) and its manufacturing
drawing (``draw_mg_magnifying_bracket.py``).

PURE DATA, no SolidWorks/COM imports.  Nothing else imports this bracket's
nominals -- the magnifier assembly places it BY NAME and mates it by named
references (never a Python constant), so one ``_spec`` module is right here (no
``_geom`` split, unlike the magnifying LEVER whose knife-axis station an
assembly imports).  The offline lockstep test asserts the part marks and the
drawing keeps EXACTLY ``DRAWING_DIMENSIONS``.

The bracket is a three-feature fitting: an extruded COLLAR tube (Ø12 OD, 10
long about local X) whose bore is the PRESS seat for the Ø6 magnifying-lever
rod (nominal and band from ``mg_lever_press_fit_geom``, the joint's one read
point), a rectangular ARM cantilevering +Z to the summing plate, and a mounting
FLANGE that butts the plate's front face.  The two plan rectangles carry the
auto-importable marked dimensions, including the flange thickness band; the
collar's end-view circles carry the OD and the banded bore, and its extrude
the length.  Native counterbore callouts define the through bore and head seat.
"""

from __future__ import annotations
from magnifying_bracket_joint_layout import (
    POSITION_BAND,
    GRIP_MIN,
)

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The two extruded PLAN rectangles auto-import to the top view
# exactly like column_clamp_front's BlockProfile; the arm and flange chains are
# NAME-DISAMBIGUATED in the build (ArmWidth/ArmDepth vs FlangeWidth/FlangeDepth)
# because a shared bare "Width"/"Depth" would collide in the top view's keep
# map.  The collar's annulus sketch (Right plane) imports to the RIGHT end view
# -- the OD and the press-seat bore with its native band -- and the mid-plane
# extrude's one dimension, the collar length, to the top view. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "CollarProfile": {"CollarOd", "CollarBore"},
    "Collar": {"CollarLen"},
    "ArmProfile": {"ArmWidth", "ArmDepth"},
    "FlangeProfile": {"FlangeWidth", "FlangeDepth"},
    "Flange": {"FlangeHeight"},
    "MountingCoordinates": {"MountingX0", "MountingX1", "MountingY0"},
}

# Wizard callout precision is applied in the build through observed native
# dimension names; those identifiers must never be renamed for this contract.
DRAWING_PRECISION = {
    "CollarProfile": {"CollarOd": 2, "CollarBore": 3},
    "Collar": {"CollarLen": 2},
    "ArmProfile": {"ArmWidth": 2, "ArmDepth": 2},
    "FlangeProfile": {"FlangeWidth": 2, "FlangeDepth": 3},
    "Flange": {"FlangeHeight": 2},
}
DRAWING_POSITION_BAND = POSITION_BAND

# True free-text instructions only (policy rule 6): the collar's sizes and the
# bore's band, the arm's section and the mounting pattern are native dimensions
# on the sheet (the bore's callout names the MHA-MG-003 rod), so the notes carry
# the assembly-time press and its retention (the assembly print has no notes;
# user ruling 2026-10-11) and the one named floor exception, nothing the views
# show.
DRAWING_NOTES = "\n".join(
    (
        "PRESS LEVER INTO COLLAR, END FLUSH WITH OUTER FACE.",
        "RETAIN WITH LOCTITE 638.",
        "ALTERNATIVE: SOFT SOLDER OR BRAZE.",
        # Named exception: MHA-MG-001 counterbore floor 1.525 MIN
        # (drawing-simplicity-policy.md, "Named exceptions").
        f"COUNTERBORE FLOOR {GRIP_MIN:.3f} MIN.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"
