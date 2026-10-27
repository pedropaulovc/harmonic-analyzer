"""Cached machinist verdicts and AST enforcement, without models or SolidWorks."""

from __future__ import annotations

import ast
from contextlib import nullcontext
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from doit.loader import load_tasks
from doit.task import dict_to_task

from _buildgraph import RECIPE_SKIP_MODULES
from _machinist_review_mode import MachinistReviewMode, mode_for_drawing
from machinist_review_config import (
    DEFAULT_EFFORTS,
    DEFAULT_MODELS,
    ENV_FIELDS,
    ENV_PREFIX,
    ReviewProfile,
    registered_review_profile,
    validate_review_profile,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_FIELDS = ReviewProfile._fields
PROFILE_CHANGES = [
    ("backend", "codex"),
    ("model", "claude-fable-5-1"),
    ("effort", "high"),
    ("judge_backend", "codex"),
    ("judge_model", "claude-fable-5-1"),
    ("judge_effort", "high"),
]
INVALID_PROFILE_VALUES = [
    ("backend", "other"), ("judge_backend", "other"),
    ("backend", ""), ("judge_backend", " codex"),
    ("backend", "Claude"), ("backend", "codex "),
    ("effort", "maximum"), ("judge_effort", "minimal"),
    ("effort", ""), ("judge_effort", "high "),
    ("model", ""), ("judge_model", " "),
    ("model", "gpt-6-astra\n"), ("judge_model", "--model=other"),
]


@pytest.fixture(scope="module")
def loaded_dodo():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
        for suffix in ENV_FIELDS.values():
            patch.delenv(ENV_PREFIX + suffix, raising=False)
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def dodo(loaded_dodo, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setattr(
        loaded_dodo, "_MACHINIST_REVIEW_PROFILE", registered_review_profile({})
    )
    loaded_dodo._reviewed_drawings.cache_clear()
    yield loaded_dodo
    loaded_dodo._reviewed_drawings.cache_clear()


# OFF never reaches the action: it yields no task.
REVIEWED_MODES = [MachinistReviewMode.LEARN, MachinistReviewMode.ENFORCE]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("raise RuntimeError('must not import')\n", MachinistReviewMode.OFF),
        ("MACHINIST_REVIEW = MachinistReviewMode.OFF\n", MachinistReviewMode.OFF),
        (
            "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n",
            MachinistReviewMode.ENFORCE,
        ),
        ("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n", MachinistReviewMode.LEARN),
        ("def helper():\n    MACHINIST_REVIEW = 'local'\n", MachinistReviewMode.OFF),
    ],
)
def test_mode_is_read_without_importing(tmp_path, source, expected):
    script = tmp_path / "draw_probe.py"
    script.write_text(source, encoding="utf-8")
    assert mode_for_drawing(script) is expected


@pytest.mark.parametrize(
    "source",
    [
        "MACHINIST_REVIEW = 'enforce'",
        "MACHINIST_REVIEW = True",
        "MACHINIST_REVIEW = MachinistReviewMode.UNKNOWN",
        "MACHINIST_REVIEW = Other.ENFORCE",
        "MACHINIST_REVIEW = choose_mode()",
        "MACHINIST_REVIEW: str = MachinistReviewMode.ENFORCE",
        "if enabled:\n    MACHINIST_REVIEW = MachinistReviewMode.ENFORCE",
        "MACHINIST_REVIEW = MachinistReviewMode.LEARN\nMACHINIST_REVIEW = MachinistReviewMode.ENFORCE",
        "from settings import MACHINIST_REVIEW",
        "def MACHINIST_REVIEW(): pass",
    ],
)
def test_invalid_modes_fail_loud_at_graph_load(tmp_path, source):
    script = tmp_path / "draw_probe.py"
    script.write_text(source + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="MACHINIST_REVIEW must be"):
        mode_for_drawing(script)


def _local_import_closure(entry: Path) -> set[str]:
    """Unlike the CAD recipe walker, include non-underscore review modules too."""
    scripts = entry.parent
    found = set()
    pending = [entry]
    while pending:
        path = pending.pop()
        if path.name in found or path.name in RECIPE_SKIP_MODULES:
            continue
        found.add(path.name)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                local = scripts / f"{name}.py"
                # Registry is only used by interactive name/--all selectors.
                # The leaf supplies PDF/kind/name and always passes --force,
                # so the lazy _drawing_diff precheck import is unreachable too.
                if local.is_file() and name not in {"_drawing_registry", "_drawing_diff"}:
                    pending.append(local)
    return found


def test_declared_review_modules_equal_the_real_import_closure(dodo):
    assert _local_import_closure(dodo.SCRIPTS_DIR / "machinist_review.py") == set(
        dodo._MACHINIST_REVIEW_MODULES
    )


def test_forced_leaf_never_imports_or_calls_diff(inputs, monkeypatch):
    import builtins
    import sys

    original_import = builtins.__import__

    def no_diff_import(name, *args, **kwargs):
        assert name != "_drawing_diff", "forced leaf imported PDF diff implementation"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_diff_import)
    spec = importlib.util.spec_from_file_location(
        "_forced_leaf_review", REPO_ROOT / "cad" / "scripts" / "machinist_review.py"
    )
    review = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, review)
    spec.loader.exec_module(review)
    calls = []

    def clean_review(package, **kwargs):
        calls.append(package)
        return SimpleNamespace(
            verdict={
                "verdict": "SHIP",
                "summary": "No findings.",
                **{category: [] for category in review.FINDING_KEYS},
            },
            error=None,
            blind=True,
            passed=True,
            sheet_count=1,
            extra={"inspection_proven": True},
        )

    def no_precheck(*args, **kwargs):
        pytest.fail("forced leaf invoked precheck despite --force")

    monkeypatch.setattr(review, "review_package", clean_review)
    monkeypatch.setattr(review, "_review_session", no_precheck)
    command = inputs.module._machinist_review_command(
        "probe", inputs.module._machinist_review_profile()
    )
    assert review.main(command[2:]) == 0
    assert len(calls) == 3
    assert all(package.before_sources == () for package in calls)
    aggregate = inputs.module._read_machinist_aggregate("probe")
    assert aggregate["precheck"]["forced"] is True
    assert aggregate["precheck"]["skipped"] is False
    assert aggregate["error"] is None


def test_explicit_pdf_command_cannot_select_a_registry_package(dodo):
    stem = "pd_platen_guide"
    command = dodo._machinist_review_command(stem, dodo._machinist_review_profile())
    assert command[0] == dodo.sys.executable
    assert command[2:] == [
        "--pdf",
        str(dodo.DRAWINGS_BY_NAME[stem].outputs["pdf"]),
        "--name",
        stem,
        "--kind",
        "part",
        "--force",
        "--runs",
        "3",
        "--report-dir",
        str(dodo._machinist_review_dir(stem)),
        "--reviewer",
        "claude",
        "--model",
        "claude-opus-5-5",
        "--effort",
        "medium",
        "--judge-reviewer",
        "claude",
        "--judge-model",
        "claude-opus-5-5",
        "--judge-effort",
        "medium",
    ]


