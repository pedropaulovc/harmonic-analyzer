"""End play of the cone gear stack on MHA-DT-004, and of MHA-DT-004 in its bearings.

Two independent floats (user ruling 2026-09-29):

* The stack (MHA-DT-007 and the twenty MHA-DT-003) floats on the shaft between
  MHA-DT-004's integral thrust collar and the MHA-VN-016 set-screw shaft collar.  At
  fit-up the stack is pushed onto the thrust collar, the MHA-VN-016 collar is
  pushed against T006 over one COLLAR_FEELER leaf and its set screw locked on
  the Sec4 D-flat.  That gap is how far the stack can float north in service,
  whatever the shaft does.  The feeler follows the pinion drum's shim rule
  (pinion_rig_layout.DRUM_END_SHIM): the smallest 0.05 blade whose
  tightest setting keeps MIN_END_PLAY with MARGIN_SPARE to spare.
* The shaft floats between the MHA-DT-005 boss (its thrust collar's south face)
  and the MHA-VN-017 cup (its tip), SHAFT_END_PLAY, set by the cup screw alone.
  The tip block and the MHA-VN-016 collar never touch
  (build_drive_train_assembly's collar-to-block air).

Import-free on purpose: the shaft spec, the gear-mesh proof and the assembly
sheet all read these numbers, and none of them may pick up another spec
through this module.
"""

from __future__ import annotations

import math

MIN_END_PLAY = 0.10  # running floor: the stack never clamped on the shaft
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
FEELER_STEP = 0.05  # blades of the metric gauge set
COLLAR_FEELER_BAND = 0.10  # set error: the collar creeps as its set screw bites
COLLAR_FEELER = FEELER_STEP * math.ceil(
    round((MIN_END_PLAY + MARGIN_SPARE + COLLAR_FEELER_BAND) / FEELER_STEP, 9)
)  # 0.45
# (min, max) float of the stack north off the thrust collar in service.
STACK_FLOAT = (
    COLLAR_FEELER - COLLAR_FEELER_BAND,
    COLLAR_FEELER + COLLAR_FEELER_BAND,
)
# (min, max) shaft end play at MHA-DT-000 step 3: the cup screw is run in until
# the shaft just stops shuttling, then backed off 1/8 turn (0.099 on the
# #10-32).  0.05: the shaft never runs clamped.  0.25: the most the
# collar-to-block air, the adjuster's embed window and the drum's engaged-zone
# margin book for it.
SHAFT_END_PLAY = (0.05, 0.25)
# The stack's in-service float north of its model pose along the cone axis:
# the shaft at the far end of its play and the stack at the far end of its own.
CONE_FLOAT_NORTH = SHAFT_END_PLAY[1] + STACK_FLOAT[1]
