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
import _cone_gear_geometry as geometry
import _cone_gear_readback as readback
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
    assert spec.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
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
        # The turned blank reads as an overall diameter on the side view,
        # never as a circular/end-view leader; face width keeps that view too.
        assert set(drawing.front_keep(teeth)) == {"FloorDia", "ToothThickness"}
        assert set(drawing.right_keep(teeth)) == {"BlankDia", "FaceWidth"}


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


@pytest.mark.parametrize("teeth, suffix", ((6, "T006"), (12, "T012"), (120, "T120")))
def test_two_digit_family_number_keeps_three_digit_tooth_configuration(
    teeth: int, suffix: str,
) -> None:
    assert spec.configuration_number(" mha-dt-03 ", teeth) == f"MHA-DT-03-{suffix}"


def test_bore_bands_are_the_current_derived_seat_fit_bands() -> None:
    assert spec.BORE_DIA_BAND == pytest.approx(
        (spec.BORE_BAND_FIT_UPPER, spec.BORE_BAND_LOWER)
    )
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
        assert readback._expected_configuration_volume(teeth) == pytest.approx((
            math.pi * profile.blank_radius_mm**2
            - teeth * profile.gap_area_mm2 - geometry.bore_area_mm2(teeth)
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
            "CUTTER", "CUTTER PLUNGE FROM BLANK OD", "WHOLE DEPTH",
            "TOOTH FORM", "BACKLASH WITH MATE", "ROOT RADIAL MIN/MAX", "WEB",
            "OVER 2 PINS",
        ):
            assert physical_recipe in data, (teeth, physical_recipe)
        # ENFORCE round 1 of #971: "TOOL T" told the shop how to set the
        # cutter (rule 7); the plunge stays, a reference depth.
        assert "TOOL T" not in data
        # Stock cutters name their template; T006's space is the last sheet.
        last = len(spec.CONFIGURATION_TEETH) + 1
        cutter = f"NOT STOCK; FORM = TOOTH SPACE, SHEET {last}" if teeth == 6 else "; TEMPLATE "
        assert cutter in data, teeth
        assert ("RELIEF BELOW R1.531" in data) == (teeth == 6)
        assert "TIF" not in data
        assert notes.CYLINDER_MATE_NUMBER in data
        for obsolete in ("CONTACT RATIO", "RANGE ONLY", "MATCH FLANKS", "LONG ADDENDUM"):
            assert obsolete not in data
        assert len(data.splitlines()) * 0.00351 <= drawing.GEAR_DATA_HEIGHT


def test_native_gap_features_are_distinct_and_preserve_real_template_topology() -> None:
    features = [name for teeth in spec.CONFIGURATION_TEETH for name in spec.tooth_features(teeth)]
    assert len(set(features)) == 3 * len(spec.CONFIGURATION_TEETH)
    assert len(spec.SIMPLIFIED_FEATURES) == 2 * len(spec.CONFIGURATION_TEETH)
    assert spec.SIMPLIFIED_FEATURES_BY_CONFIGURATION == {
        f"T{teeth:03d}": spec.tooth_features(teeth)[1:] for teeth in spec.CONFIGURATION_TEETH
    }
    for teeth in spec.CONFIGURATION_TEETH:
        profile = spec.stock_form_profile(teeth)
        core = profile.cut_order_native_segments(
            unit_scale=1.0 / spec.MM_PER_IN, clearance_radius_mm=geometry.R_CLEAR_MM
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
        assert all(name.endswith(f"T{teeth:03d}") for name in spec.tooth_features(teeth))
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
    assert drawing.DIMENSION_CALLOUTS["FloorDia"].splitlines()[0] == "ROOT ENVELOPE"


def test_tight_bands_name_their_mates_at_the_callout() -> None:
    """Machinist review of the round-2 build: straight witnesses with no
    circle left the circular thickness unmeasurable, so under the value the
    callout names the pitch circle (N / 48 in). ENFORCE round 1 of #971:
    each tight band names its mate and fit at the callout (rule 4). ENFORCE
    round 2: a multi-line callout above a value never prints, so every
    above-callout is one line."""
    assert "MHA-DT-04" in drawing.DIMENSION_CALLOUTS["BoreAF"]
    assert "MHA-DT-04" in drawing.DIMENSION_CALLOUTS["BoreCutDia"]
    assert "MHA-DT-04" in drawing.DIMENSION_CALLOUTS["FaceWidth"]
    assert notes.CYLINDER_MATE_NUMBER in drawing.DIMENSION_CALLOUTS["FloorDia"]
    above = drawing.CALLOUTS_ABOVE
    assert set(above) == {"ToothThickness", "BoreFlatClock"}
    assert all("\n" not in text for text in above.values())
    assert notes.CYLINDER_MATE_NUMBER in above["ToothThickness"]
    blank_reason = drawing.DIMENSION_CALLOUTS["BlankDia"]
    assert " ".join(blank_reason.split()) == f"MESHES WITH {notes.CYLINDER_MATE_NUMBER}"
    assert "MHA-DT-04" in above["BoreFlatClock"]
    label = "CIRCULAR TOOTH THICKNESS"
    assert drawing.DIMENSION_CALLOUTS["ToothThickness"] == label
    # The bore diameter's rows stay as narrow as its value, clear of the
    # flat's witness on T006/T012 (r2: a 20-character row crossed it).
    assert max(map(len, drawing.DIMENSION_CALLOUTS["BoreCutDia"].splitlines())) <= 10
    assert len(above["ToothThickness"]) <= len(label)
    for teeth in spec.CONFIGURATION_TEETH:
        below = drawing.callouts_below(teeth)
        assert set(below) == set(drawing.DIMENSION_CALLOUTS)
        pitch_dia = teeth / spec.DIAMETRAL_PITCH * 25.4
        assert below["ToothThickness"] == f"{label}\nON PITCH CIRCLE \u00d8{pitch_dia:.3f}"
        assert max(map(len, below["ToothThickness"].splitlines())) <= len(label)
        assert pitch_dia / 2.0 == pytest.approx(spec.stock_form_profile(teeth).pitch_radius_mm)


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
        unit_scale=1.0, clearance_radius_mm=geometry.R_CLEAR_MM
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
    monkeypatch.setattr(readback, "stock_form_profile", lambda _teeth: profile)
    minimum, maximum, count = readback._native_root_envelope_mm(body, teeth=profile.teeth)
    assert count == profile.teeth
    assert minimum == pytest.approx(profile.root_radius_min_mm)
    assert maximum == pytest.approx(profile.root_radius_max_mm)
    assert minimum < maximum
    assert all(len(edge.queries) == 2 for edge in edges)
    # A gap that did not cut through leaves its root off the far face.
    faces[-1].edges.pop()
    with pytest.raises(RuntimeError, match="native root arcs on the exit face"):
        readback._native_root_envelope_mm(body, teeth=profile.teeth)


def test_root_envelope_reads_the_body_and_failures_name_their_call() -> None:
    # f68549253: the reopened audit passed the IPartDoc where the reader calls
    # IBody2.GetFaces, and every configuration failed as an anonymous
    # DISP_E_MEMBERNOTFOUND.
    try:
        readback._exit_face(object())
    except AttributeError as exc:
        site = readback._failure_site(exc)
    assert '_com_invoke(body, "IBody2", "GetFaces")' in site
    assert "in _exit_face" in site


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


def test_custom_six_sheet_defines_the_tooth_space_point_by_point() -> None:
    """The last sheet defines the T006 tooth space (3 places, one-sided form
    tolerance), which is DT6-FORM1's edge; the gear is accepted over pins.
    ENFORCE round 1 of #971: as a tool drawing it carried the gear's title
    block and told the shop how to inspect its tool. Round 3: the form
    tolerance names the mesh it sets, and the acceptance names its sheet."""
    profile = spec.stock_form_profile(6)
    template = profile.template
    data = drawing.cutter_grind_data()
    lines = data.splitlines()
    assert lines[0] == "T006 TOOTH SPACE FORM, mm"
    assert drawing.SHEET_NAMES[0] == "T006"
    assert "OVER PINS PER SHEET 1 " in lines[-1]
    assert notes.CYLINDER_MATE_NUMBER in lines[-2]
    assert "(REF)" not in data
    assert "COMPARATOR" not in data and "TIF" not in data
    assert "INSPECT" not in data and "TOOL" not in data and "GRIND" not in data
    assert "SYMMETRIC ABOUT THE SPACE CENTERLINE (CL):" in lines
    assert "ROOT: ARC R1.100 ABOUT GEAR AXIS" in lines
    assert "ROOT ARC TO R1.531: STRAIGHT LINES ROW TO ROW" in lines
    assert "ABOVE R1.531: INVOLUTE, BASE R1.492" in lines
    # Wide only, by half the T006 thinning band (0/-0.04 on thickness).
    assert spec.CUSTOM_SIX_FORM_TOLERANCE_MM == pytest.approx(0.02)
    assert "FORM TOLERANCE: X +0.020 / -0.000" in lines
    points = spec.custom_six_form_points_mm()
    rows = [line for line in lines if line.startswith("R") and "   X" in line]
    assert rows == [f"R{r:.3f}   X{x:.3f}   Y{y:.3f}" for r, x, y in points]
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    assert points[0] == (root, 0.0, 0.0)
    assert points[-1][0] == profile.blank_radius_mm
    # Rows print at 3 places; the relief's end rows round to the nearest.
    resolution = 0.0005 * math.sqrt(2.0)

    def model_xy(radius: float) -> tuple[float, float]:
        angle = spec.custom_six_gap_half_angle_rad(radius)
        return radius * math.sin(angle), radius * math.cos(angle) - root

    # The tip arc ends where the relief leaves the root circle; the straight
    # lines end at the junction row, and every row above it is on the involute.
    split = next(i for i, (r, _, _) in enumerate(points) if abs(r - junction) < resolution)
    relief, involute = points[1:split + 1], points[split + 1:]
    assert math.dist(relief[0][1:], model_xy(root)) < resolution
    assert math.dist(relief[-1][1:], model_xy(junction)) < resolution
    assert all(r >= root - resolution for r, _, _ in relief)
    for radius, x, y in involute:
        assert junction < radius and (x, y) == pytest.approx(model_xy(radius), abs=1e-12)
    # The straight lines never cut inside the model relief (a line point sits
    # at no smaller polar angle than the relief at its radius), and stand at
    # most 0.006 off it (the rounding of their ends aside).
    curve = [model_xy(root + (junction - root) * i / 2000) for i in range(2001)]
    inside, offset = 0.0, 0.0
    for (_, x0, y0), (_, x1, y1) in zip(relief, relief[1:]):
        for index in range(21):
            x = x0 + (x1 - x0) * index / 20
            y = y0 + (y1 - y0) * index / 20
            radius = math.hypot(x, y + root)
            distance = min(math.dist((x, y), point) for point in curve)
            offset = max(offset, distance)
            if root < radius < junction and math.atan2(x, y + root) < (
                spec.custom_six_gap_half_angle_rad(radius)
            ):
                inside = max(inside, distance)
    assert inside < 0.0005
    assert offset < 0.006
    # Closed-form cross-checks against the native profile: the pitch and
    # blank-OD rows are the tool's pitch thickness and the profile's tip chord.
    by_radius = {round(r, 6): x for r, x, _ in involute}
    pitch_half_gap = math.asin(by_radius[round(profile.pitch_radius_mm, 6)] / profile.pitch_radius_mm)
    thickness = profile.pitch_radius_mm * (profile.angular_pitch_rad - 2.0 * pitch_half_gap)
    assert thickness == pytest.approx(profile.pitch_tooth_thickness_mm, abs=1e-6)
    assert by_radius[round(profile.blank_radius_mm, 6)] == pytest.approx(
        profile.blank_radius_mm * math.sin(profile.tip_half_angle_rad), abs=1e-9
    )
    # Relief and involute meet at the junction row.
    assert template.relief_half_angle_rad(junction) == pytest.approx(
        spec.custom_six_gap_half_angle_rad(junction + 1e-9), abs=1e-6
    )
    assert "(t)" not in data and "sin" not in data and "SOURCE" not in data
    # Every decimal prints at 3 places.
    for number in re.findall(r"\d+\.\d+", data):
        assert len(number.split(".")[1]) == 3, number
    # The note stays clear of the title block (4.6 mm a line, run
    # 20261011T114502461Z render of this sheet).
    assert drawing.CUTTER_DETAIL_POS[1] - len(lines) * 0.0046 > 0.100


def test_over_pins_acceptance_matches_the_closed_form_involute() -> None:
    """The standard even-count over-pins formula agrees with the sampled
    model flank where that flank is the gear's own involute (T006's
    DT6-FORM1, T012's 12T template), and the thin limit reads below the
    thick one. ENFORCE round 1 of #971: every sheet carries the row, not T006
    only; the stock gears' 1.00 pin lands on the flank and stands proud. A
    stock cutter cuts its template's form, thinner up the flank than the
    gear's own involute away from the template count, so there the pins read
    up to ~0.015 under the formula and the row follows the model."""
    for teeth in spec.CONFIGURATION_TEETH:
        assert teeth % 2 == 0, teeth
        profile = spec.stock_form_profile(teeth)
        pitch_dia = 2.0 * profile.pitch_radius_mm
        alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
        base_dia = pitch_dia * math.cos(alpha)
        pin = spec.over_pins_pin_dia_mm(teeth)
        assert pin == (1.20 if teeth == 6 else 1.00)

        def involute(angle: float) -> float:
            return math.tan(angle) - angle

        target = (
            profile.pitch_tooth_thickness_mm / pitch_dia + involute(alpha)
            + pin / base_dia - math.pi / teeth
        )
        low, high = 0.0, 1.4
        for _ in range(80):
            middle = (low + high) / 2.0
            low, high = (middle, high) if involute(middle) < target else (low, middle)
        closed_form = base_dia / math.cos(low) + pin
        nominal, contact_radius, interior = spec._over_pins_mm(profile, pin)
        assert interior, teeth
        assert base_dia / 2.0 <= contact_radius < profile.blank_radius_mm, teeth
        if profile.template.cutter_number is None or profile.template.reference_teeth == teeth:
            assert nominal == pytest.approx(closed_form, abs=2e-4), teeth
        else:
            assert closed_form - 0.02 < nominal <= closed_form + 2e-4, teeth
        assert nominal / 2.0 > profile.blank_radius_mm, teeth
        minimum, maximum = spec.over_pins_limits_mm(teeth)
        assert minimum < nominal < maximum + 1e-3, teeth
        row = f"OVER 2 PINS \u00d8{pin:.2f}, OPPOSITE GAPS (mm):  {minimum:.3f} TO {maximum:.3f}"
        assert row in notes.gear_data(teeth), teeth
    minimum, maximum = spec.over_pins_limits_mm(6)
    assert maximum - minimum == pytest.approx(0.063, abs=0.002)


def test_tooth_space_sheet_plots_the_table_beside_it() -> None:
    """ENFORCE rounds 3 and 4 of #971: the cropped, rotated illustration
    showed no CL, axes or stations, and the table alone left the sheet
    bunched in a corner (rule 15). The plot draws the table's own rows, with
    CL, X axis, origin and R stations, between the table and the border. The
    sheet's T006 view only feeds the title block, hidden."""
    source = inspect.getsource(drawing.build)
    assert '"*Front", *CUTTER_SOURCE_VIEW_CENTER' in source
    assert "_hide_title_block_source(adapter, source_view)" in source
    assert "_draw_form_plot(adapter)" in source
    flank = drawing.form_plot_flank_mm()
    rows = spec.custom_six_form_points_mm()
    junction = spec.stock_form_profile(6).template.relief_junction_radius_mm
    relief = [(x, y) for radius, x, y in rows[1:] if radius <= junction + 1e-9]
    # The relief rows are the plot's vertices (straight lines row to row);
    # above the junction the plot samples the involute the rows lie on.
    assert flank[: len(relief)] == relief
    for radius, x, y in rows[1 + len(relief):]:
        half = spec.custom_six_gap_half_angle_rad(radius)
        assert (x, y) == pytest.approx(
            (radius * math.sin(half), radius * math.cos(half) - rows[0][0]), abs=6e-4
        )
    assert flank[-1] == pytest.approx(rows[-1][1:], abs=6e-4)
    # The table at the default note height: 2.4 mm a character, measured on
    # the run-20261010T051729717Z render of this sheet (113 mm, 47 characters).
    widest = max(map(len, drawing.cutter_grind_data().splitlines()))
    table_right = drawing.CUTTER_DETAIL_POS[0] + widest * 0.0024
    plotted = [drawing.form_plot_xy(side * x, y) for x, y in flank for side in (1, -1)]
    for key, reach in drawing.FORM_PLOT_STATION_REACH_MM.items():
        radius = rows[-1][0] if key == "blank" else spec.stock_form_profile(6).template.relief_junction_radius_mm
        plotted.append(drawing.form_plot_xy(*drawing.form_plot_station_mm(radius, reach)))
    for text, (left, top) in drawing.form_plot_labels():
        width = max(map(len, text.splitlines())) * 0.0026
        plotted += [(left, top), (left + width, top - 0.005 * len(text.splitlines()))]
    xs, ys = zip(*plotted)
    assert min(xs) > table_right + 0.020
    assert max(xs) < 0.415
    # Above the title block (top 0.064) and below the border (0.267).
    assert min(ys) > 0.070 and max(ys) < 0.262


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
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): native D-bore dimensions carry its fit, and the Gear Data block
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


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_each_sheet_prints_the_tooth_runout_the_mesh_stack_books(teeth: int) -> None:
    import cone_set_stack

    assert (
        f"TOOTH CUTTING SETUP, ACCEPT AT SETUP:  {cone_set_stack.TOOTH_RUNOUT_TIR_MM:.2f} "
        "TIR MAX TO FINISHED BORE"
    ) in notes.gear_data(teeth)


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


def test_no_gdt_and_no_surface_finish() -> None:
    # ENFORCE round 1 of #971: a gear's D-bore does not run (rule 6), so
    # its Ra 1.6 went; the title block covers the rest.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "SURFACE_FINISHES")
    assert not hasattr(drawing, "bore_finish_xy")
    for module in (drawing, part):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "add_surface_finish" not in source
        assert "author_part_pmi" not in source


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
        assert right["BlankDia"][1] < drawing.GEAR_DATA_POS[1] - 0.035
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
# sheet format's 12.7 mm zone band (_drawing_sheet_region.sheet_drawable_region;
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
        # (the keep x) and running right, with its leader above. The pitch
        # circle line over the value adds one 4.9 mm row (run
        # 20261011T155111413Z).
        ctt_x, ctt_y = drawing.front_keep(teeth)["ToothThickness"]
        clock_box = (
            clock_x - drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y - drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
            clock_x + drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y + drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
        )
        ctt_box = (ctt_x - 0.001, ctt_y - 0.0078, ctt_x + 0.0642, ctt_y + 0.0137)
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


def test_settled_clocks_refuse_stub_arcs_on_any_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    sheets: list[str] = []
    ddoc = SimpleNamespace(ActivateSheet=lambda name: sheets.append(name) or True)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "_clock_arcs", lambda display: display)
    clocks = [("T012", [], 12), ("T018", [], 18)]
    with pytest.raises(RuntimeError, match=r"settling rebuild:\nT012: no arc\nT018: no arc"):
        drawing._assert_settled_clocks(SimpleNamespace(currentModel=ddoc), clocks)
    assert sheets == ["T012", "T018"]


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


