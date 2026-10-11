"""Strict traveler infrastructure, using only synthetic geometry and shop data."""

from __future__ import annotations

import hashlib
import json
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest
from prechips.report import inspection_sketch_names, report_hash

import _process_plans as plans

STEM = "ch_rocker_arm"
LABEL = "HAF_BORE__P01"
REFS = (f"#10/ADVANCED_FACE[1]/{LABEL}", f"#20/ADVANCED_FACE[2]/{LABEL}")


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    root = tmp_path / "process"
    source = root / STEM / "plan.toml"
    source.parent.mkdir(parents=True)
    shop = root / "shop"
    shop.mkdir()
    for name in plans.SHOP_FILES:
        (shop / name).write_text("version = 1\n", encoding="utf-8")
    out = tmp_path / "out"
    bundle = out / "features" / STEM
    bundle.mkdir(parents=True)
    step = bundle / "ch-rocker-arm.STEP"
    step.write_bytes(b"synthetic STEP bytes\n")
    manifest = bundle / "features.toml"
    manifest.write_text(
        'part = "ch-rocker-arm"\n'
        f'step = "{step.name}"\nstep_sha256 = "{hashlib.sha256(step.read_bytes()).hexdigest()}"\n'
        'drawing = { revision = "v41" }\n'
        "[features.bore]\nfaces = " + json.dumps(REFS) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(plans, "PROCESS_ROOT", root)
    monkeypatch.setattr(plans, "TRAVELER_STEMS", (STEM,))
    return source, out, manifest, shop


def test_label_refs_preserves_all_faces(synthetic):
    _, _, manifest, _ = synthetic
    assert plans.label_refs(tomllib.loads(manifest.read_text()))[LABEL] == REFS


def test_bind_list_splices_and_preserves_unrelated_bytes(synthetic):
    source, out, manifest, _ = synthetic
    raw = (
        'part = "ch-rocker-arm"\r\n'
        '# "HAF_BORE__P01" is a comment\r\n'
        'features = "../../out/old/features.toml" # path comment\r\n'
        'note = "prose HAF_BORE__P01 remains literal"\r\n'
        "literal = 'prose HAF_BORE__P01 remains literal'\r\n"
        'faces = ["before", "HAF_BORE__P01", "after"] # keep spacing\r\n'
        'drawing = { revision = "v41" }\r\n'
    ).encode()
    source.write_bytes(raw)
    bound = plans.bind_plan(STEM, out)
    parsed = tomllib.loads(bound.read_text(encoding="utf-8"))
    assert parsed["faces"] == ["before", *REFS, "after"]
    assert (bound.parent / parsed["features"]).resolve() == manifest.resolve()
    result = bound.read_bytes()
    for line in raw.splitlines(keepends=True):
        if not line.startswith((b"features =", b"faces =")):
            assert line in result
    assert result.count(b"\r\n") == raw.count(b"\r\n")
    assert b"# path comment\r\n" in result
    assert b"# keep spacing\r\n" in result
    assert source.read_bytes() == raw


@pytest.mark.parametrize("value", ['"HAF_BORE__P01"', "'HAF_BORE__P01'"])
def test_scalar_multiface_names_source_line(synthetic, value):
    source, out, _, _ = synthetic
    source.write_text(
        f'part = "ch-rocker-arm"\nfeatures = "old"\nface = {value}\n'
        'drawing = { revision = "v41" }\n'
    )
    with pytest.raises(plans.PlanBindError, match=r"(?i)line\s*3|:3\b"):
        plans.bind_plan(STEM, out)


@pytest.mark.parametrize("label", ["HAF_UNKNOWN__P01", "HAF_OTHER__P01"])
def test_unknown_or_wrongly_owned_label_rejected(synthetic, label):
    source, out, manifest, _ = synthetic
    if label == "HAF_OTHER__P01":
        manifest.write_text(manifest.read_text().replace(LABEL, label))
    source.write_text(
        f'part = "ch-rocker-arm"\nfeatures = "old"\nfaces = ["{label}"]\n'
        'drawing = { revision = "v41" }\n'
    )
    with pytest.raises(plans.PlanBindError, match=r"line 3:"):
        plans.bind_plan(STEM, out)


def test_single_face_scalar_and_literal_quotes(synthetic):
    source, out, manifest, _ = synthetic
    manifest.write_text(
        manifest.read_text().replace(json.dumps(REFS), json.dumps(REFS[:1]))
    )
    source.write_text(
        "part = 'ch-rocker-arm'\nfeatures = 'old'\nface = 'HAF_BORE__P01'\n"
        'drawing = { revision = "v41" }\n'
    )
    bound = plans.bind_plan(STEM, out)
    assert tomllib.loads(bound.read_text())["face"] == REFS[0]


@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("extra", [1, 2])
def test_multiline_prose_ending_in_quotes_is_preserved(synthetic, quote, extra):
    source, out, _, _ = synthetic
    prose = "note = " + quote * 3 + "literal HAF_UNKNOWN__P01 " + quote * (3 + extra)
    raw = (
        'part = "ch-rocker-arm"\nfeatures = "old"\n'
        + prose
        + '\nfaces = ["HAF_BORE__P01"]\n'
        + 'drawing = { revision = "v41" }\n'
    ).encode()
    source.write_bytes(raw)
    bound = plans.bind_plan(STEM, out)
    assert (prose + "\n").encode() in bound.read_bytes()
    assert tomllib.loads(bound.read_text())["faces"] == list(REFS)


def _spec(monkeypatch, solids=True):
    module = ModuleType("ch_rocker_arm_tl_test_spec")
    if solids:
        module.PRECHIPS_SOLIDS = [
            {"shape": "box", "at_mm": [0.0, 0.0, 0.0], "size_mm": [2.0, 3.0, 4.0]}
        ]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def test_shop_splices_spec_primitives_and_copies_policy(synthetic, monkeypatch):
    _, out, _, shop = synthetic
    module = _spec(monkeypatch)
    original = '[fixtures.test]\ncad = "ch_rocker_arm_tl_test"\nnote = "keep me"\n'
    (shop / "inventory.toml").write_text(original)
    assert plans.shop_spec_modules() == (module.__name__,)
    inventory, policy, cutting = plans.bind_shop(out)
    fixture = tomllib.loads(inventory.read_text())["fixtures"]["test"]
    assert fixture["solids"] == module.PRECHIPS_SOLIDS
    assert "cad" not in fixture
    assert fixture["note"] == "keep me"
    assert inventory.parent == out / "travelers" / "_shop"
    for bound in (policy, cutting):
        assert bound.read_bytes() == (shop / bound.name).read_bytes()
    assert (shop / "inventory.toml").read_text() == original


def test_parallel_shop_binders_install_identical_files_only_once(
    synthetic, monkeypatch
):
    _, out, _, _ = synthetic
    writes = []
    original_write = Path.write_bytes

    def slow_write(path, content):
        if path.parent.name != "_shop":
            return original_write(path, content)
        writes.append(path.name)
        # Expose a truncate/read window if callers do not serialize installation.
        with path.open("wb") as stream:
            time.sleep(0.02)
            return stream.write(content)

    monkeypatch.setattr(Path, "write_bytes", slow_write)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(plans.bind_shop, [out] * 4))
    assert all(paths == results[0] for paths in results)
    assert sorted(writes) == sorted(plans.SHOP_FILES)
    assert tomllib.loads(results[0][0].read_text()) == {"version": 1}
    for path in results[0][1:]:
        assert (
            path.read_bytes() == (plans.PROCESS_ROOT / "shop" / path.name).read_bytes()
        )


