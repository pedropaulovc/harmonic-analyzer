import { access, readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadNativeIdentityMap, NATIVE_IDENTITY_MAP_SHA256 } from './native-identity-map.mjs'
import { validateCurrentNativeIdentityTable } from '../current-native-identity.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
const fail = message => { throw new Error(`Current native identity inputs: ${message}`) }
const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const sorted = rows => rows.sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)))
const identity = row => ({
  parent: row.parent ?? null, stem: row.stem, number: row.number,
  priorStem: row.priorStem ?? row.prior_stem ?? null,
  priorNumber: row.priorNumber ?? row.prior_number ?? null,
  configuration: row.configuration ?? null, role: row.role ?? null,
})
const archivedOnly = new Set([
  'vn-transgear-collar-cross-pin/pd-paper-drive/pd-vn-transgear-collar-cross-pin',
  'vn-latch-hook-rivet/pd-paper-drive/pd-vn-latch-hook-rivet',
  'vn-pedestal-hold-down-screw/ch-channel/ch-vn-pedestal-hold-down-screw',
])

/** Active rows equal current CAD; retired reservations and three archive occurrences are not live identities. */
export function validateCurrentNativeIdentityProjection(table, cadMap, archivedMap) {
  if (cadMap.schema_version !== 1 || !Array.isArray(cadMap.parts_and_assemblies)
    || !Array.isArray(cadMap.retired_identities)) fail('invalid current CAD map')
  const reservedStems = new Set(), reservedNumbers = new Set()
  // A post-migration identity retires with no historical Number (old_number
  // null); its current Numbers are still reserved.
  const numbersOf = (historical, targets) =>
    [...(historical === null ? [] : [historical]), ...targets.map(target => target.number)]
  for (const row of cadMap.retired_identities) {
    if (row.status !== 'retired' || !Array.isArray(row.new_identities) || !row.new_identities.length
      || [row.old_stem, ...row.new_identities.map(target => target.stem)]
        .some(stem => typeof stem !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(stem))
      || row.old_number === undefined
      || numbersOf(row.old_number, row.new_identities)
        .some(number => typeof number !== 'string' || !number.startsWith('MHA-'))) fail('invalid retired identity reservation')
    for (const stem of new Set([row.old_stem, ...row.new_identities.map(target => target.stem)])) {
      if (reservedStems.has(stem)) fail(`colliding retired identity stem ${stem}`)
      reservedStems.add(stem)
    }
    for (const number of new Set(numbersOf(row.old_number, row.new_identities))) {
      if (reservedNumbers.has(number)) fail(`colliding retired identity Number ${number}`)
      reservedNumbers.add(number)
    }
  }
  for (const row of cadMap.parts_and_assemblies) {
    if (row.status === 'retired'
      || [row.old_stem, ...row.new_identities.map(target => target.stem)].some(stem => reservedStems.has(stem))
      || numbersOf(row.old_number, row.new_identities).some(number => reservedNumbers.has(number))) {
      fail(`active identity collides with retired reservation ${row.old_stem}`)
    }
  }
  if (cadMap.historical_current_aliases.some(row => [row.old_stem, row.prior_current_stem, row.current_stem]
    .some(stem => reservedStems.has(stem)))) fail('historical alias reactivates a retired identity')
  const currentRows = [...table.machineVendors, ...table.nativeIdentities,
    ...table.toolingVendors.map(row => ({ sourceStem: row.sourceStem, sourceNumber: row.sourceNumber, identities: [row] }))]
  for (const row of [...currentRows, ...table.archiveOnlyVendors.map(target => ({
    sourceStem: target.sourceStem, sourceNumber: target.sourceNumber, identities: [target],
  }))]) {
    if ([row.sourceStem, ...row.identities.map(target => target.stem)].some(stem => reservedStems.has(stem))
      || [row.sourceNumber, ...row.identities.map(target => target.number)].some(number => reservedNumbers.has(number))) {
      fail(`projected identity reactivates retired reservation ${row.sourceStem}`)
    }
  }
  const expected = sorted(cadMap.parts_and_assemblies.map(row => ({
    sourceStem: row.old_stem, sourceNumber: row.old_number, kind: row.kind ?? 'part', identities: sorted(row.new_identities.map(identity)),
  })))
  const actual = sorted(currentRows.map(row => ({
    sourceStem: row.sourceStem, sourceNumber: row.sourceNumber, kind: row.kind ?? 'part', identities: sorted(row.identities.map(identity)),
  })))
  if (!equal(actual, expected)) fail('current projection entries differ from the frozen current CAD map')
  if (table.occurrenceNamespace !== 'archive-role-local'
    || cadMap.rules?.occurrence_namespace !== table.occurrenceNamespace) fail('occurrence namespace differs from the current CAD map')
  const groups = sorted(cadMap.shared_vendor_groups.map(row => ({
    stem: row.stem, number: row.number, supplier: row.supplier, supplierSku: row.supplier_sku,
    configurations: row.configurations, neutralExportConfiguration: row.neutral_export_configuration,
  })))
  if (!equal(sorted(table.sharedVendors.map(row => ({ ...row }))), groups)) fail('shared vendor members differ from the current CAD map')
  const sourceFiles = sorted(cadMap.current_source_files.map(row => ({
    currentPath: row.current_path, sourcePath: row.source_path, configuration: row.configuration, role: row.role,
  })))
  if (!equal(sorted(table.sourceFiles.map(row => ({ ...row }))), sourceFiles)) fail('current source files differ from the current CAD map')
  const aliases = sorted(cadMap.historical_current_aliases.map(row => ({ sourceStem: row.old_stem, stem: row.prior_current_stem })))
  if (!equal(sorted(table.archivedAliases.map(row => ({ sourceStem: row.sourceStem, stem: row.stem }))), aliases)) fail('historical aliases differ from the current CAD map')
  for (const row of cadMap.historical_current_aliases) {
    if (!currentRows.some(source => source.sourceStem === row.prior_current_stem
      && source.identities.some(target => target.stem === row.current_stem))) fail(`missing active alias target ${row.current_stem}`)
  }
  if (table.archiveOnlyVendors.length !== archivedOnly.size
    || new Set(table.archiveOnlyVendors.map(row => `${row.sourceStem}/${row.parent}/${row.stem}`)).size !== archivedOnly.size
    || table.archiveOnlyVendors.some(row => !archivedOnly.has(`${row.sourceStem}/${row.parent}/${row.stem}`)
      || row.status !== 'archive-only' || row.number !== null || row.registry !== null || row.builder !== null
      || currentRows.some(source => source.identities.some(target => target.stem === row.stem && target.parent === row.parent)))) {
    fail('archive-only identities must remain exactly the three historical occurrences, without live CAD entries')
  }
  if (archivedMap) {
    const numbers = sorted(archivedMap.rows.map(row => ({ sourceStem: row.new_stem, sourceNumber: row.new_number })))
    if (!equal(sorted(table.archivedNumbers.map(row => ({ sourceStem: row.sourceStem, sourceNumber: row.sourceNumber }))), numbers)) fail('archived Numbers differ from the frozen historical map')
  }
}

