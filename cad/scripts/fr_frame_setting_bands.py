"""Bands on MHA-FR-00's assembly settings, shared by the builder (which puts
them on the model dimensions) and the drawing (which reads them back).

Kept apart from fr_frame_attachment_spec so a band change re-keys only the
frame assembly and its sheet, not every part that reads the frame's stations.
"""

from __future__ import annotations

# Step 3's top cross-bore axis height (fr_frame_attachment_spec TOP_AXIS_*)
# prints three places on the .001 grid with the .XX-grade band it always had:
# the title block's .XXX would hold a 40 in setting to +/-.005 that no mate
# needs, since step 5 transfer-drills the tubes from the set position
# (machinist review of the PR C proof).
TOP_AXIS_HEIGHT_BAND_MM = 0.254  # +/-.010
