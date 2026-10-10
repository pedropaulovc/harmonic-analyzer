"""The simplified-view configuration policy (SolidWorks-free)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _assembly
import _simplified_part
from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    set_view_exploded_state,
    view_configuration,
)
from _simplified_bom import child_bom_identity
from _simplified_names import is_simplified, simplified_comment, simplified_name

WIREFRAME, HLV, HLR, SHADED, SHADED_EDGES = 0, 1, 2, 3, 7
FACETED_WIREFRAME, FACETED_HLV, FACETED_HLR = 4, 5, 6
# Every swDisplayMode_e that inks edges.
EDGE_MODES = [WIREFRAME, HLV, HLR, FACETED_WIREFRAME, FACETED_HLV, FACETED_HLR, SHADED_EDGES]
DOCUMENT, CONFIGURATION, PARENT, USER = 1, 2, 4, 8


class FakeView:
    """An IView whose configuration switch lands only when the drawing rebuilds.

    ``ShowExploded`` shows the explode the referenced configuration owns (one
    of ``explodes``); the explode shown does not follow a later configuration
    switch, so a view exploded before its switch shows the wrong one."""

    def __init__(
        self,
        scale: tuple[float, float],
        orientation: str,
        mode: int,
        configuration: str = ASSEMBLY_VIEW_CONFIGURATION,
        *,
        accepts: bool = True,
        explodes: frozenset[str] = frozenset(
            {ASSEMBLY_VIEW_CONFIGURATION, SIMPLIFIED_VIEW_CONFIGURATION}
        ),
    ) -> None:
        self.ScaleRatio = scale
        self.orientation = orientation
        self.mode = mode
        self.configuration = configuration
        self.accepts = accepts
        self.pending: str | None = None
        self.explodes = explodes
        self.exploded_in: str | None = None

    def ShowExploded(self, show: bool) -> bool:
        if not show:
            self.exploded_in = None
            return True
        if self.configuration not in self.explodes:
            return False
        self.exploded_in = self.configuration
        return True

    def IsExploded(self) -> bool:
        return self.exploded_in is not None

    def GetOrientationName(self) -> str:
        return self.orientation

    def GetDisplayMode2(self) -> int:
        return self.mode

    @property
    def ReferencedConfiguration(self) -> str:
        return self.configuration

    @ReferencedConfiguration.setter
    def ReferencedConfiguration(self, value: str) -> None:
        if self.accepts:
            self.pending = value


class FakeDrawing:
    """One sheet of ``FakeView``s; ``EditRebuild3`` regenerates them.

    A configuration switch that lands once the drawing has a BOM table
    (``bom_inserted``) dirties the source assembly: farm probes on #1102 read
    the drive-train source dirty after the rebuild of the first switch after
    ``insert_bom_table``, and the drawing save wrote it. ``dirtied_source``
    names each such switch."""

    def __init__(self, views: list[FakeView]) -> None:
        self.views = views
        self.rebuilds = 0
        self.bom_inserted = False
        self.dirtied_source: list[str] = []

    def EditRebuild3(self) -> bool:
        self.rebuilds += 1
        for view in self.views:
            if view.pending is not None:
                if self.bom_inserted:
                    self.dirtied_source.append(f"{view.configuration} -> {view.pending}")
                view.configuration, view.pending = view.pending, None
        return True

    def GetSheetNames(self) -> list[str]:
        return ["Sheet1"]

    def Sheet(self, _name: str) -> SimpleNamespace:
        return SimpleNamespace(GetViews=lambda: list(self.views))


def test_the_simplified_view_configuration_is_the_derived_default() -> None:
    assert SIMPLIFIED_VIEW_CONFIGURATION == simplified_name("Default") == "Default Simplified"
    assert is_simplified(SIMPLIFIED_VIEW_CONFIGURATION)
    assert not is_simplified(ASSEMBLY_VIEW_CONFIGURATION)


@pytest.mark.parametrize("mode", EDGE_MODES)
@pytest.mark.parametrize(
    ("scale", "expected"),
    [
        ((1.0, 2.0), SIMPLIFIED_VIEW_CONFIGURATION),  # the boundary is inclusive
        ((2.0, 4.0), SIMPLIFIED_VIEW_CONFIGURATION),  # the ratio, not the numbers
        ((1.0, 3.0), SIMPLIFIED_VIEW_CONFIGURATION),
        ((1.0, 8.0), SIMPLIFIED_VIEW_CONFIGURATION),
        ((2.0, 3.0), ASSEMBLY_VIEW_CONFIGURATION),
        ((1.0, 1.0), ASSEMBLY_VIEW_CONFIGURATION),
        ((2.0, 1.0), ASSEMBLY_VIEW_CONFIGURATION),
    ],
)
def test_a_view_that_inks_edges_is_simplified_at_one_to_two_or_smaller(
    mode, scale, expected
) -> None:
    assert view_configuration(scale, mode) == expected


def test_a_pure_shaded_view_keeps_full_detail() -> None:
    """Tone without edge ink: the teeth never print as a black mass."""
    assert view_configuration((1.0, 8.0), SHADED) == ASSEMBLY_VIEW_CONFIGURATION


@pytest.mark.parametrize("mode", EDGE_MODES)
def test_only_the_designated_full_detail_view_is_exempt(mode) -> None:
    """An exploded, BOM-bearing or ballooned view is not exempt: it shows the
    simplified configuration's own explode, and its components carry their
    parents' BOM identity."""
    assert view_configuration((1.0, 8.0), mode) == SIMPLIFIED_VIEW_CONFIGURATION
    assert (
        view_configuration((1.0, 8.0), mode, ViewRole.FULL_DETAIL)
        == ASSEMBLY_VIEW_CONFIGURATION
    )


