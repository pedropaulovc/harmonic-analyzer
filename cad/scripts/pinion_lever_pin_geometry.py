r"""Geometry-only contract for the pinion lever retention pin (MHA-135).

U8 + U36: a 1/16 in solid steel pin driven through the MHA-059 lever hub and
the MHA-060 lift rod at mid-engagement, 3 o'clock to the grip, peened flush at
both ends.  The holes are match-drilled at assembly through both parts.
"""

from __future__ import annotations

from pinion_lever_geometry import HUB_OD, PIN_HOLE_DIA

PIN_DIA = PIN_HOLE_DIA  # 1/16 in drill rod, in its match-drilled hole
PIN_LEN = HUB_OD  # cut to the hub diameter; both ends peened flush
