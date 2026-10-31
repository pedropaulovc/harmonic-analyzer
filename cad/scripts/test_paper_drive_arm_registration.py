"""Registration receiver/geometry regressions and the arm files' saved-GTOL
audit (real builds, seat stubbed), not operating-domain proof."""
from __future__ import annotations

import asyncio
import importlib
import math
from dataclasses import replace
from pathlib import Path

from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

import paper_drive_arm_registration as registration
import pd_transgear_arm_geometry as arm
import pd_transgear_arm_plate_geometry as plate
import pd_transgear_arm_spec as arm_spec
import pd_transgear_arm_plate_spec as plate_spec
import _transgear_arm_plate_locating_interface as pin
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm
from _test_stubbed_build import keyed_artefacts, offline_adapter, seat_calls, stub_seat


def _arm_part_seat(module, seat) -> None:
    seat._mass.side_effect = [
        (1.0, [0.0, 0.0, module.THICKNESS / 2.0]),
        (module.V_PIN + 1.0, [1.0, 0.0, 0.0]),
        (1.0, [0.0, 0.0, 0.0]),
    ]
    seat._open_end_face_sketch.return_value = (module.PIN_HOLE_Z, 0.0, True)
    seat.name_bore_axis.side_effect = [f"Axis{k}" for k in range(1, 9)]


def _plate_part_seat(module, seat) -> None:
    lowered = (
        module.V_PLATE * module.THICKNESS_OVER_ARM / 2.0
        - module.V_LOWER * module.NOTCH_DEPTH / 2.0
    ) / (module.V_PLATE + module.V_LOWER)
    seat._mass.side_effect = [
        (1.0, [0.0, 0.0, module.THICKNESS_OVER_ARM / 2.0]),
        (1.0, [0.0, 0.0, lowered]),
    ]
    seat.name_bore_axis.side_effect = [f"Axis{k}" for k in range(1, 9)]
    seat._sketch_mapper.side_effect = lambda _a, *, u_axis, v_axis, label: (
        lambda xyz: (xyz[u_axis], xyz[v_axis])
    )


def _drawing_seat(module, seat) -> None:
    seat.new_project_drawing.return_value = (MagicMock(), MagicMock())


@pytest.mark.parametrize(
    ("module_name", "export", "key", "prepare"),
    [
        ("build_pd_transgear_arm", "save_part_and_images", "part", _arm_part_seat),
        ("build_pd_transgear_arm_plate", "save_part_and_images", "part", _plate_part_seat),
        ("draw_pd_transgear_arm", "finalize_drawing", "drawing", _drawing_seat),
        ("draw_pd_transgear_arm_plate", "finalize_drawing", "drawing", _drawing_seat),
    ],
)
def test_saved_arm_files_are_audited_for_their_projected_gtols(
    monkeypatch: pytest.MonkeyPatch, module_name, export, key, prepare
) -> None:
    # Each arm part and drawing audits the file it SAVED, not the open model:
    # its own projected-zone controls, read from the path the export returns.
    module = importlib.import_module(module_name)
    if hasattr(module, "SOURCE"):
        monkeypatch.setattr(module, "SOURCE", Path(__file__))
    if hasattr(module, "hidden_sketches"):
        monkeypatch.setattr(module, "hidden_sketches", MagicMock())
    seat = stub_seat(monkeypatch, module)
    prepare(module, seat)
    getattr(seat, export).return_value = keyed_artefacts()
    adapter = offline_adapter()
    asyncio.run(module.build(adapter))
    calls = seat_calls(seat, export, "require_saved_projected_gtols")
    assert [name for name, _args, _kwargs in calls] == [export, "require_saved_projected_gtols"]
    _name, args, _kwargs = calls[1]
    assert args[0] is adapter
    assert args[1] == f"<{key}>"
    assert args[2] is module.GEOMETRIC_CONTROLS


def _readings() -> tuple[registration.RegistrationReading, ...]:
    return tuple(
        registration.RegistrationReading(name, force, moment, xy, normal)
        for name, force, moment, xy, normal in (
            ("pull", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-0.030, -0.026), (-0.003, 0.001, 0.002)),
            ("push", (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.030, 0.026), (0.003, -0.001, -0.002)),
            ("rock", (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.012, -0.020), (0.001, -0.002, 0.003)),
        )
    )


def _setup(across_mm: float, along_mm: float) -> tuple[float, float]:
    """A setup error with these components across and along S-K."""
    ux, uy = registration.S_TO_K_UNIT
    return (along_mm * ux - across_mm * uy, along_mm * uy + across_mm * ux)


_SETUP = _setup(0.018, 0.002)


