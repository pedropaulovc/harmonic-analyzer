import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { resolve, join } from 'node:path'
import { tmpdir } from 'node:os'

export const VIDEO_IDS = Object.freeze(['NAsM30MAHLg', '8KmVDxkia_w', '6dW6VYXp9HM', 'jfH-NbsmvD4', 'XPQwKRt4Y2k', '4mBuyixt22U'])
export const MODEL_SHA256 = '2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d'
export const MODEL_COMMIT = '1268c23d4a8fc741147c5e09d8d1e45247a71945'
export const PIXEL_LIMIT = 1920 * 0.02
export const CLOCK_LIMIT = 0.5
const EPSILON = 1e-6
const finite = value => typeof value === 'number' && Number.isFinite(value)
const vector = (value, size) => Array.isArray(value) && value.length === size && value.every(finite)
const text = value => typeof value === 'string' && value.trim().length > 0
const hash = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)

const ROD_HEAD_AUTHORITY = 'the one plate-like head vs u crosspiece is a discrepancy but both serve the same purpose; the 3d model will be fixed later to match device; animate assuming they will match later'
export function nativeGeometryAssumptionErrors(assumptions) {
  if (assumptions === undefined) return []
  if (!Array.isArray(assumptions) || assumptions.length !== 1) return ['Only the explicitly approved single rod-head functional-equivalence record may be declared']
  const value = assumptions[0]
  if (!exactKeys(value, ['id', 'status', 'scope', 'nativePartPaths', 'authority', 'sourceCounterpart', 'interpretation'])
    || value.id !== 'rod-head-functional-equivalence' || value.status !== 'user-approved-pending-cad-match' || value.scope !== 'rod-head-topology-only'
    || value.authority !== ROD_HEAD_AUTHORITY || value.sourceCounterpart !== 'Filmed U-shaped connecting-rod junction/crosspiece'
    || value.interpretation !== 'Functional linkage mapping for animation only; not a current geometric-fidelity pass.'
    || !Array.isArray(value.nativePartPaths) || !value.nativePartPaths.length || new Set(value.nativePartPaths).size !== value.nativePartPaths.length
    || value.nativePartPaths.some(path => typeof path !== 'string' || !/^harmonic-analyzer\/channel\/connecting-rod-([1-9]|1[0-9]|20)$/.test(path))) return ['Unapproved native geometry assumption, path, topology scope, authority or fidelity claim']
  return []
}

export function nonIdentifiableFixedPartErrors(parts) {
  if (!Array.isArray(parts)) return ['Explicit sourceNonIdentifiableFixedParts array is required']
  const errors = [], paths = new Set()
  for (const part of parts) {
    if (!exactKeys(part, ['nativePartPath', 'status', 'scope', 'rectSourcePixels', 'evidence', 'fixedNativeEvidence', 'authority', 'interpretation'])
      || !text(part.nativePartPath) || !part.nativePartPath.startsWith('harmonic-analyzer/') || /[?*]/.test(part.nativePartPath)
      || part.status !== 'user-approved-source-non-identifiable' || part.scope !== 'structural-fixed-part-only'
      || part.authority !== 'Allow explicitly unidentified fixed parts'
      || part.interpretation !== 'Rendered source-non-identifiable fixed part; not geometric-fidelity passed.'
      || !text(part.evidence) || !text(part.fixedNativeEvidence)
      || !vector(part.rectSourcePixels, 4) || part.rectSourcePixels[0] < 0 || part.rectSourcePixels[1] < 0 || part.rectSourcePixels[2] <= 0 || part.rectSourcePixels[3] <= 0 || part.rectSourcePixels[0] + part.rectSourcePixels[2] > 1920 || part.rectSourcePixels[1] + part.rectSourcePixels[3] > 1080) errors.push(`Invalid closed user-approved source-non-identifiable fixed record ${part?.nativePartPath}`)
    if (paths.has(part?.nativePartPath)) errors.push(`Duplicate source-non-identifiable fixed path ${part?.nativePartPath}`)
    paths.add(part?.nativePartPath)
  }
  return errors
}

