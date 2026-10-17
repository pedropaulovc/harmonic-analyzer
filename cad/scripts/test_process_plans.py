"""Strict traveler infrastructure, using only synthetic geometry and shop data."""

from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import math
import re
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
    manifest, step = plans.bundle_paths(STEM, out)
    step.parent.mkdir(parents=True)
    step.write_bytes(b"synthetic STEP bytes\n")
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


def test_bind_plan_reads_only_its_own_bundle_not_an_aggregate_manifest(synthetic):
    source, out, manifest, _ = synthetic
    source.write_text(
        'part = "ch-rocker-arm"\nfeatures = "old"\nfaces = ["HAF_BORE__P01"]\n'
        'drawing = { revision = "v41" }\n',
        encoding="utf-8",
    )
    unrelated, unrelated_step = plans.bundle_paths("ch_pivot_shaft", out)
    unrelated.parent.mkdir(parents=True)
    unrelated.write_bytes(b"not TOML; another leaf is incomplete\n")
    unrelated_step.write_bytes(b"unrelated STEP\n")
    before = (unrelated.read_bytes(), unrelated_step.read_bytes())
    bound = plans.bind_plan(STEM, out)
    plan = tomllib.loads(bound.read_text(encoding="utf-8"))
    assert (bound.parent / plan["features"]).resolve() == manifest.resolve()
    assert plan["faces"] == list(REFS)
    assert (unrelated.read_bytes(), unrelated_step.read_bytes()) == before


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
            {
                "name": "block",
                "shape": "box",
                "at_mm": [0.0, 0.0, 0.0],
                "size_mm": [2.0, 3.0, 4.0],
                "measured": _measurement("P. Vicente"),
            }
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


@pytest.mark.parametrize(
    ("gap", "reason"),
    [("measured", "no measured record"), ("status", "measured has no status")],
)
def test_shop_binding_refuses_a_solid_without_measured_status(
    synthetic, monkeypatch, gap, reason
):
    """#1462: prechips trusts a solid with no measured record as installed
    nominal geometry, and an omitted status reads as assumed, so binding
    refuses both, naming the spec and the solid, before writing anything."""
    _, out, _, shop = synthetic
    module = _spec(monkeypatch)
    solid = module.PRECHIPS_SOLIDS[0]
    if gap == "measured":
        del solid["measured"]
    else:
        del solid["measured"]["status"]
    (shop / "inventory.toml").write_text(
        '[fixtures.test]\ncad = "ch_rocker_arm_tl_test"\n'
    )
    where = r"ch_rocker_arm_tl_test_spec\.PRECHIPS_SOLIDS solid 'block': "
    with pytest.raises(plans.PlanBindError, match=where + reason):
        plans.bind_shop(out)
    with pytest.raises(plans.PlanBindError, match=where + reason):
        plans.shop_placeholders()
    assert not (out / "travelers" / "_shop").exists()


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
        f'content="{report["hash"]}"></head>'
        '<div class="banner">PLANNED — NOT APPROVED</div>synthetic traveler</html>',
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
    staged_manifest, _staged_step = plans.bundle_paths(STEM, stage)
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


def _measurement(by):
    return {
        "status": "measured",
        "by": by,
        "date": "2026-10-12",
        "instrument": "height gauge on surface plate",
    }


def _measured_shop(shop, by):
    measured = plans._toml_value(_measurement(by))
    (shop / "inventory.toml").write_text(
        f"[fixtures.test]\nheight_mm = {{ value = 18.5, measured = {measured} }}\n",
        encoding="utf-8",
    )


def _stage(manifest, tmp_path):
    stage = tmp_path / "stage"
    staged_manifest, _ = plans.bundle_paths(STEM, stage)
    staged_manifest.parent.mkdir(parents=True)
    staged_manifest.write_bytes(manifest.read_bytes())
    step_name = tomllib.loads(manifest.read_text())["step"]
    (staged_manifest.parent / step_name).write_bytes(
        (manifest.parent / step_name).read_bytes()
    )
    return stage


