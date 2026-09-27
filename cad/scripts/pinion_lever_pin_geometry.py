r"""Geometry-only contract for the pinion lever retention pin (MHA-135).

U8 + U36: a 1/16 in solid steel pin driven through the MHA-059 lever hub and
the MHA-060 lift rod at mid-engagement, 3 o'clock to the grip, trimmed and
peened flush at both ends.  The holes are match-drilled at assembly through
both parts.
"""

from __future__ import annotations

from pinion_lever_geometry import HUB_OD, PIN_HOLE_DIA

PIN_DIA = PIN_HOLE_DIA  # 1/16 in drill rod, in its match-drilled hole
# Codex P1 (#844): cut OVERLENGTH, then trimmed and peened flush at assembly.
# A pin cut to the hub's 13.0 at .X could be 12.2 in a 13.8 hub -- 0.8 short
# of each face with nothing left to peen.  Both lengths print at .X (+/-0.8),
# so the shortest pin still stands PEEN_ALLOWANCE proud of each face of the
# largest hub.
HUB_OD_BAND = 0.8  # MHA-059 HubOd prints .X
PIN_LEN_BAND = 0.8  # the cut length prints .X
PEEN_ALLOWANCE = 0.5  # minimum stock proud of each hub face, per end
PIN_LEN = 16.0
if PIN_LEN - PIN_LEN_BAND < HUB_OD + HUB_OD_BAND + 2.0 * PEEN_ALLOWANCE:
    raise AssertionError("shortest pin cannot be peened flush on the largest hub")

# Installed state (Codex #858 P2): the drive train shows the pin as assembly
# leaves it, trimmed and peened flush with the hub at both ends.  The part
# carries that as a second configuration; the manufactured overlength default
# stays the one the drawing prints.
INSTALLED_CONFIG = "INSTALLED"
INSTALLED_LEN = HUB_OD
