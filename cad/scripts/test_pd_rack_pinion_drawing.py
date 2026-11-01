"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

import asyncio
import importlib
import math
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import build_pd_rack_pinion as part
import draw_pd_rack_pinion as drawing
import pd_rack_pinion_spec as spec
import pd_transgear_feed_pinion_spec as feed_spec
import pd_transgear_disc_hub_geometry as hub_geometry
import pd_vn_transgear_disc_screw_spec as disc_screw
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import estimate_text_box
from _printed_tolerance import printed_band_mm
from paper_drive_stock_inspection import span_contact_points_mm
from _test_stubbed_build import offline_adapter, stub_seat


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-rack-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-rack-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-rack-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["pd_rack_pinion"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_is_kept_once_with_part_authored_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.RIGHT_KEEP]
    assert sorted(kept) == sorted(marked) == [
        "BoreDia", "FaceWidth", "OutsideDia", "ToothSpan"
    ]
    # Bore and blank print four places, the face three (inch sheet).
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "FaceWidth": 3,
        "OutsideDia": 4,
        "BoreDia": 4,
        "ToothSpan": 4,
    }
    assert "draw_pd_rack_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS",
        ("GearBlankProfile", "OutsideDia"): "*deviations(OUTSIDE_DIA_BAND)",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_the_disc_prints_no_tap_position() -> None:
    """R9-9: the taps are transferred from the MHA-PD-17 flange at assembly."""
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert not any("Tap" in name or "BoltCircle" in name for name in marked)
    assert "DiscTaps" not in spec.DRAWING_DIMENSIONS


def test_taps_sit_on_the_flange_bolt_circle() -> None:
    assert spec.TAP_CENTRES == hub_geometry.screw_centres()
    assert spec.TAP_COUNT == hub_geometry.SCREW_COUNT == 3
    for (x, y), angle in zip(
        spec.TAP_CENTRES, hub_geometry.SCREW_ANGLES_DEG, strict=True
    ):
        assert math.hypot(x, y) == pytest.approx(hub_geometry.BOLT_CIRCLE_DIA / 2.0)
        assert math.degrees(math.atan2(y, x)) % 360.0 == pytest.approx(angle)


def test_disc_screw_engages_at_least_one_and_a_half_diameters_worst_case() -> None:
    """R9-47: the MHA-PD-VN-55 tips are cut to fit inside the rear face, so the
    joint (judged in transgear_disc_screw_spec) spends the tap's losses here."""
    assert spec.TAP_SPEC.size == hub_geometry.SCREW_THREAD == "#0-80"
    assert disc_screw.ENGAGEMENT_WORST_D >= spec.ENGAGEMENT_FLOOR_D == 1.5
    assert (
        disc_screw.ENGAGEMENT_WORST
        < disc_screw.ENGAGEMENT_NOMINAL
        < spec.FACE_WIDTH - spec.MOUTH_THREAD_LOSS
    )


def test_the_tap_mouths_lose_only_their_breaks_counted_from_the_drill() -> None:
    """Machinist review of 8b5e1f354 (blocker): full thread starts where a
    mouth's 45° leg meets the tap drill, so the far-side Ø1.8 MAX countersink
    cost 0.305, not the 0.138 counted to the major, and 1.53D printed over
    1.48D.  R9-63: no countersink, a .004 break on each mouth."""
    assert spec.MOUTH_THREAD_LOSS == spec.MOUTH_BREAK_MAX == pytest.approx(0.1016)
    rear = max(
        spec.MOUTH_BREAK_MAX,
        disc_screw.TIP_BELOW_REAR_FACE[1] + disc_screw.CUT_END_BREAK_MAX,
        disc_screw.STOCK_TIP_INSIDE_REAR_MAX + spec.SCREW_PITCH,
    )
    assert rear == pytest.approx(0.3683, abs=1e-4)
    worst = spec.FACE_WIDTH_MIN - spec.MOUTH_BREAK_MAX - rear
    assert disc_screw.ENGAGEMENT_WORST == pytest.approx(worst)
    assert worst == pytest.approx(2.4003, abs=1e-4)
    assert worst / spec.TAP_MAJOR >= spec.ENGAGEMENT_FLOOR_D
    # The old Ø1.7 +0.10/0 countersink, charged to the drill, fell short.
    old_loss = (1.8 - spec.TAP_DRILL_DIA) / 2.0
    assert (spec.FACE_WIDTH_MIN - old_loss - rear) / spec.TAP_MAJOR < 1.5


