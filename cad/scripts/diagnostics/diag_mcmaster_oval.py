r"""Shared recipe for the McMaster 91790A* 18-8 stainless steel slotted 82 deg
oval head screws.

Live-page facts for https://www.mcmaster.com/91790A199/, read 2026-10-09:
18-8 stainless, slotted oval head, standard profile, nominal 82 deg,
head Ø.312 in, head height .152 in, oval top .052 in, #8-32 UNC class 2A,
fully threaded, ASME B18.6.3, 1in stock. Length is measured from the
TOP OF THE BEVEL, not crown or underhead. H/C/O in ASME 2013 Table 7
are reference dimensions; native construction is not a tolerance limit.

The underhead transition is the supplier STEP's (McMaster CAD chooser,
inspected out of tree; ``vn_transgear_arm_plate_screw_spec.SOURCE_STEP_SHA256``
and the measured face values it checks its formulas against):

- the 82 deg cone from the rim at y = 0 runs to its theoretical meeting with
  the thread major (``cone_depth``, 2.162 mm for the #8 head), where a fillet
  of radius ``fillet_r`` = thread start - ``cone_depth`` (0.3778 mm) rounds
  the corner onto a full-major neck;
- the neck ends, and the thread starts, at ``thread_start`` = H = .100 in
  below the bevel top (total head .152 in less crown .052 in): an annular step
  from the major to r = ``step_r`` (.077 in), then a ``start_half_angle``
  (60 deg from the axis) cone down to the groove root.

The page and the STEP leave the rest a construction, [INFERENCE]:

- crown = spherical cap (centre on the axis) of height ``crown_h`` above the
  top of the bevel through the Ø``head_dia`` rim, R = (r^2 + h^2) / (2h)
  (the STEP's sphere agrees);
- slot laws from the 90280A narrow fillister family
  (``diag_mcmaster_fillister.py``): width = HeadDia*0.135, depth =
  width*1.5 from the crown apex (the STEP's slot is .039 wide, .076 deep:
  kept as built, the sheet does not dimension it);
- thread laws from the fillister family (``diag_mcmaster_fillister.py``):
  tip chamfer 45 deg x 0.7P (the STEP's is 3P/8, likewise kept); helix seeded
  at the top of the bevel to P past the tip (revs = L/P + 1), the fillister's
  cutter (root flat at r = major - 0.75H) swept on the shank body only, after
  a split at the thread start; one revolved fill then restores the neck and
  the thread-start step and cone and re-merges the bodies before the fillet.

Class 2A is not modelled (nominal UN cutter).  Native/source qualification
is conditional on the printed incoming controls; it does not admit actual
bought screws or manufacture inspection readings.  There is no replica
gate: the standalone run is catalog-only (``catalog_run``), building the
recipe, checking the solid and saving it under cad/out/reference for inspection.

Frame: axis +Y, head UP, the top of the bevel at y = 0 (Top Plane); the
crown rises to y = crown_h, the factory tip is at y = -length.

Cut to fit (optional, ``cut_length`` with ``cut_end_break``): a screw cut
at assembly, as MHA-VN-040's are, is built as supplied and then trimmed by ONE
revolve-cut feature (``CUT_FEATURE``) that removes everything below
y = -cut_length and leaves a 45 deg break of radial leg ``cut_end_break``.
Suppressing that single feature restores the supplied screw, so a part can
carry the supplier stock as a native configuration.  The cut is read back
from the B-rep: the lowest point and the end face's rim radius.

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
from _com import _early_bound  # noqa: E402
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
    THREAD_START_CONE_HALF_ANGLE_DEG,
    THREAD_START_DEPTH,
    THREAD_START_STEP_R,
    UNDER_HEAD_FILLET_R,
)

OVAL_SIZES = {
    # part: (major dia, length from the top of the bevel, head dia at the top
    #        of the bevel, crown height, head angle deg, pitch)
    # #8-32 x 1 in, fully threaded, quantity 2; installed part cuts to the same fit.
    "91790A199": (
        THREAD_MAJOR,
        STOCK_LENGTH,
        HEAD_DIA,
        CROWN_H,
        HEAD_ANGLE_DEG,
        PITCH,
    ),
}

OVAL_TRANSITIONS = {
    # part: (thread start below the top of the bevel, cone-to-neck fillet
    #        radius, thread-start step radius, thread-start cone half-angle deg)
    # -- the supplier STEP's, checked against it in the spec.
    "91790A199": (
        THREAD_START_DEPTH,
        UNDER_HEAD_FILLET_R,
        THREAD_START_STEP_R,
        THREAD_START_CONE_HALF_ANGLE_DEG,
    ),
}

# The fillister-derived slot and tip laws ([INFERENCE] for an oval head).
SLOT_WIDTH_FRACTION = 0.135
SLOT_DEPTH_PER_WIDTH = 1.5
TIP_CHAMFER_PER_PITCH = 0.7

# The cut-to-fit trim, the one feature a supplier-stock configuration suppresses.
CUT_FEATURE = "CutToFit"
# How far the trim's cutter reaches past the major radius and the factory tip.
CUT_OVERRUN = 1.0
# B-rep readback tolerance on the cut's position and break (mm).
CUT_READBACK_TOL = 1e-4


def cone_depth(part_no: str) -> float:
    """Depth below the top of the bevel where the 82 deg cone, run on, meets
    the thread major diameter: the fillet's theoretical sharp corner."""
    major_d, _length, hd, _crown_h, angle, _pitch = OVAL_SIZES[part_no]
    return (hd - major_d) / 2.0 / math.tan(math.radians(angle / 2.0))


