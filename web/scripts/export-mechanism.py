#!/usr/bin/env python3
"""Write web/src/mechanics-data.ts from the working-tree CAD's pure geometry modules.

Run from the repository root:
  uv run --frozen python web/scripts/export-mechanism.py [--glb path/to/raw.glb]

Only pure spec/geometry/config modules under cad/scripts are imported; COM
recipes (build_*/draw_*) never are. With --glb, rest datums are compared with
the model's node world transforms and the residuals printed (report only).
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _config as config  # noqa: E402
import _rocker_interface as arm  # noqa: E402
import ch_amplitude_bar_spec as bar  # noqa: E402
import ch_channel_lever_spec as lever  # noqa: E402
import ch_connecting_rod_spec as rod  # noqa: E402
import ch_vn_channel_spring_installed_spec as spring_part  # noqa: E402
import ch_vn_channel_spring_stock_geom as stock  # noqa: E402
import channel_frame_geom as frame  # noqa: E402
import channel_kinematics as ck  # noqa: E402
import cone_line  # noqa: E402
import dt_cone_swing_platform_geometry as platform  # noqa: E402
import dt_cylinder_gear_spec as cyl  # noqa: E402
import dt_pinion_cam_geometry as cam  # noqa: E402
import dt_pinion_cam_pin_geometry as cam_pin  # noqa: E402
import dt_swing_stop_screw_spec as stop_screw  # noqa: E402
import dt_vn_cone_lock_knob_spec as lock_knob  # noqa: E402
import magnifying_bracket_joint_layout as mg_bracket  # noqa: E402
import mg_magnifying_clamp_geom as mg_clamp  # noqa: E402
import mg_magnifying_lever_geom as mg_lever  # noqa: E402
import mg_magnifying_vertical_rod_geom as vrod_geom  # noqa: E402
import mg_output_fixture_geom as fixture_geom  # noqa: E402
import mg_wheel_bar_geom as wheel_bar  # noqa: E402
import paper_drive_geom as paper  # noqa: E402
import pd_transgear_removable_spec as removable  # noqa: E402
import pinion_rig_layout as rig  # noqa: E402
import pinion_rig_park_geometry as park  # noqa: E402
import pn_pen_carriage_geom as pen  # noqa: E402
import rocker_bank_layout  # noqa: E402
import settled_spring_seats as settled  # noqa: E402
import sh_vn_music_wire_lever_geom as lever_wire  # noqa: E402
import sh_vn_music_wire_pen_geom as pen_wire  # noqa: E402
import sm_gooseneck_geom as goose  # noqa: E402
import sm_summing_lever_spec as summing_lever  # noqa: E402
import sm_vn_counter_spring_stock_geom as counter  # noqa: E402
import sm_vn_gooseneck_shoulder_screw_spec as counter_screw  # noqa: E402
import spring_mount_geom as mount  # noqa: E402
from _cone_axis_constants import SUMMING_Z  # noqa: E402

OUTPUT = ROOT / "web/src/mechanics-data.ts"
# The 15:150 knob-shaft/disc reducer is an external spur mesh, which reverses
# rotation (the -1 build_kinematic_probe.GEAR_SENSE pins on the live model).
EXTERNAL_MESH_SENSE = -1.0
GEARINGS = (
    ("small-large", "T24", "T12"),
    ("medium-medium", "T18", "T18"),
    ("large-small", "T12", "T24"),
)


def chain_paths() -> dict:
    """_chain solves its loop at import for the mounted pair; re-run it per pair."""
    import _chain

    mounted = removable.KNOB_TEETH, removable.CRANK_TEETH
    paths = {}
    try:
        for gearing, knob_config, crank_config in GEARINGS:
            removable.KNOB_TEETH = removable.configuration_teeth(knob_config)
            removable.CRANK_TEETH = removable.configuration_teeth(crank_config)
            c = importlib.reload(_chain)
            paths[gearing] = {
                "arcsMm": [
                    [0.0, 0.0, c.WRAP_R_A, c._ANG_N, c.SPAN_A],
                    [c.CX, c.CY, c.SLACK_R, c._ANG_GA, c.SPAN_SLACK],
                    [c.BX, c.BY, c.WRAP_R_B, c._ANG_GB, c.SPAN_B],
                ],
                "tautMm": [
                    c.BX + c.WRAP_R_B * c.TNX,
                    c.BY + c.WRAP_R_B * c.TNY,
                    c.WRAP_R_A * c.TNX,
                    c.WRAP_R_A * c.TNY,
                ],
                "tautLengthMm": c.TAUT_LEN,
                "sagMm": c.SAG,
                "crankPitchRadiusMm": c.WRAP_R_B,
            }
    finally:
        removable.KNOB_TEETH, removable.CRANK_TEETH = mounted
        c = importlib.reload(_chain)
    return {
        "linkCount": c.LINK_COUNT,
        "pitchMm": c.LINK_PITCH,
        "centrelineLengthMm": c.CENTRELINE_LEN,
        "knobCentrePreMirrorMm": list(c.KNOB_CENTRE),
        "paths": paths,
    }


def pinion_setup() -> dict:
    """Cone swing hardware and the pinion rig's eccentric/follower engagement contact."""
    swing = park.ENGAGED_SWING_RAD
    c, s = math.cos(swing), math.sin(swing)
    dx, dy = park.FPIN_C[0] - park.PIVOT_X, park.FPIN_C[1] - park.PIVOT_Y
    follower = (park.PIVOT_X + dx * c - dy * s, park.PIVOT_Y + dx * s + dy * c)
    normal = (
        park.SPR_N[0] * c - park.SPR_N[1] * s,
        park.SPR_N[0] * s + park.SPR_N[1] * c,
    )
    radii = (cam.CAM_OD + cam_pin.PIN_DIA) / 2
    lo, hi = -math.pi, 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        gx = park.LIFT_X + cam.ECC * math.sin(mid) - follower[0]
        gy = park.LIFT_Y - cam.ECC * math.cos(mid) - follower[1]
        if abs(gx * normal[1] - gy * normal[0]) - radii > 0:
            hi = mid
        else:
            lo = mid
    cone_pivot = list(cone_line.cone_station(platform.PIVOT_STATION))
    cone_pivot[1] = cone_line.Y_BASE_TOP
    hardware = platform.swing_hardware_geometry(
        (cone_pivot[0], cone_pivot[2]),
        lock_head_dia=lock_knob.HEAD_DIA,
        stop_contact_dia=stop_screw.CONTACT_DIA,
    )
    return {
        "conePivotMm": cone_pivot,
        "coneDisengageRad": math.radians(hardware.disengage_deg),
        "pinionPivotMm": [park.PIVOT_X, park.PIVOT_Y, rig.TORQUE_SHAFT_Z0],
        "pinionParkedMm": [park.APINION_X, park.APINION_Y, rig.DRUM_FRONT_Z],
        "pinionLiftMm": [park.LIFT_X, park.LIFT_Y, rig.LIFT_ROD_Z0],
        "pinionEccentricityMm": cam.ECC,
        "pinionContactRadiiMm": radii,
        "followerCentreMm": list(park.FPIN_C),
        "followerNormal": list(park.SPR_N),
        "pinionEngageSwingRad": swing,
        "pinionEngageCamRad": (lo + hi) / 2,
        # build_dt_drive_train_assembly.LEVER_TILT_DEG (COM recipe): parked lever 10 deg from vertical.
        "pinionParkedLeverRad": math.radians(10.0),
    }


