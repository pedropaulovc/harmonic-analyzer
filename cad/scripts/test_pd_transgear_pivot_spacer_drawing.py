"""Offline contracts for the transgear pivot spacer (MHA-PD-020) and its drawing."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_common
import _gtol_face
import build_pd_transgear_pivot_spacer as part
import draw_pd_transgear_pivot_spacer as drawing
import pd_transgear_pivot_spacer_spec as spec
import vn_transgear_pivot_screw_spec as screw
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _layout_geometry import Box, estimate_text_box
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-pivot-spacer.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-pivot-spacer.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-pivot-spacer_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_pivot_spacer"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert {
        (feature, name)
        for feature, names in spec.DRAWING_PRECISION.items()
        for name in names
    } == {
        (feature, name)
        for feature, names in spec.DRAWING_DIMENSIONS.items()
        for name in names
    }
    # Every size is a "hold it" size: O.D. and bore under the .XXX row, the
    # length under its explicit band.
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {3}


def test_the_length_and_the_bore_carry_their_bands_on_the_model() -> None:
    """The MHA-VN-049 spring's room rides the length and the shoulder press the
    bore, so each band is a native model tolerance from the spec (policy
    rule 2).  The O.D. prints at .XXX and the title block's row governs it;
    restating that row on the dimension is what policy rule 1 forbids."""
    assert model_toleranced_dimensions(part) == {
        ("Ring", "RingLength"): "LENGTH_BAND",
        ("RingProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    row = _config.title_block("linear_3pl")["value_in"] * 25.4
    assert 0.0 < spec.LENGTH_BAND < row
    # The ream only cuts oversize: the bore never prints under nominal.
    assert min(spec.BORE_DIA_BAND) == 0.0 < max(spec.BORE_DIA_BAND) < row
    assert (spec.BORE_DIA_MIN, spec.BORE_DIA_MAX) == pytest.approx((4.727, 4.735))


def test_the_bore_holds_a_light_press_on_the_shoulder_at_every_limit() -> None:
    """The ring is pressed flush on the MHA-VN-041 shoulder (Ø4.7625 -0.0254/0)
    so screw and spacer seat on the bar as one body: the smallest shoulder in
    the largest ream still grips, and the largest in the smallest stays
    light."""
    shoulder_min = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[0]
    shoulder_max = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[1]
    loosest = shoulder_min - spec.BORE_DIA_MAX
    tightest = shoulder_max - spec.BORE_DIA_MIN
    assert spec.PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert (loosest, tightest) == pytest.approx((0.0021, 0.0355), abs=1e-6)
    assert 0.0 < loosest < tightest


def test_wall_bands_cover_the_printed_xxx_row() -> None:
    """The wall stack charges the O.D. at least the .XXX row it prints under
    and the bore its largest ream, and the MIN the sheet states never rounds
    the worst case up (policy rule 12)."""
    row = _config.title_block("linear_3pl")["value_in"] * 25.4
    assert spec.OD_BAND >= row
    worst_at_row = (spec.OD - row - spec.BORE_DIA_MAX) / 2.0
    assert spec.WALL_WORST_PRINTED <= spec.WALL_WORST + 1e-9 <= worst_at_row + 1e-9
    assert 1.5 <= spec.WALL_WORST_PRINTED < 2.0


def test_sheet_notes_carry_the_wall_and_no_facing_step() -> None:
    """R9-6: the spacer is fitted as made, never faced."""
    lines = spec.DRAWING_NOTES.splitlines()
    assert f"WALL {spec.WALL_WORST_PRINTED:.2f} MIN." in lines
    assert not any("FACE" in line for line in lines)
    # The length and its band ride the dimension, never the note text.
    assert "±" not in spec.DRAWING_NOTES
    assert f"{spec.LENGTH:.3f}" not in spec.DRAWING_NOTES


def test_both_end_faces_run_machined_and_the_bore_carries_no_symbol() -> None:
    faces = {
        control.key: (control.roughness_um, control.face)
        for control in spec.SURFACE_FINISHES
    }
    assert set(faces) == {"front_face", "rear_face"}
    front_ra, front = faces["front_face"]
    rear_ra, rear = faces["rear_face"]
    assert front_ra == rear_ra == MACHINED_UM
    # Part frame: axis +Z, the bar-side face at z 0, the arm-side face at
    # z LENGTH (the RearFace plane).
    assert (tuple(front.normal), front.offset_mm) == ((0.0, 0.0, -1.0), 0.0)
    assert (tuple(rear.normal), rear.offset_mm) == ((0.0, 0.0, 1.0), spec.LENGTH)


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the front
    (bar) face is the right end, the rear (arm) face the left end.  A pick on
    the other end would hang the symbol on the wrong face."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    centre_x = drawing.PROFILE_CENTER[0]

    def sheet_x(z_mm: float) -> float:
        return centre_x - (z_mm - spec.LENGTH / 2.0) * scale

    assert drawing.PROFILE_ANGLE == pytest.approx(-0.5 * 3.141592653589793)
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    for key, (pick, _symbol) in drawing.FACE_FINISHES.items():
        assert pick[0] == pytest.approx(sheet_x(faces[key].offset_mm))
        radius = abs(pick[1] - drawing.PROFILE_CENTER[1]) / scale
        assert spec.BORE_DIA / 2.0 < radius < spec.OD / 2.0
    # Third angle: the end view seen from the +Z (left) end sits left of the
    # profile, on its axis.
    assert drawing.END_CENTER[0] < drawing.PROFILE_CENTER[0]
    assert drawing.END_CENTER[1] == drawing.PROFILE_CENTER[1]


def test_both_end_faces_hold_square_to_the_bore_datum() -> None:
    """Pressed on the shoulder, the bore is the screw's axis (datum A); the
    bar seats the front face and the arm the rear, so the arm tilts by both
    faces' perpendicularity to A over the smallest face it seats on."""
    assert spec.BORE_DATUM == "A"
    assert spec.GEOMETRIC_TOLERANCES_MM == {
        "rear face perpendicularity to bore": "0.01",
        "front face perpendicularity to bore": "0.01",
    }
    assert spec.REAR_FACE_PERPENDICULARITY == pytest.approx(0.01)
    assert spec.FRONT_FACE_PERPENDICULARITY == pytest.approx(0.01)
    assert spec.FACE_PERPENDICULARITY_ZONE_DIA == pytest.approx(spec.OD - spec.OD_BAND)
    # Each frame sits on the exact plane its finish row names: the rear face
    # at z LENGTH, the front at z 0.
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    frames = {mark.key: mark for mark in _FRAMES}
    assert set(frames) == {"rear_face", "front_face"}
    for key, z in (("rear_face", spec.LENGTH), ("front_face", 0.0)):
        assert frames[key].face == faces[key]
        assert frames[key].face_z_mm == pytest.approx(z)


