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
foot-stop face, at Y0; crank socket axis +Z (up). The base top is at
Z -1-3/16 in and the base bottom 3/8 in below it. Block heights and the seat axes print from the
base top, every station along the post from foot B, and every pin top from
the post axis: a pin top sets a sleeve face against that axis.

Provenance: make-data sections 1.2/1.3 supply the frame and bed height; its
pin rows predate CN-B5. The relational annulus/spread rule is in
pedropaulovc/prechips examples/inventory/pedro-shop.toml at
83807386e38aee0757762c002ee2fbea9a6318d1 (CN-B5).
examples/cone-pivot-post/built-up.toml S6 at
d2c5d58557149a8b5ced6ae27b89a6cd094517f6 references the tops to the post axis
over a seated gauge arbor. Old export X/Z stations are not geometry owners.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import _config
import dt_cone_pivot_post_spec as post
from _gtol_cylinder import CylinderFace
from _printed_tolerance import angular_band_deg, printed_band_mm
from _inch import inch
from _surface_finish import SEAT_UM, SurfaceFinishControl, surface_finish_by_key

# Base plate, foot stop and the two saddles (inventory cone-bond-cradle rows),
# snapped to inch plate and block sizes for the all-inch experiment.
BASE_WIDTH = inch(25, 8)
BASE_LENGTH = inch(21, 4)
BASE_THICK = inch(3, 8)
BASE_TOP_Z = -inch(19, 16)
BASE_END_Y = -inch(1, 2)
STOP_WIDTH = inch(19, 16)
STOP_THICK = -BASE_END_Y  # flush with the base end; its +Y face is foot B
BLOCK_HEIGHT = inch(9, 16)  # the stop and both saddles, above the base top
BLOCK_TOP_Z = BASE_TOP_Z + BLOCK_HEIGHT
SADDLE_WIDTH = inch(19, 8)
BODY_SADDLE_Y = inch(3, 8)
BODY_SADDLE_THICK = inch(3, 8)
TAIL_SADDLE_Y = inch(63, 16)
TAIL_SADDLE_THICK = inch(13, 16)
# Seats: on the post axis, SEAT_AXIS_HEIGHT above the base top. The body seat
# takes the post's turned body; the tail seat the raw bar the tail is left at
# (cone-plan stock component "body", dia_mm 44.45). Both are MATCHED FITS
# (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the body prints at .X (+/-0.8) on the post and the bar
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
if abs(BED_HEIGHT - inch(3, 4)) > 1e-9:
    raise AssertionError("body seat bed height left its 3/4 in")

# Pins: hardened 5/32 in stock dowels pressed into reamed holes in the base.
PIN_DIA = inch(5, 32)
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
CRANK_PIN_X = inch(1, 4)
CRANK_PIN_Y = post.CRANK_BORE_HEIGHT
CRANK_PIN_TOP_Z = -round(post.CRANK_BOSS_NORTH_FACE, PIN_TOP_PLACES)
CRANK_PIN_HEIGHT = CRANK_PIN_TOP_Z - BASE_TOP_Z
if abs(round(CRANK_PIN_HEIGHT, 2) - 8.73) > 1e-9:
    raise AssertionError("crank pin height left the plan's 8.73")

# Cone pins: tilted with the cone journal, axis n = (sin i, 0, cos i), the
# reverse of the post's north-cap normal. Both stand at the journal station,
# one either side of the journal axis, CONE_PIN_SPREAD along u = (cos i, 0,
# -sin i) (square to n in the post's mid-plane): each top centres on the
# north cap's annulus between the bore and the boss rim, never on the
# journal axis, where a top would sit over the bore (prechips CN-B5). The
# square tops lie in the north-cap plane, CONE_BOSS_LENGTH / 2 below the
# journal centre along n. Each pin is a stock dowel reaching its own length
# from its top down n into the base: the east (+X) top stands lower, so it
# takes the shorter one (5/32 x 5/8 and 5/32 x 3/4 stock dowels; prechips
# cone-pin-1 4x16, cone-pin-2 4x20 before the all-inch experiment).
# CN-B5's bought dowels have a ground end flat inside the stock dowel
# envelope modeled here. Contact is partial annulus/edge bearing, not a
# full-face Ø4 disk: its ±0.5-degree setup-error example bounds axial motion
# by 1.6 * tan(0.5 degrees) < 0.014. The source accepts a blued dry fit on
# both pin tops and refusal of a 0.05 feeler under the cap at either pin.
# Those process checks do not turn the stock envelope into a contact patch.
CONE_PIN_Y = post.BORE_HEIGHT
CONE_PIN_SPREAD = inch(5, 16)
if not post.BORE_DIA / 2.0 < CONE_PIN_SPREAD < post.CONE_BOSS_DIA / 2.0:
    raise AssertionError("cone pin tops left the north cap's annulus")
_INCLINE = math.radians(post.INCLINE_DEG)
CONE_PIN_AXIS = (math.sin(_INCLINE), 0.0, math.cos(_INCLINE))
CONE_PIN_ACROSS = (math.cos(_INCLINE), 0.0, -math.sin(_INCLINE))
_NORTH_CAP = surface_finish_by_key(post.SURFACE_FINISHES, "cone_boss_north_face").face
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


CONE_PIN_EAST = ConePin(side=1, length=inch(5, 8))
CONE_PIN_WEST = ConePin(side=-1, length=inch(3, 4))
CONE_PINS = {"east": CONE_PIN_EAST, "west": CONE_PIN_WEST}


def require_cone_pin_top_station(top_mm: tuple[float, float, float], side: int) -> None:
    """CN-B5's station guard in the current post frame, not its old X/Z pins.

    The cap's outward normal and offset locate its centre from the journal
    axis; the pin centres straddle it by CONE_PIN_SPREAD along the cap.
    Keep the original half-printed-unit station allowance.
    """
    expected = tuple(
        centre + _NORTH_CAP.offset_mm * normal + side * CONE_PIN_SPREAD * across
        for centre, normal, across in zip(
            (0.0, post.BORE_HEIGHT, 0.0),
            _NORTH_CAP.normal,
            CONE_PIN_ACROSS,
            strict=True,
        )
    )
    if any(
        abs(actual - nominal) > PIN_TOP_ROUNDING
        for actual, nominal in zip(top_mm, expected, strict=True)
    ):
        raise AssertionError("cone pin top left the current post north-cap station")


for _pin in CONE_PINS.values():
    require_cone_pin_top_station((_pin.top_x, CONE_PIN_Y, _pin.top_z), _pin.side)
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
# fit's acceptance (drawing-guidelines.md rule 3 (decimal places carry the tolerance); run-17 review asked for its function).
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


