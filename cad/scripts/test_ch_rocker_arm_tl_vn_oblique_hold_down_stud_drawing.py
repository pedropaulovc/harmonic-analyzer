"""Shared PM-kit stud rework, native drawing and conditional-fit contracts.

Calibration bounds are hypothetical, NOT verified Precision Matthews kit
bands. Native calls are recorded, never run.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_sh_vn_clamping_kit_hardware as part
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_jig_assembly_spec as jig
import sh_vn_clamping_kit_hold_down_stud_spec as spec
import draw_sh_vn_clamping_kit_hardware as draw
from _feature_requirements import requirements_for
from _gtol_face import FaceGeometry, SURFACE_CONE
from _hole_spec import THREAD_MAJOR_MM

STEM = "sh-vn-clamping-kit-hardware"
ROW = _config.parts(STEM)
CONFIGURATION = "HoldDownStud"
I = spec.MeasuredInterval


def _conditional_calibration(**changes):
    """Contract's conditional comparison, with invented-fixture lower spans explicit."""
    values = {
        "finished_length": I(57.2 - 0.8, 57.2 + 0.8),
        "base_bar_thickness": I(12.7 - 0.51, 12.7 + 0.51),
        "moving_block_height": I(28.0, 28.0),
        "lower_insertion": I(22.0, 22.0),
        "original_lower_insertion": I(22.0, 22.0),
        "nut_span": I(17.5, 17.5),
        "washer_stack": I(0.0, 0.0),
        "upper_thread_setback": I(0.0, 1.0),
        "lower_factory_thread_start": I(0.0, 1.0),
        "lower_loaded_interval": I(2.0, 20.0),
        "thread_pitch_mm": 25.4 / 13.0,
    }
    values.update(changes)
    return values


def test_registry_row_is_the_purchased_pm_kit_stud() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Precision Matthews"
    assert ROW["supplier_skus"] == [spec.SKU] == ["52PCCK-9/16-14mm"]
    assert ROW["material"] == spec.MATERIAL
    assert ROW["usage_scope"] == "tooling"


def test_quantity_is_c4s_hold_down_count() -> None:
    assert int(ROW["configuration_quantities"][CONFIGURATION]) == spec.QUANTITY == fasteners.HOLD_DOWN_STUD_COUNT == 4
    assert ROW["configuration_quantities"] == {"HoldDownStud": 4, "TNut": 4, "FlangeNut": 4}
    assert int(ROW["quantity"]) == sum(ROW["configuration_quantities"].values()) == 12


def test_stud_size_matches_the_hold_down_stack() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert spec.LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM == jig.STUD_LENGTH
    assert spec.MAJOR_DIA == base_bar.HOLD_DOWN_STUD_DIA == jig.STUD_DIA
    assert math.isclose(spec.MAJOR_DIA, THREAD_MAJOR_MM[spec.THREAD])


def test_profile_closes_on_the_axis_from_the_origin() -> None:
    assert spec.PROFILE[0] == (0.0, 0.0)
    assert spec.PROFILE[-1] == (spec.LENGTH, 0.0)
    assert max(r for _, r in spec.PROFILE) == spec.MAJOR_DIA / 2.0


def test_manufactured_rework_retains_actual_stock_and_property_provenance() -> None:
    assert ROW["number"] == "MHA-SH-VN-57"
    assert ROW["tolerance_class"] == "visual_noncritical"
    assert ROW["material"] == spec.MATERIAL == "Plain Carbon Steel"
    assert ROW["material_specification"] == "Hardened steel"
    member = part.MEMBER_PROPERTIES[CONFIGURATION]
    assert member["Process"] == spec.PROCESS
    assert member["Process"].startswith("rework purchased PM ")
    assert member["Tolerance Class"] == spec.TOLERANCE_CLASS == "machined_block"
    assert member["Finish"] == spec.FINISH == "BLACK OXIDE AS SUPPLIED; OIL BARE CUT END"
    assert member["Stock Length"] == "3 IN STOCK"
    assert "57.2" not in ROW["stock_name"]
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert part.STUD_REWORK_PROPERTIES == draw.STUD_REWORK_PROPERTIES
    assert set(draw.REQUIRED_PROPERTIES) <= set(part.SAVED_DRAWING_PROPERTIES)
    assert {"Material Specification", "Finish"} <= set(part.SAVED_DRAWING_PROPERTIES)
    assert part.MEMBER_DESCRIPTIONS[CONFIGURATION] == spec.BOM_DESCRIPTION
    assert spec.BOM_DESCRIPTION == "1/2-13 STUD, CUT 57.2"
    for configuration in ("TNut", "FlangeNut"):
        other = part.MEMBER_PROPERTIES[configuration]
        assert other["Finish"] == ROW["finish"] == "black oxide, as supplied"
        assert other["Manufacturing Notes"] == part.MEMBER_SPECS[configuration].DRAWING_NOTES
        assert not ({"Process", "Tolerance Class", *part.STUD_REWORK_PROPERTIES} - {"Manufacturing Notes"}) & set(other)
        assert not any(name.startswith("Stud ") for name in other)


