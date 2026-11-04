r"""McMaster 91255A150 -- black-oxide alloy steel button head SHCS, #6-32 x 5/8".

Catalogue: https://www.mcmaster.com/91255A150/ (read live 2026-11-04):
#6-32 UNC, class 3A, 5/8 in (15.875) under the head, fully threaded;
button head Ø0.262 in (6.6548) x 0.073 in (1.8542) high, 5/64 in hex drive;
black-oxide alloy steel, 140,000 psi, Rockwell C39, ASME B18.3 and ASTM F835.
Class 3A is not modelled (nominal UN cutter).

The head and drive are those of 91255A148, the 1/2 in length of the same
series, whose laws were measured from its vendor model and replica-gated
(``diag_build_91255A148.py``); ``_button_head_dimensions`` carries them, so
this length needs no law of its own. Only the length differs.

No 91255A150 vendor model is downloaded or committed, so this size has no
replica gate of its own; the native build is checked by the farm leaf. Its
standalone run is catalog-only: it builds the recipe, checks the solid is sane
and saves it under cad/out/reference for inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91255A150.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_91255a150 import DIMS  # noqa: E402
from diagnostics.diag_mcmaster_button_head import (  # noqa: E402
    build_button_head,
    catalog_run,
)


@stock_recipe("91255A150", threaded=True)
async def build_91255A150(adapter, truth=None):
    await build_button_head(adapter, DIMS)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await catalog_run(adapter, DIMS, build_91255A150)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
