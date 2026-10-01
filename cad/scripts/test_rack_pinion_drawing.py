"""Offline contracts for the rack-pinion drawing (batch gear pattern)."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _rack_bore_finish as finish_helper
import build_rack_pinion as part
import draw_rack_pinion as drawing
import rack_pinion_spec as spec
import transgear_disc_hub_geometry as hub_geometry
import transgear_disc_screw_spec as disc_screw
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rack-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rack-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rack-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["rack_pinion"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_is_kept_once_with_part_authored_places() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.RIGHT_KEEP]
    assert sorted(kept) == sorted(marked) == ["BoreDia", "FaceWidth"]
    # R9-5: the thickness is functional and prints .XXX; the bore .XXX.
    assert spec.DRAWING_PRECISION_BY_NAME == {"FaceWidth": 3, "BoreDia": 3}
    assert "draw_rack_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    # The bore's reamed slip band is the one model-authored band.
    assert model_toleranced_dimensions(part) == {
        ("BoreProfile", "BoreDia"): "*BORE_DEVIATIONS",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_the_disc_prints_no_tap_position() -> None:
    """R9-9: the taps are transferred from the MHA-159 flange at assembly."""
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
    """R9-47: the MHA-161 tips are cut to fit inside the rear face, so the
    joint (judged in transgear_disc_screw_spec) spends the tap's losses here."""
    assert spec.TAP_SPEC.size == hub_geometry.SCREW_THREAD == "#0-80"
    assert disc_screw.ENGAGEMENT_WORST_D >= spec.ENGAGEMENT_FLOOR_D == 1.5
    assert (
        disc_screw.ENGAGEMENT_WORST
        < disc_screw.ENGAGEMENT_NOMINAL
        < spec.FACE_WIDTH - spec.CSK_THREAD_LOSS
    )


