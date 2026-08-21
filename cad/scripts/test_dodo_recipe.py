"""Regression test for the recipe-change detector in ``dodo.py`` (D2 fix).

``_RecipeTracker`` must decide FULL-vs-REFRESH from the recipe *content* digest
compared against the value saved on the last SUCCESSFUL run -- never from doit's
injected ``changed`` arg, which is corrupted after an intervening failed task.
"""

import contextlib
import importlib.util
import inspect
import os
import re
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None, (
        f"could not locate dodo.py under {REPO_ROOT}"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeTask:
    def __init__(self):
        self.value_savers = []

    def saved(self):
        """Mimic doit running value_savers on success and merging the dicts."""
        out = {}
        for saver in self.value_savers:
            out.update(saver())
        return out


def test_recipe_tracker_full_vs_refresh(tmp_path):
    dodo = _load_dodo()
    recipe = tmp_path / "build_x_assembly.py"
    common = tmp_path / "_common.py"
    recipe.write_text("recipe v0\n")
    common.write_text("common v0\n")
    files = [str(recipe), str(common)]

    def run(values):
        """One up-to-date evaluation: returns (up_to_date, recipe_changed, saved)."""
        tracker = dodo._RecipeTracker("x", files)
        task = _FakeTask()
        up_to_date = tracker(task, values)
        return up_to_date, dodo._RECIPE_CHANGED["x"], task.saved()

    # 1. first ever run: no saved digest -> recipe "changed" -> FULL
    up, changed, saved1 = run({})
    assert up is False and changed is True

    # 2. unchanged recipe vs last success -> up-to-date / REFRESH territory
    up, changed, saved2 = run(saved1)
    assert up is True and changed is False

    # 3. THE D2 CASE: a prior task FAILED, so `values` still holds the last
    #    *successful* digest (savers never ran on failure). Recipe is untouched,
    #    only parts changed -> must still be REFRESH, never a spurious FULL.
    up, changed, _ = run(saved1)  # same last-success values as step 2
    assert up is True and changed is False, "post-failure parts-only must REFRESH"

    # 4. a real recipe edit -> digest differs from last success -> FULL
    recipe.write_text("recipe v1\n")
    up, changed, saved4 = run(saved1)
    assert up is False and changed is True

    # 5. after that FULL succeeds and saves, an unchanged recipe is REFRESH again
    up, changed, _ = run(saved4)
    assert up is True and changed is False


def test_recipe_tracker_detects_any_recipe_member(tmp_path):
    """Editing _common.py (not just the assembly script) must trigger FULL."""
    dodo = _load_dodo()
    recipe = tmp_path / "build_x_assembly.py"
    common = tmp_path / "_common.py"
    hook = tmp_path / "hook.py"
    for f in (recipe, common, hook):
        f.write_text("v0\n")
    files = [str(recipe), str(common), str(hook)]

    tracker = dodo._RecipeTracker("x", files)
    task = _FakeTask()
    tracker(task, {})
    saved = task.saved()

    for member in (recipe, common, hook):
        member.write_text("v1\n")
        t2 = _FakeTask()
        up = dodo._RecipeTracker("x", files)(t2, saved)
        assert up is False, f"editing {member.name} must invalidate the recipe"
        member.write_text("v0\n")  # restore for next iteration


def test_drawing_depends_on_actual_part_execution():
    dodo = _load_dodo()
    token = dodo._part_execution_token("platen_guide")
    part = next(task for task in dodo.task_part() if task["name"] == "platen_guide")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "platen_guide"
    )
    assert token in part["targets"]
    assert token in drawing["file_dep"]


def test_assembly_drawing_depends_on_actual_assembly_execution():
    dodo = _load_dodo()
    token = dodo._assembly_execution_token("pen")
    assembly = next(task for task in dodo.task_assembly() if task["name"] == "pen")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "pen_assembly"
    )
    assert token in assembly["targets"]
    assert token in drawing["file_dep"]


def test_release_revision_source_invalidates_native_and_drawing_tasks():
    dodo = _load_dodo()
    revision_source = str(dodo.RELEASE_VERSION_FILE)

    part = next(task for task in dodo.task_part() if task["name"] == "platen_guide")
    assembly = next(task for task in dodo.task_assembly() if task["name"] == "pen")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "platen_guide"
    )

    assert revision_source in part["file_dep"]
    assert revision_source in assembly["file_dep"]
    assert revision_source in drawing["file_dep"]


def test_execution_identity_is_stable_for_same_artifact(tmp_path, monkeypatch):
    dodo = _load_dodo()
    part = tmp_path / "part.SLDPRT"
    token = tmp_path / ".part.execution"
    monkeypatch.setattr(dodo, "_sldprt", lambda _stem: str(part))
    monkeypatch.setattr(dodo, "_part_execution_token", lambda _stem: str(token))

    part.write_bytes(b"cached artifact A")
    dodo._stamp_part_execution("part")
    first = token.read_text()
    dodo._stamp_part_execution("part")
    assert token.read_text() == first

    part.write_bytes(b"same recipe, different SolidWorks identity")
    dodo._stamp_part_execution("part")
    assert token.read_text() != first


def test_execution_identity_tracker_migrates_missing_and_legacy_tokens(tmp_path):
    dodo = _load_dodo()
    token = tmp_path / ".part.execution"
    tracker = dodo._ExecutionIdentityTracker(str(token))
    assert list(inspect.signature(tracker).parameters) == ["task", "values"]

    assert tracker(None, {}) is False
    token.write_text("1720860000000000000\n")
    assert tracker(None, {}) is False
    token.write_text("a" * 64 + "\n")
    assert tracker(None, {}) is True


def test_assembly_depends_on_exact_child_execution_identities():
    """Issue #301: recipe-equal CAD files can carry different PIDs/rebuild stamps."""
    dodo = _load_dodo()
    for stem in dodo.ASSEMBLY_ORDER:
        deps = set(dodo._assembly_file_deps(stem))
        for ref in dodo.references_of(stem):
            token = (
                dodo._assembly_execution_token(ref)
                if ref in dodo.ASSEMBLY_ORDER
                else dodo._part_execution_token(ref)
            )
            assert token in deps, f"assembly:{stem} lacks exact identity for {ref}"


def test_verify_gates_depend_on_exact_assembly_identities():
    """An identity-only refresh must invalidate persisted verify stamps."""
    dodo = _load_dodo()
    soundness = {task["name"]: task for task in dodo.task_verify_soundness()}
    for stem in dodo.ASSEMBLY_ORDER:
        assert dodo._assembly_execution_token(stem) in soundness[stem]["file_dep"]

    kinematics = next(
        task for task in dodo.task_verify() if task["name"] == "kinematics"
    )
    for stem in ("pen", "magnifier", "paper_drive"):
        assert dodo._assembly_execution_token(stem) in kinematics["file_dep"]


def test_assembly_cache_key_changes_with_child_identity(tmp_path, monkeypatch):
    """A foreign same-recipe child must miss instead of restoring an incompatible assembly."""
    dodo = _load_dodo()
    recipe = tmp_path / "build_parent_assembly.py"
    child = tmp_path / "child.SLDPRT"
    token = tmp_path / ".child.execution"
    recipe.write_text("unchanged recipe\n")
    child.write_bytes(b"recipe-stable CAD placeholder")
    token.write_text("a" * 64 + "\n")

    monkeypatch.setattr(dodo, "references_of", lambda _stem: ("child",))
    monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: [str(recipe)])
    monkeypatch.setattr(dodo, "_sldprt", lambda _stem: str(child))
    monkeypatch.setattr(dodo, "_part_execution_token", lambda _stem: str(token))

    first = dodo._cache_key(dodo._assembly_file_deps("parent"))
    token.write_text("b" * 64 + "\n")
    second = dodo._cache_key(dodo._assembly_file_deps("parent"))
    assert first != second


def test_cached_drawing_hit_never_builds(tmp_path, monkeypatch):
    dodo = _load_dodo()
    output = tmp_path / "platen-guide.SLDDRW"
    restores = []
    stores = []

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(
        dodo._cache,
        "restore",
        lambda key, outputs, label: restores.append((key, outputs, label)) or True,
    )
    monkeypatch.setattr(
        dodo._cache,
        "store",
        lambda key, outputs, label: stores.append((key, outputs, label)) or "stored",
    )
    monkeypatch.setattr(
        dodo,
        "_exec",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cache HIT built drawing")
        ),
    )

    dodo._cached_drawing_action("platen_guide")

    assert len(restores) == 1
    assert not stores


