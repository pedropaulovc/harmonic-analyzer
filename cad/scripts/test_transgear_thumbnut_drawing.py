"""Offline contracts for the transgear thumbnut (MHA-126) part and drawing."""

from __future__ import annotations

import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _hole_spec
import build_transgear_thumbnut as part
import draw_transgear_thumbnut as drawing
import transgear_removable_spec
import transgear_thumbnut_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME

# The B landscape template's inner border, left edge (sheet metres).
SHEET_INNER_LEFT = 0.0127


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/transgear-thumbnut.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/transgear-thumbnut.pdf")
    assert (
        DRAWINGS_BY_NAME["transgear_thumbnut"].script
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


def test_no_printed_dimension_carries_a_model_band() -> None:
    """Every size is governed by its places; the thread is the native callout."""
    assert model_toleranced_dimensions(part) == {}


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
    # Positive control: the real 1/4-20 major re-executes clean.
    clean = _thumbnut_spec_with(
        monkeypatch, _hole_spec, "THREAD_MAJOR_MM", dict(_hole_spec.THREAD_MAJOR_MM)
    )
    assert min(worst for _nominal, worst in clean.WALLS.values()) >= clean.WALL_FLOOR
    # Negative control: a thread 0.2 over the waist's allowance thins the
    # waist under the 2.0 floor at the printed worst case.
    majors = dict(_hole_spec.THREAD_MAJOR_MM)
    majors[spec.THREAD] = spec.THREAD_MAJOR + 0.2
    with pytest.raises(AssertionError, match="waist"):
        _thumbnut_spec_with(monkeypatch, _hole_spec, "THREAD_MAJOR_MM", majors)


def test_the_seat_face_refuses_a_wheel_bore_it_cannot_cover(monkeypatch) -> None:
    covered = _thumbnut_spec_with(
        monkeypatch,
        transgear_removable_spec,
        "BORE_DIA",
        transgear_removable_spec.BORE_DIA,
    )
    assert covered.SEAT_OVERLAP_WORST > 0.0
    with pytest.raises(AssertionError, match="covers the T24"):
        _thumbnut_spec_with(
            monkeypatch, transgear_removable_spec, "BORE_DIA", spec.FLANGE_DIA - 0.4
        )


def test_countersinks_take_no_more_thread_than_the_engagement_deducts() -> None:
    """The contract's engagement stack deducts the rear countersink's 0.2;
    the sheet's countersink limit may not remove more."""
    printed = float(spec.CSK_QUALIFIER.split("\u00d8")[1].split()[0])
    assert "MAX" in spec.CSK_QUALIFIER.split()
    assert (printed - spec.THREAD_MAJOR) / 2.0 <= spec.REAR_THREAD_LOSS + 1e-9


def test_countersink_line_joins_the_native_thread_line() -> None:
    native = {
        5: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        6: "",
        7: "<hw-threaddesc> <hw-threadclass> <hw-thru>",
        8: "",
    }
    rewritten = drawing._thread_callout_definitions(native)
    assert rewritten[5] == native[5]
    assert rewritten[7] == f"{native[7]}\n{spec.CSK_QUALIFIER}"
    with pytest.raises(RuntimeError):
        drawing._thread_callout_definitions({**native, 5: native[7]})


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
    row = _config.parts("transgear-thumbnut")
    assert row["number"] == "MHA-126"
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
    """R9-11: the nut runs on the MHA-078 stud."""
    import transgear_knob_shaft_spec as stud

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


def test_the_shortest_nut_keeps_full_thread_for_the_stud() -> None:
    """The overall length prints at .X; the shortest nut it admits still
    gives the stud 1.5D of the nut's full thread."""
    import transgear_drive_collar_spec as collar
    import transgear_knob_shaft_spec as stud

    assert spec.OVERALL_LENGTH_LO == pytest.approx(-0.8)
    assert collar.NUT_LENGTH_MIN == pytest.approx(15.3)
    assert collar.THUMBNUT_ENGAGEMENT_WORST >= 1.5 * stud.THREAD_MAJOR
    # The nut's own full thread over its shortest length.
    full = spec.FRONT_FULL_THREAD_Y + spec.OVERALL_LENGTH_LO - spec.REAR_FULL_THREAD_Y
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
    # Nothing prints below the seat face, where the caption hangs.
    seat_y = drawing._section_y(0.0)
    assert all(y >= seat_y for _x, y in drawing.SECTION_KEEP.values())
    # The rim's diameters print above the rim, the knurl outermost.
    rim_y = drawing._section_y(spec.OVERALL_LENGTH)
    assert drawing.SECTION_KEEP["HeadDia"][1] > drawing.SECTION_KEEP["DishDia"][1]
    assert drawing.SECTION_KEEP["DishDia"][1] > rim_y
    # Negative control: the 19e33c6c2 stack sat under the seat face.
    assert _section_station(seat_y - 0.014) < 0.0


def test_the_section_stands_rim_up_or_is_refused() -> None:
    assert drawing._rim_is_up((0.2, 0.15), (0.2, 0.198))
    assert not drawing._rim_is_up((0.2, 0.198), (0.2, 0.15))
    with pytest.raises(RuntimeError, match="not vertical"):
        drawing._rim_is_up((0.2, 0.15), (0.248, 0.15))


def test_the_thread_callout_stays_inside_the_left_border() -> None:
    """Codex on 19e33c6c2: centred 0.050 left of the face view, the
    countersink line ran off the sheet's left edge."""
    from _layout_geometry import estimate_text_box

    text = f"1/4-20 UNC - 2B THRU ALL\n{spec.CSK_QUALIFIER}"

    def left_edge(anchor: tuple[float, float]) -> float:
        box = estimate_text_box(text, anchor=anchor, height=0.0035, reference=5)
        assert box is not None
        return box.xmin

    assert left_edge(drawing.THREAD_CALLOUT_XY) > SHEET_INNER_LEFT + 0.003
    # Negative control: the 19e33c6c2 anchor.
    old = (drawing.FACE_CENTER[0] - 0.050, drawing.THREAD_CALLOUT_XY[1])
    assert left_edge(old) < SHEET_INNER_LEFT
