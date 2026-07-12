"""Regression test for the recipe-change detector in ``dodo.py`` (D2 fix).

``_RecipeTracker`` must decide FULL-vs-REFRESH from the recipe *content* digest
compared against the value saved on the last SUCCESSFUL run -- never from doit's
injected ``changed`` arg, which is corrupted after an intervening failed task.
"""
import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None, f"could not locate dodo.py under {REPO_ROOT}"
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


def test_content_checker_digest_ignores_yaml_noise(tmp_path):
    """Option A: ContentChecker digests the PARSED yaml, so comment / whitespace /
    numeric-reflow edits to a shared cad/config/*.yaml leave the digest unchanged
    (no spurious part rebuild); a real value change still flips it. Non-YAML deps
    fall through to the stock raw md5 untouched."""
    from doit.dependency import get_file_md5

    dodo = _load_dodo()
    digest = dodo.ContentChecker._digest

    cfg = tmp_path / "tolerances.yaml"
    cfg.write_text("rack_backlash_mm: 0.30\nseat_clearance_mm: 1.5\n")
    base = digest(str(cfg))

    cfg.write_text("# provenance: retargeted\nrack_backlash_mm: 0.300\nseat_clearance_mm: 1.5\n  \n")
    assert digest(str(cfg)) == base, "comment/whitespace/0.30->0.300 reflow must be inert"

    cfg.write_text("rack_backlash_mm: 0.31\nseat_clearance_mm: 1.5\n")
    assert digest(str(cfg)) != base, "a real value change must invalidate"

    nonyaml = tmp_path / "build_x.py"
    nonyaml.write_text("WIDTH = 3.0\n")
    assert digest(str(nonyaml)) == get_file_md5(str(nonyaml)), "non-yaml == stock md5"


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
    assert checker.check_modified(str(cfg), st, state) is False, "comment edit must be inert"

    # real value change with a distinct mtime -> modified
    cfg.write_text("k: 2\n")
    os.utime(str(cfg), (state[0] + 20, state[0] + 20))
    st = os.stat(str(cfg))
    assert checker.check_modified(str(cfg), st, state) is True, "value change must invalidate"


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
    recipe = dodo._digest_files(dodo._part_file_deps(dodo.SCRIPTS_DIR / f"build_{stem}.py", stem))
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
        asm_closure |= {os.path.basename(m) for m in bg.module_deps_of(bg.script_for(a))}

    def _orphan_helpers(script):
        helpers = {os.path.basename(m) for m in bg.module_deps_of(script)
                   if os.path.basename(m).startswith("_")}
        return helpers - asm_closure  # gate-logic helpers riding no .SLDASM digest

    verify_orphans = _orphan_helpers(bg.SCRIPTS_DIR / "verify.py")
    assert "_assembly_postbuild.py" in verify_orphans, verify_orphans  # the known case
    for t in dodo.task_verify():
        deps = {os.path.basename(d) for d in t["file_dep"]}
        assert verify_orphans <= deps, f"verify:{t['name']} missing gate-logic deps: {verify_orphans - deps}"

    pf_orphans = _orphan_helpers(bg.SCRIPTS_DIR / "preflight_release.py")
    pf_deps = {os.path.basename(d) for d in dodo.task_preflight()["file_dep"]}
    assert pf_orphans <= pf_deps, f"preflight missing gate-logic deps: {pf_orphans - pf_deps}"


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
    assert checker.check_modified(art, _FakeStat(churned[0] + 1234), churned) is False, \
        "byte churn with an unchanged recipe must NOT mark the artefact modified"

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


