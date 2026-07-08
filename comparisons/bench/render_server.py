# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Persistent Blender render server for the T2 closed loop.

blender_worker.py --serve builds the 409-part assembly ONCE and then renders one
camera per stdin JSON line, so a T2 round costs ~1-2 s instead of the ~40 s a
fresh render_offline invocation pays to reload. One server serves every pair
(same model); per-request width/height/frozen carry the pair's fixed frame.
"""

import itertools
import json
import subprocess
import sys
import threading
from pathlib import Path

from PIL import Image

BENCH = Path(__file__).resolve().parent
TOOLS = BENCH.parent / "tools"
sys.path.insert(0, str(TOOLS))
import render_offline as ro  # noqa: E402  (BLENDER, WORKER, model_paths)

JPEG = {"quality": 90, "optimize": True}


class RenderServer:
    def __init__(self, model: str = "harmonic_analyzer", tmp: Path | None = None):
        self.tmp = Path(tmp or (BENCH / "out" / "_serve"))
        self.tmp.mkdir(parents=True, exist_ok=True)
        _src, geom = ro.model_paths(model)
        jobf = self.tmp / "serve_job.json"
        jobf.write_text(json.dumps(geom | {"serve": True, "pairs": []}), encoding="utf-8")
        self.proc = subprocess.Popen(
            [str(ro.BLENDER), "-b", "--factory-startup", "-P", str(ro.WORKER), "--", str(jobf)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        self._ids = itertools.count()
        self._lock = threading.Lock()

    def render(self, camera: dict, w: int, h: int, frozen: dict | None, out_png: Path) -> Path:
        with self._lock:
            rid = f"r{next(self._ids)}"
            req = {"id": rid, "camera": camera, "width": w, "height": h,
                   "frozen": frozen, "out": str(out_png)}
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
            for line in self.proc.stdout:
                if line.startswith(f"SERVED {rid}"):
                    return out_png
                if self.proc.poll() is not None:
                    raise RuntimeError("blender serve process died")
            raise RuntimeError("blender serve EOF before SERVED")

    def render_jpg(self, camera: dict, w: int, h: int, frozen: dict | None,
                   bg: str, out_jpg: Path) -> Path:
        png = self.tmp / f"frame_{next(self._ids)}.png"
        self.render(camera, w, h, frozen, png)
        img = Image.open(png).convert("RGBA")
        canvas = Image.new("RGB", img.size, (255, 255, 255) if bg == "white" else (0, 0, 0))
        canvas.paste(img, mask=img.getchannel("A"))
        canvas.save(out_jpg, **JPEG)
        png.unlink(missing_ok=True)
        return out_jpg

    def close(self) -> None:
        try:
            self.proc.stdin.write("\n")
            self.proc.stdin.flush()
            self.proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            self.proc.kill()
