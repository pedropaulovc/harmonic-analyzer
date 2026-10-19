"""SolidWorks-free contract for ``_drawing_hidden_sketches``.

The fakes mimic what the summing lever measured on a real seat (probe runs
20260924T160303083Z-67cebdcd and 20260924T170431016Z-c0514e35, r21).  A
part-hidden sketch's dimensions import only while the VIEW shows it.
Blanking it again would hide them, so the module never does.  A derived view
is handled by ``part_sketches_shown`` instead.
"""

from __future__ import annotations

import ast
import functools
import importlib
import inspect
from pathlib import Path

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


# --- routing guard: which drawings must use this module --------------------
# #743 canary (r743-canary, drawing:cylinder_gear_shaft): the part blanked its
# DomeReference sketch and the drawing kept DomeHeight, but it imported
# curate_view_dimensions from what is now _drawing_dimension_import, so
# DomeHeight never arrived.
# Run r743-diag-a (fbaf8bb09) swapped only the import and the dimension
# imported. Nothing stopped the wrong helper, so this guard does.
_SCRIPTS = Path(hidden_sketches.__file__).resolve().parent


@functools.cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _reference_sketches(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "REFERENCE_SKETCHES"
            for target in node.targets
        ):
            return set(ast.literal_eval(node.value))
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "REFERENCE_SKETCHES" for alias in node.names
        ):
            return set(importlib.import_module(node.module).REFERENCE_SKETCHES)
    raise LookupError("blank_sketch on a computed name, with no REFERENCE_SKETCHES to resolve it")


def _imported_name(tree: ast.Module, name: str) -> str | None:
    """A sketch name the build imports as a module constant (build_pinion_spring's
    ``FREE_FORM_SKETCH`` from its spec), or None when it imports no such name."""
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if (alias.asname or alias.name) == name:
                return getattr(importlib.import_module(node.module), alias.name)
    return None


def _helper_blanked_parameters(module: str, function: str) -> dict[str, str | None]:
    """Parameters a repo helper passes to blank_reference_sketches as its
    sketch names (paper_drive_stock_native.author_span blanks its own
    ``feature``), each with its string default, or None without one."""
    path = _SCRIPTS / f"{module}.py"
    if not path.exists():
        return {}
    for node in _tree(path).body:
        if not (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function):
            continue
        arguments = node.args
        positional = arguments.posonlyargs + arguments.args
        defaults: dict[str, ast.expr | None] = dict.fromkeys(a.arg for a in positional + arguments.kwonlyargs)
        defaults.update(zip((a.arg for a in positional[len(positional) - len(arguments.defaults):]), arguments.defaults))
        defaults.update((a.arg, d) for a, d in zip(arguments.kwonlyargs, arguments.kw_defaults) if d is not None)
        blanked: dict[str, str | None] = {}
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and _called_name(call) == "blank_reference_sketches"):
                continue
            sketches = call.args[1]
            for item in sketches.elts if isinstance(sketches, (ast.Tuple, ast.List)) else ():
                if isinstance(item, ast.Name) and item.id in defaults:
                    default = defaults[item.id]
                    blanked[item.id] = default.value if isinstance(default, ast.Constant) else None
        return blanked
    return {}

def _literal_named_value(path: Path, name: str, visited=None):
    """Read a literal constant through explicit imports; never execute source."""
    visited = set() if visited is None else visited
    key = (path, name)
    if key in visited or not path.is_file():
        raise LookupError(f"cannot resolve literal {name} from {path}")
    visited.add(key)
    for node in _tree(path).body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    return _literal_named_value(
                        _SCRIPTS / f"{node.module}.py", alias.name, visited
                    )
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise LookupError(f"cannot resolve literal {name} from {path}")


def _loop_bound_names(path: Path, owner: ast.AST, call: ast.Call, name: str) -> set[str]:
    """Resolve a dict items()/values() loop's actual string-value binding."""
    for loop in ast.walk(owner):
        if not isinstance(loop, ast.For) or call not in ast.walk(loop):
            continue
        iterator = loop.iter
        if not (
            isinstance(iterator, ast.Call) and isinstance(iterator.func, ast.Attribute)
            and isinstance(iterator.func.value, ast.Name)
        ):
            continue
        target = loop.target
        values = None
        if iterator.func.attr == "values" and isinstance(target, ast.Name) and target.id == name:
            values = _literal_named_value(path, iterator.func.value.id).values()
        elif iterator.func.attr == "items" and isinstance(target, (ast.Tuple, ast.List)):
            for index, item in enumerate(target.elts):
                if isinstance(item, ast.Name) and item.id == name:
                    mapping = _literal_named_value(path, iterator.func.value.id)
                    values = mapping.keys() if index == 0 else mapping.values()
        if values is not None:
            result = set(values)
            if not all(isinstance(value, str) for value in result):
                raise LookupError(f"non-string hidden sketch binding {name}")
            return result
    return set()



