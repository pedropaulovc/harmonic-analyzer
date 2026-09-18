r"""Offline invariants for "no built geometry depends on a user setting".

Two halves, both regression tests for the 2026-09-17 ``logo ring extrude
failed`` leaf on ``swmaker000005@5``:

* **The latch.** SolidWorks sketch-inference preferences are APPLICATION-level,
  so they outlive the document, the recipe and the leaf.  The replaced code
  saved the observed value on entry and wrote it back on exit, which turns one
  crash inside a suppression block into a permanently mis-set seat: the next
  leaf records the leaked value as "the original" and faithfully restores it
  forever.  These tests pin the declared-constant behaviour that replaces it.

* **The authoring audit.** Every raw sketch primitive in the diagnostics
  recipes must be authored inside a control that defeats inference, rather than
  inheriting whatever the seat happens to be set to.  This is the test that
  stops the class from regrowing: a new recipe that calls ``CreateLine``
  outside a guard fails here, offline, with the file and line named.

* **The read-back's error policy.** The closure read-back must be incapable of
  failing a build on healthy geometry, because two things about
  ``ISketch.CheckFeatureUse`` are unresolved until someone runs it on a seat.
  Those tests pin "warn and proceed" as the default and leave exactly one
  raising condition.
"""

from __future__ import annotations

import ast
import types
from pathlib import Path

import pytest

from diagnostics import diag_mcmaster_lib as diag

SCRIPTS_DIR = Path(__file__).resolve().parent
DIAGNOSTICS_DIR = SCRIPTS_DIR / "diagnostics"

# ``ISketchManager`` calls that put raw geometry into a sketch.  Inference acts
# on creation, so these are the only calls whose RESULT a user setting can
# change -- the adapter's own ``add_line``/``add_arc``/``define_*`` helpers are
# already wrapped by their callers.
RAW_SKETCH_CALLS = frozenset({
    "CreateArc",
    "CreateCenterLine",
    "CreateCenterRectangle",
    "CreateCircle",
    "CreateCircleByRadius",
    "CreateCornerRectangle",
    "CreateEllipse",
    "CreateLine",
    "CreateLine2",
    "CreateParabola",
    "CreatePolygon",
    "Create3PointArc",
    "CreateSketchSlot",
    "CreateSketchText",
    "CreateSpline",
    "CreateTangentArc",
})

# Contextmanagers that force the sketch preferences for their block.
GUARD_CONTEXTMANAGERS = frozenset({"no_sketch_inference", "preference_override"})

# Files exempt from the audit, with the reason.  Both drive a bare ``sw`` COM
# application rather than the adapter -- there is no ``adapter`` to guard with
# -- and both draw a single hard-coded circle into an EMPTY throwaway part, so
# there is no model geometry and no second sketch entity for inference to snap
# to.  They exist to reproduce COM/assembly semantics, not to build parts.
AUDIT_EXEMPT = {
    "diag_cwm_min.py": "raw swApp probe; one circle in an empty throwaway part",
    "diag_cwm_gear_min.py": "raw swApp probe; circles in an empty throwaway part",
}


class _SwApp:
    """Records every preference write, so restore ORDER and VALUES are visible."""

    def __init__(self, initial: dict[int, bool]) -> None:
        self.toggles = dict(initial)
        self.writes: list[tuple[int, bool]] = []

    def GetUserPreferenceToggle(self, toggle: int) -> bool:
        return self.toggles[toggle]

    def SetUserPreferenceToggle(self, toggle: int, value: bool) -> None:
        self.toggles[toggle] = bool(value)
        self.writes.append((toggle, bool(value)))


class _Adapter:
    def __init__(self, initial: dict[int, bool]) -> None:
        self.swApp = _SwApp(initial)


def _ids() -> list[int]:
    return [toggle for toggle, _ in diag.SEAT_SKETCH_BASELINE.values()]


def _state(value: bool) -> dict[int, bool]:
    return dict.fromkeys(_ids(), value)


def _adapter_at(value: bool) -> _Adapter:
    return _Adapter(_state(value))


def test_the_two_declared_states_are_opposites_over_the_same_keys() -> None:
    """A preference may not be added to one state and forgotten in the other.

    If a key existed only in the drawing state it would be forced off and never
    restored -- the leak this module exists to prevent, reintroduced by
    omission.
    """
    assert set(diag.SKETCH_DRAWING_STATE) == set(diag.SEAT_SKETCH_BASELINE)
    for name, (toggle, drawing) in diag.SKETCH_DRAWING_STATE.items():
        baseline_toggle, baseline = diag.SEAT_SKETCH_BASELINE[name]
        assert toggle == baseline_toggle, name
        assert drawing is False and baseline is True, name


