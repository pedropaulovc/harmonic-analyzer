r"""Diagnostic: find the exact constraint scheme for the chain centreline loop.

One tangent-continuous loop (knob wrap arc, slack arc, crank wrap arc, taut
line — the _chain.py centreline), constraints added stepwise with a
definition-state probe after each step. Outcome (proven live): the single
loop is fully defined by the two centre anchors, the three radial dims and
ALL FOUR explicit junction tangents — the band's over-definition came from
its two offset loops' concentric arc centres merging at creation and being
double-anchored, not from SW auto-tangents.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diag_chain_loop.py
"""

from __future__ import annotations

import sys
from typing import Any

from _chain import (
    BX as _BX,
    BY as _BY,
    CX as _CX,
    CY as _CY,
    GAX as _GAX,
    GAY as _GAY,
    GBX as _GBX,
    GBY as _GBY,
    SLACK_R,
    TNX as _TNX,
    TNY as _TNY,
    WRAP_R_A,
    WRAP_R_B,
)
from _common import anchor_point_to_origin, check, run_build, set_sketch_direct_db


async def _state(adapter: Any) -> str:
    res = await adapter.check_sketch_fully_defined()
    if res.is_success and res.data:
        return str(res.data.get("definition_state"))
    return f"probe-failed: {res.error}"


async def _step(adapter: Any, label: str, coro) -> None:
    res = await coro
    ok = bool(res.is_success)
    state = await _state(adapter)
    print(f"  {'OK ' if ok else 'XX '} {label} -> state={state}"
          + ("" if ok else f"  [{res.error}]"))
    if state == "over_defined":
        over = await adapter.get_over_defining_relations()
        print(f"  !!  over-defining: {over.data if over.is_success else over.error!r}")


async def build(adapter: Any) -> dict[str, str]:
    check("create_part", await adapter.create_part())
    check("create_sketch loop", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    ra, rb, rs = WRAP_R_A, WRAP_R_B, SLACK_R
    wrap_knob = check(
        "add wrap-knob",
        await adapter.add_arc(0.0, 0.0, ra * _TNX, ra * _TNY, ra * _GAX, ra * _GAY),
    )
    slack = check(
        "add slack",
        await adapter.add_arc(
            _CX, _CY,
            _CX + rs * _GAX, _CY + rs * _GAY,
            _CX + rs * _GBX, _CY + rs * _GBY,
        ),
    )
    wrap_crank = check(
        "add wrap-crank",
        await adapter.add_arc(
            _BX, _BY,
            _BX + rb * _GBX, _BY + rb * _GBY,
            _BX + rb * _TNX, _BY + rb * _TNY,
        ),
    )
    taut = check(
        "add taut",
        await adapter.add_line(_BX + rb * _TNX, _BY + rb * _TNY, ra * _TNX, ra * _TNY),
    )
    set_sketch_direct_db(adapter, False)
    print(f"  ..  initial state: {await _state(adapter)}")

    await anchor_point_to_origin(adapter, f"{wrap_knob}.center", 0.0, 0.0, "knob centre")
    print(f"  ..  after knob anchor: {await _state(adapter)}")
    await anchor_point_to_origin(adapter, f"{wrap_crank}.center", _BX, _BY, "crank centre")
    print(f"  ..  after crank anchor: {await _state(adapter)}")
    for label, arc, radius in (
        ("knob radial", wrap_knob, ra),
        ("slack radial", slack, rs),
        ("crank radial", wrap_crank, rb),
    ):
        await _step(adapter, label,
                    adapter.add_sketch_dimension(arc, None, "radial", radius))
    for label, e1, e2 in (
        ("tangent crank-taut (arc-line)", wrap_crank, taut),
        ("tangent taut-knob (line-arc)", taut, wrap_knob),
        ("tangent knob-slack (arc-arc)", wrap_knob, slack),
        ("tangent slack-crank (arc-arc)", slack, wrap_crank),
    ):
        await _step(adapter, label, adapter.add_sketch_constraint(e1, e2, "tangent"))
    print(f"  ..  final state: {await _state(adapter)}")
    check("exit_sketch", await adapter.exit_sketch())
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