@pytest.fixture
def inputs(dodo, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    scripts = root / "cad" / "scripts"
    prompts = scripts / "prompts"
    prompts.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\ndependencies = ["claude-agent-sdk==0.1.0"]\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        '[[package]]\nname = "claude-agent-sdk"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    for name in dodo._MACHINIST_REVIEW_MODULES:
        (scripts / name).write_text("# review code\n", encoding="utf-8")
    (scripts / "_drawing_diff.py").write_text("# unused PDF diff\n", encoding="utf-8")
    pairing = root / "cad" / "comparisons" / "tools" / "release_diff.py"
    pairing.parent.mkdir(parents=True)
    pairing.write_text("# release identity pairing\n", encoding="utf-8")
    for name in (
        "machinist_review_part.md",
        "machinist_review_assembly.md",
        "machinist_review_part_severity.md",
        "machinist_review_assembly_severity.md",
        "machinist_review_schema.json",
        "machinist_review_judge.md",
        "machinist_review_judge_schema.json",
        "machinist_review_precheck.md",
        "machinist_review_precheck_schema.json",
    ):
        (prompts / name).write_text("{}", encoding="utf-8")
    guidelines = root / "cad" / "docs" / "drawing-guidelines.md"
    guidelines.parent.mkdir()
    guidelines.write_text("guidelines", encoding="utf-8")
    config = root / "cad" / "config"
    (config / "parts").mkdir(parents=True)
    (config / "assemblies").mkdir()
    for name in ("current-identity-map.json", "identity-migration-map.json"):
        (config / name).write_text("{}", encoding="utf-8")
    exception = config / "parts" / "probe.yaml"
    exception.write_text("probe: {}\n", encoding="utf-8")
    pdf = root / "cad" / "out" / "pdf" / "probe.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"PDF fixture")
    draw = scripts / "draw_probe.py"
    draw.write_text("# LEARN by default\n", encoding="utf-8")
    registry = scripts / "_drawing_registry.py"
    registry.write_text("# unrelated registry row\n", encoding="utf-8")
    spec = SimpleNamespace(
        outputs={"pdf": pdf},
        source_kind="part",
        script=draw,
    )
    monkeypatch.setattr(dodo, "REPO_ROOT", root)
    monkeypatch.setattr(dodo, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(dodo, "CONFIG_DIR", config)
    monkeypatch.setattr(dodo, "REPORTS", root / "cad" / "out" / "reports")
    monkeypatch.setattr(dodo, "DRAWINGS_BY_NAME", {"probe": spec})
    monkeypatch.setattr(dodo._cache, "REPO_ROOT", root)
    return SimpleNamespace(
        module=dodo,
        root=root,
        scripts=scripts,
        pdf=pdf,
        exception=exception,
        prompts=prompts,
        draw=draw,
        registry=registry,
        spec=spec,
    )


def _review_key(dodo, stem="probe", label=None):
    return dodo._machinist_review_cache_key(
        stem, dodo._machinist_review_profile(), label
    )


def test_key_changes_only_with_review_inputs(inputs):
    dodo = inputs.module

    def key():
        return _review_key(dodo)

    initial = key()
    changed_inputs = [
        Path(path) for path in dodo._machinist_review_file_deps("probe")
    ]
    for path in changed_inputs:
        before = path.read_bytes()
        path.write_bytes(before + b"\nchanged: true\n")
        assert key() != initial, path
        path.write_bytes(before)
    inputs.registry.write_text("# registry changes do not affect explicit PDFs\n")
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n")
    assert key() == initial
    inputs.exception.unlink()
    assert key() != initial
    inputs.spec.source_kind = "assembly"
    assert key() != initial


@pytest.mark.parametrize("manifest", ["pyproject.toml", "uv.lock"])
def test_dependency_manifest_edits_rekey_review(inputs, manifest):
    dodo = inputs.module
    path = inputs.root / manifest
    initial = _review_key(dodo)
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("0.1.0", "0.2.0"), encoding="utf-8")
    assert _review_key(dodo) != initial
    # Whole-manifest hashing intentionally includes non-SDK dependency edits.
    path.write_text(original + "\n# unrelated dependency edit\n", encoding="utf-8")
    assert _review_key(dodo) != initial
    path.write_text(original, encoding="utf-8")
    assert _review_key(dodo) == initial


@pytest.mark.parametrize(
    "relative_path",
    [
        "cad/scripts/_drawing_diff.py",
        "cad/comparisons/tools/release_diff.py",
        "cad/config/current-identity-map.json",
        "cad/config/identity-migration-map.json",
        "cad/scripts/prompts/machinist_review_precheck.md",
        "cad/scripts/prompts/machinist_review_precheck_schema.json",
    ],
)
def test_bypassed_precheck_inputs_do_not_invalidate_forced_review_cache(
    inputs, relative_path
):
    dodo = inputs.module
    path = inputs.root / relative_path
    assert str(path.resolve()) not in dodo._machinist_review_file_deps("probe")
    initial = _review_key(dodo)
    path.write_bytes(path.read_bytes() + b"\nchanged precheck dependency\n")
    assert _review_key(dodo) == initial


def test_key_tracks_only_selected_kind_severity_contract(inputs):
    dodo = inputs.module

    def key():
        return _review_key(dodo)

    for selected, opposite in (("part", "assembly"), ("assembly", "part")):
        inputs.spec.source_kind = selected
        initial = key()
        for kind in (selected, opposite):
            path = inputs.prompts / f"machinist_review_{kind}_severity.md"
            before = path.read_bytes()
            path.write_bytes(before + b"\nchanged: true\n")
            if kind == selected:
                assert key() != initial, path
            else:
                assert key() == initial, path
            path.write_bytes(before)
            assert key() == initial


def test_review_keys_exclude_the_shared_recipe_skip_set(inputs, monkeypatch):
    dodo = inputs.module
    for name in RECIPE_SKIP_MODULES:
        (inputs.scripts / name).write_text("# observation-only infrastructure\n")
    deps = dodo._machinist_review_file_deps("probe")
    assert {Path(path).name for path in deps}.isdisjoint(RECIPE_SKIP_MODULES)
    initial = _review_key(dodo)
    # An inert import entering the explicit manifest must still follow the
    # recipe policy, rather than accidentally charging for another review.
    monkeypatch.setattr(
        dodo,
        "_MACHINIST_REVIEW_MODULES",
        (*dodo._MACHINIST_REVIEW_MODULES, *sorted(RECIPE_SKIP_MODULES)),
    )
    assert dodo._machinist_review_file_deps("probe") == deps
    for name in RECIPE_SKIP_MODULES:
        (inputs.scripts / name).write_text("# logging-only edit must not re-review\n")
        assert _review_key(dodo) == initial


def test_assembly_exception_uses_bare_dashed_config_stem(inputs):
    dodo = inputs.module
    inputs.spec.source_kind = "assembly"
    dodo.DRAWINGS_BY_NAME["probe_assembly"] = inputs.spec
    path = dodo.CONFIG_DIR / "assemblies" / "probe.yaml"
    path.write_text("machinist_exceptions: []\n")
    assert str(path.resolve()) in dodo._machinist_review_file_deps("probe_assembly")


def test_mode_and_input_set_changes_invalidate_doit_but_not_the_verdict_key(
    inputs,
    monkeypatch,
):
    dodo = inputs.module
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n")

    current, saved = _review_freshness(dodo, {})
    assert not current
    assert _review_freshness(dodo, saved)[0]
    key = _review_key(dodo)
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n")
    current, enforced_saved = _review_freshness(dodo, saved)
    assert not current
    assert _review_key(dodo) == key
    inputs.exception.unlink()
    assert not _review_freshness(dodo, enforced_saved)[0]


def _review_freshness(dodo, values):
    """Exercise doit's configure/evaluate/success-save lifecycle without actions."""
    dodo._reviewed_drawings.cache_clear()
    task = dict_to_task(next(dodo._machinist_review_tasks()))
    checker, args, kwargs = task.uptodate[0]
    assert task.value_savers, "config_changed must register its successful-run saver"
    current = checker(task, values, *args, **kwargs)
    task.save_extra_values()
    return current, dict(task.values)


@pytest.fixture
def review_freshness(inputs, monkeypatch):
    monkeypatch.setattr(inputs.module, "_drawing_order", lambda: ["probe"])
    inputs.draw.write_text(
        "MACHINIST_REVIEW = MachinistReviewMode.LEARN\n", encoding="utf-8"
    )
    return lambda values: _review_freshness(inputs.module, values)


@pytest.mark.parametrize(("field", "value"), PROFILE_CHANGES)
def test_each_resolved_field_rekeys_review_and_invalidates_local_freshness(
    inputs, monkeypatch, review_freshness, field, value
):
    dodo = inputs.module
    label = "check:machinist_review:probe"
    defaults = registered_review_profile({})
    initial = _review_key(dodo, label=label)
    current, saved = review_freshness({})
    assert not current
    assert review_freshness(saved)[0]
    # Isolate exactly one field, including each backend independently. A model's
    # availability is a provider concern, not a reason to normalize its key.
    changed = defaults._replace(**{field: value})
    assert {
        name for name in PROFILE_FIELDS
        if getattr(defaults, name) != getattr(changed, name)
    } == {field}
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", changed)
    assert _review_key(dodo, label=label) != initial
    current, changed_saved = review_freshness(saved)
    assert not current
    assert review_freshness(changed_saved)[0]
    command = dodo._machinist_review_command("probe", changed)
    for name, selected in changed._asdict().items():
        option = "--" + ENV_FIELDS[name].lower().replace("_", "-")
        assert command[command.index(option) + 1] == selected
    # Returning to the old profile must not reuse the newer profile's stamp.
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", defaults)
    assert _review_key(dodo, label=label) == initial
    assert not review_freshness(changed_saved)[0]


def test_explicit_default_profile_has_the_same_key_and_local_freshness(
    inputs, monkeypatch, review_freshness
):
    dodo = inputs.module
    defaults = registered_review_profile({})
    explicit = registered_review_profile({
        ENV_PREFIX + ENV_FIELDS[field]: value
        for field, value in defaults._asdict().items()
    })
    assert explicit == defaults
    label = "check:machinist_review:probe"
    initial = _review_key(dodo, label=label)
    current, saved = review_freshness({})
    assert not current
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", explicit)
    assert _review_key(dodo, label=label) == initial
    assert review_freshness(saved)[0]


@pytest.mark.parametrize(("field", "value"), PROFILE_CHANGES)
def test_reviewer_selection_does_not_rekey_real_native_leaves(
    dodo, monkeypatch, field, value
):
    stem = "sm_summing_lever"
    part = next(
        path for path in dodo.part_scripts() if path.stem == f"build_{stem}"
    )
    rows = [
        (f"part:{stem}", dodo._part_file_deps(part, stem)),
        (f"drawing:{stem}", dodo._drawing_file_deps(stem)),
    ]
    config_path = str(dodo.SCRIPTS_DIR / "machinist_review_config.py")
    # Even a native dependency on the canonical config source must get the
    # plain content digest, never the review-only contextual selection.
    rows.append(("part:config_probe", [config_path]))
    initial = [dodo._cache_key(deps, label) for label, deps in rows]
    plain = [
        dodo._cache.cache_key(deps, dodo.ContentChecker._digest)
        for _label, deps in rows
    ]
    assert initial == plain
    monkeypatch.setattr(
        dodo, "_MACHINIST_REVIEW_PROFILE",
        registered_review_profile({})._replace(**{field: value}),
    )
    assert [dodo._cache_key(deps, label) for label, deps in rows] == initial


@pytest.mark.parametrize("manifest", ["pyproject.toml", "uv.lock"])
def test_dependency_manifest_edits_rekey_review_not_native_geometry(
    dodo, monkeypatch, manifest
):
    stem = "sm_summing_lever"
    part = next(
        path for path in dodo.part_scripts() if path.stem == f"build_{stem}"
    )
    rows = [
        (f"part:{stem}", dodo._part_file_deps(part, stem)),
        (f"drawing:{stem}", dodo._drawing_file_deps(stem)),
    ]
    initial = [dodo._cache_key(deps, label) for label, deps in rows]
    review_key = _review_key(dodo, stem)
    manifest_path = (dodo.REPO_ROOT / manifest).resolve()
    original_digest = dodo.ContentChecker._digest

    def changed_manifest_digest(path):
        source = original_digest(path)
        if Path(path).resolve() == manifest_path:
            return source + "-changed-dependency-manifest"
        return source

    # Simulate a manifest-only content change without touching this checkout.
    monkeypatch.setattr(
        dodo.ContentChecker, "_digest", staticmethod(changed_manifest_digest)
    )
    assert _review_key(dodo, stem) != review_key
    assert [dodo._cache_key(deps, label) for label, deps in rows] == initial


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, ReviewProfile(
            "claude", "claude-opus-5-5", "medium",
            "claude", "claude-opus-5-5", "medium",
        )),
        ({"HARMONIC_MACHINIST_REVIEWER": "codex"}, ReviewProfile(
            "codex", "gpt-6-astra", "low", "codex", "gpt-6-astra", "low",
        )),
        ({"HARMONIC_MACHINIST_JUDGE_REVIEWER": "codex"}, ReviewProfile(
            "claude", "claude-opus-5-5", "medium", "codex", "gpt-6-astra", "low",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_JUDGE_REVIEWER": "claude",
        }, ReviewProfile(
            "codex", "gpt-6-astra", "low", "claude", "claude-opus-5-5", "medium",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_MODEL": "provider/reviewer:v1",
            "HARMONIC_MACHINIST_EFFORT": "high",
            "HARMONIC_MACHINIST_JUDGE_REVIEWER": "claude",
            "HARMONIC_MACHINIST_JUDGE_MODEL": "provider/judge:v2",
            "HARMONIC_MACHINIST_JUDGE_EFFORT": "xhigh",
        }, ReviewProfile(
            "codex", "provider/reviewer:v1", "high",
            "claude", "provider/judge:v2", "xhigh",
        )),
    ],
)
def test_registered_backend_fallback_and_explicit_stage_precedence(
    environment, expected
):
    assert registered_review_profile(environment) == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (field, value) for field, value in PROFILE_CHANGES
        if field not in ("backend", "judge_backend")
    ],
)
def test_explicit_model_and_effort_overrides_are_stage_local(field, value):
    defaults = registered_review_profile({
        "HARMONIC_MACHINIST_REVIEWER": "codex",
    })
    selected = registered_review_profile({
        "HARMONIC_MACHINIST_REVIEWER": "codex",
        ENV_PREFIX + ENV_FIELDS[field]: value,
    })
    assert selected == defaults._replace(**{field: value})


