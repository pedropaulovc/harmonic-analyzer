r"""Build the oblique-trammel jig's carrier plate (MHA-CH-06-TL-21; shop fixture).

The plate the rocker blank rides on, carried on two pivot pins
(``ch_rocker_arm_tl_oblique_carrier_spec``; every (calc) value is the
calculator's, ``ch_rocker_arm_tl_oblique_trammel_spec``).

Layout (the carrier frame; SolidWorks model X = carrier X, model Y = carrier
Z, model Z = -carrier Y, so a Top-plane sketch reads carrier (X, Y)):

* the plate is a Top-plane rectangle anchored at its (-X, -Y) corner from the
  origin (the A1-B1 midpoint), extruded down by the finished thickness;
* the four reamed pin holes are one Top-plane sketch: A1 from the origin, B1
  from A1 by the spacing D1, A2 from A1 and B2 from B1 by their (dX, dY)
  chains, cut through;
* the pin holes' underside edges carry only the title block's edge break
  (owner ruling 2026-11-13: no chamfer; the purchased spacer seats on the
  broken edge). The hidden ``SectionReference``, on ``SectionAPlane``
  (coincident with the Front plane: the A1-B1 pin line), carries the
  finished thickness the drawing's edge view prints, driven from Plate's
  depth, its line on the plate's -X end face;
* ``StationReference`` retains the unchanged hidden model baseline drivers;
  only EdgeX prints as a dimension. The drawing's native hole table reads
  the actual hole axes from A1; the tap placements stay origin-based;
* the CL and CR end-clamp taps (``ClTap``, ``CrTap``), the HUB clamp tap
  (``HubTap``), the riser and the feed-lever taps are UNC Hole Wizard
  features from the top face, through; the three clamp taps are the
  ordinary #8-32 of the common clamp screw;
* each pin hole carries a hidden reference axis (``PIN_HOLE_AXES``), two
  offset planes' intersection, which the jig assembly mates on.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_carrier.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
from _bore_axis import name_bore_axis
from _check import check
from _com import _bind, _early_bound
from _dimensions import drive_dimension, name_dimensions
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
)
from _feature_tree import _feature_by_name, name_last_feature
from _fit_deviations import deviations
from _holes import SharedCoordinate, wizard_holes
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    anchor_point_to_point,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_oblique_carrier_spec import (
    CLAMP_SPEC,
    CLAMP_TAP_DRILL,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    LEVER_HOLES,
    LEVER_SPEC,
    LEVER_TAP_DRILL,
    END_CLAMPS,
    HUB,
    HUB_SPEC,
    OUTLINE_X,
    OUTLINE_Y,
    PIN_HOLE_AXES,
    PIN_HOLE_BAND,
    PIN_HOLE_DIA,
    PIN_HOLES,
    PLATE_LENGTH,
    PLATE_WIDTH,
    OUTER_Y_DEVIATIONS,
    OUTER_Y_NOTE,
    RISER_SCREWS,
    RISER_SPEC,
    REFERENCE_SKETCHES,
    RISER_TAP_DRILL,
    STATION_REFERENCE,
    STATIONS,
    THICKNESS,
    SECTION_PLANE,
    SECTION_REFERENCE,
    UNIT,
)

PART_NAME = "ch-rocker-arm-tl-oblique-carrier"
# The registry row prints 6061-T6511 aluminium (the owned 1/2 x 6 bar).
MATERIAL = "6061 Alloy"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
    "Outer Pin Row Note",
)

THROUGH_CUT_DEPTH = 2.0 * (THICKNESS + 1.0)
_UP = (0.0, 1.0, 0.0)  # the top face's outward normal (model +Y)

_R_PIN = PIN_HOLE_DIA / 2.0
V_PLATE = PLATE_LENGTH * PLATE_WIDTH * THICKNESS
V_PINS = len(PIN_HOLES) * math.pi * _R_PIN**2 * THICKNESS


def _top(point: tuple[float, float]) -> list[float]:
    """Carrier (X, Y) on the top face as model mm."""
    return [point[0], 0.0, -point[1]]


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign)
    (build_ch_rocker_arm_tl_trammel_pivot_plate's mapper)."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


def _add_point(adapter, point: tuple[float, float], label: str) -> str:
    """One sketch point straight into the sketch DB (no inference snap),
    registered for the adapter's dimension refs (build_dt_pinion_lever)."""
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


