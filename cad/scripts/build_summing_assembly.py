r"""Reproduction script: summing subassembly (book ch. 18-19).

The head of the analyzer's output, where the 20 channel springs converge on
the summing lever, in machine coordinates (assembly origin = base origin;
base top y = 50.8; the output side is -Z). The lever rocks on a true knife
edge carried by two bearing supports, hung from the top-frame casting's
integral crossbar by two knife-hanger studs, and counter-balanced from
above by the boss-hook / counter-spring / gooseneck chain.

* knife-mount x2 -- the bearing supports, one per hex trunnion, centred on
  ``SUMMING_Z`` and separated by ``+/-HEX_Z_MID``.
* knife-hanger-washer x2 -- McMaster 90126A211 washers seated separately on
  the casting top face, one at each mount centreline.
* knife-hanger-stud x2 -- modified/shortened McMaster 91247A720 bolts under
  the stable legacy stem: each passes through its washer and the casting's
  clearance hole, then threads into the knife-mount's 1/2-13 top tap.
* summing-lever -- rocks on the knife edge (Axis3 coincident to the support
  contact ridge); the part the channel + counter springs drive in the M6
  Motion study. The rock is the sub's single FREED operational DOF: its
  drive spec is recorded into the DOF manifest, never authored, so the
  saved model rocks on the knife edge.
* boss-hook (keyed to the lever's anchor eye) + counter-spring + gooseneck
  -- the counter-balance hung from the east column; the post is gripped by
  the top-frame rail hub's set screw (no separate clamp part).

Cross-subassembly fits (checked at the top level): the channel springs
(channel.SLDASM) thread the summing-lever plate's O4.5 holes -- gated
analytically by build_channel_assembly._assert_plate_threading; the knife-
hanger studs rise through the top-frame casting's integral crossbar (O13.49
close-clearance holes, frame.SLDASM); the gooseneck post drops through the
casting's rail-hub bore, gripped by its 1/4-20 set screw.

Fix-all strategy (M6.2): every structural component inserted at its exact
final transform and fixed; the summing lever + boss-hook are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 18-19.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_summing_assembly.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry

from _common import (
    apply_custom_properties,
    _early_bound,
    apply_summary_info,
    check,
    log,
    run_build,
)
import settled_spring_seats
from _drawing_marks import DRAWN_BY
from _assembly import (
    angle_driver,
    assembly_title_properties,
    assert_free_dof_necessity,
    check_no_interference,
    coincident_mate,
    component_names,
    component_origin,
    component_transform,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    reset_dof_manifest,
    save_assembly_and_images,
    write_dof_manifest,
)
from _assembly_patterns import ensure_global_pattern_axis
from _native_spring_contact import assert_assembly_spring_contacts
from _interference_contracts import allowed_interference_pairs
from _transforms import IDENTITY, ROT_Y_180, euler_from_rows
from cone_pivot_post_installation import SUMMING_Z
from build_knife_hanger_stud import (
    SHANK_DIA as BOLT_MAJOR_DIA,
    THREAD_TIP_Y_MM,
    UNDERHEAD_Y_MM,
)
from build_knife_hanger_washer import (
    INNER_DIA as HANGER_WASHER_INNER_DIA,
    OUTER_DIA as HANGER_WASHER_OUTER_DIA,
    THICKNESS as HANGER_WASHER_THICKNESS,
)
from build_knife_mount import (
    CASTING_UNDERSIDE_Y,
    MOUNT_GAP,
    STUD_TAP_THREAD_DEPTH_MM,
)
from build_top_frame import RING_HEIGHT as CROSSBAR_HEIGHT, STUD_HOLE_DIA
from summing_assembly_spec import (
    BOM_QUANTITIES,
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
)

ASM_NAME = "summing"

from spring_mount_geom import COLUMN_X, KNIFE, KNIFE_CONTACT_Y  # noqa: E402

# --- knife bearing supports (build_knife_mount) -----------------------------
from summing_lever_spec import HEX_Z_INNER, HEX_Z_OUTER  # noqa: E402

HEX_Z_MID = (HEX_Z_INNER + HEX_Z_OUTER) / 2.0  # hex trunnion mid (87.06)

# --- knife-hanger hardware (two bolts + two separate washers) ----------------
# The top-frame crossbar and knife-mount exports own the surrounding stack.
# Each washer's local origin is its mid-plane. The modified 91247A720 remains in
# its supplier-native frame, so its exported under-head and trimmed-tip stations
# determine seating and engagement without a synthetic tip-zero transform.
CROSSBAR_TOP_Y = CASTING_UNDERSIDE_Y + CROSSBAR_HEIGHT
HANGER_WASHER_Y = CROSSBAR_TOP_Y + HANGER_WASHER_THICKNESS / 2.0
HANGER_WASHER_TOP_Y = CROSSBAR_TOP_Y + HANGER_WASHER_THICKNESS
HANGER_STUD_Y = HANGER_WASHER_TOP_Y - UNDERHEAD_Y_MM
KNIFE_MOUNT_TOP_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP
KNIFE_MOUNT_THREAD_ENGAGEMENT = KNIFE_MOUNT_TOP_Y - (
    HANGER_STUD_Y + THREAD_TIP_Y_MM
)


def _assert_hanger_axis_positive_y(name: str, transform: list[float]) -> None:
    """Require the authored fastener axis to remain assembly +Y."""
    axis = transform[3:6]
    expected = (0.0, 1.0, 0.0)
    drift = max(
        abs(actual - target) for actual, target in zip(axis, expected, strict=True)
    )
    if drift > 1e-3:
        raise RuntimeError(
            f"{name}: local +Y fastener axis {axis} is not assembly +Y "
            f"(drift {drift:.4f})"
        )


def _assert_knife_hanger_stack() -> None:
    """Gate the purchased washer/bolt stack before any COM insertion."""
    bolt_in_washer_clearance = HANGER_WASHER_INNER_DIA - BOLT_MAJOR_DIA
    bolt_in_crossbar_clearance = STUD_HOLE_DIA - BOLT_MAJOR_DIA
    washer_crossbar_seat = (HANGER_WASHER_OUTER_DIA - STUD_HOLE_DIA) / 2.0
    if bolt_in_washer_clearance <= 0.0:
        raise RuntimeError(
            "knife-hanger washer ID does not clear the 91247A720 bolt: "
            f"{bolt_in_washer_clearance:.4f} mm diametral clearance"
        )
    if bolt_in_crossbar_clearance <= 0.0:
        raise RuntimeError(
            "knife-hanger bolt does not clear the crossbar hole: "
            f"{bolt_in_crossbar_clearance:.4f} mm diametral clearance"
        )
    if washer_crossbar_seat <= 0.0:
        raise RuntimeError(
            "knife-hanger washer OD does not seat beyond the crossbar hole: "
            f"{washer_crossbar_seat:.4f} mm radial bearing width"
        )

    washer_lower_y = HANGER_WASHER_Y - HANGER_WASHER_THICKNESS / 2.0
    washer_upper_y = HANGER_WASHER_Y + HANGER_WASHER_THICKNESS / 2.0
    bolt_under_head_y = HANGER_STUD_Y + UNDERHEAD_Y_MM
    bolt_tip_y = HANGER_STUD_Y + THREAD_TIP_Y_MM
    if abs(washer_lower_y - CROSSBAR_TOP_Y) > 1e-9:
        raise RuntimeError("knife-hanger washer lower face is not seated on crossbar")
    if abs(bolt_under_head_y - washer_upper_y) > 1e-9:
        raise RuntimeError("knife-hanger bolt under-head face is not seated on washer")
    if not 0.0 < KNIFE_MOUNT_THREAD_ENGAGEMENT <= STUD_TAP_THREAD_DEPTH_MM:
        raise RuntimeError(
            "knife-hanger bolt misses the knife-mount full-thread envelope: "
            f"{KNIFE_MOUNT_THREAD_ENGAGEMENT:.4f} mm engagement, "
            f"{STUD_TAP_THREAD_DEPTH_MM:.4f} mm usable thread"
        )
    log(
        "knife-hanger stack: washer "
        f"{washer_lower_y:.4f}..{washer_upper_y:.4f}, bolt under-head "
        f"{bolt_under_head_y:.4f}, tip {bolt_tip_y:.4f}, "
        f"engagement {KNIFE_MOUNT_THREAD_ENGAGEMENT:.4f}; "
        f"ID clearance {bolt_in_washer_clearance:.4f}, crossbar clearance "
        f"{bolt_in_crossbar_clearance:.4f}, radial seat {washer_crossbar_seat:.4f} mm"
    )


# --- purchased counter spring and directly threaded lower anchor -----------
import counter_spring_stock_geom as counter_stock  # noqa: E402
import gooseneck_geom  # noqa: E402
import spring_mount_geom as spring_mounts  # noqa: E402
import summing_lever_spec  # noqa: E402
from stock_anchor_geom import ANCHOR_9490T1  # noqa: E402

BOSS_HOOK_POS = (*spring_mounts.COUNTER_ANCHOR_XY, SUMMING_Z)
# The counter spring uses its complete calibrated placement, and the gooseneck
# is inserted with the spring eye clamped in its released default screw state.


def _assert_counter_spring_top_hang(
    pose: spring_mounts.SpringPose,
    gooseneck_y: float,
) -> None:
    """Bound the clamped upper eye at the fixed measured placement.

    The saved calibration must be based on the released clamped screw geometry,
    never the former 8 mm setup opening. Native body contact and zero overlap
    are certified separately against the final component instances.
    """
    ux, uy = pose.axis_xy
    screw_y = gooseneck_y + gooseneck_geom.ARM_Y
    clamped_gap = gooseneck_geom.SPRING_SCREW_CLAMPED_GAP_MM
    # Natively calibrated: the loop seats on the tube's OD corner and the head
    # closes onto it, so centre and gap both fall inside the purchased band.
    if not (
        0.0
        < gooseneck_geom.SPRING_EYE_CENTRE_FROM_ARM_END_MM
        < clamped_gap
        < counter_stock.END_OCCUPIED_WIDTH_MM
    ):
        raise RuntimeError(
            "gooseneck clamp calibration falls outside the purchased spring eye band"
        )
    clamped_eye_x = spring_mounts.COUNTER_UPPER_EYE_X
    open_eye_x = (
        spring_mounts.GOOSENECK_END_X
        + gooseneck_geom.SPRING_SCREW_OPEN_GAP_MM / 2.0
    )
    centre_error = pose.upper_eye_xy[0] - clamped_eye_x
    if abs(centre_error) >= abs(pose.upper_eye_xy[0] - open_eye_x):
        raise RuntimeError(
            "counter spring calibration still uses the obsolete open screw "
            "position; rerun diagnostics/calibrate_spring_seats.py for the "
            "clamped gooseneck geometry"
        )
    retention = (gooseneck_geom.SCREW_HEAD_DIA - counter_stock.EYE_ID_MM) / 2.0
    if retention < 1.0:
        raise RuntimeError(f"counter eye head retention only {retention:.3f} mm radial")
    projected_band = (
        abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + abs(uy) * counter_stock.LOOP_HALF_RISE_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    arm_side = pose.upper_eye_xy[0] - spring_mounts.GOOSENECK_END_X
    head_side = (
        spring_mounts.GOOSENECK_END_X
        + clamped_gap
        - pose.upper_eye_xy[0]
    )
    coil_top = (
        pose.centre_xy[1]
        + uy * counter_stock.coil_end_x_mm(pose.length_mm)
        + abs(ux) * counter_stock.COIL_MEAN_RADIUS_MM
        + counter_stock.WIRE_RADIUS_MM
    )
    main_coil_gap = screw_y - gooseneck_geom.TUBE_DIA / 2.0 - coil_top
    tube_gap, head_gap = spring_mounts.counter_half_turn_clearances(pose, screw_y)
    if min(main_coil_gap, tube_gap, head_gap) < spring_mounts.MIN_CLEARANCE_MM:
        raise RuntimeError(
            f"counter coil/support clearance: main {main_coil_gap:.3f}, "
            f"half-turn/tube {tube_gap:.3f}, half-turn/head {head_gap:.3f} mm"
        )
    log(
        f"counter upper clamp: head retention {retention:.3f}, "
        f"centre error {centre_error:.6f}, eye half-band projection "
        f"{projected_band:.3f}, arm/head spans {arm_side:.3f}/{head_side:.3f}, "
        f"main coil {main_coil_gap:.3f}, half-turn tube/head "
        f"{tube_gap:.3f}/{head_gap:.3f} mm"
    )


def _assert_counter_spring_hang(pose: spring_mounts.SpringPose) -> None:
    """Require full direct thread engagement and a tensioned supplier spring."""
    anchor = ANCHOR_9490T1
    tap = summing_lever_spec.COUNTER_HOLE_SPEC
    if tap.kind != "tapped" or tap.size != anchor.thread_size:
        raise RuntimeError("counter anchor requires its matching native through tap")
    thread_top = BOSS_HOOK_POS[1] + anchor.thread_start_y_mm
    boss_top = KNIFE[1] + summing_lever_spec.ANCHOR_H / 2.0
    if abs(thread_top - boss_top) > 1e-6:
        raise RuntimeError("counter anchor thread start is not at the boss face")
    if spring_mounts.COUNTER_SHANK_LENGTH_MM < summing_lever_spec.ANCHOR_H - 1e-6:
        raise RuntimeError("trimmed counter anchor does not engage the full boss")
    counter_stock.validate_length_mm(pose.length_mm)
    log(
        f"counter lower anchor: {tap.size} direct through tap, "
        f"{summing_lever_spec.ANCHOR_H:.3f} mm engagement; "
        f"spring inside length {pose.length_mm:.4f} mm, "
        f"calibrated force {spring_mounts.counter_force_n(pose.length_mm):.3f} N"
    )


def _explode_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{component.Name2}: invalid presentation transform {values!r}")
    return values


@_telemetry.traced("assembly.summing_explode")
def _create_summing_explode(adapter: Any) -> None:
    """Author the released seven-step presentation and restore the free model."""
    from solidworks_mcp.adapters.com_variant import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME} requires the builder's "
            f"{SOURCE_CONFIGURATION} configuration"
        )
    if int(assembly.GetExplodedViewCount2(SOURCE_CONFIGURATION)):
        raise RuntimeError("new summing assembly unexpectedly contains exploded views")

    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    groups: dict[str, list[Any]] = {stem: [] for stem in BOM_QUANTITIES}
    for component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise RuntimeError(
                f"{EXPLODED_VIEW_NAME}: unexpected component "
                f"{component.Name2}: {stem}"
            )
        groups[stem].append(component)
    actual_counts = {stem: len(group) for stem, group in groups.items()}
    if actual_counts != BOM_QUANTITIES:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME} component counts: "
            f"{actual_counts!r} != {BOM_QUANTITIES!r}"
        )
    for group in groups.values():
        group.sort(key=lambda component: str(component.Name2))

    baseline = {
        str(component.Name2): _explode_transform(component)
        for component in components
    }
    if len(baseline) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: duplicate component identities")
    expected = {name: [0.0, 0.0, 0.0] for name in baseline}

    supports = sorted(
        groups["knife-mount"],
        key=lambda component: baseline[str(component.Name2)][11],
    )
    if len(supports) != 2:
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: expected two knife supports")
    plans = (
        ("hanger bolts lift", groups["knife-hanger-stud"], "y", 0.080),
        ("hanger washers lift", groups["knife-hanger-washer"], "y", 0.040),
        ("front support withdraws", [supports[1]], "z", 0.050),
        ("back support withdraws", [supports[0]], "z", -0.050),
        ("counter anchor lifts", groups["boss-hook"], "y", 0.035),
        ("counter spring moves clear", groups["counter-spring"], "x", -0.060),
        ("gooseneck lifts", groups["gooseneck"], "y", 0.080),
    )

    axes = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(
                f"{EXPLODED_VIEW_NAME}: missing reference axis {axis_name}"
            )
        axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
        points = tuple(float(value) for value in axis.GetRefAxisParams())
        if len(points) != 6 or not all(math.isfinite(value) for value in points):
            raise RuntimeError(f"{axis_name}: invalid axis endpoints {points!r}")
        vector = tuple(points[i + 3] - points[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        if length <= 1e-12 or any(
            abs(vector[i] / length) > 1e-9
            for i in range(3)
            if i != index
        ):
            raise RuntimeError(
                f"{axis_name}: not aligned with world {key.upper()}: {vector!r}"
            )
        axes[key] = (axis_name, vector[index] > 0.0)

    if not assembly.CreateExplodedView():
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: CreateExplodedView failed")
    names = tuple(
        assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
    )
    if len(names) != 1:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: unexpected created views {names!r}"
        )
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(names[0]),
        "EXPLODEDVIEWS",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: cannot select created exploded view "
            f"{names[0]!r}"
        )
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectType3(1, 0)) != 43:
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: selection is not an exploded-view feature"
        )
    feature = _early_bound(selection.GetSelectedObject6(1, 0), "IFeature")
    if feature is None or str(feature.GetTypeName2()) != "AsmExploder":
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: selected object is not an AsmExploder"
        )
    feature.Name = EXPLODED_VIEW_NAME
    model.ClearSelection2(True)
    if (
        not model.EditRebuild3()
        or tuple(
            assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
        )
        != (EXPLODED_VIEW_NAME,)
    ):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: exploded-view feature rename did not persist"
        )
    if not assembly.ShowExploded2(True, EXPLODED_VIEW_NAME):
        raise RuntimeError(f"{EXPLODED_VIEW_NAME}: cannot activate authored view")

    try:
        for index in range(
            int(configuration.GetNumberOfExplodeSteps()) - 1,
            -1,
            -1,
        ):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(
                    f"{EXPLODED_VIEW_NAME}: cannot remove auto step {index}"
                )
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError(f"{EXPLODED_VIEW_NAME}: auto steps remain")

        for step_index, (label, moved, key, distance) in enumerate(plans, 1):
            with _telemetry.span("assembly.summing_explode.step", label=label):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(
                        f"{label}: cannot create component selection data"
                    )
                data.Mark = 1
                if int(data.Mark) != 1:
                    raise RuntimeError(
                        f"{label}: component selection mark did not persist"
                    )
                for component in moved:
                    if not component.Select4(True, data, False):
                        raise RuntimeError(
                            f"{label}: cannot select {component.Name2}"
                        )
                axis_name, positive = axes[key]
                if not model.Extension.SelectByID2(
                    axis_name,
                    "AXIS",
                    0.0,
                    0.0,
                    0.0,
                    True,
                    2,
                    null_callout(),
                    0,
                ):
                    raise RuntimeError(
                        f"{label}: cannot select global direction "
                        f"{axis_name} with mark 2"
                    )
                result = configuration.AddExplodeStep2(
                    abs(distance),
                    -1,
                    (distance > 0.0) != positive,
                    0.0,
                    -1,
                    False,
                    True,
                    False,
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(
                        f"{label}: incomplete AddExplodeStep2 result {result!r}"
                    )
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(
                        f"{label}: AddExplodeStep2 error {error!r}"
                    )
                step = _early_bound(raw_step, "IExplodeStep")
                step.Name = f"SUMMING {label.upper()}"
                if (
                    str(step.Name) != f"SUMMING {label.upper()}"
                    or not model.EditRebuild3()
                ):
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(
                        f"{label}: authored step count is not {step_index}"
                    )
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if (
                    actual != intended
                    or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9
                ):
                    raise RuntimeError(
                        f"{label}: step component/distance readback mismatch: "
                        f"{actual!r}"
                    )
                for name in intended:
                    expected[name]["xyz".index(key)] += distance
                for component in components:
                    name = str(component.Name2)
                    current = _explode_transform(component)
                    delta = tuple(
                        current[i + 9] - baseline[name][i + 9]
                        for i in range(3)
                    )
                    _telemetry.event(
                        "assembly.summing_explode.translation",
                        step=label,
                        component=name,
                        expected_mm=[
                            value * 1000.0 for value in expected[name]
                        ],
                        actual_mm=[value * 1000.0 for value in delta],
                    )
                    if any(
                        abs(delta[i] - expected[name][i]) > 1e-7
                        for i in range(3)
                    ):
                        raise RuntimeError(
                            f"{label}: {name} world translation mm "
                            f"{tuple(value * 1000.0 for value in delta)!r} != "
                            f"{tuple(value * 1000.0 for value in expected[name])!r}; "
                            f"direction={axis_name}, "
                            f"signed distance={distance * 1000.0:g} mm"
                        )
                    if any(
                        abs(current[i] - baseline[name][i]) > 1e-9
                        for i in (*range(9), 12)
                    ):
                        raise RuntimeError(
                            f"{label}: {name} presentation rotated or scaled"
                        )
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if (
                not assembly.ShowExploded2(False, EXPLODED_VIEW_NAME)
                or not model.EditRebuild3()
            ):
                raise RuntimeError(
                    f"{EXPLODED_VIEW_NAME}: failed to restore collapsed "
                    "operational assembly"
                )
            for component in components:
                name = str(component.Name2)
                current = _explode_transform(component)
                transform = _early_bound(component.Transform2, "IMathTransform")
                operational = tuple(float(value) for value in transform.ArrayData)
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational)
                    for i in range(16)
                ):
                    raise RuntimeError(
                        f"{EXPLODED_VIEW_NAME}: collapse changed "
                        f"operational transform of {name}"
                    )
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(
                f"{EXPLODED_VIEW_NAME}: cleanup after authoring failure: "
                f"{cleanup_error}"
            )

    if int(configuration.GetNumberOfExplodeSteps()) != len(plans):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: collapsed presentation lost authored steps"
        )
    if tuple(
        assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
    ) != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: collapsed presentation lost named view"
        )
    if (
        str(assembly.GetExplodedViewConfigurationName(EXPLODED_VIEW_NAME))
        != SOURCE_CONFIGURATION
    ):
        raise RuntimeError(
            f"{EXPLODED_VIEW_NAME}: named presentation is not owned by "
            f"{SOURCE_CONFIGURATION}"
        )
    _telemetry.success(
        f"{EXPLODED_VIEW_NAME}: seven native steps verified in world space; "
        "all ten instances restored"
    )


async def build(adapter) -> dict[str, str]:
    counter_seat, gooseneck_origin_y = settled_spring_seats.counter_seat()
    counter_pose = counter_seat.pose
    _assert_counter_spring_hang(counter_pose)
    _assert_counter_spring_top_hang(counter_pose, gooseneck_origin_y)
    _assert_knife_hanger_stack()

    # Reset the free-DOF manifest buffer before any *_driver(free_dof_key=...)
    # call: each freed DOF is recorded (never authored) and persisted below.
    reset_dof_manifest()
    check("create_assembly", await adapter.create_assembly())

    # Two knife bearing supports, one per hex trunnion (overhanging the lever
    # body at SUMMING_Z +/- HEX_Z_MID). The front support is FIRST so the auto-fixed assembly
    # seed is structure, not the mated summing lever. Each support's circular
    # bore is much larger than the hex, so only the trunnion's top vertex line
    # (the knife edge) nears the upper inner wall. The named "knife axis" is that
    # contact ridge line; the lever's Axis3 (hex ridge) mates coincident to it.
    km = await place_component(
        adapter,
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z + HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (front)",
    )
    await place_component(
        adapter,
        "knife-mount",
        [KNIFE[0], KNIFE_CONTACT_Y, SUMMING_Z - HEX_Z_MID],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="knife-mount (back)",
    )
    # Purchased-then-modified knife-hanger hardware: one fixed washer + bolt
    # pair on each mount centreline. The washer lower face is exactly on the
    # crossbar top, and the modified 91247A720 under-head face is exactly on
    # the washer upper face. Both parts are independently fixed at the authored
    # transforms, so this structural stack contributes no operational DOF.
    hanger_washers: list[str] = []
    hanger_bolts: list[str] = []
    for side, station_z in (
        ("front", SUMMING_Z + HEX_Z_MID),
        ("back", SUMMING_Z - HEX_Z_MID),
    ):
        hanger_washers.append(
            await place_component(
                adapter,
                "knife-hanger-washer",
                [KNIFE[0], HANGER_WASHER_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-washer ({side})",
            )
        )
        hanger_bolts.append(
            await place_component(
                adapter,
                "knife-hanger-stud",
                [KNIFE[0], HANGER_STUD_Y, station_z],
                [0.0, 0.0, 0.0],
                IDENTITY,
                ground=True,
                label=f"knife-hanger-stud ({side})",
            )
        )

    # Count the live top-level instances, not just the placement requests:
    # exactly two modified bolts and two separate washers must survive insertion.
    live_names = component_names(adapter)
    for stem, inserted in (
        ("knife-hanger-washer", hanger_washers),
        ("knife-hanger-stud", hanger_bolts),
    ):
        live = [
            name for name in live_names if name == stem or name.startswith(f"{stem}-")
        ]
        if len(live) != 2 or set(live) != set(inserted):
            raise RuntimeError(
                f"{stem}: expected exactly two inserted instances, got {sorted(live)}"
            )

    # Read back both physical stacks.  This catches a per-instance station
    # typo that the shared scalar derivation alone cannot: each washer must
    # remain coaxial with its bolt, on the crossbar, with zero axial gap at
    # the under-head face and the exact residual tap engagement.
    for washer, bolt in zip(hanger_washers, hanger_bolts, strict=True):
        washer_transform = component_transform(adapter, washer)
        bolt_transform = component_transform(adapter, bolt)
        _assert_hanger_axis_positive_y(washer, washer_transform)
        _assert_hanger_axis_positive_y(bolt, bolt_transform)
        washer_o = [value * 1000.0 for value in washer_transform[9:12]]
        bolt_o = [value * 1000.0 for value in bolt_transform[9:12]]
        radial_offset = max(
            abs(washer_o[0] - bolt_o[0]),
            abs(washer_o[2] - bolt_o[2]),
        )
        washer_lower_y = washer_o[1] - HANGER_WASHER_THICKNESS / 2.0
        washer_upper_y = washer_o[1] + HANGER_WASHER_THICKNESS / 2.0
        bolt_under_head_y = bolt_o[1] + UNDERHEAD_Y_MM
        bolt_tip_y = bolt_o[1] + THREAD_TIP_Y_MM
        engagement = KNIFE_MOUNT_TOP_Y - bolt_tip_y
        if radial_offset > 1e-6:
            raise RuntimeError(
                f"{bolt}: washer/bolt axes offset {radial_offset:.6f} mm"
            )
        if abs(washer_lower_y - CROSSBAR_TOP_Y) > 1e-6:
            raise RuntimeError(
                f"{washer}: lower face misses crossbar by "
                f"{washer_lower_y - CROSSBAR_TOP_Y:.6f} mm"
            )
        if abs(bolt_under_head_y - washer_upper_y) > 1e-6:
            raise RuntimeError(
                f"{bolt}: under-head/washer gap "
                f"{bolt_under_head_y - washer_upper_y:.6f} mm"
            )
        if abs(engagement - KNIFE_MOUNT_THREAD_ENGAGEMENT) > 1e-6:
            raise RuntimeError(
                f"{bolt}: knife-mount engagement drifted to {engagement:.6f} mm"
            )
    # Summing lever: knife-edge revolute = coincident axis-to-axis on the knife
    # line (the bore-bottom rocking edge) + a Front-plane axial distance,
    # leaving the rock DOF -- the sub's freed operational DOF (its drive spec
    # recorded into the DOF manifest, never authored). This is the part the
    # counter spring + channel springs drive in the M6 Motion study.
    sl = await place_component(
        adapter,
        "summing-lever",
        [KNIFE[0], KNIFE[1], SUMMING_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    sl_o = component_origin(adapter, sl)
    # summing-lever axes (creation order): Axis1 = pivot (cylinder centre),
    # Axis2 = anchor, Axis3 = knife ridge (hex top vertex). The lever rocks on
    # the true knife edge: Axis3 mates coincident to the support's contact ridge
    # ("knife axis" = Axis1@knife-mount). Same pose as the cylinder-centre mate
    # (ridge is 5.13 above the centre, both collinear along Z), but the freed
    # rock DOF is now about the knife edge, per the bearing-support design.
    await coincident_mate(
        adapter,
        named_ref(f"Axis3@{sl}", "AXIS"),
        named_ref(f"Axis1@{km}", "AXIS"),
        label="summing-lever knife pivot",
        verify=(sl, sl_o),
    )
    # Axial Z-slide pinned by a Front-plane distance (value 0: the lever sits on
    # the assembly Front plane). Then the rock (Rz about the knife line) is the
    # suppressible snapshot driver -- an ANGLE between Right planes, NOT the
    # off-axis spin_driver: the boss "spin ref" sits directly -X of the pivot
    # (Δy=0), so its distance-to-Top is degenerate and over-defines, whereas the
    # angle is well-conditioned and (inserted on-solution) holds without a flip.
    await distance_driver(
        adapter,
        named_ref(f"Front Plane@{sl}", "PLANE"),
        named_ref("Front Plane", "PLANE"),
        abs(sl_o[2]),
        label="summing-lever axial",
        verify=(sl, sl_o),
    )
    # The rock about the knife line is the sub's FREED operational DOF: its
    # drive spec (an ANGLE between Right planes -- the boss "spin ref"
    # distance-to-Top is degenerate here, see above) is recorded into the DOF
    # manifest, never authored -- drag the lever and it rocks on the knife
    # edge, per the magnifier lever_rock idiom.
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{sl}", "PLANE"),
        named_ref("Right Plane", "PLANE"),
        0.0,
        label="summing-lever rock PARK driver (freed in default build)",
        verify=(sl, sl_o),
        free_dof_key="lever_rock",
    )
    # The purchased, trimmed open eye threads directly into the lever's boss.
    # Locking records that rigid threaded connection while preserving lever rock.
    bh = await place_component(
        adapter,
        "boss-hook",
        list(BOSS_HOOK_POS),
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
    )
    await lock_mate(
        adapter,
        named_ref(f"ScrewAxis@{bh}", "AXIS"),
        named_ref(f"Axis2@{sl}", "AXIS"),
        label="boss-hook keyed",
    )
    # Preserve the vendor +X coil frame and required half-turn clocking at the
    # complete fixed measured pose; no seed placement or corrective move follows.
    await place_component(
        adapter,
        "counter-spring",
        [*counter_pose.centre_xy, SUMMING_Z],
        euler_from_rows(counter_pose.rotation_rows),
        counter_pose.rotation_rows,
    )
    # Ry(180): the gooseneck's overhang arm reaches from the east column toward
    # the machine centre. Its measured origin Y is inserted directly; the post
    # is held in the top-frame rail-hub bore by its 1/4-20 set screw.
    await place_component(
        adapter,
        "gooseneck",
        [COLUMN_X, gooseneck_origin_y, SUMMING_Z],
        [0.0, 180.0, 0.0],
        ROT_Y_180,
    )

    # Certify the AS-BUILT model.  The lever rock remains the sole intended
    # freed DOF; the exact allowed-stem set rejects any free washer, bolt, or
    # other structural component.  The lock-mated boss-hook MUST read
    # under-constrained WITH the lever -- a grounded/fixed regression would
    # freeze the counter-spring anchor while the lever still swings.
    assert_free_dof_necessity(
        adapter,
        1,
        required_stems=("summing-lever", "boss-hook"),
        allowed_stems=("summing-lever", "boss-hook"),
    )
    write_dof_manifest(ASM_NAME)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_summing_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A07",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "summing assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    _create_summing_explode(adapter)
    return await save_assembly_and_images(
        adapter,
        ASM_NAME,
        native_contact_check=assert_assembly_spring_contacts,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))