def test_disc_tap_drill_cuts_a_2b_minor_at_about_80_percent_thread() -> None:
    """The 3/64 (1.191) tap drill for the MHA-PD-VN-55 #0-80 UNF-2B disc taps,
    against ASME B1.1's 2B table: minor 0.0465..0.0514 in, and the
    tap-drill rule %thread = (major - drill) / (1.299038 P)."""
    inch = 25.4
    major, pitch = 0.0600 * inch, inch / 80.0
    minor_2b = (0.0465 * inch, 0.0514 * inch)  # 1.181 .. 1.306
    assert spec.TAP_MAJOR == pytest.approx(major, abs=5e-4)
    assert spec.SCREW_PITCH == pytest.approx(pitch)
    assert spec.TAP_DRILL_DIA == pytest.approx(3.0 / 64.0 * inch, abs=5e-4)
    assert minor_2b[0] <= spec.TAP_DRILL_DIA <= minor_2b[1]
    thread_percent = 100.0 * (major - spec.TAP_DRILL_DIA) / (1.299038 * pitch)
    assert thread_percent == pytest.approx(80.8, abs=0.5)


def test_tap_to_bore_wall_meets_the_target_worst_case() -> None:
    assert spec.TAP_TO_BORE_WALL_WORST >= 2.0
    assert spec.TAP_TO_BORE_WALL_WORST < spec.TAP_TO_BORE_WALL


def test_the_bore_pilots_on_the_hub_spigot_at_every_limit() -> None:
    """The bands the two builds apply (the disc's REAM_H7 bore, the MHA-PD-17
    hub's SHAFT_H spigot) never bind: at the tightest corner, the smallest
    bore over the largest spigot, they meet line on line, and the fit note
    quotes the clearance the limits give."""
    import build_pd_transgear_disc_hub as hub_part
    import pd_transgear_disc_hub_spec as hub

    assert (
        model_toleranced_dimensions(hub_part)[("HubProfile", "SpigotDia")]
        == "*SPIGOT_DIA_DEVIATIONS"
    )
    assert spec.BORE_DIA == hub.SPIGOT_DIA
    bore_lower, bore_upper = spec.BORE_DEVIATIONS
    spigot_lower, spigot_upper = hub.SPIGOT_DIA_DEVIATIONS
    least = (spec.BORE_DIA + bore_lower) - (hub.SPIGOT_DIA + spigot_upper)
    greatest = (spec.BORE_DIA + bore_upper) - (hub.SPIGOT_DIA + spigot_lower)
    assert least >= -1e-9
    assert (least, greatest) == pytest.approx(spec.SPIGOT_DIAMETRAL_CLEARANCE)
    # The disc's float on the spigot feeds the transferred taps' wall.
    assert spec.DISC_OFFSET_MAX == pytest.approx(greatest / 2.0)
    note = spec.BORE_FIT_CALLOUT
    assert "MATE HUB MHA-PD-17 SPIGOT" in note
    printed = re.search(r"\(DIA CLR (\d*\.\d+)-(\d*\.\d+)\)", note)
    assert printed is not None
    assert [float(v) * 25.4 for v in printed.groups()] == pytest.approx(
        [least, greatest], abs=0.5e-4 * 25.4
    )
    assert all(len(line) <= 70 for line in note.splitlines())


