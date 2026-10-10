"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import pytest
import yaml

import _config
import _drawing_leaders
import build_dt_cone_gear as part
import dt_cone_gear_notes as notes
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec as spec
import draw_dt_cone_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
import _drawing_annotation_extent


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["dt_cone_gear"].script == Path(drawing.__file__).resolve()


def test_every_configuration_has_one_complete_sheet_and_native_scale() -> None:
    expected_teeth = tuple(
        range(6, int(_config.machine("gear_train", "fundamental_cone_teeth")) + 1, 6)
    )
    expected_names = tuple(f"T{teeth:03d}" for teeth in expected_teeth)
    assert spec.CONFIGURATION_TEETH == expected_teeth
    assert part.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
    assert drawing.GEAR_SHEET_NAMES == expected_names
    assert drawing.SHEET_NAMES == (*expected_names, notes.CUTTER_DETAIL_SHEET)
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)

    for teeth in expected_teeth:
        name = f"T{teeth:03d}"
        numerator, denominator = drawing.SHEET_SCALES[name]
        drawn_od = drawing.outside_dia_mm(teeth) * numerator / denominator
        # The smallest member is limited by the common configured face width;
        # every view must stay inside the existing useful-size envelope.
        assert 30.0 < drawn_od < 95.0
        assert drawing.rendered_half_od(teeth) == pytest.approx(drawn_od / 2000.0)


def test_part_and_drawing_share_the_complete_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == {
        "BlankDia",
        "FaceWidth",
        "BoreCutDia",
        "BoreAF",
        "BoreFlatClock",
        "ToothThickness",
        "FloorDia",
    }
    for teeth in spec.CONFIGURATION_TEETH:
        views = (
            drawing.front_keep(teeth),
            drawing.right_keep(teeth),
            drawing.bore_view_keep(teeth),
        )
        kept = [name for keep in views for name in keep]
        # Every marked dimension prints exactly once per sheet.
        assert sorted(kept) == sorted(marked)
        # The whole D-bore prints in the bore view, and only there.
        assert set(drawing.bore_view_keep(teeth)) == spec.DRAWING_DIMENSIONS["BoreProfile"]


def test_model_owns_precision_for_every_printed_dimension() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BlankDia": 2,
        # Fewer places would round the faced gear above its derived seat pitch.
        "FaceWidth": 4,
        "BoreCutDia": 3,
        # The AF band is 0.010 wide; three places print both limits exactly.
        "BoreAF": 3,
        "BoreFlatClock": 1,
        "ToothThickness": 3,
        # Narrow floor windows need three places to preserve both limits.
        "FloorDia": 3,
    }
    assert "draw_dt_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


def test_tip_diameter_carries_its_own_mesh_depth_band() -> None:
    # Ordinary undersize-only blank band (user ruling 2026-10-10, cones at
    # ordinary tolerances); T006 keeps its own -0.02 band for the DT6-FORM1
    # relief, written into T006 alone.
    assert spec.BLANK_DIA_BAND == (0.0, -0.05)
    assert spec.blank_dia_band(6) == spec.CUSTOM_SIX_BLANK_DIA_BAND == (0.0, -0.02)
    assert all(spec.blank_dia_band(t) is spec.BLANK_DIA_BAND for t in spec.CONFIGURATION_TEETH if t != 6)
    assert spec.BLANK_DIA_BAND[0] < spec.MODULE_MM / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        '"BlankProfile", "BlankDia", *deviations(BLANK_DIA_BAND)' in source
    )
    assert "_set_configuration_bands(adapter)" in source


def test_face_width_fills_the_seat_pitch_without_crossing_it() -> None:
    # Solid touching stack: twenty gears end to end on SEAT_PITCH centres.
    # The nominal is the seat pitch floored to 4 places, so it never prints
    # longer than the pitch; cone_gear_stack owns the stack's band.
    assert spec.FACE_WIDTH == math.floor(spec.SEAT_PITCH * 1e4) / 1e4
    assert spec.FACE_WIDTH <= spec.SEAT_PITCH < spec.FACE_WIDTH + 1e-4
    assert spec.FACE_WIDTH_BAND == (0.025, -0.025)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Blank", "FaceWidth", *deviations(FACE_WIDTH_BAND)' in source


def test_each_configuration_sheet_carries_its_own_drawing_number() -> None:
    number = str(_config.parts("dt-cone-gear")["number"])
    assert spec.configuration_number(number, 6) == f"{number}-T006"
    assert spec.configuration_number(number, 120) == f"{number}-T120"
    numbers = {spec.configuration_number(number, t) for t in spec.CONFIGURATION_TEETH}
    assert len(numbers) == len(spec.CONFIGURATION_TEETH)
    with pytest.raises(ValueError):
        spec.configuration_number(number, 7)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Number": configuration_number(part_number, teeth)' in source


def test_bore_bands_are_the_current_derived_seat_fit_bands() -> None:
    assert part.BORE_DIA_BAND is spec.BORE_DIA_BAND
    assert spec.BORE_DIA_BAND[0] <= spec.BORE_BAND_FIT_UPPER
    assert spec.BORE_DIA_BAND[0] <= spec.terminal_web_bore_upper_mm()
    assert spec.BORE_DIA_BAND[0] - spec.BORE_DIA_BAND[1] >= 0.02 - 1e-9
    assert spec.BORE_AF_BAND == pytest.approx((0.02, 0.01))
    for teeth in spec.CONFIGURATION_TEETH:
        assert spec.bore_dia_mm(teeth) == pytest.approx(
            dt_cone_gear_shaft_spec.SECTION_DIAS[spec.land_section(teeth)]
        )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"BoreProfile", "BoreCutDia", *deviations(BORE_DIA_BAND)' in source
    assert '"BoreProfile", "BoreAF", *deviations(BORE_AF_BAND)' in source


