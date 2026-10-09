"""Checkpointed native-geometry camera/setup/crank fit, dense residual validation."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
from itertools import chain
import time

import cv2
import numpy as np

from ..render_client import RenderClient
from ..video import PROJECT, data_root, decode_selected, load_shots, sha256, video_path, write_json
from .camera import CameraFitter, bounds_points, decimate_camera, interpolate_camera, scale_camera
from .crank import decimate_crank, fit_bank_offset, fit_crank, interpolate_turns, smooth_shot
from .metrics import mask_edges, mask_iou, symmetric_chamfer
from .report import save_contact_sheet, write_report
from .setup import default_input, fit_setup
from .snapshot import build_snapshot, source_seal
from .ready import ready_shots


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
    text = (shot['id']+' '+shot['reason']).lower()
    if view['viewId'] == 'main' and any(word in text for word in ('whole', 'turntable', 'presenter')):
        return 'static'
    for words, group in ((('crank',), 'crank'), (('cone', 'gear'), 'cones'), (('rocker', 'cam', 'rod'), 'channel-1'),
                         (('spring',), 'springs'), (('summing', 'knife'), 'summing'), (('magnif', 'clamp'), 'magnifier'),
                         (('wheel', 'wire'), 'wheel-wire'), (('pen',), 'pen'), (('platen', 'paper'), 'platen-paper')):
        if any(word in text for word in words):
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
    x, y, w, h = source['view']['rectSourcePixels']
    crop = image[y:y+h, x:x+w]
    return cv2.cvtColor(cv2.resize(crop, (source['samples'][0]['width'], source['samples'][0]['height'])), cv2.COLOR_BGR2RGB)


def request(sample: dict) -> dict:
    return {field: sample[field] for field in ('camera', 'input', 'width', 'height', 'presentation')}


def validate_frame(ids: np.ndarray, sample: dict, group_ids: dict) -> dict:
    rendered = ids > 0
    rendered_edges = mask_edges(rendered)
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
                        'chamferPx': symmetric_chamfer(source_edges, mask_edges(projected_crop), source_width=crop_scale),
                        'visiblePixels': area, 'sourceEdgePixels': int(np.count_nonzero(source_edges)), 'source': 'projection-conditioned'}
    return {'iou': mask_iou(sample['mask'], rendered),
            'chamferPx': symmetric_chamfer(sample['edges'], rendered_edges, source_width=scale),
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
            if authored['start'] > t:
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
    candidate_infeasibility = []
    previous_turns = 0.
    snapshot, snapshot_info = (None, {'mode': 'development-iteration'}) if shot_id else build_snapshot(PROJECT.parent, root)
    render_sources = snapshot_info.get('sourceFilesSha256') or source_seal(PROJECT.parent)
    render_code_hash = hashlib.sha256(json.dumps(render_sources, sort_keys=True).encode()).hexdigest()
    if snapshot and snapshot_info['bundleFilesSha256']['models/ha-harmonic-analyzer.glb'] != model_hash:
        raise ValueError('Frozen snapshot model differs from the source model identity')
    setup_stamp = hashlib.sha256(json.dumps({'segments': segments, 'manual': manual.get('segments', []), 'model': model_hash, 'render': render_code_hash, 'setupCode': sha256(Path(__file__).parent/'setup.py')}, sort_keys=True).encode()).hexdigest()
    setup_checkpoint = video_root/'fit-checkpoints'/'setups.json'
    if not shot_id and not force and setup_checkpoint.is_file():
        cached_setup = json.loads(setup_checkpoint.read_text())
        if cached_setup['fingerprint'] == setup_stamp:
            runtime_segments.update(cached_setup['segments'])
            segment_evidence.update(cached_setup['evidence'])
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
                    for segment_id, value in saved['segments'].items():
                        runtime_segments.setdefault(segment_id, value)
                    for segment_id, value in saved['segmentEvidence'].items():
                        segment_evidence.setdefault(segment_id, value)
                    crank_keys.extend(saved['crank'])
                    residuals.extend(saved['frames'])
                    sheets.extend(saved['contactSheets'])
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
                    seed, loss = camera_fitter.fit(sample, target_group=target_group(shot, view), seed=seed, coarse=seed is None,
                                                   evaluations=140 if seed is None else 30)
                    keys.append({'t': sample['t'], 'camera': seed, 'loss': loss})
                if not keys:
                    raise ValueError(f'No nonempty source masks: {shot["id"]}/{view_id}')
                camera_keys[view_id] = keys
            # Editorial insets can be independent takes. The largest source
            # machine view alone drives the shot's single mechanism state.
            exposures = {sample['index']: sample for sample in driver['samples']}
            explicit_handle = 'crank' in (shot['id']+' '+shot['reason']).lower() and len(sources) == 1
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
                        explicit_handle_view=explicit_handle, grid_count=9 if not shot_crank else 5)
                usable_setup = shot['classification'] == 'machine' and np.count_nonzero(sample['mask']) >= 50 and np.count_nonzero(sample['edges']) >= 25
                if segment_id not in runtime_segments and usable_setup:
                    partial = deepcopy(segment)
                    is_manual = segment_id in manual_segments
                    if is_manual:
                        entry = manual_segments[segment_id]
                        partial.update({field: entry[field] for field in ('start', 'end') if field in entry})
                        partial['init'] = merge_input(sample['input'], entry['init'])
                        partial['fit'] = []
                        sample['input'] = merge_input(sample['input'], entry['init'])
                    bank_evidence = {'provenance': 'manual' if is_manual else 'chosen', 'reason': 'Bank origin unavailable or manually fixed'}
                    if not is_manual and not fixed:
                        turns, bank_evidence = fit_bank_offset(client, sample, group_ids, turns)
                        partial['fit'] = [path for path in partial.get('fit', []) if path != 'setup.driveCrankOffsetTurns']
                        partial.setdefault('init', {}).setdefault('setup', {})['driveCrankOffsetTurns'] = sample['input']['setup']['driveCrankOffsetTurns']
                    sample['turns'] = turns
                    sample['input']['crankTurns'] = turns
                    fitted, setup_evidence = fit_setup(client, partial, [sample], group_ids=group_ids, manual=is_manual)
                    if bank_evidence['provenance'] == 'bank-inferred':
                        fitted['provenance']['setup.driveCrankOffsetTurns'] = 'fitted'
                    runtime_segments[segment_id] = fitted
                    segment_evidence[segment_id] = {'bank': bank_evidence, 'setup': setup_evidence, 'fitFrame': {'shotId': shot['id'], 'viewId': source['view']['viewId'], 'index': index, 't': sample['t']}}
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
                for key in camera_keys[view_id]:
                    sample = min(source['samples'], key=lambda sample: abs(sample['t']-key['t']))
                    sample['input'] = segment_input(sample['t'])
                    sample['input']['crankTurns'] = interpolate_turns(shot_crank, sample['t'])
                    key['camera'], key['loss'] = camera_fitter.fit(sample, seed=key['camera'], coarse=False, evaluations=25, full_pose=True)
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
                        worst.append((row['chamferPx'] if row['chamferPx'] is not None else 1e9, sample['index'], sample, ids.copy()))
                        worst.sort(key=lambda item: item[0], reverse=True)
                        del worst[4:]
                errors = [row['chamferPx'] for row in shot_frames if row['viewId'] == view_id and row['chamferPx'] is not None]
                quality = {'medianPx': float(np.median(errors)) if errors else None,
                           'p90Px': float(np.percentile(errors, 90)) if errors else None,
                           'maxPx': float(max(errors)) if errors else None,
                           'status': 'manual' if manual_cameras[view_id] else ('fitted' if len(errors) == len(samples) and max(errors) <= 960 else 'unfitted')}
                size = tuple(view['rectSourcePixels'][2:])
                exported = [{'t': key['t'], 'camera': scale_camera(key['camera'], (samples[0]['width'], samples[0]['height']), size)} for key in camera_keys[view_id]]
                exported = decimate_camera(exported, bounds_points(ready['boundsMetres']), size, fixed_times={key['t'] for key in manual_cameras[view_id]})
                shot_views.append({**view, 'cameraKeys': exported, 'quality': quality})
                panels = [{'source': source_frame(source, index, Fraction(*census['fps'])), 'ids': ids,
                           'title': f'{shot["id"]}/{view_id} t={sample["t"]:.3f}s T={sample["input"]["crankTurns"]:.3f}',
                           'errorPx': None if error == 1e9 else error} for error, index, sample, ids in worst]
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
                     'seconds': time.perf_counter()-shot_started}
            write_json(checkpoint, saved)
            runtime_shots.append(runtime_shot)
            crank_keys.extend(shot_crank)
            residuals.extend(shot_frames)
            sheets.extend(shot_sheets)
            previous_turns = shot_crank[-1]['turns'] if shot_crank else previous_turns
            if not shot_id:
                write_json(setup_checkpoint, {'fingerprint': setup_stamp, 'segments': runtime_segments, 'evidence': segment_evidence})
            log(root, 'shot-complete', videoId=video_id, shotId=shot['id'], frames=len(shot_frames), seconds=saved['seconds'], smoothing=smooth_evidence)
    # Hidden/non-machine setup intervals retain an explicit chosen prior.
    prior = default_input(video_id)
    for segment in segments:
        segment_id = segment['id']
        if segment_id not in runtime_segments:
            prior = merge_input(prior, segment.get('init', {}))
            entry = manual_segments.get(segment_id)
            if entry:
                prior = merge_input(prior, entry['init'])
            prior.pop('crankTurns', None)
            runtime_segments[segment_id] = {'id': segment_id, 'start': segment['start'], 'end': segment['end'],
                                           'input': deepcopy(prior), 'provenance': {
                                               path: 'manual' if entry and (path.split('.')[0] in entry['init']) else 'chosen'
                                               for path in [*(f'amplitudes.{j}' for j in range(20)), *(f'phases.{j}' for j in range(20)),
                                                            'gearing', 'magnification', *(f'setup.{key}' for key in prior['setup'])]}}
        prior = runtime_segments[segment_id]['input']
    by_shot = {shot['id']: shot for shot in runtime_shots}
    final_shots = [by_shot.get(shot['id'], {**{field: shot[field] for field in ('id', 'start', 'end', 'startFrame', 'endFrame', 'classification')}, 'views': []}) for shot in census['shots']]
    by_time = {key['t']: key for key in crank_keys}
    for key in manual.get('crank', []):
        by_time[key['t']] = {'t': key['t'], 'turns': key['turns'], 'source': 'held'}
    crank_keys = [by_time[t] for t in sorted(by_time)]
    track = {'schemaVersion': 1, 'videoId': video_id, 'sourceSha256': source_hash, 'modelSha256': model_hash, 'fps': census['fps'],
             'shots': final_shots, 'segments': [runtime_segments[segment['id']] for segment in segments],
             'crank': decimate_crank(crank_keys, fixed_times={key['t'] for key in manual.get('crank', [])})}
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
              'timing': {'maxSourceClockErrorSeconds': max((abs(row['t']-row['index']*census['fps'][1]/census['fps'][0]) for row in residuals), default=None),
                         'method': 'Frame-index sample clock; fitted model state requested at each corresponding index/fps'},
              'partial': shot_id is not None, 'sourceCoverage': {'expectedViews': sum(len(shot['views']) for shot in census['shots'] if shot['classification'] != 'non-machine'),
              'processedViews': sum(len(shot['views']) for shot in runtime_shots),
              'missingViews': [{'shotId': shot['id'], 'viewId': view['viewId']} for shot in census['shots'] if shot['classification'] != 'non-machine' and shot['id'] not in by_shot for view in shot['views']]}}
    write_json(video_root/'report'/'residuals.json', result)
    summary = write_report(video_id, root, result)
    log(root, 'video-complete', videoId=video_id, runtimeSeconds=result['runtimeSeconds'], syncBytes=result['syncBytes'], partial=result['partial'])
    return summary
