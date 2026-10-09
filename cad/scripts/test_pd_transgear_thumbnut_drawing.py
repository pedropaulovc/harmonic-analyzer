"""Offline contracts for the transgear thumbnut (MHA-PD-013) part and drawing."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _hole_spec
import build_pd_transgear_thumbnut as part
import draw_pd_transgear_thumbnut as drawing
import pd_transgear_thumbnut_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm

# The B landscape template's inner border, left edge (sheet metres).
SHEET_INNER_LEFT = 0.0127


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-thumbnut.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-thumbnut.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_transgear_thumbnut"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FACE_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FACE_KEEP) & set(drawing.SECTION_KEEP)
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # The knurl callout rides on a dimension the section prints.
    assert set(drawing.DIMENSION_CALLOUTS_ABOVE) <= set(drawing.SECTION_KEEP)


def test_actual_entry_cones_carry_model_owned_controls() -> None:
    assert model_toleranced_dimensions(part) == {
        ("CountersinkProfile", "CountersinkHalfAngle"): "max(CSK_HALF_ANGLE_BAND)",
        ("CountersinkProfile", "FrontCountersinkHalfAngle"): "max(CSK_HALF_ANGLE_BAND)",
    }
    assert spec.CSK_DIA_TOL_TYPE == 6
    assert spec.CSK_DIA_PLACES == 3
    assert spec.DRAWING_DIMENSIONS["CountersinkProfile"] == {
        "CountersinkDia", "CountersinkHalfAngle",
    }
    assert not any(character.isdigit() for character in spec.CSK_QUALIFIER[3:])


def _thumbnut_spec_with(monkeypatch, module, name: str, value):
    """A fresh execution of the thumbnut spec with one upstream value patched:
    the spec's own gate is observed, not re-derived here."""
    monkeypatch.setattr(module, name, value)
    fresh_spec = importlib.util.spec_from_file_location(
        "_thumbnut_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_walls_over_the_thread_refuse_a_larger_thread(monkeypatch) -> None:
    # Positive control: the actual #8-32 major re-executes clean.
    clean = _thumbnut_spec_with(
        monkeypatch, _hole_spec, "THREAD_MAJOR_MM", dict(_hole_spec.THREAD_MAJOR_MM)
    )
    assert min(worst for _nominal, worst in clean.WALLS.values()) >= clean.WALL_FLOOR
    # A deliberately oversized thread crosses the waist's legal wall floor.
    majors = dict(_hole_spec.THREAD_MAJOR_MM)
    majors[spec.THREAD] = 7.0
    with pytest.raises(AssertionError, match="waist"):
        _thumbnut_spec_with(monkeypatch, _hole_spec, "THREAD_MAJOR_MM", majors)


def test_the_seat_face_bears_on_the_collar_pilot(monkeypatch) -> None:
    """R9-70: the nut seats on MHA-PD-022's faced pilot, not on the T24: its seat
    bears on the pilot's annulus outside the rear countersink and its flange
    covers the pilot all round, at the printed worst case."""
    import pd_transgear_drive_collar_spec as collar

    pilot_min = collar.PILOT_DIA + min(collar.PILOT_DIA_BAND)
    assert collar.NUT_PILOT_BEARING_WORST == pytest.approx(
        (pilot_min - spec.CSK_DIA) / 2.0
    )
    assert collar.NUT_PILOT_BEARING_WORST > 1.5
    assert collar.NUT_FLANGE_OVER_PILOT_WORST > 0.0
    # A rear countersink as wide as the pilot leaves the nut nothing to bear on.
    monkeypatch.setattr(spec, "CSK_DIA", collar.PILOT_DIA)
    fresh_spec = importlib.util.spec_from_file_location(
        "_collar_perturbed", collar.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    with pytest.raises(AssertionError, match="countersink swallows the pilot"):
        fresh_spec.loader.exec_module(fresh)


def test_countersinks_take_no_more_thread_than_the_engagement_deducts() -> None:
    """Actual MAX cone and the smallest printed half-angle charge both ends."""
    assert spec.CSK_DIA == pytest.approx(4.566)
    rear = (spec.CSK_DIA - spec.TAP_DRILL_DIA) / (
        2.0 * math.tan(math.radians(spec.CSK_HALF_ANGLE_MIN))
    )
    assert rear == pytest.approx(spec.REAR_THREAD_LOSS)
    deepest_floor = spec.DISH_DEPTH + printed_band_mm(spec.DISH_DEPTH_PLACES)
    front = deepest_floor + rear
    assert front > rear
    assert front <= spec.FRONT_THREAD_LOSS + 1e-9


def _outside_every_countersink(point: tuple[float, float]) -> bool:
    """Whether a profile point (radius, y) survives the drill and both
    countersinks: on neither cone's side of the printed MAX Ø."""
    radius, _y = point
    return radius > spec.CSK_DIA / 2.0 > spec.TAP_DRILL_DIA / 2.0


def test_the_dish_ends_on_its_floor_at_every_printed_size() -> None:
    """Machinist review of 6de7230aa (blocker): Ø15.0 and a 1.2 depth to a
    point on the axis inside the tap drill left the sloping recess ending
    wherever the Ø6.75 MAX countersink met it.  The recess now ends on a flat
    floor whose edge Ø the model carries and the section prints; the
    countersink is cut inside that floor at every printed size; and the
    depth runs from the rim's edge to the floor's, both edges the finished
    nut keeps."""
    assert {"DishDia", "DishFloorDia", "DishDepth"} == spec.DRAWING_DIMENSIONS[
        "DishProfile"
    ]
    assert {"DishDia", "DishFloorDia", "DishDepth"} <= set(drawing.SECTION_KEEP)
    # Title-block .X: the band the margins below are judged at.
    assert drawing.DRAWING_PRECISION_BY_NAME["DishFloorDia"] == 1
    assert spec.dish_floor_margins(
        spec.DISH_DIA, spec.DISH_FLOOR_DIA, spec.DISH_DEPTH, spec.CSK_DIA
    ) == pytest.approx(
        {
            "floor land outside the countersink": (9.0 - 0.8 - 4.566) / 2.0,
            "cone from the rim to the floor": 2.2,
            "floor below the rim": 0.2,
        }
    )
    rim, floor = spec.DISH_RIM_CORNER, spec.DISH_FLOOR_CORNER
    assert rim == pytest.approx((spec.DISH_DIA / 2.0, spec.RIM_Y))
    assert floor == pytest.approx((spec.DISH_FLOOR_DIA / 2.0, spec.DISH_FLOOR_Y))
    assert rim[1] - floor[1] == pytest.approx(spec.DISH_DEPTH)
    band = printed_band_mm(spec.DISH_FLOOR_DIA_PLACES)
    assert _outside_every_countersink((floor[0] - band / 2.0, floor[1]))
    assert _outside_every_countersink(rim)
    # Negative controls: the 6de7230aa depth ran to the axis, inside the
    # drill; a floor no wider than the countersink lets it cut the cone.
    assert not _outside_every_countersink((0.0, spec.RIM_Y - 1.2))
    narrow = spec.dish_floor_margins(
        spec.DISH_DIA, spec.CSK_DIA, spec.DISH_DEPTH, spec.CSK_DIA
    )
    assert narrow["floor land outside the countersink"] < 0.0


def test_the_dish_dimensions_stack_clear_of_each_other_and_the_rim() -> None:
    """The rim's diameters nest (each one's extension lines inside the next
    one's dimension line), and the dish depth's text stands above its rim
    extension line rather than on it, as the 6de7230aa 1.2 did."""
    from _layout_geometry import estimate_text_box

    keep = drawing.SECTION_KEEP
    rim_y = drawing._section_y(spec.OVERALL_LENGTH)
    assert keep["HeadDia"][1] > keep["DishDia"][1] > keep["DishFloorDia"][1] > rim_y

    def bottom(anchor: tuple[float, float]) -> float:
        box = estimate_text_box("1.0", anchor=anchor, height=0.0035, reference=2)
        assert box is not None
        return box.ymin

    assert bottom(keep["DishDepth"]) > rim_y
    # Negative control: the 6de7230aa anchor at the rim's height.
    assert bottom((keep["DishDepth"][0], rim_y)) < rim_y


def test_thread_callout_is_native_and_is_not_rewritten_for_countersinks(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)

    class Callout:
        def __init__(self, text):
            self.text = text

        def GetText(self, part):
            assert part in (1, 2, 3, 4)
            return self.text if part == 3 else ""

    drawing._assert_native_thread(Callout(f"{spec.THREAD} UNC - 2B THRU ALL"))
    for wrong in ("1/4-20 UNC - 2B THRU ALL", "#8-32 UNC - 2A", "#8-32 THRU"):
        with pytest.raises(RuntimeError, match="source thread"):
            drawing._assert_native_thread(Callout(wrong))
    with pytest.raises(RuntimeError, match="invalid readback"):
        drawing._assert_native_thread(Callout(None))


def test_the_knurl_puts_crests_on_the_section_plane() -> None:
    """Section A-A is the Front plane: both of its sides must cut a crest, or
    the knurl diameter has no edge to print on."""
    root, flank_a, flank_b = part.knurl_seed_points()
    root_angle = math.atan2(root[1], root[0])
    pitch = 2.0 * math.pi / spec.KNURL_TEETH
    crests = {
        round(math.degrees(root_angle + k * pitch + side * pitch / 2.0), 6) % 360.0
        for k in range(spec.KNURL_TEETH)
        for side in (-1, 1)
    }
    assert {0.0, 180.0} <= crests
    assert math.hypot(*root) == pytest.approx(spec.KNURL_ROOT_DIA / 2.0)
    # Each flank passes through its crest on the knurl diameter.
    for flank, crest_angle in (
        (flank_a, root_angle - pitch / 2.0),
        (flank_b, root_angle + pitch / 2.0),
    ):
        crest = (
            spec.HEAD_DIA / 2.0 * math.cos(crest_angle),
            spec.HEAD_DIA / 2.0 * math.sin(crest_angle),
        )
        cross = (flank[0] - root[0]) * (crest[1] - root[1]) - (flank[1] - root[1]) * (
            crest[0] - root[0]
        )
        assert cross == pytest.approx(0.0, abs=1e-9)


def test_registry_row_is_the_turned_brass_mha_126() -> None:
    row = _config.parts("pd-transgear-thumbnut")
    assert row["number"] == "MHA-PD-013"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["tolerance_class"] == "machined_block"
    assert "fit_class" not in row


def _nut_fits_stud(nut, stud) -> bool:
    """The nut's tapped thread is the stud's: same size, same major, and the
    stud's thread blank is turned under that major."""
    return (
        nut.THREAD == stud.THREAD
        and nut.TAP_SPEC.size == stud.THREAD
        and nut.THREAD_MAJOR == pytest.approx(stud.THREAD_MAJOR)
        and stud.THREAD_BLANK_DIA <= nut.THREAD_MAJOR
    )


def test_the_nut_thread_is_the_knob_shaft_stud_thread() -> None:
    """R9-11: the nut runs on the MHA-PD-008 stud."""
    import pd_transgear_knob_shaft_spec as stud

    assert _nut_fits_stud(spec, stud)
    # Negative control: a #10-32 stud is refused.
    other = SimpleNamespace(
        THREAD="#10-32",
        THREAD_MAJOR=_hole_spec.THREAD_MAJOR_MM["#10-32"],
        THREAD_BLANK_DIA=_hole_spec.THREAD_MAJOR_MM["#10-32"],
    )
    assert not _nut_fits_stud(spec, other)


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank."""
    import _common
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_common.part_properties(part.PART_NAME))
    stamp = _calls(part.__file__)["apply_drawing_properties"]
    assert [ast.unparse(a) for a in stamp.args] == ["adapter", "PART_NAME"]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []


# Face view, run 20261001T151531763Z, as its layout audit measured them: the
# thread callout's leader, from its arrow on the tap drill to its knee, and
# the shoulder of SolidWorks' own tapped-hole note.  The note's drop
# to its arrow on the countersink is the 19e33c6c2 audit's (the same note,
# DetailItem348; the run's audit reported only the shoulder it crossed).
_THREAD_CALLOUT_LEADER = LeaderSegment(
    "hole-callout RD1", "note", 0.0873, 0.1723, 0.1014, 0.2166
)
_TAPPED_HOLE_NOTE_LEADER = (
    LeaderSegment("note DetailItem348", "note", 0.0977, 0.1866, 0.0913, 0.1866),
    LeaderSegment("note DetailItem348", "note", 0.0908, 0.1863, 0.0850, 0.1745),
)


def test_the_tapped_hole_note_whose_leader_the_callout_crossed_is_removed() -> None:
    """Run 20261001T151531763Z failed its layout audit on leader-crosses-leader
    at (91.9, 186.6) mm: the callout's leader through the auto-inserted note's
    shoulder.  The note restates the callout's thread, so finalize deletes it
    before the audit, as every sibling tapped-hole sheet does."""
    [crossing] = find_leader_leader_crossings(
        [_THREAD_CALLOUT_LEADER, *_TAPPED_HOLE_NOTE_LEADER]
    )
    assert {crossing.a.label, crossing.b.label} == {
        "hole-callout RD1",
        "note DetailItem348",
    }
    assert (crossing.x, crossing.y) == pytest.approx((0.0919, 0.1866), abs=1e-4)
    finalize = _calls(drawing.__file__)["finalize_drawing"]
    removal = {
        k.arg: ast.literal_eval(k.value)
        for k in finalize.keywords
        if k.arg in ("redundant_note_substrings", "expected_redundant_notes")
    }
    assert removal == {
        "redundant_note_substrings": ("Tapped Hole",),
        "expected_redundant_notes": 1,
    }
    # The removal reaches the note, and the callout itself is no note to lose.
    note_text = f"{spec.THREAD} Tapped Hole".lower()
    assert all(s.lower() in note_text for s in removal["redundant_note_substrings"])
    callout_text = f"{spec.THREAD} UNC - 2B THRU ALL".lower()
    assert not any(
        s.lower() in callout_text for s in removal["redundant_note_substrings"]
    )


def test_the_knurl_is_the_designated_din_82_raa_1_0() -> None:
    """R9-57: the modelled teeth are the 1.0-pitch 90° straight knurl the
    callout names, so the shop's wheel forms what the model shows."""
    assert spec.KNURL_CREST_PITCH == pytest.approx(1.0, abs=0.01)
    assert spec.KNURL_TOOTH_ANGLE_DEG == pytest.approx(90.0, abs=2.0)
    assert spec.KNURL_DESIGNATION in spec.KNURL_CALLOUT
    # Negative control: the 19e33c6c2 model (60 teeth over a Ø19.7 root)
    # was a 1.07-pitch, 108.5° V no standard wheel forms.
    old_angle = spec.knurl_tooth_angle_deg(spec.HEAD_DIA, 19.7, 60)
    assert old_angle == pytest.approx(108.5, abs=0.1)
    assert math.pi * spec.HEAD_DIA / 60 - spec.KNURL_PITCH > 0.01


def test_the_knurl_designation_is_authored_where_it_prints() -> None:
    """Run 20261001T154021634Z's machinist review: the sheet showed Ø20.5 and
    no knurl.  The designation rode a two-line above-callout, which SolidWorks
    stored but did not print; one line in that compartment prints."""
    above = drawing.DIMENSION_CALLOUTS_ABOVE
    assert spec.KNURL_DESIGNATION in above["HeadDia"]
    assert "DIA OVER KNURL" in above["HeadDia"]
    assert drawing._printable_above_callouts(above) == above
    with pytest.raises(RuntimeError, match="HeadDia"):
        drawing._printable_above_callouts(
            {"HeadDia": f"STRAIGHT KNURL {spec.KNURL_DESIGNATION}\nDIA OVER KNURL"}
        )


def test_the_shortest_nut_keeps_full_thread_for_the_stud() -> None:
    """The overall length prints at .X; the shortest nut it admits still
    gives the stud 1.5D of the nut's full thread."""
    import pd_transgear_drive_collar_spec as collar
    import pd_transgear_knob_shaft_spec as stud

    assert spec.OVERALL_LENGTH_LO == pytest.approx(-0.8)
    assert collar.NUT_LENGTH_MIN == pytest.approx(15.3)
    assert collar.THUMBNUT_ENGAGEMENT_WORST >= 1.5 * stud.THREAD_MAJOR
    # The nut's own full thread over its shortest length, the front
    # countersink on the deepest printed floor.
    shortest_rim = spec.RIM_Y + spec.OVERALL_LENGTH_LO
    full = shortest_rim - spec.FRONT_THREAD_LOSS - spec.REAR_FULL_THREAD_Y
    assert full >= 1.5 * spec.THREAD_MAJOR


def _section_station(y: float) -> float:
    """Model station (from the seat face) of sheet height ``y`` on A-A."""
    return (y - drawing.SECTION_CENTER[1]) * 1000.0 / drawing._S + (
        spec.OVERALL_LENGTH / 2.0
    )


def test_the_stem_diameters_print_across_their_own_cut() -> None:
    """Codex on 19e33c6c2: the Ø12.40 and Ø11.00 extension lines ran through
    the head's hatching to a stack below the seat face, on the SECTION A-A
    caption.  Each now prints at its own feature's height, text right of
    the knurl, so no extension line crosses another feature's cut."""
    head_right = drawing._section_x(spec.HEAD_DIA / 2.0)
    for name, (lo, hi) in {
        "FlangeDia": (0.0, spec.FLANGE_LENGTH),
        "WaistDia": (spec.FLANGE_LENGTH, spec.FLANGE_LENGTH + spec.WAIST_LENGTH),
    }.items():
        x, y = drawing.SECTION_KEEP[name]
        assert lo < _section_station(y) < hi, name
        assert x > head_right, name
    # The text clears the overall length's dimension line beyond it.
    assert drawing.SECTION_KEEP["OverallLength"][0] - drawing._STEM_TEXT_X > 0.004
    # All nine turned/dished sizes remain above the seat. The cone diameter
    # has a left caption lane; the native angle's arc stays at its real cone.
    seat_y = drawing._section_y(0.0)
    turned = set().union(
        *(spec.DRAWING_DIMENSIONS[feature] for feature in ("HeadProfile", "StemProfile", "DishProfile"))
    )
    assert len(turned) == 9
    assert all(drawing.SECTION_KEEP[name][1] >= seat_y for name in turned)
    dia = drawing.SECTION_KEEP["CountersinkDia"]
    angle_arc = drawing.SECTION_KEEP["CountersinkHalfAngle"]
    angle_text = drawing.COUNTERSINK_ANGLE_TEXT_XY
    assert dia[0] < drawing.SECTION_CENTER[0] - drawing.HALF_HEAD - 0.020
    assert angle_text[0] > head_right + 0.010
    assert dia[1] == angle_text[1] < seat_y
    assert dia[1] > SHEET_INNER_LEFT + 0.020
    # Compact arc anchor just outside the rear cone, not outside the head.
    cone_right = drawing._section_x(spec.CSK_DIA / 2.0)
    assert 0.0 < angle_arc[0] - cone_right < 0.003
    assert 0.0 < seat_y - angle_arc[1] < 0.003
    apex = (drawing.SECTION_CENTER[0], drawing._section_y(spec.REAR_CSK_APEX_Y))
    assert math.dist(angle_arc, apex) < 0.015
    # Negative control: 4e9a4df's sheet-outboard anchor grew a >50 mm arc.
    old_arc = (head_right + 0.025, seat_y - 0.008)
    assert math.dist(old_arc, apex) > 0.050
    # The rim's diameters print above the rim, the knurl outermost.
    rim_y = drawing._section_y(spec.OVERALL_LENGTH)
    assert drawing.SECTION_KEEP["HeadDia"][1] > drawing.SECTION_KEEP["DishDia"][1]
    assert drawing.SECTION_KEEP["DishDia"][1] > rim_y
    # Negative control: the 19e33c6c2 stack sat under the seat face.
    assert _section_station(seat_y - 0.014) < 0.0


@pytest.mark.parametrize(
    "offset_persists,arc_moves,text_moves",
    ((True, True, True), (False, True, True), (True, False, True), (True, True, False)),
)
def test_native_cone_angle_offsets_only_text_and_refuses_noops(
    monkeypatch, offset_persists, arc_moves, text_moves,
) -> None:
    """Bounded annotation fake follows the SDK OffsetText movement semantics."""
    model_dimension = object()

    class Display:
        def __init__(self):
            self.offset = True  # A previous offset must not preserve a long arc.

        @property
        def OffsetText(self):
            return self.offset

        @OffsetText.setter
        def OffsetText(self, value):
            self.offset = bool(value) and offset_persists

    class Annotation:
        def __init__(self):
            self.name = "CountersinkHalfAngle"
            self.dimension = model_dimension
            self.display = Display()
            self.arc = (0.271, 0.133)
            self.text = self.arc

        def GetSpecificAnnotation(self):
            return self.display

        def SetPosition2(self, x, y, z):
            assert z == 0.0
            can_move = text_moves if self.display.OffsetText else arc_moves
            if can_move:
                self.text = (x, y)
                if not self.display.OffsetText:
                    self.arc = self.text
            return True  # A successful status alone does not prove a move.

        def GetPosition(self):
            return (*self.text, 0.0)

    annotation = Annotation()
    adapter = object()
    calls = []

    def offset(actual_adapter, annotations, positions):
        assert actual_adapter is adapter and annotations == [annotation]
        calls.append(positions)
        annotation.display.OffsetText = True
        assert annotation.SetPosition2(*positions[annotation.name], 0.0)

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    if not offset_persists:
        with pytest.raises(RuntimeError, match="did not stay offset"):
            drawing._place_countersink_angle(adapter, [annotation])
    elif not arc_moves:
        with pytest.raises(RuntimeError, match="angle arc did not persist"):
            drawing._place_countersink_angle(adapter, [annotation])
    elif not text_moves:
        with pytest.raises(RuntimeError, match="angle text did not persist"):
            drawing._place_countersink_angle(adapter, [annotation])
    else:
        drawing._place_countersink_angle(adapter, [annotation])
        assert annotation.arc == drawing.SECTION_KEEP[annotation.name]
        assert annotation.text == drawing.COUNTERSINK_ANGLE_TEXT_XY
        assert annotation.display.OffsetText
    assert annotation.dimension is model_dimension
    assert calls == (
        [{annotation.name: drawing.COUNTERSINK_ANGLE_TEXT_XY}] if arc_moves else []
    )
    call = _calls(drawing.__file__)["_place_countersink_angle"]
    assert [ast.unparse(arg) for arg in call.args] == ["adapter", "section_annotations"]


def test_native_cone_angle_requires_exactly_one_model_annotation(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    angle = SimpleNamespace(name="CountersinkHalfAngle")
    for annotations in ([], [angle, angle]):
        with pytest.raises(RuntimeError, match="needs one native"):
            drawing._place_countersink_angle(object(), annotations)


def test_the_section_stands_rim_up_or_is_refused() -> None:
    assert drawing._rim_is_up((0.2, 0.15), (0.2, 0.198))
    assert not drawing._rim_is_up((0.2, 0.198), (0.2, 0.15))
    with pytest.raises(RuntimeError, match="not vertical"):
        drawing._rim_is_up((0.2, 0.15), (0.248, 0.15))


class _SectionView:
    """Section A-A as run 20261001T142942518Z saw it: Position reads where the
    view was put, ``SetViewPosition`` moves the ink by the difference from it,
    and reversing the cut swings the ink about the seat face while Position
    stays put.  It starts as created: rim down, outline on SECTION_CENTER."""

    MARGIN = 0.005588  # the 19e33c6c2 views' outline padding

    def __init__(self, *, moves: bool = True) -> None:
        half = spec.OVERALL_LENGTH * drawing._S / 2000.0
        self.seat = (drawing.SECTION_CENTER[0], drawing.SECTION_CENTER[1] + half)
        self.up = -1.0
        self.Position = drawing.SECTION_CENTER
        self.Angle = 0.0
        self.moves = moves
        self.reversed = False

    def project(self, xyz: tuple[float, float, float]) -> tuple[float, float]:
        return (
            self.seat[0] + xyz[0] * drawing._S,
            self.seat[1] + self.up * xyz[1] * drawing._S,
        )

    def GetOutline(self) -> tuple[float, float, float, float]:
        rim_y = self.project((0.0, spec.OVERALL_LENGTH / 1000.0, 0.0))[1]
        half = drawing.HALF_HEAD
        return (
            self.seat[0] - half - self.MARGIN,
            min(self.seat[1], rim_y) - self.MARGIN,
            self.seat[0] + half + self.MARGIN,
            max(self.seat[1], rim_y) + self.MARGIN,
        )

    def SetViewPosition(self, xy, _update: bool = False) -> bool:
        if self.moves:
            dx, dy = xy[0] - self.Position[0], xy[1] - self.Position[1]
            self.seat = (self.seat[0] + dx, self.seat[1] + dy)
        self.Position = tuple(xy)
        return True

    def GetSection(self):
        view = self

        class Cut:
            def GetReversedCutDirection(self) -> bool:
                return view.reversed

            def SetReversedCutDirection(self, reversed_cut: bool) -> None:
                view.reversed = reversed_cut
                view.up = -view.up

        return Cut()


def _stand(monkeypatch, view: _SectionView) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda _a, v, xyz, label: v.project(xyz)
    )
    drawing._stand_section_rim_up(object(), view)


def test_the_reversed_section_is_centred_by_its_outline(monkeypatch) -> None:
    """Run 20261001T142942518Z: re-centred on its stale Position, the
    reversed section projected its seat at y 0.18915, one nut length above
    the 0.14085 every SECTION_KEEP place assumes."""
    view = _SectionView()
    _stand(monkeypatch, view)
    assert view.reversed
    assert view.project((0.0, 0.0, 0.0)) == pytest.approx(
        (drawing.SECTION_CENTER[0], drawing._section_y(0.0))
    )
    rim = view.project((0.0, spec.OVERALL_LENGTH / 1000.0, 0.0))
    assert rim[1] == pytest.approx(drawing._section_y(spec.OVERALL_LENGTH))
    # Negative control: the stale Position the run re-centred on.
    run = _SectionView()
    run.GetSection().SetReversedCutDirection(True)
    run.SetViewPosition(drawing.SECTION_CENTER)
    assert run.project((0.0, 0.0, 0.0))[1] == pytest.approx(0.18915)


def test_a_section_whose_ink_will_not_move_is_refused(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="outline centre stayed"):
        _stand(monkeypatch, _SectionView(moves=False))


def test_the_outline_must_be_the_nut_on_its_axis() -> None:
    view = _SectionView()
    outline = view.GetOutline()
    assert drawing._outline_is_the_nut_on_end(outline)
    # The 19e33c6c2 section A-A outline, read by the layout audit.
    assert drawing._outline_is_the_nut_on_end((0.178662, 0.135262, 0.251338, 0.194738))
    # The same nut lying on its side.
    x0, y0, x1, y1 = outline
    centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    w, h = (x1 - x0) / 2.0, (y1 - y0) / 2.0
    turned = (centre[0] - h, centre[1] - w, centre[0] + h, centre[1] + w)
    assert not drawing._outline_is_the_nut_on_end(turned)


def test_the_thread_callout_stays_inside_the_left_border() -> None:
    """The source #8 thread fits; a deliberate border-crossing anchor fails."""
    from _layout_geometry import estimate_text_box

    text = f"{spec.THREAD} UNC - 2B THRU ALL"

    def left_edge(anchor: tuple[float, float]) -> float:
        box = estimate_text_box(text, anchor=anchor, height=0.0035, reference=5)
        assert box is not None
        return box.xmin

    assert left_edge(drawing.THREAD_CALLOUT_XY) > SHEET_INNER_LEFT + 0.003
    # Negative control: place the centre directly on the border.
    old = (SHEET_INNER_LEFT, drawing.THREAD_CALLOUT_XY[1])
    assert left_edge(old) < SHEET_INNER_LEFT


class _CountersinkTolerance:
    def __init__(self, *, accepts=True, persists=True):
        self.Type = 0
        self.low = self.high = 0.0
        self.accepts, self.persists = accepts, persists

    def SetValues(self, low: float, high: float) -> bool:
        if self.persists:
            self.low, self.high = low, high
        return self.accepts

    def GetMinValue(self) -> float:
        return self.low

    def GetMaxValue(self) -> float:
        return self.high


def _apply_countersink_max(monkeypatch, tolerance, *, diameter=None):
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda *_args: (object(), SimpleNamespace(
            SystemValue=(spec.CSK_DIA if diameter is None else diameter) / 1000.0,
            Tolerance=tolerance,
        )),
    )
    part._countersink_max_limit(object(), "CountersinkDia")


def test_native_countersink_max_owns_real_diameter_envelope(monkeypatch) -> None:
    tolerance = _CountersinkTolerance()
    _apply_countersink_max(monkeypatch, tolerance)
    assert tolerance.Type == spec.CSK_DIA_TOL_TYPE
    assert (
        spec.CSK_DIA + tolerance.low * 1000.0,
        spec.CSK_DIA + tolerance.high * 1000.0,
    ) == pytest.approx((spec.THREAD_MAJOR, spec.CSK_DIA))


@pytest.mark.parametrize(
    "tolerance, diameter, message",
    [(None, None, "missing"),
     (_CountersinkTolerance(accepts=False), None, "rejected"),
     (_CountersinkTolerance(persists=False), None, "persist"),
     (_CountersinkTolerance(), 6.75, "diameter")],
)
def test_native_countersink_control_refuses_unwritten_or_obsolete_geometry(
    monkeypatch, tolerance, diameter, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _apply_countersink_max(monkeypatch, tolerance, diameter=diameter)
