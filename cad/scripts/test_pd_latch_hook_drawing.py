"""Offline contracts for the latch hook (MHA-PD-014) and its drawing."""

from __future__ import annotations

import ast
import importlib.util
import itertools
import math
from pathlib import Path

import pytest

import _config
import build_pd_latch_hook as part
import draw_pd_latch_hook as drawing
import pd_latch_hook_bracket_geometry as bracket
import pd_latch_hook_geometry as geom
import pd_latch_hook_spec as spec
import pd_paper_drive_assembly_steps as steps
import pd_support_bar_spec as bar
import pd_transgear_arm_geometry as arm
import vn_transgear_latch_pin_spec as pin
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME


def _band(places: int) -> float:
    return _config.title_block(f"linear_{places}pl")["value_in"] * 25.4


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-latch-hook.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-latch-hook.pdf")
    assert DRAWINGS_BY_NAME["pd_latch_hook"].script == Path(drawing.__file__).resolve()
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_placement_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_only_the_drilled_holes_carry_a_model_band() -> None:
    assert model_toleranced_dimensions(part) == {
        ("PinHoleProfile", "PinHoleDia"): "*deviations(HOLE_BAND)",
        ("RivetHoleProfile", "RivetHoleDia"): "*deviations(HOLE_BAND)",
    }
    assert min(spec.HOLE_BAND) == 0.0 < max(spec.HOLE_BAND)


def _on_centreline(y: float, z: float) -> float:
    """Distance of machine (y, z) from the centreline arc that governs y."""
    centre, radius = (geom.C1, geom.R1) if y >= geom.JUNCTION[0] else (geom.C2, geom.R2)
    return abs(math.hypot(y - centre[0], z - centre[1]) - radius)


def test_the_centreline_is_two_tangent_arcs_from_a_square_top() -> None:
    """R9-10: the tangent two-arc chain replaces the traced spline; the top
    cut is square to the strip.  R9-26: the pin's axis crosses the strip at
    the arm's pin height; the hole is within the sheet's centring band of the
    centreline."""
    # Square top: arc 1's centre lies on the normal to the cut line (y const).
    assert geom.C1[0] == geom.TOP_Y
    # Tangent: both centres and the junction collinear.
    (y1, z1), (y2, z2), (yj, zj) = geom.C1, geom.C2, geom.JUNCTION
    cross = (y2 - y1) * (zj - z1) - (z2 - z1) * (yj - y1)
    assert abs(cross) / (geom.R1 * geom.R1) < 1e-5
    for station in (geom.JUNCTION, geom.END_YZ):
        assert _on_centreline(*station) < 2e-3
    arm_pin_z = arm.FRONT_FACE_MACHINE_Z + arm.THICKNESS / 2.0
    assert geom.PIN_AXIS_YZ[1] == pytest.approx(arm_pin_z, abs=1e-9)
    assert _on_centreline(*geom.PIN_HOLE_YZ) <= spec.CENTRING_BAND
    # The rivet pair straddles the centreline symmetrically.
    (ya, za), (yb, zb) = geom.RIVET_YZ
    assert ya == yb == geom.RIVET_Y
    assert zb - za == pytest.approx(geom.RIVET_PITCH)
    assert (za + zb) / 2.0 == pytest.approx(geom.centreline_z(geom.RIVET_Y))


def test_the_strip_fills_the_contract_envelope() -> None:
    """The model carries the printed 99.9 tip run, 0.05 short of the
    contract's 206.25 end; the envelope holds within that."""
    assert geom.END_YZ[0] == pytest.approx(geom.TOP_Y - round(geom.TIP_RUN, 1))
    assert geom.BBOX_Y == pytest.approx((201.25, 306.2), abs=0.06)
    assert geom.BBOX_Z[0] == pytest.approx(-128.5, abs=0.06)
    assert geom.PLANE_X[1] - geom.PLANE_X[0] == pytest.approx(geom.STRIP_T)


