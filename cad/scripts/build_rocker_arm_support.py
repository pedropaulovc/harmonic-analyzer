r"""Reproduction script: rocker-arm support (manual feature-tree replay).

Feature-tree replay of ``rocker-arm-support.SLDPRT`` with stock-compatible
hold-down clearance holes: a thin-walled cast bracket with a trapezoidal wedge
wall (wide foot, narrow top) stood **Y-up**, lightened by a window that
opens on the two big front/back faces, with a mounting foot drilled for four
top-down hex-head screws, the window rim broken by a fillet + chamfer, and a
top rail tapped for the rocker pivot brackets' hold-down screws.

The part is oriented to match the source SLDPRT's standard views: the **Front**
view (along Z) looks square-on at the rounded window; the **Right** view (along
X) shows the trapezoid taper; the **Top** view (along Y) shows the two channels,
the central web, and the four foot holes.

The original is hand-built; this rebuilds it feature-for-feature, matching the
source's tree STRUCTURE and sketch construction but with SEMANTIC feature names
(the convention of the other tracked parts) rather than the source's generic
auto-names. The tree is Wall (``Boss-Extrude1``) -> CavityCut/WindowCut1/
WindowCut2 (``Cut-Extrude2/3/4``) -> CornerFillet (``Fillet3``) ->
PocketCornerFillet -> FootClearanceHoles (5/16 DRILL THRU, HoleWzd) ->
RimChamfer (``Chamfer2``) -> BracketSeats (#743, HoleWzd). The trapezoid lives
on the **Right plane** (sketch-x -> model Z taper, sketch-y -> model Y height,
mid-plane extrude along X); the window/cavity cuts use single rectangles on the
**Front plane** (matching the source's window/cavity sketches). The source
casting's per-stage ``volume_check`` targets were native SolidWorks
measurements; #743's deeper rail adds exact analytic deltas to them (see the
volume-target block), and the hole, chamfer and seat targets are analytic
expectations, all within the original 200 mm³ check tolerance.

Geometry (mm), source casting with the corrected top-down hold-down interface
(model frame: X = extrude/width, Y = height with the wide foot at Y=-88.9,
Z = wall thickness):

* **Wall** -- trapezoid, wide foot ``Z ±31.75`` at ``Y=-88.9`` tapering to
  ``Z ±8.4665`` at ``Y=+88.9``; mid-plane extrude 177.8 (``X ±88.9``).
* **CavityCut** -- 127 mm cavity square (``±63.5``), Through-All-Both -> the
  central cavity, leaving 6.35 mm shell walls (whole ``CavityProfile``).
* **WindowCut1 / WindowCut2** -- ONE shared window, 165.1 mm wide
  (``WindowProfile``, ``X ±82.55``, ``Y -82.55..+67.9``: the source's square
  with its top edge lowered so the top rail is 21.0 deep, #743). Each cut is a
  Through-All that STARTS ``WEB``
  (3.175) off the sketch plane in the opposite direction (forward / reverse, the
  second re-selecting ``WindowProfile`` -> a shared-sketch reference), so the
  2*WEB band between them survives as the central web -- the source's
  ``FromOffsetDistance`` / ``ReverseDirection`` pair, reproducing the
  two-sketches-feed-three-cuts tree.
* **CornerFillet** -- R12.7 on the four cavity corner edges.
* **PocketCornerFillet** -- R6.35 on the four corners of each opposed pocket.
* **FootClearanceHoles** -- a single Hole Wizard (``HoleWzd``) feature, 4x
  5/16 in clearance drills through the 6.35 mm foot from its top seat
  (Y=-82.55) at ``(X ±60.32, Z ±17.46)``. One feature carries all four
  placement points; the visible 1/4-20 hex-head screws install from the top
  into blind tapped seats in the harmonic base.
* **RimChamfer** -- 1.27 mm / 45° on the 12 inner-frame opening edges plus the
  two slant faces, the two trapezoid (±X) faces, and one fillet face, with
  tangent propagation -- i.e. the whole window rim.
* **BracketSeats** -- one Hole Wizard feature, 4x #8-32 bottoming-tapped seats
  down from the top face on the rail's centreline, under the MHA-123 pivot
  brackets' hold-down holes (``rocker_bracket_seat_layout`` owns their stack;
  the print transfers them from the set brackets at assembly).

Like the 71 tracked parts, this is **equation-driven and self-naming**: seven
equation-manager globals (``FootHalf``/``TopHalf``/``HalfHeight``/``CavHalf``/
``WindowOuter``/``RailDepth``/``WallWidth``, all ``mm``) drive every profile
sketch's dimensions (named e.g.
``WallHeight@WallProfile``, ``WinWidth@WindowProfile``), the sketches and
features carry stable names, and the drive equations are applied in one deferred
batch after a rebuild. A final "equations neutral" ``volume_check`` proves the
driving did not move the geometry, so a GUI edit to a global reshapes the part
and round-trips. See ``build_top_frame.py`` for the reference pattern.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rocker_arm_support.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_polygon_chain,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import blind_hole_volume_mm3, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _hole_spec import blind_cut_dia_mm
from _part_pmi import author_part_pmi
from rocker_arm_support_drawing_spec import SURFACE_FINISHES
from rocker_arm_support_spec import (
    FOOT_THICKNESS,
    HALF_Y,
    HOLE_DIA,
    HOLE_SPEC,
    NARROW,
    WIDE,
)
from rocker_bracket_seat_layout import (
    RAIL_DEPTH,
    SEAT_LOCAL_X,
    SEAT_SPEC,
    WINDOW_TOP_Y,
)

PART_NAME = "rocker-arm-support"
# The source repro was authored in steel, but this casting is now the machine's
# green rocker-arm-support (it replaced rocker-arm-portal): match the other cast
# structure (harmonic-base, top-frame) and the registry row (Gray Cast Iron,
# materials.yaml casting_green_parts) so it renders green, not steel-grey.
MATERIAL = "Gray Cast Iron"

# Trapezoid (Sketch1) -- wide foot / narrow top: WIDE / NARROW / HALF_Y are
# rocker_arm_support_spec's (pure data, so the base, frame and drive train
# read them without importing this COM script). On the Right plane: sketch-x
# -> model Z (taper), sketch-y -> model Y (height).
BOSS_DEPTH = 177.8  # mid-plane extrude along X (X ±88.9)

CAV = 63.5  # 127 mm square half (Cut-Extrude2)
# The window: 165.1 wide (X ±BIG), its bottom edge FOOT_THICKNESS over the foot
# face and its top edge RAIL_DEPTH under the top face (#743: the rail carries
# the rocker brackets' #8-32 seats, so it grew down into the window from the
# source's 6.35 -- the window is no longer square).
BIG = round(HALF_Y - FOOT_THICKNESS, 6)  # 82.55: the window's side and bottom half
WEB = 3.175  # window-cut start-offset; the 2*WEB band left as the web
# The cavity's top rim (chamfered on both web faces) must stay a web edge
# under the rail, not run into the pocket's top face: the 4.4 band keeps it.
if WINDOW_TOP_Y - CAV < 2.0:
    raise AssertionError("the deeper rail's underside reaches the cavity's top rim")

FILLET_R = 12.7
FILLET_EDGES = [  # four inner-frame corner edges (run along Z through the web)
    [63.5, 63.5, 0.0],
    [-63.5, 63.5, 0.0],
    [63.5, -63.5, 0.0],
    [-63.5, -63.5, 0.0],
]
POCKET_FILLET_R = 6.35


def _wall_half_z_at(y_mm: float) -> float:
    fraction = (y_mm + HALF_Y) / (2.0 * HALF_Y)
    return WIDE + (NARROW - WIDE) * fraction


POCKET_FILLET_EDGES = [
    [
        x_sign * BIG,
        window_y,
        face_sign * (WEB + _wall_half_z_at(window_y)) / 2.0,
    ]
    for x_sign in (-1, 1)
    for window_y in (-BIG, WINDOW_TOP_Y)
    for face_sign in (-1, 1)
]

# Volume targets. The source casting's (square window, 6.35 rail) are native
# SolidWorks measurements; the deeper rail's are those plus exact analytic
# deltas, so the first build re-proves them:
# * each window cut now stops at WINDOW_TOP_Y, leaving the band
#   WINDOW_TOP_Y..BIG across the 2*BIG window, from the web face out to the
#   tapered wall -- linear in y, so its mid-band depth integrates exactly;
# * the four top pocket-corner fillets move down to the new window top, where
#   the wall is thicker: each fillet's spandrel ((1 - pi/4) R^2) runs from the
#   web face to the wall at its centroid, which sits R (10 - 3 pi)/(12 - 3 pi)
#   inside the corner.
SQUARE_WINDOW_CUT1_VOLUME = 434_257
SQUARE_WINDOW_CUT2_VOLUME = 245_806
SQUARE_CORNER_FILLET_VOLUME = 246_685
SQUARE_POCKET_FILLET_VOLUME = 247_860
SQUARE_RIM_CHAMFER_REMOVAL = 3_153
RAIL_BAND_VOLUME = (
    2.0
    * BIG
    * (BIG - WINDOW_TOP_Y)
    * (_wall_half_z_at((BIG + WINDOW_TOP_Y) / 2.0) - WEB)
)
_SPANDREL_CENTROID = POCKET_FILLET_R * (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)
TOP_FILLET_SHIFT_VOLUME = (
    4.0
    * (1.0 - math.pi / 4.0)
    * POCKET_FILLET_R**2
    * (
        _wall_half_z_at(WINDOW_TOP_Y - _SPANDREL_CENTROID)
        - _wall_half_z_at(BIG - _SPANDREL_CENTROID)
    )
)
WINDOW_CUT1_VOLUME = SQUARE_WINDOW_CUT1_VOLUME + RAIL_BAND_VOLUME
WINDOW_CUT2_VOLUME = SQUARE_WINDOW_CUT2_VOLUME + 2.0 * RAIL_BAND_VOLUME
CORNER_FILLET_VOLUME = SQUARE_CORNER_FILLET_VOLUME + 2.0 * RAIL_BAND_VOLUME
POCKET_FILLET_VOLUME = (
    SQUARE_POCKET_FILLET_VOLUME + 2.0 * RAIL_BAND_VOLUME + TOP_FILLET_SHIFT_VOLUME
)

HOLES = [(60.32, 17.46), (-60.32, 17.46), (60.32, -17.46), (-60.32, -17.46)]

# The manufacturing print's dimension set (draw_rocker_arm_support.py imports
# exactly these marked dimensions; its keep maps must stay in lockstep).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "WallProfile": {"FootSpan", "TopSpan", "WallHeight"},
    "Wall": {"Depth"},
    # A single associative size plus an SQ callout defines each square.
    "WindowProfile": {"WinWidth"},
    "CavityProfile": {"CavWidth"},
    "CornerFillet": {"CavityRadius"},
    "PocketCornerFillet": {"PocketRadius"},
    "RimChamfer": {"RimChamferSize"},
}

# PocketCornerFillet volume minus four through clearance drills.
FOOT_HOLED_VOLUME = (
    POCKET_FILLET_VOLUME - len(HOLES) * math.pi / 4.0 * HOLE_DIA**2 * FOOT_THICKNESS
)

CHAMFER = 1.27  # leg, 45°
# The measured window-rim chamfer removal, less the four window side edges
# (two per slant face) the rail shortened: square to both faces, each lost
# millimetre removed CHAMFER^2 / 2. The rail's top edges keep their length.
RIM_CHAMFER_VOLUME = FOOT_HOLED_VOLUME - (
    SQUARE_RIM_CHAMFER_REMOVAL - 4.0 * (BIG - WINDOW_TOP_Y) * CHAMFER**2 / 2.0
)
# The rocker brackets' four bottoming-tapped seats, down from the top face on
# the rail's centreline (rocker_bracket_seat_layout owns their stack).
SEAT_POINTS = [[x, HALF_Y, 0.0] for x in SEAT_LOCAL_X]
BRACKET_SEATS_VOLUME = RIM_CHAMFER_VOLUME - len(SEAT_POINTS) * blind_hole_volume_mm3(
    blind_cut_dia_mm(SEAT_SPEC), SEAT_SPEC.depth_mm
)
CHAMFER_EDGES = [  # 12 inner-frame opening edges, both web faces (Z = ±WEB)
    [0.0, -63.5, -3.175],
    [63.5, 0.0, -3.175],
    [59.78, 59.78, -3.175],
    [0.0, 63.5, -3.175],
    [-63.5, 0.0, -3.175],
    [-59.78, -59.78, -3.175],
    [0.0, -63.5, 3.175],
    [-59.78, -59.78, 3.175],
    [-63.5, 0.0, 3.175],
    [-59.78, 59.78, 3.175],
    [0.0, 63.5, 3.175],
    [63.5, 0.0, 3.175],
]
CHAMFER_FACES = [  # whole faces whose every edge is chamfered (tangent-propagated)
    [0.0, -85.0, 31.24],
    [0.0, -85.0, -31.24],  # ±Z slant window surrounds
    [88.9, 0.0, 0.0],
    [-88.9, 0.0, 0.0],  # front / back trapezoid (±X) faces
    [59.78, -59.78, 0.0],  # one inner fillet face
]


def _add_construction_diagonals(adapter, half_mm: float) -> None:
    """Add the two corner-to-corner CONSTRUCTION diagonals that the center-
    rectangle tool draws, so a ``define_centered_rectangle`` square matches the
    source sketch's segment set (4 real sides + 2 construction diagonals).

    The diagonal endpoints sit on the square's existing corners (exact coords,
    so the suppressed-inference DB merges them onto the corner vertices); pinned
    to fully-defined corners, the diagonals add no DOF and the sketch stays
    fully defined.
    """
    sm = adapter.currentSketchManager
    sm = _early_bound(sm, "ISketchManager")
    h = half_mm / 1000.0
    prev = bool(sm.AddToDB)
    sm.AddToDB = True
    try:
        for (x1, y1), (x2, y2) in (((-h, -h), (h, h)), ((-h, h), (h, -h))):
            seg = sm.CreateLine(x1, y1, 0.0, x2, y2, 0.0)
            seg = _early_bound(seg, "ISketchSegment")
            seg.ConstructionGeometry = True
    finally:
        sm.AddToDB = prev


def _select_sketch(adapter, name: str) -> None:
    """Select a sketch by name for the next feature (shared-sketch friendly: a
    second select of an already-consumed sketch is how WindowCut2 reuses
    WindowProfile, which SolidWorks then shows as a ``<2>`` reference)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"select sketch {name!r} failed")


