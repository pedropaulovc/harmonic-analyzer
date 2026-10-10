"""On-demand native GLB ID renders through a headless Playwright page.

Client arrays are top-left row-major uint16; ready()['groupIds'] names the IDs.
The wire format tags base64 IDs as uint8 or little-endian uint16.
The browser receives CameraRecord principal points in the requested viewport's
pixels. Callers scaling a source camera must scale its principal point too.
The loaded page has Vite HMR disabled so code edits cannot interrupt a running fit.
Full runs can use preview=True, preview_out_dir=<private snapshot directory>.
The caller builds and records that snapshot; this client only serves it.
Candidate search may reject only the two documented native magnifier RangeErrors;
manual/final renders remain strict. last_candidate_failures holds per-call reason
counts; candidate_failure_counts accumulates them across the client's lifetime.
Appearance renders optionally add sRGB uint8 RGB and float32 native XYZ; XYZ
background is NaN and uses the same pixel order, mirror and principal point as IDs.

Run the private smoke/throughput check from the repository root:
    uv run --project web/sync python -m harmonic_sync.render_client --smoke
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Iterable, cast
from urllib.error import URLError
from urllib.request import urlopen

import numpy as np
from playwright.sync_api import Browser, Page, Playwright, sync_playwright


class RenderClient:
    """Own a headless browser and optionally a Vite server; use as a context manager."""

    def __init__(
        self,
        url: str | None = None,
        *,
        web_root: Path | str | None = None,
        preview: bool = False,
        preview_out_dir: Path | str | None = None,
        executable_path: str | None = None,
        chromium_args: Iterable[str] = (),
        gpu_backend: str = "auto",
        data_root: Path | str | None = None,
        timeout_seconds: float = 120,
        quiet_batches: bool = False,  # Quiet batch stderr only; JSONL and other events are unchanged.
    ) -> None:
        self.web_root = Path(web_root) if web_root else Path(__file__).resolve().parents[2]
        if preview_out_dir is not None and not preview:
            raise ValueError("preview_out_dir requires preview=True")
        self._preview_out_dir = Path(preview_out_dir).expanduser().resolve() if preview_out_dir is not None else None
        if self._preview_out_dir is not None and self._preview_out_dir.is_relative_to(self.web_root.resolve().parent):
            raise ValueError("preview_out_dir must be outside the repository")
        self.data_root = Path(data_root or os.environ.get("HARMONIC_SYNC_DATA", "~/data/harmonic-analyzer-sync")).expanduser()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._server: subprocess.Popen[bytes] | None = None
        self._server_log = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self.page: Page | None = None
        self._log_path = self.data_root / "render.jsonl"
        self._quiet_batches = quiet_batches
        self._ready: dict[str, Any] = {}
        self._browser_errors: list[str] = []
        self.last_batch_timing: dict[str, Any] = {}
        self.last_candidate_failures: dict[str, int] = {}
        self.candidate_failure_counts: dict[str, int] = {}
        started = time.perf_counter()
        try:
            self.url = url or self._start_vite(preview, timeout_seconds)
            self._playwright = sync_playwright().start()
            launch: dict[str, Any] = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage", "--ignore-gpu-blocklist", *chromium_args],
                "timeout": int(timeout_seconds * 1000),
            }
            if gpu_backend not in ("auto", "browser-default", "wsl-d3d12"):
                raise ValueError(f"Unknown GPU backend: {gpu_backend}")
            wsl = "microsoft" in platform.release().lower() and Path("/usr/lib/wsl/lib").is_dir()
            if gpu_backend == "wsl-d3d12" or gpu_backend == "auto" and wsl:
                # Headless Chromium still needs an X display for ANGLE's GL
                # backend. Use the WSLg socket without opening any browser UI.
                browser_env = {**os.environ, "GALLIUM_DRIVER": "d3d12", "MESA_D3D12_DEFAULT_ADAPTER_NAME": os.environ.get("MESA_D3D12_DEFAULT_ADAPTER_NAME", "NVIDIA")}
                browser_env["DISPLAY"] = os.environ.get("DISPLAY") or ":0"
                browser_env["LD_LIBRARY_PATH"] = "/usr/lib/wsl/lib" + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
                launch["env"] = browser_env
                launch["args"].extend(["--use-gl=angle", "--use-angle=gl", "--disable-software-rasterizer"])
                launch["ignore_default_args"] = ["--enable-unsafe-swiftshader"]
            chrome = executable_path or os.environ.get("HARMONIC_CHROME")
            if chrome is None and Path("/usr/bin/google-chrome").is_file():
                chrome = "/usr/bin/google-chrome"
            if chrome:
                launch["executable_path"] = chrome
            self._browser = self._playwright.chromium.launch(**launch)
            self.page = self._browser.new_page(viewport={"width": 480, "height": 270}, device_scale_factor=1)
            self.page.set_default_timeout(timeout_seconds * 1000)
            self.page.on("pageerror", lambda error: self._browser_error(str(error)))
            self.page.on("console", lambda message: self._browser_error(message.text) if message.type == "error" else None)
            # A long fit must retain its loaded module graph during shared edits.
            # The HMR client is unnecessary for this on-demand, headless page.
            self.page.route("**/@vite/client", lambda route: route.fulfill(
                status=200, content_type="application/javascript", body="",
            ))
            self.page.goto(self.url, wait_until="load", timeout=timeout_seconds * 1000)
            if self._browser_errors:
                raise RuntimeError("Browser startup error: " + "\n".join(self._browser_errors))
            self.page.wait_for_function("window.harmonicFit !== undefined")
            self._ready = self.page.evaluate("() => window.harmonicFit.ready()")
            self._log("ready", seconds=time.perf_counter() - started, renderer=self._ready["renderer"], groups={k: len(v) for k, v in self._ready["groups"].items()})
        except BaseException:
            self.close()
            raise

    def _start_vite(self, preview: bool, timeout_seconds: float) -> str:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        vite = self.web_root / "node_modules" / ".bin" / "vite"
        if not vite.is_file():
            raise FileNotFoundError(f"Vite missing at {vite}; run npm --prefix web ci")
        base = "/"
        if preview:
            built = (self._preview_out_dir or self.web_root / "dist") / "fit.html"
            html = built.read_text(encoding="utf-8")
            # Serve the exact base embedded in this snapshot, not today's Vite
            # environment. Relative/root-based snapshot assets use "/".
            asset = re.search(r"""<script\b[^>]*\bsrc=["'](/(?:[^"']*/)?assets/)""", html)
            if asset:
                base = asset.group(1).removesuffix("assets/")
        command = [str(vite), *(["preview"] if preview else []), "--host", "127.0.0.1", "--port", str(port), "--strictPort", "--base", base]
        if self._preview_out_dir is not None:
            command.extend(["--outDir", str(self._preview_out_dir)])
        self._server_log = (self.data_root / f"render-vite-{port}.log").open("wb")
        self._server = subprocess.Popen(
            command, cwd=self.web_root, env={**os.environ, "BROWSER": "none"},
            stdout=self._server_log, stderr=subprocess.STDOUT, start_new_session=True,
        )
        url = f"http://127.0.0.1:{port}{base}fit.html"
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if self._server.poll() is not None:
                raise RuntimeError(f"Vite exited ({self._server.returncode}); inspect {self._server_log.name}")
            try:
                with urlopen(url, timeout=1) as response:
                    if response.status == 200:
                        return url
            except (OSError, URLError):
                time.sleep(0.1)
        raise TimeoutError(f"Vite did not serve {url}; inspect {self._server_log.name}")

    def _log(self, event: str, **fields: Any) -> None:
        record = {"t": time.time(), "event": event, **fields}
        line = json.dumps(record, separators=(",", ":"))
        with self._log_path.open("a") as stream:
            stream.write(line + "\n")
        if event != "batch" or not self._quiet_batches:
            print(f"[render] {line}", file=sys.stderr, flush=True)

    def _browser_error(self, message: str) -> None:
        self._browser_errors.append(message)
        self._log("browser-error", error=message)

    def ready(self) -> dict[str, Any]:
        return self._ready

    @staticmethod
    def _decode(result: dict[str, Any]) -> np.ndarray:
        raw = base64.b64decode(result["ids"], validate=True)
        width, height = result["width"], result["height"]
        dtype = {"uint8": np.dtype("u1"), "uint16": np.dtype("<u2")}[result["dtype"]]
        if len(raw) != width * height * dtype.itemsize:
            raise ValueError("Browser ID byte count does not match render dimensions")
        return np.frombuffer(raw, dtype=dtype).reshape(height, width).astype(np.uint16, copy=False)

    @classmethod
    def _decode_appearance(cls, result: dict[str, Any]) -> dict[str, np.ndarray]:
        arrays = {"ids": cls._decode(result)}
        for field, key, dtype in (("rgb", "rgb", np.dtype("u1")), ("worldPositions", "world_positions", np.dtype("<f4"))):
            if field not in result:
                continue
            raw = base64.b64decode(result[field], validate=True)
            width, height = result["width"], result["height"]
            if len(raw) != width * height * 3 * dtype.itemsize:
                raise ValueError(f"Browser {field} byte count does not match render dimensions")
            arrays[key] = np.frombuffer(raw, dtype=dtype).reshape(height, width, 3)
        if "rgb" not in arrays:
            raise ValueError("Browser did not return requested shaded RGB")
        return arrays

    def render(self, request: dict[str, Any], *, shot_id: str | None = None, view_id: str | None = None) -> np.ndarray:
        return self.render_batch([request], shot_id=shot_id, view_id=view_id)[0]

    def render_batch(
        self, requests: Iterable[dict[str, Any]], *, shot_id: str | None = None, view_id: str | None = None,
    ) -> list[np.ndarray]:
        return cast(list[np.ndarray], self._render_batch(requests, shot_id, view_id, candidates=False))

    def render_appearance(
        self, request: dict[str, Any], *, world_positions: bool = True,
        shot_id: str | None = None, view_id: str | None = None,
    ) -> dict[str, np.ndarray]:
        return self.render_appearance_batch([request], world_positions=world_positions, shot_id=shot_id, view_id=view_id)[0]

    def render_appearance_batch(
        self, requests: Iterable[dict[str, Any]], *, world_positions: bool = True,
        shot_id: str | None = None, view_id: str | None = None,
    ) -> list[dict[str, np.ndarray]]:
        """Strict native-material RGB; optional XYZ is in metres with NaN background."""
        outputs = ["rgb", "worldPositions"] if world_positions else ["rgb"]
        batch = [{**request, "outputs": outputs} for request in requests]
        return cast(list[dict[str, np.ndarray]], self._render_batch(batch, shot_id, view_id, candidates=False, appearance=True))

    def render_candidate_batch(
        self, requests: Iterable[dict[str, Any]], *, shot_id: str | None = None, view_id: str | None = None,
    ) -> list[np.ndarray | None]:
        """Return None only for documented physical infeasibility during search."""
        self.last_candidate_failures = {}
        return cast(list[np.ndarray | None], self._render_batch(requests, shot_id, view_id, candidates=True))

    def _render_batch(
        self, requests: Iterable[dict[str, Any]], shot_id: str | None, view_id: str | None, *,
        candidates: bool, appearance: bool = False,
    ) -> list[np.ndarray | dict[str, np.ndarray] | None]:
        if self.page is None:
            raise RuntimeError("RenderClient is closed")
        batch = list(requests)
        if not batch:
            return []
        before = self.timing_snapshot()
        started = time.perf_counter()
        try:
            # Compress only the CDP envelope, not the harmonicFit API. Flat ID
            # images otherwise spend more time in JSON transport than rendering.
            envelope = self.page.evaluate("""async ({requests, candidates}) => {
                const failures = {};
                let results;
                const renderStarted = performance.now();
                if (candidates) {
                    const allowed = [
                        'Magnifier hook has left the installed upper hub-tangent branch',
                        'Pen wire has exhausted its hanging run; reset the physical output fixture before using this clamp setting',
                    ];
                    results = [];
                    for (const request of requests) {
                        try {
                            results.push(await window.harmonicFit.render(request));
                        } catch (error) {
                            if (!(error instanceof RangeError) || !allowed.includes(error.message)) throw error;
                            failures[error.message] = (failures[error.message] ?? 0) + 1;
                            results.push(null);
                        }
                    }
                } else {
                    results = await window.harmonicFit.renderBatch(requests);
                }
                const renderMs = performance.now() - renderStarted;
                const started = performance.now();
                const stream = new Blob([JSON.stringify({results, failures})]).stream()
                    .pipeThrough(new CompressionStream('gzip'));
                const compressed = new Uint8Array(await new Response(stream).arrayBuffer());
                return {gzip: compressed.toBase64(), renderMs, transportMs: performance.now() - started};
            }""", {"requests": batch, "candidates": candidates})
            evaluated = time.perf_counter()
            if self._browser_errors:
                raise RuntimeError("Browser render error: " + "\n".join(self._browser_errors))
            payload = json.loads(gzip.decompress(base64.b64decode(envelope["gzip"], validate=True)))
            unpacked = time.perf_counter()
            if candidates:
                self.last_candidate_failures = payload["failures"]
                for reason, count in self.last_candidate_failures.items():
                    self.candidate_failure_counts[reason] = self.candidate_failure_counts.get(reason, 0) + count
                if self.last_candidate_failures:
                    self._log("candidate-infeasible", shotId=shot_id, viewId=view_id,
                              count=sum(self.last_candidate_failures.values()), reasons=self.last_candidate_failures)
            arrays = [
                None if candidates and result is None else self._decode_appearance(result) if appearance else self._decode(result)
                for result in payload["results"]
            ]
            decoded = time.perf_counter()
        except Exception as error:
            self._log("batch-error", shotId=shot_id, viewId=view_id, count=len(batch), candidates=candidates,
                      seconds=time.perf_counter() - started, error=str(error))
            raise
        seconds = decoded - started
        after = self.timing_snapshot()
        browser = {key: after[key] - value for key, value in before.items()}
        # Candidate calls use strict render(), not renderBatch(), so measure
        # their full search duration here, including rejected physical solves.
        browser["batchMs"] = envelope["renderMs"]
        self.last_batch_timing = {
            "browser": browser, "evaluateMs": (evaluated - started) * 1000,
            "browserTransportMs": envelope["transportMs"],
            "unpackMs": (unpacked - evaluated) * 1000,
            "decodeMs": (decoded - unpacked) * 1000,
            "cdpAndSerializationMs": (evaluated - started) * 1000 - browser["batchMs"] - envelope["transportMs"],
        }
        self._log("batch", shotId=shot_id, viewId=view_id, count=len(batch), candidates=candidates,
                  seconds=seconds, rendersPerSecond=len(batch) / seconds, timing=self.last_batch_timing)
        return arrays

    def timing_snapshot(self) -> dict[str, float]:
        if self.page is None:
            raise RuntimeError("RenderClient is closed")
        return self.page.evaluate("async () => (await window.harmonicFit.ready()).timings")

    def renderer_info(self) -> dict[str, Any]:
        if self.page is None:
            raise RuntimeError("RenderClient is closed")
        return self.page.evaluate("""() => {
            const gl = document.querySelector('#fit').getContext('webgl2');
            const ext = gl.getExtension('WEBGL_debug_renderer_info');
            return {renderer: gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER),
                    vendor: gl.getParameter(ext ? ext.UNMASKED_VENDOR_WEBGL : gl.VENDOR),
                    version: gl.getParameter(gl.VERSION)};
        }""")

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
        finally:
            self._browser = None
            self.page = None
            try:
                if self._playwright:
                    self._playwright.stop()
            finally:
                self._playwright = None
                if self._server:
                    try:
                        os.killpg(self._server.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        self._server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(self._server.pid, signal.SIGKILL)
                        self._server.wait()
                    self._server = None
                if self._server_log:
                    self._server_log.close()
                    self._server_log = None

    def __enter__(self) -> RenderClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _camera(eye: tuple[float, float, float], target: tuple[float, float, float], up: tuple[float, float, float]) -> dict[str, Any]:
    z = np.asarray(eye) - np.asarray(target)
    z /= np.linalg.norm(z)
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.column_stack((x, y, z))
    trace = float(np.trace(m))
    q = np.empty(4)
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        q[:] = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, s / 4]
    else:
        i = int(np.argmax(np.diag(m)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1 + m[i, i] - m[j, j] - m[k, k]) * 2
        q[i] = s / 4
        q[j] = (m[j, i] + m[i, j]) / s
        q[k] = (m[k, i] + m[i, k]) / s
        q[3] = (m[k, j] - m[j, k]) / s
    return {"positionMetres": list(eye), "quaternion": q.tolist(), "verticalFovDegrees": 38, "principalPointViewportPixels": [240, 135]}


def smoke(client: RenderClient, count: int = 64, *, appearance: bool = False) -> dict[str, Any]:
    """Save synthetic renders, check pose/filter/mirror, and time a batch."""
    from PIL import Image

    destination = client.data_root / "harness-smoke"
    destination.mkdir(parents=True, exist_ok=True)
    ready = client.ready()
    group_ids = ready["groupIds"]
    groups = ready["groups"]
    default_input = {
        "crankTurns": 0, "amplitudes": [0.0] * 20, "phases": [0.0] * 20,
        "gearing": "small-large", "magnification": 165 / 39.85,
        "setup": {"counterHeightM": None, "meanLineAngleRad": 0, "platenOffsetM": 0, "wireFixtureOffsetM": 0, "coneSwingRad": 0, "pinionCamRad": 0, "heldChannelTurns": 0, "driveCrankOffsetTurns": 0},
    }
    lower = np.asarray(ready["boundsMetres"]["min"])
    upper = np.asarray(ready["boundsMetres"]["max"])
    center = (lower + upper) / 2
    half = (upper - lower) / 2
    cameras: dict[str, Any] = {}
    # Native machine Y is up; its twenty-station bank extends along Z.
    for view, axis, horizontal, vertical, up in (
        ("front", 0, 2, 1, (0, 1, 0)),
        ("side", 2, 0, 1, (0, 1, 0)),
        ("top", 1, 0, 2, (0, 0, -1)),
    ):
        distance = half[axis] + 1.12 * max(half[vertical], half[horizontal] / (16 / 9)) / math.tan(math.radians(38 / 2))
        eye = center.copy()
        eye[axis] += distance
        cameras[view] = _camera(tuple(eye), tuple(center), up)
    palette = np.zeros((max(group_ids.values()) + 1, 3), dtype=np.uint8)
    import colorsys
    for group, index in group_ids.items():
        colour = (0.55, 0.55, 0.55) if group == "static" else colorsys.hsv_to_rgb((index * 0.61803398875) % 1, 0.7, 1)
        palette[index] = np.rint(np.asarray(colour) * 255).astype(np.uint8)

    def request(camera: dict[str, Any], turns: float, only: list[str] | None = None) -> dict[str, Any]:
        value = {"camera": camera, "input": {**default_input, "crankTurns": turns}, "width": 480, "height": 270, "presentation": "native"}
        if only is not None:
            value["groups"] = only
        return value

    checks: dict[str, Any] = {}
    for view, camera in cameras.items():
        turns = (0, 0.173, 2.137)
        images = client.render_batch([request(camera, value) for value in turns], shot_id="harness-smoke", view_id=view)
        for value, ids in zip(turns, images, strict=True):
            if not np.any(ids):
                raise AssertionError(f"Empty {view} native render")
            Image.fromarray(palette[ids]).save(destination / f"{view}-{value:g}.png")
        static = client.render_batch([request(camera, value, ["static"]) for value in (0, 2.137)], shot_id="harness-smoke-static", view_id=view)
        if not np.any(static[0]) or not np.array_equal(static[0], static[1]):
            raise AssertionError(f"Static group changed or invisible in {view}")
        moving = client.render_batch([request(camera, value, [name for name in groups if name != "static"]) for value in (0, 2.137)], shot_id="harness-smoke-moving", view_id=view)
        changed = int(np.count_nonzero(moving[0] != moving[1]))
        if changed == 0:
            raise AssertionError(f"Moving groups do not move in {view}")
        checks[view] = {"staticExact": True, "movingChangedPixels": changed, "foregroundPixels": int(np.count_nonzero(images[0]))}
    first = client.render(request(cameras["front"], 0), shot_id="harness-smoke-mirror")
    mirrored_request = request(cameras["front"], 0)
    mirrored_request["presentation"] = "horizontal-mirror"
    mirrored = client.render(mirrored_request, shot_id="harness-smoke-mirror")
    if not np.array_equal(mirrored, first[:, ::-1]):
        raise AssertionError("Horizontal mirror is not an exact x flip")
    offcenter = {**cameras["front"], "principalPointViewportPixels": [253, 142]}
    shifted = client.render(request(offcenter, 0), shot_id="harness-smoke-principal-point")
    if not np.array_equal(shifted[7:, 13:], first[:-7, :-13]):
        raise AssertionError("Principal-point camera did not translate the image by (13,7)")
    appearance_checks: dict[str, Any] = {}
    if appearance:
        appearance_request = request(offcenter, 0)
        shaded = client.render_appearance(appearance_request, shot_id="harness-smoke-appearance")
        if not np.array_equal(shaded["ids"], shifted):
            raise AssertionError("Appearance changed the native ID projection")
        xyz = shaded["world_positions"]
        mask = shaded["ids"] > 0
        if not np.isfinite(xyz[mask]).all() or not np.isnan(xyz[~mask]).all():
            raise AssertionError("World positions must be finite on-machine and NaN off-machine")
        x, y, z, w = offcenter["quaternion"]
        rotation = np.array([
            [1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
            [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
            [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)],
        ])
        local = (xyz[mask] - np.asarray(offcenter["positionMetres"])) @ rotation
        tangent = math.tan(math.radians(offcenter["verticalFovDegrees"] / 2))
        cx, cy = offcenter["principalPointViewportPixels"]
        projected = np.column_stack((cx + local[:, 0] / -local[:, 2] * 270 / (2 * tangent),
                                     cy - local[:, 1] / -local[:, 2] * 270 / (2 * tangent)))
        yy, xx = np.nonzero(mask)
        error = np.linalg.norm(projected - np.column_stack((xx + 0.5, yy + 0.5)), axis=1)
        if float(error.max()) > 0.1:
            raise AssertionError(f"World-position reprojection error: {float(error.max()):.6f}px")
        mirrored_appearance = client.render_appearance(
            {**appearance_request, "presentation": "horizontal-mirror"}, shot_id="harness-smoke-appearance-mirror",
        )
        if not np.array_equal(mirrored_appearance["rgb"], shaded["rgb"][:, ::-1]):
            raise AssertionError("Shaded RGB mirror is not an exact x flip")
        if not np.array_equal(mirrored_appearance["ids"], shaded["ids"][:, ::-1]):
            raise AssertionError("Appearance IDs mirror is not an exact x flip")
        if not np.allclose(mirrored_appearance["world_positions"], xyz[:, ::-1], rtol=0, atol=0, equal_nan=True):
            raise AssertionError("World-position mirror is not an exact x flip")
        if not np.array_equal(client.render(appearance_request, shot_id="harness-smoke-material-restore"), shifted):
            raise AssertionError("Appearance did not restore ID materials")
        Image.fromarray(shaded["rgb"]).save(destination / "front-rgb.png")
        Image.fromarray(mirrored_appearance["rgb"]).save(destination / "front-rgb-mirror.png")
        appearance_checks = {"worldPositionsNaNBackground": True, "worldPositionsMaxReprojectionPx": float(error.max()),
                             "rgbMirrorExact": True, "worldPositionsMirrorExact": True, "idMaterialsRestored": True}
    # Warm shader programs and GPU buffers before the timed transport+decode batch.
    client.render_batch([request(cameras["front"], i * 0.13) for i in range(8)], shot_id="harness-throughput-warmup")
    started = time.perf_counter()
    client.render_batch([request(cameras["front"], i * 0.137) for i in range(count)], shot_id="harness-throughput")
    seconds = time.perf_counter() - started
    crank_timing = client.last_batch_timing
    camera_requests = []
    for i in range(count):
        eye = np.asarray(cameras["front"]["positionMetres"]).copy()
        eye[2] += (i - count / 2) * 0.003
        camera_requests.append(request(_camera(tuple(eye), tuple(center), (0, 1, 0)), 0.173))
    started = time.perf_counter()
    client.render_batch(camera_requests, shot_id="harness-throughput-camera-only")
    camera_seconds = time.perf_counter() - started
    summary = {
        "renderer": client.renderer_info(), "groupIds": group_ids,
        "groupCounts": {name: len(parts) for name, parts in groups.items()},
        "channelMapping": ready["channelMapping"], "checks": checks,
        "boundsMetres": ready["boundsMetres"], "cameras": cameras,
        "appearanceChecks": appearance_checks,
        "mirrorExact": True, "principalPointExact": True,
        "throughput": {"count": count, "width": 480, "height": 270, "seconds": seconds, "rendersPerSecond": count / seconds, "targetRendersPerSecond": 30},
        "timingSplit": crank_timing,
        "cameraOnlyThroughput": {"count": count, "width": 480, "height": 270, "seconds": camera_seconds, "rendersPerSecond": count / camera_seconds, "timingSplit": client.last_batch_timing},
        "output": str(destination),
    }
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (destination / "groups.json").write_text(json.dumps(ready, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", required=True)
    parser.add_argument("--appearance", action="store_true", help="Also verify shaded RGB and native per-pixel XYZ")
    parser.add_argument("--url", help="Attach to an existing Vite fit.html URL")
    parser.add_argument("--preview", action="store_true", help="Serve an already-built web/dist instead of Vite dev")
    parser.add_argument("--count", type=int, default=64)
    parser.add_argument("--chromium-arg", action="append", default=[])
    parser.add_argument("--gpu-backend", choices=("auto", "browser-default", "wsl-d3d12"), default="auto")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be positive")
    with RenderClient(url=args.url, preview=args.preview, chromium_args=args.chromium_arg, gpu_backend=args.gpu_backend) as client:
        print(json.dumps(smoke(client, args.count, appearance=args.appearance), indent=2))


if __name__ == "__main__":
    main()
