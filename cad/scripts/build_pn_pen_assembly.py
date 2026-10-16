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
  block top; vn-pen-rod-set-screw (front face) locks the pen's yaw, which is
  PEN_BLOCK_YAW_DEG to the paper.
* vn-pen-marker -- the purchased Sharpie Fine Point, its grip in the block's V-groove,
  nib on the paper, body running out forward and east.
* pn-pen-frame -- the stirrup flush on the block's PAPER end; vn-pen-set-screw
  (the thumb screw) threads up through its bottom rail and presses the grip
  into the V.
* pn-pen-adjust-screw + vn-pen-adjust-nut -- the height adjuster on the rod
  top: the stud threads into the rod's #0-80 tap, the jam nut locks it, and
  the pen wire ties through its eye.
* vn-pen-wire -- WIRE 2's straight rest-pose run hanging PLUMB from the wheel
  rim's 3 o'clock tangent onto the stud's eye head (the rod line is the rim's
  mid-plane), locked to the rod so it rides the pen travel. The rim wrap and
  tie-off are not modeled; the kinematic coupling stays a Motion-study mate
  (cad/docs/motion-policy.md).
* vn-hanger-screw + vn-pen-hanger-nut + vn-pen-hanger-jam-nut -- fasten the
  pen-hanger: the screw from behind the wheel bar through the strap's
  clearance hole, the nut on the strap front and the thin jam nut jammed
  against it, locking it.

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
beyond the thread-envelope allowances in ``_interference_contracts``.

Fitter package (draw_pn_pen_assembly.py, MHA-PN-000): the three carriage
settings -- stud height, pen yaw and nib preset -- are blanked construction
sketches (``StudSetting`` on the Front plane, ``CarriageSetting`` on the Top
plane) whose driving, toleranced dimensions the drawing imports, and the
``PN_EXPLODED`` presentation is authored here from
``pn_pen_assembly_spec.EXPLODE_STEPS`` in both drawing configurations.