def _receive(**changes) -> tuple[float, float]:
    inputs = dict(
        setup_error_xy_mm=_SETUP, readings=_readings(),
        required_load_cases=("pull", "push", "rock"), measurement_uncertainty_mm=0.001,
        own_datum_patterns_accepted=(True, True), free_hand_assembly=True,
    )
    inputs.update(changes)
    return registration.require_matched_registration(**inputs)


def test_locator_sites_share_real_part_frames_and_paid_mouth_walls() -> None:
    assert arm.LOCATOR_PAIR_BASELINE_MM == registration.LOCATOR_PAIR_BASELINE_MM
    assert math.dist(*arm.LOCATOR_SITES_MM) == pytest.approx(arm.LOCATOR_PAIR_BASELINE_MM)
    for arm_xy, plate_xy in zip(arm.LOCATOR_SITES_MM, plate.LOCATOR_SITES_MM, strict=True):
        assert plate_xy == pytest.approx((arm_xy[0] - plate.BORE_STATION, arm_xy[1] - plate.BORE_OFFSET))
    for geometry in (arm, plate):
        locator_walls = {name: wall for name, wall in geometry.WALLS.items() if name.startswith("locator")}
        assert len(locator_walls) >= 4
        assert all(worst >= geometry.WALL_TARGET for _nominal, worst in locator_walls.values())
    x, y = arm.LOCATOR_SITES_MM[0]
    # Full worst case: the outline's title-block edge break (either permitted
    # form) and the match drill's run-off through the thickest stock are paid.
    outline_break = max(
        edge_break_radius_mm(unit=arm.UNIT), edge_break_chamfer_mm(unit=arm.UNIT)
    )
    assert arm.OUTLINE_EDGE_BREAK_MAX_MM == outline_break
    expected = (arm.PIVOT_END_R - x * math.sin(arm.EDGE_LEAN) - abs(y) * math.cos(arm.EDGE_LEAN)
                - arm.OUTLINE_BAND - arm.LOCATOR_MOUTH_POSITION_RADIUS_MM - pin.PRESS_HOLE_LIMITS_MM[1] / 2.0
                - pin.HOLE_MOUTH_BREAK_RADIAL_MAX_MM - outline_break
                - (arm.THICKNESS + arm.THICKNESS_BAND) * math.tan(math.radians(0.3)))
    assert arm.WALLS["locator 1 to arm edge"][1] == pytest.approx(expected)
    assert "locator blind floor" not in arm.WALLS

def test_three_signed_normal_sites_pay_the_outside_gear_plane_height_lever() -> None:
    lever = (
        math.hypot(arm.KNOB_BORE_STATION - arm.PLATE_SCREW_MID_STATION, arm.KNOB_BORE_OFFSET)
        + registration.REDUCER_AXIS_SETUP_RADIUS_MM + registration.LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM
    )
    expected = registration.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM * (
        1.0 + 2.0 * lever / registration.ARM_SEAT_SPAN_MIN_MM
    )
    assert registration.gear_plane_k_loaded_normal_change_bound_mm() == pytest.approx(expected)
    assert expected > registration.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM




def test_three_accessible_rear_indicator_sites_bound_every_tilt_direction() -> None:
    points = registration.ARM_SEAT_NORMAL_WITNESS_XY_MM
    assert len(points) == 3
    twice_area = abs((points[1][0] - points[0][0]) * (points[2][1] - points[0][1])
                     - (points[1][1] - points[0][1]) * (points[2][0] - points[0][0]))
    nominal_width = twice_area / max(math.dist(points[i], points[j]) for i, j in ((0, 1), (1, 2), (2, 0)))
    assert nominal_width == pytest.approx(14.5)
    assert nominal_width - 2.0 * registration.ARM_SEAT_WITNESS_POSITION_RADIUS_MM >= registration.ARM_SEAT_SPAN_MIN_MM
    footprint = registration.ARM_SEAT_INDICATOR_TIP_DIA_MAX_MM / 2.0
    for x, y in points:
        edge = arm.PIVOT_END_R - x * math.sin(arm.EDGE_LEAN) - abs(y) * math.cos(arm.EDGE_LEAN)
        assert edge - arm.OUTLINE_BAND - footprint - registration.ARM_SEAT_WITNESS_POSITION_RADIUS_MM > 0.0
        px, py = x - plate.BORE_STATION, y - plate.BORE_OFFSET
        assert min(px - plate.EDGE_MINUS_X, plate.EDGE_PLUS_X - px,
                   (plate.arm_upper_edge_y(px) - py) * math.cos(arm.EDGE_LEAN),
                   (py - plate.notch_face_y(px)) * math.cos(arm.EDGE_LEAN)) - plate.BAND_X - footprint - 0.1 > 0.0
        for hx, hy in plate.SCREW_HOLES:
            assert math.hypot(px - hx, py - hy) > (plate.CSK_DIA + plate.CSK_DIA_BAND) / 2.0 + footprint + 0.15
        for hx, hy in plate.LOCATOR_SITES_MM:
            assert math.hypot(px - hx, py - hy) > pin.SLIP_HOLE_LIMITS_MM[1] / 2.0 + footprint + 0.15




