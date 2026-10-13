r"""Purchased brass platen-clip screw (McMaster 90114A124) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread and the head/shank dims the platen's clip sockets, the clip
and the paper-drive assembly read. ``build_vn_platen_clip_screw`` builds the
stock part from the same ``_mcmaster_90114a124`` row; consumers read it here so
the stock recipe does not ride their cache keys (#880).
"""

from __future__ import annotations

from _mcmaster_90114a124 import FILLISTER_SIZE

SKU = "90114A124"
THREAD = "#2-56"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH = FILLISTER_SIZE
