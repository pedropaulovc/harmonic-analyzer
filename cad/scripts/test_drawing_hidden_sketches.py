"""SolidWorks-free contract for ``_drawing_hidden_sketches``.

The fakes mimic what the summing lever measured on a real seat (probe runs
20260924T160303083Z-67cebdcd and 20260924T170431016Z-c0514e35, r21).  A
part-hidden sketch's dimensions import only while the VIEW shows it.
Blanking it again would hide them, so the module never does.  A derived view
is handled by ``part_sketches_shown`` instead.
"""

from __future__ import annotations

import pytest

import _drawing_common
import _drawing_hidden_sketches as hidden_sketches
from test_targeted_model_items import (
    FakeAdapter,
    FakeAnnotation,
    FakeDrawing,
    FakeView,
)

DIMENSIONS = {"ArcReference": {"ArcCentreX"}, "Column": {"Length"}}


@pytest.fixture(autouse=True)
def _no_com_curate(monkeypatch) -> None:
    """``curate_dimensions`` repositions over COM; here it only deletes."""

    def curate(adapter, annotations, *, delete=(), reposition=None):
        return [
            a
            for a in annotations
            if _drawing_common.dimension_name(adapter, a) not in delete
        ]

    monkeypatch.setattr(_drawing_common, "curate_dimensions", curate)


class FakeSketchFeature:
    """An ``IFeature`` double: a profile sketch, its saved visibility and the
    features that consume it."""

    def __init__(self, type_name: str, visible: int, children: int = 0) -> None:
        self._type_name = type_name
        self.Visible = visible
        self._children = tuple(object() for _ in range(children))

    def GetTypeName2(self) -> str:
        return self._type_name

    def GetChildren(self):
        return self._children or None


class FakePart:
    """The view's referenced part; the per-view path must only READ it."""

    def __init__(self, features: dict[str, tuple]) -> None:
        self.doc_type = 1  # swDocPART
        self.features = {
            name: FakeSketchFeature(*spec) for name, spec in features.items()
        }

    def FeatureByName(self, name: str):
        return self.features.get(name)

    def GetType(self) -> int:
        return self.doc_type


class VisibleAnnotation(FakeAnnotation):
    def __init__(self, name: str, visible: int) -> None:
        super().__init__(name)
        self.Visible = visible


class HiddenSketchDrawing(FakeDrawing):
    """Imports a part-hidden sketch's dimensions only while the VIEW shows it."""

    def __init__(self, part: FakePart, view: str, component: str) -> None:
        self.sketch = f"ArcReference@{component}@{view}"
        kinds = {
            view: "DRAWINGVIEW",
            self.sketch: "SKETCH",
            f"Column@{component}@{view}": "BODYFEATURE",
        }
        dimensions = {
            self.sketch: ["ArcCentreX"],
            f"Column@{component}@{view}": ["Length"],
        }
        super().__init__(kinds, dimensions)
        self.part = part
        self.log: list[tuple] = []
        self.view_shows_sketch = part.features["ArcReference"].Visible == 2
        self.dimension_visibility = 1

    def UnblankSketch(self) -> None:
        self.log.append(("unblank", tuple(self.selection)))
        self.view_shows_sketch = True

    def BlankSketch(self) -> None:
        self.log.append(("blank", tuple(self.selection)))
        self.view_shows_sketch = False

    def InsertModelAnnotations3(
        self, option, types, all_views, duplicate_dims, hidden, placement
    ):
        self.log.append(("import", self.view_shows_sketch))
        annotations = super().InsertModelAnnotations3(
            option, types, all_views, duplicate_dims, hidden, placement
        )
        return [
            VisibleAnnotation(a._display._dimension.Name, self.dimension_visibility)
            for a in annotations
            if self.view_shows_sketch or a._display._dimension.Name != "ArcCentreX"
        ]


class ReferencingView(FakeView):
    def __init__(
        self, name: str, component: str, part: FakePart, orientation: str = "*Top"
    ) -> None:
        super().__init__(name, component)
        self.ReferencedDocument = part
        self._orientation = orientation

    def GetOrientationName(self) -> str:
        return self._orientation


def _hidden_seat(visible: int = 1, children: int = 0, orientation: str = "*Top"):
    part = FakePart(
        {
            "ArcReference": ("ProfileFeature", visible, children),
            "Column": ("Extrusion", 2),
        }
    )
    drawing = HiddenSketchDrawing(part, "Drawing View2", "summing-lever-2")
    view = ReferencingView("Drawing View2", "summing-lever-2", part, orientation)
    return FakeAdapter(drawing), drawing, view


