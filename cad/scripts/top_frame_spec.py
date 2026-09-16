r"""Pure-data dimensional contract shared by the top-frame casting and drawing.

PURE DATA, no SolidWorks/COM imports.  ``build_top_frame`` imports the marked-
dimension NAME map, notes and the machined-surface geometry from here;
``draw_top_frame`` keeps exactly ``DRAWING_DIMENSIONS`` and imports the rest of
the casting's plan geometry from ``build_top_frame`` for its view math.

2026-08-02 rederive (ch30 px measurement anchored on the 394x224 column pitch
+ GT bundle rescale + ch19 closeups): the ring absorbed the old top-crossbar
(full-height integral bar) and the gooseneck-clamp (square-head set screw in
the east-rail hub, -X crank side), grew its rails to 34.2/38.0, gained webbed
faces, proud corner bosses, side-screw taps, hanger-stud holes and the
west-rail fulcrum-keeper taps.
"""

from __future__ import annotations

from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from cone_pivot_post_installation import FRAME_FRONT_COLUMN_Z, FRAME_REAR_COLUMN_Z
from frame_attachment_spec import CAP_RECESS_DEPTH, COLUMN_SOCKET_DIAMETER

# --- Machined-surface geometry ------------------------------------------------
#
# The stations and diameters the cut surfaces sit at. They live in the spec (not
# in ``build_top_frame``) because a surface-finish symbol on the sheet has to be
# provenance-checked against the very face spec the casting authors -- see
# ``_drawing_contract``'s drawing-surface-finish-provenance rule. Everything
# else about the plan geometry stays in the build script.
COLUMN_X = 197.0  # column stations (frame.SLDASM)
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z  # -112
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z  # +112
RING_HEIGHT = 36.5  # rail band (ch30 p002 36.7 / p006 37.0 / ch19 img03 35.6)
HALF_H = RING_HEIGHT / 2.0  # 18.25; band local y -18.25..+18.25
BOSS_ABOVE = 4.5  # boss proud of the rail top (corner-crop step)
BORE_DIA = COLUMN_SOCKET_DIAMETER
CAP_RECESS_FLOOR_Y = HALF_H + BOSS_ABOVE - CAP_RECESS_DEPTH  # 6.45
GOOSENECK_X = -COLUMN_X  # east rail, -X crank side (summing's post station)
GOOSENECK_BORE_DIA = 17.0  # O16 post slides through


# --- Machining-required surfaces ---------------------------------------------
#
# Why these nine faces and nothing else. The title block names no grade
# ("CAST/MACHINED"), so a surface that MUST be cut on an otherwise as-cast
# casting has to say so on the face (simplicity policy rule 5: what LOCATES the
# part gets the control).
#
# * The four tube-socket bores take the MHA-083 columns on a match-fitted close
#   hand-slip; a cast bore wall cannot hold that fit and would score the tube.
# * The four cap-recess floors are the axial seats the MHA-133 caps land on --
#   they set the columns' shoulder height, so their roughness is a fit surface,
#   not cosmetic.
# * The gooseneck bore guides the O16 counter-spring post through the hub and
#   is pinched by the set screw against it.
#
# SEAT grade throughout: nothing runs on these surfaces continuously, so the
# commercial machine finish is what the fit needs. The part authors one native
# symbol per qualified face; each sheet states the requirement ONCE, and the
# target text names the family so a single symbol cannot be misread as one
# instance (harmonic-base FLANGE_PERIMETER_TARGET precedent).
SOCKET_BORE_TARGET = "TUBE SOCKET BORES, 4X"
CAP_SEAT_TARGET = "CAP SEAT FLOORS, 4X"
SURFACE_FINISHES = tuple(
    control
    for rail, x in (("east", GOOSENECK_X), ("west", COLUMN_X))
    for end, z in (("front", FRONT_COLUMN_Z), ("rear", REAR_COLUMN_Z))
    for control in (
        SurfaceFinishControl(
            f"socket_{rail}_{end}",
            SEAT_UM,
            CylinderFace(BORE_DIA, contains_x_mm=x, contains_z_mm=z),
            production_method=SOCKET_BORE_TARGET,
        ),
        SurfaceFinishControl(
            f"cap_seat_{rail}_{end}",
            SEAT_UM,
            PlanarFace(
                (0.0, 1.0, 0.0),
                CAP_RECESS_FLOOR_Y,
                contains_x_mm=x,
                contains_z_mm=z,
            ),
            production_method=CAP_SEAT_TARGET,
        ),
    )
) + (
    SurfaceFinishControl(
        "hub_bore",
        SEAT_UM,
        CylinderFace(GOOSENECK_BORE_DIA, contains_x_mm=GOOSENECK_X),
    ),
)


# --- Marked-dimension contract -------------------------------------------------
#
# The hole sizes remain associative callouts; named Hole Wizard placement
# dimensions expose the stations without duplicating those sizes.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OuterProfile": {"Width", "Depth", "WinWidth", "WinDepth"},
    "WebProfile": {
        "WebOuterWidth",
        "WebOuterDepth",
        "WebInnerWidth",
        "WebInnerDepth",
    },
    "WebRing": {"RingHeight"},
    "BossUpProfile": {"C0Dia"},
    "BossesUpper": {"BossTopExtent"},
    "BossesLower": {"BossBottomExtent"},
    "BoreProfile": {"B0X", "B0Z", "B0Dia"},
    "SpotFaceRearProfile": {"S1Dia"},
    "BarProfile": {
        "BarAnchorX",
        "BarAnchorZ",
        "BarFootSpan",
        "GussetRunE",
        "BarSideE",
    },
    "HubBossProfile": {"HubDia"},
    "HubBoss": {"HubBossExtent"},
    "RibProfile": {"RibWidth"},
    "SetPocketProfile": {"PocketRun", "PocketRise"},
    "GooseneckTap": {"SetTapZ"},
    "GooseneckProfile": {"GnX", "GnZ"},
    "StudHoles": {"StudFrontX", "StudFrontZ", "StudRearX", "StudRearZ"},
    "KeeperTaps": {
        "KeeperFrontX",
        "KeeperFrontZ",
        "KeeperRearX",
        "KeeperRearZ",
    },
    "CapRecessProfile": {"CapRecessDia"},
    "CapRecesses": {"CapRecessDepth"},
}


# The nominal socket geometry stays fixed; the assigned actual tube governs fit.
DRAWING_NOTES = (
    "MATCH EACH SOCKET TO ITS ASSIGNED ACTUAL MHA-083 TUBE.\n"
    "CLOSE HAND-SLIP; NO PERCEPTIBLE ROCK.\n"
    "RETAIN CORNER AND ORIENTATION MATCH MARKS."
)
DRAWING_NOTES_B = ""
