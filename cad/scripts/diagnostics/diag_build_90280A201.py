r"""McMaster 90280A201 -- steel narrow fillister head slotted screw.

One of the five 90280A* sizes built by the shared parametric recipe in
``diag_mcmaster_fillister.py`` (see its docstring for the vendor laws).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90280A201.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diag_mcmaster_fillister import build_fillister  # noqa: E402
from diag_mcmaster_lib import replica_main  # noqa: E402


async def build_90280A201(adapter, truth):
    await build_fillister(adapter, "90280A201")


if __name__ == "__main__":
    sys.exit(replica_main("90280A201", build_90280A201))
