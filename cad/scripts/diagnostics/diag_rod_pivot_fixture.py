"""DESIGNED_CENTERED_LOADPATH: three complete cam/rod/fork/rocker stations.

Not the current production assembly and not a dynamic mate proof. Run through
Main's doit COM-seat wrapper. Installed peened pins only; no rivet blank claim.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _config
from _assembly import place_component
from _common import CAD_ROOT, _early_bound, check, run_build
import channel_axial_spec as axial
import connecting_rod_spec as rod
import cylinder_gear_spec as gear
import rocker_arm_spec as rocker
import rod_pivot_spec as pivot

OUT = CAD_ROOT / "out" / "reports" / "forked-rod-fixture"
RY180 = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _faces(model):
    bodies = _early_bound(model, "IPartDoc").GetBodies2(0, False) or ()
    if len(bodies) != 1:
        raise RuntimeError(f"source requires one native solid, got {len(bodies)}")
    return [
        _early_bound(face, "IFace2")
        for face in _early_bound(bodies[0], "IBody2").GetFaces()
    ]


def _levels(model, x, y):
    levels = []
    for face in _faces(model):
        surface = _early_bound(face.GetSurface(), "ISurface")
        if not surface.IsPlane() or abs(float(surface.PlaneParams[2])) < 0.999999:
            continue
        point = face.GetClosestPointOn(
            x / 1000.0, y / 1000.0, float(surface.PlaneParams[5])
        )
        if (
            math.hypot(float(point[0]) * 1000.0 - x, float(point[1]) * 1000.0 - y)
            < 1e-5
        ):
            levels.append(float(point[2]) * 1000.0)
    return sorted(set(round(value, 7) for value in levels))


def _cylinders(model):
    result = []
    for face in _faces(model):
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface.IsCylinder():
            p = tuple(float(value) for value in surface.CylinderParams)
            result.append(
                {
                    "center": [v * 1000.0 for v in p[:3]],
                    "axis": p[3:6],
                    "diameter": p[6] * 2000.0,
                    "box": [float(v) * 1000.0 for v in face.GetBox()],
                }
            )
    return result


def _axis_cylinders(model, diameter, x, y):
    result = [
        c
        for c in _cylinders(model)
        if abs(c["diameter"] - diameter) < 1e-5
        and abs(c["axis"][2]) > 0.999999
        and math.hypot(c["center"][0] - x, c["center"][1] - y) < 1e-5
    ]
    if not result:
        raise RuntimeError(
            f"missing native cylinder diameter={diameter}, axis={(x, y)}"
        )
    return result


def _bounds(cylinders):
    return min(c["box"][2] for c in cylinders), max(c["box"][5] for c in cylinders)


def _zero_interference(adapter):
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    manager = _early_bound(
        asm.InterferenceDetectionManager, "IInterferenceDetectionMgr"
    )
    manager.TreatCoincidenceAsInterference = False
    manager.TreatSubAssembliesAsComponents = True
    manager.IncludeMultibodyPartInterferences = True
    manager.MakeInterferingPartsTransparent = False
    manager.CreateFastenersFolder = False
    manager.UseTransform = False
    records = []
    try:
        for item in manager.GetInterferences() or ():
            item = _early_bound(item, "IInterference")
            records.append(
                {
                    "components": [
                        str(_early_bound(c, "IComponent2").Name2)
                        for c in item.Components
                    ],
                    "volume_mm3": float(item.Volume) * 1e9,
                    "box_mm": [
                        float(v) * 1000.0
                        for v in _early_bound(
                            item.GetInterferenceBody(), "IBody2"
                        ).GetBodyBox()
                    ],
                }
            )
    finally:
        manager.Done()
        adapter.currentModel.ClearSelection2(True)
        adapter.currentModel.GraphicsRedraw2()
    if any(record["volume_mm3"] > 0.0 for record in records):
        raise RuntimeError(
            f"centered fork fixture has positive interference: {records}"
        )
    return records


async def _capture(adapter, name, view, bounds=None):
    model = adapter.currentModel
    model.ShowNamedView2("", view)
    if bounds is None:
        model.ViewZoomtofit2()
    else:
        model.ViewZoomTo2(*(v / 1000.0 for v in bounds))
    model.GraphicsRedraw2()
    path = OUT / f"{name}.png"
    path.unlink(missing_ok=True)
    check(
        f"capture {name}",
        await adapter.export_image(
            {
                "file_path": str(path),
                "format_type": "png",
                "width": 2000,
                "height": 1600,
                "view_orientation": "current",
            }
        ),
    )
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"missing native capture {path}")
    return str(path)


async def build(adapter):
    OUT.mkdir(parents=True, exist_ok=True)
    check("create centered fork fixture", await adapter.create_assembly())
    pitch = _config.machine("channels", "station_pitch_mm")
    names = {}
    # Central station first: expose the actual gear's eccentric surface before
    # positioning the remaining stations from its measured local cam frame.
    names["gear0"] = await place_component(
        adapter,
        "cylinder-gear",
        [
            0.0,
            -rod.CENTER_DISTANCE - gear.ECCENTRICITY,
            (gear.FACE_WIDTH + gear.CAM_THICKNESS / 2.0),
        ],
        [0, 180, 0],
        RY180,
    )
    asm = _early_bound(adapter.currentModel, "IAssemblyDoc")
    gear_model = _early_bound(
        asm.GetComponentByName(names["gear0"]), "IComponent2"
    ).GetModelDoc2()
    cam = _axis_cylinders(gear_model, gear.CAM_DIA, 0.0, gear.ECCENTRICITY)
    cam_low, cam_high = _bounds(cam)
    cam_center = cam[0]["center"]
    cam_mid = (cam_low + cam_high) / 2.0
    if abs(cam_mid - (gear.FACE_WIDTH + gear.CAM_THICKNESS / 2.0)) > 0.001:
        raise RuntimeError("central gear placement disagrees with native cam midpoint")
    native_channel_mid = gear.FACE_WIDTH / 2.0 - cam_mid
    if abs(native_channel_mid - axial.CHANNEL_MID_DZ) > 0.001:
        raise RuntimeError(
            "production channel datum disagrees with native cam midpoint"
        )
    for station in (-1, 0, 1):
        z = station * pitch
        if station:
            names[f"gear{station}"] = await place_component(
                adapter,
                "cylinder-gear",
                [cam_center[0], -rod.CENTER_DISTANCE - cam_center[1], z + cam_mid],
                [0, 180, 0],
                RY180,
            )
        names[f"rod{station}"] = await place_component(
            adapter, "connecting-rod", [0, -rod.CENTER_DISTANCE, z], [0, 180, 0], RY180
        )
        names[f"rocker{station}"] = await place_component(
            adapter,
            "rocker-arm",
            [rocker.ROD_HOLE_X, -rocker.ROD_HOLE_Y, z],
            [0, 180, 0],
            RY180,
        )
        names[f"pin{station}"] = await place_component(
            adapter, "rod-pivot-pin", [0, 0, z], [0, 0, 0], IDENTITY, config="Default"
        )
    models = {
        key: _early_bound(
            asm.GetComponentByName(names[key]), "IComponent2"
        ).GetModelDoc2()
        for key in ("rod0", "rocker0", "pin0")
    }
    fork_faces = _levels(models["rod0"], 2.0, rod.CENTER_DISTANCE)
    rocker_faces = _levels(
        models["rocker0"], rocker.ROD_HOLE_X + 2.0, rocker.ROD_HOLE_Y
    )
    if len(fork_faces) != 4 or len(rocker_faces) != 2:
        raise RuntimeError(
            f"expected two fork cheeks around one rocker: fork={fork_faces}, rocker={rocker_faces}"
        )
    fork_bores = _axis_cylinders(
        models["rod0"], pivot.ROCKER_BORE_NOMINAL, 0, rod.CENTER_DISTANCE
    )
    if len(fork_bores) != 2:
        raise RuntimeError(
            f"expected separate coaxial bores through both cheeks: {fork_bores}"
        )
    rocker_bore = _axis_cylinders(
        models["rocker0"],
        pivot.ROCKER_BORE_NOMINAL,
        rocker.ROD_HOLE_X,
        rocker.ROD_HOLE_Y,
    )
    journal = _axis_cylinders(models["pin0"], pivot.PIN_JOURNAL_DIA, 0, 0)
    heads = _axis_cylinders(models["pin0"], pivot.PIN_HEAD_DIA, 0, 0)
    if len(heads) != 2:
        raise RuntimeError(f"expected two installed peened heads: {heads}")
    heads.sort(key=lambda c: c["box"][2])
    fork_bores.sort(key=lambda c: c["box"][2])
    rim_radius = (
        max(c["diameter"] for c in fork_bores) + min(c["diameter"] for c in heads)
    ) / 4.0
    rim_faces = _levels(models["pin0"], rim_radius, 0.0)
    if len(rim_faces) != 4:
        raise RuntimeError(f"installed heads lack two flat bearing rims: {rim_faces}")
    journal_low, journal_high = _bounds(journal)
    if max(abs(journal_low - fork_faces[0]), abs(journal_high - fork_faces[3])) > 0.001:
        raise RuntimeError("installed pin grip does not span outer cheek faces")
    measured = dict(
        fork_gap=fork_faces[2] - fork_faces[1],
        rocker=rocker_faces[1] - rocker_faces[0],
        cheek_left=fork_faces[1] - fork_faces[0],
        cheek_right=fork_faces[3] - fork_faces[2],
        head_left=heads[0]["box"][5] - heads[0]["box"][2],
        head_right=heads[1]["box"][5] - heads[1]["box"][2],
        head_dia_left=heads[0]["diameter"],
        head_dia_right=heads[1]["diameter"],
        head_rim_left=rim_faces[1] - rim_faces[0],
        head_rim_right=rim_faces[3] - rim_faces[2],
        ear_bore_left=fork_bores[0]["diameter"],
        ear_bore_right=fork_bores[1]["diameter"],
        bore=rocker_bore[0]["diameter"],
        journal=journal[0]["diameter"],
        station_pitch=pitch,
    )
    fit = pivot.check_measured_joint(**measured)
    ring = _axis_cylinders(models["rod0"], rod.RING_BORE_DIA, 0, 0)
    ring_low, ring_high = _bounds(ring)
    support = {
        "left_mm": -ring_high - (cam_mid - cam_high),
        "right_mm": (cam_mid - cam_low) - (-ring_low),
        "diametral_clearance_mm": ring[0]["diameter"] - cam[0]["diameter"],
    }
    if min(support.values()) <= 0.0:
        raise RuntimeError(f"cam fails full ring support/running clearance: {support}")
    root = [
        c
        for c in _cylinders(models["rod0"])
        if abs(c["axis"][0]) > 0.999999
        and abs(c["diameter"] - 2 * pivot.FORK_ROOT_RADIUS) < 1e-5
    ]
    bottom = [
        c
        for c in _cylinders(models["rocker0"])
        if abs(c["diameter"] - 2 * rocker.R_BOTTOM) < 1e-4
    ]
    if len(root) != 1 or not bottom:
        raise RuntimeError("native fork root/rocker bottom surfaces unavailable")
    half_rocker = measured["rocker"] / 2.0
    root_radius = root[0]["diameter"] / 2.0
    root_y = (
        root[0]["center"][1]
        - rod.CENTER_DISTANCE
        - math.sqrt(root_radius**2 - half_rocker**2)
    )
    bottom_radius = bottom[0]["diameter"] / 2.0
    bottom_y = min(
        bottom[0]["center"][1] - math.sqrt(bottom_radius**2 - x * x) - rocker.ROD_HOLE_Y
        for x in (
            rocker.ROD_HOLE_X - rod.HEAD_WIDTH / 2.0,
            rocker.ROD_HOLE_X + rod.HEAD_WIDTH / 2.0,
        )
    )
    root_clearance = bottom_y - root_y
    if (
        max(
            abs(fork_faces[0] + fork_faces[3]),
            abs(fork_faces[1] + fork_faces[2]),
            abs(rocker_faces[0] + rocker_faces[1]),
        )
        > 0.001
    ):
        raise RuntimeError("fork and rocker native midplanes are not centered at Z=0")
    for bore_face, expected in zip(
        sorted(fork_bores, key=lambda c: c["box"][2]),
        ((fork_faces[0], fork_faces[1]), (fork_faces[2], fork_faces[3])),
        strict=True,
    ):
        if (
            max(
                abs(bore_face["box"][2] - expected[0]),
                abs(bore_face["box"][5] - expected[1]),
            )
            > 0.001
        ):
            raise RuntimeError("fork bore does not span its measured cheek")
    if (
        max(
            abs(heads[0]["box"][5] - fork_faces[0]),
            abs(heads[1]["box"][2] - fork_faces[3]),
        )
        > 0.001
    ):
        raise RuntimeError("installed formed heads do not seat on the outer cheeks")
    if root_clearance <= 0.0:
        raise RuntimeError(f"static rocker intersects fork root: {root_clearance}")
    records = _zero_interference(adapter)
    images = {
        "whole": await _capture(adapter, "whole", 7),
        "end": await _capture(
            adapter, "end", 4, [-12, -20, -pitch - 5, 12, 8, pitch + 5]
        ),
        "joint": await _capture(adapter, "joint", 7, [-10, -17, -6, 10, 6, 6]),
    }
    manager = _early_bound(adapter.currentModel.ModelViewManager, "IModelViewManager")
    section = _early_bound(manager.CreateSectionViewData(), "ISectionViewData")
    section.FirstPlane = asm.FeatureByName("Right Plane")
    section.FirstOffset = 0.0
    section.FirstReverseDirection = False
    section.Redraw = True
    section.ShowSectionCap = True
    section.KeepCapColor = False
    section.GraphicsOnlySection = False
    if not manager.CreateSectionView(section):
        raise RuntimeError("native fork display section invalid")
    images["section"] = await _capture(
        adapter, "section", 4, [-10, -17, -pitch - 5, 10, 6, pitch + 5]
    )
    if not manager.RemoveSectionView():
        raise RuntimeError("failed to remove native display section")
    path = OUT / "forked-rod-fixture.SLDASM"
    path.unlink(missing_ok=True)
    adapter.currentModel.SaveAs3(str(path), 0, 2)
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError("native fork fixture not saved")
    report = OUT / "fit.json"
    report.write_text(
        json.dumps(
            {
                "scope": "DESIGNED_CENTERED_LOADPATH; static three-station fixture, not production assembly or full dynamics",
                "production_integration": "Production shares channel_axial_spec.CHANNEL_MID_DZ; this fixture does not prove production mates or full motion.",
                "native_channel_mid_dz_mm": native_channel_mid,
                "measured_mm": measured,
                "fit": fit,
                "fork_faces_mm": fork_faces,
                "fork_bores": fork_bores,
                "rocker_faces_mm": rocker_faces,
                "pin_journal_mm": [journal_low, journal_high],
                "cam_native": cam,
                "cam_support": support,
                "static_root_clearance_mm": root_clearance,
                "positive_interferences": records,
                "station_pitch_mm": pitch,
                "station_count": 3,
                "images": images,
                "assembly": str(path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {**images, "fit": str(report), "assembly": str(path)}


if __name__ == "__main__":
    sys.exit(run_build(build))
