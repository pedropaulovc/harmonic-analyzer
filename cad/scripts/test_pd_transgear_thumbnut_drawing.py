"""Offline contracts for the transgear thumbnut (MHA-PD-13) part and drawing."""

from __future__ import annotations

import ast
import asyncio
import importlib.util
from enum import Enum
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import _config
import _hole_spec
import build_pd_transgear_thumbnut as part
import draw_pd_transgear_thumbnut as drawing
import pd_transgear_thumbnut_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_layout_check import LeaderSegment, find_leader_leader_crossings
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import angular_band_deg, printed_band_mm
from _test_stubbed_build import offline_adapter, stub_seat

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
    # The cone half-angle folds into the countersink callout's "X 90°".
    assert set(drawing.FACE_KEEP) | set(drawing.SECTION_KEEP) == marked - {
        "CountersinkHalfAngle"
    }
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
    # Machinist review: the 45° ±0.5° half-angle named no mate, so the title
    # block's angular row governs it; only the MAX diameter is model-owned.
    assert model_toleranced_dimensions(part) == {}
    assert spec.CSK_HALF_ANGLE_MIN == pytest.approx(
        spec.CSK_HALF_ANGLE_DEG - angular_band_deg()
    )
    # Round 6: one MAX the part authors as text; SolidWorks' native swTolMAX
    # printed a lowercase "max.".
    assert spec.CSK_DIA_TOL_TYPE == 0
    assert spec.CSK_DIA_SUFFIX == " MAX"
    # Machinist review: a thread-entry chamfer's MAX needs few places (.XX).
    assert spec.CSK_DIA_PLACES == 2
    assert spec.DRAWING_DIMENSIONS["CountersinkProfile"] == {
        "CountersinkDia", "CountersinkHalfAngle",
    }