def _origin_x(station: str) -> str:
    """An origin-based |X| placement from its hidden A1 baseline driver."""
    a1x = _pin_dim("A1X")
    printed = f'"{station}@{STATION_REFERENCE}"'
    if STATIONS[station][0] < 0.0:
        return f"{a1x} - {printed}"
    return f"{printed} - {a1x}"


async def _station_reference(adapter) -> list[tuple[str, str]]:
    """Retain the original A1-based geometry drivers without printing chains.

    A Hole Wizard placement sketch cannot carry a datum point. This point-only
    owner supplies its baseline drivers and the one surviving EdgeX dimension.
    The hole table reads physical edges; none of these hidden points is its
    datum or a replacement for a hole.
    """
    stations = SketchDims()
    check("create_sketch station reference", await adapter.create_sketch("Top"))
    a1 = PIN_HOLES["A1"]
    origin = _add_point(adapter, a1, "A1 station")
    await anchor_point_to_origin(adapter, origin, *a1, "A1 station")
    stations.record("StationA1X", _pin_dim("A1X"))
    x_drives = {
        "EdgeX": '"PlateHalfLength@PlateProfile" - ' + _pin_dim("A1X"),
        "LeverX": _pin_dim("A1X"),
    }
    y_drives = {"EdgeX": '"PlateNearY@PlateProfile"'}
    for name, point in STATIONS.items():
        target = _add_point(adapter, point, f"{name} station")
        await anchor_point_to_point(
            adapter,
            origin,
            target,
            point[0] - a1[0],
            point[1] - a1[1],
            f"{name} from A1",
        )
        stations.record(name, x_drives.get(name))
        stations.record(f"{name}Rise", y_drives.get(name))
    await ensure_fully_defined(adapter, "station reference sketch")
    check("exit_sketch station reference", await adapter.exit_sketch())
    name_last_feature(adapter, STATION_REFERENCE)
    return stations.apply(adapter, STATION_REFERENCE)


def _pin_dim(name: str) -> str:
    return f'"{name}@PinHoleProfile"'


# Each pin-hole axis's |X| and |Y| offsets from the PinHoleProfile chain
# (_pin_holes): A1 at -A1X, B1 PinSpacing on, A2/B2 out by their dX and up by
# their dY. ``name_bore_axis`` ignores the Y drive on the Y = 0 holes.
_PIN_AXIS_DRIVES = {
    "A1": (_pin_dim("A1X"), None),
    "B1": (f"{_pin_dim('PinSpacing')} - {_pin_dim('A1X')}", None),
    "A2": (f"{_pin_dim('A1X')} + {_pin_dim('A2DX')}", _pin_dim("A2DY")),
    "B2": (
        f"{_pin_dim('PinSpacing')} - {_pin_dim('A1X')} + {_pin_dim('B2DX')}",
        _pin_dim("B2DY"),
    ),
}
_A1, _B1, _A2, _B2 = (PIN_HOLES[key] for key in ("A1", "B1", "A2", "B2"))
if not (
    _A1[0] < 0.0 < _B1[0]
    and _A2[0] < _A1[0]
    and _B2[0] > _B1[0]
    and _A1[1] == _B1[1] == 0.0
    and _A2[1] > 0.0
    and _B2[1] > 0.0
):
    raise AssertionError("the pin-axis drives no longer match the hole chain's signs")


async def _pin_holes(adapter, dims: SketchDims) -> None:
    """A1 from the origin (half the spacing, driven), B1 from A1 by D1, A2
    from A1 and B2 from B1 by their (dX, dY) chains (one Top-plane sketch)."""
    a1, b1, a2, b2 = (PIN_HOLES[k] for k in ("A1", "B1", "A2", "B2"))
    first = await define_circle(
        adapter,
        *a1,
        _R_PIN,
        "pin hole A1",
        dims=dims,
        names=("A1X", None, "PinHoleDia"),
        drives=('"PinSpacing@PinHoleProfile" / 2', None, None),
    )
    centres = {"A1": first}
    for key, point, base, chain_names in (
        ("B1", b1, "A1", ("PinSpacing",)),
        ("A2", a2, "A1", ("A2DX", "A2DY")),
        ("B2", b2, "B1", ("B2DX", "B2DY")),
    ):
        sketch_mgr = adapter.currentSketchManager
        previous_add_to_db = bool(sketch_mgr.AddToDB)
        sketch_mgr.AddToDB = True
        try:
            circle = await adapter.add_circle(*point, _R_PIN)
            check(f"add_circle pin hole {key}", circle)
        finally:
            sketch_mgr.AddToDB = previous_add_to_db
        origin = PIN_HOLES[base]
        await anchor_point_to_point(
            adapter,
            f"{centres[base]}.center",
            f"{circle.data}.center",
            point[0] - origin[0],
            point[1] - origin[1],
            f"pin hole {key} from {base}",
        )
        for name in chain_names:
            dims.record(name)
        check(
            f"dimension pin hole {key} diameter",
            await adapter.add_sketch_dimension(
                circle.data, None, "diameter", PIN_HOLE_DIA
            ),
        )
        dims.record(f"PinHoleDia{key}", '"PinHoleDia@PinHoleProfile"')
        centres[key] = circle.data


