"""Offline contracts for the latch-hook bracket (MHA-PD-021) and its drawing."""

from __future__ import annotations

import ast
import importlib.util
import itertools
import math
import re
from pathlib import Path

import pytest

import _config
import _printed_tolerance
import build_pd_latch_hook_bracket as part
import draw_pd_latch_hook_bracket as drawing
import pd_latch_hook_bracket_geometry as geometry
import vn_latch_hook_bracket_screw_spec as screw
import pd_latch_hook_bracket_spec as spec
import pd_latch_hook_geometry as hook
import pd_latch_hook_spec as hook_spec
import vn_latch_hook_rivet_spec as rivet
import pd_support_bar_spec as bar
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME


def _row_mm(places: int) -> float:
    """The printed general row's ± in mm (the policy's figure; the title
    block's inch row it rounds up must be no looser)."""
    band = _printed_tolerance.printed_band_mm(places)
    assert _config.title_block(f"linear_{places}pl")["value_in"] * 25.4 <= band
    return band


def _machine(y: float, z: float) -> tuple[float, float]:
    """A part-frame (Y, Z) in machine coordinates."""
    return (y + geometry.MACHINE_ORIGIN[1], z + geometry.MACHINE_ORIGIN[2])


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-latch-hook-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-latch-hook-bracket.pdf")
    assert (
        DRAWINGS_BY_NAME["pd_latch_hook_bracket"].script
        == Path(drawing.__file__).resolve()
    )
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert not drawing_specification_violations(source, filename=drawing.__file__)


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    keeps = (drawing.ELEVATION_KEEP, drawing.PLAN_KEEP, drawing.SIDE_KEEP)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*keeps) == marked
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # Each hole size carries its pair count and process, in the view that
    # prints it.
    sizes = {"ScrewDia", "RivetDia"}
    assert set(drawing.CALLOUTS_ABOVE) == set(drawing.CALLOUTS_BELOW) == sizes
    assert "ScrewDia" in drawing.PLAN_KEEP and "RivetDia" in drawing.SIDE_KEEP


def test_rivet_holes_are_sized_only_and_drilled_through_the_hook() -> None:
    """R9-15: match-drilled at assembly through MHA-PD-014, so the sheet prints
    their size and process and no location."""
    assert spec.DRAWING_DIMENSIONS["RivetHoleProfile"] == {"RivetDia"}
    assert "RivetHoleProfile" not in spec.POSITION_DIMENSIONS
    assert drawing.CALLOUTS_BELOW["RivetDia"] == ("DRILL AT ASSEMBLY THROUGH MHA-PD-014")


def test_holes_positions_and_width_carry_their_bands_on_the_model() -> None:
    """Drilled holes never under size; every printed hole position carries
    the ± position band (the build loops over POSITION_DIMENSIONS); the width
    its explicit band.  The outline prints its title-block rows."""
    assert model_toleranced_dimensions(part) == {
        ("ScrewHoleProfile", "ScrewDia"): "*deviations(HOLE_BAND)",
        ("RivetHoleProfile", "RivetDia"): "*deviations(HOLE_BAND)",
        ("Bracket", "Width"): "WIDTH_TOL",
        ("feature_name", "dimension_name"): "POSITION_TOL",
    }
    assert part.POSITION_DIMENSIONS is spec.POSITION_DIMENSIONS
    assert min(spec.HOLE_BAND) == 0.0 < max(spec.HOLE_BAND)
    # Every printed screw-hole dimension but the size is a banded position.
    printed = spec.DRAWING_DIMENSIONS["ScrewHoleProfile"]
    assert set(spec.POSITION_DIMENSIONS) == {"ScrewHoleProfile"}
    assert set(spec.POSITION_DIMENSIONS["ScrewHoleProfile"]) == printed - {"ScrewDia"}


