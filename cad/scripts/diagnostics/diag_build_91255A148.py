r"""McMaster 91255A148 -- black-oxide alloy steel button head SHCS, #6-32 x 1/2".

Catalog: #6-32 UNC-3A, flat tip, head Ø0.262 in (6.65) x 0.073 in (1.85),
5/64 hex drive, 1/2 in (12.7) under the head, fully threaded (the McMaster
product page, supplied by the user on 2026-09-24).  Class 3A is not modelled
(nominal UN cutter).

Laws: measured from the vendor model (Main ruling (i), 2026-09-24), read by
the read-only dump ``cad/out/reports/mcmaster-91255A148-dump.json`` of
``cad/references/mcmaster/91255A148.SLDPRT``, SHA-256
4b8dac17c6b7e77499209a399342aa51780743b657aec0df7175f227b54e59a0.  The vendor
file is local-only (© McMaster, gitignored, never committed; see
cad/references/mcmaster/README.md).  Vendor truth: volume 130.7033 mm^3, area
291.3955 mm^2, 26 faces.  Every value below is the vendor's own dimension or
solved sketch geometry, in mm:

- head (their Sketch3 + Revolve1): a flat top Ø2.778125 (7/64, D1@Sketch2) at
  the full head height 1.8542; a spherical dome R3.941216, centred on the
  axis, from the flat top's edge down to the head OD Ø6.6548 at 0.27813 above
  the bearing face; below it a 10 deg band cone 0.27813 high (0.15 x head
  height) narrowing to Ø6.556716 at the bearing face.  Both band edges carry
  an R0.09271 fillet (their Fillet1, 0.05 x head height), so the flat bearing
  annulus ends at Ø6.401130.
- drive (their Cut-Extrude1 + Cut-Extrude2): 5/64 hex socket, flat floor
  1.01981 (0.55 x head height) below the flat top; the flat top covers the
  hex, so the key depth is 1.020 at the corners as well as the flats.  A 60 deg
  countersink (60 deg draft from the axis) from the hex's corner circle,
  Ø2.291358, breaks the corners; it runs out on the flats 0.0886 down.  The
  replica revolves that cone as a cut instead of drafting an extrude.
- shank and thread (Split1, Helix/Spiral1, Sketch7, Cut-Sweep1): major
  Ø3.5052 (0.138 in), 45 deg x 0.75P tip chamfer; helix seeded at the tip,
  L + P high (17 revs, start 90 deg), overrunning the bearing face by P into
  the split-off head, where the sweep's scope keeps it out; the symmetric UN
  cutter centred 7P/16 past the tip (root flat P/8 at the root radius
  1.237044, top 15P/16 at major + H/16).
- neck (Boss-Extrude1): a 45 deg cone from Ø3.677052 (major + H/4, the sharp
  V's crest line) at the bearing face, shrinking into the shank; it fills the
  last groove turns under the head and re-merges the split bodies.  It
  reaches the major 0.0859 below the bearing face and the root 0.6015 below.

Frame: head UP, bearing face at y = 0.  The vendor origin sits mid-overall
(axis z, head +z), so their bearing face is at z = (L - HH) / 2 = 5.4229.

Run standalone (SolidWorks open, vendor file and dump local)::

    uv run python cad\scripts\diagnostics\diag_build_91255A148.py
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
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

IN = 25.4
MAJOR_DIA = 0.138 * IN  # 3.5052, their "Screw Size Decimal Equivalent"
PITCH = IN / 32.0
LENGTH = 0.5 * IN  # under the head, fully threaded
HEAD_DIA = 0.262 * IN  # 6.6548
HEAD_H = 0.073 * IN  # 1.8542
HEX_AF = 5.0 / 64.0 * IN  # 1.984375
FLAT_TOP_DIA = 7.0 / 64.0 * IN  # 2.778125
DOME_R_MEASURED = 3.941216
BAND_H = 0.15 * HEAD_H  # 0.27813
BAND_DEG = 10.0
EDGE_FILLET_R = 0.05 * HEAD_H  # 0.09271
SOCKET_DEPTH = 0.55 * HEAD_H  # 1.01981, flat top to floor
CSK_DEG = 60.0  # draft from the axis
TIP_CHAMFER = 0.75 * PITCH  # 45 deg
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_DIA / 2.0 - 0.75 * H_SHARP  # 1.237044
NECK_DIA = MAJOR_DIA + H_SHARP / 4.0  # 3.677052
VENDOR_BEARING_Z = (LENGTH - HEAD_H) / 2.0  # 5.4229


def hex_corner_r() -> float:
    return HEX_AF / math.sqrt(3.0)


def bearing_edge_r() -> float:
    """Radius where the band cone meets the bearing face, before the fillet."""
    return HEAD_DIA / 2.0 - BAND_H * math.tan(math.radians(BAND_DEG))


def _fillet_setback(interior_deg: float) -> float:
    return EDGE_FILLET_R / math.tan(math.radians(interior_deg) / 2.0)


def _fillet_area(interior_deg: float) -> float:
    """Section area a fillet removes from a convex corner."""
    theta = math.radians(interior_deg)
    return EDGE_FILLET_R**2 * (1.0 / math.tan(theta / 2.0) - (math.pi - theta) / 2.0)


def bearing_face_dia() -> float:
    """Outer diameter of the flat bearing annulus: the band edge less the
    fillet's setback (the bearing corner is 90 + BAND_DEG inside)."""
    return 2.0 * (bearing_edge_r() - _fillet_setback(90.0 + BAND_DEG))


