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

* **The closure verdict's error policy.** ``assert_profile_closed`` decides
  from ONE shared read (``_common.record_sketch_closure``).  It must raise on a
  MEASURED open profile and must NOT raise when the read failed or when the
  contour count merely disagrees -- the absence of a measurement is not a
  measurement of absence, and a guard that fails closed on healthy geometry is
  worse than no guard.
"""

from __future__ import annotations

import ast
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

# DELIBERATELY excluded: ``CreateSplinesByEqnParams2``, the only other
# ``ISketchManager`` entity creator this repo calls
# (``diag_build_1330K524._transition_sketch``, ``diag_build_9432K31``).  It
# takes an ``ISplineParamData`` -- control points and a knot vector, no
# interactive point input -- and the family is documented to IGNORE
# ``AddToDB``/``DisplayWhenAdded`` and write straight to the sketch database
# (cited at ``diag_build_1330K524.py:520`` and ``diag_build_9432K31.py:496``,
# both proven live on a seat).  That is permanently the state
# ``AddToDB = True`` is used to reach, so there is no inference stage for a
# user setting to change and a guard would be theatre.  Anything that grows
# interactive point input belongs in the set above.

# Contextmanagers that force the sketch preferences for their block.
GUARD_CONTEXTMANAGERS = frozenset({"no_sketch_inference", "preference_override"})

# Files exempt from the audit, with the reason.  Both drive a bare ``sw`` COM
# application rather than the adapter -- there is no ``adapter`` to guard with
# -- and both draw a single hard-coded circle into an EMPTY throwaway part, so
# there is no model geometry and no second sketch entity for inference to snap
# to.  They exist to reproduce COM/assembly semantics, not to build parts.
# Keyed by path RELATIVE to the diagnostics directory, because the audit walks
# the tree: a bare file name would also exempt a same-named file dropped into
# any subdirectory, which is an exemption nobody wrote and nobody would see.
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

    def _attempt(self, thunk, default=None):
        try:
            return thunk()
        except Exception:
            return default


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


def test_a_failed_entry_does_not_pin_the_depth_counter() -> None:
    """The silent-disable must not be reachable through the guard's own error.

    ``SetUserPreferenceToggle`` is a COM call on a seat that may be dying.  If
    the counter went up before that write succeeded, a throw would leave it at
    1 with no ``finally`` ever entered, and every later block on this adapter
    would see a nonzero depth and become a no-op -- no suppression, no
    restore, for the life of the process.  A half-applied suppression is also a
    poisoned seat, so the declared baseline goes back before the throw
    propagates.
    """
    adapter = _adapter_at(True)
    failing = adapter.swApp
    calls: list[int] = []

    def _set(toggle: int, value: bool) -> None:
        calls.append(toggle)
        if value is False:
            raise OSError("the seat dropped the connection")
        failing.toggles[toggle] = bool(value)

    adapter.swApp.SetUserPreferenceToggle = _set

    with pytest.raises(OSError):
        with diag.no_sketch_inference(adapter):
            raise AssertionError("the block must never run")

    assert getattr(adapter, "_sketch_drawing_depth", 0) == 0
    assert adapter.swApp.toggles == _state(True), "the baseline was not restored"

    # Drop the instance attribute so the real method is found on the class
    # again: the SAME adapter must still work, which is the whole point.
    del adapter.swApp.SetUserPreferenceToggle
    adapter.swApp.writes.clear()
    with diag.no_sketch_inference(adapter):
        assert adapter.swApp.toggles == _state(False)
    assert adapter.swApp.writes, "a later block stopped applying preferences"


def _is_guard_call(expr: ast.expr) -> bool:
    """Is ``expr`` a call to one of the guard contextmanagers?

    Both spellings count: a bare ``no_sketch_inference(adapter)`` and a
    qualified ``diag.no_sketch_inference(adapter)``.  Matching only the bare
    name would make the audit report every primitive inside a legitimately
    guarded block the moment a recipe imported the module instead of the
    function -- a false alarm, which is how a gate gets switched off.
    """
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    if isinstance(func, ast.Name):
        return func.id in GUARD_CONTEXTMANAGERS
    return isinstance(func, ast.Attribute) and func.attr in GUARD_CONTEXTMANAGERS


def _add_to_db_assignment(node: ast.AST) -> tuple[str, ast.expr] | None:
    """``(receiver source, assigned value)`` for an ``*.AddToDB = ...`` assign.

    The RECEIVER matters: ``sk1.AddToDB = True`` says nothing about what
    ``sk2`` will do with the primitives drawn through it.
    """
    if not isinstance(node, ast.Assign):
        return None
    for target in node.targets:
        if isinstance(target, ast.Attribute) and target.attr == "AddToDB":
            return ast.unparse(target.value), node.value
    return None


# A ``no_sketch_inference`` block forces APPLICATION preferences, so it covers
# every sketch manager in scope; an ``AddToDB`` block covers one receiver.
_EVERY_RECEIVER = "*"

# Code objects whose body may run long after the enclosing guard has exited.
# A raw primitive in one of them is NOT covered by a guard it was merely
# written inside; only a guard within the object itself counts.  A class BODY
# is not deferred -- its statements run during class creation, under the
# guard -- so ``ClassDef`` is deliberately absent.
_DEFERRED_CODE = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.GeneratorExp,
)


def _enable_state(value: ast.expr) -> bool:
    return isinstance(value, ast.Constant) and value.value is True


def _try_guarded_receivers(
    node: ast.Try, enabled: dict[str, bool]
) -> frozenset[str]:
    """Receivers an ``AddToDB`` try/finally really guards for its body.

    All of it is required, and each part is a failure this audit would
    otherwise wave through:

    * the ``finally`` must restore the receiver -- a ``finally`` that only
      assigns ``AddToDB = False`` restores a value it never enabled;
    * that receiver's LATEST assignment before the ``try`` must be literal
      ``True`` -- an intervening ``sk.AddToDB = False`` puts the manager back
      through the inference engine, and an earlier enable does not undo it;
    * the body must not reassign it -- from that statement on the guarantee is
      gone, so the whole block is refused rather than split at it.  Only the
      BODY counts here: an ``except``/``else``/``finally`` clause runs after or
      instead of the guarded work, so a reassignment there cannot reach a
      primitive in the body, and treating it as one would report guarded work
      as unguarded.
    """
    restored = {
        found[0]
        for stmt in node.finalbody
        if (found := _add_to_db_assignment(stmt)) is not None
    }
    active = {receiver for receiver in restored if enabled.get(receiver)}
    if not active:
        return frozenset()
    inside = {
        found[0]
        for body_stmt in node.body
        for stmt in ast.walk(body_stmt)
        if isinstance(stmt, ast.stmt)
        and (found := _add_to_db_assignment(stmt)) is not None
    }
    return frozenset(active - inside)


def _check_call(node: ast.Call, guards: frozenset[str]) -> tuple[int, str] | None:
    """Report ``node`` if it is a raw primitive whose RECEIVER is unguarded.

    ``sk1.AddToDB = True`` says nothing about primitives drawn through ``sk2``,
    so the call's own receiver has to be the guarded one.
    """
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in RAW_SKETCH_CALLS:
        return None
    if _EVERY_RECEIVER in guards or ast.unparse(func.value) in guards:
        return None
    return (node.lineno, func.attr)


def _visit(
    node: ast.AST, guards: frozenset[str], found: list, enabled: dict[str, bool]
) -> set[str]:
    """Walk ``node``, carrying what is guarded and enabled at this point.

    Returns the receivers this node left DISABLED, so an enclosing suite can
    be pessimistic about a disable inside a branch it cannot evaluate.
    """
    if isinstance(node, _DEFERRED_CODE):
        # Its body runs later, so neither the guard nor the enable in force
        # HERE says anything about it -- and by the same argument a disable
        # in there says nothing about the code around it.
        guards, enabled = frozenset(), {}
    if isinstance(node, (ast.With, ast.AsyncWith)) and any(
        _is_guard_call(item.context_expr) for item in node.items
    ):
        guards = guards | {_EVERY_RECEIVER}
    if isinstance(node, ast.Call):
        offender = _check_call(node, guards)
        if offender is not None:
            found.append(offender)
    disabled: set[str] = set()
    for _field, value in ast.iter_fields(node):
        items = value if isinstance(value, list) else [value]
        if items and all(isinstance(item, ast.stmt) for item in items):
            disabled |= _visit_suite(items, guards, found, enabled)
            continue
        for item in items:
            if isinstance(item, ast.AST):
                disabled |= _visit(item, guards, found, enabled)
    return set() if isinstance(node, _DEFERRED_CODE) else disabled


def _visit_suite(
    suite: list[ast.stmt],
    guards: frozenset[str],
    found: list,
    enabled: dict[str, bool] | None = None,
) -> set[str]:
    """Walk a statement suite IN ORDER, tracking ``AddToDB`` as it changes.

    Order matters: the enable, the ``try`` it guards and any later disable are
    separate statements, and only their sequence says what was in force when a
    primitive ran.

    ``enabled`` arrives from the enclosing suite, because nothing requires the
    enable and the ``try`` it guards to be siblings -- a recipe may well
    enable once and then guard inside an ``if`` or a ``for``.  Starting each
    nested suite blank reported that as unguarded geometry.

    State flows DOWN by copy, so one branch cannot enable a receiver for its
    siblings, and a disable flows back UP via the return value, so a branch
    this walk cannot evaluate is assumed to have taken it.
    """
    state = dict(enabled or {})
    disabled: set[str] = set()

    def sink(receivers: set[str]) -> None:
        for receiver in receivers:
            state[receiver] = False
            disabled.add(receiver)

    for stmt in suite:
        assignment = _add_to_db_assignment(stmt)
        if assignment is not None:
            receiver, value = assignment
            state[receiver] = _enable_state(value)
            if state[receiver]:
                disabled.discard(receiver)
            else:
                disabled.add(receiver)
        if isinstance(stmt, ast.Try) and stmt.finalbody:
            active = _try_guarded_receivers(stmt, state)
            sink(_visit_suite(stmt.body, guards | active, found, state))
            # An `except`/`else`/`finally` clause runs after or instead of the
            # guarded work -- and the restore itself lives in `finally` -- so
            # a primitive there is not covered by the enable.
            for handler in stmt.handlers:
                sink(_visit(handler, guards, found, state))
            for clause in (stmt.orelse, stmt.finalbody):
                if clause:
                    sink(_visit_suite(clause, guards, found, state))
            continue
        sink(_visit(stmt, guards, found, state))
    return disabled


def _unguarded_raw_calls(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    _visit_suite(ast.parse(path.read_text(encoding="utf-8")).body, frozenset(), found)
    return sorted(found)


def test_every_raw_sketch_primitive_is_authored_under_a_guard() -> None:
    """No recipe may inherit the seat's inference setting.

    Inference snapping is SCREEN-space, and nothing on the authoring path fits,
    orients or reads the view -- the only ``ViewZoomtofit2``/``ShowNamedView2``
    calls in the adapter live in ``export_image``, after the geometry exists.
    So a primitive drawn outside a guard depends on the worker's window pixel
    geometry, which is per-seat, unasserted and unrecorded.  That is not a
    setting that can be normalised; it is a dependency that has to go.
    """
    # rglob, not glob: a recipe moved into a subpackage must not fall out of
    # the audit silently.  And the audited set is asserted non-empty, because
    # a renamed or missing directory would otherwise make this whole gate pass
    # by inspecting nothing -- the failure mode that turns a regression gate
    # into decoration.
    audited = [
        path
        for path in sorted(DIAGNOSTICS_DIR.rglob("*.py"))
        if str(path.relative_to(DIAGNOSTICS_DIR).as_posix()) not in AUDIT_EXEMPT
    ]
    assert len(audited) > 20, (
        f"the audit inspected {len(audited)} files under {DIAGNOSTICS_DIR}; "
        "it is meant to cover every recipe in the tree"
    )
    offenders = {
        path.name: calls
        for path in audited
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
    for relative, reason in AUDIT_EXEMPT.items():
        path = DIAGNOSTICS_DIR / relative
        assert path.exists(), f"exemption for a file that no longer exists: {relative}"
        assert reason
        source = path.read_text(encoding="utf-8")
        assert "no_sketch_inference" not in source
        assert _unguarded_raw_calls(path), f"{relative} no longer needs an exemption"


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


def test_a_real_add_to_db_block_counts_as_a_guard(tmp_path: Path) -> None:
    """The engine-level control: enable before the try, restore in finally."""
    good = tmp_path / "diag_build_addtodb.py"
    good.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(good) == []


def test_an_intervening_disable_cancels_the_guard(tmp_path: Path) -> None:
    """``AddToDB = False`` puts the manager back through the inference engine.

    An earlier enable does not undo it, so the primitive inside the ``try``
    really does run with inference on -- and its result really does depend on
    the seat's window pixel geometry.
    """
    offender = tmp_path / "diag_build_disabled.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    sk.AddToDB = True\n"
        "    sk.AddToDB = False\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = True\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(6, "CreateLine")]


def test_an_enable_on_a_different_receiver_is_not_a_guard(tmp_path: Path) -> None:
    """``sk1.AddToDB = True`` says nothing about primitives drawn through ``sk2``.

    Two sketch managers is the realistic shape: a recipe that opens a second
    document, or an assembly recipe holding both the part's manager and the
    assembly's.
    """
    offender = tmp_path / "diag_build_two_managers.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk1 = adapter.currentSketchManager\n"
        "    sk2 = adapter.otherSketchManager\n"
        "    sk1.AddToDB = True\n"
        "    try:\n"
        "        sk2.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk2.AddToDB = False\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(6, "CreateLine")]


def test_a_disable_inside_the_block_ends_the_guard(tmp_path: Path) -> None:
    """Everything after ``sk.AddToDB = False`` is back on the inference engine.

    The enable before the ``try`` does not survive its own block being turned
    off, so a primitive after that assignment is exactly as view-dependent as
    an unguarded one.
    """
    offender = tmp_path / "diag_build_disabled_inside.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    sk.AddToDB = True\n"
        "    try:\n"
        "        sk.AddToDB = False\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = True\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(6, "CreateLine")]


def test_a_primitive_in_the_finally_clause_is_not_guarded(tmp_path: Path) -> None:
    """The restore runs there, so the enable no longer holds.

    A cleanup path that draws is still drawing: this is the shape a "just
    put back a placeholder circle on failure" handler takes.
    """
    offender = tmp_path / "diag_build_finally_draws.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = prev\n"
        "        sk.CreateCircleByRadius(0.0, 0.0, 0.0, 1.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(9, "CreateCircleByRadius")]


def test_a_reset_in_an_except_clause_does_not_unguard_the_body(
    tmp_path: Path,
) -> None:
    """A handler runs after the body, so it cannot reach a primitive in it.

    This is the shape a recipe takes when it disables direct-to-database
    before reporting a failure -- and crediting that reset to the body would
    make the audit report correctly guarded geometry, which is the failure
    mode that gets a gate deleted.
    """
    guarded = tmp_path / "diag_build_reset_on_error.py"
    guarded.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    except RuntimeError:\n"
        "        sk.AddToDB = False\n"
        "        raise\n"
        "    finally:\n"
        "        sk.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded) == []


def test_a_call_on_an_unguarded_receiver_inside_the_block_is_reported(
    tmp_path: Path,
) -> None:
    """Enabling ``sk1`` says nothing about primitives drawn through ``sk2``.

    The block is a perfectly well-formed guard -- enable before, restore in
    ``finally`` -- for a sketch manager that never draws anything.  Crediting
    it to the one that does is how a line-span audit blesses a primitive that
    really did go through the inference engine.
    """
    offender = tmp_path / "diag_build_wrong_receiver.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk1 = adapter.currentSketchManager\n"
        "    sk2 = adapter.otherSketchManager\n"
        "    prev = sk1.AddToDB\n"
        "    sk1.AddToDB = True\n"
        "    try:\n"
        "        sk1.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "        sk2.CreateLine(0.0, 0.0, 0.0, 2.0, 2.0, 0.0)\n"
        "    finally:\n"
        "        sk1.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(8, "CreateLine")]


def test_a_nested_function_does_not_inherit_the_guard(tmp_path: Path) -> None:
    """A deferred body can run long after the contextmanager has exited.

    ``adapter.register(draw)`` inside the block is the realistic shape: the
    callback is CALLED later, with the seat back at its baseline, so lexical
    containment proves nothing about what was in force when it drew.
    """
    offender = tmp_path / "diag_build_deferred.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    with no_sketch_inference(adapter):\n"
        "        def draw():\n"
        "            sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "        adapter.register(draw)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(5, "CreateLine")]


def test_a_nested_function_with_its_own_guard_is_clean(tmp_path: Path) -> None:
    """The fix must not punish the correct spelling of a deferred draw.

    A callback that opens the guard itself is authored correctly whenever it
    runs, which is the whole difference from the case above.
    """
    guarded = tmp_path / "diag_build_deferred_guarded.py"
    guarded.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    def draw():\n"
        "        with no_sketch_inference(adapter):\n"
        "            sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    adapter.register(draw)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded) == []


def test_a_qualified_guard_call_is_recognised(tmp_path: Path) -> None:
    """``diag.no_sketch_inference(...)`` guards exactly as the bare name does.

    Failing to see the qualified spelling would report primitives inside a
    properly guarded block, and a gate that cries wolf is a gate somebody
    switches off.
    """
    guarded = tmp_path / "diag_build_qualified.py"
    guarded.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    with diag.no_sketch_inference(adapter):\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded) == []


def test_a_finally_that_never_enabled_add_to_db_is_not_a_guard(
    tmp_path: Path,
) -> None:
    """The shape that a text search for "AddToDB" would wave through.

    Restoring a value that was never enabled means the primitives went through
    the inference stage after all -- pixel tolerance, per-seat window size,
    exactly the failure this audit exists to prevent. A mention of ``AddToDB``
    is not a guard; the enable is.
    """
    offender = tmp_path / "diag_build_pretend.py"
    offender.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = False\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(4, "CreateLine")]


def test_an_enable_in_an_outer_suite_still_guards_a_nested_block(
    tmp_path: Path,
) -> None:
    """Nothing requires the enable and its ``try`` to be siblings.

    A recipe that enables once and then guards inside an ``if`` or a ``for``
    is authoring its geometry exactly as this PR asks; reporting it as
    unguarded would be a false positive on correct code, and those are what
    get a gate deleted instead of fixed.
    """
    guarded = tmp_path / "diag_build_nested_suite.py"
    guarded.write_text(
        "async def build(adapter, deep):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "    if deep:\n"
        "        try:\n"
        "            sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "        finally:\n"
        "            sk.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded) == []


def test_a_disable_in_a_branch_cancels_a_later_guard(tmp_path: Path) -> None:
    """State flows down by copy, but a DISABLE flows back up.

    This walk cannot evaluate ``if deep``, so it has to assume the branch was
    taken: crediting the outer enable here would bless a primitive that may
    well have gone through the inference engine, which is the failure this
    audit exists to catch.
    """
    offender = tmp_path / "diag_build_branch_disable.py"
    offender.write_text(
        "async def build(adapter, deep):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "    if deep:\n"
        "        sk.AddToDB = False\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender) == [(8, "CreateLine")]


def test_a_disable_inside_a_nested_function_does_not_leak_out(
    tmp_path: Path,
) -> None:
    """Deferred code runs later, so it says nothing about the code around it.

    The inner ``reset`` may never be called at all; letting its assignment
    cancel the enclosing guard would report correct geometry as unguarded.
    """
    guarded = tmp_path / "diag_build_deferred_disable.py"
    guarded.write_text(
        "async def build(adapter):\n"
        "    sk = adapter.currentSketchManager\n"
        "    prev = sk.AddToDB\n"
        "    sk.AddToDB = True\n"
        "\n"
        "    def reset():\n"
        "        sk.AddToDB = False\n"
        "\n"
        "    try:\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "    finally:\n"
        "        sk.AddToDB = prev\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded) == []


def _verdict(monkeypatch, verdict: dict, *, loops: int = 2) -> dict:
    """Drive :func:`assert_profile_closed` against a canned closure verdict.

    The verdict is produced by ``_common.record_sketch_closure`` -- ONE read,
    shared with the forensics record -- so this decision is pure and testable
    without any COM at all.
    """
    seen: list[tuple] = []

    def _record(_adapter, _label, sketch=None, **kwargs):
        seen.append((sketch, kwargs.get("expect_contours")))
        return verdict

    monkeypatch.setattr(diag, "record_sketch_closure", _record)
    result = diag.assert_profile_closed(
        object(), "ring", loops=loops, feature="LogoProfile"
    )
    # The sketch is named, never left to "last ProfileFeature wins": a recipe
    # that authors two sketches before checking would otherwise verdict the
    # wrong one, and a verdict on the wrong sketch is worse than no verdict.
    assert seen == [("LogoProfile", loops)]
    return result


def test_a_measured_open_profile_fails_the_build(monkeypatch) -> None:
    """Zero contours is a MEASUREMENT of the failure mode, so it must raise."""
    with pytest.raises(RuntimeError, match="profile did not close"):
        _verdict(monkeypatch, {
            "closure": "open",
            "contour_count": 0,
            "segment_count": 9,
            "point_count": 18,
            "unmerged_points": 9,
        })


def test_an_unreadable_verdict_does_not_fail_the_build(monkeypatch) -> None:
    """The ABSENCE of a measurement is not a measurement of absence.

    An RPC hiccup becoming a geometry failure would be a guard that fails
    closed on healthy geometry, which is worse than no guard.  The real gates
    are offline (``endpoint_merges``, ``minor_arc``) and have already run.
    """
    verdict = {"closure": "unknown", "point_census_error": "RPC_E_DISCONNECTED"}

    assert _verdict(monkeypatch, verdict) is verdict


def test_a_contour_count_that_disagrees_does_not_fail_the_build(
    monkeypatch,
) -> None:
    """It is unmeasured whether a revolve centreline counts as a contour.

    99607A213 draws its revolve axis into the same sketch as its profile, so a
    healthy one-loop flare could legitimately report two contours.  Until that
    is measured on a seat, the COUNT may warn but may not fail; only zero does.
    """
    verdict = {"closure": "closed", "contour_count": 3, "segment_count": 9}

    assert _verdict(monkeypatch, verdict) is verdict


def test_the_closed_verdict_is_returned_for_failure_context(monkeypatch) -> None:
    """The caller passes these counts to ``capture_com_failure``.

    Returning the verdict is what removes the SECOND COM read: the extrude's
    failure context and the closure record come from the same numbers.
    """
    verdict = {"closure": "closed", "contour_count": 2, "unmerged_points": 0}

    assert _verdict(monkeypatch, verdict) == verdict


def test_the_snap_family_is_recorded_and_never_written(monkeypatch) -> None:
    """The evidence the failing leaf did not have -- and it must stay read-only.

    The 2026-09-17 log contains no record of any seat preference, which is why
    the failure could only be diagnosed by argument.  Two of these govern the
    competitor that most plausibly broke the logo ring: CenterPoints (the inner
    triangle's vertices ARE the outer corner arcs' centres, so every outer arc
    endpoint has a snap competitor at exactly 0.400 mm) and Nearest (an
    effectively unbounded screen-space radius).  Writing them is NOT the fix --
    ``swSketchInference`` is the family's master switch and the drawing state
    already forces it off -- so a write here would be restore surface for no
    gain.
    """
    logged: list[str] = []
    monkeypatch.setattr(diag._telemetry, "info", logged.append)
    adapter = _Adapter(dict.fromkeys(diag.SKETCH_SNAP_AUDIT.values(), True))

    state = diag.audit_sketch_snaps(adapter, "91247A720")

    assert state == dict.fromkeys(diag.SKETCH_SNAP_AUDIT, True)
    assert adapter.swApp.writes == []
    assert "CenterPoints=True" in logged[0] and "Nearest=True" in logged[0]


def test_a_snap_member_this_build_cannot_read_is_recorded_as_unknown(
    monkeypatch,
) -> None:
    """A refused read must be None, not a crash and not a silent False.

    False would read as "that snap is off", which is the opposite of unknown.
    """
    monkeypatch.setattr(diag._telemetry, "info", lambda _msg: None)
    ids = dict.fromkeys(diag.SKETCH_SNAP_AUDIT.values(), True)
    del ids[diag.SKETCH_SNAP_AUDIT["swSketchSnapsNearest"]]

    state = diag.audit_sketch_snaps(_Adapter(ids), "91247A720")

    assert state["swSketchSnapsNearest"] is None
    assert state["swSketchSnapsCenterPoints"] is True


def test_the_snap_audit_ids_do_not_collide_with_the_asserted_toggles() -> None:
    """Audit-only and applied sets must stay disjoint.

    An id in both would be written by ``apply_sketch_preferences`` while
    claiming to be read-only.
    """
    applied = {toggle for toggle, _ in diag.SEAT_SKETCH_BASELINE.values()}
    assert applied.isdisjoint(diag.SKETCH_SNAP_AUDIT.values())
    assert len(set(diag.SKETCH_SNAP_AUDIT.values())) == len(diag.SKETCH_SNAP_AUDIT)