def test_placeholder_traveler_is_provisional_and_cannot_release(synthetic, tmp_path):
    *_, shop = synthetic
    _measured_shop(shop, plans.PLACEHOLDER_BY)
    out, manifest, bound, report = _complete(synthetic)
    assert report[plans.PROVISIONAL_KEY] == {
        "provisional": True,
        "placeholders": 1,
        "remeasure": plans.PLACEHOLDER_ISSUE,
    }
    html = (bound.parent / "traveler.html").read_text(encoding="utf-8")
    assert f'<div class="banner">{plans.provisional_banner(1)}PLANNED' in html
    # Ordinary builds and farm runs still certify the (provisional) traveler.
    plans.verify_traveler(STEM, out)
    stage = _stage(manifest, tmp_path)
    with pytest.raises(plans.PlaceholderRelease) as refusal:
        plans.stage_travelers(out, stage)
    assert plans.PLACEHOLDER_ISSUE in str(refusal.value)
    assert str(refusal.value).endswith(
        "\ninventory.toml:fixtures.test.height_mm.measured.by"
    )
    assert not (stage / "travelers").exists()
    with pytest.raises(plans.PlaceholderRelease):
        plans.require_measured_release()


def test_measured_fixture_traveler_is_not_provisional(synthetic, tmp_path):
    *_, shop = synthetic
    _measured_shop(shop, "P. Vicente")
    out, manifest, bound, report = _complete(synthetic)
    assert report[plans.PROVISIONAL_KEY] == plans.provisional_stamp(())
    assert not report[plans.PROVISIONAL_KEY]["provisional"]
    assert "PROVISIONAL" not in (bound.parent / "traveler.html").read_text(
        encoding="utf-8"
    )
    plans.require_measured_release()
    assert plans.stage_travelers(out, _stage(manifest, tmp_path)) == [
        tmp_path / "stage" / "travelers" / STEM
    ]


def test_every_bound_placeholder_is_counted(synthetic, monkeypatch):
    _, out, _, shop = synthetic
    module = _spec(monkeypatch)
    module.PRECHIPS_SOLIDS[0]["measured"] = _measurement(plans.PLACEHOLDER_BY)
    (shop / "inventory.toml").write_text(
        '[fixtures.test]\ncad = "ch_rocker_arm_tl_test"\n'
        "[gauges.radius]\n"
        f"# Identity: by = {plans.PLACEHOLDER_BY!r}; schema has no measured.\n"
        "range_mm = [\n  [1.0, 7.0],\n]\n"
        f"note = {plans._toml_value('provenance: by = ' + plans.PLACEHOLDER_BY)}\n",
        encoding="utf-8",
    )
    assert plans.shop_placeholders() == (
        "inventory.toml:fixtures.test.solids[0].measured.by",
        "inventory.toml:gauges.radius.note",
        "inventory.toml:gauges.radius line 4 (comment)",
    )
    bound = plans.bind_shop(out)
    assert plans._placeholders(path.read_bytes() for path in bound) == (
        plans.shop_placeholders()
    )


@pytest.mark.parametrize("tamper", ["stamp", "header"])
def test_verification_requires_the_provisional_stamp(synthetic, tamper):
    *_, shop = synthetic
    _measured_shop(shop, plans.PLACEHOLDER_BY)
    out, _, bound, report = _complete(synthetic)
    if tamper == "stamp":
        report[plans.PROVISIONAL_KEY] = plans.provisional_stamp(())
    else:
        html = bound.parent / "traveler.html"
        content = html.read_bytes().replace(plans.provisional_banner(1).encode(), b"")
        html.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        report["inputs"]["traveler:html"]["sha256"] = digest
    _write_report(bound.parent, report)
    with pytest.raises(plans.TravelerIncomplete, match="(?i)provisional"):
        plans.verify_traveler(STEM, out)


def test_enrolled_plan_revisions_match_configured_release():
    import yaml

    release = Path(__file__).resolve().parents[1] / "config" / "release.yaml"
    revision = yaml.safe_load(release.read_text())["next_revision"]
    for stem in plans.TRAVELER_STEMS:
        assert (
            tomllib.loads(plans.plan_path(stem).read_text())["drawing"]["revision"]
            == revision
        )


# Plans migrated to the pinned prechips, enrolled or still held from enrollment
# (the rocker until its traveler reaches exit 0, cad/process/README.md).
MIGRATED_PLANS = ("ch_rocker_arm",)


def test_migrated_plans_name_faces_by_bare_labels_their_op_owns():
    import yaml

    release = Path(__file__).resolve().parents[1] / "config" / "release.yaml"
    revision = yaml.safe_load(release.read_text())["next_revision"]
    for stem in dict.fromkeys((*MIGRATED_PLANS, *plans.TRAVELER_STEMS)):
        text = plans.plan_path(stem).read_text(encoding="utf-8")
        plan = tomllib.loads(text)
        assert plan["part"] == stem.replace("_", "-")
        assert plan["drawing"]["revision"] == revision
        # The wrapper passes the shop files; exact STEP refs exist only once bound.
        assert "paths" not in plan
        assert plans._REF.search(text) is None
        faced = [
            (op["feature"], label)
            for setup in plan["setups"]
            for op in setup["ops"]
            for label in op.get("faces", ())
        ]
        assert faced
        for feature, label in faced:
            match = plans._LABEL.fullmatch(label)
            assert match is not None, label
            assert match["feature"].lower() == feature, label