def _cut_through_all(
    adapter,
    sketch_name: str,
    *,
    both: bool,
    reverse_dir: bool,
    start_offset_mm: float = 0.0,
    flip_start: bool = False,
):
    """Through-all ``FeatureCut4`` on the named sketch.

    ``both`` -> Through-All-Both (the cavity). A single-direction cut with
    ``start_offset_mm`` reproduces the windows: each window cut shares one
    centered window square but STARTS ``start_offset_mm`` off the sketch plane
    (forward / reverse, opposite ``flip_start``), so the 2*offset band between
    them survives as the central web -- exactly the source's
    ``FromOffsetDistance``/``ReverseDirection`` pair.
    """
    model = adapter.currentModel
    model = _early_bound(model, "IModelDoc2")
    fm = model.FeatureManager
    fm = _early_bound(fm, "IFeatureManager")
    _select_sketch(adapter, sketch_name)

    through = adapter.constants.get("swEndCondThroughAll", 1)
    t0 = (
        adapter.constants.get("swStartOffset", 3)
        if start_offset_mm
        else adapter.constants.get("swStartSketchPlane", 0)
    )
    # 27-param FeatureCut4: T0/StartOffset/FlipStartOffset are the start-condition
    # tail (26-param is the SW-2025 form).
    args = (
        not both,
        False,
        reverse_dir,
        through,
        through,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        t0,
        start_offset_mm / 1000.0,
        flip_start,
        False,
    )
    feat = adapter._attempt(lambda: fm.FeatureCut4(*args), default=None)
    if not feat:
        feat = adapter._attempt(lambda: fm.FeatureCut4(*args[:-1]), default=None)
    model.ClearSelection2(True)
    if not feat:
        raise RuntimeError(f"FeatureCut4 on {sketch_name} failed")
    return feat


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: named equation-manager globals (mm) that drive every
    # profile sketch's dimensions, so a GUI edit to a global reshapes the part
    # and round-trips into the script (same self-naming treatment as the 71
    # tracked parts -- see build_top_frame.py). Lengths carry an explicit `mm`:
    # the part is modelled inch, and the equation manager evaluates bare numbers
    # in DOCUMENT units, so an unsuffixed global would be read as inches.
    await set_global(adapter, "FootHalf", f"{WIDE}mm")  # trapezoid foot half-width (Z)
    await set_global(adapter, "TopHalf", f"{NARROW}mm")  # trapezoid top half-width (Z)
    await set_global(adapter, "HalfHeight", f"{HALF_Y}mm")  # trapezoid half-height (Y)
    await set_global(adapter, "CavHalf", f"{CAV}mm")  # cavity square half
    await set_global(adapter, "WindowOuter", f"{BIG}mm")  # window side/bottom half
    await set_global(adapter, "RailDepth", f"{RAIL_DEPTH}mm")  # top face to window
    await set_global(
        adapter, "WallWidth", f"{BOSS_DEPTH}mm"
    )  # mid-plane extrude span (X)

    # Each sketch records its dim names + drive equations inline as it is drawn
    # (per-sketch SketchDims); the (dim@feature, expr) jobs are collected here and
    # applied in ONE deferred batch after the whole model + a rebuild exist, so
    # every equation target resolves. The neutrality volume_check at the end is
    # the proof that driving did not move the geometry.
    drive_jobs: list[tuple[str, str]] = []

    # 1. Boss: trapezoid on the Right plane (sketch-x -> model Z, sketch-y ->
    #    model Y, so the wide foot sits at Y=-88.9), mid-plane extruded 177.8
    #    along X. A polygon chain (two slanted sides) anchored at the foot's
    #    -Z corner; the six dims drive off FootHalf/TopHalf/HalfHeight.
    trap = SketchDims()
    check("sketch boss", await adapter.create_sketch("Right"))
    trap_pts = [(-WIDE, -HALF_Y), (WIDE, -HALF_Y), (NARROW, HALF_Y), (-NARROW, HALF_Y)]
    trap_lines = await add_line_chain(adapter, trap_pts)
    await define_polygon_chain(
        adapter,
        trap_lines,
        trap_pts,
        anchor=0,
        label="trapezoid",
        dims=trap,
        names=[
            "FootAnchorZ",
            "FootAnchorY",
            "FootSpan",
            "TaperRun",
            "WallHeight",
            "TopSpan",
        ],
        drives=[
            '"FootHalf"',
            '"HalfHeight"',
            '2 * "FootHalf"',
            '"FootHalf" - "TopHalf"',
            '2 * "HalfHeight"',
            '2 * "TopHalf"',
        ],
    )
    await ensure_fully_defined(adapter, "trapezoid")
    check("exit boss", await adapter.exit_sketch())
    name_last_feature(adapter, "WallProfile")
    drive_jobs += trap.apply(adapter, "WallProfile")
    check(
        "boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BOSS_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Wall")
    depth_dim = name_dimensions(adapter, "Wall", ["Depth"])
    drive_jobs += [(depth_dim[0], '"WallWidth"')]
    await volume_check(adapter, "Wall", 1_271_363, 200)

    # 2-4. Two sketches drive three cuts, exactly as the source tree does (only
    # the names are semantic here, not the source's Sketch11/Cut-ExtrudeN). Both
    # window/cavity sketches are single rectangles on the Front plane:
    #   * WindowProfile -- the 165.1 mm wide window, its top edge RailDepth under
    #     the top face (so NOT origin-centred: a rectilinear chain anchored at its
    #     top-left corner). WindowCut1 and WindowCut2 BOTH consume this ONE sketch
    #     (the second re-selects it -> a shared-sketch reference), each a
    #     Through-All cut that STARTS WEB (3.175) off the sketch plane in the
    #     opposite direction, so the 2*WEB band between them survives as the
    #     central web -- the source's FromOffsetDistance/ReverseDirection pair,
    #     not a sketch gap. Drives off WindowOuter/HalfHeight/RailDepth.
    #   * CavityProfile -- the 127 mm cavity square; CavityCut consumes it whole
    #     (Through-All-Both). Drives off CavHalf.
    # Built in the source's creation order (window profile, then cavity) and cut
    # in the source's order (cavity, then the two windows).
    windows = SketchDims()
    check("sketch windows", await adapter.create_sketch("Front"))
    window_pts = [
        (-BIG, WINDOW_TOP_Y),
        (BIG, WINDOW_TOP_Y),
        (BIG, -BIG),
        (-BIG, -BIG),
    ]
    window_lines = await add_line_chain(adapter, window_pts)
    await define_rectilinear_chain(
        adapter,
        window_lines,
        window_pts,
        anchor=0,
        label="window",
        dims=windows,
        names=["WinWidth", "WinHeight", "WinAnchorX", "WinAnchorY"],
        drives=[
            '2 * "WindowOuter"',
            '"HalfHeight" - "RailDepth" + "WindowOuter"',
            '"WindowOuter"',
            '"HalfHeight" - "RailDepth"',
        ],
    )
    await ensure_fully_defined(adapter, "window")
    check("exit windows", await adapter.exit_sketch())
    name_last_feature(adapter, "WindowProfile")
    drive_jobs += windows.apply(adapter, "WindowProfile")

    cavity = SketchDims()
    check("sketch cavity", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter,
        CAV,
        CAV,
        "cavity",
        dims=cavity,
        name_width="CavWidth",
        drive_width='2 * "CavHalf"',
        name_depth="CavDepth",
        drive_depth='2 * "CavHalf"',
    )
    await ensure_fully_defined(adapter, "cavity")
    check("exit cavity", await adapter.exit_sketch())
    name_last_feature(adapter, "CavityProfile")
    drive_jobs += cavity.apply(adapter, "CavityProfile")

    # CavityCut: cavity -- whole CavityProfile, Through-All-Both.
    _cut_through_all(adapter, "CavityProfile", both=True, reverse_dir=False)
    name_last_feature(adapter, "CavityCut")
    await volume_check(adapter, "CavityCut", 622_708, 200)

    # WindowCut1: one window -- Through-All forward, started WEB off-plane.
    _cut_through_all(
        adapter,
        "WindowProfile",
        both=False,
        reverse_dir=False,
        start_offset_mm=WEB,
        flip_start=True,
    )
    name_last_feature(adapter, "WindowCut1")
    await volume_check(adapter, "WindowCut1", WINDOW_CUT1_VOLUME, 200)

    # WindowCut2: the other window -- the SAME WindowProfile, Through-All reverse,
    # started WEB off-plane the other way (leaves the 2*WEB central web).
    _cut_through_all(
        adapter,
        "WindowProfile",
        both=False,
        reverse_dir=True,
        start_offset_mm=WEB,
        flip_start=False,
    )
    name_last_feature(adapter, "WindowCut2")
    await volume_check(adapter, "WindowCut2", WINDOW_CUT2_VOLUME, 200)

    # 5. CornerFillet: R12.7 on the four cavity corners.
    check("fillet cavity corners", await adapter.add_fillet(FILLET_R, FILLET_EDGES))
    name_last_feature(adapter, "CornerFillet")
    await volume_check(adapter, "CornerFillet", CORNER_FILLET_VOLUME, 200)
    name_dimensions(adapter, "CornerFillet", ["CavityRadius"])

    # 6. PocketCornerFillet: R6.35 on both opposed pocket openings.
    check(
        "fillet pocket corners",
        await adapter.add_fillet(POCKET_FILLET_R, POCKET_FILLET_EDGES),
    )
    name_last_feature(adapter, "PocketCornerFillet")
    name_dimensions(adapter, "PocketCornerFillet", ["PocketRadius"])
    await volume_check(adapter, "PocketCornerFillet", POCKET_FILLET_VOLUME, 20)

    # 7. FootClearanceHoles: one native Hole Wizard feature, four 5/16 drills.
    wizard_holes(
        adapter,
        HOLE_SPEC,
        [[x, -BIG, z] for x, z in HOLES],
        (0.0, 1.0, 0.0),
        "rocker-support top-down clearance holes (5/16)",
        name="FootClearanceHoles",
        expect_dia_mm=HOLE_DIA,
    )
    await volume_check(adapter, "FootClearanceHoles", FOOT_HOLED_VOLUME, 200)

    # 8. RimChamfer: 1.27 mm / 45° around the whole window rim -- the 12 inner-
    #    frame opening edges plus the slant/trapezoid/fillet faces, tangent-
    #    propagated.
    check(
        "chamfer",
        await adapter.add_chamfer(
            CHAMFER, CHAMFER_EDGES, face_points=CHAMFER_FACES, tangent_propagation=True
        ),
    )
    name_last_feature(adapter, "RimChamfer")
    name_dimensions(adapter, "RimChamfer", ["RimChamferSize"])
    await volume_check(adapter, "RimChamfer", RIM_CHAMFER_VOLUME, 200)

    # 9. BracketSeats: the rocker brackets' four #8-32 bottoming-tapped seats,
    #    down from the top face into the deepened rail. Located at their
    #    nominal stations; the print says TRANSFER FROM MHA-123 AT ASSEMBLY.
    wizard_holes(
        adapter,
        SEAT_SPEC,
        SEAT_POINTS,
        (0.0, 1.0, 0.0),
        "rocker-bracket hold-down bottoming-tapped seats (#8-32)",
        name="BracketSeats",
    )
    await volume_check(adapter, "BracketSeats", BRACKET_SEATS_VOLUME, 200)

    # Apply the deferred drive equations now that the whole model + a rebuild
    # exist, so every named-dim target resolves. Each equation evaluates to the
    # value just built, so the geometry must not move -- the re-check below is
    # the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven part (equations neutral)", BRACKET_SEATS_VOLUME, 200
    )

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(
        adapter, CASTING_GREEN
    )  # green-painted casting, like the base/top-frame
    await report_mass_properties(adapter)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
