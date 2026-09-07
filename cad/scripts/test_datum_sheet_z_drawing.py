"""The datum Z diagnostic changes one argument and never trusts a True alone."""

from dataclasses import replace
import pytest

from diagnostics import probe_datum_sheet_z as probe
from test_native_callouts_drawing import native_setup


def setup(monkeypatch):
    adapter, view, annotation, _, _, _, measure = native_setup(monkeypatch)
    annotation.position = (0.05, 0.055, -0.00325)

    def capture(adapter, view, annotation):
        row = probe.callouts._read_symbol(adapter, view, annotation, measure)
        return row, {"geometry": (("face", 4001),), "body": row.body.bounds}

    return adapter, view, annotation, capture


def test_z_variants_keep_identical_absolute_xy():
    variants = probe.z_variants((0.2, 0.3), -0.00325)
    assert variants == (
        ("returned_z", (0.2, 0.3, -0.00325)),
        ("sheet_zero", (0.2, 0.3, 0.0)),
    )


@pytest.mark.parametrize("xy,z", [((float("nan"), 0), 0), ((0, 0), float("inf"))])
def test_nonfinite_target_is_rejected_before_com(xy, z):
    with pytest.raises(ValueError, match="finite"):
        probe.z_variants(xy, z)


def test_true_clamped_xy_is_reported_not_claimed_exact(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    annotation.mode = "clamp_horizontal"
    record = {}
    probe.run_trial(adapter, view, annotation, (0.2, 0.055, 0), record, capture=capture)
    assert record["attempt"]["returned"] is True
    assert record["attempt"]["placement"] == "clamped_xy"
    assert record["attempt"]["actual"] == (0.05, 0.055, 0)
    assert record["restore"]["requested"] == (0.05, 0.055, -0.00325)
    assert record["restore"]["placement"] == "exact_xy"
    assert annotation.moves == [(0.2, 0.055, 0), (0.05, 0.055, -0.00325)]


def test_changed_returned_z_does_not_hide_exact_xy(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    record = {}
    probe.run_trial(adapter, view, annotation, (0.05, 0.08, 0), record, capture=capture)
    assert record["attempt"]["placement"] == "exact_xy"
    assert record["attempt"]["actual"][2] == -0.0045385


def test_false_result_is_explicit_and_restore_still_runs(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    original = annotation.SetPosition2
    count = 0

    def reject_once(*target):
        nonlocal count
        count += 1
        return False if count == 1 else original(*target)

    annotation.SetPosition2 = reject_once
    record = {}
    probe.run_trial(adapter, view, annotation, (0.2, 0.08, 0), record, capture=capture)
    assert record["attempt"]["placement"] == "rejected"
    assert record["restore"]["placement"] == "exact_xy"


@pytest.mark.parametrize(
    "field,value",
    [
        ("properties", ("B", True, 2)),
        ("text", ("B",)),
        ("format", ("changed",)),
        ("entities", (object(),)),
        ("owner", object()),
        ("annotation", object()),
        ("specific", object()),
    ],
)
def test_changed_semantic_or_exact_identity_fails_and_restores(
    monkeypatch, field, value
):
    adapter, view, annotation, capture = setup(monkeypatch)
    reads = 0

    def changed(*args):
        nonlocal reads
        reads += 1
        row, data = capture(*args)
        return (replace(row, **{field: value}), data) if reads == 2 else (row, data)

    record = {}
    with pytest.raises(RuntimeError):
        probe.run_trial(
            adapter, view, annotation, (0.05, 0.08, 0), record, capture=changed
        )
    assert "attempt" in record and "restore" in record
    assert annotation.moves[-1] == (0.05, 0.055, -0.00325)


def test_changed_body_is_not_accepted_as_a_new_baseline(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    annotation.mode = "deform_final"
    with pytest.raises(RuntimeError, match="body"):
        probe.run_trial(adapter, view, annotation, (0.05, 0.08, 0), {}, capture=capture)


def test_failed_native_read_retains_attempted_coordinates_and_restores(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    reads = 0

    def fail_second(*args):
        nonlocal reads
        reads += 1
        if reads == 2:
            raise RuntimeError("native read failed")
        return capture(*args)

    record = {}
    with pytest.raises(RuntimeError, match="native read failed"):
        probe.run_trial(
            adapter, view, annotation, (0.05, 0.08, 0), record, capture=fail_second
        )
    assert record["attempt"] == {"requested": (0.05, 0.08, 0), "returned": True}
    assert record["restore"]["placement"] == "exact_xy"


def test_clamped_restoration_is_evidence_not_a_new_seed(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    original = annotation.SetPosition2
    calls = 0

    def clamp_restore(x, y, z):
        nonlocal calls
        calls += 1
        return original(x + (0.001 if calls == 2 else 0), y, z)

    annotation.SetPosition2 = clamp_restore
    record = {}
    probe.run_trial(adapter, view, annotation, (0.05, 0.08, 0), record, capture=capture)
    assert record["restore"]["placement"] == "clamped_xy"
    assert len(annotation.moves) == 2


def test_equal_identity_with_changed_geometry_fails(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    reads = 0

    def changed(*args):
        nonlocal reads
        reads += 1
        row, data = capture(*args)
        if reads == 2:
            data["geometry"] = (("different face",),)
        return row, data

    with pytest.raises(RuntimeError, match="controlled geometry"):
        probe.run_trial(adapter, view, annotation, (0.05, 0.08, 0), {}, capture=changed)


def test_new_copy_baseline_must_match_before_attempt(monkeypatch):
    adapter, view, annotation, capture = setup(monkeypatch)
    row, data = capture(adapter, view, annotation)
    old = probe.serial(row, data)
    probe.baseline_matches(old, dict(old))
    with pytest.raises(RuntimeError, match="baseline position"):
        probe.baseline_matches(old, {**old, "position": (0, 0, 0)})
    with pytest.raises(RuntimeError, match="baseline properties"):
        probe.baseline_matches(old, {**old, "properties": ("B", False, 2)})


def test_source_hash_change_fails_even_after_other_probe_errors(tmp_path):
    source = tmp_path / "source.SLDDRW"
    source.write_bytes(b"before")
    report = {
        "source_hashes": {str(source): probe.file_digest(source)},
        "operation_error": "another failure",
    }
    source.write_bytes(b"after")
    with pytest.raises(RuntimeError, match="original"):
        probe.guard_sources(report)
    assert report["source_hashes_after"] != report["source_hashes"]