def test_native_controls_reference_actual_bores_and_project_past_real_chain_plane() -> None:
    # The arm's pattern is located from S (Ø.0019, inside the 0.05 stack
    # zone); the plate's from its own knob bore K, so it carries K's Ø0.100
    # setting circle about S.
    for spec, geometry, prefix, zone in (
        (arm_spec, arm, "arm", ".0019"), (plate_spec, plate, "plate", "0.100"),
    ):
        controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
        for index, xy in enumerate(geometry.LOCATOR_SITES_MM, 1):
            control = controls[f"{prefix}_locator_{index}_position"]
            assert control.datums == ("A", "B", "C") and control.tolerance_zone == "diametral"
            assert control.tolerance == zone
            assert (control.face.contains_x_mm, control.face.contains_y_mm) == xy
            assert control.face.diameter_mm == geometry.LOCATOR_HOLE_DIA_MM
        assert {(feature, name) for feature, name in spec.BASIC_REDUCER_DIMENSIONS if feature == "LocatorProfile"} == {
            ("LocatorProfile", name) for name in ("LocatorX1", "LocatorY1", "LocatorX2", "LocatorY2")
        }
    arm_control = next(control for control in arm_spec.GEOMETRIC_CONTROLS if control.key == "feed_stud_projected_axis")
    plate_control = next(control for control in plate_spec.GEOMETRIC_CONTROLS if control.key == "knob_projected_axis")
    for control, datum_z, height, zone in (
        (arm_control, registration.ARM_FRONT_MACHINE_Z_MM, registration.S_PROJECTED_HEIGHT_MM, ".0019"),
        (plate_control, registration.PLATE_MOUNT_MACHINE_Z_MM, registration.K_PROJECTED_HEIGHT_MM, "0.050"),
    ):
        assert control.projected_zone_height_mm == height
        assert control.tolerance == zone and control.datums == ("A",)
        assert datum_z - height <= registration.CHAIN_PLANE_MACHINE_Z_LIMITS_MM[0]
        assert datum_z - height < registration.gear_plane_machine_z_mm() < datum_z


def test_clamp_axes_have_real_projected_zones_and_each_countersink_rides_its_hole() -> None:
    from _gtol_cylinder import CylinderFace
    arm_controls = {control.key: control for control in arm_spec.GEOMETRIC_CONTROLS}
    plate_controls = {control.key: control for control in plate_spec.GEOMETRIC_CONTROLS}
    # The cones are coaxial with their holes (the plan's 2X CSK callout): no frame of their own.
    assert not any("countersink" in key for key in plate_controls)
    for index, (x, y) in enumerate(plate.SCREW_HOLES, 1):
        tap = arm_controls[f"plate_tap_{index}_position"]
        hole = plate_controls[f"plate_hole_{index}_position"]
        assert tap.projected_zone_height_mm == arm.CLAMP_TAP_PROJECTED_HEIGHT_MM
        assert hole.projected_zone_height_mm == plate.CLAMP_PLATE_PROJECTED_HEIGHT_MM
        assert isinstance(hole.face, CylinderFace)
        assert (hole.face.contains_x_mm, hole.face.contains_y_mm) == (x, y)
        for control, zone in ((tap, ".0019"), (hole, "0.100")):
            assert control.datums == ("A", "B", "C")
            assert control.tolerance == zone and control.tolerance_zone == "diametral"


def test_measured_receiver_pays_full_two_pose_travel_and_uncertainty() -> None:
    widths = _receive()
    assert widths == pytest.approx((0.062, 0.054))
    assert math.hypot(*widths) <= registration.LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM
    assert registration.LOCATOR_GEAR_PLANE_TRAVEL_MAX_MM == 0.100
    assert registration.REDUCER_AXIS_SETUP_RADIUS_MM == 0.050
    assert registration.LOCATOR_COORDINATE_TRAVEL_MAX_MM <= 0.100 / math.sqrt(2.0)


