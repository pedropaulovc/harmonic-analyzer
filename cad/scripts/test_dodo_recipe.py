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
