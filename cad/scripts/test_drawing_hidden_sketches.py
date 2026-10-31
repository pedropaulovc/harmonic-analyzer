"""SolidWorks-free contract for ``_drawing_hidden_sketches``.

The fakes mimic what the summing lever measured on a real seat (probe runs
20260924T160303083Z-67cebdcd and 20260924T170431016Z-c0514e35, r21).  A
part-hidden sketch's dimensions import only while the VIEW shows it.
Blanking it again would hide them, so the module never does.  A derived view
is handled by ``part_sketches_shown`` instead.
"""

from __future__ import annotations

import asyncio
import ast
import functools
import inspect
import unicodedata
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_dimension_import
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
    """``curate_dimensions`` repositions over COM; here it deletes and lands
    each kept dimension exactly on its requested point."""

    def curate(adapter, annotations, *, delete=(), reposition=None):
        survivors = []
        for a in annotations:
            name = hidden_sketches._sw_drawing.dimension_name(adapter, a)
            if name in delete:
                continue
            if reposition and name in reposition:
                a.position = reposition[name]
            survivors.append(a)
        return survivors

    monkeypatch.setattr(hidden_sketches._sw_drawing, "curate_dimensions", curate)


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
    drawing = HiddenSketchDrawing(part, "Drawing View2", "sm-summing-lever-2")
    view = ReferencingView("Drawing View2", "sm-summing-lever-2", part, orientation)
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
    assert sorted(hidden_sketches._sw_drawing.dimension_name(adapter, a) for a in curated) == [
        "ArcCentreX",
        "Length",
    ]
    sketch = ("ArcReference@sm-summing-lever-2@Drawing View2",)
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
        _drawing_dimension_import,
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
        self.on_blank = lambda: None
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
        self.on_blank()


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


class RebuildingHiddenSketchDrawing(HiddenSketchDrawing):
    """The drawing the block rebuilds, logging onto the part's event log."""

    def __init__(self, part: TogglePart) -> None:
        super().__init__(part, "Drawing View2", "sm-summing-lever-2")
        self.events = part.log

    def UnblankSketch(self) -> None:
        self.events.append("view unblank")
        super().UnblankSketch()

    def BlankSketch(self) -> None:
        self.events.append("view blank")
        super().BlankSketch()

    def EditRebuild3(self) -> bool:
        self.events.append("rebuild")
        return True


def _base_view_block(tmp_path, orientation: str):
    part = TogglePart(tmp_path / "lever.SLDPRT", "ArcReference")
    drawing = RebuildingHiddenSketchDrawing(part)
    base = ReferencingView("Drawing View2", "sm-summing-lever-2", part, orientation)
    block = hidden_sketches.part_sketches_shown(
        FakeAdapter(drawing), part, ["ArcReference"], label="Detail A", base_view=base
    )
    return part, drawing, block


def test_the_base_view_shows_the_sketches_first_and_keeps_them(tmp_path) -> None:
    """pc-p1r: a detail's items select through its base view, and with only
    the part showing the sketches the import delivered nothing.  The base view
    shows them per view before the part does and is never blanked again."""
    part, drawing, block = _base_view_block(tmp_path, "*Right")
    with block:
        hidden_sketches._PART_SHOWN[-1].dimensioned.add("ArcReference")
        part.log.append("create + curate")
    assert part.log == [
        "view unblank",
        "part unblank",
        "rebuild",
        "create + curate",
        "part blank",
        "rebuild",
    ]
    sketch = ("ArcReference@sm-summing-lever-2@Drawing View2",)
    assert drawing.log == [("unblank", sketch)]
    assert drawing.view_shows_sketch


def test_a_pictorial_base_view_never_shows_a_reference_sketch(tmp_path) -> None:
    part, drawing, block = _base_view_block(tmp_path, "*Isometric")
    with pytest.raises(RuntimeError, match="pictorial base view"):
        with block:
            pass
    assert part.log == []
    assert drawing.log == []
    assert hidden_sketches._PART_SHOWN == []


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


