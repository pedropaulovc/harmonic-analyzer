r"""McMaster 97175A344 -- 4140 pull-out dowel, 3/8 x 3/4 in, tapped 10-32.

Used as dt-cylinder-gear-tl-vn-cam-stub (MHA-DT-12-TL-VN-50). The catalogue
facts are ``_mcmaster_97175a344``'s. The model is one revolved section: the
nominal Ø3/8 cylinder (no end forms: the page states none, the
``diag_build_98296A027`` convention) with its tapped end bored to the 10-32
tap drill (``_hole_spec.TAP_DRILL_MM``, the repo's tapped-hole convention)
to the ASME B18.8.2 full-thread depth.

No vendor model was downloaded: the standalone run is catalog-only.

Frame: axis +Y, the plain (pressed) end face at y = 0, the tapped end face
at y = LENGTH.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_97175A344.py
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
from _hole_spec import TAP_DRILL_MM  # noqa: E402
from _mcmaster_97175a344 import (  # noqa: E402
    DIA,
    FULL_THREAD_DEPTH_MIN,
    LENGTH,
    PART_NO,
    THREAD,
)
from _part_checks import volume_check  # noqa: E402
from _sketch import add_line_chain  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference  # noqa: E402

TAP_DIA = TAP_DRILL_MM[THREAD]
TAP_DEPTH = FULL_THREAD_DEPTH_MIN


def dowel_section() -> list[tuple[float, float]]:
    """The half-section (radius, y) revolved about Y, closed on the axis."""
    radius = DIA / 2.0
    tap = TAP_DIA / 2.0
    return [
        (0.0, 0.0),
        (radius, 0.0),
        (radius, LENGTH),
        (tap, LENGTH),
        (tap, LENGTH - TAP_DEPTH),
        (0.0, LENGTH - TAP_DEPTH),
    ]


def dowel_volume() -> float:
    """Nominal volume of the modelled dowel, in mm^3."""
    return math.pi / 4.0 * (DIA**2 * LENGTH - TAP_DIA**2 * TAP_DEPTH)


@stock_recipe("97175A344", threaded=False)
async def build_97175A344(adapter, truth=None):
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_sketch dowel section", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, LENGTH / 1000.0, 0.0) is None:
            raise RuntimeError(f"{PART_NO} dowel section: CreateCenterLine failed")
        await add_line_chain(adapter, dowel_section())
    check("exit_sketch dowel section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    check(
        "revolve dowel",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "PinBody")
    volume = dowel_volume()
    await volume_check(adapter, "pull-out dowel", volume, 0.005 * volume)


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
        await build_97175A344(adapter)
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