def dome_center_y() -> float:
    """The dome's centre on the axis, through the flat top's edge and the
    head OD at the band's top."""
    r1, y1 = FLAT_TOP_DIA / 2.0, HEAD_H
    r2, y2 = HEAD_DIA / 2.0, BAND_H
    return (r1**2 - r2**2 + y1**2 - y2**2) / (2.0 * (y1 - y2))


def dome_radius() -> float:
    return math.hypot(FLAT_TOP_DIA / 2.0, HEAD_H - dome_center_y())


def _rim_interior_deg() -> float:
    """Inside angle at the dome-to-band edge."""
    yc = dome_center_y()
    big_r = dome_radius()
    nx, ny = HEAD_DIA / 2.0 / big_r, (BAND_H - yc) / big_r
    up_dome = (-ny, nx)  # the dome's tangent, heading for the axis
    band = math.radians(BAND_DEG)
    down_band = (-math.sin(band), -math.cos(band))
    cos_t = up_dome[0] * down_band[0] + up_dome[1] * down_band[1]
    return math.degrees(math.acos(cos_t))


def revolved_volume() -> float:
    """The revolve before any cut: flat-topped dome zone, band cone, shank."""
    yc = dome_center_y()
    big_r = dome_radius()

    def zone(y: float) -> float:
        return big_r**2 * (y - yc) - (y - yc) ** 3 / 3.0

    major_r = MAJOR_DIA / 2.0
    return (
        math.pi * (zone(HEAD_H) - zone(BAND_H))
        + _rev_frustum(BAND_H, bearing_edge_r(), HEAD_DIA / 2.0)
        + math.pi * major_r**2 * (LENGTH - TIP_CHAMFER)
        + _rev_frustum(TIP_CHAMFER, major_r, major_r - TIP_CHAMFER)
    )


def socket_volume() -> float:
    return math.sqrt(3.0) / 2.0 * HEX_AF**2 * SOCKET_DEPTH


def countersink_volume(steps: int = 2000) -> float:
    """The 60 deg cone's bite outside the hex (six corner slivers)."""
    rc = hex_corner_r()
    slope = math.tan(math.radians(CSK_DEG))
    half_af = HEX_AF / 2.0
    total = 0.0
    dphi = (math.pi / 6.0) / steps
    for i in range(steps):
        phi = (i + 0.5) * dphi  # 0..30 deg off a flat's normal
        rho = half_af / math.cos(phi)
        total += (rc * (rc**2 - rho**2) / 2.0 - (rc**3 - rho**3) / 3.0) * dphi
    return 12.0 * total / slope


def edge_fillet_volume() -> float:
    """Both band-edge fillets by Pappus, each at its corner's radius."""
    return 2.0 * math.pi * (
        bearing_edge_r() * _fillet_area(90.0 + BAND_DEG)
        + HEAD_DIA / 2.0 * _fillet_area(_rim_interior_deg())
    )


def neck_reach() -> tuple[float, float]:
    """Depths below the bearing face where the 45 deg neck meets the major
    and the root."""
    neck_r = NECK_DIA / 2.0
    return neck_r - MAJOR_DIA / 2.0, neck_r - ROOT_R


if abs(dome_radius() - DOME_R_MEASURED) > 1e-5:
    raise ValueError("91255A148 dome no longer matches the vendor's R3.941216")
if FLAT_TOP_DIA <= 2.0 * hex_corner_r():
    raise ValueError("91255A148 flat top no longer covers the hex socket")
if HEAD_H - SOCKET_DEPTH <= BAND_H:
    raise ValueError("91255A148 socket floor falls into the head's band")


