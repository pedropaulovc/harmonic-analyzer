"""Bands on MHA-FR-00's assembly settings, shared by the builder (which puts
them on the model dimensions) and the drawing (which reads them back).

Kept apart from fr_frame_attachment_spec so a band change re-keys only the
frame assembly and its sheet, not every part that reads the frame's stations.
"""

from __future__ import annotations

# The top cross-bore axis height (fr_frame_attachment_spec TOP_AXIS_*) prints
# three places on the .001 grid with a band a tape measure reads (#2389).
# No mate needs it closer: the tubes are transfer-drilled from the set
# position, and the only base-to-top-frame links, the 20 MHA-CH-01 bars, are
# common to every channel, so a height error turns all 20 levers alike (.030
# over the 5.00 bar pin radius is 0.34 deg) and MHA-HA-00's summing levelling
# takes it out. The original frame (ch30 eight-views, a cross screw per
# corner boss) shows no finer height control.
TOP_AXIS_HEIGHT_BAND_MM = 0.762  # +/-.030
