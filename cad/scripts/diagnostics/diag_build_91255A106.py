r"""McMaster 91255A106 -- black-oxide alloy steel button head SHCS, #4-40 x 1/4".

Catalogue: the McMaster product page https://www.mcmaster.com/91255A106/
(read in a headless browser on 2026-09-30 for the guide-lock screws, ruling
R9-31): #4-40 UNC, class 3A, right hand, 1/4 in (6.35) under the head, fully
threaded, flat tip; standard-profile button head Ø0.213 in (5.4102) x 0.059 in
(1.4986) high, 1/16 in hex drive; black-oxide alloy steel, 140 ksi, Rockwell
C39, ASME B18.3 and ASTM F835; screw size decimal 0.112 in (2.8448).  Class 3A
is not modelled (nominal UN cutter).

The page gives the thread, length, head Ø and height and the hex size, and
nothing else.  Every other value is the 91255A148 button-head law
(``diag_build_91255A148.py``, measured from its vendor model and
replica-gated) carried over in proportion [INFERENCE]: the flat top is 7/5 of
the hex across flats (7/64 over 5/64 there); the band is 0.15 of the head
height at 10 deg; both band edges take an R 0.05 x head height fillet; the
socket floor is 0.55 of the head height below the flat top; a 60 deg
countersink from the hex's corner circle breaks the corners.  The dome is the
sphere through the flat top's edge and the head OD at the band's top.

Shank and thread: the 91251A108 laws -- 45 deg x 0.75P tip chamfer, the body
split at the bearing face so the sweep scopes to the shank, a tip-seeded
right-hand helix L + P high, the symmetric UN cutter 7P/16 past the tip, and a
45 deg neck cone from major + H/4 that re-merges the bodies.

No 91255A106 vendor model is downloaded or committed, so this size has no
replica gate of its own; the native build is checked by the farm leaf.  Its
standalone run is catalog-only: it builds the recipe, checks the solid is sane
and saves it under cad/out/reference for inspection.

``build_button_head`` and ``catalog_run`` take the ``ButtonHeadScrew``
dimensions, so another length of the series reuses this recipe unchanged
(``diag_build_91255A108.py``, the 3/8 in screw MHA-VN-046 takes since R9-48).

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91255A106.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91255a106 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_button_head import (  # noqa: E402
    build_button_head,
    catalog_run,
)


@stock_recipe("91255A106", threaded=True)
async def build_91255A106(adapter, truth=None):
    await build_button_head(adapter, DIMS)




async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await catalog_run(adapter, DIMS, build_91255A106)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