async def build_91255A148(adapter, truth=None):
    from _common import _feature_by_name, _early_bound, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    major_r = MAJOR_DIA / 2.0
    head_r = HEAD_DIA / 2.0
    top_r = FLAT_TOP_DIA / 2.0
    cap_r = dome_radius()
    yc = dome_center_y()
    tip_ch = TIP_CHAMFER
    revs = LENGTH / PITCH + 1.0

    # --- revolve profile (their Sketch3 + Revolve1) --------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, HEAD_H / 1000.0, 0.0, 0.0, -LENGTH / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError("button head profile: CreateCenterLine failed")
    # Three-point dome arc under no_sketch_inference: the fillister's proven
    # form (inference snapping and CreateArc's direction flag both misfire).
    ang_top = math.atan2(HEAD_H - yc, top_r)
    ang_rim = math.atan2(BAND_H - yc, head_r)
    ang_mid = (ang_top + ang_rim) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            top_r / 1000.0,
            HEAD_H / 1000.0,
            0.0,  # start: the flat top's edge
            head_r / 1000.0,
            BAND_H / 1000.0,
            0.0,  # end: head OD, top of the band
            cap_r * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + cap_r * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError("button head profile: dome arc failed")
        await add_line_chain(
            adapter,
            [
                (head_r, BAND_H),
                (bearing_edge_r(), 0.0),
                (major_r, 0.0),
                (major_r, -(LENGTH - tip_ch)),
                (major_r - tip_ch, -LENGTH),
                (0.0, -LENGTH),
                (0.0, HEAD_H),
                (top_r, HEAD_H),
            ],
            close=False,
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

    # --- hex socket: blind cut down from the flat top ------------------------
    # 92865A585's grade-mark idiom: a sketch on a Top-offset plane at the head
    # top, FeatureCut4 single-direction, default direction, blind -- proven to
    # cut down into the head.
    offset_plane(adapter, "HeadTopPlane", HEAD_H)
    check("create_sketch socket", await adapter.create_sketch("HeadTopPlane"))
    flat = HEX_AF / 2.0
    corner = hex_corner_r()
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
    )
    if feat is None:
        raise RuntimeError("hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    v = await volume_check(
        adapter, "hex socket", v - socket_volume(), 0.01 * socket_volume()
    )

    # --- 60 deg countersink from the hex's corner circle ---------------------
    # Their Cut-Extrude2 is a 60 deg drafted cut; a revolved cone removes the
    # same six corner slivers (inside the flats the socket is already air)
    # without a draft-direction flag, the 93075A194 crown-dish idiom.  The
    # check's 0.02 is a twentieth of the ~0.4 mm^3 a cone dished into the flat
    # top would take.
    slope = math.tan(math.radians(CSK_DEG))
    lift = 0.05
    apex_y = HEAD_H - corner / slope
    check("create_sketch countersink", await adapter.create_sketch("Front"))
    sk3 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk3.CreateCenterLine(
                0.0, (HEAD_H + lift) / 1000.0, 0.0, 0.0, apex_y / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("countersink: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, HEAD_H + lift),
                (corner + lift * slope, HEAD_H + lift),
                (0.0, apex_y),
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

    # --- R0.09271 on both band edges (their Fillet1) -------------------------
    check(
        "band fillets",
        await adapter.add_fillet(
            EDGE_FILLET_R,
            [[bearing_edge_r(), 0.0, 0.0], [head_r, BAND_H, 0.0]],
        ),
    )
    name_last_feature(adapter, "BandFillets")
    await volume_check(adapter, "band fillets", v - edge_fillet_volume(), 0.02)

    # --- split at the bearing face (scopes the sweep) -----------------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:  # extends below the bearing face
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix: tip-seeded, L + P up (90114A511's proven right hand) ---------
    # Their tip plane has normal -z with clockwise=True, reverse=True; ours is
    # +y, so both flags invert (93075A194 proved the handedness).
    offset_plane(adapter, "TipPlane", -LENGTH)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
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
        revs,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- thread groove: the symmetric cutter 7P/16 past the tip ------------
    cy = -LENGTH - 7.0 * PITCH / 16.0
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
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name, "ThreadGroove")

    # --- 45 deg neck cone (their Boss-Extrude1; re-merges the bodies) -------
    neck_r = NECK_DIA / 2.0
    neck_h = neck_reach()[1]
    check("create_sketch neck", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk2.CreateCenterLine(0.0, 0.0, 0.0, 0.0, -neck_h / 1000.0, 0.0) is None:
            raise RuntimeError("neck: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, 0.0),
                (neck_r, 0.0),
                (ROOT_R, -neck_h),
                (0.0, -neck_h),
            ],
        )
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    check(
        "neck cone",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "ThreadNeck")

    # Vendor frame: axis z, head +z, origin mid-overall.
    adapter._mcm_com_map = lambda v: [v[1], v[2] - VENDOR_BEARING_Z, v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("91255A148", build_91255A148))