@pytest.mark.parametrize("effort", ("high", "max"))
def test_codex_configuration_is_explicit_for_both_stages(dodo, monkeypatch, effort):
    profile = registered_review_profile({
        "HARMONIC_MACHINIST_REVIEWER": "codex",
        "HARMONIC_MACHINIST_EFFORT": effort,
        "HARMONIC_MACHINIST_JUDGE_EFFORT": effort,
    })
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", profile)
    command = dodo._machinist_review_command(
        "sm_summing_lever", dodo._machinist_review_profile()
    )
    assert command[-12:] == [
        "--reviewer", "codex", "--model", "gpt-6-astra", "--effort", effort,
        "--judge-reviewer", "codex", "--judge-model", "gpt-6-astra",
        "--judge-effort", effort,
    ]


def test_environment_is_not_reread_between_freshness_key_and_command(
    inputs, monkeypatch, review_freshness
):
    dodo = inputs.module
    label = "check:machinist_review:probe"
    profile = dodo._machinist_review_profile()
    key = _review_key(dodo, label=label)
    command = dodo._machinist_review_command("probe", profile)
    current, saved = review_freshness({})
    assert not current
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-after-import")
    assert dodo._machinist_review_profile() is profile
    assert _review_key(dodo, label=label) == key
    assert dodo._machinist_review_command(
        "probe", dodo._machinist_review_profile()
    ) == command
    assert review_freshness(saved)[0]


