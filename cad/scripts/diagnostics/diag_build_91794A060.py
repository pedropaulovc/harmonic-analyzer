r"""McMaster 91794A060 -- #0-80 x 1/2 18-8 stainless fillister screw.

Owner ruling 2026-11-26 (#3738): four stock #0-80 x 1/2 slotted fillisters
(MHA-PD-VN-72) screw the MHA-PD-26 feed rack to the MHA-PD-27 bottom guide
rail. A new purchased SKU (#2886): the native fillister family's head, slot
and tip chamfer on a plain shank at the #0-80 basic major; the thread is not
modelled. Derived slot and dome are family assumptions, not verified vendor
geometry. No vendor model has been harvested.

Run standalone (SolidWorks open); without a vendor file this is catalog-only::

    uv run python cad\scripts\diagnostics\diag_build_91794A060.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _check import check  # noqa: E402
from _session import run_build  # noqa: E402
from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91794a060 import FILLISTER_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_fillister_plain import build_plain_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    OUT_DIR,
    assert_seat_sketch_baseline,
    close_all,
    export_views,
    mass_properties,
)


@stock_recipe("91794A060", threaded=False)
def build_91794A060(adapter, truth=None):
    build_plain_fillister(adapter, FILLISTER_SIZE)


def build_catalog(adapter) -> dict[str, str]:
    """Build and save the catalog recipe without claiming vendor equivalence."""
    with _telemetry.span("catalog.build", label="91794A060"):
        check("create_part 91794A060", adapter.create_part())
        assert_seat_sketch_baseline(adapter, "91794A060")
        build_91794A060(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError("91794A060 catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / "91794A060-catalog.SLDPRT"
        check(f"save -> {path}", adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(export_views(adapter, "91794A060-catalog"))
        _telemetry.success(
            f"91794A060 catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
