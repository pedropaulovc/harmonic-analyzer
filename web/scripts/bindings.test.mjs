import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { projectCurrentNativeMetadata } from '../current-native-identity.mjs'

// Declarative articulation registry only: no model bytes, GL or solver. The
// census refuses a present-but-unbound thumb screw instead of drawing it fixed.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false },
  appType: 'custom',
})
after(async () => { await server.close() })
let BINDINGS, unboundThumbScrewFailures, UNBOUND_THUMB_SCREW_ISSUE
try {
  ;({ BINDINGS, unboundThumbScrewFailures, UNBOUND_THUMB_SCREW_ISSUE } = await server.ssrLoadModule('/src/bindings.ts'))
} catch (error) {
  await server.close()
  throw error
}
const archivedInventory = JSON.parse(await readFile(new URL('../content/v39-source/native-inventory.json', import.meta.url), 'utf8'))
const inventory = projectCurrentNativeMetadata(archivedInventory)
const RELEASED_PATHS = inventory.inventory.map(row => row.path)
const MAGNIFIER = 'ha-harmonic-analyzer/mg-magnifier/'
const FIXTURE_SCREW = `${MAGNIFIER}mg-vn-thumb-screw-2`

test('the current released native census has no unbound thumb-screw instance', () => {
  assert.ok(RELEASED_PATHS.includes(`${MAGNIFIER}mg-vn-thumb-screw-1`))
  assert.ok(!RELEASED_PATHS.includes(FIXTURE_SCREW), 'release 39 predates the output-fixture screw')
  assert.deepEqual(unboundThumbScrewFailures(RELEASED_PATHS), [])
  const clamp = BINDINGS.find(binding => binding.id === 'magnifierClamp')
  assert.ok(clamp.pattern.test(`${MAGNIFIER}mg-vn-thumb-screw-1`))
  assert.equal(clamp.motion, 'magnifier-clamp')
})

test('a present output-fixture thumb screw with no binding is refused by name and issue', () => {
  const failures = unboundThumbScrewFailures([...RELEASED_PATHS, FIXTURE_SCREW])
  assert.equal(failures.length, 1)
  assert.ok(failures[0].startsWith(`${FIXTURE_SCREW}: `), failures[0])
  assert.ok(UNBOUND_THUMB_SCREW_ISSUE.startsWith('web: bind magnifier fixture thumb-screw-2 to the output fixture at next GLB refresh'), UNBOUND_THUMB_SCREW_ISSUE)
  assert.ok(failures[0].includes('https://github.com/pedropaulovc/harmonic-analyzer/issues/1351'), failures[0])
  assert.ok(failures[0].includes(UNBOUND_THUMB_SCREW_ISSUE), failures[0])
  assert.ok(!BINDINGS.some(binding => binding.pattern.test(FIXTURE_SCREW)), 'no binding may silently claim the unreleased screw')
})

test('the census is generic over thumb-screw instances and ignores other unbound parts', () => {
  const failures = unboundThumbScrewFailures([`${MAGNIFIER}mg-vn-thumb-screw-7`, `${MAGNIFIER}mg-wheel-axle-1`, 'ha-harmonic-analyzer/pn-pen/pn-vn-thumb-screw-1'])
  assert.deepEqual(failures.map(line => line.split(': ')[0]), [`${MAGNIFIER}mg-vn-thumb-screw-7`])
})

test('every binding resolves its exact census after archive ingestion projection', () => {
  for (const binding of BINDINGS) {
    assert.equal(RELEASED_PATHS.filter(path => binding.pattern.test(path)).length, binding.expected, binding.id)
  }
  assert.ok(RELEASED_PATHS.includes(`${MAGNIFIER}mg-vn-lever-wire-1`))
  assert.ok(RELEASED_PATHS.includes('ha-harmonic-analyzer/pn-pen/pn-vn-pen-wire-1'))
  assert.ok(RELEASED_PATHS.includes('ha-harmonic-analyzer/pn-pen/pn-vn-pen-marker-1'))
  assert.ok(RELEASED_PATHS.includes('ha-harmonic-analyzer/pd-paper-drive/pd-vn-transgear-collar-cross-pin-1'))
  assert.ok(RELEASED_PATHS.includes('ha-harmonic-analyzer/pd-paper-drive/pd-vn-latch-hook-rivet-1'))
})

test('projected binding census retains historical inventory provenance and transforms', () => {
  assert.strictEqual(inventory.identity, archivedInventory.identity)
  assert.strictEqual(inventory.source, archivedInventory.source)
  assert.equal(inventory.sha256, archivedInventory.sha256)
  assert.ok(archivedInventory.inventory.some(row => row.path === `${MAGNIFIER}vn-thumb-screw-1`))
  assert.ok(!archivedInventory.inventory.some(row => row.path === `${MAGNIFIER}mg-vn-thumb-screw-1`))
  inventory.inventory.forEach((row, index) => {
    assert.strictEqual(row.world, archivedInventory.inventory[index].world)
  })
})
