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


def test_the_save_hides_planes_axes_points_and_curves_but_not_sketches() -> None:
    model = _part_tree(
        _Feature("HandleSeat", "RefPlane", SHOWN),
        _Feature("Axis1", "RefAxis", SHOWN),
        _Feature("Point1", "RefPoint", SHOWN),
        _Feature("Helix1", "Helix", SHOWN),
        _Feature("StationReference", "ProfileFeature", SHOWN),
    )
    hidden = _visibility.hide_reference_geometry(_adapter(model), "crank-arm")
    assert hidden == ["HandleSeat", "Axis1", "Point1", "Helix1"]
    assert model.by_name["StationReference"].Visible == SHOWN
    with pytest.raises(RuntimeError, match="StationReference") as raised:
        _visibility.assert_reference_geometry_hidden(_adapter(model), "crank-arm")
    assert "Axis1" not in str(raised.value)


def test_the_hide_fails_when_blank_ref_geom_does_not_take() -> None:
    model = _part_tree(_Feature("Axis1", "RefAxis", SHOWN), blank_works=False)
    with pytest.raises(RuntimeError, match=r"left \['Axis1'\] shown"):
        _visibility.hide_reference_geometry(_adapter(model), "p")


def test_part_save_hides_reference_geometry_then_checks() -> None:
    saves: list[str] = []
    model = _part_tree(
        _Feature("Axis1", "RefAxis", SHOWN),
        _Feature("StationReference", "ProfileFeature", SHOWN),
    )
    with pytest.raises(RuntimeError, match="StationReference"):
        asyncio.run(_common.save_part_and_images(_adapter(model, saves), "crank-arm"))
    assert model.by_name["Axis1"].Visible == HIDE
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
    assert "hide_reference_geometry(adapter, asm_name)" in assembly
    cone_gear = (SCRIPTS / "build_cone_gear.py").read_text(encoding="utf-8")
    assert "hide_reference_geometry(adapter, PART_NAME)" in cone_gear


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


def test_the_save_backstop_counts_what_it_had_to_hide(monkeypatch) -> None:
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        _visibility._telemetry,
        "event",
        lambda name, **attrs: events.append((name, attrs)),
    )
    model = _part_tree(_Feature("Plane2", "RefPlane", SHOWN))
    _visibility.hide_reference_geometry(_adapter(model), "crank-arm")
    _visibility.hide_reference_geometry(_adapter(model), "crank-arm")
    counts = [
        attrs["count"] for name, attrs in events if name == "refgeom.hidden_at_save"
    ]
    assert counts == [1, 0]


def test_each_save_walk_logs_its_size_and_cost(monkeypatch) -> None:
    """A farm leaf uploads only its task.log, so both save walks put
    features_visited and their elapsed time on an info line (#880's bar)."""
    lines: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        _visibility._telemetry, "info", lambda msg, **attrs: lines.append((msg, attrs))
    )
    model = _part_tree(_Feature("Plane2", "RefPlane"))
    _visibility.hide_reference_geometry(_adapter(model), "crank-arm")
    _visibility.assert_reference_geometry_hidden(_adapter(model), "crank-arm")
    walks = [attrs for _msg, attrs in lines if "walk_purpose" in attrs]
    assert [attrs["walk_purpose"] for attrs in walks] == ["hide", "check"]
    for attrs in walks:
        assert attrs["features_visited"] >= 1
        assert attrs["walk_s"] >= 0.0
    assert all(
        msg.startswith("crank-arm: ") for msg, attrs in lines if "walk_purpose" in attrs
    )


def test_shared_reference_creators_hide_what_they_create() -> None:
    for module in ("_gear.py", "_chain_link.py", "_features.py", "_assembly.py"):
        text = (SCRIPTS / module).read_text(encoding="utf-8")
        creates = text.count("await adapter.create_plane(") + text.count(
            "await adapter.create_axis("
        )
        assert creates and "blank_reference_geometry(" in text, module


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


def test_creation_hides_and_the_save_backstop_are_distinct_spans() -> None:
    text = (SCRIPTS / "_visibility.py").read_text(encoding="utf-8")
    for span in (
        "appearance.blank_reference_geometry",
        "appearance.hide_reference_geometry",
        "appearance.blank_sketch_feature",
        "appearance.assert_reference_geometry_hidden",
    ):
        assert text.count(f'"{span}"') == 1, span
    stock = (SCRIPTS / "_stock_fastener.py").read_text(encoding="utf-8")
    assert "FeatureWalk(model)" in stock and "walk_siblings" not in stock
