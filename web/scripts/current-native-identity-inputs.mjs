import { readFile } from 'node:fs/promises'
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
const identity = row => ({ parent: row.parent ?? null, stem: row.stem, number: row.number })
const archivedOnly = new Set([
  'vn-transgear-collar-cross-pin/pd-paper-drive/pd-vn-transgear-collar-cross-pin',
  'vn-latch-hook-rivet/pd-paper-drive/pd-vn-latch-hook-rivet',
  'vn-pedestal-hold-down-screw/ch-channel/ch-vn-pedestal-hold-down-screw',
])

/** Only active rows must equal CAD; the three explicitly retired archive occurrences are not registry entries. */
export function validateCurrentNativeIdentityProjection(table, cadMap, archivedMap) {
  if (cadMap.schema_version !== 1 || !Array.isArray(cadMap.parts_and_assemblies)) fail('invalid current CAD map')
  const currentRows = [...table.machineVendors, ...table.nativeIdentities,
    ...table.toolingVendors.map(row => ({ sourceStem: row.sourceStem, sourceNumber: row.sourceNumber, identities: [row] }))]
  const expected = sorted(cadMap.parts_and_assemblies.map(row => ({
    sourceStem: row.old_stem, sourceNumber: row.old_number, kind: row.kind ?? 'part', identities: sorted(row.new_identities.map(identity)),
  })))
  const actual = sorted(currentRows.map(row => ({
    sourceStem: row.sourceStem, sourceNumber: row.sourceNumber, kind: row.kind ?? 'part', identities: sorted(row.identities.map(identity)),
  })))
  if (!equal(actual, expected)) fail('current projection entries differ from the frozen current CAD map')
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
  validateCurrentNativeIdentityProjection(table, JSON.parse(currentBytes), archivedMap)
}
