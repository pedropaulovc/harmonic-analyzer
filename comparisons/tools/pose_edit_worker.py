"""Blender GUI worker for interactive pose editing — see pose_edit.py.

Runs INSIDE Blender (windowed, not -b):

    blender --python pose_edit_worker.py -- job.json
    blender -b --factory-startup --python pose_edit_worker.py -- selftest

The job builds the pair's exact render scene (blender_worker functions), puts
the render camera at the manifest pose, loads the prepared reference as a
half-transparent camera background image, and locks the viewport to the
camera so normal orbit/pan navigation moves the render camera itself. A
"Pose" sidebar panel (N key) exposes ortho scale (zoom), photo opacity and
the Save button; saving decomposes the camera back into the manifest's
az/el/roll + target_mm + zoom fields, which every later re-render reuses.

Camera convention identical to blender_worker.py. Decomposition: o = +Z
column (out vector) -> el = asin(o.y), az = atan2(o.x, o.z); roll compared
against the zero-roll axes; target = the point on the view axis closest to
the scene centre (ortho renders are invariant along the axis); zoom inverts
ortho_scale = need_w * 1.05 / zoom.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_worker as bw  # noqa: E402

STATE: dict = {}


def compose_camera(cam, camera, lo, hi, w, h):
    ext = max(b - a for a, b in zip(lo, hi))
    r, u, o = bw.camera_axes(camera.get("az_deg", 0.0), camera.get("el_deg", 0.0),
                             camera.get("roll_deg", 0.0))
    target, zoom = bw.resolve_framing(camera, STATE["boxes"], lo, hi)
    from mathutils import Matrix
    rot = Matrix(((r[0], u[0], o[0]), (r[1], u[1], o[1]), (r[2], u[2], o[2])))
    m = rot.to_4x4()
    m.translation = Vector(target) + Vector(o) * ext * 3
    cam.matrix_world = m
    need_w = max(bw._proj_extent(lo, hi, r), bw._proj_extent(lo, hi, u) * w / h)
    cam.data.ortho_scale = need_w * 1.05 / zoom


def decompose_camera(cam, lo, hi, w, h) -> dict:
    m = cam.matrix_world
    r = Vector(m.col[0][:3]).normalized()
    o = Vector(m.col[2][:3]).normalized()
    el = math.degrees(math.asin(max(-1.0, min(1.0, o.y))))
    az = math.degrees(math.atan2(o.x, o.z)) if abs(o.y) < 0.999999 else 0.0
    r0, u0, _ = bw.camera_axes(az, el, 0.0)
    roll = math.degrees(math.atan2(r.dot(Vector(u0)), r.dot(Vector(r0))))
    centre = Vector(tuple((a + b) / 2 for a, b in zip(lo, hi)))
    loc = m.translation
    d = -o
    target = loc + (centre - loc).dot(d) * d
    need_w = max(bw._proj_extent(lo, hi, r), bw._proj_extent(lo, hi, Vector(m.col[1][:3]).normalized()) * w / h)
    zoom = need_w * 1.05 / cam.data.ortho_scale
    return {
        "mode": "euler",
        "az_deg": round(az, 2),
        "el_deg": round(el, 2),
        "roll_deg": round(roll, 2),
        "zoom": round(zoom, 4),
        "target_mm": [round(v * 1000.0, 1) for v in target],
    }


def save_pose() -> dict:
    job = STATE["job"]
    vals = decompose_camera(STATE["cam"], STATE["lo"], STATE["hi"],
                            job["width"], job["height"])
    mpath = Path(job["manifest"])
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    pair = next(p for p in manifest["pairs"] if p["id"] == job["pair_id"])
    pair["camera"].update(vals)
    pair["status"] = "aligned"
    mpath.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"POSE SAVED {job['pair_id']}: {vals}", flush=True)
    return vals


class POSE_OT_save(bpy.types.Operator):
    bl_idname = "pose_edit.save"
    bl_label = "Save pose to manifest"

    def execute(self, context):
        vals = save_pose()
        self.report({"INFO"}, f"saved az {vals['az_deg']} el {vals['el_deg']} "
                              f"roll {vals['roll_deg']} zoom {vals['zoom']}")
        return {"FINISHED"}


class POSE_OT_zoom(bpy.types.Operator):
    """Scale the model against the photo (camera ortho scale = saved zoom).

    The plain scroll wheel only magnifies the camera frame — photo and model
    together — which never changes the pose; this operator is bound to
    Ctrl+Wheel and numpad +/- instead."""
    bl_idname = "pose_edit.zoom"
    bl_label = "Pose zoom (model vs photo)"

    factor: bpy.props.FloatProperty(default=1.05)

    def execute(self, context):
        cam = STATE["cam"]
        cam.data.ortho_scale = max(1e-9, cam.data.ortho_scale * self.factor)
        return {"FINISHED"}


def register_zoom_keymap():
    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
    for key, ctrl, factor in (
        ("WHEELUPMOUSE", True, 1 / 1.05),   # zoom in -> model larger
        ("WHEELDOWNMOUSE", True, 1.05),
        ("NUMPAD_PLUS", False, 1 / 1.05),
        ("NUMPAD_MINUS", False, 1.05),
    ):
        kmi = km.keymap_items.new("pose_edit.zoom", key, "PRESS", ctrl=ctrl)
        kmi.properties.factor = factor


class POSE_PT_panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Pose"
    bl_label = "Pose editor"

    def draw(self, context):
        col = self.layout.column()
        job = STATE["job"]
        cam = STATE["cam"]
        col.label(text=job["pair_id"])
        vals = decompose_camera(cam, STATE["lo"], STATE["hi"], job["width"], job["height"])
        col.label(text=f"az {vals['az_deg']}  el {vals['el_deg']}  roll {vals['roll_deg']}")
        col.label(text=f"zoom {vals['zoom']}")
        col.prop(cam.data, "ortho_scale", text="Ortho scale (1/zoom)")
        bg = cam.data.background_images[0]
        col.prop(bg, "alpha", text="Photo opacity")
        col.prop(bg, "display_depth", text="")
        col.operator("pose_edit.save", icon="EXPORT")
        col.label(text="orbit/pan moves the camera")
        col.label(text="Ctrl+Wheel / numpad +-: zoom pose")
        col.label(text="plain wheel: magnify view only")


def setup_viewport():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.region_3d.view_perspective = "CAMERA"
                space.lock_camera = True
                space.shading.type = "SOLID"
                space.shading.color_type = "OBJECT"
                space.shading.light = "STUDIO"
            for region in area.regions:
                if region.type == "UI":
                    with bpy.context.temp_override(area=area, region=region):
                        try:
                            bpy.ops.wm.context_set_string(
                                data_path="area.ui_type", value="VIEW_3D")
                        except Exception:
                            pass
    return None  # one-shot timer


def run_editor(job_path: Path):
    """Defer the build into a timer: operators (stl_import) poll-fail in the
    startup-script context of a GUI session; a timer runs in the live window
    context (with temp_override for the operator calls)."""
    job = json.loads(job_path.read_text(encoding="utf-8"))

    def build():
        win = bpy.context.window_manager.windows[0]
        area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
        with bpy.context.temp_override(window=win, screen=win.screen, area=area):
            try:
                _build_editor(job)
            except Exception:
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                if job.get("smoke"):
                    bpy.ops.wm.quit_blender()
        return None

    bpy.app.timers.register(build, first_interval=0.2)


def _build_editor(job: dict):
    # closing after "Save pose" must not raise Blender's save-file prompt;
    # disable pref auto-save FIRST so neither tweak leaks into the user's
    # persistent Blender preferences on quit
    bpy.context.preferences.use_preferences_save = False
    bpy.context.preferences.view.use_save_prompt = False
    for obj in list(bpy.data.objects):  # drop the default cube/camera/light
        bpy.data.objects.remove(obj, do_unlink=True)
    objs, boxes = (bw.build_assembly(job) if job.get("scene") else bw.build_part(job))
    lo, hi = bw.scene_bounds(objs)
    scene = bpy.context.scene

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "HORIZONTAL"
    ext = max(b - a for a, b in zip(lo, hi))
    cam_data.clip_start = ext * 0.001
    cam_data.clip_end = ext * 20
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x = job["width"]
    scene.render.resolution_y = job["height"]

    STATE.update(job=job, cam=cam, lo=lo, hi=hi, boxes=boxes)
    compose_camera(cam, job["camera"], lo, hi, job["width"], job["height"])

    cam_data.show_background_images = True
    bg = cam_data.background_images.new()
    bg.image = bpy.data.images.load(job["ref"])
    bg.alpha = 0.5
    bg.display_depth = "FRONT"
    bg.frame_method = "FIT"

    bpy.utils.register_class(POSE_OT_save)
    bpy.utils.register_class(POSE_OT_zoom)
    bpy.utils.register_class(POSE_PT_panel)
    register_zoom_keymap()
    setup_viewport()

    if job.get("smoke"):
        def smoke():
            try:
                save_pose()
            except Exception:
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
            bpy.ops.wm.quit_blender()
            return None
        bpy.app.timers.register(smoke, first_interval=1.0)


def selftest() -> None:
    """Round-trip compose -> decompose over a pose grid on a dummy scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mesh = bpy.data.meshes.new("box")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("box", mesh)
    obj.scale = (0.45, 1.3, 0.25)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    lo, hi = bw.scene_bounds([obj])

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    STATE.update(boxes=[])

    w, h = 900, 1400
    worst = 0.0
    for az in (-135.0, -45.0, 0.0, 60.0, 180.0):
        for el in (-20.0, 0.0, 35.0, 75.0):
            for roll in (-10.0, 0.0, 25.0):
                for zoom in (1.0, 2.5):
                    camera = {"az_deg": az, "el_deg": el, "roll_deg": roll,
                              "zoom": zoom, "target_mm": [120.0, -40.0, 310.0]}
                    compose_camera(cam, camera, lo, hi, w, h)
                    got = decompose_camera(cam, lo, hi, w, h)
                    dazi = abs((got["az_deg"] - az + 180) % 360 - 180)
                    pose_err = max(dazi, abs(got["el_deg"] - el),
                                   abs(got["roll_deg"] - roll), abs(got["zoom"] - zoom))
                    # ortho: only the lateral target components are defined;
                    # stored target_mm is rounded to 0.1 mm -> 0.2 mm gate
                    r, u, o = bw.camera_axes(az, el, roll)
                    t_err = 0.0
                    for axis in (r, u):
                        want = sum(a * b for a, b in zip(axis, camera["target_mm"]))
                        have = sum(a * b for a, b in zip(axis, got["target_mm"]))
                        t_err = max(t_err, abs(want - have))
                    worst = max(worst, pose_err, t_err)
                    if pose_err > 0.05 or t_err > 0.2:
                        raise SystemExit(
                            f"SELFTEST FAIL az={az} el={el} roll={roll} zoom={zoom}: "
                            f"{got} pose_err={pose_err} t_err={t_err}")
    print(f"SELFTEST OK (worst error {worst:.4f})")


def main():
    arg = sys.argv[sys.argv.index("--") + 1]
    if arg == "selftest":
        selftest()
        return
    run_editor(Path(arg))


if __name__ == "__main__":
    main()
