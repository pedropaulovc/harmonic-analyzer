r"""McMaster 91251A108 -- black-oxide alloy steel socket head screw, #4-40 x 3/8".

Catalogue: the McMaster product page https://www.mcmaster.com/91251A108/
(read in a headless browser on 2026-09-29 for the MHA-140 hold-down): #4-40
UNC, class 3A, right hand, 3/8 in (9.525) under the head, fully threaded,
flat tip; standard socket head Ø0.183 in (4.6482) x 0.112 in (2.8448) high,
3/32 in hex drive; black-oxide alloy steel, 170 ksi, Rockwell C37, ASTM
A574; screw size decimal 0.112 in (2.8448).  Class 3A is not modelled
(nominal UN cutter).

The page gives no socket depth, so the socket takes ASME B18.3's minimum key
engagement for #4, 0.055 in (1.397).  The head is a plain cylinder: the
page gives no top chamfer or under-head fillet, and none is modelled.

Geometry: the 91255A148 socket-screw laws (``diag_build_91255A148.py``,
replica-gated against its vendor model) with a cylindrical head -- revolved
head and chamfered shank, a flat-floored hex socket cut blind down from the
head top, the body split at the bearing face so the thread sweep scopes to the
shank, a tip-seeded right-hand helix L + P high, the symmetric UN cutter 7P/16
past the tip, and a 45 deg neck cone from major + H/4 that re-merges the
bodies.  No 91251A108 vendor model is downloaded or committed, so this size
has no replica gate of its own.  Its standalone run is catalog-only: it builds
the recipe, checks the solid is sane and saves it under cad/out/reference for
inspection.

Frame: axis +Y, head up, bearing face (head underside) at y = 0.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91251A108.py
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

PART_NO = "91251A108"
IN = 25.4


@dataclass(frozen=True, slots=True)
class SocketHeadScrew:
    """Catalogue dimensions of one socket head cap screw, in mm."""

    part_no: str
    major_dia: float
    pitch: float
    length: float  # under the head
    head_dia: float
    head_h: float
    socket_af: float
    socket_depth: float

    @property
    def underside_y(self) -> float:
        """The bearing face sits on the origin."""
        return 0.0

    @property
    def top_y(self) -> float:
        return self.underside_y + self.head_h

    @property
    def tip_y(self) -> float:
        return self.underside_y - self.length

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
    def socket_corner_r(self) -> float:
        return self.socket_af / math.sqrt(3.0)

    @property
    def helix_revs(self) -> float:
        return self.length / self.pitch + 1.0


DIMS = SocketHeadScrew(
    part_no=PART_NO,
    major_dia=0.112 * IN,
    pitch=IN / 40.0,
    length=0.375 * IN,
    head_dia=0.183 * IN,
    head_h=0.112 * IN,
    socket_af=3.0 / 32.0 * IN,
    socket_depth=0.055 * IN,
)

if 2.0 * DIMS.socket_corner_r >= DIMS.head_dia:
    raise ValueError("91251A108 socket corners break out of the head")
if DIMS.socket_depth >= DIMS.head_h:
    raise ValueError("91251A108 socket floor falls through the head")


def revolved_volume(d: SocketHeadScrew = DIMS) -> float:
    major_r = d.major_dia / 2.0
    return (
        math.pi * (d.head_dia / 2.0) ** 2 * d.head_h
        + math.pi * major_r**2 * (d.length - d.tip_chamfer)
        + _rev_frustum(d.tip_chamfer, major_r, major_r - d.tip_chamfer)
    )


def socket_volume(d: SocketHeadScrew = DIMS) -> float:
    return math.sqrt(3.0) / 2.0 * d.socket_af**2 * d.socket_depth


async def build_91251A108(adapter, truth=None):
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    d = DIMS
    major_r = d.major_dia / 2.0
    head_r = d.head_dia / 2.0
    base = d.underside_y
    top = d.top_y
    tip = d.tip_y
    tip_ch = d.tip_chamfer

    # --- revolve profile: cylindrical head and chamfered shank -------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if sk_mgr.CreateCenterLine(0.0, top / 1000.0, 0.0, 0.0, tip / 1000.0, 0.0) is None:
            raise RuntimeError(f"{PART_NO} profile: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, top),
                (head_r, top),
                (head_r, base),
                (major_r, base),
                (major_r, tip + tip_ch),
                (major_r - tip_ch, tip),
                (0.0, tip),
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

    # --- hex socket: blind cut down from the head top (91255A148 idiom) ----
    offset_plane(adapter, "HeadTopPlane", top)
    check("create_sketch socket", await adapter.create_sketch("HeadTopPlane"))
    flat = d.socket_af / 2.0
    corner = d.socket_corner_r
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
        raise RuntimeError(f"{PART_NO} hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    await volume_check(
        adapter, "hex socket", v - socket_volume(), 0.01 * socket_volume()
    )

    # --- split at the bearing face (scopes the sweep) -----------------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < base - 1.0:  # extends below the bearing face
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{PART_NO} split produced no shank body")
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
            raise RuntimeError(f"{PART_NO} helix seed circle failed")
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
        if sk2.CreateCenterLine(0.0, base / 1000.0, 0.0, 0.0, (base - neck_h) / 1000.0, 0.0) is None:
            raise RuntimeError(f"{PART_NO} neck: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, base),
                (neck_r, base),
                (d.root_r, base - neck_h),
                (0.0, base - neck_h),
            ],
        )
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    check(
        "neck cone",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "ThreadNeck")


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
        await build_91251A108(adapter)
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
