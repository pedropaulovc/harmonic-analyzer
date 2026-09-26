"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import rocker_arm_notes
import rocker_arm_spec
import draw_rocker_arm as drawing
import build_rocker_arm as arm
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DRAWINGS_BY_NAME
from cone_pivot_post_installation import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        rocker_arm_spec.ROD_HOLE_X,
        rocker_arm_spec.TOP_END_Y,
    )
    assert rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert arm.ROD_HOLE_SPEC is rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = rocker_arm_notes.DRAWING_NOTES
    assert "R800" in notes
    assert "R816" in notes
    # The rod hole rides its native Ø1.99 THRU ALL callout; the notes state
    # count and process only, never a second copy of a sheet dimension.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "REAM +0.03/0" in notes
    assert "16.00 REF" in notes
    assert "11.5 IN" not in notes
    assert "0.22 IN" not in notes
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert re.search(
        r'add_property_linked_note\(\s*adapter, "Manufacturing Notes"', source
    )


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = pivot bore axis, B = broad face (right end view), C = rod-side tip
    # face; the rod-pin position frame references all three.
    assert source.count("add_datum_feature(") == 3
    # Datum A's leader runs oblique, 45 deg off both centre-mark axes.
    assert math.degrees(drawing.PIVOT_DATUM_ANGLE) % 90.0 == pytest.approx(45.0)
    assert 'label="pivot bore cylindrical datum feature"' in source
    assert source.count("shoulder=True") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B", "C")' in source
    assert 'characteristic="position"' in source
    assert "add_surface_finish(" in source
    assert "add_native_hole_callout(" in source
    # r743-p1s-B: both rod-pin annotations take the diameter-picked edge.
    assert "edge_xy=rod_rim" not in source
    assert source.count("edge=rod_hole_edge") == 1
    assert source.count("edge_entity=rod_hole_edge") == 1


