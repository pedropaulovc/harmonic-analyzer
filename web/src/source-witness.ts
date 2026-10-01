import { createMechanismPose, solveMechanism, type MechanismInput, type MechanismPose } from './mechanics'
import { physicalChannelAngle } from './kinematics'
import type { CameraRecord, ImagePlaneWarp, PartOverride, SourceComposite, SourceLayoutEntry } from './scene'
import { prepareImagePlaneFootprintContext, imagePlaneSourceFootprintBounds } from './image-plane-homography'

export const ROD_HEAD_FUNCTIONAL_EQUIVALENCE = {
  id: 'rod-head-functional-equivalence',
  status: 'user-approved-pending-cad-match',
  scope: 'rod-head-topology-only',
  authority: 'the one plate-like head vs u crosspiece is a discrepancy but both serve the same purpose; the 3d model will be fixed later to match device; animate assuming they will match later',
  sourceCounterpart: 'Filmed U-shaped connecting-rod junction/crosspiece',
  interpretation: 'Functional linkage mapping for animation only; not a current geometric-fidelity pass.',
} as const
export const LOWER_ROCKER_SIDE_FACE_FUNCTIONAL_EXCEPTION = {
  id: 'lower-rocker-side-face-functional-exception',
  status: 'user-approved-absent-uncertified',
  scope: 'two-lower-rocker-side-face-features-only',
  authority: 'Allow a narrow functional exception',
  sourceCounterpart: 'Two small rimmed/recessed lower-rocker side-face features either side of the fulcrum',
  sourceFeatureIds: ['lower-rocker-nearest-left-face-bore', 'lower-rocker-nearest-right-face-bore'],
  interpretation: 'Only the two declared side-face features may remain absent from the native rockers and uncertified; animation-only exception, not whole-part correspondence or a measured/topology fidelity pass.',
} as const
export type NativeGeometryAssumption = (typeof ROD_HEAD_FUNCTIONAL_EQUIVALENCE | typeof LOWER_ROCKER_SIDE_FACE_FUNCTIONAL_EXCEPTION) & { nativePartPaths: string[] }

export function validateNativeGeometryAssumptions(assumptions: readonly NativeGeometryAssumption[] | undefined): void {
  if (assumptions === undefined) return
  if (!Array.isArray(assumptions) || assumptions.length > 2) throw new Error('Native geometry assumptions permit at most one of each closed user-approved declaration.')
  const ids = new Set<NativeGeometryAssumption['id']>()
  for (const assumption of assumptions) {
    const policy = assumption?.id === ROD_HEAD_FUNCTIONAL_EQUIVALENCE.id ? ROD_HEAD_FUNCTIONAL_EQUIVALENCE
      : assumption?.id === LOWER_ROCKER_SIDE_FACE_FUNCTIONAL_EXCEPTION.id ? LOWER_ROCKER_SIDE_FACE_FUNCTIONAL_EXCEPTION : null
    if (!policy || ids.has(assumption.id)) throw new Error('Unknown or duplicate native geometry assumption identity.')
    ids.add(assumption.id)
    keys(assumption, [...Object.keys(policy), 'nativePartPaths'], 'Native geometry assumption')
    for (const key of Object.keys(policy) as (keyof typeof policy)[]) {
      if (!equalRecord(assumption[key], policy[key])) throw new Error(`Native geometry assumption has unapproved ${key}.`)
    }
    const pathPattern = policy.id === ROD_HEAD_FUNCTIONAL_EQUIVALENCE.id
      ? /^harmonic-analyzer\/channel\/connecting-rod-(?:[1-9]|1[0-9]|20)$/
      : /^harmonic-analyzer\/channel\/rocker-arm-(?:[1-9]|1[0-9]|20)$/
    if (!Array.isArray(assumption.nativePartPaths) || !assumption.nativePartPaths.length || assumption.nativePartPaths.length > 20
      || new Set(assumption.nativePartPaths).size !== assumption.nativePartPaths.length
      || assumption.nativePartPaths.some((path: unknown) => typeof path !== 'string' || !pathPattern.test(path))) throw new Error(`Approved ${policy.id} permits only unique qualified paths in its declared native family, numbered 1..20.`)
  }
}

