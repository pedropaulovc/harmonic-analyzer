"""Build the swing-stop screw from shared McMaster 90280A199 stock."""

from __future__ import annotations

import sys

from _common import run_build
import _config
from _holes import HoleSpec
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from diagnostics.diag_build_90280A199 import build_90280A199
from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

PART_NAME = "swing-stop-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material

THREAD = "#8-32"
SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, THREAD_PITCH = FILLISTER_SIZES["90280A199"]
EMBED_LEN = 15.525
PROUD_LEN = SHANK_LEN - EMBED_LEN
TIP_CHAMFER = 0.7 * THREAD_PITCH
UNDERHEAD_FILLET = THREAD_PITCH / 10.0
PLATE_THICKNESS_ALLOWANCE = 25.4 * float(_config.title_block("linear_2pl")["value_in"])


def require_seat_fit(seat: HoleSpec, plate_thickness: float) -> None:
    """Keep the stock stop clear of the moving plate without starving its tap."""
    if seat.kind != "tapped" or seat.size != THREAD or seat.end != "blind":
        raise AssertionError("swing stop requires a blind #8-32 tapped seat")
    if EMBED_LEN - TIP_CHAMFER < SHANK_DIA:
        raise AssertionError("swing stop has less than 1D useful thread engagement")
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if thread_depth - EMBED_LEN < 0.25 - 1e-9:
        raise AssertionError("swing stop bottoms in its threaded seat")
    if seat.depth_mm - thread_depth < 5.0 * THREAD_PITCH - 1e-9:
        raise AssertionError("swing-stop drill lacks five-pitch plug-tap lead")
    # Include the plate's two-place drawing allowance and the vendor's
    # underside fillet, not only the nominal flat head plane.
    if PROUD_LEN - plate_thickness - PLATE_THICKNESS_ALLOWANCE - UNDERHEAD_FILLET < 1.0:
        raise AssertionError("swing-stop head crowds the tolerance-high platform")


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                "90280A199",
                build_90280A199,
                RigidTransform(translation_mm=(0.0, PROUD_LEN, 0.0)),
            ),
        ),
        material=MATERIAL,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
