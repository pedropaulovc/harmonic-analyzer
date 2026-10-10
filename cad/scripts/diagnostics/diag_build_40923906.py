r"""MSC 40923906 -- 1/4-20 x 4 in zinc-plated steel slotted fillister screw.

Value Collection, MSC Industrial Supply: SAE J82 steel, zinc, ASME B18.6.3.
The selected catalog identity and 4 in under-head length come from MSC's
primary search result for https://www.mscdirect.com/product/details/40923906.
The direct product-page read returned HTTP 403; no manufacturer part
number, threaded length, stock price or live inventory is asserted.

This is a catalog-only ideal native model, not vendor CAD or a measured
replica.  The head retains the existing ASME B18.6.3 1/4 maxima (height
0.237 in, diameter 0.414 in).  The supplied under-head length is 101.6 mm;
MHA-VN-031's builder alone cuts it to fit.  The 90280A* family laws for the
head shape, slot, tip, runout and full-shank helical thread are retained as
modeling conventions, not verified dimensions of the supplied screw.

There is no vendor-model replica gate: the standalone run is catalog-only
-- it builds the recipe, checks its mass properties are sane and saves it
under cad/out/reference for inspection.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_40923906.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

from _msc_40923906 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402

PART_NO = "40923906"


@stock_recipe("40923906", threaded=True)
async def build_40923906(adapter, truth=None):
    await build_fillister(adapter, PART_NO, FILLISTER_SIZE)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _check import check
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=PART_NO):
        check(f"create_part {PART_NO}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        await build_40923906(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{PART_NO} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{PART_NO}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{PART_NO}-catalog"))
        _telemetry.success(
            f"{PART_NO} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    from _session import run_build

    sys.exit(run_build(build_catalog))
