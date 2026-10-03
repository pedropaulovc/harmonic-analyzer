r"""McMaster 91255A106 -- black-oxide alloy steel button head SHCS, #4-40 x 1/4".

Catalogue: the McMaster product page https://www.mcmaster.com/91255A106/
(read in a headless browser on 2026-09-30 for the guide-lock screws, ruling
R9-31): #4-40 UNC, class 3A, right hand, 1/4 in (6.35) under the head, fully
threaded, flat tip; standard-profile button head Ø0.213 in (5.4102) x 0.059 in
(1.4986) high, 1/16 in hex drive; black-oxide alloy steel, 140 ksi, Rockwell
C39, ASME B18.3 and ASTM F835; screw size decimal 0.112 in (2.8448).  Class 3A
is not modelled (nominal UN cutter).

The page gives the thread, length, head Ø and height and the hex size, and
nothing else.  Every other value is the 91255A148 button-head law
(``diag_build_91255A148.py``, measured from its vendor model and
replica-gated) carried over in proportion [INFERENCE]: the flat top is 7/5 of
the hex across flats (7/64 over 5/64 there); the band is 0.15 of the head
height at 10 deg; both band edges take an R 0.05 x head height fillet; the
socket floor is 0.55 of the head height below the flat top; a 60 deg
countersink from the hex's corner circle breaks the corners.  The dome is the
sphere through the flat top's edge and the head OD at the band's top.

Shank and thread: the 91251A108 laws -- 45 deg x 0.75P tip chamfer, the body
split at the bearing face so the sweep scopes to the shank, a tip-seeded
right-hand helix L + P high, the symmetric UN cutter 7P/16 past the tip, and a
45 deg neck cone from major + H/4 that re-merges the bodies.

No 91255A106 vendor model is downloaded or committed, so this size has no
replica gate of its own; the native build is checked by the farm leaf.  Its
standalone run is catalog-only: it builds the recipe, checks the solid is sane
and saves it under cad/out/reference for inspection.

``build_button_head`` and ``catalog_run`` take the ``ButtonHeadScrew``
dimensions, so another length of the series reuses this recipe unchanged
(``diag_build_91255A108.py``, the 3/8 in screw MHA-VN-046 takes since R9-48).

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91255A106.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import check, name_last_feature, volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    thread_sweep_cut,
)

PART_NO = "91255A106"
IN = 25.4

# The 91255A148 vendor-measured proportions (see its module docstring).
FLAT_TOP_PER_HEX_AF = 7.0 / 5.0
BAND_PER_HEAD_H = 0.15
BAND_DEG = 10.0
FILLET_PER_HEAD_H = 0.05
SOCKET_PER_HEAD_H = 0.55
CSK_DEG = 60.0  # draft from the axis


@dataclass(frozen=True, slots=True)
class ButtonHeadScrew:
    """Catalogue dimensions of one button head socket cap screw, in mm."""

    part_no: str
    major_dia: float
    pitch: float
    length: float  # under the head
    head_dia: float
    head_h: float
    hex_af: float

    @property
    def flat_top_dia(self) -> float:
        return FLAT_TOP_PER_HEX_AF * self.hex_af

    @property
    def band_h(self) -> float:
        return BAND_PER_HEAD_H * self.head_h

    @property
    def edge_fillet_r(self) -> float:
        return FILLET_PER_HEAD_H * self.head_h

    @property
    def socket_depth(self) -> float:
        """Flat top to the socket floor."""
        return SOCKET_PER_HEAD_H * self.head_h

    @property
    def tip_chamfer(self) -> float:
        return 0.75 * self.pitch

    @property
    def h_sharp(self) -> float:
        return self.pitch * math.sqrt(3.0) / 2.0

    @property
    def root_r(self) -> float:
        return self.major_dia / 2.0 - 0.75 * self.h_sharp

    @property
    def neck_dia(self) -> float:
        return self.major_dia + self.h_sharp / 4.0

    @property
    def hex_corner_r(self) -> float:
        return self.hex_af / math.sqrt(3.0)

    @property
    def helix_revs(self) -> float:
        return self.length / self.pitch + 1.0

    @property
    def bearing_edge_r(self) -> float:
        """Radius where the band cone meets the bearing face, before the fillet."""
        return self.head_dia / 2.0 - self.band_h * math.tan(math.radians(BAND_DEG))

    @property
    def dome_center_y(self) -> float:
        """The dome's centre on the axis, through the flat top's edge and the
        head OD at the band's top."""
        r1, y1 = self.flat_top_dia / 2.0, self.head_h
        r2, y2 = self.head_dia / 2.0, self.band_h
        return (r1**2 - r2**2 + y1**2 - y2**2) / (2.0 * (y1 - y2))

    @property
    def dome_radius(self) -> float:
        return math.hypot(self.flat_top_dia / 2.0, self.head_h - self.dome_center_y)


