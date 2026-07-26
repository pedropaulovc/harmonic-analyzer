r"""Tests for the targeted ``_flag_only`` COM-method flag helper (no SolidWorks).

``_flag_only`` replaces whole-interface ``_flag(comp, "IComponent2")`` (165
``_FlagAsMethod`` round-trips) in per-component loops with a flag of just the
one or two zero-arg methods actually called -- the fix for issue #87. The
helper is pure dispatch glue, so it runs in plain CI:

    python cad/scripts/test_flag_only.py        # or: pytest cad/scripts/test_flag_only.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import _early_bound, _flag_only  # noqa: E402


class _Flaggable:
    """Stand-in for a pywin32 CDispatch recording _FlagAsMethod calls."""

    def __init__(self) -> None:
        self.flagged: list[str] = []

    def _FlagAsMethod(self, name: str) -> None:  # noqa: N802 — COM casing
        self.flagged.append(name)


def test_flags_only_the_named_methods() -> None:
    """Only the given names are flagged -- not a whole interface (issue #87)."""
    obj = _Flaggable()
    _flag_only(obj, "GetConstrainedStatus", "IsPatternInstance")
    assert obj.flagged == ["GetConstrainedStatus", "IsPatternInstance"]


def test_object_without_flag_method_is_noop() -> None:
    """An object lacking _FlagAsMethod is a silent no-op, never raises."""
    _flag_only(object(), "GetConstrainedStatus")  # must not raise


def test_unknown_names_are_skipped() -> None:
    """A name not on the dispatch raises in _FlagAsMethod and is skipped."""

    class _Picky:
        def __init__(self) -> None:
            self.flagged: list[str] = []

        def _FlagAsMethod(self, name: str) -> None:  # noqa: N802 — COM casing
            if name == "Unknown":
                raise Exception("Unknown name.")
            self.flagged.append(name)

    obj = _Picky()
    _flag_only(obj, "GetConstrainedStatus", "Unknown")
    assert obj.flagged == ["GetConstrainedStatus"]


class _Dispatch:
    """Stand-in for a live pywin32 CDispatch (identified by ``_oleobj_``)."""

    def __init__(self) -> None:
        self._oleobj_ = object()


def _patch_binding(monkeypatch, *, typed, early: bool):
    from solidworks_mcp.adapters import sw_type_info

    monkeypatch.setattr(sw_type_info, "early_bound", lambda obj, iface: typed)
    monkeypatch.setattr(
        sw_type_info, "is_early_bound", lambda obj, iface: early
    )


def test_early_bound_returns_the_generated_wrapper(monkeypatch) -> None:
    typed = _Dispatch()
    _patch_binding(monkeypatch, typed=typed, early=True)
    assert _early_bound(_Dispatch(), "IComponent2", "GetModelDoc2") is typed


def test_early_bound_RAISES_rather_than_returning_a_raw_dispatch(monkeypatch)\
        -> None:
    """The root-cause fix for the [out]-param trap.

    This replaced ``test_early_bound_delegates_with_selective_fallback_names``,
    which pinned the OPPOSITE contract: delegate to ``early_bound_or_flag``,
    which hands back a flagged LATE-BOUND object when no generated class
    resolves. That silent downgrade is the bug -- it flips where a method's
    ``[out]`` params land (return tuple vs byref VARIANT) with nothing visible
    at the call site, and the wrong choice reads as "no data" rather than
    failing. The old contract was deliberate, so this is a deliberate reversal,
    not an assertion loosened to make a test pass.
    """
    original = _Dispatch()
    _patch_binding(monkeypatch, typed=original, early=False)
    with pytest.raises(RuntimeError, match="could not bind"):
        _early_bound(original, "IComponent2", "GetModelDoc2")


def test_non_com_objects_still_pass_through_quietly(monkeypatch) -> None:
    """Test doubles and None never reach a COM boundary, so they are exempt."""
    double = object()  # no _oleobj_
    assert _early_bound(double, "IComponent2") is double
    assert _early_bound(None, "IComponent2") is None


if __name__ == "__main__":
    test_flags_only_the_named_methods()
    test_object_without_flag_method_is_noop()
    test_unknown_names_are_skipped()
    print("test_flag_only: all passed")