def test_disc_tap_drill_cuts_a_2b_minor_at_about_80_percent_thread() -> None:
    """The 3/64 (1.191) tap drill for the MHA-161 #0-80 UNF-2B disc taps,
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
    assert spec.CSK_TO_BORE_WORST >= 1.5


def test_the_bore_slips_on_the_sleeve_spigot_at_every_limit() -> None:
    """The bands the two builds apply (the disc's bore, the MHA-110 sleeve's
    spigot) leave clearance at the tightest corner: the smallest bore over
    the largest spigot, and the fit note quotes the same clearance."""
    import build_transgear_feed_pinion as sleeve_part
    import transgear_feed_pinion_spec as sleeve

    assert (
        model_toleranced_dimensions(sleeve_part)[("SleeveProfile", "SpigotDia")]
        == "*SPIGOT_DIA_DEVIATIONS"
    )
    bore_lower, bore_upper = spec.BORE_DEVIATIONS
    spigot_lower, spigot_upper = sleeve.SPIGOT_DIA_DEVIATIONS
    least = (spec.BORE_DIA + bore_lower) - (sleeve.SPIGOT_DIA + spigot_upper)
    greatest = (spec.BORE_DIA + bore_upper) - (sleeve.SPIGOT_DIA + spigot_lower)
    assert least > 0.0
    assert (least, greatest) == pytest.approx(spec.SPIGOT_DIAMETRAL_CLEARANCE)
    # The disc's float on the spigot feeds the transferred taps' wall.
    assert spec.DISC_OFFSET_MAX == pytest.approx(greatest / 2.0)
    note = spec.BORE_FIT_CALLOUT
    assert f"MATE SLEEVE {sleeve.SLEEVE_NUMBER}" in note
    assert f"(DIA CLR {least:.3f}-{greatest:.3f} mm)" in note
    assert f"\N{DIAMETER SIGN}{sleeve.SPIGOT_DIA:.3f} +{spigot_upper:.3f}/" in note
    assert all(len(line) <= 70 for line in note.splitlines())
    for banned in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert banned not in note.upper()


def test_thickness_band_is_the_printed_xxx_band() -> None:
    band = printed_band_mm(3)
    assert (spec.FACE_WIDTH_MIN, spec.FACE_WIDTH_MAX) == pytest.approx(
        (spec.FACE_WIDTH - band, spec.FACE_WIDTH + band)
    )


def test_tap_callout_carries_countersink_break_and_transfer() -> None:
    definitions = {5: "", 6: "<hw-threadclass> THRU", 7: "", 8: ""}
    updated = drawing.tap_callout_definitions(definitions)
    assert updated[6].endswith(spec.TAP_CALLOUT_QUALIFIER)
    assert {k: v for k, v in updated.items() if k != 6} == {5: "", 7: "", 8: ""}
    text = spec.TAP_CALLOUT_QUALIFIER
    assert "CSK" in text and "1.7 +0.10/0" in text
    assert "BREAK EDGE 0.05" in text
    assert "MHA-159" in text and "MATCH-MARK" in text
    for banned in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "BOOK FIDELITY"):
        assert banned not in text.upper()
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""})


def test_gear_data_block_specifies_the_tooth_system() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm",
        "OUTSIDE DIAMETER (mm)",
        "WHOLE DEPTH (mm)",
        "TOOTH FORM",
    ):
        assert field in data, field
    assert "120" in data
    assert "X.XX" not in data


def test_manufacturing_notes_fit_the_limits_and_state_the_screw_engagement() -> None:
    notes = part.MANUFACTURING_NOTES.splitlines()
    assert len(notes) <= 4
    assert all(len(line) <= 70 for line in notes)
    # 19e33c6c2's blind review subtracted a blind tap's incomplete lead from
    # the through tap; the sheet states the worst engagement, which the
    # printed MIN never rounds up past and which meets the 1.5D floor.
    printed = part.ENGAGEMENT_WORST_D_PRINTED
    assert f"ENGAGEMENT {printed:.2f}D MIN" in part.MANUFACTURING_NOTES
    assert spec.ENGAGEMENT_FLOOR_D <= printed <= disc_screw.ENGAGEMENT_WORST_D


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


def test_tap_leader_lands_on_the_lower_left_tap_and_crosses_no_bore_leader() -> None:
    """19e33c6c2: the tap leader rose across the bore to the upper tap."""
    centre = drawing.FRONT_CENTER
    bolt_r = hub_geometry.BOLT_CIRCLE_DIA / 2000.0
    tap = drawing.TAP_SHEET_CENTER
    assert math.dist(tap, centre) == pytest.approx(bolt_r)
    assert tap[0] < centre[0] and tap[1] < centre[1]
    # The pick lies on the drill circle, off both centre-mark lines.
    pick = drawing.TAP_PICK
    assert math.dist(pick, tap) == pytest.approx(spec.TAP_DRILL_DIA / 2000.0)
    assert min(abs(pick[0] - tap[0]), abs(pick[1] - tap[1])) > 0.0003
    leader = (drawing.TAP_CALLOUT_XY, pick)
    bore_r = spec.BORE_DIA / 2000.0
    assert _distance_to_segment(centre, *leader) > bore_r + 0.002
    # The bore's diameter line runs through the centre to the far rim.
    dim_xy = drawing.FRONT_KEEP["BoreDia"]
    far = (
        centre[0] + (centre[0] - dim_xy[0]) * bore_r / math.dist(dim_xy, centre),
        centre[1] + (centre[1] - dim_xy[1]) * bore_r / math.dist(dim_xy, centre),
    )
    finish_attach = (centre[0] + bore_r, centre[1])
    for other in (
        (dim_xy, far),
        (drawing.BORE_FIT_NOTE, drawing.BORE_FIT_ATTACH),
        (drawing.BORE_FINISH_POSITION, finish_attach),
    ):
        assert not _segments_cross(*leader, *other)
    # The finish leader passes under the 0° tap, not through it.
    right_tap = (centre[0] + bolt_r, centre[1])
    finish_leader = (drawing.BORE_FINISH_POSITION, finish_attach)
    clearance = _distance_to_segment(right_tap, *finish_leader)
    assert clearance > spec.TAP_DRILL_DIA / 2000.0 + 0.001


def test_bore_finish_symbol_stands_clear_of_the_edge_view_thickness() -> None:
    """19e33c6c2 printed Ra 1.6 into the 3.000."""
    x, y = drawing.BORE_FINISH_POSITION
    # The symbol and its "Ra 1.6" run about 45 mm right of and 16 mm above
    # the insertion point (the farm run's print).
    symbol_right, symbol_top = x + 0.045, y + 0.016
    thickness_x, thickness_y = drawing.RIGHT_KEEP["FaceWidth"]
    # The 3.000 text and its extension lines start at the disc's front face.
    assert symbol_right < min(drawing.FRONT_FACE_X, thickness_x - 0.006) - 0.010
    assert symbol_top < drawing.FRONT_CENTER[1] - drawing.HALF_OD


def test_mesh_geometry_is_unchanged() -> None:
    assert (part.TEETH, part.DP, part.FACE_WIDTH) == (120, 38.0, 3.0)
    assert spec.CENTRE_DISTANCE == 44.766
    assert part.BORE_DIAMETER == spec.BORE_DIA == 10.0
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "THRU - REAM"}


def test_part_config_properties() -> None:
    import _config

    config = _config.parts("rack-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert int(config["quantity"]) == 1


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == spec.BORE_DIA
    assert drawing.add_rack_bore_finish is finish_helper.add_rack_bore_finish
    assert finish_helper.SURFACE_FINISHES is spec.SURFACE_FINISHES
    assert finish_helper.BORE_DIA == spec.BORE_DIA
    assert finish_helper.FACE_WIDTH == spec.FACE_WIDTH


@pytest.fixture
def finish_insertion(monkeypatch):
    """No fake exposes position, endpoint, or reattachment setters."""
    state = SimpleNamespace(
        calls=[],
        data=SimpleNamespace(),
        select_result=True,
        selected_count=1,
        rebuild_result=True,
        inventory_mode="insert",
        inventory=[],
        dangling=False,
        equality_mode="identity",
        after_rebuild=None,
        text_result=True,
        text_mode="write",
        texts={},
        style_result=0,
        symbol=1,
        leader_count=1,
        points=(
            0.278,
            0.113,
            0.0015,
            0.23,
            0.15,
            0.0015,
            0.222499999953,
            0.175,
            0.0015,
        ),
        face_result="valid",
        fail_rebuild_at=None,
        mutate_rebuild_at=2,
        activate_result=True,
    )
    front = SimpleNamespace(
        GetAnnotations=lambda: state.inventory, GetName2=lambda: "Front test view"
    )

    def select(append, data):
        state.calls.append("select")
        assert append is False and data is state.data and data.View is front
        assert (data.X, data.Y, data.Z) == (0.2225, 0.175, spec.FACE_WIDTH / 2000.0)
        return state.select_result

    edge = SimpleNamespace(Select4=select)
    state.selected, state.entities, state.types = edge, (edge,), (1,)

    def selected_count(mark):
        state.calls.append("selection-count")
        assert mark == -1
        return state.selected_count

    def selected_object(index, mark):
        state.calls.append("selected-object")
        assert (index, mark) == (1, -1)
        return state.selected

    manager = SimpleNamespace(
        CreateSelectData=lambda: state.data,
        GetSelectedObjectCount2=selected_count,
        GetSelectedObject6=selected_object,
    )

    def style(*arguments):
        state.calls.append("style")
        assert arguments == (2, 0, True, False, False, False)
        return state.style_result

    annotation = SimpleNamespace(
        GetType=lambda: 7,
        SetLeader3=style,
        GetAttachedEntities3=lambda: state.entities,
        GetAttachedEntityTypes=lambda: state.types,
        IsDangling=lambda: state.dangling,
        GetLeaderCount=lambda: state.leader_count,
        GetLeaderPointsAtIndex=lambda _index: state.points,
    )
    state.annotation = annotation

    def set_text(slot, value):
        state.calls.append(f"text-{slot}")
        assert slot == 8 and value == f"Ra {spec.SURFACE_FINISHES[0].roughness_ra}"
        if state.text_mode == "write":
            state.texts[slot] = value
        return state.text_result

    finish = SimpleNamespace(
        GetAnnotation=lambda: state.annotation,
        SetText=set_text,
        GetText=lambda slot: state.texts.get(slot, ""),
        GetSymbol=lambda: state.symbol,
    )
    state.finish = finish

    def insert(*arguments):
        state.calls.append("insert")
        assert arguments == (
            1,
            2,
            *drawing.BORE_FINISH_POSITION,
            0.0,
            0,
            10,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        if state.inventory_mode == "insert":
            state.inventory = [annotation]
        return state.finish

    def rebuild():
        state.calls.append("rebuild")
        if (
            state.after_rebuild is not None
            and state.calls.count("rebuild") == state.mutate_rebuild_at
        ):
            state.after_rebuild()
        if state.calls.count("rebuild") == state.fail_rebuild_at:
            return False
        return state.rebuild_result

    def clear(all_selections):
        assert all_selections is True
        state.calls.append("clear")

    def activate(name):
        state.calls.append("activate")
        assert name == front.GetName2()
        return state.activate_result

    def same(left, right):
        phase = (
            "inventory"
            if right is annotation
            else "attachment"
            if "rebuild" in state.calls
            else "selection"
        )
        state.calls.append(f"{phase}-identity")
        assert right is edge or right is annotation
        if state.equality_mode == f"unknown-{phase}":
            return -1
        return int(left is right)

    model = SimpleNamespace(
        SelectionManager=manager,
        ClearSelection2=clear,
        EditRebuild3=rebuild,
        Extension=SimpleNamespace(InsertSurfaceFinishSymbol3=insert),
        ActivateView=activate,
    )
    adapter = SimpleNamespace(currentModel=model, swApp=SimpleNamespace(IsSame=same))

    def project(actual_adapter, view, xyz, *, label):
        state.calls.append("project")
        assert actual_adapter is adapter and view is front
        assert xyz == (spec.BORE_DIA / 2000.0, 0.0, spec.FACE_WIDTH / 1000.0)
        assert label == "rack bore finish semantic rim point"
        return (0.2225, 0.175)

    def validate(entity, *, entity_type, control, label):
        state.calls.append("validate-face")
        assert entity is edge and entity_type == "EDGE"
        assert control is spec.SURFACE_FINISHES[0]
        assert label == "rack pinion bore finish"
        if state.face_result == "reject":
            raise RuntimeError("test face control mismatch")

    monkeypatch.setattr(finish_helper, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        finish_helper, "_validate_surface_finish_control_face", validate
    )
    monkeypatch.setattr(finish_helper, "model_point_in_view", project)
    state.run = lambda: finish_helper.add_rack_bore_finish(
        adapter, front, edge, symbol_xy=drawing.BORE_FINISH_POSITION
    )
    state.edge = edge
    return state


def test_finish_insertion_validates_face_then_selects_and_inserts_once(
    finish_insertion,
):
    state = finish_insertion
    assert state.run() is state.finish
    assert state.calls == [
        "validate-face",
        "activate",
        "clear",
        "project",
        "select",
        "selection-count",
        "selected-object",
        "selection-identity",
        "insert",
        "rebuild",
        "text-8",
        "style",
        "clear",
        "rebuild",
        "inventory-identity",
        "attachment-identity",
    ]
    assert state.entities == (state.edge,) and state.types == (1,)
    for forbidden in (
        "SetPosition2",
        "SetPosition",
        "SetLeaderAttachmentPointAtIndex",
        "SetAttachedEntities",
    ):
        assert not hasattr(state.annotation, forbidden)


def test_finish_face_mismatch_rejected_before_any_selection_or_insertion(
    finish_insertion,
):
    state = finish_insertion
    state.face_result = "reject"
    with pytest.raises(RuntimeError, match="face control mismatch"):
        state.run()
    assert state.calls == ["validate-face"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("activate_result", False, "view activation failed"),
        ("data", None, "no selection data"),
        ("select_result", False, "semantic edge selection failed"),
        ("selected_count", 0, "exactly one selected edge"),
        ("selected_count", 2, "exactly one selected edge"),
        ("selected", None, "wrong semantic edge"),
        ("selected", object(), "wrong semantic edge"),
        ("equality_mode", "unknown-selection", "wrong semantic edge"),
    ],
)
def test_finish_insertion_rejects_bad_selection_before_insertion(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert "insert" not in state.calls and "rebuild" not in state.calls


@pytest.mark.parametrize(
    ("field", "value", "message", "rebuilds"),
    [
        ("finish", None, "insertion returned null", 0),
        ("annotation", None, "no annotation", 1),
        ("text_result", False, "roughness assignment failed", 1),
        ("style_result", 1, "leader style failed", 1),
    ],
)
def test_finish_insertion_checks_each_mutation_result(
    finish_insertion, field, value, message, rebuilds
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == rebuilds


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("inventory_mode", "noop", "insertion inventory mismatch"),
        ("equality_mode", "unknown-inventory", "insertion inventory mismatch"),
        ("text_mode", "noop", "manufacturing content changed"),
        ("symbol", 0, "manufacturing content changed"),
    ],
)
def test_finish_insertion_rejects_noops_and_readback_failure(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize("phase", [1, 2])
def test_finish_each_rebuild_result_is_required(finish_insertion, phase):
    state = finish_insertion
    state.fail_rebuild_at = phase
    with pytest.raises(RuntimeError, match="rebuild failed"):
        state.run()
    assert state.calls.count("rebuild") == phase
    if phase == 1:
        assert "text-8" not in state.calls and "style" not in state.calls


@pytest.mark.parametrize("phase", [1, 2])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("entities", ()),
        ("entities", None),
        ("entities", (None,)),
        ("entities", (object(),)),
        ("entities", (object(), object())),
        ("types", ()),
        ("types", None),
        ("types", (2,)),
        ("types", (1, 1)),
        ("equality_mode", "unknown-attachment"),
        ("dangling", True),
    ],
)
def test_finish_insertion_rechecks_semantic_attachment_after_rebuild(
    finish_insertion, field, value, phase
):
    state = finish_insertion
    state.mutate_rebuild_at = phase
    state.after_rebuild = lambda: setattr(state, field, value)
    with pytest.raises(RuntimeError, match="lost its semantic edge attachment"):
        state.run()
    assert state.calls.count("insert") == 1 and state.calls.count("rebuild") == 2


@pytest.mark.parametrize(
    "inventory",
    [
        [],
        [SimpleNamespace(GetType=lambda: 7)],
        [SimpleNamespace(GetType=lambda: 7), SimpleNamespace(GetType=lambda: 7)],
    ],
)
def test_finish_inventory_after_rebuild_must_be_exact_returned_annotation(
    finish_insertion, inventory
):
    state = finish_insertion
    state.after_rebuild = lambda: setattr(state, "inventory", inventory)
    with pytest.raises(RuntimeError, match="insertion inventory mismatch"):
        state.run()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("leader_count", 0, "exactly one leader"),
        ("leader_count", 2, "exactly one leader"),
        ("points", (), "points are invalid"),
        ("points", None, "points are invalid"),
        ("points", (0, 0, 0), "points are invalid"),
        ("points", (float("nan"), 0, 0, 0.2225, 0.175, 0.0015), "points are invalid"),
        (
            "points",
            (0.278, 0.113, 0, 0.2225, 0.175, float("inf")),
            "points are invalid",
        ),
        ("points", (0.278, 0.113, 0, 0, 0, 0), "off the intended right rim"),
        (
            "points",
            (0.278, 0.113, 0, 0.22250002, 0.175, 0.0015),
            "off the intended right rim",
        ),
        (
            "points",
            (0.278, 0.113, 0, 0.2225, 0.17500002, 0.0015),
            "off the intended right rim",
        ),
    ],
)
def test_finish_leader_requires_finite_shape_and_exact_right_rim(
    finish_insertion, field, value, message
):
    state = finish_insertion
    setattr(state, field, value)
    with pytest.raises(RuntimeError, match=message):
        state.run()


def test_finish_straight_leader_with_native_readback_point_is_valid(finish_insertion):
    state = finish_insertion
    state.points = (0.278, 0.113, 0.0015, 0.222499999953, 0.175, 0.0015)
    assert state.run() is state.finish
