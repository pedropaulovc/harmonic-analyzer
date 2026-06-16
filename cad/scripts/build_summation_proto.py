r"""THROWAWAY de-risk rig for the `summation` reorg (task #10).

The F3 80 mm-amplitude rebuild swings the FIXED-length installed channel
springs into the summing-lever plate (10 interferences, regression). The fix
(user-chosen): co-locate both spring ends in one assembly so each spring can be
MATED end-to-end, with its length driven from the measured static gap -- then it
sits exactly on its line of action instead of a stale 63 mm pose poking the
plate.

This rig validates the narrow empirical question BEFORE the 20-channel reorg:

  with length = the measured eye-to-eye gap, what mate combo against a horizontal
  lever-tab pin (top) and the plate hole (bottom) gives EXACTLY 0 DOF with no
  redundant mates?

Scheme under test (`SUMMATION_BOTTOM`, default `spinlock`):

  * TOP   -- the baked top-eye axis CONCENTRIC to a horizontal pin axis (the
             lever tab). A hinge: leaves slide-along-pin (X) + swing-about-pin.
  * SLIDE -- distance(bottom-lead axis -> Right Plane) pins the axial slide (X).
  * SWING -- distance(bottom-lead axis -> Front Plane) pins the hinge swing (Z),
             i.e. the `spin_driver` pattern proven on p0/p1/p2.

The bottom is deliberately NOT a second concentric: a fixed-length spring cannot
keep its lead vertical AND reach a tilted-lever tab, so a bottom concentric
fights the top one (redundant by 2 -- the classic pin-in-two-holes). The two
plane distances pin the same DOFs purely, and generalise to any tilt by changing
their targets (the measured-length write).

Anchors are ASSEMBLY-level named reference axes/planes (grounded, no anchor
parts). The proto spring is a SEPARATE part name (`channel-spring-proto`) so the
real `channel-spring-installed` stays untouched. The assembly is NEVER saved.

  C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_summation_proto.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from _common import (
    FULLY_CONSTRAINED, UNDER_CONSTRAINED, _flag, _read_member, check,
    component_transform, concentric_mate, distance_driver, log, name_bore_axis,
    named_ref, world_point,
)
from build_channel_spring import MEAN_RADIUS, build_spring
from build_channel_spring_installed import (
    BOTTOM_LEAD, INSTALLED_BODY_LENGTH, TOP_LEAD,
)
from build_motion_study import _entity_ref

OVER_CONSTRAINED = 4

PROTO_PART = "channel-spring-proto"

# The measured static gap (eye-to-eye) the summation reorg would write per
# channel. Use the canonical installed numbers as a representative case; body
# length is DERIVED from the gap (the "measured-length write").
EYE_C2C = INSTALLED_BODY_LENGTH + TOP_LEAD + BOTTOM_LEAD  # 74.15
PROTO_BODY = EYE_C2C - TOP_LEAD - BOTTOM_LEAD             # -> 63.05, the write
TOP_EYE_LOCAL_Y = PROTO_BODY + TOP_LEAD                  # 65.05 above part origin

# Rig offset in X so the bottom-lead axis sits at x = X0 (non-zero) -- a zero
# distance to the Right plane is a degenerate axis-in-plane selection.
X0 = 50.0
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]

BOTTOM_MODE = os.environ.get("SUMMATION_BOTTOM", "spinlock")  # spinlock | concentric


def _org(adapter, comp: str) -> list[float]:
    a = component_transform(adapter, comp)
    return [a[9] * 1000.0, a[10] * 1000.0, a[11] * 1000.0]


def _status(adapter, comp: str) -> int:
    component = adapter.currentModel.GetComponentByName(comp)
    _flag(component, "IComponent2")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    return int(adapter._attempt(lambda: component.GetConstrainedStatus(), default=-1))


async def build(adapter) -> None:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    log(f"proto gap (eye c2c) = {EYE_C2C:.2f} -> body {PROTO_BODY:.2f} "
        f"(leads bottom {BOTTOM_LEAD}, top {TOP_LEAD}); bottom mode = {BOTTOM_MODE}")

    # 1. Build the proto spring (baked eye axes) -- separate name, never the real part.
    axes = await build_spring(
        adapter, PROTO_PART, PROTO_BODY, leads=(BOTTOM_LEAD, TOP_LEAD), eye_axes=True)
    bottom_axis = axes["bottom_lead_axis"]
    top_axis = axes["top_eye_axis"]
    log(f"  baked axes: bottom-lead={bottom_axis!r} top-eye={top_axis!r}")

    # 2. Fresh assembly; insert the spring on-solution (Ry90), unfixed.
    check("create_assembly", await adapter.create_assembly())
    from _common import OUT_SLDPRT
    path = (OUT_SLDPRT / f"{PROTO_PART}.SLDPRT").resolve()
    data = check("insert proto spring", await adapter.insert_component(
        InsertComponentParameters(file_path=str(path), position=[X0, 0.0, 0.0],
                                  rotation=[0.0, 90.0, 0.0], configuration="")))
    spring = data["name"]
    placed = _org(adapter, spring)
    log(f"  spring inserted as {spring!r} at {[round(v, 2) for v in placed]}")

    # As-placed eye centres (the targets the summation gap must reproduce).
    top_eye = world_point(adapter, spring, [0.0, TOP_EYE_LOCAL_Y, 0.0])
    bot_eye = world_point(adapter, spring, [0.0, -BOTTOM_LEAD, 0.0])
    log(f"  top eye {[round(v, 2) for v in top_eye]}  "
        f"bottom eye {[round(v, 2) for v in bot_eye]}  "
        f"c2c {((top_eye[1] - bot_eye[1])):.2f}")

    # 3. Grounded assembly anchors. Top pin = horizontal axis along X at the top
    #    eye height; bottom-lead distance targets read from the as-placed axis.
    top_pin = await name_bore_axis(
        adapter, "Top Plane", TOP_EYE_LOCAL_Y, "Front Plane", 0.0, "lever-tab pin")
    z_swing = MEAN_RADIUS  # |z| of the bottom-lead axis (at part-local x = mean_radius)
    x_slide = X0           # |x| of the bottom-lead axis (the rig offset)

    # TOP hinge: top-eye axis concentric on the lever-tab pin.
    await concentric_mate(
        adapter, _entity_ref(spring, top_axis, "AXIS"), named_ref(top_pin, "AXIS"),
        label="top hinge (eye on lever-tab pin)", verify=(spring, placed))

    if BOTTOM_MODE == "concentric":
        # A/B: prove the bottom concentric fights the top hinge (redundant).
        plate_hole = await name_bore_axis(
            adapter, "Right Plane", X0, "Front Plane", MEAN_RADIUS, "plate hole")
        await concentric_mate(
            adapter, _entity_ref(spring, bottom_axis, "AXIS"),
            named_ref(plate_hole, "AXIS"),
            label="bottom thread (lead in plate hole)", verify=(spring, placed))
    else:
        # SWING + SLIDE: two pure plane distances on the bottom-lead axis.
        await distance_driver(
            adapter, _entity_ref(spring, bottom_axis, "AXIS"),
            named_ref("Front Plane", "PLANE"), z_swing,
            label="swing lock (bottom-lead -> Front)", verify=(spring, placed))
        await distance_driver(
            adapter, _entity_ref(spring, bottom_axis, "AXIS"),
            named_ref("Right Plane", "PLANE"), x_slide,
            label="slide lock (bottom-lead -> Right)", verify=(spring, placed))

    # 4. Report DOF + landing.
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    status = _status(adapter, spring)
    names = {FULLY_CONSTRAINED: "FULLY DEFINED (0 DOF)",
             UNDER_CONSTRAINED: "UNDER-DEFINED (free DOF left)",
             OVER_CONSTRAINED: "OVER-DEFINED (redundant mates)"}
    after = _org(adapter, spring)
    drift = max(abs(a - b) for a, b in zip(after, placed, strict=True))
    log(f"  spring constrained status = {status} : {names.get(status, '?')}")
    log(f"  origin drift after mates = {drift:.4f} mm (mates must not move it)")

    if status == FULLY_CONSTRAINED and drift < 0.5:
        log(f"  PASS: hinge + {BOTTOM_MODE} -> 0 DOF, no redundancy, eyes land "
            f"on anchors. The summation bottom-eye mate + measured-length write "
            f"are de-risked.")
        return
    raise RuntimeError(
        f"FAIL: status {status} ({names.get(status, '?')}), drift {drift:.4f} mm "
        f"-- bottom mode {BOTTOM_MODE!r} does not give a clean 0-DOF fit")


async def _main() -> int:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter
    adapter = PyWin32Adapter({})
    print("Connecting ...", flush=True)
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    try:
        await build(adapter)
    finally:
        await adapter.disconnect()
        print("Disconnected (assembly NOT saved).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
