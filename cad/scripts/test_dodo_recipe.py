"""Regression test for the recipe-change detector in ``dodo.py`` (D2 fix).

``_RecipeTracker`` must decide FULL-vs-REFRESH from the recipe *content* digest
compared against the value saved on the last SUCCESSFUL run -- never from doit's
injected ``changed`` arg, which is corrupted after an intervening failed task.
"""

import ast
import contextlib
from functools import cache
import importlib.util
import inspect
import os
import re
import time
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def local_executor(monkeypatch):
    """Pin every recipe test to the LOCAL executor.

    These tests drive ``dodo``'s cached-action internals directly and stub the local
    path (``_exec_com``, ``_com_seat``, ``_cache``). ``HARMONIC_EXECUTOR`` is process
    environment, so a farm-mode parent (``build.py --executor farm`` runs the
    ``check:recipe`` pytest as a subprocess) leaked ``farm`` in here and sent the
    stubbed leaves to the REAL farm: the fake ``"k" * 64`` cache key came back as
    ``invalid_request: cache key must be a lowercase 64-hex digest`` and three tests
    failed only because of how the suite was invoked. The suite's verdict must not
    depend on the caller's executor.
    """
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")


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
    helper = tmp_path / "_session.py"
    recipe.write_text("recipe v0\n")
    helper.write_text("helper v0\n")
    files = [str(recipe), str(helper)]

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
    """Editing a shared helper (not just the assembly script) must trigger FULL."""
    dodo = _load_dodo()
    recipe = tmp_path / "build_x_assembly.py"
    helper = tmp_path / "_session.py"
    hook = tmp_path / "hook.py"
    for f in (recipe, helper, hook):
        f.write_text("v0\n")
    files = [str(recipe), str(helper), str(hook)]

    tracker = dodo._RecipeTracker("x", files)
    task = _FakeTask()
    tracker(task, {})
    saved = task.saved()

    for member in (recipe, helper, hook):
        member.write_text("v1\n")
        t2 = _FakeTask()
        up = dodo._RecipeTracker("x", files)(t2, saved)
        assert up is False, f"editing {member.name} must invalidate the recipe"
        member.write_text("v0\n")  # restore for next iteration


def test_drawing_depends_on_actual_part_execution():
    dodo = _load_dodo()
    token = dodo._part_execution_token("pd_platen_guide")
    part = next(task for task in dodo.task_part() if task["name"] == "pd_platen_guide")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "pd_platen_guide"
    )
    assert token in part["targets"]
    assert token in drawing["file_dep"]


def test_assembly_drawing_depends_on_actual_assembly_execution():
    dodo = _load_dodo()
    token = dodo._assembly_execution_token("pn_pen")
    assembly = next(task for task in dodo.task_assembly() if task["name"] == "pn_pen")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "pn_pen_assembly"
    )
    assert token in assembly["targets"]
    assert token in drawing["file_dep"]


def test_release_revision_source_invalidates_native_and_drawing_tasks():
    dodo = _load_dodo()
    revision_source = str(dodo.RELEASE_VERSION_FILE)

    part = next(task for task in dodo.task_part() if task["name"] == "pd_platen_guide")
    assembly = next(task for task in dodo.task_assembly() if task["name"] == "pn_pen")
    drawing = next(
        task for task in dodo.task_drawing() if task["name"] == "pd_platen_guide"
    )

    assert revision_source in part["file_dep"]
    assert revision_source in assembly["file_dep"]
    assert revision_source in drawing["file_dep"]


def test_drawing_tasks_depend_on_all_selected_layout_templates():
    dodo = _load_dodo()
    tasks = {task["name"]: task for task in dodo.task_drawing()}

    assert tasks.keys() == dodo.DRAWINGS_BY_NAME.keys()
    for stem, spec in dodo.DRAWINGS_BY_NAME.items():
        layouts = dict.fromkeys((spec.layout, *spec.additional_layouts))
        selected = {
            str(dodo.DRAWING_TEMPLATES[layout].path.resolve()) for layout in layouts
        }
        assert {str(path.resolve()) for path in spec.assets} == selected, stem
        template_deps = {
            str(Path(path).resolve())
            for path in tasks[stem]["file_dep"]
            if Path(path).suffix.casefold() == ".drwdot"
        }
        assert template_deps == selected, stem


@pytest.mark.parametrize(
    ("stem", "rows"),
    [
        # cone_gear_shaft and the drive-train sheet read the cone gear's
        # grouped spec. (R1 hard-codes the crank numbers crank_pinion_spec
        # prints, test_crank_pinion_drawing pins them to the registry, so the
        # pin sheet no longer reads a foreign row.)
        ("dt_cone_gear_shaft", ("dt-cone-gear",)),
        ("dt_drive_train_assembly", ("dt-cone-gear",)),
    ],
)
def test_drawing_depends_on_the_config_rows_its_closure_reads(stem, rows):
    """Codex #936 T_oyK: a sheet that prints another part's registry row must
    go stale, and miss the cache, when only that row changes."""
    dodo = _load_dodo()
    spec = dodo.DRAWINGS_BY_NAME[stem]
    deps = set(dodo._drawing_file_deps(stem))
    for row in rows:
        assert str((dodo.CONFIG_DIR / "parts" / f"{row}.yaml").resolve()) in deps
    assert set(dodo._config_deps(spec.script, spec.part, "drawing")) <= deps
    drawing = next(task for task in dodo.task_drawing() if task["name"] == stem)
    assert deps <= set(drawing["file_dep"])


def test_every_drawing_carries_its_config_read_set():
    dodo = _load_dodo()
    for stem, spec in dodo.DRAWINGS_BY_NAME.items():
        config = set(dodo._config_deps(spec.script, spec.part, "drawing"))
        assert config <= set(dodo._drawing_file_deps(stem)), stem


def test_drawing_reading_a_foreign_part_row_carries_that_row(tmp_path):
    """The Codex example itself: a draw script that prints pivot-bracket's
    number from the registry depends on parts/ch-pivot-bracket.yaml."""
    dodo = _load_dodo()
    script = tmp_path / "draw_foreign_row_probe.py"
    script.write_text(
        'import _config\nPIVOT_NUMBER = _config.parts("ch-pivot-bracket")["number"]\n',
        encoding="utf-8",
    )
    deps = dodo._config_deps(script, "fr_rocker_arm_support", "drawing")
    parts = dodo.CONFIG_DIR / "parts"
    assert str((parts / "ch-pivot-bracket.yaml").resolve()) in deps
    # A literal read names its row; it does not also pull the sheet's own row.
    assert str((parts / "fr-rocker-arm-support.yaml").resolve()) not in deps


# Every source that reads the registry through a NON-literal part name
# (config_files_of's "parts/*" token) inside a drawing closure, and why that
# name is the drawing's OWN part.  dodo._expand_parts_token narrows "parts/*"
# to the own row for a drawing on exactly this premise; a new dynamic reader
# must be reviewed here, or the narrowing would hide a foreign row edit.
_DRAWING_OWN_ROW_READERS = {
    # part_properties(name): the name arrives from a caller, pinned below to
    # build_<own part>.py's PART_NAME.
    "_part_properties.py",
    # save_part_and_images(adapter, name) forwards its caller's part name to
    # part_properties(name), which the dynamic-row scan sees here.
    "_part_save.py",
    # save_simplified_part(adapter, part_name) forwards the same caller-owned
    # name to save_part_and_images; its entrypoint is pinned below as well.
    "_simplified_part.py",
    # apply_drawing_properties(adapter, name): same callers, same pin.
    "_drawing_marks.py",
    # _config.parts(stock.part_name) after the source identity check
    # (spec.source.stem == stock.part_name).
    "_purchased_fastener_drawing.py",
    # The configured sheet reads spec.source.stem, derived from spec.part;
    # output artifact labels cannot select a foreign registry row.
    "_purchased_variant_drawing.py",
    # Configured purchased members read/export only the part_name supplied by
    # their producer. The caller argument checks below cover these entrypoints.
    "_part_configuration_exports.py",
    "_purchased_part_variants.py",
    # Supplier stock diagrams bind source = spec.source before their registry
    # read; the binding and callers' own registered SPEC are checked below.
    "_supplier_spring_drawing.py",
}
# Registry-reading helper -> (argument index, keyword spelling).
_OWN_ROW_HELPERS = {
    "part_properties": (0, "part_name"),
    "save_part_and_images": (1, "part_name"),
    "save_simplified_part": (1, "part_name"),
    "apply_drawing_properties": (1, "part_name"),
    "member_configurations": (0, "stem"),
    "require_member_configurations": (0, "part_name"),
    "create_member_configurations": (1, "part_name"),
    "apply_member_properties": (1, "part_name"),
    "assert_member_properties": (1, "part_name"),
    "save_member_part": (1, "part_name"),
    "export_member_configurations": (1, "part_name"),
    "configuration_export_paths": (0, "stem"),
    "configuration_producer_paths": (0, "stem"),
    "part_configuration_outputs": (0, "stem"),
    "validate_member_exports": (0, "stem"),
    "build_supplier_spring_drawing": (1, "spec"),
}


def _module_part_name(tree: ast.Module) -> str | None:
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "PART_NAME" for t in node.targets
            )
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    return None


def _helper_name_arguments(tree: ast.AST) -> tuple[tuple[str, str], ...]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name not in _OWN_ROW_HELPERS:
            continue
        index, keyword = _OWN_ROW_HELPERS[name]
        args = [*node.args[index : index + 1]]
        args += [kw.value for kw in node.keywords if kw.arg == keyword]
        assert len(args) == 1, f"{name}: missing or ambiguous part-name argument"
        found.extend((name, ast.unparse(arg)) for arg in args)
    return tuple(found)


def _registered_drawing_spec(tree: ast.Module) -> str | None:
    """Return the registered drawing only when SPEC has one unshadowed binding."""
    imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "_drawing_registry"
        and any(alias.name == "DRAWINGS_BY_NAME" and alias.asname is None for alias in node.names)
        for node in tree.body
    )
    bindings = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SPEC" for target in node.targets)
    ]
    if not imported or len(bindings) != 1:
        return None
    # Only the one module assignment may bind SPEC. AST name stores cover
    # assignments, loops, with-targets and comprehensions; parameters, imports,
    # definitions, exception handlers and pattern captures bind names separately.
    if sum(
        isinstance(node, ast.Name) and node.id == "SPEC"
        and isinstance(node.ctx, (ast.Store, ast.Del))
        for node in ast.walk(tree)
    ) != 1:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.arg == "SPEC":
            return None
        if isinstance(node, ast.alias) and (
            (node.asname or node.name.split(".")[0]) == "SPEC" or node.name == "*"
        ):
            return None
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
             ast.ExceptHandler, ast.MatchAs, ast.MatchStar),
        ) and node.name == "SPEC":
            return None
        if isinstance(node, ast.MatchMapping) and node.rest == "SPEC":
            return None
    value = bindings[0]
    if not (
        isinstance(value, ast.Subscript)
        and isinstance(value.value, ast.Name)
        and value.value.id == "DRAWINGS_BY_NAME"
        and isinstance(value.slice, ast.Constant)
        and isinstance(value.slice.value, str)
    ):
        return None
    return value.slice.value


def _registered_source_row(tree: ast.Module) -> str | None:
    """Only the declared drawing's native source can select its dynamic row."""
    registered = _registered_drawing_spec(tree)
    if registered is None or any(
        isinstance(node, ast.Import)
        and any(alias.name == "_config" and alias.asname for alias in node.names)
        for node in ast.walk(tree)
    ):
        return None
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_config"
        and node.func.attr == "parts"
    ]
    if not calls or any(
        len(call.args) != 1
        or call.keywords
        or ast.unparse(call.args[0]) != "SPEC.source.stem"
        for call in calls
    ):
        return None
    return registered


@pytest.mark.parametrize(
    "name,index",
    (
        ("require_member_configurations", 0),
        ("create_member_configurations", 1),
        ("save_member_part", 1),
        ("apply_member_properties", 1),
        ("assert_member_properties", 1),
        ("save_simplified_part", 1),
        ("member_configurations", 0),
        ("export_member_configurations", 1),
        ("configuration_export_paths", 0),
        ("configuration_producer_paths", 0),
        ("part_configuration_outputs", 0),
        ("validate_member_exports", 0),
    ),
)
@pytest.mark.parametrize("selected", ("PART_NAME", "foreign_part", None))
@pytest.mark.parametrize("keyword_call", (False, True))
def test_configured_member_row_calls_reject_foreign_or_missing_part_inputs(
    monkeypatch, tmp_path, name, index, selected, keyword_call
):
    import _buildgraph as bg

    script = tmp_path / "build_sh_vn_chain_link.py"
    arguments = ["adapter"] * index
    if selected is not None:
        _index, keyword = _OWN_ROW_HELPERS[name]
        arguments.append(f"{keyword}={selected}" if keyword_call else selected)
    script.write_text(
        'import _config\nPART_NAME = "sh-vn-chain-link"\n'
        '_config.parts(PART_NAME)\n'
        f"{name}({', '.join(arguments)})\n",
        encoding="utf-8",
    )
    spec = SimpleNamespace(script=script, part="sh_vn_chain_link")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: ())
    if selected == "PART_NAME":
        test_drawing_closures_read_no_foreign_dynamic_part_row()
    else:
        with pytest.raises(AssertionError):
            test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize("registered", ("fixture", "foreign", None))
@pytest.mark.parametrize("selector", ("SPEC.source.stem", "foreign_source.stem"))
@pytest.mark.parametrize("aliased_read", (False, True))
@pytest.mark.parametrize(
    "filename",
    ("draw_fixture.py", "draw_sh_vn_chain_link.py",
     "draw_sh_vn_music_wire.py", "draw_sh_vn_thumb_screw.py"),
)
def test_drawing_source_rows_require_the_selected_registered_native(
    monkeypatch, tmp_path, registered, selector, aliased_read, filename
):
    import _buildgraph as bg

    script = tmp_path / filename
    binding = "" if registered is None else f"SPEC = DRAWINGS_BY_NAME[{registered!r}]\n"
    extra_read = (
        "import _config as cfg\ncfg.parts(foreign_source.stem)\n"
        if aliased_read
        else ""
    )
    script.write_text(
        "from _drawing_registry import DRAWINGS_BY_NAME\nimport _config\n"
        + binding
        + f"_config.parts({selector})\n" + extra_read,
        encoding="utf-8",
    )
    spec = SimpleNamespace(script=script, part="sh_vn_thumb_screw")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: ())
    if registered == "fixture" and selector == "SPEC.source.stem" and not aliased_read:
        test_drawing_closures_read_no_foreign_dynamic_part_row()
    else:
        with pytest.raises(AssertionError):
            test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize(
    "filename", ("draw_sh_vn_music_wire.py", "draw_sh_vn_thumb_screw.py"),
)
@pytest.mark.parametrize("reader", ("direct", "supplier", "supplier_keyword"))
@pytest.mark.parametrize(
    "shadow",
    (
        "SPEC = foreign_spec\n",
        "def read(SPEC):\n    return {read}\n",
        "def read(*, SPEC):\n    return {read}\n",
        "read = lambda SPEC: {read}\n",
        "def read():\n    SPEC = foreign_spec\n    return {read}\n",
        "for SPEC in foreign_specs:\n    pass\n",
        "with foreign_context() as SPEC:\n    pass\n",
        "rows = [SPEC for SPEC in foreign_specs]\n",
        "try:\n    pass\nexcept Exception as SPEC:\n    pass\n",
        "match foreign_spec:\n    case SPEC:\n        pass\n",
        "match foreign_spec:\n    case [*SPEC]:\n        pass\n",
        "match foreign_spec:\n    case {{**SPEC}}:\n        pass\n",
        "import foreign_spec as SPEC\n",
        "from foreign_module import SPEC\n",
        "def SPEC():\n    pass\n",
        "class SPEC:\n    pass\n",
        "del SPEC\n",
    ),
)
def test_registered_drawing_spec_rejects_shadowed_spec(
    monkeypatch, tmp_path, filename, shadow, reader
):
    import _buildgraph as bg

    script = tmp_path / filename
    read = (
        "_config.parts(SPEC.source.stem)" if reader == "direct"
        else "build_supplier_spring_drawing(adapter, spec=SPEC)"
        if reader == "supplier_keyword"
        else "build_supplier_spring_drawing(adapter, SPEC)"
    )
    shadow = shadow.format(read=read)
    valid = (
        "from _drawing_registry import DRAWINGS_BY_NAME\nimport _config\n"
        "SPEC = DRAWINGS_BY_NAME['fixture']\n"
        f"def read():\n    return {read}\n"
    )
    spec = SimpleNamespace(script=script, part=filename.removeprefix("draw_").removesuffix(".py"))
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: ())
    script.write_text(valid, encoding="utf-8")
    assert _registered_drawing_spec(ast.parse(valid)) == "fixture"
    if reader == "direct":
        assert _registered_source_row(ast.parse(valid)) == "fixture"
    test_drawing_closures_read_no_foreign_dynamic_part_row()
    script.write_text(valid + shadow, encoding="utf-8")
    assert _registered_drawing_spec(ast.parse(valid + shadow)) is None
    if reader == "direct":
        assert _registered_source_row(ast.parse(valid + shadow)) is None
    with pytest.raises(AssertionError):
        test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize(
    "filename",
    ("draw_sh_vn_chain_link.py", "draw_sh_vn_music_wire.py", "draw_sh_vn_thumb_screw.py"),
)
@pytest.mark.parametrize(
    "call",
    ("apply_drawing_properties(adapter, foreign_part)",
     "configuration_export_paths(stem=foreign_part)"),
)
def test_registered_drawing_readers_reject_direct_part_helper_calls(
    monkeypatch, tmp_path, filename, call
):
    import _buildgraph as bg

    script = tmp_path / filename
    valid = (
        "from _drawing_registry import DRAWINGS_BY_NAME\nimport _config\n"
        "SPEC = DRAWINGS_BY_NAME['fixture']\n"
        "_config.parts(SPEC.source.stem)\n"
    )
    spec = SimpleNamespace(script=script, part="sh_vn_chain_link")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: ())
    script.write_text(valid, encoding="utf-8")
    test_drawing_closures_read_no_foreign_dynamic_part_row()
    script.write_text(valid + call + "\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize("registered", ("fixture", "foreign"))
@pytest.mark.parametrize("selected", ("SPEC", "foreign_spec"))
@pytest.mark.parametrize("keyword_call", (False, True))
def test_supplier_drawing_call_requires_own_registered_spec(
    monkeypatch, tmp_path, registered, selected, keyword_call
):
    import _buildgraph as bg

    script = tmp_path / "draw_fixture.py"
    argument = f"spec={selected}" if keyword_call else selected
    candidate = (
        "from _drawing_registry import DRAWINGS_BY_NAME\n"
        f"SPEC = DRAWINGS_BY_NAME[{registered!r}]\n"
        f"build_supplier_spring_drawing(adapter, {argument})\n"
    )
    spec = SimpleNamespace(script=script, part="sh_vn_chain_link")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: ())
    valid_argument = "spec=SPEC" if keyword_call else "SPEC"
    script.write_text(
        "from _drawing_registry import DRAWINGS_BY_NAME\n"
        "SPEC = DRAWINGS_BY_NAME['fixture']\n"
        f"build_supplier_spring_drawing(adapter, {valid_argument})\n",
        encoding="utf-8",
    )
    test_drawing_closures_read_no_foreign_dynamic_part_row()
    script.write_text(candidate, encoding="utf-8")
    if registered == "fixture" and selected == "SPEC":
        test_drawing_closures_read_no_foreign_dynamic_part_row()
    else:
        with pytest.raises(AssertionError):
            test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize("selected", ("part_name", "foreign_part"))
@pytest.mark.parametrize("extra_call", (False, True))
def test_simplified_part_wrapper_requires_exact_passthrough(
    monkeypatch, tmp_path, selected, extra_call
):
    import _buildgraph as bg

    script = tmp_path / "draw_fixture.py"
    script.write_text("", encoding="utf-8")
    wrapper = tmp_path / "_simplified_part.py"
    candidate = (
        "async def save_simplified_part(adapter, part_name):\n"
        f"    await save_part_and_images(adapter, {selected})\n"
        + ("save_part_and_images(adapter, foreign_part)\n" if extra_call else "")
    )
    spec = SimpleNamespace(script=script, part="sh_vn_chain_link")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: (wrapper,))
    wrapper.write_text(
        "async def save_simplified_part(adapter, part_name):\n"
        "    await save_part_and_images(adapter, part_name)\n",
        encoding="utf-8",
    )
    test_drawing_closures_read_no_foreign_dynamic_part_row()
    wrapper.write_text(candidate, encoding="utf-8")
    if selected == "part_name" and not extra_call:
        test_drawing_closures_read_no_foreign_dynamic_part_row()
    else:
        with pytest.raises(AssertionError):
            test_drawing_closures_read_no_foreign_dynamic_part_row()


@pytest.mark.parametrize("binding", ("spec.source", "foreign_spec.source"))
@pytest.mark.parametrize("rebind", (False, True))
def test_supplier_row_reader_requires_unmodified_source_binding(
    monkeypatch, tmp_path, binding, rebind
):
    import _buildgraph as bg

    script = tmp_path / "draw_fixture.py"
    script.write_text("", encoding="utf-8")
    supplier = tmp_path / "_supplier_spring_drawing.py"
    candidate = (
        "import _config\n"
        "async def build_supplier_spring_drawing(adapter, spec):\n"
        f"    source = {binding}\n"
        + ("    source = foreign_spec.source\n" if rebind else "")
        + "    return _config.parts(source.stem)\n"
    )
    spec = SimpleNamespace(script=script, part="sh_vn_chain_link")
    monkeypatch.setitem(
        globals(), "_load_dodo",
        lambda: SimpleNamespace(DRAWINGS_BY_NAME={"fixture": spec}),
    )
    monkeypatch.setattr(bg, "module_deps_of", lambda _script: (supplier,))
    supplier.write_text(
        "import _config\n"
        "async def build_supplier_spring_drawing(adapter, spec):\n"
        "    source = spec.source\n"
        "    return _config.parts(source.stem)\n",
        encoding="utf-8",
    )
    test_drawing_closures_read_no_foreign_dynamic_part_row()
    supplier.write_text(candidate, encoding="utf-8")
    if binding == "spec.source" and not rebind:
        test_drawing_closures_read_no_foreign_dynamic_part_row()
    else:
        with pytest.raises(AssertionError):
            test_drawing_closures_read_no_foreign_dynamic_part_row()


def test_drawing_closures_read_no_foreign_dynamic_part_row():
    import _buildgraph as bg

    dodo = _load_dodo()
    drawing_names = {
        spec.script.resolve(): stem for stem, spec in dodo.DRAWINGS_BY_NAME.items()
    }

    @cache
    def source_facts(source: Path):
        # A shared helper can occur in every drawing closure. Source is unchanged
        # throughout this scan; cache immutable facts, not a production AST oracle.
        try:
            tokens = bg._config_tokens_in_source(source)
        except bg._UnknownConfigUse:
            return None  # the whole-config fallback narrows nothing
        tree = ast.parse(source.read_text(encoding="utf-8"))
        calls = _helper_name_arguments(tree)
        supplier_calls = tuple(
            call for call in calls if call[0] == "build_supplier_spring_drawing"
        )
        if supplier_calls:
            # A SPEC-shaped expression is safe only if it selects this script's
            # own registered drawing, not another drawing's native source.
            assert source in drawing_names, (source.name, supplier_calls)
            assert _registered_drawing_spec(tree) == drawing_names[source], source.name
            assert {arg for _name, arg in supplier_calls} <= {"SPEC"}, supplier_calls
        if source.name == "_supplier_spring_drawing.py":
            reads = [
                node for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "parts"
                and bg._literal_first_arg(node) is None
            ]
            arguments = {
                ast.unparse(node.args[0]) if node.args else "<whole registry>"
                for node in reads
            }
            assert arguments == {"source.stem"}, (source.name, arguments)
        if source.name == "_supplier_spring_drawing.py":
            # source is only an alias for the caller's spec, never a foreign row.
            supplier = next(
                node for node in tree.body
                if isinstance(node, ast.AsyncFunctionDef)
                and node.name == "build_supplier_spring_drawing"
            )
            assert supplier.args.args[1].arg == "spec"
            local_nodes = tuple(ast.walk(supplier))
            assert all(read in local_nodes for read in reads), source.name
            binding = next(
                node for node in supplier.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "source" for t in node.targets)
            )
            assert isinstance(binding.value, ast.Attribute)
            assert binding.value.attr == "source"
            assert isinstance(binding.value.value, ast.Name)
            assert binding.value.value.id == "spec"
            assert [
                node.id
                for node in local_nodes
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
                and node.id in {"source", "spec"}
            ] == ["source"], source.name
        if source.name == "_simplified_part.py":
            # This wrapper forwards the caller's part_name. Keep its exact
            # boundary checked; save_simplified_part callers still go through
            # the own-builder/PART_NAME checks below.
            wrapper = next(
                node for node in tree.body
                if isinstance(node, ast.AsyncFunctionDef)
                and node.name == "save_simplified_part"
            )
            assert wrapper.args.args[1].arg == "part_name"
            assert _helper_name_arguments(tree) == _helper_name_arguments(wrapper) == (
                ("save_part_and_images", "part_name"),
            )
            return tokens, (), None
        if source.name in _DRAWING_OWN_ROW_READERS:
            return tokens, supplier_calls, None  # checked/forwarded identities only
        return tokens, calls, _module_part_name(tree)

    for stem, spec in dodo.DRAWINGS_BY_NAME.items():
        script = spec.script.resolve()
        own_build = f"build_{spec.part}.py"
        for source in (script, *(Path(path) for path in bg.module_deps_of(script))):
            facts = source_facts(source)
            if facts is None:
                continue
            tokens, calls, part_name = facts
            if "parts/*" in tokens:
                registered_source = source == script and _registered_source_row(
                    ast.parse(source.read_text(encoding="utf-8"))
                ) == stem
                assert (
                    source.name in {*_DRAWING_OWN_ROW_READERS, own_build}
                    or registered_source
                ), (
                    f"drawing:{stem} reaches a new dynamic registry read in "
                    f"{source.name}; review it against _expand_parts_token"
                )
            supplier_calls = tuple(
                call for call in calls if call[0] == "build_supplier_spring_drawing"
            )
            if supplier_calls:
                assert source == script, (stem, source.name, supplier_calls)
            calls = tuple(
                call for call in calls if call[0] != "build_supplier_spring_drawing"
            )
            if not calls:
                continue
            assert source.name == own_build, (stem, source.name, calls)
            assert {arg for _name, arg in calls} == {"PART_NAME"}, (stem, calls)
            assert part_name == spec.part.replace("_", "-"), stem


@pytest.fixture
def isolated_drawing_keys(tmp_path, monkeypatch):
    """Copy real drawing closures; keep all native inputs and writes isolated."""
    import _buildgraph as bg

    dodo = _load_dodo()
    stems = ("pd_platen_guide", "ch_vn_frame_side_screw", "pn_pen_assembly")
    configured_stems = (
        "sh_vn_chain_link", "sh_vn_clamping_kit_hardware", "sh_vn_music_wire"
    )
    release_relative = dodo.RELEASE_VERSION_FILE.relative_to(REPO_ROOT)
    config_relative = dodo.CONFIG_DIR.relative_to(REPO_ROOT)
    # The drawing recipe folds the config rows its closure reads (Codex #936
    # T_oyK), so the checkout carries the config tree its keys hash.
    sources = {dodo.RELEASE_VERSION_FILE, *dodo.CONFIG_DIR.rglob("*.yaml")}
    for stem in (*stems, *configured_stems):
        spec = dodo.DRAWINGS_BY_NAME[stem]
        sources.update((spec.script, *spec.assets))
        sources.update(Path(path) for path in dodo._helper_deps(spec.script))
    contents = {
        path.resolve().relative_to(REPO_ROOT): path.read_bytes() for path in sources
    }

    def clear_closure():
        bg.clear_import_caches()
        bg.config_files_of.cache_clear()

    def checkout(name="repo", *, crlf=False, drawing_stems=stems):
        root = tmp_path / name
        scripts = root / "cad" / "scripts"
        for relative, content in contents.items():
            copied = root / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            if crlf and copied.suffix == ".py":
                content = content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            copied.write_bytes(content)
        monkeypatch.setattr(dodo, "REPO_ROOT", root)
        monkeypatch.setattr(dodo._cache, "REPO_ROOT", root)
        monkeypatch.setattr(dodo, "SCRIPTS_DIR", scripts)
        monkeypatch.setattr(bg, "SCRIPTS_DIR", scripts)
        monkeypatch.setattr(dodo, "CONFIG_DIR", root / config_relative)
        monkeypatch.setattr(bg, "CONFIG_DIR", dodo.CONFIG_DIR)
        monkeypatch.setattr(bg, "ASSEMBLY_CONTRACT_DIR", dodo.CONFIG_DIR / "assemblies")
        monkeypatch.setattr(dodo, "CAD_OUT", root / "cad" / "out")
        monkeypatch.setattr(bg, "CAD_OUT", dodo.CAD_OUT)
        monkeypatch.setattr(
            dodo,
            "RELEASE_VERSION_FILE",
            root / release_relative,
        )
        adapter = root / ".adapter.digest"
        adapter.write_bytes(b"fixed drawing adapter\n")
        monkeypatch.setattr(dodo, "_submodule_dep", lambda: str(adapter))
        native_recipe = root / "native-recipe.py"
        native_recipe.write_bytes(b"MODEL_DIMENSION = 1\n")
        monkeypatch.setattr(
            dodo, "_part_file_deps", lambda _script, _stem: [str(native_recipe)]
        )
        monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: [str(native_recipe)])
        monkeypatch.setattr(dodo, "references_of", lambda _stem: ())

        def reload_registry():
            path = scripts / "_drawing_registry.py"
            module = ModuleType("_isolated_drawing_registry")
            module.__file__ = str(path)
            monkeypatch.setitem(sys.modules, module.__name__, module)
            # Compile current bytes directly: same-size, same-second row edits
            # must not be hidden by Python's timestamp-based .pyc cache.
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            monkeypatch.setattr(dodo, "DRAWINGS_BY_NAME", module.DRAWINGS_BY_NAME)

        reload_registry()
        index = {}
        for stem in drawing_stems:
            spec = dodo.DRAWINGS_BY_NAME[stem]
            kind = spec.source_kind
            source = Path(
                dodo._sldasm(spec.part)
                if kind == "assembly"
                else dodo._sldprt(spec.part)
            )
            token = Path(
                dodo._assembly_execution_token(spec.part)
                if kind == "assembly"
                else dodo._part_execution_token(spec.part)
            )
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"fixed native model identity")
            token.write_bytes(b"a" * 64 + b"\n")
            index[dodo._artefact_key(str(source))] = (kind, spec.part)
        dodo._ARTEFACT_INDEX = index

        def snapshot():
            reload_registry()
            clear_closure()
            dodo._ARTEFACT_DIGEST_MEMO.clear()
            result = {}
            for stem in drawing_stems:
                deps = dodo._drawing_file_deps(stem)
                assert all(
                    Path(path).resolve().is_relative_to(root.resolve()) for path in deps
                ), stem
                result[stem] = (dodo._digest_files(deps), dodo._cache_key(deps))
            return result

        return dodo, root, snapshot

    try:
        yield checkout
    finally:
        clear_closure()


def test_drawing_registry_projection_accepts_only_declarative_layout_members():
    import _buildgraph as bg

    dodo = _load_dodo()
    registry = dodo.SCRIPTS_DIR / "_drawing_registry.py"
    source = registry.read_text(encoding="utf-8")
    marker = "layout=DrawingLayout.LANDSCAPE,"
    spec = dodo.DRAWINGS_BY_NAME["pd_platen_guide"]

    for member in ("LANDSCAPE", "PORTRAIT"):
        candidate = source.replace(
            marker,
            f"layout=DrawingLayout.{member},",
            1,
        )
        assert bg.drawing_registry_recipe(candidate, spec)

    executable = source.replace(marker, "layout=choose_layout(),", 1)
    with pytest.raises(
        ValueError,
        match="only literals or DrawingLayout members",
    ):
        bg.drawing_registry_recipe(executable, spec)


@pytest.mark.parametrize("change", ["edit", "add"])
def test_unrelated_drawing_rows_preserve_freshness_and_cache_keys(
    isolated_drawing_keys, change
):
    dodo, root, snapshot = isolated_drawing_keys()
    before = snapshot()
    generated = {
        Path(path)
        for stem in before
        for path in dodo._drawing_file_deps(stem)
        if Path(path).is_relative_to(dodo.CAD_OUT) and Path(path).suffix == ".digest"
    }
    old_time = 1_600_000_000_000_000_000
    for path in generated:
        os.utime(path, ns=(old_time, old_time))
    persisted = {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in generated
    }
    registry = root / "cad" / "scripts" / "_drawing_registry.py"
    text = registry.read_text(encoding="utf-8")
    original = text
    if change == "edit":
        text = text.replace(
            'artifact_stem="dt-crank-arm"', 'artifact_stem="dt-crank-arm-new"'
        )
    else:
        text = text.replace(
            "DRAWINGS: tuple[DrawingSpec, ...] = (",
            "DRAWINGS: tuple[DrawingSpec, ...] = (\n"
            '    DrawingSpec("unrelated", "unrelated", "unrelated", '
            '"draw_unrelated.py", DrawingLayout.LANDSCAPE),',
        )
    assert text != original, "the unrelated registry mutation must actually change its fixture"
    registry.write_text(text, encoding="utf-8")
    assert snapshot() == before
    assert generated, "drawing projection must have a persisted freshness input"
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in generated
    } == persisted


def test_selected_drawing_row_changes_only_its_freshness_and_cache_key(
    isolated_drawing_keys,
):
    _dodo, root, snapshot = isolated_drawing_keys()
    before = snapshot()
    registry = root / "cad" / "scripts" / "_drawing_registry.py"
    registry.write_text(
        registry.read_text(encoding="utf-8").replace(
            'artifact_stem="pd-platen-guide"', 'artifact_stem="pd-platen-guide-revised"'
        ),
        encoding="utf-8",
    )
    after = snapshot()
    assert all(a != b for a, b in zip(before["pd_platen_guide"], after["pd_platen_guide"]))
    for stem in ("ch_vn_frame_side_screw", "pn_pen_assembly"):
        assert after[stem] == before[stem]


def test_config_row_change_moves_only_its_readers_freshness_and_cache_key(
    isolated_drawing_keys,
):
    dodo, _root, snapshot = isolated_drawing_keys()
    before = snapshot()
    # A renumbering: no geometry input moves, only the printed registry value.
    row = dodo.CONFIG_DIR / "parts" / "pd-platen-guide.yaml"
    text = row.read_text(encoding="utf-8")
    renumbered = re.sub(r"(?m)^(\s+number:\s*)\S+$", r"\g<1>MHA-PD-99", text, count=1)
    assert renumbered != text
    row.write_text(renumbered, encoding="utf-8")
    after = snapshot()
    assert all(a != b for a, b in zip(before["pd_platen_guide"], after["pd_platen_guide"]))
    for stem in ("ch_vn_frame_side_screw", "pn_pen_assembly"):
        assert after[stem] == before[stem], stem


@pytest.mark.parametrize(
    "changed_stem",
    ["sh_vn_chain_link", "sh_vn_clamping_kit_hardware", "sh_vn_music_wire"],
)
@pytest.mark.parametrize("field", ["default_configuration", "configuration_quantities"])
def test_purchased_configuration_changes_invalidate_only_own_drawing(
    isolated_drawing_keys, monkeypatch, changed_stem, field
):
    """Real member consumers and direct drawing keys agree on registry ownership."""
    import _config
    import _part_configuration_exports as exports
    import _purchased_part_variants as variants
    import yaml

    purchased = ("sh_vn_chain_link", "sh_vn_clamping_kit_hardware", "sh_vn_music_wire")
    dodo, _root, drawing_keys = isolated_drawing_keys(
        drawing_stems=(*purchased, "pd_platen_guide")
    )
    monkeypatch.setattr(_config, "CONFIG_DIR", dodo.CONFIG_DIR)

    def snapshot():
        _config._parts_registry.cache_clear()
        _config._doc.cache_clear()
        try:
            members = {}
            for stem in purchased:
                paths = exports.configuration_export_paths(stem, dodo.CAD_OUT)
                members[stem] = (
                    paths,
                    {
                        name: variants._member_properties(
                            stem.replace("_", "-"), name, name, {}
                        )
                        for name in paths
                    },
                )
            return drawing_keys(), members
        finally:
            _config._parts_registry.cache_clear()
            _config._doc.cache_clear()

    before_keys, before_members = snapshot()
    dashed = changed_stem.replace("_", "-")
    path = dodo.CONFIG_DIR / "parts" / f"{dashed}.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    row = document[dashed]
    quantities = row["configuration_quantities"]
    if field == "default_configuration":
        row[field] = next(name for name in quantities if name != row[field])
    else:
        quantities[row["default_configuration"]] += 1
        row["quantity"] = sum(quantities.values())
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    after_keys, after_members = snapshot()

    for stem in before_keys:
        if stem == changed_stem:
            # Both local freshness and the cross-machine cache must invalidate,
            # even with the native producer recipe/execution identity held fixed.
            assert all(a != b for a, b in zip(before_keys[stem], after_keys[stem]))
        else:
            assert after_keys[stem] == before_keys[stem], stem
    for stem in purchased:
        assert (after_members[stem] != before_members[stem]) == (stem == changed_stem), stem


@pytest.mark.parametrize(
    "member", ["shared_registry", "transitive_helper", "template", "revision"]
)
def test_shared_drawing_inputs_invalidate_freshness_and_cache_keys(
    isolated_drawing_keys, member
):
    dodo, root, snapshot = isolated_drawing_keys()
    before = snapshot()
    scripts = root / "cad" / "scripts"
    if member == "shared_registry":
        path = scripts / "_drawing_registry.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'f"{self.artifact_stem}_drawing.png"',
                'f"{self.artifact_stem}_preview.png"',
            ),
            encoding="utf-8",
        )
    elif member == "revision":
        dodo.RELEASE_VERSION_FILE.write_text("next_revision: v999\n", encoding="utf-8")
    else:
        path = {
            "transitive_helper": scripts / "_drawing_common.py",
            "template": next(iter(dodo.DRAWINGS_BY_NAME["pd_platen_guide"].assets)),
        }[member]
        path.write_bytes(path.read_bytes() + b"\n# changed shared input\n")
    after = snapshot()
    for stem in before:
        assert all(a != b for a, b in zip(before[stem], after[stem])), stem


def test_registry_imported_helper_remains_in_complete_drawing_closure(
    isolated_drawing_keys, monkeypatch
):
    _dodo, root, snapshot = isolated_drawing_keys()
    scripts = root / "cad" / "scripts"
    helper = scripts / "_drawing_recipe_extra.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    module = ModuleType("_drawing_recipe_extra")
    exec(compile(helper.read_bytes(), str(helper), "exec"), module.__dict__)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    registry = scripts / "_drawing_registry.py"
    registry.write_text(
        registry.read_text(encoding="utf-8")
        + "\nfrom _drawing_recipe_extra import VALUE\n",
        encoding="utf-8",
    )
    before = snapshot()
    helper.write_text("VALUE = 2\n", encoding="utf-8")
    after = snapshot()
    for stem in before:
        assert all(a != b for a, b in zip(before[stem], after[stem])), stem


@pytest.mark.parametrize(
    "consumer",
    [
        "from _drawing_registry import DRAWINGS\nALL_DRAWINGS = tuple(DRAWINGS)\n",
        "from _drawing_registry import DRAWINGS_BY_NAME\nOTHER = DRAWINGS_BY_NAME['dt_crank_arm']\n",
        "from _drawing_registry import DRAWINGS_BY_NAME\n"
        "def select(name):\n    return DRAWINGS_BY_NAME[name]\n",
        "import _drawing_registry as registry\ndef expose():\n    return registry\n",
        "from _drawing_registry import DRAWINGS_BY_NAME as rows\n"
        "def lookup():\n    return rows.get('pd_platen_guide')\n",
        "import importlib\n"
        "registry = importlib.import_module('_drawing_registry')\n"
        "OTHER = registry.DRAWINGS_BY_NAME['dt_crank_arm']\n",
        "import sys\n"
        "registry = sys.modules['_drawing_registry']\n"
        "OTHER = registry.DRAWINGS_BY_NAME['dt_crank_arm']\n",
        "from importlib import import_module as load\n"
        "registry = load('_drawing_' + 'registry')\n"
        "OTHER = registry.DRAWINGS_BY_NAME['dt_crank_arm']\n",
        "REGISTRY_NAME = '_drawing_registry'\n"
        "def other_row(loader):\n"
        "    return loader(REGISTRY_NAME).DRAWINGS_BY_NAME['dt_crank_arm']\n",
    ],
    ids=[
        "whole",
        "other-row",
        "dynamic",
        "escaped-module",
        "unknown-mapping-call",
        "dynamic-import",
        "sys-modules",
        "computed-module-import",
        "escaped-module-name",
    ],
)
def test_unclassified_transitive_registry_consumers_keep_full_dependency(
    isolated_drawing_keys, consumer
):
    _dodo, root, snapshot = isolated_drawing_keys()
    scripts = root / "cad" / "scripts"
    helper = scripts / "_drawing_common.py"
    helper.write_text(
        helper.read_text(encoding="utf-8") + "\n" + consumer, encoding="utf-8"
    )
    before = snapshot()
    registry = scripts / "_drawing_registry.py"
    registry.write_text(
        registry.read_text(encoding="utf-8").replace(
            'artifact_stem="dt-crank-arm"', 'artifact_stem="dt-crank-arm-revised"'
        ),
        encoding="utf-8",
    )
    after = snapshot()
    for stem in before:
        assert all(a != b for a, b in zip(before[stem], after[stem])), stem


def test_drawing_registry_keys_are_checkout_and_eol_independent(isolated_drawing_keys):
    _dodo, _root, snapshot = isolated_drawing_keys("lf")
    before = snapshot()
    _dodo, _root, snapshot = isolated_drawing_keys("crlf", crlf=True)
    assert snapshot() == before


@pytest.mark.parametrize("stem", ["pd_platen_guide", "pn_pen_assembly"])
def test_drawing_projection_preserves_exact_native_execution_identity(
    isolated_drawing_keys, stem
):
    dodo, _root, snapshot = isolated_drawing_keys()
    before = snapshot()
    spec = dodo.DRAWINGS_BY_NAME[stem]
    assembly = spec.source_kind == "assembly"
    source = dodo._sldasm(spec.part) if assembly else dodo._sldprt(spec.part)
    token = (
        dodo._assembly_execution_token(spec.part)
        if assembly
        else dodo._part_execution_token(spec.part)
    )
    Path(source).write_bytes(b"same recipe with foreign persistent-reference IDs")
    assert snapshot() == before, (
        "recipe identity deliberately ignores native save bytes"
    )
    Path(token).write_bytes(b"b" * 64 + b"\n")
    after = snapshot()
    assert all(a != b for a, b in zip(before[stem], after[stem]))
    for other in before.keys() - {stem}:
        assert after[other] == before[other]


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


@pytest.fixture
def isolated_assembly_helper_keys(tmp_path, monkeypatch):
    """Real discovered dependency sets and key functions, copied input bytes only.

    Discovery reads source but never native outputs. All artifacts, execution
    tokens, and synthetic adapter dependencies live under this fixture before
    task generation; changing a helper cannot race a concurrent CAD build.
    """
    import _buildgraph

    dodo = _load_dodo()
    fixture_root = tmp_path / "repo"
    fixture_root.mkdir()
    monkeypatch.setattr(dodo, "CAD_OUT", fixture_root / "cad" / "out")
    monkeypatch.setattr(_buildgraph, "CAD_OUT", dodo.CAD_OUT)
    for tier in ("part", "assembly"):
        sidecar = fixture_root / f".adapter-{tier}.digest"
        sidecar.write_text(f"fixed {tier} adapter input\n", encoding="utf-8")
        monkeypatch.setattr(
            dodo, f"_submodule_{tier}_dep", lambda path=str(sidecar): path
        )

    assembly_recipes = {stem: dodo._recipe_files(stem) for stem in dodo.ASSEMBLY_ORDER}
    part_tasks = {task["name"]: task for task in dodo.task_part()}
    assembly_tasks = {task["name"]: task for task in dodo.task_assembly()}
    sources = {path for recipe in assembly_recipes.values() for path in recipe} | {
        path for task in part_tasks.values() for path in task["file_dep"]
    }
    mapped = {}
    for path in sources:
        original = Path(path).resolve()
        if original.is_relative_to(fixture_root):
            mapped[path] = str(original)
            continue
        copied = fixture_root / original.relative_to(REPO_ROOT)
        assert copied.resolve().is_relative_to(fixture_root.resolve())
        copied.parent.mkdir(parents=True, exist_ok=True)
        if original.exists():
            copied.write_bytes(original.read_bytes())
        mapped[path] = str(copied)

    for task in [*part_tasks.values(), *assembly_tasks.values()]:
        for target in task["targets"]:
            path = Path(target)
            assert path.resolve().is_relative_to(fixture_root.resolve()), path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"a" * 64 + b"\n")

    recipes = {
        stem: [mapped[path] for path in paths]
        for stem, paths in assembly_recipes.items()
    }
    part_deps = {
        stem: [mapped[path] for path in task["file_dep"]]
        for stem, task in part_tasks.items()
    }
    monkeypatch.setattr(dodo, "_recipe_files", lambda stem: recipes[stem])
    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, stem: part_deps[stem])
    monkeypatch.setattr(dodo, "REPO_ROOT", fixture_root)
    monkeypatch.setattr(dodo._cache, "REPO_ROOT", fixture_root)
    dodo._ARTEFACT_INDEX = None
    dodo._ARTEFACT_DIGEST_MEMO.clear()
    for stem, task in assembly_tasks.items():
        assert dodo._assembly_file_deps(stem) == [
            mapped.get(path, path) for path in task["file_dep"]
        ]

    def snapshot():
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        # Generate again after redirecting recipe paths; the discovery-time
        # assembly_tasks above are used only to initialize isolated targets.
        current_assembly_tasks = {task["name"]: task for task in dodo.task_assembly()}
        for stem, task in current_assembly_tasks.items():
            assert task["file_dep"] == dodo._assembly_file_deps(stem)
            assert all(
                Path(path).resolve().is_relative_to(fixture_root.resolve())
                for path in task["file_dep"]
            ), stem
        return {
            "recipes": {
                stem: dodo._digest_files(paths) for stem, paths in recipes.items()
            },
            "assemblies": {
                stem: dodo._cache_key(task["file_dep"])
                for stem, task in current_assembly_tasks.items()
            },
            "part_recipes": {
                stem: dodo._digest_files(paths) for stem, paths in part_deps.items()
            },
            "parts": {
                stem: dodo._cache_key(paths) for stem, paths in part_deps.items()
            },
        }

    return dodo, fixture_root, snapshot


