r"""McMaster 91255A267 -- black-oxide alloy steel button head hex drive screw, 10-32 x 5/8.

Used as ch-rocker-strap-tl-vn-hub-screw (MHA-CH-13-TL-VN-51), the screw that
snugs the strap blank's hub on the sub-plate through the hub washer (owner
ruling 2026-11-23).  The catalogue facts and the head form are
``_mcmaster_91255a267``'s.

The model is one Front-plane half profile revolved about the sketch Y axis:
the flat head top, the spherical dome down to the catalogue head diameter,
the head's side to the bearing face at y = 0, the shank at the 10-32 basic
major to the 45 deg tip chamfer; then the 1/8 hex socket cut mid-plane
about a plane at the head top (the half above it is air).  The thread is not
modelled.  The production build turns the body so the recipe's +Y is the
part frame's +Z.

The vendor model was probed but is not committed, so there is no replica
gate: the standalone run is catalog-only, building the recipe, checking the
solid and saving it under cad/out/reference.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91255A267.py
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
from _mcmaster_91255a267 import (  # noqa: E402
    DOME_CENTER_Y,
    HEAD_DIA,
    HEAD_HEIGHT,
    LENGTH,
    MAJOR_DIA,
    SIDE_TOP_Y,
    SKU,
    SOCKET_AF,
    SOCKET_DEPTH,
    TIP_CHAMFER,
    TOP_FLAT_R,
    revolved_volume,
    screw_volume,
)
from _part_checks import volume_check  # noqa: E402
from _sketch import add_line_chain  # noqa: E402
from diagnostics.diag_mcmaster_lib import no_sketch_inference, offset_plane  # noqa: E402

PART_NO = SKU
HEAD_TOP_PLANE = "HeadTopPlane"


def shank_profile_mm() -> list[tuple[float, float]]:
    """The profile's line chain from the dome's foot round to the head top's
    centre, (radius, y): the dome arc closes it."""
    rh = HEAD_DIA / 2.0
    rm = MAJOR_DIA / 2.0
    return [
        (rh, SIDE_TOP_Y),
        (rh, 0.0),
        (rm, 0.0),
        (rm, -LENGTH + TIP_CHAMFER),
        (rm - TIP_CHAMFER, -LENGTH),
        (0.0, -LENGTH),
        (0.0, HEAD_HEIGHT),
        (TOP_FLAT_R, HEAD_HEIGHT),
    ]


def socket_hexagon_mm() -> list[tuple[float, float]]:
    """The socket's six corners on the head-top plane (symmetric, so the
    plane's sketch orientation does not matter)."""
    r = SOCKET_AF / math.sqrt(3.0)
    return [
        (r * math.sin(math.radians(60.0 * i)), r * math.cos(math.radians(60.0 * i)))
        for i in range(6)
    ]


@stock_recipe("91255A267", threaded=False)
def build_91255A267(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_sketch screw profile", adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        check(
            "screw axis",
            adapter.add_centerline(0.0, HEAD_HEIGHT, 0.0, -LENGTH),
        )
        add_line_chain(adapter, shank_profile_mm(), close=False)
        # Counter-clockwise from the dome's foot up to the top flat's rim.
        check(
            "screw dome",
            adapter.add_arc(
                0.0, DOME_CENTER_Y, HEAD_DIA / 2.0, SIDE_TOP_Y, TOP_FLAT_R, HEAD_HEIGHT
            ),
        )
    check("exit_sketch screw profile", adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    check(
        "revolve screw",
        adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "ScrewBody")
    revolved = revolved_volume()
    volume_check(adapter, "button head screw", revolved, 0.005 * revolved)

    offset_plane(adapter, HEAD_TOP_PLANE, HEAD_HEIGHT)
    check("create_sketch socket", adapter.create_sketch(HEAD_TOP_PLANE))
    add_line_chain(adapter, socket_hexagon_mm())
    check("exit_sketch socket", adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    check(
        "cut socket",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * SOCKET_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "HexSocket")
    volume = screw_volume()
    volume_check(adapter, "button head screw with socket", volume, 0.005 * volume)


def build_catalog(adapter) -> dict[str, str]:
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
        check(f"create_part {PART_NO}", adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        build_91255A267(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{PART_NO} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{PART_NO}-catalog.SLDPRT"
        check(f"save -> {path}", adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(export_views(adapter, f"{PART_NO}-catalog"))
        _telemetry.success(
            f"{PART_NO} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        close_all(adapter)
    return artefacts


if __name__ == "__main__":
    from _session import run_build  # noqa: E402 -- diagnostic path bootstrap

    sys.exit(run_build(build_catalog))
