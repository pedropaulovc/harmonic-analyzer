r"""McMaster 9714K392 -- steel wave disc spring, ID 0.385 x OD 0.5 in.

Used as vn-cylinder-bank-spring (MHA-VN-052).  The catalogue facts and the
part frame are ``vn_cylinder_bank_spring_spec``'s.  The model is the
spring's installed envelope: one Top-plane ID x OD annulus extruded blind
MODEL_HEIGHT along +Y from the south bearing face (y = 0).  [INFERENCE: the
waves are not modelled; the envelope is what the bank layout and the
interference gate see.]  The production build turns the body so the
recipe's +Y is the part frame's +Z.

A 3-D model is offered on the page but none was fetched or harvested, so it
has no replica gate: the standalone run is catalog-only, building the recipe,
checking the solid and saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_9714K392.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import check, define_circle, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402
from vn_cylinder_bank_spring_spec import (  # noqa: E402
    ID,
    MODEL_HEIGHT,
    OD,
    SKU,
    spring_volume,
)

PART_NO = SKU


async def build_9714K392(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch spring annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, OD / 2.0, "spring OD")
        await define_circle(adapter, 0.0, 0.0, ID / 2.0, "spring ID")
    check("exit_sketch spring annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    check(
        "extrude spring envelope",
        await adapter.create_extrusion(ExtrusionParameters(depth=MODEL_HEIGHT)),
    )
    name_last_feature(adapter, "SpringBody")
    volume = spring_volume()
    await volume_check(adapter, "wave spring envelope", volume, 0.005 * volume)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
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
        await build_9714K392(adapter)
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