def root_radius(part_no: str) -> float:
    """The thread cutter's root flat: major - 0.75H (H the sharp-V height)."""
    major_d, _length, _hd, _crown_h, _angle, pitch = OVAL_SIZES[part_no]
    return major_d / 2.0 - 0.75 * pitch * math.sqrt(3.0) / 2.0


def thread_start_cone_end(part_no: str) -> float:
    """Depth below the top of the bevel where the thread-start cone reaches
    the groove root."""
    start, _fillet_r, step_r, half_angle = OVAL_TRANSITIONS[part_no]
    return start + (step_r - root_radius(part_no)) / math.tan(math.radians(half_angle))


def fillet_neck_tangent(part_no: str) -> float:
    """Depth below the top of the bevel where the cone-to-neck fillet meets
    the full-major neck: the corner plus R tan(deflection / 2), the cone's
    deflection from the axis being half the head angle."""
    _start, fillet_r, _step_r, _half = OVAL_TRANSITIONS[part_no]
    angle = OVAL_SIZES[part_no][4]
    return cone_depth(part_no) + fillet_r * math.tan(math.radians(angle / 4.0))


def slot_depth(part_no: str) -> float:
    """Driver slot depth from the crown apex."""
    return OVAL_SIZES[part_no][2] * SLOT_WIDTH_FRACTION * SLOT_DEPTH_PER_WIDTH


def check_cut(part_no: str, cut_length: float, cut_end_break: float) -> None:
    """Refuse a cut the trim cannot make: one that keeps the factory tip,
    leaves an unbroken end, or reaches the thread start under the head."""
    major_d, length, _hd, _crown_h, _angle, pitch = OVAL_SIZES[part_no]
    if not cut_length < length - TIP_CHAMFER_PER_PITCH * pitch:
        raise ValueError(
            f"{part_no}: a {cut_length} mm cut does not clear the supplied "
            f"{length} mm screw's factory tip"
        )
    if not 0.0 < cut_end_break < major_d / 2.0:
        raise ValueError(f"{part_no}: cut end break {cut_end_break} mm")
    if not thread_start_cone_end(part_no) < cut_length - cut_end_break:
        raise ValueError(f"{part_no}: the {cut_length} mm cut leaves no threaded shank")


