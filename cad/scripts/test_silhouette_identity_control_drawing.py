from types import SimpleNamespace as NS

import pytest

from diagnostics import _silhouette_identity_control as control


@pytest.mark.parametrize("raw", [None, (), [], "abc", (True,), (-1,), (256,), (1.0,)])
def test_bad_native_references_rejected(raw):
    with pytest.raises(RuntimeError, match="native persistent reference"):
        control._byte_reference(raw)


def test_literal_byte_references_and_native_comparisons(monkeypatch):
    monkeypatch.setattr(control, "_variant", lambda value: value)
    calls = []

    def compare(first, second):
        calls.append((first, second))
        return int(first == second)

    extension = NS(GetPersistReference3=lambda value: value, IsSamePersistentID=compare)
    records = {}
    control.persistent_controls(extension, {
        "expected": (1, 2), "selected": (1, 2), "selected_again": (1, 2),
        "expected_face": (3,), "selected_face": (4,),
    }, records)
    assert records["expected"] == {"value": (1, 2)}
    assert records["compare.expected.selected"] == {"value": 1}
    assert records["compare.expected_face.selected_face"] == {"value": 0}
    assert len(calls) == 5


def test_missing_reference_never_becomes_a_comparison(monkeypatch):
    def compare(*unused):
        pytest.fail("missing native IDs must not be compared")

    extension = NS(GetPersistReference3=lambda value: None, IsSamePersistentID=compare)
    records = {}
    control.persistent_controls(extension, {"expected": object()}, records)
    assert "empty" in records["expected"]["error"]
    assert records["compare.expected.selected"] == {"status": "missing_reference"}


def test_capture_never_drives_unowned_document_or_replaces_original_error():
    def deny():
        raise RuntimeError("not owned")

    records = {}
    control.capture(NS(ownership=NS(assert_current_owned=deny)), None, None, None, records)
    assert records == {"persistent_identity_control": {"capture_error": "RuntimeError('not owned')"}}
