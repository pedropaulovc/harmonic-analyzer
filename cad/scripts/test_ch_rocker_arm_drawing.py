"""Offline contracts for the rocker-arm drawing."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import ch_rocker_arm_notes
import ch_rocker_arm_spec
import draw_ch_rocker_arm as drawing
import build_ch_rocker_arm as arm
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_installation import MECHANISM_X_SHIFT
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rocker-arm_drawing.png")
    assert DRAWINGS_BY_NAME["ch_rocker_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: build marks exactly the spec's map, the drawing keeps
    # exactly its union across the per-view keep-maps.
    assert arm.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_rocker_arm_notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept | drawing.NOTE_ONLY_DIMENSIONS == marked


def test_draw_view_math_matches_the_spec() -> None:
    # The drawing's view math reads the spec's nominal spans, not a divergent
    # copy; the spec's geometry must match the part the build actually builds.
    assert (drawing.ROD_HOLE_X, drawing.TOP_END_Y) == (
        ch_rocker_arm_spec.ROD_HOLE_X,
        ch_rocker_arm_spec.TOP_END_Y,
    )
    assert ch_rocker_arm_spec.CURVE_RADIUS == arm.CURVE_RADIUS
    assert ch_rocker_arm_spec.ARM_DEPTH == arm.ARM_DEPTH
    assert ch_rocker_arm_spec.ARM_THICKNESS == arm.ARM_THICKNESS
    assert ch_rocker_arm_spec.TOP_ARC_LEN == arm.TOP_ARC_LEN
    assert ch_rocker_arm_spec.BOT_ARC_LEN == arm.BOT_ARC_LEN
    assert ch_rocker_arm_spec.TIP_FACE == arm.TIP_FACE
    assert ch_rocker_arm_spec.ROD_HOLE_X == arm.ROD_HOLE_X
    assert arm.ROD_HOLE_SPEC is ch_rocker_arm_spec.ROD_HOLE_SPEC
    assert drawing._ROD_HOLE_DIA == blind_cut_dia_mm(ch_rocker_arm_spec.ROD_HOLE_SPEC)


def test_rod_pin_follows_the_recentered_cam_and_recloses_neutral_y() -> None:
    assert math.isclose(
        ch_rocker_arm_spec.ROD_HOLE_X,
        127.3738 - MECHANISM_X_SHIFT,
        abs_tol=1e-12,
    )
    assert math.isclose(ch_rocker_arm_spec.ROD_HOLE_Y, 16.456064115939025, abs_tol=1e-12)
    assert ch_rocker_arm_spec.ROD_HOLE_ABOVE_BOTTOM == arm.ROD_HOLE_ABOVE_BOTTOM
    assert ch_rocker_arm_spec.ROD_HOLE_Y == arm.ROD_HOLE_Y


def test_sheet_runs_at_1_to_2() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_are_functional_metric_and_not_title_block_duplicates() -> None:
    notes = ch_rocker_arm_notes.DRAWING_NOTES
    assert "R800" in notes
    assert "R816" in notes
    # The rod hole rides its native Ø1.99 THRU ALL callout; the notes state
    # count and process only, never a second copy of a sheet dimension.
    assert "(1X)" in notes
    assert "#47" not in notes
    assert "6. PIVOT HOLE: REAM." in notes
    assert "16.00 REF" in notes
    # User ruling 2026-09-26: the edge height over the pivot is the control
    # (a model dimension, test_top_edge_height_is_a_banded_model_dimension);
    # the arc centre distance is reference.
    assert "808.00 REF FROM THE PIVOT" in notes
    assert f"INTEGRAL HUB DIA {ch_rocker_arm_spec.HUB_DIA:.2f}" in notes
    assert (
        "HUB OD COAXIAL WITH PIVOT BORE WITHIN Ø0.50 (TURN HUB AND REAM BORE IN ONE SETUP)"
        in " ".join(line.strip() for line in notes.splitlines())
    )
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
    assert "R800" in ch_rocker_arm_notes.DRAWING_NOTES
    assert "R816" in ch_rocker_arm_notes.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-rocker-arm")
    assert spec["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    assert spec["finish"] == "matte black oxide"
    assert int(spec["quantity"]) == 20


def test_surface_finish_is_part_owned_authored_and_consumed() -> None:
    (control,) = ch_rocker_arm_spec.SURFACE_FINISHES
    assert control.key == "pivot_bore"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == ch_rocker_arm_spec.PIVOT_HOLE_DIA
    assert arm.PIVOT_HOLE_DIA == ch_rocker_arm_spec.PIVOT_HOLE_DIA
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
    # Both views import by feature: only Hub's dimensions arrive in the end
    # view, only the pivot bore's in the front (r743-3: the front's
    # entire-model fallback warned on the leaf).
    assert curated["RIGHT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert curated["FRONT_KEEP"][1]["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert drawing.DRAWING_DIMENSIONS is ch_rocker_arm_notes.DRAWING_DIMENSIONS


def test_hub_length_prints_its_one_sided_band() -> None:
    """#743 PR2: the hubs are a solid stack whose north end is the rocker
    bank's datum, so each hub may only come out long and the print says so
    natively; rocker_bank_layout's L20 acceptance caps the sum."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["Hub"] == {"HubLength"}
    assert "HubLength" in drawing.RIGHT_KEEP
    assert model_toleranced_dimensions(arm)[("Hub", "HubLength")] == (
        "*deviations(HUB_LENGTH_BAND)"
    )
    assert ch_rocker_arm_spec.HUB_LENGTH_BAND == (0.05, 0.0)
    assert f"{ch_rocker_arm_spec.HUB_LENGTH:.2f}" not in ch_rocker_arm_notes.DRAWING_NOTES


