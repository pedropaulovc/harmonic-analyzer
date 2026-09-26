"""No part or assembly saves construction geometry shown (#880).

A shown sketch, plane, axis, point or reference curve renders in the part's
images and in every assembly that places it: the drive-train isometric carried
grey dots and a line from them.  These tests drive the save-time check through
a fake feature tree, and pin the allowance list that may only shrink.
"""

from __future__ import annotations

import ast
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _common
import _visibility
import build
import visibility_debt

SCRIPTS = Path(__file__).resolve().parent
HIDE, SHOWN = 1, 2


class _Feature:
    """The IFeature surface the check walks; no ``_oleobj_``, so no binding."""

    def __init__(self, name: str, kind: str, visible: int = HIDE, subs=()) -> None:
        self.Name = name
        self.kind = kind
        self.Visible = visible
        self.subs = list(subs)
        self.next: _Feature | None = None
        self.next_sub: _Feature | None = None
        for first, second in zip(self.subs, self.subs[1:], strict=False):
            first.next_sub = second

    def GetTypeName2(self) -> str:
        return self.kind

    def GetFirstSubFeature(self):
        return self.subs[0] if self.subs else None

    def GetNextSubFeature(self):
        return self.next_sub

    def GetNextFeature(self):
        return self.next


class _Extension:
    def __init__(self, model: _Model) -> None:
        self.model = model

    def SelectByID2(self, name, kind, _x, _y, _z, append, *_rest) -> bool:
        feature = self.model.by_name.get(name)
        if feature is None or _SELECT_TYPES.get(feature.kind) != kind:
            return False
        if not append:
            self.model.selected = []
        self.model.selected.append(feature)
        return True


_SELECT_TYPES = {
    "ProfileFeature": "SKETCH",
    "3DProfileFeature": "SKETCH",
    "RefPlane": "PLANE",
    "RefAxis": "AXIS",
    "RefPoint": "DATUMPOINT",
    "Helix": "REFERENCECURVES",
    "CompositeCurve": "REFERENCECURVES",
}
_SKETCHES = {"ProfileFeature", "3DProfileFeature"}


class _FeatureManager:
    def __init__(self, model: _Model) -> None:
        self.model = model
        self.get_features_calls = 0

    def GetFeatures(self, top_level_only: bool):
        assert top_level_only is False
        self.get_features_calls += 1
        found: list[_Feature] = []

        def add(feature: _Feature) -> None:
            found.append(feature)
            if feature.kind != "Reference":  # a component's own tree
                for child in feature.subs:
                    add(child)

        for feature in self.model.features:
            add(feature)
        return tuple(found)


class _Model:
    def __init__(self, *features: _Feature, blank_works: bool = True) -> None:
        self.features = list(features)
        for first, second in zip(self.features, self.features[1:], strict=False):
            first.next = second
        self.by_name: dict[str, _Feature] = {}
        stack = list(self.features)
        while stack:
            feature = stack.pop()
            self.by_name[feature.Name] = feature
            stack.extend(feature.subs)
        self.selected: list[_Feature] = []
        self.blank_works = blank_works
        self.Extension = _Extension(self)
        self.FeatureManager = _FeatureManager(self)

    def FirstFeature(self):
        return self.features[0] if self.features else None

    def ClearSelection2(self, _all: bool) -> None:
        self.selected = []

    def _blank(self, sketches: bool) -> None:
        if not self.blank_works:
            return
        for feature in self.selected:
            if (feature.kind in _SKETCHES) == sketches:
                feature.Visible = HIDE

    def BlankSketch(self) -> None:
        self._blank(sketches=True)

    def BlankRefGeom(self) -> None:
        self._blank(sketches=False)


def _adapter(model: _Model, saves: list[str] | None = None):
    async def save_file(path: str):
        saves.append(path)
        return SimpleNamespace(is_success=True, data={}, error=None)

    return SimpleNamespace(currentModel=model, save_file=save_file)