def test_an_unknown_display_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown"):
        view_configuration((1.0, 8.0), -1)


@pytest.mark.parametrize("scale", [(0.0, 2.0), (1.0, 0.0), (-1.0, 2.0)])
def test_a_degenerate_scale_is_refused(scale) -> None:
    with pytest.raises(ValueError, match="positive"):
        view_configuration(scale, HLR)


@pytest.mark.parametrize(
    ("parent", "grandparent", "child"),
    [
        # Document name: the child already prints the file name.
        ((DOCUMENT, "", False, "d", True), None, (DOCUMENT, "", False, "d", True)),
        # Its own name would print "<P> Simplified": link to the parent instead.
        ((CONFIGURATION, "", False, "d", True), None, (PARENT, "", False, "d", True)),
        # A linked parent prints ITS parent's name; a link would print "T24".
        ((PARENT, "", False, "d", True), "Default", (USER, "Default", True, "d", True)),
        # User specified: the alternate name is copied with it.
        ((USER, "MHA-1", True, "d", False), None, (USER, "MHA-1", True, "d", False)),
    ],
)
def test_a_derived_configuration_prints_its_parents_part_number(
    parent, grandparent, child
) -> None:
    assert child_bom_identity(parent, "T24", grandparent) == child


@pytest.mark.parametrize(
    ("parent", "grandparent"),
    [((PARENT, "", False, "", False), None), ((16, "", False, "", False), "Default")],
)
def test_an_unresolvable_part_number_is_refused(parent, grandparent) -> None:
    with pytest.raises(ValueError, match="T24"):
        child_bom_identity(parent, "T24", grandparent)


class FakeConfiguration:
    def __init__(
        self,
        name: str,
        parent: FakeConfiguration | None = None,
        *,
        comment: str = "",
        source: int = DOCUMENT,
    ) -> None:
        self.Name = name
        self.parent = parent
        self.Comment = comment
        self.BOMPartNoSource = source
        self.AlternateName = ""
        self.UseAlternateNameInBOM = False
        self.Description = ""
        self.UseDescriptionInBOM = False

    def GetParent(self) -> FakeConfiguration | None:
        return self.parent


class FakeModel:
    """A part or assembly document with configurations (and components)."""

    def __init__(self, *configurations: FakeConfiguration, components=()) -> None:
        self.configurations = {item.Name: item for item in configurations}
        self.components = list(components)
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=configurations[0], AddConfiguration2=self._add
        )
        self.Extension = SimpleNamespace(
            CustomPropertyManager=lambda _name: SimpleNamespace(GetNames=lambda: ())
        )

    def _add(self, name, comment, _alternate, _options, parent, _description, _rebuild):
        created = FakeConfiguration(name, self.configurations[parent], comment=comment)
        self.configurations[name] = created
        return created

    def GetConfigurationNames(self) -> list[str]:
        return list(self.configurations)

    def GetConfigurationByName(self, name: str) -> FakeConfiguration | None:
        return self.configurations.get(name)

    def ShowConfiguration2(self, name: str) -> bool:
        self.ConfigurationManager.ActiveConfiguration = self.configurations[name]
        return True

    def GetComponents(self, _top_level: bool) -> list[FakeComponent]:
        return self.components


