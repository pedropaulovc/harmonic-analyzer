r"""Pure-data dimensional contract shared by the gooseneck post and its drawing.

PURE DATA, no SolidWorks/COM imports. ``build_gooseneck`` imports the marked
dimension, precision and note contract; ``draw_gooseneck`` partitions the same
model-owned dimensions among the elevation, post-end and joint-section views.
"""

from __future__ import annotations



# Per-view native-dimension partitions. The part marks their union; each drawing
# view imports only the dimensions whose source plane projects truthfully there.
# Plug and screw are Front-plane revolves, so a view parallel to the bend plane
# imports their diameters as side-view sizes: the z=0 joint section carries the
# plug in the tube bore, and a screw-only side view carries the screw.
ELEVATION_DIMENSIONS: dict[str, set[str]] = {
    "Leg": {"LegLength"},
    "BendPath": {"BendRadius", "ArmRun"},
}
POST_SECTION_DIMENSIONS: dict[str, set[str]] = {
    "LegProfile": {"TubeDia", "TubeBoreDia"},
}
JOINT_DIMENSIONS: dict[str, set[str]] = {
    "EndPlugProfile": {"PlugDia", "TapMinorDia", "PlugDepth"},
}
SCREW_DIMENSIONS: dict[str, set[str]] = {
    "ScrewProfile": {
        "ScrewHeadDia",
        "ScrewShankDia",
        "HeadThickness",
        "UnderHeadLength",
    },
    "ScrewSlotProfile": {"SlotDepth", "SlotWidth"},
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {}
for _partition in (
    ELEVATION_DIMENSIONS,
    POST_SECTION_DIMENSIONS,
    JOINT_DIMENSIONS,
    SCREW_DIMENSIONS,
):
    for _feature, _names in _partition.items():
        DRAWING_DIMENSIONS.setdefault(_feature, set()).update(_names)

# The tube is purchased stock that nobody cuts, so its Ø16 and Ø12 print as
# REFERENCE and Material names the stock (Main ruling on Codex machinist r19 B1;
# the U41 swing-plate precedent). The wall is then the mill's, not a machining
# band: ASTM A519-03 Table 8 footnote B sends an ID under 1/2 in (ours is
# 0.472 in) to Table 9, which holds a wall <= 25% of OD with an ID up to
# 1.499 in to +/-10.0%. So 2.0 * 0.9 = 1.80 min straight. Outer-fibre thinning
# at the R51 bend is about 2R/(2R + OD) = 0.864, so 1.56 at the bend: at or
# above rule 12's 1.5 floor, which covers MACHINED walls anyway. A519/A519M-24a
# was not checked (paywalled).
TUBE_STOCK_WALL_TOL = 0.10

# Decimal places are the tolerance statement (policy rule 2), so the model owns
# them and the drawing verifies readback. Formed lengths and radii print to one
# place: the arm run enters the counter moment about 1:1, so +/-0.8 on it is
# about +/-1% of moment against the purchased spring's +/-10%, which setup
# re-tensions anyway. So do the screw's under-head length (the through thread
# adjusts it), the plug length (thread engagement, not a fit), the screw
# head (sized so the slot web holds 2 mm at the worst case of this band) and
# the head diameter (eye retention, not a fit; Codex machinist r19). At
# Ø12.8 the head still clears the counter spring's raised half-turn by 1.26 mm.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LegProfile": {"TubeDia": 1, "TubeBoreDia": 1},
    "Leg": {"LegLength": 1},
    "BendPath": {"BendRadius": 1, "ArmRun": 1},
    "EndPlugProfile": {"PlugDia": 2, "TapMinorDia": 3, "PlugDepth": 1},
    "ScrewProfile": {
        "ScrewShankDia": 3,
        "UnderHeadLength": 1,
        "ScrewHeadDia": 1,
        "HeadThickness": 1,
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
# Policy rule 12 (U27) engagement: all of the worst-case 6.2 plug (7.0 at .X)
# is FULL thread, 1.77D. The plug is tapped through, so it has no tap-lead
# loss, and in the installed, clamped state the screw passes fully through it
# (9.58 reach at worst case), so its tip threads sit past the plug. The 8.0
# open gap is assembly access only: the eye hangs loose and the screw carries
# no clamp load, so it is not a load case for engagement (Main ruling on Codex
# machinist r19 B2). This lives here, not in gooseneck_geom, which the channel,
# magnifier and summing recipes read.
TAP_CALLOUT = "#6-32 UNC-2B THRU"
# The bend radius is the tube-bender's centreline radius; its imported
# dimension rides the (unshown) sweep path, so the sheet says so.
BEND_RADIUS_CALLOUT = "AT TUBE CENTERLINE"
SCREW_CALLOUT = "#6-32 UNC-2A"

# Only non-dimensional fabrication/functional facts remain in notes. Coating
# lives in the title-block Finish field and every size is a native dimension.
DRAWING_NOTES = "\n".join(
    (
        "FULL FAYING-SURFACE BRAZE PENETRATION; NO OPEN VOIDS.",
        "BEND OVALITY 5% MAX; NO FLATS, KINKS OR CRACKS.",
        "SCREW SHOWN CLAMPED; GAP UNDER HEAD = SPRING-EYE SEAT (EYE NOT SHOWN).",
        "LOOSEN SCREW FOR EYE INSTALLATION, THEN RETIGHTEN.",
    )
)
# Section and detail views carry SolidWorks' native label (letter + scale);
# only the unlabelled model views need a caption note.
# The one drawing-created dimension (overall height) is the read-only sum of
# model-owned sizes: no model dimension to import and no tolerance to carry.
# Its places are still specification, so the part hands them over here.
DRAWING_REFERENCE_PRECISION = 1

ELEVATION_VIEW_NOTE = "ELEVATION SCALE 1:3"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:3"
# The screw is not plated with the tube and plug (see the part's finish), so
# its own finish rides its view caption: stated once, next to the screw.
SCREW_VIEW_NOTE = "ADJUSTMENT SCREW SHOWN ALONE SCALE 7:1\nBLACK OXIDE, NOT PLATED"
# The plan view only carries cutting line A-A, but it prints at 1:2 on a 1:3
# sheet, so it is captioned like any unlabelled model view.
PLAN_VIEW_NOTE = "PLAN VIEW SCALE 1:2"