def test_top_edge_height_is_a_banded_model_dimension() -> None:
    """Codex #936 PRRT_kwDOPHDy386mV3AO, policy rule 2: the clearance-critical
    "8.00 +0.50/0" lived only in a note. It is now the one printed dimension
    of a hidden reference sketch, carrying the band natively; the arcs'
    centre is derived from it, and no note repeats it."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_rocker_arm_spec.TOP_EDGE_BAND
    assert lower == 0.0 < upper == 0.50
    assert ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT == pytest.approx(8.0)
    assert not hasattr(ch_rocker_arm_notes, "TOP_EDGE_BAND")
    assert ch_rocker_arm_notes.DRAWING_DIMENSIONS["TopEdgeReference"] == {"TopAbovePivot"}
    assert model_toleranced_dimensions(arm)[("TopEdgeReference", "TopAbovePivot")] == (
        "*deviations(TOP_EDGE_BAND)"
    )
    assert "TopAbovePivot" in drawing.FRONT_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "ABOVE THE PIVOT" not in joined
    assert f"+{upper:.2f}/0" not in joined
    build = Path(arm.__file__).read_text(encoding="utf-8")
    # The centre is an equation of the printed height, so the model can't
    # hold one value while the sheet prints another.
    assert '"ArmDepth" / 2 + "TopAbovePivot" + "CurveRadius"' in build
    assert ch_rocker_arm_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"] == 2


def test_pivot_bore_ream_band_rides_its_diameter_not_a_note() -> None:
    """Codex #936 sweep (policy rule 2): note 6 printed "REAM +0.03/0, Ra
    1.6" while the O6.50 printed bare. The band is now native on PivotDia and
    the Ra is the bore's own symbol; the note keeps only REAM."""
    from _drawing_contract import model_toleranced_dimensions

    assert model_toleranced_dimensions(arm)[("PivotHoleProfile", "PivotDia")] == (
        "*deviations(PIVOT_HOLE_BAND)"
    )
    assert "PivotDia" in drawing.FRONT_KEEP
    joined = " ".join(
        line.strip() for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()
    )
    assert "+0.03" not in joined
    assert "Ra 1.6" not in joined
    assert any(
        control.key == "pivot_bore" for control in ch_rocker_arm_spec.SURFACE_FINISHES
    )


def test_no_rocker_note_carries_a_tolerance_band() -> None:
    """Policy rule 2 / 6: every band on MHA-CH-006 is a model tolerance. The one
    exception is the hub coaxiality, a plain note by Main's ruling
    (2026-09-26)."""
    for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines():
        if "COAXIAL" in line or "WITHIN" in line:
            continue
        assert not re.search(r"\+\d|[-+]0\.\d+/|±|\+/-", line), line


def test_top_edge_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880 / #950: a reference sketch owns a printed dimension but no
    # geometry, so the part saves it hidden (no assembly instance renders it)
    # and the drawing shows it per view through _drawing_hidden_sketches.
    build = Path(arm.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "TopEdgeReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source


def test_top_edge_height_text_stands_clear_above_the_strap() -> None:
    """The dimension runs up the mirror axis from the pivot centre; its text
    sits over the strap, right of datum A's box and left of the rod-pin
    frame."""
    pivot = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)
    edge = drawing._sheet_xy(
        0.0, ch_rocker_arm_spec.PIVOT_MID_Y + ch_rocker_arm_spec.TOP_EDGE_ABOVE_PIVOT
    )
    text = drawing.FRONT_KEEP["TopAbovePivot"]
    assert text[0] == pytest.approx(pivot[0])
    assert text[1] > edge[1] + 0.005
    datum_a = drawing._pivot_datum_request(pivot)
    assert datum_a[0] < text[0] - 0.012
    assert text[0] + 0.012 < drawing.FCF_XY[0]