_FRAMES = (drawing.REAR_FACE_FRAME, drawing.FRONT_FACE_FRAME)


_S = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
# A leader's arrowhead as the hub's farm run drew it (20261002T180658288Z).
_ARROWHEAD = 0.00313
# A finish symbol's ink from its insertion point at 2.5 mm text, measured on
# the feed pinion's run 20261001T110844152Z: left of the root by 2.1, right to
# the "Ra" text's corner at 14.7, up 7.2.
_FINISH_INK = (-0.0021, 0.0, 0.0147, 0.0072)
# Dimension text as the fleet's sheets print it (test_arbor_pedestal_drawing).
_CAP_M = 0.0035
_ADVANCE = 109.7 / (42 * 3.5)
_AIR = 0.002


def _sheet_point(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (x, z) on the profile: *Top turned a quarter
    turn clockwise, so model +Z runs left and model +X down."""
    return (
        drawing.PROFILE_CENTER[0] - (z_mm - spec.LENGTH / 2.0) * _S,
        drawing.PROFILE_CENTER[1] - x_mm * _S,
    )


def _frame_box(mark) -> Box:
    x, top = drawing.frame_position(mark, mark.nominal_landing)
    return Box(x, top - drawing.FRAME_HEIGHT, x + drawing.FRAME_WIDTH, top)


def test_each_frame_lands_square_on_its_own_face() -> None:
    """The rear face's leader lands on the profile's left end and the front
    face's on its right end.  Each lands on its face's annulus an arrowhead
    and a millimetre or more from the corner the face shares with the O.D.,
    runs level from its frame (square to the face) and stands outboard of
    its face, on the side of the axis that face's finish leaves free."""
    finish_picks = {key: pick for key, (pick, _symbol) in drawing.FACE_FINISHES.items()}
    for mark in _FRAMES:
        landing = mark.nominal_landing
        assert landing == pytest.approx(_sheet_point(mark.landing_x_mm, mark.face_z_mm))
        radius = abs(mark.landing_x_mm)
        assert spec.BORE_DIA_MAX / 2.0 < radius < spec.OD / 2.0
        assert (spec.OD / 2.0 - radius) * _S >= _ARROWHEAD + 0.001
        finish_side = finish_picks[mark.key][1] - drawing.PROFILE_CENTER[1]
        assert (landing[1] - drawing.PROFILE_CENTER[1]) * finish_side < 0.0
        frame = _frame_box(mark)
        assert (frame.ymin + frame.ymax) / 2.0 == pytest.approx(landing[1])
        # Outboard: left of the rear (left) end, right of the front (right) end.
        if mark.key == "rear_face":
            assert landing[0] == pytest.approx(_sheet_point(0.0, spec.LENGTH)[0])
            assert landing[0] - frame.xmax >= _ARROWHEAD + 0.003
        else:
            assert landing[0] == pytest.approx(_sheet_point(0.0, 0.0)[0])
            assert frame.xmin - landing[0] >= _ARROWHEAD + 0.003


def _text_box(text: str, anchor: tuple[float, float], reference: int) -> Box:
    box = estimate_text_box(
        text, anchor=anchor, height=_CAP_M, reference=reference, advance_ratio=_ADVANCE
    )
    assert box is not None
    return box


def test_both_frames_stand_inside_the_sheet_clear_of_every_annotation() -> None:
    """Both frames and their leaders keep 2 mm of air from every other
    annotation's box and line on the sheet (the dimensions' text and
    extension lines, both finishes, the notes, the axis centreline and both
    views) and from each other, and stand inside the inner border, off the
    title block."""
    s = _S
    centre_x, axis_y = drawing.PROFILE_CENTER
    rear_x, front_x = _sheet_point(0.0, spec.LENGTH)[0], _sheet_point(0.0, 0.0)[0]
    top, bottom = axis_y + spec.OD / 2.0 * s, axis_y - spec.OD / 2.0 * s
    length_y = drawing.PROFILE_KEEP["RingLength"][1]
    od_x = drawing.OD_ON_PROFILE[0]
    end_r = spec.OD / 2.0 * s
    obstacles = {
        "profile": Box(rear_x, bottom, front_x, top),
        "end view": Box(
            drawing.END_CENTER[0] - end_r,
            drawing.END_CENTER[1] - end_r,
            drawing.END_CENTER[0] + end_r,
            drawing.END_CENTER[1] + end_r,
        ),
        "length text": _text_box(
            f"{spec.LENGTH:.3f}±{spec.LENGTH_BAND:.3f}",
            drawing.PROFILE_KEEP["RingLength"],
            2,
        ),
        "O.D. text": _text_box(f"\u00d8{spec.OD:.3f}", drawing.OD_ON_PROFILE, 2),
        "bore text": _text_box(
            f"\u00d8{spec.BORE_DIA:.3f} +{max(spec.BORE_DIA_BAND):.3f}\n"
            f"{drawing.DIMENSION_CALLOUTS['BoreDia']}",
            drawing.END_KEEP["BoreDia"],
            2,
        ),
        "notes": _text_box(spec.DRAWING_NOTES, drawing.NOTES_XY, 0),
        "isometric note": _text_box(spec.ISOMETRIC_VIEW_NOTE, drawing.ISO_NOTE_XY, 0),
        # Lines: the axis centreline, the length's extension lines down from
        # the part's lower corners, the O.D.'s out from its two corners.
        "centreline": Box(drawing.END_CENTER[0], axis_y, od_x, axis_y),
        "length rear extension": Box(rear_x, length_y, rear_x, bottom),
        "length front extension": Box(front_x, length_y, front_x, bottom),
        "O.D. upper extension": Box(front_x, top, od_x, top),
        "O.D. lower extension": Box(front_x, bottom, od_x, bottom),
        "O.D. dimension line": Box(od_x, bottom, od_x, top),
    }
    dx0, dy0, dx1, dy1 = _FINISH_INK
    for key, (pick, (sx, sy)) in drawing.FACE_FINISHES.items():
        obstacles[f"{key} finish"] = Box(sx + dx0, sy + dy0, sx + dx1, sy + dy1)
        obstacles[f"{key} finish leader"] = Box(
            min(pick[0], sx), min(pick[1], sy), max(pick[0], sx), max(pick[1], sy)
        )
    symbols: dict[str, Box] = {}
    for mark in _FRAMES:
        frame, (landing_x, landing_y) = _frame_box(mark), mark.nominal_landing
        near_x = frame.xmax if mark.outboard < 0.0 else frame.xmin
        symbols[f"{mark.key} frame"] = frame
        symbols[f"{mark.key} frame leader"] = Box(
            min(near_x, landing_x), landing_y, max(near_x, landing_x), landing_y
        )
    for name, box in symbols.items():
        for other, obstacle in obstacles.items():
            if name.endswith("leader") and other == "profile":
                continue  # a leader ends on the part's face
            assert box.gap(obstacle) >= _AIR, (name, other)
    for name, box in symbols.items():
        for other, neighbour in symbols.items():
            if name.split()[0] != other.split()[0]:
                assert box.gap(neighbour) >= _AIR, (name, other)
    template = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
    margin = 0.0127
    left, right = margin + _AIR, template.width_m - margin - _AIR
    bottom_edge, top_edge = margin + _AIR, template.height_m - margin - _AIR
    title_block = Box(
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )
    for mark in _FRAMES:
        box = _frame_box(mark)
        assert left <= box.xmin and box.xmax <= right, mark.key
        assert bottom_edge <= box.ymin and box.ymax <= top_edge, mark.key
        assert box.gap(title_block) >= _AIR, mark.key


def _circle(radius: float, z: float, *, axis_z: float = 1.0):
    return _drawing_common.ViewEdge(
        edge=object(),
        line=None,
        circle=(0.0, 0.0, z, 0.0, 0.0, axis_z, radius),
        vertices=None,
    )


def test_each_frame_finds_the_od_rim_of_its_own_face() -> None:
    """The rim is the one O.D. circle at the face's station on the spacer's
    axis, either normal sign; the other end's rim and the bore's circle at the
    same station never stand in for it, and none or two fail listing every
    circle."""
    od_r, bore_r = spec.OD / 2.0, spec.BORE_DIA / 2.0
    for mark, z, other_z in (
        (drawing.FRONT_FACE_FRAME, 0.0, spec.LENGTH),
        (drawing.REAR_FACE_FRAME, spec.LENGTH, 0.0),
    ):
        rim = _circle(od_r, z, axis_z=-1.0)
        neighbours = (
            _circle(od_r, other_z),
            _circle(bore_r, z),
            _circle(bore_r, other_z),
        )
        edges = _drawing_common.ViewEdges(label="profile", edges=(*neighbours, rim))
        assert drawing.face_rim(edges, mark) is rim
        lone = _drawing_common.ViewEdges(label="profile", edges=neighbours)
        with pytest.raises(RuntimeError, match=r"matched 0 of 3 circles: r 4\.3000"):
            drawing.face_rim(lone, mark)
        split = _drawing_common.ViewEdges(
            label="profile", edges=(rim, _circle(od_r, z))
        )
        with pytest.raises(RuntimeError, match="matched 2 of 2"):
            drawing.face_rim(split, mark)


def _surface_face(
    identity: int, parameters: tuple[float, ...], *, flipped: bool = False
):
    """A model face as ``_gtol_face_read.face_geometry`` reads it (metres)."""
    surface = SimpleNamespace(
        Identity=identity, PlaneParams=parameters, CylinderParams=parameters
    )
    return SimpleNamespace(
        GetSurface=lambda: surface,
        FaceInSurfaceSense=lambda: flipped,
        GetBox=lambda: (),
    )


def _plane(z_mm: float, *, facing: float):
    """The plane square to the spacer axis at ``z_mm``, facing +Z or -Z."""
    return _surface_face(
        _gtol_face.SURFACE_PLANE,
        (0.0, 0.0, 1.0, 0.0, 0.0, z_mm / 1000.0),
        flipped=facing < 0.0,
    )


def _od_cylinder():
    return _surface_face(
        _gtol_face.SURFACE_CYLINDER,
        (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, spec.OD / 2000.0),
    )


def _rim_between(*faces):
    edge = SimpleNamespace(GetTwoAdjacentFaces2=lambda: faces)
    return _drawing_common.ViewEdge(edge=edge, line=None, circle=None, vertices=None)


@pytest.mark.parametrize("plane_first", [False, True])
def test_each_frame_attaches_to_its_end_face_never_the_od(plane_first: bool) -> None:
    """Of its rim's two faces, the front frame takes the front face (z 0,
    facing -Z) and the rear frame the rear face (z LENGTH, facing +Z),
    whichever the rim reports first; the O.D., the other end, or a plane
    facing the other way never stands in, and two such planes or a lone face
    fail."""
    for mark, z, facing in (
        (drawing.FRONT_FACE_FRAME, 0.0, -1.0),
        (drawing.REAR_FACE_FRAME, spec.LENGTH, 1.0),
    ):
        plane, cylinder = _plane(z, facing=facing), _od_cylinder()
        pair = (plane, cylinder) if plane_first else (cylinder, plane)
        assert drawing.controlled_face(_rim_between(*pair), mark) is plane
        for wrong in (
            _plane(z, facing=-facing),
            _plane(spec.LENGTH - z, facing=-facing),
        ):
            with pytest.raises(RuntimeError, match="matched 0 of 2 faces"):
                drawing.controlled_face(_rim_between(_od_cylinder(), wrong), mark)
        twin = _plane(z, facing=facing)
        with pytest.raises(RuntimeError, match="matched 2 of 2 faces"):
            drawing.controlled_face(_rim_between(plane, twin), mark)
        with pytest.raises(RuntimeError, match="matched 1 of 1 faces"):
            drawing.controlled_face(_rim_between(None, plane), mark)


@pytest.mark.parametrize("turn", [1.0, -1.0])
def test_face_landing_puts_the_leader_at_its_model_x_on_the_projected_line(
    turn: float,
) -> None:
    """The landing sits at the mark's model x between the rim's projected -X
    and +X ends, whichever way the view turns them."""
    axis_y = drawing.PROFILE_CENTER[1]
    r = spec.OD / 2.0 * _S
    for mark in _FRAMES:
        minus_end = (0.19, axis_y - turn * r)
        plus_end = (0.19, axis_y + turn * r)
        assert drawing.face_landing(mark, minus_end, plus_end) == pytest.approx(
            (0.19, axis_y + turn * mark.landing_x_mm * _S)
        )


def test_turned_part_diameters_follow_the_machinist() -> None:
    # Rule 7: the O.D. is moved onto the lathe profile; the bore, a solid
    # circle only end-on, keeps the end view.
    assert set(drawing.PROFILE_KEEP) == {"RingLength"}
    assert set(drawing.END_KEEP) == {"BoreDia", "RingOd"}
    profile_right = drawing.PROFILE_CENTER[0] + spec.LENGTH * drawing._S / 2.0
    assert drawing.OD_ON_PROFILE[0] > profile_right
    assert drawing.OD_ON_PROFILE[1] == drawing.PROFILE_CENTER[1]
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE {}:{}".format(
        *spec.ISOMETRIC_VIEW_SCALE
    )


