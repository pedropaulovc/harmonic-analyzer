"""A hole callout's process prefix keeps a closing line break.

The RD1 probe (917-s1-rd1probe, swmaker000007) read back the cone pivot
post's foot dowel callout as one 117 mm row, "...FROM FOOT 2X <MOD-DIAM>
3.188 <HOLE-DEPTH> 8.5": add_native_hole_callout joined process and format
text as process.rstrip() + " ", which ate the prefix's closing line break.
"""

from __future__ import annotations

import inspect

from types import SimpleNamespace

import pytest
from solidworks_mcp.adapters import sw_type_info
import _drawing_hole_callout

# The probe's read-back: the post's prefix rows and the native format text.
PROBE_PREFIX = "MATCH-DRILL/REAM WITH\nMHA-091 AT ASSEMBLY;\nREAM (.1255 IN) FROM FOOT\n"
PROBE_NATIVE = "2X <MOD-DIAM> 3.188 <HOLE-DEPTH> 8.5"


def test_a_closing_line_break_puts_the_native_size_on_its_own_row() -> None:
    rows = _drawing_hole_callout.compose_hole_callout_prefix(PROBE_PREFIX, PROBE_NATIVE).splitlines()
    assert rows == [
        "MATCH-DRILL/REAM WITH",
        "MHA-091 AT ASSEMBLY;",
        "REAM (.1255 IN) FROM FOOT",
        PROBE_NATIVE,
    ]


def test_a_one_line_process_still_joins_with_one_space() -> None:
    assert _drawing_hole_callout.compose_hole_callout_prefix("DRILL ", " 2X <MOD-DIAM>") == "DRILL 2X <MOD-DIAM>"
    assert _drawing_hole_callout.compose_hole_callout_prefix("A\nB", "2X") == "A\nB 2X"


def test_add_native_hole_callout_composes_through_it() -> None:
    source = inspect.getsource(_drawing_hole_callout.add_native_hole_callout)
    assert "compose_hole_callout_prefix(process, existing)" in source
    assert 'process.rstrip() + " "' not in source


@pytest.mark.parametrize("separate_size_row", [False, True])
@pytest.mark.parametrize("ignored", [False, True])
def test_native_process_prefix_keeps_size_depth_and_tolerance_variables(
    monkeypatch: pytest.MonkeyPatch, ignored: bool, separate_size_row: bool,
) -> None:
    native = "<MOD-DIAM><hw-diam> <hw-tol> <hw-thru>"
    from ch_rocker_arm_spec import ROD_HOLE_SPEC
    from _hole_spec import drill_process

    process = drill_process(ROD_HOLE_SPEC) + ("\n" if separate_size_row else "")
    expected = "#47 DRILL" + ("\n" if separate_size_row else " ") + native
    writes = []
    stored = {5: native}

    def set_text(part, text):
        writes.append((part, text))
        if not ignored:
            stored[5] = text

    annotation = SimpleNamespace(SetPosition2=lambda *_: True)
    display = SimpleNamespace(
        IsHoleCallout=lambda: True,
        GetAnnotation=lambda: annotation,
        GetText=lambda part: stored[part],
        SetText=set_text,
    )
    draw = SimpleNamespace(
        AddHoleCallout2=lambda *_: display,
        ClearSelection2=lambda *_: None,
    )
    adapter = SimpleNamespace(
        currentModel=draw, swApp=SimpleNamespace(RunCommand=lambda *_: True),
    )
    edge = object()
    monkeypatch.setattr(_drawing_hole_callout, "_early_bound", lambda obj, *_: obj)
    monkeypatch.setattr(sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(_drawing_hole_callout, "_select_view_entity", lambda *_a, **_k: edge)
    monkeypatch.setattr(_drawing_hole_callout, "describe_selected_entity", lambda *_a, **_k: {})
    monkeypatch.setattr(_drawing_hole_callout, "rebuild_drawing", lambda *_a, **_k: None)
    kwargs = dict(
        edge=edge, callout_xy=(0.2, 0.1), process=process, label="rod-pin",
    )
    if ignored:
        with pytest.raises(RuntimeError, match="process prefix did not persist"):
            _drawing_hole_callout.add_native_hole_callout(adapter, object(), **kwargs)
    else:
        assert _drawing_hole_callout.add_native_hole_callout(
            adapter, object(), **kwargs,
        ) is display
        assert stored[5] == expected
    assert writes == [(1, expected)]
    assert all(token in writes[0][1] for token in (
        "<MOD-DIAM>", "<hw-diam>", "<hw-tol>", "<hw-thru>",
    ))
    assert not any(nominal in writes[0][1] for nominal in ("1.99", "6.50", "+0.03"))
