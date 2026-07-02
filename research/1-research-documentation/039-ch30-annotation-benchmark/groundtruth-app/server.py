"""Ground-truth annotation server for the ch30 benchmark.

Run:  uv run python research/1-research-documentation/039-ch30-annotation-benchmark/groundtruth-app/server.py
Open: http://localhost:8039

Serves the drag-drop UI, the original ch30 images, and persists ground truth to
../ground_truth/<stem>.json. Prefills each image from ch30_annotated/final/<stem>.json
(the round-1 consensus) when no ground truth exists yet, so you drag dots into place
instead of starting blank.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = Path(__file__).parent
BENCH = APP.parent
REPO = BENCH.parents[2]
IMAGES = REPO / "references" / "albert-michelsons-harmonic-analyzer" / "ch30_images"
CONSENSUS = REPO / "ch30_annotated" / "final"
GT = BENCH / "ground_truth"

STEMS = [f"page00{n}_img01" for n in range(2, 10)]
EXT = {s: ("jpeg" if s in ("page005_img01", "page007_img01") else "png") for s in STEMS}

FEATURES = [
    ("pinion_center", "red"),
    ("crank_axle_sprocket_center", "red"),
    ("cylinder_gear_center_1", "orange"),
    ("cylinder_gear_center_2", "orange"),
    ("cone_gear_center", "magenta"),
    ("rocker_arm_corner_butt_left", "yellow"),
    ("rocker_arm_corner_butt_right", "yellow"),
    ("rocker_arm_corner_tip_left", "yellow"),
    ("rocker_arm_corner_tip_right", "yellow"),
    ("analyzer_corner_top_front_left", "cyan"),
    ("analyzer_corner_top_front_right", "cyan"),
    ("analyzer_corner_top_back_left", "cyan"),
    ("analyzer_corner_top_back_right", "cyan"),
    ("analyzer_corner_base_front_left", "cyan"),
    ("analyzer_corner_base_front_right", "cyan"),
    ("analyzer_corner_base_back_left", "cyan"),
    ("analyzer_corner_base_back_right", "cyan"),
]


def load_state(stem):
    gt_file = GT / f"{stem}.json"
    if gt_file.exists():
        d = json.loads(gt_file.read_text())
        d["provenance"] = "ground_truth"
        return d
    cons = CONSENSUS / f"{stem}.json"
    if cons.exists():
        d = json.loads(cons.read_text())
        return {
            "image": d["image"],
            "points": [{"feature": p["feature"], "x": p["x"], "y": p["y"]} for p in d["points"]],
            "occluded": [{"feature": o["feature"], "reason": o.get("reason", "")} for o in d.get("occluded", [])],
            "provenance": "consensus_prefill",
        }
    return {"image": f"{stem}.{EXT[stem]}", "points": [], "occluded": [], "provenance": "empty"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (APP / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path.startswith("/images/"):
            f = IMAGES / self.path.split("/images/", 1)[1]
            if f.is_file() and f.parent == IMAGES:
                return self._send(200, f.read_bytes(), "image/jpeg" if f.suffix == ".jpeg" else "image/png")
            return self._send(404, {"error": "not found"})
        if self.path == "/api/state":
            return self._send(200, {
                "stems": STEMS,
                "ext": EXT,
                "features": [{"name": n, "color": c} for n, c in FEATURES],
                "states": {s: load_state(s) for s in STEMS},
            })
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/save":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0))
        d = json.loads(self.rfile.read(n))
        stem = d.get("stem")
        if stem not in STEMS:
            return self._send(400, {"error": f"bad stem {stem!r}"})
        GT.mkdir(exist_ok=True)
        out = {
            "image": f"{stem}.{EXT[stem]}",
            "points": d.get("points", []),
            "occluded": d.get("occluded", []),
            "source": "human_ground_truth",
        }
        (GT / f"{stem}.json").write_text(json.dumps(out, indent=2))
        return self._send(200, {"ok": True, "saved": f"ground_truth/{stem}.json"})

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print("ground-truth app on http://localhost:8039  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", 8039), Handler).serve_forever()