def test_setup_must_hold_the_drawn_centre_distance_band_along_s_k() -> None:
    import pd_rack_pinion_spec as disc
    high, low = disc.CENTRE_DISTANCE_SET_BAND
    # +x/-0: never closer than nominal; the top is K's setting circle radius.
    assert (high, low) == (registration.REDUCER_AXIS_SETUP_RADIUS_MM, 0.0)
    uncertainty = 0.001
    s_to_k = (arm.KNOB_BORE_STATION - arm.PIN_STATION, arm.KNOB_BORE_OFFSET)
    assert math.hypot(*s_to_k) == pytest.approx(disc.CENTRE_DISTANCE)
    # Exactly on the low limit with the uncertainty paid inward: accepted,
    # though the reading is rebuilt through S_TO_K_UNIT.
    _receive(setup_error_xy_mm=_setup(0.0, low + uncertainty))
    # Closer than nominal, inside the position circle: refused.
    for along in (low, low - 0.002):
        with pytest.raises(ValueError, match="centre distance"):
            _receive(setup_error_xy_mm=_setup(0.0, along))
    # The top of the band is the position circle's own limit.
    with pytest.raises(ValueError, match="position circle"):
        _receive(setup_error_xy_mm=_setup(0.0, high))
    # The same error across S-K is only a clocking error: accepted.
    _receive(setup_error_xy_mm=_setup(high / 2.0, 0.002))


def test_loaded_envelope_is_anchored_to_the_setup_reading() -> None:
    accepted = _receive()
    # Every loaded reading slips the same way: the travel from setup counts.
    slip = 1.0
    slipped = tuple(
        replace(row, gear_plane_k_xy_mm=(row.gear_plane_k_xy_mm[0] + slip, row.gear_plane_k_xy_mm[1]))
        for row in _readings()
    )
    with pytest.raises(ValueError, match="two-pose envelope"):
        _receive(readings=slipped)
    # A setup reading inside the loaded spread changes nothing.
    assert _receive(setup_error_xy_mm=_setup(0.0, 0.002)) == pytest.approx(accepted)


def test_actual_joint_receiver_requires_critical_setting_and_every_signed_loaded_site() -> None:
    import transgear_hanger_joints as joints
    inputs = dict(
        setup_error_xy_mm=_SETUP, registration_readings=_readings(),
        required_load_cases=("pull", "push", "rock"), measurement_uncertainty_mm=0.001,
        own_datum_patterns_accepted=(True, True), free_hand_assembly=True,
    )
    assert joints.require_arm_plate_joint_inspection(**inputs) == pytest.approx((0.062, 0.054))
    for changes in (
        {"own_datum_patterns_accepted": (True, False)},
        {"own_datum_patterns_accepted": (1, 1)},
        {"free_hand_assembly": False},
        {"registration_readings": (replace(_readings()[0], seat_normal_changes_mm=(0.0, 0.0)), *_readings()[1:])},
    ):
        with pytest.raises(ValueError):
            joints.require_arm_plate_joint_inspection(**(inputs | changes))


def test_receiver_charges_full_delta_uncertainty_without_unneeded_one_micron_instrument_grade() -> None:
    """Synthetic readings only: two .002 instrument errors cost .004."""
    readings = tuple(replace(row, seat_normal_changes_mm=(0.0, 0.0, 0.0)) for row in _readings())
    # A .004 uncertainty is paid inward of the +x/-0 band, so the setup
    # reading must stand at least .004 above nominal.
    widths = _receive(
        setup_error_xy_mm=_setup(0.0, 0.004), readings=readings,
        measurement_uncertainty_mm=0.004,
    )
    assert widths == pytest.approx((0.068, 0.060))
    assert registration.ARM_SEAT_NORMAL_UNCERTAINTY_MAX_MM == registration.ARM_PLATE_LOADED_NORMAL_CHANGE_MAX_MM
    with pytest.raises(ValueError, match="observation is invalid or exceeds the grade"):
        _receive(
            setup_error_xy_mm=_setup(0.0, 0.004), measurement_uncertainty_mm=0.004,
            readings=tuple(replace(row, seat_normal_changes_mm=(0.0011, 0.0, 0.0)) for row in _readings()),
        )


@pytest.mark.parametrize("changes", [
    {"setup_error_xy_mm": (0.024, 0.024)}, {"setup_error_xy_mm": (0.025, 0.0)},
    {"own_datum_patterns_accepted": (True, False)}, {"free_hand_assembly": False},
    {"required_load_cases": ("pull", "push")}, {"required_load_cases": ("pull", "push", "rock", "missing")},
    {"required_load_cases": ()}, {"measurement_uncertainty_mm": 0.0},
    {"measurement_uncertainty_mm": math.nan},
    {"measurement_uncertainty_mm": registration.ARM_SEAT_NORMAL_UNCERTAINTY_MAX_MM + 0.0001},
])
def test_receiver_refuses_incomplete_inspection(changes) -> None:
    with pytest.raises(ValueError):
        _receive(**changes)


