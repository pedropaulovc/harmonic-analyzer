r"""Reproduction script: rocker-arm support (manual feature-tree replay).

An exact feature-tree replay of ``rocker-arm-support-manual.SLDPRT`` -- a
thin-walled cast bracket: a trapezoidal wedge wall (wide foot, narrow top)
stood **Y-up**, lightened by a square window that opens on the two big front/
back faces, with a mounting foot drilled by four tapped holes (bored vertically
up through the foot) and the window rim broken by a fillet + chamfer.

The part is oriented to match the source SLDPRT's standard views: the **Front**
view (along Z) looks square-on at the rounded window; the **Right** view (along
X) shows the trapezoid taper; the **Top** view (along Y) shows the two channels,
the central web, and the four foot holes.

The original is hand-built; this rebuilds it feature-for-feature (matching the
tree Boss-Extrude1 -> Cut-Extrude2/3/4 -> Fillet3 -> 9/16-12 Tapped Hole1
(HoleWzd) -> Chamfer2) rather than as a simplified parametric equivalent. The
the trapezoid lives on the **Right plane** (sketch-x -> model Z taper, sketch-y
-> model Y height, mid-plane extrude along X); the window/cavity cuts use SINGLE
origin-centred squares on the **Front plane** (matching the source's Sketch11/
Sketch12). The per-stage ``volume_check`` targets are the real part's measured
volumes (rotation-invariant, so unchanged by orientation), so any geometry drift
fails loudly:

    Boss-Extrude1 1 271 363 | Cut-Extrude2 622 708 | Cut-Extrude3 434 257
    Cut-Extrude4   245 806 | Fillet3      246 685 | Holes        243 665
    Chamfer2       240 512

Geometry (mm), all from the source part (model frame: X = extrude/width,
Y = height with the wide foot at Y=-88.9, Z = wall thickness / window depth):

* **Boss** -- trapezoid, wide foot ``Z ±31.75`` at ``Y=-88.9`` tapering to
  ``Z ±8.4665`` at ``Y=+88.9``; mid-plane extrude 177.8 (``X ±88.9``).
* **Cut-Extrude2** -- 127 mm cavity square (``±63.5``), Through-All-Both -> the
  central cavity, leaving 6.35 mm shell walls (whole ``Sketch12`` profile).
* **Cut-Extrude3 / 4** -- ONE shared 165.1 mm window square (``Sketch11``,
  ``±82.55``). Each cut is a Through-All that STARTS ``WEB`` (3.175) off the
  sketch plane in the opposite direction (cut3 forward / cut4 reverse, cut4
  re-selecting Sketch11 -> ``Sketch11<2>``), so the 2*WEB band between them
  survives as the central web -- the source's ``FromOffsetDistance`` /
  ``ReverseDirection`` pair, reproducing the two-sketches-feed-three-cuts tree.
* **Fillet3** -- R12.7 on the four inner-frame corner edges (concave: adds
  material).
* **9/16-12 Tapped Hole1** -- a single Hole Wizard (``HoleWzd``) feature, 4x
  9/16-12 ANSI-inch bottoming tapped holes (Ø12.30376 tap drill), drilled up
  through the foot from the bottom face (Y=-88.9) at ``(X ±60.32, Z ±17.46)``,
  through-next. One feature with four placement points, matching the source
  (no separate placement Sketch5).
* **Chamfer2** -- 1.27 mm / 45° on the 12 inner-frame opening edges plus the
  two slant faces, the two trapezoid (±X) faces, and one fillet face, with
  tangent propagation -- i.e. the whole window rim.

Like the 71 tracked parts, this is **equation-driven and self-naming**: five
equation-manager globals (``FootHalf``/``TopHalf``/``HalfHeight``/``CavHalf``/
``WindowOuter``, all ``mm``) drive every profile sketch's dimensions (named e.g.
``WallHeight@Sketch1``, ``WinWidth@Sketch11``), the sketches and features carry
stable names, and the drive equations are applied in one deferred
batch after a rebuild. A final "equations neutral" ``volume_check`` proves the
driving did not move the geometry, so a GUI edit to a global reshapes the part
and round-trips. See ``build_top_frame.py`` for the reference pattern.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rocker_arm_support_manual.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_centered_rectangle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "rocker-arm-support-manual"
MATERIAL = "AISI 1020 Steel, Cold Rolled"  # source part's database material

# Trapezoid (Sketch1) -- wide foot / narrow top, half-extents in mm. On the
# Right plane: sketch-x -> model Z (taper), sketch-y -> model Y (height).
WIDE = 31.75       # foot half-width (Z) at Y=-88.9
NARROW = 8.4665    # top half-width (Z) at Y=+88.9
HALF_Y = 88.9      # trapezoid half-height (Y)
BOSS_DEPTH = 177.8  # mid-plane extrude along X (X ±88.9)

CAV = 63.5         # 127 mm square half (Cut-Extrude2)
BIG = 82.55        # 165.1 mm square half (Cut-Extrude3/4)
WEB = 3.175        # window-cut start-offset; the 2*WEB band left as the web

FILLET_R = 12.7
FILLET_EDGES = [  # four inner-frame corner edges (run along Z through the web)
    [63.5, 63.5, 0.0], [-63.5, 63.5, 0.0],
    [63.5, -63.5, 0.0], [-63.5, -63.5, 0.0],
]

HOLES = [(60.32, 17.46), (-60.32, 17.46), (60.32, -17.46), (-60.32, -17.46)]
# Hole Wizard constants (resolved from the SW type library on this seat):
SW_FM_HOLE_WZD = 25            # swFeatureNameID_e.swFmHoleWzd (CreateDefinition)
SW_WZD_TAP = 4                 # swWzdGeneralHoleTypes_e.swWzdTap (straight tap)
SW_STD_ANSI_INCH = 0           # swWzdHoleStandards_e.swStandardAnsiInch
SW_HOLE_FASTENER_TYPE = 26     # ANSI-inch "Bottoming Tapped Hole"
SW_END_THROUGH_NEXT = 2        # swEndCondThroughNext / swEndThreadTypeTHROUGH_NEXT
HOLE_SSIZE = "9/16-12"
HOLE_THREAD_CLASS = "1B"

CHAMFER = 1.27     # leg, 45°
CHAMFER_EDGES = [  # 12 inner-frame opening edges, both web faces (Z = ±WEB)
    [0.0, -63.5, -3.175], [63.5, 0.0, -3.175], [59.78, 59.78, -3.175],
    [0.0, 63.5, -3.175], [-63.5, 0.0, -3.175], [-59.78, -59.78, -3.175],
    [0.0, -63.5, 3.175], [-59.78, -59.78, 3.175], [-63.5, 0.0, 3.175],
    [-59.78, 59.78, 3.175], [0.0, 63.5, 3.175], [63.5, 0.0, 3.175],
]
CHAMFER_FACES = [  # whole faces whose every edge is chamfered (tangent-propagated)
    [0.0, -85.0, 31.24], [0.0, -85.0, -31.24],  # ±Z slant window surrounds
    [88.9, 0.0, 0.0], [-88.9, 0.0, 0.0],        # front / back trapezoid (±X) faces
    [59.78, -59.78, 0.0],                        # one inner fillet face
]


def _flag(obj, iface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info
    try:
        sw_type_info.flag_methods(obj, iface)
    except Exception:  # noqa: BLE001
        pass


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
    _flag(sm, "ISketchManager")
    h = half_mm / 1000.0
    prev = bool(sm.AddToDB)
    sm.AddToDB = True
    try:
        for (x1, y1), (x2, y2) in (((-h, -h), (h, h)), ((-h, h), (h, -h))):
            seg = sm.CreateLine(x1, y1, 0.0, x2, y2, 0.0)
            _flag(seg, "ISketchSegment")
            seg.ConstructionGeometry = True
    finally:
        sm.AddToDB = prev


def _select_sketch(adapter, name: str) -> None:
    """Select a sketch by name for the next feature (shared-sketch friendly: a
    second select of an already-consumed sketch is how cut4 reuses Sketch11,
    which SolidWorks then shows as ``Sketch11<2>``)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
            name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"select sketch {name!r} failed")