def test_countersink_prints_in_symbol_form_with_its_included_angle() -> None:
    # Rule 26: size, then angle, with the countersink symbol; no separate
    # half-angle dimension and no words for the countersink.
    assert drawing.DIMENSION_PREFIXES == {"CountersinkDia": "<HOLE-SINK><MOD-DIAM>"}
    assert drawing.DIMENSION_SUFFIXES["CountersinkDia"] == " MAX X 90°"
    assert drawing.DIMENSION_CALLOUTS_BELOW == {"CountersinkDia": "BOTH ENDS"}
    assert "CountersinkHalfAngle" not in drawing.SECTION_KEEP


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
    """R9-70: the nut seats on MHA-PD-22's faced pilot, not on the T24: its seat
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
    assert spec.CSK_DIA == pytest.approx(4.572)  # .18
    rear = (spec.CSK_DIA - spec.TAP_DRILL_DIA) / (
        2.0 * math.tan(math.radians(spec.CSK_HALF_ANGLE_MIN))
    )
    assert rear == pytest.approx(spec.REAR_THREAD_LOSS)
    deepest_floor = spec.DISH_DEPTH + printed_band_mm(spec.DISH_DEPTH_PLACES, unit=spec.UNIT)
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
    # Title-block .XX: the band the margins below are judged at.
    assert drawing.DRAWING_PRECISION_BY_NAME["DishFloorDia"] == 2
    assert spec.dish_floor_margins(
        spec.DISH_DIA, spec.DISH_FLOOR_DIA, spec.DISH_DEPTH, spec.CSK_DIA
    ) == pytest.approx(
        {
            "floor land outside the countersink": (8.89 - 0.254 - 4.572) / 2.0,
            "cone from the rim to the floor": (14.986 - 0.254 - 8.89 - 0.254) / 2.0,
            "floor below the rim": 1.016 - 0.254,
        }
    )
    rim, floor = spec.DISH_RIM_CORNER, spec.DISH_FLOOR_CORNER
    assert rim == pytest.approx((spec.DISH_DIA / 2.0, spec.RIM_Y))
    assert floor == pytest.approx((spec.DISH_FLOOR_DIA / 2.0, spec.DISH_FLOOR_Y))
    assert rim[1] - floor[1] == pytest.approx(spec.DISH_DEPTH)
    band = printed_band_mm(spec.DISH_FLOOR_DIA_PLACES, unit=spec.UNIT)
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
    """The rim's diameters nest left of the rim (each one's extension lines
    inside the next one's dimension line), and the dish depth's text stands
    clear of its rim extension line rather than on it, as the 6de7230aa 1.2
    did."""
    from _layout_geometry import estimate_text_box

    keep = drawing.SECTION_KEEP
    rim_x = drawing._section_x(spec.OVERALL_LENGTH)
    assert rim_x == pytest.approx(drawing.RIM_X)
    assert keep["HeadDia"][0] < keep["DishDia"][0] < keep["DishFloorDia"][0] < rim_x

    def box(text: str, anchor: tuple[float, float], reference: int = 2):
        found = estimate_text_box(text, anchor=anchor, height=0.0035, reference=reference)
        assert found is not None
        return found

    # The knurl's text, widest row, ends left of the dish diameter's line and
    # clear of the face view; the dish values clear each other's lines.
    knurl = box(drawing.KNURL_CALLOUT, keep["HeadDia"], reference=5)
    assert 1.15 * (knurl.xmax - keep["HeadDia"][0]) < keep["DishDia"][0] - keep["HeadDia"][0]
    face_right = drawing.FACE_CENTER[0] + drawing.HALF_HEAD
    assert keep["HeadDia"][0] - 1.15 * (keep["HeadDia"][0] - knurl.xmin) > face_right + 0.003
    assert box("Ø.59", keep["DishDia"]).xmax < keep["DishFloorDia"][0] - 0.002
    assert box("Ø.35", keep["DishFloorDia"]).xmin > keep["DishDia"][0] + 0.002
    # The stagger keeps the dish values off the axis centreline and inside
    # their own spans.
    for name, dia in (("DishDia", spec.DISH_DIA), ("DishFloorDia", spec.DISH_FLOOR_DIA)):
        offset = abs(keep[name][1] - drawing.SECTION_CENTER[1])
        assert 0.004 < offset < dia * drawing._S / 2000.0 - 0.003, name

    assert box("1.0", keep["DishDepth"]).xmax < rim_x
    assert keep["DishDepth"][1] < drawing.HEAD_BOTTOM - 0.010
    # Negative control: the 6de7230aa anchor on the rim face.
    assert box("1.0", (rim_x, keep["DishDepth"][1])).xmax > rim_x


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


class _Readback(Enum):
    """How the fake callout's resolved rows read back after the edit."""

    FOLLOWS_DEFINITION = "follows"
    KEEPS_CLASS = "keeps"


class _NativeTapCallout:
    """A native hole callout whose resolved rows follow its prefix definition."""

    def __init__(self, readback: _Readback = _Readback.FOLLOWS_DEFINITION) -> None:
        self.definition = "<hw-threaddesc> - <hw-threadclass> THRU ALL"
        self.readback = readback

    def IsHoleCallout(self) -> bool:
        return True

    def SetText(self, part: int, text: str) -> None:
        assert part == 1
        self.definition = text

    def GetText(self, part: int) -> str:
        if part == 5:
            return self.definition
        if part == 1:
            resolved = self.definition.replace("<hw-threaddesc>", "#8-32 UNC")
            resolved = resolved.replace("<hw-threadclass>", "2B")
            if self.readback is _Readback.KEEPS_CLASS:
                resolved += " - 2B"
            return resolved
        return ""


def test_tap_callout_leaves_the_class_to_the_title_block(monkeypatch) -> None:
    import _hole_callout_thread_class as thread_class

    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(thread_class, "_early_bound", lambda value, _kind: value)
    native = _NativeTapCallout()
    drawing._omit_thread_class(native)
    assert native.definition == "<hw-threaddesc> THRU ALL"
    assert native.GetText(1) == "#8-32 UNC THRU ALL"
    # Negative control: a callout whose rows still resolve the class refuses.
    with pytest.raises(RuntimeError, match="still prints its class"):
        drawing._omit_thread_class(_NativeTapCallout(_Readback.KEEPS_CLASS))


