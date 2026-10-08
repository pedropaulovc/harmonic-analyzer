r"""Pure-data contract for the cone pivot post's bond cradle (MHA-DT-005-TL-01).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). While the
retaining compound in the cone and crank sockets cures (prechips S6/S7), the
post lies on its side in this cradle, held by gravity alone: the turned body
in the body seat, the raw tail on the tail seat, foot B against the foot stop,
the cone sleeve's north cap on the two tilted cone pins and the crank sleeve's
north face on the two crank pins.

Frame: the cone pivot post's model frame R0, unchanged (make-data section 1.2:
the cradle frame IS the post frame, so a prechips pose of the post in the
cradle is the identity). Post axis +Y through X0 Z0 with foot B, the
foot-stop face, at Y0; crank socket axis +Z (up). The base top is at Z -30
and the base bottom at Z -40. Block heights and the seat axes print from the
base top, every station along the post from foot B, and every pin top from
the post axis: a pin top sets a sleeve face against that axis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import dt_cone_pivot_post_spec as post
from _feature_requirements import ExportFeature, limits
from _gtol_spec import CylinderFace, PlanarFace
from _printed_tolerance import angular_band_deg, printed_band_mm
from _surface_finish import SEAT_UM, SurfaceFinishControl

# Base plate, foot stop and the two saddles (inventory cone-bond-cradle rows).
BASE_WIDTH = 80.0
BASE_LENGTH = 134.0
BASE_THICK = 10.0
BASE_TOP_Z = -30.0
BASE_END_Y = -12.0
STOP_WIDTH = 30.0
STOP_THICK = -BASE_END_Y  # flush with the base end; its +Y face is foot B
BLOCK_HEIGHT = 15.0  # the stop and both saddles, above the base top
BLOCK_TOP_Z = BASE_TOP_Z + BLOCK_HEIGHT
SADDLE_WIDTH = 60.0
BODY_SADDLE_Y = 10.0
BODY_SADDLE_THICK = 10.0
TAIL_SADDLE_Y = 100.0
TAIL_SADDLE_THICK = 20.0

# Seats: on the post axis, SEAT_AXIS_HEIGHT above the base top. The body seat
# takes the post's turned body; the tail seat the raw bar the tail is left at
# (cone-plan stock component "body", dia_mm 44.45). Both are MATCHED FITS
# (policy rule 2): the body prints at .X (+/-0.8) on the post and the bar
# carries mill tolerance, so no printed seat band can take the actual post
# without either rejecting it or letting it shake, and with it the axis the
# pins work from. Each seat is bored to suit its identified mate; the
# diameter is a reference size and the callout's acceptance defines the fit.
SEAT_AXIS_HEIGHT = -BASE_TOP_Z
BODY_SEAT_DIA = post.BLOCK_DIA
TAIL_SEAT_DIA = 44.45
POST_NUMBER = _config.parts("dt-cone-pivot-post")["number"]
# Callout lines stay narrow (run-15 review: wider blocks ran into the plan's
# 80.0 and the isometric).
BODY_SEAT_CALLOUT = f"BORE TO SUIT\n{POST_NUMBER}\nCONE PIVOT\nPOST BODY:\nBEDS WITHOUT\nSHAKE"
TAIL_SEAT_CALLOUT = f"BORE TO SUIT\n{POST_NUMBER}\nCONE PIVOT\nPOST TAIL:\nBEDS WITHOUT\nSHAKE"
SEAT_OVERRUN = 1.0  # each seat cut runs past both saddle faces
# The bed under a NOMINAL body; a matched seat moves it with the body, never
# the axis.
BED_HEIGHT = BASE_THICK + SEAT_AXIS_HEIGHT - BODY_SEAT_DIA / 2.0
if abs(BED_HEIGHT - 18.9945) > 1e-9:
    raise AssertionError("body seat bed height left the inventory's 18.9945")

# Pins: hardened O4 m6 dowels pressed into reamed holes in the base.
PIN_DIA = 4.0
PIN_RADIUS = PIN_DIA / 2.0

# Every pin top prints from the post axis at PIN_TOP_PLACES under an explicit
# band (CRANK/CONE_PIN_FROM_AXIS_TOL below). The model is driven at the
# PRINTED nominal, the parent's value rounded to those places, so the
# exported band and the printed limits are the same numbers (FixtureCAD
# ruling: an explicit band applies to the printed nominal). The rounding
# moves a top at most half a printed unit off the parent's face.
PIN_TOP_PLACES = 2
PIN_TOP_ROUNDING = 0.5 * 10.0**-PIN_TOP_PLACES

# Crank pins: vertical, under the crank sleeve's north face, at the crank
# socket's station from foot B.
CRANK_PIN_X = 6.0
CRANK_PIN_Y = post.CRANK_BORE_HEIGHT
CRANK_PIN_TOP_Z = -round(post.CRANK_BOSS_NORTH_FACE, PIN_TOP_PLACES)
CRANK_PIN_HEIGHT = CRANK_PIN_TOP_Z - BASE_TOP_Z
if abs(round(CRANK_PIN_HEIGHT, 2) - 8.62) > 1e-9:
    raise AssertionError("crank pin height left the plan's 8.62")

# Cone pins: tilted with the cone journal, axis n = (sin i, 0, cos i), the
# reverse of the post's north-cap normal. Both stand at the journal station,
# one either side of the journal axis, CONE_PIN_SPREAD along u = (cos i, 0,
# -sin i) (square to n in the post's mid-plane): each top centres on the
# north cap's annulus between the bore and the boss rim, never on the
# journal axis, where a top would sit over the bore (prechips CN-B5). The
# square tops lie in the north-cap plane, CONE_BOSS_LENGTH / 2 below the
# journal centre along n. Each pin is a stock dowel reaching its own length
# from its top down n into the base: the east (+X) top stands lower, so it
# takes the shorter one (prechips cone-pin-1 4x16, cone-pin-2 4x20).
CONE_PIN_Y = post.BORE_HEIGHT
CONE_PIN_SPREAD = 7.4
if not post.BORE_DIA / 2.0 < CONE_PIN_SPREAD < post.CONE_BOSS_DIA / 2.0:
    raise AssertionError("cone pin tops left the north cap's annulus")
_INCLINE = math.radians(post.INCLINE_DEG)
CONE_PIN_AXIS = (math.sin(_INCLINE), 0.0, math.cos(_INCLINE))
CONE_PIN_ACROSS = (math.cos(_INCLINE), 0.0, -math.sin(_INCLINE))
_NORTH_CAP = post.SURFACE_FINISHES[3].face
if any(abs(a + c) > 1e-12 for a, c in zip(CONE_PIN_AXIS, _NORTH_CAP.normal, strict=True)):
    raise AssertionError("cone pin axis is not square to the post's north cap")
CONE_PIN_TOP_S = -round(post.CONE_BOSS_LENGTH / 2.0, PIN_TOP_PLACES)
if abs(-CONE_PIN_TOP_S - _NORTH_CAP.offset_mm) > PIN_TOP_ROUNDING:
    raise AssertionError("cone pin tops left the post's north-cap plane")


@dataclass(frozen=True)
class ConePin:
    """One cone pin: ``side`` +1 east (+X), -1 west, of the journal axis."""

    side: int
    length: float

    @property
    def top_x(self) -> float:
        return CONE_PIN_TOP_S * CONE_PIN_AXIS[0] + self.side * CONE_PIN_SPREAD * CONE_PIN_ACROSS[0]

    @property
    def top_z(self) -> float:
        return CONE_PIN_TOP_S * CONE_PIN_AXIS[2] + self.side * CONE_PIN_SPREAD * CONE_PIN_ACROSS[2]

    @property
    def above_base(self) -> float:
        """Axis length from the base top up to the pin top."""
        return (self.top_z - BASE_TOP_Z) / CONE_PIN_AXIS[2]

    @property
    def entry_x(self) -> float:
        """Where the axis enters the base top: the reamed hole's position."""
        return self.top_x - self.above_base * CONE_PIN_AXIS[0]

    @property
    def bottom_z(self) -> float:
        return self.top_z - self.length * CONE_PIN_AXIS[2]


