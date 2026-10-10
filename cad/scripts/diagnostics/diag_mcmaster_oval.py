r"""Shared recipe for the McMaster 91790A* 18-8 stainless steel slotted 82 deg
oval head screws (catalog-only: no vendor model is downloaded or committed).

Live-page facts for https://www.mcmaster.com/91790A199/, read2026-10-09:
18-8 stainless, slotted oval head, standard profile, nominal82deg,
headØ.312in, headheight.152in, ovaltop.052in, #8-32 UNC class2A,
fully threaded, ASME B18.6.3, 1in stock. Length is measured from the
TOP OF THE BEVEL, not crown or underhead. H/C/O in ASME2013 Table7
are reference dimensions; native construction is not a tolerance limit.

The page gives no slot dimensions, tip-chamfer or crown-radius figure, nor
dimensional tolerance bands.  The remaining shape laws are [INFERENCE]:

- crown = spherical cap (centre on the axis) of height ``crown_h`` above the
  top of the bevel through the Ø``head_dia`` rim, R = (r^2 + h^2) / (2h);
- bevel = the 82 deg cone from the rim at y = 0 down to where it meets the
  thread major diameter (``cone_depth``, 2.162 mm for the #8 head).  With
  the crown the modelled head is about 3.483 mm overall, independently
  derived from diameter, angle and crown, not forced from either published
  head-height value;
- slot laws from the 90280A narrow fillister family
  (``diag_mcmaster_fillister.py``): width = HeadDia*0.135, depth =
  width*1.5 from the crown apex;
- thread and runout laws from the fillister family
  (``diag_mcmaster_fillister.py``): tip chamfer 45 deg x 0.7P; helix seeded at the
  top of the bevel to P past the tip (revs = L/P + 1), the fillister's
  cutter (root flat at r = major - 0.75H) swept on the shank body only, after
  a split at the cone-to-shank junction, so the thread runs to under the
  head; runout at the junction: major-diameter fill P/2 deep plus a 30 deg
  taper (one revolved feature here, since the junction is below the Top
  Plane), junction fillet r = P/10.

Class 2A is not modelled (nominal UN cutter).  Native/source qualification
is conditional on the printed incoming controls; it does not admit actual
bought screws or manufacture inspection readings.  There is no replica
gate: the standalone run is catalog-only (``catalog_run``), building the
recipe, checking the solid and saving it under cad/out/reference for inspection.

Frame: axis +Y, head UP, the top of the bevel at y = 0 (Top Plane); the
crown rises to y = crown_h, the tip is at y = -length.

Cut to fit (optional, ``cut_length`` with ``cut_end_break``): a screw cut
at assembly, as MHA-VN-040's are, is drawn as installed.  The revolve profile
ends the shank at y = -cut_length with a 45 deg break of radial leg
``cut_end_break`` in place of the factory 0.7P tip chamfer; everything else
(head, slot, split, helix to P past the end, thread, runout) is the stock
build's, and ``revolved_volume`` follows the cut.  Without them the build is
the supplied screw at the row's length, which the catalog run builds.

Per-part entry points: ``diag_build_91790A*.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    _spherical_cap_volume,
    insert_helix,
    thread_sweep_cut,
)
from vn_transgear_arm_plate_screw_spec import (  # noqa: E402
    CROWN_H,
    HEAD_ANGLE_DEG,
    HEAD_DIA,
    PITCH,
    STOCK_LENGTH,
    THREAD_MAJOR,
)

OVAL_SIZES = {
    # part: (major dia, length from the top of the bevel, head dia at the top
    #        of the bevel, crown height, head angle deg, pitch)
    # #8-32 x1in, fully threaded, quantity2; installed part cuts to the same fit.
    "91790A199": (
        THREAD_MAJOR,
        STOCK_LENGTH,
        HEAD_DIA,
        CROWN_H,
        HEAD_ANGLE_DEG,
        PITCH,
    ),
}

# The fillister-derived slot and tip laws ([INFERENCE] for an oval head).
SLOT_WIDTH_FRACTION = 0.135
SLOT_DEPTH_PER_WIDTH = 1.5
TIP_CHAMFER_PER_PITCH = 0.7


def cone_depth(part_no: str) -> float:
    """Depth below the top of the bevel where the 82 deg cone meets the
    thread major diameter: the modelled bevel height."""
    major_d, _length, hd, _crown_h, angle, _pitch = OVAL_SIZES[part_no]
    return (hd - major_d) / 2.0 / math.tan(math.radians(angle / 2.0))


def slot_depth(part_no: str) -> float:
    """Driver slot depth from the crown apex."""
    return OVAL_SIZES[part_no][2] * SLOT_WIDTH_FRACTION * SLOT_DEPTH_PER_WIDTH


def shank_end(
    part_no: str,
    cut_length: float | None = None,
    cut_end_break: float | None = None,
) -> tuple[float, float]:
    """(length from the top of the bevel, 45 deg end chamfer leg): the
    supplied screw's factory tip, or the cut end of a screw cut to fit."""
    major_d, length, _hd, _crown_h, _angle, pitch = OVAL_SIZES[part_no]
    tip_ch = TIP_CHAMFER_PER_PITCH * pitch
    if cut_length is None and cut_end_break is None:
        return length, tip_ch
    if cut_length is None or cut_end_break is None:
        raise ValueError(f"{part_no}: a cut needs both its length and its end break")
    if not cut_length < length - tip_ch:
        raise ValueError(
            f"{part_no}: a {cut_length} mm cut does not clear the supplied "
            f"{length} mm screw's factory tip"
        )
    if not 0.0 < cut_end_break < major_d / 2.0:
        raise ValueError(f"{part_no}: cut end break {cut_end_break} mm")
    if not cone_depth(part_no) < cut_length - cut_end_break:
        raise ValueError(f"{part_no}: the {cut_length} mm cut leaves no shank")
    return cut_length, cut_end_break


