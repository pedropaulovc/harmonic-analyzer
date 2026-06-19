---
name: motion-avi-export
description: Why IMotionStudy.SaveToAVI(.avi) fails headlessly and the native MP4/MKV/FLV fix (export_motion_video)
metadata: 
  node_type: memory
  type: project
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

SOLIDWORKS Motion video export, root-caused live 2026-06-13 on SW 2026 SP2.0 Makers.

`IMotionStudy::SaveToAVI` with `OutputType=swAnimationOutput_AVI (1)` ALWAYS returns
false in automation — the `.avi` path opens the Windows Video-Compression **codec
dialog**, which has no API, so it returns false with NO dialog at all headlessly. That
is why it works from the UI (the user picks a codec → produced a 104 MB uncompressed
AVI) but never headlessly. NOT licence-limited, NOT a parameter problem. The SW macro
recorder also does NOT capture "Save Animation to File" (recorded .swp is empty), so
there were never any parameters to copy.

**The real fix: don't use the .avi container — use the modern single-file ones.**
`OutputType` MP4 (7), MKV (8), FLV (9) encode internally with no dialog and write a
real, compact H.264 video headlessly via the API. Verified: .mp4 41674 B, .mkv 40815,
.flv 41499, all valid H.264 1920×848; .avi = nothing. Image series (BMP 2, TGA 3,
PNG 4, JPG 5, TIF 6) also work but are multi-file — no need. NO ffmpeg, NO BMP scratch
dir. (Earlier BMP+ffmpeg attempt was a hack and was deleted.)

Gotcha: `SaveToAVI` returns true IMMEDIATELY then finishes writing on a background
thread — poll until the output file size stabilizes before reading it (checking size
right after the call gave a false "MP4 = 0 bytes" reading). Also set
`RendererType=Solidworks_Screen (0)` (the PhotoView renderer needs a loaded ray-trace
engine), `Stop()` the study before saving (else the save races the animator → false),
and restore the SW window (un-minimise via `ISldWorks::Frame::GetHWndx64` +
`ShowWindow(SW_RESTORE)`) so the framebuffer grab isn't blank.

Shipped in adapter `solidworks/motion.py` `_export_motion_video_impl` — method renamed
`export_motion_avi` → **`export_motion_video`** (extension-driven container; `.avi`
raises an explanatory error). `MotionExportParameters`/`ExportMotionVideoInput` carry
`frames_per_second` (width/height dropped — screen renderer uses the viewport). Also
added `sw_type_info.early_bound()` (wrap late-bound dispatch in its early-bound
interface class so dispid-only members like `IModelDocExtension.GetMotionStudyManager`
resolve). PR-M3 on branch `motion-video-export` → `personal`. See
[[harmonic-analyzer-project]]; adapter PRs target `personal` per [[fix-migration-status]].
