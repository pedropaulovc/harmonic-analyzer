r"""Offline gate: every sketch entity a drawing recipe creates goes in direct-to-DB.

``ISketchManager.Create*`` runs a new entity through the sketch inference
engine unless the manager is in ``AddToDB`` mode, and inference snaps input
points onto nearby view geometry with a SCREEN-pixel tolerance. On 2026-09-22
that made the knife-hanger stud's detail fence depend on the farm seat: centred
on a thread-root vertex on swmaker000005 (parent radius 6.35 mm) and 0.02 mm
off on swmaker000006 (5.02 mm), from the same code. ``_drawing_common.
direct_sketch`` is the one sanctioned way in; this test fails, with file and
line, any drawing recipe that creates sketch geometry outside it or hand-rolls
the ``AddToDB`` toggle.

Scope: every ``draw_*.py`` plus every helper module only drawings import
(derived from ``_buildgraph.module_deps_of``, so a new drawing helper joins the
audit without anyone remembering to list it).

    uv run --frozen pytest cad/scripts/test_drawing_direct_sketch.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _drawing_common  # noqa: E402
from _buildgraph import module_deps_of  # noqa: E402
from test_sketch_preference_baseline import RAW_SKETCH_CALLS  # noqa: E402

GUARD = "direct_sketch"
# ``CreatePoint`` is also ``IMathUtility``'s constructor for a math point, which
# every drawing helper calls; it counts only on a sketch-manager receiver.
POINT_CALL = "CreatePoint"
# The sketch-manager modes only ``direct_sketch`` may write.
GUARDED_MODES = frozenset({"AddToDB", "DisplayWhenAdded"})
# Code whose body runs later than the ``with`` it is written in.
_DEFERRED_CODE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.GeneratorExp)


def audited_files() -> list[Path]:
    """``draw_*.py`` and the repo-local modules imported by drawings only."""
    drawings = sorted(SCRIPTS_DIR.glob("draw_*.py"))

    def local(script: Path) -> set[Path]:
        return {
            Path(dep).resolve()
            for dep in module_deps_of(script)
            if Path(dep).resolve().parent == SCRIPTS_DIR
        }

    drawing_closure = set().union(*(local(script) for script in drawings))
    build_closure = set().union(
        *(local(script) for script in SCRIPTS_DIR.glob("build_*.py"))
    )
    helpers = sorted(drawing_closure - build_closure - set(drawings))
    return [*drawings, *helpers]


def _is_guard(expr: ast.expr) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    return name == GUARD and len(expr.args) == 1


def _guarded_receivers(node: ast.With | ast.AsyncWith) -> set[str]:
    """What a ``with direct_sketch(manager) [as alias]:`` block covers."""
    receivers: set[str] = set()
    for item in node.items:
        if not _is_guard(item.context_expr):
            continue
        receivers.add(ast.unparse(item.context_expr.args[0]))
        if isinstance(item.optional_vars, ast.Name):
            receivers.add(item.optional_vars.id)
    return receivers


def _sketch_manager_names(tree: ast.AST) -> set[str]:
    """Names bound anywhere in the module to an expression naming a SketchManager."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and "SketchManager" in ast.unparse(node.value):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _is_sketch_creation(call: ast.Call, managers: set[str]) -> bool:
    func = call.func
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in RAW_SKETCH_CALLS:
        return True
    receiver = ast.unparse(func.value)
    return func.attr == POINT_CALL and (
        receiver in managers or "SketchManager" in receiver
    )


def _visit(
    node: ast.AST, guarded: frozenset[str], managers: set[str], found: list
) -> None:
    if isinstance(node, _DEFERRED_CODE):
        guarded = frozenset()
    if isinstance(node, (ast.With, ast.AsyncWith)):
        guarded = guarded | _guarded_receivers(node)
    if isinstance(node, ast.Call) and _is_sketch_creation(node, managers):
        receiver = ast.unparse(node.func.value)  # type: ignore[attr-defined]
        if receiver not in guarded:
            found.append((node.lineno, f"{receiver}.{node.func.attr}"))  # type: ignore[attr-defined]
    for child in ast.iter_child_nodes(node):
        _visit(child, guarded, managers, found)


