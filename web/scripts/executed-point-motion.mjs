import { readFile } from 'node:fs/promises'
import { webcrypto } from 'node:crypto'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline'
import * as THREE from 'three'
import { createServer, createLogger } from 'vite'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const finitePoint = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite)
const supportedMotion = motion => motion === 'crank' || motion === 'wheel'
const EMPTY_OVERRIDES = Object.freeze([])

/** CPU-only capability classification, not source pose, visibility, or raster proof.
 * Load the approved real GLB once and read only this update's NORMAL matrix lease.
 * The private pairs never alter the chosen source inputs/cameras/assembly metadata.
 */
export async function createPointMotionClassifier({ webRoot = WEB_ROOT, modelPath } = {}) {
  const approved = JSON.parse(await readFile(resolve(webRoot, 'content/model-representation.json'), 'utf8'))
  const manifest = JSON.parse(await readFile(resolve(webRoot, 'content/canonical-native/manifest.json'), 'utf8'))
  const logger = createLogger()
  logger.info = message => process.stderr.write(`${message}\n`)
  const server = await createServer({ root: webRoot, configFile: false, customLogger: logger,
    server: { middlewareMode: true, hmr: false, ws: false, watch: null }, appType: 'custom' })
  let machine
  try {
    const { loadMachine } = await server.ssrLoadModule('/src/scene.ts')
    const { BINDINGS } = await server.ssrLoadModule('/src/bindings.ts')
    const { compileInput, solveSourceInput } = await server.ssrLoadModule('/src/source-witness.ts')
    const { createMechanismPose } = await server.ssrLoadModule('/src/mechanics.ts')
    const scene = new THREE.Scene()
    const url = `http://localhost/${approved.representation.path}`
    const globals = ['fetch', 'location', 'self', 'crypto'].map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)])
    try {
      // File transport only: loadMachine still hashes, decodes, binds and articulates
      // the actual approved browser representation, with no inventory scene substitute.
      const bytes = await readFile(modelPath ?? resolve(webRoot, 'public', approved.representation.path))
      globalThis.fetch = async requested => {
        if (String(requested) !== url) throw new Error(`Unexpected native model request: ${requested}`)
        return new Response(bytes, { status: 200 })
      }
      globalThis.location = { href: 'http://localhost/' }
      globalThis.self = globalThis
      if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true })
      machine = await loadMachine(scene, { url })
    } finally {
      for (const [key, descriptor] of globals) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor)
        else delete globalThis[key]
      }
    }
    if (machine.availability !== 'available' || machine.provenance.identity !== 'matched' || machine.missing.length) {
      throw new Error(`Actual native motion model unavailable: ${machine.loadError ?? machine.missing.join('; ')}`)
    }
    // Only supported rigid candidate nodes retain a rest inverse, before any update.
    // No geometry/primitive dumps, duplicated axis catalogue, or draw certificates.
    const parts = new Map()
    scene.updateMatrixWorld(true)
    function visit(node, parentPath) {
      const name = typeof node.userData.name === 'string' ? node.userData.name : node.name
      const path = parentPath ? `${parentPath}/${name}` : name
      const binding = BINDINGS.find(binding => binding.pattern.test(path))
      if (supportedMotion(binding?.motion)) {
        let unsupported = false
        node.traverse(child => {
          if (child.isSkinnedMesh || child.isInstancedMesh || child.isBatchedMesh
            || (child.isMesh && Object.keys(child.geometry.morphAttributes).length)) unsupported = true
        })
        parts.set(path, { motion: binding.motion, unsupported,
          inverse: node.matrixWorld.determinant() === 0 ? null : node.matrixWorld.clone().invert() })
      }
      for (const child of node.children) visit(child, path)
    }
    for (const root of scene.children) for (const child of root.children) visit(child, '')
    const matrix = new Float64Array(16), transform = new THREE.Matrix4(), point = new THREE.Vector3()
    const pairCache = new Map()
    let disposed = false
    const matrixCache = new Map(), solvePose = createMechanismPose()

    function pairFor(raw, motion) {
      const key = JSON.stringify([motion, raw])
      if (pairCache.has(key)) return pairCache.get(key)
      let pair = null
      try {
        const first = structuredClone(raw)
        const initialPose = solveSourceInput(compileInput(first, 'Executed point-motion baseline'), [], solvePose)
        // Hold the actual auto-calibrated physical counter identical in A/B.
        if (first.setup.counterHeightM === null) first.setup.counterHeightM = initialPose.counter.gooseneckHeightM
        const second = structuredClone(first)
        second.crankTurns += 0.125
        const inputs = [compileInput(first, 'Executed point-motion baseline'), compileInput(second, 'Executed point-motion changed driver')]
        const angles = [], equilibriumResidualNm = []
        for (const input of inputs) {
          const pose = solveSourceInput(input, [], solvePose)
          angles.push(motion === 'crank' ? pose.crankAngleRad : pose.magnifier.wheelAngleRad)
          equilibriumResidualNm.push(pose.equilibriumResidualNm)
        }
        const angleDelta = angles[1] - angles[0]
        if (Number.isFinite(angleDelta) && angleDelta !== 0 && Math.abs(angleDelta) < Math.PI) {
          pair = { serialized: [first, second], inputs, driver: 'crankTurns', angles, equilibriumResidualNm }
        }
      } catch { /* Invalid or unclosed capability inputs are unknown, not fixed. */ }
      pairCache.set(key, pair)
      return pair
    }

    function matricesFor(pair) {
      const key = JSON.stringify(pair.serialized)
      if (matrixCache.has(key)) return matrixCache.get(key)
      // A→A measures repeat precision; A→B→A also measures solver/scene return
      // noise. Collect these small body matrices once per complete input family.
      const matrices = [pair.inputs[0], pair.inputs[0], pair.inputs[1], pair.inputs[0]].map(input => {
        const sample = new Map()
        machine.update(input, baseline => {
          for (const [path, part] of parts) {
            if (!part.unsupported && baseline.readWorldMatrix(path, matrix) && matrix.every(Number.isFinite)) {
              sample.set(path, matrix.slice())
            }
          }
          return EMPTY_OVERRIDES
        })
        return sample
      })
      matrixCache.set(key, matrices)
      return matrices
    }

    function classify(request) {
      if (disposed) throw new Error('Executed point-motion classifier is disposed')
      const inputPairs = [], groups = new Map()
      const results = (request.cases ?? []).map(({ anchor }) => ({ id: anchor?.id, motion: null, reason: 'unsupported native point association' }))
      const identityMatches = request.model?.sha256 === approved.source.sha256
        && request.model?.sourceCommit === approved.source.sourceCommit
        && request.model?.units === 'metres' && request.model?.axes === 'X-width/Y-height/Z-depth'
        && request.nativeIdentity?.mapSha256 === approved.identity.mapSha256
        && request.nativeIdentity?.canonicalSha256 === approved.identity.canonicalSha256
        && request.nativeIdentity?.inventorySha256 === manifest.currentSourceInventory?.sha256
      if (!identityMatches) return { results: results.map(row => ({ ...row, reason: 'native identity differs from approved actual model' })), inputPairs }
      for (const [index, { anchor, input }] of (request.cases ?? []).entries()) {
        const part = parts.get(anchor?.partPath)
        if (!part || part.unsupported || anchor.runtimeTemplatePartPath !== undefined
          || !anchor.correspondenceEvidence || !['physical-feature', 'section-center'].includes(anchor.kind)
          || (Object.hasOwn(anchor, 'partLocalMetres') === Object.hasOwn(anchor, 'worldMetres'))
          || !finitePoint(anchor.partLocalMetres ?? anchor.worldMetres)) continue
        if (anchor.worldMetres && !part.inverse) continue
        point.fromArray(anchor.partLocalMetres ?? anchor.worldMetres)
        if (anchor.worldMetres) point.applyMatrix4(part.inverse)
        const local = point.toArray()
        const pair = pairFor(input, part.motion)
        if (!pair) { results[index].reason = 'no feasible non-full-turn relevant driver pair'; continue }
        let group = groups.get(pair)
        if (!group) {
          group = { pair, points: [], index: inputPairs.length }
          groups.set(pair, group)
          inputPairs.push({ input: pair.serialized, driver: pair.driver, angles: pair.angles, equilibriumResidualNm: pair.equilibriumResidualNm })
        }
        group.points.push({ index, path: anchor.partPath, local, world: [] })
      }
      for (const group of groups.values()) {
        const matrices = matricesFor(group.pair)
        for (const entry of group.points) for (const sample of matrices) {
          const worldMatrix = sample.get(entry.path)
          if (!worldMatrix) { entry.world.push(null); continue }
          point.fromArray(entry.local).applyMatrix4(transform.fromArray(worldMatrix))
          entry.world.push(Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z) ? point.toArray() : null)
        }
        for (const entry of group.points) {
          const [first, repeated, second, returned] = entry.world
          if (!first || !repeated || !second || !returned) { results[entry.index].reason = 'actual normal-solved matrix unavailable or nonfinite'; continue }
          const distance = other => Math.hypot(other[0] - first[0], other[1] - first[1], other[2] - first[2])
          const displacementMetres = distance(second), sameInputNoiseMetres = distance(repeated), returnInputNoiseMetres = distance(returned)
          // Each native endpoint coordinate carries at most half a decoded
          // Float32 ulp of datum roundoff: two endpoints give sqrt(3) ulps in
          // Euclidean XYZ. Add the measured identical/return-input scene noise.
          // This prevents nominal centres' decoded-datum offsets counting as motion.
          const scale = Math.max(1, Math.abs(first[0]), Math.abs(first[1]), Math.abs(first[2]),
            Math.abs(second[0]), Math.abs(second[1]), Math.abs(second[2]))
          const roundoffMetres = Math.sqrt(3) * 2 ** -23 * scale + Math.max(sameInputNoiseMetres, returnInputNoiseMetres)
          const moving = Number.isFinite(displacementMetres) && displacementMetres > roundoffMetres
          results[entry.index] = { id: results[entry.index].id, motion: moving ? 'moving' : null,
            reason: moving ? null : 'zero or roundoff-ambiguous point displacement',
            pointPair: [first, second], sameInputPoint: repeated, returnedInputPoint: returned,
            displacementMetres, sameInputNoiseMetres, returnInputNoiseMetres, roundoffMetres, inputPairIndex: group.index }
        }
      }
      return { results, inputPairs, provenance: machine.provenance }
    }
    return { classify, machine,
      async dispose() { if (disposed) return; disposed = true; machine.dispose(); await server.close() } }
  } catch (error) {
    machine?.dispose()
    await server.close()
    throw error
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let classifier
  const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })
  try {
    for await (const line of lines) {
      try {
        classifier ??= await createPointMotionClassifier()
        process.stdout.write(`${JSON.stringify(classifier.classify(JSON.parse(line)))}\n`)
      } catch (error) { process.stdout.write(`${JSON.stringify({ error: error.message })}\n`) }
    }
  } finally { await classifier?.dispose() }
}
