r"""McMaster 94773A606 -- 18-8 stainless shim, ID 1/8 x OD 1/4 x .005 in.

Used as pd-vn-transgear-cluster-shim (MHA-PD-VN-68).  The catalogue facts and
the part frame are ``pd_vn_transgear_cluster_shim_spec``'s.  The model is one
Top-plane ID x OD annulus extruded blind THICKNESS (the catalogue's .005 in
nominal) along +Y from the y = 0 face, the bore at its band's middle.

The product page is behind McMaster's login wall, so no 3-D model was
fetched: the recipe has no replica gate, and the standalone run is
catalog-only, building the recipe, checking the solid and saving it under
cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_94773A606.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _sketch_circle import define_circle  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402
from pd_vn_transgear_cluster_shim_spec import (  # noqa: E402
    ID,
    OD,
    SKU,
    THICKNESS,
    shim_volume,
)

PART_NO = SKU


@stock_recipe("94773A606", threaded=False)
async def build_94773A606(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch shim annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, OD / 2.0, "shim OD")
        await define_circle(adapter, 0.0, 0.0, ID / 2.0, "shim ID")
    check("exit_sketch shim annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "ShimProfile")
    check(
        "extrude shim",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "ShimBody")
    volume = shim_volume()
    await volume_check(adapter, "shim", volume, 0.005 * volume)


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
        await build_94773A606(adapter)
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
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
