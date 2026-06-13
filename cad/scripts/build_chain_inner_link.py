r"""Reproduction script: roller-chain INNER link (book ch. 23/30).

Two inner side-plates (obround, one LINK_PITCH long) plus two bored bushings
at the pin stations -- the inner half of the drive chain that loops the two
mounted removable gears (T12 crank shaft -> T24 knob shaft). The outer links
(build_chain_outer_link.py) alternate with these along the centreline loop via
the two-group Connected-Linkage chain component pattern in
build_output_assembly.py. Geometry and clearances: _chain.py / _chain_link.py.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_chain_inner_link.py
"""

from __future__ import annotations

import sys

from _chain_link import INNER_LINK, build_link
from _common import run_build

PART_NAME = "chain-inner-link"
MATERIAL = "Plain Carbon Steel"


async def build(adapter) -> dict[str, str]:
    return await build_link(
        adapter, part_name=PART_NAME, material=MATERIAL, **INNER_LINK
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