def revolved_volume(part_no: str) -> float:
    """The supplied screw's revolved body before the slot and thread: crown,
    bevel cone to the theoretical corner, major shank, factory tip."""
    major_d, length, hd, crown_h, _angle, pitch = OVAL_SIZES[part_no]
    end_ch = TIP_CHAMFER_PER_PITCH * pitch
    major_r, head_r = major_d / 2.0, hd / 2.0
    bevel = cone_depth(part_no)
    return (
        _spherical_cap_volume(head_r, crown_h)
        + _rev_frustum(bevel, head_r, major_r)
        + math.pi * major_r**2 * (length - bevel - end_ch)
        + _rev_frustum(end_ch, major_r, major_r - end_ch)
    )


for _part_no, _row in OVAL_SIZES.items():
    _start, _fillet_r, _step_r, _half = OVAL_TRANSITIONS[_part_no]
    if not 0.0 < cone_depth(_part_no) < _row[1] - TIP_CHAMFER_PER_PITCH * _row[5]:
        raise ValueError(f"{_part_no}: the bevel leaves no threaded shank")
    if slot_depth(_part_no) >= _row[3] + cone_depth(_part_no):
        raise ValueError(f"{_part_no}: the driver slot falls through the oval head")
    if not (0.0 < _fillet_r and fillet_neck_tangent(_part_no) < _start):
        raise ValueError(f"{_part_no}: the underhead fillet overruns the neck")
    if not root_radius(_part_no) < _step_r < _row[0] / 2.0:
        raise ValueError(f"{_part_no}: the thread-start step is off the thread")
    if not 0.0 < _half < 90.0:
        raise ValueError(f"{_part_no}: thread-start cone half-angle {_half} deg")


def solid_body(adapter, label: str):
    """The part's one solid body: the split's head and shank must be merged."""
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = tuple(part.GetBodies2(0, False) or ())  # swSolidBody
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected one solid body, found {len(bodies)}")
    return _early_bound(bodies[0], "IBody2")


def lowest_y_mm(adapter, label: str) -> float:
    """The solid's lowest point along the screw axis (exact
    ``IBody2.GetExtremePoint``, see ``_part_checks.bbox_extent_check``), mm."""
    found = solid_body(adapter, label).GetExtremePoint(0.0, -1.0, 0.0)
    if not found or len(found) < 4 or not found[0]:
        raise RuntimeError(f"{label}: GetExtremePoint failed")
    return float(found[2]) * 1000.0


def end_rim_radius_mm(adapter, end_y_mm: float, label: str) -> float:
    """The outermost vertex radius of the one planar face whose vertices all
    lie at ``end_y_mm``: the cut end's rim inside its 45 deg break."""
    radii: list[float] = []
    faces = 0
    for raw_face in solid_body(adapter, label).GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        normal = tuple(float(v) for v in (face.Normal or ()))
        if len(normal) != 3 or abs(abs(normal[1]) - 1.0) > 1e-9:
            continue  # IFace2.Normal is (0, 0, 0) for a non-planar face
        points = []
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            for vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                if vertex is not None:
                    point = _early_bound(vertex, "IVertex").GetPoint()
                    points.append(tuple(float(v) * 1000.0 for v in point))
        if not points or any(abs(y - end_y_mm) > 1e-6 for _x, y, _z in points):
            continue
        faces += 1
        radii.extend(math.hypot(x, z) for x, _y, z in points)
    if faces != 1 or not radii:
        raise RuntimeError(f"{label}: expected one planar end face at y={end_y_mm}, found {faces}")
    return max(radii)


