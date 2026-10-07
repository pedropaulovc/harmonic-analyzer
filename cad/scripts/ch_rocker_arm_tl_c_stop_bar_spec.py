r"""Pure-data contract for the rocker inspection box's C stop bar (MHA-CH-006-TL-09).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). In the
rocker arm's off-machine A/B/C position check (prechips S4 op 50) the arm's
datum-B strap face seats on the inspection box front face and its datum-C tip
land rests on this bar's top: the bar simulates datum C. Route (shop-additions
section 4, binding): O1 ground flat 1/2 x 1/2 in, sawn and milled to length,
drilled and counterbored, torch-hardened in oil and tempered, then the top and
bottom lapped to 12.700 +-0.002 (the parallelism comes from the lap, printed as
the height band plus the LAPPED note; fixtures carry no GD&T). The bar sits on
the granite with the box, so its top is 12.70 above the box base by its own
height; two #8-32 socket head cap screws hold it to the box front wall, no
dowels (the inventory's M4 screws map to #8-32 under the fastener policy).

Frame: the inspection box's model frame (ch_rocker_arm_tl_inspection_box_spec),
so the bar's model coordinates are its installed box coordinates: origin at
the bar's left end, bottom and back (the face on the box front face), +X along
the bar, +Y up, +Z away from the box. The inventory's box frame (rocker-inv
fixtures.rocker-inspection-box) maps as inventory (x, y, z) = model (x, -z, y).
"""

from __future__ import annotations

import _config
import ch_rocker_arm_spec as rocker
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _hole_spec import CLEARANCE_MM, THREAD_MAJOR_MM, HoleSpec
from _printed_tolerance import printed_band_mm

INCH = 25.4
# Abrams 102060: O1 precision-ground flat stock 1/2 x 1/2 in.
BAR_LENGTH = 40.0
BAR_HEIGHT = 12.7  # lapped; the datum-C simulator height above the base
BAR_WIDTH = 12.7  # as-ground stock, projection in front of the box
# Lapped to 12.700 +-0.002 (shop-additions section 4).
BAR_HEIGHT_BAND = (0.002, -0.002)  # (upper, lower) deviations
_X = printed_band_mm(1)

# The rocker's datum-C tip land rests wholly on the bar top: its strap
# thickness across the bar's projection, its tip face along the bar, at the
# op-50 station (inventory reading 1: C land x = 5.43..11.02).
C_LAND_X0 = 5.43
if rocker.ARM_THICKNESS >= BAR_WIDTH - _X:
    raise AssertionError("C stop bar projection does not carry the rocker strap")
if not (C_LAND_X0 > _X and C_LAND_X0 + rocker.TIP_FACE < BAR_LENGTH - _X):
    raise AssertionError("rocker datum-C tip land overhangs the C stop bar")

# Two #8-32 socket head cap screws (ASME B18.3: head 0.270 in dia x 0.164 in)
# through counterbored #8 normal clearance holes into the box front wall.
SCREW_THREAD = "#8-32"
SCREW_HEAD_DIA = 0.270 * INCH
SCREW_HEAD_H = 0.164 * INCH
SCREW_LENGTH = 0.625 * INCH  # #8-32 x 5/8 SHCS
SCREW_X = (10.0, 30.0)  # from the bar's left end (= the box left face)
SCREW_Y = BAR_HEIGHT / 2.0
CLEARANCE_DIA = CLEARANCE_MM[("#8", "normal")]
CBORE_DIA = 8.0
CBORE_DEPTH = 4.8
_DRILLED = _config.title_block("drilled_hole")
DRILLED_BAND = (float(_DRILLED["plus_mm"]), -float(_DRILLED["minus_mm"]))
# The native counterbore callout prints two places: the .XX general band.
_XX = printed_band_mm(2)
if CBORE_DIA - _XX <= SCREW_HEAD_DIA:
    raise AssertionError("C stop bar counterbore does not clear the #8 head")
if CBORE_DEPTH - _XX < SCREW_HEAD_H:
    raise AssertionError("#8 head stands proud of the C stop bar counterbore")
if (BAR_HEIGHT - (CBORE_DIA + _XX)) / 2.0 < 2.0:
    raise AssertionError("counterbore wall under rule 12")
# Screw stations: the bar's clearance holes and the box's taps are drilled to
# the same numbers on two parts. Each part holds half the radial clearance on
# each axis, so the worst diagonal pair still passes the screw.
SCREW_RADIAL_CLEARANCE = (CLEARANCE_DIA - THREAD_MAJOR_MM[SCREW_THREAD]) / 2.0
SCREW_POSITION_BAND = (0.10, -0.10)  # (upper, lower), each part, each axis
if 2.0 * (2.0 * SCREW_POSITION_BAND[0] ** 2) ** 0.5 >= SCREW_RADIAL_CLEARANCE:
    raise AssertionError("C stop bar screw stations can bind the screws")