def test_the_screw_holes_ligament_to_the_y_edges_holds_2_at_the_worst_case() -> None:
    """R9-10: the y-edge ligament is 2.366 nominal and 2.00 at the worst case
    (width at its lower limit, the hole at its far position, drilled
    oversize)."""
    high = geometry.WIDTH - geometry.SCREW_HOLE_Y - geometry.SCREW_HOLE_DIA / 2.0
    worst = high - spec.WIDTH_TOL - spec.POSITION_TOL - max(spec.HOLE_BAND) / 2.0
    assert high == pytest.approx(2.366, abs=1e-6)
    assert worst >= spec.WALL_TARGET
    assert spec.WALLS["screw holes to the base's y edges"] == pytest.approx(
        (high, worst), abs=1e-6
    )


def test_every_wall_holds_2_at_the_worst_case() -> None:
    """Policy rule 12 with the sheet's own rows (the base length at .XX, the
    flap height at .X, screw holes at their far position), the rivet holes
    anywhere over the hook's set as sheet 4 prints it (.XX, ±0.51 about the
    rounded value) at the hook's .XXX pitch, every hole drilled oversize."""
    screw_grow = spec.POSITION_TOL + max(spec.HOLE_BAND) / 2.0
    x_edge = (
        geometry.BASE_LENGTH
        + geometry.SCREW_HOLE_X[0]
        - geometry.SCREW_HOLE_DIA / 2.0
        - _row_mm(spec.BASE_LENGTH_PLACES)
        - screw_grow
    )
    rivet_r = (geometry.RIVET_HOLE_DIA + max(spec.HOLE_BAND)) / 2.0
    pitch_band = _row_mm(spec.HOOK_PITCH_PLACES)
    (y_low, y_high), (z_low, z_high) = spec.HOOK_SET_Y_DEV, spec.HOOK_SET_Z_DEV
    ((rivet_y, low_z), (_, top_z)) = geometry.RIVET_YZ
    top_edge = (
        geometry.FLAP_HEIGHT
        - _row_mm(spec.FLAP_HEIGHT_PLACES)
        - (top_z + z_high + pitch_band + rivet_r)
    )
    bend = (low_z + z_low - pitch_band - rivet_r) - (
        geometry.SHEET_T + geometry.SHEET_T_PLUS + geometry.INSIDE_BEND_R_MAX
    )
    y_edges = (
        min(
            rivet_y + y_low,
            geometry.WIDTH - spec.WIDTH_TOL - rivet_y - y_high,
        )
        - rivet_r
    )
    web = hook.RIVET_PITCH - pitch_band - 2.0 * rivet_r
    expected = {
        "screw hole to the base's -X edge": x_edge,
        "upper rivet hole to the flap's top edge": top_edge,
        "lower rivet hole to the inside bend fillet": bend,
        "rivet holes to the flap's y edges": y_edges,
        "web between the rivet holes": web,
    }
    for name, worst in expected.items():
        assert worst >= spec.WALL_TARGET, name
        # The sheet rounds each printed value to its places (≤ 0.0005).
        assert spec.WALLS[name][1] == pytest.approx(worst, abs=1e-3), name
    assert min(worst for _, worst in spec.WALLS.values()) >= spec.WALL_TARGET


def _flap_top_wall(flap_height: float, hole_dia: float) -> float:
    """The upper rivet hole to the flap's top edge at the printed worst case:
    the flap at the bottom of its .X row, the hook set its full printed range
    up, the pitch at the top of its .XXX row, the hole drilled at the top of
    its +0.10/0 band."""
    top_z = geometry.RIVET_YZ[1][1]
    return (
        flap_height
        - _row_mm(spec.FLAP_HEIGHT_PLACES)
        - (
            top_z
            + spec.HOOK_SET_Z_DEV[1]
            + _row_mm(spec.HOOK_PITCH_PLACES)
            + (hole_dia + max(spec.HOLE_BAND)) / 2.0
        )
    )


