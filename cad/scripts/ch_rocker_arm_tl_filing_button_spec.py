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
from _surface_finish import MACHINED_UM, SurfaceFinishControl

THICKNESS = 4.0
THICKNESS_PLACES = 2

# The rim is the filing line: the button O.D. is the hub O.D. Codex round 3
# found the shop-additions 0.010 lapped band unsupported: the hub prints at
# two places, so the three-place general band already holds the filed hub
# far inside it, and a hub taper inside that band is harmless.
OD = rocker.HUB_DIA
OD_PLACES = 3
# A button O.D. of HUB_DIA at the three-place band files the hub to about
# 10.07-10.33, inside the hub's printed two-place O9.69-10.71.
_OD_MIN, _OD_MAX = limits(OD, OD_PLACES)
_HUB_MIN, _HUB_MAX = limits(rocker.HUB_DIA, 2)
if not (_HUB_MIN <= _OD_MIN and _OD_MAX <= _HUB_MAX):
    raise AssertionError("filing-button rim band leaves the hub's printed O.D. band")

# The bore prints as a reference and its fit to the stud governs (callout).
# BORE_BAND is the design intent of that fit for the stud's stack checks
# only; features.toml carries what the print says, the nominal and the note.
BORE_DIA = 6.51
BORE_BAND = (0.005, -0.005)
BORE_PLACES = 3
# Policy rules 2 and 6: the matched fit sits on the bore's callout, naming
# the mate by Number with its acceptance (callout above, callout below).
BORE_FIT_CALLOUT = ("", "SLIDES ON MHA-CH-006-TL-05 STUD BY HAND WITHOUT SHAKE")
BORE_FIT_NOTE = " ".join(part for part in BORE_FIT_CALLOUT if part)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"DiscDia", "BoreDia"},
    "Disc": {"DiscThick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "RingProfile": {"DiscDia": OD_PLACES, "BoreDia": BORE_PLACES},
    "Disc": {"DiscThick": THICKNESS_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked filing-button dimension needs authored places")

# The bore locates on the stud: a machining-required symbol at the project's
# machined grade (codex round 8); the fit callout governs its size.
SURFACE_FINISHES = (SurfaceFinishControl("bore", MACHINED_UM, CylinderFace(BORE_DIA)),)
# The blind reviewer sees only the sheet: each note states a function.
# Hardness lives in the Finish field.
DRAWING_NOTES = (
    "RIM SETS THE FILED DIAMETER OF THE ROCKER ARM HUB; O.D. ROUND AND TRUE TO BORE.\n"
    "THICKNESS LOCATES THE STACK.\n"
    "KEEP RIM CORNERS SHARP; STONE BURRS ONLY."
)
REFERENCE_DIMENSIONS = frozenset({"BoreDia"})
REFERENCE_CALLOUTS = {"BoreDia": BORE_FIT_CALLOUT}
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
                ("OD", "OD_PLACES", ("ch_rocker_arm_spec", "HUB_DIA")),
            ),
            "dia_nominal": (OD, ("OD", ("ch_rocker_arm_spec", "HUB_DIA"))),
        },
        precision={"dia": OD_PLACES},
    ),
    "bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(BORE_DIA),),
        requirements=("note", "thru"),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": _AXIS,
            "dia_nominal": (BORE_DIA, ("BORE_DIA",)),
            "thru": (True, ("BORE_DIA",)),
            "note": (BORE_FIT_NOTE, ("BORE_FIT_NOTE",)),
        },
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
            "plane": (
                {"frame": "model", "axis": "z", "value": THICKNESS},
                ("THICKNESS",),
            ),
            "thickness": (limits(THICKNESS, THICKNESS_PLACES), ("THICKNESS",)),
        },
        precision={"thickness": THICKNESS_PLACES},
    ),
}