def test_cached_drawing_miss_builds_once_then_stores(tmp_path, monkeypatch):
    dodo = _load_dodo()
    output = tmp_path / "platen-guide.SLDDRW"
    outcomes = iter((False, False))
    restores = []
    builds = []
    stores = []

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(
        dodo._cache,
        "restore",
        lambda key, outputs, label: (
            restores.append((key, outputs, label)) or next(outcomes)
        ),
    )
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext())
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)

    def build(*_args, **_kwargs):
        builds.append(True)
        output.write_bytes(b"drawing")

    monkeypatch.setattr(dodo, "_exec_com", build)
    monkeypatch.setattr(
        dodo._cache,
        "store",
        lambda key, outputs, label: stores.append((key, outputs, label)) or "stored",
    )

    dodo._cached_drawing_action("platen_guide")

    assert len(restores) == 2
    assert builds == [True]
    assert len(stores) == 1
    assert stores[0][1] == [output]


def test_cache_status_covers_drawings():
    dodo = _load_dodo()
    rows = dict(dodo._cache_rows())
    stem = dodo._drawing_order()[0]
    assert rows[f"drawing:{stem}"] == dodo._drawing_file_deps(stem)


def test_content_checker_digest_ignores_yaml_noise(tmp_path):
    """Option A: ContentChecker digests the PARSED yaml, so comment / whitespace /
    numeric-reflow edits to a shared cad/config/*.yaml leave the digest unchanged
    (no spurious part rebuild); a real value change still flips it."""

    dodo = _load_dodo()
    digest = dodo.ContentChecker._digest

    cfg = tmp_path / "tolerances.yaml"
    cfg.write_text("rack_backlash_mm: 0.30\nseat_clearance_mm: 1.5\n")
    base = digest(str(cfg))

    cfg.write_text(
        "# provenance: retargeted\nrack_backlash_mm: 0.300\nseat_clearance_mm: 1.5\n  \n"
    )
    assert digest(str(cfg)) == base, (
        "comment/whitespace/0.30->0.300 reflow must be inert"
    )

    cfg.write_text("rack_backlash_mm: 0.31\nseat_clearance_mm: 1.5\n")
    assert digest(str(cfg)) != base, "a real value change must invalidate"

    nonyaml = tmp_path / "build_x.py"
    nonyaml.write_text("WIDTH = 3.0\n")
    assert digest(str(nonyaml)) == dodo._canonical_file_md5(str(nonyaml))


def test_content_checker_digest_is_checkout_eol_independent(tmp_path):
    """Issue #255: Git-equivalent text content must produce one digest whether a
    Windows checkout materialises LF, CRLF, or mixed line endings. Binary inputs
    remain byte-sensitive -- newline bytes can be meaningful inside a binary."""
    dodo = _load_dodo()
    digest = dodo.ContentChecker._digest

    source = tmp_path / "build_x.py"
    source.write_bytes(b"WIDTH = 3.0\nHEIGHT = 4.0\n")
    lf = digest(str(source))
    source.write_bytes(b"WIDTH = 3.0\r\nHEIGHT = 4.0\r\n")
    assert digest(str(source)) == lf
    source.write_bytes(b"WIDTH = 3.0\r\nHEIGHT = 4.0\n")
    assert digest(str(source)) == lf

    source.write_bytes(b"WIDTH = 3.1\r\nHEIGHT = 4.0\r\n")
    assert digest(str(source)) != lf, "a real source edit must still invalidate"

    binary = tmp_path / "input.bin"
    binary.write_bytes(b"\x00row\n")
    binary_lf = digest(str(binary))
    binary.write_bytes(b"\x00row\r\n")
    assert digest(str(binary)) != binary_lf


def test_part_cache_key_is_checkout_eol_independent(tmp_path):
    """Exercise #255 through the real cache-key boundary, not only its digest
    helper: changing one Python dep's checkout representation must leave the final
    task key unchanged while a semantic source edit must move it."""
    dodo = _load_dodo()
    source = tmp_path / "build_x.py"
    source.write_bytes(b"VALUE = 1\n")
    lf = dodo._cache_key([str(source)], "part:x")
    source.write_bytes(b"VALUE = 1\r\n")
    assert dodo._cache_key([str(source)], "part:x") == lf
    source.write_bytes(b"VALUE = 2\r\n")
    assert dodo._cache_key([str(source)], "part:x") != lf


def test_content_checker_check_modified_ignores_comment(tmp_path):
    """The full check_modified path (mtime + size differ for a comment edit) must
    still report NOT-modified -- the stock MD5Checker would short-circuit to
    modified on the size delta before ever comparing content."""
    dodo = _load_dodo()
    checker = dodo.ContentChecker()
    cfg = tmp_path / "c.yaml"
    cfg.write_text("k: 1\n")
    state = checker.get_state(str(cfg), None)

    # comment edit + FORCE a distinct mtime so the fast-path can't short-circuit
    cfg.write_text("# a comment\nk: 1\n")
    os.utime(str(cfg), (state[0] + 10, state[0] + 10))
    st = os.stat(str(cfg))
    assert st.st_mtime != state[0] and st.st_size != state[1]
    assert checker.check_modified(str(cfg), st, state) is False, (
        "comment edit must be inert"
    )

    # real value change with a distinct mtime -> modified
    cfg.write_text("k: 2\n")
    os.utime(str(cfg), (state[0] + 20, state[0] + 20))
    st = os.stat(str(cfg))
    assert checker.check_modified(str(cfg), st, state) is True, (
        "value change must invalidate"
    )


class _FakeStat:
    """Minimal os.stat stand-in: ContentChecker.check_modified only reads st_mtime."""

    def __init__(self, mtime: float):
        self.st_mtime = mtime


def test_artefact_digest_is_recipe_not_bytes():
    """A .SLDPRT/.SLDASM digest is its producing task's build-input recipe, NOT the
    artefact bytes -- so it is computed WITHOUT ever reading the (possibly absent /
    byte-churned) artefact, and equals the part task's file_dep recipe digest."""
    dodo = _load_dodo()
    stem = dodo.part_stems()[0]
    art = dodo._sldprt(stem)
    recipe = dodo._digest_files(
        dodo._part_file_deps(dodo.SCRIPTS_DIR / f"build_{stem}.py", stem)
    )
    assert dodo.ContentChecker._digest(art) == recipe
    # Deterministic across calls (memoized), and independent of the bytes on disk:
    # the artefact need not even exist for the digest to resolve.
    assert dodo.ContentChecker._digest(art) == recipe
    assert not os.path.exists(art) or dodo.ContentChecker._digest(art) == recipe


def test_verify_gate_logic_off_build_closure_is_a_file_dep():
    """A verify/preflight gate whose LOGIC lives in a module on NO assembly's build
    closure (so it rides no .SLDASM digest) MUST list that module as a direct
    file_dep -- else a change to the gate logic leaves the verify-*.ok stamp
    stale-fresh and SKIPS the gate (codex PR #193: the transient-drive replay
    lives in _assembly_postbuild.py, off every build closure). General guard: computes the
    verify/preflight ``_*.py`` helpers that are on no assembly closure and asserts
    each task depends on them."""
    dodo = _load_dodo()
    import _buildgraph as bg

    asm_closure = set()
    for a in bg.ASSEMBLY_ORDER:
        asm_closure |= {
            os.path.basename(m) for m in bg.module_deps_of(bg.script_for(a))
        }

    def _orphan_helpers(script):
        helpers = {
            os.path.basename(m)
            for m in bg.module_deps_of(script)
            if os.path.basename(m).startswith("_")
        }
        return helpers - asm_closure  # gate-logic helpers riding no .SLDASM digest

    verify_orphans = _orphan_helpers(bg.SCRIPTS_DIR / "verify.py")
    assert "_assembly_postbuild.py" in verify_orphans, verify_orphans  # the known case
    for t in dodo.task_verify():
        deps = {os.path.basename(d) for d in t["file_dep"]}
        assert verify_orphans <= deps, (
            f"verify:{t['name']} missing gate-logic deps: {verify_orphans - deps}"
        )

    pf_orphans = _orphan_helpers(bg.SCRIPTS_DIR / "preflight_release.py")
    pf_deps = {os.path.basename(d) for d in dodo.task_preflight()["file_dep"]}
    assert pf_orphans <= pf_deps, (
        f"preflight missing gate-logic deps: {pf_orphans - pf_deps}"
    )


