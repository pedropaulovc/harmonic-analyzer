r"""Build the oblique-trammel jig's end bracket (MHA-CH-06-TL-28; shop fixture).

A 6061-T6511 1/2 x 1 in flat on edge, 2.71 long, two off: each carries one of the
leadscrew feed's KP08 pillow blocks on base bar 1's top
(``ch_rocker_arm_tl_oblique_end_bracket_spec``).

Layout (the spec's model frame, +Z up): ONE Front-plane rectangle from the
inner end face (model x 0) about the mid-width line, extruded +Z by the stock
thickness; the two holes on the row y 0 (the KP08's 42 mm span) are tapped
#8-32 UNC from both faces (owner ruling 2026-11-06, Main, option B) by two
native Hole Wizard features at the same stations: ``BarTaps``, BLIND from the
bottom face (its thread ``BAR_THREAD_DEPTH``, its tap drill stopping where the
top thread ends), then ``KP08Taps``, THRU ALL from the intact top face (its
thread ``KP08_THREAD_DEPTH``), whose drill completes the through hole; then
one native cosmetic thread per finished bore from its bottom edge,
``BarFaceThread1``/``2``, ``BAR_THREAD_DEPTH`` deep (the bottom thread the
section draws).
The row's printed station (.250 from the -Y side face) lives on a hidden
reference sketch, ``HoleRowReference`` (build_ch_rocker_arm_tl_oblique_base_bar's
``RailRowReference``); the stock thickness the end view prints lives on another,
``BracketThickReference`` (a drawing view cannot attach the extrusion's depth);
the bar-face thread's depth section A-A prints lives on a third,
``BarThreadReference`` (two points on the outer hole's thread major
diameter), which the build proves equals ``BarTaps``' own thread depth.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_end_bracket.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, dump_dimensions, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _holes import _commit_definition_edits, blind_hole_volume_mm3, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _metric_vendor_dimension import set_metric_vendor_units
from _part_save import save_part_and_images, set_isometric_view
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
import _telemetry
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from ch_rocker_arm_tl_oblique_end_bracket_spec import (
    BAR_TAP_DRILL_DEPTH,
    BAR_TAP_FACE,
    BAR_TAP_SPEC,
    BAR_THREAD_DEPTH,
    BAR_THREAD_DEPTH_DIMENSION,
    BAR_THREAD_REFERENCE,
    BAR_THREAD_WITNESS_X,
    BRACKET_LENGTH,
    BRACKET_THICK,
    BRACKET_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HALF_WIDTH,
    HOLE_ROW_Y,
    HOLE_X,
    ISOMETRIC_VIEW_NOTE,
    KP08_TAP_FACE,
    KP08_TAP_SPEC,
    KP08_THREAD_DEPTH,
    METRIC_DIMENSIONS,
    SCREW,
    TAP_DRILL,
    THREAD_MAJOR,
)

PART_NAME = "ch-rocker-arm-tl-oblique-end-bracket"
MATERIAL = "6061 Alloy"  # the registry row's example aluminium flat bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

V_BRACKET = BRACKET_LENGTH * BRACKET_WIDTH * BRACKET_THICK
# The bar-face wizard's blind drills (with their 118 deg points), then the
# whole through holes once the top wizard's THRU ALL drill completes them
# (the point cone lies inside the through cylinder).
V_BAR_TAPS = len(HOLE_X) * blind_hole_volume_mm3(TAP_DRILL, BAR_TAP_DRILL_DEPTH)
V_HOLES = len(HOLE_X) * math.pi * (TAP_DRILL / 2.0) ** 2 * BRACKET_THICK
# Tight enough that a missing tap (about 237 mm^3 each) fails.
_V_TOL = 20.0


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


# swEndConditions_e: the drill's THRU ALL, the thread's BLIND.
_THRU_ALL = 1
_BLIND = 0


@_telemetry.traced("feature.thread_from_face", label_param="label")
def _thread_from_face(
    adapter, feature_name: str, depth_mm: float, *, label: str
) -> None:
    """Stop a THRU tap's thread ``depth_mm`` from its wizard face; its tap
    drill stays THRU ALL.

    ``wizard_holes`` commits a through tap with a THRU ALL thread; its own
    edit flow then sets the thread's end and depth, and the committed
    definition, read back, is the proof (a hand tap cannot thread the 1 in
    height: owner ruling 2026-11-05).
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    # IPartDoc::FeatureByName is VT_DISPATCH: a missing feature is None,
    # which _early_bound passes through, so refuse it by identity here.
    raw = _early_bound(model, "IPartDoc").FeatureByName(feature_name)
    if raw is None:
        raise RuntimeError(f"{label}: no feature {feature_name!r}")
    feature = _early_bound(raw, "IFeature")
    definition = _commit_definition_edits(
        model,
        feature,
        _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2"),
        [("ThreadEndCondition", _BLIND), ("ThreadDepth", depth_mm / 1000.0)],
        label,
    )
    readback = {
        "EndCondition": int(definition.EndCondition),
        "ThreadEndCondition": int(definition.ThreadEndCondition),
        "ThreadDepth": float(definition.ThreadDepth) * 1000.0,
    }
    if (
        readback["EndCondition"] != _THRU_ALL
        or readback["ThreadEndCondition"] != _BLIND
        or abs(readback["ThreadDepth"] - depth_mm) > 0.005
    ):
        raise RuntimeError(f"{label}: thread did not stop short: {readback!r}")


