#!/usr/bin/env python3
"""Export magnifier source geometry and a nonzero coordinate-based control.

Run with the approved raw model and its exact source identity:
  python web/scripts/export-magnifier.py --source-commit <approved-release-commit> \\
    --model /path/to/raw.glb --expected-model-sha256 <approved-raw-sha256>
Only numeric JSON is emitted. CAD stays read-only; no COM, native build, source
images, or generated GLB modifications. This is not the website acceptance gate.
The control constructs a circle tangent by bisection of the perpendicularity
constraint, independently of magnifier.ts's analytic acos tangent expression.
The release's own visual wire end selects the tangent branch; the wrap sense
and winding law follow from that branch's geometry, never from a fixed sign.
"""

from __future__ import annotations

import hashlib
import argparse
import io
import json
import math
import subprocess
import struct
import sys
import tarfile
import tempfile
from pathlib import Path

from native_identity_source import (
    CadIdentityMap,
    glb_nodes,
    magnifier_installation,
    project_model_paths,
    validate_release_pair,
    wheel_wire_pitch_radii,
)

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True,
                        help="Approved exact CAD release source commit")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    args = parser.parse_args()
    try:
        validate_release_pair(args.source_commit, args.expected_model_sha256)
        nodes, model_hash = glb_nodes(args.model)
        if model_hash != args.expected_model_sha256:
            raise ValueError(
                f"Raw model SHA256 {model_hash} differs from --expected-model-sha256 "
                f"{args.expected_model_sha256}; supply the approved original raw GLB"
            )
    except (OSError, ValueError, struct.error) as error:
        parser.error(str(error))
    try:
        archive = subprocess.check_output(
            ["git", "-c", "core.autocrlf=false", "archive", args.source_commit, "cad/scripts", "cad/config"],
            cwd=ROOT, stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        parser.error(
            f"Cannot archive CAD source commit {args.source_commit}: "
            f"{error.stderr.decode('utf-8', errors='replace').strip()}. "
            "Working-tree CAD is never used"
        )
    except OSError as error:
        parser.error(f"Cannot archive CAD source commit {args.source_commit}: {error}")
    with tempfile.TemporaryDirectory(prefix="magnifier-source-") as temp:
        snapshot_root = Path(temp).resolve()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(snapshot_root, filter="data")
        cad = snapshot_root / "cad"
        scripts = cad / "scripts"
        try:
            identity_map = CadIdentityMap(ROOT)
            nodes, identity = project_model_paths(args.model, nodes, model_hash, identity_map)
        except (OSError, ValueError) as error:
            parser.error(f"Cannot use the approved native identity projection: {error}")
        sys.path.insert(0, str(scripts))
        wire = identity_map.import_module(cad, "mg_lever_wire_geom")
        pen = identity_map.import_module(cad, "pn_pen_wire_geom")
        lever = identity_map.import_module(cad, "mg_magnifying_lever_geom")
        clamp = identity_map.import_module(cad, "mg_magnifying_clamp_geom")
        spring = identity_map.import_module(cad, "spring_mount_geom")
        cx, cy = wire.WHEEL_X, wire.WHEEL_BAR_Y
        radius, rim = wheel_wire_pitch_radii(wire, pen)
        vertical = identity_map.import_module(cad, "mg_magnifying_vertical_rod_spec")
        fixture = identity_map.import_module(cad, "mg_output_fixture_spec")
        installation = magnifier_installation(
            identity_map.source_file(cad, "scripts/build_mg_magnifier_assembly.py")
        )
        rest = tuple(wire.WIRE_START)
        # The release's visual wire end is its contact lane (hub or drum end
        # station) and fixes which of the two hook tangents it rides. Machine
        # +1 is the side counter-clockwise (about +Z) of the hook bearing.
        contact_z = wire.WIRE_END[2]
        branch = math.copysign(
            1.0,
            math.sin(
                math.atan2(wire.WIRE_END[1] - cy, wire.WIRE_END[0] - cx)
                - math.atan2(rest[1] - cy, rest[0] - cx)
            ),
        )

        def tangent(
            hook: tuple[float, float, float],
        ) -> tuple[float, list[float], float]:
            hx, hy, _hz = hook
            # Dot((H - centre), unit(a)) - r = 0. At the hook bearing it is
            # |H - centre| - r > 0, and half a turn toward the branch side it is
            # -|H - centre| - r < 0, monotone between, so bisection finds the
            # tangent without acos or assuming a fixed contact.
            near = math.atan2(hy - cy, hx - cx)
            far = near + branch * math.pi
            for _ in range(70):
                a = (near + far) / 2
                dot = (hx - cx) * math.cos(a) + (hy - cy) * math.sin(a) - radius
                if dot > 0:
                    near = a
                else:
                    far = a
            a = (near + far) / 2
            point = [
                cx + radius * math.cos(a),
                cy + radius * math.sin(a),
                contact_z,
            ]
            return a, point, math.dist(hook, point)

        a0, contact0, length0 = tangent(rest)
        # The wire reaches the contact travelling from the hook and wraps on
        # around the wheel the same way: +1 counter-clockwise about +Z. Taut
        # no-slip conservation, L + wrap * r * (wheelAngle - a) = constant,
        # gives the winding law below.
        wrap = math.copysign(
            1.0,
            (contact0[1] - rest[1]) * math.cos(a0) - (contact0[0] - rest[0]) * math.sin(a0),
        )
        controls = []
        for angle in (-0.01, 0.01):
            kx, ky = spring.KNIFE[0], spring.KNIFE_CONTACT_Y
            dx, dy = rest[0] - kx, rest[1] - ky
            hook = (
                kx + dx * math.cos(angle) - dy * math.sin(angle),
                ky + dx * math.sin(angle) + dy * math.cos(angle),
                rest[2],
            )
            a, point, length = tangent(hook)
            wheel_angle = a - a0 - wrap * (length - length0) / radius
            controls.append(
                {
                    "summingAngleRad": angle,
                    "hookMm": hook,
                    "hubContactMm": point,
                    "wheelAngleRad": wheel_angle,
                    "penTravelMm": -rim * wheel_angle,
                    "wireLengthResidualMm": length
                    + wrap * radius * (wheel_angle - a)
                    - (length0 - wrap * radius * a0),
                }
            )
        names = (
            "mg_lever_wire_geom.py",
            "mg_magnifying_lever_geom.py",
            "mg_magnifying_wheel_geom.py",
            "mg_magnifying_wheel_spec.py",
            "pn_pen_wire_geom.py",
            "build_mg_magnifier_assembly.py",
            "build_pn_pen_assembly.py",
            "mg_magnifying_vertical_rod_spec.py",
            "build_mg_magnifying_vertical_rod.py",
            "mg_output_fixture_spec.py",
            "mg_magnifying_clamp_geom.py",
        )
        source_paths = {
            Path(module.__file__).resolve()
            for module in sys.modules.values()
            if getattr(module, "__file__", None)
            and Path(module.__file__).resolve().is_relative_to(scripts)
        }
        source_paths.update(identity_map.source_file(cad, "scripts/" + name) for name in names)
        source_paths.update((cad / "config").rglob("*.yaml"))
        print(
            json.dumps(
                {
                    "sourceCommit": args.source_commit,
                    "modelSha256": model_hash,
                    "nativeIdentityMapSha256": identity["mapSha256"],
                    "canonicalModelSha256": identity["canonicalSha256"],
                    "sourceFiles": [
                        {
                            "path": path.relative_to(snapshot_root).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                        for path in sorted(source_paths)
                    ],
                    "units": "millimetres/radians",
                    "wireDiameterMm": wire.WIRE_DIA,
                    "visualClearanceMm": wire.CLEARANCE,
                    "hubPitchRadiusMm": radius,
                    "rimPitchRadiusMm": rim,
                    # +1: counter-clockwise about machine +Z from the hook
                    # bearing (tangent) / around the wheel (wrap).
                    "tangentBranch": branch,
                    "wrapSense": wrap,
                    "clampRadiusBandMm": lever.clamp_radius_band(clamp.BLOCK_DEPTH),
                    "rest": {
                        "hookMm": rest,
                        "wheelCentreMm": [cx, cy, wire.WHEEL_MID_Z],
                        "physicalHubContactMm": contact0,
                        "visualHubContactMm": wire.WIRE_END,
                        "physicalWireLengthMm": length0,
                        "visualWireLengthMm": wire.WIRE_LEN,
                        "penWireBottomMm": pen.WIRE_BOTTOM,
                        "penRestMm": [
                            value * 1000
                            for value in nodes["ha-harmonic-analyzer/pn-pen/pn-pen-marker-1"][12:15]
                        ],
                    },
                    "coordinateControls": controls,
                    # The exact archived assembly supplies both rod-top and
                    # collar datums; the full collar stays on the straight land.
                    "fixtureOffsetRangeMm": [
                        installation["VROD_TOP_Y"] - vertical.ROD_LENGTH
                        + vertical.ROD_DIA / 2 - installation["FIXTURE_Y0"],
                        installation["LEVER_ROD_Y"] - clamp.LEVER_BORE_Y
                        - fixture.COLLAR_HEIGHT - installation["FIXTURE_Y0"],
                    ],
                    "limitations": [
                        "Installed taut no-slip guided-wrap branch; not a slip or unravelling dynamics model.",
                        "CAD wire diameter is exaggerated; finite pitch is distinct from the primary source's nominal thin-wire 5x.",
                        "CAD straight wire geometry omits wraps and tie-offs; unknown initial wrap count cancels in incremental motion.",
                    ],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