@pytest.mark.parametrize(
    ("helper", "consumers"),
    [
        (
            "_assembly_patterns",
            {
                "ch_channel",
                "dt_drive_train",
                "fr_frame",
                "mg_magnifier",
                "pd_paper_drive",
                "ms_measuring_stick",
                "pn_pen",
                "sm_summing",
                "ha_harmonic_analyzer",
                "ch_rocker_arm_tl_oblique_jig",
            },
        ),
        ("_assembly_couplings", {"dt_drive_train", "pd_paper_drive"}),
        ("_assembly", None),
        ("_component_references", None),
    ],
)
def test_assembly_helper_edits_change_only_real_recipe_and_cache_consumers(
    isolated_assembly_helper_keys, helper, consumers
):
    dodo, root, snapshot = isolated_assembly_helper_keys
    expected = set(dodo.ASSEMBLY_ORDER) if consumers is None else consumers
    before = snapshot()
    copied_helper = root / "cad" / "scripts" / f"{helper}.py"
    assert copied_helper.is_file(), f"missing real helper input: {helper}"
    copied_helper.write_bytes(
        copied_helper.read_bytes() + b"\n# isolated key mutation\n"
    )
    after = snapshot()

    def changed(group):
        return {
            stem for stem in before[group] if before[group][stem] != after[group][stem]
        }

    assert changed("recipes") == expected
    # Parent keys legitimately include child recipe digests before their exact
    # execution tokens change. This is not a direct top-level FULL rebuild.
    assert changed("assemblies") == expected | {"ha_harmonic_analyzer"}
    assert changed("part_recipes") == set()
    assert changed("parts") == set()


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


@pytest.mark.parametrize(
    ("assembly", "producers"),
    [
        (
            "dt_drive_train",
            ("sh_vn_brass_fillister_screw", "sh_vn_fillister_screw_90280a108"),
        ),
        (
            "pd_paper_drive",
            ("sh_vn_chain_link", "sh_vn_fillister_screw_90280a108"),
        ),
        ("ch_rocker_arm_tl_oblique_jig", ("sh_vn_clamping_kit_hardware",)),
    ],
)
def test_repeated_roles_and_configured_members_share_exact_producer_dependencies(
    assembly, producers,
):
    dodo = _load_dodo()
    dependencies = dodo._assembly_file_deps(assembly)
    references = dodo.references_of(assembly)
    for producer in producers:
        assert references.count(producer) == 1
        assert dependencies.count(dodo._sldprt(producer)) == 1
        assert dependencies.count(dodo._part_execution_token(producer)) == 1


def test_assembly_file_deps_drop_only_non_inserted_source_targets():
    dodo = _load_dodo()
    removed = {
        "fr_frame": ("sm_gooseneck", "ch_rocker_arm"),
        "dt_drive_train": ("fr_harmonic_base", "ch_channel"),
        "ch_channel": ("dt_cylinder_gear", "fr_frame"),
    }
    for assembly, sources in removed.items():
        dependencies = set(dodo._assembly_file_deps(assembly))
        for source in sources:
            if source in dodo.ASSEMBLY_ORDER:
                target = dodo._sldasm(source)
                token = dodo._assembly_execution_token(source)
            else:
                target = dodo._sldprt(source)
                token = dodo._part_execution_token(source)
            assert target not in dependencies, (assembly, source)
            assert token not in dependencies, (assembly, source)


def test_source_graph_cache_keys_preserve_real_transitive_identity_edges(
    tmp_path, monkeypatch
):
    """Actual DAG, isolated recipe bytes/tokens: never read a live builder's files."""
    import _buildgraph

    dodo = _load_dodo()
    monkeypatch.setattr(dodo, "CAD_OUT", tmp_path / "out")
    monkeypatch.setattr(_buildgraph, "CAD_OUT", dodo.CAD_OUT)
    recipes = {}
    part_tokens = {}
    assembly_tokens = {}
    for kind, stems in (("part", dodo.part_stems()), ("assembly", dodo.ASSEMBLY_ORDER)):
        for stem in stems:
            recipe = tmp_path / f"{kind}-{stem}.input"
            recipe.write_text(f"source recipe for {kind}:{stem}\n")
            recipes[kind, stem] = str(recipe)
            target = Path(dodo._sldprt(stem) if kind == "part" else dodo._sldasm(stem))
            token = Path(
                dodo._part_execution_token(stem)
                if kind == "part"
                else dodo._assembly_execution_token(stem)
            )
            assert target.resolve().is_relative_to(tmp_path.resolve()), target
            assert token.resolve().is_relative_to(tmp_path.resolve()), token
            target.parent.mkdir(parents=True, exist_ok=True)
            token.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"CAD identity A")
            token.write_text("a" * 64 + "\n")
            (part_tokens if kind == "part" else assembly_tokens)[stem] = token
    monkeypatch.setattr(dodo, "_recipe_files", lambda stem: [recipes["assembly", stem]])
    monkeypatch.setattr(
        dodo, "_part_file_deps", lambda _script, stem: [recipes["part", stem]]
    )

    def keys():
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        return {
            stem: dodo._cache_key(dodo._assembly_file_deps(stem))
            for stem in dodo.ASSEMBLY_ORDER
        }

    def changed(before, after):
        return {stem for stem in before if before[stem] != after[stem]}

    baseline = keys()
    cases = {
        "ch_rocker_arm": {"ch_channel"},
        "sm_gooseneck": {"sm_summing"},
        "fr_harmonic_base": {"fr_frame"},
        "dt_cylinder_gear": {"dt_drive_train"},
        "ch_vn_frame_side_screw": {"ch_channel"},
        "fr_vn_frame_cross_screw": {"fr_frame"},
    }
    for source, expected in cases.items():
        part_tokens[source].write_text("b" * 64 + "\n")
        assert changed(baseline, keys()) == expected, source
        part_tokens[source].write_text("a" * 64 + "\n")

    # A real channel-child identity refresh restamps channel, then invalidates
    # top-level CAD. It must never traverse the removed channel->drive edge.
    part_tokens["ch_rocker_arm"].write_text("b" * 64 + "\n")
    channel_dirty = keys()
    assembly_tokens["ch_channel"].write_text("c" * 64 + "\n")
    assert changed(channel_dirty, keys()) == {"ha_harmonic_analyzer"}
    assembly_tokens["ch_channel"].write_text("a" * 64 + "\n")
    part_tokens["ch_rocker_arm"].write_text("a" * 64 + "\n")

    # Recipe changes propagate recursively even before execution tokens change.
    Path(recipes["part", "ch_rocker_arm"]).write_text("changed rocker geometry recipe\n")
    assert changed(baseline, keys()) == {"ch_channel", "ha_harmonic_analyzer"}


def test_verify_gates_depend_on_exact_assembly_identities():
    """An identity-only refresh must invalidate persisted verify stamps."""
    dodo = _load_dodo()
    soundness = {task["name"]: task for task in dodo.task_verify_soundness()}
    for stem in dodo.ASSEMBLY_ORDER:
        assert dodo._assembly_execution_token(stem) in soundness[stem]["file_dep"]

    kinematics = next(
        task for task in dodo.task_verify() if task["name"] == "kinematics"
    )
    for stem in ("pn_pen", "mg_magnifier", "pd_paper_drive"):
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
    output = tmp_path / "pd-platen-guide.SLDDRW"
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

    dodo._cached_drawing_action("pd_platen_guide")

    assert len(restores) == 1
    assert not stores


def test_cached_drawing_miss_builds_once_then_stores(tmp_path, monkeypatch):
    dodo = _load_dodo()
    output = tmp_path / "pd-platen-guide.SLDDRW"
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

    dodo._cached_drawing_action("pd_platen_guide")

    assert len(restores) == 2
    assert builds == [True]
    assert len(stores) == 1
    assert stores[0][1] == [output]


def _locked(dodo, key, label):
    return dodo._cache.RestoreLocked(
        label, key, PermissionError(13, "Permission denied", "pd-platen-guide.SLDDRW")
    )


def test_cached_drawing_locked_restore_releases_seat_then_restores(
    tmp_path, monkeypatch
):
    """A HIT refused by a share lock must NOT fall through to a local build (that
    forks the artefact identity off the fleet's): release the seat's resident
    documents under the seat, then the re-probe restores the cached build."""
    dodo = _load_dodo()
    output = tmp_path / "pd-platen-guide.SLDDRW"
    events = []

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    outcomes = iter(("locked", True))

    def restore(key, outputs, label):
        outcome = next(outcomes)
        events.append(("restore", outcome))
        if outcome == "locked":
            raise _locked(dodo, key, label)
        return outcome

    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext())
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(
        dodo,
        "_exec_com",
        lambda cmd, label, **_kwargs: events.append(("exec", Path(cmd[1]).name)),
    )
    monkeypatch.setattr(
        dodo._cache,
        "store",
        lambda *_args: events.append(("store", None)) or "stored",
    )

    dodo._cached_drawing_action("pd_platen_guide")

    assert events == [
        ("restore", "locked"),
        ("exec", "release_seat_documents.py"),
        ("restore", True),
    ]


def test_cached_drawing_lock_first_seen_under_seat_still_recovers(
    tmp_path, monkeypatch
):
    """Outside probe: miss. A peer publishes while we queue; the under-seat
    probe is the first to hit the lock -- it still gets the release + one
    re-probe instead of failing (CodeRabbit, #754)."""
    dodo = _load_dodo()
    output = tmp_path / "pd-platen-guide.SLDDRW"
    events = []

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    outcomes = iter((False, "locked", True))

    def restore(key, outputs, label):
        outcome = next(outcomes)
        events.append(("restore", outcome))
        if outcome == "locked":
            raise _locked(dodo, key, label)
        return outcome

    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext())
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(
        dodo,
        "_exec_com",
        lambda cmd, label, **_kwargs: events.append(("exec", Path(cmd[1]).name)),
    )
    monkeypatch.setattr(dodo._cache, "store", lambda *_args: "stored")

    dodo._cached_drawing_action("pd_platen_guide")

    assert events == [
        ("restore", False),
        ("restore", "locked"),
        ("exec", "release_seat_documents.py"),
        ("restore", True),
    ]


def test_cached_drawing_still_locked_after_release_fails_loud(tmp_path, monkeypatch):
    dodo = _load_dodo()
    output = tmp_path / "pd-platen-guide.SLDDRW"
    builds = []

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)

    def restore(key, outputs, label):
        raise _locked(dodo, key, label)

    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext())
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(
        dodo, "_exec_com", lambda cmd, label, **_kwargs: builds.append(Path(cmd[1]).name)
    )

    with pytest.raises(RuntimeError, match="still share-locked"):
        dodo._cached_drawing_action("pd_platen_guide")

    # The release ran; the drawing itself was never built over the locked file.
    assert builds == ["release_seat_documents.py"]


def test_cached_drawing_locked_restore_under_farm_fails_loud(tmp_path, monkeypatch):
    """The farm submitter holds no seat to release: a locked restore is fatal
    before any leaf is dispatched."""
    dodo = _load_dodo()
    output = tmp_path / "pd-platen-guide.SLDDRW"

    monkeypatch.setattr(
        dodo, "_drawing_file_deps", lambda _stem: [str(tmp_path / "dep")]
    )
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)

    def restore(key, outputs, label):
        raise _locked(dodo, key, label)

    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(dodo._farm, "enabled", lambda: True)
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda *_args: (_ for _ in ()).throw(AssertionError("leaf dispatched")),
    )

    with pytest.raises(dodo._cache.RestoreLocked, match="share-locked"):
        dodo._cached_drawing_action("pd_platen_guide")


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


def test_content_checker_yaml_digest_reads_same_size_same_mtime_edits(tmp_path):
    dodo = _load_dodo()
    digest = dodo.ContentChecker._digest
    cfg = tmp_path / "config.yaml"
    cfg.write_bytes(b"value: 1\n")
    original_stat = cfg.stat()
    original_digest = digest(str(cfg))

    cfg.write_bytes(b"value: 2\n")
    os.utime(cfg, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    assert digest(str(cfg)) != original_digest

    cfg.write_bytes(b"value: 1\n")
    assert digest(str(cfg)) == original_digest
    cfg.unlink()
    with pytest.raises(FileNotFoundError):
        digest(str(cfg))
    cfg.mkdir()
    with pytest.raises(OSError):
        digest(str(cfg))


@pytest.mark.parametrize(
    "raw",
    [
        b"value: [\n",
        b"value: [\r\n",
        b"value: \xff\r\n",
        b"value: \x00\r\n",
    ],
)
def test_content_checker_yaml_load_failure_keeps_raw_fallback(tmp_path, raw):
    dodo = _load_dodo()
    cfg = tmp_path / "malformed.yaml"
    cfg.write_bytes(raw)
    expected = dodo._canonical_file_md5(str(cfg))
    assert dodo.ContentChecker._digest(str(cfg)) == expected
    assert dodo.ContentChecker._digest(str(cfg)) == expected
    cfg.write_bytes(b"value: 1\n")
    assert dodo.ContentChecker._digest(str(cfg)) != expected


def test_content_checker_yaml_digest_preserves_mapping_order(tmp_path):
    dodo = _load_dodo()
    cfg = tmp_path / "config.yaml"
    cfg.write_bytes(b"first: 1\nsecond: 2\n")
    original = dodo.ContentChecker._digest(str(cfg))
    cfg.write_bytes(b"second: 2\nfirst: 1\n")
    assert dodo.ContentChecker._digest(str(cfg)) != original


def test_content_checker_yaml_digest_preserves_binary_reader_encoding(tmp_path):
    dodo = _load_dodo()
    cfg = tmp_path / "config.yaml"
    text = "value: caf\u00e9\n"
    cfg.write_bytes(text.encode("utf-8"))
    original = dodo.ContentChecker._digest(str(cfg))
    cfg.write_bytes(text.encode("utf-16"))
    assert dodo.ContentChecker._digest(str(cfg)) == original


def test_content_checker_yaml_non_yaml_load_error_propagates(tmp_path):
    dodo = _load_dodo()
    cfg = tmp_path / "config.yaml"
    cfg.write_bytes(b"date: 2026-13-01\n")
    with pytest.raises(ValueError):
        dodo.ContentChecker._digest(str(cfg))


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


def test_content_checker_sees_a_same_tick_same_size_rewrite(tmp_path):
    """A dep rewritten at the same size inside the file-time tick its state was
    recorded in keeps its mtime, so the mtime fast path alone would vouch for the
    stale content and leave the task up to date. Pinning one mtime across both
    writes reproduces that tick deterministically."""
    dodo = _load_dodo()
    checker = dodo.ContentChecker()
    src = tmp_path / "s.py"
    src.write_text("X = 'old'\n")
    tick = (time.time_ns(),) * 2
    os.utime(src, ns=tick)
    state = checker.get_state(str(src), None)
    src.write_text("X = 'new'\n")
    os.utime(src, ns=tick)
    assert checker.check_modified(str(src), os.stat(src), state) is True


def test_content_checker_keeps_the_fast_path_for_settled_deps(tmp_path):
    """A dep whose mtime settled before its state was recorded keeps doit's mtime
    fast path: an unchanged mtime means unchanged, with no digest recomputed."""
    dodo = _load_dodo()
    checker = dodo.ContentChecker()
    src = tmp_path / "s.py"
    src.write_text("X = 1\n")
    settled = (time.time_ns() - 60_000_000_000,) * 2
    os.utime(src, ns=settled)
    state = checker.get_state(str(src), None)
    assert state[0] == os.stat(src).st_mtime
    assert checker.get_state(str(src), state) is None


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
    lives in _assembly_postbuild.py, off every build closure). Derive each leaf's
    helpers from the Python entry points it actually executes, not from a shared
    verify.py closure that unrelated verification commands need not execute."""
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

    tasks = [
        (f"verify:{task['name']}", task) for task in dodo.task_verify()
    ] + [
        (f"verify_soundness:{task['name']}", task)
        for task in dodo.task_verify_soundness()
    ] + [("preflight", dodo.task_preflight())]
    verify_entry_seen = False
    for label, task in tasks:
        entries = set()
        for action, args in task["actions"]:
            if action is dodo._cached_com_action:
                command_entries = {
                    Path(arg).resolve()
                    for arg in args[1]
                    if str(arg).endswith(".py")
                }
                assert command_entries, f"{label} runs no Python entry point"
                entries.update(command_entries)
        if not entries:
            # Stamp-only aggregates inherit execution from their child stamps;
            # their explicit Python dependencies describe the gate they aggregate.
            entries = {
                Path(dep).resolve()
                for dep in task["file_dep"]
                if str(dep).endswith(".py")
            }
        assert entries, f"{label} has no gate source to inspect"
        deps = {os.path.basename(dep) for dep in task["file_dep"]}
        for entry in entries:
            orphans = _orphan_helpers(entry)
            if entry == Path(dodo.VERIFY_PY).resolve():
                verify_entry_seen = True
                assert "_assembly_postbuild.py" in orphans, orphans
            assert orphans <= deps, (
                f"{label} ({entry.name}) missing gate-logic deps: {orphans - deps}"
            )
    assert verify_entry_seen, "the verify.py gate closure was never inspected"


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
    HARMONIC_COM_SEAT (inherited by the COM subprocess -> _session.run_build's tripwire), and
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
    # Written after com.seat.wait closed, so it names its resource itself --
    # otherwise it lands on the umbrella resource, parentless (4.9k rows / 7 d).
    assert fields == {
        "wait_s": 45.0,
        "held_s": 5.5,
        "elapsed_s": 50.5,
        "service": dodo._telemetry.BUILD_INFRA_SERVICE,
    }


@pytest.fixture
def vendor_warning_capture(monkeypatch):
    """Capture the real severity/resource-routed OTel logs without disk or OTLP."""
    from opentelemetry._logs import get_logger_provider
    from opentelemetry.sdk._logs.export import (
        InMemoryLogRecordExporter,
        SimpleLogRecordProcessor,
    )
    import _telemetry

    try:
        with monkeypatch.context() as capture_patch:
            capture_patch.setattr(
                _telemetry, "_resolve_otlp_endpoint", lambda _signal, **_kw: None
            )
            capture_patch.setattr(_telemetry, "_telemetry_dir", lambda: None)
            capture_patch.setenv("HARMONIC_VERBOSITY", "warn")
            _telemetry.configure(force=True)
            logs = InMemoryLogRecordExporter()
            processor = SimpleLogRecordProcessor(logs)
            get_logger_provider().add_log_record_processor(processor)
            # Task-stage logger providers share these processors, as in test_telemetry.
            _telemetry._log_processors.append(processor)
            _telemetry._aux_logger_providers.clear()
            yield logs
    finally:
        _telemetry.configure(force=True)


@pytest.mark.parametrize("failed", [False, True], ids=["normal-exit", "exception"])
def test_vendor_warning_capture_restores_jsonl_sink(tmp_path, monkeypatch, failed):
    """A subsequent real log reaches the restored sink even after a test raises."""
    import json
    import _telemetry

    try:
        with monkeypatch.context() as restored:
            restored.setattr(_telemetry, "_telemetry_dir", lambda: tmp_path)
            restored.setattr(
                _telemetry, "_resolve_otlp_endpoint", lambda _signal, **_kw: None
            )
            capture = vendor_warning_capture.__wrapped__(monkeypatch)
            try:
                next(capture)
                _telemetry.warn("temporary capture", fixture_probe="captured")
                assert not (tmp_path / "logs.jsonl").exists()
                if failed:
                    with pytest.raises(RuntimeError):
                        capture.throw(RuntimeError("test failed during capture"))
            finally:
                capture.close()

            _telemetry.warn("restored sink", fixture_probe="restored")
            rows = [
                json.loads(line)
                for line in (tmp_path / "logs.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            assert any(
                row.get("attributes", {}).get("fixture_probe") == "restored"
                for row in rows
            )
    finally:
        _telemetry.configure(force=True)


@pytest.mark.parametrize(
    "stem,executor,restores,worker,expected",
    [
        pytest.param("dt_vn_bearing", "local", (False, False), False, True, id="local-build"),
        pytest.param("dt_vn_bearing", "local", (False, False), True, True, id="worker-build"),
        pytest.param("dt_vn_bearing", "local", (True,), False, False, id="initial-hit"),
        pytest.param("dt_vn_bearing", "local", (False, True), False, False, id="hit-after-wait"),
        pytest.param("dt_vn_bearing", "farm", (False,), False, False, id="submitter-dispatch"),
        pytest.param("pn_pen_rod", "local", (False, False), False, False, id="ordinary-part"),
        pytest.param("dt_vn_bearing", "drawing", (False, False), False, False, id="vendor-drawing"),
        pytest.param(
            "ch_rocker_arm_tl_vn_oblique_cl_dowel", "local", (False, False),
            False, True, id="tooling-vendor-build",
        ),
        pytest.param(
            "ch_rocker_arm_tl_oblique_carrier", "local", (False, False),
            False, False, id="fabricated-tooling-build",
        ),
    ],
)
def test_vendor_part_warning_only_at_actual_build(
    tmp_path, monkeypatch, capsys, vendor_warning_capture,
    stem, executor, restores, worker, expected
):
    """Warn at the work boundary, not a miss that later restores or dispatches.

    A farm worker executes with the local executor and autostart disabled. All
    host-facing collaborators are replaced, including prewarm before dodo import.
    """
    import _artifact_cache

    monkeypatch.setattr(_artifact_cache, "prewarm", lambda: None)
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm" if executor == "farm" else "local")
    if worker:
        monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
        monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "farm.execution=test-vendor-warning")
    dodo = _load_dodo()
    key = "a" * 64
    script = tmp_path / f"build_{stem}.py"
    output = tmp_path / f"{stem}.SLDPRT"
    outcomes = iter(restores)
    events = []
    logs = vendor_warning_capture
    label = f"part:{stem}"

    def vendor_warnings():
        return [
            record.log_record
            for record in logs.get_finished_logs()
            if (record.log_record.attributes or {}).get("label") == label
        ]

    def execute(*_args, **_kwargs):
        # Inspect the consumer-visible record at the execution boundary.
        assert len(vendor_warnings()) == int(expected)
        events.append("execute")

    monkeypatch.setattr(dodo, "_part_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda *_a: key)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(dodo._cache, "store", lambda *_a: "stored")
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(0.0))
    monkeypatch.setattr(dodo, "_farm_build", lambda *_a: events.append("dispatch"))
    monkeypatch.setattr(dodo, "_exec_com", execute)

    if executor == "drawing":
        dodo._cached_com_action(
            f"drawing:{stem}", [sys.executable, str(script)], [], [output], "drawing"
        )
    else:
        dodo._cached_part_action(stem, script)

    warnings = vendor_warnings()
    console = capsys.readouterr().err
    if expected:
        from opentelemetry._logs import SeverityNumber

        assert len(warnings) == 1
        record = warnings[0]
        assert record.severity_number == SeverityNumber.WARN
        assert record.attributes["cache.key"] == key[:12]
        assert record.attributes["key_full"] == key
        assert record.trace_id and record.span_id
        assert "!!" in console and label in console and key[:12] in console
        assert events == ["execute"]
    else:
        assert warnings == []
        assert "!!" not in console
        if executor == "farm":
            assert events == ["dispatch"]
        elif not all(outcome is False for outcome in restores):
            assert events == []
        else:
            assert events == ["execute"]


def test_cached_part_miss_emits_four_sibling_phase_spans(tmp_path, monkeypatch):
    """A cached COM task is FOUR top-level spans, never nested: the cache probe (the
    Azure restore attempt), the seat wait, the task itself (starting once the seat is
    held), and the publish. Each phase is then timed for what it is -- crucially the
    ``task`` span cannot absorb the queueing or the network transfers."""
    dodo = _load_dodo()
    script = tmp_path / "build_pn_pen_rod.py"
    script.write_text("", encoding="utf-8")
    outcomes = iter((False, False))  # probe MISS, re-probe under the seat MISS

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(
        dodo, "_part_cache_outputs", lambda _stem: [tmp_path / "pn-pen-rod.SLDPRT"]
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

    dodo._cached_part_action("pn_pen_rod", script)

    # The seat wait span is _com_seat's, so it is not in this list.
    assert opened == [
        "cache.probe part:pn_pen_rod",
        "cache.reprobe part:pn_pen_rod",
        "task part:pn_pen_rod",
        "cache.store part:pn_pen_rod",
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
    script = tmp_path / "build_pn_pen_rod.py"
    script.write_text("", encoding="utf-8")
    outcomes = iter((False, False))  # probe MISS, re-probe MISS -> builds

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(
        dodo, "_part_cache_outputs", lambda _stem: [tmp_path / "pn-pen-rod.SLDPRT"]
    )
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: next(outcomes))
    monkeypatch.setattr(dodo._cache, "store", lambda *_a: "stored")
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda _stem: None)
    monkeypatch.setattr(dodo, "_exec_com", lambda *_a, **_kw: None)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(45.0))
    monkeypatch.setattr(dodo, "_SW_ENSURED", False)
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    # The real preflight reads the live sldworks.exe commit and force-recovers
    # (stops and relaunches) SolidWorks past the budget.
    monkeypatch.setattr(dodo, "_sw_preflight", lambda: None)

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

    dodo._cached_part_action("pn_pen_rod", script)

    assert opened == [
        "cache.probe part:pn_pen_rod",
        "cache.reprobe part:pn_pen_rod",
        "sw.ensure_ready",
        "task part:pn_pen_rod",
        "cache.store part:pn_pen_rod",
    ]


def test_sw_ensure_once_runs_once_and_respects_the_opt_out(monkeypatch):
    """``_sw_ensure_once`` calls ``ensure_ready`` at most once per worker (the
    ``_SW_ENSURED`` guard) and not at all under ``HARMONIC_SW_AUTOSTART=0``."""
    dodo = _load_dodo()
    calls: list[int] = []
    monkeypatch.setattr(dodo._sw_lifecycle, "ensure_ready", lambda: calls.append(1))
    # The real preflight reads the live sldworks.exe commit and force-recovers
    # (stops and relaunches) SolidWorks past the budget.
    monkeypatch.setattr(dodo, "_sw_preflight", lambda: None)

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
    """Task labels map to the pipeline stage advertised by their subprocess."""
    dodo = _load_dodo()
    assert dodo._stage_name("part:pn_pen_rod") == "part-build"
    assert dodo._stage_name("assembly:pn_pen") == "assembly-build"
    assert dodo._stage_name("drawing:pn_pen_rod") == "drawing-export"
    assert dodo._stage_name("package:features:ch_rocker_arm") == "export"
    assert dodo._stage_name("package:features") == "harmonic-analyzer"
    assert dodo._stage_name("verify soundness") == "verify-soundness"
    assert dodo._stage_name("nothing recognisable") == "harmonic-analyzer"


def test_external_logs_follow_warning_default_and_explicit_verbosity(monkeypatch):
    dodo = _load_dodo()
    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    assert dodo._external_console_level() == "WARNING"
    monkeypatch.setenv("HARMONIC_VERBOSITY", "debug")
    assert dodo._external_console_level() == "DEBUG"
    monkeypatch.setenv("HARMONIC_VERBOSITY", "success")
    assert dodo._external_console_level() == "SUCCESS"


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


def test_every_cache_phase_span_names_its_cache_key(monkeypatch):
    """The phase spans are sibling ROOT traces, so a build can be tied to the key
    it produced only if each span names it: probe, re-probe, task and store all
    carry ``cache.key`` (the 12-hex prefix ``cache.jsonl`` prints)."""
    dodo = _load_dodo()
    key = "0123456789abcdef" * 4
    spans: list[tuple[str, dict]] = []

    @contextlib.contextmanager
    def record_span(name, **attrs):
        entry = (name, dict(attrs))
        spans.append(entry)

        class _Span:
            def set_attribute(self, attr, value):
                entry[1][attr] = value

        yield _Span()

    @contextlib.contextmanager
    def free_seat(label):
        yield 0.0

    monkeypatch.setattr(dodo._telemetry, "span", record_span)
    monkeypatch.setattr(dodo, "_cache_key", lambda file_deps, label: key)
    monkeypatch.setattr(dodo._cache, "restore", lambda *args: False)
    monkeypatch.setattr(dodo._cache, "store", lambda *args: "stored")
    monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
    monkeypatch.setattr(dodo, "_com_seat", free_seat)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_exec_com", lambda *args, **kwargs: None)

    dodo._cached_com_action("part:x", ["build"], [], [], "part-x")

    tagged = {name.split()[0]: attrs.get("cache.key") for name, attrs in spans}
    assert tagged == {
        "cache.probe": key[:12],
        "cache.reprobe": key[:12],
        "task": key[:12],
        "cache.store": key[:12],
    }


def test_farm_restore_span_names_its_cache_key(monkeypatch):
    """Under ``--executor farm`` the submitter's phases are ``cache.probe`` then
    ``cache.restore`` (the worker publishes, this side downloads). The restore is
    the span that proves the leaf landed, so it names the key like the rest."""
    dodo = _load_dodo()
    key = "fedcba9876543210" * 4
    spans: list[tuple[str, dict]] = []
    restores = iter([False, True])  # probe misses, post-farm restore hits

    @contextlib.contextmanager
    def record_span(name, **attrs):
        entry = (name, dict(attrs))
        spans.append(entry)

        class _Span:
            def set_attribute(self, attr, value):
                entry[1][attr] = value

        yield _Span()

    succeeded = dodo._farm.LeafResult(
        state="succeeded",
        exit_code=0,
        worker_id="w@1",
        attempt=1,
        cache_present=True,
        log_blob=None,
        failure_category=None,
        failure_message=None,
    )
    monkeypatch.setattr(dodo._telemetry, "span", record_span)
    monkeypatch.setattr(dodo, "_cache_key", lambda file_deps, label: key)
    monkeypatch.setattr(dodo._cache, "restore", lambda *args: next(restores))
    monkeypatch.setattr(dodo._farm, "enabled", lambda: True)
    monkeypatch.setattr(dodo._farm, "checkout_drift", lambda task_inputs=None: None)
    monkeypatch.setattr(dodo._farm, "run_leaf", lambda label, k: succeeded)

    dodo._cached_com_action("part:x", ["build"], [], [], "part-x")

    tagged = {name.split()[0]: attrs.get("cache.key") for name, attrs in spans}
    assert tagged == {"cache.probe": key[:12], "cache.restore": key[:12]}


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
    DO carry real gate edges -- asserted separately below.)

    ``verify:soundness`` and ``package:features`` are seat-free aggregators over
    their own COM leaves. Their explicit edges include those leaves in the
    packaged farm graph without serializing unrelated work."""
    dodo = _load_dodo()
    for t in dodo.task_part():
        assert not t.get("task_dep"), f"part:{t['name']} has a stray task_dep"
    for t in dodo.task_assembly():
        assert not t.get("task_dep"), f"assembly:{t['name']} has a stray task_dep"
    for t in dodo.task_verify_soundness():
        assert not t.get("task_dep"), (
            f"verify_soundness:{t['name']} has a stray task_dep"
        )
    for t in dodo.task_package():
        if t["name"].startswith("features:"):
            assert not t.get("task_dep"), f"package:{t['name']} has a stray task_dep"
    aggregated = {
        "soundness": [f"verify_soundness:{stem}" for stem in dodo.ASSEMBLY_ORDER]
    }
    for t in dodo.task_verify():
        assert t.get("task_dep", []) == aggregated.get(t["name"], []), (
            f"verify:{t['name']} carries an unexpected task_dep"
        )
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


