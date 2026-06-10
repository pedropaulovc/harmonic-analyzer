"""Shared infrastructure for the part reproduction scripts.

Every part/assembly in ``cad/out`` is built by a ``build_<part>.py`` script in
this directory that drives SolidWorks through the ``PyWin32Adapter`` from the
SolidworksMCP-python repo (expected as a sibling checkout at
``C:/src/SolidworksMCP-python``, overridable via ``SOLIDWORKS_MCP_ROOT``).

Conventions (see cad/DIMENSIONS.md for the dimension source of truth):

* All sketch geometry is in millimetres; dimension constants are declared at
  the top of each script and traceable to a DIMENSIONS.md row.
* Every sketch must pass ``check_sketch_fully_defined`` before it is consumed
  by a feature — use :func:`ensure_fully_defined`.

Fully-defined recipes (probed live on SW 2026):

* **Line chains**: consecutive ``add_line`` calls sharing exact endpoint
  coordinates get merged/coincident vertices; with one vertex on the sketch
  origin, horizontal/vertical constraints and per-segment length dimensions
  fully define the chain — no ``fix`` needed.
* **Circles**: centre points are not addressable with the current tool
  surface, so anchor with ``fix`` FIRST, then add the diameter dimension —
  SolidWorks auto-marks a dimension added to fixed geometry as driven, while
  the reverse order (dimension, then fix) makes the sketch over-defined. Use
  :func:`define_circle`.
* **Off-origin line profiles**: pass the line IDs as ``fix_entities`` —
  perpendicular fixed lines with merged vertices pin each other's endpoints.
* **Never mix driving dimensions with fix escalation across a chain**: a
  driving dim determines geometry downstream through merged vertices;
  fixing any of that downstream geometry re-pins what the dim already
  determined and the sketch goes over-defined (consistent-but-redundant
  counts — caught live on the channel-lever outline). A profile is either
  constraints+dims with no fixes (amplitude-bar style, needs an origin
  vertex) or fix-only (crank-pin style).
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from collections.abc import Awaitable, Callable, Iterable
from pathlib import Path
from typing import Any

CAD_ROOT = Path(__file__).resolve().parents[1]
OUT_SLDPRT = CAD_ROOT / "out" / "sldprt"
OUT_SLDASM = CAD_ROOT / "out" / "sldasm"
OUT_PNG = CAD_ROOT / "out" / "png"

SW_MCP_ROOT = Path(os.environ.get("SOLIDWORKS_MCP_ROOT", r"C:\src\SolidworksMCP-python"))
sys.path.insert(0, str(SW_MCP_ROOT / "src"))

IN = 25.4  # inch -> mm

DEFAULT_VIEWS = ("front", "top", "isometric")


def check(label: str, result: Any) -> Any:
    """Raise when an adapter result is not success; return ``result.data``."""
    if not result.is_success:
        raise RuntimeError(f"{label} failed: {result.error}")
    print(f"  OK  {label}")
    return result.data


async def ensure_fully_defined(
    adapter: Any, label: str, fix_entities: Iterable[str] = ()
) -> None:
    """Assert the active sketch is fully defined, escalating to ``fix``.

    Checks ``check_sketch_fully_defined``; when under-defined and
    ``fix_entities`` are provided, applies a ``fix`` relation to each and
    re-checks. Raises if the sketch still is not fully defined.
    """
    async def _state() -> str | None:
        res = await adapter.check_sketch_fully_defined()
        if res.is_success and res.data:
            state = res.data.get("definition_state")
            if state not in ("fully_defined", "under_defined", "over_defined"):
                print(f"  ..  check payload: {res.data!r}")
            return state
        return None

    state = await _state()
    if state == "fully_defined":
        print(f"  OK  fully defined: {label}")
        return

    # Escalate one entity at a time: fixing everything at once makes the
    # driving dimensions redundant and over-defines the sketch. "unknown"
    # is kept fixable as a safety net: the status probe can transiently fail
    # (pywin32 property/method resolution drift on GetConstrainedStatus) and
    # a later read may recover.
    for entity_id in fix_entities:
        if state not in ("under_defined", "unknown"):
            break
        fixed = await adapter.add_sketch_constraint(entity_id, None, "fix")
        if not fixed.is_success:
            raise RuntimeError(f"{label}: fix {entity_id} failed: {fixed.error}")
        state = await _state()
        print(f"  ..  fixed {entity_id} -> {state}")
        if state == "fully_defined":
            print(f"  OK  fully defined after fixing {entity_id}: {label}")
            return

    raise RuntimeError(f"{label}: sketch not fully defined (state={state!r})")


async def define_circle(
    adapter: Any, x: float, y: float, radius: float, label: str
) -> str:
    """Add a circle, anchor it with ``fix``, then document its diameter.

    The fix-then-dimension order matters: the dimension lands as driven on the
    already-fixed circle; dimension-then-fix over-defines the sketch.
    """
    circle = await adapter.add_circle(x, y, radius)
    check(f"add_circle {label}", circle)
    check(
        f"fix {label}",
        await adapter.add_sketch_constraint(circle.data, None, "fix"),
    )
    check(
        f"dimension {label} diameter (driven)",
        await adapter.add_sketch_dimension(circle.data, None, "diameter", radius * 2.0),
    )
    return circle.data


async def add_line_chain(
    adapter: Any, points: list[tuple[float, float]], close: bool = True
) -> list[str]:
    """Draw consecutive lines through ``points`` and return their entity IDs."""
    vertices = list(points) + ([points[0]] if close else [])
    ids: list[str] = []
    for (x1, y1), (x2, y2) in zip(vertices, vertices[1:], strict=False):
        result = await adapter.add_line(x1, y1, x2, y2)
        ids.append(check(f"add_line ({x1:g},{y1:g})->({x2:g},{y2:g})", result))
    return ids


def _read_member(obj: Any, name: str) -> Any:
    """Read a COM accessor that pywin32 may expose as a method or property."""
    member = getattr(obj, name, None)
    if not callable(member):
        return member
    try:
        return member()
    except Exception:
        return member


def feature_name_by_type(adapter: Any, type_name: str) -> str:
    """Return the name of the last feature whose GetTypeName2 matches.

    Recovers features whose creator call returns None on success (e.g. the
    raw-COM ``InsertHelix`` stopgap used until Phase 3 lands), by walking the
    feature tree with method flagging.
    """
    from solidworks_mcp.adapters import sw_type_info

    def _flag(obj: Any, iface: str) -> None:
        try:
            sw_type_info.flag_methods(obj, iface)
        except Exception:
            pass

    _flag(adapter.currentModel, "IModelDoc2")
    found = ""
    feat = _read_member(adapter.currentModel, "FirstFeature")
    for _ in range(5000):
        if not feat:
            break
        _flag(feat, "IFeature")
        try:
            if _read_member(feat, "GetTypeName2") == type_name:
                found = str(_read_member(feat, "Name"))
        except Exception:
            pass
        feat = _read_member(feat, "GetNextFeature")
    return found


def set_sketch_direct_db(adapter: Any, enabled: bool) -> None:
    """Toggle ``SketchManager.AddToDB`` around non-axis-parallel geometry.

    With inferencing on (the default), a nearly-horizontal sloped line gets
    snapped to an automatic ``horizontal`` relation — a tapered revolve
    profile silently flattens into a rectangle (caught live on the crank
    pin: the frustum came back as a perfect cylinder; on the channel lever
    a step profile picked up redundant auto-relations and went straight to
    over-defined). ``AddToDB=True`` bypasses inference relations; exactly
    coincident endpoints still merge in the sketch DB (proven live: the
    pin chain closed and defined through fixed neighbours).
    """
    adapter.currentSketchManager.AddToDB = enabled
    print(f"  OK  sketch AddToDB = {enabled}")


def insert_helix(
    adapter: Any, height: float, pitch: float, clockwise: bool = True
) -> str:
    """Create a helix from the OPEN base-circle sketch; return the feature name.

    Raw-COM stopgap (``IModelDoc2::InsertHelix``, height & pitch mode) until
    Phase 3 reference geometry lands. ``height``/``pitch`` are millimetres.
    The helix starts on the +X side of the base circle.
    """
    adapter.currentModel.InsertHelix(
        False, clockwise, False, False, 2, height / 1000.0, pitch / 1000.0, 0.0, 0.0, 0.0
    )
    adapter.currentModel.ClearSelection2(True)
    name = feature_name_by_type(adapter, "Helix")
    if not name:
        raise RuntimeError("InsertHelix did not create a helix feature")
    print(f"  OK  insert_helix -> {name}")
    return name


def extrude_at_offset(
    adapter: Any, depth: float, offset: float, flip: bool = False
) -> str:
    """Boss-extrude the last exited sketch starting at an offset from its plane.

    Raw-COM stopgap (``FeatureExtrusion3`` with ``T0=swStartOffset``) until
    Phase 3 reference geometry lands -- the adapter's ``create_extrusion``
    only starts at the sketch plane. ``depth``/``offset`` are millimetres;
    ``flip=True`` mirrors both the offset and the extrude direction to the
    other side of the sketch plane (legacy SummingLever.cs edge-rib call).
    Returns the new feature name.
    """
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    sketch_name = feature_name_by_type(adapter, "ProfileFeature")
    if not sketch_name:
        raise RuntimeError("extrude_at_offset: no sketch found to consume")
    model = adapter.currentModel
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        sketch_name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"extrude_at_offset: cannot select sketch {sketch_name!r}")
    feature = model.FeatureManager.FeatureExtrusion3(
        True,  # Sd: single direction
        False,  # Flip side to cut
        flip,  # Dir: flip extrude direction
        0,  # T1: swEndCondBlind
        0,  # T2
        depth / 1000.0,  # D1
        0.0,  # D2
        False, False,  # Dchk1/2
        False, False,  # Ddir1/2
        0.0, 0.0,  # Dang1/2
        False, False,  # OffsetReverse1/2
        False, False,  # TranslateSurface1/2
        True,  # Merge
        False,  # UseFeatScope
        True,  # UseAutoSelect
        3,  # T0: swStartOffset
        offset / 1000.0,  # StartOffset
        flip,  # FlipStartOffset
    )
    model.ClearSelection2(True)
    if feature is None:
        raise RuntimeError("extrude_at_offset: FeatureExtrusion3 returned None")
    name = str(_read_member(feature, "Name"))
    print(f"  OK  extrude_at_offset {sketch_name} @ {'-' if flip else '+'}{offset:g} -> {name}")
    return name


async def save_part_and_images(
    adapter: Any, part_name: str, views: Iterable[str] = DEFAULT_VIEWS
) -> dict[str, str]:
    """Save the part to ``cad/out/sldprt`` and PNG views to ``cad/out/png``."""
    OUT_SLDPRT.mkdir(parents=True, exist_ok=True)
    part_path = (OUT_SLDPRT / f"{part_name}.SLDPRT").resolve()
    check(f"save_file -> {part_path}", await adapter.save_file(str(part_path)))

    png_dir = OUT_PNG / part_name
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts = {"part": str(part_path)}
    for view in views:
        img_path = (png_dir / f"{part_name}_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img_path),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img_path)
    return artefacts


async def apply_material(adapter: Any, material: str) -> None:
    """Assign a SolidWorks-database material (saved with the part).

    Materials follow the book: brass for the polished gauge/lever/pen
    hardware, gray cast iron for the castings (base, levers, supports),
    plain carbon steel for shafts/pins/bars, alloy steel for spring wire,
    oak for the stained-wood crank handle (see DIMENSIONS.md per chapter).
    """
    from solidworks_mcp.adapters.base import ApplyMaterialParameters

    check(
        f"apply_material {material}",
        await adapter.apply_material(ApplyMaterialParameters(material=material)),
    )


async def measure_check(
    adapter: Any,
    label: str,
    entities: list[dict[str, Any]],
    key: str,
    expected: float,
    tol: float = 0.01,
) -> None:
    """Measure entities and assert ``key`` equals ``expected`` (mm/mm²/deg).

    ``entities`` are ``MeasureEntityRef`` kwargs, e.g.
    ``{"entity_type": "EDGE", "point": [x, y, z]}`` or
    ``{"entity_type": "PLANE", "name": "Front Plane"}``. Point-based
    selection is view-dependent (screen projection) — use points visible
    in the default view, same caveat as the live regression suite.
    """
    from solidworks_mcp.adapters.base import MeasureEntityRef, MeasureParameters

    # Point selection projects through the screen, so the whole part must be
    # in the viewport — long parts otherwise miss their far faces.
    adapter._zoom_to_fit(adapter.currentModel)

    refs = [MeasureEntityRef(**entity) for entity in entities]
    res = await adapter.measure(MeasureParameters(entities=refs))
    if not res.is_success:
        raise RuntimeError(f"measure {label} failed: {res.error}")
    value = res.data.get(key)
    if value is None:
        raise RuntimeError(f"measure {label}: no {key!r} in {res.data!r}")
    if abs(value - expected) > tol:
        raise RuntimeError(
            f"measure {label}: {key}={value} outside {expected} +/- {tol}"
        )
    print(f"  OK  measure {label}: {key}={value:.4f} (expected {expected:g})")


async def report_mass_properties(adapter: Any) -> None:
    """Print volume/bounding data for the eyeball-vs-DIMENSIONS.md check."""
    res = await adapter.get_mass_properties()
    if res.is_success:
        print(f"  mass properties: {res.data!r}")
        return
    print(f"  WARN get_mass_properties failed: {res.error}")


def run_build(build: Callable[[Any], Awaitable[dict[str, str]]]) -> int:
    """Connect, run ``build(adapter)``, disconnect; return a process exit code."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    async def _run() -> dict[str, str]:
        adapter = PyWin32Adapter({})
        print("Connecting to SolidWorks ...")
        await adapter.connect()
        try:
            return await build(adapter)
        finally:
            try:
                await adapter.disconnect()
                print("Disconnected.")
            except Exception as exc:  # noqa: BLE001
                print(f"  WARN disconnect failed: {exc}")

    try:
        artefacts = asyncio.run(_run())
    except Exception:
        traceback.print_exc()
        return 1
    print("\nArtefacts:")
    for key, value in artefacts.items():
        print(f"  {key}: {value}")
    return 0
