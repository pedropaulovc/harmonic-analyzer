r"""Axial stack of the gears on the cone gear shaft (MHA-014).

SolidWorks-free and GEOMETRY ONLY, like ``cylinder_bank_layout``: no drawing
notes, no title-block reads, so a print-wording edit can never re-key a part.

The cone set is a SOLID STACK (user ruling 2026-09-28).  No gear is bonded:
each slides onto its D-flat land (``gear_seat_fit``) and bears on the one
before it, so the stack itself sets every station.

* The 64T (MHA-021) bears on MHA-014's thrust collar and grows NORTH to meet
  T120: its south face stays where the v36 post put it (crank_boss_rim).
* Each cone gear (MHA-013) is one seat pitch thick, grown SOUTH from the
  north face every station was laid out on, so T120 bears on the 64T and
  each gear on the one before it, T006 last.
* The cone tip bushing (MHA-096) bears on T006's north face, and the tip
  block (MHA-092) is feeler-set off the bushing (cone_stack_end_play).
* Every gear face prints +/-0.025 (the cylinder bank's L20 d' rule, user
  ruling 2026-09-28).  A fit-up acceptance on the measured 20-gear stack
  (STACK_L20_ACCEPT, +/-0.20) caps the cumulative deviation; a part of the
  stack is capped by partial_stack_band, not by the acceptance alone.

"South" is toward the pivot post (cone station decreasing), "north" toward
the tip.
"""

from __future__ import annotations

from cone_gear_spec import FACE_WIDTH, FACE_WIDTH_BAND, SEAT_PITCH
from crank_drive_gear_spec import FACE_WIDTH_BAND as GEAR64_FACE_WIDTH_BAND

COUNT = 20  # T120 (j = 0) .. T006 (j = 19)

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
STACK_L20 = COUNT * FACE_WIDTH  # T120 south face to T006 north face
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
    from nominal, from the collar's north face with the stack pushed onto it:
    the 64T plus every cone gear south of that face."""
    if face not in ("south", "north"):
        raise ValueError(f"face is 'south' or 'north', not {face!r}")
    if not 0 <= j < COUNT:
        raise ValueError(f"cone gear index is 0..{COUNT - 1}, not {j}")
    upper, lower = partial_stack_band(j + (face == "north"))
    return (upper + GEAR64_FACE_WIDTH_BAND[0], lower + GEAR64_FACE_WIDTH_BAND[1])


# The worst station of the set, either face.  With centred bands it is not
# T006 but the face with 14 gears south of it (cylinder_bank_layout's finding).
STATION_BAND = (
    max(face_band(j, face)[0] for j in range(COUNT) for face in ("south", "north")),
    min(face_band(j, face)[1] for j in range(COUNT) for face in ("south", "north")),
)
