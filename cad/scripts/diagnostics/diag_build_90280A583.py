r"""McMaster 90280A583 -- zinc-plated steel 5/16-18 x 1 fillister screw.

Catalog sizes were read live on 2026-10-10. Reuses the native fillister
family laws; derived slot, dome, thread/runout and vendor-frame mapping are
family assumptions, not verified vendor geometry. The supplied model is
stored locally as ``cad/references/mcmaster/90280A583.SLDPRT``. Its native
comparison is PENDING -- requires SolidWorks.
The pure stock specification owns the dimensions.

After read-only source harvest with ``diag_dump_part.py``, compare natively
(SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90280A583.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from vn_gooseneck_spring_screw_spec import SKU  # noqa: E402


async def build_90280A583(adapter, truth=None):
    await build_fillister(adapter, SKU)


if __name__ == "__main__":
    sys.exit(replica_main(SKU, build_90280A583))
