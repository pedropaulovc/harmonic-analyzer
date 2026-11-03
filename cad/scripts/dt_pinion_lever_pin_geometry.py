r"""Geometry-only contract for the pinion lever retention pin (MHA-DT-30).

U8 + U36: a 1/16 in solid steel pin inserted through the MHA-DT-16 lever hub
and the MHA-DT-17 lift rod at mid-engagement, 3 o'clock to the grip, trimmed
and peened flush at both ends.  The holes are match-drilled at assembly through
both parts; the pin slips into them and its peened heads retain it (#1064).
"""

from __future__ import annotations

import _config
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from dt_pinion_lever_geometry import HUB_OD
from dt_pinion_lever_geometry import UNIT as LEVER_UNIT

UNIT = drawing_unit("parts/dt-pinion-lever-pin", _config.parts("dt-pinion-lever-pin"))
# 1/16 in drill rod as supplied (vendor size), in the hub's match-drilled hole
# (dt_pinion_lever_geometry.PIN_HOLE_DIA).
PIN_DIA = 25.4 / 16.0
# Codex P1 (#844): cut OVERLENGTH, then trimmed and peened flush at assembly.
# A pin cut to the hub's own length could be short of each face with nothing
# left to peen.  Both lengths print at .XX, so the shortest pin still stands
# PEEN_ALLOWANCE proud of each face of the largest hub.
HUB_OD_BAND = printed_band_mm(2, unit=LEVER_UNIT)  # MHA-DT-16 HubOd prints .XX
PIN_LEN_BAND = printed_band_mm(2, unit=UNIT)  # the cut length prints .XX
PEEN_ALLOWANCE = 0.5  # minimum stock proud of each hub face, per end
PIN_LEN = 16.002  # .63
if PIN_LEN - PIN_LEN_BAND < HUB_OD + HUB_OD_BAND + 2.0 * PEEN_ALLOWANCE:
    raise AssertionError("shortest pin cannot be peened flush on the largest hub")

# Installed state (Codex #858 P2): the drive train shows the pin as assembly
# leaves it, trimmed and peened flush with the hub at both ends.  The part
# carries that as a second configuration; the manufactured overlength default
# stays the one the drawing prints.
INSTALLED_CONFIG = "INSTALLED"
INSTALLED_LEN = HUB_OD
