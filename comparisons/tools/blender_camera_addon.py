"""Blender add-on: interactively adjust a comparison pair's camera pose.

Loads the harmonic-analyzer (or any manifest model) from the STL/boxes render
cache exactly like the offline renderer, drops the book reference photo behind
the camera, and lets you dial the manifest euler pose (az / el / roll / zoom /
lens) with live viewport feedback — then writes it straight back to
comparisons/manifest.json. The camera placement is shared with the renderer
(blender_worker.aim_camera), so what you frame here is what render_offline.py
reproduces 1:1.

Install: Edit > Preferences > Add-ons > Install... > pick this file > enable
"Harmonic Analyzer: Comparison Camera". Panel: View3D > N-sidebar > "Harmonic".

Workflow:
  1. Set Repo root (defaults to this checkout), pick a Pair, click Build Scene.
     The model loads, the reference photo appears behind the camera, and the
     sliders seed from the pair's current manifest pose.
  2. Adjust az / el / roll / lens — the camera tracks live. Or orbit the
     viewport (camera is view-locked) and click "Capture Orientation From View"
     to read az/el/roll back off the navigated camera.
  3. "Save Pose To Manifest" writes az/el/roll/lens onto the pair. Re-render
     with:  uv run comparisons/tools/render_offline.py --only <id>

Notes
- There is no camera-zoom control on purpose. The camera ALWAYS auto-fits the
  whole-model bbox (zoom pinned to 1.0); SIZE/placement is the manifest "align"
  (scale/dx/dy) applied by composite.py AFTER render — so match only the photo's
  *foreshortening* and silhouette ANGLE here, never its scale. (A non-1.0 camera
  zoom dollies the perspective camera and distorts foreshortening in a way align
  can't undo — the trap this add-on now removes.) To eyeball size against the
  photo, use the viewport-only "Ref scale" or untick View > View Lock > Camera
  to View and scroll-zoom the whole view.
- The reference shown is the prepared comparisons/ref/<id>.jpg (falls back to the
  raw reference). Its aspect sets the render aspect, hence portrait vs landscape.
"""

import json
import math
import os
import sys
from pathlib import Path

import bpy

bl_info = {
    "name": "Harmonic Analyzer: Comparison Camera",
    "author": "harmonic-analyzer",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > Harmonic",
    "description": "Interactively pose a comparison pair's camera and write it to manifest.json",
    "category": "3D View",
}

# blender_worker.py holds the shared camera/scene math (single source of truth
# with the renderer). Blender's "Install Add-on" COPIES this file into its addons
# dir, away from blender_worker.py, so it can't be imported at enable time by
# sibling path. Import it LAZILY from <repo_root>/comparisons/tools at Build Scene
# (repo_root is editable in the panel), and keep enabling the add-on import-free.
bw = None  # blender_worker module, set by _ensure_bw()


def _has_worker(root) -> bool:
    return (Path(root) / "comparisons" / "tools" / "blender_worker.py").exists()


def _default_repo() -> str:
    """Best guess for the checkout: $HARMONIC_REPO, this file's repo (works when
    run from the Text Editor), then the known dev path."""
    env = os.environ.get("HARMONIC_REPO")
    if env and _has_worker(env):
        return env
    here = Path(__file__).resolve()
    candidates = [here.parents[i] for i in range(len(here.parents)) if i <= 3]
    candidates.append(Path(r"C:\src\harmonic-analyzer"))
    for cand in candidates:
        if _has_worker(cand):
            return str(cand)
    return str(here.parents[2] if len(here.parents) > 2 else here.parent)


