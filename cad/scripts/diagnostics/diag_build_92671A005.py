r"""McMaster 92671A005 -- brass hex nut, #4-40, 1/4 in across flats x 3/32 in.

Used as vn-wheel-axle-nut (MHA-VN-025, two per wheel: nut and locknut).  The
catalogue facts and the part frame are ``vn_wheel_axle_nut_spec``'s.  The
model is one Top-plane profile -- the hexagon (flats normal to the sketch X,
as ``build_9489T111``'s nut) with the bore circle inside it -- extruded blind
THICKNESS along +Y from the y = 0 bearing face.  The thread is not modelled:
the bore is the #4-40 basic major diameter.  The production build turns the
body so the recipe's +Y is the part frame's +Z.

A 3-D model is offered on the page but none was fetched or harvested, so it
has no replica gate: the standalone run is catalog-only, building the recipe,
checking the solid and saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92671A005.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    add_line_chain,
    check,
    define_circle,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402
from vn_wheel_axle_nut_spec import (  # noqa: E402
    ACROSS_CORNERS,
    BORE_DIA,
    SKU,
    THICKNESS,
    nut_volume,
)

PART_NO = SKU


def hex_profile_mm() -> list[tuple[float, float]]:
    """The hexagon's six sketch vertices, corners on the sketch +-Y meridian."""
    r = ACROSS_CORNERS / 2.0
    return [
        (r * math.sin(math.radians(60.0 * i)), r * math.cos(math.radians(60.0 * i)))
        for i in range(6)
    ]


async def build_92671A005(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch nut profile", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, hex_profile_mm())
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "nut bore")
    check("exit_sketch nut profile", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    check(
        "extrude nut",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "NutBody")
    volume = nut_volume()
    await volume_check(adapter, "hex nut", volume, 0.005 * volume)


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
        await build_92671A005(adapter)
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