/** The closed union is intentionally strict: irreversible gray pixels are never BGR. */
export function sourceImageError(image, source, native = null) {
  const key = image?.pixelFormat === 'bgr8' ? 'sha256Bgr8' : image?.pixelFormat === 'gray8' ? 'sha256Gray8' : null
  const fields = ['frameIndex', 'pixelFormat', 'width', 'height', 'sourceSha256', key]
  if (!key || !image || Object.keys(image).some(field => !fields.includes(field)) || fields.some(field => !Object.hasOwn(image, field))
    || !Number.isInteger(image.frameIndex) || image.frameIndex < 0 || !hash(image[key])
    || image.width !== 1920 || image.height !== 1080 || !hash(image.sourceSha256)
    || (source && image.sourceSha256 !== source.sha256)
    || (native && image.frameIndex >= native.pts.length)) return 'Expected the exclusive native bgr8/sha256Bgr8 or gray8/sha256Gray8 union, original source SHA256, 1920×1080 and an existing native frame index'
  return null
}
export function sourceImageKey(image) {
  return `${image?.frameIndex}/${image?.pixelFormat}/${image?.sha256Bgr8 ?? image?.sha256Gray8}`
}
/** Visit every claimed exposure, including proofs, registration parents and shared-rig maps. */
export function claimedSourceImages(data) {
  const images = []
  function visit(value, path) {
    if (!value || typeof value !== 'object') return
    if (!Array.isArray(value) && (Object.hasOwn(value, 'pixelFormat') || Object.hasOwn(value, 'sha256Bgr8') || Object.hasOwn(value, 'sha256Gray8'))) {
      images.push({ image: value, path })
      return
    }
    for (const [key, child] of Object.entries(value)) {
      if (key === 'sourceImage' || key === 'referenceSourceImage') images.push({ image: child, path: `${path}.${key}` })
      else visit(child, `${path}.${key}`)
    }
  }
  visit(data, 'reference')
  return images
}
const evidenceText = value => text(value) || (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0)
const inRect = (pixel, rect) => vector(pixel, 2) && vector(rect, 4) && pixel[0] >= rect[0] && pixel[1] >= rect[1] && pixel[0] < rect[0] + rect[2] && pixel[1] < rect[1] + rect[3]
const distance = (a, b) => Math.hypot(...a.map((value, index) => value - b[index]))
export const INPUT_FIELDS = Object.freeze(['crankTurns', 'gearing', 'magnification', ...Array.from({ length: 20 }, (_, i) => `amplitudes[${i}]`), ...Array.from({ length: 20 }, (_, i) => `phases[${i}]`), ...['counterHeightM', 'meanLineAngleRad', 'platenOffsetM', 'wireFixtureOffsetM', 'coneSwingRad', 'pinionCamRad', 'heldChannelTurns', 'driveCrankOffsetTurns'].map(key => `setup.${key}`)])
function exactKeys(value, keys) { return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key)) }
export function completeInput(input) {
  const setupKeys = INPUT_FIELDS.filter(field => field.startsWith('setup.')).map(field => field.slice(6))
  return exactKeys(input, ['crankTurns', 'amplitudes', 'phases', 'gearing', 'magnification', 'setup'])
    && finite(input.crankTurns) && vector(input.amplitudes, 20) && input.amplitudes.every(value => value >= -1 && value <= 1)
    && vector(input.phases, 20) && ['small-large', 'medium-medium', 'large-small'].includes(input.gearing) && finite(input.magnification) && input.magnification > 0
    && exactKeys(input.setup, setupKeys) && setupKeys.every(key => key === 'counterHeightM' ? input.setup[key] === null || finite(input.setup[key]) : finite(input.setup[key]))
}
/** Static accounting only. Acceptance evaluates these against the actual rendered native pose. */
export function witnessErrors(witness, expected, anchors, landmarks, view = {}) {
  const errors = []
  const reject = detail => errors.push(detail)
  if (!exactKeys(witness, ['input', 'unobservedInputFields', 'constraints', 'visibilityProof', ...(Object.hasOwn(witness ?? {}, 'continuity') ? ['continuity'] : [])]) || !completeInput(witness?.input)) return ['Witness needs an explicit complete physical input and the closed runtimeWitness fields']
  if (!Array.isArray(witness.unobservedInputFields) || !Array.isArray(witness.constraints)) return ['Witness requires typed constraints and explicit unobserved field accounting']
  const accounted = new Set(), constraints = new Set()
  for (const field of witness.unobservedInputFields) {
    if (!INPUT_FIELDS.includes(field) || accounted.has(field)) reject(`Unknown/duplicate unobserved field ${field}`)
    accounted.add(field)
  }
  for (const constraint of witness.constraints) {
    const { kind, field } = constraint ?? {}
    const id = ['input-value', 'input-interval'].includes(kind) ? `input:${field}` : kind === 'channel-angle' ? `${kind}:${constraint.channelIndex}` : kind
    if (!text(constraint?.evidence) || constraints.has(id)) reject(`Missing evidence or duplicate constraint ${id}`)
    constraints.add(id)
    const bounds = (minimum, maximum) => finite(minimum) && finite(maximum) && minimum <= maximum
    if (kind === 'input-value' || kind === 'input-interval') {
      if (!INPUT_FIELDS.includes(field)) reject(`Unknown constrained field ${field}`)
      if (kind === 'input-value') {
        if (!exactKeys(constraint, ['kind', 'field', 'value', 'tolerance', 'evidence']) || !finite(constraint.tolerance) || constraint.tolerance < 0
          || (field === 'gearing' ? !['small-large', 'medium-medium', 'large-small'].includes(constraint.value) || constraint.tolerance !== 0 : constraint.value === null ? field !== 'setup.counterHeightM' || witness.input.setup.counterHeightM !== null || constraint.tolerance !== 0 || !witness.unobservedInputFields.includes(field) : !finite(constraint.value))) reject(`Invalid input-value ${field}`)
      } else if (!exactKeys(constraint, ['kind', 'field', 'minimum', 'maximum', 'evidence']) || field === 'gearing' || !bounds(constraint.minimum, constraint.maximum)) reject(`Invalid input interval ${field}`)
      if (field === 'setup.counterHeightM' && witness.input.setup.counterHeightM === null && !(kind === 'input-value' && constraint.value === null)) reject('Null auto-level counter cannot carry a numeric measured counter constraint')
      if (!(kind === 'input-value' && constraint.value === null)) {
        if (accounted.has(field)) reject(`Measured/unobserved or duplicate accounting ${field}`)
        accounted.add(field)
      }
    } else if (kind === 'effective-bank-drive') {
      if (!exactKeys(constraint, ['kind', 'minimumTurns', 'maximumTurns', 'winding', 'evidence']) || !bounds(constraint.minimumTurns, constraint.maximumTurns) || !['unwrapped', 'modulo-one'].includes(constraint.winding)) reject('Invalid effective-bank-drive')
    } else if (kind === 'channel-angle') {
      if (!exactKeys(constraint, ['kind', 'channelIndex', 'minimumRadians', 'maximumRadians', 'winding', 'evidence']) || !Number.isInteger(constraint.channelIndex) || constraint.channelIndex < 0 || constraint.channelIndex >= 20 || !bounds(constraint.minimumRadians, constraint.maximumRadians) || !['unwrapped', 'modulo-turn'].includes(constraint.winding)) reject('Invalid channel-angle')
    } else if (kind === 'paper-travel' || kind === 'pen-travel') {
      if (!exactKeys(constraint, ['kind', 'minimumMetres', 'maximumMetres', 'evidence']) || !bounds(constraint.minimumMetres, constraint.maximumMetres)) reject(`Invalid ${kind}`)
    } else reject(`Unknown source constraint ${kind}`)
  }
  for (const field of INPUT_FIELDS) if (!accounted.has(field)) reject(`Unaccounted input field ${field}`)
  if (witness.input.setup.counterHeightM === null && !witness.unobservedInputFields.includes('setup.counterHeightM')) reject('Auto-level null counter must remain explicitly unobserved')
  if (witness.continuity && (!exactKeys(witness.continuity, ['intervalId', 'evidence']) || !text(witness.continuity.intervalId) || !text(witness.continuity.evidence))) reject('Continuity requires a source-evidenced interval')
  return [...errors, ...visibilityProofErrors(witness.visibilityProof, expected, anchors, landmarks, view)]
}
export function visibilityProofErrors(proof, expected, anchors, landmarks, view = {}) {
  const errors = []
  const reject = detail => errors.push(detail)
  const binding = proof?.binding
  if (!exactKeys(proof, ['binding', 'sourceVisibleParts', 'excludedParts', 'sourceNonIdentifiableFixedParts', 'unresolvedParts', 'evidence']) || !text(proof.evidence)
    || !exactKeys(binding, [...Object.keys(expected), 'intervalSeconds'])) return [...errors, 'Missing complete, explicitly bound visibility proof']
  for (const key of Object.keys(expected)) if (canonicalJson(binding[key]) !== canonicalJson(expected[key])) reject(`Visibility proof binding mismatch: ${key}`)
  if (!vector(binding.intervalSeconds, 2) || binding.intervalSeconds[0] > expected.timeSeconds || binding.intervalSeconds[1] < expected.timeSeconds || binding.intervalSeconds[0] > binding.intervalSeconds[1]) reject('Visibility proof interval does not cover this sample')
  if (!Array.isArray(proof.sourceVisibleParts) || !Array.isArray(proof.excludedParts) || !Array.isArray(proof.sourceNonIdentifiableFixedParts) || !Array.isArray(proof.unresolvedParts)) return [...errors, 'Missing full native part census arrays, including explicit sourceNonIdentifiableFixedParts']
  if (proof.unresolvedParts.length) reject(`Unresolved native parts: ${proof.unresolvedParts.length}`)
  errors.push(...nonIdentifiableFixedPartErrors(proof.sourceNonIdentifiableFixedParts))
  const paths = new Set()
  for (const part of [...proof.sourceVisibleParts, ...proof.excludedParts]) {
    if (!text(part?.partPath) || !part.partPath.startsWith('harmonic-analyzer/') || paths.has(part.partPath) || !text(part.evidence)) reject(`Invalid/duplicate native census path ${part?.partPath}`)
    paths.add(part?.partPath)
  }
  for (const part of proof.sourceNonIdentifiableFixedParts) {
    const path = part?.nativePartPath
    if (paths.has(path)) reject(`Overlapping source-non-identifiable/native census path ${path}`)
    paths.add(path)
  }
  if (!paths.size) reject('Empty native part census')
  for (const part of proof.sourceVisibleParts) {
    const coverage = part.sourceCoverage
    if (!exactKeys(part, ['partPath', 'sourceFeatures', 'sourceCoverage', 'evidence']) || !Array.isArray(part.sourceFeatures) || !part.sourceFeatures.length || !part.sourceFeatures.every(text) || !coverage) { reject(`Missing actual source coverage for ${part.partPath}`); continue }
    if (coverage.kind === 'rigid-native-attachment') {
      if (!exactKeys(coverage, ['kind', 'attachedToPartPath']) || !text(coverage.attachedToPartPath) || !part.partPath.startsWith(`${coverage.attachedToPartPath}/`) || !proof.sourceVisibleParts.some(parent => parent.partPath === coverage.attachedToPartPath)) reject(`Unsupported native rigid attachment ${part.partPath}`)
      continue
    }
    const key = coverage.kind === 'landmarks' ? 'landmarkIds' : coverage.kind === 'native-line-checks' ? 'lineCheckIds' : coverage.kind === 'source-contour' ? 'contourCheckIds' : null
    if (!key || !exactKeys(coverage, ['kind', key]) || !Array.isArray(coverage[key]) || !coverage[key].length || new Set(coverage[key]).size !== coverage[key].length) { reject(`Invalid source coverage ${part.partPath}`); continue }
    for (const id of coverage[key]) {
      const matched = key === 'landmarkIds' ? anchors.some(anchor => anchor.id === id && anchor.partPath === part.partPath) && landmarks.some(item => item.anchorId === id && item.status === 'observed')
        : (key === 'lineCheckIds' ? view.nativeLineChecks : view.sourceContourChecks)?.some(check => check.id === id && check.partPath === part.partPath)
      if (!matched) reject(`Unknown/current-frame missing ${key}: ${id} for ${part.partPath}`)
    }
  }
  for (const part of proof.excludedParts) if (!exactKeys(part, ['partPath', 'reason', 'evidence']) || !['outside', 'occluded', 'absent'].includes(part.reason)) reject(`Invalid source exclusion ${part.partPath}`)
  return errors
}

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
  return JSON.stringify(value)
}
export function jsonDigest(value) { return createHash('sha256').update(canonicalJson(value)).digest('hex') }
export async function sha256File(path) {
  const digest = createHash('sha256')
  for await (const chunk of createReadStream(path)) digest.update(chunk)
  return digest.digest('hex')
}

/** No shell, finite deadline, and the child is killed on timeout or interruption. */
export function runTool(binary, args, { timeoutMs = 120_000, signal, maxBytes = 64 * 1024 * 1024 } = {}) {
  return new Promise((resolveResult, reject) => {
    const child = spawn(binary, args, { stdio: ['ignore', 'pipe', 'pipe'], signal })
    const stdout = [], stderr = []
    let bytes = 0, failure = null
    const timer = setTimeout(() => { failure = new Error(`${binary} exceeded ${timeoutMs / 1000}s`); child.kill('SIGKILL') }, timeoutMs)
    child.stdout.on('data', chunk => {
      bytes += chunk.length
      if (bytes > maxBytes) { failure = new Error(`${binary} output exceeded ${maxBytes} bytes`); child.kill('SIGKILL') }
      else stdout.push(chunk)
    })
    child.stderr.on('data', chunk => { if (stderr.reduce((n, item) => n + item.length, 0) < 64 * 1024) stderr.push(chunk) })
    child.once('error', error => { clearTimeout(timer); reject(error) })
    child.once('close', code => {
      clearTimeout(timer)
      const errorText = Buffer.concat(stderr).toString()
      if (failure || code !== 0) reject(failure ?? new Error(`${binary} exited ${code}: ${errorText.trim()}`))
      else resolveResult({ stdout: Buffer.concat(stdout), stderr: errorText })
    })
  })
}