class FakeComponent:
    def __init__(self, name: str, path: str, model: FakeModel, referenced: str) -> None:
        self.Name2 = name
        self.path = path
        self.model = model
        self.ReferencedConfiguration = referenced

    def GetPathName(self) -> str:
        return self.path

    def IsSuppressed(self) -> bool:
        return False

    def GetModelDoc2(self) -> FakeModel:
        return self.model


def test_a_linked_configurations_simplified_child_prints_the_root_name() -> None:
    root = FakeConfiguration("Default", source=CONFIGURATION)
    linked = FakeConfiguration("T24", root, source=PARENT)
    child = FakeConfiguration("T24 Simplified", linked)
    _simplified_part._copy_bom_identity(FakeModel(root, linked, child), "T24", child.Name)
    assert (child.BOMPartNoSource, child.AlternateName, child.UseAlternateNameInBOM) == (
        USER,
        "Default",
        True,
    )


def _assembly_model(*components: FakeComponent) -> FakeModel:
    default = FakeConfiguration("Default")
    return FakeModel(default, components=components)


def _sync(model: FakeModel, paths: dict[str, FakeModel]) -> int:
    app = SimpleNamespace(GetConfigurationNames=lambda path: paths[path].GetConfigurationNames())
    adapter = SimpleNamespace(currentModel=model, swApp=app)
    return _assembly.sync_simplified_configuration(adapter, "fixture", verify=False)


def test_a_childs_changed_simplified_geometry_forces_the_assembly_save() -> None:
    t24 = FakeConfiguration("T24")
    gear_simplified = FakeConfiguration("T24 Simplified", t24, comment=simplified_comment("Teeth"))
    gear = FakeModel(t24, gear_simplified)
    sub = _assembly_model(FakeComponent("gear-1", "gear.SLDPRT", gear, "T24"))
    top = _assembly_model(FakeComponent("sub-1", "sub.SLDASM", sub, "Default"))
    paths = {"gear.SLDPRT": gear, "sub.SLDASM": sub}
    assert _sync(sub, paths) > 0  # created, re-pointed
    assert _sync(top, paths) > 0
    # A settled refresh leaves both byte-stable.
    assert (_sync(sub, paths), _sync(top, paths)) == (0, 0)
    # The part recipe now suppresses more: Default and every component's
    # referenced configuration are unchanged, yet both levels must re-save.
    gear_simplified.Comment = simplified_comment("Teeth, Chamfer")
    assert (_sync(sub, paths), _sync(top, paths)) == (1, 1)
    assert (_sync(sub, paths), _sync(top, paths)) == (0, 0)


class FakeAssemblyFile:
    """A saved ``.SLDASM``: whether each configuration's saved data is stale.

    paper-drive (c85a21ec4) reconciled "was 1", read NeedsRebuild2=0 in memory
    after its EditRebuild3 + Save3, and still opened with NeedsRebuild2=1 for
    verify:soundness, while the same reconcile held on every build before
    ``Default Simplified`` existed. The double models that: one stale saved
    configuration makes the document open dirty, in memory NeedsRebuild2
    reads only the active configuration, and a plain Save3 writes only the
    active configuration's data plus the rebuild-save-marked ones'.
    """

    def __init__(self, stale: dict[str, bool], *, stuck: tuple[str, ...] = ()) -> None:
        self.stale = dict(stale)
        self.stuck = set(stuck)  # saved stale whatever a rebuild does


class FakeOpenAssembly:
    def __init__(self, file: FakeAssemblyFile) -> None:
        self.file = file
        self.configurations = {name: FakeConfiguration(name) for name in file.stale}
        for name, configuration in self.configurations.items():
            configuration.NeedsRebuild = file.stale[name]
            configuration.AddRebuildSaveMark = False
        self.configurations["Default"].NeedsRebuild = any(file.stale.values())
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=self.configurations["Default"])
        self.Extension = self

    @property
    def NeedsRebuild2(self) -> int:  # noqa: N802
        return int(self.ConfigurationManager.ActiveConfiguration.NeedsRebuild)

    def GetConfigurationNames(self) -> list[str]:
        return list(self.configurations)

    def GetConfigurationByName(self, name: str) -> FakeConfiguration:
        return self.configurations[name]

    def ShowConfiguration2(self, name: str) -> bool:
        if self.ConfigurationManager.ActiveConfiguration.Name == name:
            return False  # SolidWorks refuses the already-active configuration
        self.ConfigurationManager.ActiveConfiguration = self.configurations[name]
        return True

    def EditRebuild3(self) -> bool:
        self.ConfigurationManager.ActiveConfiguration.NeedsRebuild = False
        return True

    def Save3(self, _options: int, _errors: int, _warnings: int) -> bool:
        active = self.ConfigurationManager.ActiveConfiguration
        for name, configuration in self.configurations.items():
            if configuration is active or configuration.AddRebuildSaveMark:
                self.file.stale[name] = configuration.NeedsRebuild or name in self.file.stuck
        return True


