"""Offline contracts; these do not replace the final source-SHA native receipt."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import itertools
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
from _printed_tolerance import printed_band_mm
from pd_cluster_stack_band import PRINTED_LENGTH_BAND, STACK_NAME
from paper_drive_stock_inspection import span_contact_points_mm, toothspace_gauge_contact_mm
from stock_form_cutter import (
    CutterTemplate,
    StockFormProfile,
    template_for_teeth,
    translation_for_tangent_span,
)
from _test_stubbed_build import offline_adapter, stub_seat


F_MACHINE_Z = -148.1


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.name == "pd-transgear-knob-shaft.SLDDRW"
    assert drawing.PDF.name == "pd-transgear-knob-shaft.pdf"
    assert drawing.PNG.name == "pd-transgear-knob-shaft_drawing.png"
    assert DRAWINGS_BY_NAME["pd_transgear_knob_shaft"].script == Path(drawing.__file__).resolve()


def test_native_stock_source_is_the_selected_15t_48dp_master() -> None:
    import pd_rack_pinion_spec as disc

    profile = spec.STOCK_PROFILE
    assert spec.TEETH == profile.teeth == disc.MESH_PINION_TEETH == 15
    assert spec.DIAMETRAL_PITCH == disc.DIAMETRAL_PITCH == 48
    assert profile.template == spec.CUTTER_TEMPLATE == template_for_teeth(15, 48, 20)
    assert spec.CUTTER_TEMPLATE == CutterTemplate(14, 48, 20)
    assert profile.template.cutter_number == spec.CUTTER_NUMBER == 7
    assert profile.template.reference_teeth == 14
    assert profile.radial_translation_mm == spec.RADIAL_SETTING == 0.266
    assert profile.blank_radius_mm == spec.OUTSIDE_DIA / 2
    assert spec.OUTSIDE_DIA == 8.98
    assert spec.OUTSIDE_DIA_BAND == (0.0, -0.02)
    assert spec.CUTTER_DIA == 44.45
    assert spec.CUTTER_ARBOR_BORE == 22.225
    assert spec.CUTTER_SKU == "10-289-487"
    assert part.STOCK_PROFILE is profile
    assert "PROFILE SHIFT" not in spec.GEAR_DATA
    lower, upper = sorted(spec.SPAN_LIMITS)
    assert spec.GEAR_DATA.splitlines()[1:] == [
        "NUMBER OF TEETH:  15",
        "DIAMETRAL PITCH:  48.00",
        "PRESSURE ANGLE:  20.0 DEG",
        f"PITCH DIAMETER (mm, REF):  {spec.PITCH_DIA:.2f}",
        f"WHOLE DEPTH (mm, REF):  {spec.WHOLE_DEPTH:.3f}",
        "CUTTER:  #7, 14-16T",
        f"SPAN OVER 2 TEETH:  {lower:.4f}-{upper:.4f}",
        f"ROOT DIAMETER (mm):  {spec.ROOT_DIA_MIN:.2f} MIN",
        "MATES WITH:  DISC MHA-PD-06, 150T",
    ]


def test_span_is_actual_finite_contact_and_printed_limits_are_inverted() -> None:
    assert spec.SPAN_TEETH == 2
    assert spec.SPAN_PLACES == 4
    assert spec.SPAN_NOMINAL == pytest.approx(spec.STOCK_PROFILE.tangent_span_mm(2))
    assert spec.SPAN_DEVIATIONS == pytest.approx(
        (spec.SPAN_LIMITS[0] - spec.SPAN_NOMINAL, spec.SPAN_LIMITS[1] - spec.SPAN_NOMINAL)
    )
    for setting, tip in ((p.radial_translation_mm, p.blank_radius_mm) for p in spec.manufactured_profiles()):
        profile = StockFormProfile(spec.TEETH, spec.CUTTER_TEMPLATE, tip, setting)
        assert spec.RADIAL_SETTING_LIMITS[0] <= setting <= spec.RADIAL_SETTING_LIMITS[1]
        actual = profile.tangent_span_mm(2)
        # The mechanics test's convention: the inverted setting limits land
        # on the printed span within the evaluator error plus a few ulps.
        error = 2 * profile.geometry_error_bound_mm + 8.0 * math.ulp(spec.SPAN_NOMINAL)
        assert spec.SPAN_LIMITS[0] - error <= actual <= spec.SPAN_LIMITS[1] + error
        a, b = span_contact_points_mm(profile, 2)
        assert math.dist(a, b) == pytest.approx(actual, abs=1e-10)
    assert spec.SPAN_PREFIX == "CONTROL SPAN 2 TEETH "
    for note in (spec.TOOTH_EDGE_NOTE, spec.BEARING_FACE_NOTE):
        assert "BISECTOR" not in note  # method, not requirement
    # Rounded limits, not the old provisional setting band, define acceptance.
    lo, hi = spec.RADIAL_SETTING_LIMITS
    assert lo < spec.RADIAL_SETTING < hi
    outside = hi + 0.001
    tip_min = (spec.OUTSIDE_DIA + min(spec.OUTSIDE_DIA_BAND)) / 2
    rejected_span = StockFormProfile(
        spec.TEETH, spec.CUTTER_TEMPLATE, tip_min, outside
    ).tangent_span_mm(2)
    assert rejected_span > spec.SPAN_LIMITS[1]
    with pytest.raises(ValueError):
        translation_for_tangent_span(
            spec.TEETH, spec.CUTTER_TEMPLATE, rejected_span, 2,
            translation_bounds_mm=spec.RADIAL_SETTING_LIMITS,
        )


def test_all_accepted_corners_keep_genuine_finite_ground_tip_in_air() -> None:
    for profile in spec.manufactured_profiles():
        tip = profile.flank_point(profile.template.flank_parameter_max)
        assert math.hypot(*tip) - profile.blank_radius_mm > profile.geometry_error_bound_mm
        assert 2 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
        assert profile.root_point(profile.root_half_angle_rad)[0] >= spec.ROOT_DEPTH_X_MIN
    # The finite tip is the translated master's support, not the 14T
    # reference's own tip radius (which this 15T blank already exceeds).
    support = spec.STOCK_PROFILE.support_radius_max_mm
    assert spec.CUTTER_TEMPLATE.tip_radius_mm < spec.STOCK_PROFILE.blank_radius_mm < support
    with pytest.raises(ValueError, match="FINITE cutter support"):
        replace(spec.STOCK_PROFILE, blank_radius_mm=support + 0.001)


def test_front_core_and_journal_clear_the_straight_through_cutter() -> None:
    # #2034: straight full-depth gaps through the face, no rear endcut; the
    # cutter runs out over the D-core at F and over the journal at the rear.
    assert spec.FRONT_CORE_AIR_MIN > 0.0
    journal_max = spec.JOURNAL_DIA + max(spec.JOURNAL_DIA_BAND)
    assert spec.ROOT_DIA_EXACT_MIN > journal_max + spec.TOOTH_SPACE_RUNOUT_TIR_MM
    assert spec.JOURNAL_CUTTER_AIR_MIN == pytest.approx(
        (spec.ROOT_DIA_EXACT_MIN - journal_max - spec.TOOTH_SPACE_RUNOUT_TIR_MM) / 2
    )
    assert spec.JOURNAL_CUTTER_AIR_MIN > spec.JOURNAL_CUTTER_AIR_FLOOR
    for retired in (
        "FULL_DEPTH", "CUTTER_RUNOUT_MAX", "CUTTER_RUNOUT_END_WORST", "CUTTER_RUNOUT_END_Z",
        "RUNOUT_RISE_WORST", "CUTTER_AXIS_R", "CUTTER_AXIS_Z", "DISC_REAR_FROM_F_WORST",
        "HUB_BORE_FROM_F_WORST", "cutter_runout", "endcut_volume_bounds_mm3",
    ):
        assert not hasattr(spec, retired), retired
    # Negative controls: a core enlarged to Ø6.6 and a Ø6.7 journal both
    # stand in the cutter's path.
    assert spec.ROOT_DIA_EXACT_MIN - 6.6 - spec.CORE_TOTAL_RUNOUT - spec.TOOTH_SPACE_RUNOUT_TIR_MM < 0.0
    assert spec.ROOT_DIA_EXACT_MIN - 6.7 - spec.TOOTH_SPACE_RUNOUT_TIR_MM < 0.0


def test_real_d_core_thread_and_six_mm_g6_source() -> None:
    assert spec.CORE_DIA == 4.85 and spec.CORE_DIA_BAND == (0.0, -0.008)
    assert spec.CORE_FLAT_FROM_AXIS == 2.125 and spec.CORE_FLAT_BAND == (0.0, -0.015)
    assert spec.JOURNAL_DIA == 6.0 and spec.JOURNAL_DIA_BAND == (-0.004, -0.012)
    # The thread length reads from the relief's shoulder (machinist review r8).
    assert spec.THREAD == "#8-32"
    assert spec.THREAD_CALLOUT == "#8-32 UNC\nTHREAD TO RELIEF"
    assert spec.RELIEF_DIA_MAX < spec.THREAD_ROOT_2A_MIN
    assert spec.TIP_CHAMFER_MAX < spec.THREAD_PITCH
    # The #8-32 UNC-2A class governs the blank: no separate printed band.
    assert spec.THREAD_BLANK_LIMITS == spec.THREAD_MAJOR_2A
    assert not hasattr(spec, "THREAD_BLANK_DIA_BAND")
    blank_min, blank_max = spec.THREAD_BLANK_LIMITS
    assert blank_min < spec.THREAD_BLANK_DIA < blank_max
    # The chamfer runs to the minor, so its worst depth follows the largest
    # 2A blank; a Ø5.0 blank's chamfer would pass the one-pitch budget.
    assert spec.TIP_CHAMFER_MAX == pytest.approx(
        (spec.THREAD_MAJOR_2A[1] - spec.THREAD_BASIC_MINOR) / 2.0
    )
    assert (5.0 - spec.THREAD_BASIC_MINOR) / 2.0 > spec.THREAD_PITCH
    assert spec.TIP_CHAMFER_CALLOUT == "CHAMFER 45 DEG TO MINOR"
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
    assert spec.FRONT_CORNER_RADIUS == 0.1
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
    assert flat_min - (spec.FRONT_RELIEF_DIA_MAX / 2 + 0.050) > 0.0


def test_neck_diameter_prints_limits_that_state_both_jobs() -> None:
    # Owner ruling (machinist review r8): LIMITS 3.95/3.82 at two places;
    # the maximum clears the collar, the minimum carries the drive torque.
    assert spec.FRONT_RELIEF_DIA_TOL_TYPE == 3
    assert spec.FRONT_RELIEF_DIA_PLACES == 2
    assert spec.FRONT_RELIEF_DIA_MAX == spec.FRONT_RELIEF_DIA == 3.95
    assert spec.FRONT_RELIEF_DIA_MIN == 3.82
    hi, lo = spec.FRONT_RELIEF_DIA_BAND
    assert hi == 0.0
    assert spec.FRONT_RELIEF_DIA + lo == pytest.approx(spec.FRONT_RELIEF_DIA_MIN)
    assert spec.FRONT_RELIEF_AREA_MIN == pytest.approx(math.pi * 3.82**2 / 4.0)
    jobs = " ".join(drawing.NECK_DIA_JOBS)
    assert jobs == f"MAX CLEARS {spec.DRIVE_COLLAR_NUMBER}; MIN CARRIES DRIVE TORQUE"
    suffix = drawing.DIMENSION_SUFFIXES["FrontReliefDia"]
    assert suffix == f" {drawing.NECK_DIA_JOBS[0]}"
    row = drawing.DIMENSION_CALLOUTS_BELOW["FrontReliefDia"]
    assert row == drawing.NECK_DIA_JOBS[1]
    # Negative control: the two-place general band would put the neck's
    # crown into the torqued core-flat plane.
    flat_min = spec.CORE_FLAT_FROM_AXIS + min(spec.CORE_FLAT_BAND)
    runouts = (spec.CORE_TOTAL_RUNOUT + spec.FRONT_RELIEF_TOTAL_RUNOUT) / 2
    two_place_max = spec.FRONT_RELIEF_DIA + printed_band_mm(2)
    assert flat_min - two_place_max / 2 - runouts < 0.0
    assert flat_min - spec.FRONT_RELIEF_DIA_MAX / 2 - runouts > 0.0
    # The neck width keeps three places: two would leave the flat no reach
    # past the core shoulder; its callout states that function.
    assert spec.FRONT_RELIEF_WIDTH_PLACES == 3
    assert spec.FRONT_RELIEF_WIDTH - printed_band_mm(2) - 0.170 < 0.100
    assert drawing.DIMENSION_CALLOUTS_BELOW["FrontReliefWidth"] == "D-FLAT\nRUNOUT"


def test_neck_corner_radius_prints_a_maximum_from_sharp() -> None:
    # R0.10 MAX (swTolMAX): the modelled corner is the largest acceptable.
    assert spec.FRONT_CORNER_RADIUS_TOL_TYPE == 6
    assert spec.FRONT_CORNER_RADIUS_PLACES == 2
    assert spec.FRONT_CORNER_RADIUS == spec.FRONT_CORNER_RADIUS_MAX
    hi, lo = spec.FRONT_CORNER_RADIUS_BAND
    assert spec.FRONT_CORNER_RADIUS + lo == 0.0
    assert hi == 0.0
    # The narrowest neck keeps a straight floor between two maximum corners.
    assert spec.FRONT_RELIEF_WIDTH_MIN > 2.0 * spec.FRONT_CORNER_RADIUS_MAX


def test_complete_nominal_native_volume_uses_full_face_gaps_and_true_d() -> None:
    lower, upper = spec.expected_volume_bounds_mm3()
    r = spec.CORE_DIA / 2
    h = spec.CORE_FLAT_FROM_AXIS
    flat_removed = (r*r*math.acos(h/r) - h*math.sqrt(r*r-h*h)) * spec.CORE_ACTIVE_LENGTH
    turned = (
        math.pi * spec.STOCK_PROFILE.blank_radius_mm**2 * spec.FACE_WIDTH
        + part.V_STUD + part.V_JOURNAL - flat_removed
    )
    straight = spec.TEETH * spec.STOCK_PROFILE.gap_area_mm2 * spec.FACE_WIDTH
    assert lower <= turned - straight <= upper
    assert upper - lower <= 1e-6
    # Negative control: the retired straight pass to 4.65, its endcut
    # omitted, cannot meet the oracle.
    partial = spec.TEETH * spec.STOCK_PROFILE.gap_area_mm2 * 4.65
    assert turned - partial > upper


def test_every_native_dimension_is_placed_once_with_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.SIDE_KEEP, drawing.END_KEEP, drawing.DETAIL_KEEP)
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set().union(*keeps) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_DIMENSIONS["CoreFlatProfile"] == {"FlatEnd", "FlatToolRadius"}
    assert spec.DRAWING_DIMENSIONS["CoreFlatReference"] == {"FlatToAxis"}
    # The span over two teeth prints once, in the gear data block (machinist
    # review r8: its end-view dimension crossed the bores and the flat).
    assert "SpanProfile" not in spec.DRAWING_DIMENSIONS
    assert f"SPAN OVER {spec.SPAN_TEETH} TEETH" in spec.GEAR_DATA
    assert "RootInspectionProfile" not in spec.DRAWING_DIMENSIONS
    assert "TipChamfer" not in marked  # "CHAMFER 45 DEG TO MINOR" sizes it
    assert not {"FullDepth", "CutterRunout"} & marked
    assert not {"FullDepth", "CutterRunout"} & set(drawing.SIDE_KEEP)
    assert set(drawing.END_KEEP) == {"FlatToAxis"}
    assert "FlatToAxis" not in drawing.SIDE_KEEP
    assert "OverallLength" in drawing.SIDE_KEEP
    detail = {"FrontReliefDia", "FrontReliefWidth", "FrontCornerRadius"}
    assert set(drawing.DETAIL_KEEP) == detail | {"FlatEnd", "FlatToolRadius"}
    # Three-place sizes keep only what a stack needs; the rest print .XX.
    assert spec.DRAWING_PRECISION["StudProfile"]["CoreFront"] == 2
    assert spec.DRAWING_PRECISION["StudProfile"]["PlainCore"] == 2
    assert spec.DRAWING_PRECISION["StudProfile"]["ThreadBlankDia"] == 2
    assert spec.DRAWING_PRECISION["StudProfile"]["OverallLength"] == 2
    references = {"OverallLength": False, "ThreadBlankDia": True}
    assert drawing.REFERENCE_DIMENSIONS == references


def test_tool_end_limits_print_as_native_detail_dimensions() -> None:
    # The D-flat tool's end prints in detail B as the part's own FlatEnd
    # (LIMIT from F, prefixed) and FlatToolRadius (MAX); no note repeats it.
    assert not hasattr(spec, "CORE_FLAT_TOOL_REACH_NOTE")
    assert not hasattr(spec, "DRAWING_NOTES")
    assert spec.CORE_FLAT_CUT_END_PREFIX == "D-FLAT TOOL END "
    places = spec.DRAWING_PRECISION["CoreFlatProfile"]
    assert places == {"FlatEnd": 2, "FlatToolRadius": 2}
    flat_places = spec.DRAWING_PRECISION["CoreFlatReference"]
    assert flat_places == {"FlatToAxis": spec.CORE_FLAT_PLACES}
    assert spec.CORE_FLAT_TOOL_END_RADIUS_TOL_TYPE == 6
    assert spec.CORE_FLAT_CUT_END_TOL_TYPE == 3
    # Each shop note is short and leadered to its feature (machinist review r8).
    for note in (drawing.TOOTH_EDGE_LEADER_NOTE, spec.BEARING_FACE_NOTE):
        assert len(note.splitlines()) <= 4
    assert " ".join(drawing.TOOTH_EDGE_LEADER_NOTE.splitlines()) == spec.TOOTH_EDGE_NOTE
    assert spec.DRIVE_COLLAR_NUMBER in spec.BEARING_FACE_NOTE


def test_the_tool_end_keeps_its_native_limits(monkeypatch) -> None:
    # Its prefix is checked in the build-order test (set_dimension_prefix).
    limits: list[tuple[str, str, int]] = []

    def record(_adapter, feature, name, _nominal, _band, tol_type):
        limits.append((feature, name, tol_type))

    monkeypatch.setattr(part, "_apply_native_limits", record)
    part._apply_neck_and_flat_limits(object())
    assert limits == [
        ("StudProfile", "FrontReliefDia", 3),
        ("StudProfile", "FrontCornerRadius", 6),
        ("CoreFlatProfile", "FlatEnd", 3),
        ("CoreFlatProfile", "FlatToolRadius", 6),
    ]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "RootEnvelope" not in source and "author_root_envelope" not in source


def test_model_bands_and_source_linked_properties() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands[("StudProfile", "CoreDia")] == "*deviations(CORE_DIA_BAND)"
    assert bands[("JournalProfile", "JournalDia")] == "*deviations(JOURNAL_DIA_BAND)"
    assert bands[("CoreFlatReference", "FlatToAxis")] == "*deviations(CORE_FLAT_BAND)"
    assert ("CoreFlatProfile", "FlatToAxis") not in bands
    assert bands[("StudProfile", "OutsideDia")] == "*deviations(OUTSIDE_DIA_BAND)"
    assert bands[("GearBlank", "FaceWidth")] == "FACE_WIDTH_BAND"
    assert spec.FACE_WIDTH_BAND == PRINTED_LENGTH_BAND
    assert spec.FACE_WIDTH_BAND < printed_band_mm(spec.FACE_WIDTH_PLACES)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(source, filename=drawing.__file__)
    controls = {control.key: control for control in spec.GEOMETRIC_CONTROLS}
    assert set(drawing.CONTROL_ATTACHMENTS) == set(controls)
    assert drawing.CONTROL_ATTACHMENTS["core_total_runout"][0] != drawing.CONTROL_ATTACHMENTS["front_neck_total_runout"][0]
    for key, control in controls.items():
        assert control.datums == ("A",)
        assert float(control.tolerance) == spec.CORE_TOTAL_RUNOUT
    assert not hasattr(spec, "ROOT_ACCEPTANCE")
    assert f"ROOT DIAMETER (mm):  {spec.ROOT_DIA_MIN:.2f} MIN" in spec.GEAR_DATA


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
    # Owner material ruling: the generic grade, not a bar standard.
    assert config["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert config["material_specification"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert int(config["quantity"]) == 1
    # One running surface; the D-core is a sliding seat with no finish mark.
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    assert set(faces) == {"journal"}
    assert faces["journal"].diameter_mm == spec.JOURNAL_DIA
    assert not hasattr(drawing, "CORE_FINISH_SYMBOL")
    assert STACK_NAME in drawing.DIMENSION_CALLOUTS_BELOW["FaceWidth"]
    assert "TipChamfer" not in drawing.DIMENSION_CALLOUTS_BELOW


def test_tight_bands_name_their_mates_by_name_and_number() -> None:
    above, below = drawing.DIMENSION_CALLOUTS_ABOVE, drawing.DIMENSION_CALLOUTS_BELOW
    mates = {
        "JournalDia": ("ARM PLATE", "pd-transgear-arm-plate"),
        "CoreDia": ("DRIVE COLLAR", "pd-transgear-drive-collar"),
        "FlatToAxis": ("DRIVE COLLAR", "pd-transgear-drive-collar"),
        "ReliefDia": ("THUMBNUT", "pd-transgear-thumbnut"),
        "JournalLength": ("KNOB CUP", "pd-transgear-knob-cup"),
        # The D-flat tool's end leaves a full flat under the collar (r8).
        "FlatEnd": ("COLLAR", "pd-transgear-drive-collar"),
    }
    for name, (mate, key) in mates.items():
        text = " ".join({**above, **below}[name].split())
        assert mate in text and _config.parts(key)["number"] in text, name
    assert f"DISC {spec.DISC_NUMBER}" in above["OutsideDia"]
    assert "ToothSpan" not in above
    assert "FrontReliefDia" in drawing.DIMENSION_SUFFIXES
    assert "MHA-PD-22" in drawing.DIMENSION_SUFFIXES["FrontReliefDia"]
    # No fit callout carries a number of its own (the bands stay native).
    suffixes = drawing.DIMENSION_SUFFIXES
    for text in (*above.values(), *below.values(), *suffixes.values()):
        for word in text.replace("\n", " ").split():
            assert not word.replace(".", "").isdigit(), text
    # Vertical Ø callouts go above their text (a below one would sit on the
    # Ø's own line); no dimension carries both.
    assert not set(above) & set(below)


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
        # FlatEnd's tool-end point (the end arc's lower tangent) and the arc.
        (
            spec.CORE_FLAT_CUT_END_Z,
            -spec.CORE_FLAT_FROM_AXIS - spec.CORE_FLAT_TOOL_END_RADIUS,
        ),
        (
            spec.CORE_FLAT_CUT_END_Z - spec.CORE_FLAT_TOOL_END_RADIUS,
            -spec.CORE_FLAT_FROM_AXIS,
        ),
    ]
    for point in references:
        assert _inside(point, focus, radius), point
    # Sheet: the crop is inside the sheet border, the frame row under it.
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    assert crop == pytest.approx(radius * drawing.DETAIL_SCALE[0] / 1000.0)
    assert center[0] - crop > 0.0254 / 2 and center[1] + crop < 0.2667
    frame_x, frame_top = drawing.NECK_RUNOUT_FRAME
    # The frame's box corner nearest the crop stands clear of the circle.
    corner_xy = (frame_x, frame_top - drawing._FRAME_HEIGHT)
    assert corner_xy[0] > center[0]
    assert math.dist(corner_xy, center) - crop >= 0.002
    assert frame_top <= 0.2667 - 0.0015
    landing = drawing.NECK_RUNOUT_LANDING
    # The landing is on the straight floor, between the corner tori.
    assert -width + corner < drawing.NECK_LANDING_Z_MM < -corner
    assert math.dist(landing, center) < crop
    assert frame_x > landing[0]
    # The Ø's line rises left of the frame's leader, inside the neck.
    dia_x = drawing.DETAIL_KEEP["FrontReliefDia"][0]
    assert drawing._detail_xy(-corner, 0.0)[0] < dia_x < landing[0] - 0.001


def test_neck_dia_block_and_frames_share_the_band_over_the_crop() -> None:
    # Owner ruling r8: the neck Ø prints LIMITS with both jobs, a block that
    # runs from ~7.8 mm under its keep to ~5.7 mm over it (LIMITS stack two
    # 4.5 mm rows, the MIN row 5.5 mm more; run 20261101T035809796Z: the
    # flat's LIMITS and three rows ran from 13.3 under to 11.2 over).  It
    # hangs left of its line over its shoulder; the neck frame stands right
    # of its plumb leader, over the core frame.
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    x, y = drawing.DETAIL_KEEP["FrontReliefDia"]
    shoulder, top = y - 0.0078, y + 0.0057
    crop_top = center[1] + math.sqrt(crop**2 - (x - center[0]) ** 2)
    assert shoulder > crop_top + 0.001
    assert top <= 0.2667 - 0.001
    # Negative control: both jobs as two rows under the value top out past
    # the border.
    assert top + 0.0055 / 2 + 0.0005 > 0.2667
    neck_x, neck_top = drawing.NECK_RUNOUT_FRAME
    neck_bottom = neck_top - drawing._FRAME_HEIGHT
    landing = drawing.NECK_RUNOUT_LANDING
    assert neck_x == pytest.approx(landing[0] + drawing._FRAME_SHOULDER)
    # The plumb leader rises right of the Ø's line and its shoulder.
    assert landing[0] > x + 0.001
    core_x, core_top = drawing.CORE_RUNOUT_FRAME
    core_mid = core_top - drawing._FRAME_HEIGHT / 2
    core_shoulder = (core_x - drawing._FRAME_SHOULDER, core_mid)
    # The core frame stands a row under the neck frame; its leader descends
    # to the core under the neck frame's box.
    assert core_top < neck_bottom - 0.001
    assert core_shoulder[1] < neck_bottom
    assert drawing.CORE_RUNOUT_LANDING[1] < neck_bottom
    assert core_x + drawing._FRAME_WIDTH > neck_x + drawing._FRAME_WIDTH


def test_neck_detail_annotations_stay_clear_of_the_side_and_end_views() -> None:
    # The detail, its frame, label and kept texts sit left of the journal
    # Ø's witness line and over the journal's outline; the gear data dropped
    # to the lower left, between the datum A box (bottom 0.140) and the
    # border (0.0127).
    journal_line = drawing.SIDE_KEEP["JournalDia"][0]
    journal_top = drawing._sheet_y(spec.JOURNAL_DIA / 2.0)
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    assert center[0] + crop < journal_line
    assert center[1] - crop > 0.193
    for x, y in drawing.DETAIL_KEEP.values():
        assert x < journal_line - 0.005 and y > journal_top + 0.005
    assert drawing.DETAIL_LABEL_XY[0] + 0.030 < center[0] - crop
    gear_top = drawing.GEAR_DATA_XY[1]
    lines = len(spec.GEAR_DATA.splitlines())
    assert gear_top < 0.140 - 0.010
    assert gear_top - lines * 1.4 * drawing.GEAR_DATA_CHAR_HEIGHT > 0.0127
    # The tool end's texts stand outside the crop.
    for name in ("FlatEnd", "FlatToolRadius"):
        assert math.dist(drawing.DETAIL_KEEP[name], center) > crop, name


def test_overall_reference_runs_on_the_last_row_clear_of_the_gear_data() -> None:
    # Its rear witness line drops past the gear data block (right edge
    # ~0.0732 on the baseline sheet) to the last row, inside the border.
    x, y = drawing.SIDE_KEEP["OverallLength"]
    assert drawing.REAR_X - 0.0732 >= 0.003
    assert y == drawing._ROW_Y[5] > 0.0127 + 0.005
    assert drawing.REAR_X < x < drawing.TIP_X


def test_tooth_space_note_lands_low_right_away_from_the_span() -> None:
    # Baseline: from the upper right the note's leader crossed the span's
    # bisector and witness lines; the REFERENCE ROOT dimension is gone (the
    # root prints in the gear data).
    x, y = drawing.TOOTHSPACE_NOTE_XY
    assert drawing.TOOTH_SPACE_GAP_INDEX == 9
    assert y < drawing.FRONT_CENTER[1] - drawing.HALF_OD - 0.010
    assert x > drawing.TIP_X + 0.030 and x + 0.082 < 0.4191


def test_tip_chamfer_callout_ends_short_of_the_tooth_space_leader() -> None:
    # Farm run 20261031T205208603Z: the one-line callout ran [293.4, 357.3] mm
    # at y 140.9..144.5 and the note's leader, (329.3, 113.6) -> (342.1,
    # 150.2) mm, ran 3.78 mm through it.  Same character width, two lines.
    char_w = (0.3573 - 0.2934) / len("CHAMFER 45 DEG TO MINOR")
    lines = drawing.TIP_CHAMFER_NOTE.splitlines()
    assert " ".join(lines) == spec.TIP_CHAMFER_CALLOUT and len(lines) == 2
    right = drawing.CHAMFER_NOTE_XY[0] + max(map(len, lines)) * char_w
    (x0, y0), (x1, y1) = (0.3293, 0.1136), (0.3421, 0.1502)
    # The anchor is the text's top left; the leader leans right as it rises,
    # so its x at the callout's bottom row is the nearest it comes.
    bottom = drawing.CHAMFER_NOTE_XY[1] - len(lines) * 0.0045
    leader_x = x0 + (bottom - y0) * (x1 - x0) / (y1 - y0)
    assert right + 0.003 < leader_x
    # Negative control: the old single line reaches past the leader.
    assert drawing.CHAMFER_NOTE_XY[0] + 23 * char_w > leader_x


def _dia_block(name: str) -> tuple[float, float, float, float, float]:
    """(line x, left, right, bottom, top) of a vertical Ø text and its
    one-line above callout: left of the view's centre it hangs right of its
    line, else left; the block runs 7.3 mm under the keep to the callout's
    row 8.7 mm over it (run 20261031T205208603Z, draw_dt_cone_gear_shaft)."""
    x, y = drawing.SIDE_KEEP[name]
    char_w = drawing.ABOVE_CALLOUT_CHAR_WIDTH
    width = len(drawing.DIMENSION_CALLOUTS_ABOVE[name]) * char_w
    left, right = (x, x + width) if x < drawing.SIDE_CENTER[0] else (x - width, x)
    return x, left, right, y - 0.0073, y + 0.0087 + 0.0036


def test_vertical_dia_shoulders_cross_no_other_dia_line() -> None:
    # Run 20261031T205208603Z: the journal's shoulder (240.6 -> 136.3 mm at y
    # 182.2) crossed the core's and the relief's lines.  Every above callout
    # prints on one line; no Ø line rises through another's block, no two
    # blocks overlap, and the blocks stay clear of detail B and the border.
    above = drawing.DIMENSION_CALLOUTS_ABOVE
    assert all("\n" not in text for text in above.values())
    names = ("JournalDia", "OutsideDia", "CoreDia", "ReliefDia")
    blocks = {name: _dia_block(name) for name in names}
    feature_r = {
        "JournalDia": spec.JOURNAL_DIA,
        "OutsideDia": spec.OUTSIDE_DIA,
        "CoreDia": spec.CORE_DIA,
        "ReliefDia": spec.RELIEF_DIA,
    }
    for name, (line_x, _l, _r, bottom, _t) in blocks.items():
        line_bottom = drawing._sheet_y(feature_r[name] / 2.0)
        for other, (_x, left, right, o_bottom, o_top) in blocks.items():
            if other == name:
                continue
            crosses_x = left - 0.002 < line_x < right + 0.002
            crossed = crosses_x and o_bottom < bottom and o_top > line_bottom
            assert not crossed, (name, other)
    for a, b in itertools.combinations(names, 2):
        _, al, ar, ab, at = blocks[a]
        _, bl, br, bb, bt = blocks[b]
        assert ar < bl or br < al or at + 0.0005 < bb or bt + 0.0005 < ab, (a, b)
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    for _x, left, _r, _b, top in blocks.values():
        assert left > center[0] + crop + 0.002
        assert top < 0.2667 - 0.003
    # Negative control: the run's journal row and three-line run cross the
    # core's line.
    char_w = drawing.ABOVE_CALLOUT_CHAR_WIDTH
    run_right = drawing.SIDE_KEEP["JournalDia"][0] + 38 * char_w
    assert run_right > drawing.SIDE_KEEP["CoreDia"][0]


def test_core_frame_stands_in_detail_b_clear_of_every_dia_line() -> None:
    # Main and run 20261031T233549214Z: from over the thread blank the core
    # frame's leader (240.2, 172.0) -> (229.5, 167.3) mm crossed the relief
    # Ø's line at x 238.6; in detail B it reaches the core from the right.
    assert drawing.CONTROL_VIEWS == {
        "core_total_runout": "detail",
        "front_neck_total_runout": "detail",
    }
    landing, (frame_x, frame_top) = drawing.CONTROL_ATTACHMENTS["core_total_runout"]
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    # On the core's round top, behind its step, inside the crop.
    assert -spec.FRONT_RELIEF_WIDTH > drawing.CORE_LANDING_Z_MM
    assert landing[1] == pytest.approx(drawing._detail_xy(0.0, spec.CORE_DIA / 2.0)[1])
    assert math.dist(landing, center) < crop - 0.0005
    # The neck Ø's line rises left of the leader, which descends from the
    # shoulder on the box's left.
    assert landing[0] > drawing.DETAIL_KEEP["FrontReliefDia"][0] + 0.003
    shoulder_x = frame_x - drawing._FRAME_SHOULDER
    mid = frame_top - drawing._FRAME_HEIGHT / 2.0
    assert shoulder_x > landing[0] and mid > landing[1]
    # The box stands right of the crop, left of the relief's block, over
    # the journal's, and under the border.
    assert frame_x - drawing._FRAME_SHOULDER > center[0] + 0.020
    assert frame_x + drawing._FRAME_WIDTH < _dia_block("ReliefDia")[1] - 0.002
    assert frame_top - drawing._FRAME_HEIGHT > _dia_block("JournalDia")[4] + 0.010
    assert frame_top < 0.2667 - 0.004
    # Negative control: the side view's frame over the thread blank put its
    # shoulder right of the relief's line and its landing left of it.
    relief_x = drawing.SIDE_KEEP["ReliefDia"][0]
    assert drawing.CORE_END_X < relief_x < drawing.THREAD_END_X + 0.0003


def test_run_233549_text_clears_the_border_lines_and_labels() -> None:
    # The neck Ø's one line hangs left of its keep at 2.75 mm a character
    # (36 characters read [7.0, 106.1] mm): it starts inside the border.
    # Owner ruling r8: LIMITS (stacked, one value wide) with the MAX job on
    # the value's line and the MIN job in the row under it.
    char_w = (0.1061 - 0.0070) / 36
    keep_x = drawing.DETAIL_KEEP["FrontReliefDia"][0]
    suffix = drawing.DIMENSION_SUFFIXES["FrontReliefDia"]
    text = f"\N{DIAMETER SIGN}3.95{suffix}"
    assert keep_x - len(text) * char_w > 0.0127 + 0.005
    row = drawing.DIMENSION_CALLOUTS_BELOW["FrontReliefDia"]
    assert len(row) <= len(text)  # centred under the wider value line
    assert keep_x - 36 * char_w < 0.0127
    # Negative control: both jobs on the value's one line run past the border.
    one_line = f"\N{DIAMETER SIGN}3.95 {' '.join(drawing.NECK_DIA_JOBS)}"
    assert keep_x - len(one_line) * char_w < 0.0127
    # The corner R's 23.5 mm text, centred on its keep, ends short of the
    # crop circle at its own height (run: the circle crossed its last letter).
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    x, y = drawing.DETAIL_KEEP["FrontCornerRadius"]
    low = y - 0.0019
    circle_x = center[0] - math.sqrt(crop**2 - (low - center[1]) ** 2)
    assert x + 0.01175 < circle_x - 0.002
    assert x + 0.004 + 0.01175 > circle_x - 0.002  # the run's keep
    # The mark's "B" (2 mm wide) stands between the face width's rear
    # witness line and the tooth-tip Ø's lower arrow, 2 mm clear of each.
    bx = drawing.PARENT_LETTER_XY[0]
    assert drawing.PINION_REAR_X + 0.002 < bx
    assert bx + 0.002 + 0.002 < drawing.SIDE_KEEP["OutsideDia"][0] - 0.0004 - 0.002


def test_run_004958_journal_finish_stands_clear() -> None:
    # The finish lands on the journal's lower outline, mid-left, where no
    # tooth, line or text is near (machinist review r5: in the end view it
    # landed where the journal circle meets the teeth).
    px, py = drawing.JOURNAL_FINISH_PICK
    assert py == pytest.approx(drawing._sheet_y(-spec.JOURNAL_DIA / 2.0))
    assert drawing.REAR_X < px < drawing.PINION_REAR_X
    # The symbol (V tip at its position, ~16.7 mm wide, text ~10.3 mm over
    # the tip; its leader runs 6.35 mm level toward the landing) stands
    # under the outline, right of the rear witness line and left of the
    # journal Ø's lower arrow and the 40.938 text.
    sx, sy = drawing.JOURNAL_FINISH_SYMBOL
    assert sy + 0.0103 < py - 0.002
    assert sx - 0.0064 > drawing.REAR_X + 0.002
    assert sx - 0.0022 + 0.0167 < drawing.SIDE_KEEP["JournalDia"][0] - 0.002
    assert sx - 0.0022 + 0.0167 < drawing.SIDE_KEEP["JournalLength"][0] - 0.0085 - 0.002


def test_run_022045_flat_prints_in_the_tip_end_view_clear_of_its_neighbours() -> None:
    # Machinist review r7: in the side view the flat's line ran over the
    # #8-32 thread, level with the thread's lower edge, and read as the
    # thread's radius.  It prints in the end view from the tip instead.
    assert "FlatToAxis" in drawing.END_KEEP and "FlatToAxis" not in drawing.SIDE_KEEP
    x, y = drawing.END_KEEP["FlatToAxis"]
    cx, cy = drawing.FRONT_CENTER
    flat_y = cy - spec.CORE_FLAT_FROM_AXIS * drawing._S / 1000.0
    # The line stands right of the tooth tips.  The rows stay within 12
    # characters; the block hangs right of the line (32.8 mm, from 12.8 mm
    # under the keep to 12.9 mm over it in run 20261101T022045634Z).
    assert x > cx + drawing.HALF_OD + 0.003
    assert max(map(len, drawing.COLLAR_SLIDING_FIT.splitlines())) <= 12
    # Its top stands under the flat's arrow, its bottom over the tooth-space
    # note (top 112.4 mm), its right end inside the border (419.1 mm).
    assert y + 0.0129 < flat_y - 0.002
    assert y - 0.0128 > 0.1124 + 0.005
    assert x + 0.0328 < 0.4191 - 0.005
    # The bearing note's leader passes over the upper arrow's stub (6.3 mm
    # over centre); test_run_035809_shop_notes_land_on_their_features.


def _front_view_point(radius_mm: float, model_deg: float) -> tuple[float, float]:
    """Sheet point of a model point on F in the mirrored front end view."""
    cx, cy = drawing.FRONT_CENTER
    r = radius_mm * drawing._S / 1000.0
    angle = math.radians(model_deg)
    return cx - r * math.cos(angle), cy + r * math.sin(angle)


def test_run_035809_shop_notes_land_on_their_features() -> None:
    # Machinist review r8: the edge-break and bearing notes sat in a free
    # block; each now leaders to the feature it names in the front end view.
    pitch = 360.0 / spec.TEETH
    tooth_deg = drawing.TOOTH_EDGE_TOOTH * pitch
    gap_deg = (0.5 + drawing.TOOTH_SPACE_GAP_INDEX) * pitch  # the toothspace gap
    assert (tooth_deg - gap_deg) % pitch == pytest.approx(pitch / 2)
    tip = _front_view_point(spec.OUTSIDE_DIA / 2.0, tooth_deg)
    cx, cy = drawing.FRONT_CENTER
    # Upper right, clear of the centre mark's arms (to 13.6 mm out).
    assert tip[0] > cx + 0.005 and tip[1] > cy + 0.010
    char_w, pitch_y = 0.0026, 0.0045
    lines = drawing.TOOTH_EDGE_LEADER_NOTE.splitlines()
    x, top = drawing.TOOTH_EDGE_NOTE_XY
    bottom = top - len(lines) * pitch_y
    iso_bottom = 0.2025  # run 20261101T035809796Z's isometric outline
    # The anchor is 1 mm over the first line's 3.5 mm letters.
    assert top - 0.001 < iso_bottom - 0.003
    assert x + max(map(len, lines)) * char_w < 0.4191 - 0.005
    assert bottom > tip[1] + 0.010 and x > tip[0]
    # The bearing note lands on F's annulus, between the core and the root,
    # under the edge-break note and right of the gear.
    r = drawing.BEARING_LANDING_RADIUS_MM
    assert spec.CORE_DIA / 2.0 + 0.2 < r < spec.ROOT_DIA_EXACT_MIN / 2.0 - 0.2
    landing = _front_view_point(r, drawing.BEARING_LANDING_DEG)
    bx, btop = drawing.BEARING_NOTE_XY
    blines = spec.BEARING_FACE_NOTE.splitlines()
    bbottom = btop - len(blines) * pitch_y
    assert btop < bottom - 0.003
    assert bx + max(map(len, blines)) * char_w < 0.4191 - 0.005
    # Attached at the note's lowest line, its leader still clears the
    # flat's upper arrow stub (x 353.5, 6.3 mm over centre) by 2 mm.
    stub_x = drawing.END_KEEP["FlatToAxis"][0]
    stub_top = cy + 0.0063
    attach_y = bbottom + 0.00175
    slope = (attach_y - landing[1]) / (bx - landing[0])
    at_stub = landing[1] + (stub_x - landing[0]) * slope
    assert landing[0] < stub_x < bx
    assert at_stub > stub_top + 0.002
    assert landing[1] > cy + 0.002  # over the centre mark's level arm


def test_run_035809_detail_b_function_rows_stand_clear() -> None:
    # Machinist review r8: the neck width and the D-flat tool's end state
    # their functions as rows under their values.  Each block stacks its
    # value and rows over its dimension line, centred on the keep: rows
    # push the line down and the value up by half a 5.5 mm row each (run
    # 20261101T035809796Z: the tool end's 8 mm limits ran from its line at
    # keep - 4.5 mm; the one-row width's line stood 2.8 mm under its keep and
    # the journal length's, with two rows, 8.3 mm under its keep).
    row, char_w = 0.0055, 0.0026
    center, crop = drawing.DETAIL_CENTER, drawing.DETAIL_CROP_RADIUS
    below = drawing.DIMENSION_CALLOUTS_BELOW
    fx, fy = drawing.DETAIL_KEEP["FlatEnd"]
    flat_rows = below["FlatEnd"].splitlines()
    flat_line = fy - 0.0045 - len(flat_rows) * row / 2
    flat_top = fy + 0.0035 + len(flat_rows) * row / 2
    # Its line stays over the end view's teeth (top 0.1735) and the
    # journal's outline (0.169); its limits' right end (~26 mm right of the
    # keep) stands outside the crop; its rows end short of F's witness line.
    assert flat_line >= 0.1735 - 1e-9
    assert math.dist((fx + 0.026, flat_top), center) > crop + 0.002
    assert fx + max(map(len, flat_rows)) * char_w / 2 < drawing._F_DETAIL_X - 0.003
    wx, wy = drawing.DETAIL_KEEP["FrontReliefWidth"]
    width_rows = below["FrontReliefWidth"].splitlines()
    width_line = wy - 0.0028 - len(width_rows) * row / 2
    width_top = wy + 0.0007 + len(width_rows) * row / 2
    half = max(len(r) for r in width_rows) * char_w / 2
    # Over the tool end's outer arrow (on its line), right of the step's
    # witness line, left of the journal Ø's line and under the crop.
    assert width_line > flat_line + 0.003
    assert wx - half > drawing._STEP_X + 0.003
    assert wx + 0.0071 < drawing.SIDE_KEEP["JournalDia"][0] - 0.005
    left = wx - half
    crop_bottom = center[1] - math.sqrt(crop**2 - (left - center[0]) ** 2)
    assert width_top < crop_bottom - 0.003
    # The two blocks stand side by side, the tool end's left of F.
    assert fx + 0.026 < left - 0.005


def test_flat_reference_sketch_carries_the_printed_flat_on_the_front_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = stub_seat(monkeypatch, part, keep=("_flat_end_view_reference",))
    seat.check.side_effect = lambda _label, result: result
    adapter = offline_adapter()
    adapter.add_centerline.return_value = "Line1"
    asyncio.run(part._flat_end_view_reference(adapter))

    assert seat._create_sketch.call_args.args[1] == "Front"
    h, station = spec.CORE_FLAT_FROM_AXIS, part.FLAT_WITNESS_STATION
    # One construction line on the flat, from under the axis out to the
    # witness on model -X: the tip-end view mirrors X, so it shows right,
    # toward the dimension line.  The witness lies on the flat inside the
    # core circle and outside the thread blank's.
    assert adapter.add_centerline.await_args.args == (-station, -h, 0.0, -h)
    assert spec.THREAD_BLANK_DIA / 2.0 < math.hypot(station, h) < spec.CORE_DIA / 2.0
    constraints = [call.args for call in adapter.add_sketch_constraint.await_args_list]
    assert constraints == [
        ("Line1", None, "horizontal"),
        ("Line1.end", "origin", "vertical_points"),
    ]
    dimensions = [call.args[1:5] for call in seat.dimension_between.await_args_list]
    assert dimensions == [
        ("Line1.start", "origin", "horizontal_distance", station),
        ("Line1.start", "origin", "vertical_distance", h),
    ]
    # The printed one is driven by the cut's own CoreFlat global.
    records = [call.args for call in seat.SketchDims.return_value.record.call_args_list]
    assert records == [("FlatWitnessStation",), ("FlatToAxis", '"CoreFlat"')]
    names = [name for name, _args, _kwargs in seat.mock_calls]
    assert names.index("name_last_feature") < names.index("blank_reference_sketches")
    assert seat.name_last_feature.call_args.args[1] == "CoreFlatReference"
    assert seat.blank_reference_sketches.call_args.args[1] == ("CoreFlatReference",)


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
            "_set_dimension_suffixes", "set_reference_dimension",
        ):
            monkeypatch.setattr(drawing, name, self._recorder(name))
        monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
        # Each stand-in annotation is its dimension's name.
        monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation)
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
        # A projected model point reads back as its own (x, y), in metres.
        monkeypatch.setattr(
            drawing,
            "model_point_in_view",
            lambda _adapter, _view, point, *, label: (point[0], point[1]),
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
        return list(drawing.DETAIL_KEEP)

    def _curate(self, _adapter, view, *, keep, view_label, dimensions_by_feature):
        self.calls.append(("curate_view_dimensions", view_label))
        return list(keep)

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
    # detail must import its five before the side view's targeted import;
    # the mark circle goes on after every side-view pick.
    import asyncio

    seat = _BuildRecorder(monkeypatch, tmp_path)
    assert asyncio.run(drawing.build(seat.adapter)) == {}
    assert seat.index("_placed_detail_view") < seat.index(
        "_dimension_then_crop_detail", "detail"
    ) < seat.index("curate_view_dimensions", "side")
    frames = [which for name, which in seat.calls if name == "add_feature_control_frame"]
    assert frames == ["core_total_runout", "front_neck_total_runout"]
    # Both frames stand in detail B (the core's side-view leader crossed the
    # relief Ø's line).
    assert seat.frame_views == ["detail", "detail"]
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
    pitch = 2.0 * math.pi / spec.TEETH
    gap = math.pi / spec.TEETH + drawing.TOOTH_SPACE_GAP_INDEX * pitch
    assert callout["rotate_rad"] == pytest.approx(gap)
    assert callout["axial_station_mm"] == 0.0
    ((control, _kwargs),) = seat.made["require_source_control"]
    assert control == (spec.TOOTH_SPACE_CALLOUT_PROPERTY, spec.TOOTH_SPACE_CALLOUT)
    notes = [args[1] for args, _kwargs in seat.made["add_property_linked_note"]]
    assert notes == ["Gear Data"]
    # Mate callouts above the vertical Ø texts, below the horizontal ones.
    made = seat.made
    callouts = {
        kwargs["location"]: args[2] for args, kwargs in made["set_dimension_callouts"]
    }
    assert callouts == {
        "above": drawing.DIMENSION_CALLOUTS_ABOVE,
        "below": drawing.DIMENSION_CALLOUTS_BELOW,
    }
    references = {
        args[1]: kwargs["diameter"] for args, kwargs in made["set_reference_dimension"]
    }
    assert references == drawing.REFERENCE_DIMENSIONS
    # The thread and the tip chamfer each carry one attached callout; the
    # two shop notes lead to a tooth tip and to F in the front end view.
    attached = seat.made["add_attached_note"]
    texts = [kwargs["text"] for _args, kwargs in attached]
    assert texts == [
        spec.THREAD_CALLOUT,
        drawing.TIP_CHAMFER_NOTE,
        drawing.TOOTH_EDGE_LEADER_NOTE,
        spec.BEARING_FACE_NOTE,
    ]
    (tooth_args, tooth), (bearing_args, bearing) = attached[2:]
    assert tooth_args[1].name == bearing_args[1].name == "*Back"
    angle = drawing.TOOTH_EDGE_TOOTH * 2.0 * math.pi / spec.TEETH
    tip_r = spec.OUTSIDE_DIA / 2000.0
    tip = (tip_r * math.cos(angle), tip_r * math.sin(angle))
    assert tooth["entity_xy"] == pytest.approx(tip)
    assert tooth["note_xy"] == drawing.TOOTH_EDGE_NOTE_XY
    # F is picked at its landing in the front end view, the tooth note's way.
    assert bearing["entity_type"] == "FACE"
    assert "entity" not in bearing and "leader_attach_xy" not in bearing
    face = math.radians(drawing.BEARING_LANDING_DEG)
    face_r = drawing.BEARING_LANDING_RADIUS_MM / 1000.0
    face_point = (face_r * math.cos(face), face_r * math.sin(face))
    assert bearing["entity_xy"] == pytest.approx(face_point)
    assert bearing["note_xy"] == drawing.BEARING_NOTE_XY
    # The journal's finish lands on the journal's own side-view silhouette,
    # not on the end view's circle among the teeth.
    [(finish_args, finish)] = seat.made["add_surface_finish"]
    assert finish["label"] == "journal finish"
    assert finish_args[1].name == "*Right"
    assert finish["entity_type"] == "SILHOUETTE"
    assert finish["edge_xy"] == drawing.JOURNAL_FINISH_PICK
    assert finish["leader_attach_xy"] == drawing.JOURNAL_FINISH_PICK


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
    ("module_name", "volume_check", "pattern", "cut_depth", "cut_drive"),
    [
        (
            "build_pd_transgear_knob_shaft", "_native_volume_check", "pattern_stock_feature",
            "FACE_WIDTH", '"FaceWidth"',
        ),
        (
            "build_pd_transgear_feed_pinion", "check_one_solid_body_volume", "pattern_about_z",
            "FULL_DEPTH", '"FullDepth"',
        ),
    ],
)
def test_straight_stock_pass_bosses_the_blank_then_cuts_one_patterned_gap(
    monkeypatch: pytest.MonkeyPatch, module_name: str, volume_check: str, pattern: str,
    cut_depth: str, cut_drive: str,
) -> None:
    module = importlib.import_module(module_name)
    seat = stub_seat(monkeypatch, module, keep=("_straight_stock_gaps",))
    seat.placed_ground_curve.side_effect = (
        lambda _adapter, _segment, _phase: f"Curve{seat.placed_ground_curve.call_count}"
    )
    seat.name_last_feature.side_effect = lambda _adapter, name: name
    adapter = offline_adapter()
    seat.attach_mock(adapter, "adapter")
    jobs: list[tuple[object, str]] = []
    asyncio.run(module._straight_stock_gaps(adapter, jobs))

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
    # A blind boss of the face width, then a blind cut (the knob's through
    # the whole face, #2034; the feed pinion's to its full depth), both from
    # the sketch plane (F): one direction, solid, merged, each result checked.
    boss = adapter.create_extrusion.await_args.args[0]
    cut = adapter.create_cut_extrude.await_args.args[0]
    assert (boss.depth, cut.depth) == (module.FACE_WIDTH, getattr(module, cut_depth))
    assert jobs[-1][1] == cut_drive
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
    # The overall witness hangs off the tip face's top corner.
    assert any(c[2] == "coincident" and str(c[1]).endswith(".end") for c in constraints)
    dimensions = [call.args for call in adapter.add_sketch_dimension.await_args_list]
    assert (front, None, "radial", radius) in dimensions


def test_build_cuts_no_endcut_and_checks_the_full_face_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # #2034: the straight full-face pass is the only tooth cut; no rear
    # stock-disk endcut, its witnesses, globals or limits remain.
    for retired in ("_stock_cutter_endcut", "author_cutter_endcut", "_runout_max_limit"):
        assert not hasattr(part, retired), retired
    seat = stub_seat(
        monkeypatch, part,
        spy=("_stud_profile", "_journal_profile", "_revolve_profile"),
    )
    seat._straight_stock_gaps.return_value = part.ToothedDisc(
        1000.0, ("StraightToothGap", "StraightToothPattern")
    )
    seat._cut_core_flat.side_effect = lambda _adapter, _jobs, volume: volume
    seat._native_volume_check.side_effect = (
        lambda _adapter, _label, lower, upper, _allowance: (lower + upper) / 2.0
    )
    seat._native_arc.side_effect = lambda _adapter, label, *_points: label
    adapter = offline_adapter()
    seat.attach_mock(adapter, "adapter")
    asyncio.run(part.build(adapter))

    names = [name for name, _args, _kwargs in seat.mock_calls]
    assert names.index("_straight_stock_gaps") < names.index("_stud_profile")
    assert names.index("_stud_profile") < names.index("_journal_profile")
    # The flat's printed reference sketch follows the span, before the
    # rebuild that precedes the drive equations.
    assert names.index("author_span") < names.index("_flat_end_view_reference")
    assert names.index("_flat_end_view_reference") < names.index("force_rebuild")
    assert "pattern_stock_feature" not in names
    globals_set = [args[1] for name, args, _kwargs in seat.mock_calls if name == "set_global"]
    assert "FaceWidth" in globals_set
    assert not {"FullDepth", "CutterRunoutMax"} & set(globals_set)
    prefixed = [args[2] for name, args, _kwargs in seat.mock_calls if name == "set_dimension_prefix"]
    assert not {"FullDepth", "CutterRunout"} & set(prefixed)
    assert prefixed == ["FlatEnd"]  # no REFERENCE ROOT: the root is gear data
    (saved,) = [args for name, args, _kwargs in seat.mock_calls if name == "save_simplified_part"]
    assert saved[2] == ("StraightToothGap", "StraightToothPattern")
    # The stud sketch keeps two construction witnesses: the tooth-tip blank
    # and the overall length from the tip face's top corner to the rear face.
    witnesses = [call.args for call in adapter.add_line.await_args_list]
    tip_corner_y = part._R_BLANK - part.TIP_CHAMFER
    assert witnesses == [
        (0.0, part.OUTSIDE_DIA / 2.0, -part.FACE_WIDTH, part.OUTSIDE_DIA / 2.0),
        (part.TIP_STATION, tip_corner_y, -part.REAR_END_Z, tip_corner_y),
    ]
    assert -part.REAR_END_Z == pytest.approx(part.TIP_STATION - part.OVERALL_LENGTH)
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
