"""Consumer-visible source identity and presentation refusal boundaries."""
import copy
from contextlib import contextmanager, redirect_stdout
import importlib.util
import gzip
import hashlib
import io
import json
import math
import re
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_script(os.environ.get('SOURCE_COMMON_PATH', 'compact-source-common.py'),
                     'source_generation_common')
camera_tracks = load_script(os.environ.get('SOURCE_GENERATOR_PATH',
                                          'generate-analysis-synthesis-source-tracks.py'),
                            'source_generation_camera_tracks')
fresh_tracks = load_script('fresh-source-tracks.py', 'source_generation_fresh')
observe_source = load_script('observe-source.py', 'source_generation_observe')


HISTORICAL_SCENE_SHA256 = '7b28468cc3f36a2e4d3699e252c54df837770868481c83a486b572a32f6b3b8b'




def historical_synthesis_dependencies():
    """Exact old producer/math bytes, not a claim about today's source files."""
    packet = json.loads((HERE.parent / 'content/canonical-native/8KmVDxkia_w.automatic-motion.json').read_bytes())
    return {path: common.historical_code_bytes(path, record['sha256'])
            for path, record in packet['generationDependencies'].items()
            if not path.startswith('web/content/')}


def historical_synthesis_generator():
    # The real constructor always reads the original sealed source archives.
    # It does not borrow current native bytes or override filesystem reads.
    return camera_tracks.HistoricalReceiptRevalidator('8KmVDxkia_w')


@contextmanager
def historical_archive_fixture():
    """Real packet files and private archive copies, with matching nominal code.

    Packet symlinks are immutable inputs; only private copied archive bytes are
    changed. Matching nominal source files make a live-file fallback observable.
    """
    content = HERE.parent / 'content/canonical-native'
    with tempfile.TemporaryDirectory(prefix='historical-archive-refusal-') as directory:
        root = Path(directory)
        web = root / 'web'
        canonical = web / 'content/canonical-native'
        canonical.mkdir(parents=True)
        for source in content.iterdir():
            if source.name != 'historical-code':
                (canonical / source.name).symlink_to(source, target_is_directory=source.is_dir())
        for source in (content / 'historical-code').glob('*/*'):
            target = canonical / 'historical-code' / source.parent.name / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        sources = historical_synthesis_dependencies()
        sources['web/src/scene.ts'] = common.historical_code_bytes(
            'web/src/scene.ts', HISTORICAL_SCENE_SHA256)
        for relative, raw in sources.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (web / 'scripts/generate-analysis-bank-source-controls.py').symlink_to(
            HERE / 'generate-analysis-bank-source-controls.py')
        with patch.object(camera_tracks, 'ROOT', root), patch.object(camera_tracks, 'WEB', web), \
                patch.object(camera_tracks.common, 'WEB', web):
            yield root, web


def exact_exposure():
    selected = {
        'shotId': 'machine', 'classification': 'machine', 'timeSeconds': 1,
        'decodedTimeSeconds': 1.0, 'decodedFrameIndex': 30,
        'sourceImage': {'frameIndex': 30, 'sourceSha256': 'a' * 64,
                        'pixelFormat': 'gray8', 'sha256Gray8': 'b' * 64,
                        'width': 1920, 'height': 1080},
        'landmarks': [],
    }
    donor = copy.deepcopy(selected)
    donor['timeSeconds'] = 1.001
    donor['landmarks'] = [{'anchorId': 'support', 'status': 'observed',
                          'pixel': [120.5, 340.25], 'role': 'check'}]
    return {
        'source': {'sha256': 'a' * 64, 'width': 1920, 'height': 1080},
        'shots': [{'id': 'machine', 'hasCorrespondingMachine': True}],
        'frames': [selected, donor],
    }


def retain(data, selected=None):
    if selected is None:
        selected = copy.deepcopy(data['frames'][0])
    return common.retain_exact_exposure_landmarks([selected], data)[0]

CURRENT_BASE_PATHS = (
    'web/scripts/compact-source-common.py', 'web/scripts/approved-model.mjs',
    'web/model-representation.mjs', 'web/content/model-representation.json',
    'web/src/bindings.ts', 'web/src/scene.ts', 'web/src/mechanics.ts',
    'web/src/mechanics-data.ts', 'web/src/magnifier.ts', 'web/src/kinematics.ts',
    'web/scripts/native-identity-map.mjs', 'web/scripts/released-models.json',
    'cad/config/identity-migration-map.json',
)
CURRENT_PRODUCERS = (
    ('generate-analysis-synthesis-source-tracks.py', '6dW6VYXp9HM', 'Generator'),
    ('generate-analysis-synthesis-source-tracks.py', '8KmVDxkia_w', 'Generator'),
    ('compact-operation-rocker.py', 'jfH-NbsmvD4', 'operation'),
    ('compact-operation-rocker.py', '4mBuyixt22U', 'rocker'),
    ('generate-intro-source-track.py', 'NAsM30MAHLg', 'generate'),
    ('compact-spin.py', 'XPQwKRt4Y2k', 'generate'),
)


def current_record(video_id, approval, inventory_sha):
    """Synthetic new annotations, never historical fixtures with new labels.

    The source/model/map oracle is real and the inventory is the actual exporter
    result. Synthetic image identities, pixels, cameras and chosen complete inputs
    exist only in the isolated fixture; they are not source fidelity evidence.
    """
    catalog = (HERE.parent / 'src/video-catalog.ts').read_text()
    match = re.search(r"id: '" + re.escape(video_id) +
                      r"'[^\n]*durationSeconds: ([0-9.]+), sourceSha256: '([a-f0-9]{64})'", catalog)
    duration, source_sha = float(match[1]), match[2]
    model = {**approval['source'], 'units': 'metres', 'axes': 'X-width/Y-height/Z-depth'}
    native = {key: approval['identity'][key] for key in ('mapSha256', 'canonicalSha256')}
    native['inventorySha256'] = inventory_sha
    data = {
        'schemaVersion': 1, 'kind': 'current-source-observations',
        'source': {'videoId': video_id, 'sha256': source_sha, 'width': 1920, 'height': 1080,
                   'durationSeconds': duration, 'fps': {'numerator': 30, 'denominator': 1},
                   'rights': 'Synthetic test annotation; no source pixels redistributed.'},
        'model': model, 'nativeIdentity': native,
        'anchors': [{'id': 'support', 'kind': 'physical-feature',
                     'partPath': 'ha-harmonic-analyzer/fr-frame/fr-harmonic-base-1',
                     'partLocalMetres': [0, 0, 0], 'description': 'Synthetic fixed feature',
                     'correspondenceEvidence': 'Isolated test association to an actual exported native path.'}],
        'shots': [{'id': 'front', 'startSeconds': 0, 'endSeconds': 1.5,
                   'classification': 'machine', 'hasCorrespondingMachine': True, 'reason': 'Synthetic front shot.'},
                  {'id': 'detail', 'startSeconds': 1.5, 'endSeconds': duration,
                   'classification': 'machine', 'hasCorrespondingMachine': True, 'reason': 'Synthetic second shot.'}],
        'frames': [],
        'coverage': {'status': 'complete', 'blockers': [], 'requiredEveryIntegerSecond': True,
                     'changeTimesSeconds': [1.5, 1.75]},
    }
    state = {'crankTurns': 0, 'amplitudes': [0] * 20, 'phases': [0] * 20,
             'gearing': 'medium-medium', 'magnification': 165 / 39.85,
             'setup': {key: None if key == 'counterHeightM' else 0 for key in common.SETUP_FIELDS}}
    for time in sorted({*range(math.ceil(duration)), 1.5, 1.75}):
        image = {'frameIndex': round(time * 30), 'pixelFormat': 'gray8', 'width': 1920, 'height': 1080,
                 'sourceSha256': source_sha,
                 'sha256Gray8': hashlib.sha256(f'new synthetic annotation/{video_id}/{time}'.encode()).hexdigest()}
        ids = ['main'] if time < 1.75 else ['main', 'inset']
        views = [{
            'id': view_id, 'rectSourcePixels': [0, 0, 1920, 1080] if view_id == 'main' else [1200, 100, 600, 400],
            'presentation': 'native' if view_id == 'main' else 'horizontal-mirror',
            'camera': {'positionMetres': [0, 1, 3], 'quaternion': [0, 0, 0, 1], 'verticalFovDegrees': 30},
            'input': copy.deepcopy(state),
            'provenance': common.chosen_provenance('Synthetic chosen input; no recovered historical settings.'),
            'cameraProvenance': {'kind': 'source-informed-framing', 'evidence': 'Synthetic test camera.',
                                 'family': f'{video_id}/{view_id}/synthetic'},
            'cameraContinuityFamily': f'{video_id}/{view_id}/synthetic',
            'cameraMeasurement': {'model': copy.deepcopy(model), 'nativeIdentity': copy.deepcopy(native),
                                  'sourceImage': copy.deepcopy(image), 'evidence': 'Synthetic exact current association.'},
        } for view_id in ids]
        data['frames'].append({
            'timeSeconds': time, 'decodedTimeSeconds': time, 'sourceImage': image,
            'shotId': 'front' if time < 1.5 else 'detail', 'classification': 'machine', 'views': views,
            'landmarks': [{'anchorId': 'support', 'viewId': 'main', 'role': 'check', 'status': 'observed',
                           'method': 'manual', 'pixel': [120.5, 340.25], 'uncertaintyPx': 0.5}],
        })
    return data


def write_current_record(web, video_id, record):
    """Encode newly authored fixture JSON once with the actual shared byte codec."""
    decoded = (json.dumps(record, indent=2) + '\n').encode('utf-8')
    path = web / f'content/v39-source/{video_id}.observations.json.gz'
    path.write_bytes(fresh_tracks.observations.encode_observation_bytes(decoded))
    return path


@contextmanager
def current_source_fixture(filename, video_ids, *, inventory_path=None):
    """Execute real strict loaders/solver/gates under a temporary sealed authority."""
    source_root = HERE.parents[1]
    paths = set(CURRENT_BASE_PATHS)
    paths.update((Path(path).resolve().relative_to(source_root) if Path(path).is_absolute()
                  else Path(path)).as_posix() for path in fresh_tracks.EXECUTED_INPUTS)
    paths.add('web/scripts/' + filename)
    inventory_path = inventory_path or HERE.parent / 'content/v39-source/native-inventory.json'
    inventory_bytes = Path(inventory_path).read_bytes()
    inventory_sha = hashlib.sha256(inventory_bytes).hexdigest()
    approval = json.loads((HERE.parent / 'content/model-representation.json').read_bytes())
    with tempfile.TemporaryDirectory(prefix='fresh-source-generation-') as directory:
        root = Path(directory)
        web = root / 'web'
        for relative in paths:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((source_root / relative).read_bytes())
        (web / 'node_modules').symlink_to(HERE.parent / 'node_modules', target_is_directory=True)
        (web / 'content/v39-source').mkdir()
        (web / 'content/v39-source/native-inventory.json').write_bytes(inventory_bytes)
        (web / 'content/canonical-native').mkdir()
        manifest = {
            'canonicalConsumerHashNormalization': 'CRLF-to-LF',
            'canonicalConsumerInputs': [
                {'path': relative, 'sha256': hashlib.sha256(
                    (root / relative).read_bytes().replace(b'\r\n', b'\n')).hexdigest()}
                for relative in sorted(paths)],
            'currentSourceInventory': {'path': 'web/content/v39-source/native-inventory.json', 'sha256': inventory_sha},
        }
        (web / 'content/canonical-native/manifest.json').write_text(json.dumps(manifest))
        data = {}
        for video_id in video_ids:
            record = current_record(video_id, approval, inventory_sha)
            data[video_id] = record
            write_current_record(web, video_id, record)
            (web / f'content/{video_id}.source-track.json').write_text('{"previous":"must survive refusal"}\n')
        module = load_script(str(web / 'scripts' / filename), 'temporary_fresh_producer')
        yield root, module, data, paths