def _reconcile(file: FakeAssemblyFile) -> SimpleNamespace:
    async def open_model(_path: str) -> bool:
        adapter.currentModel = FakeOpenAssembly(file)
        return True

    adapter = SimpleNamespace(
        currentModel=None,
        swApp=SimpleNamespace(CloseAllDocuments=lambda _include_unsaved: True),
        open_model=open_model,
        _attempt=lambda fn, default=None: fn(),
    )
    asyncio.run(_assembly.reconcile_saved_rebuild_state(adapter, "pd-paper-drive", "x.SLDASM"))
    return adapter


def test_the_reconciled_assembly_reopens_clean_in_every_configuration() -> None:
    file = FakeAssemblyFile({"Default": True, SIMPLIFIED_VIEW_CONFIGURATION: True})
    adapter = _reconcile(file)
    assert file.stale == {"Default": False, SIMPLIFIED_VIEW_CONFIGURATION: False}
    assert FakeOpenAssembly(file).NeedsRebuild2 == 0  # verify:soundness's open
    assert adapter.currentModel.ConfigurationManager.ActiveConfiguration.Name == "Default"


def test_a_reconciled_assembly_that_still_opens_dirty_is_refused() -> None:
    file = FakeAssemblyFile(
        {"Default": True, SIMPLIFIED_VIEW_CONFIGURATION: True},
        stuck=(SIMPLIFIED_VIEW_CONFIGURATION,),
    )
    with pytest.raises(RuntimeError, match="Default Simplified"):
        _reconcile(file)


def _apply(view: FakeView, role: ViewRole = ViewRole.PLAIN) -> tuple[str, FakeDrawing]:
    drawing = FakeDrawing([view])
    applied = apply_view_configuration(
        SimpleNamespace(currentModel=drawing), view, role=role, label="fixture"
    )
    return applied, drawing


@pytest.mark.parametrize(
    ("view", "role", "expected"),
    [
        (FakeView((1.0, 4.0), "*Front", HLR), ViewRole.PLAIN, SIMPLIFIED_VIEW_CONFIGURATION),
        (FakeView((1.0, 2.0), "*Right", HLV), ViewRole.PLAIN, SIMPLIFIED_VIEW_CONFIGURATION),
        # A pictorial view is judged shaded-with-edges (finalize_drawing's
        # mode) whatever its current mode: the drive-train's 1:8 exploded,
        # BOM-bearing and ballooned isometrics.
        (
            FakeView((1.0, 8.0), "*Isometric", SHADED_EDGES),
            ViewRole.PLAIN,
            SIMPLIFIED_VIEW_CONFIGURATION,
        ),
        (FakeView((1.0, 4.0), "*Isometric", SHADED), ViewRole.PLAIN, SIMPLIFIED_VIEW_CONFIGURATION),
        (
            FakeView((1.0, 8.0), "*Isometric", SHADED_EDGES),
            ViewRole.FULL_DETAIL,
            ASSEMBLY_VIEW_CONFIGURATION,
        ),
        # A view enlarged past 1:2 goes back to full detail.
        (
            FakeView((1.0, 1.0), "*Front", HLR, SIMPLIFIED_VIEW_CONFIGURATION),
            ViewRole.PLAIN,
            ASSEMBLY_VIEW_CONFIGURATION,
        ),
    ],
)
def test_a_view_is_left_on_its_policy_configuration(view, role, expected) -> None:
    applied, _drawing = _apply(view, role)
    assert applied == expected
    assert view.ReferencedConfiguration == expected


def test_a_view_already_on_its_configuration_is_not_regenerated() -> None:
    view = FakeView((1.0, 4.0), "*Front", HLR, SIMPLIFIED_VIEW_CONFIGURATION)
    _applied, drawing = _apply(view)
    assert drawing.rebuilds == 0


def test_a_view_that_does_not_take_its_configuration_is_refused() -> None:
    view = FakeView((1.0, 4.0), "*Front", HLR, accepts=False)
    with pytest.raises(RuntimeError, match="Default Simplified"):
        _apply(view)