def build() -> tuple[dict, list]:
    count = config.machine("channels", "count")
    amplitudes = config.amplitudes()
    z0 = config.machine("channels", "station_z0_mm")
    pitch = config.machine("channels", "station_pitch_mm")
    mid_dz = rocker_bank_layout.ARM_MID_DZ
    native_counter, native_goose_y = settled.counter_seat()
    lever_rod_y, lever_rod_z = (
        mg_bracket.BRACKET_ORIGIN[1],
        mg_bracket.BRACKET_ORIGIN[2],
    )
    clamp_x = lever_wire.CLAMP_X
    fixture_y = fixture_geom.FIXTURE_AXIS_Y
    vrod_top_y = lever_rod_y - mg_clamp.LEVER_BORE_Y + vrod_geom.SHOULDER_X
    wheel = [lever_wire.WHEEL_X, wheel_bar.WHEEL_BAR_Y, lever_wire.WHEEL_MID_Z]
    knife = [mount.KNIFE[0], mount.KNIFE_CONTACT_Y, SUMMING_Z]
    setup = pinion_setup()
    data = {
        "harmonicNumbers": [row["harmonic_n"] for row in config.channels()],
        "channel": {
            "pivotMm": list(frame.ROCKER_PIVOT_XY),
            "fulcrumMm": list(frame.LEVER_FULCRUM_XY),
            "camShaftMm": list(frame.CAM_SHAFT_XY),
            "camHomeRad": math.radians(frame.CAM_HOME_PHASE_DEG),
            "eccentricityMm": cyl.ECCENTRICITY,
            "rodLengthMm": rod.CENTER_DISTANCE,
            "rodPinMm": [-arm.ROD_HOLE_X, arm.ROD_HOLE_Y - arm.PIVOT_MID_Y],
            "arcRadiusMm": arm.CURVE_RADIUS,
            "arcCentreYMm": arm.CENTER_Y - arm.PIVOT_MID_Y,
            "barLengthMm": bar.TOP_PIN_Y,
            "barWidthMm": bar.BAR_WIDTH,
            "contactOffsetMm": [
                bar.BAR_WIDTH / 2.0,
                bar.BOTTOM_NOTCH_HEIGHT
                - config.fit("cam_follower_contact", "contact_gap_mm"),
            ],
            "leverBarArmMm": lever.BAR_PIN_X,
            "leverSpringArmMm": lever.LEVER_SPRING_X,
            "maximumStationMm": config.machine("amplitude", "max_travel_mm"),
            "stationZ0Mm": z0,
            "stationPitchMm": pitch,
            "midplaneOffsetMm": mid_dz,
            "rodDepthOffsetMm": -(cyl.FACE_WIDTH + cyl.CAM_THICKNESS) / 2.0,
        },
        "spring": {
            "anchorMm": list(mount.CHANNEL_ANCHOR_XY),
            "lowerSeatOffsetMm": mount._CHANNEL_LOWER_OFFSET,
            "upperSeatDropMm": mount._CHANNEL_UPPER_DROP,
            "insideDiameterMm": stock.COIL_ID_MM,
            "coilOutsideDiameterMm": stock.COIL_OD_MM,
            "wireDiameterMm": stock.WIRE_DIA_MM,
            "coilTurns": stock.COIL_TURNS,
            "freeLengthMm": stock.FREE_LENGTH_MM,
            "maximumLengthMm": stock.MAX_LENGTH_MM,
            "rateNPerMm": mount.CHANNEL_RATE_N_PER_MM,
            "initialTensionN": mount.CHANNEL_INITIAL_TENSION_N,
            "maximumForceN": spring_part.MAXIMUM_LOAD_N,
        },
        "counter": {
            "anchorMm": list(mount.COUNTER_ANCHOR_XY),
            "upperEyeXMm": mount.COUNTER_UPPER_EYE_X,
            "lowerSeatOffsetMm": mount._COUNTER_LOWER_OFFSET,
            "insideDiameterMm": counter.EYE_ID_MM,
            "freeLengthMm": counter.FREE_LENGTH_MM,
            "maximumLengthMm": counter.MAX_LENGTH_MM,
            "rateNPerMm": mount.COUNTER_RATE_N_PER_MM,
            "initialTensionN": mount.COUNTER_INITIAL_TENSION_N,
            "maximumForceN": mount.COUNTER_MAXIMUM_LOAD_N,
            "loopMeanRadiusMm": counter.COIL_MEAN_RADIUS_MM,
            "wireRadiusMm": counter.WIRE_RADIUS_MM,
            "loopTurns": counter.LOOP_TURNS,
            "loopRiseMm": counter.LOOP_RISE_MM,
            "loopHalfRiseMm": counter.LOOP_HALF_RISE_MM,
            "screwRadiusMm": counter_screw.SHOULDER_DIA / 2.0,
            "coilOutsideDiameterMm": counter.COIL_OD_MM,
            "wireDiameterMm": counter.WIRE_DIA_MM,
            "coilTurns": counter.COIL_TURNS,
            "gooseneckArmYMm": goose.ARM_Y,
            "referenceGooseneckYMm": mount.GOOSENECK_ORIGIN_Y,
            "nativeReference": {"length_mm": native_counter.pose.length_mm},
            "nativeGooseneckYMm": native_goose_y,
        },
        "summing": {"knifeMm": knife, "anchorArmMm": summing_lever.HOLE_X},
        "magnifier": {
            "clampRadiusBandMm": list(mg_lever.clamp_radius_band(mg_clamp.BLOCK_DEPTH)),
            "clampRestMm": [clamp_x, lever_rod_y, lever_rod_z],
            "fixtureRestMm": [clamp_x, fixture_y, fixture_geom.VROD_Z],
            "fixtureOffsetRangeM": [  # whole cross bore on the straight rod, below the clamp
                (
                    vrod_top_y
                    - vrod_geom.ROD_LENGTH
                    + vrod_geom.DOME_R
                    + fixture_geom.HEX_CORNER_RADIUS
                    - fixture_y
                )
                / 1000,
                (
                    lever_rod_y
                    - mg_clamp.LEVER_BORE_Y
                    - fixture_geom.HEX_CORNER_RADIUS
                    - fixture_y
                )
                / 1000,
            ],
            "hubPitchRadiusMm": lever_wire.YOKE_PITCH_R,
            "rimPitchRadiusMm": pen_wire.RIM_WIRE_R,
            "visualClearanceMm": lever_wire.CLEARANCE,
            "hookMm": list(lever_wire.WIRE_START),
            "hubTangentMm": list(lever_wire.WIRE_END),
            "wheelCentreMm": wheel,
            "penWireBottomMm": list(pen_wire.WIRE_BOTTOM),
            "penRestMm": list(pen.MARKER_POS),
        },
        "setup": setup,
        "paperDrive": {
            "chainRatioFine": paper.CHAIN_RATIO,
            "reducerRatio": paper.GEAR_RATIO,
            "externalMeshSense": EXTERNAL_MESH_SENSE,
            "chain": chain_paths(),
        },
        "restChannels": [],
    }
    ch, dt = "ch-channel/", "dt-drive-train/"
    checks = []  # (node path suffix, local point mm, expected world mm)
    for index in range(count):
        n, station = index + 1, z0 + pitch * index
        mid = station + mid_dz
        state = ck.solve_state(amplitudes[index])
        spring = settled.channel_seat(amplitudes[index]).pose
        data["restChannels"].append({"nativeSpring": {"length_mm": spring.length_mm}})
        checks += [
            (
                f"{ch}ch-rocker-arm-{n}",
                [0, arm.PIVOT_MID_Y, 0],
                [*frame.ROCKER_PIVOT_XY, mid],
            ),
            (f"{ch}ch-channel-lever-{n}", [0, 0, 0], [*frame.LEVER_FULCRUM_XY, mid]),
            (
                f"{ch}ch-amplitude-bar-{n}",
                [0, 0, 0],
                [
                    state["bar_origin_x"],
                    state["bar_origin_y"],
                    mid - bar.BAR_WIDTH / 2.0,
                ],
            ),
            (
                f"{ch}ch-connecting-rod-{n}",
                [0, 0, 0],
                [
                    *ck._RING_CENTER,
                    station - (cyl.FACE_WIDTH + cyl.CAM_THICKNESS) / 2.0,
                ],
            ),
            (
                f"{ch}ch-vn-channel-spring-installed-*-{n}",
                [0, 0, 0],
                [*spring.centre_xy, mid],
            ),
            (
                f"{dt}dt-cylinder-gear-{n}",
                [0, 0, 0],
                [*frame.CAM_SHAFT_XY, station + cyl.FACE_WIDTH / 2.0],
            ),
        ]
    checks += [
        ("sm-summing/sm-summing-lever-1", [0, 0, 0], [*mount.KNIFE, SUMMING_Z]),
        (
            "sm-summing/sm-vn-counter-spring-1",
            [0, 0, 0],
            [*native_counter.pose.centre_xy, SUMMING_Z],
        ),
        (
            "sm-summing/sm-gooseneck-1",
            [0, 0, 0],
            [mount.COLUMN_X, native_goose_y, SUMMING_Z],
        ),
        (
            "mg-magnifier/mg-magnifying-lever-1",
            [mg_lever.KNIFE_LOCAL_X, mg_lever.KNIFE_LOCAL_Y, 0],
            [knife[0], knife[1], lever_rod_z],
        ),
        ("mg-magnifier/mg-magnifying-wheel-1", [0, 0, 0], wheel),
        ("pn-pen/pn-vn-pen-marker-1", [0, 0, 0], list(pen.MARKER_POS)),
        (f"{dt}dt-cone-swing-platform-1", [0, 0, 0], setup["conePivotMm"]),
        (f"{dt}dt-pinion-pivot-shaft-1", [0, 0, 0], setup["pinionPivotMm"]),
        (f"{dt}dt-pinion-lift-rod-1", [0, 0, 0], setup["pinionLiftMm"]),
        (f"{dt}dt-alignment-pinion-1", [0, 0, 0], setup["pinionParkedMm"]),
    ]
    return data, checks


