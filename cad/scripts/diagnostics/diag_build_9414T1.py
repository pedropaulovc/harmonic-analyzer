r"""McMaster 9414T1 -- black-oxide 1215 steel set screw shaft collar, 1/16" bore.

Catalogue: the McMaster product page https://www.mcmaster.com/9414T1/ (read
in a headless browser on 2026-09-29 for MHA-VN-016): one-piece set screw shaft
collar for 1/16 in shaft, 1/4 in OD, 3/16 in wide, black-oxide 1215 carbon
steel, one black-oxide steel hex-socket set screw included.  The vendor STEP
model was read locally (never committed) for what the page does not give:
45 deg breaks on all four edges and the #2-56 radial cup-point set screw at
mid-width, 0.050 in hex socket, its outer end proud of the OD as supplied.
Every number is in ``cone_tip_collar_spec``.

No vendor .SLDPRT is downloaded or committed, so this recipe has no replica
gate.  Its standalone run is catalog-only: it builds the recipe, checks the
solid and saves it under cad/out/reference for inspection.

Geometry, in the spec's frame (collar axis +Y, south face y = 0, north face
y = WIDTH, set screw along +X at y = WIDTH / 2):

* the ring section revolved about Y, with the 45 deg EDGE_BREAK on the OD and
  bore edges of both faces;
* the set-screw hole: SET_SCREW_MAJOR_DIA revolved-cut about the screw axis,
  from the collar axis out past the OD (threads are not modelled);
* the set screw as material: a SET_SCREW_MAJOR_DIA cylinder revolved about the
  same axis, its cup rim at ``cup_radius`` from the collar axis (the
  as-supplied SET_SCREW_CUP_RADIUS by default) and its socket end the screw's
  length (SET_SCREW_END_RADIUS - SET_SCREW_CUP_RADIUS) further out, with
  SET_SCREW_END_CHAMFER at 45 deg on the socket end.  An installed collar
  passes the radius its screw is tightened to, so the screw reads seated on
  its shaft.  The cup point is modelled as a plain flat end at the cup rim,
  not a conical recess: the rim radius is what bears on the shaft flat and
  the recess has no fit role;
* the hex socket SET_SCREW_SOCKET_AF across flats, cut blind
  SET_SCREW_SOCKET_DEPTH in from the screw's outer end.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_9414T1.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import check, name_last_feature, volume_check  # noqa: E402
from vn_cone_tip_collar_spec import (  # noqa: E402
    BORE_DIA,
    EDGE_BREAK,
    OUTER_DIA,
    SET_SCREW_CUP_RADIUS,
    SET_SCREW_END_CHAMFER,
    SET_SCREW_END_RADIUS,
    SET_SCREW_MAJOR_DIA,
    SET_SCREW_SOCKET_AF,
    SET_SCREW_SOCKET_DEPTH,
    SKU,
    WIDTH,
)
from diagnostics.diag_mcmaster_lib import _rev_frustum, offset_plane  # noqa: E402

PART_NO = SKU
HOLE_OVERRUN = 0.5  # mm past the OD, so the cut leaves no skin

_BORE_R = BORE_DIA / 2.0
_OUTER_R = OUTER_DIA / 2.0
_SCREW_R = SET_SCREW_MAJOR_DIA / 2.0
_SCREW_Y = WIDTH / 2.0
_SOCKET_CORNER_R = SET_SCREW_SOCKET_AF / math.sqrt(3.0)

if 2.0 * EDGE_BREAK >= _OUTER_R - _BORE_R:
    raise ValueError("9414T1 edge breaks meet across the ring wall")
if _SOCKET_CORNER_R >= _SCREW_R - SET_SCREW_END_CHAMFER:
    raise ValueError("9414T1 socket corners break out of the set screw end")
if SET_SCREW_SOCKET_DEPTH >= SET_SCREW_END_RADIUS - SET_SCREW_CUP_RADIUS:
    raise ValueError("9414T1 socket floor falls through the set screw")


def ring_volume() -> float:
    """Revolved ring less the four 45 deg edge-break rings (Pappus)."""
    c = EDGE_BREAK
    tri = c * c / 2.0
    return (
        math.pi * (_OUTER_R**2 - _BORE_R**2) * WIDTH
        - 2.0 * 2.0 * math.pi * (_OUTER_R - c / 3.0) * tri
        - 2.0 * 2.0 * math.pi * (_BORE_R + c / 3.0) * tri
    )


def hole_volume(steps: int = 600) -> float:
    """Ring material inside the set-screw hole, by midpoint integration.

    The hole runs along +X from the collar axis; at each (x, z) its chord
    along Y is 2 sqrt(r^2 - z^2), counted where (x, z) lies in the ring wall.
    The hole stays clear of the face breaks (checked in the spec).
    """
    x_end = _OUTER_R + HOLE_OVERRUN
    dx = x_end / steps
    dz = 2.0 * _SCREW_R / steps
    total = 0.0
    for i in range(steps):
        x = (i + 0.5) * dx
        for j in range(steps):
            z = -_SCREW_R + (j + 0.5) * dz
            rr = x * x + z * z
            if _BORE_R**2 <= rr <= _OUTER_R**2:
                total += 2.0 * math.sqrt(_SCREW_R**2 - z * z)
    return total * dx * dz


def screw_volume() -> float:
    """Flat-ended cylinder, cup rim to socket end, less the end chamfer."""
    ch = SET_SCREW_END_CHAMFER
    length = SET_SCREW_END_RADIUS - SET_SCREW_CUP_RADIUS
    return math.pi * _SCREW_R**2 * (length - ch) + _rev_frustum(
        ch, _SCREW_R, _SCREW_R - ch
    )


def socket_volume() -> float:
    return math.sqrt(3.0) / 2.0 * SET_SCREW_SOCKET_AF**2 * SET_SCREW_SOCKET_DEPTH


async def _revolve_about_screw_axis(adapter, label: str, points, *, is_cut: bool):
    """Revolve a Front-plane profile about the set-screw axis (y = WIDTH/2)."""
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    x_hi = max(p[0] for p in points)
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(
                0.0, _SCREW_Y / 1000.0, 0.0, (x_hi + 1.0) / 1000.0, _SCREW_Y / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} {label}: CreateCenterLine failed")
        await add_line_chain(adapter, points)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, f"{label}Profile")
    check(
        f"revolve {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=is_cut)),
    )
    name_last_feature(adapter, label)


async def build_9414T1(adapter, truth=None, *, cup_radius: float = SET_SCREW_CUP_RADIUS):
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    c = EDGE_BREAK
    end_radius = cup_radius + (SET_SCREW_END_RADIUS - SET_SCREW_CUP_RADIUS)
    if not 0.0 < cup_radius <= SET_SCREW_CUP_RADIUS:
        raise ValueError(
            f"{PART_NO} set screw cup at {cup_radius} mm: it can only be "
            f"tightened in from the as-supplied {SET_SCREW_CUP_RADIUS} mm"
        )
    if end_radius <= _OUTER_R:
        raise ValueError(f"{PART_NO} set screw socket end sinks inside the collar OD")

    # --- ring section revolved about Y, four 45 deg breaks ------------------
    check("create_sketch ring", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, 0.0, 0.0, 0.0, WIDTH / 1000.0, 0.0) is None:
            raise RuntimeError(f"{PART_NO} ring: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (_BORE_R + c, 0.0),
                (_OUTER_R - c, 0.0),
                (_OUTER_R, c),
                (_OUTER_R, WIDTH - c),
                (_OUTER_R - c, WIDTH),
                (_BORE_R + c, WIDTH),
                (_BORE_R, WIDTH - c),
                (_BORE_R, c),
            ],
        )
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    check(
        "revolve ring",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Ring")
    v = ring_volume()
    v = await volume_check(adapter, "ring", v, 0.005 * v)

    # --- radial set-screw hole along +X at mid-width ------------------------
    x_end = _OUTER_R + HOLE_OVERRUN
    await _revolve_about_screw_axis(
        adapter,
        "SetScrewHole",
        [
            (0.0, _SCREW_Y),
            (0.0, _SCREW_Y + _SCREW_R),
            (x_end, _SCREW_Y + _SCREW_R),
            (x_end, _SCREW_Y),
        ],
        is_cut=True,
    )
    hole = hole_volume()
    v = await volume_check(adapter, "set-screw hole", v - hole, 0.01 * hole)

    # --- set screw as material: flat cup end to chamfered socket end --------
    ch = SET_SCREW_END_CHAMFER
    await _revolve_about_screw_axis(
        adapter,
        "SetScrew",
        [
            (cup_radius, _SCREW_Y),
            (cup_radius, _SCREW_Y + _SCREW_R),
            (end_radius - ch, _SCREW_Y + _SCREW_R),
            (end_radius, _SCREW_Y + _SCREW_R - ch),
            (end_radius, _SCREW_Y),
        ],
        is_cut=False,
    )
    # The screw lies wholly in the emptied hole, the bore or outside the ring,
    # so it adds its own volume exactly.
    screw = screw_volume()
    v = await volume_check(adapter, "set screw", v + screw, 0.005 * screw)

    # --- hex socket: blind cut in from the screw's outer end ----------------
    # Right Plane sketch: sketch x is model -Z, sketch y is model Y; the hex is
    # symmetric about sketch x = 0, so the sign of Z does not matter.  As in
    # 91251A108's socket, the default blind direction runs against the plane
    # normal, here -X into the screw.
    offset_plane(adapter, "SetScrewEndPlane", end_radius, base="Right Plane")
    check("create_sketch socket", await adapter.create_sketch("SetScrewEndPlane"))
    flat = SET_SCREW_SOCKET_AF / 2.0
    corner = _SOCKET_CORNER_R
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, _SCREW_Y + corner),
                (-flat, _SCREW_Y + corner / 2.0),
                (-flat, _SCREW_Y - corner / 2.0),
                (0.0, _SCREW_Y - corner),
                (flat, _SCREW_Y - corner / 2.0),
                (flat, _SCREW_Y + corner / 2.0),
            ],
        )
    check("exit_sketch socket", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "SocketProfile").Select2(False, 0)
    feat = fm.FeatureCut4(
        True, False, False,  # single, no flip, default dir
        0, 0, SET_SCREW_SOCKET_DEPTH / 1000.0, 0.0,  # blind to the floor
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False,
    )
    if feat is None:
        raise RuntimeError(f"{PART_NO} hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    await volume_check(
        adapter, "hex socket", v - socket_volume(), 0.01 * socket_volume()
    )


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
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
        await build_9414T1(adapter)
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
