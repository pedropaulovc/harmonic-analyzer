r"""McMaster 91882A425 -- knurled-head thumb screw.

One of the two 91882A* sizes built by the shared parametric recipe in
``diag_mcmaster_thumb.py`` (see its docstring for the vendor laws).

The official 91882A425.SLDPRT recipe was read-only harvested on 2026-09-08:
Sketch1 length 19.05, major diameter 6.35, pitch 1.27, collar 12.7 x 9.525,
head 25.4 x 6.35 mm. Its chamfer, thread and knurl laws match the shared recipe.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91882A425.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from diagnostics.diag_mcmaster_thumb import build_thumb_screw  # noqa: E402


async def build_91882A425(adapter, truth=None):
    await build_thumb_screw(adapter, "91882A425")


if __name__ == "__main__":
    sys.exit(replica_main("91882A425", build_91882A425))
