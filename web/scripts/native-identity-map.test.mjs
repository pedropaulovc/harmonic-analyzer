import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { projectNativeIdentity, validateNativeIdentityProjection, nativeIdentityPaths, loadNativeIdentityMap, NATIVE_IDENTITY_MAP_SHA256 } from './native-identity-map.mjs'
import { optimizeModel, validateDecodedEquivalence } from './optimize-model.mjs'

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const align4 = value => Math.ceil(value / 4) * 4
function document() {
  return {
    asset: { version: '2.0', generator: 'Projection behavior fixture, not native CAD evidence' },
    scene: 0, scenes: [{ name: 'Default', nodes: [0, 1] }],
    nodes: [
      { name: 'current camera', camera: 0, extras: { description: 'harmonic-analyzer' } },
      { name: 'harmonic-analyzer', children: [2, 4] },
      { name: 'channel', children: [3] },
      { name: 'channel-spring-installed-stretch00-15', mesh: 0, translation: [1, 2, 3], extras: {
        nativeIdentity: { stem: 'channel-spring-installed', registry: 'cad/config/parts/channel-spring-installed.yaml' },
        nativePath: 'harmonic-analyzer/channel/channel-spring-installed-stretch00-15',
        nativePaths: ['harmonic-analyzer/channel/channel-spring-installed-stretch00-15'],
        description: 'channel-spring-installed', arbitrary: { note: 'harmonic-analyzer/channel' },
      } },
      { name: 'drive-train', children: [5] },
      { name: 'cone-gear--T120-2', mesh: 0, scale: [1, 1, 1] },
    ],
    cameras: [{ type: 'perspective', perspective: { yfov: 0.7, znear: 0.1 } }],
    meshes: [{ name: 'unchanged source mesh name', primitives: [{ attributes: { POSITION: 0 }, material: 0 }] }],
    materials: [{ name: 'unchanged source material name', pbrMetallicRoughness: { baseColorFactor: [1, 0, 0, 1] } }],
    buffers: [{ byteLength: 36 }], bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36, target: 34962 }],
    accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' }],
    extras: { description: 'harmonic-analyzer' },
  }
}
function serialize(json, binary = null) {
  if (!binary) {
    binary = Buffer.alloc(36)
    ;[0, 0, 0, 1, 0, 0, 0, 1, 0].forEach((value, index) => binary.writeFloatLE(value, index * 4))
  }
  const text = Buffer.from(typeof json === 'string' ? json : JSON.stringify(json)), length = align4(text.length), binLength = align4(binary.length)
  const bytes = Buffer.alloc(28 + length + binLength)
  bytes.writeUInt32LE(0x46546c67, 0); bytes.writeUInt32LE(2, 4); bytes.writeUInt32LE(bytes.length, 8)
  bytes.writeUInt32LE(length, 12); bytes.writeUInt32LE(0x4e4f534a, 16)
  bytes.fill(0x20, 20, 20 + length); text.copy(bytes, 20)
  bytes.writeUInt32LE(binLength, 20 + length); bytes.writeUInt32LE(0x004e4942, 24 + length); binary.copy(bytes, 28 + length)
  return bytes
}
function parse(bytes) {
  const length = bytes.readUInt32LE(12)
  return { json: JSON.parse(bytes.subarray(20, 20 + length)), binary: bytes.subarray(28 + length) }
}
async function directory(t) {
  const path = await mkdtemp(join(tmpdir(), 'native-identity-projection-'))
  t.after(() => rm(path, { recursive: true, force: true }))
  return path
}