export interface SerializedInput extends Omit<MechanismInput, 'amplitudes' | 'phases'> {
  amplitudes: number[]
  phases: number[]
}
export type InputField = 'crankTurns' | 'gearing' | 'magnification' | `amplitudes[${number}]` | `phases[${number}]` | `setup.${keyof MechanismInput['setup']}`
export const SETUP_KEYS: readonly (keyof MechanismInput['setup'])[] = [
  'counterHeightM', 'meanLineAngleRad', 'platenOffsetM', 'wireFixtureOffsetM',
  'coneSwingRad', 'pinionCamRad', 'heldChannelTurns', 'driveCrankOffsetTurns',
]
export const INPUT_FIELDS: readonly InputField[] = [
  'crankTurns', 'gearing', 'magnification',
  ...Array.from({ length: 20 }, (_, i) => `amplitudes[${i}]` as InputField),
  ...Array.from({ length: 20 }, (_, i) => `phases[${i}]` as InputField),
  ...SETUP_KEYS.map((key) => `setup.${key}` as InputField),
]
const fieldSet: Record<string, true> = Object.fromEntries(INPUT_FIELDS.map((field) => [field, true]))
export type SourceConstraint = (
  | { kind: 'input-value'; field: InputField; value: number | MechanismInput['gearing'] | null; tolerance: number }
  | { kind: 'input-interval'; field: InputField; minimum: number; maximum: number }
  | { kind: 'effective-bank-drive'; minimumTurns: number; maximumTurns: number; winding: 'unwrapped' | 'modulo-one' }
  | { kind: 'channel-angle'; channelIndex: number; minimumRadians: number; maximumRadians: number; winding: 'unwrapped' | 'modulo-turn' }
  | { kind: 'paper-travel'; minimumMetres: number; maximumMetres: number }
  | { kind: 'pen-travel'; minimumMetres: number; maximumMetres: number }
) & { evidence: string }
export type SourceImageIdentity = {
  frameIndex: number; width: number; height: number; sourceSha256: string
} & ({ pixelFormat: 'bgr8'; sha256Bgr8: string; sha256Gray8?: never } | { pixelFormat: 'gray8'; sha256Gray8: string; sha256Bgr8?: never })
export interface SourceImagePlaneWarp {
  kind: 'homography'
  unwarpedViewportPixels: [number, number]
  cornersSourcePixels: [[number, number], [number, number], [number, number], [number, number]]
  sourceImage: SourceImageIdentity
  referenceSourceImage: SourceImageIdentity
  cornerMeasurementEvidence: {
    sourceImage: SourceImageIdentity
    referenceSourceImage: SourceImageIdentity
    evidence: string
    [key: string]: unknown
  }
  correspondences: Array<{
    id: string
    role: 'fit' | 'check'
    referencePixelSource: [number, number]
    pixelSource: [number, number]
    method: 'manual' | 'optical-flow' | 'image-edge' | 'template-match'
    uncertaintyPx: number
    measurementEvidence: {
      sourceImage: SourceImageIdentity
      referenceSourceImage: SourceImageIdentity
      evidence: string
      [key: string]: unknown
    }
  }>
}
export type SourceCoverage =
  | { kind: 'landmarks'; landmarkIds: string[] }
  | { kind: 'native-line-checks'; lineCheckIds: string[] }
  | { kind: 'source-contour'; contourCheckIds: string[] }
  | { kind: 'rigid-native-attachment'; attachedToPartPath: string }
