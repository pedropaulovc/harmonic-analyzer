#!/usr/bin/env python3
"""Private static-source constraints, using registered spin images and native equations.

Run with uv --no-project --with numpy --with scipy --with opencv-python-headless.
No source images, cameras, observation tracks, or full physical input are written
under web/. This helper consumes another owner's registration, not a camera fit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--pixels", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--hashes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--views", type=Path)
    parser.add_argument("--crops", type=Path)
    parser.add_argument("--loop-gray", type=Path)
    parser.add_argument("--identities", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = args.pixels.parent
    registration = json.loads(args.registration.read_text())
    params = np.array(registration["parameters"], dtype=float)
    pixels = json.loads(args.pixels.read_text())
    inventory = json.loads(args.inventory.read_text())
    hashes = json.loads(args.hashes.read_text())
    native_script = f"""
import {{MECHANISM_DATA,createMechanismInput,createMechanismPose,solveMechanism}} from {json.dumps(str(root / "src/mechanics.ts"))};
import {{physicalChannelAngle}} from {json.dumps(str(root / "src/kinematics.ts"))};
const input=createMechanismInput(),pose=createMechanismPose();
input.crankTurns=.137;
for(let j=0;j<20;j++){{input.amplitudes[j]=.12*Math.sin(j);input.phases[j]=.35*Math.cos(j);}}
solveMechanism(input,pose);
input.setup.counterHeightM=pose.counter.gooseneckHeightM;solveMechanism(input,pose);
const alternative=createMechanismInput(),alternativePose=createMechanismPose();
alternative.setup={{...input.setup,driveCrankOffsetTurns:4}};
alternative.crankTurns=input.crankTurns;alternative.amplitudes.set(input.amplitudes);
for(let j=0;j<20;j++)alternative.phases[j]=input.phases[j]+physicalChannelAngle(4,j);
solveMechanism(alternative,alternativePose);
const differences=[];
function compare(left,right,path=''){{for(const k of Object.keys(left)){{if(k==='_work')continue;
 const a=left[k],b=right[k];if(typeof a==='number')differences.push({{path:path+'.'+k,difference:Math.abs(a-b)}});
 else if(a!==null&&typeof a==='object')compare(a,b,path+'.'+k);
}}}}
compare(pose,alternativePose);
const gauge={{input,alternative,pose,alternativePose,maxConsumerPoseDifference:Math.max(...differences.map(d=>d.difference)),
 meaning:'Crank-bank lag +4 turns compensated by 20 native harmonic phase offsets; fixed counter height prevents an invented home-recalibration change.',
 warning:'Native witness only, not recovered source amplitudes or phases.'}};
