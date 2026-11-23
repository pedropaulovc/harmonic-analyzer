r"""Reproduction script: pen subassembly (book ch. 24; engineerguy 4/4, 9:15-10:34).

The machine's output transducer: the pen carriage that writes the Fourier sum
onto the recording paper, in machine coordinates (assembly origin = base
origin; the output side is -Z). The square pen rod slides vertically through
the hanger's two U guides; the magnifying wheel's wire (pen-wire, WIRE 2 --
modeled as its straight rest-pose run only) raises and lowers it to trace
the curve. Everything below the guides rides the rod:

* pn-pen-hanger (ground) on the wheel bar -- the fixed U guides.
* pn-pen-rod -- a Y-prismatic; its travel is the sub's single FREED operational
  DOF: its drive spec is recorded into the DOF manifest, never authored, so
  the saved model slides freely and carries NO pen-driver equation.
  verify:kinematics replays the recorded spec and installs the F5
  chained-Fourier driver transiently (reproduces truth_model.pen_y from a
  CrankDeg global, no force solver).
* pn-pen-v-block -- the brass block HANGING on the rod: the rod's turned pivot
  end drops into the block's pivot bore and its square shoulder rests on the
  block top; sh-vn-arbor-set-screw (front face) locks the pen's yaw, which is
  PEN_BLOCK_YAW_DEG to the paper.
* pn-vn-pen-marker -- the purchased Sharpie Fine Point, its grip in the block's V-groove,
  nib on the paper, body running out forward and east.
* pn-pen-frame -- the stirrup on the block's PAPER end, flush as modelled (its
  setting: the rear face .310 to .325 from that end, the paper face not
  proud of it); pn-vn-pen-set-screw (the thumb screw) threads up through its
  bottom rail and presses the grip into the V.
* pn-pen-adjust-screw + pn-vn-pen-adjust-nut -- the height adjuster on the rod
  top: the stud threads into the rod's #0-80 tap, the jam nut locks it, and
  the pen wire ties through its eye.
* sh-vn-music-wire (PenWire) -- WIRE 2's straight rest-pose run hanging PLUMB from the wheel
  rim's 3 o'clock tangent onto the stud's eye head (the rod line is the rim's
  mid-plane), locked to the rod so it rides the pen travel. The rim wrap and
  tie-off are not modeled; the kinematic coupling stays a Motion-study mate
  (cad/docs/motion-policy.md).
* pn-vn-hanger-screw + pn-vn-pen-hanger-nut + pn-vn-pen-hanger-jam-nut -- fasten the
  pen-hanger: the screw from behind the wheel bar through the strap's
  clearance hole, the nut on the strap front and the thin jam nut jammed
  against it, locking it; all three fixed at their authored poses.

The carriage layout and its plan balance live in ``pn_pen_carriage_geom``
(pure): the rod line PEN_Z_MID and the v-block's pivot-bore station put the
carriage CG on the rod axis, so the pen hangs level and its yaw is held by the
set screw, not by the guides.

Cross-subassembly fits (checked at the top level): the pen-hanger clamps the
wheel bar (mg-magnifier.SLDASM) and the wheel rim -> pen wire couples the pen
to the magnifier; the stirrup's paper-side corner and the nib stand off the
recording paper's front face (pd-paper-drive.SLDASM).

Fix-all strategy (M6.2): the hanger inserted at its exact final transform and
fixed; the rod left free and constrained by mates (its Y-travel recorded into
the DOF manifest, never authored); the carriage parts placed on-solution and
lock-mated to the rod; transforms asserted by read-back; zero interference
beyond the thread-envelope allowances in ``_pn_pen_interference``.

Fitter package (draw_pn_pen_assembly.py, MHA-PN-00): the five settings --
stud height, pen yaw, nib preset, the stirrup's setting and rod
travel -- are blanked construction sketches (``StudSetting`` and
``TravelSetting`` on the Right plane,
``CarriageSetting`` on the Top plane) whose driving, toleranced dimensions
the drawing imports, and the
``PN_EXPLODED`` presentation is authored by ``_pn_pen_explode`` from
``pn_pen_explode_spec.EXPLODE_STEPS`` in both drawing configurations.

Dimensions: cad/config/dimensions.yaml ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_assembly.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry
import pn_pen_assembly_spec as spec
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_angular_tolerance,
    set_dimension_symmetric_tolerance,
)
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _assembly_named_views import name_standard_views
from _pn_pen_explode import create_pn_explode
from _assembly import (
    activate_assembly_contract,
    author_in_drawing_configurations,
    angle_driver,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _transforms import IDENTITY, euler_from_rows
from _pn_pen_interference import ALLOWED_PAIRS
from pn_vn_hanger_screw_spec import SHANK_LEN as HANGER_SHANK_LEN
from pn_vn_hanger_screw_spec import TIP_CHAMFER as HANGER_TIP_CHAMFER
from pn_vn_pen_hanger_jam_nut_spec import THICKNESS as HANGER_JAM_NUT_T
from pn_vn_pen_hanger_nut_spec import ACROSS_CORNERS as HANGER_NUT_ACROSS_CORNERS
from pn_vn_pen_hanger_nut_spec import THICKNESS as HANGER_NUT_T
from _mg_wheel_rim_geometry import RIM_AXIAL as WHEEL_RIM_AXIAL
from _mg_wheel_rim_geometry import RIM_OUTER_DIA as WHEEL_RIM_OUTER_DIA
from _column_clamp_interface import BAR_DEPTH as WHEEL_BAR_DEPTH
from mg_wheel_bar_geom import WHEEL_BAR_Y, WHEEL_X
from pn_pen_hanger_spec import (
    HANGER_POS,
    SCREW_HOLE_XY as HANGER_HOLE_XY,
    STRAP_Z as HANGER_STRAP_Z,
)
from sh_vn_music_wire_pen_geom import (
    CONFIGURATION as PEN_WIRE_CONFIGURATION,
    WHEEL_MID_Z,
    WIRE_BOTTOM as PEN_WIRE_BOTTOM,
)
from pn_pen_carriage_geom import (
    BLOCK_ROWS,
    FRAME_POS,
    FRAME_ROWS,
    MARKER_POS,
    MARKER_ROWS,
    NUT_POS,
    NUT_ROWS,
    ROD_POS as PEN_ROD_POS,
    ROD_SET_SCREW_POS,
    ROD_SET_SCREW_ROWS,
    STUD_POS,
    THUMB_SCREW_POS,
    THUMB_SCREW_ROWS,
    VBLOCK_POS,
)

ASM_NAME = "pn-pen"

# --- amplification wire 2 (rim -> stud eye) ---------------------------------------
_RIM_R = WHEEL_RIM_OUTER_DIA / 2.0

# --- M6.10 fastener ----------------------------------------------------------
# Pen-hanger screw from BEHIND the bar. Its under-head frame follows the shared
# wheel-bar back face; the exact stock shank passes through the 9.5 mm bar, the
# 3 mm strap's clearance hole, the nut on the strap front and the jam nut on
# that, then stands clear of the magnifying-wheel rim.
BAR_BACK_Z = HANGER_POS[2] + max(HANGER_STRAP_Z) + WHEEL_BAR_DEPTH
HANGER_SCREW_POS = (
    HANGER_POS[0] + HANGER_HOLE_XY[0],
    HANGER_POS[1] + HANGER_HOLE_XY[1],
    BAR_BACK_Z,
)
HANGER_SCREW_TIP_Z = HANGER_SCREW_POS[2] - HANGER_SHANK_LEN
HANGER_STRAP_FRONT_Z = HANGER_POS[2] + min(HANGER_STRAP_Z)
# Both nuts' frames span local z 0..T (pn_vn_pen_hanger_nut_spec,
# pn_vn_pen_hanger_jam_nut_spec): the nut placed un-rotated at the strap front
# less its T bears on the strap with its z = T face; the jam nut, placed at
# the nut's z = 0 face less its own T, bears on the nut the same way.
HANGER_NUT_POS = (
    HANGER_SCREW_POS[0],
    HANGER_SCREW_POS[1],
    HANGER_STRAP_FRONT_Z - HANGER_NUT_T,
)
HANGER_JAM_NUT_POS = (
    HANGER_SCREW_POS[0],
    HANGER_SCREW_POS[1],
    HANGER_NUT_POS[2] - HANGER_JAM_NUT_T,
)
WHEEL_RIM_BACK_Z = WHEEL_MID_Z + WHEEL_RIM_AXIAL / 2.0
# Full thread standing past the jam nut's outer face, the tip chamfer excluded.
HANGER_THREAD_PAST_NUT = HANGER_JAM_NUT_POS[2] - HANGER_SCREW_TIP_Z - HANGER_TIP_CHAMFER
HANGER_TIP_TO_RIM = HANGER_SCREW_TIP_Z - WHEEL_RIM_BACK_Z
# The wider nut's corners against the rim, radially from the wheel axis.
HANGER_NUT_RIM_RADIAL = (
    math.hypot(HANGER_SCREW_POS[0] - WHEEL_X, HANGER_SCREW_POS[1] - WHEEL_BAR_Y)
    - HANGER_NUT_ACROSS_CORNERS / 2.0
    - _RIM_R
)

# Every part that rides the rod: (stem, position, rows). Each is placed at its
# exact pose and LOCKED to the rod (a Lock mate freezes the full relative
# transform, so one mate per rider). Threaded riders (thumb screw, rod set
# screw, stud, nut) sit on their tapped-hole axes by construction -- the same
# block/rod stations the parts' hole features resolve to; an extra coaxial mate
# on top of the Lock would only over-constrain the solve.
RIDERS = (
    ("pn-pen-v-block", VBLOCK_POS, BLOCK_ROWS),
    ("pn-vn-pen-marker", MARKER_POS, MARKER_ROWS),
    ("pn-pen-frame", FRAME_POS, FRAME_ROWS),
    ("pn-vn-pen-set-screw", THUMB_SCREW_POS, THUMB_SCREW_ROWS),
    ("sh-vn-arbor-set-screw", ROD_SET_SCREW_POS, ROD_SET_SCREW_ROWS),
    ("pn-pen-adjust-screw", STUD_POS, IDENTITY),
    ("pn-vn-pen-adjust-nut", NUT_POS, NUT_ROWS),
    ("sh-vn-music-wire", PEN_WIRE_BOTTOM, IDENTITY),
)


def _construction(adapter: Any, line: str, label: str) -> None:
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} is not construction")


def _author_stud_setting(adapter: Any) -> None:
    """STUD HEIGHT: a vertical construction line on the rod axis from the
    rod's top face to the stud's head top (Right plane, sketch = machine -Z,
    Y), its length the nominal stud's setting. It carries no band: the stud
    is set from its measured length (``spec.stud_head_setting``), so the
    drawing prints it as a reference. No solid or pose edits."""
    (u, rod_top_y), (_u, head_top_y) = spec.STUD_LINE
    dims = SketchDims()
    check("create stud setting sketch", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    line = check("stud setting line", adapter.add_line(u, rod_top_y, u, head_top_y))
    set_sketch_direct_db(adapter, False)
    _construction(adapter, line, "stud setting line")
    check("stud setting vertical", adapter.add_sketch_constraint(line, None, "vertical"))
    anchor_point_to_origin(adapter, f"{line}.start", u, rod_top_y, "rod top on axis")
    dims.record("StudRodAxisZ")
    dims.record("StudRodTopY")
    dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        spec.STUD_HEIGHT, "stud head top above rod top",
    )
    dims.record(spec.STUD_DIMENSION)
    ensure_fully_defined(adapter, "stud setting")
    check("exit stud setting sketch", adapter.exit_sketch())
    name_last_feature(adapter, spec.STUD_FEATURE)
    dims.apply(adapter, spec.STUD_FEATURE)


def _author_travel_setting(adapter: Any) -> None:
    """ROD TRAVEL: a vertical construction line on the rod axis from the
    hanger's upper U-guide top down to the block top (Right plane, sketch =
    machine -Z, Y) in the rest pose, toleranced by the pen's travel each way.
    No solid or pose edits: the rod stays free in Y."""
    (u, guide_top_y), (_u, block_top_y) = spec.TRAVEL_LINE
    dims = SketchDims()
    check("create travel setting sketch", adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    line = check("travel line", adapter.add_line(u, guide_top_y, u, block_top_y))
    set_sketch_direct_db(adapter, False)
    _construction(adapter, line, "travel line")
    check("travel line vertical", adapter.add_sketch_constraint(line, None, "vertical"))
    anchor_point_to_origin(
        adapter, f"{line}.start", u, guide_top_y, "upper guide top on axis"
    )
    dims.record("TravelRodAxisZ")
    dims.record("TravelGuideTopY")
    dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        spec.TRAVEL_REFERENCE, "block top below upper guide top",
    )
    dims.record(spec.TRAVEL_DIMENSION)
    ensure_fully_defined(adapter, "travel setting")
    check("exit travel setting sketch", adapter.exit_sketch())
    name_last_feature(adapter, spec.TRAVEL_FEATURE)
    dims.apply(adapter, spec.TRAVEL_FEATURE)
    set_dimension_symmetric_tolerance(
        adapter,
        spec.TRAVEL_FEATURE,
        spec.TRAVEL_DIMENSION,
        spec.TRAVEL_TOLERANCE_MM,
        places=spec.TRAVEL_PRECISION,
        display_unit=assembly_contract(ASM_NAME).drawing_unit,
    )


def _add_driving_yaw_angle(adapter: Any, nib_line: str, flat_line: str) -> None:
    """The marker axis's angle to the rod-flat arm, as a DRIVING dimension.

    ``build_pn_pen_v_block._add_driving_flank_angle``'s recipe: both lines
    selected as segments, the text point inside the wedge passed as sketch
    (u, v) in the x / y slots and as the model point (Z = -v on the Top plane)
    in the z slot, so it lands in the wedge whichever space SOLIDWORKS reads
    it in; the measured value is checked before the dimension drives."""
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    u, v = (value / 1000.0 for value in spec.YAW_TEXT_UV)
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [nib_line, flat_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        u,
        v,
        -v,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"pen yaw: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual_rad = abs(float(dimension.SystemValue))
    if abs(actual_rad - math.radians(spec.YAW_DEG)) > 1e-8:
        raise RuntimeError(
            f"pen yaw: measured {math.degrees(actual_rad):.6f} deg, "
            f"expected {spec.YAW_DEG:.6f} deg"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError("pen yaw: angular dimension did not become driving")
    _telemetry.success(f"driving pen yaw: {spec.YAW_DEG:g} deg")


def _author_carriage_setting(adapter: Any) -> None:
    """PEN YAW, NIB PRESET and the STIRRUP SETTING on the Top plane (sketch
    u, v = machine X, -Z): from the marker axis at the block's paper-end
    face, a rod-flat arm along machine -X, the marker-axis arm to the nib tip
    and, collinear with it into the block, the stirrup arm to the stirrup's
    rear face. Their angle is the yaw, the second arm's length the nib
    preset, the third's the stirrup's rear face from the end face (#3467).
    No solid or pose edits."""
    end_u, end_v = spec.CARRIAGE_END_UV
    dims = SketchDims()
    check("create carriage setting sketch", adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    # All three arms start on the one end-face point (exactly coincident
    # endpoints merge in the sketch database).
    flat = check("rod-flat arm", adapter.add_line(end_u, end_v, *spec.FLAT_END_UV))
    nib = check("marker-axis arm", adapter.add_line(end_u, end_v, *spec.NIB_UV))
    stirrup = check(
        "stirrup arm", adapter.add_line(end_u, end_v, *spec.STIRRUP_REAR_UV)
    )
    set_sketch_direct_db(adapter, False)
    _construction(adapter, flat, "rod-flat arm")
    _construction(adapter, nib, "marker-axis arm")
    _construction(adapter, stirrup, "stirrup arm")
    check("rod-flat arm horizontal", adapter.add_sketch_constraint(flat, None, "horizontal"))
    check(
        "stirrup arm on the marker axis",
        adapter.add_sketch_constraint(stirrup, nib, "collinear"),
    )
    anchor_point_to_origin(adapter, f"{flat}.start", end_u, end_v, "paper-end point")
    dims.record("CarriageEndX")
    dims.record("CarriageEndZ")
    dimension_between(
        adapter, f"{flat}.start", f"{flat}.end", "horizontal_distance",
        spec.FLAT_LINE_LENGTH, "rod-flat arm",
    )
    dims.record("RodFlatArm")
    dimension_between(
        adapter, f"{nib}.start", f"{nib}.end", "distance",
        spec.NIB_PROTRUSION, "nib beyond the paper-end face",
    )
    dims.record(spec.NIB_DIMENSION)
    _add_driving_yaw_angle(adapter, nib, flat)
    dims.record(spec.YAW_DIMENSION)
    dimension_between(
        adapter, f"{stirrup}.start", f"{stirrup}.end", "distance",
        spec.STIRRUP_REAR, "stirrup rear face from the paper-end face",
    )
    dims.record(spec.STIRRUP_DIMENSION)
    ensure_fully_defined(adapter, "carriage setting")
    check("exit carriage setting sketch", adapter.exit_sketch())
    name_last_feature(adapter, spec.CARRIAGE_FEATURE)
    dims.apply(adapter, spec.CARRIAGE_FEATURE)
    unit = assembly_contract(ASM_NAME).drawing_unit
    set_dimension_symmetric_tolerance(
        adapter,
        spec.CARRIAGE_FEATURE,
        spec.NIB_DIMENSION,
        spec.NIB_TOLERANCE_MM,
        places=spec.NIB_PRECISION,
        display_unit=unit,
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, spec.CARRIAGE_FEATURE, spec.YAW_DIMENSION, spec.YAW_TOLERANCE_DEG
    )
    set_dimension_bilateral_tolerance(
        adapter,
        spec.CARRIAGE_FEATURE,
        spec.STIRRUP_DIMENSION,
        *spec.STIRRUP_TOLERANCE_MM,
        places=spec.STIRRUP_PRECISION,
        display_unit=unit,
    )


def _author_settings(adapter: Any) -> None:
    """The three setting sketches, their places, drawing marks, then blanked."""
    _author_stud_setting(adapter)
    _author_carriage_setting(adapter)
    _author_travel_setting(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
        blank_sketch(adapter, feature)


def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", adapter.create_assembly())
    apply_package_model_units(
        adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME
    )

    # The pen carriage slides vertically through the hanger's U guides: the
    # magnifying wheel's wire (flexible, not modeled as geometry --
    # dimensions.yaml ch24) raises/lowers it to trace the curve. The rod runs
    # as a Y-prismatic -- its local slide axis held parallel to the Front +
    # Right planes (axis-to-plane distance, no rotational overlap), an
    # angle(Front) snapshot killing spin, and the Y-travel drive spec (the
    # compliant-chain snapshot the wire would set) recorded into the DOF
    # manifest -- the travel stays live in the saved model. The carriage
    # rides the rod via Lock mates. The hanger is FIRST so the auto-fixed
    # seed is structure, not the rod.
    place_component(
        adapter, "pn-pen-hanger", list(HANGER_POS), [0.0, 0.0, 0.0], IDENTITY
    )
    pen_rod = place_component(
        adapter,
        "pn-pen-rod",
        list(PEN_ROD_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    rod_o = component_origin(adapter, pen_rod)
    distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Front Plane", "PLANE"),
        rod_o[2],
        label="pen-rod slide depth",
        verify=(pen_rod, rod_o),
    )
    distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        rod_o[0],
        label="pen-rod slide across",
        verify=(pen_rod, rod_o),
    )
    angle_driver(
        adapter,
        named_ref(f"Front Plane@{pen_rod}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        0.0,
        label="pen-rod spin snapshot",
        verify=(pen_rod, rod_o),
    )
    # The Y-travel is the sub's FREED operational DOF (the pen up/down the
    # magnifying wheel's wire drives in the real device): its drive spec is
    # recorded into the DOF manifest, never authored -- drag the rod and the
    # whole carriage + pen-wire slide with it.
    distance_driver(
        adapter,
        named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        rod_o[1],
        label="pen-rod travel PARK driver (freed in default build)",
        verify=(pen_rod, rod_o),
        free_dof_key="pen_travel",
    )

    for part, pos, rows in RIDERS:
        name = place_component(
            adapter,
            part,
            list(pos),
            euler_from_rows(rows),
            rows,
            ground=False,
            configuration=PEN_WIRE_CONFIGURATION if part == spec.WIRE else "",
            component_reference="PenWire:1" if part == spec.WIRE else "",
        )
        lock_mate(
            adapter,
            named_ref(f"Front Plane@{name}", "PLANE"),
            named_ref(f"Front Plane@{pen_rod}", "PLANE"),
            label=f"{part} locked to rod",
        )
        assert_component_placed(adapter, name, list(pos), rows)

    # Kinematic pen driver (plan F5): re-drives the Y-travel mate from a
    # CrankDeg global through the chained Fourier sum, so the pose reproduces
    # truth_model.pen_y with no force solver (the 21-spring summation is
    # computed, not simulated -- cad/docs/motion-policy.md). The build never
    # authors this mate or its equation -- verify:kinematics replays the
    # recorded DOF-manifest spec and installs the equation transiently on the
    # replayed mate (renamed DRIVE_pen_travel), then discards the model
    # unsaved.

    # The hanger screw, the nut on the strap front and the jam nut on the
    # nut are static: each is fixed at its exact authored pose on the screw
    # axis, like the hanger they clamp.
    place_component(
        adapter,
        "pn-vn-hanger-screw",
        list(HANGER_SCREW_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    for stem, pos in (
        ("pn-vn-pen-hanger-nut", HANGER_NUT_POS),
        ("pn-vn-pen-hanger-jam-nut", HANGER_JAM_NUT_POS),
    ):
        place_component(adapter, stem, list(pos), [0.0, 0.0, 0.0], IDENTITY)

    # Certify the AS-BUILT model. Necessity only: the freed pen travel is
    # genuinely free; the lock-mated riders MUST read under-constrained WITH
    # the rod -- with the neutral preset the motion sweep reads got == want == 0
    # even if a rider were disconnected.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=("pn-pen-rod", *(part for part, *_ in RIDERS)),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=ALLOWED_PAIRS,
    )
    # The fitter drawing's settings: driving, toleranced model dimensions on
    # blanked construction sketches, authored once the as-built model is
    # certified (they touch no component, mate or pose).
    _author_settings(adapter)
    # Title-block identity for the fitter drawing (draw_pn_pen_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires; material and finish are per component (each
    # component drawing), so the assembly's own cells defer to them.
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The fitter drawing's exploded view references Default Simplified, so
    # the explode is authored in both drawing configurations.
    author_in_drawing_configurations(
        adapter, ASM_NAME, lambda configuration: create_pn_explode(adapter, configuration)
    )
    # The exploded view's camera: *Isometric turned about +Y so the v-block's
    # front face, the set screw's tap in it and the screw's explode read
    # obliquely (spec.EXPLODED_VIEW).
    name_standard_views(
        adapter,
        views={spec.EXPLODED_VIEW: spec.EXPLODED_VIEW_STANDARD},
        label=ASM_NAME,
        model_rotation=spec.EXPLODED_VIEW_TURN,
    )
    return save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
