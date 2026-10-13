r"""Reproduction script: one-piece platen paper holder (book ch. 22, pp. 54-55).

One of the two bright brass holders hugging the platen front's extreme
left/right edges, running from the TOP edge down about 84 mm.  The reference
photos (ch22 img02 front, img03 close-up) show one slotted sheet: a flat screw
rail along the platen edge and a spring rail toward the paper, separated by
two narrow open-ended slits that stop either side of one intact middle bridge.
Each free half of the spring rail lifts off the platen in a smooth shallow bow
and comes back down to lie flat at its rounded paper-contact end.

The model is one merged brass body with no added end flange and no faceted
creases: the spring rail is a mid-plane thin extrusion of one tangent
line/arc path, so every bend is a smooth cylindrical band.  In plan, the
spring ends are full half-rounds, the screw rail's corners are rounded
(large on the outer edge, small at the slit), and each slit ends in a full
half-round at the bridge, as img03 shows.  The two slotted fillister heads sit
directly on the flat 0.8 mm sheet (img03: no raised seats); the platen's rear
socket bosses take the rest of the stock shank as thread
(pd_platen_spec.SOCKET_BOSS_H).

Used twice in pd-paper-drive.SLDASM.  Length is local +X, total width is local +Y,
and the flat rail's outward face is local z = 0.  The assembly turns the holder
-90 degrees about Z and places local z = SHEET_T against the platen.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_clip.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
from _appearance import apply_material
from _check import check
from _com import _early_bound, _read_member
from _dimensions import (
    _dim_value_mm,
    _display_dimensions,
    _rename_dimensions,
    drive_dimension,
    name_dimensions,
    set_global,
)
from _feature_tree import _feature_by_name, feature_name_by_type, name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _hole_spec import THREAD_MAJOR_MM
from _holes import CLEARANCE_MM, HoleSpec, wizard_holes
from vn_platen_clip_screw_spec import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
from pd_platen_spec import PLATE_THICKNESS, SOCKET_BOSS_H, SOCKET_THREAD_ENGAGEMENT

PART_NAME = "pd-platen-clip"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

CLIP_LENGTH = (
    83.5  # ch22 p.55 rear photo: 86.7 of the 140 mm plate (0.619) x PLATE_HEIGHT 134.82
)
CLIP_WIDTH = 8.988  # ch30-p002 Pose Studio: 10 * 0.8988
SHEET_T = 0.8  # photo-backed brass sheet thickness
CLIP_THICKNESS = SHEET_T  # assembly stand-off: one sheet, not a face stack

# ch22 img03 (one clip, 603 x 68 px of brass): the screw rail and the spring
# rail are each 32 px wide and the slit between them 4 px.
SCREW_RAIL_WIDTH = CLIP_WIDTH * 32.0 / 68.0
NOTCH_WIDTH = CLIP_WIDTH * 4.0 / 68.0
SPRING_RAIL_WIDTH = CLIP_WIDTH - SCREW_RAIL_WIDTH - NOTCH_WIDTH
SPRING_RAIL_Y0 = SCREW_RAIL_WIDTH + NOTCH_WIDTH
# img03: the slits stop 77 px apart on their centreline; with their full
# half-round ends (radius NOTCH_WIDTH / 2, 2 px) the tangent points sit
# 81 px apart.  The bridge length is that tangent-point span, which is also
# the spring rail's flat middle run.
CENTER_BRIDGE_LENGTH = CLIP_LENGTH * 81.0 / 603.0
SLIT_END_RADIUS = NOTCH_WIDTH / 2.0
BRIDGE_X0 = (CLIP_LENGTH - CENTER_BRIDGE_LENGTH) / 2.0
BRIDGE_X1 = BRIDGE_X0 + CENTER_BRIDGE_LENGTH
# img03 plan corners: the spring rail ends are full half-rounds; the screw
# rail's outer corners round at ~18 px (2.5 mm) and its slit-side corners at
# ~6 px (0.75 mm).
SPRING_END_RADIUS = SPRING_RAIL_WIDTH / 2.0
SCREW_RAIL_END_RADIUS = 2.5
SCREW_RAIL_SLIT_RADIUS = 0.75
ARCH_RISE = 1.5  # shallow outward bow; editable as ArchRise in Tools > Equations

# The brass #2-56 fillister screws (vn-platen-clip-screw; img03's heads read
# ~2.6-3.0 mm) retain their lengthwise stations in the flat rail, centred
# across it; each head lies wholly on the rail.
HOLE_INSET = 7.1904  # ch30-p002 Pose Studio: 8 * 0.8988 from each end
HOLE_Y = SCREW_RAIL_WIDTH / 2.0
CLEARANCE_SIZE = THREAD.split("-")[0]  # "#2"
HOLE_DIA = CLEARANCE_MM[(CLEARANCE_SIZE, "normal")]
HEAD_TO_SPRING_RAIL = SPRING_RAIL_Y0 - (HOLE_Y + HEAD_DIA / 2.0)
HEAD_RAIL_MARGIN = (SCREW_RAIL_WIDTH - HEAD_DIA) / 2.0

# Spring rail section (local X, Z) as its sheet MID-SURFACE: the free tip lies
# flat from its end-round centre out to the screw station, then each free half
# lifts in one smooth bow of three tangent arcs of equal radius (concave,
# convex crown, concave) and lies flat again over the middle bridge.  For a
# bow of run L and rise h, R = L^2 / (16 h) + h / 4 and each concave arc turns
# asin(L / 4R); the crown turns twice that.  Offsetting the mid-surface by
# SHEET_T / 2 keeps the same run and rise on both faces.
BOW_RUN = BRIDGE_X0 - HOLE_INSET
BEND_RADIUS = BOW_RUN**2 / (16.0 * ARCH_RISE) + ARCH_RISE / 4.0
BEND_ANGLE = math.asin(BOW_RUN / (4.0 * BEND_RADIUS))
TIP_FLAT_LENGTH = HOLE_INSET - SPRING_END_RADIUS
MID_SURFACE_LENGTH = (
    2.0 * TIP_FLAT_LENGTH + CENTER_BRIDGE_LENGTH + 2.0 * 4.0 * BEND_RADIUS * BEND_ANGLE
)

MODEL_FEATURES = (
    "FlatSheet",
    "SpringRail",
    "RoundedSpringEnds",
    "ScrewHoles",
)
BOSS_DRIVES = {
    "FlatSheet": ('"SheetT"',),
    "RoundedSpringEnds": ('"SheetT"',),
}
# The spring rail's thin extrusion carries three display dimensions, matched
# by their built value (all distinct): (name, value mm, driving expression).
SPRING_RAIL_DRIVES = (
    ("RailWidth", SPRING_RAIL_WIDTH, '"SpringRailW"'),
    ("StartOffset", SPRING_RAIL_Y0, '"SpringRailY0"'),
    ("WallT", SHEET_T, '"SheetT"'),
)
# Native equation self-test: each knob is flexed, rebuilt, checked against the
# analytic volume and z span, then restored.  NotchW is how SpringRailY0
# moves (it is the derived "ScrewRailW" + "NotchW"); widening the slit opens a
# gap at the bridge unless the spring rail's start offset follows.
EQUATION_FLEX = (
    ("SheetT", SHEET_T, 1.0, "sheet_t"),
    ("NotchW", NOTCH_WIDTH, 0.8, "notch_w"),
)
_CORNER_LOSS = (
    (1.0 - math.pi / 4.0) * 2.0 * (SCREW_RAIL_END_RADIUS**2 + SCREW_RAIL_SLIT_RADIUS**2)
)


def clip_volumes(
    sheet_t: float = SHEET_T, notch_w: float = NOTCH_WIDTH
) -> tuple[float, float, float, float]:
    """(flat sheet, spring rail, rounded ends, holes) volumes in mm^3.

    Parametric in the two knobs ``EQUATION_FLEX`` edits: the sheet thickness,
    and the slit width, which narrows the spring rail and its end rounds.
    """
    spring_w = CLIP_WIDTH - SCREW_RAIL_WIDTH - notch_w
    end_r = spring_w / 2.0
    # Plan area of the screw rail with its four rounded corners, plus the
    # bridge between the slits' half-round ends.
    flat = (
        CLIP_LENGTH * SCREW_RAIL_WIDTH
        - _CORNER_LOSS
        + CENTER_BRIDGE_LENGTH * notch_w
        - math.pi * (notch_w / 2.0) ** 2
    ) * sheet_t
    # A mid-plane thin wall's section area is exactly sheet_t x path length.
    path = (
        2.0 * (HOLE_INSET - end_r)
        + CENTER_BRIDGE_LENGTH
        + 2.0 * 4.0 * BEND_RADIUS * BEND_ANGLE
    )
    spring = path * sheet_t * spring_w
    # Each full end circle overlaps one half-circle of the flat tip run,
    # leaving exactly two outer half-circles of additional material.
    ends = math.pi * end_r**2 * sheet_t
    holes = 2.0 * math.pi * (HOLE_DIA / 2.0) ** 2 * sheet_t
    return flat, spring, ends, holes


V_FLAT_SHEET, V_SPRING_RAIL, V_ROUNDED_ENDS, V_HOLES = clip_volumes()
V_FINAL = V_FLAT_SHEET + V_SPRING_RAIL + V_ROUNDED_ENDS - V_HOLES

if not math.isclose(
    SCREW_RAIL_WIDTH + NOTCH_WIDTH + SPRING_RAIL_WIDTH,
    CLIP_WIDTH,
    abs_tol=1e-9,
):
    raise AssertionError("platen clip lane widths must close to ClipWidth")
if HOLE_Y - HOLE_DIA / 2.0 <= 0.0 or HOLE_Y + HOLE_DIA / 2.0 >= SCREW_RAIL_WIDTH:
    raise AssertionError(
        "platen clip screw holes must stay wholly inside the flat rail"
    )
if HEAD_TO_SPRING_RAIL <= 0.0:
    raise AssertionError("platen clip screw heads must clear the spring rail in plan")
if HEAD_RAIL_MARGIN <= 0.0:
    raise AssertionError("platen clip screw heads must lie wholly on the screw rail")
if HOLE_INSET - HEAD_DIA / 2.0 <= SCREW_RAIL_END_RADIUS:
    raise AssertionError("platen clip screw heads must sit clear of the rounded ends")
if SCREW_RAIL_END_RADIUS + SCREW_RAIL_SLIT_RADIUS >= SCREW_RAIL_WIDTH:
    raise AssertionError("screw rail corner rounds must leave a straight end")
if CENTER_BRIDGE_LENGTH <= 2.0 * SLIT_END_RADIUS:
    raise AssertionError("slit end rounds must leave an intact bridge")
# The end round must lie wholly on the flat tip, before the bow lifts.
if TIP_FLAT_LENGTH < SPRING_END_RADIUS or BOW_RUN <= 0.0 or ARCH_RISE <= 0.0:
    raise AssertionError(
        "platen clip spring bows need a flat tip, positive run and rise"
    )
if BEND_RADIUS <= SHEET_T / 2.0:
    raise AssertionError("platen clip bend radius must exceed half the sheet")
# Heads seat directly on the sheet: the shank's remainder is all thread.
if abs(CLIP_THICKNESS + SOCKET_THREAD_ENGAGEMENT - SHANK_LEN) > 1e-9:
    raise AssertionError("clip/platen stack no longer finishes at the screw tip")
if abs(SOCKET_THREAD_ENGAGEMENT - (PLATE_THICKNESS + SOCKET_BOSS_H)) > 1e-9:
    raise AssertionError("clip screw receiver no longer runs through plate and boss")
if SOCKET_THREAD_ENGAGEMENT + 1e-9 < 1.5 * THREAD_MAJOR_MM[THREAD]:
    raise AssertionError(
        f"clip {THREAD} engagement {SOCKET_THREAD_ENGAGEMENT:.4f} < 1.5D (drawing-guidelines.md rule 18 (thread engagement))"
    )
if HOLE_DIA < SHANK_DIA:
    raise AssertionError("stock fillister shank does not clear the clip")


def _bow_points(x0: float, s0: float) -> dict[str, tuple[float, float]]:
    """One bow's arc centres and joins in the Top sketch, (x, s = -Z)."""
    r, a = BEND_RADIUS, BEND_ANGLE
    x1 = x0 + BOW_RUN
    lift = s0 + r * (1.0 - math.cos(a))
    return {
        "c1": (x0, s0 + r),
        "p1": (x0 + r * math.sin(a), lift),
        "c2": (x0 + BOW_RUN / 2.0, s0 + ARCH_RISE - r),
        "p2": (x1 - r * math.sin(a), lift),
        "c3": (x1, s0 + r),
    }