def _helper_fixed_blanked_sketches(module: str, function: str) -> set[str]:
    """Names a called author blanks directly, excluding its name parameters."""
    path = _SCRIPTS / f"{module}.py"
    if not path.is_file():
        return set()
    tree = _tree(path)
    names: set[str] = set()
    for owner in tree.body:
        if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) or owner.name != function:
            continue
        parameters = {
            arg.arg for arg in owner.args.posonlyargs + owner.args.args + owner.args.kwonlyargs
        }
        for call in ast.walk(owner):
            if not isinstance(call, ast.Call) or _called_name(call) != "blank_reference_sketches":
                continue
            sketches = call.args[1]
            if not isinstance(sketches, (ast.Tuple, ast.List)):
                names |= _reference_sketches(tree)
                continue
            for item in sketches.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    names.add(item.value)
                elif isinstance(item, ast.Name) and item.id in parameters:
                    continue  # Resolved against the author call by the parameter guard.
                elif isinstance(item, ast.Name) and (values := _declared_strings(path, item.id, set())):
                    names |= values
                elif isinstance(item, ast.Name) and (values := _loop_bound_names(path, owner, call, item.id)):
                    names |= values
                else:
                    names |= _reference_sketches(tree)
    return names


def _blanked_sketches(build: Path) -> set[str]:
    """Every sketch a part build hides with _sketch.blank_sketch, or with
    _sketch.blank_reference_sketches (which calls it per sketch) over a
    literal tuple or the build's REFERENCE_SKETCHES, directly or through a
    repo helper that blanks the sketch it authors (keyword or default name)."""
    tree = _tree(build)
    helpers = {
        alias.asname or alias.name: (node.module, alias.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
    }
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = _called_name(node)
        if called == "blank_reference_sketches":
            sketches = node.args[1]
            if isinstance(sketches, (ast.Tuple, ast.List)) and all(
                isinstance(item, ast.Constant) for item in sketches.elts
            ):
                names |= {item.value for item in sketches.elts}
                continue
            names |= _reference_sketches(tree)
            continue
        if called != "blank_sketch":
            if isinstance(node.func, ast.Name) and node.func.id in helpers:
                names |= _helper_fixed_blanked_sketches(*helpers[node.func.id])
                passed = {k.arg: k.value for k in node.keywords if k.arg}
                for parameter, default in _helper_blanked_parameters(*helpers[node.func.id]).items():
                    value = passed.get(parameter)
                    if isinstance(value, ast.Constant):
                        names.add(value.value)
                    elif value is None and default is not None:
                        names.add(default)
                    else:
                        raise LookupError(f"{called} blanks a computed sketch name ({parameter})")
            continue
        sketch = node.args[1]
        if isinstance(sketch, ast.Constant):
            names.add(sketch.value)
            continue
        if isinstance(sketch, ast.Name) and (imported := _imported_name(tree, sketch.id)):
            names.add(imported)
            continue
        names |= _reference_sketches(tree)
    for path, owner, _nodes, _imports in _reachable_functions(build):
        names |= _helper_fixed_blanked_sketches(path.stem, owner.name)
    return names


def _declared_strings(
    path: Path, name: str, visited: set[tuple[Path, str]]
) -> set[str]:
    """Follow only a named constant's declaration, not an imported module's API."""
    key = (path, name)
    if key in visited or not path.is_file():
        return set()
    visited.add(key)
    tree = _tree(path)
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    return _declared_strings(_SCRIPTS / f"{node.module}.py", alias.name, visited)
        if value is not None:
            strings = {
                child.value for child in ast.walk(value)
                if isinstance(child, ast.Constant) and isinstance(child.value, str)
            }
            for child in ast.walk(value):
                if isinstance(child, ast.Name):
                    strings |= _declared_strings(path, child.id, visited)
            return strings
    return set()


def _strings_read_by(draw: Path) -> set[str]:
    """Drawing/helper strings, including constants those helpers import by name."""
    trees = [_tree(draw)]
    for node in trees[0].body:
        if isinstance(node, ast.ImportFrom):
            modules = [node.module]
        elif isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        else:
            continue
        trees += [_tree(_SCRIPTS / f"{m}.py") for m in modules if m and (_SCRIPTS / f"{m}.py").exists()]
    strings = {
        node.value
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for tree in trees:
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    strings |= _declared_strings(
                        _SCRIPTS / f"{node.module}.py", alias.name, set()
                    )
    return strings


def _reachable_functions(path: Path):
    """Called repo functions, including named callbacks and partial's first arg."""
    visited: set[tuple[Path, int]] = set()

    def follows(path: Path, scope: ast.AST, enclosing: dict[str, ast.AST]):
        key = (path, scope.lineno)
        if key in visited:
            return
        visited.add(key)
        pending = list(ast.iter_child_nodes(scope))
        nodes = []
        while pending:
            node = pending.pop()
            nodes.append(node)
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                pending.extend(ast.iter_child_nodes(node))
        functions = {
            **enclosing,
            **{node.name: node for node in nodes
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))},
        }
        imports: dict[str, tuple[str, str | None]] = {}
        for node in [*_tree(path).body, *nodes]:
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.update((alias.asname or alias.name, (node.module, alias.name))
                               for alias in node.names)
            elif isinstance(node, ast.Import):
                imports.update((alias.asname or alias.name, (alias.name, None))
                               for alias in node.names)
        yield path, scope, nodes, imports
        for call in nodes:
            if not isinstance(call, ast.Call):
                continue
            for reference in (call.func, *call.args, *(kw.value for kw in call.keywords)):
                if isinstance(reference, ast.Name) and reference.id in functions:
                    yield from follows(path, functions[reference.id], functions)
                    continue
                target = _import_target(reference, imports)
                if target is None:
                    continue
                module, name = target
                # These are terminal APIs, not additional drawing/model owners.
                if module in {"_drawing_hidden_sketches", "_drawing_dimension_import", "_sketch"}:
                    continue
                helper = _SCRIPTS / f"{module}.py"
                if not helper.is_file():
                    continue
                definitions = {
                    node.name: node for node in _tree(helper).body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if name in definitions:
                    yield from follows(helper, definitions[name], definitions)

    definitions = {
        node.name: node for node in _tree(path).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if "build" in definitions:
        yield from follows(path, definitions["build"], definitions)


def _import_target(reference: ast.AST, imports):
    if isinstance(reference, ast.Name):
        return imports.get(reference.id)
    if isinstance(reference, ast.Attribute) and isinstance(reference.value, ast.Name):
        imported = imports.get(reference.value.id)
        if imported and imported[1] is None:
            return imported[0], reference.attr
    return None


def _curates_through_hidden_sketches(draw: Path) -> bool:
    """Require an actual canonical call in a reachable drawing owner."""
    return any(
        isinstance(node, ast.Call)
        and _import_target(node.func, imports)
        == ("_drawing_hidden_sketches", "curate_view_dimensions")
        for _path, _scope, nodes, imports in _reachable_functions(draw)
        for node in nodes
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (
            "from supplier import annotate as owned\n"
            "async def build(adapter):\n"
            "    owned(adapter)\n",
            True,
        ),
        (
            "import supplier as owned\n"
            "async def build(adapter):\n"
            "    owned.annotate(adapter)\n",
            True,
        ),
        (
            "from supplier import annotate\n"
            "def supplier_dimensions(adapter):\n"
            "    annotate(adapter)\n"
            "async def build(adapter):\n"
            "    export(adapter, supplier_dimensions=supplier_dimensions)\n",
            True,
        ),
        (
            "from _drawing_hidden_sketches import curate_view_dimensions\n"
            "from supplier import bypass\n"
            "async def build(adapter):\n"
            "    bypass(adapter)\n",
            False,
        ),
        (
            "from supplier import annotate, bypass\n"
            "def unused(adapter):\n"
            "    annotate(adapter)\n"
            "async def build(adapter):\n"
            "    bypass(adapter)\n",
            False,
        ),
        (
            "from supplier import cycle\n"
            "async def build(adapter):\n"
            "    cycle(adapter)\n",
            False,
        ),
    ],
    ids=("called-helper", "module-alias", "callback", "unused-import", "unused-helper", "cycle"),
)
def test_hidden_routing_follows_only_reachable_curators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, expected: bool
) -> None:
    monkeypatch.setitem(globals(), "_SCRIPTS", tmp_path)
    (tmp_path / "supplier.py").write_text(
        "from _drawing_hidden_sketches import curate_view_dimensions as hidden\n"
        "from _drawing_dimension_import import curate_view_dimensions as direct\n"
        "def annotate(adapter):\n"
        "    hidden(adapter, view, keep={}, view_label='stock', dimensions_by_feature={})\n"
        "def bypass(adapter):\n"
        "    direct(adapter, view, keep={}, view_label='stock')\n"
        "def cycle(adapter):\n"
        "    cycle(adapter)\n",
        encoding="utf-8",
    )
    drawing = tmp_path / "draw_fixture.py"
    drawing.write_text(body, encoding="utf-8")
    assert _curates_through_hidden_sketches(drawing) is expected


