#!/usr/bin/env python3
"""Offline identity-only evidence replay; never qualifies current geometry.

The immutable originals, portable CAD map and manifest are the only inputs.
JSON numbers are lexical bytes, not floating-point values. Historical producer
snapshots are hashed only, never imported or executed. See web/README.md.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'web/content/canonical-native/manifest.json'
MAP = 'cad/config/identity-migration-map.json'
STRING = re.compile(rb'"(?:[^"\\]|\\.)*"')
STRUCTURE = re.compile(rb'"(?:[^"\\]|\\.)*"|[{}]')
TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
NATIVE = re.compile(r'(?<![/\w:-])harmonic-analyzer/[^\s"\'<>`,;:()\[\]{}]+')
MESH = re.compile(r'mesh(?:_[0-9]+(?:_[0-9]+)*)?')
PRESERVATION = ('All original numeric JSON tokens retained byte-for-byte. Only '
                'identity/dependency strings translated; no geometric re-export '
                'or renderer/camera requalification.')
SCOPE = ('Current consumer code/data input SHA-256 after CRLF-to-LF normalization only; '
         'detects live consumer drift, not captured producer lineage, byte identity, '
         'geometric or GPU/source verification.')
CONSUMER_NORMALIZATION = 'CRLF-to-LF'
CURRENT_OBSERVATION_LABELS = ('analysisStationaryFrontCamera', 'synthesisCoarseFraming', 'synthesisWheelFraming')
HISTORICAL_PRODUCER_USAGE = 'historical-producer-lineage'
HISTORICAL_PRODUCER_ROLES = ('generator', 'shared-source-selector', 'native-anchor-motion-lineage')
FRESH_CONSUMER_INPUTS = (
    'web/scripts/fresh-source-observations.py',
    'web/scripts/fresh-source-observations.mjs',
    'web/scripts/fresh-source-observations.schema.json',
    'web/scripts/fresh-source-tracks.py',
    'web/scripts/source-observations.schema.json',
    'web/source-visibility.mjs',
    'web/native-line-checks.mjs',
    'web/scripts/executed-point-motion.mjs',
    'web/scripts/native-identity-map.mjs',
    'web/src/native-primitive-snapshot.ts',
    'web/src/source-assembly.ts',
    'web/src/native-landmark-eligibility.ts',
    'web/src/native-target-shader-feedback.ts',
    'web/scripts/current-native-eligibility-report.mjs',
    'web/scripts/json-report-writer.mjs',
    'web/scripts/current-first-surface.py',
    'web/scripts/canonical-native-evidence.py',
)
CURRENT_INVENTORY_PATH = 'web/content/v39-source/native-inventory.json'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def consumer_digest(data: bytes) -> str:
    # Current editable text inputs follow Git newline conversion. Evidence,
    # original/snapshot certificates and dependency pins always use digest().
    return digest(data.replace(b'\r\n', b'\n'))


def file_path(name: str) -> Path:
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or Path(name).is_absolute():
        raise ValueError(f'Not a repository-relative input: {name}')
    return path


def numbers(data: bytes, start: int = 0) -> str:
    result = hashlib.sha256()
    for match in TOKEN.finditer(data, start):
        if not match[0].startswith(b'"'):
            result.update(match[0])
            result.update(b'\n')
    return result.hexdigest()


def compact(data: bytes) -> bytes:
    # Keep every quoted token verbatim; strip ONLY JSON whitespace between them.
    return re.sub(rb'"(?:[^"\\]|\\.)*"|[ \t\r\n]+',
                  lambda match: match[0] if match[0].startswith(b'"') else b'',
                  data) + b'\n'


def strings(data: bytes, replacements: dict[str, str], native=None) -> bytes:
    member_paths = {old: new for old, new in replacements.items() if old.startswith('web/content/')}
    path_pattern = (re.compile(r'(?<![\w-])(?:' + '|'.join(re.escape(p) for p in member_paths)
                               + r')(?![\w./-])') if member_paths else None)
    def replace(match):
        raw = match[0]
        # Decode keys as well as values, including escaped slashes/unicode.
        # Only changed string tokens are serialized; number tokens never are.
        value = json.loads(raw)
        changed = replacements.get(value, value)
        if path_pattern is not None and changed == value:
            changed = path_pattern.sub(lambda m: member_paths[m[0]], changed)
        if native is not None:
            changed = native(changed, match.start())
        if changed == value:
            return raw
        return json.dumps(changed, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    return STRING.sub(replace, data)


class UndeclaredNativeBinding(ValueError):
    def __init__(self, binding, reason):
        self.binding = binding
        self.reason = reason
        super().__init__(f'Undeclared native binding: {binding}: {reason}')


class NativeBindingInventoryError(ValueError):
    def __init__(self, occurrences):
        self.occurrences = occurrences
        super().__init__('Undeclared native bindings:\n' + json.dumps(
            {'occurrences': occurrences}, ensure_ascii=False, indent=2))


class ObjectPairs(list):
    """JSON object representation retaining duplicates for context and authority checks."""


def native_mapper(mapping, archived):
    stems = {row['old_stem']: row['new_stem'] for row in mapping['identities']}
    variants = sorted(mapping['variants'], key=lambda row: -len(row['old_prefix']))
    ordered_stems = sorted(stems, key=len, reverse=True)
    def component(value, selector=False):
        if value in stems:
            return stems[value]
        for old in ordered_stems:
            suffix = value[len(old):]
            if value.startswith(old) and ((selector and suffix == '-*') or re.fullmatch(r'-[0-9]+', suffix)):
                return stems[old] + suffix
        for variant in variants:
            old = variant['old_prefix']
            if value.startswith(old) and re.fullmatch(r'[a-z0-9-]*', value[len(old):]):
                return variant['new_prefix'] + value[len(old):]
        return None
    def translate(value, offset=None, selector=False):
        def replace(match):
            # A sentence's terminating period is not a path segment. Interior
            # periods, wildcards, @ annotations and extra segments stay whole
            # so unsupported locators cannot be translated by partial match.
            original = match[0].rstrip('.')
            punctuation = match[0][len(original):]
            if original in archived:
                return 'archived-not-current:' + original + punctuation
            segments = original.split('/')[1:]
            mesh = ''
            if segments and MESH.fullmatch(segments[-1]):
                mesh = '/' + segments.pop()
            if len(segments) == 1:
                mapped = component(segments[0], selector)
                if mapped is not None:
                    return stems['harmonic-analyzer'] + '/' + mapped + mesh + punctuation
            elif len(segments) == 2:
                assembly, part = segments
                role = ''
                # Actual addPartInstance locators, declared in scene.ts and its
                # sealed historical producer; not general-purpose CAD aliases.
                if assembly == 'paper-drive' and part in (
                        'transgear-removable-3@upper', 'transgear-removable-3@crank'):
                    part, role_name = part.split('@')
                    role = '@' + role_name
                mapped = component(part, selector)
                if assembly in stems and mapped is not None:
                    return stems['harmonic-analyzer'] + '/' + stems[assembly] + '/' + mapped + role + mesh + punctuation
            raise UndeclaredNativeBinding(original, 'unsupported path form or undeclared identity segment')
        value = value.replace('/harmonic-analyzer/models/harmonic-analyzer.glb',
                              '/harmonic-analyzer/models/' + stems['harmonic-analyzer'] + '.glb')
        return NATIVE.sub(replace, value)
    return translate


def native_string_contexts(raw):
    """Yield decoded string-token contexts in lexical order, retaining duplicates."""
    class NumberLexeme(str):
        pass
    def walk(value, path, member=None, hypothesis=False):
        if isinstance(value, str) and not isinstance(value, NumberLexeme):
            yield value, path, member, 'value', hypothesis
        elif isinstance(value, ObjectPairs):
            for index, (key, child) in enumerate(value):
                child_path = path + '[' + json.dumps(key, ensure_ascii=False) + ']'
                yield key, child_path, index, 'key', False
                unbound_family = (key == 'candidatePartFamily'
                                  and re.fullmatch(r'\$\["visibleMotionFeatures"\]\["[^"]+"\]', path) is not None
                                  and [v for k, v in value if k == 'partPath'] == [None])
                yield from walk(child, child_path, index, unbound_family)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, f'{path}[{index}]')
    yield from walk(json.loads(raw, object_pairs_hook=ObjectPairs,
                               parse_float=NumberLexeme, parse_int=NumberLexeme), '$')


def negative_native_case_label(value, path, location):
    return (location == 'value' and value.startswith('negative-native-') and re.fullmatch(
        r'\$\["independentSourceCalibration"\]\["sourceNonIdentifiableFixedPartQualification"\]'
        r'\["cases"\]\[[0-9]+\]\["name"\]', path) is not None)


def contextual_native_mapper(raw, source, mapping, archived):
    translate = native_mapper(mapping, archived)
    contexts = {}
    tokens = list(STRING.finditer(raw))
    decoded = list(native_string_contexts(raw))
    require(len(tokens), len(decoded), source + ' string context inventory')
    for token, (value, path, member, location, hypothesis) in zip(tokens, decoded):
        require(json.loads(token[0]), value, source + ' string context order')
        contexts[token.start()] = (path, member, location, hypothesis)
    def transform(value, offset):
        path, _, location, hypothesis = contexts[offset]
        # This diagnostic schema explicitly contains family selectors rather
        # than concrete drawable bindings, including the accompanying error.
        selector = location == 'value' and re.fullmatch(
            r'\$\["independentSourceCalibration"\]\["sourceNonIdentifiableFixedPartQualification"\]'
            r'\["cases"\]\[[0-9]+\](?:\["nativePartPaths"\]\[[0-9]+\]|\["error"\])', path) is not None
        if negative_native_case_label(value, path, location):
            # The immutable case label embeds its nativePartPaths locator after
            # this schema-specific prefix; it is not a general prose alias.
            return 'negative-native-' + translate(value[len('negative-native-'):])
        if hypothesis:
            # Unbound candidatePartFamily is a symbolic range hypothesis, not
            # a declared drawable. Translate only its known hierarchy; retain
            # the historical family symbol, never invent a CAD identity.
            stems = {row['old_stem']: row['new_stem'] for row in mapping['identities']}
            def family(match):
                binding = match[0].rstrip('.')
                grammar = re.fullmatch(
                    r'harmonic-analyzer/([a-z0-9-]+)/([a-z0-9-]+)-([0-9]+)\.\.([0-9]+)', binding)
                if grammar is None or grammar[1] not in stems or int(grammar[3]) > int(grammar[4]):
                    raise UndeclaredNativeBinding(binding, 'unsupported unbound family selector grammar')
                return (stems['harmonic-analyzer'] + '/' + stems[grammar[1]] + '/'
                        + grammar[2] + '-' + grammar[3] + '..' + grammar[4]
                        + match[0][len(binding):])
            return NATIVE.sub(family, value)
        return translate(value, selector=selector)
    return transform, contexts


def native_binding_occurrences(raw, source, mapping, archived):
    """Inventory only; the lexical raw-token transformer authors output bytes."""
    translate, contexts = contextual_native_mapper(raw, source, mapping, archived)
    occurrences = []
    for token in STRING.finditer(raw):
        path, member, location, _ = contexts[token.start()]
        value = json.loads(token[0])
        if negative_native_case_label(value, path, location):
            value = value[len('negative-native-'):]
        for match in NATIVE.finditer(value):
            try:
                translate(match[0], token.start())
            except UndeclaredNativeBinding as error:
                occurrence = {'sourcePacket': source, 'jsonPath': path,
                              'binding': error.binding, 'reason': error.reason,
                              'location': location}
                if member is not None:
                    occurrence['objectMemberIndex'] = member
                occurrences.append(occurrence)
    return occurrences


def require(actual, expected, label):
    if actual != expected:
        raise ValueError(f'{label}: expected {expected}, got {actual}')


def compressed_observations(row) -> bool:
    name = row['path']
    if row['originalPath'].endswith('.observations.json'):
        if not name.endswith('.observations.json.gz'):
            raise ValueError(f'Canonical observations must be gzip: {name}')
        require(row['contentEncoding'], 'gzip', name + ' content encoding')
        return True
    if name.endswith('.gz') or 'contentEncoding' in row or 'decodedSha256' in row:
        raise ValueError(f'Non-observation derivative must remain plain JSON: {name}')
    return False


def encode_observations(data: bytes) -> bytes:
    stored = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=stored, compresslevel=9, mtime=0) as compressed:
        compressed.write(data)
    return stored.getvalue()


def validate_json(data: bytes, name: str):
    def reject_constant(value):
        raise ValueError(f'{name}: invalid JSON numeric constant {value}')
    # Validation only: never turn lexical numbers into floats or serialize them.
    document = json.loads(data, parse_int=str, parse_float=str, parse_constant=reject_constant)
    if not isinstance(document, dict):
        raise ValueError(f'{name}: derivative JSON must be an object')
    return document


def decoded_derivative(row, data: bytes) -> bytes:
    if compressed_observations(row):
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError, zlib.error) as error:
            raise ValueError(f"{row['path']}: invalid gzip: {error}") from error
    document = validate_json(data, row['path'])
    header = document.get('identityDerivative')
    if not isinstance(header, dict):
        raise ValueError(f"{row['path']}: missing identity derivative provenance")
    for key in ('originalPath', 'originalSha256', 'originalNumericLexemeSha256', 'archivedNativeBindings'):
        require(header.get(key), row[key], row['path'] + ' provenance ' + key)
    opening = data.index(b'{')
    prefix = b'"identityDerivative":'
    start = opening + 1
    require(data[start:start + len(prefix)], prefix, row['path'] + ' provenance prefix')
    depth = 0
    for token in STRUCTURE.finditer(data, start + len(prefix)):
        if token[0] == b'{':
            depth += 1
        elif token[0] == b'}':
            depth -= 1
            if depth == 0:
                end = token.end()
                require(data[end:end + 1], b',', row['path'] + ' provenance separator')
                require(numbers(data, end + 1), row['originalNumericLexemeSha256'],
                        row['path'] + ' decoded numeric seal')
                break
    else:
        raise ValueError(f"{row['path']}: incomplete identity derivative provenance")
    return data


def replay(manifest, mapping_bytes):
    mapping = json.loads(mapping_bytes)
    require(mapping['schema_version'], manifest['mappingSchemaVersion'], 'mapping schema')
    rows = manifest['derivatives']
    by_sha = {row['originalSha256']: row for row in rows}
    # Captured evidence retains the baseline plaintext path/payload projection.
    paths = {row['originalPath']: row['path'][:-3] if compressed_observations(row) else row['path']
             for row in rows}
    originals = {}
    dependencies = {}
    for row in rows:
        name = row['path']
        if not name.startswith('web/content/canonical-native/') or '/historical-code/' in name:
            raise ValueError(f'Not a derivative destination: {name}')
        if name == row['originalPath']:
            raise ValueError(f'Original is an output: {name}')
        compressed_observations(row)
        raw = file_path(row['originalPath']).read_bytes()
        require(digest(raw), row['originalSha256'], row['originalPath'] + ' original SHA')
        require(numbers(raw), row['originalNumericLexemeSha256'], row['originalPath'] + ' numeric seal')
        originals[name] = raw
        dependencies[name] = sorted({by_sha[m[0][1:-1].decode('ascii')]['path']
                                     for m in re.finditer(rb'"[0-9a-f]{64}"', raw)
                                     if m[0][1:-1].decode('ascii') in by_sha})
    for row in manifest['historicalCodeSnapshots']:
        require(digest(file_path(row['path']).read_bytes()), row['sha256'], row['path'] + ' historical SHA')
    occurrences = []
    for row in sorted(rows, key=lambda row: row['originalPath']):
        occurrences.extend(native_binding_occurrences(
            originals[row['path']], row['originalPath'], mapping, set(row['archivedNativeBindings'])))
    if occurrences:
        raise NativeBindingInventoryError(occurrences)
    outputs = {}
    payload_shas = {}
    pending = list(rows)
    while pending:
        ready = [row for row in pending if all(p in outputs for p in dependencies[row['path']])]
        if not ready:
            raise ValueError('Cyclic original evidence dependencies: ' + ', '.join(r['path'] for r in pending))
        for row in ready:
            name = row['path']
            raw = originals[name]
            replacements = dict(paths)
            replacements['harmonic-analyzer'] = next(
                r['new_stem'] for r in mapping['identities'] if r['old_stem'] == 'harmonic-analyzer')
            historical = {}
            for dependency in dependencies[name]:
                parent = next(r for r in rows if r['path'] == dependency)
                replacements[parent['originalSha256']] = payload_shas[dependency]
                historical[parent['originalPath']] = parent['originalSha256']
            translate, _ = contextual_native_mapper(raw, row['originalPath'], mapping, set(row['archivedNativeBindings']))
            body = strings(raw, replacements, translate)
            require(numbers(body), row['originalNumericLexemeSha256'], name + ' derivative numeric seal')
            header = {
                'kind': 'materialized-canonical-native-identity-derivative',
                'originalSourceCommit': manifest['originalSourceCommit'],
                'originalPath': row['originalPath'], 'originalSha256': row['originalSha256'],
                'mappingSchemaVersion': manifest['mappingSchemaVersion'], 'mappingSha256': digest(mapping_bytes),
                'originalNumericLexemeSha256': row['originalNumericLexemeSha256'],
                'measurementPreservation': PRESERVATION,
                'archivedNativeBindings': row['archivedNativeBindings'],
                'historicalSourceDependencies': dict(sorted(historical.items())),
            }
            opening = body.index(b'{')
            output = body[:opening + 1] + b'"identityDerivative":' + json.dumps(
                header, ensure_ascii=False, separators=(',', ':')).encode('utf8') + b',' + body[opening + 1:]
            if compressed_observations(row):
                output = compact(output)
            validate_json(output, name)
            payload_shas[name] = digest(output)
            outputs[name] = encode_observations(output) if compressed_observations(row) else output
            pending.remove(row)
    return outputs


def pin_code(data: bytes, replacements: dict[str, str]) -> bytes:
    # AST-bound constant edits, not free-form substitutions in prose or source.
    source = data.decode('utf8')
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode('utf8')))
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in replacements:
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            raw = data[start:end]
            quote = raw[:1]
            if quote not in (b'"', b"'") or raw[-1:] != quote:
                raise ValueError('Dependency pin must be a plain quoted Python string')
            edits.append((start, end, quote + replacements[node.value].encode('ascii') + quote))
    for start, end, value in sorted(edits, reverse=True):
        data = data[:start] + value + data[end:]
    return data


def current_projection_fields(data: bytes, name: str):
    """Refuse duplicate authority members before selecting current projections."""
    document = json.loads(data, object_pairs_hook=ObjectPairs, parse_int=str, parse_float=str)
    def select(value, fields, path):
        if not isinstance(value, ObjectPairs):
            raise ValueError(name + ': current projection object expected at ' + path)
        selected = {}
        for key, child in value:
            if key not in fields:
                continue
            child_path = path + '[' + json.dumps(key) + ']'
            if key in selected:
                raise ValueError(name + ': duplicate current projection member at ' + child_path)
            selected[key] = child
        return selected
    root = select(document, ('evidence',), '$')
    if 'evidence' not in root:
        return {}
    current = select(root['evidence'], ('generatorInputs', *CURRENT_OBSERVATION_LABELS), '$["evidence"]')
    for label in CURRENT_OBSERVATION_LABELS:
        record = current.get(label)
        if isinstance(record, ObjectPairs):
            current[label] = select(record, ('sourceObservations',), '$["evidence"][' + json.dumps(label) + ']')
    if 'generatorInputs' in current:
        records = current['generatorInputs']
        if not isinstance(records, list) or isinstance(records, ObjectPairs):
            raise ValueError(name + ': current generatorInputs must be an array')
        current['generatorInputs'] = []
        for index, record in enumerate(records):
            path = f'$["evidence"]["generatorInputs"][{index}]'
            projected = select(record, ('requiredForRegeneration', 'usage'), path)
            if (projected.get('requiredForRegeneration') is True
                    or projected.get('usage') == HISTORICAL_PRODUCER_USAGE):
                projected.update(select(record, ('path', 'sha256', 'role', 'origin'), path))
                if 'origin' in projected:
                    projected['origin'] = select(
                        projected['origin'], ('sourceCommit', 'sourcePath', 'snapshotPath'), path + '["origin"]')
            current['generatorInputs'].append(projected)
    return current


def validate_historical_track_input(record, name, manifest):
    """Prior identity-migrated lineage is not original capture or a live pin."""
    require(record.get('requiredForRegeneration'), True, name + ' historical regeneration requirement')
    if record.get('role') not in HISTORICAL_PRODUCER_ROLES:
        raise ValueError(name + ': historical producer lineage requires a declared code role')
    path, sha = record.get('path'), record.get('sha256')
    origin = record.get('origin')
    if (not isinstance(path, str) or not path.endswith(('.py', '.ts'))
            or not isinstance(sha, str) or re.fullmatch(r'[0-9a-f]{64}', sha) is None
            or not isinstance(origin, dict)
            or not isinstance(origin.get('sourceCommit'), str)
            or re.fullmatch(r'[0-9a-f]{40}', origin['sourceCommit']) is None):
        raise ValueError(name + ': historical producer lineage requires exact SHA and Git origin')
    require(origin.get('sourcePath'), path, name + ' historical source path')
    snapshot = ('web/content/canonical-native/historical-code/' + sha + '/' + Path(path).name)
    require(origin.get('snapshotPath'), snapshot, name + ' historical snapshot path')
    certificates = [row for row in manifest['historicalCodeSnapshots'] if row['path'] == snapshot]
    require(len(certificates), 1, name + ' historical snapshot certificate count')
    certificate = certificates[0]
    require(certificate['sha256'], sha, name + ' historical snapshot certificate SHA')
    require(certificate.get('origin'), {
        'sourceCommit': origin['sourceCommit'], 'sourcePath': path,
    }, name + ' historical snapshot certificate origin')
    require(digest(file_path(snapshot).read_bytes()), sha, name + ' historical producer SHA')
    if not any(row['path'] == path for row in manifest['canonicalConsumerInputs']):
        raise ValueError(name + ': historical producer requires a separate current consumer seal: ' + path)


def current_track_inputs(data: bytes, name: str, manifest, outputs, code_updates) -> bytes:
    """Project live storage reads, preserving explicitly certified prior lineage."""
    current = current_projection_fields(data, name)
    artifacts = {row['originalPath']: row['path'] for row in manifest['derivatives']}
    observations = {row['path'][:-3]: row['path'] for row in manifest['derivatives']
                    if compressed_observations(row)}
    observations.update({row['originalPath']: row['path'] for row in manifest['derivatives']
                         if compressed_observations(row)})
    artifacts.update(observations)
    changes = {}
    # These labels come from actual current observation reads, not captured lineage.
    for label in CURRENT_OBSERVATION_LABELS:
        record = current.get(label, {})
        if isinstance(record, dict):
            old = record.get('sourceObservations')
            if isinstance(old, str) and old in observations:
                changes[f'$["evidence"]["{label}"]["sourceObservations"]'] = observations[old]
    for index, record in enumerate(current.get('generatorInputs', [])):
        usage = record.get('usage')
        if usage == HISTORICAL_PRODUCER_USAGE:
            validate_historical_track_input(record, name, manifest)
            continue
        if record.get('requiredForRegeneration') is True and usage not in (None, 'current-regeneration-input'):
            raise ValueError(name + ': unsupported required generator input usage: ' + str(usage))
        if record.get('requiredForRegeneration') is not True:
            continue
        if record.get('role') in HISTORICAL_PRODUCER_ROLES and usage is None:
            raise ValueError(name + ': required producer code must declare current or historical usage')
        old = record['path']
        if not isinstance(old, str) or not isinstance(record['sha256'], str):
            raise ValueError(name + ': current generator input requires path and SHA strings')
        path = artifacts.get(old, old)
        if path.endswith('.source-track.json'):
            raise ValueError(name + ': generated source track cannot be a regeneration input')
        if path in outputs:
            raw = outputs[path]
        elif path in code_updates:
            raw = code_updates[path]
        else:
            raw = file_path(path).read_bytes()
        prefix = f'$["evidence"]["generatorInputs"][{index}]'
        if path != old:
            changes[prefix + '["path"]'] = path
        sha = digest(raw)
        if sha != record['sha256']:
            changes[prefix + '["sha256"]'] = sha
    if not changes:
        return data
    contexts = {token.start(): path for token, (_, path, _, location, _) in zip(
        STRING.finditer(data), native_string_contexts(data)) if location == 'value' and path in changes}
    return strings(data, {}, lambda value, offset: changes.get(contexts.get(offset), value))


def consumer_updates(manifest, outputs):
    replacements = {row['sha256']: digest(outputs[row['path']]) for row in manifest['derivatives']}
    replacements.update({row['path'][:-3]: row['path'] for row in manifest['derivatives']
                         if compressed_observations(row)})
    paths = {row['path'] for row in manifest['canonicalConsumerInputs'] if row['path'].endswith('.py')}
    tracks = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'web/content').glob('*.source-track.json'))
    updates = {}
    for name in sorted(paths):
        data = file_path(name).read_bytes()
        changed = pin_code(data, replacements)
        if changed != data:
            updates[name] = changed
    for name in tracks:
        data = file_path(name).read_bytes()
        changed = current_track_inputs(data, name, manifest, outputs, updates)
        if changed != data:
            updates[name] = changed
    return updates


def validate_current_inventory_registration(manifest):
    """The exporter result is exact-byte data authority, never a text/code repin."""
    record = manifest.get('currentSourceInventory')
    if (not isinstance(record, dict) or set(record) != {'path', 'sha256'}
            or record['path'] != CURRENT_INVENTORY_PATH
            or not isinstance(record['sha256'], str)
            or re.fullmatch(r'[0-9a-f]{64}', record['sha256']) is None):
        raise ValueError('Current source inventory requires explicit independent registration')
    require(digest(file_path(record['path']).read_bytes()), record['sha256'],
            'exact current source inventory bytes')
    if any(row['path'] == CURRENT_INVENTORY_PATH for row in manifest['canonicalConsumerInputs']):
        raise ValueError('Current source inventory cannot be CRLF-normalized consumer code')


def compress_observations(names):
    """Store current authored JSON bytes before consumer seals are refreshed.

    The current inventory path defines the approved release authoring namespace.
    Updating that existing contract enables the next release; archived namespaces
    are not storage inputs. Schema and physical qualification remain with producers.
    """
    namespace = Path(CURRENT_INVENTORY_PATH).parent
    pending = []
    seen = set()
    for name in names:
        path = file_path(name)
        match = re.fullmatch(r'([A-Za-z0-9_-]{11})\.observations\.json', path.name)
        if (Path(name).parent != namespace or path.parent != ROOT / namespace
                or path.name != Path(name).name or match is None):
            raise ValueError(f'{name}: expected authored observations in {namespace}')
        if path in seen:
            raise ValueError(f'{name}: duplicate observation input')
        seen.add(path)
        target = path.with_name(path.name + '.gz')
        if target.is_symlink():
            raise ValueError(f'{name}: gzip destination must not be a symlink')
        data = path.read_bytes()
        document = validate_json(data, name)
        require(document.get('kind'), 'current-source-observations', name + ' record kind')
        source = document.get('source')
        if not isinstance(source, dict):
            raise ValueError(f'{name}: missing observation source identity')
        require(source.get('videoId'), match[1], name + ' source video identity')
        if 'identityDerivative' in document:
            raise ValueError(f'{name}: historical identity derivatives are not authored observations')
        pending.append((path, target, data, encode_observations(data)))
    results = []
    for path, target, data, encoded in pending:
        target.write_bytes(encoded)
        stored = target.read_bytes()
        decoded = gzip.decompress(stored)
        require(decoded, data, str(target) + ' exact decoded bytes')
        require(stored[:10], b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x02\xff',
                str(target) + ' deterministic gzip header')
        require(stored, encode_observations(decoded), str(target) + ' deterministic gzip stream')
        results.append({
            'sourcePath': path.relative_to(ROOT).as_posix(),
            'path': target.relative_to(ROOT).as_posix(),
            'contentEncoding': 'gzip',
            'sha256': digest(stored),
            'decodedSha256': digest(decoded),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('generate', 'validate', 'check', 'compress-observations'))
    parser.add_argument('paths', nargs='*', help='Repository-relative authored observation JSON paths')
    args = parser.parse_args()
    if args.command == 'compress-observations':
        if not args.paths:
            parser.error('compress-observations requires explicit observation JSON paths')
        print(json.dumps({
            'command': args.command,
            'observations': compress_observations(args.paths),
            'scope': 'Exact-byte storage only; no schema, physical or geometry qualification.',
        }, indent=2))
        return
    if args.paths:
        parser.error(f'{args.command} does not accept observation paths')
    manifest = json.loads(file_path(MANIFEST).read_bytes())
    validate_current_inventory_registration(manifest)
    inputs = manifest['canonicalConsumerInputs']
    paths = {row['path'] for row in inputs}
    if len(paths) != len(inputs):
        raise ValueError('Duplicate current consumer input paths')
    missing = sorted(set(FRESH_CONSUMER_INPUTS) - paths)
    if args.command == 'generate':
        inputs.extend({'path': path, 'sha256': '', 'scope': SCOPE} for path in missing)
    elif missing:
        raise ValueError('Missing fresh current consumer input seals: ' + ', '.join(missing))
    mapping_bytes = file_path(MAP).read_bytes()
    outputs = replay(manifest, mapping_bytes)
    updates = consumer_updates(manifest, outputs)
    if args.command == 'generate':
        for name, data in outputs.items():
            file_path(name).write_bytes(data)
        for name, data in updates.items():
            file_path(name).write_bytes(data)
        manifest['mappingSha256'] = digest(mapping_bytes)
        for row in manifest['derivatives']:
            row['sha256'] = digest(outputs[row['path']])
            if compressed_observations(row):
                row['decodedSha256'] = digest(decoded_derivative(row, outputs[row['path']]))
        manifest['canonicalConsumerHashNormalization'] = CONSUMER_NORMALIZATION
        for row in manifest['canonicalConsumerInputs']:
            row['sha256'] = consumer_digest(file_path(row['path']).read_bytes())
            row['scope'] = SCOPE
        file_path(MANIFEST).write_bytes((json.dumps(manifest, indent=2) + '\n').encode('utf8'))
    else:
        require(digest(mapping_bytes), manifest['mappingSha256'], 'mapping SHA')
        require(manifest['canonicalConsumerHashNormalization'], CONSUMER_NORMALIZATION,
                'current consumer hash normalization')
        mismatches = []
        for row in manifest['derivatives']:
            data = file_path(row['path']).read_bytes()
            try:
                decoded = decoded_derivative(row, data)
                if compressed_observations(row) and digest(decoded) != row['decodedSha256']:
                    mismatches.append(row['path'] + ': decoded SHA differs')
            except ValueError as error:
                mismatches.append(str(error))
            if digest(data) != row['sha256']:
                mismatches.append(row['path'] + ': derivative SHA differs')
            if data != outputs[row['path']]:
                mismatches.append(row['path'] + ': deterministic byte replay differs')
        if mismatches:
            raise ValueError('\n'.join(mismatches))
        if updates:
            raise ValueError('Stale current consumer pins: ' + ', '.join(updates))
        for row in manifest['canonicalConsumerInputs']:
            require(consumer_digest(file_path(row['path']).read_bytes()), row['sha256'],
                    row['path'] + ' normalized current consumer SHA')
    print(f'{args.command}: {len(outputs)} identity derivatives; immutable/numeric/current seals checked; no geometry qualification')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'canonical-native evidence: {error}', file=sys.stderr)
        raise SystemExit(1)
