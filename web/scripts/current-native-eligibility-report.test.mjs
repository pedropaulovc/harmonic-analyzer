import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { createContext, runInContext } from 'node:vm'

const { collectCurrentNativeEligibilityEvidence } = await import(
  process.env.CURRENT_NATIVE_ELIGIBILITY_REPORT_MODULE ?? './current-native-eligibility-report.mjs'
)

// Execute the collector's browser callbacks, with the lease's real asynchronous
// refusal/callback/restoration contract. Synthetic bytes are not native proof.
function browser({ refusal = null, restorationError = null, snapshotStatus = 'captured' } = {}) {
  const counters = { released: 0, disposed: 0, captureCalls: 0 }
  const positions = new Float32Array([0.25, -0.5, 1])
  const capture = { status: 'captured', landmarks: [{ id: 'anchor', sourcePixels: [12, 34] }] }
  const metadata = { status: 'current-diagnostic-submission', draw: { viewId: 'main' } }
  const snapshot = { status: snapshotStatus, reason: snapshotStatus === 'captured' ? null : 'Native geometry is unavailable',
    manifest: { primitives: [], runtimeClones: [] }, buffers: snapshotStatus === 'captured' ? { primitive: { localPositions: positions } } : null }
  const context = createContext({ window: { harmonicAnalyzer: {
    renderedLandmarks() { counters.captureCalls++; return capture },
    renderedMechanism() { return { status: 'captured', drawRevision: 7 } },
    nativePrimitiveSnapshot() { return snapshot },
    async withNativeDiagnosticLease(run) {
      if (refusal) throw refusal
      try {
        return await run({ readNativeDrawMetadata: () => metadata, readRegisteredNativeLandmarkAnchors: () => [] })
      } finally {
        counters.released++
        if (restorationError) throw restorationError
      }
    },
  } }, btoa: text => Buffer.from(text, 'binary').toString('base64') })
  const invoke = (callback, ...args) => runInContext(`(${callback.toString()})`, context)(...args)
  const page = { async evaluateHandle(callback, arg) {
    const state = await invoke(callback, arg)
    return { async evaluate(callback, arg) { return structuredClone(await invoke(callback, state, arg)) }, async dispose() { counters.disposed++ } }
  } }
  return { page, counters, capture, metadata, positions }
}

const frame = { views: [{ id: 'main' }], landmarks: [] }
const collect = fixture => collectCurrentNativeEligibilityEvidence(fixture.page, frame, {}, {}, { collect: true })

test('lease refusal preserves unavailable cause, pre-lease snapshot and captures', async () => {
  for (const snapshotStatus of ['captured', 'unavailable']) {
    const reason = 'Native diagnostics require a current completed idle native model/frame and paused source'
    const fixture = browser({ refusal: new Error(reason), snapshotStatus })
    const evidence = await collect(fixture)
    assert.equal(evidence.collection.status, 'unavailable')
    assert.equal(evidence.collection.reason, reason)
    assert.equal(evidence.collection.snapshotStatus, snapshotStatus)
    assert.equal(evidence.snapshot.status, snapshotStatus)
    assert.equal(evidence.snapshot.buffers, null)
    assert.deepEqual(evidence.captures, [{ viewId: 'main', capture: fixture.capture, mechanism: { status: 'captured', drawRevision: 7 } }])
    assert.equal(evidence.currentMetadata, null)
    assert.deepEqual(evidence.queries, [])
    assert.equal(evidence.collection.byteLength, 0)
    assert.equal(fixture.counters.released, 0)
    assert.equal(fixture.counters.disposed, 1)
  }
})

test('successful collection transports exact bytes and releases its lease', async () => {
  const fixture = browser()
  const evidence = await collect(fixture)
  assert.equal(evidence.collection.status, 'collected')
  assert.equal(evidence.collection.reason, null)
  assert.deepEqual(evidence.currentMetadata, fixture.metadata)
  assert.deepEqual(evidence.snapshot.buffers.primitive.localPositions, fixture.positions)
  assert.equal(evidence.collection.byteLength, fixture.positions.byteLength)
  assert.deepEqual(evidence.collection.bufferReceipts, [{ primitiveId: 'primitive', name: 'localPositions', arrayType: 'Float32Array',
    byteLength: fixture.positions.byteLength, sha256: createHash('sha256').update(new Uint8Array(fixture.positions.buffer)).digest('hex') }])
  assert.equal(fixture.counters.released, 1)
  assert.equal(fixture.counters.disposed, 1)
})

test('new lease restoration errors remain failures rather than collected evidence', async () => {
  const error = new Error('Native restoration failed')
  const fixture = browser({ restorationError: error })
  await assert.rejects(collect(fixture), failure => failure === error)
  assert.equal(fixture.counters.released, 1)
  assert.equal(fixture.counters.disposed, 1)
})