Dimensions: cad/config/dimensions.yaml ch. 24.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pn_pen_assembly.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry
import pn_pen_assembly_spec as spec
from _check import check
from _com import _early_bound
from _custom_properties import apply_custom_properties
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import (
    set_dimension_symmetric_angular_tolerance,
    set_dimension_symmetric_tolerance,
)
from _feature_tree import name_last_feature
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _assembly_patterns import ensure_global_pattern_axis
from _simplified_names import simplified_name
from _assembly import (
    activate_assembly_contract,
    author_in_drawing_configurations,
    angle_driver,
    assembly_title_properties,
    assert_component_placed,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    parallel_mate,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _transforms import IDENTITY, euler_from_rows
from _interference_contracts import allowed_interference_pairs
from vn_hanger_screw_spec import SHANK_LEN as HANGER_SHANK_LEN
from vn_hanger_screw_spec import THREAD_PITCH as HANGER_THREAD_PITCH
from vn_hanger_screw_spec import TIP_CHAMFER as HANGER_TIP_CHAMFER
from vn_pen_hanger_jam_nut_spec import (
    THREAD_PAST_MIN_PITCHES as HANGER_THREAD_PAST_PITCHES,
)
from vn_pen_hanger_jam_nut_spec import THICKNESS as HANGER_JAM_NUT_T
from vn_pen_hanger_nut_spec import ACROSS_CORNERS as HANGER_NUT_ACROSS_CORNERS
from vn_pen_hanger_nut_spec import THICKNESS as HANGER_NUT_T
from mg_magnifying_wheel_geom import RIM_AXIAL as WHEEL_RIM_AXIAL
from mg_magnifying_wheel_geom import RIM_OUTER_DIA as WHEEL_RIM_OUTER_DIA
from mg_wheel_bar_geom import BAR_DEPTH as WHEEL_BAR_DEPTH
from mg_wheel_bar_geom import HANGER_SCREW_MACHINE_X
from mg_wheel_bar_geom import WHEEL_X
from pn_pen_hanger_spec import (
    GUIDE_ENGAGE_MARGIN,
    GUIDE_SPAN_Y,
    HANGER_POS,
    SCREW_HOLE_XY as HANGER_HOLE_XY,
    STRAP_Z as HANGER_STRAP_Z,
)
from vn_pen_wire_geom import (
    WHEEL_BAR_Y,
    WHEEL_MID_Z,
    WIRE_BOTTOM as PEN_WIRE_BOTTOM,
    WIRE_LEN as PEN_WIRE_LEN,
)
from pn_pen_carriage_geom import (
    BLOCK_ROWS,
    CARRIAGE_TOP_Y,
    FRAME_POS,
    FRAME_ROWS,
    MARKER_POS,
    MARKER_ROWS,
    NUT_POS,
    NUT_ROWS,
    ROD_POS as PEN_ROD_POS,
    ROD_SET_SCREW_POS,
    ROD_SET_SCREW_ROWS,
    ROD_SQUARE_TOP_Y,
    STUD_HEAD_TOP_Y,
    STUD_POS,
    THUMB_SCREW_POS,
    THUMB_SCREW_ROWS,
    VBLOCK_POS,
)

ASM_NAME = "pn-pen"
assert ASM_NAME == spec.ASM_NAME, (ASM_NAME, spec.ASM_NAME)

# --- hanger guides: the rod square stays in both U guides over the full travel,
# and nothing riding the rod reaches the lower guide --------------------------------
if ROD_SQUARE_TOP_Y[0] < GUIDE_SPAN_Y[1] + GUIDE_ENGAGE_MARGIN:
    raise AssertionError(
        "pen-rod square leaves the upper U guide at the bottom of travel"
    )
if CARRIAGE_TOP_Y[1] > GUIDE_SPAN_Y[0] - GUIDE_ENGAGE_MARGIN:
    raise AssertionError("pen carriage reaches the lower U guide at the top of travel")

# --- amplification wire 2 (rim -> stud eye) ---------------------------------------
# The run's top rides the rim groove's tangent at the wheel-axis height; it hangs
# plumb onto the stud's eye head, which stays below the rim at the top of travel.
if not math.isclose(PEN_WIRE_BOTTOM[1] + PEN_WIRE_LEN, WHEEL_BAR_Y, abs_tol=1e-9):
    raise AssertionError("pen-wire top drifted from the wheel-axis tangent height")
_RIM_R = WHEEL_RIM_OUTER_DIA / 2.0
_RIM_LOW_Y_AT_WIRE = WHEEL_BAR_Y - math.sqrt(
    _RIM_R**2 - (WHEEL_X - PEN_WIRE_BOTTOM[0]) ** 2
)
if STUD_HEAD_TOP_Y[1] > _RIM_LOW_Y_AT_WIRE - 2.0:
    raise AssertionError(
        "adjuster stud eye reaches the magnifying-wheel rim at the top of travel"
    )

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
assert math.isclose(HANGER_SCREW_POS[0], HANGER_SCREW_MACHINE_X, abs_tol=1e-9)
assert math.isclose(HANGER_SCREW_POS[1], WHEEL_BAR_Y, abs_tol=1e-9)
HANGER_SCREW_TIP_Z = HANGER_SCREW_POS[2] - HANGER_SHANK_LEN
HANGER_STRAP_FRONT_Z = HANGER_POS[2] + min(HANGER_STRAP_Z)
# Both nuts' frames span local z 0..T (vn_pen_hanger_nut_spec,
# vn_pen_hanger_jam_nut_spec): the nut placed un-rotated at the strap front
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
if HANGER_THREAD_PAST_NUT < HANGER_THREAD_PAST_PITCHES * HANGER_THREAD_PITCH:
    raise AssertionError(
        "stock hanger screw stands under two full pitches past the jam nut"
    )
if HANGER_TIP_TO_RIM <= 0.0:
    raise AssertionError("stock hanger screw tip reaches the magnifying-wheel rim")
if HANGER_NUT_RIM_RADIAL <= 0.0:
    raise AssertionError("hanger nut corners reach the magnifying-wheel rim")

# Every part that rides the rod: (stem, position, rows). Each is placed at its
# exact pose and LOCKED to the rod (a Lock mate freezes the full relative
# transform, so one mate per rider). Threaded riders (thumb screw, rod set
# screw, stud, nut) sit on their tapped-hole axes by construction -- the same
# block/rod stations the parts' hole features resolve to; an extra coaxial mate
# on top of the Lock would only over-constrain the solve.
RIDERS = (
    ("pn-pen-v-block", VBLOCK_POS, BLOCK_ROWS),
    ("vn-pen-marker", MARKER_POS, MARKER_ROWS),
    ("pn-pen-frame", FRAME_POS, FRAME_ROWS),
    ("vn-pen-set-screw", THUMB_SCREW_POS, THUMB_SCREW_ROWS),
    ("vn-pen-rod-set-screw", ROD_SET_SCREW_POS, ROD_SET_SCREW_ROWS),
    ("pn-pen-adjust-screw", STUD_POS, IDENTITY),
    ("vn-pen-adjust-nut", NUT_POS, NUT_ROWS),
    ("vn-pen-wire", PEN_WIRE_BOTTOM, IDENTITY),
)


def pn_exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too."""
    if configuration == spec.SOURCE_CONFIGURATION:
        return spec.EXPLODED_VIEW_NAME
    if configuration == simplified_name(spec.SOURCE_CONFIGURATION):
        return simplified_name(spec.EXPLODED_VIEW_NAME)
    raise ValueError(
        f"{spec.EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}"
    )


def _presentation_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{component.Name2}: invalid presentation transform {values!r}")
    return values


def _global_axes(adapter: Any, assembly: Any, view_name: str) -> dict[str, tuple[str, bool]]:
    """The native world axes (shared with component patterns) and whether each
    points along +key; geometry and signed sense are verified."""
    axes = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(f"{view_name}: missing reference axis {axis_name}")
        axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
        points = tuple(float(value) for value in axis.GetRefAxisParams())
        if len(points) != 6 or not all(math.isfinite(value) for value in points):
            raise RuntimeError(f"{axis_name}: invalid axis endpoints {points!r}")
        vector = tuple(points[i + 3] - points[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        if length <= 1e-12 or any(
            abs(vector[i] / length) > 1e-9 for i in range(3) if i != index
        ):
            raise RuntimeError(f"{axis_name}: not aligned with world {key.upper()}: {vector!r}")
        axes[key] = (axis_name, vector[index] > 0.0)
    return axes


def _create_named_view(
    model: Any, assembly: Any, configuration_name: str, view_name: str
) -> None:
    from solidworks_mcp.adapters.com_variant import null_callout

    if not assembly.CreateExplodedView():
        raise RuntimeError(f"{view_name}: CreateExplodedView failed")
    names = tuple(assembly.GetExplodedViewNames2(configuration_name) or ())
    if len(names) != 1:
        raise RuntimeError(f"{view_name}: unexpected created views {names!r}")
    # Exploded views are configuration-tree AsmExploder features, not ordinary
    # assembly features discoverable through FeatureByName.
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(names[0]), "EXPLODEDVIEWS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"{view_name}: cannot select created exploded view {names[0]!r}")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectType3(1, 0)) != 43:  # swSelEXPLVIEWS
        raise RuntimeError(f"{view_name}: selection is not an exploded-view feature")
    feature = _early_bound(selection.GetSelectedObject6(1, 0), "IFeature")
    if feature is None or str(feature.GetTypeName2()) != "AsmExploder":
        raise RuntimeError(f"{view_name}: selected object is not an AsmExploder")
    feature.Name = view_name
    model.ClearSelection2(True)
    if not model.EditRebuild3() or tuple(
        assembly.GetExplodedViewNames2(configuration_name) or ()
    ) != (view_name,):
        raise RuntimeError(f"{view_name}: exploded-view feature rename did not persist")


@_telemetry.traced("assembly.pn_explode")
def _create_pn_explode(adapter: Any, configuration_name: str) -> None:
    """Author ``spec.EXPLODE_STEPS`` in the active ``configuration_name`` and
    leave the operational model collapsed (the ms-measuring-stick recipe).

    Run in Default and in Default Simplified
    (``_assembly.author_in_drawing_configurations``): a drawing view shows the
    explode of the configuration it references."""
    from solidworks_mcp.adapters.com_variant import null_callout

    view_name = pn_exploded_view_name(configuration_name)
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != configuration_name:
        raise RuntimeError(
            f"{view_name} requires the active {configuration_name} configuration, "
            f"not {configuration.Name!r}"
        )
    if int(assembly.GetExplodedViewCount2(configuration_name)):
        raise RuntimeError(f"{view_name}: {configuration_name} unexpectedly contains exploded views")

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    groups: dict[str, list[Any]] = {stem: [] for stem in spec.QUANTITIES}
    for component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise RuntimeError(f"{view_name}: unexpected component {component.Name2}: {stem}")
        groups[stem].append(component)
    counts = {stem: len(group) for stem, group in groups.items()}
    if counts != spec.QUANTITIES:
        raise RuntimeError(f"{view_name} component counts: {counts!r} != {spec.QUANTITIES!r}")
    baseline = {str(component.Name2): _presentation_transform(component) for component in components}
    if len(baseline) != sum(spec.QUANTITIES.values()):
        raise RuntimeError(f"{view_name}: duplicate component identities")
    expected = {name: [0.0, 0.0, 0.0] for name in baseline}
    axes = _global_axes(adapter, assembly, view_name)

    _create_named_view(model, assembly, configuration_name, view_name)
    if not assembly.ShowExploded2(True, view_name):
        raise RuntimeError(f"{view_name}: cannot activate authored view")
    try:
        for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(f"{view_name}: cannot remove auto step {index}")
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError(f"{view_name}: auto steps remain")
        for step_index, (label, stems, key, distance_mm) in enumerate(spec.EXPLODE_STEPS, 1):
            moved = [component for stem in stems for component in groups[stem]]
            distance = distance_mm / 1000.0
            with _telemetry.span("assembly.pn_explode.step", label=label, moved=len(moved)):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(f"{label}: cannot create component selection data")
                data.Mark = 1
                for component in moved:
                    if not component.Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {component.Name2}")
                axis_name, positive = axes[key]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                ):
                    raise RuntimeError(f"{label}: cannot select global direction {axis_name} with mark 2")
                # Explicit entity only; -1 omits the component-local manipulator.
                # Early-bound wrapper returns (IExplodeStep, error); omit [out].
                result = configuration.AddExplodeStep2(
                    abs(distance), -1, (distance > 0.0) != positive,
                    0.0, -1, False, True, False,
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                step = _early_bound(raw_step, "IExplodeStep")
                # Distinct per explode: Default Simplified's copy carries the suffix.
                step_name = f"PN {label.upper()}"
                if configuration_name != spec.SOURCE_CONFIGURATION:
                    step_name = simplified_name(step_name)
                step.Name = step_name
                if str(step.Name) != step_name or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(f"{label}: authored step count is not {step_index}")
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if actual != intended or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9:
                    raise RuntimeError(f"{label}: step component/distance readback mismatch: {actual!r}")
                for name in intended:
                    expected[name]["xyz".index(key)] += distance
                # Read every instance, the unmoved ones too.
                for component in components:
                    name = str(component.Name2)
                    current = _presentation_transform(component)
                    delta = tuple(current[i + 9] - baseline[name][i + 9] for i in range(3))
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
                        raise RuntimeError(
                            f"{label}: {name} world translation mm "
                            f"{tuple(value * 1000.0 for value in delta)!r} != "
                            f"{tuple(value * 1000.0 for value in expected[name])!r}; "
                            f"direction={axis_name}, signed distance={distance_mm:g} mm"
                        )
                    if any(abs(current[i] - baseline[name][i]) > 1e-9 for i in (*range(9), 12)):
                        raise RuntimeError(f"{label}: {name} presentation rotated or scaled")
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, view_name) or not model.EditRebuild3():
                raise RuntimeError(f"{view_name}: failed to restore collapsed operational assembly")
            for component in components:
                name = str(component.Name2)
                current = _presentation_transform(component)
                transform = _early_bound(component.Transform2, "IMathTransform")
                operational = tuple(float(value) for value in transform.ArrayData)
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational) for i in range(16)
                ):
                    raise RuntimeError(f"{view_name}: collapse changed operational transform of {name}")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{view_name}: cleanup after authoring failure: {cleanup_error}")
    if int(configuration.GetNumberOfExplodeSteps()) != len(spec.EXPLODE_STEPS):
        raise RuntimeError(f"{view_name}: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2(configuration_name) or ()) != (view_name,):
        raise RuntimeError(f"{view_name}: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(view_name)) != configuration_name:
        raise RuntimeError(f"{view_name}: named presentation is not owned by {configuration_name}")
    _telemetry.success(
        f"{view_name}: {len(spec.EXPLODE_STEPS)} native steps verified in world space; "
        f"all {len(components)} instances restored"
    )


def _construction(adapter: Any, line: str, label: str) -> None:
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{label} is not construction")


async def _author_stud_setting(adapter: Any) -> None:
    """STUD HEIGHT: a vertical construction line on the rod axis from the
    rod's top face to the stud's head top (Front plane, sketch = machine X,
    Y), its length the toleranced setting. No solid or pose edits."""
    (x, rod_top_y), (_x, head_top_y) = spec.STUD_LINE
    dims = SketchDims()
    check("create stud setting sketch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    line = check("stud setting line", await adapter.add_line(x, rod_top_y, x, head_top_y))
    set_sketch_direct_db(adapter, False)
    _construction(adapter, line, "stud setting line")
    check("stud setting vertical", await adapter.add_sketch_constraint(line, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{line}.start", x, rod_top_y, "rod top on axis")
    dims.record("StudRodAxisX")
    dims.record("StudRodTopY")
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "vertical_distance",
        spec.STUD_HEIGHT, "stud head top above rod top",
    )
    dims.record(spec.STUD_DIMENSION)
    await ensure_fully_defined(adapter, "stud setting")
    check("exit stud setting sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.STUD_FEATURE)
    dims.apply(adapter, spec.STUD_FEATURE)
    set_dimension_symmetric_tolerance(
        adapter, spec.STUD_FEATURE, spec.STUD_DIMENSION, spec.STUD_TOLERANCE_MM
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


async def _author_carriage_setting(adapter: Any) -> None:
    """PEN YAW and NIB PRESET on the Top plane (sketch u, v = machine X, -Z):
    from the marker axis at the block's paper-end face, a rod-flat arm along
    machine -X and the marker-axis arm to the nib tip. Their angle is the yaw,
    the second arm's length the nib preset. No solid or pose edits."""
    end_u, end_v = spec.CARRIAGE_END_UV
    dims = SketchDims()
    check("create carriage setting sketch", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    # Both arms start on the one end-face point (exactly coincident
    # endpoints merge in the sketch database).
    flat = check("rod-flat arm", await adapter.add_line(end_u, end_v, *spec.FLAT_END_UV))
    nib = check("marker-axis arm", await adapter.add_line(end_u, end_v, *spec.NIB_UV))
    set_sketch_direct_db(adapter, False)
    _construction(adapter, flat, "rod-flat arm")
    _construction(adapter, nib, "marker-axis arm")
    check("rod-flat arm horizontal", await adapter.add_sketch_constraint(flat, None, "horizontal"))
    await anchor_point_to_origin(adapter, f"{flat}.start", end_u, end_v, "paper-end point")
    dims.record("CarriageEndX")
    dims.record("CarriageEndZ")
    await dimension_between(
        adapter, f"{flat}.start", f"{flat}.end", "horizontal_distance",
        spec.FLAT_LINE_LENGTH, "rod-flat arm",
    )
    dims.record("RodFlatArm")
    await dimension_between(
        adapter, f"{nib}.start", f"{nib}.end", "distance",
        spec.NIB_PROTRUSION, "nib beyond the paper-end face",
    )
    dims.record(spec.NIB_DIMENSION)
    _add_driving_yaw_angle(adapter, nib, flat)
    dims.record(spec.YAW_DIMENSION)
    await ensure_fully_defined(adapter, "carriage setting")
    check("exit carriage setting sketch", await adapter.exit_sketch())
    name_last_feature(adapter, spec.CARRIAGE_FEATURE)
    dims.apply(adapter, spec.CARRIAGE_FEATURE)
    set_dimension_symmetric_tolerance(
        adapter, spec.CARRIAGE_FEATURE, spec.NIB_DIMENSION, spec.NIB_TOLERANCE_MM
    )
    set_dimension_symmetric_angular_tolerance(
        adapter, spec.CARRIAGE_FEATURE, spec.YAW_DIMENSION, spec.YAW_TOLERANCE_DEG
    )


async def _author_settings(adapter: Any) -> None:
    """Both setting sketches, their places, drawing marks, then blanked."""
    await _author_stud_setting(adapter)
    await _author_carriage_setting(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    for feature, names in spec.DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature, names)
        blank_sketch(adapter, feature)


async def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

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
    hanger = await place_component(
        adapter, "pn-pen-hanger", list(HANGER_POS), [0.0, 0.0, 0.0], IDENTITY
    )
    pen_rod = await place_component(
        adapter,
        "pn-pen-rod",
        list(PEN_ROD_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    rod_o = component_origin(adapter, pen_rod)
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Front Plane", "PLANE"),
        rod_o[2],
        label="pen-rod slide depth",
        verify=(pen_rod, rod_o),
    )
    await distance_driver(
        adapter,
        named_ref(f"Axis1@{pen_rod}", "AXIS"),
        named_ref("Right Plane", "PLANE"),
        rod_o[0],
        label="pen-rod slide across",
        verify=(pen_rod, rod_o),
    )
    await angle_driver(
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
    await distance_driver(
        adapter,
        named_ref(f"Top Plane@{pen_rod}", "PLANE"),
        named_ref("Top Plane", "PLANE"),
        rod_o[1],
        label="pen-rod travel PARK driver (freed in default build)",
        verify=(pen_rod, rod_o),
        free_dof_key="pen_travel",
    )

    for part, pos, rows in RIDERS:
        name = await place_component(
            adapter, part, list(pos), euler_from_rows(rows), rows, ground=False
        )
        await lock_mate(
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

    hanger_screw = await place_component(
        adapter,
        "vn-hanger-screw",
        list(HANGER_SCREW_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await coincident_mate(
        adapter,
        named_ref(f"ScrewAxis@{hanger_screw}", "AXIS"),
        named_ref(f"HangerScrewAxis@{hanger}", "AXIS"),
        label="hanger screw coaxial with strap clearance hole",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{hanger_screw}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        HANGER_SCREW_POS[2],
        label="hanger screw head plane",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    await parallel_mate(
        adapter,
        named_ref(f"Right Plane@{hanger_screw}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        label="hanger screw anti-spin",
        verify=(hanger_screw, list(HANGER_SCREW_POS)),
    )
    assert_component_placed(adapter, hanger_screw, list(HANGER_SCREW_POS), IDENTITY)

    # The nut on the strap front and the jam nut on the nut: each placed on
    # the screw axis at its exact pose and locked to the fixed hanger -- one
    # Lock mate, like the riders; a coaxial mate on top would only
    # over-constrain the solve.
    for stem, pos, label in (
        ("vn-pen-hanger-nut", HANGER_NUT_POS, "hanger nut locked to hanger"),
        (
            "vn-pen-hanger-jam-nut",
            HANGER_JAM_NUT_POS,
            "hanger jam nut locked to hanger",
        ),
    ):
        nut = await place_component(
            adapter, stem, list(pos), [0.0, 0.0, 0.0], IDENTITY, ground=False
        )
        await lock_mate(
            adapter,
            named_ref(f"Front Plane@{nut}", "PLANE"),
            named_ref(f"Front Plane@{hanger}", "PLANE"),
            label=label,
        )
        assert_component_placed(adapter, nut, list(pos), IDENTITY)

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
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # The fitter drawing's settings: driving, toleranced model dimensions on
    # blanked construction sketches, authored once the as-built model is
    # certified (they touch no component, mate or pose).
    await _author_settings(adapter)
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
        adapter, ASM_NAME, lambda configuration: _create_pn_explode(adapter, configuration)
    )
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
