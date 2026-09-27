"""A hole callout's process prefix keeps a closing line break.

The RD1 probe (917-s1-rd1probe, swmaker000007) read back the cone pivot
post's foot dowel callout as one 117 mm row, "...FROM FOOT 2X <MOD-DIAM>
3.188 <HOLE-DEPTH> 8.5": add_native_hole_callout joined process and format
text as process.rstrip() + " ", which ate the prefix's closing line break.
"""

from __future__ import annotations

import inspect

import _drawing_common as dc

# The probe's read-back: the post's prefix rows and the native format text.
PROBE_PREFIX = "MATCH-DRILL/REAM WITH\nMHA-091 AT ASSEMBLY;\nREAM (.1255 IN) FROM FOOT\n"
PROBE_NATIVE = "2X <MOD-DIAM> 3.188 <HOLE-DEPTH> 8.5"


def test_a_closing_line_break_puts_the_native_size_on_its_own_row() -> None:
    rows = dc.compose_hole_callout_prefix(PROBE_PREFIX, PROBE_NATIVE).splitlines()
    assert rows == [
        "MATCH-DRILL/REAM WITH",
        "MHA-091 AT ASSEMBLY;",
        "REAM (.1255 IN) FROM FOOT",
        PROBE_NATIVE,
    ]


def test_a_one_line_process_still_joins_with_one_space() -> None:
    assert dc.compose_hole_callout_prefix("DRILL ", " 2X <MOD-DIAM>") == "DRILL 2X <MOD-DIAM>"
    assert dc.compose_hole_callout_prefix("A\nB", "2X") == "A\nB 2X"


def test_add_native_hole_callout_composes_through_it() -> None:
    source = inspect.getsource(dc.add_native_hole_callout)
    assert "compose_hole_callout_prefix(process, existing)" in source
    assert 'process.rstrip() + " "' not in source