def test_the_flap_top_holds_2_over_the_wider_rivet_holes(monkeypatch) -> None:
    """R9-51: the Ø1.65 holes (the largest 1/16 shank's clearance) cost the
    flap top 0.025; one .X step on the flap height (19.5 -> 19.6) restores the
    2.0 wall at the worst case: 19.6 - 0.8 - (15.204 + 0.506 + 0.13 + 0.875),
    the set's 0.506 being 11.30 + 0.51 over the front hole's 11.3045."""
    wall = _flap_top_wall(geometry.FLAP_HEIGHT, geometry.RIVET_HOLE_DIA)
    assert wall >= spec.WALL_TARGET
    assert wall == pytest.approx(2.0850, abs=1e-4)
    assert spec.WALLS["upper rivet hole to the flap's top edge"][1] == pytest.approx(
        wall, abs=1e-3
    )
    # Negative control: the Ø1.65 holes in the 19.5 flap leave 1.98, and the
    # gate refuses it.
    assert _flap_top_wall(19.5, geometry.RIVET_HOLE_DIA) < spec.WALL_TARGET
    monkeypatch.setattr(geometry, "FLAP_HEIGHT", 19.5)
    with pytest.raises(AssertionError, match="flap's top edge wall 1.98"):
        _spec_fresh()


def _worst_rivet_walls(
    set_y: tuple[float, float], set_z: tuple[float, float]
) -> dict[str, float]:
    """Every flap wall around the match-drilled rivet holes, least over the
    corners: the hook set anywhere within its (lower, upper) deviations
    ``set_y`` and ``set_z``, either rivet hole the one the hook's printed
    pitch is taken from, the pitch at either end of its .XXX row, holes
    nominal, drilled oversize or at the rivet vendor's #51 drill, the width,
    the flap height, the sheet and the bend radius at either limit."""
    ((rivet_y, low_z), (_, top_z)) = geometry.RIVET_YZ
    pitch_band = _row_mm(spec.HOOK_PITCH_PLACES)
    flap_band = _row_mm(spec.FLAP_HEIGHT_PLACES)
    worst: dict[str, float] = {}
    corners = itertools.product(
        set_y,
        set_z,
        (False, True),
        (-pitch_band, pitch_band),
        (
            min(spec.HOLE_BAND),
            max(spec.HOLE_BAND),
            rivet.VENDOR_HOLE_DIA - geometry.RIVET_HOLE_DIA,
        ),
        (-spec.WIDTH_TOL, spec.WIDTH_TOL),
        (-flap_band, flap_band),
        (-geometry.SHEET_T_MINUS, geometry.SHEET_T_PLUS),
        (geometry.INSIDE_BEND_R, geometry.INSIDE_BEND_R_MAX),
    )
    for set_y, set_z, upper_datum, pitch, grow, width, flap, sheet, bend_r in corners:
        r = (geometry.RIVET_HOLE_DIA + grow) / 2.0
        # The pitch error lands wholly on the hole not taken as the datum.
        low = low_z + set_z - (pitch if upper_datum else 0.0)
        top = top_z + set_z + (0.0 if upper_datum else pitch)
        y = rivet_y + set_y
        walls = {
            "upper rivet hole to the flap's top edge": geometry.FLAP_HEIGHT
            + flap
            - (top + r),
            "lower rivet hole to the inside bend fillet": (low - r)
            - (geometry.SHEET_T + sheet + bend_r),
            "rivet holes to the flap's y edges": min(
                y - r, geometry.WIDTH + width - y - r
            ),
            "web between the rivet holes": (top - low) - 2.0 * r,
        }
        for name, wall in walls.items():
            worst[name] = min(worst.get(name, wall), wall)
    return worst


