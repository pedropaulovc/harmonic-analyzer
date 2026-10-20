r"""McMaster 91771A112 -- 18-8 stainless steel Phillips flat head screw, 82 deg, #4-40 x 5/8".

Catalogue first: ``_mcmaster_91771a112`` (its docstring carries the live
catalogue reading of 2026-10-19); the Phillips recess form and the tip
chamfer, which the catalogue does not state, are the same-family reading of
the 91771A110 vendor model, labelled so there.  Geometry: the Phillips flat
head recipe ``diag_mcmaster_phillips_flat_head.build_phillips_flat_head`` on
``_mcmaster_91771a112.DIMS``, its thread swept by
``diag_mcmaster_lib.thread_sweep_cut_modern`` on the single shank body.

No vendor model of this SKU was downloaded; the recipe is NOT replica-gated
(user ruling 2026-10-17) and no vendor file is kept in the repo.  The
standalone run is catalog-only: it builds the recipe, checks the solid is
sane and saves it under cad/out/reference for inspection.

Frame: axis +Y (Front ∩ Right), head up, the flat top on the Top Plane, the
tip at y = -length (McMaster's length is overall).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91771A112.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91771a112 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_phillips_flat_head import (  # noqa: E402
    build_phillips_flat_head,
    build_phillips_flat_head_catalog,
)


@stock_recipe("91771A112", threaded=True)
async def build_91771A112(adapter, truth=None):
    await build_phillips_flat_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await build_phillips_flat_head_catalog(adapter, DIMS)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
