"""Offline contracts; these do not replace the final source-SHA native receipt."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import _config
import build_pd_transgear_knob_shaft as part
import draw_pd_transgear_knob_shaft as drawing
import pd_transgear_arm_plate_geometry as plate
import pd_transgear_knob_shaft_spec as spec
import pd_transgear_knob_thrust_ring_spec as ring
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_notes import property_link
from paper_drive_stock_inspection import span_contact_points_mm, toothspace_gauge_contact_mm
from stock_form_cutter import CutterTemplate, StockFormProfile, translation_for_tangent_span
from _test_stubbed_build import offline_adapter, stub_seat


F_MACHINE_Z = -148.1


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.name == "pd-transgear-knob-shaft.SLDDRW"
    assert drawing.PDF.name == "pd-transgear-knob-shaft.pdf"
    assert drawing.PNG.name == "pd-transgear-knob-shaft_drawing.png"
    assert DRAWINGS_BY_NAME["pd_transgear_knob_shaft"].script == Path(drawing.__file__).resolve()


def test_native_stock_source_is_the_selected_12t_48dp_master() -> None:
    import pd_rack_pinion_spec as disc

    profile = spec.STOCK_PROFILE
    assert spec.TEETH == profile.teeth == disc.MESH_PINION_TEETH == 12
    assert spec.DIAMETRAL_PITCH == disc.DIAMETRAL_PITCH == 48
    assert profile.template == spec.CUTTER_TEMPLATE == CutterTemplate(12, 48, 20)
    assert profile.template.cutter_number == 8
    assert profile.template.reference_teeth == 12
    assert profile.radial_translation_mm == spec.RADIAL_SETTING
    assert profile.blank_radius_mm == spec.OUTSIDE_DIA / 2
    assert spec.OUTSIDE_DIA == 7.40
    assert spec.OUTSIDE_DIA_BAND == (0.0, -0.02)
    assert spec.CUTTER_DIA == 44.45
    assert spec.CUTTER_ARBOR_BORE == 22.225
    assert spec.CUTTER_SKU == "10-289-488"
    assert part.STOCK_PROFILE is profile
    assert "PROFILE SHIFT" not in spec.GEAR_DATA
    lower, upper = sorted(spec.SPAN_LIMITS)
    assert spec.GEAR_DATA.splitlines()[1:] == [
        "NUMBER OF TEETH:  12",
        "DIAMETRAL PITCH:  48.00",
        "PRESSURE ANGLE:  20.0 DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"WHOLE DEPTH (mm, REF):  {spec.WHOLE_DEPTH:.3f}",
        "CUTTER:  #8, 12-13T",
        f"SPAN OVER 2 TEETH:  {lower:.4f}-{upper:.4f}",
        "MATES WITH:  DISC MHA-PD-06, 120T",
    ]


def test_span_is_actual_finite_contact_and_printed_limits_are_inverted() -> None:
    assert spec.SPAN_TEETH == 2
    assert spec.SPAN_PLACES == 4
    assert spec.SPAN_NOMINAL == pytest.approx(spec.STOCK_PROFILE.tangent_span_mm(2))
    assert spec.SPAN_DEVIATIONS == pytest.approx(
        (spec.SPAN_LIMITS[0] - spec.SPAN_NOMINAL, spec.SPAN_LIMITS[1] - spec.SPAN_NOMINAL)
    )
    for setting, tip in ((p.radial_translation_mm, p.blank_radius_mm) for p in spec.manufactured_profiles()):
        profile = StockFormProfile(12, spec.CUTTER_TEMPLATE, tip, setting)
        assert spec.RADIAL_SETTING_LIMITS[0] <= setting <= spec.RADIAL_SETTING_LIMITS[1]
        actual = profile.tangent_span_mm(2)
        error = 2 * profile.geometry_error_bound_mm
        assert spec.SPAN_LIMITS[0] - error <= actual <= spec.SPAN_LIMITS[1] + error
        a, b = span_contact_points_mm(profile, 2)
        assert math.dist(a, b) == pytest.approx(actual, abs=1e-10)
    assert spec.SPAN_PREFIX == "CONTROL SPAN 2 TEETH "
    assert "BISECTOR" not in spec.DRAWING_NOTES  # method, not requirement
    # Rounded limits, not the old provisional setting band, define acceptance.
    lo, hi = spec.RADIAL_SETTING_LIMITS
    assert lo < spec.RADIAL_SETTING < hi
    outside = hi + 0.001
    rejected_span = StockFormProfile(12, spec.CUTTER_TEMPLATE, 3.69, outside).tangent_span_mm(2)
    assert rejected_span > spec.SPAN_LIMITS[1]
    with pytest.raises(ValueError):
        translation_for_tangent_span(
            12, spec.CUTTER_TEMPLATE, rejected_span, 2,
            translation_bounds_mm=spec.RADIAL_SETTING_LIMITS,
        )


def test_all_accepted_corners_keep_genuine_finite_ground_tip_in_air() -> None:
    for profile in spec.manufactured_profiles():
        tip = profile.flank_point(profile.template.flank_parameter_max)
        assert math.hypot(*tip) - profile.blank_radius_mm > profile.geometry_error_bound_mm
        assert 2 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
        assert profile.root_point(profile.root_half_angle_rad)[0] >= spec.ROOT_DEPTH_X_MIN
    with pytest.raises(ValueError):
        replace(spec.STOCK_PROFILE, blank_radius_mm=spec.CUTTER_TEMPLATE.tip_radius_mm + 0.02)


def test_front_core_and_actual_rear_terminal_window() -> None:
    assert spec.FRONT_CORE_AIR_MIN > 0.0
    assert spec.FULL_DEPTH_MIN >= spec.DISC_REAR_FROM_F_WORST
    assert spec.CUTTER_RUNOUT_END_WORST < spec.CUTTER_RUNOUT_MAX < spec.HUB_BORE_FROM_F_WORST
    assert spec.PINION_REAR_Z < spec.CUTTER_RUNOUT_END_Z < spec.HUB_BORE_FROM_F_WORST
    assert spec.CUTTER_AXIS_R == pytest.approx(
        spec.CUTTER_DIA / 2 + spec.STOCK_PROFILE.root_point(spec.STOCK_PROFILE.root_half_angle_rad)[0]
    )
    assert spec.CUTTER_AXIS_R != pytest.approx(spec.CUTTER_DIA / 2 + spec.ROOT_DIA / 2)
    # Negative controls: a larger catalogue disk and an enlarged core are not equivalent.
    assert spec.FULL_DEPTH_MAX + spec.cutter_runout(2.75 * 25.4, spec.RUNOUT_RISE_WORST) > spec.CUTTER_RUNOUT_MAX
    assert spec.ROOT_DIA_EXACT_MIN - 5.1 - spec.CORE_TOTAL_RUNOUT - spec.TOOTH_SPACE_RUNOUT_TIR_MM < 0.0


def test_real_d_core_thread_and_six_mm_g6_source() -> None:
    assert spec.CORE_DIA == 4.85 and spec.CORE_DIA_BAND == (0.0, -0.008)
    assert spec.CORE_FLAT_FROM_AXIS == 2.125 and spec.CORE_FLAT_BAND == (0.0, -0.015)
    assert spec.JOURNAL_DIA == 6.0 and spec.JOURNAL_DIA_BAND == (-0.004, -0.012)
    assert spec.THREAD == "#8-32" and spec.THREAD_CALLOUT == "#8-32 UNC"
    assert spec.RELIEF_DIA_MAX < spec.THREAD_ROOT_2A_MIN
    assert spec.TIP_CHAMFER_MAX < spec.THREAD_PITCH
    assert spec.THREAD_MAJOR_2A[0] <= spec.THREAD_BLANK_LIMITS[0]
    assert spec.THREAD_BLANK_LIMITS[1] <= spec.THREAD_MAJOR_2A[1]
    assert ring.LENGTH == 5.2


def test_machine_and_float_stations_are_unchanged() -> None:
    for local, machine in (
        (spec.TIP_Z, -172.0), (spec.THREAD_END_Z, -155.6),
        (spec.PINION_REAR_Z, -142.2), (spec.REAR_END_Z, -101.26),
    ):
        assert F_MACHINE_Z + local == pytest.approx(machine, abs=0.005)
    assert spec.CUP_FACE_STATION == pytest.approx(ring.LENGTH + plate.HUB_TO_BOSS + spec.END_FLOAT)
    assert spec.END_FLOAT > spec.END_FLOAT_SET_TOL
    assert spec.JOURNAL_LENGTH == pytest.approx(spec.CUP_FACE_STATION + spec.JOURNAL_REAR_EXTENSION)
    assert spec.OVERALL_LENGTH == pytest.approx(70.74, abs=0.005)


def test_d_flat_uses_signed_physical_round_tool_end_and_real_neck() -> None:
    assert spec.FRONT_RELIEF_DIA == 3.95
    assert spec.FRONT_RELIEF_WIDTH == 0.4
    assert spec.FRONT_CORNER_RADIUS == 0.05
    assert spec.FRONT_CORNER_RADIUS_MAX == 0.1
    assert spec.CORE_ACTIVE_LENGTH == pytest.approx(4.85)
    assert -spec.CORE_FLAT_CUT_END_Z == pytest.approx(0.110)
    upper, lower = spec.CORE_FLAT_CUT_END_BAND
    assert -spec.CORE_FLAT_CUT_END_Z + lower == pytest.approx(0.050)
    assert -spec.CORE_FLAT_CUT_END_Z + upper == pytest.approx(0.170)
    assert spec.FRONT_RELIEF_WIDTH_MIN - 0.170 >= 0.100 - 1e-12
    # .XXX general ±.130 on the terminal could overrun F; not equivalent.
    assert 0.110 - 0.130 < 0.0
    # The old 4.050 neck misses the adopted full-relative-axis D-plane charge.
    flat_min = spec.CORE_FLAT_FROM_AXIS + min(spec.CORE_FLAT_BAND)
    assert flat_min - ((4.050 + 0.130) / 2 + 0.050) < 0.0
    assert flat_min - ((spec.FRONT_RELIEF_DIA + 0.130) / 2 + 0.050) > 0.0


def test_neck_corner_radius_band_runs_from_sharp_to_the_maximum() -> None:
    assert spec.FRONT_CORNER_RADIUS_TOL_TYPE == 3
    hi, lo = spec.FRONT_CORNER_RADIUS_BAND
    assert spec.FRONT_CORNER_RADIUS + lo == 0.0
    assert spec.FRONT_CORNER_RADIUS + hi == pytest.approx(0.1)


def test_complete_nominal_native_volume_uses_bounded_rear_disk_and_true_d() -> None:
    end_lo, end_hi = spec.endcut_volume_bounds_mm3(absolute_error_mm3=0.05 / spec.TEETH)
    assert 0.0 < end_lo <= end_hi
    lower, upper = spec.expected_volume_bounds_mm3()
    r = spec.CORE_DIA / 2
    h = spec.CORE_FLAT_FROM_AXIS
    flat_removed = (r*r*math.acos(h/r) - h*math.sqrt(r*r-h*h)) * spec.CORE_ACTIVE_LENGTH
    straight = spec.TEETH * spec.STOCK_PROFILE.gap_area_mm2 * spec.FULL_DEPTH
    before_end = (
        math.pi * spec.STOCK_PROFILE.blank_radius_mm**2 * spec.FACE_WIDTH
        + part.V_STUD + part.V_JOURNAL - flat_removed - straight
    )
    assert lower <= before_end - spec.TEETH * (end_lo + end_hi) / 2 <= upper
    assert upper - lower <= 0.051
    assert before_end > upper  # omitting the true terminal cannot meet the oracle
    with pytest.raises(ValueError):
        spec.endcut_volume_bounds_mm3(full_depth_mm=spec.FACE_WIDTH + 0.1)
    with pytest.raises(ValueError):
        spec.endcut_volume_bounds_mm3(profile=replace(spec.STOCK_PROFILE, teeth=13))


def test_every_native_dimension_is_placed_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.SIDE_KEEP, drawing.END_KEEP, drawing.DETAIL_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set().union(*keeps) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_DIMENSIONS["CoreFlatProfile"] == {"FlatToAxis"}
    assert spec.DRAWING_DIMENSIONS["SpanProfile"] == {"ToothSpan"}
    assert spec.DRAWING_DIMENSIONS["RootInspectionProfile"] == {"RootEnvelope"}
    assert {"FullDepth", "CutterRunout"} <= spec.DRAWING_DIMENSIONS["StudProfile"]
    assert "RootEnvelope" in drawing.END_KEEP and "ToothSpan" in drawing.END_KEEP
    assert "FlatToAxis" in drawing.SIDE_KEEP
    assert set(drawing.DETAIL_KEEP) == {
        "FrontReliefDia", "FrontReliefWidth", "FrontCornerRadius",
    }


def test_tool_end_limits_print_once_in_the_notes_from_the_spec() -> None:
    # The D-flat tool's end lies in air under the neck: no edge carries a
    # dimension, so note 4 is the one printed owner of both limits.
    lo, hi = spec.CORE_FLAT_CUT_END_LIMITS
    note = spec.CORE_FLAT_TOOL_REACH_NOTE
    assert f"TOOL END {lo:.2f}-{hi:.2f} FROM 12T FRONT FACE" in note
    assert f"R{spec.CORE_FLAT_TOOL_END_RADIUS_MAX:.3f} MAX" in note
    assert "\n" not in note
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not {"FlatEnd", "FlatToolRadius"} & marked
    printed = "\n".join((spec.DRAWING_NOTES, note))
    assert len(printed.splitlines()) <= 4


def test_the_tool_end_keeps_its_native_limits_but_no_sheet_text(monkeypatch) -> None:
    # Both limits stay authored on the model's FlatEnd/FlatToolRadius (the
    # fit-band contract reads them); the sheet text is note 4's alone.
    limits: list[tuple[str, str]] = []
    prefixes: list[str] = []
    monkeypatch.setattr(
        part, "_apply_native_limits",
        lambda _adapter, feature, name, *_args: limits.append((feature, name)),
    )
    monkeypatch.setattr(
        part, "set_dimension_prefix", lambda _adapter, _feature, name, _text: prefixes.append(name)
    )
    part._apply_neck_and_flat_limits(object())
    assert ("CoreFlatProfile", "FlatEnd") in limits
    assert ("CoreFlatProfile", "FlatToolRadius") in limits
    assert prefixes == []


def test_model_bands_and_source_linked_properties() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands[("StudProfile", "CoreDia")] == "*deviations(CORE_DIA_BAND)"
    assert bands[("JournalProfile", "JournalDia")] == "*deviations(JOURNAL_DIA_BAND)"
    assert bands[("CoreFlatProfile", "FlatToAxis")] == "*deviations(CORE_FLAT_BAND)"
    assert bands[("StudProfile", "OutsideDia")] == "*deviations(OUTSIDE_DIA_BAND)"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(source, filename=drawing.__file__)
    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    assert set(drawing.CONTROL_ATTACHMENTS) == set(controls)
    assert drawing.CONTROL_ATTACHMENTS["core_total_runout"][0] != drawing.CONTROL_ATTACHMENTS["front_neck_total_runout"][0]
    for key, control in controls.items():
        assert control.datums == ("A",)
        assert float(control.tolerance) == spec.CORE_TOTAL_RUNOUT
    assert f"Ø{spec.ROOT_DIA_MIN:.2f} MIN" in spec.ROOT_ACCEPTANCE


def test_supported_certified_pin_inspects_all_actual_finite_corners() -> None:
    pin_diameter = spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM
    assert pin_diameter == 1.0
    contacts = spec.tooth_space_gauge_contacts(pin_diameter)
    profiles = spec.manufactured_profiles()
    assert len(contacts) == len(profiles) == 4
    for profile, contact in zip(profiles, contacts, strict=True):
        assert profile.flank_parameter_min < contact.parameter < profile.flank_parameter_max
        assert contact.root_air_mm > 0.0 and contact.tip_air_mm > 0.0
        assert contact.center_radius_error_bound_mm > 0.0
        assert math.dist(contact.flank_point_mm, (contact.center_radius_mm, 0.0)) == pytest.approx(pin_diameter / 2)
    assert min(c.root_air_mm for c in contacts) == spec.TOOTH_SPACE_GAUGE_ROOT_AIR_MIN_MM
    assert min(c.tip_air_mm for c in contacts) == spec.TOOTH_SPACE_GAUGE_TIP_AIR_MIN_MM


def test_indicator_grade_has_one_live_source_and_span_does_not_certify_eccentricity() -> None:
    from _gear_quality import toothspace_runout_tir_mm

    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM == toothspace_runout_tir_mm() == 0.05
    assert spec.TOOTH_SPACE_CALLOUT.splitlines()[0] == "TOOTH SPACE RUNOUT 0.05 TIR TO A"
    assert spec.TOOTH_SPACE_CALLOUT_PROPERTY == "Tooth Space Inspection"
    assert all(word not in spec.TOOTH_SPACE_CALLOUT for word in ("CANDIDATE", "TODO", "GATE"))
    contact = toothspace_gauge_contact_mm(spec.STOCK_PROFILE, spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    eccentricity = 0.04
    a, b = span_contact_points_mm(spec.STOCK_PROFILE, spec.SPAN_TEETH)
    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM > 0.0
    moved = tuple((x + eccentricity, y) for x, y in (a, b))
    assert math.dist(*moved) == pytest.approx(math.dist(a, b))
    indication = (contact.center_radius_mm + eccentricity) - (contact.center_radius_mm - eccentricity)
    assert indication == pytest.approx(2 * eccentricity)
    assert indication > spec.TOOTH_SPACE_RUNOUT_TIR_MM


@pytest.mark.parametrize("pin_diameter", [0.001, 10.0, 0.0, math.nan])
def test_wrong_inspection_pin_cannot_certify_an_unsupported_contact(pin_diameter: float) -> None:
    with pytest.raises(ValueError):
        toothspace_gauge_contact_mm(spec.STOCK_PROFILE, pin_diameter)


def test_shared_callout_takes_the_one_formed_edge_through_the_contact() -> None:
    import paper_drive_stock_drawing as ink

    contact = (2.5, 1.5, 0.0)
    flank = ink.EdgeReading("flank", (2.5, 1.505, 0.0), False)
    neighbour = ink.EdgeReading("next flank", (2.5, 1.52, 0.0), False)
    root_line = ink.EdgeReading("root line", contact, True)
    far_face = ink.EdgeReading("far face flank", (2.5, 1.5, 5.9), False)
    assert ink.flank_at_contact([neighbour, root_line, flank, far_face], contact) is flank
    # Run 11: the knob's hit test took a line or circle; the feed's took the
    # far face's partial-depth flank 0.23 mm off; the rack's a neighbour.
    with pytest.raises(RuntimeError, match=r"matched 0 of 3 drawn edges; nearest: line/circle 0\.0000"):
        ink.flank_at_contact([root_line, neighbour, far_face], contact)
    twin = ink.EdgeReading("twin", (2.5, 1.495, 0.0), False)
    with pytest.raises(RuntimeError, match="matched 2 of 2"):
        ink.flank_at_contact([flank, twin], contact)
    with pytest.raises(RuntimeError, match="matched 0 of 0 drawn edges; nearest: none"):
        ink.flank_at_contact([], contact)


class _DrawnEdge:
    """A view edge as COM answers it: closest point (m) and curve kind."""

    def __init__(self, closest_mm, *, straight: bool = False) -> None:
        self.closest_m = tuple(value / 1000.0 for value in closest_mm)
        self.curve = SimpleNamespace(IsLine=lambda: straight, IsCircle=lambda: False)

    def GetClosestPointOn(self, *_point):
        return self.closest_m

    def GetCurve(self):
        return self.curve


_LANDING = (0.120, 0.080)


def _callout_seat(monkeypatch: pytest.MonkeyPatch, *, landed=_LANDING, attached=(1,)):
    """Run the shared callout on a recording sheet; return its parts and the contact (mm)."""
    import paper_drive_stock_drawing as ink

    kwargs = dict(
        profile=spec.STOCK_PROFILE,
        actual_pin_diameter_mm=spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM,
        rotate_rad=0.3,
        axial_station_mm=spec.FACE_WIDTH,
        property_name=spec.TOOTH_SPACE_CALLOUT_PROPERTY,
        note_xy=(0.150, 0.100),
    )
    contact = toothspace_gauge_contact_mm(spec.STOCK_PROFILE, kwargs["actual_pin_diameter_mm"])
    x, y = ink._rotate(contact.flank_point_mm, kwargs["rotate_rad"])
    edges = {
        "neighbour": _DrawnEdge((x + 0.2, y, spec.FACE_WIDTH)),
        "root line": _DrawnEdge((x, y, spec.FACE_WIDTH), straight=True),
        "flank": _DrawnEdge((x, y + 0.004, spec.FACE_WIDTH)),
        "far face": _DrawnEdge((x, y, 0.0)),
    }
    seat = MagicMock()
    draw = seat.adapter.currentModel
    draw.SelectionManager.SetSelectionPoint2.return_value = True
    annotation = draw.InsertNote.return_value.GetAnnotation.return_value
    annotation.SetLeader3.return_value = 0
    annotation.SetPosition2.return_value = True
    annotation.GetAttachedEntityCount3.return_value = len(attached)
    annotation.GetAttachedEntityTypes.return_value = attached
    annotation.GetLeaderCount.return_value = 1
    annotation.IsDangling.return_value = False
    annotation.GetLeaderPointsAtIndex.return_value = (0.15, 0.10, 0.0, *landed, 0.0)
    monkeypatch.setattr(ink, "visible_view_entities", lambda _view, _kind, label: list(edges.values()))
    monkeypatch.setattr(
        ink, "_com_invoke", lambda obj, _interface, method, *args: getattr(obj, method)(*args)
    )
    monkeypatch.setattr(ink, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(ink, "model_point_in_view", seat.model_point_in_view)
    seat.model_point_in_view.return_value = _LANDING
    monkeypatch.setattr(ink, "_select_view_entity", seat._select_view_entity)
    monkeypatch.setattr(ink, "rebuild_drawing", seat.rebuild_drawing)
    return ink, seat, edges, kwargs, (x, y)


def test_shared_callout_attaches_one_leader_to_the_flank_at_the_gauge_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ink, seat, edges, kwargs, (x, y) = _callout_seat(monkeypatch)
    view = object()
    note = ink.add_toothspace_callout(seat.adapter, view, **kwargs)

    draw = seat.adapter.currentModel
    assert note is draw.InsertNote.return_value
    # The contact is projected at the inspected end face, in metres.
    projected = seat.model_point_in_view.call_args
    assert projected.args[1] is view
    assert projected.args[2] == pytest.approx((x / 1e3, y / 1e3, spec.FACE_WIDTH / 1e3))
    # The formed flank through it is selected by entity, the landing is that
    # selection's point, and the note linked to the part's control rides it.
    selected = seat._select_view_entity.call_args
    assert selected.args[1:3] == (view, "EDGE") and selected.kwargs["entity"] is edges["flank"]
    names = [name for name, _args, _kwargs in seat.mock_calls]
    order = [
        names.index("_select_view_entity"),
        names.index("adapter.currentModel.SelectionManager.SetSelectionPoint2"),
        names.index("adapter.currentModel.InsertNote"),
        names.index("rebuild_drawing"),
        names.index("adapter.currentModel.ClearSelection2"),
    ]
    assert order == sorted(order)
    draw.SelectionManager.SetSelectionPoint2.assert_called_once_with(1, -1, *_LANDING, 0.0)
    draw.InsertNote.assert_called_once_with(property_link(spec.TOOTH_SPACE_CALLOUT_PROPERTY))
    annotation = note.GetAnnotation.return_value
    annotation.SetPosition2.assert_called_once_with(*kwargs["note_xy"], 0.0)


@pytest.mark.parametrize(
    ("readback", "message"),
    [
        ({"landed": (_LANDING[0] + 0.002, _LANDING[1])}, "leader attachment moved"),
        ({"attached": (1, 1)}, "exactly one EDGE attachment"),
        ({"attached": (2,)}, "exactly one EDGE attachment"),
    ],
)
def test_shared_callout_fails_on_a_wrong_attachment_or_a_moved_landing(
    monkeypatch: pytest.MonkeyPatch, readback: dict, message: str
) -> None:
    ink, seat, _edges, kwargs, _contact = _callout_seat(monkeypatch, **readback)
    with pytest.raises(RuntimeError, match=message):
        ink.add_toothspace_callout(seat.adapter, object(), **kwargs)


def test_shared_callout_refuses_a_landing_the_sheet_did_not_take(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ink, seat, _edges, kwargs, _contact = _callout_seat(monkeypatch)
    seat.adapter.currentModel.SelectionManager.SetSelectionPoint2.return_value = False
    with pytest.raises(RuntimeError, match="failed to set the flank landing"):
        ink.add_toothspace_callout(seat.adapter, object(), **kwargs)
    seat.adapter.currentModel.InsertNote.assert_not_called()


@pytest.mark.parametrize(
    ("spec_module", "pin_name"),
    [
        ("pd_rack_pinion_spec", "TOOTH_SPACE_GAUGE_PIN_DIA_MM"),
        ("pd_transgear_feed_pinion_spec", "TOOTHSPACE_GAUGE_DIA_MM"),
        ("pd_transgear_knob_shaft_spec", "TOOTH_SPACE_GAUGE_PIN_DIA_MM"),
    ],
)
def test_flank_ends_lie_far_outside_the_contact_tolerance(spec_module: str, pin_name: str) -> None:
    """Root-fillet and tip edges meet the flank only at its ends; each end
    must sit over 20x the contact tolerance from the gauge contact."""
    import importlib

    import paper_drive_stock_drawing as ink

    owner = importlib.import_module(spec_module)
    profile = owner.STOCK_PROFILE
    contact = toothspace_gauge_contact_mm(profile, getattr(owner, pin_name))
    for parameter in (profile.flank_parameter_min, profile.flank_parameter_max):
        end = profile.flank_point(parameter)
        assert math.dist(contact.flank_point_mm, end) > 20.0 * ink.CONTACT_TOLERANCE_MM


def test_the_ink_module_never_hit_tests_the_sheet() -> None:
    # Main precedent: test_dt_pinion_arbor_drawing ('"SelectByID2" not in helper').
    import paper_drive_stock_drawing as ink

    assert "SelectByID2" not in inspect.getsource(ink)


def test_single_native_solid_volume_has_no_adapter_fallback(monkeypatch) -> None:
    import paper_drive_stock_native as native

    class Body:
        def GetType(self):
            return 0

        def GetMassProperties(self, density):
            assert density == 1.0
            return (0.0, 0.0, 0.0, 1.25e-9, 0.0, 1.25e-9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    class NativePart:
        def __init__(self, bodies):
            self.bodies = bodies

        def GetBodies2(self, kind, visible_only):
            assert kind == 0 and visible_only is False
            return self.bodies

    monkeypatch.setattr(native, "_early_bound", lambda value, interface: value)
    model = NativePart((Body(),))
    adapter = SimpleNamespace(currentModel=model)
    assert native.measure_one_solid_body_volume(adapter) == pytest.approx(1.25)
    for bodies in (None, (), (None,), (Body(), Body())):
        model.bodies = bodies
        with pytest.raises(RuntimeError, match="one native solid"):
            native.measure_one_solid_body_volume(adapter)


def test_part_record_and_running_finishes() -> None:
    config = _config.parts("pd-transgear-knob-shaft")
    assert config["number"] == "MHA-PD-08"
    assert config["material_specification"] == "SAE 1018 CF bar, ASTM A108-24"
    assert int(config["quantity"]) == 1
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    assert faces["journal"].diameter_mm == spec.JOURNAL_DIA
    assert faces["core"].diameter_mm == spec.CORE_DIA
    assert spec.CORE_FRONT_Z < faces["core"].contains_z_mm < spec.CORE_REAR_Z
    assert drawing.DIMENSION_CALLOUTS_BELOW == {"TipChamfer": spec.CHAMFER_CALLOUT}


def _inside(point_mm, focus_mm, radius_mm) -> bool:
    return math.dist(point_mm, focus_mm) < radius_mm


def test_neck_detail_fence_holds_every_detail_reference() -> None:
    # A crop drops a dimension whose reference it cuts away: FrontReliefDia
    # measures from the axis to the floor, FrontReliefWidth from F's origin
    # to the step, the corner R is its arc; both floors carry the Ø's arrows.
    focus, radius = drawing.DETAIL_FOCUS_MM, drawing.DETAIL_RADIUS_MM
    floor = spec.FRONT_RELIEF_DIA / 2.0
    width = spec.FRONT_RELIEF_WIDTH
    corner = spec.FRONT_CORNER_RADIUS
    references = [
        (0.0, 0.0),
        (-width, 0.0),
        (-corner, floor + corner),
        (-width, spec.CORE_DIA / 2.0),
        *((-z, sign * floor) for z in (corner, width - corner) for sign in (1, -1)),
    ]
    for point in references:
        assert _inside(point, focus, radius), point
    # Sheet: the crop is inside the sheet border, the frame row under it.
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    assert crop == pytest.approx(radius * drawing.DETAIL_SCALE[0] / 1000.0)
    assert center[0] - crop > 0.0254 / 2 and center[1] + crop < 0.2667
    frame_x, frame_top = drawing.NECK_RUNOUT_FRAME
    # The frame's box corner nearest the crop stands clear of the circle.
    corner_xy = (frame_x + drawing._FRAME_WIDTH, frame_top - drawing._FRAME_HEIGHT)
    assert corner_xy[0] < center[0]
    assert math.dist(corner_xy, center) - crop >= 0.002
    assert frame_top < 0.2667 - 0.004
    landing = drawing.NECK_RUNOUT_LANDING
    # The landing is on the straight floor, between the corner tori.
    assert -width + corner < drawing.NECK_LANDING_Z_MM < -corner
    assert math.dist(landing, center) < crop
    assert frame_x + drawing._FRAME_WIDTH < landing[0]
    # The Ø's line rises right of the frame's leader, inside the neck.
    dia_x = drawing.DETAIL_KEEP["FrontReliefDia"][0]
    assert landing[0] < dia_x < drawing._detail_xy(-width + corner, 0.0)[0]


def test_neck_frame_leader_stays_under_the_relief_dia_text() -> None:
    # 3f50160d9 full build: the Ø3.950 text hung LEFT of its line, box
    # [87.8, 256.6]..[104.6, 260.2] mm for a keep at (106.0, 258.5), and the
    # frame's shoulder (98.2 -> 104.5 at y 258.5) ran 6.35 mm through it
    # (leader-through-text).  Whichever side the text hangs, the frame's
    # shoulder and plumb leader now run under it, and the text clears the
    # frame's box and the border.
    x, y = drawing.DETAIL_KEEP["FrontReliefDia"]
    text_w, text_h, short = 0.0168, 0.0036, 0.0014
    frame_x, frame_top = drawing.NECK_RUNOUT_FRAME
    shoulder_y = frame_top - drawing._FRAME_HEIGHT / 2.0
    landing = drawing.NECK_RUNOUT_LANDING
    assert frame_x + drawing._FRAME_WIDTH + drawing._FRAME_SHOULDER == pytest.approx(
        landing[0]
    )
    # Shoulder and plumb leader run at or under shoulder_y, inside the
    # frame's row; the text, either side of its line, stands over the row.
    ymin, ymax = y - text_h / 2.0, y + text_h / 2.0
    assert max(shoulder_y, landing[1]) < frame_top
    assert ymin - frame_top >= 0.002
    assert ymax <= 0.2667 - 0.0015
    # The old row, frame top 0.262 with the text level with its shoulder,
    # reproduces the logged crossing under the same model.
    old_top, old_y = 0.262, 0.2585
    old_shoulder = old_top - drawing._FRAME_HEIGHT / 2.0
    assert old_y - text_h / 2.0 < old_shoulder < old_y + text_h / 2.0
    assert x - short - text_w < landing[0] - drawing._FRAME_SHOULDER / 2.0 < x - short


def test_neck_detail_annotations_stay_clear_of_the_side_and_end_views() -> None:
    # The detail, its frame, label and kept texts sit left of the journal
    # Ø's witness line (x 0.1353) and over its text (top 0.193); the gear
    # data dropped to the lower left, between the datum A box (bottom 0.140)
    # and the notes (top 0.070).
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    assert center[0] + crop < 0.1353
    assert center[1] - crop > 0.193
    for x, y in drawing.DETAIL_KEEP.values():
        assert x < 0.1353 - 0.005 and y > 0.193 - 0.010
    assert drawing.DETAIL_LABEL_XY[0] + 0.030 < center[0] - crop
    gear_top = drawing.GEAR_DATA_XY[1]
    lines = len(spec.GEAR_DATA.splitlines())
    assert gear_top < 0.140 - 0.010
    assert gear_top - lines * 1.4 * drawing.GEAR_DATA_CHAR_HEIGHT > drawing.NOTES_XY[1]


def test_root_envelope_text_stands_right_of_the_end_view() -> None:
    # mr-stack6: left of the view, REFERENCE ROOT ran into the side view's
    # tip witness line and the axial rows.  Right of it, the text clears the
    # root acceptance note (top 0.105) and the ToothSpan text (bottom 0.187).
    x, y = drawing.END_KEEP["RootEnvelope"]
    assert x - drawing.FRONT_CENTER[0] > 2.0 * drawing.HALF_OD
    assert 0.105 + 0.010 < y < 0.187 - 0.010
    assert x + 0.026 < 0.4191


class _NeckView:
    """A recording IView double for detail B's place-move-crop."""

    def __init__(
        self, *, crop_status: int = 1, crops: bool = True, moves: bool = True,
        mirrored: bool = False,
    ) -> None:
        self.ScaleRatio = (10.0, 1.0)
        self.Position = (0.300, 0.100)
        self.crop_status = crop_status
        self.crops = crops
        self.moves = moves
        self.mirrored = mirrored
        self.cropped = False
        self.calls: list[str] = []
        self.CropViewJaggedOutline = False
        self.CropViewNoOutline = False

    def SetViewPosition(self, target, _update) -> bool:  # noqa: N802
        self.calls.append("SetViewPosition")
        if self.moves:
            self.Position = tuple(float(value) for value in target)
        return True

    def GetOutline(self):  # noqa: N802
        if self.cropped:
            return (0.078, 0.196, 0.132, 0.250)
        return (-0.100, 0.150, 0.610, 0.300)

    def Crop2(self, jagged, no_outline, intensity) -> int:  # noqa: N802
        self.calls.append(f"Crop2({jagged}, {no_outline}, {intensity})")
        self.cropped = self.crops
        return self.crop_status

    def IsCropped(self) -> bool:  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self) -> None:  # noqa: N802
        self.calls.append("UpdateViewDisplayGeometry")