async def _flat_sheet_outline(adapter) -> SketchDims:
    """Screw rail plus middle bridge in the open Front sketch, fully defined.

    Drawn counter-clockwise from the outer edge: rounded outer corners, the
    slit-side corners, then the bridge between the slits' half-round ends.
    add_arc runs counter-clockwise start -> end, so the two slit-end arcs
    (traversed clockwise by the outline) are entered end-first.
    """
    dims = SketchDims()
    length, rail = CLIP_LENGTH, SCREW_RAIL_WIDTH
    ro, ri, rs = SCREW_RAIL_END_RADIUS, SCREW_RAIL_SLIT_RADIUS, SLIT_END_RADIUS
    y0 = SPRING_RAIL_Y0
    set_sketch_direct_db(adapter, True)
    bottom = check("outer edge", await adapter.add_line(ro, 0.0, length - ro, 0.0))
    c_br = check(
        "outer far corner",
        await adapter.add_arc(length - ro, ro, length - ro, 0.0, length, ro),
    )
    right = check("far end", await adapter.add_line(length, ro, length, rail - ri))
    c_tr = check(
        "slit far corner",
        await adapter.add_arc(
            length - ri, rail - ri, length, rail - ri, length - ri, rail
        ),
    )
    top_r = check(
        "far slit edge", await adapter.add_line(length - ri, rail, BRIDGE_X1, rail)
    )
    slit_r = check(
        "far slit end",
        await adapter.add_arc(BRIDGE_X1, rail + rs, BRIDGE_X1, y0, BRIDGE_X1, rail),
    )
    bridge = check("bridge edge", await adapter.add_line(BRIDGE_X1, y0, BRIDGE_X0, y0))
    slit_l = check(
        "near slit end",
        await adapter.add_arc(BRIDGE_X0, rail + rs, BRIDGE_X0, rail, BRIDGE_X0, y0),
    )
    top_l = check("near slit edge", await adapter.add_line(BRIDGE_X0, rail, ri, rail))
    c_tl = check(
        "slit near corner",
        await adapter.add_arc(ri, rail - ri, ri, rail, 0.0, rail - ri),
    )
    left = check("near end", await adapter.add_line(0.0, rail - ri, 0.0, ro))
    c_bl = check("outer near corner", await adapter.add_arc(ro, ro, 0.0, ro, ro, 0.0))
    set_sketch_direct_db(adapter, False)

    for label, first, second, relation in (
        ("outer edge horizontal", bottom, None, "horizontal"),
        ("far slit edge horizontal", top_r, None, "horizontal"),
        ("bridge edge horizontal", bridge, None, "horizontal"),
        ("near slit edge horizontal", top_l, None, "horizontal"),
        ("far end vertical", right, None, "vertical"),
        ("near end vertical", left, None, "vertical"),
        ("outer far corner tangent edge", c_br, bottom, "tangent"),
        ("outer far corner tangent end", c_br, right, "tangent"),
        ("slit far corner tangent end", c_tr, right, "tangent"),
        ("slit far corner tangent slit", c_tr, top_r, "tangent"),
        ("far slit end tangent rail", slit_r, top_r, "tangent"),
        ("far slit end tangent bridge", slit_r, bridge, "tangent"),
        ("near slit end tangent bridge", slit_l, bridge, "tangent"),
        ("near slit end tangent rail", slit_l, top_l, "tangent"),
        ("slit near corner tangent slit", c_tl, top_l, "tangent"),
        ("slit near corner tangent end", c_tl, left, "tangent"),
        ("outer near corner tangent end", c_bl, left, "tangent"),
        ("outer near corner tangent edge", c_bl, bottom, "tangent"),
        ("slit edges one line", top_l, top_r, "collinear"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))

    await anchor_point_to_origin(
        adapter, f"{bottom}.start", ro, 0.0, "outer edge start"
    )
    dims.record("EdgeStartX", '"ScrewRailEndR"')
    check(
        "outer edge length",
        await adapter.add_sketch_dimension(bottom, None, "linear", length - 2.0 * ro),
    )
    dims.record("EdgeLength", '"ClipLength" - 2 * "ScrewRailEndR"')
    for name, arc, radius, expr in (
        ("EndR1", c_br, ro, '"ScrewRailEndR"'),
        ("EndR2", c_bl, ro, '"ScrewRailEndR"'),
        ("SlitCornerR1", c_tr, ri, '"ScrewRailSlitR"'),
        ("SlitCornerR2", c_tl, ri, '"ScrewRailSlitR"'),
    ):
        check(
            f"{name} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", radius),
        )
        dims.record(name, expr)
    await dimension_between(
        adapter,
        f"{bottom}.start",
        f"{top_r}.start",
        "vertical_distance",
        rail,
        "screw rail width",
    )
    dims.record("RailWidth", '"ScrewRailW"')
    await dimension_between(
        adapter,
        f"{top_r}.end",
        f"{bridge}.start",
        "vertical_distance",
        NOTCH_WIDTH,
        "slit width",
    )
    dims.record("SlitWidth", '"NotchW"')
    await dimension_between(
        adapter,
        "origin",
        f"{bridge}.end",
        "horizontal_distance",
        BRIDGE_X0,
        "bridge start",
    )
    dims.record("BridgeX0", '"BridgeX0"')
    check(
        "bridge length",
        await adapter.add_sketch_dimension(
            bridge, None, "linear", CENTER_BRIDGE_LENGTH
        ),
    )
    dims.record("BridgeLength", '"CenterBridgeL"')
    return dims