def test_the_flap_walls_hold_2_over_the_hook_set_range_at_every_corner() -> None:
    """R9-26: the set takes up the hook's .XX pin-run band, and every flap
    wall around the match-drilled rivet holes holds 2.0 over it, read as
    sheet 4 prints it: 3.80 and 11.30, ±0.51."""
    assert spec.HOOK_SET_RANGE >= _row_mm(hook_spec.PIN_RUN_PLACES)
    worst = _worst_rivet_walls(spec.HOOK_SET_Y_DEV, spec.HOOK_SET_Z_DEV)
    assert min(worst.values()) >= spec.WALL_TARGET
    for name, wall in worst.items():
        # The spec's stack, judged at the printed hole band, is looser than
        # the corners by no more than the #51 drill's recorded excess over it.
        over = max(rivet.VENDOR_HOLE_OVER_BAND, 0.0)
        assert spec.WALLS[name][1] <= wall + over + 1e-6, name
    # Negative control: a set 0.01 wider each way than the thinnest margin of
    # the walls the set moves (the web between the holes moves with neither)
    # breaks 2.0.
    moved = {n: w for n, w in worst.items() if n != "web between the rivet holes"}
    extra = min(moved.values()) - spec.WALL_TARGET + 0.01
    wider = [
        (low - extra, high + extra)
        for low, high in (spec.HOOK_SET_Y_DEV, spec.HOOK_SET_Z_DEV)
    ]
    assert min(_worst_rivet_walls(*wider).values()) < spec.WALL_TARGET


