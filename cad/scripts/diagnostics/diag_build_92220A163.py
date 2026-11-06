r"""McMaster 92220A163 -- black-oxide alloy steel low-profile socket head screw, #10-24 x 1/2".

Catalogue: ``_mcmaster_92220a163`` (its docstring carries the live catalogue
reading of 2026-11-06 and the socket depth's source); every dimension is the
catalogue's, the socket depth the standard's minimum key engagement.

Geometry: the shared fully threaded socket-head recipe in
``diag_mcmaster_socket_head.py`` (see its docstring), at the page's low head:
the supplied screw, as MHA-CH-06-TL-VN-85 installs it.

No vendor model is downloaded or committed (catalogue-only, not
replica-gated: user ruling 2026-10-17 for this jig's hardware).  The
standalone run is catalog-only: it builds the supplied screw, checks the
solid is sane and saves it under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -length.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92220A163.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_92220a163 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    build_socket_head,
    build_socket_head_catalog,
)


@stock_recipe("92220A163", threaded=True)
async def build_92220A163(adapter, truth=None):
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