_PIVOT_CENTRE = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)


class _Tag:
    def __init__(self, attached: tuple, dangling: bool = False) -> None:
        self.annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: attached,
            IsDangling=lambda: dangling,
        )

    def GetAnnotation(self) -> SimpleNamespace:
        return self.annotation


_BORE, _HUB = object(), object()
_APP = SimpleNamespace(IsSame=lambda a, b: 1 if a is b else 0)


@pytest.fixture
def bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)


def test_datum_a_attached_to_the_bore_passes(bound: None) -> None:
    drawing._require_datum_on_bore(_APP, _Tag((_BORE,)), _BORE)


@pytest.mark.parametrize(
    ("attached", "dangling", "match"),
    [
        ((_HUB,), False, "other than the O6.5 pivot bore"),
        ((), False, "has 0"),
        ((_BORE, _HUB), False, "has 2"),
        ((_BORE,), True, "dangling"),
    ],
)
def test_datum_a_off_the_bore_fails(
    bound: None, attached: tuple, dangling: bool, match: str
) -> None:
    """r743-4D: the rim pick attached datum A to the concentric O10 hub,
    which changes what the A-B-C frame controls."""
    with pytest.raises(RuntimeError, match=match):
        drawing._require_datum_on_bore(_APP, _Tag(attached, dangling), _BORE)


def _picker(monkeypatch: pytest.MonkeyPatch, resolve) -> list:
    """Route each EDGE pick through ``resolve(fraction of the bore radius)``."""
    picks: list = []

    def select(_adapter, _view, entity_type, xy, *, label):
        assert entity_type == "EDGE" and xy is not None
        fraction = round(math.dist(xy, _PIVOT_CENTRE) / drawing.PIVOT_BORE_SHEET_R, 6)
        picks.append((fraction, xy))
        return resolve(fraction)

    monkeypatch.setattr(drawing, "_select_view_entity", select)
    return picks


_ADAPTER = SimpleNamespace(
    swApp=_APP, currentModel=SimpleNamespace(ClearSelection2=lambda _all: True)
)


def test_pivot_pick_takes_the_bore_rim_on_the_datum_ray(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda _fraction: _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)
    assert [fraction for fraction, _ in picks] == [1.0]
    bearing = math.atan2(xy[1] - _PIVOT_CENTRE[1], xy[0] - _PIVOT_CENTRE[0])
    assert bearing == pytest.approx(drawing.PIVOT_DATUM_ANGLE)
    assert math.dist(xy, _PIVOT_CENTRE) == pytest.approx(drawing.PIVOT_BORE_SHEET_R)


def test_pivot_pick_moves_inward_when_the_rim_resolves_to_the_hub(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picks = _picker(monkeypatch, lambda fraction: _HUB if fraction == 1.0 else _BORE)
    xy = drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)
    assert [fraction for fraction, _ in picks] == list(drawing.PIVOT_PICK_FRACTIONS)
    assert xy == picks[-1][1]
    # Inward points stay inside the bore, further from the hub rim.
    assert all(0.0 < f <= 1.0 for f in drawing.PIVOT_PICK_FRACTIONS)


def test_pivot_pick_that_never_finds_the_bore_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def resolve(fraction: float) -> object:
        if fraction == 1.0:
            return _HUB
        raise RuntimeError("failed to select pivot bore datum pick edge")

    _picker(monkeypatch, resolve)
    with pytest.raises(RuntimeError, match="no pick on datum A's ray"):
        drawing._pick_pivot_bore(_ADAPTER, object(), _BORE, _PIVOT_CENTRE)


class _Window:
    def __init__(self) -> None:
        self.calls: list = []

    def ViewZoomTo2(self, *box: float) -> None:
        self.calls.append(("zoom", box))

    def ViewZoomtofit2(self) -> None:
        self.calls.append(("fit",))