def test_walls_hold_the_target_at_the_worst_case_the_sheet_prints() -> None:
    drill = max(spec.HOLE_BAND)
    rivet_r = (geom.RIVET_HOLE_DIA + drill) / 2.0
    pin_r = (geom.PIN_HOLE_DIA + drill) / 2.0
    tol3 = _band(spec.RIVET_PLACES)
    edge_loss = spec.CENTRING_BAND + spec.STOCK_WIDTH_TOL / 2.0
    top = round(geom.RIVET_RUN, 3) - tol3 - rivet_r
    web = round(geom.RIVET_PITCH, 3) - tol3 - 2.0 * rivet_r
    edge = geom.HALF_W - (round(geom.RIVET_PITCH, 3) + tol3) / 2.0 - rivet_r - edge_loss
    pin = geom.HALF_W - pin_r - edge_loss
    for worst in (top, web, edge, pin):
        assert worst >= spec.WALL_TARGET - 0.01
    assert spec.WALLS_WORST == pytest.approx(
        {
            "rivet hole to top cut": top,
            "rivet hole to long edge": edge,
            "rivet web": web,
            "pin hole to long edge": pin,
        },
        abs=0.01,
    )


def _swept_pin(dia: float) -> list[tuple[float, float]]:
    """Machine (y, z) of the pin's surface where it crosses the strip's two
    faces, the arm at its drawn pose: its full ``dia`` swept obliquely."""
    pivot = (bar.PIVOT_TAP_X, bracket.BAR_CENTRE_Y + bar.HANGER_TAP_Y)
    axis_y, axis_z = geom.PIN_AXIS_YZ
    mid_x = sum(geom.PLANE_X) / 2.0
    run = (mid_x - pivot[0], axis_y - pivot[1])
    length = math.hypot(*run)
    ux, uy = run[0] / length, run[1] / length  # the pin axis, in a z plane
    points = []
    for step in range(3600):
        phi = 2.0 * math.pi * step / 3600
        # A point on the pin's surface: across the axis in the xy plane by
        # r cos(phi) (normal (-uy, ux)), along z by r sin(phi).
        across, off_z = dia / 2.0 * math.cos(phi), dia / 2.0 * math.sin(phi)
        off_x, off_y = -uy * across, ux * across
        for face_x in geom.PLANE_X:
            s = (face_x - mid_x - off_x) / ux
            points.append((axis_y + s * uy + off_y, axis_z + off_z))
    return points


def _room_below(points: list[tuple[float, float]], hole: tuple[float, float]) -> float:
    """How far the swept pin can fall down the strip (-y) inside a Ø5.4 at
    its least size centred on ``hole``: the arm's drop on the latch."""
    r = geom.PIN_HOLE_DIA / 2.0
    return min(
        (y - hole[0]) + math.sqrt(max(r**2 - (z - hole[1]) ** 2, 0.0))
        for y, z in points
    )


def test_the_latch_pin_enters_its_hole_at_the_fit_up_pose() -> None:
    """The pin's full diameter, swept obliquely through the strip, leaves the
    5.4 hole the latch's minimum room each side along the strip."""
    reach = max(
        math.hypot(y - geom.PIN_AXIS_YZ[0], z - geom.PIN_AXIS_YZ[1])
        for y, z in _swept_pin(pin.DIA_MAX)
    )
    clearance = geom.PIN_HOLE_DIA / 2.0 - reach
    assert clearance >= spec.PIN_CLEARANCE_MIN
    assert spec.PIN_CLEARANCE_ALONG == pytest.approx(clearance, abs=1e-3)


def test_the_arm_rests_on_the_hook_and_keeps_its_feed_mesh() -> None:
    """Codex P1 on b2eb9a0e1: the hook is set with its hole's lower edge on
    the pin, and the drawn hole holds the largest pin there, so the unclamped
    arm cannot fall through it to open the feed mesh past the 1.1 rule.  A
    hole centred on the pin's axis let the arm fall 0.620 along the strip,
    the pinion 0.220: the band's loose end ran at e 0.839, CR 0.77 at the
    smallest tip (the nominal set's 0.55 at e 0.770, CR 0.88)."""
    largest, least = _swept_pin(pin.DIA_MAX), _swept_pin(pin.DIA + min(pin.DIA_BAND))
    # Bearing, not interfering: the largest pin touches the lower edge, the
    # least one sits within a few hundredths of it.
    assert _room_below(largest, geom.PIN_HOLE_YZ) == pytest.approx(0.0, abs=2e-3)
    assert _room_below(least, geom.PIN_HOLE_YZ) < 0.01
    assert steps.LATCH_SLACK_ALONG == pytest.approx(
        _room_below(largest, geom.PIN_HOLE_YZ), abs=2e-3
    )
    steps.check_mesh_band(
        steps.MESH_BACKLASH_RANGE, _room_below(least, geom.PIN_HOLE_YZ)
    )
    # The hole drawn on the pin's axis: the arm falls through its clearance.
    centred = _room_below(largest, geom.PIN_AXIS_YZ)
    assert centred == pytest.approx(spec.PIN_CLEARANCE_ALONG, abs=2e-3)
    with pytest.raises(ValueError, match="working window"):
        steps.check_mesh_band(steps.MESH_BACKLASH_RANGE, centred)