test('projection preserves qualified native paths, raw bytes and all non-identity glTF semantics', async () => {
  const sourceDocument = document()
  // The number comes from the sole authoritative map rather than a duplicated fixture authority.
  const map = await loadNativeIdentityMap()
  const spring = map.rows.find(row => row.old_stem === 'channel-spring-installed')
  sourceDocument.nodes[3].extras.nativeIdentity.number = spring.old_number
  const raw = serialize(sourceDocument), untouched = Buffer.from(raw)
  const { canonicalBytes, identity, paths } = await projectNativeIdentity(raw)
  const canonical = parse(canonicalBytes)
  assert.deepEqual(raw, untouched)
  assert.equal(identity.mapSha256, NATIVE_IDENTITY_MAP_SHA256)
  assert.equal(identity.canonicalSha256, sha256(canonicalBytes))
  assert.equal(identity.renamedNodes, 5)
  assert.equal(identity.nodeCount, 6)
  assert.deepEqual(paths, [
    { source: 'harmonic-analyzer', canonical: 'ha-harmonic-analyzer' },
    { source: 'harmonic-analyzer/channel', canonical: 'ha-harmonic-analyzer/ch-channel' },
    { source: 'harmonic-analyzer/channel/channel-spring-installed-stretch00-15', canonical: 'ha-harmonic-analyzer/ch-channel/vn-channel-spring-installed-stretch00-15' },
    { source: 'harmonic-analyzer/drive-train', canonical: 'ha-harmonic-analyzer/dt-drive-train' },
    { source: 'harmonic-analyzer/drive-train/cone-gear--T120-2', canonical: 'ha-harmonic-analyzer/dt-drive-train/dt-cone-gear--T120-2' },
  ])
  assert.deepEqual(canonical.json.nodes[0], sourceDocument.nodes[0])
  assert.deepEqual(canonical.json.nodes[3].extras.nativeIdentity, { stem: spring.new_stem, number: spring.new_number, registry: spring.new_registry })
  assert.equal(canonical.json.nodes[3].extras.nativePath, paths[2].canonical)
  assert.equal(canonical.json.nodes[3].extras.description, sourceDocument.nodes[3].extras.description)
  assert.deepEqual(canonical.json.nodes[3].extras.arbitrary, sourceDocument.nodes[3].extras.arbitrary)
  assert.deepEqual(canonical.binary, parse(raw).binary)
  assert.deepEqual(canonical.json.nodes[3].extras.nativePaths, [paths[2].canonical])
  const proof = await validateNativeIdentityProjection(raw, canonicalBytes)
  assert.deepEqual(proof.identity, identity)
  assert.deepEqual(proof.paths, paths)
  const { optimizedBytes } = await optimizeModel(canonicalBytes)
  const equivalence = await validateDecodedEquivalence(canonicalBytes, optimizedBytes)
  assert.equal(equivalence.drawableInstances, 2)
  await assert.rejects(validateDecodedEquivalence(raw, optimizedBytes), /decoded equivalence failed for nodes/)
  const repeated = await projectNativeIdentity(canonicalBytes)
  assert.deepEqual(repeated.canonicalBytes, canonicalBytes)
  assert.equal(repeated.identity.renamedNodes, 0)
  assert.deepEqual(repeated.paths, paths.map(path => ({ source: path.canonical, canonical: path.canonical })))
})

test('renamed transforms retain JSON signed zero and parsed numeric semantics', async () => {
  // Author the numeric token directly: JSON.stringify(-0) would erase the
  // behavior under test before the production projector ever sees the source.
  const sourceFor = coordinate => serialize(`{
      "asset":{"version":"2.0"},
      "scene":0,"scenes":[{"nodes":[0]}],
      "buffers":[{"byteLength":36}],
      "nodes":[{"name":"harmonic-analyzer","translation":[${coordinate},2,3],
        "extras":{"negativeZero":-0,"-0":"literal -0, quoted \\"-0\\", slash \\\\",
          "large":9007199254740993,"representable":9007199254740994,
          "nested":[null,true,{"value":-0}]}}]
    }`)
  for (const coordinate of ['1', '-0']) {
    const raw = sourceFor(coordinate)
    const before = parse(raw)
    const { canonicalBytes, identity } = await projectNativeIdentity(raw)
    const after = parse(canonicalBytes)
    assert.equal(after.json.nodes[0].name, 'ha-harmonic-analyzer')
    assert.equal(identity.renamedNodes, 1)
    assert.equal(Object.is(after.json.nodes[0].translation[0], -0), coordinate === '-0')
    assert.equal(Object.is(after.json.nodes[0].extras.negativeZero, -0), true)
    assert.equal(Object.is(after.json.nodes[0].extras.nested[2].value, -0), true)
    assert.deepEqual(after.json.nodes[0].extras, before.json.nodes[0].extras)
    assert.deepEqual(after.binary, before.binary)
    const proof = await validateNativeIdentityProjection(raw, canonicalBytes)
    assert.deepEqual(proof.identity, identity)
    assert.deepEqual((await projectNativeIdentity(canonicalBytes)).canonicalBytes, canonicalBytes)
    // The independent oracle must still reject losing the sign, rather than
    // treating -0 and +0 as interchangeable to make projection pass.
    if (coordinate === '-0') {
      const positiveZero = await projectNativeIdentity(sourceFor('0'))
      await assert.rejects(validateNativeIdentityProjection(raw, positiveZero.canonicalBytes), /unauthorized glTF semantic change/)
    }
  }
})