def _explode(view: FakeView, show: bool, configuration: str, drawing: FakeDrawing) -> None:
    set_view_exploded_state(
        SimpleNamespace(currentModel=drawing),
        view,
        show,
        configuration=configuration,
        label="fixture",
    )


def test_an_exploded_view_shows_its_policy_configurations_explode() -> None:
    view = FakeView((1.0, 8.0), "*Isometric", SHADED_EDGES)
    applied, drawing = _apply(view)
    _explode(view, True, applied, drawing)
    assert view.exploded_in == SIMPLIFIED_VIEW_CONFIGURATION


def test_the_exploded_state_is_refused_before_the_configuration_switch() -> None:
    view = FakeView((1.0, 8.0), "*Isometric", SHADED_EDGES)
    with pytest.raises(RuntimeError, match="after apply_view_configuration"):
        _explode(view, True, SIMPLIFIED_VIEW_CONFIGURATION, FakeDrawing([view]))
    assert not view.IsExploded()


def test_a_view_exploded_before_its_switch_is_re_exploded_in_the_new_one() -> None:
    view = FakeView((1.0, 8.0), "*Isometric", SHADED_EDGES)
    view.ShowExploded(True)  # Default's explode, e.g. a re-scale re-applies the policy
    applied, drawing = _apply(view)
    _explode(view, True, applied, drawing)
    assert view.exploded_in == SIMPLIFIED_VIEW_CONFIGURATION


def test_a_configuration_without_its_own_explode_is_refused() -> None:
    """An assembly built before Default Simplified carried the explode."""
    view = FakeView(
        (1.0, 8.0),
        "*Isometric",
        SHADED_EDGES,
        explodes=frozenset({ASSEMBLY_VIEW_CONFIGURATION}),
    )
    applied, drawing = _apply(view)
    with pytest.raises(RuntimeError, match="exploded-state readback is False"):
        _explode(view, True, applied, drawing)


def _stub_drive_train_sheets(monkeypatch, fitted_for):
    """The drive-train recipe over one ``FakeDrawing``: every placed view is a
    ``FakeView``; the cluster ring fits at ``fitted_for(preferred)``. Returns
    the recipe module, its adapter, and the (event, configuration, explode)
    log of the view on the active sheet."""
    import draw_dt_drive_train_assembly as drawing

    fake = FakeDrawing([])
    adapter = SimpleNamespace(currentModel=fake)
    by_sheet: dict[str, FakeView] = {}
    active = [""]
    seen: list[tuple[str, str, str | None]] = []

    def activate(_adapter, sheet_name: str) -> None:
        active[0] = sheet_name

    def place(_adapter, _source, orientation, _x, _y, *, scale) -> FakeView:
        mode = SHADED_EDGES if orientation == "*Isometric" else HLR
        view = FakeView(scale, orientation, mode)
        fake.views.append(view)
        by_sheet[active[0]] = view
        return view

    def record(event: str):
        def call(*_args, **_kwargs):
            view = by_sheet[active[0]]
            seen.append((event, view.configuration, view.exploded_in))

        return call

    def set_scale(_adapter, bound, scale, *, label) -> None:
        bound.ScaleRatio = scale

    def ballooned(*_args, **_kwargs) -> list:
        record("balloons")()
        return []

    idle = lambda *_args, **_kwargs: None  # noqa: E731
    for name, stub in {
        "_activate_sheet": activate,
        "place_view": place,
        "set_high_quality_shaded_with_edges": idle,
        "_isolate_instances": record("isolate"),
        "_link_view_to_bom": record("bom link"),
        "_view_outline": lambda _view: (0.0, 0.0, 0.1, 0.1),
        "cluster_ring_scale": lambda _outline, preferred, **_kwargs: fitted_for(preferred),
        "_set_view_scale": set_scale,
        "cluster_ring_fit": lambda _outline: ((0.0, 0.0), [], 0.0),
        "_shift_view": idle,
        "add_component_bom_balloons": ballooned,
        "_spread_balloons": idle,
        "rebuild_drawing": idle,
        "_uncross_balloon_leaders": idle,
        "_verify_balloon_attachments": record("balloon read-back"),
        "_heading": idle,
        "_balloon_annotations": lambda _balloons: {},
    }.items():
        monkeypatch.setattr(drawing, name, stub)
    return drawing, adapter, seen


def _cluster_facts(drawing) -> SimpleNamespace:
    return SimpleNamespace(
        clusters={cluster: frozenset() for cluster in drawing.CLUSTER_SHEETS}, instances=[]
    )


