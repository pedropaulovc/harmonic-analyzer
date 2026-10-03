r"""McMaster 9715K43 -- high-carbon steel curved disc spring for a 0.190" shaft.

Used as transgear-pivot-spring (MHA-184).  The catalogue facts and the part
frame are ``transgear_pivot_spring_spec``'s.  One Front-plane half-section
revolved 360 deg about the Y axis: [INFERENCE: the page's "two contact
points" describe a bowed washer, which a single revolve cannot make] the
axisymmetric cone spanning the catalogue ID, OD and thickness, shown as
installed at MODEL_HEIGHT (the nominal room).  Its outer edge stands at
r = OD / 2 from the OD rim's bearing face (y = 0) up THICKNESS; its inner
edge at r = ID / 2 from MODEL_HEIGHT - THICKNESS up to the ID rim's face at
y = MODEL_HEIGHT.  The production build turns the body so the recipe's +Y is
the part frame's +Z.

A 3-D model is offered on the page but none was fetched or harvested, so it
has no replica gate: the standalone run is catalog-only, building the recipe,
checking the solid and saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_9715K43.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import add_line_chain, check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402
from transgear_pivot_spring_spec import (  # noqa: E402
    ID,
    MODEL_HEIGHT,
    OD,
    SKU,
    THICKNESS,
    spring_volume,
)

PART_NO = SKU


def spring_section() -> list[tuple[float, float]]:
    """The closed half-section (radius, y), mm, counter-clockwise: up the
    outer edge from the OD rim's bearing face, along the cone's upper face to
    the ID rim's face, down the inner edge and back along the lower face."""
    inner, outer = ID / 2.0, OD / 2.0
    return [
        (outer, 0.0),
        (outer, THICKNESS),
        (inner, MODEL_HEIGHT),
        (inner, MODEL_HEIGHT - THICKNESS),
    ]


async def build_9715K43(adapter, truth=None):
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_sketch spring section", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, MODEL_HEIGHT / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError(f"{PART_NO} spring section: CreateCenterLine failed")
        await add_line_chain(adapter, spring_section(), close=True)
    check("exit_sketch spring section", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringProfile")
    check(
        "revolve spring",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "SpringBody")
    volume = spring_volume()
    await volume_check(adapter, "disc spring", volume, 0.005 * volume)


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
        await build_9715K43(adapter)
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