def glb_world_matrices(path: Path) -> dict[str, list[float]]:
    """Column-major world matrices (metres) by slash-joined node-name path."""
    with path.open("rb") as stream:
        stream.read(12)
        length, _ = struct.unpack("<II", stream.read(8))
        gltf = json.loads(stream.read(length))
    nodes, result = gltf["nodes"], {}

    def local(node: dict) -> list[float]:
        if "matrix" in node:
            return node["matrix"]
        x, y, z, w = node.get("rotation", [0, 0, 0, 1])
        sx, sy, sz = node.get("scale", [1, 1, 1])
        return [
            (1 - 2 * (y * y + z * z)) * sx,
            2 * (x * y + z * w) * sx,
            2 * (x * z - y * w) * sx,
            0,
            2 * (x * y - z * w) * sy,
            (1 - 2 * (x * x + z * z)) * sy,
            2 * (y * z + x * w) * sy,
            0,
            2 * (x * z + y * w) * sz,
            2 * (y * z - x * w) * sz,
            (1 - 2 * (x * x + y * y)) * sz,
            0,
            *node.get("translation", [0, 0, 0]),
            1,
        ]

    def visit(index: int, parent: list[float], prefix: str) -> None:
        node, m = nodes[index], local(nodes[index])
        world = [
            sum(parent[k * 4 + r] * m[c * 4 + k] for k in range(4))
            for c in range(4)
            for r in range(4)
        ]
        name = (
            f"{prefix}/{node.get('name', index)}"
            if prefix
            else node.get("name", str(index))
        )
        result[name] = world
        for child in node.get("children", []):
            visit(child, world, name)

    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(root, [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0], "")
    return result


