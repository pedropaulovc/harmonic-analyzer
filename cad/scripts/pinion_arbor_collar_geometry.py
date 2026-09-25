r"""Pure pinion-arbor collar geometry consumed by the part and assembly recipes.

User ruling 2026-09-24 (R1a, dt-pinion-arbor-retention-20260924.md): a turned
steel collar slides on the MHA-102 arbor outboard of the front MHA-056 strap
and is cross-pinned to it with the rig's 1/16 in slotted spring pin.  It is a
northward walk-out backstop behind the drum's Loctite 638 bond, and it gives
the model the sleeve and the flush pin end the ch25 photos show there
(page001_img01, page002_img07).  The pin hole is centred on the length, so
the collar is the same either way round.

Keep drawing-only notes and annotation contracts out of this module so edits
to manufacturing-sheet text cannot invalidate the drive-train assembly recipe.
"""

from __future__ import annotations

COLLAR_OD = 15.0  # the integral head's Ø15, the photographed sleeve
# 17 long (was 20, Codex P2 on #860): the pin station and the length are
# printed at .X independently and the collar fits either way round, so the
# pin-to-inboard-face distance spans 1.6 either side of half the length.  At
# 20 the worst corner pressed the front strap; 17 keeps every corner clear
# (pinion_arbor_collar_spec.collar_strap_gaps) with no band tightened (U27).
COLLAR_LEN = 17.0
BORE = 8.0  # drilled +0.10/0: a slide fit over the Ø8 -0.01/-0.10 arbor
PIN_HOLE_Z = COLLAR_LEN / 2.0  # centred on the length, from either face