def test_assembly_artefact_digest_folds_in_refs():
    """An assembly's stable digest folds its own recipe together with each referenced
    artefact's digest, recursively -- so a leaf-part input change propagates up to
    every ancestor (correct invalidation) while pure save-churn of an unchanged part
    does not (idempotency)."""
    dodo = _load_dodo()
    asm = "fr_frame"
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
    orphan = tmp_path / "ch-vn-channel-spring-installed-stretch07.SLDPRT"
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

    # Face width is floor(SEAT_PITCH * 1e4) / 1e4: SEAT_PITCH depends on DP
    # and nominal drum-seat length, hence gear_train + cone_incline. The stamped
    # contact-ratio screen needs the cone_drum_oblique_mesh group for edge slack
    # and journal float: c_deep=(N_cone*M + PD_drum)/2 + edge_slack, then
    # opening/runout; the drum tip band comes from the gear_tip group.
    # World station_z0 and active_count cancel; channels.yaml remains unread.
    cone = dodo._config_deps(scripts / "build_dt_cone_gear.py", "dt_cone_gear", "part")
    assert _rel(cone, cfg) == {
        "machine/gear_train.yaml",
        "machine/cone_incline.yaml",
        "tolerances/cone_drum_oblique_mesh.yaml",
        "tolerances/gear_tip.yaml",
        "parts/dt-cone-gear.yaml",
        # cone_set_stack reads the drum and arbor specs, whose sheet unit
        # (#290 drawing_unit) lives on their own registry rows.
        "parts/dt-cylinder-gear.yaml",
        "parts/dt-cylinder-gear-shaft.yaml",
        "parts/_defaults.yaml",
        "title_block.yaml",
        "release.yaml",
    }, _rel(cone, cfg)
    cylinder = dodo._config_deps(
        scripts / "build_dt_cylinder_gear.py", "dt_cylinder_gear", "part"
    )
    assert "machine/gear_train.yaml" in _rel(cylinder, cfg)
    assert set(cone) <= whole

    # Editing ONE part's registry row rebuilds only that part: a leaf screw depends
    # on its own row + shared defaults + title_block.yaml + release.yaml, nothing
    # else.
    screw = dodo._config_deps(
        scripts / "build_sh_vn_brass_fillister_screw.py",
        "sh_vn_brass_fillister_screw",
        "part",
    )
    assert _rel(screw, cfg) == {
        "parts/sh-vn-brass-fillister-screw.yaml",
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
    frame_recipe = _rel(dodo._recipe_files("fr_frame"), cfg)
    # #290 transition: a spec/geometry module the frame imports reads its own
    # registry row (and with it the shared defaults) for its sheet's
    # drawing_unit (UNIT); only those rows may appear.  Cutover removes the
    # switch and this allowance.
    drawing_unit_rows = {"parts/dt-pinion-pivot-block.yaml", "parts/_defaults.yaml"}
    assert not any(
        t.startswith("parts/") and t not in drawing_unit_rows for t in frame_recipe
    ), frame_recipe
    assert "dimensions.yaml" not in frame_recipe
    # Assembly title stamping is a separate contract: every released assembly
    # drawing owns TOL_* properties and therefore tracks title_block.yaml, but
    # that must not imply ownership of part-registry rows or the part template.
    # Tolerance fit classes stay out of frame.
    assert not any(path.startswith("tolerances/") for path in frame_recipe), frame_recipe
    assert "title_block.yaml" in frame_recipe, frame_recipe
    assert "release.yaml" in frame_recipe, frame_recipe
    channel_recipe = _rel(dodo._recipe_files("ch_channel"), cfg)
    assert "parts/ch-vn-channel-spring-installed.yaml" in channel_recipe, channel_recipe
    assert "release.yaml" in channel_recipe, channel_recipe
    assert "title_block.yaml" in channel_recipe, channel_recipe
    # The part TEMPLATE narrows identically: channel GENERATES its stretch
    # springs in-script via NewPart (which instantiates the template), so the
    # PRTDOT is a direct recipe member -- a template edit must FULL-rebuild the
    # generated variants and shift channel's cache key. A non-generating
    # assembly (frame) gets the template only transitively (re-stamped parts ->
    # shifted artefact digests -> REFRESH), never as a direct member.
    channel_names = {Path(p).name.lower() for p in dodo._recipe_files("ch_channel")}
    frame_names = {Path(p).name.lower() for p in dodo._recipe_files("fr_frame")}
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
        if stem == "ch_channel":
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
    drive = _rel(dodo._recipe_files("dt_drive_train"), cfg)
    frame = _rel(dodo._recipe_files("fr_frame"), cfg)
    assert "machine/channels.yaml" in drive, drive
    assert "machine/channels.yaml" not in frame, (
        "frame must not FULL on an active_count edit"
    )
    frame_modules = {Path(path).name for path in dodo._recipe_files("fr_frame")}
    assert "dt_post_mount_stack.py" in frame_modules, frame_modules
    assert not frame_modules & {
        "dt_vn_post_mount_screw_spec.py",
        "dt_cone_swing_platform_spec.py",
        "cone_line.py",
    }, frame_modules


def test_shared_post_mount_interference_depth_matches_the_part():
    """The universal exception needs penetration, not the cone's world pose.

    Keep its import-free nominal law tied to the physical owners, including
    the cut-length rounding; a second pinned engagement could drift silently.
    """
    import dt_post_mount_stack as stack
    import _cone_axis_constants as axis
    import dt_cone_pivot_post_spec as post
    import dt_cone_swing_platform_spec as platform
    import dt_vn_post_mount_screw_spec as screw

    assert stack.POST_BODY_HEIGHT_MM == post.BLOCK_HEIGHT
    assert stack.POST_MOUNT_COUNTERBORE_DEPTH_MM == post.ATTACHMENT_CBORE_DEPTH
    assert axis.PLATFORM_THICKNESS_MM == platform.PLATE_THICKNESS
    assert stack.CUT_TO_FIT_SHORT_MM == platform.POST_SCREW_CUT_TO_FIT_SHORT
    assert stack.CUT_LENGTH_PLACES == screw.DRAWING_PRECISION_BY_NAME["CutLength"]
    assert stack.GRIP_MM == screw.GRIP_MM
    assert stack.CUT_LENGTH_MM == screw.CUT_LENGTH_MM
    assert stack.POST_SCREW_ENGAGEMENT_NOMINAL == screw.ENGAGEMENT_NOMINAL_MM


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


def test_deleting_a_submodule_source_reruns_check_recipe(tmp_path):
    """check:recipe runs the adapter contract against the vendored package, so a
    submodule bump must re-run it. file_dep catches an edited or added module,
    but a DELETED one just leaves the dep list -- doit never compares it -- so
    the gate also carries the manifest of source paths (codex #1101)."""
    dodo = _load_dodo()
    src = _redirect_submodule(dodo, tmp_path)
    (src / "adapter.py").write_text("A = 1\n")
    (src / "headers.py").write_text("H = 1\n")

    def recipe_is_current(saved: dict) -> tuple[bool, dict]:
        task = next(t for t in dodo.task_check() if t["name"] == "recipe")
        (checker,) = task["uptodate"]
        current = checker(None, saved)
        return current, {"_config_changed": checker.config_digest}

    _, saved = recipe_is_current({})
    assert recipe_is_current(saved)[0], "an unchanged tree must stay up to date"

    (src / "headers.py").unlink()
    assert not recipe_is_current(saved)[0], "a deleted source must re-run the gate"


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
    the pn-pen.SLDASM recipe digest.)"""
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


def test_recipe_gate_enrolls_component_pattern_contract_once():
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    contract = dodo.SCRIPTS_DIR / "test_component_patterns.py"
    relative = str(contract.resolve().relative_to(dodo.REPO_ROOT.resolve()))
    assert recipe["actions"][0][1][0].count(relative) == 1
    assert recipe["file_dep"].count(str(contract)) == 1
    assert str(dodo.SCRIPTS_DIR / "_assembly_patterns.py") in recipe["file_dep"]


def test_recipe_gate_tracks_sources_imported_by_its_tests():
    """Editing code exercised by the drawing tests must stale the
    ``check:recipe`` stamp even when the test files themselves are unchanged."""
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    deps = {Path(path).name for path in recipe["file_dep"]}
    assert {
        "_holes.py",
        "build_pd_platen_guide.py",
        "identity-migration-map.json",
        "current-identity-map.json",
    } <= deps
    assert {
        str(template.path.resolve()) for template in dodo.DRAWING_TEMPLATES.values()
    } <= set(recipe["file_dep"])
    pytest_command = recipe["actions"][0][1][0]
    assert {
        "test_drawing_marks.py",
        "test_cone_drawing_batch_contract.py",
        "test_fastener_catalog.py",
        "test_grouped_bom_properties.py",
        "test_ch_vn_arbor_set_screw.py",
        "test_dt_vn_fillister_screw.py",
        "test_mg_vn_clamp_screw.py",
        "test_mg_vn_thumb_screw.py",
        "test_drawing_specification_purity.py",
        "test_drawing_surface_finish_validation.py",
        "test_gtol_contracts.py",
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


def test_recipe_gate_tracks_machinist_prompt_and_schema_contract() -> None:
    """Runtime-read review inputs must invalidate the offline contract stamp."""
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    prompt_dir = (dodo.SCRIPTS_DIR / "prompts").resolve()
    expected = {
        str((dodo.SCRIPTS_DIR.parent / "docs" / "drawing-guidelines.md").resolve()),
        str(prompt_dir / "machinist_review_part.md"),
        str(prompt_dir / "machinist_review_assembly.md"),
        str(prompt_dir / "machinist_review_schema.json"),
    }
    assert expected <= set(recipe["file_dep"])


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


def test_modal_dialog_exit_code_is_a_solidworks_failure():
    # exit 88 (_watchdog.EXIT_MODAL_DIALOG) must take the kill + relaunch + retry
    # path like a crash, not raise as an ordinary gate failure.
    dodo = _load_dodo()
    assert {86, 87, 88} <= set(dodo._WATCHDOG_EXIT_CODES)


def test_sw_preflight_restarts_only_past_the_commit_budget(monkeypatch):
    dodo = _load_dodo()
    calls: list[str] = []
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: calls.append("recover") or "connected",
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "wait_until_ready",
        lambda: calls.append("wait") or "connected",
    )
    monkeypatch.setenv("HARMONIC_SW_MAX_COMMIT_GB", "40")

    monkeypatch.setattr(dodo, "_sw_commit_gb", lambda: 12.5)
    dodo._sw_preflight()
    assert calls == []

    monkeypatch.setattr(dodo, "_sw_commit_gb", lambda: 66.3)  # the 2026-09-02 seat
    dodo._sw_preflight()
    assert calls == ["recover"]

    monkeypatch.setattr(
        dodo, "_sw_commit_gb", lambda: None
    )  # not running / probe glitch
    dodo._sw_preflight()
    assert calls == ["recover"]

    monkeypatch.setattr(dodo, "_sw_commit_gb", lambda: 66.3)
    monkeypatch.setenv("HARMONIC_SW_MAX_COMMIT_GB", "0")  # disabled
    dodo._sw_preflight()
    assert calls == ["recover"]


def test_sw_preflight_waits_out_a_slow_cold_start(monkeypatch):
    dodo = _load_dodo()
    calls: list[str] = []
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "force_recover",
        lambda: calls.append("recover") or "starting",
    )
    monkeypatch.setattr(
        dodo._sw_lifecycle,
        "wait_until_ready",
        lambda: calls.append("wait") or "connected",
    )
    monkeypatch.setenv("HARMONIC_SW_MAX_COMMIT_GB", "40")
    monkeypatch.setattr(dodo, "_sw_commit_gb", lambda: 66.3)
    dodo._sw_preflight()
    assert calls == ["recover", "wait"]


def test_sw_preflight_budget_rejects_non_finite_overrides(monkeypatch):
    dodo = _load_dodo()
    for raw in ("nan", "inf", "-inf", "banana"):
        monkeypatch.setenv("HARMONIC_SW_MAX_COMMIT_GB", raw)
        assert dodo._sw_max_commit_gb() == dodo._SW_MAX_COMMIT_GB_DEFAULT, raw
    monkeypatch.setenv("HARMONIC_SW_MAX_COMMIT_GB", "12.5")
    assert dodo._sw_max_commit_gb() == 12.5


def test_export_cache_ships_every_file_it_certifies():
    """The export cache entry must cover the whole release-neutral inventory.

    `release-neutral.json` records a sha256 + byte count per bundle file and
    `cut_release` refuses to stage a file whose bytes moved, so any inventory
    member missing from the cache payload means a farm-run export certifies bytes
    the submitter never receives -- it keeps its own older, recipe-equivalent copy,
    and the release dies at staging (v36: `alignment-pinion_isometric.png`).
    Renders are the sharp case: they are not reproducible across seats.
    """
    dodo = _load_dodo()
    sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
    import export_models

    parts = export_models.part_stems()
    assemblies = list(export_models.ASSEMBLY_ORDER)
    # Scene meshes come from built boxes JSONs; the per-config STLs they add live in
    # cad/out/stl, already covered by the part entries below, so an empty scene map
    # keeps this test independent of whether anything is built.
    inventory = export_models._release_inventory(parts, assemblies, {}, set(assemblies))
    covered = [p.resolve() for p in dodo._export_cache_outputs()]

    uncovered = sorted(
        destination for destination, source in inventory.items()
        if not any(
            source.resolve() == entry or entry in source.resolve().parents
            for entry in covered
        )
    )
    assert not uncovered, (
        f"{len(uncovered)} certified release file(s) are not in the export cache "
        f"payload: {uncovered[:5]}"
    )


def test_title_block_geometry_readers_keep_the_title_block_without_stamping(
    monkeypatch,
) -> None:
    # Codex #854 review (Main): pinion_rig_layout sizes the torque shaft and the
    # lift rod from the title block's printed rows (_printed_tolerance), so a
    # row edit moves drive-train placements.  The title_block token must
    # survive for such an assembly even if it stopped stamping; only a
    # stamp-free assembly that reads no geometry from it drops the token.
    import _buildgraph

    dodo = _load_dodo()
    drive_train = dodo.script_for("dt_drive_train")
    channel = dodo.script_for("ch_channel")
    assert _buildgraph.reads_title_block_geometry(drive_train)
    monkeypatch.setattr(dodo, "stamps_title_block_properties", lambda _script: False)
    assert dodo._expand_title_block_token("assembly", drive_train)
    # Every assembly reaches a geometry reader today, so a stamp-free, geometry-
    # free one is simulated to prove the drop branch.
    monkeypatch.setattr(dodo, "reads_title_block_geometry", lambda _script: False)
    assert dodo._expand_title_block_token("assembly", channel) == []


def test_check_pytest_commands_disable_the_shared_cache():
    """Parallel offline gates must not create root-level cache temp directories."""
    dodo = _load_dodo()
    pytest_gates = {}
    for task in dodo.task_check():
        if task["actions"][0][0] is not dodo._run_stamped:
            continue
        command = task["actions"][0][1][0]
        if command[1:3] == ["-m", "pytest"]:
            pytest_gates[task["name"]] = command
    assert {"graph", "numerals", "recipe"} <= pytest_gates.keys()
    for name, command in pytest_gates.items():
        assert command[4:6] == ["-p", "no:cacheprovider"], (
            f"check:{name} shares pytest's atomic cache-directory rename"
        )


def test_check_gates_depend_on_everything_they_execute():
    """Every ``check:*`` stamp must go stale when code or config it EXECUTES
    changes, or the gate reports green without running.

    For each gate, the entry points are the ``.py`` arguments of its command
    (``verify.py`` for math/config, the pytest files otherwise). Their local
    import closure (``module_deps_of``, which follows lazy function-local
    imports too) and the config files that closure reads (``_config_deps``,
    conservative whole-config on any unclassified use) must all be declared
    ``file_dep``s. ``check:math`` missed ``build_sm_summing_assembly.py`` and
    ``sm_gooseneck_geom.py``: a gooseneck edit left the stamp green (2026-09-23),
    and only an unrelated config change later re-ran it -- red.

    Not covered by this derivation, so still hand-listed where a gate needs
    them: modules ``module_deps_of`` excludes by design (``_buildgraph``,
    ``_telemetry``, ``_watchdog``, ``test_*`` helpers), ``dodo.py`` itself
    (outside ``cad/scripts``, loaded via ``spec_from_file_location``), other
    ``importlib``/``runpy`` loads, and data files read at run time.
    """
    dodo = _load_dodo()
    gaps: dict[str, list[str]] = {}
    for task in dodo.task_check():
        if task["actions"][0][0] is dodo._cached_machinist_review_action:
            # This leaf's explicit PDF/name/kind path excludes registry lookup;
            # test_machinist_review_leaf pins its complete local-import closure
            # and runtime-read rubric/exception inputs separately.
            assert set(dodo._machinist_review_file_deps(
                task["name"].split(":", 1)[1]
            )) <= set(task["file_dep"])
            continue
        declared = {str(Path(dep).resolve()) for dep in task["file_dep"]}
        command = task["actions"][0][1][0]
        entries = [Path(arg) for arg in command if str(arg).endswith(".py")]
        assert entries, f"check:{task['name']} runs no .py entry point: {command}"
        executed = {
            path
            for entry in entries
            for path in (
                str(entry.resolve()),
                *dodo.module_deps_of(entry),
                *dodo._config_deps(entry),
            )
        }
        missing = sorted(executed - declared)
        if missing:
            gaps[task["name"]] = [
                str(Path(path).relative_to(REPO_ROOT)) for path in missing
            ]
    assert not gaps, "check:* gates execute undeclared inputs (stale-green): " + "; ".join(
        f"check:{name} misses {len(paths)}: {', '.join(paths)}"
        for name, paths in sorted(gaps.items())
    )


def test_fastener_catalog_dep_is_narrowed_to_the_rows_each_task_reads():
    """Catalogue readers carry only their rows; pure-dimension consumers carry
    no catalogue digest, and the build subprocess is told exactly the rows read."""
    dodo = _load_dodo()
    catalog = str(dodo._FASTENER_CATALOG)
    part = dodo._part_file_deps(
        dodo.SCRIPTS_DIR / "build_ch_vn_frame_side_screw.py", "ch_vn_frame_side_screw"
    )
    drawing = dodo._drawing_file_deps("ch_vn_frame_side_screw")
    assembly = dodo._recipe_files("pn_pen")
    for label, deps in (
        ("part-ch_vn_frame_side_screw", part),
        ("drawing-ch_vn_frame_side_screw", drawing),
    ):
        assert catalog not in deps, label
        assert any(
            Path(dep).name == f"{label}.digest"
            and Path(dep).parent.name == ".fastener-catalog"
            for dep in deps
        ), label
    assert dodo._fastener_rows_env("part:ch_vn_frame_side_screw") == "ch-vn-frame-side-screw"
    assert dodo._fastener_rows_env("drawing:ch_vn_frame_side_screw") == "ch-vn-frame-side-screw"
    # The pen reads the pure SKU dimensions, not the stock builder's catalogue row.
    assert catalog not in assembly
    assert not any(Path(dep).parent.name == ".fastener-catalog" for dep in assembly)
    assert dodo._fastener_rows_env("assembly:pn_pen") is None
    assert dodo._fastener_rows_env("check:math") is None


def test_run_subprocess_hands_the_fastener_rows_to_the_build(monkeypatch):
    dodo = _load_dodo()
    seen = {}

    def fake_run(cmd, cwd, env):
        seen.update(env)
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "inherited-must-not-leak")
    monkeypatch.setenv("HARMONIC_FIT_GROUPS", "inherited-must-not-leak")
    monkeypatch.setattr(dodo.subprocess, "run", fake_run)
    assert dodo._run_subprocess(["x"], "part:ch_vn_frame_side_screw") == 0
    assert seen["HARMONIC_FASTENER_ROWS"] == "ch-vn-frame-side-screw"
    assert seen["HARMONIC_FIT_GROUPS"] == dodo._fit_groups_env("part:ch_vn_frame_side_screw")
    seen.clear()
    assert dodo._run_subprocess(["x"], "check:math") == 0
    assert "HARMONIC_FASTENER_ROWS" not in seen
    assert "HARMONIC_FIT_GROUPS" not in seen
    seen.clear()
    assert dodo._run_subprocess(["x"], "package:features") == 0
    assert "HARMONIC_FASTENER_ROWS" not in seen
    assert "HARMONIC_FIT_GROUPS" not in seen


def test_fit_guard_uses_task_recipe_config_dependencies():
    dodo = _load_dodo()
    for task, deps in (
        (
            "part:dt_cone_gear",
            dodo._part_file_deps(
                dodo.SCRIPTS_DIR / "build_dt_cone_gear.py", "dt_cone_gear"
            ),
        ),
        ("assembly:dt_drive_train", dodo._recipe_files("dt_drive_train")),
        ("drawing:ch_vn_frame_side_screw", dodo._drawing_file_deps("ch_vn_frame_side_screw")),
        (
            "package:features:ch_rocker_arm",
            dodo._feature_export_file_deps("ch_rocker_arm"),
        ),
    ):
        groups = {
            Path(dep).stem for dep in deps
            if Path(dep).parent == (dodo.CONFIG_DIR / "tolerances").resolve()
            and Path(dep).stem != "_base"
        }
        assert dodo._fit_groups_env(task) == ",".join(sorted(groups))
    # The drive train and its crank pinion read these groups through literal
    # fit() calls; an empty guard here would refuse a real build. The inch
    # cone and drum tips read gear_tip; the crank gears sit on cone_line's
    # stations, so the pinion also reads the cone mesh's edge slack. The
    # train's stock-form transgear specs read stock_form_quality, and the
    # transgear knob shaft's 15T face width reads the disc cluster's printed
    # band (pd_cluster_stack, #2038).
    assert dodo._fit_groups_env("assembly:dt_drive_train") == (
        "cone_drum_oblique_mesh,crank_mesh,gear_tip,pd_cluster_stack,"
        "shaft_in_bushing,stock_form_quality"
    )
    assert dodo._fit_groups_env("part:dt_crank_pinion") == (
        "cone_drum_oblique_mesh,crank_mesh,gear_mesh,shaft_in_bushing"
    )
    assert dodo._fit_groups_env("check:config") is None
    assert dodo._fit_groups_env("package:features") is None
    assert dodo._fit_groups_env("features:ch_rocker_arm") is None
    with pytest.raises(ValueError, match="fit groups are unknown"):
        dodo._fit_groups_env("part:no_such_part")


@pytest.mark.parametrize("groups", [(), ("gear_mesh",)])
def test_feature_subprocess_refuses_fit_groups_outside_its_cache_key(
    monkeypatch, groups
):
    import _config

    dodo = _load_dodo()
    stems = []
    seen = {}

    def feature_deps(stem):
        stems.append(stem)
        return [
            str((dodo.CONFIG_DIR / "tolerances" / f"{group}.yaml").resolve())
            for group in ("_base", *groups)
        ]

    def fake_run(cmd, cwd, env):
        seen.update(env)
        # Apply only the child's fit guard, including its absence. Without the
        # package namespace fix this real group read succeeds, failing raises().
        with monkeypatch.context() as child:
            if "HARMONIC_FIT_GROUPS" in env:
                child.setenv("HARMONIC_FIT_GROUPS", env["HARMONIC_FIT_GROUPS"])
            else:
                child.delenv("HARMONIC_FIT_GROUPS", raising=False)
            _config.fit("crank_mesh")
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "inherited-must-not-leak")
    monkeypatch.setenv("HARMONIC_FIT_GROUPS", "inherited-must-not-leak")
    monkeypatch.setattr(dodo, "_feature_export_file_deps", feature_deps)
    monkeypatch.setattr(dodo.subprocess, "run", fake_run)
    with pytest.raises(
        KeyError, match="fit group 'crank_mesh' is outside this build's cache key"
    ):
        dodo._run_subprocess(["x"], "package:features:ch_rocker_arm")
    assert stems == ["ch_rocker_arm"]
    assert seen["HARMONIC_FIT_GROUPS"] == ",".join(groups)
    assert "HARMONIC_FASTENER_ROWS" not in seen
    assert os.environ["HARMONIC_FIT_GROUPS"] == "inherited-must-not-leak"


def test_fit_config_dependencies_expand_conservatively(tmp_path):
    dodo = _load_dodo()
    script = tmp_path / "fit_probe.py"
    script.write_text("import _config\nvalue = _config.fit('gear_mesh', 'backlash_mm')\n")
    assert dodo._config_deps(script) == [
        str((dodo.CONFIG_DIR / "tolerances" / "gear_mesh.yaml").resolve())
    ]
    script = tmp_path / "dynamic_fit_probe.py"
    script.write_text("import _config\nreader = _config.fit\nvalue = reader(group)\n")
    assert set(dodo._config_deps(script)) == set(dodo.tolerance_family_files())
    assert str((dodo.CONFIG_DIR / "tolerances" / "_base.yaml").resolve()) in dodo._config_deps(script)


def _assembly_subprocess_envs(dodo, monkeypatch, tmp_path, stem, *, mode):
    """Drive a local ``build_or_refresh(stem)`` miss through ``mode`` ("full" with
    one injected post-assembly hook, or "refresh") and return ``(label, env)`` for
    every subprocess it launched."""
    launched = []

    class FakePopen:
        def __init__(self, cmd, cwd, env, **_kw):
            launched.append((cmd, env))
            self.stdout = iter(())

        def wait(self):
            return 0

    @contextlib.contextmanager
    def free_seat(label):
        yield 0.0

    target = tmp_path / f"{stem}.SLDASM"
    ledger = tmp_path / f".{stem}.inputs.json"
    # Prime the task's rows from the real recipe, then stub the recipe so the
    # injected hook (no such file) is never read.
    dodo._fastener_rows_env(f"assembly:{stem}")
    deps = dodo._recipe_files(stem)
    if mode == "refresh":
        # Built from exactly the current recipe: only a reference could differ.
        target.write_bytes(b"asm")
        dodo._write_input_ledger(ledger, dodo._ledger_inputs(deps))
    monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: deps)
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda _stem: deps)
    monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dodo, "POST_ASSEMBLY", {stem: ("hook_probe.py",)})
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(dodo._cache, "restore", lambda *_a: False)
    monkeypatch.setattr(dodo._cache, "store", lambda *_a, **_kw: "stored")
    monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
    monkeypatch.setattr(dodo, "_com_seat", free_seat)
    monkeypatch.setattr(dodo, "_reprobe_under_seat", lambda *_a: False)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: False)
    monkeypatch.setattr(dodo, "_input_ledger", lambda _stem: ledger)
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda _stem: [])
    monkeypatch.setattr(dodo, "_stamp_assembly_execution", lambda _stem: None)
    monkeypatch.setattr(dodo.subprocess, "Popen", FakePopen)
    monkeypatch.setenv("HARMONIC_FASTENER_ROWS", "inherited-must-not-leak")
    monkeypatch.setenv("HARMONIC_FIT_GROUPS", "inherited-must-not-leak")

    dodo.build_or_refresh(stem, [], [], [str(target)])

    return [(Path(cmd[1]).name, env) for cmd, env in launched]


@pytest.mark.parametrize("mode", ["full", "refresh"])
def test_every_assembly_subprocess_is_guarded_by_its_rows(monkeypatch, tmp_path, mode):
    """Codex on #868: the FULL/REFRESH/hook subprocesses carry display labels, so
    keying the guard on the label dropped it for every assembly build. The guard
    is keyed on the doit task instead, whatever the display label says."""
    dodo = _load_dodo()
    # Exercise a narrowed assembly's guard plumbing on an assembly with no
    # explode-tier plan (the pen's explode qualifies since #1603, so its FULL
    # path first probes an explode base); the row is a stand-in.
    monkeypatch.setitem(
        dodo._FASTENER_ROWS, "assembly:ms_measuring_stick", frozenset({"pn-vn-pen-set-screw"})
    )
    fit_groups = dodo._fit_groups_env("assembly:ms_measuring_stick")
    launched = _assembly_subprocess_envs(
        dodo, monkeypatch, tmp_path, "ms_measuring_stick", mode=mode
    )

    scripts = [name for name, _env in launched]
    if mode == "full":
        assert scripts == ["build_ms_measuring_stick_assembly.py", "hook_probe.py"]
    else:
        assert scripts == ["refresh_assembly.py"]
    for name, env in launched:
        assert env.get("HARMONIC_FASTENER_ROWS") == "pn-vn-pen-set-screw", name
        assert env.get("HARMONIC_FIT_GROUPS") == fit_groups, name


PD_EXPLODE_SPEC = "cad/scripts/pd_paper_drive_explode_spec.py"


def _pd_clean_leaf(dodo, monkeypatch, tmp_path, *, base_inputs, refresh_rc=0):
    """Run ``build_or_refresh("pd_paper_drive")`` on a clean workspace whose full
    cache key misses. ``base_inputs`` is the ledger of the cached explode base,
    or None when the cache holds no base; ``refresh_rc`` is the exit code of
    ``refresh_assembly.py``. Returns ``(commands, restores, stores)`` as
    ``(script, args)`` and ``(key, label)`` rows."""
    launched, restores, stores = [], [], []

    class FakePopen:
        def __init__(self, cmd, cwd, env, **_kw):
            self.script = Path(cmd[1]).name
            launched.append((self.script, list(cmd[2:])))
            self.stdout = iter(())

        def wait(self):
            return refresh_rc if self.script == "refresh_assembly.py" else 0

    @contextlib.contextmanager
    def free_seat(label):
        yield 0.0

    target = tmp_path / "pd-paper-drive.SLDASM"
    ledger = tmp_path / ".pd-paper-drive.inputs.json"

    def restore(key, _outputs, label):
        restores.append((key, label))
        if base_inputs is None or not label.endswith("explode-base"):
            return False
        target.write_bytes(b"base")
        (tmp_path / ".pd-paper-drive.massprops.sha").write_text("proof\n", encoding="utf-8")
        dodo._write_input_ledger(ledger, base_inputs)
        return True

    deps = dodo._recipe_files("pd_paper_drive")
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda _stem: deps)
    monkeypatch.setattr(dodo, "_input_ledger", lambda _stem: ledger)
    monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(
        dodo._cache,
        "store",
        lambda key, _o, label, **_kw: stores.append((key, label)) or "stored",
    )
    monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
    monkeypatch.setattr(dodo, "_com_seat", free_seat)
    monkeypatch.setattr(dodo, "_reprobe_under_seat", lambda *_a: False)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_sw_autostart_enabled", lambda: False)
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda _stem: [])
    monkeypatch.setattr(dodo, "_stamp_assembly_execution", lambda _stem: None)
    monkeypatch.setattr(dodo.subprocess, "Popen", FakePopen)

    dodo.build_or_refresh("pd_paper_drive", [], [], [str(target)])

    assert dodo._read_input_ledger(ledger) == dodo._ledger_inputs(deps)
    return launched, restores, stores


def test_clean_leaf_with_an_explode_base_takes_the_explode_tier(monkeypatch, tmp_path):
    dodo = _load_dodo()
    current = dodo._ledger_inputs(dodo._recipe_files("pd_paper_drive"))
    assert PD_EXPLODE_SPEC in current
    base = {**current, PD_EXPLODE_SPEC: "0" * 32}

    launched, restores, stores = _pd_clean_leaf(
        dodo, monkeypatch, tmp_path, base_inputs=base
    )

    assert launched == [("refresh_assembly.py", ["pd_paper_drive", "explode"])]
    assert [label for _key, label in restores] == [
        "assembly:pd_paper_drive",
        "assembly:pd_paper_drive explode-base",
    ]
    # The base it started from is already cached; only the full key is new.
    assert stores == [restores[0]]


def test_failed_explode_tier_falls_back_to_full_in_the_same_task(monkeypatch, tmp_path):
    """A pre-save EXPLODE failure leaves the base's bytes, proof and ledger as
    they were, so the next leaf restoring that base would pick EXPLODE and fail
    the same way again (coderabbit on #1575). The task builds FULL instead."""
    dodo = _load_dodo()
    current = dodo._ledger_inputs(dodo._recipe_files("pd_paper_drive"))
    base = {**current, PD_EXPLODE_SPEC: "0" * 32}

    launched, restores, stores = _pd_clean_leaf(
        dodo, monkeypatch, tmp_path, base_inputs=base, refresh_rc=1
    )

    assert launched == [
        ("refresh_assembly.py", ["pd_paper_drive", "explode"]),
        ("build_pd_paper_drive_assembly.py", []),
    ]
    # The FULL result is a fresh base for this operational model: publish both.
    assert stores == restores


def test_clean_leaf_without_a_base_builds_full_and_publishes_the_base(
    monkeypatch, tmp_path
):
    dodo = _load_dodo()

    launched, restores, stores = _pd_clean_leaf(
        dodo, monkeypatch, tmp_path, base_inputs=None
    )

    assert launched == [("build_pd_paper_drive_assembly.py", [])]
    assert stores == restores
    assert stores[0][0] != stores[1][0]


def test_explode_base_key_ignores_only_the_explode_closure(monkeypatch):
    dodo = _load_dodo()
    deps = dodo._recipe_files("pd_paper_drive")
    plan = dodo.explode_plan("pd_paper_drive")
    digest = dodo.ContentChecker._digest
    keys = {}
    for edited in (
        None,
        PD_EXPLODE_SPEC,
        "cad/scripts/build_pd_paper_drive_assembly.py",
    ):
        monkeypatch.setattr(
            dodo.ContentChecker,
            "_digest",
            staticmethod(
                lambda path, edited=edited: "edited"
                if edited and dodo._rel_tag(path) == edited
                else digest(path)
            ),
        )
        keys[edited] = (dodo._cache_key(deps), dodo._explode_base_key(deps, plan))
    full, base = keys[None]
    assert keys[PD_EXPLODE_SPEC][0] != full and keys[PD_EXPLODE_SPEC][1] == base
    builder = keys["cad/scripts/build_pd_paper_drive_assembly.py"]
    assert builder[0] != full and builder[1] != base


@pytest.mark.parametrize(
    "label",
    [
        "FULL build channel (target missing)",
        "REFRESH channel",
        "hook hook_probe.py",
        "check math",
        "release documents part:ch_vn_frame_side_screw",
        "part:no_such_part",
        "assembly:no_such_assembly",
        "drawing:no_such_drawing",
        "",
    ],
)
def test_fastener_rows_refuse_a_label_that_names_no_task(label):
    """Silently mapping a display label to "no rows" is what dropped the guard; a
    label that is not a task (or names a task that does not exist) fails loud."""
    dodo = _load_dodo()
    with pytest.raises(ValueError):
        dodo._fastener_rows_env(label)


def test_fastener_rows_leave_unnarrowed_tasks_unguarded():
    dodo = _load_dodo()
    assert dodo._fastener_rows_env("check:math") is None
    assert dodo._fastener_rows_env("release") is None
    assert dodo._fastener_rows_env("verify:kinematics") is None


def test_every_subprocess_launch_names_a_task_the_guard_can_map():
    """Every task action that launches a subprocess under a display label passes
    its doit task, so none can reach the guard's refusal at run time."""
    dodo = _load_dodo()
    for task in dodo.task_check():
        for action, args in task["actions"]:
            if action is dodo._run_stamped:
                dodo._fastener_rows_env(args[3])  # raises on an unmappable task


def test_every_title_block_reader_is_classified() -> None:
    # Main (restricted review of #854): the title_block token survives for a
    # stamp-free assembly only through TITLE_BLOCK_GEOMETRY_MODULES, so a module
    # that reads the printed rows for geometry and is missing from it would
    # silently drop title_block.yaml from an assembly recipe.  Every module that
    # calls the accessor is either one of the TOL_* stampers, a drawing script
    # (drawing tasks always keep the token), or a geometry reader in the set.
    import _buildgraph

    # The accessor, the TOL_* stampers and the TOL_* text they stamp.
    stampers = {"_config", "_part_properties", "_assembly", "_title_block_units"}
    readers = {
        path.stem
        for path in (REPO_ROOT / "cad" / "scripts").glob("*.py")
        if not path.stem.startswith(("test_", "draw_"))
        and re.search(r"\btitle_block\(", path.read_text(encoding="utf-8"))
    }
    unclassified = sorted(readers - stampers - _buildgraph.TITLE_BLOCK_GEOMETRY_MODULES)
    assert not unclassified, (
        "modules read _config.title_block but are not in "
        f"TITLE_BLOCK_GEOMETRY_MODULES: {unclassified}"
    )
    stale = sorted(_buildgraph.TITLE_BLOCK_GEOMETRY_MODULES - readers)
    assert not stale, f"TITLE_BLOCK_GEOMETRY_MODULES names non-readers: {stale}"


def test_every_python_action_passes_doits_argument_rules():
    """doit refuses, at run time, a python action whose callable declares one of
    its reserved names (``task``, ``targets``, ``dependencies``, ``changed``) with a
    default.  ``gallery`` passed ``_run`` straight through after ``_run`` gained a
    keyword-only ``task=None``, and the break surfaced only inside ``release``,
    the one command that runs ``gallery`` (v37, 2026-09-27).  Prepare every
    action's arguments through doit's own code so the whole graph is checked
    offline, not just the tasks a build happens to execute."""
    from doit.action import PythonAction
    from doit.loader import load_tasks

    dodo = _load_dodo()
    tasks = load_tasks(dict(vars(dodo)), allow_delayed=True)
    assert any(task.name == "gallery" for task in tasks)
    refused = []
    for task in tasks:
        # doit fills these just before it executes a task.
        task.init_options()
        task.dep_changed = []
        for action in task.actions:
            if not isinstance(action, PythonAction):
                continue
            action.task = task
            try:
                action._prepare_kwargs()
            except Exception as problem:  # doit raises InvalidTask
                refused.append(f"{task.name}: {problem}")
    assert not refused, "\n".join(refused)



@pytest.fixture
def isolated_export_keys(tmp_path, monkeypatch):
    """Use discovered export dependencies, but mutate only their isolated copies."""
    import export_models

    dodo = _load_dodo()
    monkeypatch.setattr(dodo, "_cad_identity_deps", lambda: [])
    deps = dodo._export_requirement_deps()
    root = tmp_path / "repo"
    copied = []
    for source in deps:
        original = Path(source)
        destination = root / original.relative_to(REPO_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original.read_bytes())
        copied.append(str(destination))
    monkeypatch.setattr(dodo._cache, "REPO_ROOT", root)
    monkeypatch.setattr(dodo, "_export_requirement_deps", lambda: copied)
    bundles = []
    for source in dodo._feature_bundle_outputs():
        destination = root / source.relative_to(REPO_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"produced feature bundle input\n")
        bundles.append(destination)
    monkeypatch.setattr(dodo, "_feature_bundle_outputs", lambda: bundles)
    monkeypatch.setattr(export_models, "_import_dodo", lambda: dodo)
    monkeypatch.setattr(export_models, "__file__", str(root / "cad/scripts/export_models.py"))

    def snapshot():
        return (
            dodo._cache_key(dodo._export_file_deps(), "export"),
            export_models._exporter_digest(),
        )

    return root, snapshot


@pytest.mark.parametrize(
    "source",
    [
        "export_features.py", "features_bound.py", "_export_feature_faces.py",
        "_gtol_face_read.py", "_gtol_face.py",
    ],
)
def test_export_runtime_inputs_invalidate_outer_key_and_internal_ledger(
    isolated_export_keys, source,
):
    root, snapshot = isolated_export_keys
    before = snapshot()
    member = root / "cad/scripts" / source
    with member.open("a", encoding="utf-8") as stream:
        stream.write("\nFEATURE_EXPORT_INPUT_REVISION = 2\n")

    after = snapshot()

    assert after[0] != before[0], source
    assert after[1] != before[1], source


@pytest.mark.parametrize("member", ["features.toml", "ch-rocker-arm.STEP"])
def test_produced_bundle_edits_rekey_full_export_without_invalidating_native_ledger(
    isolated_export_keys, member,
):
    root, snapshot = isolated_export_keys
    before = snapshot()
    source = root / "cad/out/features/ch_rocker_arm" / member
    source.write_bytes(source.read_bytes() + b"bundle revision\n")
    after = snapshot()
    assert after[0] != before[0]
    assert after[1] == before[1]


@pytest.mark.parametrize("source", [
    "draw_ch_rocker_arm.py", "draw_ch_rocker_arm_tl_oblique_carrier.py",
    "_drawing_layout_audit.py", "_pdf_ink.py",
])
def test_draw_source_edits_do_not_rekey_full_export_before_producing_bundles(
    isolated_export_keys, source,
):
    root, snapshot = isolated_export_keys
    member = root / "cad/scripts" / source
    assert not member.exists(), "full export must not fold drawing/declaration closures"
    member.write_bytes(b"DRAWING_REVISION = 1\n")
    before = snapshot()
    member.write_bytes(b"DRAWING_REVISION = 2\n")
    assert snapshot() == before


def test_feature_cache_and_status_share_the_parsed_yaml_key(tmp_path, monkeypatch):
    dodo = _load_dodo()
    source = tmp_path / "drawing.yaml"
    source.write_text("diameter: 6.5\n", encoding="utf-8")
    deps = [str(source)]
    label = "package:features:ch_rocker_arm"
    probes = []
    messages = []
    monkeypatch.setattr(dodo, "_cache_rows", lambda: [(label, deps)])
    monkeypatch.setattr(dodo._cache, "probe", lambda key: (probes.append(key), False)[1])
    monkeypatch.setattr(dodo._cache, "last_stored_key", lambda _label: None)
    for level in ("info", "warn", "success", "debug"):
        monkeypatch.setattr(dodo._telemetry, level, messages.append)

    before = dodo._cache_key(deps, label)
    dodo._cache_status([label])
    source.write_text("# Authored value unchanged.\ndiameter: 6.500\n", encoding="utf-8")
    unchanged = dodo._cache_key(deps, label)
    dodo._cache_status([label])
    source.write_text("diameter: 6.6\n", encoding="utf-8")
    changed = dodo._cache_key(deps, label)
    dodo._cache_status([label])

    assert unchanged == before
    assert changed != before
    assert probes == [before, unchanged, changed]
    assert f"MISS {before[:12]}  {label}" in messages
    assert f"MISS {changed[:12]}  {label}" in messages


@pytest.fixture
def synthetic_prechips_task(tmp_path, monkeypatch):
    import _process_plans
    import export_features

    dodo = _load_dodo()
    stem = "ch_rocker_arm"
    root = tmp_path / "process"
    source = root / stem / "plan.toml"
    source.parent.mkdir(parents=True)
    source.write_text('features = "unused"\n')
    shop = root / "shop"
    shop.mkdir()
    for name in _process_plans.SHOP_FILES:
        (shop / name).write_text("version = 1\n")
    (shop / "inventory.toml").write_text(
        '[fixtures.test]\ncad = "ch_rocker_arm_tl_oblique_carrier"\n'
    )
    monkeypatch.setattr(_process_plans, "PROCESS_ROOT", root)
    monkeypatch.setattr(_process_plans, "TRAVELER_STEMS", (stem,))
    spec = dodo.SCRIPTS_DIR / "ch_rocker_arm_tl_oblique_carrier_spec.py"
    helper = dodo.SCRIPTS_DIR / "_synthetic_fixture_dimensions.py"
    original = dodo._executed_closure

    def closure(command):
        if command == [str(spec)]:
            return [str(spec), str(helper)]
        return original(command)

    monkeypatch.setattr(dodo, "_executed_closure", closure)
    return dodo, _process_plans, export_features, stem, source, spec, helper


@pytest.fixture
def synthetic_prechips_kernel(tmp_path, monkeypatch):
    """Model discovery and --version without importing or launching FreeCAD."""
    import subprocess

    state = {
        "path": tmp_path / "FreeCAD 1.1" / "freecadcmd.exe",
        "version": "FreeCAD 1.1.0\n",
        "error": None,
        "discoveries": 0,
        "queries": [],
    }
    kernel = ModuleType("prechips.kernel")

    def discover_kernel():
        state["discoveries"] += 1
        return state["path"]

    original = subprocess.check_output

    def version(command, **kwargs):
        if command[-1] != "--version":
            return original(command, **kwargs)
        assert command == [str(Path(state["path"]).resolve()), "--version"]
        assert kwargs["text"] is True
        state["queries"].append(command)
        if state["error"] is not None:
            raise state["error"]
        return state["version"]

    kernel.discover_kernel = discover_kernel
    monkeypatch.setitem(sys.modules, "prechips.kernel", kernel)
    monkeypatch.setattr(subprocess, "check_output", version)
    return state


def test_prechips_task_shape_and_complete_dependency_closure(synthetic_prechips_task):
    dodo, plans, exporter, stem, source, spec, helper = synthetic_prechips_task
    task = next(dodo.task_prechips())
    assert task["name"] == stem
    assert task["task_dep"] == [f"package:features:{stem}"]
    deps = {str(path) for path in task["file_dep"]}
    expected = {
        str(source), *(str(path) for path in plans.shop_paths()),
        str(spec), str(helper), str(dodo.REPO_ROOT / "pyproject.toml"),
        str(dodo.REPO_ROOT / "uv.lock"), str(dodo.REPO_ROOT / "dodo.py"),
        str(dodo.SCRIPTS_DIR / "_telemetry.py"),
        *(str(path) for path in exporter.bundle_paths(stem)),
    }
    assert expected <= deps
    assert str(dodo.SCRIPTS_DIR / "prechips_traveler.py") in deps
    assert str(dodo.SCRIPTS_DIR / "_process_plans.py") in deps
    directory = plans.traveler_dir(stem, dodo.CAD_OUT)
    targets = {str(path) for path in task["targets"]}
    assert {
        str(directory / "plan.toml"), str(directory / "report.json"),
        str(directory / "traveler.html"),
        str(dodo.CAD_OUT / "reports" / f"prechips-{stem}.ok"),
    } <= targets
    assert (plans.traveler_complete, [stem, dodo.CAD_OUT]) in task["uptodate"]
    assert any(
        isinstance(check, dodo._PrechipsKernelTracker) for check in task["uptodate"]
    )
    action, args = task["actions"][0]
    assert action is dodo._run_stamped
    assert args[3] == f"prechips:{stem}"
    assert "prechips_traveler.py" in " ".join(map(str, args[0]))
    assert stem in args[0]


def test_prechips_build_release_edges_and_stage(synthetic_prechips_task):
    dodo, _, _, stem, _, _, _ = synthetic_prechips_task
    for task in (dodo.task_build(), dodo.task_release()):
        assert f"prechips:{stem}" in task["task_dep"]
    assert dodo._stage_name(f"prechips:{stem}") == "prechips-traveler"
    assert not any(name.startswith("traveler_") for name in dodo._CHECK_NAMES)
    assert not any(task["name"].startswith("traveler_") for task in dodo.task_check())


@pytest.mark.parametrize("consumer", ["traveler", "export"])
def test_feature_failure_blocks_full_export_but_not_another_traveler(
    synthetic_prechips_task, consumer,
):
    from doit.control import TaskControl
    from doit.loader import load_tasks

    dodo, _, exporter, stem, _, _, _ = synthetic_prechips_task
    failing = next(part for part in exporter.SUPPORTED_PARTS if part != stem)
    selected = f"prechips:{stem}" if consumer == "traveler" else "export"
    control = TaskControl(load_tasks(dict(vars(dodo)), allow_delayed=True))
    control.process([selected])
    dispatcher = control.task_dispatcher()
    scheduled = {}
    processed = None
    while True:
        try:
            node = dispatcher.generator.send(processed)
        except StopIteration:
            break
        assert not isinstance(node, str), "all dispatched tasks receive a completion"
        # No task action executes: model one failed feature leaf in doit's real
        # scheduler, and propagate its failure through consumer dependency nodes.
        node.run_status = (
            "failure" if node.task.name == f"package:features:{failing}" or node.bad_deps
            else "done"
        )
        scheduled[node.task.name] = node.run_status
        processed = node
    feature_leaves = {
        name for name in scheduled if name.startswith("package:features:")
    }
    if consumer == "traveler":
        assert feature_leaves == {f"package:features:{stem}"}
        assert scheduled[selected] == "done"
    else:
        assert feature_leaves == {
            f"package:features:{part}" for part in exporter.SUPPORTED_PARTS
        }
        assert scheduled[selected] == "failure"


def test_prechips_kernel_discovery_is_lazy_at_task_load(
    synthetic_prechips_task, synthetic_prechips_kernel,
):
    from doit.loader import load_tasks

    dodo, _, _, stem, _, _, _ = synthetic_prechips_task
    loaded = load_tasks(dict(vars(dodo)), allow_delayed=True)
    assert f"prechips:{stem}" in {task.name for task in loaded}
    assert synthetic_prechips_kernel["discoveries"] == 0
    assert synthetic_prechips_kernel["queries"] == []


@pytest.mark.parametrize("changed", ["path", "version"])
def test_prechips_kernel_change_invalidates_last_success(
    synthetic_prechips_task, synthetic_prechips_kernel, changed,
):
    dodo, _, _, _, _, _, _ = synthetic_prechips_task
    state = synthetic_prechips_kernel

    def evaluate(values):
        definition = next(dodo.task_prechips())
        tracker = next(
            check for check in definition["uptodate"]
            if isinstance(check, dodo._PrechipsKernelTracker)
        )
        task = _FakeTask()
        return tracker(task, values), task.saved()

    up, saved = evaluate({})
    assert up is False
    assert saved == {
        "_prechips_kernel": {
            "path": str(Path(state["path"]).resolve()),
            "version": state["version"].strip(),
        },
    }
    assert evaluate(saved)[0] is True
    if changed == "path":
        state["path"] = str(Path(state["path"]).parent / "other-freecadcmd.exe")
    else:
        state["version"] = "FreeCAD 1.1.1\n"
    up, changed_saved = evaluate(saved)
    assert up is False
    assert changed_saved != saved
    # A failed action never runs the saver; the previous success stays stale.
    assert evaluate(saved)[0] is False
    assert evaluate(changed_saved)[0] is True
    assert state["discoveries"] == len(state["queries"]) == 5


@pytest.mark.parametrize(
    "unavailable", ["missing", "empty_version", "launch_error", "query_failure", "timeout"],
)
def test_prechips_unavailable_kernel_is_never_current(
    synthetic_prechips_task, synthetic_prechips_kernel, unavailable,
):
    dodo, _, _, _, _, _, _ = synthetic_prechips_task
    state = synthetic_prechips_kernel
    tracker = dodo._PrechipsKernelTracker()
    task = _FakeTask()
    assert tracker(task, {}) is False
    saved = task.saved()
    if unavailable == "missing":
        state["path"] = None
    elif unavailable == "empty_version":
        state["version"] = " \n"
    elif unavailable == "launch_error":
        state["error"] = OSError("kernel unavailable")
    elif unavailable == "query_failure":
        state["error"] = dodo.subprocess.CalledProcessError(1, "freecadcmd")
    else:
        state["error"] = dodo.subprocess.TimeoutExpired("freecadcmd", 10)

    for previous in (saved, {"_prechips_kernel": None}):
        task = _FakeTask()
        assert dodo._PrechipsKernelTracker()(task, previous) is False
        assert task.saved() == {"_prechips_kernel": None}


@pytest.mark.parametrize(
    ("inventory", "diagnostic"),
    [
        ("fixtures = [\n", "cannot read inventory"),
        ('[fixtures.test]\ncad = "not-a-fixture"\n', "invalid fixture TL stem"),
    ],
)
def test_prechips_malformed_inventory_fails_only_its_recorded_action(
    synthetic_prechips_task, synthetic_prechips_kernel, tmp_path, monkeypatch,
    inventory, diagnostic,
):
    from doit.loader import load_tasks

    dodo, plans, exporter, stem, _, _, _ = synthetic_prechips_task
    monkeypatch.setattr(dodo, "REPORTS", tmp_path / "reports")
    source = plans.shop_paths()[0]
    source.write_text(inventory, encoding="utf-8")
    loaded = load_tasks(dict(vars(dodo)), allow_delayed=True)
    names = {task.name for task in loaded}
    assert {f"prechips:{stem}", "build", "gallery", "check:math"} <= names
    assert any(task.name.startswith("part:") for task in loaded)
    definition = next(dodo.task_prechips())
    assert str(source.resolve()) in definition["file_dep"]
    assert not {
        str(path.resolve()) for path in exporter.bundle_paths(stem, dodo.CAD_OUT)
    } & set(definition["file_dep"])
    assert definition["task_dep"] == []
    assert definition["uptodate"] == [False]
    action, args = definition["actions"][0]
    assert action is dodo._fail_prechips_inventory
    assert diagnostic in args[2]
    assert "line " in args[2]

    # The action reports the captured failure, even if inventory is repaired later.
    source.write_text("version = 1\n", encoding="utf-8")

    def refuse_reload():
        pytest.fail("the recorded inventory failure must not parse again")

    monkeypatch.setattr(plans, "shop_spec_modules", refuse_reload)
    with pytest.raises(RuntimeError, match=re.escape(diagnostic)) as raised:
        action(*args)
    assert str(source.resolve()) in str(raised.value)
    assert f"prechips:{stem}" in str(raised.value)
    assert not (dodo.REPORTS / f"prechips-{stem}.ok").exists()
    assert synthetic_prechips_kernel["discoveries"] == 0
    assert synthetic_prechips_kernel["queries"] == []


def test_prechips_missing_fixture_spec_fails_only_its_recorded_action(
    synthetic_prechips_task, synthetic_prechips_kernel, tmp_path, monkeypatch,
):
    from doit.loader import load_tasks

    dodo, plans, exporter, stem, _, _, _ = synthetic_prechips_task
    monkeypatch.setattr(dodo, "REPORTS", tmp_path / "reports")
    source = plans.shop_paths()[0]
    missing_stem = "ch_rocker_arm_tl_nonexistent_inventory_fixture"
    missing_spec = dodo.SCRIPTS_DIR / f"{missing_stem}_spec.py"
    assert not missing_spec.exists()
    source.write_text(
        f'[fixtures.test]\ncad = "{missing_stem}"\n', encoding="utf-8",
    )

    def refuse_launch(*args, **kwargs):
        pytest.fail("bad inventory must not launch geometry or traveler work")

    monkeypatch.setattr(dodo, "_run", refuse_launch)
    loaded = load_tasks(dict(vars(dodo)), allow_delayed=True)
    names = {task.name for task in loaded}
    assert {f"prechips:{stem}", "build", "gallery", "check:math"} <= names
    assert any(task.name.startswith("part:") for task in loaded)
    definition = next(dodo.task_prechips())
    assert str(source.resolve()) in definition["file_dep"]
    assert not {
        str(path.resolve()) for path in exporter.bundle_paths(stem, dodo.CAD_OUT)
    } & set(definition["file_dep"])
    assert definition["task_dep"] == []
    assert definition["uptodate"] == [False]
    action, args = definition["actions"][0]
    assert action is dodo._fail_prechips_inventory
    assert "missing CAD fixture spec" in args[2]
    assert str(missing_spec.resolve()) in args[2]
    assert "correct the inventory cad stem" in args[2]

    # Repairing the inventory cannot erase the action's captured diagnostic.
    source.write_text("version = 1\n", encoding="utf-8")

    def refuse_reload():
        pytest.fail("the recorded inventory failure must not parse again")

    monkeypatch.setattr(plans, "shop_spec_modules", refuse_reload)
    with pytest.raises(RuntimeError, match="missing CAD fixture spec") as raised:
        action(*args)
    message = str(raised.value)
    assert f"prechips:{stem}" in message
    assert str(source.resolve()) in message
    assert str(missing_spec.resolve()) in message
    assert not (dodo.REPORTS / f"prechips-{stem}.ok").exists()
    assert synthetic_prechips_kernel["discoveries"] == 0
    assert synthetic_prechips_kernel["queries"] == []


def test_prechips_failed_action_never_writes_stamp(tmp_path, monkeypatch):
    dodo = _load_dodo()
    stamp = tmp_path / "prechips-synthetic.ok"
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic strict traveler exit 2")
    monkeypatch.setattr(dodo, "_run", fail)
    with pytest.raises(RuntimeError, match="exit 2"):
        dodo._run_stamped(["synthetic-only"], "traveler", str(stamp), "prechips:ch_rocker_arm")
    assert not stamp.exists()


def test_recipe_enrolls_strict_traveler_tests():
    dodo = _load_dodo()
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    deps = {Path(path).name for path in recipe["file_dep"]}
    assert {"test_process_plans.py", "test_prechips_traveler.py"} <= deps
    command = " ".join(str(arg) for _, args in recipe["actions"] for arg in args[0])
    assert "test_process_plans.py" in command
    assert "test_prechips_traveler.py" in command


def test_recipe_gate_tracks_migrated_and_enrolled_plans(
    synthetic_prechips_task, monkeypatch
):
    dodo, plans, _, stem, source, _, _ = synthetic_prechips_task
    other = "synthetic_second_part"
    held = "synthetic_held_part"
    monkeypatch.setattr(plans, "MIGRATED_PLANS", (held, stem))
    monkeypatch.setattr(plans, "TRAVELER_STEMS", (stem, other))
    second = plans.plan_path(other)
    second.parent.mkdir(parents=True)
    second.write_text('features = "unused"\n', encoding="utf-8")
    held_plan = plans.plan_path(held)
    held_plan.parent.mkdir(parents=True)
    held_plan.write_text('features = "held"\n', encoding="utf-8")
    historical = plans.plan_path("synthetic_historical_part")
    historical.parent.mkdir(parents=True)
    historical.write_text('features = "historical"\n', encoding="utf-8")
    recipe = next(task for task in dodo.task_check() if task["name"] == "recipe")
    deps = recipe["file_dep"]
    for member in (source, held_plan, second):
        assert deps.count(str(member.resolve())) == 1
    assert str(historical.resolve()) not in deps
    before = dodo._digest_files(deps)
    historical.write_text('features = "still historical"\n', encoding="utf-8")
    assert dodo._digest_files(deps) == before
    for member in (source, held_plan, second):
        before = dodo._digest_files(recipe["file_dep"])
        with member.open("a", encoding="utf-8") as stream:
            stream.write('[drawing]\nrevision = "v2"\n')
        assert dodo._digest_files(recipe["file_dep"]) != before, member


@pytest.fixture
def isolated_feature_keys(isolated_assembly_helper_keys, monkeypatch):
    """Use real leaf/native recipes and keys, mutating only isolated source bytes."""
    import export_features

    dodo, root, native_snapshot = isolated_assembly_helper_keys
    adapter = root / ".adapter-features.digest"
    adapter.write_bytes(b"fixed feature exporter adapter\n")
    monkeypatch.setattr(dodo, "_submodule_assembly_dep", lambda: str(adapter))
    sources = {
        stem: dodo._feature_requirement_deps(stem)
        for stem in export_features.SUPPORTED_PARTS
    }
    copied_sources = {}
    for source in {path for paths in sources.values() for path in paths}:
        original = Path(source).resolve()
        copied = root / original.relative_to(REPO_ROOT)
        assert copied.resolve().is_relative_to(root.resolve())
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(original.read_bytes())
        copied_sources[source] = str(copied)
    monkeypatch.setattr(
        dodo, "_feature_requirement_deps",
        lambda stem: [copied_sources[path] for path in sources[stem]],
    )
    monkeypatch.setattr(
        dodo, "RELEASE_VERSION_FILE",
        root / dodo.RELEASE_VERSION_FILE.relative_to(REPO_ROOT),
    )

    def snapshot(*, native=True):
        """Every key group, or with ``native=False`` only ``features``.

        Feature-only callers skip regenerating every part and assembly key, but
        still start from an empty artefact-digest memo exactly as a full
        snapshot does, so an edit made since the last call is always re-read.
        """
        if native:
            result = native_snapshot()
        else:
            dodo._ARTEFACT_DIGEST_MEMO.clear()
            result = {}
        tasks = {
            task["name"].removeprefix("features:"): task
            for task in dodo.task_package()
            if task["name"].startswith("features:")
        }
        for stem, task in tasks.items():
            assert all(
                Path(path).resolve().is_relative_to(root.resolve())
                for path in task["file_dep"]
            ), stem
        result["features"] = {
            stem: dodo._cache_key(task["file_dep"], f"package:features:{stem}")
            for stem, task in tasks.items()
        }
        return result

    return dodo, root, snapshot


def test_one_draw_edit_rekeys_only_its_features_leaf_not_native_closures(
    isolated_feature_keys,
):
    dodo, root, snapshot = isolated_feature_keys
    before = snapshot()
    source = root / "cad/scripts/draw_ch_rocker_arm.py"
    assert source.is_file()
    source.write_bytes(source.read_bytes() + b"\nFEATURE_RECIPE_REVISION = 2\n")
    after = snapshot()
    changed = {
        stem for stem in before["features"]
        if before["features"][stem] != after["features"][stem]
    }
    assert changed == {"ch_rocker_arm"}
    for group in ("recipes", "assemblies", "part_recipes", "parts"):
        assert after[group] == before[group], group
    assert all(
        str(source) not in dodo._part_file_deps(script, script.stem.removeprefix("build_"))
        for script in dodo.part_scripts()
    )


@pytest.mark.parametrize(
    "member",
    [
        "cad/scripts/export_models.py", "cad/scripts/_export_feature_faces.py",
        "cad/scripts/_feature_requirements.py", "cad/config/release.yaml",
        ".adapter-features.digest", "cad/config/parts/ch-rocker-arm.yaml",
        "cad/config/title_block.yaml",
        "cad/out/sldprt/.ch-rocker-arm.execution",
    ],
)
def test_features_keys_fold_each_real_shared_or_own_input(isolated_feature_keys, member):
    dodo, root, snapshot = isolated_feature_keys
    before = snapshot(native=False)["features"]
    source = root / member
    assert source.is_file(), member
    if source.suffix == ".yaml":
        source.write_bytes(source.read_bytes() + b"\nfeature_recipe_revision: 2\n")
    elif source.suffix == ".py":
        source.write_bytes(source.read_bytes() + b"\nFEATURE_RECIPE_REVISION = 2\n")
    else:
        source.write_bytes(b"b" * 64 + b"\n")
    after = snapshot(native=False)["features"]
    expected = {
        stem for stem in before if str(source.resolve()) in dodo._feature_export_file_deps(stem)
    }
    assert expected, member
    assert {stem for stem in before if before[stem] != after[stem]} == expected


@pytest.mark.parametrize(
    "member",
    ["cad/config/parts/fr-nameplate.yaml", "cad/config/assemblies/pd-paper-drive.yaml"],
)
def test_unrelated_config_edit_preserves_rocker_feature_key(isolated_feature_keys, member):
    dodo, root, snapshot = isolated_feature_keys
    source = root / member
    assert source.is_file(), member
    assert str(source.resolve()) not in dodo._feature_export_file_deps("ch_rocker_arm")
    before = snapshot(native=False)["features"]["ch_rocker_arm"]
    source.write_bytes(source.read_bytes() + b"\nfeature_recipe_revision: 2\n")
    assert snapshot(native=False)["features"]["ch_rocker_arm"] == before


def test_prechips_rejects_unexported_enrollment(monkeypatch):
    import _process_plans
    dodo = _load_dodo()
    monkeypatch.setattr(_process_plans, "TRAVELER_STEMS", ("synthetic_not_exported",))
    with pytest.raises(AssertionError, match="synthetic_not_exported"):
        list(dodo.task_prechips())


def test_prechips_empty_enrollment_has_no_tasks(monkeypatch, synthetic_prechips_kernel):
    import _process_plans
    dodo = _load_dodo()
    monkeypatch.setattr(_process_plans, "TRAVELER_STEMS", ())
    monkeypatch.setattr(_process_plans, "MIGRATED_PLANS", ("synthetic_held_part",))
    assert list(dodo.task_prechips()) == []
    assert synthetic_prechips_kernel["discoveries"] == 0
    assert synthetic_prechips_kernel["queries"] == []


@pytest.mark.parametrize("kind", ["part", "assembly", "explode_assembly", "gate"])
@pytest.mark.parametrize("outcome", ["stored", "lost", "skip", "empty", "error", "off"])
def test_forced_refresh_never_restores_and_requires_a_stored_result(
    monkeypatch, tmp_path, kind, outcome
):
    import json
    import _artifact_cache

    monkeypatch.setattr(_artifact_cache, "prewarm", lambda: None)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    dodo = _load_dodo()
    labels = {
        "part": "part:pn_pen_rod",
        "assembly": "assembly:ms_measuring_stick",
        "explode_assembly": "assembly:pd_paper_drive",
        "gate": "verify:kinematics",
    }
    label = labels[kind]
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": [label], "reason": "Owner - Re-evaluate unchanged inputs",
    }))
    output = tmp_path / "result"
    ledger = tmp_path / "inputs.json"
    builds = []
    stores = []
    refreshes = []
    commands = []

    def execute(cmd, *_args, **_kwargs):
        builds.append(label)
        commands.append(cmd)

    monkeypatch.setattr(dodo, "_cache_key", lambda *_a: "a" * 64)
    monkeypatch.setattr(
        dodo._cache, "restore", lambda *_a: pytest.fail("refreshed leaf restored")
    )
    monkeypatch.setattr(dodo._cache, "note_refresh", lambda *args: refreshes.append(args))
    monkeypatch.setattr(dodo._cache, "capture_refresh", lambda *_args: None)
    monkeypatch.setattr(
        dodo._cache, "store", lambda *args, **_kw: stores.append(args) or outcome
    )
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(0.0))
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(dodo, "_exec_com", execute)
    monkeypatch.setattr(dodo, "_part_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda *_a: [output])
    monkeypatch.setattr(dodo, "_stamp_part_execution", lambda *_a: None)
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda *_a: [output])
    monkeypatch.setattr(dodo, "_stamp_assembly_execution", lambda *_a: None)
    monkeypatch.setattr(dodo, "_input_ledger", lambda *_a: ledger)
    if kind.endswith("assembly"):
        # A matching local target and ledger must not launder the old cached
        # assembly by taking a cheap reload tier (PARTS/EXPLODE) or restoring an
        # explode base instead of rerunning its recipe.
        output.write_bytes(b"old cached assembly")
        (tmp_path / ".result.massprops.sha").write_text("proof\n", encoding="utf-8")
        dodo._write_input_ledger(ledger, {})

    def run():
        if kind == "part":
            dodo._cached_part_action("pn_pen_rod", tmp_path / "build.py")
        elif kind.endswith("assembly"):
            dodo.build_or_refresh(label.split(":")[1], [], [], [str(output)])
        else:
            dodo._cached_com_action(label, ["gate"], [], [output], "gate")

    if outcome == "stored":
        run()
    else:
        with pytest.raises(RuntimeError, match="forced cache refresh did not store outputs"):
            run()
    assert builds == [label]
    if kind == "assembly":
        assert Path(commands[0][1]).name == "build_ms_measuring_stick_assembly.py"
    if kind == "explode_assembly":
        assert Path(commands[0][1]).name == "build_pd_paper_drive_assembly.py"
    expected = [("a" * 64, [output], label)]
    if kind == "explode_assembly" and outcome == "stored":
        # The recomputed result also replaces the explode base it would share.
        assert [(o, lab) for _key, o, lab in stores[1:]] == [
            ([output], f"{label} explode-base")
        ]
        stores = stores[:1]
    assert stores == expected
    # Both the first probe and under-seat re-probe bypassed restore.
    assert refreshes == [(label, "a" * 64, "Owner - Re-evaluate unchanged inputs")] * 2


