r"""Shared recipe for the McMaster 91251A* black-oxide alloy steel socket head
cap screws.

Each size's catalogue facts live in its entry point (``diag_build_91251A*.py``)
as a ``SocketHeadScrew``.  No size of this family has a vendor model
downloaded or committed, so none has a replica gate: each standalone run is
catalog-only (``build_socket_head_catalog``) -- it builds the recipe, checks
the solid is sane and saves it under cad/out/reference for inspection.

Geometry: the 91255A148 socket-screw laws (``diag_build_91255A148.py``,
replica-gated against its vendor model) with a cylindrical head -- revolved
head and chamfered shank at the major, a flat-floored hex socket cut blind
down from the head top, the body split at the thread top so the thread sweep
scopes to the threaded body, a tip-seeded right-hand helix (threaded length +
P) high, the symmetric UN cutter 7P/16 past the tip, and a 45 deg cone at the
thread top that fills the last turns and re-merges the bodies.  The head is a
plain cylinder: the catalogue gives no top chamfer or under-head fillet.
Class 3A is not modelled (nominal UN cutter).

- Fully threaded (``thread_length`` None, e.g. 91251A108): the thread top is
  the bearing face, the split is the stock Top Plane and the cone starts at
  major + H/4 under the head (the 91255A148 neck).
- Partially threaded (``thread_length`` set, e.g. 91251A157): the thread top
  is ``thread_length`` up from the tip, on an offset ``ThreadTopPlane``; the
  shank above it stays plain at the major.  The split at the thread top, the
  helix of thread_length/P + 1 revs and the runout starting flush at the
  major are the replica-gated 91247A720 partial thread's
  (``diag_build_91247A720.py``); the runout itself stays this family's
  revolved 45 deg cone.  [UNVERIFIED-COM]: no partially threaded size of this
  recipe has been built on a SolidWorks seat yet.

Frame: axis +Y, head up, bearing face (head underside) at y = 0, tip at
y = -length.

The dimension record is pure data: module import pulls in no SolidWorks
call, so the screw specs read it.
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


@dataclass(frozen=True, slots=True)
class SocketHeadScrew:
    """Catalogue dimensions of one socket head cap screw, in mm.

    ``thread_length`` is the catalogue minimum thread length from the tip;
    None means fully threaded to the head.
    """

    part_no: str
    major_dia: float
    pitch: float
    length: float  # under the head
    head_dia: float
    head_h: float
    socket_af: float
    socket_depth: float
    thread_length: float | None = None

    def __post_init__(self) -> None:
        if 2.0 * self.socket_corner_r >= self.head_dia:
            raise ValueError(f"{self.part_no} socket corners break out of the head")
        if self.socket_depth >= self.head_h:
            raise ValueError(f"{self.part_no} socket floor falls through the head")
        if self.thread_length is not None and not (
            self.neck_h < self.thread_length < self.length
        ):
            raise ValueError(
                f"{self.part_no} thread length {self.thread_length} is not a"
                f" partial thread of the {self.length} shank"
            )

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
    def fully_threaded(self) -> bool:
        return self.thread_length is None

    @property
    def threaded_length(self) -> float:
        """Thread length from the tip: the whole shank when fully threaded."""
        return self.length if self.thread_length is None else self.thread_length

    @property
    def thread_top_y(self) -> float:
        """Where the thread ends: the bearing face when fully threaded."""
        return self.tip_y + self.threaded_length

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
        """The 45 deg cone's start at the thread top: the sharp V's crest line
        (major + H/4) under a head, the plain shank's major on a partial
        thread (no lip above the runout)."""
        if self.fully_threaded:
            return self.major_dia + self.h_sharp / 4.0
        return self.major_dia

    @property
    def neck_h(self) -> float:
        """Depth of the 45 deg cone below the thread top, to the root."""
        return self.neck_dia / 2.0 - self.root_r

    @property
    def socket_corner_r(self) -> float:
        return self.socket_af / math.sqrt(3.0)

    @property
    def helix_revs(self) -> float:
        return self.threaded_length / self.pitch + 1.0


def revolved_volume(d: SocketHeadScrew) -> float:
    major_r = d.major_dia / 2.0
    return (
        math.pi * (d.head_dia / 2.0) ** 2 * d.head_h
        + math.pi * major_r**2 * (d.length - d.tip_chamfer)
        + _rev_frustum(d.tip_chamfer, major_r, major_r - d.tip_chamfer)
    )


def socket_volume(d: SocketHeadScrew) -> float:
    return math.sqrt(3.0) / 2.0 * d.socket_af**2 * d.socket_depth


async def build_socket_head(adapter, d: SocketHeadScrew) -> None:
    from _common import _early_bound, _feature_by_name, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    part_no = d.part_no
    major_r = d.major_dia / 2.0
    head_r = d.head_dia / 2.0
    base = d.underside_y
    top = d.top_y
    tip = d.tip_y
    tip_ch = d.tip_chamfer
    thread_top = d.thread_top_y

    # --- revolve profile: cylindrical head and chamfered shank -------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, top / 1000.0, 0.0, 0.0, tip / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError(f"{part_no} profile: CreateCenterLine failed")
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
    v = revolved_volume(d)
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
    )  # fmt: skip
    if feat is None:
        raise RuntimeError(f"{part_no} hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    await volume_check(
        adapter, "hex socket", v - socket_volume(d), 0.01 * socket_volume(d)
    )

    # --- split at the thread top (scopes the sweep) -------------------------
    # Fully threaded: the bearing face (stock Top Plane).  Partially threaded:
    # an offset plane thread_length up from the tip, as 91247A720 splits its
    # thread top [UNVERIFIED-COM on this recipe].
    if d.fully_threaded:
        body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    else:
        offset_plane(adapter, "ThreadTopPlane", thread_top)
        body_boxes = split_at_plane(adapter, "ThreadTopPlane", "ThreadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < thread_top - 1.0:  # extends below the thread top
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{part_no} split produced no threaded body")
    _telemetry.info(f"threaded body: {shank_name}")

    # --- helix: tip-seeded, threaded length + P up, right hand -------------
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

    # --- 45 deg cone at the thread top: fills the last turns, re-merges ----
    neck_r = d.neck_dia / 2.0
    neck_h = d.neck_h
    check("create_sketch neck", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0, thread_top / 1000.0, 0.0, 0.0, (thread_top - neck_h) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} neck: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, thread_top),
                (neck_r, thread_top),
                (d.root_r, thread_top - neck_h),
                (0.0, thread_top - neck_h),
            ],
        )
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    check(
        "neck cone",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "ThreadNeck")


async def build_socket_head_catalog(adapter, d: SocketHeadScrew) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
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
        await build_socket_head(adapter, d)
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