def test_a_poisoned_seat_is_repaired_and_named_at_recipe_start(monkeypatch) -> None:
    """The fleet-wide repair: the drift is reported BY NAME, not just fixed.

    A seat left at the suppressed value by a crashed leaf is what makes the
    same recipe fail on one worker and pass on another.  Reporting the names is
    what turns "flaky" into a fact.
    """
    warnings: list[str] = []
    monkeypatch.setattr(diag._telemetry, "warn", warnings.append)
    adapter = _adapter_at(False)

    drifted = diag.assert_seat_sketch_baseline(adapter, "91247A720")

    assert sorted(drifted) == sorted(diag.SEAT_SKETCH_BASELINE)
    assert adapter.swApp.toggles == _state(True)
    assert len(warnings) == 1
    for name in diag.SEAT_SKETCH_BASELINE:
        assert name in warnings[0]


def test_a_clean_seat_reports_no_drift_and_stays_clean(monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(diag._telemetry, "warn", warnings.append)
    adapter = _adapter_at(True)

    assert diag.assert_seat_sketch_baseline(adapter, "91247A720") == []
    assert adapter.swApp.toggles == _state(True)
    assert warnings == []


def test_suppression_restores_the_declared_baseline_not_the_observed_value() -> None:
    """The latch, directly.

    The seat starts POISONED (inference already off).  Save-and-restore-observed
    would write ``False`` back on exit and perpetuate it; the declared baseline
    leaves the seat correct, so the next leaf on this seat is not affected by
    this one.
    """
    adapter = _adapter_at(False)

    with diag.no_sketch_inference(adapter):
        assert adapter.swApp.toggles == _state(False)

    assert adapter.swApp.toggles == _state(True)


def test_suppression_restores_after_an_exception() -> None:
    """A recipe that raises must not leave the seat suppressed.

    This is the narrow window the watchdog and COM-disconnect paths can still
    lose -- a Python-level failure must not widen it.
    """
    adapter = _adapter_at(True)

    with pytest.raises(RuntimeError, match="logo ring extrude failed"):
        with diag.no_sketch_inference(adapter):
            raise RuntimeError("logo ring extrude failed")

    assert adapter.swApp.toggles == _state(True)


def test_nested_suppression_does_not_re_enable_inference_mid_draw() -> None:
    """Only the OUTERMOST exit restores.

    Restoring a declared baseline from an inner block would switch inference ON
    while the outer block is still drawing -- strictly worse than the code this
    replaces, whose inner restore happened to write the same value.  Depth
    counting is what makes the declared-baseline design safe to nest.
    """
    adapter = _adapter_at(True)

    with diag.no_sketch_inference(adapter):
        with diag.no_sketch_inference(adapter):
            assert adapter.swApp.toggles == _state(False)
        assert adapter.swApp.toggles == _state(False), "inner exit re-enabled inference"
        assert adapter._sketch_drawing_depth == 1

    assert adapter.swApp.toggles == _state(True)
    assert adapter._sketch_drawing_depth == 0


def test_an_exception_in_a_nested_block_does_not_pin_the_depth_counter() -> None:
    """A pinned counter would silently disable every later block on the seat.

    Adapters live for the whole leaf and build many parts, so a depth that
    never comes back down would mean no suppression and no restore for the rest
    of the run -- a latch again, wearing a different hat.
    """
    adapter = _adapter_at(True)

    with pytest.raises(ValueError):
        with diag.no_sketch_inference(adapter):
            with diag.no_sketch_inference(adapter):
                raise ValueError("inner failure")

    assert adapter._sketch_drawing_depth == 0
    adapter.swApp.writes.clear()
    with diag.no_sketch_inference(adapter):
        assert adapter.swApp.toggles == _state(False)
    assert adapter.swApp.writes, "a later block stopped applying preferences"


def _guarded_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Line spans of the two controls that defeat inference.

    ``no_sketch_inference`` forces the user preferences for its block.  An
    ``AddToDB = True`` try/finally is the stronger, engine-level control: it
    writes segments straight into the sketch database, so the inference stage
    -- and with it the SCREEN-SPACE snap tolerance that made this failure
    view-dependent -- never runs at all.  Either is sufficient; both are
    accepted here because the fleet legitimately uses both.
    """
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in GUARD_CONTEXTMANAGERS
                ):
                    spans.append((node.lineno, node.end_lineno))
        elif isinstance(node, ast.Try) and node.finalbody:
            restores = ast.dump(ast.Module(body=node.finalbody, type_ignores=[]))
            if "AddToDB" in restores:
                spans.append((node.lineno, node.end_lineno))
    return spans


def _unguarded_raw_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    spans = _guarded_line_ranges(tree)
    return [
        (node.lineno, node.func.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in RAW_SKETCH_CALLS
        and not any(start <= node.lineno <= end for start, end in spans)
    ]


def test_every_raw_sketch_primitive_is_authored_under_a_guard() -> None:
    """No recipe may inherit the seat's inference setting.

    Inference snapping is SCREEN-space, and nothing on the authoring path fits,
    orients or reads the view -- the only ``ViewZoomtofit2``/``ShowNamedView2``
    calls in the adapter live in ``export_image``, after the geometry exists.
    So a primitive drawn outside a guard depends on the worker's window pixel
    geometry, which is per-seat, unasserted and unrecorded.  That is not a
    setting that can be normalised; it is a dependency that has to go.
    """
    offenders = {
        path.name: calls
        for path in sorted(DIAGNOSTICS_DIR.glob("*.py"))
        if path.name not in AUDIT_EXEMPT
        for calls in [_unguarded_raw_calls(path)]
        if calls
    }

    assert offenders == {}, "\n".join(
        f"{name}:{line} {call} is outside a suppression block or AddToDB=True "
        "try/finally"
        for name, calls in offenders.items()
        for line, call in calls
    )


def test_the_audit_exemptions_still_exist_and_are_still_raw_com_probes() -> None:
    """An exemption must not outlive the file it excuses, or its reason.

    If one of these grows an ``adapter`` it is a recipe, not a probe, and it
    belongs in the audit.
    """
    for name, reason in AUDIT_EXEMPT.items():
        path = DIAGNOSTICS_DIR / name
        assert path.exists(), f"exemption for a file that no longer exists: {name}"
        assert reason
        source = path.read_text(encoding="utf-8")
        assert "no_sketch_inference" not in source
        assert _unguarded_raw_calls(path), f"{name} no longer needs an exemption"


def test_the_audit_detects_an_unguarded_primitive(tmp_path: Path) -> None:
    """The audit's own teeth: it must fail on the shape it is looking for."""
    offender = tmp_path / "diag_build_regression.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    with no_sketch_inference(adapter):\n"
        "        sk.CreateCircleByRadius(0.0, 0.0, 0.0, 1.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(3, "CreateLine")]


class _Sketch:
    def __init__(self, checked, points: int = 9) -> None:
        self._checked = checked
        self._points = points

    def GetSketchPoints2(self) -> tuple[object, ...]:
        return tuple(range(self._points))

    def CheckFeatureUse(self, usage: int, _open: int, _closed: int):
        assert usage == diag._SW_CHECK_BASEEXTRUDE
        return self._checked


class _CheckAdapter:
    """Just enough adapter for :func:`_report_profile_closure`."""

    def __init__(self, checked, points: int = 9) -> None:
        self.currentModel = types.SimpleNamespace(
            SketchManager=types.SimpleNamespace(ActiveSketch=_Sketch(checked, points))
        )

    def _attempt(self, thunk, default=None):
        try:
            return thunk()
        except Exception:
            return default


def _closure(monkeypatch, checked, *, loops: int = 2) -> tuple[str, list[str]]:
    warnings: list[str] = []
    monkeypatch.setattr(diag._telemetry, "warn", warnings.append)
    monkeypatch.setattr(diag, "_early_bound", lambda obj, _iface: obj)
    evidence = diag._report_profile_closure(_CheckAdapter(checked), "ring", loops, 9)
    return evidence, warnings


@pytest.mark.parametrize("checked", [(0, 0, 2), (0, 2, 0)])
def test_closure_read_back_accepts_a_healthy_profile_in_either_count_order(
    monkeypatch, checked
) -> None:
    """The unresolved half of ``CheckFeatureUse`` must not be a coin flip.

    The live signature reads ``(status, open, closed)``; the skill bundle's
    learning reads the last value as the open count.  A healthy profile is the
    same UNORDERED pair under either reading, so comparing it as a set settles
    the question by not asking it.  If this guard ever bets on one order, a
    wrong bet fails every closed profile in the repo.
    """
    evidence, warnings = _closure(monkeypatch, checked)

    assert warnings == []
    assert "contours=0/2" in evidence


def test_closure_read_back_raises_only_when_no_contour_exists(monkeypatch) -> None:
    """Zero closed contours under EVERY reading -- the one unambiguous defect."""
    with pytest.raises(RuntimeError, match="NO contours at all"):
        _closure(monkeypatch, (0, 0, 0))


@pytest.mark.parametrize(
    "checked",
    [
        (6, 1, 1),    # a revolve centreline may or may not count as open
        (11, 9, 0),   # MixedContours: the real unmerged shape
        (0, 3, 2),
        (99, 0, 2),   # a status nobody has characterised
    ],
)
def test_closure_read_back_warns_and_proceeds_on_anything_else(
    monkeypatch, checked
) -> None:
    """Unexplained counts cost a log line, never a build.

    Two questions about this diagnostic are open until someone runs it on a
    seat: which count is which, and whether construction geometry registers as
    an open contour (99607A213 draws a revolve centreline into the same sketch
    as its profile).  Until both are settled, the closure GUARANTEE is the
    offline assertion plus the checked merge relations; this call is forensics.
    A guard that can fail closed on healthy geometry is worse than no guard.
    """
    evidence, warnings = _closure(monkeypatch, checked)

    assert len(warnings) == 1
    assert "proceeding to the extrude" in warnings[0]
    assert evidence


@pytest.mark.parametrize("checked", [None, 0, (0, 2), (0, 0, 2, 4), (0, -1, 2)])
def test_an_unreadable_check_result_is_unknown_not_failure(
    monkeypatch, checked
) -> None:
    """Including the shape the learning doc implies: anything but a triple."""
    evidence, warnings = _closure(monkeypatch, checked)

    assert len(warnings) == 1
    assert evidence == "points=9, check=unreadable"