class _NeckModel:
    def ClearSelection2(self, _all) -> None:  # noqa: N802
        pass

    def EditRebuild3(self) -> None:  # noqa: N802
        pass


def _neck_seat(monkeypatch, view: _NeckView) -> list[tuple]:
    """Point the drawing's COM helpers at ``view``: a *Right projection at
    10:1 (model +Z runs left) a fixed offset from the view's position."""
    log: list[tuple] = []
    offset = (-0.050, 0.070)

    def place(_adapter, _source, orientation, x, y, *, scale):
        log.append(("place", orientation, (x, y), scale))
        return view

    def model_point(_adapter, _view, point, *, label):
        handing = 1.0 if view.mirrored else -1.0
        return (
            view.Position[0] + offset[0] + handing * 10.0 * point[2],
            view.Position[1] + offset[1] + 10.0 * point[1],
        )

    def circle(_adapter, _view, center, radius, *, label, add_to_db=False):
        log.append(("circle", center, radius, add_to_db))
        return object()

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", model_point)
    monkeypatch.setattr(drawing, "_sketch_circle", circle)
    monkeypatch.setattr(drawing, "_activate_view", lambda *_a, **_k: "Drawing View5")
    return log


def _crop_neck(monkeypatch, view: _NeckView) -> list[tuple]:
    adapter = SimpleNamespace(currentModel=_NeckModel())
    log = _neck_seat(monkeypatch, view)
    assert drawing._placed_detail_view(adapter) is view
    drawing._crop_detail_view(adapter, view)
    return log