def test_release_is_gated_on_every_gate():
    """release must depend on export + preflight + BOTH verify suites + EVERY offline
    check -- explicit real edges now the spine no longer pulls them transitively, so a
    release can't publish past a stale/failing gate."""
    dodo = _load_dodo()
    deps = set(dodo.task_release()["task_dep"])
    expected = {"export", "preflight", "verify:soundness", "verify:kinematics",
                *(f"check:{c}" for c in dodo._CHECK_NAMES)}
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
    assert action is dodo._run
    assert args[-1] is True
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
    assert {"asme-b-book.drwdot", "asme-b-book.slddrt"} <= {
        name.lower() for name in dep_names
    }

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
        assert ":" not in tag and not tag.startswith("/"), f"tag not repo-relative: {tag}"
        setattr(dodo, "REPO_ROOT", tmp_path / "B")
        b = dodo._digest_files(files_b)
    finally:
        setattr(dodo, "REPO_ROOT", orig)
    assert a == b, "recipe digest must be identical across checkout roots (cross-machine cache key)"


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
    # (NOT machine/channels.yaml, where active_count lives) + its own registry row.
    cone = dodo._config_deps(scripts / "build_cone_gear.py", "cone_gear", "part")
    assert _rel(cone, cfg) == {
        "machine/gear_train.yaml", "parts/cone-gear.yaml", "parts/_defaults.yaml",
    }, _rel(cone, cfg)
    assert set(cone) <= whole

    # Editing ONE part's registry row rebuilds only that part: a leaf screw depends
    # on its own row + shared defaults, nothing else.
    screw = dodo._config_deps(scripts / "build_fillister_screw.py", "fillister_screw", "part")
    assert _rel(screw, cfg) == {"parts/fillister-screw.yaml", "parts/_defaults.yaml"}

    # No part depends on dimensions.yaml.
    for stem in dodo.part_stems():
        deps = {Path(p).name for p in dodo._config_deps(scripts / f"build_{stem}.py", stem, "part")}
        assert "dimensions.yaml" not in deps, stem

    # A non-stamping assembly needs NO parts row (part-row edits propagate via the
    # rebuilt .SLDPRT -> REFRESH); a stamping one (channel) tracks the rows it
    # stamps. _recipe_files is the single source for the FULL/REFRESH digest AND the
    # file_dep, so narrowing it keeps that parity intact.
    frame_recipe = _rel(dodo._recipe_files("frame"), cfg)
    assert not any(t.startswith("parts/") for t in frame_recipe), frame_recipe
    assert "dimensions.yaml" not in frame_recipe
    channel_recipe = _rel(dodo._recipe_files("channel"), cfg)
    assert "parts/channel-spring-installed.yaml" in channel_recipe, channel_recipe


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
    assert "machine/channels.yaml" not in frame, "frame must not FULL on an active_count edit"


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
    assert dodo._digest_files(files) == base, "yaml comment/whitespace in recipe must be inert"

    yaml_cfg.write_text("station_pitch_mm: 11\nrows: 3\n")
    assert dodo._digest_files(files) != base, "real placement-value change must FULL-rebuild"

    yaml_cfg.write_text("station_pitch_mm: 10\nrows: 3\n")  # restore yaml -> back to base
    assert dodo._digest_files(files) == base
    script.write_text("v1\n")
    assert dodo._digest_files(files) != base, "assembly-script change must FULL-rebuild"


# --- Issue #144: the SolidworksMCP-python submodule is a runtime build input of every
# COM task, so its source content must fold into every part/assembly recipe + cache
# key (a submodule bump busts the key) -- while the SolidWorks-free check:* tasks,
# which never touch COM, must stay off it.
def _redirect_submodule(dodo, root: Path):
    """Point dodo's submodule source + BOTH synthetic sidecars (full + part-relevant)
    into a temp sandbox and reset the per-process memoization, so a test controls the
    tree content and never writes into the real cad/out."""
    src = root / "src" / "solidworks_mcp"
    src.mkdir(parents=True, exist_ok=True)
    dodo.SUBMODULE_SRC = src
    dodo._SUBMODULE_DIGEST_FILE = root / ".submodule.digest"
    dodo._SUBMODULE_PART_DIGEST_FILE = root / ".submodule-part.digest"
    dodo._SUBMODULE_DIGEST = None
    dodo._SUBMODULE_PART_DIGEST = None
    dodo._SUBMODULE_DEP_PATH = None
    dodo._SUBMODULE_PART_DEP_PATH = None
    return src


def _reset_submodule_memo(dodo):
    """Force both digests to re-read the (redirected) tree on the next call."""
    dodo._SUBMODULE_DIGEST = None
    dodo._SUBMODULE_PART_DIGEST = None
    dodo._SUBMODULE_DEP_PATH = None
    dodo._SUBMODULE_PART_DEP_PATH = None


