r"""Pure-data contract for the rocker arm's pivot-screw washer (MHA-CH-006-TL-07).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's S4 profile hold the MHA-CH-006-TL-06 pivot screw's head clamps
this washer onto the upper hub face, so the clamp load goes washer -> hub ->
hub stand and the head never scuffs the hub.

Route (shop-additions.md section 2): O1 drill rod, drilled and parted off,
used as supplied (annealed), faced both sides; it only clamps.

Frame (the inventory's fixture frame, rocker-inv:1735-1751): origin on the
pivot axis at the upper hub face, +Z up; the washer sits Z0..1.5.
"""

from __future__ import annotations

import ch_rocker_arm_tl_pivot_screw_spec as screw
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _printed_tolerance import printed_band_mm

# AUTHOR'S CHOICE: Ø10 stock O1 drill rod with its OD left as supplied (the
# inventory's 9.0 would leave a 1.2 wall); the head still bears inside it and
# its rim may overhang the Ø10.2 hub edge, which carries nothing. The OD
# prints as the stock with the stock's own diameter tolerance, +/-0.013 for
# 4-12 mm metric O1 drill rod
# (https://store.diesupplies.com/o1-drill-rod-oil-hardening-tool-steel-oilcrat-pm-metric-p114.aspx),
# not the title block's .X band.
OUTER_DIA = 10.0
OUTER_BAND = (0.013, -0.013)
OUTER_PLACES = 3
OUTER_CALLOUT = "DRILL ROD AS SUPPLIED"
BORE_DIA = 6.6
# The thickness is a link in the pivot screw's axial stack (shoulder clear
# of the plate bore floor, full thread engagement): it prints at .XXX.
THICK = screw.WASHER_THICK
THICK_PLACES = screw.WASHER_THICK_PLACES
PLACES = 1
# A drilled bore: the title block's DRILLED HOLES row, +0.10/0, held natively.
BORE_BAND = (0.10, 0.0)

# The bore passes the largest shoulder; the head, at its smallest, still
# bears on the washer face outside the largest bore.
_BORE_MIN = BORE_DIA + BORE_BAND[1]
_BORE_MAX = BORE_DIA + BORE_BAND[0]
if _BORE_MIN <= screw.SHOULDER_DIA + screw.SHOULDER_BAND[0]:
    raise AssertionError("pivot washer bore does not pass the pivot-screw shoulder")
if _BORE_MAX >= screw.HEAD_DIA + screw.HEAD_BAND[1]:
    raise AssertionError("pivot-screw head has no bearing on the washer")
# The head's clamp ring lands on the hub face, inside the arm's hub diameter;
# a washer rim past the hub edge only overhangs air.
if screw.HEAD_DIA + screw.HEAD_BAND[0] >= screw.rocker.HUB_DIA:
    raise AssertionError("pivot-screw head clamps outside the rocker hub face")
# Rule 12: radial wall and axial thickness at their worst printed limits.
WALL_MIN = round(((OUTER_DIA + OUTER_BAND[1]) - _BORE_MAX) / 2.0, 6)
THICK_MIN = round(THICK - printed_band_mm(THICK_PLACES), 6)
if min(WALL_MIN, THICK_MIN) < 1.5 - 1e-9:
    raise AssertionError("pivot washer falls under the rule-12 floor")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WasherProfile": {"OuterDia", "BoreDia"},
    "Washer": {"Thick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "WasherProfile": {"OuterDia": OUTER_PLACES, "BoreDia": PLACES},
    "Washer": {"Thick": THICK_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked pivot-washer dimension needs authored places")

# Named exception: MHA-CH-006-TL-07 wall 1.64 MIN (drawing-simplicity-policy.md)
WALL_STATED_MIN = 1.64
if round(WALL_MIN, 2) != WALL_STATED_MIN:
    raise AssertionError("pivot-washer stated wall drifted from its geometry")
WALL_NOTE = f"WALL {WALL_STATED_MIN:.2f} MIN."
DRAWING_NOTES = "\n".join(
    (
        "CLAMP WASHER: IT LOCATES NOTHING, BUT ITS THICKNESS SETS THE PIVOT SCREW DEPTH.",
        WALL_NOTE,
    )
)
BORE_CALLOUT = "DRILL"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 5:1"

EXPORT_FEATURES: dict[str, ExportFeature] = {
    "bore": ExportFeature(
        kind="hole",
        faces=(CylinderFace(BORE_DIA),),
        requirements=("dia",),
        fields={
            "at": ([0.0, 0.0, 0.0], ("__frame__",)),
            "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
            "dia": (
                limits(BORE_DIA, PLACES, BORE_BAND),
                ("BORE_DIA", "BORE_BAND", ("ch_rocker_arm_tl_pivot_screw_spec", "SHOULDER_DIA")),
            ),
            "thru": (True, ("BORE_DIA",)),
        },
        precision={"dia": PLACES},
    ),
    "hub_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("thickness", "dia"),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "thickness": (limits(THICK, THICK_PLACES), ("THICK", "THICK_PLACES")),
            "dia": (
                limits(OUTER_DIA, OUTER_PLACES, OUTER_BAND),
                ("OUTER_DIA", "OUTER_BAND", ("ch_rocker_arm_spec", "HUB_DIA")),
            ),
            "process": ("face", ("DRAWING_NOTES",)),
        },
        precision={"thickness": THICK_PLACES, "dia": OUTER_PLACES},
    ),
    "head_face": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), THICK),),
        requirements=("thickness",),
        fields={
            "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": THICK}, ("THICK",)),
            "thickness": (limits(THICK, THICK_PLACES), ("THICK", "THICK_PLACES")),
            "process": ("face", ("DRAWING_NOTES",)),
        },
        precision={"thickness": THICK_PLACES},
    ),
}
