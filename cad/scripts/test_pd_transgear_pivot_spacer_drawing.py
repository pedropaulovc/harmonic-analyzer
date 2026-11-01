"""Offline contracts for the transgear pivot spacer (MHA-PD-20) and its drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import _config
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm, printed_band_mm
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
import _drawing_edges
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
import _gtol_face
from _layout_geometry import Box, estimate_text_box
from _surface_finish import MACHINED_UM, SEAT_UM
import build_pd_transgear_pivot_spacer as part
import draw_pd_transgear_pivot_spacer as drawing
import pd_transgear_pivot_spacer_spec as spec
import _mcmaster_90325a174 as screw


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
    # The length (on the .001 grid) and the bore hold their own bands; the
    # O.D., an outside profile no stack reads, takes the loosest row (.XX).
    assert spec.DRAWING_PRECISION_BY_NAME == {"RingOd": 2, "BoreDia": 4, "RingLength": 3}


def test_the_length_and_the_bore_carry_their_bands_on_the_model() -> None:
    """The MHA-PD-VN-63 spring's room rides the length and the shoulder press the
    bore, so each band is a native model tolerance from the spec (policy
    drawing-simplicity-policy.md `How the repository implements the guidelines`).  The O.D. prints at .X and the title block's row governs it;
    restating that row on the dimension is what drawing-guidelines.md rule 2 (the title block is the general specification) forbids."""
    assert model_toleranced_dimensions(part) == {
        ("Ring", "RingLength"): "LENGTH_TOLERANCE",
        ("RingProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
    }
    row = printed_band_mm(3, unit=spec.UNIT)
    assert 0.0 < spec.LENGTH_TOLERANCE <= spec.LENGTH_BAND < row
    # The ream only cuts oversize: the bore never prints under nominal.
    assert 0.0 < min(spec.BORE_DIA_BAND) < max(spec.BORE_DIA_BAND) < row
    assert (spec.BORE_DIA_MIN, spec.BORE_DIA_MAX) == pytest.approx((4.7117, 4.7244))


def test_the_bore_holds_a_light_press_on_the_shoulder_at_every_limit() -> None:
    """The ring is pressed flush on the MHA-PD-VN-57 shoulder (Ø4.7625 -0.0254/0)
    so screw and spacer seat on the bar as one body: the smallest shoulder in
    the largest ream still grips, and the largest in the smallest stays
    light."""
    shoulder_min = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[0]
    shoulder_max = screw.SHOULDER_DIA + screw.SHOULDER_DIA_LIMITS[1]
    loosest = shoulder_min - spec.BORE_DIA_MAX
    tightest = shoulder_max - spec.BORE_DIA_MIN
    assert spec.PRESS_INTERFERENCE == pytest.approx((loosest, tightest))
    assert (loosest, tightest) == pytest.approx((0.0127, 0.0508), abs=1e-6)
    assert 0.0 < loosest < tightest


def test_wall_holds_the_target_at_the_full_worst_case() -> None:
    """Rule 17 with every allowance the shop sees: the O.D. at its .XX row's
    low limit, the bore at its largest ream offset from the O.D. by half the
    printed O.D. runout to A, and the title block's larger permitted break
    (radius or chamfer) on both rims of an end face.  One chucking, so no
    run-off."""
    row = printed_band_mm(2, unit=spec.UNIT)
    setback = max(edge_break_radius_mm(unit=spec.UNIT), edge_break_chamfer_mm(unit=spec.UNIT))
    assert spec.OD_BAND == pytest.approx(row)
    assert spec.EDGE_BREAK == pytest.approx(setback)
    # Runout's full indicator movement is twice the axes' offset.
    assert spec.OD_RUNOUT == pytest.approx(0.016 * 25.4)
    assert spec.BORE_ECCENTRICITY == pytest.approx(spec.OD_RUNOUT / 2.0)
    worst = (
        (spec.OD - row - spec.BORE_DIA_MAX) / 2.0
        - spec.OD_RUNOUT / 2.0
        - 2.0 * setback
    )
    assert spec.WALL_WORST == pytest.approx(worst) == pytest.approx(2.3876)
    assert spec.WALL_WORST >= spec.WALL_TARGET == WALL_TARGET_MM


def test_a_larger_permitted_radius_break_charges_the_wall(monkeypatch) -> None:
    """The wall charges whichever permitted break sets back further: an R.020
    break with the .010 chamfer kept leaves 2.3876 - 2 x 0.254 < 2.032, so
    the spec refuses rather than missing the radius."""
    import importlib.util

    real = _config.title_block

    def title_block(key, *, unit="mm"):
        row = real(key, unit=unit)
        return {**row, "radius_in": 0.020} if key == "edge_break" and unit == "in" else row

    monkeypatch.setattr(_config, "title_block", title_block)
    # Execute a private copy: reloading the shared module would rebind its
    # band tuples, and test_fit_bands matches consumers to bands by id().
    probe_spec = importlib.util.spec_from_file_location(
        "_pivot_spacer_spec_probe", spec.__file__
    )
    probe = importlib.util.module_from_spec(probe_spec)
    with pytest.raises(AssertionError, match=r"MHA-PD-20 wall 1\.880 < the 2\.032"):
        probe_spec.loader.exec_module(probe)
    assert spec.EDGE_BREAK == pytest.approx(0.254)


def test_the_sheet_states_no_shortfall_and_no_facing_step() -> None:
    """The wall holds the target, so no WALL MIN line; R9-6: fitted as made,
    never faced.  The sheet carries no general notes at all."""
    assert not hasattr(spec, "DRAWING_NOTES")
    assert not hasattr(spec, "WALL_NOTE")
    assert "Manufacturing Notes" not in part._SAVED_DRAWING_PROPERTIES


def test_the_arm_runs_on_the_rear_face_and_the_front_face_seats_on_the_bar() -> None:
    """Rule 6: the arm swings on the shoulder against the rear face, which
    runs (Ra 1.6, labelled BEARING FACE); the front face is the one static
    seat on the bar (Ra 3.2).  The pressed bore carries no symbol."""
    controls = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(controls) == {"front_face", "rear_face"}
    front, rear = controls["front_face"].face, controls["rear_face"].face
    assert controls["front_face"].roughness_um == SEAT_UM
    assert controls["front_face"].production_method == ""
    assert controls["rear_face"].roughness_um == MACHINED_UM
    assert controls["rear_face"].production_method == "BEARING FACE"
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
    assert spec.GEOMETRIC_TOLERANCES_IN == {
        "rear face perpendicularity to bore": ".0004",
        "front face perpendicularity to bore": ".0004",
        "o.d. circular runout to bore": ".016",
    }
    assert spec.REAR_FACE_PERPENDICULARITY == pytest.approx(0.0004 * 25.4)
    assert spec.FRONT_FACE_PERPENDICULARITY == pytest.approx(0.0004 * 25.4)
    # The arm seats on the face's flat inside the O.D. rim's break.
    assert spec.FACE_PERPENDICULARITY_ZONE_DIA == pytest.approx(
        spec.OD - spec.OD_BAND - 2.0 * spec.EDGE_BREAK
    )
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


# A dimension's text block with its callout rows, as farm run
# 20261027T121009040Z-eda67c82 printed them (layout-audit text runs): the
# block centres near the annotation position SetPosition2 takes (the
# length's rows on 0.2445, 0.1205 against its 0.2445, 0.1215; the bore's on
# 0.0500, 0.2215 against 0.050, 0.222), so each box grows by 1.5 of anchor
# slip; its rows stand 5.55 apart at 3.5 text, and the widest row's advance
# reaches 0.80 of the cap height ("MHA-PD-VN-57 SHOULDER" ran 58.6 wide).
# The bore's stacked +0.008 is one more row on top.
_ROW_PITCH = 0.00555 / _CAP_M
_CALLOUT_ADVANCE = 0.80
_ANCHOR_SLIP = 0.0015


def _callout_block(text: str, anchor: tuple[float, float]) -> Box:
    box = estimate_text_box(
        text,
        anchor=anchor,
        height=_CAP_M,
        reference=2,
        advance_ratio=_CALLOUT_ADVANCE,
        line_spacing=_ROW_PITCH,
    )
    assert box is not None
    return Box(
        box.xmin - _ANCHOR_SLIP,
        box.ymin - _ANCHOR_SLIP,
        box.xmax + _ANCHOR_SLIP,
        box.ymax + _ANCHOR_SLIP,
    )


def _length_text_box() -> Box:
    return _callout_block(
        f"{spec.LENGTH:.3f} ±{spec.LENGTH_BAND:.2f}\n"
        f"{drawing.DIMENSION_CALLOUTS['RingLength']}",
        drawing.LENGTH_TEXT_XY,
    )


def _bore_text_box() -> Box:
    return _callout_block(
        f"+{max(spec.BORE_DIA_BAND):.3f}\n"
        f"\u00d8{spec.BORE_DIA:.3f} {min(spec.BORE_DIA_BAND):.3f}\n"
        f"{drawing.DIMENSION_CALLOUTS['BoreDia']}",
        drawing.END_KEEP["BoreDia"],
    )


def test_both_frames_stand_inside_the_sheet_clear_of_every_annotation() -> None:
    """All three frames and their leaders keep 2 mm of air from every other
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
        "length text": _length_text_box(),
        "length dimension line": Box(rear_x, length_y, drawing.LENGTH_TEXT_XY[0], length_y),
        "O.D. text": _text_box(
            f"\u00d8{spec.OD:.{spec.OD_PLACES}f}", drawing.OD_ON_PROFILE, 2
        ),
        "bore text": _bore_text_box(),
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
    # The O.D.'s runout frame above the profile, its leader down to the upper
    # O.D. line (the leader leaves the frame's left side at mid-height).
    rx, ry = drawing.OD_RUNOUT_FRAME
    runout = Box(rx, ry - drawing.FRAME_HEIGHT, rx + drawing.FRAME_WIDTH, ry)
    landing_x = drawing._profile_x(drawing.OD_RUNOUT_LANDING_Z_MM)
    assert rear_x < landing_x < front_x
    symbols["runout frame"] = runout
    symbols["runout frame leader"] = Box(
        min(rx, landing_x), top, max(rx, landing_x), ry - drawing.FRAME_HEIGHT / 2.0
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
    for key, box in (
        *((mark.key, _frame_box(mark)) for mark in _FRAMES),
        ("runout", runout),
    ):
        assert left <= box.xmin and box.xmax <= right, key
        assert bottom_edge <= box.ymin and box.ymax <= top_edge, key
        assert box.gap(title_block) >= _AIR, key


def _circle(radius: float, z: float, *, axis_z: float = 1.0):
    return _drawing_edges.ViewEdge(
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
        edges = _drawing_edges.ViewEdges(label="profile", edges=(*neighbours, rim))
        assert drawing.face_rim(edges, mark) is rim
        lone = _drawing_edges.ViewEdges(label="profile", edges=neighbours)
        with pytest.raises(RuntimeError, match=rf"matched 0 of 3 circles: r {re.escape(f'{od_r:.4f}')}"):
            drawing.face_rim(lone, mark)
        split = _drawing_edges.ViewEdges(
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
    return _drawing_edges.ViewEdge(edge=edge, line=None, circle=None, vertices=None)


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
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): the O.D. is moved onto the lathe profile; the bore, a solid
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
    """The bore is a light press on the MHA-PD-VN-57 shoulder: a fit bore, so it
    is reamed (drawing-guidelines.md rule 12 (hole and slot callouts say what to do)) and its one-sided band holds the press; its callout
    rides the end-view diameter, the hole's defining view, and names the
    shoulder and the interference both limits produce (rule 4)."""
    drilled_growth = _config.title_block("drilled_hole")["plus_mm"]
    # The press band is tighter than a drill's oversize: only a reamer holds it.
    assert 0.0 < max(spec.BORE_DIA_BAND) < drilled_growth
    assert set(drawing.DIMENSION_CALLOUTS) == {"BoreDia", "RingLength"}
    assert "BoreDia" in drawing.END_KEEP and "RingLength" in drawing.PROFILE_KEEP
    bore = " ".join(drawing.DIMENSION_CALLOUTS["BoreDia"].split())
    # Process, fit and mate (rule 4), not their wording or wrapping.
    assert bore.startswith("REAM THRU")
    assert "DIAMETRAL INTERFERENCE" in bore
    screw = _config.parts("pd-vn-transgear-pivot-screw")["number"]
    # The mating feature is the screw's shoulder, not its thread.
    assert re.search(rf"{re.escape(screw)}\s+SHOULDER\b", bore)
    assert "THREAD" not in bore
    # The printed window encloses the spec's press at both limits; a sign
    # before either limit is never read as its magnitude.
    (window,) = re.findall(r"(?<![-+\d.])(\d*\.\d+)-(\d*\.\d+)", bore)
    low, high = (float(v) * 25.4 for v in window)
    assert 0.0 < low <= spec.PRESS_INTERFERENCE[0] < spec.PRESS_INTERFERENCE[1] <= high
    assert high - spec.PRESS_INTERFERENCE[1] < 0.00254
    assert spec.PRESS_INTERFERENCE[0] - low < 0.00254


def test_the_length_band_names_the_spring_room_it_sets() -> None:
    """Rule 4: a width that sets a stack names the stack.  The ±0.05 length
    sets the MHA-PD-VN-63 spring's room (transgear_hanger_joints)."""
    callout = " ".join(drawing.DIMENSION_CALLOUTS["RingLength"].split())
    assert _config.parts("pd-vn-transgear-pivot-spring")["number"] in callout
    assert "SPRING ROOM" in callout


# The rows run 20261027T121009040Z-eda67c82 printed (layout audit: each
# row's lower-left anchor, plus its width and the 3.5 cap), with the text
# and SetPosition2 anchor that produced them.
_PRINTED_BLOCKS = (
    (
        "5.000 ±0.05\nSETS MHA-PD-VN-63\nSPRING ROOM",
        (0.2445, 0.1215),
        (0.2224, 0.1132, 0.2665, 0.1278),
    ),
    (
        "+0.008\nØ4.727 0.000\nREAM THRU\n0.002-0.036 DIAMETRAL\n"
        "INTERFERENCE ON\nMHA-PD-VN-57 SHOULDER",
        (0.050, 0.222),
        (0.0207, 0.2064, 0.0793, 0.2366),
    ),
)


def test_callout_block_model_encloses_the_rows_the_farm_printed() -> None:
    """The calibration behind _callout_block, on the text and anchors the
    farm printed, independent of where the sheet places them now."""
    for text, anchor, (xmin, ymin, xmax, ymax) in _PRINTED_BLOCKS:
        box = _callout_block(text, anchor)
        assert box.xmin <= xmin and xmax <= box.xmax
        assert box.ymin <= ymin and ymax <= box.ymax


def test_offset_length_text_clears_every_extension_line() -> None:
    """Review 2026-10-23 (clarity): the length's text filled the 25 between
    its extension lines.  Offset right of the front face's extension line, it
    keeps 2 mm of air from both length extension lines, the O.D.'s lower
    extension line and dimension line, and the front face's finish."""
    rear_x, front_x = _sheet_point(0.0, spec.LENGTH)[0], _sheet_point(0.0, 0.0)[0]
    bottom = drawing.PROFILE_CENTER[1] - spec.OD / 2.0 * _S
    top = drawing.PROFILE_CENTER[1] + spec.OD / 2.0 * _S
    length_y = drawing.PROFILE_KEEP["RingLength"][1]
    od_x = drawing.OD_ON_PROFILE[0]
    text = _length_text_box()
    sx, sy = drawing.FACE_FINISHES["front_face"][1]
    dx0, dy0, dx1, dy1 = _FINISH_INK
    for name, line in {
        "rear extension": Box(rear_x, length_y, rear_x, bottom),
        "front extension": Box(front_x, length_y, front_x, bottom),
        "O.D. lower extension": Box(front_x, bottom, od_x, bottom),
        "O.D. dimension line": Box(od_x, bottom, od_x, top),
        "front finish": Box(sx + dx0, sy + dy0, sx + dx1, sy + dy1),
    }.items():
        assert text.gap(line) >= _AIR, name
    assert text.xmin > front_x


def test_bore_callout_clears_the_end_view() -> None:
    end_r = spec.OD / 2.0 * _S
    circle = Box(
        drawing.END_CENTER[0] - end_r,
        drawing.END_CENTER[1] - end_r,
        drawing.END_CENTER[0] + end_r,
        drawing.END_CENTER[1] + end_r,
    )
    assert _bore_text_box().gap(circle) >= _AIR


# Datum tag box as run 20261027T131303762Z-7567dd7c printed it: 3.2 x 3.4 of
# text in a ~7 mm square frame.
_DATUM_TAG = 0.007


def test_datum_a_tag_stands_off_the_od_and_the_bore_callout() -> None:
    """The native drop put datum A's tag on the Ø11.0 outline (text-on-line).
    The placed tag stands outside the O.D. circle with air, whichever corner
    of the tag SolidWorks anchors at the requested point, and clear of the
    bore callout and the vertical centreline."""
    cx, cy = drawing.END_CENTER
    od_r = spec.OD / 2.0 * _S
    x, y = drawing.DATUM_A_SYMBOL
    for dx in (-_DATUM_TAG, 0.0):
        for dy in (-_DATUM_TAG, 0.0):
            tag = Box(x + dx, y + dy, x + dx + _DATUM_TAG, y + dy + _DATUM_TAG)
            nearest = (
                min(max(cx, tag.xmin), tag.xmax),
                min(max(cy, tag.ymin), tag.ymax),
            )
            assert math.dist(nearest, (cx, cy)) >= od_r + _AIR
            assert tag.gap(_bore_text_box()) >= _AIR
            assert tag.xmax <= cx - _AIR


def test_registry_row_is_the_turned_brass_mha_167() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-20"
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
    assert carried["Isometric View Note"] == spec.ISOMETRIC_VIEW_NOTE
    assert set(part._SAVED_DRAWING_PROPERTIES) <= set(required)