@pytest.mark.parametrize(
    ("preferred", "expected"),
    [
        ((1.0, 3.0), SIMPLIFIED_VIEW_CONFIGURATION),
        # Larger than 1:2 the cluster keeps every tooth, exploded in Default.
        ((2.0, 3.0), ASSEMBLY_VIEW_CONFIGURATION),
    ],
)
def test_cluster_balloons_attach_to_the_explode_of_the_configuration_printed(
    monkeypatch, preferred, expected
) -> None:
    """Configuration, then its own explode, then isolation and BOM link, and
    only then balloons."""
    drawing, adapter, seen = _stub_drive_train_sheets(monkeypatch, lambda placed: placed)
    cluster = next(iter(drawing.CLUSTER_SHEETS))
    monkeypatch.setitem(drawing.CLUSTER_SCALES, cluster, preferred)

    view = drawing._place_cluster_view(adapter, cluster)
    facts = _cluster_facts(drawing)
    scale = drawing._fit_cluster_view(adapter, cluster, view, facts)
    drawing._balloon_cluster_sheet(adapter, cluster, view, facts, scale, bom_name="BOM", items={})

    assert scale == preferred
    assert [event for event, _configuration, _explode in seen] == [
        "isolate",
        "bom link",
        "balloons",
        "balloon read-back",
    ]
    assert all(
        (configuration, explode) == (expected, expected)
        for _event, configuration, explode in seen
    ), seen


def test_a_ring_fit_that_would_switch_an_exploded_view_is_refused(monkeypatch) -> None:
    """A step down past 1:2 would switch the view after every other switch
    was made; it is refused, not made, and the view keeps its scale."""
    drawing, adapter, _seen = _stub_drive_train_sheets(monkeypatch, lambda _placed: (1.0, 2.0))
    cluster = next(iter(drawing.CLUSTER_SHEETS))
    monkeypatch.setitem(drawing.CLUSTER_SCALES, cluster, (2.0, 3.0))

    view = drawing._place_cluster_view(adapter, cluster)
    with pytest.raises(RuntimeError, match="dirties the source"):
        drawing._fit_cluster_view(adapter, cluster, view, _cluster_facts(drawing))
    assert view.ScaleRatio == (2.0, 3.0)
    assert view.configuration == ASSEMBLY_VIEW_CONFIGURATION


def test_the_package_switches_and_explodes_every_view_before_the_bom(monkeypatch) -> None:
    """The whole drive-train package over one drawing: no configuration switch
    lands once the BOM table exists, every cluster view is already exploded
    then, every view prints its policy configuration, and each cluster view
    shows that configuration's explode."""
    drawing, adapter, _seen = _stub_drive_train_sheets(
        monkeypatch, lambda placed: {(1.0, 3.0): (1.0, 4.0)}.get(placed, placed)
    )

    def reference(sheet: int, orientation: str, scale, role=ViewRole.PLAIN) -> FakeView:
        drawing._activate_sheet(adapter, drawing.SHEET_NAMES[sheet - 1])
        view = drawing.place_view(adapter, "src", orientation, 0.0, 0.0, scale=scale)
        drawing._configure_view(adapter, view, exploded=False, role=role, label=orientation)
        return view

    def assembled(_adapter, _facts) -> list[str]:
        for orientation in ("*Front", "*Top", "*Right", "*Isometric"):
            reference(1, orientation, (1.0, 3.0))
        return []

    def sheet(number: int):
        def place(_adapter, _facts) -> list[str]:
            reference(number, "*Isometric", (1.0, 8.0))
            return []

        return place

    def bom_view(_adapter) -> FakeView:
        return reference(2, "*Isometric", (1.0, 8.0))

    exploded_at_bom: list[int] = []

    def insert_bom(_adapter, _view, _facts) -> tuple[str, dict[str, str]]:
        fake = adapter.currentModel
        exploded_at_bom.append(sum(view.IsExploded() for view in fake.views))
        fake.bom_inserted = True
        return "BOM", {}

    def full_detail(_adapter) -> tuple[float, float]:
        reference(drawing.FULL_DETAIL_SHEET, "*Right", (1.0, 1.0), ViewRole.FULL_DETAIL)
        return (1.0, 1.0)

    idle = lambda *_args, **_kwargs: None  # noqa: E731
    for name, stub in {
        "_create_package_sheets": idle,
        "_place_assembled_sheet": assembled,
        "_place_bom_view": bom_view,
        "_insert_bom": insert_bom,
        "_place_sequence_sheet": sheet(drawing.SEQUENCE_SHEET),
        "_place_bank_sheet": sheet(drawing.BANK_SHEET),
        "_place_fit_sheet": sheet(drawing.FIT_SHEET),
        "_place_checks_sheet": sheet(drawing.CHECKS_SHEET),
        "_place_continuation_sheet": sheet(drawing.CONTINUATION_SHEET),
        "_place_full_detail_sheet": full_detail,
        "assert_full_detail_view": idle,
        "_final_balloon_uncross": idle,
        "_check_package_layout": idle,
    }.items():
        monkeypatch.setattr(drawing, name, stub)

    steps: list[str] = []
    drawing._place_package(adapter, _cluster_facts(drawing), steps.append)

    fake = adapter.currentModel
    assert fake.dirtied_source == []
    assert exploded_at_bom == [len(drawing.CLUSTER_SHEETS)]
    exploded = [view for view in fake.views if view.IsExploded()]
    assert len(exploded) == len(drawing.CLUSTER_SHEETS)
    for view in fake.views:
        wanted = view_configuration(
            view.ScaleRatio,
            view.mode,
            ViewRole.FULL_DETAIL if view.ScaleRatio == (1.0, 1.0) else ViewRole.PLAIN,
        )
        assert view.configuration == wanted
        assert view.exploded_in in (None, wanted)


