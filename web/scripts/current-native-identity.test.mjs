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
  projectCurrentNativePath, projectCurrentNativeNumber, requireCurrentNativeOccurrenceNamespace,
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
const retiredTooling = [
  ['ch-rocker-arm', 'CH-06', [
    ['filing-button', '04'], ['filing-stud', '05'], ['riser-block', '10'], ['strap-shim-stack', '11'],
    ['filing-stand', '12'], ['outline-template', '13'], ['trammel-pivot-block', '14'],
    ['trammel-scriber-block', '15'], ['trammel-scriber-point', '16'], ['trammel-setting-bar', '17'],
    ['trammel-pivot-point', '18'], ['trammel-pivot-plate', '19'],
  ]],
  ['ch-pivot-bracket', 'CH-08', [['ledge', '01'], ['angle-plate', '02']]],
  ['dt-cone-pivot-post', 'DT-05', [['bond-cradle', '01'], ['saw-cradle', '02'], ['cap-jaw-button', '03'], ['soft-jaw', '04']]],
].flatMap(([parent, category, tools]) => tools.map(([tool, sequence]) => ({
  old_stem: `${parent}-tl-${tool}`,
  old_number: `MHA-${category.replace('-', '-0')}-TL-${sequence}`,
  new_identities: [{ stem: `${parent}-tl-${tool}`, number: `MHA-${category}-TL-${sequence}` }],
  status: 'retired',
})))
retiredTooling.push(...[
  ['nut-bracket', '29', '29', false],
  ['pivot-cap', null, '30', false, '2026-10-20'],
  ['pivot-retainer', null, '31', false, '2026-10-20'],
  ['hub-pin', '25', '25', false],
  ['pivot-cap-screw', null, '73', true, '2026-10-20'],
  ['pivot-clevis-pin', null, '74', true, '2026-10-20'],
  ['pivot-cotter', null, '75', true, '2026-10-20'],
  ['pivot-lock-wire', null, '76', true, '2026-10-20'],
  ['bearing', '32', '52', true],
  ['block-screw', '43', '63', true],
  ['block-washer', '50', '70', true],
  ['pivot-pin', '23', '23', false],
].map(([suffix, previousSequence, sequence, vendor, introduced]) => ({
  old_stem: `ch-rocker-arm-tl-${vendor && previousSequence === null ? 'vn-' : ''}oblique-${suffix}`,
  old_number: previousSequence === null ? null : `MHA-CH-006-TL-${previousSequence}`,
  ...(introduced ? { introduced } : {}),
  new_identities: [{
    ...(vendor ? { parent: 'ch-rocker-arm-tl-oblique-jig' } : {}),
    stem: `ch-rocker-arm-tl-${vendor ? 'vn-' : ''}oblique-${suffix}`,
    number: `MHA-CH-06-TL-${vendor ? 'VN-' : ''}${sequence}`,
  }],
  status: 'retired',
})))
// The MHA-PD-VN-67 pivot shim, retired 2026-10-31 (#290): the arm's spot face took its room.
retiredTooling.push({
  old_stem: 'vn-transgear-pivot-shim',
  old_number: 'MHA-VN-069',
  new_identities: [{ parent: 'pd-paper-drive', stem: 'pd-vn-transgear-pivot-shim', number: 'MHA-PD-VN-67' }],
  status: 'retired',
})

