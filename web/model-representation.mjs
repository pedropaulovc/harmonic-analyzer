// Shared by the importer, browser and verifier. This validates a compiled/tracked
// approval record, never a manifest supplied by the downloaded model.
export const REPRESENTATION_KIND = 'lossless-web-model-representation'
export const REPRESENTATION_PATH = 'models/ha-harmonic-analyzer.glb'
export const PIPELINE_VERSION = 1
export const PIPELINE_STEPS = Object.freeze(['exact-dedup', 'meshopt'])

const SHA256 = /^[0-9a-f]{64}$/
const COMMIT = /^[0-9a-f]{40}$/

function record(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).length !== keys.length
    || !keys.every(key => Object.hasOwn(value, key))) throw new Error(`Invalid ${label} fields`)
}
function requireValue(condition, label) {
  if (!condition) throw new Error(`Invalid ${label}`)
}

export function validateModelRepresentation(value) {
  record(value, ['schemaVersion', 'kind', 'source', 'representation', 'pipeline', 'equivalence'], 'model representation')
  requireValue(value.schemaVersion === 1 && value.kind === REPRESENTATION_KIND, 'model representation schema/version')
  record(value.source, ['sha256', 'sourceCommit'], 'native source')
  requireValue(typeof value.source.sha256 === 'string' && SHA256.test(value.source.sha256), 'native source SHA256')
  requireValue(typeof value.source.sourceCommit === 'string' && COMMIT.test(value.source.sourceCommit), 'native source commit')
  record(value.representation, ['path', 'sha256', 'byteLength', 'codec'], 'representation')
  requireValue(value.representation.path === REPRESENTATION_PATH, 'representation path')
  requireValue(typeof value.representation.sha256 === 'string' && SHA256.test(value.representation.sha256), 'representation SHA256')
  requireValue(Number.isSafeInteger(value.representation.byteLength) && value.representation.byteLength > 0, 'representation byte length')
  requireValue(value.representation.codec === 'EXT_meshopt_compression', 'representation codec')
  record(value.pipeline, ['version', 'steps', 'codecVersion'], 'pipeline')
  requireValue(value.pipeline.version === PIPELINE_VERSION, 'pipeline version')
  requireValue(Array.isArray(value.pipeline.steps) && value.pipeline.steps.length === PIPELINE_STEPS.length
    && PIPELINE_STEPS.every((step, index) => value.pipeline.steps[index] === step), 'lossless pipeline steps')
  requireValue(typeof value.pipeline.codecVersion === 'string' && /^meshoptimizer@[0-9]+\.[0-9]+\.[0-9]+$/.test(value.pipeline.codecVersion), 'Meshopt codec version')
  record(value.equivalence, ['method', 'semanticSha256', 'drawableCount'], 'decoded equivalence')
  requireValue(value.equivalence.method === 'decoded-per-drawable-exact-v1', 'decoded equivalence method')
  requireValue(typeof value.equivalence.semanticSha256 === 'string' && SHA256.test(value.equivalence.semanticSha256), 'decoded semantic SHA256')
  requireValue(Number.isSafeInteger(value.equivalence.drawableCount) && value.equivalence.drawableCount > 0, 'decoded drawable count')
  return value
}

export function assertNativeSourceAssociation(representation, native) {
  const approved = validateModelRepresentation(representation)
  if (approved.source.sha256 !== native.modelSha256 || approved.source.sourceCommit !== native.sourceCommit) {
    throw new Error('Compiled model representation targets a different native CAD source; regenerate the representation and matching native metadata')
  }
  return approved
}

export function assertModelRepresentationBytes(representation, native, actual) {
  const approved = assertNativeSourceAssociation(representation, native)
  if (actual.sha256 !== approved.representation.sha256 || actual.byteLength !== approved.representation.byteLength) {
    throw new Error(`Model representation identity mismatch: observed ${actual.sha256} (${actual.byteLength} bytes); expected ${approved.representation.sha256} (${approved.representation.byteLength} bytes); model not parsed or added to the scene`)
  }
  return approved
}
