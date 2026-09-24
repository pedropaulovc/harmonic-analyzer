r"""Crank-arm drawing prose -- the hub-seat and seam callouts on its sheet.

Imported ONLY by ``draw_crank_arm`` and its offline test (codex #361; see
``crank_hub_notes``), so a wording edit re-keys the drawing, never the part.
"""

from __future__ import annotations

from crank_hub_notes import seam_callout, seat_bore_callout

# Short lines: the callout is centred under the diameter, so its widest line
# sets how close to the left border the hub-end dimension can stand.  The
# matched fit's acceptance lives here, on the feature (policy rule 6).
HUB_SEAT_CALLOUT = seat_bore_callout("MHA-137 HUB")
# The MHA-138 seam is match-drilled with the hub at assembly; its callout sits
# on the seam itself (policy rule 6) with the pin's nominal size and depth.
SEAM_CALLOUT = seam_callout("MHA-137")