def _spec_with(monkeypatch, name: str, value):
    monkeypatch.setattr(geom, name, value)
    loaded = importlib.util.spec_from_file_location("_hook_perturbed", spec.__file__)
    fresh = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(fresh)
    return fresh


def test_the_wall_gate_refuses_the_contract_pitch(monkeypatch) -> None:
    """The contract's 3.2 rivet pitch leaves the web under target."""
    fresh = _spec_with(monkeypatch, "RIVET_PITCH", geom.RIVET_PITCH)
    assert fresh.WALLS_WORST == spec.WALLS_WORST
    with pytest.raises(AssertionError, match="rivet web"):
        _spec_with(monkeypatch, "RIVET_PITCH", 3.2)


def test_legacy_assembly_extents_stay_exported() -> None:
    assert part.STRIP_T == geom.STRIP_T == 0.6
    assert part.X_MAX == pytest.approx(0.0, abs=1e-9)
    assert part.X_MIN == pytest.approx(-(geom.TIP_RUN + geom.TIP_R), abs=0.01)
    assert part.Y_MIN == pytest.approx(-11.8605, abs=0.01)


def test_registry_row_is_the_dead_soft_strip_mha_127() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-014"
    assert int(row["quantity"]) == 1
    assert "dead soft" in row["material_specification"]
    assert "spring" not in row["finish"] + row["material_specification"]
    # Review of 19e33c6c2: the stock is the title block's MATERIAL cell, so no
    # note restates it; the cell holds 30 characters.
    assert row["material"] == spec.MATERIAL_TITLE
    assert len(spec.MATERIAL_TITLE) <= 30
    stock = f"{geom.STRIP_W:g} x {geom.STRIP_T:g}"
    assert stock in row["material"] and stock in row["material_specification"]


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
        "{'Manufacturing Notes': DRAWING_NOTES}",
    ]
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None, part.PART_NAME, {"Manufacturing Notes": spec.DRAWING_NOTES}
    )
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []


_TITLE_BLOCK_TEXT = ("BREAK SHARP EDGES", "DEBURR", "REMOVE BURRS")


def test_the_notes_fit_the_note_field_and_leave_the_title_block_its_own() -> None:
    """Review of 19e33c6c2: BREAK SHARP EDGES restated the title block and
    the stock line the MATERIAL cell.  At most 4 lines of at most 70."""
    lines = spec.DRAWING_NOTES.split("\n")
    assert len(lines) <= 4
    assert [line for line in lines if len(line) > 70] == []
    assert [t for t in _TITLE_BLOCK_TEXT if t in spec.DRAWING_NOTES] == []
    assert "STRIP" not in spec.DRAWING_NOTES.replace("STRIP TO LIE FLAT", "")


def test_the_centring_note_states_what_the_rivet_pair_holds() -> None:
    """Review of 19e33c6c2 (blocker): "ALL HOLES ... CENTRED ON THE STRIP
    WIDTH" contradicted the rivet pair 3.900 apart.  The note centres the
    pin hole and the pair's midpoint -- which is what the model holds -- and
    no single rivet hole, which sits half a pitch off the centreline."""
    notes = spec.DRAWING_NOTES
    assert "ALL HOLES" not in notes
    (centring,) = [line for line in notes.split("\n") if "CENTRE" in line]
    assert "PIN HOLE" in centring and "RIVET HOLES' MIDPOINT" in centring
    assert f"WITHIN {spec.CENTRING_BAND:.2f}" in centring
    # The pair's midpoint is on the centreline; a single hole is far outside
    # the band, so a note centring each hole would be false.
    (ya, za), (_, zb) = geom.RIVET_YZ
    centre_z = geom.centreline_z(ya)
    assert abs((za + zb) / 2.0 - centre_z) <= 1e-6
    assert min(abs(za - centre_z), abs(zb - centre_z)) > spec.CENTRING_BAND
    assert _on_centreline(*geom.PIN_HOLE_YZ) <= spec.CENTRING_BAND


