r"""McMaster 91290A168 -- black-oxide alloy steel socket head screw, M4 x 0.7 x 20 mm.

Catalogue: ``_mcmaster_91290a168`` (its docstring carries the live catalogue reading of
2026-10-17 and the socket depth's source); every dimension is the catalogue's,
the socket depth the standard's minimum key engagement.

Geometry: the shared fully threaded socket-head recipe in
``diag_mcmaster_socket_head.py`` (see its docstring).

The product page's vendor model (SLDPRT SHA-256
``d95f5c3556da2eb440809a63d8e4511e9bf35dba2e57dafa8c55c9c5bc2a1e10``, and its STEP) was
downloaded on 2026-10-17 and read for dimensions only: it is NOT
replica-gated (user ruling 2026-10-17) and no copy is kept in the repo.  The
standalone run is catalog-only: it builds the recipe, checks the solid is
sane and saves it under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -length.

Cut to fit (optional ``cut_length``; MHA-CH-06-TL-VN-64, owner ruling
2026-11-01): a screw cut at assembly is drawn as installed, the same recipe
at the cut length under the head, its 0.75P tip chamfer standing for the
broken cut end.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91290A168.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91290a168 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_socket_head import (  # noqa: E402
    build_socket_head,
    build_socket_head_catalog,
)


@stock_recipe("91290A168", threaded=True)
async def build_91290A168(adapter, truth=None, cut_length: float | None = None):
    if cut_length is None:
        await build_socket_head(adapter, DIMS)
        return
    if not 0.0 < cut_length < DIMS.length:
        raise ValueError(
            f"91290A168: a {cut_length} mm cut is not inside the {DIMS.length} mm screw"
        )
    await build_socket_head(adapter, replace(DIMS, length=cut_length))


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
