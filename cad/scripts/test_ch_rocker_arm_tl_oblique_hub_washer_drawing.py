"""Offline contracts for the MHA-CH-06-TL-52 oblique-trammel hub top-hat washer."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_hub_washer as part
import ch_rocker_arm_tl_oblique_hub_washer_spec as spec
import ch_rocker_strap_notes as strap_notes
import ch_rocker_strap_spec as strap
import draw_ch_rocker_arm_tl_oblique_hub_washer as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_91251a197 import DIMS as HUB_SCREW
from _printed_tolerance import edge_break_chamfer_mm, inside_corner_radius_mm
from ch_rocker_hub_fit import STRAP_HOLE_BAND

STEM = "ch-rocker-arm-tl-oblique-hub-washer"
INCH = 25.4
# ASME B18.3 #8 SHCS underhead fillet, largest transition diameter (.188 in).
SCREW_FILLET_DIA_MAX = 0.188 * INCH


def test_registry_row_is_the_turned_brass_washer() -> None:
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-52"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "C36000" in row["material_specification"]
    assert "13/64" in row["process"] and "one chucking" in row["process"]
    # A literal, so verify's static PART_NAME scan registers the build.
    assert part.PART_NAME == spec.STEM == STEM
    assert part.MATERIAL == "Brass"


def test_flange_wall_shortfall_is_the_declared_owner_minor() -> None:
    # Owner ruling 2026-11-07 (#2249, option A): .06 ±.01 flange kept, its
    # .005-broken rims leave .040, stated floored on the sheet.
    from machinist_exceptions import load_exceptions

    assert spec.FLANGE_WALL_MIN == pytest.approx(1.270 - 2.0 * 0.127)
    assert spec.FLANGE_WALL_MIN < WALL_FLOOR_MM
    assert spec.FLANGE_WALL_MIN_TEXT == ".040"
    assert spec.FLANGE_WALL_CALLOUT == "WALL .040 MIN AT RIMS"
    assert drawing.DIMENSION_CALLOUTS["WasherThickness"].splitlines()[-1] == (
        spec.FLANGE_WALL_CALLOUT
    )
    (wall,) = load_exceptions(_config.CONFIG_DIR, "ch_rocker_arm_tl_oblique_hub_washer", "part")
    assert (wall.id, wall.kind) == ("RV-01", "minor")
    assert spec.FLANGE_WALL_CALLOUT in wall.where
    assert "2026-11-07" in wall.reason and "#2249" in wall.reason
    # The 1.5D full thread the thicker .XX flanges would cost is the holding
    # spec's; this sheet carries no thread gate.


def test_sheet_is_registered_and_enforced() -> None:
    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_washer"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert sheet.script_name in PRECISION_MIGRATED_DRAWINGS


def test_owner_r4_top_hat_sizes() -> None:
    # Owner R4 rulings 2026-11-07: Ø11 flange (on the .433 grid), spigot
    # Ø.391 ±.002 about .35 mm long (#2249, option A), 13/64 drilled bore.
    assert round(11.0 / INCH, spec.OD_PLACES) == 0.433
    assert spec.OD == pytest.approx(0.433 * INCH)
    assert spec.THICK == pytest.approx(0.06 * INCH)
    # The spigot on the .001 grid: native limits == printed.
    assert spec.SPIGOT_DIA == pytest.approx(0.391 * INCH)
    assert spec.SPIGOT_DIA_LIMITS == pytest.approx(
        (spec.SPIGOT_DIA - spec.SPIGOT_DIA_TOL, spec.SPIGOT_DIA + spec.SPIGOT_DIA_TOL)
    )
    assert spec.SPIGOT_LENGTH == pytest.approx(0.014 * INCH)
    assert abs(spec.SPIGOT_LENGTH - 0.35) < 0.01
    assert spec.BORE_DRILL == "13/64"
    assert spec.ID == pytest.approx(13.0 / 64.0 * INCH)
    assert spec.HEIGHT == pytest.approx(spec.THICK + spec.SPIGOT_LENGTH)


def test_only_the_spigot_carries_an_explicit_band() -> None:
    # Ø.391 ±.002 on the .001 grid; every other size takes a title-block row.
    assert model_toleranced_dimensions(part) == {
        ("WasherProfile", "SpigotDia"): "SPIGOT_DIA_TOL",
    }
    assert spec.SPIGOT_DIA_PLACES == 3
    assert spec.SPIGOT_DIA_TOL == pytest.approx(0.002 * INCH)
    assert spec.SPIGOT_DIA_LIMITS == pytest.approx((9.8806, 9.9822))
    assert spec.OD_LIMITS == pytest.approx((10.8712, 11.1252))
    assert spec.THICK_LIMITS == pytest.approx((1.270, 1.778))
    assert spec.SPIGOT_LENGTH_LIMITS == pytest.approx((0.2286, 0.4826))
    assert spec.BORE_LIMITS == pytest.approx((5.1562, 5.2578))


def test_spigot_locates_loose_in_mains_strap_hole() -> None:
    # The product interface is main's unchanged Ø.4000 +.0005/0 strap hole.
    assert spec.STRAP_HOLE_LIMITS == pytest.approx(
        (strap.HOLE_DIA + STRAP_HOLE_BAND[1], strap.HOLE_DIA + STRAP_HOLE_BAND[0])
    )
    assert spec.STRAP_HOLE_LIMITS == pytest.approx((10.16, 10.1727))
    assert spec.SPIGOT_FLOAT_MIN > 0.0
    assert spec.SPIGOT_FLOAT_MAX == pytest.approx((10.1727 - 9.8806) / 2.0)
    assert spec.SPIGOT_FLOAT_MAX == pytest.approx(0.14605)
    callout = drawing.DIMENSION_CALLOUTS["SpigotDia"]
    assert spec.STRAP_NUMBER == strap.NUMBER == "MHA-CH-13"
    assert f"STRAP {strap.NUMBER}" in callout
    assert "(.4000-.4005 REF)" in callout


def test_local_edge_limits_keep_a_cylindrical_locating_land() -> None:
    # The title block's default break and inside corner would each consume
    # the shortest .014 spigot, so both are overridden on the sheet.
    assert edge_break_chamfer_mm(unit=spec.UNIT) >= spec.SPIGOT_LENGTH_LIMITS[0]
    assert inside_corner_radius_mm(unit=spec.UNIT) > spec.SPIGOT_LENGTH_LIMITS[1]
    assert spec.FLANGE_EDGE_BREAK_MAX == pytest.approx(0.005 * INCH)
    assert spec.SPIGOT_ROOT_RADIUS_MAX == pytest.approx(0.003 * INCH)
    # The root fillet stays inside the sharp hole edge: the flange seats flat
    # with the largest spigot centred in the smallest hole.
    assert spec.SPIGOT_DIA_LIMITS[1] + 2.0 * spec.SPIGOT_ROOT_RADIUS_MAX < (
        spec.STRAP_HOLE_LIMITS[0]
    )
    assert spec.ROOT_SEAT_CLEARANCE_MIN == pytest.approx(
        (10.16 - 9.9822) / 2.0 - 0.0762
    )
    assert spec.SPIGOT_END_EDGE_BREAK_MAX == 0.0
    # The strap prints both hub-hole edges sharp: no entry break to charge.
    assert "BOTH EDGES SHARP" in strap_notes.HOLE_EDGE_CALLOUT
    assert spec.STRAP_HOLE_ENTRY_BREAK_MAX == 0.0
    assert spec.SPIGOT_LAND_MIN == pytest.approx(
        spec.SPIGOT_LENGTH_LIMITS[0] - spec.SPIGOT_ROOT_RADIUS_MAX
    )
    assert spec.SPIGOT_LAND_MIN > 0.0
    # The owner's .005 flange break: the seat ring left on the strap outside
    # its hub hole, which the title block's .010 would lose.
    assert spec.SEAT_RING_MIN == pytest.approx(
        (10.8712 - 10.1727) / 2.0 - spec.SPIGOT_FLOAT_MAX - 0.127
    )
    assert spec.SEAT_RING_MIN > 0.0
    assert spec.SEAT_RING_MIN - edge_break_chamfer_mm(unit=spec.UNIT) + 0.127 < 0.0
    # So all three limits print, each as its own leader note on the edge or
    # corner it controls, and the size dimensions carry none of them.
    assert drawing.DIMENSION_CALLOUTS["WasherThickness"] == spec.FLANGE_WALL_CALLOUT
    assert "SpigotLength" not in drawing.DIMENSION_CALLOUTS
    notes = {label: text for label, text, _, _ in drawing.DETAIL_NOTES}
    assert notes == {
        "flange rim break": "BREAK EDGES .005 MAX\nBOTH FLANGE RIMS",
        "spigot root corner": "R.003 MAX",
        "spigot end edge": "END EDGE SHARP, NO BURR",
    }


def test_bore_clears_the_8_32_shcs_and_its_fillet() -> None:
    assert drawing.DIMENSION_CALLOUTS["WasherBore"] == "13/64 DRILL THRU"
    assert spec.BORE_LIMITS[0] > SCREW_FILLET_DIA_MAX > HUB_SCREW.major_dia
    assert spec.OD_LIMITS[0] > HUB_SCREW.head_dia
    assert spec.WALL_MIN >= WALL_TARGET_MM
    assert spec.WALL_MIN == pytest.approx(
        (spec.SPIGOT_DIA_LIMITS[0] - spec.BORE_LIMITS[1]) / 2.0
    )


def test_od_keeps_its_xxx_row_and_names_the_cutter_it_clears() -> None:
    # Rule 3: a .XXX clearance names what it clears.  The 1.5 mm floor is the
    # holding proof's and the jig's tooling-clearance check's, not the sheet's.
    assert spec.OD_PLACES == 3
    assert spec.CUTTER_CLEARANCE_MIN == 1.5
    assert drawing.DIMENSION_CALLOUTS["WasherOd"] == f"CLEARS 3/8 CUTTER\nON {spec.JIG_NUMBER}"


def test_every_callout_keeps_to_two_lines_of_words() -> None:
    # Rule 7: anything longer moves to a numbered flag note.
    for name, text in drawing.DIMENSION_CALLOUTS.items():
        assert len(text.splitlines()) <= 2, name


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    views = (drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.DETAIL_KEEP)
    assert set().union(*views) == marked
    assert sum(len(view) for view in views) == len(marked)
    assert set(drawing.FRONT_KEEP) == spec.DRAWING_DIMENSIONS["BoreProfile"]
    assert set(drawing.RIGHT_KEEP) | set(drawing.DETAIL_KEEP) == (
        spec.DRAWING_DIMENSIONS["WasherProfile"]
    )
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "WasherOd": 3,
        "WasherThickness": 2,
        "SpigotDia": 3,
        "SpigotLength": 3,
        "WasherBore": 3,
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION


def test_turned_profile_frame_and_volume() -> None:
    # Right-plane (u, v) = model (-Z, Y): head-side face at u = -THICK, seat
    # face at u = 0, spigot end at u = SPIGOT_LENGTH, closed on the axis.
    assert part.PROFILE_POINTS == [
        (-spec.THICK, 0.0),
        (-spec.THICK, spec.OD / 2.0),
        (0.0, spec.OD / 2.0),
        (0.0, spec.SPIGOT_DIA / 2.0),
        (spec.SPIGOT_LENGTH, spec.SPIGOT_DIA / 2.0),
        (spec.SPIGOT_LENGTH, 0.0),
    ]
    assert part.V_WASHER == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.ID / 2.0) ** 2) * spec.THICK
        + math.pi * ((spec.SPIGOT_DIA / 2.0) ** 2 - (spec.ID / 2.0) ** 2)
        * spec.SPIGOT_LENGTH
    )
    # The mid-plane bore cut passes both the head-side face and the spigot end.
    assert part.BORE_CUT_DEPTH / 2.0 > max(spec.THICK, spec.SPIGOT_LENGTH)


def test_side_view_diameters_sit_clear_of_the_part() -> None:
    s = drawing._S
    assert drawing.HEAD_FACE_X < drawing.SEAT_FACE_X < drawing.SPIGOT_END_X
    assert drawing.SPIGOT_END_X - drawing.HEAD_FACE_X == pytest.approx(spec.HEIGHT * s)
    assert set(drawing.RIGHT_KEEP) == {"WasherOd", "SpigotDia"}
    # Flange Ø left of the head-side face, spigot Ø right of the spigot end.
    assert drawing.HEAD_FACE_X - drawing.RIGHT_KEEP["WasherOd"][0] >= 0.030
    assert drawing.RIGHT_KEEP["SpigotDia"][0] - drawing.SPIGOT_END_X >= 0.030
    # Each Ø's text block centres on the axis, midway between its arrows.
    assert drawing.RIGHT_KEEP["WasherOd"][1] == drawing.RIGHT_CENTER[1]
    assert drawing.RIGHT_KEEP["SpigotDia"][1] == drawing.RIGHT_CENTER[1]


def test_detail_a_carries_both_lengths_on_separate_rows() -> None:
    # Farm r1: at 4:1 the chained .06 and .014 piled their arrowheads on the
    # shared seat-face extension line; detail A reads them at 20:1.
    assert set(drawing.DETAIL_KEEP) == {"WasherThickness", "SpigotLength"}
    assert drawing.DETAIL_SCALE == (20, 1)
    ds = drawing._DS
    assert drawing.DETAIL_SPIGOT_X - drawing.DETAIL_SEAT_X == pytest.approx(
        spec.SPIGOT_LENGTH * ds
    )
    assert drawing.DETAIL_SEAT_X - drawing.DETAIL_HEAD_X == pytest.approx(spec.THICK * ds)
    assert drawing.DETAIL_SPIGOT_X - drawing.DETAIL_SEAT_X > 0.006
    # The fence takes in every length corner and stays above the axis, so
    # neither Ø (measured from the axis) comes into the detail.
    for corner in (drawing._HEAD_CORNER, drawing._SEAT_CORNER, drawing._SPIGOT_CORNER):
        assert math.dist(drawing.DETAIL_FOCUS_MM, corner) < drawing.DETAIL_RADIUS_MM
    assert drawing.DETAIL_FOCUS_MM[1] - drawing.DETAIL_RADIUS_MM > spec.ID / 2.0
    # Two rows, both above the profile, so the arrowheads on the shared
    # extension line stand apart.
    thick_row = drawing.DETAIL_KEEP["WasherThickness"][1]
    spigot_row = drawing.DETAIL_KEEP["SpigotLength"][1]
    assert spigot_row > drawing.DETAIL_OD_TOP_Y
    assert thick_row - spigot_row >= 0.008
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_CROP_RADIUS
    # Repeat review of run 20261108T055431582Z: each dimension line's outside
    # stub ran level into its text.  Each text block now stands above its
    # row, its lowest line clear of the stub's height, and its near edge
    # beyond the stub's end (about 3.3 mm past the extension line).
    thick_x, thick_y = drawing.DETAIL_TEXT_XY["WasherThickness"]
    spigot_x, spigot_y = drawing.DETAIL_TEXT_XY["SpigotLength"]
    assert thick_y - thick_row - (_ROW_PITCH / 2.0 + _GLYPH / 2.0) > 0.002
    assert spigot_y - spigot_row - _GLYPH / 2.0 > 0.002
    wall_half = len(spec.FLANGE_WALL_CALLOUT) * _CHAR / 2.0
    assert thick_x + wall_half < drawing.DETAIL_HEAD_X - 0.0033
    assert spigot_x - len(".014") * _CHAR / 2.0 > drawing.DETAIL_SPIGOT_X + 0.0033
    for name, xy in drawing.DETAIL_TEXT_XY.items():
        assert math.dist(xy, (cx, cy)) > r, name
    # Clear of the bottom border (0.0127), the title block (x 0.216) and the
    # face view (its bottom near y 0.128).
    assert drawing.DETAIL_LABEL_XY[1] - 0.010 > 0.0127
    assert max(thick_y, spigot_y) + 0.010 < drawing.FRONT_CENTER[1] - spec.OD / 2.0 * drawing._S
    # The parent's letter above the flange Ø's upper extension line.
    assert drawing.DETAIL_LETTER_XY[1] > drawing._OD_TOP_Y + 0.005


# Sheet text metrics read off the prescreen and run 20261108T055431582Z
# renders: about 2.45 mm per character, 5.5 mm row pitch, 3.5 mm glyphs.
_CHAR = 0.00245
_ROW_PITCH = 0.0055
_GLYPH = 0.0035


def _crosses(a: tuple, b: tuple, c: tuple, d: tuple) -> bool:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def test_edge_limit_notes_point_at_their_edges_from_clear_air() -> None:
    tips = {label: tip for label, _, _, tip in drawing.DETAIL_NOTES}
    # The arrows land on the profile points where each edge or corner shows.
    assert tips["flange rim break"] == pytest.approx(
        (drawing.DETAIL_HEAD_X, drawing.DETAIL_OD_TOP_Y)
    )
    assert tips["spigot end edge"] == pytest.approx(
        (drawing.DETAIL_SPIGOT_X, drawing.DETAIL_SPIGOT_TOP_Y)
    )
    assert tips["spigot root corner"] == pytest.approx(
        (drawing.DETAIL_SEAT_X, drawing.DETAIL_SPIGOT_TOP_Y)
    )
    assert drawing.DETAIL_SPIGOT_TOP_Y < drawing.DETAIL_OD_TOP_Y
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_CROP_RADIUS
    spigot_row = drawing.DETAIL_KEEP["SpigotLength"][1]
    thick_text_bottom = (
        drawing.DETAIL_TEXT_XY["WasherThickness"][1] - _ROW_PITCH / 2.0 - _GLYPH
    )
    spigot_text_bottom = drawing.DETAIL_TEXT_XY["SpigotLength"][1] - _GLYPH
    leaders = {}
    for label, text, (x, y), tip in drawing.DETAIL_NOTES:
        rows = text.splitlines()
        width = max(len(row) for row in rows) * _CHAR
        bottom = y - len(rows) * _ROW_PITCH
        # Top-left anchored, wholly outside the detail circle and the sheet's
        # border, title block and the dimension texts above.
        for corner in ((x, y), (x + width, y), (x, bottom), (x + width, bottom)):
            assert math.dist(corner, (cx, cy)) > r, label
        assert x > 0.0127 and x + width < 0.216 and bottom > 0.0127, label
        assert y < min(thick_text_bottom, spigot_text_bottom), label
        # The leader leaves the side nearest the tip, mid-height.
        start = (x + width if tip[0] > x + width else x, (y + bottom) / 2.0)
        leaders[label] = (start, tip)
        # Below every dimension line (rule 14: a leader never crosses one).
        assert max(start[1], tip[1]) < spigot_row, label
    labels = sorted(leaders)
    for i, first in enumerate(labels):
        for second in labels[i + 1 :]:
            assert not _crosses(*leaders[first], *leaders[second]), (first, second)


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