def test_neck_detail_is_a_cropped_right_model_view(monkeypatch) -> None:
    view = _NeckView()
    log = _crop_neck(monkeypatch, view)
    assert log[0] == ("place", "*Right", drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)
    kind, center, radius, add_to_db = log[1]
    assert kind == "circle" and not add_to_db
    assert center == pytest.approx(drawing.DETAIL_CENTER, abs=1e-12)
    assert radius == pytest.approx(drawing.DETAIL_CROP_RADIUS)
    assert view.calls[0] == "SetViewPosition"
    assert "Crop2(False, False, 1)" in view.calls


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"crop_status": 0}, "not cropped"),
        ({"crops": False}, "not cropped"),
        ({"moves": False}, "neck detail focus sits at"),
        ({"mirrored": True}, "neck runout landing sits at"),
    ],
)
def test_neck_detail_fails_loud_when_the_seat_does_not_obey(
    monkeypatch, kwargs, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _crop_neck(monkeypatch, _NeckView(**kwargs))


class _DimensionedView:
    def __init__(self) -> None:
        self.names: list[str] = []


def _order_seat(monkeypatch, view: _DimensionedView, *, crop_drops: tuple[str, ...]):
    calls: list[str] = []
    events: list[tuple[str, dict]] = []

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        calls.append("import")
        view.names = sorted(keep)
        return ["curated"]

    def crop(_adapter, _view):
        calls.append("crop")
        view.names = [name for name in view.names if name not in crop_drops]

    def names(_adapter, _view):
        calls.append("read")
        return sorted(view.names)

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_detail_view", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", names)
    monkeypatch.setattr(
        drawing._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return calls, events


def test_neck_detail_is_dimensioned_before_it_is_cropped(monkeypatch) -> None:
    view = _DimensionedView()
    calls, events = _order_seat(monkeypatch, view, crop_drops=())
    assert drawing._dimension_then_crop_detail(object(), view) == ["curated"]
    assert calls == ["import", "read", "crop", "read"]
    assert events[0][0] == "neck_detail.crop" and events[0][1]["lost"] == ""


class _BuildRecorder:
    """Stand-ins for every seat-touching call ``drawing.build`` makes,
    recording each call's name and its view in the order build makes them."""

    def __init__(self, monkeypatch, tmp_path) -> None:
        self.calls: list[tuple[str, object]] = []
        self.made: dict[str, list[tuple[tuple, dict]]] = {}
        self.frame_views: list[object] = []
        source = tmp_path / "pd-transgear-knob-shaft.SLDPRT"
        source.write_bytes(b"")
        monkeypatch.setattr(drawing, "SOURCE", source)
        self.views: dict[str, SimpleNamespace] = {}
        self.detail = SimpleNamespace(name="detail", ReferencedDocument=object())
        for name in (
            "check", "require_source_control", "stamp_drawing_summary",
            "set_hidden_lines_removed", "set_dimension_callouts",
            "assert_imported_precision", "add_view_centerline", "add_attached_note",
            "add_surface_finish", "add_datum_feature", "add_feature_control_frame",
            "add_toothspace_callout", "_mark_detail_on_side", "_label_detail",
            "add_property_linked_note", "visible_circle_edge",
        ):
            monkeypatch.setattr(drawing, name, self._recorder(name))
        monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
        monkeypatch.setattr(
            drawing, "read_required_properties",
            lambda _model, wanted, *, required: {key: key for key in wanted},
        )
        monkeypatch.setattr(
            drawing, "new_project_drawing", lambda *_a, **_k: (object(), object())
        )
        monkeypatch.setattr(drawing, "place_view", self._place)
        monkeypatch.setattr(drawing, "_placed_detail_view", self._placed_detail)
        monkeypatch.setattr(drawing, "_dimension_then_crop_detail", self._crop_detail)
        monkeypatch.setattr(drawing, "curate_view_dimensions", self._curate)
        monkeypatch.setattr(
            drawing, "resolve_faces", lambda _model, requests: {key: key for key in requests}
        )
        monkeypatch.setattr(drawing, "finalize_drawing", self._finalize)
        self.adapter = SimpleNamespace(currentModel=object(), open_model=self._open)

    def _recorder(self, name: str):
        def record(*args, **kwargs):
            view = next(
                (arg.name for arg in args if hasattr(arg, "ReferencedDocument")), None
            )
            self.calls.append((name, kwargs.get("label") or view))
            self.made.setdefault(name, []).append((args, kwargs))
            if name == "add_feature_control_frame":
                self.frame_views.append(view)
            return True

        return record

    async def _open(self, _path):
        return True

    def _place(self, _adapter, _source, orientation, _x, _y, *, scale):
        view = SimpleNamespace(name=orientation, ReferencedDocument=object())
        self.views[orientation] = view
        return view

    def _placed_detail(self, _adapter):
        self.calls.append(("_placed_detail_view", None))
        return self.detail

    def _crop_detail(self, _adapter, view):
        self.calls.append(("_dimension_then_crop_detail", view.name))
        return ["detail dims"]

    def _curate(self, _adapter, view, *, keep, view_label, dimensions_by_feature):
        self.calls.append(("curate_view_dimensions", view_label))
        return [view_label]

    async def _finalize(self, *_args, **_kwargs):
        self.calls.append(("finalize_drawing", None))
        return {}

    def index(self, name: str, view=None) -> int:
        return next(
            i for i, (called, which) in enumerate(self.calls)
            if called == name and (view is None or which == view)
        )


def test_build_dimensions_the_detail_before_the_side_and_marks_it_last(
    monkeypatch, tmp_path
) -> None:
    # A dimension already on the sheet is never imported again, so the
    # detail must import its three before the side view's targeted import;
    # the mark circle goes on after every side-view pick.
    import asyncio

    seat = _BuildRecorder(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(seat.adapter)) == {}
    assert seat.index("_placed_detail_view") < seat.index(
        "_dimension_then_crop_detail", "detail"
    ) < seat.index("curate_view_dimensions", "side")
    frames = [which for name, which in seat.calls if name == "add_feature_control_frame"]
    assert frames == ["core_total_runout", "front_neck_total_runout"]
    assert seat.frame_views == ["*Right", "detail"]
    last_pick = max(
        i for i, (name, _label) in enumerate(seat.calls)
        if name in ("add_feature_control_frame", "add_toothspace_callout")
    )
    assert last_pick < seat.index("_mark_detail_on_side") < seat.index("_label_detail")
    assert seat.index("_label_detail") < seat.index("finalize_drawing")


def test_build_takes_its_controls_and_callouts_from_the_spec(monkeypatch, tmp_path) -> None:
    # Run 10: a silhouette hit-test on the 0.3 mm neck floor took a
    # neighbour; each frame now lands on its resolved source FACE.
    import asyncio

    seat = _BuildRecorder(monkeypatch, tmp_path)
    asyncio.run(drawing.build(seat.adapter))
    for (_args, kwargs) in seat.made["add_feature_control_frame"]:
        key = kwargs["label"]
        assert kwargs["entity_type"] == "FACE" and kwargs["entity"] == key
        assert kwargs["leader_attach_xy"] == drawing.CONTROL_ATTACHMENTS[key][0]
    ((_args, callout),) = seat.made["add_toothspace_callout"]
    assert callout["profile"] is spec.STOCK_PROFILE
    assert callout["actual_pin_diameter_mm"] == spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM
    assert callout["rotate_rad"] == pytest.approx(math.pi / spec.TEETH)
    assert callout["axial_station_mm"] == 0.0
    ((control, _kwargs),) = seat.made["require_source_control"]
    assert control == (spec.TOOTH_SPACE_CALLOUT_PROPERTY, spec.TOOTH_SPACE_CALLOUT)
    notes = [args[1] for args, _kwargs in seat.made["add_property_linked_note"]]
    assert notes == ["Gear Data", "Manufacturing Notes", "Root Acceptance"]


def test_neck_detail_fails_loud_when_the_crop_takes_a_dimension(monkeypatch) -> None:
    view = _DimensionedView()
    _calls, events = _order_seat(monkeypatch, view, crop_drops=("FrontReliefDia",))
    with pytest.raises(RuntimeError, match=r"lost \['FrontReliefDia'\] to its crop"):
        drawing._dimension_then_crop_detail(object(), view)
    assert events[0][1]["lost"] == "FrontReliefDia"


# The stock-gear part builds, run offline with their seat stubbed
# (_test_stubbed_build): what each authors, in what order, checked on the
# recorded calls of the real functions.


@pytest.mark.parametrize(
    ("module_name", "volume_check", "pattern"),
    [
        ("build_pd_transgear_knob_shaft", "_native_volume_check", "pattern_stock_feature"),
        ("build_pd_transgear_feed_pinion", "check_one_solid_body_volume", "pattern_about_z"),
    ],
)
def test_straight_stock_pass_bosses_the_blank_then_cuts_one_patterned_gap(
    monkeypatch: pytest.MonkeyPatch, module_name: str, volume_check: str, pattern: str
) -> None:
    module = importlib.import_module(module_name)
    seat = stub_seat(monkeypatch, module, keep=("_straight_stock_gaps",))
    seat.placed_ground_curve.side_effect = (
        lambda _adapter, _segment, _phase: f"Curve{seat.placed_ground_curve.call_count}"
    )
    seat.name_last_feature.side_effect = lambda _adapter, name: name
    adapter = offline_adapter()
    seat.attach_mock(adapter, "adapter")
    asyncio.run(module._straight_stock_gaps(adapter, []))

    watched = {
        "ensure_fully_defined", "adapter.exit_sketch", "adapter.create_extrusion",
        "adapter.create_cut_extrude", volume_check, "placed_ground_curve", pattern,
    }
    order = [name for name, _args, _kwargs in seat.mock_calls if name in watched]
    order = [name for k, name in enumerate(order) if k == 0 or name != order[k - 1]]
    assert order == [
        "ensure_fully_defined", "adapter.exit_sketch", "adapter.create_extrusion",
        volume_check,
        "placed_ground_curve", "ensure_fully_defined", "adapter.exit_sketch",
        "adapter.create_cut_extrude", volume_check,
        pattern, volume_check,
    ]
    # The gap is the stock profile's native segments in cut order, each
    # FIXed as created, at clearance past the blank.
    profile = module.STOCK_PROFILE
    segments = [placed.args[1] for placed in seat.placed_ground_curve.call_args_list]
    assert segments == list(
        profile.cut_order_native_segments(clearance_radius_mm=profile.blank_radius_mm + 1.0)
    )
    curves = [f"Curve{k}" for k in range(1, len(segments) + 1)]
    assert seat.ensure_fully_defined.call_args_list[1].kwargs["fix_entities"] == curves
    # A blind boss of the face width, then a blind cut of the full depth,
    # both from the sketch plane (F): one direction, solid, merged, each
    # result checked.
    boss = adapter.create_extrusion.await_args.args[0]
    cut = adapter.create_cut_extrude.await_args.args[0]
    assert (boss.depth, cut.depth) == (module.FACE_WIDTH, module.FULL_DEPTH)
    for feature in (boss, cut):
        assert feature.end_condition == "Blind"
        assert feature.start_offset == 0.0
        assert not (feature.reverse_direction or feature.both_directions or feature.thin_feature)
        assert feature.merge_result
    checked = [id(call.args[1]) for call in seat.check.call_args_list]
    assert id(adapter.create_extrusion.return_value) in checked
    assert id(adapter.create_cut_extrude.return_value) in checked
    # One pattern of the cut gap seed, one instance per tooth.
    names = [name for name, _args, _kwargs in seat.mock_calls]
    cut_at = names.index("adapter.create_cut_extrude")
    seed = next(
        args[1] for name, args, _kwargs in seat.mock_calls[cut_at:]
        if name == "name_last_feature"
    )
    (patterned,) = getattr(seat, pattern).call_args_list
    assert patterned.args[1] == seed
    assert patterned.args[2] == module.TEETH


def test_neck_corners_are_equal_tangent_quarter_arcs_with_a_radial_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = stub_seat(monkeypatch, part, keep=("_stud_profile",))
    arcs: list[tuple[str, tuple[float, ...]]] = []

    def native_arc(_adapter, _label, *points):
        arcs.append((f"Arc{len(arcs) + 1}", points))
        return arcs[-1][0]

    seat._native_arc.side_effect = native_arc
    adapter = offline_adapter()
    asyncio.run(part._stud_profile(adapter))

    radius = part.FRONT_CORNER_RADIUS
    assert len(arcs) == 2
    for _name, (cx, cy, sx, sy, ex, ey) in arcs:
        assert math.dist((cx, cy), (sx, sy)) == pytest.approx(radius)
        assert math.dist((cx, cy), (ex, ey)) == pytest.approx(radius)
        assert math.dist((sx, sy), (ex, ey)) == pytest.approx(radius * math.sqrt(2.0))
        assert min(sy, ey) == pytest.approx(part._R_NECK)
    front, core = (name for name, _points in arcs)
    constraints = [call.args for call in adapter.add_sketch_constraint.await_args_list]
    for arc in (front, core):
        assert sum(1 for c in constraints if arc in c[:2] and c[2] == "tangent") == 2
    assert (front, core, "equal") in constraints
    dimensions = [call.args for call in adapter.add_sketch_dimension.await_args_list]
    assert (front, None, "radial", radius) in dimensions


def test_cutter_end_is_authored_after_the_turned_profiles_within_its_volume_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = stub_seat(
        monkeypatch, part,
        spy=("_stud_profile", "_journal_profile", "_revolve_profile", "_stock_cutter_endcut"),
    )
    seat._straight_stock_gaps.return_value = part.ToothedDisc(
        1000.0, ("StraightToothGap", "StraightToothPattern")
    )
    seat._cut_core_flat.side_effect = lambda _adapter, _jobs, volume: volume
    seat._native_volume_check.side_effect = (
        lambda _adapter, _label, lower, upper, _allowance: (lower + upper) / 2.0
    )
    seat._native_arc.side_effect = lambda _adapter, label, *_points: label
    endcut = SimpleNamespace(plane="ToolEndPlane", cut="ToolEndCut")
    seat.author_cutter_endcut.return_value = endcut
    adapter = offline_adapter()
    seat.attach_mock(adapter, "adapter")
    asyncio.run(part.build(adapter))

    names = [name for name, _args, _kwargs in seat.mock_calls]
    authored = names.index("author_cutter_endcut")
    assert names.index("_stud_profile") < authored
    assert names.index("_journal_profile") < authored
    assert seat.author_cutter_endcut.await_args.args[1:] == (
        part.STOCK_PROFILE, part.CUTTER_DIA, part.FULL_DEPTH
    )
    # The seed removes one tooth's end and the pattern TEETH of them, each
    # within the spec's resolved removal bounds of the volume before it.
    lower, upper = spec.endcut_volume_bounds_mm3()
    before = seat._stock_cutter_endcut.call_args.args[1]
    checks = [
        args[2:4] for name, args, _kwargs in seat.mock_calls[authored:]
        if name == "_native_volume_check"
    ]
    assert checks[0] == pytest.approx((before - upper, before - lower))
    assert checks[1] == pytest.approx(
        (before - part.TEETH * upper, before - part.TEETH * lower)
    )
    (patterned,) = [
        args for name, args, _kwargs in seat.mock_calls[authored:]
        if name == "pattern_stock_feature"
    ]
    assert patterned[1:3] == (endcut.cut, part.TEETH)
    # Each turned profile is revolved a full turn as its sketch closes, the
    # body named for the profile handed over.
    revolves = []
    for name, args, _kwargs in seat.mock_calls:
        if name == "_revolve_profile":
            revolves.append(("handoff", args[1:]))
        elif name == "adapter.create_revolve":
            revolves.append(("revolve", args[0].angle))
        elif name == "name_last_feature" and args[1] in (
            "StudProfile", "Stud", "JournalProfile", "Journal"
        ):
            revolves.append(("named", args[1]))
    assert revolves == [
        ("named", "StudProfile"), ("handoff", ("stud", "Stud")),
        ("revolve", 360.0), ("named", "Stud"),
        ("named", "JournalProfile"), ("handoff", ("journal", "Journal")),
        ("revolve", 360.0), ("named", "Journal"),
    ]
    # The last native volume check is the complete part against the spec's
    # finished-shaft bounds, after the drive equations' final rebuild.
    volume_checks = [k for k, name in enumerate(names) if name == "_native_volume_check"]
    last_rebuild = len(names) - 1 - names[::-1].index("force_rebuild")
    assert volume_checks[-1] > last_rebuild
    assert seat.mock_calls[volume_checks[-1]].args[2:4] == pytest.approx(
        spec.expected_volume_bounds_mm3()
    )