def _part_tree(*extra: _Feature, blank_works: bool = True) -> _Model:
    """A realistic part: default planes hidden, solids shown, absorbed profile."""
    return _Model(
        _Feature("Front Plane", "RefPlane"),
        _Feature("Top Plane", "RefPlane"),
        _Feature("Origin", "OriginProfileFeature", SHOWN),
        _Feature(
            "Boss", "Extrusion", SHOWN, subs=[_Feature("Sketch1", "ProfileFeature")]
        ),
        *extra,
        blank_works=blank_works,
    )


def test_a_clean_part_passes() -> None:
    _visibility.assert_reference_geometry_hidden(_adapter(_part_tree()), "clean")


@pytest.mark.parametrize(
    ("feature", "text"),
    [
        (
            _Feature("StationReference", "ProfileFeature", SHOWN),
            "sketch 'StationReference'",
        ),
        (_Feature("Plane7", "RefPlane", SHOWN), "plane 'Plane7'"),
        (_Feature("BoreAxis", "RefAxis", SHOWN), "axis 'BoreAxis'"),
        (_Feature("Point1", "RefPoint", SHOWN), "point 'Point1'"),
        (_Feature("Helix1", "Helix", SHOWN), "curve 'Helix1'"),
    ],
)
def test_any_shown_construction_entity_fails(feature: _Feature, text: str) -> None:
    with pytest.raises(RuntimeError, match=re.escape(text)):
        _visibility.assert_reference_geometry_hidden(_adapter(_part_tree(feature)), "p")


def test_a_shown_wizard_placement_sketch_under_its_hole_fails() -> None:
    hole = _Feature(
        "PivotHole",
        "HoleWzd",
        SHOWN,
        subs=[
            _Feature("Sketch9", "ProfileFeature"),
            _Feature("3DSketch1", "3DProfileFeature", SHOWN),
        ],
    )
    with pytest.raises(RuntimeError, match=re.escape("3D sketch '3DSketch1'")):
        _visibility.assert_reference_geometry_hidden(
            _adapter(_part_tree(hole)), "block"
        )


def test_an_assembly_does_not_walk_into_its_components() -> None:
    component = _Feature(
        "crank-arm-1",
        "Reference",
        SHOWN,
        subs=[_Feature("Sk", "ProfileFeature", SHOWN)],
    )
    model = _Model(_Feature("Front Plane", "RefPlane"), component)
    _visibility.assert_reference_geometry_hidden(_adapter(model), "asm")


def test_an_assembly_level_shown_sketch_fails() -> None:
    model = _Model(
        _Feature("crank-arm-1", "Reference", SHOWN),
        _Feature("LayoutSketch", "ProfileFeature", SHOWN),
    )
    with pytest.raises(RuntimeError, match="LayoutSketch"):
        _visibility.assert_reference_geometry_hidden(_adapter(model), "asm")


def test_an_allowance_admits_its_sketch_and_nothing_else() -> None:
    model = _part_tree(
        _Feature("StationReference", "ProfileFeature", SHOWN),
        _Feature("Plane7", "RefPlane", SHOWN),
    )
    allowed = {"StationReference": "crankhub: reason"}
    with pytest.raises(RuntimeError, match="Plane7") as raised:
        _visibility.assert_reference_geometry_hidden(_adapter(model), "p", allowed)
    assert "StationReference" not in str(raised.value)
    model.by_name["Plane7"].Visible = HIDE
    _visibility.assert_reference_geometry_hidden(_adapter(model), "p", allowed)


def test_a_stale_allowance_fails_so_the_list_shrinks() -> None:
    with pytest.raises(RuntimeError, match="matches nothing shown"):
        _visibility.assert_reference_geometry_hidden(
            _adapter(_part_tree()), "p", {"StationReference": "crankhub: reason"}
        )