@pytest.mark.parametrize("failure", ["conflict", "module", "attribute"])
def test_shop_binding_fails_closed(synthetic, monkeypatch, failure):
    _, out, _, shop = synthetic
    stem = "ch_rocker_arm_tl_test" if failure != "module" else "ch_missing_tl_test"
    _spec(monkeypatch, solids=failure != "attribute")
    text = f'[fixtures.test]\ncad = "{stem}"\n'
    if failure == "conflict":
        text += 'solids = [{kind = "box", size = [1, 1, 1]}]\n'
    (shop / "inventory.toml").write_text(text)
    with pytest.raises(plans.PlanBindError):
        plans.bind_shop(out)


def _complete(synthetic):
    source, out, manifest, _ = synthetic
    source.write_text(
        'part = "ch-rocker-arm"\n'
        'features = "old"\ndrawing = { revision = "v41" }\n[[setups]]\nid = "lathe"\n'
        "[[setups.ops]]\nop = 7\n[setups.ops.inspection_views]\nbore = {}\n"
        '[[setups]]\nid = "mill"\nops = []\n'
    )
    bound = plans.bind_plan(STEM, out)
    directory = bound.parent
    inventory, policy, cutting = plans.bind_shop(out)
    paths = {
        "plan": bound,
        "features": manifest,
        "inventory": inventory,
        "shop_policy": policy,
        "cutting_data": cutting,
        "step": manifest.parent / "ch-rocker-arm.STEP",
    }
    inputs = {
        kind: {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for kind, path in paths.items()
    }
    for key, name in (
        ("lathe", "setup-S1.png"),
        ("lathe:7:bore", "setup-S1-op7-bore.png"),
        ("mill", "setup-S2.png"),
    ):
        data = b"synthetic image " + name.encode()
        (directory / name).write_bytes(data)
        inputs[f"render:{key}"] = {
            "path": name,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    report = {
        "expected_exit": 0,
        "inputs": inputs,
        "step_sha256": tomllib.loads(manifest.read_text())["step_sha256"],
        "verification": "checked",
    }
    _write_report(directory, report)
    (directory / "traveler.html").write_text(
        '<html><head><meta name="prechips-report" '
        f'content="{report["hash"]}"></head>synthetic traveler</html>',
        encoding="utf-8",
    )
    plans.bind_traveler_html(STEM, out)
    report = json.loads((directory / "report.json").read_bytes())
    return out, manifest, bound, report


def _write_report(directory, report):
    report["hash"] = report_hash(report)
    (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")


def test_required_outputs_uses_installed_inspection_names(synthetic, monkeypatch):
    _, _, bound, _ = _complete(synthetic)
    plan = tomllib.loads(bound.read_text())
    expected = {
        "report.json",
        "traveler.html",
        "setup-S1.png",
        "setup-S2.png",
        *inspection_sketch_names(plan),
    }
    assert {path.name for path in plans.required_outputs(bound)} == expected
    import prechips.report

    seen = []

    def names(value):
        seen.append(value)
        return ("installed-api-sentinel.png",)

    monkeypatch.setattr(prechips.report, "inspection_sketch_names", names)
    assert bound.parent / "installed-api-sentinel.png" in plans.required_outputs(bound)
    assert seen == [plan]


def test_verification_rejects_tampered_report_with_unchanged_hash(synthetic):
    out, _, bound, report = _complete(synthetic)
    plans.verify_traveler(STEM, out)
    original_hash = report["hash"]
    report["verification"] = "planned"
    (bound.parent / "report.json").write_text(json.dumps(report), encoding="utf-8")
    assert report["hash"] == original_hash
    assert report_hash(report) != original_hash
    with pytest.raises(plans.TravelerIncomplete, match="report hash"):
        plans.verify_traveler(STEM, out)
    assert not plans.traveler_complete(STEM, out)


def test_verification_rejects_edited_html(synthetic, tmp_path):
    out, manifest, bound, _ = _complete(synthetic)
    plans.verify_traveler(STEM, out)
    html = bound.parent / "traveler.html"
    html.write_bytes(
        html.read_bytes().replace(b"synthetic traveler", b"stale instructions")
    )
    with pytest.raises(plans.TravelerIncomplete, match="traveler.html.*sha256"):
        plans.verify_traveler(STEM, out)
    assert not plans.traveler_complete(STEM, out)
    stage = tmp_path / "stage"
    staged_manifest = stage / "features" / STEM / "features.toml"
    staged_manifest.parent.mkdir(parents=True)
    staged_manifest.write_bytes(manifest.read_bytes())
    (staged_manifest.parent / "ch-rocker-arm.STEP").write_bytes(
        (manifest.parent / "ch-rocker-arm.STEP").read_bytes()
    )
    with pytest.raises(plans.TravelerIncomplete, match="traveler.html.*sha256"):
        plans.stage_travelers(out, stage)


def test_html_record_is_inside_the_hashed_report(synthetic):
    out, _, bound, report = _complete(synthetic)
    html_record = report["inputs"]["traveler:html"]
    assert (
        html_record["sha256"]
        == hashlib.sha256((bound.parent / "traveler.html").read_bytes()).hexdigest()
    )
    assert report["hash"] == report_hash(report)
    html_record["sha256"] = "0" * 64
    (bound.parent / "report.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(plans.TravelerIncomplete, match="report hash"):
        plans.verify_traveler(STEM, out)


def test_html_binding_cannot_reseal_an_existing_certificate(synthetic):
    out, _, bound, _ = _complete(synthetic)
    report_bytes = (bound.parent / "report.json").read_bytes()
    (bound.parent / "traveler.html").write_bytes(b"edited instructions")
    with pytest.raises(plans.TravelerIncomplete, match="already bound"):
        plans.bind_traveler_html(STEM, out)
    assert (bound.parent / "report.json").read_bytes() == report_bytes


def test_html_binding_rejects_another_upstream_generation(synthetic):
    out, _, bound, report = _complete(synthetic)
    html_record = report["inputs"].pop("traveler:html")
    report["hash"] = html_record["source_report_hash"]
    _write_report(bound.parent, report)
    html = bound.parent / "traveler.html"
    html.write_bytes(
        html.read_bytes().replace(html_record["source_report_hash"].encode(), b"0" * 64)
    )
    with pytest.raises(plans.TravelerIncomplete, match="identify its source report"):
        plans.bind_traveler_html(STEM, out)


def test_verification_authenticates_html_source_generation(synthetic):
    out, _, bound, report = _complete(synthetic)
    report["inputs"]["traveler:html"]["source_report_hash"] = "0" * 64
    _write_report(bound.parent, report)
    with pytest.raises(plans.TravelerIncomplete, match="upstream report generation"):
        plans.verify_traveler(STEM, out)


@pytest.mark.parametrize(
    "failure",
    [
        "png_missing",
        "html_missing",
        "report_missing",
        "render_missing",
        "render_key",
        "render_path",
        "render_hash",
        "exit",
        "step_digest",
    ],
)
def test_completeness_rejects_every_incomplete_artifact(synthetic, failure):
    out, _, bound, report = _complete(synthetic)
    plans.verify_traveler(STEM, out)
    assert plans.traveler_complete(STEM, out)
    if failure.endswith("_missing") and failure != "render_missing":
        name = {
            "png_missing": "setup-S1-op7-bore.png",
            "html_missing": "traveler.html",
            "report_missing": "report.json",
        }[failure]
        (bound.parent / name).unlink()
    elif failure == "render_missing":
        del report["inputs"]["render:lathe:7:bore"]
        _write_report(bound.parent, report)
    elif failure == "render_key":
        report["inputs"]["render:wrong:7:bore"] = report["inputs"].pop(
            "render:lathe:7:bore"
        )
        _write_report(bound.parent, report)
    elif failure == "render_path":
        report["inputs"]["render:lathe:7:bore"]["path"] = "wrong.png"
        _write_report(bound.parent, report)
    elif failure == "render_hash":
        (bound.parent / "setup-S1.png").write_bytes(b"rewritten image")
    else:
        report["expected_exit" if failure == "exit" else "step_sha256"] = (
            2 if failure == "exit" else "0" * 64
        )
        _write_report(bound.parent, report)
    with pytest.raises(plans.TravelerIncomplete):
        plans.verify_traveler(STEM, out)
    assert not plans.traveler_complete(STEM, out)


def test_manifest_override_and_staging_prove_staged_digest(synthetic, tmp_path):
    out, manifest, bound, _ = _complete(synthetic)
    stage = tmp_path / "stage"
    staged_manifest = stage / "features" / STEM / "features.toml"
    staged_manifest.parent.mkdir(parents=True)
    staged_manifest.write_bytes(manifest.read_bytes())
    step_name = tomllib.loads(manifest.read_text())["step"]
    (staged_manifest.parent / step_name).write_bytes(
        (manifest.parent / step_name).read_bytes()
    )
    copied = plans.stage_travelers(out, stage)
    assert copied == [stage / "travelers" / STEM]
    for source in bound.parent.iterdir():
        assert (copied[0] / source.name).read_bytes() == source.read_bytes()
    staged_manifest.write_text(
        staged_manifest.read_text().replace(
            tomllib.loads(manifest.read_text())["step_sha256"], "0" * 64
        )
    )
    with pytest.raises(plans.TravelerIncomplete):
        plans.verify_traveler(STEM, out, manifest=staged_manifest)
    with pytest.raises(plans.TravelerIncomplete):
        plans.stage_travelers(out, stage)


def test_enrolled_plan_revisions_match_configured_release():
    import yaml

    release = Path(__file__).resolve().parents[1] / "config" / "release.yaml"
    revision = yaml.safe_load(release.read_text())["next_revision"]
    for stem in plans.TRAVELER_STEMS:
        assert (
            tomllib.loads(plans.plan_path(stem).read_text())["drawing"]["revision"]
            == revision
        )


def test_shop_without_cad_has_no_spec_dependencies(synthetic):
    _, out, _, shop = synthetic
    (shop / "inventory.toml").write_text(
        '[fixtures.bought]\nsolids = [{shape = "box", at_mm = [0, 0, 0], size_mm = [1, 2, 3]}]\n'
    )
    assert plans.shop_spec_modules() == ()
    inventory, _, _ = plans.bind_shop(out)
    assert tomllib.loads(inventory.read_text()) == tomllib.loads(
        (shop / "inventory.toml").read_text()
    )


def test_shop_spec_module_dependencies_are_deduplicated(synthetic, monkeypatch):
    _, _, _, shop = synthetic
    _spec(monkeypatch)
    (shop / "inventory.toml").write_text(
        '[fixtures.one]\ncad = "ch_rocker_arm_tl_test"\n'
        '[fixtures.two]\ncad = "ch_rocker_arm_tl_test"\n'
    )
    assert plans.shop_spec_modules() == ("ch_rocker_arm_tl_test_spec",)


def test_empty_enrollment_stages_no_travelers(tmp_path, monkeypatch):
    monkeypatch.setattr(plans, "TRAVELER_STEMS", ())
    assert plans.stage_travelers(tmp_path / "absent-out", tmp_path / "stage") == []


@pytest.mark.parametrize("rebind", [False, True])
def test_changed_tracked_plan_cannot_reuse_successful_traveler(
    synthetic, tmp_path, rebind
):
    out, manifest, _bound, _report = _complete(synthetic)
    source = plans.plan_path(STEM)
    source.write_bytes(
        source.read_bytes().replace(
            b'features = "old"', b'features = "old" # new authored plan'
        )
    )
    if rebind:
        plans.bind_plan(STEM, out)
    with pytest.raises(plans.TravelerIncomplete, match="plan"):
        plans.verify_traveler(STEM, out)
    assert not plans.traveler_complete(STEM, out)
    stage = tmp_path / "stage"
    staged_manifest = stage / "features" / STEM / "features.toml"
    staged_manifest.parent.mkdir(parents=True)
    staged_manifest.write_bytes(manifest.read_bytes())
    (staged_manifest.parent / "ch-rocker-arm.STEP").write_bytes(
        (manifest.parent / "ch-rocker-arm.STEP").read_bytes()
    )
    with pytest.raises(plans.TravelerIncomplete, match="plan"):
        plans.stage_travelers(out, stage)


def test_changed_manifest_with_identical_step_cannot_reuse_traveler(synthetic):
    out, manifest, _bound, report = _complete(synthetic)
    step_digest = report["step_sha256"]
    manifest.write_bytes(manifest.read_bytes() + b"width = [1.0, 2.0]\n")
    assert tomllib.loads(manifest.read_text())["step_sha256"] == step_digest
    with pytest.raises(plans.TravelerIncomplete, match="features input"):
        plans.verify_traveler(STEM, out)


@pytest.mark.parametrize(
    "kind", ["plan", "features", "inventory", "shop_policy", "cutting_data", "step"]
)
def test_missing_or_stale_input_hash_cannot_certify_traveler(synthetic, kind):
    out, _manifest, bound, report = _complete(synthetic)
    report["inputs"][kind]["sha256"] = "0" * 64
    _write_report(bound.parent, report)
    with pytest.raises(plans.TravelerIncomplete, match=f"{kind} input"):
        plans.verify_traveler(STEM, out)


def test_changed_tracked_shop_cannot_reuse_bound_shop_or_traveler(synthetic):
    out, _manifest, _bound, _report = _complete(synthetic)
    (plans.PROCESS_ROOT / "shop" / "shop-policy.toml").write_bytes(b"version = 2\n")
    with pytest.raises(plans.TravelerIncomplete, match="current shop inputs"):
        plans.verify_traveler(STEM, out)


@pytest.mark.parametrize("configured", [None, "v42"])
def test_revision_validation_names_authored_revision_line(synthetic, configured):
    source, out, _manifest, _shop = synthetic
    authored = "v42" if configured is None else "v41"
    source.write_text(
        'part = "ch-rocker-arm"\nfeatures = "old"\n[drawing]\n'
        f'revision = "{authored}"\n'
    )
    with pytest.raises(plans.PlanBindError, match="line 4:.*drawing.revision"):
        plans.check_plan_revision(STEM, out, revision=configured)
    if configured is None:
        with pytest.raises(plans.PlanBindError, match="line 4:.*drawing.revision"):
            plans.bind_plan(STEM, out)


def test_inline_table_scalar_in_array_is_not_spliced_as_list(synthetic):
    source, out, _manifest, _shop = synthetic
    source.write_text(
        'part = "ch-rocker-arm"\nfeatures = "old"\n'
        'items = [{ face = "HAF_BORE__P01" }]\n'
        'drawing = { revision = "v41" }\n'
    )
    with pytest.raises(plans.PlanBindError, match="line 3:.*cannot bind a scalar"):
        plans.bind_plan(STEM, out)
    source.write_text(
        source.read_text().replace(
            'face = "HAF_BORE__P01"', 'faces = ["HAF_BORE__P01"]'
        )
    )
    bound = plans.bind_plan(STEM, out)
    assert tomllib.loads(bound.read_text())["items"][0]["faces"] == list(REFS)


def test_staging_ships_only_verified_snapshots_and_shared_shop(
    synthetic, tmp_path, monkeypatch
):
    out, manifest, bound, _report = _complete(synthetic)
    original_png = (bound.parent / "setup-S1.png").read_bytes()
    (bound.parent / ".report.killed.tmp").write_bytes(b"stray temporary")
    (bound.parent / ".check").mkdir()
    (bound.parent / ".check" / "report.json").write_bytes(b"scratch report")
    stage = tmp_path / "stage"
    staged_manifest = stage / "features" / STEM / "features.toml"
    staged_manifest.parent.mkdir(parents=True)
    staged_manifest.write_bytes(manifest.read_bytes())
    (staged_manifest.parent / "ch-rocker-arm.STEP").write_bytes(
        (manifest.parent / "ch-rocker-arm.STEP").read_bytes()
    )
    original_verify = plans._verified_traveler_bytes

    def verify_then_change(*args, **kwargs):
        snapshots = original_verify(*args, **kwargs)
        (bound.parent / "setup-S1.png").write_bytes(b"changed after validation")
        return snapshots

    monkeypatch.setattr(plans, "_verified_traveler_bytes", verify_then_change)
    copied = plans.stage_travelers(out, stage)
    assert (copied[0] / "setup-S1.png").read_bytes() == original_png
    assert not (copied[0] / ".report.killed.tmp").exists()
    assert not (copied[0] / ".check").exists()
    for name in plans.SHOP_FILES:
        assert (stage / "travelers" / "_shop" / name).read_bytes() == (
            out / "travelers" / "_shop" / name
        ).read_bytes()