def test_the_bore_front_chamfer_clears_the_spigot_corner() -> None:
    """The flange clamps the front face only if the bore's front chamfer
    reaches past the hub's spigot-to-flange corner radius at every limit the
    title block's .XXX row allows."""
    import pd_transgear_disc_hub_spec as hub

    band = printed_band_mm(3, unit="in")
    assert spec.BORE_FRONT_CHAMFER_LIMITS == pytest.approx(
        (spec.BORE_FRONT_CHAMFER - band, spec.BORE_FRONT_CHAMFER + band)
    )
    assert spec.BORE_FRONT_CHAMFER_LIMITS[0] >= hub.CORNER_RADIUS_MAX


def test_thickness_band_is_the_printed_xxx_band() -> None:
    band = printed_band_mm(3, unit="in")
    assert (spec.FACE_WIDTH_MIN, spec.FACE_WIDTH_MAX) == pytest.approx(
        (spec.FACE_WIDTH - band, spec.FACE_WIDTH + band)
    )


def test_tap_callout_carries_both_mouth_breaks_and_transfer() -> None:
    definitions = {5: "", 6: "<hw-thread> - <hw-threadclass> THRU", 7: "", 8: ""}
    updated = drawing.tap_callout_definitions(definitions)
    assert updated[6].startswith("<hw-thread> THRU\n")
    assert updated[6].endswith(spec.TAP_CALLOUT_QUALIFIER)
    assert {k: v for k, v in updated.items() if k != 6} == {5: "", 7: "", 8: ""}
    text = spec.TAP_CALLOUT_QUALIFIER
    assert "CSK" not in text
    printed_break = re.search(r"BREAK EDGE (\d*\.\d+) MAX BOTH SIDES", text)
    assert printed_break is not None
    assert float(printed_break.group(1)) * 25.4 == pytest.approx(spec.MOUTH_BREAK_MAX)
    assert "MHA-PD-17" in text and "MATCH-MARK" in text
    for banned in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert banned not in text.upper()
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""})


def test_gear_data_block_is_what_the_machinist_needs() -> None:
    data = spec.GEAR_DATA
    lower, upper = sorted(spec.SPAN_LIMITS)
    for label, value in (
        ("NUMBER OF TEETH", "150"),
        ("DIAMETRAL PITCH", "48.00"),
        ("PRESSURE ANGLE", "20.0 DEG"),
        ("PITCH DIAMETER (REF)", f"{spec.PITCH_DIA / 25.4:.4f}".lstrip("0")),
        ("WHOLE DEPTH (REF)", f"{spec.WHOLE_DEPTH / 25.4:.4f}".lstrip("0")),
        ("CUTTER", "#1, 135T-RACK"),
        (
            f"SPAN OVER {spec.SPAN_TEETH} TEETH",
            f"{lower / 25.4:.4f}-{upper / 25.4:.4f}".replace("0.", "."),
        ),
        ("MATES WITH", f"KNOB SHAFT MHA-PD-08, {spec.MESH_PINION_TEETH}T"),
    ):
        assert f"{label}:  {value}" in data
    assert len(data.splitlines()) == 9
    assert "CIRCULAR THICKNESS" not in data
    assert "None" not in data
    assert spec.CUTTER_NUMBER == 1
    assert spec.CUTTER_REFERENCE_TEETH == 135 != spec.TEETH == 150
    assert spec.CUTTER_TOOTH_RANGE == (135, None)
    assert part.GEAR_DATA == data
    assert "CERTIFIED" not in data and "PREMISE" not in data
    assert not hasattr(spec, "PROFILE_SHIFT")
    assert not hasattr(spec, "MESH_PINION_PROFILE_SHIFT")
    assert "PROFILE SHIFT" not in data