def test_large_radius_values_are_note_only() -> None:
    assert drawing.NOTE_ONLY_DIMENSIONS == {"TopRadius", "BottomRadius"}
    assert "R800" in rocker_arm_notes.DRAWING_NOTES
    assert "R816" in rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == rocker_arm_spec.PIVOT_HOLE_DIA
    part_source = "".join(Path(arm.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bore")' in sheet_source
    )
    assert "roughness_ra=" not in sheet_source


def test_every_view_keep_map_is_curated_on_its_own_view() -> None:
    """Codex #936 (PRRT_kwDOPHDy386mRk__): RIGHT_KEEP promised HubLength but
    build() curated only the front view, so the hub length never printed. Each
    non-empty <VIEW>_KEEP must be curated on that view, and curation fails
    loud on a missing kept dimension, so the print carries every one."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    curated = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "curate_view_dimensions"
        ):
            continue
        keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
        curated[keywords["keep"]] = (ast.unparse(node.args[1]), keywords)
    for keep_name, view in (
        ("FRONT_KEEP", "front"),
        ("RIGHT_KEEP", "right"),
        ("TOP_KEEP", "top"),
    ):
        if not getattr(drawing, keep_name):
            continue
        assert keep_name in curated, keep_name
        assert curated[keep_name][0] == view
    # The end view imports by feature: only Hub's dimensions arrive there.
    assert curated["RIGHT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_one_sided_band() -> None:
    """#743 PR2: the hubs are a solid stack whose north end is the rocker
    bank's datum, so each hub may only come out long and the print says so
    natively; rocker_bank_layout's L20 acceptance caps the sum."""
    from _drawing_contract import model_toleranced_dimensions

    assert rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == (
        "*deviations(HUB_LENGTH_BAND)"
    )
    assert rocker_arm_spec.HUB_LENGTH_BAND == (0.05, 0.0)
    assert f"{rocker_arm_spec.HUB_LENGTH:.2f}" not in rocker_arm_notes.DRAWING_NOTES


def test_datum_a_is_the_pivot_bore_picked_by_its_diameter() -> None:
    """r743-4D: the rim-coordinate pick put datum A's triangle on the O10 hub
    circle, which changes what the A-B-C frame controls. Datum A must attach
    to the edge picked by the pivot bore's diameter."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    picks = {
        node.targets[0].id: ast.unparse(node.value.args[2])
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", "") == "visible_circle_edge"
    }
    datums = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "add_datum_feature":
            keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
            datums[keywords["datum"].strip("'\"")] = keywords
    edge = datums["A"].get("edge_entity")
    assert edge is not None and "edge_xy" not in datums["A"]
    assert picks[edge] == "PIVOT_HOLE_DIA"
    assert rocker_arm_spec.PIVOT_HOLE_DIA < rocker_arm_spec.HUB_DIA


def _datum_readback(radius_m: float, bearing_deg: float) -> tuple[float, float]:
    centre = drawing._sheet_xy(0.0, rocker_arm_spec.PIVOT_MID_Y)
    bearing = math.radians(bearing_deg)
    return (
        centre[0] + radius_m * math.cos(bearing),
        centre[1] + radius_m * math.sin(bearing),
    )


_PIVOT_CENTRE = drawing._sheet_xy(0.0, rocker_arm_spec.PIVOT_MID_Y)
_TRIANGLE_M = 0.00209 - drawing.PIVOT_BORE_SHEET_R  # r743-3C: rim to readback


def test_datum_a_on_the_bore_passes() -> None:
    """r743-3C's readback: 2.09 mm from the pivot at 135.4 deg, the bore rim
    plus the triangle on the requested ray."""
    drawing._require_pivot_datum_on_bore(_datum_readback(0.00209, 135.4), _PIVOT_CENTRE)
    drawing._require_pivot_datum_on_bore(
        _datum_readback(drawing.PIVOT_BORE_SHEET_R, 135.0), _PIVOT_CENTRE
    )


def test_datum_a_on_the_hub_fails() -> None:
    hub_readback = drawing.PIVOT_HUB_SHEET_R + _TRIANGLE_M
    with pytest.raises(RuntimeError, match="hub rim"):
        drawing._require_pivot_datum_on_bore(
            _datum_readback(hub_readback, 135.0), _PIVOT_CENTRE
        )
    # Even a bare hub-rim readback, with no triangle, is not the bore.
    with pytest.raises(RuntimeError, match="hub rim"):
        drawing._require_pivot_datum_on_bore(
            _datum_readback(drawing.PIVOT_HUB_SHEET_R, 135.0), _PIVOT_CENTRE
        )


def test_datum_a_off_its_ray_fails() -> None:
    # On the horizontal centre-mark axis: the leader no longer reads oblique.
    with pytest.raises(RuntimeError, match="swung"):
        drawing._require_pivot_datum_on_bore(_datum_readback(0.00209, 180.0), _PIVOT_CENTRE)
    with pytest.raises(RuntimeError, match="swung"):
        drawing._require_pivot_datum_on_bore(_datum_readback(0.00209, 315.0), _PIVOT_CENTRE)


def test_datum_a_read_at_the_tag_or_inside_the_bore_fails() -> None:
    """A leaderless tag reads at the tag, a stand-off out; neither it nor a
    point inside the bore is a leader end on the bore."""
    tag = drawing.PIVOT_BORE_SHEET_R + drawing.PIVOT_DATUM_STANDOFF
    with pytest.raises(RuntimeError, match="hub rim"):
        drawing._require_pivot_datum_on_bore(_datum_readback(tag, 135.0), _PIVOT_CENTRE)
    with pytest.raises(RuntimeError, match="bore rim"):
        drawing._require_pivot_datum_on_bore(
            _datum_readback(drawing.PIVOT_BORE_SHEET_R / 2.0, 135.0), _PIVOT_CENTRE
        )


def test_datum_a_gross_bound_is_the_request_to_centre_distance() -> None:
    """add_datum_feature's own bound only guards against an ignored move: a
    bore readback anywhere in the checked sector is nearer the request than
    the pivot centre is, and the default drop (40 mm+) is not."""
    reach = drawing.PIVOT_BORE_SHEET_R + drawing.PIVOT_DATUM_STANDOFF
    request = _datum_readback(reach, 135.0)
    worst = max(
        math.dist(request, _datum_readback(radius, 135.0 + sign * swing))
        for radius in (drawing.PIVOT_BORE_SHEET_R, drawing.PIVOT_HUB_SHEET_R)
        for sign in (-1.0, 1.0)
        for swing in (math.degrees(drawing.PIVOT_DATUM_BEARING_TOLERANCE),)
    )
    assert worst <= drawing.PIVOT_DATUM_POSITION_TOLERANCE
    assert drawing.PIVOT_DATUM_POSITION_TOLERANCE == pytest.approx(reach)


def test_pivot_diameter_text_is_clear_of_the_rod_pin_x_dimension() -> None:
    """r743-4D: the O6.50 leader, from text straight below the bore, crossed
    the rod-pin X location dimension. Its text now sits left of that
    dimension's span (pivot to rod-pin hole) and below the strap."""
    text_x, text_y = drawing.FRONT_KEEP["PivotDia"]
    pivot_x, pivot_y = drawing._sheet_xy(0.0, rocker_arm_spec.PIVOT_MID_Y)
    # Diameter text runs ~2.6 mm a character from its anchor: "O6.50" is 5.
    assert text_x + 5 * 0.0026 < pivot_x - rocker_arm_spec.HUB_DIA / 2000.0
    assert text_y < pivot_y - rocker_arm_spec.ARM_DEPTH / 2000.0
    # Above the notes band.
    assert text_y > drawing.NOTES_CEILING + 0.010


def test_both_bores_are_picked_by_diameter_not_by_a_rim_coordinate() -> None:
    """r743-p1s-B: a coordinate pick on the #47 rod-hole rim resolved to the
    strap's tapered end-face line, so AddHoleCallout2 returned None. Every
    annotation on the rod-pin hole takes the diameter-picked edge."""
    import ast

    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    picks = {}
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (
                isinstance(call.func, ast.Name)
                and call.func.id == "visible_circle_edge"
            ):
                picks[node.targets[0].id] = ast.unparse(call.args[2])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keywords = {k.arg: ast.unparse(k.value) for k in node.keywords}
            if keywords.get("label", "").startswith("'rod-pin") or keywords.get(
                "label", ""
            ).startswith('"rod-pin'):
                if node.func.id != "set_basic_dimension":
                    uses.append((node.func.id, keywords))
    assert picks == {
        "rod_hole_edge": "_ROD_HOLE_DIA",
        "pivot_bore_edge": "PIVOT_HOLE_DIA",
    }
    kinds = {name for name, _ in uses}
    assert kinds == {
        "add_native_hole_callout",
        "add_edge_dimension",
        "add_feature_control_frame",
    }
    for name, keywords in uses:
        assert "edge_xy" not in keywords, name
        if name == "add_native_hole_callout":
            assert keywords["edge"] == "rod_hole_edge"
        elif name == "add_edge_dimension":
            assert keywords["entities"] == "(pivot_bore_edge, rod_hole_edge)"
        else:
            assert keywords["edge_entity"] == "rod_hole_edge"


# Measured on the r743-p1s-B2 render (5100x3300 px on 431.8x279.4 mm): the
# drawable region ends 12.7 mm above the sheet's bottom edge, the linked
# notes pitch ~4.14 mm a line, and the iso caption runs ~2.5 mm a character.
BORDER_BOTTOM = 0.0127
NOTE_LINE_PITCH = 0.0042
CAPTION_CHAR_WIDTH = 0.0026
RIGHT_BORDER = 0.415
DRAWABLE = DrawableRegion(0.0127, BORDER_BOTTOM, 0.4191, 0.2667)


class _FakeAnnotation:
    def __init__(self, position: tuple[float, float]) -> None:
        self.position = position

    def GetPosition(self) -> tuple[float, float, float]:
        return (*self.position, 0.0)

    def SetPosition(self, x: float, y: float, _z: float) -> bool:
        self.position = (x, y)
        return True


class _FakeNote:
    """A top-left-anchored text block whose box sits off its insertion point
    and follows a move only ``tracking`` of the way, as SolidWorks' does."""

    def __init__(
        self, anchor: tuple[float, float], height: float, tracking: float = 1.0
    ) -> None:
        self.annotation = _FakeAnnotation(anchor)
        self.anchor = anchor
        self.height = height
        self.tracking = tracking

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y = (
            a + (p - a) * self.tracking
            for a, p in zip(self.anchor, self.annotation.position)
        )
        x0, y1 = x + 0.0008, y - 0.0011
        return (x0, y1 - self.height, 0.0, x0 + 0.180, y1, 0.0)


def _seat(monkeypatch: pytest.MonkeyPatch, note: _FakeNote) -> tuple[float, ...]:
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        drawing, "sheet_drawable_region", lambda *_args, **_kwargs: DRAWABLE
    )
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    return drawing._seat_notes_on_border(adapter, note, sheet=object())