def test_registered_profile_uses_environment_only_when_mapping_is_omitted(monkeypatch):
    for suffix in ENV_FIELDS.values():
        monkeypatch.delenv(ENV_PREFIX + suffix, raising=False)
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "codex")
    assert registered_review_profile() == registered_review_profile({
        "HARMONIC_MACHINIST_REVIEWER": "codex",
    })
    assert registered_review_profile({}).backend == "claude"


def test_validation_does_not_reresolve_environment_or_provider_defaults(monkeypatch):
    profile = registered_review_profile({})
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-after-resolution")
    for backend in ("claude", "codex"):
        monkeypatch.setitem(DEFAULT_MODELS, backend, "changed-model")
        monkeypatch.setitem(DEFAULT_EFFORTS, backend, "invalid-default")
    assert validate_review_profile(profile) is None


@pytest.mark.parametrize("stage", ("", "judge_"))
@pytest.mark.parametrize("model", ("claude-opus-5-5", "claude-fable-5-1"))
def test_claude_xhigh_effort_is_preserved(stage, model):
    profile = registered_review_profile({
        ENV_PREFIX + ENV_FIELDS[stage + "model"]: model,
        ENV_PREFIX + ENV_FIELDS[stage + "effort"]: "xhigh",
    })
    assert getattr(profile, stage + "model") == model
    assert getattr(profile, stage + "effort") == "xhigh"


def test_graph_load_freezes_all_environment_overrides_before_prewarm(
    dodo, monkeypatch
):
    expected = ReviewProfile(
        "codex", "explicit-review", "max",
        "claude", "explicit-judge", "xhigh",
    )
    for field, value in expected._asdict().items():
        monkeypatch.setenv(ENV_PREFIX + ENV_FIELDS[field], value)
    spec = importlib.util.spec_from_file_location(
        "configured_review_dodo", REPO_ROOT / "dodo.py"
    )
    module = importlib.util.module_from_spec(spec)
    prewarmed = []

    def prewarm():
        assert module._MACHINIST_REVIEW_PROFILE == expected
        prewarmed.append(module._MACHINIST_REVIEW_PROFILE)

    monkeypatch.setattr(dodo._cache, "prewarm", prewarm)
    spec.loader.exec_module(module)
    assert prewarmed == [expected]
    frozen = module._machinist_review_profile()
    assert frozen == expected
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-after-import")
    assert module._machinist_review_profile() is frozen


@pytest.mark.parametrize(("field", "value"), INVALID_PROFILE_VALUES)
def test_invalid_profile_fails_graph_load_before_cache_or_native_work(
    dodo, monkeypatch, field, value
):
    for suffix in ENV_FIELDS.values():
        monkeypatch.delenv(ENV_PREFIX + suffix, raising=False)
    variable = ENV_PREFIX + ENV_FIELDS[field]
    monkeypatch.setenv(variable, value)
    monkeypatch.setattr(
        dodo._cache, "prewarm",
        lambda: pytest.fail("invalid review selection reached cache prewarming"),
    )
    spec = importlib.util.spec_from_file_location(
        "invalid_review_dodo", REPO_ROOT / "dodo.py"
    )
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(ValueError, match=variable):
        spec.loader.exec_module(module)


@pytest.mark.parametrize(("field", "value"), PROFILE_CHANGES)
def test_cache_status_probes_the_same_selected_review_key(
    inputs, monkeypatch, field, value
):
    dodo = inputs.module
    label = "check:machinist_review:probe"
    defaults = dodo._machinist_review_profile()
    default_key = _review_key(dodo, label=label)
    profile = defaults._replace(**{field: value})
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", profile)
    deps = dodo._machinist_review_file_deps("probe")
    expected = _review_key(dodo, label=label)
    assert expected != default_key
    native_label = "part:config_probe"
    native_deps = [str(inputs.scripts / "machinist_review_config.py")]
    native_key = dodo._cache_key(native_deps, native_label)
    assert native_key == dodo._cache.cache_key(
        native_deps, dodo.ContentChecker._digest
    )
    probed = []
    monkeypatch.setattr(
        dodo, "_cache_rows",
        lambda: [(label, deps), (native_label, native_deps)],
    )
    monkeypatch.setattr(dodo._cache, "probe", lambda key: probed.append(key))
    monkeypatch.setattr(dodo._cache, "last_stored_key", lambda _label: None)
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-after-resolution")
    dodo._cache_status([])
    assert probed == [expected, native_key]



def test_review_telemetry_has_a_stage_resource(dodo):
    assert dodo._stage_name("check:machinist_review:probe") == "check-machinist-review"


