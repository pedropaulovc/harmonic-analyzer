"""Offline contract for reading a fresh detail view's projection (#1336)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_detail_projection as projection

# Leaf 20261013T033510Z-1-11767ee6 (drawing:dt_cone_swing_platform): detail B's
# outline was centred on its request while its transform still projected the
# centre through the frame the view had before SetViewPosition recentred it.
INK = (0.08349999999999999, 0.04500000000000001)
STALE = (0.07792919217322382, -0.05755193679034118)
CURRENT = (0.08349998709459218, 0.04499996678531765)  # a passing leaf's read
CENTRE = (0.0, 0.0127, -0.006)


class _Detail:
    """A detail whose transform the barrier refreshes once ``rebuilds_needed``
    rebuilds have run (never, for ``None``); rebuilds alone never refresh it."""

    def __init__(self, rebuilds_needed: int | None) -> None:
        self.rebuilds_needed = rebuilds_needed
        self.rebuilds = 0
        self.current = False
        self.events: list[str] = []

    def UpdateViewDisplayGeometry(self) -> None:
        self.events.append("barrier")
        if self.rebuilds_needed is not None and self.rebuilds >= self.rebuilds_needed:
            self.current = True

    def GetOutline(self):
        return (INK[0] - 0.019, INK[1] - 0.02, INK[0] + 0.019, INK[1] + 0.02)

    @property
    def Position(self):
        return (0.09068514155596494, 0.1475519035756588)

    def project(self) -> tuple[float, float]:
        self.events.append("read")
        return CURRENT if self.current else STALE


def _settle(monkeypatch, detail: _Detail, *, rebuild_s: float = 0.15):
    clock = [0.0]
    span: dict[str, object] = {}

    def rebuild(_adapter, *, label):
        detail.events.append(f"rebuild {label}")
        detail.rebuilds += 1
        clock[0] += rebuild_s

    monkeypatch.setattr(projection, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        projection,
        "model_point_in_view",
        lambda _adapter, view, xyz, *, label: view.project(),
    )
    monkeypatch.setattr(projection, "rebuild_drawing", rebuild)
    monkeypatch.setattr(
        projection, "time", SimpleNamespace(perf_counter=lambda: clock[0])
    )
    monkeypatch.setattr(
        projection._telemetry, "annotate", lambda **attrs: span.update(attrs)
    )
    projected = projection.settle_detail_projection(
        SimpleNamespace(),
        detail,
        CENTRE,
        ink_xy=INK,
        tolerance_xy=(0.0005, 0.0005),
        label="detail B",
    )
    return projected, span


def test_the_barrier_makes_the_first_read_current_without_a_rebuild(monkeypatch):
    detail = _Detail(rebuilds_needed=0)
    projected, span = _settle(monkeypatch, detail)
    assert projected == CURRENT
    assert detail.events == ["read", "barrier", "read"]
    assert span["reads"] == 1 and span["rebuilds"] == 0 and span["waited_s"] == 0.0
    assert span["stale_before_refresh"] is True
    assert span["unrefreshed_dy_mm"] == pytest.approx(-102.552, abs=1e-3)
    assert abs(span["dx_mm"]) < 1e-3 and abs(span["dy_mm"]) < 1e-3


def test_a_transform_the_barrier_refreshes_only_after_a_rebuild_is_waited_for(
    monkeypatch,
):
    detail = _Detail(rebuilds_needed=2)
    projected, span = _settle(monkeypatch, detail)
    assert projected == CURRENT
    assert detail.events == [
        "read",
        "barrier",
        "read",
        "rebuild settle detail B",
        "barrier",
        "read",
        "rebuild settle detail B",
        "barrier",
        "read",
    ]
    assert span["reads"] == 3 and span["rebuilds"] == 2
    assert span["waited_s"] == pytest.approx(0.3)


@pytest.mark.parametrize(("rebuild_s", "rebuilds"), [(0.15, 34), (1.0, 5)])
def test_the_settle_is_bounded_by_time_not_by_a_read_count(
    monkeypatch, rebuild_s, rebuilds
):
    detail = _Detail(rebuilds_needed=None)
    with pytest.raises(RuntimeError) as failure:
        _settle(monkeypatch, detail, rebuild_s=rebuild_s)
    message = str(failure.value)
    assert detail.rebuilds == rebuilds
    assert message.startswith(
        f"detail B projects its centre to {STALE} while its outline is centred on {INK}"
    )
    assert f"after {rebuilds + 1} refreshed reads, {rebuilds} rebuilds" in message
    assert "Position (0.09068514155596494, 0.1475519035756588)" in message
