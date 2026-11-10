"""Pure regression coverage of the deliberately closed experimental drawing planner."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from diagnostics._drawing_reconcile import plan, recipe

SCRIPT = Path(__file__).resolve().parent / "diagnostics" / "benchmark_drawing_reconcile.py"


def test_identical_serialized_recipe_is_noop():
    before = recipe()
    result = plan(before, json.loads(json.dumps(before)))
    assert result.decision == "noop"
    assert result.edits == ()


def test_depth_change_is_the_only_edit_without_mutating_inputs():
    before = recipe(20, 12)
    after = recipe(20, 16)
    snapshots = copy.deepcopy((before, after))
    result = plan(before, after)
    assert result.decision == "incremental"
    assert result.edits == (("depth", 16.0),)
    assert (before, after) == snapshots


def test_both_keyed_part_dimensions_keep_semantic_order():
    assert plan(recipe(20, 12), recipe(24, 16)).edits == (("diameter", 24.0), ("depth", 16.0))


def _note(value):
    return next(item for item in value["annotations"] if item["kind"] == "note")


@pytest.mark.parametrize("change", [
    lambda value: value.update(schema=2),
    lambda value: value["template"].update(layout="portrait"),
    lambda value: value["sheet"].update(scale=[1.0, 2.0]),
    lambda value: value["sheet"].update(units="in"),
    lambda value: value["sheet"].update(decimals=3),
    # Added / removed / reordered views.
    lambda value: value["views"].append({**value["views"][1], "key": "top", "name": "ReconcileTop",
                                         "orientation": "*Top"}),
    lambda value: value["views"].pop(),
    lambda value: value["views"].reverse(),
    lambda value: value["views"][0].update(name="Drawing View1"),
    lambda value: value["views"][1].update(orientation="*Isometric"),
    lambda value: value["views"][1].update(position_mm=[210.0, 170.0]),
    lambda value: value["views"][0].update(scale=[2.0, 1.0]),
    lambda value: value["views"][0].update(configuration="Other"),
    lambda value: value["views"][0].update(unsupported_option=True),
    # Added / removed / moved annotations.
    lambda value: value["annotations"].pop(0),
    lambda value: value["annotations"].remove(_note(value)),
    lambda value: value["annotations"].append({**_note(value), "key": "note2"}),
    lambda value: value["annotations"].append({**value["annotations"][0], "key": "diameter_side", "view": "side"}),
    lambda value: value["annotations"][0].update(view="side"),
    lambda value: value["annotations"][1].update(dimension="diameter"),
    lambda value: value["annotations"][0].update(kind="reference_dimension"),
    lambda value: _note(value).update(text="CHANGED NOTE"),
    lambda value: _note(value).update(position_mm=[41.0, 250.0]),
    lambda value: _note(value).update(owner="front"),
    # Part structure is refused through the part planner.
    lambda value: value["part"]["features"][1].update(operation="through_all"),
    lambda value: value["part"]["dimensions"].update(depth="D1@OtherFeature"),
])
def test_structural_change_refuses_entire_parameter_edit(change):
    after = recipe(20, 16)
    change(after)
    result = plan(recipe(20, 12), after)
    assert result.decision == "full_build"
    assert result.edits == ()  # never leak partial edits from a refused plan


@pytest.mark.parametrize("mutate", [
    lambda value: value["views"].pop(),
    lambda value: value["annotations"].remove(_note(value)),
    lambda value: value["part"]["features"][1].update(operation="through_all"),
])
def test_matching_but_unsupported_structures_do_not_become_noop(mutate):
    unsupported = recipe()
    mutate(unsupported)
    result = plan(unsupported, copy.deepcopy(unsupported))
    assert result.decision == "full_build"
    assert result.edits == ()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "16", None])
def test_invalid_depth_fails_before_any_edit_plan(value):
    after = recipe()
    after["part"]["parameters_mm"]["depth"] = value
    with pytest.raises(ValueError, match="finite positive"):
        plan(recipe(), after)


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(unknown=True),
    lambda value: value.pop("views"),
    lambda value: value.pop("annotations"),
    lambda value: value["part"].pop("features"),
    lambda value: value["part"]["parameters_mm"].update(extra=1),
    lambda value: value["part"]["parameters_mm"].pop("depth"),
])
def test_malformed_recipe_is_not_silently_treated_as_full_build(mutate):
    after = recipe()
    mutate(after)
    with pytest.raises(ValueError):
        plan(recipe(), after)


@pytest.mark.parametrize("value", [None, [], "recipe"])
def test_non_object_recipe_fails(value):
    with pytest.raises(ValueError):
        plan(recipe(), value)


def test_recipe_instances_do_not_share_structural_containers():
    first = recipe()
    first["views"][0]["position_mm"].append(1.0)
    first["sheet"]["scale"][0] = 2.0
    _note(first)["text"] = "MUTATED"
    first["part"]["features"][1]["depends_on"].clear()
    second = recipe()
    assert second["views"][0]["position_mm"] == [110.0, 170.0]
    assert second["sheet"]["scale"] == [1.0, 1.0]
    assert _note(second)["text"] == "EXPERIMENTAL KEYED DRAWING RECONCILIATION"
    assert second["part"]["features"][1]["depends_on"] == ["profile"]


def test_model_references_isolate_part_and_assembly_dependencies():
    from diagnostics.benchmark_drawing_reconcile import model_references

    pairs = [("format", r"C:\t\a - landscape.slddrt"), ("part", r"C:\t\Part.SLDPRT"), ("asm", r"C:\t\A.sldasm")]
    models, others = model_references(pairs)
    assert models == pairs[1:]
    assert others == pairs[:1]


def _text_pdf(path: Path, *pages: str) -> Path:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    for text in pages:
        page = writer.add_blank_page(width=300, height=200)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("ascii"))
        page.replace_contents(stream)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_pdf_evidence_records_hash_pages_and_text(tmp_path):
    from diagnostics.benchmark_drawing_reconcile import pdf_evidence

    path = _text_pdf(tmp_path / "trial.pdf", "DEPTH 16")
    evidence = pdf_evidence(path)
    assert evidence["page_count"] == 1
    assert "DEPTH 16" in evidence["text"]
    assert len(evidence["sha256"]) == len(evidence["text_sha256"]) == 64
    with pytest.raises(RuntimeError, match="expected 1"):
        pdf_evidence(_text_pdf(tmp_path / "two.pdf", "A", "B"))


def test_pdf_comparison_reports_text_differences_without_failing(tmp_path):
    from diagnostics.benchmark_drawing_reconcile import compare_pdfs, pdf_evidence

    baseline = pdf_evidence(_text_pdf(tmp_path / "baseline.pdf", "DEPTH 12"))
    clean = pdf_evidence(_text_pdf(tmp_path / "clean.pdf", "DEPTH 16"))
    same = pdf_evidence(_text_pdf(tmp_path / "same.pdf", "DEPTH 16"))
    other = pdf_evidence(_text_pdf(tmp_path / "other.pdf", "DEPTH 15"))
    equal = compare_pdfs(clean, same, baseline)
    assert equal["text_equal"] and equal["page_count_equal"] and equal["text_diff"] == []
    assert not equal["clean_text_equals_baseline"]
    different = compare_pdfs(clean, other, baseline)
    assert not different["text_equal"]
    assert "-DEPTH 16" in different["text_diff"] and "+DEPTH 15" in different["text_diff"]


def _validation(depth=16.0, outline_width=16.0, position=(110.0, 170.0)):
    view = {"name": "ReconcileSide", "orientation": "*Right", "referenced_configuration": "Default",
            "scale": [1.0, 1.0], "model_out_of_date": False, "display_dimension_count": 1,
            "position_mm": list(position), "outline_mm": [0.0, 0.0, outline_width, 20.0]}
    return {
        "part_geometry": {"dimensions_mm": {"diameter": 20.0, "depth": depth},
                          "bounds_mm": [[-10.0, 10.0], [-10.0, 10.0], [0.0, depth]], "volume_mm3": 100.0 * depth},
        "sheet": {"names": ["Sheet1"], "scale": [1.0, 1.0], "units_linear": 0, "decimals": 2},
        "views": {"side": view},
        "dimensions": {"depth": {"view": "side", "value_mm": depth, "position_mm": [1.0, 2.0]}},
        "note": {"text": "N", "position_mm": [40.0, 250.0]},
        "auto_annotations": {"front:13": 1},
    }


def test_clean_incremental_comparison_returns_placement_evidence():
    from diagnostics.benchmark_drawing_reconcile import compare_pair

    evidence = compare_pair(_validation(), _validation(position=(111.0, 170.0)))
    assert evidence["view_position_delta_mm"]["side"] == [-1.0, 0.0]
    assert evidence["view_outline_size_delta_mm"]["side"] == [0.0, 0.0]


@pytest.mark.parametrize("incremental, message", [
    (_validation(outline_width=12.0), "outline size"),
    (_validation(depth=12.0), "part dimensions"),
    ({**_validation(), "auto_annotations": {}}, "automatic annotation"),
])
def test_clean_incremental_content_mismatch_is_fatal(incremental, message):
    from diagnostics.benchmark_drawing_reconcile import compare_pair

    with pytest.raises(RuntimeError, match=message):
        compare_pair(_validation(), incremental)


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          env=env, timeout=120, check=False)


def _without_seat() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("HARMONIC_COM_SEAT", None)
    return env


def test_help_loads_no_native_bindings():
    probe = (
        "import runpy, sys; sys.argv = [sys.argv[1], '--help']\n"
        "try:\n    runpy.run_path(sys.argv[0], run_name='__main__')\n"
        "except SystemExit as exit:\n    assert exit.code == 0, exit.code\n"
        "native = sorted(m for m in sys.modules if m.split('.')[0] in "
        "{'win32com', 'pythoncom', 'pywintypes', 'solidworks_mcp', '_session', '_com', '_drawing_common'})\n"
        "assert not native, native\n"
    )
    result = subprocess.run([sys.executable, "-c", probe, str(SCRIPT)], capture_output=True, text=True,
                            env=_without_seat(), timeout=120, check=False)
    assert result.returncode == 0, result.stderr
    assert "benchmark" in result.stdout and "plan" in result.stdout


def test_plan_cli_reads_persisted_manifest(tmp_path):
    manifest = tmp_path / "baseline-manifest.json"
    target = tmp_path / "target-recipe.json"
    manifest.write_text(json.dumps({"recipe": recipe(20, 12)}), encoding="utf-8")
    target.write_text(json.dumps(recipe(20, 16)), encoding="utf-8")
    result = _run("plan", str(manifest), str(target), env=_without_seat())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"decision": "incremental", "reason": "supported part dimension edit",
                                         "edits": [["depth", 16.0]]}


def test_plan_cli_refuses_structural_view_change(tmp_path):
    manifest = tmp_path / "baseline-manifest.json"
    target = tmp_path / "target-recipe.json"
    structural = recipe(20, 16)
    structural["views"].pop()
    manifest.write_text(json.dumps({"recipe": recipe(20, 12)}), encoding="utf-8")
    target.write_text(json.dumps(structural), encoding="utf-8")
    result = _run("plan", str(manifest), str(target), env=_without_seat())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"decision": "full_build", "reason": "unsupported or changed views",
                                         "edits": []}


def test_plan_cli_rejects_malformed_target(tmp_path):
    manifest = tmp_path / "baseline-manifest.json"
    target = tmp_path / "target-recipe.json"
    manifest.write_text(json.dumps({"recipe": recipe(20, 12)}), encoding="utf-8")
    malformed = recipe(20, 16)
    malformed["part"]["parameters_mm"]["depth"] = -5
    target.write_text(json.dumps(malformed), encoding="utf-8")
    result = _run("plan", str(manifest), str(target), env=_without_seat())
    assert result.returncode != 0
    assert "finite positive" in result.stderr


def test_benchmark_refuses_standalone_launch_before_native_import():
    result = _run("benchmark", env=_without_seat())
    assert result.returncode != 0
    assert "canonical verify:drawing_reconcile task" in result.stderr
