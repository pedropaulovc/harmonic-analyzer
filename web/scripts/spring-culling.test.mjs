import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { webcrypto } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import * as THREE from 'three'
import { createServer } from 'vite'
import { nativeImageBitmap } from './native-image-bitmap.mjs'

// Real released geometry and the live native evaluator are the containment
// oracle. This is not framebuffer/GL proof; Windows Chrome checks own that.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)), configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false }, appType: 'custom',
})
after(async () => {
  nativeFixture?.machine.dispose()
  await server.close()
})
let loadMachine, MECHANISM_DATA, nativeCaptureModels, sealNativeDrawState, createSpringCullingBounds
try {
  ;({ loadMachine } = await server.ssrLoadModule('/src/scene.ts'))
  ;({ MECHANISM_DATA } = await server.ssrLoadModule('/src/mechanics.ts'))
  ;({ nativeCaptureModels, sealNativeDrawState } = await server.ssrLoadModule('/src/native-primitive-snapshot.ts'))
  ;({ createSpringCullingBounds } = await server.ssrLoadModule('/src/spring-culling-bounds.ts'))
} catch (error) { await server.close(); throw error }

let nativeFixture
async function fixture() {
  if (nativeFixture) return nativeFixture
  const descriptor = JSON.parse(await readFile(new URL('../content/model-representation.json', import.meta.url), 'utf8'))
  const modelPath = process.env.SPRING_MODEL_PATH
    ?? fileURLToPath(new URL(`../.vite/deployment-model/${descriptor.representation.sha256}.glb`, import.meta.url))
  // A missing exact asset fails with its actual path; do not silently substitute
  // a miniature/mock spring or skip the native geometry containment assertions.
  const bytes = await readFile(modelPath)
  const originalFetch = globalThis.fetch
  const globals = new Map(['fetch', 'self', 'createImageBitmap', 'location', 'crypto']
    .map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]))
  const modelUrl = 'https://native-model.test/approved.glb'
  const scene = new THREE.Scene()
  let machine
  try {
    globalThis.fetch = async (input, options) => {
      const url = input instanceof Request ? input.url : String(input)
      return url === modelUrl ? new Response(bytes) : originalFetch(input, options)
    }
    Object.defineProperty(globalThis, 'self', { value: globalThis, configurable: true })
    Object.defineProperty(globalThis, 'createImageBitmap', { value: nativeImageBitmap, configurable: true })
    Object.defineProperty(globalThis, 'location', { value: { href: 'https://native-model.test/' }, configurable: true })
    if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
    machine = await loadMachine(scene, { url: modelUrl, nativePrimitiveSnapshots: true })
  } finally {
    for (const [key, descriptor] of globals) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor)
      else delete globalThis[key]
    }
  }
  assert.equal(machine.availability, 'available', machine.loadError ?? machine.missing.join('\n'))
  assert.deepEqual(machine.missing, [])
  machine.update(machine.input)
  const root = scene.children[0], model = nativeCaptureModels.get(root)
  assert.ok(model)
  const springs = []
  const textures = new Set()
  root.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value)
    }
    const evaluator = model.spring(object)
    if (evaluator) springs.push({ mesh: object, evaluator })
  })
  assert.ok(textures.size > 0, 'The real embedded native image must not disappear through a swallowed texture-loading failure')
  for (const texture of textures) {
    assert.ok(Number.isSafeInteger(texture.image.width) && texture.image.width > 0)
    assert.ok(Number.isSafeInteger(texture.image.height) && texture.image.height > 0)
    assert.ok(texture.image.data instanceof Uint8Array)
    assert.equal(texture.image.data.length, texture.image.width * texture.image.height * 4)
  }
  assert.equal(new Set(springs.map(entry => entry.evaluator)).size, 21)
  nativeFixture = { scene, machine, root, model, springs }
  return nativeFixture
}

