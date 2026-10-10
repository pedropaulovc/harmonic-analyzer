r"""McMaster 91251A108 -- black-oxide alloy steel socket head screw, #4-40 x 3/8".

Catalogue: the McMaster product page https://www.mcmaster.com/91251A108/
(read in a headless browser on 2026-09-29 for the MHA-VN-030 hold-down): #4-40
UNC, class 3A, right hand, 3/8 in (9.525) under the head, fully threaded,
flat tip; standard socket head Ø0.183 in (4.6482) x 0.112 in (2.8448) high,
3/32 in hex drive; black-oxide alloy steel, 170 ksi, Rockwell C37, ASTM
A574; screw size decimal 0.112 in (2.8448).  Class 3A is not modelled
(nominal UN cutter).

The page gives no socket depth, so the socket takes ASME B18.3's minimum key
engagement for #4, 0.055 in (1.397).  The head is a plain cylinder: the
page gives no top chamfer or under-head fillet, and none is modelled.

Geometry: the shared fully threaded socket-head recipe in
``diag_mcmaster_socket_head.py`` (see its docstring).  No 91251A108 vendor
model is downloaded or committed, so this size has no replica gate of its
own.  Its standalone run is catalog-only: it builds the recipe, checks the
solid is sane and saves it under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91251A108.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    SocketHeadScrew,
    build_socket_head,
    build_socket_head_catalog,
)

PART_NO = "91251A108"
IN = 25.4

DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.375 * IN,
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.055 * IN,
)


async def build_91251A108(adapter, truth=None):
    await build_socket_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await build_socket_head_catalog(adapter, DIMS)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
