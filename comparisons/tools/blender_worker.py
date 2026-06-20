"""Blender headless worker — renders comparison pairs from the STL cache.

Runs INSIDE Blender's bundled Python (no repo imports; stdlib + bpy only):

    blender -b --factory-startup -P blender_worker.py -- job.json

job.json (part model):
  {"stl": "<abs path>", "rgb": [r,g,b] | null,
   "pairs": [{"id", "camera", "width", "height", "out"}]}

job.json (assembly model):
  {"parts_dir": "<abs dir of per-part STLs>",
   "scene": "<abs path of boxes/scene JSON>",      # boxes + components
   "pairs": [...]}

Geometry is exported in millimetres, untranslated (export_models.py sets
swExportStlUnits/swSTLDontTranslateToPositive); the scene-graph transforms
and boxes are scaled to the same millimetres, so component transforms
(IMathTransform.ArrayData: row-vector convention, 9 rotation + 3
translation + scale) place instanced part meshes exactly in assembly
space, and component boxes need no normalisation. (Framing is unit-agnostic
anyway — it derives from bbox ratios — but mesh and transform units must
agree, and now both are mm.)

Camera convention matches cad/scripts/render_compare.py: model space has +Y
up, az 0 / el 0 looks from +Z (SolidWorks Front), +az moves the camera
toward +X. Orthographic by default; a pair whose camera.perspective is set
(focal_length_mm = the book's 100 mm lens, or a raw object_sizes_away) renders
with a matching perspective camera — see lens_params(), which orients the DX
long edge to the canvas so both engines reproduce the same lens.
Pairs with camera.frame_components replicate resolve_framing(): centre on the
matched components' union box, zoom = clamp(0.75 * whole/box, 1, 15).
Workbench renders with per-object colours (the components' appearance RGB);
background is transparent and the CLI composites it onto white.
"""

import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

DEFAULT_RGB = (0.55, 0.55, 0.55)

# Book camera (references/.../31_Notes_on_the_Design): Nikon D60 dSLR, APS-C
# "DX" sensor 23.6 x 15.8 mm, Tokina 100 mm macro. Blender is a true
# focal-length camera, so a perspective pair renders the real lens: lens =
# focal_length_mm with the DX long edge (23.6 mm) oriented to the canvas long
# edge -- a portrait canvas (the tall machine, ch30 ~675x1600) rotates the
# camera just as the photographer did. render_compare.py references the same
# long edge (ObjectSizesAway = f / long_edge), so both engines reproduce the
# lens's long-axis angle of view (~13.5 deg at 100 mm).
DX_SENSOR_MM = (23.6, 15.8)
DX_SENSOR_LONG_MM = DX_SENSOR_MM[0]              # 23.6 mm -- long edge
DEFAULT_OBJECT_SIZES_AWAY = 4.0


def lens_params(c):
    """(focal_length_mm, sensor_long_mm) for a perspective pair, or None (ortho).

    A focal_length_mm spec maps straight to a real lens on the DX long edge; a
    raw object_sizes_away (distance/size) is the equivalent f = osa * long_edge.
    The long edge is the reference dimension in both engines (see module note).
    """
    p = c.get("perspective")
    if not p:
        return None
    s = DX_SENSOR_LONG_MM
    if p.get("focal_length_mm") is not None:
        return float(p["focal_length_mm"]), float(p.get("sensor_dim_mm", s))
    return float(p.get("object_sizes_away", DEFAULT_OBJECT_SIZES_AWAY)) * s, s


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


