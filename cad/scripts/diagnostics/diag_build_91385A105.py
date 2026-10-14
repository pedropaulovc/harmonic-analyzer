r"""McMaster 91385A105 -- thread-locking alloy steel cup-tip set screw, #4-40 x 3/16 (MHA-VN-061).

Catalogue-only: no vendor model has been harvested, so there is no pinned
VENDOR_* truth and no replica gate. The catalogue facts are
``_mcmaster_91385a105``'s (read live 2026-10-13): #4-40 UNC-3A, 3/16 in
(4.7625) long, black-oxide alloy steel, Rockwell C45, 0.050 in hex drive.
Class 3A is not modelled (nominal UN cutter), nor is the nylon patch.

Family assumption: this is the vendor-verified 91375A106 (#4-40 x 1/4)
1/16 in shorter. Every length-independent law is restated from
``diag_build_91375A106`` unchanged (a recipe may not import another recipe:
each stock build's cache closure holds its own recipe only): the socket-end
45 deg x 0.75P chamfer, the 45 deg x P cup-end chamfer, the cup rim and its
59 deg cone, the 1.778 deep 0.050 in hex, the 50 deg drill point, the 45 deg
countersink, and the UN cutter 7P/16 past the cup end. Only the length, and
with it the helix height (L + 1.01P), change.

Frame: axis +Y, origin mid-length, socket face at y = +L/2 and cup end at
y = -L/2; build_vn_pen_rod_set_screw lifts the cup end onto y = 0.

Run standalone (SolidWorks open); without a vendor file this is catalogue-only::

    uv run python cad\scripts\diagnostics\diag_build_91385A105.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _mcmaster_91385a105 import HEX_AF, LENGTH, MAJOR_DIA, PITCH  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _session import run_build  # noqa: E402
from _stock_recipe import stock_recipe  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    OUT_DIR,
    _rev_frustum,
    assert_seat_sketch_baseline,
    bodies,
    close_all,
    export_views,
    insert_helix,
    mass_properties,
    no_sketch_inference,
    offset_plane,
    thread_sweep_cut_modern,
)

HALF = LENGTH / 2.0  # LENGTH 4.7625, cup end to socket face
SOCKET_DEPTH = 0.070 * 25.4  # 1.778, the 91375A106 "Drive Depth"
SOCKET_CHAMFER = 0.75 * PITCH  # 45 deg
POINT_CHAMFER = PITCH  # 45 deg
CUP_HALF_ANGLE_DEG = 59.0
CUP_RIM_DIA = 2.0 * 0.747713
DRILL_HALF_ANGLE_DEG = 50.0
CSK_HALF_ANGLE_DEG = 45.0
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_DIA / 2.0 - 0.75 * H_SHARP
HELIX_REVS = LENGTH / PITCH + 1.01  # Length + 1.01 Pitch


def point_end_dia() -> float:
    """The cup end's diameter under the point chamfer."""
    return MAJOR_DIA - 2.0 * POINT_CHAMFER


def cup_depth() -> float:
    return CUP_RIM_DIA / 2.0 / math.tan(math.radians(CUP_HALF_ANGLE_DEG))


def hex_corner_r() -> float:
    return HEX_AF / math.sqrt(3.0)


def drill_point_depth() -> float:
    return HEX_AF / 2.0 / math.tan(math.radians(DRILL_HALF_ANGLE_DEG))


def socket_volume() -> float:
    return math.sqrt(3.0) / 2.0 * HEX_AF**2 * SOCKET_DEPTH


def drill_point_volume() -> float:
    return _rev_frustum(drill_point_depth(), HEX_AF / 2.0, 0.0)


def countersink_volume(steps: int = 2000) -> float:
    """The 45 deg cone's bite outside the hex (six slivers on the flats)."""
    rc = hex_corner_r()
    slope = math.tan(math.radians(CSK_HALF_ANGLE_DEG))
    half_af = HEX_AF / 2.0
    total = 0.0
    dphi = (math.pi / 6.0) / steps
    for i in range(steps):
        phi = (i + 0.5) * dphi  # 0..30 deg off a flat's normal
        rho = half_af / math.cos(phi)
        total += (rc * (rc**2 - rho**2) / 2.0 - (rc**3 - rho**3) / 3.0) * dphi
    return 12.0 * total / slope


def web_between_apexes() -> float:
    """Solid on the axis between the drill point's apex and the cup's."""
    return LENGTH - SOCKET_DEPTH - drill_point_depth() - cup_depth()


def revolved_volume() -> float:
    major_r = MAJOR_DIA / 2.0
    return (
        _rev_frustum(SOCKET_CHAMFER, major_r, major_r - SOCKET_CHAMFER)
        + math.pi * major_r**2 * (LENGTH - SOCKET_CHAMFER - POINT_CHAMFER)
        + _rev_frustum(POINT_CHAMFER, major_r, point_end_dia() / 2.0)
        - _rev_frustum(cup_depth(), CUP_RIM_DIA / 2.0, 0.0)
    )


if web_between_apexes() <= 0.0:
    raise ValueError("91385A105 socket drill point breaks into the cup")


