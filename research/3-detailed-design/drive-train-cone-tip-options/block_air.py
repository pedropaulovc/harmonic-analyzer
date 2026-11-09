"""Nominal air from a moved MHA-DT-21 and the tip bushing to the drum bank (G19).

World-Z air from the block's south face (only the part inside G19's tip circle) and from a
bushing on the pivot to G19's back face, over the P1 swing angles the VN-54 air proof sweeps.
Prints the air main proves for VN-54 today for comparison, and whether the moved block still
sits on the swing platform. Run from the repo root of a main checkout:
uv run --frozen python research/.../block_air.py > air.json
"""

import dataclasses
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path("cad/scripts").resolve()))

import cone_line
import cylinder_bank_layout as bank
import dt_cone_gear_shaft_spec as shaft
import dt_cone_swing_platform_geometry as plate
import dt_cone_tip_block_spec as tip
import dt_tip_collar_air as air

IN = 25.4
BLOCK_GAP = 0.300 * IN  # T006 north face to the block's south face
BLOCK_DEPTH = 0.430 * IN
BUSH_D, BUSH_L = 0.225 * IN, 0.160 * IN
DRUM_TIP_R = (122.0 / cone_line.DP_TRAIN) * IN / 2.0
ANGLES = sorted({row["angle_deg"] for row in air.full_sweep_proof(intervals=40)})


def block_air(south_station: float) -> float:
    best = math.inf
    half = tip.BLOCK_X / 2.0
    for angle in ANGLES:
        origin, axis = air.collar_pose_frame(angle)
        lat = (axis[2], 0.0, -axis[0])
        for i in range(41):
            x = -half + 2 * half * i / 40
            for j in range(41):
                y = -tip.ADJUSTER_AXIS_HEIGHT + tip.BLOCK_HEIGHT * j / 40
                p = [origin[k] + south_station * axis[k] + x * lat[k] for k in range(3)]
                p[1] += y
                if (
                    math.hypot(p[0] - cone_line.X_DRUM, p[1] - cone_line.Y_DRIVE)
                    > DRUM_TIP_R
                ):
                    continue
                best = min(best, p[2] - bank.G19_BACK_FACE_Z)
    return best


nose = next(t for t in air.TIERS if t.name == "nose")
offset = shaft.TIP_COLLAR_START_STATION - shaft.T006_NORTH_FACE_STATION
bushing = dataclasses.replace(
    nose,
    name="bushing",
    south_mm=-offset,
    north_mm=BUSH_L - offset,
    radius_mm=BUSH_D / 2,
)
south = shaft.T006_NORTH_FACE_STATION + BLOCK_GAP
local = (south - cone_line.PIVOT_STATION, south + BLOCK_DEPTH - cone_line.PIVOT_STATION)
print(
    json.dumps(
        {
            "block_air_now": block_air(shaft.TIP_BLOCK_SOUTH_FACE_STATION),
            "block_air_at_gap": block_air(south),
            "bushing_air": min(
                air.projection_nominal_mm(bushing, angle_deg=a) for a in ANGLES
            ),
            "collar_nominal_air_by_tier": {
                t.name: min(air.projection_nominal_mm(t, angle_deg=a) for a in ANGLES)
                for t in air.TIERS
            },
            "collar_worst_air_by_tier": air.require_air(),
            "block_local_z_from_pivot": local,
            "plate_west_half_width_at_block": [plate._west_edge_x(z) for z in local],
            "plate_east_half_width_north": plate.HALF_WIDTH_N,
            "block_half_width": tip.BLOCK_X / 2.0,
            "plate_south_z": plate.PLATE_SOUTH_Z,
        },
        indent=1,
    )
)