CONE_PIN_EAST = ConePin(side=1, length=16.0)
CONE_PIN_WEST = ConePin(side=-1, length=20.0)
CONE_PINS = {"east": CONE_PIN_EAST, "west": CONE_PIN_WEST}
# prechips CN-B5's stations for the tops, to the half printed unit the
# rounded top plane may move them along the pin axis.
if (
    abs(CONE_PIN_EAST.top_x - 2.671145) > PIN_TOP_ROUNDING
    or abs(CONE_PIN_EAST.top_z + 22.110089) > PIN_TOP_ROUNDING
    or abs(CONE_PIN_WEST.top_x + 11.777018) > PIN_TOP_ROUNDING
    or abs(CONE_PIN_WEST.top_z + 18.902193) > PIN_TOP_ROUNDING
):
    raise AssertionError("cone pin tops left prechips CN-B5's stations")
# Each pin's bottom end stays inside the base plate.
_BOTTOM_HALF_DROP = PIN_RADIUS * math.sin(_INCLINE)
for _pin in CONE_PINS.values():
    if not (
        BASE_TOP_Z - BASE_THICK < _pin.bottom_z - _BOTTOM_HALF_DROP
        and _pin.bottom_z + _BOTTOM_HALF_DROP < BASE_TOP_Z
    ):
        raise AssertionError("cone pin end leaves the base plate")

