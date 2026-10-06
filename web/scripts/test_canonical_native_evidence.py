"""Offline identity grammar/transaction regressions; run by the coordinating root."""
from contextlib import contextmanager
import importlib.util
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'canonical_native_evidence', Path(__file__).with_name('canonical-native-evidence.py'))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

MAPPING = {'schema_version': 2, 'identities': [
    {'old_stem': 'harmonic-analyzer', 'new_stem': 'ha-harmonic-analyzer'},
    {'old_stem': 'measuring-stick', 'new_stem': 'ha-measuring-stick'},
    {'old_stem': 'measuring-stick-stop', 'new_stem': 'ha-measuring-stick-stop'},
    {'old_stem': 'frame', 'new_stem': 'fr-frame'},
    {'old_stem': 'tube-frame', 'new_stem': 'fr-tube-frame'},
    {'old_stem': 'paper-drive', 'new_stem': 'pd-paper-drive'},
    {'old_stem': 'transgear-removable', 'new_stem': 'pd-transgear-removable'},
], 'variants': []}


class NativeEvidenceTests(unittest.TestCase):
    def test_current_text_seals_ignore_checkout_eol_but_detect_content_changes(self):
        lf = b'{"nativePartPath":"ha-harmonic-analyzer/fr-frame/fr-tube-frame-3",\n"n":1.2300e-09}\n'
        crlf = lf.replace(b'\n', b'\r\n')
        changed = crlf.replace(b'fr-tube-frame-3', b'fr-tube-frame-4')
        self.assertEqual(evidence.consumer_digest(lf), evidence.consumer_digest(crlf))
        self.assertNotEqual(evidence.consumer_digest(crlf), evidence.consumer_digest(changed))
        # The checkout exception must never weaken exact evidence certificates.
        self.assertNotEqual(evidence.digest(lf), evidence.digest(crlf))

    def test_direct_nested_and_mesh_instance_suffixes(self):
        translate = evidence.native_mapper(MAPPING, set())
        for old, new in [
            ('measuring-stick-1', 'ha-measuring-stick-1'),
            ('measuring-stick-stop-1/mesh', 'ha-measuring-stick-stop-1/mesh'),
            ('measuring-stick-stop-12/mesh_276_1', 'ha-measuring-stick-stop-12/mesh_276_1'),
            ('frame/tube-frame-3/mesh_4_2', 'fr-frame/fr-tube-frame-3/mesh_4_2'),
        ]:
            with self.subTest(old=old):
                self.assertEqual(translate('harmonic-analyzer/' + old), 'ha-harmonic-analyzer/' + new)

    def test_known_prefix_does_not_accept_unknown_tail(self):
        translate = evidence.native_mapper(MAPPING, set())
        for path in ['measuring-stick-1unknown', 'frame/tube-frame-3/mesh_4_bad',
                     'frame/tube-frame-3/mesh_4/extra', 'frame/tube-frame-3@unknown']:
            with self.subTest(path=path), self.assertRaises(evidence.UndeclaredNativeBinding):
                translate('harmonic-analyzer/' + path)

    def test_escaped_slash_keys_values_and_numeric_bytes(self):
        raw = b'{"harmonic-analyzer\\/measuring-stick-1":"harmonic-analyzer\\/measuring-stick-stop-1\\/mesh","n":1.2300e-09}'
        changed = evidence.strings(raw, {}, evidence.native_mapper(MAPPING, set()))
        self.assertEqual(json.loads(changed), {
            'ha-harmonic-analyzer/ha-measuring-stick-1': 'ha-harmonic-analyzer/ha-measuring-stick-stop-1/mesh',
            'n': 1.2300e-09})
        self.assertIn(b'1.2300e-09', changed)
        self.assertEqual(evidence.numbers(raw), evidence.numbers(changed))

    def test_archive_allowlist_is_exact(self):
        archived = 'harmonic-analyzer/frame/retired-1/mesh_4'
        translate = evidence.native_mapper(MAPPING, {archived})
        self.assertEqual(translate(archived), 'archived-not-current:' + archived)
        with self.assertRaises(evidence.UndeclaredNativeBinding):
            translate(archived + '_1')

    def test_role_instances_and_contextual_family_selector(self):
        translate = evidence.native_mapper(MAPPING, set())
        self.assertEqual(translate('harmonic-analyzer/paper-drive/transgear-removable-3@upper'),
                         'ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-3@upper')
        with self.assertRaises(evidence.UndeclaredNativeBinding):
            translate('harmonic-analyzer/paper-drive/transgear-removable-3@spare')
        selector = 'harmonic-analyzer/frame/tube-frame-*'
        raw = json.dumps({'independentSourceCalibration': {
            'sourceNonIdentifiableFixedPartQualification': {'cases': [
                {'nativePartPaths': [selector], 'error': 'Fixed part ' + selector + ': not a drawable.'}]}}}).encode()
        native, _ = evidence.contextual_native_mapper(raw, 'fixture.json', MAPPING, set())
        changed = json.loads(evidence.strings(raw, {}, native))
        case = changed['independentSourceCalibration']['sourceNonIdentifiableFixedPartQualification']['cases'][0]
        self.assertEqual(case, {'nativePartPaths': ['ha-harmonic-analyzer/fr-frame/fr-tube-frame-*'],
                                'error': 'Fixed part ha-harmonic-analyzer/fr-frame/fr-tube-frame-*: not a drawable.'})
        invalid = json.dumps({'partPath': selector}).encode()
        records = evidence.native_binding_occurrences(invalid, 'fixture.json', MAPPING, set())
        self.assertEqual([(r['jsonPath'], r['binding']) for r in records], [('$["partPath"]', selector)])

    def test_unbound_family_hypothesis_is_not_a_concrete_identity(self):
        family = 'harmonic-analyzer/frame/unidentified-family-1..20'
        raw = json.dumps({'visibleMotionFeatures': {'occluded-feature': {
            'partPath': None, 'candidatePartFamily': family}}}).encode()
        native, _ = evidence.contextual_native_mapper(raw, 'fixture.json', MAPPING, set())
        changed = json.loads(evidence.strings(raw, {}, native))
        self.assertEqual(changed['visibleMotionFeatures']['occluded-feature'], {
            'partPath': None, 'candidatePartFamily': 'ha-harmonic-analyzer/fr-frame/unidentified-family-1..20'})
        for concrete in [family, 'harmonic-analyzer/frame/unidentified-family-20..1']:
            invalid = json.dumps({'partPath': concrete}).encode()
            records = evidence.native_binding_occurrences(invalid, 'fixture.json', MAPPING, set())
            self.assertEqual([r['binding'] for r in records], [concrete])
        invalid = json.dumps({'visibleMotionFeatures': {'occluded-feature': {
            'partPath': None, 'candidatePartFamily': 'harmonic-analyzer/frame/unidentified-family-20..1'}}}).encode()
        self.assertEqual([r['binding'] for r in evidence.native_binding_occurrences(
            invalid, 'fixture.json', MAPPING, set())],
            ['harmonic-analyzer/frame/unidentified-family-20..1'])

    def test_all_packets_duplicate_members_and_no_generate_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for name, raw in [('a', b'{"p":"harmonic-analyzer/unknown-1","p":"harmonic-analyzer/unknown-1"}'),
                              ('b', b'{"harmonic-analyzer/unknown-2":"harmonic-analyzer/unknown-3"}')]:
                source = 'web/content/' + name + '.json'
                output = 'web/content/canonical-native/' + name + '.json'
                (root / source).parent.mkdir(parents=True, exist_ok=True)
                (root / source).write_bytes(raw)
                (root / output).parent.mkdir(parents=True, exist_ok=True)
                (root / output).write_bytes(b'unchanged output')
                rows.append({'originalPath': source, 'path': output,
                             'originalSha256': evidence.digest(raw),
                             'originalNumericLexemeSha256': evidence.numbers(raw),
                             'archivedNativeBindings': []})
            manifest = {'mappingSchemaVersion': 2, 'derivatives': rows, 'historicalCodeSnapshots': []}
            (root / evidence.MANIFEST).write_text(json.dumps(manifest), encoding='utf8')
            (root / evidence.MAP).parent.mkdir(parents=True, exist_ok=True)
            (root / evidence.MAP).write_text(json.dumps(MAPPING), encoding='utf8')
            before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(evidence, 'ROOT', root), patch.object(evidence.sys, 'argv', ['evidence', 'generate']):
                with self.assertRaises(evidence.NativeBindingInventoryError) as caught:
                    evidence.main()
            records = caught.exception.occurrences
            self.assertEqual([(r['sourcePacket'], r['jsonPath'], r['binding']) for r in records], [
                ('web/content/a.json', '$["p"]', 'harmonic-analyzer/unknown-1'),
                ('web/content/a.json', '$["p"]', 'harmonic-analyzer/unknown-1'),
                ('web/content/b.json', '$["harmonic-analyzer/unknown-2"]', 'harmonic-analyzer/unknown-2'),
                ('web/content/b.json', '$["harmonic-analyzer/unknown-2"]', 'harmonic-analyzer/unknown-3'),
            ])
            self.assertEqual([r['objectMemberIndex'] for r in records[:2]], [0, 1])
            self.assertEqual([r['location'] for r in records], ['value', 'value', 'key', 'value'])
            self.assertEqual({p: p.read_bytes() for p in root.rglob('*') if p.is_file()}, before)

    def test_case_label_inventory_collects_all_unknown_labels_and_drawable_paths(self):
        raw = (
            b'{"independentSourceCalibration":{"sourceNonIdentifiableFixedPartQualification":{"cases":['
            b'{"name":"negative-native-harmonic-analyzer/unknown-label-1",'
            b'"name":"negative-native-harmonic-analyzer/unknown-label-2",'
            b'"nativePartPaths":["harmonic-analyzer/unknown-drawable-1"]},'
            b'{"name":"negative-native-harmonic-analyzer/unknown-label-3",'
            b'"nativePartPaths":["harmonic-analyzer/unknown-drawable-2"]}]}}}')
        records = evidence.native_binding_occurrences(raw, 'labels.json', MAPPING, set())
        prefix = '$["independentSourceCalibration"]["sourceNonIdentifiableFixedPartQualification"]["cases"]'
        self.assertEqual([
            (record['sourcePacket'], record['jsonPath'], record['binding'],
             record['location'], record.get('objectMemberIndex')) for record in records
        ], [
            ('labels.json', prefix + '[0]["name"]', 'harmonic-analyzer/unknown-label-1', 'value', 0),
            ('labels.json', prefix + '[0]["name"]', 'harmonic-analyzer/unknown-label-2', 'value', 1),
            ('labels.json', prefix + '[0]["nativePartPaths"][0]', 'harmonic-analyzer/unknown-drawable-1', 'value', None),
            ('labels.json', prefix + '[1]["name"]', 'harmonic-analyzer/unknown-label-3', 'value', 0),
            ('labels.json', prefix + '[1]["nativePartPaths"][0]', 'harmonic-analyzer/unknown-drawable-2', 'value', None),
        ])

    def test_case_label_mapping_is_known_and_schema_specific_not_a_prose_alias(self):
        outside = 'negative-native-harmonic-analyzer/unknown-outside-label-1'
        note = 'negative-native-harmonic-analyzer/unknown-case-prose-1'
        raw = json.dumps({
            'name': outside,
            'independentSourceCalibration': {'sourceNonIdentifiableFixedPartQualification': {'cases': [
                {'name': 'negative-native-harmonic-analyzer/frame/tube-frame-3', 'note': note},
            ]}},
        }).encode('utf8')
        self.assertEqual(evidence.native_binding_occurrences(raw, 'labels.json', MAPPING, set()), [])
        translate, _ = evidence.contextual_native_mapper(raw, 'labels.json', MAPPING, set())
        changed = json.loads(evidence.strings(raw, {}, translate))
        case = changed['independentSourceCalibration']['sourceNonIdentifiableFixedPartQualification']['cases'][0]
        self.assertEqual(case['name'], 'negative-native-ha-harmonic-analyzer/fr-frame/fr-tube-frame-3')
        self.assertEqual(case['note'], note)
        self.assertEqual(changed['name'], outside)