@pytest.fixture
def canonical_publication(tmp_path, monkeypatch):
    """Real pack/unpack, keys and native tokens; only COM/Azure transport are fake."""
    import hashlib
    from types import SimpleNamespace
    import _artifact_cache
    from test_artifact_cache import _BlockBlobService

    monkeypatch.setattr(_artifact_cache, "prewarm", lambda: None)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    dodo = _load_dodo()
    cache_module = dodo._cache
    complete_part_cache_outputs = dodo._part_cache_outputs
    service = _BlockBlobService()
    seats, probes, publications = {}, [], []
    references = {}

    class Backend(cache_module._BlobBackend):
        def put(self, key, blob, *, replace_etag=None):
            assert not seats.get(dodo.REPO_ROOT, 0), "publication held the COM seat"
            publications.append((dodo.REPO_ROOT.name, key, replace_etag))
            return super().put(key, blob, replace_etag=replace_etag)

    backend = Backend(service)
    monkeypatch.setattr(cache_module, "_BACKEND", backend)
    monkeypatch.setattr(cache_module, "_REFRESH_ETAGS", {})
    monkeypatch.setattr(cache_module, "_KEY_INPUTS", {})
    monkeypatch.setattr(cache_module, "_KEY_CONTEXT", {})
    monkeypatch.setattr(cache_module, "_KEY_MANIFESTS", {})
    monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
    monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
    monkeypatch.setattr(
        dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("unconfigured fake COM work")
    )
    monkeypatch.setattr(
        dodo, "_farm_build", lambda *_a: pytest.fail("unexpected farm dispatch")
    )
    monkeypatch.setattr(
        dodo, "_release_seat_documents",
        lambda _label: pytest.fail("unexpected document-release subprocess"),
    )

    @contextlib.contextmanager
    def seat(_label):
        root = dodo.REPO_ROOT
        assert not seats.get(root, 0)
        seats[root] = 1
        try:
            yield 0.0
        finally:
            seats[root] = 0

    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(
        dodo, "_sldprt",
        lambda stem: str(dodo.CAD_OUT / "sldprt" / f"{stem}.SLDPRT"),
    )
    monkeypatch.setattr(
        dodo, "_sldasm",
        lambda stem: str(dodo.CAD_OUT / "sldasm" / f"{stem}.SLDASM"),
    )

    def script(stem, assembly=False):
        suffix = "_assembly" if assembly else ""
        return dodo.REPO_ROOT / "cad" / "scripts" / f"build_{stem}{suffix}.py"

    def deps(stem):
        result = [str(script(stem, assembly=True))]
        for kind, child in references.get(stem, ()):
            result.append(
                dodo._part_execution_token(child) if kind == "part"
                else dodo._assembly_execution_token(child)
            )
        return result

    def outputs(kind, stem="leaf"):
        out = dodo.CAD_OUT
        if kind == "part":
            return [
                Path(dodo._sldprt(stem)), out / "stl" / f"{stem}.STL",
                out / "png" / f"{stem}.png",
            ]
        if kind == "assembly":
            return [
                Path(dodo._sldasm(stem)), dodo._input_ledger(stem),
                out / "sldasm" / f".{stem}.massprops.sha",
                out / "png" / f"{stem}.png",
            ]
        if kind == "drawing":
            return [
                out / "drawings" / "leaf.SLDDRW", out / "sldprt" / "leaf.SLDPRT",
                out / "pdf" / "leaf.pdf",
            ]
        return [out / "reports" / "gate.ok", out / "reports" / "gate.json"]

    monkeypatch.setattr(dodo, "_part_file_deps", lambda path, _stem: [str(path)])
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda stem: outputs("part", stem))
    monkeypatch.setattr(dodo, "_assembly_file_deps", deps)
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda stem: outputs("assembly", stem))
    monkeypatch.setattr(dodo, "_input_ledger", lambda stem: dodo.CAD_OUT / "sldasm" / f".{stem}.inputs.json")
    monkeypatch.setattr(dodo, "_recipe_files", lambda stem: [str(script(stem, True))])
    monkeypatch.setattr(dodo, "POST_ASSEMBLY", {})
    monkeypatch.setattr(dodo, "explode_plan", lambda _stem: SimpleNamespace(closure=frozenset()))
    monkeypatch.setattr(dodo, "_assembly_tier", lambda *_a: (dodo.RefreshTier.FULL, "test missing"))
    monkeypatch.setattr(dodo, "_drawing_file_deps", lambda _stem: [str(script("leaf"))])
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: outputs("drawing"))
    original_restore = cache_module.restore

    def restore(key, paths, label):
        hit = original_restore(key, paths, label)
        probes.append((dodo.REPO_ROOT.name, label, hit))
        return hit

    monkeypatch.setattr(cache_module, "restore", restore)

    @contextlib.contextmanager
    def at(name):
        root = (tmp_path / name).resolve()
        scripts = root / "cad" / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        for stem in ("leaf", "mid", "top"):
            for suffix in ("", "_assembly"):
                path = scripts / f"build_{stem}{suffix}.py"
                if not path.exists():
                    path.write_text(f"# same {stem}{suffix} recipe\n", encoding="utf-8")
        out = root / "cad" / "out"
        with monkeypatch.context() as patch:
            patch.setattr(dodo, "REPO_ROOT", root)
            patch.setattr(dodo, "CAD_OUT", out)
            patch.setattr(dodo, "REPORTS", out / "reports")
            patch.setattr(cache_module, "REPO_ROOT", root)
            patch.setattr(cache_module, "_CACHE_OUTPUT_ROOT", out)
            patch.setattr(cache_module, "_REPORTS", out / "reports")
            patch.setattr(cache_module, "_EVENTS_LOG", out / "reports" / "cache.jsonl")
            patch.setattr(cache_module, "_KEYDIR", out / "reports" / "cache-keys")
            yield root

    def emit(kind, payload, stem="leaf"):
        for path in outputs(kind, stem):
            if path == dodo._input_ledger(stem):
                continue  # the real action writes the ledger
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload + b":" + path.name.encode())

    def run(kind, stem="leaf"):
        if kind == "part":
            dodo._cached_part_action(stem, script(stem))
        elif kind == "assembly":
            dodo.build_or_refresh(stem, [], [], [dodo._sldasm(stem)])
        elif kind == "drawing":
            dodo._cached_drawing_action("pd_platen_guide")
        else:
            paths = outputs(kind)
            dodo._cached_com_action(
                "verify:test", ["fake-gate"], [str(script("leaf"))],
                paths, "test-gate", stamp=str(paths[0]),
            )

    def identity(kind, stem="leaf"):
        if kind in ("part", "assembly"):
            token = (
                dodo._part_execution_token(stem) if kind == "part"
                else dodo._assembly_execution_token(stem)
            )
            native = Path(dodo._sldprt(stem) if kind == "part" else dodo._sldasm(stem))
            value = Path(token).read_text(encoding="utf-8").strip()
            assert value == hashlib.sha256(native.read_bytes()).hexdigest()
            return value
        return hashlib.sha256(outputs(kind)[-1].read_bytes()).hexdigest()

    return SimpleNamespace(
        dodo=dodo, cache=cache_module, backend=backend, service=service,
        at=at, run=run, emit=emit, identity=identity, outputs=outputs,
        references=references, probes=probes, publications=publications, seats=seats,
        complete_part_cache_outputs=complete_part_cache_outputs,
    )


