r"""McMaster 3088A086 -- carbon-steel ring shim, 12 mm ID x 18 mm OD x 1 mm.

One thickness of the MHA-VN-071 crank seat shim pack (``vn-crank-seat-shim``).
The model and its catalogue-only status are
``diagnostics.diag_shim_3088a_12x18``'s.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_3088A086.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from diagnostics.diag_shim_3088a_12x18 import author_shim, build_catalog  # noqa: E402

PART_NO = "3088A086"


@stock_recipe("3088A086", threaded=False)
async def build_3088A086(adapter, truth=None, *, stacked_volume_mm3: float = 0.0):
    await author_shim(adapter, PART_NO, stacked_volume_mm3)


if __name__ == "__main__":
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(lambda adapter: build_catalog(adapter, PART_NO, build_3088A086)))
