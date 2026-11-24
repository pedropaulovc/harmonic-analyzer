r"""Reproduction script: transgear arm plate (MHA-PD-19; ch. 23; 1 used).

The flat steel plate screwed across the MHA-PD-18 arm by two MHA-PD-VN-56
oval-head screws: it holds the MHA-PD-28 knob bush, pressed into its hole on
axis K, which carries the knob shaft's running bore and both thrust faces
(``pd_transgear_arm_plate_geometry``; the sheet's contract is
``pd_transgear_arm_plate_spec``).

Layout (part frame of ``pd_transgear_arm_plate_geometry``: origin on K at
face A, the Front Plane, which seats on the arm's rear face; +X/+Y the
arm's axes; +Z to the rear):

* ``PlateOutline`` (Front plane): the ``END_R`` end round about K, each side edge
  parallel to the long axis down to its kink [INFERENCE] and straight on to
  tangency with the round (symmetric about K), the top edge on the arm's
  upper edge; extruded ``THICKNESS_OVER_ARM`` toward +Z as ``Plate``.
* ``PressHole``: the bush's reamed press hole through on K, a cut like the
  other reamed holes; ``PressHoleChamfer`` its face-A mouth's 45° lead-in.
* ``ScrewHoles``: two drilled clearance holes through, over the arm's taps.
* ``Countersink1`` / ``Countersink2``: the 82-degree seats of the oval heads,
  revolved cuts sketched on ``ScrewHolePlane`` (y through both hole axes).
* ``CountersinkReference`` (blanked, on ``RearFace``, round the +X hole): the
  printed countersink Ø; the revolved cuts' own profiles lie edge-on to the plan.

Datums (all blanked): ``Axis1`` press hole, ``Axis2``/``Axis3`` screw holes
(-X, +X); planes ``RearFace`` (z = THICKNESS_OVER_ARM) and
``ScrewHolePlane``; the Front Plane is face A.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_arm_plate.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_basic_tolerance
from _document_units import apply_package_model_units
from _part_pmi import author_part_pmi
from _part_properties import part_drawing_unit
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_arm_plate_geometry import (
    LOCATOR_SITES_MM,
    LOCATOR_HOLE_DIA_MM,
    CSK_ANGLE_DEG,
    CSK_DEPTH,
    CSK_DIA,
    END_R,
    KINK,
    KINK_RIGHT,
    KINK_TANGENT,
    KINK_TANGENT_RIGHT,
    PRESS_HOLE_DIA,
    PRESS_HOLE_CHAMFER,
    PRESS_HOLE_CHAMFER_VOLUME_MM3,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    THICKNESS_OVER_ARM,
    TOP_LEFT,
    TOP_RIGHT,
    WIDTH,
    section_area_moments,
)
from pd_transgear_arm_plate_spec import (
    BASIC_REDUCER_DIMENSIONS,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "pd-transgear-arm-plate"
MATERIAL = "Plain Carbon Steel"  # AISI 1018; see _appearance.apply_material
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Isometric View Note",
)

THROUGH_CUT_DEPTH = 4.0 * THICKNESS_OVER_ARM  # mid-plane total; > the plate's depth
# The countersink profiles run this far past the rear face so the revolved
# cut clears it, and their axis this far again (not printed).
CSK_OVERRUN = 1.0
SCREW_HOLE_Y = SCREW_HOLES[0][1]
if any(abs(y - SCREW_HOLE_Y) > 1e-9 for _, y in SCREW_HOLES):
    raise AssertionError("the screw holes no longer share one ScrewHolePlane")
# The printed hole Ø (``ScrewHoleDia``) is the first (-X) hole's circle; the
# printed countersink Ø's reference circle goes round the other (+X) hole, so
# the sheet leads the two callouts to different holes and they never cross.
CSK_REFERENCE_HOLE = 1

_R_PRESS = PRESS_HOLE_DIA / 2.0
_R_HOLE = SCREW_HOLE_DIA / 2.0
_R_CSK = CSK_DIA / 2.0
_CSK_HALF_ANGLE = CSK_ANGLE_DEG / 2.0
_CSK_APEX_Z = REAR_FACE_Z - _R_CSK / math.tan(math.radians(_CSK_HALF_ANGLE))


def _csk_removed() -> float:
    """One countersink cone past its clearance hole: frustum less the hole."""
    r, big, h = _R_HOLE, _R_CSK, CSK_DEPTH
    return math.pi * h / 3.0 * (big**2 + big * r + r**2) - math.pi * r**2 * h


V_PLATE = section_area_moments(TOP_LEFT, TOP_RIGHT)[0] * THICKNESS_OVER_ARM
V_PRESS_HOLE = math.pi * _R_PRESS**2 * THICKNESS_OVER_ARM
V_HOLES = len(SCREW_HOLES) * math.pi * _R_HOLE**2 * THICKNESS_OVER_ARM
V_CSK = _csk_removed()


def _mass(adapter: Any) -> tuple[float, list[float]]:
    res = adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"arm-plate mass properties failed: {res.error}")
    return float(res.data.volume), [float(c) for c in res.data.center_of_mass]


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    An offset plane's sketch axes are SolidWorks' choice; the profile points
    go through ``ModelToSketchTransform`` so only the orientation (which
    relations read horizontal/vertical) is assumed, and it is checked here.
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
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


def _outline(
    adapter: Any,
    dims: SketchDims,
    upper_left: tuple[float, float],
    upper_right: tuple[float, float],
    names: dict[str, str],
    label: str,
) -> None:
    """Draw and fully define one outline on the Front plane (sketch x, y =
    model X, Y): upper edge, +X edge, +X kink line tangent to the end round
    about K, the round, the -X kink line tangent to it, the -X edge up to the
    upper edge.  ``names`` maps the roles EndR/EdgeLeftX/EdgeRightX/LeftY/
    RightY/KinkY/KinkRightY to dimension names; the edges are driven by half
    the global ``Width`` and the heights by their ``<role>Drive`` expression
    when one is given."""
    set_sketch_direct_db(adapter, True)
    upper = check(
        f"{label} upper edge", adapter.add_line(*upper_left, *upper_right)
    )
    right = check(f"{label} +X edge", adapter.add_line(*upper_right, *KINK_RIGHT))
    kink_right = check(
        f"{label} +X kink line",
        adapter.add_line(*KINK_RIGHT, *KINK_TANGENT_RIGHT),
    )
    round_ = check(
        f"{label} end round",
        adapter.add_arc(0.0, 0.0, *KINK_TANGENT, *KINK_TANGENT_RIGHT),
    )
    kink = check(f"{label} kink line", adapter.add_line(*KINK_TANGENT, *KINK))
    left = check(f"{label} -X edge", adapter.add_line(*KINK, *upper_left))
    set_sketch_direct_db(adapter, False)
    anchor_point_to_origin(
        adapter, f"{round_}.center", 0.0, 0.0, f"{label} end round on K"
    )
    # The loop's corners: separate entities, so each joint is explicit.
    for p1, p2 in (
        (f"{upper}.end", f"{right}.start"),
        (f"{right}.end", f"{kink_right}.start"),
        (f"{kink_right}.end", f"{round_}.end"),
        (f"{round_}.start", f"{kink}.start"),
        (f"{kink}.end", f"{left}.start"),
        (f"{left}.end", f"{upper}.start"),
    ):
        check(
            f"{label} corner {p1}-{p2}",
            adapter.add_sketch_constraint(p1, p2, "coincident"),
        )
    for relation_label, e1, e2, relation in (
        ("+X kink line tangent", kink_right, round_, "tangent"),
        ("kink line tangent", round_, kink, "tangent"),
    ):
        check(
            f"{label} {relation_label}",
            adapter.add_sketch_constraint(e1, e2, relation),
        )
    for edge_label, edge in (("+X edge", right), ("-X edge", left)):
        check(
            f"{label} {edge_label} vertical",
            adapter.add_sketch_constraint(edge, None, "vertical"),
        )
    check(
        f"{label} end radius",
        adapter.add_sketch_dimension(round_, None, "radial", END_R),
    )
    dims.record(names["EndR"], '"EndR"')
    # The bar stands centred on K: each side edge half the width from it.
    for role, ref, value in (
        ("EdgeLeftX", f"{kink}.end", KINK[0]),
        ("EdgeRightX", f"{kink_right}.start", KINK_RIGHT[0]),
    ):
        dimension_between(
            adapter,
            f"{round_}.center",
            ref,
            "horizontal_distance",
            abs(value),
            f"{label} {role} from K",
        )
        dims.record(names[role], '"Width" / 2')
    for role, ref, value in (
        ("LeftY", f"{upper}.start", upper_left[1]),
        ("RightY", f"{upper}.end", upper_right[1]),
        ("KinkY", f"{kink}.end", KINK[1]),
        ("KinkRightY", f"{kink_right}.start", KINK_RIGHT[1]),
    ):
        dimension_between(
            adapter,
            f"{round_}.center",
            ref,
            "vertical_distance",
            abs(value),
            f"{label} {role} from K",
        )
        dims.record(names[role], names.get(f"{role}Drive"))
    ensure_fully_defined(adapter, label)


def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing: this
    # is an INCH document and the equation manager reads bare numbers in
    # document units.  Stations are magnitudes; each side is the model's.
    for name, value in (
        ("EndR", END_R),
        ("Width", WIDTH),
        ("TopLeftY", TOP_LEFT[1]),
        ("TopRightY", TOP_RIGHT[1]),
        ("KinkY", KINK[1]),
        ("ThicknessOverArm", THICKNESS_OVER_ARM),
        ("PressHoleDia", PRESS_HOLE_DIA),
        ("PressHoleChamferSize", PRESS_HOLE_CHAMFER),
        ("ScrewHoleX1", abs(SCREW_HOLES[0][0])),
        ("ScrewHoleX2", abs(SCREW_HOLES[1][0])),
        ("ScrewHoleY", SCREW_HOLE_Y),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("CskDia", CSK_DIA),
        ("LocatorX", abs(LOCATOR_SITES_MM[0][0])),
        ("LocatorY1", abs(LOCATOR_SITES_MM[0][1])),
        ("LocatorY2", abs(LOCATOR_SITES_MM[1][1])),
        ("LocatorDia", LOCATOR_HOLE_DIA_MM),
    ):
        set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- The plate: the whole outline, THICKNESS_OVER_ARM toward +Z ----------
    outline = SketchDims()
    check("create_sketch plate outline", adapter.create_sketch("Front"))
    _outline(
        adapter,
        outline,
        TOP_LEFT,
        TOP_RIGHT,
        {
            "EndR": "EndR",
            "EdgeLeftX": "EdgeLeftX",
            "EdgeRightX": "EdgeRightX",
            "LeftY": "TopLeftY",
            "LeftYDrive": '"TopLeftY"',
            "RightY": "TopRightY",
            "RightYDrive": '"TopRightY"',
            "KinkY": "KinkY",
            "KinkYDrive": '"KinkY"',
            "KinkRightY": "KinkRightY",
            "KinkRightYDrive": '"KinkY"',
        },
        "plate outline",
    )
    check("exit_sketch plate outline", adapter.exit_sketch())
    name_last_feature(adapter, "PlateOutline")
    drive_jobs += outline.apply(adapter, "PlateOutline")
    check(
        "extrude over-arm section",
        adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS_OVER_ARM)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs += [
        (
            name_dimensions(adapter, "Plate", ["ThicknessOverArm"])[0],
            '"ThicknessOverArm"',
        )
    ]
    expected = V_PLATE
    volume_check(adapter, "plate", expected, 0.002 * expected)
    _, com = _mass(adapter)
    if abs(com[2] - THICKNESS_OVER_ARM / 2.0) > 0.01:
        raise RuntimeError(
            f"plate centre of mass z = {com[2]:.3f}: the extrusion "
            "must run toward +Z"
        )

    # --- The bush's press hole through on K -----------------------------------
    press = SketchDims()
    check("create_sketch press hole", adapter.create_sketch("Front"))
    define_circle(
        adapter,
        0.0,
        0.0,
        _R_PRESS,
        "bush press hole",
        dims=press,
        names=(None, None, "PressHoleDia"),
        drives=(None, None, '"PressHoleDia"'),
    )
    ensure_fully_defined(adapter, "press hole sketch")
    check("exit_sketch press hole", adapter.exit_sketch())
    name_last_feature(adapter, "PressHoleProfile")
    drive_jobs += press.apply(adapter, "PressHoleProfile")
    check(
        "cut press hole",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PressHole")
    expected -= V_PRESS_HOLE
    volume_check(adapter, "plate with press hole", expected, 0.01 * V_PRESS_HOLE)
    # The face-A mouth's .015 X 45° lead-in for the bush, one native 45 deg
    # chamfer picked on the hole's edge in face A (the rear mouth keeps the
    # title block's break).
    check(
        "chamfer the press hole's face-A mouth",
        adapter.add_chamfer(PRESS_HOLE_CHAMFER, [[_R_PRESS, 0.0, 0.0]]),
    )
    name_last_feature(adapter, "PressHoleChamfer")
    drive_jobs.append(
        (
            name_dimensions(adapter, "PressHoleChamfer", ["PressHoleChamferSize"])[0],
            '"PressHoleChamferSize"',
        )
    )
    expected -= PRESS_HOLE_CHAMFER_VOLUME_MM3
    volume_check(
        adapter, "press hole's face-A chamfer", expected,
        0.02 * PRESS_HOLE_CHAMFER_VOLUME_MM3 + 0.05,
    )

    # --- Screw holes through the plate ----------------------------------------
    holes = SketchDims()
    check("create_sketch screw holes", adapter.create_sketch("Front"))
    for index, ((x, y), names, drives) in enumerate(
        zip(
            SCREW_HOLES,
            (
                ("ScrewHoleX1", "ScrewHoleY", "ScrewHoleDia"),
                ("ScrewHoleX2", "ScrewHoleY2", "ScrewHoleDia2"),
            ),
            (
                ('"ScrewHoleX1"', '"ScrewHoleY"', '"ScrewHoleDia"'),
                ('"ScrewHoleX2"', '"ScrewHoleY"', '"ScrewHoleDia"'),
            ),
            strict=True,
        ),
        start=1,
    ):
        define_circle(
            adapter,
            x,
            y,
            _R_HOLE,
            f"screw hole {index}",
            dims=holes,
            names=names,
            drives=drives,
        )
    ensure_fully_defined(adapter, "screw-hole sketch")
    check("exit_sketch screw holes", adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += holes.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    expected -= V_HOLES
    volume_check(adapter, "plate with screw holes", expected, 0.01 * V_HOLES)

    # --- Named planes -----------------------------------------------------------
    for plane, base, offset, drive in (
        ("RearFace", "Front Plane", REAR_FACE_Z, '"ThicknessOverArm"'),
        ("ScrewHolePlane", "Top Plane", SCREW_HOLE_Y, '"ScrewHoleY"'),
        ("LocatorClock", "Right Plane", LOCATOR_SITES_MM[0][0], '"LocatorX"'),
    ):
        check(
            f"create_plane {plane}",
            adapter.create_plane(
                CreatePlaneParameters(mode="offset", base_plane=base, offset=offset)
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append(
            (name_dimensions(adapter, plane, [f"{plane}Offset"])[0], drive)
        )
    blank_reference_geometry(
        adapter,
        (
            ("RearFace", "PLANE"),
            ("ScrewHolePlane", "PLANE"),
            ("LocatorClock", "PLANE"),
        ),
    )

    # --- 82-degree countersinks: one revolved cut per hole --------------------
    # ScrewHolePlane holds both hole axes; model X reads along sketch u and
    # model Z along v, so the axis and the seat's outer wall are vertical.
    for index, ((x, _), x_drive) in enumerate(
        zip(SCREW_HOLES, ('"ScrewHoleX1"', '"ScrewHoleX2"'), strict=True), start=1
    ):
        csk = SketchDims()
        check(
            f"create_sketch countersink {index}",
            adapter.create_sketch("ScrewHolePlane"),
        )
        to_sketch = _sketch_mapper(
            adapter, u_axis=0, v_axis=2, label=f"countersink {index}"
        )
        origin = to_sketch((0.0, SCREW_HOLE_Y, 0.0))
        if origin != (0.0, 0.0):
            raise RuntimeError(f"countersink {index}: sketch origin maps to {origin}")
        top = REAR_FACE_Z + CSK_OVERRUN
        profile = [
            to_sketch((x, SCREW_HOLE_Y, _CSK_APEX_Z)),
            to_sketch((x + _R_CSK, SCREW_HOLE_Y, REAR_FACE_Z)),
            to_sketch((x + _R_CSK, SCREW_HOLE_Y, top)),
            to_sketch((x, SCREW_HOLE_Y, top)),
        ]
        set_sketch_direct_db(adapter, True)
        csk_axis = check(
            f"countersink {index} axis",
            adapter.add_centerline(
                *profile[3], *to_sketch((x, SCREW_HOLE_Y, top + CSK_OVERRUN))
            ),
        )
        csk_lines = add_line_chain(adapter, profile)
        set_sketch_direct_db(adapter, False)
        # cone, outer wall (vertical), top (horizontal), axis side (vertical)
        for line, relation in zip(
            csk_lines[1:], ("vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"countersink {index} {relation} {line}",
                adapter.add_sketch_constraint(line, None, relation),
            )
        check(
            f"countersink {index} axis vertical",
            adapter.add_sketch_constraint(csk_axis, None, "vertical"),
        )
        check(
            f"countersink {index} axis on the profile",
            adapter.add_sketch_constraint(
                f"{csk_axis}.start", f"{csk_lines[3]}.start", "coincident"
            ),
        )
        check(
            f"countersink {index} axis length",
            adapter.add_sketch_dimension(csk_axis, None, "linear", CSK_OVERRUN),
        )
        csk.record(f"Csk{index}AxisLength")
        dimension_between(
            adapter,
            "origin",
            f"{csk_lines[3]}.start",
            "horizontal_distance",
            abs(x),
            f"countersink {index} station",
        )
        csk.record(f"Csk{index}X", x_drive)
        dimension_between(
            adapter,
            "origin",
            f"{csk_lines[1]}.start",
            "vertical_distance",
            REAR_FACE_Z,
            f"countersink {index} on the rear face",
        )
        csk.record(f"Csk{index}Seat", '"ThicknessOverArm"')
        add_diametric_linear_dimension(
            adapter,
            csk_axis,
            csk_lines[1],
            (profile[2][0] + 3.0, profile[2][1]),
            f"Csk{index}Dia",
        )
        csk.record(f"Csk{index}Dia", '"CskDia"')
        # The cone's apex depth below the rim fixes the 82-deg seat, not an
        # angular dimension: one between the cone and the axis side may read
        # the 139-deg supplement, and driving that to 41 would carry the apex
        # past the rim into a self-crossing profile.  The revolve failed right
        # after the angular form (run 20261001T011714683Z, countersink 1).  The
        # drive keeps the angle when CskDia moves.
        dimension_between(
            adapter,
            f"{csk_lines[0]}.start",
            f"{csk_lines[1]}.start",
            "vertical_distance",
            REAR_FACE_Z - _CSK_APEX_Z,
            f"countersink {index} apex depth",
        )
        csk.record(f"Csk{index}ApexDepth", f'"CskDia" / 2 / tan({_CSK_HALF_ANGLE:g})')
        dimension_between(
            adapter,
            f"{csk_lines[1]}.start",
            f"{csk_lines[1]}.end",
            "vertical_distance",
            CSK_OVERRUN,
            f"countersink {index} overrun",
        )
        csk.record(f"Csk{index}Overrun")
        ensure_fully_defined(adapter, f"countersink {index} profile")
        check(f"exit_sketch countersink {index}", adapter.exit_sketch())
        name_last_feature(adapter, f"CountersinkProfile{index}")
        drive_jobs += csk.apply(adapter, f"CountersinkProfile{index}")
        check(
            f"revolve-cut countersink {index}",
            adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
        )
        name_last_feature(adapter, f"Countersink{index}")
        expected -= V_CSK
        volume_check(
            adapter, f"countersink {index}", expected, 0.03 * V_CSK + 0.05
        )

    # --- REFERENCE sketch: the printed countersink Ø on the rear face --------
    csk_ref = SketchDims()
    check(
        "create_sketch countersink reference", adapter.create_sketch("RearFace")
    )
    define_circle(
        adapter,
        *SCREW_HOLES[CSK_REFERENCE_HOLE],
        _R_CSK,
        "countersink reference",
        dims=csk_ref,
        names=("CskRefX", "CskRefY", "CskDia"),
        drives=(f'"ScrewHoleX{CSK_REFERENCE_HOLE + 1}"', '"ScrewHoleY"', '"CskDia"'),
    )
    ensure_fully_defined(adapter, "countersink reference sketch")
    check("exit_sketch countersink reference", adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkReference")
    drive_jobs += csk_ref.apply(adapter, "CountersinkReference")

    # --- Named axes for the assembly mates ------------------------------------
    for label, plane_a, offset_b, drive_b, want in (
        ("press hole axis", "Top Plane", 0.0, None, "Axis1"),
        (
            "screw hole 1 axis",
            "ScrewHolePlane",
            SCREW_HOLES[0][0],
            '"ScrewHoleX1"',
            "Axis2",
        ),
        (
            "screw hole 2 axis",
            "ScrewHolePlane",
            SCREW_HOLES[1][0],
            '"ScrewHoleX2"',
            "Axis3",
        ),
    ):
        named = name_bore_axis(
            adapter,
            plane_a,
            0.0,
            "Right Plane",
            offset_b,
            label,
            drive_b=drive_b,
            drive_jobs=drive_jobs,
        )
        if named != want:
            raise RuntimeError(f"{label} came back {named!r}, not {want}")


    # The female sockets are THROUGH: separately finished while the datum
    # carriers retain the common pilot setup; never slip-ream the arm.
    locators = SketchDims()
    check("create_sketch locating bores", adapter.create_sketch("Front"))
    for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1):
        define_circle(
            adapter, x, y, LOCATOR_HOLE_DIA_MM / 2.0, f"locator {index}",
            dims=locators,
            names=(f"LocatorX{index}", f"LocatorY{index}", f"LocatorDia{index}"),
            drives=('"LocatorX"', f'"LocatorY{index}"', '"LocatorDia"'),
        )
    ensure_fully_defined(adapter, "matched locating bore sketch")
    check("exit_sketch locating bores", adapter.exit_sketch())
    name_last_feature(adapter, "LocatorProfile")
    drive_jobs += locators.apply(adapter, "LocatorProfile")
    check(
        "cut through locating bores",
        adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LocatorHoles")
    expected -= len(LOCATOR_SITES_MM) * math.pi * (LOCATOR_HOLE_DIA_MM / 2.0)**2 * THICKNESS_OVER_ARM
    volume_check(adapter, "matched through locating bores", expected, 0.001 * expected)
    for index, (x, y) in enumerate(LOCATOR_SITES_MM, 1):
        axis = name_bore_axis(
            adapter, "Top Plane", y, "Right Plane", x, f"locator {index}",
            drive_a=f'"LocatorY{index}"', drive_b='"LocatorX"', drive_jobs=drive_jobs,
        )
        if axis != f"Axis{index + 3}":
            raise RuntimeError(f"locator {index} native axis is {axis!r}")
    # Deferred drive equations; each evaluates to the value just built.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    volume_check(
        adapter, "driven plate (equations neutral)", expected, 0.001 * expected
    )
    bbox_extent_check(adapter, "bar width", "x", WIDTH)

    # The press hole and the locating holes print their set reamer's size
    # and no band (fit audit 2026-11-23): each is accepted with its mate
    # (pd_transgear_arm_plate_notes).  The locating holes' coordinates are
    # BASIC under circular position controls, never +/- substitutes.
    for feature_name, dimension_name in BASIC_REDUCER_DIMENSIONS:
        set_dimension_basic_tolerance(adapter, feature_name, dimension_name)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    apply_material(adapter, MATERIAL)
    apply_color(adapter, POLISHED_STEEL)
    report_mass_properties(adapter)
    # Datum B is the press hole, resolved on its exact native face.
    author_part_pmi(adapter, datums=PART_DATUMS, controls=GEOMETRIC_CONTROLS)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_sketches(adapter, ("CountersinkReference",))
    artefacts = save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