async def cut_to_fit(
    adapter, part_no: str, cut_length: float, cut_end_break: float
) -> None:
    """Trim the supplied screw to ``cut_length`` with a 45 deg end break, as
    one revolve cut (``CUT_FEATURE``), and read the cut back."""
    from _sketch import add_line_chain
    from solidworks_mcp.adapters.base import RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference

    check_cut(part_no, cut_length, cut_end_break)
    major_d, length, _hd, _crown_h, _angle, _pitch = OVAL_SIZES[part_no]
    major_r = major_d / 2.0
    rim_r = major_r - cut_end_break
    cut_y = -cut_length
    outer_r = major_r + CUT_OVERRUN
    bottom_y = -(length + CUT_OVERRUN)
    check("create_sketch cut to fit", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCenterLine(
                0.0, cut_y / 1000.0, 0.0, 0.0, bottom_y / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{part_no} cut to fit: CreateCenterLine failed")
        # The 45 deg break line runs on past the major radius, so the cutter
        # also clears everything outside it below the break.
        await add_line_chain(
            adapter,
            [
                (0.0, cut_y),
                (rim_r, cut_y),
                (outer_r, cut_y + (outer_r - rim_r)),
                (outer_r, bottom_y),
                (0.0, bottom_y),
            ],
        )
    check("exit_sketch cut to fit", await adapter.exit_sketch())
    name_last_feature(adapter, f"{CUT_FEATURE}Profile")
    check(
        "cut to fit",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, CUT_FEATURE)

    end_y = lowest_y_mm(adapter, f"{part_no} cut to fit")
    if abs(end_y - cut_y) > CUT_READBACK_TOL:
        raise RuntimeError(f"{part_no}: cut end at y={end_y}, expected {cut_y}")
    rim = end_rim_radius_mm(adapter, cut_y, f"{part_no} cut to fit")
    if abs(rim - rim_r) > CUT_READBACK_TOL:
        raise RuntimeError(f"{part_no}: cut-end rim radius {rim}, expected {rim_r}")
    _telemetry.success(
        f"{part_no} cut to fit: end y={end_y:.5f}, rim r={rim:.5f} "
        f"(break {major_r - rim:.5f})"
    )


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

    if (cut_length is None) != (cut_end_break is None):
        raise ValueError(f"{part_no}: a cut needs both its length and its end break")
    if cut_length is not None:
        check_cut(part_no, cut_length, cut_end_break)
    major_d, length, hd, crown_h, _angle, pitch = OVAL_SIZES[part_no]
    thread_start, fillet_r, step_r, start_half_angle = OVAL_TRANSITIONS[part_no]
    tip_ch = TIP_CHAMFER_PER_PITCH * pitch
    major_r = major_d / 2.0
    head_r = hd / 2.0
    junction_y = -cone_depth(part_no)
    start_y = -thread_start
    slot_w = hd * SLOT_WIDTH_FRACTION
    slot_d = slot_depth(part_no)
    root_r = root_radius(part_no)
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
                (major_r, -(length - tip_ch)),  # the factory tip
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

    # --- split at the thread start (scopes the sweep) -----------------------
    # The head body keeps the cone and the full-major neck down to the
    # supplier's thread start; only the shank body below it is threaded.
    offset_plane(adapter, "ThreadStart", start_y)
    body_boxes = split_at_plane(adapter, "ThreadStart", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < start_y - 1.0:  # extends below the thread start
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError(f"{part_no} split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix (top of the bevel -> P past the tip) -------------------------
    # Seeded on the Top Plane like the pan's; the turns above the thread start
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

    # --- thread start fill + underhead fillet (re-merges the bodies) --------
    # One revolved profile, the supplier STEP's thread start: the full-major
    # neck from the cone corner down to the thread start (inside the head
    # body), the annular step to ``step_r`` there, then the
    # ``start_half_angle`` cone down to the groove root, fully submerged.
    fill_end_y = -thread_start_cone_end(part_no)
    check("create_sketch thread start", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0,
                junction_y / 1000.0,
                0.0,
                0.0,
                fill_end_y / 1000.0,
                0.0,
            )
            is None
        ):
            raise RuntimeError(f"{part_no} thread start: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, junction_y),
                (major_r, junction_y),
                (major_r, start_y),
                (step_r, start_y),
                (root_r, fill_end_y),
                (0.0, fill_end_y),
            ],
        )
    check("exit_sketch thread start", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadStartProfile")
    check(
        "thread start fill",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "ThreadStartFill")

    check(
        "underhead fillet",
        await adapter.add_fillet(fillet_r, [[major_r, junction_y, 0.0]]),
    )
    name_last_feature(adapter, "UnderheadFillet")

    if cut_length is not None:
        await cut_to_fit(adapter, part_no, cut_length, cut_end_break)


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