// Independent behavioral expectations, not values copied out of the projection table.
const sharedCases = [
  ['pd-paper-drive', 'vn-chain-inner-link', 'MHA-VN-002', 'pd-vn-chain-inner-link', 'MHA-PD-VN-50',
    'sh-vn-chain-link', 'sh-vn-chain-link--InnerLink', 'MHA-SH-VN-50', 'InnerLink', 'InnerLink'],
  ['pd-paper-drive', 'vn-chain-outer-link', 'MHA-VN-003', 'pd-vn-chain-outer-link', 'MHA-PD-VN-51',
    'sh-vn-chain-link', 'sh-vn-chain-link--OuterLink', 'MHA-SH-VN-50', 'OuterLink', 'OuterLink'],
  ...[
    ['dt-drive-train', 'dt-vn-fillister-screw', 'MHA-DT-VN-50'],
    ['fr-frame', 'fr-vn-fillister-screw', 'MHA-FR-VN-50'],
    ['pd-paper-drive', 'pd-vn-fillister-screw', 'MHA-PD-VN-52'],
  ].map(([parent, priorStem, priorNumber]) => [parent, 'vn-fillister-screw', 'MHA-VN-006', priorStem, priorNumber,
    'sh-vn-brass-fillister-screw', 'sh-vn-brass-fillister-screw', 'MHA-SH-VN-51', 'Default', 'FillisterScrew']),
  ['dt-drive-train', 'vn-foot-screw', 'MHA-VN-020', 'dt-vn-foot-screw', 'MHA-DT-VN-58',
    'sh-vn-fillister-screw-90280a108', 'sh-vn-fillister-screw-90280a108__FootScrew', 'MHA-SH-VN-52', 'Default', 'FootScrew'],
  ['dt-drive-train', 'vn-swing-stop-screw', 'MHA-VN-015', 'dt-vn-swing-stop-screw', 'MHA-DT-VN-53',
    'sh-vn-fillister-screw-90280a108', 'sh-vn-fillister-screw-90280a108__SwingStopScrew', 'MHA-SH-VN-52', 'Default', 'SwingStopScrew'],
  ['pd-paper-drive', 'vn-latch-hook-bracket-screw', 'MHA-VN-043', 'pd-vn-latch-hook-bracket-screw', 'MHA-PD-VN-59',
    'sh-vn-fillister-screw-90280a108', 'sh-vn-fillister-screw-90280a108', 'MHA-SH-VN-52', 'Default', 'LatchHookBracketScrew'],
  ...[
    ['mg-magnifier', 'mg-vn-clamp-screw', 'MHA-MG-VN-51'],
    ['pd-paper-drive', 'pd-vn-clamp-screw', 'MHA-PD-VN-53'],
  ].map(([parent, priorStem, priorNumber]) => [parent, 'vn-clamp-screw', 'MHA-VN-021', priorStem, priorNumber,
    'sh-vn-clamp-screw', 'sh-vn-clamp-screw', 'MHA-SH-VN-53', 'Default', 'ClampScrew']),
  ...[
    ['ch-channel', 'ch-vn-arbor-set-screw', 'MHA-CH-VN-53'],
    ['dt-drive-train', 'dt-vn-arbor-set-screw', 'MHA-DT-VN-64'],
  ].map(([parent, priorStem, priorNumber]) => [parent, 'vn-arbor-set-screw', 'MHA-VN-034', priorStem, priorNumber,
    'sh-vn-arbor-set-screw', 'sh-vn-arbor-set-screw', 'MHA-SH-VN-54', 'Default', 'ArborSetScrew']),
  ...[
    ['mg-magnifier', 'mg-vn-thumb-screw', 'MHA-MG-VN-50'],
    ['ms-measuring-stick', 'ms-vn-thumb-screw', 'MHA-MS-VN-50'],
  ].map(([parent, priorStem, priorNumber]) => [parent, 'vn-thumb-screw', 'MHA-VN-011', priorStem, priorNumber,
    'sh-vn-thumb-screw', 'sh-vn-thumb-screw', 'MHA-SH-VN-55', 'Default', 'ThumbScrew']),
  ['mg-magnifier', 'mg-lever-wire', 'MHA-MG-009', 'mg-vn-lever-wire', 'MHA-MG-VN-56',
    'sh-vn-music-wire', 'sh-vn-music-wire--LeverWire', 'MHA-SH-VN-56', 'LeverWire', 'LeverWire'],
  ['pn-pen', 'pn-pen-wire', 'MHA-PN-006', 'pn-vn-pen-wire', 'MHA-PN-VN-57',
    'sh-vn-music-wire', 'sh-vn-music-wire--PenWire', 'MHA-SH-VN-56', 'PenWire', 'PenWire'],
  ...[
    ['hold-down-stud', 'MHA-CH-006-TL-38', 'MHA-CH-06-TL-VN-58', 'HoldDownStud'],
    ['t-nut', 'MHA-CH-006-TL-39', 'MHA-CH-06-TL-VN-59', 'TNut'],
    ['flange-nut', 'MHA-CH-006-TL-40', 'MHA-CH-06-TL-VN-60', 'FlangeNut'],
  ].map(([member, sourceNumber, priorNumber, configuration]) => [
    'ch-rocker-arm-tl-oblique-jig', `ch-rocker-arm-tl-oblique-${member}`, sourceNumber,
    `ch-rocker-arm-tl-vn-oblique-${member}`, priorNumber, 'sh-vn-clamping-kit-hardware',
    `sh-vn-clamping-kit-hardware--${configuration}`, 'MHA-SH-VN-57', configuration, configuration]),
].map(([parent, sourceStem, sourceNumber, priorStem, priorNumber, stem, occurrenceStem, number, configuration, role]) =>
  ({ parent, sourceStem, sourceNumber, priorStem, priorNumber, stem, occurrenceStem, number, configuration, role }))

