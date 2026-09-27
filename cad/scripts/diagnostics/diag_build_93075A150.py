r"""McMaster 93075A150 -- low-strength zinc-plated steel hex head screw, #6-32 x 5/8".

Catalogue: the McMaster product page https://www.mcmaster.com/93075A150/
(read through Browserbase on 2026-09-25 for the I31 hold-down; the tip
block's foot flange is sized for it in ``cone_tip_block_spec``): #6-32 UNC,
5/8 in (15.875) under the head, fully threaded, zinc-plated low-strength
steel, ASME B18.6.3; hex head 1/4 in across flats (0.244 min) and 3/32 in
high (0.080 to 0.093), across corners 0.272 min.  The replica takes the
nominal 1/4 x 3/32 head and the #6 major, 0.138 in (3.5052).

Geometry: the 93075A* family laws of ``diag_mcmaster_hex_head.py`` -- the
laws ``diag_build_93075A194.py`` reads off the vendor 93075A194 model and
proves against it in the replica gate -- at those five catalogue dimensions.
No 93075A150 vendor model is downloaded or committed (no McMaster .SLDPRT of
this size exists in the repository or its references), so this size has no
replica gate of its own.  Its standalone run is catalog-only: it builds the
recipe, checks the solid is sane and saves it under cad/out/reference for
inspection.  ``test_cone_tip_block_screw_drawing.py`` pins the catalogue
dimensions and proves the family builder reproduces 93075A194's recipe call
for call.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_93075A150.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagnostics.diag_mcmaster_hex_head import (  # noqa: E402
    HexHeadScrew,
    build_hex_head_screw,
)

PART_NO = "93075A150"
IN = 25.4
DIMS = HexHeadScrew(
    part_no=PART_NO,
    major_dia=0.138 * IN,
    pitch=IN / 32.0,
    length=0.625 * IN,
    head_af=0.25 * IN,
    head_h=3.0 / 32.0 * IN,
)


async def build_93075A150(adapter, truth=None):
    await build_hex_head_screw(adapter, DIMS)


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
        await build_93075A150(adapter)
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
