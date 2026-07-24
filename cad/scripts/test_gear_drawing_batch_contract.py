"""Cross-sheet offline contracts for the eight current gear drawings."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _gear_drawing_entities
import alignment_pinion_spec
import cone_gear_spec
import crank_drive_gear_spec
import crank_pinion_spec
import cylinder_gear_spec
import draw_alignment_pinion
import draw_cone_gear
import draw_crank_drive_gear
import draw_crank_pinion
import draw_cylinder_gear
import draw_rack_pinion
import draw_transgear_feed_pinion
import draw_transgear_pinion
import rack_pinion_spec
import transgear_feed_pinion_spec
import transgear_pinion_spec


SHEETS = (
    ("alignment-pinion", alignment_pinion_spec),
    ("cone-gear", cone_gear_spec),
    ("crank-drive-gear", crank_drive_gear_spec),
    ("crank-pinion", crank_pinion_spec),
    ("cylinder-gear", cylinder_gear_spec),
    ("rack-pinion", rack_pinion_spec),
    ("transgear-feed-pinion", transgear_feed_pinion_spec),
    ("transgear-pinion", transgear_pinion_spec),
)

DRAWING_MODULES = (
    draw_alignment_pinion,
    draw_cone_gear,
    draw_crank_drive_gear,
    draw_crank_pinion,
    draw_cylinder_gear,
    draw_rack_pinion,
    draw_transgear_feed_pinion,
    draw_transgear_pinion,
)

CRANK_PAIR_MODULES = (
    draw_crank_drive_gear,
    draw_crank_pinion,
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK EDGES",
    "BREAK SHARP",
    "DEBUR",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGES",
    "U.O.S.",
    "UNLESS OTHERWISE SPECIFIED",
    " UOS",
)


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec in SHEETS:
        notes = spec.DRAWING_NOTES.upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_notes_do_not_repeat_title_block_quantity() -> None:
    for part_name, spec in SHEETS:
        if part_name == "cone-gear":
            # One of each configuration is essential family-table scope, not a
            # repeat of the per-configuration title-block quantity.
            continue
        assert " REQUIRED" not in spec.DRAWING_NOTES.upper(), part_name


def test_bore_annotations_use_explicit_nonconflicting_selectors() -> None:
    for module in DRAWING_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "gear_faces = gear_model_faces(" in source, module.__name__
        assert "entity=gear_faces.bore" in source, module.__name__
        if module in CRANK_PAIR_MODULES:
            assert "edge_xy=bore_top" not in source, module.__name__
            assert source.count("entity=gear_faces.bore") == 2, module.__name__
            assert source.count("leader_attach_xy=(") == 2, module.__name__
            assert "position_tolerance_m=0.080" in source, module.__name__
            assert "shoulder=True" in source, module.__name__
            continue
        assert "edge_xy=bore_top" in source, module.__name__
        assert "edge_xy=bore_bottom" not in source, module.__name__
        assert source.count("entity=gear_faces.bore") == 1, module.__name__
        expected_tolerance = (
            "position_tolerance_m=0.008"
            if module.__name__ == "draw_cylinder_gear"
            else "position_tolerance_m=0.001"
        )
        assert expected_tolerance in source, module.__name__
        assert "shoulder=True" in source, module.__name__


def test_crank_pair_runout_uses_source_model_tooth_tip_face() -> None:
    helper_source = Path(_gear_drawing_entities.__file__).read_text(encoding="utf-8")
    assert "_SOURCE_FACE_SCAN_LIMIT" in helper_source
    assert "GetClosestPointOn" in helper_source
    for module in CRANK_PAIR_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "tooth_tip_diameter_mm=OUTSIDE_DIA" in source
        assert "entity=gear_faces.tooth_tip" in source
        assert 'entity_type="MODEL_FACE"' in source


def test_all_gear_annotations_avoid_drawing_visible_entity_walks() -> None:
    helper_source = Path(_gear_drawing_entities.__file__).read_text(encoding="utf-8")
    assert "GetVisibleComponents" not in helper_source
    assert "GetVisibleEntities2" not in helper_source
    for module in DRAWING_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "entity=gear_faces.end" in source
        assert 'entity_type="MODEL_FACE"' in source
        assert "edge_xy=(FRONT_FACE_X" not in source
        if module is not draw_cylinder_gear:
            assert "leader_attach_xy=(" in source


def test_gear_model_faces_uses_axial_end_and_right_view_top_tip(monkeypatch) -> None:
    class Surface:
        def __init__(
            self,
            kind: str,
            radius_mm: float = 0.0,
            normal: tuple[float, float, float] = (0.0, 0.0, 1.0),
        ) -> None:
            self.kind = kind
            self.CylinderParams = (0, 0, 0, 0, 0, 0, radius_mm / 1000.0)
            self.PlaneParams = (*normal, 0.0, 0.0, 0.0)

        def IsPlane(self) -> bool:
            return self.kind == "plane"

        def IsCylinder(self) -> bool:
            return self.kind == "cylinder"

    class Vertex:
        def __init__(self, point: tuple[float, float, float]) -> None:
            self.point = point

        def GetPoint(self):
            return self.point

    class Edge:
        def __init__(
            self,
            start: tuple[float, float, float],
            end: tuple[float, float, float],
        ) -> None:
            self.start = Vertex(start)
            self.end = Vertex(end)

        def GetStartVertex(self):
            return self.start

        def GetEndVertex(self):
            return self.end

    class Face:
        def __init__(
            self,
            surface: Surface,
            *,
            area: float = 0.0,
            edges=(),
            closest: tuple[float, float, float] | None = None,
        ) -> None:
            self.surface = surface
            self.area = area
            self.edges = edges
            self.closest = closest
            self.closest_queries: list[tuple[float, float, float]] = []

        def GetSurface(self):
            return self.surface

        def GetEdges(self):
            return self.edges

        def GetArea(self):
            return self.area

        def GetClosestPointOn(self, x: float, y: float, z: float):
            self.closest_queries.append((x, y, z))
            if self.closest is None:
                return None
            return (*self.closest, 0.0, 0.0)

    lower_tip = Face(
        Surface("other"),
        edges=(Edge((0.0085, 0.0, 0.0), (0.0085, 0.0, 0.010)),),
        closest=(0.0085, 0.0, 0.005),
    )
    top_tip = Face(
        Surface("other"),
        edges=(Edge((0.0, 0.0085, 0.0), (0.0, 0.0085, 0.010)),),
        closest=(0.0, 0.0085, 0.005),
    )
    closer_flank = Face(
        Surface("other"),
        edges=(Edge((0.0, 0.0085, 0.0), (0.0, 0.0075, 0.010)),),
        closest=(0.0, 0.0085, 0.0),
    )
    axial_small = Face(Surface("plane"), area=0.001)
    axial_large = Face(Surface("plane", normal=(0.0, 0.0, -1.0)), area=0.002)
    bore = Face(Surface("cylinder", 3.0))
    misleading_plane = Face(Surface("plane", normal=(1.0, 0.0, 0.0)), area=100.0)
    faces = [
        lower_tip,
        top_tip,
        closer_flank,
        axial_small,
        axial_large,
        bore,
        misleading_plane,
    ]
    adapter = SimpleNamespace(_attempt=lambda call, default=None: call())
    monkeypatch.setattr(
        _gear_drawing_entities, "_early_bound", lambda value, *_args: value
    )
    monkeypatch.setattr(
        _gear_drawing_entities,
        "referenced_model_faces",
        lambda _adapter, _view, *, label: faces,
    )

    selected = _gear_drawing_entities.gear_model_faces(
        adapter,
        object(),
        6.0,
        label="test gear",
        tooth_tip_diameter_mm=17.0,
    )

    assert selected.bore is bore
    assert selected.end is axial_large
    assert selected.tooth_tip is top_tip
    expected_query = (0.0, 0.0085, 0.0)
    assert lower_tip.closest_queries == [expected_query]
    assert top_tip.closest_queries == [expected_query]
    assert closer_flank.closest_queries == [expected_query]


def test_gear_model_faces_fails_before_an_unbounded_face_scan(monkeypatch) -> None:
    faces = [object()] * (_gear_drawing_entities._SOURCE_FACE_SCAN_LIMIT + 1)
    monkeypatch.setattr(
        _gear_drawing_entities,
        "referenced_model_faces",
        lambda _adapter, _view, *, label: faces,
    )

    with pytest.raises(RuntimeError, match="exceed the bounded classification limit"):
        _gear_drawing_entities.gear_model_faces(
            SimpleNamespace(), object(), 6.0, label="oversized gear"
        )


def test_tooth_runout_is_stated_against_the_bore_axis_datum() -> None:
    for (part_name, spec), module in zip(SHEETS, DRAWING_MODULES, strict=True):
        if module in CRANK_PAIR_MODULES:
            source = Path(module.__file__).read_text(encoding="utf-8")
            assert 'characteristic="circular_runout"' in source, part_name
            assert 'datums=("A",)' in source, part_name
            assert 'quantity="TOOTH TIPS"' in source, part_name
            continue
        notes = spec.DRAWING_NOTES.upper()
        assert (
            "GEAR TEETH: CIRCULAR RUNOUT 0.05 MAX ABOUT DATUM A, "
            "MEASURED AT THE TOOTH TIPS" in notes
        ), part_name
        assert "WITHIN 0.05 TIR" not in notes, part_name