def test_the_template_callouts_state_the_constructions_the_model_holds() -> None:
    """Review of 19e33c6c2 (blocker): R845.0, R485.0 and 52.9 did not fix
    the arcs' centres or their tangency.  R845's centre is on the top cut's
    line extended, R485 is internally tangent to it, and the 52.9 run ends at
    that tangent point on the inner edge."""
    top_cut_x = geom.TOP_LOWER[0]
    assert geom.TOP_UPPER[0] == top_cut_x
    assert geom.C1_L[0] == pytest.approx(top_cut_x, abs=1e-9)
    assert "TOP CUT" in spec.INNER_R1_CALLOUT
    # Internal tangency: the centres are R1 - R2 apart, both on the inner side.
    gap = math.dist(geom.C1_L, geom.C2_L)
    assert gap == pytest.approx(geom.INNER_R1 - geom.INNER_R2, abs=1e-3)
    assert geom.C1_L[1] < geom.TOP_LOWER[1] and geom.C2_L[1] < geom.TOP_LOWER[1]
    assert "TANGENT" in spec.INNER_R2_CALLOUT
    # The 52.9 run lands on the inner edge's tangent point.
    tangent = geom.JUNCTION_LOWER
    assert math.dist(tangent, geom.C1_L) == pytest.approx(geom.INNER_R1, abs=2e-3)
    assert math.dist(tangent, geom.C2_L) == pytest.approx(geom.INNER_R2, abs=2e-3)
    assert -tangent[0] == pytest.approx(geom.JUNCTION_RUN, abs=1e-9)
    assert "TANGENT POINT" in spec.JUNCTION_RUN_CALLOUT
    assert "CENTRE" in spec.TIP_RUN_CALLOUT
    for name in ("InnerR1", "InnerR2"):
        assert name in drawing.DIMENSION_CALLOUTS
    assert {"JunctionRun", "TipRun"} <= set(drawing.CALLOUTS_ABOVE)


# Sheet text: 3.5 dimension characters, the notes' 3.0 (top-left anchored).
_CHAR_WIDTH = 0.00276
_LINE_PITCH = 0.0045
_NOTE_CHAR_WIDTH = 0.0024
_NOTE_LINE_PITCH = 0.0042
_BORDER = 0.0127
_S = drawing._S / 1000.0


