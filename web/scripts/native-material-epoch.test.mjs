import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import * as THREE from 'three'
import { createServer } from 'vite'

// Real TS module, real Three materials, bounded descriptor GL contract only.
// This suite does not emulate GPU pixels, draws, or qualification acceptance.
// Materialize immutable controls beside src/native-material-capture.ts so its
// relative imports resolve, then inject the unchanged module with this seam.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)), configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null }, appType: 'custom',
})
after(async () => { await server.close() })
let createNativeMaterialCapture
try {
  ;({ createNativeMaterialCapture } = await server.ssrLoadModule(
    process.env.NATIVE_MATERIAL_CAPTURE_MODULE_PATH ?? '/src/native-material-capture.ts',
  ))
} catch (error) { await server.close(); throw error }

function fixture(t) {
  const cryptoDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
  if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
  t.after(() => {
    if (cryptoDescriptor) Object.defineProperty(globalThis, 'crypto', cryptoDescriptor)
    else delete globalThis.crypto
  })
  const gl = {
    getBufferSubData() { throw new Error('Untextured descriptor test must not query GPU bytes') },
    isContextLost() { return false },
  }
  for (const name of ['texImage2D', 'texSubImage2D', 'compressedTexImage2D', 'compressedTexSubImage2D', 'copyTexImage2D', 'copyTexSubImage2D', 'texStorage2D', 'generateMipmap', 'texParameteri', 'texParameterf']) {
    gl[name] = () => { throw new Error('Untextured descriptor test must not mutate GPU storage') }
  }
  const capture = createNativeMaterialCapture({ getContext: () => gl })
  t.after(() => capture.dispose())
  const objects = new Map()
  let viewKey
  const sink = { async put(bytes) {
    const sha256 = createHash('sha256').update(bytes).digest('hex')
    objects.set(sha256, bytes.slice())
    return { sha256, byteLength: bytes.byteLength }
  } }
  return {
    capture,
    // The immutable reviewed implementation predates the lifecycle method.
    // Absence is deliberately not a test failure: its descriptor behavior is.
    begin(key) { viewKey = key; capture.beginView?.(key) },
    async record(material, ...keys) {
      const sha256 = await capture.capture(material, sink, keys.length ? keys[0] : viewKey)
      return JSON.parse(new TextDecoder().decode(objects.get(sha256)))
    },
  }
}

function material(t) {
  const result = new THREE.MeshStandardMaterial({ color: 0x284b63, roughness: 0.3, alphaTest: 0 })
  result.name = 'original native material'
  t.after(() => result.dispose())
  return result
}

// Calling observeDraw is the descriptor observer seam, not a claim that this
// bounded Node fixture executed a standard GL draw. Actual draw timing and
// hidden mesh behavior are covered by the parent-owned browser control.
test('a later hidden epoch serializes changed installed material, not an earlier compatible draw', async t => {
  const f = fixture(t), original = material(t)
  f.begin('71:left')
  f.capture.observeDraw(original)
  const drawn = await f.record(original)
  assert.equal(drawn.properties.alphaTest, 0)
  assert.equal(drawn.properties.roughness, 0.3)
  original.alphaTest = 1.001
  original.roughness = 0.91
  original.color.setRGB(0.9, 0.05, 0.4)
  original.clippingPlanes = [new THREE.Plane(new THREE.Vector3(1, 0, 0), -0.125)]
  f.begin('72:left') // No observeDraw: this material has no submission in the new epoch.
  const hidden = await f.record(original)
  assert.equal(hidden.properties.alphaTest, 1.001)
  assert.equal(hidden.properties.roughness, 0.91)
  assert.deepEqual(hidden.properties.color, original.color.toArray())
  assert.deepEqual(hidden.clippingPlanes, [[1, 0, 0, -0.125]])
})

test('another view in the same epoch cannot inherit the first view material descriptor', async t => {
  const f = fixture(t), original = material(t)
  f.begin('83:left')
  f.capture.observeDraw(original)
  await f.record(original)
  original.opacity = 0.375
  original.transparent = true
  original.depthWrite = false
  f.begin('83:right') // Same completed scene epoch, different actual view.
  const hidden = await f.record(original)
  assert.equal(hidden.properties.opacity, 0.375)
  assert.equal(hidden.properties.transparent, true)
  assert.equal(hidden.properties.depthWrite, false)
})

test('unchanged nondrawn material and a fresh visible draw retain their original descriptor semantics', async t => {
  const f = fixture(t), original = material(t)
  f.begin('94:left')
  f.capture.observeDraw(original)
  const visible = await f.record(original)
  f.begin('95:left')
  assert.deepEqual(await f.record(original), visible)
  original.alphaTest = 0.4
  original.color.setRGB(0.1, 0.7, 0.2)
  f.begin('95:right')
  f.capture.observeDraw(original)
  const redrawn = await f.record(original)
  assert.equal(redrawn.properties.alphaTest, 0.4)
  assert.deepEqual(redrawn.properties.color, original.color.toArray())
})

test('same-view transparent two-pass snapshot keeps the restored original material side', async t => {
  const f = fixture(t), original = material(t)
  original.transparent = true
  original.side = THREE.DoubleSide
  f.begin('106:transparent')
  original.side = THREE.BackSide
  f.capture.observeDraw(original)
  original.side = THREE.FrontSide
  f.capture.observeDraw(original)
  original.side = THREE.DoubleSide
  const restored = await f.record(original)
  assert.equal(restored.properties.side, THREE.DoubleSide)
  assert.equal(restored.properties.transparent, true)
})

test('delayed capture of an earlier view selects its actual draw after another view draws the same material', async t => {
  const f = fixture(t), original = material(t)
  original.alphaTest = 0.25
  f.begin('117:left')
  f.capture.observeDraw(original)
  const left = await f.record(original)
  original.alphaTest = 0.75
  f.begin('117:right')
  f.capture.observeDraw(original)
  assert.equal((await f.record(original)).properties.alphaTest, 0.75)
  assert.deepEqual(await f.record(original, '117:left'), left)
})

test('a new epoch removes earlier view draw authority and refuses foreign or omitted capture keys', async t => {
  const f = fixture(t), original = material(t)
  f.begin('128:left')
  f.capture.observeDraw(original)
  await f.record(original)
  original.alphaTest = 0.81
  f.begin('129:right')
  assert.equal((await f.record(original)).properties.alphaTest, 0.81)
  await assert.rejects(f.record(original, '128:left'), /view/i)
  await assert.rejects(f.record(original, '129:missing'), /view/i)
  await assert.rejects(f.record(original, undefined), /view/i)
})

test('a current nondrawn texture assignment is described without borrowing previous draw or GPU sampler authority', async t => {
  const f = fixture(t), original = material(t)
  f.begin('140:left')
  f.capture.observeDraw(original)
  await f.record(original)
  const texture = new THREE.Texture()
  t.after(() => texture.dispose())
  texture.repeat.set(3, 2)
  texture.offset.set(0.125, 0.25)
  original.map = texture
  f.begin('141:left')
  const current = await f.record(original)
  assert.deepEqual(current.textures.map(entry => entry.slot), ['map'])
  assert.deepEqual(current.textures[0].repeat, [3, 2])
  assert.deepEqual(current.textures[0].offset, [0.125, 0.25])
  assert.equal(current.textures[0].source.authority, 'unmeasured-original-gpu-texture')
  assert.match(current.textures[0].source.reason, /draw/i)
})