export type AxisPerspectiveBiasComponents = {
  geometryBoundPx: number
  evidence: string
} & (
  | { kind: 'independent-geometry'; sourceLocalizationBoundPx: 0 }
  | { kind: 'includes-source-localization'; sourceLocalizationBoundPx: number }
)
export interface NativeLineCheck {
  id: string
  partPath: string
  partLocalLineMetres: [[number, number, number], [number, number, number]]
  sourceLinePixels: [[number, number], [number, number]]
  uncertaintyPx: number
  measurementEvidence: {
    sourceImage: SourceImageIdentity
    detector: string
    edgeRows: Array<{ y: number; left: number; right: number; contrast: number; [key: string]: unknown }>
    axisPerspectiveBiasBoundPx: number
    axisPerspectiveBiasComponents: AxisPerspectiveBiasComponents
    axisPerspectiveEvidence: string
    axisPerspectiveBiasSpace?: 'source-global' | 'unwarped-viewport'
    axisPerspectiveBiasRegionViewportPixels?: [number, number, number, number]
    [key: string]: unknown
  }
}
export interface SourceContourCheck {
  id: string
  partPath: string
  sourceContourPixels: [number, number][]
  uncertaintyPx: number
  measurementEvidence: { sourceImage: SourceImageIdentity; evidence: string }
}
/** Closed budget semantics match the independent static/GPU acceptance certificate. */
export function validateNativeLineAxisBiasComponents(line: NativeLineCheck, context: Pick<SourceLayoutEntry, 'rectSourcePixels' | 'resolvedImagePlaneWarp'>, label: string): void {
  const footprintContext = prepareImagePlaneFootprintContext(context, label)
  const sourceUncertainty = finite(line.uncertaintyPx, `${label}.uncertaintyPx`)
  if (sourceUncertainty < 0) throw new Error(`${label}: source localization uncertainty must be nonnegative.`)
  const measured = line.measurementEvidence, components = measured?.axisPerspectiveBiasComponents
  if (!measured || !components) throw new Error(`${label}: an explicit axis-bias decomposition certificate is required.`)
  keys(components, ['kind', 'geometryBoundPx', 'sourceLocalizationBoundPx', 'evidence'], label)
  const total = finite(measured.axisPerspectiveBiasBoundPx, `${label}.axisPerspectiveBiasBoundPx`)
  const geometry = finite(components.geometryBoundPx, `${label}.geometryBoundPx`)
  const source = finite(components.sourceLocalizationBoundPx, `${label}.sourceLocalizationBoundPx`)
  evidence(components.evidence, label)
  if (total < 0 || geometry < 0 || source < 0
    || Math.abs(geometry + source - total) > 1e-9 * Math.max(1, total)) throw new Error(`${label}: axis components do not close the unchanged authored bound.`)
  const space = measured.axisPerspectiveBiasSpace
  if (footprintContext ? !['source-global', 'unwarped-viewport'].includes(space ?? '') : space !== undefined && space !== 'source-global') throw new Error(`${label}: axis-bias coordinate space is missing or unsupported.`)
  if (components.kind === 'independent-geometry') {
    if (source !== 0) throw new Error(`${label}: independent geometry cannot contain source localization.`)
  } else if (components.kind === 'includes-source-localization') {
    if ((space ?? 'source-global') !== 'source-global' || source !== sourceUncertainty) throw new Error(`${label}: inclusive axis must certify the same final-source localization exactly once.`)
  } else throw new Error(`${label}: unknown axis-bias decomposition kind.`)
  if (footprintContext) {
    const localGeometry = space === 'unwarped-viewport'
    const region = measured.axisPerspectiveBiasRegionViewportPixels
    if (localGeometry) {
      const [width, height] = footprintContext.unwarpedViewportPixels
      if (!Array.isArray(region) || region.length !== 4) throw new Error(`${label}: a bounded unwarped geometry-bias region is required.`)
      region.forEach((value) => finite(value, label))
      if (region[0] < 0 || region[1] < 0 || region[2] <= 0 || region[3] <= 0 || region[0] + region[2] > width || region[1] + region[3] > height) throw new Error(`${label}: geometry-bias region must be positive and inside the native viewport.`)
    }
    const validateFootprint = (point: readonly [number, number]) => {
      const bounds = imagePlaneSourceFootprintBounds(footprintContext, point, sourceUncertainty, localGeometry ? geometry : 0, label)
      if (localGeometry && (!region || bounds[0] < region[0] || bounds[1] < region[1] || bounds[2] > region[0] + region[2] || bounds[3] > region[1] + region[3])) throw new Error(`${label}: geometry-bias region must contain the entire inverse source-localization footprint plus independent geometry.`)
    }
    if (!Array.isArray(line.sourceLinePixels) || line.sourceLinePixels.length !== 2 || !Array.isArray(measured.edgeRows)) throw new Error(`${label}: source endpoints and measured edge rows are required.`)
    for (const point of line.sourceLinePixels) validateFootprint(point)
    for (const row of measured.edgeRows) {
      const left = finite(row?.left, label), right = finite(row?.right, label), y = finite(row?.y, label)
      validateFootprint([left / 2 + right / 2, y])
    }
  }
}
export const SOURCE_NON_IDENTIFIABLE_FIXED_POLICY = {
  status: 'user-approved-source-non-identifiable',
  scope: 'structural-fixed-part-only',
  authority: 'Allow explicitly unidentified fixed parts',
  interpretation: 'Rendered source-non-identifiable fixed part; not geometric-fidelity passed.',
} as const
export type SourceNonIdentifiableFixedPart = typeof SOURCE_NON_IDENTIFIABLE_FIXED_POLICY & {
  nativePartPath: string
  rectSourcePixels: [number, number, number, number]
  evidence: string
  fixedNativeEvidence: string
}
export interface WitnessBinding {
  sourceVideoId: string
  sourceSha256: string
  sourceImage: SourceImageIdentity
  modelSha256: string
  modelSourceCommit: string
  shotId: string
  viewId: string
  timeSeconds: number
  decodedTimeSeconds: number
  intervalSeconds: [number, number]
  input: SerializedInput
  camera: CameraRecord
  rectSourcePixels: [number, number, number, number]
  presentation: 'native' | 'horizontal-mirror'
  composite: SourceComposite
  imagePlaneWarp: SourceImagePlaneWarp | null
  resolvedImagePlaneWarp: ImagePlaneWarp | null
  sourceLayout: readonly SourceLayoutEntry[]
  partOverrides: readonly PartOverride[]
  constraints: readonly SourceConstraint[]
  continuity: RuntimeWitness['continuity'] | null
  nativeGeometryAssumptions: readonly NativeGeometryAssumption[]
  sourceNonIdentifiableFixedParts: readonly SourceNonIdentifiableFixedPart[]
}
export interface SourceOcclusion {
  kind: 'measured-opaque-human-hand-interior'
  sourceImage: SourceImageIdentity
  polygonSourcePixels: [number, number][]
  uncertaintyPx: number
  evidence: string
}
type SourceExclusion = { partPath: string; evidence: string } & (
  | { reason: 'outside' | 'occluded' | 'absent'; sourceOcclusion?: never }
  | { reason: 'source-occluded'; sourceOcclusion: SourceOcclusion }
)
export interface VisibilityProof {
  binding: WitnessBinding
  sourceVisibleParts: { partPath: string; sourceFeatures: string[]; sourceCoverage: SourceCoverage; evidence: string }[]
  excludedParts: SourceExclusion[]
  unresolvedParts: { partPath: string; reason: string }[]
  sourceNonIdentifiableFixedParts: SourceNonIdentifiableFixedPart[]
  evidence: string
}
export interface RuntimeWitness {
  input: SerializedInput
  unobservedInputFields: InputField[]
  constraints: SourceConstraint[]
  visibilityProof: VisibilityProof
  continuity?: { intervalId: string; evidence: string }
}
export type MechanicalObservation = (
  | { status: 'observed'; input: SerializedInput; visiblePoseCompleteness: 'complete'; visibilityProof: VisibilityProof; runtimeWitness?: never }
  | { status: 'constrained'; input: null; visiblePoseCompleteness: 'complete'; runtimeWitness: RuntimeWitness; visibilityProof?: never }
  | { status: 'unobservable' | 'not-applicable'; input: null; visiblePoseCompleteness?: 'complete' | 'partial'; runtimeWitness?: never; visibilityProof?: never }
) & { evidence: string }
export interface MechanicalProvenance {
  mechanicalProvenance: 'observed' | 'constrained'
  unobservedInputFields: readonly InputField[]
  constraintSummary: readonly SourceConstraint[]
  visibilityProof: VisibilityProof
  continuity: NonNullable<RuntimeWitness['continuity']> | null
  sourceNonIdentifiableFixedParts: readonly SourceNonIdentifiableFixedPart[]
  nativeGeometryAssumptions: readonly NativeGeometryAssumption[]
}

