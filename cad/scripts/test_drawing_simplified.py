"""The simplified-view configuration policy (SolidWorks-free)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _assembly
import _drawing_simplified
from _drawing_common import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    view_configuration,
)
from _drawing_simplified import (
    child_bom_identity,
    is_simplified,
    simplified_comment,
    simplified_name,
)

HLV, HLR, SHADED, SHADED_EDGES = 1, 2, 3, 7
DOCUMENT, CONFIGURATION, PARENT, USER = 1, 2, 4, 8


class FakeView:
    """An IView whose configuration switch lands only when the drawing rebuilds."""

    def __init__(
        self,
        scale: tuple[float, float],
        orientation: str,
        mode: int,
        configuration: str = ASSEMBLY_VIEW_CONFIGURATION,
        *,
        accepts: bool = True,
    ) -> None:
        self.ScaleRatio = scale
        self.orientation = orientation
        self.mode = mode
        self.configuration = configuration
        self.accepts = accepts
        self.pending: str | None = None

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
    """One sheet of ``FakeView``s; ``EditRebuild3`` regenerates them."""

    def __init__(self, views: list[FakeView]) -> None:
        self.views = views
        self.rebuilds = 0

    def EditRebuild3(self) -> bool:
        self.rebuilds += 1
        for view in self.views:
            if view.pending is not None:
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


@pytest.mark.parametrize("mode", [HLV, HLR])
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
def test_a_line_view_is_simplified_at_one_to_two_or_smaller(mode, scale, expected) -> None:
    assert view_configuration(scale, mode) == expected


@pytest.mark.parametrize("mode", [SHADED, SHADED_EDGES, 0])
def test_a_shaded_or_wireframe_view_keeps_full_detail(mode) -> None:
    assert view_configuration((1.0, 8.0), mode) == ASSEMBLY_VIEW_CONFIGURATION


@pytest.mark.parametrize(
    "role", [ViewRole.EXPLODED, ViewRole.BOM, ViewRole.BALLOONS, ViewRole.FULL_DETAIL]
)
def test_a_view_that_carries_more_than_geometry_keeps_full_detail(role) -> None:
    assert view_configuration((1.0, 8.0), HLR, role) == ASSEMBLY_VIEW_CONFIGURATION


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
    _drawing_simplified._copy_bom_identity(FakeModel(root, linked, child), "T24", child.Name)
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
    asyncio.run(_assembly.reconcile_saved_rebuild_state(adapter, "paper-drive", "x.SLDASM"))
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
        # A pictorial view is judged shaded whatever its current line mode.
        (FakeView((1.0, 4.0), "*Isometric", HLR), ViewRole.PLAIN, ASSEMBLY_VIEW_CONFIGURATION),
        (FakeView((1.0, 4.0), "*Front", HLR), ViewRole.BOM, ASSEMBLY_VIEW_CONFIGURATION),
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