def test_pivot_pick_zoom_frames_the_hub_and_restores_fit() -> None:
    window = _Window()
    adapter = SimpleNamespace(currentModel=window)
    half = drawing.PIVOT_PICK_ZOOM_HALF
    with pytest.raises(ValueError):
        with drawing._zoomed_on(adapter, _PIVOT_CENTRE, half):
            raise ValueError("pick failed")
    x, y = _PIVOT_CENTRE
    assert window.calls == [
        ("zoom", (x - half, y - half, 0.0, x + half, y + half, 0.0)),
        ("fit",),
    ]
    # The window holds the hub with margin, so the pick point is on screen.
    assert half > drawing.PIVOT_HUB_SHEET_R


# Datum A's frame as r743-4D printed it (coordinate pick, request 20 mm out on
# the 135-degree ray; 5100x3300 px render on 431.8x279.4 mm): the box spans
# 13.40..6.46 mm left of the requested point and 3.5 mm either side of it.
DATUM_BOX_LEFT = 0.01340
DATUM_BOX_RIGHT = 0.00646
DATUM_BOX_HALF_HEIGHT = 0.0035


def _strap_top_sheet_y(sheet_x: float) -> float:
    scale = drawing._S / 1000.0
    model_x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
    return drawing._sheet_xy(
        model_x,
        ch_rocker_arm_spec.CENTER_Y - math.sqrt(ch_rocker_arm_spec.R_TOP**2 - model_x**2),
    )[1]


def test_datum_a_frame_box_sits_off_the_part_outline() -> None:
    """r743-1RC: the entity-attached tag printed its frame on the strap. The
    coordinate-picked frame sits above the strap's top edge across its whole
    width, clear of the O6.50 text and above the notes."""
    rx, ry = drawing._pivot_datum_request(_PIVOT_CENTRE)
    box = (
        rx - DATUM_BOX_LEFT,
        ry - DATUM_BOX_HALF_HEIGHT,
        rx - DATUM_BOX_RIGHT,
        ry + DATUM_BOX_HALF_HEIGHT,
    )
    # r743-4D's measured frame for this same request: the fixture is that print.
    assert box == pytest.approx((0.15131, 0.18347, 0.15825, 0.19047), abs=2e-4)
    # The top edge is concave up, so its highest point under the box is at
    # one of the box's ends.
    strap_top = max(_strap_top_sheet_y(box[0]), _strap_top_sheet_y(box[2]))
    assert box[1] > strap_top + DATUM_BOX_HALF_HEIGHT
    _text_x, text_y = drawing.FRONT_KEEP["PivotDia"]
    assert box[1] > text_y + 0.010
    assert box[1] > drawing.NOTES_CEILING