def _box(
    lines: list[str], xy: tuple[float, float], above: int = 0
) -> tuple[float, ...]:
    """A text box centred on ``xy``, ``above`` callout lines stacked over it."""
    half_width = max(map(len, lines)) * _CHAR_WIDTH / 2.0
    body = len(lines) - above
    return (
        xy[0] - half_width,
        xy[1] - body * _LINE_PITCH / 2.0,
        xy[0] + half_width,
        xy[1] + body * _LINE_PITCH / 2.0 + above * _LINE_PITCH,
    )


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _crosses(p, q, r, s) -> bool:
    """Whether segments pq and rs properly intersect."""

    def side(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return side(p, q, r) * side(p, q, s) < 0 and side(r, s, p) * side(r, s, q) < 0


def _box_edges(box):
    x0, y0, x1, y1 = box
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return list(zip(corners, corners[1:] + corners[:1]))


def _layout():
    """Every text box, dimension line and leader of the face view, in sheet
    metres, from the drawing's own placements and the model's geometry."""
    keep = drawing.FRONT_KEEP
    notes_lines = spec.DRAWING_NOTES.split("\n")
    nx, ny = drawing.NOTES_XY
    notes = (
        nx,
        ny - len(notes_lines) * _NOTE_LINE_PITCH,
        nx + max(map(len, notes_lines)) * _NOTE_CHAR_WIDTH,
        ny,
    )
    top_cut_x = drawing._sheet(0.0, 0.0)[0]
    runs = {
        "JunctionRun": -geom.JUNCTION_RUN,
        "PinHoleRun": geom.PIN_HOLE_L[0],
        "TipRun": geom.END_L[0],
        "RivetRun": geom.RIVET_L[0][0],
    }
    overall_xy = drawing._sheet(-spec.OVERALL_LENGTH / 2.0, drawing.OVERALL_TEXT_Y)
    dim_lines = {
        name: ((drawing._sheet(x, 0.0)[0], keep[name][1]), (top_cut_x, keep[name][1]))
        for name, x in runs.items()
    }
    dim_lines["overall"] = (
        (drawing._sheet(-spec.OVERALL_LENGTH, 0.0)[0], overall_xy[1]),
        (top_cut_x, overall_xy[1]),
    )
    # The pitch's extension lines run from each rivet centre to its text.
    for i, (x, y) in enumerate(geom.RIVET_L):
        start = drawing._sheet(x, y)
        dim_lines[f"RivetPitch ext {i}"] = (start, (keep["RivetPitch"][0], start[1]))
    texts = {
        "JunctionRun": _box(
            ["52.9", spec.JUNCTION_RUN_CALLOUT], keep["JunctionRun"], 1
        ),
        "PinHoleRun": _box(["77.16"], keep["PinHoleRun"]),
        "TipRun": _box(["99.9", spec.TIP_RUN_CALLOUT], keep["TipRun"], 1),
        "overall": _box(["(104.9)"], overall_xy),
        "InnerR1": _box(
            ["R845.0", *spec.INNER_R1_CALLOUT.splitlines()], keep["InnerR1"]
        ),
        "InnerR2": _box(
            ["R485.0", *spec.INNER_R2_CALLOUT.splitlines()], keep["InnerR2"]
        ),
        "PinHoleDia": _box(
            ["\u00d85.40 +0.10", "0.00", spec.PIN_HOLE_CALLOUT], keep["PinHoleDia"]
        ),
        "RivetRun": _box(["3.200"], keep["RivetRun"]),
        "RivetPitch": _box(["3.900"], keep["RivetPitch"]),
        "RivetHoleDia": _box(
            ["\u00d81.65 +0.10", "0.00", spec.RIVET_HOLE_CALLOUT], keep["RivetHoleDia"]
        ),
    }

    def rim(centre_l, radius, text):
        centre = drawing._sheet(*centre_l)
        d = math.dist(centre, text)
        r = radius * _S
        return (
            centre[0] + (text[0] - centre[0]) * r / d,
            centre[1] + (text[1] - centre[1]) * r / d,
        )

    leaders = {
        "PinHoleDia": rim(geom.PIN_HOLE_L, geom.PIN_HOLE_DIA / 2.0, keep["PinHoleDia"]),
        "RivetHoleDia": rim(
            geom.RIVET_L[0], geom.RIVET_HOLE_DIA / 2.0, keep["RivetHoleDia"]
        ),
        "InnerR1": rim(geom.C1_L, geom.INNER_R1, keep["InnerR1"]),
        "InnerR2": rim(geom.C2_L, geom.INNER_R2, keep["InnerR2"]),
    }
    leaders = {name: (keep[name], end) for name, end in leaders.items()}
    return texts, dim_lines, leaders, notes


def test_every_text_stands_inside_the_border_off_the_title_block_and_notes() -> None:
    """Review of 19e33c6c2: the template radii ran through the bottom border
    and the title block, the Ø5.40 into the notes."""
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    title_block = (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    texts, _lines, _leaders, notes = _layout()
    iso_half = _iso_half_extents()
    iso = (
        drawing.ISO_CENTER[0] - iso_half[0],
        drawing.ISO_CENTER[1] - iso_half[1],
        drawing.ISO_CENTER[0] + iso_half[0],
        drawing.ISO_CENTER[1] + iso_half[1],
    )
    for box, name in [
        *((b, n) for n, b in texts.items()),
        (notes, "notes"),
        (iso, "iso"),
    ]:
        assert box[0] > _BORDER + 0.002 and box[1] > _BORDER + 0.002, name
        assert box[2] < template.width_m - _BORDER - 0.002, name
        assert box[3] < template.height_m - _BORDER - 0.002, name
        assert not _overlap(box, title_block), name
    boxes = {**texts, "notes": notes, "iso": iso}
    for (a, box_a), (b, box_b) in itertools.combinations(boxes.items(), 2):
        assert not _overlap(box_a, box_b), (a, b)
    # The strip itself stays clear of the notes and the isometric view.
    outline = [drawing._sheet(x, y) for x, y in geom._OUTLINE]
    strip = (
        min(p[0] for p in outline),
        min(p[1] for p in outline),
        max(p[0] for p in outline),
        max(p[1] for p in outline),
    )
    assert not _overlap(strip, notes) and not _overlap(strip, iso)


def test_no_leader_crosses_a_dimension_line_a_text_or_the_notes() -> None:
    """Review of 19e33c6c2: the Ø1.65 leader crossed the 52.9 and 3.200
    dimensions and the Ø5.40 leader crossed the notes."""
    texts, dim_lines, leaders, notes = _layout()
    for name, (start, end) in leaders.items():
        for line_name, (p, q) in dim_lines.items():
            assert not _crosses(start, end, p, q), (name, line_name)
        for other, box in {**texts, "notes": notes}.items():
            if other == name:
                continue
            for p, q in _box_edges(box):
                assert not _crosses(start, end, p, q), (name, other)
    for (a, (pa, qa)), (b, (pb, qb)) in itertools.combinations(leaders.items(), 2):
        assert not _crosses(pa, qa, pb, qb), (a, b)


def test_the_template_radii_are_shortened_where_their_centres_leave_the_sheet() -> None:
    """Review of 19e33c6c2: full-length R485/R845 lines ran to centres 1.4 m
    and 2.5 m off the sheet, through the border and the title block."""
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    off_sheet = {
        name
        for name, centre in (("InnerR1", geom.C1_L), ("InnerR2", geom.C2_L))
        if not (
            _BORDER < drawing._sheet(*centre)[0] < template.width_m - _BORDER
            and _BORDER < drawing._sheet(*centre)[1] < template.height_m - _BORDER
        )
    }
    assert off_sheet == {"InnerR1", "InnerR2"}
    assert off_sheet <= set(drawing.SHORTENED_RADII)
    # Each radius text sits between its arc and its centre: the shortened
    # line points at the centre from the concave side.
    _texts, _lines, leaders, _notes = _layout()
    for name, centre in (("InnerR1", geom.C1_L), ("InnerR2", geom.C2_L)):
        text, rim = leaders[name]
        centre_sheet = drawing._sheet(*centre)
        assert math.dist(text, centre_sheet) < math.dist(rim, centre_sheet), name


def test_the_overall_reference_runs_to_the_full_round_extreme() -> None:
    """Review of 19e33c6c2: 99.9 runs to the end round's centre; the strip's
    true overall prints as a reference, outermost over the run stack."""
    # LOCAL_X_MIN is the sampled outline's extreme.
    assert spec.OVERALL_LENGTH == pytest.approx(-geom.LOCAL_X_MIN, abs=1e-4)
    assert spec.OVERALL_LENGTH == pytest.approx(geom.TIP_RUN + geom.TIP_R)
    assert spec.DRAWING_REFERENCE_PRECISION == {
        "overall length reference": spec.TEMPLATE_PLACES
    }
    # The round pick is on the full round's flank, on the far side of its
    # centre, so re-anchoring to the arc's extreme takes the free end.
    pick = drawing._ROUND_PICK
    assert math.dist(pick, geom.END_L) == pytest.approx(geom.TIP_R)
    assert pick[0] < geom.END_L[0]
    top_pick = drawing._TOP_CUT_PICK
    assert top_pick[0] == geom.TOP_UPPER[0]
    assert geom.TOP_LOWER[1] < top_pick[1] < geom.TOP_UPPER[1]
    for x, y in geom.RIVET_L:
        assert math.dist(top_pick, (x, y)) > geom.RIVET_HOLE_DIA
    runs_y = [drawing.FRONT_KEEP[n][1] for n in ("JunctionRun", "PinHoleRun", "TipRun")]
    overall_y = drawing._sheet(0.0, drawing.OVERALL_TEXT_Y)[1]
    assert overall_y > max(runs_y)


def _iso_half_extents() -> tuple[float, float]:
    """Half the isometric view's sheet extents: the strip's outline at either
    face, projected on the standard isometric's screen axes."""
    scale = drawing.ISO_SCALE[0] / drawing.ISO_SCALE[1] / 1000.0
    points = [
        ((x - z) / math.sqrt(2.0), (-x + 2.0 * y - z) / math.sqrt(6.0))
        for x, y in geom._OUTLINE
        for z in (0.0, geom.STRIP_T)
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    # Line weight and silhouette rounding.
    return (
        (max(xs) - min(xs)) * scale / 2.0 + 0.002,
        (max(ys) - min(ys)) * scale / 2.0 + 0.002,
    )
