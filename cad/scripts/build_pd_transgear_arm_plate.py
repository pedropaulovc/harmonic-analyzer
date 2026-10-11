r"""Reproduction script: transgear arm plate (MHA-PD-019; ch. 23; 1 used).

The steel plate screwed across the MHA-PD-018 arm by two MHA-VN-040 oval-head
screws: it carries the knob shaft's running bore on axis K, a front hub (the
MHA-PD-015 thrust ring's seat) and a rear boss (the MHA-PD-016 cup runs behind it)
(``pd_transgear_arm_plate_geometry``; the sheet's contract is
``pd_transgear_arm_plate_spec``).

Layout (part frame of ``pd_transgear_arm_plate_geometry``: origin on K at the
MOUNTING face, the Front Plane, which seats on the arm's rear face; +X/+Y the
arm's axes; +Z to the rear):

* ``PlateOutline`` (Front plane): the R12.5 end round about K, each side edge
  parallel to the long axis down to its kink [INFERENCE] and straight on to
  tangency with the round (symmetric about K), the top edge on the arm's
  upper edge; extruded ``THICKNESS_OVER_ARM`` toward +Z as ``Plate``.
* ``LowerOutline``: the same outline below the notch line (``NOTCH_RELIEF``
  clear of the arm's lower edge), extruded ``NOTCH_DEPTH`` toward -Z as
  ``LowerSection``; its top edge is the notch face.
* ``BearingProfile`` (Right plane, the section plane through K): the front
  hub and the rear boss [INFERENCE], revolved as ``Bearing``.  The hub face's
  station is dimensioned from the notch's inner corner on the mounting face.
* ``Bore``: the Ø8.5 running bore through on K.
* ``ScrewHoles``: two Ø4.5 clearance holes through, over the arm's taps.
* ``Countersink1`` / ``Countersink2``: the 82-degree seats of the oval heads,
  revolved cuts sketched on ``ScrewHolePlane`` (y through both hole axes).
* ``CountersinkReference`` (blanked, on ``RearFace``, round the +X hole): the
  printed countersink Ø; the revolved cuts' own profiles lie edge-on to the plan.

Datums (all blanked): ``Axis1`` bore, ``Axis2``/``Axis3`` screw holes (-X,
+X); planes ``RearFace`` (z = 5), ``HubFace`` (z = -20.5375), ``BossFace``
(z = 8.5) and ``ScrewHolePlane``; the Front Plane is the mounting face.

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
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pd_transgear_arm_plate_geometry import (
    BORE_DIA,
    BOSS_DIA,
    BOSS_FACE_Z,
    BOSS_HEIGHT,
    CSK_ANGLE_DEG,
    CSK_DEPTH,
    CSK_DIA,
    END_R,
    HUB_DIA,
    HUB_FACE_TO_MOUNTING,
    HUB_FACE_Z,
    HUB_LENGTH,
    HUB_TO_BOSS,
    KINK,
    KINK_RIGHT,
    KINK_TANGENT,
    KINK_TANGENT_RIGHT,
    NOTCH_DEPTH,
    NOTCH_LEFT,
    NOTCH_RIGHT,
    REAR_FACE_Z,
    SCREW_HOLE_DIA,
    SCREW_HOLES,
    THICKNESS_OVER_ARM,
    TOP_LEFT,
    TOP_RIGHT,
    WIDTH,
    notch_face_y,
)
from pd_transgear_arm_plate_spec import (
    BORE_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HOLE_POSITION_TOLERANCE,
    HUB_TO_BOSS_TOLERANCE,
    ISOMETRIC_VIEW_NOTE,
    SURFACE_FINISHES,
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

THROUGH_CUT_DEPTH = 4.0 * HUB_TO_BOSS  # mid-plane total; > the plate's depth
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

_R_BORE = BORE_DIA / 2.0
_R_HUB = HUB_DIA / 2.0
_R_BOSS = BOSS_DIA / 2.0
_R_HOLE = SCREW_HOLE_DIA / 2.0
_R_CSK = CSK_DIA / 2.0
_CSK_HALF_ANGLE = CSK_ANGLE_DEG / 2.0
_CSK_APEX_Z = REAR_FACE_Z - _R_CSK / math.tan(math.radians(_CSK_HALF_ANGLE))
# The notch's inner corner in the section plane (x = 0): the mounting-face
# point the hub station is measured from.
_NOTCH_CORNER_Y = notch_face_y(0.0)


def _outline_area(upper_left: tuple[float, float], upper_right: tuple[float, float]):
    """Area of the outline closed by the upper edge ``upper_left`` ->
    ``upper_right``: the polygon through the edge, the +X kink and its
    tangent, K, the -X kink tangent and the -X kink, plus the end round's
    sector from the -X kink tangent round the bottom to the +X one."""
    points = [
        upper_left,
        upper_right,
        KINK_RIGHT,
        KINK_TANGENT_RIGHT,
        (0.0, 0.0),
        KINK_TANGENT,
        KINK,
    ]
    shoelace = sum(
        x0 * y1 - x1 * y0
        for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True)
    )
    sweep = (
        math.atan2(KINK_TANGENT_RIGHT[1], KINK_TANGENT_RIGHT[0])
        - math.atan2(KINK_TANGENT[1], KINK_TANGENT[0])
    ) % (2.0 * math.pi)
    return 0.5 * abs(shoelace) + 0.5 * END_R**2 * sweep


def _csk_removed() -> float:
    """One countersink cone past its clearance hole: frustum less the hole."""
    r, big, h = _R_HOLE, _R_CSK, CSK_DEPTH
    return math.pi * h / 3.0 * (big**2 + big * r + r**2) - math.pi * r**2 * h


V_PLATE = _outline_area(TOP_LEFT, TOP_RIGHT) * THICKNESS_OVER_ARM
V_LOWER = _outline_area(NOTCH_LEFT, NOTCH_RIGHT) * NOTCH_DEPTH
V_HUB = math.pi * _R_HUB**2 * HUB_LENGTH
V_BOSS = math.pi * _R_BOSS**2 * BOSS_HEIGHT
V_BORE = math.pi * _R_BORE**2 * HUB_TO_BOSS
V_HOLES = len(SCREW_HOLES) * math.pi * _R_HOLE**2 * THICKNESS_OVER_ARM
V_CSK = _csk_removed()


async def _mass(adapter: Any) -> tuple[float, list[float]]:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"arm-plate mass properties failed: {res.error}")
    return float(res.data.volume), [float(c) for c in res.data.center_of_mass]


def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the flag is
    ISketchSegment's, not the derived ISketchLine's)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


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


async def _outline(
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
        f"{label} upper edge", await adapter.add_line(*upper_left, *upper_right)
    )
    right = check(f"{label} +X edge", await adapter.add_line(*upper_right, *KINK_RIGHT))
    kink_right = check(
        f"{label} +X kink line",
        await adapter.add_line(*KINK_RIGHT, *KINK_TANGENT_RIGHT),
    )
    round_ = check(
        f"{label} end round",
        await adapter.add_arc(0.0, 0.0, *KINK_TANGENT, *KINK_TANGENT_RIGHT),
    )
    kink = check(f"{label} kink line", await adapter.add_line(*KINK_TANGENT, *KINK))
    left = check(f"{label} -X edge", await adapter.add_line(*KINK, *upper_left))
    set_sketch_direct_db(adapter, False)
    await anchor_point_to_origin(
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
            await adapter.add_sketch_constraint(p1, p2, "coincident"),
        )
    for relation_label, e1, e2, relation in (
        ("+X kink line tangent", kink_right, round_, "tangent"),
        ("kink line tangent", round_, kink, "tangent"),
    ):
        check(
            f"{label} {relation_label}",
            await adapter.add_sketch_constraint(e1, e2, relation),
        )
    for edge_label, edge in (("+X edge", right), ("-X edge", left)):
        check(
            f"{label} {edge_label} vertical",
            await adapter.add_sketch_constraint(edge, None, "vertical"),
        )
    check(
        f"{label} end radius",
        await adapter.add_sketch_dimension(round_, None, "radial", END_R),
    )
    dims.record(names["EndR"], '"EndR"')
    # The bar stands centred on K: each side edge half the width from it.
    for role, ref, value in (
        ("EdgeLeftX", f"{kink}.end", KINK[0]),
        ("EdgeRightX", f"{kink_right}.start", KINK_RIGHT[0]),
    ):
        await dimension_between(
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
        await dimension_between(
            adapter,
            f"{round_}.center",
            ref,
            "vertical_distance",
            abs(value),
            f"{label} {role} from K",
        )
        dims.record(names[role], names.get(f"{role}Drive"))
    await ensure_fully_defined(adapter, label)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations).  The mm suffix is load-bearing: this
    # is an INCH document and the equation manager reads bare numbers in
    # document units.  Stations are magnitudes; each side is the model's.
    for name, value in (
        ("EndR", END_R),
        ("Width", WIDTH),
        ("TopLeftY", TOP_LEFT[1]),
        ("TopRightY", TOP_RIGHT[1]),
        ("KinkY", KINK[1]),
        ("NotchLeftY", NOTCH_LEFT[1]),
        ("NotchRightY", NOTCH_RIGHT[1]),
        ("ThicknessOverArm", THICKNESS_OVER_ARM),
        ("NotchDepth", NOTCH_DEPTH),
        ("HubDia", HUB_DIA),
        ("BossDia", BOSS_DIA),
        ("HubFaceToMounting", HUB_FACE_TO_MOUNTING),
        ("HubToBoss", HUB_TO_BOSS),
        ("BoreDia", BORE_DIA),
        ("ScrewHoleX1", abs(SCREW_HOLES[0][0])),
        ("ScrewHoleX2", abs(SCREW_HOLES[1][0])),
        ("ScrewHoleY", SCREW_HOLE_Y),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("CskDia", CSK_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- Over-arm section: the whole outline, 5 toward +Z --------------------
    outline = SketchDims()
    check("create_sketch plate outline", await adapter.create_sketch("Front"))
    await _outline(
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
    check("exit_sketch plate outline", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateOutline")
    drive_jobs += outline.apply(adapter, "PlateOutline")
    check(
        "extrude over-arm section",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS_OVER_ARM)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs += [
        (
            name_dimensions(adapter, "Plate", ["ThicknessOverArm"])[0],
            '"ThicknessOverArm"',
        )
    ]
    expected = V_PLATE
    await volume_check(adapter, "over-arm section", expected, 0.002 * expected)
    _, com = await _mass(adapter)
    if abs(com[2] - THICKNESS_OVER_ARM / 2.0) > 0.01:
        raise RuntimeError(
            f"over-arm section centre of mass z = {com[2]:.3f}: the extrusion "
            "must run toward +Z"
        )

    # --- Section below the arm: under the notch line, 8 toward -Z ------------
    lower = SketchDims()
    check("create_sketch lower outline", await adapter.create_sketch("Front"))
    await _outline(
        adapter,
        lower,
        NOTCH_LEFT,
        NOTCH_RIGHT,
        {
            "EndR": "LowerEndR",
            "EdgeLeftX": "LowerEdgeLeftX",
            "EdgeRightX": "LowerEdgeRightX",
            "LeftY": "NotchLeftY",
            "LeftYDrive": '"NotchLeftY"',
            "RightY": "NotchRightY",
            "RightYDrive": '"NotchRightY"',
            "KinkY": "LowerKinkY",
            "KinkYDrive": '"KinkY"',
            "KinkRightY": "LowerKinkRightY",
            "KinkRightYDrive": '"KinkY"',
        },
        "lower outline",
    )
    check("exit_sketch lower outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LowerOutline")
    drive_jobs += lower.apply(adapter, "LowerOutline")
    check(
        "extrude section below the arm",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=NOTCH_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "LowerSection")
    drive_jobs += [
        (name_dimensions(adapter, "LowerSection", ["NotchDepth"])[0], '"NotchDepth"')
    ]
    expected += V_LOWER
    await volume_check(adapter, "plate with lower section", expected, 0.002 * expected)
    _, com = await _mass(adapter)
    want_z = (V_PLATE * THICKNESS_OVER_ARM / 2.0 - V_LOWER * NOTCH_DEPTH / 2.0) / (
        V_PLATE + V_LOWER
    )
    if abs(com[2] - want_z) > 0.02:
        raise RuntimeError(
            f"plate centre of mass z = {com[2]:.3f}, expected {want_z:.3f}: the "
            "lower section must run toward -Z"
        )

    # --- Hub and boss: revolved in the section plane through K ---------------
    bearing = SketchDims()
    check("create_sketch bearing profile", await adapter.create_sketch("Right"))
    to_sketch = _sketch_mapper(adapter, u_axis=2, v_axis=1, label="bearing profile")
    corners = [
        to_sketch((0.0, 0.0, HUB_FACE_Z)),
        to_sketch((0.0, _R_HUB, HUB_FACE_Z)),
        to_sketch((0.0, _R_HUB, REAR_FACE_Z)),
        to_sketch((0.0, _R_BOSS, REAR_FACE_Z)),
        to_sketch((0.0, _R_BOSS, BOSS_FACE_Z)),
        to_sketch((0.0, 0.0, BOSS_FACE_Z)),
    ]
    notch_corner = to_sketch((0.0, _NOTCH_CORNER_Y, 0.0))
    set_sketch_direct_db(adapter, True)
    axis = check("bearing axis", await adapter.add_centerline(0.0, 0.0, *corners[0]))
    reference = check(
        "mounting-face reference", await adapter.add_line(0.0, 0.0, *notch_corner)
    )
    bearing_lines = await add_line_chain(adapter, corners)
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, reference)
    # Along Z (sketch u) the lines read horizontal, along Y vertical.
    for index, line in enumerate(bearing_lines):
        relation = "vertical" if index % 2 == 0 else "horizontal"
        check(
            f"bearing profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "bearing axis horizontal",
        await adapter.add_sketch_constraint(axis, None, "horizontal"),
    )
    check(
        "bearing axis ends on the hub face",
        await adapter.add_sketch_constraint(
            f"{axis}.end", f"{bearing_lines[0]}.start", "coincident"
        ),
    )
    check(
        "mounting-face reference vertical",
        await adapter.add_sketch_constraint(reference, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{axis}.start", 0.0, 0.0, "bearing axis on K"
    )
    check(
        "mounting-face reference on K",
        await adapter.add_sketch_constraint(
            f"{reference}.start", "origin", "coincident"
        ),
    )
    await add_diametric_linear_dimension(
        adapter,
        axis,
        bearing_lines[1],
        (corners[1][0] + 4.0, corners[1][1] + 4.0),
        "HubDia",
    )
    bearing.record("HubDia", '"HubDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        bearing_lines[3],
        (corners[4][0] - 4.0, corners[4][1] + 4.0),
        "BossDia",
    )
    bearing.record("BossDia", '"BossDia"')
    await dimension_between(
        adapter,
        f"{reference}.end",
        f"{bearing_lines[0]}.end",
        "horizontal_distance",
        HUB_FACE_TO_MOUNTING,
        "hub face from the mounting face",
    )
    bearing.record("HubFaceToMounting", '"HubFaceToMounting"')
    await dimension_between(
        adapter,
        f"{bearing_lines[0]}.end",
        f"{bearing_lines[4]}.start",
        "horizontal_distance",
        HUB_TO_BOSS,
        "hub face to boss face",
    )
    bearing.record("HubToBoss", '"HubToBoss"')
    # The boss seats on the rear face: its step follows the over-arm
    # thickness (not printed; the three dimensions above fix the boss face).
    await dimension_between(
        adapter,
        "origin",
        f"{bearing_lines[2]}.start",
        "horizontal_distance",
        REAR_FACE_Z,
        "boss seat on the rear face",
    )
    bearing.record("BossSeat", '"ThicknessOverArm"')
    # Where the reference meets the notch face (not printed).
    await dimension_between(
        adapter,
        f"{reference}.start",
        f"{reference}.end",
        "vertical_distance",
        abs(_NOTCH_CORNER_Y),
        "mounting-face reference to the notch corner",
    )
    bearing.record("NotchCornerY")
    await ensure_fully_defined(adapter, "bearing profile")
    check("exit_sketch bearing profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BearingProfile")
    drive_jobs += bearing.apply(adapter, "BearingProfile")
    check(
        "revolve hub and boss",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Bearing")
    expected += V_HUB + V_BOSS
    await volume_check(adapter, "plate with hub and boss", expected, 0.002 * expected)
    await bbox_extent_check(adapter, "hub face to boss face", "z", HUB_TO_BOSS)

    # --- Running bore through on K --------------------------------------------
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        _R_BORE,
        "knob-shaft bore",
        dims=bore,
        names=(None, None, "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    expected -= V_BORE
    await volume_check(adapter, "plate with bore", expected, 0.01 * V_BORE)

    # --- Screw holes through the over-arm section -----------------------------
    holes = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Front"))
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
        await define_circle(
            adapter,
            x,
            y,
            _R_HOLE,
            f"screw hole {index}",
            dims=holes,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "screw-hole sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += holes.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    expected -= V_HOLES
    await volume_check(adapter, "plate with screw holes", expected, 0.01 * V_HOLES)

    # --- Named planes -----------------------------------------------------------
    for plane, base, offset, drive in (
        ("RearFace", "Front Plane", REAR_FACE_Z, '"ThicknessOverArm"'),
        ("BossFace", "Front Plane", BOSS_FACE_Z, '"HubToBoss" - "HubFaceToMounting"'),
        ("HubFace", "Front Plane", HUB_FACE_Z, '"HubFaceToMounting"'),
        ("ScrewHolePlane", "Top Plane", SCREW_HOLE_Y, '"ScrewHoleY"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
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
            ("BossFace", "PLANE"),
            ("HubFace", "PLANE"),
            ("ScrewHolePlane", "PLANE"),
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
            await adapter.create_sketch("ScrewHolePlane"),
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
            await adapter.add_centerline(
                *profile[3], *to_sketch((x, SCREW_HOLE_Y, top + CSK_OVERRUN))
            ),
        )
        csk_lines = await add_line_chain(adapter, profile)
        set_sketch_direct_db(adapter, False)
        # cone, outer wall (vertical), top (horizontal), axis side (vertical)
        for line, relation in zip(
            csk_lines[1:], ("vertical", "horizontal", "vertical"), strict=True
        ):
            check(
                f"countersink {index} {relation} {line}",
                await adapter.add_sketch_constraint(line, None, relation),
            )
        check(
            f"countersink {index} axis vertical",
            await adapter.add_sketch_constraint(csk_axis, None, "vertical"),
        )
        check(
            f"countersink {index} axis on the profile",
            await adapter.add_sketch_constraint(
                f"{csk_axis}.start", f"{csk_lines[3]}.start", "coincident"
            ),
        )
        check(
            f"countersink {index} axis length",
            await adapter.add_sketch_dimension(csk_axis, None, "linear", CSK_OVERRUN),
        )
        csk.record(f"Csk{index}AxisLength")
        await dimension_between(
            adapter,
            "origin",
            f"{csk_lines[3]}.start",
            "horizontal_distance",
            abs(x),
            f"countersink {index} station",
        )
        csk.record(f"Csk{index}X", x_drive)
        await dimension_between(
            adapter,
            "origin",
            f"{csk_lines[1]}.start",
            "vertical_distance",
            REAR_FACE_Z,
            f"countersink {index} on the rear face",
        )
        csk.record(f"Csk{index}Seat", '"ThicknessOverArm"')
        await add_diametric_linear_dimension(
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
        await dimension_between(
            adapter,
            f"{csk_lines[0]}.start",
            f"{csk_lines[1]}.start",
            "vertical_distance",
            REAR_FACE_Z - _CSK_APEX_Z,
            f"countersink {index} apex depth",
        )
        csk.record(f"Csk{index}ApexDepth", f'"CskDia" / 2 / tan({_CSK_HALF_ANGLE:g})')
        await dimension_between(
            adapter,
            f"{csk_lines[1]}.start",
            f"{csk_lines[1]}.end",
            "vertical_distance",
            CSK_OVERRUN,
            f"countersink {index} overrun",
        )
        csk.record(f"Csk{index}Overrun")
        await ensure_fully_defined(adapter, f"countersink {index} profile")
        check(f"exit_sketch countersink {index}", await adapter.exit_sketch())
        name_last_feature(adapter, f"CountersinkProfile{index}")
        drive_jobs += csk.apply(adapter, f"CountersinkProfile{index}")
        check(
            f"revolve-cut countersink {index}",
            await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
        )
        name_last_feature(adapter, f"Countersink{index}")
        expected -= V_CSK
        await volume_check(
            adapter, f"countersink {index}", expected, 0.03 * V_CSK + 0.05
        )

    # --- REFERENCE sketch: the printed countersink Ø on the rear face --------
    csk_ref = SketchDims()
    check(
        "create_sketch countersink reference", await adapter.create_sketch("RearFace")
    )
    await define_circle(
        adapter,
        *SCREW_HOLES[CSK_REFERENCE_HOLE],
        _R_CSK,
        "countersink reference",
        dims=csk_ref,
        names=("CskRefX", "CskRefY", "CskDia"),
        drives=(f'"ScrewHoleX{CSK_REFERENCE_HOLE + 1}"', '"ScrewHoleY"', '"CskDia"'),
    )
    await ensure_fully_defined(adapter, "countersink reference sketch")
    check("exit_sketch countersink reference", await adapter.exit_sketch())
    name_last_feature(adapter, "CountersinkReference")
    drive_jobs += csk_ref.apply(adapter, "CountersinkReference")

    # --- Named axes for the assembly mates ------------------------------------
    for label, plane_a, offset_b, drive_b, want in (
        ("bore axis", "Top Plane", 0.0, None, "Axis1"),
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
        named = await name_bore_axis(
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

    # Deferred drive equations; each evaluates to the value just built.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven plate (equations neutral)", expected, 0.001 * expected
    )
    await bbox_extent_check(adapter, "bar width", "x", WIDTH)

    # Manufacturing drawing support: the bore's running fit, the knob-float
    # length and the screw-hole positions carry explicit bands; everything
    # else is governed by its places (policy rule 2).
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *deviations(BORE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "BearingProfile", "HubToBoss", HUB_TO_BOSS_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "ScrewHoleProfile", "ScrewHoleX1", HOLE_POSITION_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "ScrewHoleProfile", "ScrewHoleX2", HOLE_POSITION_TOLERANCE
    )
    set_dimension_symmetric_tolerance(
        adapter, "ScrewHoleProfile", "ScrewHoleY", HOLE_POSITION_TOLERANCE
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    # The Ø8.5 running bore and the hub and boss thrust faces, each resolved
    # on its exact native face (HubFace z -20.5375 and BossFace z 8.5 are
    # unique).
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_sketches(adapter, ("CountersinkReference",))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
