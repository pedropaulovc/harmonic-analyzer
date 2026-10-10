r"""McMaster 90280A110 -- #4-40 x 1/2 steel narrow fillister head slotted screw.

Catalogue dimensions were read live on 2026-10-09 from the publicly browsable
McMaster #4-40 zinc-plated fillister family table and the part's 2-D PDF
(0.183 head dia, 0.107 head height, 0.112 major, 0.5 long). Reuses the
existing native fillister recipe; derived slot, dome, thread/runout and
vendor-frame mapping are family assumptions, not verified vendor geometry.
No vendor model harvested.

Run standalone on a farm seat; without vendor CAD this is catalogue-only::

    uv run python cad\scripts\diagnostics\diag_build_90280A110.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import check, run_build  # noqa: E402
from diagnostics.diag_mcmaster_fillister import build_fillister  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    OUT_DIR,
    assert_seat_sketch_baseline,
    close_all,
    export_views,
    mass_properties,
)


async def build_90280A110(adapter, truth=None):
    await build_fillister(adapter, "90280A110")


async def build_catalog(adapter) -> dict[str, str]:
    """Build and save the catalogue recipe without claiming vendor equivalence."""
    with _telemetry.span("catalog.build", label="90280A110"):
        check("create_part 90280A110", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, "90280A110")
        await build_90280A110(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError("90280A110 catalogue build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / "90280A110-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, "90280A110-catalog"))
        _telemetry.success(
            f"90280A110 catalogue build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
