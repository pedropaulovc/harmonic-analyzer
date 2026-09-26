"""#923: every project drawing prints a nil tolerance deviation as a bare 0."""

from __future__ import annotations

import pytest

import _drawing_common as dc


class _Extension:
    def __init__(self, *, dimension_style: int = 1, accept: bool = True) -> None:
        self.prefs = {(dc._PREF_DIM_TRAILING_ZERO, 0): dimension_style, (dc._PREF_TOL_TRAILING_ZERO, 0): 1}
        self.accept = accept
        self.writes: list[tuple[int, int, int]] = []

    def SetUserPreferenceInteger(self, pref: int, option: int, value: int) -> bool:
        self.writes.append((pref, option, value))
        if not self.accept:
            return False
        self.prefs[(pref, option)] = value
        return True

    def GetUserPreferenceInteger(self, pref: int, option: int) -> int:
        return self.prefs[(pref, option)]


class _Drawing:
    def __init__(self, extension: _Extension) -> None:
        self.Extension = extension


def test_the_drawing_strips_zeros_of_a_nil_deviation_only():
    extension = _Extension()
    dc._pin_tolerance_zero_display(_Drawing(extension))
    assert extension.prefs[(582, 0)] == 4  # swDimRemoveOnlyOnZero
    assert extension.writes == [(582, 0, 4)]  # 15 (the nominal's style) is never written


def test_a_smart_dimension_style_fails_loud_before_any_write():
    extension = _Extension(dimension_style=0)
    with pytest.raises(RuntimeError, match="Smart"):
        dc._pin_tolerance_zero_display(_Drawing(extension))
    assert extension.writes == []


def test_a_refused_pin_fails_loud():
    with pytest.raises(RuntimeError, match="document reads 1"):
        dc._pin_tolerance_zero_display(_Drawing(_Extension(accept=False)))


def test_every_project_drawing_pins_it():
    import inspect

    source = inspect.getsource(dc.new_project_drawing)
    assert "_pin_tolerance_zero_display(draw)" in source