def test_tap_callout_refuses_to_omit_a_nondefault_class(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "TAP_SPEC", SimpleNamespace(thread_class="3B"))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a nondefault class must not reach the native edit")

    monkeypatch.setattr(drawing, "omit_title_block_thread_class", forbidden)
    with pytest.raises(RuntimeError, match="only the title block's default class 2B"):
        drawing._omit_thread_class(object())


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
    assert row["number"] == "MHA-PD-13"
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
    """R9-11: the nut runs on the MHA-PD-08 stud."""
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
    import _part_properties
    import _drawing_marks

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
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


def test_the_knurl_is_the_designated_wheel() -> None:
    """R9-57: the modelled teeth are the 90° straight knurl the callout names
    (25 TPI, 1.016 mm pitch), so the shop's wheel forms what the model shows."""
    assert spec.KNURL_PITCH == pytest.approx(25.4 / 25)
    assert spec.KNURL_CREST_PITCH == pytest.approx(spec.KNURL_PITCH, rel=0.01)
    assert spec.KNURL_TOOTH_ANGLE_DEG == pytest.approx(90.0, abs=2.0)
    assert spec.KNURL_DESIGNATION in spec.KNURL_CALLOUT
    # Negative control: the 19e33c6c2 model (60 teeth over a Ø19.7 root
    # under its Ø20.5 crests) was a 1.07-pitch, 108.5° V no standard wheel forms.
    old_angle = spec.knurl_tooth_angle_deg(20.5, 19.7, 60)
    assert old_angle == pytest.approx(108.5, abs=0.1)
    assert math.pi * 20.5 / 60 - spec.KNURL_PITCH > 0.01


def test_the_knurl_designation_is_authored_where_it_prints() -> None:
    """Run 20261001T154021634Z's machinist review: the sheet showed Ø20.5 and
    no knurl.  The designation rode a two-line above-callout, which SolidWorks
    stored but did not print; one line in that compartment prints.  Round 3:
    a callout wider than the Ø.81 span ran the dimension line out under its
    text, so it fits between the extension lines."""
    from _layout_geometry import estimate_text_box

    above = drawing.DIMENSION_CALLOUTS_ABOVE
    assert spec.KNURL_DESIGNATION in above["HeadDia"]
    assert "OVER KNURL" in drawing.DIMENSION_SUFFIXES["HeadDia"]
    assert drawing._printable_above_callouts(above) == above
    with pytest.raises(RuntimeError, match="HeadDia"):
        drawing._printable_above_callouts(
            {"HeadDia": f"STRAIGHT KNURL {spec.KNURL_DESIGNATION}\nDIA OVER KNURL"}
        )

    def width(text: str) -> float:
        box = estimate_text_box(text, anchor=(0.0, 0.0), height=0.0035, reference=5)
        assert box is not None
        return box.xmax - box.xmin

    # The estimate reads ~11 % short of the printed ink (round 3's callout:
    # 0.104 estimated, 0.116 printed), so charge that margin.
    span = spec.HEAD_DIA * drawing._S / 1000.0
    assert 1.15 * width(above["HeadDia"]) < span
    # Negative control: round 3's one-line callout overran the span.
    assert width("STRAIGHT KNURL 25 TPI, 90° TOOTH; DIA OVER KNURL") > span


def test_the_shortest_nut_keeps_full_thread_for_the_stud() -> None:
    """The overall length prints at .XX; the shortest nut it admits still
    gives the stud 1.5D of the nut's full thread."""
    import pd_transgear_drive_collar_spec as collar
    import pd_transgear_knob_shaft_spec as stud

    assert spec.OVERALL_LENGTH_LO == pytest.approx(-0.254)
    assert collar.NUT_LENGTH_MIN == pytest.approx(15.748)
    assert collar.THUMBNUT_ENGAGEMENT_WORST >= 1.5 * stud.THREAD_MAJOR
    # The nut's own full thread over its shortest length, the front
    # countersink on the deepest printed floor.
    shortest_rim = spec.RIM_Y + spec.OVERALL_LENGTH_LO
    full = shortest_rim - spec.FRONT_THREAD_LOSS - spec.REAR_FULL_THREAD_Y
    assert full >= 1.5 * spec.THREAD_MAJOR


