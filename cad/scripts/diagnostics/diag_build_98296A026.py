r"""McMaster 98296A026 -- 1050-1095 spring steel slotted spring pin, 1/16 x 9/16.

One of the 98296A* sizes built by the shared recipe in
``diag_mcmaster_spring_pin.py`` (see its docstring for the catalogue facts).
Historically used as transgear-collar-cross-pin (MHA-VN-037), now retired.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98296A026.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from _mcmaster_98296a026 import SPRING_PIN_SIZE, WALL_T  # noqa: E402
from diagnostics.diag_mcmaster_spring_pin import (  # noqa: E402
    build_spring_pin,
    spring_pin_bore,
    spring_pin_volume,
)

PART_NO = "98296A026"
PIN_OD, PIN_LEN = SPRING_PIN_SIZE
PIN_ID = spring_pin_bore(SPRING_PIN_SIZE, WALL_T)
V_PIN = spring_pin_volume(SPRING_PIN_SIZE, WALL_T)


async def build_98296A026(adapter, truth=None):
    await build_spring_pin(adapter, SPRING_PIN_SIZE, WALL_T)


if __name__ == "__main__":
    sys.exit(replica_main(PART_NO, build_98296A026))