async def _spring_mid_surface(adapter) -> SketchDims:
    """The spring rail's mid-surface path in the open Top sketch, fully defined.

    Top-plane sketch (x, s) is part (X, -Z): the flats lie at s = -SHEET_T/2
    and the bows rise toward +s, away from the platen.  Drawn left to right,
    endpoints merged at creation (inference OFF); the convex crown arcs run
    counter-clockwise against the travel, so they are entered end-first.
    """
    dims = SketchDims()
    s0 = -SHEET_T / 2.0
    tip_x0 = SPRING_END_RADIUS
    tip_x1 = CLIP_LENGTH - SPRING_END_RADIUS
    near = _bow_points(HOLE_INSET, s0)
    far = _bow_points(BRIDGE_X1, s0)
    far_end = CLIP_LENGTH - HOLE_INSET
    set_sketch_direct_db(adapter, True)
    tip_l = check("near tip flat", await adapter.add_line(tip_x0, s0, HOLE_INSET, s0))
    a1 = check(
        "near lift",
        await adapter.add_arc(*near["c1"], HOLE_INSET, s0, *near["p1"]),
    )
    a2 = check(
        "near crown", await adapter.add_arc(*near["c2"], *near["p2"], *near["p1"])
    )
    a3 = check(
        "near return", await adapter.add_arc(*near["c3"], *near["p2"], BRIDGE_X0, s0)
    )
    mid = check("bridge flat", await adapter.add_line(BRIDGE_X0, s0, BRIDGE_X1, s0))
    a4 = check("far lift", await adapter.add_arc(*far["c1"], BRIDGE_X1, s0, *far["p1"]))
    a5 = check("far crown", await adapter.add_arc(*far["c2"], *far["p2"], *far["p1"]))
    a6 = check("far return", await adapter.add_arc(*far["c3"], *far["p2"], far_end, s0))
    tip_r = check("far tip flat", await adapter.add_line(far_end, s0, tip_x1, s0))
    set_sketch_direct_db(adapter, False)

    for label, first, second, relation in (
        ("near tip horizontal", tip_l, None, "horizontal"),
        ("bridge flat horizontal", mid, None, "horizontal"),
        ("far tip horizontal", tip_r, None, "horizontal"),
        ("near lift tangent tip", a1, tip_l, "tangent"),
        ("near crown tangent lift", a2, a1, "tangent"),
        ("near return tangent crown", a3, a2, "tangent"),
        ("near return tangent bridge", a3, mid, "tangent"),
        ("far lift tangent bridge", a4, mid, "tangent"),
        ("far crown tangent lift", a5, a4, "tangent"),
        ("far return tangent crown", a6, a5, "tangent"),
        ("far return tangent tip", a6, tip_r, "tangent"),
        ("bridge flat in the sheet plane", mid, tip_l, "collinear"),
        ("far tip in the sheet plane", tip_r, tip_l, "collinear"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))

    await anchor_point_to_origin(adapter, f"{tip_l}.start", tip_x0, s0, "tip start")
    dims.record("PathStartX", '"SpringEndR"')
    dims.record("PathStartZ", '"SheetT" / 2')
    check(
        "near tip flat length",
        await adapter.add_sketch_dimension(tip_l, None, "linear", TIP_FLAT_LENGTH),
    )
    dims.record("TipFlatL1", '"HoleInset" - "SpringEndR"')
    for index, arc in enumerate((a1, a2, a3, a4, a5, a6), start=1):
        check(
            f"bend {index} radius",
            await adapter.add_sketch_dimension(arc, None, "radial", BEND_RADIUS),
        )
        dims.record(f"BendR{index}", '"BendR"')
    await dimension_between(
        adapter,
        "origin",
        f"{mid}.start",
        "horizontal_distance",
        BRIDGE_X0,
        "near bow end",
    )
    dims.record("BridgeX0", '"BridgeX0"')
    check(
        "bridge flat length",
        await adapter.add_sketch_dimension(mid, None, "linear", CENTER_BRIDGE_LENGTH),
    )
    dims.record("BridgeLength", '"CenterBridgeL"')
    await dimension_between(
        adapter,
        "origin",
        f"{tip_r}.start",
        "horizontal_distance",
        far_end,
        "far bow end",
    )
    dims.record("FarBowEndX", '"HoleFarX"')
    check(
        "far tip flat length",
        await adapter.add_sketch_dimension(tip_r, None, "linear", TIP_FLAT_LENGTH),
    )
    dims.record("TipFlatL2", '"HoleInset" - "SpringEndR"')
    return dims