class FakeConfiguredAssembly:
    """An assembly whose active configuration changes only through
    ``ShowConfiguration2`` of a configuration that exists."""

    def __init__(self) -> None:
        self.names = [ASSEMBLY_VIEW_CONFIGURATION]
        self.active = ASSEMBLY_VIEW_CONFIGURATION

    def ShowConfiguration2(self, name: str) -> bool:
        if name not in self.names:
            return False
        self.active = name
        return True


def _author_in_both(monkeypatch, model: FakeConfiguredAssembly, author) -> None:
    def sync(_adapter, _asm_name, *, verify: bool = True) -> int:
        model.names.append(SIMPLIFIED_VIEW_CONFIGURATION)
        return 1

    monkeypatch.setattr(_assembly, "sync_simplified_configuration", sync)
    monkeypatch.setattr(_assembly, "active_configuration_name", lambda _a, m: m.active)
    _assembly.author_in_drawing_configurations(
        SimpleNamespace(currentModel=model), "fixture", author
    )


def test_the_explode_is_authored_in_both_drawing_configurations(monkeypatch) -> None:
    """Default Simplified exists before anything configuration-owned is
    authored; each run sees its own configuration active; the saved-active
    Default is active again afterwards."""
    model = FakeConfiguredAssembly()
    authored: list[tuple[str, str]] = []
    _author_in_both(
        monkeypatch, model, lambda configuration: authored.append((configuration, model.active))
    )
    assert authored == [
        (ASSEMBLY_VIEW_CONFIGURATION, ASSEMBLY_VIEW_CONFIGURATION),
        (SIMPLIFIED_VIEW_CONFIGURATION, SIMPLIFIED_VIEW_CONFIGURATION),
    ]
    assert model.active == ASSEMBLY_VIEW_CONFIGURATION


def test_a_failed_simplified_explode_still_leaves_default_active(monkeypatch) -> None:
    model = FakeConfiguredAssembly()

    def author(configuration: str) -> None:
        if configuration == SIMPLIFIED_VIEW_CONFIGURATION:
            raise RuntimeError("AddExplodeStep2 error 3")

    with pytest.raises(RuntimeError, match="AddExplodeStep2"):
        _author_in_both(monkeypatch, model, author)
    assert model.active == ASSEMBLY_VIEW_CONFIGURATION


TEETH = ("ToothGapCut", "ToothGapPattern")


def _names(variant) -> list[str]:
    """The configuration names of a ``bstr_array`` VARIANT (or a plain list)."""
    return list(getattr(variant, "value", variant))


