"""The cone pivot post (MHA-016) to swing platform (MHA-091) screw interface.

Two MHA-142 1/4-20 fillister screws pass the post's clearance holes into the
platform's tapped pair.  Both parts print the same hole-to-hole pitch as ONE
direct dimension with an explicit band, and both bands close against the
screw's diametral clearance in the post holes, with what is left covering tap
tilt.  Each part's spec reads its terms from here, so a band, a hole size or
the pitch cannot change on one side without the stack re-proving itself.

Before this module the post printed two half-pitch stations at .XX (pitch
+/-1.02) and the platform located each tap from its pivot at .XX per axis
(pitch about +/-1.22): 2.24 of possible mismatch against 0.79 of clearance
(Codex P1 on #833).

The post's holes are drilled FROM THE FOOT, where the pitch mates, and
counterbored from the top with a pilot riding the drilled hole (Main ruling on
#833, reversing the "from top face" half of U37).  The drill wanders on its
way up, so every top-side and mid-height wall in the post's stack carries the
wander; the piloted counterbore keeps the head clearance independent of it.

Pure data plus the stack asserts.  The asserts that need only interface data
run at import; the post and platform specs call ``assert_post_stack`` and
``assert_tilt_covered`` at their own import with their geometry (the platform
spec imports the post spec, which imports this module, so this module cannot
import either spec back).
"""

from __future__ import annotations

import math

from asme_b18_6_3 import FILLISTER_HEAD

MM_PER_IN = 25.4

SCREW_SIZE = "1/4-20"
SCREW_MAJOR_DIA = 0.25 * MM_PER_IN  # 6.35
SCREW_HEAD_DIA_MAX = FILLISTER_HEAD["1/4"].dia_max_in * MM_PER_IN  # 10.5156
# The post's through hole: the 0.2812 in (9/32) normal-fit clearance for 1/4.
POST_HOLE_DIA = 7.14248
# Diametral clearance: how far the two patterns may disagree before a
# conforming second screw cannot start.
CLEARANCE = POST_HOLE_DIA - SCREW_MAJOR_DIA  # 0.79248
# Piloted 7/16 counterbore (Main ruling (a) on #833, superseding U37c's
# 11.509): the largest standard size that leaves the collar ligament its 2.0.
POST_CBORE_DIA = 7.0 / 16.0 * MM_PER_IN  # 11.1125

# Hole-to-hole pitch, symmetric about the post axis: a round 1.050 in for
# layout (Main ruling (a) on #833; the harvested v2 value was 26.88704).
PITCH = 1.050 * MM_PER_IN  # 26.67
# Explicit bilateral bands, one per part (Main ruling on #833 P1, option c).
POST_PITCH_BAND = 0.25
PLATFORM_PITCH_BAND = 0.25
# What the two pitch bands leave of the clearance: it covers tap and screw
# tilt over the platform's thread engagement (assert_tilt_covered).
PERPENDICULARITY_ALLOWANCE = CLEARANCE - POST_PITCH_BAND - PLATFORM_PITCH_BAND
# Assumed tap tilt: a hand tap started square in a guide block.
TAP_TILT_DEG = 1.0

# Each post hole's station off the post axis: the pitch band split evenly by
# the pair's implied symmetry about the axis.
POST_HOLE_STATION_BAND = POST_PITCH_BAND / 2.0
# Radial drill wander over the post's drilled length (U37's novice-safe
# figure, kept by Main's ruling), taken in full at every station it touches.
DRILL_WANDER = 0.5

MIN_WEB = 2.0  # wall target (novice-safe margins; 1.5 is the floor)
MIN_HEAD_RADIAL = 0.25  # screw head to piloted counterbore wall


def _stack_text(terms: dict[str, float]) -> str:
    return "; ".join(f"{name} {value:+.4f}" for name, value in terms.items())


def head_radial_terms() -> dict[str, float]:
    """Head clearance in the piloted counterbore (concentric with the hole)."""
    return {
        "counterbore min radius": POST_CBORE_DIA / 2.0,
        "B18.6.3 1/4 fillister head max radius": -SCREW_HEAD_DIA_MAX / 2.0,
    }


def assert_head_clearance() -> float:
    terms = head_radial_terms()
    radial = sum(terms.values())
    if radial < MIN_HEAD_RADIAL:
        raise AssertionError(
            f"head radial clearance {radial:.4f} < {MIN_HEAD_RADIAL}: "
            + _stack_text(terms)
        )
    return radial