def test_part_save_checks_before_the_first_save() -> None:
    saves: list[str] = []
    adapter = _adapter(
        _part_tree(_Feature("StationReference", "ProfileFeature", SHOWN)), saves
    )
    with pytest.raises(RuntimeError, match="StationReference"):
        asyncio.run(_common.save_part_and_images(adapter, "crank-arm"))
    assert saves == []


def test_a_shown_plane_reaching_the_save_fails_it() -> None:
    """The creating helpers own hiding; nothing hides at save, so the check is
    the fail-loud backstop for a plane, axis, point or curve left shown."""
    saves: list[str] = []
    model = _part_tree(_Feature("Axis1", "RefAxis", SHOWN))
    with pytest.raises(RuntimeError, match="axis 'Axis1'"):
        asyncio.run(_common.save_part_and_images(_adapter(model, saves), "crank-arm"))
    assert model.by_name["Axis1"].Visible == SHOWN
    assert saves == []


def test_blank_sketch_feature_hides_and_proves_it() -> None:
    sketch = _Feature("3DSketch1", "3DProfileFeature", SHOWN)
    model = _Model(_Feature("Hole", "HoleWzd", SHOWN, subs=[sketch]))
    _visibility.blank_sketch_feature(model, sketch, "hole")
    assert sketch.Visible == HIDE
    _visibility.blank_sketch_feature(model, sketch, "hole")  # already hidden: no-op


def test_blank_sketch_feature_fails_when_the_blank_does_not_take() -> None:
    sketch = _Feature("3DSketch1", "3DProfileFeature", SHOWN)
    model = _Model(_Feature("Hole", "HoleWzd", SHOWN, subs=[sketch]), blank_works=False)
    with pytest.raises(RuntimeError, match="still visible"):
        _visibility.blank_sketch_feature(model, sketch, "hole")


def test_both_hole_wizard_helpers_hide_their_placement_sketch() -> None:
    tree = ast.parse((SCRIPTS / "_holes.py").read_text(encoding="utf-8"))
    callers = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and getattr(call.func, "id", None) == "blank_sketch_feature"
    }
    assert {"wizard_holes", "wizard_hole_on_cylinder"} <= callers


def test_every_standalone_save_path_runs_the_check() -> None:
    """Part saves go through save_part_and_images; the exceptions check too."""
    own_savers = {"build_cone_gear.py"}
    for path in sorted(SCRIPTS.glob("build_*.py")):
        text = path.read_text(encoding="utf-8")
        if "adapter.save_file(" not in text:
            continue
        assert path.name in own_savers, f"{path.name} saves itself; add the check"
        assert "assert_reference_geometry_hidden(adapter" in text
    assembly = (SCRIPTS / "_assembly.py").read_text(encoding="utf-8")
    assert "assert_reference_geometry_hidden(adapter, asm_name)" in assembly


# The debt at the time the check landed.  Owners delete entries as they convert
# their parts; nobody adds one.  Shrink this snapshot along with the list.
_SNAPSHOT = {
    "pinion-arbor": {
        "BackJournalReference",
        "BackRimReference",
        "BondZoneReference",
        "DrumStationReference",
        "FrontJournalReference",
        "OverallReference",
        "PinStationReference",
    },
    "pinion-lever": {"GripStationReference", "PinHoleStationReference"},
    "crank-arm": {"PinStationReference", "StationReference"},
    "crank-drive-gear": {"OutsideDiaReference"},
    "cone-pivot-post": {"BoreSpacingReference", "JournalPlanReference"},
}
_OWNERS = {"pinioncluster", "crankhub", "pivot"}


def _allowances() -> dict[str, dict[str, str]]:
    return visibility_debt.shown_sketch_allowances()


def test_the_allowance_list_only_shrinks() -> None:
    for part, entries in _allowances().items():
        grown = set(entries) - _SNAPSHOT.get(part, set())
        assert not grown, (
            f"{part}: new visibility allowance {sorted(grown)}; hide it instead"
        )


