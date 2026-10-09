"""Discover segment parameters only at chronological source/native observations."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from .camera import interpolate_camera, scale_camera
from .crank import fit_bank_offset, interpolate_turns
from .setup import affected_groups, default_input, fit_setup


_BANK = 'setup.driveCrankOffsetTurns'


def _visibility_groups(path, group_ids):
    if path.startswith('amplitudes.'):
        names = ['amplitude-bars']
    elif path.startswith('phases.'):
        names = [f'channel-{20-int(path.split(".")[1])}']
    elif path in ('gearing', 'setup.platenOffsetM'):
        names = ['platen-paper']
    elif path in ('magnification', 'setup.wireFixtureOffsetM'):
        names = ['magnifier', 'wheel-wire', 'pen']
    elif path in ('setup.coneSwingRad', 'setup.pinionCamRad'):
        names = ['cones']
    elif path == 'setup.counterHeightM':
        names = ['springs', 'summing']
    elif path in (_BANK, 'setup.heldChannelTurns'):
        names = [name for name in group_ids if name.startswith('channel-')]
    else:
        names = []
    return [group_ids[name] for name in names if name in group_ids]


def _visible(ids, sample, selected, minimum=8):
    projected = np.isin(ids, selected)
    if np.count_nonzero(projected & sample['mask']) < minimum:
        return False
    support = cv2.dilate(projected.astype(np.uint8), np.ones((13, 13), np.uint8)) > 0
    return (np.count_nonzero(sample['edges'] & support) >= 25
            and np.count_nonzero(sample['mask'] & support) >= 50)


def _window_keys(keys, start, end):
    """Include boundary interpolation anchors without unrelated timeline keys."""
    ordered = sorted(keys, key=lambda key: key['t'])
    inside = [key for key in ordered if start <= key['t'] < end]
    before = [key for key in ordered if key['t'] < start]
    after = [key for key in ordered if key['t'] >= end]
    return ([before[-1]] if before else []) + inside + (after[:1] if after else [])


def discover_setups(client, ready, census, root, runtime_shots, segments, manual,
                    width, crank_keys, *, render_code_hash='', force: bool = False):
    """Return frozen runtime segments and private, per-parameter fit evidence."""
    from . import pipeline as p

    root = Path(root)
    video_id = census['videoId']
    video_root = root / video_id
    fps = Fraction(*census['fps'])
    group_ids = ready['groupIds']
    authored_shots = {shot['id']: shot for shot in census['shots']}
    shots = sorted(runtime_shots, key=lambda shot: shot['startFrame'])
    manual_segments = {segment['id']: segment for segment in manual.get('segments', [])}
    checkpoint = video_root / 'fit-checkpoints' / 'observable-setups.json'
    cached = json.loads(checkpoint.read_text()) if checkpoint.is_file() else {}
    code = hashlib.sha256()
    for name in ('first_visible.py', 'setup.py', 'crank.py', 'camera.py', 'pipeline.py'):
        code.update((Path(__file__).parent / name).read_bytes())
    model_hash = census.get('modelSha256') or p.sha256(
        p.PROJECT.parent / 'public' / 'models' / 'ha-harmonic-analyzer.glb')
    runtime_segments, segment_evidence = {}, {}
    carried = default_input(video_id)
    sources = {}

    for segment in sorted(segments, key=lambda entry: entry['start']):
        started = time.perf_counter()
        segment_id = segment['id']
        p.log(root, 'setup-segment-start', videoId=video_id, segmentId=segment_id)
        start, end = round(segment['start'] * fps), round(segment['end'] * fps)
        relevant = [shot for shot in shots
                    if shot['startFrame'] < end and shot['endFrame'] > start]
        source_stamps, camera_stamps = [], []
        for shot in relevant:
            authored = authored_shots[shot['id']]
            for view in authored['views']:
                folder = video_root / shot['id'] / view['viewId']
                index = json.loads((folder / 'index.json').read_text())
                motion = json.loads((folder / 'motion.json').read_text())
                source_stamps.append({'shotId': shot['id'], 'view': view,
                                      'inputHash': index['inputHash'],
                                      'motionInputHash': motion.get('motionInputHash')})
            camera_stamps.append({'id': shot['id'], 'classification': authored['classification'],
                                 'startFrame': shot['startFrame'], 'endFrame': shot['endFrame'],
                                 'driverViewId': shot.get('driverViewId'),
                                 'views': [{'viewId': view['viewId'], 'cameraKeys':
                                            _window_keys(view['cameraKeys'], segment['start'], segment['end'])}
                                           for view in shot['views']]})
        payload = {'segment': segment, 'manual': manual_segments.get(segment_id),
                   'carried': carried, 'native': ready, 'model': model_hash,
                   'renderCode': render_code_hash, 'fitCode': code.hexdigest(),
                   'width': width, 'sources': source_stamps, 'cameras': camera_stamps,
                   'crank': _window_keys(crank_keys, segment['start'], segment['end'])}
        stamp = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        saved = cached.get(segment_id)
        if not force and saved and saved.get('fingerprint') == stamp:
            runtime = deepcopy(saved['runtime'])
            evidence = deepcopy(saved['evidence'])
            resumed = True
        else:
            resumed = False
            state = p.merge_input(carried, segment.get('init', {}))
            is_manual = segment_id in manual_segments
            if is_manual:
                state = p.merge_input(state, manual_segments[segment_id].get('init', {}))
            seed = {'input': state, 'turns': interpolate_turns(crank_keys, segment['start']),
                    't': segment['start']}
            # An empty search initializes complete provenance without probing geometry.
            runtime, initial = fit_setup(client, {**segment, 'init': {}, 'fit': [],
                                                 'provenance': {} if is_manual else segment.get('provenance', {})},
                                         [seed], group_ids=group_ids, manual=is_manual)
            pending = [] if is_manual else list(segment.get('fit', []))
            if not is_manual and _BANK not in pending:
                pending.append(_BANK)
            evidence = {'parameterFits': [], 'attempts': [], 'pending': [], 'setup': initial}
            terminal = {}
            for path in list(pending):
                if path == 'setup.meanLineAngleRad':
                    terminal[path] = 'readout-only datum has no native projection effect'
                elif path.startswith('setup.') and state['setup'][path.split('.')[1]] is None:
                    terminal[path] = 'auto-calibrated null setting, not a numeric measurement'
                if path in terminal:
                    pending.remove(path)
            if terminal:
                evidence['notIdentified'] = terminal

            def record_fit(paths, sample, bank=False):
                groups = ([name for name in group_ids if name != 'static'] if bank else
                          sorted({name for path in paths for name in affected_groups(path, group_ids)}))
                identity = {key: sample[key] for key in ('shotId', 'viewId', 'index', 't')}
                evidence['parameterFits'].append({'paths': paths, 'groups': groups, **identity})
                evidence.setdefault('fitFrame', identity)

            for shot in relevant:
                authored = authored_shots[shot['id']]
                if not pending or authored['classification'] != 'machine':
                    continue
                view_id = shot['driverViewId']
                source_key = (shot['id'], view_id)
                if source_key not in sources:
                    view = next(view for view in authored['views'] if view['viewId'] == view_id)
                    sources[source_key] = p.load_view(video_root, authored, view, census['sourceSha256'], width)
                source = sources[source_key]
                exported = next(view for view in shot['views'] if view['viewId'] == view_id)
                cameras = [{**key, 'camera': scale_camera(key['camera'],
                            tuple(source['view']['rectSourcePixels'][2:]),
                            (source['samples'][0]['width'], source['samples'][0]['height']))}
                           for key in exported['cameraKeys']]
                samples = [sample for sample in source['samples'] if start <= sample['index'] < end]
                attempted = set()
                cursor = 0
                while cursor < len(samples) and any(path not in attempted for path in pending):
                    batch = []
                    for raw in samples[cursor:cursor+64]:
                        sample = {**raw, 'shotId': shot['id'], 'viewId': view_id,
                                  'camera': interpolate_camera(cameras, raw['t']),
                                  'input': deepcopy(runtime['input']),
                                  'turns': interpolate_turns(crank_keys, raw['t'])}
                        sample['input']['crankTurns'] = sample['turns']
                        batch.append(sample)
                    try:
                        arrays = client.render_batch([p.request(sample) for sample in batch],
                                                     shot_id=shot['id'], view_id=view_id)
                    except Exception as exc:
                        message = str(exc)
                        physical_errors = (
                            'Magnifier hook has left the installed upper hub-tangent branch',
                            'Pen wire has exhausted its hanging run; reset the physical output fixture before using this clamp setting',
                        )
                        classification = ('setup-suspect' if any(
                            f'RangeError: {reason}' in message for reason in physical_errors)
                            else 'execution-error')
                        p.write_json(video_root / 'fit-checkpoints' /
                                     f'observable-{segment_id}-{shot["id"]}-failure.json', {
                            'classification': classification, 'segmentId': segment_id,
                            'shotId': shot['id'], 'viewId': view_id,
                            'samples': [{'index': sample['index'], 't': sample['t'],
                                         'input': sample['input']} for sample in batch],
                            'exceptionType': type(exc).__name__, 'exception': message})
                        raise
                    for sample, ids in zip(batch, arrays):
                        cursor += 1
                        visible = [path for path in pending if path not in attempted
                                   and _visible(ids, sample, _visibility_groups(path, group_ids),
                                                16 if path == _BANK else 8)]
                        if not visible:
                            continue
                        # Re-render the exact fitting frame after every earlier setup change;
                        # batch results are visibility hints, never fitting objectives.
                        sample['input'] = deepcopy(runtime['input'])
                        sample['input']['crankTurns'] = sample['turns']
                        ids = client.render(p.request(sample), shot_id=shot['id'], view_id=view_id)
                        visible = [path for path in visible if _visible(
                            ids, sample, _visibility_groups(path, group_ids), 16 if path == _BANK else 8)]
                        if not visible:
                            continue
                        attempt = {key: sample[key] for key in ('shotId', 'viewId', 'index', 't')}
                        bank_evidence = None
                        if _BANK in visible:
                            visible.remove(_BANK)
                            attempted.add(_BANK)
                            if sample['input']['setup']['coneSwingRad'] == 0:
                                _, bank_evidence = fit_bank_offset(client, sample, group_ids, sample['turns'])
                                evidence['bank'] = bank_evidence
                                attempt['bank'] = bank_evidence
                                if bank_evidence['provenance'] == 'bank-inferred':
                                    runtime['input']['setup']['driveCrankOffsetTurns'] = sample['input']['setup']['driveCrankOffsetTurns']
                                    runtime['provenance'][_BANK] = 'fitted'
                                    pending.remove(_BANK)
                                    record_fit([_BANK], sample, bank=True)
                            # Bank candidates may alter visibility of other pending fields.
                            ids = client.render(p.request(sample), shot_id=shot['id'], view_id=view_id)
                            visible = [path for path in pending if path not in attempted and _visible(
                                ids, sample, _visibility_groups(path, group_ids))]
                        attempted.update(visible)
                        partial = {**segment, 'init': {}, 'fit': visible,
                                   'provenance': runtime['provenance']}
                        runtime, setup_evidence = fit_setup(client, partial, [sample], group_ids=group_ids)
                        attempt['setup'] = setup_evidence
                        evidence['setup'] = setup_evidence
                        evidence['attempts'].append(attempt)
                        identified = setup_evidence['observable']
                        if identified:
                            record_fit(identified, sample)
                            pending = [path for path in pending if path not in identified]
                        # Discard all remaining stale batch hints, including newly revealed
                        # geometry, and restart at the very next chronological frame.
                        break
            evidence['pending'] = pending
            if not evidence['attempts']:
                evidence['notes'] = ('Manual segment: complete carried input is authoritative.' if is_manual else
                                     'No eligible native/source-visible driver observation; values remain chosen.')
            elif pending:
                evidence['notes'] = 'Unobserved or locally dependent parameters retain chosen values.'
            cached[segment_id] = {'fingerprint': stamp, 'runtime': runtime, 'evidence': evidence}
            p.write_json(checkpoint, cached)
        runtime_segments[segment_id] = runtime
        segment_evidence[segment_id] = evidence
        carried = p.merge_input(carried, runtime['input'])
        carried['crankTurns'] = 0.0
        p.log(root, 'setup-segment-complete', videoId=video_id, segmentId=segment_id,
              seconds=time.perf_counter()-started, resumed=resumed,
              pending=evidence['pending'], parameterFits=len(evidence['parameterFits']))
    return runtime_segments, segment_evidence