def test_printed_span_limits_define_every_accepted_translation_corner() -> None:
    from stock_form_cutter import translation_for_tangent_span

    assert spec.SPAN_TEETH == 17
    assert spec.SPAN_LIMITS == pytest.approx((1.0582 * 25.4, 1.0589 * 25.4))
    assert spec.RADIAL_SETTING_LIMITS[0] < 3.959
    assert spec.RADIAL_SETTING_LIMITS[1] > 3.979
    for limit, setting, sign in zip(
        spec.SPAN_LIMITS, spec.RADIAL_SETTING_LIMITS, (-1.0, 1.0), strict=True
    ):
        target = limit + sign * 2.0 * spec._SPAN_GEOMETRY_ERROR
        inverse = translation_for_tangent_span(
            spec.TEETH,
            spec.CUTTER_TEMPLATE,
            target,
            spec.SPAN_TEETH,
            translation_bounds_mm=spec._SPAN_INVERSE_BOUNDS,
        )
        assert inverse == pytest.approx(setting, abs=1e-12)
    assert {profile.radial_translation_mm for profile in spec.manufactured_profiles()} == set(
        spec.RADIAL_SETTING_LIMITS
    )
    for profile in spec.manufactured_profiles():
        a, b = span_contact_points_mm(profile, spec.SPAN_TEETH)
        assert math.dist(a, b) == pytest.approx(profile.tangent_span_mm(spec.SPAN_TEETH))
        assert max(math.hypot(*a), math.hypot(*b)) <= profile.blank_radius_mm
        allowance = 4.0 * profile.geometry_error_bound_mm
        assert spec.SPAN_LIMITS[0] - allowance <= profile.tangent_span_mm(spec.SPAN_TEETH)
        assert profile.tangent_span_mm(spec.SPAN_TEETH) <= spec.SPAN_LIMITS[1] + allowance


def test_finite_blank_cap_uses_the_lowest_printed_span_inverted_translation() -> None:
    from stock_form_cutter import StockFormProfile

    lowest = StockFormProfile(
        150, spec.CUTTER_TEMPLATE, spec.PITCH_DIA / 2.0,
        spec.RADIAL_SETTING_LIMITS[0],
    )
    cap = 2.0 * lowest.support_radius_max_mm
    assert spec.SUPPORT_OUTSIDE_DIA_MM == pytest.approx(cap)
    assert spec.OUTSIDE_DIA == pytest.approx(3.1655 * 25.4)
    assert spec.OUTSIDE_DIA + spec.OUTSIDE_DIA_BAND[0] < cap
    # Standard actual-N OD would require unsupported upper-tip continuation.
    standard_od = (spec.TEETH + 2.0) * spec.MODULE_MM
    assert standard_od > cap
    with pytest.raises(ValueError, match="FINITE"):
        StockFormProfile(150, spec.CUTTER_TEMPLATE, standard_od / 2.0,
                         spec.RADIAL_SETTING_LIMITS[0])


def test_real_finite_corners_preserve_root_web_volume_and_material_land() -> None:
    for profile in spec.manufactured_profiles():
        assert profile.teeth == 150 and profile.template.reference_teeth == 135
        assert profile.root_radius_min_mm < profile.root_radius_max_mm
        assert 2.0 * profile.root_radius_min_mm >= spec.ROOT_DIA_MIN
        assert profile.root_radius_min_mm > hub_geometry.BOLT_CIRCLE_DIA / 2.0
        assert profile.tip_land_mm >= 0.25 * spec.MODULE_MM
        assert profile.support_radius_max_mm - profile.blank_radius_mm > profile.geometry_error_bound_mm
        toothed = (
            math.pi * profile.blank_radius_mm**2
            - profile.teeth * profile.gap_area_mm2
        ) * spec.FACE_WIDTH
        assert toothed > part.V_BORE + part.V_TAPS
        assert profile.gap_area_error_bound_mm2 < profile.gap_area_mm2


def test_native_builder_consumes_one_full_axial_profile_and_physical_inspection() -> None:
    assert part.STOCK_PROFILE is spec.STOCK_PROFILE


