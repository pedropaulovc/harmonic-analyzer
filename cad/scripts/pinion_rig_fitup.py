"""Fit-up settings for the pinion rig that the prints state and no build reads.

Every fit-up setting is a stock leaf, or a pair of leaves, of one purchased
thickness gage (FEELER_GAGE), and each is sized in pinion_rig_layout, where the
worst fitted stacks that need it live.  This module is the print-facing import
point: it re-exports the settings, checks each is a leaf or a leaf pair of the
gage, and words the step each print carries.  Only tests and drawing steps
import it.

- The front block is set FRONT_BLOCK_FEELER off the front strap (+/- BAND;
  the base's RIG SET note, before its seats are transferred), which sets the
  pinned cluster's end play.
- MHA-DT-019 is match-drilled on a DRUM_END_SHIM leaf at the drum's front end
  (SHAFT_DRILL_STEP), which sets the drum's end play.
- The rig's axial datum (user ruling P1-2): with the cylinder-gear bank
  pushed north, the drum's back end is set RIG_SET_LEAF_D off the north
  MHA-DT-012's back face before the block seats are transferred (the base's
  RIG SET note, RIG_SET_STEP, which both transfer callouts name).  The bank pushed north is what keeps its end
  play out of j = 19's stack (#743), so the step says so.
- The MHA-DT-023 collars (user ruling P1-1): the front collar's front face
  FRONT_COLLAR_LEAF off the front block, the back collar's back face
  BACK_COLLAR_LEAF_F off the back block (COLLAR_SET_STEP).  Nothing is cut
  there, so it is a drive-train assembly step, never an MHA-DT-023 note (policy
  rule 6, as MHA-DT-018 keeps its feeler off its own print).
- The MHA-DT-024 foot pad's aft edge, flush with the strip's, is set
  SPRING_PAD_LEAF off the back block before its seat is transferred (the
  same RIG SET note).  The foot lies east of the block's east end, so the
  leaf stands on edge against the block's inner face and overhangs that
  end to meet the pad.
- ASSEMBLY_SEQUENCE orders the rig's assembly steps.  The MHA-DT-033 collar's
  install, the bonds and the MHA-DT-030 drive-through are each part spec's
  ASSEMBLY_STEP (policy rule 6 moved them off the part sheets, #814),
  imported here, never retyped.
"""

from __future__ import annotations

import dt_pinion_arbor_collar_spec
import dt_pinion_arbor_spec
import dt_pinion_cam_pin_spec
import dt_pinion_handle_spec
import dt_pinion_lever_pin_spec
from pinion_rig_layout import (
    BACK_COLLAR_LEAF_F,
    DRUM_END_SHIM,
    DRUM_END_SHIM_SET_ERROR,
    FEELER_LEAF_MAX,
    FEELER_LEAF_STEP,
    FEELER_SET_ERROR,
    FLUSH_SET_ERROR,
    FRONT_BLOCK_FEELER,
    FRONT_BLOCK_FEELER_BAND,
    RIG_SET_LEAF_D,
    RIG_SET_LEAVES,
    SPRING_PAD_LEAF,
)
from vn_pinion_strap_pin_spec import PIN_SUB_FLUSH_MAX

# One purchased set, pinned like any other bought part: Starrett 66MA metric
# thickness gage, 20 straight tempered-steel leaves 0.05-1.00 mm in 0.05 steps
# (starrett.com cat-no 66MA, EDP 55974, read 2026-09-25).
FEELER_GAGE_NAME = "STARRETT 66MA"
FEELER_GAGE = f"{FEELER_GAGE_NAME} METRIC THICKNESS GAGE (EDP 55974)"
FEELER_GAGE_LEAVES_MM = tuple(round(0.05 * k, 2) for k in range(1, 21))
if (FEELER_GAGE_LEAVES_MM[0], FEELER_GAGE_LEAVES_MM[-1]) != (
    FEELER_LEAF_STEP,
    FEELER_LEAF_MAX,
):
    raise AssertionError("pinion_rig_layout sizes leaves the gage does not carry")