def _section_station(x: float) -> float:
    """Model station (from the seat face) of sheet ``x`` on A-A (seat right)."""
    return spec.OVERALL_LENGTH / 2.0 - (x - drawing.SECTION_CENTER[0]) * 1000.0 / drawing._S


def test_the_section_lies_axis_horizontal_beside_the_face_view() -> None:
    """Round 4 of run 20261107T201806645Z (rule 11): A-A stood axis-vertical.
    It lies as in the lathe, rim left and seat right, on the face view's
    horizontal centreline (third angle), cut on the face view's vertical
    centreline."""
    assert drawing.SECTION_CENTER[1] == drawing.FACE_CENTER[1]
    assert drawing.FACE_VIEW_ANGLE == pytest.approx(math.pi / 2.0)
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1 == drawing.FACE_CENTER[0]
    assert y1 - y0 > 2.0 * drawing.HALF_HEAD
    assert drawing.RIM_X < drawing.SEAT_X
    assert drawing.SEAT_X - drawing.RIM_X == pytest.approx(
        spec.OVERALL_LENGTH * drawing._S / 1000.0
    )
    assert _section_station(drawing.SEAT_X) == pytest.approx(0.0)
    assert drawing.FACE_CENTER[0] + drawing.HALF_HEAD < drawing.SECTION_KEEP["HeadDia"][0]
    # The isometric stays right of everything A-A prints.
    assert max(x for x, _ in drawing.SECTION_KEEP.values()) + 0.035 < drawing.ISO_CENTER[0] - 0.035


def test_the_stem_diameters_print_across_their_own_cut() -> None:
    """Codex on 19e33c6c2: the stem's extension lines ran through the head's
    hatching.  Each diameter's line runs at its own feature's middle, its
    text below the part, so no extension line crosses another feature's
    cut; round 4's Ø.43 line on the Ø.49 shoulder stays fixed."""
    flange_bottom = drawing._section_y(-spec.FLANGE_DIA / 2.0)
    for name, (lo, hi), floor in (
        ("FlangeDia", (0.0, spec.FLANGE_LENGTH), flange_bottom),
        ("WaistDia", (spec.FLANGE_LENGTH, spec.HEAD_REAR_Y), drawing.HEAD_BOTTOM),
    ):
        x, y = drawing.SECTION_KEEP[name]
        assert _section_station(x) == pytest.approx((lo + hi) / 2.0), name
        assert y < floor - 0.008, name
    # The waist's line stands clear of the flange's shoulder and the head.
    waist_x = drawing.SECTION_KEEP["WaistDia"][0]
    gap = spec.WAIST_LENGTH * drawing._S / 2000.0
    assert gap > 0.003
    assert waist_x - drawing._section_x(spec.HEAD_REAR_Y) == pytest.approx(gap)
    # The two values stagger: the waist's text below the flange's.
    assert drawing.SECTION_KEEP["WaistDia"][1] < drawing.SECTION_KEEP["FlangeDia"][1] - 0.008
    # The cone diameter's line stands right of the seat face, its two rows
    # below the waist's value and above the caption.
    dia = drawing.SECTION_KEEP["CountersinkDia"]
    assert drawing.SEAT_X < dia[0] < drawing.SEAT_X + 0.012
    assert dia[1] < drawing.SECTION_KEEP["WaistDia"][1] - 0.008
    turned = set().union(
        *(spec.DRAWING_DIMENSIONS[feature] for feature in ("HeadProfile", "StemProfile", "DishProfile"))
    )
    assert len(turned) == 9