def test_finished_and_stock_lengths_are_separate_shared_authorities() -> None:
    assert spec.THREAD == fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert spec.STOCK_LENGTH == fasteners.HOLD_DOWN_STUD_STOCK_LENGTH == "3"
    assert spec.STOCK_LENGTH_MM == fasteners.HOLD_DOWN_STUD_STOCK_LENGTH_MM == 76.2
    assert spec.LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM == 57.2
    assert spec.LENGTH_PLACES == fasteners.HOLD_DOWN_STUD_LENGTH_PLACES == 1
    assert spec.LENGTH_BAND == fasteners.HOLD_DOWN_STUD_LENGTH_BAND == 0.8
    assert spec.THREAD_PITCH_MM == fasteners.HOLD_DOWN_STUD_PITCH_MM == 25.4 / 13
    assert spec.MAJOR_DIA == base_bar.HOLD_DOWN_STUD_DIA
    assert spec.CLEARANCE_MIN == 3.0 and spec.COMPLETE_PROJECTION_PITCHES == 1.0
    source = Path(spec.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"win32com", "solidworks_mcp", "_com"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
            assert all(not alias.name.startswith("build_") for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden
            assert not (node.module or "").startswith("build_")
    assert "UNVERIFIED" in spec.__doc__ and "ESTIMATED" in spec.__doc__
    assert spec.SOURCE_URL in spec.__doc__


def test_finished_envelope_keeps_lower_factory_end_and_axis() -> None:
    assert spec.PROFILE[:3] == ((0.0, 0.0), (0.0, spec.RADIUS - 1.0), (1.0, spec.RADIUS))
    assert spec.PROFILE[-3:] == ((56.2, spec.RADIUS), (57.2, spec.RADIUS - 1.0), (57.2, 0.0))
    assert part.hold_down_stud_profile_points() == [(0.0, 0.0), (spec.RADIUS, 0.0), (spec.RADIUS, spec.LENGTH), (0.0, spec.LENGTH)]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Front Plane", 0.0, "Right Plane", 0.0' in source
    assert 'name_last_feature(adapter, "ScrewAxis")' in source


def test_closed_form_volume_matches_a_numeric_revolve() -> None:
    def radius(y: float) -> float:
        for (y0, r0), (y1, r1) in zip(spec.PROFILE, spec.PROFILE[1:]):
            if y0 <= y <= y1 and y1 > y0:
                return r0 + (r1 - r0) * (y - y0) / (y1 - y0)
        raise AssertionError(y)

    n = 20000
    dy = spec.LENGTH / n
    numeric = sum(math.pi * radius((i + 0.5) * dy) ** 2 * dy for i in range(n))
    assert math.isclose(spec.VOLUME_MM3, numeric, rel_tol=1e-6)


def test_native_dimension_maps_cover_every_manufacturing_control_once() -> None:
    assert spec.DRAWING_DIMENSIONS == {
        "StudProfile": {"FinishedLength"}, "CutEndChamfer": {"CutEndChamfer"},
    }
    assert {feature: set(row) for feature, row in spec.DRAWING_PRECISION.items()} == spec.DRAWING_DIMENSIONS
    assert set(draw.FRONT_KEEP) | set(draw.END_KEEP) == set(spec.DRAWING_PRECISION_BY_NAME)
    assert set(draw.FRONT_KEEP).isdisjoint(draw.END_KEEP)
    assert spec.DRAWING_PRECISION_BY_NAME == {"FinishedLength": 1, "CutEndChamfer": 1}
    assert spec.DIMENSION_TOLERANCE_TYPES == {"FinishedLength": 0, "CutEndChamfer": 6}
    assert all(not any(char.isdigit() for char in text) for text in spec.DIMENSION_CALLOUTS.values())
    fields = requirements_for(draw)
    assert set(fields) == {"finished_upper_end", "cut_end_chamfer"}
    assert fields["finished_upper_end"].fields["length"][0] == [56.4, 58.0]
    assert fields["cut_end_chamfer"].fields["length"][0] == [0.0, 1.0]
    assert "LENGTH_BAND" in fields["finished_upper_end"].fields["length"][1]


def test_length_callout_screen_uses_captured_native_font_and_paper_lane() -> None:
    # Captured native sheet: approximately 2.45 mm/character, border X12.7,
    # Front outline X101.7. This 2.50 approximation is not native ink proof.
    advance_mm = 2.50
    width_mm = max(map(len, spec.DIMENSION_CALLOUTS["FinishedLength"].splitlines())) * advance_mm
    centre_mm = draw.FRONT_KEEP["FinishedLength"][0] * 1000.0
    border_mm, front_outline_mm = 12.7, 101.7
    assert centre_mm - width_mm / 2.0 > border_mm
    assert centre_mm + width_mm / 2.0 < front_outline_mm


def test_thread_callout_screen_fits_between_native_length_line_and_left_barrel() -> None:
    # Approximate offline screen only: native ink/leader routing remains required.
    left_mm = draw.THREAD_NOTE_XY[0] * 1000.0
    width_mm = max(map(len, draw.THREAD_CALLOUT.splitlines())) * 2.50
    assert draw.FRONT_KEEP["FinishedLength"][0] * 1000.0 < left_mm
    assert left_mm + width_mm < 107.3


def test_feature_selector_distinguishes_actual_cut_end_from_factory_chamfer() -> None:
    selector = requirements_for(draw)["cut_end_chamfer"].faces[0]

    def cone(low_y, high_y):
        return FaceGeometry(
            None, SURFACE_CONE, (0, 0, 0, 0, 1, 0, spec.RADIUS / 1000, math.pi / 4), None,
            (-spec.RADIUS / 1000, low_y / 1000, -spec.RADIUS / 1000,
             spec.RADIUS / 1000, high_y / 1000, spec.RADIUS / 1000),
        )

    assert selector.matches(cone(spec.LENGTH - spec.CUT_END_CHAMFER_MAX, spec.LENGTH))
    assert not selector.matches(cone(0.0, spec.LOWER_FACTORY_CHAMFER))


def test_conditional_full_finished_band_passes_but_old_stock_band_fails() -> None:
    result = spec.measured_fit_bounds(**_conditional_calibration())
    assert result.clearance_min_mm == pytest.approx(4.19)
    assert result.complete_projection_min_mm == pytest.approx(2.69)
    assert result.required_projection_mm == pytest.approx(25.4 / 13)
    assert result.full_actual_nut_span_retained and result.lower_loaded_interval_retained
    assert result.insertion_unchanged and result.acceptable
    old = spec.measured_fit_bounds(**_conditional_calibration(finished_length=I(76.2 - 0.8, 76.2 + 0.8)))
    assert old.clearance_min_mm == pytest.approx(-14.81)
    assert not old.acceptable
    # A nominal-only height that happens to pass cannot certify its wider band.
    nominal = spec.measured_fit_bounds(**_conditional_calibration(moving_block_height=I(26.1, 26.1), finished_length=I(57.2, 57.2)))
    actual = spec.measured_fit_bounds(**_conditional_calibration(moving_block_height=I(26.1, 26.1)))
    assert nominal.acceptable and not actual.acceptable


@pytest.mark.parametrize("delta, accepted", [(-0.001, False), (0.001, True)])
def test_clearance_boundary_on_both_sides(delta, accepted) -> None:
    values = _conditional_calibration()
    threshold = spec.CLEARANCE_MIN + values["finished_length"].upper_mm - values["base_bar_thickness"].lower_mm - values["lower_insertion"].lower_mm
    values["moving_block_height"] = I(threshold + delta, threshold + delta)
    result = spec.measured_fit_bounds(**values)
    assert result.clearance_min_mm == pytest.approx(spec.CLEARANCE_MIN + delta)
    assert result.acceptable is accepted


@pytest.mark.parametrize("delta, accepted", [(-0.001, True), (0.001, False)])
def test_complete_pitch_projection_boundary_on_both_sides(delta, accepted) -> None:
    values = _conditional_calibration()
    maximum_nut = (
        values["finished_length"].lower_mm - values["lower_insertion"].upper_mm
        - values["base_bar_thickness"].upper_mm - values["washer_stack"].upper_mm
        - values["upper_thread_setback"].upper_mm - spec.THREAD_PITCH_MM
    )
    values["nut_span"] = I(maximum_nut + delta, maximum_nut + delta)
    result = spec.measured_fit_bounds(**values)
    assert result.complete_projection_min_mm == pytest.approx(spec.THREAD_PITCH_MM - delta)
    assert result.acceptable is accepted


@pytest.mark.parametrize("change", [
    {"nut_span": I(18.5, 18.5)},
    {"washer_stack": I(0.8, 0.8)},
    {"base_bar_thickness": I(13.7 - 0.51, 13.7 + 0.51)},
    {"upper_thread_setback": I(0.0, 2.0)},
])
def test_actual_nut_washer_anchor_stack_and_complete_thread_setback_change_the_bound(change) -> None:
    result = spec.measured_fit_bounds(**_conditional_calibration(**change))
    assert result.complete_projection_min_mm < spec.THREAD_PITCH_MM
    assert not result.acceptable
    assert spec.CUT_END_CHAMFER_MAX == 1.0  # does not imply measured U <= 1


def test_deeper_insertion_cannot_rescue_a_failed_clearance() -> None:
    values = _conditional_calibration(moving_block_height=I(26.5, 26.5))
    assert not spec.measured_fit_bounds(**values).acceptable
    values["lower_insertion"] = I(22.5, 22.5)
    result = spec.measured_fit_bounds(**values)
    assert result.clearance_min_mm > spec.CLEARANCE_MIN
    assert result.complete_projection_min_mm > spec.THREAD_PITCH_MM
    assert not result.insertion_unchanged and not result.acceptable


def test_full_actual_nut_span_and_original_lower_loaded_threads_are_retained() -> None:
    nut = spec.measured_fit_bounds(**_conditional_calibration(nut_span=I(21.0, 21.0)))
    assert not nut.full_actual_nut_span_retained and not nut.acceptable
    lower = spec.measured_fit_bounds(**_conditional_calibration(lower_factory_thread_start=I(2.5, 2.5)))
    assert lower.full_actual_nut_span_retained and not lower.lower_loaded_interval_retained
    assert not lower.acceptable
    cut_loaded_threads = spec.measured_fit_bounds(**_conditional_calibration(finished_length=I(20.0, 20.0)))
    assert not cut_loaded_threads.lower_loaded_interval_retained and not cut_loaded_threads.acceptable


@pytest.mark.parametrize("bad", [(-1.0, 0.0), (2.0, 1.0), (math.nan, 1.0), (0.0, math.inf)])
def test_unknown_or_invalid_measurement_intervals_are_not_nominal_defaults(bad) -> None:
    with pytest.raises(ValueError):
        I(*bad)


def test_every_actual_fit_input_is_required_and_unknown_never_becomes_verified() -> None:
    assert all(parameter.default is inspect.Parameter.empty for parameter in inspect.signature(spec.measured_fit_bounds).parameters.values())
    with pytest.raises(TypeError):
        spec.measured_fit_bounds()
    values = _conditional_calibration(nut_span=None)
    with pytest.raises(ValueError, match="explicit MeasuredInterval"):
        spec.measured_fit_bounds(**values)
    for pitch in (0.0, -1.0, math.inf, math.nan):
        with pytest.raises(ValueError, match="pitch"):
            spec.measured_fit_bounds(**_conditional_calibration(thread_pitch_mm=pitch))
    assert not hasattr(spec.measured_fit_bounds(**_conditional_calibration()), "verified")


class _Tolerance:
    def __init__(self, kind=0, values=(0.0, 0.0), *, accepts=True, drift=0.0):
        self.Type, self.values, self.accepts, self.drift = kind, values, accepts, drift

    def SetValues(self, lower, upper):
        self.values = lower, upper
        return self.accepts

    def GetMinValue(self):
        return self.values[0]

    def GetMaxValue(self):
        return self.values[1] + self.drift


@pytest.mark.parametrize("failure", [None, "reference", "nominal", "reject", "readback"])
def test_actual_cut_feature_gets_native_max_without_forcing_driven_state(monkeypatch, failure) -> None:
    tolerance = _Tolerance(accepts=failure != "reject", drift=1e-5 if failure == "readback" else 0.0)
    dimension = SimpleNamespace(
        DrivenState=1 if failure == "reference" else 2,
        SystemValue=spec.CUT_END_CHAMFER_MAX / 1000 + (0.001 if failure == "nominal" else 0.0),
        Tolerance=tolerance,
    )
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (None, dimension))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    if failure:
        with pytest.raises(RuntimeError):
            part._author_cut_end_maximum(object())
    else:
        part._author_cut_end_maximum(object())
        assert tolerance.Type == 6 and tolerance.values == (-0.001, 0.0)
    assert dimension.DrivenState == (1 if failure == "reference" else 2)


@pytest.mark.parametrize("chamfers", [(1.0, 1.0), (0.6, 1.2)])
@pytest.mark.parametrize("end", ["lower_factory", "upper_cut"])
@pytest.mark.parametrize("failure", [None, "missing", "duplicate"])
def test_end_note_and_presentation_resolve_exact_visible_rim_not_projected_centre(monkeypatch, failure, end, chamfers):
    monkeypatch.setattr(spec, "LOWER_FACTORY_CHAMFER", chamfers[0])
    monkeypatch.setattr(spec, "CUT_END_CHAMFER_MAX", chamfers[1])
    lower_radius = (spec.RADIUS - spec.LOWER_FACTORY_CHAMFER) / 1000
    upper_radius = (spec.RADIUS - spec.CUT_END_CHAMFER_MAX) / 1000
    radius = lower_radius if end == "lower_factory" else upper_radius
    y = 0.0 if end == "lower_factory" else spec.LENGTH / 1000
    selector = draw.lower_factory_end_edge if end == "lower_factory" else draw.upper_cut_end_edge


    def edge(params, *, circle=True):
        curve = SimpleNamespace(IsCircle=lambda: circle, CircleParams=params)
        return SimpleNamespace(GetCurve=lambda: curve)

    lower = edge((0.0, 0.0, 0.0, 0.0, -1.0, 0.0, lower_radius))
    upper = edge((0.0, spec.LENGTH / 1000, 0.0, 0.0, 1.0, 0.0, upper_radius))
    target, other = (lower, upper) if end == "lower_factory" else (upper, lower)
    shoulder = edge((0.0, spec.LOWER_FACTORY_CHAMFER / 1000, 0.0, 0.0, 1.0, 0.0, spec.RADIUS / 1000))
    wrong_radius = edge((0.0, y, 0.0, 0.0, 1.0, 0.0, spec.RADIUS / 1000))
    wrong_axis = edge((0.0, y, 0.0, 1.0, 0.0, 0.0, radius))
    noncircle = edge(None, circle=False)
    edges = [other, shoulder, wrong_radius, wrong_axis, noncircle]
    if failure != "missing":
        edges.append(target)
    if failure == "duplicate":
        edges.append(edge((0.0, y, 0.0, 0.0, 1.0, 0.0, radius)))
    view = object()
    monkeypatch.setattr(draw, "visible_view_entities", lambda owner, kind, *, label: edges)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    if failure:
        with pytest.raises(RuntimeError, match="expected one visible native rim"):
            selector(view)
    else:
        assert selector(view) is target


@pytest.mark.parametrize("failure", [
    None, "lower_attachment", "thread_attachment",
    "lower_landing", "landing", "late_landing",
])
def test_rework_notes_keep_native_feature_attachment_and_noncorner_landings(monkeypatch, failure):
    monkeypatch.setattr(spec, "LOWER_FACTORY_CHAMFER", 0.6)
    monkeypatch.setattr(spec, "CUT_END_CHAMFER_MAX", 1.2)
    lower_rim, barrel_face, neighbour = object(), object(), object()
    flank = SimpleNamespace(GetFace=lambda: barrel_face)
    other_flank = SimpleNamespace(GetFace=lambda: neighbour)
    front = object()
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: 1 if a is b else 0))
    projected = []
    late = False
    selected = {}
    inserted = []

    def select(owner, view, kind, xy, *, label, entity):
        selected.clear()
        selected.update(entity=entity, kind=kind)
        return entity

    def set_point(index, mark, x, y, z):
        selected["point"] = (x, y)
        return True

    def project(owner, view, points, *, label):
        projected.append(points)
        return [(0.120 + 2.0 * x, 0.093 + 2.0 * y) for x, y, _z in points]

    def silhouettes(owner, view, picks, *, label):
        _cylinder, xy = picks["thread"]
        from _drawing_edges import _segment_distance

        if _segment_distance(xy, (0.1073, 0.2052), (0.1073, 0.0948)) > 1e-5:
            raise RuntimeError("no native barrel silhouette passes through the requested point")
        return {"thread": flank}

    def insert(text):
        inserted.append(text)
        record = dict(selected)
        thread = record["kind"] == "SILHOUETTE"
        actual = record["entity"]
        if failure == "thread_attachment" and thread:
            actual = other_flank
        elif failure == "lower_attachment" and not thread:
            actual = neighbour

        def position(x, y, z):
            record["note_xy"] = (x, y)
            return True

        def leader(_index):
            x, y = record["point"]
            if thread and (failure == "landing" or (failure == "late_landing" and late)):
                y += 0.010
            if not thread and failure == "lower_landing":
                x += 0.010
            return (*record["note_xy"], 0.0, x, y, 0.0)

        annotation = SimpleNamespace(
            SetLeader3=lambda *_args: 0,
            SetPosition2=position,
            GetAttachedEntities3=lambda: (actual,),
            GetAttachedEntityCount3=lambda: 1,
            GetAttachedEntityTypes=lambda: (46 if thread else 1,),
            GetLeaderCount=lambda: 1,
            IsDangling=lambda: False,
            GetLeaderPointsAtIndex=leader,
        )
        return SimpleNamespace(GetAnnotation=lambda: annotation)

    adapter.currentModel = SimpleNamespace(
        SelectionManager=SimpleNamespace(SetSelectionPoint2=set_point),
        InsertNote=insert,
        ClearSelection2=lambda _all: None,
    )
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "model_points_in_view", project)
    monkeypatch.setattr(draw, "face_silhouettes_through", silhouettes)
    monkeypatch.setattr(draw, "lower_factory_end_edge", lambda view: lower_rim)
    monkeypatch.setattr(draw, "_select_view_entity", select)
    monkeypatch.setattr(draw, "rebuild_drawing", lambda _adapter, **_kwargs: None)
    if failure and failure != "late_landing":
        with pytest.raises(RuntimeError):
            draw.add_rework_notes(adapter, front)
        return
    settled = draw.add_rework_notes(adapter, front)
    assert inserted == [
        draw.property_link(f"{CONFIGURATION} Rework Lower End Note"),
        draw.THREAD_CALLOUT,
    ]
    lower, thread = projected[0]
    rim_radius = (spec.RADIUS - spec.LOWER_FACTORY_CHAMFER) / 1000
    assert lower[1] == 0.0 and 0.0 < lower[0] < rim_radius
    assert math.hypot(lower[0], lower[2]) == pytest.approx(rim_radius)
    assert thread[0] == -spec.RADIUS / 1000 and thread[2] == 0.0
    assert spec.LOWER_FACTORY_CHAMFER / 1000 < thread[1] < (spec.LENGTH - spec.CUT_END_CHAMFER_MAX) / 1000
    late = True
    if failure == "late_landing":
        with pytest.raises(RuntimeError, match="leader attachment moved"):
            settled()
    else:
        settled()


