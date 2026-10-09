import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { createServer } from 'vite'

// Exercise the actual loader's failure contract, not renderer/source fidelity.
// The generated tracked descriptor must exist before this suite is run.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)), configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false }, appType: 'custom',
})
after(async () => { await server.close() })
let loadMachine, MECHANISM_DATA
try {
  ;({ loadMachine } = await server.ssrLoadModule('/src/scene.ts'))
  ;({ MECHANISM_DATA } = await server.ssrLoadModule('/src/mechanics.ts'))
} catch (error) { await server.close(); throw error }

function interceptFetch(t, response) {
  const original = globalThis.fetch
  const cryptoDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
  globalThis.fetch = async () => response
  if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
  t.after(() => {
    globalThis.fetch = original
    if (cryptoDescriptor) Object.defineProperty(globalThis, 'crypto', cryptoDescriptor)
    else delete globalThis.crypto
  })
}

test('tampered download is rejected before parse/scene attachment and reports its actual byte digest', async t => {
  const bytes = Buffer.from('Not the approved optimized representation')
  const observedSha256 = createHash('sha256').update(bytes).digest('hex')
  interceptFetch(t, new Response(bytes, { status: 200 }))
  let parses = 0
  const parseAsync = GLTFLoader.prototype.parseAsync
  GLTFLoader.prototype.parseAsync = async () => { parses++; throw new Error('Unapproved bytes reached GLTFLoader') }
  t.after(() => { GLTFLoader.prototype.parseAsync = parseAsync })
  const scene = new THREE.Scene()
  const machine = await loadMachine(scene, { url: 'https://invalid.test/unapproved.glb' })
  assert.equal(machine.availability, 'incompatible')
  assert.equal(machine.provenance.identity, 'mismatched')
  assert.equal(machine.provenance.observedSha256, observedSha256)
  assert.equal(machine.provenance.observedByteLength, bytes.length)
  assert.equal(machine.provenance.sourceSha256, MECHANISM_DATA.provenance.modelSha256)
  assert.equal(machine.provenance.sourceCommit, MECHANISM_DATA.provenance.sourceCommit)
  assert.notEqual(machine.provenance.observedSha256, machine.provenance.sourceSha256)
  assert.equal(parses, 0)
  assert.equal(scene.children.length, 0)
  assert.match(machine.loadError, /identity mismatch/)
  machine.dispose()
})

test('streamed progress counts decoded chunks against the approved size, not compressed Content-Length', async t => {
  const chunks = [Buffer.from('Not '), Buffer.from('the approved '), Buffer.from('representation')]
  const bytes = Buffer.concat(chunks)
  const progress = []
  let nextChunk = 0
  interceptFetch(t, new Response(new ReadableStream({
    pull(controller) {
      if (nextChunk < chunks.length) controller.enqueue(chunks[nextChunk++])
      else controller.close()
    },
  }), { headers: { 'Content-Encoding': 'gzip', 'Content-Length': '1' } }))
  const fetch = globalThis.fetch
  globalThis.fetch = async (...args) => {
    assert.equal(progress.length, 1, 'initial progress must precede the request')
    assert.equal(progress[0].phase, 'downloading')
    assert.equal(progress[0].loadedBytes, 0)
    return fetch(...args)
  }
  let parses = 0
  const parseAsync = GLTFLoader.prototype.parseAsync
  GLTFLoader.prototype.parseAsync = async () => { parses++; throw new Error('Unapproved bytes reached GLTFLoader') }
  t.after(() => { GLTFLoader.prototype.parseAsync = parseAsync })
  const scene = new THREE.Scene()
  const machine = await loadMachine(scene, {
    url: 'https://invalid.test/streamed.glb',
    onProgress: event => progress.push(event),
  })
  const totalBytes = machine.provenance.expectedByteLength
  assert.deepEqual(progress, [
    { phase: 'downloading', loadedBytes: 0, totalBytes },
    { phase: 'downloading', loadedBytes: chunks[0].length, totalBytes },
    { phase: 'downloading', loadedBytes: chunks[0].length + chunks[1].length, totalBytes },
    { phase: 'downloading', loadedBytes: bytes.length, totalBytes },
    { phase: 'preparing' },
  ])
  assert.ok(totalBytes > bytes.length, 'a compressed header must not report an early full download')
  assert.equal(machine.availability, 'incompatible')
  assert.equal(machine.provenance.identity, 'mismatched')
  assert.equal(machine.provenance.observedSha256, createHash('sha256').update(bytes).digest('hex'))
  assert.equal(machine.provenance.observedByteLength, bytes.length)
  assert.equal(parses, 0)
  assert.equal(scene.children.length, 0)
  assert.match(machine.loadError, /identity mismatch/)
  machine.dispose()
})

test('a failed response body retains received progress without preparing or invented observations', async t => {
  const bytes = Buffer.from('partial model')
  const progress = []
  let receivedChunk
  const chunkObserved = new Promise(resolve => { receivedChunk = resolve })
  let sent = false
  interceptFetch(t, new Response(new ReadableStream({
    async pull(controller) {
      if (!sent) {
        sent = true
        controller.enqueue(bytes)
      } else {
        await chunkObserved
        controller.error(new Error('Download interrupted'))
      }
    },
  })))
  const scene = new THREE.Scene()
  const machine = await loadMachine(scene, {
    url: 'https://invalid.test/interrupted.glb',
    onProgress: event => {
      progress.push(event)
      if (event.phase === 'downloading' && event.loadedBytes > 0) receivedChunk()
    },
  })
  const totalBytes = machine.provenance.expectedByteLength
  assert.deepEqual(progress, [
    { phase: 'downloading', loadedBytes: 0, totalBytes },
    { phase: 'downloading', loadedBytes: bytes.length, totalBytes },
  ])
  assert.equal(machine.availability, 'unavailable')
  assert.equal(machine.provenance.identity, 'unavailable')
  assert.equal(machine.provenance.observedSha256, null)
  assert.equal(machine.provenance.observedByteLength, null)
  assert.equal(scene.children.length, 0)
  assert.match(machine.loadError, /Download interrupted/)
  machine.dispose()
})

test('missing public artifact remains a supported unavailable state without invented observations', async t => {
  interceptFetch(t, new Response('Not found', { status: 404 }))
  const scene = new THREE.Scene()
  const progress = []
  const machine = await loadMachine(scene, {
    url: 'https://invalid.test/missing.glb',
    onProgress: event => progress.push(event),
  })
  assert.deepEqual(progress, [
    { phase: 'downloading', loadedBytes: 0, totalBytes: machine.provenance.expectedByteLength },
  ])
  assert.equal(machine.availability, 'unavailable')
  assert.equal(machine.provenance.identity, 'unavailable')
  assert.equal(machine.provenance.observedSha256, null)
  assert.equal(machine.provenance.observedByteLength, null)
  assert.equal(scene.children.length, 0)
  assert.match(machine.loadError, /HTTP 404/)
  machine.dispose()
})