@pytest.fixture
def action(inputs, monkeypatch):
    dodo = inputs.module
    original_probe = dodo._probe_cache
    original_store = dodo._cache.store
    original_key = dodo._machinist_review_cache_key
    profile = dodo._machinist_review_profile()
    calls = {"run": 0, "store": 0, "warnings": [], "probe": []}
    state = {"verdict": "SHIP", "error": None, "hit": False, "code": 0}
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", lambda *_args: "a" * 64)
    monkeypatch.setattr(
        dodo._telemetry,
        "span",
        lambda *_args, **_kwargs: nullcontext(
            SimpleNamespace(set_attribute=lambda *_args: None)
        ),
    )
    monkeypatch.setattr(dodo._telemetry, "warn", calls["warnings"].append)

    def forbidden(*_args, **_kwargs):
        pytest.fail("review touched COM or dispatched to the farm")

    monkeypatch.setattr(dodo, "_com_seat", forbidden)
    monkeypatch.setattr(dodo, "_farm_build", forbidden)

    def report():
        directory = dodo._machinist_review_dir("probe")
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "probe.aggregate.json").write_text(
            json.dumps(
                {
                    "name": "probe",
                    "kind": "part",
                    "verdict": state["verdict"],
                    "gating_count": 0 if state["verdict"] == "SHIP" else 2,
                    "error": state["error"],
                }
            ),
            encoding="utf-8",
        )

    def probe(_key, outputs, label, _span):
        calls["probe"].append(label)
        if state["hit"]:
            report()
            return "hit"
        return "miss"

    def run(*_args, **_kwargs):
        calls["run"] += 1
        report()
        return state["code"]

    def store(_key, outputs, _label):
        calls["store"] += 1
        assert outputs == [dodo._machinist_review_dir("probe")]
        assert not dodo._machinist_review_stamp("probe").exists()
        return "stored"

    monkeypatch.setattr(dodo, "_probe_cache", probe)
    monkeypatch.setattr(dodo, "_run_subprocess", run)
    monkeypatch.setattr(dodo._cache, "store", store)
    return SimpleNamespace(
        dodo=dodo,
        calls=calls,
        state=state,
        original_probe=original_probe,
        profile=profile,
        original_store=original_store,
        original_key=original_key,
    )


@pytest.fixture
def review_sessions(monkeypatch):
    """Replace only the model-session boundary, not CLI/aggregate consumers."""
    import machinist_review as mr

    seen = []

    def session(package, **kwargs):
        findings = kwargs.get("judge_findings")
        role = "judge" if findings is not None else "reviewer"
        seen.append((role, kwargs["reviewer"], kwargs["model"], kwargs["effort"]))
        claim = {
            "where": "front view", "issue": "hermetic claim", "fix": "check the sheet",
        }
        if findings is None:
            verdict = {
                "verdict": "FIX", "summary": "requires adjudication",
                "blockers": [claim], "over_specification": [], "clarity": [], "minor": [],
            }
        else:
            verdict = {"clusters": [{
                **claim, "category": "blockers", "decision": "rejected",
                "member_ids": [finding["id"] for finding in findings],
                "reason": "The hermetic judge rejects this synthetic claim.",
            }]}
        return replace(
            mr._failed_review(
                package, kwargs["reviewer"], kwargs["model"], kwargs["effort"],
                [mr._sha256(source) for source in package.sources], "unused",
            ),
            verdict=verdict, error=None, passed=findings is not None, sheet_count=1,
            prompt_sha256="hermetic-session", extra={"inspection_proven": True},
        )

    monkeypatch.setattr(mr, "_review_session", session)
    return SimpleNamespace(module=mr, seen=seen)


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, ReviewProfile(
            "claude", "claude-opus-5-5", "medium",
            "claude", "claude-opus-5-5", "medium",
        )),
        ({"HARMONIC_MACHINIST_REVIEWER": "codex"}, ReviewProfile(
            "codex", "gpt-6-astra", "low", "codex", "gpt-6-astra", "low",
        )),
        ({"HARMONIC_MACHINIST_JUDGE_REVIEWER": "codex"}, ReviewProfile(
            "claude", "claude-opus-5-5", "medium", "codex", "gpt-6-astra", "low",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_JUDGE_REVIEWER": "claude",
        }, ReviewProfile(
            "codex", "gpt-6-astra", "low", "claude", "claude-opus-5-5", "medium",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_MODEL": "explicit-review",
            "HARMONIC_MACHINIST_EFFORT": "high",
            "HARMONIC_MACHINIST_JUDGE_REVIEWER": "claude",
            "HARMONIC_MACHINIST_JUDGE_MODEL": "explicit-judge",
            "HARMONIC_MACHINIST_JUDGE_EFFORT": "low",
        }, ReviewProfile(
            "codex", "explicit-review", "high", "claude", "explicit-judge", "low",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_EFFORT": "high",
            "HARMONIC_MACHINIST_JUDGE_EFFORT": "high",
        }, ReviewProfile(
            "codex", "gpt-6-astra", "high", "codex", "gpt-6-astra", "high",
        )),
        ({
            "HARMONIC_MACHINIST_REVIEWER": "codex",
            "HARMONIC_MACHINIST_EFFORT": "max",
            "HARMONIC_MACHINIST_JUDGE_EFFORT": "max",
        }, ReviewProfile(
            "codex", "gpt-6-astra", "max", "codex", "gpt-6-astra", "max",
        )),
    ],
)
def test_registered_selection_reaches_real_cli_reviewers_and_judge(
    action, review_sessions, monkeypatch, environment, expected
):
    dodo = action.dodo
    # Replacing the process snapshot simulates a newly imported dodo, rather
    # than depending on forbidden ambient environment rereads after import.
    profile = registered_review_profile(environment)
    assert profile == expected
    monkeypatch.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", profile)
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.ENFORCE
    )
    task = next(dodo._machinist_review_tasks())
    # Each task captures one profile for freshness, command and key, even if a
    # later process configuration or the ambient environment changes.
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-after-snapshot")
    monkeypatch.setattr(
        dodo, "_MACHINIST_REVIEW_PROFILE", profile._replace(model="later-model")
    )
    keyed_profiles = []
    monkeypatch.setattr(
        dodo, "_machinist_review_cache_key",
        lambda stem, profile, label: keyed_profiles.append(profile) or "a" * 64,
    )

    def run(command, *_args, **_kwargs):
        return review_sessions.module.main(command[2:])

    monkeypatch.setattr(dodo, "_run_subprocess", run)
    execute, arguments = task["actions"][0]
    execute(*arguments)
    assert keyed_profiles == [profile]
    reviewer = expected[:3]
    judge = expected[3:]
    assert sorted(review_sessions.seen) == sorted([
        ("reviewer", *reviewer), ("reviewer", *reviewer), ("reviewer", *reviewer),
        ("judge", *judge),
    ])
    aggregate = dodo._read_machinist_aggregate("probe")
    assert (aggregate["reviewer"], aggregate["model"], aggregate["effort"]) == reviewer
    assert tuple(
        aggregate["judge"][name] for name in ("reviewer", "model", "effort")
    ) == judge
    assert aggregate["judge"]["skipped"] is False
    assert aggregate["verdict"] == "SHIP"
    assert dodo._machinist_review_stamp("probe").is_file()