def test_every_allowance_names_its_owner_and_reason() -> None:
    for part, entries in _allowances().items():
        assert entries, f"{part}: an empty SHOWN_SKETCH_ALLOWANCES; delete it"
        for name, note in entries.items():
            owner, _, reason = note.partition(": ")
            assert owner in _OWNERS and reason.strip(), (part, name, note)


def test_each_listed_part_passes_its_allowance_to_the_save() -> None:
    passing = set()
    for path in SCRIPTS.glob("build_*.py"):
        text = path.read_text(encoding="utf-8")
        if "allowed_shown=SHOWN_SKETCH_ALLOWANCES" not in text:
            continue
        match = re.search(r'^PART_NAME = "([^"]+)"', text, re.MULTILINE)
        assert match, path.name
        passing.add(match.group(1))
    assert passing == set(_allowances())


def test_only_a_command_that_executes_release_is_refused(monkeypatch) -> None:
    """``info``/``clean``/``forget release`` publish nothing (Codex on #880)."""
    monkeypatch.setattr(build, "_visibility_debt", lambda: "release blocked")
    doit = build.DoitMain()

    def refusal(*argv: str) -> str | None:
        args = list(argv)
        return build._release_refusal(args, build._executing_command(args, doit))

    for argv in (["release"], ["run", "release"], ["release", "--", "v22"]):
        assert refusal(*argv) == "release blocked", argv
    for argv in (
        ["info", "release"],
        ["clean", "release"],
        ["forget", "release"],
        ["list"],
        ["build", "--", "release"],
    ):
        assert refusal(*argv) is None, argv


def test_release_refuses_to_start_while_any_allowance_remains(tmp_path) -> None:
    assert _allowances(), "no debt left; keep only the clean half of this test"
    assert build._selects_release(["release", "--", "v22"])
    assert build._selects_release(["run", "release"])
    assert not build._selects_release(["build", "--", "release"])
    assert "release blocked" in (build._visibility_debt() or "")
    assert build.main(["release"]) == 2
    clean = tmp_path / "build_clean_part.py"
    clean.write_text(
        'PART_NAME = "clean-part"\nSHOWN_SKETCH_ALLOWANCES = {}\n', encoding="utf-8"
    )
    visibility_debt.assert_no_visibility_debt(tmp_path)


def test_name_bore_axis_hides_the_planes_and_axis_it_creates() -> None:
    model = _Model(
        _Feature("Front Plane", "RefPlane"), _Feature("Top Plane", "RefPlane")
    )

    def _ok(name: str):
        return SimpleNamespace(
            is_success=True, error=None, data=SimpleNamespace(name=name)
        )

    async def create_plane(_params):
        feature = _Feature(f"Plane{len(model.features) - 1}", "RefPlane", SHOWN)
        model.features[-1].next = feature
        model.features.append(feature)
        model.by_name[feature.Name] = feature
        return _ok(feature.Name)

    async def create_axis(_params):
        feature = _Feature("Axis1", "RefAxis", SHOWN)
        model.features[-1].next = feature
        model.features.append(feature)
        model.by_name[feature.Name] = feature
        return _ok(feature.Name)

    adapter = SimpleNamespace(
        currentModel=model, create_plane=create_plane, create_axis=create_axis
    )
    axis = asyncio.run(
        _common.name_bore_axis(adapter, "Front Plane", 4.0, "Top Plane", 0.0, "bore")
    )
    assert axis == "Axis1"
    assert [f.Name for f in model.features if f.Visible == SHOWN] == []
    assert _visibility.visible_reference_geometry(model) == []


class _CountingFeature(_Feature):
    """Counts the COM reads the save check makes on it."""

    reads: dict[str, int] = {}

    def __getattribute__(self, name: str):
        if name in ("Name", "Visible", "GetTypeName2"):
            reads = _CountingFeature.reads
            reads[name] = reads.get(name, 0) + 1
        return super().__getattribute__(name)