def test_native_tooth_inspection_reads_the_actual_installed_cutter() -> None:
    # Ordinary +/-0.075 thickness band about the cutter's standard-depth
    # thickness; T006 alone is thin-only (DT6-FORM1 relief clearance).
    assert spec.TOOTH_THICKNESS_BAND == (0.075, -0.075)
    assert spec.tooth_thickness_band(6) == spec.CUSTOM_SIX_TOOTH_THICKNESS_BAND == (0.0, -0.04)
    for teeth in spec.CONFIGURATION_TEETH:
        _upper, lower = spec.tooth_thickness_band(teeth)
        profile = spec.stock_form_profile(teeth)
        assert profile.pitch_tooth_thickness_mm == pytest.approx(spec.tooth_thickness_mm(teeth))
        assert 2.0 * profile.blank_radius_mm == pytest.approx(spec.outside_dia_mm(teeth))
        assert profile.pitch_tooth_thickness_mm + lower > 0.0
        assert part._expected_configuration_volume(teeth) == pytest.approx((
            math.pi * profile.blank_radius_mm**2
            - teeth * profile.gap_area_mm2 - part.bore_area_mm2(teeth)
        ) * spec.FACE_WIDTH)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "*deviations(TOOTH_THICKNESS_BAND)" in source
    assert "FloorDip" not in source
    assert "gear_facts(" not in source
    assert "gap_area_in_disc(" not in source

def test_each_sheet_gets_its_own_actual_cutting_recipe() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth)
        assert data.startswith("GEAR DATA\n")
        assert f"T{teeth:03d}" in data
        assert f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f} DEG" in data
        for physical_recipe in (
            "CUTTER", "TEMPLATE", "TOOL T", "PLUNGE", "WHOLE DEPTH",
            "TOOTH FORM", "BACKLASH WITH MATE", "ROOT RADIAL MIN/MAX", "WEB",
        ):
            assert physical_recipe in data, (teeth, physical_recipe)
        assert ("TROCHOID RELIEF" in data) == (teeth == 6)
        assert notes.CYLINDER_MATE_NUMBER in data
        for obsolete in ("CONTACT RATIO", "RANGE ONLY", "MATCH FLANKS", "LONG ADDENDUM"):
            assert obsolete not in data
        assert len(data.splitlines()) * 0.00351 <= drawing.GEAR_DATA_HEIGHT


def test_native_gap_features_are_distinct_and_preserve_real_template_topology() -> None:
    features = [name for teeth in spec.CONFIGURATION_TEETH for name in part.tooth_features(teeth)]
    assert len(set(features)) == 3 * len(spec.CONFIGURATION_TEETH)
    assert len(part.SIMPLIFIED_FEATURES) == 2 * len(spec.CONFIGURATION_TEETH)
    assert part.SIMPLIFIED_FEATURES_BY_CONFIGURATION == {
        f"T{teeth:03d}": part.tooth_features(teeth)[1:] for teeth in spec.CONFIGURATION_TEETH
    }
    for teeth in spec.CONFIGURATION_TEETH:
        profile = spec.stock_form_profile(teeth)
        core = profile.cut_order_native_segments(
            unit_scale=1.0 / spec.MM_PER_IN, clearance_radius_mm=part.R_CLEAR_MM
        )
        expected_entities = 8 if profile.template.root_radius_mm < profile.template.base_radius_mm else 6
        assert len(core) == expected_entities
        native = part.native_gap_segments(teeth)
        assert [row[0] for row in native] == [segment.name for segment in core]
        for (_name, x, y), segment in zip(native, core, strict=True):
            assert segment.x in x and segment.y in x
            assert segment.x in y and segment.y in y
        if teeth != 6:
            assert profile.template.reference_teeth <= teeth
            assert profile.template.reference_teeth in (12, 17, 21, 26, 35, 55)
        assert all(name.endswith(f"T{teeth:03d}") for name in part.tooth_features(teeth))
        assert profile.contains_material(
            profile.pitch_radius_mm, 0.0, rotate_rad=math.pi / teeth
        ), f"T{teeth:03d} must seed a physical tooth on +X"
        phase = math.pi / teeth
        for (_name, x_expression, y_expression), segment in zip(native, core, strict=True):
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                variables = {"t": t, "cos": math.cos, "sin": math.sin}
                observed = (
                    eval(x_expression, {"__builtins__": {}}, variables),
                    eval(y_expression, {"__builtins__": {}}, variables),
                )
                x, y = segment.point(t)
                expected = (
                    (math.cos(phase) * x - math.sin(phase) * y) / spec.MM_PER_IN,
                    (math.sin(phase) * x + math.cos(phase) * y) / spec.MM_PER_IN,
                )
                assert observed == pytest.approx(expected, abs=1e-12)


def test_root_envelope_is_the_actual_translated_arc_not_a_bisector_circle() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        profile = spec.stock_form_profile(teeth)
        assert spec.floor_radius_min_mm(teeth) == pytest.approx(profile.root_radius_min_mm)
        assert spec.floor_radius_max_mm(teeth) == pytest.approx(profile.root_radius_max_mm)
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert minimum <= 2.0 * profile.root_radius_min_mm + 1e-9
        assert maximum >= 2.0 * profile.root_radius_max_mm - 1e-9
        assert minimum == pytest.approx(round(minimum, 3), abs=1e-12)
        if abs(profile.radial_translation_mm) > 1e-9:
            assert profile.root_radius_min_mm < profile.root_radius_max_mm
    assert drawing.DIMENSION_CALLOUTS["FloorDia"] == "ROOT ENVELOPE"


def test_refused_rows_block_the_complete_native_family(monkeypatch: pytest.MonkeyPatch) -> None:
    visited = []

    def profile(teeth: int) -> object:
        visited.append(teeth)
        if teeth in (6, 18, 120):
            raise ValueError("finite support refused")
        return object()

    monkeypatch.setattr(part, "stock_form_profile", profile)
    with pytest.raises(RuntimeError, match="cutter-native cone family is unqualified") as caught:
        part.require_complete_stock_family()
    assert visited == list(spec.CONFIGURATION_TEETH)
    for teeth in (6, 18, 120):
        assert f"T{teeth:03d}: finite support refused" in str(caught.value)