def test_hidden_inventory_follows_the_called_authors_imported_constants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(globals(), "_SCRIPTS", tmp_path)
    (tmp_path / "source_names.py").write_text(
        "DIAMETER = 'SupplierDiameterReference'\n"
        "WALL = 'SupplierWallReference'\n",
        encoding="utf-8",
    )
    (tmp_path / "author.py").write_text(
        "from source_names import DIAMETER, WALL\n"
        "def dowel(adapter):\n"
        "    blank_reference_sketches(adapter, (DIAMETER,))\n"
        "def spring(adapter):\n"
        "    blank_reference_sketches(adapter, (WALL,))\n",
        encoding="utf-8",
    )
    build = tmp_path / "build_fixture.py"
    build.write_text(
        "from author import dowel\n"
        "async def build(adapter):\n"
        "    dowel(adapter)\n",
        encoding="utf-8",
    )
    assert _blanked_sketches(build) == {"SupplierDiameterReference"}
    (tmp_path / "drawing_helper.py").write_text(
        "from source_names import DIAMETER\n"
        "DIMENSIONS = {DIAMETER: {'Diameter'}}\n",
        encoding="utf-8",
    )
    draw = tmp_path / "draw_fixture.py"
    draw.write_text("from drawing_helper import DIMENSIONS\n", encoding="utf-8")
    read = _strings_read_by(draw)
    assert "SupplierDiameterReference" in read
    assert "SupplierWallReference" not in read