DIMS = ButtonHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.25 * IN,
    head_dia=0.213 * IN,
    head_h=0.059 * IN,
    hex_af=1.0 / 16.0 * IN,
)

if DIMS.flat_top_dia <= 2.0 * DIMS.hex_corner_r:
    raise ValueError("91255A106 flat top no longer covers the hex socket")
if DIMS.head_h - DIMS.socket_depth <= DIMS.band_h:
    raise ValueError("91255A106 socket floor falls into the head's band")


def _fillet_setback(interior_deg: float, d: ButtonHeadScrew = DIMS) -> float:
    return d.edge_fillet_r / math.tan(math.radians(interior_deg) / 2.0)


def _fillet_area(interior_deg: float, d: ButtonHeadScrew = DIMS) -> float:
    """Section area a fillet removes from a convex corner."""
    theta = math.radians(interior_deg)
    return d.edge_fillet_r**2 * (1.0 / math.tan(theta / 2.0) - (math.pi - theta) / 2.0)


def bearing_face_dia(d: ButtonHeadScrew = DIMS) -> float:
    """Outer diameter of the flat bearing annulus: the band edge less the
    fillet's setback (the bearing corner is 90 + BAND_DEG inside)."""
    return 2.0 * (d.bearing_edge_r - _fillet_setback(90.0 + BAND_DEG, d))


def _rim_interior_deg(d: ButtonHeadScrew = DIMS) -> float:
    """Inside angle at the dome-to-band edge."""
    yc = d.dome_center_y
    big_r = d.dome_radius
    nx, ny = d.head_dia / 2.0 / big_r, (d.band_h - yc) / big_r
    up_dome = (-ny, nx)  # the dome's tangent, heading for the axis
    band = math.radians(BAND_DEG)
    down_band = (-math.sin(band), -math.cos(band))
    cos_t = up_dome[0] * down_band[0] + up_dome[1] * down_band[1]
    return math.degrees(math.acos(cos_t))


def revolved_volume(d: ButtonHeadScrew = DIMS) -> float:
    """The revolve before any cut: flat-topped dome zone, band cone, shank."""
    yc = d.dome_center_y
    big_r = d.dome_radius

    def zone(y: float) -> float:
        return big_r**2 * (y - yc) - (y - yc) ** 3 / 3.0

    major_r = d.major_dia / 2.0
    return (
        math.pi * (zone(d.head_h) - zone(d.band_h))
        + _rev_frustum(d.band_h, d.bearing_edge_r, d.head_dia / 2.0)
        + math.pi * major_r**2 * (d.length - d.tip_chamfer)
        + _rev_frustum(d.tip_chamfer, major_r, major_r - d.tip_chamfer)
    )


def socket_volume(d: ButtonHeadScrew = DIMS) -> float:
    return math.sqrt(3.0) / 2.0 * d.hex_af**2 * d.socket_depth


def countersink_volume(d: ButtonHeadScrew = DIMS, steps: int = 2000) -> float:
    """The 60 deg cone's bite outside the hex (six corner slivers)."""
    rc = d.hex_corner_r
    slope = math.tan(math.radians(CSK_DEG))
    half_af = d.hex_af / 2.0
    total = 0.0
    dphi = (math.pi / 6.0) / steps
    for i in range(steps):
        phi = (i + 0.5) * dphi  # 0..30 deg off a flat's normal
        rho = half_af / math.cos(phi)
        total += (rc * (rc**2 - rho**2) / 2.0 - (rc**3 - rho**3) / 3.0) * dphi
    return 12.0 * total / slope


def edge_fillet_volume(d: ButtonHeadScrew = DIMS) -> float:
    """Both band-edge fillets by Pappus, each at its corner's radius."""
    return 2.0 * math.pi * (
        d.bearing_edge_r * _fillet_area(90.0 + BAND_DEG, d)
        + d.head_dia / 2.0 * _fillet_area(_rim_interior_deg(d), d)
    )