def test_native_root_readback_measures_the_offcentre_arc(monkeypatch: pytest.MonkeyPatch) -> None:
    from stock_form_cutter import CutterTemplate, StockFormProfile

    template = CutterTemplate(12, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG)
    profile = StockFormProfile(12, template, template.tip_radius_mm + 0.05, 0.1)
    root = next(segment for segment in profile.native_segments(
        unit_scale=1.0, clearance_radius_mm=part.R_CLEAR_MM
    ) if segment.kind == "root_arc")

    z = part.FACE_WIDTH / 1000.0

    class Edge:
        def __init__(self, index: int) -> None:
            angle = (2 * index + 1) * math.pi / profile.teeth
            cosine, sine = math.cos(angle), math.sin(angle)
            self.points = []
            for t in (0.0, 0.5, 1.0):
                x, y = root.point(t)
                self.points.append((cosine * x - sine * y, sine * x + cosine * y))
            self.queries = []

        def GetCurve(self) -> object:
            return object()

        def GetCurveParams2(self) -> tuple[float, ...]:
            (x0, y0), (x1, y1) = self.points[0], self.points[-1]
            return x0 / 1000.0, y0 / 1000.0, z, x1 / 1000.0, y1 / 1000.0, z, 0.0, 1.0

        def GetClosestPointOn(self, x: float, y: float, z: float) -> tuple[float, ...]:
            self.queries.append((x, y, z))
            if x == y == 0.0:
                point = min(self.points, key=lambda point: math.hypot(*point))
            else:
                point = self.points[1]
            return point[0] / 1000.0, point[1] / 1000.0, z, 0.0, 0.0

    class Line:
        """A tooth-flank edge: it runs along the gear axis, never a root."""

        def GetCurve(self) -> object:
            return object()

        def GetCurveParams2(self) -> tuple[float, ...]:
            return 0.004, 0.0, 0.0, 0.004, 0.0, z, 0.0, 1.0

    class Face:
        def __init__(self, z_mm: float, edges: list) -> None:
            self.z, self.edges = z_mm / 1000.0, edges

        def GetBox(self) -> tuple[float, ...]:
            return -0.01, -0.01, self.z, 0.01, 0.01, self.z

        def GetEdges(self) -> list:
            return self.edges

    edges = [Edge(index) for index in range(profile.teeth)]
    flank = type("Flank", (), {"GetBox": lambda self: (-0.01, -0.01, 0.0, 0.01, 0.01, z)})()
    faces = [Face(0.0, []), flank, Face(part.FACE_WIDTH, [Line(), *edges])]
    body = type("Body", (), {"GetFaces": lambda self: faces})()
    monkeypatch.setattr(part, "stock_form_profile", lambda _teeth: profile)
    minimum, maximum, count = part._native_root_envelope_mm(body, teeth=profile.teeth)
    assert count == profile.teeth
    assert minimum == pytest.approx(profile.root_radius_min_mm)
    assert maximum == pytest.approx(profile.root_radius_max_mm)
    assert minimum < maximum
    assert all(len(edge.queries) == 2 for edge in edges)
    # A gap that did not cut through leaves its root off the far face.
    faces[-1].edges.pop()
    with pytest.raises(RuntimeError, match="native root arcs on the exit face"):
        part._native_root_envelope_mm(body, teeth=profile.teeth)


def test_root_envelope_reads_the_body_and_failures_name_their_call() -> None:
    # f68549253: the reopened audit passed the IPartDoc where the reader calls
    # IBody2.GetFaces, and every configuration failed as an anonymous
    # DISP_E_MEMBERNOTFOUND.
    source = inspect.getsource(part._configuration_topology)
    assert "_native_root_envelope_mm(bodies[0], teeth=teeth)" in source
    try:
        part._exit_face(object())
    except AttributeError as exc:
        site = part._failure_site(exc)
    assert '_com_invoke(body, "IBody2", "GetFaces")' in site
    assert "in _exit_face" in site
    assert "_failure_site(exc)" in inspect.getsource(part.assert_saved_configuration_topology)


def test_custom_six_detail_reproduces_complete_finite_core_grinding_curves() -> None:
    from dataclasses import replace

    installed = spec.stock_form_profile(6)
    template = installed.template
    tool = replace(
        installed, blank_radius_mm=template.tip_radius_mm, radial_translation_mm=0.0
    )
    detail = notes.custom_cutter_detail()
    assert template.cutter_number is None
    assert template.name == notes.CUTTER_DETAIL_SHEET == "DT6-FORM1"
    assert drawing.SHEET_NAMES[-1] == notes.CUTTER_DETAIL_SHEET
    assert "CUSTOM GROUND FORM" in detail
    assert "NO UPPER CONTINUATION" in detail
    assert "ROOT ARC; DRUM-TIP TROCHOID RELIEF TO TIF; N6 WORKING INVOLUTE" in detail
    normalized = re.sub(r"\s+", "", detail)
    required = []
    for segment in tool.native_segments(
        unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0
    ):
        if segment.kind in {"root_arc", "relief", "flank"}:
            required.append(segment.kind)
            assert re.sub(r"\s+", "", segment.x) in normalized
            assert re.sub(r"\s+", "", segment.y) in normalized
    assert sorted(required) == ["flank", "flank", "relief", "relief", "root_arc"]
    assert "closing_ray" not in detail
    assert "clearance_arc" not in detail
    assert "STOCK #8" not in detail
    assert max(map(len, detail.splitlines())) <= notes.CUTTER_DETAIL_LINE_CHARS


def test_custom_six_sheet_gives_grind_data_not_equations() -> None:
    """Sheet DT6-FORM1 prints what the toolmaker grinds to (3 places, the
    comparator check at the sheet's own scale), not the model's equations."""
    profile = spec.stock_form_profile(6)
    data = drawing.cutter_grind_data()
    lines = data.splitlines()
    assert lines[0] == "DT6-FORM1 GROUND FORM TOOL, mm"
    assert lines[-1] == "GRIND TO TEMPLATE; CHECK ON OPTICAL COMPARATOR AT 20:1"
    assert "FORM DEPTH (PLUNGE FROM BLANK OD):  1.055" in lines
    assert "TIP ARC (FORMS GEAR ROOT):  R1.100" in lines
    assert "TIF (RELIEF TO INVOLUTE):  R1.531 REF" in lines
    # Chords across the installed gap, which at T=0 IS the ground form:
    # the pitch chord closes on the tool's pitch tooth thickness.
    pitch = next(line for line in lines if line.startswith("WIDTH AT PITCH DIA 3.175 (CHORD)"))
    chord = float(pitch.rsplit(" ", 1)[1])
    half_gap = math.asin(chord / (2.0 * profile.pitch_radius_mm))
    thickness = profile.pitch_radius_mm * (profile.angular_pitch_rad - 2.0 * half_gap)
    assert thickness == pytest.approx(profile.pitch_tooth_thickness_mm, abs=0.002)
    assert "WIDTH AT BLANK OD 4.310 (CHORD):  1.953" in lines
    assert "(t)" not in data and "sin" not in data and "SOURCE" not in data
    # Every decimal prints at 3 places.
    for number in re.findall(r"\d+\.\d+", data):
        assert len(number.split(".")[1]) == 3, number


