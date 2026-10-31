r"""Print-only data for the MHA-DT-20 cone swing platform sheet.

PURE DATA.  ``build_dt_cone_swing_platform`` marks and places these dimensions on
the part (the model owns its decimal places) and ``draw_dt_cone_swing_platform``
imports exactly ``DRAWING_DIMENSIONS``.  Kept out of
``dt_cone_swing_platform_spec`` so a print edit re-keys only the platform part and
its sheet, not the harmonic base or the drive train that read the spec.
"""

from __future__ import annotations


# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  The pivot-hole centre is the layout origin: every plan corner,
# both post-mount taps and the lock notch are located from it in the plate's own
# axes (station along the cone axis, offset across it), so a shop lays the whole
# plate out from one scribed centre.  Corner radii come off their fillets. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "PlateProfile": {
        "NorthEastX",
        "NorthEdgeZ",
        "NorthWestX",
        "SouthWestX",
        "PlateLenDim",
        "SouthEastX",
    },
    "Plate": {"PlateThk"},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia"},
    "PivotBearingRelief": {"PivotBearingReliefDepth"},
    "PostMountHoles": {
        "PostMountWestX",
        "PostMountWestZ",
        "PostMountEastX",
        "PostMountEastZ",
    },
    "LockNotchCapEProfile": {"CapECx", "CapECz", "CapEDia"},
    # The tip-block hold-down's two stations from the pivot bore; the native
    # Hole Wizard callout carries its sizes.
    "HoldDownHole": {"HoldDownX", "HoldDownZ"},
    "CornerNE": {"CornerNER"},
    "CornerNW": {"CornerNWR"},
    "CornerSW": {"CornerSWR"},
    "CornerSE": {"CornerSER"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity-policy.md `How the repository implements the guidelines`
# ), so the MODEL owns them: build_dt_cone_swing_platform applies this map to the
# .SLDPRT and draw_dt_cone_swing_platform only reads it back. The whole plate
# outline, its corner radii, the relief diameter and the notch print .XX inch
# (#290); the east edge at the swing stop and the west edge at the notch mouth
# spend the disengaged lock-knob head margin
# (dt_cone_swing_platform_geometry.DISENGAGE_HEAD_MARGIN).  The tapped-hole
# pattern and the hold-down's station along the cone axis are post- and
# tip-block closures, off the grid, so they print .XXX; with HoldDownX they
# carry the explicit bands the tip-block stacks need
# (dt_cone_swing_platform_spec).  Relief depth is a reference nominal governed
# by the matched fit above. The Hole Wizard owns the pivot- and hold-down-hole
# sizes/callouts.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "NorthEastX": 2,
        "NorthEdgeZ": 2,
        "NorthWestX": 2,
        "SouthWestX": 2,
        "PlateLenDim": 2,
        "SouthEastX": 2,
    },
    "Plate": {"PlateThk": 2},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia": 2},
    "PivotBearingRelief": {"PivotBearingReliefDepth": 3},
    "PostMountHoles": {
        "PostMountWestX": 3,
        "PostMountWestZ": 3,
        "PostMountEastX": 3,
        "PostMountEastZ": 3,
    },
    "LockNotchCapEProfile": {"CapECx": 2, "CapECz": 2, "CapEDia": 2},
    # Banded on the part (HOLDDOWN_STATION_TOL_MM).
    "HoldDownHole": {"HoldDownX": 2, "HoldDownZ": 3},
    "CornerNE": {"CornerNER": 2},
    "CornerNW": {"CornerNWR": 2},
    "CornerSW": {"CornerSWR": 2},
    "CornerSE": {"CornerSER": 2},
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


# View scales differ from the sheet scale and therefore remain property-linked
# labels.  The split plans are named so each dimension set has an unambiguous
# owner; these are view captions, not manufacturing notes.
PROFILE_VIEW_NOTE = "PLATE PROFILE — SCALE 1:2"
FEATURE_VIEW_NOTE = "HOLE LOCATIONS — SCALE 1:2"
NOTCH_VIEW_NOTE = "LOCK NOTCH — SCALE 1:2"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"

# Feature-callout wording is specification data; the drawing owns placement.
# Name features, not compass directions: the plan maps model north downward.
RELIEF_WIDTH_CALLOUT = "TOP RELIEF\nCTR ON PIVOT\nOPEN THRU\nPIVOT END"
PIVOT_BORE_CALLOUT_BELOW = ("RUNNING FIT ON MHA-DT-VN-52 SHOULDER",)
POST_MOUNT_LOCATING_CALLOUT = "LOCATES MHA-DT-05 CONE PIVOT POST"
# A drawing number identifies the hold-down's mate without lengthening its
# leader shelf into the title block.
HOLDDOWN_CALLOUT_BELOW = ("FROM UNDERSIDE", "LOCATES MHA-DT-21")
# The process belongs to the THRU row, not the counterbore-diameter row.
HOLDDOWN_PROCESS = "DRILL"
PIVOT_PROCESS = "REAM"
TOP_FACE_LABEL = "TOP FACE"
UNDERSIDE_LABEL = "UNDERSIDE"
