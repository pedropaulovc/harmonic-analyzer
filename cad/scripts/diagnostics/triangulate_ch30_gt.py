r"""Triangulate the ch30 eight-views ground-truth annotations into machine coords.

Bundle adjustment over the 8 book photos (`references/.../ch30_images`) using the
human ground truth from `research/1-research-documentation/039-ch30-annotation-
benchmark/ground_truth/`. Solves, jointly:

* one pinhole camera per view (position, yaw/pitch/roll, focal shared per image
  group: the 4 tall views vs the 4 three-quarter views);
* the top-frame casting outer silhouette extents (TX, TY_top, TZ) as free global
  parameters (the model's nominal 208/1040.7/123 looked too small against the
  pixels — measure, don't assume);
* the 3D machine positions of the drive-train features (crank sprocket, cone
  big-end, alignment-pinion ends, cylinder-drum ends).

Anchors: the 4 base-slab bottom corners at (±228.6, 0, ±139.7) — base 457.2 ×
279.4 from the ch6 p.3 callouts (annotated, HIGH) — are the only fixed-scale
landmarks; everything else floats.

MACHINE WORLD FRAME (the SLDASM frame): +y up from the base bottom, front at
-z, and +x on the viewer's LEFT when facing the front (so the drive train lives
at world x < 0; the "dimensions frame" used in dimensions.yaml prose is this
frame with x negated — see _transforms.py mirror rationale).

SolidWorks-free. Run:

    uv run python cad/scripts/diagnostics/triangulate_ch30_gt.py [--overlays DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
GT_DIR = (
    REPO
    / "research"
    / "1-research-documentation"
    / "039-ch30-annotation-benchmark"
    / "ground_truth"
)
IMG_DIR = REPO / "references" / "albert-michelsons-harmonic-analyzer" / "ch30_images"

# ---------------------------------------------------------------- fixed world
BASE_X, BASE_Z = 228.6, 139.7  # half-extents, ch6 annotated (457.2 x 279.4)

# corner name -> world (x, y, z); "left" = viewer-left facing the front = +x
def corner_world(name: str, top: np.ndarray) -> np.ndarray:
    tx, ty, tz = top
    _, _, kind, fb, lr = name.split("_")  # analyzer_corner_<top|base>_<fb>_<lr>
    x_half = {"base": BASE_X, "top": tx}[kind]
    z_half = {"base": BASE_Z, "top": tz}[kind]
    y = {"base": 0.0, "top": ty}[kind]
    x = +x_half if lr == "left" else -x_half
    z = -z_half if fb == "front" else +z_half
    return np.array([x, y, z])


# view -> (image size, init azimuth deg, init distance mm, focal group)
# Azimuth convention: az=0 -> camera on the front (-z) side looking +z; the
# camera orbits so that az=90 puts it on the world +x side. Init azimuths are
# derived from which corners each GT file marks visible (the SPEC's view labels
# use the opposite left/right convention).
VIEWS = {
    "page002_img01": ((1749, 4143), 0.0, 3000.0, "tall"),
    "page003_img01": ((1204, 2854), 315.0, 3500.0, "quarter"),
    "page004_img01": ((1776, 4209), 270.0, 3000.0, "tall"),
    "page005_img01": ((1204, 2854), 225.0, 3500.0, "quarter"),
    "page006_img01": ((1732, 4104), 180.0, 3000.0, "tall"),
    "page007_img01": ((1242, 2870), 135.0, 3500.0, "quarter"),
    "page008_img01": ((1789, 4239), 90.0, 3000.0, "tall"),
    "page009_img01": ((1204, 2854), 45.0, 3500.0, "quarter"),
}
FOCAL_GROUPS = ["tall", "quarter"]

# feature clusters: (solver key, views that mark the SAME physical point).
# End-on features (drum/pinion ends) are marked on the near face per side, so
# front-side and back-side clicks are separate 3D points sharing an axis.
FRONT_VIEWS = {"page002_img01", "page003_img01", "page009_img01"}
BACK_VIEWS = {"page005_img01", "page006_img01", "page007_img01"}


def feature_key(feature: str, view: str) -> str | None:
    if feature == "crank_axle_sprocket_center":
        return "crank_sprocket"
    if feature == "cone_gear_center":
        # front-side views see the big-end face; back-side views the small tip end
        return "cone_front" if view in FRONT_VIEWS else "cone_back"
    if feature == "pinion_center":
        return "pinion_front" if view in FRONT_VIEWS else "pinion_back"
    if feature == "cylinder_gear_center_1":
        return "cyl_front" if view in FRONT_VIEWS else "cyl_back"
    return None  # rocker corners: per-view arms, reported separately


FEATURE_INIT = {  # world frame (x<0 = drive side)
    "crank_sprocket": [-125.0, 126.8, -146.0],
    "cone_front": [-100.0, 126.8, -60.0],
    "cone_back": [-100.0, 126.8, 75.0],
    "pinion_front": [-15.0, 100.0, -80.0],
    "pinion_back": [-15.0, 100.0, 70.0],
    "cyl_front": [-54.0, 126.8, -98.0],
    "cyl_back": [-54.0, 126.8, 78.0],
}
TOP_INIT = [208.0, 1040.7, 123.0]  # model nominal (build_top_frame.py)
COL_INIT = [197.0, 112.0]  # column centres (±X, ±Z), model nominal
TUBE_R = 25.4 / 2.0  # column OD 25.4 (M6.11)

# Tube-silhouette observations: (view, image row v, [(sx, sz) tube signs], a, b)
# where [a, b] is the measured bright run (px) of the merged tube pair in that
# row. These break the focal/distance degeneracy the near-coplanar corner sets
# leave (the run's width + pair separation encode true perspective), and they
# solve the actual column positions. Measured from 16px-band brightness
# profiles (threshold 60) on the tall views.
TUBE_OBS = [
    ("page002_img01", 900, [(+1, -1), (+1, +1)], 165, 285),
    ("page002_img01", 900, [(-1, -1), (-1, +1)], 1486, 1612),
    ("page002_img01", 1500, [(+1, -1), (+1, +1)], 172, 287),
    ("page002_img01", 1500, [(-1, -1), (-1, +1)], 1481, 1608),
    ("page002_img01", 2600, [(-1, -1), (-1, +1)], 1479, 1601),
    ("page006_img01", 900, [(-1, -1), (-1, +1)], 148, 263),
    ("page006_img01", 900, [(+1, -1), (+1, +1)], 1474, 1586),
    ("page006_img01", 1500, [(-1, -1), (-1, +1)], 153, 265),
    ("page004_img01", 900, [(+1, -1), (-1, -1)], 522, 661),
    ("page004_img01", 900, [(+1, +1), (-1, +1)], 1303, 1390),
    ("page004_img01", 1500, [(+1, -1), (-1, -1)], 527, 663),
    ("page004_img01", 1500, [(+1, +1), (-1, +1)], 1303, 1390),
    ("page004_img01", 2600, [(+1, +1), (-1, +1)], 1305, 1390),
    ("page008_img01", 900, [(+1, +1), (-1, +1)], 443, 564),
    ("page008_img01", 900, [(+1, -1), (-1, -1)], 1185, 1313),
    ("page008_img01", 1500, [(+1, +1), (-1, +1)], 448, 565),
    ("page008_img01", 1500, [(+1, -1), (-1, -1)], 1186, 1310),
    ("page008_img01", 2600, [(+1, +1), (-1, +1)], 454, 557),
]

# current model positions (machine world frame) for the comparison table
# (2026-07-14 mesh rederive: drive plane y 104.8, crank (-122.8, 142.733), chain
# plane z -155, alignment pinion restored -- build_drive_train_assembly)
MODEL_NOW = {
    "crank_sprocket": (-122.8, 142.73308686, -155.0),  # T12 chain-wheel mid-plane
    "cone_front": (-116.05, 104.8, -60.47),  # T120 big-end centre
    "cone_back": (-80.99, 104.8, 97.44),  # shaft tip (station 190; GT wants
    # z ~101.8 -- deferred to the portal/back-frame re-layout)
    "cyl_front": (-54.7, 104.8, -90.0),  # arbor south end (ARBOR_SOUTH_Z)
    "cyl_back": (-54.7, 104.8, 78.0),  # arbor north end (GT wants ~91.5 --
    # deferred with the north bearing / helical end gears)
    "pinion_front": (-10.38, 104.8, -144.0),  # tee-handle hub (HANDLE_Z)
    "pinion_back": (-10.38, 104.8, 91.25),  # back stub free end
    "top_frame": (208.0, 1040.7, 123.0),
}


# ------------------------------------------------------------------- camera
def cam_rotation(yaw: float, pitch: float, roll: float) -> np.ndarray:
    """Rows = camera right/up/forward in world coords. yaw=0 -> forward +z."""
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    fwd = np.array([-sy * cp, sp, cy * cp])
    up0 = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up0)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    # roll about forward
    right, up = (
        cr * right + sr * up,
        -sr * right + cr * up,
    )
    return np.stack([right, up, fwd])


def project(cam: np.ndarray, f: float, size: tuple[int, int], P: np.ndarray) -> np.ndarray:
    """cam = [Cx,Cy,Cz,yaw,pitch,roll,dcx,dcy]; P (...,3) world mm -> (...,2) px.

    (dcx, dcy) shift the principal point off the image centre: the book plates
    are asymmetric CROPS of the original photographs, so the optical axis need
    not pierce the crop centre (it visibly doesn't, vertically).
    """
    R = cam_rotation(cam[3], cam[4], cam[5])
    q = (np.atleast_2d(P) - cam[:3]) @ R.T
    u = size[0] / 2.0 + cam[6] + f * q[:, 0] / q[:, 2]
    v = size[1] / 2.0 + cam[7] - f * q[:, 1] / q[:, 2]
    return np.stack([u, v], axis=1)


# ------------------------------------------------------------------ problem
class Problem:
    def __init__(self) -> None:
        self.obs: list[tuple[str, str, float, float]] = []  # view, target, u, v
        for path in sorted(GT_DIR.glob("page*.json")):
            data = json.loads(path.read_text())
            view = path.stem
            for p in data["points"]:
                name = p["feature"]
                if name.startswith("analyzer_corner_"):
                    self.obs.append((view, name, p["x"], p["y"]))
                    continue
                key = feature_key(name, view)
                if key:
                    self.obs.append((view, "@" + key, p["x"], p["y"]))
        self.view_names = list(VIEWS)
        self.feat_names = list(FEATURE_INIT)

    # parameter vector layout:
    #   per view: C(3), yaw, pitch, roll, dcx, dcy  (8)  x 8
    #   focals: f_tall, f_quarter                   (2)
    #   top: TX, TY, TZ                             (3)
    #   columns: col_X, col_Z                       (2)
    #   per feature: (3)                            x 7
    NC = 8  # params per camera

    def x0(self) -> np.ndarray:
        xs = []
        for v in self.view_names:
            _, az_deg, dist, _ = VIEWS[v]
            az = math.radians(az_deg)
            fwd = np.array([-math.sin(az), 0.0, math.cos(az)])
            C = np.array([0.0, 530.0, 0.0]) - fwd * dist
            xs += [*C, az, 0.0, 0.0, 0.0, 0.0]
        xs += [3300.0, 2400.0]
        xs += TOP_INIT
        xs += COL_INIT
        for k in self.feat_names:
            xs += FEATURE_INIT[k]
        return np.array(xs, float)

    def unpack(self, x: np.ndarray):
        nv = len(self.view_names)
        cams = {
            v: x[i * self.NC : (i + 1) * self.NC]
            for i, v in enumerate(self.view_names)
        }
        f = {"tall": x[nv * self.NC], "quarter": x[nv * self.NC + 1]}
        top = x[nv * self.NC + 2 : nv * self.NC + 5]
        col = x[nv * self.NC + 5 : nv * self.NC + 7]
        base = nv * self.NC + 7
        feats = {
            k: x[base + 3 * i : base + 3 * i + 3]
            for i, k in enumerate(self.feat_names)
        }
        return cams, f, top, col, feats

    def _tube_run_pred(self, cam, fv, size, col, signs, v_row):
        """Predicted [min, max] image-u span of a merged tube pair at row v."""
        edges = []
        for sx, sz in signs:
            P = np.array([sx * col[0], 550.0, sz * col[1]])
            for _ in range(3):  # Newton on y so the tube's projection hits v_row
                uv = project(cam, fv, size, P)[0]
                uv2 = project(cam, fv, size, P + [0.0, 1.0, 0.0])[0]
                dv = uv2[1] - uv[1]
                if abs(dv) < 1e-9:
                    break
                P[1] += (v_row - uv[1]) / dv
            uv = project(cam, fv, size, P)[0]
            R = cam_rotation(cam[3], cam[4], cam[5])
            d = ((P - cam[:3]) @ R.T)[2]
            half = fv * TUBE_R / d
            edges += [uv[0] - half, uv[0] + half]
        return min(edges), max(edges)

    def residuals(self, x: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
        cams, f, top, col, feats = self.unpack(x)
        res = []
        for view, target, u, v in self.obs:
            P = feats[target[1:]] if target.startswith("@") else corner_world(target, top)
            size, _, _, grp = VIEWS[view]
            uv = project(cams[view], f[grp], size, P)[0]
            res += [uv[0] - u, uv[1] - v]
        res = np.array(res)
        if weights is not None:
            res = res * np.repeat(weights, 2)
        pri = []
        # soft priors: roll ~ 0 (upright photos), pitch small, principal point
        # near the crop centre, focals near the physically-estimated values
        for i, v in enumerate(self.view_names):
            pri.append(x[i * self.NC + 5] / math.radians(1.5))  # roll
            pri.append(x[i * self.NC + 4] / math.radians(12.0))  # pitch
            pri.append(x[i * self.NC + 6] / 500.0)  # dcx
            pri.append(x[i * self.NC + 7] / 900.0)  # dcy
        nv = len(self.view_names)
        pri.append((x[nv * self.NC] - 3300.0) / 2000.0)  # f_tall
        pri.append((x[nv * self.NC + 1] - 2400.0) / 2000.0)  # f_quarter
        # tube-silhouette runs (see TUBE_OBS)
        tube = []
        for view, v_row, signs, a, b in TUBE_OBS:
            size, _, _, grp = VIEWS[view]
            pa, pb = self._tube_run_pred(cams[view], f[grp], size, col, signs, v_row)
            tube += [(pa - a) / 2.0, (pb - b) / 2.0]  # ~2 px edge noise
        return np.concatenate([res, pri, tube])

    def huber_weights(self, x: np.ndarray, k: float = 12.0) -> np.ndarray:
        """Per-observation robust weights from current pixel errors."""
        r = self.residuals(x)[: 2 * len(self.obs)].reshape(-1, 2)
        e = np.linalg.norm(r, axis=1)
        return np.minimum(1.0, k / np.maximum(e, 1e-9))

    def solve(self) -> np.ndarray:
        x = self.x0()
        weights = None
        for round_ in range(4):  # IRLS: LM passes with Huber reweighting between
            x = self._lm(x, weights)
            weights = self.huber_weights(x)
        return x

    def _lm(self, x: np.ndarray, weights) -> np.ndarray:
        lam = 1e-3
        r = self.residuals(x, weights)
        cost = r @ r
        for _ in range(120):
            J = self._jac(x, weights)
            g = J.T @ r
            H = J.T @ J
            improved = False
            dx = np.zeros_like(x)
            for _ in range(12):
                try:
                    dx = np.linalg.solve(H + lam * np.diag(np.diag(H) + 1e-9), -g)
                except np.linalg.LinAlgError:
                    lam *= 10
                    continue
                x_new = x + dx
                r_new = self.residuals(x_new, weights)
                c_new = r_new @ r_new
                if c_new < cost:
                    x, r, cost = x_new, r_new, c_new
                    lam = max(lam / 3, 1e-9)
                    improved = True
                    break
                lam *= 10
            if not improved or (np.abs(dx).max() < 1e-8):
                break
        return x

    def _jac(self, x: np.ndarray, weights) -> np.ndarray:
        r0 = self.residuals(x, weights)
        J = np.zeros((r0.size, x.size))
        for i in range(x.size):
            h = max(1e-6, 1e-7 * abs(x[i]))
            xp = x.copy()
            xp[i] += h
            J[:, i] = (self.residuals(xp, weights) - r0) / h
        return J


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlays", help="dir to write projection-overlay PNGs")
    ap.add_argument("--json-out", help="write solved values as JSON")
    ap.add_argument("--params-in", help="reuse a solved param vector (json with 'params') instead of re-solving")
    args = ap.parse_args()

    prob = Problem()
    if args.params_in:
        x = np.array(json.loads(Path(args.params_in).read_text())["params"], float)
    else:
        x = prob.solve()
    cams, f, top, col, feats = prob.unpack(x)
    r = prob.residuals(x)
    n_obs = sum(1 for _ in prob.obs) * 2
    px = r[:n_obs].reshape(-1, 2)
    err = np.linalg.norm(px, axis=1)
    tube_res = r[-2 * len(TUBE_OBS):] * 2.0

    # 1-sigma parameter uncertainties from the robust-weighted normal equations
    w = prob.huber_weights(x)
    Jw = prob._jac(x, w)
    sigma0 = np.sqrt(np.median(err[w >= 1.0] ** 2)) if (w >= 1.0).any() else 3.0
    try:
        cov = np.linalg.inv(Jw.T @ Jw) * sigma0**2
        psig = np.sqrt(np.maximum(np.diag(cov), 0.0))
    except np.linalg.LinAlgError:
        psig = np.full(x.size, np.nan)
    nv = len(prob.view_names)
    top_sig = psig[nv * prob.NC + 2 : nv * prob.NC + 5]
    col_sig = psig[nv * prob.NC + 5 : nv * prob.NC + 7]
    fbase = nv * prob.NC + 7
    feat_sig = {
        k: psig[fbase + 3 * i : fbase + 3 * i + 3]
        for i, k in enumerate(prob.feat_names)
    }

    print(f"observations: {len(prob.obs)}  rms px error: {np.sqrt((err**2).mean()):.2f}"
          f"  median: {np.median(err):.2f}  max: {err.max():.2f}")
    print(f"focals: tall {f['tall']:.0f}px  quarter {f['quarter']:.0f}px")
    print(f"top frame solved: TX ±{top[0]:.1f}±{top_sig[0]:.1f}  "
          f"TY {top[1]:.1f}±{top_sig[1]:.1f}  TZ ±{top[2]:.1f}±{top_sig[2]:.1f}"
          f"   (model nominal ±208 / 1040.7 / ±123)")
    print(f"columns solved: X ±{col[0]:.1f}±{col_sig[0]:.1f}  Z ±{col[1]:.1f}±{col_sig[1]:.1f}"
          f"   (model nominal ±197 / ±112)"
          f"   tube-run rms {np.sqrt((tube_res**2).mean()):.1f} px")
    for v in prob.view_names:
        c = cams[v]
        print(f"  {v}: C=({c[0]:8.1f},{c[1]:7.1f},{c[2]:8.1f}) "
              f"yaw={math.degrees(c[3]):7.2f} pitch={math.degrees(c[4]):6.2f} "
              f"roll={math.degrees(c[5]):5.2f}")
    print("\nfeature positions, machine WORLD frame (x<0 = drive side), ±1sigma mm:")
    for k in prob.feat_names:
        p = feats[k]
        s = feat_sig[k]
        now = MODEL_NOW.get(k)
        now_s = f"model now ({now[0]:8.2f},{now[1]:7.2f},{now[2]:8.2f})" if now else "model: absent"
        views = [o[0][4:7] for o in prob.obs if o[1] == "@" + k]
        errs = [err[i] for i, o in enumerate(prob.obs) if o[1] == "@" + k]
        print(f"  {k:15s} ({p[0]:8.2f}±{s[0]:4.1f},{p[1]:7.2f}±{s[1]:4.1f},"
              f"{p[2]:8.2f}±{s[2]:4.1f})  {now_s}"
              f"   views p{'/p'.join(views)}  px err {', '.join(f'{e:.0f}' for e in errs)}")
    print("\nper-observation residuals > 15 px:")
    for i, (view, target, *_uv) in enumerate(prob.obs):
        if err[i] > 15:
            print(f"  {view} {target}: {err[i]:.1f} px")

    if args.json_out:
        out = {
            "top_frame": {"TX": top[0], "TY": top[1], "TZ": top[2]},
            "columns": {"X": col[0], "Z": col[1]},
            "features": {k: list(map(float, feats[k])) for k in prob.feat_names},
            "rms_px": float(np.sqrt((err**2).mean())),
            "params": [float(v) for v in x],
        }
        Path(args.json_out).write_text(json.dumps(out, indent=1))

    if args.overlays:
        from PIL import Image, ImageDraw

        od = Path(args.overlays)
        od.mkdir(parents=True, exist_ok=True)
        for v in prob.view_names:
            imgs = list(IMG_DIR.glob(v + ".*"))
            if not imgs:
                continue
            im = Image.open(imgs[0]).convert("RGB")
            dr = ImageDraw.Draw(im)
            size, _, _, grp = VIEWS[v]
            cam_v, f_v = cams[v], f[grp]

            def prj(p):
                return project(cam_v, f_v, size, np.array(p, float))[0]

            # solved columns (BLUE) + the model drum axis (ORANGE)
            for cx_, cz_ in (
                (col[0], col[1]), (col[0], -col[1]),
                (-col[0], col[1]), (-col[0], -col[1]),
            ):
                a, b = prj([cx_, 50.8, cz_]), prj([cx_, 1040.7, cz_])
                dr.line([*a, *b], fill=(0, 100, 255), width=3)
            a, b = prj([-54.7, 104.8, -90.0]), prj([-54.7, 104.8, 78.0])
            dr.line([*a, *b], fill=(255, 140, 0), width=3)  # model drum axis
            for view, target, u, gv in prob.obs:
                if view != v:
                    continue
                P = feats[target[1:]] if target.startswith("@") else corner_world(target, top)
                uv = project(cam_v, f_v, size, P)[0]
                dr.ellipse([u - 8, gv - 8, u + 8, gv + 8], outline=(0, 255, 0), width=3)
                dr.ellipse([uv[0] - 5, uv[1] - 5, uv[0] + 5, uv[1] + 5], fill=(255, 0, 0))
                dr.line([u, gv, uv[0], uv[1]], fill=(255, 255, 0), width=2)
            im.resize((im.width // 3, im.height // 3)).save(od / f"{v}_overlay.png")
        print(f"overlays -> {od}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
