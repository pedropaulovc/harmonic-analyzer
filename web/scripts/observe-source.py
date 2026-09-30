#!/usr/bin/env python3
"""Sample actual local source frames and conservatively track manually identified features.

python web/scripts/observe-source.py --source /private/source.mp4
  --observations web/content/XPQwKRt4Y2k.observations.json --output /tmp/observed.json

Only numeric observations are written. Never copies source frames/video into the repo.
Content classification comes from the human-observed shot census, NOT guessed image labels.
Part-axis section centres are virtual geometric measurements: they are NOT optical-flow
features. Track only anchors explicitly classified as physical-feature. A failed track
ends permanently until a genuinely observed manual seed, with no extrapolation/recovery
from CAD projections. Forward/backward flow and source-patch correlation reject occlusion,
appearance discontinuity and drift. These checks are conservative, not semantic proof.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def patch(image, point):
    x, y = point
    if not 12 <= x < image.shape[1] - 12 or not 12 <= y < image.shape[0] - 12:
        return None
    value = cv2.getRectSubPix(image, (21, 21), (float(x), float(y))).astype(float)
    return value - value.mean()


def correlation(first, second):
    if first is None or second is None:
        return -1.0
    norm = float(np.linalg.norm(first) * np.linalg.norm(second))
    return float((first * second).sum() / norm) if norm > 1e-6 else -1.0


def track_direction(cap, seed_index, boundary_index, seed, kinds, fps):
    direction = 1 if boundary_index > seed_index else -1
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, image = cap.read()
    if not ok:
        raise ValueError('Cannot decode manually observed seed frame')
    previous = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    active = {(item.get('viewId'), item['anchorId']): copy.deepcopy(item) for item in seed['landmarks'] if kinds[item['anchorId']] == 'physical-feature' and item['method'] == 'manual'}
    seed_views = {view['id']: view['rectSourcePixels'] for view in seed.get('views', [])}
    original_patches = {key: patch(previous, item['pixel']) for key, item in active.items()}
    observed, failures = {}, []
    # Seek backward only when necessary; forward decoding stays sequential.
    for index in range(seed_index + direction, boundary_index + direction, direction):
        if not active:
            break
        if direction < 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            for key in active:
                failures.append({'anchorId': key[1], 'viewId': key[0], 'timeSeconds': index / fps, 'reason': 'source decode failed', 'direction': direction})
            break
        current = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        keys = list(active)
        old = np.array([active[key]['pixel'] for key in keys], dtype=np.float32).reshape(-1, 1, 2)
        new, forward_status, _ = cv2.calcOpticalFlowPyrLK(previous, current, old, None, winSize=(25, 25), maxLevel=3)
        if new is None:
            for key in keys:
                failures.append({'anchorId': key[1], 'viewId': key[0], 'timeSeconds': index / fps, 'reason': 'optical flow failed', 'direction': direction})
            break
        reverse, reverse_status, _ = cv2.calcOpticalFlowPyrLK(current, previous, new, None, winSize=(25, 25), maxLevel=3)
        for offset, key in enumerate(keys):
            candidate = new[offset, 0]
            backward_error = float(np.linalg.norm(reverse[offset, 0] - old[offset, 0])) if reverse is not None else math.inf
            similarity = correlation(original_patches[key], patch(current, candidate))
            local_similarity = correlation(patch(previous, old[offset, 0]), patch(current, candidate))
            valid = bool(forward_status[offset, 0]) and reverse_status is not None and bool(reverse_status[offset, 0])
            reason = None
            if not valid:
                reason = 'flow lost visible source feature'
            elif backward_error > 1.0:
                reason = f'forward/backward inconsistency {backward_error:.3f}px (occlusion/discontinuity)'
            elif similarity < .80 or local_similarity < .90:
                reason = f'source appearance changed: seed correlation {similarity:.3f}, adjacent {local_similarity:.3f}'
            if reason is None and key[0] in seed_views:
                x, y, width, height = seed_views[key[0]]
                if not x <= candidate[0] < x + width or not y <= candidate[1] < y + height:
                    reason = 'source feature left its independently identified source viewport'
            if reason:
                failures.append({'anchorId': key[1], 'viewId': key[0], 'timeSeconds': index / fps, 'reason': reason, 'direction': direction})
                del active[key]
                continue
            item = active[key]
            item['pixel'] = [float(candidate[0]), float(candidate[1])]
            item['method'] = 'optical-flow'
            item['uncertaintyPx'] = max(item['uncertaintyPx'], backward_error)
            item['trackingEvidence'] = {'seedTimeSeconds': seed['timeSeconds'], 'forwardBackwardErrorPx': backward_error, 'seedPatchCorrelation': similarity, 'adjacentPatchCorrelation': local_similarity}
        observed[index] = [copy.deepcopy(item) for item in active.values()]
        previous = current
    return observed, failures


def repeated_source_views(cap, seed, shot, shots, fps, frame_count):
    """Reacquire ONLY an actually repeated source view, using source images, not CAD.

    This does not interpolate through an occlusion. A new view must independently
    match the manual source image and EACH landmark's source patch. The manual
    section centre retains its geometric meaning only for this identical view.
    """
    seed_index = round(seed['decodedTimeSeconds'] * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, image = cap.read()
    if not ok:
        raise ValueError('Cannot decode repeated-view manual seed')
    grey_seed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(grey_seed > 20)
    if not len(xs):
        return {}, []
    # Source-derived crop excludes unrelated overlay/credit regions.
    left, right = max(0, int(xs.min()) - 2), min(image.shape[1], int(xs.max()) + 3)
    top, bottom = max(0, int(ys.min()) - 2), min(image.shape[0], int(ys.max()) + 3)
    reference = cv2.resize(grey_seed[top:bottom, left:right], (160, 240)).astype(float)
    reference -= reference.mean()
    seeds = [item for item in seed['landmarks'] if item['method'] == 'manual']
    patterns = {(item.get('viewId'), item['anchorId']): cv2.getRectSubPix(grey_seed, (21, 21), tuple(map(float, item['pixel']))) for item in seeds}
    result, evidence = {}, []
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for index in range(frame_count):
        ok, image = cap.read()
        if not ok:
            break
        time = index / fps
        current_shot = next((item for item in shots if item['startSeconds'] <= time < item['endSeconds']), None)
        if current_shot is None or current_shot['classification'] != 'machine' or current_shot.get('continuityGroup', current_shot['id']) != shot.get('continuityGroup', shot['id']):
            continue
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(grey[top:bottom, left:right], (160, 240)).astype(float)
        small -= small.mean()
        whole_correlation = correlation(reference, small)
        if whole_correlation < .998:
            continue
        landmarks = []
        for original in seeds:
            px, py = map(float, original['pixel'])
            x0, y0 = round(px) - 14, round(py) - 14
            if x0 < 0 or y0 < 0 or x0 + 29 > grey.shape[1] or y0 + 29 > grey.shape[0]:
                break
            score = cv2.matchTemplate(grey[y0:y0 + 29, x0:x0 + 29], patterns[(original.get('viewId'), original['anchorId'])], cv2.TM_CCOEFF_NORMED)
            _, maximum, _, location = cv2.minMaxLoc(score)
            if maximum < .97:
                break
            item = copy.deepcopy(original)
            item['pixel'] = [float(x0 + location[0] + 10), float(y0 + location[1] + 10)]
            item['method'] = 'template-match'
            item['trackingEvidence'] = {'seedTimeSeconds': seed['timeSeconds'], 'wholeSourceViewCorrelation': whole_correlation, 'sourcePatchCorrelation': maximum, 'reacquiredFromActualPixels': True}
            landmarks.append(item)
        if len(landmarks) != len(seeds):
            continue
        result[index] = landmarks
        evidence.append({'decodedTimeSeconds': time, 'frameIndex': index, 'sourceViewCorrelation': whole_correlation})
    return result, evidence


def needs_machine(classification, shot):
    """Same rule as fit-source.py needs_machine and verify-reference.mjs sourceNeedsMachine."""
    if classification == 'machine':
        return True
    if classification == 'non-machine':
        return shot.get('hasCorrespondingMachine') is True
    return shot.get('hasCorrespondingMachine') is not False


def observe(data, source_path, match_repeated_view=False):
    if digest(source_path) != data['source']['sha256']:
        raise ValueError('Private source hash does not match observation provenance')
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise ValueError('Cannot open actual source')
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (width, height) != (data['source']['width'], data['source']['height']):
        raise ValueError('Source frame size differs from manual observations')
    output = copy.deepcopy(data)
    kinds = {anchor['id']: anchor.get('kind', 'section-center') for anchor in data['anchors']}
    shots = {shot['id']: shot for shot in data['shots']}
    manual_seeds = [frame for frame in data['frames'] if any(item['method'] == 'manual' for item in frame['landmarks'])]
    tracked, failures = {}, []
    for seed in manual_seeds:
        shot = shots[seed['shotId']]
        seed_index = round(seed['decodedTimeSeconds'] * fps)
        for boundary in (math.ceil(shot['startSeconds'] * fps), min(frame_count - 1, math.ceil(shot['endSeconds'] * fps) - 1)):
            if boundary == seed_index:
                continue
            observations, stopped = track_direction(cap, seed_index, boundary, seed, kinds, fps)
            for index, values in observations.items():
                existing = {(item.get('viewId'), item['anchorId']): item for item in tracked.get(index, [])}
                for item in values:
                    # Prefer the closer genuinely observed seed, never a model-projected point.
                    key = (item.get('viewId'), item['anchorId'])
                    old = existing.get(key)
                    if old is None or abs(index / fps - item['trackingEvidence']['seedTimeSeconds']) < abs(index / fps - old['trackingEvidence']['seedTimeSeconds']):
                        existing[key] = item
                tracked[index] = list(existing.values())
            failures.extend(stopped)
    repeated, repeated_evidence = {}, []
    if match_repeated_view:
        for seed in manual_seeds:
            if not seed.get('repeatSourceViewSeed', True):
                continue
            values, evidence = repeated_source_views(cap, seed, shots[seed['shotId']], data['shots'], fps, frame_count)
            repeated.update(values)
            repeated_evidence.extend(evidence)
        # These are new source-image measurements, NOT optical-flow continuation.
        tracked.update(repeated)
    # Full cadence PLUS every native-frame tracking observation, loss and content boundary.
    existing = {frame['timeSeconds']: frame for frame in output['frames']}
    wanted = set(range(math.ceil(data['source']['durationSeconds'])))
    wanted.update(shot['startSeconds'] for shot in data['shots'])
    wanted.update(index / fps for index, values in tracked.items() if values)
    wanted.update(item['timeSeconds'] for item in failures)
    wanted.update(existing)
    all_frames = []
    for t in sorted(wanted):
        if not 0 <= t < data['source']['durationSeconds']:
            continue
        index = min(frame_count - 1, round(t * fps))
        shot = next(shot for shot in data['shots'] if shot['startSeconds'] <= t < shot['endSeconds'])
        frame = existing.get(t)
        if frame is None:
            required = needs_machine(shot['classification'], shot)
            state = copy.deepcopy(shot.get('mechanicalState', {
                'status': 'unobservable' if required else 'not-applicable',
                'input': None,
                'evidence': 'No measured mechanical input for this required native source frame; it remains unavailable.' if required
                else 'Shot census declares no corresponding mechanism; no source pose is asserted.',
            }))
            frame = {'timeSeconds': t, 'decodedTimeSeconds': index / fps, 'shotId': shot['id'], 'classification': shot['classification'], 'landmarks': [], 'unavailable': [], 'camera': None, 'mechanicalState': state}
            seed_times = [item['trackingEvidence']['seedTimeSeconds'] for item in tracked.get(index, [])]
            if seed_times:
                seed = next(item for item in manual_seeds if item['timeSeconds'] == seed_times[0])
                if seed.get('views'):
                    frame['views'] = copy.deepcopy(seed['views'])
                    for view in frame['views']:
                        view['camera'] = None
                        view['mechanicalState'] = copy.deepcopy(state)
        if not frame['landmarks'] and frame['classification'] == 'machine':
            frame['landmarks'] = copy.deepcopy(tracked.get(index, []))
        observed_ids = {item['anchorId'] for item in frame['landmarks']}
        if frame['classification'] == 'machine':
            frame['unavailable'] = [{'anchorId': anchor['id'], 'reason': 'No verified measurement at this source frame; axis centres are not optical-flow features and physical tracks stop at occlusion/appearance failure.'} for anchor in data['anchors'] if anchor['id'] not in observed_ids]
        frame['camera'] = None
        all_frames.append(frame)
    # Hash real decoded BGR bytes, not a re-encoded PNG or a rendered model.
    measured_indices = sorted({round(frame['decodedTimeSeconds'] * fps) for frame in all_frames if frame['landmarks']})
    source_images = {}
    for index in measured_indices:
        if round(cap.get(cv2.CAP_PROP_POS_FRAMES)) != index:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            raise ValueError(f'Cannot reproduce source observation frame {index}')
        source_images[index] = {
            'frameIndex': index, 'sha256Bgr8': hashlib.sha256(image.tobytes()).hexdigest(),
            'pixelFormat': 'bgr8', 'width': width, 'height': height,
            'sourceSha256': data['source']['sha256'],
        }
    for frame in all_frames:
        if frame['landmarks']:
            frame['sourceImage'] = source_images[round(frame['decodedTimeSeconds'] * fps)]
    cap.release()
    output['frames'] = all_frames
    output['tracking'] = {'method': 'native-frame pyramidal Lucas-Kanade, forward/backward <=1px, seed NCC>=0.80, adjacent NCC>=0.90; no CAD-generated pixels', 'failures': failures, 'observedNativeFrameCount': sum(bool(values) for values in tracked.values()), 'autoReacquisition': False}
    output['sourceViewReacquisition'] = {'enabled': match_repeated_view, 'method': 'actual-source whole-view NCC>=0.998 plus EACH independently located 21px landmark template NCC>=0.97; no temporal/camera extrapolation or CAD-generated pixels', 'acceptedNativeFrames': repeated_evidence}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--match-repeated-view', action='store_true', help='Independently measure only actual source images matching a manual seed view')
    args = parser.parse_args()
    output = observe(json.loads(args.observations.read_text()), args.source, args.match_repeated_view)
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'videoId': output['source']['videoId'], 'sampleCount': len(output['frames']), 'framesWithSourcePixels': sum(bool(frame['landmarks']) for frame in output['frames']), 'tracking': output['tracking'], 'coverage': output['coverage']}, indent=2))


if __name__ == '__main__':
    main()