test('all eight shared targets retain each of the nineteen exact member and role identities', () => {
  assert.equal(table.schemaVersion, 1)
  assert.equal(table.occurrenceNamespace, 'archive-role-local')
  assert.equal(sharedCases.length, 19)
  assert.equal(new Set(sharedCases.map(row => row.stem)).size, 8)
  const expectedGroups = [...new Set(sharedCases.map(row => row.stem))].map(stem => {
    const members = sharedCases.filter(row => row.stem === stem)
    return [stem, members[0].number, [...new Set(members.map(row => row.configuration))].sort()]
  }).sort()
  assert.deepEqual(table.sharedVendors.map(row => [row.stem, row.number, [...row.configurations].sort()]).sort(), expectedGroups)
  assert.equal(CURRENT_NATIVE_IDENTITY_PROJECTION.occurrenceNamespace, 'archive-role-local')
  for (const row of sharedCases) {
    for (const source of [row.sourceStem, row.priorStem]) {
      const expected = path(row.parent, `${row.occurrenceStem}-1`)
      assert.equal(projectCurrentNativePath(path(row.parent, `${source}-1`)), expected)
      assert.equal(projectCurrentNativePath(expected), expected)
    }
    for (const [number, stem] of [[row.sourceNumber, row.sourceStem], [row.priorNumber, row.priorStem],
      [row.number, row.occurrenceStem], [row.number, `${row.occurrenceStem}-1`]]) {
      assert.equal(projectCurrentNativeNumber(number, stem, row.parent), row.number)
    }
  }
  assert.throws(() => projectCurrentNativeNumber('MHA-SH-VN-52', 'sh-vn-fillister-screw-90280a108', 'dt-drive-train'),
    /no unique immediate parent/)
  assert.throws(() => projectCurrentNativeNumber('MHA-SH-VN-50', 'sh-vn-chain-link', 'pd-paper-drive'),
    /no unique immediate parent/)
})

test('all five Default shared groups preserve native variant suffixes on repeated projection', () => {
  const defaults = sharedCases.filter(row => row.configuration === 'Default')
  assert.equal(new Set(defaults.map(row => row.stem)).size, 5)
  for (const row of defaults) for (const variant of ['T006', 'Installed']) {
    const expected = path(row.parent, `${row.occurrenceStem}--${variant}-7@upper`)
    for (const source of [row.sourceStem, row.priorStem]) {
      const current = projectCurrentNativePath(path(row.parent, `${source}--${variant}-7@upper`))
      assert.equal(current, expected)
      assert.equal(projectCurrentNativePath(current), expected)
      assert.equal(projectCurrentNativePath(expected), expected)
    }
  }
})