def test_com_deps_include_submodule_and_checks_do_not(tmp_path):
    """The synthetic submodule dep is present in EVERY COM task's dep set and absent
    from EVERY check:* file_dep. Two-tier since #144-followup: PARTS fold the
    part-relevant slice (``_submodule_part_dep``), ASSEMBLIES fold the whole tree
    (``_submodule_dep``); the two sidecars are distinct files."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapters.py").write_text("def mate(): return 1\n")
    full_dep = dodo._submodule_dep()
    part_dep = dodo._submodule_part_dep()
    assert Path(full_dep) == (tmp_path / ".submodule.digest").resolve()
    assert Path(part_dep) == (tmp_path / ".submodule-part.digest").resolve()
    assert full_dep != part_dep, "part + assembly must track SEPARATE sidecars"

    stem = dodo.part_stems()[0]
    part_deps = dodo._part_file_deps(dodo.SCRIPTS_DIR / f"build_{stem}.py", stem)
    assert part_dep in part_deps, "every part must depend on the part-slice digest"
    assert full_dep not in part_deps, "a part must NOT fold the whole-tree digest"

    asm = dodo.ASSEMBLY_ORDER[0]
    assert full_dep in dodo._recipe_files(asm), "assembly recipe must fold the submodule"
    assert full_dep in dodo._assembly_file_deps(asm), "assembly file_dep must include it"

    # check:* tasks never touch COM -> neither submodule sidecar may enter their dep
    # set, or an offline gate would spuriously re-run on a submodule bump.
    for task in dodo.task_check():
        assert full_dep not in task["file_dep"] and part_dep not in task["file_dep"], \
            f"check:{task['name']} must not depend on the submodule"


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
        _reset_submodule_memo(dodo)        # re-read the tree on each call
        return dodo._cache_key(dodo._part_file_deps(script, stem), f"part:{stem}")

    k1 = key()
    assert key() == k1, "recompute with no change must be stable (idempotent)"

    (src / "adapters.py").write_text("def mate(): return 2\n")   # dirty edit
    k2 = key()
    assert k2 != k1, "a part-relevant submodule edit must bust the part cache key"

    (src / "planes.py").write_text("PLANE = 3\n")               # new source file
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
    excluded.write_text("def add_mate(): return 2\n")            # assembly-only edit
    p2, a2 = part_key(), asm_key()

    assert p2 == p1, "an assembly-only submodule edit must NOT bust the part key"
    assert a2 != a1, "an assembly-only submodule edit MUST bust the assembly key"


def test_part_digest_excludes_assembly_level_modules():
    """Unit-level: the classifier drops ONLY the assembly/motion COM modules from the
    part slice while keeping the shared helpers AND the MCP-server surface (codex #191:
    tools/server stay in the part digest), and the two digests of the REAL tree
    genuinely differ (so the exclusion isn't a no-op)."""
    dodo = _load_dodo()
    src = dodo.SUBMODULE_SRC
    excl = dodo._is_part_relevant_submodule_file
    assert excl(src / "adapters" / "solidworks" / "assembly.py") is False
    assert excl(src / "adapters" / "solidworks" / "motion.py") is False
    # MCP-server surface stays IN the part digest (kept, not excluded):
    assert excl(src / "server.py") is True
    assert excl(src / "tools" / "modeling.py") is True
    assert excl(src / "adapters" / "base.py") is True
    assert excl(src / "adapters" / "com_variant.py") is True
    assert dodo._submodule_part_digest() != dodo._submodule_digest(), \
        "part slice must exclude real content, else the split is a no-op"


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

    assert digest_under(tmp_path / "A") == digest_under(tmp_path / "B"), \
        "identical submodule content must hash equally across checkout roots"


def test_recipe_gate_tracks_sources_imported_by_its_tests():
    """Editing code exercised by the drawing tests must stale the
    ``check:recipe`` stamp even when the test files themselves are unchanged."""
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    deps = {Path(path).name for path in recipe["file_dep"]}
    assert {
        "_holes.py",
        "build_platen_guide.py",
    } <= deps
