r"""Reproduction script: roller-chain CONNECTING link (book ch. 23/30).

The one clip-retained outer link (McMaster 6261K108) that joins the cut
chain's two inner-link ends into the closed loop. It is modelled as the
outer-link stand-in (_chain_link.CONNECTING_LINK): two outer side-plates plus
two solid pins, without the vendor's spring clip. The assembly
(build_pd_paper_drive_assembly.py) seats it at the loop's closing station,
after the connected-linkage chain pattern of inner and outer links.
Geometry and clearances: _chain.py / _chain_link.py.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_vn_chain_connecting_link.py
"""

from __future__ import annotations

import sys

from _chain_link import CONNECTING_LINK, build_link
from _session import run_build
from _supplier_chain_stock import add_chain_stock_references

PART_NAME = "pd-vn-chain-connecting-link"
MATERIAL = "Plain Carbon Steel"


async def _add_supplier_references(adapter) -> None:
    await add_chain_stock_references(adapter, connecting=True)


async def build(adapter) -> dict[str, str]:
    return await build_link(
        adapter, part_name=PART_NAME, material=MATERIAL,
        before_save=_add_supplier_references, **CONNECTING_LINK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
