r"""Build the rocker template trammel's pivot block (MHA-CH-006-TL-14; shop tooling).

A 1018 block that clamps on the trammel bar and holds the pivot point
(``ch_rocker_arm_tl_trammel_pivot_block_spec``), built by the recipe it
shares with the scriber block (``_trammel_block.build_block``).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_trammel_pivot_block.py
"""

from __future__ import annotations

import sys

import ch_rocker_arm_tl_trammel_pivot_block_spec as spec
from _session import run_build
from _trammel_block import build_block

PART_NAME = "ch-rocker-arm-tl-trammel-pivot-block"


async def build(adapter) -> dict[str, str]:
    return await build_block(adapter, spec, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
