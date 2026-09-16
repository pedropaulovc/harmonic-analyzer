"""SolidWorks-free contract for the targeted model-item import.

``curate_view_dimensions`` used to import every marked dimension of the whole
model into every view and delete what the view did not keep. It now inverts the
source part spec's ``DRAWING_DIMENSIONS`` (``{feature: {dimension names}}``) to
find the features that own the kept names and imports from those alone. These
cases pin the inversion, the two decisions that are invisible in a render — a
view that keeps nothing must not touch COM at all, and a spec that cannot
account for a kept name must fail before the seat is used — and the selection
recipe the import depends on, which fails SILENTLY when it is wrong:
``InsertModelAnnotations3(swImportModelItemsFromSelectedFeature)`` imports
nothing at all unless the drawing view is selected FIRST and the features are
appended to that selection (measured in
``diagnostics/probe_targeted_model_items.py``).
"""

from __future__ import annotations

import pytest

import _drawing_common as drawing_common
import harmonic_base_spec
import tube_frame_spec


class RefusingAdapter:
    """Any COM access is a test failure, not a silent slow path."""

    def __getattr__(self, name: str):
        raise AssertionError(f"COM touched: adapter.{name}")


def test_only_the_features_owning_the_kept_names_are_imported() -> None:
    features = drawing_common._features_owning(
        tube_frame_spec.DRAWING_DIMENSIONS,
        {"Length", "TopChamfer"},
        view_label="length",
    )
    assert features == ("Column", "TopEndBreak")


def test_one_feature_is_selected_once_for_all_of_its_kept_names() -> None:
    """Three kept names on one sketch must not become three selections."""
    assert drawing_common._features_owning(
        tube_frame_spec.DRAWING_DIMENSIONS,
        {"LowerHoleY", "UpperHoleY", "CrossHoleDia"},
        view_label="length",
    ) == ("CrossHoleProfile",)


def test_every_marked_dimension_of_a_real_spec_resolves_to_its_feature() -> None:
    for spec in (tube_frame_spec, harmonic_base_spec):
        owner = drawing_common._feature_by_dimension_name(spec.DRAWING_DIMENSIONS)
        for feature, names in spec.DRAWING_DIMENSIONS.items():
            for name in names:
                assert owner[name] == feature


def test_a_kept_name_no_feature_declares_fails_before_com() -> None:
    with pytest.raises(RuntimeError) as error:
        drawing_common._features_owning(
            tube_frame_spec.DRAWING_DIMENSIONS, {"Length", "Bogus"}, view_label="end"
        )
    assert "end view keeps dimensions no feature declares: ['Bogus']" in str(
        error.value
    )
    assert "declared=['CrossHoleDia', 'Length'" in str(error.value)


def test_a_dimension_two_features_claim_is_a_spec_bug() -> None:
    with pytest.raises(ValueError, match="claimed by features"):
        drawing_common._feature_by_dimension_name(
            {"Profile": {"Bore"}, "Cut": {"Bore"}}
        )


def test_a_view_that_keeps_nothing_imports_nothing() -> None:
    assert (
        drawing_common.curate_view_dimensions(
            RefusingAdapter(),
            object(),
            keep={},
            view_label="end",
            dimensions_by_feature=tube_frame_spec.DRAWING_DIMENSIONS,
        )
        == []
    )


class FakeDimension:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeDisplayDimension:
    def __init__(self, name: str) -> None:
        self._dimension = FakeDimension(name)

    def GetDimension(self):
        return self._dimension


class FakeAnnotation:
    def __init__(self, name: str) -> None:
        self._display = FakeDisplayDimension(name)

    def GetSpecificAnnotation(self):
        return self._display


class FakeComponent:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeView:
    """An ``IView`` double: a name, its root component, and its base view."""

    def __init__(self, name: str, component: str, base: FakeView | None = None) -> None:
        self._name = name
        self._component = FakeComponent(component)
        self._base = base
        self.child_context = []

    def GetName2(self) -> str:
        return self._name

    def GetBaseView(self) -> FakeView | None:
        return self._base

    def RootDrawingComponent2(self, in_child_context: bool):
        self.child_context.append(in_child_context)
        return self._component


class FakeExtension:
    def __init__(self, drawing: FakeDrawing) -> None:
        self._drawing = drawing

    def SelectByID2(self, name, type_name, x, y, z, append, mark, callout, option):
        self._drawing.calls.append(("select", name, type_name, append))
        if self._drawing.kinds.get(name) != type_name:
            return False
        self._drawing.selection.append(name)
        return True