SCREW_HOLE_SPEC = HoleSpec(
    "counterbore_socket",
    "#8",
    overrides_mm={
        "HoleDiameter": CLEARANCE_DIA,
        "CounterBoreDiameter": CBORE_DIA,
        "CounterBoreDepth": CBORE_DEPTH,
    },
)
# Thread the screw reaches into the box wall past the bar's counterbore floor.
SCREW_ENGAGEMENT = SCREW_LENGTH - (BAR_WIDTH - CBORE_DEPTH)
if not 1.5 * THREAD_MAJOR_MM[SCREW_THREAD] <= SCREW_ENGAGEMENT:
    raise AssertionError("#8-32 x 5/8 screw engages under one and a half diameters")

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BarProfile": {"BarLength", "BarHeight"},
    "Bar": {"BarWidth"},
    "ScrewHoles": {"HoleLeftX", "HoleRightX", "HoleY"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BarProfile": {"BarLength": 1, "BarHeight": 3},
    "Bar": {"BarWidth": 1},
    "ScrewHoles": {"HoleLeftX": 2, "HoleRightX": 2, "HoleY": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked C stop bar dimension needs authored places")
# (feature, dimension) -> (upper, lower) native band.
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("BarProfile", "BarHeight"): BAR_HEIGHT_BAND,
    ("ScrewHoles", "HoleLeftX"): SCREW_POSITION_BAND,
    ("ScrewHoles", "HoleRightX"): SCREW_POSITION_BAND,
    ("ScrewHoles", "HoleY"): SCREW_POSITION_BAND,
}

SURFACE_FINISHES = ()
DRAWING_NOTES = (
    "GAUGE BAR: ITS HEIGHT IS THE ROCKER DATUM C INSPECTION GAUGE HEIGHT.\nTOP AND BOTTOM LAPPED AFTER HARDENING (SHOP HAS NO GRINDER).\n"
    "TOP FACE IS THE DATUM C STOP: NO NICKS, BURRS OR STAMPING ON IT.\n"
    "HOLE STATIONS MATCH THE BOX TAPS: SCREWS MUST ENTER FREELY WITH BAR SEATED."
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

_Z = [0.0, 0.0, 1.0]
EXPORT_FEATURES: dict[str, ExportFeature] = {
    "c_stop_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), BAR_HEIGHT),),
        requirements=("height", "process"),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": BAR_HEIGHT}, ("BAR_HEIGHT",)),
            "height": (
                limits(BAR_HEIGHT, 3, BAR_HEIGHT_BAND),
                ("BAR_HEIGHT", "BAR_HEIGHT_BAND"),
            ),
            "height_nominal": (BAR_HEIGHT, ("BAR_HEIGHT",)),
            "length": (
                limits(BAR_LENGTH, 1),
                ("BAR_LENGTH", "C_LAND_X0", ("ch_rocker_arm_spec", "TIP_FACE")),
            ),
            "width": (
                limits(BAR_WIDTH, 1),
                ("BAR_WIDTH", ("ch_rocker_arm_spec", "ARM_THICKNESS")),
            ),
            "process": ("lap", ("DRAWING_NOTES",)),
        },
        precision={"height": 3, "length": 1, "width": 1},
    ),
    "base_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
        requirements=("height", "process"),
        fields={
            "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "height": (
                limits(BAR_HEIGHT, 3, BAR_HEIGHT_BAND),
                ("BAR_HEIGHT", "BAR_HEIGHT_BAND"),
            ),
            "process": ("lap", ("DRAWING_NOTES",)),
        },
        precision={"height": 3},
    ),
    "box_face_seat": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
        requirements=("width",),
        fields={
            "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
            "width": (limits(BAR_WIDTH, 1), ("BAR_WIDTH",)),
        },
        precision={"width": 1},
    ),
    **{
        f"screw_hole_{side}": ExportFeature(
            kind="counterbore",
            faces=(CylinderFace(CLEARANCE_DIA, contains_x_mm=x),),
            requirements=("at", "dia", "thru"),
            fields={
                "at": ([x, SCREW_Y, BAR_WIDTH], ("SCREW_X", "SCREW_Y", "BAR_WIDTH")),
                "axis": (_Z, ("__frame__",)),
                "station": (limits(x, 2, SCREW_POSITION_BAND), ("SCREW_X", "SCREW_POSITION_BAND")),
                "height": (limits(SCREW_Y, 2, SCREW_POSITION_BAND), ("SCREW_Y", "SCREW_POSITION_BAND")),
                "dia_nominal": (CLEARANCE_DIA, ("CLEARANCE_DIA",)),
                "dia": (
                    limits(CLEARANCE_DIA, 2, DRILLED_BAND),
                    ("CLEARANCE_DIA", "DRILLED_BAND", "SCREW_HOLE_SPEC"),
                ),
                "hole_spec": (
                    f"#8 SOCKET HEAD COUNTERBORE {CBORE_DIA:.2f} X {CBORE_DEPTH:.2f} DEEP",
                    ("SCREW_HOLE_SPEC", "CBORE_DIA", "CBORE_DEPTH"),
                ),
                "thru": (True, ("SCREW_HOLE_SPEC",)),
            },
            precision={"station": 2, "height": 2, "dia": 2},
        )
        for side, x in zip(("left", "right"), SCREW_X, strict=True)
    },
}