function assertContained(mesh, evaluator, matrix = null, stride = 1) {
  const sphere = matrix ? mesh.boundingSphere.clone().applyMatrix4(matrix) : mesh.boundingSphere
  const position = mesh.geometry.getAttribute('position')
  const vertex = new THREE.Vector3(), deformed = new THREE.Vector3()
  let maximumDistance = 0
  for (let i = 0; i < position.count; i += stride) {
    vertex.fromBufferAttribute(position, i)
    evaluator.evaluate(mesh.geometry, i, vertex, deformed)
    if (matrix) deformed.applyMatrix4(matrix)
    const distance = deformed.distanceTo(sphere.center)
    assert.ok(Number.isFinite(distance) && distance <= sphere.radius + 1e-12,
      `${mesh.name} vertex ${i} at span ${evaluator.length.value}: distance ${distance} exceeds sphere radius ${sphere.radius}`)
    maximumDistance = Math.max(maximumDistance, distance)
  }
  return maximumDistance
}

test('every actual native spring vertex is enclosed at rest, catalog extrema and source-override spans', async () => {
  const { machine, springs } = await fixture()
  const identities = springs.map(({ mesh }) => ({ mesh, geometry: mesh.geometry, material: mesh.material,
    attributes: { ...mesh.geometry.attributes }, index: mesh.geometry.index, name: mesh.name, parent: mesh.parent }))
  for (const { mesh, evaluator } of springs) {
    const stock = evaluator.descriptor().stock === 'counter' ? MECHANISM_DATA.counter : MECHANISM_DATA.spring
    const rest = evaluator.restLength.value
    const spans = [stock.freeLengthMm / 1000 - 1e-9, rest,
      (stock.freeLengthMm + stock.maximumLengthMm) / 2000,
      stock.maximumLengthMm / 1000 + 1e-9, 0.001, 0.75, -0.05]
    for (const span of spans) {
      evaluator.length.value = span
      assert.equal(mesh.frustumCulled, true)
      assert.ok(mesh.boundingSphere instanceof THREE.Sphere && Number.isFinite(mesh.boundingSphere.radius))
      const maximumDistance = assertContained(mesh, evaluator)
      if (span >= stock.freeLengthMm / 1000 - 1e-9 && span <= stock.maximumLengthMm / 1000 + 1e-9) {
        assert.ok(mesh.boundingSphere.radius / maximumDistance < 1.5,
          `${mesh.name} at ${span}: a conservative sphere must remain useful for culling, not exceed actual radius by 50%`)
      }
    }
  }
  machine.update(machine.input)
  for (const before of identities) {
    assert.equal(before.mesh.geometry, before.geometry)
    assert.equal(before.mesh.material, before.material)
    assert.equal(before.mesh.geometry.index, before.index)
    assert.equal(before.mesh.name, before.name)
    assert.equal(before.mesh.parent, before.parent)
    for (const [name, attribute] of Object.entries(before.attributes)) assert.equal(before.mesh.geometry.getAttribute(name), attribute)
  }
})

test('native spring bounds follow transformed owners and source visibility/lever overrides', async () => {
  const { machine, model, springs } = await fixture()
  assert.equal(machine.availability, 'available')
  const moved = new THREE.Matrix4().compose(new THREE.Vector3(.31, -.27, .08),
    new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 2, -1).normalize(), 1.13), new THREE.Vector3(1.4, .8, 1.2))
  for (const { mesh, evaluator } of springs) {
    assertContained(mesh, evaluator, moved.clone().multiply(mesh.matrixWorld), Math.max(1, Math.floor(mesh.geometry.getAttribute('position').count / 128)))
  }
  const leverPath = 'ha-harmonic-analyzer/ch-channel/ch-channel-lever-1'
  const springPath = 'ha-harmonic-analyzer/ch-channel/vn-channel-spring-installed-stretch00-1'
  assert.ok(machine.partPaths.includes(springPath))
  const intended = springs.filter(({ mesh }) => model.identity(mesh).nodePath === springPath)
  assert.ok(intended.length > 0, 'Station 1 must resolve to its actual canonical native spring owner')
  const normalLength = intended[0].evaluator.length.value
  machine.update(machine.input, baseline => {
    const world = new Float64Array(16)
    assert.equal(baseline.readWorldMatrix(leverPath, world), true)
    assert.equal(baseline.readVisibility(springPath, 'effective'), true)
    const leverPosition = [world[12] + .12, world[13] + .08, world[14]]
    return [{ partPath: leverPath, worldPositionMetres: leverPosition }, { partPath: springPath, visibility: 'hidden' }]
  })
  assert.notEqual(intended[0].evaluator.length.value, normalLength, 'The real station-1 lever override must update its spring shader length')
  for (const { mesh } of springs) {
    let visible = true
    for (let owner = mesh; owner; owner = owner.parent) if (!owner.visible) visible = false
    assert.equal(visible, model.identity(mesh).nodePath !== springPath,
      'The intended canonical spring must be hidden without hiding other native spring owners')
  }
  assert.deepEqual(machine.missing, [])
  for (const { mesh, evaluator } of springs) assertContained(mesh, evaluator, mesh.matrixWorld)
  const probe = machine.createPartVisibilityProbe()
  assert.ok(probe.partPaths.some(path => path === springPath || path.startsWith(`${springPath}/`)))
  probe.dispose()
  machine.update(machine.input)
})