@stock_recipe("91385A105", threaded=True)
async def build_91385A105(adapter, truth=None):
    from _com import _early_bound, _read_member
    from _feature_tree import _feature_by_name
    from _sketch import add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters

    major_r = MAJOR_DIA / 2.0
    face_r = major_r - SOCKET_CHAMFER
    cup_r = CUP_RIM_DIA / 2.0
    corner = hex_corner_r()
    flat = HEX_AF / 2.0

    # --- revolve profile (the 91375A106 Sketch2 + Revolve1 + Chamfer1) ------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, HALF / 1000.0, 0.0, 0.0, -HALF / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError("91385A105 profile: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, HALF),  # socket face on the axis
                (face_r, HALF),
                (major_r, HALF - SOCKET_CHAMFER),
                (major_r, -HALF + POINT_CHAMFER),
                (point_end_dia() / 2.0, -HALF),
                (cup_r, -HALF),
                (0.0, -HALF + cup_depth()),  # cup apex
            ],
        )
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check(
        "revolve body",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Body")
    v = revolved_volume()
    v = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- hex socket: blind cut down from the socket face ---------------------
    offset_plane(adapter, "SocketFacePlane", HALF)
    check("create_sketch socket", await adapter.create_sketch("SocketFacePlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, corner),
                (-flat, corner / 2.0),
                (-flat, -corner / 2.0),
                (0.0, -corner),
                (flat, -corner / 2.0),
                (flat, corner / 2.0),
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
        0, 0, SOCKET_DEPTH / 1000.0, 0.0,  # blind to the floor
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False,
    )  # fmt: skip
    if feat is None:
        raise RuntimeError("91385A105 hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    v = await volume_check(
        adapter, "hex socket", v - socket_volume(), 0.01 * socket_volume()
    )

    # --- drill point under the floor, from the hex's inscribed circle -------
    # The 91375A106 double cone: its widest circle is the floor's inscribed
    # circle, the upper cone shrinks inside the socket's air, the lower one is
    # the point, so no cut face lands on the floor plane or the hex walls.
    floor_y = HALF - SOCKET_DEPTH
    apex_y = floor_y - drill_point_depth()
    check("create_sketch drill point", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0,
                (floor_y + drill_point_depth()) / 1000.0,
                0.0,
                0.0,
                apex_y / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError("drill point: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, floor_y + drill_point_depth()),
                (flat, floor_y),
                (0.0, apex_y),
            ],
        )
    check("exit_sketch drill point", await adapter.exit_sketch())
    name_last_feature(adapter, "DrillPointProfile")
    check(
        "drill point",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "SocketDrillPoint")
    v = await volume_check(
        adapter, "socket drill point", v - drill_point_volume(), 0.02
    )

    # --- 45 deg countersink from the hex's corner circle ---------------------
    # Lifted into the air over the socket face (the 91255A148 idiom).
    lift = 0.05
    csk_slope = math.tan(math.radians(CSK_HALF_ANGLE_DEG))
    csk_apex_y = HALF - corner / csk_slope
    check("create_sketch countersink", await adapter.create_sketch("Front"))
    sk3 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk3.CreateCenterLine(
                0.0, (HALF + lift) / 1000.0, 0.0, 0.0, csk_apex_y / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("countersink: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, HALF + lift),
                (corner + lift * csk_slope, HALF + lift),
                (0.0, csk_apex_y),
            ],
        )
    check("exit_sketch countersink", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkProfile")
    check(
        "countersink",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "SocketCountersink")
    v = await volume_check(
        adapter, "socket countersink", v - countersink_volume(), 0.02
    )

    # --- helix: seeded on the cup end, L + 1.01P toward the socket -----------
    # The 91375A106 helix exactly: flags inverted for the +y seed plane, and
    # the pi/2 start that puts the sweep path on the Front-plane cutter.
    offset_plane(adapter, "CupEndPlane", -HALF)
    check("create_sketch helix seed", await adapter.create_sketch("CupEndPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("helix seed circle failed")
    insert_helix(
        adapter,
        PITCH,
        HELIX_REVS,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- thread groove: the symmetric cutter 7P/16 past the cup end ----------
    cy = -HALF - 7.0 * PITCH / 16.0
    crest_r = major_r + H_SHARP / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (crest_r, cy + 15.0 * PITCH / 32.0),
                (ROOT_R, cy + PITCH / 16.0),
                (ROOT_R, cy - PITCH / 16.0),
                (crest_r, cy - 15.0 * PITCH / 32.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    if len(bodies(adapter)) != 1:
        raise RuntimeError("91385A105: expected one body before the thread cut")
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix", "ThreadGroove")

    # Family assumption: the 91375A106 vendor frame (socket end +z).
    adapter._mcm_com_map = lambda c: [c[0], c[2], -c[1]]


async def build_catalog(adapter) -> dict[str, str]:
    """Build and save the catalogue recipe without claiming vendor equivalence."""
    with _telemetry.span("catalog.build", label="91385A105"):
        check("create_part 91385A105", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, "91385A105")
        await build_91385A105(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError("91385A105 catalogue build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / "91385A105-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, "91385A105-catalog"))
        _telemetry.success(
            f"91385A105 catalogue build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
