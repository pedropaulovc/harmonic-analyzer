"""Consume atomically published source completion without a video-wide barrier."""

from collections.abc import Iterator
from copy import deepcopy
import json
from pathlib import Path
import sys
import time


_HASH_FIELDS = ('maskInputHash', 'edgeInputHash', 'motionInputHash', 'inputHash')


def _manifest(path: Path, census: dict, shots: dict) -> dict | None:
    try:
        manifest = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    if not isinstance(manifest, dict):
        raise ValueError(f'Malformed source readiness manifest: {path}')
    for field in ('videoId', 'sourceSha256'):
        if manifest.get(field) != census[field]:
            raise ValueError(f'Unexpected {field} in source readiness manifest: {path}')
    entries = manifest.get('shots')
    if not isinstance(entries, dict):
        raise ValueError(f'Malformed readiness shots: {path}')
    for shot_id, entry in entries.items():
        if shot_id not in shots:
            raise ValueError(f'Unknown readiness shot {shot_id}: {path}')
        if not isinstance(entry, dict) or not isinstance(entry.get('views'), dict):
            raise ValueError(f'Malformed readiness shot {shot_id}: {path}')
        view_ids = {view['viewId'] for view in shots[shot_id].get('views', [])}
        for view_id, hashes in entry['views'].items():
            if view_id not in view_ids:
                raise ValueError(f'Unknown readiness view {shot_id}/{view_id}: {path}')
            if not isinstance(hashes, dict) or any(
                not isinstance(hashes.get(field), str) or not hashes[field]
                for field in _HASH_FIELDS
            ):
                raise ValueError(f'Malformed readiness hashes {shot_id}/{view_id}: {path}')
    return entries


def _view_ready(folder: Path, census: dict, shot: dict, view: dict, hashes: dict) -> bool:
    try:
        index = json.loads((folder / 'index.json').read_text())
    except FileNotFoundError:
        return False
    if not isinstance(index, dict):
        raise ValueError(f'Malformed source index: {folder}')
    identity = {
        'videoId': census['videoId'], 'sourceSha256': census['sourceSha256'],
        'shotId': shot['id'], 'viewId': view['viewId'],
        'rectSourcePixels': view['rectSourcePixels'],
    }
    for field, expected in identity.items():
        if index.get(field) != expected:
            raise ValueError(f'Unexpected {field} in source index: {folder}')
    # Legacy indices and in-progress stages have no final four-stage marker.
    if any(index.get(field) != hashes[field] for field in _HASH_FIELDS):
        return False
    frames = index.get('frames')
    if not isinstance(frames, list) or not frames:
        return False
    for frame in frames:
        if not isinstance(frame, dict) or type(frame.get('index')) is not int:
            raise ValueError(f'Malformed source frame index: {folder}')
        for stage in ('masks', 'edges'):
            if not (folder / stage / f"{frame['index']}.png").is_file():
                return False
    return (folder / 'motion.json').is_file()


def ready_shots(census: dict, data_root: Path, *, poll_seconds: float = 2.) -> Iterator[dict]:
    """Yield each photographed shot once, in start order among available shots."""
    if poll_seconds < 0:
        raise ValueError('poll_seconds must be nonnegative')
    shots = {shot['id']: shot for shot in census['shots']}
    pending = {
        shot_id: shot for shot_id, shot in shots.items()
        if shot['classification'] in ('machine', 'transition') and shot.get('views')
    }
    root = data_root / census['videoId']
    last_waiting = None
    while pending:
        entries = _manifest(root / 'ready.json', census, shots)
        available = []
        if entries is not None:
            for shot_id, shot in pending.items():
                entry = entries.get(shot_id)
                if entry is None:
                    continue
                views = entry['views']
                if all(
                    view['viewId'] in views and _view_ready(
                        root / shot_id / view['viewId'], census, shot, view,
                        views[view['viewId']],
                    )
                    for view in shot['views']
                ):
                    available.append(shot)
        for shot in sorted(available, key=lambda item: (item['start'], item['id'])):
            del pending[shot['id']]
            result = dict(shot)
            result['_readyHashes'] = deepcopy(entries[shot['id']])
            yield result
        if not available and pending:
            waiting = frozenset(pending)
            if waiting != last_waiting:
                print(f"Waiting for source readiness: {len(pending)} shots ({census['videoId']})",
                      file=sys.stderr, flush=True)
                last_waiting = waiting
            time.sleep(poll_seconds)
