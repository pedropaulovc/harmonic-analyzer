"""Blender headless worker — renders comparison pairs from an STL.

Runs INSIDE Blender's bundled Python (no repo imports; stdlib + bpy only):

    blender -b --factory-startup -P blender_worker.py -- job.json

job.json = {
  "stl": "<abs path>",
  "boxes": "<abs path or null>",          # component boxes JSON (assemblies)
  "pairs": [{"id", "camera", "width", "height", "out"}]
}

Camera convention matches cad/scripts/render_compare.py: model space has +Y
up, az 0 / el 0 looks from +Z (SolidWorks Front), +az moves the camera
toward +X. Orthographic only (the SolidWorks pipeline is ortho too). Pairs
with camera.frame_components replicate resolve_framing(): centre on the
matched components' union box, zoom = clamp(0.75 * whole/box, 1, 15).
Background is rendered transparent; the CLI composites it onto white.
"""

import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def camera_axes(az_deg, el_deg, roll_deg=0.0):
    az, el, roll = (math.radians(v) for v in (az_deg, el_deg, roll_deg))
    o = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
    if abs(math.cos(el)) < 1e-9:
        up = (0.0, 0.0, -1.0) if el > 0 else (0.0, 0.0, 1.0)
    else:
        up = (0.0, 1.0, 0.0)
    r = _norm(_cross(up, o))
    u0 = _cross(o, r)
    cr, sr = math.cos(roll), math.sin(roll)
    rr = tuple(cr * a + sr * b for a, b in zip(r, u0))
    uu = tuple(-sr * a + cr * b for a, b in zip(r, u0))
    return rr, uu, o


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _proj_extent(lo, hi, axis):
    vals = [axis[0] * x + axis[1] * y + axis[2] * z
            for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    return max(vals) - min(vals)


def scene_bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = tuple(min(p[i] for p in pts) for i in range(3))
    hi = tuple(max(p[i] for p in pts) for i in range(3))
    return lo, hi


def load_boxes(path, mesh_lo, mesh_hi):
    """Component boxes scaled from metres into mesh units via bbox ratio
    (robust to whatever unit the STL was exported in)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    boxes = [(e["name"], e["box"]) for e in data["boxes"]]
    blo = tuple(min(b[i] for _, b in boxes) for i in range(3))
    bhi = tuple(max(b[i + 3] for _, b in boxes) for i in range(3))
    s = max(hi - lo for hi, lo in zip(mesh_hi, mesh_lo)) / max(
        hi - lo for hi, lo in zip(bhi, blo))
    return [(n, [v * s for v in b]) for n, b in boxes]


def resolve_framing(cam, boxes, mesh_lo, mesh_hi):
    focus = cam.get("frame_components") or []
    target = None
    zoom = float(cam.get("zoom") or 1.0)
    if focus and boxes:
        pats = [re.compile(re.escape(f.replace("_", "-")) + r"(-\d+)?$") for f in focus]
        hits = [b for n, b in boxes if any(p.fullmatch(n.split("/")[-1].lower()) for p in pats)]
        if hits:
            lo = tuple(min(b[i] for b in hits) for i in range(3))
            hi = tuple(max(b[i + 3] for b in hits) for i in range(3))
            r, u, _o = camera_axes(cam.get("az_deg", 0.0), cam.get("el_deg", 0.0),
                                   cam.get("roll_deg", 0.0))
            z = min(_proj_extent(mesh_lo, mesh_hi, r) / max(_proj_extent(lo, hi, r), 1e-9),
                    _proj_extent(mesh_lo, mesh_hi, u) / max(_proj_extent(lo, hi, u), 1e-9))
            zoom = max(1.0, min(0.75 * z, 15.0))
            target = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    if target is None:
        target = tuple((mesh_lo[i] + mesh_hi[i]) / 2 for i in range(3))
    return target, zoom


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.stl_import(filepath=job["stl"])
    scene = bpy.context.scene
    objs = [o for o in scene.objects if o.type == "MESH"]
    if not objs:
        raise RuntimeError(f"no meshes imported from {job['stl']}")
    mesh_lo, mesh_hi = scene_bounds(objs)
    ext = max(hi - lo for hi, lo in zip(mesh_hi, mesh_lo))
    boxes = load_boxes(job["boxes"], mesh_lo, mesh_hi) if job.get("boxes") else []

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.clip_start = ext * 0.001
    cam_data.clip_end = ext * 20
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.render_aa = "11"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"

    for pair in job["pairs"]:
        c = pair["camera"]
        r, u, o = camera_axes(c.get("az_deg", 0.0), c.get("el_deg", 0.0), c.get("roll_deg", 0.0))
        target, zoom = resolve_framing(c, boxes, mesh_lo, mesh_hi)
        # explicit manifest target overrides (mm -> mesh units not resolvable
        # without boxes; framed/centred cases cover the manifest as seeded)
        rot = Matrix(((r[0], u[0], o[0]), (r[1], u[1], o[1]), (r[2], u[2], o[2])))
        m = rot.to_4x4()
        m.translation = Vector(target) + Vector(o) * ext * 3
        cam.matrix_world = m

        w, h = pair["width"], pair["height"]
        scene.render.resolution_x = w
        scene.render.resolution_y = h
        need_w = max(_proj_extent(mesh_lo, mesh_hi, r),
                     _proj_extent(mesh_lo, mesh_hi, u) * w / h)
        cam_data.ortho_scale = need_w * 1.05 / zoom

        scene.render.filepath = pair["out"]
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {pair['id']}")


if __name__ == "__main__":
    main()