def test_custom_gap_detail_crop_contains_every_real_boundary() -> None:
    profile = spec.stock_form_profile(6)
    center_x, center_y, radius = drawing.cutter_detail_window_mm()
    phase = math.pi / profile.teeth
    for segment in profile.gap_segments():
        if segment.kind == "tip_arc":
            continue
        for index in range(129):
            x, y = segment.point(index / 128)
            rotated = (
                math.cos(phase) * x - math.sin(phase) * y,
                math.sin(phase) * x + math.cos(phase) * y,
            )
            assert math.dist((center_x, center_y), rotated) < radius
    numerator, denominator = drawing.SHEET_SCALES[notes.CUTTER_DETAIL_SHEET]
    rendered_radius = radius * numerator / denominator / 1000.0
    # The grind data at the default note height: 2.4 mm a character, measured
    # on the run-20261010T051729717Z render of this sheet's 47-character
    # installed-gap label (113 mm).
    widest = max(map(len, drawing.cutter_grind_data().splitlines()))
    assert drawing.CUTTER_DETAIL_VIEW_CENTER[0] - rendered_radius > (
        drawing.CUTTER_DETAIL_POS[0] + widest * 0.0024 + 0.005
    )
    assert drawing.CUTTER_DETAIL_VIEW_CENTER[0] + rendered_radius < 0.420
    assert drawing.CUTTER_DETAIL_VIEW_CENTER[1] - rendered_radius > 0.100


def test_configuration_owned_bores_and_title_block_alloys_cover_the_family() -> None:
    registry = _config.parts("dt-cone-gear")
    assert spec.BODY_MATERIAL_SPEC == registry["material_specification"]
    assert spec.TIP_MATERIAL_SPEC == registry["material_tip_specification"]
    assert spec.TIP_MATERIAL_SPEC != spec.BODY_MATERIAL_SPEC
    # Brass and manganese bronze take no coating; the field says so rather
    # than reading as a missing value.  "Gear teeth cut; polished" (before
    # e44791855) was a method, and polishing would round the tooth edges
    # note 1 forbids breaking.
    assert registry["finish"] == "AS MACHINED, UNCOATED"
    assert str(registry["finish"]).strip().upper() not in {"", "NONE", "N/A"}
    for teeth in spec.CONFIGURATION_TEETH:
        assert part.bore_dia_in(teeth) * spec.MM_PER_IN == pytest.approx(
            spec.bore_dia_mm(teeth)
        )
        expected = spec.TIP_MATERIAL_SPEC if teeth <= 24 else spec.BODY_MATERIAL_SPEC
        assert spec.material_specification(teeth) == expected