def test_the_check_reads_one_member_per_feature_and_logs_its_cost(monkeypatch) -> None:
    """#880's save bar: one GetFeatures call, then GetTypeName2 per feature,
    Visible only on reference types and Name only on a shown one; the size
    and cost reach the task.log, the only telemetry a farm leaf uploads."""
    lines: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        _visibility._telemetry, "info", lambda msg, **attrs: lines.append((msg, attrs))
    )
    features = [
        _CountingFeature("Front Plane", "RefPlane"),
        _CountingFeature(
            "Boss",
            "Extrusion",
            SHOWN,
            subs=[_CountingFeature("Sketch1", "ProfileFeature")],
        ),
        _CountingFeature("Fillet1", "Fillet", SHOWN),
        _CountingFeature("StationReference", "ProfileFeature", SHOWN),
    ]
    model = _Model(*features)
    _CountingFeature.reads = {}  # the fake's own setup read every Name
    allowed = {"StationReference": "crankhub: reason"}
    _visibility.assert_reference_geometry_hidden(_adapter(model), "crank-arm", allowed)
    assert model.FeatureManager.get_features_calls == 1
    assert _CountingFeature.reads == {"GetTypeName2": 5, "Visible": 3, "Name": 1}
    scans = [
        (msg, attrs) for msg, attrs in lines if attrs.get("walk_purpose") == "check"
    ]
    assert len(scans) == 1
    msg, attrs = scans[0]
    assert msg.startswith("crank-arm: check scanned 5 features with 11 COM calls")
    assert attrs["features_visited"] == 5 and attrs["com_calls"] == 11
    assert 0.0 <= attrs["fetch_s"] <= attrs["walk_s"]


def test_shared_reference_creators_hide_what_they_create() -> None:
    for module in ("_gear.py", "_chain_link.py", "_features.py", "_assembly.py"):
        text = (SCRIPTS / module).read_text(encoding="utf-8")
        creates = text.count("await adapter.create_plane(") + text.count(
            "await adapter.create_axis("
        )
        assert creates and "blank_reference_geometry(" in text, module


_REFERENCE_CREATE = re.compile(
    r"\b(?:create_plane|create_axis|create_reference_point|InsertRefPlane"
    r"|InsertAxis2?|InsertReferencePoint|InsertHelix|InsertCompositeCurve)\("
)
_REFERENCE_HIDES = (
    "blank_reference_geometry(",
    ".BlankRefGeom(",
    "_blank_recipe_references(",
)
# Modules that create reference geometry but never save a document: the
# motion studies author transient points/planes on an open model and discard it.
_NON_SAVING_CREATORS = frozenset(
    {"build_motion_study.py", "build_motion_study_springs.py"}
)


def _creates_without_hiding(text: str) -> bool:
    """A module that authors reference geometry must hide some of it itself."""
    code = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    if not any(_REFERENCE_CREATE.search(line) for line in code):
        return False
    return not any(hide in line for line in code for hide in _REFERENCE_HIDES)


def test_the_creator_sweep_flags_a_create_without_a_hide() -> None:
    assert _creates_without_hiding(
        "plane = check('p', await adapter.create_plane(params)).name\n"
    )
    assert _creates_without_hiding(
        "model.FeatureManager.InsertReferencePoint(7, 0, 0.0, 1)\n"
    )
    assert not _creates_without_hiding(
        "name = check('p', await adapter.create_plane(params)).name\n"
        "blank_reference_geometry(adapter, ((name, 'PLANE'),))\n"
    )
    assert not _creates_without_hiding("# await adapter.create_axis(params)\n")
    assert not _creates_without_hiding("CreateAxisParameters(mode='two_planes')\n")


