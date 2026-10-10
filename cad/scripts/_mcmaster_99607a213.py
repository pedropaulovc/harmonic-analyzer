"""Pure McMaster 99607A213 dimensions shared by recipe and assembly placement.

Separate from the COM recipe and part-save wrapper to limit cache blast radius.
"""

from __future__ import annotations

TS_MAJOR_R = 2.8448 / 2.0
TS_PITCH = 0.635
TS_LEN = 15.875
TS_SH_R = 5.953125 / 2.0
TS_SH_H = 3.175
TS_HEAD_R = 7.540625 / 2.0
TS_HEAD_H = 3.175


HEAD_DIA = 2.0 * TS_HEAD_R
HEAD_H = TS_HEAD_H
HEAD_STACK_LEN = TS_SH_H + TS_HEAD_H
SHANK_DIA = 2.0 * TS_MAJOR_R
SHANK_LEN = TS_LEN
TIP_CHAMFER = TS_PITCH * 0.75