@pytest.mark.parametrize(
    ("flags", "reviewer", "judge"),
    [
        ([], ("claude", "claude-opus-5-5", "medium"),
         ("claude", "claude-opus-5-5", "medium")),
        (["--reviewer", "codex"], ("codex", "gpt-6-astra", "low"),
         ("claude", "claude-opus-5-5", "medium")),
        (["--reviewer", "codex", "--model", "explicit-review", "--effort", "high",
          "--judge-reviewer", "claude", "--judge-model", "explicit-judge",
          "--judge-effort", "low"],
         ("codex", "explicit-review", "high"), ("claude", "explicit-judge", "low")),
    ],
)
def test_standalone_cli_ignores_all_registered_environment_overrides(
    inputs, review_sessions, monkeypatch, tmp_path, flags, reviewer, judge
):
    for suffix in ENV_FIELDS.values():
        monkeypatch.setenv(ENV_PREFIX + suffix, "invalid-for-registered-gate")
    assert review_sessions.module.main([
        "--pdf", str(inputs.pdf), "--name", "probe", "--kind", "part", "--force",
        "--report-dir", str(tmp_path / "standalone"), *flags,
    ]) == 0
    assert sorted(review_sessions.seen) == sorted([
        ("reviewer", *reviewer), ("reviewer", *reviewer), ("reviewer", *reviewer),
        ("judge", *judge),
    ])


@pytest.mark.parametrize(
    ("profile", "error"),
    [
        (None, "ReviewProfile"),
        ("codex", "ReviewProfile"),
        (registered_review_profile({})._asdict(), "ReviewProfile"),
        (tuple(registered_review_profile({})), "ReviewProfile"),
        *[
            (
                registered_review_profile({})._replace(**{field: value}),
                ENV_PREFIX + ENV_FIELDS[field],
            )
            for field, value in INVALID_PROFILE_VALUES
        ],
        *[
            (
                registered_review_profile({})._replace(**{field: None}),
                ENV_PREFIX + ENV_FIELDS[field],
            )
            for field in PROFILE_FIELDS
        ],
    ],
)
def test_direct_action_rejects_unresolved_or_invalid_profile_before_work(
    action, monkeypatch, profile, error
):
    dodo = action.dodo
    stamp = dodo._machinist_review_stamp("probe")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("prior success")
    directory = dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    evidence = directory / "prior-evidence.json"
    evidence.write_text("prior evidence")

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid action profile performed review work")

    monkeypatch.setattr(dodo, "_machinist_review_dir", forbidden)
    monkeypatch.setattr(dodo, "_machinist_review_file_deps", forbidden)
    monkeypatch.setattr(dodo, "_probe_cache", forbidden)
    monkeypatch.setattr(dodo, "_run_subprocess", forbidden)
    monkeypatch.setattr(dodo._cache, "store", forbidden)
    with pytest.raises(ValueError, match=error):
        dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.ENFORCE, profile
        )
    assert stamp.read_text() == "prior success"
    assert evidence.read_text() == "prior evidence"


@pytest.mark.parametrize(("field", "value"), PROFILE_CHANGES)
def test_effective_profile_invalidates_real_freshness_and_cached_action(
    action, review_sessions, monkeypatch, field, value
):
    from doit.task import Stream

    from test_artifact_cache import _BlockBlobService

    dodo = action.dodo
    cache = dodo._cache
    root = dodo.REPO_ROOT
    label = "check:machinist_review:probe"
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", root / "cad" / "out")
    monkeypatch.setattr(cache, "_REPORTS", dodo.REPORTS)
    monkeypatch.setattr(cache, "_EVENTS_LOG", dodo.REPORTS / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", dodo.REPORTS / "cache-keys")
    monkeypatch.setattr(cache, "_BACKEND", cache._BlobBackend(_BlockBlobService()))
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", action.original_key)
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.ENFORCE
    )
    commands = []
    probed_keys = []
    stored_keys = []

    def probe(key, *args):
        probed_keys.append(key)
        return action.original_probe(key, *args)

    def store(key, *args):
        stored_keys.append(key)
        return action.original_store(key, *args)

    monkeypatch.setattr(dodo, "_probe_cache", probe)
    monkeypatch.setattr(cache, "store", store)

    def run(command, *_args, **_kwargs):
        commands.append(command)
        return review_sessions.module.main(command[2:])

    monkeypatch.setattr(dodo, "_run_subprocess", run)

    def registered_task():
        return dict_to_task(next(dodo._machinist_review_tasks()))

    def freshness(task, values):
        check, args, kwargs = task.uptodate[0]
        return check(task, values, *args, **kwargs)

    def execute(previous):
        task = registered_task()
        # Task construction registers config_changed's saver; doit evaluates
        # freshness before execution and saves values only after success.
        assert not freshness(task, previous)
        assert task.execute(Stream(0)) is None
        task.save_extra_values()
        key = _review_key(dodo, label=label)
        return dict(task.values), key, dict(cache._KEY_INPUTS[(label, key)])

    saved, first_key, first_inputs = execute({})
    assert freshness(registered_task(), saved)
    assert len(commands) == 1 and len(review_sessions.seen) == 4
    changed = action.profile._replace(**{field: value})
    assert {
        name for name in PROFILE_FIELDS
        if getattr(action.profile, name) != getattr(changed, name)
    } == {field}
    with monkeypatch.context() as change:
        change.setattr(dodo, "_MACHINIST_REVIEW_PROFILE", changed)
        assert not freshness(registered_task(), saved)
        second_saved, second_key, second_inputs = execute(saved)
        assert first_key != second_key
        assert len(commands) == 2 and len(review_sessions.seen) == 8
        aggregate = dodo._read_machinist_aggregate("probe")
        assert tuple(
            aggregate[name] for name in ("reviewer", "model", "effort")
        ) == changed[:3]
        assert tuple(
            aggregate["judge"][name] for name in ("reviewer", "model", "effort")
        ) == changed[3:]
        for name, selected in changed._asdict().items():
            option = "--" + ENV_FIELDS[name].lower().replace("_", "-")
            assert commands[-1][commands[-1].index(option) + 1] == selected

    reverted = registered_task()
    assert freshness(reverted, saved)
    assert not freshness(reverted, second_saved)
    _, restored_key, _ = execute(second_saved)
    assert restored_key == first_key
    assert len(commands) == 2 and len(review_sessions.seen) == 8
    aggregate = dodo._read_machinist_aggregate("probe")
    assert tuple(
        aggregate[name] for name in ("reviewer", "model", "effort")
    ) == action.profile[:3]
    assert tuple(
        aggregate["judge"][name] for name in ("reviewer", "model", "effort")
    ) == action.profile[3:]
    assert probed_keys == [first_key, second_key, first_key]
    assert stored_keys == [first_key, second_key]
    config_tag = "cad/scripts/machinist_review_config.py"
    assert {path for path in first_inputs if first_inputs[path] != second_inputs[path]} == {
        config_tag,
    }
    assert all((root / path).is_file() for path in first_inputs)
    config_path = str(root / config_tag)
    effective = json.dumps(
        action.profile._asdict(), sort_keys=True, separators=(",", ":")
    )
    source = dodo.ContentChecker._digest(config_path)
    assert first_inputs[config_tag] == dodo.hashlib.sha256(
        f"{source}\0{effective}".encode()
    ).hexdigest()
    assert cache.key_input_paths(label, first_key) == sorted(first_inputs)