async def build_button_head(adapter, d: ButtonHeadScrew = DIMS) -> None:
    """Build one button head screw of ``d``'s dimensions (the 91255A106 laws)."""
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    part_no = d.part_no
    major_r = d.major_dia / 2.0
    head_r = d.head_dia / 2.0
    top_r = d.flat_top_dia / 2.0
    cap_r = d.dome_radius
    yc = d.dome_center_y
    head_h = d.head_h
    band_h = d.band_h
    tip = -d.length
    tip_ch = d.tip_chamfer

    # --- revolve profile: dome, band, chamfered shank (91255A148 idiom) -----
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, head_h / 1000.0, 0.0, 0.0, tip / 1000.0, 0.0) is None:
            raise RuntimeError(f"{part_no} profile: CreateCenterLine failed")
    ang_top = math.atan2(head_h - yc, top_r)
    ang_rim = math.atan2(band_h - yc, head_r)
    ang_mid = (ang_top + ang_rim) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            top_r / 1000.0,
            head_h / 1000.0,
            0.0,  # start: the flat top's edge
            head_r / 1000.0,
            band_h / 1000.0,
            0.0,  # end: head OD, top of the band
            cap_r * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + cap_r * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError(f"{part_no} profile: dome arc failed")
        await add_line_chain(
            adapter,
            [
                (head_r, band_h),
                (d.bearing_edge_r, 0.0),
                (major_r, 0.0),
                (major_r, tip + tip_ch),
                (major_r - tip_ch, tip),
                (0.0, tip),
                (0.0, head_h),
                (top_r, head_h),
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
    v = revolved_volume(d)
    v = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- hex socket: blind cut down from the flat top -----------------------
    offset_plane(adapter, "HeadTopPlane", head_h)
    check("create_sketch socket", await adapter.create_sketch("HeadTopPlane"))
    flat = d.hex_af / 2.0
    corner = d.hex_corner_r
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
        0, 0, d.socket_depth / 1000.0, 0.0,  # blind to the floor
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False,
    )
    if feat is None:
        raise RuntimeError(f"{part_no} hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    v = await volume_check(
        adapter, "hex socket", v - socket_volume(d), 0.01 * socket_volume(d)
    )

    # --- 60 deg countersink from the hex's corner circle (revolved cut) -----
    slope = math.tan(math.radians(CSK_DEG))
    lift = 0.05
    apex_y = head_h - corner / slope
    check("create_sketch countersink", await adapter.create_sketch("Front"))
    sk3 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk3.CreateCenterLine(
                0.0, (head_h + lift) / 1000.0, 0.0, 0.0, apex_y / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} countersink: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, head_h + lift),
                (corner + lift * slope, head_h + lift),
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
        adapter, "socket countersink", v - countersink_volume(d), 0.02
    )

    # --- fillets on both band edges -----------------------------------------
    check(
        "band fillets",
        await adapter.add_fillet(
            d.edge_fillet_r,
            [[d.bearing_edge_r, 0.0, 0.0], [head_r, band_h, 0.0]],
        ),
    )
    name_last_feature(adapter, "BandFillets")
    await volume_check(adapter, "band fillets", v - edge_fillet_volume(d), 0.02)

    # --- split at the bearing face (scopes the sweep) -----------------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:  # extends below the bearing face
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{part_no} split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix: tip-seeded, L + P up, right hand ----------------------------
    offset_plane(adapter, "TipPlane", tip)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} helix seed circle failed")
    insert_helix(
        adapter,
        d.pitch,
        d.helix_revs,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- thread groove: the symmetric cutter 7P/16 past the tip ------------
    p = d.pitch
    cy = tip - 7.0 * p / 16.0
    crest_r = major_r + d.h_sharp / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (crest_r, cy + 15.0 * p / 32.0),
                (d.root_r, cy + p / 16.0),
                (d.root_r, cy - p / 16.0),
                (crest_r, cy - 15.0 * p / 32.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name, "ThreadGroove")

    # --- 45 deg neck cone: fills the last turns, re-merges the bodies -------
    neck_r = d.neck_dia / 2.0
    neck_h = neck_r - d.root_r
    check("create_sketch neck", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk2.CreateCenterLine(0.0, 0.0, 0.0, 0.0, -neck_h / 1000.0, 0.0) is None:
            raise RuntimeError(f"{part_no} neck: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, 0.0),
                (neck_r, 0.0),
                (d.root_r, -neck_h),
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


async def build_91255A106(adapter, truth=None):
    await build_button_head(adapter, DIMS)


async def catalog_run(adapter, d: ButtonHeadScrew, author) -> dict[str, str]:
    """Catalog-only run of ``author`` (the recipe for ``d``): build it and
    save it, no vendor truth."""
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    part_no = d.part_no
    with _telemetry.span("catalog.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await author(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{part_no} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{part_no}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{part_no}-catalog"))
        _telemetry.success(
            f"{part_no} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


async def build_catalog(adapter) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    return await catalog_run(adapter, DIMS, build_91255A106)


if __name__ == "__main__":
    from _common import run_build

    sys.exit(run_build(build_catalog))
