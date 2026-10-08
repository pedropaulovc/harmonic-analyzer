"""View-scoped pixel consumers; synthetic geometry is not source fidelity evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fitter = load_script('fit-source.py', 'view_consumer_fitter')
observer = load_script('observe-source.py', 'view_consumer_observer')


def fixture(scope):
    xyz = np.array([
        [-0.5, -0.4, 0], [0.5, -0.4, 0.2], [-0.5, 0.4, 0.1],
        [0.5, 0.4, -0.1], [-0.2, 0.1, 0.4], [0.3, -0.2, -0.3],
        [-0.1, -0.3, 0.3], [0.2, 0.3, 0.2],
    ])
    pixels, _ = fitter.project(np.array([0, 0, 0, 0, 0, 4, np.log(900)]), xyz, 1920, 1080)
    landmarks = [
        {'anchorId': str(index), 'role': 'fit' if index < 6 else 'check',
         'pixel': pixel.tolist(), 'status': 'observed', 'method': 'image-edge',
         'uncertaintyPx': 0.5, **({} if scope == 'missing' else {'viewId': scope})}
        for index, pixel in enumerate(pixels)
    ]
    views = [
        {'id': view_id, 'rectSourcePixels': [0, 0, 1920, 1080],
         'presentation': 'native', 'camera': None, 'input': None,
         'mechanicalState': {'status': 'unobservable', 'input': None},
         'cameraProvenance': {'kind': 'source-fit', 'evidence': 'Synthetic geometry control'}}
        for view_id in ('main', 'other')
    ]
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    source_image = {'frameIndex': 0, 'pixelFormat': 'bgr8', 'width': 1920, 'height': 1080,
                    'sourceSha256': 's', 'sha256Bgr8': hashlib.sha256(image.tobytes()).hexdigest()}
    data = {
        'schemaVersion': 1, 'kind': 'current-source-observations',
        'source': {'videoId': 'fixture', 'sha256': 's', 'width': 1920, 'height': 1080, 'durationSeconds': 1},
        'model': {'sha256': 'm'},
        'anchors': [{'id': str(index), 'partPath': 'part', 'partLocalMetres': point.tolist(),
                     'correspondenceEvidence': 'Synthetic geometry control'} for index, point in enumerate(xyz)],
        'shots': [{'id': 'shot', 'startSeconds': 0, 'endSeconds': 1, 'classification': 'machine'}],
        'frames': [{'timeSeconds': 0, 'decodedTimeSeconds': 0, 'decodedFrameIndex': 0,
                    'sourceImage': source_image, 'shotId': 'shot', 'classification': 'machine',
                    'landmarks': landmarks, 'views': views, 'unavailable': [],
                    'mechanicalState': {'status': 'unobservable', 'input': None}}],
        'coverage': {'status': 'blocked', 'blockers': []},
    }
    inventory = {'sha256': 'm', 'inventory': [{'path': 'part', 'world': np.eye(4).ravel(order='F').tolist()}]}
    return data, inventory, image


class PixelCapture:
    def __init__(self, image):
        self.image = image

    def set(self, *_args):
        pass

    def read(self):
        return True, self.image.copy()


class ConsumerOnlyContract:
    """Isolate numeric/availability behavior from unrelated live native authority."""
    def validate_observations(self, *_args, **_kwargs):
        pass


class SourceViewConsumerTests(unittest.TestCase):
    def test_runtime_optional_view_scope_boundary_preserves_raw_records(self):
        # Actual sealed records retain every native/source guard; only private scope
        # mutations exercise optional IDs. No synthetic record is fidelity evidence.
        subprocess.run(["node", "--input-type=module", "-e", r"""
