r"""McMaster 91251A157 -- black-oxide alloy steel socket head screw, #6-32 x 1-1/2".

Catalogue: the McMaster product page https://www.mcmaster.com/91251A157/
(read live 2026-10 for the MHA-VN-024 knife-hanger screw): 6-32 UNC, class
3A, right hand, 1-1/2 in (38.1) under the head ("Length is measured from under
the head"), partially threaded with a 3/4 in (19.05) minimum thread length,
flat tip; socket head Ø0.226 in (5.7404) x 0.138 in (3.5052) high, 7/64 in
(2.7781) hex drive; black-oxide alloy steel, 170 ksi, Rockwell C37, ASTM
A574.  Class 3A is not modelled (nominal UN cutter); the major is the repo's
#6-32 thread major (``_hole_spec.THREAD_MAJOR_MM``).

The page gives no socket depth, so the socket takes ASME B18.3's minimum key
engagement for #6, 0.064 in (1.6256) -- the 91251A108 convention (B18.3
socket head cap screw table, T min).  The head is a plain cylinder: the page
gives no top chamfer or under-head fillet, and none is modelled.

Geometry: the shared socket-head recipe in ``diag_mcmaster_socket_head.py``,
partially threaded: the groove runs only over the minimum thread length from
the tip and the shank above it is plain at the major.  [UNVERIFIED-COM]: the
partial-thread split and runout have not been built on a seat yet.  No
91251A157 vendor model is downloaded or committed, so this size has no
replica gate of its own; its standalone run is catalog-only.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -38.1.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91251A157.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91251a157 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    build_socket_head,
    build_socket_head_catalog,
)


@stock_recipe("91251A157", threaded=True)
async def build_91251A157(adapter, truth=None):
    await build_socket_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await build_socket_head_catalog(adapter, DIMS)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
