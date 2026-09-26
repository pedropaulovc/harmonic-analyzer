r"""McMaster 91375A106 -- alloy steel cup-tip set screw, #4-40 x 1/4 (MHA-147).

Catalog: #4-40 UNC-3A, 1/4 in (6.35) long, black-oxide alloy steel, Rockwell
C45, 0.050 in hex drive, cup point.  Class 3A is not modelled (nominal UN
cutter).

Laws: measured from the vendor model, read by the read-only dump
``cad/out/reports/mcmaster-91375A106-dump.json`` (amet window 2026-09-26) of
``cad/references/mcmaster/91375A106.SLDPRT``, SHA-256
7f4cfb6c5bdd3053372667ac29a37b319392bff40cdc908f924424c8d8ebecd8.  The vendor
file is local-only (© McMaster, gitignored, never committed; see
cad/references/mcmaster/README.md).  Vendor truth, pinned below as
VENDOR_*: volume 25.8601 mm^3, area 95.038 mm^2, 28 faces.  Every value is the
vendor's own dimension or solved sketch geometry, in mm:

- body (their Sketch1/Sketch2 + Revolve1 + Chamfer1): major Ø2.8448 ("Screw
  Size Decimal Equivalent"), L 6.35.  Socket end: a flat face out to
  Ø1.8923, then a 45 deg x 0.75P (0.47625) chamfer to the major.  Cup end: a
  45 deg x P (0.635) chamfer (their Chamfer1, D1 = Pitch) down to Ø1.5748,
  a flat rim annulus, and the cup -- a 59 deg cone (their D5) from Ø1.495426
  at the end face to its apex 0.449271 inside.
- drive (their Cut-Extrude1/3/2): the 0.050 in hex, up to their Sketch1
  "Drive Depth" point 1.778 below the socket face; below its flat floor a
  drill-point cone from the hex's inscribed circle (their Sketch11, draft
  50 deg, so the cone's half-angle is 50 deg and its apex 0.5328 down),
  leaving six flat corner triangles of the floor; and a 45 deg countersink
  from the hex's corner circle (their Sketch4) that runs out on the flats.
  The replica revolves both cones as cuts (the 91255A148 idiom).
- thread (their Sketch7 + Helix/Spiral1 + Sketch8 + Cut-Sweep1): helix
  seeded on the cup-end face, L + 1.01P high (11.01 revs, start 0 deg),
  running out past the socket face; the symmetric UN cutter centred 7P/16
  past the cup end (root flat P/8 at the root radius 1.009955, top 15P/16 at
  major + H/16) -- the 91255A148 cutter.

Frame: axis +Y, origin mid-length, socket face at y = +L/2 and cup end at
y = -L/2.  The vendor's axis is z (socket +z), so replica (x, y, z) is vendor
(x, z, -y); build_arbor_set_screw lifts the cup end onto y = 0.

Run standalone (SolidWorks open, vendor file and dump local)::

    uv run python cad\scripts\diagnostics\diag_build_91375A106.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    bodies,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
    thread_sweep_cut_modern,
)

IN = 25.4
MAJOR_DIA = 0.112 * IN  # 2.8448
PITCH = IN / 40.0  # 0.635
LENGTH = 0.25 * IN  # 6.35, cup end to socket face
HALF = LENGTH / 2.0
HEX_AF = 0.050 * IN  # 1.27
SOCKET_DEPTH = 0.070 * IN  # 1.778, their "Drive Depth"
SOCKET_CHAMFER = 0.75 * PITCH  # 0.47625, 45 deg
POINT_CHAMFER = PITCH  # 0.635, 45 deg (their Chamfer1)
CUP_HALF_ANGLE_DEG = 59.0  # their D5
CUP_RIM_DIA = 2.0 * 0.747713  # their Sketch2 Line27 start
DRILL_HALF_ANGLE_DEG = 50.0  # their Cut-Extrude3 draft
CSK_HALF_ANGLE_DEG = 45.0  # their Cut-Extrude2 draft
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_DIA / 2.0 - 0.75 * H_SHARP  # 1.009955
HELIX_REVS = LENGTH / PITCH + 1.01  # their D3 = Length + 1.01 Pitch

# The vendor truth this replica is gated against (the 2026-09-26 harvest).
VENDOR_VOLUME_MM3 = 25.8601
VENDOR_SURFACE_MM2 = 95.038
VENDOR_FACE_COUNT = 28
VENDOR_COM_MM = (-0.000826, 0.002023, -0.158326)


def point_end_dia() -> float:
    """The cup end's diameter under the point chamfer."""
    return MAJOR_DIA - 2.0 * POINT_CHAMFER


