"""Benchmark shared COM dispatch overhead on an existing SolidWorks model.

The harness is read-only: it opens a supplied model, runs one selected traversal,
reports timing plus binding/flagging cost as JSON, and closes without saving.
Launch it through ``dodo._run(..., com=True)``; the environment guard prevents an
accidental standalone run from bypassing the machine-global SolidWorks seat lock.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument(
        "--workload", choices=("layout", "features", "mates"), default="layout"
    )
    parser.add_argument(
        "--mode",
        choices=("early", "flag"),
        default="early",
        help="'early' = early binding (current); 'flag' = force the pre-migration "
        "whole-interface flag_methods path, for an A/B on the same seat + model",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="checkout whose shared code and SolidworksMCP submodule to benchmark",
    )
    return parser.parse_args()


async def _run(
    model_path: Path, repo: Path, workload: str, mode: str = "early"
) -> dict[str, Any]:
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("benchmark must run inside dodo._com_seat")

    repo = repo.resolve()
    sys.path.insert(0, str(repo / "SolidworksMCP-python" / "src"))
    sys.path.insert(0, str(repo / "cad" / "scripts"))

    import _telemetry
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    _telemetry.set_service("diagnostic-com-benchmark")
    adapter = PyWin32Adapter()
    flag_calls: Counter[str] = Counter()
    flag_seconds: Counter[str] = Counter()
    selective_flag_calls: Counter[str] = Counter()
    selective_flag_seconds: Counter[str] = Counter()
    binding_calls: Counter[str] = Counter()
    binding_seconds: Counter[str] = Counter()
    original_flag_methods = sw_type_info.flag_methods
    original_flag_method_names = getattr(sw_type_info, "flag_method_names", None)
    original_early_bound = getattr(sw_type_info, "early_bound", None)

    def _timed_flag_methods(obj: Any, *interfaces: str) -> int:
        started = time.perf_counter()
        try:
            return original_flag_methods(obj, *interfaces)
        finally:
            elapsed = time.perf_counter() - started
            key = "+".join(interfaces) or "<none>"
            flag_calls[key] += 1
            flag_seconds[key] += elapsed

    def _timed_flag_method_names(obj: Any, *names: str) -> int:
        started = time.perf_counter()
        try:
            if original_flag_method_names is None:
                return 0
            return original_flag_method_names(obj, *names)
        finally:
            elapsed = time.perf_counter() - started
            key = "+".join(names) or "<none>"
            selective_flag_calls[key] += 1
            selective_flag_seconds[key] += elapsed

    def _timed_early_bound(obj: Any, interface: str) -> Any:
        started = time.perf_counter()
        try:
            if original_early_bound is None:
                return obj
            return original_early_bound(obj, interface)
        finally:
            binding_calls[interface] += 1
            binding_seconds[interface] += time.perf_counter() - started

    # 'flag' mode reproduces the pre-migration cost: route every call site's
    # early_bound_or_flag through whole-interface flag_methods (timed above) and
    # return the object unwrapped, exactly as the old code did.
    original_early_bound_or_flag = sw_type_info.early_bound_or_flag

    def _flag_mode_early_bound_or_flag(
        obj: Any, interface: str, *_names: str
    ) -> Any:
        if obj is not None:
            sw_type_info.flag_methods(obj, interface)
        return obj

    sw_type_info.flag_methods = _timed_flag_methods
    if original_flag_method_names is not None:
        sw_type_info.flag_method_names = _timed_flag_method_names
    if original_early_bound is not None:
        sw_type_info.early_bound = _timed_early_bound
    if mode == "flag":
        sw_type_info.early_bound_or_flag = _flag_mode_early_bound_or_flag
    try:
        with _telemetry.span(
            "benchmark.com_dispatch", model=str(model_path), workload=workload
        ):
            with _telemetry.span("benchmark.connect"):
                await adapter.connect()
            with _telemetry.span("benchmark.open"):
                adapter.swApp.CloseAllDocuments(True)
                opened = await adapter.open_model(str(model_path.resolve()))
            if not opened.is_success:
                raise RuntimeError(f"failed to open benchmark model: {opened.error}")

            with _telemetry.span("benchmark.collect"):
                started = time.perf_counter()
                if workload == "layout":
                    import _drawing_common

                    elements, width, height = (
                        _drawing_common.collect_layout_elements(adapter)
                    )
                    signature = [
                        [
                            element.label,
                            element.kind,
                            round(element.xmin, 9),
                            round(element.ymin, 9),
                            round(element.xmax, 9),
                            round(element.ymax, 9),
                            element.scope.value,
                            element.owner,
                        ]
                        for element in elements
                    ]
                    item_count = len(elements)
                    workload_data: dict[str, Any] = {"sheet": [width, height]}
                elif workload == "features":
                    result = await adapter.list_features(include_suppressed=True)
                    if not result.is_success:
                        raise RuntimeError(f"feature walk failed: {result.error}")
                    rows = result.data or []
                    signature = [
                        [
                            row.get("name"),
                            row.get("type"),
                            bool(row.get("suppressed")),
                            row.get("position"),
                        ]
                        for row in rows
                    ]
                    item_count = len(rows)
                    workload_data = {}
                else:
                    result = await adapter.list_mates()
                    if not result.is_success:
                        raise RuntimeError(f"mate walk failed: {result.error}")
                    rows = result.data or []
                    signature = [
                        [
                            row.get("name"),
                            row.get("type"),
                            bool(row.get("suppressed")),
                        ]
                        for row in rows
                    ]
                    item_count = len(rows)
                    workload_data = {}
                elapsed = time.perf_counter() - started
            return {
                "repo": str(repo),
                "model": str(model_path.resolve()),
                "workload": workload,
                "mode": mode,
                "elapsed_seconds": round(elapsed, 6),
                "item_count": item_count,
                **workload_data,
                "flag_calls": dict(sorted(flag_calls.items())),
                "flag_seconds": {
                    key: round(value, 6) for key, value in sorted(flag_seconds.items())
                },
                "selective_flag_calls": dict(sorted(selective_flag_calls.items())),
                "selective_flag_seconds": {
                    key: round(value, 6)
                    for key, value in sorted(selective_flag_seconds.items())
                },
                "binding_calls": dict(sorted(binding_calls.items())),
                "binding_seconds": {
                    key: round(value, 6)
                    for key, value in sorted(binding_seconds.items())
                },
                "signature": signature,
            }
    finally:
        sw_type_info.flag_methods = original_flag_methods
        if original_flag_method_names is not None:
            sw_type_info.flag_method_names = original_flag_method_names
        if original_early_bound is not None:
            sw_type_info.early_bound = original_early_bound
        sw_type_info.early_bound_or_flag = original_early_bound_or_flag
        with _telemetry.span("benchmark.disconnect"):
            await adapter.disconnect()


def main() -> int:
    args = _args()
    result = asyncio.run(_run(args.model, args.repo, args.workload, args.mode))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
