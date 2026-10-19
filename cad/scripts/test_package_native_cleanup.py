"""Offline contracts for release packaging's fail-loud document cleanup."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
import sys
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_native  # noqa: E402


class _Document:
    def __init__(self, title: str, *, unreadable_path: bool = False):
        self.title = title
        self.unreadable_path = unreadable_path

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        if self.unreadable_path:
            raise OSError("path unreadable")
        return f"C:/fixture/{self.title}"


class _Seat:
    def __init__(self, documents, *, fail_title=None, count_unreadable=False, stuck=False):
        self.documents = list(documents)
        self.fail_title = fail_title
        self.count_unreadable = count_unreadable
        self.stuck = stuck
        self.original = RuntimeError("native CloseDoc server fault")
        self.failed = False
        self.closed = []
        self.hidden_closed = False

    @property
    def IActiveDoc2(self):
        assert not self.failed, "cleanup must not read COM again after a server fault"
        return self.documents[0] if self.documents else None

    def GetDocumentCount(self):
        if self.count_unreadable:
            raise OSError("count unreadable")
        return len(self.documents)

    def CloseDoc(self, title):
        self.closed.append(title)
        if title == self.fail_title:
            self.failed = True
            raise self.original
        if not self.stuck:
            self.documents.pop(0)

    def CloseAllDocuments(self, discard):
        assert discard is True
        self.hidden_closed = True


@pytest.fixture
def observed_cleanup(monkeypatch):
    logs: list[tuple[str, dict[str, Any]]] = []
    captures = []
    monkeypatch.setattr(package_native._telemetry, "span", lambda *a, **k: nullcontext())
    monkeypatch.setattr(
        package_native._telemetry,
        "info",
        lambda message, **context: logs.append((message, context.copy())),
    )

    def capture(adapter, label, message, *, exception, **context):
        assert adapter is None
        captures.append((label, context.copy()))
        raise exception

    monkeypatch.setattr(package_native._seat_forensics, "capture_com_failure", capture)
    return logs, captures


def test_close_fault_keeps_exact_document_context_and_original_exception(observed_cleanup):
    logs, captures = observed_cleanup
    seat = _Seat([_Document("first.SLDDRW"), _Document("last.SLDASM")], fail_title="last.SLDASM")

    with pytest.raises(RuntimeError) as caught:
        package_native._discard_open_documents(seat)

    assert caught.value is seat.original
    assert seat.closed == ["first.SLDDRW", "last.SLDASM"]
    assert not seat.hidden_closed
    assert captures == [
        (
            "package-close-documents",
            {
                "api": "ISldWorks.CloseDoc",
                "close_iteration": 2,
                "document_title": "last.SLDASM",
                "document_path": "C:/fixture/last.SLDASM",
                "document_count": 1,
            },
        )
    ]
    assert logs[-1][1] == captures[0][1]


def test_diagnostic_identity_read_failures_do_not_prevent_close(observed_cleanup):
    logs, captures = observed_cleanup
    seat = _Seat([_Document("drawing.SLDDRW", unreadable_path=True)], count_unreadable=True)

    package_native._discard_open_documents(seat)

    assert seat.closed == ["drawing.SLDDRW"]
    assert seat.hidden_closed
    assert captures == []
    closing = next(context for message, context in logs if message.startswith("package close: closing '"))
    assert closing["document_title"] == "drawing.SLDDRW"
    assert closing["document_path_error"] == "OSError: path unreadable"
    assert closing["document_count_error"] == "OSError: count unreadable"


@pytest.mark.parametrize("empty_title", [False, True])
def test_empty_title_and_iteration_exhaustion_still_fail_loud(observed_cleanup, empty_title):
    _logs, captures = observed_cleanup
    seat = _Seat([_Document("" if empty_title else "stuck.SLDASM")], stuck=True)

    with pytest.raises(RuntimeError, match="empty title" if empty_title else "500 CloseDoc"):
        package_native._discard_open_documents(seat)

    assert len(seat.closed) == (0 if empty_title else 500)
    assert not seat.hidden_closed
    assert captures[0][1]["close_iteration"] == (1 if empty_title else 500)


@pytest.mark.parametrize("body_fails", [False, True])
def test_package_cleanup_never_masks_body_failure_or_writes_sidecar(
    tmp_path, monkeypatch, body_fails
):
    top = tmp_path / "ha-harmonic-analyzer.SLDASM"
    top.write_bytes(b"fixture")
    body_error = ValueError("packaging failed")
    close_error = RuntimeError("close failed")
    monkeypatch.setattr(package_native, "OUT_SLDASM", tmp_path)
    monkeypatch.setattr(package_native, "RELEASE_DIR", tmp_path / "release")
    monkeypatch.setattr(package_native, "DRAWING_OUTPUTS", {"fixture": {}})
    monkeypatch.setattr(package_native, "attach_solidworks", lambda: (object(), "fixture"))
    monkeypatch.setattr(package_native, "package_top_assembly", lambda *a: ())

    def drawings(*args):
        if body_fails:
            raise body_error
        return {}

    def release(*args):
        raise close_error

    monkeypatch.setattr(package_native, "package_drawings", drawings)
    monkeypatch.setattr(package_native, "_release_seat", release)
    monkeypatch.setattr(package_native, "write_sidecar", lambda *a: pytest.fail("failed package wrote sidecar"))

    with pytest.raises(Exception) as caught:
        package_native.package_native(tmp_path / "native")

    assert caught.value is (body_error if body_fails else close_error)