test('logical member selectors remain case-sensitive rather than accepting physical filename spelling', () => {
  const exact = path('pd-paper-drive', 'sh-vn-chain-link--InnerLink-1')
  assert.equal(projectCurrentNativePath(exact), exact)
  assert.throws(() => projectCurrentNativePath(path('pd-paper-drive', 'sh-vn-chain-link--innerlink-1')),
    /no unique immediate parent/)
  assert.throws(() => projectCurrentNativeNumber('MHA-SH-VN-50', 'sh-vn-chain-link--innerlink', 'pd-paper-drive'),
    /no unique immediate parent/)
})

test('role-local archive paths cannot be used as rebuilt native occurrence addresses', () => {
  const archived = path('dt-drive-train', 'vn-foot-screw-1')
  requireCurrentNativeOccurrenceNamespace('archive-role-local')
  assert.equal(projectCurrentNativePath(archived, 'archive-role-local'),
    path('dt-drive-train', 'sh-vn-fillister-screw-90280a108__FootScrew-1'))
  for (const namespace of ['rebuilt-native', '', null, undefined]) {
    assert.throws(() => requireCurrentNativeOccurrenceNamespace(namespace), /namespace/i)
    if (namespace !== undefined) {
      assert.throws(() => projectCurrentNativePath(archived, namespace), /namespace/i)
      assert.throws(() => projectCurrentNativePath('Camera', namespace), /namespace/i)
    }
  }
})

test('node namespace preflight rejects rebuilt-native extras before changing any source node', () => {
  for (const boundary of ['extras', 'nativeIdentity']) {
    const matrix = [-0, 1, 0, 1]
    const sourceExtras = { nativePath: path('dt-drive-train', 'vn-foot-screw-1') }
    const rejectedExtras = boundary === 'extras'
      ? { occurrenceNamespace: 'rebuilt-native' }
      : { nativeIdentity: { stem: 'vn-swing-stop-screw', occurrenceNamespace: 'rebuilt-native' } }
    const document = { nodes: [
      { name: 'ha-harmonic-analyzer', children: [1] },
      { name: 'dt-drive-train', children: [2, 3] },
      { name: 'vn-foot-screw-1', matrix, extras: sourceExtras },
      { name: 'vn-swing-stop-screw-1', extras: rejectedExtras },
    ] }
    const before = structuredClone(document)
    assert.throws(() => projectCurrentNativeDocument(document), /namespace/i)
    assert.deepEqual(document, before)
    assert.equal(document.nodes[2].name, 'vn-foot-screw-1')
    assert.strictEqual(document.nodes[2].extras, sourceExtras)
    assert.strictEqual(document.nodes[2].matrix, matrix)
    assert.ok(Object.is(matrix[0], -0))
  }
})