def test_chain_drilled_features_are_broken_out_before_they_are_filed():
    # prechips credits a chain_drill op's stock_removal_bounds as removed; its only
    # break-out text is the drilling op's own "after drilling" sentence (prechips#213).
    # Where the webs wait for the bench, the plan must carry that step itself (#1548): a
    # noted bench step on the feature before its file_to_line.
    for stem in dict.fromkeys((*MIGRATED_PLANS, *plans.TRAVELER_STEMS)):
        plan = tomllib.loads(plans.plan_path(stem).read_text(encoding="utf-8"))
        ops = [(setup["id"], op) for setup in plan["setups"] for op in setup["ops"]]
        for index, (sid, op) in enumerate(ops):
            if op.get("contour", {}).get("method") != "chain_drill":
                continue
            later = [
                o for _, o in ops[index + 1 :] if o.get("feature") == op["feature"]
            ]
            filed = [i for i, o in enumerate(later) if o["do"] == "file_to_line"]
            if not filed:
                continue
            assert any(
                o["do"] == "deburr" and "break out" in o.get("note", "").lower()
                for o in later[: filed[0]]
            ), (
                f"{stem} {sid} op {op['op']}: {op['feature']} is filed with no break-out step"
            )


# A touch spot printed in a plan's prose: "at X+157.0 Y+6.65", setup-frame millimetres.
_TOUCH_SPOT = re.compile(r"\bat X([+-]\d+(?:\.\d+)?) Y([+-]\d+(?:\.\d+)?)")


def _tool_radius(tools: dict, ref: str) -> float:
    """Half the widest of a member's cutting and shank diameters, in mm."""
    kit, member = ref.split("/", 1)
    record = tools[kit]["members"][member]

    def value(key: str) -> float:
        field = record.get(key, 0.0)
        return float(field["value"] if isinstance(field, dict) else field)

    return max(value("dia_mm"), value("shank_mm"), value("shank_in") * 25.4) / 2


def _hold_solids(fixtures: dict, ref: str) -> list[dict]:
    kit, _, member = ref.partition("/")
    record = fixtures[kit]["members"][member] if member else fixtures[kit]
    if "cad" in record:
        return importlib.import_module(f"{record['cad']}_spec").PRECHIPS_SOLIDS
    return record["solids"]


def _posed_box(solid: dict, pose: dict) -> tuple[list[float], list[float]]:
    """Conservative setup-frame AABB for supported box and cylinder primitives."""
    x, z = pose["x"], pose["z"]
    y = [
        z[1] * x[2] - z[2] * x[1],
        z[2] * x[0] - z[0] * x[2],
        z[0] * x[1] - z[1] * x[0],
    ]
    at = solid["at_mm"]
    shape = solid.get("shape")
    if shape == "cylinder":
        axis_length = math.sqrt(sum(component**2 for component in solid["axis"]))
        if axis_length == 0:
            raise ValueError(
                f"fixture solid {solid.get('name', '?')!r}: zero cylinder axis"
            )
        axis = [component / axis_length for component in solid["axis"]]
        direction = [sum(axis[k] * (x, y, z)[k][a] for k in range(3)) for a in range(3)]
        start = [
            pose["origin_mm"][a] + sum(at[k] * (x, y, z)[k][a] for k in range(3))
            for a in range(3)
        ]
        end = [start[a] + solid["length_mm"] * direction[a] for a in range(3)]
        radial = [
            solid["dia_mm"] / 2 * math.sqrt(max(0.0, 1.0 - component**2))
            for component in direction
        ]
        return (
            [min(start[a], end[a]) - radial[a] for a in range(3)],
            [max(start[a], end[a]) + radial[a] for a in range(3)],
        )
    if shape != "box":
        raise ValueError(
            f"fixture solid {solid.get('name', '?')!r}: unsupported shape {shape!r}"
        )
    size = solid["size_mm"]
    corners = [
        [
            pose["origin_mm"][axis]
            + sum((at[k] + size[k] * corner[k]) * (x, y, z)[k][axis] for k in range(3))
            for axis in range(3)
        ]
        for corner in itertools.product((0, 1), repeat=3)
    ]
    return [min(c[a] for c in corners) for a in range(3)], [
        max(c[a] for c in corners) for a in range(3)
    ]


