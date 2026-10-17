r"""McMaster 91595A452 -- 52100 alloy-steel dowel pin, 6 mm diameter, 20 mm long.

Catalogue: https://www.mcmaster.com/91595A452/ (read live 2026-10-17):
diameter 6 mm, +0.004 to +0.012 mm (DIN 6325-m6 / ISO 8734), 20 long, Rockwell
C52 min, end shape "Round x Chamfer/Round".  The diameter is the carrier's
(``carrier.CL_DOWEL_DIA``); the end forms are the vendor model's, read off its
STEP in FreeCAD (``_mcmaster_91595a452``, whose docstring carries the source
and the numbers).

Geometry: one revolve (``PinBody``) of a half-section with no flat face: the
chamfered end's spherical crown and 15 deg cone, the Ø6 cylinder, and the
round end's spherical dome.  ``diag_mcmaster_dowel.build_dowel`` draws flat
end faces and a tangent corner radius, which this pin does not have, so the
section is drawn here.  The model is at nominal Ø6, as the vendor's is.

McMaster's vendor model (SLDPRT and STEP, downloaded from the product page
2026-10-17) was read for dimensions only; it is NOT replica-gated (user ruling
2026-10-17).  The standalone run is catalog-only: it builds the recipe, checks
the solid and saves it under cad/out/reference.

Frame: pin axis = model Y (Front ∩ Right); the chamfered end's tip at y = 0
(the Top Plane), the round end's tip at y = LENGTH.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91595A452.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_91595a452 import (  # noqa: E402
    CHAMFER_LEN,
    CROWN_H,
    DIA,
    DOME_H,
    LENGTH,
    chamfer_rim_radius,
    crown_radius,
    dome_radius,
    dowel_volume,
)
from diagnostics.sketch_profile import Line, Segment, minor_arc  # noqa: E402

PART_NO = "91595A452"


def pin_section() -> tuple[Segment, ...]:
    """The pin's half-section on Front, (radius, y) in mm, from the chamfered
    tip round the crown, chamfer, cylinder and dome back down the axis.  Pure."""
    radius = DIA / 2.0
    tip, crown_rim = (0.0, 0.0), (chamfer_rim_radius(), CROWN_H)
    chamfer_end = (radius, CROWN_H + CHAMFER_LEN)
    dome_rim, far_tip = (radius, LENGTH - DOME_H), (0.0, LENGTH)
    return (
        minor_arc((0.0, crown_radius()), tip, crown_rim),
        Line(crown_rim, chamfer_end),
        Line(chamfer_end, dome_rim),
        minor_arc((0.0, LENGTH - dome_radius()), dome_rim, far_tip),
        Line(far_tip, tip),
    )


@stock_recipe("91595A452", threaded=False)
async def build_91595A452(adapter, truth=None):
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _check import check  # noqa: E402 -- diagnostic path bootstrap
    from _feature_tree import name_last_feature  # noqa: E402 -- diagnostic path bootstrap
    from _part_checks import volume_check  # noqa: E402 -- diagnostic path bootstrap
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import (
        assert_profile_closed,
        draw_closed_profile,
        no_sketch_inference,
    )

    check("create_sketch pin section", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCenterLine(
                0.0, 0.0, 0.0, 0.0, LENGTH / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} pin section: CreateCenterLine failed")
    await draw_closed_profile(
        adapter, pin_section(), label=f"{PART_NO} pin section", loops=1
    )
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    assert_profile_closed(
        adapter, f"{PART_NO} pin section", loops=1, feature="PinProfile"
    )
    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "PinBody")
    volume = dowel_volume()
    await volume_check(adapter, f"{PART_NO} dowel pin", volume, 0.005 * volume)


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    import _telemetry
    from _check import check  # noqa: E402 -- diagnostic path bootstrap
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
        await build_91595A452(adapter)
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
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