def test_notes_state_no_bore_joint_method_or_review_record() -> None:
    # Rule 6: native D-bore dimensions carry its fit, and the Gear Data block
    # reports actual cutter/mesh facts separately. Every sheet keeps the same
    # two short manufacturing notes, without review history or waived floors.
    expected = [
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        "MAKE ONE GEAR FROM EACH T-CONFIGURATION SHEET.",
    ]
    assert notes.DRAWING_NOTES.splitlines() == expected
    assert not hasattr(notes, "ATTACHMENT")
    for teeth in spec.CONFIGURATION_TEETH:
        text = notes.drawing_notes(teeth)
        assert text.splitlines() == expected
        for review_or_method in (
            "SOLDER",
            "BRAZE",
            "LOCTITE",
            "BOND",
            "KEYWAY",
            "AT ASSEMBLY",
            "EXCEPTION",
            "BOOK FIDELITY",
            "CONTACT RATIO",
            "WEB",
        ):
            assert review_or_method not in text
        for unsupported in ("PIN", "SET SCREW", "HUB"):
            assert unsupported not in text
        for retired in ("RUNOUT", "DATUM", "+/-", "PITCH DIA="):
            assert retired not in text
    assert notes.CYLINDER_MATE_NUMBER == _config.parts("dt-cylinder-gear")["number"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes": drawing_notes(teeth)' in source


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_actual_web_prints_as_a_fact(teeth: int) -> None:
    data = notes.gear_data(teeth)
    web = notes.root_to_bore_web_min_mm(teeth)
    required = spec.WEB_EXCEPTIONS_MM.get(teeth, spec.MACHINED_WEB_TARGET_MM)
    assert web >= required - 1e-9
    assert f"WEB MIN (mm, REF):  {math.floor(web * 100.0) / 100.0:.2f}" in data


_REVIEW_RECORD_TEXT = re.compile(
    r"RULE \d|U\d\d|EXCEPTION|BOOK FIDELITY|POLICY|RULING"
)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_no_sheet_prints_a_review_record(teeth: int) -> None:
    # Rulings, exceptions and policy rules are provenance for the design
    # review (finding-rulings.md, code comments); a machinist cannot act on
    # them, so neither printed text block may carry one.
    for printed in (notes.drawing_notes(teeth), notes.gear_data(teeth)):
        assert not _REVIEW_RECORD_TEXT.search(printed), printed


def test_no_gdt_and_only_the_fitted_bore_has_a_surface_finish() -> None:
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert [control.key for control in spec.SURFACE_FINISHES] == ["cone_gear_bore"]
    assert spec.SURFACE_FINISHES[0].native_attachment == "model"
    for teeth in spec.CONFIGURATION_TEETH:
        control = spec.bore_surface_finish(teeth)
        assert control.key == "cone_gear_bore"
        assert control.native_attachment == "model"
        assert control.face.diameter_mm == pytest.approx(spec.bore_dia_mm(teeth))


def test_every_sheet_layout_keeps_views_dimensions_and_title_block_separate() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        half_od = drawing.rendered_half_od(teeth)
        half_face = drawing.rendered_half_face_width(teeth)
        front = drawing.front_keep(teeth)
        right = drawing.right_keep(teeth)
        bore = drawing.bore_view_keep(teeth)
        for x, y in (*front.values(), *right.values(), *bore.values()):
            assert 0.012 < x < 0.420
            assert 0.012 < y < 0.267
            assert not (x > 0.216 and y < 0.070)
        assert drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - half_face
        assert drawing.RIGHT_CENTER[0] + half_face < drawing.ISO_CENTER[0] - half_od
        assert front["BlankDia"][1] < drawing.GEAR_DATA_POS[1] - 0.035
        # Third-angle projection: the side view shares the front bore axis.
        assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
        # The Gear Data block clears the largest side view, and the face-width
        # dimension hangs BELOW the side view -- the native layout audit
        # missed the text collision this replaced on T084 and T108-T120.
        assert (
            drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
            > drawing.RIGHT_CENTER[1] + half_od + 0.008
        )
        assert right["FaceWidth"][1] < drawing.RIGHT_CENTER[1] - half_od - 0.008
        # The face-width text never sits on its extension lines (#834
        # machinist review, sheets 5-20): centred only where the face spans
        # the text plus a clearance each side, otherwise wholly right of the
        # right extension line and still clear of the iso view.
        text_x = right["FaceWidth"][0]
        text_half = drawing.FACE_WIDTH_TEXT_WIDTH / 2.0
        clearance = drawing.FACE_WIDTH_TEXT_CLEARANCE
        if drawing.face_width_text_inside(teeth):
            assert text_x == pytest.approx(drawing.RIGHT_CENTER[0])
            assert half_face - text_half >= clearance
        else:
            assert text_x - text_half >= drawing.RIGHT_CENTER[0] + half_face + clearance
            assert text_x + text_half < drawing.ISO_CENTER[0] - half_od - 0.005
        # Thickness text (~65 mm callout centred on its x) sits below the gear,
        # left of the side view and its face-width dimension.
        ctt_x, ctt_y = front["ToothThickness"]
        assert ctt_y < drawing.FRONT_CENTER[1] - half_od - 0.015
        assert ctt_x + 0.0325 < drawing.RIGHT_CENTER[0] - half_face - 0.020
        assert ctt_x - 0.0325 > bore["BoreCutDia"][0] + _BORE_DIA_TEXT_HALF_WIDTH + 0.010
        # The bore finish sits above-left of the gear, inside the border and
        # below the manufacturing notes.
        (edge_x, edge_y), (symbol_x, symbol_y) = drawing.bore_finish_xy(teeth)
        assert edge_x < drawing.FRONT_CENTER[0] and edge_y > drawing.FRONT_CENTER[1]
        assert 0.015 < symbol_x < drawing.FRONT_CENTER[0] - half_od * 0.7
        assert drawing.FRONT_CENTER[1] + half_od * 0.7 < symbol_y < 0.225
        assert front["ToothThickness"][0] > drawing.FRONT_CENTER[0] + half_od
        # The gap-floor limit stack (two 3-place values plus "GAP FLOOR",
        # ~17 x 11 mm) stands right of the tip circle, above the thickness
        # witness, left of the side view and below the Gear Data block.
        floor_x, floor_y = front["FloorDia"]
        assert floor_x - _FLOOR_TEXT_HALF_WIDTH > drawing.FRONT_CENTER[0] + half_od
        assert floor_x + _FLOOR_TEXT_HALF_WIDTH < drawing.RIGHT_CENTER[0] - half_face - 0.020
        # The shelf under "GAP FLOOR" keeps the fleet's arrow-to-text
        # clearance from the thickness dimension's upper arrow tail: one
        # template arrow length past the witness, which stands half the arc
        # thickness above the bore axis at sheet scale (an upper bound on the
        # chord it witnesses).
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        witness_y = (
            drawing.FRONT_CENTER[1]
            + spec.tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
        )
        tail_y = witness_y + drawing.DIMENSION_ARROW_LENGTH
        shelf_y = floor_y - drawing.FLOOR_STACK_HALF_HEIGHT
        assert shelf_y - tail_y >= _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-9, teeth
        assert (
            floor_y + drawing.FLOOR_STACK_HALF_HEIGHT
            < drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
        )
        # The shelf rises only where the tail needs it: every other sheet
        # keeps the stack's usual place.
        usual = (
            drawing.FRONT_CENTER[1] + 0.6 * half_od + drawing.FLOOR_DIA_RISE
        )
        assert floor_y >= usual - 1e-12
        if floor_y > usual:
            assert shelf_y - tail_y == pytest.approx(_drawing_leaders.ARROW_TEXT_CLEARANCE)


# Text half-widths in the bore view, sheet metres: the stacked diameter
# (~33 mm, measured when its callout still read "REAM THRU"; "THRU" is
# narrower), and the two-line title. The clock text's measured block is
# drawing.BORE_CLOCK_TEXT_HALF_WIDTH/HEIGHT.
_BORE_DIA_TEXT_HALF_WIDTH = 0.0165
_BORE_TEXT_HALF_HEIGHT = 0.005
_BORE_TITLE_HEIGHT = 0.008
# The layout audit compares IView.GetOutline boxes, which pad the geometry:
# ~5.5 mm round an uncropped view (T084 front [54.8, 99.8, 155.2, 200.2]
# about a 44.66 mm half tip circle) and 10.1-10.75 mm past a bore view's crop
# circle (T006-T024 and T030+ sheets; 11.3 is taken as the pad), inside the
# sheet format's 12.7 mm zone band (_drawing_common.sheet_drawable_region;
# farm run 20260929T061328212Z at 70d2e52).
_FRONT_OUTLINE_PAD = 0.0056
_CROPPED_OUTLINE_PAD = 0.0113
_ZONE_MARGIN = 0.0127


def test_bore_view_enlarges_every_d_bore_clear_of_its_neighbours() -> None:
    ladder = [n / d for n, d in drawing.BORE_VIEW_SCALE_LADDER]
    cx, cy = drawing.BORE_VIEW_CENTER
    for teeth in spec.CONFIGURATION_TEETH:
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        sheet_ratio = numerator / denominator
        view_numerator, view_denominator = drawing.bore_view_scale(teeth)
        ratio = view_numerator / view_denominator
        bore = spec.bore_dia_mm(teeth)
        # Enlarged past the sheet, to the smallest ladder ratio that renders
        # the bore legibly, with the flat at least 2.5 mm deep on paper.
        assert ratio > sheet_ratio
        assert bore * ratio / 1000.0 >= drawing.BORE_VIEW_BORE_MIN
        assert all(
            bore * smaller / 1000.0 < drawing.BORE_VIEW_BORE_MIN
            for smaller in ladder
            if sheet_ratio < smaller < ratio
        )
        depth = (bore / 2.0 - spec.bore_flat_offset_mm(teeth)) * ratio / 1000.0
        assert depth >= 0.0025, teeth
        crop = drawing.bore_view_crop_radius(teeth)
        assert crop > bore * ratio / 2000.0
        # The crop circle stands inside the border and clear of the front
        # view's tip circle, and the boxes the audit compares stay apart: the
        # views overlap in x, so the bore view's box must sit under the front
        # view's on every sheet (T084 met it at y 0.066 with a 7 mm margin).
        assert cx - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        assert cy - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        half_od = drawing.rendered_half_od(teeth)
        assert math.dist((cx, cy), drawing.FRONT_CENTER) > crop + half_od + 0.010
        front_bottom = drawing.FRONT_CENTER[1] - half_od - _FRONT_OUTLINE_PAD
        assert cy + crop + _CROPPED_OUTLINE_PAD + 0.002 < front_bottom, teeth
        keep = drawing.bore_view_keep(teeth)
        for x, y in keep.values():
            assert math.dist((x, y), drawing.FRONT_CENTER) > half_od + 0.015
        dia_x, dia_y = keep["BoreCutDia"]
        assert dia_x - _BORE_DIA_TEXT_HALF_WIDTH > 0.012
        assert dia_y - _BORE_TEXT_HALF_HEIGHT > cy + crop - 0.003
        # The across-flat text stands wholly right of the flat's witness,
        # left of the title block, above the title, which stays inside the
        # border, and under the clock's text.
        af_x, af_y = keep["BoreAF"]
        flat = spec.bore_flat_offset_mm(teeth) * ratio / 1000.0
        assert af_x - drawing.BORE_VIEW_AF_HALF_WIDTH > cx + flat + 0.002
        assert af_x + drawing.BORE_VIEW_AF_HALF_WIDTH < 0.216
        assert af_y < cy - crop
        title_top = drawing.bore_view_label_top(teeth)
        assert af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT > title_top
        assert title_top - _BORE_TITLE_HEIGHT > _ZONE_MARGIN + 0.001
        assert af_y + 2.0 * _BORE_TEXT_HALF_HEIGHT < keep["BoreFlatClock"][1] - 0.010
        # The clock text stands wholly right of the circle and clear of the
        # thickness callout under the front view.
        clock_x, clock_y = keep["BoreFlatClock"]
        # Its two-line block (measured half-extents) stands an arrow length
        # plus clearance above the axis line, where the arc's arrowhead ends
        # under the text, and clear of the crop circle.
        assert clock_y - drawing.BORE_CLOCK_TEXT_HALF_HEIGHT >= (
            cy + drawing.BORE_CLOCK_ARROW_LENGTH + _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-12
        ), teeth
        assert clock_x - drawing.BORE_CLOCK_TEXT_HALF_WIDTH >= cx + crop + 0.002 - 1e-12, teeth
        # The thickness callout, measured on the T006 PDF of run
        # 20261010T051729717Z: its text spans x 136.2-200.4, y 100.0-116.5 mm
        # round its keep (136.24, 107.76) mm, starting at its dimension line
        # (the keep x) and running right, with its leader above.
        ctt_x, ctt_y = drawing.front_keep(teeth)["ToothThickness"]
        clock_box = (
            clock_x - drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y - drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
            clock_x + drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y + drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
        )
        ctt_box = (ctt_x - 0.001, ctt_y - 0.0078, ctt_x + 0.0642, ctt_y + 0.0088)
        assert _drawing_annotation_extent.boxes_clear(clock_box, ctt_box), teeth
        # The clock's arc centres where the flat crosses the axis and swings
        # through its text, in the quadrant right of the flat and above the
        # axis: clear of the diameter's upper-left lane and under the front
        # view. Left in the sketch's upper-left quadrant, it crossed the
        # diameter's shoulder on every 4:1 sheet.
        vx, vy = drawing.bore_flat_vertex(teeth)
        assert (vx, vy) == pytest.approx((cx + flat, cy))
        assert clock_x > vx and clock_y > vy
        reach = math.dist((vx, vy), (clock_x, clock_y))
        assert dia_x + _BORE_DIA_TEXT_HALF_WIDTH < vx - 0.005
        assert vy + reach + 0.003 < front_bottom, teeth
        assert drawing.bore_view_label(teeth).splitlines() == [
            "BORE PROFILE",
            f"SCALE {view_numerator:g} : {view_denominator:g}",
        ]


def test_settled_clock_check_refuses_outside_arrow_stubs() -> None:
    """Run 20261010T073917031Z's arc readbacks (sheet mm): T006's clock drew
    one arc between its legs, broken by its text; T120's, its arrows left
    smart, drew two 10 deg stubs outside them and no arc. The clock is forced
    arrows-inside, and finalize re-reads every sheet's arcs after settling."""

    def arc(vertex, radius, start, end):
        steps = 12
        return (
            vertex,
            [
                (
                    vertex[0] + radius * math.cos(math.radians(start + (end - start) * i / steps)),
                    vertex[1] + radius * math.sin(math.radians(start + (end - start) * i / steps)),
                )
                for i in range(steps + 1)
            ],
        )

    good_vertex = (0.05292, 0.060)
    good = [arc(good_vertex, 0.04642, 0.0, 11.0), arc(good_vertex, 0.04642, 18.0, 90.0)]
    assert drawing.clock_arc_faults(good, good_vertex) == []
    bad_vertex = (0.068, 0.060)
    bad = [arc(bad_vertex, 0.03503, -10.2, 0.0), arc(bad_vertex, 0.03503, 90.0, 100.2)]
    faults = drawing.clock_arc_faults(bad, bad_vertex)
    assert any("outside the quadrant" in fault for fault in faults)
    assert any("sweep" in fault for fault in faults)
    assert drawing.clock_arc_faults([], bad_vertex) == ["no arc"]
    assert drawing.ARROWS_INSIDE == 0  # swDimensionArrowsSide_e.swDimArrowsInside
    assert "display.ArrowSide = ARROWS_INSIDE" in inspect.getsource(
        drawing._sweep_clock_right_of_flat
    )
    assert "settled_checks=(lambda: _assert_settled_clocks(adapter, clocks),)" in (
        inspect.getsource(drawing.build)
    )


def test_dimension_arrow_length_is_read_from_the_drawing() -> None:
    """The layout's arrow length is the drawing's own, not a remembered one."""

    class _Extension:
        def __init__(self, value: float) -> None:
            self.value = value
            self.calls: list[tuple[int, int]] = []

        def GetUserPreferenceDouble(self, pref: int, option: int) -> float:  # noqa: N802
            self.calls.append((pref, option))
            return self.value

    class _Drawing:
        def __init__(self, value: float) -> None:
            self.Extension = _Extension(value)

    matching = _Drawing(drawing.DIMENSION_ARROW_LENGTH)
    drawing._assert_dimension_arrow_length(matching)
    # swDetailingArrowLength, swDetailingNoOptionSpecified
    assert matching.Extension.calls == [(26, 0)]
    with pytest.raises(RuntimeError, match="drawing arrow length reads 3.175 mm"):
        drawing._assert_dimension_arrow_length(_Drawing(0.003175))


# The functional root callout is thirteen characters, wider than either value.
_FLOOR_TEXT_HALF_WIDTH = len(drawing.DIMENSION_CALLOUTS["FloorDia"]) * 0.00185 / 2.0


class _FakeFeature:
    def __init__(self, visible: int) -> None:
        self.Visible = visible


class _FakePart:
    """A part document that records sketch blanks and reports visibility."""

    def __init__(self, *, hides: bool) -> None:
        self.hides = hides
        self.selected: list[tuple[str, str]] = []
        self.blanked: list[str] = []
        self.Extension = self

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def SelectByID2(self, name: str, kind: str, *_args: object) -> bool:
        self.selected.append((name, kind))
        return True

    def BlankSketch(self) -> None:
        self.blanked.append(self.selected[-1][0])

    def FeatureByName(self, name: str) -> _FakeFeature:
        # swVisibilityState_e: 1 hidden, 2 shown
        return _FakeFeature(1 if self.hides and name in self.blanked else 2)


class _FakeAdapter:
    def __init__(self, model: object) -> None:
        self.currentModel = model


def test_the_part_saves_both_authoring_sketches_hidden() -> None:
    """#950's save gate: a shown construction sketch renders in the part images
    and in every assembly that places a gear, so the part blanks both before
    its first save and reads the blank back."""
    model = _FakePart(hides=True)
    part._blank_reference_sketches(_FakeAdapter(model))
    sketches = [spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH]
    assert model.selected == [(sketch, "SKETCH") for sketch in sketches]
    assert model.blanked == sketches
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.index("_suppress_rows_and_hide_references(adapter, pattern_axis)") < body.index(
        "await adapter.save_file("
    )
    # Hide/show is per configuration (7e88be269 T006 image): the axis and both
    # sketches are blanked inside the loop that activates each configuration,
    # and the reopened part is gated in every configuration.
    helper = inspect.getsource(part._suppress_rows_and_hide_references)
    loop = helper[helper.index("for configuration in"):]
    assert "_activate_configuration(model, configuration)" in loop
    assert 'blank_reference_geometry(adapter, ((pattern_axis, "AXIS"),))' in loop
    assert "_blank_reference_sketches(adapter)" in loop
    assert "blank_reference_geometry(" not in body
    assert "assert_reference_geometry_hidden_in_every_configuration(adapter, PART_NAME)" in body


def test_a_blank_that_does_not_take_fails_the_part_build() -> None:
    with pytest.raises(RuntimeError, match="still visible after BlankSketch"):
        part._blank_reference_sketches(_FakeAdapter(_FakePart(hides=False)))


class _FakeTolerance:
    def __init__(self, accept: bool = True) -> None:
        self.Type = 0
        self.accept = accept
        self.calls: list[tuple[float, float, int, list[str]]] = []

    def SetValues2(self, lower: float, upper: float, which: int, names: object) -> bool:
        self.calls.append((lower, upper, which, list(names.value)))
        return self.accept


def _patch_floor_dimension(monkeypatch: pytest.MonkeyPatch, tolerance: object) -> None:
    dimension = type("Dimension", (), {"Tolerance": tolerance})()

    def named(_adapter: object, feature: str, name: str) -> tuple[object, object]:
        assert (feature, name) == (spec.GAP_FLOOR_SKETCH, "FloorDia")
        return object(), dimension

    monkeypatch.setattr(part, "_named_dimension", named)


def test_each_configuration_stores_its_own_gap_floor_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#834 Codex P1: the floor band is a native per-configuration LIMIT, one
    SetValues2 per configuration naming only that configuration."""
    tolerance = _FakeTolerance()
    _patch_floor_dimension(monkeypatch, tolerance)
    part._set_gap_floor_limits(object())
    assert tolerance.Type == 3  # swTolLIMIT
    assert [call[3] for call in tolerance.calls] == [[name] for name, _ in part.CONFIGS]
    for (lower, upper, which, _names), (_name, teeth) in zip(
        tolerance.calls, part.CONFIGS, strict=True
    ):
        assert which == 3  # swSetValue_InSpecificConfigurations
        nominal = 2.0 * spec.floor_radius_min_mm(teeth)
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert nominal + lower * 1000.0 == pytest.approx(minimum, abs=1e-9)
        assert nominal + upper * 1000.0 == pytest.approx(maximum, abs=1e-9)
        assert lower <= 0.0 < upper


def test_a_rejected_configuration_limit_fails_the_part_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_floor_dimension(monkeypatch, _FakeTolerance(accept=False))
    with pytest.raises(RuntimeError, match="FloorDia@T006: SetValues2 rejected"):
        part._set_gap_floor_limits(object())


def test_every_configuration_stores_its_own_blank_and_thickness_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """part:dt_cone_gear at 039e557da: the T006-only write's immediate readback
    returned T006's band. The FloorDia form instead: all twenty written, T006
    its own, then each read back in the reopened audit with itself active."""
    tolerances = {"BlankDia": _FakeTolerance(), "ToothThickness": _FakeTolerance()}

    def named(_adapter: object, _feature: str, name: str) -> tuple[object, object]:
        return object(), type("Dimension", (), {"Tolerance": tolerances[name]})()

    monkeypatch.setattr(part, "_named_dimension", named)
    part._set_configuration_bands(object())
    for name, band_for in (
        ("BlankDia", spec.blank_dia_band),
        ("ToothThickness", spec.tooth_thickness_band),
    ):
        calls = tolerances[name].calls
        assert [call[3] for call in calls] == [[c] for c, _ in part.CONFIGS]
        for (lower, upper, which, _names), (_c, teeth) in zip(calls, part.CONFIGS, strict=True):
            assert which == 3
            upper_mm, lower_mm = band_for(teeth)
            assert (lower * 1000.0, upper * 1000.0) == pytest.approx((lower_mm, upper_mm))
    source = inspect.getsource(part.assert_saved_configuration_topology)
    assert "_assert_configuration_bands(adapter, configuration, teeth)" in source
    assert "GetMinValue" not in inspect.getsource(part._set_configuration_bands)


def test_only_the_front_view_shows_the_authoring_sketches() -> None:
    """Both sketches' dimensions live on the front view, which takes the
    opt-in import; the side, iso and bore views show the part as saved."""
    for sketch in (spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH):
        owned = spec.DRAWING_DIMENSIONS[sketch]
        for teeth in spec.CONFIGURATION_TEETH:
            assert owned <= set(drawing.front_keep(teeth))
            assert not owned & set(drawing.right_keep(teeth))
            assert not owned & set(drawing.bore_view_keep(teeth))


# Measured by the layout audit on the T006 sheet (layoutcal2, cone-gear.json):
# the vertical centre-mark line reaches y 0.1763, and the BlankDia value's text
# box hangs 0.0036 below its anchor (anchor 0.1791, box bottom 0.1755).
_T006_CENTRE_MARK_TOP = 0.1763
_BLANK_DIA_TEXT_DESCENT = 0.0036


def test_t006_blank_dia_value_clears_the_centre_mark_line() -> None:
    """layoutcheck T006: the value sat 0.82 mm down over the centre-mark line."""
    text_bottom = drawing.front_keep(6)["BlankDia"][1] - _BLANK_DIA_TEXT_DESCENT
    assert text_bottom >= _T006_CENTRE_MARK_TOP + 0.001


def test_invalid_family_member_is_rejected() -> None:
    with pytest.raises(ValueError):
        spec.bore_dia_mm(7)
    with pytest.raises(ValueError):
        spec.floor_radius_max_mm(7)
    with pytest.raises(ValueError):
        spec.floor_radius_min_mm(7)
    with pytest.raises(ValueError):
        spec.outside_dia_mm(7)
    with pytest.raises(ValueError):
        spec.tooth_thickness_mm(7)
    with pytest.raises(ValueError):
        notes.drawing_notes(7)
    with pytest.raises(ValueError):
        spec.material_specification(7)
    with pytest.raises(ValueError):
        notes.gear_data(7)


def test_root_to_bore_webs_keep_the_floor_and_target_guards() -> None:
    # Printed root MIN against the outward-rounded maximum bore, not a nominal
    # floor. T006's approved 0.62 web is separate from the ordinary 2.0 target.
    for teeth in spec.CONFIGURATION_TEETH:
        web = notes.root_to_bore_web_min_mm(teeth)
        if teeth in spec.WEB_EXCEPTIONS_MM:
            assert web >= spec.WEB_EXCEPTIONS_MM[teeth] - 1e-9
            continue
        assert web >= spec.MACHINED_WEB_TARGET_MM, (teeth, web)
    # The flat is a chord of the round bore on the axis's +X side: it only
    # ever leaves material, so no web is thinner than the round side's.
    for teeth in spec.CONFIGURATION_TEETH:
        assert 0.0 < spec.bore_flat_offset_mm(teeth) < spec.bore_dia_mm(teeth) / 2.0
    # The terminal gear remains bounded by its current spec-owned special
    # web floor; neither a stale historical pin nor a new approval is used.
    terminal = spec.CONFIGURATION_TEETH[0]
    assert notes.root_to_bore_web_min_mm(terminal) >= (
        spec.WEB_EXCEPTIONS_MM[terminal] - 1e-9
    )
    for teeth in spec.CONFIGURATION_TEETH:
        section = spec.land_section(teeth)
        assert spec.bore_dia_mm(teeth) == pytest.approx(
            dt_cone_gear_shaft_spec.SECTION_DIAS[section]
        )


def test_dimensions_record_gear_bores_row_follows_the_spec() -> None:
    # The narrative record is read by no part, so nothing rebuilds when the
    # bores move: it kept the pre-S1 map (9.5 on T024-T120) after U40.  It
    # must name every round seat, its gears and its across-flat.
    groups: dict[float, list[int]] = {}
    for teeth in spec.CONFIGURATION_TEETH:
        groups.setdefault(spec.bore_dia_mm(teeth), []).append(teeth)
    record = yaml.safe_load(
        (Path(part.__file__).resolve().parents[1] / "config" / "dimensions.yaml")
        .read_text(encoding="utf-8")
    )
    rows = []
    stack = [record]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            if node and isinstance(node[0], str) and node[0].startswith("Gear bores"):
                rows.append(node)
            stack.extend(node)
    assert len(rows) == 1
    row = rows[0][1]
    printed_bores = sorted({float(value) for value in re.findall(r"Ø(\d+\.\d+)", row)})
    assert printed_bores == pytest.approx(sorted(groups))
    for bore, teeth in groups.items():
        span = f"T{teeth[0]:03d}" if len(teeth) == 1 else f"T{teeth[0]:03d}–T{teeth[-1]:03d}"
        assert span in row, span
        assert f"{spec.bore_flat_af_mm(teeth[0]):.3f}" in row, bore