def _thin_extrude_at_offset(
    adapter, depth: float, offset: float, thickness: float
) -> str:
    """Mid-plane thin boss of the last exited open sketch, offset from its plane.

    The adapter's thin extrusion only starts at the sketch plane, and
    ``_extrude.extrude_at_offset`` makes solid bosses only, so this is the
    same raw ``FeatureExtrusion3``-style call on ``FeatureExtrusionThin2``
    with T0 = swStartOffset and the wall split evenly about the path
    (RevThinDir 2, mid-plane).  Millimetre arguments; returns the feature name.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("thin extrude: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"thin extrude: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusionThin2(
        True,  # Sd: single direction
        False,  # Flip (unused)
        False,  # Dir: along the sketch normal
        0,  # T1: swEndCondBlind
        0,  # T2
        depth / 1000.0,  # D1
        0.0,  # D2
        False,
        False,  # Dchk1/2
        False,
        False,  # Ddir1/2
        0.0,
        0.0,  # Dang1/2
        False,
        False,  # OffsetReverse1/2
        False,
        False,  # TranslateSurface1/2
        True,  # Merge
        thickness / 1000.0,  # Thk1: total wall for mid-plane
        0.0,  # Thk2 (two-direction only)
        0.0,  # EndThk
        2,  # RevThinDir: mid-plane
        0,  # CapEnds
        False,  # AddBends
        0.0,  # BendRad
        False,  # UseFeatScope
        True,  # UseAutoSelect
        3,  # T0: swStartOffset
        offset / 1000.0,  # StartOffset
        False,  # FlipStartOffset
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("thin extrude: FeatureExtrusionThin2 returned None")
    name = str(_read_member(feature, "Name"))
    _telemetry.success(f"thin extrude {sketch_name} @ +{offset:g} -> {name}")
    return name


def _z_extremes(adapter) -> tuple[float, float]:
    """(min, max) local Z (mm) of the part's single solid body.

    ``IBody2::GetExtremePoint`` is exact; the early-bound wrapper returns
    (ok, x, y, z) in metres.
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"platen clip: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    out = []
    for direction in ((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)):
        res = adapter._attempt(
            lambda d=direction: body.GetExtremePoint(*d), default=None
        )
        if not res or len(res) < 4:
            raise RuntimeError("platen clip: GetExtremePoint failed")
        out.append(float(res[3]) * 1000.0)
    return out[0], out[1]


