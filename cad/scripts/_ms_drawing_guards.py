"""Clean-source guard and imported-text readback for the measuring-stick
part drawings (MHA-MS-01..03).

A sheet captures its source part before presenting anything -- the file's
SHA-256 and the open document's save flag (``IModelDoc2.GetSaveFlag``) -- and
proves both at every native document boundary ``new_project_drawing`` and
``finalize_drawing`` expose as checkpoints, and once more after the finalizer
returns.  The drawings author no presentation on imported dimensions: the
parts write their own callout rows and quantity prefixes (#1942), which a
drawing only reads back here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _telemetry
from _com import _early_bound
from solidworks_mcp.adapters.solidworks.drawing import dimension_name

# swDimensionTextParts_e
_CALLOUT_BELOW = 4  # swDimensionTextCalloutBelow
_PREFIX_DEFINITION = 5  # swDimensionTextPrefixDefinition


@dataclass(frozen=True)
class CleanSource:
    """A drawing's source part, captured clean before any view exists.

    ``strict_in_memory`` also requires the open document's save flag to stay
    clear.  A sheet that shows hidden part sketches in memory for a derived
    view (``_drawing_hidden_sketches.part_sketches_shown``) re-blanks them but
    may leave the flag set, so it proves the file bytes only."""

    path: Path
    sha256: str
    model: Any
    label: str
    strict_in_memory: bool


def _file_sha256(path: Path) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _save_flag(model: Any) -> bool:
    return bool(_early_bound(model, "IModelDoc2").GetSaveFlag())


@_telemetry.traced("drawing.ms_source_capture", label_param="label")
def capture_clean_source(
    path: Path, model: Any, *, label: str, strict_in_memory: bool = True
) -> CleanSource:
    """Hash the source part's bytes and require its open document clean,
    before the drawing presents anything."""
    digest = _file_sha256(path)
    dirty = _save_flag(model)
    _telemetry.event(
        "drawing.ms_source_clean",
        label=label,
        stage="captured",
        source_sha256=digest,
        dirty=dirty,
    )
    if dirty:
        raise RuntimeError(
            f"{label}: source part is modified before the drawing starts"
        )
    return CleanSource(Path(path), digest, model, label, strict_in_memory)


def assert_source_clean(
    source: CleanSource, *, stage: str, in_memory: bool = True
) -> None:
    """The source file still has its captured bytes and, while its document
    is open (``in_memory``) on a strict sheet, its save flag is clear."""
    actual = _file_sha256(source.path)
    dirty = _save_flag(source.model) if in_memory else None
    _telemetry.event(
        "drawing.ms_source_clean",
        label=source.label,
        stage=stage,
        source_sha256=actual,
        dirty=dirty,
    )
    if actual != source.sha256:
        raise RuntimeError(
            f"{source.label} {stage}: source part bytes changed "
            f"({source.sha256[:12]} -> {actual[:12]}); the drawing must never save it"
        )
    if dirty and source.strict_in_memory:
        raise RuntimeError(
            f"{source.label} {stage}: the drawing modified its source part"
        )


def source_checkpoint(source: CleanSource) -> Callable[[str], None]:
    """A ``new_project_drawing`` / ``finalize_drawing`` checkpoint proving the
    source at every native document boundary; once the drawing has closed,
    only the file is read."""

    def checkpoint(stage: str) -> None:
        assert_source_clean(
            source, stage=stage, in_memory=stage != "after_drawing_close"
        )

    return checkpoint


def _rows(text: str) -> tuple[str, ...]:
    return tuple(row.strip() for row in text.replace("\r", "").split("\n"))


@_telemetry.traced("drawing.ms_imported_text")
def assert_imported_text(
    adapter: Any,
    annotations: Iterable[Any],
    below: Mapping[str, str],
    prefixes: Mapping[str, str] | None = None,
) -> None:
    """Every named imported dimension prints the callout rows and quantity
    prefix its PART authored; the drawing never writes them."""
    prefixes = prefixes or {}
    seen: set[str] = set()
    wrong: dict[str, str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in below and name not in prefixes:
            continue
        seen.add(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name in below:
            printed = str(display.GetText(_CALLOUT_BELOW) or "")
            if _rows(printed) != _rows(below[name]):
                wrong[name] = printed
        if name in prefixes:
            definition = str(display.GetText(_PREFIX_DEFINITION) or "")
            if not definition.startswith(prefixes[name]):
                wrong[f"{name} prefix"] = definition
    missing = sorted({*below, *prefixes} - seen)
    if missing:
        raise RuntimeError(f"imported dimensions missing from the sheet: {missing}")
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )
