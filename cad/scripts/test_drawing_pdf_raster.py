"""Offline contract for the PDF export's shaded-raster DPI override.

``pdf_shaded_raster_dpi`` raises a SEAT-GLOBAL system preference for the one
``SaveAs3`` that prints a drawing's PDF. Pinned here: the export sees the
raised value, the seat is put back to the declared baseline however the export
ends, every value is read back onto the span, and a refused restore never
replaces the export's own exception.

    python -m pytest cad/scripts/test_drawing_pdf_raster.py
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import _drawing_common

_PREF = _drawing_common._PREF_PDF_SHADED_DRAFT_DPI
_BASELINE = _drawing_common._PDF_SHADED_DRAFT_DPI_BASELINE
_DPI = _drawing_common.PDF_SHADED_DRAFT_DPI


class _Seat:
    """``ISldWorks`` integer preferences; ``refuse`` values read back unchanged."""

    def __init__(self, value: int, refuse: frozenset[int] = frozenset()) -> None:
        self.values = {_PREF: value}
        self.refuse = refuse
        self.writes: list[int] = []

    def GetUserPreferenceIntegerValue(self, pref: int) -> int:
        return self.values[pref]

    def SetUserPreferenceIntegerValue(self, pref: int, value: int) -> bool:
        self.writes.append(value)
        if value in self.refuse:
            return False
        self.values[pref] = value
        return True


class _Span:
    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value


@pytest.fixture(autouse=True)
def _late_bound(monkeypatch):
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda obj, _iface: obj)


def _adapter(seat: _Seat) -> SimpleNamespace:
    return SimpleNamespace(swApp=seat)


def test_export_runs_at_raised_dpi_and_seat_returns_to_baseline() -> None:
    seat, span = _Seat(_BASELINE), _Span()
    with _drawing_common.pdf_shaded_raster_dpi(_adapter(seat), span):
        assert seat.values[_PREF] == _DPI
    assert seat.values[_PREF] == _BASELINE
    assert span.attributes == {
        "pdf.shaded_draft_dpi.before": _BASELINE,
        "pdf.shaded_draft_dpi.baseline": _BASELINE,
        "pdf.shaded_draft_dpi.applied": _DPI,
        "pdf.shaded_draft_dpi.restored": _BASELINE,
    }


def test_stranded_seat_is_restored_to_declared_baseline_not_entry_value() -> None:
    """A leaf killed mid-export leaves 300; the next export must not keep it."""
    seat, span = _Seat(_DPI), _Span()
    with _drawing_common.pdf_shaded_raster_dpi(_adapter(seat), span):
        pass
    assert seat.values[_PREF] == _BASELINE
    assert span.attributes["pdf.shaded_draft_dpi.before"] == _DPI


def test_refused_apply_raises_and_still_restores() -> None:
    seat = _Seat(_BASELINE, refuse=frozenset({_DPI}))
    with pytest.raises(RuntimeError, match="did not persist"):
        with _drawing_common.pdf_shaded_raster_dpi(_adapter(seat), _Span()):
            pytest.fail("exported at the seat's 96 dpi")
    assert seat.writes == [_DPI, _BASELINE]


def test_refused_restore_raises_after_a_clean_export() -> None:
    seat = _Seat(_BASELINE, refuse=frozenset({_BASELINE}))
    with pytest.raises(RuntimeError, match="restore refused"):
        with _drawing_common.pdf_shaded_raster_dpi(_adapter(seat), _Span()):
            pass


def test_refused_restore_never_replaces_the_export_failure() -> None:
    seat = _Seat(_BASELINE, refuse=frozenset({_BASELINE}))
    with pytest.raises(OSError, match="SaveAs3 died"):
        with _drawing_common.pdf_shaded_raster_dpi(_adapter(seat), _Span()):
            raise OSError("SaveAs3 died")


def test_only_the_pdf_artifact_touches_the_seat(tmp_path: Path, monkeypatch) -> None:
    seat = _Seat(_BASELINE)
    spans: dict[str, _Span] = {}

    def span(name: str, **_attributes: Any):
        spans[name] = _Span()
        return contextlib.nullcontext(spans[name])

    monkeypatch.setattr(_drawing_common._telemetry, "span", span)
    for kind in ("drawing", "pdf"):
        target = tmp_path / f"out.{kind}"
        with _drawing_common._drawing_artifact_save(_adapter(seat), kind, str(target)):
            target.write_bytes(b"x" * 7)
    assert seat.writes == [_DPI, _BASELINE]
    assert (
        "pdf.shaded_draft_dpi.applied" not in spans["drawing.save_drawing"].attributes
    )
    assert spans["drawing.save_pdf"].attributes["pdf.shaded_draft_dpi.applied"] == _DPI
    assert spans["drawing.save_pdf"].attributes["artifact.bytes"] == 7