@pytest.mark.parametrize("failure", [
    None, "missing", "duplicate", "name_value", "number_value", "sheet", "view",
])
def test_local_title_fit_preserves_full_name_number_and_never_touches_material(monkeypatch, failure):
    number = ROW["number"]
    name_link = draw.property_link("SW-Title(Title)")
    number_link = draw.property_link("Number")

    def note(link, text):
        return SimpleNamespace(PropertyLinkedText=link, GetText=lambda: text)

    name = note(
        f"<FONT size=15PTS>{name_link}",
        "shortened name" if failure == "name_value" else draw.PART_STEM,
    )
    number_note = note(number_link, "wrong" if failure == "number_value" else number)
    material = note(draw.property_link("Material"), ROW["material"])
    notes = [name, number_note, material]
    if failure == "missing":
        notes.remove(number_note)
    if failure == "duplicate":
        notes.append(note(number_link, number))
    for index, item in enumerate(notes):
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        item.GetNext = lambda next_note=next_note: next_note
    sheet = object()
    sheet_view = SimpleNamespace(GetFirstNote2=lambda: notes[0])
    active = []
    document = SimpleNamespace(
        GetCurrentSheet=lambda: None if failure == "sheet" else sheet,
        GetFirstView=lambda: None if failure == "view" else sheet_view,
        ActivateSheet=lambda value: active.append(value) or True,
    )
    adapter = SimpleNamespace(currentModel=document)
    fitted, settled = [], []

    def fit(_adapter, drawing, actual_sheet, item, *, label, minimum):
        assert _adapter is adapter and drawing is document and actual_sheet is sheet
        fitted.append((item, label, minimum))
        return lambda: settled.append((item, active[-1]))

    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "_fit_title_note", fit)
    if failure:
        with pytest.raises(RuntimeError):
            draw.fit_stud_title_block(adapter, sheet_name="REWORK", number=number)
    else:
        check_title = draw.fit_stud_title_block(adapter, sheet_name="REWORK", number=number)
        assert [(item, minimum) for item, _label, minimum in fitted] == [
            (name, 0.003), (number_note, 0.003),
        ]
        assert material not in [item for item, _label, _minimum in fitted]
        check_title()
        assert active == ["REWORK"]
        assert settled == [(name, "REWORK"), (number_note, "REWORK")]
        document.ActivateSheet = lambda _name: False
        with pytest.raises(RuntimeError, match="failed to activate"):
            check_title()


