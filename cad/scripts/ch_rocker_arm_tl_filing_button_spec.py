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

# The rim is the filing line: the button O.D. is the hub O.D., ring-lapped on
# an arbor in its own bore to a band far inside the hub's printed band.
OD = rocker.HUB_DIA
OD_BAND = (0.005, -0.005)  # (upper, lower) deviations
OD_PLACES = 3
if not (-rocker.LINEAR_2PL <= OD_BAND[1] and OD_BAND[0] <= rocker.LINEAR_2PL):
    raise AssertionError("filing-button rim band leaves the hub O.D. band")

# Barrel-lapped bore: a slip fit on the stud's lapped body.
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
DRAWING_NOTES = (
    "HARDEN AND TEMPER: A FILE SHALL BARELY BITE.\n"
    "BORE, BOTH FACES AND O.D. LAPPED; FACES FLAT AND PARALLEL.\n"
    "LAP THE O.D. ON AN ARBOR IN THE LAPPED BORE.\n"
    "RIM IS THE FILING LINE: STONE BURRS ONLY, KEEP CORNERS SHARP."
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
                limits(OD, OD_PLACES, OD_BAND),
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
