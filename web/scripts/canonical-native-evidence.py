#!/usr/bin/env python3
"""Offline identity-only evidence replay; never qualifies current geometry.

The immutable originals, portable CAD map and manifest are the only inputs.
JSON numbers are lexical bytes, not floating-point values. Historical producer
snapshots are hashed only, never imported or executed. See web/README.md.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = 'web/content/canonical-native/manifest.json'
MAP = 'cad/config/identity-migration-map.json'
STRING = re.compile(rb'"(?:[^"\\]|\\.)*"')
TOKEN = re.compile(rb'"(?:[^"\\]|\\.)*"|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?')
NATIVE = re.compile(r'(?<![/\w:-])harmonic-analyzer/[^\s"\'<>`,;:()\[\]{}]+')
MESH = re.compile(r'mesh(?:_[0-9]+(?:_[0-9]+)*)?')
PRESERVATION = ('All original numeric JSON tokens retained byte-for-byte. Only '
                'identity/dependency strings translated; no geometric re-export '
                'or renderer/camera requalification.')
SCOPE = ('Current consumer code/data input SHA-256 after CRLF-to-LF normalization only; '
         'not a claim of byte identity, geometric or GPU/source verification.')
CONSUMER_NORMALIZATION = 'CRLF-to-LF'


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


def numbers(data: bytes) -> str:
    result = hashlib.sha256()
    for match in TOKEN.finditer(data):
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
    """Diagnostic-only object representation retaining duplicate members."""


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
        case_name = location == 'value' and re.fullmatch(
            r'\$\["independentSourceCalibration"\]\["sourceNonIdentifiableFixedPartQualification"\]'
            r'\["cases"\]\[[0-9]+\]\["name"\]', path) is not None
        if case_name and value.startswith('negative-native-'):
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
        for match in NATIVE.finditer(json.loads(token[0])):
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


def replay(manifest, mapping_bytes):
    mapping = json.loads(mapping_bytes)
    require(mapping['schema_version'], manifest['mappingSchemaVersion'], 'mapping schema')
    rows = manifest['derivatives']
    by_sha = {row['originalSha256']: row for row in rows}
    paths = {row['originalPath']: row['path'] for row in rows}
    originals = {}
    dependencies = {}
    for row in rows:
        name = row['path']
        if not name.startswith('web/content/canonical-native/') or '/historical-code/' in name:
            raise ValueError(f'Not a derivative destination: {name}')
        if name == row['originalPath']:
            raise ValueError(f'Original is an output: {name}')
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
                replacements[parent['originalSha256']] = digest(outputs[dependency])
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
            if name.endswith('.observations.json'):
                output = compact(output)
            outputs[name] = output
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
                raise ValueError('SHA pin must be a plain quoted Python string')
            edits.append((start, end, quote + replacements[node.value].encode('ascii') + quote))
    for start, end, value in sorted(edits, reverse=True):
        data = data[:start] + value + data[end:]
    return data


def consumer_updates(manifest, outputs):
    replacements = {row['sha256']: digest(outputs[row['path']]) for row in manifest['derivatives']}
    paths = {row['path'] for row in manifest['canonicalConsumerInputs'] if row['path'].endswith('.py')}
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'web/content').glob('*.source-track.json'))
    updates = {}
    for name in sorted(paths):
        data = file_path(name).read_bytes()
        changed = pin_code(data, replacements) if name.endswith('.py') else strings(data, replacements)
        if changed != data:
            updates[name] = changed
    return updates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('generate', 'validate', 'check'))
    args = parser.parse_args()
    manifest = json.loads(file_path(MANIFEST).read_bytes())
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
