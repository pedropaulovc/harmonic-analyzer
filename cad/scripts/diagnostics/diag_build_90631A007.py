r"""McMaster 90631A007 -- zinc-plated steel nylon-insert locknut, #6-32.

Catalogue: the McMaster product page https://www.mcmaster.com/90631A007/
(read through Browserbase on 2026-09-25 for the I31 hold-down): #6-32 UNC,
zinc-plated steel with a nylon insert, 5/16 in (7.9375) across flats and
11/64 in (4.365625) high.  The catalogue publishes no insert height, no
washer face and no corner chamfer, so the replica is the catalogue envelope:
a sharp-cornered hexagonal prism the full 11/64 high (the largest the nut can
sweep; ``cone_tip_block_spec`` sizes the flange against those corners), bored
through at the #6-32 tap drill (``_hole_spec``, #36, 2.705).  Nothing is taken
from a vendor model: no McMaster .SLDPRT of this part is downloaded or
committed.

Frame: axis +Y, midplane about the origin (the production build moves the
bearing face to y = 0).

With no vendor model there is no replica gate: the standalone run is
catalog-only -- it builds the recipe, checks its volume against the prism's
closed form (``volume_check``) and saves it under cad/out/reference for
inspection.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90631A007.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    check,
    define_circle,
    name_last_feature,
    volume_check,
)
from _hole_spec import HoleSpec, blind_cut_dia_mm  # noqa: E402

PART_NO = "90631A007"
IN = 25.4
THREAD = "#6-32"
NUT_AF = 5.0 / 16.0 * IN
NUT_H = 11.0 / 64.0 * IN
NUT_AC = NUT_AF * 2.0 / math.sqrt(3.0)
BORE_DIA = blind_cut_dia_mm(HoleSpec("tapped", THREAD))


def prism_volume() -> float:
    return (NUT_AF**2 * math.sqrt(3.0) / 2.0 - math.pi * BORE_DIA**2 / 4.0) * NUT_H


async def build_90631A007(adapter, truth=None):
    from _common import add_line_chain
    from diagnostics.diag_mcmaster_lib import no_sketch_inference
    from solidworks_mcp.adapters.base import ExtrusionParameters

    flat_r = NUT_AF / 2.0
    corner_r = NUT_AC / 2.0
    check("create_sketch nut", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, corner_r),
            (-flat_r, corner_r / 2.0),
            (-flat_r, -corner_r / 2.0),
            (0.0, -corner_r),
            (flat_r, -corner_r / 2.0),
            (flat_r, corner_r / 2.0),
        ])
    await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "nut bore")
    check("exit_sketch nut", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    check("extrude nut", await adapter.create_extrusion(
        ExtrusionParameters(depth=NUT_H, both_directions=True)))
    name_last_feature(adapter, "NutBody")
    v = prism_volume()
    await volume_check(adapter, "nut prism", v, 0.005 * v)

    # Replica frame: extrude axis = model Y, vendor frame: axis = Z.
    adapter._mcm_com_map = lambda v: [v[0], v[2], v[1]]


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
    )

    with _telemetry.span("catalog.build", label=PART_NO):
        check(f"create_part {PART_NO}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        await build_90631A007(adapter)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{PART_NO}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{PART_NO}-catalog"))
        _telemetry.success(f"{PART_NO} catalog build saved")
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
