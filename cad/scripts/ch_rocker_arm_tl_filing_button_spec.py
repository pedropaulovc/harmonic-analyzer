r"""Pure-data contract for the rocker arm hub filing button (MHA-CH-006-TL-04).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's hub filing hold (prechips S3F) two buttons ride the headed filing
stud (MHA-CH-006-TL-05) that locates in the arm's reamed pivot bore: one seats
on each hub face, the stud's nut clamps the arm between them, and the hub is
filed down until the file rides on both hardened rims all round. The rim is
the filing line, so the button O.D. is the hub O.D. Two are made, O1 drill
rod torch-hardened and lapped (shop-additions section 1: the shop has no
grinder, so bore, faces and O.D. are lapped).

Frame: the button axis is model +Z (the inventory fixture frame's stud axis),
the hub-seating face at Z0 and the outer face at +Z.
"""

from __future__ import annotations

import ch_rocker_arm_spec as rocker
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace

THICKNESS = 4.0
THICKNESS_PLACES = 2

# The rim is the filing line: the button O.D. is the hub O.D. Codex round 3
# found the shop-additions 0.010 lapped band unsupported: the hub prints at
# two places, so the three-place general band already holds the filed hub
# far inside it, and a hub taper inside that band is harmless.
OD = rocker.HUB_DIA
OD_PLACES = 3
OD_BAND = (limits(OD, OD_PLACES)[1] - OD, limits(OD, OD_PLACES)[0] - OD)
if not (-rocker.LINEAR_2PL <= OD_BAND[1] and OD_BAND[0] <= rocker.LINEAR_2PL):
    raise AssertionError("filing-button rim band leaves the hub O.D. band")

# Barrel-lapped bore: its limits give the stud body (stud spec) the slip
# clearance that holds the rim concentric to the arm's pivot bore.
BORE_DIA = 6.51
BORE_BAND = (0.005, -0.005)
BORE_PLACES = 3

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": OD_PLACES, "BoreDia": BORE_PLACES},
    "Disc": {"DiscThick": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-button dimension needs authored places")

SURFACE_FINISHES = ()
# The blind reviewer sees only the sheet: each note states why a band is
# tight. Hardness and the lapped surfaces live in the Finish field.
DRAWING_NOTES = (
    "RIM SETS THE FILED DIAMETER OF THE ROCKER ARM HUB; O.D. ROUND AND TRUE TO BORE.\n"
    "BORE LIMITS GIVE THE FILING STUD THE CLEARANCE THAT KEEPS THE RIM ON CENTRE.\n"
    "KEEP RIM CORNERS SHARP; STONE BURRS ONLY. THICKNESS LOCATES THE STACK."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 4:1"

_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "rim": ExportFeature(
        kind="boss",
        faces=(CylinderFace(OD),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (
                limits(OD, OD_PLACES),
                ("OD", "OD_BAND", ("ch_rocker_arm_spec", "HUB_DIA")),
            ),
            "dia_nominal": (OD, ("OD", ("ch_rocker_arm_spec", "HUB_DIA"))),
        },
        precision={"dia": OD_PLACES},
    ),
    "bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(BORE_DIA),),
        requirements=("dia", "thru"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia": (limits(BORE_DIA, BORE_PLACES, BORE_BAND), ("BORE_DIA", "BORE_BAND")),
            "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
            "thru": (True, ("BORE_DIA",)),
            "process": ("lap", ("BORE_BAND",)),
        },
        precision={"dia": BORE_PLACES},
    ),
    "hub_seat_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "thickness": (limits(THICKNESS, THICKNESS_PLACES), ("THICKNESS",)),
            "thickness_nominal": (THICKNESS, ("THICKNESS",)),
        },
        precision={"thickness": THICKNESS_PLACES},
    ),
    "outer_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), THICKNESS),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": THICKNESS}, ("THICKNESS",)),
            "thickness": (limits(THICKNESS, THICKNESS_PLACES), ("THICKNESS",)),
        },
        precision={"thickness": THICKNESS_PLACES},
    ),
}