test('unknown identities, wrong assembly contexts, malformed qualifiers, collisions and mixed epochs refuse', async () => {
  for (const [change, expected] of [
    [json => { json.nodes[5].name = 'unapproved-part-2' }, /unknown native node/],
    [json => { json.nodes[5].name = 'magnifying-lever-2' }, /not authorized in assembly/],
    [json => { json.nodes[5].name = 'cone-gear--T120-0' }, /unknown native node/],
    [json => { json.nodes[3].name = 'channel-spring-installed-stretch000-15' }, /unknown native node/],
    [json => { json.nodes.push({ name: 'cone-gear--T120-2' }); json.nodes[4].children.push(6) }, /colliding native path/],
    [json => { json.nodes[5].name = 'dt-cone-gear--T120-2' }, /mixed legacy and canonical/],
    [json => { json.nodes[3].extras.nativePath = 'ha-harmonic-analyzer/ch-channel/vn-channel-spring-installed-stretch00-15' }, /mixed legacy and canonical/],
    [json => { json.nodes[3].extras.nativePath = 'harmonic-analyzer/channel/nonexistent-1' }, /unknown native identity extra/],
    [json => { json.nodes.push({ name: 'non-native-a', children: [7] }, { name: 'non-native-b', children: [6] }) }, /cyclic/],
  ]) {
    const json = document()
    change(json)
    await assert.rejects(projectNativeIdentity(serialize(json)), expected)
  }
})

test('independent projection proof rejects geometry, accessor, hierarchy, material and transform changes', async () => {
  const json = document()
  const raw = serialize(json), { canonicalBytes } = await projectNativeIdentity(raw)
  for (const change of [
    model => { model.binary.writeFloatLE(9, 0) },
    model => { model.json.accessors[0].componentType = 5125 },
    model => { model.json.nodes[3].translation[0] += 1 },
    model => { model.json.nodes[1].children.reverse() },
    model => { model.json.materials[0].pbrMetallicRoughness.baseColorFactor[0] = 0.5 },
    model => { model.json.meshes[0].name = 'unauthorized mesh rename' },
    model => { model.json.nodes[3].extras.description = 'unauthorized annotation rewrite' },
    model => { model.json.nodes[3].extras.nativeIdentity.unapprovedAnnotation = 'new annotation' },
    model => { model.json.nodes[3].extras.nativePaths.push('unapproved-path') },
  ]) {
    const altered = parse(Buffer.from(canonicalBytes))
    change(altered)
    await assert.rejects(validateNativeIdentityProjection(raw, serialize(altered.json, altered.binary)), /unauthorized glTF semantic change|binary payload/)
  }
})

test('map digest tampering refuses before projection and CLI stream hashes match canonical bytes', async t => {
  const dir = await directory(t)
  const mapPath = join(dir, 'tampered-map.json')
  const mapBytes = await readFile(new URL('../../cad/config/identity-migration-map.json', import.meta.url))
  await writeFile(mapPath, Buffer.concat([mapBytes, Buffer.from('\n')]))
  const json = document()
  const raw = serialize(json)
  await assert.rejects(projectNativeIdentity(raw, { mapPath }), /map SHA256 mismatch/)
  const modelPath = join(dir, 'immutable-raw.glb')
  await writeFile(modelPath, raw)
  const projection = await projectNativeIdentity(raw)
  const streamed = await nativeIdentityPaths(modelPath)
  assert.equal(streamed.rawSha256, sha256(raw))
  assert.deepEqual(streamed.identity, projection.identity)
  assert.deepEqual(streamed.paths, projection.paths)
  const cli = JSON.parse(execFileSync(process.execPath, [fileURLToPath(new URL('./native-identity-map.mjs', import.meta.url)), '--model', modelPath, '--paths-only'], { encoding: 'utf8' }))
  assert.deepEqual(cli, streamed)
  assert.deepEqual(await readFile(modelPath), raw)
  await writeFile(modelPath, projection.canonicalBytes)
  const canonical = await nativeIdentityPaths(modelPath)
  assert.equal(canonical.rawSha256, projection.identity.canonicalSha256)
  assert.equal(canonical.identity.canonicalSha256, projection.identity.canonicalSha256)
  assert.equal(canonical.identity.renamedNodes, 0)
})

test('qualified BOM numbers and lowercase component configurations preserve their exact suffixes', async () => {
  const map = await loadNativeIdentityMap()
  const cone = map.rows.find(row => row.old_stem === 'cone-gear')
  const json = document()
  json.nodes[5].name = 'cone-gear--t006-7'
  json.nodes[5].extras = { nativeIdentity: { number: `${cone.old_number}-T006` }, description: `${cone.old_number}-T006` }
  const raw = serialize(json), { canonicalBytes } = await projectNativeIdentity(raw)
  const canonical = parse(canonicalBytes).json
  assert.equal(canonical.nodes[5].name, 'dt-cone-gear--t006-7')
  assert.equal(canonical.nodes[5].extras.nativeIdentity.number, 'MHA-DT-003-T006')
  assert.equal(canonical.nodes[5].extras.description, `${cone.old_number}-T006`)
  await validateNativeIdentityProjection(raw, canonicalBytes)
  const repeated = await projectNativeIdentity(canonicalBytes)
  assert.deepEqual(repeated.canonicalBytes, canonicalBytes)
  assert.equal(parse(repeated.canonicalBytes).json.nodes[5].extras.nativeIdentity.number, 'MHA-DT-003-T006')
  for (const number of ['MHA-999-T006', `${cone.old_number}-T6`, `${cone.new_number}-T006`]) {
    const altered = structuredClone(json)
    altered.nodes[5].extras.nativeIdentity.number = number
    await assert.rejects(projectNativeIdentity(serialize(altered)), /unknown or ambiguous native number|mixed legacy and canonical/)
  }
})

test('the pinned CAD map translates overlapping assembly tokens in their declared field namespaces', async () => {
  const map = await loadNativeIdentityMap()
  const root = map.rows.find(row => row.old_stem === 'harmonic-analyzer')
  const frame = map.rows.find(row => row.old_stem === 'frame')
  const moduleName = path => path.split('/').at(-1).slice(0, -3)
  const json = document()
  json.nodes[1].children.push(6)
  json.nodes.push({ name: frame.old_stem })
  function nativeExtras(row, path) {
    return {
      nativeIdentity: {
        stem: row.old_stem, underscore: row.old_underscore, assembly: row.old_underscore,
        number: row.old_number, registry: row.old_registry, builder: row.old_builder,
        file: row.old_registry, module: moduleName(row.old_builder),
        name: row.old_stem, path,
      },
      nativePath: path, nativePaths: [path], description: row.old_stem,
    }
  }
  json.nodes[1].extras = nativeExtras(root, root.old_stem)
  json.nodes[6].extras = nativeExtras(frame, `${root.old_stem}/${frame.old_stem}`)
  const raw = serialize(json), { canonicalBytes } = await projectNativeIdentity(raw)
  const canonical = parse(canonicalBytes).json
  for (const [index, row, path] of [
    [1, root, root.new_stem],
    [6, frame, `${root.new_stem}/${frame.new_stem}`],
  ]) {
    assert.deepEqual(canonical.nodes[index].extras.nativeIdentity, {
      stem: row.new_stem, underscore: row.new_underscore, assembly: row.new_underscore,
      number: row.new_number, registry: row.new_registry, builder: row.new_builder,
      file: row.new_registry, module: moduleName(row.new_builder),
      name: row.new_stem, path,
    })
    assert.equal(canonical.nodes[index].extras.nativePath, path)
    assert.deepEqual(canonical.nodes[index].extras.nativePaths, [path])
    assert.equal(canonical.nodes[index].extras.description, row.old_stem)
  }
  assert.notEqual(canonical.nodes[6].extras.nativeIdentity.stem, canonical.nodes[6].extras.nativeIdentity.underscore)
  await validateNativeIdentityProjection(raw, canonicalBytes)
  assert.deepEqual((await projectNativeIdentity(canonicalBytes)).canonicalBytes, canonicalBytes)
  for (const [field, wrongNamespace] of [
    ['underscore', frame.new_stem],
    ['path', frame.old_registry],
    ['registry', `${root.old_stem}/${frame.old_stem}`],
    ['name', root.old_underscore],
  ]) {
    const altered = structuredClone(json)
    altered.nodes[6].extras.nativeIdentity[field] = wrongNamespace
    await assert.rejects(projectNativeIdentity(serialize(altered)), /unknown native identity extra/)
  }
})