class CanonicalObservationCodecTests(unittest.TestCase):
    @contextmanager
    def authored_fixture(self):
        raw = (b'{"n":1.2300e-09,"historicalCommand":"python fit-source.py '
               b'web/content/snapshot.observations.json"}\n')
        row = {
            'path': 'web/content/canonical-native/snapshot.observations.json.gz',
            'contentEncoding': 'gzip',
            'decodedSha256': evidence.digest(raw),
            'sha256': evidence.digest(raw),
            'originalPath': 'web/content/snapshot.observations.json',
            'originalSha256': evidence.digest(raw),
            'originalNumericLexemeSha256': evidence.numbers(raw),
            'archivedNativeBindings': [],
        }
        mapping_bytes = json.dumps(MAPPING).encode('utf8')
        manifest = {
            'mappingSchemaVersion': 2,
            'mappingSha256': evidence.digest(mapping_bytes),
            'originalSourceCommit': 'fixture-original',
            'derivatives': [row],
            'historicalCodeSnapshots': [],
            'canonicalConsumerInputs': [],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stored = root / row['path']
            stored.parent.mkdir(parents=True)
            (root / row['originalPath']).write_bytes(raw)
            (root / evidence.MANIFEST).write_text(json.dumps(manifest), encoding='utf8')
            (root / evidence.MAP).parent.mkdir(parents=True)
            (root / evidence.MAP).write_bytes(mapping_bytes)
            with patch.object(evidence, 'ROOT', root):
                with patch.object(evidence.sys, 'argv', ['evidence', 'generate']):
                    evidence.main()
                yield root, row, stored

    def test_decoding_rejects_corruption_and_changed_numeric_or_provenance_seals(self):
        with self.authored_fixture() as (_, row, stored):
            valid = stored.read_bytes()
            decoded = evidence.decoded_derivative(row, valid)
            self.assertIn(b'1.2300e-09', decoded)
            self.assertEqual(json.loads(decoded)['historicalCommand'],
                             'python fit-source.py web/content/canonical-native/snapshot.observations.json')
            bad_crc = valid[:-8] + bytes([valid[-8] ^ 1]) + valid[-7:]
            cases = (
                ('header', b'not a gzip stream'),
                ('truncated', valid[:-8]),
                ('crc', bad_crc),
                ('json', evidence.encode_observations(b'{"n":')),
                ('numeric-lexeme', evidence.encode_observations(
                    decoded.replace(b'1.2300e-09', b'1.23e-9'))),
                ('provenance', evidence.encode_observations(
                    decoded.replace(row['originalSha256'].encode('ascii'), b'0' * 64))),
            )
            for label, wire in cases:
                with self.subTest(label=label), self.assertRaises(ValueError):
                    evidence.decoded_derivative(row, wire)

    def test_check_rejects_reencoded_payload_even_with_honest_wire_and_decoded_seals(self):
        with self.authored_fixture() as (root, _, stored):
            decoded = gzip.decompress(stored.read_bytes())
            replacement = gzip.compress(decoded, compresslevel=9, mtime=1)
            stored.write_bytes(replacement)
            manifest_path = root / evidence.MANIFEST
            manifest = json.loads(manifest_path.read_bytes())
            manifest['derivatives'][0]['sha256'] = evidence.digest(replacement)
            manifest['derivatives'][0]['decodedSha256'] = evidence.digest(decoded)
            manifest_path.write_text(json.dumps(manifest), encoding='utf8')
            with patch.object(evidence.sys, 'argv', ['evidence', 'check']), self.assertRaises(ValueError):
                evidence.main()

    def test_capture_dependencies_and_current_inputs_keep_separate_payload_and_wire_identities(self):
        with self.authored_fixture() as (root, observation, stored):
            plain_path = observation['path'][:-3]
            plain_sha = evidence.digest(gzip.decompress(stored.read_bytes()))
            captured = {'path': plain_path, 'sha256': plain_sha}
            probe_raw = json.dumps({'lineage': {'observations': {
                'path': observation['originalPath'],
                'sha256': observation['originalSha256'],
            }}}).encode('utf8')
            probe = {
                'path': 'web/content/canonical-native/probe.json',
                'sha256': evidence.digest(probe_raw),
                'originalPath': 'web/content/probe.json',
                'originalSha256': evidence.digest(probe_raw),
                'originalNumericLexemeSha256': evidence.numbers(probe_raw),
                'archivedNativeBindings': [],
            }
            (root / probe['originalPath']).write_bytes(probe_raw)
            manifest_path = root / evidence.MANIFEST
            manifest = json.loads(manifest_path.read_bytes())
            manifest['derivatives'].append(probe)
            manifest_path.write_text(json.dumps(manifest), encoding='utf8')
            track_path = root / 'web/content/snapshot.source-track.json'
            track = {'evidence': {
                'generatorInputs': [{**captured, 'requiredForRegeneration': True}],
                'synthesisCoarseFraming': {'sourceObservations': plain_path},
                'historicalReportInputs': {'reports': [captured]},
            }}
            track_path.write_text(json.dumps(track), encoding='utf8')
            with patch.object(evidence.sys, 'argv', ['evidence', 'generate']):
                evidence.main()
            self.assertEqual(json.loads((root / probe['path']).read_bytes())['lineage']['observations'],
                             captured)
            changed = json.loads(track_path.read_bytes())['evidence']
            self.assertEqual(changed['generatorInputs'][0], {
                'path': observation['path'], 'sha256': evidence.digest(stored.read_bytes()),
                'requiredForRegeneration': True,
            })
            self.assertEqual(changed['synthesisCoarseFraming']['sourceObservations'], observation['path'])
            self.assertEqual(changed['historicalReportInputs']['reports'], [captured])
            changed['generatorInputs'][0]['path'] = 'web/content/snapshot.source-track.json'
            track_path.write_text(json.dumps({'evidence': changed}), encoding='utf8')
            with patch.object(evidence.sys, 'argv', ['evidence', 'generate']), self.assertRaises(ValueError):
                evidence.main()


class CurrentTrackProjectionTests(unittest.TestCase):
    def setUp(self):
        self.old_path = 'web/content/review.observations.json'
        self.new_path = 'web/content/canonical-native/review.observations.json.gz'
        plain = b'{"frames":[]}\n'
        self.wire = evidence.encode_observations(plain)
        self.old_sha = evidence.digest(plain)
        self.manifest = {'derivatives': [{
            'originalPath': self.old_path, 'path': self.new_path, 'contentEncoding': 'gzip',
        }]}

    def input_record(self, required):
        return json.dumps({
            'path': self.old_path, 'sha256': self.old_sha, 'requiredForRegeneration': required,
        }, separators=(',', ':')).encode('utf8')

    def project(self, raw):
        return evidence.current_track_inputs(
            raw, 'projection.json', self.manifest, {self.new_path: self.wire}, {})

    def test_duplicate_projection_containers_and_authority_leaves_fail_closed(self):
        false = self.input_record(False)
        true = self.input_record(True)
        old_path = json.dumps(self.old_path).encode('utf8')
        sha = json.dumps(self.old_sha).encode('ascii')
        cases = [
            ('generatorInputs-false-true', b'{"evidence":{"generatorInputs":[' + false
             + b'],"generatorInputs":[' + true + b']}}'),
            ('generatorInputs-true-false', b'{"evidence":{"generatorInputs":[' + true
             + b'],"generatorInputs":[' + false + b']}}'),
            ('evidence', b'{"evidence":{"generatorInputs":[' + false
             + b']},"evidence":{"generatorInputs":[' + true + b']}}'),
            ('input-path', b'{"evidence":{"generatorInputs":[{"path":' + old_path
             + b',"path":' + old_path + b',"sha256":' + sha + b',"requiredForRegeneration":true}]}}'),
            ('input-sha', b'{"evidence":{"generatorInputs":[{"path":' + old_path
             + b',"sha256":' + sha + b',"sha256":' + sha + b',"requiredForRegeneration":true}]}}'),
            ('input-required', b'{"evidence":{"generatorInputs":[{"path":' + old_path
             + b',"sha256":' + sha + b',"requiredForRegeneration":false,"requiredForRegeneration":true}]}}'),
        ]
        for label in ('analysisStationaryFrontCamera', 'synthesisCoarseFraming', 'synthesisWheelFraming'):
            key = json.dumps(label).encode('ascii')
            record = b'{"sourceObservations":' + old_path + b'}'
            cases.append((label + '-container', b'{"evidence":{' + key + b':' + record
                          + b',' + key + b':' + record + b'}}'))
            cases.append((label + '-leaf', b'{"evidence":{' + key + b':{"sourceObservations":'
                          + old_path + b',"sourceObservations":' + old_path + b'}}}'))
        for label, raw in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.project(raw)

    def test_inactive_input_duplicates_remain_byte_exact_beside_active_input(self):
        old_path = json.dumps(self.old_path).encode('utf8')
        sha = json.dumps(self.old_sha).encode('ascii')
        older_sha = json.dumps(evidence.digest(b'{"frames":[{"frame":0}]}\n')).encode('ascii')
        for required in (b',"requiredForRegeneration":false', b''):
            with self.subTest(required=required):
                captured = (b'{"path":"web/content/captured-older.observations.json","path":' + old_path
                            + b',"sha256":' + older_sha + b',"sha256":' + sha
                            + required + b',"n":1.2300e-09}')
                raw = (b'{"evidence":{"generatorInputs":[' + captured + b','
                       + self.input_record(True) + b']}}')
                changed = self.project(raw)
                self.assertIn(captured, changed)
                records = json.loads(changed)['evidence']['generatorInputs']
                self.assertEqual(records[1], {
                    'path': self.new_path, 'sha256': evidence.digest(self.wire), 'requiredForRegeneration': True,
                })

    def test_unrelated_archival_duplicates_remain_byte_exact_during_current_projection(self):
        false = self.input_record(False)
        archive = (b'"archive":{"evidence":{"generatorInputs":[' + false
                   + b'],"generatorInputs":[' + false + b']},"n":1.2300e-09},'
                   b'"archive":{"note":"captured duplicate"}')
        raw = b'{' + archive + b',"evidence":{"generatorInputs":[' + self.input_record(True) + b']}}'
        changed = self.project(raw)
        self.assertIn(archive, changed)
        record = json.loads(changed)['evidence']['generatorInputs'][0]
        self.assertEqual(record, {
            'path': self.new_path, 'sha256': evidence.digest(self.wire), 'requiredForRegeneration': True,
        })


if __name__ == '__main__':
    unittest.main()