def _ensure_bw(repo_root: str):
    """Import blender_worker from the repo's comparisons/tools, caching it."""
    global bw
    if bw is not None:
        return bw
    tools = str(Path(bpy.path.abspath(repo_root)).resolve() / "comparisons" / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import blender_worker as _bw  # noqa: E402
    bw = _bw
    return bw


# Built-scene handle (objects/camera/bounds) so slider edits re-aim without a
# rebuild. Keyed once per Build Scene.
_STATE: dict = {}
_ENUM_CACHE: list = []  # keep EnumProperty item strings alive (Blender quirk)


# --------------------------------------------------------------------------- #
# paths / manifest helpers
# --------------------------------------------------------------------------- #
def _repo(props) -> Path:
    return Path(bpy.path.abspath(props.repo_root)).resolve()


def _manifest_path(props) -> Path:
    return _repo(props) / "comparisons" / "manifest.json"


def _load_manifest(props) -> dict:
    return json.loads(_manifest_path(props).read_text(encoding="utf-8"))


def _pair(props, manifest=None) -> dict | None:
    manifest = manifest or _load_manifest(props)
    for p in manifest["pairs"]:
        if p["id"] == props.pair_id:
            return p
    return None


def _ref_image_path(props, pair) -> Path | None:
    """Prefer the prepared ref (cropped/rotated, sets render aspect); else raw."""
    prepared = _repo(props) / "comparisons" / "ref" / f"{pair['id']}.jpg"
    if prepared.exists():
        return prepared
    raw = _repo(props) / pair["reference"]["path"]
    return raw if raw.exists() else None


def _model_geometry(props, model: str):
    """(scene_json, parts_dir) for an assembly, or (stl, None) for a part."""
    out = _repo(props) / "cad" / "out"
    dashed = model.replace("_", "-")
    asm = out / "sldasm" / f"{dashed}.SLDASM"
    if asm.exists():
        return out / "boxes" / f"{dashed}.json", out / "stl"
    return out / "stl" / f"{dashed}.STL", None


# --------------------------------------------------------------------------- #
# camera pose <-> sliders
# --------------------------------------------------------------------------- #
def _camera_spec(props) -> dict:
    """Manifest euler camera dict synthesised from the current sliders.

    zoom is pinned to 1.0: the camera always auto-fits the whole model to the
    frame, and SIZE matching is the post-render 2D ``align`` (scale/dx/dy), never
    a camera dolly — a non-1.0 zoom only distorts perspective in a way align
    can't undo. Use the viewport-only "Ref scale" to eyeball size against the
    photo; match the *angle* here."""
    return {
        "mode": "euler",
        "az_deg": props.az_deg,
        "el_deg": props.el_deg,
        "roll_deg": props.roll_deg,
        "zoom": 1.0,
        "target_mm": None,
        "perspective": {"focal_length_mm": props.focal_mm} if props.perspective else None,
    }


def _aim(props):
    """Re-place the built camera from the sliders (no rebuild)."""
    if not _STATE.get("built"):
        return
    bw.aim_camera(
        _STATE["cam"], _STATE["cam_data"], _camera_spec(props),
        _STATE["boxes"], _STATE["mesh_lo"], _STATE["mesh_hi"],
        _STATE["ext"], _STATE["w"], _STATE["h"],
    )


def _invert_pose(cam_matrix):
    """Blender camera world matrix -> (az_deg, el_deg, roll_deg) in manifest
    convention. Inverse of blender_worker.camera_axes: the camera's local +Z is
    the view axis ``o`` (target->camera), local +X/+Y are right/up."""
    o = cam_matrix.col[2].xyz.normalized()
    rr = cam_matrix.col[0].xyz.normalized()
    el = math.degrees(math.asin(max(-1.0, min(1.0, o.y))))
    az = math.degrees(math.atan2(o.x, o.z))
    # roll: how far the actual right axis is rotated from the roll-0 basis about o
    r0, u0, _o0 = bw.camera_axes(az, el, 0.0)
    cr = rr.x * r0[0] + rr.y * r0[1] + rr.z * r0[2]
    sr = rr.x * u0[0] + rr.y * u0[1] + rr.z * u0[2]
    roll = math.degrees(math.atan2(sr, cr))
    return az, el, roll


# --------------------------------------------------------------------------- #
# property update callbacks
# --------------------------------------------------------------------------- #
def _on_pose_update(self, context):
    _aim(context.scene.hac_camera)


def _on_ref_update(self, context):
    cam_data = _STATE.get("cam_data")
    if not cam_data or not cam_data.background_images:
        return
    props = context.scene.hac_camera
    bg = cam_data.background_images[0]
    cam_data.show_background_images = props.show_ref
    bg.alpha = props.ref_alpha
    bg.scale = props.ref_scale
    bg.offset = (props.ref_off_x, props.ref_off_y)


def _pair_items(self, context):
    _ENUM_CACHE.clear()
    try:
        manifest = _load_manifest(context.scene.hac_camera)
    except Exception:
        _ENUM_CACHE.append(("NONE", "<manifest not found>", ""))
        return _ENUM_CACHE
    for p in manifest["pairs"]:
        _ENUM_CACHE.append((p["id"], p["id"], p.get("notes", "")))
    if not _ENUM_CACHE:
        _ENUM_CACHE.append(("NONE", "<no pairs>", ""))
    return _ENUM_CACHE


# --------------------------------------------------------------------------- #
# properties
# --------------------------------------------------------------------------- #
class HACCameraProps(bpy.types.PropertyGroup):
    repo_root: bpy.props.StringProperty(
        name="Repo root", subtype="DIR_PATH", default=_default_repo(),
    )
    pair_id: bpy.props.EnumProperty(name="Pair", items=_pair_items)

    az_deg: bpy.props.FloatProperty(name="Azimuth", update=_on_pose_update, step=100)
    el_deg: bpy.props.FloatProperty(name="Elevation", min=-90, max=90,
                                    update=_on_pose_update, step=100)
    roll_deg: bpy.props.FloatProperty(name="Roll", update=_on_pose_update, step=100)
    perspective: bpy.props.BoolProperty(name="Perspective", default=True,
                                        update=_on_pose_update)
    focal_mm: bpy.props.FloatProperty(name="Lens (mm)", default=100.0, min=4.0, max=600.0,
                                      update=_on_pose_update)

    show_ref: bpy.props.BoolProperty(name="Show reference", default=True,
                                     update=_on_ref_update)
    ref_alpha: bpy.props.FloatProperty(name="Ref opacity", default=0.5, min=0.0, max=1.0,
                                       update=_on_ref_update)
    ref_scale: bpy.props.FloatProperty(name="Ref scale", default=1.0, min=0.1, max=8.0,
                                       update=_on_ref_update, step=5)
    ref_off_x: bpy.props.FloatProperty(name="Ref shift X", default=0.0,
                                       update=_on_ref_update, step=2)
    ref_off_y: bpy.props.FloatProperty(name="Ref shift Y", default=0.0,
                                       update=_on_ref_update, step=2)


# --------------------------------------------------------------------------- #
# operators
# --------------------------------------------------------------------------- #
def _clear_built():
    """Remove objects/camera/meshes from a previous Build Scene."""
    for obj in _STATE.get("objs", []) + ([_STATE["cam"]] if _STATE.get("cam") else []):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except (ReferenceError, RuntimeError):
            pass
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    _STATE.clear()


def _set_view_to_camera(context, cam):
    """Look through the camera and lock navigation to it (so orbit moves it)."""
    for area in context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.region_3d.view_perspective = "CAMERA"
        space.lock_camera = True
        # Workbench-like shading so the viewport resembles the render.
        sh = space.shading
        sh.type = "SOLID"
        sh.light = "STUDIO"
        sh.color_type = "OBJECT"
        sh.show_backface_culling = False
        space.show_object_viewport_camera = True
        break


class HAC_OT_build_scene(bpy.types.Operator):
    bl_idname = "hac.build_scene"
    bl_label = "Build Scene"
    bl_description = "Load the pair's model + reference and seed the pose sliders"

    def execute(self, context):
        props = context.scene.hac_camera
        if not _has_worker(bpy.path.abspath(props.repo_root)):
            self.report({"ERROR"}, f"no comparisons/tools/blender_worker.py under "
                                   f"Repo root {props.repo_root!r} — fix Repo root")
            return {"CANCELLED"}
        try:
            _ensure_bw(props.repo_root)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"import blender_worker failed: {exc}")
            return {"CANCELLED"}
        manifest = _load_manifest(props)
        pair = _pair(props, manifest)
        if pair is None:
            self.report({"ERROR"}, f"pair {props.pair_id!r} not in manifest")
            return {"CANCELLED"}

        _clear_built()
        scene_json, parts_dir = _model_geometry(props, pair["model"])
        if not scene_json.exists():
            self.report({"ERROR"}, f"{scene_json} missing — run cad/scripts/export_models.py")
            return {"CANCELLED"}

        if parts_dir is not None:
            objs, boxes = bw.build_assembly({"scene": str(scene_json), "parts_dir": str(parts_dir)})
        else:
            objs, boxes = bw.build_part({"stl": str(scene_json), "rgb": None})
        mesh_lo, mesh_hi = bw.scene_bounds(objs)
        ext = max(hi - lo for hi, lo in zip(mesh_hi, mesh_lo))

        cam_data = bpy.data.cameras.new("hac_cam")
        cam_data.clip_start = ext * 0.001
        cam_data.clip_end = ext * 40
        cam = bpy.data.objects.new("hac_cam", cam_data)
        context.scene.collection.objects.link(cam)
        context.scene.camera = cam

        # Reference photo behind the camera; its aspect drives the render aspect.
        w, h = 1600, 1000
        ref_path = _ref_image_path(props, pair)
        if ref_path is not None:
            img = bpy.data.images.load(str(ref_path), check_existing=True)
            w, h = img.size
            cam_data.show_background_images = props.show_ref
            bg = cam_data.background_images.new()
            bg.image = img
            bg.alpha = props.ref_alpha
            bg.scale = props.ref_scale
            bg.offset = (props.ref_off_x, props.ref_off_y)
            bg.display_depth = "FRONT"
            bg.frame_method = "FIT"

        _STATE.update(built=True, objs=objs, boxes=boxes, cam=cam, cam_data=cam_data,
                      mesh_lo=mesh_lo, mesh_hi=mesh_hi, ext=ext, w=w, h=h)

        # Seed sliders from the pair's stored pose (fires _aim via callbacks).
        c = pair["camera"]
        props.az_deg = float(c.get("az_deg", 0.0))
        props.el_deg = float(c.get("el_deg", 0.0))
        props.roll_deg = float(c.get("roll_deg", 0.0))
        persp = c.get("perspective")
        props.perspective = bool(persp)
        if persp and persp.get("focal_length_mm"):
            props.focal_mm = float(persp["focal_length_mm"])
        _aim(props)
        _set_view_to_camera(context, cam)
        self.report({"INFO"}, f"built {pair['model']} for {pair['id']} ({w}x{h})")
        return {"FINISHED"}


class HAC_OT_capture_view(bpy.types.Operator):
    bl_idname = "hac.capture_view"
    bl_label = "Capture Orientation From View"
    bl_description = "Read az/el/roll from the navigated camera (lens kept)"

    def execute(self, context):
        if not _STATE.get("built"):
            self.report({"ERROR"}, "Build Scene first")
            return {"CANCELLED"}
        props = context.scene.hac_camera
        az, el, roll = _invert_pose(_STATE["cam"].matrix_world)
        props.az_deg, props.el_deg, props.roll_deg = az, el, roll
        _aim(props)  # re-centre framing on the captured angle
        self.report({"INFO"}, f"az {az:.1f}  el {el:.1f}  roll {roll:.1f}")
        return {"FINISHED"}


class HAC_OT_save_manifest(bpy.types.Operator):
    bl_idname = "hac.save_manifest"
    bl_label = "Save Pose To Manifest"
    bl_description = "Write az/el/roll/zoom/lens onto this pair in manifest.json"

    def execute(self, context):
        props = context.scene.hac_camera
        path = _manifest_path(props)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        pair = next((p for p in manifest["pairs"] if p["id"] == props.pair_id), None)
        if pair is None:
            self.report({"ERROR"}, f"pair {props.pair_id!r} not in manifest")
            return {"CANCELLED"}
        c = pair.setdefault("camera", {})
        c["mode"] = "euler"
        c["az_deg"] = round(props.az_deg, 2)
        c["el_deg"] = round(props.el_deg, 2)
        c["roll_deg"] = round(props.roll_deg, 2)
        c["zoom"] = 1.0  # camera always auto-fits; size is the post-render 2D align
        c["perspective"] = {"focal_length_mm": round(props.focal_mm, 2)} if props.perspective else None
        c.setdefault("target_mm", None)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.report({"INFO"}, f"saved pose -> {path.name} ({props.pair_id})")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# panel
