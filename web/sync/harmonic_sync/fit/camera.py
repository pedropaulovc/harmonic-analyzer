"""Static-native-geometry camera fitting and projection-bounded key reduction."""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

import cv2
import numpy as np
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation, Slerp


def look_at(eye: np.ndarray, target: np.ndarray) -> np.ndarray:
    z = eye - target
    z /= np.linalg.norm(z)
    up = np.array([0., 1., 0.])
    if abs(z @ up) > .98:
        up = np.array([0., 0., 1.])
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    return Rotation.from_matrix(np.column_stack((x, np.cross(z, x), z))).as_quat()


def scale_camera(camera: dict, from_size: tuple[float, float], to_size: tuple[float, float]) -> dict:
    result = deepcopy(camera)
    principal = camera.get('principalPointViewportPixels', [from_size[0] / 2, from_size[1] / 2])
    result['principalPointViewportPixels'] = [principal[j] * to_size[j] / from_size[j] for j in range(2)]
    return result


def interpolate_camera(keys: list[dict], t: float) -> dict:
    if not keys:
        raise ValueError('Camera interpolation requires at least one key')
    keys = sorted(keys, key=lambda key: key['t'])
    if t <= keys[0]['t']:
        return deepcopy(keys[0]['camera'])
    if t >= keys[-1]['t']:
        return deepcopy(keys[-1]['camera'])
    right = next(j for j, key in enumerate(keys) if key['t'] >= t)
    a, b = keys[right - 1], keys[right]
    u = (t - a['t']) / (b['t'] - a['t'])
    ca, cb = a['camera'], b['camera']
    return {
        'positionMetres': ((1-u)*np.array(ca['positionMetres']) + u*np.array(cb['positionMetres'])).tolist(),
        'quaternion': Slerp([0, 1], Rotation.from_quat([ca['quaternion'], cb['quaternion']]))([u]).as_quat()[0].tolist(),
        'verticalFovDegrees': (1-u)*ca['verticalFovDegrees'] + u*cb['verticalFovDegrees'],
        'principalPointViewportPixels': ((1-u)*np.array(ca['principalPointViewportPixels']) + u*np.array(cb['principalPointViewportPixels'])).tolist(),
    }


def bounds_points(bounds: dict) -> np.ndarray:
    lo, hi = np.array(bounds['min']), np.array(bounds['max'])
    return np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])] + [((lo+hi)/2).tolist()])


def project(camera: dict, points: np.ndarray, width: float, height: float) -> np.ndarray:
    local = Rotation.from_quat(camera['quaternion']).inv().apply(points - np.array(camera['positionMetres']))
    focal = height / (2 * math.tan(math.radians(camera['verticalFovDegrees']) / 2))
    pp = camera['principalPointViewportPixels']
    depth = -local[:, 2]
    if np.any(depth <= 1e-5):
        return np.full((len(points), 2), np.inf)
    return np.column_stack((pp[0] + focal*local[:, 0]/depth, pp[1] - focal*local[:, 1]/depth))


def decimate_camera(keys: list[dict], points: np.ndarray, size: tuple[float, float], tolerance: float = 2., fixed_times: set[float] | None = None) -> list[dict]:
    """Bound native bounds-control-point interpolation at every retained candidate time."""
    keys = sorted(keys, key=lambda key: key['t'])
    if len(keys) < 3:
        return keys
    fixed = fixed_times or set()
    keep = {0, len(keys)-1} | {j for j, key in enumerate(keys) if key['t'] in fixed}
    def split(a: int, b: int) -> None:
        if b <= a+1:
            return
        errors = []
        for j in range(a+1, b):
            candidate = interpolate_camera([keys[a], keys[b]], keys[j]['t'])
            actual = project(keys[j]['camera'], points, *size)
            interpolated = project(candidate, points, *size)
            error = np.max(np.linalg.norm(actual-interpolated, axis=1)) if np.isfinite(actual).all() and np.isfinite(interpolated).all() else math.inf
            errors.append((float(error), j))
        error, j = max(errors)
        if error > tolerance:
            keep.add(j)
            split(a, j)
            split(j, b)
    for a, b in zip(sorted(keep), sorted(keep)[1:]):
        split(a, b)
    return [keys[j] for j in sorted(keep)]