def test_lengths_read_from_the_seat_face() -> None:
    """Machinist review: the 2.4 waist chained off the head's 8.7 shoulder.
    The flange length and the head's rear face read from the faced seat face,
    baseline with the overall length; the waist is their remainder and does
    not print."""
    assert spec.DRAWING_DIMENSIONS["HeadProfile"] == {"HeadDia", "HeadRearY", "OverallLength"}
    stem = spec.DRAWING_DIMENSIONS["StemProfile"]
    assert "FlangeLength" in stem and "WaistLength" not in stem
    assert (spec.FLANGE_LENGTH, spec.HEAD_REAR_Y) == pytest.approx((5.08, 7.366))
    assert spec.HEAD_REAR_Y - spec.FLANGE_LENGTH == pytest.approx(spec.WAIST_LENGTH)
    # Three lanes above the knurl, flange inner, overall outer, each text
    # mid-span from the seat and its line on its lane.
    lines = []
    for name, end, lane in zip(
        ("FlangeLength", "HeadRearY", "OverallLength"),
        (spec.FLANGE_LENGTH, spec.HEAD_REAR_Y, spec.OVERALL_LENGTH),
        drawing.LENGTH_LANES,
        strict=True,
    ):
        x, y = drawing.SECTION_KEEP[name]
        assert _section_station(x) == pytest.approx(end / 2.0), name
        line = y - drawing.DIM_LINE_BELOW_TEXT
        assert line == pytest.approx(drawing.HEAD_TOP + lane), name
        lines.append(line)
    assert all(b - a >= 0.009 for a, b in zip(lines, lines[1:]))
    assert lines[0] - drawing.HEAD_TOP >= 0.008
    # Run 20261024T025840809Z: an outside arrow hung past the seat into
    # the cone diameter's "max."; both spans hold their arrows inside, and
    # round 3's knurl diameter, whose outside tail ran under its callout.
    assert drawing.ARROWS_INSIDE == ("FlangeLength", "HeadRearY", "HeadDia")


def test_the_section_axis_is_sketched_at_the_sheet_scale() -> None:
    """Round 3's gating finding: the projected axis passed straight into the
    3:1 sheet sketch printed three times out, from the top border down onto
    the isometric.  Sketch points are sheet points over the sheet scale, so
    the printed line lands back on the section."""
    end = (
        drawing._section_x(-drawing.AXIS_OVERSHOOT_MM),
        drawing.SECTION_CENTER[1],
    )
    sketch = drawing._sheet_sketch_point(end)
    printed = (sketch[0] * drawing._S, sketch[1] * drawing._S)
    assert printed == pytest.approx(end)
    # Negative control: the unscaled point prints off the 431.8 mm sheet.
    assert end[0] * drawing._S > 0.4318


def test_the_waist_keeps_a_length_at_every_printed_corner(monkeypatch) -> None:
    """codjiflo on 11fe6c440: chained from the rim and the seat, the waist
    could close to 0. From the seat, the head's rear face at its lowest
    stands clear above the flange's shoulder at its highest."""
    band = printed_band_mm(2, unit=spec.UNIT)
    assert spec.WAIST_LENGTH_WORST == pytest.approx(
        (spec.HEAD_REAR_Y - band) - (spec.FLANGE_LENGTH + band)
    )
    assert spec.WAIST_LENGTH_WORST == pytest.approx(1.778)
    # The spec's own gate refuses a printed row wide enough to close the
    # waist (two-place bands 5x wider; the walls still hold first).
    import _printed_tolerance

    real = _printed_tolerance.printed_deviations

    def wider(nominal: float, places: int, **kwargs) -> tuple[float, float]:
        lo, hi = real(nominal, places, **kwargs)
        return (lo * 5.0, hi * 5.0) if places == 2 else (lo, hi)

    with pytest.raises(AssertionError, match="waist closes"):
        _thumbnut_spec_with(monkeypatch, _printed_tolerance, "printed_deviations", wider)