class FakeFeature:
    """An IFeature whose suppression is per configuration.

    ``leaks_to_parent`` models the defect the readback must catch: suppressing
    in a derived child also suppresses the parent.
    """

    def __init__(self, name: str, part: FakePart, suppressed_in: set[str]) -> None:
        self.Name = name
        self.part = part
        self.suppressed = set(suppressed_in)

    def IsSuppressed2(self, option: int, names) -> tuple[bool, ...]:
        """Answers in the PART's configuration order, not the requested one:
        what a multi-name query did on the farm (cone-gear, 2026-09-28, read
        Default's missing teeth against T006)."""
        assert option == 3  # swSpecifyConfiguration
        asked = set(_names(names))
        return tuple(
            name in self.suppressed for name in self.part.GetConfigurationNames() if name in asked
        )

    def SetSuppression2(self, action: int, option: int, names) -> bool:
        assert (action, option) == (0, 3)  # swSuppressFeature, swSpecifyConfiguration
        for name in _names(names):
            self.suppressed.add(name)
            parent = self.part.configurations[name].GetParent()
            if self.part.leaks_to_parent and parent is not None:
                self.suppressed.add(parent.Name)
        return True


class FakePart(FakeModel):
    """A saved multi-configuration part: a derived child starts with its
    parent's feature states and becomes active, as AddConfiguration2 does."""

    def __init__(
        self,
        names: tuple[str, ...],
        *,
        active: str,
        suppressed_in: set[str] = frozenset(),
        leaks_to_parent: bool = False,
    ) -> None:
        super().__init__(*(FakeConfiguration(name) for name in names))
        self.ConfigurationManager.ActiveConfiguration = self.configurations[active]
        self.Extension.GetWhatsWrong = lambda: None
        self.leaks_to_parent = leaks_to_parent
        self.features = {name: FakeFeature(name, self, suppressed_in) for name in TEETH}

    def _add(self, name, comment, alternate, options, parent, description, rebuild):
        created = super()._add(name, comment, alternate, options, parent, description, rebuild)
        for feature in self.features.values():
            if parent in feature.suppressed:
                feature.suppressed.add(name)
        self.ConfigurationManager.ActiveConfiguration = created
        return created

    def FeatureByName(self, name: str) -> FakeFeature | None:
        return self.features.get(name)

    def ForceRebuild3(self, _top_only: bool) -> bool:
        return True

    def states(self, *configurations: str) -> dict[str, tuple[bool, ...]]:
        return {
            name: tuple(name in feature.suppressed for feature in self.features.values())
            for name in configurations
        }


def _part_adapter(part: FakePart) -> SimpleNamespace:
    return SimpleNamespace(currentModel=part, _attempt=lambda fn, default=None: fn())


def _cone_gear() -> FakePart:
    """cone-gear as farm build 2 read it: T-configurations keep their teeth,
    the unplaced Default reads them suppressed."""
    return FakePart(("Default", "T006", "T120"), active="T120", suppressed_in={"Default"})


def test_only_the_named_parents_are_simplified_and_keep_their_teeth() -> None:
    part = _cone_gear()
    children = _simplified_part.add_simplified_configurations(
        _part_adapter(part), "dt-cone-gear", TEETH, ["T006", "T120"]
    )
    assert children == ["T006 Simplified", "T120 Simplified"]
    assert "Default Simplified" not in part.GetConfigurationNames()
    assert part.states("T006", "T120") == {"T006": (False, False), "T120": (False, False)}
    assert part.states(*children) == {child: (True, True) for child in children}
    assert part.ConfigurationManager.ActiveConfiguration.Name == "T120"


def test_a_parent_that_already_lacks_the_features_is_refused_before_deriving() -> None:
    part = _cone_gear()
    with pytest.raises(RuntimeError, match=r"already suppressed: \['ToothGapCut in Default'"):
        _simplified_part.add_simplified_configurations(_part_adapter(part), "dt-cone-gear", TEETH)
    assert part.GetConfigurationNames() == ["Default", "T006", "T120"]


def test_a_child_suppression_that_reaches_its_parent_fails_the_readback() -> None:
    part = FakePart(("Default", "T024"), active="Default", leaks_to_parent=True)
    with pytest.raises(
        RuntimeError, match=r"ToothGapCut: suppressed in \(Default, Default Simplified\) reads \(True, True\)"
    ):
        _simplified_part.add_simplified_configurations(_part_adapter(part), "fixture", TEETH)


def test_a_simplified_child_of_an_unnamed_configuration_is_an_orphan() -> None:
    part = _cone_gear()
    adapter = _part_adapter(part)
    _simplified_part.add_simplified_configurations(adapter, "dt-cone-gear", TEETH, ["T006", "T120"])
    part.ConfigurationManager.AddConfiguration2("Default Simplified", "", "", 0, "Default", "", False)
    with pytest.raises(RuntimeError, match=r"orphan simplified configurations \['Default Simplified'\]"):
        _simplified_part.assert_simplified_configurations(
            adapter, "dt-cone-gear", TEETH, ["T006", "T120"]
        )