def cup_depth() -> float:
    return CUP_RIM_DIA / 2.0 / math.tan(math.radians(CUP_HALF_ANGLE_DEG))


def hex_corner_r() -> float:
    return HEX_AF / math.sqrt(3.0)


def drill_point_depth() -> float:
    return HEX_AF / 2.0 / math.tan(math.radians(DRILL_HALF_ANGLE_DEG))


def revolved_volume() -> float:
    major_r = MAJOR_DIA / 2.0
    return (
        _rev_frustum(SOCKET_CHAMFER, major_r, major_r - SOCKET_CHAMFER)
        + math.pi * major_r**2 * (LENGTH - SOCKET_CHAMFER - POINT_CHAMFER)
        + _rev_frustum(POINT_CHAMFER, major_r, point_end_dia() / 2.0)
        - _rev_frustum(cup_depth(), CUP_RIM_DIA / 2.0, 0.0)
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


def _check_truth(truth: dict | None) -> None:
    """A harvest that is not the pinned one is a different vendor file."""
    if truth is None:
        return
    mass = truth["mass"]
    faces = sum(len(body.get("faces") or []) for body in truth.get("bodies") or [])
    if (
        abs(float(mass["volume_mm3"]) - VENDOR_VOLUME_MM3) > 1e-4
        or abs(float(mass["surface_area_mm2"]) - VENDOR_SURFACE_MM2) > 1e-3
        or faces != VENDOR_FACE_COUNT
    ):
        raise RuntimeError(
            "91375A106 harvest does not match the pinned vendor truth "
            f"(volume {mass['volume_mm3']}, surface {mass['surface_area_mm2']}, "
            f"{faces} faces)"
        )


if hex_corner_r() >= MAJOR_DIA / 2.0 - SOCKET_CHAMFER:
    raise ValueError("91375A106 hex corners break into the socket-end chamfer")
if abs(cup_depth() - (HALF - 2.725729)) > 1e-5:
    raise ValueError("91375A106 cup no longer matches the vendor's apex")
if ROOT_R <= hex_corner_r():
    raise ValueError("91375A106 thread root reaches the hex socket")


async def build_91375A106(adapter, truth=None):
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters

    _check_truth(truth)
    major_r = MAJOR_DIA / 2.0
    face_r = major_r - SOCKET_CHAMFER
    cup_r = CUP_RIM_DIA / 2.0
    corner = hex_corner_r()
    flat = HEX_AF / 2.0

    # --- revolve profile (their Sketch2 + Revolve1 + Chamfer1) --------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, HALF / 1000.0, 0.0, 0.0, -HALF / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError("91375A106 profile: CreateCenterLine failed")
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
        raise RuntimeError("91375A106 hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    v = await volume_check(
        adapter, "hex socket", v - socket_volume(), 0.01 * socket_volume()
    )

    # --- drill point under the floor, from the hex's inscribed circle -------
    # Their Cut-Extrude3 drafts BOTH ways from the floor plane, so its tool is
    # a double cone whose widest circle is the floor's inscribed circle: the
    # upper cone shrinks inside the socket's air, the lower one is the point.
    # Revolving that diamond keeps every cut face off the floor plane and off
    # the hex walls (a lifted cylinder would graze the flats).
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
    # Their seed plane faces -z with clockwise=True, reverse=True; ours faces
    # +y, so both flags invert (the 91255A148 / 93075A194 handedness proof).
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
        start_angle_rad=0.0,
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
        raise RuntimeError("91375A106: expected one body before the thread cut")
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix", "ThreadGroove")

    # Vendor (x, y, z) -> replica (x, z, -y): their socket end is +z.
    adapter._mcm_com_map = lambda c: [c[0], c[2], -c[1]]


if __name__ == "__main__":
    sys.exit(replica_main("91375A106", build_91375A106))