def unguarded_sketch_calls(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    _visit(tree, frozenset(), _sketch_manager_names(tree), found)
    return sorted(found)


def mode_writes_outside_guard(source: str) -> list[tuple[int, str]]:
    """``*.AddToDB = ...`` / ``*.DisplayWhenAdded = ...`` outside ``direct_sketch``'s
    own definition -- a hand-rolled toggle the call audit could not vouch for."""
    tree = ast.parse(source)
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == GUARD:
            allowed |= {id(child) for child in ast.walk(node)}
    found = []
    for node in ast.walk(tree):
        if id(node) in allowed:
            continue
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, (ast.AugAssign, ast.AnnAssign))
            else []
        )
        for target in targets:
            if isinstance(target, ast.Attribute) and target.attr in GUARDED_MODES:
                found.append((node.lineno, ast.unparse(target)))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "setattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in GUARDED_MODES
            and id(node) not in allowed
        ):
            found.append((node.lineno, ast.unparse(node)))
    return sorted(found)


def test_every_drawing_sketch_entity_is_created_direct_to_db() -> None:
    files = audited_files()
    names = {path.name for path in files}
    # A renamed helper or a broken closure walk must not pass by auditing
    # nothing: the modules that carried the snapped fences must be in scope.
    assert {"_drawing_common.py", "_stock_trim_drawing.py"} <= names, sorted(names)
    assert len([n for n in names if n.startswith("draw_")]) > 50, sorted(names)
    offenders = {
        path.name: calls
        for path in files
        for calls in [unguarded_sketch_calls(path.read_text(encoding="utf-8"))]
        if calls
    }
    assert offenders == {}, "\n".join(
        f"{name}:{line} {call} creates sketch geometry outside "
        "`with direct_sketch(<that manager>)` -- sketch inference will snap it"
        for name, calls in offenders.items()
        for line, call in calls
    )


def test_no_drawing_module_toggles_the_sketch_manager_mode_by_hand() -> None:
    offenders = {
        path.name: writes
        for path in audited_files()
        for writes in [mode_writes_outside_guard(path.read_text(encoding="utf-8"))]
        if writes
    }
    assert offenders == {}, "\n".join(
        f"{name}:{line} {write}: use `with direct_sketch(manager):` instead"
        for name, writes in offenders.items()
        for line, write in writes
    )


# --------------------------------------------------------------------------- #
# The audit's own teeth.
# --------------------------------------------------------------------------- #
def test_the_audit_flags_the_end_detail_shape() -> None:
    """The exact shape that snapped: a fence drawn on the bare manager."""
    source = (
        "def end_detail(draw):\n"
        "    manager = _early_bound(draw.SketchManager, 'ISketchManager')\n"
        "    manager.CreateCircle(0, 0, 0, 1, 0, 0)\n"
    )
    assert unguarded_sketch_calls(source) == [(3, "manager.CreateCircle")]


def test_the_audit_accepts_a_guarded_call_and_its_alias() -> None:
    source = (
        "def f(draw):\n"
        "    manager = draw.SketchManager\n"
        "    with direct_sketch(manager):\n"
        "        manager.CreateLine(0, 0, 0, 1, 0, 0)\n"
        "    with direct_sketch(draw.SketchManager) as sketch:\n"
        "        sketch.CreateCenterLine(0, 0, 0, 1, 0, 0)\n"
        "        draw.SketchManager.CreatePoint(0, 0, 0)\n"
    )
    assert unguarded_sketch_calls(source) == []


def test_the_audit_matches_the_guarded_receiver() -> None:
    """Guarding one manager says nothing about entities drawn through another."""
    source = (
        "def f(a, b):\n"
        "    first = a.SketchManager\n"
        "    second = b.SketchManager\n"
        "    with direct_sketch(first):\n"
        "        second.CreateCircle(0, 0, 0, 1, 0, 0)\n"
    )
    assert unguarded_sketch_calls(source) == [(5, "second.CreateCircle")]


def test_the_audit_ignores_math_points_but_not_sketch_points() -> None:
    source = (
        "def f(adapter, draw):\n"
        "    utility = adapter.swApp.GetMathUtility()\n"
        "    utility.CreatePoint(double_array([0.0, 0.0, 0.0]))\n"
        "    manager = draw.SketchManager\n"
        "    manager.CreatePoint(0, 0, 0)\n"
    )
    assert unguarded_sketch_calls(source) == [(5, "manager.CreatePoint")]