@pytest.mark.parametrize("replacement", [
    {"seat_normal_changes_mm": (0.0041, 0.0, 0.0)}, {"seat_normal_changes_mm": (-0.0041, 0.0, 0.0)},
    {"seat_normal_changes_mm": (0.0, 0.0)}, {"applied_force_n": (math.nan, 0.0, 0.0)},
    {"applied_moment_nmm": (0.0, 0.0)}, {"gear_plane_k_xy_mm": (-0.045, -0.026)},
])
def test_receiver_refuses_missing_signed_normal_values_or_excess_real_motion(replacement) -> None:
    readings = _readings()
    with pytest.raises(ValueError):
        _receive(readings=(replace(readings[0], **replacement), *readings[1:]))


@pytest.mark.parametrize("native_shift", (0.0, 0.04))
def test_native_registration_reads_real_socket_intersections_not_nominal_proxy(
    monkeypatch: pytest.MonkeyPatch, native_shift: float,
) -> None:
    import build_pd_paper_drive_assembly as assembly
    import _gtol_face_read
    import _gtol_face_resolve

    models = {
        "arm": SimpleNamespace(name="arm", geometry=arm, seat_z=arm.THICKNESS),
        "plate": SimpleNamespace(name="plate", geometry=plate, seat_z=0.0),
    }

    class Component:
        def __init__(self, model):
            self.model = model

        def GetModelDoc2(self):
            return self.model

    class Assembly:
        def GetComponentByName(self, name):
            return Component(models[name])

    def resolve(model, requests):
        values = {}
        for label in requests:
            if label == "actual mounting seat":
                parameters = (0.0, 0.0, 1.0, 0.0, 0.0, model.seat_z / 1000.0)
            else:
                index = int(label.split()[2]) - 1
                x, y = model.geometry.LOCATOR_SITES_MM[index]
                x += native_shift if model.name == "plate" else 0.0
                parameters = (x / 1000.0, y / 1000.0, 0.0, 0.0, 0.0, 1.0,
                              model.geometry.LOCATOR_HOLE_DIA_MM / 2000.0)
            values[label] = SimpleNamespace(parameters=parameters)
        return values

    def world_point(_adapter, name, local_mm):
        origin = (0.0, 0.0, 0.0) if name == "arm" else (
            plate.BORE_STATION, plate.BORE_OFFSET, arm.THICKNESS,
        )
        return [local_mm[axis] + origin[axis] for axis in range(3)]

    monkeypatch.setattr(assembly, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_gtol_face_resolve, "resolve_faces", resolve)
    monkeypatch.setattr(_gtol_face_read, "face_geometry", lambda face: face)
    monkeypatch.setattr(assembly, "world_point", world_point)
    adapter = SimpleNamespace(currentModel=Assembly())
    if native_shift:
        with pytest.raises(RuntimeError, match="seat intersection is off source"):
            assembly._assert_arm_plate_registered(adapter, "arm", "plate")
    else:
        assembly._assert_arm_plate_registered(adapter, "arm", "plate")


@pytest.mark.parametrize("parameters", (None, (0.0,) * 6, (math.nan,) * 7))
def test_rear_socket_rim_refuses_null_or_invalid_native_variant(
    monkeypatch: pytest.MonkeyPatch, parameters,
) -> None:
    import draw_pd_transgear_arm as drawing

    class Curve:
        CircleParams = parameters  # declared native property, not a method

        def IsCircle(self):
            return True

    class Edge:
        def GetCurve(self):
            return Curve()

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "visible_view_entities", lambda *args, **kwargs: (Edge(),))
    with pytest.raises(RuntimeError, match="native circle parameters"):
        drawing._rear_rim(None, radius_mm=1.0, station_mm=0.0, offset_mm=0.0, label="locator")


def test_construction_property_put_has_no_boolean_return_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    import build_pd_transgear_arm as builder

    class Segment:
        def __init__(self):
            self.value = False

        @property
        def ConstructionGeometry(self):
            return self.value

        @ConstructionGeometry.setter
        def ConstructionGeometry(self, value):
            self.value = value
            # Native property PUT returns VOID/None. Readback owns success.

    segment = Segment()
    monkeypatch.setattr(builder, "_early_bound", lambda value, _interface: value)
    builder._as_construction(SimpleNamespace(_sketch_entities={"line": segment}), "line")
    assert segment.ConstructionGeometry is True
