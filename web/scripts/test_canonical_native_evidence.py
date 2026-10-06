"""Offline identity grammar/transaction regressions; run by the coordinating root."""
import importlib.util
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


if __name__ == '__main__':
    unittest.main()