/** Re-read and authenticate the real files on every authority load, including copied authoring fixtures. */
export async function validateCurrentNativeIdentityInputs(webRoot = WEB_ROOT) {
  const archivedMap = await loadNativeIdentityMap(resolve(webRoot, '../cad/config/identity-migration-map.json'))
  const table = JSON.parse(await readFile(resolve(webRoot, 'content/current-native-identities.json'), 'utf8'))
  await validateCurrentNativeIdentityTable(table)
  if (table.sourceMapSha256 !== NATIVE_IDENTITY_MAP_SHA256) fail('historical map pin differs')
  const currentBytes = await readFile(resolve(webRoot, '../cad/config/current-identity-map.json'))
  if (sha256(currentBytes) !== table.currentRegistryMapSha256) fail('current CAD map SHA256 mismatch')
  const cadMap = JSON.parse(currentBytes)
  validateCurrentNativeIdentityProjection(table, cadMap, archivedMap)
  for (const row of cadMap.retired_identities) {
    for (const stem of new Set([row.old_stem, ...row.new_identities.map(target => target.stem)])) {
      const registry = resolve(webRoot, '../cad/config/parts', `${stem}.yaml`)
      try {
        await access(registry)
      } catch (error) {
        if (error.code === 'ENOENT') continue
        throw error
      }
      fail(`retired identity still has a part registry ${stem}`)
    }
  }
}
