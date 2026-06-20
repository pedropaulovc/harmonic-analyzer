r"""Reproduction script: roller-chain OUTER link (book ch. 23/30).

Two outer side-plates (obround, one LINK_PITCH long) plus two solid pins at
the pin stations -- the outer half of the drive chain. Each pin floats through
the neighbouring inner link's bushing bore (0.35 clearance) at the shared
joints; the outer links alternate with the inner links
(build_chain_inner_link.py) along the centreline loop via the two-group
Connected-Linkage chain component pattern in build_paper_drive_assembly.py.
Geometry and clearances: _chain.py / _chain_link.py.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_chain_outer_link.py
"""

from __future__ import annotations

import sys

from _chain_link import OUTER_LINK, build_link
from _common import run_build

PART_NAME = "chain-outer-link"
MATERIAL = "Plain Carbon Steel"


async def build(adapter) -> dict[str, str]:
    return await build_link(
        adapter, part_name=PART_NAME, material=MATERIAL, **OUTER_LINK
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