def test_the_bore_callout_names_ream_for_the_shoulder_press() -> None:
    """The bore is a light press on the MHA-VN-041 shoulder: a fit bore, so it
    is reamed (rule 7) and its one-sided band holds the press; its callout
    rides the end-view diameter, the hole's defining view."""
    drilled_growth = _config.title_block("drilled_hole")["plus_mm"]
    # The press band is tighter than a drill's oversize: only a reamer holds it.
    assert 0.0 < max(spec.BORE_DIA_BAND) < drilled_growth
    assert set(drawing.DIMENSION_CALLOUTS) == {"BoreDia"} <= set(drawing.END_KEEP)
    assert drawing.DIMENSION_CALLOUTS["BoreDia"].split()[0] == "REAM"


def test_registry_row_is_the_turned_brass_mha_167() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-020"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"
    assert "fit_class" not in row


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    """The drawing refuses a source part missing a required property; every
    one must be carried and non-blank, and the notes the sheet links are the
    spec's."""
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
    assert [ast.unparse(a) for a in stamp.args[:2]] == ["adapter", "PART_NAME"]
    extra = {
        ast.literal_eval(key): getattr(part, value.id)
        for key, value in zip(stamp.args[2].keys, stamp.args[2].values, strict=True)
    }
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME, extra)
    carried.update(stamped)
    assert [name for name in required if not str(carried.get(name) or "").strip()] == []
    assert carried["Manufacturing Notes"] == spec.DRAWING_NOTES
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
    assert set(part._SAVED_DRAWING_PROPERTIES) <= set(required)
