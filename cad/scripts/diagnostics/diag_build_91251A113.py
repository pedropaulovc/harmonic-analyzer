r"""McMaster 91251A113 -- black-oxide alloy steel socket head screw, #4-40 x 3/4".

Catalogue: ``_mcmaster_91251a113`` (its docstring carries the live listing
reading of 2026-11-01 and the socket depth's source); every dimension is the
catalogue's, the socket depth the standard's minimum key engagement.

Geometry: the shared fully threaded socket-head recipe in
``diag_mcmaster_socket_head.py`` (see its docstring).  No vendor model is
downloaded or committed (the product page is login-walled), so this size has
no replica gate.  The standalone run is catalog-only: it builds the recipe,
checks the solid is sane and saves it under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -length.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91251A113.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91251a113 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    build_socket_head,
    build_socket_head_catalog,
)


@stock_recipe("91251A113", threaded=True)
async def build_91251A113(adapter, truth=None):
    await build_socket_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await build_socket_head_catalog(adapter, DIMS)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
