r"""McMaster 91794A080 -- #2-56 x 7/16 18-8 stainless fillister screw.

Catalog dimensions were read live on 2026-10-10 from the public #2-56
fillister family table. Reuses the native fillister family laws; derived slot,
dome, thread/runout and vendor-frame mapping are family assumptions, not
verified vendor geometry. No vendor model has been harvested.

Run standalone (SolidWorks open); without a vendor file this is catalog-only::

    uv run python cad\scripts\diagnostics\diag_build_91794A080.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import check, run_build  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    OUT_DIR,
    assert_seat_sketch_baseline,
    close_all,
    export_views,
    mass_properties,
)


async def build_91794A080(adapter, truth=None):
    await build_fillister(adapter, "91794A080")


async def build_catalog(adapter) -> dict[str, str]:
    """Build and save the catalog recipe without claiming vendor equivalence."""
    with _telemetry.span("catalog.build", label="91794A080"):
        check("create_part 91794A080", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, "91794A080")
        await build_91794A080(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError("91794A080 catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / "91794A080-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, "91794A080-catalog"))
        _telemetry.success(
            f"91794A080 catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
