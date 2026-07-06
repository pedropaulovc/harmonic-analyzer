---
name: pose-studio-camera-toggle
description: Blender pose_studio Numpad-0 (camera view) toggle jump — root cause in RegionView3D restore + the keymap/watcher fix, plus the stale blender_camera_addon conflict
metadata:
  type: project
---

`comparisons/tools/pose_studio.py` — leaving camera view (Numpad 0) used to fling
the model into a corner/onto its side.

**Root cause (verified empirically, not guessed):** Blender's stock
`view3d.view_camera` operator, when EXITING camera view, restores its own stored
*pre-camera* view. Writing `RegionView3D.view_rotation/location/distance` while IN
camera view is asymmetric — `view_location` and `view_distance` survive the toggle,
but `view_rotation` reverts to the stored default. So pre-syncing the free view
inside camera mode does NOT work for rotation.

**Fix (two layers):**
1. `HAC_OT_toggle_camera` bound to NUMPAD_0 via an addon keymap — on exit it seeds
   the free view from `hac_cam` (`_apply_camera_to_free`) then flips
   `view_perspective` by DIRECT assignment (direct assignment skips the store/restore
   dance, so rotation sticks).
2. `_camera_exit_watcher` — a persistent `bpy.app.timers` poll that snaps the free
   view to the camera on ANY camera→free edge (menu, gizmo, or if the keymap loses
   precedence). This is the correctness guarantee; the keymap just makes it
   flicker-free. `smooth_view=0` so the snap is instant.

Viewport FOV match: `space.lens = cam.lens * 36 / sensor_long` (free viewport meters
on a 36 mm sensor; `aim_camera` meters on the DX long edge).

**Verification pattern:** `pose_studio.py --shots <dir>` drives the real UI (build →
`view3d.view_camera` toggle → OpenGL viewport render `render.opengl(view_context=True)`
of each state → quit). Use `render.opengl`, NOT `screen.screenshot` — the latter
catches the startup splash. `HARMONIC_NO_SYNC=1` captures the pre-fix baseline.

**Env gotcha:** the RETIRED `blender_camera_addon.py` (deleted from repo; replaced by
pose_studio) had a stale ENABLED copy under `%APPDATA%/Blender Foundation/Blender/
5.1/scripts/addons/`. It registered a panel in the SAME `"Harmonic"` N-panel category
and force-set `space.lock_camera = True`, fighting pose_studio every session (and
erroring on shutdown). Removed + `addon_disable`d 2026-07-05. If camera behaviour goes
weird again, check that folder for a reinstalled copy. See [[harmonic-analyzer-project-decisions]].
