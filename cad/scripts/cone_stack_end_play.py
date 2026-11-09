"""End play of the cone gear stack on MHA-DT-04, and of MHA-DT-04 in its bearings.

Two independent floats (user ruling 2026-09-29; owner decision C1 keyed,
2026-11-09, PR #1992, cone_tip_cluster):

* The stack (MHA-DT-07 and T030..T120 of MHA-DT-03, on the land-1 key)
  floats on the shaft between MHA-DT-04's integral thrust collar and T024,
  which is bonded (LOCTITE 638) on the round land 2 and is the stack's north
  stop.  At fit-up the stack is pushed onto the thrust collar and T024 is
  bonded one STACK_FEELER leaf off T030's north face.  That gap is how far
  the stack can float north in service, whatever the shaft does.  The feeler
  follows the pinion drum's shim rule (pinion_rig_layout.DRUM_END_SHIM): the
  smallest 0.05 blade whose tightest setting keeps MIN_END_PLAY with
  MARGIN_SPARE to spare.  T024, T018, T012 and T006 are bonded to the shaft,
  so they move only with it.
* The shaft floats between the MHA-DT-05 boss (its thrust collar's south face)
  and the end screw (cone_tip_cluster), SHAFT_END_PLAY, set by the end screw
  against the brass bushing on T006's pivot alone and locked by MHA-DT-21's
  pinch slit.

The 2026-09-29 collar version (MHA-DT-VN-54 set-screw collar off T006, the
MHA-DT-VN-55 cup on the tip) is superseded by that decision.

Import-free on purpose: the shaft spec, the gear-mesh proof and the assembly
sheet all read these numbers, and none of them may pick up another spec
through this module.
"""

from __future__ import annotations

import math

MIN_END_PLAY = 0.10  # running floor: the stack never clamped on the shaft
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set
# Set error: T024 can creep on its land before the 638 fixes.
STACK_FEELER_BAND = 0.10
STACK_FEELER = FEELER_STEP * math.ceil(
    round((MIN_END_PLAY + MARGIN_SPARE + STACK_FEELER_BAND) / FEELER_STEP, 9)
)  # 0.45
# (min, max) float of the stack north off the thrust collar in service.
STACK_FLOAT = (
    STACK_FEELER - STACK_FEELER_BAND,
    STACK_FEELER + STACK_FEELER_BAND,
)
# (min, max) shaft end play at MHA-DT-00's end-screw step: the end screw is
# run in until the shaft just stops shuttling, then backed off 1/8 turn
# (0.113 on the 1/4-28).  0.05: the shaft never runs clamped.  0.25: the most
# the tip air ledger and the drum's engaged-zone margin book for it.
SHAFT_END_PLAY = (0.05, 0.25)
# The cone set's in-service float north of its layout stations along the
# cone axis: the shaft at the far end of its play and the stack at the far
# end of its own.  The bonded tip gears sit STACK_FEELER north of layout
# (cone_tip_cluster.TIP_SET_SHIFT_MM) within STACK_FEELER_BAND, so their
# envelope lies inside this one.
CONE_FLOAT_NORTH = SHAFT_END_PLAY[1] + STACK_FLOAT[1]