@pytest.mark.parametrize("failure", [None, "missing", "duplicate"])
def test_existing_thread_callout_targets_upper_cylindrical_boundary_not_cut_face(monkeypatch, failure):
    radius = spec.RADIUS / 1000
    y = (spec.LENGTH - spec.CUT_END_CHAMFER_MAX) / 1000

    def edge(at_y, at_radius):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(0.0, at_y, 0.0, 0.0, 1.0, 0.0, at_radius),
        )
        return SimpleNamespace(GetCurve=lambda: curve)

    thread_rim = edge(y, radius)
    edges = [
        edge(0.0, radius - spec.LOWER_FACTORY_CHAMFER / 1000),
        edge(spec.LOWER_FACTORY_CHAMFER / 1000, radius),
        edge(spec.LENGTH / 1000, radius - spec.CUT_END_CHAMFER_MAX / 1000),
        edge(y, radius - spec.CUT_END_CHAMFER_MAX / 1000),
    ]
    if failure != "missing":
        edges.append(thread_rim)
    if failure == "duplicate":
        edges.append(edge(y, radius))
    monkeypatch.setattr(draw, "visible_view_entities", lambda *_args, **_kwargs: edges)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    if failure:
        with pytest.raises(RuntimeError, match="expected one visible native rim"):
            draw.upper_thread_blank_edge(object())
    else:
        assert draw.upper_thread_blank_edge(object()) is thread_rim
    assert spec.THREAD in draw.THREAD_CALLOUT
    assert "2A" not in draw.THREAD_CALLOUT  # No fabricated qualification of kit stock.