test('metadata and glTF namespace declarations also refuse unchecked rebuilt-native linking', () => {
  const oldPath = path('dt-drive-train', 'vn-foot-screw-1')
  assert.throws(() => projectCurrentNativeMetadata({ occurrenceNamespace: 'rebuilt-native', partPath: oldPath }), /namespace/i)
  assert.throws(() => projectCurrentNativeDocument({ nodes: [] }, 'rebuilt-native'), /namespace/i)
  for (const container of ['extras', 'asset']) {
    const document = { nodes: [] }
    if (container === 'extras') document.extras = { occurrenceNamespace: 'rebuilt-native' }
    else document.asset = { version: '2.0', extras: { occurrenceNamespace: 'rebuilt-native' } }
    assert.throws(() => projectCurrentNativeDocument(document), /namespace/i)
  }
})

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
  await writeFile(join(directory, currentCad), bytes.get(currentCad))
  const reactivated = structuredClone(cadMap)
  reactivated.parts_and_assemblies.push(reactivated.retired_identities.shift())
  await writeFile(join(directory, currentCad), JSON.stringify(reactivated))
  await assert.rejects(() => validateCurrentNativeIdentityInputs(webRoot), /current CAD map SHA256 mismatch/)
  await writeFile(join(directory, currentCad), bytes.get(currentCad))
  const registry = join(directory, 'cad/config/parts', `${retiredTooling[0].old_stem}.yaml`)
  await mkdir(join(registry, '..'), { recursive: true })
  await writeFile(registry, `number: ${retiredTooling[0].new_identities[0].number}\n`)
  await assert.rejects(() => validateCurrentNativeIdentityInputs(webRoot), /retired identity still has a part registry/)
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
  for (const field of ['configuration', 'role', 'priorStem', 'priorNumber']) {
    const changed = structuredClone(table)
    changed.machineVendors.find(row => row.sourceStem === 'vn-chain-inner-link').identities[0][field] += 'Changed'
    assert.throws(() => validateCurrentNativeIdentityProjection(changed, cadMap), /projection entries differ/, field)
  }
  const changedCad = structuredClone(cadMap)
  changedCad.parts_and_assemblies.find(row => row.old_stem === 'vn-chain-inner-link')
    .new_identities[0].configuration = 'OuterLink'
  assert.throws(() => validateCurrentNativeIdentityProjection(table, changedCad), /projection entries differ/)
})

test('retired tooling keeps exactly its frozen old/current reservations without a current Number lookup', () => {
  assert.deepEqual(cadMap.retired_identities, retiredTooling)
  for (const row of retiredTooling) {
    const current = row.new_identities[0]
    assert.ok(!table.nativeIdentities.some(active => active.sourceStem === row.old_stem
      || active.identities.some(target => target.stem === current.stem || target.number === current.number)))
    assert.ok(!table.toolingVendors.some(active => active.sourceStem === row.old_stem
      || active.stem === current.stem || active.number === current.number))
    for (const number of [row.old_number, current.number]) {
      assert.throws(() => projectCurrentNativeNumber(number, current.stem), /unknown native identity/)
    }
    const unknown = path('ch-channel', `${current.stem}-1`)
    assert.equal(projectCurrentNativePath(unknown), unknown) // Unknown non-vendor tokens are not a current lookup.
  }
})

test('retired stems and Numbers cannot reappear through active rows, aliases or archive-only exceptions', () => {
  const reservation = cadMap.retired_identities[0]
  const activeAgain = structuredClone(cadMap)
  activeAgain.parts_and_assemblies.push(structuredClone(reservation))
  assert.throws(() => validateCurrentNativeIdentityProjection(table, activeAgain), /active identity collides with retired/)
  for (const field of ['stem', 'number']) {
    const reused = structuredClone(cadMap)
    reused.parts_and_assemblies[0].new_identities[0][field] = reservation.new_identities[0][field]
    assert.throws(() => validateCurrentNativeIdentityProjection(table, reused), /active identity collides with retired/)
  }
  const activeProjection = structuredClone(table)
  activeProjection.nativeIdentities.push({
    sourceStem: reservation.old_stem, sourceNumber: reservation.old_number, identities: reservation.new_identities,
  })
  assert.throws(() => validateCurrentNativeIdentityProjection(activeProjection, cadMap), /projected identity reactivates retired/)
  const alias = structuredClone(cadMap)
  alias.historical_current_aliases[0].old_stem = reservation.old_stem
  assert.throws(() => validateCurrentNativeIdentityProjection(table, alias), /alias reactivates a retired/)
  const archive = structuredClone(table)
  archive.archiveOnlyVendors.push({
    sourceStem: reservation.old_stem, sourceNumber: reservation.old_number,
    ...reservation.new_identities[0], status: 'archive-only', registry: null, builder: null,
  })
  assert.throws(() => validateCurrentNativeIdentityProjection(archive, cadMap), /projected identity reactivates retired/)
  const duplicate = structuredClone(cadMap)
  duplicate.retired_identities.push(structuredClone(reservation))
  assert.throws(() => validateCurrentNativeIdentityProjection(table, duplicate), /colliding retired identity/)
})

