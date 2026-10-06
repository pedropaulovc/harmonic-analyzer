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
NATIVE = re.compile(r'(?<![/\w:-])harmonic-analyzer/([a-z0-9-]+)/([a-z0-9-]+)(/mesh_[0-9_]+)?')
PRESERVATION = ('All original numeric JSON tokens retained byte-for-byte. Only '
                'identity/dependency strings translated; no geometric re-export '
                'or renderer/camera requalification.')
SCOPE = 'Current consumer code/data input hash only; not a claim of geometric or GPU/source verification.'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    encoded = {json.dumps(old).encode('utf8') for old in replacements}
    def replace(match):
        raw = match[0]
        if raw not in encoded and b'web/content/' not in raw and b'harmonic-analyzer/' not in raw:
            return raw
        value = json.loads(raw)
        changed = replacements.get(value, value)
        if path_pattern is not None and changed == value:
            changed = path_pattern.sub(lambda m: member_paths[m[0]], changed)
        if native is not None:
            changed = native(changed)
        if changed == value:
            return raw
        return json.dumps(changed, ensure_ascii=False, separators=(',', ':')).encode('utf8')
    return STRING.sub(replace, data)


def native_mapper(mapping, archived):
    stems = {row['old_stem']: row['new_stem'] for row in mapping['identities']}
    variants = sorted(mapping['variants'], key=lambda row: -len(row['old_prefix']))
    ordered_stems = sorted(stems, key=len, reverse=True)
    def component(value):
        if value in stems:
            return stems[value]
        for old in ordered_stems:
            suffix = value[len(old):]
            if value.startswith(old) and re.fullmatch(r'-[0-9]+', suffix):
                return stems[old] + suffix
        for variant in variants:
            old = variant['old_prefix']
            if value.startswith(old):
                return variant['new_prefix'] + value[len(old):]
        return None
    def translate(value):
        def replace(match):
            original = match[0]
            if original in archived:
                return 'archived-not-current:' + original
            assembly, part, mesh = match.groups()
            mapped = component(part)
            if assembly not in stems or mapped is None:
                raise ValueError(f'Undeclared native binding: {original}')
            return stems['harmonic-analyzer'] + '/' + stems[assembly] + '/' + mapped + (mesh or '')
        value = value.replace('/harmonic-analyzer/models/harmonic-analyzer.glb',
                              '/harmonic-analyzer/models/' + stems['harmonic-analyzer'] + '.glb')
        return NATIVE.sub(replace, value)
    return translate


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
            body = strings(raw, replacements, native_mapper(mapping, set(row['archivedNativeBindings'])))
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
        for row in manifest['canonicalConsumerInputs']:
            row['sha256'] = digest(file_path(row['path']).read_bytes())
        file_path(MANIFEST).write_bytes((json.dumps(manifest, indent=2) + '\n').encode('utf8'))
    else:
        require(digest(mapping_bytes), manifest['mappingSha256'], 'mapping SHA')
        for row in manifest['derivatives']:
            data = file_path(row['path']).read_bytes()
            require(digest(data), row['sha256'], row['path'] + ' derivative SHA')
            if data != outputs[row['path']]:
                raise ValueError(row['path'] + ': deterministic byte replay differs')
        if updates:
            raise ValueError('Stale current consumer pins: ' + ', '.join(updates))
        for row in manifest['canonicalConsumerInputs']:
            require(digest(file_path(row['path']).read_bytes()), row['sha256'], row['path'] + ' current consumer SHA')
    print(f'{args.command}: {len(outputs)} identity derivatives; immutable/numeric/current seals checked; no geometry qualification')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print(f'canonical-native evidence: {error}', file=sys.stderr)
        raise SystemExit(1)