# Each pin top sets a sleeve face against the POST AXIS, so it prints from
# that axis as one relation: never a chain of a pin height and a seat-axis
# height through the base top, which stacks +/-0.51 and +/-0.8 against bands
# of +/-0.51 (crank) and +/-0.255 (cone). The post axis is the line through
# both seat axes, read over gauge rods bedded in the two seats (the matched
# seats take the post's body and tail, so rods of those sizes bed as the post
# does). Both cone pin tops lie in one plane square to n, the north-cap
# plane: they print along n from the post axis to that plane.
CRANK_PIN_FROM_AXIS = -CRANK_PIN_TOP_Z
CONE_PIN_FROM_AXIS = -CONE_PIN_TOP_S
for _pin in CONE_PINS.values():
    _along = _pin.top_x * CONE_PIN_AXIS[0] + _pin.top_z * CONE_PIN_AXIS[2]
    if abs(-_along - CONE_PIN_FROM_AXIS) > 1e-9:
        raise AssertionError("a cone pin top left the north-cap plane")
# The two cone tops' errors along n must agree within CONE_PIN_TOPS_MATCH:
# 0.03 over the 2 x CONE_PIN_SPREAD spacing rolls the post 0.12 deg, inside
# the 0.13 deg the S6 crank-mouth roll check allows (prechips cone data). Two
# independent +/-0.06 bands alone could roll it 0.46 deg. The note names the
# mate whose cone boss face bears on both tops, so the match reads as that
# fit's acceptance (policy rule 2; run-17 review asked for its function).
CONE_PIN_TOPS_MATCH = 0.03
if math.degrees(math.atan(CONE_PIN_TOPS_MATCH / (2.0 * CONE_PIN_SPREAD))) >= 0.13:
    raise AssertionError("cone pin tops' match no longer holds the S6 roll check")
CONE_PIN_TOPS_NOTE = (
    f"TOPS WITHIN {CONE_PIN_TOPS_MATCH:.2f} OF EACH OTHER: "
    f"BOSS OF {POST_NUMBER} BEARS ON BOTH"
)
# Each relation's band is the fixture's share of the post band the pin sets:
# AUTHOR'S CHOICE 25 %, rounded down to the hundredth, leaving 75 % to the
# sleeve and the bond. The two shares sum to the band they replace, the
# transfer rule of MH 27th p.987 ("Transfer of Tolerances"). MH 27th p.678's
# gagemakers tolerance (5 % of the workpiece tolerance, ANSI B4.4M) is for
# fixed limit gages, not a fixture that sets a part, so it does not apply.
FIXTURE_SHARE = 0.25


def _fixture_band(post_band_mm: float) -> float:
    return math.floor(FIXTURE_SHARE * post_band_mm * 100.0 + 1e-9) / 100.0


# The crank sleeve's north face is the post's CrankBossStartZ station.
CRANK_POST_BAND = printed_band_mm(post.DRAWING_PRECISION_BY_NAME["CrankBossStartZ"])
CRANK_PIN_FROM_AXIS_TOL = _fixture_band(CRANK_POST_BAND)
# The north cap is ConeBossLen / 2 off the post centre and takes half its
# band (the post's ruling behind TIP_EMBED_WORST_MM).
CONE_POST_BAND = printed_band_mm(post.DRAWING_PRECISION_BY_NAME["ConeBossLen"]) / 2.0
CONE_PIN_FROM_AXIS_TOL = _fixture_band(CONE_POST_BAND)
if (CRANK_PIN_FROM_AXIS_TOL, CONE_PIN_FROM_AXIS_TOL) != (0.12, 0.06):
    raise AssertionError("a pin relation's fixture share left the post band it sets")

