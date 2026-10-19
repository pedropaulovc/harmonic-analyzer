r"""Purchased brass platen-clip screw (McMaster 92446A077) nominals.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the thread and the head/shank dims the platen's clip sockets, the clip
and the paper-drive assembly read. ``build_pd_vn_platen_clip_screw`` builds the
stock part from the same ``_mcmaster_92446a077`` row; consumers read it here so
the stock recipe does not ride their cache keys (#880).

A slotted PAN head (user ruling 2026-10-15): the 90114A124 fillister's
Ø0.124 in least head left 0.05 mm of bearing land over the clip's largest
drilled #2 loose hole; the pan head's least Ø0.155 in leaves 0.44.
"""

from __future__ import annotations

import _mcmaster_92446a077 as _catalogue

SKU = _catalogue.PART_NO
THREAD = _catalogue.THREAD
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH = _catalogue.PAN_HEAD_SIZE
# ASME B18.6.3 #2 slotted pan head table (Olander 2C25SPMBP, cross-referenced
# to 92446A077, read 2026-10-15): least head Ø0.155 in. The bearing land over
# the clip's hole uses it.
HEAD_DIA_MIN = _catalogue.HEAD_DIA_MIN