class FakeDrawing:
    """Enough of ``IDrawingDoc``/``IModelDoc2`` to record the import recipe.

    ``InsertModelAnnotations3`` mimics the measured SolidWorks behaviour: the
    selection list must start with the drawing view, and only the FEATURES
    appended after it contribute dimensions.
    """

    def __init__(self, kinds: dict[str, str], dimensions: dict[str, list[str]]) -> None:
        self.kinds = kinds
        self.dimensions = dimensions
        self.calls: list[tuple] = []
        self.selection: list[str] = []
        self.Extension = FakeExtension(self)

    def ActivateView(self, name: str) -> bool:
        self.calls.append(("activate", name))
        return True

    def ClearSelection2(self, append: bool) -> None:
        self.calls.append(("clear",))
        self.selection = []

    def InsertModelAnnotations3(
        self, option, types, all_views, duplicate_dims, hidden, placement
    ):
        self.calls.append(("import", option, types, all_views))
        if not self.selection or self.kinds.get(self.selection[0]) != "DRAWINGVIEW":
            return None  # the real call returns an empty array and imports nothing
        names = [
            name
            for selected in self.selection[1:]
            for name in self.dimensions.get(selected, ())
        ]
        return [FakeAnnotation(name) for name in names]


class FakeAdapter:
    def __init__(self, drawing: FakeDrawing) -> None:
        self.currentModel = drawing

    def _attempt(self, call, default=None):
        return call()

    def _get_attr_or_call(self, obj, name):
        member = getattr(obj, name)
        return member() if callable(member) else member


def _seat(view="Drawing View1", component="tube-frame-1"):
    kinds = {
        view: "DRAWINGVIEW",
        f"AnnulusProfile@{component}@{view}": "SKETCH",
        f"Column@{component}@{view}": "BODYFEATURE",
    }
    dimensions = {
        f"AnnulusProfile@{component}@{view}": ["OuterDia"],
        f"Column@{component}@{view}": ["Length", "TopChamfer"],
    }
    drawing = FakeDrawing(kinds, dimensions)
    return FakeAdapter(drawing), drawing, FakeView(view, component)


def test_the_view_is_selected_before_the_features_are_appended() -> None:
    adapter, drawing, view = _seat()
    named = drawing_common.insert_feature_dimensions(
        adapter, view, ("AnnulusProfile", "Column")
    )
    assert [name for name, _ in named] == ["OuterDia", "Length", "TopChamfer"]
    selects = [call for call in drawing.calls if call[0] == "select"]
    assert selects[0] == ("select", "Drawing View1", "DRAWINGVIEW", False)
    assert all(append for _, _, _, append in selects[1:])
    assert drawing.calls.count(("import", 1, 0x8000 | 0x20000, False)) == 1
    # One import, not one per feature: both owners ride the same selection.
    assert sum(call[0] == "import" for call in drawing.calls) == 1


def test_a_body_feature_owner_is_retried_after_the_sketch_type() -> None:
    """An owner can be a sketch or a body feature; an empty Type resolves neither."""
    adapter, drawing, view = _seat()
    drawing_common.insert_feature_dimensions(adapter, view, ("Column",))
    attempted = [
        (name, type_name)
        for kind, name, type_name, _ in (
            call for call in drawing.calls if call[0] == "select"
        )
    ]
    assert attempted == [
        ("Drawing View1", "DRAWINGVIEW"),
        ("Column@tube-frame-1@Drawing View1", "SKETCH"),
        ("Column@tube-frame-1@Drawing View1", "BODYFEATURE"),
    ]


def test_a_feature_of_neither_kind_fails_loudly() -> None:
    adapter, drawing, view = _seat()
    with pytest.raises(RuntimeError, match="as a SKETCH or a BODYFEATURE"):
        drawing_common.insert_feature_dimensions(adapter, view, ("Missing",))


def test_a_derived_view_is_qualified_by_its_base_view() -> None:
    """A section answers to none of its own model-item paths; its base does.

    Measured on the built top-frame drawing:
    ``"CapRecessProfile@top-frame-7@Section View A-A"`` refuses as a SKETCH and
    as a BODYFEATURE (and for every instance suffix 1..20), the same feature
    resolves through the section's base view, and the import still lands in the
    section because ``InsertModelAnnotations3`` follows the SELECTED view.
    """
    adapter, drawing, base = _seat(view="Drawing View7", component="top-frame-7")
    section = FakeView("Section View A-A", "top-frame-7", base=base)
    drawing.kinds["Section View A-A"] = "DRAWINGVIEW"
    named = drawing_common.insert_feature_dimensions(
        adapter, section, ("AnnulusProfile",)
    )
    assert [name for name, _ in named] == ["OuterDia"]
    assert [
        (name, type_name)
        for _, name, type_name, _ in (
            call for call in drawing.calls if call[0] == "select"
        )
    ] == [
        ("Section View A-A", "DRAWINGVIEW"),
        ("AnnulusProfile@top-frame-7@Section View A-A", "SKETCH"),
        ("AnnulusProfile@top-frame-7@Section View A-A", "BODYFEATURE"),
        ("AnnulusProfile@top-frame-7@Drawing View7", "SKETCH"),
    ]
    assert ("activate", "Section View A-A") in drawing.calls


def test_the_component_qualifier_is_read_back_per_view() -> None:
    """The middle qualifier is the view's own root component, never the part stem."""
    adapter, drawing, view = _seat(view="Drawing View2", component="tube-frame-2")
    drawing_common.insert_feature_dimensions(adapter, view, ("AnnulusProfile",))
    assert view.child_context == [False]
    assert (
        "select",
        "AnnulusProfile@tube-frame-2@Drawing View2",
        "SKETCH",
        True,
    ) in drawing.calls