# --------------------------------------------------------------------------- #
class HAC_PT_panel(bpy.types.Panel):
    bl_label = "Comparison Camera"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Harmonic"

    def draw(self, context):
        props = context.scene.hac_camera
        col = self.layout.column(align=True)
        col.prop(props, "repo_root")
        col.prop(props, "pair_id")
        col.operator(HAC_OT_build_scene.bl_idname, icon="IMPORT")

        box = self.layout.box()
        box.label(text="Pose")
        box.prop(props, "az_deg")
        box.prop(props, "el_deg")
        box.prop(props, "roll_deg")
        row = box.row(align=True)
        row.prop(props, "perspective", toggle=True)
        sub = row.row(align=True)
        sub.enabled = props.perspective
        sub.prop(props, "focal_mm")
        box.operator(HAC_OT_capture_view.bl_idname, icon="CAMERA_DATA")

        box = self.layout.box()
        box.label(text="Reference")
        box.prop(props, "show_ref")
        box.prop(props, "ref_alpha", slider=True)
        box.prop(props, "ref_scale", slider=True)
        row = box.row(align=True)
        row.prop(props, "ref_off_x")
        row.prop(props, "ref_off_y")

        self.layout.operator(HAC_OT_save_manifest.bl_idname, icon="FILE_TICK")


_CLASSES = (
    HACCameraProps,
    HAC_OT_build_scene,
    HAC_OT_capture_view,
    HAC_OT_save_manifest,
    HAC_PT_panel,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hac_camera = bpy.props.PointerProperty(type=HACCameraProps)


def unregister():
    _clear_built()
    del bpy.types.Scene.hac_camera
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