console.log(JSON.stringify({{data:MECHANISM_DATA,pose,gauge}},(k,v)=>k==='_work'?undefined:ArrayBuffer.isView(v)?Array.from(v):v));
"""
    native = json.loads(
        subprocess.run(
            ["bun", "-e", native_script], check=True, capture_output=True, text=True
        ).stdout
    )
    data = native["data"]
    # Exact conservative upstream domain bound; counter/wire settings do not
    # enter solveChannel. This is NOT a source absence/occlusion verdict.
    c = data["channel"]
    shaft = np.array(c["camShaftMm"]) - c["pivotMm"]
    shaft_radius = float(np.linalg.norm(shaft))
    pin_radius = math.hypot(*c["rodPinMm"])
    shaft_bearing = math.atan2(shaft[1], shaft[0]) + 2 * math.pi
    pin_bearing = math.atan2(c["rodPinMm"][1], c["rodPinMm"][0])
    rocker_bounds = sorted(
        shaft_bearing
        - math.acos(
            (shaft_radius**2 + pin_radius**2 - span**2)
            / (2 * shaft_radius * pin_radius)
        )
        - pin_bearing
        for span in [
            c["rodLengthMm"] - c["eccentricityMm"],
            c["rodLengthMm"] + c["eccentricityMm"],
        ]
    )
    rocker_abs = max(map(abs, rocker_bounds))
    contact_x_abs = c["maximumStationMm"] + math.hypot(*c["contactOffsetMm"])
    rest_y_max = c["arcCentreYMm"] - math.sqrt(c["arcRadiusMm"] ** 2 - contact_x_abs**2)
    rotated_arc_y = []
    for rocker in rocker_bounds:
        stationary_x = max(
            -contact_x_abs, min(contact_x_abs, -c["arcRadiusMm"] * math.sin(rocker))
        )
        for x in [-contact_x_abs, stationary_x, contact_x_abs]:
            rotated_arc_y.append(
                x * math.sin(rocker)
                + (c["arcCentreYMm"] - math.sqrt(c["arcRadiusMm"] ** 2 - x * x))
                * math.cos(rocker)
            )
    offset_y = [
        c["contactOffsetMm"][0] * math.sin(beta)
        + c["contactOffsetMm"][1] * math.cos(beta)
        for beta in [-0.3, 0.2]
    ]
    foot_y_min = c["pivotMm"][1] + min(rotated_arc_y) - max(offset_y)
    foot_y_max = (
        c["pivotMm"][1]
        + contact_x_abs * math.sin(rocker_abs)
        + rest_y_max
        - min(offset_y)
    )
    foot_x_min = (
        c["pivotMm"][0]
        - contact_x_abs
        - rest_y_max * math.sin(rocker_abs)
        - math.hypot(*c["contactOffsetMm"])
    )
    foot_x_max = (
        c["pivotMm"][0]
        + contact_x_abs
        + rest_y_max * math.sin(rocker_abs)
        + math.hypot(*c["contactOffsetMm"])
    )
    initial_top_y_min = foot_y_min + c["barLengthMm"] * math.cos(0.3)
    initial_top_y_max = foot_y_max + c["barLengthMm"]
    top_gap_abs = max(
        abs(initial_top_y_min - c["fulcrumMm"][1]),
        abs(initial_top_y_max - c["fulcrumMm"][1]),
    )
    top_x_min = c["fulcrumMm"][0] - c["leverBarArmMm"]
    top_x_max = c["fulcrumMm"][0] - math.sqrt(c["leverBarArmMm"] ** 2 - top_gap_abs**2)
    horizontal_span = max(top_x_max - foot_x_min, foot_x_max - top_x_min)
    top_y_min = foot_y_min + math.sqrt(c["barLengthMm"] ** 2 - horizontal_span**2)
    native_bank_bounds = {
        "units": "mm",
        "rockerAngleIntervalRad": rocker_bounds,
        "footXIntervalMm": [foot_x_min, foot_x_max],
        "footYIntervalMm": [foot_y_min, foot_y_max],
        "barTopPinYConservativeIntervalMm": [top_y_min, initial_top_y_max],
        "reason": "Exact cam/rod circle existence; rotated circular rocker arc extrema; actual bar beta bracket; lifting-side lever circle branch; fixed bar length.",
        "branch": "Native bisection enters the left-hand lever-circle intersection. This is the authored lifting-side closure, not an alternate right-hand assembly.",
        "sourceVerdict": "None. Source top metal tabs exist above casting; depth/occlusion and source correspondence must be established before asserting a mismatch.",
    }
    parts = {part["path"]: part for part in inventory["inventory"]}
    world_rotation = Rotation.from_rotvec(params[:3]).as_matrix()
    focal = math.exp(params[6])
    phase_count = 71

    def project(world: np.ndarray, frame: int) -> np.ndarray:
        world = np.asarray(world, dtype=float).reshape(-1, 3)
        phase = ((frame - 42) % 142) // 2
        turntable = Rotation.from_rotvec(
            [0, phase * 2 * math.pi / phase_count, 0]
        ).as_matrix()
        point = (
            world - [params[7], 0, params[8]]
        ) @ turntable.T @ world_rotation.T + params[3:6]
        return point[:, :2] / point[:, 2:] * focal + [960, 540]

    measurements = pixels["measurements"]
    for row in measurements:
        row["sourceImage"] = {
            "frameIndex": row["frameIndex"],
            "ptsSeconds": row["frameIndex"] * 1001 / 24000,
            "sha256Bgr8": hashes[row["frameIndex"]],
            "pixelFormat": "bgr8",
            "width": 1920,
            "height": 1080,
            "sourceSha256": pixels["sourceSha256"],
        }

    def errors(rows: list[dict], world: np.ndarray) -> list[dict]:
        return [
            {
                "anchorId": row["anchorId"],
                "frameIndex": row["frameIndex"],
                "observedPixel": row["pixel"],
                "projectedPixel": project(point, row["frameIndex"])[0].tolist(),
                "errorPx": float(
                    np.linalg.norm(project(point, row["frameIndex"])[0] - row["pixel"])
                ),
            }
            for row, point in zip(rows, world, strict=True)
        ]

    paper = parts["ha-harmonic-analyzer/pd-paper-drive/pd-platen-paper-1"]
    paper_rows = [row for row in measurements if row["anchorId"].startswith("paper.")]
    paper_world = np.array(
        [
            [
                paper["bounds"]["max" if "plusX" in row["anchorId"] else "min"][0],
                paper["bounds"]["max" if "top" in row["anchorId"] else "min"][1],
                paper["bounds"]["min"][2],
            ]
            for row in paper_rows
        ]
    )
    paper_fit = [i for i, row in enumerate(paper_rows) if "plusX" in row["anchorId"]]

    def paper_residual(shift: np.ndarray) -> np.ndarray:
        moved = paper_world + [shift[0], 0, 0]
        return np.concatenate(
            [
                project(moved[i], paper_rows[i]["frameIndex"])[0]
                - paper_rows[i]["pixel"]
                for i in paper_fit
            ]
        )

    rack_fit = least_squares(paper_residual, [-0.06])
    paper_errors = errors(paper_rows, paper_world + [rack_fit.x[0], 0, 0])

    crank_axis = np.array(
        parts["ha-harmonic-analyzer/dt-drive-train/dt-crankshaft-1"]["world"][12:15]
    )
    handle_origin = np.array(
        parts["ha-harmonic-analyzer/dt-drive-train/dt-crank-handle-1"]["world"][12:15]
    )
    crank_rows = [
        row for row in measurements if row["anchorId"] == "crank.handle-pivot"
    ]

    def crank_point(angle: float) -> np.ndarray:
        return crank_axis + Rotation.from_rotvec([0, 0, angle]).apply(
            handle_origin - crank_axis
        )

    def crank_residual(angle: np.ndarray) -> np.ndarray:
        return np.concatenate(
            [
                project(crank_point(angle[0]), row["frameIndex"])[0] - row["pixel"]
                for row in crank_rows
            ]
        )

    crank_fit = least_squares(crank_residual, [0])
    crank_errors = errors(
        crank_rows, np.array([crank_point(crank_fit.x[0])] * len(crank_rows))
    )
    crank_axes = {
        row["frameIndex"]: row
        for row in measurements
        if row["anchorId"] == "crank.axis"
    }

    def relative_crank_residual(angle: np.ndarray) -> np.ndarray:
        return np.concatenate(
            [
                (
                    project(crank_point(angle[0]), row["frameIndex"])[0]
                    - project(crank_axis, row["frameIndex"])[0]
                )
                - (np.array(row["pixel"]) - crank_axes[row["frameIndex"]]["pixel"])
                for row in crank_rows
            ]
        )

    relative_crank_fit = least_squares(relative_crank_residual, [0])

    # A cropped upper screw does not make the entire counter unobservable:
    # the genuine native rigid stem's lower free end survives five source views.
    goose = parts["ha-harmonic-analyzer/sm-summing/sm-gooseneck-1"]
    goose_tip = np.array(
        [goose["world"][12], goose["bounds"]["min"][1], goose["world"][14]]
    )
    goose_datum = data["counter"]["nativeGooseneckYMm"] / 1000
    counter_rows = [
        row for row in measurements if row["anchorId"] == "counter.stem-tip"
    ]
    counter_fit_rows = [
        row for row in counter_rows if row["frameIndex"] in (66, 90, 138)
    ]

    def counter_residual(height: np.ndarray) -> np.ndarray:
        point = goose_tip + [0, height[0] - goose_datum, 0]
        return np.concatenate(
            [
                project(point, row["frameIndex"])[0] - row["pixel"]
                for row in counter_fit_rows
            ]
        )

    counter_fit = least_squares(counter_residual, [goose_datum])
    counter_errors = errors(
        counter_rows,
        np.array(
            [goose_tip + [0, counter_fit.x[0] - goose_datum, 0]] * len(counter_rows)
        ),
    )
    # This interval is source compatibility at the contractual pixel limit,
    # not a fabricated confidence interval or proof of an upper screw setting.
    from scipy.optimize import brentq

    def counter_max_error(height: float) -> float:
        point = goose_tip + [0, height - goose_datum, 0]
        return max(
            float(np.linalg.norm(project(point, row["frameIndex"])[0] - row["pixel"]))
            for row in counter_rows
        )

    counter_interval = [
        brentq(
            lambda height: counter_max_error(height) - 38.4,
            counter_fit.x[0] - 0.08,
            counter_fit.x[0],
        ),
        brentq(
            lambda height: counter_max_error(height) - 38.4,
            counter_fit.x[0],
            counter_fit.x[0] + 0.08,
        ),
    ]

    # Relative radii use photographed shaft centres, cancelling the absolute
    # camera translation error. Both sprockets face the same source axis plane.
    sprocket_rows = pixels["sprocketRatioMeasurements"]
    ratio_intervals = []
    for row in sprocket_rows:
        upper_radius = float(
            np.linalg.norm(
                np.subtract(row["upperOuterTopPixel"], row["upperCentrePixel"])
            )
        )
        lower_radius = float(
            np.linalg.norm(
                np.subtract(row["lowerOuterTopPixel"], row["lowerCentrePixel"])
            )
        )
        uncertainty = row["radiusUncertaintyPx"]
        row["upperRadiusPx"] = upper_radius
        row["lowerRadiusPx"] = lower_radius
        row["sourceImage"] = {
            "frameIndex": row["frameIndex"],
            "width": 1920,
            "height": 1080,
            "pixelFormat": "bgr8",
            "sha256Bgr8": hashes[row["frameIndex"]],
            "sourceSha256": pixels["sourceSha256"],
        }
        ratio_intervals.append(
            [
                (upper_radius - uncertainty) / (lower_radius + uncertainty),
                (upper_radius + uncertainty) / (lower_radius - uncertainty),
            ]
        )
    ratio_interval = [
        max(interval[0] for interval in ratio_intervals),
        min(interval[1] for interval in ratio_intervals),
    ]
    small = parts["ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-2"]
    large = parts["ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-1"]
    medium = parts["ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-3"]
    small_radius = (small["bounds"]["max"][1] - small["bounds"]["min"][1]) / 2
    large_radius = (large["bounds"]["max"][1] - large["bounds"]["min"][1]) / 2
    medium_radius = (medium["bounds"]["max"][0] - medium["bounds"]["min"][0]) / 2
    native_radius_ratio = large_radius / small_radius
    gear_ratios = {
        "small-large": native_radius_ratio,
        "medium-medium": 1.0,
        "large-small": 1 / native_radius_ratio,
    }
    radii = {
        "small-large": (large_radius, small_radius),
        "medium-medium": (medium_radius, medium_radius),
        "large-small": (small_radius, large_radius),
    }
    upper_centre = np.array(large["world"][12:15])
    lower_centre = np.array(small["world"][12:15])
    for row in sprocket_rows:
        frame = row["frameIndex"]
        upper_pixel = project(upper_centre, frame)[0]
        lower_pixel = project(lower_centre, frame)[0]
        row["nativeProjectedRadiusRatios"] = {
            name: float(
                np.linalg.norm(
                    project(upper_centre + [0, ru, 0], frame)[0] - upper_pixel
                )
                / np.linalg.norm(
                    project(lower_centre + [0, rl, 0], frame)[0] - lower_pixel
                )
            )
            for name, (ru, rl) in radii.items()
        }
    compatible_gearing = [
        name
        for name in gear_ratios
        if all(
            interval[0] <= row["nativeProjectedRadiusRatios"][name] <= interval[1]
            for row, interval in zip(sprocket_rows, ratio_intervals, strict=True)
        )
    ]
    if len(compatible_gearing) != 1:
        raise ValueError(
            f"Source sprocket ratio does not uniquely identify installed native gearing: {compatible_gearing}"
        )
    gearing = compatible_gearing[0]

    m = data["magnifier"]
    knife = np.array(data["summing"]["knifeMm"]) / 1000
    wheel = np.array(m["wheelCentreMm"]) / 1000
    fixture_rest = np.array(m["fixtureRestMm"]) / 1000
    hook_rest = np.array(m["hookMm"]) / 1000
    clamp_rest = np.array(m["clampRestMm"]) / 1000
    hub_radius, rim_radius = m["hubPitchRadiusMm"] / 1000, m["rimPitchRadiusMm"] / 1000
    contact_z = m["hubTangentMm"][2] / 1000
    dx, dy = hook_rest[:2] - wheel[:2]
    rest_d2 = dx * dx + dy * dy
    rest_azimuth = math.atan2(dy, dx) - math.acos(hub_radius / math.sqrt(rest_d2))
    rest_length = math.sqrt(
        rest_d2 - hub_radius * hub_radius + (hook_rest[2] - contact_z) ** 2
    )

    # The independent visible coordinates are summing tilt, knife-to-clamp radius
    # and collar slide. They do not invent twenty spring settings to realise tilt.
    def output_points(q: np.ndarray) -> dict[str, np.ndarray | float]:
        angle, radius, slide = q
        rotation = Rotation.from_rotvec([0, 0, angle])
        change = radius - m["clampRadiusBandMm"][1] / 1000
        clamp = knife + rotation.apply(clamp_rest + [change, 0, 0] - knife)
        fixture = knife + rotation.apply(
            fixture_rest + [change, slide + 0.004, 0] - knife
        )
        hook = knife + rotation.apply(hook_rest + [change, slide, 0] - knife)
        dx, dy = hook[:2] - wheel[:2]
        d2 = dx * dx + dy * dy
        azimuth = math.atan2(dy, dx) - math.acos(hub_radius / math.sqrt(d2))
        length = math.sqrt(d2 - hub_radius * hub_radius + (hook[2] - contact_z) ** 2)
        wheel_angle = azimuth - rest_azimuth + (length - rest_length) / hub_radius
        pen_travel = -rim_radius * wheel_angle
        pen = np.array([-0.01035, 0.36325 + pen_travel, -0.14365])
        return {
            "magnifier.clamp": clamp,
            "magnifier.fixture": fixture,
            "pen.nib": pen,
            "wheelAngleRad": wheel_angle,
            "penTravelM": pen_travel,
            "hookM": hook,
        }

    output_rows = [
        row
        for row in measurements
        if row["anchorId"] in ("magnifier.clamp", "magnifier.fixture", "pen.nib")
    ]

    def output_residual(q: np.ndarray) -> np.ndarray:
        points = output_points(q)
        return np.concatenate(
            [
                project(points[row["anchorId"]], row["frameIndex"])[0] - row["pixel"]
                for row in output_rows
            ]
        )

    out_fit = least_squares(
        output_residual,
        [0, 0.165, 0],
        bounds=(
            [-0.32, 0.066, m["fixtureOffsetRangeM"][0]],
            [0.32, 0.209, m["fixtureOffsetRangeM"][1]],
        ),
    )
    points = output_points(out_fit.x)
    out_errors = errors(
        output_rows, np.array([points[row["anchorId"]] for row in output_rows])
    )
    spoke_rows = [row for row in measurements if row["anchorId"] == "wheel.spoke-top"]
    hubs = {
        row["frameIndex"]: row for row in measurements if row["anchorId"] == "wheel.hub"
    }

    def relative_spoke_residual(angle: np.ndarray) -> np.ndarray:
        spoke = wheel + Rotation.from_rotvec([0, 0, angle[0]]).apply([0, 0.044, 0])
        return np.concatenate(
            [
                (
                    project(spoke, row["frameIndex"])[0]
                    - project(wheel, row["frameIndex"])[0]
                )
                - (np.array(row["pixel"]) - hubs[row["frameIndex"]]["pixel"])
                for row in spoke_rows
            ]
        )

    spoke_fit = least_squares(
        relative_spoke_residual, [0], bounds=(-math.pi / 6, math.pi / 6)
    )
    spoke_disagreement = (
        float(points["wheelAngleRad"]) - float(spoke_fit.x[0]) + math.pi / 6
    ) % (math.pi / 3) - math.pi / 6
    # Independently exercise the exact native wire consumer, not a copied formula.
    output_script = f"""