# The bottom thread's own drawn feature: farm 84d5991d45 and 26bb imported
# BarTaps' wizard thread annotations hidden in every view (IAnnotation.Visible
# 3, no display) while KP08Taps' drew; KP08Taps' THRU ALL drill re-makes the
# bore after BarTaps [inference: the wizard thread's face is gone]. A native
# cosmetic thread on each finished bore's bottom edge, made after the last
# cut, is the bottom thread section A-A draws. Its callout text matches the
# wizards' own "... Tapped Hole" notes, which the sheet sweeps: the hole
# callouts state every thread (draw_..._end_bracket, REDUNDANT_THREAD_NOTES).
BAR_FACE_THREAD = "BarFaceThread"
BAR_FACE_THREAD_NOTE = f"{SCREW} Tapped Hole"
# swStandardViews_e.swBackView: the viewer on -Z, facing the Front plane's
# back, i.e. the bottom face (BAR_TAP_FACE, outward normal -Z). add_thread
# picks its edge through SelectByID2, which picks at the point's screen
# projection (features._select_by_point: a hidden edge misses, or the pick
# lands on what hides it); from the default isometric the bottom edges sit
# behind the body, so the picks run square-on to the bottom face, and
# _require_bar_face_threads proves the edge each thread holds.
_SW_BACK_VIEW = 2
_EDGE_TOL_MM = 0.01


@_telemetry.traced("feature.bar_face_cosmetic_threads")
async def _bar_face_cosmetic_threads(adapter) -> tuple[str, ...]:
    """One #8-32 cosmetic thread per bore from its bottom edge, BLIND
    BAR_THREAD_DEPTH, named ``BarFaceThread<k>``; picked square-on to the
    bottom face, the standard isometric restored after."""
    from solidworks_mcp.adapters.base import AddThreadParameters

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    model.ShowNamedView2("", _SW_BACK_VIEW)
    adapter._zoom_to_fit(model)
    names = []
    _normal, face_z = BAR_TAP_FACE
    try:
        for k, x in enumerate(HOLE_X, start=1):
            label = f"bar-face cosmetic thread {k}"
            created = check(
                label,
                await adapter.add_thread(
                    AddThreadParameters(
                        edge_point=[x + TAP_DRILL / 2.0, 0.0, face_z],
                        standard="ansi_inch",
                        size=SCREW,
                        end_type="blind",
                        depth=BAR_THREAD_DEPTH,
                        note=BAR_FACE_THREAD_NOTE,
                    )
                ),
            )
            native = created.get("name")
            if type(native) is not str or not native:
                raise RuntimeError(f"{label}: returned no feature name")
            raw = part.FeatureByName(native)
            if raw is None:
                raise RuntimeError(f"{label}: no feature {native!r}")
            name = f"{BAR_FACE_THREAD}{k}"
            _early_bound(raw, "IFeature").Name = name
            if part.FeatureByName(name) is None:
                raise RuntimeError(f"{label}: {native!r} refused the name {name!r}")
            names.append(name)
    finally:
        set_isometric_view(adapter)
    _telemetry.info(f"bar-face cosmetic threads: {names!r}")
    return tuple(names)