# The functional root callout's widest row (the mate's, seventeen characters)
# is wider than either value.
_FLOOR_TEXT_HALF_WIDTH = (
    max(map(len, drawing.DIMENSION_CALLOUTS["FloorDia"].splitlines())) * 0.00185 / 2.0
)


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
    assert "blank_reference_geometry(" not in body
    assert "assert_reference_geometry_hidden_in_every_configuration(adapter, PART_NAME)" in body


def test_hide_and_show_is_set_with_each_configuration_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """7e88be269 T006 image: blanked with T120 active only, the axis and both
    sketches rendered in every other configuration."""
    from types import SimpleNamespace

    events: list[tuple[str, ...]] = []
    suppressed = SimpleNamespace(IsSuppressed2=lambda *_args: (True,))
    model = SimpleNamespace(
        GetConfigurationNames=lambda: [c for c, _t in spec.CONFIGS],
        FeatureByName=lambda _name: suppressed,
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(part, "_activate_configuration", lambda _m, c: events.append(("activate", c)))
    monkeypatch.setattr(part, "blank_reference_geometry", lambda _a, refs: events.append(("blank", *refs[0])))
    monkeypatch.setattr(part, "_blank_reference_sketches", lambda _a: events.append(("sketches",)))
    part._suppress_rows_and_hide_references(SimpleNamespace(currentModel=model), "Axis1")
    assert events == [
        event
        for configuration, _teeth in spec.CONFIGS
        for event in (("activate", configuration), ("blank", "Axis1", "AXIS"), ("sketches",))
    ]


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

    monkeypatch.setattr(readback, "_named_dimension", named)


def test_each_configuration_stores_its_own_gap_floor_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#834 Codex P1: the floor band is a native per-configuration LIMIT, one
    SetValues2 per configuration naming only that configuration."""
    tolerance = _FakeTolerance()
    _patch_floor_dimension(monkeypatch, tolerance)
    part._set_gap_floor_limits(object())
    assert tolerance.Type == 3  # swTolLIMIT
    assert [call[3] for call in tolerance.calls] == [[name] for name, _ in spec.CONFIGS]
    for (lower, upper, which, _names), (_name, teeth) in zip(
        tolerance.calls, spec.CONFIGS, strict=True
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
        assert [call[3] for call in calls] == [[c] for c, _ in spec.CONFIGS]
        for (lower, upper, which, _names), (_c, teeth) in zip(calls, spec.CONFIGS, strict=True):
            assert which == 3
            upper_mm, lower_mm = band_for(teeth)
            assert (lower * 1000.0, upper * 1000.0) == pytest.approx((lower_mm, upper_mm))


def test_the_reopened_audit_reads_each_band_with_its_own_configuration_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reopened audit reads every configuration's bands with that
    configuration active, and a failure names the call that raised (a raw
    COM error carries no member name, f68549253)."""
    import asyncio
    from types import SimpleNamespace

    active: list[str] = []
    banded: list[tuple[str, str, int]] = []

    async def activate(configuration: str) -> SimpleNamespace:
        active.append(configuration)
        return SimpleNamespace(is_success=True, data={"rebuilt": True}, error=None)

    async def topology(_adapter, configuration, teeth, *, phase, measure_roots):
        assert measure_roots and active[-1] == configuration
        return float(teeth), configuration, ()

    def bands(_adapter, configuration, teeth):
        banded.append((active[-1], configuration, teeth))
        if teeth == spec.CONFIGS[0][1]:
            raise AttributeError("member not found")

    monkeypatch.setattr(readback, "_configuration_topology", topology)
    monkeypatch.setattr(readback, "_assert_configuration_bands", bands)
    adapter = SimpleNamespace(set_active_configuration=activate)
    with pytest.raises(RuntimeError) as failure:
        asyncio.run(readback.assert_saved_configuration_topology(adapter))
    assert sorted(banded) == sorted((c, c, t) for c, t in spec.CONFIGS)
    message = str(failure.value)
    assert f"{spec.CONFIGS[0][0]}: AttributeError at line" in message
    assert "_assert_configuration_bands(adapter, configuration, teeth)" in message
    assert message.count("AttributeError") == 1


def test_only_the_front_view_shows_the_authoring_sketches() -> None:
    """The two inspection references belong only to Front; other views keep
    those hidden. The consumed BlankProfile is separately shown in Right."""
    for sketch in (spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH):
        owned = spec.DRAWING_DIMENSIONS[sketch]
        for teeth in spec.CONFIGURATION_TEETH:
            assert owned <= set(drawing.front_keep(teeth))
            assert not owned & set(drawing.right_keep(teeth))
            assert not owned & set(drawing.bore_view_keep(teeth))


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_side_blank_diameter_lane_clears_preserved_dimensions_and_iso(teeth: int) -> None:
    """Projected diameter witnesses and text have their own side-view lane."""
    half_face = drawing.rendered_half_face_width(teeth)
    half_od = drawing.rendered_half_od(teeth)
    cx, cy = drawing.RIGHT_CENTER
    blank_x, blank_y = drawing.right_keep(teeth)["BlankDia"]
    face_x, face_y = drawing.right_keep(teeth)["FaceWidth"]
    # The 22 mm lane is measured from the physical side silhouette, not the
    # end-view circle. At the bore axis a vertical linear diameter spans the
    # whole OD; its text cannot be lifted back onto the end view.
    assert blank_x == pytest.approx(cx + half_face + 0.022)
    assert blank_y == pytest.approx(cy)
    assert blank_x - (cx + half_face) >= 0.022 - 1e-12
    # The same mesh reason is stacked below the value rather than shortened;
    # bound its native multiline footprint independently of the model size.
    blank_half_width = 0.032 / 2.0
    blank_half_height = 0.020 / 2.0
    assert blank_x - blank_half_width > cx + half_face + 0.005
    # Standard isometric horizontal projection includes the axial face span,
    # not just the end-view radius; reserve another 5 mm around that silhouette.
    iso_half_span = (half_od + half_face) / math.sqrt(2.0)
    assert blank_x + blank_half_width < drawing.ISO_CENTER[0] - iso_half_span - 0.005
    # Keep the existing FaceWidth position independently of the new OD lane.
    expected_face_x = cx if 2.0 * half_face >= 0.040 else cx + half_face + 0.020
    assert (face_x, face_y) == pytest.approx((expected_face_x, cy - half_od - 0.017))
    assert face_y + 0.012 < cy - half_od
    assert face_y + 0.012 < blank_y - blank_half_height
    floor_x, _floor_y = drawing.front_keep(teeth)["FloorDia"]
    assert floor_x + _FLOOR_TEXT_HALF_WIDTH < cx - half_face - 0.020
    assert floor_x + _FLOOR_TEXT_HALF_WIDTH < blank_x - blank_half_width
    assert blank_y + blank_half_height < drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT


# Captured from the copied native cylinder positive control, 64.44 mm at 3:2:
# C:/farm-runs/fix-cone-gear-blank-od-20261020/positive-control-cylinder.
# These four segments are observed native ink; source projection is a separate
# input. The source_x below deliberately equals the observed witness start,
# not the unverified inferred cylinder projection x=.210.
_CYLINDER_NATIVE_BLANK_INK = [
    ((0.2112439, 0.22167), (0.249, 0.22167)),
    ((0.2112439, 0.31833), (0.249, 0.31833)),
    ((0.248, 0.22167), (0.248, 0.2571399)),
    ((0.248, 0.31833), (0.248, 0.2828601)),
]
_CYLINDER_TEST_PROJECTED_ENDS = [(0.2112439, 0.22167), (0.2112439, 0.31833)]


def test_native_cylinder_capture_accepts_split_axis_and_witness_overrun() -> None:
    assert drawing._blank_diameter_ink_problem(
        _CYLINDER_NATIVE_BLANK_INK, _CYLINDER_TEST_PROJECTED_ENDS, 0.248,
    ) is None


@pytest.mark.parametrize("gap", (0.0, 0.001244, 0.003))
def test_native_witness_start_allows_only_presentation_extension_gap(gap: float) -> None:
    # Synthetic projection inputs, not a claim about the captured CAD origin.
    ends = [(0.2112439 - gap, y) for _, y in _CYLINDER_TEST_PROJECTED_ENDS]
    assert drawing._blank_diameter_ink_problem(
        _CYLINDER_NATIVE_BLANK_INK, ends, 0.248,
    ) is None


@pytest.mark.parametrize("outside_arrows", (False, True))
def test_native_blank_axis_can_continue_outside_both_arrows(outside_arrows: bool) -> None:
    segments = list(_CYLINDER_NATIVE_BLANK_INK[:2])
    low, high = 0.22167, 0.31833
    extension = 0.006 if outside_arrows else 0.0
    segments.append(((0.248, low - extension), (0.248, high + extension)))
    assert drawing._blank_diameter_ink_problem(
        segments, _CYLINDER_TEST_PROJECTED_ENDS, 0.248,
    ) is None


def _bad_blank_ink(problem: str):
    segments = list(_CYLINDER_NATIVE_BLANK_INK)
    if problem == "horizontal-axis":
        segments[2:] = [((0.22167, 0.248), (0.31833, 0.248))]
    elif problem == "diagonal-axis":
        segments[2:] = [((0.247, 0.22167), (0.249, 0.31833))]
    elif problem == "wrong-span":
        segments[2:] = [((0.248, 0.224), (0.248, 0.316))]
    elif problem == "wrong-axis":
        segments[2:] = [((0.245, 0.22167), (0.245, 0.31833))]
    elif problem == "missing-upper-witness":
        del segments[1]
    elif problem == "missing-lower-witness":
        del segments[0]
    elif problem == "wrong-upper-origin":
        segments[1] = ((0.220, 0.31833), (0.249, 0.31833))
    elif problem == "wrong-lower-origin":
        segments[0] = ((0.220, 0.22167), (0.249, 0.22167))
    elif problem == "upper-witness-short":
        segments[1] = ((0.2112439, 0.31833), (0.247, 0.31833))
    elif problem == "lower-witness-short":
        segments[0] = ((0.2112439, 0.22167), (0.247, 0.22167))
    elif problem == "diagonal-witness":
        segments[1] = ((0.2112439, 0.317), (0.249, 0.31833))
    elif problem == "wrong-witness-span":
        segments[1] = ((0.2112439, 0.316), (0.249, 0.316))
    elif problem == "disconnected-witness":
        segments[1] = ((0.2112439, 0.31833), (0.215, 0.31833))
        segments.append(((0.244, 0.31833), (0.249, 0.31833)))
    elif problem == "extra-left-witness":
        segments.append(((0.200, 0.31833), (0.205, 0.31833)))
    elif problem == "extra-detached-witness":
        segments.append(((0.230, 0.31833), (0.235, 0.31833)))
    elif problem == "nan":
        segments[2] = ((math.nan, 0.22167), (0.248, 0.2571399))
    elif problem == "infinite":
        segments[1] = ((0.2112439, 0.31833), (math.inf, 0.31833))
    elif problem == "empty":
        segments = []
    else:
        raise AssertionError(problem)
    return segments


_BAD_BLANK_INK_CASES = (
    "horizontal-axis", "diagonal-axis", "wrong-span", "wrong-axis",
    "missing-upper-witness", "missing-lower-witness",
    "wrong-upper-origin", "wrong-lower-origin",
    "upper-witness-short", "lower-witness-short", "diagonal-witness",
    "wrong-witness-span", "disconnected-witness", "extra-left-witness",
    "extra-detached-witness", "nan", "infinite", "empty",
)


@pytest.mark.parametrize("start_offset", (-0.000101, 0.003101))
def test_native_witness_start_rejects_just_outside_gap_and_ink_slop(
    start_offset: float,
) -> None:
    segments = list(_CYLINDER_NATIVE_BLANK_INK)
    source_x = _CYLINDER_TEST_PROJECTED_ENDS[0][0]
    segments[1] = ((source_x + start_offset, 0.31833), (0.249, 0.31833))
    assert drawing._blank_diameter_ink_problem(
        segments, _CYLINDER_TEST_PROJECTED_ENDS, 0.248,
    )


@pytest.mark.parametrize("problem", _BAD_BLANK_INK_CASES)
def test_native_blank_ink_rejects_independent_geometry_failures(problem: str) -> None:
    result = drawing._blank_diameter_ink_problem(
        _bad_blank_ink(problem), _CYLINDER_TEST_PROJECTED_ENDS, 0.248,
    )
    assert isinstance(result, str) and result


@pytest.mark.parametrize(
    "ends",
    (
        [], [(0.2112439, 0.22167)],
        [(0.2112439, 0.22167), (0.2112439, 0.31833), (0.2112439, 0.4)],
        [(0.2112439, 0.22167), (0.215, 0.31833)],
        [(0.2112439, 0.22167), (0.2112439, 0.22167)],
        [(math.nan, 0.22167), (0.2112439, 0.31833)],
        [(0.2112439, 0.22167), (0.2112439, math.inf)],
    ),
)
def test_native_blank_ink_requires_two_finite_projected_diameter_limits(ends) -> None:
    assert drawing._blank_diameter_ink_problem(
        _CYLINDER_NATIVE_BLANK_INK, ends, 0.248,
    )


@pytest.mark.parametrize("line_x", (math.nan, math.inf, -math.inf))
def test_native_blank_ink_rejects_nonfinite_axis(line_x: float) -> None:
    assert drawing._blank_diameter_ink_problem(
        _CYLINDER_NATIVE_BLANK_INK, _CYLINDER_TEST_PROJECTED_ENDS, line_x,
    )


class _ImportedBlankDimension:
    """Read-only model data: presentation cannot rewrite size or bands."""

    __slots__ = ("Name", "values", "queries")

    def __init__(self, teeth: int, name: str = "BlankDia") -> None:
        self.Name = name
        self.values = {f"T{teeth:03d}": (spec.outside_dia_mm(teeth) / 1000.0,)}
        self.queries: list[tuple[int, str]] = []

    @property
    def SystemValue(self) -> float:
        raise AssertionError("Read the sheet configuration, not the active model")

    def GetSystemValue3(self, which: int, configuration: str) -> tuple[float, ...]:
        assert which == 3
        self.queries.append((which, configuration))
        return self.values[configuration]


class _ImportedBlankDisplay:
    def __init__(self, teeth: int, name: str = "BlankDia") -> None:
        self.dimension = _ImportedBlankDimension(teeth, name)
        self.kind = 6
        self.linear = False
        self.accept_linear = True
        self.annotation = _ImportedBlankAnnotation(self)
        self.segments = _blank_view_geometry(teeth)[1]

    @property
    def Type2(self) -> int:
        return self.kind

    @property
    def DisplayAsLinear(self) -> bool:
        return self.linear

    @DisplayAsLinear.setter
    def DisplayAsLinear(self, value: bool) -> None:
        if self.accept_linear:
            self.linear = value

    def SetVertical(self) -> bool:
        raise AssertionError("Native ink, not SetVertical's return, proves orientation")

    def GetAnnotation(self):
        return self.annotation

    def GetDimension2(self, index: int) -> _ImportedBlankDimension:
        assert index == 0
        return self.dimension


class _ImportedBlankAnnotation:
    def __init__(self, display: _ImportedBlankDisplay) -> None:
        self.display = display

    def GetSpecificAnnotation(self) -> _ImportedBlankDisplay:
        return self.display


def _blank_view_geometry(teeth: int):
    from types import SimpleNamespace

    numerator, denominator = drawing.SHEET_SCALES[f"T{teeth:03d}"]
    view = SimpleNamespace(
        source_x=drawing.RIGHT_CENTER[0],
        center_y=drawing.RIGHT_CENTER[1],
        scale=numerator / denominator,
    )
    radius = spec.outside_dia_mm(teeth) / 2000.0
    low, high = view.center_y - radius * view.scale, view.center_y + radius * view.scale
    line_x = drawing.right_keep(teeth)["BlankDia"][0]
    # A synthetic native-ink fixture, independent of the annotation's flag.
    segments = [
        ((view.source_x + 0.0012, low), (line_x + 0.001, low)),
        ((view.source_x + 0.0012, high), (line_x + 0.001, high)),
        ((line_x, low), (line_x, view.center_y - 0.004)),
        ((line_x, high), (line_x, view.center_y + 0.004)),
    ]
    return view, segments


@pytest.fixture
def native_blank_adapter(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace

    events = []
    active: list[str] = []
    model = SimpleNamespace(
        ActivateSheet=lambda name: active.append(name) or True,
        GraphicsRedraw2=lambda: events.append("redraw"),
    )
    adapter = SimpleNamespace(
        currentModel=model, active=active, curations=[],
        projections=[], ink_reads=[], events=events,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "dimension_name",
        lambda _adapter, annotation: annotation.GetSpecificAnnotation().dimension.Name,
    )

    def curate(_adapter, annotations, *, reposition):
        assert events and events[-1] == "redraw"
        events.append("curate")
        adapter.curations.append((annotations, reposition))

    def project(_adapter, view, points, *, label):
        adapter.projections.append((view, points, label))
        return [
            (view.source_x + x * view.scale, view.center_y + y * view.scale)
            for x, y, z in points
        ]

    def ink(annotation):
        events.append("ink")
        adapter.ink_reads.append(annotation)
        return annotation.display.segments

    monkeypatch.setattr(drawing, "curate_dimensions", curate)
    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "dimension_segments", ink)
    return adapter


@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
def test_imported_blank_has_native_vertical_ink_without_changing_model_data(
    native_blank_adapter, configuration: str, teeth: int,
) -> None:
    display = _ImportedBlankDisplay(teeth)
    view, _segments = _blank_view_geometry(teeth)
    original = dict(display.dimension.values)
    result = drawing._set_linear_blank_diameter(
        native_blank_adapter, [display.annotation], configuration, teeth, view,
    )
    assert result is display
    assert display.DisplayAsLinear
    assert display.Type2 == 6
    assert display.dimension.values == original
    assert display.dimension.queries
    assert set(display.dimension.queries) == {(3, configuration)}
    assert native_blank_adapter.curations == [
        ([display.annotation], {"BlankDia": drawing.right_keep(teeth)["BlankDia"]})
    ]
    assert native_blank_adapter.ink_reads == [display.annotation]
    projected_view, points, _label = native_blank_adapter.projections[-1]
    assert projected_view is view
    radius = original[configuration][0] / 2.0
    assert points == [(0, -radius, 0), (0, radius, 0)]


@pytest.mark.parametrize("problem", _BAD_BLANK_INK_CASES)
def test_blank_flag_and_position_cannot_substitute_for_native_ink(
    native_blank_adapter, problem: str,
) -> None:
    display = _ImportedBlankDisplay(6)
    view, _segments = _blank_view_geometry(6)
    line_x = drawing.right_keep(6)["BlankDia"][0]
    radius_on_sheet = spec.outside_dia_mm(6) / 2000.0 * view.scale

    def map_point(point):
        x, y = point
        return (
            view.source_x + (x - 0.2112439) * (line_x - view.source_x) / (0.248 - 0.2112439),
            view.center_y + (y - 0.270) * radius_on_sheet / (0.31833 - 0.270),
        )

    display.segments = [
        (map_point(start), map_point(end)) for start, end in _bad_blank_ink(problem)
    ]
    with pytest.raises(RuntimeError) as failure:
        drawing._set_linear_blank_diameter(
            native_blank_adapter, [display.annotation], "T006", 6, view,
        )
    assert "T006" in str(failure.value)
    assert "BlankDia" in str(failure.value)


def test_blank_redraw_precedes_reposition_and_native_ink(native_blank_adapter) -> None:
    display = _ImportedBlankDisplay(6)
    view, _segments = _blank_view_geometry(6)

    def redraw():
        assert display.DisplayAsLinear
        native_blank_adapter.events.append("redraw")

    native_blank_adapter.currentModel.GraphicsRedraw2 = redraw
    drawing._set_linear_blank_diameter(
        native_blank_adapter, [display.annotation], "T006", 6, view,
    )
    events = native_blank_adapter.events
    assert events.index("redraw") < events.index("curate")
    assert events.index("curate") < events.index("ink")


@pytest.mark.parametrize("kind", (0, 2, 3, 5, 12, 15))
def test_blank_rejects_wrong_native_type_before_reading_a_length(
    native_blank_adapter, kind: int,
) -> None:
    display = _ImportedBlankDisplay(6)
    display.kind = kind
    with pytest.raises(RuntimeError, match="native diameter"):
        drawing._set_linear_blank_diameter(
            native_blank_adapter, [display.annotation], "T006", 6, _blank_view_geometry(6)[0],
        )
    assert not display.dimension.queries
    assert not display.DisplayAsLinear


@pytest.mark.parametrize(
    "values", ((), (0.001,), (0.001, 0.002), (math.nan,), (math.inf,)),
)
def test_blank_rejects_wrong_or_ambiguous_configuration_value(
    native_blank_adapter, values: tuple[float, ...],
) -> None:
    display = _ImportedBlankDisplay(6)
    display.dimension.values["T006"] = values
    with pytest.raises(RuntimeError, match="BlankDia"):
        drawing._set_linear_blank_diameter(
            native_blank_adapter, [display.annotation], "T006", 6, _blank_view_geometry(6)[0],
        )
    assert not display.DisplayAsLinear


@pytest.mark.parametrize("names", ((), ("FaceWidth",), ("BlankDia", "BlankDia")))
def test_blank_requires_one_imported_model_dimension(
    native_blank_adapter, names: tuple[str, ...],
) -> None:
    annotations = [_ImportedBlankDisplay(6, name).annotation for name in names]
    with pytest.raises(RuntimeError, match="expected one BlankDia"):
        drawing._set_linear_blank_diameter(
            native_blank_adapter, annotations, "T006", 6, _blank_view_geometry(6)[0],
        )


@pytest.mark.parametrize("refusal", ("linear", "curation-revert", "value-drift", "type-drift"))
def test_blank_refuses_failed_or_unsettled_native_presentation(
    native_blank_adapter, monkeypatch: pytest.MonkeyPatch, refusal: str,
) -> None:
    display = _ImportedBlankDisplay(6)
    display.accept_linear = refusal != "linear"

    original_curate = drawing.curate_dimensions

    def curate(_adapter, annotations, *, reposition):
        original_curate(_adapter, annotations, reposition=reposition)
        if refusal == "curation-revert":
            display.linear = False
        if refusal == "value-drift":
            display.dimension.values["T006"] = (0.001,)
        if refusal == "type-drift":
            display.kind = 5

    monkeypatch.setattr(drawing, "curate_dimensions", curate)
    with pytest.raises(RuntimeError, match="BlankDia"):
        drawing._set_linear_blank_diameter(
            native_blank_adapter, [display.annotation], "T006", 6, _blank_view_geometry(6)[0],
        )


def test_blank_native_value_readback_returns_actual_metres(native_blank_adapter) -> None:
    display = _ImportedBlankDisplay(6)
    display.linear = True
    assert drawing._assert_blank_diameter_value(
        display, "T006", 6,
    ) == display.dimension.values["T006"][0]


def test_settled_blank_readback_checks_every_sheet(native_blank_adapter) -> None:
    blanks = []
    for configuration, teeth in spec.CONFIGS:
        display = _ImportedBlankDisplay(teeth)
        display.linear = True
        blanks.append((configuration, display, teeth, _blank_view_geometry(teeth)[0]))
    drawing._assert_settled_blank_diameters(native_blank_adapter, blanks)
    assert native_blank_adapter.active == list(drawing.GEAR_SHEET_NAMES)
    assert native_blank_adapter.ink_reads == [display.annotation for _, display, _, _ in blanks]
    for configuration, display, _teeth, _view in blanks:
        assert display.dimension.queries
        assert set(display.dimension.queries) == {(3, configuration)}


@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
@pytest.mark.parametrize("drift", ("circular", "value", "type", "ink"))
def test_settled_blank_refuses_native_regression_on_any_sheet(
    native_blank_adapter, configuration: str, teeth: int, drift: str,
) -> None:
    blanks = []
    for sheet, count in spec.CONFIGS:
        display = _ImportedBlankDisplay(count)
        display.linear = True
        blanks.append((sheet, display, count, _blank_view_geometry(count)[0]))
    original_activate = native_blank_adapter.currentModel.ActivateSheet

    def activate(sheet):
        if sheet == configuration:
            display = next(display for name, display, _, _ in blanks if name == sheet)
            if drift == "circular":
                display.linear = False
            elif drift == "value":
                display.dimension.values[configuration] = (0.001,)
            elif drift == "type":
                display.kind = 5
            else:
                display.segments = display.segments[:2]
        return original_activate(sheet)

    native_blank_adapter.currentModel.ActivateSheet = activate
    with pytest.raises(RuntimeError) as failure:
        drawing._assert_settled_blank_diameters(native_blank_adapter, blanks)
    assert configuration in str(failure.value)
    assert "BlankDia" in str(failure.value)


class _BlankReferencePart:
    """Tripwire at the actual view-to-part boundary, not disconnected state."""

    def __getattr__(self, name):
        raise AssertionError(f"drawing-only blank reference accessed part member {name}")


class _BlankReferenceView:
    def __init__(self, configuration, role, instance):
        self.name = f"Drawing View{instance}"
        self.component = f"cone-instance-{instance}"
        self.ReferencedConfiguration = configuration
        self.orientation = {
            "right": "*Right", "front": "*Front",
            "iso": "*Isometric", "bore": "*Front",
        }[role]
        self.shown = {"GapFloorReference"} if role == "front" else set()
        self.base = None

    def GetName2(self):
        return self.name

    def GetOrientationName(self):
        return self.orientation

    def RootDrawingComponent2(self, in_child_context):
        assert in_child_context is False
        from types import SimpleNamespace
        return SimpleNamespace(Name=self.component)

    def GetBaseView(self):
        return self.base


class _BlankReferenceDrawing:
    """Selection/ownership state only; not a simulator of native printed ink."""

    def __init__(self):
        self.views = {}
        part_model = _BlankReferencePart()
        for configuration, _teeth in spec.CONFIGS:
            for role in ("front", "right", "iso", "bore"):
                view = _BlankReferenceView(configuration, role, len(self.views) + 1)
                view.ReferencedDocument = part_model
                self.views[configuration, role] = view
        self.Extension = self
        self.active = None
        self.selected = None
        self.refused_activation = set()
        self.refused_selection = set()
        self.attempts = []
        self.unblanked = []

    def ActivateView(self, name):
        if name in self.refused_activation:
            return False
        self.active = next(view for view in self.views.values() if view.name == name)
        return True

    def ClearSelection2(self, all_marks):
        assert all_marks is True
        self.selected = None

    def SelectByID2(self, name, kind, x, y, z, append, mark, callout, option):
        assert (kind, x, y, z, append, mark, option) == (
            "SKETCH", 0.0, 0.0, 0.0, False, 0, 0,
        )
        self.attempts.append(name)
        self.selected = None
        if name in self.refused_selection:
            return False
        for view in self.views.values():
            if name == f"BlankProfile@{view.component}@{view.name}":
                if self.active is not view:
                    return False
                self.selected = (view, "BlankProfile")
                return True
        return False

    def UnblankSketch(self):
        assert self.selected is not None
        view, sketch = self.selected
        assert self.active is view
        view.shown.add(sketch)
        self.unblanked.append((view, sketch))
        # SolidWorks returns void, not a success Boolean.
        return None


@pytest.fixture
def blank_reference_adapter(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace
    import _drawing_dimension_import

    # Keep the actual view-name/component qualifier and show primitive. Only
    # COM binding/null marshalling is replaced at this offline boundary.
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(_drawing_dimension_import, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(drawing.hidden_sketches, "null_callout", lambda: None)

    def member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    return SimpleNamespace(
        currentModel=_BlankReferenceDrawing(), _get_attr_or_call=member,
    )


def test_blank_reference_persists_only_in_each_exact_right_view(blank_reference_adapter):
    adapter = blank_reference_adapter
    draw = adapter.currentModel
    original = {key: set(view.shown) for key, view in draw.views.items()}
    for index, (configuration, _teeth) in enumerate(spec.CONFIGS, start=1):
        right = draw.views[configuration, "right"]
        drawing._show_blank_profile(adapter, right)
        assert draw.active is right
        assert draw.selected is None
        assert draw.attempts[-1] == f"BlankProfile@{right.component}@{right.name}"
        assert len(draw.unblanked) == index
        # Check all eighty persistent owners after EACH show, not just the
        # last active view or twenty independent throwaway fake documents.
        visited = set(drawing.GEAR_SHEET_NAMES[:index])
        for (sheet, role), view in draw.views.items():
            added = {"BlankProfile"} if role == "right" and sheet in visited else set()
            assert view.shown == original[sheet, role] | added


@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
@pytest.mark.parametrize("failure", ("activation", "exact-selection", "base-fallback"))
def test_blank_reference_refuses_without_showing_another_owner(
    blank_reference_adapter, configuration, teeth, failure,
):
    adapter = blank_reference_adapter
    draw = adapter.currentModel
    right = draw.views[configuration, "right"]
    front = draw.views[configuration, "front"]
    # An available base qualifier is tempting but must NEVER be tried.
    right.base = front
    exact = f"BlankProfile@{right.component}@{right.name}"
    if failure == "activation":
        draw.refused_activation.add(right.name)
    else:
        draw.refused_selection.add(exact)
        if failure == "exact-selection":
            right.base = None
    draw.ActivateView(front.name)
    before = {key: set(view.shown) for key, view in draw.views.items()}
    with pytest.raises(RuntimeError, match="activate|cannot select"):
        drawing._show_blank_profile(adapter, right)
    assert draw.attempts == ([] if failure == "activation" else [exact])
    assert not draw.unblanked
    assert draw.selected is None
    assert {key: view.shown for key, view in draw.views.items()} == before


@pytest.mark.parametrize("role", ("front", "iso", "bore"))
@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
def test_blank_reference_rejects_nonright_targets_before_activation(
    blank_reference_adapter, configuration, teeth, role,
):
    adapter = blank_reference_adapter
    draw = adapter.currentModel
    right = draw.views[configuration, "right"]
    draw.ActivateView(right.name)
    before = {key: set(view.shown) for key, view in draw.views.items()}
    with pytest.raises(RuntimeError, match=r"requires \*Right"):
        drawing._show_blank_profile(adapter, draw.views[configuration, role])
    assert draw.active is right
    assert not draw.attempts
    assert not draw.unblanked
    assert {key: view.shown for key, view in draw.views.items()} == before


@pytest.mark.parametrize("configuration,teeth", spec.CONFIGS)
def test_build_shows_configured_blank_reference_before_right_import(
    blank_reference_adapter, monkeypatch: pytest.MonkeyPatch, configuration, teeth,
):
    """Exercise build wiring; the fake selection state cannot prove printing."""
    import asyncio
    from types import SimpleNamespace

    class RightImportReached(Exception):
        pass

    adapter = blank_reference_adapter
    draw = adapter.currentModel
    roles = ("front", "right", "iso", "bore")
    views = tuple(draw.views[configuration, role] for role in roles)
    for view in views:
        view.ReferencedConfiguration = "not-yet-configured"
    original = {key: set(view.shown) for key, view in draw.views.items()}
    placement = iter(views)
    configured = []

    async def open_model(_source):
        return True

    async def topology(_adapter, *, phase):
        pass

    def no_op(*args, **kwargs):
        pass

    def activate_sheet(sheet):
        assert sheet == configuration
        return True

    def place(_adapter, _source, orientation, x, y, *, scale):
        view = next(placement)
        assert orientation == view.orientation
        return view

    def rebuild(_adapter, *, label):
        # Keep the real _configure_views assignment/readback. This checkpoint
        # also rejects moving the show operation before configuration.
        assert all(view.ReferencedConfiguration == configuration for view in views)
        assert not draw.unblanked
        configured.append(configuration)

    def import_other_view(_adapter, view, **kwargs):
        assert view in (views[0], views[3])
        draw.ActivateView(view.name)
        return []

    def right_import(_adapter, view, *, keep, view_label):
        right = views[1]
        assert configured == [configuration]
        assert view is right
        assert right.ReferencedConfiguration == configuration
        assert draw.active is right
        assert draw.selected is None
        assert draw.unblanked == [(right, "BlankProfile")]
        assert draw.attempts == [f"BlankProfile@{right.component}@{right.name}"]
        for key, owner in draw.views.items():
            added = {"BlankProfile"} if owner is right else set()
            assert owner.shown == original[key] | added
        raise RightImportReached

    monkeypatch.setattr(drawing, "SOURCE", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(drawing, "CONFIGURATION_TEETH", (teeth,))
    monkeypatch.setattr(adapter, "open_model", open_model, raising=False)
    monkeypatch.setattr(draw, "ActivateSheet", activate_sheet, raising=False)
    monkeypatch.setattr(drawing, "check", no_op)
    monkeypatch.setattr(drawing, "assert_saved_configuration_topology", topology)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *a, **k: (draw, None))
    for name in (
        "read_required_properties", "_assert_dimension_arrow_length",
        "create_blank_drawing_sheets", "stamp_drawing_summary",
        "set_hidden_lines_removed", "_hide_tangent_edges", "_assert_tooth_geometry",
        "_center_bore_view", "_sweep_clock_right_of_flat", "_crop_bore_view",
    ):
        monkeypatch.setattr(drawing, name, no_op)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", import_other_view)
    monkeypatch.setattr(drawing, "_curate_repeated_dimensions", right_import)
    with pytest.raises(RightImportReached):
        asyncio.run(drawing.build(adapter))


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
