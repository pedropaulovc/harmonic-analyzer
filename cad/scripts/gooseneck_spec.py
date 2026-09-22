r"""Pure-data dimensional contract shared by the gooseneck post and its drawing.

PURE DATA, no SolidWorks/COM imports. ``build_gooseneck`` imports the marked
dimension, precision and note contract; ``draw_gooseneck`` partitions the same
model-owned dimensions among the elevation, post-end and joint-section views.
"""

from __future__ import annotations



# Per-view native-dimension partitions. The part marks their union; each drawing
# view imports only the dimensions whose source plane projects truthfully there.
# Plug and screw are Front-plane revolves, so the z=0 joint section carries
# their side-view diameters and lengths; the slot detail enlarges that section.
ELEVATION_DIMENSIONS: dict[str, set[str]] = {
    "Leg": {"LegLength"},
    "BendPath": {"BendRadius", "ArmRun"},
}
POST_SECTION_DIMENSIONS: dict[str, set[str]] = {
    "LegProfile": {"TubeDia", "TubeBoreDia"},
}
JOINT_DIMENSIONS: dict[str, set[str]] = {
    "EndPlugProfile": {"PlugDia", "TapMinorDia", "PlugDepth"},
    "ScrewProfile": {
        "ScrewHeadDia",
        "ScrewShankDia",
        "HeadThickness",
        "UnderHeadLength",
    },
}
SLOT_DETAIL_DIMENSIONS: dict[str, set[str]] = {
    "ScrewSlotProfile": {"SlotDepth", "SlotWidth"},
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {}
for _partition in (
    ELEVATION_DIMENSIONS,
    POST_SECTION_DIMENSIONS,
    JOINT_DIMENSIONS,
    SLOT_DETAIL_DIMENSIONS,
):
    for _feature, _names in _partition.items():
        DRAWING_DIMENSIONS.setdefault(_feature, set()).update(_names)

# Decimal places are the tolerance statement (policy rule 2), so the model owns
# them and the drawing verifies readback. The calibration-critical 50.80 arm
# reach prints to two places; routine formed length/radius print to one.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LegProfile": {"TubeDia": 2, "TubeBoreDia": 2},
    "Leg": {"LegLength": 1},
    "BendPath": {"BendRadius": 1, "ArmRun": 2},
    "EndPlugProfile": {"PlugDia": 2, "TapMinorDia": 3, "PlugDepth": 2},
    "ScrewProfile": {
        "ScrewShankDia": 3,
        "UnderHeadLength": 2,
        "ScrewHeadDia": 2,
        "HeadThickness": 2,
    },
    "ScrewSlotProfile": {"SlotDepth": 2, "SlotWidth": 2},
}

DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if len(DRAWING_PRECISION_BY_NAME) != sum(
    len(dimensions) for dimensions in DRAWING_PRECISION.values()
):
    raise AssertionError("two features share a gooseneck drawing dimension name")
for _feature, _dimensions in DRAWING_PRECISION.items():
    _unmarked = sorted(set(_dimensions) - DRAWING_DIMENSIONS.get(_feature, set()))
    if _unmarked:
        raise AssertionError(
            f"DRAWING_PRECISION names unmarked dimensions on {_feature}: {_unmarked}"
        )

# Ø11.85 is the nominal model size only. Stock tube ID is not assumed accurate:
# match the identified plug to the ACTUAL assigned bore. The filler supplier's
# 0.002-0.005 in joint gap is clearance between facing surfaces, hence radial.
PLUG_FIT_CALLOUT = (
    "MATCH-FIT TO ACTUAL MHA-032 TUBE BORE\n"
    "0.051-0.127 RADIAL CLEARANCE\n"
    "CENTER CONCENTRIC; SILVER-BRAZE AWS A5.8 BAg-7"
)
TAP_CALLOUT = "#6-32 UNC-2B THRU"
SCREW_CALLOUT = "#6-32 UNC-2A"

# Only non-dimensional fabrication/functional facts remain in notes. Coating
# lives in the title-block Finish field and every size is a native dimension.
DRAWING_NOTES = "\n".join(
    (
        "FULL FAYING-SURFACE BRAZE PENETRATION; NO OPEN VOIDS.",
        "BEND OVALITY 5% MAX; NO FLATS, KINKS OR CRACKS.",
        "DEFAULT SHOWN CLAMPED; LOOSEN SCREW FOR EYE INSTALLATION, THEN RETIGHTEN.",
    )
)
# Section and detail views carry SolidWorks' native label (letter + scale);
# only the unlabelled model views need a caption note.
ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
