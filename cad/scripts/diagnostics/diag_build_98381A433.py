r"""McMaster 98381A433 -- alloy steel dowel pin, 3/32" diameter, 3/16" long.

One of the 98381A* sizes built by the shared recipe in
``diag_mcmaster_dowel.py`` (see its docstring for the catalogue facts).
Used as transgear-knob-drive-pin (MHA-155).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98381A433.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_dowel import build_catalog, build_dowel  # noqa: E402

PART_NO = "98381A433"


async def build_98381A433(adapter, truth=None):
    await build_dowel(adapter, PART_NO)


async def _catalog(adapter) -> dict[str, str]:
    return await build_catalog(adapter, PART_NO)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(_catalog))
