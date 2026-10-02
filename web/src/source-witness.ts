import { createMechanismPose, solveMechanism, type MechanismInput, type MechanismPose } from './mechanics'
import { physicalChannelAngle } from './kinematics'
import type { SourceLayoutEntry } from './scene'
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
export function equalRecord(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false
  const aKeys = Object.keys(a)
  const bKeys = Object.keys(b)
  return aKeys.length === bKeys.length && aKeys.every((key) => Object.hasOwn(b, key) && equalRecord((a as Record<string, unknown>)[key], (b as Record<string, unknown>)[key]))
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