test('a retired post-migration identity with no historical Number still reserves its current Number', () => {
  const reservation = cadMap.retired_identities.find(row => row.old_number === null)
  assert.ok(reservation, 'the current map retires at least one post-migration identity')
  const reused = structuredClone(cadMap)
  reused.parts_and_assemblies[0].new_identities[0].number = reservation.new_identities[0].number
  assert.throws(() => validateCurrentNativeIdentityProjection(table, reused), /active identity collides with retired/)
  const missing = structuredClone(cadMap)
  delete missing.retired_identities.find(row => row.old_number === null).old_number
  assert.throws(() => validateCurrentNativeIdentityProjection(table, missing), /invalid retired identity reservation/)
})

test('shared targets permit consistent many-to-one rows but reject duplicate source contexts and undeclared semantics', async t => {
  for (const sourceStem of ['vn-boss-hook', 'vn-chain-inner-link']) {
    const duplicate = structuredClone(table)
    const source = duplicate.machineVendors.find(row => row.sourceStem === sourceStem)
    source.identities.push({ ...source.identities[0] })
    await assert.rejects(() => isolatedProjection(t, duplicate), /colliding current identity/)
  }
  const converged = structuredClone(table)
  const original = converged.machineVendors.find(row => row.sourceStem === 'vn-chain-inner-link')
  const alias = structuredClone(original)
  alias.sourceStem = 'vn-test-shared-inner-link'
  alias.identities[0].priorStem = 'pd-vn-test-shared-inner-link'
  converged.machineVendors.push(alias)
  const accepted = await isolatedProjection(t, converged)
  assert.equal(accepted.projectCurrentNativePath(path('pd-paper-drive', 'vn-test-shared-inner-link-1')),
    path('pd-paper-drive', 'sh-vn-chain-link--InnerLink-1'))
  for (const [field, value] of [['number', 'MHA-SH-VN-99'], ['configuration', 'UnknownMember'], ['role', 'OuterLink']]) {
    const changed = structuredClone(converged)
    changed.machineVendors.at(-1).identities[0][field] = value
    await assert.rejects(() => isolatedProjection(t, changed), /conflict|inconsistent|configuration|shared|collid/i)
  }
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

test('shared vendors still resolve by their immediate parent and reject unsupported consumers', () => {
  for (const row of sharedCases) {
    assert.equal(projectCurrentNativePath(path(row.parent, `${row.sourceStem}-7`)),
      path(row.parent, `${row.occurrenceStem}-7`))
  }
  assert.throws(() => projectCurrentNativePath(path('pn-pen', 'vn-fillister-screw-1')), /no unique immediate parent/)
  assert.throws(() => projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw'), /no unique immediate parent/)
})

test('two-digit Numbers preserve geometry/configuration qualifiers and purchased tooling scope', () => {
  assert.equal(projectCurrentNativeNumber('MHA-DT-003-T006', 'dt-cone-gear'), 'MHA-DT-03-T006')
  assert.equal(projectCurrentNativeNumber('MHA-HA-000', 'ha-harmonic-analyzer'), 'MHA-HA-00')
  assert.equal(projectCurrentNativeNumber('MHA-CH-006-TL-30', 'ch-rocker-arm-tl-oblique-rail', 'ch-rocker-arm-tl-oblique-jig'), 'MHA-CH-06-TL-VN-50')
  assert.equal(projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw', 'fr-frame'), 'MHA-SH-VN-51')
  assert.equal(projectCurrentNativeNumber('MHA-VN-006', 'vn-fillister-screw', 'pd-paper-drive'), 'MHA-SH-VN-51')
  assert.equal(projectCurrentNativeNumber('MHA-MG-009', 'mg-lever-wire', 'mg-magnifier'), 'MHA-SH-VN-56')
  assert.throws(() => projectCurrentNativeNumber('MHA-DT-003-T06', 'dt-cone-gear'), /does not identify/)
  assert.equal(projectCurrentNativePath(path('ch-channel', 'vn-channel-spring-installed-stretch00-20')), path('ch-channel', 'ch-vn-channel-spring-installed-stretch00-20'))
  assert.equal(projectCurrentNativePath(path('dt-drive-train', 'dt-cone-gear--T006-1@upper')),
    path('dt-drive-train', 'dt-cone-gear--T006-1@upper'))
  assert.equal(projectCurrentNativePath(path('mg-magnifier', 'mg-lever-wire--T006-1@upper')),
    path('mg-magnifier', 'sh-vn-music-wire--LeverWire--T006-1@upper'))
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
    assert.deepEqual({ ...current, path: original.path }, original)
    assert.equal(projectCurrentNativePath(current.path), current.path)
  }
  const oldPedestal = inventory.inventory.filter(row => /\/ch-channel\/vn-pedestal-hold-down-screw-/.test(row.path))
  assert.equal(oldPedestal.length, 4)
  for (const row of oldPedestal) assert.match(projectCurrentNativePath(row.path), /\/ch-channel\/ch-vn-pedestal-hold-down-screw-[1-4]$/)
  assert.equal(projectCurrentNativeNumber('MHA-VN-032', 'vn-pedestal-hold-down-screw', 'ch-channel'), null)
  assert.equal(projectCurrentNativeNumber('MHA-VN-032', 'vn-pedestal-hold-down-screw', 'dt-drive-train'), 'MHA-DT-VN-62')
  assert.equal(projectCurrentNativeNumber('MHA-VN-037', 'vn-transgear-collar-cross-pin', 'pd-paper-drive'), null)
  for (const [source, expected] of [
    ['dt-drive-train/vn-foot-screw-1', 'dt-drive-train/sh-vn-fillister-screw-90280a108__FootScrew-1'],
    ['dt-drive-train/vn-swing-stop-screw-1', 'dt-drive-train/sh-vn-fillister-screw-90280a108__SwingStopScrew-1'],
    ['pd-paper-drive/vn-chain-inner-link-1', 'pd-paper-drive/sh-vn-chain-link--InnerLink-1'],
    ['pd-paper-drive/vn-chain-outer-link-1', 'pd-paper-drive/sh-vn-chain-link--OuterLink-1'],
  ]) {
    const index = inventory.inventory.findIndex(row => row.path === `ha-harmonic-analyzer/${source}`)
    assert.notEqual(index, -1)
    assert.equal(projected.inventory[index].path, `ha-harmonic-analyzer/${expected}`)
  }
})

test('metadata ingestion changes qualified identity values/keys, never archived filenames, URLs or numeric arrays', () => {
  const oldPath = path('pd-paper-drive', 'vn-clamp-screw-3')
  const numeric = [-0, 1.2345678901234567, 3]
  const source = { sourceFile: 'cad/scripts/build_vn_clamp_screw.py', url: 'https://example.test/v39/vn-clamp-screw',
    sha256: inventory.source.sha256, partPath: oldPath, matrices: { [oldPath]: numeric }, prose: `Archive component ${oldPath}` }
  const projected = projectCurrentNativeMetadata(source), currentPath = path('pd-paper-drive', 'sh-vn-clamp-screw-3')
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
  const part = document.nodes[2], currentPath = path('dt-drive-train', 'sh-vn-brass-fillister-screw-1')
  assert.equal(part.name, 'sh-vn-brass-fillister-screw-1')
  assert.equal(part.extras.nativePath, currentPath)
  assert.deepEqual(part.extras.nativePaths, [currentPath])
  assert.equal(part.extras.annotation, oldPath)
  assert.deepEqual(part.extras.nativeIdentity, {
    stem: 'sh-vn-brass-fillister-screw', underscore: 'sh_vn_brass_fillister_screw', name: 'sh-vn-brass-fillister-screw-1', number: 'MHA-SH-VN-51',
    builder: 'cad/scripts/build_sh_vn_brass_fillister_screw.py', registry: 'cad/config/parts/sh-vn-brass-fillister-screw.yaml', note: oldPath,
    configuration: 'Default', role: 'FillisterScrew', semanticReference: 'FillisterScrew:1',
    occurrenceNamespace: 'archive-role-local',
  })
  assert.strictEqual(part.matrix, matrix)
  assert.strictEqual(document.meshes, meshes)
  assert.ok(Object.is(part.matrix[0], -0))
  assert.deepEqual(document.accessors, [{ count: 1 }])
  assert.deepEqual(document.buffers, [{ byteLength: 12 }])
})

test('every shared glTF member declares configuration and semantic role without changing geometry references', () => {
  for (const row of sharedCases) {
    const matrix = [-0, 0.125, 1, 0], translation = [1, 2, 3], rotation = [0, 0, 0, 1], scale = [1, 1, 1]
    const meshes = [{ primitives: [{ attributes: { POSITION: 0 }, indices: 1, material: 0 }] }]
    const accessors = [{ count: 3 }], materials = [{ name: 'original' }], buffers = [{ byteLength: 36 }]
    const oldPath = path(row.parent, `${row.sourceStem}-7`)
    const document = { nodes: [
      { name: 'ha-harmonic-analyzer', children: [1] }, { name: row.parent, children: [2] },
      { name: `${row.sourceStem}-7`, mesh: 0, matrix, translation, rotation, scale, extras: {
        nativePath: oldPath, nativeIdentity: { stem: row.sourceStem, number: row.sourceNumber },
        annotation: oldPath,
      } },
    ], meshes, accessors, materials, buffers }
    projectCurrentNativeDocument(document)
    const part = document.nodes[2]
    assert.equal(part.name, `${row.occurrenceStem}-7`)
    assert.equal(part.extras.nativePath, path(row.parent, `${row.occurrenceStem}-7`))
    assert.deepEqual(part.extras.nativeIdentity, {
      stem: row.stem, number: row.number, configuration: row.configuration, role: row.role,
      semanticReference: `${row.role}:7`, occurrenceNamespace: 'archive-role-local',
    })
    assert.equal(part.extras.annotation, oldPath)
    assert.equal(part.mesh, 0)
    for (const [key, original] of Object.entries({ matrix, translation, rotation, scale })) assert.strictEqual(part[key], original)
    for (const [key, original] of Object.entries({ meshes, accessors, materials, buffers })) assert.strictEqual(document[key], original)
    assert.ok(Object.is(part.matrix[0], -0))
    projectCurrentNativeDocument(document)
    assert.equal(part.name, `${row.occurrenceStem}-7`)
    assert.equal(part.extras.nativeIdentity.semanticReference, `${row.role}:7`)
  }
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
    parent: 'sh-vn-music-wire', stem: 'mg-vn-fillister-screw', number: 'MHA-MG-VN-99',
  })
  const projection = await isolatedProjection(t, fixtureTable)
  const document = { nodes: [
    { name: 'ha-harmonic-analyzer', children: [1] },
    { name: 'mg-magnifier', children: [2] },
    { name: 'mg-lever-wire-1', children: [3] },
    { name: 'vn-fillister-screw-1', extras: { nativeIdentity: { stem: 'vn-fillister-screw', number: 'MHA-VN-006' } } },
  ] }
  projection.projectCurrentNativeDocument(document)
  assert.equal(document.nodes[2].name, 'sh-vn-music-wire--LeverWire-1')
  assert.equal(document.nodes[3].name, 'mg-vn-fillister-screw-1')
  assert.equal(document.nodes[3].extras.nativeIdentity.number, 'MHA-MG-VN-99')
})