def _canonical_two_producer_race(fixture, monkeypatch, kind, after_consumer=None):
    """Schedule barrier: both miss; A publishes; consumer hits; B finishes late."""
    f = fixture
    seen, arrived = {}, False

    def execute(_cmd, label, **kwargs):
        nonlocal arrived
        if f.dodo.REPO_ROOT.name == "B" and not arrived:
            arrived = True
            with f.at("A"):
                f.run(kind)
                seen["A"] = f.identity(kind)
            with f.at("consumer"):
                f.run(kind)
                seen["consumer"] = f.identity(kind)
                if after_consumer is not None:
                    after_consumer()
        f.emit(kind, f.dodo.REPO_ROOT.name.encode())

    monkeypatch.setattr(f.dodo, "_exec_com", execute)
    with f.at("B"):
        f.run(kind)
        seen["B"] = f.identity(kind)
        if kind == "assembly":
            assert f.dodo._read_input_ledger(f.dodo._input_ledger("leaf")) == f.dodo._ledger_inputs(
                f.dodo._assembly_file_deps("leaf")
            )
    assert seen["B"] == seen["consumer"] == seen["A"], "canonical identity fork"
    assert [hit for name, _label, hit in f.probes if name == "B"] == [False, False, True]
    with f.at("late-consumer"):
        f.run(kind)
        assert f.identity(kind) == seen["consumer"], "canonical identity changed after publication"
    return seen


