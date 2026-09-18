r"""Offline invariants for "no built geometry depends on a user setting".

Two halves, both regression tests for the 2026-09-17 ``logo ring extrude
failed`` leaf on ``swmaker000005@5``:

* **The latch.** SolidWorks sketch-inference preferences are APPLICATION-level,
  so they outlive the document, the recipe and the leaf.  The replaced code
  saved the observed value on entry and wrote it back on exit, which turns one
  crash inside a suppression block into a permanently mis-set seat: the next
  leaf records the leaked value as "the original" and faithfully restores it
  forever.  These tests pin the declared-constant behaviour that replaces it.

* **The authoring audit.** Every raw sketch primitive in the DRAWING recipes,
  the shared drawing helpers and the diagnostics recipes must be authored
  inside a control that defeats inference, rather than inheriting whatever the
  seat happens to be set to.  This is the test that stops the class from
  regrowing: a new recipe that calls ``CreateLine`` outside a guard fails
  here, offline, with the file and line named.  Its reach is declared as
  NAMED GROUPS, each with its own minimum count, because this audit used to
  walk ``DIAGNOSTICS_DIR`` alone -- the one directory where a drawing defect
  cannot occur -- and so passed for its whole life while auditing nothing
  relevant.  ``drawing:top_frame``'s oblique D-D cut plane
  (``cad/docs/section-line-inference-snap.md``) is what that cost.

* **The preference writes.** The guard above is keyed on a NAME, so a recipe
  could keep its own set/try/finally beside a guarded call and the primitive
  audit would say nothing.  ``AddToDB`` is therefore permitted in exactly one
  SCOPE -- the contextmanager's own body -- with every unmigrated copy
  enrolled and equality-asserted, and the three OTHER per-session sketch
  preferences (``AutoInference``, ``AutoSolve``, ``DisplayWhenAdded``) are
  asserted to have no writer at all.  ``DisplayWhenAdded`` was the last one,
  hand-rolled around the guard at two drawing sites, and it is deleted rather
  than guarded because it cannot move a coordinate -- see
  :data:`HAND_ROLLED_SESSION_PREFERENCES` for why that is the cheaper
  invariant, and what stops the four lines growing back by symmetry.

* **The closure verdict's error policy.** ``assert_profile_closed`` decides
  from ONE shared read (``_common.record_sketch_closure``).  It must raise on a
  MEASURED open profile and must NOT raise when the read failed or when the
  contour count merely disagrees -- the absence of a measurement is not a
  measurement of absence, and a guard that fails closed on healthy geometry is
  worse than no guard.

Re-deriving what the audit catches, so the claim is backed by the commit and
not by a report -- the widened audit flags NINE pre-guard sites at
``4c5a4322`` (the commit before the migration), and the number is
re-derivable by anyone after any rebase.  The worktree stays at ``4c5a4322``
on purpose: that is the only tree where the unguarded sites still exist, so
replaying against a guard commit would derive nothing.  What a rebase moves
is which guard commit the count was last checked against -- currently
``ceaff371``, where those same nine are migrated and this file is green::

    git worktree add /tmp/pre 4c5a4322
    cp cad/scripts/test_sketch_preference_baseline.py /tmp/pre/cad/scripts/
    # run from the submodule-initialised clone: SCRIPTS_DIR comes from
    # __file__, so the interpreter's tree does not matter, the FILE's does
    uv run python -m pytest /tmp/pre/cad/scripts/test_sketch_preference_baseline.py \
        -q -k authored_under_a_guard -p no:cacheprovider

It fails listing ``_drawing_common.py:1127`` (``create_section_view``, the
site that shipped the oblique cut), ``_drawing_common.py:3578``
(``create_view_theoretical_datum``, whose overshoot is INHERENT: a
theoretical sharp is by construction not on the geometry the view shows),
``_stock_trim_drawing.py:69``, ``draw_arbor_pedestal.py:282``,
``draw_cone_swing_platform.py:153``, ``draw_cylinder_gear.py:155``,
``draw_rocker_arm_support.py:234``, ``draw_top_frame.py:427`` and
``draw_top_frame.py:856``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
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
    "CreatePoint",
    "Create3PointArc",
    "CreateSketchSlot",
    "CreateSketchText",
    "CreateSpline",
    "CreateTangentArc",
})

# ``CreatePoint`` is the one name two interfaces share, and only one of them
# authors sketch geometry: ``ISketchManager.CreatePoint(x, y, z)`` takes three
# doubles and puts a snappable point IN the sketch, while
# ``IMathUtility.CreatePoint(array)`` takes ONE SafeArray of three doubles and
# returns an ``IMathPoint`` that never enters a sketch -- every drawing recipe
# uses it to transform sheet coordinates
# (``utility.CreatePoint(double_array([x, y, 0.0]))``).  Discriminating by
# ARGUMENT COUNT is structural, straight off the two declared signatures;
# discriminating by receiver NAME would be a guess, and it would report every
# coordinate transform in the drawing tier as unguarded geometry -- a gate
# that cries wolf is a gate somebody switches off.
MINIMUM_ARGUMENTS = {"CreatePoint": 3}

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

# The ONE idiom a drawing recipe may use to author raw sketch geometry:
# ``_drawing_common.sketch_geometry_direct_to_db(sketch_manager)``, which
# reads the previous ``AddToDB`` off the live COM property, sets it, and
# restores it in ``finally``.  The audit keys on that NAME rather than on the
# hand-rolled set/try/finally SHAPE deliberately: the shape has to get the
# ``bool()``, the ``try`` and the ``finally`` right at every site, and a copy
# whose restore sits on the wrong path -- in the ``try``, or skipped by an
# early ``return`` -- leaves ``AddToDB`` flipped for the whole APPLICATION,
# which outlives the document, the recipe and the leaf.  That persistence is
# why seats drifting with inference OFF masked the oblique-cut defect for
# weeks.  A shape matcher cannot tell a correct copy from that one; a name can.
SKETCH_DB_CONTEXTMANAGER = "sketch_geometry_direct_to_db"

# Contextmanagers that make a receiver safe, per tier.  The drawing tier has
# exactly one; the diagnostics tier uses the APPLICATION-preference
# suppressors in ``diag_mcmaster_lib``, which a production recipe must not
# import (the diagnostics tree is not in any recipe's dependency closure).
DRAWING_GUARDS = frozenset({SKETCH_DB_CONTEXTMANAGER})
DIAGNOSTICS_GUARDS = frozenset({"no_sketch_inference", "preference_override"})

# ``no_sketch_inference``/``preference_override`` write APPLICATION
# preferences, so they cover every sketch manager in scope.
# ``sketch_geometry_direct_to_db`` writes ONE manager's ``AddToDB``, so it
# covers only the manager it was handed -- ``sk1`` says nothing about ``sk2``.
RECEIVER_SCOPED_GUARDS = frozenset({SKETCH_DB_CONTEXTMANAGER})

# The contextmanager's parameter, so its keyword spelling names the same
# receiver its positional spelling does.
GUARD_RECEIVER_KEYWORD = "sketch_manager"

# Files exempt from the audit, with the reason.  Both drive a bare ``sw`` COM
# application rather than the adapter -- there is no ``adapter`` to guard with
# -- and both draw a single hard-coded circle into an EMPTY throwaway part, so
# there is no model geometry and no second sketch entity for inference to snap
# to.  They exist to reproduce COM/assembly semantics, not to build parts.
# Keyed by path RELATIVE to the scripts directory, because the audit walks the
# tree: a bare file name would also exempt a same-named file dropped into any
# subdirectory, which is an exemption nobody wrote and nobody would see.
AUDIT_EXEMPT = {
    "diagnostics/diag_cwm_min.py": "raw swApp probe; one circle in an empty throwaway part",
    "diagnostics/diag_cwm_gear_min.py": "raw swApp probe; circles in an empty throwaway part",
}


@dataclass(frozen=True)
class _SourceGroup:
    """One named set of files the audit must READ, with its own tier policy.

    ``minimum`` is the anti-vacuity anchor and it is PER GROUP on purpose: one
    count over the union still passes when a whole group drops out, which is
    the shape of the defect this file is fixing.  A group that matches nothing
    -- a renamed directory, a pattern that went one level stale -- fails
    NAMING ITSELF instead of quietly contributing zero files.

    Patterns are matched with ``rglob``, so a recipe moved into a subpackage
    stays audited rather than falling silently out of reach.
    """

    root: Path
    patterns: tuple[str, ...]
    minimum: int
    guards: frozenset[str]
    inline_add_to_db_is_a_guard: bool

    def files(self) -> list[Path]:
        found = {
            path for pattern in self.patterns for path in self.root.rglob(pattern)
        }
        return sorted(
            path
            for path in found
            if path.relative_to(SCRIPTS_DIR).as_posix() not in AUDIT_EXEMPT
        )


# Every tier that authors sketch geometry through a guard this audit can read.
# ``build_*.py``/``_common.py``/``_assembly.py`` are deliberately absent and
# the reason is recorded in ``HAND_ROLLED_ADD_TO_DB`` rather than left as an
# absent glob -- an exclusion nobody can see is how this audit came to walk
# ``DIAGNOSTICS_DIR`` alone.
#
# The diagnostics tier still accepts the hand-rolled ``AddToDB`` try/finally,
# because its three remaining users predate the contextmanager and cannot
# import it; that tolerance is bounded, not open, because every one of those
# writes is named in ``HAND_ROLLED_ADD_TO_DB`` and a new one fails as an
# unregistered write.  So the hand-rolled shape can be used nowhere new.
SOURCE_GROUPS = {
    "drawing recipes": _SourceGroup(
        SCRIPTS_DIR, ("draw_*.py",), 90, DRAWING_GUARDS, False
    ),
    "shared drawing helpers": _SourceGroup(
        SCRIPTS_DIR, ("_drawing_common.py", "_stock_*.py"), 3, DRAWING_GUARDS, False
    ),
    "diagnostics recipes": _SourceGroup(
        DIAGNOSTICS_DIR, ("*.py",), 150, DIAGNOSTICS_GUARDS, True
    ),
}

_DRAWING_POLICY = SOURCE_GROUPS["drawing recipes"]
_DIAGNOSTICS_POLICY = SOURCE_GROUPS["diagnostics recipes"]

# Files that call a raw sketch primitive and are NOT in any group above, with
# the reason.  This is the reach assertion: the audit's coverage is checked
# against the tree rather than trusted, so a group deleted from
# ``SOURCE_GROUPS`` -- or a new tier of recipes nobody enrolled -- fails
# NAMING THE FILES it stopped auditing, instead of shrinking the audit in
# silence.  Asserted for equality, so an entry that gets audited or migrated
# must be deleted rather than left as a false statement about coverage.
#
# The whole model/assembly tier is here for ONE reason, and it is the build
# graph, not layering: the shared helper lives in ``_drawing_common.py``,
# which only drawing recipes import, so guarding these files means promoting
# it to ``_common.py`` -- in the helper closure of every part and assembly
# recipe, i.e. ~100 recipe digests and hours of farm time on a seat-limited
# fleet.  The drawing tier's digests are already moving this run, so the
# drawing half cost no extra COM work.  The hazard here is UNFIXED, not
# absent.
UNAUDITED_RAW_SKETCH_FILES = {
    "_assembly.py": "assembly tier; CreateEllipse",
    "_common.py": "model tier; CreateCenterRectangle",
    "_holes.py": "model tier; hole-wizard CreatePoint",
    "build_magnifying_wheel.py": "model tier; CreatePoint",
    "build_motion_study_springs.py": "model tier; CreatePoint",
    "build_output_fixture.py": "model tier; CreatePoint",
    "build_rocker_arm_support.py": "model tier; CreateLine",
}

# The single place allowed to write ``AddToDB`` by hand: the contextmanager's
# own body.  This is a SCOPE permission, not a line permission -- see
# :func:`_add_to_db_writers`.
ADD_TO_DB_ALLOW_LIST = f"_drawing_common.py::{SKETCH_DB_CONTEXTMANAGER}"

# Every place OUTSIDE that one definition which still writes ``AddToDB`` by
# hand, keyed ``<path relative to cad/scripts>::<enclosing function>``, with
# the reason it is not migrated.  A permission with no liveness check is
# untestable by construction, so this registry is asserted for EQUALITY
# against the tree: a new hand-rolled copy anywhere fails as an unregistered
# write, and an entry whose site HAS been migrated fails as a stale exemption
# that must be deleted.  It therefore self-deletes on migration instead of
# rotting into permanent cover for a gap nobody can see.
HAND_ROLLED_ADD_TO_DB = {
    # Model tier.  The correct fix is this same contextmanager promoted to
    # ``_common.py``, done when a full cold rebuild is already being paid for:
    # ``_common.py`` sits in the helper closure of every part and assembly
    # recipe, so touching it moves ~100 recipe digests and every assembly's.
    # ``_drawing_common.py`` is imported only by drawing recipes, whose
    # digests are already moving this run.  The hazard is real and unfixed:
    # these sites carry the same application-level preference that outlives
    # the leaf, and ``set_sketch_direct_db`` is a PAIRED call with no
    # ``finally``, so a raise between its True and its False leaks the flag.
    "_common.py::set_sketch_direct_db": "model tier's paired toggle; 50 build recipes call it",
    "_common.py::define_circle": "model tier sketch helper",
    "_common.py::define_centered_rectangle": "model tier sketch helper",
    "_common.py::add_line_chain": "model tier sketch helper",
    "_assembly.py::insert_sketch_text": "assembly tier sketch helper",
    "_assembly.py::add_ellipse": "assembly tier sketch helper",
    "_features.py::sketch_rounded_rect": "model tier feature helper",
    "_holes.py::wizard_holes": "model tier hole wizard",
    "build_motion_study_springs.py::_eye_point": "build recipe; authors no drawing",
    "build_rocker_arm_support.py::_add_construction_diagonals": "build recipe; authors no drawing",
    # Diagnostics tier.  These probe COM behaviour rather than build shipped
    # geometry, and two of them have inference itself as their SUBJECT, so
    # writing the preference is the experiment.
    "diagnostics/diag_build_91829A560.py::build_91829A560": "diagnostics probe",
    "diagnostics/diag_build_9489T111.py::_wire_path": "diagnostics probe",
    "diagnostics/diag_build_9490T1.py::_wire_path": "diagnostics probe",
    "diagnostics/diag_mcmaster_lib.py::draw_closed_profile": "diagnostics library; runs inside no_sketch_inference",
    "diagnostics/exp_inference_determinism.py::_one": "inference experiment; AddToDB is the subject",
    "diagnostics/exp_inference_zoom.py::_build_inference": "inference experiment; AddToDB is the subject",
    "diagnostics/exp_inference_zoom.py::main": "inference experiment; AddToDB is the subject",
}

# Test modules are outside that registry: their ``AddToDB`` assignments are a
# FAKE sketch manager initialising its own attribute, not a write to a seat
# preference.  The exclusion is pinned rather than assumed -- these fakes must
# still carry such a write -- so it is re-justified if they change shape,
# instead of silently covering a real write a test file grew later.
TEST_FAKE_ADD_TO_DB_ANCHORS = {
    "test_failure_forensics.py": "__init__",
    "test_rocker_arm_support_drawing.py": "__init__",
    # The guard's own contract file (``ceaff371``).  Enrolled because it is
    # the test module most easily mistaken for a real site: its double records
    # ``AddToDB`` at creation and exposes a ``CreatePoint``, so anyone grepping
    # for either would expect this audit to have something to say about it.
    # It does, and the answer is stated rather than implied by a prefix rule.
    "test_sketch_geometry_guards.py": "__init__",
}

# ``AddToDB`` is not the only per-SESSION sketch preference a recipe can reach.
# ``_common.sketch_manager_state`` (``_common`` 2986) enumerates the set
# the forensics bag snapshots, and that enumeration -- not this file's taste --
# is the authority; :func:`test_the_session_preference_names_come_from_the_forensics_bag`
# asserts the two agree, so a rename there cannot leave this audit auditing a
# spelling nothing writes.
SESSION_SKETCH_PREFERENCES = ("AddToDB", "AutoInference", "AutoSolve", "DisplayWhenAdded")

# The three besides ``AddToDB`` are not guarded, they are ABSENT: no non-test
# module writes any of them.  ``DisplayWhenAdded`` was the last one, hand-rolled
# around the guard at ``_drawing_common::create_view_theoretical_datum`` and
# ``draw_rocker_arm_support::_create_view_centerline``, and it is deleted rather
# than guarded: per ``ISketchManager::DisplayWhenAdded`` it only decides whether
# an entity is drawn between creation and the next redraw, it needs ``AddToDB``
# true to decide even that, and both sites rebuild before returning -- so no
# artifact can observe the value, and an assertion on it would fail a two-hour
# farm build over a cosmetic no-op while making the inference guard's message
# lie about what moved.  Absence is the cheaper invariant, and it is worth
# auditing precisely BECAUSE it is cheap to break: the deletion leaves an
# asymmetry at both sites that the next reader will be tempted to "fix" by
# symmetry with ``AddToDB``.  Equality-asserted like the registry above, so a
# re-added write fails as unregistered and an entry whose site is gone fails as
# stale.  A future diagnostics experiment whose SUBJECT is one of these
# preferences belongs here with its reason, exactly as the inference
# experiments are enrolled above.
HAND_ROLLED_SESSION_PREFERENCES: dict[str, str] = {}

_MODULE_SCOPE = "<module>"


class _SwApp:
    """Records every preference write, so restore ORDER and VALUES are visible.

    ``SetUserPreferenceToggle`` returns ``None``, because that is what the real
    one does: on ``ISldWorks`` it is declared ``VT_VOID`` (dispid 45, retval
    ``(24, 0)``), so pywin32 returns ``None`` on SUCCESS.  The ``VT_BOOL`` form
    lives on ``IModelDoc``/``IModelDoc2`` (65844) and ``IModelDocExtension``
    (159), and ``adapter.swApp`` is none of those.  A fake that returned a
    truthy value here would agree with the code under test instead of with the
    interface, and would green-light a guard that rejects every successful
    write on a live seat.

    ``refuse`` models the real SILENT failure: the call is accepted, returns
    nothing, and the preference simply does not move -- so a refused write is
    indistinguishable from a successful one except by READ-BACK.  Each member
    is a ``(toggle, value)`` pair, so a fake can decline the suppression write
    while still accepting the baseline restore that follows it.
    """

    def __init__(
        self,
        initial: dict[int, bool],
        refuse: frozenset[tuple[int, bool]] = frozenset(),
    ) -> None:
        self.toggles = dict(initial)
        self.writes: list[tuple[int, bool]] = []
        self.refuse = frozenset(refuse)

    def GetUserPreferenceToggle(self, toggle: int) -> bool:
        return self.toggles[toggle]

    def SetUserPreferenceToggle(self, toggle: int, value: bool) -> None:
        # The seat receives the call either way; only the effect differs.
        self.writes.append((toggle, bool(value)))
        if (toggle, bool(value)) in self.refuse:
            return
        self.toggles[toggle] = bool(value)


class _Adapter:
    def __init__(
        self,
        initial: dict[int, bool],
        refuse: frozenset[tuple[int, bool]] = frozenset(),
    ) -> None:
        self.swApp = _SwApp(initial, refuse)

    def _attempt(self, thunk, default=None):
        try:
            return thunk()
        except Exception:
            return default


def _ids() -> list[int]:
    return [toggle for toggle, _ in diag.SEAT_SKETCH_BASELINE.values()]


def _state(value: bool) -> dict[int, bool]:
    return dict.fromkeys(_ids(), value)


def _adapter_at(
    value: bool, refuse: frozenset[tuple[int, bool]] = frozenset()
) -> _Adapter:
    return _Adapter(_state(value), refuse)


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


def test_a_successful_void_write_is_not_mistaken_for_a_failure() -> None:
    """The regression that the return-value guard would fail on every seat.

    ``ISldWorks.SetUserPreferenceToggle`` is ``VT_VOID``, so pywin32 returns
    ``None`` when the write SUCCEEDS.  A guard written as
    ``if not app.SetUserPreferenceToggle(...)`` therefore rejects every
    successful write -- ``no_sketch_inference`` would raise before
    ``draw_closed_profile`` authored a single segment, taking
    ``_stock_fastener`` and every ``diag_build_*`` recipe with it, with an
    error asserting the opposite of what happened.  The fake returns ``None``
    here precisely so this test can see that; a fake that returned ``True``
    would be agreeing with the code instead of with the interface.
    """
    adapter = _adapter_at(True)
    assert adapter.swApp.SetUserPreferenceToggle(_ids()[0], True) is None

    with diag.no_sketch_inference(adapter):
        assert adapter.swApp.toggles == _state(False)
    assert adapter.swApp.toggles == _state(True)
    assert diag.assert_seat_sketch_baseline(adapter, "91247A720") == []


def test_a_silently_declined_suppression_is_caught_by_read_back() -> None:
    """A declined write is invisible in the return, so it is READ BACK.

    The seat accepts the call, returns nothing, and leaves the preference
    where it was.  Undetected, the guard enters its body with inference still
    LIVE on a seat that never took the suppression -- the per-seat divergence
    this module exists to remove, now hidden behind the guard that claims to
    have removed it.  So the refusal must propagate, the body must never run,
    and the seat must be left at the declared baseline, not half-suppressed.
    """
    inference = diag.SKETCH_DRAWING_STATE["swSketchInference"][0]
    adapter = _adapter_at(True, refuse=frozenset({(inference, False)}))

    # Anchored on the DIRECTION of the declined write, not merely on
    # "refused": ``apply_sketch_preferences`` raises one message for both the
    # suppression write and the baseline write, with the values the other way
    # round, so a bare substring is satisfied by whichever refusal reaches it
    # and cannot tell the two paths apart.
    with pytest.raises(
        RuntimeError,
        match="refused to set swSketchInference .* to False: it still reads "
        "back True",
    ):
        with diag.no_sketch_inference(adapter):
            raise AssertionError("the block must never run under a refused write")

    # The call WAS made -- this is not a missing write, it is an ignored one.
    assert (inference, False) in adapter.swApp.writes
    assert adapter.swApp.toggles == _state(True), "the baseline was not restored"
    assert getattr(adapter, "_sketch_drawing_depth", 0) == 0


def test_a_silently_declined_baseline_write_is_not_reported_as_a_repair(
    monkeypatch,
) -> None:
    """A repair that did not happen must not be announced as one.

    ``assert_seat_sketch_baseline`` decides "drifted" from a read taken BEFORE
    the write.  On a seat that declines the write, that read is still evidence
    of drift but the write did not fix it, so returning the name (and warning
    that it "has been reset") would tell the pool's leaf-admission audit the
    seat was repaired while it is still poisoned.
    """
    warnings: list[str] = []
    monkeypatch.setattr(diag._telemetry, "warn", warnings.append)
    inference = diag.SEAT_SKETCH_BASELINE["swSketchInference"][0]
    adapter = _adapter_at(False, refuse=frozenset({(inference, True)}))

    # The mirror image of the suppression refusal above, anchored so neither
    # test can be satisfied by the other path's message.
    with pytest.raises(
        RuntimeError,
        match="refused to set swSketchInference .* to True: it still reads "
        "back False",
    ):
        diag.assert_seat_sketch_baseline(adapter, "91247A720")

    assert adapter.swApp.toggles[inference] is False
    assert warnings == [], "a refused write was announced as a completed repair"


def _is_guard_call(expr: ast.expr, guards: frozenset[str]) -> frozenset[str]:
    """Receivers the contextmanager ``expr`` covers; empty if it is not one.

    Both spellings count: a bare ``no_sketch_inference(adapter)`` and a
    qualified ``diag.no_sketch_inference(adapter)``.  Matching only the bare
    name would make the audit report every primitive inside a legitimately
    guarded block the moment a recipe imported the module instead of the
    function -- a false alarm, which is how a gate gets switched off.

    An APPLICATION-preference guard covers every manager in scope.
    ``sketch_geometry_direct_to_db`` writes ONE manager's ``AddToDB``, so it
    covers only the manager it was handed: crediting it to a second manager
    would bless a primitive that really did go through the inference engine.
    """
    if not isinstance(expr, ast.Call):
        return frozenset()
    func = expr.func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return frozenset()
    if name not in guards:
        return frozenset()
    if name not in RECEIVER_SCOPED_GUARDS:
        return frozenset({_EVERY_RECEIVER})
    receiver = _guard_receiver(expr)
    return frozenset() if receiver is None else frozenset({receiver})


def _guard_receiver(expr: ast.Call) -> str | None:
    """The sketch manager a receiver-scoped guard was handed, if it is named.

    The positional and keyword spellings have to agree, and a call this walk
    cannot read (``*args``) covers nothing rather than everything.
    """
    for argument in expr.args:
        if isinstance(argument, ast.Starred):
            return None
        return ast.unparse(argument)
    for keyword in expr.keywords:
        if keyword.arg == GUARD_RECEIVER_KEYWORD:
            return ast.unparse(keyword.value)
    return None


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


def _is_raw_primitive_call(node: ast.AST) -> bool:
    """Is ``node`` a call that puts raw geometry into a sketch?

    ``MINIMUM_ARGUMENTS`` discriminates the shared ``CreatePoint`` name by
    signature.  A STARRED argument defeats the count -- ``CreatePoint(*(value
    / 1000.0 for value in local_point))`` in ``build_motion_study_springs`` is
    the sketch overload spelled through an unpack -- so a call whose arity
    this walk cannot read counts as the sketch one.  An audit that cannot tell
    must report, never quietly skip.
    """
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in RAW_SKETCH_CALLS:
        return False
    minimum = MINIMUM_ARGUMENTS.get(node.func.attr, 0)
    if not minimum or any(isinstance(argument, ast.Starred) for argument in node.args):
        return True
    return len(node.args) >= minimum


def _check_call(node: ast.Call, guards: frozenset[str]) -> tuple[int, str] | None:
    """Report ``node`` if it is a raw primitive whose RECEIVER is unguarded.

    ``sk1.AddToDB = True`` says nothing about primitives drawn through ``sk2``,
    so the call's own receiver has to be the guarded one.
    """
    if not _is_raw_primitive_call(node):
        return None
    func = node.func
    if _EVERY_RECEIVER in guards or ast.unparse(func.value) in guards:
        return None
    return (node.lineno, func.attr)


def _visit(
    node: ast.AST,
    guards: frozenset[str],
    found: list,
    enabled: dict[str, bool],
    policy: _SourceGroup,
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
    if isinstance(node, (ast.With, ast.AsyncWith)):
        for item in node.items:
            guards = guards | _is_guard_call(item.context_expr, policy.guards)
    if isinstance(node, ast.Call):
        offender = _check_call(node, guards)
        if offender is not None:
            found.append(offender)
    disabled: set[str] = set()
    for _field, value in ast.iter_fields(node):
        items = value if isinstance(value, list) else [value]
        if items and all(isinstance(item, ast.stmt) for item in items):
            disabled |= _visit_suite(items, guards, found, enabled, policy)
            continue
        for item in items:
            if isinstance(item, ast.AST):
                disabled |= _visit(item, guards, found, enabled, policy)
    return set() if isinstance(node, _DEFERRED_CODE) else disabled


def _visit_suite(
    suite: list[ast.stmt],
    guards: frozenset[str],
    found: list,
    enabled: dict[str, bool] | None,
    policy: _SourceGroup,
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

    ``policy.inline_add_to_db_is_a_guard`` is what makes the drawing tier
    stricter than the diagnostics tier: there, only
    ``sketch_geometry_direct_to_db`` counts, and the hand-rolled
    set/try/finally is refused even when it is written correctly, because a
    matcher cannot distinguish a correct copy from one whose restore an early
    ``return`` skips -- and that copy leaves the preference flipped for the
    whole application.
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
            active = (
                _try_guarded_receivers(stmt, state)
                if policy.inline_add_to_db_is_a_guard
                else frozenset()
            )
            sink(_visit_suite(stmt.body, guards | active, found, state, policy))
            # An `except`/`else`/`finally` clause runs after or instead of the
            # guarded work -- and the restore itself lives in `finally` -- so
            # a primitive there is not covered by the enable.
            for handler in stmt.handlers:
                sink(_visit(handler, guards, found, state, policy))
            for clause in (stmt.orelse, stmt.finalbody):
                if clause:
                    sink(_visit_suite(clause, guards, found, state, policy))
            continue
        sink(_visit(stmt, guards, found, state, policy))
    return disabled


def _unguarded_raw_calls(path: Path, policy: _SourceGroup) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    _visit_suite(
        ast.parse(path.read_text(encoding="utf-8")).body,
        frozenset(),
        found,
        None,
        policy,
    )
    return sorted(found)


def _add_to_db_writers(path: Path) -> dict[str, list[int]]:
    """``{enclosing function: lines}`` for every direct ``*.AddToDB = ...``.

    The permission this feeds is a SCOPE condition -- "only inside the
    contextmanager's own definition" -- and text cannot express a scope: a
    line matcher for ``sketch_manager.AddToDB = True`` permits that line
    anywhere in the file, including at a site that never got migrated, which
    is exactly the hole the audit exists to close.  So the enclosing function
    is carried DOWN the tree (``ast.walk`` discards the parent link) and the
    INNERMOST one is reported: a write inside a nested helper is that
    helper's, not its parent's.

    Only ASSIGNMENTS count.  READING ``AddToDB`` is how the contextmanager
    learns what to restore, so reporting a read would make the audit fail on
    the very definition it requires -- a check whose only route to green is
    being weakened into decoration.
    """
    writers: dict[str, list[int]] = {}

    def walk(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                else function
            )
            if _add_to_db_assignment(child) is not None:
                writers.setdefault(function, []).append(child.lineno)
            walk(child, inner)

    walk(ast.parse(path.read_text(encoding="utf-8")), _MODULE_SCOPE)
    return writers


def _session_preference_writers(path: Path) -> dict[str, list[int]]:
    """``{function::attribute: lines}`` for the NON-``AddToDB`` preferences.

    Same scope carry-down as :func:`_add_to_db_writers`, and deliberately
    disjoint from it: ``AddToDB`` has a guard whose shape has to be analysed,
    these three have no legitimate writer at all, so reporting them together
    would make one registry's green depend on the other's shape analysis.
    Keyed by attribute as well as function because the two hand-rolled sites
    that were deleted wrote ``DisplayWhenAdded`` in a function that also wrote
    ``AddToDB`` -- a function-only key would have let one hide the other.
    """
    writers: dict[str, list[int]] = {}
    audited = set(SESSION_SKETCH_PREFERENCES) - {"AddToDB"}

    def walk(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = (
                child.name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                else function
            )
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Attribute) and target.attr in audited:
                        key = f"{function}::{target.attr}"
                        writers.setdefault(key, []).append(child.lineno)
            walk(child, inner)

    walk(ast.parse(path.read_text(encoding="utf-8")), _MODULE_SCOPE)
    return writers


def _preference_write_tree() -> list[Path]:
    """Every non-test module under ``cad/scripts``, for the write registry."""
    return [
        path
        for path in sorted(SCRIPTS_DIR.rglob("*.py"))
        if not path.name.startswith("test_")
    ]


def _raw_sketch_calls_in(path: Path) -> bool:
    """Does ``path`` call a raw sketch primitive at all, guarded or not?

    Reach, not correctness: this is what decides whether a file OUGHT to be
    audited, so it ignores guards entirely.
    """
    return any(
        _is_raw_primitive_call(node)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    )


def test_every_raw_sketch_primitive_is_authored_under_a_guard() -> None:
    """No recipe may inherit the seat's inference setting.

    Inference snapping is SCREEN-space, and nothing on the authoring path fits,
    orients or reads the view -- the only ``ViewZoomtofit2``/``ShowNamedView2``
    calls in the adapter live in ``export_image``, after the geometry exists.
    So a primitive drawn outside a guard depends on the worker's window pixel
    geometry, which is per-seat, unasserted and unrecorded.  That is not a
    setting that can be normalised; it is a dependency that has to go.
    """
    offenders: list[tuple[str, str, int, str]] = []
    for name, group in SOURCE_GROUPS.items():
        parsed = 0
        for path in group.files():
            # PARSING is the proof the audit really read this file: a path
            # that moved raises here instead of contributing zero findings.
            # Emptiness is not the signal -- ``diagnostics/__init__.py`` is
            # legitimately empty -- the per-group COUNT is.
            calls = _unguarded_raw_calls(path, group)
            parsed += 1
            offenders.extend(
                (name, path.relative_to(SCRIPTS_DIR).as_posix(), line, call)
                for line, call in calls
            )
        # Per-group anti-vacuity, named.  One count over the union still
        # passes when a WHOLE group drops out, and a group that matches
        # nothing -- a renamed directory, a pattern gone one level stale after
        # an innocent file move -- must fail saying which group it was rather
        # than quietly contributing zero files.
        assert parsed >= group.minimum, (
            f"source group {name!r} read {parsed} files "
            f"({', '.join(group.patterns)} under {group.root}), expected at "
            f"least {group.minimum}: the files this audit claims to audit "
            "have moved or gone, so it would pass by inspecting nothing"
        )

    assert offenders == [], "\n".join(
        f"{relative}:{line} {call} is not inside "
        f"{' or '.join(sorted(SOURCE_GROUPS[name].guards))}(...) "
        f"[{name}]"
        for name, relative, line, call in offenders
    )


def test_every_file_that_authors_sketch_geometry_is_claimed() -> None:
    """The audit's REACH, asserted against the tree instead of trusted.

    The defect this file exists to close was reach, not logic: the scan walked
    ``DIAGNOSTICS_DIR`` alone -- the one directory where a drawing defect
    cannot occur -- and passed for its whole life while auditing nothing
    relevant.  A per-group count cannot catch that, because a group deleted
    from ``SOURCE_GROUPS`` takes its own count with it.  So every file in the
    tree that calls a raw primitive must be either audited or NAMED as
    unaudited, and dropping a group fails here listing the files it stopped
    covering.
    """
    audited = {path for group in SOURCE_GROUPS.values() for path in group.files()}
    exempt = {SCRIPTS_DIR / relative for relative in AUDIT_EXEMPT}
    unclaimed = sorted(
        path.relative_to(SCRIPTS_DIR).as_posix()
        for path in _preference_write_tree()
        if path not in audited
        and path not in exempt
        and _raw_sketch_calls_in(path)
        and path.relative_to(SCRIPTS_DIR).as_posix() not in UNAUDITED_RAW_SKETCH_FILES
    )
    assert unclaimed == [], (
        "these files author raw sketch geometry and no source group reads "
        f"them: {', '.join(unclaimed)} -- enrol them in SOURCE_GROUPS, or "
        "name them in UNAUDITED_RAW_SKETCH_FILES with the reason"
    )
    covered = {
        path.relative_to(SCRIPTS_DIR).as_posix()
        for path in audited
        if _raw_sketch_calls_in(path)
    }
    claimed_but_audited = sorted(covered & set(UNAUDITED_RAW_SKETCH_FILES))
    assert claimed_but_audited == [], (
        f"named unaudited but now audited: {', '.join(claimed_but_audited)}"
        " -- delete the entry; it reads as a statement that the gap is still "
        "open"
    )
    gone = sorted(
        relative
        for relative in UNAUDITED_RAW_SKETCH_FILES
        if not (SCRIPTS_DIR / relative).exists()
        or not _raw_sketch_calls_in(SCRIPTS_DIR / relative)
    )
    assert gone == [], (
        f"named unaudited but no longer authors sketch geometry: "
        f"{', '.join(gone)} -- delete the entry"
    )


def test_the_only_hand_rolled_preference_writes_are_the_registered_ones() -> None:
    """``AddToDB`` may be written by hand in ONE place, and nowhere new.

    This is the half that makes the name-keyed guard honest.  Without it a
    recipe could keep its own set/try/finally next to a guarded call and the
    primitive audit would say nothing, so the eight hand-rolled copies the
    contextmanager replaced could simply regrow.

    Equality, in both directions, on purpose: an unregistered write is a new
    copy, and a registered write that is GONE is an exemption asserting a
    false fact -- documentation the next reader trusts.  A permission with no
    liveness check is untestable by construction.
    """
    derived = {
        f"{path.relative_to(SCRIPTS_DIR).as_posix()}::{function}"
        for path in _preference_write_tree()
        for function in _add_to_db_writers(path)
    }
    unregistered = sorted(derived - {ADD_TO_DB_ALLOW_LIST} - set(HAND_ROLLED_ADD_TO_DB))
    assert unregistered == [], (
        "hand-rolled AddToDB juggling outside "
        f"{ADD_TO_DB_ALLOW_LIST}: {', '.join(unregistered)} -- author the "
        f"geometry inside {SKETCH_DB_CONTEXTMANAGER}(...) instead, so the "
        "restore cannot be skipped by a path nobody tested"
    )
    stale = sorted(set(HAND_ROLLED_ADD_TO_DB) - derived)
    assert stale == [], (
        f"exempt but no longer hand-rolling the preference: {', '.join(stale)}"
        " -- delete the exemption; it now excuses nothing and reads as a "
        "statement that the gap is still open"
    )


def test_the_one_allowed_preference_writer_is_a_live_definition() -> None:
    """The audit's single permission must point at code that exists.

    This is the self-rejection hazard, which is the vacuity class inverted: if
    the write moves out of ``sketch_geometry_direct_to_db`` into a helper, the
    scan refuses the definition it requires, every drawing recipe is reported
    and the cheapest way to green becomes weakening the guard.  Naming the
    move here says what actually happened.
    """
    writers = _add_to_db_writers(SCRIPTS_DIR / "_drawing_common.py")
    assert SKETCH_DB_CONTEXTMANAGER in writers, (
        f"_drawing_common.py writes AddToDB in {sorted(writers)} but not in "
        f"{SKETCH_DB_CONTEXTMANAGER}: the audit's one permission is scoped to "
        "that definition, so the preference scoping has moved out of the only "
        "place allowed to do it"
    )


def test_the_test_module_exclusion_still_covers_only_fake_managers() -> None:
    """Test modules are outside the write registry because their fakes assign
    their OWN ``AddToDB`` attribute.  Pinned, so the exclusion cannot quietly
    start covering a real preference write a test file grew later.
    """
    for name, function in TEST_FAKE_ADD_TO_DB_ANCHORS.items():
        path = SCRIPTS_DIR / name
        assert path.exists(), f"exclusion names a file that is gone: {name}"
        writers = _add_to_db_writers(path)
        assert function in writers, (
            f"{name} no longer assigns AddToDB in {function} (writes: "
            f"{sorted(writers)}): the test-module exclusion is covering "
            "something else now, so re-justify it"
        )
    # EQUALITY, not just liveness: "test_*.py is excluded" is a rule no test
    # can falsify, and ``ceaff371`` demonstrated the cost -- it added
    # ``test_sketch_geometry_guards.py``, whose double records ``AddToDB`` and
    # exposes a ``CreatePoint``, and the prefix rule absorbed it in silence.
    # A test module that grows a preference write must now be ENROLLED, so
    # the exclusion enumerates what it covers instead of asserting a prefix.
    writing_test_modules = sorted(
        path.relative_to(SCRIPTS_DIR).as_posix()
        for path in SCRIPTS_DIR.rglob("test_*.py")
        if _add_to_db_writers(path)
    )
    assert writing_test_modules == sorted(TEST_FAKE_ADD_TO_DB_ANCHORS), (
        f"test modules writing AddToDB {writing_test_modules} do not match "
        f"the enrolled exclusions {sorted(TEST_FAKE_ADD_TO_DB_ANCHORS)} -- "
        "enrol the new one with the function its FAKE writes from, or delete "
        "the entry whose fake is gone"
    )


def test_the_session_preference_names_come_from_the_forensics_bag() -> None:
    """The audited spellings are the repo's own, not this file's guess.

    ``AutoInference`` is one ``ISketchManager`` member among four with almost
    the same name (``AutoInference``, ``AutoSolve``, ``AutomaticSolve``,
    ``AutomaticRelations``), and a registry asserted empty against a spelling
    nothing can write is the purest vacuous pass there is: it would stay green
    through any number of real writes.  So the set is read out of
    ``sketch_manager_state``, which is the function that has to know
    these names to snapshot them, and a rename there reds HERE instead of
    silently retiring the audit.
    """
    tree = ast.parse((SCRIPTS_DIR / "_common.py").read_text(encoding="utf-8"))
    enumerations = [
        tuple(element.value for element in node.iter.elts)
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        and function.name == "sketch_manager_state"
        for node in ast.walk(function)
        if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Tuple)
        and all(
            isinstance(element, ast.Constant) and isinstance(element.value, str)
            for element in node.iter.elts
        )
    ]
    assert len(enumerations) == 1, (
        "sketch_manager_state no longer enumerates the sketch "
        f"preferences in exactly one tuple (found {len(enumerations)}): the "
        "audited set has no authority to read, so name it there again"
    )
    assert enumerations[0] == SESSION_SKETCH_PREFERENCES, (
        f"the forensics bag records {enumerations[0]} but this audit covers "
        f"{SESSION_SKETCH_PREFERENCES}: update the audited set, and decide "
        "for any NEW preference whether a recipe may write it"
    )


def test_no_module_writes_a_session_preference_other_than_add_to_db() -> None:
    """The three preferences besides ``AddToDB`` have no writer, and stay so.

    ``DisplayWhenAdded`` was hand-rolled around the guard at two sites and is
    deleted, not guarded, because it cannot move a coordinate and both sites
    rebuild before returning.  The deletion leaves an asymmetry a reader can
    "restore" in four lines, and it would be a write to an application-level
    preference with no read-back and no restore on an early ``return`` -- the
    same shape as the eight the contextmanager replaced, minus the one
    consequence that made those visible.  Equality in both directions: a
    re-added write is unregistered, an entry whose site is gone is stale.
    """
    derived = {
        f"{path.relative_to(SCRIPTS_DIR).as_posix()}::{key}"
        for path in _preference_write_tree()
        for key in _session_preference_writers(path)
    }
    unregistered = sorted(derived - set(HAND_ROLLED_SESSION_PREFERENCES))
    assert unregistered == [], (
        "writes a per-session sketch preference with no registered reason: "
        f"{', '.join(unregistered)} -- these outlive the document, the recipe "
        "and the leaf, and none of them is needed: DisplayWhenAdded is "
        "cosmetic before the next rebuild, and inference is already owned by "
        f"{SKETCH_DB_CONTEXTMANAGER}(...)"
    )
    stale = sorted(set(HAND_ROLLED_SESSION_PREFERENCES) - derived)
    assert stale == [], (
        f"registered as writing a session preference but no longer does: "
        f"{', '.join(stale)} -- delete the entry"
    )


def test_the_session_preference_matcher_sees_a_hand_rolled_display_pair(
    tmp_path: Path,
) -> None:
    """The empty registry's positive control, without which it proves nothing.

    An equality assertion between two empty sets passes whether the matcher
    works or not, so the matcher is shown finding the exact shape that was
    deleted -- keyed by attribute, and NOT reporting the ``AddToDB`` write
    beside it, which belongs to the other registry and would otherwise be
    counted twice.
    """
    offender = tmp_path / "draw_regrown_display.py"
    offender.write_text(
        "def _centerline(sketch_manager):\n"
        "    previous_display = bool(sketch_manager.DisplayWhenAdded)\n"
        "    sketch_manager.DisplayWhenAdded = True\n"
        "    try:\n"
        "        with sketch_geometry_direct_to_db(sketch_manager):\n"
        "            return sketch_manager.CreateCenterLine(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)\n"
        "    finally:\n"
        "        sketch_manager.DisplayWhenAdded = previous_display\n"
        "\n"
        "def _probe(sk):\n"
        "    sk.AddToDB = True\n"
        "    sk.AutoSolve = False\n",
        encoding="utf-8",
    )

    assert _session_preference_writers(offender) == {
        "_centerline::DisplayWhenAdded": [3, 8],
        "_probe::AutoSolve": [12],
    }


def test_the_audit_exemptions_still_exist_and_are_still_raw_com_probes() -> None:
    """An exemption must not outlive the file it excuses, or its reason.

    If one of these grows an ``adapter`` it is a recipe, not a probe, and it
    belongs in the audit.
    """
    for relative, reason in AUDIT_EXEMPT.items():
        path = SCRIPTS_DIR / relative
        assert path.exists(), f"exemption for a file that no longer exists: {relative}"
        assert reason
        source = path.read_text(encoding="utf-8")
        assert "no_sketch_inference" not in source
        assert _unguarded_raw_calls(path, _DIAGNOSTICS_POLICY), (
            f"{relative} no longer needs an exemption"
        )


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(3, "CreateLine")]


def test_a_real_add_to_db_block_is_a_guard_only_in_the_diagnostics_tier(
    tmp_path: Path,
) -> None:
    """The hand-rolled engine-level control: enable, restore in ``finally``.

    It is still a real guard where it is the only option (three diagnostics
    recipes predate the contextmanager and cannot import it), and it is
    refused where the contextmanager exists.  Both halves in one test, because
    the tier difference IS the invariant: 28 lines of duplicated preference
    juggling become unreachable rather than merely correct today.
    """
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

    assert _unguarded_raw_calls(good, _DIAGNOSTICS_POLICY) == []
    # ... and is REFUSED in the drawing tier, where the contextmanager exists.
    # A correct copy and a copy whose restore an early ``return`` skips are
    # the same four lines to a matcher, and the second leaves the preference
    # flipped for the whole application, outliving the leaf.
    assert _unguarded_raw_calls(good, _DRAWING_POLICY) == [(6, "CreateLine")]


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(6, "CreateLine")]


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(6, "CreateLine")]


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(6, "CreateLine")]


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [
        (9, "CreateCircleByRadius")
    ]


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

    assert _unguarded_raw_calls(guarded, _DIAGNOSTICS_POLICY) == []


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(8, "CreateLine")]


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(5, "CreateLine")]


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

    assert _unguarded_raw_calls(guarded, _DIAGNOSTICS_POLICY) == []


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

    assert _unguarded_raw_calls(guarded, _DIAGNOSTICS_POLICY) == []


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(4, "CreateLine")]


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

    assert _unguarded_raw_calls(guarded, _DIAGNOSTICS_POLICY) == []


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

    assert _unguarded_raw_calls(offender, _DIAGNOSTICS_POLICY) == [(8, "CreateLine")]


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

    assert _unguarded_raw_calls(guarded, _DIAGNOSTICS_POLICY) == []


def test_the_drawing_guard_covers_the_manager_it_was_handed(tmp_path: Path) -> None:
    """The idiom a migrated drawing recipe uses, in both spellings."""
    guarded = tmp_path / "draw_guarded.py"
    guarded.write_text(
        "def _detail(draw, sketch_manager):\n"
        "    with sketch_geometry_direct_to_db(sketch_manager):\n"
        "        sketch_manager.CreateCenterLine(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)\n"
        "    with dc.sketch_geometry_direct_to_db(sketch_manager=sketch_manager):\n"
        "        sketch_manager.CreateCircle(0.0, 0.0, 0.0, 1.0, 0.0, 0.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(guarded, _DRAWING_POLICY) == []


def test_the_drawing_guard_does_not_cover_a_second_manager(tmp_path: Path) -> None:
    """It writes ONE manager's ``AddToDB``, so it protects only that one.

    An assembly drawing holding the sheet's manager and a view's is the
    realistic shape; crediting the block to both would bless a primitive that
    really did go through the inference engine.
    """
    offender = tmp_path / "draw_two_managers.py"
    offender.write_text(
        "def _detail(sk1, sk2):\n"
        "    with sketch_geometry_direct_to_db(sk1):\n"
        "        sk1.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n"
        "        sk2.CreateLine(0.0, 0.0, 0.0, 2.0, 2.0, 0.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender, _DRAWING_POLICY) == [(4, "CreateLine")]


def test_the_diagnostics_suppressors_do_not_guard_a_drawing_recipe(
    tmp_path: Path,
) -> None:
    """One spelling per tier.  ``no_sketch_inference`` lives in the
    diagnostics tree, which is in no recipe's dependency closure, so a
    drawing recipe reaching for it is not authored correctly -- it is
    authored against a module it must not import.
    """
    offender = tmp_path / "draw_wrong_guard.py"
    offender.write_text(
        "def _detail(adapter, sk):\n"
        "    with no_sketch_inference(adapter):\n"
        "        sk.CreateLine(0.0, 0.0, 0.0, 1.0, 1.0, 0.0)\n",
        encoding="utf-8",
    )

    assert _unguarded_raw_calls(offender, _DRAWING_POLICY) == [(3, "CreateLine")]


def test_a_preference_write_is_attributed_to_its_enclosing_function(
    tmp_path: Path,
) -> None:
    """The permission is a SCOPE, not a line.

    The same assignment appears three times here: inside the allow-listed
    contextmanager, inside a sibling function, and inside a nested helper.  A
    text matcher for the line permits all three, which would bless every
    unmigrated site in a file that merely CONTAINS the definition.  Only the
    innermost enclosing function is credited, and a READ is not a write.
    """
    module = tmp_path / "_drawing_common_like.py"
    module.write_text(
        "import contextlib\n"
        "\n"
        "@contextlib.contextmanager\n"
        "def sketch_geometry_direct_to_db(sketch_manager):\n"
        "    previous = bool(sketch_manager.AddToDB)\n"
        "    sketch_manager.AddToDB = True\n"
        "    try:\n"
        "        yield\n"
        "    finally:\n"
        "        sketch_manager.AddToDB = previous\n"
        "\n"
        "def _unmigrated(sketch_manager):\n"
        "    sketch_manager.AddToDB = True\n"
        "\n"
        "def _outer(sketch_manager):\n"
        "    def _inner():\n"
        "        sketch_manager.AddToDB = False\n"
        "    _inner()\n"
        "\n"
        "def _only_reads(sketch_manager):\n"
        "    return bool(sketch_manager.AddToDB)\n",
        encoding="utf-8",
    )

    assert _add_to_db_writers(module) == {
        "sketch_geometry_direct_to_db": [6, 10],
        "_unmigrated": [13],
        "_inner": [17],
    }


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


# The verdict shape this call path can ACTUALLY produce.  Every key here is one
# ``_sketch_state``/``_point_census`` fills in unconditionally; the logo ring
# unmerged is 18 points sitting in 9 coincident pairs over 9 distinct places.
# Deliberately does NOT carry ``unmerged_points``: ``_sketch_state`` derives
# that only when given ``expected_points``, and
# ``assert_profile_closed`` passes only ``expect_contours``.  Feeding it here
# is what hid a permanently absent number in the raise.
_OPEN_LOGO_VERDICT = {
    "closure": "open",
    "contour_count": 0,
    "segment_count": 9,
    "point_count": 18,
    "distinct_point_positions": 9,
    "coincident_point_pairs": 9,
}


def test_a_measured_open_profile_fails_the_build(monkeypatch) -> None:
    """Zero contours is a MEASUREMENT of the failure mode, so it must raise."""
    with pytest.raises(RuntimeError, match="profile did not close"):
        _verdict(monkeypatch, _OPEN_LOGO_VERDICT)


def test_the_failure_message_carries_only_numbers_that_were_measured(
    monkeypatch,
) -> None:
    """A dead leaf's log gets this string and nothing else, so it must be whole.

    The message used to name ``unmerged_points``, which this path can never
    populate, so the sole human-readable record of the failure carried a
    literal ``None`` where the merge evidence should be.  A field that is
    always absent is worse than an omitted one: it reads as "measured, and the
    answer is nothing".
    """
    with pytest.raises(RuntimeError) as raised:
        _verdict(monkeypatch, _OPEN_LOGO_VERDICT)
    message = str(raised.value)

    assert "None" not in message, message
    # The fingerprint of an unmerged profile: 18 points over 9 places, 9 pairs.
    assert "coincident_point_pairs=9" in message
    assert "18 sketch points" in message
    assert "9 distinct places" in message


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
