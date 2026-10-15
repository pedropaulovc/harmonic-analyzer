r"""Reproduction script: platen support bar (book ch. 21/22, pp. 50-55, 62-63).

THE bar the platen rides on (book p.62 caption, singular): one rectangular
steel bar clamped across the two front columns by the two-piece column
clamps (build_sh_column_clamp_front.py and build_sh_column_clamp_back.py), carrying the hanging platen
(guides + locks on the platen back) and, on its own back face, the ch. 23
transgear hanger (pivot screw MHA-VN-041) and the latch hook (MHA-PD-014).
Cross-section 28 tall x 9 deep (it fills the platen's guide channel to a
1.0 bottom-rail clearance; ``pd_support_bar_spec.BAR_HEIGHT`` carries the
photo chain); 452 long so the ends run ~29 past each column (ch30 p002).

Holes (all along local Z, the machine front-back axis):
* 4x clamp-screw counterbores flanking each column (x +-197 -+ 17.5):
  the screw heads sit sub-flush in the BAR's front face so the refitted platen
  can slide across the east clamp, and thread into the back clamp arc.
* the hanger's #8-32 blind pivot tap and the latch hook's two #4-40 base-screw
  through taps, all entering the back face (``pd_support_bar_spec``).

The hanger holes make the bar x-ASYMMETRIC, so it is authored MACHINE-
handed and placed on its exact machine transform.

Layout: bar axis along X, origin at the bar centre; height along Y,
depth along Z (front face local z -4.5, back face +4.5; named plane
``BackFace``). Dimensions: memory/paper-drive-rework.md E1/E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_support_bar.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _feature_tree import name_last_feature
from _part_pmi import author_part_pmi
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _holes import wizard_holes
from _visibility import blank_reference_geometry
import _telemetry
from vn_clamp_screw_spec import HEAD_H as CLAMP_HEAD_H
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_DEPTH,
    BAR_HEIGHT,
    BAR_BAND_PLACES,
    BAR_DEPTH_BAND,
    BAR_HEIGHT_BAND,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    HANGER_TAP_Y,
    HOLE_POSITION_BAND,
    PIVOT_TAP_CSK_DIA,
    PIVOT_TAP_DRILL_DEPTH,
    PIVOT_TAP_DRILL_DEPTH_LIMITS,
    PIVOT_TAP_DRILL_DIA,
    PIVOT_TAP_FULL_THREAD_MIN,
    PIVOT_TAP_X,
)
from pd_support_bar_drawing_spec import (
    CLAMP_STATION_NAMES,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    HANGER_STATION_NAMES,
    ISOMETRIC_VIEW_NOTE,
    SHEET_PRECISION,
    SURFACE_FINISHES,
    TOL_MAX,
    TOL_MIN,
)

PART_NAME = "pd-support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_LENGTH = 452.0  # ends at x +-226, ~29 past each Ø25.4 column (ch30 p002)

COLUMN_X = 197.0  # frame column line (frame assembly)
CLAMP_SCREW_DX = 17.5  # clamp screws flank each column
# The stock 90280A201 #8-32 clamp screws pass through #8 clearance holes.
# Their 3.9624-mm heads sit below the bar front: the right-shifted platen
# travels across the east clamp line, so proud heads would block its slide.
# The recess is 0.35 so the depth's printed .XXX band
# (pd_support_bar_drawing_spec.CLAMP_CBORE_DEPTH_PLACES) still leaves the head
# about 0.22 under the face at the shallowest; at 0.2 under the .XX band the
# head stood 0.31 proud (Main ruling on the r1 machinist blocker).
CLAMP_HEAD_RECESS = 0.35
CLAMP_CBORE_DIA = 8.5
CLAMP_CBORE_DEPTH = CLAMP_HEAD_H + CLAMP_HEAD_RECESS
CLAMP_THROUGH_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_THROUGH_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    CLAMP_THROUGH_HOLE_SPEC.size,
    overrides_mm={
        "HoleDiameter": CLAMP_HOLE_DIA,
        "CounterBoreDiameter": CLAMP_CBORE_DIA,
        "CounterBoreDepth": CLAMP_CBORE_DEPTH,
    },
)

CLAMP_HOLE_X = tuple(
    s * (COLUMN_X + d) for s in (-1.0, 1.0) for d in (-CLAMP_SCREW_DX, CLAMP_SCREW_DX)
)

# --- Print rows (pd_support_bar_drawing_spec) ---------------------------------
# The hanger holes on the back face: stations from the left end, the row's
# height from the TOP face, which carries the platen's top rail.
LEFT_END_X = -BAR_LENGTH / 2.0
HANGER_ROW_HEIGHT = BAR_HEIGHT / 2.0 - HANGER_TAP_Y
HANGER_STATIONS = tuple(x - LEFT_END_X for x in (PIVOT_TAP_X, *BRACKET_TAP_X))
# The clamp holes on the front face: stations from the same (left, x = -226)
# end as the hanger row, so one end is the datum on both faces, and the
# height from the top face, its rise on the +X end.
CLAMP_ROW_START_X = LEFT_END_X
CLAMP_ROW_HEIGHT = BAR_HEIGHT / 2.0
CLAMP_ROW_X = tuple(sorted(CLAMP_HOLE_X))
CLAMP_STATIONS = tuple(x - CLAMP_ROW_START_X for x in CLAMP_ROW_X)
# The pivot tap's full-thread minimum, drawn along the tap axis in its section
# plane from the back face.
PIVOT_SECTION_PLANE = "PivotSectionPlane"
REFERENCE_SKETCHES = (
    "HangerRowReference",
    "ClampRowReference",
    "CountersinkReference",
    "PivotThreadReference",
)


def _as_construction(adapter, entity_id: str, label: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} did not take the construction flag")


async def _author_row(
    adapter,
    feature: str,
    *,
    rise_x: float,
    row_y: float,
    start_x: float,
    holes: tuple[tuple[str, float, float], ...],
    height_name: str,
    prefix: str,
) -> list[tuple[str, str]]:
    """One hole row as model dimensions on a hidden Front-plane sketch (the
    build_mg_wheel_bar BoreRowReference pattern): a construction chain on the
    row from the bar end at ``start_x`` through each hole (``holes``: name,
    model x, station from that end) to a rise at ``rise_x`` that drops from
    the top face to the row, so the stations read from the end and the row's
    height from the top face."""
    top_y = BAR_HEIGHT / 2.0
    row_xs = (start_x, *(x for _, x, _ in holes), rise_x)
    row = SketchDims()
    check(f"create_sketch {feature}", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    rise = check(
        f"{feature} rise", await adapter.add_line(rise_x, top_y, rise_x, row_y)
    )
    legs = [
        check(f"{feature} leg {index}", await adapter.add_line(x0, row_y, x1, row_y))
        for index, (x0, x1) in enumerate(zip(row_xs, row_xs[1:]))
    ]
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, rise, f"{feature} rise")
    check(
        f"{feature} rise vertical",
        await adapter.add_sketch_constraint(rise, None, "vertical"),
    )
    for index, leg in enumerate(legs):
        _as_construction(adapter, leg, f"{feature} leg {index}")
        check(
            f"{feature} leg {index} horizontal",
            await adapter.add_sketch_constraint(leg, None, "horizontal"),
        )
    for index, (leg, after) in enumerate(zip(legs, [*legs[1:], None])):
        end = f"{rise}.end" if after is None else f"{after}.start"
        check(
            f"{feature} leg {index} chained",
            await adapter.add_sketch_constraint(f"{leg}.end", end, "coincident"),
        )
    await anchor_point_to_origin(
        adapter, f"{rise}.start", rise_x, top_y, f"{feature} top corner"
    )
    row.record(f"{prefix}RiseX", '"BarLength" / 2')
    row.record(f"{prefix}RiseY", '"BarHeight" / 2')
    await dimension_between(
        adapter,
        f"{rise}.start",
        f"{rise}.end",
        "vertical_distance",
        top_y - row_y,
        f"{feature} height",
    )
    row.record(height_name)
    start = f"{legs[0]}.start"
    await dimension_between(
        adapter, start, "origin", "horizontal_distance", abs(start_x), f"{feature} end"
    )
    row.record(f"{prefix}StartX", '"BarLength" / 2')
    # Each hole ends one leg; the last leg runs on to the rise.
    for leg, (name, _x, station) in zip(legs[:-1], holes, strict=True):
        await dimension_between(
            adapter, start, f"{leg}.end", "horizontal_distance", station, name
        )
        row.record(name)
    await ensure_fully_defined(adapter, f"{feature} sketch")
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return row.apply(adapter, feature)


def _model_to_sketch(
    adapter, model_mm: tuple[float, float, float]
) -> tuple[float, float]:
    """``model_mm`` in the active sketch's own axes (``ModelToSketchTransform``;
    build_dt_cone_pivot_post_tl_bond_cradle's reader), which must hold it."""
    from solidworks_mcp.adapters.com_variant import double_array

    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([v / 1000.0 for v in model_mm])), "IMathPoint"
    )
    moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    x, y, z = (float(v) * 1000.0 for v in moved.ArrayData)
    if abs(z) > 1e-6:
        raise RuntimeError(f"{model_mm} lies {z:g} mm off the active sketch plane")
    return x, y


