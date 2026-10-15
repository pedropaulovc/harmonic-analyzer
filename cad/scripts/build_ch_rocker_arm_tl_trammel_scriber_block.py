r"""Build the rocker template trammel's scriber block (MHA-CH-006-TL-15; shop tooling).

The pivot block's recipe (``_trammel_block.build_block``) with the scriber
block's spec (``ch_rocker_arm_tl_trammel_scriber_block_spec``):
two point holes 16.000 apart, the longer slit and two pinch screws.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_trammel_scriber_block.py
"""

from __future__ import annotations

import sys

import ch_rocker_arm_tl_trammel_scriber_block_spec as spec
from _session import run_build
from _trammel_block import build_block

PART_NAME = "ch-rocker-arm-tl-trammel-scriber-block"


async def build(adapter) -> dict[str, str]:
    return await build_block(adapter, spec, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
