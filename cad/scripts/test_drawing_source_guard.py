"""Offline contract of the shared drawing clean-source guard."""

from __future__ import annotations

from pathlib import Path

import pytest

import _drawing_source_guard as guard
from _drawing_source_guard import SourceCheck


class _SourceDocument:
    """An open source document: its path and save flag, counting flag reads."""

    def __init__(self, path: Path, *, dirty: object = False) -> None:
        self.path = path
        self.dirty = dirty
        self.flag_reads = 0

    def GetPathName(self) -> str:  # noqa: N802 - COM member name
        return str(self.path)

    def GetSaveFlag(self) -> object:  # noqa: N802 - COM member name
        self.flag_reads += 1
        return self.dirty


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "source.SLDPRT"
    path.write_bytes(b"source")
    return path


@pytest.mark.parametrize(
    "check", [SourceCheck.NATIVE_CLEAN, SourceCheck.TRANSIENT_VIEW_STATE]
)
@pytest.mark.parametrize("flag", [True, None, 1])
def test_capture_refuses_a_source_that_is_not_clean_before_the_drawing(
    tmp_path, check, flag
) -> None:
    path = _source(tmp_path)
    with pytest.raises(RuntimeError, match="before the drawing starts"):
        guard.capture_clean_source(
            path, _SourceDocument(path, dirty=flag), label="source", check=check
        )


def test_capture_refuses_a_foreign_open_document_or_a_closed_policy(tmp_path) -> None:
    path = _source(tmp_path)
    other = tmp_path / "other.SLDPRT"
    other.write_bytes(b"source")
    with pytest.raises(RuntimeError, match="is not"):
        guard.capture_clean_source(path, _SourceDocument(other), label="source")
    with pytest.raises(ValueError, match="captured open"):
        guard.capture_clean_source(
            path, _SourceDocument(path), label="source", check=SourceCheck.CLOSED
        )


def test_native_clean_refuses_a_set_save_flag_while_the_drawing_is_open(
    tmp_path,
) -> None:
    path = _source(tmp_path)
    document = _SourceDocument(path)
    source = guard.capture_clean_source(path, document, label="source")
    checkpoint = guard.source_checkpoint(source)
    checkpoint("after_new_document")
    checkpoint("before_drawing_save")
    document.dirty = True
    with pytest.raises(RuntimeError, match="after_drawing_save: the drawing modified"):
        checkpoint("after_drawing_save")
    reads = document.flag_reads
    # From the drawing close on, the handle is never dereferenced.
    checkpoint(guard.AFTER_DRAWING_CLOSE)
    guard.assert_source_closed(source, stage="after finalize")
    assert document.flag_reads == reads


def test_transient_view_state_records_the_flag_but_proves_the_bytes(tmp_path) -> None:
    path = _source(tmp_path)
    document = _SourceDocument(path)
    source = guard.capture_clean_source(
        path, document, label="source", check=SourceCheck.TRANSIENT_VIEW_STATE
    )
    checkpoint = guard.source_checkpoint(source)
    document.dirty = True
    checkpoint("after_create_view")
    checkpoint("before_drawing_save")
    assert document.flag_reads == 3  # capture, then each open-document stage
    path.write_bytes(b"saved by the sheet")
    with pytest.raises(
        RuntimeError, match="after_drawing_save: source file bytes changed"
    ):
        checkpoint("after_drawing_save")


@pytest.mark.parametrize(
    "check", [SourceCheck.NATIVE_CLEAN, SourceCheck.TRANSIENT_VIEW_STATE]
)
def test_every_stage_refuses_changed_bytes_including_after_close(
    tmp_path, check
) -> None:
    path = _source(tmp_path)
    document = _SourceDocument(path)
    source = guard.capture_clean_source(path, document, label="source", check=check)
    path.write_bytes(b"saved by the sheet")
    with pytest.raises(
        RuntimeError, match="before_drawing_save: source file bytes changed"
    ):
        guard.assert_source_clean(source, stage="before_drawing_save")
    reads = document.flag_reads
    with pytest.raises(
        RuntimeError, match="after_drawing_close: source file bytes changed"
    ):
        guard.source_checkpoint(source)(guard.AFTER_DRAWING_CLOSE)
    with pytest.raises(RuntimeError, match="after finalize: source file bytes changed"):
        guard.assert_source_closed(source, stage="after finalize")
    assert document.flag_reads == reads