@pytest.mark.parametrize("registered", (False, True))
def test_computed_helper_blanking_requires_a_reference_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registered: bool
) -> None:
    monkeypatch.setitem(globals(), "_SCRIPTS", tmp_path)
    declaration = "REFERENCE_SKETCHES = ('DeclaredReference',)\n" if registered else ""
    (tmp_path / "author.py").write_text(
        declaration
        + "def author(adapter):\n"
        "    feature = make_reference_name()\n"
        "    blank_reference_sketches(adapter, (feature,))\n",
        encoding="utf-8",
    )
    build = tmp_path / "build_fixture.py"
    build.write_text(
        "from author import author\n"
        "async def build(adapter):\n"
        "    author(adapter)\n",
        encoding="utf-8",
    )
    if registered:
        assert _blanked_sketches(build) == {"DeclaredReference"}
    else:
        with pytest.raises(LookupError, match="no REFERENCE_SKETCHES"):
            _blanked_sketches(build)


@pytest.mark.parametrize("binding", ("_, feature in FEATURES.items()", "feature in FEATURES.values()"))
def test_computed_author_loop_resolves_actual_values_without_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, binding: str
) -> None:
    monkeypatch.setitem(globals(), "_SCRIPTS", tmp_path)
    (tmp_path / "names.py").write_text(
        "FEATURES = {'Front': 'FrontReference', 'Top': 'TopReference'}\n",
        encoding="utf-8",
    )
    (tmp_path / "author.py").write_text(
        "from names import FEATURES\n"
        "def author(adapter):\n"
        f"    for {binding}:\n"
        "        blank_reference_sketches(adapter, (feature,))\n"
        "async def save(adapter):\n"
        "    author(adapter)\n",
        encoding="utf-8",
    )
    build = tmp_path / "build_fixture.py"
    build.write_text(
        "from functools import partial\n"
        "from author import save\n"
        "async def build(adapter):\n"
        "    export(adapter, saver=partial(save, adapter))\n",
        encoding="utf-8",
    )
    assert _blanked_sketches(build) == {"FrontReference", "TopReference"}


def test_supplier_authors_blank_exactly_their_declared_reference_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from _supplier_pin_data import DIAMETER_FEATURE, MATING_HOLE_FEATURE, WALL_FEATURE
    from _supplier_screw_reference_names import FEATURE_BY_PLANE, REFERENCE_SKETCHES

    dowel = _helper_fixed_blanked_sketches(
        "_supplier_pin_model", "author_supplier_dowel_references"
    )
    spring = _helper_fixed_blanked_sketches(
        "_supplier_pin_model", "author_supplier_spring_pin_references"
    )
    assert dowel == {DIAMETER_FEATURE}
    assert spring == {MATING_HOLE_FEATURE, WALL_FEATURE}
    # Both directions: no unowned declaration and no undeclared hidden source.
    assert dowel | spring == _reference_sketches(_tree(_SCRIPTS / "_supplier_pin_model.py"))
    def no_declaration_fallback(_tree):
        raise AssertionError("actual author binding must resolve without metadata fallback")

    monkeypatch.setitem(globals(), "_reference_sketches", no_declaration_fallback)
    screw = _helper_fixed_blanked_sketches(
        "_supplier_screw_reference", "add_supplier_reference_sketch"
    )
    assert screw == set(REFERENCE_SKETCHES) == set(FEATURE_BY_PLANE.values())


def test_clamp_screw_inventory_and_routing_reject_a_wrong_curator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = _SCRIPTS / "build_vn_clamp_screw.py"
    draw = _SCRIPTS / "draw_vn_clamp_screw.py"
    assert "SupplierReference" in _blanked_sketches(build)
    assert "SupplierReference" in _drawings_reading_blanked_sketches()["vn_clamp_screw"]
    assert _curates_through_hidden_sketches(draw)

    original_tree = _tree

    class WrongCurator(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module == "_drawing_hidden_sketches":
                node.module = "_drawing_dimension_import"
            return node

    def wrong_tree(path: Path):
        if path.name == "_supplier_screw_dimensions.py":
            return WrongCurator().visit(ast.parse(path.read_text(encoding="utf-8")))
        return original_tree(path)

    monkeypatch.setitem(globals(), "_tree", wrong_tree)
    assert not _curates_through_hidden_sketches(draw)


@functools.cache
def _drawings_reading_blanked_sketches() -> dict[str, frozenset[str]]:
    from _drawing_registry import DRAWINGS

    found = {}
    for spec in DRAWINGS:
        build = _SCRIPTS / f"build_{spec.part}.py"
        draw = _SCRIPTS / spec.script_name
        if not (build.exists() and draw.exists()):
            continue
        blanked = _blanked_sketches(build)
        if not blanked:
            continue
        read = blanked & _strings_read_by(draw)
        if read:
            found[spec.name] = frozenset(read)
    return found


def test_the_routing_guard_sees_the_known_hidden_sketch_drawings() -> None:
    """The guard below is only as good as its detection: pin what it finds."""
    found = _drawings_reading_blanked_sketches()
    assert {
        "dt_arbor_pedestal",
        "dt_cone_gear",
        "dt_cone_pivot_post",
        "dt_cone_tip_block",
        "dt_cylinder_gear_shaft",
        "fr_harmonic_base",
        "dt_pinion_spring",
    } <= set(found)
    assert found["dt_cylinder_gear_shaft"] == {"DomeReference"}
    # Blanked with _sketch.blank_reference_sketches, not blank_sketch.
    assert found["dt_cone_pivot_post"] == {
        "BoreSpacingReference",
        "JournalPlanReference",
        "CrankBossStationReference",
        "ConeBossStationReference",
    }
    # Blanked inside paper_drive_stock_native.author_span/author_root_envelope
    # (PD farm run 9, drawing:pd_rack_pinion and :pd_transgear_feed_pinion:
    # SpanProfile/RootInspectionProfile dimensions missing from the import).
    assert found["pd_rack_pinion"] == {"SpanProfile", "RootInspectionProfile"}
    assert found["pd_transgear_feed_pinion"] == {"SpanProfile"}
    assert found["pd_transgear_knob_shaft"] == {"SpanProfile", "RootInspectionProfile"}
    # Separate supplier stock views must route their hidden reference dimensions
    # through the same per-view visibility handling as fabricated-part references.
    assert found["vn_boss_hook"] == {"SupplierNominalStockProfile"}
    assert found["vn_spring_hook"] == {"SupplierStockAxis"}
    assert "SupplierMaxLimitProfile" in found["vn_post_mount_screw"]


def test_a_drawing_of_a_part_hidden_sketch_curates_through_this_module() -> None:
    """A drawing that reads a sketch its part blanks must curate through
    _drawing_hidden_sketches: _drawing_dimension_import's targeted import delivers
    nothing from a hidden childless sketch."""
    from _drawing_registry import DRAWINGS_BY_NAME

    wrong = {
        name: sorted(sketches)
        for name, sketches in _drawings_reading_blanked_sketches().items()
        if not _curates_through_hidden_sketches(
            _SCRIPTS / DRAWINGS_BY_NAME[name].script_name
        )
    }
    assert wrong == {}


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


def test_every_hidden_sketch_curate_call_passes_its_required_keywords() -> None:
    wrong = {
        path.name: missing
        for path in sorted(_SCRIPTS.glob("*.py"))
        if (missing := _hidden_curate_calls_missing_keywords(_tree(path)))
    }
    assert wrong == {}