function finite(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label} must be finite.`)
  return value
}
function evidence(value: unknown, label: string): void {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label}: source evidence is required.`)
}
function keys(value: object, required: readonly string[], label: string): void {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).some((key) => !required.includes(key))
    || required.some((key) => !Object.hasOwn(value, key))) throw new Error(`${label}: missing or unknown fields.`)
}
function inputField(value: unknown, label: string): asserts value is InputField {
  if (typeof value !== 'string' || !Object.hasOwn(fieldSet, value)) throw new Error(`${label}: unknown input field ${String(value)}.`)
}
export function inputValue(input: MechanismInput, field: InputField): number | string | null {
  if (field === 'crankTurns' || field === 'gearing' || field === 'magnification') return input[field]
  if (field.startsWith('setup.')) return input.setup[field.slice(6) as keyof MechanismInput['setup']]
  const index = Number(field.slice(field.indexOf('[') + 1, -1))
  return field.startsWith('amplitudes[') ? input.amplitudes[index]! : input.phases[index]!
}
/** No interactive defaults participate in compiling a source input. */
export function compileInput(raw: SerializedInput, label: string): MechanismInput {
  keys(raw, ['crankTurns', 'amplitudes', 'phases', 'gearing', 'magnification', 'setup'], label)
  if (!Array.isArray(raw.amplitudes) || !Array.isArray(raw.phases) || raw.amplitudes.length !== 20 || raw.phases.length !== 20) throw new Error(`${label}: exactly twenty physical stations are required.`)
  if (!['small-large', 'medium-medium', 'large-small'].includes(raw.gearing)) throw new Error(`${label}: unknown gearing.`)
  keys(raw.setup, SETUP_KEYS, `${label}.setup`)
  const setup = {} as MechanismInput['setup']
  for (const key of SETUP_KEYS) {
    const value = raw.setup[key]
    if (key === 'counterHeightM' && value === null) setup.counterHeightM = null
    else setup[key] = finite(value, `${label}.setup.${key}`)
  }
  const amplitudes = new Float64Array(20)
  const phases = new Float64Array(20)
  for (let i = 0; i < 20; i++) {
    const amplitude = finite(raw.amplitudes[i], `${label}.amplitudes[${i}]`)
    if (amplitude < -1 || amplitude > 1) throw new Error(`${label}: amplitude outside [-1,1].`)
    amplitudes[i] = amplitude
    phases[i] = finite(raw.phases[i], `${label}.phases[${i}]`)
  }
  return { crankTurns: finite(raw.crankTurns, `${label}.crankTurns`), amplitudes, phases, gearing: raw.gearing, magnification: finite(raw.magnification, `${label}.magnification`), setup }
}
function interval(minimum: unknown, maximum: unknown, label: string): void {
  if (finite(minimum, label) > finite(maximum, label)) throw new Error(`${label}: reversed interval.`)
}
export function compileWitness(witness: RuntimeWitness, label: string): MechanismInput {
  keys(witness, ['input', 'unobservedInputFields', 'constraints', 'visibilityProof', ...(Object.hasOwn(witness, 'continuity') ? ['continuity'] : [])], label)
  const input = compileInput(witness.input, label)
  if (Object.hasOwn(witness, 'continuity')) {
    keys(witness.continuity!, ['intervalId', 'evidence'], `${label}.continuity`)
    evidence(witness.continuity!.intervalId, label)
    evidence(witness.continuity!.evidence, label)
  }
  if (!Array.isArray(witness.unobservedInputFields) || !Array.isArray(witness.constraints)) throw new Error(`${label}: witness accounting is required.`)
  const accounted = new Set<InputField>()
  const constraintIds = new Set<string>()
  for (const field of witness.unobservedInputFields) {
    inputField(field, label)
    if (accounted.has(field)) throw new Error(`${label}: duplicate accounting for ${field}.`)
    accounted.add(field)
  }
  for (const constraint of witness.constraints) {
    evidence(constraint.evidence, label)
    const identity = constraint.kind === 'input-value' || constraint.kind === 'input-interval' ? `input:${constraint.field}`
      : constraint.kind === 'channel-angle' ? `channel-angle:${constraint.channelIndex}` : constraint.kind
    if (constraintIds.has(identity)) throw new Error(`${label}: duplicate source constraint ${identity}.`)
    constraintIds.add(identity)
    switch (constraint.kind) {
      case 'input-value': {
        keys(constraint, ['kind', 'field', 'value', 'tolerance', 'evidence'], label)
        inputField(constraint.field, label)
        if (finite(constraint.tolerance, label) < 0) throw new Error(`${label}: negative tolerance.`)
        if (constraint.field === 'gearing') {
          if (typeof constraint.value !== 'string' || !['small-large', 'medium-medium', 'large-small'].includes(constraint.value) || constraint.tolerance !== 0) throw new Error(`${label}: gearing needs an exact enum constraint.`)
        } else if (constraint.value === null) {
          if (constraint.field !== 'setup.counterHeightM' || constraint.tolerance !== 0 || !witness.unobservedInputFields.includes(constraint.field)) throw new Error(`${label}: null counter is an exact algorithmic choice and must remain unobserved.`)
          break
        } else finite(constraint.value, label)
        if (accounted.has(constraint.field)) throw new Error(`${label}: duplicate or measured/unobserved accounting for ${constraint.field}.`)
        accounted.add(constraint.field)
        break
      }
      case 'input-interval':
        keys(constraint, ['kind', 'field', 'minimum', 'maximum', 'evidence'], label)
        inputField(constraint.field, label)
        if (constraint.field === 'gearing') throw new Error(`${label}: enum interval is invalid.`)
        interval(constraint.minimum, constraint.maximum, label)
        if (accounted.has(constraint.field)) throw new Error(`${label}: duplicate or measured/unobserved accounting for ${constraint.field}.`)
        accounted.add(constraint.field)
        break
      case 'effective-bank-drive':
        keys(constraint, ['kind', 'minimumTurns', 'maximumTurns', 'winding', 'evidence'], label)
        interval(constraint.minimumTurns, constraint.maximumTurns, label)
        if (!['unwrapped', 'modulo-one'].includes(constraint.winding)) throw new Error(`${label}: unknown bank winding.`)
        break
      case 'channel-angle':
        keys(constraint, ['kind', 'channelIndex', 'minimumRadians', 'maximumRadians', 'winding', 'evidence'], label)
        if (!Number.isInteger(constraint.channelIndex) || constraint.channelIndex < 0 || constraint.channelIndex >= 20) throw new Error(`${label}: invalid physical channel index.`)
        interval(constraint.minimumRadians, constraint.maximumRadians, label)
        if (!['unwrapped', 'modulo-turn'].includes(constraint.winding)) throw new Error(`${label}: unknown channel winding.`)
        break
      case 'paper-travel':
      case 'pen-travel':
        keys(constraint, ['kind', 'minimumMetres', 'maximumMetres', 'evidence'], label)
        interval(constraint.minimumMetres, constraint.maximumMetres, label)
        break
      default: throw new Error(`${label}: unknown source constraint kind.`)
    }
  }
  for (const field of INPUT_FIELDS) if (!accounted.has(field)) throw new Error(`${label}: unaccounted input field ${field}.`)
  if (input.setup.counterHeightM === null && !witness.unobservedInputFields.includes('setup.counterHeightM')) throw new Error(`${label}: auto-calibrated counter must be labelled chosen/unobserved.`)
  return input
}
export function equalRecord(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false
  const aKeys = Object.keys(a)
  const bKeys = Object.keys(b)
  return aKeys.length === bKeys.length && aKeys.every((key) => Object.hasOwn(b, key) && equalRecord((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]))
}
function validateResolvedImagePlaneWarp(warp: ImagePlaneWarp | null, label: string): void {
  if (warp === null) return
  keys(warp, ['kind', 'unwarpedViewportPixels', 'renderToSourcePixels'], label)
  if (warp.kind !== 'homography') throw new Error(`${label}: unknown image-plane warp kind.`)
  if (!Array.isArray(warp.unwarpedViewportPixels) || warp.unwarpedViewportPixels.length !== 2) throw new Error(`${label}: two unwarped viewport dimensions are required.`)
  for (const value of warp.unwarpedViewportPixels) {
    if (finite(value, label) <= 0) throw new Error(`${label}: positive finite unwarped viewport dimensions are required.`)
  }
  if (!Array.isArray(warp.renderToSourcePixels) || warp.renderToSourcePixels.length !== 9) throw new Error(`${label}: a nine-coefficient derived homography is required.`)
  for (const value of warp.renderToSourcePixels) finite(value, label)
}
function validateSourceLayout(expected: Omit<WitnessBinding, 'intervalSeconds'>, label: string): void {
  validateResolvedImagePlaneWarp(expected.resolvedImagePlaneWarp, `${label}.resolvedImagePlaneWarp`)
  if ((expected.imagePlaneWarp === null) !== (expected.resolvedImagePlaneWarp === null)) throw new Error(`${label}: authored and resolved image-plane warp must both be explicit null or both be present.`)
  if (expected.imagePlaneWarp !== null) {
    keys(expected.imagePlaneWarp, ['kind', 'unwarpedViewportPixels', 'cornersSourcePixels', 'sourceImage', 'referenceSourceImage', 'cornerMeasurementEvidence', 'correspondences'], `${label}.imagePlaneWarp`)
    if (expected.imagePlaneWarp.kind !== 'homography'
      || !equalRecord(expected.imagePlaneWarp.unwarpedViewportPixels, expected.resolvedImagePlaneWarp!.unwarpedViewportPixels)
      || !equalRecord(expected.imagePlaneWarp.sourceImage, expected.sourceImage)) throw new Error(`${label}: authored warp must bind its resolved viewport and actual source image.`)
  }
  if (!Array.isArray(expected.sourceLayout) || !expected.sourceLayout.length) throw new Error(`${label}: complete ordered source layout is required.`)
  const viewIds = new Set<string>()
  for (const entry of expected.sourceLayout) {
    keys(entry, ['viewId', 'rectSourcePixels', 'presentation', 'composite', 'resolvedImagePlaneWarp'], `${label}.sourceLayout`)
    evidence(entry.viewId, `${label}.sourceLayout.viewId`)
    if (viewIds.has(entry.viewId)) throw new Error(`${label}: duplicate source layout view.`)
    viewIds.add(entry.viewId)
    if (!Array.isArray(entry.rectSourcePixels) || entry.rectSourcePixels.length !== 4) throw new Error(`${label}: source layout rectangle needs four coordinates.`)
    for (const value of entry.rectSourcePixels) finite(value, label)
    const [x, y, width, height] = entry.rectSourcePixels
    if (x < 0 || y < 0 || width <= 0 || height <= 0
      || x + width > expected.sourceImage.width || y + height > expected.sourceImage.height) throw new Error(`${label}: source layout rectangle exceeds the actual source image.`)
    if (entry.presentation !== 'native' && entry.presentation !== 'horizontal-mirror') throw new Error(`${label}: unknown source layout presentation.`)
    if (entry.composite !== null) {
      const composite = entry.composite
      if (composite.mode === 'opaque') keys(composite, ['mode'], `${label}.sourceLayout.composite`)
      else if (composite.mode === 'crossfade') {
        keys(composite, ['mode', 'groupId', 'imageLayerId', 'opacity'], `${label}.sourceLayout.composite`)
        evidence(composite.groupId, label)
        evidence(composite.imageLayerId, label)
        const opacity = finite(composite.opacity, label)
        if (opacity < 0 || opacity > 1) throw new Error(`${label}: source layout opacity must be between zero and one.`)
      } else throw new Error(`${label}: unknown source layout composite mode.`)
    }
    validateResolvedImagePlaneWarp(entry.resolvedImagePlaneWarp, `${label}.sourceLayout.resolvedImagePlaneWarp`)
    if (entry.viewId === expected.viewId
      && (!equalRecord(entry.rectSourcePixels, expected.rectSourcePixels)
        || entry.presentation !== expected.presentation
        || !equalRecord(entry.composite, expected.composite)
        || !equalRecord(entry.resolvedImagePlaneWarp, expected.resolvedImagePlaneWarp))) throw new Error(`${label}: own source layout entry does not match the visibility binding.`)
  }
  if (!viewIds.has(expected.viewId)) throw new Error(`${label}: source layout omits the bound view.`)
}
function validateSourceOcclusion(mask: SourceOcclusion, image: SourceImageIdentity, label: string): void {
  keys(mask, ['kind', 'sourceImage', 'polygonSourcePixels', 'uncertaintyPx', 'evidence'], label)
  if (mask.kind !== 'measured-opaque-human-hand-interior' || !equalRecord(mask.sourceImage, image)) throw new Error(`${label}: source occlusion needs the exact original image and closed opaque-human-hand kind.`)
  evidence(mask.evidence, label)
  if (finite(mask.uncertaintyPx, label) < 0) throw new Error(`${label}: source mask uncertainty must be nonnegative.`)
  const polygon = mask.polygonSourcePixels
  if (!Array.isArray(polygon) || polygon.length < 3) throw new Error(`${label}: source hand interior needs a convex nondegenerate polygon.`)
  let area2 = 0
  for (let i = 0; i < polygon.length; i++) {
    const point = polygon[i]!
    if (!Array.isArray(point) || point.length !== 2 || point.some((value) => typeof value !== 'number' || !Number.isFinite(value))
      || point[0] < 0 || point[1] < 0 || point[0] > image.width || point[1] > image.height) throw new Error(`${label}: source hand polygon exceeds the original image.`)
    for (let j = 0; j < i; j++) if (point[0] === polygon[j]![0] && point[1] === polygon[j]![1]) throw new Error(`${label}: duplicate source hand polygon vertex.`)
  }
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i]!, b = polygon[(i + 1) % polygon.length]!
    area2 += a[0] * b[1] - a[1] * b[0]
  }
  if (!Number.isFinite(area2) || area2 === 0) throw new Error(`${label}: degenerate source hand polygon.`)
  const orientation = Math.sign(area2)
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i]!, b = polygon[(i + 1) % polygon.length]!
    for (const point of polygon) if (orientation * ((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])) < 0) throw new Error(`${label}: source hand polygon must be convex and non-self-intersecting.`)
  }
}
export function validateVisibilityProof(proof: VisibilityProof, expected: Omit<WitnessBinding, 'intervalSeconds'>, anchors: readonly { id: string; partPath?: string }[], label: string): void {
  keys(proof, ['binding', 'sourceVisibleParts', 'excludedParts', 'unresolvedParts', 'sourceNonIdentifiableFixedParts', 'evidence'], label)
  evidence(proof.evidence, label)
  keys(expected, ['sourceVideoId', 'sourceSha256', 'sourceImage', 'modelSha256', 'modelSourceCommit', 'shotId', 'viewId', 'timeSeconds', 'decodedTimeSeconds', 'input', 'camera', 'rectSourcePixels', 'presentation', 'composite', 'imagePlaneWarp', 'resolvedImagePlaneWarp', 'sourceLayout', 'partOverrides', 'constraints', 'continuity', 'nativeGeometryAssumptions', 'sourceNonIdentifiableFixedParts'], `${label}.expected`)
  validateNativeGeometryAssumptions(expected.nativeGeometryAssumptions)
  keys(proof.binding, [...Object.keys(expected), 'intervalSeconds'], `${label}.binding`)
  for (const key of Object.keys(expected) as (keyof typeof expected)[]) {
    if (!equalRecord(proof.binding[key], expected[key])) throw new Error(`${label}: visibility proof does not bind ${key}.`)
  }
  const image = expected.sourceImage
  const digestKey = image.pixelFormat === 'bgr8' ? 'sha256Bgr8' : image.pixelFormat === 'gray8' ? 'sha256Gray8' : null
  if (!digestKey) throw new Error(`${label}: unknown decoded image pixel format.`)
  keys(image, ['frameIndex', 'width', 'height', 'sourceSha256', 'pixelFormat', digestKey], `${label}.sourceImage`)
  const digest = image[digestKey as keyof SourceImageIdentity]
  if (typeof digest !== 'string' || !/^[a-f0-9]{64}$/.test(digest) || image.sourceSha256 !== expected.sourceSha256
    || image.width !== 1920 || image.height !== 1080 || !Number.isInteger(image.frameIndex) || image.frameIndex < 0) throw new Error(`${label}: invalid decoded source image identity.`)
  validateSourceLayout(expected, label)
  const bounds = proof.binding.intervalSeconds
  if (!Array.isArray(bounds) || bounds.length !== 2) throw new Error(`${label}: missing visibility interval.`)
  interval(bounds[0], bounds[1], label)
  if (expected.timeSeconds < bounds[0] || expected.timeSeconds > bounds[1]) throw new Error(`${label}: frame is outside its visibility interval.`)
  if (!Array.isArray(proof.sourceVisibleParts) || !Array.isArray(proof.excludedParts) || !Array.isArray(proof.unresolvedParts) || !Array.isArray(proof.sourceNonIdentifiableFixedParts)) throw new Error(`${label}: complete four-bucket native visibility census is required.`)
  if (proof.unresolvedParts.length) throw new Error(`${label}: unresolved native parts cannot establish a complete visible pose.`)
  const paths = new Set<string>()
  for (const part of [...proof.sourceVisibleParts, ...proof.excludedParts]) {
    if (typeof part.partPath !== 'string' || !part.partPath.includes('/') || /[*?]/.test(part.partPath) || paths.has(part.partPath)) throw new Error(`${label}: invalid or duplicate qualified native path.`)
    paths.add(part.partPath)
    evidence(part.evidence, label)
  }
  for (const part of proof.sourceNonIdentifiableFixedParts) {
    keys(part, [...Object.keys(SOURCE_NON_IDENTIFIABLE_FIXED_POLICY), 'nativePartPath', 'rectSourcePixels', 'evidence', 'fixedNativeEvidence'], label)
    for (const key of Object.keys(SOURCE_NON_IDENTIFIABLE_FIXED_POLICY) as (keyof typeof SOURCE_NON_IDENTIFIABLE_FIXED_POLICY)[]) {
      if (part[key] !== SOURCE_NON_IDENTIFIABLE_FIXED_POLICY[key]) throw new Error(`${label}: unapproved source-non-identifiable fixed-part ${key}.`)
    }
    if (typeof part.nativePartPath !== 'string' || !part.nativePartPath.includes('/') || /[*?]/.test(part.nativePartPath) || paths.has(part.nativePartPath)) throw new Error(`${label}: invalid or overlapping source-non-identifiable fixed native path.`)
    paths.add(part.nativePartPath)
    evidence(part.evidence, label)
    evidence(part.fixedNativeEvidence, label)
    if (!Array.isArray(part.rectSourcePixels) || part.rectSourcePixels.length !== 4) throw new Error(`${label}: source-non-identifiable region needs four coordinates.`)
    part.rectSourcePixels.forEach((value) => finite(value, label))
    const [x, y, w, h] = part.rectSourcePixels
    if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > image.width || y + h > image.height) throw new Error(`${label}: source-non-identifiable region exceeds the actual source image.`)
  }
  if (!paths.size) throw new Error(`${label}: empty native visibility census.`)
  for (const part of proof.sourceVisibleParts) {
    keys(part, ['partPath', 'sourceFeatures', 'sourceCoverage', 'evidence'], label)
    if (!Array.isArray(part.sourceFeatures) || !part.sourceFeatures.length) throw new Error(`${label}: independent source features are required.`)
    for (const feature of part.sourceFeatures) evidence(feature, label)
    const coverage = part.sourceCoverage
    if (coverage.kind === 'rigid-native-attachment') {
      keys(coverage, ['kind', 'attachedToPartPath'], label)
      if (!part.partPath.startsWith(`${coverage.attachedToPartPath}/`) || !proof.sourceVisibleParts.some((candidate) => candidate.partPath === coverage.attachedToPartPath)) throw new Error(`${label}: rigid attachment needs its evidenced native ancestor.`)
      continue
    }
    const idKey = coverage.kind === 'landmarks' ? 'landmarkIds' : coverage.kind === 'native-line-checks' ? 'lineCheckIds' : coverage.kind === 'source-contour' ? 'contourCheckIds' : null
    if (!idKey) throw new Error(`${label}: unknown source coverage kind.`)
    keys(coverage, ['kind', idKey], label)
    const ids = (coverage as unknown as Record<string, unknown>)[idKey]
    if (!Array.isArray(ids) || !ids.length || new Set(ids).size !== ids.length) throw new Error(`${label}: unique independent source coverage IDs are required.`)
    for (const id of ids) {
      evidence(id, label)
      if (coverage.kind === 'landmarks' && !anchors.some((anchor) => anchor.id === id && anchor.partPath === part.partPath)) throw new Error(`${label}: unknown native source landmark ${id}.`)
    }
  }
  for (const part of proof.excludedParts) {
    keys(part, ['partPath', 'reason', 'evidence', ...(part.reason === 'source-occluded' ? ['sourceOcclusion'] : [])], label)
    if (part.reason === 'source-occluded') {
      validateSourceOcclusion(part.sourceOcclusion, image, label)
      if (expected.timeSeconds !== expected.decodedTimeSeconds || bounds[0] !== expected.decodedTimeSeconds || bounds[1] !== expected.decodedTimeSeconds) throw new Error(`${label}: source hand mask requires one exact decoded-exposure point certificate, not a held/interpolated interval.`)
    } else if (!['outside', 'occluded', 'absent'].includes(part.reason)) throw new Error(`${label}: unknown native exclusion reason.`)
  }
}
function inInterval(value: number, minimum: number, maximum: number, period: number, label: string): void {
  // A modulo interval may straddle its seam by expressing the upper bound above one period.
  const lifted = period === 0 ? value : value + Math.ceil((minimum - value) / period) * period
  if (!Number.isFinite(value) || lifted < minimum - 1e-12 || lifted > maximum + 1e-12) throw new Error(`${label}: actual physical solution violates its source constraint (${value}).`)
}
export function evaluateConstraints(input: MechanismInput, pose: MechanismPose, constraints: readonly SourceConstraint[], label: string): void {
  for (const constraint of constraints) {
    switch (constraint.kind) {
      case 'input-value': {
        const actual = inputValue(input, constraint.field)
        if (typeof actual === 'number' && typeof constraint.value === 'number') inInterval(actual, constraint.value - constraint.tolerance, constraint.value + constraint.tolerance, 0, label)
        else if (actual !== constraint.value) throw new Error(`${label}: input-value constraint contradicts the rendered input.`)
        break
      }
      case 'input-interval': {
        const actual = inputValue(input, constraint.field)
        if (typeof actual !== 'number') throw new Error(`${label}: numeric interval cannot constrain an algorithmic/enum choice.`)
        inInterval(actual, constraint.minimum, constraint.maximum, 0, label)
        break
      }
      case 'effective-bank-drive':
        // Recover the bank coordinate from the actual solved physical H1 angle;
        // never duplicate the solver's engagement/offset branch equation.
        inInterval((pose.channelAnglesRad[19]! - input.phases[19]!) / physicalChannelAngle(1, 19), constraint.minimumTurns, constraint.maximumTurns, constraint.winding === 'modulo-one' ? 1 : 0, label)
        break
      case 'channel-angle': inInterval(pose.channelAnglesRad[constraint.channelIndex]!, constraint.minimumRadians, constraint.maximumRadians, constraint.winding === 'modulo-turn' ? 2 * Math.PI : 0, label); break
      case 'paper-travel': inInterval(pose.platenTravelM, constraint.minimumMetres, constraint.maximumMetres, 0, label); break
      case 'pen-travel': inInterval(pose.magnifier.penTravelM, constraint.minimumMetres, constraint.maximumMetres, 0, label); break
      default: throw new Error(`${label}: unknown source constraint kind.`)
    }
  }
}
export function solveSourceInput(input: MechanismInput, constraints: readonly SourceConstraint[], pose = createMechanismPose()): MechanismPose {
  solveMechanism(input, pose)
  evaluateConstraints(input, pose, constraints, 'Source-visible reconstruction')
  return pose
}
