r"""Shared recipe for the McMaster 98381A* alloy-steel dowel pins.

Catalogue: each size's own McMaster product page, read live 2026-09-30 in a
headless browser (dt-logs transgear-evidence/mcmaster-skus.md R6): alloy
steel, unplated, diameter +0.0001 to +0.0003 in over nominal, end shape
"Round x Chamfer".  The pages state neither the end radius nor the chamfer,
so the recipe models the plain nominal cylinder (the
``diag_build_98296A027`` convention for unstated end forms) rather than
inventing either.

No vendor .SLDPRT is downloaded or committed, so the family has no replica
gate; each size's standalone run (``diag_build_98381A*.py``) is catalog-only:
it builds the recipe, checks the solid and saves it under cad/out/reference.

Frame: the pin section revolved about model Y, the pressed (chamfered) end
face at y = 0 and the rounded lead end at y = length.

The size table is pure data: module import pulls in no SolidWorks helper,
so the pin specs read it.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MM_PER_IN = 25.4

DOWEL_SIZES = {
    # part:        (nominal dia, length), mm
    "98381A433": (3.0 / 32.0 * MM_PER_IN, 3.0 / 16.0 * MM_PER_IN),  # 3/32 x 3/16
    "98381A434": (3.0 / 32.0 * MM_PER_IN, 0.25 * MM_PER_IN),  # 3/32 x 1/4
}
# Catalogue diameter tolerance over nominal, in inches (every size above).
DIA_BAND_IN = (0.0001, 0.0003)


def dowel_volume(part_no: str) -> float:
    dia, length = DOWEL_SIZES[part_no]
    return math.pi * (dia / 2.0) ** 2 * length


async def build_dowel(adapter, part_no: str) -> None:
    from _common import add_line_chain, check, name_last_feature, volume_check
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    dia, length = DOWEL_SIZES[part_no]
    radius = dia / 2.0
    check("create_sketch pin section", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, length / 1000.0, 0.0) is None:
            raise RuntimeError(f"{part_no} pin section: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [(0.0, 0.0), (radius, 0.0), (radius, length), (0.0, length)],
        )
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "PinBody")
    volume = dowel_volume(part_no)
    await volume_check(adapter, "dowel pin", volume, 0.005 * volume)


async def build_catalog(adapter, part_no: str) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    from _common import check
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await build_dowel(adapter, part_no)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{part_no} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{part_no}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{part_no}-catalog"))
        _telemetry.success(
            f"{part_no} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts
