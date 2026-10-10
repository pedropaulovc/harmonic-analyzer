"""Private render/photo camera-initializer trial; never publishes runtime tracks.

Install: uv sync --project web/sync --extra appearance
Run from the repository root:
  uv run --project web/sync --extra appearance python -m harmonic_sync.fit.appearance \
    --selection /private/selected-views.json --output /private/appearance-trial

Matches are restricted to both machine masks. Candidates are ranked by geometric
inliers, not silhouette loss. Only the retained candidates undergo PnP; the best
PnP hypothesis initializes the existing bidirectional chamfer/IoU local refine.
A rejected initializer is recorded explicitly, never replaced by the old camera.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial.transform import Rotation

from ..render_client import RenderClient
from ..video import PROJECT, data_root, load_shots, write_json
from .camera import CameraFitter, interpolate_camera, look_at, scale_camera
from .crank import interpolate_turns
from .metrics import chamfer_metrics, mask_iou
from .pipeline import source_frame, target_group


class LearnedMatcher:
    def __init__(self, name: str, device: str = 'cuda'):
        import torch
        self.torch, self.name, self.device = torch, name, device
        torch.manual_seed(0)
        torch.set_num_threads(4)
        if device == 'cuda' and not torch.cuda.is_available():
            raise RuntimeError('Appearance trial requires available CUDA or explicit --device cpu')
        if name == 'loftr':
            from kornia.feature import LoFTR
            self.model = LoFTR(pretrained='outdoor').eval().to(device)
        elif name == 'roma':
            from romatch import roma_outdoor
            self.model = roma_outdoor(device=device, coarse_res=560, upsample_preds=False, use_custom_corr=False).eval()
        else:
            raise ValueError(f'Unknown matcher {name}')

    def match(self, rendered: np.ndarray, source: np.ndarray, render_mask: np.ndarray,
              source_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        torch = self.torch
        a, b = rendered.copy(), source.copy()
        a[~render_mask], b[~source_mask] = 0, 0
        with torch.inference_mode():
            if self.name == 'loftr':
                import torch.nn.functional as functional
                def tensor(image):
                    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
                    value = torch.from_numpy(gray).to(self.device, dtype=torch.float32)[None, None]/255
                    return functional.pad(value, (0, -image.shape[1] % 8, 0, -image.shape[0] % 8))
                result = self.model({'image0': tensor(a), 'image1': tensor(b)})
                pa = result['keypoints0'].cpu().numpy()
                pb = result['keypoints1'].cpu().numpy()
                confidence = result['confidence'].cpu().numpy()
            else:
                warp, certainty = self.model.match(Image.fromarray(a), Image.fromarray(b), device=self.device)
                matches, certainty = self.model.sample(warp, certainty, num=2000)
                pa, pb = self.model.to_pixel_coordinates(matches, a.shape[0], a.shape[1], b.shape[0], b.shape[1])
                pa, pb, confidence = pa.cpu().numpy(), pb.cpu().numpy(), certainty.cpu().numpy()
                # RoMa's align_corners=False coordinates use pixel centres at .5;
                # keep all matcher pixels in array-index coordinates, as LoFTR does.
                pa, pb = pa-.5, pb-.5
        ia, ib = np.rint(pa).astype(int), np.rint(pb).astype(int)
        valid = ((ia[:, 0] >= 0) & (ia[:, 0] < a.shape[1]) & (ia[:, 1] >= 0) & (ia[:, 1] < a.shape[0]) &
                 (ib[:, 0] >= 0) & (ib[:, 0] < b.shape[1]) & (ib[:, 1] >= 0) & (ib[:, 1] < b.shape[0]))
        if self.name == 'roma':
            valid &= confidence >= .05
        keep = np.flatnonzero(valid)
        valid[keep] &= render_mask[ia[keep, 1], ia[keep, 0]] & source_mask[ib[keep, 1], ib[keep, 0]]
        return pa[valid], pb[valid], confidence[valid]


def geometric_inliers(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    if len(pa) < 8:
        return np.zeros(len(pa), bool)
    cv2.setRNGSeed(0)
    _, mask = cv2.findFundamentalMat(pa, pb, cv2.USAC_MAGSAC, 1.5, .999, 3000)
    return np.zeros(len(pa), bool) if mask is None else mask.ravel().astype(bool)


def candidate_cameras(sample: dict, bounds: dict, current: dict) -> list[dict]:
    lo, hi = np.array(bounds['min']), np.array(bounds['max'])
    centre, extents = (lo+hi)/2, hi-lo
    width, height = sample['width'], sample['height']
    ys, xs = np.nonzero(sample['mask'])
    if len(xs) < 8:
        raise ValueError('Appearance source mask is empty')
    principal = [float(np.median(xs)), float(np.median(ys))]
    if sample['presentation'] == 'horizontal-mirror':
        principal[0] = width-1-principal[0]
    fill_y = np.clip((ys.max()-ys.min()+1)/height, .08, .98)
    fill_x = np.clip((xs.max()-xs.min()+1)/width, .08, .98)
    candidates = [{'camera': current, 'azimuthDegrees': None, 'elevationDegrees': None, 'distanceScale': None, 'kind': 'current'}]
    for azimuth in np.linspace(-math.pi, math.pi, 8, endpoint=False):
        for elevation_degrees in (-10., 15., 50., 80.):
            elevation = math.radians(elevation_degrees)
            direction = np.array([math.cos(elevation)*math.sin(azimuth), math.sin(elevation), math.cos(elevation)*math.cos(azimuth)])
            quaternion = look_at(centre+direction, centre)
            basis = Rotation.from_quat(quaternion).as_matrix()
            span_x, span_y = abs(basis[:, 0]) @ extents, abs(basis[:, 1]) @ extents
            for fov in (30., 65.):
                tangent = math.tan(math.radians(fov)/2)
                distance = max(span_y/(2*tangent*fill_y), span_x/(2*tangent*(width/height)*fill_x), .04)
                for distance_scale in (.7, 1.2):
                    eye = centre+direction*distance*distance_scale
                    if np.all(eye >= lo) and np.all(eye <= hi):
                        continue
                    candidates.append({'camera': {'positionMetres': eye.tolist(), 'quaternion': quaternion.tolist(),
                        'verticalFovDegrees': fov, 'principalPointViewportPixels': principal},
                        'azimuthDegrees': float(math.degrees(azimuth)), 'elevationDegrees': elevation_degrees,
                        'distanceScale': distance_scale, 'kind': 'sphere'})
    return candidates


def solve_camera(world: np.ndarray, pixels: np.ndarray, camera: dict, sample: dict) -> dict | None:
    if len(world) < 6:
        return None
    pixels = pixels.astype(np.float64).copy()
    if sample['presentation'] == 'horizontal-mirror':
        pixels[:, 0] = sample['width']-1-pixels[:, 0]
    # World readback samples viewport centres, not integer array origins.
    pixels += .5
    focal = sample['height']/(2*math.tan(math.radians(camera['verticalFovDegrees'])/2))
    cx, cy = camera['principalPointViewportPixels']
    intrinsics = np.array([[focal, 0., cx], [0., focal, cy], [0., 0., 1.]])
    cv2.setRNGSeed(0)
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(world.astype(np.float64), pixels, intrinsics, None,
        iterationsCount=2000, reprojectionError=3., confidence=.999, flags=cv2.SOLVEPNP_EPNP)
    if not ok or inliers is None or len(inliers) < 6:
        return None
    keep = inliers.ravel()
    rvec, tvec = cv2.solvePnPRefineLM(world[keep].astype(np.float64), pixels[keep], intrinsics, None, rvec, tvec)
    rotation = cv2.Rodrigues(rvec)[0]
    camera_points = world @ rotation.T+tvec.ravel()
    if np.mean(camera_points[keep, 2] > 0) < .95:
        return None
    position = -rotation.T @ tvec.ravel()
    # OpenCV camera axes: +x right, +y down, +z forward; three.js: +y up, -z forward.
    quaternion = Rotation.from_matrix(rotation.T @ np.diag([1., -1., -1.])).as_quat()
    projected = cv2.projectPoints(world, rvec, tvec, intrinsics, None)[0].reshape(-1, 2)
    errors = np.linalg.norm(projected-pixels, axis=1)
    return {'camera': {**deepcopy(camera), 'positionMetres': position.tolist(), 'quaternion': quaternion.tolist()},
            'inliers': len(keep), 'inlierFraction': len(keep)/len(world),
            'medianReprojectionPx': float(np.median(errors[keep])), 'inlierIndices': keep.tolist()}


def silhouette_metrics(ids: np.ndarray, sample: dict) -> dict:
    edges = cv2.morphologyEx(ids.astype(np.uint16), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    return {'iou': mask_iou(sample['mask'], ids > 0),
            **chamfer_metrics(sample['edges'], edges, source_width=sample['sourceWidth'])}


def record_log(output: Path, event: str, **fields) -> None:
    line = json.dumps({'at': time.time(), 'event': event, **fields}, allow_nan=False)
    with (output/'timing.jsonl').open('a') as stream:
        stream.write(line+'\n')
    if all(key in fields for key in ('videoId', 'shotId', 'viewId')):
        name = '--'.join(str(fields[key]) for key in ('videoId', 'shotId', 'viewId'))
        with (output/f'{name}--timing.jsonl').open('a') as stream:
            stream.write(line+'\n')
    if event != 'candidate':
        print(line, flush=True)


def render_request(sample: dict, camera: dict) -> dict:
    return {'camera': camera, 'input': sample['input'], 'width': sample['width'], 'height': sample['height'],
            'presentation': sample['presentation']}


def save_comparison(path: Path, source: np.ndarray, current: dict, new: dict | None, row: dict) -> None:
    width, height = source.shape[1], source.shape[0]
    sheet = Image.new('RGB', (3*width, height+90), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    sheet.paste(Image.fromarray(source), (0, 90))
    for j, rendered in enumerate((current, new), 1):
        if rendered is not None:
            blend = source.copy()
            mask = rendered['ids'] > 0
            blend[mask] = (.45*source[mask]+.55*rendered['rgb'][mask]).astype(np.uint8)
            sheet.paste(Image.fromarray(rendered['rgb'] if j == 1 else blend), (j*width, 90))
        else:
            draw.text((j*width+12, 130), 'No supported PnP camera\nInitializer rejected', fill='orange')
    draw.text((8, 8), f"{row['videoId']} {row['shotId']}/{row['viewId']} frame {row['index']}\nSource photograph", fill='white')
    for j, name in enumerate(('current', 'new'), 1):
        metrics = row.get(name+'Metrics')
        title = 'Current fit' if name == 'current' else 'Appearance + local refine'
        draw.text((j*width+8, 8), title, fill='white')
        if metrics:
            draw.text((j*width+8, 27), f"IoU {metrics['iou']:.3f}\nS->R {metrics['sourceToRenderChamferPx']:.1f}px  R->S {metrics['renderToSourceChamferPx']:.1f}px", fill='white')
    sheet.save(path)


def save_candidates(path: Path, source: np.ndarray, retained: list[dict]) -> None:
    width, height = source.shape[1], source.shape[0]
    sheet = Image.new('RGB', (3*width, 2*(height+40)), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    sheet.paste(Image.fromarray(source), (0, 40))
    draw.text((8, 8), 'Masked source', fill='white')
    for j, candidate in enumerate(retained[:5], 1):
        x, y = (j % 3)*width, (j//3)*(height+40)
        sheet.paste(Image.fromarray(candidate['render']['rgb']), (x, y+40))
        draw.text((x+8, y+8), f"az {candidate['azimuthDegrees']} el {candidate['elevationDegrees']} F {candidate['geometricInliers']} PnP {candidate.get('pnpInliers', 0)}", fill='white')
    sheet.save(path)


def trial_view(client, matcher, ready, selection, root, output, width, evaluations, deadline) -> dict:
    started = time.perf_counter()
    video_id, shot_id, view_id = (selection[key] for key in ('videoId', 'shotId', 'viewId'))
    name = f'{video_id}--{shot_id}--{view_id}'
    census = load_shots(video_id)
    track = json.loads(Path(selection['currentSync']).read_text())
    shot = next(shot for shot in census['shots'] if shot['id'] == shot_id)
    view = next(view for view in shot['views'] if view['viewId'] == view_id)
    folder = root/video_id/shot_id/view_id
    index = json.loads((folder/'index.json').read_text())
    source_row = next(row for row in index['frames'] if row['index'] == selection['index'])
    size = (min(width, index['width']), max(1, round(index['height']*min(width, index['width'])/index['width'])))
    def image_field(field):
        image = cv2.imread(str(folder/field/f"{selection['index']}.png"), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(f'Missing source {field} at {folder}')
        return cv2.resize(image, size, interpolation=cv2.INTER_NEAREST if field == 'masks' else cv2.INTER_AREA) > (0 if field == 'masks' else 12)
    sample = {**source_row, 'width': size[0], 'height': size[1], 'sourceWidth': view['rectSourcePixels'][2],
              'presentation': view['presentation'], 'mask': image_field('masks'), 'edges': image_field('edges')}
    fps = Fraction(*census['fps'])
    t = selection['index']/float(fps)
    segment = next(segment for segment in track['segments'] if round(segment['start']*fps) <= selection['index'] < round(segment['end']*fps))
    sample['input'] = deepcopy(segment['input'])
    sample['input']['crankTurns'] = interpolate_turns(track['crank'], t)
    exported = next(view for shot in track['shots'] if shot['id'] == shot_id for view in shot['views'] if view['viewId'] == view_id)
    current_camera = scale_camera(interpolate_camera(exported['cameraKeys'], t), tuple(view['rectSourcePixels'][2:]), size)
    source = source_frame({'folder': folder, 'view': view, 'index': index, 'samples': [sample]}, selection['index'], fps)
    current = client.render_appearance(render_request(sample, current_camera), world_positions=False)
    row = {**selection, 'matcher': matcher.name, 'targetGroup': target_group(shot, view),
           'width': size[0], 'height': size[1], 'currentCamera': current_camera,
           'rectSourcePixels': view['rectSourcePixels'],
           'currentMetrics': silhouette_metrics(current['ids'], sample)}
    record_log(output, 'view-start', videoId=video_id, shotId=shot_id, viewId=view_id, index=selection['index'])
    bounds = ready['groupBoundsMetres'].get(row['targetGroup'], ready['boundsMetres'])
    retained, scores = [], []
    for number, candidate in enumerate(candidate_cameras(sample, bounds, current_camera)):
        if time.monotonic() >= deadline:
            raise TimeoutError('Appearance trial wall-clock budget exhausted')
        candidate_started = time.perf_counter()
        rendered = current if candidate['kind'] == 'current' else client.render_appearance(render_request(sample, candidate['camera']), world_positions=False)
        # Erode only the correspondence support, not the scoring silhouette.
        support = cv2.erode((rendered['ids'] > 0).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        pa, pb, confidence = matcher.match(rendered['rgb'], source, support, sample['mask'])
        inliers = geometric_inliers(pa, pb)
        summary = {**candidate, 'candidate': number, 'matches': len(pa), 'geometricInliers': int(inliers.sum()),
                   'seconds': time.perf_counter()-candidate_started}
        scores.append(summary)
        record_log(output, 'candidate', videoId=video_id, shotId=shot_id, viewId=view_id, **summary)
        retained.append({**summary, 'render': rendered, 'renderPixels': pa, 'sourcePixels': pb, 'confidence': confidence, 'geometricMask': inliers})
        retained.sort(key=lambda value: (value['geometricInliers'], value['matches']), reverse=True)
        del retained[5:]
    solved = []
    for candidate in retained:
        candidate['render'] = client.render_appearance(render_request(sample, candidate['camera']))
        pa, pb = candidate['renderPixels'], candidate['sourcePixels']
        coords = np.rint(pa).astype(int)
        world = candidate['render']['world_positions'][coords[:, 1], coords[:, 0]]
        valid = np.isfinite(world).all(axis=1)
        result = solve_camera(world[valid], pb[valid], candidate['camera'], sample)
        candidate['pnpInliers'] = result['inliers'] if result else 0
        if result:
            solved.append({**result, 'candidate': candidate['candidate']})
    solved.sort(key=lambda value: (value['inliers'], -value['medianReprojectionPx']), reverse=True)
    new = None
    if solved:
        solution = solved[0]
        row['pnp'] = solution
        row['initializerCamera'] = solution['camera']
        refine_started = time.perf_counter()
        camera, loss = CameraFitter(client, ready).fit(sample, target_group=row['targetGroup'], seed=solution['camera'],
            coarse=False, full_pose=True, evaluations=evaluations)
        row.update(newCamera=camera, refineLoss=loss, refineSeconds=time.perf_counter()-refine_started, status='pnp-refined')
        new = client.render_appearance(render_request(sample, camera), world_positions=False)
        row['newMetrics'] = silhouette_metrics(new['ids'], sample)
    else:
        row.update(status='initializer-rejected', reason='No retained view produced six positive-depth PnP+RANSAC inliers')
    row['seconds'] = time.perf_counter()-started
    row['candidateCount'] = len(scores)
    row['candidatesPath'] = str(output/f'{name}--candidates.json')
    row['sheetPath'] = str(output/f'{name}--comparison.png')
    row['candidateSheetPath'] = str(output/f'{name}--candidates.png')
    row['currentRenderPath'] = str(output/f'{name}--current.png')
    Image.fromarray(current['rgb']).save(row['currentRenderPath'])
    if new is not None:
        row['newRenderPath'] = str(output/f'{name}--refined.png')
        Image.fromarray(new['rgb']).save(row['newRenderPath'])
    for candidate in retained:
        coords = np.rint(candidate['renderPixels']).astype(int)
        world = candidate['render']['world_positions'][coords[:, 1], coords[:, 0]]
        np.savez_compressed(output/f"{name}--matches-{candidate['candidate']}.npz",
            world=world, renderPixels=candidate['renderPixels'], sourcePixels=candidate['sourcePixels'],
            confidence=candidate['confidence'], geometricInliers=candidate['geometricMask'])
    write_json(Path(row['candidatesPath']), {'candidates': scores, 'solutions': solved})
    masked_source = source.copy()
    masked_source[~sample['mask']] = 0
    save_candidates(Path(row['candidateSheetPath']), masked_source, retained)
    save_comparison(Path(row['sheetPath']), source, current, new, row)
    write_json(output/f'{name}.json', row)
    record_log(output, 'view-complete', videoId=video_id, shotId=shot_id, viewId=view_id, status=row['status'],
               seconds=row['seconds'], candidateCount=len(scores), pnpInliers=row.get('pnp', {}).get('inliers', 0))
    return row


def select_video_views(video_ids: list[str], root: Path) -> list[dict]:
    """Use the earliest maximum-machine-mask-area sample in each census view."""
    selections = []
    for video_id in video_ids:
        census = load_shots(video_id)
        current_sync = PROJECT.parent/'content'/'sync'/f'{video_id}.sync.json'
        for shot in census['shots']:
            if shot['classification'] not in ('machine', 'transition'):
                continue
            for view in shot['views']:
                index_path = root/video_id/shot['id']/view['viewId']/'index.json'
                index = json.loads(index_path.read_text())
                frames = index['frames']
                if not frames:
                    raise ValueError(f'No source samples for proposal: {index_path}')
                frame = max(frames, key=lambda row: (row['maskArea'], -row['index']))
                selections.append({'rank': len(selections)+1, 'videoId': video_id,
                    'shotId': shot['id'], 'viewId': view['viewId'], 'index': frame['index'],
                    'currentSync': str(current_sync), 'sourceIndex': str(index_path),
                    'sourceSha256': census['sourceSha256'], 'sourceInputHash': index['inputHash']})
    return selections


def write_proposals(video_ids: list[str], results: list[dict]) -> dict[str, int]:
    counts = {}
    for video_id in video_ids:
        cameras = []
        for row in results:
            if row['videoId'] != video_id or row.get('status') != 'pnp-refined':
                continue
            metrics = row['newMetrics']
            camera = scale_camera(row['newCamera'], (row['width'], row['height']),
                                  tuple(row['rectSourcePixels'][2:]))
            cameras.append({'shotId': row['shotId'], 'viewId': row['viewId'], 'frame': row['index'],
                'camera': camera, 'iou': metrics['iou'], 's2rPx': metrics['sourceToRenderChamferPx'],
                'r2sPx': metrics['renderToSourceChamferPx'], 'pnpInliers': row['pnp']['inliers'],
                'pnpInlierFraction': row['pnp']['inlierFraction']})
        write_json(PROJECT/'videos'/video_id/'proposals.json', {'cameras': cameras})
        counts[video_id] = len(cameras)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--selection', type=Path)
    scope.add_argument('--videos', nargs='+', help='Generate one proposal per machine/transition census view')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--matcher', choices=['loftr', 'roma'], default='roma')
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--width', type=int, default=480)
    parser.add_argument('--evaluations', type=int, default=120)
    parser.add_argument('--ranks', type=int, nargs='*')
    parser.add_argument('--budget-seconds', type=float, default=7000)
    args = parser.parse_args()
    root, output = data_root(), args.output.expanduser().resolve()
    if output.is_relative_to(Path(__file__).resolve().parents[4]):
        raise ValueError('Appearance artifacts must be outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    selections = select_video_views(args.videos, root) if args.videos else json.loads(args.selection.read_text())['views']
    if args.ranks:
        selections = [view for view in selections if view['rank'] in args.ranks]
    write_json(output/'selection.json', {'views': selections})
    started = time.perf_counter()
    deadline = time.monotonic()+args.budget_seconds
    matcher_started = time.perf_counter()
    matcher = LearnedMatcher(args.matcher, args.device)
    record_log(output, 'matcher-ready', matcher=args.matcher, seconds=time.perf_counter()-matcher_started)
    results, proposal_counts = [], {}
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with RenderClient(quiet_batches=True, data_root=output) as client:
        ready = client.ready()
        write_json(output/'render-ready.json', ready)
        for selection in selections:
            if time.monotonic() >= deadline:
                record_log(output, 'budget-exhausted', completed=len(results), expected=len(selections))
                break
            fingerprint = hashlib.sha256(json.dumps({'selection': selection, 'matcher': args.matcher,
                'width': args.width, 'evaluations': args.evaluations, 'code': code_hash,
                'bounds': ready['groupBoundsMetres']}, sort_keys=True).encode()).hexdigest()
            selection = {**selection, 'fingerprint': fingerprint}
            row_path = output/f"{selection['videoId']}--{selection['shotId']}--{selection['viewId']}.json"
            cached = json.loads(row_path.read_text()) if row_path.is_file() else None
            if cached is not None and cached.get('fingerprint') == fingerprint:
                row = cached
                record_log(output, 'view-resumed', videoId=row['videoId'], shotId=row['shotId'],
                    viewId=row['viewId'], status=row['status'], seconds=row['seconds'])
            else:
                view_started = time.perf_counter()
                try:
                    row = trial_view(client, matcher, ready, selection, root, output, args.width, args.evaluations, deadline)
                except TimeoutError:
                    record_log(output, 'budget-exhausted', completed=len(results), expected=len(selections))
                    break
                except Exception as error:
                    row = {**selection, 'matcher': args.matcher, 'status': 'execution-error',
                        'seconds': time.perf_counter()-view_started,
                        'errorType': type(error).__name__, 'error': str(error)}
                    write_json(row_path, row)
                    record_log(output, 'view-failed', videoId=row['videoId'], shotId=row['shotId'],
                        viewId=row['viewId'], seconds=row['seconds'], errorType=row['errorType'], error=row['error'])
            results.append(row)
            if args.videos:
                proposal_counts = write_proposals(args.videos, results)
            write_json(output/'results.json', {'matcher': args.matcher, 'views': results})
    failures = [row for row in results if row['status'] != 'pnp-refined']
    summary = {'matcher': args.matcher, 'expectedViews': len(selections), 'completedViews': len(results),
        'proposalCounts': proposal_counts, 'seconds': time.perf_counter()-started,
        'viewSeconds': sum(row['seconds'] for row in results),
        'failures': [{key: row[key] for key in ('videoId', 'shotId', 'viewId', 'index', 'status', 'reason', 'errorType', 'error') if key in row}
                     for row in failures],
        'pending': [{key: row[key] for key in ('videoId', 'shotId', 'viewId', 'index')} for row in selections[len(results):]]}
    write_json(output/'summary.json', summary)
    record_log(output, 'run-complete', expectedViews=len(selections), completedViews=len(results),
        proposalCounts=proposal_counts, seconds=summary['seconds'], failures=len(failures), pending=len(summary['pending']))


if __name__ == '__main__':
    main()