def test_pivot_leaders_take_separate_quadrants() -> None:
    """r743-1RC: datum A, the Ra and the O6.50 converged on the bore. The
    O6.50 line runs through the centre, so it takes its text's quadrant and
    the opposite one; datum A and the Ra take the other two."""

    def quadrant(bearing: float) -> int:
        return int((bearing % math.tau) // (math.pi / 2.0))

    text = drawing.FRONT_KEEP["PivotDia"]
    dimension = math.atan2(text[1] - _PIVOT_CENTRE[1], text[0] - _PIVOT_CENTRE[0])
    rim, _symbol = drawing._pivot_finish_placement()
    finish = math.atan2(rim[1] - _PIVOT_CENTRE[1], rim[0] - _PIVOT_CENTRE[0])
    used = [
        quadrant(drawing.PIVOT_DATUM_ANGLE),
        quadrant(finish),
        quadrant(dimension),
        quadrant(dimension + math.pi),
    ]
    assert sorted(used) == [0, 1, 2, 3]
    # Datum A and the Ra land oblique to the centre-mark axes, not on them.
    for bearing in (drawing.PIVOT_DATUM_ANGLE, finish):
        assert math.degrees(bearing) % 90.0 == pytest.approx(45.0)


def test_pivot_diameter_text_is_clear_of_the_rod_pin_x_dimension() -> None:
    """r743-4D: the O6.50 leader, from text straight below the bore, crossed
    the rod-pin X location dimension. Its text now sits left of that
    dimension's span (pivot to rod-pin hole) and below the strap."""
    text_x, text_y = drawing.FRONT_KEEP["PivotDia"]
    pivot_x, pivot_y = drawing._sheet_xy(0.0, ch_rocker_arm_spec.PIVOT_MID_Y)
    # Diameter text runs ~2.6 mm a character from its anchor: "O6.50" is 5.
    assert text_x + 5 * 0.0026 < pivot_x - ch_rocker_arm_spec.HUB_DIA / 2000.0
    assert text_y < pivot_y - ch_rocker_arm_spec.ARM_DEPTH / 2000.0
    # Above the notes band.
    assert text_y > drawing.NOTES_CEILING + 0.010


def test_both_bores_are_picked_by_diameter_not_by_a_rim_coordinate() -> None:
    """r743-p1s-B: a coordinate pick on the #47 rod-hole rim resolved to the
    strap's tapered end-face line, so AddHoleCallout2 returned None. Every
    annotation on the rod-pin hole takes the diameter-picked edge."""

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
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
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


# r743-3 (4ca562169, w4): the 21-line block rendered 16.06..110.76 mm, i.e.
# 94.70 mm tall, 0.76 over NOTES_CEILING -- ~4.51 mm a line of rendered
# extent (box margins included), well above the 4.14 line pitch B2 measured.
R743_3_RENDERED_PITCH = 0.09470 / 21


def test_general_notes_leave_a_full_line_of_headroom() -> None:
    """Main (r743-3): the line estimate undercounted, so the block must fit
    the band with one full rendered line to spare at the measured pitch."""
    lines = len(ch_rocker_arm_notes.DRAWING_NOTES.splitlines())
    band = drawing.NOTES_CEILING - DRAWABLE.ymin - drawing.NOTES_BORDER_CLEARANCE
    assert (lines + 1) * R743_3_RENDERED_PITCH <= band
    # Every line stays within the widest line r743-2R already rendered
    # clear of the front view.
    assert max(len(line) for line in ch_rocker_arm_notes.DRAWING_NOTES.splitlines()) <= 42


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
    caption = ch_rocker_arm_notes.ISOMETRIC_VIEW_NOTE
    left, top = drawing.ISO_CAPTION_XY
    right = left + len(caption) * CAPTION_CHAR_WIDTH
    fcf_bottom = drawing.FCF_XY[1] - 0.007
    assert top < fcf_bottom - 0.003
    assert left > drawing.RIGHT_CENTER[0] + 0.015  # the end view and its +0.05
    assert right < RIGHT_BORDER - 0.005
    # Under the iso: the caption's span overlaps the iso's.
    assert left < drawing.ISO_CENTER[0] < right


# The Ra symbol as r743-1RC printed it at note text height: its ink runs
# 7.2 mm above and 14.7 mm right of its anchor (the leader end).
FINISH_SYMBOL_HEIGHT = 0.0072
FINISH_SYMBOL_WIDTH = 0.0147


def _strap_bottom_sheet_y(sheet_x: float) -> float:
    scale = drawing._S / 1000.0
    model_x = (sheet_x - drawing.FRONT_CENTER[0]) / scale
    return drawing._sheet_xy(
        model_x,
        ch_rocker_arm_spec.CENTER_Y
        - math.sqrt(ch_rocker_arm_spec.R_BOTTOM**2 - model_x**2),
    )[1]


def test_pivot_finish_leader_runs_up_left_from_a_symbol_below_the_strap() -> None:
    """r743-p1s-B2: from the 7:30 rim the leader ran up through the symbol,
    whose body draws up-right of its leader end. r743-1RC: at 1:30 it met the
    O6.50 line. At 4:30 the symbol sits down-right of its rim point, its whole
    body below the strap's bottom edge, at note text height."""
    rim, symbol = drawing._pivot_finish_placement()
    scale = drawing._S / 1000.0
    assert math.dist(rim, _PIVOT_CENTRE) == pytest.approx(
        ch_rocker_arm_spec.PIVOT_HOLE_DIA / 2.0 * scale
    )
    # Oblique to both centre-mark axes.
    assert abs(rim[0] - _PIVOT_CENTRE[0]) > 0.0005
    assert abs(rim[1] - _PIVOT_CENTRE[1]) > 0.0005
    assert symbol[0] > rim[0] and symbol[1] < rim[1]
    assert math.dist(symbol, _PIVOT_CENTRE) > ch_rocker_arm_spec.HUB_DIA / 2.0 * scale + 0.005
    # The bottom edge is concave up: its lowest point under the body is at
    # the body's left end.
    body_top = symbol[1] + FINISH_SYMBOL_HEIGHT
    assert body_top < _strap_bottom_sheet_y(symbol[0]) - 0.002
    # Right of the rod-pin X location's extension line through the pivot, and
    # above that dimension's line and text (y 0.138).
    assert rim[0] > _PIVOT_CENTRE[0]
    assert symbol[1] > 0.138 + 0.010
    assert symbol[0] + FINISH_SYMBOL_WIDTH < drawing._sheet_xy(
        ch_rocker_arm_spec.ROD_HOLE_X, 0.0
    )[0]
    assert drawing.PIVOT_FINISH_CHAR_HEIGHT <= 0.0025
