import { readFile } from 'node:fs/promises'
import { webcrypto } from 'node:crypto'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline'
import * as THREE from 'three'
import { createServer, createLogger } from 'vite'
import { completeInput } from './verify-reference.mjs'

const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const finitePoint = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite)
const supportedMotion = motion => motion === 'crank' || motion === 'wheel'
const EMPTY_OVERRIDES = Object.freeze([])

/** The real source compiler/solver owns feasibility; reject raw invalid values
 * BEFORE JSON cache keys can turn NaN/Infinity into the valid automatic null.
 */
export function createPointMotionPairCompiler({ compileInput, solveSourceInput, createMechanismPose }) {
  const cache = new Map(), solvePose = createMechanismPose()
  return function pairFor(raw, motion) {
    if (!supportedMotion(motion) || !completeInput(raw)) return null
    const key = JSON.stringify([motion, raw])
    if (cache.has(key)) return cache.get(key)
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
    cache.set(key, pair)
    return pair
  }
}

/** Only a compiled four-body photograph exposes an independent body-local
 * rotation. The production geometry mapping, not anchor names, selects the DOF.
 * A/B keep the complete operating input and every other source pose identical.
 */
export function createSourcePointMotionPairCompiler({ compileInput, solveSourceInput, createMechanismPose,
  compileSourceAssemblyState, SOURCE_GEAR_PART_PATHS, NATIVE_RUNTIME_INSTANCES }) {
  const cache = new Map(), pose = createMechanismPose()
  const rotation = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), 0.125)
  const quaternion = new THREE.Quaternion()
  return function pairFor(raw, sourceAssembly, anchor) {
    if (!completeInput(raw) || !anchor?.correspondenceEvidence
      || !['physical-feature', 'section-center'].includes(anchor.kind)
      || !finitePoint(anchor.partLocalMetres) || Object.hasOwn(anchor, 'worldMetres')) return null
    try {
      // Compilation MUST precede serialization/cache lookup: NaN is not null.
      const first = compileSourceAssemblyState(sourceAssembly)
      if (first.state.kind !== 'source-assembly' || first.state.photograph?.pair !== 'four-gears') return null
      const gearId = Object.keys(SOURCE_GEAR_PART_PATHS).find(id => SOURCE_GEAR_PART_PATHS[id] === anchor.partPath)
      if (!gearId || !first.requiredPartPaths.includes(anchor.partPath)) return null
      const declaration = Object.values(NATIVE_RUNTIME_INSTANCES).find(value => value.partPath === anchor.partPath)
      if (declaration ? anchor.runtimeTemplatePartPath !== declaration.templatePartPath
        : anchor.runtimeTemplatePartPath !== undefined) return null
      const key = JSON.stringify([raw, first.state, gearId])
      if (cache.has(key)) return cache.get(key)
      const input = compileInput(raw, 'Executed source point-motion unchanged input')
      const solved = solveSourceInput(input, [], pose)
      const changed = structuredClone(sourceAssembly)
      const target = changed.photograph.fourGearPoses[gearId]
      target.quaternion = quaternion.fromArray(first.state.photograph.fourGearPoses[gearId].quaternion).multiply(rotation).toArray()
      const second = compileSourceAssemblyState(changed)
      const unchanged = structuredClone(second.state)
      unchanged.photograph.fourGearPoses[gearId].quaternion = [...first.state.photograph.fourGearPoses[gearId].quaternion]
      if (JSON.stringify(unchanged) !== JSON.stringify(first.state)) return null
      const pair = { serialized: [structuredClone(raw), structuredClone(raw)], inputs: [input, input],
        sourceAssembly: [first.state, second.state], assemblies: [first, second],
        driver: `photograph.fourGearPoses.${gearId}.quaternion.localZ`, angles: [0, 0.125],
        equilibriumResidualNm: [solved.equilibriumResidualNm, solved.equilibriumResidualNm] }
      cache.set(key, pair)
      return pair
    } catch { return null }
  }
}

const distance3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])

/** This is geometric displacement only; the caller supplies actual leased
 * A→A→B→A points after its identity, rigid-binding and association checks.
 */
export function classifyPointMotion(world) {
  if (!Array.isArray(world) || world.length !== 4 || !world.every(finitePoint)) {
    return { motion: null, reason: 'actual completed-update point unavailable or nonfinite' }
  }
  const [first, repeated, second, returned] = world
  const displacementMetres = distance3(second, first)
  const sameInputNoiseMetres = distance3(repeated, first), returnInputNoiseMetres = distance3(returned, first)
  // Two endpoint coordinates give sqrt(3) decoded Float32 ulps in XYZ.
  // Add measured repeat/return noise, never count a centre's datum offset.
  const scale = Math.max(1, Math.abs(first[0]), Math.abs(first[1]), Math.abs(first[2]),
    Math.abs(second[0]), Math.abs(second[1]), Math.abs(second[2]))
  const roundoffMetres = Math.sqrt(3) * 2 ** -23 * scale + Math.max(sameInputNoiseMetres, returnInputNoiseMetres)
  const moving = Number.isFinite(displacementMetres) && displacementMetres > roundoffMetres
  return { motion: moving ? 'moving' : null, reason: moving ? null : 'zero or roundoff-ambiguous point displacement',
    pointPair: [first, second], sameInputPoint: repeated, returnedInputPoint: returned,
    displacementMetres, sameInputNoiseMetres, returnInputNoiseMetres, roundoffMetres }
}

