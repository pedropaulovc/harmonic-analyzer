r"""MSC 40923906 -- 1/4-20 x 4 in zinc-plated steel slotted fillister screw.

Value Collection, MSC Industrial Supply: SAE J82 steel, zinc, ASME B18.6.3.
The user supplied the exact MSC 40923906 engineering drawing on 2026-10-19;
``_msc_40923906`` records its inch limits and partial-thread dimension.
The canonical per-SKU recipe uses the drawing's 1.500 in distal factory
thread and representative source-band midpoints: 0.1625 in straight skirt,
0.0695 in slot width, and 0.098 in slot depth. It retains the existing
in-band maximum head diameter (0.414 in), head height (0.237 in), and
under-head stock length (4.000 in).

The source does not specify crown curvature, fillet radii, or a vendor
solid. The smooth crown, retained P/10 under-head junction fillet and helical
thread form remain representative, not a measured replica or complete ASME proof.
MHA-VN-031 consumes this same canonical stock geometry before its existing
matched-hole cut and deburr; the cut-to-fit acceptance is unchanged.

There is no vendor-model replica gate: the standalone run builds the
source-based representative recipe, checks its mass properties are sane,
and saves it under cad/out/reference for inspection.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_40923906.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _check import check  # noqa: E402
from _com import _early_bound  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _msc_40923906 import (  # noqa: E402
    FILLISTER_SIZE,
    MODEL_DOME_RADIUS_MM,
    MODEL_JUNCTION_FILLET_MM,
    MODEL_PLAIN_SHANK_MM,
    MODEL_SLOT_DEPTH_MM,
    MODEL_SLOT_WIDTH_MM,
    MODEL_STRAIGHT_SKIRT_MM,
    MODEL_THREAD_LENGTH_MM,
)
from _part_checks import volume_check  # noqa: E402
from _rebuild import force_rebuild  # noqa: E402
from _sketch import add_line_chain  # noqa: E402
from _stock_recipe import stock_recipe  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    combine_union,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    split_at_plane,
    thread_sweep_cut,
)
from vn_post_mount_screw_spec import (  # noqa: E402
    FACTORY_TIP_CHAMFER_MM,
    MODEL_REVOLVED_VOLUME_MM3,
    MODEL_SLOT_REMOVED_MM3,
    MODEL_STOCK_VOLUME_MM3,
    MODEL_THREAD_REMOVED_MM3,
)

THREAD_START_PLANE = "FactoryThreadStart"
THREAD_SPLIT = "FactoryThreadSplit"
BODY_UNION = "BodyUnion"


async def _revolved_stock(adapter) -> None:
    from solidworks_mcp.adapters.base import RevolveParameters

    diameter, length, height, head_diameter, _pitch = FILLISTER_SIZE
    radius, head_radius = diameter / 2.0, head_diameter / 2.0
    cap_center_y = height - MODEL_DOME_RADIUS_MM
    mid_angle = (
        math.pi / 2.0
        + math.atan2(MODEL_STRAIGHT_SKIRT_MM - cap_center_y, head_radius)
    ) / 2.0
    check("create source-corrected stock profile", await adapter.create_sketch("Front"))
    manager = adapter.currentSketchManager
    # Reuse the native fillister three-point-arc pattern with inference off;
    # its curvature is a representative convention, not a source dimension.
    with no_sketch_inference(adapter):
        if manager.CreateCenterLine(
            0.0, height / 1000.0, 0.0, 0.0, -length / 1000.0, 0.0
        ) is None:
            raise RuntimeError("MSC source stock: cannot create revolve axis")
        arc = manager.Create3PointArc(
            0.0, height / 1000.0, 0.0,
            head_radius / 1000.0, MODEL_STRAIGHT_SKIRT_MM / 1000.0, 0.0,
            MODEL_DOME_RADIUS_MM * math.cos(mid_angle) / 1000.0,
            (cap_center_y + MODEL_DOME_RADIUS_MM * math.sin(mid_angle)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError("MSC source stock: cannot create representative crown")
        await add_line_chain(adapter, [
            (head_radius, MODEL_STRAIGHT_SKIRT_MM), (head_radius, 0.0),
            (radius, 0.0), (radius, -(length - FACTORY_TIP_CHAMFER_MM)),
            (radius - FACTORY_TIP_CHAMFER_MM, -length), (0.0, -length),
            (0.0, height),
        ], close=False)
    check("close source-corrected stock profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve source-corrected stock", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)
    ))
    name_last_feature(adapter, "Body")
    await volume_check(
        adapter, "MSC source stock revolve", MODEL_REVOLVED_VOLUME_MM3,
        0.005 * MODEL_REVOLVED_VOLUME_MM3,
    )


async def _driver_slot(adapter) -> None:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    height, head_diameter = FILLISTER_SIZE[2:4]
    half = MODEL_SLOT_WIDTH_MM / 2.0
    check("create midband driver slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-half, height + 0.5), (half, height + 0.5),
            (half, height - MODEL_SLOT_DEPTH_MM), (-half, height - MODEL_SLOT_DEPTH_MM),
        ])
    check("close midband driver slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut midband driver slot", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=2.0 * head_diameter, both_directions=True)
    ))
    name_last_feature(adapter, "DriverSlot")
    await volume_check(
        adapter, "MSC midband slot", MODEL_REVOLVED_VOLUME_MM3 - MODEL_SLOT_REMOVED_MM3,
        0.005 * MODEL_SLOT_REMOVED_MM3,
    )


async def _partial_thread(adapter) -> None:
    diameter, _length, _height, _head_diameter, pitch = FILLISTER_SIZE
    radius = diameter / 2.0
    root = radius - 0.75 * pitch * math.sqrt(3.0) / 2.0
    boundary = -MODEL_PLAIN_SHANK_MM
    offset_plane(adapter, THREAD_START_PLANE, boundary)
    pieces = split_at_plane(adapter, THREAD_START_PLANE, THREAD_SPLIT)
    # The approximate boxes discriminate the two widely separated pieces only;
    # exact thread length comes from the source plane and body-scoped cut.
    distal = [piece for piece in pieces if piece["box_mm"] and piece["box_mm"][1] < boundary - 1.0]
    if len(pieces) != 2 or len(distal) != 1:
        raise RuntimeError("MSC partial thread: split did not isolate the factory threaded region")
    check("create partial-thread helix seed", await adapter.create_sketch(THREAD_START_PLANE))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, radius / 1000.0
        ) is None:
            raise RuntimeError("MSC partial thread: cannot create helix seed")
    # Translate the original phase by exactly 50 pitches. One overrun turn
    # clears the factory tip; body scoping prevents any groove in plain stock.
    insert_helix(
        adapter, pitch, MODEL_THREAD_LENGTH_MM / pitch + 1.0,
        clockwise=True, reversed_dir=True, start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )
    check("create partial-thread cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (root + 7.0 * pitch / 16.0 * math.sqrt(3.0), boundary + 15.0 * pitch / 16.0),
            (root + 13.0 * pitch / 32.0 * math.sqrt(3.0), boundary - pitch / 32.0),
            (root, boundary + 3.0 * pitch / 8.0),
            (root, boundary + pitch / 2.0),
        ])
    check("close partial-thread cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", distal[0]["name"], "ThreadGroove")
    combine_union(adapter, BODY_UNION)
    await force_rebuild(adapter)
    part = _early_bound(adapter.currentModel, "IPartDoc")
    if len(tuple(part.GetBodies2(0, False) or ())) != 1:
        raise RuntimeError("MSC partial thread: union did not restore one solid")


PART_NO = "40923906"


@stock_recipe("40923906", threaded=True)
async def build_40923906(adapter, truth=None):
    """Author original source-corrected stock; production owns its fitted cut."""
    await _revolved_stock(adapter)
    await _driver_slot(adapter)
    await _partial_thread(adapter)
    # Preserve the old fillister author's exact inner-edge scope. Partial
    # threading removes the head-end runout, not this under-head shoulder round.
    check("junction fillet", await adapter.add_fillet(
        MODEL_JUNCTION_FILLET_MM, [[FILLISTER_SIZE[0] / 2.0, 0.0, 0.0]],
    ))
    name_last_feature(adapter, "JunctionFillet")
    await volume_check(
        adapter, "MSC partial-thread stock", MODEL_STOCK_VOLUME_MM3,
        0.005 * MODEL_THREAD_REMOVED_MM3,
    )


async def build_catalog(adapter) -> dict[str, str]:
    """Save source-based representative stock, without a supplied vendor solid."""
    import _telemetry
    if __package__:
        from . import _script_paths  # noqa: F401
    else:
        import _script_paths  # noqa: F401
    from _check import check
    from diagnostics.diag_mcmaster_lib import (
        OUT_DIR,
        assert_seat_sketch_baseline,
        close_all,
        export_views,
        mass_properties,
    )

    with _telemetry.span("catalog.build", label=PART_NO):
        check(f"create_part {PART_NO}", await adapter.create_part())
        assert_seat_sketch_baseline(adapter, PART_NO)
        await build_40923906(adapter)
        props = mass_properties(adapter)
        if not props["volume_mm3"] > 0.0:
            raise RuntimeError(f"{PART_NO} catalog build has no solid volume")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUT_DIR / f"{PART_NO}-catalog.SLDPRT"
        check(f"save -> {path}", await adapter.save_file(str(path.resolve())))
        artefacts = {"sldprt": str(path)}
        artefacts.update(await export_views(adapter, f"{PART_NO}-catalog"))
        _telemetry.success(
            f"{PART_NO} catalog build saved: volume {props['volume_mm3']:.4f} mm^3"
        )
        await close_all(adapter)
    return artefacts


if __name__ == "__main__":
    from _session import run_build

    sys.exit(run_build(build_catalog))