def _spec_fresh():
    fresh_spec = importlib.util.spec_from_file_location(
        "_bracket_perturbed", spec.__file__
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_a_coarser_outline_row(monkeypatch) -> None:
    # Positive control: the title block as it is.
    assert _spec_fresh().WALLS == spec.WALLS
    # Negative control: a base-length row loose enough to thin the screw
    # hole's -X edge wall under 2.0.
    monkeypatch.setattr(_printed_tolerance, "printed_band_mm", lambda _places: 1.0)
    with pytest.raises(AssertionError, match="target"):
        _spec_fresh()


def test_the_screw_head_clears_the_bend_fillet_at_the_worst_case() -> None:
    """R9-10: ≥ 0.2 between the flap-side screw's head and the inside bend
    fillet, at the printed maximum bend radius, the thickest stock sheet, the
    hole at its position limit toward the flap, and the screw floating in the
    largest drilled hole over the smallest #4-40 2A major."""
    fillet_start = -(
        geometry.SHEET_T + geometry.SHEET_T_PLUS + geometry.INSIDE_BEND_R_MAX
    )
    head_rim = (
        geometry.SCREW_HOLE_X[1]
        + spec.POSITION_TOL
        + (geometry.SCREW_HOLE_DIA + max(spec.HOLE_BAND) - screw.MAJOR_DIA_MIN) / 2.0
        + screw.HEAD_DIA / 2.0
    )
    worst = fillet_start - head_rim
    assert worst >= spec.HEAD_CLEARANCE_FLOOR
    assert spec.HEAD_CLEARANCE_WORST == pytest.approx(worst, abs=1e-6)
    # The modelled bend is inside the printed limit the clearance was judged at.
    assert geometry.INSIDE_BEND_R <= geometry.INSIDE_BEND_R_MAX
    assert geometry.OUTSIDE_BEND_R == pytest.approx(
        geometry.INSIDE_BEND_R + geometry.SHEET_T
    )


def test_the_printed_bend_limit_is_the_one_the_clearance_was_judged_at() -> None:
    limits = re.findall(r"INSIDE BEND R(\d+(?:\.\d+)?) MAX", spec.DRAWING_NOTES)
    assert [float(value) for value in limits] == [geometry.INSIDE_BEND_R_MAX]
    assert "AFTER BENDING" in spec.DRAWING_NOTES


def test_screw_holes_sit_over_the_bar_taps() -> None:
    bar_y = geometry.BAR_CENTRE_Y + bar.HANGER_TAP_Y
    for x, tap_x in zip(geometry.SCREW_HOLE_X, bar.BRACKET_TAP_X, strict=True):
        assert x + geometry.MACHINE_ORIGIN[0] == pytest.approx(tap_x)
    assert geometry.SCREW_HOLE_Y + geometry.MACHINE_ORIGIN[1] == pytest.approx(bar_y)


def test_rivet_holes_are_the_hooks() -> None:
    flap = [c for yz in sorted(_machine(*yz) for yz in geometry.RIVET_YZ) for c in yz]
    strip = [c for yz in sorted(hook.RIVET_YZ) for c in yz]
    assert flap == pytest.approx(strip, abs=1e-5)


def test_the_bracket_screws_grip_the_bracket_sheet() -> None:
    """The screw's engagement and tip stacks read the bracket's sheet."""
    assert (screw.SHEET_T, screw.SHEET_T_PLUS, screw.SHEET_T_MINUS) == (
        geometry.SHEET_T,
        geometry.SHEET_T_PLUS,
        geometry.SHEET_T_MINUS,
    )


def test_registry_row_is_the_steel_sheet_mha_170() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-021"
    assert int(row["quantity"]) == 1
    assert "sheet" in row["material_specification"].lower()
    # Review of 19e33c6c2: the stock is the title block's MATERIAL cell (30
    # characters), so no note restates it.
    assert row["material"] == spec.MATERIAL_TITLE
    assert len(spec.MATERIAL_TITLE) <= 30
    assert f"{geometry.SHEET_T:.1f}" in row["material"]
    assert "16 GA" in row["material"] and "16 GA" in row["material_specification"]


def test_the_notes_leave_the_stock_and_edge_break_to_the_title_block() -> None:
    """Review of 19e33c6c2: MAKE FROM ... SHEET restated the material and
    BREAK SHARP EDGES; DEBURR HOLES the title block's general note."""
    lines = spec.DRAWING_NOTES.split("\n")
    assert len(lines) <= 4
    assert [line for line in lines if len(line) > 70] == []
    for restated in ("SHEET", "STEEL", "BREAK SHARP", "DEBURR", "BURRS"):
        assert restated not in spec.DRAWING_NOTES, restated


def test_the_explicit_bands_are_the_ones_the_walls_need() -> None:
    """Review of 19e33c6c2 asked for the title block's rows on the hole
    positions (.XXX) and the base length (.X).  Either breaks a target: the
    y-edge ligament and the screw head's bend clearance at ±0.13, the screw
    hole's -X edge wall at the base length's ±0.8."""
    grow = max(spec.HOLE_BAND) / 2.0
    ligament = geometry.WIDTH - geometry.SCREW_HOLE_Y - geometry.SCREW_HOLE_DIA / 2.0
    loose = _row_mm(spec.POSITION_PLACES)
    assert spec.POSITION_TOL < loose
    assert ligament - spec.WIDTH_TOL - spec.POSITION_TOL - grow >= spec.WALL_TARGET
    assert ligament - spec.WIDTH_TOL - loose - grow < spec.WALL_TARGET
    head_loss = loose - spec.POSITION_TOL
    assert spec.HEAD_CLEARANCE_WORST - head_loss < spec.HEAD_CLEARANCE_FLOOR
    # The base length: .XX holds, .X does not.
    x_edge = (
        geometry.BASE_LENGTH + geometry.SCREW_HOLE_X[0] - geometry.SCREW_HOLE_DIA / 2.0
    )
    for places, holds in ((spec.BASE_LENGTH_PLACES, True), (1, False)):
        wall = x_edge - _row_mm(places) - spec.POSITION_TOL - grow
        assert (wall >= spec.WALL_TARGET) is holds, places


# Sheet text at 3.5 (dimensions) and the notes' default height; notes are
# anchored top-left.
_CHAR_WIDTH = 0.00276
_LINE_PITCH = 0.0045
_BORDER = 0.0127


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _crosses(p, q, r, s) -> bool:
    """Whether segments pq and rs properly intersect."""

    def side(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return side(p, q, r) * side(p, q, s) < 0 and side(r, s, p) * side(r, s, q) < 0


def _rect(p, q) -> tuple[float, float, float, float]:
    return (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))


def _views() -> dict[str, tuple[float, float, float, float]]:
    """The orthographic views' outlines and the isometric's bounding disc's
    square (any projection of the part's box lies within half its diagonal
    of the view centre), in sheet metres."""
    iso_r = (
        math.dist(
            (0.0, 0.0, 0.0),
            (geometry.BASE_LENGTH, geometry.WIDTH, geometry.FLAP_HEIGHT),
        )
        / 2.0
        * drawing.ISO_SCALE[0]
        / drawing.ISO_SCALE[1]
        / 1000.0
    )
    ix, iy = drawing.ISO_CENTER
    return {
        "elevation": _rect(
            drawing._elevation(-geometry.BASE_LENGTH, 0.0),
            drawing._elevation(0.0, geometry.FLAP_HEIGHT),
        ),
        "plan": _rect(
            drawing._plan(-geometry.BASE_LENGTH, 0.0),
            drawing._plan(0.0, geometry.WIDTH),
        ),
        "side": _rect(
            drawing._side(0.0, 0.0), drawing._side(geometry.WIDTH, geometry.FLAP_HEIGHT)
        ),
        "iso": (ix - iso_r, iy - iso_r, ix + iso_r, iy + iso_r),
    }


def _rivet_callout_box() -> tuple[float, float, float, float]:
    x, y = drawing.SIDE_KEEP["RivetDia"]
    lines = [spec.PAIR_CALLOUT, "\u00d81.65 +0.10", "0.00", spec.RIVET_HOLE_CALLOUT]
    half_width = max(map(len, lines)) * _CHAR_WIDTH / 2.0
    # The pair count stacks above the size, the process below it.
    return (
        x - half_width,
        y - 2.5 * _LINE_PITCH,
        x + half_width,
        y + 1.5 * _LINE_PITCH,
    )


def test_every_view_and_caption_stands_inside_the_border_off_the_title_block() -> None:
    """Review of 19e33c6c2: the side view ran into the title block and the
    isometric caption touched the right border."""
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    title_block = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    caption = spec.ISOMETRIC_VIEW_NOTE
    cx, cy = drawing.ISO_NOTE_XY
    caption_box = (cx, cy - _LINE_PITCH, cx + len(caption) * _CHAR_WIDTH, cy)
    views = _views()
    boxes = {**views, "caption": caption_box, "RivetDia": _rivet_callout_box()}
    for name, box in boxes.items():
        assert box[0] > _BORDER + 0.003 and box[1] > _BORDER + 0.003, name
        assert box[2] < template.width_m - _BORDER - 0.003, name
        assert box[3] < template.height_m - _BORDER - 0.003, name
        assert not _overlap(box, title_block), name
    for (a, box_a), (b, box_b) in itertools.combinations(boxes.items(), 2):
        assert not _overlap(box_a, box_b), (a, b)
    # The caption is centred under the isometric view.
    assert abs(cx + len(caption) * _CHAR_WIDTH / 2.0 - drawing.ISO_CENTER[0]) < 0.01
    assert cy < views["iso"][1]


def test_the_rivet_callout_stands_off_the_side_view_and_its_leader_is_clear() -> None:
    """Review of 19e33c6c2: DRILL AT ASSEMBLY THROUGH MHA-PD-014 sat on the
    side view's top edge.  The callout stands right of the flap; its leader
    meets the lower hole without crossing the view's top edge or either
    hole's horizontal centre line."""
    side = _views()["side"]
    box = _rivet_callout_box()
    assert box[0] > side[2] + 0.003
    text = drawing.SIDE_KEEP["RivetDia"]
    centres = [drawing._side(y, z) for y, z in geometry.RIVET_YZ]
    lower = min(centres, key=lambda c: c[1])
    r = geometry.RIVET_HOLE_DIA / 2.0 * drawing._S
    d = math.dist(lower, text)
    rim = (
        lower[0] + (text[0] - lower[0]) * r / d,
        lower[1] + (text[1] - lower[1]) * r / d,
    )
    top_edge = ((side[0], side[3]), (side[2], side[3]))
    assert not _crosses(text, rim, *top_edge)
    for cx, cy in centres:
        centre_line = ((side[0] - 0.003, cy), (side[2] + 0.003, cy))
        assert not _crosses(text, rim, *centre_line)


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
    assert [ast.unparse(a) for a in stamp.args] == [
        "adapter",
        "PART_NAME",
        "DRAWING_PROPERTIES",
    ]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None, part.PART_NAME, part.DRAWING_PROPERTIES
    )
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