def test_single_pin_contacts_every_actual_finite_corner_on_the_running_datum() -> None:
    assert spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM == pytest.approx(0.040 * 25.4)
    from _gear_quality import toothspace_runout_tir_mm

    assert spec.TOOTH_SPACE_RUNOUT_TIR_MM == toothspace_runout_tir_mm() == 0.05
    contacts = spec.tooth_space_gauge_contacts(1.0003)
    assert len(contacts) == len(spec.manufactured_profiles()) == 4
    for profile, contact in zip(spec.manufactured_profiles(), contacts, strict=True):
        assert profile.flank_parameter_min < contact.parameter < profile.flank_parameter_max
        assert contact.flank_point_mm == profile.flank_point(contact.parameter)
        assert contact.root_air_mm > 0.0 and contact.tip_air_mm > 0.0
        assert contact.center_radius_error_bound_mm < spec.TOOTH_SPACE_RUNOUT_TIR_MM
    nominal = spec.tooth_space_gauge_contacts(spec.TOOTH_SPACE_GAUGE_PIN_DIA_MM)
    assert any(a.center_radius_mm != b.center_radius_mm for a, b in zip(
        contacts, nominal, strict=True
    ))
    inspection = spec.TOOTH_SPACE_CALLOUT
    assert part.TOOTH_SPACE_CALLOUT is drawing.TOOTH_SPACE_CALLOUT is inspection
    assert part.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert drawing.TOOTH_SPACE_CALLOUT_PROPERTY == spec.TOOTH_SPACE_CALLOUT_PROPERTY
    assert spec.TOOTH_SPACE_CALLOUT_PROPERTY == "Tooth Space Inspection"
    assert inspection.splitlines()[0] == (
        f"TOOTH SPACE RUNOUT {spec.TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR TO A, "
        "ACCEPT AT CUTTING SETUP"
    )
    # The printed TIR never exceeds the running-fit TIR it controls.
    assert float(spec.TOOTH_SPACE_RUNOUT_TIR_TEXT) * 25.4 <= spec.TOOTH_SPACE_RUNOUT_TIR_MM
    assert len(inspection.splitlines()) == 2
    assert "INDEX" not in inspection
    assert max(map(len, inspection.splitlines())) <= 70
    # The part sheet names only its own datum; the assembled axis is the
    # assembly's transfer step (test_pd_paper_drive_assembly_drawing).
    assert "MHA-" not in inspection and "ASSEMBLED" not in inspection
    # The sheet states the requirement; the method and history stay off it.
    assert not any(word in inspection + spec.GEAR_DATA for word in ("CERTIFIED", "PREMISE"))
    assert not any(word in inspection for word in ("TRANSFER", "LOCK", "MATCH-MARK"))


def test_native_blank_lookup_checks_dispatch_null_before_binding(monkeypatch) -> None:
    model = SimpleNamespace(FeatureByName=lambda _name: None)
    adapter = SimpleNamespace(currentModel=model)

    def bind(value, interface):
        assert value is not None
        assert interface == "IPartDoc"
        return value

    monkeypatch.setattr(part, "_early_bound", bind)
    monkeypatch.setattr(part, "feature_name_by_type", lambda *_args: "Boss-Extrude1")
    with pytest.raises(RuntimeError, match="could not be retrieved"):
        part._rename_gear_blank(adapter)


def test_native_blank_subfeature_is_a_method_and_names_are_properties(monkeypatch) -> None:
    class Feature:
        def __init__(self, name, child=None):
            self._name = name
            self.child = child
            self.getter_calls = 0

        @property
        def Name(self):
            return self._name

        @Name.setter
        def Name(self, value):
            assert type(value) is str
            self._name = value

        def GetFirstSubFeature(self):
            self.getter_calls += 1
            return self.child

    profile = Feature("Sketch1")
    blank = Feature("Boss-Extrude1", profile)
    model = SimpleNamespace(FeatureByName=lambda name: blank if name == blank.Name else None)
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(part, "feature_name_by_type", lambda *_args: "Boss-Extrude1")
    part._rename_gear_blank(adapter)
    assert blank.getter_calls == 1
    assert (blank.Name, profile.Name) == ("GearBlank", "GearBlankProfile")


