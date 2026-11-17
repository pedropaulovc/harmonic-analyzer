"""One-off converter: legacy content/*.source-track.json -> compact shot tables.

Run once from web/ with the release GLB in public/models (camera targets are
placed on visible geometry):

    uv run --no-project python scripts/convert-source-tracks.py

Writes content/tracks/<slug>.json and content/cameras.json, then replays the
legacy runtime semantics (src/source-track.ts at origin/main ebd3bf3b44) and the
new shot-table semantics (src/track.ts) at every legacy sample time and each
midpoint, printing the worst camera (source pixels) and input deviations.
Legacy non-operating source assemblies (manual bars, measuring tool, gear
change, pen) are not rendered by the new runtime; their rows are marked
"review": "unverified". The legacy tracks are deleted after this conversion;
this script is kept in history only and is not part of the build.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
CONTENT = WEB / "content"
SLUGS = {
    "NAsM30MAHLg": "intro-history",
    "8KmVDxkia_w": "synthesis",
    "6dW6VYXp9HM": "analysis",
    "jfH-NbsmvD4": "operation",
    "XPQwKRt4Y2k": "machine-spin",
    "4mBuyixt22U": "rocker-arms",
}
SETUP_KEYS = (
    "counterHeightM", "meanLineAngleRad", "platenOffsetM", "wireFixtureOffsetM",
    "coneSwingRad", "pinionCamRad", "heldChannelTurns", "driveCrankOffsetTurns",
)
DEFAULT_MAGNIFICATION = 165 / 39.85
# Linear-merge tolerances per interpolated field (units of the field).
TOL = {
    "crankTurns": 0.002, "magnification": 0.002,
    "counterHeightM": 0.0002, "meanLineAngleRad": 0.0005, "platenOffsetM": 0.0001,
    "wireFixtureOffsetM": 0.0001, "coneSwingRad": 0.0005, "pinionCamRad": 0.001,
    "heldChannelTurns": 0.002, "driveCrankOffsetTurns": 0.002,
}
CAMERA_TOL_PX = 1.0  # source pixels (1080-line frame)
PHASE = 2 * math.pi
# Readable names for the most-used cameras (by rendered seconds), chosen by eye.
CAMERA_NAMES: dict[str, str] = {
    "rocker-arms-1": "rocker-bank-closeup", "operation-1": "platen-front", "intro-history-1": "front-full",
    "operation-2": "front-full-high", "operation-3": "crank-chain-oblique", "operation-4": "drive-front",
    "operation-5": "magnifier-lever", "synthesis-1": "rocker-springs-front", "synthesis-2": "spring-bank-low",
    "intro-history-2": "front-full-far", "operation-6": "pen-overhead", "analysis-1": "rocker-bars",
    "operation-7": "drive-oblique-low", "operation-8": "paper-sprocket", "synthesis-3": "counter-spring",
    "operation-9": "pen-closeup", "operation-10": "magnifier-wheel", "synthesis-4": "front-full-tall",
    "operation-11": "magnifier-rod", "operation-12": "pen-platen",
}


# --------------------------------------------------------------------------- geometry

def quat_rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a, b, f):
    return a + (b - a) * f


def lerp3(a, b, f):
    return tuple(lerp(a[i], b[i], f) for i in range(len(a)))


def slerp(a, b, f):
    d = dot4(a, b)
    if d < 0:
        b = tuple(-c for c in b)
        d = -d
    if d > 0.9995:
        r = tuple(lerp(a[i], b[i], f) for i in range(4))
    else:
        th = math.acos(d)
        s = math.sin(th)
        wa, wb = math.sin((1 - f) * th) / s, math.sin(f * th) / s
        r = tuple(wa * a[i] + wb * b[i] for i in range(4))
    n = math.sqrt(dot4(r, r))
    return tuple(c / n for c in r)


def dot4(a, b):
    return sum(a[i] * b[i] for i in range(4))


def load_glb_points(path: Path):
    data = path.read_bytes()
    length = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + length])

    def mat(node):
        if "matrix" in node:
            m = node["matrix"]
            return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
        x, y, z, w = node.get("rotation", [0, 0, 0, 1])
        s = node.get("scale", [1, 1, 1])
        t = node.get("translation", [0, 0, 0])
        r = [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
        return [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)] + [[0, 0, 0, 1]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]

    points = []

    def walk(index, parent):
        node = gltf["nodes"][index]
        world = mul(parent, mat(node))
        if "mesh" in node:
            points.append((world[0][3], world[1][3], world[2][3]))
        for child in node.get("children", []):
            walk(child, world)

    identity = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        walk(root, identity)
    return points


class Cam:
    """position/quaternion/fov/principal (fraction of tile) camera."""

    def __init__(self, position, quaternion, fov, principal):
        self.p = tuple(position)
        n = math.sqrt(dot4(quaternion, quaternion))
        self.q = tuple(c / n for c in quaternion)
        self.fov = fov
        self.pp = tuple(principal)

    def axes(self):
        return quat_rotate(self.q, (1, 0, 0)), quat_rotate(self.q, (0, 1, 0)), quat_rotate(self.q, (0, 0, -1))

    def project(self, point, w, h):
        right, up, forward = self.axes()
        d = sub(point, self.p)
        z = dot(d, forward)
        if z <= 1e-6:
            return None
        f = (h / 2) / math.tan(math.radians(self.fov) / 2)
        return (self.pp[0] * w + f * dot(d, right) / z, self.pp[1] * h - f * dot(d, up) / z)

    def unproject(self, u, v, depth, w, h):
        right, up, forward = self.axes()
        f = (h / 2) / math.tan(math.radians(self.fov) / 2)
        x = (u - self.pp[0] * w) / f
        y = -(v - self.pp[1] * h) / f
        return add(self.p, add(scale(forward, depth), add(scale(right, x * depth), scale(up, y * depth))))


def scene_depth(cam: Cam, points, w, h):
    cached = cam.__dict__.get("_depth")
    if cached is not None and cached[0] == (w, h):
        return cached[1]
    right, up, forward = cam.axes()
    depths = []
    for p in points:
        uv = cam.project(p, w, h)
        if uv and 0 <= uv[0] <= w and 0 <= uv[1] <= h:
            depths.append(dot(sub(p, cam.p), forward))
    if not depths:
        centre = (0.0, 0.3, -0.05)
        depth = max(0.05, dot(sub(centre, cam.p), forward))
    else:
        depths.sort()
        depth = depths[len(depths) // 2]
    cam._depth = ((w, h), depth)
    return depth


_ERRORS: dict = {}


def camera_error_px(a: Cam, b: Cam, w, h, points):
    """Max source-pixel displacement of a 3x3 grid of scene-depth points."""
    key = (id(a), id(b), w, h)
    if key in _ERRORS and _ERRORS[key][0] is a and _ERRORS[key][1] is b:
        return _ERRORS[key][2]
    worst = 0.0
    for first, second in ((a, b), (b, a)):
        depth = scene_depth(first, points, w, h)
        for fu in (0.1, 0.5, 0.9):
            for fv in (0.1, 0.5, 0.9):
                world = first.unproject(fu * w, fv * h, depth, w, h)
                pa = first.project(world, w, h)
                pb = second.project(world, w, h)
                if pb is None:
                    worst = math.inf
                    break
                worst = max(worst, math.hypot(pa[0] - pb[0], pa[1] - pb[1]))
    _ERRORS[key] = (a, b, worst)
    return worst


# ----------------------------------------------------------------- legacy semantics

def legacy_camera(view):
    c = view["camera"]
    w, h = view["rectSourcePixels"][2], view["rectSourcePixels"][3]
    pp = c.get("principalPointViewportPixels")
    principal = (0.5, 0.5) if pp is None else (pp[0] / w, pp[1] / h)
    return Cam(c["positionMetres"], c["quaternion"], c["verticalFovDegrees"], principal)


def required_view(frame, view):
    if "sourceVisibility" in view:
        return False
    composite = view.get("composite")
    if composite and composite.get("mode") == "crossfade" and composite.get("opacity") == 0:
        return False
    if view.get("imagePlaneWarp") or view.get("imagePlaneWarpMeasurement"):
        return True
    views = frame["views"]
    own = view["rectSourcePixels"]
    for later in views[views.index(view) + 1:]:
        other = later.get("composite")
        rect = later["rectSourcePixels"]
        if later.get("imagePlaneWarp") or later.get("imagePlaneWarpMeasurement"):
            continue
        if other and other.get("mode") == "crossfade" and (
            other.get("opacity") != 1 or (
                composite and composite.get("mode") == "crossfade"
                and composite["groupId"] == other["groupId"] and composite["imageLayerId"] != other["imageLayerId"])):
            continue
        if rect[0] <= own[0] and rect[1] <= own[1] and rect[0] + rect[2] >= own[0] + own[2] and rect[1] + rect[3] >= own[1] + own[3]:
            return False
    return True


def layout_key(view):
    return (view["id"], tuple(view["rectSourcePixels"]), view["presentation"],
            json.dumps(view.get("composite") or {"mode": "opaque"}, sort_keys=True),
            json.dumps(view.get("imagePlaneWarp"), sort_keys=True))


def compile_legacy(track):
    shots = {shot["id"]: shot for shot in track["shots"]}
    frames = []
    for frame in track["frames"]:
        shot = shots[frame["shotId"]]
        cls = frame["classification"]
        corresponding = shot.get("hasCorrespondingMachine")
        otherwise = (frame.get("sourceMachineRequirement") == "required" or cls == "machine"
                     or ((corresponding is True) if cls == "non-machine" else (corresponding is not False)))
        source_required = otherwise or len(frame["views"]) > 0
        views = [view for view in frame["views"] if required_view(frame, view)]
        required = source_required and (len(frame["views"]) == 0 or len(views) > 0)
        available = frame["decodedTimeSeconds"] is not None and (
            not required or (views and all(v.get("input") is not None and v.get("camera") is not None for v in views)))
        frames.append({"t": frame["timeSeconds"], "shot": shot, "required": required, "available": bool(available),
                       "views": views, "id": frame["shotId"], "cont": False, "camInterp": []})
    for a, b in zip(frames, frames[1:]):
        cont = (a["available"] and b["available"] and a["required"] and b["required"] and a["id"] == b["id"]
                and len(a["views"]) == len(b["views"])
                and [layout_key(v) for v in a["views"]] == [layout_key(v) for v in b["views"]]
                and all(va["id"] == vb["id"] and va["input"]["gearing"] == vb["input"]["gearing"]
                        and (va["input"]["setup"]["counterHeightM"] is None) == (vb["input"]["setup"]["counterHeightM"] is None)
                        for va, vb in zip(a["views"], b["views"])))
        a["cont"] = bool(cont)
        if cont:
            interp = []
            for va, vb in zip(a["views"], b["views"]):
                pa, pb = va.get("cameraProvenance"), vb.get("cameraProvenance")
                interp.append(bool(
                    va.get("cameraInterpolation") != "held" and vb.get("cameraInterpolation") != "held"
                    and isinstance(va.get("cameraContinuityFamily"), str)
                    and va.get("cameraContinuityFamily") == vb.get("cameraContinuityFamily")
                    and pa is not None and pb is not None
                    and ((pa["kind"] != "source-informed-framing" and pb["kind"] != "source-informed-framing")
                         or (va.get("cameraInterpolation") == "continuous-shot" and vb.get("cameraInterpolation") == "continuous-shot"))
                    and pa["family"] == pb["family"]))
            a["camInterp"] = interp
    return frames


def legacy_state(frames, duration, t):
    """(kind, views) where kind is approx|hold; views are [(rect, mirror, Cam, inputDict, assemblyJson)]."""
    t = max(0.0, min(duration, t))
    lo, hi = 0, len(frames)
    while lo < hi:
        mid = (lo + hi) // 2
        if frames[mid]["t"] <= t:
            lo = mid + 1
        else:
            hi = mid
    index = max(0, lo - 1)
    frame = frames[index]
    shot = frame["shot"]
    unavailable = (frame["t"] > t or t < shot["startSeconds"] or t > shot["endSeconds"]
                   or (t == shot["endSeconds"] and t < duration) or not frame["available"])
    if unavailable or not frame["required"]:
        return "hold", None
    nxt = frames[index + 1] if index + 1 < len(frames) else None
    mix = (t - frame["t"]) / (nxt["t"] - frame["t"]) if frame["cont"] else 0.0
    out = []
    for i in tile_layout(frame):
        view = frame["views"][i]
        inp = dict(view["input"])
        cam = legacy_camera(view)
        if frame["cont"]:
            other = nxt["views"][i]
            inp = blend_input(view["input"], other["input"], mix)
            if frame["camInterp"][i]:
                oc = legacy_camera(other)
                cam = Cam(lerp3(cam.p, oc.p, mix), slerp(cam.q, oc.q, mix), lerp(cam.fov, oc.fov, mix), lerp3(cam.pp, oc.pp, mix))
        out.append((tuple(view["rectSourcePixels"]), view["presentation"] == "horizontal-mirror", cam, inp, assembly_of(view)))
    return "approx", out


def phase_delta(a, b):
    d = ((b % PHASE) - (a % PHASE)) % PHASE
    if d >= math.pi:
        d -= PHASE
    elif d < -math.pi:
        d += PHASE
    return d


def blend_input(a, b, mix):
    out = {"crankTurns": lerp(a["crankTurns"], b["crankTurns"], mix),
           "magnification": lerp(a["magnification"], b["magnification"], mix),
           "gearing": a["gearing"],
           "amplitudes": [lerp(x, y, mix) for x, y in zip(a["amplitudes"], b["amplitudes"])],
           "phases": [x + phase_delta(x, y) * mix for x, y in zip(a["phases"], b["phases"])],
           "setup": dict(a["setup"])}
    for key in SETUP_KEYS:
        x, y = a["setup"][key], b["setup"][key]
        if x is not None and y is not None:
            out["setup"][key] = lerp(x, y, mix)
    return out


def assembly_of(view):
    state = view.get("sourceAssembly")
    if not state or state.get("kind") == "operating":
        return None
    return {key: value for key, value in state.items() if key not in ("kind", "provenance")}


# ------------------------------------------------------------------ conversion

class Knot:
    """Exact legacy state of one view at a sample time."""

    def __init__(self, view):
        self.cam = legacy_camera(view)
        self.input = view["input"]
        self.assembly = assembly_of(view)


def numeric_fields(inp):
    values = {"crankTurns": inp["crankTurns"], "magnification": inp["magnification"]}
    for key in SETUP_KEYS:
        if inp["setup"][key] is not None:
            values[key] = inp["setup"][key]
    return values


def build_rows(frames, duration, points):
    intervals = []  # (t0, t1, kind, frame index)
    for i, frame in enumerate(frames):
        t0 = frame["t"]
        t1 = frames[i + 1]["t"] if i + 1 < len(frames) else duration
        end = min(t1, frame["shot"]["endSeconds"]) if i + 1 < len(frames) else t1
        if t0 >= end:
            continue
        kind = "approx" if frame["available"] and frame["required"] else "hold"
        intervals.append((t0, end, kind, i))
        if end < t1:
            intervals.append((end, t1, "hold", None))
    if intervals and intervals[0][0] > 0:
        intervals.insert(0, (0.0, intervals[0][0], "hold", None))

    rows = []
    i = 0
    while i < len(intervals):
        t0, t1, kind, index = intervals[i]
        if kind == "hold":
            rows.append({"start": t0, "end": t1, "mode": "hold"})
            i += 1
            continue
        run = [intervals[i]]
        while (i + len(run) < len(intervals) and frames[run[-1][3]]["cont"]
               and intervals[i + len(run)][2] == "approx" and intervals[i + len(run)][3] == run[-1][3] + 1
               and intervals[i + len(run)][0] == run[-1][1]):
            run.append(intervals[i + len(run)])
        rows.extend(rows_for_run(frames, run, points))
        i += len(run)
    return merge_rows(rows)


def tile_layout(frame):
    """Visible tiles: drop the weaker layer of overlapping crossfades."""
    views = frame["views"]
    keep = []
    for view in views:
        rect = view["rectSourcePixels"]
        weight = (view.get("composite") or {}).get("opacity", 1) if (view.get("composite") or {}).get("mode") == "crossfade" else 1
        replaced = False
        for k, (other, other_weight) in enumerate(keep):
            orect = other["rectSourcePixels"]
            if rect[0] < orect[0] + orect[2] and orect[0] < rect[0] + rect[2] and rect[1] < orect[1] + orect[3] and orect[1] < rect[1] + rect[3]:
                if weight >= other_weight:
                    keep[k] = (view, weight)
                replaced = True
                break
        if not replaced:
            keep.append((view, weight))
    return [views.index(view) for view, _ in keep]


def rows_for_run(frames, run, points):
    first = frames[run[0][3]]
    tile_indices = tile_layout(first)
    rects = [first["views"][k]["rectSourcePixels"] for k in tile_indices]
    times = [interval[0] for interval in run] + [run[-1][1]]
    # knots[s][tile] state at start of segment s; segment s spans times[s]..times[s+1].
    knots = [[Knot(frames[interval[3]]["views"][k]) for k in tile_indices] for interval in run]
    interp_input = [frames[interval[3]]["cont"] for interval in run]
    interp_cam = [[frames[interval[3]]["camInterp"][k] if frames[interval[3]]["cont"] else False for k in tile_indices] for interval in run]
    n = len(run)

    def left_limit(segment, tile):
        """State at the end of segment (approached from the left)."""
        if interp_input[segment] and segment + 1 < n:
            return knots[segment + 1][tile]
        if interp_input[segment] and segment + 1 == n:
            # the last interval may be cut short by its shot end: blend there
            index = run[segment][3]
            frame, nxt = frames[index], frames[index + 1]
            mix = (times[segment + 1] - frame["t"]) / (nxt["t"] - frame["t"])
            view = frame["views"][tile_indices[tile]]
            other = nxt["views"][tile_indices[tile]]
            knot = Knot(view)
            knot.input = blend_input(view["input"], other["input"], mix)
            if interp_cam[segment][tile]:
                a, b = legacy_camera(view), legacy_camera(other)
                knot.cam = Cam(lerp3(a.p, b.p, mix), slerp(a.q, b.q, mix), lerp(a.fov, b.fov, mix), lerp3(a.pp, b.pp, mix))
            return knot
        return knots[segment][tile]

    def end_cam(segment, tile):
        if interp_cam[segment][tile]:
            return left_limit(segment, tile).cam
        return knots[segment][tile].cam

    def representable(s0, m):
        """Row covering segments s0..m-1 as one linear row; returns tile specs or None."""
        specs = []
        for tile in range(len(tile_indices)):
            k0 = knots[s0][tile]
            end = left_limit(m - 1, tile)
            w, h = rects[tile][2], rects[tile][3]
            # channel preset, gearing and assembly are constant within a row
            # (amplitude blends get presetEnd only for single-segment rows).
            for s in range(s0, m):
                ks = knots[s][tile]
                if ks.input["gearing"] != k0.input["gearing"] or ks.assembly != k0.assembly:
                    return None
                if s > s0 and (ks.input["amplitudes"] != k0.input["amplitudes"] or ks.input["phases"] != k0.input["phases"]):
                    return None
            blend_channels = end.input["amplitudes"] != k0.input["amplitudes"] or end.input["phases"] != k0.input["phases"]
            if blend_channels and m - s0 > 1:
                return None
            # numeric fields: linear from k0 to end, checked at interior knots
            a, b = numeric_fields(k0.input), numeric_fields(end.input)
            if set(a) != set(b):
                return None
            span = times[m] - times[s0]
            for s in range(s0 + 1, m):
                f = (times[s] - times[s0]) / span
                values = numeric_fields(knots[s][tile].input)
                if set(values) != set(a):
                    return None
                for key, value in values.items():
                    if abs(lerp(a[key], b[key], f) - value) > TOL[key]:
                        return None
                # a constant segment followed by a step is not linear
                if not interp_input[s - 1] and numeric_fields(knots[s - 1][tile].input) != values:
                    return None
            if not interp_input[m - 1] and m - s0 > 1:
                if numeric_fields(knots[m - 1][tile].input) != numeric_fields(knots[m - 2][tile].input) and not interp_input[m - 2]:
                    return None
            # camera: static or a single linear move
            moving = any(interp_cam[s][tile] for s in range(s0, m))
            if moving:
                if not all(interp_cam[s][tile] for s in range(s0, m)):
                    return None
                cam_end = end_cam(m - 1, tile)
                for s in range(s0 + 1, m):
                    f = (times[s] - times[s0]) / span
                    guess = Cam(lerp3(k0.cam.p, cam_end.p, f), slerp(k0.cam.q, cam_end.q, f), lerp(k0.cam.fov, cam_end.fov, f), lerp3(k0.cam.pp, cam_end.pp, f))
                    if camera_error_px(guess, knots[s][tile].cam, w, h, points) > CAMERA_TOL_PX:
                        return None
            else:
                cam_end = None
                for s in range(s0 + 1, m):
                    if camera_error_px(k0.cam, knots[s][tile].cam, w, h, points) > CAMERA_TOL_PX:
                        return None
            specs.append({"k0": k0, "end": end, "camEnd": cam_end, "blend": blend_channels})
        return specs

    rows = []
    s0 = 0
    while s0 < n:
        m = s0 + 1
        best = representable(s0, m)
        assert best is not None, "single segment must be representable"
        while m + 1 <= n:
            candidate = representable(s0, m + 1)
            if candidate is None:
                break
            m += 1
            best = candidate
        rows.append({"start": times[s0], "end": times[m], "mode": "follow",
                     "tiles": [dict(spec, rect=rects[k], mirror=first["views"][tile_indices[k]]["presentation"] == "horizontal-mirror")
                               for k, spec in enumerate(best)]})
        s0 = m
    return rows


def merge_rows(rows):
    merged = []
    for row in rows:
        prev = merged[-1] if merged else None
        if prev and prev["mode"] == row["mode"] == "hold":
            prev["end"] = row["end"]
            continue
        merged.append(row)
    return merged


# ------------------------------------------------------------------ serialization

def r(value, digits):
    rounded = round(value, digits)
    return 0.0 if rounded == 0 else rounded


def camera_json(cam: Cam, w, h, points):
    right, up, forward = cam.axes()
    depth = scene_depth(cam, points, w, h)
    target = add(cam.p, scale(forward, depth))
    out = {"position": [r(c, 5) for c in cam.p], "target": [r(c, 5) for c in target], "fov": r(cam.fov, 4)}
    # roll relative to the default world-up look-at
    default_right = cross(forward, (0, 1, 0))
    if math.sqrt(dot(default_right, default_right)) < 1e-6:
        out["up"] = [r(c, 5) for c in up]
    else:
        default_up = cross(norm(default_right), forward)
        if dot(default_up, up) < math.cos(math.radians(0.002)):
            out["up"] = [r(c, 5) for c in up]
    if abs(cam.pp[0] - 0.5) > 1e-5 or abs(cam.pp[1] - 0.5) > 1e-5:
        out["principal"] = [r(cam.pp[0], 5), r(cam.pp[1], 5)]
    return out


def preset_name(amplitudes, phases, presets, slug):
    key = json.dumps([amplitudes, phases])
    for name, value in presets.items():
        if json.dumps([value["amplitudes"], value["phases"]]) == key:
            return name
    if not any(amplitudes) and not any(phases):
        name = "zero"
    else:
        name = f"{slug}-{len(presets) + 1}"
    presets[name] = {"amplitudes": [r(a, 6) for a in amplitudes], "phases": [r(p, 6) for p in phases]}
    # store exact for lookup, rounded for output
    presets[name]["_key"] = key
    return name


def find_preset(amplitudes, phases, presets, slug):
    key = json.dumps([amplitudes, phases])
    for name, value in presets.items():
        if value.get("_key") == key:
            return name
    if not any(amplitudes) and not any(phases):
        name = "zero"
    else:
        name = f"{slug}-{sum(1 for n in presets if n != 'zero') + 1}"
    presets[name] = {"amplitudes": [r(a, 6) for a in amplitudes], "phases": [r(p, 6) for p in phases], "_key": key}
    return name


def setup_json(inp):
    out = {}
    if inp["gearing"] != "small-large":
        out["gearing"] = inp["gearing"]
    if abs(inp["magnification"] - DEFAULT_MAGNIFICATION) > 1e-9:
        out["magnification"] = r(inp["magnification"], 6)
    for key in SETUP_KEYS:
        value = inp["setup"][key]
        if value is None or value == 0:
            continue
        out[key] = r(value, 7)
    return out


def setup_end_json(start, end):
    a, b = numeric_fields(start), numeric_fields(end)
    out = {}
    for key in a:
        if abs(a[key] - b[key]) > 1e-12 and key != "crankTurns":
            out[key] = r(b[key], 7 if key != "magnification" else 6)
    return out


def tile_json(spec, presets, slug, points, cameras):
    k0, end = spec["k0"], spec["end"]
    w, h = spec["rect"][2], spec["rect"][3]
    out = {}
    out["camera"] = camera_ref(camera_json(k0.cam, w, h, points), cameras)
    if spec["camEnd"] is not None:
        out["cameraEnd"] = camera_ref(camera_json(spec["camEnd"], w, h, points), cameras)
    out["crankTurns"] = [r(k0.input["crankTurns"], 6), r(end.input["crankTurns"], 6)]
    out["preset"] = find_preset(k0.input["amplitudes"], k0.input["phases"], presets, slug)
    if spec["blend"]:
        out["presetEnd"] = find_preset(end.input["amplitudes"], end.input["phases"], presets, slug)
    setup = setup_json(k0.input)
    if setup:
        out["setup"] = setup
    setup_end = setup_end_json(k0.input, end.input)
    if setup_end:
        out["setupEnd"] = setup_end
    return out


def camera_ref(camera, cameras):
    key = json.dumps(camera, sort_keys=True)
    for name, value in cameras.items():
        if json.dumps(value, sort_keys=True) == key:
            return name
    return camera


FULL = [0, 0, 1920, 1080]
SHARED = ("crankTurns", "preset", "presetEnd", "setup", "setupEnd")


def row_json(row, presets, slug, points, cameras):
    out = {"start": r(row["start"], 4), "end": r(row["end"], 4), "mode": row["mode"]}
    if row["mode"] == "hold":
        return out
    # Tiles that showed a photograph of loose parts (operation's gear icons) are
    # not a view of the machine; leave their rectangle empty.
    specs = [spec for spec in row["tiles"] if not (spec["k0"].assembly or {}).get("photograph")]
    if not specs:
        return {**out, "mode": "hold"}
    setup_state = any(spec["k0"].assembly is not None for spec in specs)
    tiles = []
    for spec in specs:
        tile = tile_json(spec, presets, slug, points, cameras)
        if spec["rect"] != FULL:
            tile = {"rect": spec["rect"], **tile}
        if spec["mirror"]:
            tile = {**tile, "mirror": True}
        tiles.append(tile)
    if len(tiles) == 1 and "rect" not in tiles[0] and "mirror" not in tiles[0]:
        out.update(tiles[0])
    else:
        for key in SHARED:
            values = [json.dumps(tile.get(key), sort_keys=True) for tile in tiles]
            if all(key in tile for tile in tiles) and len(set(values)) == 1:
                out[key] = tiles[0][key]
                for tile in tiles:
                    del tile[key]
        out["tiles"] = tiles
    if setup_state:
        out["review"] = "unverified"
    return out


def dumps_track(track):
    lines = ["{", f'  "video": {json.dumps(track["video"])},', '  "presets": {']
    names = list(track["presets"])
    for i, name in enumerate(names):
        comma = "," if i + 1 < len(names) else ""
        lines.append(f"    {json.dumps(name)}: {json.dumps(track['presets'][name], separators=(',', ':'))}{comma}")
    lines.append("  },")
    lines.append('  "shots": [')
    for i, shot in enumerate(track["shots"]):
        comma = "," if i + 1 < len(track["shots"]) else ""
        lines.append(f"    {json.dumps(shot, separators=(',', ':'))}{comma}")
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ new semantics (mirror of src/track.ts)

def resolve_camera(ref, cameras):
    return cameras[ref] if isinstance(ref, str) else ref


def camera_from_json(c):
    position = tuple(c["position"])
    forward = norm(sub(tuple(c["target"]), position))
    up_hint = tuple(c.get("up", (0, 1, 0)))
    right = norm(cross(forward, up_hint))
    up = cross(right, forward)
    # rotation matrix columns: right, up, -forward
    m = [[right[0], up[0], -forward[0]], [right[1], up[1], -forward[1]], [right[2], up[2], -forward[2]]]
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = 0.5 / math.sqrt(trace + 1)
        q = ((m[2][1] - m[1][2]) * s, (m[0][2] - m[2][0]) * s, (m[1][0] - m[0][1]) * s, 0.25 / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = 2 * math.sqrt(1 + m[0][0] - m[1][1] - m[2][2])
        q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = 2 * math.sqrt(1 + m[1][1] - m[0][0] - m[2][2])
        q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    else:
        s = 2 * math.sqrt(1 + m[2][2] - m[0][0] - m[1][1])
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s, (m[1][0] - m[0][1]) / s)
    return Cam(position, q, c["fov"], tuple(c.get("principal", (0.5, 0.5))))


def new_state(track, cameras, t):
    shots = track["shots"]
    row = None
    for candidate in shots:
        if candidate["start"] <= t < candidate["end"]:
            row = candidate
            break
    if row is None or row["mode"] == "hold":
        return "hold", None
    f = (t - row["start"]) / (row["end"] - row["start"])
    tiles = row.get("tiles") or [{}]
    out = []
    for tile in tiles:
        get = lambda key: tile.get(key, row.get(key))  # noqa: E731
        cam_a = resolve_camera(get("camera"), cameras)
        a = camera_from_json(cam_a)
        if get("cameraEnd") is None:
            cam = a
        else:
            b = camera_from_json(resolve_camera(get("cameraEnd"), cameras))
            cam = Cam(lerp3(a.p, b.p, f), slerp(a.q, b.q, f), lerp(a.fov, b.fov, f), lerp3(a.pp, b.pp, f))
        turns = get("crankTurns")
        preset = track["presets"][get("preset")]
        inp = {"crankTurns": lerp(turns[0], turns[1], f), "amplitudes": preset["amplitudes"], "phases": preset["phases"]}
        if get("presetEnd"):
            other = track["presets"][get("presetEnd")]
            inp["amplitudes"] = [lerp(x, y, f) for x, y in zip(preset["amplitudes"], other["amplitudes"])]
            inp["phases"] = [x + phase_delta(x, y) * f for x, y in zip(preset["phases"], other["phases"])]
        setup = dict(get("setup") or {})
        for key, value in (get("setupEnd") or {}).items():
            base = setup.get(key, DEFAULT_MAGNIFICATION if key == "magnification" else 0)
            setup[key] = lerp(base, value, f)
        rect = tuple(tile.get("rect", FULL))
        out.append((rect, bool(tile.get("mirror")), cam, inp, setup))
    return "approx", out


# ------------------------------------------------------------------ main

def main():
    points = load_glb_points(WEB / "public/models/ha-harmonic-analyzer.glb")
    cameras: dict[str, dict] = {}
    outputs = {}
    for video, slug in SLUGS.items():
        legacy = json.loads((CONTENT / f"{video}.source-track.json").read_text(encoding="utf-8"))
        duration = legacy["source"]["durationSeconds"]
        frames = compile_legacy(legacy)
        rows = build_rows(frames, duration, points)
        outputs[video] = (slug, legacy, frames, rows, duration)

    # Name the cameras that carry the most rendered time.
    usage: dict[str, list] = {}
    for video, (slug, legacy, frames, rows, duration) in outputs.items():
        for row in rows:
            if row["mode"] != "follow":
                continue
            for spec in row["tiles"]:
                if spec["camEnd"] is not None or (spec["k0"].assembly or {}).get("photograph"):
                    continue
                cam = camera_json(spec["k0"].cam, spec["rect"][2], spec["rect"][3], points)
                key = json.dumps(cam, sort_keys=True)
                entry = usage.setdefault(key, [0.0, slug, cam])
                entry[0] += row["end"] - row["start"]
    ranked = sorted(usage.items(), key=lambda item: -item[1][0])
    counters: dict[str, int] = {}
    for key, (seconds, slug, cam) in ranked[:20]:
        if seconds < 8:
            break
        counters[slug] = counters.get(slug, 0) + 1
        name = f"{slug}-{counters[slug]}"
        cameras[CAMERA_NAMES.get(name, name)] = cam

    report = []
    for video, (slug, legacy, frames, rows, duration) in outputs.items():
        presets: dict[str, dict] = {}
        shots = [row_json(row, presets, slug, points, cameras) for row in rows]
        track = {"video": video, "presets": {name: {k: v for k, v in value.items() if k != "_key"} for name, value in presets.items()},
                 "shots": shots}
        text = dumps_track(track)
        path = CONTENT / "tracks" / f"{slug}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        report.append(verify(slug, frames, duration, json.loads(text), cameras, points, len(text)))
    (CONTENT / "cameras.json").write_text(dumps_cameras(cameras), encoding="utf-8", newline="\n")
    for line in report:
        print(line)


def dumps_cameras(cameras):
    lines = ["{"]
    names = list(cameras)
    for i, name in enumerate(names):
        comma = "," if i + 1 < len(names) else ""
        lines.append(f"  {json.dumps(name)}: {json.dumps(cameras[name], separators=(',', ':'))}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def verify(slug, frames, duration, track, cameras, points, size):
    times = set()
    for i, frame in enumerate(frames):
        # just after the knot: row boundaries are rounded to 0.1 ms
        nxt = frames[i + 1]["t"] if i + 1 < len(frames) else duration
        if frame["t"] + 0.0002 < nxt:
            times.add(frame["t"] + 0.0002)
        if i + 1 < len(frames) and frames[i + 1]["t"] - frame["t"] > 0.0005:
            times.add((frame["t"] + frames[i + 1]["t"]) / 2)
    worst_cam = 0.0
    worst = {key: 0.0 for key in TOL}
    worst_amp = 0.0
    mismatched_kind = 0
    follow_seconds = sum(s["end"] - s["start"] for s in track["shots"] if s["mode"] == "follow")
    for t in sorted(times):
        if t >= duration:
            continue
        kind, old = legacy_state(frames, duration, t)
        kind_new, new = new_state(track, cameras, t)
        if kind != kind_new:
            mismatched_kind += 1
            continue
        if kind == "hold":
            continue
        # match legacy visible tiles to new tiles by rect
        for rect, mirror, cam, inp, setup in new:
            match = [view for view in old if view[0] == rect]
            assert match, (slug, t, rect)
            o_rect, o_mirror, o_cam, o_inp, _ = match[-1]
            assert o_mirror == mirror
            worst_cam = max(worst_cam, camera_error_px(o_cam, cam, rect[2], rect[3], points))
            worst["crankTurns"] = max(worst["crankTurns"], abs(o_inp["crankTurns"] - inp["crankTurns"]))
            for key in SETUP_KEYS:
                if o_inp["setup"][key] is not None:
                    worst[key] = max(worst[key], abs(o_inp["setup"][key] - setup.get(key, 0)))
            worst["magnification"] = max(worst["magnification"], abs(o_inp["magnification"] - setup.get("magnification", DEFAULT_MAGNIFICATION)))
            assert o_inp["gearing"] == setup.get("gearing", "small-large"), (slug, t)
            worst_amp = max(worst_amp, max(abs(a - b) for a, b in zip(o_inp["amplitudes"], inp["amplitudes"])))
    detail = ", ".join(f"{k} {v:.2g}" for k, v in worst.items() if v > 0)
    return (f"{slug}: {len(track['shots'])} rows, {size / 1024:.1f} KiB, follow {follow_seconds:.1f} s; "
            f"{len(times)} samples, kind mismatches {mismatched_kind}; worst camera {worst_cam:.2f} px; "
            f"worst amplitude {worst_amp:.2g}; {detail}")


if __name__ == "__main__":
    sys.exit(main())
