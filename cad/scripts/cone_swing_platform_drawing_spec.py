r"""Print-only data for the MHA-091 cone swing platform sheet.

PURE DATA.  ``build_cone_swing_platform`` marks and places these dimensions on
the part (the model owns its decimal places) and ``draw_cone_swing_platform``
imports exactly ``DRAWING_DIMENSIONS``.  Kept out of
``cone_swing_platform_spec`` so a print edit re-keys only the platform part and
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
    "TipScrewSlotProfile": {"TipSlotEastCx", "TipSlotWestCx", "TipSlotZ", "TipSlotW"},
    "TipScrewCboreProfile": {"TipCboreW"},
    "TipScrewCbore": {"TipCboreDepth"},
    "CornerNE": {"CornerNER"},
    "CornerNW": {"CornerNWR"},
    "CornerSW": {"CornerSWR"},
    "CornerSE": {"CornerSER"},
}

# Decimal places ARE the tolerance statement (drawing-simplicity policy rule
# 2), so the MODEL owns them: build_cone_swing_platform applies this map to the
# .SLDPRT and draw_cone_swing_platform only reads it back. The whole plate
# outline prints one place (+/-0.8): the east edge at the swing stop and the
# west edge at the notch mouth spend the disengaged lock-collar margin, which
# build_cone_swing_platform.DISENGAGE_COLLAR_MARGIN sizes to keep >= 2.0 mm
# at this band.  Relief diameter, tapped-hole pattern and notch stay at the
# .XX grade. Relief
# depth is a reference nominal governed by the matched fit above. The Hole
# Wizard owns the pivot-hole size/callout.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "PlateProfile": {
        "NorthEastX": 1,
        "NorthEdgeZ": 1,
        "NorthWestX": 1,
        "SouthWestX": 1,
        "PlateLenDim": 1,
        "SouthEastX": 1,
    },
    "Plate": {"PlateThk": 2},
    "PivotBearingReliefProfile": {"PivotBearingReliefDia": 2},
    "PivotBearingRelief": {"PivotBearingReliefDepth": 2},
    "PostMountHoles": {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    },
    "LockNotchCapEProfile": {"CapECx": 2, "CapECz": 2, "CapEDia": 2},
    # The slot ends are .XX so the +/-2.25 fit-up travel keeps >= +/-1.74.
    "TipScrewSlotProfile": {
        "TipSlotEastCx": 2,
        "TipSlotWestCx": 2,
        "TipSlotZ": 2,
        "TipSlotW": 1,
    },
    "TipScrewCboreProfile": {"TipCboreW": 2},
    "TipScrewCbore": {"TipCboreDepth": 2},
    "CornerNE": {"CornerNER": 1},
    "CornerNW": {"CornerNWR": 1},
    "CornerSW": {"CornerSWR": 1},
    "CornerSE": {"CornerSER": 1},
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