def _curate(adapter, view, keep, dimensions=DIMENSIONS):
    return hidden_sketches.curate_view_dimensions(
        adapter,
        view,
        keep={name: (0.1, 0.1) for name in keep},
        view_label="form top",
        dimensions_by_feature=dimensions,
    )


def test_a_part_hidden_sketch_is_shown_in_the_view_and_left_shown() -> None:
    """Order: per-view unblank -> import (shown), and NO blank after it: r21
    measured that a per-view re-blank hides the dimensions it delivered."""
    adapter, drawing, view = _hidden_seat()
    curated = _curate(adapter, view, ("ArcCentreX", "Length"))
    assert sorted(_drawing_common.dimension_name(adapter, a) for a in curated) == [
        "ArcCentreX",
        "Length",
    ]
    sketch = ("ArcReference@summing-lever-2@Drawing View2",)
    assert drawing.log == [("unblank", sketch), ("import", True)]
    assert drawing.view_shows_sketch
    # The part is only read: its saved hidden state stands.
    assert drawing.part.features["ArcReference"].Visible == 1


def test_a_visible_sketch_imports_untouched() -> None:
    """No-op when nothing is hidden: no per-view toggles at all."""
    adapter, drawing, view = _hidden_seat(visible=2)
    _curate(adapter, view, ("ArcCentreX",))
    assert drawing.log == [("import", True)]


def test_a_consumed_sketch_is_not_shown() -> None:
    """A profile a feature consumed reads hidden too, but its dimensions import
    without it (r21's PlateProfile etc.): showing it would print its geometry."""
    adapter, drawing, view = _hidden_seat(children=1)
    with pytest.raises(RuntimeError, match="missing model dimensions"):
        _curate(adapter, view, ("ArcCentreX",))
    assert drawing.log == [("import", False)]


def test_a_kept_dimension_that_reads_hidden_fails_loudly() -> None:
    adapter, drawing, view = _hidden_seat()
    drawing.dimension_visibility = 3  # swAnnotationHidden
    with pytest.raises(RuntimeError, match=r"read hidden: \['ArcCentreX'"):
        _curate(adapter, view, ("ArcCentreX",))


def test_a_shown_sketch_must_own_a_kept_dimension(monkeypatch) -> None:
    """Main's rule: a shown sketch with nothing dimensioned from it in the view
    is stray geometry.  The owner inversion makes that impossible today, so a
    future edit that selects a non-owner is simulated."""
    monkeypatch.setattr(
        _drawing_common,
        "_features_owning",
        lambda spec, keep, view_label: ("ArcReference", "Column"),
    )
    adapter, _drawing, view = _hidden_seat()
    with pytest.raises(RuntimeError, match=r"shows \['ArcReference'\] but keeps"):
        _curate(adapter, view, ("Length",))


def test_a_pictorial_view_never_shows_a_reference_sketch() -> None:
    adapter, drawing, view = _hidden_seat(orientation="*Isometric")
    with pytest.raises(RuntimeError, match="pictorial view"):
        _curate(adapter, view, ("ArcCentreX",))
    assert drawing.log == []


def test_a_missing_dimensions_undetected_owner_is_named_in_a_warning(
    monkeypatch,
) -> None:
    """r18 went silent: dimensions missing, no hidden sketch detected, no log."""
    warnings: list[str] = []
    monkeypatch.setattr(hidden_sketches._telemetry, "warn", warnings.append)
    adapter, _drawing, view = _hidden_seat(children=1)
    with pytest.raises(RuntimeError, match="missing model dimensions"):
        _curate(adapter, view, ("ArcCentreX",))
    assert len(warnings) == 1
    assert "owners ['ArcReference'] were not detected" in warnings[0]
    assert "'ArcReference': 'ProfileFeature Visible=1 children=1'" in warnings[0]


def test_the_detection_report_is_logged_at_info(monkeypatch) -> None:
    infos: list[str] = []
    monkeypatch.setattr(hidden_sketches._telemetry, "info", infos.append)
    adapter, _drawing, view = _hidden_seat()
    _curate(adapter, view, ("ArcCentreX", "Length"))
    assert infos[0] == (
        "hidden-sketch check Drawing View2: {'ArcReference': "
        "'ProfileFeature Visible=1 children=0', 'Column': 'Extrusion'}; "
        "showing ['ArcReference']"
    )
    assert "Visible states {'ArcCentreX': 1, 'Length': 1}" in infos[-1]


def test_a_view_of_an_assembly_is_not_checked_for_hidden_sketches(monkeypatch) -> None:
    infos: list[str] = []
    monkeypatch.setattr(hidden_sketches._telemetry, "info", infos.append)
    adapter, drawing, view = _hidden_seat()
    drawing.part.doc_type = 2  # swDocASSEMBLY
    _curate(adapter, view, ("Length",))
    assert drawing.log == [("import", False)]
    assert infos[0] == (
        "hidden-sketch check Drawing View2: "
        "{'*': 'referenced document type 2, not a part'}; showing []"
    )


