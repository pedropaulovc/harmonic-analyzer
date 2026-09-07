"""Preparation keys follow blank setup, not later manufacturing callouts."""

import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_prepared_template as prepared
from _buildgraph import ASSEMBLY_ORDER, module_deps_of, part_scripts, script_for
from _drawing_registry import DRAWINGS


def registered_specs():
    return sorted(
        {importlib.import_module(row.script.stem).TEMPLATE_SPEC for row in DRAWINGS},
        key=lambda spec: (spec.scale, spec.decimals),
    )


def keys():
    adapter = SimpleNamespace(swApp=SimpleNamespace(RevisionNumber=lambda: "34.3.0"))
    specs = registered_specs()
    assert len(specs) == 15
    return [prepared._key(prepared.preparation_inputs(adapter, spec)) for spec in specs]


def changed_source(monkeypatch, relative_path):
    """Substitute one byte digest; never write checkout files or native artifacts."""
    root = Path(prepared.__file__).resolve().parents[2]
    target = root / relative_path
    original = prepared._sha
    changed = hashlib.sha256(
        target.read_bytes() + b"\n# changed source bytes\n"
    ).hexdigest()
    monkeypatch.setattr(
        prepared,
        "_sha",
        lambda path: changed if Path(path).resolve() == target else original(path),
    )


def test_unrelated_callout_bytes_leave_all_registered_template_keys_unchanged(
    monkeypatch,
):
    before = keys()
    changed_source(monkeypatch, "cad/scripts/_drawing_common.py")
    assert keys() == before


def test_setup_bytes_change_every_registered_template_key(monkeypatch):
    before = keys()
    changed_source(monkeypatch, "cad/scripts/_drawing_sheet_setup.py")
    assert all(first != second for first, second in zip(before, keys(), strict=True))


@pytest.mark.parametrize(
    "spec", [prepared.TemplateSpec(scale=(2, 1)), prepared.TemplateSpec(decimals=3)]
)
def test_actual_scale_and_precision_inputs_remain_distinct(spec):
    adapter = SimpleNamespace(swApp=SimpleNamespace(RevisionNumber=lambda: "34.3.0"))
    baseline = prepared._key(
        prepared.preparation_inputs(adapter, prepared.TemplateSpec())
    )
    assert prepared._key(prepared.preparation_inputs(adapter, spec)) != baseline


@pytest.mark.parametrize(
    "source",
    [
        "cad/scripts/_drawing_template_defaults.py",
        "cad/scripts/_drawing_template_viewport.py",
        "cad/scripts/_drawing_annotation_bounds.py",
        "cad/templates/harmonic-analyzer.DRWDOT",
        "cad/config/release.yaml",
        "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/drawing.py",
        "uv.lock",
    ],
)
def test_actual_preparation_inputs_remain_load_bearing(monkeypatch, source):
    adapter = SimpleNamespace(swApp=SimpleNamespace(RevisionNumber=lambda: "34.3.0"))
    spec = prepared.TemplateSpec()
    before = prepared._key(prepared.preparation_inputs(adapter, spec))
    changed_source(monkeypatch, source)
    assert prepared._key(prepared.preparation_inputs(adapter, spec)) != before


def test_preparation_closure_cannot_reenter_manufacturing_helpers():
    closure = {Path(path).name for path in module_deps_of(Path(prepared.__file__))}
    assert "_drawing_sheet_setup.py" in closure
    assert not closure.intersection(
        {
            "_drawing_common.py",
            "_drawing_layout_check.py",
            "_part_pmi.py",
            "_gtol_spec.py",
            "_surface_finish.py",
        }
    )


def test_setup_is_drawing_only_and_all_registered_drawings_depend_on_it():
    for script in [*part_scripts(), *(script_for(stem) for stem in ASSEMBLY_ORDER)]:
        assert "_drawing_sheet_setup.py" not in {
            Path(path).name for path in module_deps_of(script)
        }, script.name
    for row in DRAWINGS:
        assert "_drawing_sheet_setup.py" in {
            Path(path).name for path in module_deps_of(row.script)
        }, row.name
