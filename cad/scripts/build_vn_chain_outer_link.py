r"""Reproduction script: roller-chain OUTER link (book ch. 23/30).

Two outer side-plates (obround, one LINK_PITCH long) plus two solid pins at
the pin stations -- the outer half of the drive chain. Each pin floats through
the neighbouring inner link's bushing bore (0.35 clearance) at the shared
joints; the outer links alternate with the inner links
(build_vn_chain_inner_link.py) along the centreline loop via the two-group
Connected-Linkage chain component pattern in build_pd_paper_drive_assembly.py;
the loop's closing outer link is the separate connecting link
(build_vn_chain_connecting_link.py).
Geometry and clearances: _chain.py / _chain_link.py.

Installed geometry is a clearance stand-in. The isolated Supplier-Free state
is source-derived stock identification, not a replacement for the installed
solid, its original configurations or the two chain path axes.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_vn_chain_outer_link.py
"""

from __future__ import annotations

import sys

from _chain_link import OUTER_LINK, build_link
from _session import run_build
from _supplier_chain_stock import add_chain_stock_references

PART_NAME = "vn-chain-outer-link"
MATERIAL = "Plain Carbon Steel"


async def build(adapter) -> dict[str, str]:
    return await build_link(
        adapter,
        part_name=PART_NAME,
        material=MATERIAL,
        **OUTER_LINK,
        before_save=add_chain_stock_references,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