import assert from 'node:assert/strict'
import {loadCurrentObservations, validateCurrentObservations, WEB_ROOT} from './scripts/fresh-source-observations.mjs'
import {VIDEO_IDS} from './scripts/verify-reference.mjs'
const original = await loadCurrentObservations(WEB_ROOT, VIDEO_IDS[0])
const scope = original.frames.find(frame => frame.landmarks.length).landmarks[0].viewId
for (const frame of original.frames) {
  for (const view of frame.views) if (view.id === scope) view.id = 'main'
  for (const point of frame.landmarks) if (point.viewId === scope) point.viewId = 'main'
}
for (const absent of [false, true]) {
  const data = structuredClone(original)
  if (absent) for (const frame of data.frames) for (const point of frame.landmarks) {
    if (point.viewId === 'main') delete point.viewId
  }
  const frame = data.frames.find(frame => frame.views.length)
  for (const owner of [frame, frame.views[0]]) {
    owner.unavailable = [...(owner.unavailable ?? []),
      {reason:'Private absent-scope boundary control'},
      {reason:'Private explicit-scope boundary control', viewId:'main'},
      {reason:'Private other-scope boundary control', viewId:scope},
      {reason:'Schema permits empty unavailable scope', viewId:''}]
  }
  const raw = JSON.stringify(data)
  assert.equal(await validateCurrentObservations(data), data)
  assert.equal(JSON.stringify(data), raw, 'Validation rewrote authored associations')
}
for (const kind of ['landmark', 'frame-unavailable', 'view-unavailable']) {
  for (const value of kind === 'landmark' ? [null, 7, false, {}, [], '', ' '] : [null, 7, false, {}, []]) {
    const data = structuredClone(original)
    if (kind === 'landmark') {
      for (const frame of data.frames) for (const point of frame.landmarks) {
        if (point.viewId === 'main') point.viewId = value
      }
    } else {
      const frame = data.frames.find(frame => frame.views.length)
      const owner = kind === 'frame-unavailable' ? frame : frame.views[0]
      owner.unavailable = [...(owner.unavailable ?? []),
        {reason:'Private invalid-scope boundary control', viewId:value}]
    }
    const raw = JSON.stringify(data)
    await assert.rejects(validateCurrentObservations(data), /viewId|source landmark/,
      `${kind} accepted invalid viewId ${JSON.stringify(value)}`)
    assert.equal(JSON.stringify(data), raw, 'Rejected input was rewritten')
  }
}
"""], cwd=HERE.parent, check=True)

    def test_actual_numeric_fit_scopes_pixels_without_rewriting_measurements(self):
        for scope, target in [('missing', 'main'), ('main', 'main'), ('other', 'other')]:
            with self.subTest(scope=scope):
                data, inventory, _ = fixture(scope)
                original = copy.deepcopy(data)
                fitted, report = fitter._run_computation(data, inventory)
                self.assertEqual([row['viewId'] for row in report['fits']], [target])
                solved = report['fits'][0]
                self.assertEqual(solved['status'], 'passed')
                self.assertLess(solved['heldOutMaxPx'], 1e-3)
                self.assertEqual({row['anchorId'] for row in solved['checkErrors']}, {'6', '7'})
                other = 'other' if target == 'main' else 'main'
                self.assertEqual([row['viewId'] for row in report['missingCameraEvidence']], [other])
                self.assertEqual(fitted['frames'][0]['landmarks'], original['frames'][0]['landmarks'])
                self.assertEqual(data, original)

    def test_observed_anchor_available_only_in_its_contract_view(self):
        for scope, target in [('missing', 'main'), ('main', 'main'), ('other', 'other')]:
            with self.subTest(scope=scope):
                data, inventory, image = fixture(scope)
                original = copy.deepcopy(data)
                result = observer._observe_current(data, PixelCapture(image), [0], inventory,
                                                   ConsumerOnlyContract(), False)
                missing = {(row['viewId'], row['anchorId']) for row in result['frames'][0]['unavailable']
                           if 'anchorId' in row}
                other = 'other' if target == 'main' else 'main'
                self.assertEqual(missing, {(other, str(index)) for index in range(8)})
                self.assertEqual(result['frames'][0]['landmarks'], original['frames'][0]['landmarks'])
                self.assertEqual(data, original)

    def test_native_clock_retains_rational_cut_boundary(self):
        cut = 25045 * 1001 / 24000
        probe = {'streams': [{'time_base': '1/24000'}],
                 'frames': [{'best_effort_timestamp': index * 1001} for index in (25044, 25045)]}
        result = SimpleNamespace(returncode=0, stdout=json.dumps(probe))
        with patch.object(observer.subprocess, 'run', return_value=result) as run:
            pts = observer.source_clock(Path('/private/original.mp4'))
        self.assertEqual(pts[-1], cut)
        self.assertEqual(observer.bisect_left(pts, cut), 1)
        self.assertIn('stream=time_base:frame=best_effort_timestamp', run.call_args.args[0])
        self.assertNotEqual(float(f'{cut:.6f}'), cut)

    def test_current_gray_identity_and_measurements_use_native_raster(self):
        data, inventory, bgr = fixture('main')
        gray = np.full(bgr.shape[:2], 73, dtype=np.uint8)
        cap = PixelCapture(bgr)
        cap.gray = lambda index: gray.copy()
        image = data['frames'][0]['sourceImage']
        image['pixelFormat'] = 'gray8'
        del image['sha256Bgr8']
        image['sha256Gray8'] = hashlib.sha256(gray.tobytes()).hexdigest()
        original = copy.deepcopy(data)
        result = observer._observe_current(data, cap, [0], inventory, ConsumerOnlyContract(), False)
        self.assertEqual(result['frames'][0]['sourceImage'], image)
        self.assertEqual(data, original)
        np.testing.assert_array_equal(observer.tracking_gray(cap, bgr, 0, data['frames'][0]), gray)
        for mutation in ('hash', 'pts', 'index', 'format'):
            broken = copy.deepcopy(data)
            frame = broken['frames'][0]
            if mutation == 'hash':
                frame['sourceImage']['sha256Gray8'] = '0' * 64
            elif mutation == 'pts':
                frame['decodedTimeSeconds'] = .01
            elif mutation == 'index':
                frame['decodedFrameIndex'] = 1
            else:
                frame['sourceImage']['pixelFormat'] = 'rgb8'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                observer._observe_current(broken, cap, [0], inventory, ConsumerOnlyContract(), False)

    def test_native_gray_protocol_checks_pts_range_and_removes_stride(self):
        # Native limited-range Y plus decoder row padding. This is a deterministic
        # consumer regression, not a claim of source/native geometry certification.
        def capture(*, time=0, pixel_format='yuv420p', color_range=1):
            plane = np.array([16, 17, 235, 255, 99, 99, 99, 99], dtype=np.uint8)
            plane = memoryview(plane)
            class Plane(bytearray):
                line_size = 8
            frame = SimpleNamespace(
                pts=time, time_base=1, width=4, height=1,
                format=SimpleNamespace(name=pixel_format), color_range=color_range,
                planes=[Plane(plane)],
            )
            cap = observer.CheckedCapture.__new__(observer.CheckedCapture)
            cap.pts = [0]
            cap.dimensions = (4, 1)
            cap.gray_container = object()
            cap.gray_frames = iter([frame])
            cap.gray_next_index = 0
            return cap
        np.testing.assert_array_equal(capture().gray(0), [[0, 1, 255, 255]])
        for kwargs in ({'time': .01}, {'pixel_format': 'rgb24'}, {'pixel_format': 'yuv422p'},
                       {'pixel_format': 'yuv444p'}, {'color_range': 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                capture(**kwargs).gray(0)

    def test_historical_unscoped_pixels_still_fit_the_implicit_none_view(self):
        data, inventory, _ = fixture('missing')
        data.pop('kind')
        data['frames'][0].pop('views')
        fitted, report = fitter._run_computation(data, inventory)
        self.assertEqual([row['viewId'] for row in report['fits']], [None])
        self.assertEqual(report['fits'][0]['status'], 'passed')
        self.assertLess(report['fits'][0]['heldOutMaxPx'], 1e-3)
        self.assertEqual(fitted['frames'][0]['landmarks'], data['frames'][0]['landmarks'])


if __name__ == '__main__':
    unittest.main()