def report_rest_residuals(glb: Path, checks: list) -> None:
    """Print the worst CAD-vs-model rest residual per datum family (report only)."""
    import fnmatch
    import re

    import _chain  # reloaded on the mounted pair by chain_paths()

    nodes = glb_world_matrices(glb)
    worst: dict[str, tuple[float, int]] = {}
    for suffix, point, expected in checks:
        found = fnmatch.filter(nodes, f"ha-harmonic-analyzer/{suffix}")
        if len(found) != 1:
            print(f"{suffix}: {len(found)} matching nodes")
            continue
        m = nodes[found[0]]
        actual = [
            m[12 + r] * 1000 + sum(m[c * 4 + r] * point[c] for c in range(3))
            for r in range(3)
        ]
        family = re.sub(r"-\d+$", "-N", suffix)
        error, seen = worst.get(family, (0.0, 0))
        worst[family] = (max(error, math.dist(actual, expected)), seen + 1)
    links = [
        m
        for path, m in nodes.items()
        if re.search(r"/(sh-vn-chain-link|pd-vn-chain-connecting-link)-\d+$", path)
    ]
    worst["pd-paper-drive/chain link pin0 to mounted loop"] = (
        max(
            _chain.centreline_distance(
                m[12] * 1000, m[13] * 1000, *_chain.KNOB_CENTRE, mirror_x=True
            )
            for m in links
        ),
        len(links),
    )
    print(f"{'datum family':56} {'nodes':>5} {'max |d| mm':>11}")
    for family, (error, seen) in worst.items():
        print(f"{family:56} {seen:5d} {error:11.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--glb",
        type=Path,
        help="raw GLB whose rest node transforms to compare (report only)",
    )
    args = parser.parse_args()
    data, checks = build()
    text = json.dumps(data, indent=2, allow_nan=False)
    header = "// Generated by web/scripts/export-mechanism.py from cad/; do not edit.\n"
    OUTPUT.write_text(
        f"{header}export const MECHANISM_DATA = {text} as const\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    if args.glb:
        report_rest_residuals(args.glb, checks)


if __name__ == "__main__":
    main()