@pytest.mark.parametrize(
    ("axis", "low", "high"),
    [
        ([0.0, 0.0, 1.0], [-2.0, -2.0, 0.0], [2.0, 2.0, 10.0]),
        ([0.0, 0.0, 2.0], [-2.0, -2.0, 0.0], [2.0, 2.0, 10.0]),
        ([1.0, 0.0, 0.0], [0.0, -2.0, -2.0], [10.0, 2.0, 2.0]),
        (
            [0.6, 0.0, 0.8],
            [-1.6, -2.0, -1.2],
            [7.6, 2.0, 9.2],
        ),
    ],
)
def test_posed_cylinder_bounds_include_radial_extent(axis, low, high):
    solid = {
        "name": "stud",
        "shape": "cylinder",
        "at_mm": [0.0, 0.0, 0.0],
        "axis": axis,
        "dia_mm": 4.0,
        "length_mm": 10.0,
    }
    pose = {"origin_mm": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "z": [0.0, 0.0, 1.0]}
    actual_low, actual_high = _posed_box(solid, pose)
    assert actual_low == pytest.approx(low)
    assert actual_high == pytest.approx(high)


def test_posed_cylinder_rejects_a_zero_axis():
    solid = {"name": "stud", "shape": "cylinder", "at_mm": [0, 0, 0], "axis": [0, 0, 0]}
    pose = {"origin_mm": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "z": [0.0, 0.0, 1.0]}
    with pytest.raises(ValueError, match="fixture solid 'stud': zero cylinder axis"):
        _posed_box(solid, pose)


def test_posed_unknown_primitive_names_the_solid():
    pose = {"origin_mm": [0.0, 0.0, 0.0], "x": [1.0, 0.0, 0.0], "z": [0.0, 0.0, 1.0]}
    with pytest.raises(
        ValueError, match="fixture solid 'mystery': unsupported shape 'cone'"
    ):
        _posed_box({"name": "mystery", "shape": "cone", "at_mm": [0, 0, 0]}, pose)


@pytest.mark.parametrize(
    "stem",
    [
        pytest.param(
            stem,
            marks=(
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason="superseded plan collides with 52PCCK clamps; rewrite in #1577",
                )
                if stem == "ch_rocker_arm"
                else ()
            ),
        )
        for stem in dict.fromkeys((*MIGRATED_PLANS, *plans.TRAVELER_STEMS))
    ],
)
def test_every_touch_spot_clears_the_hold_by_the_tool_radius_plus_1mm(stem):
    # A paper touch lowers the tool onto the work's top face at a spot the plan names in
    # prose (prechips 0.1.2 has no touch-position field). The tool's widest diameter must
    # clear, in plan view, every hold solid standing above that face (the strap clamps) by
    # 1 mm; solids wholly under it (table, riser blocks, shim stacks) cannot meet a tool
    # that stops on it, and a touch over a support is the stiffest spot.
    shop = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    plan = tomllib.loads(plans.plan_path(stem).read_text(encoding="utf-8"))
    for setup in plan["setups"]:
        zero = setup.get("zero", {})
        touches = [
            (touch["tool"], touch["method"]) for touch in zero.get("tool_touches", ())
        ]
        if zero.get("z", {}).get("method") == "paper":
            touches.append((zero["z"]["tool"], zero["z"].get("edge", "")))
        if not touches:
            continue
        hold = setup["hold"]
        top = setup["stock_state"]["top_z"]
        placed = [(hold["fixture"], hold["pose"])] + [
            (clamp["ref"], clamp["pose"]) for clamp in hold.get("clamps", ())
        ]
        boxes = [
            (ref, solid.get("name", "?"), box)
            for ref, pose in placed
            for solid in _hold_solids(shop["fixtures"], ref)
            if not solid.get("void", False)
            for box in [_posed_box(solid, pose)]
            if box[1][2] > top
        ]
        for tool, prose in touches:
            where = f"{stem} {setup['id']} {tool} touch"
            spot = _TOUCH_SPOT.search(prose)
            assert spot, f"{where}: no 'at X.. Y..' spot in {prose!r}"
            sx, sy = float(spot[1]), float(spot[2])
            need = _tool_radius(shop["tools"], tool) + 1.0
            for ref, name, (low, high) in boxes:
                dx = max(low[0] - sx, 0.0, sx - high[0])
                dy = max(low[1] - sy, 0.0, sy - high[1])
                assert math.hypot(dx, dy) >= need, (
                    f"{where} at X{sx:+} Y{sy:+}: {ref} {name} is "
                    f"{math.hypot(dx, dy):.2f} away, needs {need:.2f}"
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
