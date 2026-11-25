"""End play of the cone gear stack on MHA-DT-04, and of MHA-DT-04 in its bearings.

Two independent floats (user ruling 2026-09-29; owner decision C1 keyed,
2026-11-09, PR #1992, cone_tip_cluster):

* The stack (MHA-DT-07 and T030..T120 of MHA-DT-03, on the land-1 key)
  floats on the shaft between MHA-DT-04's integral thrust collar and T024,
  which is bonded (LOCTITE 638) on the round land 2 and is the stack's north
  stop.  At fit-up the stack is pushed onto the thrust collar and T024 is
  bonded one feeler leaf off T030's north face, any one leaf of
  STACK_FEELER_RANGE.  That gap is how far the stack can float north in
  service, whatever the shaft does.  The range's thin end is the thinnest
  leaf of the shop's inch feeler gauge (dt_feeler_leaves, #3042) whose
  tightest setting, its own tolerance booked, keeps MIN_END_PLAY with
  MARGIN_SPARE to spare (pinion_rig_layout.DRUM_END_SHIM's rule), and the
  shaft spec's recess proof holds there.  T024, T018, T012 and T006 are bonded
  to the shaft, so they move only with it.
* The shaft floats between the MHA-DT-05 boss (its thrust collar's south face)
  and the end screw (cone_tip_cluster), SHAFT_END_PLAY, set by the end screw
  against the brass bushing on T006's pivot alone and locked by MHA-DT-21's
  pinch slit.

The 2026-09-29 collar version (MHA-DT-VN-54 set-screw collar off T006, the
MHA-DT-VN-55 cup on the tip) is superseded by that decision.

Free of spec imports on purpose (its one import, dt_feeler_leaves, has none):
the shaft spec, the gear-mesh proof and the assembly sheet all read these
numbers, and none of them may pick up another spec through this module.
"""

from __future__ import annotations

import dt_feeler_leaves as _leaves

MIN_END_PLAY = 0.10  # running floor: the stack never clamped on the shaft
MARGIN_SPARE = 0.25  # novice spare over every floor (pinion_rig_layout rule)
# D4, delegated ruling 2026-11-24 (Main), no precedent; owner review #2144
# (audit part 2 C7 row 1R):
# "print the widest leaf range whose thin end keeps at least 0.03 mm of the
# shaft end inside T024's bore with the baseless creep term dropped".  The
# 0.10 mm "T024 can creep on its land before the 638 fixes" term (3cdf40acf1)
# had no ruling behind it: the leaf stays under T024 until the bond grabs
# (1U) and nothing pushes T024 toward T030 before the cure.  The thin end
# below keeps 0.036 mm of the end inside T024's bore
# (dt_cone_gear_shaft_spec.TIP_END_RECESS_FLOOR_MM); the thick end is C7's
# own .020.  The model sets T024 on a .019 leaf, inside the range.
STACK_FEELER_RANGE = (
    _leaves.smallest_setting(MIN_END_PLAY + MARGIN_SPARE, 0.0),  # .015
    _leaves.thousandths(20),
)
STACK_FEELER = _leaves.thousandths(19)
for _leaf in (*STACK_FEELER_RANGE, STACK_FEELER):
    if len(_leaves.leaf_stack(_leaf)) != 1:
        raise AssertionError(f"{_leaf:.4f} mm is not one leaf of the set")
if not STACK_FEELER_RANGE[0] <= STACK_FEELER <= STACK_FEELER_RANGE[1]:
    raise AssertionError("the model's stack leaf is outside the printed range")
# (min, max) float of the stack north off the thrust collar in service: the
# range's ends, each leaf's own tolerance booked.
STACK_FLOAT = (
    STACK_FEELER_RANGE[0] - _leaves.LEAF_TOLERANCE,
    STACK_FEELER_RANGE[1] + _leaves.LEAF_TOLERANCE,
)
# What T024's gap can be off the model's leaf by, either way (the thin end's
# side, the larger): the symmetric band the station proofs book.
STACK_FEELER_BAND = max(STACK_FEELER - STACK_FLOAT[0], STACK_FLOAT[1] - STACK_FEELER)
# (min, max) shaft end play at MHA-DT-00's end-screw step: the end screw is
# run in until the shaft just stops shuttling, then backed off 1/8 turn
# (0.113 on the 1/4-28).  0.05: the shaft never runs clamped.  0.305: the
# title block's .XXX row (sheet 16 row 8 prints .002-.012; restoration
# round 1, 2026-11-25, drawing-guidelines rule 4: no check fails at it: the
# end screw's pivot engagement 1.401 -> 1.346 mm, its embed window margins
# 3.218 -> 3.163 / 2.658 mm, the bushing air 0.024 mm and the look 0.731 mm
# unchanged).  0.305, not 0.3048: the inward rounding then cannot print .011.
SHAFT_END_PLAY = (0.05, 0.305)
# The cone set's in-service float north of its layout stations along the
# cone axis: the shaft at the far end of its play and the stack at the far
# end of its own.  The bonded tip gears sit STACK_FEELER north of layout
# (cone_tip_cluster.TIP_SET_SHIFT_MM) within STACK_FEELER_BAND, so their
# envelope lies inside this one.
CONE_FLOAT_NORTH = SHAFT_END_PLAY[1] + STACK_FLOAT[1]
