r"""McMaster 91375A106 -- alloy steel cup-tip set screw, #4-40 x 1/4 (MHA-147).

Not a reverse-engineered replica: the builder is the production part's own
ASME B18.3 nominal geometry (``build_arbor_set_screw.author_set_screw``), so
running it through the replica fleet's vendor gates measures how far the
shipped model sits from the vendor file (#743 release blocker). The gates are
expected to fail on the thread and cup detail; the report's volume, surface,
COM and face-area deltas are the evidence either way.

Needs the local-only vendor file and its harvest (``diag_dump_part.py``);
see ``diag_build_mcmaster.py``.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91375A106.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from build_arbor_set_screw import author_set_screw  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


async def build_91375A106(adapter, truth=None) -> None:
    await author_set_screw(adapter, truth)


if __name__ == "__main__":
    sys.exit(replica_main("91375A106", build_91375A106))