# The front collar sits flush with the front strap's outer face, so its leaf
# is the front block's own feeler (ruling (c)).
FRONT_COLLAR_LEAF = FRONT_BLOCK_FEELER

# Every single-leaf setting, by the step that uses it.
SINGLE_LEAF_SETTINGS = {
    "front block feeler": FRONT_BLOCK_FEELER,
    "MHA-DT-019 drum end shim": DRUM_END_SHIM,
    "front collar leaf": FRONT_COLLAR_LEAF,
    "back collar leaf F": BACK_COLLAR_LEAF_F,
    "spring pad leaf": SPRING_PAD_LEAF,
}
for _name, _leaf in SINGLE_LEAF_SETTINGS.items():
    if round(_leaf, 2) not in FEELER_GAGE_LEAVES_MM:
        raise AssertionError(f"{_name} {_leaf} mm is not a leaf of the {FEELER_GAGE}")
# The rig-set D is the one setting that needs a pair of leaves.
if len(RIG_SET_LEAVES) > 2 or any(
    round(leaf, 2) not in FEELER_GAGE_LEAVES_MM for leaf in RIG_SET_LEAVES
):
    raise AssertionError(f"rig-set D {RIG_SET_LEAVES} is not one or two gage leaves")
if abs(sum(RIG_SET_LEAVES) - RIG_SET_LEAF_D) > 1e-9:
    raise AssertionError("the rig-set leaves do not make up D")
# Every setting is made to the same band as the front-block feeler.
if FEELER_SET_ERROR != FRONT_BLOCK_FEELER_BAND or DRUM_END_SHIM_SET_ERROR != (
    FRONT_BLOCK_FEELER_BAND
):
    raise AssertionError("a fit-up setting carries its own band")


# The set-up the rig-set leaf assumes (#743): the bank's end play taken up
# north, so g19 never sits north of the datum D is measured from.
RIG_SET_BANK_PRECONDITION = "BANK PUSHED NORTH"


def _leaves_text(leaves: tuple[float, ...]) -> str:
    return " + ".join(f"{leaf:.2f}" for leaf in leaves)


# The step each print carries, uppercase to match the sheets.  The base
# carries the set-up its transfer seats are spotted in: RIG_SET_STEP is a
# note named by its first words, and both transfer callouts name it
# (TRANSFER_AFTER_RIG_SET).  On the callouts it
# overflowed the sheet (pc-p1 render: through the top border, over the TOP
# VIEW caption, section arrow A and the MHA-VN-027 callout), and the sheet takes
# no numbered notes (Main), so the name is the reference.
RIG_SET_NAME = "RIG SET"
RIG_SET_STEP = "\n".join(
    (
        f"{RIG_SET_NAME}, BEFORE SPOTTING THE TRANSFER SEATS:",
        f"FRONT MHA-DT-018 {FRONT_BLOCK_FEELER:.2f} LEAF OFF FRONT MHA-DT-014;",
        f"MHA-DT-001 BACK END {_leaves_text(RIG_SET_LEAVES)} LEAVES OFF",
        f"NORTH MHA-DT-012 BACK FACE, {RIG_SET_BANK_PRECONDITION};",
        f"MHA-DT-024 PAD {SPRING_PAD_LEAF:.2f} LEAF OFF MHA-DT-018.",
    )
)
TRANSFER_AFTER_RIG_SET = f"AFTER {RIG_SET_NAME};"
COLLAR_SET_STEP = (
    f"SET MHA-DT-023 COLLARS ON {FEELER_GAGE_NAME} LEAVES, LOCK SCREWS:\n"
    f"  FRONT COLLAR FRONT FACE {FRONT_COLLAR_LEAF:.2f} OFF FRONT MHA-DT-018;\n"
    f"  BACK COLLAR BACK FACE {BACK_COLLAR_LEAF_F:.2f} OFF BACK MHA-DT-018."
)

