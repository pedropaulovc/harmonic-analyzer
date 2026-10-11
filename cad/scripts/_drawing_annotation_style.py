"""Leader style constants shared by drawing annotation authoring.

Separate module so edits re-key only recipes that use this concern.
"""

from __future__ import annotations


# swLeaderStyle_e.swBENT / swLeaderSide_e.swLS_SMART. Every leadered annotation
# is bent: a straight leader runs at whatever angle its anchor-to-text vector
# happens to take, which is what drove the old Ra symbol's leader diagonally
# across two views. A bent leader lands its elbow horizontally at the text.
_LEADER_BENT = 2


_LEADER_SIDE_SMART = 0
