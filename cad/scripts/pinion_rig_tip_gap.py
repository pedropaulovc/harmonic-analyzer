"""MHA-A03 feeler setting from the assembly's saved cam-contact rest pose.

The configured level-centre 2.2425 mm construction gap locates the fixed block
seats.  The spring then swings the rigid strap clockwise onto the eccentric-down
cam before the assembly is saved; the actual rest tooth-tip gap is about 2.4853
mm.  Fit-up rounds THAT gap to 2.50 mm of STARRETT 66MA feeler leaves.
"""

from __future__ import annotations

import pinion_rig_park_geometry as park
from pinion_rig_fitup import FEELER_GAGE_LEAVES_MM, FEELER_GAGE_NAME
from pinion_rig_layout import FEELER_LEAF_STEP
from pinion_rig_park_geometry import TIP_GAP_ACCEPT, TIP_GAP_ACCEPT_BAND, TIP_GAP_FEELER


SETUP_TIP_GAP = park.APINION_GAP
REST_TIP_GAP = park.REST_TIP_GAP
if not REST_TIP_GAP > SETUP_TIP_GAP:
    raise AssertionError("rest tip gap must exceed the level-centre construction gap")


def leaf_stack(setting: float) -> tuple[float, ...]:
    """The gage leaves that make up ``setting``, thickest first: as many of the
    thickest leaf as fit, then the one leaf for the remainder."""
    thickest = FEELER_GAGE_LEAVES_MM[-1]
    steps, per_leaf = round(setting / FEELER_LEAF_STEP), round(thickest / FEELER_LEAF_STEP)
    count, remainder = divmod(steps, per_leaf)
    leaves = (thickest,) * count
    if remainder:
        leaves += (FEELER_GAGE_LEAVES_MM[remainder - 1],)
    return leaves


TIP_GAP_LEAVES = leaf_stack(TIP_GAP_FEELER)
TIP_GAP_LEAVES_TEXT = " + ".join(f"{leaf:.2f}" for leaf in TIP_GAP_LEAVES)
TIP_GAP_FEELER_TEXT = (
    f"{TIP_GAP_FEELER:.2f} FEELER ({TIP_GAP_LEAVES_TEXT} {FEELER_GAGE_NAME} LEAVES)"
)
TIP_GAP_ACCEPT_TEXT = f"ACCEPT {TIP_GAP_ACCEPT[0]:.2f}-{TIP_GAP_ACCEPT[1]:.2f}"

__all__ = [
    "SETUP_TIP_GAP",
    "REST_TIP_GAP",
    "TIP_GAP_ACCEPT",
    "TIP_GAP_ACCEPT_BAND",
    "TIP_GAP_ACCEPT_TEXT",
    "TIP_GAP_FEELER",
    "TIP_GAP_FEELER_TEXT",
    "TIP_GAP_LEAVES",
    "leaf_stack",
]