@pytest.mark.parametrize("verdict", ["SHIP", "FIX", "ERROR"])
@pytest.mark.parametrize("mode", REVIEWED_MODES)
@pytest.mark.parametrize("hit", [False, True])
def test_cached_verdict_policy_and_error_publication(action, verdict, mode, hit):
    action.state.update(verdict=verdict, hit=hit, code=0 if verdict == "SHIP" else 1)
    if mode is MachinistReviewMode.ENFORCE and verdict != "SHIP":
        with pytest.raises(RuntimeError, match=f"{verdict}, gating_count=2"):
            action.dodo._cached_machinist_review_action("probe", mode, action.profile)
    else:
        action.dodo._cached_machinist_review_action("probe", mode, action.profile)
    assert action.calls["run"] == int(not hit)
    assert action.calls["store"] == int(not hit and verdict != "ERROR")
    assert len(action.calls["warnings"]) == int(
        mode is MachinistReviewMode.LEARN and verdict != "SHIP"
    )
    assert action.dodo._machinist_review_stamp("probe").exists() == (
        verdict != "ERROR"
        and not (mode is MachinistReviewMode.ENFORCE and verdict == "FIX")
    )


@pytest.mark.parametrize("executor", ["local", "farm"])
@pytest.mark.parametrize("outcome", ["stored", "error", "provider_error"])
def test_forced_review_uses_shared_refresh_probe_store_and_freshness(
    action, monkeypatch, executor, outcome
):
    dodo = action.dodo
    label = "check:machinist_review:probe"
    reason = "Owner - Refresh cached judgement"
    refreshes = []
    monkeypatch.setenv("HARMONIC_EXECUTOR", executor)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv(
        "HARMONIC_CACHE_REFRESH", json.dumps({"labels": [label], "reason": reason})
    )
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    dodo.DRAWINGS_BY_NAME["probe"].script.write_text(
        "MACHINIST_REVIEW = MachinistReviewMode.LEARN\n"
    )
    dodo._reviewed_drawings.cache_clear()
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(dodo._cache, "store", action.original_store)
    monkeypatch.setattr(
        dodo._cache, "restore", lambda *_args: pytest.fail("forced review restored")
    )
    monkeypatch.setattr(
        dodo._cache, "note_refresh", lambda *args: refreshes.append(args)
    )
    monkeypatch.setattr(dodo._cache, "_REFRESH_ETAGS", {(label, "a" * 64): None})

    def publish(_key, outputs, published_label, *, replace_etag=None):
        action.calls["store"] += 1
        assert outputs == [dodo._machinist_review_dir("probe")]
        assert published_label == label
        assert not dodo._machinist_review_stamp("probe").exists()
        return outcome

    monkeypatch.setattr(dodo._cache, "_store", publish)
    task = next(dodo._machinist_review_tasks())
    assert False in task["uptodate"]
    if outcome == "provider_error":
        action.state.update(verdict="ERROR", error="provider unavailable", code=1)
    run, arguments = task["actions"][0]
    if outcome == "stored":
        run(*arguments)
    else:
        expected = "ERROR" if outcome == "provider_error" else "did not store outputs"
        with pytest.raises(RuntimeError, match=expected):
            run(*arguments)
    assert refreshes == [(label, "a" * 64, reason)]
    assert action.calls["run"] == 1
    assert action.calls["store"] == int(outcome != "provider_error")
    assert dodo._machinist_review_stamp("probe").exists() == (outcome == "stored")
    assert not action.calls["warnings"]


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize(
    ("verdict", "error"),
    [
        ("ERROR", None),
        ("ERROR", "provider unavailable"),
        ("SHIP", "provider unavailable"),
    ],
)
def test_provider_error_is_not_cached_and_forced_refresh_overrides_learning(
    action, monkeypatch, refresh, verdict, error
):
    action.state.update(verdict=verdict, error=error, code=int(verdict == "ERROR"))
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    if refresh:
        monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
        monkeypatch.setenv(
            "HARMONIC_CACHE_REFRESH",
            json.dumps(
                {
                    "labels": ["check:machinist_review:probe"],
                    "reason": "provider recovery requested",
                }
            ),
        )
        with pytest.raises(RuntimeError, match=f"{verdict}, gating_count="):
            action.dodo._cached_machinist_review_action(
                "probe", MachinistReviewMode.LEARN, action.profile
            )
    else:
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.profile
        )
        assert f"{verdict}, gating_count=" in action.calls["warnings"][0]
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()
    assert bool(action.calls["warnings"]) is not refresh


def test_failed_runner_cannot_reuse_a_previous_aggregate(action, monkeypatch):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    (directory / "probe.aggregate.json").write_text('{"verdict": "SHIP"}')
    monkeypatch.setattr(action.dodo, "_run_subprocess", lambda *_args, **_kwargs: 2)
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.LEARN, action.profile
    )
    assert action.calls["store"] == 0
    assert "ERROR" in action.calls["warnings"][0]


def test_cache_hit_replaces_instead_of_mixing_previous_evidence(action):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    old_attempt = directory / "unrelated-old-attempt.json"
    old_attempt.write_text("{}")
    action.state["hit"] = True
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.LEARN, action.profile
    )
    assert not old_attempt.exists()
    assert action.calls["run"] == 0
    assert action.calls["store"] == 0


@pytest.mark.parametrize("mode", REVIEWED_MODES)
def test_farm_restore_lock_uses_the_drawing_error_policy(action, monkeypatch, mode):
    def locked(*_args):
        raise action.dodo._cache.RestoreLocked(
            "probe", "a" * 64, PermissionError("locked")
        )

    monkeypatch.setattr(action.dodo, "_probe_cache", locked)
    if mode is MachinistReviewMode.ENFORCE:
        with pytest.raises(RuntimeError, match="ERROR"):
            action.dodo._cached_machinist_review_action("probe", mode, action.profile)
    else:
        action.dodo._cached_machinist_review_action("probe", mode, action.profile)
        assert "ERROR" in action.calls["warnings"][0]
    assert action.calls["run"] == action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()


def test_invalid_refresh_carrier_is_not_demoted_to_a_learning_warning(
    action, monkeypatch
):
    def malformed(*_args):
        raise ValueError("malformed HARMONIC_CACHE_REFRESH")

    monkeypatch.setattr(action.dodo, "_probe_cache", malformed)
    with pytest.raises(ValueError, match="HARMONIC_CACHE_REFRESH"):
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.profile
        )
    assert not action.calls["warnings"]


