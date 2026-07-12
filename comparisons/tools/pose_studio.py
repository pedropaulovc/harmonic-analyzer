# /// script
# requires-python = ">=3.11"
# ///
"""pose_studio.py — interactive Blender studio for posing a comparison pair's
camera against its book reference, writing the euler pose to
``comparisons/manifest.json``.

One file, two roles
-------------------
* **Launcher** (plain uv/system Python, no ``bpy``): finds ``blender.exe`` and
  relaunches itself *inside* Blender's GUI with the same arguments::

      uv run comparisons/tools/pose_studio.py --pair ch30-p003

  ``--pair`` matches a manifest pair id (full ``harmonic_analyzer--ch30-p003-img01``
  or any substring). ``--repo`` / ``--blender`` / ``$HARMONIC_BLENDER`` override.

* **Studio** (inside Blender, ``bpy`` present): builds the model + reference
  scene, registers the "Harmonic" N-panel, and drives
  ``blender_worker.aim_camera`` live from the sliders.

Why not the old add-on
----------------------
The retired ``blender_camera_addon.py`` *locked the viewport to the camera*
(``space.lock_camera = True``), which hijacked pan/zoom/rotate and gave no way
to zoom into the reference for fine alignment. This tool leaves the view
**unlocked**: native orbit/pan work, and scroll-zoom *inside camera view*
magnifies the framed reference + model together (zoom in to check pixel
alignment, zoom back out) without moving the camera. Toggle "Lock camera to
view" only when you want navigation to fly the camera, then "Capture from view"
bakes the result back into the euler pose.

Pose model (round-trips 1:1 with render_offline.py, all via
``blender_worker.aim_camera``):
    az / el / roll  ......  camera orientation (3)
    target xyz      ......  framing centre / truck-pedestal (3)   -> the 6 axes
    zoom            ......  framing tightness
    lens (mm)       ......  perspective focal length (or ortho)
Reference overlay: opacity, scale, offset x/y.
"""

import sys


def _in_blender() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except ModuleNotFoundError:
        return False


# --------------------------------------------------------------------------- #
# launcher (plain Python) — relaunch inside Blender's GUI
# --------------------------------------------------------------------------- #
def _launch() -> None:
    import argparse
    import os
    import subprocess
    from pathlib import Path

    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description="Launch the Blender pose studio.")
    ap.add_argument("--pair", default="", help="manifest pair id or substring")
    ap.add_argument("--repo", default=str(here.parents[2]), help="repo checkout root")
    ap.add_argument(
        "--blender",
        default=os.environ.get(
            "HARMONIC_BLENDER",
            r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        ),
        help="path to blender.exe ($HARMONIC_BLENDER)",
    )
    ap.add_argument("--shots", default="", help="verify: relaunch headed, capture "
                    "the camera<->free toggle screenshots to this dir, then quit")
    args = ap.parse_args()

    blender = Path(args.blender)
    if not blender.exists():
        raise SystemExit(
            f"blender not found: {blender}\n"
            f"pass --blender <path> or set HARMONIC_BLENDER"
        )
    # --factory-startup: skip the user's startup.blend AND addons, so the studio
    # opens the same pristine factory scene render_offline.py renders (it also
    # passes --factory-startup) — no stray user-startup objects to pose against,
    # and the retired blender_camera_addon can't load and collide.
    cmd = [
        str(blender), "--factory-startup", "--python", str(here), "--",
        "--pair", args.pair, "--repo", str(Path(args.repo).resolve()),
    ]
    if args.shots:
        cmd += ["--shots", str(Path(args.shots).resolve())]
    print("launching:", " ".join(cmd), flush=True)
    raise SystemExit(subprocess.call(cmd))


if not _in_blender():
    _launch()


# =========================================================================== #
# everything below runs INSIDE Blender
# =========================================================================== #
import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_worker as bw  # noqa: E402

# Built-scene handle: objects/camera/bounds so slider edits re-aim without a
# full rebuild. Populated by HAC_OT_build_scene.
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
    return next((p for p in manifest["pairs"] if p["id"] == props.pair_id), None)


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
def _bbox_center() -> tuple[float, float, float]:
    lo, hi = _STATE["mesh_lo"], _STATE["mesh_hi"]
    return tuple((lo[i] + hi[i]) / 2 for i in range(3))


def _camera_spec(props) -> dict:
    """Manifest euler camera dict synthesised from the current sliders.

    ``target_mm`` is emitted only when the user has freed the target off the
    bbox centre — otherwise it stays null so ``aim_camera`` auto-centres exactly
    as it did historically (and the render is byte-identical)."""
    target = [props.target_x, props.target_y, props.target_z] if props.free_target else None
    return {
        "mode": "euler",
        "az_deg": props.az_deg,
        "el_deg": props.el_deg,
        "roll_deg": props.roll_deg,
        "zoom": props.zoom,
        "target_mm": target,
        "perspective": {"focal_length_mm": props.focal_mm} if props.perspective else None,
    }


