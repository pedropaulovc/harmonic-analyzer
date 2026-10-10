r"""McMaster 91375A942 -- alloy steel cup-tip set screw, #1-72 x 5/32 (MHA-VN-055).

Catalogue-only: no vendor model has been harvested, so there is no pinned
VENDOR_* truth and no replica gate. Read live on 2026-10-09 (the public
#1-72 black-oxide cup-point family table and the part's 2-D PDF; the product
detail table is login-only):

- catalogue: #1-72 UNF, 5/32 in (3.96875) long, black-oxide alloy steel,
  Rockwell C45, 0.035 in hex drive; family facets Class 3A, ASME B18.3,
  ASTM F912, right hand. 2-D PDF: major 0.073 in, length 0.156 in, drive
  0.035 in. Class 3A is not modelled (nominal UN cutter).
- family assumptions (the 91375A106 vendor recipe's laws, scaled to the
  #1-72 pitch and the catalogue hex; not verified vendor geometry):
  socket-end 45 deg x 0.75P chamfer; a cup-end chamfer P long down to the
  ASME B18.3 #1 maximum cup diameter, 0.040 in (CUP_DIA); a flat cup rim
  annulus P/16 wide (91375A106: 0.7874 - 0.747713 = 0.635/16); a 59 deg
  cup cone from that rim to its apex; hex socket 1.4 x the drive size deep
  (91375A106: 0.070 in for the 0.050 in drive); a 50 deg drill point under
  the floor from the hex's inscribed circle; a 45 deg countersink from the
  hex's corner circle; the helix seeded on the cup end, L + 1.01P high; the
  symmetric UN cutter 7P/16 past the cup end (root flat P/8 at major - 0.75H,
  top 15P/16 at major + H/16); and the 91375A106 vendor-frame COM mapping.

Frame: axis +Y, origin mid-length, socket face at y = +L/2 and cup end at
y = -L/2; build_vn_fulcrum_set_screw lifts the cup end onto y = 0.

Run standalone (SolidWorks open); without a vendor file this is catalogue-only::

    uv run python cad\scripts\diagnostics\diag_build_91375A942.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    check,
    name_last_feature,
    run_build,
    volume_check,
)
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

IN = 25.4
# Catalogue (live 2026-10-09).
MAJOR_DIA = 0.073 * IN  # 1.8542, the 2-D PDF's 0.073in
PITCH = IN / 72.0  # 0.352778
LENGTH = 5.0 / 32.0 * IN  # 3.96875, cup end to socket face
HALF = LENGTH / 2.0
HEX_AF = 0.035 * IN  # 0.889
# Family assumptions (the 91375A106 laws).
SOCKET_DEPTH = 1.4 * HEX_AF  # 1.2446
SOCKET_CHAMFER = 0.75 * PITCH  # 0.264583, 45 deg
POINT_CHAMFER = PITCH  # 0.352778 long (the 91375A106's one-pitch point)
# Cup diameter: the 2-D PDF gives none, so the ASME B18.3 cup-point maximum
# for #1 (0.040 in). The 91375A106's 45 deg x P law would leave 0.045 in,
# over that maximum, so this chamfer runs ~50 deg off the axis instead.
CUP_DIA = 0.040 * IN  # 1.016
CUP_RIM_WIDTH = PITCH / 16.0  # the flat rim annulus
CUP_HALF_ANGLE_DEG = 59.0
DRILL_HALF_ANGLE_DEG = 50.0
CSK_HALF_ANGLE_DEG = 45.0
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_DIA / 2.0 - 0.75 * H_SHARP  # 0.697964
HELIX_REVS = LENGTH / PITCH + 1.01  # Length + 1.01 Pitch
# The 91375A106 recipe checks its small cuts to 0.02 mm^3; at this size the
# countersink is only 0.0039 mm^3, so half of that keeps a missing cut visible.
SMALL_CUT_TOL_MM3 = 0.002


def point_end_dia() -> float:
    """The cup end's diameter under the point chamfer."""
    return CUP_DIA


def cup_rim_dia() -> float:
    return point_end_dia() - 2.0 * CUP_RIM_WIDTH


def cup_depth() -> float:
    return cup_rim_dia() / 2.0 / math.tan(math.radians(CUP_HALF_ANGLE_DEG))


def hex_corner_r() -> float:
    return HEX_AF / math.sqrt(3.0)


def drill_point_depth() -> float:
    return HEX_AF / 2.0 / math.tan(math.radians(DRILL_HALF_ANGLE_DEG))


def web_between_apexes() -> float:
    """Solid on the axis between the drill point's apex and the cup's."""
    return LENGTH - SOCKET_DEPTH - drill_point_depth() - cup_depth()


def revolved_volume() -> float:
    major_r = MAJOR_DIA / 2.0
    return (
        _rev_frustum(SOCKET_CHAMFER, major_r, major_r - SOCKET_CHAMFER)
        + math.pi * major_r**2 * (LENGTH - SOCKET_CHAMFER - POINT_CHAMFER)
        + _rev_frustum(POINT_CHAMFER, major_r, point_end_dia() / 2.0)
        - _rev_frustum(cup_depth(), cup_rim_dia() / 2.0, 0.0)
    )


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


if hex_corner_r() >= MAJOR_DIA / 2.0 - SOCKET_CHAMFER:
    raise ValueError("91375A942 hex corners break into the socket-end chamfer")
if cup_rim_dia() <= 0.0:
    raise ValueError("91375A942 cup rim leaves no cup")
if web_between_apexes() <= 0.0:
    raise ValueError("91375A942 socket drill point breaks into the cup")
if ROOT_R <= hex_corner_r():
    raise ValueError("91375A942 thread root reaches the hex socket")


async def build_91375A942(adapter, truth=None):
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters

    major_r = MAJOR_DIA / 2.0
    face_r = major_r - SOCKET_CHAMFER
    cup_r = cup_rim_dia() / 2.0
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
            raise RuntimeError("91375A942 profile: CreateCenterLine failed")
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
        raise RuntimeError("91375A942 hex socket cut failed")
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
        adapter, "socket drill point", v - drill_point_volume(), SMALL_CUT_TOL_MM3
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
        adapter, "socket countersink", v - countersink_volume(), SMALL_CUT_TOL_MM3
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
        raise RuntimeError("91375A942: expected one body before the thread cut")
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix", "ThreadGroove")

    # Family assumption: the 91375A106 vendor frame (socket end +z).
    adapter._mcm_com_map = lambda c: [c[0], c[2], -c[1]]


async def build_catalog(adapter) -> dict[str, str]:
    """Build and save the catalogue recipe without claiming vendor equivalence."""
    with _telemetry.span("catalog.build", label="91375A942"):
        check("create_part 91375A942", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, "91375A942")
        await build_91375A942(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError("91375A942 catalogue build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / "91375A942-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, "91375A942-catalog"))
        _telemetry.success(
            f"91375A942 catalogue build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build_catalog))
