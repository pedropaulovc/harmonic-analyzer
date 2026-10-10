#!/usr/bin/env python3
"""Export pure CAD mechanism data and verify it against an explicitly pinned raw GLB.

Run from the repository root (use the approved release commit and raw digest):
  uv run --isolated --no-project --python 3.13 \\
    --with-requirements web/scripts/requirements-model-export.txt \\
    python web/scripts/export-mechanics.py --model /path/to/raw-native.glb \\
    --source-commit 81539e53f5146c06a77541415bd79da673806d96 \\
    --expected-model-sha256 60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c
Only web output is written. CAD sources and the raw model are read-only. The GLB
is not redistributed. CAD is archived from the exact supplied commit, never from
the working tree. Analytic force seats and calibrated native render seats are
kept separate; the latter are never interpolated into an invented force model.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
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

from native_identity_source import (
    CadIdentityMap,
    glb_nodes,
    magnifier_installation,
    project_model_paths,
    validate_release_pair,
)


def recipe_literal_constants(path: Path, names: tuple[str, ...]) -> dict:
    """Read pinned numeric recipe constants without importing COM recipes."""
    values = {}
    for node in ast.parse(path.read_text(), filename=str(path)).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    values[target.id] = ast.literal_eval(node.value)
    if set(values) != set(names):
        raise ValueError(f"Missing native mathematical contract {names} in {path}")
    return values


def pen_rest_datum(path: Path, block, marker) -> list[float]:
    """Evaluate the archived nib-placement data and its pure transform only."""
    constants = recipe_literal_constants(
        path,
        ("PAPER_FRONT_Z", "CLEARANCE", "PEN_ROD_X", "PEN_Z_MID",
         "BLOCK_BOTTOM_Y", "BLOCK_YAW_DEG"),
    )
    namespace = {
        **constants,
        "math": math,
        "BLOCK_DEPTH": block.BLOCK_DEPTH,
        "BORE_X": block.BORE_X,
        "GROOVE_DEPTH": block.GROOVE_DEPTH,
        "BARREL_DIA": marker.BARREL_DIA,
    }
    names = {
        "_C", "_S", "BLOCK_ROWS", "ROD_BORE_LOCAL", "VBLOCK_POS",
        "MARKER_AXIS_LOCAL_Y", "MARKER_TIP_LOCAL_X", "MARKER_POS",
    }
    statements = []
    found = set()
    for node in ast.parse(path.read_text(), filename=str(path)).body:
        if isinstance(node, ast.FunctionDef) and node.name == "_block_to_machine":
            statements.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            targets = {target.id for target in node.targets if isinstance(target, ast.Name)}
            if targets & names:
                statements.append(node)
                found.update(targets)
    if found != names | {"_block_to_machine"}:
        raise ValueError(f"Missing released pen-placement contract in {path}")
    exec(compile(ast.Module(body=statements, type_ignores=[]),
                 str(path), "exec"), namespace)  # noqa: S102
    return namespace["MARKER_POS"]


def spring_deformation_contract(cad: Path, stock, counter) -> tuple[dict, dict]:
    """Read only the archived pure transition AST, never its COM imports.

    Export the actual coil length law and hook/transition geometry consumed by
    scene.ts. Catalogue limits, forces and other rigid end-assembly geometry
    are deliberately not fixed by this contract.
    """
    transition_path = cad / "scripts/diagnostics/diag_build_9432K31.py"
    transition_values = recipe_literal_constants(
        transition_path,
        ("VENDOR_TRANSITION_CP_MM", "VENDOR_HANDLE_POLAR_RAD", "_FREE_EPS_MM"),
    )
    transition_tree = ast.parse(transition_path.read_text(), filename=str(transition_path))
    transition_function = next(
        node for node in transition_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "transition_bezier_mm"
    )
    namespace = {**vars(stock), **transition_values, "math": math}
    exec(compile(ast.Module(body=[transition_function], type_ignores=[]),
                 str(transition_path), "exec"), namespace)  # noqa: S102

    contracts = []
    for module in (stock, counter):
        is_counter = module is counter
        lengths = (module.FREE_LENGTH_MM, module.MAX_LENGTH_MM)
        profiles = []
        for length in lengths:
            ends = (
                (module.coil_start_x_mm(length), module.coil_end_x_mm(length))
                if is_counter else module.coil_ends_mm(length)
            )
            profile = {"lengthMm": length, "coilEndsMm": ends}
            if not is_counter:
                profile["hookEyeCentresMm"] = module.end_centers_mm(length)
                profile["transitionControlPointsMm"] = namespace["transition_bezier_mm"](length)
            profiles.append(profile)
        start, end = profiles[0]["coilEndsMm"]
        contract = {
            "coilEndInsetMm": lengths[0] / 2.0 + start,
            "coilEndCorrectionMm": -start - end,
            "coilMeanRadiusMm": module.COIL_MEAN_RADIUS_MM,
            "wireRadiusMm": module.WIRE_RADIUS_MM if is_counter else module.WIRE_DIA_MM / 2.0,
            "profiles": profiles,
        }
        if is_counter:
            contract["coilAxis"] = module.COIL_AXIS
        else:
            contract["transitionHandlePolarRad"] = transition_values["VENDOR_HANDLE_POLAR_RAD"]
            contract["transitionTangentMm"] = module.TRANSITION_TANGENT_MM
        contracts.append(contract)
    return tuple(contracts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cad-root", type=Path, default=Path(__file__).resolve().parents[2] / "cad"
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--source-commit",
        required=True,
        help="Approved CAD source commit: exactly 40 lowercase hexadecimal characters",
    )
    parser.add_argument(
        "--expected-model-sha256",
        required=True,
        help="Approved raw GLB SHA256: exactly 64 lowercase hexadecimal characters",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src/mechanics-data.ts",
    )
    args = parser.parse_args()
    try:
        validate_release_pair(args.source_commit, args.expected_model_sha256)
    except ValueError as error:
        parser.error(str(error))
    try:
        nodes, model_hash = glb_nodes(args.model)
    except (OSError, ValueError, struct.error) as error:
        parser.error(f"Cannot read --model as a complete raw GLB: {error}")
    if model_hash != args.expected_model_sha256:
        parser.error(
            f"Raw model SHA256 {model_hash} differs from --expected-model-sha256 "
            f"{args.expected_model_sha256}; supply the approved original raw GLB"
        )
    repo = args.cad_root.resolve().parent
    # Evaluate the exact supplied model revision, never working-tree CAD.
    # Only pure scripts/configuration enter the temporary snapshot.
    try:
        archive = subprocess.check_output(
            ["git", "-c", "core.autocrlf=false", "archive", args.source_commit, "cad/scripts", "cad/config"],
            cwd=repo,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", errors="replace").strip()
        parser.error(
            f"Cannot archive CAD source commit {args.source_commit}: {detail}. "
            "Fetch that exact commit with cad/scripts and cad/config; working-tree CAD is never used"
        )
    except OSError as error:
        parser.error(f"Cannot archive CAD source commit {args.source_commit} from {repo}: {error}")
    snapshot = tempfile.TemporaryDirectory(prefix="harmonic-mechanics-source-")
    snapshot_root = Path(snapshot.name).resolve()
    try:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(snapshot_root, filter="data")
    except (OSError, tarfile.TarError) as error:
        snapshot.cleanup()
        parser.error(f"Cannot read CAD source archive for {args.source_commit}: {error}")
    cad = snapshot_root / "cad"
    if not (cad / "scripts").is_dir() or not (cad / "config").is_dir():
        snapshot.cleanup()
        parser.error(f"CAD source archive for {args.source_commit} lacks cad/scripts or cad/config")
    try:
        identity_map = CadIdentityMap(repo)
        nodes, identity = project_model_paths(args.model, nodes, model_hash, identity_map)
    except (OSError, ValueError) as error:
        snapshot.cleanup()
        parser.error(f"Cannot use the approved native identity projection: {error}")
    try:
        export_snapshot(args, repo, cad, identity_map, nodes, identity, model_hash)
    finally:
        try:
            # Imports may configure telemetry with files inside this archive.
            # Only its owner may close them, before the snapshot is removed.
            telemetry = sys.modules.get("_telemetry")
            telemetry_path = getattr(telemetry, "__file__", None)
            if telemetry_path and Path(telemetry_path).resolve().is_relative_to(snapshot_root):
                telemetry.shutdown()
        finally:
            snapshot.cleanup()


def export_snapshot(
    args: argparse.Namespace, repo: Path, cad: Path, identity_map: CadIdentityMap,
    nodes: dict, identity: dict, model_hash: str,
) -> None:
    snapshot_root = cad.parent
    sys.path.insert(0, str(cad / "scripts"))
    # Historical released data tables sit in COM recipes whose unrelated
    # imports pull telemetry/Windows machinery. Evaluate exact assignment ASTs
    # only: genuine supplier data, no substitute geometry or COM function stubs.
    thumb_path = identity_map.source_file(cad, "scripts/diagnostics/diag_mcmaster_thumb.py")
    thumb_tree = ast.parse(thumb_path.read_text(), filename=str(thumb_path))
    thumb_assignment = next(
        (
            node
            for node in thumb_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "THUMB_SPECS"
                for target in node.targets
            )
        ),
        None,
    )
    if thumb_assignment is not None:
        thumb_module = types.ModuleType("diagnostics.diag_mcmaster_thumb")
        thumb_module.__file__ = str(thumb_path)
        # Pinned-commit assignment AST; not literal_eval-able (dict() calls, arithmetic).
        thumb_code = compile(
            ast.Module(body=[thumb_assignment], type_ignores=[]), str(thumb_path), "exec"
        )
        exec(thumb_code, thumb_module.__dict__)  # noqa: S102
        sys.modules[thumb_module.__name__] = thumb_module
    fillister_path = identity_map.source_file(cad, "scripts/diagnostics/diag_mcmaster_fillister.py")
    fillister_tree = ast.parse(fillister_path.read_text(), filename=str(fillister_path))
    # Historical released sources embed this table in the recipe. Current
    # sources import pure per-SKU dimensions and need no recipe projection.
    fillister_assignment = next(
        (
            node
            for node in fillister_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "FILLISTER_SIZES"
                for target in node.targets
            )
        ),
        None,
    )
    if fillister_assignment is not None:
        fillister_module = types.ModuleType("diagnostics.diag_mcmaster_fillister")
        fillister_module.__file__ = str(fillister_path)
        # Resolve the table's pure-spec bindings from this exact archived revision,
        # including aliases used by later supplier rows. Importing the COM recipe
        # itself would pull unrelated telemetry/Windows machinery into the exporter.
        required_names = {
            node.id for node in ast.walk(fillister_assignment.value)
            if isinstance(node, ast.Name)
        }
        for statement in fillister_tree.body:
            if not isinstance(statement, ast.ImportFrom) or not statement.module:
                continue
            if statement.level or not statement.module.endswith("_spec"):
                continue
            aliases = [
                alias for alias in statement.names
                if (alias.asname or alias.name) in required_names
            ]
            if not aliases:
                continue
            spec_module = identity_map.import_module(cad, statement.module)
            for alias in aliases:
                fillister_module.__dict__[alias.asname or alias.name] = getattr(
                    spec_module, alias.name
                )
        # Pinned-commit assignment AST; all referenced supplier constants are bound.
        fillister_code = compile(
            ast.Module(body=[fillister_assignment], type_ignores=[]),
            str(fillister_path),
            "exec",
        )
        exec(fillister_code, fillister_module.__dict__)  # noqa: S102
        sys.modules[fillister_module.__name__] = fillister_module
    modules = {
        name: identity_map.import_module(cad, name)
        for name in (
            "_config",
            "channel_kinematics",
            "channel_frame_geom",
            "ch_amplitude_bar_spec",
            "ch_rocker_arm_spec",
            "ch_channel_lever_spec",
            "ch_connecting_rod_spec",
            "dt_cylinder_gear_spec",
            "vn_channel_spring_stock_geom",
            "vn_counter_spring_stock_geom",
            "spring_mount_geom",
            "settled_spring_seats",
            "sm_gooseneck_geom",
            "sm_summing_lever_spec",
            "rocker_bank_layout",
            "dt_cone_pivot_post_installation",
            "mg_magnifying_lever_geom",
            "mg_magnifying_clamp_geom",
            "mg_lever_wire_geom",
            "pn_pen_wire_geom",
            "pn_pen_v_block_spec",
            "pn_pen_marker_spec",
            "paper_drive_geom",
            "pd_transgear_removable_spec",
            "spring_force_model",
            "pinion_rig_park_geometry",
            "dt_pinion_cam_geometry",
            "dt_pinion_cam_pin_geometry",
            "dt_pinion_bracket_geometry",
            "cone_line",
            "dt_cone_swing_platform_geometry",
            "vn_cone_lock_knob_spec",
            "vn_swing_stop_screw_spec",
            "mg_magnifying_vertical_rod_spec",
            "mg_output_fixture_spec",
            "_chain",
        )
    }
    config = modules["_config"]
    ck = modules["channel_kinematics"]
    frame = modules["channel_frame_geom"]
    bar = modules["ch_amplitude_bar_spec"]
    arm = modules["ch_rocker_arm_spec"]
    lever = modules["ch_channel_lever_spec"]
    cyl = modules["dt_cylinder_gear_spec"]
    rod = modules["ch_connecting_rod_spec"]
    stock = modules["vn_channel_spring_stock_geom"]
    counter = modules["vn_counter_spring_stock_geom"]
    spring_deformation, counter_deformation = spring_deformation_contract(cad, stock, counter)
    mount = modules["spring_mount_geom"]
    settled = modules["settled_spring_seats"]
    goose = modules["sm_gooseneck_geom"]
    mag = modules["mg_magnifying_lever_geom"]
    lw = modules["mg_lever_wire_geom"]
    pw = modules["pn_pen_wire_geom"]
    paper = modules["paper_drive_geom"]
    removable = modules["pd_transgear_removable_spec"]
    chain = modules["_chain"]
    installation = modules["dt_cone_pivot_post_installation"]
    magnifier_layout = magnifier_installation(
        identity_map.source_file(cad, "scripts/build_mg_magnifier_assembly.py")
    )
    feed_senses = recipe_literal_constants(
        identity_map.source_file(cad, "scripts/build_kinematic_probe.py"), ("GEAR_SENSE", "FEED_SIGN")
    )
    crank_teeth = [
        recipe_literal_constants(
            identity_map.source_file(cad, "scripts/build_dt_crank_pinion.py"), ("TEETH",)
        )["TEETH"],
        recipe_literal_constants(
            identity_map.source_file(cad, "scripts/dt_crank_drive_gear_spec.py"), ("TEETH",)
        )["TEETH"],
    ]
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
        prefix = "ha-harmonic-analyzer/ch-channel/"
        check(
            prefix + f"ch-rocker-arm-{n}",
            [0.0, arm.PIVOT_MID_Y, 0.0],
            [*frame.ROCKER_PIVOT_XY, mid],
        )
        check(
            prefix + f"ch-channel-lever-{n}",
            [0.0, 0.0, 0.0],
            [*frame.LEVER_FULCRUM_XY, mid],
        )
        check(
            prefix + f"ch-amplitude-bar-{n}",
            [0.0, 0.0, 0.0],
            [state["bar_origin_x"], state["bar_origin_y"], mid - bar.BAR_WIDTH / 2.0],
        )
        check(
            prefix + f"ch-connecting-rod-{n}",
            [0.0, 0.0, 0.0],
            [*ck._RING_CENTER, station - (cyl.FACE_WIDTH + cyl.CAM_THICKNESS) / 2.0],
        )
        spring_name = next(
            path
            for path in nodes
            if path.startswith(prefix + "vn-channel-spring-installed-")
            and path.endswith(f"-{n}")
        )
        check(spring_name, [0.0, 0.0, 0.0], [*spring.centre_xy, mid])
        check(
            f"ha-harmonic-analyzer/dt-drive-train/dt-cylinder-gear-{n}",
            [0.0, 0.0, 0.0],
            [*frame.CAM_SHAFT_XY, station + cyl.FACE_WIDTH / 2.0],
        )
        rest_channels.append(
            {
                "stationM": station / 1000.0,
                "midplaneM": mid / 1000.0,
                "rockerWorldMatrix": nodes[prefix + f"ch-rocker-arm-{n}"],
                "rodWorldMatrix": nodes[prefix + f"ch-connecting-rod-{n}"],
                "barWorldMatrix": nodes[prefix + f"ch-amplitude-bar-{n}"],
                "leverWorldMatrix": nodes[prefix + f"ch-channel-lever-{n}"],
                "springWorldMatrix": nodes[spring_name],
                "nativeSpring": asdict(spring),
            }
        )
    sum_z = installation.SUMMING_Z
    check(
        "ha-harmonic-analyzer/sm-summing/sm-summing-lever-1",
        [0.0, 0.0, 0.0],
        [*mount.KNIFE, sum_z],
    )
    check(
        "ha-harmonic-analyzer/sm-summing/sm-knife-mount-1",
        [0.0, 0.0, 0.0],
        [mount.KNIFE[0], mount.KNIFE_CONTACT_Y, sum_z + 87.0585],
    )
    check(
        "ha-harmonic-analyzer/sm-summing/vn-counter-spring-1",
        [0.0, 0.0, 0.0],
        [*native_counter.pose.centre_xy, sum_z],
    )
    check(
        "ha-harmonic-analyzer/sm-summing/sm-gooseneck-1",
        [0.0, 0.0, 0.0],
        [mount.COLUMN_X, native_goose_y, sum_z],
    )
    check(
        "ha-harmonic-analyzer/mg-magnifier/mg-magnifying-lever-1",
        [mag.KNIFE_LOCAL_X, mag.KNIFE_LOCAL_Y, 0.0],
        [*mount.KNIFE[:1], mount.KNIFE_CONTACT_Y, magnifier_layout["LEVER_ROD_Z"]],
    )
    check(
        "ha-harmonic-analyzer/mg-magnifier/mg-magnifying-wheel-1",
        [0.0, 0.0, 0.0],
        [lw.WHEEL_X, lw.WHEEL_BAR_Y, lw.WHEEL_MID_Z],
    )
    check(
        "ha-harmonic-analyzer/pn-pen/pn-pen-marker-1",
        [0.0, 0.0, 0.0],
        pen_rest_datum(
            identity_map.source_file(cad, "scripts/build_pn_pen_assembly.py"),
            modules["pn_pen_v_block_spec"], modules["pn_pen_marker_spec"],
        ),
    )
    park = modules["pinion_rig_park_geometry"]
    cam = modules["dt_pinion_cam_geometry"]
    cone_line = modules["cone_line"]
    platform = modules["dt_cone_swing_platform_geometry"]
    cone_pivot = cone_line.cone_station(platform.PIVOT_STATION)
    cone_pivot[1] = cone_line.Y_BASE_TOP
    hardware = platform.swing_hardware_geometry(
        (cone_pivot[0], cone_pivot[2]),
        lock_head_dia=modules["vn_cone_lock_knob_spec"].HEAD_DIA,
        stop_contact_dia=modules["vn_swing_stop_screw_spec"].CONTACT_DIA,
    )
    pinion_z = nodes["ha-harmonic-analyzer/dt-drive-train/dt-pinion-pivot-shaft-1"][14] * 1000
    lift_z = nodes["ha-harmonic-analyzer/dt-drive-train/dt-pinion-lift-rod-1"][14] * 1000
    drum_z = nodes["ha-harmonic-analyzer/dt-drive-train/dt-alignment-pinion-1"][14] * 1000
    check(
        "ha-harmonic-analyzer/dt-drive-train/dt-cone-swing-platform-1",
        [0.0, 0.0, 0.0],
        cone_pivot,
    )
    check(
        "ha-harmonic-analyzer/dt-drive-train/dt-pinion-pivot-shaft-1",
        [0.0, 0.0, 0.0],
        [park.PIVOT_X, park.PIVOT_Y, pinion_z],
    )
    check(
        "ha-harmonic-analyzer/dt-drive-train/dt-pinion-lift-rod-1",
        [0.0, 0.0, 0.0],
        [park.LIFT_X, park.LIFT_Y, lift_z],
    )
    check(
        "ha-harmonic-analyzer/dt-drive-train/dt-alignment-pinion-1",
        [0.0, 0.0, 0.0],
        [park.APINION_X, park.APINION_Y, drum_z],
    )
    # The engagement triangle and eccentric/follower contact are the actual
    # source equations (build_dt_drive_train_assembly.py:2532-2607), not a sweep RPM.
    pd = math.hypot(
        frame.CAM_SHAFT_XY[0] - park.PIVOT_X, frame.CAM_SHAFT_XY[1] - park.PIVOT_Y
    )
    parked_azimuth = math.atan2(
        park.APINION_Y - park.PIVOT_Y, park.APINION_X - park.PIVOT_X
    )
    strap = modules["dt_pinion_bracket_geometry"].C2C
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
    radii = (cam.CAM_OD + modules["dt_pinion_cam_pin_geometry"].PIN_DIA) / 2
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
    # Derive each source pitch circle while retaining the actual native chain.
    # Swapping mounted wheels cannot replace its existing links; the unchanged
    # archived closure bracket/assertions must solve that fixed standard length.
    chain_tree = ast.parse(Path(chain.__file__).read_text(), filename=chain.__file__)
    chain_paths = {}
    for gearing, knob_config, crank_config in (
        ("small-large", "T24", "T12"),
        ("medium-medium", "T18", "T18"),
        ("large-small", "T12", "T24"),
    ):
        knob_radius = removable.pitch_dia(removable.TEETH[knob_config]) / 2.0
        crank_radius = removable.pitch_dia(removable.TEETH[crank_config]) / 2.0
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
                elif node.targets[0].id == "LINK_COUNT":
                    node.value = ast.Constant(chain.LINK_COUNT)
        values = {"__name__": f"exported_chain_{gearing}"}
        # Whole archived source with mounted pitch radii and actual native link count.
        exec(compile(ast.fix_missing_locations(tree), chain.__file__, "exec"), values)  # noqa: S102
        # Assertions in the archived helper remain active in normal execution,
        # but Python -O must not publish a loop which misses its native length.
        # Re-evaluate its original sag bracket, before bisection overwrote it.
        bracket_assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Tuple)
                and [item.id for item in target.elts] == ["_LO_SAG", "_HI_SAG"]
                for target in node.targets
            )
        )
        bracket = dict(values)
        exec(compile(ast.Module(body=[bracket_assignment], type_ignores=[]),
                     chain.__file__, "exec"), bracket)  # noqa: S102
        loop_length = values["_loop_length"]
        target_length = values["CENTRELINE_LEN"]
        for sag in (bracket["_LO_SAG"], bracket["_HI_SAG"], values["SAG"]):
            # Mirror the archived slack-radius bracket (including its lower
            # bound search), without relying on its optimizable assert.
            lower_radius = max(knob_radius, crank_radius) + values["D"] / 2.0
            droop = values["_droop"]
            while droop(lower_radius) < sag:
                lower_radius *= 0.9
            if not droop(lower_radius) > sag > droop(10000.0):
                raise ValueError(f"Mounted chain {gearing} has no slack-radius bracket")
        # Check the actual solved radius as well as the archived search bounds:
        # future helper brackets must not silently clamp the published droop.
        if not abs(values["_droop"](values["SLACK_R"]) - values["SAG"]) < 1e-6:
            raise ValueError(f"Mounted chain {gearing} slack radius does not match its sag")
        if not (
            loop_length(bracket["_LO_SAG"]) < target_length
            < loop_length(bracket["_HI_SAG"])
        ):
            raise ValueError(f"Mounted chain {gearing} cannot bracket the native chain length")
        if not abs(loop_length(values["SAG"]) - target_length) < 1e-6:
            raise ValueError(f"Mounted chain {gearing} does not close on the native chain length")
        if not abs(
            values["SPAN_A"] + values["SPAN_SLACK"] + values["SPAN_B"]
            - 2.0 * math.pi
        ) < 1e-9:
            raise ValueError(f"Mounted chain {gearing} arc spans do not close a full turn")
        if not abs(
            knob_radius * values["SPAN_A"] + crank_radius * values["SPAN_B"]
            + values["SLACK_R"] * values["SPAN_SLACK"] + values["TAUT_LEN"]
            - target_length
        ) < 1e-6:
            raise ValueError(f"Mounted chain {gearing} arc length does not close on the native chain")
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
                "ha-harmonic-analyzer/pd-paper-drive/vn-chain-inner-link-",
                "ha-harmonic-analyzer/pd-paper-drive/vn-chain-outer-link-",
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
        identity_map.source_file(cad, "scripts/" + name)
        for name in (
            "build_dt_drive_train_assembly.py",
            "build_pd_paper_drive_assembly.py",
            "build_mg_magnifier_assembly.py",
            "build_pn_pen_assembly.py",
            "build_kinematic_probe.py",
            "build_dt_crank_pinion.py",
            "dt_crank_drive_gear_spec.py",
            "diagnostics/diag_build_9432K31.py",
        )
    )
    sources = []
    for path in sorted(set(source_paths)):
        relative = path.relative_to(snapshot_root).as_posix()
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
        "driveTrain": {
            "crankRatio": config.machine("gear_train", "crank_drive_ratio"),
            "crankTeeth": crank_teeth,
            "cylinderTeeth": cyl.TEETH,
            "channelMeshes": [
                {
                    "coneTeeth": row["cone_teeth"],
                    "cylinderTeeth": row["cylinder_teeth"],
                    "ratio": row["ratio"],
                }
                for row in config.channels()
            ],
        },
        "provenance": {
            "sourceCommit": args.source_commit,
            "modelSha256": model_hash,
            "nativeIdentityMapSha256": identity["mapSha256"],
            "canonicalModelSha256": identity["canonicalSha256"],
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
            "deformation": spring_deformation,
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
                config.parts(identity_map.registry_name(cad, "vn-channel-spring-installed"))["maximum_load_n"]
            ),
        },
        "counter": {
            "deformation": counter_deformation,
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
            "anchorArmMm": modules["sm_summing_lever_spec"].HOLE_X,
        },
        "magnifier": {
            "clampRadiusBandMm": mag.clamp_radius_band(
                modules["mg_magnifying_clamp_geom"].BLOCK_DEPTH
            ),
            "clampRestMm": [
                lw.CLAMP_X, magnifier_layout["LEVER_ROD_Y"], magnifier_layout["LEVER_ROD_Z"]
            ],
            "fixtureRestMm": [
                lw.CLAMP_X,
                magnifier_layout["FIXTURE_Y0"],
                lw.HOOK_Z
                + modules["mg_magnifying_vertical_rod_spec"].ROD_DIA / 2
                + lw.WIRE_DIA / 2
                + lw.CLEARANCE,
            ],
            # Read the exact archived assembly's rod top and collar datums.
            # Full collar must remain on the straight rod, below the clamp.
            "fixtureOffsetRangeM": [
                (
                    magnifier_layout["VROD_TOP_Y"]
                    - modules["mg_magnifying_vertical_rod_spec"].ROD_LENGTH
                    + modules["mg_magnifying_vertical_rod_spec"].ROD_DIA / 2
                    - magnifier_layout["FIXTURE_Y0"]
                )
                / 1000,
                (
                    magnifier_layout["LEVER_ROD_Y"]
                    - modules["mg_magnifying_clamp_geom"].LEVER_BORE_Y
                    - modules["mg_output_fixture_spec"].COLLAR_HEIGHT
                    - magnifier_layout["FIXTURE_Y0"]
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
            # The nib is the marker's native local origin. Its raw world datum
            # passed the independent archived MARKER_POS rest check above.
            "penRestMm": [
                value * 1000
                for value in nodes["ha-harmonic-analyzer/pn-pen/pn-pen-marker-1"][12:15]
            ],
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
            "externalMeshSense": feed_senses["GEAR_SENSE"],
            "rackFeedSense": feed_senses["FEED_SIGN"],
            "netTravelSense": feed_senses["GEAR_SENSE"] * feed_senses["FEED_SIGN"],
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
                for value in nodes["ha-harmonic-analyzer/dt-drive-train/dt-crankshaft-1"][12:15]
            ],
            "crankAxis": [0.0, 0.0, 1.0],
            "coneShaftPivotMm": [
                value * 1000
                for value in nodes["ha-harmonic-analyzer/dt-drive-train/dt-cone-gear-shaft-1"][
                    12:15
                ]
            ],
            "coneShaftAxis": nodes["ha-harmonic-analyzer/dt-drive-train/dt-cone-gear-shaft-1"][
                8:11
            ],
            "paperKnobPivotMm": [
                value * 1000
                for value in nodes[
                    "ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1"
                ][12:15]
            ],
            "paperFeedPivotMm": [
                value * 1000
                for value in nodes["ha-harmonic-analyzer/pd-paper-drive/pd-rack-pinion-1"][12:15]
            ],
            "paperFeedAxis": [0.0, 0.0, 1.0],
            "platenRestMm": [
                value * 1000
                for value in nodes["ha-harmonic-analyzer/pd-paper-drive/pd-platen-1"][12:15]
            ],
            "worldMatrices": {
                path: matrix
                for path, matrix in nodes.items()
                if path.startswith("ha-harmonic-analyzer/")
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
                "nativeIdentityMapSha256": identity["mapSha256"],
                "canonicalModelSha256": identity["canonicalSha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
