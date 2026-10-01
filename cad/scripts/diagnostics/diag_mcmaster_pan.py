r"""Shared recipe for the McMaster 90283A* zinc-plated steel slotted pan head
screws (catalog-only: no vendor model is downloaded or committed).

Live-page facts (``transgear-evidence/mcmaster-skus.md``, R4, verified
2026-09-30 on 90283A191/192; 90283A193 resolves in the same series, so its
row is [INFERENCE] from them): zinc-plated steel, slotted pan head Ø0.322 in
x 0.096 in high on every length, fully threaded, flat tip, 8-32 UNC class 2A.
The page gives only the head's diameter and height, so its SHAPE is
[INFERENCE], taken from the nearest replica-gated family, the 90280A narrow
fillister (``diag_mcmaster_fillister.py``), whose vendor laws are reused
unchanged:

- head cylinder band = HeadHeight*0.8; crown = spherical cap (centre on the
  axis) through the apex and the head rim;
- slot width = HeadDia*0.135, slot depth = width*1.5 (from the crown apex);
- tip chamfer = 45 deg x 0.7P; helix from the under-head junction to P past
  the tip (revs = L/P + 1); the fillister's cutter (root flat at
  r = major - 0.75H) swept on the shank body after a split at the junction;
- runout: major-diameter fill P/2 deep plus a 30-deg taper, junction fillet
  r = P/10 (re-merges the split bodies).

Class 2A is not modelled (nominal UN cutter).  There is no replica gate: the
standalone run is catalog-only (``catalog_run``), building the recipe,
checking the solid and saving it under cad/out/reference for inspection.

Frame: axis +Y, head UP, under-head bearing face at y = 0 (Top Plane).

Per-part entry points: ``diag_build_90283A*.py``.
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
    _spherical_cap_volume,
    insert_helix,
    thread_sweep_cut,
)
from transgear_knob_retaining_screw_spec import (  # noqa: E402
    HEAD_DIA,
    HEAD_H,
    PITCH,
    SHANK_DIA,
    SHANK_LEN,
)

PAN_SIZES = {
    # part:        (major dia, length under the head, head height, head dia, pitch)
    # 8-32 x 7/16, fully threaded (MHA-158, the transgear knob retaining screw).
    "90283A193": (SHANK_DIA, SHANK_LEN, HEAD_H, HEAD_DIA, PITCH),
}

# The fillister-derived head laws ([INFERENCE] for a pan head; see above).
HEAD_BAND_FRACTION = 0.8
SLOT_WIDTH_FRACTION = 0.135
SLOT_DEPTH_PER_WIDTH = 1.5
TIP_CHAMFER_PER_PITCH = 0.7


def head_band(part_no: str) -> float:
    """Height of the pan head's cylindrical band below its crown."""
    return PAN_SIZES[part_no][2] * HEAD_BAND_FRACTION


def slot_depth(part_no: str) -> float:
    """Driver slot depth from the crown apex."""
    return PAN_SIZES[part_no][3] * SLOT_WIDTH_FRACTION * SLOT_DEPTH_PER_WIDTH


def revolved_volume(part_no: str) -> float:
    """The revolved body before the slot and thread: crown, band, shank."""
    major_d, length, hh, hd, pitch = PAN_SIZES[part_no]
    major_r, head_r = major_d / 2.0, hd / 2.0
    band = head_band(part_no)
    tip_ch = TIP_CHAMFER_PER_PITCH * pitch
    return (
        _spherical_cap_volume(head_r, hh - band)
        + math.pi * head_r**2 * band
        + math.pi * major_r**2 * (length - tip_ch)
        + _rev_frustum(tip_ch, major_r, major_r - tip_ch)
    )


for _part_no in PAN_SIZES:
    if slot_depth(_part_no) >= PAN_SIZES[_part_no][2]:
        raise ValueError(f"{_part_no}: the driver slot falls through the pan head")