@pytest.mark.parametrize("winner,loser", [("FIX", "SHIP"), ("SHIP", "FIX")])
@pytest.mark.parametrize("mode", REVIEWED_MODES)
def test_losing_review_restores_full_winner_and_rereads_verdict(
    action, monkeypatch, winner, loser, mode, request
):
    from test_artifact_cache import _BlockBlobService

    dodo = action.dodo
    cache = dodo._cache
    root = dodo.REPO_ROOT
    directory = dodo._machinist_review_dir("probe")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", root / "cad" / "out")
    monkeypatch.setattr(cache, "_REPORTS", dodo.REPORTS)
    monkeypatch.setattr(cache, "_EVENTS_LOG", dodo.REPORTS / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", dodo.REPORTS / "cache-keys")
    backend = cache._BlobBackend(_BlockBlobService())
    monkeypatch.setattr(cache, "_BACKEND", backend)
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", action.original_key)
    key = _review_key(dodo)
    directory.mkdir(parents=True)
    (directory / "probe.aggregate.json").write_text(json.dumps({
        "name": "probe", "kind": "part", "verdict": winner,
        "gating_count": 2 if winner == "FIX" else 0, "error": None,
    }), encoding="utf-8")
    (directory / "winner-evidence.json").write_text('{"producer":"A"}', encoding="utf-8")
    winning_archive = cache._pack([directory])
    request.addfinalizer(winning_archive.close)
    # The first probe misses. Another producer publishes only once our own
    # expensive review has completed, before its conditional publication.
    run = dodo._run_subprocess
    action.state.update(verdict=loser, code=int(loser == "FIX"))

    def competing_review(*args, **kwargs):
        code = run(*args, **kwargs)
        (directory / "loser-only-attempt.json").write_text("{}", encoding="utf-8")
        backend.put(key, winning_archive)
        return code

    monkeypatch.setattr(dodo, "_run_subprocess", competing_review)
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(cache, "store", action.original_store)
    if mode is MachinistReviewMode.ENFORCE and winner == "FIX":
        with pytest.raises(RuntimeError, match="FIX, gating_count=2"):
            dodo._cached_machinist_review_action("probe", mode, action.profile)
    else:
        dodo._cached_machinist_review_action("probe", mode, action.profile)
    assert dodo._read_machinist_aggregate("probe")["verdict"] == winner
    assert (directory / "winner-evidence.json").is_file()
    assert not (directory / "loser-only-attempt.json").exists()
    assert dodo._machinist_review_stamp("probe").exists() == (
        winner == "SHIP" or mode is MachinistReviewMode.LEARN
    )
    assert action.calls["run"] == 1
    assert cache.last_stored_key("check:machinist_review:probe") is None


@pytest.mark.parametrize("failure", ["missing", "locked", "cleanup", "invalid-aggregate"])
def test_failed_review_adoption_is_fatal_even_in_learn(action, monkeypatch, failure):
    dodo = action.dodo
    directory = dodo._machinist_review_dir("probe")
    monkeypatch.setattr(dodo._cache, "store", lambda *_args: "lost")

    def restore(key, outputs, label):
        assert outputs == [directory]
        if failure == "locked":
            raise dodo._cache.RestoreLocked(label, key, PermissionError("locked"))
        if failure == "invalid-aggregate":
            directory.mkdir()
            (directory / "probe.aggregate.json").write_text("{}", encoding="utf-8")
            return True
        return False

    monkeypatch.setattr(dodo._cache, "restore", restore)
    if failure == "cleanup":
        def locked_cleanup(_path):
            raise PermissionError("report directory locked")

        monkeypatch.setattr(dodo.shutil, "rmtree", locked_cleanup)
    with pytest.raises(RuntimeError, match="canonical|share-locked"):
        dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.profile
        )
    assert not dodo._machinist_review_stamp("probe").exists()
    assert not action.calls["warnings"]


def test_only_opted_in_drawings_are_submitter_only_build_and_release_leaves(
    dodo,
    tmp_path,
    monkeypatch,
):
    import build

    stems = list(dodo.DRAWINGS_BY_NAME)
    declared = {
        dodo.DRAWINGS_BY_NAME[stems[0]].script: MachinistReviewMode.LEARN,
        dodo.DRAWINGS_BY_NAME[stems[1]].script: MachinistReviewMode.ENFORCE,
    }
    monkeypatch.setattr(
        dodo,
        "mode_for_drawing",
        lambda script: declared.get(script, MachinistReviewMode.OFF),
    )
    leaves = {task["name"]: task for task in dodo._machinist_review_tasks()}
    expected = {f"machinist_review:{stem}" for stem in stems[:2]}
    assert set(leaves) == expected
    reviews_in = [
        name for name in dodo.task_build()["task_dep"]
        if name.startswith("check:machinist_review:")
    ]
    assert set(reviews_in) == {f"check:{name}" for name in leaves}
    assert {f"check:{name}" for name in leaves} <= set(dodo.task_release()["task_dep"])
    assert f"check:machinist_review:{stems[2]}" not in dodo.task_release()["task_dep"]
    tasks = list(load_tasks(vars(dodo), [], allow_delayed=False))
    control = build._validate_farm_selection(tasks, ["build"])
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "protocol.py").write_text("# intercepted protocol")
    (tmp_path / "pyproject.toml").write_text("# intercepted project")
    queried = []

    def protocol_query(_argv, **kwargs):
        queried.extend(json.loads(kwargs["input"]))
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(
                {
                    "refused": [
                        task
                        for task in queried
                        if task.startswith("check:machinist_review:")
                    ],
                    "agent_identity": "fixture",
                    "agent_version": "fixture",
                }
            ),
        )

    monkeypatch.setattr(build.subprocess, "run", protocol_query)
    monkeypatch.setattr(build, "_pool_home", lambda: tmp_path)
    dispatchable, _identity = build._require_leaf_admission(control)
    assert queried == dispatchable
    assert dispatchable
    assert not {f"check:{name}" for name in leaves} & set(dispatchable)
    for name, task in leaves.items():
        stem = name.split(":", 1)[1]
        assert (
            str(dodo.DRAWINGS_BY_NAME[stem].outputs["pdf"].resolve())
            in task["file_dep"]
        )
        assert task["task_dep"] == [f"drawing:{stem}"]
        assert task["actions"][0][0]._remote_cache_action
        assert not getattr(task["actions"][0][0], "_farm_leaf_action", False)


def test_invalid_declaration_is_checked_when_generating_graph(
    dodo, tmp_path, monkeypatch
):
    stem, original = next(iter(dodo.DRAWINGS_BY_NAME.items()))
    script = tmp_path / "draw_invalid.py"
    script.write_text("MACHINIST_REVIEW = 'typo'\n")
    monkeypatch.setattr(
        dodo,
        "DRAWINGS_BY_NAME",
        {
            stem: replace(original, script_name=str(script)),
        },
    )
    with pytest.raises(ValueError, match="MACHINIST_REVIEW"):
        list(dodo._machinist_review_tasks())