def _cut_through_all(adapter, sketch_name: str, *, both: bool, reverse_dir: bool,
                     start_offset_mm: float = 0.0, flip_start: bool = False):
    """Through-all ``FeatureCut4`` on the named sketch.

    ``both`` -> Through-All-Both (the cavity). A single-direction cut with
    ``start_offset_mm`` reproduces the windows: each window cut shares one
    centered ``Sketch11`` square but STARTS ``start_offset_mm`` off the sketch
    plane (cut3 forward / cut4 reverse, opposite ``flip_start``), so the 2*offset
    band between them survives as the central web -- exactly the source's
    ``FromOffsetDistance``/``ReverseDirection`` pair.
    """
    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    fm = model.FeatureManager
    _flag(fm, "IFeatureManager")
    _select_sketch(adapter, sketch_name)

    through = adapter.constants.get("swEndCondThroughAll", 1)
    t0 = (adapter.constants.get("swStartOffset", 3) if start_offset_mm
          else adapter.constants.get("swStartSketchPlane", 0))
    # 27-param FeatureCut4: T0/StartOffset/FlipStartOffset are the start-condition
    # tail (26-param is the SW-2025 form).
    args = (not both, False, reverse_dir, through, through, 0.0, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, False,
            False, True, False, False, False,
            t0, start_offset_mm / 1000.0, flip_start, False)
    feat = adapter._attempt(lambda: fm.FeatureCut4(*args), default=None)
    if not feat:
        feat = adapter._attempt(lambda: fm.FeatureCut4(*args[:-1]), default=None)
    model.ClearSelection2(True)
    if not feat:
        raise RuntimeError(f"FeatureCut4 on {sketch_name} failed")
    return feat