# MHA-DT-019's drilling pose.  Main's re-ruling (2026-09-26, after the
# pc-858x928b eye pass; it supersedes the #858 restricted review's rulings 2
# and 3 that printed it on MHA-DT-019): the fitter match-drills the shaft
# working from MHA-DT-000, and the machinist making MHA-DT-019 never drills those
# holes, so the pose is printed where it is performed, once (policy rule 6,
# as #857's shim note).  MHA-DT-019's callout keeps the hole specification; its
# "SEE MHA-DT-000 STEP n" pointer lands at integration, generated from the
# assembly step registry, never a hand-typed step name or number.  The pose
# is what fixes the pin-hole stations -- the shaft prints none -- and its two
# set errors ride the bearing stacks by name (pinion_rig_layout).  The drive
# carries its own acceptance (Codex #858, PRRT_kwDOPHDy386mV2GL): neither end
# proud, since the west end faces the MHA-DT-023 collar across 0.38 of air, and
# neither end deeper than vn_pinion_strap_pin_spec.PIN_SUB_FLUSH_MAX, which keeps
# a pin diameter of grip in each strap wall.
SHAFT_DRILL_NAME = "SHAFT DRILL SET"
STRAP_PIN_NUMBER = "MHA-VN-033"
SHAFT_DRILL_STEP = "\n".join(
    (
        f"{SHAFT_DRILL_NAME}: MATCH-DRILL MHA-DT-019 THRU MHA-DT-014 CROSS HOLES, 2 PL,",
        f"MHA-DT-019 REAR END FLUSH WITH MHA-DT-018 REAR FACE +/-{FLUSH_SET_ERROR:.2f},",
        "STRAPS ON BACK STOP, MHA-DT-001 ON BACK STRAP,",
        f"{DRUM_END_SHIM:.2f} FEELER AT MHA-DT-001 FRONT END; DRIVE {STRAP_PIN_NUMBER} PINS,",
        f"BOTH ENDS 0 TO {PIN_SUB_FLUSH_MAX:.1f} BELOW THE MHA-DT-014 EDGES.",
    )
)

# The rig's assembly steps in order.  MHA-DT-033 goes on first, pinned, with the
# front strap behind it: neither passes the Ø15 head, nor the drum once it is
# bonded (Codex #860, PRRT_kwDOPHDy386mTbe7).  The three LOCTITE 638 bonds
# follow: the shaft is drilled with MHA-DT-001 on the back strap, and RIG SET
# measures from the drum's back end, so the drum joint must be made before
# either.
# The shaft is pinned before RIG SET: the pins freeze the strap spacing the
# drum's back end is set from.  MHA-DT-030 is driven last, through the lever hub
# and lift rod match-drilled with the grip parked, once the collars are set.
ASSEMBLY_SEQUENCE = (
    dt_pinion_arbor_collar_spec.ASSEMBLY_STEP,
    dt_pinion_arbor_spec.ASSEMBLY_STEP,
    dt_pinion_handle_spec.ASSEMBLY_STEP,
    dt_pinion_cam_pin_spec.ASSEMBLY_STEP,
    SHAFT_DRILL_STEP,
    RIG_SET_STEP,
    COLLAR_SET_STEP,
    dt_pinion_lever_pin_spec.ASSEMBLY_STEP,
)

__all__ = [
    "ASSEMBLY_SEQUENCE",
    "BACK_COLLAR_LEAF_F",
    "COLLAR_SET_STEP",
    "DRUM_END_SHIM",
    "DRUM_END_SHIM_SET_ERROR",
    "FEELER_GAGE",
    "FEELER_GAGE_LEAVES_MM",
    "FEELER_GAGE_NAME",
    "FEELER_SET_ERROR",
    "FRONT_BLOCK_FEELER",
    "FRONT_BLOCK_FEELER_BAND",
    "FRONT_COLLAR_LEAF",
    "RIG_SET_BANK_PRECONDITION",
    "RIG_SET_LEAF_D",
    "RIG_SET_LEAVES",
    "RIG_SET_NAME",
    "RIG_SET_STEP",
    "SHAFT_DRILL_NAME",
    "SHAFT_DRILL_STEP",
    "SINGLE_LEAF_SETTINGS",
    "SPRING_PAD_LEAF",
    "STRAP_PIN_NUMBER",
    "TRANSFER_AFTER_RIG_SET",
]
