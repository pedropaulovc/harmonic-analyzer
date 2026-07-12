r"""Reproduction script: transgear-bracket screw (book ch. 23, p. 62-63; 2 used).

One of the two large slotted screws fastening the transgear bracket to the
BACK of the platen support bar (visible in the p.62 top-down and p.63 back
views): head on the bracket's back face, shank through the bracket plate (4)
into the bar's O4.0 back-face sockets. Plain cylindrical head; slot and
thread not modeled (documented simplification, same as fillister-screw).

Layout: axis along Z, authored pointing +Z (the assembly flips it to point
machine -Z, into the bar): under-head face on the Front plane at z = 0,
head -2.5..0, shank 0..+12.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_bracket_screw.py
"""

from __future__ import annotations

import sys

from _fastener_catalog import fastener
from _flat_screw import build_flat_screw
from _common import run_build

PART_NAME = "bracket-screw"
SPEC = fastener(PART_NAME)

HEAD_DIA = 8.0  # large slotted head (p.62/63, low)
HEAD_H = 2.5
SHANK_DIA = SPEC.model_diameter_mm  # #8-32 modeled thread minor diameter
# (threads the bar's #8-32 sockets; rides the bracket's O4.4 clearance)
SHANK_LEN = SPEC.length_mm  # bracket plate 4 + 8 into the 9-deep bar


async def build(adapter) -> dict[str, str]:
    return await build_flat_screw(
        adapter,
        part_name=PART_NAME,
        material=SPEC.material,
        head_dia=HEAD_DIA,
        head_h=HEAD_H,
        shank_dia=SHANK_DIA,
        shank_len=SHANK_LEN,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