def assert_pitch_stack_closes(
    post_band: float,
    platform_band: float,
    allowance: float,
) -> None:
    """Raise unless both pitch bands fit the clearance less ``allowance``.

    Worst case, one part's pitch sits at its upper limit and the other's at its
    lower: the patterns disagree by the sum of the two bands, and that
    disagreement must fit inside the diametral clearance the screw has in the
    post holes after the allowance for tilt.
    """
    if allowance <= 0.0 or post_band + platform_band > CLEARANCE - allowance:
        raise AssertionError(
            f"post pitch +/-{post_band} + platform pitch +/-{platform_band} "
            f"exceeds the {CLEARANCE:.5f} diametral clearance less the "
            f"{allowance:.5f} perpendicularity allowance"
        )


def assert_tilt_covered(engagement_mm: float) -> float:
    """Raise unless the allowance covers opposed tap tilt on both screws.

    A tap tilted by TAP_TILT_DEG shifts its screw by engagement * tan(tilt)
    over the thread engagement; the two screws tilting apart add.
    """
    demand = 2.0 * engagement_mm * math.tan(math.radians(TAP_TILT_DEG))
    break_even = math.degrees(
        math.atan(PERPENDICULARITY_ALLOWANCE / (2.0 * engagement_mm))
    )
    if demand > PERPENDICULARITY_ALLOWANCE:
        raise AssertionError(
            f"tap tilt {TAP_TILT_DEG} deg over {engagement_mm} engagement needs "
            f"{demand:.4f}, over the {PERPENDICULARITY_ALLOWANCE:.4f} allowance "
            f"(break-even {break_even:.2f} deg)"
        )
    return demand


def post_stack_terms(
    *,
    collar_dia: float,
    collar_band: float,
    drilled_plus: float,
    crank_bore_dia: float,
    crank_bore_upper: float,
    cone_bore_dia: float,
    cone_bore_upper: float,
    incline_deg: float,
) -> dict[str, dict[str, float]]:
    """Worst-case walls around the post's mounting holes, term by term.

    ``collar_band`` is the +/- deviation printed on the collar diameter;
    ``drilled_plus`` is the DRILLED HOLES upper deviation, applied to the thru
    hole and the counterbore alike; the ``*_upper`` values are the running
    bores' upper size deviations.
    """
    inward = PITCH / 2.0 - POST_HOLE_STATION_BAND - DRILL_WANDER
    hole_r = (POST_HOLE_DIA + drilled_plus) / 2.0
    return {
        "collar-to-counterbore ligament": {
            "collar min radius": (collar_dia - collar_band) / 2.0,
            "half pitch": -PITCH / 2.0,
            "station band": -POST_HOLE_STATION_BAND,
            "drill wander at exit": -DRILL_WANDER,
            "counterbore max radius": -(POST_CBORE_DIA + drilled_plus) / 2.0,
        },
        # The crank bore runs along model Z through the post axis; the
        # vertical hole's axis is `inward` from it at its closest.
        "hole-to-crank-bore web": {
            "hole axis min station": inward,
            "hole max radius": -hole_r,
            "crank bore max radius": -(crank_bore_dia + crank_bore_upper) / 2.0,
        },
        # The cone bore's axis is yawed incline_deg off model Z in plan, so
        # its common normal with the vertical hole axis is station * cos(I).
        "hole-to-cone-bore web": {
            "hole axis min station, normal to cone axis": inward
            * math.cos(math.radians(incline_deg)),
            "hole max radius": -hole_r,
            "cone bore max radius": -(cone_bore_dia + cone_bore_upper) / 2.0,
        },
    }


def assert_post_stack(**geometry: float) -> dict[str, float]:
    """Raise unless every post wall around the holes meets MIN_WEB."""
    stacks = post_stack_terms(**geometry)
    walls = {name: sum(terms.values()) for name, terms in stacks.items()}
    short = [name for name, wall in walls.items() if wall < MIN_WEB]
    if short:
        raise AssertionError(
            " | ".join(
                f"{name} {walls[name]:.4f} < {MIN_WEB}: {_stack_text(stacks[name])}"
                for name in short
            )
        )
    return walls


assert_pitch_stack_closes(
    POST_PITCH_BAND, PLATFORM_PITCH_BAND, PERPENDICULARITY_ALLOWANCE
)
assert_head_clearance()
