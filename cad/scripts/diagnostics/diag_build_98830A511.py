r"""McMaster 98830A511 -- 1008-1045 carbon steel key stock, 1/16 x 1/16 x 12 in.

Used as cone-shaft-key (MHA-DT-VN-71), cut to length by its builder.  The
catalogue facts are ``_mcmaster_98830a511``'s (read live 2026-11-09).  The
model is the whole supplied bar at its nominal 1/16 square: one Front-plane
section, height along +X from the bottom face on the Right Plane and width
centred on the Top Plane, extruded blind the stock's 12 in along +Z from the
z = 0 end.  No vendor model was fetched (the page states no edge form), so
the recipe has no replica gate and the standalone run is catalog-only,
building the recipe, checking the solid and saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98830A511.py
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
from _sketch import (  # noqa: E402
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
)
from _mcmaster_98830a511 import LENGTH, PART_NO, SIZE  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402


@stock_recipe("98830A511", threaded=False)
async def build_98830A511(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    half = SIZE / 2.0
    dims = SketchDims()
    check("create_sketch key section", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        # Front sketch x and y are model +X and +Y: bottom face on x = 0.
        lines = await add_line_chain(
            adapter, [(0.0, -half), (SIZE, -half), (SIZE, half), (0.0, half)]
        )
        for line, relation in zip(
            lines, ("horizontal", "vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"key section {relation} {line}",
                await adapter.add_sketch_constraint(line, None, relation),
            )
        await anchor_point_to_origin(
            adapter, f"{lines[0]}.start", 0.0, -half, "key section bottom corner"
        )
        dims.record("KeyHalfWidth")
        await dimension_between(
            adapter,
            f"{lines[0]}.start",
            f"{lines[0]}.end",
            "horizontal_distance",
            SIZE,
            "key height",
        )
        dims.record("KeyHeight")
        await dimension_between(
            adapter,
            f"{lines[1]}.start",
            f"{lines[1]}.end",
            "vertical_distance",
            SIZE,
            "key width",
        )
        dims.record("KeyWidth")
        await ensure_fully_defined(adapter, "key section")
    check("exit_sketch key section", await adapter.exit_sketch())
    name_last_feature(adapter, "KeyProfile")
    dims.apply(adapter, "KeyProfile")
    check(
        "extrude key stock",
        await adapter.create_extrusion(ExtrusionParameters(depth=LENGTH)),
    )
    name_last_feature(adapter, "KeyStock")
    volume = SIZE * SIZE * LENGTH
    await volume_check(adapter, "key stock", volume, 0.005 * volume)


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
        await build_98830A511(adapter)
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
