"""Probe where ``GetVisibleEntities2`` time goes on the frame nameplate (issue #768).

Read-only: opens the built frame assembly, places the exploded isometric in a
scratch drawing, and times, for the nameplate component, the native count, a raw
``InvokeTypes`` fetch (no per-element pywin32 wrapping), per-element wrap/bind
costs, the wrapped makepy call, and finally RELEASING the fetched proxies -- one
cross-process ``Release`` each, which no fetch strategy avoids. Nothing is saved.
Must run under ``dodo._com_seat`` (``HARMONIC_COM_SEAT``).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32com.client  # noqa: E402

import draw_frame_assembly as frame  # noqa: E402
from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_common import (  # noqa: E402
    _drawing_component_children,
    _drawing_component_stems,
    _edge_endpoint_key,
    set_high_quality_shaded_with_edges,
)
from solidworks_mcp.adapters import sw_type_info  # noqa: E402
from solidworks_mcp.adapters.solidworks.drawing import new_drawing, place_view  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "out" / "reports" / "probe-balloon-anchor.json"
STEM = "nameplate"
SAMPLE = 200


def _timed(results: dict[str, Any], key: str, fn):
    started = time.perf_counter()
    value = fn()
    results[key] = round(time.perf_counter() - started, 4)
    print(f"{key}: {results[key]} s", file=sys.stderr, flush=True)
    return value


def _raw_visible_entities(view: Any, component: Any, kind: int) -> tuple[Any, ...]:
    dispid = view._oleobj_.GetIDsOfNames("GetVisibleEntities2")
    raw = view._oleobj_.InvokeTypes(
        dispid, 0, 1, (12, 0), ((9, 1), (3, 1)), component._oleobj_, kind
    )
    return tuple(raw or ())


def _walk_leaves(adapter: Any, view: Any, stem: str) -> tuple[int, Any]:
    root = view.RootDrawingComponent2(False)
    pending = list(_drawing_component_children(root))
    visited = 0
    while pending:
        drawing_component = pending.pop()
        children = _drawing_component_children(drawing_component)
        pending.extend(children)
        if children:
            continue
        visited += 1
        if stem in _drawing_component_stems(adapter, drawing_component, frozenset({stem})):
            return visited, drawing_component
    return visited, None


async def build(adapter: Any) -> dict[str, str]:
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("probe must run inside dodo._com_seat")
    results: dict[str, Any] = {"stem": STEM}
    check("open frame assembly", await adapter.open_model(str(frame.SOURCE)))
    new_drawing(adapter, width=0.4318, height=0.2794)
    view = place_view(
        adapter, str(frame.SOURCE), "*Isometric", 0.20, 0.14, scale=frame.EXPLODED_ISO_SCALE
    )
    frame._set_exploded_state(adapter, view, True, label="probe exploded")
    set_high_quality_shaded_with_edges(adapter, view, label="probe exploded")
    view = _early_bound(view, "IView")

    visited, drawing_component = _timed(
        results, "tree_walk_s", lambda: _walk_leaves(adapter, view, STEM)
    )
    results["tree_walk_visited"] = visited
    if drawing_component is None:
        raise RuntimeError("nameplate drawing component not found")
    component = _early_bound(drawing_component.Component, "IComponent2")
    results["component"] = str(component.Name2)

    results["count_edges"] = _timed(
        results, "count_edges_s", lambda: int(view.GetVisibleEntityCount2(component, 1))
    )
    results["count_faces"] = _timed(
        results, "count_faces_s", lambda: int(view.GetVisibleEntityCount2(component, 3))
    )
    raw_edges = _timed(
        results, "raw_fetch_edges_s", lambda: _raw_visible_entities(view, component, 1)
    )
    results["raw_edges"] = len(raw_edges)
    results["raw_element_type"] = type(raw_edges[0]).__name__ if raw_edges else None
    raw_faces = _timed(
        results, "raw_fetch_faces_s", lambda: _raw_visible_entities(view, component, 3)
    )
    results["raw_faces"] = len(raw_faces)

    sample = raw_edges[:SAMPLE]
    results["sample"] = len(sample)
    _timed(
        results,
        "generic_wrap_sample_s",
        lambda: [win32com.client.Dispatch(item) for item in sample],
    )
    edge_class = sw_type_info._strict_subclass(sw_type_info._interface_class("IEdge"))
    bound = _timed(
        results, "class_bind_sample_s", lambda: [edge_class(item) for item in sample]
    )
    _timed(
        results,
        "endpoint_key_first20_s",
        lambda: [_edge_endpoint_key(adapter, edge) for edge in bound[:20]],
    )
    results["first_edge_key_raw"] = list(_edge_endpoint_key(adapter, bound[0]) or ())

    wrapped = _timed(
        results,
        "wrapped_fetch_edges_s",
        lambda: tuple(view.GetVisibleEntities2(component, 1) or ()),
    )
    results["wrapped_edges"] = len(wrapped)
    compared = min(len(wrapped), len(raw_edges), SAMPLE)
    results["same_order_first_n"] = compared
    results["same_order"] = all(
        wrapped[index]._oleobj_ == raw_edges[index] for index in range(compared)
    )
    results["first_edge_key_wrapped"] = list(
        _edge_endpoint_key(adapter, _early_bound(wrapped[0], "IEdge")) or ()
    )
    # Every proxy above shares identity with its raw twin, so the round-trips
    # happen only when the LAST reference to each element drops.
    held = [raw_edges, raw_faces, sample, bound, wrapped]
    raw_edges = raw_faces = sample = bound = wrapped = None
    _timed(results, "release_all_s", held.clear)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))