/** CPU-only native/source-provider point capability, not historical movement,
 * source-image acceptance, visibility or raster proof. The approved real GLB
 * and production providers are executed; private B is never a published pose.
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
    const assembly = await server.ssrLoadModule('/src/source-assembly.ts')
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
    let disposed = false
    const matrixCache = new Map()
    const pairFor = createPointMotionPairCompiler({ compileInput, solveSourceInput, createMechanismPose })
    const sourcePairFor = createSourcePointMotionPairCompiler({ compileInput, solveSourceInput, createMechanismPose, ...assembly })
    const sourceBuffer = assembly.createSourceAssemblyBuffer()
    const worldPoint = new Float64Array(3)
    const sourcePointCache = new Map()

    function matricesFor(pair) {
      const key = JSON.stringify([pair.serialized, assembly.OPERATING_SOURCE_ASSEMBLY.state])
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
      const identityMatches = machine.availability === 'available'
        && request.model?.sha256 === approved.source.sha256
        && request.model?.sourceCommit === approved.source.sourceCommit
        && request.model?.units === 'metres' && request.model?.axes === 'X-width/Y-height/Z-depth'
        && request.nativeIdentity?.mapSha256 === approved.identity.mapSha256
        && request.nativeIdentity?.canonicalSha256 === approved.identity.canonicalSha256
        && request.nativeIdentity?.inventorySha256 === manifest.currentSourceInventory?.sha256
      if (!identityMatches) return { results: results.map(row => ({ ...row, reason: 'native identity differs from approved available actual model' })), inputPairs }
      for (const [index, { anchor, input, sourceAssembly }] of (request.cases ?? []).entries()) {
        let compiled
        try { compiled = assembly.compileSourceAssemblyState(sourceAssembly) }
        catch { results[index].reason = 'invalid source assembly'; continue }
        const source = compiled.state.kind !== 'operating'
        const part = parts.get(anchor?.partPath)
        let pair, local
        if (source) {
          pair = sourcePairFor(input, sourceAssembly, anchor)
          if (!pair) { results[index].reason = 'no supported feasible body-local source driver'; continue }
          local = anchor.partLocalMetres
        } else {
          if (!part || part.unsupported || anchor.runtimeTemplatePartPath !== undefined
            || !anchor.correspondenceEvidence || !['physical-feature', 'section-center'].includes(anchor.kind)
            || (Object.hasOwn(anchor, 'partLocalMetres') === Object.hasOwn(anchor, 'worldMetres'))
            || !finitePoint(anchor.partLocalMetres ?? anchor.worldMetres)) continue
          if (anchor.worldMetres && !part.inverse) continue
          point.fromArray(anchor.partLocalMetres ?? anchor.worldMetres)
          if (anchor.worldMetres) point.applyMatrix4(part.inverse)
          local = point.toArray()
          pair = pairFor(input, part.motion)
          if (!pair) { results[index].reason = 'no feasible non-full-turn relevant driver pair'; continue }
        }
        let group = groups.get(pair)
        if (!group) {
          group = { pair, source, points: [], index: inputPairs.length }
          groups.set(pair, group)
          inputPairs.push({ input: pair.serialized, ...(source ? { sourceAssembly: pair.sourceAssembly } : {}),
            driver: pair.driver, angles: pair.angles, equilibriumResidualNm: pair.equilibriumResidualNm })
        }
        group.points.push({ index, path: anchor.partPath, anchor, local, world: [] })
      }
      for (const group of groups.values()) {
        if (group.source) {
          const key = JSON.stringify([group.pair.serialized, group.pair.sourceAssembly,
            group.points.map(entry => entry.anchor)])
          const cached = sourcePointCache.get(key)
          if (cached) for (let i = 0; i < group.points.length; i++) group.points[i].world = cached[i]
          else {
            // Same validated actual copy and its Float32 marker vertex across
            // A→A→B→A. NORMAL baseline is used only inside the real provider.
            const probe = machine.createLandmarkProbe(group.points.map((entry, i) => ({ ...entry.anchor, id: `motion-${i}` })))
            try {
              for (const state of [0, 0, 1, 0]) {
                machine.update(group.pair.inputs[state], baseline => assembly.solveSourceAssembly(group.pair.assemblies[state], baseline, sourceBuffer))
                for (let i = 0; i < group.points.length; i++) {
                  group.points[i].world.push(probe.readWorldPoint(`motion-${i}`, worldPoint) ? Array.from(worldPoint) : null)
                }
              }
              sourcePointCache.set(key, group.points.map(entry => entry.world))
            } catch (error) {
              for (const entry of group.points) {
                entry.world = []
                results[entry.index].reason = `source provider refused physical witness: ${error.message}`
              }
            } finally { probe.dispose() }
          }
        } else {
          const matrices = matricesFor(group.pair)
          for (const entry of group.points) for (const sample of matrices) {
            const worldMatrix = sample.get(entry.path)
            if (!worldMatrix) { entry.world.push(null); continue }
            point.fromArray(entry.local).applyMatrix4(transform.fromArray(worldMatrix))
            entry.world.push(Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z) ? point.toArray() : null)
          }
        }
        for (const entry of group.points) if (entry.world.length) {
          results[entry.index] = { id: results[entry.index].id, ...classifyPointMotion(entry.world), inputPairIndex: group.index }
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