@pytest.mark.parametrize("failure", [
    None, "missing", "duplicate", "name_value", "number_value", "sheet", "view",
])
def test_local_title_fit_preserves_full_name_number_and_never_touches_material(monkeypatch, failure):
    number = ROW["number"]
    name_link = draw.property_link("SW-Title(Title)")
    number_link = draw.property_link("Number")

    def note(link, text):
        return SimpleNamespace(PropertyLinkedText=link, GetText=lambda: text)

    name = note(
        f"<FONT size=15PTS>{name_link}",
        "shortened name" if failure == "name_value" else draw.PART_STEM,
    )
    number_note = note(number_link, "wrong" if failure == "number_value" else number)
    material = note(draw.property_link("Material"), ROW["material"])
    notes = [name, number_note, material]
    if failure == "missing":
        notes.remove(number_note)
    if failure == "duplicate":
        notes.append(note(number_link, number))
    for index, item in enumerate(notes):
        next_note = notes[index + 1] if index + 1 < len(notes) else None
        item.GetNext = lambda next_note=next_note: next_note
    sheet = object()
    sheet_view = SimpleNamespace(GetFirstNote2=lambda: notes[0])
    active = []
    document = SimpleNamespace(
        GetCurrentSheet=lambda: None if failure == "sheet" else sheet,
        GetFirstView=lambda: None if failure == "view" else sheet_view,
        ActivateSheet=lambda value: active.append(value) or True,
    )
    adapter = SimpleNamespace(currentModel=document)
    fitted, settled = [], []

    def fit(_adapter, drawing, actual_sheet, item, *, label, minimum):
        assert _adapter is adapter and drawing is document and actual_sheet is sheet
        fitted.append((item, label, minimum))
        return lambda: settled.append((item, active[-1]))

    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "_fit_title_note", fit)
    if failure:
        with pytest.raises(RuntimeError):
            draw.fit_stud_title_block(adapter, sheet_name="REWORK", number=number)
    else:
        check_title = draw.fit_stud_title_block(
            adapter, sheet_name="REWORK", number=number,
        )
        assert [(item, minimum) for item, _label, minimum in fitted] == [
            (name, 0.003), (number_note, 0.003),
        ]
        assert material not in [item for item, _label, _minimum in fitted]
        check_title()
        assert active == ["REWORK"]
        assert settled == [(name, "REWORK"), (number_note, "REWORK")]
        document.ActivateSheet = lambda _name: False
        with pytest.raises(RuntimeError, match="failed to activate"):
            check_title()


@pytest.mark.parametrize("failure", [
    None, "feature", "definition", "type", "angle", "degrees", "length_as_angle",
    "nan", "infinite", "distance",
])
def test_saved_cutting_feature_owns_angle_not_imported_length(monkeypatch, failure):
    angle = {
        "angle": math.pi / 3, "degrees": 45.0, "length_as_angle": 0.001,
        "nan": math.nan, "infinite": math.inf,
    }.get(failure, math.pi / 4)
    sides = []

    def distance(side):
        sides.append(side)
        return 0.002 if failure == "distance" else 0.001

    definition = SimpleNamespace(
        Type=2 if failure == "type" else 1, EdgeChamferAngle=angle,
        GetEdgeChamferDistance=distance,
    )
    feature = SimpleNamespace(GetDefinition=lambda: None if failure == "definition" else definition)
    lookups = []

    def lookup(name):
        lookups.append(name)
        return None if failure == "feature" else feature

    # The shared producer's drawing adapter must never be retargeted to a part.
    model = SimpleNamespace(FeatureByName=lookup)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    if failure:
        with pytest.raises(RuntimeError):
            draw.read_saved_cut_end_angle(model)
    else:
        assert draw.read_saved_cut_end_angle(model) == pytest.approx(math.pi / 4)
        assert sides == [0]
    assert lookups == ["CutEndChamfer"]


class _Display:
    def __init__(self, name, value, tolerance, *, state=2, reference=False):
        self.name = name
        feature = "StudProfile" if name == "FinishedLength" else "CutEndChamfer"
        self.primary = SimpleNamespace(
            SystemValue=value, DrivenState=state, Tolerance=tolerance,
            FullName=f"{name}@{feature}@{STEM}.Part",
        )
        self.Type2 = 2  # The native imported chamfer driver is a linear dimension.
        self.reference = reference

    def GetDimension2(self, index):
        assert index == 0, "linear display must never be queried for a second angular driver"
        return self.primary

    def GetText(self, index):
        return {1: "(", 2: ")"}.get(index, "") if self.reference else ""


@pytest.mark.parametrize("failure", [
    None, "nominal", "reference", "brackets", "type", "band", "display_type",
    "missing", "duplicate", "factory_feature", "unqualified", "callable_full_name",
])
def test_sheet_requires_actual_native_drivers_and_max_not_retyped_dimensions(monkeypatch, failure) -> None:
    length = _Display("FinishedLength", spec.LENGTH / 1000, _Tolerance())
    chamfer = _Display("CutEndChamfer", 0.001, _Tolerance(6, (-0.001, 0.0)))
    if failure == "nominal":
        length.primary.SystemValue = spec.STOCK_LENGTH_MM / 1000
    elif failure == "reference":
        length.primary.DrivenState = 1
    elif failure == "brackets":
        length.reference = True
    elif failure == "type":
        chamfer.primary.Tolerance.Type = 0
    elif failure == "band":
        chamfer.primary.Tolerance.values = (-0.001, 0.0001)
    elif failure == "display_type":
        chamfer.Type2 = 10  # compound chamfer, not the imported linear MAX control
    elif failure == "factory_feature":
        chamfer.primary.FullName = f"CutEndChamfer@LowerFactoryChamfer@{STEM}.Part"
    elif failure == "unqualified":
        chamfer.primary.FullName = "CutEndChamfer@CutEndChamfer"
    elif failure == "callable_full_name":
        chamfer.primary.FullName = lambda: f"CutEndChamfer@CutEndChamfer@{STEM}.Part"
    displays = [length, chamfer]
    if failure == "missing":
        displays.pop()
    elif failure == "duplicate":
        displays.append(length)
    annotations = [SimpleNamespace(GetSpecificAnnotation=lambda d=display: d, display=display) for display in displays]
    precision_calls = []
    monkeypatch.setattr(draw, "dimension_name", lambda _adapter, note: note.display.name)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "assert_imported_precision", lambda adapter, notes, precision: precision_calls.append((notes, precision)))
    if failure:
        with pytest.raises(RuntimeError):
            draw.assert_machining_controls(object(), annotations)
    else:
        draw.assert_machining_controls(object(), annotations)
        assert precision_calls == [(annotations, spec.DRAWING_PRECISION_BY_NAME)]


