"""Handle phase tracking with one segment-local bank-cycle offset, never modulo pose."""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

import cv2
import numpy as np


def _edge_score(ids: np.ndarray, sample: dict, selected_ids: list[int]) -> float:
    mask = np.isin(ids, selected_ids)
    if np.count_nonzero(mask) < 8 or not sample['edges'].any():
        return 1e4
    # A union silhouette hides a pen moving over paper and adjacent rockers.
    # Retain the actual native group boundaries as well as the outer contour.
    selected = np.where(mask, ids, 0).astype(np.uint16)
    edges = cv2.morphologyEx(selected, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    if not edges.any():
        return 1e4
    dt = sample.get('edgeDistance')
    if dt is None:
        dt = cv2.distanceTransform((~sample['edges']).astype(np.uint8), cv2.DIST_L2, 3)
        sample['edgeDistance'] = dt
    scale = sample['sourceWidth']/sample['width']
    outside = 1 - np.count_nonzero(mask & sample['mask']) / np.count_nonzero(mask)
    return float(np.minimum(dt[edges], 96/scale).mean())*scale + 70*outside


def _requests(sample: dict, turns: list[float], groups: list[str] | None = None) -> list[dict]:
    requests = []
    for value in turns:
        mechanism = deepcopy(sample['input'])
        mechanism['crankTurns'] = value
        requests.append({'camera': sample['camera'], 'input': mechanism, 'width': sample['width'],
                         'height': sample['height'], 'presentation': sample['presentation'],
                         **({'groups': groups} if groups else {})})
    return requests


def fit_bank_offset(client: Any, sample: dict, group_ids: dict, turns: float) -> tuple[float, dict]:
    """Fit the handle's integer bank ambiguity without advancing crank/paper.

    Integer drive offset spans the actual eighty-turn bank period. Explicit
    native physical-infeasible candidates are rejected, never hidden in a final
    chosen render. The selected offset becomes the segment's frozen setup.
    """
    groups = [name for name in group_ids if name.startswith('channel-')]
    selected = [group_ids[name] for name in groups]
    fraction = sample['input']['setup']['driveCrankOffsetTurns'] % 1
    values = [fraction+j for j in range(80)]
    scored = []
    rejected = {}
    for offset in range(0, 80, 32):
        requests = _requests(sample, [turns]*len(values[offset:offset+32]))
        for request, value in zip(requests, values[offset:offset+32]):
            request['input']['setup']['driveCrankOffsetTurns'] = value
        renders = client.render_candidate_batch(requests)
        for reason, count in client.last_candidate_failures.items():
            rejected[reason] = rejected.get(reason, 0)+count
        scored.extend((_edge_score(ids, sample, selected), value, int(np.count_nonzero(np.isin(ids, selected))))
                      for ids, value in zip(renders, values[offset:offset+32]) if ids is not None)
    if not scored:
        # The original/final state remains strict. Do not fabricate a feasible
        # pose when the whole candidate domain is unavailable.
        client.render(_requests(sample, [turns])[0])
        raise ValueError('No feasible bank-offset candidates')
    best = min(scored)
    observed = best[0] < 1e4 and best[2] >= 8
    if observed:
        sample['input']['setup']['driveCrankOffsetTurns'] = float(best[1])
    return turns, {'driveCrankOffsetTurns': sample['input']['setup']['driveCrankOffsetTurns'],
                   'fixedCrankTurns': turns, 'loss': best[0], 'visibleBankPixels': best[2],
                   'provenance': 'bank-inferred' if observed else 'chosen', 'periodTurns': 80,
                   'infeasibleCandidates': rejected,
                   'alternatives': [{'driveCrankOffsetTurns': value, 'loss': loss} for loss, value, _ in sorted(scored)[:5]]}


def crank_support(ids: np.ndarray, sample: dict, group_ids: dict) -> dict:
    """Automatic, projection-conditioned crank support; not a source annotation."""
    mask = ids == group_ids['crank']
    visible = int(np.count_nonzero(mask))
    minimum = max(1, math.ceil(150*(sample['width']/480)**2))
    fraction = float(np.count_nonzero(mask & sample['mask'])/visible) if visible else 0.
    return {'visiblePixels': visible, 'minVisiblePixels': minimum,
            'sourceMaskFraction': fraction, 'eligible': visible >= minimum and fraction >= .5}


def fit_crank(client: Any, sample: dict, group_ids: dict, previous: float | None,
              *, grid_count: int = 9) -> tuple[float, str, dict]:
    centre = 0. if previous is None else previous
    values = np.linspace(centre-.5, centre+.5, grid_count).tolist()
    # Full poses retain real occlusion. Captions/reason text never qualify a
    # handle: each candidate needs sufficient projected physical-mask support.
    arrays = client.render_candidate_batch(_requests(sample, values))
    if not any(ids is not None for ids in arrays):
        client.render(_requests(sample, [centre])[0])
        raise ValueError('No feasible crank candidates')
    supports = [crank_support(ids, sample, group_ids) if ids is not None else None for ids in arrays]
    handle = any(support and support['eligible'] for support in supports)
    selected = [group_ids['crank']] if handle else [
        value for name, value in group_ids.items() if name != 'static']

    def score(ids, support):
        if ids is None:
            return math.inf
        if handle and not support['eligible']:
            return 1e4
        return _edge_score(ids, sample, selected)

    losses = np.array([score(ids, support) for ids, support in zip(arrays, supports)])
    j = int(np.argmin(losses))
    finite_losses = losses[np.isfinite(losses)]
    if losses[j] >= 1e4 or float(np.ptp(finite_losses)) < .1:
        middle = len(values)//2
        if arrays[middle] is None:
            arrays[middle] = client.render(_requests(sample, [centre])[0])
            supports[middle] = crank_support(arrays[middle], sample, group_ids)
        return float(centre), 'held', {'loss': float(losses[j]), 'phaseContrast': 0.,
                                     'crankSupport': supports[middle], 'phaseGroups': selected,
                                     'reason': 'Insufficient phase response'}
    # One quadratic sub-grid proposal stays within the +/-half-turn search band.
    value, support = values[j], supports[j]
    if 0 < j < len(values)-1 and np.isfinite(losses[j-1:j+2]).all():
        curvature = losses[j-1]-2*losses[j]+losses[j+1]
        if curvature > 1e-8:
            delta = .5*(losses[j-1]-losses[j+1])/curvature
            proposal = value+float(np.clip(delta, -.5, .5))*(values[1]-values[0])
            ids = client.render_candidate_batch(_requests(sample, [proposal]))[0]
            proposed_support = crank_support(ids, sample, group_ids) if ids is not None else None
            proposal_loss = score(ids, proposed_support)
            if proposal_loss < losses[j]:
                value, losses[j], support = proposal, proposal_loss, proposed_support
    contrast = float(np.median(finite_losses)-losses[j])
    source = 'tracked' if handle and support['eligible'] else 'inferred'
    return float(value), source, {'loss': float(losses[j]), 'phaseContrast': contrast,
                                'crankSupport': support, 'phaseGroups': selected}


def _isotonic(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    blocks: list[list[float]] = []
    for j, (value, weight) in enumerate(zip(values, weights)):
        blocks.append([float(j), float(j), float(value*weight), float(weight)])
        while len(blocks) > 1 and blocks[-2][2]/blocks[-2][3] > blocks[-1][2]/blocks[-1][3]:
            right = blocks.pop()
            left = blocks.pop()
            blocks.append([left[0], right[1], left[2]+right[2], left[3]+right[3]])
    result = np.empty(len(values))
    for start, end, total, weight in blocks:
        result[int(start):int(end)+1] = total/weight
    return result


def smooth_shot(keys: list[dict], fixed: dict[float, float] | None = None) -> tuple[list[dict], dict]:
    """Monotone least-squares projection, with authoritative manual anchors exact.

    Direction is observed from independently tracked handle samples or manual
    anchors. Inferred same-parts minima cannot establish a reversal; an otherwise
    unobserved direction uses a labelled chosen forward prior.
    """
    if not keys:
        return [], {'direction': 'unobserved', 'adjustmentMaxTurns': 0.}
    by_time = {key['t']: deepcopy(key) for key in keys}
    for t, turns in (fixed or {}).items():
        by_time[t] = {'t': t, 'turns': turns, 'source': 'held', 'manual': True}
    ordered = [by_time[t] for t in sorted(by_time)]
    values = np.array([key['turns'] for key in ordered])
    manual_indices = [j for j, key in enumerate(ordered) if key.get('manual')]
    weights = np.array([8. if key['source'] == 'tracked' else 1. for key in ordered])
    tracked = [key['turns'] for key in ordered if key['source'] == 'tracked']
    observed = np.diff(tracked)
    direction = -1. if len(observed) >= 3 and np.mean(observed < -.002) >= .75 else 1.
    direction_source = 'tracked-handle' if len(observed) >= 3 else 'chosen'
    result = values.copy()
    boundaries = sorted(set([0, len(ordered)-1, *manual_indices]))
    for a, b in zip(boundaries, boundaries[1:]):
        local_direction = direction
        if a in manual_indices and b in manual_indices and values[b] != values[a]:
            local_direction = float(np.sign(values[b]-values[a]))
        section = _isotonic(values[a:b+1]*local_direction, weights[a:b+1])*local_direction
        if a in manual_indices:
            section = np.maximum(section, values[a]) if local_direction > 0 else np.minimum(section, values[a])
        if b in manual_indices:
            section = np.minimum(section, values[b]) if local_direction > 0 else np.maximum(section, values[b])
        result[a:b+1] = section
    for j in manual_indices:
        result[j] = values[j]
    for key, value in zip(ordered, result):
        if key['source'] == 'tracked' and abs(value-key['turns']) > .005:
            key['source'] = 'inferred'
        key['turns'] = float(value)
    return ordered, {'direction': 'reverse' if direction < 0 else 'forward',
                     'adjustmentMaxTurns': float(np.max(np.abs(result-values))),
                     'directionProvenance': direction_source,
                     'manualReversalOnly': True}


def interpolate_turns(keys: list[dict], t: float) -> float:
    if not keys:
        return 0.
    return float(np.interp(t, [key['t'] for key in keys], [key['turns'] for key in keys]))


def decimate_crank(keys: list[dict], tolerance: float = .005, fixed_times: set[float] | None = None) -> list[dict]:
    if len(keys) < 3:
        return keys
    fixed = fixed_times or set()
    keep = {0, len(keys)-1} | {j for j, key in enumerate(keys) if key['t'] in fixed}
    # Keep provenance boundaries: interpolating an inferred span must not hide it.
    keep |= {j for j in range(1, len(keys)) if keys[j]['source'] != keys[j-1]['source']}
    keep |= {j-1 for j in range(1, len(keys)) if keys[j]['source'] != keys[j-1]['source']}
    def split(a: int, b: int) -> None:
        if b <= a+1:
            return
        errors = [(abs(keys[j]['turns']-interpolate_turns([keys[a], keys[b]], keys[j]['t'])), j) for j in range(a+1, b)]
        error, j = max(errors)
        if error > tolerance:
            keep.add(j)
            split(a, j)
            split(j, b)
    ordered = sorted(keep)
    for a, b in zip(ordered, ordered[1:]):
        split(a, b)
    return [{field: key[field] for field in ('t', 'turns', 'source')} for j, key in enumerate(keys) if j in keep]
