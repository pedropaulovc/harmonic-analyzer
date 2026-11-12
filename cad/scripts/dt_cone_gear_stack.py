r"""Axial stack of the gears on the cone gear shaft (MHA-DT-04).

SolidWorks-free and GEOMETRY ONLY, like ``cylinder_bank_layout``: no drawing
notes, no title-block reads, so a print-wording edit can never re-key a part.

The cone set is a SOLID STACK (user ruling 2026-09-28): each gear is one seat
pitch thick and bears on the one before it.  That ruling's "no gear is
bonded" is superseded by the owner decision 2026-11-09 (C1 keyed, PR #1992;
cone_tip_cluster, cone_stack_end_play):

* The 64T (MHA-DT-07) bears on MHA-DT-04's thrust collar and grows NORTH to meet
  T120: its south face stays where the v36 post put it (crank_boss_rim).
* Each cone gear is one seat pitch thick, grown SOUTH from the north face
  every station was laid out on.  The 64T and T120..T030 (MHA-DT-03, on the
  land-1 key) float between the collar and T024; they are modelled, and
  banded here, pushed onto the collar.
* T024 is bonded (LOCTITE 638) on land 2 one STACK_FEELER off T030's north
  face, within STACK_FEELER_BAND; T018 and T012, bonded on MHA-DT-37's
  spigot, butt T024 and each other, and T006's leaves (MHA-DT-37, one face
  width like every cone) butt T012.  The four sit TIP_SET_SHIFT_MM
  (= STACK_FEELER) north of their layout stations (cone_tip_cluster), so
  their faces carry the feeler's set band on top of the faces south of them.
* Every cone gear face prints +/-0.051 (+/-.002 in, #2314), T006's leaves
  included; the 64T's prints +/-0.025 (dt_cone_gear_spec records the
  per-gear band's provenance).  A fit-up acceptance on the measured twenty
  cone faces (STACK_L20_ACCEPT, +/-0.20, the cylinder bank's L20 d'
  precedent) caps the cumulative deviation; a part of the stack is capped by
  partial_stack_band, not by the acceptance alone.

"South" is toward the pivot post (cone station decreasing), "north" toward
the tip.
"""

from __future__ import annotations

from cone_stack_end_play import STACK_FEELER_BAND
from dt_cone_gear_spec import CONE_TEETH, FACE_WIDTH, FACE_WIDTH_BAND, SEAT_PITCH
from dt_crank_drive_gear_spec import FACE_WIDTH_BAND as GEAR64_FACE_WIDTH_BAND

# Cone faces on the shaft: T120 (j = 0) .. T006's leaves (j = 19).
COUNT = len(CONE_TEETH)
# j of T024, the first feeler-set (bonded) gear; T024..T006 are j >= this.
TIP_SET_FIRST_INDEX = CONE_TEETH[::-1].index(24)

# The gear prints its face at four places and is never the longer of the two,
# so the modelled stack closes without interference (cylinder_bank_layout's
# PITCH_LOCKSTEP_TOLERANCE).
PITCH_LOCKSTEP_TOLERANCE = 0.001
if not 0.0 <= SEAT_PITCH - FACE_WIDTH <= PITCH_LOCKSTEP_TOLERANCE:
    raise AssertionError(
        f"cone gear face {FACE_WIDTH} is not the seat pitch {SEAT_PITCH:.6f} "
        f"(0..{PITCH_LOCKSTEP_TOLERANCE})"
    )

# --- stack length acceptance -------------------------------------------------
STACK_L20 = COUNT * FACE_WIDTH  # the twenty cone faces, T120 through T006
# (upper, lower): re-face a long stack; remake the thinnest gear of a short
# one, which no re-facing can lengthen (the cylinder bank's L20 d').
STACK_L20_ACCEPT_BAND = (0.20, -0.20)
STACK_L20_ACCEPT = (
    STACK_L20 + STACK_L20_ACCEPT_BAND[1],
    STACK_L20 + STACK_L20_ACCEPT_BAND[0],
)
if (
    FACE_WIDTH_BAND[0] != -FACE_WIDTH_BAND[1]
    or STACK_L20_ACCEPT_BAND[0] != -STACK_L20_ACCEPT_BAND[1]
):
    raise AssertionError(
        "cone gear face and 20-gear stack bands must both be centred: "
        f"face {FACE_WIDTH_BAND}, L20 {STACK_L20_ACCEPT_BAND}"
    )


def partial_stack_band(n: int) -> tuple[float, float]:
    """(upper, lower) summed face deviation of any n cone gears of an accepted
    stack: each gear inside its band, all COUNT inside the acceptance, so the
    other COUNT - n may lean the opposite way."""
    if not 0 <= n <= COUNT:
        raise ValueError(f"a stack part has 0..{COUNT} gears, not {n}")
    upper, lower = FACE_WIDTH_BAND
    accept_upper, accept_lower = STACK_L20_ACCEPT_BAND
    rest = COUNT - n
    return (
        min(n * upper, accept_upper - rest * lower),
        max(n * lower, accept_lower - rest * upper),
    )


def face_band(j: int, face: str) -> tuple[float, float]:
    """(upper, lower) deviation of cone gear j's ``face`` ("south" or "north")
    from its modelled station, from the collar's north face with the floating
    stack pushed onto it: the 64T plus every cone gear south of that face,
    and, from T024 north (j >= TIP_SET_FIRST_INDEX, modelled TIP_SET_SHIFT_MM
    north of layout), the feeler's set band."""
    if face not in ("south", "north"):
        raise ValueError(f"face is 'south' or 'north', not {face!r}")
    if not 0 <= j < COUNT:
        raise ValueError(f"cone gear index is 0..{COUNT - 1}, not {j}")
    upper, lower = partial_stack_band(j + (face == "north"))
    upper += GEAR64_FACE_WIDTH_BAND[0]
    lower += GEAR64_FACE_WIDTH_BAND[1]
    if j >= TIP_SET_FIRST_INDEX:
        upper += STACK_FEELER_BAND
        lower -= STACK_FEELER_BAND
    return upper, lower


# The worst station of the set, either face.
STATION_BAND = (
    max(face_band(j, face)[0] for j in range(COUNT) for face in ("south", "north")),
    min(face_band(j, face)[1] for j in range(COUNT) for face in ("south", "north")),
)