class ObservationStorageCommandTests(unittest.TestCase):
    def test_storage_cli_preserves_authored_bytes_before_any_seals_exist(self):
        codec = load_script('canonical-native-evidence.py', 'observation_storage_cli')
        name = 'web/content/v39-source/NAsM30MAHLg.observations.json'
        authored = (b'{\r\n "kind":"current-source-observations",'
                    b'"source":{"videoId":"NAsM30MAHLg"},'
                    b'"measurements":[-0,1.2300,1e-09,9007199254740993]\r\n}\r\n')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / name
            source.parent.mkdir(parents=True)
            source.write_bytes(authored)
            with patch.object(codec, 'ROOT', root), patch.object(
                    codec.sys, 'argv', ['canonical-native-evidence.py', 'compress-observations', name]):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    codec.main()
                report = json.loads(stdout.getvalue())
                target = source.with_name(source.name + '.gz')
                stored = target.read_bytes()
                self.assertEqual(gzip.decompress(stored), authored)
                self.assertEqual(stored[:10], b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff')
                self.assertEqual(report['observations'][0]['sha256'], hashlib.sha256(stored).hexdigest())
                self.assertEqual(report['observations'][0]['decodedSha256'], hashlib.sha256(authored).hexdigest())
                with redirect_stdout(io.StringIO()):
                    codec.main()
                self.assertEqual(target.read_bytes(), stored)
                self.assertEqual(source.read_bytes(), authored)
                self.assertFalse((root / codec.MANIFEST).exists())

    def test_storage_refuses_non_authored_inputs_before_writing_batch(self):
        codec = load_script('canonical-native-evidence.py', 'observation_storage_refusals')
        name = 'web/content/v39-source/NAsM30MAHLg.observations.json'
        valid = b'{"kind":"current-source-observations","source":{"videoId":"NAsM30MAHLg"}}'
        cases = [
            ('web/content/v39-source/native-inventory.json', valid),
            ('web/content/canonical-native/NAsM30MAHLg.observations.json.gz', valid),
            ('web/content/v38-source/NAsM30MAHLg.observations.json', valid),
            ('web/content/v39-source/8KmVDxkia_w.observations.json', valid),
            (name, valid.replace(b'current-source-observations', b'source-observations')),
            (name, valid[:-1] + b',"identityDerivative":{}}'),
            (name, b'[]'),
            (name, b'{"kind":NaN}'),
        ]
        for rejected_name, rejected in cases:
            with self.subTest(path=rejected_name, record=rejected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                first_name = 'web/content/v39-source/yF0kZ6kfR6E.observations.json'
                first = root / first_name
                first.parent.mkdir(parents=True)
                first.write_bytes(valid.replace(b'NAsM30MAHLg', b'yF0kZ6kfR6E'))
                source = root / rejected_name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(rejected)
                with patch.object(codec, 'ROOT', root), self.assertRaises(ValueError):
                    codec.compress_observations([first_name, rejected_name])
                self.assertFalse(first.with_name(first.name + '.gz').exists())
                self.assertEqual(source.read_bytes(), rejected)

    def test_storage_refuses_symlink_escape_and_destination_overwrite(self):
        codec = load_script('canonical-native-evidence.py', 'observation_storage_symlinks')
        name = 'web/content/v39-source/NAsM30MAHLg.observations.json'
        authored = b'{"kind":"current-source-observations","source":{"videoId":"NAsM30MAHLg"}}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / name
            source.parent.mkdir(parents=True)
            outside = root / 'NAsM30MAHLg.observations.json'
            outside.write_bytes(authored)
            source.symlink_to(outside)
            with patch.object(codec, 'ROOT', root), self.assertRaises(ValueError):
                codec.compress_observations([name])
            source.unlink()
            source.write_bytes(authored)
            target = source.with_name(source.name + '.gz')
            target.symlink_to(outside)
            with patch.object(codec, 'ROOT', root), self.assertRaises(ValueError):
                codec.compress_observations([name])
            self.assertEqual(outside.read_bytes(), authored)


@contextmanager
def pair_refusal_phase(module, *, before_build=None):
    """Observe the actual failing consumer phase without replacing validation."""
    refusal = []
    original_generator = module.Generator
    original_prepare = module.common.prepare_track

    class ObservedGenerator(original_generator):
        def __init__(self, video_id, *args, **kwargs):
            try:
                super().__init__(video_id, *args, **kwargs)
            except ValueError:
                refusal.append(('constructor', video_id))
                raise

        def build(self):
            if before_build is not None:
                before_build(self)
            try:
                return super().build()
            except ValueError:
                refusal.append(('build', self.video_id))
                raise

    def prepare(track):
        try:
            return original_prepare(track)
        except ValueError:
            refusal.append(('prepare', track['source']['videoId']))
            raise

    with patch.object(module, 'Generator', ObservedGenerator), \
            patch.object(module.common, 'prepare_track', prepare):
        yield refusal


def ordinary_build(module, video_id, entrypoint, data=None):
    if entrypoint == 'Generator':
        return module.Generator(video_id, data=data).build()
    return getattr(module, entrypoint)(data=data)


class FreshCurrentGenerationTests(unittest.TestCase):
    def test_all_six_ordinary_apis_assemble_actual_fresh_records_and_publish(self):
        for filename, video_id, entrypoint in CURRENT_PRODUCERS:
            with self.subTest(video=video_id), current_source_fixture(filename, [video_id]) as (root, module, data, _):
                track = ordinary_build(module, video_id, entrypoint, data[video_id])
                module.common.write_track(track)
                published = json.loads((root / f'web/content/{video_id}.source-track.json').read_bytes())
                self.assertEqual(published['sourceRecord']['kind'], 'current-source-observations')
                observation_path = root / f'web/content/v39-source/{video_id}.observations.json.gz'
                compressed = observation_path.read_bytes()
                decoded = (json.dumps(data[video_id], indent=2) + '\n').encode('utf-8')
                self.assertEqual(published['sourceRecord']['path'], f'content/v39-source/{video_id}.observations.json.gz')
                self.assertEqual(published['sourceRecord']['sha256'], hashlib.sha256(compressed).hexdigest())
                self.assertEqual(published['sourceRecord']['decodedSha256'], hashlib.sha256(decoded).hexdigest())
                self.assertEqual(published['nativeIdentity'], data[video_id]['nativeIdentity'])
                self.assertEqual(published['coverage']['status'], 'complete')
                first_detail = next(frame for frame in published['frames'] if frame['timeSeconds'] == 1.5)
                inset_change = next(frame for frame in published['frames'] if frame['timeSeconds'] == 1.75)
                self.assertEqual(first_detail['shotId'], 'detail')
                self.assertEqual([view['id'] for view in inset_change['views']], ['main', 'inset'])
                self.assertEqual(inset_change['views'][1]['presentation'], 'horizontal-mirror')
                self.assertEqual(first_detail['landmarks'][0]['pixel'], [120.5, 340.25])
                self.assertEqual(first_detail['views'][0]['cameraMeasurement']['sourceImage'], first_detail['sourceImage'])
                self.assertEqual(published['stages'], {str(stage): {'status': 'unmeasured'} for stage in (50, 20, 10, 5)})

    def test_compiled_anchor_motion_extends_only_the_closed_capture_contract(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            # The native association is minimal; retain the real catalog duration
            # and complete feasible exposure census required by the producer.
            track = module.Generator(video_id, data=data[video_id]).build()
            program = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const { root, track } = JSON.parse(readFileSync(0, 'utf8'));
const fresh = await import(root + '/scripts/fresh-source-observations.mjs');
const observations = await fresh.loadCurrentObservations(root, track.source.videoId);
await fresh.validateCurrentTrackAssociation(track, observations, root);
for (const motion of ['fixed', 'moving', null, undefined]) {
  const candidate = structuredClone(track);
  if (motion === undefined) delete candidate.anchors[0].motion;
  else candidate.anchors[0].motion = motion;
  await fresh.validateCurrentTrackAssociation(candidate, observations, root);
}
for (const motion of ['frozen', false, 0, {}, []]) {
  const candidate = structuredClone(track);
  candidate.anchors[0].motion = motion;
  await assert.rejects(fresh.validateCurrentTrackAssociation(candidate, observations, root),
    /invalid playback motion/);
}
for (const change of [
  { untrustedExtension: true }, { partLocalMetres: null },
  { worldMetres: [0, 0, 0] }, { correspondenceEvidence: '' },
]) {
  const candidate = structuredClone(track);
  Object.assign(candidate.anchors[0], change);
  await assert.rejects(fresh.validateCurrentTrackAssociation(candidate, observations, root),
    /closed actual native feature association/);
}
for (const change of [
  { partPath: null }, { partPath: 'ha-harmonic-analyzer/fr-frame/unknown-native-1' },
  { runtimeTemplatePartPath: observations.anchors[0].partPath },
]) {
  const candidate = structuredClone(track);
  Object.assign(candidate.anchors[0], change);
  await assert.rejects(fresh.validateCurrentTrackAssociation(candidate, observations, root),
    /unknown runtime instance\/alias or mislabels/);
}
for (const change of [{ motion: 'fixed' }, { untrustedExtension: true }, { partLocalMetres: null }]) {
  const capture = structuredClone(observations);
  Object.assign(capture.anchors[0], change);
  await assert.rejects(fresh.validateCurrentObservations(capture, { webRoot: root }),
    /closed actual native feature association/);
}
"""
            result = subprocess.run(
                ['node', '--input-type=module', '--eval', program],
                input=json.dumps({'root': str(root / 'web'), 'track': track}),
                capture_output=True, text=True, cwd=root, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_readback_routes_only_adjacent_cut_clocks_to_the_incoming_shot(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            cut = record['shots'][1]['startSeconds']
            before = math.nextafter(cut, -math.inf)
            after = math.nextafter(cut, math.inf)
            two_before = math.nextafter(before, -math.inf)
            incoming = next(frame for frame in record['frames'] if frame['timeSeconds'] == cut)
            program = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const { root, track, cut, before, after, twoBefore } = JSON.parse(readFileSync(0, 'utf8'));
const fresh = await import(root + '/scripts/fresh-source-observations.mjs');
const observations = await fresh.loadCurrentObservations(root, track.source.videoId);
const index = track.frames.findIndex(frame => frame.timeSeconds === cut);
await fresh.validateCurrentTrackAssociation(track, observations, root);
for (const time of [before, cut, after]) {
  const candidate = structuredClone(track);
  candidate.frames[index].timeSeconds = time;
  await fresh.validateCurrentTrackAssociation(candidate, observations, root);
  assert.equal(candidate.frames[index].timeSeconds, time);
  assert.equal(candidate.frames[index].decodedTimeSeconds, track.frames[index].decodedTimeSeconds);
}
for (const time of [twoBefore, cut - 0.125]) {
  const candidate = structuredClone(track);
  candidate.frames[index].timeSeconds = time;
  await assert.rejects(fresh.validateCurrentTrackAssociation(candidate, observations, root),
    /stale requested\/decoded source clock or classification/);
}
for (const time of [twoBefore, cut - 0.125]) {
  const candidate = structuredClone(track);
  candidate.frames[index].decodedTimeSeconds = time;
  await assert.rejects(fresh.validateCurrentTrackAssociation(candidate, observations, root),
    /stale requested\/decoded source clock or classification/);
}
const outgoing = structuredClone(track);
outgoing.frames[index].timeSeconds = before;
outgoing.frames[index].shotId = observations.shots[0].id;
await assert.rejects(fresh.validateCurrentTrackAssociation(outgoing, observations, root),
  /stale requested\/decoded source clock or classification/);
// Authored exposures retain strict ownership: the exact predecessor of an
// outgoing end is still valid capture evidence, not a compiled execution key.
const outgoingCapture = structuredClone(observations);
outgoingCapture.frames.find(frame => frame.timeSeconds === 1).decodedTimeSeconds = before;
await fresh.validateCurrentObservations(outgoingCapture, { webRoot: root });
const capture = structuredClone(observations);
capture.frames.find(frame => frame.timeSeconds === cut).decodedTimeSeconds = twoBefore;
await assert.rejects(fresh.validateCurrentObservations(capture, { webRoot: root }),
  /current requested\/decoded clock or shot classification differs/);
"""
            for decoded in (cut, after):
                with self.subTest(decoded=decoded):
                    incoming['decodedTimeSeconds'] = decoded
                    write_current_record(root / 'web', video_id, record)
                    track = module.Generator(video_id, data=record).build()
                    result = subprocess.run(
                        ['node', '--input-type=module', '--eval', program],
                        input=json.dumps({'root': str(root / 'web'), 'track': track,
                                          'cut': cut, 'before': before, 'after': after,
                                          'twoBefore': two_before}),
                        capture_output=True, text=True, cwd=root, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_analysis_and_rocker_cut_packets_preserve_source_ownership(self):
        cases = (
            ('generate-analysis-synthesis-source-tracks.py', '6dW6VYXp9HM', 'Generator', 'analysis-37'),
            ('compact-operation-rocker.py', '4mBuyixt22U', 'rocker', 'overlay-2'),
        )
        program = r"""
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const { root, track, time, shotId, incomingId, twoBefore, precut } = JSON.parse(readFileSync(0, 'utf8'));
const fresh = await import(root + '/scripts/fresh-source-observations.mjs');
const observations = await fresh.loadCurrentObservations(root, track.source.videoId);
const frame = track.frames.find(frame => frame.timeSeconds === time);
assert.equal(frame.shotId, shotId);
await fresh.validateCurrentTrackAssociation(track, observations, root);
assert.equal(frame.timeSeconds, time);
if (incomingId) {
  // The genuine authored outgoing predecessor is not an incoming alias.
  const borrowed = structuredClone(track);
  borrowed.frames.find(frame => frame.timeSeconds === time).shotId = incomingId;
  await assert.rejects(fresh.validateCurrentTrackAssociation(borrowed, observations, root),
    /stale requested\/decoded source clock or classification/);
} else {
  const shot = observations.shots.find(shot => shot.id === shotId);
  assert.ok(frame.decodedTimeSeconds >= shot.startSeconds && frame.decodedTimeSeconds < shot.endSeconds);
  const gap = structuredClone(track);
  gap.frames.find(frame => frame.timeSeconds === time).timeSeconds = twoBefore;
  await assert.rejects(fresh.validateCurrentTrackAssociation(gap, observations, root),
    /stale requested\/decoded source clock or classification/);
  const borrowed = structuredClone(track);
  const target = borrowed.frames.find(frame => frame.timeSeconds === time);
  Object.assign(target, { decodedTimeSeconds: precut.decodedTimeSeconds,
    sourceImage: precut.sourceImage, views: precut.views, landmarks: precut.landmarks });
  await assert.rejects(fresh.validateCurrentTrackAssociation(borrowed, observations, root),
    /stale requested\/decoded source clock or classification/);
}
"""
        for filename, video_id, entrypoint, shot_id in cases:
            with self.subTest(video=video_id), current_source_fixture(filename, [video_id]) as (root, module, _, _):
                # Keep the original authored gzip bytes and authority tuple exact.
                relative = f'content/v39-source/{video_id}.observations.json.gz'
                original = (HERE.parent / relative).read_bytes()
                (root / 'web' / relative).write_bytes(original)
                record = json.loads(gzip.decompress(original))
                track = ordinary_build(module, video_id, entrypoint, record)
                shot = next(shot for shot in record['shots'] if shot['id'] == shot_id)
                incoming_id, two_before, precut = None, None, None
                expected_shot_id = shot_id
                if video_id == '6dW6VYXp9HM':
                    time = math.nextafter(shot['endSeconds'], -math.inf)
                    frame = next(frame for frame in record['frames']
                                 if frame['timeSeconds'] == time and frame['shotId'] == shot_id)
                    endpoint = next(row for row in track['frames'] if row['timeSeconds'] == time)
                    self.assertEqual(endpoint['shotId'], shot_id)
                    self.assertEqual(endpoint['decodedTimeSeconds'], frame['decodedTimeSeconds'])
                    self.assertEqual(endpoint['sourceImage'], frame['sourceImage'])
                    incoming_id = next(row['id'] for row in record['shots']
                                       if row['startSeconds'] == shot['endSeconds'])
                else:
                    time = math.nextafter(shot['startSeconds'], -math.inf)
                    two_before = math.nextafter(time, -math.inf)
                    precut = max((frame for frame in record['frames']
                                  if frame['decodedTimeSeconds'] < shot['startSeconds']),
                                 key=lambda frame: frame['decodedTimeSeconds'])
                    authored = next((frame for frame in record['frames']
                                     if frame['timeSeconds'] == time), None)
                    if authored is not None:
                        # A genuine authored outgoing clock outranks derived cut routing.
                        self.assertLess(authored['decodedTimeSeconds'], shot['startSeconds'])
                        endpoint = next(row for row in track['frames'] if row['timeSeconds'] == time)
                        self.assertEqual(endpoint['sourceImage'], authored['sourceImage'])
                        self.assertEqual(endpoint['decodedTimeSeconds'], authored['decodedTimeSeconds'])
                        expected_shot_id = authored['shotId']
                        incoming_id = shot_id
                controls = [{'time': time, 'shotId': expected_shot_id, 'incomingId': incoming_id,
                             'twoBefore': two_before, 'precut': precut}]
                if video_id == '4mBuyixt22U' and incoming_id is not None:
                    # The separate incoming packet still refuses a two-ULP key or outgoing PTS.
                    start = shot['startSeconds']
                    controls.append({'time': start, 'shotId': shot_id, 'incomingId': None,
                                     'twoBefore': math.nextafter(math.nextafter(start, -math.inf), -math.inf),
                                     'precut': precut})
                for control in controls:
                    result = subprocess.run(
                        ['node', '--input-type=module', '--eval', program],
                        input=json.dumps({'root': str(root / 'web'), 'track': track, **control}),
                        capture_output=True, text=True, cwd=root, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_fresh_record_and_old_headers_never_read_old_calibration(self):
        for filename, video_id, entrypoint in CURRENT_PRODUCERS:
            for mutation in ('missing', 'archive-kind', 'old-model'):
                with self.subTest(video=video_id, mutation=mutation), current_source_fixture(filename, [video_id]) as (root, module, data, _):
                    path = root / f'web/content/v39-source/{video_id}.observations.json.gz'
                    if mutation == 'missing':
                        path.with_suffix('').write_bytes(module.common.fresh.read_observation_bytes(path))
                        path.unlink()
                    elif mutation == 'archive-kind':
                        data[video_id]['kind'] = 'source-observations'
                        write_current_record(root / 'web', video_id, data[video_id])
                    else:
                        data[video_id]['model'] = {
                            'sha256': camera_tracks.ANALYSIS_MODEL_SHA256,
                            'sourceCommit': camera_tracks.FRAMING_GPU_MODEL_SOURCE['sourceCommit'],
                            'units': 'metres', 'axes': 'X-width/Y-height/Z-depth'}
                        write_current_record(root / 'web', video_id, data[video_id])
                    previous = (root / f'web/content/{video_id}.source-track.json').read_bytes()
                    original_read = Path.read_bytes
                    def refuse_old(path):
                        if path.name.endswith('source-seeds.json') or path.name == Path(camera_tracks.CALIBRATION).name:
                            raise AssertionError('Ordinary refusal reached old native calibration.')
                        return original_read(path)
                    with patch.object(Path, 'read_bytes', refuse_old), self.assertRaises(ValueError):
                        ordinary_build(module, video_id, entrypoint)
                    self.assertEqual((root / f'web/content/{video_id}.source-track.json').read_bytes(), previous)

    def test_direct_data_mutation_and_publish_substitution_cannot_bypass_fresh_record(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            generator = module.Generator(video_id, data=data[video_id])
            pristine = copy.deepcopy(generator.data)
            first = generator.build()
            self.assertEqual(generator.data, pristine)
            first['frames'][0]['views'][0]['camera']['positionMetres'][0] += 1
            with self.assertRaises(ValueError):
                module.common.prepare_track(first)
            generator.data['frames'][0]['views'][0]['camera']['positionMetres'][0] += 1
            with self.assertRaises(ValueError):
                generator.build()
            generator.data = pristine
            track = generator.build()
            path = root / f'web/content/v39-source/{video_id}.observations.json.gz'
            decoded = module.common.fresh.read_observation_bytes(path)
            path.write_bytes(module.common.fresh.encode_observation_bytes(decoded + b'\n'))
            with self.assertRaises(ValueError):
                module.common.prepare_track(track)

    def test_publication_requires_both_exact_byte_seals_and_gzip_source_path(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            track = module.Generator(video_id, data=data[video_id]).build()
            for mutation in ('plain-path', 'missing-compressed-sha', 'compressed-sha',
                             'missing-decoded-sha', 'decoded-sha', 'malformed-decoded-sha'):
                with self.subTest(mutation=mutation):
                    candidate = copy.deepcopy(track)
                    record = candidate['sourceRecord']
                    if mutation == 'plain-path':
                        record['path'] = record['path'].removesuffix('.gz')
                    elif mutation == 'missing-compressed-sha':
                        del record['sha256']
                    elif mutation == 'compressed-sha':
                        record['sha256'] = '0' * 64
                    elif mutation == 'missing-decoded-sha':
                        del record['decodedSha256']
                    else:
                        record['decodedSha256'] = '0' * (64 if mutation == 'decoded-sha' else 63)
                    with self.assertRaises(ValueError):
                        module.common.prepare_track(candidate)
            observation_path = root / 'web' / track['sourceRecord']['path']
            observation_path.with_suffix('').write_bytes(module.common.fresh.read_observation_bytes(observation_path))
            observation_path.unlink()
            with self.assertRaises(FileNotFoundError):
                module.Generator(video_id, data=data[video_id]).build()
            with self.assertRaises(FileNotFoundError):
                module.common.prepare_track(track)

    def test_storage_and_decoded_byte_changes_cannot_reuse_an_existing_publication(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            track = module.Generator(video_id, data=data[video_id]).build()
            path = root / f'web/content/v39-source/{video_id}.observations.json.gz'
            compressed = path.read_bytes()
            decoded = module.common.fresh.decode_observation_bytes(compressed)
            changed_header = bytearray(compressed)
            changed_header[4] ^= 1
            self.assertEqual(module.common.fresh.decode_observation_bytes(bytes(changed_header)), decoded)
            path.write_bytes(changed_header)
            with self.assertRaises(ValueError):
                module.common.prepare_track(track)
            changed_json = module.common.fresh.encode_observation_bytes(decoded + b'\n')
            self.assertEqual(json.loads(module.common.fresh.decode_observation_bytes(changed_json)), data[video_id])
            path.write_bytes(changed_json)
            resealed = copy.deepcopy(track)
            resealed['sourceRecord']['sha256'] = hashlib.sha256(changed_json).hexdigest()
            with self.assertRaises(ValueError):
                module.common.prepare_track(resealed)
            changed_data = copy.deepcopy(data[video_id])
            changed_data['frames'][0]['views'][0]['camera']['positionMetres'][0] += 1
            write_current_record(root / 'web', video_id, changed_data)
            resealed['sourceRecord']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            resealed['sourceRecord']['decodedSha256'] = hashlib.sha256(
                module.common.fresh.read_observation_bytes(path)).hexdigest()
            with self.assertRaises(ValueError):
                module.common.prepare_track(resealed)
            corrupted = compressed[:-8] + bytes([compressed[-8] ^ 1]) + compressed[-7:]
            path.write_bytes(corrupted)
            resealed['sourceRecord']['sha256'] = hashlib.sha256(corrupted).hexdigest()
            with self.assertRaises(gzip.BadGzipFile):
                module.common.prepare_track(resealed)

    def test_publication_cannot_omit_changed_missing_or_unsealed_actual_inputs(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, _):
            track = module.Generator(video_id, data=data[video_id]).build()
            module.common.write_track(track)
            output = root / f'web/content/{video_id}.source-track.json'
            published = output.read_bytes()
            inputs = set(track['sourceRecord']['executedInputs']) | set(CURRENT_BASE_PATHS)
            inputs.add(track['sourceRecord']['producerPath'])
            # The identity-map payload has its own canonical exact-byte identity,
            # not a CRLF-normalized executed-code seal.
            inputs.discard('cad/config/identity-migration-map.json')
            manifest_path = root / 'web/content/canonical-native/manifest.json'
            manifest_bytes = manifest_path.read_bytes()
            for relative in sorted(inputs):
                path = root / relative
                original = path.read_bytes()
                candidate = copy.deepcopy(track)
                candidate['sourceRecord']['executedInputs'] = [
                    name for name in candidate['sourceRecord']['executedInputs'] if name != relative]
                for mutation in ('changed', 'missing', 'unsealed'):
                    with self.subTest(path=relative, mutation=mutation):
                        try:
                            if mutation == 'changed':
                                path.write_bytes(original + b'\n')
                            elif mutation == 'missing':
                                path.unlink()
                            else:
                                manifest = json.loads(manifest_bytes)
                                manifest['canonicalConsumerInputs'] = [
                                    row for row in manifest['canonicalConsumerInputs'] if row['path'] != relative]
                                manifest_path.write_text(json.dumps(manifest))
                            with self.assertRaises(ValueError):
                                module.common.write_track(candidate)
                            self.assertEqual(output.read_bytes(), published)
                        finally:
                            path.write_bytes(original)
                            manifest_path.write_bytes(manifest_bytes)

    def test_complete_unsolved_input_and_conflicting_exact_exposure_layout_refuse(self):
        video_id = 'XPQwKRt4Y2k'
        for mutation in ('unsolved', 'alias-layout', 'alias-pixel-hash', 'alias-bgr-layout'):
            with self.subTest(mutation=mutation), current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
                baseline = copy.deepcopy(data[video_id])
                if mutation != 'unsolved':
                    alias = copy.deepcopy(baseline['frames'][0])
                    alias['timeSeconds'] = 0.25
                    if mutation == 'alias-bgr-layout':
                        del alias['sourceImage']['sha256Gray8']
                        alias['sourceImage'].update(pixelFormat='bgr8', sha256Bgr8='0' * 64)
                        alias['views'][0]['cameraMeasurement']['sourceImage'] = copy.deepcopy(alias['sourceImage'])
                    baseline['frames'].insert(1, alias)
                # Repeated requested keys for one decoded exposure are legal
                # when their associations agree, including distinct pixel codecs.
                write_current_record(root / 'web', video_id, baseline)
                published_track = module.Generator(video_id, data=baseline).build()
                module.common.write_track(published_track)
                output = root / f'web/content/{video_id}.source-track.json'
                published = output.read_bytes()
                record = copy.deepcopy(baseline)
                if mutation == 'unsolved':
                    record['frames'][0]['views'][0]['input']['magnification'] = 100
                elif mutation == 'alias-pixel-hash':
                    alias = record['frames'][1]
                    alias['sourceImage']['sha256Gray8'] = '0' * 64
                    alias['views'][0]['cameraMeasurement']['sourceImage'] = copy.deepcopy(alias['sourceImage'])
                else:
                    record['frames'][1]['views'][0]['presentation'] = 'horizontal-mirror'
                with self.assertRaises(ValueError):
                    module.Generator(video_id, data=record)
                self.assertEqual(output.read_bytes(), published)

    def test_measured_single_machine_attenuation_publishes_without_fake_background_camera(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            for frame, opacity in zip(record['frames'][:2], (0, 0.5)):
                frame['views'][0]['composite'] = {
                    'mode': 'crossfade', 'groupId': 'source-black-fade',
                    'imageLayerId': 'machine-photo', 'opacity': opacity}
                frame['views'][0]['compositeEvidence'] = 'Synthetic actual single machine photo attenuated over black.'
                if opacity == 0:
                    frame['landmarks'] = []
            write_current_record(root / 'web', video_id, record)
            track = module.Generator(video_id).build()
            path, payload = module.common.prepare_track(track)
            published = json.loads(payload)
            self.assertEqual(path, root / f'web/content/{video_id}.source-track.json')
            self.assertEqual([frame['views'][0]['composite']['opacity'] for frame in published['frames'][:2]], [0, 0.5])
            self.assertEqual([len(frame['views']) for frame in published['frames'][:2]], [1, 1])

    def test_current_attenuation_cannot_drop_observed_features_or_violate_actual_image_weights(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            for mutation in ('zero-observed', 'missing-evidence', 'overweight', 'same-image-weights', 'unknown-mode'):
                with self.subTest(mutation=mutation):
                    baseline = copy.deepcopy(data[video_id])
                    frame = baseline['frames'][0]
                    view = frame['views'][0]
                    view['composite'] = {
                        'mode': 'crossfade', 'groupId': 'source-black-fade',
                        'imageLayerId': 'machine-photo', 'opacity': 0.7}
                    view['compositeEvidence'] = 'Synthetic independent actual source image weights.'
                    if mutation in ('overweight', 'same-image-weights'):
                        other = copy.deepcopy(view)
                        other['id'] = 'second'
                        if mutation == 'overweight':
                            other['composite'].update(imageLayerId='actual-second-image', opacity=0.3)
                        frame['views'].append(other)
                    write_current_record(root / 'web', video_id, baseline)
                    module.common.write_track(module.Generator(video_id, data=baseline).build())
                    output = root / f'web/content/{video_id}.source-track.json'
                    published = output.read_bytes()
                    record = copy.deepcopy(baseline)
                    view = record['frames'][0]['views'][0]
                    if mutation == 'zero-observed':
                        view['composite']['opacity'] = 0
                    elif mutation == 'missing-evidence':
                        del view['compositeEvidence']
                    elif mutation == 'unknown-mode':
                        view['composite']['mode'] = 'unknown'
                    else:
                        record['frames'][0]['views'][1]['composite']['opacity'] = (
                            0.7 if mutation == 'overweight' else 0.3)
                    with self.assertRaises(ValueError):
                        module.Generator(video_id, data=record)
                    self.assertEqual(output.read_bytes(), published)

    def test_actual_compiled_assembly_changes_are_retained_without_authored_change_labels(self):
        video_id = 'jfH-NbsmvD4'
        with current_source_fixture('compact-operation-rocker.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            template = copy.deepcopy(record['frames'][0])
            provenance = {'kind': 'chosen-feasible', 'videoId': video_id, 'frameIndex': 20,
                          'evidence': 'Synthetic actual source release support; hidden thread phase remains chosen.',
                          'unobservedDegreesOfFreedom': ['thread phase']}
            added = []
            for time, release, evidence in (
                (0.2, 1, 'first independently supported release'),
                (0.3, 1, 'changed evidence only, not a new physical pose'),
                (0.4, 2, 'second independently supported release'),
                (0.5, None, 'normal operating restoration'),
            ):
                frame = copy.deepcopy(template)
                frame['timeSeconds'] = frame['decodedTimeSeconds'] = time
                frame['sourceImage']['frameIndex'] = round(time * 30)
                frame['sourceImage']['sha256Gray8'] = hashlib.sha256(f'synthetic physical exposure/{time}'.encode()).hexdigest()
                view = frame['views'][0]
                view['cameraMeasurement']['sourceImage'] = copy.deepcopy(frame['sourceImage'])
                if release is not None:
                    view['sourceAssembly'] = {
                        'kind': 'source-assembly', 'provenance': {**provenance, 'evidence': evidence},
                        'retainingNut': {'attachment': 'threaded', 'releaseTurns': release},
                    }
                added.append(frame)
            record['frames'][1:1] = added
            self.assertEqual(module.common.fresh.assembly_change_times(record, web_root=root / 'web'), [0.2, 0.4, 0.5])
            write_current_record(root / 'web', video_id, record)
            track = module.Generator(video_id).build()
            selected = {frame['timeSeconds']: frame for frame in track['frames']}
            self.assertEqual(selected[0.2]['views'][0]['sourceAssembly']['retainingNut']['releaseTurns'], 1)
            self.assertEqual(selected[0.4]['views'][0]['sourceAssembly']['retainingNut']['releaseTurns'], 2)
            self.assertNotIn('sourceAssembly', selected[0.5]['views'][0])
            self.assertNotIn(0.3, selected)
            for time in (0.2, 0.4, 0.5):
                self.assertIn(time, track['coverage']['changeTimesSeconds'])
            module.common.prepare_track(track)

    def test_genuine_runtime_instance_anchor_keeps_template_binding_and_refuses_rest_aliases(self):
        video_id = 'jfH-NbsmvD4'
        template_path = 'ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-3'
        with current_source_fixture('compact-operation-rocker.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            anchor = record['anchors'][0]
            anchor.update(partPath=template_path + '@upper',
                          runtimeTemplatePartPath=template_path,
                          description='Synthetic local feature of the genuine runtime upper T18 instance',
                          correspondenceEvidence='Synthetic current feature association; no template REST world projection.')
            write_current_record(root / 'web', video_id, record)
            track = module.Generator(video_id).build()
            _, payload = module.common.prepare_track(track)
            published = json.loads(payload)
            self.assertEqual(published['anchors'][0]['partPath'], template_path + '@upper')
            self.assertEqual(published['anchors'][0]['runtimeTemplatePartPath'], template_path)
            self.assertEqual(published['anchors'][0]['partLocalMetres'], [0, 0, 0])
            self.assertNotIn('worldMetres', published['anchors'][0])
            tampered = copy.deepcopy(track)
            tampered['anchors'][0]['runtimeTemplatePartPath'] = 'ha-harmonic-analyzer/fr-frame/fr-harmonic-base-1'
            with self.assertRaises(ValueError):
                module.common.prepare_track(tampered)
            for mutation in ('unknown-instance', 'wrong-template', 'missing-template',
                             'world-only', 'mixed-coordinates', 'rest-as-instance'):
                with self.subTest(mutation=mutation):
                    invalid = copy.deepcopy(record)
                    candidate = invalid['anchors'][0]
                    if mutation == 'unknown-instance':
                        candidate['partPath'] = template_path + '@top'
                    elif mutation == 'wrong-template':
                        candidate['runtimeTemplatePartPath'] = 'ha-harmonic-analyzer/fr-frame/fr-harmonic-base-1'
                    elif mutation == 'missing-template':
                        del candidate['runtimeTemplatePartPath']
                    elif mutation == 'rest-as-instance':
                        candidate['partPath'] = template_path
                    else:
                        candidate['worldMetres'] = [0, 0, 0]
                        if mutation == 'world-only':
                            del candidate['partLocalMetres']
                    with self.assertRaises(ValueError):
                        module.Generator(video_id, data=invalid)

    def test_direct_data_requires_current_header_native_tuple_and_exact_camera_binding(self):
        video_id = '6dW6VYXp9HM'
        with current_source_fixture('generate-analysis-synthesis-source-tracks.py', [video_id]) as (root, module, data, _):
            baseline = module.Generator(video_id, data=data[video_id]).build()
            module.common.write_track(baseline)
            output = root / f'web/content/{video_id}.source-track.json'
            published = output.read_bytes()
            for mutation in ('archive-header', 'old-model', 'native-map', 'camera-image', 'missing-binding'):
                with self.subTest(mutation=mutation):
                    record = copy.deepcopy(data[video_id])
                    if mutation == 'archive-header':
                        record['kind'] = 'source-observations'
                    elif mutation == 'old-model':
                        record['model']['sha256'] = camera_tracks.ANALYSIS_MODEL_SHA256
                        for frame in record['frames']:
                            for view in frame['views']:
                                view['cameraMeasurement']['model'] = copy.deepcopy(record['model'])
                    elif mutation == 'native-map':
                        record['nativeIdentity']['mapSha256'] = '0' * 64
                        for frame in record['frames']:
                            for view in frame['views']:
                                view['cameraMeasurement']['nativeIdentity'] = copy.deepcopy(record['nativeIdentity'])
                    elif mutation == 'camera-image':
                        record['frames'][0]['views'][0]['cameraMeasurement']['sourceImage']['sha256Gray8'] = '0' * 64
                    else:
                        del record['frames'][0]['views'][0]['cameraMeasurement']
                    with self.assertRaises(ValueError):
                        module.Generator(video_id, data=record)
                    self.assertEqual(output.read_bytes(), published)

    def test_live_executed_input_drift_and_authority_revocation_refuse_new_builds(self):
        video_id = 'NAsM30MAHLg'
        with current_source_fixture('generate-intro-source-track.py', [video_id]) as (root, module, data, paths):
            generator = module.Generator(video_id, data=data[video_id])
            generator.build()
            for relative in sorted(paths):
                if relative.endswith('model-representation.json'):
                    continue
                path = root / relative
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b'\n')
                    with self.subTest(input=relative), self.assertRaises(ValueError):
                        generator.build()
                finally:
                    path.write_bytes(original)
            approval_path = root / 'web/content/model-representation.json'
            approval = json.loads(approval_path.read_bytes())
            approval['schemaVersion'] = 1
            approval_path.write_text(json.dumps(approval))
            # An independently changed fixture live seal still cannot replace
            # the strict authority oracle with permissive old-schema approval.
            manifest_path = root / 'web/content/canonical-native/manifest.json'
            manifest = json.loads(manifest_path.read_bytes())
            next(row for row in manifest['canonicalConsumerInputs']
                 if row['path'] == 'web/content/model-representation.json')['sha256'] = hashlib.sha256(approval_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                generator.build()

    def test_both_pair_clis_preflight_all_builds_and_preparations_before_publication(self):
        pairs = (
            ('generate-analysis-synthesis-source-tracks.py', ['6dW6VYXp9HM', '8KmVDxkia_w']),
            ('compact-operation-rocker.py', ['jfH-NbsmvD4', '4mBuyixt22U']),
        )
        for filename, video_ids in pairs:
            for failure in ('constructor', 'prepare'):
                with self.subTest(producer=filename, failure=failure), current_source_fixture(filename, video_ids) as (root, module, data, _):
                    # Positive control uses this same two-video fixture and the
                    # unmodified CLI, not a direct-data single-video constructor.
                    with patch.object(sys, 'argv', [filename]), redirect_stdout(io.StringIO()):
                        module.main()
                    paths = [root / f'web/content/{video_id}.source-track.json' for video_id in video_ids]
                    previous = [path.read_bytes() for path in paths]
                    self.assertEqual([json.loads(raw)['source']['videoId'] for raw in previous], video_ids)
                    second = video_ids[1]
                    record = data[second]
                    if failure == 'constructor':
                        record['frames'][0]['views'][0]['input']['magnification'] = 100
                    else:
                        record['coverage'].update(status='blocked', blockers=['Synthetic missing camera.'])
                        record['frames'][0]['views'][0]['camera'] = None
                        record['frames'][0]['views'][0]['unavailable'] = [{'reason': 'Synthetic missing camera.'}]
                    write_current_record(root / 'web', second, record)
                    with pair_refusal_phase(module) as refusal, patch.object(sys, 'argv', [filename]), \
                            redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                        module.main()
                    self.assertEqual(refusal, [(failure, second)])
                    self.assertEqual([path.read_bytes() for path in paths], previous)


class ObserveExactExposureTests(unittest.TestCase):
    def fixture(self):
        data = exact_exposure()
        view = {'id': 'main', 'presentation': 'native', 'rectSourcePixels': [0, 0, 1920, 1080]}
        for frame in data['frames']:
            frame['views'] = [copy.deepcopy(view)]
        seed = data['frames'][1]
        seed['landmarks'][0].update(viewId='main', method='manual', uncertaintyPx=0.5)
        return seed, data['frames'][0]

    def test_identical_exposure_and_full_layout_retain_manual_physical_pixels(self):
        seed, frame = self.fixture()
        result = observe_source.exact_exposure_landmarks(seed, frame, frame['sourceImage'], {'support': 'physical-feature'})
        self.assertEqual(result[0]['pixel'], [120.5, 340.25])
        self.assertEqual(result[0]['uncertaintyPx'], 0.5)

    def test_equal_roi_cannot_override_hash_pts_or_complete_layout(self):
        for mutation in ('hash', 'pts', 'mirror', 'warp', 'opacity', 'layer', 'extra-view', 'missing-view', 'draw-order'):
            with self.subTest(mutation=mutation):
                seed, frame = self.fixture()
                if mutation == 'hash':
                    frame['sourceImage']['sha256Gray8'] = 'c' * 64
                elif mutation == 'pts':
                    frame['decodedTimeSeconds'] += 0.01
                elif mutation == 'mirror':
                    frame['views'][0]['presentation'] = 'horizontal-mirror'
                elif mutation == 'warp':
                    frame['views'][0]['imagePlaneWarp'] = {'kind': 'homography', 'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                elif mutation in ('opacity', 'layer'):
                    seed['views'][0]['composite'] = {'mode': 'crossfade', 'groupId': 'same', 'imageLayerId': 'out', 'opacity': 0.5}
                    frame['views'][0]['composite'] = copy.deepcopy(seed['views'][0]['composite'])
                    frame['views'][0]['composite']['opacity' if mutation == 'opacity' else 'imageLayerId'] = 0.25 if mutation == 'opacity' else 'in'
                elif mutation == 'extra-view':
                    frame['views'].append({'id': 'inset', 'rectSourcePixels': [0, 0, 200, 200], 'presentation': 'native'})
                elif mutation == 'draw-order':
                    seed['views'].append({'id': 'inset', 'rectSourcePixels': [0, 0, 200, 200], 'presentation': 'native'})
                    frame['views'] = list(reversed(copy.deepcopy(seed['views'])))
                else:
                    frame['views'] = []
                self.assertEqual(observe_source.exact_exposure_landmarks(
                    seed, frame, frame['sourceImage'], {'support': 'physical-feature'}), [])



class ObservationStorageBoundaryTests(unittest.TestCase):
    def test_bad_or_missing_gzip_never_uses_plain_canonical_sibling(self):
        valid = gzip.compress(b'{"frames": []}', mtime=0)
        bad_crc = valid[:-8] + bytes([valid[-8] ^ 1]) + valid[-7:]
        cases = (
            ('missing', None, FileNotFoundError),
            ('bad-header', b'not a gzip stream', gzip.BadGzipFile),
            ('truncated', valid[:-8], EOFError),
            ('bad-crc', bad_crc, gzip.BadGzipFile),
            ('invalid-json', gzip.compress(b'{"frames":', mtime=0), json.JSONDecodeError),
        )
        for label, stored, error in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                web = Path(directory)
                content = web / 'content' / 'canonical-native'
                content.mkdir(parents=True)
                (content / 'fixture.observations.json').write_text('{"frames": []}')
                if stored is not None:
                    (content / 'fixture.observations.json.gz').write_bytes(stored)
                with patch.object(common, 'WEB', web), self.assertRaises(error):
                    common.load_historical_observations('fixture')

    def test_plain_canonical_observation_output_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            web = Path(directory)
            content = web / 'content' / 'canonical-native'
            content.mkdir(parents=True)
            path = content / 'fixture.observations.json'
            with patch.object(common, 'WEB', web), self.assertRaisesRegex(
                    ValueError, 'Canonical observation output must end in'):
                common.write_observations(path, {'frames': []})
            self.assertFalse(path.exists())




class HistoricalObservationNamespaceTests(unittest.TestCase):
    scripts = ('observe-source.py', 'fit-source.py')

    def test_clis_refuse_checkout_outputs_without_consuming_runtime_inputs_or_overwriting(self):
        original = common.load_historical_observations('NAsM30MAHLg')
        with tempfile.TemporaryDirectory() as temporary, \
                tempfile.TemporaryDirectory(dir=HERE.parent / 'public') as public, \
                tempfile.TemporaryDirectory(dir=HERE.parent / 'src') as source, \
                tempfile.TemporaryDirectory(dir=HERE.parent.parent / 'cad') as cad, \
                tempfile.TemporaryDirectory(dir=HERE.parent.parent) as checkout:
            root = Path(temporary)
            observations = root / 'historical.json'
            observations.write_text(json.dumps(original))
            alias = root / 'checkout-alias'
            alias.symlink_to(HERE.parent.parent, target_is_directory=True)
            destinations = (Path(public) / 'receipt.json', Path(source) / 'receipt.json',
                            Path(checkout) / 'receipt.json', Path(cad) / 'receipt.json',
                            alias / Path(checkout).name / 'receipt.json')
            for filename in self.scripts:
                arguments = (
                    ['--observations', str(observations), '--source', str(root / 'missing.mp4')]
                    if filename == 'observe-source.py'
                    else [str(observations), '--inventory', str(root / 'missing.json')]
                )
                for destination in destinations:
                    with self.subTest(script=filename, destination=destination):
                        destination.write_bytes(b'original receipt must survive')
                        result = subprocess.run(
                            [sys.executable, str(HERE / filename), *arguments,
                             '--historical-diagnostic', '--output', str(destination)],
                            capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('require private .vite/verification-output', result.stderr)
                        self.assertNotIn('FileNotFoundError', result.stderr)
                        self.assertEqual(destination.read_bytes(), b'original receipt must survive')

    def test_historical_outputs_use_resolved_temp_roots_excluding_the_whole_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            web = root / 'checkout/web'
            private = web / '.vite/verification-output'
            private.mkdir(parents=True)
            external = root / 'external'
            external.mkdir()
            checkout_alias = root / 'checkout-alias'
            checkout_alias.symlink_to(web.parent, target_is_directory=True)
            temp_alias = root / 'temp-alias'
            temp_alias.symlink_to(root, target_is_directory=True)
            external_alias = root / 'external-alias'
            external_alias.symlink_to(external, target_is_directory=True)
            private_escape = private / 'escape'
            private_escape.symlink_to(external, target_is_directory=True)

            def temporary_roots(value):
                return temp_alias if str(value) in ('/tmp', '/var/tmp') else Path(value)

            module = load_script('fresh-source-observations.py', 'observation_namespace')
            with patch.object(module, 'WEB', web), \
                    patch.object(module, 'Path', temporary_roots):
                for destination in (private / 'receipt.json', external / 'receipt.json',
                                    external_alias / 'receipt.json'):
                    module.check_namespace(destination, historical_diagnostic=True, output=True)
                for destination in (web / 'public/receipt.json', web / 'src/receipt.json',
                                    web.parent / 'receipt.json', web.parent / 'cad/receipt.json',
                                    checkout_alias / 'cad/receipt.json',
                                    private_escape / 'receipt.json',
                                    checkout_alias / 'web/.vite/verification-output/escape/receipt.json'):
                    with self.subTest(destination=destination), self.assertRaises(ValueError):
                        module.check_namespace(destination, historical_diagnostic=True, output=True)
                # The allowlist is output-only: historical diagnostic inputs
                # remain readable, while current gzip rules stay intact.
                module.check_namespace(web / 'content/original.json', historical_diagnostic=True)
                module.check_namespace(web / 'public/original.json', historical_diagnostic=True)
                module.check_namespace(web / 'public/current.json.gz', output=True)
                with self.assertRaises(ValueError):
                    module.check_namespace(external / 'current.json', output=True)
                with self.assertRaises(ValueError):
                    module.check_namespace(
                        web / 'content/v39-source/NAsM30MAHLg.observations.json.gz',
                        historical_diagnostic=True)

                private_escape.unlink()
                private.rmdir()
                for target in (web / 'public', web / 'src', external):
                    private.symlink_to(target, target_is_directory=True)
                    for destination in (private / 'receipt.json',
                                        checkout_alias / 'web/.vite/verification-output/receipt.json'):
                        with self.subTest(target=target, destination=destination), \
                                self.assertRaises(ValueError):
                            module.check_namespace(destination, historical_diagnostic=True, output=True)
                    private.unlink()


class HistoricalDiagnosticOutputBoundaryTests(unittest.TestCase):
    scripts = ('NAsM30MAHLg-calibrate-static.py',
               'generate-analysis-bank-source-controls.py',
               'generate-spin-source-controls.py',
               '6dW6VYXp9HM-visible-crank-extract.py')

    def test_clis_refuse_published_repository_and_symlink_outputs_before_write(self):
        public = HERE.parent / 'public'
        if not public.exists():
            public.mkdir()
            self.addCleanup(public.rmdir)
        private = HERE.parent / '.vite/verification-output'
        private.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=HERE.parent / 'public') as published, \
                tempfile.TemporaryDirectory(dir=HERE) as tracked, \
                tempfile.TemporaryDirectory(dir=HERE.parent.parent) as repository, \
                tempfile.TemporaryDirectory() as temporary, \
                tempfile.TemporaryDirectory(dir=private) as private_directory:
            public_path = Path(published) / 'receipt.json'
            tracked_path = Path(tracked) / 'receipt.json'
            escape = Path(temporary) / 'escape'
            escape.symlink_to(Path(published), target_is_directory=True)
            private_escape = Path(private_directory) / 'escape'
            private_escape.symlink_to(Path(temporary), target_is_directory=True)
            for filename in self.scripts:
                diagnostic = ([] if filename == '6dW6VYXp9HM-visible-crank-extract.py'
                              else ['--historical-diagnostic'])
                for destination in (public_path, tracked_path,
                                    Path(repository) / 'receipt.json',
                                    escape / 'receipt.json',
                                    private_escape / 'receipt.json'):
                    with self.subTest(script=filename, destination=destination):
                        destination.write_bytes(b'original destination must survive')
                        result = subprocess.run(
                            [sys.executable, str(HERE / filename), *diagnostic,
                             '--output', str(destination)],
                            text=True, capture_output=True)
                        self.assertEqual(result.returncode, 2, result.stderr)
                        self.assertIn('require private .vite/verification-output', result.stderr)
                        self.assertEqual(destination.read_bytes(),
                                         b'original destination must survive')
                        destination.unlink()

    def test_declared_content_alias_to_external_temp_is_refused_before_any_write(self):
        # Resolving into /tmp is not permission to write through a declared
        # published namespace. Each real CLI must refuse before touching inputs.
        with tempfile.TemporaryDirectory(dir=HERE.parent / 'content') as content, \
                tempfile.TemporaryDirectory() as temporary:
            external = Path(temporary)
            alias = Path(content) / 'external'
            alias.symlink_to(external, target_is_directory=True)
            destination = alias / 'receipt.json'
            original = b'original external receipt must survive'
            destination.write_bytes(original)
            for filename in self.scripts:
                diagnostic = ([] if filename == '6dW6VYXp9HM-visible-crank-extract.py'
                              else ['--historical-diagnostic'])
                with self.subTest(script=filename):
                    result = subprocess.run(
                        [sys.executable, str(HERE / filename), *diagnostic,
                         '--output', str(destination)], text=True, capture_output=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn('filesystem aliases', result.stderr)
                    self.assertNotIn('FileNotFoundError', result.stderr)
                    self.assertEqual(destination.read_bytes(), original)
                    self.assertEqual(sorted(path.name for path in external.iterdir()), ['receipt.json'])

    def test_analysis_cli_writes_original_historical_diagnostic_to_external_temporary_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'diagnostic'
            target.mkdir()
            alias = Path(temporary) / 'temporary-alias'
            alias.symlink_to(target, target_is_directory=True)
            destination = alias / 'receipt.json'
            result = subprocess.run(
                [sys.executable, str(HERE / 'generate-analysis-bank-source-controls.py'),
                 '--historical-diagnostic', '--output', str(destination)],
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(destination.read_text())
            self.assertEqual(packet['kind'], 'historical-source-track-receipt')
            self.assertIs(packet['historicalDiagnostic'], True)
            self.assertIs(packet['publishable'], False)
            self.assertIs(packet['productionIntegrated'], False)
            original = common.load_historical_observations('6dW6VYXp9HM')
            self.assertEqual(packet['source'], original['source'])
            self.assertEqual(packet['model'], original['model'])
            ledger = json.loads((HERE.parent / 'content/canonical-native/'
                                 'analysis-recovery-calibration-evidence/'
                                 'augmented-face-frozen-check/interior-cap-check-ledger.json').read_text())
            self.assertEqual(packet['sourceMeasurementCounts']['independentMeasuredChecks'],
                             ledger['counts']['measured'])
            self.assertEqual(packet['sourceMeasurementCounts']['unresolvedChecksPreserved'],
                             ledger['counts']['unresolved'])


class HistoricalReceiptBoundaryTests(unittest.TestCase):
    def test_synthesis_receipt_reuses_instance_without_changing_retained_numbers_or_counts(self):
        generator = historical_synthesis_generator()
        original = copy.deepcopy(generator.data)
        framing = copy.deepcopy(generator.framing_observations)
        first = generator.revalidate_receipt()
        for key in first['evidence']['synthesisCoarseFraming']['shots'].values():
            self.assertGreater(key['eligibleViewCount'], 0)
            self.assertEqual(key['appliedViewCount'], key['eligibleViewCount'])
            self.assertGreater(key['appliedSeedExposureCount'], 0)
        self.assertGreater(first['evidence']['synthesisWheelFraming']['appliedViewCount'], 0)
        second = generator.revalidate_receipt()
        # Full equality includes every retained camera/input and per-replay count,
        # not just the receipt label or a fresh-instance reconstruction.
        self.assertEqual(first, second)
        self.assertEqual(generator.data, original)
        self.assertEqual(generator.framing_observations, framing)
        with self.assertRaisesRegex(ValueError, 'cannot build an ordinary source track'):
            generator.build()

    def test_reused_synthesis_receipt_still_refuses_retained_framing_numeric_mutation(self):
        generator = historical_synthesis_generator()
        generator.revalidate_receipt()
        original = copy.deepcopy(generator.synthesis_coarse_framing)
        for mutation in ('cone-fov', 'cam-position', 'focal-scale', 'native-fit', 'source-clock'):
            with self.subTest(mutation=mutation):
                generator.synthesis_coarse_framing = copy.deepcopy(original)
                cone = generator.synthesis_coarse_framing['shots']['cone-overview']
                cam = generator.synthesis_coarse_framing['shots']['cam-rod']
                if mutation == 'cone-fov':
                    cone['chosenCamera']['verticalFovDegrees'] += 0.01
                elif mutation == 'cam-position':
                    cam['chosenCamera']['positionMetres'][0] += 0.001
                elif mutation == 'focal-scale':
                    cone['positiveFocalScale'] += 0.01
                elif mutation == 'native-fit':
                    cone['objectiveFITs'][0]['nativePixels'][0] += 1
                else:
                    cone['decodedTimeSeconds'] += 0.001
                with self.assertRaisesRegex(ValueError, 'Synthesis retained framing numerical association changed'):
                    generator.revalidate_receipt()

    def test_both_receipt_routes_recheck_archive_math_after_a_successful_receipt(self):
        path = 'web/src/mechanics.ts'
        for video_id, mutation in (('6dW6VYXp9HM', 'missing'), ('8KmVDxkia_w', 'changed')):
            with self.subTest(video=video_id, mutation=mutation), historical_archive_fixture() as (root, web):
                generator = camera_tracks.HistoricalReceiptRevalidator(video_id)
                receipt = generator.revalidate_receipt()
                self.assertEqual(receipt['kind'], 'historical-source-track-receipt')
                sha = (generator.automatic_motion['diagnostics']['nativeForwardSmoke']['nativeMathSha256'][path]
                       if generator.analysis else generator.synthesis_automatic_motion['packet']['generationDependencies'][path]['sha256'])
                archive = web / 'content/canonical-native/historical-code' / sha / Path(path).name
                original = archive.read_bytes()
                if mutation == 'missing':
                    archive.unlink()
                else:
                    archive.write_bytes(original + b'\n')
                self.assertEqual((root / path).read_bytes(), original)
                with self.assertRaises(ValueError):
                    generator.revalidate_receipt()
                with self.assertRaises(ValueError):
                    camera_tracks.HistoricalReceiptRevalidator(video_id)

    def test_historical_analysis_receipt_rechecks_consumed_numeric_inputs(self):
        for mutation in ('native-bounds', 'candidate-input', 'automatic-drive', 'bank-pixel',
                         'held-camera', 'visible-drive', 'visible-fixed-input', 'observed-clock'):
            with self.subTest(mutation=mutation):
                receipt = camera_tracks.HistoricalReceiptRevalidator('6dW6VYXp9HM')
                if mutation == 'native-bounds':
                    receipt.parts[0]['rigidWorldBoundsM'][0][0] += 0.001
                elif mutation == 'candidate-input':
                    receipt.candidate['frames'][0]['chosenInput']['crankTurns'] += 0.001
                elif mutation == 'automatic-drive':
                    receipt.automatic_motion['frames'][80]['crankTurns'] += 0.00001
                elif mutation == 'bank-pixel':
                    receipt.bank_controls['frames'][0]['landmarks'][0]['pixel'][0] += 1
                elif mutation == 'held-camera':
                    receipt.analysis_held_camera['camera']['verticalFovDegrees'] += 0.001
                elif mutation == 'visible-drive':
                    receipt.visible_crank_motion['frames'][80]['relativeCrankTurns'] += 0.00001
                elif mutation == 'observed-clock':
                    receipt.data['frames'][0]['timeSeconds'] += 0.01
                else:
                    receipt.visible_crank_fixed_input['setup']['coneSwingRad'] += 0.001
                with self.assertRaises(ValueError):
                    receipt.revalidate_receipt()

    def test_relabelled_current_inputs_cannot_reuse_historical_gpu_readbacks(self):
        generator = historical_synthesis_generator()
        current = camera_tracks.common.load_approved_model_source()
        # Negative tampering fixture only. Original pixels, bounds and GPU
        # readbacks have not changed and cannot become current by new labels.
        generator.data['model'] = copy.deepcopy(current)
        generator.framing_observations['model'] = copy.deepcopy(current)
        generator.native['modelSha256'] = current['sha256']
        for build_packet in (generator.synthesis_coarse_framing_packet,
                             generator.synthesis_wheel_framing_packet):
            with self.subTest(packet=build_packet.__name__), self.assertRaisesRegex(
                    ValueError, 'Retained framing GPU evidence targets a different native source'):
                build_packet()

    def test_historical_receipt_route_never_builds_or_publishes_current_track(self):
        for video_id in ('6dW6VYXp9HM', '8KmVDxkia_w'):
            with self.subTest(video=video_id):
                generator = camera_tracks.HistoricalReceiptRevalidator(video_id)
                with self.assertRaises(ValueError):
                    generator.build()
                receipt = generator.revalidate_receipt()
                self.assertEqual(receipt['kind'], 'historical-source-track-receipt')
                self.assertEqual(receipt['source'], generator.data['source'])
                self.assertEqual(receipt['model'], generator.data['model'])
                self.assertEqual(receipt['model']['sha256'], camera_tracks.ANALYSIS_MODEL_SHA256)
                for publish in (camera_tracks.common.prepare_track, camera_tracks.common.write_track):
                    with self.assertRaises(ValueError):
                        publish(receipt)
                receipt['kind'] = 'compact-source-track'
                with self.assertRaises(ValueError):
                    camera_tracks.common.prepare_track(receipt)


class HalfOpenCutSelectionTests(unittest.TestCase):
    def fixture(self, cut, requested, decoded):
        def frame(shot_id, time, pts, index):
            return {
                'shotId': shot_id, 'classification': 'machine',
                'timeSeconds': time, 'decodedTimeSeconds': pts,
                'decodedFrameIndex': index,
                'sourceImage': {
                    'frameIndex': index, 'sourceSha256': 'a' * 64,
                    'pixelFormat': 'gray8', 'sha256Gray8': f'{index:064x}',
                    'width': 1920, 'height': 1080},
                'views': [{'id': 'main', 'presentation': 'native',
                           'rectSourcePixels': [0, 0, 1920, 1080]}],
                'landmarks': [{'anchorId': 'support', 'viewId': 'main',
                               'status': 'observed', 'role': 'check',
                               'pixel': [120.5 + index, 340.25], 'uncertaintyPx': 0.5}],
            }

        return {
            'kind': 'current-source-observations',
            # No fps: fresh exposure identity must not be inferred from a rate.
            'source': {'durationSeconds': cut + 1.5, 'sha256': 'a' * 64,
                       'width': 1920, 'height': 1080},
            'shots': [
                {'id': 'outgoing', 'startSeconds': 0, 'endSeconds': cut,
                 'classification': 'machine', 'hasCorrespondingMachine': True},
                {'id': 'incoming', 'startSeconds': cut, 'endSeconds': cut + 1.5,
                 'classification': 'machine', 'hasCorrespondingMachine': True}],
            'coverage': {'changeTimesSeconds': [requested, cut - 0.125]},
            'frames': [
                frame('outgoing', 0, 0, 0),
                frame('outgoing', cut - 0.125, cut - 0.125, 1),
                # A genuinely incoming decoded exposure cannot be relabeled as
                # outgoing just because its authored request precedes the cut.
                frame('outgoing', cut - 0.01, decoded, 2),
                frame('incoming', cut + 0.01, decoded, 3),
                frame('incoming', cut + 1, cut + 1, 4)],
        }

    def test_adjacent_derived_requests_use_only_strict_incoming_exposures(self):
        cuts = (96.721625, 193.568375, 338.8385, 532.532,
                628.628, 773.898125, 967.591625)
        for cut in cuts:
            for request_direction in (-math.inf, math.inf):
                for decoded in (cut, math.nextafter(cut, math.inf)):
                    with self.subTest(cut=cut, request=request_direction, pts=decoded):
                        requested = math.nextafter(cut, request_direction)
                        data = self.fixture(cut, requested, decoded)
                        original = copy.deepcopy(data)
                        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
                        source = original['frames'][3]
                        for time in (cut, requested):
                            self.assertEqual(rows[time]['shotId'], 'incoming')
                            self.assertEqual(rows[time]['decodedTimeSeconds'], decoded)
                            self.assertEqual(rows[time]['retainedObservationTimeSeconds'],
                                             source['timeSeconds'])
                            self.assertEqual(rows[time]['sourceImage'], source['sourceImage'])
                            self.assertEqual(rows[time]['landmarks'], source['landmarks'])
                            self.assertEqual(rows[time]['views'], source['views'])
                            self.assertNotIn('sourceSampleUnavailable', rows[time])
                        self.assertEqual(rows[cut - 0.125], original['frames'][1])
                        self.assertFalse(any(row.get('decodedFrameIndex') == 2
                                             for row in rows.values()))
                        self.assertEqual(data['frames'], original['frames'])
                        self.assertEqual(data['shots'], original['shots'])
                        self.assertEqual(data['coverage'], original['coverage'])
                        self.assertEqual(data['samplingDiagnostics']['excludedCrossCutObservations'],
                                         [{'shotId': 'outgoing', 'timeSeconds': cut - 0.01,
                                           'decodedTimeSeconds': decoded}])

    def test_exact_authored_predecessor_keeps_its_outgoing_exposure(self):
        cut = 4.25
        before = math.nextafter(cut, -math.inf)
        data = self.fixture(cut, before, cut)
        data['frames'][1]['timeSeconds'] = before
        data['frames'][1]['decodedTimeSeconds'] = before
        original = copy.deepcopy(data)
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        self.assertEqual(rows[before], original['frames'][1])
        self.assertEqual(rows[cut]['shotId'], 'incoming')
        self.assertEqual(rows[cut]['decodedTimeSeconds'], cut)
        self.assertEqual(data['frames'], original['frames'])
        self.assertEqual(data['shots'], original['shots'])

    def test_extra_outgoing_predecessor_survives_a_nearby_incoming_cut_key(self):
        cut = 4.25
        before = math.nextafter(cut, -math.inf)
        # Only the incoming cut is required. The predecessor must survive the
        # separate sparse-extra endpoint pass, not an authored coverage request.
        data = self.fixture(cut, cut, cut)
        data['frames'][1]['timeSeconds'] = before
        data['frames'][1]['decodedTimeSeconds'] = before
        original = copy.deepcopy(data)
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        self.assertEqual(rows[before], original['frames'][1])
        self.assertEqual(rows[cut]['shotId'], 'incoming')
        self.assertEqual(rows[cut]['decodedTimeSeconds'], cut)
        self.assertEqual(rows[cut]['sourceImage'], original['frames'][3]['sourceImage'])
        self.assertEqual(data['frames'], original['frames'])
        self.assertEqual(data['coverage'], original['coverage'])

    def test_nearby_extra_within_the_same_shot_keeps_existing_sampling(self):
        cut = 4.25
        extra = math.nextafter(5.0, math.inf)
        data = self.fixture(cut, cut, cut)
        data['frames'][-1]['timeSeconds'] = extra
        data['frames'][-1]['decodedTimeSeconds'] = 5.0
        source = copy.deepcopy(data['frames'][-1])
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        self.assertNotIn(extra, rows)
        self.assertEqual(rows[5.0]['shotId'], 'incoming')
        self.assertEqual(rows[5.0]['decodedTimeSeconds'], source['decodedTimeSeconds'])
        self.assertEqual(rows[5.0]['sourceImage'], source['sourceImage'])

    def test_pre_cut_native_pts_cannot_supply_a_derived_incoming_request(self):
        cut = 4.25
        before = math.nextafter(cut, -math.inf)
        data = self.fixture(cut, before, before)
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        for time in (cut, before):
            self.assertEqual(rows[time]['shotId'], 'incoming')
            self.assertTrue(rows[time]['sourceSampleUnavailable'])
            self.assertIsNone(rows[time]['decodedTimeSeconds'])
        self.assertEqual(rows[cut - 0.01]['shotId'], 'outgoing')
        self.assertEqual(rows[cut - 0.01]['decodedTimeSeconds'], before)
        self.assertEqual(data['samplingDiagnostics']['excludedCrossCutObservations'],
                         [{'shotId': 'incoming', 'timeSeconds': cut + 0.01,
                           'decodedTimeSeconds': before}])

    def test_two_float_steps_before_cut_remains_an_outgoing_exposure(self):
        cut = 4.25
        before = math.nextafter(math.nextafter(cut, -math.inf), -math.inf)
        data = self.fixture(cut, cut, cut)
        data['coverage']['changeTimesSeconds'].append(before)
        data['frames'][1]['timeSeconds'] = before
        data['frames'][1]['decodedTimeSeconds'] = before
        original = copy.deepcopy(data)
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        self.assertEqual(rows[before], original['frames'][1])
        self.assertEqual(rows[cut]['shotId'], 'incoming')
        self.assertEqual(rows[cut]['decodedTimeSeconds'], cut)
        self.assertEqual(data['frames'], original['frames'])
        self.assertEqual(data['shots'], original['shots'])

    def test_real_pre_cut_and_missing_same_shot_gap_do_not_borrow_outgoing_exposure(self):
        cut = 4.25
        requested = math.nextafter(cut, -math.inf)
        data = self.fixture(cut, requested, cut + 0.75)
        # Only actual incoming observations 0.75s and 1s after the cut remain;
        # the real outgoing exposure 0.125s before it is closer but ineligible.
        data['frames'] = [row for row in data['frames'] if row['decodedFrameIndex'] != 2]
        original = copy.deepcopy(data)
        rows = {row['timeSeconds']: row for row in common.selected_frames(data)}
        self.assertEqual(rows[cut - 0.125], original['frames'][1])
        for time in (cut, requested):
            self.assertEqual(rows[time]['shotId'], 'incoming')
            self.assertTrue(rows[time]['sourceSampleUnavailable'])
            self.assertIsNone(rows[time]['decodedTimeSeconds'])
            self.assertEqual(rows[time]['landmarks'], [])
            self.assertEqual(rows[time]['views'], [])
            self.assertEqual(rows[time]['unavailable'], [{
                'reason': 'No retained same-shot decoded source observation within 0.5s.'}])
        self.assertEqual(data['frames'], original['frames'])
        self.assertEqual(data['shots'], original['shots'])
        self.assertEqual(data['coverage'], original['coverage'])


class ExactExposureLandmarkTests(unittest.TestCase):
    def test_gray8_preserves_original_observed_check(self):
        data = exact_exposure()
        originals = copy.deepcopy(data['frames'])
        result = retain(data)
        self.assertEqual(result['landmarks'], originals[1]['landmarks'])
        self.assertEqual(data['frames'], originals)

    def test_different_hash_pts_or_layout_cannot_supply_check(self):
        for mismatch in ('hash', 'pts', 'layout'):
            with self.subTest(mismatch=mismatch):
                data = exact_exposure()
                donor = data['frames'][1]
                if mismatch == 'hash':
                    donor['sourceImage']['sha256Gray8'] = 'c' * 64
                elif mismatch == 'pts':
                    donor['decodedTimeSeconds'] = 1.00001
                else:
                    donor['views'] = [{'id': 'main', 'rectSourcePixels': [0, 0, 960, 1080]}]
                self.assertEqual(retain(data)['landmarks'], [])

    def test_opposite_format_with_equal_hash_cannot_supply_check(self):
        data = exact_exposure()
        donor_image = data['frames'][1]['sourceImage']
        donor_image['pixelFormat'] = 'bgr8'
        donor_image['sha256Bgr8'] = donor_image['sha256Gray8']
        self.assertEqual(retain(data)['landmarks'], [])

    def test_contradictory_same_view_anchor_rejects(self):
        data = exact_exposure()
        data['frames'][0]['landmarks'] = copy.deepcopy(data['frames'][1]['landmarks'])
        # Explicit main and legacy unscoped main refer to the same source view.
        data['frames'][1]['landmarks'][0].update(viewId='main', pixel=[121, 340])
        with self.assertRaises(ValueError):
            retain(data)

    def test_ambiguous_selected_declaration_diagnosed_once(self):
        for use_original_object in (True, False):
            with self.subTest(use_original_object=use_original_object):
                data = exact_exposure()
                ambiguous = {'anchorId': 'ambiguous', 'viewId': 'missing',
                             'status': 'observed', 'pixel': [10, 20], 'role': 'check'}
                data['frames'][0]['landmarks'] = [ambiguous]
                selected = data['frames'][0] if use_original_object else copy.deepcopy(data['frames'][0])
                result = retain(data, selected)
                diagnostics = data['samplingDiagnostics']['exactExposureAliasLandmarks']
                ambiguity = [row for row in diagnostics['unavailable']
                             if row.get('anchorId') == 'ambiguous']
                self.assertEqual(len(ambiguity), 1)
                self.assertEqual(result['landmarks'], [ambiguous, *data['frames'][1]['landmarks']])



class ChosenCameraNativeClockTests(unittest.TestCase):
    def fixture(self, track_schema):
        first, last = 623, 637
        rate = 24000 / 1001
        shot = {'id': 'presenter-to-spin', 'startSeconds': 25.984291667,
                'endSeconds': 26.609916667,
                ('nativeStartFrame' if track_schema else 'startDecodedFrameIndex'): first}
        rows = [{'shotId': shot['id'], 'decodedTimeSeconds': index / rate,
                 ('sourceFrameIndex' if track_schema else 'decodedFrameIndex'): index,
                 'camera': None, 'views': [{'id': 'main', 'camera': None,
                    'rectSourcePixels': [0, 0, 1920, 1080], 'presentation': 'native'}]}
                for index in range(first, last + 1)]
        data = {'source': {'sha256': 'a' * 64, 'width': 1920, 'height': 1080,
                          'fps': {'numerator': 24000, 'denominator': 1001}},
                'shots': [shot], 'frames': rows}
        permission = {'shotId': shot['id'], 'viewId': 'main', 'componentFamily': 'whole',
                      'cameraProvenanceKind': 'source-informed-framing',
                      'measurementStatus': 'unmeasured', 'cameraInterpolation': 'continuous-shot',
                      'cameraInterpolationEvidence': 'Chosen single-body continuous reframing.',
                      'cameraContinuityFamily': 'chosen:presenter-to-spin:main',
                      'startSeconds': shot['startSeconds'], 'endSeconds': shot['endSeconds'],
                      'startDecodedFrameIndex': first, 'lastDecodedFrameIndex': last}
        packet = {'schemaVersion': 1, 'videoId': '8KmVDxkia_w',
                  'sourceSha256': data['source']['sha256'], 'permissions': [permission]}
        return data, packet

    def load_permission(self, data, packet):
        generator = camera_tracks.HistoricalReceiptRevalidator.__new__(camera_tracks.HistoricalReceiptRevalidator)
        generator.data = data
        generator.shots = {shot['id']: shot for shot in data['shots']}
        return generator.chosen_camera_continuity_packet('8KmVDxkia_w', packet)

    def test_both_native_schemas_accept_decimal_cut_rounding_without_mutation(self):
        for track_schema in (False, True):
            with self.subTest(track_schema=track_schema):
                data, packet = self.fixture(track_schema)
                original = copy.deepcopy(data)
                permissions = self.load_permission(data, packet)
                self.assertEqual(permissions[('presenter-to-spin', 'main')], packet['permissions'][0])
                self.assertEqual(data, original)

    def test_missing_conflicting_or_off_clock_native_evidence_is_refused(self):
        for mismatch in ('missing-row', 'shot-index', 'row-index', 'nan-pts',
                         'off-clock', 'frame-camera', 'view-camera', 'layout', 'presentation'):
            with self.subTest(mismatch=mismatch):
                data, packet = self.fixture(True)
                row = data['frames'][0]
                if mismatch == 'missing-row':
                    data['frames'].pop(7)
                elif mismatch == 'shot-index':
                    data['shots'][0]['startDecodedFrameIndex'] = 624
                elif mismatch == 'row-index':
                    row['decodedFrameIndex'] = 624
                elif mismatch == 'nan-pts':
                    row['decodedTimeSeconds'] = float('nan')
                elif mismatch == 'off-clock':
                    data['frames'][7]['decodedTimeSeconds'] += 0.01
                elif mismatch == 'frame-camera':
                    row['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'view-camera':
                    row['views'][0]['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'presentation':
                    row['views'][0]['presentation'] = 'horizontal-mirror'
                else:
                    row['views'][0]['rectSourcePixels'] = [0, 0, 960, 1080]
                with self.assertRaises(ValueError):
                    self.load_permission(data, packet)


class PresenterOriginalViewTests(unittest.TestCase):
    def source(self, legacy_views=True):
        # Exercise the real retained producer input and constructor, including
        # the outgoing/incoming null-camera layout accepted before normalization.
        data = camera_tracks.common.load_historical_observations('8KmVDxkia_w', prefer_track=True)
        if not legacy_views:
            return data
        for frame in data['frames']:
            if frame['shotId'] == 'presenter-to-spin':
                view = {'rectSourcePixels': [0, 0, data['source']['width'], data['source']['height']],
                        'presentation': 'native', 'camera': None}
                frame['views'] = [dict(view, id=name) for name in ('outgoing', 'incoming')]
        return data

    def construct(self, data):
        with patch.object(camera_tracks.common, 'load_historical_observations', return_value=data):
            return historical_synthesis_generator()

    def test_existing_retained_source_accepts_permission(self):
        generator = self.construct(self.source(legacy_views=False))
        self.assertIn(('presenter-to-spin', 'main'), generator.chosen_camera_permissions)

    def test_legacy_null_views_normalize_and_apply_permission_at_native_first_exposure(self):
        generator = self.construct(self.source())
        frame = next(frame for frame in generator.data['frames']
                     if frame['shotId'] == 'presenter-to-spin' and frame['sourceFrameIndex'] == 623)
        self.assertLess(frame['decodedTimeSeconds'], generator.shots[frame['shotId']]['startSeconds'])
        self.assertEqual([view['id'] for view in frame['views']], ['main'])
        track = {'frames': [{**frame, 'views': generator.views(frame)}]}
        generator.camera_metadata(track)
        permission = generator.chosen_camera_permissions[(frame['shotId'], 'main')]
        view = track['frames'][0]['views'][0]
        self.assertEqual(view['cameraInterpolation'], 'continuous-shot')
        self.assertEqual(view['cameraContinuityFamily'], permission['cameraContinuityFamily'])
        self.assertEqual(view['cameraProvenance']['kind'], 'source-informed-framing')

    def test_unsupported_original_views_are_refused_before_normalization(self):
        for mismatch in ('camera', 'rect', 'presentation', 'empty', 'missing', 'warp',
                         'resolved-warp', 'crossfade', 'unexpected-id', 'duplicate-id'):
            with self.subTest(mismatch=mismatch):
                data = self.source()
                frame = next(frame for frame in data['frames'] if frame['shotId'] == 'presenter-to-spin')
                view = frame['views'][1]
                if mismatch == 'camera':
                    view['camera'] = {'verticalFovDegrees': 30}
                elif mismatch == 'rect':
                    view['rectSourcePixels'] = [960, 0, 960, 1080]
                elif mismatch == 'presentation':
                    view['presentation'] = 'horizontal-mirror'
                elif mismatch == 'empty':
                    frame['views'] = []
                elif mismatch == 'missing':
                    frame.pop('views')
                elif mismatch in ('warp', 'resolved-warp'):
                    view['resolvedImagePlaneWarp' if mismatch == 'resolved-warp' else 'imagePlaneWarp'] = {
                        'kind': 'homography', 'unwarpedViewportPixels': [0, 0, 1920, 1080],
                        'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                elif mismatch == 'crossfade':
                    view['composite'] = {'mode': 'crossfade', 'groupId': 'body',
                                         'imageLayerId': 'incoming', 'opacity': 0.5}
                elif mismatch == 'unexpected-id':
                    view['id'] = 'unmapped-body'
                else:
                    frame['views'].append(copy.deepcopy(view))
                original = copy.deepcopy(frame.get('views'))
                with self.assertRaises(ValueError):
                    self.construct(data)
                self.assertEqual(frame.get('views'), original)

    def test_unrelated_original_source_views_remain_outside_permission_guard(self):
        data = self.source()
        frame = next(frame for frame in data['frames']
                     if frame['shotId'] != 'presenter-to-spin' and frame.get('views'))
        frame['views'][0]['rectSourcePixels'] = [0, 0, 960, 1080]
        original = copy.deepcopy(frame['views'])
        generator = self.construct(data)
        self.assertEqual(frame['views'], original)
        self.assertIn(('presenter-to-spin', 'main'), generator.chosen_camera_permissions)

    def test_presenter_without_selected_permission_keeps_existing_normalization(self):
        data = self.source()
        frame = next(frame for frame in data['frames'] if frame['shotId'] == 'presenter-to-spin')
        frame['views'][1]['rectSourcePixels'] = [960, 0, 960, 1080]
        packet = {'schemaVersion': 1, 'videoId': '8KmVDxkia_w',
                  'sourceSha256': data['source']['sha256'], 'permissions': []}
        permission_path = camera_tracks.WEB / 'content/canonical-native/8KmVDxkia_w.chosen-camera-continuity.json'
        read_text = Path.read_text

        def read_packet(path, *args, **kwargs):
            return json.dumps(packet) if path == permission_path else read_text(path, *args, **kwargs)

        with patch.object(Path, 'read_text', read_packet):
            generator = self.construct(data)
        self.assertEqual(generator.chosen_camera_permissions, {})
        self.assertEqual([view['id'] for view in frame['views']], ['main'])


class AnalysisAutomaticMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = camera_tracks.HistoricalReceiptRevalidator('6dW6VYXp9HM')
        cls.track = cls.generator.revalidate_receipt()
        # Fixtures stay beside these tests even when the actual producer is an
        # earlier git revision selected by SOURCE_GENERATOR_PATH.
        content = HERE.parent / 'content' / 'canonical-native'
        cls.packet = json.loads((content / '6dW6VYXp9HM.automatic-motion.json').read_text())
        cls.controls = json.loads((content / '6dW6VYXp9HM.motion-controls.json').read_text())
        cls.visible = json.loads((content / '6dW6VYXp9HM.visible-crank-motion.json').read_text())
        cls.gauge = json.loads((content / '6dW6VYXp9HM.visible-crank-gauge.json').read_text())

    def native_frame(self, index):
        return next(frame for frame in self.generator.data['frames']
                    if frame.get('decodedFrameIndex') == index
                    and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-9)

    def test_all_204_exact_native_keys_use_cumulative_drive_and_fixed_complete_input(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for authority in self.packet['frames']:
            with self.subTest(index=authority['frameIndex']):
                frame = generated[authority['timeSeconds']]
                original = self.native_frame(authority['frameIndex'])
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], authority['sourceImage'])
                self.assertEqual(frame['sourceImage'], original['sourceImage'])
                self.assertEqual(frame['shotId'], 'analysis-22')
                bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
                expected = copy.deepcopy(self.packet['fixedInput'])
                expected['crankTurns'] = authority['crankTurns']
                self.assertEqual(bank['input'], expected)
                original_view = next(view for view in original['views'] if view['id'] == 'bar-bank')
                self.assertEqual(bank['rectSourcePixels'], original_view['rectSourcePixels'])
                self.assertEqual(bank['presentation'], original_view['presentation'])
                self.assertEqual(bank['camera'],
                                 camera_tracks.common.compact_camera(self.generator.candidate['nativeCameraRecord']))
        self.assertEqual(generated[self.packet['frames'][0]['timeSeconds']]['views'][0]['input']['crankTurns'], 0)
        self.assertGreater(generated[self.packet['frames'][-1]['timeSeconds']]['views'][0]['input']['crankTurns'], 3)

    def test_exact_native_keys_preserve_all_raw_fit_check_pixels_and_nulls(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        fields = ('anchorId', 'viewId', 'role', 'pixel', 'status', 'method',
                  'uncertaintyPx', 'trackingEvidence', 'measurementEvidence')
        for control in self.generator.bank_controls['frames']:
            with self.subTest(index=control['decodedFrameIndex']):
                frame = generated[control['timeSeconds']]
                points = {(point['viewId'], point['anchorId']): point for point in frame['landmarks']}
                for point in control['landmarks']:
                    expected = {key: copy.deepcopy(point[key]) for key in fields if key in point}
                    self.assertEqual(points[(point['viewId'], point['anchorId'])], expected)
                unavailable = {(point['viewId'], point['anchorId']): point
                               for point in frame.get('unavailable', []) if 'anchorId' in point}
                for point in control['unavailable']:
                    key = (point['viewId'], point['anchorId'])
                    self.assertNotIn(key, points)
                    self.assertEqual(unavailable[key]['reason'], point['reason'])
        anchors = {anchor['id']: anchor for anchor in self.track['anchors']}
        for anchor in self.generator.bank_controls['anchors']:
            self.assertEqual(anchors[anchor['id']]['partPath'], anchor['partPath'])
            self.assertEqual(anchors[anchor['id']]['partLocalMetres'], anchor['partLocalMetres'])

    def test_actual_source_seconds_interpolate_cumulative_drive_not_phase_or_label(self):
        left, right = self.packet['frames'][34:36]
        frame = copy.deepcopy(self.native_frame(left['frameIndex']))
        frame.pop('decodedFrameIndex')
        frame.pop('sourceImage')
        frame['decodedTimeSeconds'] = left['timeSeconds'] + 0.25 * (right['timeSeconds'] - left['timeSeconds'])
        frame['timeSeconds'] = 117
        view = frame['views'][0]
        value, _ = self.generator.input(frame, 'bar', view)
        self.assertAlmostEqual(value['crankTurns'],
                               left['crankTurns'] + 0.25 * (right['crankTurns'] - left['crankTurns']), places=12)
        for field in ('amplitudes', 'phases', 'gearing', 'magnification', 'setup'):
            self.assertEqual(value[field], self.packet['fixedInput'][field])

    def test_integer_alias_retains_actual_exposure_drive_and_source_identity(self):
        frame = next(frame for frame in self.track['frames'] if frame['timeSeconds'] == 117)
        authority = next(row for row in self.packet['frames'] if row['frameIndex'] == 3506)
        self.assertEqual(frame['sourceImage'], authority['sourceImage'])
        self.assertAlmostEqual(frame['decodedTimeSeconds'], authority['timeSeconds'], places=12)
        bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
        self.assertEqual(bank['input']['crankTurns'], authority['crankTurns'])
        self.assertNotEqual(bank['input']['crankTurns'],
                            next(row for row in self.packet['frames'] if row['frameIndex'] == 3507)['crankTurns'])

    def test_wrong_shot_view_family_or_presentation_keeps_original_inverse_input(self):
        for boundary in ('shot', 'view', 'family', 'presentation', 'before', 'shot-end'):
            with self.subTest(boundary=boundary):
                frame = copy.deepcopy(self.native_frame(3450))
                view, family = frame['views'][0], 'bar'
                if boundary == 'shot':
                    frame['shotId'] = 'analysis-23'
                elif boundary == 'view':
                    view['id'] = 'main'
                elif boundary == 'family':
                    view['id'] = 'pen-inset'
                elif boundary == 'presentation':
                    view['presentation'] = 'native'
                elif boundary == 'before':
                    frame['decodedTimeSeconds'] = self.packet['interval']['startSeconds'] - 0.01
                else:
                    frame['decodedTimeSeconds'] = self.generator.shots['analysis-22']['endSeconds']
                family = self.generator.family(frame, view)
                time = frame['decodedTimeSeconds']
                snapshots = self.generator.analysis_snapshots
                first = snapshots[0]['sourceFrameIdentity']['timeSeconds']
                last = snapshots[-1]['sourceFrameIdentity']['timeSeconds']
                if family == 'bar' and first <= time <= last:
                    expected = min(snapshots, key=lambda row: abs(row['sourceFrameIdentity']['timeSeconds'] - time))
                else:
                    expected = snapshots[0] if time < first else snapshots[-1]
                rendered = next(row for row in self.generator.views(frame) if row['id'] == view['id'])
                self.assertEqual(rendered['input'], expected['chosenInput'])

    def test_endpoint_held_for_every_remaining_same_shot_key_without_source_image(self):
        end = self.packet['interval']['endSeconds']
        expected = copy.deepcopy(self.packet['fixedInput'])
        expected['crankTurns'] = self.packet['frames'][-1]['crankTurns']
        held = [frame for frame in self.track['frames']
                if frame['shotId'] == 'analysis-22' and frame['decodedTimeSeconds'] > end]
        for frame in held:
            bank = next(view for view in frame['views'] if view['id'] == 'bar-bank')
            self.assertEqual(bank['input'], expected)
        for index in (3580, 3730):
            original = self.native_frame(index)
            self.assertIsNone(original.get('sourceImage'))
            bank = next(view for view in self.generator.views(original) if view['id'] == 'bar-bank')
            self.assertEqual(bank['input'], expected)
        self.assertAlmostEqual(held[-1]['decodedTimeSeconds'], 3730 / (30000 / 1001), places=9)
        next_shot = self.native_frame(3731)
        for view in self.generator.views(next_shot):
            self.assertEqual(view['input'], self.generator.analysis_snapshots[-1]['chosenInput'])
        diagnostics = self.track['cpuDiagnostics']['analysisAutomaticMotion']
        self.assertEqual(diagnostics['domain']['measurementStatus'], 'conditional-source-fit')
        self.assertEqual(diagnostics['domain']['endSeconds'], end)
        self.assertEqual(diagnostics['endpointHold']['kind'], 'chosen-endpoint-hold')
        self.assertEqual(diagnostics['endpointHold']['measurementStatus'], 'unmeasured')
        self.assertEqual(diagnostics['endpointHold']['endSeconds'], self.generator.shots['analysis-22']['endSeconds'])
        self.assertFalse(diagnostics['stageAcceptance'])
        self.assertEqual(diagnostics['physicalCrankDirection'], 'unobservable')
        self.assertEqual(diagnostics['absolutePhysicalCrankPhase'], 'unobservable')

    def test_changed_or_missing_pinned_artifact_rejects_instead_of_falling_back(self):
        for target in (camera_tracks.AUTOMATIC_MOTION, camera_tracks.MOTION_CONTROLS):
            for missing in (False, True):
                with self.subTest(target=target, missing=missing), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for path in (camera_tracks.AUTOMATIC_MOTION, camera_tracks.MOTION_CONTROLS):
                        if path == target and missing:
                            continue
                        destination = root / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        data = (camera_tracks.ROOT / path).read_bytes()
                        destination.write_bytes(data + b' ' if path == target else data)
                    with patch.object(camera_tracks, 'ROOT', root), self.assertRaises(ValueError):
                        self.generator.analysis_automatic_motion_packet()

    def test_semantically_unsupported_native_authority_rejects(self):
        for mismatch in ('kind', 'source', 'model', 'fps', 'missing-frame', 'duplicate-frame',
                         'pts', 'nan-pts', 'image', 'source-image', 'native-math', 'camera',
                         'station', 'amplitudes', 'phases', 'setup', 'nonfinite-drive',
                         'backward-drive', 'physical-sign', 'stage-claim'):
            with self.subTest(mismatch=mismatch):
                packet, controls = copy.deepcopy(self.packet), copy.deepcopy(self.controls)
                generator = copy.copy(self.generator)
                if mismatch == 'kind':
                    packet['kind'] = 'chosen-generic-animation'
                elif mismatch == 'source':
                    packet['authority']['videoSha256'] = '0' * 64
                elif mismatch == 'model':
                    packet['authority']['nativeModelSha256'] = '0' * 64
                elif mismatch == 'fps':
                    generator.data = {**generator.data, 'source': {**generator.data['source'], 'fps': {'numerator': 30, 'denominator': 1}}}
                elif mismatch == 'missing-frame':
                    packet['frames'].pop(80)
                elif mismatch == 'duplicate-frame':
                    packet['frames'][80]['frameIndex'] = packet['frames'][79]['frameIndex']
                elif mismatch == 'pts':
                    packet['frames'][80]['timeSeconds'] += 0.001
                elif mismatch == 'nan-pts':
                    packet['frames'][80]['timeSeconds'] = float('nan')
                elif mismatch == 'image':
                    packet['frames'][80]['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'source-image':
                    index = packet['frames'][80]['frameIndex']
                    generator.data = {**generator.data, 'frames': [
                        {**frame, 'sourceImage': None} if frame.get('decodedFrameIndex') == index else frame
                        for frame in generator.data['frames']]}
                elif mismatch == 'native-math':
                    packet['diagnostics']['nativeForwardSmoke']['nativeMathSha256']['web/src/mechanics.ts'] = '0' * 64
                elif mismatch == 'camera':
                    controls['frozenCandidate']['nativeCameraRecord']['verticalFovDegrees'] += 1
                elif mismatch == 'station':
                    packet['stationCorrespondence'][0]['nativeStationIndex'] = 0
                elif mismatch == 'amplitudes':
                    packet['fixedInput']['amplitudes'].pop()
                elif mismatch == 'phases':
                    packet['fixedInput']['phases'][0] = float('nan')
                elif mismatch == 'setup':
                    packet['fixedInput']['setup']['coneSwingRad'] = 0.1
                elif mismatch == 'nonfinite-drive':
                    packet['frames'][80]['crankTurns'] = float('inf')
                elif mismatch == 'backward-drive':
                    packet['frames'][80]['crankTurns'] = -1
                elif mismatch == 'physical-sign':
                    packet['authority']['physicalCrankDirection'] = 'measured-positive'
                else:
                    packet['integration']['stageAcceptance'] = True
                with self.assertRaises(ValueError):
                    generator.validate_analysis_automatic_motion(packet, controls)

        proof_path = 'web/src/mechanics.ts'
        hashes = self.packet['diagnostics']['nativeForwardSmoke']['nativeMathSha256']
        for missing in (False, True):
            with self.subTest(historical_snapshot='missing' if missing else 'modified'), \
                    tempfile.TemporaryDirectory() as directory:
                web = Path(directory)
                for path, digest in hashes.items():
                    if path == proof_path and missing:
                        continue
                    target = web / 'content/canonical-native/historical-code' / digest / Path(path).name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    raw = common.historical_code_bytes(path, digest)
                    target.write_bytes(raw + b'\n' if path == proof_path else raw)
                reason = 'unavailable' if missing else 'changed'
                with patch.object(camera_tracks.common, 'WEB', web), \
                        self.assertRaisesRegex(ValueError, f'Historical producer snapshot {reason}: {proof_path}$'):
                    self.generator.validate_analysis_automatic_motion(self.packet, self.controls)

    def test_runtime_native_identity_or_camera_mismatch_cannot_borrow_fitted_drive(self):
        for mismatch in ('hash', 'pts', 'camera'):
            with self.subTest(mismatch=mismatch):
                frame = copy.deepcopy(self.native_frame(3450))
                view = frame['views'][0]
                if mismatch == 'hash':
                    frame['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'pts':
                    frame['decodedTimeSeconds'] += 0.001
                else:
                    view['camera'] = copy.deepcopy(self.generator.candidate['nativeCameraRecord'])
                    view['camera']['verticalFovDegrees'] += 1
                with self.assertRaises(ValueError):
                    self.generator.input(frame, 'bar', view)

    def test_all_207_visible_crank_native_keys_use_chosen_gauge_and_one_fixed_setup(self):
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        fixed = copy.deepcopy(self.generator.analysis_snapshots[0]['chosenInput'])
        fixed['setup']['driveCrankOffsetTurns'] = 0.7118017231396382
        for row in self.visible['frames']:
            with self.subTest(index=row['frameIndex']):
                original = self.native_frame(row['frameIndex'])
                expected = copy.deepcopy(fixed)
                expected['crankTurns'] = -row['relativeCrankTurns'] + 0.7118017231396382
                # Stable consumer API: old main must fail for its actual zero
                # drive, not a missing helper or a changed input signature.
                actual = next(view for view in self.generator.views(original) if view['id'] == 'main')
                self.assertEqual(actual['input'], expected)
                frame = generated[row['timeSeconds']]
                self.assertEqual(frame['shotId'], 'analysis-16')
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], {
                    'frameIndex': row['frameIndex'], 'pixelFormat': 'bgr8',
                    **{key: row['sourceImage'][key] for key in ('sourceSha256', 'sha256Bgr8', 'width', 'height')}})
                self.assertEqual(row['sourceImage']['pts'], 1001 * row['frameIndex'])
                self.assertEqual([view['id'] for view in frame['views']], ['main'])
                view = frame['views'][0]
                self.assertEqual(view['input'], expected)
                self.assertEqual(view['presentation'], 'native')
                self.assertEqual(view['rectSourcePixels'], [0, 0, 1920, 1080])
                self.assertEqual(view['camera'], self.gauge['cameraAssociation']['camera'])
        self.assertIsNone(self.visible['authority']['selectedNativeSign'])
        self.assertIsNone(self.visible['authority']['absoluteNativeHomeTurns'])

    def test_visible_crank_source_controls_and_original_observations_are_not_reclassified(self):
        raw = camera_tracks.common.load_historical_observations('6dW6VYXp9HM')
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for row in self.visible['frames']:
            frame = generated[row['timeSeconds']]
            original = next(frame for frame in raw['frames']
                            if frame.get('decodedFrameIndex') == row['frameIndex']
                            and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-9)
            self.assertEqual(frame['landmarks'], [
                {key: point[key] for key in ('anchorId', 'viewId', 'role', 'pixel', 'status', 'method',
                                            'uncertaintyPx', 'trackingEvidence', 'measurementEvidence') if key in point}
                for point in original['landmarks'] if point.get('status') == 'observed' and point.get('pixel') is not None])
            self.assertEqual(self.native_frame(row['frameIndex']).get('views'), original.get('views'))
            self.assertEqual(self.native_frame(row['frameIndex']).get('camera'), original.get('camera'))
            self.assertEqual(self.native_frame(row['frameIndex']).get('unavailable'), original.get('unavailable'))
            if original.get('sourceImage') is not None:
                self.assertEqual(frame['sourceImage'], original['sourceImage'])

    def test_visible_crank_pre_and_post_domain_hold_new_input_until_actual_cut(self):
        first, last = self.visible['frames'][0], self.visible['frames'][-1]
        first_input = copy.deepcopy(self.generator.analysis_snapshots[0]['chosenInput'])
        first_input['setup']['driveCrankOffsetTurns'] = 0.7118017231396382
        first_input['crankTurns'] = 0.7118017231396382
        last_input = copy.deepcopy(first_input)
        last_input['crankTurns'] = -last['relativeCrankTurns'] + 0.7118017231396382
        for frame in self.track['frames']:
            if frame['shotId'] != 'analysis-16':
                continue
            if frame['decodedTimeSeconds'] < first['timeSeconds']:
                self.assertEqual(frame['views'][0]['input'], first_input)
            elif frame['decodedTimeSeconds'] > last['timeSeconds']:
                self.assertEqual(frame['views'][0]['input'], last_input)
        for index, expected in ((2381, first_input), (2607, last_input)):
            frame = self.native_frame(index)
            rendered = next(view for view in self.generator.views(frame) if view['id'] == 'main')
            self.assertEqual(rendered['input'], expected)
        frame = self.native_frame(2608)
        for rendered in self.generator.views(frame):
            self.assertEqual(rendered['input'], self.generator.analysis_snapshots[0]['chosenInput'])

    def test_visible_crank_wrong_shot_view_presentation_or_family_keeps_legacy_input(self):
        for boundary in ('shot', 'view', 'presentation', 'family'):
            with self.subTest(boundary=boundary):
                frame = copy.deepcopy(self.native_frame(2450))
                view = camera_tracks.common.source_views(frame, self.generator.data)[0]
                frame['views'] = [view]
                if boundary == 'shot':
                    frame['shotId'] = 'analysis-17'
                elif boundary == 'view':
                    view['id'] = 'bar-bank'
                elif boundary == 'presentation':
                    view['presentation'] = 'horizontal-mirror'
                else:
                    view['id'] = 'pen-inset'
                rendered = next(row for row in self.generator.views(frame) if row['id'] == view['id'])
                self.assertEqual(rendered['input'], self.generator.analysis_snapshots[0]['chosenInput'])

    def test_visible_crank_interpolates_actual_source_time_and_retains_observed_bottom_noise(self):
        left, right = self.visible['frames'][55:57]
        frame = copy.deepcopy(self.native_frame(left['frameIndex']))
        frame.pop('decodedFrameIndex')
        frame.pop('sourceImage', None)
        frame['decodedTimeSeconds'] = left['timeSeconds'] + 0.25 * (right['timeSeconds'] - left['timeSeconds'])
        frame['timeSeconds'] = 86
        view = camera_tracks.common.source_views(frame, self.generator.data)[0]
        value, _ = self.generator.input(frame, 'cone', view)
        relative = left['relativeCrankTurns'] + 0.25 * (right['relativeCrankTurns'] - left['relativeCrankTurns'])
        self.assertAlmostEqual(value['crankTurns'], -relative + 0.7118017231396382, places=12)
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for row in self.visible['frames']:
            if row['frameIndex'] >= 2512:
                self.assertEqual(generated[row['timeSeconds']]['views'][0]['input']['crankTurns'],
                                 -row['relativeCrankTurns'] + 0.7118017231396382)

    def test_visible_crank_semantic_identity_and_unresolved_source_sign_are_required(self):
        for mismatch in ('missing-frame', 'frame-index', 'pts', 'hash', 'format', 'time',
                         'turns', 'selected-sign', 'home', 'phase-transfer', 'source-conflict'):
            with self.subTest(mismatch=mismatch):
                packet = copy.deepcopy(self.visible)
                generator = copy.copy(self.generator)
                row = packet['frames'][40]
                if mismatch == 'missing-frame':
                    packet['frames'].pop(40)
                elif mismatch == 'frame-index':
                    row['frameIndex'] += 1
                elif mismatch == 'pts':
                    row['sourceImage']['pts'] += 1
                elif mismatch == 'hash':
                    row['sourceImage']['sha256Bgr8'] = 'not-a-hash'
                elif mismatch == 'format':
                    row['sourceImage']['format'] = 'gray8'
                elif mismatch == 'time':
                    row['timeSeconds'] += 0.001
                elif mismatch == 'turns':
                    row['relativeCrankTurns'] = float('nan')
                elif mismatch == 'selected-sign':
                    packet['authority']['selectedNativeSign'] = -1
                elif mismatch == 'home':
                    packet['authority']['absoluteNativeHomeTurns'] = 0.7118017231396382
                elif mismatch == 'phase-transfer':
                    packet['authority']['phaseTransferToOtherShots'] = True
                else:
                    generator.data = {**generator.data, 'frames': [
                        {**frame, 'sourceImage': {**frame['sourceImage'], 'sha256Bgr8': '0' * 64}}
                        if frame.get('decodedFrameIndex') == row['frameIndex'] else frame
                        for frame in generator.data['frames']]}
                with self.assertRaises(ValueError):
                    generator.validate_analysis_visible_crank(packet)

    def test_visible_crank_missing_legacy_images_gain_only_exact_authority_identities(self):
        data = camera_tracks.common.load_historical_observations('6dW6VYXp9HM')
        index = 2450
        originals = [copy.deepcopy(frame) for frame in data['frames'] if frame.get('decodedFrameIndex') == index]
        for frame in data['frames']:
            if frame.get('decodedFrameIndex') == index:
                frame.pop('sourceImage', None)
        with patch.object(camera_tracks.common, 'load_historical_observations', return_value=data):
            generator = camera_tracks.HistoricalReceiptRevalidator('6dW6VYXp9HM')
        authority = next(row for row in self.visible['frames'] if row['frameIndex'] == index)
        generated = [frame for frame in generator.data['frames'] if frame.get('decodedFrameIndex') == index]
        for before, after in zip(originals, generated):
            self.assertEqual(after['sourceImage'], camera_tracks.visible_crank_source_image(authority))
            self.assertEqual({key: value for key, value in after.items() if key != 'sourceImage'},
                             {key: value for key, value in before.items() if key != 'sourceImage'})

    def test_visible_crank_missing_or_corrupt_source_and_gauge_artifacts_refuse(self):
        paths = (camera_tracks.VISIBLE_CRANK_MOTION, camera_tracks.VISIBLE_CRANK_GAUGE)
        for target in paths:
            for missing in (False, True):
                with self.subTest(target=target, missing=missing), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for path in paths:
                        if path == target and missing:
                            continue
                        destination = root / path
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        data = (camera_tracks.ROOT / path).read_bytes()
                        destination.write_bytes(data + b' ' if path == target else data)
                    with patch.object(camera_tracks, 'ROOT', root), self.assertRaises(ValueError):
                        self.generator.analysis_visible_crank_packet()

    def test_visible_crank_gauge_cannot_promote_source_sign_or_change_camera_setup_math(self):
        for mismatch in ('native-sign', 'offset', 'lag', 'historical-sign', 'camera',
                         'phase', 'math', 'model', 'stage', 'source-sign', 'positive-control'):
            with self.subTest(mismatch=mismatch):
                gauge = copy.deepcopy(self.gauge)
                if mismatch == 'native-sign':
                    gauge['chosenGauge']['nativeSign'] = 1
                elif mismatch == 'offset':
                    gauge['chosenGauge']['shotLocalOffsetTurns'] = 0
                elif mismatch == 'lag':
                    gauge['chosenGauge']['driveCrankOffsetTurns'] = 0
                elif mismatch == 'historical-sign':
                    gauge['chosenGauge']['historicalNativeSignIdentified'] = True
                elif mismatch == 'camera':
                    gauge['cameraAssociation']['camera']['verticalFovDegrees'] += 1
                elif mismatch == 'phase':
                    gauge['baseChosenInput']['phases'][0] += 0.1
                elif mismatch == 'math':
                    gauge['nativeMathSha256']['web/src/mechanics.ts'] = '0' * 64
                elif mismatch == 'model':
                    gauge['modelSha256'] = '0' * 64
                elif mismatch == 'stage':
                    gauge['qualification']['stageAcceptance'] = True
                elif mismatch == 'source-sign':
                    gauge['qualification']['sourceSelectedNativeSign'] = -1
                else:
                    gauge['positiveControls'][0]['projectedDirection'] = 'clockwise'
                with self.assertRaises(ValueError):
                    self.generator.validate_analysis_visible_crank_gauge(self.visible, gauge)

    def test_visible_crank_runtime_native_identity_and_camera_mismatches_refuse(self):
        for mismatch in ('hash', 'pts', 'camera'):
            with self.subTest(mismatch=mismatch):
                frame = copy.deepcopy(self.native_frame(2450))
                view = camera_tracks.common.source_views(frame, self.generator.data)[0]
                if mismatch == 'hash':
                    frame['sourceImage']['sha256Bgr8'] = '0' * 64
                elif mismatch == 'pts':
                    frame['decodedTimeSeconds'] += 0.001
                else:
                    view['camera'] = copy.deepcopy(self.gauge['cameraAssociation']['camera'])
                    view['camera']['verticalFovDegrees'] += 1
                with self.assertRaises(ValueError):
                    self.generator.input(frame, 'cone', view)

    def test_visible_crank_diagnostics_separate_observed_source_and_chosen_native_gauge(self):
        diagnostics = self.track['cpuDiagnostics']['analysisVisibleCrankMotion']
        self.assertEqual(diagnostics['domain']['measurementStatus'], 'observed-cycles-approximate-within-cycle-phase')
        self.assertEqual(diagnostics['domain']['startSeconds'], self.visible['interval']['startSeconds'])
        self.assertEqual(diagnostics['domain']['endSeconds'], self.visible['interval']['endSeconds'])
        self.assertEqual([hold['kind'] for hold in diagnostics['sameShotMarginHolds']],
                         ['chosen-first-input-hold', 'chosen-last-input-hold'])
        self.assertTrue(all(hold['measurementStatus'] == 'unmeasured'
                            for hold in diagnostics['sameShotMarginHolds']))
        self.assertEqual(diagnostics['sourceAuthority'], self.visible['authority'])
        self.assertIsNone(diagnostics['sourceAuthority']['selectedNativeSign'])
        self.assertIsNone(diagnostics['sourceAuthority']['absoluteNativeHomeTurns'])
        self.assertEqual(diagnostics['chosenGauge']['nativeSign'], -1)
        self.assertFalse(diagnostics['chosenGauge']['historicalNativeSignIdentified'])
        self.assertFalse(diagnostics['chosenGauge']['historicalNativeHomeIdentified'])
        self.assertFalse(diagnostics['cameraAssociation']['sourceNativeCameraQualified'])
        self.assertFalse(diagnostics['qualification']['stageAcceptance'])


class OrdinaryProducerLiveGuardTests(unittest.TestCase):
    def test_intro_and_spin_live_renderer_refusal_preserves_publication_despite_matching_archive(self):
        producers = (
            ('generate-intro-source-track.py', 'NAsM30MAHLg'),
            ('compact-spin.py', 'XPQwKRt4Y2k'),
        )
        for filename, video_id in producers:
            with self.subTest(video=video_id), current_source_fixture(filename, [video_id]) as (root, module, _, _):
                with redirect_stdout(io.StringIO()):
                    module.main()
                output = root / f'web/content/{video_id}.source-track.json'
                published = output.read_bytes()
                live_path = root / 'web/src/scene.ts'
                original = live_path.read_bytes()
                archive = (root / 'web/content/canonical-native/historical-code'
                           / hashlib.sha256(original).hexdigest() / live_path.name)
                archive.parent.mkdir(parents=True)
                archive.write_bytes(original)
                # An exact sealed historical copy is not live renderer authority,
                # even after these ordinary CLIs have successfully published.
                for mutation in ('changed', 'missing'):
                    with self.subTest(mutation=mutation):
                        if mutation == 'changed':
                            live_path.write_bytes(original + b'\n')
                        else:
                            live_path.unlink()
                        try:
                            with self.assertRaises(ValueError):
                                module.main()
                            self.assertEqual(output.read_bytes(), published)
                        finally:
                            live_path.write_bytes(original)


class SourcePairPublicationOrderingTests(unittest.TestCase):
    def test_second_constructor_or_build_refusal_preserves_both_published_outputs(self):
        filename = 'generate-analysis-synthesis-source-tracks.py'
        videos = ('6dW6VYXp9HM', '8KmVDxkia_w')
        for phase in ('constructor', 'build'):
            with self.subTest(phase=phase), current_source_fixture(filename, videos) as (root, module, data, _):
                with patch.object(sys, 'argv', [filename]), redirect_stdout(io.StringIO()):
                    module.main()
                paths = tuple(root / f'web/content/{video}.source-track.json' for video in videos)
                previous = tuple(path.read_bytes() for path in paths)
                self.assertEqual(tuple(json.loads(raw)['source']['videoId'] for raw in previous), videos)
                if phase == 'constructor':
                    data[videos[1]]['model']['sha256'] = camera_tracks.ANALYSIS_MODEL_SHA256
                    write_current_record(root / 'web', videos[1], data[videos[1]])

                def mutate_second_build(generator):
                    if generator.video_id == videos[1] and phase == 'build':
                        # Only the second real build sees this changed bound
                        # tuple, after the first real build has completed.
                        generator.data['model']['sha256'] = camera_tracks.ANALYSIS_MODEL_SHA256

                with pair_refusal_phase(module, before_build=mutate_second_build) as refusal, \
                        patch.object(sys, 'argv', [filename]), redirect_stdout(io.StringIO()):
                    with self.assertRaises(ValueError):
                        module.main()
                self.assertEqual(refusal, [(phase, videos[1])])
                self.assertEqual(tuple(path.read_bytes() for path in paths), previous)


class SynthesisAutomaticSourceDriveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the actual consumer constructor, including inline retained native
        # calibration, rather than assuming every calibration record is a file.
        cls.generator = historical_synthesis_generator()
        cls.track = cls.generator.revalidate_receipt()
        cls.baseline = common.compact_input(cls.generator.base)
        cls.native_frames = {
            frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')): frame
            for frame in cls.generator.data['frames']
            if frame.get('decodedTimeSeconds') is not None
            and abs(frame['timeSeconds'] - frame['decodedTimeSeconds']) < 1e-8
        }
        # These fixtures remain beside the tests when SOURCE_GENERATOR_PATH
        # selects an exact historical producer copied to a sibling file.
        content = HERE.parent / 'content' / 'canonical-native'
        cls.packet = json.loads((content / '8KmVDxkia_w.automatic-motion.json').read_text())
        cls.candidate = next(row for row in cls.packet['bankCandidates']
                             if row['id'] == 'bank-direction-+1')

    def source_frame(self, index):
        return self.native_frames[index]

    def main_input(self, frame):
        return next(view['input'] for view in self.generator.views(frame)
                    if view['id'] == 'main')

    def assert_complete_input(self, value, turns):
        self.assertAlmostEqual(value['crankTurns'], turns, places=10)
        expected = copy.deepcopy(self.baseline)
        expected['phases'] = self.candidate['staticPhasesRad']
        expected['setup'].update(self.candidate['requiredSetup'])
        for field in ('amplitudes', 'phases', 'gearing', 'magnification', 'setup'):
            self.assertEqual(value[field], expected[field], field)

    def test_cumulative_source_drive_wins_over_old_single_rocker_fold(self):
        first, last = self.source_frame(2541), self.source_frame(2973)
        a, b = self.main_input(first), self.main_input(last)
        # This assertion fails on original main's consumer-visible parked crank,
        # before accessing any API or constant introduced by automatic motion.
        self.assertGreater(b['crankTurns'] - a['crankTurns'], 27)
        self.assertEqual(a['phases'], b['phases'])
        self.assertEqual(len(set(a['phases'])), 1)
        self.assertEqual(len(a['phases']), 20)
        fps = self.packet['source']['fps']
        rate = fps['numerator'] / fps['denominator']
        for knot in self.candidate['knots']:
            index = round(knot['timeSeconds'] * rate)
            with self.subTest(index=index):
                self.assert_complete_input(self.main_input(self.source_frame(index)),
                                           knot['crankTurns'])
        # Also exercise serialization and the real integer playback aliases;
        # the drive belongs to the retained exposure, not its rounded label.
        generated = {frame['timeSeconds']: frame for frame in self.track['frames']}
        for label, original, value in ((106, first, a), (124, last, b)):
            with self.subTest(label=label):
                frame = generated[label]
                self.assertEqual(frame['decodedTimeSeconds'], original['decodedTimeSeconds'])
                self.assertEqual(frame['sourceImage'], original['sourceImage'])
                bank = next(view for view in frame['views'] if view['id'] == 'main')
                self.assertEqual(bank['input'], value)

    def test_between_knots_interpolation_does_not_wrap_or_park_the_crank(self):
        before, after = self.source_frame(2579), self.source_frame(2581)
        middle = self.source_frame(2580)  # Independent CHECK, excluded from knot FIT.
        a, b, m = (self.main_input(frame) for frame in (before, after, middle))
        self.assertNotIn(middle['decodedTimeSeconds'],
                         [knot['timeSeconds'] for knot in self.candidate['knots']])
        self.assertGreater(a['crankTurns'], 1)
        self.assertLess(a['crankTurns'], m['crankTurns'])
        self.assertLess(m['crankTurns'], b['crankTurns'])
        expected_turns = (a['crankTurns'] + b['crankTurns']) / 2
        self.assert_complete_input(m, expected_turns)

    def test_interval_edges_hold_in_same_shot_but_never_cross_the_cut(self):
        first, end = self.source_frame(2541), self.source_frame(2983)
        end_input = self.main_input(end)
        # Comparing against source authority (not another parked output) catches
        # missing cumulative drive as well as an endpoint return-to-zero blend.
        self.assert_complete_input(end_input, self.candidate['knots'][-1]['crankTurns'])
        before_input = self.main_input(self.source_frame(2540))
        self.assert_complete_input(before_input, self.candidate['knots'][0]['crankTurns'])
        self.assertEqual(before_input, self.main_input(first))
        shot_end = self.generator.shots['rocker-bank']['endSeconds']
        for time in ((end['decodedTimeSeconds'] + shot_end) / 2, shot_end - 1e-6):
            with self.subTest(time=time):
                boundary = copy.deepcopy(end)
                # Mathematical instants, not extra observations/source identities.
                for field in ('sourceImage', 'sourceFrameIndex', 'decodedFrameIndex'):
                    boundary.pop(field, None)
                boundary['timeSeconds'] = boundary['decodedTimeSeconds'] = time
                self.assertEqual(self.main_input(boundary), end_input)
        next_shot = self.source_frame(2984)
        self.assertEqual(next_shot['shotId'], 'rocker-out')
        self.assertEqual(self.main_input(next_shot)['crankTurns'], self.baseline['crankTurns'])


class ExecutedPointMotionTests(unittest.TestCase):
    def test_rotary_points_need_executed_baseline_not_only_a_body_binding(self):
        for path, coordinate in (
            ('dt-drive-train/dt-crank-handle-1', [0.057999998331069946, 0, 0]),
            ('dt-drive-train/dt-crank-handle-butt-cup-1', [-0.008100000210106373, 0, 0]),
            ('mg-magnifier/mg-magnifying-wheel-1', [-0.0014816663460806012, 0.04997804015874863, 0]),
            ('dt-drive-train/dt-crankshaft-1', [0, 0, 0]),
        ):
            with self.subTest(path=path):
                self.assertIsNone(common.anchor_motion({
                    'id': 'unproved-feature', 'kind': 'physical-feature',
                    'partPath': 'ha-harmonic-analyzer/' + path, 'partLocalMetres': coordinate,
                    'correspondenceEvidence': 'Native correspondence is not executed motion.'}))

    def test_historical_anchor_authority_does_not_open_live_point_motion_route(self):
        self.assertEqual(common.executed_anchor_motion(
            {'kind': 'historical-source-observations'}, [{'id': 'old', 'motion': None}], []), {})
        self.assertEqual(common.anchor_motion({'id': 'old', 'motion': 'moving'}), 'moving')

    def bridge(self, responses):
        # Protocol aggregation controls only: no substitute native model or
        # fabricated source/geometry proof is installed in the classifier.
        bridge = object.__new__(common._PointMotionBridge)
        bridge.cache = {}
        bridge.unavailable = False
        bridge.process = type("ResponseStream", (), {})()
        bridge.process.stdin = io.StringIO()
        bridge.process.stdout = io.StringIO("".join(json.dumps(row) + "\n" for row in responses))
        return bridge

    def test_global_motion_requires_every_occurrence_not_any_matching_id(self):
        request = {"cases": [{"anchor": {"id": "reused"}} for _ in range(3)]}
        for motions, expected in (
                (["moving", "moving", "moving"], {"reused": "moving"}),
                (["moving", None, "moving"], {}),
                ([None, "moving", "moving"], {}),
                (["moving", "moving", None], {})):
            bridge = self.bridge([{"results": [{"id": "reused", "motion": motion} for motion in motions]}])
            self.assertEqual(bridge.classify(request), expected)

    def test_missing_or_misidentified_occurrence_cannot_promote(self):
        request = {"cases": [{"anchor": {"id": "reused"}}, {"anchor": {"id": "reused"}}]}
        for rows in (
                [{"id": "reused", "motion": "moving"}],
                [{"id": "reused", "motion": "moving"}, {"id": "other", "motion": "moving"}]):
            bridge = self.bridge([{"results": rows}])
            with patch("sys.stderr", io.StringIO()):
                self.assertEqual(bridge.classify(request), {})
            self.assertTrue(bridge.unavailable)

    def test_bridge_cache_separates_source_assembly_and_never_serializes_nan_as_null(self):
        request = {"cases": [{"anchor": {"id": "point"}, "input": {"crankTurns": 0},
                              "sourceAssembly": {"photograph": {"pair": "four-gears", "angle": 0}}}]}
        bridge = self.bridge([{"results": [{"id": "point", "motion": "moving"}]},
                              {"results": [{"id": "point", "motion": None}]}])
        self.assertEqual(bridge.classify(request), {"point": "moving"})
        written = bridge.process.stdin.getvalue()
        self.assertEqual(bridge.classify(copy.deepcopy(request)), {"point": "moving"})
        self.assertEqual(bridge.process.stdin.getvalue(), written)
        changed = copy.deepcopy(request)
        changed["cases"][0]["sourceAssembly"]["photograph"]["angle"] = .125
        self.assertEqual(bridge.classify(changed), {})
        invalid = copy.deepcopy(request)
        invalid["cases"][0]["sourceAssembly"]["photograph"]["angle"] = float("nan")
        with self.assertRaises(ValueError):
            bridge.classify(invalid)


class HistoricalSynthesisSourceDriveBoundaryTests(unittest.TestCase):
    def fixture(self, load_motion=True):
        generator = historical_synthesis_generator()
        if not load_motion:
            generator.synthesis_automatic_motion = None
        return generator

    def source_frame(self, generator, index):
        return next(frame for frame in generator.data['frames']
                    if frame['shotId'] == 'rocker-bank'
                    and frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) == index)

    def main_view(self, generator, frame):
        return next(view for view in common.source_views(frame, generator.data)
                    if view['id'] == 'main')

    def test_historical_no_bank_drive_leaks_to_other_shots_views_or_camera_layers(self):
        generator = self.fixture()
        frame = self.source_frame(generator, 2700)
        view = self.main_view(generator, frame)
        for scope in ('other-shot', 'wrong-family', 'inset', 'mirror', 'warp', 'composite', 'other-corpus'):
            with self.subTest(scope=scope):
                row, source_view, family = copy.deepcopy(frame), copy.deepcopy(view), 'bar'
                if scope == 'other-shot':
                    row['shotId'] = 'rocker-out'
                elif scope == 'wrong-family':
                    family = 'cone'
                elif scope == 'inset':
                    source_view['id'] = 'lower-inset'
                    source_view['rectSourcePixels'] = [0, 0, 960, 1080]
                elif scope == 'mirror':
                    source_view['presentation'] = 'horizontal-mirror'
                elif scope == 'warp':
                    source_view['imagePlaneWarp'] = {'kind': 'homography',
                        'unwarpedViewportPixels': [0, 0, 1920, 1080],
                        'renderToSourcePixels': [1, 0, 0, 0, 1, 0, 0, 0, 1]}
                elif scope == 'composite':
                    source_view['composite'] = {'mode': 'crossfade'}
                elif scope == 'other-corpus':
                    generator.data['source']['videoId'] = '6dW6VYXp9HM'
                self.assertIsNone(generator.synthesis_automatic_input(row, family, source_view))

    def test_historical_interval_refuses_exact_cut(self):
        generator = self.fixture()
        end = self.source_frame(generator, 2983)
        boundary = copy.deepcopy(end)
        boundary['decodedTimeSeconds'] = generator.shots['rocker-bank']['endSeconds']
        self.assertIsNone(generator.synthesis_automatic_input(
            boundary, 'bar', self.main_view(generator, end)))

    def test_historical_h1_pixel_holdout_accepts_fit_times_but_refuses_exposure_holdout(self):
        generator = self.fixture()
        packet = generator.synthesis_automatic_motion['packet']
        evidence = json.loads((camera_tracks.ROOT / camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE).read_text())
        annotation_fits = {row['sourceImage']['frameIndex'] for row in evidence['annotations']
                           if row['role'] == 'fit'}
        h1_checks = [row for row in evidence['nearestJointSource']['rows'] if row['role'] == 'check']
        self.assertEqual(len(h1_checks), 17)
        self.assertTrue({row['sourceImage']['frameIndex'] for row in h1_checks} <= annotation_fits)
        # A valid cross-feature CHECK exposure must retain its annotation cadence
        # knot, not be dropped by an overbroad all-physical exposure holdout.
        knots = {row['timeSeconds']: row['crankTurns']
                 for row in generator.synthesis_automatic_motion['candidate']['knots']}
        for row in h1_checks:
            with self.subTest(accepted_h1_frame=row['sourceImage']['frameIndex']):
                frame = self.source_frame(generator, row['sourceImage']['frameIndex'])
                value, _ = generator.synthesis_automatic_input(
                    frame, 'bar', self.main_view(generator, frame))
                self.assertAlmostEqual(value['crankTurns'], knots[row['timeSeconds']], places=10)

        paths = [camera_tracks.SYNTHESIS_AUTOMATIC_MOTION, camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE]
        for mismatch in ('h1-exposure-authority', 'h1-disjoint-time', 'h20-fit-overlap'):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for relative in paths:
                    target = root / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((camera_tracks.ROOT / relative).read_bytes())
                changed_packet, changed_evidence = copy.deepcopy(packet), copy.deepcopy(evidence)
                expected_error = 'H1 CHECK feature-pixel holdout'
                if mismatch == 'h1-exposure-authority':
                    changed_packet['bankMeasurement']['physicalCHECKHoldout']['nearest1PhysicalJoint'] = (
                        'exposure-disjoint-from-annotation-FIT')
                else:
                    if mismatch == 'h1-disjoint-time':
                        changed_row = next(row for row in changed_evidence['nearestJointSource']['rows']
                                           if row['role'] == 'check')
                        exposure = changed_evidence['physicalMetalCHECK'][0]
                    else:
                        changed_row = changed_evidence['physicalMetalCHECK'][0]
                        exposure = next(row for row in changed_evidence['annotations'] if row['role'] == 'fit')
                        expected_error = 'H20 CHECK exposure holdout'
                    changed_row['sourceImage'] = copy.deepcopy(exposure['sourceImage'])
                    changed_row['timeSeconds'] = exposure['timeSeconds']
                evidence_path = root / camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE
                evidence_path.write_text(json.dumps(changed_evidence, indent=2) + '\n')
                evidence_hash = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                changed_packet['generationDependencies'][camera_tracks.SYNTHESIS_AUTOMATIC_EVIDENCE]['sha256'] = (
                    evidence_hash)
                packet_path = root / camera_tracks.SYNTHESIS_AUTOMATIC_MOTION
                packet_path.write_text(json.dumps(changed_packet, indent=2) + '\n')
                packet_hash = hashlib.sha256(packet_path.read_bytes()).hexdigest()
                # Re-pin real fixture bytes so refusal must come from the typed
                # holdout and actual exposure sets, not the outer digest gate.
                with patch.object(camera_tracks, 'ROOT', root), \
                        patch.object(camera_tracks, 'SYNTHESIS_AUTOMATIC_MOTION_SHA256', packet_hash), \
                        patch.object(camera_tracks, 'SYNTHESIS_AUTOMATIC_EVIDENCE_SHA256', evidence_hash):
                    with self.assertRaisesRegex(ValueError, expected_error):
                        generator.synthesis_automatic_motion_packet()

    def test_historical_source_model_and_exact_exposure_mismatches_are_refused(self):
        for mismatch in ('source', 'model', 'missing-knot-exposure', 'wrong-exposure-hash', 'off-native-clock'):
            with self.subTest(mismatch=mismatch):
                generator = self.fixture(load_motion=False)
                if mismatch == 'source':
                    generator.data['source']['sha256'] = '0' * 64
                elif mismatch == 'model':
                    generator.data['model']['sha256'] = '0' * 64
                elif mismatch == 'missing-knot-exposure':
                    generator.data['frames'] = [frame for frame in generator.data['frames']
                        if frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) != 2557]
                else:
                    rows = [frame for frame in generator.data['frames'] if frame['shotId'] == 'rocker-bank'
                        and frame.get('sourceFrameIndex', frame.get('decodedFrameIndex')) == 2557]
                    for frame in rows:
                        if mismatch == 'wrong-exposure-hash':
                            frame['sourceImage']['sha256Bgr8'] = '0' * 64
                        else:
                            frame['decodedTimeSeconds'] += 0.001
                with self.assertRaises(ValueError):
                    generator.synthesis_automatic_motion_packet()

    def test_historical_missing_motion_and_changed_native_math_never_fall_back_to_old_fold(self):
        packet = json.loads((camera_tracks.ROOT / camera_tracks.SYNTHESIS_AUTOMATIC_MOTION).read_bytes())
        dependencies = packet['generationDependencies']
        for path in dependencies:
            if path.startswith('web/content/'):
                continue
            for mutation in ('missing', 'changed'):
                with self.subTest(path=path, mutation=mutation), historical_archive_fixture() as (root, web):
                    generator = self.fixture(load_motion=False)
                    positive = generator.synthesis_automatic_motion_packet()
                    self.assertEqual(positive['packet'], packet)
                    archive = web / 'content/canonical-native/historical-code' / dependencies[path]['sha256'] / Path(path).name
                    original = archive.read_bytes()
                    if mutation == 'missing':
                        archive.unlink()
                    else:
                        archive.write_bytes(original + b'\n')
                    # Exact original nominal-path bytes remain available, but
                    # cannot rescue a missing or modified sealed archive.
                    self.assertEqual((root / path).read_bytes(), original)
                    with self.assertRaises(ValueError):
                        generator.synthesis_automatic_motion_packet()
        with historical_archive_fixture() as (root, _):
            generator = self.fixture(load_motion=False)
            (root / camera_tracks.SYNTHESIS_AUTOMATIC_MOTION).unlink()
            with self.assertRaises(ValueError):
                generator.synthesis_automatic_motion_packet()


class HistoricalSceneArchiveBoundaryTests(unittest.TestCase):
    def test_original_scene_archive_refusal_cannot_borrow_matching_nominal_scene(self):
        for mutation in ('missing', 'changed'):
            with self.subTest(mutation=mutation), historical_archive_fixture() as (root, web):
                generator = historical_synthesis_generator()
                receipt = generator.revalidate_receipt()
                self.assertEqual(receipt['kind'], 'historical-source-track-receipt')
                archive = web / 'content/canonical-native/historical-code' / HISTORICAL_SCENE_SHA256 / 'scene.ts'
                original = archive.read_bytes()
                if mutation == 'missing':
                    archive.unlink()
                else:
                    archive.write_bytes(original + b'\n')
                self.assertEqual((root / 'web/src/scene.ts').read_bytes(), original)
                with self.assertRaises(ValueError):
                    camera_tracks.HistoricalReceiptRevalidator('8KmVDxkia_w')
                with self.assertRaises(ValueError):
                    generator.revalidate_receipt()


class QualifiedSourceVisibilityTests(unittest.TestCase):
    @staticmethod
    def qualify(frame, view):
        view['sourceVisibility'] = {
            'kind': 'policy-excluded', 'reasonCode': 'blurred-navigation-background',
            'sourceImage': copy.deepcopy(frame['sourceImage']),
            'rectSourcePixels': copy.deepcopy(view['rectSourcePixels']),
            'manualSourceAudit': {'method': 'manual-source-pixel-inspection',
                                  'evidence': 'Synthetic full physical ROI audit for ordinary producer contract only.'},
        }

    def test_normal_current_producer_retains_inventory_and_only_omits_qualified_background_denominators(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            for frame in record['frames']:
                background = copy.deepcopy(frame['views'][0])
                frame['views'][0]['rectSourcePixels'] = [0, 0, 400, 600]
                background['id'] = 'background'
                background['camera'] = None
                background['input'] = None
                background.pop('cameraMeasurement', None)
                background['unavailable'] = [{'reason': 'Source-qualified blurred background has no current native pose claim.'}]
                self.qualify(frame, background)
                frame['views'].insert(0, background)
            write_current_record(root / 'web', video_id, record)
            track = ordinary_build(module, video_id, 'generate', record)
            self.assertEqual(track['coverage']['status'], 'complete')
            self.assertEqual(track['sourceMeasurements']['requiredViewSamples'],
                             sum(len(frame['views']) - 1 for frame in track['frames']))
            self.assertEqual(track['sourceMeasurements']['qualifiedExcludedViewSamples'], len(track['frames']))
            for frame in track['frames']:
                self.assertEqual(frame['views'][0]['id'], 'background')
                self.assertEqual(frame['views'][0]['sourceVisibility']['sourceImage'], frame['sourceImage'])
            self.assertTrue(all(stage['status'] == 'unmeasured' for stage in track['stages'].values()))
            module.common.write_track(track)

    def test_normal_producer_refuses_incomplete_roi_wrong_image_unknown_reason_and_readable_current_pixels(self):
        video_id = 'XPQwKRt4Y2k'
        for mutation in ('image', 'roi', 'reason', 'blank-audit', 'readable'):
            with self.subTest(mutation=mutation), current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
                record = data[video_id]
                frame = record['frames'][0]
                background = copy.deepcopy(frame['views'][0])
                background['id'] = 'background'
                self.qualify(frame, background)
                frame['views'].append(background)
                value = background['sourceVisibility']
                if mutation == 'image':
                    value['sourceImage']['frameIndex'] += 1
                elif mutation == 'roi':
                    value['rectSourcePixels'][2] -= 1
                elif mutation == 'reason':
                    value['reasonCode'] = 'unobservable'
                elif mutation == 'blank-audit':
                    value['manualSourceAudit']['evidence'] = ' '
                else:
                    frame['landmarks'].append({**frame['landmarks'][0], 'viewId': 'background'})
                write_current_record(root / 'web', video_id, record)
                with self.assertRaises(ValueError):
                    ordinary_build(module, video_id, 'generate', record)

    def test_normal_producer_preserves_inadmissible_template_donors_without_using_them_as_checks(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            frame = record['frames'][0]
            for point in frame['landmarks']:
                point['method'] = 'template-match'
                point.pop('trackingEvidence', None)
            self.qualify(frame, frame['views'][0])
            frame['views'][0]['sourceVisibility']['reasonCode'] = 'unreadable-near-black-fade'
            donors = copy.deepcopy(frame['landmarks'])
            write_current_record(root / 'web', video_id, record)
            track = ordinary_build(module, video_id, 'generate', record)
            retained = next(row for row in track['frames'] if row['timeSeconds'] == frame['timeSeconds'])
            self.assertEqual(retained['landmarks'], donors)
            self.assertEqual(track['sourceMeasurements']['preservedInadmissibleLandmarkSamples'], len(donors))
            self.assertTrue(all(stage['status'] == 'unmeasured' for stage in track['stages'].values()))
            module.common.write_track(track)

    def test_qualification_transition_is_a_retained_observed_change_even_without_authored_keys(self):
        data = {
            'kind': 'current-source-observations', 'coverage': {'changeTimesSeconds': []},
            'frames': [
                {'timeSeconds': 0, 'views': [{'id': 'main'}]},
                {'timeSeconds': 0.25, 'views': [{'id': 'main', 'sourceVisibility': {'reasonCode': 'blurred-navigation-background'}}]},
                {'timeSeconds': 0.5, 'views': [{'id': 'main'}]},
            ],
        }
        self.assertEqual(common.compact_change_times(data), {0, 0.25, 0.5})

    def test_current_physical_views_do_not_inherit_non_machine_labels(self):
        current = {'kind': 'current-source-observations',
                   'shots': [{'id': 'navigation', 'classification': 'non-machine',
                              'hasCorrespondingMachine': False}]}
        frame = {'shotId': 'navigation', 'classification': 'non-machine',
                 'views': [{'id': 'readable-bank'}]}
        self.assertTrue(common.needs_machine(frame, current))
        frame['views'] = []
        self.assertFalse(common.needs_machine(frame, current))
        frame['views'] = [{'id': 'historical-view'}]
        self.assertFalse(common.needs_machine(frame, {**current, 'kind': 'source-observations'}))

    def test_normal_producer_preserves_covered_lower_inventory_and_distinguishes_ordinary_coverage(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            frame = record['frames'][0]
            lower = frame['views'][0]
            top = copy.deepcopy(lower)
            top['id'] = 'top-bank'
            top['composite'] = {'mode': 'opaque'}
            lower['camera'] = None
            lower['input'] = None
            lower.pop('cameraMeasurement', None)
            lower['unavailable'] = [{'reason': 'Preserved lower source candidate fully covered by the ordinary exact opaque bank.'}]
            frame['views'].append(top)
            original_points = copy.deepcopy(frame['landmarks'])
            write_current_record(root / 'web', video_id, record)
            track = ordinary_build(module, video_id, 'generate', record)
            self.assertEqual(track['coverage']['status'], 'complete')
            self.assertEqual(track['sourceMeasurements']['noncontributingCoveredViewSamples'], 1)
            self.assertEqual(track['sourceMeasurements']['qualifiedExcludedViewSamples'], 0)
            self.assertEqual(track['sourceMeasurements']['requiredViewSamples'],
                             sum(len(row['views']) for row in track['frames']) - 1)
            self.assertEqual(track['frames'][0]['landmarks'], original_points)
            self.assertEqual([view['id'] for view in track['frames'][0]['views']], ['main', 'top-bank'])
            self.assertTrue(all(stage['status'] == 'unmeasured' for stage in track['stages'].values()))
            module.common.write_track(track)

    def test_exact_opaque_coverage_never_rounds_away_source_strips_or_transparency(self):
        for mutation in ('none', 'strip', 'transparent', 'warp', 'independent-fade'):
            lower = {'id': 'main', 'rectSourcePixels': [0, 0, 1920, 1080]}
            top = {'id': 'bank', 'rectSourcePixels': [0, 0, 1920, 1080]}
            if mutation == 'strip':
                top['rectSourcePixels'] = [0.0012211742535110114, 0.00044720401288042083,
                                          1919.9959881610268, 1079.9993538624958]
            if mutation == 'transparent':
                top['composite'] = {'mode': 'crossfade', 'groupId': 'overlay',
                                    'imageLayerId': 'bank', 'opacity': 0.9999999999999999}
            if mutation == 'warp':
                top['imagePlaneWarp'] = {'kind': 'homography'}
            if mutation == 'independent-fade':
                lower['composite'] = {'mode': 'crossfade', 'groupId': 'fade',
                                      'imageLayerId': 'main', 'opacity': 0.5}
                top['composite'] = {'mode': 'crossfade', 'groupId': 'fade',
                                    'imageLayerId': 'bank', 'opacity': 1}
            frame = {'views': [lower, top]}
            self.assertIs(common.fully_covering_source_view(frame, lower),
                          top if mutation == 'none' else None)

    def test_normal_producer_retains_exact_zero_images_without_creating_source_checks(self):
        video_id = 'XPQwKRt4Y2k'
        with current_source_fixture('compact-spin.py', [video_id]) as (root, module, data, _):
            record = data[video_id]
            frame = record['frames'][0]
            zero = copy.deepcopy(frame['views'][0])
            zero['id'] = 'zero-incoming'
            zero['composite'] = {'mode': 'crossfade', 'groupId': 'incoming',
                                 'imageLayerId': 'incoming', 'opacity': 0}
            zero['compositeEvidence'] = 'Synthetic exact zero contribution producer control, not an actual source attenuation measurement.'
            zero['camera'] = None
            zero['input'] = None
            zero.pop('cameraMeasurement', None)
            zero['unavailable'] = [{'reason': 'Exact zero incoming image has no current source/native pose claim.'}]
            frame['views'].append(zero)
            write_current_record(root / 'web', video_id, record)
            track = ordinary_build(module, video_id, 'generate', record)
            self.assertEqual(track['coverage']['status'], 'complete')
            self.assertEqual(track['sourceMeasurements']['noncontributingZeroOpacityViewSamples'], 1)
            self.assertEqual(track['sourceMeasurements']['qualifiedExcludedViewSamples'], 0)
            self.assertEqual(track['sourceMeasurements']['noncontributingCoveredViewSamples'], 0)
            self.assertEqual(track['frames'][0]['views'][1]['composite'], zero['composite'])
            self.assertEqual(track['sourceMeasurements']['requiredViewSamples'],
                             sum(len(row['views']) for row in track['frames']) - 1)
            self.assertTrue(all(stage['status'] == 'unmeasured' for stage in track['stages'].values()))
            module.common.write_track(track)
            for composite in (
                {**zero['composite'], 'opacity': math.nextafter(0, 1)},
                {'mode': 'opaque', 'opacity': 0},
                {'mode': 'crossfade', 'opacity': 0},
            ):
                self.assertFalse(common.zero_opacity_source_view({**zero, 'composite': composite}))
            zero['composite']['opacity'] = math.nextafter(0, 1)
            write_current_record(root / 'web', video_id, record)
            with self.assertRaisesRegex(ValueError, 'unresolved.*camera/input'):
                ordinary_build(module, video_id, 'generate', record)


if __name__ == '__main__':
    unittest.main()