def test_the_bore_callout_with_its_fit_clears_the_gear_data_and_the_rim() -> None:
    """The fit lines hang under the bore size on its own leader, so they must
    clear the gear data block to the left and the toothed rim to the right."""
    note = dict(advance_ratio=109.7 / (42 * 3.5), line_spacing=16.8 * 25.4 / 72.0 / 3.5)
    data = estimate_text_box(
        spec.GEAR_DATA, anchor=drawing.GEAR_DATA_XY,
        height=drawing.GEAR_DATA_CHAR_HEIGHT, **note,
    )
    size = f"\N{DIAMETER SIGN}{spec.BORE_DIA:.3f} +0.018"
    callout = estimate_text_box(
        "\n".join((size, drawing.DIMENSION_CALLOUTS["BoreDia"])),
        anchor=drawing.FRONT_KEEP["BoreDia"], height=0.0035, reference=5, **note,
    )
    assert data is not None and callout is not None
    assert data.xmin >= 0.0127 and data.ymax <= 0.2667
    assert data.xmax < callout.xmin - 0.002
    corner = (callout.xmax, callout.ymin)  # the corner nearest the rim
    assert math.dist(corner, drawing.FRONT_CENTER) > drawing.HALF_OD + 0.005


def test_tooth_space_control_fits_the_upper_right_note_lane() -> None:
    control = estimate_text_box(
        spec.TOOTH_SPACE_CALLOUT,
        anchor=drawing.TOOTH_SPACE_CALLOUT_XY,
        height=drawing.TOOTH_SPACE_CALLOUT_CHAR_HEIGHT,
        advance_ratio=109.7 / (42 * 3.5),
        line_spacing=16.8 * 25.4 / 72.0 / 3.5,
    )
    assert control is not None
    assert control.xmin >= drawing.FRONT_CENTER[0]
    assert control.xmax <= 0.4191
    assert control.ymax <= 0.2667
    assert control.ymin > drawing.FRONT_CENTER[1] + drawing.HALF_OD + 0.010
    assert control.ymin > drawing.FRONT_KEEP["ToothSpan"][1] + 0.010


def test_stale_native_tooth_space_control_is_refused_before_drawing_creation(
    monkeypatch, tmp_path
) -> None:
    import asyncio

    source = tmp_path / "pd-rack-pinion.SLDPRT"
    source.write_bytes(b"")
    created: list[str] = []

    async def opened(_path):
        return SimpleNamespace(is_success=True, data=None, error=None)

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(
        drawing, "read_required_properties",
        lambda _model, wanted, *, required: {
            key: "TOOTH SPACE RUNOUT 0.10 TIR TO A" for key in wanted
        },
    )
    monkeypatch.setattr(
        drawing, "new_project_drawing", lambda *_a, **_k: created.append("drawing")
    )
    adapter = SimpleNamespace(currentModel=object(), open_model=opened)
    with pytest.raises(RuntimeError):
        asyncio.run(drawing.build(adapter))
    assert created == []


def test_saved_crlf_control_passes_and_a_changed_line_is_refused() -> None:
    """A reopened part reads its property's line breaks back as CRLF (the run
    20261010T001620278Z SLDPRT stores them so); the lines are the control."""
    from paper_drive_stock_drawing import require_source_control

    saved = spec.TOOTH_SPACE_CALLOUT.replace("\n", "\r\n")
    require_source_control(saved, spec.TOOTH_SPACE_CALLOUT, label="rack pinion")
    stale = saved.replace(f"{spec.TOOTH_SPACE_RUNOUT_TIR_TEXT} TIR", ".0039 TIR")
    with pytest.raises(RuntimeError, match="differs from the current specification"):
        require_source_control(stale, spec.TOOTH_SPACE_CALLOUT, label="rack pinion")


def test_tooth_space_gap_index_names_a_real_gap() -> None:
    assert 0 <= drawing.TOOTH_SPACE_GAP_INDEX < spec.TEETH


