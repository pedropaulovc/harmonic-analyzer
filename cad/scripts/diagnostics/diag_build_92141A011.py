r"""McMaster 92141A011 -- 18-8 stainless steel washer, No. 10, ID 0.203 x OD 0.438 in.

Used as dt-cylinder-gear-tl-vn-cam-clamp-washer (MHA-DT-12-TL-VN-53). The
catalogue facts are ``_mcmaster_92141a011``'s. The model is one Top-plane
ID x OD annulus extruded blind MODEL_THICKNESS (the 0.017-0.047 in range's
mid value) along +Y from the y = 0 face, the part frame's axis.

No vendor model was downloaded, so the recipe has no replica gate: the
standalone run is catalog-only, building the recipe, checking the solid and
saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92141A011.py
"""

from __future__ import annotations

import math
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
from _mcmaster_92141a011 import ID, MODEL_THICKNESS, OD, PART_NO  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _sketch_circle import define_circle  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402


def washer_volume() -> float:
    """Nominal annulus volume of the modelled washer, in mm^3."""
    return math.pi / 4.0 * (OD**2 - ID**2) * MODEL_THICKNESS


@stock_recipe("92141A011", threaded=False)
async def build_92141A011(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch washer annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, OD / 2.0, "washer OD")
        await define_circle(adapter, 0.0, 0.0, ID / 2.0, "washer ID")
    check("exit_sketch washer annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    check(
        "extrude washer",
        await adapter.create_extrusion(ExtrusionParameters(depth=MODEL_THICKNESS)),
    )
    name_last_feature(adapter, "WasherBody")
    volume = washer_volume()
    await volume_check(adapter, "washer", volume, 0.005 * volume)


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
        await build_92141A011(adapter)
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