def sw_matrix(xform):
    """SolidWorks ArrayData (row-vector convention) -> Blender 4x4."""
    a, b, c, d, e, f, g, h, i, tx, ty, tz, s = xform[:13]
    m = Matrix((
        (a * s, d * s, g * s, tx),
        (b * s, e * s, h * s, ty),
        (c * s, f * s, i * s, tz),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m


def import_stl(path):
    before = set(bpy.data.objects)
    bpy.ops.wm.stl_import(filepath=str(path))
    new = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
    if not new:
        raise RuntimeError(f"no mesh imported from {path}")
    return new[0]


def build_part(job):
    obj = import_stl(job["stl"])
    obj.color = (*(job.get("rgb") or DEFAULT_RGB), 1.0)
    return [obj], []


def build_assembly(job):
    scene_data = json.loads(Path(job["scene"]).read_text(encoding="utf-8"))
    components = scene_data.get("components") or []
    if not components:
        raise RuntimeError(f"no components in {job['scene']} — re-run export_models.py")
    parts_dir = Path(job["parts_dir"])
    meshes = {}
    objs = []
    for comp in components:
        key = comp.get("mesh") or comp["part"]
        if key not in meshes:
            seed = import_stl(parts_dir / f"{key}.STL")
            meshes[key] = seed.data
            bpy.data.objects.remove(seed)
        obj = bpy.data.objects.new(comp["name"], meshes[key])
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = sw_matrix(comp["xform"])
        obj.color = (*(comp.get("rgb") or DEFAULT_RGB), 1.0)
        objs.append(obj)
    boxes = [(e["name"], e["box"]) for e in scene_data.get("boxes", [])]
    return objs, boxes


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
    objs, boxes = build_assembly(job) if job.get("scene") else build_part(job)
    scene = bpy.context.scene
    mesh_lo, mesh_hi = scene_bounds(objs)
    ext = max(hi - lo for hi, lo in zip(mesh_hi, mesh_lo))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.clip_start = ext * 0.001
    cam_data.clip_end = ext * 40        # perspective pulls the eye back ~f/long_edge*frame
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.render_aa = "11"
    # Display colours as-authored: factory-startup defaults to AgX, a film
    # tone-map that desaturates the part RGBs (washed-out vs SolidWorks, which
    # shows plain sRGB). Standard keeps the appearance colours faithful.
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"

    for pair in job["pairs"]:
        c = pair["camera"]
        r, u, o = camera_axes(c.get("az_deg", 0.0), c.get("el_deg", 0.0), c.get("roll_deg", 0.0))
        target, zoom = resolve_framing(c, boxes, mesh_lo, mesh_hi)

        w, h = pair["width"], pair["height"]
        scene.render.resolution_x = w
        scene.render.resolution_y = h
        need_w = max(_proj_extent(mesh_lo, mesh_hi, r),
                     _proj_extent(mesh_lo, mesh_hi, u) * w / h)
        frame_w = need_w * 1.05 / zoom  # world width that fills the frame at target

        # Orthographic unless the pair requests a lens. For perspective, orient
        # the DX long edge (sensor_long) to the canvas long edge so a portrait
        # canvas rotates the camera like the book shot, then pull the eye back
        # so the long-edge world span fills the frame: distance = fit_span *
        # lens / sensor_long. That keeps the same silhouette fit as ortho at the
        # target plane (near parts enlarged) while the long-axis angle of view
        # matches the real f-mm lens (~13.5 deg at 100 mm on 23.6 mm).
        lp = lens_params(c)
        if lp is None:
            cam_data.type = "ORTHO"
            cam_data.sensor_fit = "HORIZONTAL"
            cam_data.ortho_scale = frame_w
            cam_dist = ext * 3
        else:
            lens_mm, sensor_long = lp
            cam_data.type = "PERSP"
            cam_data.lens = lens_mm
            if h >= w:  # portrait: long edge runs vertically
                cam_data.sensor_fit = "VERTICAL"
                cam_data.sensor_height = sensor_long
                fit_span = frame_w * h / w  # world height that fills the frame
            else:       # landscape: long edge runs horizontally
                cam_data.sensor_fit = "HORIZONTAL"
                cam_data.sensor_width = sensor_long
                fit_span = frame_w          # world width that fills the frame
            cam_dist = fit_span * lens_mm / sensor_long

        rot = Matrix(((r[0], u[0], o[0]), (r[1], u[1], o[1]), (r[2], u[2], o[2])))
        m = rot.to_4x4()
        m.translation = Vector(target) + Vector(o) * cam_dist
        cam.matrix_world = m

        scene.render.filepath = pair["out"]
        bpy.ops.render.render(write_still=True)
        print(f"RENDERED {pair['id']}")


if __name__ == "__main__":
    main()
