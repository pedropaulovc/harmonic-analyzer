#!/usr/bin/env python3
"""Export pure CAD mechanism data and verify it against the released GLB.

Run from the repository root:
  python web/scripts/export-mechanics.py --model /path/to/harmonic-analyzer.glb
Only web output is written. CAD sources and the model are read-only. The GLB is
not redistributed. Analytic force seats and calibrated native render seats are
kept separate; the latter are never interpolated into an invented force model.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import io
import json
import math
import struct
import subprocess
import sys
import tarfile
import tempfile
import types
from dataclasses import asdict
from pathlib import Path

RELEASE_COMMIT = "1268c23d4a8fc741147c5e09d8d1e45247a71945"
RELEASE_SHA256 = "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"


def glb_nodes(path: Path) -> tuple[dict[str, list[float]], str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        stream.seek(0)
        magic, version, size = struct.unpack("<III", stream.read(12))
        if magic != 0x46546C67 or version != 2 or size != path.stat().st_size:
            raise ValueError("Not a complete GLB 2 file")
        length, kind = struct.unpack("<II", stream.read(8))
        if kind != 0x4E4F534A:
            raise ValueError("The first GLB chunk must be JSON")
        gltf = json.loads(stream.read(length))
    identity = [
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    result: dict[str, list[float]] = {}

    def multiply(a: list[float], b: list[float]) -> list[float]:
        return [
            sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
            for col in range(4)
            for row in range(4)
        ]

    def visit(index: int, parent: list[float], prefix: str) -> None:
        node = gltf["nodes"][index]
        name = node.get("name", f"unnamed-{index}")
        fullpath = f"{prefix}/{name}" if prefix else name
        if "matrix" in node:
            local = node["matrix"]
        else:
            x, y, z, w = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
            sx, sy, sz = node.get("scale", [1.0, 1.0, 1.0])
            tx, ty, tz = node.get("translation", [0.0, 0.0, 0.0])
            local = [
                (1 - 2 * (y * y + z * z)) * sx,
                2 * (x * y + z * w) * sx,
                2 * (x * z - y * w) * sx,
                0.0,
                2 * (x * y - z * w) * sy,
                (1 - 2 * (x * x + z * z)) * sy,
                2 * (y * z + x * w) * sy,
                0.0,
                2 * (x * z + y * w) * sz,
                2 * (y * z - x * w) * sz,
                (1 - 2 * (x * x + y * y)) * sz,
                0.0,
                tx,
                ty,
                tz,
                1.0,
            ]
        world = multiply(parent, local)
        if fullpath in result:
            raise ValueError(f"Duplicate qualified model path: {fullpath}")
        result[fullpath] = world
        for child in node.get("children", []):
            visit(child, world, fullpath)

    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        visit(root, identity, "")
    return result, digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cad-root", type=Path, default=Path(__file__).resolve().parents[2] / "cad"
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src/mechanics-data.ts",
    )
    args = parser.parse_args()
    working_cad = args.cad_root.resolve()
    repo = working_cad.parent
    # Evaluate the exact model revision, not today's potentially different CAD.
    # Only pure scripts/configuration enter the temporary snapshot.
    snapshot = tempfile.TemporaryDirectory(prefix="harmonic-mechanics-source-")
    snapshot_root = Path(snapshot.name)
    archive = subprocess.check_output(
        ["git", "archive", RELEASE_COMMIT, "cad/scripts", "cad/config"], cwd=repo
    )
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(snapshot_root, filter="data")
    cad = snapshot_root / "cad"
    sys.path.insert(0, str(cad / "scripts"))
    # This released data table sits in a COM recipe whose unrelated imports
    # pull telemetry/Windows machinery. Evaluate its exact assignment AST only:
    # genuine supplier data, no substitute geometry and no COM function stubs.
    thumb_path = cad / "scripts/diagnostics/diag_mcmaster_thumb.py"
    thumb_tree = ast.parse(thumb_path.read_text(), filename=str(thumb_path))
    thumb_assignment = next(
        node
        for node in thumb_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "THUMB_SPECS"
            for target in node.targets
        )
    )
    thumb_module = types.ModuleType("diagnostics.diag_mcmaster_thumb")
    thumb_module.__file__ = str(thumb_path)
    # Pinned-commit assignment AST; not literal_eval-able (dict() calls, arithmetic).
    thumb_code = compile(
        ast.Module(body=[thumb_assignment], type_ignores=[]), str(thumb_path), "exec"
    )
    exec(thumb_code, thumb_module.__dict__)  # noqa: S102
    sys.modules[thumb_module.__name__] = thumb_module
    fillister_path = cad / "scripts/diagnostics/diag_mcmaster_fillister.py"
    fillister_tree = ast.parse(fillister_path.read_text(), filename=str(fillister_path))
    fillister_assignment = next(
        node
        for node in fillister_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "FILLISTER_SIZES"
            for target in node.targets
        )
    )
    fillister_module = types.ModuleType("diagnostics.diag_mcmaster_fillister")
    fillister_module.__file__ = str(fillister_path)
    cross_spec = importlib.import_module("frame_cross_screw_spec")
    for name in ("SHANK_DIA", "SHANK_LEN", "HEAD_H", "HEAD_DIA", "PITCH"):
        fillister_module.__dict__[name] = getattr(cross_spec, name)
    # Pinned-commit assignment AST; references the injected cross-screw constants.
    fillister_code = compile(
        ast.Module(body=[fillister_assignment], type_ignores=[]),
        str(fillister_path),
        "exec",
    )
    exec(fillister_code, fillister_module.__dict__)  # noqa: S102
    sys.modules[fillister_module.__name__] = fillister_module
    modules = {
        name: importlib.import_module(name)
        for name in (
            "_config",
            "channel_kinematics",
            "channel_frame_geom",
            "amplitude_bar_spec",
            "rocker_arm_spec",
            "channel_lever_spec",
            "connecting_rod_spec",
            "cylinder_gear_spec",
            "channel_spring_stock_geom",
            "counter_spring_stock_geom",
            "spring_mount_geom",
            "settled_spring_seats",
            "gooseneck_geom",
            "summing_lever_spec",
            "rocker_bank_layout",
            "cone_pivot_post_installation",
            "magnifying_lever_geom",
            "magnifying_clamp_geom",
            "lever_wire_geom",
            "pen_wire_geom",
            "paper_drive_geom",
            "spring_force_model",
            "pinion_rig_park_geometry",
            "pinion_cam_geometry",
            "pinion_cam_pin_geometry",
            "pinion_bracket_geometry",
            "cone_line",
            "cone_swing_platform_geometry",
            "cone_lock_knob_spec",
            "swing_stop_screw_spec",
            "magnifying_vertical_rod_spec",
            "output_fixture_spec",
            "_chain",
        )
    }
    config = modules["_config"]
    ck = modules["channel_kinematics"]
    frame = modules["channel_frame_geom"]
    bar = modules["amplitude_bar_spec"]
    arm = modules["rocker_arm_spec"]
    lever = modules["channel_lever_spec"]
    cyl = modules["cylinder_gear_spec"]
    rod = modules["connecting_rod_spec"]
    stock = modules["channel_spring_stock_geom"]
    counter = modules["counter_spring_stock_geom"]
    mount = modules["spring_mount_geom"]
    settled = modules["settled_spring_seats"]
    goose = modules["gooseneck_geom"]
    mag = modules["magnifying_lever_geom"]
    lw = modules["lever_wire_geom"]
    pw = modules["pen_wire_geom"]
    paper = modules["paper_drive_geom"]
    chain = modules["_chain"]
    installation = modules["cone_pivot_post_installation"]
    nodes, model_hash = glb_nodes(args.model)
    if model_hash != RELEASE_SHA256:
        raise ValueError(f"Model SHA256 {model_hash} is not the pinned v37 release")
    count = config.machine("channels", "count")
    if count != 20:
        raise ValueError("The web solver requires the complete twenty-channel machine")
    amplitudes = config.amplitudes()
    z0 = config.machine("channels", "station_z0_mm")
    pitch = config.machine("channels", "station_pitch_mm")
    mid_dz = modules["rocker_bank_layout"].ARM_MID_DZ
    native_counter, native_goose_y = settled.counter_seat()
    checks: list[dict] = []

    def check(
        path: str,
        local_point: list[float],
        target: list[float],
        tolerance_mm: float = 0.002,
    ) -> None:
        matrix = nodes[path]
        actual = [
            matrix[12 + r] * 1000
            + sum(matrix[c * 4 + r] * local_point[c] for c in range(3))
            for r in range(3)
        ]
        error = math.dist(actual, target)
        checks.append(
            {
                "path": path,
                "localPointMm": local_point,
                "expectedMm": target,
                "actualMm": actual,
                "errorMm": error,
                "toleranceMm": tolerance_mm,
            }
        )
        if error > tolerance_mm:
            raise ValueError(
                f"Source/model rest-frame mismatch at {path}: {error:.6f} mm > {tolerance_mm} mm"
            )

    rest_channels = []
    for index in range(count):
        n = index + 1
        station = z0 + pitch * index
        mid = station + mid_dz
        state = ck.solve_state(amplitudes[index])
        spring = settled.channel_seat(amplitudes[index]).pose
        prefix = "harmonic-analyzer/channel/"
        check(
            prefix + f"rocker-arm-{n}",
            [0.0, arm.PIVOT_MID_Y, 0.0],
            [*frame.ROCKER_PIVOT_XY, mid],
        )
        check(
            prefix + f"channel-lever-{n}",
            [0.0, 0.0, 0.0],
            [*frame.LEVER_FULCRUM_XY, mid],
        )
        check(
            prefix + f"amplitude-bar-{n}",
            [0.0, 0.0, 0.0],
            [state["bar_origin_x"], state["bar_origin_y"], mid - bar.BAR_WIDTH / 2.0],
        )
        check(
            prefix + f"connecting-rod-{n}",
            [0.0, 0.0, 0.0],
            [*ck._RING_CENTER, station - (cyl.FACE_WIDTH + cyl.CAM_THICKNESS) / 2.0],
        )
        spring_name = next(
            path
            for path in nodes
            if path.startswith(prefix + "channel-spring-installed-")
            and path.endswith(f"-{n}")
        )
        check(spring_name, [0.0, 0.0, 0.0], [*spring.centre_xy, mid])
        check(
            f"harmonic-analyzer/drive-train/cylinder-gear-{n}",
            [0.0, 0.0, 0.0],
            [*frame.CAM_SHAFT_XY, station + cyl.FACE_WIDTH / 2.0],
        )
        rest_channels.append(
            {
                "stationM": station / 1000.0,
                "midplaneM": mid / 1000.0,
                "rockerWorldMatrix": nodes[prefix + f"rocker-arm-{n}"],
                "rodWorldMatrix": nodes[prefix + f"connecting-rod-{n}"],
                "barWorldMatrix": nodes[prefix + f"amplitude-bar-{n}"],
                "leverWorldMatrix": nodes[prefix + f"channel-lever-{n}"],
                "springWorldMatrix": nodes[spring_name],
                "nativeSpring": asdict(spring),
            }
        )
    sum_z = installation.SUMMING_Z
    check(
        "harmonic-analyzer/summing/summing-lever-1",
        [0.0, 0.0, 0.0],
        [*mount.KNIFE, sum_z],
    )
    check(
        "harmonic-analyzer/summing/knife-mount-1",
        [0.0, 0.0, 0.0],
        [mount.KNIFE[0], mount.KNIFE_CONTACT_Y, sum_z + 87.0585],
    )
    check(
        "harmonic-analyzer/summing/counter-spring-1",
        [0.0, 0.0, 0.0],
        [*native_counter.pose.centre_xy, sum_z],
    )
    check(
        "harmonic-analyzer/summing/gooseneck-1",
        [0.0, 0.0, 0.0],
        [mount.COLUMN_X, native_goose_y, sum_z],
    )
    check(
        "harmonic-analyzer/magnifier/magnifying-lever-1",
        [mag.KNIFE_LOCAL_X, mag.KNIFE_LOCAL_Y, 0.0],
        [*mount.KNIFE[:1], mount.KNIFE_CONTACT_Y, -128.3],
    )
    check(
        "harmonic-analyzer/magnifier/magnifying-wheel-1",
        [0.0, 0.0, 0.0],
        [lw.WHEEL_X, lw.WHEEL_BAR_Y, lw.WHEEL_MID_Z],
    )
    park = modules["pinion_rig_park_geometry"]
    cam = modules["pinion_cam_geometry"]
    cone_line = modules["cone_line"]
    platform = modules["cone_swing_platform_geometry"]
    cone_pivot = cone_line.cone_station(platform.PIVOT_STATION)
    cone_pivot[1] = cone_line.Y_BASE_TOP
    hardware = platform.swing_hardware_geometry(
        (cone_pivot[0], cone_pivot[2]),
        lock_collar_dia=modules["cone_lock_knob_spec"].COLLAR_DIA,
        stop_shank_dia=modules["swing_stop_screw_spec"].SHANK_DIA,
    )
    pinion_z = nodes["harmonic-analyzer/drive-train/pinion-pivot-shaft-1"][14] * 1000
    lift_z = nodes["harmonic-analyzer/drive-train/pinion-lift-rod-1"][14] * 1000
    drum_z = nodes["harmonic-analyzer/drive-train/alignment-pinion-1"][14] * 1000
    check(
        "harmonic-analyzer/drive-train/cone-swing-platform-1",
        [0.0, 0.0, 0.0],
        cone_pivot,
    )
    check(
        "harmonic-analyzer/drive-train/pinion-pivot-shaft-1",
        [0.0, 0.0, 0.0],
        [park.PIVOT_X, park.PIVOT_Y, pinion_z],
    )
    check(
        "harmonic-analyzer/drive-train/pinion-lift-rod-1",
        [0.0, 0.0, 0.0],
        [park.LIFT_X, park.LIFT_Y, lift_z],
    )
    check(
        "harmonic-analyzer/drive-train/alignment-pinion-1",
        [0.0, 0.0, 0.0],
        [park.APINION_X, park.APINION_Y, drum_z],
    )
    # The engagement triangle and eccentric/follower contact are the actual
    # source equations (build_drive_train_assembly.py:2532-2607), not a sweep RPM.
    pd = math.hypot(
        frame.CAM_SHAFT_XY[0] - park.PIVOT_X, frame.CAM_SHAFT_XY[1] - park.PIVOT_Y
    )
    parked_azimuth = math.atan2(
        park.APINION_Y - park.PIVOT_Y, park.APINION_X - park.PIVOT_X
    )
    strap = modules["pinion_bracket_geometry"].C2C
    c2c = config.machine("alignment_pinion", "engaged_center_distance_mm")
    engaged_azimuth = math.atan2(
        frame.CAM_SHAFT_XY[1] - park.PIVOT_Y, frame.CAM_SHAFT_XY[0] - park.PIVOT_X
    ) - math.acos((strap * strap + pd * pd - c2c * c2c) / (2 * strap * pd))
    engage_swing = engaged_azimuth - parked_azimuth
    c, s = math.cos(engage_swing), math.sin(engage_swing)
    dx, dy = park.FPIN_C[0] - park.PIVOT_X, park.FPIN_C[1] - park.PIVOT_Y
    follower = (park.PIVOT_X + dx * c - dy * s, park.PIVOT_Y + dx * s + dy * c)
    normal = (
        park.SPR_N[0] * c - park.SPR_N[1] * s,
        park.SPR_N[0] * s + park.SPR_N[1] * c,
    )
    radii = (cam.CAM_OD + modules["pinion_cam_pin_geometry"].PIN_DIA) / 2
    lo, hi = -math.pi, 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        dx = park.LIFT_X + cam.ECC * math.sin(mid) - follower[0]
        dy = park.LIFT_Y - cam.ECC * math.cos(mid) - follower[1]
        gap = abs(dx * normal[1] - dy * normal[0]) - radii
        if gap > 0:
            hi = mid
        else:
            lo = mid
    engage_cam = (lo + hi) / 2

    # Preserve the released chain equation for each actual removable-gear pair.
    # Only its explicit wrap-radius input assignments differ; the 66 existing
    # native links and 6.35 mm pitch stay fixed, with sag absorbing the change.
    chain_tree = ast.parse(Path(chain.__file__).read_text(), filename=chain.__file__)
    chain_paths = {}
    for gearing, knob_radius, crank_radius in (
        ("small-large", 24.0, 12.0),
        ("medium-medium", 18.0, 18.0),
        ("large-small", 12.0, 24.0),
    ):
        tree = ast.parse(ast.unparse(chain_tree), filename=chain.__file__)
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                if node.targets[0].id == "WRAP_R_A":
                    node.value = ast.Constant(knob_radius)
                elif node.targets[0].id == "WRAP_R_B":
                    node.value = ast.Constant(crank_radius)
        values = {"__name__": f"exported_chain_{gearing}"}
        # Whole pinned-commit chain module with only WRAP_R_A/B constants replaced.
        exec(compile(ast.fix_missing_locations(tree), chain.__file__, "exec"), values)  # noqa: S102
        if values["LINK_COUNT"] != chain.LINK_COUNT:
            raise ValueError(
                f"{gearing} does not close on the existing native link count"
            )
        chain_paths[gearing] = {
            "arcsMm": [
                [0.0, 0.0, knob_radius, values["_ANG_N"], values["SPAN_A"]],
                [
                    values["CX"],
                    values["CY"],
                    values["SLACK_R"],
                    values["_ANG_GA"],
                    values["SPAN_SLACK"],
                ],
                [
                    values["BX"],
                    values["BY"],
                    crank_radius,
                    values["_ANG_GB"],
                    values["SPAN_B"],
                ],
            ],
            "tautMm": [
                values["BX"] + crank_radius * values["TNX"],
                values["BY"] + crank_radius * values["TNY"],
                knob_radius * values["TNX"],
                knob_radius * values["TNY"],
            ],
            "tautLengthMm": values["TAUT_LEN"],
            "sagMm": values["SAG"],
            "crankPitchRadiusMm": crank_radius,
        }
    chain_native = []
    for path, matrix in nodes.items():
        if path.startswith(
            (
                "harmonic-analyzer/paper-drive/chain-inner-link-",
                "harmonic-analyzer/paper-drive/chain-outer-link-",
            )
        ):
            station = chain.loop_parameter(
                matrix[12] * 1000.0,
                matrix[13] * 1000.0,
                dx=chain.KNOB_CENTRE[0],
                dy=chain.KNOB_CENTRE[1],
                mirror_x=True,
            )
            chain_native.append(
                {
                    "partPath": path,
                    "restStationMm": station,
                    "restPin0Mm": [value * 1000.0 for value in matrix[12:15]],
                    "restPin1Mm": [
                        matrix[12 + i] * 1000.0 + matrix[i] * chain.LINK_PITCH
                        for i in range(3)
                    ],
                }
            )
    if len(chain_native) != chain.LINK_COUNT:
        raise ValueError(
            "Native chain inventory does not match the source closed chain"
        )
    chain_native.sort(key=lambda link: link["restStationMm"])
    for index, link in enumerate(chain_native):
        following = chain_native[(index + 1) % len(chain_native)]
        link["nextPartPath"] = following["partPath"]
        link["nextRestStationMm"] = following["restStationMm"] + (
            chain.CENTRELINE_LEN
            if following["restStationMm"] < link["restStationMm"]
            else 0.0
        )
        link["nextNativePinGapMm"] = math.dist(
            link["restPin1Mm"], following["restPin0Mm"]
        )
    native_joint_gaps = [link["nextNativePinGapMm"] for link in chain_native]
    # Record released-source hashes and make working-tree differences explicit.
    # Every equation above was evaluated from the released-source snapshot.
    source_paths = sorted(
        {
            Path(m.__file__).resolve()
            for m in sys.modules.values()
            if getattr(m, "__file__", None)
            and Path(m.__file__).resolve().is_relative_to(cad / "scripts")
        }
    )
    source_paths.extend(sorted((cad / "config").rglob("*.yaml")))
    source_paths.extend(
        cad / "scripts" / name
        for name in (
            "build_drive_train_assembly.py",
            "build_paper_drive_assembly.py",
            "build_magnifier_assembly.py",
            "build_kinematic_probe.py",
        )
    )
    sources = []
    for path in sorted(set(source_paths)):
        relative = str(path.relative_to(snapshot_root))
        release = path.read_bytes()
        working_path = repo / relative
        working_matches = working_path.exists() and working_path.read_bytes() == release
        sources.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(release).hexdigest(),
                "workingTreeMatchesRelease": working_matches,
            }
        )
    data = {
        "harmonicNumbers": [row["harmonic_n"] for row in config.channels()],
        "provenance": {
            "sourceCommit": RELEASE_COMMIT,
            "modelSha256": model_hash,
            "units": "CAD mm; exported pose uses metres/radians/newtons",
            "sourceFiles": sources,
            "restChecks": checks,
            "maximumRestErrorMm": max(check["errorMm"] for check in checks),
        },
        "channel": {
            "count": count,
            "pivotMm": frame.ROCKER_PIVOT_XY,
            "fulcrumMm": frame.LEVER_FULCRUM_XY,
            "camShaftMm": frame.CAM_SHAFT_XY,
            "camHomeRad": math.radians(frame.CYLINDER_LOCK_PHASE_DEG),
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
            "stationDomainKind": "configured-nominal-not-engraved-scale",
            "stickScaleSpanMm": config.machine("amplitude", "stick_division_spacing_mm")
            * (config.machine("amplitude", "stick_division_count") - 1),
            "stickZeroToFootAxisDatum": "unresolved; do not equate configured maximum station with the engraved 10",
            "stationZ0Mm": z0,
            "stationPitchMm": pitch,
            "midplaneOffsetMm": mid_dz,
            "rodDepthOffsetMm": -(cyl.FACE_WIDTH + cyl.CAM_THICKNESS) / 2.0,
            "stickDivisionMm": config.machine("amplitude", "stick_division_spacing_mm"),
        },
        "spring": {
            "anchorMm": mount.CHANNEL_ANCHOR_XY,
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
            "maximumForceN": float(
                config.parts("channel-spring-installed")["maximum_load_n"]
            ),
        },
        "counter": {
            "anchorMm": mount.COUNTER_ANCHOR_XY,
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
            "screwRadiusMm": goose.SCREW_SHANK_DIA / 2.0,
            "coilOutsideDiameterMm": counter.COIL_OD_MM,
            "wireDiameterMm": counter.WIRE_DIA_MM,
            "coilTurns": counter.COIL_TURNS,
            "gooseneckArmYMm": goose.ARM_Y,
            "reference": asdict(mount.COUNTER_REFERENCE_POSE),
            "referenceGooseneckYMm": mount.GOOSENECK_ORIGIN_Y,
            "nativeReference": asdict(native_counter.pose),
            "nativeGooseneckYMm": native_goose_y,
        },
        "summing": {
            "knifeMm": [mount.KNIFE[0], mount.KNIFE_CONTACT_Y, sum_z],
            "anchorArmMm": modules["summing_lever_spec"].HOLE_X,
        },
        "magnifier": {
            "clampRadiusBandMm": mag.clamp_radius_band(
                modules["magnifying_clamp_geom"].BLOCK_DEPTH
            ),
            "clampRestMm": [lw.CLAMP_X, mount.KNIFE[1], -128.3],
            "fixtureRestMm": [
                lw.CLAMP_X,
                lw.HOOK_Y + lw.WIRE_DIA / 2 + lw.CLEARANCE,
                lw.HOOK_Z
                + modules["magnifying_vertical_rod_spec"].ROD_DIA / 2
                + lw.WIRE_DIA / 2
                + lw.CLEARANCE,
            ],
            # build_magnifier_assembly:209 sets rod top at lever Y+5.
            # Full collar must remain on the straight rod, below the clamp.
            "fixtureOffsetRangeM": [
                (
                    mount.KNIFE[1]
                    + 5.0
                    - modules["magnifying_vertical_rod_spec"].ROD_LENGTH
                    + modules["magnifying_vertical_rod_spec"].ROD_DIA / 2
                    - (lw.HOOK_Y + lw.WIRE_DIA / 2 + lw.CLEARANCE)
                )
                / 1000,
                (
                    mount.KNIFE[1]
                    - modules["magnifying_clamp_geom"].LEVER_BORE_Y
                    - modules["output_fixture_spec"].COLLAR_HEIGHT
                    - (lw.HOOK_Y + lw.WIRE_DIA / 2 + lw.CLEARANCE)
                )
                / 1000,
            ],
            "hubPitchRadiusMm": lw.HUB_DIA / 2 + lw.WIRE_DIA / 2,
            "rimPitchRadiusMm": pw.RIM_DIA / 2 + pw.WIRE_DIA / 2,
            "wireDiameterMm": lw.WIRE_DIA,
            "visualClearanceMm": lw.CLEARANCE,
            "hookMm": lw.WIRE_START,
            "hubTangentMm": lw.WIRE_END,
            "wheelCentreMm": [lw.WHEEL_X, lw.WHEEL_BAR_Y, lw.WHEEL_MID_Z],
            "penWireBottomMm": pw.WIRE_BOTTOM,
            "cadCoupling": "Rest-linearized yoke; operational wire swing/spin and wrap require the separate physical output-chain solver.",
        },
        "setup": {
            "conePivotMm": cone_pivot,
            "coneDisengageRad": math.radians(hardware.disengage_deg),
            "pinionPivotMm": [park.PIVOT_X, park.PIVOT_Y, pinion_z],
            "pinionParkedMm": [park.APINION_X, park.APINION_Y, drum_z],
            "pinionLiftMm": [park.LIFT_X, park.LIFT_Y, lift_z],
            "pinionEccentricityMm": cam.ECC,
            "pinionContactRadiiMm": radii,
            "followerCentreMm": park.FPIN_C,
            "followerNormal": park.SPR_N,
            "pinionEngageSwingRad": engage_swing,
            "pinionEngageCamRad": engage_cam,
            "pinionParkedLeverRad": math.radians(10.0),
        },
        "paperDrive": {
            "chainRatioFine": paper.CHAIN_RATIO,
            "reducerRatio": paper.GEAR_RATIO,
            "feedPitchDiameterMm": paper.FEED_PITCH_DIA,
            "fineTravelMmPerCrankRev": paper.NET_RACK_TRAVEL_PER_CRANK_REV,
            # Released build_kinematic_probe constants 101/108 and signed gate 314-324.
            "crankAxis": [0.0, 0.0, 1.0],
            "sprocketAxis": [0.0, 0.0, 1.0],
            "discAxis": [0.0, 0.0, 1.0],
            "feedAxis": [0.0, 0.0, 1.0],
            "chainSense": 1.0,
            "externalMeshSense": -1.0,
            "rackFeedSense": 1.0,
            "netTravelSense": -1.0,
            "chain": {
                "linkCount": chain.LINK_COUNT,
                "pitchMm": chain.LINK_PITCH,
                "centrelineLengthMm": chain.CENTRELINE_LEN,
                "mirrorX": True,
                "knobCentrePreMirrorMm": chain.KNOB_CENTRE,
                "nativeLinks": chain_native,
                "paths": chain_paths,
                "presentationModel": "released CAD circle/sag proxy; not rigid-link tooth-contact or 3D setup-chain dynamics",
                "nativeRestJoinedPins": sum(gap <= 0.0001 for gap in native_joint_gaps),
                "nativeRestMaximumPinGapMm": max(native_joint_gaps),
                "advanceMmPerCrankRadian": "negative selected crank pitch radius",
            },
        },
        "renderFrames": {
            "crankPivotMm": [
                value * 1000
                for value in nodes["harmonic-analyzer/drive-train/crankshaft-1"][12:15]
            ],
            "crankAxis": [0.0, 0.0, 1.0],
            "coneShaftPivotMm": [
                value * 1000
                for value in nodes["harmonic-analyzer/drive-train/cone-gear-shaft-1"][
                    12:15
                ]
            ],
            "coneShaftAxis": nodes["harmonic-analyzer/drive-train/cone-gear-shaft-1"][
                8:11
            ],
            "paperKnobPivotMm": [
                value * 1000
                for value in nodes[
                    "harmonic-analyzer/paper-drive/transgear-knob-shaft-1"
                ][12:15]
            ],
            "paperFeedPivotMm": [
                value * 1000
                for value in nodes["harmonic-analyzer/paper-drive/rack-pinion-1"][12:15]
            ],
            "paperFeedAxis": [0.0, 0.0, 1.0],
            "platenRestMm": [
                value * 1000
                for value in nodes["harmonic-analyzer/paper-drive/platen-1"][12:15]
            ],
            "worldMatrices": {
                path: matrix
                for path, matrix in nodes.items()
                if path.startswith("harmonic-analyzer/")
            },
        },
        "restChannels": rest_channels,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "// Generated by web/scripts/export-mechanics.py; do not edit by hand.\n"
        "// Source-only data; no source video, book images, or model geometry.\n"
        "export const MECHANISM_DATA = "
        + json.dumps(data, indent=2, allow_nan=False)
        + " as const\n"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sourceFiles": len(sources),
                "restChecks": len(checks),
                "maximumRestErrorMm": data["provenance"]["maximumRestErrorMm"],
                "modelSha256": model_hash,
            }
        )
    )
    snapshot.cleanup()


if __name__ == "__main__":
    main()
