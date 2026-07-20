r"""Diagnostic: the ch11 crank close-up cluster in a minimal assembly.

Fast iteration harness for the crank pull-hardware (book ch. 11 --
``ch11_images/page001_img02`` hero shot): crankshaft + dome, crank arm with
its rear hub, T12 chain wheel, tapered pin + brass pull ring, keeper screw +
chain eyelet, and the handle -- each GROUNDED on its exact drive-train /
paper-drive machine transform (no mates: the placement IS the pose), so a
part edit re-renders in ~2 min instead of a full drive-train build.

Gates: the shared interference check -- this is where a pin/cone-hole
misfit or a hub/T12 clash fails loud before touching the real assemblies.

Outputs: renders under cad/out/png/diag-crank-closeup/ and a GLB at
cad/out/gltf/crank-closeup-check.glb for the meshprobe photo comparison.

Run (SolidWorks already open)::

    uv run python cad\scripts\diagnostics\diag_crank_closeup.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _assembly import (  # noqa: E402
    check_no_interference,
    place_component,
)
from _transforms import euler_from_rows  # noqa: E402
from _common import OUT_PNG, check, run_build  # noqa: E402
from crank_arm_spec import (  # noqa: E402
    ARM_C2C,
    HUB_DIA,
    KEEPER_PROUD,
    KEEPER_X,
    PIN_HOLE_Z,
)
from crank_pin_spec import (  # noqa: E402
    NECK_LEN,
    PIN_SEAT_PROUD,
    RING_MEAN_R,
)
from export_models import OUT_GLTF, _save_as  # noqa: E402

X_CRANK = -122.8
Y_CRANK = 142.985
CRANK_ARM_ORIGIN_Z = -167.0
CRANKSHAFT_Z0 = -175.0
# Machine z of the pin axis: DERIVED via the same mapping the real assembly
# uses (arm Ry(180) pose: part +Z -> machine -Z), not a -163 literal -- the
# literal masked the assembly's sign bug (ORIGIN + PIN_HOLE_Z = -171) once.
PIN_STATION_Z = CRANK_ARM_ORIGIN_Z - PIN_HOLE_Z  # -163
T12_Z0 = -156.2  # paper-drive REMOVABLE_Z0

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
# Arm rest pose (drive-train): Ry(180) o Rz(-90) -- local +X (arm length)
# hangs machine -Y, local +Y (pin hole) points machine -X (outboard), local
# +Z (plate thickness) runs machine -Z.
ARM_ROWS = [[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]]
# Ring: hangs in the plane PERPENDICULAR to the pin (encircling the neck),
# its top wire threading the neck cross-hole along machine Z: part Y (ring
# axis) -> machine X, part X -> machine -Y so the C-gap hangs low.
RING_ROWS = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]
# Eyelet: part Y (loop axis) -> machine X (around the screw shank), part Z
# (tail direction, authored -Z) -> machine Y so the tail hangs down.
EYELET_ROWS = [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

# Pin: big-end face PIN_SEAT_PROUD outboard of the hub flank.
PIN_BIG_END_X = X_CRANK - (HUB_DIA / 2.0 + PIN_SEAT_PROUD)  # -137.8
RING_HOLE_X = PIN_BIG_END_X - NECK_LEN / 2.0  # -139.3: mid-neck cross-hole
# Keeper screw on the arm's outboard edge (arm local +Y face at machine -X).
KEEPER_FACE_X = X_CRANK - HUB_DIA / 2.0  # the edge face, -130.8
SCREW_HEAD_X = KEEPER_FACE_X - KEEPER_PROUD  # under-head plane, -132.0
EYELET_LOOP_X = KEEPER_FACE_X - KEEPER_PROUD / 2.0  # loop mid-band, -131.4
KEEPER_Y = Y_CRANK - KEEPER_X  # 129.985 (arm hangs down)
KEEPER_Z = CRANK_ARM_ORIGIN_Z - 4.0  # mid-plate, -171
# Eyelet loop centre: the Ø2 shank sits inside the loop's Ø5 inner opening,
# hanging -- shank outer at (drop + 1.0) vs loop inner 2.5, 0.25 slack.
EYELET_Y = KEEPER_Y - 1.25
RING_DROP = RING_MEAN_R  # ring hangs this far below the neck cross-hole
EYELET_DROP = 1.25  # eyelet hangs this far below the screw shank axis

# The photographed crank angle: the crank spin is a free DOF, and the ch11
# hero shot has the arm swung so the pin points up toward the camera. The
# whole keyed cluster (arm, handle, pin, screw) rotates about the shaft
# axis; the gravity-hung ring and eyelet keep their hanging orientation and
# only their anchor points rotate.
CRANK_POSE_DEG = 0.0  # true rest pose (pin head outboard machine-west), as
# drive-train ships it -- the ch11 photo views the crank from ITS LEFT (the
# machine-west side), so the camera goes west, not the crank east (the old
# 180 pose faked the composition mirrored; Pedro caught it 2026-07-20)


def _crank_rot(pos: list[float], rows: list[list[float]]):
    """Rotate a machine-frame pose about the crankshaft axis by CRANK_POSE_DEG."""
    c = math.cos(math.radians(CRANK_POSE_DEG))
    s = math.sin(math.radians(CRANK_POSE_DEG))
    dx, dy = pos[0] - X_CRANK, pos[1] - Y_CRANK
    rpos = [X_CRANK + dx * c - dy * s, Y_CRANK + dx * s + dy * c, pos[2]]
    rrows = [[v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2]] for v in rows]
    return rpos, rrows


def _rot_point(p: list[float]) -> list[float]:
    c = math.cos(math.radians(CRANK_POSE_DEG))
    s = math.sin(math.radians(CRANK_POSE_DEG))
    dx, dy = p[0] - X_CRANK, p[1] - Y_CRANK
    return [X_CRANK + dx * c - dy * s, Y_CRANK + dx * s + dy * c, p[2]]


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())

    # Keyed cluster: rotated to the photographed crank angle.
    arm_pos, arm_rows = _crank_rot(
        [X_CRANK, Y_CRANK, CRANK_ARM_ORIGIN_Z], ARM_ROWS
    )
    handle_pos, handle_rows = _crank_rot(
        [X_CRANK, Y_CRANK - ARM_C2C, CRANKSHAFT_Z0], ROT_Y_POS90
    )
    pin_pos, pin_rows = _crank_rot(
        [PIN_BIG_END_X, Y_CRANK, PIN_STATION_Z], IDENTITY
    )
    screw_pos, screw_rows = _crank_rot(
        [SCREW_HEAD_X, KEEPER_Y, KEEPER_Z], ROT_Y_POS90
    )
    # Gravity-hung hardware: anchor points rotate with the cluster, hanging
    # orientation stays world-down.
    ring_anchor = _rot_point([RING_HOLE_X, Y_CRANK, PIN_STATION_Z])
    ring_pos = [ring_anchor[0], ring_anchor[1] - RING_DROP, ring_anchor[2]]
    eyelet_anchor = _rot_point([EYELET_LOOP_X, KEEPER_Y, KEEPER_Z])
    eyelet_pos = [eyelet_anchor[0], eyelet_anchor[1] - EYELET_DROP, eyelet_anchor[2]]

    placements = [
        ("crankshaft", [X_CRANK, Y_CRANK, CRANKSHAFT_Z0], ROT_X_POS90, ""),
        ("crank-arm", arm_pos, arm_rows, ""),
        ("crank-handle", handle_pos, handle_rows, ""),
        ("transgear-removable", [X_CRANK, Y_CRANK, T12_Z0], IDENTITY, "T12"),
        ("crank-pin", pin_pos, pin_rows, ""),
        ("crank-pin-ring", ring_pos, RING_ROWS, ""),
        ("fillister-screw", screw_pos, screw_rows, ""),
        ("crank-chain-eyelet", eyelet_pos, EYELET_ROWS, ""),
    ]
    for part, pos, rows, config in placements:
        await place_component(
            adapter, part, pos, euler_from_rows(rows), rows,
            ground=True, configuration=config, label=f"diag {part}",
        )

    # The one gate that matters here: the pin cone in its reamed holes, the
    # ring in the neck cross-hole, the hub against the T12 -- any misfit
    # fails loud before the real assemblies are touched.
    check_no_interference(adapter)

    doc = adapter.currentModel
    OUT_GLTF.mkdir(parents=True, exist_ok=True)
    glb = (OUT_GLTF / "crank-closeup-check.glb").resolve()
    _save_as(doc, glb)

    png_dir = OUT_PNG / "diag-crank-closeup"
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {"glb": str(glb)}
    for view in ("front", "isometric"):
        img = (png_dir / f"diag-crank-closeup_{view}.png").resolve()
        check(
            f"export_image {view}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1800,
                    "height": 1200,
                    "view_orientation": view,
                }
            ),
        )
        artefacts[view] = str(img)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