@pytest.mark.parametrize("kind", ["part", "assembly", "drawing", "generic"])
def test_two_producers_and_consumer_adopt_one_complete_canonical_bundle(
    canonical_publication, monkeypatch, kind
):
    f = canonical_publication
    ledger_writes = []
    write_ledger = f.dodo._write_input_ledger

    def record_ledger(path, inputs):
        ledger_writes.append((f.dodo.REPO_ROOT.name, Path(f.dodo._sldasm("leaf")).read_bytes()))
        write_ledger(path, inputs)

    if kind == "assembly":
        monkeypatch.setattr(f.dodo, "_write_input_ledger", record_ledger)
    _canonical_two_producer_race(f, monkeypatch, kind)
    if kind == "assembly":
        assert [body[:2] for name, body in ledger_writes if name == "B"] == [b"B:", b"A:"]
    with f.at("B"):
        for path in f.outputs(kind):
            if path.name.endswith(".inputs.json") or path.name == "gate.ok":
                continue
            assert path.read_bytes().startswith(b"A:"), path


def test_same_race_rejects_an_overwrite_backend_mutation(canonical_publication, monkeypatch):
    f = canonical_publication
    original = f.backend.put

    def overwrite(key, blob, *, replace_etag=None):
        return original(key, blob, replace_etag=f.backend.etag(key))

    monkeypatch.setattr(f.backend, "put", overwrite)
    # The exact same oracle must reject the old last-writer behavior.
    with pytest.raises(AssertionError, match="canonical identity fork"):
        _canonical_two_producer_race(f, monkeypatch, "part")


def test_inline_prerequisite_adoption_converges_nested_assembly_keys(
    canonical_publication, monkeypatch
):
    f = canonical_publication
    f.references.update(mid=[("part", "leaf")], top=[("assembly", "mid")])
    expected = {}

    def downstream():
        def emit_assembly(_cmd, label, **kwargs):
            stem = kwargs["task"].split(":")[1]
            f.emit("assembly", b"consumer-native", stem)

        with monkeypatch.context() as patch:
            patch.setattr(f.dodo, "_exec_com", emit_assembly)
            for stem in ("mid", "top"):
                f.run("assembly", stem)
                expected[stem] = (
                    f.dodo._cache_key(f.dodo._assembly_file_deps(stem)),
                    f.identity("assembly", stem),
                )

    _canonical_two_producer_race(f, monkeypatch, "part", after_consumer=downstream)
    # A worker leaf can build a missing prerequisite inline, then keep walking
    # its native closure; no private losing identity may leak into either level.
    monkeypatch.setattr(
        f.dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("nested key diverged")
    )
    with f.at("B"):
        for stem in ("mid", "top"):
            assert f.dodo._cache_key(f.dodo._assembly_file_deps(stem)) == expected[stem][0]
            f.run("assembly", stem)
            assert f.identity("assembly", stem) == expected[stem][1]


@pytest.mark.parametrize("persistent", [False, True], ids=["release-recovers", "still-locked"])
def test_loser_adoption_holds_seat_and_releases_documents_once(
    canonical_publication, monkeypatch, persistent
):
    f = canonical_publication
    released = []
    original_unpack = f.cache._unpack

    def unpack(blob, outputs):
        if f.dodo.REPO_ROOT.name == "B":
            assert f.seats[f.dodo.REPO_ROOT] == 1
            if persistent or not released:
                raise PermissionError(13, "share-locked", "leaf.SLDPRT")
        original_unpack(blob, outputs)

    def release(_label):
        assert f.seats[f.dodo.REPO_ROOT] == 1
        released.append(f.dodo.REPO_ROOT.name)

    monkeypatch.setattr(f.cache, "_unpack", unpack)
    monkeypatch.setattr(f.dodo, "_release_seat_documents", release)
    if persistent:
        with pytest.raises(RuntimeError, match="still share-locked"):
            _canonical_two_producer_race(f, monkeypatch, "part")
    else:
        _canonical_two_producer_race(f, monkeypatch, "part")
    assert released == ["B"]
    assert not any(f.seats.values())


@pytest.mark.parametrize("lock_at,persistent", [
    (None, False),
    ("optional-file", False), ("optional-file", True),
    ("directory", False), ("directory", True),
    ("install", False), ("install", True),
])
def test_sparse_winner_adoption_removes_loser_geometry_and_retries_replacement_locks(
    canonical_publication, monkeypatch, lock_at, persistent
):
    """Different real archive members converge, including cleanup/install locks."""
    import _transforms

    f = canonical_publication
    released, refused = [], []
    winner_identity = None

    def outputs():
        return [
            Path(f.dodo._sldprt("leaf")),
            f.dodo.CAD_OUT / "stl" / "leaf.STL",
            f.dodo.CAD_OUT / "png" / "leaf",
        ]

    monkeypatch.setattr(f.dodo, "_part_cache_outputs", lambda _stem: outputs())

    def execute(*_args, **_kwargs):
        nonlocal winner_identity
        producer = f.dodo.REPO_ROOT.name
        if producer == "B":
            with f.at("A"):
                f.run("part")
                winner_identity = f.identity("part")
        native, optional, views = outputs()
        native.parent.mkdir(parents=True, exist_ok=True)
        native.write_bytes(producer.encode() + b"-native")
        views.mkdir(parents=True, exist_ok=True)
        (views / "canonical.png").write_bytes(producer.encode() + b"-render")
        if producer == "B":
            optional.parent.mkdir(parents=True)
            optional.write_bytes(
                b"solid loser\nvertex 0 0 0\nvertex 9 8 0\nvertex 0 0 7\nendsolid\n"
            )
            stale = views / "loser-only"
            stale.mkdir()
            (stale / "geometry.STL").write_bytes(b"loser-only directory member")

    def release(_label):
        assert f.seats[f.dodo.REPO_ROOT] == 1
        released.append("B")

    def locked(phase, path):
        if (
            f.dodo.REPO_ROOT.name == "B" and phase == lock_at
            and (persistent or not released)
        ):
            assert f.seats[f.dodo.REPO_ROOT] == 1
            refused.append(phase)
            raise PermissionError(13, "share-locked replacement", str(path))

    unlink = Path.unlink
    rmtree = f.cache.shutil.rmtree
    replace = f.cache.os.replace

    def unlink_output(path, *args, **kwargs):
        if path == outputs()[1]:
            locked("optional-file", path)
        return unlink(path, *args, **kwargs)

    def remove_directory(path, *args, **kwargs):
        if Path(path) == outputs()[2]:
            locked("directory", path)
        return rmtree(path, *args, **kwargs)

    def install(source, target, *args, **kwargs):
        if Path(target) == outputs()[0]:
            locked("install", target)
        return replace(source, target, *args, **kwargs)

    monkeypatch.setattr(f.dodo, "_exec_com", execute)
    monkeypatch.setattr(f.dodo, "_release_seat_documents", release)
    monkeypatch.setattr(Path, "unlink", unlink_output)
    monkeypatch.setattr(f.cache.shutil, "rmtree", remove_directory)
    monkeypatch.setattr(f.cache.os, "replace", install)
    with f.at("B"):
        sibling = f.dodo.CAD_OUT / "png" / "unrelated" / "keep.png"
        sibling.parent.mkdir(parents=True)
        sibling.write_bytes(b"unrelated")
        if persistent:
            with pytest.raises(RuntimeError, match="still share-locked"):
                f.run("part")
        else:
            f.run("part")
            native, optional, views = outputs()
            assert f.identity("part") == winner_identity
            assert native.read_bytes() == b"A-native"
            assert (views / "canonical.png").read_bytes() == b"A-render"
            assert not optional.exists()
            assert not (views / "loser-only").exists()
            monkeypatch.setattr(_transforms, "OUT_STL", optional.parent)
            monkeypatch.setattr(_transforms, "_STL_BBOX_CACHE", {})
            with pytest.raises(FileNotFoundError):
                _transforms.stl_bbox_mm("leaf")
        assert sibling.read_bytes() == b"unrelated"
        assert not list(f.dodo.CAD_OUT.glob(".cache-restore-*"))
    assert released == (["B"] if lock_at else [])
    assert refused == ([lock_at] * (2 if persistent else 1) if lock_at else [])
    assert not any(f.seats.values())


def test_hash_invalid_canonical_adoption_is_fatal(canonical_publication, monkeypatch):
    f = canonical_publication

    def corrupt_after_consumer():
        _producer, key, _etag = f.publications[-1]
        f.service.metadata[f.backend._name(key)]["archive_sha256"] = "0" * 64

    with pytest.raises(RuntimeError, match="canonical outputs could not be restored"):
        _canonical_two_producer_race(
            f, monkeypatch, "part", after_consumer=corrupt_after_consumer
        )


def _enable_test_explode_alias(f, monkeypatch):
    from types import SimpleNamespace

    base_key = f.cache.key_inputs([], f.dodo.ContentChecker._digest)[0]
    monkeypatch.setattr(
        f.dodo, "explode_plan", lambda _stem: SimpleNamespace(closure=frozenset({"explode.py"}))
    )
    monkeypatch.setattr(f.dodo, "_explode_base_key", lambda *_args: base_key)
    return base_key