def test_every_reference_creator_hides_what_it_creates() -> None:
    """Nothing hides at save any more, so each builder hides its own planes,
    axes, points and curves.  ``diagnostics/`` is out of scope: its purchased-part
    recipes are blanked by their caller (``_stock_fastener._blank_recipe_references``)
    and the rest are hand-run probes that never ship an artefact."""
    offenders = sorted(
        path.name
        for path in SCRIPTS.rglob("*.py")
        if "diagnostics" not in path.relative_to(SCRIPTS).parts
        and not path.name.startswith("test_")
        and path.name not in _NON_SAVING_CREATORS
        and _creates_without_hiding(path.read_text(encoding="utf-8"))
    )
    assert offenders == []


def test_the_non_saving_allowance_stays_honest() -> None:
    for module in _NON_SAVING_CREATORS:
        text = (SCRIPTS / module).read_text(encoding="utf-8")
        assert _creates_without_hiding(text), module
        assert "save_part_and_images" not in text, module
        assert "save_assembly_and_images" not in text, module


def test_one_error_names_both_unexpected_and_stale_entries() -> None:
    model = _part_tree(_Feature("Plane7", "RefPlane", SHOWN))
    with pytest.raises(RuntimeError) as raised:
        _visibility.assert_reference_geometry_hidden(
            _adapter(model), "p", {"StationReference": "crankhub: reason"}
        )
    assert "Plane7" in str(raised.value)
    assert "StationReference" in str(raised.value)


def _without_allowances(text: str) -> str:
    """The builder source minus its SHOWN_SKETCH_ALLOWANCES literal."""
    lines = text.splitlines()
    for node in ast.parse(text).body:
        targets = getattr(node, "targets", [])
        if any(getattr(t, "id", "") == "SHOWN_SKETCH_ALLOWANCES" for t in targets):
            del lines[node.lineno - 1 : node.end_lineno]
            break
    return "\n".join(lines)


def test_every_allowance_names_a_sketch_its_builder_authors() -> None:
    """A name the builder never authors could only be stale.  Names are literal,
    or ``f"{prefix}Reference"`` with a literal prefix (the arbor's journals)."""
    for path in SCRIPTS.glob("build_*.py"):
        text = path.read_text(encoding="utf-8")
        match = re.search(r'^PART_NAME = "([^"]+)"', text, re.MULTILINE)
        if not match or match.group(1) not in _allowances():
            continue
        text = _without_allowances(text)
        for name in _allowances()[match.group(1)]:
            prefix = name.removesuffix("Reference")
            authored = f'"{name}"' in text or (
                'f"{prefix}Reference"' in text and f'prefix="{prefix}"' in text
            )
            assert authored, f"{path.name} authors no sketch named {name!r}"


def test_the_shared_walk_counts_every_feature_but_skips_components() -> None:
    component = _Feature(
        "crank-arm-1", "Reference", SHOWN, subs=[_Feature("Sk", "ProfileFeature")]
    )
    hole = _Feature(
        "Hole", "HoleWzd", SHOWN, subs=[_Feature("3DSketch1", "3DProfileFeature")]
    )
    walk = _visibility.FeatureWalk(
        _Model(_Feature("Front Plane", "RefPlane"), hole, component)
    )
    assert [feature.Name for feature in walk] == [
        "Front Plane",
        "Hole",
        "3DSketch1",
        "crank-arm-1",
    ]
    assert walk.visited == 4


def test_creation_hides_and_the_save_check_are_distinct_spans() -> None:
    text = (SCRIPTS / "_visibility.py").read_text(encoding="utf-8")
    for span in (
        "appearance.blank_reference_geometry",
        "appearance.blank_sketch_feature",
        "appearance.assert_reference_geometry_hidden",
    ):
        assert text.count(f'"{span}"') == 1, span
    stock = (SCRIPTS / "_stock_fastener.py").read_text(encoding="utf-8")
    assert "FeatureWalk(model)" in stock and "walk_siblings" not in stock