/**
 * Single requirement rule shared with the runtime timeline: a frame must be
 * physically matched when it shows the machine, when its shot declares a
 * corresponding machine (whatever its classification: transition, photograph,
 * overlay…), or when a transition/unobservable shot does not explicitly exempt
 * it. Only non-machine shots without a declared machine, or shots explicitly
 * declaring hasCorrespondingMachine=false, are exempt.
 */
export function sourceNeedsMachine(frame, shot) {
  if (frame.classification === 'machine' || shot?.hasCorrespondingMachine === true) return true
  if (frame.classification === 'non-machine' || shot?.hasCorrespondingMachine === false) return false
  return true
}
/** Index of the source frame governing time t (last frame at or before t), or -1. */
export function frameIndexAt(frames, time) {
  let lo = 0, hi = frames.length
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (frames[mid].timeSeconds <= time) lo = mid + 1; else hi = mid }
  return lo - 1
}
/** Contiguous source intervals governed only by required (physically matched) frames. */
export function requiredRuns(data) {
  const shots = new Map((data.shots ?? []).map(shot => [shot.id, shot]))
  const runs = []
  let current = null
  for (const frame of data.frames ?? []) {
    const required = sourceNeedsMachine(frame, shots.get(frame.shotId))
    if (required && !current) current = { startSeconds: frame.timeSeconds, endSeconds: null, frames: 0 }
    if (!required && current) { current.endSeconds = frame.timeSeconds; runs.push(current); current = null }
    if (current) current.frames++
  }
  if (current) { current.endSeconds = data.source.durationSeconds; runs.push(current) }
  return runs
}
export function frameViews(frame) {
  return frame.views ?? [{ id: 'main', rectSourcePixels: [0, 0, 1920, 1080], presentation: 'native', camera: frame.camera, mechanicalState: frame.mechanicalState, cameraEvidence: frame.cameraEvidence, nativeLineChecks: frame.nativeLineChecks, sourceContourChecks: frame.sourceContourChecks, composite: frame.composite, compositeEvidence: frame.compositeEvidence, partOverrides: frame.partOverrides }]
}
export function nearestPtsIndex(pts, time) {
  let lo = 0, hi = pts.length
  while (lo < hi) { const mid = (lo + hi) >>> 1; if (pts[mid] < time) lo = mid + 1; else hi = mid }
  if (lo === 0) return 0
  if (lo === pts.length) return lo - 1
  return time - pts[lo - 1] <= pts[lo] - time ? lo - 1 : lo
}

function measuredImageErrors(item, image) {
  const evidence = item.measurementEvidence ?? item.trackingEvidence, errors = []
  if (!evidenceText(evidence)) errors.push('Missing actual source measurement evidence')
  if (evidence && typeof evidence === 'object') {
    if (evidence.sourceImage && canonicalJson(evidence.sourceImage) !== canonicalJson(image)) errors.push('Stale measurement sourceImage')
    for (const [field, key] of [['sourceSha256Bgr8', 'sha256Bgr8'], ['sourceSha256Gray8', 'sha256Gray8']]) if (Object.hasOwn(evidence, field) && evidence[field] !== image?.[key]) errors.push(`Stale measurement ${field}`)
  }
  return errors
}
export function nativeLineErrors(lines, image, rect, overrides = []) {
  const errors = [], ids = new Set()
  for (const line of lines) {
    const evidence = line?.measurementEvidence, local = line?.partLocalLineMetres, source = line?.sourceLinePixels
    const reject = detail => errors.push(`${line?.id ?? 'unknown'}: ${detail}`)
    if (!text(line?.id) || ids.has(line.id) || !text(line.partPath) || !line.partPath.startsWith('harmonic-analyzer/') || !Array.isArray(local) || local.length !== 2 || !local.every(point => vector(point, 3)) || distance(local[0], local[1]) <= 1e-9
      || !Array.isArray(source) || source.length !== 2 || !source.every(point => inRect(point, rect)) || distance(source[0], source[1]) <= 1e-6 || !finite(line.uncertaintyPx) || line.uncertaintyPx < 0 || line.uncertaintyPx > PIXEL_LIMIT) { reject('Invalid/degenerate native geometry or actual source segment'); continue }
    ids.add(line.id)
    if (canonicalJson(evidence?.sourceImage) !== canonicalJson(image) || !text(evidence?.detector) || !text(evidence?.axisPerspectiveEvidence) || !finite(evidence?.axisPerspectiveBiasBoundPx) || evidence.axisPerspectiveBiasBoundPx < 0 || evidence.axisPerspectiveBiasBoundPx > line.uncertaintyPx) { reject('Need current exposure, actual edge detector and conservative independently justified axis perspective bias'); continue }
    const rows = evidence.edgeRows
    if (!Array.isArray(rows) || rows.length < 2 || new Set(rows.map(row => row?.y)).size < 2) { reject('Need distinct actually observed paired-edge rows'); continue }
    const delta = source[1].map((value, i) => value - source[0][i]), squared = delta.reduce((sum, value) => sum + value * value, 0)
    for (const row of rows) {
      if (!finite(row.y) || !finite(row.left) || !finite(row.right) || !finite(row.contrast) || row.contrast <= 0 || !inRect([row.left, row.y], rect) || !inRect([row.right, row.y], rect) || row.left >= row.right) { reject('Unobservable/outside ROI edge pair'); continue }
      const point = [(row.left + row.right) / 2, row.y], fraction = Math.max(0, Math.min(1, point.reduce((sum, value, i) => sum + (value - source[0][i]) * delta[i], 0) / squared))
      if (distance(point, source[0].map((value, i) => value + fraction * delta[i])) > line.uncertaintyPx) reject('Source line is unsupported by actual paired edges')
    }
    if (Math.min(...source.map(point => point[1])) < Math.min(...rows.map(row => row.y)) - line.uncertaintyPx || Math.max(...source.map(point => point[1])) > Math.max(...rows.map(row => row.y)) + line.uncertaintyPx) reject('Source line extends beyond observed edge support')
    if (overrides.some(override => override.visibility === 'hidden' && (line.partPath === override.partPath || line.partPath.startsWith(`${override.partPath}/`)))) reject('Source line belongs to hidden native geometry')
  }
  return errors
}
const matVec = (matrix, point) => matrix.map(row => row.reduce((sum, value, i) => sum + value * point[i], 0))
const transpose = matrix => matrix[0].map((_, i) => matrix.map(row => row[i]))
const matMul = (a, b) => a.map(row => transpose(b).map(column => row.reduce((sum, value, i) => sum + value * column[i], 0)))
function rotationVectorMatrix(vector) {
  const angle = Math.hypot(...vector)
  if (angle < 1e-15) return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  const [x, y, z] = vector.map(value => value / angle), c = Math.cos(angle), s = Math.sin(angle), t = 1 - c
  return [[t*x*x+c, t*x*y-s*z, t*x*z+s*y], [t*x*y+s*z, t*y*y+c, t*y*z-s*x], [t*x*z-s*y, t*y*z+s*x, t*z*z+c]]
}
function quaternionMatrix([x, y, z, w]) {
  return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
}
export function cameraParameters(camera, rect) {
  const rotation = matMul([[1, 0, 0], [0, -1, 0], [0, 0, -1]], transpose(quaternionMatrix(camera.quaternion)))
  return { rotation, translation: matVec(rotation, camera.positionMetres).map(value => -value), focal: rect[3] / (2 * Math.tan(camera.verticalFovDegrees * Math.PI / 360)), principal: camera.principalPointViewportPixels ?? [rect[2] / 2, rect[3] / 2] }
}
function rigParameters(rig, phase) {
  const angle = 2 * Math.PI * phase / 71
  const rotation = matMul(rotationVectorMatrix(rig.worldToReferenceCameraCV.rotationVectorRad), [[Math.cos(angle), 0, Math.sin(angle)], [0, 1, 0], [-Math.sin(angle), 0, Math.cos(angle)]])
  const axis = matVec(rotation, rig.axisPointWorldMetres)
  return { rotation, translation: rig.worldToReferenceCameraCV.translationMetres.map((value, i) => value - axis[i]), focal: rig.worldToReferenceCameraCV.focalPixels, principal: [960, 540] }
}
/** Derived camera identities are recomputed, never inferred from fit status/error summaries. */
export function cameraEvidenceErrors(data) {
  const errors = [], rigs = new Map((data.sourceCameraRigs ?? []).map(rig => [rig.id, rig])), contexts = new Map(), resolved = new Map(), active = new Set()
  for (const frame of data.frames ?? []) for (const view of frameViews(frame)) contexts.set(`${frame.timeSeconds}/${view.id}`, { frame, view })
  function resolveCamera(key) {
    if (resolved.has(key)) return resolved.get(key)
    if (active.has(key)) throw new Error('Camera registration dependency cycle')
    const context = contexts.get(key)
    if (!context?.view.camera) throw new Error(`Missing independently calibrated camera ${key}`)
    active.add(key)
    const { frame, view } = context, evidence = view.cameraEvidence ?? frame.cameraEvidence ?? { kind: 'direct-fit' }
    let expected, parentImage, parentRect
    if (evidence.kind === 'direct-fit') {
      if (!exactKeys(evidence, ['kind'])) throw new Error('Unknown direct camera evidence fields')
      const landmarks = frame.landmarks?.filter(item => (item.viewId ?? 'main') === view.id) ?? []
      if (landmarks.filter(item => item.role === 'fit').length < 6 || landmarks.filter(item => item.role === 'check').length < 2) throw new Error('Direct camera retains >=6 fit/>=2 held-out guard')
      expected = cameraParameters(view.camera, view.rectSourcePixels)
    } else {
      if (Object.keys(view.cameraFit ?? {}).length || Object.keys(frame.cameraFit ?? {}).length) throw new Error('Derived camera cannot specify a new camera fit')
      const reference = evidence.kind === 'shared-rigid-sequence' ? evidence : evidence.reference
      if (reference?.rigId !== undefined) {
        const rig = rigs.get(reference.rigId), image = rig?.phaseImages?.find(item => item.phaseIndex === reference.phaseIndex)?.sourceImage
        if (!rig || !image || !Number.isInteger(reference.phaseIndex) || reference.phaseIndex < 0 || reference.phaseIndex >= 71) throw new Error('Missing independently identifiable rig phase')
        expected = rigParameters(rig, reference.phaseIndex); parentImage = image; parentRect = [0, 0, 1920, 1080]
        if (evidence.kind === 'shared-rigid-sequence') {
          const registration = rig.independentLoopEvidence?.sourceFrameMap?.find(item => canonicalJson(item.sourceImage) === canonicalJson(frame.sourceImage))
          if (!exactKeys(evidence, ['kind', 'rigId', 'phaseIndex']) || canonicalJson(view.rectSourcePixels) !== canonicalJson(parentRect) || view.presentation !== 'native' || !registration?.phaseAccepted || registration.referencePhaseIndex !== reference.phaseIndex) throw new Error('Current actual source exposure does not establish claimed native whole-source rig phase')
        } else if (!exactKeys(reference, ['rigId', 'phaseIndex'])) throw new Error('Mixed camera reference kinds')
      } else if (evidence.kind === 'source-registered' && exactKeys(reference, ['timeSeconds', 'viewId'])) {
        const parentKey = `${reference.timeSeconds}/${reference.viewId ?? 'main'}`, parent = contexts.get(parentKey)
        if (!parent || parent.view.presentation !== 'native') throw new Error('Missing or mirrored registration parent')
        expected = resolveCamera(parentKey); parentImage = parent.frame.sourceImage; parentRect = parent.view.rectSourcePixels
      } else throw new Error('Unknown camera evidence kind/reference')
      if (evidence.kind === 'source-registered') {
        if (!exactKeys(evidence, ['kind', 'reference', 'sourceToViewportPixels', 'sourceImage', 'referenceSourceImage', 'correspondences']) || canonicalJson(evidence.sourceImage) !== canonicalJson(frame.sourceImage) || canonicalJson(evidence.referenceSourceImage) !== canonicalJson(parentImage)) throw new Error('Stale or mixed source registration identity')
        const affine = evidence.sourceToViewportPixels
        if (!vector(affine, 6) || affine[0] <= 0 || Math.abs(affine[1]) > 1e-9 || Math.abs(affine[3]) > 1e-9 || Math.abs(affine[4] - affine[0]) > 1e-9) throw new Error('Need positive uniform source crop affine, without shear/rotation')
        const ids = new Set(), sourcePixels = new Set(), targetPixels = new Set(), roles = { fit: 0, check: 0 }
        for (const item of evidence.correspondences ?? []) {
          const a = canonicalJson(item.sourcePixel), b = canonicalJson(item.viewportPixel)
          if (!text(item.id) || ids.has(item.id) || sourcePixels.has(a) || targetPixels.has(b) || !['fit', 'check'].includes(item.role) || !['manual', 'optical-flow', 'image-edge', 'template-match'].includes(item.method) || !finite(item.uncertaintyPx) || item.uncertaintyPx < 0 || item.uncertaintyPx > PIXEL_LIMIT || !inRect(item.sourcePixel, [0, 0, 1920, 1080]) || !inRect(item.viewportPixel, [0, 0, view.rectSourcePixels[2], view.rectSourcePixels[3]]) || measuredImageErrors(item, frame.sourceImage).length) throw new Error('Invalid/disjoint actual registration measurements')
          ids.add(item.id); sourcePixels.add(a); targetPixels.add(b); roles[item.role]++
          if (distance([affine[0] * item.sourcePixel[0] + affine[2], affine[0] * item.sourcePixel[1] + affine[5]], item.viewportPixel) > PIXEL_LIMIT) throw new Error(`Independent ${item.role} affine error exceeds ${PIXEL_LIMIT}px`)
        }
        if (roles.fit < 2 || roles.check < 2) throw new Error('Affine needs >=2 fitting and >=2 separately measured held-out correspondences')
        expected = { ...expected, focal: expected.focal * affine[0], principal: expected.principal.map((value, i) => affine[0] * (value + parentRect[i]) + affine[i === 0 ? 2 : 5]) }
      }
      const actual = cameraParameters(view.camera, view.rectSourcePixels)
      if (distance(actual.rotation.flat(), expected.rotation.flat()) > 1e-6 || distance(actual.translation, expected.translation) > 1e-6 || Math.abs(actual.focal - expected.focal) > 1e-4 || distance(actual.principal, expected.principal) > 1e-4) throw new Error('Resolved camera does not equal independent rig/crop pose/intrinsics')
    }
    active.delete(key); resolved.set(key, expected); return expected
  }
  for (const [key, { frame, view }] of contexts) if (view.camera && sourceNeedsMachine(frame, data.shots?.find(shot => shot.id === frame.shotId))) {
    try { resolveCamera(key) } catch (error) { active.clear(); errors.push({ code: 'camera-evidence', detail: error.message, timeSeconds: frame.timeSeconds, viewId: view.id }) }
  }
  return errors
}

/** Validates measured evidence, never the fitter's authored error summaries. */
export function inspectReference(data, expectedId, native = null) {
  const failures = []
  const fail = (code, detail, timeSeconds, viewId) => failures.push({ code, detail, ...(timeSeconds === undefined ? {} : { timeSeconds }), ...(viewId === undefined ? {} : { viewId }) })
  const source = data?.source, coverage = data?.coverage
  const summary = { videoId: expectedId, frameCount: 0, integerSecondsRequired: 0, integerSecondsPresent: 0, changeTimesRequired: 0, changeTimesPresent: 0, machineFrames: 0, exemptFrames: 0, requiredViews: 0, fitLandmarks: 0, checkLandmarks: 0, nativeLineChecks: 0, sourceContourChecks: 0, sourcePtsChecked: 0, maxDecodeSkewSeconds: 0, intervals: [], failures }
  if (data?.schemaVersion !== 1) fail('schema', 'schemaVersion must be 1')
  if (source?.videoId !== expectedId || !hash(source?.sha256) || source?.width !== 1920 || source?.height !== 1080 || !finite(source?.durationSeconds) || source.durationSeconds <= 0) {
    fail('source-identity', 'Expected this public video, its SHA256, 1920×1080 and a positive duration')
    return summary
  }
  if (data.model?.sha256 !== MODEL_SHA256 || data.model?.sourceCommit !== MODEL_COMMIT || data.model?.units !== 'metres' || data.model?.axes !== 'X-width/Y-height/Z-depth') fail('model-identity', 'Observations must target the authentic released metre CAD export')
  if (coverage?.status !== 'complete' || !Array.isArray(coverage?.blockers) || coverage.blockers.length) fail('blocked-coverage', JSON.stringify(coverage ?? null))
  if (coverage?.requiredEveryIntegerSecond !== true) fail('integer-census', 'All integer seconds must be required')
  const images = new Map()
  for (const { image, path } of claimedSourceImages(data)) {
    const error = sourceImageError(image, source, native)
    if (error) { fail('source-image-identity', `${path}: ${error}`); continue }
    const key = `${image.frameIndex}/${image.pixelFormat}`, value = image.sha256Bgr8 ?? image.sha256Gray8
    if (images.has(key) && images.get(key) !== value) fail('source-image-conflict', `Conflicting ${image.pixelFormat} hashes for actual native exposure ${image.frameIndex}`)
    images.set(key, value)
  }
  summary.claimedSourceImageCount = images.size
  summary.nativeGeometryAssumptions = data.nativeGeometryAssumptions ?? []
  for (const detail of nativeGeometryAssumptionErrors(data.nativeGeometryAssumptions)) fail('native-geometry-assumption', detail)
  summary.sourcePixelFormats = [...new Set([...images.keys()].map(key => key.split('/')[1]))].sort()
  const anchors = new Map()
  for (const anchor of data.anchors ?? []) {
    if (!text(anchor.id) || anchors.has(anchor.id) || !['physical-feature', 'section-center'].includes(anchor.kind) || !text(anchor.partPath) || !text(anchor.correspondenceEvidence) || !text(anchor.description)) fail('anchor-correspondence', `Invalid/duplicate anchor ${anchor.id}`)
    if (vector(anchor.partLocalMetres, 3) === vector(anchor.worldMetres, 3)) fail('anchor-point', `${anchor.id} needs exactly one finite local or world point`)
    // Fixed CAD-world points cannot serve as articulated moving-part observations.
    if (anchor.worldMetres && !anchor.partPath?.startsWith('harmonic-analyzer/frame/')) fail('unarticulated-anchor', `${anchor.id}: moving part points must use partLocalMetres`)
    anchors.set(anchor.id, anchor)
  }
  const shots = new Map(), duration = source.durationSeconds
  let end = 0
  for (const shot of data.shots ?? []) {
    if (!text(shot.id) || shots.has(shot.id) || !finite(shot.startSeconds) || !finite(shot.endSeconds) || shot.endSeconds <= shot.startSeconds || Math.abs(shot.startSeconds - end) > EPSILON || !text(shot.reason) || !['machine', 'non-machine', 'transition', 'unobservable'].includes(shot.classification)) fail('shot-census', `Invalid, overlapping, gapped or unordered shot ${shot.id}`)
    if (shot.classification === 'machine' && shot.hasCorrespondingMachine === false) fail('machine-exemption', `Physical-machine shot ${shot.id} cannot be exempted`)
    shots.set(shot.id, shot)
    summary.intervals.push({ id: shot.id, startSeconds: shot.startSeconds, endSeconds: shot.endSeconds, classification: shot.classification, hasCorrespondingMachine: shot.hasCorrespondingMachine, reason: shot.reason })
    end = shot.endSeconds
  }
  if (!shots.size || Math.abs(end - duration) > EPSILON) fail('shot-duration', 'Shot census must cover source start through its full duration')
  if (!Array.isArray(data.frames) || !data.frames.length) { fail('missing-frames', 'No actual decoded reference frames'); return summary }
  summary.frameCount = data.frames.length
  const times = [], nativeIndices = new Set()
  const allNative = coverage?.requiredEveryNativeFrame === true
  // A full native-frame census subsumes every change. Otherwise the explicit change
  // census is mandatory; chapter-only timestamps are not a motion/edit census.
  if (!allNative && (coverage?.requiredEveryChange !== true || !Array.isArray(coverage?.changeTimesSeconds) || !text(coverage?.changeCensusEvidence))) fail('change-census', 'Declare requiredEveryChange, measured changeTimesSeconds and changeCensusEvidence, or provide every native decoded frame')
  let previous = -Infinity
  const seeds = new Map()
  for (const frame of data.frames) {
    for (const item of frame.landmarks ?? []) if (item.method === 'manual') seeds.set(`${frame.timeSeconds}/${item.viewId ?? 'main'}/${item.anchorId}`, item)
  }
  for (const frame of data.frames) {
    const t = frame.timeSeconds
    if (!finite(t) || t <= previous || t < 0 || t > duration) fail('chronology', 'Frame times must be finite and strictly increasing within source duration', t)
    previous = t; times.push(t)
    const shot = shots.get(frame.shotId)
    if (!shot || t < shot.startSeconds - EPSILON || t >= shot.endSeconds + EPSILON || frame.classification !== shot.classification) { fail('shot-frame', 'Frame must belong to the declared actual-source shot/classification', t); continue }
    if (!finite(frame.decodedTimeSeconds)) fail('decoded-time', 'Missing finite decoded native timestamp', t)
    if (native && finite(frame.decodedTimeSeconds)) {
      const index = nearestPtsIndex(native.pts, frame.decodedTimeSeconds)
      const pt = native.pts[index]
      const mismatch = Math.abs(pt - frame.decodedTimeSeconds), skew = Math.abs(t - frame.decodedTimeSeconds)
      const localStep = Math.max(native.pts[Math.min(index + 1, native.pts.length - 1)] - pt, pt - native.pts[Math.max(index - 1, 0)], 1 / native.fps)
      if (mismatch > 0.001 || skew > localStep + 0.001) fail('source-pts', `Decoded time is not a native source exposure within one frame (${mismatch.toFixed(6)}s identity error)`, t)
      if (frame.decodedFrameIndex !== undefined && frame.decodedFrameIndex !== index) fail('source-frame-index', `Declared frame ${frame.decodedFrameIndex} differs from native ${index}`, t)
      nativeIndices.add(index); summary.sourcePtsChecked++; summary.maxDecodeSkewSeconds = Math.max(summary.maxDecodeSkewSeconds, skew)
      if (frame.sourceImage && frame.sourceImage.frameIndex !== index) fail('source-image-index', `Actual decoded image hash belongs to a different exposure than native ${index}`, t)
    }
    if (!sourceNeedsMachine(frame, shot)) {
      summary.exemptFrames++
      if ((frame.landmarks?.length ?? 0) > 0 || frame.views?.some(view => view.camera)) fail('non-machine-evidence', 'A no-corresponding-machine hold cannot conceal measured physical views', t)
      continue
    }
    summary.machineFrames++
    if (!Array.isArray(frame.landmarks) || !Array.isArray(frame.unavailable)) { fail('missing-landmarks', 'Missing actual-source landmark/unavailability arrays', t); continue }
    if (sourceImageError(frame.sourceImage, source, native)) fail('source-image-identity', 'Every required physical view needs an independently reproducible actual native BGR8 or gray8 exposure', t)
    const views = frameViews(frame), viewIds = new Set()
    if (!views.length) fail('missing-views', 'Corresponding physical machine has no source view', t)
    for (const view of views) {
      const viewId = view.id
      if (!text(viewId) || viewIds.has(viewId)) fail('view-id', 'View IDs must be nonempty and distinct', t, viewId)
      viewIds.add(viewId); summary.requiredViews++
      summary.nativeLineChecks += view.nativeLineChecks?.length ?? 0
      summary.sourceContourChecks += view.sourceContourChecks?.length ?? 0
      const rect = view.rectSourcePixels
      if (!vector(rect, 4) || rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0 || rect[0] + rect[2] > 1920 || rect[1] + rect[3] > 1080 || !['native', 'horizontal-mirror'].includes(view.presentation)) fail('source-viewport', 'Invalid actual source ROI or mirror presentation', t, viewId)
      const camera = view.camera
      if (!camera || camera.status !== 'passed' || !vector(camera.positionMetres, 3) || !vector(camera.quaternion, 4) || Math.abs(Math.hypot(...camera.quaternion) - 1) > 0.002 || !finite(camera.verticalFovDegrees) || camera.verticalFovDegrees <= 0 || camera.verticalFovDegrees >= 179) fail('camera-state', 'Missing/failed/incomplete observed camera', t, viewId)
      const state = view.mechanicalState, input = state?.status === 'constrained' ? state.runtimeWitness?.input : state?.input
      if (!['observed', 'constrained'].includes(state?.status) || state.visiblePoseCompleteness !== 'complete' || !text(state.evidence) || !completeInput(input)
        || !exactKeys(state, ['status', 'evidence', 'input', 'visiblePoseCompleteness', state.status === 'observed' ? 'visibilityProof' : 'runtimeWitness'])
        || (state.status === 'observed' && input?.setup?.counterHeightM === null) || (state.status === 'constrained' && state.input !== null)) fail('mechanical-state', 'Need a closed exclusive observed input/proof with measured numeric counter, or raw input:null with an explicit feasible constrained witness/proof', t, viewId)
      if (state?.status === 'constrained' || state?.status === 'observed') {
        const proof = state.status === 'constrained' ? state.runtimeWitness?.visibilityProof : state.visibilityProof
        const expected = { sourceVideoId: source.videoId, sourceSha256: source.sha256, sourceImage: frame.sourceImage, modelSha256: data.model.sha256, modelSourceCommit: data.model.sourceCommit, shotId: frame.shotId, viewId, timeSeconds: t, decodedTimeSeconds: frame.decodedTimeSeconds, input, camera, rectSourcePixels: rect, presentation: view.presentation, composite: view.composite ?? { mode: 'opaque' }, partOverrides: view.partOverrides ?? [], constraints: state.runtimeWitness?.constraints ?? [], continuity: state.runtimeWitness?.continuity ?? null, nativeGeometryAssumptions: data.nativeGeometryAssumptions ?? [], sourceNonIdentifiableFixedParts: proof?.sourceNonIdentifiableFixedParts }
        const landmarks = frame.landmarks.filter(item => (item.viewId ?? 'main') === viewId)
        const errors = state.status === 'constrained' ? witnessErrors(state.runtimeWitness, expected, data.anchors ?? [], landmarks, view) : visibilityProofErrors(state.visibilityProof, expected, data.anchors ?? [], landmarks, view)
        for (const error of errors) fail(state.status === 'constrained' ? 'witness-proof' : 'observed-native-proof', error, t, viewId)
        if (Array.isArray(proof?.sourceNonIdentifiableFixedParts)) (summary.sourceNonIdentifiableFixedParts ??= []).push(...proof.sourceNonIdentifiableFixedParts.map(part => ({ ...part, timeSeconds: t, viewId })))
      }
      for (const override of view.partOverrides ?? []) {
        if (!text(override.partPath) || (override.visibility !== undefined && !['visible', 'hidden'].includes(override.visibility)) || (override.worldPositionMetres !== undefined && !vector(override.worldPositionMetres, 3)) || (override.worldQuaternion !== undefined && (!vector(override.worldQuaternion, 4) || Math.abs(Math.hypot(...override.worldQuaternion) - 1) > 0.002))) fail('part-override', 'Disassembly/setup must use qualified native part paths and finite observed poses', t, viewId)
        if (!text(override.evidence) || override.sourceTimeSeconds !== frame.decodedTimeSeconds || !Array.isArray(override.landmarkIds) || !override.landmarkIds.length || new Set(override.landmarkIds).size !== override.landmarkIds.length || override.landmarkIds.some(id => !frame.landmarks.some(item => item.anchorId === id && item.role === 'check' && (item.viewId ?? 'main') === viewId))) fail('part-override-evidence', 'Overrides need actual current exposure evidence and independent native checks; unknown parts cannot be hidden', t, viewId)
      }
      if (new Set((view.partOverrides ?? []).map(override => override.partPath)).size !== (view.partOverrides ?? []).length) fail('duplicate-part-override', 'A qualified native part may be overridden only once per source view', t, viewId)
      if (view.anchorWorldMetres || frame.anchorWorldMetres) {
        if (!text(view.anchorPoseEvidence ?? frame.anchorPoseEvidence)) fail('posed-anchor-evidence', 'Posed CAD fitting points require independent mechanical pose evidence', t, viewId)
      }
      const landmarks = frame.landmarks.filter(item => (item.viewId ?? 'main') === viewId)
      const observed = new Set(), fitIds = new Set(), checkIds = new Set(), fitPixels = [], checkPixels = []
      for (const item of landmarks) {
        const anchor = anchors.get(item.anchorId)
        if (!anchor || observed.has(item.anchorId) || !['fit', 'check'].includes(item.role) || item.status !== 'observed' || !vector(item.pixel, 2) || item.pixel[0] < 0 || item.pixel[0] >= 1920 || item.pixel[1] < 0 || item.pixel[1] >= 1080 || !finite(item.uncertaintyPx) || item.uncertaintyPx < 0 || item.uncertaintyPx > PIXEL_LIMIT || !['manual', 'optical-flow', 'image-edge', 'template-match'].includes(item.method)) fail('source-measurement', `Invalid/duplicate/unmeasured source point ${item.anchorId}`, t, viewId)
        observed.add(item.anchorId)
        if (vector(rect, 4) && vector(item.pixel, 2) && (item.pixel[0] < rect[0] || item.pixel[1] < rect[1] || item.pixel[0] >= rect[0] + rect[2] || item.pixel[1] >= rect[1] + rect[3])) fail('landmark-roi', `${item.anchorId} lies outside its physical source view`, t, viewId)
        if (item.role === 'fit') { fitIds.add(item.anchorId); fitPixels.push(item.pixel); summary.fitLandmarks++ }
        if (item.role === 'check') { checkIds.add(item.anchorId); checkPixels.push(item.pixel); summary.checkLandmarks++ }
        if (item.method === 'optical-flow') {
          const evidence = item.trackingEvidence
          const seed = seeds.get(`${evidence?.seedTimeSeconds}/${viewId}/${item.anchorId}`)
          if (anchor?.kind !== 'physical-feature' || !seed || seed.role !== item.role || !finite(evidence?.forwardBackwardErrorPx) || evidence.forwardBackwardErrorPx > 1 || !finite(evidence?.seedPatchCorrelation) || evidence.seedPatchCorrelation < 0.80 || !finite(evidence?.adjacentPatchCorrelation) || evidence.adjacentPatchCorrelation < 0.90) fail('flow-provenance', `${item.anchorId}: no independent physical-feature seed/consistent actual-source track`, t, viewId)
        } else if (item.method === 'template-match') {
          const evidence = item.trackingEvidence
          const seed = seeds.get(`${evidence?.seedTimeSeconds}/${viewId}/${item.anchorId}`)
          if (!seed || seed.role !== item.role || evidence.reacquiredFromActualPixels !== true || !finite(evidence.wholeSourceViewCorrelation) || evidence.wholeSourceViewCorrelation < 0.998 || !finite(evidence.sourcePatchCorrelation) || evidence.sourcePatchCorrelation < 0.97) fail('template-provenance', `${item.anchorId}: independent seed and source-view/source-feature correlations must be retained`, t, viewId)
        } else if (item.method === 'image-edge' && !item.measurementEvidence) fail('edge-provenance', `${item.anchorId}: no actual source edge/search evidence`, t, viewId)
        if ((view.partOverrides ?? []).some(override => override.visibility === 'hidden' && (anchor?.partPath === override.partPath || anchor?.partPath?.startsWith(`${override.partPath}/`)))) fail('hidden-anchor', `${item.anchorId}: physical landmark belongs to a hidden native part`, t, viewId)
      }
      const cameraKind = (view.cameraEvidence ?? frame.cameraEvidence ?? { kind: 'direct-fit' }).kind
      if (cameraKind === 'direct-fit') {
        if (fitIds.size < 6 || checkIds.size < 2) fail('independent-check-count', `Direct camera needs >=6 fit and >=2 separately measured held-out anchors; observed ${fitIds.size}/${checkIds.size}`, t, viewId)
      } else if (!['shared-rigid-sequence', 'source-registered'].includes(cameraKind) || (!checkIds.size && !(view.nativeLineChecks?.length))) fail('derived-native-check', 'Derived camera needs an independently identifiable calibration and actual target native held-out point or native line evidence', t, viewId)
      for (const item of landmarks) if (item.measurementEvidence || item.trackingEvidence) for (const error of measuredImageErrors(item, frame.sourceImage)) fail('measurement-image-binding', `${item.anchorId}: ${error}`, t, viewId)
      for (const error of nativeLineErrors(view.nativeLineChecks ?? [], frame.sourceImage, rect, view.partOverrides ?? [])) fail('native-line-evidence', error, t, viewId)
      const contourIds = new Set()
      for (const contour of view.sourceContourChecks ?? []) {
        if (!text(contour.id) || contourIds.has(contour.id) || !text(contour.partPath) || !contour.partPath.startsWith('harmonic-analyzer/') || !Array.isArray(contour.sourceContourPixels) || contour.sourceContourPixels.length < 2 || !contour.sourceContourPixels.every(point => inRect(point, rect)) || contour.sourceContourPixels.every(point => canonicalJson(point) === canonicalJson(contour.sourceContourPixels[0])) || !finite(contour.uncertaintyPx) || contour.uncertaintyPx < 0 || contour.uncertaintyPx > PIXEL_LIMIT || canonicalJson(contour.measurementEvidence?.sourceImage) !== canonicalJson(frame.sourceImage) || !text(contour.measurementEvidence?.evidence)) fail('source-contour-evidence', 'Need a distinct nondegenerate actually measured current-source native contour inside ROI with bounded uncertainty', t, viewId)
        contourIds.add(contour.id)
      }
      const composite = view.composite ?? { mode: 'opaque' }
      if (composite.mode === 'opaque' ? !exactKeys(composite, ['mode']) : composite.mode !== 'crossfade' || !exactKeys(composite, ['mode', 'groupId', 'opacity']) || !text(composite.groupId) || !finite(composite.opacity) || composite.opacity < 0 || composite.opacity > 1 || !text(view.compositeEvidence)) fail('source-composite', 'Need explicit opaque mode or source-measured crossfade group/weight evidence', t, viewId)
      if (composite.mode === 'crossfade' && composite.opacity <= 0 && (landmarks.length || view.nativeLineChecks?.length)) fail('dropped-source-layer', 'Source-discernible corresponding points/lines cannot have zero rendered image contribution', t, viewId)
      if ([...checkIds].some(id => fitIds.has(id)) || checkPixels.some(pixel => fitPixels.some(fit => vector(pixel, 2) && vector(fit, 2) && Math.hypot(pixel[0] - fit[0], pixel[1] - fit[1]) < EPSILON))) fail('fit-check-leakage', 'A held-out anchor/pixel cannot also be a camera-fitting observation', t, viewId)
    }
    for (const error of sourceCompositeErrors(views)) fail(error.code, error.detail, t, error.viewId)
    for (const item of frame.landmarks) if (!viewIds.has(item.viewId ?? 'main')) fail('unknown-landmark-view', `Unknown view for ${item.anchorId}`, t, item.viewId)
  }
  const present = time => Math.abs(times[nearestPtsIndex(times, time)] - time) <= EPSILON
  summary.integerSecondsRequired = Math.floor(duration) + 1
  for (let second = 0; second <= Math.floor(duration); second++) {
    if (present(second)) summary.integerSecondsPresent++
    else fail('missing-integer-second', `Missing required source second ${second}`, second)
  }
  const changes = new Set([...shots.values()].flatMap(shot => [shot.startSeconds, shot.endSeconds]).filter(time => time < duration))
  for (const time of coverage?.changeTimesSeconds ?? []) {
    if (!finite(time) || time < 0 || time >= duration) fail('change-time', 'Invalid measured source change time', time)
    else changes.add(time)
  }
  summary.changeTimesRequired = changes.size
  for (const time of changes) { if (present(time)) summary.changeTimesPresent++; else fail('missing-change', `Missing source shot/mechanical/camera change ${time}`, time) }
  if (native && allNative && nativeIndices.size !== native.pts.length) fail('missing-native-frame', `All-change census claims every native frame but supplies ${nativeIndices.size}/${native.pts.length}`)
  failures.push(...cameraEvidenceErrors(data))
  return summary
}

