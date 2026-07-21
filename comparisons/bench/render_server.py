# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Persistent Blender render server for the T2 closed loop.

blender_worker.py --serve builds the 409-part assembly ONCE and then renders one
camera per stdin JSON line, so a T2 round costs ~1-2 s instead of the ~40 s a
fresh render_offline invocation pays to reload. One server serves every pair
(same model); per-request width/height/frozen carry the pair's fixed frame.

A model-proposed T2 correction is untrusted input (run.py clamps it, but defense
in depth): a degenerate camera can make Blender's rasterizer stall far past a
normal 1-2 s render. Every request therefore has a timeout; a request that blows
it (or a dead pipe) KILLS AND RESTARTS the Blender process (paying the ~40 s
reload once) rather than wedging every other caller queued behind the shared
render lock forever.
"""

import itertools
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image

BENCH = Path(__file__).resolve().parent
TOOLS = BENCH.parent / "tools"
sys.path.insert(0, str(TOOLS))
import render_offline as ro  # noqa: E402  (blender_exe, WORKER, model_paths)

JPEG = {"quality": 90, "optimize": True}
DEFAULT_TIMEOUT = 60.0    # normal render is 1-2s; this only trips on a genuine stall
STARTUP_TIMEOUT = 240.0   # cold-load of the full assembly under CPU contention (no GPU)


class RenderServer:
    def __init__(self, model: str = "harmonic_analyzer", tmp: Path | None = None,
                timeout: float = DEFAULT_TIMEOUT):
        self.model = model
        self.tmp = Path(tmp or (BENCH / "out" / "_serve"))
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._ids = itertools.count()
        self._lock = threading.Lock()
        self.restarts = 0
        self._start_proc()

    def _start_proc(self) -> None:
        """(Re)spawn the worker and BLOCK until it signals READY.

        Called from __init__ (no concurrent callers yet) and from
        _restart_locked (caller already holds self._lock) -- either way,
        blocking here means no render() request can reach the fresh process
        before its cold-load (importing every part STL, building the scene
        graph -- can run well past a request timeout under CPU contention with
        no GPU) has actually finished. Skipping this handshake was the earlier
        bug: a restart's replacement got hit with the next queued request
        immediately, timed out again before finishing its own reload, and
        restarted again -- a livelock that never completed a single render.
        """
        _src, geom = ro.model_paths(self.model)
        jobf = self.tmp / "serve_job.json"
        jobf.write_text(json.dumps(geom | {"serve": True, "pairs": []}), encoding="utf-8")
        self.proc = subprocess.Popen(
            [ro.blender_exe(), "-b", "--factory-startup", "-P", str(ro.WORKER), "--", str(jobf)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        self._q: queue.Queue = queue.Queue()
        proc = self.proc  # bind for the closure so a later restart doesn't race the reader

        def _read_loop():
            try:
                for line in proc.stdout:
                    self._q.put(line)
            except (OSError, ValueError):
                pass
            self._q.put(None)  # EOF/death sentinel
        threading.Thread(target=_read_loop, daemon=True).start()

        deadline = time.monotonic() + STARTUP_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                proc.kill()
                raise RuntimeError(f"blender serve did not become READY within "
                                   f"{STARTUP_TIMEOUT}s")
            try:
                line = self._q.get(timeout=remaining)
            except queue.Empty:
                continue
            if line is None:
                raise RuntimeError("blender serve process died during startup")
            if line.strip() == "READY":
                return

    def _restart_locked(self) -> None:
        """Caller must hold self._lock. Kills the wedged process and reloads fresh."""
        try:
            self.proc.kill()
            self.proc.wait(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        self.restarts += 1
        self._start_proc()

    def render(self, camera: dict, w: int, h: int, frozen: dict | None, out_png: Path) -> Path:
        with self._lock:
            rid = f"r{next(self._ids)}"
            req = {"id": rid, "camera": camera, "width": w, "height": h,
                   "frozen": frozen, "out": str(out_png)}
            try:
                self.proc.stdin.write(json.dumps(req) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                self._restart_locked()
                raise RuntimeError(f"blender serve pipe broken (rid={rid}); server restarted")
            deadline = time.monotonic() + self.timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._restart_locked()
                    raise TimeoutError(f"blender serve stalled >{self.timeout}s (rid={rid}); "
                                       "server restarted")
                try:
                    line = self._q.get(timeout=remaining)
                except queue.Empty:
                    continue
                if line is None:
                    self._restart_locked()
                    raise RuntimeError(f"blender serve process died (rid={rid}); server restarted")
                if line.startswith(f"SERVED {rid}"):
                    return out_png
                # stale line from a prior (timed-out) request, or blender noise: keep waiting

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