@pytest.mark.parametrize("tracking", [1.0, 0.8])
def test_general_notes_bottom_is_seated_inside_the_frame(
    monkeypatch: pytest.MonkeyPatch, tracking: float
) -> None:
    """r743-p1s-B2: anchored by its top at 0.082, the 18-line block ran two
    lines past the bottom border. Seated from its measured extent, its bottom
    lands on the drawable region's clearance line and its left on NOTES_LEFT,
    whatever the insertion point's offset from the rendered box."""
    lines = len(rocker_arm_notes.DRAWING_NOTES.splitlines())
    note = _FakeNote(
        (drawing.NOTES_LEFT, drawing.NOTES_CEILING),
        lines * NOTE_LINE_PITCH,
        tracking,
    )
    x0, y0, _x1, y1 = _seat(monkeypatch, note)
    assert y0 >= DRAWABLE.ymin
    assert y0 == pytest.approx(
        DRAWABLE.ymin + drawing.NOTES_BORDER_CLEARANCE,
        abs=0.0005,
    )
    assert x0 == pytest.approx(drawing.NOTES_LEFT, abs=0.0005)
    assert y1 < drawing.NOTES_CEILING
    # The old top anchor: the same block reached below the border.
    assert 0.082 - lines * NOTE_LINE_PITCH < BORDER_BOTTOM


