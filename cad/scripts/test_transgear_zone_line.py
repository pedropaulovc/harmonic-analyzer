"""The arm/plate shared sketch-line core, against COM-shaped fakes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _transgear_zone_line as zone_lines


class _App:
    def __init__(self, on: bool, *, sticky: bool = False) -> None:
        self.toggle = on
        self.sticky = sticky
        self.writes: list[bool] = []

    def GetUserPreferenceToggle(self, which: int) -> bool:  # noqa: N802 - COM member name
        assert which == 10
        return self.toggle

    def SetUserPreferenceToggle(self, which: int, value: bool) -> None:  # noqa: N802
        assert which == 10
        self.writes.append(value)
        if not self.sticky:
            self.toggle = value


def test_dimension_input_is_suppressed_inside_and_restored_after() -> None:
    app = _App(True)
    with zone_lines.dimension_input_suppressed(SimpleNamespace(swApp=app)):
        assert app.toggle is False
    assert app.toggle is True and app.writes == [False, True]


def test_dimension_input_that_stays_on_is_refused_and_still_restored() -> None:
    app = _App(True, sticky=True)
    with pytest.raises(RuntimeError, match="stayed on"):
        with zone_lines.dimension_input_suppressed(SimpleNamespace(swApp=app)):
            pass
    assert app.writes == [False, True]


def _placed(color: int, style: int, width: int, end: tuple[float, float, float]):
    point = lambda xyz: SimpleNamespace(X=xyz[0], Y=xyz[1], Z=xyz[2])  # noqa: E731
    line = SimpleNamespace(
        GetStartPoint2=lambda: point((0.0, 0.0, 0.0)), GetEndPoint2=lambda: point(end),
    )
    segment = SimpleNamespace(Color=color, Style=style, Width=width)
    return zone_lines.SketchedLine(segment, line, ((0.0, 0.0, 0.0), (0.01, 0.0, 0.0)))


class _Adapter:
    @staticmethod
    def _get_attr_or_call(target, name):
        value = getattr(target, name)
        return value() if callable(value) else value


@pytest.fixture(autouse=True)
def _plain_binding(monkeypatch):
    import _drawing_sections

    monkeypatch.setattr(zone_lines, "_early_bound", lambda value, _name: value)
    monkeypatch.setattr(_drawing_sections, "_early_bound", lambda value, _name: value)


def test_require_placed_reads_back_font_and_ends() -> None:
    chain = {"style": zone_lines.CHAIN_LINE_STYLE, "width": zone_lines.CHAIN_LINE_WEIGHT}
    good = _placed(0, chain["style"], chain["width"], (0.01, 0.0, 0.0))
    zone_lines.require_placed(_Adapter(), {"zone": good}, label="z", stage="settled", **chain)
    grey = _placed(0x808080, chain["style"], chain["width"], (0.01, 0.0, 0.0))
    with pytest.raises(RuntimeError, match="font reads"):
        zone_lines.require_placed(_Adapter(), {"zone": grey}, label="z", stage="settled", **chain)
    snapped = _placed(0, chain["style"], chain["width"], (0.0101, 0.0, 0.0))
    with pytest.raises(RuntimeError, match="snapped"):
        zone_lines.require_placed(
            _Adapter(), {"zone": snapped}, label="z", stage="settled", **chain
        )