def _aim(props) -> None:
    """Re-place the built camera from the sliders (no rebuild)."""
    if not _STATE.get("built"):
        return
    target, _zoom, cam_dist = bw.aim_camera(
        _STATE["cam"], _STATE["cam_data"], _camera_spec(props),
        _STATE["boxes"], _STATE["mesh_lo"], _STATE["mesh_hi"],
        _STATE["ext"], _STATE["w"], _STATE["h"],
    )
    _STATE["target"], _STATE["cam_dist"] = target, cam_dist


def _apply_camera_to_free(space) -> None:
    """Copy ``hac_cam``'s eye position, orientation and FOV onto the free-orbit
    view fields (``RegionView3D.view_rotation/location/distance`` + ``space.lens``).

    Used when LEAVING camera view so the free view starts exactly where the camera
    is — no jump. Matching eye + orientation removes the position/scale shift; the
    lens match makes the projected FOV agree. The free viewport meters its lens on
    a 36 mm sensor along its fit axis, whereas ``aim_camera`` meters the real lens
    on the DX long edge (``sensor_long``) — hence the 36/long scale."""
    if os.environ.get("HARMONIC_NO_SYNC") or not _STATE.get("built"):  # baseline: no-op
        return
    cam, cam_data = _STATE["cam"], _STATE["cam_data"]
    rv3d = space.region_3d
    dist = float(_STATE.get("cam_dist") or _STATE["ext"] * 3)
    quat = cam.matrix_world.to_quaternion()
    rv3d.view_rotation = quat
    rv3d.view_distance = dist
    rv3d.view_location = cam.matrix_world.translation - (quat @ Vector((0.0, 0.0, dist)))
    if cam_data.type == "PERSP":
        sensor_long = (cam_data.sensor_height if cam_data.sensor_fit == "VERTICAL"
                       else cam_data.sensor_width)
        space.lens = cam_data.lens * 36.0 / max(sensor_long, 1e-6)
    # Match the PROJECTION too: a fallback exit (View menu / gizmo, or if the
    # keymap loses) can restore an ORTHO free view, which would render a
    # perspective camera orthographically — a visible scale jump. Force the
    # viewport's projection to the camera's regardless of what was restored.
    rv3d.view_perspective = "ORTHO" if cam_data.type == "ORTHO" else "PERSP"


def _invert_pose(cam_matrix):
    """Blender camera world matrix -> (az, el, roll) in manifest convention.

    Inverse of blender_worker.camera_axes: the camera's local +Z is the view
    axis ``o`` (target->camera), local +X/+Y are right/up."""
    o = cam_matrix.col[2].xyz.normalized()
    rr = cam_matrix.col[0].xyz.normalized()
    el = math.degrees(math.asin(max(-1.0, min(1.0, o.y))))
    az = math.degrees(math.atan2(o.x, o.z))
    r0, u0, _o0 = bw.camera_axes(az, el, 0.0)
    cr = rr.x * r0[0] + rr.y * r0[1] + rr.z * r0[2]
    sr = rr.x * u0[0] + rr.y * u0[1] + rr.z * u0[2]
    roll = math.degrees(math.atan2(sr, cr))
    return az, el, roll


