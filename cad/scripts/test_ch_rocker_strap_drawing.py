"""Offline contracts for the rocker strap (MHA-CH-13) drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm as rocker_part
import build_ch_rocker_strap as part
import ch_rocker_arm_notes as rocker_notes
import ch_rocker_arm_spec as rocker
import ch_rocker_hub_fit as fit
import _rocker_interface as rocker_interface
import ch_rocker_strap_notes as notes
import ch_rocker_strap_spec as spec
import draw_ch_rocker_strap as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rocker-strap.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rocker-strap.pdf")
    assert (
        DRAWINGS_BY_NAME["ch_rocker_strap"].script == Path(drawing.__file__).resolve()
    )
    assert "draw_ch_rocker_strap.py" in PRECISION_MIGRATED_DRAWINGS


def test_outline_is_the_finished_rocker_strap() -> None:
    # Same frame and the same vertices as MHA-CH-06's strap profile.
    assert spec.HOLE_DIA == rocker.HUB_DIA
    assert spec.PIVOT_MID_Y == rocker_interface.PIVOT_MID_Y
    assert spec.ROD_TIP_X == rocker.ROD_TIP_X
    assert spec.BOT_END_X == rocker.BOT_END_X
    assert spec.BOT_END_Y == pytest.approx(
        rocker_interface.CENTER_Y
        - math.sqrt(rocker_interface.R_BOTTOM**2 - rocker.BOT_END_X**2)
    )
    assert spec.ROD_TIP_Y < spec.TOP_END_Y
    # The tip land runs along the top arc's radius.
    tip_radius = math.hypot(spec.ROD_TIP_X, spec.ROD_TIP_Y - spec.CENTER_Y)
    assert tip_radius == pytest.approx(rocker.R_TOP + rocker.TIP_FACE)
    assert spec.strap_area() == pytest.approx(rocker_part._strap_area(), rel=1e-9)
    assert part.V_STRAP == pytest.approx(
        (spec.strap_area() - math.pi * (spec.HOLE_DIA / 2.0) ** 2)
        * rocker.ARM_THICKNESS
    )
    # The hub hole's walls (rule 17), each edge at the worst end of its band
    # against the reamed hole's top limit: both edges are held from the hole,
    # so the radii never stack into the wall (r1 machinist review: .031).
    hole_radius_max = (spec.HOLE_DIA + fit.STRAP_HOLE_BAND[0]) / 2.0
    top_wall = spec.TOP_EDGE_ABOVE_PIVOT + spec.TOP_EDGE_BAND[1] - hole_radius_max
    bottom_wall = (
        spec.BOTTOM_EDGE_BELOW_PIVOT + spec.BOTTOM_EDGE_BAND[1] - hole_radius_max
    )
    assert min(top_wall, bottom_wall) >= WALL_TARGET_MM
    # The bottom edge sits where MHA-CH-06's R816 puts it on the axis.
    assert spec.BOTTOM_EDGE_BELOW_PIVOT == pytest.approx(
        rocker_interface.PIVOT_MID_Y
        - (rocker_interface.CENTER_Y - rocker_interface.R_BOTTOM)
    )


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(notes.DIMENSION_CALLOUTS) <= marked
    assert notes.DRAWING_PRECISION_BY_NAME["StrapThickness"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["TopAbovePivot"] == 3
    assert notes.DRAWING_PRECISION_BY_NAME["BottomBelowPivot"] == 3
    # TailTipLen is the RodTipLen's mirror: it prints once, as 2X, and so
    # does the land's angle from vertical (r4: "RADIAL" named no centre).
    assert "TailTipLen" not in marked
    assert notes.TIP_LAND_PREFIX == notes.TIP_LAND_ANGLE_PREFIX == "2X "
    assert "TipLandAngle" in notes.DRAWING_DIMENSIONS["StrapProfile"]
    assert notes.DRAWING_PRECISION_BY_NAME["TipLandAngle"] == 1
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source


def test_printed_edge_limits_are_the_finished_rockers() -> None:
    # The strap's outline is finished here, so each edge's PRINTED inch limits
    # must be the finished MHA-CH-06's: the .315 BASIC height with its .020
    # one-sided zone, above the pivot and (mirrored) below it.
    def limits(nominal_mm: float, places: int, band: tuple[float, float]):
        nominal = round(nominal_mm / 25.4, places)
        upper, lower = (round(d / 25.4, 3) for d in band)
        return round(nominal + lower, 3), round(nominal + upper, 3)

    arm_places = rocker_notes.DRAWING_PRECISION["TopEdgeReference"]["TopAbovePivot"]
    zone = round(rocker.TOP_EDGE_BAND[0] / 25.4, 3)
    arm_height = round(rocker.TOP_EDGE_ABOVE_PIVOT / 25.4, arm_places)
    assert (arm_height, zone) == (0.315, 0.020)
    top = limits(
        spec.TOP_EDGE_ABOVE_PIVOT,
        notes.DRAWING_PRECISION_BY_NAME["TopAbovePivot"],
        spec.TOP_EDGE_BAND,
    )
    bottom = limits(
        spec.BOTTOM_EDGE_BELOW_PIVOT,
        notes.DRAWING_PRECISION_BY_NAME["BottomBelowPivot"],
        spec.BOTTOM_EDGE_BAND,
    )
    assert top == (arm_height, round(arm_height + zone, 3)) == (0.315, 0.335)
    assert bottom == (round(arm_height - zone, 3), arm_height) == (0.295, 0.315)
    # Each edge's tolerance prints at its nominal's places (.315 +.020/.000).
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    places = {
        call.args[2].value: ast.unparse(keyword.value)
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", None) == "set_dimension_bilateral_tolerance"
        for keyword in call.keywords
        if keyword.arg == "places"
    }
    assert places == {
        name: f"DRAWING_PRECISION_BY_NAME['{name}']"
        for name in ("TopAbovePivot", "BottomBelowPivot")
    }


def test_every_band_is_native_and_names_its_mate() -> None:
    assert model_toleranced_dimensions(part) == {
        ("Strap", "StrapThickness"): "strap_upper",
        ("StrapProfile", "HoleDia"): "*deviations(STRAP_HOLE_BAND)",
        ("StrapProfile", "TopAbovePivot"): "*deviations(TOP_EDGE_BAND)",
        ("StrapProfile", "BottomBelowPivot"): "*deviations(BOTTOM_EDGE_BAND)",
    }
    assert spec.ARM_THICKNESS_BAND == rocker.ARM_THICKNESS_BAND == (0.0254, -0.0254)
    assert spec.TOP_EDGE_BAND == rocker.TOP_EDGE_BAND
    # The bottom edge's band mirrors the top's: the finished part's lower
    # profile zone, wholly in material.
    assert spec.BOTTOM_EDGE_BAND == (0.0, -0.508)
    assert notes.DIMENSION_CALLOUTS["HoleDia"] == notes.HOLE_CALLOUT
    assert notes.DIMENSION_CALLOUTS["StrapThickness"] == rocker_notes.STRAP_FIT_CALLOUT


def test_no_rod_pin_hole_and_no_finished_bore_on_the_strap() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "ROD_PIN" not in build and "PIVOT_HOLE" not in build
    printed = " ".join(notes.DIMENSION_CALLOUTS.values())
    assert "#47" not in printed
    assert f"{rocker.PIVOT_HOLE_DIA / 25.4:.3f}".removeprefix("0") not in printed


def test_drawing_quality_and_no_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish",
    }
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert drawing.ISO_SCALE == (1, 2)


def test_overall_length_is_a_one_place_reference_and_enforced() -> None:
    # ENFORCE r3: the overall printed only as two tip offsets (rule 10).
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert spec.DRAWING_REFERENCE_PRECISION == {"OverallLength": 1}
    tip_x_in = spec.ROD_TIP_X / 25.4
    offsets = 2 * round(tip_x_in, notes.DRAWING_PRECISION_BY_NAME["RodTipX"])
    overall = round(2 * tip_x_in, spec.DRAWING_REFERENCE_PRECISION["OverallLength"])
    # One place, so the reference agrees with the offsets' printed sum.
    assert overall == pytest.approx(round(offsets, 1))
    # Outermost: above the offsets' row.
    assert drawing.OVERALL_LINE_Y > drawing.TIP_LINE_Y
    functions = {
        node.name: node
        for node in ast.walk(ast.parse(Path(drawing.__file__).read_text("utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def called(function: str) -> set[str]:
        return {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(functions[function])
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        }

    # The sheet places it (the helper's behaviour is the next test's).
    assert "_add_overall_length" in called("build")


class _OverallDoubles:
    """Records what ``_add_overall_length`` asks of the sheet; the display
    dimension prints whatever places it is set to, or ``applied`` if given."""

    def __init__(self, applied: int | None = None) -> None:
        self.applied = applied
        self.vertex_points: list[tuple[float, float, float]] = []
        self.added: dict = {}
        self.measured: dict = {}
        self.referenced: list[str] = []
        self.precision: int | None = None

    # scan_view_edges(...).exact_vertex_at(point, label=...)
    def exact_vertex_at(self, point, *, label):
        self.vertex_points.append(point)
        return ("vertex", point)

    # The display dimension and its annotation.
    def GetAnnotation(self):
        return self

    def SetPrecision3(self, primary, *_rest):
        self.precision = primary

    def GetPrimaryPrecision2(self):
        return self.precision if self.applied is None else self.applied


def _patch_overall(monkeypatch, doubles: _OverallDoubles) -> None:
    def add_edge_dimension(_adapter, _view, **kwargs):
        doubles.added = kwargs
        return doubles

    def assert_dimension_measures(_adapter, dimension, **kwargs):
        assert dimension is doubles
        doubles.measured = kwargs
        return kwargs["expected_mm"]

    def set_reference_dimension(_adapter, annotation, *, label):
        assert annotation is doubles
        doubles.referenced.append(label)
        return doubles

    monkeypatch.setattr(drawing, "scan_view_edges", lambda _view, *, label: doubles)
    monkeypatch.setattr(drawing, "add_edge_dimension", add_edge_dimension)
    monkeypatch.setattr(drawing, "assert_dimension_measures", assert_dimension_measures)
    monkeypatch.setattr(drawing, "set_reference_dimension", set_reference_dimension)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)


def test_overall_length_spans_both_tip_corners_as_a_one_place_reference(
    monkeypatch,
) -> None:
    doubles = _OverallDoubles()
    _patch_overall(monkeypatch, doubles)
    drawing._add_overall_length(object(), object())
    # Both +Z-face tip corners, the outermost points of the mirrored outline.
    corners = [
        (-spec.ROD_TIP_X, spec.ROD_TIP_Y, spec.ARM_THICKNESS / 2.0),
        (spec.ROD_TIP_X, spec.ROD_TIP_Y, spec.ARM_THICKNESS / 2.0),
    ]
    assert doubles.vertex_points == corners
    vertices = tuple(("vertex", point) for point in corners)
    assert doubles.added["entities"] == vertices
    assert doubles.added["entity_types"] == ("VERTEX", "VERTEX")
    assert doubles.added["orientation"] == "horizontal"
    assert doubles.added["text_xy"] == (drawing.FRONT_CENTER[0], drawing.OVERALL_LINE_Y)
    assert doubles.measured["entities"] == vertices
    assert doubles.measured["expected_mm"] == pytest.approx(2.0 * spec.ROD_TIP_X)
    assert doubles.referenced == ["strap overall length"]
    assert doubles.precision == spec.DRAWING_REFERENCE_PRECISION["OverallLength"]


def test_overall_length_refuses_unapplied_places(monkeypatch) -> None:
    _patch_overall(monkeypatch, _OverallDoubles(applied=2))
    with pytest.raises(RuntimeError, match="prints 2 decimal places, not 1"):
        drawing._add_overall_length(object(), object())


def test_registry_row() -> None:
    row = _config.parts("ch-rocker-strap")
    assert row["number"] == spec.NUMBER == "MHA-CH-13"
    assert row["component_of"] == "ch-rocker-arm"
    assert int(row["quantity"]) == int(_config.parts("ch-rocker-arm")["quantity"])
    # Owner ruling 2026-11-03: the title-block MATERIAL row names the grade.
    assert row["material"] == "LOW-CARBON STEEL, E.G. 1018 CF"
    assert "1018" in str(row["material_specification"])
    assert len(str(row["material_specification"])) <= 36
    assert len(str(row["finish"])) <= 36
    assert part.MATERIAL == "Plain Carbon Steel"


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
    _drawing_marks.apply_drawing_properties(
        None,
        part.PART_NAME,
        {
            "Isometric View Note": notes.ISOMETRIC_VIEW_NOTE,
        },
    )
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)