def test_general_notes_too_tall_for_the_band_fail_the_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), band + 0.002)
    with pytest.raises(RuntimeError, match="do not fit"):
        _seat(monkeypatch, note)


def test_an_unresolved_notes_link_fails_instead_of_seating_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extent of an unresolved property link is one line of token text;
    seating that box would put the real block's bottom through the border."""
    note = _FakeNote((drawing.NOTES_LEFT, drawing.NOTES_CEILING), NOTE_LINE_PITCH)
    with pytest.raises(RuntimeError, match="has not resolved"):
        _seat(monkeypatch, note)


def test_iso_caption_sits_under_the_iso_clear_of_the_frame_and_end_view() -> None:
    caption = rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    fcf_bottom = drawing.FCF_XY[1] - 0.007
    assert top < fcf_bottom - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right


def test_pivot_finish_leader_runs_down_left_from_a_symbol_above_the_strap() -> None:
    """r743-p1s-B2: the default-height Ra 1.6 sat across the strap and the
    centre mark, its leader running up through the symbol. The body draws
    up-right of its leader end, so the symbol sits up-right of its rim point,
    clear of the hub and above the strap's top edge, at note text height."""
    rim, symbol = drawing._pivot_finish_placement()
    centre = drawing._sheet_xy(0.0, rocker_arm_spec.PIVOT_MID_Y)
    scale = drawing._S / 1000.0
    assert math.dist(rim, centre) == pytest.approx(
        rocker_arm_spec.PIVOT_HOLE_DIA / 2.0 * scale
    )
    # Oblique to both centre-mark axes.
    assert abs(rim[0] - centre[0]) > 0.0005 and abs(rim[1] - centre[1]) > 0.0005
    assert symbol[0] > rim[0] and symbol[1] > rim[1]
    assert math.dist(symbol, centre) > rocker_arm_spec.HUB_DIA / 2.0 * scale + 0.005
    model_x = (symbol[0] - drawing.FRONT_CENTER[0]) / scale
    strap_top = drawing._sheet_xy(
        model_x,
        rocker_arm_spec.CENTER_Y
        - math.sqrt(rocker_arm_spec.R_TOP**2 - model_x**2),
    )[1]
    assert symbol[1] > strap_top + drawing.PIVOT_FINISH_CHAR_HEIGHT
    assert drawing.PIVOT_FINISH_CHAR_HEIGHT <= 0.0025
