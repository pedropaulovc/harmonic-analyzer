
from __future__ import annotations

import asyncio
import json
import os
import pdb
import traceback
from typing import Any

from solidworks_mcp.adapters import create_adapter
from solidworks_mcp.adapters.base import ExtrusionParameters
from solidworks_mcp.config import load_config

SESSION_ID = 'prefab-dashboard'
CHECKPOINT_INDEX = 99
CHECKPOINT_TITLE = 'Mocked-only checkpoint'
PLANNED: dict[str, Any] = json.loads('{"goal": "verify fit", "tools": ["check_interference"]}')
DEBUG_PAUSE = os.getenv("SOLIDWORKS_UI_CHECKPOINT_DEBUG_PAUSE", "0").strip().lower() in ('1', 'true', 'yes', 'on')


def require_key(key: str) -> Any:
    if key not in PLANNED:
        raise ValueError(f"Missing required planned key: {key}")
    return PLANNED[key]


def require_float(key: str) -> float:
    value = require_key(key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {key}: {value!r}") from exc


def require_first_float(*keys: str) -> float:
    for key in keys:
        if key in PLANNED:
            try:
                return float(PLANNED[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid numeric value for {key}: {PLANNED[key]!r}"
                ) from exc
    raise ValueError(f"Missing required planned key(s): {', '.join(keys)}")


def require_vec(key: str, size: int) -> list[float]:
    raw = require_key(key)
    if not isinstance(raw, list) or len(raw) != size:
        raise ValueError(
            f"{key} must be a list with {size} numeric values; got {raw!r}"
        )
    try:
        return [float(v) for v in raw]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must contain numeric values; got {raw!r}") from exc


def require_result(result: Any, label: str) -> Any:
    if result is None:
        raise RuntimeError(f"{label} returned None")
    if not getattr(result, "is_success", False):
        raise RuntimeError(f"{label} failed: {getattr(result, 'error', 'unknown error')}")
    return result


def pause_point(label: str) -> None:
    print(f"EDIT POINT: {label}")
    if DEBUG_PAUSE:
        pdb.set_trace()


def payloads_for_tool(tool: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    direct = PLANNED.get(tool)
    if isinstance(direct, dict):
        payloads.append(dict(direct))

    suffixed: list[tuple[str, dict[str, Any]]] = []
    for key, value in PLANNED.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        if key.startswith(f"{tool}#"):
            suffixed.append((key, dict(value)))

    def suffix_order(item: tuple[str, dict[str, Any]]) -> tuple[int, str]:
        key = item[0]
        suffix = key.split("#", 1)[1] if "#" in key else ""
        return (int(suffix) if suffix.isdigit() else 10_000, key)

    for _, payload in sorted(suffixed, key=suffix_order):
        payloads.append(payload)

    return payloads


def key_from(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]
    return require_key(key)


def vec_from(payload: dict[str, Any], key: str, size: int) -> list[float]:
    raw = key_from(payload, key)
    if not isinstance(raw, list) or len(raw) != size:
        raise ValueError(
            f"{key} must be a list with {size} numeric values; got {raw!r}"
        )
    try:
        return [float(v) for v in raw]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must contain numeric values; got {raw!r}") from exc


def first_float_from(payload: dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value for {key}: {payload[key]!r}") from exc
    return require_first_float(*keys)


async def run_checkpoint() -> dict[str, Any]:
    tools = PLANNED.get("tools", [])
    if not isinstance(tools, list) or not tools:
        raise ValueError("planned.tools must be a non-empty list")

    tool_runs: list[dict[str, str]] = []
    failed_tools: list[str] = []

    config = load_config()
    adapter = await create_adapter(config)

    await adapter.connect()
    try:
        for idx, tool in enumerate([str(t) for t in tools], start=1):
            pause_point(f"checkpoint {CHECKPOINT_INDEX} step {idx}/{len(tools)} before {tool}")
            print(f"CHECKPOINT {CHECKPOINT_INDEX} STEP {idx}/{len(tools)}: {tool}")
            try:
                if tool == "create_part":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    part_name = str(key_from(payload, "part_name"))
                    require_result(await adapter.create_part(name=part_name), "create_part")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Created part '{part_name}'"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_part")

                elif tool == "create_assembly":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    assembly_name = str(key_from(payload, "assembly_name"))
                    require_result(await adapter.create_assembly(name=assembly_name), "create_assembly")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Created assembly '{assembly_name}'"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_assembly")

                elif tool == "open_model":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    model_path = str(key_from(payload, "model_path"))
                    require_result(await adapter.open_model(model_path), "open_model")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Opened model '{model_path}'"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after open_model")

                elif tool == "create_sketch":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        sketch_plane = str(key_from(payload, "sketch_plane"))
                        require_result(await adapter.create_sketch(sketch_plane), "create_sketch")
                        tool_runs.append({"tool": tool, "status": "success", "message": f"Created sketch on '{sketch_plane}'"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_sketch")

                elif tool == "exit_sketch":
                    require_result(await adapter.exit_sketch(), "exit_sketch")
                    tool_runs.append({"tool": tool, "status": "success", "message": "Exited sketch"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after exit_sketch")

                elif tool == "add_line":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        if "line_mm" in payload or "line_mm" in PLANNED:
                            x1, y1, x2, y2 = vec_from(payload, "line_mm", 4)
                        else:
                            sx, sy = vec_from(payload, "line_start_mm", 2)
                            ex, ey = vec_from(payload, "line_end_mm", 2)
                            x1, y1, x2, y2 = sx, sy, ex, ey
                        require_result(await adapter.add_line(x1, y1, x2, y2), "add_line")
                        tool_runs.append({"tool": tool, "status": "success", "message": "Added line"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_line")

                elif tool == "add_rectangle":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        x, y, width, height = vec_from(payload, "rectangle_mm", 4)
                        require_result(await adapter.add_rectangle(x, y, width, height), "add_rectangle")
                        tool_runs.append({"tool": tool, "status": "success", "message": "Added rectangle"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_rectangle")

                elif tool == "add_circle":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        cx, cy = vec_from(payload, "circle_center_mm", 2)
                        radius = first_float_from(payload, "circle_radius_mm")
                        require_result(await adapter.add_circle(cx, cy, radius), "add_circle")
                        tool_runs.append({"tool": tool, "status": "success", "message": "Added circle"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_circle")

                elif tool == "add_centerline":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        x1, y1, x2, y2 = vec_from(payload, "centerline_mm", 4)
                        require_result(await adapter.add_centerline(x1, y1, x2, y2), "add_centerline")
                        tool_runs.append({"tool": tool, "status": "success", "message": "Added centerline"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_centerline")

                elif tool == "add_arc":
                    payloads = payloads_for_tool(tool) or [{}]
                    for payload in payloads:
                        cx, cy = vec_from(payload, "arc_center_mm", 2)
                        sx, sy = vec_from(payload, "arc_start_mm", 2)
                        ex, ey = vec_from(payload, "arc_end_mm", 2)
                        require_result(await adapter.add_arc(cx, cy, sx, sy, ex, ey), "add_arc")
                        tool_runs.append({"tool": tool, "status": "success", "message": "Added arc"})
                        pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_arc")

                elif tool == "create_extrusion":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    depth = first_float_from(payload, "depth_mm", "depth")
                    params = ExtrusionParameters(
                        depth=depth,
                        thin_feature=bool(payload.get("thin_feature", PLANNED.get("thin_feature", False))),
                        thin_thickness=(
                            float(payload["thin_thickness_mm"])
                            if "thin_thickness_mm" in payload
                            else (
                                float(PLANNED["thin_thickness_mm"])
                                if "thin_thickness_mm" in PLANNED
                                else float(payload.get("thin_thickness", PLANNED.get("thin_thickness", 0.0)))
                            )
                        ),
                        both_directions=bool(payload.get("both_directions", PLANNED.get("both_directions", False))),
                    )
                    require_result(await adapter.create_extrusion(params), "create_extrusion")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Created extrusion depth={depth}mm"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_extrusion")

                elif tool == "create_cut_extrude":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    depth = first_float_from(payload, "depth_mm", "depth")
                    params = ExtrusionParameters(depth=depth)
                    require_result(await adapter.create_cut_extrude(params), "create_cut_extrude")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Created cut-extrude depth={depth}mm"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_cut_extrude")

                elif tool == "create_cut":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    depth = first_float_from(payload, "depth_mm", "depth")
                    sketch_name = str(payload.get("sketch_name", PLANNED.get("sketch_name", "")))
                    if sketch_name:
                        require_result(await adapter.create_cut(sketch_name, depth), "create_cut")
                        tool_runs.append({"tool": tool, "status": "success", "message": f"Created cut from {sketch_name} depth={depth}mm"})
                    else:
                        params = ExtrusionParameters(depth=depth)
                        require_result(await adapter.create_cut_extrude(params), "create_cut")
                        tool_runs.append({"tool": tool, "status": "success", "message": f"Created cut-extrude depth={depth}mm"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after create_cut")

                elif tool == "add_fillet":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    radius = first_float_from(payload, "radius_mm", "radius")
                    raw_edges = payload.get("edge_names", PLANNED.get("edge_names", []))
                    edge_names = [str(edge) for edge in raw_edges] if isinstance(raw_edges, list) else []
                    require_result(await adapter.add_fillet(radius, edge_names), "add_fillet")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Added fillet radius={radius}mm"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after add_fillet")

                elif tool == "check_sketch_fully_defined":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    sketch_name = payload.get("sketch_name", PLANNED.get("sketch_name"))
                    require_result(
                        await adapter.check_sketch_fully_defined(
                            str(sketch_name) if sketch_name else None
                        ),
                        "check_sketch_fully_defined",
                    )
                    tool_runs.append({"tool": tool, "status": "success", "message": "Checked sketch definition"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after check_sketch_fully_defined")

                elif tool == "save_file":
                    payload = (payloads_for_tool(tool) or [{}])[0]
                    file_path = str(key_from(payload, "file_path"))
                    require_result(await adapter.save_file(file_path), "save_file")
                    tool_runs.append({"tool": tool, "status": "success", "message": f"Saved file '{file_path}'"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after save_file")

                elif tool == "get_model_info":
                    require_result(await adapter.get_model_info(), "get_model_info")
                    tool_runs.append({"tool": tool, "status": "success", "message": "Retrieved model info"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after get_model_info")

                elif tool == "list_features":
                    require_result(
                        await adapter.list_features(include_suppressed=True),
                        "list_features",
                    )
                    tool_runs.append({"tool": tool, "status": "success", "message": "Listed features"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after list_features")

                elif tool == "get_mass_properties":
                    require_result(await adapter.get_mass_properties(), "get_mass_properties")
                    tool_runs.append({"tool": tool, "status": "success", "message": "Retrieved mass properties"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after get_mass_properties")

                elif tool == "analyze_geometry":
                    require_result(await adapter.get_model_info(), "analyze_geometry.get_model_info")
                    require_result(
                        await adapter.list_features(include_suppressed=True),
                        "analyze_geometry.list_features",
                    )
                    require_result(
                        await adapter.get_mass_properties(),
                        "analyze_geometry.get_mass_properties",
                    )
                    tool_runs.append({"tool": tool, "status": "success", "message": "Geometry analysis completed"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after analyze_geometry")

                elif tool == "export_image":
                    payloads = payloads_for_tool(tool)
                    payload = payloads[0] if payloads else PLANNED.get("export_image")
                    if payload is None:
                        payload = {
                            "file_path": require_key("file_path"),
                            "format_type": require_key("format_type"),
                        }
                        if "width" in PLANNED:
                            payload["width"] = int(PLANNED["width"])
                        if "height" in PLANNED:
                            payload["height"] = int(PLANNED["height"])
                        if "view_orientation" in PLANNED:
                            payload["view_orientation"] = str(PLANNED["view_orientation"])
                    if not isinstance(payload, dict):
                        raise ValueError("export_image must be an object payload")
                    require_result(await adapter.export_image(payload), "export_image")
                    tool_runs.append({"tool": tool, "status": "success", "message": "Exported image"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after export_image")

                elif tool == "check_interference":
                    payload = require_key("check_interference")
                    if not isinstance(payload, dict):
                        raise ValueError("check_interference must be an object payload")
                    require_result(await adapter.check_interference(payload), "check_interference")
                    tool_runs.append({"tool": tool, "status": "success", "message": "Checked interference"})
                    pause_point(f"checkpoint {CHECKPOINT_INDEX} after check_interference")

                else:
                    raise ValueError(f"Unsupported tool '{tool}' in strict script mode")

            except Exception as step_exc:
                failed_tools.append(tool)
                tool_runs.append({"tool": tool, "status": "error", "message": str(step_exc)})
                break

    finally:
        try:
            await adapter.disconnect()
        except Exception:
            pass

    return {
        "tool_runs": tool_runs,
        "failed_tools": failed_tools,
    }


def main() -> int:
    try:
        summary = asyncio.run(run_checkpoint())
        print("CHECKPOINT_SCRIPT_RESULT::" + json.dumps(summary, ensure_ascii=True))
        return 0 if not summary.get("failed_tools") else 1
    except Exception as exc:
        summary = {
            "tool_runs": [
                {"tool": "checkpoint.script", "status": "error", "message": str(exc)},
                {"tool": "checkpoint.script", "status": "error", "message": traceback.format_exc()},
            ],
            "failed_tools": ["checkpoint.script"],
        }
        print("CHECKPOINT_SCRIPT_RESULT::" + json.dumps(summary, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