def revolved_volume(
    part_no: str,
    cut_length: float | None = None,
    cut_end_break: float | None = None,
) -> float:
    """The revolved body before the slot and thread: crown, bevel, shank."""
    major_d, _length, hd, crown_h, _angle, _pitch = OVAL_SIZES[part_no]
    length, end_ch = shank_end(part_no, cut_length, cut_end_break)
    major_r, head_r = major_d / 2.0, hd / 2.0
    bevel = cone_depth(part_no)
    return (
        _spherical_cap_volume(head_r, crown_h)
        + _rev_frustum(bevel, head_r, major_r)
        + math.pi * major_r**2 * (length - bevel - end_ch)
        + _rev_frustum(end_ch, major_r, major_r - end_ch)
    )


for _part_no, _row in OVAL_SIZES.items():
    if not 0.0 < cone_depth(_part_no) < _row[1] - TIP_CHAMFER_PER_PITCH * _row[5]:
        raise ValueError(f"{_part_no}: the bevel leaves no threaded shank")
    if slot_depth(_part_no) >= _row[3] + cone_depth(_part_no):
        raise ValueError(f"{_part_no}: the driver slot falls through the oval head")


async def build_oval(
    adapter,
    part_no: str,
    *,
    cut_length: float | None = None,
    cut_end_break: float | None = None,
):
    from _sketch import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from diagnostics.diag_mcmaster_lib import (
        no_sketch_inference,
        offset_plane,
        split_at_plane,
    )

    major_d, _length, hd, crown_h, _angle, pitch = OVAL_SIZES[part_no]
    length, tip_ch = shank_end(part_no, cut_length, cut_end_break)
    major_r = major_d / 2.0
    head_r = hd / 2.0
    junction_y = -cone_depth(part_no)
    slot_w = hd * SLOT_WIDTH_FRACTION
    slot_d = slot_depth(part_no)
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    revs = length / pitch + 1.0
    apex_y = crown_h
    # Spherical-cap centre on the axis through the apex (0, crown_h) and the
    # rim (head_r, 0):  R - crown_h = sqrt(R^2 - head_r^2).
    cap_R = (head_r**2 + crown_h**2) / (2.0 * crown_h)

    # --- revolve profile ----------------------------------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(
                0.0, apex_y / 1000.0, 0.0, 0.0, -length / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} profile: CreateCenterLine failed")
    # The crown as a THREE-POINT arc, as the fillister family learned: the
    # mid-point form pins the bulge side with no direction flag.
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(0.0 - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0,
            apex_y / 1000.0,
            0.0,  # start: crown apex
            head_r / 1000.0,
            0.0,
            0.0,  # end: head rim, on the top of the bevel
            cap_R * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + cap_R * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError(f"{part_no} profile: crown arc failed")
        await add_line_chain(
            adapter,
            [
                (head_r, 0.0),
                (major_r, junction_y),  # the 82 deg bevel
                (major_r, -(length - tip_ch)),  # factory tip or cut-end break
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
    v = revolved_volume(part_no, cut_length, cut_end_break)
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

    # --- split at the cone-to-shank junction (scopes the sweep) -------------
    offset_plane(adapter, "HeadJunction", junction_y)
    body_boxes = split_at_plane(adapter, "HeadJunction", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < junction_y - 1.0:  # extends below the junction
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{part_no} split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix (top of the bevel -> P past the tip) -------------------------
    # Seeded on the Top Plane like the pan's; the turns above the junction
    # run through the head body, which the scoped sweep never touches.
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
    # One revolved profile: the major-diameter band P/2 below the junction,
    # then the 30 deg taper to the thread root, fully submerged.
    fill_y = junction_y - pitch / 2.0
    taper_h = (major_r - root_r) * math.sqrt(3.0)  # 30 deg from the axis
    check("create_sketch runout", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0,
                junction_y / 1000.0,
                0.0,
                0.0,
                (fill_y - taper_h) / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError(f"{part_no} runout: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, junction_y),
                (major_r, junction_y),
                (major_r, fill_y),
                (root_r, fill_y - taper_h),
                (0.0, fill_y - taper_h),
            ],
        )
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    check(
        "runout fill",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "RunoutFill")

    check(
        "junction fillet",
        await adapter.add_fillet(pitch / 10.0, [[major_r, junction_y, 0.0]]),
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
