#!/usr/bin/env python3
"""Export magnifier source geometry and a nonzero coordinate-based control.

Run from any directory: python web/scripts/export-magnifier.py
Only numeric JSON is emitted. CAD stays read-only; no COM, native build, source
images, or generated GLB modifications. This is not the website acceptance gate.
The control constructs a circle tangent by bisection of the perpendicularity
constraint, independently of magnifier.ts's analytic acos tangent expression.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import math
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

COMMIT = "1268c23d4a8fc741147c5e09d8d1e45247a71945"
ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    archive = subprocess.check_output(
        ["git", "archive", COMMIT, "cad/scripts", "cad/config"], cwd=ROOT
    )
    with tempfile.TemporaryDirectory(prefix="magnifier-source-") as temp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(temp, filter="data")
        scripts = Path(temp) / "cad/scripts"
        sys.path.insert(0, str(scripts))
        wire = importlib.import_module("lever_wire_geom")
        wheel = importlib.import_module("magnifying_wheel_geom")
        pen = importlib.import_module("pen_wire_geom")
        lever = importlib.import_module("magnifying_lever_geom")
        clamp = importlib.import_module("magnifying_clamp_geom")
        spring = importlib.import_module("spring_mount_geom")
        cx, cy = wire.WHEEL_X, wire.WHEEL_BAR_Y
        radius = wheel.HUB_DIA / 2 + wire.WIRE_DIA / 2
        vertical = importlib.import_module("magnifying_vertical_rod_spec")
        fixture = importlib.import_module("output_fixture_spec")
        rim = wheel.RIM_OUTER_DIA / 2 + pen.WIRE_DIA / 2

        def tangent(
            hook: tuple[float, float, float],
        ) -> tuple[float, list[float], float]:
            hx, hy, _hz = hook
            # Dot((H - contact), contact - centre) = 0, source +X tangent.
            # The installed hook is above the circle; [-pi/2, pi/2] brackets
            # this tangent without taking acos or assuming a fixed contact.
            lo, hi = -math.pi / 2, math.pi / 2
            for _ in range(70):
                a = (lo + hi) / 2
                dot = (hx - cx) * math.cos(a) + (hy - cy) * math.sin(a) - radius
                if dot > 0:
                    hi = a
                else:
                    lo = a
            a = (lo + hi) / 2
            point = [
                cx + radius * math.cos(a),
                cy + radius * math.sin(a),
                wire.HUB_END_Z,
            ]
            return a, point, math.dist(hook, point)

        rest = tuple(wire.WIRE_START)
        a0, contact0, length0 = tangent(rest)
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
            wheel_angle = (length - length0) / radius + a - a0
            controls.append(
                {
                    "summingAngleRad": angle,
                    "hookMm": hook,
                    "hubContactMm": point,
                    "wheelAngleRad": wheel_angle,
                    "penTravelMm": rim * wheel_angle,
                    "wireLengthResidualMm": length
                    + radius * (a - wheel_angle)
                    - (length0 + radius * a0),
                }
            )
        names = (
            "lever_wire_geom.py",
            "magnifying_lever_geom.py",
            "magnifying_wheel_geom.py",
            "magnifying_wheel_spec.py",
            "pen_wire_geom.py",
            "build_magnifier_assembly.py",
            "build_pen_assembly.py",
            "magnifying_vertical_rod_spec.py",
            "build_magnifying_vertical_rod.py",
            "output_fixture_spec.py",
            "magnifying_clamp_geom.py",
        )
        print(
            json.dumps(
                {
                    "sourceCommit": COMMIT,
                    "sourceFiles": [
                        {
                            "path": "cad/scripts/" + name,
                            "sha256": hashlib.sha256(
                                (scripts / name).read_bytes()
                            ).hexdigest(),
                        }
                        for name in names
                    ],
                    "units": "millimetres/radians",
                    "wireDiameterMm": wire.WIRE_DIA,
                    "visualClearanceMm": wire.CLEARANCE,
                    "hubPitchRadiusMm": radius,
                    "rimPitchRadiusMm": rim,
                    "clampRadiusBandMm": lever.clamp_radius_band(clamp.BLOCK_DEPTH),
                    "rest": {
                        "hookMm": rest,
                        "wheelCentreMm": [cx, cy, wire.WHEEL_MID_Z],
                        "physicalHubContactMm": contact0,
                        "visualHubContactMm": wire.WIRE_END,
                        "physicalWireLengthMm": length0,
                        "visualWireLengthMm": wire.WIRE_LEN,
                        "penWireBottomMm": pen.WIRE_BOTTOM,
                    },
                    "coordinateControls": controls,
                    # Assembly-installed rest: LEVER_ROD_Y=979.7, VROD_TOP_Y=984.7,
                    # FIXTURE_Y0=915.7. Full collar on the straight land at the low
                    # end; collar top meets the clamp bottom at the high end.
                    "fixtureOffsetRangeMm": [
                        984.7 - vertical.ROD_LENGTH + vertical.ROD_DIA / 2 - 915.7,
                        979.7 - clamp.LEVER_BORE_Y - fixture.COLLAR_HEIGHT - 915.7,
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
