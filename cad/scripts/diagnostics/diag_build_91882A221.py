r"""McMaster 91882A221 -- knurled-head thumb screw.

One of the two 91882A* sizes built by the shared parametric recipe in
``diag_mcmaster_thumb.py`` (see its docstring for the vendor laws).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91882A221.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diag_mcmaster_lib import replica_main  # noqa: E402
from diag_mcmaster_thumb import build_thumb_screw  # noqa: E402


async def build_91882A221(adapter, truth):
    await build_thumb_screw(adapter, "91882A221")


if __name__ == "__main__":
    sys.exit(replica_main("91882A221", build_91882A221))