def _find_bottom_face(model, holes_xz, y_face_mm: float):
    """Return the planar foot bottom face (normal ~ (0,-1,0)) whose bounding box
    spans all ``holes_xz`` -- the face the holes are drilled from.

    SelectByID2 by coordinate is unreliable here: a point on the Y=-88.9 plane
    resolves to the ±X trapezoid end faces (which also touch that plane), so the
    drill axis comes out along X. Selecting the face OBJECT found by enumeration
    is the reliable path.
    """
    body = (model.GetBodies2(0, False) or [None])[0]
    _flag(body, "IBody2")
    best = None
    for f in (body.GetFaces() or []):
        _flag(f, "IFace2")
        try:
            n = tuple(f.Normal)
        except Exception:  # noqa: BLE001
            continue
        if not (abs(n[0]) < 0.01 and n[1] < -0.99 and abs(n[2]) < 0.01):
            continue
        box = [v * 1000 for v in f.GetBox()]
        if abs(box[1] - y_face_mm) > 1.0:  # not on the foot bottom plane
            continue
        spans = all(box[0] - 1 <= hx <= box[3] + 1 and box[2] - 1 <= hz <= box[5] + 1
                    for hx, hz in holes_xz)
        if spans and (best is None or f.GetArea() > best.GetArea()):
            best = f
    return best