export async function probeSource(path, expected, { signal } = {}) {
  const observedSha256 = await sha256File(path)
  if (observedSha256 !== expected.sha256) throw new Error(`Source SHA256 mismatch: ${path}`)
  const { stdout } = await runTool('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_format', '-show_frames', '-show_entries', 'stream=width,height,avg_frame_rate,duration:format=duration:frame=best_effort_timestamp_time', '-of', 'json', path], { signal })
  const probe = JSON.parse(stdout), stream = probe.streams?.[0]
  const [numerator, denominator] = (stream?.avg_frame_rate ?? '').split('/').map(Number)
  const fps = numerator / denominator
  const declared = expected.fps
  let declaredFps = typeof declared === 'number' ? declared : declared?.numerator / declared?.denominator
  if (typeof declared === 'string') { const terms = declared.split('/').map(Number); declaredFps = terms.length === 2 ? terms[0] / terms[1] : Number(declared) }
  if (!finite(declaredFps) || Math.abs(declaredFps - fps) > 0.0001) throw new Error(`Actual source frame rate differs from observations: ${fps}/${declaredFps}`)
  const pts = (probe.frames ?? []).map(frame => Number(frame.best_effort_timestamp_time))
  if (stream?.width !== 1920 || stream?.height !== 1080 || !finite(fps) || fps <= 0 || !pts.length || pts.some((value, index) => !finite(value) || (index && value <= pts[index - 1]))) throw new Error(`Invalid actual decoded stream/PTS: ${path}`)
  const durationSeconds = Number(probe.format?.duration)
  if (Math.abs(durationSeconds - expected.durationSeconds) > 0.05) throw new Error(`Actual source duration differs from observations: ${durationSeconds}/${expected.durationSeconds}`)
  return { observedSha256, width: stream.width, height: stream.height, fps, durationSeconds, nativeFrameCount: pts.length, pts }
}