def test_the_section_caption_hangs_below_the_cone_diameter() -> None:
    """Machinist review: the cone diameter's line and extension lines struck the
    default caption's letters.  The caption's top stands below the cone
    diameter's two rows (value and BOTH ENDS) and the dish depth."""
    from _layout_geometry import estimate_text_box

    caption = drawing.SECTION_CAPTION_XY
    assert caption[0] == drawing.SECTION_CENTER[0]
    cone = estimate_text_box(
        "Ø.18 MAX X 90°\nBOTH ENDS",
        anchor=drawing.SECTION_KEEP["CountersinkDia"],
        height=0.0035,
        reference=2,
    )
    assert cone is not None
    assert cone.ymin - caption[1] >= 0.004
    assert drawing.SECTION_KEEP["DishDepth"][1] - caption[1] >= 0.010
    # The caption (one row now that it states no scale) stays above the
    # inner border, 12.7 mm up.
    assert caption[1] - 0.008 > 0.0127 + 0.005


def test_dimension_affixes_are_written_and_read_back(monkeypatch) -> None:
    class Display:
        def __init__(self):
            self.text = {1: "", 2: ""}

        def SetText(self, part, text):
            self.text[part] = text

        def GetText(self, part):
            return self.text[part]

    annotations = {
        name: SimpleNamespace(name=name, display=Display())
        for name in ("HeadDia", "CountersinkDia")
    }
    for annotation in annotations.values():
        annotation.GetSpecificAnnotation = lambda a=annotation: a.display
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    drawing._set_dimension_affixes(object(), list(annotations.values()))
    cone = annotations["CountersinkDia"].display.text
    assert cone == {1: "<HOLE-SINK><MOD-DIAM>", 2: " MAX X 90°"}
    with pytest.raises(RuntimeError, match="no thumbnut dimension"):
        drawing._set_dimension_affixes(object(), [annotations["HeadDia"]])


def test_the_sheet_is_pinned_at_its_printed_scale_before_the_section(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    sheet = MagicMock()
    sheet.SetScale.return_value = True
    sheet.GetProperties2.return_value = [0, 0, 3.0, 1.0]
    adapter = MagicMock()
    adapter._get_attr_or_call.side_effect = lambda obj, name: (
        sheet if name == "GetCurrentSheet" else getattr(obj, name)()
    )
    drawing._pin_sheet_scale(adapter)
    sheet.SetScale.assert_called_once_with(3.0, 1.0, False, False)
    sheet.GetProperties2.return_value = [0, 0, 2.0, 1.0]
    with pytest.raises(RuntimeError, match="did not persist"):
        drawing._pin_sheet_scale(adapter)


class _SectionView:
    """Section A-A as cut from the quarter-turned face view: the axis lies
    horizontal through Position, ``Angle`` turns the ink about it, and
    ``SetViewPosition`` moves the ink with Position (run 20261001T142942518Z).
    It starts rim right, off the place SECTION_KEEP assumes."""

    def __init__(self, *, moves: bool = True, angle: float = 0.0) -> None:
        self.Position = (0.180, 0.140)
        self.Angle = angle
        self.moves = moves

    def project(self, xyz: tuple[float, float, float]) -> tuple[float, float]:
        along = (xyz[1] * 1000.0 - spec.OVERALL_LENGTH / 2.0) * drawing._S / 1000.0
        across = xyz[0] * drawing._S
        c, s = math.cos(self.Angle), math.sin(self.Angle)
        return (
            self.Position[0] + along * c - across * s,
            self.Position[1] + along * s + across * c,
        )

    def SetViewPosition(self, xy, _update: bool = False) -> bool:
        if self.moves:
            self.Position = tuple(xy)
        return True


def _orient(monkeypatch, view: _SectionView) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "double_array", list)
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda _a, v, xyz, label: v.project(xyz)
    )
    drawing._orient_section(object(), view)


def test_the_section_is_laid_seat_right_on_its_centre(monkeypatch) -> None:
    view = _SectionView()
    # As created, the rim lies right: half a turn from where it belongs.
    assert drawing._axis_turn(view.project((0, 0, 0)), view.project((0, 0.016, 0))) == (
        pytest.approx(math.pi)
    )
    _orient(monkeypatch, view)
    assert view.project((0.0, 0.0, 0.0)) == pytest.approx(
        (drawing.SEAT_X, drawing.SECTION_CENTER[1])
    )
    assert view.project((0.0, spec.OVERALL_LENGTH / 1000.0, 0.0)) == pytest.approx(
        (drawing.RIM_X, drawing.SECTION_CENTER[1])
    )