test('two owners sharing prepared geometry retain independent live culling spheres', async () => {
  const { springs } = await fixture()
  const { mesh, evaluator } = springs[0]
  const dimensions = evaluator.descriptor().constants
  const left = new THREE.Mesh(mesh.geometry, mesh.material), right = new THREE.Mesh(mesh.geometry, mesh.material)
  const before = mesh.geometry.boundingSphere?.clone() ?? null
  const a = createSpringCullingBounds(left, { radius: dimensions.radiusM, inset: dimensions.insetM, endCorrection: dimensions.endCorrectionM, turns: dimensions.turns })
  const b = createSpringCullingBounds(right, { radius: dimensions.radiusM, inset: dimensions.insetM, endCorrection: dimensions.endCorrectionM, turns: dimensions.turns })
  a.update(.05, evaluator.restLength.value); b.update(.3, evaluator.restLength.value)
  assert.notEqual(left.boundingSphere, right.boundingSphere)
  assert.ok(right.boundingSphere.radius > left.boundingSphere.radius * 2)
  const saved = right.boundingSphere.clone()
  a.update(.09, evaluator.restLength.value)
  assert.equal(right.boundingSphere.equals(saved), true)
  if (before) assert.equal(mesh.geometry.boundingSphere.equals(before), true)
  else assert.equal(mesh.geometry.boundingSphere, null)
  a.update(Infinity, evaluator.restLength.value)
  assert.equal(left.boundingSphere.radius, Infinity)
  a.update(1e30, evaluator.restLength.value)
  assert.equal(left.boundingSphere.radius, Infinity, 'Float32 tangent normalization overflow must not produce a false finite enclosure')
})

test('Three frustum culling uses the live object sphere instead of the stale source-geometry sphere', () => {
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([-.02, 0, .003, .02, 0, .003], 3))
  geometry.setAttribute('springCoordinate', new THREE.Float32BufferAttribute([0, 0, 0, 1], 2))
  geometry.setAttribute('springRestCentre', geometry.getAttribute('position').clone())
  geometry.setAttribute('springRestTangent', new THREE.Float32BufferAttribute([1, 0, 0, 1, 0, 0], 3))
  geometry.computeBoundingSphere()
  const material = new THREE.MeshBasicMaterial(), mesh = new THREE.Mesh(geometry, material)
  const camera = new THREE.OrthographicCamera(-.01, .01, .01, -.01, .1, 2)
  camera.position.set(.09, 0, 1); camera.lookAt(.09, 0, 0); camera.updateMatrixWorld(true)
  const frustum = new THREE.Frustum().setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse))
  assert.equal(frustum.intersectsObject(mesh), false)
  const bound = createSpringCullingBounds(mesh, { radius: .003, inset: .005, endCorrection: 0, turns: 1 })
  bound.update(.2, .05)
  assert.equal(frustum.intersectsObject(mesh), true)
  bound.update(.05, .05)
  assert.equal(frustum.intersectsObject(mesh), false)
  geometry.dispose(); material.dispose()
})

test('native draw state becomes stale when a spring culling sphere or culling flag changes', async () => {
  const { machine, model, springs } = await fixture()
  machine.update(machine.input)
  const mesh = springs[0].mesh, sphere = mesh.boundingSphere
  const token = sealNativeDrawState(model)
  assert.equal(token.matches(), true)
  sphere.radius += .001
  assert.equal(token.matches(), false)
  sphere.radius -= .001
  const centreToken = sealNativeDrawState(model)
  sphere.center.x += .01
  assert.equal(centreToken.matches(), false)
  sphere.center.x -= .01
  const flagToken = sealNativeDrawState(model)
  mesh.frustumCulled = false
  assert.equal(flagToken.matches(), false)
  mesh.frustumCulled = true
})