async def build_pan(adapter, part_no: str):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    major_d, length, hh, hd, pitch = PAN_SIZES[part_no]
    major_r = major_d / 2.0
    head_r = hd / 2.0
    band = head_band(part_no)
    crown_h = hh - band
    slot_w = hd * SLOT_WIDTH_FRACTION
    slot_d = slot_depth(part_no)
    tip_ch = TIP_CHAMFER_PER_PITCH * pitch
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    revs = length / pitch + 1.0
    apex_y = hh
    # Spherical-cap centre on the axis through the apex (0, apex_y) and the
    # rim (head_r, band):  R - crown_h = sqrt(R^2 - head_r^2).
    cap_R = (head_r**2 + crown_h**2) / (2.0 * crown_h)

    # --- revolve profile ----------------------------------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, hh / 1000.0, 0.0, 0.0, -length / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError(f"{part_no} profile: CreateCenterLine failed")
    # The crown as a THREE-POINT arc, as the fillister family learned: the
    # mid-point form pins the bulge side with no direction flag.
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0,
            apex_y / 1000.0,
            0.0,  # start: crown apex
            head_r / 1000.0,
            band / 1000.0,
            0.0,  # end: head rim
            cap_R * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + cap_R * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError(f"{part_no} profile: crown arc failed")
        await add_line_chain(
            adapter,
            [
                (head_r, band),
                (head_r, 0.0),
                (major_r, 0.0),
                (major_r, -(length - tip_ch)),
                (major_r - tip_ch, -length),
                (0.0, -length),
                (0.0, apex_y),
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
    v = revolved_volume(part_no)
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- driver slot (from the crown apex) ----------------------------------
    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (-slot_w / 2.0, apex_y + 0.5),
                (slot_w / 2.0, apex_y + 0.5),
                (slot_w / 2.0, apex_y - slot_d),
                (-slot_w / 2.0, apex_y - slot_d),
            ],
        )
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * hd, both_directions=True)
        ),
    )
    name_last_feature(adapter, "DriverSlot")

    # --- split at the under-head junction (scopes the sweep) ---------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:  # extends below the junction
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{part_no} split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix (junction -> P past the tip) ---------------------------------
    check("create_sketch helix seed", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        seed = adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0
        )
        if seed is None:
            raise RuntimeError(f"{part_no} helix seed circle failed")
    insert_helix(
        adapter,
        pitch,
        revs,
        clockwise=True,
        reversed_dir=True,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- thread groove -------------------------------------------------------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (root_r + (7.0 * pitch / 16.0) * math.sqrt(3.0), 15.0 * pitch / 16.0),
                (root_r + (13.0 * pitch / 32.0) * math.sqrt(3.0), -pitch / 32.0),
                (root_r, 3.0 * pitch / 8.0),
                (root_r, pitch / 2.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name, "ThreadGroove")

    # --- runout fill + taper + junction fillet (re-merges the bodies) -------
    check("create_sketch runout fill", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} runout fill circle failed")
    check("exit_sketch runout fill", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutFillProfile")
    check(
        "runout fill",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=pitch / 2.0, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "RunoutFill")

    # Taper as a revolved frustum (the adapter's extrusion never applies a
    # draft); its bottom disc sits at the thread root radius, fully submerged.
    taper_h = (major_r - root_r) * math.sqrt(3.0)  # 30 deg from the axis
    check("create_sketch runout taper", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0,
                -pitch / 2.0 / 1000.0,
                0.0,
                0.0,
                (-pitch / 2.0 - taper_h) / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError(f"{part_no} runout taper: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, -pitch / 2.0),
                (major_r, -pitch / 2.0),
                (root_r, -pitch / 2.0 - taper_h),
                (0.0, -pitch / 2.0 - taper_h),
            ],
        )
    check("exit_sketch runout taper", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutTaperProfile")
    check(
        "runout taper",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "RunoutTaper")

    check(
        "junction fillet", await adapter.add_fillet(pitch / 10.0, [[major_r, 0.0, 0.0]])
    )
    name_last_feature(adapter, "JunctionFillet")


async def catalog_run(adapter, part_no: str, builder) -> dict[str, str]:
    """Catalog-only run: build the recipe and save it, no vendor truth."""
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=part_no):
        check(f"create_part {part_no}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, part_no)
        await builder(adapter)
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