def test_a_deferred_body_is_not_covered_by_the_block_it_is_written_in() -> None:
    source = (
        "def f(manager):\n"
        "    with direct_sketch(manager):\n"
        "        later = lambda: manager.CreateLine(0, 0, 0, 1, 0, 0)\n"
        "    later()\n"
    )
    assert unguarded_sketch_calls(source) == [(3, "manager.CreateLine")]


def test_the_mode_audit_flags_a_hand_rolled_toggle_but_not_the_guard() -> None:
    source = (
        "def direct_sketch(manager):\n"
        "    manager.AddToDB = True\n"
        "    setattr(manager, 'AddToDB', False)\n"
        "def f(manager):\n"
        "    manager.AddToDB = True\n"
        "    manager.DisplayWhenAdded = False\n"
        "    setattr(manager, 'AddToDB', True)\n"
        "    setattr(view, 'ScaleRatio', 2)\n"
    )
    assert mode_writes_outside_guard(source) == [
        (5, "manager.AddToDB"),
        (6, "manager.DisplayWhenAdded"),
        (7, "setattr(manager, 'AddToDB', True)"),
    ]


# --------------------------------------------------------------------------- #
# The runtime half: the guard itself and the detail-circle read-back.
# --------------------------------------------------------------------------- #
class _Manager:
    def __init__(self, add_to_db: bool = False, *, refuses: bool = False) -> None:
        self._add_to_db = add_to_db
        self.refuses = refuses
        self.DisplayWhenAdded = False

    @property
    def AddToDB(self) -> bool:
        return self._add_to_db

    @AddToDB.setter
    def AddToDB(self, value: bool) -> None:
        if not (self.refuses and value):
            self._add_to_db = bool(value)


def test_direct_sketch_forces_the_mode_and_hands_back_what_it_found() -> None:
    manager = _Manager(add_to_db=False)
    with _drawing_common.direct_sketch(manager) as sketch:
        assert sketch is manager
        assert (manager.AddToDB, manager.DisplayWhenAdded) == (True, True)
    assert (manager.AddToDB, manager.DisplayWhenAdded) == (False, False)


def test_direct_sketch_refuses_to_run_through_inference() -> None:
    """A manager that silently declines AddToDB must stop the recipe."""
    manager = _Manager(refuses=True)
    with pytest.raises(RuntimeError, match="refused AddToDB"):
        with _drawing_common.direct_sketch(manager):
            raise AssertionError("the block must not run")
    assert manager.DisplayWhenAdded is False


class _View:
    def __init__(self, info: list[float]) -> None:
        self.info = info

    def GetDetailCircleInfo2(self) -> list[float]:
        return self.info


def _circle(center, radius, arrows: int = 0) -> list[float]:
    x, y = center
    return [
        0.0,  # layer
        x, y, 0.0,
        x + radius, y, 0.0,  # start
        x + radius, y, 0.0,  # end
        1.0,  # line type
        x, y + radius, 0.0,  # text point
        0.0035,  # text height
        float(arrows),
        *([0.0] * 9 * arrows),
    ]


def test_detail_circles_walks_past_each_circles_arrows() -> None:
    view = _View(
        [2.0, *_circle((0.1, 0.2), 0.005, arrows=2), *_circle((0.3, 0.4), 0.002)]
    )
    circles = _drawing_common._detail_circles(view)
    assert [(tuple(round(v, 9) for v in c), round(r, 9)) for c, r in circles] == [
        ((0.1, 0.2), 0.005),
        ((0.3, 0.4), 0.002),
    ]


def test_the_detail_read_back_refuses_the_stud_5_snap() -> None:
    """stud-5: requested r 5.00 mm, the fence snapped to a thread-root vertex
    1.25 mm away and read back r 6.35 mm. The old ``0 < r < half`` bar passed it."""
    requested = ((0.11634, 0.12425), 0.005)
    _drawing_common._assert_detail_circle(
        _View([1.0, *_circle(*requested)]), *requested, label="exact"
    )
    snapped = _View([1.0, *_circle((0.11509, 0.12553), 0.00635)])
    with pytest.raises(RuntimeError, match="sketch inference snapped it"):
        _drawing_common._assert_detail_circle(snapped, *requested, label="stud-5")
