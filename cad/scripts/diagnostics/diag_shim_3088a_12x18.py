r"""Shared author for the McMaster 3088A 12 x 18 mm carbon-steel ring shims.

Each ``diag_build_3088A<nnn>.py`` recipe is one thickness of the family
(``_mcmaster_3088a_12x18``).  The model is one Top-plane 12 x 18 annulus
extruded blind the catalogue nominal along +Y from the y = 0 face, as a NEW
body: the MHA-VN-071 pack stacks several shims in one part, and touching
shims must stay separate solids.  The volume check therefore books the
bodies already in the part (``stacked_volume_mm3``).

The family's 3-D model download was refused (HTTP 403), so there is no
replica gate: a standalone run is catalog-only, building one shim, checking
the solid and saving it under cad/out/reference.
"""

from __future__ import annotations

import math

from _check import check
from _feature_tree import name_last_feature
from _mcmaster_3088a_12x18 import SHIMS, THICKNESS_NOMINAL
from _part_checks import volume_check
from _sketch import ensure_fully_defined
from _sketch_circle import define_circle
from diagnostics.diag_mcmaster_lib import no_sketch_inference


def shim_volume(sku: str) -> float:
    """Nominal annulus volume of one ``sku`` shim, mm^3."""
    dims = SHIMS[sku]
    return math.pi / 4 * (dims.od**2 - dims.id**2) * THICKNESS_NOMINAL[sku]


async def author_shim(adapter, sku: str, stacked_volume_mm3: float = 0.0) -> None:
    """Add one ``sku`` shim as a new body at y = 0..thickness."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dims = SHIMS[sku]
    check(f"create_sketch {sku} annulus", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        await define_circle(adapter, 0.0, 0.0, dims.od / 2.0, f"{sku} OD")
        await define_circle(adapter, 0.0, 0.0, dims.id / 2.0, f"{sku} ID")
    await ensure_fully_defined(adapter, f"{sku} annulus")
    check(f"exit_sketch {sku} annulus", await adapter.exit_sketch())
    name_last_feature(adapter, f"Shim{sku}Profile")
    check(
        f"extrude {sku} shim",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS_NOMINAL[sku], merge_result=False)
        ),
    )
    name_last_feature(adapter, f"Shim{sku}Body")
    volume = stacked_volume_mm3 + shim_volume(sku)
    await volume_check(adapter, f"{sku} shim", volume, 0.005 * volume)


async def build_catalog(adapter, sku: str, recipe) -> dict[str, str]:
    """Catalog-only run: build ``recipe`` alone and save it, no vendor truth."""
    import _telemetry
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=sku):
        check(f"create_part {sku}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, sku)
        await recipe(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{sku} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{sku}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{sku}-catalog"))
        _telemetry.success(
            f"{sku} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts
