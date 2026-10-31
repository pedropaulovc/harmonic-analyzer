r"""Build the oblique-trammel jig's acetal riser (MHA-CH-06-TL-24; shop fixture).

The faced and milled 6 x 40 x 340 acetal blank with its seven through holes
(``ch_rocker_arm_tl_oblique_riser_spec``). The self-cut band is not modelled.

Layout (the spec's model frame, +Z up): the blank is a Front-plane rectangle
from the origin, extruded +Z by the thickness; the HUB, CL and CR holes are
Front-plane circles cut through, and the four #4 screw holes are one native
Hole Wizard clearance feature from the top face. The 82 degree countersinks
are revolved cuts
sketched on planes through the screw rows (offsets of the Top plane at each
row's Y), each a triangle from the top face to its cone's apex, as the
rocker trammel pivot plate's; its few helpers are copied here as private
functions, since that kit is being retired.

The printed screw-hole size lives in the blanked ``ScrewHoleReference``
sketch on ``TopFace``, as build_pd_transgear_arm_plate's
``CountersinkReference``; its callout carries the countersink. The plan
cannot carry a native hole callout, because the only visible edges of the
screw holes there belong to the revolved countersinks
(``GetHoleCalloutVariables`` raised DISP_E_BADVARTYPE, farm run jig-r3; the
wizard's own bottom rims are hidden, jig-r4).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_oblique_riser.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
import _telemetry
from _check import check
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _saved_part_guard import require_saved_drawing_properties
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _visibility import blank_reference_geometry
from _holes import SharedCoordinate, wizard_holes
from ch_rocker_arm_tl_oblique_riser_spec import (
    BLANK_LENGTH,
    BLANK_WIDTH,
    CIRCLES,
    CSK_DIA,
    CSK_FLANK_ANGLE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRILLED_BAND,
    GLOBALS,
    ISOMETRIC_VIEW_NOTE,
    SCREW_DIA,
    SCREW_DIA_PRINTED,
    SCREW_HOLES,
    SCREW_SPEC,
    THICKNESS,
)

PART_NAME = "ch-rocker-arm-tl-oblique-riser"
# SolidWorks database plastic nearest the acetal (Delrin) blank.
MATERIAL = "POM Acetal Copolymer"
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

AXIS_OVERRUN = 2.0
THROUGH_CUT_DEPTH = 2.0 * THICKNESS


def _cone_cut_volume(mouth_r: float, flank_deg: float, bore_r: float) -> float:
    """A cone from a mouth on the face to its apex on the axis, less the part
    of it a coaxial bore (deeper than the apex) has already removed."""
    rise = math.tan(math.radians(flank_deg))
    cone = math.pi * mouth_r**2 * (mouth_r * rise) / 3.0
    inside_bore = 2.0 * math.pi * rise * (mouth_r * bore_r**2 / 2.0 - bore_r**3 / 3.0)
    return cone - inside_bore


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
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    A plane's sketch axes are SolidWorks' choice; the profile points go
    through ``ModelToSketchTransform`` so only the orientation (which
    relations read horizontal/vertical) is assumed, and it is checked here
    (build_pd_transgear_arm_plate's mapper). Coordinates are rounded to the
    nanometre so axis-parallel segments compare equal.
    """
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


V_BLANK = BLANK_LENGTH * BLANK_WIDTH * THICKNESS
V_HOLES = sum(math.pi * (dia / 2.0) ** 2 * THICKNESS for _xy, dia, _n, _d in CIRCLES)
V_CSK = _cone_cut_volume(CSK_DIA / 2.0, CSK_FLANK_ANGLE, SCREW_DIA / 2.0)

# The screw rows: (plane name, row Y, Y global), the countersinks on each.
_ROW_PLANES = (
    ("ScrewInnerPlane", SCREW_HOLES[0][1], '"ScrewInnerY"'),
    ("ScrewOuterPlane", SCREW_HOLES[2][1], '"ScrewOuterY"'),
)
# The printed size's reference circle: (screw index, dia, names, drives),
# round screw 2, where the one hole callout's leader lands.
_REFERENCE_CIRCLES = (
    (
        1,
        SCREW_DIA_PRINTED,
        ("ScrewRefX", "ScrewRefY", "ScrewDia"),
        '"Screw2X"',
        '"ScrewDia"',
    ),
)
REFERENCE_SKETCH = "ScrewHoleReference"
# Blanked before the save; the drawing shows it in the plan only.
REFERENCE_SKETCHES = ("ScrewHoleReference",)


def _add_flank_reference(
    adapter: Any,
    face: str,
    flank: str,
    text_model_mm: tuple[float, float, float],
    text_sketch_mm: tuple[float, float],
    label: str,
    *,
    expected_degrees: float,
) -> None:
    """Add a DRIVEN face-to-flank angle, its text steered into the wedge.

    ``AddSpecificDimension`` reads its text point in MODEL space and picks the
    angle region holding it (build_dt_cone_pivot_post's plan incline). The
    shared ``add_angular_reference_dimension`` passes z = 0, which is right on
    a Front-parallel sketch (the pivot plate's, the carrier's spots) but on
    this Top-parallel row plane lands on the bottom face, below the apex, and
    reads the 131 degree supplement (farm run jig-r2). As the cone post does,
    the point carries the sketch v in the Y slot and the model Z in the Z slot,
    so it lands in the wedge whether SolidWorks reads it in sketch or model
    space (Y is the plane normal and projects away). Sketch u is model X here;
    the check below holds that.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    if abs(text_sketch_mm[0] - text_model_mm[0]) > 1e-6:
        raise RuntimeError(f"{label}: sketch u is not model X on this plane")
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [face, flank], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_model_mm[0] / 1000.0,
        text_sketch_mm[1] / 1000.0,
        text_model_mm[2] / 1000.0,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    dimension.DrivenState = 1  # swDimensionDrivenState_e.swDimensionDriven
    if int(_read_member(dimension, "DrivenState")) != 1:
        raise RuntimeError(f"{label}: angular dimension did not become driven")
    actual = math.degrees(abs(float(_read_member(dimension, "SystemValue"))))
    if abs(actual - expected_degrees) > 1e-6:
        raise RuntimeError(
            f"{label}: angular dimension readback {actual:.6f} deg "
            f"!= {expected_degrees:.6f} deg"
        )
    _telemetry.success(f"angular reference dim {label}: {expected_degrees:.3f} deg")


async def _countersink(
    adapter: Any,
    *,
    index: int,
    plane: str,
    x: float,
    y: float,
    x_drive: str,
) -> list[tuple[str, str]]:
    """Revolve-cut one 82 degree countersink on ``plane`` (model Y = ``y``):
    mouth on the top face at model X = ``x``, apex on the hole axis below.

    The pivot plate's ``_cone_cut`` profile and dimensioning, in this part's
    +Z-up frame: axis-top P0 -> mouth P1 -> apex P2 -> P0, a centerline up
    past the face as the revolve axis, the cone depth driven from the mouth
    diameter and a driven face-to-flank reference proving the flank.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    label = f"countersink {index}"
    suffix = "" if index == 1 else str(index)
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=2, label=label)
    origin = to_sketch((0.0, y, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{label}: sketch origin maps to {origin}")
    mouth_r = CSK_DIA / 2.0
    drop = mouth_r * math.tan(math.radians(CSK_FLANK_ANGLE))
    profile = [
        to_sketch((x, y, THICKNESS)),
        to_sketch((x + mouth_r, y, THICKNESS)),
        to_sketch((x, y, THICKNESS - drop)),
    ]
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{label} axis",
        await adapter.add_centerline(
            *profile[0], *to_sketch((x, y, THICKNESS + AXIS_OVERRUN))
        ),
    )
    lines = await add_line_chain(adapter, profile)
    set_sketch_direct_db(adapter, False)
    face, flank, axis_side = lines
    for i in range(len(lines)):
        check(
            f"{label} junction {i}",
            await adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    for first, second, relation in (
        (face, None, "horizontal"),
        (axis_side, None, "vertical"),
        (axis, None, "vertical"),
        (f"{axis}.start", f"{face}.start", "coincident"),
    ):
        check(
            f"{label} {relation} {first}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    await dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "horizontal_distance",
        abs(profile[0][0]),
        f"{label} station",
    )
    dims.record(f"Csk{index}X", x_drive)
    await dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "vertical_distance",
        abs(profile[0][1]),
        f"{label} on the top face",
    )
    dims.record(f"Csk{index}Face", '"BlankThick"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{flank}.start",
        to_sketch((x + mouth_r, y, THICKNESS + 3.0)),
        f"{label} mouth diameter",
    )
    dims.record(f"Csk{index}Dia", '"CskDia"')
    await dimension_between(
        adapter,
        f"{flank}.start",
        f"{flank}.end",
        "vertical_distance",
        drop,
        f"{label} cone depth",
    )
    dims.record(
        f"Csk{index}ConeDepth", f'"CskDia" / 2 / tan({90.0 - CSK_FLANK_ANGLE:g})'
    )
    # Text on the wedge's bisector at the mouth vertex, inside the profile.
    bisector = math.radians(180.0 + CSK_FLANK_ANGLE / 2.0)
    reach = 0.5 * mouth_r
    text_model = (
        x + mouth_r + reach * math.cos(bisector),
        y,
        THICKNESS + reach * math.sin(bisector),
    )
    _add_flank_reference(
        adapter,
        face,
        flank,
        text_model,
        to_sketch(text_model),
        f"{label} face-to-flank angle",
        expected_degrees=CSK_FLANK_ANGLE,
    )
    dims.record(f"CskFlankAngle{suffix}")
    check(
        f"{label} axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", AXIS_OVERRUN),
    )
    dims.record(f"Csk{index}AxisLength")
    await ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    sketch_name = f"CountersinkProfile{index}"
    name_last_feature(adapter, sketch_name)
    jobs = dims.apply(adapter, sketch_name)
    check(
        f"revolve-cut {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, f"Countersink{index}")
    return jobs


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)
    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units (inch here).
    for name, value in GLOBALS.items():
        await set_global(adapter, name, f"{value}mm")

    # --- Blank: Front-plane rectangle from the origin, extruded +Z ---------
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Front"))
    to_front = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="blank profile")
    points = [
        to_front((0.0, 0.0, 0.0)),
        to_front((BLANK_LENGTH, 0.0, 0.0)),
        to_front((BLANK_LENGTH, BLANK_WIDTH, 0.0)),
        to_front((0.0, BLANK_WIDTH, 0.0)),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="blank profile",
        dims=blank,
        names=["BlankLength", "BlankWidth"],
        drives=['"BlankLength"', '"BlankWidth"'],
    )
    await ensure_fully_defined(adapter, "blank profile")
    check("exit_sketch blank", await adapter.exit_sketch())
    name_last_feature(adapter, "BlankProfile")
    drive_jobs = blank.apply(adapter, "BlankProfile")
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Blank")
    drive_jobs.append(
        (name_dimensions(adapter, "Blank", ["BlankThick"])[0], '"BlankThick"')
    )
    volume = await volume_check(adapter, "blank", V_BLANK, 0.002 * V_BLANK)

    # --- HUB, CL and CR plain clearance holes at the calculator stations ----
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    to_front = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="holes")
    for (x, y), dia, names, drives in CIRCLES:
        await define_circle(
            adapter,
            *to_front((x, y, 0.0)),
            dia / 2.0,
            f"{names[0]} hole",
            dims=holes,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "hole sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Holes")
    volume = await volume_check(adapter, "holes", volume - V_HOLES, 0.01 * V_HOLES)

    # --- Four #4 clearance holes: ONE native wizard feature from the top ---
    # The second hole of each row ties its Y to the first's (one printed row).
    screws = wizard_holes(
        adapter,
        SCREW_SPEC,
        [[x, y, THICKNESS] for x, y in SCREW_HOLES],
        (0.0, 0.0, 1.0),
        "riser screw holes (#4 clearance through)",
        name="ScrewHoles",
        expect_dia_mm=SCREW_DIA,
        placement_dims=[
            (("Screw1X", '"Screw1X"'), ("ScrewInnerY", '"ScrewInnerY"')),
            (("Screw2X", '"Screw2X"'), SharedCoordinate(0)),
            (("Screw3X", '"Screw3X"'), ("ScrewOuterY", '"ScrewOuterY"')),
            (("Screw4X", '"Screw4X"'), SharedCoordinate(2)),
        ],
    )
    drive_jobs += screws.placement_drive_jobs
    v_screws = len(SCREW_HOLES) * math.pi * (screws.hole_dia_mm / 2.0) ** 2 * THICKNESS
    volume = await volume_check(
        adapter, "screw holes", volume - v_screws, 0.01 * v_screws
    )
    # The sheet prints ScrewDia, a reference circle, not the wizard's cut: the
    # cut must lie in the printed size's DRILLED HOLES band.
    if not (
        SCREW_DIA_PRINTED
        <= round(screws.hole_dia_mm, 6)
        <= SCREW_DIA_PRINTED + DRILLED_BAND[0]
    ):
        raise RuntimeError(
            f"wizard cut Ø{screws.hole_dia_mm:.4f} is outside the printed "
            f"Ø{SCREW_DIA_PRINTED} +{DRILLED_BAND[0]}/0"
        )

    # --- Planes through the two screw rows ----------------------------------
    for plane, y, y_drive in _ROW_PLANES:
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=y)
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append(
            (name_dimensions(adapter, plane, [f"{plane}Offset"])[0], y_drive)
        )
    blank_reference_geometry(adapter, tuple((p, "PLANE") for p, _y, _d in _ROW_PLANES))

    # --- 82 degree countersinks on the four screw holes ---------------------
    for index, ((x, y), x_drive) in enumerate(
        zip(
            SCREW_HOLES,
            ('"Screw1X"', '"Screw2X"', '"Screw3X"', '"Screw4X"'),
            strict=True,
        ),
        start=1,
    ):
        plane = next(p for p, row_y, _d in _ROW_PLANES if row_y == y)
        drive_jobs += await _countersink(
            adapter, index=index, plane=plane, x=x, y=y, x_drive=x_drive
        )
        volume = await volume_check(
            adapter, f"countersink {index}", volume - V_CSK, 0.03 * V_CSK + 0.05
        )
    _require_one_solid_body(adapter, label="riser")

    # --- REFERENCE sketch: the printed hole and countersink Ø on the top face -
    check(
        "create_plane TopFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=THICKNESS
            )
        ),
    )
    name_last_feature(adapter, "TopFace")
    drive_jobs.append(
        (name_dimensions(adapter, "TopFace", ["TopFaceOffset"])[0], '"BlankThick"')
    )
    blank_reference_geometry(adapter, (("TopFace", "PLANE"),))
    reference = SketchDims()
    check(f"create_sketch {REFERENCE_SKETCH}", await adapter.create_sketch("TopFace"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=REFERENCE_SKETCH)
    for screw, dia, names, x_drive, dia_drive in _REFERENCE_CIRCLES:
        x, y = SCREW_HOLES[screw]
        await define_circle(
            adapter,
            *to_top((x, y, THICKNESS)),
            dia / 2.0,
            f"{names[2]} reference",
            dims=reference,
            names=names,
            drives=(x_drive, '"ScrewInnerY"', dia_drive),
        )
    await ensure_fully_defined(adapter, f"{REFERENCE_SKETCH} sketch")
    check(f"exit_sketch {REFERENCE_SKETCH}", await adapter.exit_sketch())
    name_last_feature(adapter, REFERENCE_SKETCH)
    drive_jobs += reference.apply(adapter, REFERENCE_SKETCH)

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven riser (equations neutral)", volume, 0.002 * V_BLANK
    )
    _require_one_solid_body(adapter, label="driven riser")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # No model band: every hole prints DRILL THRU under the title block's
    # DRILLED HOLES row.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter, PART_NAME, {"Isometric View Note": ISOMETRIC_VIEW_NOTE}
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
