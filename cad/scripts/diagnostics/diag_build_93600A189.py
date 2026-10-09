"""McMaster 93600A189: catalogue-only nominal 316SS 2 x 6 dowel reference.

The supplier gives chamfered ends but no dimensions. The common recipe's
plain-cylinder branch is deliberate; it is not a vendor end-form replica.
Incoming measured end/length acceptance lives in the production pin spec.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnostics.diag_mcmaster_dowel import build_catalog as _build_catalog, build_dowel

PART_NO = "93600A189"


async def build_93600A189(adapter, truth=None) -> None:
    await build_dowel(adapter, PART_NO)


async def build_catalog(adapter) -> dict[str, str]:
    return await _build_catalog(adapter, PART_NO)


if __name__ == "__main__":
    from _common import run_build
    sys.exit(run_build(build_catalog))
