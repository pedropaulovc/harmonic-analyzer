r"""McMaster 98296A027 -- 1050-1095 spring steel slotted spring pin, 1/16 x 1/2.

One of the 98296A* sizes built by the shared recipe in
``diag_mcmaster_spring_pin.py`` (see its docstring for the catalogue facts).
Used as pinion-strap-pin (MHA-145).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98296A027.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from diagnostics.diag_mcmaster_spring_pin import (  # noqa: E402
    SPRING_PIN_SIZES,
    build_spring_pin,
    spring_pin_bore,
    spring_pin_volume,
)

PART_NO = "98296A027"
PIN_OD, PIN_LEN = SPRING_PIN_SIZES[PART_NO]
PIN_ID = spring_pin_bore(PART_NO)
V_PIN = spring_pin_volume(PART_NO)


async def build_98296A027(adapter, truth=None):
    await build_spring_pin(adapter, PART_NO)


if __name__ == "__main__":
    sys.exit(replica_main(PART_NO, build_98296A027))