def test_artefact_digest_immune_to_byte_churn():
    """THE idempotency fix: a SolidWorks save rewrites a part's bytes (new mtime +
    size) without changing its geometry inputs. check_modified must report
    NOT-modified -- the stored recipe digest still matches -- so the dependent
    assembly is not refreshed for nothing. A stored BYTE md5 (the one-time migration
    off the old checker, or a genuine recipe change) still reports modified."""
    dodo = _load_dodo()
    stem = dodo.part_stems()[0]
    art = dodo._sldprt(stem)
    checker = dodo.ContentChecker()
    recipe = dodo.ContentChecker._digest(art)

    # Save churn: mtime + size differ, stored digest == recipe digest -> inert.
    churned = (10.0, 999_999, recipe)
    assert (
        checker.check_modified(art, _FakeStat(churned[0] + 1234), churned) is False
    ), "byte churn with an unchanged recipe must NOT mark the artefact modified"

    # A stored byte md5 (pre-migration / real input change) differs from the recipe
    # digest -> modified, so the one rebuild that re-stamps the ledger still happens.
    stale = (10.0, 12345, "0" * 32)
    assert checker.check_modified(art, _FakeStat(stale[0] + 1234), stale) is True


# --- Per-seat part order (cold-build divergence so two machines split the work).


def test_seat_part_order_is_a_permutation(monkeypatch):
    """_seat_part_order reorders but never drops/duplicates a part -- the spine must
    still cover exactly part_stems(), or a part would silently never build."""
    dodo = _load_dodo()
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-A")
    order = dodo._seat_part_order()
    assert sorted(order) == sorted(dodo.part_stems())
    assert len(order) == len(set(order))


def test_seat_part_order_deterministic_per_seed(monkeypatch):
    """Same seed -> identical order on every call. The COM seat lock (not the order)
    now guarantees correctness, so a diverging order can no longer deadlock; but a
    stable per-seat order keeps the fleet cache-split hint coherent across a seat's
    parent + ``-n`` worker processes."""
    dodo = _load_dodo()
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-A")
    first = dodo._seat_part_order()
    second = dodo._seat_part_order()
    assert first == second


def test_seat_part_order_diverges_across_seats(monkeypatch):
    """Different seats -> different order (the whole point: cold builders don't march
    in lock-step). With dozens of parts a fixed permutation makes a collision
    astronomically unlikely, so any two distinct seeds must reorder."""
    dodo = _load_dodo()
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-A")
    a = dodo._seat_part_order()
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-B")
    b = dodo._seat_part_order()
    assert a != b, "distinct seats must not build parts in the same order"


# --- COM seat lock (replaced the spine): serialize the single SW seat at runtime.


def test_com_seat_acquires_sets_env_and_releases(tmp_path, monkeypatch):
    """``_com_seat`` acquires the machine-global file lock, marks the seat held via
    HARMONIC_COM_SEAT (inherited by the COM subprocess -> _common's tripwire), and
    releases both on exit. Lock path is overridable so the test never touches the
    real %PROGRAMDATA% lock."""
    monkeypatch.setenv("HARMONIC_COM_LOCK", str(tmp_path / "seat.lock"))
    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    dodo = _load_dodo()
    assert dodo._COM_LOCK_PATH == tmp_path / "seat.lock"
    assert not dodo._COM_LOCK.is_locked
    with dodo._com_seat("part:x"):
        assert dodo._COM_LOCK.is_locked
        assert os.environ["HARMONIC_COM_SEAT"].startswith("part:x")
        assert dodo._read_seat_holder().startswith("part:x")
    assert not dodo._COM_LOCK.is_locked
    assert "HARMONIC_COM_SEAT" not in os.environ


def test_com_seat_wait_gets_its_own_top_level_span(tmp_path, monkeypatch):
    """A busy-seat poll is BOTH a log per poll and its own ``com.seat.wait <label>``
    span. That span is top-level and ends at acquisition, so the caller's ``task``
    span is its SIBLING, timing the work alone -- the wait can never inflate it."""
    monkeypatch.setenv("HARMONIC_COM_LOCK", str(tmp_path / "seat.lock"))
    dodo = _load_dodo()
    acquire = dodo._COM_LOCK.acquire
    attempts = 0

    def acquire_after_one_timeout(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise dodo.Timeout(str(dodo._COM_LOCK_PATH))
        return acquire(*args, **kwargs)

    spans: list[tuple[str, dict]] = []
    debug_messages: list[str] = []

    @contextlib.contextmanager
    def record_span(name, **attrs):
        entry = (name, dict(attrs))
        spans.append(entry)

        class _Span:
            def set_attribute(self, key, value):
                entry[1][key] = value

        yield _Span()
        assert dodo._COM_LOCK.is_locked, (
            "the wait span must close once the seat is held"
        )

    monkeypatch.setattr(dodo._COM_LOCK, "acquire", acquire_after_one_timeout)
    monkeypatch.setattr(dodo._telemetry, "span", record_span)
    monkeypatch.setattr(dodo._telemetry, "debug", debug_messages.append)

    with dodo._com_seat("part:x"):
        assert spans == [
            (
                "com.seat.wait part:x",
                {"label": "part:x", "polls": 1, "service": "build-infra"},
            )
        ], "the wait must be timed by its own build-infra span, before the seat is held"

    assert attempts == 2
    assert debug_messages == ["[com.seat] part:x waiting for the SolidWorks seat"]


class _FakeClock:
    """``time`` stand-in yielding scripted monotonic readings (rest passes through)."""

    def __init__(self, *ticks: float) -> None:
        self._ticks = list(ticks)

    def monotonic(self) -> float:
        return self._ticks.pop(0)

    def __getattr__(self, name):
        return getattr(time, name)


def test_com_seat_hands_back_its_wait_and_logs_total_elapsed(tmp_path, monkeypatch):
    """The wait is yielded so the sibling ``task`` span can carry it as
    ``seat_wait_s``, and release logs the seat's TOTAL elapsed time (wait + held) --
    which is where the retired ``com.seat`` span event went, the task span having
    already closed by then."""
    monkeypatch.setenv("HARMONIC_COM_LOCK", str(tmp_path / "seat.lock"))
    dodo = _load_dodo()
    # entered=100.0, acquired=145.0 (45 s blocked), released=150.5 (5.5 s held).
    monkeypatch.setattr(dodo, "time", _FakeClock(100.0, 145.0, 150.5))

    infos: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        dodo._telemetry,
        "info",
        lambda message, **fields: infos.append((message, fields)),
    )

    with dodo._com_seat("part:x") as waited:
        assert waited == 45.0
        assert not infos, "the total is only known at release"

    (message, fields) = infos[-1]
    assert message == (
        "[com.seat] part:x released after 50.5s total (waited 45.0s, held 5.5s)"
    )
    assert fields == {"wait_s": 45.0, "held_s": 5.5, "elapsed_s": 50.5}


def test_cached_part_miss_emits_four_sibling_phase_spans(tmp_path, monkeypatch):
    """A cached COM task is FOUR top-level spans, never nested: the cache probe (the
    Azure restore attempt), the seat wait, the task itself (starting once the seat is
    held), and the publish. Each phase is then timed for what it is -- crucially the
    ``task`` span cannot absorb the queueing or the network transfers."""
    dodo = _load_dodo()
    script = tmp_path / "build_pen_rod.py"
    script.write_text("", encoding="utf-8")
    outcomes = iter((False, False))  # probe MISS, re-probe under the seat MISS

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(
        dodo, "_part_cache_outputs", lambda _stem: [tmp_path / "pen-rod.SLDPRT"]
    )
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(dodo._cache, "store", lambda *_a: "stored")
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_exec_com", lambda *_a, **_kw: None)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(45.0))

    opened: list[str] = []
    depth = 0

    @contextlib.contextmanager
    def record_span(name, **_attrs):
        nonlocal depth
        opened.append(name)
        assert depth == 0, f"{name} must be top-level, not nested under a phase span"
        depth += 1

        class _Span:
            def set_attribute(self, key, value):
                pass

        try:
            yield _Span()
        finally:
            depth -= 1

    monkeypatch.setattr(dodo._telemetry, "span", record_span)

    dodo._cached_part_action("pen_rod", script)

    # The seat wait span is _com_seat's, so it is not in this list.
    assert opened == [
        "cache.probe part:pen_rod",
        "cache.reprobe part:pen_rod",
        "task part:pen_rod",
        "cache.store part:pen_rod",
    ]


