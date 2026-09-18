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


def _assigns_add_to_db(node: ast.AST, *, value: bool | None) -> bool:
    """Is ``node`` an ``*.AddToDB = <value>`` assignment?

    ``value=True`` matches only the literal enable; ``value=None`` matches any
    assignment, which is what a restore of the saved previous value looks like.
    """
    if not isinstance(node, ast.Assign):
        return False
    if not any(
        isinstance(t, ast.Attribute) and t.attr == "AddToDB" for t in node.targets
    ):
        return False
    if value is None:
        return True
    return isinstance(node.value, ast.Constant) and node.value.value is True


def _guarded_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    """Line spans of the two controls that defeat inference.

    ``no_sketch_inference`` forces the user preferences for its block.  An
    ``AddToDB = True`` try/finally is the stronger, engine-level control: it
    writes segments straight into the sketch database, so the inference stage
    -- and with it the SCREEN-SPACE snap tolerance that made this failure
    view-dependent -- never runs at all.  Either is sufficient; both are
    accepted here because the fleet legitimately uses both.

    The ``AddToDB`` form is matched STRUCTURALLY, and it must be the whole
    shape: ``AddToDB = True`` assigned before the ``try``, and some
    ``AddToDB`` assignment in the ``finally`` that puts it back.  Merely
    mentioning ``AddToDB`` in a ``finally`` is not a guard -- a block that only
    ever assigns ``AddToDB = False`` restores a value it never enabled, so its
    primitives went through inference after all.  Accepting that shape would
    make the audit's teeth cosmetic.
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
            if not any(
                _assigns_add_to_db(stmt, value=None) for stmt in node.finalbody
            ):
                continue
            # The enable must PRECEDE the try, in the same suite.
            enabled = any(
                _assigns_add_to_db(sibling, value=True)
                for parent in ast.walk(tree)
                for suite in _suites(parent)
                if node in suite
                for sibling in suite[: suite.index(node)]
            )
            if enabled:
                spans.append((node.lineno, node.end_lineno))
    return spans


def _suites(node: ast.AST) -> list[list[ast.stmt]]:
    return [
        value
        for value in (getattr(node, field, None) for field in ("body", "orelse",
                                                               "finalbody"))
        if isinstance(value, list)
    ]


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


def _verdict(monkeypatch, verdict: dict, *, loops: int = 2) -> dict:
    """Drive :func:`assert_profile_closed` against a canned closure verdict.

    The verdict is produced by ``_common.record_sketch_closure`` -- ONE read,
    shared with the forensics record -- so this decision is pure and testable
    without any COM at all.
    """
    monkeypatch.setattr(diag, "record_sketch_closure",
                        lambda _a, _l, **_kw: verdict)
    return diag.assert_profile_closed(object(), "ring", loops=loops)


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


def test_a_snap_member_this_build_does_not_expose_reads_as_unknown(
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
