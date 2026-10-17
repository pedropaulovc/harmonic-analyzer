r"""McMaster 5972K41 -- steel ball bearing, sealed, trade no. 6200-2RS, 10 x 30 x 9.

Catalogue: https://www.mcmaster.com/5972K41/ (read live 2026-10-17): steel,
Buna-N seals both sides, ABEC 1, C3 radial clearance 0.008-0.023, DIN 625-1;
ID 10 (-0.008/0), OD 30 (-0.009/0), width 9 (-0.12/0).  The envelope is the
calculator's (``trammel.BEARING_BORE`` / ``BEARING_OD`` / ``BEARING_WIDTH``);
every other value is the vendor model's, read off its STEP in FreeCAD
(``_mcmaster_5972k41``, whose docstring carries the source and the numbers).

Geometry: the vendor's eleven bodies, each its own unmerged feature --
``OuterRing`` and ``InnerRing`` (a revolve each: raceway groove, 0.45 x 45 deg
chamfers on the OD and bore corners), ``NearSeal`` and ``FarSeal`` (stepped,
crowned annuli between the lands, inner face tangent to the balls) and
``Ball1``..``Ball7`` (a semicircle revolved about its diameter on
``BallPlane``, the mid-width plane).  The balls conform to both grooves and
touch both seals, so every body is unmerged (``merge_result=False``) to keep
the vendor's body split.  Seals are modelled as their vendor solids; their lips
are not modelled finer than the vendor does.

McMaster's vendor model (SLDPRT and STEP, downloaded from the product page
2026-10-17) was read for dimensions only; it is NOT replica-gated (user ruling
2026-10-17).  The standalone run is catalog-only: it builds the recipe, checks
the solid and saves it under cad/out/reference.

Frame: bearing axis = model Y (Front ∩ Right); one side face at y = 0 (the
Top Plane), the other at y = WIDTH; the near seal sits at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_5972K41.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402
from _mcmaster_5972k41 import (  # noqa: E402
    BALL_COUNT,
    BALL_DIA,
    BORE,
    GROOVE_HALF_WIDTH,
    INNER_LAND_DIA,
    OD,
    OUTER_LAND_DIA,
    PITCH_DIA,
    RING_CHAMFER,
    SEAL_CROWN_DIA,
    SEAL_LIP_DIA,
    SEAL_LIP_RECESS,
    SEAL_WEB_RECESS,
    WIDTH,
    ball_volume,
    inner_ring_volume,
    outer_ring_volume,
    seal_crown_radius,
    seal_inner_recess,
    seal_volume,
)
from diagnostics.sketch_profile import Arc, Line, Segment, minor_arc  # noqa: E402

PART_NO = "5972K41"
BALL_PLANE = "BallPlane"
# Body order of the recipe: the section bodies on Front, then the balls.
SECTION_BODIES = ("OuterRing", "InnerRing", "NearSeal", "FarSeal")
BALL_BODIES = tuple(f"Ball{k}" for k in range(1, BALL_COUNT + 1))
BODY_NAMES = SECTION_BODIES + BALL_BODIES

_GROOVE_CENTRE = (PITCH_DIA / 2.0, WIDTH / 2.0)


def outer_ring_section() -> tuple[Segment, ...]:
    """The outer ring's half-section on Front, (radius, y) in mm.  Pure."""
    land, od = OUTER_LAND_DIA / 2.0, OD / 2.0
    c = RING_CHAMFER
    lo, hi = WIDTH / 2.0 - GROOVE_HALF_WIDTH, WIDTH / 2.0 + GROOVE_HALF_WIDTH
    a, b, d = (land, 0.0), (od - c, 0.0), (od, c)
    e, f, g = (od, WIDTH - c), (od - c, WIDTH), (land, WIDTH)
    h, i = (land, hi), (land, lo)
    return (
        Line(a, b),
        Line(b, d),
        Line(d, e),
        Line(e, f),
        Line(f, g),
        Line(g, h),
        minor_arc(_GROOVE_CENTRE, h, i),
        Line(i, a),
    )


def inner_ring_section() -> tuple[Segment, ...]:
    """The inner ring's half-section on Front, (radius, y) in mm.  Pure."""
    bore, land = BORE / 2.0, INNER_LAND_DIA / 2.0
    c = RING_CHAMFER
    lo, hi = WIDTH / 2.0 - GROOVE_HALF_WIDTH, WIDTH / 2.0 + GROOVE_HALF_WIDTH
    a, b, d = (bore + c, 0.0), (land, 0.0), (land, lo)
    e, f, g = (land, hi), (land, WIDTH), (bore + c, WIDTH)
    h, i = (bore, WIDTH - c), (bore, c)
    return (
        Line(a, b),
        Line(b, d),
        minor_arc(_GROOVE_CENTRE, d, e),
        Line(e, f),
        Line(f, g),
        Line(g, h),
        Line(h, i),
        Line(i, a),
    )


