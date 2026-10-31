"""Clean-source guard for a drawing that reads its source model and never
writes it.

A sheet captures its source before presenting anything: the open document IS
the source file (``IModelDoc2.GetPathName``), its save flag
(``IModelDoc2.GetSaveFlag``) is clear, and the file's SHA-256.  It proves the
source again at every native document boundary ``new_project_drawing`` and
``finalize_drawing`` expose as checkpoints, and once more after the finalizer
returns.  The bytes never change at any stage; :class:`SourceCheck` says what
else a stage proves.
"""

from __future__ import annotations

import enum
import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _telemetry
from _com import _early_bound

# The ``finalize_drawing`` checkpoint stage after its attempted drawing close.
AFTER_DRAWING_CLOSE = "after_drawing_close"


class SourceCheck(enum.Enum):
    """What a source proof reads besides the file's unchanged bytes."""

    NATIVE_CLEAN = "native_clean"
    """The open document's save flag stays clear: the sheet changes nothing
    in the source, in memory or on disk."""

    TRANSIENT_VIEW_STATE = "transient_view_state"
    """The sheet intentionally changes in-memory view state of the open
    source (part sketches shown for a derived view, a view's camera), which
    can set the save flag without a write: the flag is recorded, not
    refused, and the bytes are the persistence proof."""

    CLOSED = "closed"
    """The drawing has closed: only the file is read, and the source
    document handle is never dereferenced."""


@dataclass(frozen=True)
class CleanSource:
    """A drawing's source, captured clean before any view exists.

    ``check`` is the sheet's open-document policy (never ``CLOSED``)."""

    path: Path
    sha256: str
    model: Any
    label: str
    check: SourceCheck


def _file_sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@_telemetry.traced("drawing.source_capture", label_param="label")
def capture_clean_source(
    path: Path,
    model: Any,
    *,
    label: str,
    check: SourceCheck = SourceCheck.NATIVE_CLEAN,
) -> CleanSource:
    """Require the open document to be ``path`` and clean, and hash the file,
    before the drawing presents anything."""
    if check is SourceCheck.CLOSED:
        raise ValueError(f"{label}: a source is captured open, not {check}")
    path = Path(path)
    document = _early_bound(model, "IModelDoc2")
    opened = Path(str(document.GetPathName())).resolve()
    if opened != path.resolve():
        raise RuntimeError(f"{label}: open document {opened} is not {path}")
    digest = _file_sha256(path)
    save_flag = document.GetSaveFlag()
    _telemetry.event(
        "drawing.source_clean",
        label=label,
        stage="captured",
        check=check.value,
        source_sha256=digest,
        save_flag=repr(save_flag),
    )
    if save_flag is not False:
        raise RuntimeError(
            f"{label}: source document reports save flag {save_flag!r} before "
            "the drawing starts"
        )
    return CleanSource(path, digest, document, label, check)


def _prove(source: CleanSource, stage: str, check: SourceCheck) -> None:
    actual = _file_sha256(source.path)
    save_flag = None if check is SourceCheck.CLOSED else source.model.GetSaveFlag()
    _telemetry.event(
        "drawing.source_clean",
        label=source.label,
        stage=stage,
        check=check.value,
        source_sha256=actual,
        save_flag="not read" if check is SourceCheck.CLOSED else repr(save_flag),
    )
    if actual != source.sha256:
        raise RuntimeError(
            f"{source.label} {stage}: source file bytes changed "
            f"({source.sha256[:12]} -> {actual[:12]}); the drawing must never "
            "save its source"
        )
    if check is SourceCheck.NATIVE_CLEAN and save_flag is not False:
        raise RuntimeError(
            f"{source.label} {stage}: the drawing modified its source document "
            f"(save flag {save_flag!r}); refusing to save or reset it"
        )


def assert_source_clean(source: CleanSource, *, stage: str) -> None:
    """While the source document is open: its bytes, and its save flag under
    the sheet's :class:`SourceCheck`."""
    _prove(source, stage, source.check)


def assert_source_closed(source: CleanSource, *, stage: str) -> None:
    """Once the drawing has closed: the file's bytes only."""
    _prove(source, stage, SourceCheck.CLOSED)


def source_checkpoint(source: CleanSource) -> Callable[[str], None]:
    """A ``new_project_drawing`` / ``finalize_drawing`` checkpoint proving the
    source at every native document boundary; from the drawing close on,
    only the file is read."""

    def checkpoint(stage: str) -> None:
        if stage == AFTER_DRAWING_CLOSE:
            assert_source_closed(source, stage=stage)
        else:
            assert_source_clean(source, stage=stage)

    return checkpoint