@pytest.mark.parametrize("failure", [
    None, "missing_chamfer", "duplicate_chamfer", "side_chamfer", "sheet_owner",
    "wrong_owner", "missing_owner", "factory_end_view", "back_view", "missing_view",
    "iso_chamfer",
])
def test_final_views_reacquire_exact_controls_with_native_owners_and_orientation(monkeypatch, failure):
    length = _Display("FinishedLength", spec.LENGTH / 1000, _Tolerance())
    chamfer = _Display("CutEndChamfer", 0.001, _Tolerance(6, (-0.001, 0.0)))
    front = SimpleNamespace(name="Drawing View1", GetOrientationName=lambda: "*Back" if failure == "back_view" else "*Front")
    end = SimpleNamespace(name="Drawing View2", GetOrientationName=lambda: "*Bottom" if failure == "factory_end_view" else "*Top")
    iso = SimpleNamespace(name="Drawing View3")

    def annotation(display, owner):
        return SimpleNamespace(
            GetSpecificAnnotation=lambda: display, display=display,
            Owner=owner, OwnerType=0,
        )

    length_note, chamfer_note = annotation(length, front), annotation(chamfer, end)
    if failure == "sheet_owner":
        chamfer_note.OwnerType = 1
    elif failure == "wrong_owner":
        chamfer_note.Owner = front
    elif failure == "missing_owner":
        chamfer_note.Owner = None
    front_notes = [length_note]
    end_notes = [] if failure == "missing_chamfer" else [chamfer_note]
    if failure == "duplicate_chamfer":
        end_notes.append(chamfer_note)
    elif failure == "side_chamfer":
        front_notes.append(chamfer_note)
        end_notes.clear()
        chamfer_note.Owner = front
    note = SimpleNamespace(display=SimpleNamespace(name=""))
    front.GetAnnotations = lambda: [*front_notes, note]
    end.GetAnnotations = lambda: end_notes
    iso.GetAnnotations = lambda: [annotation(chamfer, iso)] if failure == "iso_chamfer" else []
    precision_calls, rim_checks = [], []
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "dimension_name", lambda _adapter, item: item.display.name)
    monkeypatch.setattr(draw, "view_name", lambda _adapter, view: view.name)
    monkeypatch.setattr(draw, "iter_views", lambda _adapter: [front, iso] if failure == "missing_view" else [front, end, iso])
    monkeypatch.setattr(draw, "upper_cut_end_edge", lambda owner: rim_checks.append(owner))
    monkeypatch.setattr(draw, "assert_imported_precision", lambda _adapter, values, _precision: precision_calls.append(values))
    if failure:
        with pytest.raises(RuntimeError):
            draw.assert_rework_view_controls(object(), front, end)
    else:
        draw.assert_rework_view_controls(object(), front, end)
        assert precision_calls == [[length_note, chamfer_note]]
        assert rim_checks == [end]


@pytest.mark.parametrize("failure", [
    None, "stale_chamfer", "stale_length", "missing_chamfer", "missing_length",
])
def test_native_callouts_keep_length_governance_and_feature_derived_angle(monkeypatch, failure):
    length = _Display("FinishedLength", spec.LENGTH / 1000, _Tolerance())
    chamfer = _Display("CutEndChamfer", 0.001, _Tolerance(6, (-0.001, 0.0)))
    displays = [length, chamfer]
    if failure == "missing_length":
        displays.remove(length)
    elif failure == "missing_chamfer":
        displays.remove(chamfer)
    annotations = [
        SimpleNamespace(GetSpecificAnnotation=lambda d=display: d, display=display)
        for display in displays
    ]
    applied, text = [], {}

    def apply(_adapter, notes, callouts):
        applied.append((notes, callouts))
        text.update(callouts)
        if failure == "stale_chamfer":
            text["CutEndChamfer"] = "stale"
        elif failure == "stale_length":
            text["FinishedLength"] = "stale"

    length.GetText = lambda index: text.get("FinishedLength", "") if index == 4 else ""
    chamfer.GetText = lambda index: text.get("CutEndChamfer", "") if index == 4 else ""
    monkeypatch.setattr(draw, "dimension_name", lambda _adapter, note: note.display.name)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "set_dimension_callouts", apply)
    if failure:
        with pytest.raises(RuntimeError):
            draw.set_machining_callouts(object(), annotations, math.pi / 6)
    else:
        draw.set_machining_callouts(object(), annotations, math.pi / 6)
        assert text["CutEndChamfer"] == "X 30° CUT END"
        assert text["FinishedLength"] == spec.DIMENSION_CALLOUTS["FinishedLength"]
        assert applied[0][0] is annotations
        assert length.primary.SystemValue == spec.LENGTH / 1000
        assert chamfer.primary.SystemValue == 0.001
        assert chamfer.primary.Tolerance.Type == 6
        assert chamfer.primary.Tolerance.values == (-0.001, 0.0)




class _StudAdapter:
    def __init__(self):
        self.constraints, self.dimensions, self.chamfers, self.names = [], [], [], []
        self.parts, self.sketches, self.revolves = 0, [], []

    @staticmethod
    def result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    async def create_part(self):
        self.parts += 1
        return self.result()

    async def create_sketch(self, plane):
        self.sketches.append(plane)
        return self.result()

    async def add_centerline(self, *points):
        self.axis = points
        return self.result("Axis")

    async def add_sketch_constraint(self, first, second, kind):
        self.constraints.append((first, second, kind))
        return self.result()

    async def add_sketch_dimension(self, first, second, kind, value):
        self.dimensions.append((first, second, kind, value))
        return self.result("D")

    async def exit_sketch(self):
        return self.result()

    async def create_revolve(self, params):
        self.revolves.append(params)
        return self.result()

    async def add_chamfer(self, distance, edge_points, *, tangent_propagation):
        self.chamfers.append((distance, edge_points, tangent_propagation))
        return self.result()


