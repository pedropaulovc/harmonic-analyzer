r"""McMaster 97482A010 -- 1100 aluminum domed head solid rivet, 1/16" x 1/8".

Used as latch-hook-rivet (MHA-175).  The catalogue facts and the part frame
are ``latch_hook_rivet_spec``'s.  One Front-plane half-section revolved 360
deg about the Y axis: the shank from y = -LENGTH to the head's flat bearing
face at y = 0, and the dome, [INFERENCE] a spherical cap from the Ø HEAD_DIA
rim to the apex at y = HEAD_H (the page states no head radius).

No vendor model was supplied or harvested, so it has no replica gate: the
standalone run is catalog-only, building the recipe, checking the solid and
saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_97482A010.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import add_line_chain, check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402
from latch_hook_rivet_spec import (  # noqa: E402
    DIA,
    DOME_CENTRE_Y,
    HEAD_DIA,
    HEAD_H,
    LENGTH,
    SKU,
    rivet_volume,
)

PART_NO = SKU


def rivet_section() -> list[tuple[float, float]]:
    """The half-section's straight run (radius, y), mm: from the apex down
    the axis, round the shank and out along the bearing face to the head's
    rim.  The dome arc closes it from the rim back to the apex."""
    radius = DIA / 2.0
    return [
        (0.0, HEAD_H),
        (0.0, -LENGTH),
        (radius, -LENGTH),
        (radius, 0.0),
        (HEAD_DIA / 2.0, 0.0),
    ]


async def build_97482A010(adapter, truth=None):
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_sketch rivet section", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(
                0.0, -LENGTH / 1000.0, 0.0, 0.0, HEAD_H / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} rivet section: CreateCenterLine failed")
        prev_db = bool(sk_mgr.AddToDB)
        sk_mgr.AddToDB = True
        try:
            # The dome: CCW about its centre on the axis, rim to apex.
            arc = sk_mgr.CreateArc(
                0.0,
                DOME_CENTRE_Y / 1000.0,
                0.0,
                HEAD_DIA / 2000.0,
                0.0,
                0.0,
                0.0,
                HEAD_H / 1000.0,
                0.0,
                1,
            )
            if arc is None:
                raise RuntimeError(f"{PART_NO} rivet section: dome arc failed")
            await add_line_chain(adapter, rivet_section(), close=False)
        finally:
            sk_mgr.AddToDB = prev_db
    check("exit_sketch rivet section", await adapter.exit_sketch())
    name_last_feature(adapter, "RivetProfile")
    check(
        "revolve rivet",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "RivetBody")
    volume = rivet_volume()
    await volume_check(adapter, "solid rivet", volume, 0.005 * volume)


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
        await build_97482A010(adapter)
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
