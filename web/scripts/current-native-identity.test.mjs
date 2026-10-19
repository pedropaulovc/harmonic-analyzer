import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { readFile, writeFile, mkdtemp, mkdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import {
  CURRENT_NATIVE_IDENTITY_MAP_SHA256, CURRENT_NATIVE_IDENTITY_PROJECTION,
  projectCurrentNativePath, projectCurrentNativeNumber,
  projectCurrentNativeMetadata, projectCurrentNativeDocument, validateCurrentNativeIdentityTable,
} from '../current-native-identity.mjs'
import { validateCurrentNativeIdentityInputs, validateCurrentNativeIdentityProjection } from './current-native-identity-inputs.mjs'

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const table = JSON.parse(await readFile(new URL('../content/current-native-identities.json', import.meta.url), 'utf8'))
const inventory = JSON.parse(await readFile(new URL('../content/v39-source/native-inventory.json', import.meta.url), 'utf8'))
const cadMap = JSON.parse(await readFile(new URL('../../cad/config/current-identity-map.json', import.meta.url), 'utf8'))

async function isolatedProjection(t, fixtureTable) {
  const directory = await mkdtemp(join(tmpdir(), 'current-native-projection-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  await mkdir(join(directory, 'content'))
  await writeFile(join(directory, 'content/current-native-identities.json'), JSON.stringify(fixtureTable))
  const source = await readFile(new URL('../current-native-identity.mjs', import.meta.url), 'utf8')
  await writeFile(join(directory, 'current-native-identity.mjs'),
    source.replace(CURRENT_NATIVE_IDENTITY_MAP_SHA256, sha256(JSON.stringify(fixtureTable))))
  return import(pathToFileURL(join(directory, 'current-native-identity.mjs')).href)
}
const path = (parent, name) => `ha-harmonic-analyzer/${parent}/${name}`

test('current table pins exact historical/current source maps and a distinct semantic projection digest', async () => {
  assert.equal(sha256(JSON.stringify(table)), CURRENT_NATIVE_IDENTITY_MAP_SHA256)
  assert.equal(sha256(await readFile(new URL('../../cad/config/identity-migration-map.json', import.meta.url))), table.sourceMapSha256)
  assert.equal(sha256(await readFile(new URL('../../cad/config/current-identity-map.json', import.meta.url))), table.currentRegistryMapSha256)
  assert.equal(CURRENT_NATIVE_IDENTITY_PROJECTION.kind, 'current-native-identity-projection')
  assert.equal(CURRENT_NATIVE_IDENTITY_PROJECTION.sourceMapSha256, inventory.identity.mapSha256)
  assert.notEqual(CURRENT_NATIVE_IDENTITY_PROJECTION.mapSha256, inventory.identity.mapSha256)
  assert.ok(Object.isFrozen(CURRENT_NATIVE_IDENTITY_PROJECTION))
})

test('current authority authenticates the actual files rather than copies of their declared pins', async t => {
  await validateCurrentNativeIdentityTable()
  const directory = await mkdtemp(join(tmpdir(), 'current-native-authority-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const webRoot = join(directory, 'web')
  const files = [
    ['../content/current-native-identities.json', 'web/content/current-native-identities.json'],
    ['../../cad/config/identity-migration-map.json', 'cad/config/identity-migration-map.json'],
    ['../../cad/config/current-identity-map.json', 'cad/config/current-identity-map.json'],
  ]
  const bytes = new Map()
  for (const [source, destination] of files) {
    const target = join(directory, destination), raw = await readFile(new URL(source, import.meta.url))
    await mkdir(join(target, '..'), { recursive: true })
    await writeFile(target, raw)
    bytes.set(destination, raw)
  }
  await validateCurrentNativeIdentityInputs(webRoot)
  const archived = 'cad/config/identity-migration-map.json'
  await writeFile(join(directory, archived), Buffer.concat([bytes.get(archived), Buffer.from('\n')]))
  await assert.rejects(() => validateCurrentNativeIdentityInputs(webRoot), /CAD identity map SHA256 mismatch/)
  await writeFile(join(directory, archived), bytes.get(archived))
  const currentTable = structuredClone(table)
  currentTable.machineVendors[0].identities[0].number = 'MHA-SM-VN-99'
  await writeFile(join(directory, files[0][1]), JSON.stringify(currentTable))
  await assert.rejects(() => validateCurrentNativeIdentityInputs(webRoot), /current table SHA256 mismatch/)
  await writeFile(join(directory, files[0][1]), bytes.get(files[0][1]))
  const currentCad = 'cad/config/current-identity-map.json'
  await writeFile(join(directory, currentCad), Buffer.concat([bytes.get(currentCad), Buffer.from('\n')]))
  await assert.rejects(() => validateCurrentNativeIdentityInputs(webRoot), /current CAD map SHA256 mismatch/)
})

test('a real checkout with core.autocrlf=true preserves both raw-pinned maps and current authority', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'current-native-checkout-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const repository = join(directory, 'source'), checkout = join(directory, 'checkout')
  await mkdir(repository)
  const files = [
    ['../../.gitattributes', '.gitattributes'],
    ['../../cad/config/identity-migration-map.json', 'cad/config/identity-migration-map.json'],
    ['../../cad/config/current-identity-map.json', 'cad/config/current-identity-map.json'],
    ['../content/current-native-identities.json', 'web/content/current-native-identities.json'],
  ]
  for (const [source, destination] of files) {
    const target = join(repository, destination)
    await mkdir(join(target, '..'), { recursive: true })
    await writeFile(target, await readFile(new URL(source, import.meta.url)))
  }
  const hooks = join(directory, 'no-hooks')
  await mkdir(hooks)
  const exec = promisify(execFile)
  const runGit = (_command, args) => exec('git', ['-c', `core.hooksPath=${hooks}`, ...args])
  await runGit('git', ['init', '--quiet', '--template=', repository])
  const git = args => runGit('git', ['-C', repository, '-c', 'core.autocrlf=true',
    '-c', 'user.name=Identity fixture', '-c', 'user.email=identity-fixture@example.invalid',
    '-c', 'commit.gpgsign=false', ...args])
  await git(['add', '--', ...files.map(([, destination]) => destination)])
  await git(['commit', '--quiet', '-m', 'Pinned map checkout fixture'])
  await runGit('git', ['clone', '--quiet', '--no-checkout', '--config', 'core.autocrlf=true', repository, checkout])
  await runGit('git', ['-C', checkout, 'checkout', '--quiet', 'HEAD'])
  assert.equal(sha256(await readFile(join(checkout, 'cad/config/identity-migration-map.json'))), table.sourceMapSha256)
  assert.equal(sha256(await readFile(join(checkout, 'cad/config/current-identity-map.json'))), table.currentRegistryMapSha256)
  await validateCurrentNativeIdentityInputs(join(checkout, 'web'))
})

test('every active projected row equals CAD and historical-only occurrences stay explicitly outside it', () => {
  validateCurrentNativeIdentityProjection(table, cadMap)
  const changedParent = structuredClone(table)
  changedParent.toolingVendors[0].parent = 'ch-rocker-arm'
  assert.throws(() => validateCurrentNativeIdentityProjection(changedParent, cadMap), /projection entries differ/)
  const changedActivePedestal = structuredClone(table)
  changedActivePedestal.machineVendors.find(row => row.sourceStem === 'vn-pedestal-hold-down-screw').identities[0].number = 'MHA-DT-VN-99'
  assert.throws(() => validateCurrentNativeIdentityProjection(changedActivePedestal, cadMap), /projection entries differ/)
  const inventedHistoricalRegistry = structuredClone(table)
  inventedHistoricalRegistry.archiveOnlyVendors[0].registry = 'cad/config/parts/pd-vn-transgear-collar-cross-pin.yaml'
  assert.throws(() => validateCurrentNativeIdentityProjection(inventedHistoricalRegistry, cadMap), /archive-only identities/)
  const addedHistorical = structuredClone(table)
  addedHistorical.archiveOnlyVendors.push({ ...addedHistorical.archiveOnlyVendors[0] })
  assert.throws(() => validateCurrentNativeIdentityProjection(addedHistorical, cadMap), /exactly the three historical/)
})

test('target collisions and conflicting source Numbers are rejected while target stems may be scoped to different parents', async t => {
  const duplicate = structuredClone(table)
  duplicate.machineVendors[0].identities.push({ ...duplicate.machineVendors[0].identities[0] })
  await assert.rejects(() => isolatedProjection(t, duplicate), /colliding current identity/)
  const conflict = structuredClone(table), first = conflict.machineVendors[0]
  conflict.nativeIdentities.push({ sourceStem: first.sourceStem, sourceNumber: 'MHA-VN-999',
    identities: [{ parent: 'test-parent', stem: 'test-vn-conflict', number: 'MHA-TEST-VN-50' }] })
  await assert.rejects(() => isolatedProjection(t, conflict), /conflicting historical number/)
  const scoped = structuredClone(table), scopedFirst = scoped.machineVendors[0]
  scopedFirst.identities.push({ ...scopedFirst.identities[0], parent: 'different-parent' })
  const projection = await isolatedProjection(t, scoped)
  assert.equal(projection.projectCurrentNativePath(path('different-parent', `${scopedFirst.sourceStem}-1`)),
    path('different-parent', `${scopedFirst.identities[0].stem}-1`))
})

test('all split vendors resolve by their immediate parent rather than one arbitrary global rename', () => {
  for (const [stem, parents] of [
    ['fillister-screw', ['fr-frame', 'dt-drive-train', 'pd-paper-drive']],
    ['clamp-screw', ['mg-magnifier', 'pd-paper-drive']],
    ['arbor-set-screw', ['ch-channel', 'dt-drive-train']],
    ['thumb-screw', ['mg-magnifier', 'ms-measuring-stick']],
  ]) for (const parent of parents) {
    const result = path(parent, `${parent.slice(0, 2)}-vn-${stem}-1`)
    assert.equal(projectCurrentNativePath(path(parent, `vn-${stem}-1`)), result)
    assert.equal(projectCurrentNativePath(result), result)
  }
  assert.throws(() => projectCurrentNativePath(path('pn-pen', 'vn-fillister-screw-1')), /no unique immediate parent/)
  assert.throws(() => projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw'), /no unique immediate parent/)
})

test('two-digit Numbers preserve geometry/configuration qualifiers and purchased tooling scope', () => {
  assert.equal(projectCurrentNativeNumber('MHA-DT-003-T006', 'dt-cone-gear'), 'MHA-DT-03-T006')
  assert.equal(projectCurrentNativeNumber('MHA-HA-000', 'ha-harmonic-analyzer'), 'MHA-HA-00')
  assert.equal(projectCurrentNativeNumber('MHA-DT-005-TL-01', 'dt-cone-pivot-post-tl-bond-cradle'), 'MHA-DT-05-TL-01')
  assert.equal(projectCurrentNativeNumber('MHA-CH-006-TL-30', 'ch-rocker-arm-tl-oblique-rail', 'ch-rocker-arm-tl-oblique-jig'), 'MHA-CH-06-TL-VN-50')
  assert.equal(projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw', 'fr-frame'), 'MHA-FR-VN-50')
  assert.equal(projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw', 'pd-paper-drive'), 'MHA-PD-VN-52')
  assert.equal(projectCurrentNativeNumber('MHA-MG-009', 'mg-lever-wire', 'mg-magnifier'), 'MHA-MG-VN-56')
  assert.throws(() => projectCurrentNativeNumber('MHA-DT-003-T06', 'dt-cone-gear'), /does not identify/)
  assert.equal(projectCurrentNativePath(path('ch-channel', 'vn-channel-spring-installed-stretch00-20')), path('ch-channel', 'ch-vn-channel-spring-installed-stretch00-20'))
  assert.equal(projectCurrentNativePath(path('mg-magnifier', 'mg-lever-wire--T006-1@upper')), path('mg-magnifier', 'mg-vn-lever-wire--T006-1@upper'))
})

test('all 457 archived native paths project uniquely without moving geometry across parents', () => {
  const projected = projectCurrentNativeMetadata(inventory)
  assert.equal(projected.inventory.length, 457)
  assert.equal(new Set(projected.inventory.map(row => row.path)).size, 457)
  assert.strictEqual(projected.source, inventory.source)
  assert.strictEqual(projected.identity, inventory.identity)
  for (let index = 0; index < inventory.inventory.length; index++) {
    const original = inventory.inventory[index], current = projected.inventory[index]
    assert.equal(current.path.split('/').slice(0, -1).join('/'), original.path.split('/').slice(0, -1).join('/'))
    assert.ok(!current.path.includes('/vn-'), current.path)
    assert.strictEqual(current.world, original.world)
    assert.equal(current.sourcePath, original.sourcePath)
    assert.equal(projectCurrentNativePath(current.path), current.path)
  }
  const oldPedestal = inventory.inventory.filter(row => /\/ch-channel\/vn-pedestal-hold-down-screw-/.test(row.path))
  assert.equal(oldPedestal.length, 4)
  for (const row of oldPedestal) assert.match(projectCurrentNativePath(row.path), /\/ch-channel\/ch-vn-pedestal-hold-down-screw-[1-4]$/)
  assert.equal(projectCurrentNativeNumber('MHA-VN-032', 'vn-pedestal-hold-down-screw', 'ch-channel'), null)
  assert.equal(projectCurrentNativeNumber('MHA-VN-032', 'vn-pedestal-hold-down-screw', 'dt-drive-train'), 'MHA-DT-VN-62')
  assert.equal(projectCurrentNativeNumber('MHA-VN-037', 'vn-transgear-collar-cross-pin', 'pd-paper-drive'), null)
})

test('metadata ingestion changes qualified identity values/keys, never archived filenames, URLs or numeric arrays', () => {
  const oldPath = path('pd-paper-drive', 'vn-clamp-screw-3')
  const numeric = [-0, 1.2345678901234567, 3]
  const source = { sourceFile: 'cad/scripts/build_vn_clamp_screw.py', url: 'https://example.test/v39/vn-clamp-screw',
    sha256: inventory.source.sha256, partPath: oldPath, matrices: { [oldPath]: numeric }, prose: `Archive component ${oldPath}` }
  const projected = projectCurrentNativeMetadata(source), currentPath = path('pd-paper-drive', 'pd-vn-clamp-screw-3')
  assert.equal(projected.partPath, currentPath)
  assert.strictEqual(projected.matrices[currentPath], numeric)
  assert.ok(Object.is(projected.matrices[currentPath][0], -0))
  assert.equal(projected.sourceFile, source.sourceFile)
  assert.equal(projected.url, source.url)
  assert.equal(projected.sha256, source.sha256)
  assert.equal(projected.prose, source.prose)
  assert.equal(source.partPath, oldPath)
  assert.throws(() => projectCurrentNativeMetadata({ [oldPath]: 1, [currentPath]: 2 }), /colliding metadata path/)
  assert.throws(() => projectCurrentNativePath('ha-harmonic-analyzer/../vn-fillister-screw-1'), /unsafe native path/)
})

test('parsed GLTF projection changes only declared native identity, retaining all geometry and annotations', () => {
  const oldPath = path('dt-drive-train', 'vn-fillister-screw-1')
  const matrix = [-0, 0, 1, 0], meshes = [{ primitives: [{ attributes: { POSITION: 0 } }] }]
  const document = { asset: { version: '2.0' }, nodes: [
    { name: 'ha-harmonic-analyzer', children: [1] },
    { name: 'dt-drive-train', children: [2] },
    { name: 'vn-fillister-screw-1', mesh: 0, matrix, extras: {
      nativePath: oldPath, nativePaths: [oldPath], annotation: oldPath,
      nativeIdentity: { stem: 'vn-fillister-screw', underscore: 'vn_fillister_screw', name: 'vn-fillister-screw-1',
        number: 'MHA-VN-006', builder: 'cad/scripts/build_vn_fillister_screw.py', registry: 'cad/config/parts/vn-fillister-screw.yaml', note: oldPath },
    } },
  ], meshes, accessors: [{ count: 1 }], buffers: [{ byteLength: 12 }] }
  projectCurrentNativeDocument(document)
  const part = document.nodes[2], currentPath = path('dt-drive-train', 'dt-vn-fillister-screw-1')
  assert.equal(part.name, 'dt-vn-fillister-screw-1')
  assert.equal(part.extras.nativePath, currentPath)
  assert.deepEqual(part.extras.nativePaths, [currentPath])
  assert.equal(part.extras.annotation, oldPath)
  assert.deepEqual(part.extras.nativeIdentity, {
    stem: 'dt-vn-fillister-screw', underscore: 'dt_vn_fillister_screw', name: 'dt-vn-fillister-screw-1', number: 'MHA-DT-VN-50',
    builder: 'cad/scripts/build_dt_vn_fillister_screw.py', registry: 'cad/config/parts/dt-vn-fillister-screw.yaml', note: oldPath,
  })
  assert.strictEqual(part.matrix, matrix)
  assert.strictEqual(document.meshes, meshes)
  assert.ok(Object.is(part.matrix[0], -0))
  assert.deepEqual(document.accessors, [{ count: 1 }])
  assert.deepEqual(document.buffers, [{ byteLength: 12 }])
})

test('archive-only displayed identities do not advertise fabricated live registry or builder files', () => {
  for (const historical of table.archiveOnlyVendors) {
    const archivedIdentity = { stem: historical.sourceStem, number: historical.sourceNumber,
      registry: `cad/config/parts/${historical.sourceStem}.yaml`,
      builder: `cad/scripts/build_${historical.sourceStem.replaceAll('-', '_')}.py`,
      file: `cad/scripts/${historical.sourceStem.replaceAll('-', '_')}_spec.py`,
      module: `${historical.sourceStem.replaceAll('-', '_')}_spec` }
    const document = { nodes: [
      { name: 'ha-harmonic-analyzer', children: [1] },
      { name: historical.parent, children: [2] },
      { name: `${historical.sourceStem}-1`, extras: { nativeIdentity: archivedIdentity } },
    ] }
    projectCurrentNativeDocument(document)
    const actual = document.nodes[2].extras.nativeIdentity
    assert.equal(actual.stem, historical.stem)
    assert.equal(actual.number, null)
    assert.equal(actual.registry, null)
    assert.equal(actual.builder, null)
    assert.equal(actual.file, null)
    assert.equal(actual.module, null)
    assert.equal(actual.status, 'archive-only')
    assert.equal(actual.archivedNumber, historical.sourceNumber)
    assert.deepEqual(actual.archivedIdentity, archivedIdentity)
  }
})

test('declared child identity resolves against the projected immediate parent, not the archived parent name', async t => {
  const fixtureTable = structuredClone(table)
  fixtureTable.machineVendors.find(row => row.sourceStem === 'vn-fillister-screw').identities.push({
    parent: 'mg-vn-lever-wire', stem: 'mg-vn-fillister-screw', number: 'MHA-MG-VN-99',
  })
  const projection = await isolatedProjection(t, fixtureTable)
  const document = { nodes: [
    { name: 'ha-harmonic-analyzer', children: [1] },
    { name: 'mg-magnifier', children: [2] },
    { name: 'mg-lever-wire-1', children: [3] },
    { name: 'vn-fillister-screw-1', extras: { nativeIdentity: { stem: 'vn-fillister-screw', number: 'MHA-VN-006' } } },
  ] }
  projection.projectCurrentNativeDocument(document)
  assert.equal(document.nodes[2].name, 'mg-vn-lever-wire-1')
  assert.equal(document.nodes[3].name, 'mg-vn-fillister-screw-1')
  assert.equal(document.nodes[3].extras.nativeIdentity.number, 'MHA-MG-VN-99')
})