def seal_section(far: bool) -> tuple[Segment, ...]:
    """One seal's half-section on Front, (radius, y) in mm; the near seal
    recesses from y = 0, the far one (``far``) from y = WIDTH.  Pure."""

    def at(depth: float) -> float:
        return WIDTH - depth if far else depth

    r_in, r_out = INNER_LAND_DIA / 2.0, OUTER_LAND_DIA / 2.0
    r_crown, r_lip = SEAL_CROWN_DIA / 2.0, SEAL_LIP_DIA / 2.0
    inner, lip, web = at(seal_inner_recess()), at(SEAL_LIP_RECESS), at(SEAL_WEB_RECESS)
    crown_c = ((r_in + r_crown) / 2.0, at(SEAL_LIP_RECESS + seal_crown_radius()))
    a, b, d = (r_in, inner), (r_out, inner), (r_out, lip)
    e, f, g, h = (r_lip, lip), (r_lip, web), (r_crown, web), (r_in, web)
    return (
        Line(a, b),
        Line(b, d),
        Line(d, e),
        Line(e, f),
        Line(f, g),
        minor_arc(crown_c, g, h),
        Line(h, a),
    )


def ball_section(index: int) -> tuple[Segment, ...]:
    """Ball ``index`` (0-based) on BallPlane: a semicircle about its centre on
    the pitch circle, closed by its radial diameter (the revolve axis).
    ``minor_arc`` refuses an exact half circle, so the Arc is authored
    directly, counter-clockwise from the inner end of the diameter.  Pure."""
    theta = 2.0 * math.pi * index / BALL_COUNT
    u = (math.cos(theta), math.sin(theta))
    pitch, radius = PITCH_DIA / 2.0, BALL_DIA / 2.0
    centre = (pitch * u[0], pitch * u[1])
    inner = ((pitch - radius) * u[0], (pitch - radius) * u[1])
    outer = ((pitch + radius) * u[0], (pitch + radius) * u[1])
    return (Arc(centre, inner, outer), Line(outer, inner))


@stock_recipe("5972K41", threaded=False)
async def build_5972K41(adapter, truth=None):
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
        bodies,
        draw_closed_profile,
        no_sketch_inference,
        offset_plane,
    )

    async def revolve_body(
        plane: str,
        name: str,
        segments: tuple[Segment, ...],
        axis: tuple[tuple[float, float], tuple[float, float]],
    ) -> None:
        check(f"create_sketch {name}", await adapter.create_sketch(plane))
        (x0, y0), (x1, y1) = axis
        with no_sketch_inference(adapter):
            if (
                adapter.currentSketchManager.CreateCenterLine(
                    x0 / 1000.0, y0 / 1000.0, 0.0, x1 / 1000.0, y1 / 1000.0, 0.0
                )
                is None
            ):
                raise RuntimeError(f"{PART_NO} {name}: CreateCenterLine failed")
        await draw_closed_profile(adapter, segments, label=f"{PART_NO} {name}", loops=1)
        check(f"exit_sketch {name}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{name}Profile")
        assert_profile_closed(
            adapter, f"{PART_NO} {name}", loops=1, feature=f"{name}Profile"
        )
        # Unmerged: every vendor body touches another (seal faces on the ring
        # lands, balls in the grooves), so one merged revolve would fuse them.
        check(
            f"revolve {name}",
            await adapter.create_revolve(
                RevolveParameters(angle=360.0, merge_result=False)
            ),
        )
        name_last_feature(adapter, name)

    bearing_axis = ((0.0, 0.0), (0.0, WIDTH))
    sections = (
        outer_ring_section(),
        inner_ring_section(),
        seal_section(far=False),
        seal_section(far=True),
    )
    expected = 0.0
    for name, segments, volume in zip(
        SECTION_BODIES,
        sections,
        (outer_ring_volume(), inner_ring_volume(), seal_volume(), seal_volume()),
        strict=True,
    ):
        await revolve_body("Front", name, segments, bearing_axis)
        expected += volume
        await volume_check(adapter, f"{PART_NO} {name}", expected, 0.005 * volume)

    offset_plane(adapter, BALL_PLANE, WIDTH / 2.0)
    for index, name in enumerate(BALL_BODIES):
        segments = ball_section(index)
        diameter = segments[1]
        await revolve_body(BALL_PLANE, name, segments, (diameter.end, diameter.start))
    expected += BALL_COUNT * ball_volume()
    await volume_check(adapter, f"{PART_NO} bearing", expected, 0.005 * expected)
    if len(bodies(adapter)) != len(BODY_NAMES):
        raise RuntimeError(
            f"{PART_NO}: {len(bodies(adapter))} bodies, expected {len(BODY_NAMES)}"
        )


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
        await build_5972K41(adapter)
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
