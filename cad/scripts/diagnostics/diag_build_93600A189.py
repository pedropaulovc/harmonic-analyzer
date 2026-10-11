r"""McMaster 93600A189: catalogue-only nominal 316SS 2 x 6 dowel reference.

The supplier gives chamfered ends but no dimensions. The common recipe's
plain-cylinder branch is deliberate; it is not a vendor end-form replica.
Incoming measured end/length acceptance lives in the production pin spec.
Used as transgear-arm-plate-locating-pin (MHA-VN-054).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93600A189.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _mcmaster_93600a189 import DOWEL_SIZE, ENDS  # noqa: E402
from diagnostics.diag_mcmaster_dowel import build_catalog, build_dowel  # noqa: E402

PART_NO = "93600A189"


@stock_recipe("93600A189", threaded=False)
async def build_93600A189(adapter, truth=None):
    await build_dowel(adapter, PART_NO, DOWEL_SIZE, ENDS)


async def _catalog(adapter) -> dict[str, str]:
    return await build_catalog(adapter, PART_NO, DOWEL_SIZE, ENDS)


if __name__ == "__main__":
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build

    sys.exit(run_build(_catalog))