def test_ordinary_alias_conflict_never_adopts_over_full_key(
    canonical_publication, monkeypatch
):
    import json
    from test_artifact_cache import _get_bytes

    f = canonical_publication
    base_key = _enable_test_explode_alias(f, monkeypatch)
    with f.at("A"):
        f.emit("assembly", b"alias-A")
        f.dodo._write_input_ledger(f.dodo._input_ledger("leaf"), {})
        assert f.cache.store(base_key, f.outputs("assembly"), "assembly:leaf explode-base") == "stored"
    old_alias = _get_bytes(f.backend, base_key)
    monkeypatch.setattr(f.dodo, "_exec_com", lambda *_a, **_kw: f.emit("assembly", b"full-B"))
    with f.at("B"):
        f.run("assembly")
        assert Path(f.dodo._sldasm("leaf")).read_bytes().startswith(b"full-B:")
        full_key = f.dodo._cache_key(f.dodo._assembly_file_deps("leaf"))
        assert _get_bytes(f.backend, full_key) != old_alias
        assert _get_bytes(f.backend, base_key) == old_alias
        events = [
            json.loads(line)["event"]
            for line in f.cache._EVENTS_LOG.read_text(encoding="utf-8").splitlines()
        ]
        assert events[-1] == "store_lost"


@pytest.mark.parametrize("initially_present", [False, True])
@pytest.mark.parametrize("conflict", [None, "root", "alias"])
def test_forced_root_and_alias_cas_snapshot_before_seat_and_work(
    canonical_publication, monkeypatch, initially_present, conflict
):
    import json
    from test_artifact_cache import _get_bytes, _put_bytes

    f = canonical_publication
    base_key = _enable_test_explode_alias(f, monkeypatch)
    with f.at("A"):
        root_key = f.dodo._cache_key(f.dodo._assembly_file_deps("leaf"))
        if initially_present:
            f.emit("assembly", b"old-A")
            f.dodo._write_input_ledger(f.dodo._input_ledger("leaf"), {})
            with f.cache._pack(f.outputs("assembly")) as archive:
                f.backend.put(root_key, archive)
                f.backend.put(base_key, archive)
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": ["assembly:leaf"], "reason": "Owner - Refresh root and alias",
    }))
    initial_etags = dict(f.service.etags)
    seat = f.dodo._com_seat
    snapshots = []

    @contextlib.contextmanager
    def before_seat(label):
        heads = [call[1] for call in f.service.calls if call[0] == "etag"]
        assert sorted(heads) == sorted([f.backend._name(root_key), f.backend._name(base_key)])
        snapshots.extend(heads)
        if conflict is not None:
            key = root_key if conflict == "root" else base_key
            _put_bytes(
                f.backend, key, b"concurrent canonical",
                replace_etag=initial_etags.get(f.backend._name(key)),
            )
        with seat(label) as waited:
            yield waited

    def execute(*_args, **_kwargs):
        assert len(snapshots) == 2
        f.emit("assembly", b"refresh-B")

    monkeypatch.setattr(f.dodo, "_com_seat", before_seat)
    monkeypatch.setattr(f.dodo, "_exec_com", execute)
    with f.at("B"):
        if conflict is None:
            f.run("assembly")
        else:
            with pytest.raises(RuntimeError, match="did not store outputs \\(lost\\)"):
                f.run("assembly")
    heads = [call[1] for call in f.service.calls if call[0] == "etag"]
    assert heads == snapshots  # no under-seat or pre-upload recapture
    if conflict == "root":
        assert _get_bytes(f.backend, root_key) == b"concurrent canonical"
        if not initially_present:
            assert _get_bytes(f.backend, base_key) is None
    elif conflict == "alias":
        assert _get_bytes(f.backend, base_key) == b"concurrent canonical"
        # The pair is deliberately non-atomic: the root has already advanced.
        assert f.service.etags[f.backend._name(root_key)] != initial_etags.get(f.backend._name(root_key))
    else:
        import tarfile

        def members(key):
            archive = f.backend.get(key)
            assert archive is not None
            with archive, tarfile.open(fileobj=archive, mode="r:gz") as tar:
                return {
                    member.name: tar.extractfile(member).read()
                    for member in tar.getmembers() if member.isreg()
                }

        assert members(root_key) == members(base_key)


@pytest.mark.parametrize("which", ["root", "alias"])
def test_refresh_snapshot_head_error_is_fatal_before_work(
    canonical_publication, monkeypatch, which
):
    import json

    f = canonical_publication
    base_key = _enable_test_explode_alias(f, monkeypatch)
    etag = f.backend.etag

    def fail(key):
        if (key == base_key) == (which == "alias"):
            raise OSError("HEAD unavailable, not absence")
        return etag(key)

    monkeypatch.setattr(f.backend, "etag", fail)
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": ["assembly:leaf"], "reason": "Owner - Snapshot failure",
    }))
    monkeypatch.setattr(f.dodo, "_com_seat", lambda *_a: pytest.fail("waited for seat after failed HEAD"))
    monkeypatch.setattr(f.dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("built after failed HEAD"))
    with f.at("B"), pytest.raises(OSError, match="HEAD unavailable"):
        f.run("assembly")
    assert not f.publications


@pytest.mark.parametrize("which", ["root", "alias"])
@pytest.mark.parametrize("initially_present", [False, True])
def test_root_or_alias_refresh_upload_failure_is_fatal(
    canonical_publication, monkeypatch, which, initially_present
):
    import json

    f = canonical_publication
    base_key = _enable_test_explode_alias(f, monkeypatch)
    with f.at("A"):
        root_key = f.dodo._cache_key(f.dodo._assembly_file_deps("leaf"))
        if initially_present:
            f.emit("assembly", b"old-A")
            f.dodo._write_input_ledger(f.dodo._input_ledger("leaf"), {})
            with f.cache._pack(f.outputs("assembly")) as archive:
                f.backend.put(root_key, archive)
                f.backend.put(base_key, archive)
    initial_etags = dict(f.service.etags)
    put = f.backend.put

    def upload(key, blob, *, replace_etag=None):
        if (key == base_key) == (which == "alias"):
            raise OSError("upload unavailable")
        return put(key, blob, replace_etag=replace_etag)

    monkeypatch.setattr(f.backend, "put", upload)
    monkeypatch.setattr(f.dodo, "_exec_com", lambda *_a, **_kw: f.emit("assembly", b"refresh-B"))
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": ["assembly:leaf"], "reason": "Owner - Publish failure",
    }))
    outcome = "lost" if initially_present else "error"
    with f.at("B"), pytest.raises(RuntimeError, match=f"did not store outputs \\({outcome}\\)"):
        f.run("assembly")
    if which == "alias":
        assert f.service.etags[f.backend._name(root_key)] != initial_etags.get(f.backend._name(root_key))
        assert f.service.etags.get(f.backend._name(base_key)) == initial_etags.get(f.backend._name(base_key))
    else:
        assert f.service.etags == initial_etags


def test_refresh_bypasses_each_cached_task_family_freshness(monkeypatch):
    import json
    import _artifact_cache

    monkeypatch.setattr(_artifact_cache, "prewarm", lambda: None)
    dodo = _load_dodo()
    labels = [
        "part:pn_pen_rod", "assembly:pn_pen", "drawing:pn_pen_rod",
        "verify_soundness:pn_pen", "verify:kinematics",
    ]
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": labels, "reason": "Re-evaluate",
    }))
    monkeypatch.setattr(dodo, "_seat_part_order", lambda: ["pn_pen_rod"])
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["pn_pen_rod"])
    monkeypatch.setattr(dodo, "ASSEMBLY_ORDER", ["pn_pen"])
    monkeypatch.setattr(dodo, "_part_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_drawing_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda *_a: [])
    monkeypatch.setattr(dodo, "_recipe_files", lambda *_a: [])
    monkeypatch.setattr(dodo, "_soundness_file_deps", lambda *_a: [])
    monkeypatch.setattr(dodo, "_kinematics_file_deps", lambda: [])
    tasks = [
        *dodo.task_part(), *dodo.task_assembly(), *dodo.task_drawing(),
        *dodo.task_verify_soundness(),
        *(task for task in dodo.task_verify() if task["name"] == "kinematics"),
    ]
    assert len(tasks) == len(labels)
    for task in tasks:
        assert False in task["uptodate"]
        assert all(getattr(action[0], "_remote_cache_action", False) for action in task["actions"])


@pytest.mark.parametrize("shortcut", ["hit", "farm"])
def test_ordinary_assembly_shortcut_does_not_walk_explode_closure(
    canonical_publication, monkeypatch, shortcut
):
    f = canonical_publication
    with f.at("A"):
        key = f.dodo._cache_key(f.dodo._assembly_file_deps("leaf"))
        if shortcut == "hit":
            f.emit("assembly", b"canonical-A")
            f.dodo._write_input_ledger(f.dodo._input_ledger("leaf"), {})
            with f.cache._pack(f.outputs("assembly")) as archive:
                f.backend.put(key, archive)

    def remote(label, requested, outputs):
        assert (label, requested) == ("assembly:leaf", key)
        f.emit("assembly", b"remote-canonical")

    monkeypatch.setattr(f.dodo._farm, "enabled", lambda: shortcut == "farm")
    monkeypatch.setattr(f.dodo, "_farm_build", remote)
    monkeypatch.setattr(f.dodo, "explode_plan", lambda *_a: pytest.fail("eager explode walk"))
    monkeypatch.setattr(f.dodo, "_explode_base_key", lambda *_a: pytest.fail("eager base key"))
    monkeypatch.setattr(f.dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("shortcut built locally"))
    with f.at("B"):
        f.run("assembly")
        f.identity("assembly")


_SHARED_MEMBER_STEMS = (
    "sh_vn_chain_link",
    "sh_vn_clamping_kit_hardware",
    "sh_vn_music_wire",
)


@pytest.fixture
def part_member_cache_action(tmp_path, monkeypatch):
    """Exercise the action with real inventory, stamps and neutral validation.

    Only host/cache boundaries are faked. The archive contains bytes selected by
    the production output list, including recursive render directories, rather
    than a restore mock that regenerates whatever the consumer expects.
    """
    import hashlib
    import json
    from types import SimpleNamespace

    import _artifact_cache
    import _part_configuration_exports as exports

    monkeypatch.setattr(_artifact_cache, "prewarm", lambda: None)
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    dodo = _load_dodo()
    state = SimpleNamespace(
        dodo=dodo, exports=exports, archive={}, restores=[], events=[],
        farm=False, build=None,
    )

    def use_root(root):
        monkeypatch.setattr(dodo, "CAD_OUT", root)

    use_root(tmp_path / "producer")
    # artefact_for normally resolves through the repository build graph; only
    # redirect its native location, leaving the cache inventory itself untouched.
    monkeypatch.setattr(
        dodo, "_sldprt",
        lambda stem: str(dodo.CAD_OUT / "sldprt" / f"{stem.replace('_', '-')}.SLDPRT"),
    )
    monkeypatch.setattr(dodo, "_part_file_deps", lambda *_args: [])
    monkeypatch.setattr(dodo, "_cache_key", lambda *_args: "a" * 64)
    monkeypatch.setattr(dodo._farm, "enabled", lambda: state.farm)

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def seed(stem):
        root = dodo.CAD_OUT
        native = Path(dodo._sldprt(stem))
        write(native, f"saved native for {stem}".encode())
        members = exports.configuration_producer_paths(stem, root)
        records = {}
        for configuration, paths in members.items():
            records[configuration] = {}
            for kind in ("step", "png"):
                path = paths[kind]
                data = f"{stem}/{configuration}/{kind} producer bytes".encode()
                write(path, data)
                records[configuration][kind] = {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
        certificate = {
            "schema": "harmonic-analyzer/part-member-neutral@1",
            "source": native.relative_to(root).as_posix(),
            "execution_identity": hashlib.sha256(native.read_bytes()).hexdigest(),
            "default_configuration": next(iter(members)),
            "configurations": records,
        }
        write(
            exports.configuration_manifest_path(stem, root),
            json.dumps(certificate).encode(),
        )

    def pack(outputs):
        archive = {}
        for output in outputs:
            files = output.rglob("*") if output.is_dir() else (output,)
            for path in files:
                if path.is_file():
                    archive[path.relative_to(dodo.CAD_OUT).as_posix()] = path.read_bytes()
        return archive

    def unpack():
        for name, data in state.archive.items():
            write(dodo.CAD_OUT / name, data)

    def restore(*_args):
        state.events.append("restore")
        hit = state.restores.pop(0)
        if hit:
            unpack()
        return hit

    def store(_key, outputs, _label):
        state.events.append("store")
        state.archive = pack(outputs)
        return "stored"

    def execute(*_args, **_kwargs):
        state.events.append("build")
        assert state.build is not None, "restored member set must not trigger COM"
        state.build()

    def farm_build(*_args):
        state.events.append("farm")
        unpack()

    monkeypatch.setattr(dodo._cache, "restore", restore)
    monkeypatch.setattr(dodo._cache, "store", store)
    monkeypatch.setattr(dodo, "_exec_com", execute)
    monkeypatch.setattr(dodo, "_farm_build", farm_build)
    monkeypatch.setattr(dodo, "_com_seat", lambda _label: contextlib.nullcontext(0.0))
    monkeypatch.setattr(
        dodo, "_sw_ensure_once", lambda: state.events.append("ensure"),
    )

    def corrupt(stem, defect):
        members = exports.configuration_producer_paths(stem, dodo.CAD_OUT)
        # Non-default members are not inside the default render directory: losing
        # their inventory entries must actually lose their bytes from the archive.
        paths = list(members.values())[-1]
        if defect == "missing-certificate":
            exports.configuration_manifest_path(stem, dodo.CAD_OUT).unlink()
        elif defect == "native-mismatch":
            Path(dodo._sldprt(stem)).write_bytes(b"another saved native identity")
        else:
            operation, kind = defect.split("-")
            if operation == "missing":
                paths[kind].unlink()
            else:
                data = paths[kind].read_bytes()
                paths[kind].write_bytes(bytes([data[0] ^ 1]) + data[1:])

    def prepare_restore(stem, route, defect=None):
        seed(stem)
        if defect:
            corrupt(stem, defect)
        state.archive = pack(dodo._part_cache_outputs(stem))
        use_root(tmp_path / "consumer")
        state.farm = route == "farm"
        state.restores = [False, True] if route == "reprobe" else [route == "probe"]

    state.use_root = use_root
    state.seed = seed
    state.corrupt = corrupt
    state.prepare_restore = prepare_restore
    state.run = lambda stem: dodo._cached_part_action(
        stem, tmp_path / f"build_{stem}.py",
    )
    return state


@pytest.mark.parametrize("stem", _SHARED_MEMBER_STEMS)
@pytest.mark.parametrize("route", ["probe", "reprobe", "farm"])
def test_part_member_cache_restores_complete_set_without_com(
    part_member_cache_action, stem, route,
):
    action = part_member_cache_action
    action.prepare_restore(stem, route)

    action.run(stem)

    root = action.dodo.CAD_OUT
    assert all(
        path.is_file()
        for path in action.exports.part_configuration_outputs(stem, root)
    )
    validated = action.exports.validate_member_exports(stem, root)
    assert validated
    assert "build" not in action.events
    assert "ensure" not in action.events
    assert "store" not in action.events
    assert action.events == {
        "probe": ["restore"],
        "reprobe": ["restore", "restore"],
        "farm": ["restore", "farm"],
    }[route]


@pytest.mark.parametrize("stem", _SHARED_MEMBER_STEMS)
@pytest.mark.parametrize("route", ["probe", "reprobe", "farm"])
@pytest.mark.parametrize(
    "defect",
    [
        "missing-certificate", "missing-step", "missing-png",
        "stale-step", "stale-png", "native-mismatch",
    ],
)
def test_part_member_cache_invalid_restored_set_fails_closed(
    part_member_cache_action, stem, route, defect,
):
    action = part_member_cache_action
    action.prepare_restore(stem, route, defect)

    with pytest.raises(RuntimeError, match=stem.replace("_", "-")):
        action.run(stem)

    # A claimed hit must not fork the cached native identity by rebuilding it.
    assert action.events == {
        "probe": ["restore"],
        "reprobe": ["restore", "restore"],
        "farm": ["restore", "farm"],
    }[route]


@pytest.mark.parametrize("stem", _SHARED_MEMBER_STEMS)
@pytest.mark.parametrize(
    "defect", ["missing-certificate", "missing-step", "missing-png", "native-mismatch"],
)
def test_part_member_incomplete_local_build_never_publishes(
    part_member_cache_action, stem, defect,
):
    action = part_member_cache_action
    action.restores = [False, False]

    def build():
        action.seed(stem)
        action.corrupt(stem, defect)

    action.build = build
    with pytest.raises(RuntimeError, match=stem.replace("_", "-")):
        action.run(stem)

    assert action.events == ["restore", "restore", "ensure", "build"]
    assert action.archive == {}


@pytest.mark.parametrize("stem", _SHARED_MEMBER_STEMS)
def test_part_member_local_publish_reconstructs_validated_set_on_new_root(
    part_member_cache_action, tmp_path, stem,
):
    action = part_member_cache_action
    action.restores = [False, False]
    action.build = lambda: action.seed(stem)

    action.run(stem)

    assert action.events == ["restore", "restore", "ensure", "build", "store"]
    producer_root = action.dodo.CAD_OUT
    expected = {
        path.relative_to(producer_root): path.read_bytes()
        for path in action.exports.part_configuration_outputs(stem, producer_root)
    }
    action.use_root(tmp_path / "fresh-submit")
    action.events.clear()
    action.restores = [True]
    action.build = None

    action.run(stem)

    root = action.dodo.CAD_OUT
    assert action.events == ["restore"]
    assert {path: (root / path).read_bytes() for path in expected} == expected
    assert action.exports.validate_member_exports(stem, root)


@pytest.mark.parametrize("stem", _SHARED_MEMBER_STEMS)
@pytest.mark.parametrize(
    "defect",
    [
        None, "missing-certificate", "certificate-identity",
        "missing-step", "missing-png", "stale-step", "stale-png",
    ],
)
def test_part_member_publication_loser_adopts_and_validates_winner_whole_set(
    canonical_publication, monkeypatch, stem, defect,
):
    """Real create-only publication must adopt member authority, not repair it."""
    import hashlib
    import json
    import _part_configuration_exports as exports

    f = canonical_publication
    dodo = f.dodo
    loser_identity = hashlib.sha256(b"B-native").hexdigest()
    winner_identity = hashlib.sha256(b"A-native").hexdigest()
    winner_bundle, observations, builds = {}, [], []
    monkeypatch.setattr(
        dodo, "_sldprt",
        lambda selected: str(
            dodo.CAD_OUT / "sldprt" / f"{selected.replace('_', '-')}.SLDPRT"
        ),
    )
    monkeypatch.setattr(dodo, "_part_cache_outputs", f.complete_part_cache_outputs)

    def script():
        # Both checkouts have this identical recipe; the member registry and real
        # production cache inventory still select the configured part's outputs.
        return dodo.REPO_ROOT / "cad" / "scripts" / "build_leaf.py"

    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def emit(producer):
        root = dodo.CAD_OUT
        native = Path(dodo._sldprt(stem))
        write(native, producer.encode() + b"-native")
        members = exports.configuration_producer_paths(stem, root)
        records = {}
        for configuration, paths in members.items():
            records[configuration] = {}
            for kind in ("step", "png"):
                path = paths[kind]
                data = f"{producer}/{configuration}/{kind} member bytes".encode()
                write(path, data)
                records[configuration][kind] = {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
        certificate = {
            "schema": "harmonic-analyzer/part-member-neutral@1",
            "source": native.relative_to(root).as_posix(),
            "execution_identity": hashlib.sha256(native.read_bytes()).hexdigest(),
            "default_configuration": next(iter(members)),
            "configurations": records,
        }
        write(
            exports.configuration_manifest_path(stem, root),
            json.dumps(certificate).encode(),
        )
        if producer == "B":
            write(dodo._stl(stem), b"loser-only STL")
            write(dodo._png_dir(stem) / "loser-only" / "stale.png", b"loser render")

    def snapshot():
        return {
            path.relative_to(dodo.CAD_OUT): path.read_bytes()
            for output in dodo._part_cache_outputs(stem)
            for path in (output.rglob("*") if output.is_dir() else (output,))
            if path.is_file()
        }

    def execute(*_args, **_kwargs):
        assert dodo.REPO_ROOT.name == "B"
        builds.append("B")
        # B has already missed both probes. Publish A's different native and
        # member bytes now, before B finishes its own otherwise valid build.
        with f.at("A"):
            emit("A")
            manifest = exports.configuration_manifest_path(stem, dodo.CAD_OUT)
            if defect == "missing-certificate":
                manifest.unlink()
            elif defect == "certificate-identity":
                certificate = json.loads(manifest.read_text(encoding="utf-8"))
                certificate["execution_identity"] = loser_identity
                manifest.write_text(json.dumps(certificate), encoding="utf-8")
            elif defect is not None:
                members = exports.configuration_producer_paths(stem, dodo.CAD_OUT)
                paths = list(members.values())[-1]
                operation, kind = defect.split("-")
                if operation == "missing":
                    paths[kind].unlink()
                else:
                    paths[kind].write_bytes(b"corrupt winner member")
            winner_bundle.update(snapshot())
            key = dodo._cache_key(dodo._part_file_deps(script(), stem), f"part:{stem}")
            # Transport integrity is valid even for a defective member bundle.
            # Its independent certificate must still fail closed on adoption.
            f.backend.put(key, f.cache._pack(dodo._part_cache_outputs(stem)))
        emit("B")

    stamp = dodo._stamp_part_execution
    validate = dodo._validate_part_configuration_outputs

    def record_stamp(selected):
        stamp(selected)
        observations.append(("stamp", f.identity("part", selected)))

    def record_validation(selected, key):
        observations.append(("validate", f.identity("part", selected)))
        validate(selected, key)

    monkeypatch.setattr(dodo, "_exec_com", execute)
    monkeypatch.setattr(dodo, "_stamp_part_execution", record_stamp)
    monkeypatch.setattr(dodo, "_validate_part_configuration_outputs", record_validation)
    with f.at("B"):
        sibling = dodo.CAD_OUT / "png" / "unrelated" / "keep.png"
        write(sibling, b"unrelated")
        if defect is None:
            dodo._cached_part_action(stem, script())
            assert exports.validate_member_exports(stem, dodo.CAD_OUT)
        else:
            with pytest.raises(RuntimeError, match="invalid member exports for cache key") as caught:
                dodo._cached_part_action(stem, script())
            assert "explicit forced cache refresh" in str(caught.value)
        assert f.identity("part", stem) == winner_identity != loser_identity
        assert snapshot() == winner_bundle
        # Check the full registry inventory independently of the packing helper:
        # absent canonical members/certificates must remove valid loser leftovers.
        for path in exports.part_configuration_outputs(stem, dodo.CAD_OUT):
            relative = path.relative_to(dodo.CAD_OUT)
            if relative in winner_bundle:
                assert path.read_bytes() == winner_bundle[relative]
            else:
                assert not path.exists()
        assert not dodo._stl(stem).exists()
        assert not (dodo._png_dir(stem) / "loser-only").exists()
        assert sibling.read_bytes() == b"unrelated"
    assert builds == ["B"]
    assert observations == [
        ("stamp", loser_identity),
        ("validate", loser_identity),
        ("validate", loser_identity),
        ("stamp", winner_identity),
        ("validate", winner_identity),
    ]
    assert [hit for name, _label, hit in f.probes if name == "B"] == [False, False, True]
    assert [(name, etag) for name, _key, etag in f.publications] == [
        ("A", None), ("B", None),
    ]
    assert not any(f.seats.values())
