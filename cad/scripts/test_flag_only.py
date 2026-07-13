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


def test_early_bound_delegates_with_selective_fallback_names(monkeypatch) -> None:
    """Shared helpers request a typed wrapper and retain an exact-name fallback."""
    from solidworks_mcp.adapters import sw_type_info

    original = object()
    typed = object()
    calls = []

    def wrap(obj, interface, *methods):
        calls.append((obj, interface, methods))
        return typed

    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", wrap)
    assert _early_bound(original, "IComponent2", "GetModelDoc2") is typed
    assert calls == [(original, "IComponent2", ("GetModelDoc2",))]


if __name__ == "__main__":
    test_flags_only_the_named_methods()
    test_object_without_flag_method_is_noop()
    test_unknown_names_are_skipped()
    print("test_flag_only: all passed")
