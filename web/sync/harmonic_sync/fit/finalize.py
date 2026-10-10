"""Dense, strict native validation after segment parameters have been frozen."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .camera import interpolate_camera, scale_camera
from .crank import crank_support, interpolate_turns


def finalize_video(client, ready, census, root, runtime_shots, runtime_segments,
                   segment_evidence, manual, width, crank_keys, *, render_code_hash: str,
                   force: bool = False) -> dict:
    # Import lazily: pipeline owns source transforms and report conventions.
    from . import pipeline as p

    started = time.perf_counter()
    root = Path(root)
    video_id = census['videoId']
    video_root = root/video_id
    fps = Fraction(*census['fps'])
    segments = list(runtime_segments.values()) if isinstance(runtime_segments, dict) else list(runtime_segments)
    segments.sort(key=lambda segment: segment['start'])
    census_shots = {shot['id']: shot for shot in census['shots']}
    group_ids = ready['groupIds']
    code = hashlib.sha256()
    for module in sorted(Path(__file__).parent.glob('*.py')):
        code.update(module.read_bytes())
    result = {'shots': [], 'frames': [], 'contactSheets': [], 'seconds': 0.,
              'candidateInfeasibility': [], 'shotTiming': []}

    def segment_at(index):
        for segment in segments:
            if round(segment['start']*fps) <= index < round(segment['end']*fps):
                return segment
        raise ValueError(f'No frozen setup segment contains source frame {index}')

    def fits_for(segment_id):
        entries = segment_evidence.get('parameterFits', [])
        if isinstance(entries, list):
            shared = [entry for entry in entries if entry.get('segmentId', segment_id) == segment_id]
        else:
            shared = entries.get(segment_id, [])
        return [*shared, *segment_evidence.get(segment_id, {}).get('parameterFits', [])]

    for runtime_shot in sorted(runtime_shots, key=lambda shot: shot['startFrame']):
        shot_started = time.perf_counter()
        shot_id = runtime_shot['id']
        p.log(root, 'validation-shot-start', videoId=video_id, shotId=shot_id)
        shot = census_shots[shot_id]
        sources = [p.load_view(video_root, shot, view, census['sourceSha256'], width)
                   for view in shot['views']]
        relevant = [segment for segment in segments
                    if round(segment['start']*fps) < shot['endFrame']
                    and round(segment['end']*fps) > shot['startFrame']]
        local_keys = [deepcopy(key) for key in crank_keys
                      if shot['startFrame'] <= round(key['t']*fps) < shot['endFrame']]
        for key in manual.get('crank', []):
            if shot['startFrame'] <= round(key['t']*fps) < shot['endFrame']:
                local_keys = [entry for entry in local_keys if entry['t'] != key['t']]
                local_keys.append({**key, 'source': 'held'})
        local_keys.sort(key=lambda key: key['t'])
        if not local_keys:
            raise ValueError(f'No frozen crank keys for shot {shot_id}')
        manual_cameras = [key for key in manual.get('cameraKeys', []) if key['shotId'] == shot_id]
        payload = {'shot': runtime_shot, 'sourceViews': shot['views'], 'segments': relevant,
                   'parameterFits': {segment['id']: [entry for entry in fits_for(segment['id'])
                                      if entry.get('shotId') == shot_id] for segment in relevant},
                   'crank': local_keys, 'manualCameras': manual_cameras, 'width': width,
                   'render': render_code_hash, 'ready': ready, 'fitCode': code.hexdigest(),
                   'sources': [{'viewId': source['view']['viewId'],
                                'inputHash': source['index']['inputHash'],
                                'motionInputHash': source['motion'].get('motionInputHash'),
                                'motion': source['motion']} for source in sources]}
        stamp = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        checkpoint = video_root/'fit-checkpoints'/f'final-{shot_id}.json'
        saved = None
        if not force and checkpoint.is_file():
            cached = json.loads(checkpoint.read_text())
            if cached.get('fingerprint') == stamp and all(Path(path).is_file() for path in cached['contactSheets']):
                saved = cached
        if saved is None:
            final_shot = deepcopy(runtime_shot)
            exported_views = {view['viewId']: view for view in runtime_shot['views']}
            final_shot['views'] = []
            frames, sheets = [], []
            for source in sources:
                view = source['view']
                view_id = view['viewId']
                samples = source['samples']
                exported = deepcopy(exported_views[view_id])
                raw_keys = {key['t']: deepcopy(key) for key in exported['cameraKeys']}
                fixed = [key for key in manual_cameras if key['viewId'] == view_id]
                for key in fixed:
                    raw_keys[key['t']] = {'t': key['t'], 'camera': deepcopy(key['camera'])}
                exported['cameraKeys'] = [raw_keys[t] for t in sorted(raw_keys)]
                cameras = [{**key, 'camera': scale_camera(key['camera'], tuple(view['rectSourcePixels'][2:]),
                            (samples[0]['width'], samples[0]['height']))} for key in exported['cameraKeys']]
                worst, view_frames = [], []
                for offset in range(0, len(samples), 64):
                    batch = samples[offset:offset+64]
                    for sample in batch:
                        segment = segment_at(sample['index'])
                        sample['camera'] = interpolate_camera(cameras, sample['t'])
                        sample['input'] = deepcopy(segment['input'])
                        sample['input']['crankTurns'] = interpolate_turns(local_keys, sample['t'])
                    try:
                        arrays = client.render_batch([p.request(sample) for sample in batch],
                                                     shot_id=shot_id, view_id=view_id)
                    except Exception as exc:
                        message = str(exc)
                        physical_errors = (
                            'Magnifier hook has left the installed upper hub-tangent branch',
                            'Pen wire has exhausted its hanging run; reset the physical output fixture before using this clamp setting',
                        )
                        classification = 'setup-suspect' if any(
                            f'RangeError: {reason}' in message for reason in physical_errors
                        ) else 'execution-error'
                        p.write_json(video_root/'fit-checkpoints'/f'{classification}-final-{shot_id}.json', {
                            'classification': classification, 'shotId': shot_id, 'viewId': view_id,
                            'samples': [{'index': sample['index'], 'segmentId': segment_at(sample['index'])['id'],
                                         'input': sample['input']} for sample in batch],
                            'exceptionType': type(exc).__name__, 'exception': str(exc)})
                        raise
                    if len(arrays) != len(batch):
                        raise ValueError(f'Incomplete final native batch: {shot_id}/{view_id}')
                    for sample, ids in zip(batch, arrays):
                        segment = segment_at(sample['index'])
                        previous = next((key for key in reversed(local_keys) if key['t'] <= sample['t']), None)
                        exact = next((key for key in local_keys if key['t'] == sample['t']), None)
                        independent = view_id != runtime_shot['driverViewId']
                        scope = 'independent-take, not validated' if independent else 'driver'
                        support = crank_support(ids, sample, group_ids)
                        origin = (exact or previous or local_keys[0]).get('source', 'inferred')
                        if origin == 'manual':
                            origin = 'held'
                        elif origin == 'tracked' and not support['eligible']:
                            origin = 'inferred'
                        row = {'shotId': shot_id, 'viewId': view_id, 'index': sample['index'], 't': sample['t'],
                               'segmentId': segment['id'], 'turns': sample['input']['crankTurns'],
                               'crankSource': origin, 'crankSupport': support,
                               'cameraSource': 'manual' if fixed else 'fitted', 'validationScope': scope,
                               **p.validate_frame(ids, sample, group_ids)}
                        for name, metrics in row['groups'].items():
                            fitted_here = any(entry.get('shotId') == shot_id and entry.get('viewId') == view_id
                                              and entry.get('index') == sample['index'] and name in entry.get('groups', [])
                                              for entry in fits_for(segment['id']))
                            metrics['heldOut'] = not fitted_here
                            metrics['validationScope'] = 'fit-frame, not held-out' if fitted_here else scope
                        frames.append(row)
                        view_frames.append(row)
                        directions = [row.get('sourceToRenderChamferPx'), row.get('renderToSourceChamferPx')]
                        max_directed = max(directions) if all(
                            value is not None and np.isfinite(value) for value in directions
                        ) else float('inf')
                        iou_rank = row['iou'] if row['iou'] is not None and np.isfinite(row['iou']) else -1.
                        worst.append(((iou_rank, -max_directed), row, sample, ids.copy()))
                        worst.sort(key=lambda item: item[0])
                        del worst[4:]
                errors = [row['chamferPx'] for row in view_frames
                          if row['chamferPx'] is not None and np.isfinite(row['chamferPx'])]
                supported = bool(view_frames) and len(view_frames) == len(samples) and all(
                    row['iou'] is not None and np.isfinite(row['iou']) and row['iou'] >= .5
                    and all(row.get(field) is not None and np.isfinite(row[field]) and row[field] <= 960
                            for field in ('sourceToRenderChamferPx', 'renderToSourceChamferPx'))
                    for row in view_frames)
                exported['quality'] = {'medianPx': float(np.median(errors)) if errors else None,
                    'p90Px': float(np.percentile(errors, 90)) if errors else None,
                    'maxPx': float(max(errors)) if errors else None,
                    'status': 'manual' if fixed else ('fitted' if supported else 'unfitted')}
                final_shot['views'].append(exported)
                panels = [{'source': p.source_frame(source, row['index'], fps), 'ids': ids,
                           'title': f'{shot_id}/{view_id} t={sample["t"]:.3f}s T={sample["input"]["crankTurns"]:.3f}',
                           'errorPx': row['chamferPx'], 'iou': row['iou'],
                           'sourceToRenderChamferPx': row.get('sourceToRenderChamferPx'),
                           'renderToSourceChamferPx': row.get('renderToSourceChamferPx')}
                          for _, row, sample, ids in worst]
                path = video_root/'report'/'contact-sheets'/f'{shot_id}--{view_id}.png'
                if panels:
                    p.save_contact_sheet(path, panels, group_ids)
                    sheets.append(str(path))
            saved = {'fingerprint': stamp, 'shot': final_shot, 'frames': frames, 'contactSheets': sheets,
                     'seconds': time.perf_counter()-shot_started, 'infeasibleCandidates': {}}
            p.write_json(checkpoint, saved)
        seconds = time.perf_counter()-shot_started
        result['shots'].append(saved['shot'])
        result['frames'].extend(saved['frames'])
        result['contactSheets'].extend(saved['contactSheets'])
        result['candidateInfeasibility'].append({'shotId': shot_id, 'reasons': saved['infeasibleCandidates']})
        result['shotTiming'].append({'shotId': shot_id, 'seconds': seconds, 'validationSeconds': saved['seconds']})
        p.log(root, 'validation-shot-complete', videoId=video_id, shotId=shot_id,
              frames=len(saved['frames']), seconds=seconds)
    result['seconds'] = time.perf_counter()-started
    return result