def test_autostart_ensures_sw_as_a_top_level_sibling_before_the_task(
    tmp_path, monkeypatch
):
    """With autostart ON, the first COM build brings SolidWorks up via a TOP-LEVEL
    ``sw.ensure_ready`` span positioned AFTER the under-seat re-probe and BEFORE the
    ``task`` span -- never nested inside it, so the task span stays pure build-work
    timing (regression guard: an earlier cut called ensure_ready inside _exec_com,
    nesting it under the task span)."""
    dodo = _load_dodo()
    script = tmp_path / "build_pen_rod.py"
    script.write_text("", encoding="utf-8")
    outcomes = iter((False, False))  # probe MISS, re-probe MISS -> builds

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(
        dodo, "_part_cache_outputs", lambda _stem: [tmp_path / "pen-rod.SLDPRT"]
    )
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(dodo._cache, "store", lambda *_a: "stored")
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_exec_com", lambda *_a, **_kw: None)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(45.0))
    monkeypatch.setattr(dodo, "_SW_ENSURED", False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")

    opened: list[str] = []
    depth = 0

    @contextlib.contextmanager
    def record_span(name, **_attrs):
        nonlocal depth
        opened.append(name)
        assert depth == 0, f"{name} must be top-level, not nested under a phase span"
        depth += 1

        class _Span:
            def set_attribute(self, key, value):
                pass

        try:
            yield _Span()
        finally:
            depth -= 1

    monkeypatch.setattr(dodo._telemetry, "span", record_span)

    def fake_ensure():
        with dodo._telemetry.span("sw.ensure_ready"):
            pass

    monkeypatch.setattr(dodo._sw_lifecycle, "ensure_ready", fake_ensure)

    dodo._cached_part_action("pen_rod", script)

    assert opened == [
        "cache.probe part:pen_rod",
        "cache.reprobe part:pen_rod",
        "sw.ensure_ready",
        "task part:pen_rod",
        "cache.store part:pen_rod",
    ]


def test_sw_ensure_once_runs_once_and_respects_the_opt_out(monkeypatch):
    """``_sw_ensure_once`` calls ``ensure_ready`` at most once per worker (the
    ``_SW_ENSURED`` guard) and not at all under ``HARMONIC_SW_AUTOSTART=0``."""
    dodo = _load_dodo()
    calls: list[int] = []
    monkeypatch.setattr(dodo._sw_lifecycle, "ensure_ready", lambda: calls.append(1))

    monkeypatch.setattr(dodo, "_SW_ENSURED", False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    dodo._sw_ensure_once()
    dodo._sw_ensure_once()  # guard: second call is a no-op
    assert calls == [1]

    monkeypatch.setattr(dodo, "_SW_ENSURED", False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    dodo._sw_ensure_once()  # opt-out: never calls ensure_ready
    assert calls == [1]


def test_task_span_carries_its_pipeline_stage_resource():
    """The parent-side ``task <label>`` span is attributed to the SAME stage as the
    subprocess it spawns (``_stage_name`` -> OTEL_SERVICE_NAME), so a task and its
    own children share a resource instead of the task reading the umbrella name.
    Queueing/transfer keep the separate build-infra resource."""
    dodo = _load_dodo()
    assert dodo._stage_name("part:pen_rod") == "part-build"
    assert dodo._stage_name("assembly:pen") == "assembly-build"
    assert dodo._stage_name("drawing:pen_rod") == "drawing-export"
    assert dodo._stage_name("verify soundness") == "verify-soundness"
    assert dodo._stage_name("nothing recognisable") == "harmonic-analyzer"

    source = inspect.getsource(dodo)
    task_spans = list(
        re.finditer(
            r'with _telemetry\.span\(\s*f"task \{label\}"(?P<args>.*?)\)\s+as\b',
            source,
            flags=re.DOTALL,
        )
    )
    assert len(task_spans) == 4, "every task span must be accounted for"
    for match in task_spans:
        assert "service=_stage_name(label)" in match.group("args")


def test_tag_seat_wait_labels_the_task_span_only_when_a_seat_was_taken():
    """``check:*`` gates take no seat (``_run`` yields None from nullcontext), so the
    task span must not grow a meaningless ``seat_wait_s=0``."""
    dodo = _load_dodo()

    class _Span:
        def __init__(self):
            self.attrs = {}

        def set_attribute(self, key, value):
            self.attrs[key] = value

    com, gate = _Span(), _Span()
    dodo._tag_seat_wait(com, 45.004)
    dodo._tag_seat_wait(gate, None)
    assert com.attrs == {"seat_wait_s": 45.0}
    assert gate.attrs == {}


def test_com_seat_is_reentrant_within_a_process(tmp_path, monkeypatch):
    """filelock counts same-process acquisitions, so a nested ``_com_seat`` (defensive
    -- no COM action nests today) neither deadlocks nor releases the seat early: the
    lock stays held until the OUTERMOST exit."""
    monkeypatch.setenv("HARMONIC_COM_LOCK", str(tmp_path / "seat.lock"))
    dodo = _load_dodo()
    with dodo._com_seat("a"):
        with dodo._com_seat("b"):
            assert dodo._COM_LOCK.is_locked
        assert dodo._COM_LOCK.is_locked, "inner exit must not free the seat"
    assert not dodo._COM_LOCK.is_locked


def test_com_tasks_carry_no_inter_com_task_dep():
    """DAG accuracy: with the spine gone, part/assembly/verify/preflight tasks must
    carry NO ``task_dep`` on another COM task -- ordering comes from their real
    file_dep on built artefacts, serialization from the seat lock. (export/release
    DO carry real gate edges -- asserted separately below.)"""
    dodo = _load_dodo()
    for t in dodo.task_part():
        assert not t.get("task_dep"), f"part:{t['name']} has a stray task_dep"
    for t in dodo.task_assembly():
        assert not t.get("task_dep"), f"assembly:{t['name']} has a stray task_dep"
    for t in dodo.task_verify():
        assert not t.get("task_dep"), f"verify:{t['name']} has a stray task_dep"
    assert not dodo.task_preflight().get("task_dep"), "preflight has a stray task_dep"


def test_export_is_gated_on_the_sw_verify_suites():
    """export writes neutral formats + refreshes the comparison gallery into cad/out,
    so it must run only AFTER the SW verify gates pass -- a real edge that used to be
    implicit in the spine (fable review)."""
    dodo = _load_dodo()
    deps = set(dodo.task_export()["task_dep"])
    assert {"verify:soundness", "verify:kinematics"} <= deps, deps


def test_release_is_gated_on_every_gate_and_staged_drawing():
    """Release has real edges to every gate and drawing artifact it stages."""
    dodo = _load_dodo()
    deps = set(dodo.task_release()["task_dep"])
    expected = {
        "export",
        "preflight",
        "verify:soundness",
        "verify:kinematics",
        *(f"check:{c}" for c in dodo._CHECK_NAMES),
        *(f"drawing:{s}" for s in dodo._drawing_order()),
    }
    assert expected <= deps, expected - deps


def test_part_tasks_cover_every_stem_once(monkeypatch):
    """The per-seat yield order must still emit EXACTLY every part stem once -- a
    dropped/duplicated stem would silently never build (the old
    _assert_spine_complete coverage check, reframed for the yield order)."""
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-A")
    dodo = _load_dodo()
    names = [t["name"] for t in dodo.task_part()]
    assert sorted(names) == sorted(dodo.part_stems())
    assert len(names) == len(set(names))


def test_drawing_runtime_lock_and_source_dependency(monkeypatch):
    """Drawings use the runtime COM lock and depend directly on their source part,
    without false assembly/export ordering edges."""
    dodo = _load_dodo()
    monkeypatch.setenv("HARMONIC_BUILD_ORDER_SEED", "seat-A")
    drawing = "drawing:platen_guide"

    task = next(task for task in dodo.task_drawing() if task["name"] == "platen_guide")
    assert "task_dep" not in task
    cad_deps = [path for path in task["file_dep"] if path.lower().endswith(".sldprt")]
    assert cad_deps == [dodo._sldprt("platen_guide")]
    assert not any(path.lower().endswith(".sldasm") for path in task["file_dep"])
    assert dodo._part_execution_token("platen_guide") in task["file_dep"]
    action, args = task["actions"][0]
    assert action is dodo._cached_drawing_action
    assert args == ["platen_guide"]
    dep_names = {Path(path).name for path in task["file_dep"]}
    assert {
        "platen-guide.SLDPRT",
        "draw_platen_guide.py",
        "_drawing_common.py",
        "_drawing_registry.py",
        "_holes.py",
        "_common.py",
        ".solidworks-mcp-submodule.digest",
    } <= dep_names
    assert {Path(path).name for path in task["targets"]} == {
        "platen-guide.SLDDRW",
        "platen-guide.pdf",
        "platen-guide_drawing.png",
    }
    assert "harmonic-analyzer.drwdot" in {name.lower() for name in dep_names}

    build_deps = set(dodo.task_build()["task_dep"])
    bare_deps = set(dodo.task_build_bare()["task_dep"])
    assert drawing in build_deps
    assert drawing not in bare_deps


def test_assembly_artefact_digest_folds_in_refs():
    """An assembly's stable digest folds its own recipe together with each referenced
    artefact's digest, recursively -- so a leaf-part input change propagates up to
    every ancestor (correct invalidation) while pure save-churn of an unchanged part
    does not (idempotency)."""
    dodo = _load_dodo()
    asm = "frame"
    got = dodo.ContentChecker._digest(dodo._sldasm(asm))

    import hashlib

    h = hashlib.md5()
    h.update(dodo._digest_files(dodo._recipe_files(asm)).encode())
    for ref in dodo.references_of(asm):
        rp = dodo._sldasm(ref) if ref in dodo.ASSEMBLY_ORDER else dodo._sldprt(ref)
        h.update((dodo._stable_artefact_digest(rp) or "").encode())
    assert got == h.hexdigest()
    # The refs genuinely contribute -- it is not merely the own-recipe digest.
    assert got != dodo._digest_files(dodo._recipe_files(asm))


def test_unknown_artefact_falls_back_to_byte_md5(tmp_path):
    """A .SLDPRT that is not a declared part/assembly target (e.g. a channel
    stretch-spring variant) has no recipe in the graph, so the digest falls back to
    the stock byte md5 rather than crashing or fabricating one."""
    from doit.dependency import get_file_md5

    dodo = _load_dodo()
    orphan = tmp_path / "channel-spring-installed-stretch07.SLDPRT"
    orphan.write_bytes(b"\x00solidworks-bytes\x01")
    assert dodo._stable_artefact_digest(str(orphan)) is None
    assert dodo.ContentChecker._digest(str(orphan)) == get_file_md5(str(orphan))


def test_digest_files_is_location_independent(tmp_path):
    """P2 #1 (PR #103 review): the recipe digest must be IDENTICAL across checkout
    roots, because it now feeds the cross-machine remote-cache key via
    ``_stable_artefact_digest``. ``_digest_files`` tags each member by its
    REPO-RELATIVE path (``_rel_tag``), not its absolute path -- an absolute tag would
    shift every assembly's key per seat and silently kill cross-machine cache hits."""
    dodo = _load_dodo()

    def make(root: Path):
        sub = root / "cad" / "scripts"
        sub.mkdir(parents=True)
        (sub / "build_x_assembly.py").write_text("recipe v0\n")
        (sub / "x.yaml").write_text("station_pitch_mm: 10\n")
        return [str(sub / "build_x_assembly.py"), str(sub / "x.yaml")]

    files_a, files_b = make(tmp_path / "A"), make(tmp_path / "B")
    orig = dodo.REPO_ROOT
    try:
        setattr(dodo, "REPO_ROOT", tmp_path / "A")
        a = dodo._digest_files(files_a)
        tag = dodo._rel_tag(files_a[0])
        assert tag == "cad/scripts/build_x_assembly.py", tag
        assert ":" not in tag and not tag.startswith("/"), (
            f"tag not repo-relative: {tag}"
        )
        setattr(dodo, "REPO_ROOT", tmp_path / "B")
        b = dodo._digest_files(files_b)
    finally:
        setattr(dodo, "REPO_ROOT", orig)
    assert a == b, (
        "recipe digest must be identical across checkout roots (cross-machine cache key)"
    )


def _rel(paths, root):
    """Config-relative names of the paths under ``root`` (ignores .py recipe
    members like the assembly script / helpers)."""
    out = set()
    for p in paths:
        rp = Path(p).resolve()
        if root in rp.parents:
            # as_posix() so the "machine/foo.yaml" literals below match on Windows
            # too (str() would yield OS-native backslashes off-POSIX).
            out.add(rp.relative_to(root).as_posix())
    return out


def test_config_deps_are_fine_grained():
    """dodo honors the per-script config read-set at SUB-FILE granularity, with
    machine.yaml/parts.yaml split per-subsystem/per-part. Never dimensions.yaml,
    and always a subset of the whole-config set it replaced."""
    dodo = _load_dodo()
    scripts = dodo.SCRIPTS_DIR
    cfg = (REPO_ROOT / "cad" / "config").resolve()
    whole = set(dodo._CONFIG_YAMLS)

    # A gear part reads machine("gear_train", ...) -> machine/gear_train.yaml ONLY
    # (NOT machine/channels.yaml, where active_count lives) + its own registry row
    # + title_block.yaml (every part stamps the title-block tolerance properties
    # from _common.part_properties -> _config.title_block) + release.yaml for the
    # global CAD Revision.
    cone = dodo._config_deps(scripts / "build_cone_gear.py", "cone_gear", "part")
    assert _rel(cone, cfg) == {
        "machine/gear_train.yaml",
        "parts/cone-gear.yaml",
        "parts/_defaults.yaml",
        "title_block.yaml",
        "release.yaml",
    }, _rel(cone, cfg)
    assert set(cone) <= whole

    # Editing ONE part's registry row rebuilds only that part: a leaf screw depends
    # on its own row + shared defaults + title_block.yaml + release.yaml, nothing
    # else.
    screw = dodo._config_deps(
        scripts / "build_fillister_screw.py", "fillister_screw", "part"
    )
    assert _rel(screw, cfg) == {
        "parts/fillister-screw.yaml",
        "parts/_defaults.yaml",
        "title_block.yaml",
        "release.yaml",
    }

    # No part depends on dimensions.yaml.
    for stem in dodo.part_stems():
        deps = {
            Path(p).name
            for p in dodo._config_deps(scripts / f"build_{stem}.py", stem, "part")
        }
        assert "dimensions.yaml" not in deps, stem

    # A non-stamping assembly needs NO parts row (part-row edits propagate via the
    # rebuilt .SLDPRT -> REFRESH); a stamping one (channel) tracks the rows it
    # stamps. _recipe_files is the single source for the FULL/REFRESH digest AND the
    # file_dep, so narrowing it keeps that parity intact.
    frame_recipe = _rel(dodo._recipe_files("frame"), cfg)
    assert not any(t.startswith("parts/") for t in frame_recipe), frame_recipe
    assert "dimensions.yaml" not in frame_recipe
    # Assembly title stamping is a separate contract: every released assembly
    # drawing owns TOL_* properties and therefore tracks title_block.yaml, but
    # that must not imply ownership of part-registry rows or the part template.
    # tolerances.yaml (fit classes) stays out of frame.
    assert "tolerances.yaml" not in frame_recipe, frame_recipe
    assert "title_block.yaml" in frame_recipe, frame_recipe
    assert "release.yaml" in frame_recipe, frame_recipe
    channel_recipe = _rel(dodo._recipe_files("channel"), cfg)
    assert "parts/channel-spring-installed.yaml" in channel_recipe, channel_recipe
    assert "release.yaml" in channel_recipe, channel_recipe
    assert "title_block.yaml" in channel_recipe, channel_recipe
    # The part TEMPLATE narrows identically: channel GENERATES its stretch
    # springs in-script via NewPart (which instantiates the template), so the
    # PRTDOT is a direct recipe member -- a template edit must FULL-rebuild the
    # generated variants and shift channel's cache key. A non-generating
    # assembly (frame) gets the template only transitively (re-stamped parts ->
    # shifted artefact digests -> REFRESH), never as a direct member.
    channel_names = {Path(p).name.lower() for p in dodo._recipe_files("channel")}
    frame_names = {Path(p).name.lower() for p in dodo._recipe_files("frame")}
    assert "harmonic-analyzer.prtdot" in channel_names, channel_names
    assert "harmonic-analyzer.prtdot" not in frame_names, frame_names
    for stem in dodo.ASSEMBLY_ORDER:
        recipe = dodo._recipe_files(stem)
        rel_recipe = _rel(recipe, cfg)
        names = {Path(path).name.lower() for path in recipe}
        script = dodo.script_for(stem)
        dynamic_part_rows = dodo._expand_parts_token(stem, "assembly", script)
        assert "title_block.yaml" in rel_recipe, stem
        assert dodo._expand_title_block_token("assembly", script), stem
        if stem == "channel":
            assert dynamic_part_rows, stem
            assert "harmonic-analyzer.prtdot" in names, stem
            continue
        assert dynamic_part_rows == [], stem
        assert "harmonic-analyzer.prtdot" not in names, stem
    # ... and every normal part task carries it directly (NewPart instantiates it).
    a_stem = next(iter(dodo.part_stems()))
    part_names = {
        Path(p).name.lower()
        for p in dodo._part_file_deps(scripts / f"build_{a_stem}.py", a_stem)
    }
    assert "harmonic-analyzer.prtdot" in part_names, part_names


def test_config_deps_recipe_digest_skips_unread_yaml():
    """A change to a config file the assembly does NOT read leaves its recipe digest
    unchanged (no spurious ~500 s FULL re-insert), while a file it DOES read flips
    it. Proven structurally: the digest is taken over _recipe_files, which lists
    only the read files. active_count lives in machine/channels.yaml: drive_train
    reads it (station geometry), frame does not."""
    dodo = _load_dodo()
    cfg = (REPO_ROOT / "cad" / "config").resolve()
    drive = _rel(dodo._recipe_files("drive_train"), cfg)
    frame = _rel(dodo._recipe_files("frame"), cfg)
    assert "machine/channels.yaml" in drive, drive
    assert "machine/channels.yaml" not in frame, (
        "frame must not FULL on an active_count edit"
    )


def test_recipe_digest_ignores_yaml_comments(tmp_path):
    """Option A reaches the ASSEMBLY recipe digest too: _digest_files folds YAML
    members in by parsed content, so a comment/reflow edit to a recipe YAML leaves
    the digest unchanged (no spurious FULL rebuild), while a real value change --
    or any non-YAML recipe member edit -- still flips it."""
    dodo = _load_dodo()
    yaml_cfg = tmp_path / "channels.yaml"
    script = tmp_path / "build_x_assembly.py"
    yaml_cfg.write_text("station_pitch_mm: 10\nrows: 3\n")
    script.write_text("v0\n")
    files = [str(script), str(yaml_cfg)]
    base = dodo._digest_files(files)

    yaml_cfg.write_text("# placement note\nstation_pitch_mm: 10\nrows: 3\n  \n")
    assert dodo._digest_files(files) == base, (
        "yaml comment/whitespace in recipe must be inert"
    )

    yaml_cfg.write_text("station_pitch_mm: 11\nrows: 3\n")
    assert dodo._digest_files(files) != base, (
        "real placement-value change must FULL-rebuild"
    )

    yaml_cfg.write_text(
        "station_pitch_mm: 10\nrows: 3\n"
    )  # restore yaml -> back to base
    assert dodo._digest_files(files) == base
    script.write_text("v1\n")
    assert dodo._digest_files(files) != base, "assembly-script change must FULL-rebuild"


# --- Issue #144: the SolidworksMCP-python submodule is a runtime build input of every
# COM task, so its source content must fold into every part/assembly recipe + cache
# key (a submodule bump busts the key) -- while the SolidWorks-free check:* tasks,
# which never touch COM, must stay off it.
def _redirect_submodule(dodo, root: Path):
    """Point dodo's submodule source + ALL THREE synthetic sidecars (full / assembly /
    part-relevant) into a temp sandbox and reset the per-process memoization, so a test
    controls the tree content and never writes into the real cad/out."""
    src = root / "src" / "solidworks_mcp"
    src.mkdir(parents=True, exist_ok=True)
    dodo.SUBMODULE_SRC = src
    dodo._SUBMODULE_DIGEST_FILE = root / ".submodule.digest"
    dodo._SUBMODULE_ASSEMBLY_DIGEST_FILE = root / ".submodule-assembly.digest"
    dodo._SUBMODULE_PART_DIGEST_FILE = root / ".submodule-part.digest"
    _reset_submodule_memo(dodo)
    return src


def _reset_submodule_memo(dodo):
    """Force all three digests to re-read the (redirected) tree on the next call."""
    dodo._SUBMODULE_DIGEST = None
    dodo._SUBMODULE_ASSEMBLY_DIGEST = None
    dodo._SUBMODULE_PART_DIGEST = None
    dodo._SUBMODULE_DEP_PATH = None
    dodo._SUBMODULE_ASSEMBLY_DEP_PATH = None
    dodo._SUBMODULE_PART_DEP_PATH = None


def test_com_deps_include_submodule_and_checks_do_not(tmp_path):
    """The synthetic submodule dep is present in EVERY COM task's dep set and absent
    from EVERY check:* file_dep. THREE tiers: PARTS fold the part-relevant slice
    (``_submodule_part_dep``), ASSEMBLIES fold the tree minus drawing.py
    (``_submodule_assembly_dep``), DRAWINGS fold the whole tree (``_submodule_dep``);
    the three sidecars are distinct files."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapters.py").write_text("def mate(): return 1\n")
    full_dep = dodo._submodule_dep()
    asm_dep = dodo._submodule_assembly_dep()
    part_dep = dodo._submodule_part_dep()
    assert Path(full_dep) == (tmp_path / ".submodule.digest").resolve()
    assert Path(asm_dep) == (tmp_path / ".submodule-assembly.digest").resolve()
    assert Path(part_dep) == (tmp_path / ".submodule-part.digest").resolve()
    assert len({full_dep, asm_dep, part_dep}) == 3, (
        "part / assembly / drawing must track SEPARATE sidecars"
    )

    stem = dodo.part_stems()[0]
    part_deps = dodo._part_file_deps(dodo.SCRIPTS_DIR / f"build_{stem}.py", stem)
    assert part_dep in part_deps, "every part must depend on the part-slice digest"
    assert full_dep not in part_deps, "a part must NOT fold the whole-tree digest"
    assert asm_dep not in part_deps, "a part must NOT fold the assembly-slice digest"

    asm = dodo.ASSEMBLY_ORDER[0]
    assert asm_dep in dodo._recipe_files(asm), (
        "assembly recipe must fold the assembly slice"
    )
    assert asm_dep in dodo._assembly_file_deps(asm), "assembly file_dep must include it"
    assert full_dep not in dodo._assembly_file_deps(asm), (
        "an assembly must NOT fold the whole-tree (drawing-inclusive) digest"
    )

    drawing_stems = dodo._drawing_order()
    if drawing_stems:
        d_task = next(t for t in dodo.task_drawing() if t["name"] == drawing_stems[0])
        assert full_dep in d_task["file_dep"], (
            "a drawing task must fold the whole-tree digest"
        )

    # check:* tasks never touch COM -> no submodule sidecar may enter their dep set,
    # or an offline gate would spuriously re-run on a submodule bump.
    for task in dodo.task_check():
        deps = task["file_dep"]
        assert not ({full_dep, asm_dep, part_dep} & set(deps)), (
            f"check:{task['name']} must not depend on the submodule"
        )


def test_part_relevant_submodule_change_flips_part_cache_key(tmp_path):
    """A PART-RELEVANT submodule source change -- a committed pin bump OR a dirty
    local edit -- flips every part's COM cache key; a no-op recompute leaves it stable
    (idempotent). Exercised through the REAL cache_key path (_cache_key ->
    _artifact_cache), so it proves the fix reaches the cross-machine key."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapters.py").write_text("def mate(): return 1\n")

    stem = dodo.part_stems()[0]
    script = dodo.SCRIPTS_DIR / f"build_{stem}.py"

    def key():
        _reset_submodule_memo(dodo)  # re-read the tree on each call
        return dodo._cache_key(dodo._part_file_deps(script, stem), f"part:{stem}")

    k1 = key()
    assert key() == k1, "recompute with no change must be stable (idempotent)"

    (src / "adapters.py").write_text("def mate(): return 2\n")  # dirty edit
    k2 = key()
    assert k2 != k1, "a part-relevant submodule edit must bust the part cache key"

    (src / "planes.py").write_text("PLANE = 3\n")  # new source file
    k3 = key()
    assert k3 != k2, "an added part-relevant submodule source file must bust it too"


def test_assembly_only_submodule_change_spares_parts(tmp_path):
    """The #144-followup guarantee: editing an EXCLUDED (assembly/motion/MCP-server)
    submodule module flips the ASSEMBLY cache key but leaves the PART key untouched,
    so an assembly-only submodule bump no longer rebuilds the ~100 parts."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapters.py").write_text("def mate(): return 1\n")  # a part-relevant file
    excluded = src / "adapters" / "solidworks" / "assembly.py"
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("def add_mate(): return 1\n")

    stem = dodo.part_stems()[0]
    part_script = dodo.SCRIPTS_DIR / f"build_{stem}.py"
    asm = dodo.ASSEMBLY_ORDER[0]

    def part_key():
        _reset_submodule_memo(dodo)
        return dodo._cache_key(dodo._part_file_deps(part_script, stem), f"part:{stem}")

    def asm_key():
        _reset_submodule_memo(dodo)
        return dodo._cache_key(dodo._assembly_file_deps(asm), f"assembly:{asm}")

    p1, a1 = part_key(), asm_key()
    excluded.write_text("def add_mate(): return 2\n")  # assembly-only edit
    p2, a2 = part_key(), asm_key()

    assert p2 == p1, "an assembly-only submodule edit must NOT bust the part key"
    assert a2 != a1, "an assembly-only submodule edit MUST bust the assembly key"


def test_part_digest_excludes_assembly_level_modules():
    """Unit-level: the PART classifier drops the assembly/motion COM modules AND
    drawing.py from the part slice while keeping the shared helpers AND the MCP-server
    surface (codex #191: tools/server stay in the part digest), and the digest of the
    REAL tree genuinely differs from the whole-tree digest (so it isn't a no-op)."""
    dodo = _load_dodo()
    src = dodo.SUBMODULE_SRC
    excl = dodo._is_part_relevant_submodule_file
    assert excl(src / "adapters" / "solidworks" / "assembly.py") is False
    assert excl(src / "adapters" / "solidworks" / "motion.py") is False
    assert excl(src / "adapters" / "solidworks" / "drawing.py") is False
    # MCP-server surface stays IN the part digest (kept, not excluded):
    assert excl(src / "server.py") is True
    assert excl(src / "tools" / "modeling.py") is True
    assert excl(src / "adapters" / "base.py") is True
    assert excl(src / "adapters" / "com_variant.py") is True
    assert dodo._submodule_part_digest() != dodo._submodule_digest(), (
        "part slice must exclude real content, else the split is a no-op"
    )


def test_assembly_digest_excludes_only_drawing():
    """Unit-level: the ASSEMBLY classifier drops ONLY drawing.py (assemblies DO call
    the assembly/motion COM path, so those stay in), and the assembly-slice digest of
    the REAL tree differs from BOTH the whole-tree and part-slice digests."""
    dodo = _load_dodo()
    src = dodo.SUBMODULE_SRC
    excl = dodo._is_assembly_relevant_submodule_file
    assert excl(src / "adapters" / "solidworks" / "drawing.py") is False
    assert excl(src / "adapters" / "solidworks" / "assembly.py") is True
    assert excl(src / "adapters" / "solidworks" / "motion.py") is True
    assert excl(src / "adapters" / "base.py") is True
    assert dodo._submodule_assembly_digest() != dodo._submodule_digest(), (
        "assembly slice must exclude drawing.py, else the split is a no-op"
    )
    assert dodo._submodule_assembly_digest() != dodo._submodule_part_digest(), (
        "assembly slice keeps assembly/motion the part slice drops -> must differ"
    )


def test_drawing_only_submodule_change_spares_parts_and_assemblies(tmp_path):
    """A drawing.py edit flips ONLY the drawing-task (whole-tree) cache key, leaving both
    the PART and ASSEMBLY keys untouched -- so a drawing helper tweak rebuilds only the
    (few) drawing tasks, never the ~100 parts or ~8 assemblies."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapters.py").write_text(
        "def mate(): return 1\n"
    )  # a shared, in-all-tiers file
    drawing = src / "adapters" / "solidworks" / "drawing.py"
    drawing.parent.mkdir(parents=True, exist_ok=True)
    drawing.write_text("def new_view(): return 1\n")

    stem = dodo.part_stems()[0]
    part_script = dodo.SCRIPTS_DIR / f"build_{stem}.py"
    asm = dodo.ASSEMBLY_ORDER[0]

    def part_key():
        _reset_submodule_memo(dodo)
        return dodo._cache_key(dodo._part_file_deps(part_script, stem), f"part:{stem}")

    def asm_key():
        _reset_submodule_memo(dodo)
        return dodo._cache_key(dodo._assembly_file_deps(asm), f"assembly:{asm}")

    def full_digest():
        _reset_submodule_memo(dodo)
        return dodo._submodule_digest()

    p1, a1, d1 = part_key(), asm_key(), full_digest()
    drawing.write_text("def new_view(): return 2\n")  # drawing-only edit
    p2, a2, d2 = part_key(), asm_key(), full_digest()

    assert p2 == p1, "a drawing.py edit must NOT bust the part key"
    assert a2 == a1, "a drawing.py edit must NOT bust the assembly key"
    assert d2 != d1, "a drawing.py edit MUST bust the whole-tree (drawing) digest"


def test_kinematics_verify_depends_on_pen_driver_and_truth_model():
    """Post-#221 (park-driver machinery removed): build_pen_assembly no longer
    imports pen_driver/truth_model, so those modules ride no assembly's .SLDASM
    digest. The F5 chained-Fourier equation they define is now authored
    TRANSIENTLY by verify:kinematics instead, so the guard for "an edit to
    pen_driver/truth_model must invalidate the stamp" moved from the pen build
    recipe to dodo.task_verify's kinematics file_dep (see the comment block there).
    Pin that it's actually still wired up -- a dropped file_dep would leave a fresh
    verify-kinematics.ok stamp valid after a pen_driver/truth_model edit and SKIP
    the re-authored equation entirely. Ditto the config VALUES those modules read
    (machine/output.yaml + channels.yaml): post-#221 they ride no pen .SLDASM
    recipe either, so they must be direct file_deps too (codex #224). (_config.py
    itself needs no direct dep -- it stays on pen's build closure, so it rides
    the pen.SLDASM recipe digest.)"""
    dodo = _load_dodo()
    kinematics = next(t for t in dodo.task_verify() if t["name"] == "kinematics")
    deps = {Path(d).name for d in kinematics["file_dep"]}
    assert "pen_driver.py" in deps, deps
    assert "truth_model.py" in deps, deps
    cfg = (REPO_ROOT / "cad" / "config").resolve()
    cfg_rel = _rel(kinematics["file_dep"], cfg)
    assert "machine/output.yaml" in cfg_rel, cfg_rel
    assert "channels.yaml" in cfg_rel, cfg_rel


def test_submodule_digest_is_location_independent(tmp_path):
    """The submodule digest folds each file by its REPO-RELATIVE tag, so identical
    submodule content under different checkout roots hashes the same -- required for
    cross-machine cache hits (mirrors test_digest_files_is_location_independent)."""
    dodo = _load_dodo()

    def digest_under(root: Path) -> str:
        sub = root / "SolidworksMCP-python" / "src" / "solidworks_mcp"
        sub.mkdir(parents=True)
        (sub / "adapters.py").write_text("def mate(): return 1\n")
        orig_repo, orig_src = dodo.REPO_ROOT, dodo.SUBMODULE_SRC
        try:
            dodo.REPO_ROOT = root
            dodo.SUBMODULE_SRC = sub
            dodo._SUBMODULE_DIGEST = None
            return dodo._submodule_digest()
        finally:
            dodo.REPO_ROOT, dodo.SUBMODULE_SRC = orig_repo, orig_src
            dodo._SUBMODULE_DIGEST = None

    assert digest_under(tmp_path / "A") == digest_under(tmp_path / "B"), (
        "identical submodule content must hash equally across checkout roots"
    )


def test_recipe_gate_tracks_sources_imported_by_its_tests():
    """Editing code exercised by the drawing tests must stale the
    ``check:recipe`` stamp even when the test files themselves are unchanged."""
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    deps = {Path(path).name for path in recipe["file_dep"]}
    assert {
        "_holes.py",
        "build_platen_guide.py",
        "test_pen_summing_drawing_batch_contract.py",
    } <= deps
    pytest_command = recipe["actions"][0][1][0]
    assert {
        "test_drawing_marks.py",
        "test_cone_drawing_batch_contract.py",
        "test_fastener_catalog.py",
        "test_direct_dimension_tolerances.py",
        "test_drawing_specification_purity.py",
        "test_drawing_surface_finish_validation.py",
        "test_gtol_spec.py",
        "test_part_owned_geometric_tolerances.py",
        "test_probe_surface_finish_pmi_telemetry.py",
        "test_surface_finish.py",
        "test_surface_finish_ownership_a.py",
        "test_pose_manifest.py",
        "test_render_offline.py",
    } <= {Path(argument).name for argument in pytest_command}

    assert {
        "composite.py",
        "pose_manifest.py",
        "render_offline.py",
    } <= deps

    command = recipe["actions"][0][1][0]
    assert any(
        Path(argument).name == "test_pen_summing_drawing_batch_contract.py"
        for argument in command
    ), "the pen/summing metadata contract must execute under check:recipe"


def test_submodule_digest_is_checkout_eol_independent(tmp_path):
    """Issue #255 also covers the synthetic submodule sidecars: raw hashing here
    would move every COM key when core.autocrlf rematerialises vendored Python."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    module = src / "adapters.py"
    module.write_bytes(b"def mate():\n    return 1\n")
    lf = dodo._submodule_digest()
    module.write_bytes(b"def mate():\r\n    return 1\r\n")
    _reset_submodule_memo(dodo)
    assert dodo._submodule_digest() == lf


def test_retry_waits_out_a_cold_start_instead_of_spending_an_attempt(monkeypatch):
    """A recovery that ends 'starting' must not release the retry immediately.

    Measured on the seat: force_recover ran its full budget, ended
    final_state=starting, and the retry it released died inside the adapter's
    60 s COM-attach window -- a slot burned on a SolidWorks that could not have
    answered. The retry has to wait for the cold start first.
    """
    dodo = _load_dodo()
    calls = []

    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: True)
    monkeypatch.setattr(dodo, "_com_retry_backoff", lambda: (0,))
    monkeypatch.setattr(
        dodo,
        "_run_subprocess",
        lambda *_a, **_kw: (calls.append("run"), 86 if len(calls) == 1 else 0)[1],
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: (calls.append("recover"), "starting")[1],
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "wait_until_ready",
        lambda: (calls.append("wait"), "connected")[1],
    )

    dodo._exec_com(["x"], "drawing:thing")

    assert calls == ["run", "recover", "wait", "run"], calls


def test_retry_does_not_wait_when_recovery_came_back_connected(monkeypatch):
    """The wait is for a cold start, not a tax on every recovery."""
    dodo = _load_dodo()
    calls = []

    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: True)
    monkeypatch.setattr(dodo, "_com_retry_backoff", lambda: (0,))
    monkeypatch.setattr(
        dodo,
        "_run_subprocess",
        lambda *_a, **_kw: (calls.append("run"), 86 if len(calls) == 1 else 0)[1],
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: (calls.append("recover"), "connected")[1],
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "wait_until_ready",
        lambda: calls.append("wait"),
    )

    dodo._exec_com(["x"], "drawing:thing")

    assert calls == ["run", "recover", "run"], calls


def test_cold_start_connect_budget_exceeds_the_measured_failure(monkeypatch):
    """300 s was calibrated on a warm relaunch; a cold 3DEXPERIENCE start blew
    straight through it (sw.start 302 s, still 'starting')."""
    dodo = _load_dodo()
    monkeypatch.delenv("HARMONIC_SW_CONNECT_TIMEOUT", raising=False)
    assert dodo._sw_lifecycle._connect_timeout() >= 900.0


def test_post_recovery_grace_is_bounded_not_a_second_full_budget(monkeypatch):
    """A dead seat must not cost two full connect budgets per retry.

    force_recover already waits the whole budget; if wait_until_ready waited
    another, a genuinely dead SolidWorks would burn ~30 min per retry and ~90 min
    before the build failed -- worse than the wasted retry the wait prevents.
    """
    dodo = _load_dodo()
    lifecycle = dodo._sw_lifecycle
    waited = []
    monkeypatch.setattr(lifecycle, "_wait", lambda _r, t: waited.append(t))
    monkeypatch.setattr(lifecycle, "_state_value", lambda _r: "starting")
    monkeypatch.delenv("HARMONIC_SW_CONNECT_TIMEOUT", raising=False)

    lifecycle.wait_until_ready()

    budget = lifecycle._connect_timeout()
    assert waited and waited[0] < budget, (waited, budget)
    # Still has to clear the ~110 s the second force_recover needed, measured.
    assert waited[0] >= 200.0, waited


def test_a_state_probe_failure_cannot_abort_the_retry_path(monkeypatch):
    """force_recover returns "error" exactly when detect_state() raised.

    Re-probing with is_connected() would re-run that same failing call and let
    the exception escape _exec_com, aborting the task instead of retrying --
    the opposite of the best-effort contract. The decision reads the returned
    state instead, so a lifecycle that is itself broken still gets its retry.
    """
    dodo = _load_dodo()
    calls = []

    def boom():
        raise RuntimeError("detect_state exploded")

    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: True)
    monkeypatch.setattr(dodo, "_com_retry_backoff", lambda: (0,))
    monkeypatch.setattr(
        dodo,
        "_run_subprocess",
        lambda *_a, **_kw: (calls.append("run"), 86 if len(calls) == 1 else 0)[1],
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: (calls.append("recover"), "error")[1],
    )
    monkeypatch.setattr(dodo._sw_lifecycle, "is_connected", boom)
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "wait_until_ready",
        lambda: (calls.append("wait"), "error")[1],
    )

    dodo._exec_com(["x"], "drawing:thing")  # must not raise

    assert calls == ["run", "recover", "wait", "run"], calls


def test_abandoning_the_grace_is_recorded_on_the_span(monkeypatch):
    """Giving up on the wait is a decision inside sw.wait_ready.

    The retry that follows an abandoned grace will probably fail, so the trace
    has to show WHEN the wait was given up on -- a span that merely ran its
    full length looks identical to one that waited successfully.
    """
    dodo = _load_dodo()
    lifecycle = dodo._sw_lifecycle
    events = []

    def blow_up(_r, _t):
        raise RuntimeError("connector never answered")

    monkeypatch.setattr(lifecycle, "_wait", blow_up)
    monkeypatch.setattr(lifecycle, "_state_value", lambda _r: "starting")
    monkeypatch.setattr(
        lifecycle._telemetry,
        "event",
        lambda name, **kw: events.append((name, kw)),
    )

    assert lifecycle.wait_until_ready() == "starting"  # never raises

    assert [n for n, _ in events] == ["sw.grace_abandoned"], events
    assert events[0][1]["grace_s"] > 0
