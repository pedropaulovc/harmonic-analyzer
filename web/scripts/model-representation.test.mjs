import test from 'node:test'
import assert from 'node:assert/strict'
import { assertNativeSourceAssociation, assertModelRepresentationBytes, validateModelRepresentation } from '../model-representation.mjs'

function approved() {
  return {
    schemaVersion: 1, kind: 'lossless-web-model-representation',
    source: { sha256: '1'.repeat(64), sourceCommit: 'a'.repeat(40) },
    representation: { path: 'models/harmonic-analyzer.glb', sha256: '2'.repeat(64), byteLength: 1024, codec: 'EXT_meshopt_compression' },
    pipeline: { version: 1, steps: ['exact-dedup', 'meshopt'], codecVersion: 'meshoptimizer@0.22.0' },
    equivalence: { method: 'decoded-per-drawable-exact-v1', semanticSha256: '3'.repeat(64), drawableCount: 2 },
  }
}
const native = { modelSha256: '1'.repeat(64), sourceCommit: 'a'.repeat(40) }
const downloaded = { sha256: '2'.repeat(64), byteLength: 1024 }

test('a pinned derivative accepts actual transport identity, not a fabricated raw observed digest', () => {
  assertModelRepresentationBytes(approved(), native, downloaded)
  assert.throws(() => assertModelRepresentationBytes(approved(), native, { ...downloaded, sha256: native.modelSha256 }), /identity mismatch/)
  assert.throws(() => assertModelRepresentationBytes(approved(), native, { ...downloaded, byteLength: downloaded.byteLength - 1 }), /identity mismatch/)
})

test('representation and native source association must match both source digest and commit', () => {
  for (const altered of [
    { ...native, modelSha256: '4'.repeat(64) },
    { ...native, sourceCommit: 'b'.repeat(40) },
  ]) assert.throws(() => assertNativeSourceAssociation(approved(), altered), /different native CAD source/)
})

test('unknown transforms, schemas and malformed approval identities fail closed', () => {
  const changes = [
    record => { record.quantize = true },
    record => { record.schemaVersion = 2 },
    record => { record.source.sha256 = 'A'.repeat(64) },
    record => { record.source.sourceCommit = 'a'.repeat(39) },
    record => { record.representation.path = '../unapproved.glb' },
    record => { record.representation.byteLength = 0 },
    record => { record.representation.byteLength = 1.5 },
    record => { record.representation.codec = 'KHR_draco_mesh_compression' },
    record => { record.pipeline.version = 2 },
    record => { record.pipeline.steps.push('quantize') },
    record => { record.pipeline.steps.reverse() },
    record => { record.pipeline.codecVersion = 'unknown' },
    record => { record.equivalence.semanticSha256 = '3'.repeat(63) },
    record => { record.equivalence.drawableCount = 0 },
    record => { record.equivalence.method = 'bounds-only' },
  ]
  for (const change of changes) {
    const record = approved()
    change(record)
    assert.throws(() => validateModelRepresentation(record), /Invalid/)
  }
  for (const key of ['source', 'representation', 'pipeline', 'equivalence']) {
    const record = approved()
    record[key].unapproved = true
    assert.throws(() => validateModelRepresentation(record), /fields/)
  }
})
