r"""Reproduction script: column-clamp screw (book ch. 21/22, ch30; 6 used:
4 on the platen support bar, 2 on the magnifying wheel-bar).

The long slotted machine screw closing each two-piece column clamp: 2 per
clamp, heads on the bar's FRONT face flanking the column (ch30 p002),
shank through the bar (9) and the front arc (17.9), threading into
the back arc (O4.0 ear holes). Plain cylindrical head; slot and thread not
modeled (documented simplification, same as fillister-screw).

Layout: axis along Z, authored in final orientation (pointing machine +Z):
under-head face on the Front plane at z = 0, head -2.5..0, shank 0..+28.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_clamp_screw.py
"""

from __future__ import annotations

import sys

from _flat_screw import build_flat_screw
from _common import run_build

PART_NAME = "clamp-screw"

HEAD_DIA = 8.0  # large slotted head on the bar front (ch30 p002, low)
HEAD_H = 2.5
SHANK_DIA = 3.15  # shank: was Ø3.9, now 3.15 = #8-32 tap-drill 3.454 - 0.3
# (threads the back-arc #8-32 tap; rides the O4.4 bar/front-arc clearance)
SHANK_LEN = 28.0  # bar 9 + front arc 17.9 + 1.1 into the back arc


async def build(adapter) -> dict[str, str]:
    return await build_flat_screw(
        adapter,
        part_name=PART_NAME,
        material="Plain Carbon Steel",
        head_dia=HEAD_DIA,
        head_h=HEAD_H,
        shank_dia=SHANK_DIA,
        shank_len=SHANK_LEN,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
