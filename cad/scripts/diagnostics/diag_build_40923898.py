r"""MSC 40923898 -- 1/4-20 x 3-1/2 zinc-plated steel slotted fillister screw.

MSC Industrial Supply, manufacturer part 1456MSL (SAE J82 steel, zinc,
ASME B18.6.3, fully threaded).  MSC publishes no head sizes and no CAD
model, so the head takes ASME B18.6.3's 1/4 maximum and the length the
86.0 cut-to-fit nominal (U37c).  Reuses the 90280A* fillister family laws
unchanged, like 90280A837.

With no vendor model there is no replica gate: the standalone run is
catalog-only -- it builds the recipe, checks its mass properties are sane
and saves it under cad/out/reference for inspection.  (The McMaster
``replica_main`` path would demand a vendor SLDPRT and its harvest, which
MSC cannot supply.)

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_40923898.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402

PART_NO = "40923898"


async def build_40923898(adapter, truth=None):
    await build_fillister(adapter, PART_NO)


async def build_catalog(adapter) -> dict[str, str]:
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

    with _telemetry.span("catalog.build", label=PART_NO):
        check(f"create_part {PART_NO}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        await build_40923898(adapter)
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
    from _common import run_build

    sys.exit(run_build(build_catalog))
