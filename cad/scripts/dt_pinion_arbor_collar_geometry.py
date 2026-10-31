r"""Pure pinion-arbor collar geometry consumed by the part and assembly recipes.

User ruling 2026-09-24 (R1a, dt-pinion-arbor-retention-20260924.md): a turned
steel collar slides on the MHA-DT-22 arbor outboard of the front MHA-DT-14 strap
and is cross-pinned to it with the rig's 1/16 in slotted spring pin.  It is a
northward walk-out backstop behind the drum's Loctite 638 bond, and it gives
the model the sleeve and the flush pin end the ch25 photos show there
(page001_img01, page002_img07).  The pin hole is centred on the length, so
the collar is the same either way round.

Keep drawing-only notes and annotation contracts out of this module so edits
to manufacturing-sheet text cannot invalidate the drive-train assembly recipe.
"""

from __future__ import annotations

COLLAR_OD = 14.986  # .59, the integral head's Ø.59, the photographed sleeve
# 17 long (was 20, Codex P2 on #860): the pin station and the length are
# printed independently and the collar fits either way round, so the
# pin-to-inboard-face distance spans both bands either side of half the
# length.  At 20 the worst corner pressed the front strap; 17 kept every corner
# clear (dt_pinion_arbor_collar_spec.collar_strap_gaps) with no band tightened
# (U27).  #290: snapped to .66 so the centred pin station prints .33 at .XX.
COLLAR_LEN = 16.764  # .66
BORE = 7.9375  # 5/16 drill, title-block drilled band: a slide fit over the 5/16 arbor
PIN_HOLE_Z = COLLAR_LEN / 2.0  # .33, centred on the length, from either face
