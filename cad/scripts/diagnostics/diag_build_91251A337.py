r"""McMaster 91251A337 -- black-oxide alloy steel socket head screw, 10-32 x 5/16".

Used as dt-cylinder-gear-tl-vn-cam-clamp-screw (MHA-DT-12-TL-VN-52).
Catalogue: ``_mcmaster_91251a337`` (its docstring carries the live catalogue
reading of 2026-11-12 and the socket depth's source).

Geometry: the shared fully threaded socket-head recipe in
``diag_mcmaster_socket_head.py`` (see its docstring). No vendor model was
downloaded: the standalone run is catalog-only, building the recipe,
checking the solid and saving it under cad/out/reference.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -length.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91251A337.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91251a337 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    build_socket_head,
    build_socket_head_catalog,
)


@stock_recipe("91251A337", threaded=True)
async def build_91251A337(adapter, truth=None):
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