export async function loadReferences(webRoot, referenceRoot, { signal } = {}) {
  const metadata = JSON.parse(await readFile(resolve(referenceRoot, 'evidence/footage-metadata.json'), 'utf8'))
  const records = [], failures = []
  for (const id of VIDEO_IDS) {
    try {
      const data = JSON.parse(await readFile(resolve(webRoot, `content/${id}.observations.json`), 'utf8'))
      const entry = metadata.find(item => item.id === id)
      if (!entry || entry.sha256 !== data.source?.sha256) throw new Error('Measured source identity differs from independent acquisition metadata')
      // Keep paths relocatable without requiring original /tmp directories.
      const suffix = entry.path.split('/videos/')[1]
      if (!suffix) throw new Error('Source metadata lacks a videos-relative private filename')
      const sourcePath = resolve(referenceRoot, 'videos', suffix)
      const native = await probeSource(sourcePath, data.source, { signal })
      const report = inspectReference(data, id, native)
      try { report.sourceImageVerification = await verifyFrameImages(sourcePath, data, { signal, native, source: data.source }) }
      catch (error) { report.failures.push({ code: 'source-image-replay', detail: error.message }) }
      if (data.sourceCameraRigs?.length) {
        try { report.sharedRigVerification = await verifySharedRigs(webRoot, data, native, { signal, sourcePath }) }
        catch (error) { report.failures.push({ code: 'rig-calibration', detail: error.message }) }
      }
      records.push({ id, data, digest: jsonDigest(data), sourcePath, native, report })
    } catch (error) { failures.push({ videoId: id, code: 'source-prerequisite', detail: error.message }) }
  }
  return { records, failures }
}