def test_a_dimension_the_part_reblank_hides_fails_loudly(tmp_path) -> None:
    """Codex on #819: the curate's gate runs before the re-blank, so the block
    re-reads its kept dimensions afterwards (a derived view other than the
    measured detail might lose them)."""
    part = TogglePart(tmp_path / "lever.SLDPRT", "ArcReference")
    adapter, _drawing, view = _hidden_seat(visible=2)
    part_adapter = FakeAdapter(RebuildingDrawing(part.log))
    with pytest.raises(
        RuntimeError, match=r"hidden by the part re-blank.*form top:ArcCentreX"
    ):
        with hidden_sketches.part_sketches_shown(
            part_adapter, part, ["ArcReference"], label="section A"
        ):
            curated = _curate(adapter, view, ("ArcCentreX",))

            def hide() -> None:
                for annotation in curated:
                    annotation.Visible = 3

            part.on_blank = hide


def test_dimensions_that_survive_the_part_reblank_pass(tmp_path, monkeypatch) -> None:
    infos: list[str] = []
    monkeypatch.setattr(hidden_sketches._telemetry, "info", infos.append)
    part = TogglePart(tmp_path / "lever.SLDPRT", "ArcReference")
    adapter, _drawing, view = _hidden_seat(visible=2)
    part_adapter = FakeAdapter(RebuildingDrawing(part.log))
    with hidden_sketches.part_sketches_shown(
        part_adapter, part, ["ArcReference"], label="Detail A"
    ):
        _curate(adapter, view, ("ArcCentreX", "Length"))
    assert infos[-1] == (
        "Detail A: after the part re-blank, dimension Visible {'form top:ArcCentreX': 1}"
    )


_SCRIPTS = Path(hidden_sketches.__file__).resolve().parent


