r"""McMaster 91790A199 -- 18-8 stainless steel slotted82deg oval head screw,
8-32 x1in from the top of the bevel, fully threaded.

The chosen SKU was read live at https://www.mcmaster.com/91790A199/ on
2026-10-09; ``vn_transgear_arm_plate_screw_spec`` owns catalogue dimensions
and published standard bounds, not a commodity receiving procedure.

Built by the shared 91790A oval recipe in ``diag_mcmaster_oval.py`` (see its
docstring for the live-page facts and the [INFERENCE] head, slot and thread
laws).  Without arguments it builds the supplied screw; ``cut_length`` with
``cut_end_break`` draws it cut to fit, as the MHA-VN-040 part installs it.  No
vendor SLDPRT is downloaded or committed, so the standalone run is
catalog-only (the supplied screw).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91790A199.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_oval import build_oval, catalog_run  # noqa: E402

PART_NO = "91790A199"


async def build_91790A199(
    adapter,
    truth=None,
    *,
    cut_length: float | None = None,
    cut_end_break: float | None = None,
):
    await build_oval(
        adapter, PART_NO, cut_length=cut_length, cut_end_break=cut_end_break
    )


async def build_catalog(adapter) -> dict[str, str]:
    return await catalog_run(adapter, PART_NO, build_91790A199)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