def _segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def side(p, q, r) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _distance_to_segment(
    point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ab = (b[0] - a[0], b[1] - a[1])
    t = ((point[0] - a[0]) * ab[0] + (point[1] - a[1]) * ab[1]) / (
        ab[0] ** 2 + ab[1] ** 2
    )
    t = min(1.0, max(0.0, t))
    return math.dist(point, (a[0] + t * ab[0], a[1] + t * ab[1]))


def test_tap_leader_lands_on_the_lower_left_tap_and_crosses_no_diameter_line() -> None:
    """19e33c6c2: the tap leader rose across the bore to the upper tap; the
    2026-11-01 review: it crossed the OD's line, and the bore's leader lay
    almost on another diameter line."""
    centre = drawing.FRONT_CENTER
    bolt_r = hub_geometry.BOLT_CIRCLE_DIA / 2000.0
    tap = drawing.TAP_SHEET_CENTER
    assert math.dist(tap, centre) == pytest.approx(bolt_r)
    assert tap[0] < centre[0] and tap[1] < centre[1]
    # The pick lies on the drill circle, off both centre-mark lines.
    pick = drawing.TAP_PICK
    assert math.dist(pick, tap) == pytest.approx(spec.TAP_DRILL_DIA / 2000.0)
    assert min(abs(pick[0] - tap[0]), abs(pick[1] - tap[1])) > 0.0003
    leader = (drawing._TAP_SHOULDER, pick)
    bore_r = spec.BORE_DIA / 2000.0
    assert _distance_to_segment(centre, *leader) > bore_r + 0.002

    def near_side(shoulder, radius):
        """A near-side diameter leader: from its text's shoulder to the rim
        point toward it; no line through the centre."""
        d = math.dist(shoulder, centre)
        return shoulder, (
            centre[0] + (shoulder[0] - centre[0]) * radius / d,
            centre[1] + (shoulder[1] - centre[1]) * radius / d,
        )

    bore = near_side(drawing._BORE_SHOULDER, bore_r)
    blank = near_side(drawing._OD_SHOULDER, drawing.HALF_OD)
    assert set(drawing.NEAR_SIDE_DIAMETERS) == {"BoreDia", "OutsideDia"}
    for a, b in ((leader, bore), (leader, blank), (bore, blank)):
        assert not _segments_cross(*a, *b)
    # Every leader passes the other taps' centre marks (2.5 mm) clear.
    for tap_xy in spec.TAP_CENTRES:
        for sign in (1.0, -1.0):
            mark = (centre[0] + tap_xy[0] / 1000.0, centre[1] + sign * tap_xy[1] / 1000.0)
            for line in (bore, blank, leader):
                if line is leader and math.dist(mark, pick) < 0.002:
                    continue  # the tap's own leader lands on it
                assert _distance_to_segment(mark, *line) > 0.0025


def test_model_and_drawing_consume_the_spec_geometry() -> None:
    assert (part.TEETH, part.DP, part.FACE_WIDTH) == (
        spec.TEETH,
        spec.DIAMETRAL_PITCH,
        spec.FACE_WIDTH,
    )
    assert part.PRESSURE_ANGLE_DEG == spec.PRESSURE_ANGLE_DEG
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.STANDARD_CENTRE_DISTANCE == pytest.approx(
        (spec.TEETH + spec.MESH_PINION_TEETH) * spec.MODULE_MM / 2.0
    )
    assert spec.CENTRE_DISTANCE == pytest.approx(
        spec.STANDARD_CENTRE_DISTANCE + spec.CENTRE_EXTENSION
    )
    assert part.BORE_DIAMETER == spec.BORE_DIA == hub_geometry.SPIGOT_DIA
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": f"{spec.BORE_CALLOUT}\n{spec.BORE_FIT_CALLOUT}",
        "OutsideDia": spec.MESH_CALLOUT_STACKED,
    }
    assert drawing.DIMENSION_CALLOUTS_ABOVE == {"ToothSpan": spec.MESH_CALLOUT}
    assert drawing.RIGHT_DIMENSION_CALLOUTS == {"FaceWidth": spec.FACE_WIDTH_CALLOUT}