@functools.cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_clamp_reference_names_drive_actual_sources(monkeypatch) -> None:
    """Changing the declaration must rename the actual source-map owners,
    rather than leave a dead parallel list for the routing scan."""
    import build_mg_magnifying_clamp as clamp

    names = ("ThumbWitness", "RodWitness", "BoreWitness")
    monkeypatch.setattr(clamp, "REFERENCE_SKETCHES", names)
    thumb, rod = object(), object()
    bore = SimpleNamespace(GetType=lambda: 1)
    sketch = SimpleNamespace(GetSketchSegments=lambda: (bore,))
    feature = SimpleNamespace(GetSpecificFeature2=lambda: sketch)
    requested = []

    def feature_by_name(name):
        requested.append(name)
        return feature

    adapter = SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=feature_by_name))
    faces = {"top": object(), "bottom": object(), "zflat": object()}
    monkeypatch.setattr(clamp, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(clamp, "resolve_faces", lambda *_args: faces)
    monkeypatch.setattr(clamp, "_stock_edge", lambda face, _ends: face)
    monkeypatch.setattr(
        clamp, "_tap_entry_circle",
        lambda face, _y: thumb if face is faces["top"] else rod,
    )
    sources = clamp._location_sources(adapter)
    assert tuple(sources) == names
    assert requested == ["LeverBoreProfile"]
    assert sources == {
        names[0]: ("Top", thumb, "IEntity", (("ThumbTapFromDiagonalFlat", faces["top"]),)),
        names[1]: ("Top", rod, "IEntity", (("RodTapFromDiagonalFlat", faces["bottom"]),)),
        names[2]: ("Right", bore, "ISketchSegment", (("LeverBoreFromZFlat", faces["zflat"]),)),
    }


def test_clamp_blanks_every_location_witness_it_creates(monkeypatch) -> None:
    """Exercise the production creation/blanking loop without a native seat."""
    import build_mg_magnifying_clamp as clamp

    created, named, hidden, measured = [], [], [], []
    center, flat = object(), object()
    circle = SimpleNamespace(GetCenterPoint2=lambda: center)
    sources = {
        name: (plane, circle, interface, ((f"Location{number}", flat),))
        for number, (name, plane, interface) in enumerate(zip(
            clamp.REFERENCE_SKETCHES, ("Top", "Top", "Right"),
            ("IEntity", "IEntity", "ISketchSegment"), strict=True,
        ))
    }
    # An extra actual source must also be created AND hidden, not silently
    # dropped by a separate enumeration used only for blanking.
    sources["AdditionalWitness"] = ("Right", circle, "ISketchSegment", ())
    sketch = SimpleNamespace(GetConstrainedStatus=lambda: 3)
    model = SimpleNamespace(GetActiveSketch2=lambda: sketch)

    async def create_sketch(plane):
        created.append(plane)
        return SimpleNamespace(is_success=True, data=None)

    async def exit_sketch():
        return SimpleNamespace(is_success=True, data=None)

    adapter = SimpleNamespace(
        currentModel=model, create_sketch=create_sketch, exit_sketch=exit_sketch,
    )
    monkeypatch.setattr(clamp, "_location_sources", lambda _adapter: sources)
    monkeypatch.setattr(clamp, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(clamp, "_convert_location_source", lambda _adapter, obj, _interface: obj)
    monkeypatch.setattr(clamp, "_tap_placement_points", lambda _adapter: {})
    monkeypatch.setattr(
        clamp, "_measure_location",
        lambda _adapter, point, edge, name: measured.append((point, edge, name)),
    )
    monkeypatch.setattr(clamp, "name_last_feature", lambda _adapter, name: named.append(name))
    monkeypatch.setattr(clamp, "blank_reference_sketches", lambda _adapter, names: hidden.extend(names))
    asyncio.run(clamp._location_profiles(adapter))
    assert created == ["Top", "Top", "Right", "Right"]
    assert named == list(sources)
    assert hidden == named
    assert measured == [(center, flat, f"Location{number}") for number in range(3)]


# cd50a8425 made dimensions_by_feature a required keyword; draw_crankshaft
# kept calling this helper without it, and nothing offline noticed until the
# seat raised TypeError (#960 leaf cr-r1c, drawing:crankshaft).
_REQUIRED_KEYWORDS = frozenset(
    name
    for name, parameter in inspect.signature(
        hidden_sketches.curate_view_dimensions
    ).parameters.items()
    if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    and parameter.default is inspect.Parameter.empty
)


def _hidden_curate_calls_missing_keywords(tree: ast.Module) -> list[tuple[int, list[str]]]:
    """Calls resolved to this module's curate_view_dimensions (a bare name
    imported from it, or an attribute of its module alias) that omit a
    required keyword."""
    names: set[str] = set()
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "_drawing_hidden_sketches":
            names |= {
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "curate_view_dimensions"
            }
        if isinstance(node, ast.Import):
            aliases |= {
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "_drawing_hidden_sketches"
            }
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        routed = (isinstance(func, ast.Name) and func.id in names) or (
            isinstance(func, ast.Attribute)
            and func.attr == "curate_view_dimensions"
            and isinstance(func.value, ast.Name)
            and func.value.id in aliases
        )
        if not routed or any(keyword.arg is None for keyword in node.keywords):
            continue
        absent = sorted(_REQUIRED_KEYWORDS - {keyword.arg for keyword in node.keywords})
        if absent:
            missing.append((node.lineno, absent))
    return missing


def test_the_keyword_guard_flags_a_call_without_dimensions_by_feature() -> None:
    # Positive control: the draw_crankshaft call shape the seat rejected.
    tree = ast.parse(
        "from _drawing_hidden_sketches import curate_view_dimensions\n"
        "curate_view_dimensions(adapter, end, keep=KEEP, view_label='end')\n"
    )
    assert _hidden_curate_calls_missing_keywords(tree) == [
        (2, ["dimensions_by_feature"])
    ]


def _may_import_hidden_sketches(path: Path) -> bool:
    """Whether ``path`` can route a call to curate_view_dimensions at all.

    The guard only follows calls through an import of _drawing_hidden_sketches,
    so a source that never spells the module name cannot be flagged. Python
    NFKC-normalizes identifiers, so non-ASCII text is searched normalized.
    """
    text = path.read_text(encoding="utf-8")
    if not text.isascii():
        text = unicodedata.normalize("NFKC", text)
    return "_drawing_hidden_sketches" in text


def test_every_hidden_sketch_curate_call_passes_its_required_keywords() -> None:
    wrong = {
        path.name: missing
        for path in sorted(_SCRIPTS.glob("*.py"))
        if _may_import_hidden_sketches(path)
        and (missing := _hidden_curate_calls_missing_keywords(_tree(path)))
    }
    assert wrong == {}