def _view3d_space(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            return area.spaces.active
    return None


# Last-seen viewport projection, so the watcher fires only on the CAMERA->free EDGE
# (not continuously — that would yank the user back while they orbit).
_LAST_PERSP: dict = {"v": None}


def _camera_exit_watcher():
    """Persistent poll: whenever the viewport LEAVES camera view — by any route
    (Numpad 0, the View menu, the gizmo) — drop the free view onto the camera's
    exact vantage so there's no jump. This is the correctness guarantee that does
    NOT depend on the Numpad-0 keymap override winning; the override just makes it
    flicker-free. Only acts on the transition edge, never mid-orbit."""
    if not _STATE.get("built"):
        return 0.2
    space = _view3d_space(bpy.context)
    if space is None:
        return 0.2
    cur = space.region_3d.view_perspective
    prev = _LAST_PERSP["v"]
    _LAST_PERSP["v"] = cur
    if prev == "CAMERA" and cur != "CAMERA":
        _apply_camera_to_free(space)
    return 0.08


# --------------------------------------------------------------------------- #
# property update callbacks
# --------------------------------------------------------------------------- #
def _on_pose_update(self, context):
    _aim(context.scene.hac_pose)


def _on_target_update(self, context):
    props = context.scene.hac_pose
    if not props.free_target:
        props.free_target = True  # nudging the target frees it off bbox centre
    _aim(props)


def _on_lock_update(self, context):
    space = _view3d_space(context)
    if space is not None:
        space.lock_camera = self.lock_to_view


def _on_ref_update(self, context):
    cam_data = _STATE.get("cam_data")
    if not cam_data or not cam_data.background_images:
        return
    props = context.scene.hac_pose
    bg = cam_data.background_images[0]
    cam_data.show_background_images = props.show_ref
    bg.alpha = props.ref_alpha
    bg.scale = props.ref_scale
    bg.offset = (props.ref_off_x, props.ref_off_y)


def _pair_items(self, context):
    _ENUM_CACHE.clear()
    try:
        manifest = _load_manifest(context.scene.hac_pose)
    except Exception:  # noqa: BLE001
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
class HACPoseProps(bpy.types.PropertyGroup):
    repo_root: bpy.props.StringProperty(name="Repo root", subtype="DIR_PATH", default="")
    pair_id: bpy.props.EnumProperty(name="Pair", items=_pair_items)

    # camera orientation
    az_deg: bpy.props.FloatProperty(name="Azimuth", update=_on_pose_update, step=100)
    el_deg: bpy.props.FloatProperty(name="Elevation", min=-90, max=90,
                                    update=_on_pose_update, step=100)
    roll_deg: bpy.props.FloatProperty(name="Roll", update=_on_pose_update, step=100)

    # camera target (framing centre) — the other 3 axes
    free_target: bpy.props.BoolProperty(name="Free target", default=False)
    target_x: bpy.props.FloatProperty(name="Target X", update=_on_target_update, step=100)
    target_y: bpy.props.FloatProperty(name="Target Y", update=_on_target_update, step=100)
    target_z: bpy.props.FloatProperty(name="Target Z", update=_on_target_update, step=100)

    zoom: bpy.props.FloatProperty(name="Zoom", default=1.0, min=1.0, max=15.0,
                                  update=_on_pose_update, step=5)
    perspective: bpy.props.BoolProperty(name="Perspective", default=True,
                                        update=_on_pose_update)
    focal_mm: bpy.props.FloatProperty(name="Lens (mm)", default=100.0, min=4.0, max=600.0,
                                      update=_on_pose_update)

    lock_to_view: bpy.props.BoolProperty(
        name="Lock camera to view", default=False, update=_on_lock_update,
        description="When ON, navigating the viewport flies the camera. When OFF "
                    "(default), scroll-zoom in camera view magnifies the framed "
                    "reference without moving the camera")

    # reference overlay
    show_ref: bpy.props.BoolProperty(name="Show reference", default=True,
                                     update=_on_ref_update)
    ref_alpha: bpy.props.FloatProperty(name="Opacity", default=0.5, min=0.0, max=1.0,
                                       update=_on_ref_update)
    ref_scale: bpy.props.FloatProperty(name="Scale", default=1.0, min=0.1, max=8.0,
                                       update=_on_ref_update, step=5)
    ref_off_x: bpy.props.FloatProperty(name="Shift X", default=0.0,
                                       update=_on_ref_update, step=2)
    ref_off_y: bpy.props.FloatProperty(name="Shift Y", default=0.0,
                                       update=_on_ref_update, step=2)

    # create-new-pair fields
    new_id: bpy.props.StringProperty(name="New id", default="")
    new_model: bpy.props.StringProperty(name="Model", default="harmonic_analyzer")
    new_ref: bpy.props.StringProperty(name="Reference", subtype="FILE_PATH", default="")


# --------------------------------------------------------------------------- #
# scene building
# --------------------------------------------------------------------------- #
_FACTORY_DEFAULT_NAMES = {"Cube", "Camera", "Light", "Lamp"}


def _clean_scene():
    """Remove our own built objects, plus the factory default cube/camera/light
    the launcher's fresh Blender opens with.

    We do NOT blind-delete every mesh/camera/light: if this is ever run inside a
    populated session (e.g. `blender --python` in the user's own file), that would
    silently wipe their unsaved scene. So the broad sweep runs ONLY when the
    leftover scene is the pristine factory default (all objects named
    Cube/Camera/Light); any foreign content is left untouched (with a warning)."""
    for obj in _STATE.get("objs", []) + ([_STATE["cam"]] if _STATE.get("cam") else []):
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except (ReferenceError, RuntimeError):
            pass
    _STATE.clear()
    leftover = list(bpy.data.objects)
    pristine = all(o.name.split(".")[0] in _FACTORY_DEFAULT_NAMES for o in leftover)
    if pristine:
        for obj in leftover:
            if obj.type in {"MESH", "CAMERA", "LIGHT"}:
                bpy.data.objects.remove(obj, do_unlink=True)
    elif leftover:
        print(f"!! pose_studio: {len(leftover)} pre-existing object(s) in scene — "
              f"leaving them untouched (run via the launcher for a clean scene)", flush=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def _frame_view(context):
    """Re-clip + re-centre the free viewport on the model.

    Geometry is in millimetres (~1400 units tall), so Blender's default viewport
    clip (0.01 .. 1000) SLICES it and the origin-centred orbit pivot flies off
    into the grey world background. Match the clip to the model scale and pivot
    the free view on the bbox centre so native orbit/pan/zoom stay on the model."""
    space = _view3d_space(context)
    if space is None or not _STATE.get("built"):
        return
    ext = _STATE["ext"]
    center = _bbox_center()
    space.clip_start = ext * 0.001
    space.clip_end = ext * 40
    rv3d = space.region_3d
    rv3d.view_location = center
    rv3d.view_distance = ext * 1.8
    context.scene.cursor.location = center


def _shade_like_render(context):
    """Workbench-ish solid shading + model-scaled clip/pivot so navigation and
    the viewport resemble render_offline."""
    space = _view3d_space(context)
    if space is None:
        return
    _frame_view(context)
    space.region_3d.view_perspective = "CAMERA"
    space.lock_camera = context.scene.hac_pose.lock_to_view
    sh = space.shading
    sh.type = "SOLID"
    sh.light = "STUDIO"
    sh.color_type = "OBJECT"
    sh.show_backface_culling = False
    # Kill the animated view transition so the camera-exit watcher's snap-to-camera
    # (see _camera_exit_watcher) lands instantly instead of fighting a smooth lerp.
    context.preferences.view.smooth_view = 0


class HAC_OT_build_scene(bpy.types.Operator):
    bl_idname = "hac.build_scene"
    bl_label = "Build / Reload Scene"
    bl_description = "Load the pair's model + reference and seed the pose sliders"

    def execute(self, context):
        props = context.scene.hac_pose
        manifest = _load_manifest(props)
        pair = _pair(props, manifest)
        if pair is None:
            self.report({"ERROR"}, f"pair {props.pair_id!r} not in manifest")
            return {"CANCELLED"}

        scene_json, parts_dir = _model_geometry(props, pair["model"])
        if not scene_json.exists():
            self.report({"ERROR"}, f"{scene_json} missing — run cad/scripts/export_models.py")
            return {"CANCELLED"}

        _clean_scene()
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

        # Reference photo as a camera background; its aspect drives the render aspect.
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
        else:
            self.report({"WARNING"}, "no reference image found; using 16:10")

        context.scene.render.resolution_x = w
        context.scene.render.resolution_y = h

        # Snapshot each part's as-built world matrix + its part stem so
        # HAC_OT_export_deltas can diff a hand-posed part against its release
        # position (the "move/resize a part to match the ref, read the shift
        # back out" loop). Assembly components carry a `part`/`mesh` stem; a
        # bare part maps to the model's dashed stem.
        orig_world = {obj.name: obj.matrix_world.copy() for obj in objs}
        if parts_dir is not None:
            sd = json.loads(scene_json.read_text(encoding="utf-8"))
            part_of = {c["name"]: (c.get("mesh") or c["part"])
                       for c in sd.get("components", [])}
        else:
            part_of = {obj.name: pair["model"].replace("_", "-") for obj in objs}

        _STATE.update(built=True, objs=objs, boxes=boxes, cam=cam, cam_data=cam_data,
                      mesh_lo=mesh_lo, mesh_hi=mesh_hi, ext=ext, w=w, h=h,
                      orig_world=orig_world, part_of=part_of)

        # Seed sliders from the pair's stored pose (fires _aim via callbacks).
        c = pair.get("camera", {})
        cx, cy, cz = _bbox_center()
        props.az_deg = float(c.get("az_deg", 0.0))
        props.el_deg = float(c.get("el_deg", 0.0))
        props.roll_deg = float(c.get("roll_deg", 0.0))
        # Resolve framing exactly as render_offline will (needs az/el/roll set
        # first): a frame_components close-up — or an explicit target_mm — yields a
        # concrete target+zoom, a bare pose falls back to the bbox centre. Seeding
        # the RESOLVED values means the preview matches the render AND Save Pose
        # (which drops frame_components) re-writes an explicit target_mm/zoom that
        # reproduces the same close-up, instead of collapsing it to the full bbox.
        explicit = bool(c.get("frame_components")) or c.get("target_mm") is not None
        target, zoom = bw.resolve_framing(c, boxes, mesh_lo, mesh_hi)
        # Seed the target sliders first — each assignment trips _on_target_update
        # (which frees the target) — then set free_target LAST so a bbox-centred
        # pose stays auto-centred (and re-saves as null, not an explicit centre).
        props.target_x, props.target_y, props.target_z = tuple(float(v) for v in target)
        props.free_target = explicit
        props.zoom = float(zoom)
        persp = c.get("perspective")
        props.perspective = bool(persp)
        if persp and persp.get("focal_length_mm"):
            props.focal_mm = float(persp["focal_length_mm"])

        _aim(props)
        _shade_like_render(context)
        self.report({"INFO"}, f"built {pair['model']} for {pair['id']} ({w}x{h})")
        return {"FINISHED"}


class HAC_OT_capture_view(bpy.types.Operator):
    bl_idname = "hac.capture_view"
    bl_label = "Capture From View"
    bl_description = ("Read az/el/roll + target from the navigated viewport "
                      "(orbit freely, then bake it into the pose; lens/zoom kept)")

    def execute(self, context):
        if not _STATE.get("built"):
            self.report({"ERROR"}, "Build Scene first")
            return {"CANCELLED"}
        space = _view3d_space(context)
        if space is None:
            self.report({"ERROR"}, "no 3D viewport")
            return {"CANCELLED"}
        props = context.scene.hac_pose
        rv3d = space.region_3d
        az, el, roll = _invert_pose(rv3d.view_matrix.inverted())
        props.az_deg, props.el_deg, props.roll_deg = az, el, roll
        loc = rv3d.view_location
        props.free_target = True
        props.target_x, props.target_y, props.target_z = loc.x, loc.y, loc.z
        _aim(props)  # re-centre framing on the captured angle + target
        self.report({"INFO"}, f"az {az:.1f}  el {el:.1f}  roll {roll:.1f}  "
                              f"target ({loc.x:.0f},{loc.y:.0f},{loc.z:.0f})")
        return {"FINISHED"}


class HAC_OT_reset_target(bpy.types.Operator):
    bl_idname = "hac.reset_target"
    bl_label = "Reset Target To Centre"
    bl_description = "Re-centre the framing on the model bbox (target_mm -> null)"

    def execute(self, context):
        if not _STATE.get("built"):
            self.report({"ERROR"}, "Build Scene first")
            return {"CANCELLED"}
        props = context.scene.hac_pose
        cx, cy, cz = _bbox_center()
        # Set the coords FIRST (each assignment trips _on_target_update, which
        # re-frees the target), then clear free_target LAST so the pose saves as a
        # null target_mm and stays auto-centred after a later bbox change.
        props.target_x, props.target_y, props.target_z = cx, cy, cz
        props.free_target = False
        _aim(props)
        return {"FINISHED"}


class HAC_OT_look_camera(bpy.types.Operator):
    bl_idname = "hac.look_camera"
    bl_label = "Look Through Camera"
    bl_description = "Return the viewport to the camera framing"

    def execute(self, context):
        space = _view3d_space(context)
        if space is not None:
            space.region_3d.view_perspective = "CAMERA"
        return {"FINISHED"}


class HAC_OT_toggle_camera(bpy.types.Operator):
    bl_idname = "hac.toggle_camera"
    bl_label = "Toggle Camera View (aligned)"
    bl_description = ("Numpad-0 replacement: leaving camera view drops you onto the "
                      "camera's exact vantage (no jump); entering returns to it")

    def execute(self, context):
        space = _view3d_space(context)
        if space is None:
            return {"CANCELLED"}
        rv3d = space.region_3d
        if rv3d.view_perspective != "CAMERA":
            rv3d.view_perspective = "CAMERA"
            return {"FINISHED"}
        # Leaving camera view: seed the free view from the camera FIRST, then flip
        # the projection by DIRECT assignment. The stock view3d.view_camera
        # operator restores its own stored pre-camera rotation (ignoring writes
        # made while in camera view — verified: loc/dist survive, rotation reverts),
        # so we bypass it entirely to land jump-free on the camera's vantage.
        _apply_camera_to_free(space)
        cam_data = _STATE.get("cam_data")
        rv3d.view_perspective = "ORTHO" if (cam_data and cam_data.type == "ORTHO") else "PERSP"
        return {"FINISHED"}


class HAC_OT_frame_model(bpy.types.Operator):
    bl_idname = "hac.frame_model"
    bl_label = "Frame Model"
    bl_description = ("Re-centre + re-clip the viewport on the model — use this if "
                      "orbiting greys out or the view gets sliced by a clip plane")

    def execute(self, context):
        if not _STATE.get("built"):
            self.report({"ERROR"}, "Build Scene first")
            return {"CANCELLED"}
        _frame_view(context)
        return {"FINISHED"}


class HAC_OT_save_manifest(bpy.types.Operator):
    bl_idname = "hac.save_manifest"
    bl_label = "Save Pose To Manifest"
    bl_description = "Write az/el/roll/target/zoom/lens onto this pair in manifest.json"

    def execute(self, context):
        props = context.scene.hac_pose
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
        c["zoom"] = round(props.zoom, 3)
        c["target_mm"] = ([round(props.target_x, 2), round(props.target_y, 2),
                           round(props.target_z, 2)] if props.free_target else None)
        c["perspective"] = {"focal_length_mm": round(props.focal_mm, 2)} if props.perspective else None
        # The studio previews an EXPLICIT euler target/zoom (it never applies
        # frame_components). Drop that seed-time auto-frame hint so the offline
        # render reproduces what was posed here, instead of silently re-deriving
        # target/zoom from the components and discarding these edits.
        dropped = c.pop("frame_components", None)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        note = "  (cleared frame_components)" if dropped else ""
        self.report({"INFO"}, f"saved pose -> {path.name} ({props.pair_id}){note}")
        return {"FINISHED"}


class HAC_OT_export_deltas(bpy.types.Operator):
    bl_idname = "hac.export_deltas"
    bl_label = "Export Part Deltas"
    bl_description = ("Diff every hand-moved/-scaled part against its release "
                     "position and write the shifts to comparisons/findings/"
                     "<pair>_deltas.json (for mapping back to SolidWorks dims)")

    # Below-noise moves are dropped so the findings file lists only real edits.
    # ~0.6 mm/px eyeball floor -> 0.5 mm; scale/rotation floors match.
    _T_MM = 0.5
    _S = 0.005
    _R_DEG = 0.2

    def execute(self, context):
        if not _STATE.get("built"):
            self.report({"ERROR"}, "Build Scene first")
            return {"CANCELLED"}
        props = context.scene.hac_pose
        orig = _STATE.get("orig_world", {})
        part_of = _STATE.get("part_of", {})

        moved = []
        for obj in _STATE.get("objs", []):
            base = orig.get(obj.name)
            if base is None:
                continue
            ot, orq, osc = base.decompose()
            ct, crq, csc = obj.matrix_world.decompose()
            dt = ct - ot                                   # world mm
            sf = [c / o if abs(o) > 1e-9 else 1.0 for c, o in zip(csc, osc)]
            dr = [math.degrees(a) for a in (crq @ orq.inverted()).to_euler()]
            if (max(abs(v) for v in dt) < self._T_MM
                    and max(abs(s - 1.0) for s in sf) < self._S
                    and max(abs(a) for a in dr) < self._R_DEG):
                continue
            moved.append({
                "name": obj.name,
                "part": part_of.get(obj.name, obj.name),
                "translate_mm": [round(v, 3) for v in dt],
                "scale": [round(s, 4) for s in sf],
                "rotate_deg": [round(a, 3) for a in dr],
            })

        out = {
            "pair": props.pair_id,
            "source": "release v0.20.0 boxes+stl (staged into cad/out)",
            "units": "translate_mm=world mm · scale=factor vs release · rotate_deg=XYZ euler",
            "pivot_hint": ("resize with Pivot=Individual Origins (period ','->3) so a "
                           "pure size change doesn't leak into translate_mm"),
            "camera": {"az_deg": round(props.az_deg, 2), "el_deg": round(props.el_deg, 2),
                       "roll_deg": round(props.roll_deg, 2), "zoom": round(props.zoom, 3),
                       "target_mm": [round(props.target_x, 2), round(props.target_y, 2),
                                     round(props.target_z, 2)] if props.free_target else None,
                       "focal_length_mm": round(props.focal_mm, 2) if props.perspective else None},
            "moved": moved,
        }
        dst = _repo(props) / "comparisons" / "findings" / f"{props.pair_id}_deltas.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(out, indent=2), encoding="utf-8")
        self.report({"INFO"}, f"{len(moved)} part(s) moved -> {dst.name}")
        return {"FINISHED"}


class HAC_OT_new_pair(bpy.types.Operator):
    bl_idname = "hac.new_pair"
    bl_label = "Create Pair"
    bl_description = "Add a new pair (id + model + reference) to manifest.json and load it"

    def execute(self, context):
        props = context.scene.hac_pose
        new_id = props.new_id.strip()
        if not new_id:
            self.report({"ERROR"}, "set a New id first")
            return {"CANCELLED"}
        ref_abs = Path(bpy.path.abspath(props.new_ref)).resolve()
        if not ref_abs.exists():
            self.report({"ERROR"}, f"reference not found: {ref_abs}")
            return {"CANCELLED"}
        try:
            rel = ref_abs.relative_to(_repo(props)).as_posix()
        except ValueError:
            self.report({"ERROR"}, "reference must live under the repo")
            return {"CANCELLED"}

        path = _manifest_path(props)
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if any(p["id"] == new_id for p in manifest["pairs"]):
            self.report({"ERROR"}, f"pair id {new_id!r} already exists")
            return {"CANCELLED"}
        manifest["pairs"].append({
            "id": new_id,
            "model": props.new_model.strip() or "harmonic_analyzer",
            "reference": {"path": rel, "source": "book"},
            "camera": {"mode": "euler", "az_deg": 0.0, "el_deg": 0.0, "roll_deg": 0.0,
                       "zoom": 1.0, "target_mm": None,
                       "perspective": {"focal_length_mm": 100.0}},
            "status": "draft",
        })
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        props.pair_id = new_id  # enum re-reads the manifest
        self.report({"INFO"}, f"created {new_id}; press Build / Reload Scene")
        return {"FINISHED"}


# --------------------------------------------------------------------------- #
# panel
# --------------------------------------------------------------------------- #
class HAC_PT_panel(bpy.types.Panel):
    bl_label = "Pose Studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Harmonic"

    def draw(self, context):
        props = context.scene.hac_pose
        layout = self.layout

        col = layout.column(align=True)
        col.prop(props, "repo_root")
        col.prop(props, "pair_id")
        col.operator(HAC_OT_build_scene.bl_idname, icon="IMPORT")

        box = layout.box()
        box.label(text="Orientation")
        box.prop(props, "az_deg")
        box.prop(props, "el_deg")
        box.prop(props, "roll_deg")

        box = layout.box()
        row = box.row()
        row.label(text="Target" + ("" if props.free_target else "  (centred)"))
        row.operator(HAC_OT_reset_target.bl_idname, text="", icon="PIVOT_BOUNDBOX")
        box.prop(props, "target_x")
        box.prop(props, "target_y")
        box.prop(props, "target_z")

        box = layout.box()
        box.label(text="Framing")
        box.prop(props, "zoom", slider=True)
        row = box.row(align=True)
        row.prop(props, "perspective", toggle=True)
        sub = row.row(align=True)
        sub.enabled = props.perspective
        sub.prop(props, "focal_mm")

        box = layout.box()
        box.label(text="Navigate")
        box.label(text="MMB orbit · Shift+MMB pan · scroll zoom", icon="INFO")
        box.label(text="Numpad 0 exits onto the camera vantage (no jump)", icon="CAMERA_DATA")
        box.prop(props, "lock_to_view", toggle=True)
        row = box.row(align=True)
        row.operator(HAC_OT_look_camera.bl_idname, icon="CAMERA_DATA")
        row.operator(HAC_OT_frame_model.bl_idname, icon="SHADING_BBOX")
        box.operator(HAC_OT_capture_view.bl_idname, icon="EYEDROPPER")

        box = layout.box()
        box.label(text="Reference")
        box.prop(props, "show_ref")
        box.prop(props, "ref_alpha", slider=True)
        box.prop(props, "ref_scale", slider=True)
        row = box.row(align=True)
        row.prop(props, "ref_off_x")
        row.prop(props, "ref_off_y")

        layout.operator(HAC_OT_save_manifest.bl_idname, icon="FILE_TICK")

        box = layout.box()
        box.label(text="Part fitting")
        box.label(text="Select a part · G move · S resize", icon="INFO")
        box.operator(HAC_OT_export_deltas.bl_idname, icon="EXPORT")

        box = layout.box()
        box.label(text="New pair")
        box.prop(props, "new_id")
        box.prop(props, "new_model")
        box.prop(props, "new_ref")
        box.operator(HAC_OT_new_pair.bl_idname, icon="ADD")


_CLASSES = (
    HACPoseProps,
    HAC_OT_build_scene,
    HAC_OT_capture_view,
    HAC_OT_reset_target,
    HAC_OT_look_camera,
    HAC_OT_toggle_camera,
    HAC_OT_frame_model,
    HAC_OT_save_manifest,
    HAC_OT_export_deltas,
    HAC_OT_new_pair,
    HAC_PT_panel,
)

_KEYMAPS: list = []


def _disable_retired_addon():
    """The retired blender_camera_addon.py registered the SAME `hac.*` operator
    ids and `Harmonic` panel category. On a seat that still has it enabled it
    loads first and collides with our register() (and keeps forcing camera-view
    lock). Disable it defensively before we register. No-op if it's absent."""
    try:
        import addon_utils
        addon_utils.disable("blender_camera_addon", default_set=False,
                            handle_error=lambda _e: None)
    except Exception:  # noqa: BLE001
        pass


def register():
    _disable_retired_addon()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hac_pose = bpy.props.PointerProperty(type=HACPoseProps)
    # Rebind Numpad-0 to the jump-free camera toggle (addon keymap wins over the
    # stock view3d.view_camera). Falls back gracefully if there's no addon config.
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new("hac.toggle_camera", "NUMPAD_0", "PRESS")
        _KEYMAPS.append((km, kmi))
    # Safety net: correctness for camera-exit doesn't hinge on the keymap winning.
    if not bpy.app.timers.is_registered(_camera_exit_watcher):
        bpy.app.timers.register(_camera_exit_watcher, persistent=True)


def unregister():
    _clean_scene()
    if bpy.app.timers.is_registered(_camera_exit_watcher):
        bpy.app.timers.unregister(_camera_exit_watcher)
    for km, kmi in _KEYMAPS:
        km.keymap_items.remove(kmi)
    _KEYMAPS.clear()
    del bpy.types.Scene.hac_pose
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


def _cli_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", default="")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--shots", default="", help="verify: capture camera<->free "
                    "toggle screenshots to this dir, then quit Blender")
    return ap.parse_known_args(argv)[0]


def _run_shots(shot_dir: str) -> None:
    """Drive the real UI: after build, toggle camera view off/on with the actual
    ``view3d.view_camera`` operator (Numpad 0) and grab window screenshots so a
    human can confirm the model no longer jumps between the two states. Set
    ``HARMONIC_NO_SYNC=1`` to capture the pre-fix baseline. Quits Blender after."""
    out = Path(shot_dir)
    out.mkdir(parents=True, exist_ok=True)
    tag = "nosync" if os.environ.get("HARMONIC_NO_SYNC") else "sync"
    win = bpy.context.window

    def v3d():
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
                return area, region
        return None, None

    def shot(name):
        # OpenGL-render exactly what the 3D viewport shows (camera or free view) —
        # geometry only; camera background (the reference overlay) is NOT composited.
        area, region = v3d()
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.render.opengl(view_context=True)
        bpy.data.images["Render Result"].save_render(filepath=str(out / f"{tag}-{name}.png"))

    def winshot(name):
        # Full-window grab — DOES show the reference background overlay the way the
        # user sees it while posing (needs the startup splash suppressed first).
        bpy.ops.screen.screenshot(filepath=str(out / f"{tag}-{name}.png"))

    def toggle():
        # Always drive the STOCK operator (the exact thing that jumped) — the fixed
        # run relies on the watcher net to correct it, proving Numpad-0 works even
        # if the keymap override loses. HARMONIC_NO_SYNC skips the watcher (baseline).
        area, region = v3d()
        with bpy.context.temp_override(window=win, area=area, region=region):
            bpy.ops.view3d.view_camera()

    steps = [
        lambda: winshot("0-camera-with-reference"),  # full window: shows the ref overlay
        lambda: shot("1-camera"),
        toggle,                             # leave camera view (Numpad 0)
        lambda: winshot("2b-free-window"),  # full window in free view
        lambda: shot("2-free-after-numpad0"),
        toggle,                             # back into camera view
        lambda: shot("3-camera-again"),
        lambda: bpy.ops.wm.quit_blender(),
    ]
    state = {"i": 0}

    def tick():
        i = state["i"]
        if i >= len(steps):
            return None
        try:
            steps[i]()
        except Exception as exc:  # noqa: BLE001
            print(f"SHOT ERROR step {i}: {exc}", flush=True)
        state["i"] += 1
        return 0.7

    bpy.app.timers.register(tick, first_interval=1.2)


def _auto_build():
    """Deferred (post-startup) seed of repo/pair + first build, from CLI args."""
    args = _cli_args()
    scene = bpy.context.scene
    props = scene.hac_pose
    props.repo_root = args.repo
    if args.pair:
        try:
            manifest = _load_manifest(props)
        except Exception:  # noqa: BLE001
            return None
        match = next((p["id"] for p in manifest["pairs"]
                      if p["id"] == args.pair or args.pair in p["id"]), None)
        if match:
            props.pair_id = match
            bpy.ops.hac.build_scene()
            if args.shots:
                _run_shots(args.shots)
    return None  # unregister the timer


if __name__ == "__main__":
    # --factory-startup restores the factory pref that shows the splash on launch;
    # suppress it so the studio (and the --shots window grabs) open straight to the
    # scene. Best-effort — never block startup on it.
    try:
        bpy.context.preferences.view.show_splash = False
    except Exception:  # noqa: BLE001
        pass
    register()
    # Build after Blender's UI is ready (context.screen valid) — a one-shot timer.
    bpy.app.timers.register(_auto_build, first_interval=0.25)