# Layout datum: every transverse (X) location prints from the base's west
# side face, a physical face the shop can square from, never from the post
# axis. Stations (Y) print from foot B; heights from the base top; pin tops
# from the post axis.
SIDE_W_X = -BASE_WIDTH / 2.0
SEAT_AXIS_FROM_SIDE = -SIDE_W_X
STOP_SIDE_OFFSET = (BASE_WIDTH - STOP_WIDTH) / 2.0
SADDLE_SIDE_OFFSET = (BASE_WIDTH - SADDLE_WIDTH) / 2.0
CRANK_PIN_WEST_FROM_SIDE = -CRANK_PIN_X - SIDE_W_X
CRANK_PIN_EAST_FROM_SIDE = CRANK_PIN_X - SIDE_W_X
CONE_PIN_ENTRY_FROM_SIDE = {name: pin.entry_x - SIDE_W_X for name, pin in CONE_PINS.items()}

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BaseProfile": {"BaseThick", "BaseLength"},
    "Base": {"BaseWidth"},
    "StopProfile": {"StopHeight", "StopThick"},
    "Stop": {"StopWidth"},
    "SaddlesProfile": {
        "BodySaddleHeight",
        "BodySaddleThick",
        "BodySaddleY",
        "TailSaddleHeight",
        "TailSaddleThick",
        "TailSaddleY",
    },
    "Saddles": {"SaddleWidth"},
    "BodySeatProfile": {"BodySeatDia"},
    "TailSeatProfile": {"TailSeatDia"},
    "CrankPinProfile": {"CrankPinY", "CrankPinDia"},
    "CrankPinReference": {"CrankPinFromAxis"},
    "PlanReference": {
        "ConePinY",
        "StopSideX",
        "SaddleSideX",
        "CrankPinWestX",
        "CrankPinEastX",
    },
    "ConePinSectionReference": {
        "BodySeatAxisX",
        "BodySeatAxisHeight",
        "ConePinEntryEastX",
        "ConePinEntryWestX",
        "ConePinTilt",
        "ConePinFromAxis",
    },
    "TailSeatReference": {"TailSeatAxisX", "TailSeatAxisHeight"},
}
# One place for the plates and blocks, the crank pins' spots (they carry a
# sleeve face, not a bore) and the seats' centring and axis heights: nothing
# locates on them closer than the .X band. The seats are matched fits, so
# their diameters are reference sizes at their mates' places: the post body's
# own (MainBodyDia) and the tail bar's two.
# The cone pins' station and hole entries take two. The pin tops take two
# under their own bands (CRANK/CONE_PIN_FROM_AXIS_TOL). The cone pin tilt
# prints to a tenth of a degree under the general angular band. The pin
# diameter names the stock dowel; the press fit is the reamed hole's job
# (DRAWING_NOTES), not a printed limit.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BaseProfile": {"BaseThick": 1, "BaseLength": 1},
    "Base": {"BaseWidth": 1},
    "StopProfile": {"StopHeight": 1, "StopThick": 1},
    "Stop": {"StopWidth": 1},
    "SaddlesProfile": {
        "BodySaddleHeight": 1,
        "BodySaddleThick": 1,
        "BodySaddleY": 1,
        "TailSaddleHeight": 1,
        "TailSaddleThick": 1,
        "TailSaddleY": 1,
    },
    "Saddles": {"SaddleWidth": 1},
    "BodySeatProfile": {"BodySeatDia": post.DRAWING_PRECISION_BY_NAME["MainBodyDia"]},
    "TailSeatProfile": {"TailSeatDia": 2},
    "CrankPinProfile": {
        "CrankPinY": 1,
        "CrankPinDia": 1,
    },
    "CrankPinReference": {"CrankPinFromAxis": PIN_TOP_PLACES},
    "PlanReference": {
        "ConePinY": 2,
        "StopSideX": 1,
        "SaddleSideX": 1,
        "CrankPinWestX": 1,
        "CrankPinEastX": 1,
    },
    "ConePinSectionReference": {
        "BodySeatAxisX": 1,
        "BodySeatAxisHeight": 1,
        "ConePinEntryEastX": 2,
        "ConePinEntryWestX": 2,
        "ConePinTilt": 1,
        "ConePinFromAxis": PIN_TOP_PLACES,
    },
    "TailSeatReference": {"TailSeatAxisX": 1, "TailSeatAxisHeight": 1},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places for dimensions in DRAWING_PRECISION.values() for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked bond-cradle dimension needs authored places")

# Construction-only sketches the part saves hidden; the drawing shows them in
# the views that print their dimensions (_drawing_hidden_sketches). The two
# section sketches lie in their cutting planes: A-A through both cone pins'
# axes, B-B between the crank pins and the tail saddle, so B-B looks on to the
# tail saddle's south face, uncut, and its seat arc is a model edge. The
# crank pin's sketch lies on the post's mid-plane and draws the post axis
# through both seats in the elevation.
TAIL_SECTION_Y = (CRANK_PIN_Y + TAIL_SADDLE_Y) / 2.0
REFERENCE_SKETCHES = (
    "PlanReference",
    "CrankPinReference",
    "ConePinSectionReference",
    "TailSeatReference",
)
SECTION_REFERENCE_SKETCHES = ("ConePinSectionReference", "TailSeatReference")

