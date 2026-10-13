r"""McMaster 90114A124 -- #2-56 x 1/4 brass slotted fillister screw.

Catalogue dimensions were read live on 2026-10-09 from the product table and
2-D PDF. As with 91794A077, secondary dome, slot, thread and runout details
are the existing native fillister-family assumptions, not vendor-solid
measurements. No vendor model has been harvested or replica gate claimed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _session import run_build  # noqa: E402
from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_90114a124 import FILLISTER_SIZE, SKU  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    OUT_DIR,
    assert_seat_sketch_baseline,
    close_all,
    export_views,
    mass_properties,
)


@stock_recipe("90114A124", threaded=True)
async def build_90114A124(adapter, truth=None):
    await build_fillister(adapter, SKU, FILLISTER_SIZE)


async def build_catalog(adapter) -> dict[str, str]:
    """Save the catalogue recipe without claiming vendor-solid equivalence."""
    with _telemetry.span("catalog.build", label=SKU):
        check(f"create_part {SKU}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, SKU)
        await build_90114A124(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{SKU} catalogue build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{SKU}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{SKU}-catalog"))
        _telemetry.success(
            f"{SKU} catalogue build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