def _check_z_span(adapter, label: str, sheet_t: float) -> None:
    """One body, platen face at SheetT, bow crests ArchRise outboard of z = 0."""
    z_min, z_max = _z_extremes(adapter)
    if abs(z_min + ARCH_RISE) > 0.01 or abs(z_max - sheet_t) > 0.01:
        raise RuntimeError(
            f"platen clip {label}: z span {z_min:.4f}..{z_max:.4f}, expected "
            f"{-ARCH_RISE:g}..{sheet_t:g}"
        )
    _telemetry.success(f"platen clip {label}: z span {z_min:.4f}..{z_max:.4f}")


def _name_spring_rail_dimensions(adapter) -> list[tuple[str, str]]:
    """Name the thin extrusion's width, start offset and wall; drive jobs.

    Each SPRING_RAIL_DRIVES value must match exactly one of the feature's own
    display dimensions, so a parameter SolidWorks does not expose fails the
    build with the full dimension list instead of staying silently literal.
    """
    feature = _feature_by_name(adapter, "SpringRail")
    dims = list(_display_dimensions(feature, "SpringRail"))
    values = [abs(_dim_value_mm(idim)) for idim in dims]
    names: list[str | None] = [None] * len(dims)
    for name, value, _expr in SPRING_RAIL_DRIVES:
        hits = [i for i, v in enumerate(values) if abs(v - value) < 1e-6]
        if len(hits) != 1:
            raise RuntimeError(
                f"SpringRail exposes {len(hits)} display dimensions of {name} "
                f"{value:.6f} mm (need exactly one); its dimensions read "
                f"{[round(v, 6) for v in values]}"
            )
        names[hits[0]] = name
    _rename_dimensions(dims, "SpringRail", names)
    return [(f"{name}@SpringRail", expr) for name, _value, expr in SPRING_RAIL_DRIVES]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing because
    # the template is IPS and bare equation-manager numbers are document units.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "SheetT", f"{SHEET_T}mm")
    await set_global(adapter, "ScrewRailW", f"{SCREW_RAIL_WIDTH}mm")
    await set_global(adapter, "NotchW", f"{NOTCH_WIDTH}mm")
    await set_global(adapter, "SpringRailW", '"ClipWidth" - "ScrewRailW" - "NotchW"')
    await set_global(adapter, "SpringRailY0", '"ScrewRailW" + "NotchW"')
    await set_global(adapter, "CenterBridgeL", f"{CENTER_BRIDGE_LENGTH}mm")
    await set_global(adapter, "BridgeX0", '("ClipLength" - "CenterBridgeL") / 2')
    await set_global(adapter, "SpringEndR", '"SpringRailW" / 2')
    await set_global(adapter, "ScrewRailEndR", f"{SCREW_RAIL_END_RADIUS}mm")
    await set_global(adapter, "ScrewRailSlitR", f"{SCREW_RAIL_SLIT_RADIUS}mm")
    await set_global(adapter, "HoleInset", f"{HOLE_INSET}mm")
    await set_global(adapter, "HoleY", '"ScrewRailW" / 2')
    await set_global(adapter, "HoleFarX", '"ClipLength" - "HoleInset"')
    await set_global(adapter, "ArchRise", f"{ARCH_RISE}mm")
    await set_global(adapter, "BowRun", '"BridgeX0" - "HoleInset"')
    await set_global(
        adapter, "BendR", '"BowRun" * "BowRun" / (16 * "ArchRise") + "ArchRise" / 4'
    )

    drive_jobs: list[tuple[str, str]] = []

    # Flat sheet: the screw rail (the only lane drilled for the two retaining
    # screws) and the middle bridge between the two slits' rounded ends.
    check("create_sketch flat sheet", await adapter.create_sketch("Front"))
    flat = await _flat_sheet_outline(adapter)
    await ensure_fully_defined(adapter, "flat sheet outline")
    check("exit_sketch flat sheet", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatSheetProfile")
    drive_jobs += flat.apply(adapter, "FlatSheetProfile")
    check(
        "extrude flat sheet",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "FlatSheet")
    flat_dims = name_dimensions(adapter, "FlatSheet", ["SheetDepth"])
    drive_jobs += [(flat_dims[0], BOSS_DRIVES["FlatSheet"][0])]
    volume = V_FLAT_SHEET
    await volume_check(adapter, "flat sheet", volume, 0.005 * volume)

    # Spring rail: one smooth mid-surface path thickened SheetT about itself
    # and swept SpringRailW across, starting SpringRailY0 off the Top plane.
    # Its flat middle run lands face-to-face on the bridge's slit-side edge.
    check("create_sketch spring rail", await adapter.create_sketch("Top"))
    path = await _spring_mid_surface(adapter)
    await ensure_fully_defined(adapter, "spring rail mid-surface")
    check("exit_sketch spring rail", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringRailPath")
    drive_jobs += path.apply(adapter, "SpringRailPath")
    _thin_extrude_at_offset(adapter, SPRING_RAIL_WIDTH, SPRING_RAIL_Y0, SHEET_T)
    name_last_feature(adapter, "SpringRail")
    drive_jobs += _name_spring_rail_dimensions(adapter)
    volume += V_SPRING_RAIL
    await volume_check(adapter, "flat sheet and spring rail", volume, 0.005 * volume)
    _check_z_span(adapter, "spring rail", SHEET_T)

    # Full circles overlap the flat tip run of the spring rail by one half
    # each.  Their exposed halves give both free ends a rounded planform.
    ends = SketchDims()
    check("create_sketch rounded spring ends", await adapter.create_sketch("Front"))
    spring_y = SPRING_RAIL_Y0 + SPRING_END_RADIUS
    define_jobs = (
        (
            SPRING_END_RADIUS,
            ("LeftEndX", "EndY", "LeftEndDia"),
            ('"SpringEndR"', '"SpringRailY0" + "SpringEndR"', '2 * "SpringEndR"'),
        ),
        (
            CLIP_LENGTH - SPRING_END_RADIUS,
            ("RightEndX", "RightEndY", "RightEndDia"),
            (
                '"ClipLength" - "SpringEndR"',
                '"SpringRailY0" + "SpringEndR"',
                '2 * "SpringEndR"',
            ),
        ),
    )
    for x, names, drives in define_jobs:
        await define_circle(
            adapter,
            x,
            spring_y,
            SPRING_END_RADIUS,
            "rounded spring end",
            dims=ends,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "rounded spring ends")
    check("exit_sketch rounded spring ends", await adapter.exit_sketch())
    name_last_feature(adapter, "SpringEndProfiles")
    drive_jobs += ends.apply(adapter, "SpringEndProfiles")
    check(
        "extrude rounded spring ends",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHEET_T)),
    )
    name_last_feature(adapter, "RoundedSpringEnds")
    end_dims = name_dimensions(adapter, "RoundedSpringEnds", ["SheetDepth"])
    drive_jobs += [(end_dims[0], BOSS_DRIVES["RoundedSpringEnds"][0])]
    volume += V_ROUNDED_ENDS
    await volume_check(adapter, "rounded spring ends", volume, 0.005 * volume)

    # End screw holes: ONE native Hole Wizard #2 clearance feature (2 points)
    # from the screw rail's outer face at local z = 0, where the heads seat.
    hole_cut = wizard_holes(
        adapter,
        HoleSpec("clearance", CLEARANCE_SIZE),
        [
            [HOLE_INSET, HOLE_Y, 0.0],
            [CLIP_LENGTH - HOLE_INSET, HOLE_Y, 0.0],
        ],
        (0.0, 0.0, -1.0),
        f"flat-rail screw holes ({CLEARANCE_SIZE} clearance)",
        name="ScrewHoles",
        placement_dims=[
            (("LeftX", '"HoleInset"'), ("LeftZ", '"HoleY"')),
            (("RightX", '"HoleFarX"'), ("RightZ", '"HoleY"')),
        ],
    )
    drive_jobs += hole_cut.placement_drive_jobs
    await volume_check(adapter, "one-piece clip", V_FINAL, 0.005 * V_FINAL)

    # Apply deferred equations after every target exists.  Their initial values
    # are neutral, so the second volume check also catches a mis-bound knob.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven one-piece clip (equations neutral)", V_FINAL, 0.005 * V_FINAL
    )
    # Equation self-test (EQUATION_FLEX): a knob that only reshapes part of
    # the sheet misses the analytic volume, opens a second body or moves the
    # z span; every knob is restored before the part is saved.
    for knob, neutral, flexed, knob_arg in EQUATION_FLEX:
        flat, spring, ends, holes = clip_volumes(**{knob_arg: flexed})
        expected = flat + spring + ends - holes
        await set_global(adapter, knob, f"{flexed}mm")
        await force_rebuild(adapter)
        await volume_check(adapter, f"{knob} = {flexed} mm", expected, 0.005 * expected)
        span_t = flexed if knob_arg == "sheet_t" else SHEET_T
        _check_z_span(adapter, f"{knob} = {flexed} mm", span_t)
        await set_global(adapter, knob, f"{neutral}mm")
        await force_rebuild(adapter)
        await volume_check(adapter, f"{knob} restored", V_FINAL, 0.005 * V_FINAL)
        _check_z_span(adapter, f"{knob} restored", SHEET_T)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
