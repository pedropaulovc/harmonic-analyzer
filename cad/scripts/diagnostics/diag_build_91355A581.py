r"""McMaster 91355A581 -- black-oxide alloy steel flanged button head screw, #4-40 x 3/4".

Catalogue: ``_mcmaster_91355a581`` (its docstring carries the live product
page reading of 2026-11-02 and the vendor STEP measurements): #4-40 x 3/4,
button head Ø0.193 x 0.059 in with a Ø0.234 x 0.024 in flange, 1/16 in hex.

Geometry: the shared button head recipe in ``diag_mcmaster_button_head.py``
(the 91255A148 laws for the dome, socket and thread), its flanged branch:
the dome stands on a square-edged flange.  The vendor STEP was measured,
not committed, so this size has no replica gate.  The standalone run is
catalog-only: it builds the recipe, checks the solid is sane and saves it
under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (flange underside) at y = 0, tip at
y = -length.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91355A581.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91355a581 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_button_head import (  # noqa: E402
    build_button_head,
    catalog_run,
)


@stock_recipe("91355A581", threaded=True)
async def build_91355A581(adapter, truth=None):
    await build_button_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await catalog_run(adapter, DIMS, build_91355A581)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