def _section_plane(adapter) -> None:
    """Section A-A's cutting plane, named and hidden: coincident with the
    Front plane (model Z = 0, the A1-B1 pin line). An offset plane cannot sit
    at zero offset, so it is InsertRefPlane's Coincident constraint on the
    selected Front plane (build_dt_cone_pivot_post's mate planes); a sketch on
    it keeps the Front plane's axes, which ``_sketch_mapper`` checks."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        "Front Plane", "PLANE", 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"plane {SECTION_PLANE}: cannot select the Front plane")
    feature_manager = _early_bound(model.FeatureManager, "IFeatureManager")
    # swRefPlaneReferenceConstraint_Coincident = 4
    if feature_manager.InsertRefPlane(4, 0.0, 0, 0.0, 0, 0.0) is None:
        raise RuntimeError(f"plane {SECTION_PLANE}: InsertRefPlane failed")
    model.ClearSelection2(True)
    name_last_feature(adapter, SECTION_PLANE)
    blank_reference_geometry(adapter, ((SECTION_PLANE, "PLANE"),))


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name SECTION_PLANE (build_pd_platen)."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if SECTION_PLANE not in parents:
        raise RuntimeError(f"{sketch} is not on {SECTION_PLANE}: parents {parents}")


async def _section_reference(adapter) -> list[tuple[str, str]]:
    """The hidden sketch section A-A imports, on SECTION_PLANE.

    SECTION_PLANE is coincident with the Front plane, model Z = 0, the A1-B1
    pin line, so section A-A cuts along it. A partial section imports a hidden
    sketch in its plane but not Plate's depth (jig-r4/r5), so this sketch
    carries the printed thickness: one vertical construction line on the
    plate's -X end face: its top on the top face (a horizontal-points
    relation to the origin) and its station from the origin driven from
    PlateHalfLength, vertical, and its length (printed) driven from Plate's
    depth. On the end face the drawing's edge view draws it under the
    plate's own outline: inside the plate (A1's +X wall, for the retired
    section A-A) it printed as a stray dashed line across the edge view
    (machinist review, run 20261114T064216453Z-bf464d35, FIX).
    """
    feature = SECTION_REFERENCE
    _section_plane(adapter)
    check(f"create_sketch {feature}", await adapter.create_sketch(SECTION_PLANE))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=feature)
    dims = SketchDims()
    x_stock = OUTLINE_X[0]
    top = to_sketch((x_stock, 0.0, 0.0))
    bottom = to_sketch((x_stock, -THICKNESS, 0.0))
    set_sketch_direct_db(adapter, True)
    stock = check(f"{feature} stock line", await adapter.add_line(*top, *bottom))
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[stock], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not segment.ConstructionGeometry:
        raise RuntimeError(f"{feature}: stock line construction flag rejected")
    await anchor_point_to_origin(
        adapter, f"{stock}.start", *top, f"{feature} stock line on the top face"
    )
    dims.record("StockLineX", '"PlateHalfLength@PlateProfile"')
    check(
        f"vertical {feature} stock line",
        await adapter.add_sketch_constraint(stock, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{stock}.start",
        f"{stock}.end",
        "vertical_distance",
        THICKNESS,
        f"{feature} finished thickness",
    )
    dims.record("StockThick", '"PlateThick@Plate"')
    await ensure_fully_defined(adapter, feature)
    check(f"exit_sketch {feature}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    _require_on_section_plane(adapter, feature)
    return dims.apply(adapter, feature)


def _author_outer_pin_rows(adapter) -> None:
    """Author the flagged limits on the unchanged, unprinted geometric drivers."""
    for dimension_name in ("A2DY", "B2DY"):
        # Preserve the irrational nominal: shift native limits to printed .964,
        # without rounding a displayed deviation or moving the model geometry.
        _, dimension = _named_dimension(adapter, "PinHoleProfile", dimension_name)
        dimension = _early_bound(_bind(dimension, "IDimension"), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        tolerance.Type = 2  # swTolBILAT
        lower, upper = (value / 1000.0 for value in OUTER_Y_DEVIATIONS)
        if not tolerance.SetValues(lower, upper):
            raise RuntimeError(f"{dimension_name}: local row limits rejected")
        if (
            int(tolerance.Type) != 2
            or abs(float(tolerance.GetMinValue()) - lower) > 1e-12
            or abs(float(tolerance.GetMaxValue()) - upper) > 1e-12
        ):
            raise RuntimeError(f"{dimension_name}: local row limits changed")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # --- Plate: Top-plane rectangle, extruded down by the stock -------------
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    points = [
        (OUTLINE_X[0], OUTLINE_Y[0]),
        (OUTLINE_X[1], OUTLINE_Y[0]),
        (OUTLINE_X[1], OUTLINE_Y[1]),
        (OUTLINE_X[0], OUTLINE_Y[1]),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        anchor=0,
        label="plate profile",
        dims=plate,
        names=["PlateLength", "PlateWidth", "PlateHalfLength", "PlateNearY"],
        drives=[None, None, '"PlateLength@PlateProfile" / 2', None],
    )
    await ensure_fully_defined(adapter, "plate profile")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs = plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Plate")
    name_dimensions(adapter, "Plate", ["PlateThick"])
    volume = await volume_check(adapter, "plate", V_PLATE, 0.002 * V_PLATE)

    # --- Pivot-pin holes, reamed through ------------------------------------
    pins = SketchDims()
    check("create_sketch pin holes", await adapter.create_sketch("Top"))
    await _pin_holes(adapter, pins)
    await ensure_fully_defined(adapter, "pin holes")
    check("exit_sketch pin holes", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pins.apply(adapter, "PinHoleProfile")
    check(
        "cut pin holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHoles")
    volume = await volume_check(adapter, "pin holes", volume - V_PINS, 0.01 * V_PINS)

    # --- Section A-A's hidden thickness reference ----------------------------
    # The pin holes' underside edges carry the title block's edge break only.
    drive_jobs += await _section_reference(adapter)

    # --- X stations from A1 ---------------------------------------------------
    # The printed baselines first: the hidden sketch of points that drives
    # every tap X placement, ahead of them in the tree.
    drive_jobs += await _station_reference(adapter)

    # --- Taps from the top face, through ------------------------------------
    # The CL and CR end clamps: one ordinary #8-32 feature each, X from its
    # printed station, Y from the pin line.
    for key, point in END_CLAMPS.items():
        prefix = key.title()
        clamp = wizard_holes(
            adapter,
            CLAMP_SPEC,
            [_top(point)],
            _UP,
            f"{key} clamp tap ({CLAMP_SPEC.size})",
            name=f"{prefix}Tap",
            expect_dia_mm=CLAMP_TAP_DRILL,
            placement_dims=[
                ((f"{prefix}XOrigin", _origin_x(f"{prefix}X")), (f"{prefix}Y", None)),
            ],
        )
        drive_jobs += clamp.placement_drive_jobs
        v_clamp = math.pi * (clamp.hole_dia_mm / 2.0) ** 2 * THICKNESS
        volume = await volume_check(
            adapter, f"{key} tap", volume - v_clamp, 0.03 * v_clamp
        )

    # The HUB clamp: on the origin's X, so its placement takes the origin-axis
    # relation; its unmarked HubY places it. The sheet prints no HUB station:
    # it is made in situ at the assembly's HUB setting (HUB_TAP_CALLOUT).
    hub = wizard_holes(
        adapter,
        HUB_SPEC,
        [_top(HUB)],
        _UP,
        f"HUB clamp tap ({HUB_SPEC.size})",
        name="HubTap",
        expect_dia_mm=CLAMP_TAP_DRILL,
        placement_dims=[((None, None), ("HubY", None))],
    )
    drive_jobs += hub.placement_drive_jobs
    v_hub = math.pi * (hub.hole_dia_mm / 2.0) ** 2 * THICKNESS
    volume = await volume_check(adapter, "HUB tap", volume - v_hub, 0.03 * v_hub)

    riser = wizard_holes(
        adapter,
        RISER_SPEC,
        [_top(point) for point in RISER_SCREWS],
        _UP,
        f"riser screw taps ({RISER_SPEC.size})",
        name="RiserTaps",
        expect_dia_mm=RISER_TAP_DRILL,
        placement_dims=[
            (("RiserX1Origin", _origin_x("RiserX1")), ("RiserY1", None)),
            (("RiserX1ROrigin", _origin_x("RiserX1R")), SharedCoordinate(0)),
            (("RiserX2Origin", _origin_x("RiserX2")), ("RiserY2", None)),
            (("RiserX2ROrigin", _origin_x("RiserX2R")), SharedCoordinate(2)),
        ],
    )
    drive_jobs += riser.placement_drive_jobs
    v_riser = len(RISER_SCREWS) * math.pi * (riser.hole_dia_mm / 2.0) ** 2 * THICKNESS
    volume = await volume_check(adapter, "riser taps", volume - v_riser, 0.03 * v_riser)

    lever = wizard_holes(
        adapter,
        LEVER_SPEC,
        [_top(point) for point in LEVER_HOLES],
        _UP,
        f"feed lever taps ({LEVER_SPEC.size})",
        name="LeverTaps",
        expect_dia_mm=LEVER_TAP_DRILL,
        placement_dims=[
            ((None, None), ("LeverY1", None)),
            ((None, None), ("LeverY2", None)),
        ],
    )
    v_lever = len(LEVER_HOLES) * math.pi * (lever.hole_dia_mm / 2.0) ** 2 * THICKNESS
    volume = await volume_check(adapter, "lever taps", volume - v_lever, 0.03 * v_lever)
    _require_one_solid_body(adapter, label="carrier")
    # Model X = carrier X and model Z = -carrier Y: each axis is a Right-plane
    # offset by its X and a Front-plane offset by its -Y, each offset driven by
    # the PinHoleProfile dimensions that place its hole (an offset plane's
    # distance is unsigned), so an edit of the holes moves the jig's mate axes.
    for hole, (x, y) in PIN_HOLES.items():
        drive_x, drive_y = _PIN_AXIS_DRIVES[hole]
        await name_bore_axis(
            adapter,
            "Right Plane",
            x,
            "Front Plane",
            -y,
            f"pin hole {hole}",
            drive_a=drive_x,
            drive_b=drive_y,
            drive_jobs=drive_jobs,
        )
        name_last_feature(adapter, PIN_HOLE_AXES[hole])

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven carrier (equations neutral)", volume, 0.002 * V_PLATE
    )
    _require_one_solid_body(adapter, label="driven carrier")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # Rule 4: the reamed pin holes; the band is millimetres, UNIT prints it
    # in inches at the nominal's four places (+.0020/+.0010: inch tolerances
    # carry the dimension's places, ASME Y14.5 inch practice). The native table
    # owns every location at the title block.
    set_dimension_bilateral_tolerance(
        adapter,
        "PinHoleProfile",
        "PinHoleDia",
        *deviations(PIN_HOLE_BAND),
        places=DRAWING_PRECISION["PinHoleProfile"]["PinHoleDia"],
        display_unit=UNIT,
    )
    # Owner's flagged .964 ±.002 control: unchanged geometric nominal,
    # actual native limits shifted to the printed nominal, never a draw edit.
    _author_outer_pin_rows(adapter)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Outer Pin Row Note": OUTER_Y_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
