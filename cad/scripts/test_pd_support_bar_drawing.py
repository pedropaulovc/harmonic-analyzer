"""Offline contracts for the support-bar drawing (MHA-PD-007)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import build_pd_support_bar as part
import draw_pd_support_bar as drawing
import pd_support_bar_drawing_spec as sheet_spec
import pd_support_bar_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME

_MATES = ("MHA-PD-011", "MHA-PD-012", "MHA-PD-014", "MHA-VN-041", "MHA-VN-043")


def test_registry_identity_and_paths() -> None:
    row = DRAWINGS_BY_NAME["pd_support_bar"]
    assert (row.part, row.artifact_stem) == ("pd_support_bar", "pd-support-bar")
    assert row.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-support-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-support-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-support-bar_drawing.png")
    assert "draw_pd_support_bar.py" in PRECISION_MIGRATED_DRAWINGS
    import _config

    config = _config.parts("pd-support-bar")
    assert config["number"] == "MHA-PD-007"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_marked_dimensions_are_the_kept_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is sheet_spec.DRAWING_DIMENSIONS
    marked = set().union(*sheet_spec.DRAWING_DIMENSIONS.values())
    kept = [*drawing.FRONT_KEEP, *drawing.BACK_KEEP, *drawing.SECTION_KEEP_NAMES]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_printed_bands_are_the_spec_bands() -> None:
    assert model_toleranced_dimensions(part) == {
        ("BarProfile", "Height"): "BAR_HEIGHT_BAND",
        ("Bar", "Depth"): "BAR_DEPTH_BAND",
        ("HangerRowReference", "name"): "HOLE_POSITION_BAND",
        ("PivotTap", "DrillDepth"): "*PIVOT_TAP_DRILL_DEPTH_LIMITS",
    }
    assert part.HANGER_STATION_NAMES == sheet_spec.HANGER_STATION_NAMES
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for name in ("HangerRowHeight", *HANGER_STATION_NAMES):' in source
    assert spec.HOLE_POSITION_BAND == 0.065
    assert spec.PIVOT_TAP_DRILL_DEPTH_LIMITS == (-0.4, 0.0)
    # The band's places print it whole: .XXX for ±0.065 and the bar bands.
    places = sheet_spec.DRAWING_PRECISION
    assert places["HangerRowReference"] == dict.fromkeys(
        ("HangerRowHeight", *sheet_spec.HANGER_STATION_NAMES), 3
    )
    assert places["BarProfile"]["Height"] == places["Bar"]["Depth"] == 3
    assert places["PivotTap"]["DrillDepth"] == 1


def test_single_limits_are_the_spec_limits() -> None:
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = {
        tuple(ast.unparse(arg) for arg in node.args[1:])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_single_limit"
    }
    assert calls == {
        (
            "'PivotThreadReference'",
            "'ThreadMin'",
            "PIVOT_TAP_FULL_THREAD_MIN",
            "TOL_MIN",
        ),
        ("'CountersinkReference'", "'PivotCskDia'", "PIVOT_TAP_CSK_DIA", "TOL_MAX"),
        (
            "'CountersinkReference'",
            "'BracketCskDia'",
            "BRACKET_TAP_CSK_DIA",
            "TOL_MAX",
        ),
    }
    assert (sheet_spec.TOL_MIN, sheet_spec.TOL_MAX) == (5, 6)
    assert spec.PIVOT_TAP_FULL_THREAD_MIN == 5.2
    assert (spec.PIVOT_TAP_CSK_DIA, spec.BRACKET_TAP_CSK_DIA) == (4.3, 3.1)


def test_row_nominals_are_the_built_holes() -> None:
    left = -part.BAR_LENGTH / 2.0
    assert part.HANGER_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0 - spec.HANGER_TAP_Y == 14.5
    assert part.HANGER_STATIONS == pytest.approx(
        tuple(x - left for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X))
    )
    assert part.HANGER_STATIONS == (168.0, 291.0, 298.0)
    # Both rows read from the same (left, x = -226) end.
    assert part.CLAMP_ROW_START_X == left
    assert part.CLAMP_ROW_X == (-214.5, -179.5, 179.5, 214.5)
    assert sorted(part.CLAMP_ROW_X) == sorted(part.CLAMP_HOLE_X)
    assert part.CLAMP_STATIONS == (11.5, 46.5, 405.5, 440.5)
    assert part.CLAMP_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0


def test_rows_stack_shortest_nearest_the_bar() -> None:
    def heights(keep: dict, names: tuple[str, ...]) -> list[float]:
        return [keep[name][1] for name in names]

    face = heights(drawing.FRONT_KEEP, (*sheet_spec.HANGER_STATION_NAMES, "Length"))
    back = heights(drawing.BACK_KEEP, sheet_spec.CLAMP_STATION_NAMES)
    for rows, bar_bottom in (
        (face, drawing.FACE_BOTTOM),
        (back, drawing.BACK_BOTTOM),
    ):
        assert all(y < bar_bottom for y in rows)
        assert all(a - b >= 0.008 - 1e-9 for a, b in zip(rows, rows[1:]))
    # Long-row texts stay between their extension lines.
    for name, span in zip(
        (*sheet_spec.HANGER_STATION_NAMES[1:], "Length"),
        (*part.HANGER_STATIONS[1:], part.BAR_LENGTH),
    ):
        x = drawing.FRONT_KEEP[name][0]
        assert drawing.LEFT_END < x < drawing.LEFT_END + span * drawing._S
    # In the front-face view that end is on the sheet's right: the long clamp
    # rows' texts stand between it and their holes; the first row's, too
    # short a span, stands between the first two holes.
    for name, hole_x in zip(sheet_spec.CLAMP_STATION_NAMES[1:], part.CLAMP_ROW_X[1:]):
        x = drawing.BACK_KEEP[name][0]
        assert drawing._back_x(hole_x) < x < drawing.RIGHT_END, name
    first = drawing.BACK_KEEP[sheet_spec.CLAMP_STATION_NAMES[0]][0]
    assert (
        drawing._back_x(part.CLAMP_ROW_X[1])
        < first
        < drawing._back_x(part.CLAMP_ROW_X[0])
    )


def test_sheet_texts_carry_no_dimensions_and_stay_short() -> None:
    # No general note: each slide grade's reason sits by its symbol.
    assert not hasattr(sheet_spec, "DRAWING_NOTES")
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
    for text in (
        sheet_spec.TOP_FINISH_REASON,
        sheet_spec.FRONT_FINISH_REASON,
        sheet_spec.FACE_VIEW_CAPTION,
        sheet_spec.BACK_VIEW_CAPTION,
    ):
        assert len(text.splitlines()) == 1
        assert re.search(r"\d", text) is None
        for token in ("Ø", "±", "+/-", "MIN", "MAX", "DATUM"):
            assert token not in text
    assert sheet_spec.ISOMETRIC_VIEW_NOTE.endswith(
        f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    )


def test_callouts_name_the_mates() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    for name in ("Height", "Depth", "HangerRowHeight", "PivotCskDia"):
        assert any(mate in callouts[name] for mate in _MATES), name
    assert "MHA-PD-011" in callouts["Height"]
    assert "MHA-VN-043" in callouts["Depth"]
    assert "MHA-VN-041" in callouts["HangerRowHeight"]
    assert "MHA-PD-014" in callouts["HangerRowHeight"]
    # Each tight hanger station names the part it places.
    assert "MHA-VN-041" in callouts["PivotTapStation"]
    assert "MHA-PD-014" in callouts["BracketTapStation1"]
    assert "MHA-PD-014" in callouts["BracketTapStation2"]
    # The thread class is the title block's (rule 2), native callout too.
    assert callouts["PivotTapDrillDia"] == "TAP #8-32 UNC"
    assert "2B" not in "".join(callouts.values())
    assert drawing._THREAD_CLASS_TOKEN == " <hw-threadclass>"
    assert callouts["DrillDepth"] == "FLAT BOTTOM"
    assert callouts["ThreadMin"] == "FULL THREAD"
    assert callouts["BracketCskDia"].startswith("2X 90\u00b0 CSK")
    for text in callouts.values():
        assert len(text.splitlines()) <= 3
    assert "MHA-VN-021" in sheet_spec.CLAMP_CBORE_CALLOUT
    assert "SLIDE FACE" in sheet_spec.CLAMP_CBORE_CALLOUT


def test_slide_faces_carry_the_slide_grade() -> None:
    from _surface_finish import MACHINED_UM

    controls = {control.key: control for control in sheet_spec.SURFACE_FINISHES}
    assert set(controls) == {"top_slide", "front_slide"}
    assert {control.roughness_um for control in controls.values()} == {MACHINED_UM}
    top, front = controls["top_slide"].face, controls["front_slide"].face
    assert (top.normal, top.offset_mm) == ((0, 1, 0), spec.BAR_HEIGHT / 2.0)
    assert (front.normal, front.offset_mm) == ((0, 0, -1), spec.BAR_DEPTH / 2.0)
    # The front-face leader lands on the face, clear of every hole.
    x, y = drawing.FRONT_FINISH_MODEL_XY
    assert abs(y) < spec.BAR_HEIGHT / 2.0
    assert all(
        abs(x - hole) > part.CLAMP_CBORE_DIA
        for hole in (*part.CLAMP_HOLE_X, *spec.BRACKET_TAP_X)
    )
    assert (
        drawing.LEFT_END
        < drawing._face_x(drawing.TOP_FINISH_MODEL_X)
        < drawing._face_x(spec.PIVOT_TAP_X)
    )


def test_build_authors_marks_properties_and_hides_references() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for needle in (
        'name_dimensions(adapter, "PivotTap", ["DrillDepth"])',
        "apply_drawing_precision(adapter, SHEET_PRECISION)",
        "clear_dimensions_for_drawing(adapter)",
        "blank_reference_sketches(adapter, REFERENCE_SKETCHES)",
        '"Isometric View Note": ISOMETRIC_VIEW_NOTE',
        "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)",
    ):
        assert source.count(needle) == 1, needle
    hidden = {
        name for name in sheet_spec.DRAWING_DIMENSIONS if name.endswith("Reference")
    }
    assert hidden == set(part.REFERENCE_SKETCHES)
    # Precision follows the bar bands' pinned literal, after the drive.
    pinned = source.index(
        '{"BarProfile": {"Height": BAR_BAND_PLACES}, "Bar": {"Depth": BAR_BAND_PLACES}}'
    )
    assert source.index("drive_dimension(") < pinned
    assert pinned < source.index("apply_drawing_precision(adapter, SHEET_PRECISION)")


def test_hole_callouts_pick_the_tap_and_counterbore_edges(monkeypatch) -> None:
    picks = []

    class _Edges:
        def circle_at(self, center, radius, *, axis, label, radius_tol_mm):
            picks.append((center, radius, axis))

            class _Hit:
                edge = label

            return _Hit()

    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, *, label: _Edges())
    assert drawing._hole_rims(object(), object()) == (
        "latch-hook tap edge",
        "clamp counterbore rim",
    )
    tap_dia = part.blind_cut_dia_mm(spec.BRACKET_TAP_SPEC)
    csk_depth = (spec.BRACKET_TAP_CSK_DIA - tap_dia) / 2.0
    assert picks == [
        (
            (spec.BRACKET_TAP_X[0], spec.HANGER_TAP_Y, spec.BACK_FACE_Z - csk_depth),
            tap_dia / 2.0,
            (0.0, 0.0, 1.0),
        ),
        (
            (max(part.CLAMP_ROW_X), 0.0, -spec.BAR_DEPTH / 2.0),
            part.CLAMP_CBORE_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
    ]


def test_isometric_is_drawn_hidden_lines_removed() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (face, back, iso):" in source
    assert "set_hidden_lines_removed(adapter, view)" in source


def test_clamp_heads_stay_under_the_front_face_at_the_printed_worst_case() -> None:
    from _printed_tolerance import printed_band_mm

    places = sheet_spec.CLAMP_CBORE_DEPTH_PLACES
    printed = round(part.CLAMP_CBORE_DEPTH, places)
    band = printed_band_mm(places)
    shallowest, deepest = printed - band, printed + band
    # The platen slides across the front face: the head never stands proud.
    assert part.CLAMP_HEAD_H < shallowest
    # Rule 17: the floor under the deepest counterbore in the thinnest bar.
    assert (spec.BAR_DEPTH - spec.BAR_DEPTH_BAND) - deepest >= 2.0