def test_part_config_properties() -> None:
    import _config

    config = _config.parts("pd-rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 1


@pytest.mark.parametrize(
    ("module_name", "spec_name", "orientation", "centre", "station", "pin", "gap_phase"),
    [
        # The disc's teeth run its full face width; the front face shows them.
        # build_pd_rack_pinion cuts its gaps with build_stock_form_gear's
        # default bisector phase, half a pitch (pi / N).
        (
            "draw_pd_rack_pinion", "pd_rack_pinion_spec", "*Front", "FRONT_CENTER",
            "FACE_WIDTH", "TOOTH_SPACE_GAUGE_PIN_DIA_MM", math.pi / spec.TEETH,
        ),
        # Run 11: the sleeve's end view looks at the step face, whose run-out
        # gaps are partial depth; the straight pass is full depth at the rear.
        # build_pd_transgear_feed_pinion places its gaps at the inspection phase.
        (
            "draw_pd_transgear_feed_pinion", "pd_transgear_feed_pinion_spec",
            "*Back", "REAR_CENTER", "TOOTH_SPACE_INSPECTION_END_MM",
            "TOOTHSPACE_GAUGE_DIA_MM", feed_spec.TOOTH_SPACE_INSPECTION_PHASE_RAD,
        ),
    ],
)
def test_sheet_calls_out_the_tooth_space_on_its_full_depth_face_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, module_name: str, spec_name: str,
    orientation: str, centre: str, station: str, pin: str, gap_phase: float,
) -> None:
    module = importlib.import_module(module_name)
    owner = importlib.import_module(spec_name)
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"")
    monkeypatch.setattr(module, "SOURCE", source)
    seat = stub_seat(monkeypatch, module)
    if hasattr(module, "_set_tap_callout_text"):
        monkeypatch.setattr(module, "_set_tap_callout_text", MagicMock())
    if hasattr(module, "SHEET_INNER_BORDER"):  # the sleeve reads its notes' extents back
        left, bottom, right, top = module.SHEET_INNER_BORDER
        seat._early_bound.return_value.GetExtent.return_value = (
            left + 0.01, bottom + 0.01, 0.0, right - 0.01, top - 0.01, 0.0
        )
    seat.new_project_drawing.return_value = (MagicMock(), MagicMock())
    seat.place_view.side_effect = lambda _adapter, path, view, x, y, scale: SimpleNamespace(
        path=path, orientation=view, centre=(x, y)
    )
    asyncio.run(module.build(offline_adapter()))

    (callout,) = seat.add_toothspace_callout.call_args_list
    view = callout.args[1]
    assert (view.path, view.orientation, view.centre) == (
        str(source), orientation, getattr(module, centre)
    )
    assert callout.kwargs["axial_station_mm"] == getattr(owner, station)
    assert callout.kwargs["profile"] is owner.STOCK_PROFILE
    assert callout.kwargs["property_name"] == owner.TOOTH_SPACE_CALLOUT_PROPERTY
    # The part's certified gauge pin, seated in the sheet's chosen gap of the
    # part as cut: the gap bisector at the part's phase, a whole number of
    # pitches round, and the note where the sheet's layout put it.
    assert callout.kwargs["actual_pin_diameter_mm"] == getattr(owner, pin)
    pitch = 2.0 * math.pi / owner.TEETH
    assert 0 <= module.TOOTH_SPACE_GAP_INDEX < owner.TEETH
    assert callout.kwargs["rotate_rad"] == pytest.approx(
        gap_phase + module.TOOTH_SPACE_GAP_INDEX * pitch, abs=1e-12
    )
    assert callout.kwargs["note_xy"] == module.TOOTH_SPACE_CALLOUT_XY
    # The callout links the part's own control, checked against the spec first.
    (required,) = seat.require_source_control.call_args_list
    assert required.args[1] == owner.TOOTH_SPACE_CALLOUT
    names = [name for name, _args, _kwargs in seat.mock_calls]
    assert names.index("require_source_control") < names.index("add_toothspace_callout")