import {{createMagnifierPose,solveMagnifier}} from {json.dumps(str(root / "src/magnifier.ts"))};
const pose=createMagnifierPose();
solveMagnifier({{magnifierHookM:{json.dumps(points["hookM"].tolist())},magnifierClampM:[0,0,0],summingAngleRad:{float(out_fit.x[0])}}},pose);
console.log(JSON.stringify(pose,(k,v)=>ArrayBuffer.isView(v)?Array.from(v):v));
"""
    exact_output = json.loads(
        subprocess.run(
            ["bun", "-e", output_script], check=True, capture_output=True, text=True
        ).stdout
    )
    native_wire_error = max(
        abs(exact_output["wheelAngleRad"] - float(points["wheelAngleRad"])),
        abs(exact_output["penTravelM"] - float(points["penTravelM"])),
    )

    witness_script = f"""
import {{createMechanismInput,createMechanismPose,solveMechanism}} from {json.dumps(str(root / "src/mechanics.ts"))};
import {{physicalChannelAngle,paperTravelM}} from {json.dumps(str(root / "src/kinematics.ts"))};
const input=createMechanismInput(),pose=createMechanismPose();
input.crankTurns={float(relative_crank_fit.x[0] / (2 * math.pi))};
input.gearing={json.dumps(gearing)};
// Explicit hypothetical bank, not measured zero amplitudes or twenty phases.
input.amplitudes.fill(0);
for(let j=0;j<20;j++)input.phases[j]=-physicalChannelAngle(input.crankTurns,j);
input.magnification={float(out_fit.x[1] * 1000 / data["summing"]["anchorArmMm"])};
input.setup.counterHeightM={float(counter_fit.x[0])};
input.setup.wireFixtureOffsetM={float(out_fit.x[2])};
input.setup.platenOffsetM={float(rack_fit.x[0])}-paperTravelM(input.crankTurns,input.gearing);
solveMechanism(input,pose);
console.log(JSON.stringify({{input,pose}},(k,v)=>k==='_work'?undefined:ArrayBuffer.isView(v)?Array.from(v):v));
"""
    witness = json.loads(
        subprocess.run(
            ["bun", "-e", witness_script], check=True, capture_output=True, text=True
        ).stdout
    )
    witness["provenance"] = (
        "Chosen complete feasible native witness, not recovered historical physical input. GPU/source checks and full view visibility remain the integrator acceptance gate."
    )
    witness["historicalFullPhysicalInput"] = None
    witness["visiblePoseCompletenessClaimed"] = False
    witness["partOverrides"] = []
    witness["functionalLinkageAssumption"] = {
        "scope": "Known filmed U-shaped connecting-rod junction versus native plate-like head only.",
        "authority": "Explicit user-approved functional equivalence pending a future CAD shape match.",
        "geometryFidelityPassed": False,
        "meaning": "Use genuine native functional linkage and source observations; do not build proxy geometry or waive other geometry/timing discrepancies.",
    }
    witness["unobservedInputFields"] = (
        ["crankTurns", "magnification"]
        + [f"amplitudes[{j}]" for j in range(20)]
        + [f"phases[{j}]" for j in range(20)]
        + [
            "setup.meanLineAngleRad",
            "setup.platenOffsetM",
            "setup.wireFixtureOffsetM",
            "setup.coneSwingRad",
            "setup.pinionCamRad",
            "setup.heldChannelTurns",
            "setup.driveCrankOffsetTurns",
        ]
    )
    witness["constraints"] = [
        {
            "kind": "input-value",
            "field": "gearing",
            "value": gearing,
            "tolerance": 0,
            "evidence": {
                "sourceMeasurements": sprocket_rows,
                "sourceUpperLowerRadiusRatioInterval": ratio_interval,
                "nativeAvailableUpperLowerRadiusRatios": gear_ratios,
            },
        },
        {
            "kind": "input-interval",
            "field": "setup.counterHeightM",
            "minimum": counter_interval[0],
            "maximum": counter_interval[1],
            "evidence": {
                "anchorId": "counter.stem-tip",
                "sourceMeasurements": counter_rows,
                "nativeRigidEndpointRestM": goose_tip.tolist(),
            },
        },
        {
            "kind": "paper-travel",
            "minimumMetres": float(rack_fit.x[0]) - 0.01,
            "maximumMetres": float(rack_fit.x[0]) + 0.01,
            "evidence": {
                "sourceMeasurements": paper_rows,
                "nativePaperBoundsM": paper["bounds"],
                "heldOutCorners": [
                    row for row in paper_errors if "minusX" in row["anchorId"]
                ],
            },
        },
    ]
    witness["coordinateAccounting"] = {
        "totalScalarCoordinates": 51,
        "independentlyInputConstrained": ["gearing", "setup.counterHeightM"],
        "explicitlyUnobserved": witness["unobservedInputFields"],
        "relationConstrainedButIndividuallyUnobserved": [
            "crankTurns",
            "setup.platenOffsetM",
        ],
        "stationOrder": "Physical native instance1..20, harmonic20..1.",
    }

    # Raster line evidence is emitted separately from inverse station identities.
    # A visible repeated stripe is not automatically a numbered physical plate.
    stripe_rows = []
    for region in pixels["stationLineRegions"]:
        frame = region["frameIndex"]
        image = cv2.imread(
            str(evidence / f"mechanics-n{frame}.png"), cv2.IMREAD_GRAYSCALE
        )
        if image is None:
            raise FileNotFoundError(f"mechanics-n{frame}.png")
        for y in [240, 400, 560, 740]:
            x0, _, x1, _ = region["rectSourcePixels"]
            profile = image[y - 2 : y + 3, x0:x1].mean(axis=0)
            peaks = [
                i
                for i in range(1, len(profile) - 1)
                if profile[i] >= profile[i - 1]
                and profile[i] > profile[i + 1]
                and profile[i] > 70
            ]
            stripe_rows.append(
                {
                    "frameIndex": frame,
                    "sourceY": y,
                    "x0": x0,
                    "profileGray": profile.tolist(),
                    "localBrightnessPeaksSourceX": [x0 + i for i in peaks],
                    "identityStatus": "Raster profile only; station identity requires registered native monotone order and occlusion rejection.",
                }
            )
    source_lines = []
    intrinsic = np.array([[focal, 0, 960], [0, focal, 540], [0, 0, 1]])
    for frame in [42, 90, 114]:
        path = evidence / f"mechanics-hough-n{frame}.json"
        if not path.exists():
            continue
        turntable = Rotation.from_rotvec(
            [0, ((frame - 42) % 142) // 2 * 2 * math.pi / 71, 0]
        ).as_matrix()
        transform = world_rotation @ turntable
        translate = params[3:6] - transform @ np.array([params[7], 0, params[8]])
        projection = intrinsic @ np.column_stack([transform, translate])
        for index, segment in enumerate(json.loads(path.read_text())):
            x1, y1, x2, y2 = segment
            line = np.array([y1 - y2, x2 - x1, x1 * y2 - x2 * y1], dtype=float)
            plane = line @ projection
            plane /= np.linalg.norm(plane[:3])
            source_lines.append(
                {
                    "id": f"edge.n{frame}.{index}",
                    "frameIndex": frame,
                    "segmentSourcePixels": segment,
                    "supportPlaneCadMetres": plane.tolist(),
                    "uncertaintyPx": 2,
                    "sourceSha256Bgr8": hashes[frame],
                    "meaning": "Visible straight source edge; any proposed corresponding native straight member must lie in this camera-ray plane.",
                    "nativeStationIdentity": None,
                    "candidateOwners": [
                        "amplitude-bar",
                        "frame-tube",
                        "diagonal-fixed-strut",
                    ],
                    "assignmentRule": "Do not manufacture individual station identities from a nearest predicted stripe. Use multi-view order, endpoints and visibility.",
                }
            )
    loop_mappings = []
    crop_packets = (
        {}
        if args.crops is None
        else {
            p["targetFrameIndex"]: p
            for p in json.loads(args.crops.read_text())["packets"]
        }
    )
    gray = None if args.loop_gray is None else np.load(args.loop_gray, mmap_mode="r")
    views = [] if args.views is None else json.loads(args.views.read_text())["frames"]
    identities = (
        {}
        if args.identities is None
        else {
            p["sourceImage"]["frameIndex"]: p
            for p in json.loads(args.identities.read_text())["sourceFrameMap"]
        }
    )
    for view in views:
        source = view.get("sourceImage")
        if source is None:
            decoded_time = view.get("decodedTimeSeconds")
            if decoded_time is None:
                loop_mappings.append(
                    {
                        "requestedTimeSeconds": view["timeSeconds"],
                        "classification": view["classification"],
                        "mapping": "No explicit decoded PTS/native image identity in legacy view; no source-pixel claim.",
                        "physicalInput": None,
                    }
                )
                continue
            frame = int(round(decoded_time * 24000 / 1001))
            if not 0 <= frame < len(hashes):
                loop_mappings.append(
                    {
                        "requestedTimeSeconds": view["timeSeconds"],
                        "classification": view["classification"],
                        "mapping": "Decoded PTS lies beyond stored native-frame hashes; no source-pixel claim.",
                        "physicalInput": None,
                    }
                )
                continue
            source = {
                "frameIndex": frame,
                "identityFrom": "Explicit decoded PTS and source rational CFR, checked against existing decoded-frame hash array.",
            }
        frame = source["frameIndex"]
        phase = ((frame - 42) % 142) // 2
        reference = 42 + 2 * phase
        packet = crop_packets.get(frame)
        row = {
            "requestedTimeSeconds": view["timeSeconds"],
            "frameIndex": frame,
            "sha256Bgr8": hashes[frame],
            "classification": view["classification"],
            "loopPhase": phase,
            "canonicalFrameIndex": reference,
            "canonicalSha256Bgr8": hashes[reference],
            "physicalInput": None,
        }
        row["nativeFrameIdentityOrigin"] = source.get(
            "identityFrom", "Owner-supplied sourceImage"
        )
        identity = identities.get(frame)
        if identity is not None and identity["phaseAccepted"]:
            phase = identity["referencePhaseIndex"]
            reference = identity["referenceSourceImage"]["frameIndex"]
            row.update(
                {
                    "loopPhase": phase,
                    "canonicalFrameIndex": reference,
                    "canonicalSha256Bgr8": hashes[reference],
                    "sourceIdentityNcc": identity["ncc"],
                    "sourceIdentitySecondBestNcc": identity["secondBestPhaseNcc"],
                    "sourceIdentityMethod": identity["method"],
                }
            )
        if 15 <= frame <= 2698 and gray is not None:
            # Existing decode only; local mechanism ROIs are not another census.
            regions = {
                "bank": (215, 35, 270, 198),
                "wheel": (180, 110, 282, 150),
                "drive": (185, 194, 295, 254),
            }
            row["registeredMechanicalRoiMadGray8"] = {
                name: float(
                    np.mean(
                        np.abs(
                            gray[frame, y0:y1, x0:x1].astype(float)
                            - gray[reference, y0:y1, x0:x1]
                        )
                    )
                )
                for name, (x0, y0, x1, y1) in regions.items()
            }
            row["mapping"] = (
                "Measured source-loop equivalence; stationary internal pose is shared, not guessed crank movement."
            )
        elif (
            0 < frame < 15
            and gray is not None
            and identity is not None
            and identity["phaseAccepted"]
        ):
            reference_gray = gray[reference, 20:265, 170:300].astype(float).ravel()
            target_gray = gray[frame, 20:265, 170:300].astype(float).ravel()
            scale, offset = np.linalg.lstsq(
                np.column_stack([reference_gray, np.ones_like(reference_gray)]),
                target_gray,
                rcond=None,
            )[0]
            row["openingAttenuationScale"] = float(scale)
            row["openingGrayOffset"] = float(offset)
            row["openingBrightnessModelRmsGray8"] = float(
                np.sqrt(np.mean((target_gray - scale * reference_gray - offset) ** 2))
            )
            row["mapping"] = (
                "Attenuated source-loop identity measured from actual gray pixels; individual dark features are not relabelled observed."
            )
        elif packet is not None and "affineSourceToTargetPixels" in packet:
            row["canonicalFrameIndex"] = packet["referenceFrameIndex"]
            row["canonicalSha256Bgr8"] = hashes[packet["referenceFrameIndex"]]
            row["affineSourceToTargetPixels"] = packet["affineSourceToTargetPixels"]
            row["mapping"] = (
                "Measured crop-registration packet, supplied by camera owner; source and target hashes retained."
            )
            row["mappedMeasurements"] = []
            affine = np.array(packet["affineSourceToTargetPixels"])
            for measurement in measurements:
                if ((measurement["frameIndex"] - 42) % 142) // 2 != packet["phase"]:
                    continue
                pixel = affine @ np.array([*measurement["pixel"], 1])
                if 0 <= pixel[0] < 1920 and 0 <= pixel[1] < 1080:
                    row["mappedMeasurements"].append(
                        {
                            "anchorId": measurement["anchorId"],
                            "pixel": pixel.tolist(),
                            "originMeasurementFrame": measurement["frameIndex"],
                            "uncertaintyPxBeforeRegistration": measurement[
                                "uncertaintyPx"
                            ]
                            * float(np.linalg.norm(affine[0, :2])),
                        }
                    )
        elif packet is not None:
            row["mapping"] = (
                "Crop owner records insufficient source registration; no affine or source-pixel propagation is invented."
            )
            row["cropRegistrationError"] = packet["error"]
        else:
            row["mapping"] = (
                "No equality claim for black, crossfade or endcard; source mechanical observables remain attenuated/occluded."
            )
        loop_mappings.append(row)
    result = {
        "videoId": pixels["videoId"],
        "sourceSha256": pixels["sourceSha256"],
        "nativeModelSha256": inventory["sha256"],
        "nativeMechanicsSourceCommit": data["provenance"]["sourceCommit"],
        "registrationInput": str(args.registration),
        "registrationSha256": hashlib.sha256(
            args.registration.read_bytes()
        ).hexdigest(),
        "warning": "CPU-projected inverse constraints only. Not an accepted GPU source comparison and not a recovered full MechanismInput.",
        "measurements": measurements,
        "paperRack": {
            "visibleTravelM": float(rack_fit.x[0]),
            "constraint": "platenOffsetM + paperTravelM(crankTurns,gearing) = visibleTravelM",
            "fitAnchorIds": [paper_rows[i]["anchorId"] for i in paper_fit],
            "errors": paper_errors,
        },
        "wheelSpokes": {
            "wheelAngleRadModuloPiOver3": float(spoke_fit.x[0]),
            "relativePixelResidual": relative_spoke_residual(spoke_fit.x).tolist(),
            "windingCandidateDisagreementRadModuloPiOver3": spoke_disagreement,
            "warning": "Wheel-only sixfold source ambiguity does not establish wire/pen invariance. The winding candidate and measured spoke state require independent GPU/correspondence review.",
        },
        "crank": {
            "angleRadModulo2Pi": float(crank_fit.x[0]),
            "turnsModulo1": float(crank_fit.x[0] / (2 * math.pi)),
            "constraint": "crankTurns modulo 1 only; source turntable is not crank motion. Cone swing held fixed at engaged candidate for this inverse.",
            "errors": crank_errors,
            "relativeAxisAngleRadModulo2Pi": float(relative_crank_fit.x[0]),
            "relativeAxisResidualPx": relative_crank_residual(
                relative_crank_fit.x
            ).tolist(),
        },
        "magnifier": {
            "summingAngleRad": float(out_fit.x[0]),
            "knifeClampRadiusM": float(out_fit.x[1]),
            "magnification": float(
                out_fit.x[1] * 1000 / data["summing"]["anchorArmMm"]
            ),
            "wireFixtureOffsetM": float(out_fit.x[2]),
            "wheelAngleRad": float(points["wheelAngleRad"]),
            "penTravelM": float(points["penTravelM"]),
            "hookM": points["hookM"].tolist(),
            "errors": out_errors,
            "identifiability": "Fitted independent visible coordinates, conditional on released wire winding reference and rod/clamp correspondence; bank inputs remain null.",
        },
        "stripeProfiles": stripe_rows,
        "sourceStraightEdgeInverseConstraints": source_lines,
        "nativeWireConsumerSmokeMaxDelta": native_wire_error,
        "nativeGaugeCounterexample": native["gauge"],
        "requiredViewLoopMappings": loop_mappings,
        "allPhysicalStations": [
            {
                "stationIndex": j,
                "nativePartSuffix": j + 1,
                "harmonic": 20 - j,
                "midplaneM": (
                    data["channel"]["stationZ0Mm"]
                    + data["channel"]["stationPitchMm"] * j
                    + data["channel"]["midplaneOffsetMm"]
                )
                / 1000,
                "amplitude": None,
                "phase": None,
            }
            for j in range(20)
        ],
        "counterConstraint": {
            "counterHeightM": float(counter_fit.x[0]),
            "sourceCompatibleIntervalM": counter_interval,
            "sourcePixelTolerancePx": 38.4,
            "nativeStemTipRestM": goose_tip.tolist(),
            "nativeOriginDatumM": goose_datum,
            "fitFrameIndices": [row["frameIndex"] for row in counter_fit_rows],
            "heldOutFrameIndices": [152, 162],
            "errors": counter_errors,
            "relation": "Sliding native rigid gooseneck lower free-end position measures counterHeightM. Upper screw/seat stay cropped. Exact coupled bank equilibrium and spring catalog remain enforced by the witness solve.",
            "nativeLowerAnchorM": (
                np.array(data["counter"]["anchorMm"]) / 1000
            ).tolist(),
            "nativeUpperEyeXM": data["counter"]["upperEyeXMm"] / 1000,
            "nativeCatalogInsideHookLengthRangeM": [
                data["counter"]["freeLengthMm"] / 1000,
                data["counter"]["maximumLengthMm"] / 1000,
            ],
        },
        "nativeBankContinuousBounds": native_bank_bounds,
        "sprocketRatioConstraint": {
            "sourceRatioInterval": ratio_interval,
            "nativeAvailableRatios": gear_ratios,
            "identifiedGearing": gearing,
            "sourceMeasurements": sprocket_rows,
        },
        "completeFeasibleWitnessCandidate": witness,
        "fullPhysicalInput": None,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "paperRackVisibleTravelM": result["paperRack"]["visibleTravelM"],
                "paperHeldOutMaxPx": max(
                    e["errorPx"] for e in paper_errors if "minusX" in e["anchorId"]
                ),
                "crankRelativeAngleRad": float(relative_crank_fit.x[0]),
                "wheelSpokeAngleRad": float(spoke_fit.x[0]),
                "wheelWindingDisagreementRad": spoke_disagreement,
                "nativeWireConsumerSmokeMaxDelta": native_wire_error,
                "nativeGaugeMaxConsumerPoseDifference": native["gauge"][
                    "maxConsumerPoseDifference"
                ],
                "counterHeightM": float(counter_fit.x[0]),
                "identifiedGearing": gearing,
                "counterHeldOutMaxPx": max(
                    row["errorPx"]
                    for row in counter_errors
                    if row["frameIndex"] in (152, 162)
                ),
                "sourceEdgeConstraints": len(source_lines),
                "viewMappings": len(loop_mappings),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