async def _author_thread_reference(adapter) -> list[tuple[str, str]]:
    """The pivot tap's full-thread minimum as a model dimension: a
    construction line down the tap axis from the back face, in a plane through
    the axis that section A-A cuts on."""
    sketch = SketchDims()
    check(
        "create_sketch PivotThreadReference",
        await adapter.create_sketch(PIVOT_SECTION_PLANE),
    )
    ax, ay = _model_to_sketch(adapter, (PIVOT_TAP_X, HANGER_TAP_Y, BACK_FACE_Z))
    bx, by = _model_to_sketch(
        adapter,
        (PIVOT_TAP_X, HANGER_TAP_Y, BACK_FACE_Z - PIVOT_TAP_FULL_THREAD_MIN),
    )
    if min(abs(ax), abs(ay)) < 1e-6:
        raise RuntimeError(f"the pivot tap mouth maps onto a sketch axis ({ax}, {ay})")
    along_x = abs(bx - ax) > abs(by - ay)
    set_sketch_direct_db(adapter, True)
    line = check("pivot thread line", await adapter.add_line(ax, ay, bx, by))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line, "pivot thread line")
    check(
        "pivot thread line along the tap axis",
        await adapter.add_sketch_constraint(
            line, None, "horizontal" if along_x else "vertical"
        ),
    )
    await anchor_point_to_origin(adapter, f"{line}.start", ax, ay, "pivot tap mouth")
    sketch.record("ThreadMouthU")
    sketch.record("ThreadMouthV")
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "horizontal_distance" if along_x else "vertical_distance",
        PIVOT_TAP_FULL_THREAD_MIN,
        "pivot full thread",
    )
    sketch.record("ThreadMin")
    await ensure_fully_defined(adapter, "PivotThreadReference sketch")
    check("exit_sketch PivotThreadReference", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotThreadReference")
    return sketch.apply(adapter, "PivotThreadReference")


def _single_limit(
    adapter, feature: str, name: str, nominal: float, tol_type: int
) -> None:
    """A dimension printed as a single MIN or MAX limit: SOLIDWORKS prints the
    nominal then the limit word, so the model value is the limit itself."""
    label = f"{name}@{feature}"
    _, dimension = _named_dimension(adapter, feature, name)
    if not math.isclose(float(dimension.SystemValue), nominal / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the limit {nominal:.7f}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = tol_type
    if not tolerance.SetValues(0.0, 0.0) or int(tolerance.Type) != tol_type:
        raise RuntimeError(f"{label}: cannot retain the single limit {tol_type}")
    _telemetry.success(f"{label}: single limit (swTolType {tol_type})")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 452 = 452 in).
    # (The old ClampHoleDia/BracketHoleDia knobs are gone: the screw holes are
    # now native Hole Wizard features whose diameters come from the ANSI-inch
    # clearance/tap tables, not driven dims.)
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile: width along X = length, height along Y; depth extruded along Z.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_HEIGHT / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Height", drive_depth='"BarHeight"',
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")
    name_dimensions(adapter, "Bar", ["Depth"])

    expected = BAR_HEIGHT * BAR_DEPTH * BAR_LENGTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Clamp-screw holes, through along Z at the bar's mid-height, drilled from
    # the bar FRONT face (local z = -BAR_DEPTH/2, where the clamp-screw heads
    # sit -- ch30 p002), while the bar is still a plain prism: one native Hole
    # Wizard feature, 4 clamp-screw #8 COUNTERBORES flanking the columns.
    front_z = -BAR_DEPTH / 2.0
    clamp_dia = CLAMP_HOLE_DIA
    wizard_holes(
        adapter, CLAMP_HOLE_SPEC,
        [[x, 0.0, front_z] for x in CLAMP_HOLE_X],
        (0.0, 0.0, -1.0), "clamp-screw counterbores (#8)", name="ClampHoles",
    )
    v_holes = len(CLAMP_HOLE_X) * (
        math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
        + math.pi
        * ((CLAMP_CBORE_DIA / 2.0) ** 2 - (clamp_dia / 2.0) ** 2)
        * CLAMP_CBORE_DEPTH
    )
    expected -= v_holes
    await volume_check(adapter, "bar with clamp holes", expected, 0.02 * v_holes)

    # Latch hook's base screws: two #4-40 taps THROUGH from the back face (their
    # exits on the front face lie under the platen footprint), then a
    # 90-degree countersink on both mouths of each.
    bracket_dia = blind_cut_dia_mm(BRACKET_TAP_SPEC)
    wizard_holes(
        adapter, BRACKET_TAP_SPEC,
        [[x, HANGER_TAP_Y, BACK_FACE_Z] for x in BRACKET_TAP_X],
        (0.0, 0.0, 1.0),
        f"latch-hook base-screw taps ({BRACKET_TAP_SPEC.size} through)",
        name="BracketTaps",
    )
    r_bracket = bracket_dia / 2.0
    v_bracket = len(BRACKET_TAP_X) * math.pi * r_bracket**2 * BAR_DEPTH
    expected -= v_bracket
    await volume_check(adapter, "bar with bracket taps", expected, 0.03 * v_bracket)
    bracket_csk = (BRACKET_TAP_CSK_DIA - bracket_dia) / 2.0
    check(
        "countersink bracket-tap mouths",
        await adapter.add_chamfer(
            bracket_csk,
            [
                [x + r_bracket, HANGER_TAP_Y, z_face]
                for x in BRACKET_TAP_X
                for z_face in (-BACK_FACE_Z, BACK_FACE_Z)
            ],
        ),
    )
    name_last_feature(adapter, "BracketTapCountersinks")
    v_bracket_csk = (
        2 * len(BRACKET_TAP_X) * math.pi * bracket_csk**2 * (r_bracket + bracket_csk / 3.0)
    )
    expected -= v_bracket_csk
    await volume_check(
        adapter, "bracket-tap countersinks", expected, 0.03 * v_bracket_csk + 0.05
    )

    # Hanger pivot: the #8-32 tap drill is FLAT-bottomed (drill + end mill), so
    # it is a plain blind cut from the back face rather than a wizard tap,
    # whose 118-degree point would eat the floor under it.
    check(
        f"create_plane BackFace (Front Plane, +{BACK_FACE_Z})",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=BACK_FACE_Z)
        ),
    )
    name_last_feature(adapter, "BackFace")
    pivot = SketchDims()
    check("create_sketch pivot tap drill", await adapter.create_sketch("BackFace"))
    await define_circle(
        adapter,
        PIVOT_TAP_X,
        HANGER_TAP_Y,
        PIVOT_TAP_DRILL_DIA / 2.0,
        "pivot tap drill",
        dims=pivot,
        names=("PivotTapX", "PivotTapY", "PivotTapDrillDia"),
        drives=(None, None, None),
    )
    await ensure_fully_defined(adapter, "pivot tap drill sketch")
    check("exit_sketch pivot tap drill", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotTapProfile")
    drive_jobs += pivot.apply(adapter, "PivotTapProfile")
    # BackFace's normal is +Z, out of the bar, so the default cut runs -Z into
    # it.  Reversed, the cut missed the body and flipped its side to cut,
    # leaving 21422 of 88036 mm^3 (run 20261001T011714683Z).
    check(
        "cut pivot tap drill (flat, blind)",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIVOT_TAP_DRILL_DEPTH)
        ),
    )
    name_last_feature(adapter, "PivotTap")
    name_dimensions(adapter, "PivotTap", ["DrillDepth"])
    r_pivot = PIVOT_TAP_DRILL_DIA / 2.0
    v_pivot = math.pi * r_pivot**2 * PIVOT_TAP_DRILL_DEPTH
    expected -= v_pivot
    await volume_check(adapter, "bar with pivot tap drill", expected, 0.03 * v_pivot)
    pivot_csk = (PIVOT_TAP_CSK_DIA - PIVOT_TAP_DRILL_DIA) / 2.0
    check(
        "countersink pivot-tap mouth",
        await adapter.add_chamfer(
            pivot_csk, [[PIVOT_TAP_X + r_pivot, HANGER_TAP_Y, BACK_FACE_Z]]
        ),
    )
    name_last_feature(adapter, "PivotTapCountersink")
    v_pivot_csk = math.pi * pivot_csk**2 * (r_pivot + pivot_csk / 3.0)
    expected -= v_pivot_csk
    await volume_check(
        adapter, "pivot-tap countersink", expected, 0.03 * v_pivot_csk + 0.05
    )

    # Drawing references, hidden in the part (blank_reference_sketches) and
    # shown per view by the drawing: the countersinks' MAX diameters on the
    # back face, the pivot's full-thread MIN down its axis, and each hole row's
    # stations and height.
    countersinks = SketchDims()
    check("create_sketch CountersinkReference", await adapter.create_sketch("BackFace"))
    for x, dia, label, names in (
        (
            PIVOT_TAP_X,
            PIVOT_TAP_CSK_DIA,
            "pivot countersink",
            ("PivotCskX", "PivotCskY", "PivotCskDia"),
        ),
        (
            BRACKET_TAP_X[0],
            BRACKET_TAP_CSK_DIA,
            "bracket countersink",
            ("BracketCskX", "BracketCskY", "BracketCskDia"),
        ),
    ):
        await define_circle(
            adapter,
            x,
            HANGER_TAP_Y,
            dia / 2.0,
            label,
            dims=countersinks,
            names=names,
            drives=(None, None, None),
        )
    await ensure_fully_defined(adapter, "CountersinkReference sketch")
    check("exit_sketch CountersinkReference", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkReference")
    drive_jobs += countersinks.apply(adapter, "CountersinkReference")
    check(
        f"create_plane {PIVOT_SECTION_PLANE} (Right Plane, {PIVOT_TAP_X})",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=PIVOT_TAP_X
            )
        ),
    )
    name_last_feature(adapter, PIVOT_SECTION_PLANE)
    drive_jobs += await _author_thread_reference(adapter)
    drive_jobs += await _author_row(
        adapter,
        "HangerRowReference",
        rise_x=BAR_LENGTH / 2.0,
        row_y=HANGER_TAP_Y,
        start_x=LEFT_END_X,
        holes=tuple(
            zip(
                HANGER_STATION_NAMES,
                (PIVOT_TAP_X, *BRACKET_TAP_X),
                HANGER_STATIONS,
                strict=True,
            )
        ),
        height_name="HangerRowHeight",
        prefix="Hanger",
    )
    drive_jobs += await _author_row(
        adapter,
        "ClampRowReference",
        rise_x=BAR_LENGTH / 2.0,
        row_y=0.0,
        start_x=CLAMP_ROW_START_X,
        holes=tuple(zip(CLAMP_STATION_NAMES, CLAMP_ROW_X, CLAMP_STATIONS, strict=True)),
        height_name="ClampRowHeight",
        prefix="Clamp",
    )
    blank_reference_geometry(
        adapter, (("BackFace", "PLANE"), (PIVOT_SECTION_PLANE, "PLANE"))
    )

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    # The bottom rail's running clearance under the bar spends the height's
    # .XXX band, and the pivot floor and bracket-screw tips the thickness's
    # (pd_support_bar_spec.BAR_HEIGHT_BAND, BAR_DEPTH_BAND), so both live on
    # the model dimensions, read back by the helper, not only in the spec.
    apply_drawing_precision(
        adapter,
        {"BarProfile": {"Height": BAR_BAND_PLACES}, "Bar": {"Depth": BAR_BAND_PLACES}},
    )
    set_dimension_symmetric_tolerance(adapter, "BarProfile", "Height", BAR_HEIGHT_BAND)
    set_dimension_symmetric_tolerance(adapter, "Bar", "Depth", BAR_DEPTH_BAND)

    # The rest of the print's places, then its bands and limits: the hanger
    # holes' row and stations carry the pivot and hook positions'
    # HOLE_POSITION_BAND (paper_drive_geom, transgear_hanger_joints); the
    # pivot drill's depth its spec limits; the full thread and countersinks
    # their single limits.
    apply_drawing_precision(adapter, SHEET_PRECISION)
    for name in ("HangerRowHeight", *HANGER_STATION_NAMES):
        set_dimension_symmetric_tolerance(
            adapter, "HangerRowReference", name, HOLE_POSITION_BAND
        )
    set_dimension_bilateral_tolerance(
        adapter, "PivotTap", "DrillDepth", *PIVOT_TAP_DRILL_DEPTH_LIMITS, places=1
    )
    _single_limit(
        adapter, "PivotThreadReference", "ThreadMin", PIVOT_TAP_FULL_THREAD_MIN, TOL_MIN
    )
    _single_limit(
        adapter, "CountersinkReference", "PivotCskDia", PIVOT_TAP_CSK_DIA, TOL_MAX
    )
    _single_limit(
        adapter, "CountersinkReference", "BracketCskDia", BRACKET_TAP_CSK_DIA, TOL_MAX
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    # The platen's slide faces (top edge, front face) carry their roughness
    # on the MODEL as plain annotations; the drawing points at them.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
