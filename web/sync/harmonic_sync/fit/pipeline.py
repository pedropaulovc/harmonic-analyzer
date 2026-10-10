"""Checkpointed native-geometry camera/setup/crank fit, dense residual validation."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys
from itertools import chain
import time

import cv2
import numpy as np

from ..render_client import RenderClient
from ..video import PROJECT, data_root, decode_selected, load_shots, sha256, video_path, write_json
from .camera import CameraFitter, bounds_points, decimate_camera, interpolate_camera, scale_camera
from .crank import decimate_crank, fit_crank, interpolate_turns, smooth_shot
from .metrics import chamfer_metrics, mask_edges, mask_iou
from .report import save_contact_sheet, write_report
from .setup import default_input
from .snapshot import build_snapshot, source_seal
from .ready import ready_shots
from .first_visible import discover_setups
from .finalize import finalize_video


def log(root: Path, event: str, **fields) -> None:
    record = {'at': time.time(), 'event': event, **fields}
    line = json.dumps(record, allow_nan=False)
    print('[fit] '+line, file=sys.stderr, flush=True)
    root.mkdir(parents=True, exist_ok=True)
    with (root/'fit.jsonl').open('a') as stream:
        stream.write(line+'\n')


def merge_input(base: dict, partial: dict) -> dict:
    result = deepcopy(base)
    for key, value in partial.items():
        if key == 'setup':
            result['setup'].update(value)
        else:
            result[key] = deepcopy(value)
    if len(result['amplitudes']) != 20 or len(result['phases']) != 20:
        raise ValueError('Exactly twenty physical amplitudes/phases are required')
    return result


def target_group(shot: dict, view: dict) -> str:
    label = (view['viewId']+' '+shot['id']).lower()
    text = (label+' '+shot['reason']).lower()
    if view['viewId'] == 'bar-bank' or view['viewId'] == 'lower-inset':
        return 'amplitude-bars'
    if 'rocker-bank' in label:
        return 'amplitude-bars'
    if view['viewId'] == 'upper-inset':
        return 'springs'
    if view['viewId'] == 'main' and any(word in text for word in ('whole', 'turntable', 'presenter')):
        return 'static'
    groups = ((('crank',), 'crank'), (('cone', 'cones', 'gear', 'gears'), 'cones'),
              (('rocker', 'cam', 'rod'), 'channel-1'), (('spring', 'springs'), 'springs'),
              (('summing', 'knife'), 'summing'), (('magnifier', 'magnification', 'clamp'), 'magnifier'),
              (('wheel', 'wire'), 'wheel-wire'), (('platen', 'paper'), 'platen-paper'),
              (('pen',), 'pen'), (('bar', 'bars', 'amplitude'), 'amplitude-bars'))
    # Authored view/shot subject is stronger than narration about another part.
    # Whole words keep "camera" and the caption "crank0" out of physical hints.
    for description in (label, text):
        tokens = set(re.findall(r'[a-z]+[0-9]*', description))
        for words, group in groups:
            if tokens.intersection(words):
                return group
    return 'static'


def load_view(root: Path, shot: dict, view: dict, source_hash: str, width: int) -> dict:
    folder = root/shot['id']/view['viewId']
    index = json.loads((folder/'index.json').read_text())
    motion = json.loads((folder/'motion.json').read_text())
    if not index.get('inputHash'):
        raise ValueError(f'Source stage has not published completion: {folder}')
    if index['sourceSha256'] != source_hash or index['rectSourcePixels'] != view['rectSourcePixels']:
        raise ValueError(f'Stale source identity/layout: {folder}')
    size = (min(width, index['width']), max(1, round(index['height']*min(width, index['width'])/index['width'])))
    rows = index['frames']
    if not rows or any(not shot['startFrame'] <= row['index'] < shot['endFrame'] for row in rows):
        raise ValueError(f'Empty or out-of-shot source frame-index range: {folder}')
    if any(a['index'] >= b['index'] for a, b in zip(rows, rows[1:])):
        raise ValueError(f'Unordered source frame indices: {folder}')
    samples = []
    for row in rows:
        mask = cv2.imread(str(folder/'masks'/f"{row['index']}.png"), cv2.IMREAD_GRAYSCALE)
        edges = cv2.imread(str(folder/'edges'/f"{row['index']}.png"), cv2.IMREAD_GRAYSCALE)
        if mask is None or edges is None or mask.shape != (index['height'], index['width']) or edges.shape != mask.shape:
            raise ValueError(f'Missing/malformed source mask or edge: {folder}/{row["index"]}')
        mask = cv2.resize(mask, size, interpolation=cv2.INTER_NEAREST) > 0
        edges = cv2.resize(edges, size, interpolation=cv2.INTER_AREA) > 12
        samples.append({**row, 'mask': mask, 'edges': edges, 'width': size[0], 'height': size[1],
                        'sourceWidth': view['rectSourcePixels'][2], 'presentation': view['presentation']})
    moving = motion.get('model') == 'not-planar' or any(word in shot['reason'].lower() for word in ('turntable', 'zooms', 'zoom', 'reframed', 'expands', 'shrinks'))
    trusted = [row for row in motion.get('frames', []) if row.get('H') is not None and row.get('inlierRatio', 0) >= .3]
    corners = np.array([[0, 0], [index['width'], 0], [0, index['height']], [index['width'], index['height']]], np.float32).reshape(1, -1, 2)
    if trusted:
        displacement = [np.max(np.linalg.norm(cv2.perspectiveTransform(corners, np.array(row['H']).reshape(3, 3))-corners, axis=2)) for row in trusted]
        moving |= max(displacement) > 3
    if 'stationary' in shot['reason'].lower() and not any(word in shot['reason'].lower() for word in ('zoom', 'expands', 'shrinks')):
        moving = False
    return {'view': view, 'folder': folder, 'index': index, 'motion': motion, 'samples': samples, 'moving': moving}


def selected_keys(samples: list[dict], moving: bool) -> list[dict]:
    usable = [sample for sample in samples if np.count_nonzero(sample['mask']) >= 8]
    if not usable:
        return []
    if not moving:
        candidates = [usable[0], usable[len(usable)//2], usable[-1]]
        return [max(candidates, key=lambda sample: sample['sharpness'])]
    times = np.arange(usable[0]['t'], usable[-1]['t'], .5).tolist()+[usable[-1]['t']]
    unique = {min(usable, key=lambda sample: abs(sample['t']-t))['index'] for t in times}
    return [sample for sample in usable if sample['index'] in unique]


def fingerprint(shot: dict, views: list[dict], segments: list[dict], manual: dict, model_hash: str, width: int, render_code_hash: str) -> str:
    digest = hashlib.sha256(json.dumps({'shot': shot, 'segments': segments, 'manual': manual, 'model': model_hash, 'width': width, 'renderCode': render_code_hash}, sort_keys=True).encode())
    for module in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(module.read_bytes())
    for source in views:
        for name in ('index.json', 'motion.json'):
            digest.update((source['folder']/name).read_bytes())
    return digest.hexdigest()


def source_frame(source: dict, index: int, fps: Fraction) -> np.ndarray:
    path = source['folder']/'frames'/f'{index}.png'
    image = cv2.imread(str(path)) if path.is_file() else next(iter(decode_selected(video_path(source['index']['videoId']), [index], fps)))[1]
    if image is None:
        raise ValueError(f'Cannot decode source photograph {path}')
    if not path.is_file():
        if not cv2.imwrite(str(path), image):
            raise OSError(f'Cannot cache decoded source frame {path}')
    x, y, w, h = source['view']['rectSourcePixels']
    crop = image[y:y+h, x:x+w]
    return cv2.cvtColor(cv2.resize(crop, (source['samples'][0]['width'], source['samples'][0]['height'])), cv2.COLOR_BGR2RGB)


def request(sample: dict) -> dict:
    return {field: sample[field] for field in ('camera', 'input', 'width', 'height', 'presentation')}


def validate_frame(ids: np.ndarray, sample: dict, group_ids: dict) -> dict:
    rendered = ids > 0
    rendered_edges = cv2.morphologyEx(ids.astype(np.uint16), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    scale = sample['sourceWidth']
    groups = {}
    for name, value in group_ids.items():
        projected = ids == value
        area = int(np.count_nonzero(projected))
        if area < 8:
            groups[name] = {'iou': None, 'chamferPx': None, 'visiblePixels': area, 'source': 'projection-conditioned'}
            continue
        support = cv2.dilate(projected.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0
        ys, xs = np.nonzero(support)
        bounds = (slice(ys.min(), ys.max()+1), slice(xs.min(), xs.max()+1))
        projected_crop = projected[bounds]
        source_mask = (sample['mask'] & support)[bounds]
        source_edges = (sample['edges'] & support)[bounds]
        crop_scale = scale * projected_crop.shape[1] / sample['width']
        groups[name] = {'iou': mask_iou(source_mask, projected_crop),
                        **chamfer_metrics(source_edges, mask_edges(projected_crop), source_width=crop_scale),
                        'visiblePixels': area, 'sourceEdgePixels': int(np.count_nonzero(source_edges)), 'source': 'projection-conditioned'}
    return {'iou': mask_iou(sample['mask'], rendered),
            **chamfer_metrics(sample['edges'], rendered_edges, source_width=scale),
            'sourceEdgePixels': int(np.count_nonzero(sample['edges'])), 'renderEdgePixels': int(np.count_nonzero(rendered_edges)),
            'groups': groups}


def fit_video(video_id: str, *, shot_id: str | None = None, width: int = 480, force: bool = False, url: str | None = None) -> dict:
    if width < 64:
        raise ValueError('Fit width must be at least64 pixels')
    started = time.perf_counter()
    root = data_root()
    if root.resolve().is_relative_to(PROJECT.parent.parent):
        raise ValueError('Derived source/fitting data must be outside the repository')
    if shot_id is None and url:
        raise ValueError('Full fits own an immutable native snapshot; --url is for --shot iteration only')
    video_root = root/video_id
    census = load_shots(video_id)
    segments = json.loads((PROJECT/'videos'/video_id/'segments.json').read_text())['segments']
    if not segments or any(a['end'] > b['start'] or a['start'] >= a['end'] for a, b in zip(segments, segments[1:])):
        raise ValueError('Setup segments must be ordered, nonempty and nonoverlapping')
    manual_path = PROJECT/'videos'/video_id/'manual.json'
    manual = json.loads(manual_path.read_text()) if manual_path.is_file() else {'cameraKeys': [], 'segments': [], 'crank': []}
    overrides = {entry['id']: entry for entry in manual.get('segments', [])}
    segments = [{**segment, **{field: overrides[segment['id']][field] for field in ('start', 'end') if segment['id'] in overrides and field in overrides[segment['id']]}} for segment in segments]
    fps_float = census['fps'][0]/census['fps'][1]
    if any(round(segment['start']*fps_float) >= round(segment['end']*fps_float) for segment in segments) or any(round(a['end']*fps_float) != round(b['start']*fps_float) for a, b in zip(segments, segments[1:])):
        raise ValueError('Manual/authored segment intervals must remain a contiguous timeline')
    model_hash = sha256(PROJECT.parent/'public'/'models'/'ha-harmonic-analyzer.glb')
    if not video_path(video_id).is_file():
        raise FileNotFoundError(video_path(video_id))
    source_hash = sha256(video_path(video_id))
    if source_hash != census['sourceSha256']:
        raise ValueError('Source video hash differs from shot census')
    manual_segments = {segment['id']: segment for segment in manual.get('segments', [])}
    def in_shot(t: float, shot: dict) -> bool:
        return shot['startFrame'] <= round(t*fps_float) < shot['endFrame']
    def segment_at(t: float) -> dict:
        index = round(t*fps_float)
        for segment in segments:
            if round(segment['start']*fps_float) <= index < round(segment['end']*fps_float):
                return segment
        raise ValueError(f'No setup segment contains {t}')
    chosen = [shot for shot in census['shots'] if shot['classification'] != 'non-machine' and (shot_id is None or shot['id'] == shot_id)]
    if shot_id and not chosen:
        raise ValueError(f'No photographed shot {shot_id}')
    # Production consumes final ready entries incrementally, without a global
    # barrier. A scoped development fit still refuses missing source markers.
    if shot_id:
        for shot in chosen:
            for view in shot['views']:
                folder = video_root/shot['id']/view['viewId']
                if not (folder/'index.json').is_file() or not (folder/'motion.json').is_file():
                    raise FileNotFoundError(f'Source stage incomplete: {folder}')
    work = iter(chosen) if shot_id else ready_shots(census, root)
    first_shot = next(work)
    runtime_segments: dict[str, dict] = {}
    def segment_input(t: float) -> dict:
        carried = default_input(video_id)
        for authored in segments:
            if round(authored['start']*fps_float) > round(t*fps_float):
                break
            if authored['id'] in runtime_segments:
                carried = merge_input(carried, runtime_segments[authored['id']]['input'])
            else:
                carried = merge_input(carried, authored.get('init', {}))
                if authored['id'] in manual_segments:
                    carried = merge_input(carried, manual_segments[authored['id']]['init'])
        carried['crankTurns'] = previous_turns
        return carried
    segment_evidence = {}
    crank_keys: list[dict] = []
    residuals = []
    runtime_shots = []
    sheets = []
    camera_fit_entries = []
    shot_timing = []
    candidate_infeasibility = []
    previous_turns = 0.
    snapshot, snapshot_info = (None, {'mode': 'development-iteration'}) if shot_id else build_snapshot(PROJECT.parent, root)
    render_sources = snapshot_info.get('sourceFilesSha256') or source_seal(PROJECT.parent)
    render_code_hash = hashlib.sha256(json.dumps(render_sources, sort_keys=True).encode()).hexdigest()
    if snapshot and snapshot_info['bundleFilesSha256']['models/ha-harmonic-analyzer.glb'] != model_hash:
        raise ValueError('Frozen snapshot model differs from the source model identity')
    with RenderClient(url, data_root=root, quiet_batches=True, preview=snapshot is not None, preview_out_dir=snapshot) as client:
        ready = client.ready()
        group_ids = ready['groupIds']
        camera_fitter = CameraFitter(client, ready)
        for shot in chain([first_shot], work):
            shot_started = time.perf_counter()
            infeasible_before = dict(client.candidate_failure_counts)
            log(root, 'shot-start', videoId=video_id, shotId=shot['id'])
            sources = [load_view(video_root, shot, view, source_hash, width) for view in shot['views']]
            driver = max(sources, key=lambda source: np.median([sample['maskArea'] for sample in source['samples']]) / np.prod(source['index']['maskScale']))
            driver_view_id = driver['view']['viewId']
            checkpoint = video_root/'fit-checkpoints'/f"{shot['id']}.json"
            stamp = fingerprint(shot, sources, segments, manual, model_hash, width, render_code_hash)
            if not force and checkpoint.is_file():
                saved = json.loads(checkpoint.read_text())
                if saved['fingerprint'] == stamp:
                    runtime_shots.append(saved['shot'])
                    crank_keys.extend(saved['crank'])
                    residuals.extend(saved['frames'])
                    sheets.extend(saved['contactSheets'])
                    camera_fit_entries.extend(saved.get('cameraFitEntries', []))
                    shot_timing.append({'shotId': shot['id'], 'fitSeconds': saved['seconds'], 'resumed': True})
                    candidate_infeasibility.append({'shotId': shot['id'], 'reasons': saved.get('infeasibleCandidates', {})})
                    previous_turns = saved['crank'][-1]['turns'] if saved['crank'] else previous_turns
                    log(root, 'shot-resume', videoId=video_id, shotId=shot['id'], seconds=time.perf_counter()-shot_started)
                    continue
            camera_keys = {}
            manual_cameras = {}
            for source in sources:
                view = source['view']
                view_id = view['viewId']
                fixed = [key for key in manual.get('cameraKeys', []) if key['shotId'] == shot['id'] and key['viewId'] == view_id]
                fixed = [{'t': key['t'], 'camera': scale_camera(key['camera'], tuple(view['rectSourcePixels'][2:]), (source['samples'][0]['width'], source['samples'][0]['height']))} for key in fixed]
                if any(not in_shot(key['t'], shot) for key in fixed):
                    raise ValueError(f'Manual camera key outside shot: {shot["id"]}/{view_id}')
                manual_cameras[view_id] = fixed
                if fixed:
                    camera_keys[view_id] = sorted(fixed, key=lambda key: key['t'])
                    continue
                keys = []
                seed = None
                for sample in selected_keys(source['samples'], source['moving']):
                    sample['input'] = segment_input(sample['t'])
                    focus = target_group(shot, view)
                    seed, loss = camera_fitter.fit(sample, target_group=focus, seed=seed, coarse=seed is None,
                                                   evaluations=140 if seed is None else 30,
                                                   full_pose=focus != 'static')
                    keys.append({'t': sample['t'], 'camera': seed, 'loss': loss})
                    camera_fit_entries.append({'paths': ['camera'], 'groups': list(group_ids),
                                               'shotId': shot['id'], 'viewId': view_id,
                                               'index': sample['index'], 't': sample['t']})
                if not keys:
                    raise ValueError(f'No nonempty source masks: {shot["id"]}/{view_id}')
                camera_keys[view_id] = keys
            # Editorial insets can be independent takes. The largest source
            # machine view alone drives the shot's single mechanism state.
            exposures = {sample['index']: sample for sample in driver['samples']}
            shot_crank = []
            shot_track_evidence = []
            for index in sorted(exposures):
                source, sample = driver, exposures[index]
                segment = segment_at(sample['t'])
                segment_id = segment['id']
                sample['input'] = segment_input(sample['t'])
                sample['camera'] = interpolate_camera(camera_keys[source['view']['viewId']], sample['t'])
                fixed = {key['t']: key['turns'] for key in manual.get('crank', []) if in_shot(key['t'], shot)}
                nearest = min(fixed, key=lambda t: abs(t-sample['t'])) if fixed else None
                if nearest is not None and round(nearest*fps_float) == sample['index']:
                    turns, origin, evidence = fixed[nearest], 'held', {'manual': True}
                else:
                    turns, origin, evidence = fit_crank(client, sample, group_ids, previous_turns,
                        grid_count=9 if not shot_crank else 5)
                previous_turns = turns
                shot_crank.append({'t': sample['t'], 'turns': turns, 'source': origin})
                shot_track_evidence.append({'index': index, 't': sample['t'], **evidence})
            fixed = {key['t']: key['turns'] for key in manual.get('crank', []) if in_shot(key['t'], shot)}
            shot_crank, smooth_evidence = smooth_shot(shot_crank, fixed)
            # One full-pose alternation, always keeping manual camera records fixed.
            for source in sources:
                view_id = source['view']['viewId']
                if manual_cameras[view_id]:
                    continue
                for key_index, key in enumerate(camera_keys[view_id]):
                    sample = min(source['samples'], key=lambda sample: abs(sample['t']-key['t']))
                    sample['input'] = segment_input(sample['t'])
                    sample['input']['crankTurns'] = interpolate_turns(shot_crank, sample['t'])
                    key['camera'], key['loss'] = camera_fitter.fit(
                        sample, target_group=target_group(shot, source['view']),
                        seed=key['camera'], coarse=False,
                        evaluations=140 if key_index == 0 else 30, full_pose=True)
            shot_frames = []
            shot_views = []
            shot_sheets = []
            origins = {key['t']: key['source'] for key in shot_crank}
            for source in sources:
                view, samples = source['view'], source['samples']
                view_id = view['viewId']
                worst = []
                for offset in range(0, len(samples), 64):
                    batch = samples[offset:offset+64]
                    for sample in batch:
                        sample['camera'] = interpolate_camera(camera_keys[view_id], sample['t'])
                        sample['input'] = segment_input(sample['t'])
                        sample['input']['crankTurns'] = interpolate_turns(shot_crank, sample['t'])
                    arrays = client.render_batch([request(sample) for sample in batch], shot_id=shot['id'], view_id=view_id)
                    for sample, ids in zip(batch, arrays):
                        row = {'shotId': shot['id'], 'viewId': view_id, 'index': sample['index'], 't': sample['t'],
                               'segmentId': segment_at(sample['t'])['id'], 'turns': sample['input']['crankTurns'],
                               'crankSource': origins.get(sample['t'], 'inferred'), 'cameraSource': 'manual' if manual_cameras[view_id] else 'fitted',
                               'validationScope': 'driver' if view_id == driver_view_id else 'independent-take, not validated',
                               **validate_frame(ids, sample, group_ids)}
                        shot_frames.append(row)
                        worst.append((row, sample['index'], sample, ids.copy()))
                        worst.sort(key=lambda item: (
                            -1. if item[0]['iou'] is None else item[0]['iou'],
                            -(item[0]['chamferPx'] or 1e9)))
                        del worst[4:]
                errors = [row['chamferPx'] for row in shot_frames if row['viewId'] == view_id and row['chamferPx'] is not None]
                observed = [row for row in shot_frames if row['viewId'] == view_id]
                qualified = bool(observed) and all(
                    row['iou'] is not None and row['iou'] >= .5 and all(
                        row[field] is not None and row[field] <= 960
                        for field in ('renderToSourceChamferPx', 'sourceToRenderChamferPx'))
                    for row in observed)
                quality = {'medianPx': float(np.median(errors)) if errors else None,
                           'p90Px': float(np.percentile(errors, 90)) if errors else None,
                           'maxPx': float(max(errors)) if errors else None,
                           'status': 'manual' if manual_cameras[view_id] else ('fitted' if qualified else 'unfitted')}
                size = tuple(view['rectSourcePixels'][2:])
                exported = [{'t': key['t'], 'camera': scale_camera(key['camera'], (samples[0]['width'], samples[0]['height']), size)} for key in camera_keys[view_id]]
                exported = decimate_camera(exported, bounds_points(ready['boundsMetres']), size, fixed_times={key['t'] for key in manual_cameras[view_id]})
                shot_views.append({**view, 'cameraKeys': exported, 'quality': quality})
                panels = [{'source': source_frame(source, index, Fraction(*census['fps'])), 'ids': ids,
                           'title': f'{shot["id"]}/{view_id} t={sample["t"]:.3f}s T={sample["input"]["crankTurns"]:.3f}',
                           'errorPx': row['chamferPx'], 'iou': row['iou'],
                           'renderToSourceChamferPx': row['renderToSourceChamferPx'],
                           'sourceToRenderChamferPx': row['sourceToRenderChamferPx']}
                          for row, index, sample, ids in worst]
                path = video_root/'report'/'contact-sheets'/f'{shot["id"]}--{view_id}.png'
                if panels:
                    save_contact_sheet(path, panels, group_ids)
                    shot_sheets.append(str(path))
            runtime_shot = {field: shot[field] for field in ('id', 'start', 'end', 'startFrame', 'endFrame', 'classification')}
            runtime_shot['views'] = shot_views
            runtime_shot['driverViewId'] = driver_view_id
            infeasible = {reason: count-infeasible_before.get(reason, 0) for reason, count in client.candidate_failure_counts.items() if count > infeasible_before.get(reason, 0)}
            candidate_infeasibility.append({'shotId': shot['id'], 'reasons': infeasible})
            saved = {'fingerprint': stamp, 'shot': runtime_shot, 'segments': runtime_segments,
                     'sourceStageHashes': shot.get('_readyHashes'), 'renderCodeSha256': render_code_hash,
                     'segmentEvidence': segment_evidence, 'crank': shot_crank, 'frames': shot_frames,
                     'contactSheets': shot_sheets, 'trackingEvidence': shot_track_evidence, 'smoothing': smooth_evidence,
                     'infeasibleCandidates': infeasible,
                     'cameraFitEntries': [entry for entry in camera_fit_entries if entry['shotId'] == shot['id']],
                     'seconds': time.perf_counter()-shot_started}
            write_json(checkpoint, saved)
            runtime_shots.append(runtime_shot)
            crank_keys.extend(shot_crank)
            residuals.extend(shot_frames)
            sheets.extend(shot_sheets)
            shot_timing.append({'shotId': shot['id'], 'fitSeconds': saved['seconds'], 'resumed': False})
            previous_turns = shot_crank[-1]['turns'] if shot_crank else previous_turns
            log(root, 'shot-complete', videoId=video_id, shotId=shot['id'], frames=len(shot_frames), seconds=saved['seconds'], smoothing=smooth_evidence)
        crank_keys.sort(key=lambda key: key['t'])
        runtime_segments, segment_evidence = discover_setups(
            client, ready, census, root, runtime_shots, segments, manual, width, crank_keys,
            render_code_hash=render_code_hash, force=force)
        reasons_by_shot = {entry['shotId']: entry['reasons'] for entry in candidate_infeasibility}
        for evidence in segment_evidence.values():
            for attempt in evidence.get('attempts', []):
                reasons = reasons_by_shot.setdefault(attempt['shotId'], {})
                for stage in ('bank', 'setup'):
                    for reason, count in attempt.get(stage, {}).get('infeasibleCandidates', {}).items():
                        reasons[reason] = reasons.get(reason, 0) + count
        candidate_infeasibility = [{'shotId': shot, 'reasons': reasons} for shot, reasons in reasons_by_shot.items()]
        for entry in camera_fit_entries:
            segment_id = segment_at(entry['t'])['id']
            segment_evidence.setdefault(segment_id, {}).setdefault('parameterFits', []).append(entry)
        fixed_crank_times = {key['t'] for key in manual.get('crank', [])}
        fixed_crank_times.update(entry['t'] for evidence in segment_evidence.values()
                                 for entry in evidence.get('parameterFits', []) if entry['paths'] != ['camera'])
        for shot in runtime_shots:
            local = [key for key in crank_keys if in_shot(key['t'], shot)]
            if local:
                fixed_crank_times.update((local[0]['t'], local[-1]['t']))
        crank_keys = decimate_crank(crank_keys, fixed_times=fixed_crank_times)
        final = finalize_video(client, ready, census, root, runtime_shots, runtime_segments,
                               segment_evidence, manual, width, crank_keys, render_code_hash=render_code_hash, force=force)
        runtime_shots, residuals, sheets = final['shots'], final['frames'], final['contactSheets']
        timing_by_shot = {entry['shotId']: entry for entry in shot_timing}
        for entry in final['shotTiming']:
            timing_by_shot[entry['shotId']].update(entry)
    by_shot = {shot['id']: shot for shot in runtime_shots}
    final_shots = [by_shot.get(shot['id'], {**{field: shot[field] for field in ('id', 'start', 'end', 'startFrame', 'endFrame', 'classification')}, 'views': []}) for shot in census['shots']]
    by_time = {key['t']: key for key in crank_keys}
    for key in manual.get('crank', []):
        by_time[key['t']] = {'t': key['t'], 'turns': key['turns'], 'source': 'held'}
    crank_keys = [by_time[t] for t in sorted(by_time)]
    track = {'schemaVersion': 1, 'videoId': video_id, 'sourceSha256': source_hash, 'modelSha256': model_hash, 'fps': census['fps'],
             'shots': final_shots, 'segments': [runtime_segments[segment['id']] for segment in segments],
             'crank': crank_keys}
    serialized = json.dumps(track, separators=(',', ':'), allow_nan=False)+'\n'
    if shot_id is None:
        destination = PROJECT.parent/'content'/'sync'/f'{video_id}.sync.json'
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.json.tmp')
        temporary.write_text(serialized)
        temporary.replace(destination)
    else:
        write_json(video_root/'report'/f'partial-{shot_id}.sync.json', track)
    result = {'videoId': video_id, 'sourceSha256': source_hash, 'modelSha256': model_hash,
              'runtimeSeconds': time.perf_counter()-started, 'channelMapping': ready['channelMapping'],
              'renderSnapshot': snapshot_info, 'renderer': ready['renderer'],
              'segments': track['segments'], 'segmentEvidence': segment_evidence, 'shots': final_shots,
              'frames': residuals, 'syncBytes': len(serialized.encode()), 'contactSheets': sheets,
              'candidateInfeasibility': candidate_infeasibility,
              'shotTiming': list(timing_by_shot.values()), 'frozenValidationSeconds': final['seconds'],
              'timing': {'maxSourceClockErrorSeconds': max((abs(row['t']-row['index']*census['fps'][1]/census['fps'][0]) for row in residuals), default=None),
                         'method': 'Frame-index sample clock; fitted model state requested at each corresponding index/fps'},
              'partial': shot_id is not None, 'sourceCoverage': {'expectedViews': sum(len(shot['views']) for shot in census['shots'] if shot['classification'] != 'non-machine'),
              'processedViews': sum(len(shot['views']) for shot in runtime_shots),
              'missingViews': [{'shotId': shot['id'], 'viewId': view['viewId']} for shot in census['shots'] if shot['classification'] != 'non-machine' and shot['id'] not in by_shot for view in shot['views']]}}
    write_json(video_root/'report'/'residuals.json', result)
    summary = write_report(video_id, root, result)
    log(root, 'video-complete', videoId=video_id, runtimeSeconds=result['runtimeSeconds'], syncBytes=result['syncBytes'], partial=result['partial'])
    return summary