class CameraFitter:
    def __init__(self, client: Any, ready: dict):
        self.client, self.ready = client, ready

    def loss_function(self, sample: dict):
        mask = sample['mask']
        source_edges = sample['edges'].astype(np.uint8)
        dt = cv2.distanceTransform(1-source_edges, cv2.DIST_L2, 3)
        scale = sample['sourceWidth'] / mask.shape[1]
        cap = 96 / scale
        source_area = max(1, np.count_nonzero(mask))
        def score(ids: np.ndarray) -> float:
            rendered = ids > 0
            area = int(np.count_nonzero(rendered))
            if area < 8 or area >= .98*rendered.size or np.count_nonzero(source_edges) < 8:
                return 1e4
            edges = cv2.morphologyEx(rendered.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
            if not edges.any():
                return 1e4
            edge = float(np.minimum(dt[edges], cap).mean()) * scale
            intersection = np.count_nonzero(mask & rendered)
            union = source_area + area - intersection
            outside = 1-intersection/area
            # Static frame cannot fill the source moving-parts mask. A low-weight
            # IoU plus robust directed edges avoids making that impossible target.
            # Suppress the tiny-geometry-on-one-source-edge degeneracy without
            # pretending the source's moving mask is a static-only annotation.
            area_penalty = 12*abs(math.log(max(1., area)/(.5*source_area)))
            return edge + 65*outside + 15*(1-intersection/max(1, union)) + area_penalty
        return score

    def fit(self, sample: dict, *, target_group: str = 'static', seed: dict | None = None, coarse: bool = True, evaluations: int = 80, full_pose: bool = False) -> tuple[dict, float]:
        width, height = sample['width'], sample['height']
        mask = sample['mask']
        if np.count_nonzero(mask) < 8:
            raise ValueError('Cannot fit camera to empty source mask')
        bounds = self.ready['groupBoundsMetres'].get(target_group, self.ready['boundsMetres'])
        lo, hi = np.array(bounds['min']), np.array(bounds['max'])
        centre = (lo+hi)/2
        diameter = max(.05, float(np.linalg.norm(hi-lo)))
        ys, xs = np.nonzero(mask)
        principal = [float(np.median(xs)), float(np.median(ys))]
        if sample['presentation'] == 'horizontal-mirror':
            principal[0] = width-1-principal[0]
        fill = max(.08, min(.98, (ys.max()-ys.min()+1)/height))
        groups = None if full_pose else ['static']
        def request(camera: dict) -> dict:
            return {'camera': camera, 'input': sample['input'], 'width': width, 'height': height,
                    'presentation': sample['presentation'], **({'groups': groups} if groups else {})}
        score = self.loss_function(sample)
        candidates = []
        if seed:
            candidates.append(seed)
        if coarse or not seed:
            for azimuth in np.linspace(-math.pi, math.pi, 12, endpoint=False):
                for elevation in (math.radians(-15), math.radians(20), math.radians(55)):
                    direction = np.array([math.cos(elevation)*math.sin(azimuth), math.sin(elevation), math.cos(elevation)*math.cos(azimuth)])
                    for fov in (22., 40., 65.):
                        distance = diameter/(2*math.tan(math.radians(fov)/2)*fill)
                        eye = centre+direction*distance
                        candidates.append({'positionMetres': eye.tolist(), 'quaternion': look_at(eye, centre).tolist(),
                                           'verticalFovDegrees': fov, 'principalPointViewportPixels': principal})
        scored = []
        for offset in range(0, len(candidates), 32):
            batch = candidates[offset:offset+32]
            scored.extend((1e4 if np.all(np.asarray(camera['positionMetres']) >= lo) and np.all(np.asarray(camera['positionMetres']) <= hi) else score(ids), camera)
                          for ids, camera in zip(self.client.render_batch([request(camera) for camera in batch]), batch))
        best_loss, base = min(scored, key=lambda row: row[0])
        base_rotation = Rotation.from_quat(base['quaternion'])
        base_position = np.array(base['positionMetres'])
        base_pp = np.array(base['principalPointViewportPixels'])
        def decode(x: np.ndarray) -> dict:
            return {'positionMetres': (base_position+x[:3]*diameter*.15).tolist(),
                    'quaternion': (base_rotation*Rotation.from_rotvec(x[3:6]*.12)).as_quat().tolist(),
                    'verticalFovDegrees': float(base['verticalFovDegrees']+x[6]*5),
                    'principalPointViewportPixels': (base_pp+x[7:9]*np.array([width, height])*.05).tolist()}
        best = deepcopy(base)
        def objective(x: np.ndarray) -> float:
            nonlocal best, best_loss
            camera = decode(x)
            eye = np.asarray(camera['positionMetres'])
            if np.all(eye >= lo) and np.all(eye <= hi):
                return 1e4+float(x @ x)
            if not 8 <= camera['verticalFovDegrees'] <= 110 or np.linalg.norm(x[:3]) > 12 or np.linalg.norm(x[3:6]) > 12 or np.linalg.norm(x[7:9]) > 15:
                return 1e4+float(x @ x)
            loss = score(self.client.render(request(camera)))
            if loss < best_loss:
                best, best_loss = camera, loss
            return loss
        simplex = np.vstack((np.zeros(9), np.eye(9)*.8))
        minimize(objective, np.zeros(9), method='Nelder-Mead', options={'maxfev': evaluations, 'xatol': .025, 'fatol': .025, 'initial_simplex': simplex})
        return best, float(best_loss)