export function errorStats(values) {
  if (!values.length) return { count: 0, maxPx: null, rmsPx: null }
  let maximum = 0, sumSquares = 0
  for (const value of values) { maximum = Math.max(maximum, value); sumSquares += value * value }
  return { count: values.length, maxPx: maximum, rmsPx: Math.sqrt(sumSquares / values.length) }
}

/** Half-open ROI edge partition: disjoint source tiles do not share an opacity budget. */
export function sourceCompositeErrors(views) {
  const failures = [], completedGroups = new Set()
  for (let index = 0; index < views.length;) {
    const first = views[index], composite = first.composite ?? { mode: 'opaque' }
    if (composite.mode !== 'crossfade') { index++; continue }
    const groupId = composite.groupId, stack = []
    const reject = (code, detail) => failures.push({ code, detail, viewId: first.id })
    if (completedGroups.has(groupId)) reject('composite-layer-order', 'Crossfade group must be one contiguous actual source layer stack')
    completedGroups.add(groupId)
    while (index < views.length && views[index].composite?.mode === 'crossfade' && views[index].composite.groupId === groupId) stack.push(views[index++])
    if (stack.length < 2 || stack.some(view => !vector(view.rectSourcePixels, 4) || view.rectSourcePixels[2] <= 0 || view.rectSourcePixels[3] <= 0 || !finite(view.composite.opacity) || view.composite.opacity < 0 || view.composite.opacity > 1)) {
      reject('composite-layer-weights', 'Need >=2 measured layers with finite source ROIs and individual contribution in [0,1]')
      continue
    }
    const xs = [...new Set(stack.flatMap(view => [view.rectSourcePixels[0], view.rectSourcePixels[0] + view.rectSourcePixels[2]]))].sort((a, b) => a - b)
    const ys = [...new Set(stack.flatMap(view => [view.rectSourcePixels[1], view.rectSourcePixels[1] + view.rectSourcePixels[3]]))].sort((a, b) => a - b)
    let positive = false
    for (let y = 0; y < ys.length - 1; y++) for (let x = 0; x < xs.length - 1; x++) {
      let weight = 0, active = 0
      for (const view of stack) {
        const [left, top, width, height] = view.rectSourcePixels
        if (xs[x] >= left && xs[x] < left + width && ys[y] >= top && ys[y] < top + height) { weight += view.composite.opacity; active++ }
      }
      if (!active) continue
      positive ||= weight > 0
      if (weight > 1 + EPSILON) reject('composite-layer-weights', `Measured source group ${groupId} has active weight ${weight}>1 in half-open source cell [${xs[x]},${ys[y]},${xs[x + 1] - xs[x]},${ys[y + 1] - ys[y]}]; no normalization or alpha-over rescue`)
    }
    if (!positive) reject('composite-layer-weights', 'Measured source group has no positive image contribution anywhere in its ROI union')
  }
  return failures
}