def _thread_edge_circle(model, definition, *, label: str) -> list[float]:
    """The circle (centre xyz, radius; mm) of the edge a cosmetic thread
    starts on: ``ICosmeticThreadFeatureData.Edge`` read inside
    AccessSelections, ``ICurve.CircleParams`` (centre, axis, radius; m)."""
    # AccessSelections and IsCircle are VT_BOOL; test them identity-strict.
    if definition.AccessSelections(model, None) is not True:
        raise RuntimeError(f"{label}: AccessSelections failed")
    try:
        edge = _early_bound(definition.Edge, "IEdge")
        if edge is None:
            raise RuntimeError(f"{label}: thread has no edge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve is None or curve.IsCircle() is not True:
            raise RuntimeError(f"{label}: thread edge is not a circle")
        raw = curve.CircleParams
        params = [float(value) for value in raw] if raw is not None else []
    finally:
        definition.ReleaseSelectionAccess()
    if len(params) != 7:
        raise RuntimeError(f"{label}: CircleParams read {params!r}")
    return [value * 1000.0 for value in (*params[:3], params[6])]


@_telemetry.traced("feature.require_bar_face_threads")
def _require_bar_face_threads(adapter, names: tuple[str, ...]) -> None:
    """Each bottom cosmetic thread BLIND at BarTaps' committed thread depth,
    the spec's BAR_THREAD_DEPTH (build_mg_magnifying_lever's readback), on
    its own bore's bottom edge: the tap drill's circle centred on that
    station, on the bottom face."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(model, "IPartDoc")
    raw_taps = part.FeatureByName("BarTaps")
    if raw_taps is None:
        raise RuntimeError("bar-face threads: no feature 'BarTaps'")
    wizard = _early_bound(
        _early_bound(raw_taps, "IFeature").GetDefinition(), "IWizardHoleFeatureData2"
    )
    wizard_mm = float(wizard.ThreadDepth) * 1000.0
    _normal, face_z = BAR_TAP_FACE
    readback = {}
    for name in names:
        raw = part.FeatureByName(name)
        if raw is None:
            raise RuntimeError(f"bar-face threads: no feature {name!r}")
        definition = _early_bound(
            _early_bound(raw, "IFeature").GetDefinition(), "ICosmeticThreadFeatureData"
        )
        if definition is None:
            raise RuntimeError(f"bar-face threads: {name!r} has no thread definition")
        # swCosmeticEndConditions_e: Blind = 0.
        readback[name] = (
            int(definition.EndCondition),
            float(definition.BlindDepth) * 1000.0,
            _thread_edge_circle(model, definition, label=f"bar-face thread {name}"),
        )
    wanted = {
        f"{BAR_FACE_THREAD}{k}": (x, 0.0, face_z, TAP_DRILL / 2.0)
        for k, x in enumerate(HOLE_X, start=1)
    }
    if (
        set(readback) != set(wanted)
        or abs(wizard_mm - BAR_THREAD_DEPTH) > 0.005
        or any(
            end != _BLIND
            or abs(depth - wizard_mm) > 0.005
            or any(
                abs(got - want) > _EDGE_TOL_MM
                for got, want in zip(circle, wanted[name], strict=True)
            )
            for name, (end, depth, circle) in readback.items()
        )
    ):
        raise RuntimeError(
            f"bar-face threads {readback!r} differ from their bottom edges "
            f"{wanted!r} or BarTaps' thread {wizard_mm:.4f} mm / "
            f"BAR_THREAD_DEPTH {BAR_THREAD_DEPTH:.4f}"
        )
    _telemetry.info(f"bar-face threads read back: {readback!r}")


def _add_point(adapter, point: tuple[float, float], label: str) -> str:
    """One sketch point straight into the sketch DB (no inference snap),
    registered for the adapter's dimension refs
    (build_ch_rocker_arm_tl_oblique_carrier)."""
    sketch_manager = _early_bound(adapter.currentSketchManager, "ISketchManager")
    previous = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        created = sketch_manager.CreatePoint(point[0] / 1000.0, point[1] / 1000.0, 0.0)
    finally:
        sketch_manager.AddToDB = previous
    if created is None:
        raise RuntimeError(f"cannot create the {label} point")
    return adapter._register_sketch_entity("Point", created)


def _require_bar_thread_reference(adapter) -> None:
    """The depth section A-A prints is the bar-face wizard's own thread
    depth: ``BarThreadReference``'s dimension and ``BarTaps``' committed
    ``ThreadDepth`` both read ``BAR_THREAD_DEPTH``; its station stands on the
    outer hole's thread major diameter (``BAR_THREAD_WITNESS_X``)."""
    rows = {
        row["full_name"].split("@")[0]: row["value_mm"]
        for row in dump_dimensions(adapter, BAR_THREAD_REFERENCE)
        if row["full_name"].split("@")[1:2] == [BAR_THREAD_REFERENCE]
    }
    raw = _early_bound(adapter.currentModel, "IPartDoc").FeatureByName("BarTaps")
    if raw is None:
        raise RuntimeError("bar thread reference: no feature 'BarTaps'")
    definition = _early_bound(
        _early_bound(raw, "IFeature").GetDefinition(), "IWizardHoleFeatureData2"
    )
    wizard = float(definition.ThreadDepth) * 1000.0
    depth = rows.get(BAR_THREAD_DEPTH_DIMENSION)
    station = rows.get("BarThreadStation")
    if (
        depth is None
        or abs(depth - wizard) > 1e-4
        or abs(wizard - BAR_THREAD_DEPTH) > 1e-4
        or station is None
        or abs(station - BAR_THREAD_WITNESS_X) > 1e-4
    ):
        raise RuntimeError(
            f"bar thread reference {rows!r} mm disagrees with BarTaps' thread "
            f"{wizard:.4f} mm, the spec's {BAR_THREAD_DEPTH:.4f} mm or the "
            f"witness station {BAR_THREAD_WITNESS_X:.4f} mm"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("BracketLength", BRACKET_LENGTH),
        ("BracketWidth", BRACKET_WIDTH),
        ("BracketThick", BRACKET_THICK),
        ("HoleX1", HOLE_X[0]),
        ("HoleX2", HOLE_X[1]),
        ("BarThreadDepth", BAR_THREAD_DEPTH),
        ("ThreadMajor", THREAD_MAJOR),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Bracket: Front-plane rectangle about the mid-width line, +Z ---------
    profile = SketchDims()
    check("create_sketch bracket", await adapter.create_sketch("Front"))
    points = [
        (0.0, -HALF_WIDTH),
        (BRACKET_LENGTH, -HALF_WIDTH),
        (BRACKET_LENGTH, HALF_WIDTH),
        (0.0, HALF_WIDTH),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bracket profile",
        dims=profile,
        names=["BracketLength", "BracketWidth", "BracketHalfWidth"],
        drives=['"BracketLength"', '"BracketWidth"', '"BracketWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "bracket profile")
    check("exit_sketch bracket", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketProfile")
    drive_jobs = profile.apply(adapter, "BracketProfile")
    check(
        "extrude bracket",
        await adapter.create_extrusion(ExtrusionParameters(depth=BRACKET_THICK)),
    )
    name_last_feature(adapter, "Bracket")
    # The depth stays off the print: the stock thickness prints from
    # BracketThickReference (below), which a drawing view can attach to.
    drive_jobs.append(
        (name_dimensions(adapter, "Bracket", ["BracketDepth"])[0], '"BracketThick"')
    )
    volume = await volume_check(adapter, "bracket", V_BRACKET, _V_TOL)

    # --- Bar-face threads: ONE #8-32 UNC BLIND wizard from the bottom face --
    # Their screws come up through TL-20, so each thread runs from the bar
    # face, BAR_THREAD_DEPTH deep; the drill stops where the KP08-face thread
    # will end, so the top face stays whole for the next wizard. The wizard
    # sets the row on y 0 by an origin relation (a zero coordinate takes no
    # dimension); each station is a dimension from the inner end.
    bar_normal, bar_z = BAR_TAP_FACE
    bar_taps = wizard_holes(
        adapter,
        BAR_TAP_SPEC,
        [[x, 0.0, bar_z] for x in HOLE_X],
        bar_normal,
        "bar-face screw threads (#8-32 from the bar face)",
        name="BarTaps",
        expect_dia_mm=TAP_DRILL,
        placement_dims=[
            ((f"BarTap{k}X", f'"HoleX{k}"'), (None, None))
            for k in range(1, len(HOLE_X) + 1)
        ],
    )
    drive_jobs += bar_taps.placement_drive_jobs
    volume = await volume_check(
        adapter, "bracket with bar-face threads", volume - V_BAR_TAPS, _V_TOL
    )

    # --- KP08-face threads: ONE #8-32 UNC wizard THRU ALL from the top face --
    # Its drill completes each through hole; its thread stops
    # KP08_THREAD_DEPTH from the top, short of the bar screw's reach.
    kp08_normal, kp08_z = KP08_TAP_FACE
    kp08_taps = wizard_holes(
        adapter,
        KP08_TAP_SPEC,
        [[x, 0.0, kp08_z] for x in HOLE_X],
        kp08_normal,
        "KP08-face screw threads (#8-32 from the KP08 face)",
        name="KP08Taps",
        expect_dia_mm=TAP_DRILL,
        placement_dims=[
            ((f"KP08Tap{k}X", f'"HoleX{k}"'), (None, None))
            for k in range(1, len(HOLE_X) + 1)
        ],
    )
    drive_jobs += kp08_taps.placement_drive_jobs
    _thread_from_face(
        adapter, "KP08Taps", KP08_THREAD_DEPTH, label="KP08-face screw threads"
    )
    volume = await volume_check(
        adapter,
        "bracket with through holes",
        V_BRACKET - V_HOLES,
        _V_TOL,
    )

    # --- The bar-face threads, drawn: one cosmetic thread per finished bore --
    # After the last cut, on each bore's bottom edge (BAR_FACE_THREAD).
    bar_face_threads = await _bar_face_cosmetic_threads(adapter)

    # --- The row's station: a reference sketch -------------------------------
    # One line down the inner end face from the origin to the -Y side, driven
    # by the width that side itself reads. It lies on the end face's edge and
    # stays a plain sketch line: a construction line prints its dash font
    # over the drawing's outline (machinist review mr4: the end view's bottom
    # edge printed broken).
    row_station = SketchDims()
    check("create_sketch hole row reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    row_line = check(
        "hole row station line", await adapter.add_line(0.0, 0.0, 0.0, -HOLE_ROW_Y)
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(adapter, f"{row_line}.start", 0.0, 0.0, "hole row")
    await anchor_point_to_origin(
        adapter, f"{row_line}.end", 0.0, -HOLE_ROW_Y, "hole row station HoleRowY"
    )
    row_station.record("HoleRowY", '"BracketWidth" / 2')
    await ensure_fully_defined(adapter, "hole row reference sketch")
    check("exit_sketch hole row reference", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleRowReference")
    drive_jobs += row_station.apply(adapter, "HoleRowReference")

    # --- The stock thickness: a reference sketch ------------------------------
    # Farm r1 (#290): the extrusion's imported depth has no sound drawing-view
    # attachment, so _supplier_dimensions refuses to dress it as the STOCK
    # reference; a sketch dimension attaches to its witness line (the base
    # bar's BarWidth, _supplier_washer_model's thickness witness). One plain
    # sketch line up the inner end face's -Y edge on the Right plane (on the
    # edge, as the row's line), sketch (u, v) = model (-Z, Y)
    # (_oblique_pivot_block_model), the end view's plane.
    thick = SketchDims()
    check("create_sketch thickness reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    witness = check(
        "thickness witness line",
        await adapter.add_line(0.0, -HALF_WIDTH, -BRACKET_THICK, -HALF_WIDTH),
    )
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(
        adapter, f"{witness}.start", 0.0, -HALF_WIDTH, "thickness witness foot"
    )
    thick.record("ThickWitnessY", '"BracketWidth" / 2')
    check(
        "thickness witness along Z",
        await adapter.add_sketch_constraint(witness, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{witness}.start",
        f"{witness}.end",
        "distance",
        BRACKET_THICK,
        "BracketThick",
    )
    thick.record("BracketThick", '"BracketThick"')
    await ensure_fully_defined(adapter, "thickness reference sketch")
    check("exit_sketch thickness reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BracketThickReference")
    drive_jobs += thick.apply(adapter, "BracketThickReference")

    # --- The bar-face thread's depth: a reference sketch ---------------------
    # Section A-A cuts the hole row (y 0) and prints the bar-face thread's
    # depth from the bottom face, which no wizard dimension carries into a
    # view. Two points on the outer hole's thread major diameter, outer-end
    # side (BAR_THREAD_WITNESS_X, where the section draws that thread's side
    # line), on the Top plane through the row, sketch (u, v) = model (X, -Z)
    # (build_fr_nameplate's SectionReference): one on the bottom face, one
    # BAR_THREAD_DEPTH above it, at the drawn thread's end. Points, not a
    # line: a line would print over the thread. _require_bar_thread_reference
    # proves the depth equals BarTaps' committed thread depth and the
    # station the hole's plus half the major diameter.
    thread_ref = SketchDims()
    check("create_sketch bar thread reference", await adapter.create_sketch("Top"))
    witness_x = BAR_THREAD_WITNESS_X
    face_point = _add_point(adapter, (witness_x, 0.0), "bar thread face")
    await anchor_point_to_origin(
        adapter, face_point, witness_x, 0.0, "bar thread face station"
    )
    thread_ref.record("BarThreadStation", f'"HoleX{len(HOLE_X)}" + "ThreadMajor" / 2')
    end_point = _add_point(adapter, (witness_x, -BAR_THREAD_DEPTH), "bar thread end")
    await anchor_point_to_point(
        adapter,
        face_point,
        end_point,
        0.0,
        -BAR_THREAD_DEPTH,
        BAR_THREAD_DEPTH_DIMENSION,
    )
    thread_ref.record(BAR_THREAD_DEPTH_DIMENSION, '"BarThreadDepth"')
    await ensure_fully_defined(adapter, "bar thread reference sketch")
    check("exit_sketch bar thread reference", await adapter.exit_sketch())
    name_last_feature(adapter, BAR_THREAD_REFERENCE)
    drive_jobs += thread_ref.apply(adapter, BAR_THREAD_REFERENCE)
    _require_one_solid_body(adapter, label="end bracket")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven end bracket (equations neutral)", volume, _V_TOL
    )
    _require_one_solid_body(adapter, label="driven end bracket")
    _require_bar_thread_reference(adapter)
    _require_bar_face_threads(adapter, bar_face_threads)

    # Every model edit -- material, marked set, model-owned places -- precedes
    # the save. The row prints at three places, so the title block's ±.005
    # governs it; the hole stations print exact millimetres with their own
    # band (owner ruling 4; spec module docstring).
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    for (feature_name, dimension_name), (places, band) in METRIC_DIMENSIONS.items():
        set_dimension_symmetric_tolerance(
            adapter, feature_name, dimension_name, band, display_unit="mm"
        )
        set_metric_vendor_units(adapter, feature_name, dimension_name, places=places)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    # The reference sketches own printed dimensions but no geometry: hide
    # them so no assembly renders them; the drawing shows each in the view
    # that imports its dimension (_drawing_hidden_sketches).
    blank_sketch(adapter, "HoleRowReference")
    blank_sketch(adapter, "BracketThickReference")
    blank_sketch(adapter, BAR_THREAD_REFERENCE)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