class TogglePart(FakePart):
    """The drawing's open part: records selections and part-level toggles."""

    def __init__(self, path, sketch: str = "KnifeReference") -> None:
        super().__init__({sketch: ("ProfileFeature", 1)})
        self.path = path
        path.write_bytes(b"saved part")
        self.log: list[str] = []
        self.selected = None
        self.stuck = False
        feature = self.features[sketch]
        feature.Select2 = lambda append, mark: self._select(feature)

    def _select(self, feature) -> bool:
        self.selected = feature
        return True

    def ClearSelection2(self, _all) -> None:
        self.selected = None

    def GetPathName(self) -> str:
        return str(self.path)

    def UnblankSketch(self) -> None:
        self.log.append("part unblank")
        if not self.stuck:
            self.selected.Visible = 2

    def BlankSketch(self) -> None:
        self.log.append("part blank")
        self.selected.Visible = 1


class RebuildingDrawing:
    def __init__(self, log: list) -> None:
        self.log = log

    def EditRebuild3(self) -> bool:
        self.log.append("rebuild")
        return True


def _dimension_knife(block_part) -> None:
    """Stand-in for a detail's curate inside the block: marks KnifeReference
    dimensioned, as the real curate does when its dimension survives."""
    hidden_sketches._PART_SHOWN[-1].dimensioned.add("KnifeReference")
    block_part.log.append("create + curate")


def test_part_sketches_are_shown_around_the_block_then_blanked(tmp_path) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT")
    adapter = FakeAdapter(RebuildingDrawing(part.log))
    with hidden_sketches.part_sketches_shown(
        adapter, part, ["KnifeReference"], label="Detail A"
    ):
        assert part.features["KnifeReference"].Visible == 2
        _dimension_knife(part)
    assert part.log == [
        "part unblank",
        "rebuild",
        "create + curate",
        "part blank",
        "rebuild",
    ]
    assert part.features["KnifeReference"].Visible == 1
    assert hidden_sketches._PART_SHOWN == []


def test_a_real_curate_inside_the_block_marks_its_owner_dimensioned(
    tmp_path,
) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT", "ArcReference")
    adapter, _drawing, view = _hidden_seat(visible=2)
    part_adapter = FakeAdapter(RebuildingDrawing(part.log))
    with hidden_sketches.part_sketches_shown(
        part_adapter, part, ["ArcReference"], label="Detail A"
    ):
        _curate(adapter, view, ("ArcCentreX",))
        assert hidden_sketches._PART_SHOWN[-1].dimensioned == {"ArcReference"}


def test_part_sketches_are_blanked_again_when_the_block_fails(tmp_path) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT")
    adapter = FakeAdapter(RebuildingDrawing(part.log))
    with pytest.raises(RuntimeError, match="import failed"):
        with hidden_sketches.part_sketches_shown(
            adapter, part, ["KnifeReference"], label="Detail A"
        ):
            raise RuntimeError("import failed")
    assert part.log[-2:] == ["part blank", "rebuild"]
    assert part.features["KnifeReference"].Visible == 1
    assert hidden_sketches._PART_SHOWN == []


def test_a_part_sketch_nothing_dimensions_fails_loudly(tmp_path) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT")
    adapter = FakeAdapter(RebuildingDrawing(part.log))
    with pytest.raises(RuntimeError, match=r"\['KnifeReference'\] were shown but"):
        with hidden_sketches.part_sketches_shown(
            adapter, part, ["KnifeReference"], label="Detail A"
        ):
            pass
    assert part.features["KnifeReference"].Visible == 1


def test_a_part_sketch_that_does_not_show_fails_loudly(tmp_path) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT")
    part.stuck = True
    adapter = FakeAdapter(RebuildingDrawing(part.log))
    with pytest.raises(RuntimeError, match="reads Visible=1 after UnblankSketch"):
        with hidden_sketches.part_sketches_shown(
            adapter, part, ["KnifeReference"], label="Detail A"
        ):
            pass


def test_a_part_saved_while_its_sketches_were_shown_fails_loudly(tmp_path) -> None:
    part = TogglePart(tmp_path / "lever.SLDPRT")
    adapter = FakeAdapter(RebuildingDrawing(part.log))
    with pytest.raises(RuntimeError, match="must never save the part"):
        with hidden_sketches.part_sketches_shown(
            adapter, part, ["KnifeReference"], label="Detail A"
        ):
            _dimension_knife(part)
            part.path.write_bytes(b"saved again")
    assert part.features["KnifeReference"].Visible == 1