def _drill_tapped_holes(adapter, holes_xz, y_face_mm: float):
    """Create ONE Hole Wizard (HoleWzd) feature with a placement point at each
    of ``holes_xz`` (model X,Z in mm), drilled from the foot bottom face at
    ``y_face_mm``.

    The face is selected as an OBJECT (coordinate selection mis-resolves to the
    ±X end faces). The wizard is created on that face (one auto point), then its
    placement sketch is edited: the auto point is moved to hole #0 (SetCoords)
    and the other points are added (model->sketch via the sketch's
    ModelToSketchTransform; MathUtility is marshalled with an explicit VARIANT
    array since a bare Python list does not pass as a safearray). Rebuilt: one
    HoleWzd feature, N holes, matching the source tree (no separate placement
    sketch in the design tree).
    """
    import pythoncom
    from win32com.client import VARIANT

    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    _flag(model, "IModelDoc2")
    fm = model.FeatureManager
    _flag(fm, "IFeatureManager")

    data = fm.CreateDefinition(SW_FM_HOLE_WZD)
    _flag(data, "IWizardHoleFeatureData2")
    data.InitializeHole(
        SW_WZD_TAP, SW_STD_ANSI_INCH, SW_HOLE_FASTENER_TYPE,
        HOLE_SSIZE, SW_END_THROUGH_NEXT)
    for prop, val in (("ThreadClass", HOLE_THREAD_CLASS),
                      ("EndCondition", SW_END_THROUGH_NEXT),
                      ("ThreadEndCondition", SW_END_THROUGH_NEXT)):
        try:
            setattr(data, prop, val)
        except Exception:  # noqa: BLE001
            pass

    bottom = _find_bottom_face(model, holes_xz, y_face_mm)
    if bottom is None:
        raise RuntimeError("hole wizard: foot bottom face not found")
    model.ClearSelection2(True)
    if not bottom.Select2(False, 0):
        raise RuntimeError("hole wizard: bottom face Select failed")
    feat = fm.CreateFeature(data)
    if feat is None:
        raise RuntimeError("hole wizard: CreateFeature returned None")
    _flag(feat, "IFeature")

    # locate the wizard's 1-point placement sketch
    place_sk = place_name = None
    sub = feat.GetFirstSubFeature()
    while sub is not None:
        _flag(sub, "IFeature")
        if str(sub.GetTypeName2()) == "ProfileFeature":
            sk = sub.GetSpecificFeature2()
            _flag(sk, "ISketch")
            if len(sk.GetSketchPoints2() or []) == 1:
                place_sk, place_name = sk, str(sub.Name)
                break
        sub = sub.GetNextSubFeature()
    if place_sk is None:
        raise RuntimeError("hole wizard: placement sketch not found")

    math = adapter.swApp.GetMathUtility()
    _flag(math, "IMathUtility")
    xform = place_sk.ModelToSketchTransform  # model -> sketch
    _flag(xform, "IMathTransform")
    y_face = y_face_mm / 1000.0

    def _sketch_xy(hx, hz):
        arr = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8,
                      [hx / 1000.0, y_face, hz / 1000.0])
        mpt = math.CreatePoint(arr)
        _flag(mpt, "IMathPoint")
        spt = mpt.MultiplyTransform(xform)
        _flag(spt, "IMathPoint")
        return list(spt.ArrayData)[:3]

    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
            place_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0):
        raise RuntimeError(f"hole wizard: cannot edit {place_name}")
    model.EditSketch()
    sm = model.SketchManager
    _flag(sm, "ISketchManager")
    auto = (place_sk.GetSketchPoints2() or [None])[0]
    _flag(auto, "ISketchPoint")
    sx, sy, sz = _sketch_xy(*holes_xz[0])
    auto.SetCoords(sx, sy, sz)  # move auto point to hole #0
    for hx, hz in holes_xz[1:]:
        sx, sy, sz = _sketch_xy(hx, hz)
        sm.CreatePoint(sx, sy, sz)
    model.EditSketch()  # toggle out of the placement sketch
    model.EditRebuild3()

    npts = len(place_sk.GetSketchPoints2() or [])
    if npts != len(holes_xz):
        raise RuntimeError(
            f"hole wizard: expected {len(holes_xz)} placement points, got {npts}")
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
    await set_global(adapter, "FootHalf", f"{WIDE}mm")      # trapezoid foot half-width (Z)
    await set_global(adapter, "TopHalf", f"{NARROW}mm")     # trapezoid top half-width (Z)
    await set_global(adapter, "HalfHeight", f"{HALF_Y}mm")  # trapezoid half-height (Y)
    await set_global(adapter, "CavHalf", f"{CAV}mm")        # cavity square half
    await set_global(adapter, "WindowOuter", f"{BIG}mm")    # window square half

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
        adapter, trap_lines, trap_pts, anchor=0, label="trapezoid", dims=trap,
        names=["FootAnchorZ", "FootAnchorY", "FootSpan", "TaperRun",
               "WallHeight", "TopSpan"],
        drives=['"FootHalf"', '"HalfHeight"', '2 * "FootHalf"',
                '"FootHalf" - "TopHalf"', '2 * "HalfHeight"', '2 * "TopHalf"'],
    )
    await ensure_fully_defined(adapter, "trapezoid")
    check("exit boss", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch1")
    drive_jobs += trap.apply(adapter, "Sketch1")
    check("boss", await adapter.create_extrusion(
        ExtrusionParameters(depth=BOSS_DEPTH, both_directions=True)))
    name_last_feature(adapter, "Boss-Extrude1")
    await volume_check(adapter, "Boss-Extrude1", 1_271_363, 200)

    # 2-4. Two sketches drive three cuts, exactly as the source tree does. Both
    # window/cavity sketches are SINGLE origin-centred squares on the Front plane,
    # drawn center-rectangle style (four real sides + two construction diagonals),
    # matching the source's Sketch11/Sketch12 segment set:
    #   * Sketch11 -- the 165.1 mm window square. Cut-Extrude3 and Cut-Extrude4
    #     BOTH consume this ONE sketch (cut4 re-selects it -> "Sketch11<2>"), each
    #     a Through-All cut that STARTS WEB (3.175) off the sketch plane in the
    #     opposite direction, so the 2*WEB band between them survives as the
    #     central web -- the source's FromOffsetDistance/ReverseDirection pair,
    #     not a sketch gap. The square drives off WindowOuter.
    #   * Sketch12 -- the 127 mm cavity square; Cut-Extrude2 consumes it whole
    #     (Through-All-Both). Drives off CavHalf.
    # Built in the source's creation order (Sketch11, then Sketch12) and cut in
    # the source's order (cavity, then the two windows).
    windows = SketchDims()
    check("sketch windows", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BIG, BIG, "window", dims=windows,
        name_width="WinWidth", drive_width='2 * "WindowOuter"',
        name_depth="WinHeight", drive_depth='2 * "WindowOuter"',
        name_corner=("WinCornerX", "WinCornerY"),
        drive_corner=('"WindowOuter"', '"WindowOuter"'),
    )
    _add_construction_diagonals(adapter, BIG)
    await ensure_fully_defined(adapter, "window")
    check("exit windows", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch11")
    drive_jobs += windows.apply(adapter, "Sketch11")

    cavity = SketchDims()
    check("sketch cavity", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, CAV, CAV, "cavity", dims=cavity,
        name_width="CavWidth", drive_width='2 * "CavHalf"',
        name_depth="CavDepth", drive_depth='2 * "CavHalf"',
        name_corner=("CavCornerX", "CavCornerY"),
        drive_corner=('"CavHalf"', '"CavHalf"'),
    )
    _add_construction_diagonals(adapter, CAV)
    await ensure_fully_defined(adapter, "cavity")
    check("exit cavity", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch12")
    drive_jobs += cavity.apply(adapter, "Sketch12")

    # Cut-Extrude2: cavity -- whole Sketch12 profile, Through-All-Both.
    _cut_through_all(adapter, "Sketch12", both=True, reverse_dir=False)
    name_last_feature(adapter, "Cut-Extrude2")
    await volume_check(adapter, "Cut-Extrude2", 622_708, 200)

    # Cut-Extrude3: one window -- Through-All forward, started WEB off-plane.
    _cut_through_all(adapter, "Sketch11", both=False, reverse_dir=False,
                     start_offset_mm=WEB, flip_start=True)
    name_last_feature(adapter, "Cut-Extrude3")
    await volume_check(adapter, "Cut-Extrude3", 434_257, 200)

    # Cut-Extrude4: the other window -- the SAME Sketch11, Through-All reverse,
    # started WEB off-plane the other way (leaves the 2*WEB central web).
    _cut_through_all(adapter, "Sketch11", both=False, reverse_dir=True,
                     start_offset_mm=WEB, flip_start=False)
    name_last_feature(adapter, "Cut-Extrude4")
    await volume_check(adapter, "Cut-Extrude4", 245_806, 200)

    # 5. Fillet3: R12.7 on the four inner-frame corner edges (concave -> adds).
    check("fillet", await adapter.add_fillet(FILLET_R, FILLET_EDGES))
    name_last_feature(adapter, "Fillet3")
    await volume_check(adapter, "Fillet3", 246_685, 200)

    # 6. 9/16-12 Tapped Hole1: ONE Hole Wizard (HoleWzd) feature with four
    #    placement points, 9/16-12 ANSI-inch bottoming tapped holes drilled up
    #    through the foot from the bottom face (Y=-HALF_Y) at (X ±60.32, Z ±17.46),
    #    through-next. Only the 6.35 mm foot tip (Y -88.9..-82.55) carries
    #    material along the bore -- the window cuts opened everything above -- so
    #    through-next drills exactly that band, matching the source's measured
    #    volume. One feature, no separate placement sketch (matches the source).
    _drill_tapped_holes(adapter, HOLES, y_face_mm=-HALF_Y)
    name_last_feature(adapter, "9/16-12 Tapped Hole1")
    await volume_check(adapter, "Holes", 243_665, 200)

    # 7. Chamfer2: 1.27 mm / 45° around the whole window rim -- the 12 inner-
    #    frame opening edges plus the slant/trapezoid/fillet faces, tangent-
    #    propagated.
    check("chamfer", await adapter.add_chamfer(
        CHAMFER, CHAMFER_EDGES, face_points=CHAMFER_FACES, tangent_propagation=True))
    name_last_feature(adapter, "Chamfer2")
    await volume_check(adapter, "Chamfer2", 240_512, 200)

    # Apply the deferred drive equations now that the whole model + a rebuild
    # exist, so every named-dim target resolves. Each equation evaluates to the
    # value just built, so the geometry must not move -- the re-check below is
    # the proof (same final volume as Chamfer2 above).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven part (equations neutral)", 240_512, 200)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