# The seats MUST be cut (the title block's surface row is CAST/MACHINED, not
# a grade): the post lies in them. Nothing runs on them, so they take the
# static seat grade.
SURFACE_FINISHES = (
    SurfaceFinishControl("body_seat", SEAT_UM, CylinderFace(BODY_SEAT_DIA)),
    SurfaceFinishControl("tail_seat", SEAT_UM, CylinderFace(TAIL_SEAT_DIA)),
)
BUILT_UP_PERMISSION_NOTE = "BASE, STOP AND SADDLES MAY BE SCREWED AND DOWELED BLOCKS."
DRAWING_NOTES = "\n".join(
    (
        BUILT_UP_PERMISSION_NOTE,
        "PINS ARE STOCK HARDENED DOWELS; PIN ENDS STAY INSIDE THE BASE.",
        "REAM PIN HOLES THRU FOR A PRESS FIT; A PRESSED PIN MUST NOT TURN.",
        # Short enough to stop clear of the title block (run-15 review).
        "STATIONS FROM STOP, HEIGHTS FROM BASE, PIN TOPS FROM AXIS OF SEATED RODS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

_POST = "dt_cone_pivot_post_spec"
_UP = ([0.0, 0.0, 1.0], ("__frame__",))
_POST_AXIS = ([0.0, 1.0, 0.0], ("__frame__",))
# Pin tops print from the post axis: the body seat's axis (the tail seat's
# is the same line).
_HEIGHT_FROM = "body_seat"
# Every transverse (X) location prints from the base's west side face; it
# exports as a ``width`` band, the distance from that face (base_west_side).
# The sizes across the base, the stop and the saddles export as ``width``
# bands on their east faces, from the same block's west face.
_FROM_BASE_TOP = ("base_top", ("BASE_TOP_Z",))
# The printed cone pin tilt under the title block's general angular band.
CONE_PIN_TILT_TOL = angular_band_deg()
CONE_PIN_TILT = round(post.INCLINE_DEG, DRAWING_PRECISION_BY_NAME["ConePinTilt"])
# Saddle-top faces are picked off the seats' chords and the stop's top.
SADDLE_TOP_PICK_X = SADDLE_WIDTH / 2.0 - 5.0
if not (
    STOP_WIDTH / 2.0 < SADDLE_TOP_PICK_X
    and math.sqrt((TAIL_SEAT_DIA / 2.0) ** 2 - BLOCK_TOP_Z**2) < SADDLE_TOP_PICK_X
):
    raise AssertionError("saddle-top pick strays off the saddle tops")


def _width(nominal: float, printed: str, sources: tuple[str, ...]) -> dict:
    """A transverse location or size: its band and nominal at printed places.

    Every exported ``*_nominal`` is the PRINTED value (FixtureCAD ruling:
    prechips refuses a nominal outside its band), never the raw model one.
    """
    places = DRAWING_PRECISION_BY_NAME[printed]
    return {
        "width": (limits(nominal, places), sources),
        "width_nominal": (round(nominal, places), sources),
    }


def _block_face(
    axis: str,
    outward: float,
    at: float,
    key: str,
    printed: str,
    nominal: float,
    sources: tuple[str, ...],
    *,
    picks: tuple[float | None, ...] = (None,),
) -> ExportFeature:
    """One printed block dimension, owned by the face(s) it ends on: the plane
    at model ``axis`` = ``at`` facing ``outward``. Heights read from the base
    top, stations from foot B, widths from the side named above."""
    normal = [0.0, 0.0, 0.0]
    normal["xyz".index(axis)] = outward
    places = DRAWING_PRECISION_BY_NAME[printed]
    fields = {
        "normal": (normal, ("__frame__",)),
        "plane": ({"frame": "model", "axis": axis, "value": at}, sources),
        key: (limits(nominal, places), sources),
        f"{key}_nominal": (round(nominal, places), sources),
    }
    if key == "height":
        fields["height_from"] = _FROM_BASE_TOP
    return ExportFeature(
        kind="face",
        faces=tuple(PlanarFace(tuple(normal), outward * at, contains_x_mm=x) for x in picks),
        requirements=(key,),
        fields=fields,
        precision={key: places},
    )


def _seat_finish(key: str) -> dict:
    control = next(item for item in SURFACE_FINISHES if item.key == key)
    return {"finish_ra": (control.roughness_um, ("SURFACE_FINISHES",))}


def _crank_pin(x: float) -> ExportFeature:
    return ExportFeature(
        kind="pin",
        faces=(
            CylinderFace(PIN_DIA, contains_x_mm=x, contains_y_mm=CRANK_PIN_Y),
            PlanarFace((0.0, 0.0, 1.0), CRANK_PIN_TOP_Z, contains_x_mm=x),
        ),
        requirements=("height", "station", "width"),
        fields={
            "at": ([x, CRANK_PIN_Y, CRANK_PIN_TOP_Z], ("CRANK_PIN_X", "CRANK_PIN_Y", "CRANK_PIN_TOP_Z")),
            "axis": _UP,
            "height": (
                limits(
                    CRANK_PIN_FROM_AXIS,
                    DRAWING_PRECISION_BY_NAME["CrankPinFromAxis"],
                    (CRANK_PIN_FROM_AXIS_TOL, -CRANK_PIN_FROM_AXIS_TOL),
                ),
                (
                    "CRANK_PIN_FROM_AXIS",
                    (_POST, "CRANK_BOSS_NORTH_FACE"),
                    "CRANK_PIN_FROM_AXIS_TOL",
                    (_POST, "DRAWING_PRECISION"),
                ),
            ),
            "height_nominal": (CRANK_PIN_FROM_AXIS, ("CRANK_PIN_FROM_AXIS",)),
            "height_from": (_HEIGHT_FROM, ("CRANK_PIN_FROM_AXIS", "SEAT_AXIS_HEIGHT")),
            "station": (
                limits(CRANK_PIN_Y, DRAWING_PRECISION_BY_NAME["CrankPinY"]),
                ("CRANK_PIN_Y", (_POST, "CRANK_BORE_HEIGHT")),
            ),
            "station_nominal": (CRANK_PIN_Y, ("CRANK_PIN_Y",)),
            "dia_nominal": (PIN_DIA, ("PIN_DIA",)),
            **_width(
                x - SIDE_W_X,
                "CrankPinWestX" if x < 0.0 else "CrankPinEastX",
                ("CRANK_PIN_WEST_FROM_SIDE" if x < 0.0 else "CRANK_PIN_EAST_FROM_SIDE",),
            ),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["CrankPinFromAxis"],
            "station": DRAWING_PRECISION_BY_NAME["CrankPinY"],
            "width": DRAWING_PRECISION_BY_NAME["CrankPinWestX" if x < 0.0 else "CrankPinEastX"],
        },
    )


def _cone_pin(name: str) -> ExportFeature:
    pin = CONE_PINS[name]
    pin_name = f"CONE_PIN_{name.upper()}"
    entry = f"ConePinEntry{name.title()}X"
    return ExportFeature(
        kind="pin",
        faces=(CylinderFace(PIN_DIA, contains_x_mm=pin.top_x, contains_y_mm=CONE_PIN_Y),),
        requirements=("height", "station", "width", "land_angle_deg", "note"),
        fields={
            "at": (
                [pin.top_x, CONE_PIN_Y, pin.top_z],
                (pin_name, "CONE_PIN_Y", "CONE_PIN_SPREAD", (_POST, "CONE_BOSS_LENGTH")),
            ),
            "axis": (list(CONE_PIN_AXIS), ("CONE_PIN_AXIS", (_POST, "INCLINE_DEG"))),
            # Along the pin's own axis, from the post axis to the tops' plane.
            "height": (
                limits(
                    CONE_PIN_FROM_AXIS,
                    DRAWING_PRECISION_BY_NAME["ConePinFromAxis"],
                    (CONE_PIN_FROM_AXIS_TOL, -CONE_PIN_FROM_AXIS_TOL),
                ),
                (
                    "CONE_PIN_FROM_AXIS",
                    (_POST, "CONE_BOSS_LENGTH"),
                    "CONE_PIN_FROM_AXIS_TOL",
                    (_POST, "DRAWING_PRECISION"),
                ),
            ),
            "height_nominal": (CONE_PIN_FROM_AXIS, ("CONE_PIN_FROM_AXIS",)),
            "height_from": (_HEIGHT_FROM, ("CONE_PIN_FROM_AXIS", "SEAT_AXIS_HEIGHT")),
            "station": (
                limits(CONE_PIN_Y, DRAWING_PRECISION_BY_NAME["ConePinY"]),
                ("CONE_PIN_Y", (_POST, "BORE_HEIGHT")),
            ),
            "station_nominal": (
                round(CONE_PIN_Y, DRAWING_PRECISION_BY_NAME["ConePinY"]),
                ("CONE_PIN_Y",),
            ),
            "angle_deg": (post.INCLINE_DEG, ((_POST, "INCLINE_DEG"),)),
            # The printed 12.5 deg tilt, +/- the general angular band.
            "land_angle_deg": (
                [CONE_PIN_TILT - CONE_PIN_TILT_TOL, CONE_PIN_TILT + CONE_PIN_TILT_TOL],
                ("CONE_PIN_TILT", "CONE_PIN_TILT_TOL", (_POST, "INCLINE_DEG")),
            ),
            "land_angle_nominal_deg": (CONE_PIN_TILT, ("CONE_PIN_TILT", (_POST, "INCLINE_DEG"))),
            # The hole's entry into the base top, from the west side.
            **_width(CONE_PIN_ENTRY_FROM_SIDE[name], entry, ("CONE_PIN_ENTRY_FROM_SIDE",)),
            "dia_nominal": (PIN_DIA, ("PIN_DIA",)),
            "note": (CONE_PIN_TOPS_NOTE, ("CONE_PIN_TOPS_NOTE", "CONE_PIN_TOPS_MATCH")),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["ConePinFromAxis"],
            "station": DRAWING_PRECISION_BY_NAME["ConePinY"],
            "width": DRAWING_PRECISION_BY_NAME[entry],
            "land_angle_deg": DRAWING_PRECISION_BY_NAME["ConePinTilt"],
        },
    )


EXPORT_FEATURES: dict[str, ExportFeature] = {
    "body_seat": ExportFeature(
        kind="seat",
        faces=(CylinderFace(BODY_SEAT_DIA),),
        requirements=("note", "height", "width", "finish_ra"),
        fields={
            "at": ([0.0, BODY_SADDLE_Y, 0.0], ("BODY_SADDLE_Y", "__frame__")),
            "axis": _POST_AXIS,
            "dia_nominal": (BODY_SEAT_DIA, ("BODY_SEAT_DIA", (_POST, "BLOCK_DIA"))),
            "note": (BODY_SEAT_CALLOUT, ("BODY_SEAT_CALLOUT", "POST_NUMBER")),
            "height": (
                limits(SEAT_AXIS_HEIGHT, DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"]),
                ("SEAT_AXIS_HEIGHT", "BASE_TOP_Z"),
            ),
            "height_nominal": (SEAT_AXIS_HEIGHT, ("SEAT_AXIS_HEIGHT",)),
            **_width(SEAT_AXIS_FROM_SIDE, "BodySeatAxisX", ("SEAT_AXIS_FROM_SIDE",)),
            **_seat_finish("body_seat"),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["BodySeatAxisHeight"],
            "width": DRAWING_PRECISION_BY_NAME["BodySeatAxisX"],
            "finish_ra": 1,
        },
    ),
    "tail_seat": ExportFeature(
        kind="seat",
        faces=(CylinderFace(TAIL_SEAT_DIA),),
        requirements=("note", "height", "width", "finish_ra"),
        fields={
            "at": ([0.0, TAIL_SADDLE_Y, 0.0], ("TAIL_SADDLE_Y", "__frame__")),
            "axis": _POST_AXIS,
            "dia_nominal": (TAIL_SEAT_DIA, ("TAIL_SEAT_DIA",)),
            "note": (TAIL_SEAT_CALLOUT, ("TAIL_SEAT_CALLOUT", "POST_NUMBER")),
            "height": (
                limits(SEAT_AXIS_HEIGHT, DRAWING_PRECISION_BY_NAME["TailSeatAxisHeight"]),
                ("SEAT_AXIS_HEIGHT", "BASE_TOP_Z"),
            ),
            "height_nominal": (SEAT_AXIS_HEIGHT, ("SEAT_AXIS_HEIGHT",)),
            **_width(SEAT_AXIS_FROM_SIDE, "TailSeatAxisX", ("SEAT_AXIS_FROM_SIDE",)),
            **_seat_finish("tail_seat"),
        },
        precision={
            "height": DRAWING_PRECISION_BY_NAME["TailSeatAxisHeight"],
            "width": DRAWING_PRECISION_BY_NAME["TailSeatAxisX"],
            "finish_ra": 1,
        },
    ),
    "foot_stop": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 1.0, 0.0), 0.0),),
        requirements=("plane", "thickness"),
        fields={
            "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
            "thickness": (
                limits(STOP_THICK, DRAWING_PRECISION_BY_NAME["StopThick"]),
                ("STOP_THICK",),
            ),
            "thickness_nominal": (STOP_THICK, ("STOP_THICK",)),
        },
        precision={"thickness": DRAWING_PRECISION_BY_NAME["StopThick"]},
    ),
    "base_top": ExportFeature(
        kind="face",
        faces=(PlanarFace((0.0, 0.0, 1.0), BASE_TOP_Z),),
        requirements=("thickness",),
        fields={
            "normal": _UP,
            "plane": ({"frame": "model", "axis": "z", "value": BASE_TOP_Z}, ("BASE_TOP_Z",)),
            "thickness": (
                limits(BASE_THICK, DRAWING_PRECISION_BY_NAME["BaseThick"]),
                ("BASE_THICK",),
            ),
            "thickness_nominal": (BASE_THICK, ("BASE_THICK",)),
        },
        precision={"thickness": DRAWING_PRECISION_BY_NAME["BaseThick"]},
    ),
    # The face every transverse location prints from.
    "base_west_side": ExportFeature(
        kind="face",
        faces=(PlanarFace((-1.0, 0.0, 0.0), -SIDE_W_X),),
        requirements=("plane",),
        fields={
            "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
            "plane": ({"frame": "model", "axis": "x", "value": SIDE_W_X}, ("SIDE_W_X",)),
        },
    ),
    "base_east_side": _block_face(
        "x", 1.0, -SIDE_W_X, "width", "BaseWidth", BASE_WIDTH, ("BASE_WIDTH", "SIDE_W_X")
    ),
    "base_far_end": _block_face(
        "y",
        1.0,
        BASE_END_Y + BASE_LENGTH,
        "length",
        "BaseLength",
        BASE_LENGTH,
        ("BASE_LENGTH", "BASE_END_Y"),
    ),
    "stop_top": _block_face(
        "z",
        1.0,
        BLOCK_TOP_Z,
        "height",
        "StopHeight",
        BLOCK_HEIGHT,
        ("BLOCK_HEIGHT", "BLOCK_TOP_Z"),
        picks=(0.0,),
    ),
    "stop_west_side": _block_face(
        "x",
        -1.0,
        -STOP_WIDTH / 2.0,
        "width",
        "StopSideX",
        STOP_SIDE_OFFSET,
        ("STOP_SIDE_OFFSET", "STOP_WIDTH", "SIDE_W_X"),
    ),
    "stop_east_side": _block_face(
        "x", 1.0, STOP_WIDTH / 2.0, "width", "StopWidth", STOP_WIDTH, ("STOP_WIDTH",)
    ),
    # Both saddles' tops, either side of each seat: one plane, one height.
    "saddle_tops": _block_face(
        "z",
        1.0,
        BLOCK_TOP_Z,
        "height",
        "BodySaddleHeight",
        BLOCK_HEIGHT,
        ("BLOCK_HEIGHT", "BLOCK_TOP_Z", "SADDLE_TOP_PICK_X"),
        picks=(-SADDLE_TOP_PICK_X, SADDLE_TOP_PICK_X),
    ),
    "body_saddle_south": _block_face(
        "y", -1.0, BODY_SADDLE_Y, "station", "BodySaddleY", BODY_SADDLE_Y, ("BODY_SADDLE_Y",)
    ),
    "body_saddle_north": _block_face(
        "y",
        1.0,
        BODY_SADDLE_Y + BODY_SADDLE_THICK,
        "thickness",
        "BodySaddleThick",
        BODY_SADDLE_THICK,
        ("BODY_SADDLE_THICK", "BODY_SADDLE_Y"),
    ),
    "tail_saddle_south": _block_face(
        "y", -1.0, TAIL_SADDLE_Y, "station", "TailSaddleY", TAIL_SADDLE_Y, ("TAIL_SADDLE_Y",)
    ),
    "tail_saddle_north": _block_face(
        "y",
        1.0,
        TAIL_SADDLE_Y + TAIL_SADDLE_THICK,
        "thickness",
        "TailSaddleThick",
        TAIL_SADDLE_THICK,
        ("TAIL_SADDLE_THICK", "TAIL_SADDLE_Y"),
    ),
    # Both saddles' side faces share each plane.
    "saddle_west_sides": _block_face(
        "x",
        -1.0,
        -SADDLE_WIDTH / 2.0,
        "width",
        "SaddleSideX",
        SADDLE_SIDE_OFFSET,
        ("SADDLE_SIDE_OFFSET", "SADDLE_WIDTH", "SIDE_W_X"),
    ),
    "saddle_east_sides": _block_face(
        "x", 1.0, SADDLE_WIDTH / 2.0, "width", "SaddleWidth", SADDLE_WIDTH, ("SADDLE_WIDTH",)
    ),
    "crank_pin_west": _crank_pin(-CRANK_PIN_X),
    "crank_pin_east": _crank_pin(CRANK_PIN_X),
    "cone_pin_east": _cone_pin("east"),
    "cone_pin_west": _cone_pin("west"),
}