def test_a_section_whose_ink_will_not_move_is_refused(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="axis ends at seat"):
        _orient(monkeypatch, _SectionView(moves=False, angle=math.pi))


def test_a_section_off_the_horizontal_is_refused(monkeypatch) -> None:
    with pytest.raises(RuntimeError, match="off the sheet's horizontal"):
        _orient(monkeypatch, _SectionView(angle=math.pi / 2.0))


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
    """A tolerance that keeps its type, or one stuck at the old swTolMAX."""

    def __init__(self, *, persists=True):
        self._type = 6
        self.persists = persists

    @property
    def Type(self) -> int:
        return self._type

    @Type.setter
    def Type(self, value: int) -> None:
        if self.persists:
            self._type = value


class _CountersinkDisplay:
    def __init__(self, *, persists=True):
        self.texts: dict[int, str] = {}
        self.persists = persists

    def SetText(self, part: int, text: str) -> None:
        if self.persists:
            self.texts[part] = text

    def GetText(self, part: int) -> str:
        return self.texts.get(part, "")


def _apply_countersink_max(monkeypatch, tolerance, display=None, *, diameter=None):
    display = _CountersinkDisplay() if display is None else display
    monkeypatch.setattr(part, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        part, "_named_dimension",
        lambda *_args: (display, SimpleNamespace(
            SystemValue=(spec.CSK_DIA if diameter is None else diameter) / 1000.0,
            Tolerance=tolerance,
        )),
    )
    part._countersink_max_limit(object(), "CountersinkDia")
    return display


def test_the_countersink_prints_its_single_max_as_authored_text(monkeypatch) -> None:
    tolerance = _CountersinkTolerance()
    display = _apply_countersink_max(monkeypatch, tolerance)
    assert tolerance.Type == spec.CSK_DIA_TOL_TYPE == 0
    assert display.GetText(2) == spec.CSK_DIA_SUFFIX
    # The modelled size IS the max, and it clears the thread major.
    assert spec.CSK_DIA > spec.THREAD_MAJOR


@pytest.mark.parametrize(
    "tolerance, display, diameter, message",
    [(None, None, None, "missing"),
     (_CountersinkTolerance(persists=False), None, None, "persist"),
     (_CountersinkTolerance(), _CountersinkDisplay(persists=False), None, "persist"),
     (_CountersinkTolerance(), None, 6.75, "diameter")],
)
def test_native_countersink_control_refuses_unwritten_or_obsolete_geometry(
    monkeypatch, tolerance, display, diameter, message
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _apply_countersink_max(monkeypatch, tolerance, display, diameter=diameter)


def test_build_pins_the_sheet_before_the_section_and_writes_affixes_after_callouts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    source = tmp_path / "source.SLDPRT"
    source.write_bytes(b"")
    monkeypatch.setattr(drawing, "SOURCE", source)
    seat = stub_seat(monkeypatch, drawing)
    monkeypatch.setattr(drawing, "_assert_native_thread", MagicMock())
    seat.new_project_drawing.return_value = (MagicMock(), MagicMock())
    seat.curate_view_dimensions.side_effect = (
        lambda _adapter, _view, *, view_label, **_kwargs: [f"{view_label} dimension"]
    )
    asyncio.run(drawing.build(offline_adapter()))

    (written,) = seat._set_dimension_affixes.call_args_list
    assert written.args[1] == ["axial section dimension"]
    names = [name for name, _args, _kwargs in seat.mock_calls]
    assert names.index("_pin_sheet_scale") < names.index("create_section_view")
    affixes = names.index("_set_dimension_affixes")
    callouts = [k for k, name in enumerate(names) if name == "set_dimension_callouts"]
    assert len(callouts) == 2 and max(callouts) < affixes < names.index("finalize_drawing")