/** Re-decode only claimed actual exposures, in each explicitly declared reversible format. */
export async function verifyFrameImages(sourcePath, data, { signal, timeoutMs = 180_000, native = null, source = data?.source } = {}) {
  const observedSha256 = await sha256File(sourcePath)
  if (source && observedSha256 !== source.sha256) throw new Error('Independent original MP4 SHA256 mismatch before image replay')
  const identitySource = source ?? { sha256: observedSha256 }, formats = new Map()
  for (const { image, path } of claimedSourceImages(data)) {
    const error = sourceImageError(image, identitySource, native)
    if (error) throw new Error(`${path}: ${error}`)
    let images = formats.get(image.pixelFormat)
    if (!images) { images = new Map(); formats.set(image.pixelFormat, images) }
    const value = image.sha256Bgr8 ?? image.sha256Gray8
    if (images.has(image.frameIndex) && images.get(image.frameIndex) !== value) throw new Error(`Conflicting ${image.pixelFormat} hashes at actual native frame ${image.frameIndex}`)
    images.set(image.frameIndex, value)
  }
  const frames = Array.isArray(data) ? data : data?.frames ?? []
  for (const frame of frames) if (frame.sourceImage && native && (!finite(frame.decodedTimeSeconds) || Math.abs(native.pts[frame.sourceImage.frameIndex] - frame.decodedTimeSeconds) > 0.001 || (frame.decodedFrameIndex !== undefined && frame.decodedFrameIndex !== frame.sourceImage.frameIndex))) throw new Error(`Stale native PTS/index at ${frame.timeSeconds}s`)
  if (!formats.size) return { count: 0, formats: [], frameHashDigest: null, reason: 'No source-image pixels claimed' }
  const directory = await mkdtemp(join(tmpdir(), 'harmonic-verify-framehash-')), reports = [], allDigest = createHash('sha256')
  try {
    for (const [pixelFormat, images] of [...formats].sort(([a], [b]) => a.localeCompare(b))) {
      const indices = [...images.keys()].sort((a, b) => a - b), spans = []
      let start = indices[0], last = start
      for (const index of indices.slice(1)) {
        if (index === last + 1) last = index
        else { spans.push(start === last ? `eq(n,${start})` : `between(n,${start},${last})`); start = last = index }
      }
      spans.push(start === last ? `eq(n,${start})` : `between(n,${start},${last})`)
      const filter = join(directory, `${pixelFormat}-select.txt`)
      await writeFile(filter, `select='${spans.join('+')}'`)
      const { stdout } = await runTool('ffmpeg', ['-v', 'error', '-threads', '2', '-copyts', '-i', sourcePath, '-an', '-filter_script:v', filter, '-frames:v', String(indices.length), '-fps_mode', 'passthrough', '-pix_fmt', pixelFormat === 'bgr8' ? 'bgr24' : 'gray', '-f', 'framehash', '-hash', 'sha256', 'pipe:1'], { signal, timeoutMs })
      const output = stdout.toString(), timeBase = output.match(/^#tb 0:\s*(\d+)\/(\d+)/m)
      const tick = timeBase ? Number(timeBase[1]) / Number(timeBase[2]) : NaN
      const decoded = output.split('\n').filter(line => line.trim() && !line.startsWith('#')).map(line => line.split(',').map(value => value.trim()))
      if (decoded.length !== indices.length || !finite(tick) || tick <= 0) throw new Error(`Actual ${pixelFormat} framehash/PTS coverage ${decoded.length}/${indices.length}`)
      const digest = createHash('sha256'), bytesPerFrame = 1920 * 1080 * (pixelFormat === 'bgr8' ? 3 : 1)
      for (let i = 0; i < indices.length; i++) {
        const row = decoded[i], index = indices[i], actual = row[5], actualPts = Number(row[2]) * tick
        if (row.length !== 6 || Number(row[4]) !== bytesPerFrame || actual !== images.get(index)) throw new Error(`Actual source ${pixelFormat} bytes/hash mismatch at native frame ${index}: ${actual}/${images.get(index)}`)
        const expectedPts = native?.pts[index] ?? frames.find(frame => frame.sourceImage?.frameIndex === index)?.decodedTimeSeconds
        if (expectedPts !== undefined && (!finite(actualPts) || Math.abs(actualPts - expectedPts) > tick / 2 + 0.001)) throw new Error(`Stale actual decoded ${pixelFormat} PTS at frame ${index}: ${actualPts}/${expectedPts}`)
        digest.update(`${index}:${actual}\n`); allDigest.update(`${pixelFormat}:${index}:${actual}\n`)
      }
      reports.push({ pixelFormat, count: indices.length, bytesPerFrame, frameHashDigest: digest.digest('hex'), decoder: `ffmpeg native select; passthrough original PTS; SHA256 over actual ${pixelFormat} bytes` })
    }
    return { count: reports.reduce((sum, item) => sum + item.count, 0), formats: reports, frameHashDigest: allDigest.digest('hex'), originalSourceSha256: observedSha256 }
  } finally { await rm(directory, { recursive: true, force: true }) }
}

/** Reproject native geometry and independently replay actual phase/period source pixels. */
export async function verifySharedRigs(webRoot, data, native, { signal, sourcePath } = {}) {
  if (!text(sourcePath) || await sha256File(sourcePath) !== data.source.sha256) throw new Error('Actual original MP4 is required for independent rig phase/period pixel replay')
  const directory = await mkdtemp(join(tmpdir(), 'harmonic-verify-rig-'))
  try {
    const packet = join(directory, 'reference.json')
    await writeFile(packet, JSON.stringify(data))
    const code = `import importlib.util,json,sys,os
os.environ["OPENBLAS_NUM_THREADS"]="2";os.environ["OMP_NUM_THREADS"]="2"
spec=importlib.util.spec_from_file_location("source_fit",sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
data=json.load(open(sys.argv[2]));inventory=json.load(open(sys.argv[3]))
if inventory.get("sha256") != data["model"]["sha256"]: raise ValueError("Native inventory model SHA256 mismatch")
for rig in data["sourceCameraRigs"]:
 if rig["independentLoopEvidence"]["decodedNativeFrameCount"] != int(sys.argv[4]): raise ValueError("Stale independent native frame census")
points=m.world_points(data,inventory);rigs=m.prepare_camera_rigs(data,points)
if any(not rig["passed"] for rig in rigs.values()): raise ValueError("Fresh global native projection/held-out check failed")
import cv2,numpy as np
cv2.setNumThreads(2)
states=[];required=set()
for rig in data["sourceCameraRigs"]:
 evidence=rig["independentLoopEvidence"];entries=evidence["sourceFrameMap"]
 indices=[entry["sourceImage"]["frameIndex"] for entry in entries]
 start=min(indices);stop=max(indices)+1;loop=evidence["loopNativeFrameCount"];adjacent=loop-2
 if loop != 142 or stop-start-loop < loop: raise ValueError("Actual source phase map does not span a complete independent photographic loop comparison")
 requests={}
 for entry in entries:
  if entry.get("roiSourcePixels") != [680,80,520,980]: raise ValueError("Missing/mismatched independently measured machine correlation ROI")
  requests.setdefault(entry["sourceImage"]["frameIndex"],[]).append(entry)
 phases={image["sourceImage"]["frameIndex"]:image["phaseIndex"] for image in rig["phaseImages"]}
 required.update(range(start,stop));required.update(phases);required.update(indices)
 states.append({"id":rig["id"],"start":start,"stop":stop,"loop":loop,"adjacent":adjacent,"requests":requests,"phases":phases,"refs":{},"matrix":None,"pending":[],"period":[],"adjacentPeriod":[],"registrations":[]})
def normalise(gray):
 row=gray[20:265,170:300].astype(np.float64).ravel()
 row-=row.mean();norm=np.linalg.norm(row)
 if norm < 1: raise ValueError("Actual source photograph has no independently observable phase contrast")
 return row/norm
def register(state,index,row):
 correlations=np.clip(state["matrix"]@row,-1,1);order=np.argsort(correlations);winner=int(order[-1]);second=float(correlations[order[-2]])
 for entry in state["requests"].get(index,[]):
  if winner != entry["referencePhaseIndex"] or correlations[winner] <= .75 or correlations[winner] <= second: raise ValueError("Actual native source pixels disagree with claimed photographic phase at frame "+str(index))
  state["registrations"].append({"frameIndex":index,"phaseIndex":winner,"ncc":float(correlations[winner]),"secondBestPhaseNcc":second,"margin":float(correlations[winner]-second)})
options=[cv2.CAP_PROP_N_THREADS,2] if hasattr(cv2,"CAP_PROP_N_THREADS") else []
cap=cv2.VideoCapture(sys.argv[5],cv2.CAP_FFMPEG,options)
if not cap.isOpened(): raise ValueError("Independent native original MP4 pixel decoder is unavailable")
ring={}
try:
 for index in range(max(required)+1):
  if not cap.grab(): raise ValueError("Original native source exposure is missing at frame "+str(index))
  if index not in required: continue
  ok,bgr=cap.retrieve()
  if not ok or bgr.shape != (1080,1920,3): raise ValueError("Actual native source pixel dimensions/decode failed")
  # Measured source recipe: native BGR -> gray, then quarter-size INTER_AREA.
  gray=cv2.resize(cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY),(480,270),interpolation=cv2.INTER_AREA)
  for state in states:
   if index in state["phases"]:
    state["refs"][state["phases"][index]]=normalise(gray)
    if len(state["refs"]) == 71:
     state["matrix"]=np.stack([state["refs"][phase] for phase in range(71)])
     for oldIndex,oldRow in state["pending"]: register(state,oldIndex,oldRow)
     state["pending"].clear()
   if index in state["requests"]:
    row=normalise(gray)
    if state["matrix"] is None: state["pending"].append((index,row))
    else: register(state,index,row)
   if state["start"] <= index < state["stop"]:
    for offset,key in ((state["loop"],"period"),(state["adjacent"],"adjacentPeriod")):
     old=index-offset
     if old >= state["start"]:
      if old not in ring: raise ValueError("Actual source period pixels are unavailable")
      state[key].append(float(cv2.absdiff(gray,ring[old]).mean()))
  ring[index]=gray
  oldest=index-142
  for old in list(ring):
   if old < oldest: del ring[old]
finally: cap.release()
pixelProof={}
for state in states:
 registrations=state["registrations"];period=float(np.median(state["period"]));adjacent=float(np.median(state["adjacentPeriod"]))
 if state["matrix"] is None or len(registrations) != sum(map(len,state["requests"].values())) or len(state["period"]) < 142 or not np.isfinite(period) or not np.isfinite(adjacent) or not 0 <= period < adjacent: raise ValueError("Independent actual source photographic loop/phase proof failed")
 pixelProof[state["id"]]={"sourceFrameCount":len(registrations),"referencePhaseCount":71,"sourceNativeFrameInterval":[state["start"],state["stop"]],"recipe":"Actual original native BGR -> OpenCV gray -> 480x270 INTER_AREA; every machine ROI pixel; exhaustive 71 references; mean/L2-normalised brightness","minimumNcc":min(row["ncc"] for row in registrations),"minimumSecondBestMargin":min(row["margin"] for row in registrations),"periodPixelComparison":{"nativeOffset142MedianMAD":period,"adjacentOffsetMedianMAD":adjacent,"adjacentPhaseControlNativeOffsetFrames":state["adjacent"],"nativePairCount":len(state["period"]),"adjacentPairCount":len(state["adjacentPeriod"]),"recipe":"Entire actual 480x270 quarter-gray frame absolute-difference means; median over every pair in the reported native interval"}}
print(json.dumps({"rigs":{key:rig["proof"] for key,rig in rigs.items()},"sourcePixelRegistration":pixelProof}))
`
    const { stdout } = await runTool('python3', ['-c', code, resolve(webRoot, 'scripts/fit-source.py'), packet, resolve(process.env.HARMONIC_MODEL_INVENTORY ?? '/tmp/harmonic-web-model/model-inventory.json'), String(native.nativeFrameCount), sourcePath], { signal, timeoutMs: 180_000 })
    return { method: 'independent-native-inventory-global-reprojection-and-actual-source-pixel-registration', ...JSON.parse(stdout.toString()), originalSourceSha256: data.source.sha256, actualGpuAcceptance: false }
  } finally { await rm(directory, { recursive: true, force: true }) }
}
