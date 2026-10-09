"""Offline contracts for the one-piece latch hook (MHA-PD-014) and its drawing."""

from __future__ import annotations

import ast
import itertools
import math
from pathlib import Path

import pytest

import _config
import build_pd_latch_hook as part
import draw_pd_latch_hook as drawing
import pd_latch_hook_geometry as geom
import pd_latch_hook_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-latch-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-latch-hook.pdf")
    assert DRAWINGS_BY_NAME["pd_latch_hook"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_placement_and_model_places() -> None:
    keeps = (drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.BOTTOM_KEEP)
    for a, b in itertools.combinations(keeps, 2):
        assert not set(a) & set(b)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*keeps) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    callouts = {*drawing.CALLOUTS_ABOVE, *drawing.CALLOUTS_BELOW}
    assert callouts | set(drawing.SHORTENED_RADII) <= marked
    # The flat pattern prints from the hidden reference sketch, side view only.
    flat = spec.DRAWING_DIMENSIONS[spec.FLAT_SKETCH]
    assert flat <= set(drawing.RIGHT_KEEP)
    assert spec.REFERENCE_SKETCHES == (spec.FLAT_SKETCH,)


def test_the_model_owns_every_band_the_sheet_prints() -> None:
    """Drilled holes never under size; the inside bend up to the largest the
    screw head clears; the screw positions, the width and the base length
    their own ± bands; every formed arm feature the formed band (the far
    face its per-axis share).  Everything else takes its title-block row."""
    assert model_toleranced_dimensions(part) == {
        ("ScrewHoleProfile", "ScrewDia"): "*deviations(HOLE_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(HOLE_BAND)",
        ("InsideBend", "InsideBendR"): "*deviations(BEND_R_BAND)",
        ("BaseEar", "Width"): "WIDTH_TOL",
        ("BaseEarProfile", "BaseLength"): "BASE_LENGTH_TOL",
        # The position, formed and face loops (read below).
        ("feature_name", "dimension_name"): "band",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "for feature_name, dimension_names in POSITION_DIMENSIONS.items()" in source
    assert "((FORMED_DIMENSIONS, FORMED_BAND), (FACE_DIMENSIONS, FACE_BAND))" in source
    assert min(spec.HOLE_BAND) == 0.0 < max(spec.HOLE_BAND)
    assert spec.BEND_R_BAND[0] == pytest.approx(
        geom.INSIDE_BEND_R_MAX - geom.INSIDE_BEND_R
    )
    for groups in (spec.FORMED_DIMENSIONS, spec.FACE_DIMENSIONS):
        for feature, names in groups.items():
            assert names <= spec.DRAWING_DIMENSIONS[feature]
    for feature, names in spec.POSITION_DIMENSIONS.items():
        assert set(names) <= spec.DRAWING_DIMENSIONS[feature]
    # The far face's X and Y bands move it at most the formed band along U.
    assert spec.FAR_FACE_U_BAND <= spec.FORMED_BAND


def test_walls_hold_the_target_at_the_worst_case_the_sheet_prints() -> None:
    assert spec.WALLS
    for name, (nominal, worst) in spec.WALLS.items():
        assert nominal >= worst >= spec.WALL_TARGET - 1e-9, name
    assert spec.WALL_TARGET > spec.WALL_FLOOR


def test_the_screw_head_clears_the_inside_bend_at_the_worst_case() -> None:
    assert spec.HEAD_CLEARANCE_NOMINAL > spec.HEAD_CLEARANCE_WORST
    assert spec.HEAD_CLEARANCE_WORST >= spec.HEAD_CLEARANCE_FLOOR
    assert spec.HEAD_FLOAT_MAX > 0.0
    # More bend radius or more float only eats the clearance.
    base = spec.head_clearance(geom.INSIDE_BEND_R, geom.SHEET_T, 0.0, 0.0)
    assert spec.head_clearance(geom.INSIDE_BEND_R_MAX, geom.SHEET_T, 0.0, 0.0) < base
    assert spec.head_clearance(geom.INSIDE_BEND_R, geom.SHEET_T, 0.0, 0.1) < base


def test_the_build_constants_sit_on_the_published_geometry() -> None:
    # The far face at the pin lies on the straight's +U (outer) edge.
    face = part.FAR_FACE_POINT
    edge = (
        geom.OUTER_TAB_START[0] - geom.OUTER_ROLL_END[0],
        geom.OUTER_TAB_START[1] - geom.OUTER_ROLL_END[1],
    )
    run = (face[0] - geom.OUTER_ROLL_END[0], face[1] - geom.OUTER_ROLL_END[1])
    assert abs(edge[0] * run[1] - edge[1] * run[0]) / math.hypot(*edge) < 1e-6
    assert 0.0 < math.hypot(*run) < math.hypot(*edge)
    assert part.ARM_FRONT_Z == pytest.approx(geom.z_local(geom.Z_FRONT))
    # The flat pattern's columns: the blank across the bend, the arm's lip.
    flat = part._FLAT
    assert flat["top_end"][0] - flat["top_rear"][0] == pytest.approx(geom.FLAT_LENGTH)
    assert flat["taper_end"][0] - flat["taper_start"][0] == pytest.approx(geom.LIP_W)
    assert -flat["taper_start"][1] == pytest.approx(geom.DEV_TAPER[0])
    assert -flat["taper_end"][1] == pytest.approx(geom.DEV_TAPER[1])
    assert flat["top_rear"][0] == drawing.FLAT_GAP == part.FLAT_GAP


def test_registry_row_is_the_formed_spring_steel_hook() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-014"
    assert int(row["quantity"]) == 1
    assert "1095" in row["material_specification"]
    assert "annealed" in row["material_specification"]
    assert "temper" in row["finish"]
    # The stock is the title block's MATERIAL cell, so no note restates it;
    # the cell holds 30 characters.
    assert row["material"] == spec.MATERIAL_TITLE
    assert len(spec.MATERIAL_TITLE) <= 30


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
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


_TITLE_BLOCK_TEXT = ("BREAK SHARP EDGES", "DEBURR", "REMOVE BURRS", "1095", "HRC")


def test_the_notes_fit_the_note_field_and_leave_the_title_block_its_own() -> None:
    """At most 4 lines of at most 70; no dimension, and nothing the MATERIAL
    or FINISH cells already print."""
    lines = spec.DRAWING_NOTES.split("\n")
    assert len(lines) <= 4
    assert [line for line in lines if len(line) > 70] == []
    assert [t for t in _TITLE_BLOCK_TEXT if t in spec.DRAWING_NOTES] == []
    assert not any(
        ch.isdigit() for line in lines for ch in line[2:].replace("MHA-PD-007", "")
    )
    # The pin hole's callout points at the match-drill note.
    assert "MATCH-DRILL" in spec.DRAWING_NOTES
    assert "NOTE 3" in spec.PIN_HOLE_CALLOUT and lines[2].startswith("3.")


# --- Sheet layout ----------------------------------------------------------------
# Sheet text: 3.5 dimension characters, the notes' 3.0 (top-left anchored).
_CHAR_WIDTH = 0.00276
_LINE_PITCH = 0.0045
_NOTE_CHAR_WIDTH = 0.0024
_NOTE_LINE_PITCH = 0.0042
_BORDER = 0.0127


def _box(
    width_chars: int, xy: tuple[float, float], above: int = 0, below: int = 0
) -> tuple[float, ...]:
    """A dimension text centred on ``xy`` with callout lines over/under it."""
    half_width = width_chars * _CHAR_WIDTH / 2.0
    return (
        xy[0] - half_width,
        xy[1] - _LINE_PITCH / 2.0 - below * _LINE_PITCH,
        xy[0] + half_width,
        xy[1] + _LINE_PITCH / 2.0 + above * _LINE_PITCH,
    )


def _note_box(text: str, xy: tuple[float, float]) -> tuple[float, ...]:
    lines = text.split("\n")
    return (
        xy[0],
        xy[1] - len(lines) * _NOTE_LINE_PITCH,
        xy[0] + max(map(len, lines)) * _NOTE_CHAR_WIDTH,
        xy[1],
    )


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside(point: tuple[float, float], box: tuple[float, ...]) -> bool:
    return box[0] < point[0] < box[2] and box[1] < point[1] < box[3]


def _crosses(p, q, r, s) -> bool:
    """Whether segments pq and rs properly intersect."""

    def side(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return side(p, q, r) * side(p, q, s) < 0 and side(r, s, p) * side(r, s, q) < 0


def _box_edges(box):
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return list(zip(corners, corners[1:] + corners[:1]))


def _texts() -> dict[str, tuple[float, ...]]:
    """Every dimension's text box: the value with its band, and callouts."""
    above = {
        name: len(text.split("\n")) for name, text in drawing.CALLOUTS_ABOVE.items()
    }
    below = {
        name: len(text.split("\n")) for name, text in drawing.CALLOUTS_BELOW.items()
    }
    # Printed widths in characters: value and band ("12.631 ±0.065",
    # "Ø3.20 +0.10" over "0.00", "R1.2 +0.3" over "-0.2", "16.0").
    widths = {
        "ScrewX1": 13, "ScrewX2": 12, "ScrewY": 12, "ScrewDia": 11,
        "RollStart": 9, "FaceY": 10, "FaceX": 10, "TabEndX": 9,
        "StraightLen": 9, "PinHoleDia": 11, "RollR": 10, "TabR": 9,
        "Width": 10, "ArmFrontZ": 3, "ArmLowZ": 3, "RootR": 4, "RoundR": 5,
        "FlatLength": 4, "DevTaper1": 4, "DevTaper2": 4, "DevRoundC": 4,
        "BaseLength": 11, "EarHeight": 4, "InsideBendR": 9,
    }  # fmt: skip
    keep = {**drawing.FRONT_KEEP, **drawing.RIGHT_KEEP, **drawing.BOTTOM_KEEP}
    assert set(widths) == set(keep)
    boxes = {}
    for name, xy in keep.items():
        callouts = [
            *drawing.CALLOUTS_ABOVE.get(name, "").split("\n"),
            *drawing.CALLOUTS_BELOW.get(name, "").split("\n"),
        ]
        chars = max(widths[name], *map(len, callouts))
        boxes[name] = _box(chars, xy, above.get(name, 0), below.get(name, 0))
    return boxes


def _arm_centreline(step: float = 0.5) -> list[tuple[float, float]]:
    """The arm's mid-plane in the front view's local (X, Y): the vertical,
    the roll, the straight and the tab."""
    top = geom.to_local(*geom.ROLL_START)[1]
    count = math.ceil((geom.WIDTH - top) / step)
    points = [
        (-geom.HALF_T, geom.WIDTH - (geom.WIDTH - top) * i / count)
        for i in range(count)
    ]
    centre = geom.ROLL_C_L
    turn = math.radians(geom.ROLL_TURN_DEG)
    count = math.ceil(geom.ROLL_R * turn / step)
    points.extend(
        (
            centre[0] + geom.ROLL_R * math.cos(-turn * i / count),
            centre[1] + geom.ROLL_R * math.sin(-turn * i / count),
        )
        for i in range(count + 1)
    )
    roll_end = geom.to_local(*geom.ROLL_END)
    tab_start = geom.to_local(*geom.TAB_START)
    count = math.ceil(math.dist(roll_end, tab_start) / step)
    points.extend(
        (
            roll_end[0] + (tab_start[0] - roll_end[0]) * i / count,
            roll_end[1] + (tab_start[1] - roll_end[1]) * i / count,
        )
        for i in range(1, count + 1)
    )
    tab_c = geom.TAB_C_L
    tab_end = geom.to_local(*geom.TAB_END)
    a0 = math.atan2(tab_start[1] - tab_c[1], tab_start[0] - tab_c[0])
    a1 = math.atan2(tab_end[1] - tab_c[1], tab_end[0] - tab_c[0])
    a1 += 2.0 * math.pi * round((a0 - a1) / (2.0 * math.pi))  # the short way
    count = math.ceil(geom.TAB_R * abs(a1 - a0) / step)
    points.extend(
        (
            tab_c[0] + geom.TAB_R * math.cos(a0 + (a1 - a0) * i / count),
            tab_c[1] + geom.TAB_R * math.sin(a0 + (a1 - a0) * i / count),
        )
        for i in range(1, count + 1)
    )
    return points


def test_the_sampled_centreline_follows_the_published_chain() -> None:
    points = _arm_centreline()
    assert geom.to_local(*geom.ROLL_START) in [pytest.approx(p) for p in points]
    assert points[-1] == pytest.approx(geom.to_local(*geom.TAB_END))
    assert max(math.dist(a, b) for a, b in itertools.pairwise(points)) < 0.6
    hole = geom.PIN_HOLE_L
    assert min(math.dist(p, hole) for p in points) < 0.3
    # The tab arc turns the short way, through the published angle.
    tab_c = geom.TAB_C_L
    start, end = geom.to_local(*geom.TAB_START), points[-1]
    turn = math.degrees(
        math.acos(
            (
                (start[0] - tab_c[0]) * (end[0] - tab_c[0])
                + (start[1] - tab_c[1]) * (end[1] - tab_c[1])
            )
            / geom.TAB_R**2
        )
    )
    assert turn == pytest.approx(geom.TAB_TURN_DEG, abs=1e-6)
    tab = points[points.index(pytest.approx(start)) :]
    length = sum(math.dist(a, b) for a, b in itertools.pairwise(tab))
    assert length == pytest.approx(
        geom.TAB_R * math.radians(geom.TAB_TURN_DEG), rel=1e-3
    )


def _part_regions() -> list[tuple[float, ...]]:
    """Sheet boxes of the drawn part: the front view's base and every 0.8
    strip sample (with the strip's half thickness), the side view's band
    sections and the flat pattern, and the bottom view's bounding box."""
    pad = (geom.HALF_T + 0.5) * drawing._S
    regions = []
    lo, hi = drawing._front(-geom.BASE_LENGTH, 0.0), drawing._front(0.0, geom.WIDTH)
    regions.append((lo[0], lo[1], hi[0], hi[1]))
    for x, y in _arm_centreline():
        sx, sy = drawing._front(x, y)
        regions.append((sx - pad, sy - pad, sx + pad, sy + pad))
    a, b = drawing._right(geom.EAR_HEIGHT, 0.0), drawing._right(0.0, geom.WIDTH)
    regions.append((a[0], a[1], b[0], b[1]))
    for y0, y1, z0, z1 in geom.arm_sections(step=1.0):
        a = drawing._right(geom.z_local(z1), y0 - geom.BASE_Y[0])
        b = drawing._right(geom.z_local(z0), y1 - geom.BASE_Y[0])
        regions.append((a[0], a[1], b[0], b[1] + 1e-6))
    flat = part._FLAT
    a = drawing._flat(flat["top_rear"][0], flat["round_front"][1] - geom.ROUND_R)
    b = drawing._flat(flat["top_end"][0], flat["top_rear"][1])
    regions.append((a[0], a[1], b[0], b[1]))
    xs = [x - geom.PART_ORIGIN_MACHINE[0] for x in geom.BBOX_X]
    zs = [z - geom.PART_ORIGIN_MACHINE[2] for z in geom.BBOX_Z]
    a, b = drawing._bottom(xs[0], zs[0]), drawing._bottom(xs[1], zs[1])
    regions.append((a[0], a[1], b[0], b[1]))
    return regions


def _iso_box() -> tuple[float, ...]:
    """The isometric view's sheet box: the part's bounding-box corners on
    the standard isometric's screen axes, plus line weight."""
    scale = drawing.ISO_SCALE[0] / drawing.ISO_SCALE[1] / 1000.0
    corners = list(itertools.product(geom.BBOX_X, geom.BBOX_Y, geom.BBOX_Z))
    points = [
        ((x - z) / math.sqrt(2.0), (-x + 2.0 * y - z) / math.sqrt(6.0))
        for x, y, z in corners
    ]
    half = (
        (max(p[0] for p in points) - min(p[0] for p in points)) * scale / 2.0 + 0.002,
        (max(p[1] for p in points) - min(p[1] for p in points)) * scale / 2.0 + 0.002,
    )
    cx, cy = drawing.ISO_CENTER
    return (cx - half[0], cy - half[1], cx + half[0], cy + half[1])


def _notes() -> dict[str, tuple[float, ...]]:
    return {
        "notes": _note_box(spec.DRAWING_NOTES, drawing.NOTES_XY),
        "iso note": _note_box(spec.ISOMETRIC_VIEW_NOTE, drawing.ISO_NOTE_XY),
        "bottom note": _note_box(spec.BOTTOM_VIEW_NOTE, drawing.BOTTOM_NOTE_XY),
    }


def test_every_text_stands_inside_the_border_off_the_title_block() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    title_block = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    boxes = {**_texts(), **_notes(), "iso": _iso_box()}
    for name, box in boxes.items():
        assert box[0] > _BORDER + 0.002 and box[1] > _BORDER + 0.002, name
        assert box[2] < template.width_m - _BORDER - 0.002, name
        assert box[3] < template.height_m - _BORDER - 0.002, name
        assert not _overlap(box, title_block), name
    for (a, box_a), (b, box_b) in itertools.combinations(boxes.items(), 2):
        assert not _overlap(box_a, box_b), (a, b)
    for region in _part_regions():
        assert not _overlap(region, title_block)
        for name, box in boxes.items():
            if name != "iso":
                assert not _overlap(region, box), name


def _front_lines() -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """The front view's dimension and extension lines that run past other
    texts: the straight's (offset to its -U side), the far face's and the
    tab end's (dropped from the origin and the feature)."""
    keep = drawing.FRONT_KEEP
    lines = {}
    straight = keep["StraightLen"]
    offset = (
        (straight[0] - drawing._front(*geom.OUTER_ROLL_END)[0]) * geom.ARM_U[0]
        + (straight[1] - drawing._front(*geom.OUTER_ROLL_END)[1]) * geom.ARM_U[1]
    ) / drawing._S
    for end, label in (
        (geom.OUTER_ROLL_END, "roll end"),
        (geom.OUTER_TAB_START, "tab start"),
    ):
        moved = drawing._on(end, offset)
        lines[f"StraightLen ext {label}"] = (
            drawing._front(*end),
            drawing._front(*moved),
        )
    lines["StraightLen"] = (
        drawing._front(*drawing._on(geom.OUTER_ROLL_END, offset)),
        drawing._front(*drawing._on(geom.OUTER_TAB_START, offset)),
    )
    for name, feature in (
        ("FaceX", part.FAR_FACE_POINT),
        ("TabEndX", geom.OUTER_TAB_END),
    ):
        y = keep[name][1]
        lines[f"{name} ext"] = (
            drawing._front(*feature),
            (drawing._front(*feature)[0], y),
        )
        lines[f"{name} origin ext"] = (
            drawing._front(0.0, 0.0),
            (drawing._front(0.0, 0.0)[0], y),
        )
        lines[name] = (
            (drawing._front(*feature)[0], y),
            (drawing._front(0.0, 0.0)[0], y),
        )
    return lines


def test_no_dimension_line_runs_through_another_text() -> None:
    """The straight's dimension sits outside the pin hole's size; the far
    face's extension line drops clear of it."""
    texts = {**_texts(), **_notes()}
    for line_name, (p, q) in _front_lines().items():
        owner = line_name.split(" ")[0]
        for name, box in texts.items():
            if name == owner:
                continue
            assert not (_inside(p, box) or _inside(q, box)), (line_name, name)
            for r, s in _box_edges(box):
                assert not _crosses(p, q, r, s), (line_name, name)


def test_the_roll_radius_is_shortened_because_its_centre_leaves_the_sheet() -> None:
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]

    def on_sheet(point) -> bool:
        x, y = drawing._front(*point)
        return (
            _BORDER < x < template.width_m - _BORDER
            and _BORDER < y < template.height_m - _BORDER
        )

    assert not on_sheet(geom.ROLL_C_L)
    assert on_sheet(geom.TAB_C_L)
    assert drawing.SHORTENED_RADII == ("RollR",)
    # The roll radius text sits between the inside arc and its centre.
    text = drawing.FRONT_KEEP["RollR"]
    centre = drawing._front(*geom.ROLL_C_L)
    assert math.dist(text, centre) < geom.INNER_ROLL_R * drawing._S
    angle = math.degrees(math.atan2(text[1] - centre[1], text[0] - centre[0]))
    assert -geom.ROLL_TURN_DEG < angle < 0.0


def test_the_view_origins_follow_their_centres_and_projection() -> None:
    """The side view is level with the front view (third-angle projection);
    each origin is its view's bounding-box centre offset by the part's."""
    assert drawing.RIGHT_ORIGIN[1] == drawing.FRONT_ORIGIN[1]
    assert drawing.RIGHT_CENTER[0] > drawing.FRONT_CENTER[0]
    x0, x1 = (x - geom.PART_ORIGIN_MACHINE[0] for x in geom.BBOX_X)
    y0, y1 = (y - geom.PART_ORIGIN_MACHINE[1] for y in geom.BBOX_Y)
    assert drawing._front((x0 + x1) / 2.0, (y0 + y1) / 2.0) == pytest.approx(
        drawing.FRONT_CENTER
    )
    assert drawing._right(geom.EAR_HEIGHT / 2.0, (y0 + y1) / 2.0) == pytest.approx(
        drawing.RIGHT_CENTER
    )
    assert drawing._bottom((x0 + x1) / 2.0, geom.EAR_HEIGHT / 2.0) == pytest.approx(
        drawing.BOTTOM_CENTER
    )
