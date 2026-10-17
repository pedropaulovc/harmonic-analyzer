"""Offline contract for the drawing's all-uppercase dimension text pin.

``_pin_uppercase_dimensions`` turns on Drafting Standard > "All uppercase for
dimensions and hole callouts" on every new drawing so swTolMAX / swTolMIN
print MAX / MIN. Pinned here: the document toggle is written on and read back,
and a refused write fails the drawing instead of shipping lowercase text.

    python -m pytest cad/scripts/test_drawing_uppercase_dimensions.py
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _drawing_common

_TOGGLE = _drawing_common._PREF_UPPERCASE_DIMENSIONS
_EXCLUSIONS = _drawing_common._PREF_UPPERCASE_EXCLUSION_LIST
_NO_OPTION = _drawing_common._DETAILING_NO_OPTION


class _Extension:
    """``IModelDocExtension`` document preferences; ``refuse`` ignores writes."""

    def __init__(self, *, refuse: bool = False) -> None:
        self.toggles = {(_TOGGLE, _NO_OPTION): False}
        self.strings = {(_EXCLUSIONS, _NO_OPTION): "m;mm;"}
        self.refuse = refuse
        self.writes: list[bool] = []

    def SetUserPreferenceToggle(self, pref: int, option: int, value: bool) -> bool:
        self.writes.append(value)
        if self.refuse:
            return False
        self.toggles[(pref, option)] = value
        return True

    def GetUserPreferenceToggle(self, pref: int, option: int) -> bool:
        return self.toggles[(pref, option)]

    def GetUserPreferenceString(self, pref: int, option: int) -> str:
        return self.strings[(pref, option)]


def test_uppercase_dimensions_are_switched_on_and_read_back() -> None:
    ext = _Extension()

    _drawing_common._pin_uppercase_dimensions(SimpleNamespace(Extension=ext))

    assert ext.writes == [False, True]
    assert ext.toggles[(_TOGGLE, _NO_OPTION)] is True
    assert ext.strings[(_EXCLUSIONS, _NO_OPTION)] == "m;mm;"


def test_refused_uppercase_toggle_fails_the_drawing() -> None:
    ext = _Extension(refuse=True)

    with pytest.raises(RuntimeError, match="all-uppercase dimensions"):
        _drawing_common._pin_uppercase_dimensions(SimpleNamespace(Extension=ext))