def test_native_recipe_uses_one_true_length_driver_and_independent_end_features(monkeypatch) -> None:
    adapter = _StudAdapter()
    applied, marks = [], []

    async def no_native(*_args, **_kwargs):
        return None

    async def chain(_adapter, points):
        assert points == part.hold_down_stud_profile_points()
        return ["L0", "L1", "L2", "L3"]

    for name in ("ensure_fully_defined", "volume_check", "bbox_extent_check"):
        monkeypatch.setattr(part, name, no_native)
    monkeypatch.setattr(part, "add_line_chain", chain)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "name_last_feature", lambda _adapter, name: adapter.names.append(name))
    monkeypatch.setattr(part.SketchDims, "apply", lambda dims, _adapter, name: applied.append((name, dims._rows)))
    monkeypatch.setattr(part, "name_dimensions", lambda _adapter, feature, names: applied.append((feature, names)))
    monkeypatch.setattr(part, "_author_cut_end_maximum", lambda *_args: None)
    monkeypatch.setattr(part, "apply_drawing_precision", lambda _adapter, precision: applied.append(("precision", precision)))
    monkeypatch.setattr(part, "mark_dimensions_for_drawing", lambda _adapter, feature, names: marks.append((feature, names)))
    asyncio.run(part._author_hold_down_stud(adapter))
    assert adapter.parts == 0 and adapter.sketches == ["Front"]
    assert adapter.axis == (0.0, 0.0, 0.0, spec.LENGTH)
    assert [params.angle for params in adapter.revolves] == [360.0]
    assert adapter.dimensions == [
        ("L1.start", "L1.end", "vertical_distance", spec.LENGTH),
        ("L0.start", "L0.end", "horizontal_distance", spec.RADIUS),
    ]
    assert applied[:2] == [("StudProfile", [("FinishedLength", None), ("MajorRadius", None)]), ("CutEndChamfer", ["CutEndChamfer"])]
    assert adapter.constraints == [
        ("L0", None, "horizontal"), ("L1", None, "vertical"),
        ("L2", None, "horizontal"), ("L3", None, "vertical"),
        ("L0.start", "origin", "coincident"),
    ]
    assert adapter.chamfers == [
        (spec.LOWER_FACTORY_CHAMFER, [[spec.RADIUS, 0.0, 0.0]], False),
        (spec.CUT_END_CHAMFER_MAX, [[spec.RADIUS, spec.LENGTH, 0.0]], False),
    ]
    assert adapter.names == ["StudProfile", "Stud", "LowerFactoryChamfer", "CutEndChamfer"]
    assert dict(marks) == spec.DRAWING_DIMENSIONS


def test_rework_sheet_does_not_duplicate_fixture_qualification() -> None:
    assert draw.SHEET_NAMES == ("REWORK",)
    assert draw.HOLD_DOWN_REFERENCE == jig.HOLD_DOWN_REFERENCE
    assert not hasattr(draw, "INSTRUCTION_PLACEMENTS")
    assert set(draw.STUD_REWORK_PROPERTIES) == {"Stock Length", "Stock Note", "Lower End Note"}
    for name in part.SAVED_DRAWING_PROPERTIES:
        assert "Stud Measurement Instructions" not in name
        assert "Stud Fit Limits" not in name
        assert "Stud Rework Acceptance" not in name
    assert part.MEMBER_NOTE_PROPERTIES[f"{CONFIGURATION} Manufacturing Notes"] == "REWORKED STUD; SEE REWORK."


@pytest.mark.parametrize("drift", [None, "configuration", "source", "scale", "activation"])
def test_drawing_keeps_native_chamfer_end_view_and_part_only_rework_sheet(monkeypatch, tmp_path, drift) -> None:
    source = tmp_path / "stud.SLDPRT"
    source.touch()
    active, views, curated, notes, configured = [], [], [], [], []
    source_model = object()

    class Drawing:
        refuse = False

        def ActivateSheet(self, name):
            active.append(name)
            return not self.refuse

    document = Drawing()
    adapter = _StudAdapter()
    adapter.currentModel = document

    def place(_adapter, _source, orientation, *position, scale):
        assert Path(_source) == source
        view = SimpleNamespace(
            sheet=active[-1], orientation=orientation, position=position,
            ScaleRatio=scale, ReferencedConfiguration="Default",
            ReferencedDocument=source_model, GetReferencedModelName=lambda: str(source),
        )
        views.append(view)
        return view

    def configure(_adapter, configuration, selected):
        assert configuration == CONFIGURATION
        configured.append(list(selected))
        for view in selected:
            view.ReferencedConfiguration = configuration

    def curate(_adapter, view, *, keep, view_label, dimensions_by_feature):
        assert view.ReferencedConfiguration == CONFIGURATION
        curated.append((view, keep, dimensions_by_feature))
        return list(keep)

    monkeypatch.setattr(draw, "SOURCE", source)
    property_reads = []

    def properties(model):
        property_reads.append(model)
        return {"Number": ROW["number"]}

    monkeypatch.setattr(draw, "_assert_stud_rework_properties", properties)
    saved_angle_calls = []
    monkeypatch.setattr(draw, "read_saved_cut_end_angle", lambda model: saved_angle_calls.append(model) or math.pi / 4)
    monkeypatch.setattr(draw, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(draw, "place_view", place)
    monkeypatch.setattr(draw, "configure_reference_views", configure)
    monkeypatch.setattr(draw, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(draw, "curate_view_dimensions", curate)
    control_calls, owner_checks = [], []
    monkeypatch.setattr(draw, "assert_machining_controls", lambda _adapter, annotations: control_calls.append(annotations))
    monkeypatch.setattr(draw, "assert_rework_view_controls", lambda _adapter, front, end: owner_checks.append((front, end)))
    callouts = []
    monkeypatch.setattr(draw, "set_machining_callouts", lambda _adapter, annotations, angle: callouts.append((annotations, angle)))
    rework_note_views, notes_settled = [], []

    def rework_notes(_adapter, view):
        rework_note_views.append(view)
        notes.extend([
            ("REWORK", f"{CONFIGURATION} Rework Lower End Note", None),
            ("REWORK", "Existing Thread", None),
        ])
        return lambda: notes_settled.append(view)

    monkeypatch.setattr(draw, "add_rework_notes", rework_notes)
    title_calls, title_settled = [], []

    def fit_title(_adapter, *, sheet_name, number):
        title_calls.append((active[-1], sheet_name, number))
        return lambda: title_settled.append(sheet_name)

    monkeypatch.setattr(draw, "fit_stud_title_block", fit_title)
    monkeypatch.setattr(draw, "add_property_linked_note", lambda _adapter, name, *position, **kwargs: notes.append((active[-1], name, kwargs.get("char_height"))))
    captions = []
    monkeypatch.setattr(draw, "add_note", lambda _adapter, text, *xy: captions.append((text, xy)) or object())
    checks = draw.append_stud_rework_sheets(adapter)
    assert active == list(draw.SHEET_NAMES) == ["REWORK"]
    assert [view.orientation for view in views] == ["*Front", "*Top", "*Isometric"]
    assert all(view.ScaleRatio == draw.SHEET_SCALE for view in views)
    assert configured == [views]
    assert all(view.ReferencedConfiguration == CONFIGURATION for view in views)
    assert [(keep, dimensions) for _view, keep, dimensions in curated] == [
        (draw.FRONT_KEEP, spec.DRAWING_DIMENSIONS),
        (draw.END_KEEP, spec.DRAWING_DIMENSIONS),
    ]
    assert control_calls == [["FinishedLength", "CutEndChamfer"]]

    assert callouts == [(["FinishedLength", "CutEndChamfer"], math.pi / 4)]
    assert saved_angle_calls == [source_model]
    assert adapter.currentModel is document
    assert rework_note_views == [views[0]]
    assert title_calls == [("REWORK", "REWORK", ROW["number"])]
    assert notes == [
        ("REWORK", f"{CONFIGURATION} Rework Lower End Note", None),
        ("REWORK", "Existing Thread", None),
        ("REWORK", f"{CONFIGURATION} Rework Stock Note", None),
    ]
    assert (draw.END_VIEW_LABEL, draw.END_VIEW_LABEL_XY) in captions
    assert (f"INSTALLED ACCEPTANCE:\n{jig.HOLD_DOWN_REFERENCE}", draw.ASSEMBLY_REFERENCE_XY) in captions
    if drift == "configuration":
        views[-1].ReferencedConfiguration = "TNut"
    elif drift == "source":
        views[0].GetReferencedModelName = lambda: str(tmp_path / "wrong.SLDPRT")
    elif drift == "scale":
        views[1].ScaleRatio = (1.0, 1.0)
    elif drift == "activation":
        document.refuse = True
    if drift:
        with pytest.raises(RuntimeError):
            checks[0]()
    else:
        for check in checks:
            check()
        assert property_reads == [source_model, source_model]
        assert control_calls == [["FinishedLength", "CutEndChamfer"]]
        assert owner_checks == [(views[0], views[1])] * 2
        assert notes_settled == [views[0]]
        assert title_settled == ["REWORK"]


def test_shared_drawing_uses_one_configured_supplier_sheet_and_appended_stud_sheets(monkeypatch) -> None:
    calls = []

    async def configured_drawing(adapter, drawing_spec, **kwargs):
        calls.append((adapter, drawing_spec, kwargs))
        return {"pdf": "recorded"}

    monkeypatch.setattr(draw, "build_purchased_variant_drawing", configured_drawing)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "recorded"}
    assert len(calls) == 1
    assert calls[0][:2] == (adapter, draw.SPEC)
    options = calls[0][2]
    assert tuple(name for name, _label in options["variants"]) == part.CONFIGURATIONS
    assert options["annotate_member"] is draw.annotate_member
    assert options["append_sheets"] is draw.append_stud_rework_sheets
    assert options["additional_sheet_scales"] == {name: draw.SHEET_SCALE for name in draw.SHEET_NAMES}


@pytest.mark.parametrize("drift", [None, "Finish", "Process", "Quantity", "Stock Length", "document_note"])
def test_stud_sheet_requires_native_member_and_source_linked_rework_properties(monkeypatch, drift) -> None:
    common = {
        "Number": ROW["number"], "Material Specification": ROW["material_specification"],
        **{f"{CONFIGURATION} Rework {name}": value for name, value in draw.STUD_REWORK_PROPERTIES.items()},
    }
    native = {
        **part.MEMBER_PROPERTIES[CONFIGURATION],
        "Number": ROW["number"], "Quantity": str(spec.QUANTITY),
    }
    if drift == "document_note":
        common[f"{CONFIGURATION} Rework Lower End Note"] = "stale"
    elif drift:
        native[drift] = "stale"
    monkeypatch.setattr(draw, "read_required_properties", lambda *_args, **_kwargs: common)
    model = SimpleNamespace(GetCustomInfoValue=lambda configuration, name: native[name])
    if drift:
        with pytest.raises(RuntimeError):
            draw._assert_stud_rework_properties(model)
    else:
        draw._assert_stud_rework_properties(model)


def test_shared_native_builder_retains_material_member_suppression_and_save_guards(monkeypatch) -> None:
    events = []
    adapter = _StudAdapter()

    async def record(name, *args):
        events.append((name, *args))

    def async_recorder(name):
        async def called(*args, **kwargs):
            await record(name, *args[1:], kwargs)
        return called

    def recorder(name):
        return lambda *args, **kwargs: events.append((name, *args, kwargs))

    for name in (
        "create_member_configurations", "activate_member", "select_member_features",
        "name_bore_axis", "apply_material", "apply_color", "report_mass_properties",
        "_author_hold_down_stud", "_author_t_nut", "_author_flange_nut",
    ):
        monkeypatch.setattr(part, name, async_recorder(name))
    for name in (
        "require_member_configurations", "name_last_feature", "set_member_suppression",
        "blank_reference_geometry", "apply_custom_properties", "apply_drawing_properties",
        "apply_member_properties", "require_saved_drawing_properties",
    ):
        monkeypatch.setattr(part, name, recorder(name))

    async def save(_adapter, name, configurations, *, material, readback):
        assert name == STEM and configurations == part.CONFIGURATIONS
        assert material == spec.MATERIAL and readback is part._readback
        events.append(("save",))
        return {"part": "recorded"}

    monkeypatch.setattr(part, "save_member_part", save)
    assert asyncio.run(part.build(adapter)) == {"part": "recorded"}
    assert adapter.parts == 1
    assert part.MEMBER_FEATURES[CONFIGURATION] == (
        "StudProfile", "Stud", "LowerFactoryChamfer", "CutEndChamfer",
    )
    assert [event[0] for event in events if event[0].startswith("_author_")] == [
        "_author_hold_down_stud", "_author_t_nut", "_author_flange_nut",
    ]
    assert [event[1] for event in events if event[0] == "apply_material"] == [spec.MATERIAL] * 3
    assert [event[2] for event in events if event[0] == "apply_member_properties"] == [STEM] * 3
    assert [event[3] for event in events if event[0] == "apply_member_properties"] == list(part.CONFIGURATIONS)
    assert [event[5] for event in events if event[0] == "apply_member_properties"] == [
        part.MEMBER_PROPERTIES[name] for name in part.CONFIGURATIONS
    ]
    property_events = [event for event in events if event[0] == "apply_drawing_properties"]
    assert property_events == [("apply_drawing_properties", adapter, STEM, part.MEMBER_NOTE_PROPERTIES, {})]
    assert events[-2:] == [
        ("save",),
        ("require_saved_drawing_properties", adapter, part.SAVED_DRAWING_PROPERTIES, {}),
    ]
