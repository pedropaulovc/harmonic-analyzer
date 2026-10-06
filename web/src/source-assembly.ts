import nativeInventory from '../content/v39-source/native-inventory.json'
import { BINDINGS } from './bindings'
import { MECHANISM_DATA } from './mechanics-data'
import type { PartOverride, Point3, Quaternion4 } from './scene'

/**
 * Source display/attachment state is NOT the operating mechanism's 51 inputs.
 * Only released v39 bodies and the two existing genuine T18 instances occur here.
 * Source: jfH-NbsmvD4 setup 43..74, service 170..230, photos 234..285,
 * pen assembly 565..649; approved CAD 81539e53 / raw 60a62a2e.
 *
 * Runtime contract: on EVERY view/state change, Machine.update first restores
 * every native part, performs the normal operating solve, then calls this solver
 * with those baseline world matrices and applies its existing simultaneous world
 * override block. Never feed last view's overridden matrices back into this
 * solver. Operating emits no overrides; it does not restore an already-mutated
 * scene by itself. The machine's normal reset is the sole restoration authority.
 * No geometry, topology, material, scale, camera or raster tolerance is changed.
 */
export interface SourceAssemblyProvenance {
  kind: 'chosen-feasible'
  videoId: 'jfH-NbsmvD4'
  frameIndex: number
  evidence: string
  /** Explicitly unknown source DOFs, not claims of recovered 3D history. */
  unobservedDegreesOfFreedom: readonly string[]
}
/** World pose of the named domain's native reference body, not an arbitrary mesh. */
export interface SourceRigidPose {
  positionMetres: Point3
  quaternion: Quaternion4
}
export type SourceAxialAttachment =
  | { attachment: 'installed' }
  | { attachment: 'withdrawing' | 'inserting'; travelMetres: number }
  | { attachment: 'held'; pose: SourceRigidPose }
export interface SourceCrankAssembly {
  /** MHA-024 tapered pin + its ring; NOT MHA-138 arm/hub seam key. */
  pin: SourceAxialAttachment
  /** MHA-137 reference; MHA-138 and the eye/anchor screw remain on this carrier. */
  carrier: SourceAxialAttachment
  /** The released keeper mesh is a monolithic drape, not 68 articulated links. */
  keeper?: { loopPose: SourceRigidPose; connectorPose: SourceRigidPose }
}
export type SourceRetainingNut =
  | { attachment: 'threaded'; releaseTurns: number }
  | { attachment: 'held'; pose: SourceRigidPose }
export interface SourceHangerAssembly {
  attachment: 'latched' | 'unlatched' | 'open' | 'returning'
  swingRad: number
  /** Rigid root-hinge gauge at the two actual rivets; not an elastic leaf solve. */
  hookReleaseRad: number
}
export type SourceGearId = 'T24' | 'T12' | 'T18-upper' | 'T18-crank'
export type SourceGearAttachment =
  | { attachment: 'upper' | 'crank'; phaseRad: number }
  | { attachment: 'upper-withdrawing' | 'crank-withdrawing' | 'upper-inserting' | 'crank-inserting'; phaseRad: number; travelMetres: number }
  | { attachment: 'held' | 'stored'; pose: SourceRigidPose }
export interface SourceGearAssembly {
  /** All four genuine bodies remain accounted for, including removed/held gears. */
  members: Readonly<Record<SourceGearId, SourceGearAttachment>>
}
export type SourceChainContact =
  | { kind: 'held'; joint: number; positionMetres: Point3 }
  | { kind: 'sprocket'; joint: number; gear: SourceGearId; tooth: number }
export interface SourceChainAssembly {
  attachment: 'slack-on-sprockets' | 'held-off-sprockets' | 'reinstalling'
  /** Exactly 68 hinge positions, in SOURCE_CHAIN_PART_PATHS connectivity order. */
  jointsMetres: readonly Point3[]
  /** Actual parallel hinge axes: a freely posed plane, not independent link roll. */
  planeNormal: Point3
  contacts: readonly SourceChainContact[]
}
export interface SourceToolCalibration {
  /** Chosen physical zero on the native 200 mm rule, NOT the engraved zero. */
  zeroAtStickMetres: number
}
export type SourceMeasuringTool =
  | { attachment: 'held' | 'withdrawn'; stickPose: SourceRigidPose; stopAtStickMetres: number; calibration: SourceToolCalibration }
  | { attachment: 'on-rocker'; station: number; quaternion: Quaternion4; stopAtStickMetres: number; calibration: SourceToolCalibration }
  | { attachment: 'bar-against-stop'; station: number; barSide: 'local-x-min' | 'local-x-max'; barHeightMetres: number; clockRad: number; stopAtStickMetres: number; calibration: SourceToolCalibration }
export interface SourcePenAssembly {
  rod: SourceAxialAttachment
  /** Native authored block yaw is 45deg; this is a relative rotation about the
   * rod CENTRE line (local z=2.5mm), never about a camera or the rod corner. */
  yawDeltaRad: number
  vBlock: { attachment: 'rod' } | { attachment: 'held'; pose: SourceRigidPose }
  frame: { attachment: 'v-block' } | { attachment: 'inserting'; travelMetres: number } | { attachment: 'held'; pose: SourceRigidPose }
  marker: { attachment: 'frame' } | { attachment: 'inserting'; travelMetres: number } | { attachment: 'held'; pose: SourceRigidPose }
  /** A withdrawn rod releases its wire tie; the fixed hanger is not withdrawn. */
  wire: { attachment: 'connected' } | { attachment: 'released'; pose: SourceRigidPose }
}
export type SourceGearPhotoPair = 'T24-T12' | 'T18-T18' | 'T12-T24'
export interface SourceGearPhotograph {
  pair: SourceGearPhotoPair | 'four-gears'
  /** Explicit chosen world placement of the frontal display coordinate frame. */
  displayPose: SourceRigidPose
  /** Four-part photograph has no measured centres in the pair receipt. */
  fourGearPoses?: Readonly<Record<SourceGearId, SourceRigidPose>>
}
export type SourceAssemblyState =
  | { kind: 'operating' }
  | {
    kind: 'source-assembly'
    provenance: SourceAssemblyProvenance
    crank?: SourceCrankAssembly
    retainingNut?: SourceRetainingNut
    hanger?: SourceHangerAssembly
    gears?: SourceGearAssembly
    chain?: SourceChainAssembly
    measuringTool?: SourceMeasuringTool
    pen?: SourcePenAssembly
    /** Genuine photograph subject scope only; all bodies still enter capture census. */
    photograph?: SourceGearPhotograph
  }
export interface SourceAssemblyContext {
  readonly partPaths: readonly string[]
  /** Exact copied current normal-solve world matrix; available only inside the
   * immediate Machine.update provider, never a retained/live matrix reference. */
  readWorldMatrix(partPath: string, out: Float64Array): boolean
  readVisibility(partPath: string, mode?: 'self' | 'effective'): boolean | null
  /** Exact current sprocketAt seat, selected from the actually mounted visible
   * native wheel, including root transforms; never an inactive T12/T24 body. */
  readGearSeatWorldMatrix(seat: 'upper' | 'crank', out: Float64Array): boolean
  readSeatedGearPartPath(seat: 'upper' | 'crank'): string | null
}
export interface CompiledSourceAssembly {
  readonly state: SourceAssemblyState
  readonly requiredPartPaths: readonly string[]
  /** Canonical physical descriptor, excluding support witness/provenance only. */
  readonly physicalKey: string
}
const ROOT = 'ha-harmonic-analyzer'
const DRIVE = `${ROOT}/dt-drive-train/`
const PAPER = `${ROOT}/pd-paper-drive/`
const PEN = `${ROOT}/pn-pen/`
const STICK = `${ROOT}/ha-measuring-stick-1`
const STOP = `${ROOT}/ha-measuring-stick-stop-1`
const HUB = `${DRIVE}dt-crank-hub-1`
const PIN = `${DRIVE}dt-crank-pin-1`
const NUT = `${PAPER}pd-transgear-thumbnut-1`
const ROD = `${PEN}pn-pen-rod-1`
const BLOCK = `${PEN}pn-pen-v-block-1`
const FRAME = `${PEN}pn-pen-frame-1`
const MARKER = `${PEN}pn-pen-marker-1`
const WIRE = `${PEN}pn-pen-wire-1`
const SPARE = `${PAPER}pd-transgear-removable-3`
const GEAR_IDS: readonly SourceGearId[] = ['T24', 'T12', 'T18-upper', 'T18-crank']
/** Sole declaration of the two genuine existing Scene/template instances. */
export const NATIVE_RUNTIME_INSTANCES: Readonly<Record<'upperMedium' | 'crankMedium', Readonly<{
  partPath: string
  templatePartPath: string
  localGeometryBinding: 'shared-decoded-native-template-attributes-and-index'
}>>> = Object.freeze({
  upperMedium: Object.freeze({ partPath: `${SPARE}@upper`, templatePartPath: SPARE, localGeometryBinding: 'shared-decoded-native-template-attributes-and-index' }),
  crankMedium: Object.freeze({ partPath: `${SPARE}@crank`, templatePartPath: SPARE, localGeometryBinding: 'shared-decoded-native-template-attributes-and-index' }),
})
export const SOURCE_GEAR_PART_PATHS: Readonly<Record<SourceGearId, string>> = Object.freeze({
  T24: `${PAPER}pd-transgear-removable-1`, T12: `${PAPER}pd-transgear-removable-2`,
  'T18-upper': NATIVE_RUNTIME_INSTANCES.upperMedium.partPath, 'T18-crank': NATIVE_RUNTIME_INSTANCES.crankMedium.partPath,
})
const GEAR_SEATS = ['upper', 'crank'] as const
const REST = new Map(nativeInventory.inventory.map(row => [row.path, row.world as readonly number[]]))
const NATIVE_PATHS = Object.freeze(nativeInventory.inventory.map(row => row.path))
if (nativeInventory.sha256 !== MECHANISM_DATA.provenance.modelSha256
  || nativeInventory.source.sourceCommit !== MECHANISM_DATA.provenance.sourceCommit
  || nativeInventory.identity.mapSha256 !== MECHANISM_DATA.provenance.nativeIdentityMapSha256
  || NATIVE_PATHS.length !== 457 || REST.size !== 457) throw new Error('Source assembly requires the exact released v39 native inventory, not an alias/rest fallback.')
function bindingGroup(id: string): readonly string[] {
  const binding = BINDINGS.find(value => value.id === id)
  if (!binding) throw new Error(`Source assembly has no canonical binding ${id}.`)
  const paths = NATIVE_PATHS.filter(path => binding.pattern.test(path))
  if (paths.length !== binding.expected) throw new Error(`Source assembly ${id}: native census ${paths.length}/${binding.expected}.`)
  return Object.freeze(paths)
}
const CRANK_CARRIER = Object.freeze([
  HUB, `${DRIVE}dt-crank-arm-1`, `${DRIVE}vn-crank-hub-pin-1`, `${DRIVE}dt-crank-pin-eye-1`,
  `${DRIVE}vn-fillister-screw-1`, `${DRIVE}dt-crank-handle-1`, `${DRIVE}dt-crank-handle-ferrule-1`,
  `${DRIVE}dt-crank-handle-butt-cup-1`, `${DRIVE}dt-crank-handle-pivot-screw-1`,
])
const CRANK_PIN = Object.freeze([PIN, `${DRIVE}dt-crank-pin-ring-1`])
const KEEPER = Object.freeze([`${DRIVE}vn-keeper-chain-1`, `${DRIVE}vn-keeper-chain-link-1`])
const HANGER = Object.freeze([...bindingGroup('paperHanger'), ...bindingGroup('paperKnob').filter(path => path !== NUT), ...bindingGroup('paperFeed')])
const HOOK = `${PAPER}pd-latch-hook-1`
const RIVETS = Object.freeze([`${PAPER}vn-latch-hook-rivet-1`, `${PAPER}vn-latch-hook-rivet-2`])
const FRAME_GROUP = Object.freeze([FRAME, `${PEN}vn-pen-set-screw-1`])
const NATIVE_LINKS = [...MECHANISM_DATA.paperDrive.chain.nativeLinks].sort((a, b) => a.restStationMm - b.restStationMm)
export const SOURCE_CHAIN_PART_PATHS = Object.freeze(NATIVE_LINKS.map(link => link.partPath))
if (NATIVE_LINKS.length !== 68) throw new Error('Source assembly requires exactly 68 native chain links.')
for (let i = 0; i < 68; i++) {
  const link = NATIVE_LINKS[i]!, next = NATIVE_LINKS[(i + 1) % 68]!
  if (link.nextPartPath !== next.partPath || !REST.has(link.partPath)
    || link.partPath.includes('outer') === next.partPath.includes('outer')) throw new Error('Source assembly native chain connectivity/alternation is incompatible.')
}
export const SOURCE_ASSEMBLY_GROUPS = Object.freeze({ crankCarrier: CRANK_CARRIER, crankPin: CRANK_PIN, keeper: KEEPER, hanger: HANGER, penFrame: FRAME_GROUP })
export const OPERATING_SOURCE_ASSEMBLY: CompiledSourceAssembly = Object.freeze({ state: Object.freeze({ kind: 'operating' }), requiredPartPaths: Object.freeze([]), physicalKey: '{"kind":"operating"}' })
const EMPTY_OVERRIDES: readonly PartOverride[] = Object.freeze([])
const CHORD_M = MECHANISM_DATA.paperDrive.chain.pitchMm / 1000
/** Numerical closure tolerance only (0.1 micrometre), NOT a native/raster waiver. */
const CONTACT_EPS_M = 1e-7
const THREAD_PITCH_M = 0.0254 / 20 // Actual MHA-126 1/4-20 UNC.
// Actual MHA-078 stud: tip station23.9mm, 45deg chamfer from6.22mm blank
// to the 1/4-20 basic minor diameter. Last full thread, not nut body length.
const STUD_TIP_CHAMFER_M = (0.00622 - (0.00635 - 1.082532 * THREAD_PITCH_M)) / 2
const NUT_THREAD_RELEASE_M = 0.0239 - STUD_TIP_CHAMFER_M
  - (rest(`${PAPER}pd-transgear-knob-shaft-1`)[14]! - rest(NUT)[14]!)
const ROD_AXIS_LOCAL: Point3 = [0, 0, 0.0024999999441206455]
const ZERO: Point3 = [0, 0, 0]
const X: Point3 = [1, 0, 0]
const Y: Point3 = [0, 1, 0]
const Z: Point3 = [0, 0, 1]
/** Actual raw geometry/datums, not source-measured world coordinates. */
export const SOURCE_ASSEMBLY_DATUMS = Object.freeze({
  rodAxisLocalMetres: ROD_AXIS_LOCAL,
  chainChordMetres: CHORD_M,
  nutThreadReleaseTurns: NUT_THREAD_RELEASE_M / THREAD_PITCH_M,
  stickLengthMetres: 0.20000000298023224,
  stickEngravedZeroMetres: 0.0575,
  stickEngravedDivisionMetres: 0.0142,
  stickUndersideLocalZMetres: 0.003000000026077032,
  /** Midpoint of the actual central native top-edge facet, NOT analytic R800. */
  rockerSupportLocalMetres: [0, 0.016059251502156258, 0] as Point3,
  stopContactLocalMetres: [-0.006000000052154064, 0.010, 0] as Point3,
  gearFaceLocalZMetres: 0.00279999990016222,
  gearOuterRadiusMetres: { T24: 0.02601769007742405, T12: 0.013742903247475624, T18: 0.019905386492609978 },
})
const STOP_ORIGIN_IN_STICK: V3 = [0, 0, 0]
const STOP_CONTACT_IN_STICK: V3 = [0, 0, 0]
const DATUM_WORK: V3 = [0, 0, 0]
point(DATUM_WORK, rest(STOP), ZERO); inversePoint(STOP_ORIGIN_IN_STICK, rest(STICK), DATUM_WORK)
point(DATUM_WORK, rest(STOP), SOURCE_ASSEMBLY_DATUMS.stopContactLocalMetres); inversePoint(STOP_CONTACT_IN_STICK, rest(STICK), DATUM_WORK)
const KEEPER_CONNECTOR_LOCAL_ENDS: readonly Point3[] = [[-0.00285, 0, 0], [0.00285, 0, 0]]
const KEEPER_LOOP_LOCAL_ENDS: readonly V3[] = [[0, 0, 0], [0, 0, 0]]
for (let i = 0; i < 2; i++) {
  point(DATUM_WORK, rest(KEEPER[1]!), KEEPER_CONNECTOR_LOCAL_ENDS[i]!)
  inversePoint(KEEPER_LOOP_LOCAL_ENDS[i]!, rest(KEEPER[0]!), DATUM_WORK)
}
export const SOURCE_GEAR_PHOTO_FRAMING = Object.freeze({
  sourceFrameIndex: 7343, verticalFovDegrees: 28,
  principalPointViewportPixels: [320, 180] as const,
  photographStartSeconds: 234.10053333333335, platenPanelsStartSeconds: 239.30573333333334,
})
/** Source centres and withheld second radii: raw frame7343 (not7393), actual
 * native face centres, chosen frontal depth/clock gauge. Not GPU fit acceptance. */
export const SOURCE_GEAR_PHOTOGRAPHS = Object.freeze({
  'T24-T12': { ids: ['T24', 'T12'] as const, rectSourcePixels: [0, 0, 640, 360] as const,
    centresSourcePixels: [[385.82862393751435, 150.02710774178726], [477.80490600641906, 265.16918844566715]] as const,
    pixelsPerMetre: 2982.5130940843546, cameraDistanceMetres: 0.24205780335663243, secondRadiusResidualPixels: 0.04631723423280931 },
  'T18-T18': { ids: ['T18-upper', 'T18-crank'] as const, rectSourcePixels: [0, 360, 640, 360] as const,
    centresSourcePixels: [[348.694179172351, 484.1643929058663], [440.72778913883207, 599.4312656214497]] as const,
    pixelsPerMetre: 2981.8040999116574, cameraDistanceMetres: 0.24211535830198946, secondRadiusResidualPixels: 0.731935761467355 },
  'T12-T24': { ids: ['T12', 'T24'] as const, rectSourcePixels: [0, 720, 640, 360] as const,
    centresSourcePixels: [[347.8680602382558, 822.7012811867835], [439.55449807387265, 938.1296170405619]] as const,
    pixelsPerMetre: 3024.6784432515965, cameraDistanceMetres: 0.23868341100760115, secondRadiusResidualPixels: 2.032759805465247 },
})

function object(value: unknown, allowed: readonly string[], label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label}: expected an object.`)
  const record = value as Record<string, unknown>
  for (const key of Object.keys(record)) if (!allowed.includes(key)) throw new Error(`${label}: unsupported key ${key}.`)
  return record
}
function number(value: unknown, label: string, min = -Infinity, max = Infinity): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) throw new Error(`${label}: invalid finite physical value.`)
  return value
}
function choice(value: unknown, choices: readonly string[], label: string): string {
  if (typeof value !== 'string' || !choices.includes(value)) throw new Error(`${label}: unsupported state.`)
  return value
}
function vector(value: unknown, n: number, label: string, unit = false): void {
  if (!Array.isArray(value) || value.length !== n) throw new Error(`${label}: invalid dimensions.`)
  let squared = 0
  for (const item of value) { const component = number(item, label); if (unit) squared += component * component }
  if (unit) {
    const length = Math.sqrt(squared)
    if (Math.abs(length - 1) > 1e-8) throw new Error(`${label}: must be unit length.`)
    // Normalize only the owned compiled copy, as the existing override consumer
    // does. Repeated composition must not turn permitted roundoff into scaling.
    for (let i = 0; i < n; i++) value[i] /= length
  }
}
function rigid(value: unknown, label: string): void {
  const pose = object(value, ['positionMetres', 'quaternion'], label)
  vector(pose.positionMetres, 3, label); vector(pose.quaternion, 4, label, true)
}
function axial(value: unknown, label: string): void {
  const state = object(value, ['attachment', 'travelMetres', 'pose'], label)
  const attachment = choice(state.attachment, ['installed', 'withdrawing', 'inserting', 'held'], label)
  if (attachment === 'held') { rigid(state.pose, label); if (state.travelMetres !== undefined) throw new Error(`${label}: held pose cannot have axis travel.`) }
  else if (attachment === 'installed') { if (state.pose !== undefined || state.travelMetres !== undefined) throw new Error(`${label}: installed has no free pose/travel.`) }
  else { number(state.travelMetres, label, 0); if (state.pose !== undefined) throw new Error(`${label}: axis motion cannot have a free pose.`) }
}
function member(value: unknown, label: string, attached: string, maxTravel: number): void {
  const state = object(value, ['attachment', 'travelMetres', 'pose'], label)
  const attachment = choice(state.attachment, [attached, 'inserting', 'held'], label)
  if (attachment === 'held') { rigid(state.pose, label); if (state.travelMetres !== undefined) throw new Error(`${label}: held has no insertion travel.`) }
  else if (attachment === 'inserting') { number(state.travelMetres, label, 0, maxTravel); if (state.pose !== undefined) throw new Error(`${label}: insertion has no free pose.`) }
  else if (state.pose !== undefined || state.travelMetres !== undefined) throw new Error(`${label}: attached has no free pose/travel.`)
}
function freeze(value: unknown): void {
  if (!value || typeof value !== 'object') return
  for (const child of Object.values(value)) freeze(child)
  Object.freeze(value)
}
freeze(SOURCE_ASSEMBLY_DATUMS)
freeze(SOURCE_GEAR_PHOTOGRAPHS)
freeze(SOURCE_GEAR_PHOTO_FRAMING)
// Only states created and deeply frozen by this compiler bypass validation.
// Scene's captured descriptor and Main's re-entered descriptor must be the
// same exact object, not a second rounded normalization/clone.
const COMPILED_STATES = new WeakMap<SourceAssemblyState, CompiledSourceAssembly>()
COMPILED_STATES.set(OPERATING_SOURCE_ASSEMBLY.state, OPERATING_SOURCE_ASSEMBLY)

/** Validate once when loading source data; never accept serialized arbitrary overrides. */
export function compileSourceAssemblyState(value: unknown): CompiledSourceAssembly {
  if (value === undefined) return OPERATING_SOURCE_ASSEMBLY
  if (value && typeof value === 'object') {
    const compiled = COMPILED_STATES.get(value as SourceAssemblyState)
    if (compiled) return compiled
  }
  const initial = object(value, ['kind', 'provenance', 'crank', 'retainingNut', 'hanger', 'gears', 'chain', 'measuringTool', 'pen', 'photograph'], 'Source assembly')
  if (initial.kind === 'operating') {
    if (Object.keys(initial).length !== 1) throw new Error('Operating assembly cannot contain source controls.')
    return OPERATING_SOURCE_ASSEMBLY
  }
  choice(initial.kind, ['source-assembly'], 'Source assembly')
  const record = structuredClone(initial)
  const provenance = object(record.provenance, ['kind', 'videoId', 'frameIndex', 'evidence', 'unobservedDegreesOfFreedom'], 'Assembly provenance')
  if (provenance.kind !== 'chosen-feasible' || provenance.videoId !== 'jfH-NbsmvD4' || !Number.isInteger(number(provenance.frameIndex, 'Assembly source frame', 0, 21189))) throw new Error('Assembly source witness must identify the actual operation video/frame.')
  if (typeof provenance.evidence !== 'string' || !provenance.evidence.trim() || !Array.isArray(provenance.unobservedDegreesOfFreedom) || !provenance.unobservedDegreesOfFreedom.length || provenance.unobservedDegreesOfFreedom.some(value => typeof value !== 'string' || !value.trim())) throw new Error('Assembly must name source evidence and unknown chosen-feasible DOFs.')
  const required = new Set<string>()
  function need(paths: readonly string[]): void { for (const path of paths) required.add(path) }
  if (record.crank !== undefined) {
    const crank = object(record.crank, ['pin', 'carrier', 'keeper'], 'Crank')
    axial(crank.pin, 'Crank pin'); axial(crank.carrier, 'Crank carrier')
    const pin = crank.pin as SourceAxialAttachment, carrier = crank.carrier as SourceAxialAttachment
    if (carrier.attachment !== 'installed' && pin.attachment === 'installed') throw new Error('Withdraw the tapered service pin before withdrawing its carrier.')
    if (carrier.attachment !== 'installed' && pin.attachment !== 'held'
      && pin.attachment !== 'installed' && pin.travelMetres < 0.04055) throw new Error('The actual 45mm tapered pin must clear the 22.25mm hub barrel before carrier withdrawal.')
    if (pin.attachment !== 'installed' || carrier.attachment !== 'installed') {
      const keeper = object(crank.keeper, ['loopPose', 'connectorPose'], 'Keeper rigid-display gauges')
      rigid(keeper.loopPose, 'Keeper loop'); rigid(keeper.connectorPose, 'Keeper connector')
    } else if (crank.keeper !== undefined) throw new Error('Installed crank uses its unchanged native keeper drape.')
    need(CRANK_CARRIER); need(CRANK_PIN); need(KEEPER); need([`${DRIVE}dt-crankshaft-1`])
  }
  if (record.retainingNut !== undefined) {
    const nut = object(record.retainingNut, ['attachment', 'releaseTurns', 'pose'], 'Retaining nut')
    const attachment = choice(nut.attachment, ['threaded', 'held'], 'Retaining nut')
    if (attachment === 'held') { rigid(nut.pose, 'Retaining nut'); if (nut.releaseTurns !== undefined) throw new Error('Held nut cannot have thread advance.') }
    else { number(nut.releaseTurns, 'Nut release turns', 0, NUT_THREAD_RELEASE_M / THREAD_PITCH_M); if (nut.pose !== undefined) throw new Error('Threaded nut cannot have a free pose.') }
    need([NUT, `${PAPER}pd-transgear-knob-shaft-1`])
  }
  if (record.hanger !== undefined) {
    const hanger = object(record.hanger, ['attachment', 'swingRad', 'hookReleaseRad'], 'Hanger')
    choice(hanger.attachment, ['latched', 'unlatched', 'open', 'returning'], 'Hanger')
    number(hanger.swingRad, 'Hanger swing', -Math.PI, Math.PI); number(hanger.hookReleaseRad, 'Hook root-hinge gauge', -Math.PI / 2, Math.PI / 2)
    if (hanger.attachment === 'latched' && (hanger.swingRad !== 0 || hanger.hookReleaseRad !== 0)) throw new Error('Latched hanger must use native engaged pose.')
    if (hanger.attachment !== 'latched' && hanger.hookReleaseRad === 0 && hanger.swingRad === 0) throw new Error('Unlatched hanger must release the native hook/pin contact.')
    if (hanger.swingRad !== 0 && record.chain === undefined) throw new Error('Moving the upper hanger requires an explicit native chain state.')
    need(HANGER); need([NUT, HOOK, `${PAPER}pd-transgear-pivot-spacer-1`]); need(RIVETS); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (record.gears !== undefined) {
    const gears = object(record.gears, ['members'], 'Gear exchange'), members = object(gears.members, GEAR_IDS, 'Gear members')
    let upper = false, crank = false
    for (const id of GEAR_IDS) {
      const gear = object(members[id], ['attachment', 'phaseRad', 'travelMetres', 'pose'], id)
      const attachment = choice(gear.attachment, ['upper', 'crank', 'upper-withdrawing', 'crank-withdrawing', 'upper-inserting', 'crank-inserting', 'held', 'stored'], id)
      if (attachment === 'held' || attachment === 'stored') { rigid(gear.pose, id); if (gear.phaseRad !== undefined || gear.travelMetres !== undefined) throw new Error(`${id}: free gear has no axis controls.`) }
      else {
        number(gear.phaseRad, `${id} clock`)
        if (attachment.includes('-')) number(gear.travelMetres, `${id} withdrawal`, 0)
        else if (gear.travelMetres !== undefined) throw new Error(`${id}: seated gear has no withdrawal.`)
        if (gear.pose !== undefined) throw new Error(`${id}: shaft-attached gear has no free pose.`)
        if (attachment.startsWith('upper')) { if (upper) throw new Error('Two gears cannot occupy the same upper shaft.'); upper = true }
        else { if (crank) throw new Error('Two gears cannot occupy the same crank shaft.'); crank = true }
      }
    }
    if (record.retainingNut === undefined) throw new Error('Gear exchange must state the nut attachment independently.')
    const nut = record.retainingNut as SourceRetainingNut
    if (nut.attachment === 'threaded' && nut.releaseTurns === 0 && Object.values(members).some(value => (value as SourceGearAttachment).attachment.startsWith('upper-'))) throw new Error('Remove/release the retaining nut before withdrawing the upper wheel.')
    need(Object.values(SOURCE_GEAR_PART_PATHS)); need([SPARE, `${DRIVE}dt-crankshaft-1`, `${PAPER}pd-transgear-knob-shaft-1`])
  }
  if (record.chain !== undefined) {
    const chain = object(record.chain, ['attachment', 'jointsMetres', 'planeNormal', 'contacts'], 'Native chain')
    choice(chain.attachment, ['slack-on-sprockets', 'held-off-sprockets', 'reinstalling'], 'Native chain')
    vector(chain.planeNormal, 3, 'Chain hinge normal', true)
    if (!Array.isArray(chain.jointsMetres) || chain.jointsMetres.length !== 68) throw new Error('Native chain requires all 68 joint positions.')
    for (const point of chain.jointsMetres) vector(point, 3, 'Chain hinge')
    if (!Array.isArray(chain.contacts) || !chain.contacts.length) throw new Error('Loose/held chain must declare actual attachment contacts.')
    let held = false, sprocket = false
    for (const contact of chain.contacts) {
      const item = object(contact, ['kind', 'joint', 'positionMetres', 'gear', 'tooth'], 'Chain contact')
      if (!Number.isInteger(number(item.joint, 'Chain joint', 0, 67))) throw new Error('Chain joint must be an integer.')
      if (item.kind === 'held') { vector(item.positionMetres, 3, 'Held chain contact'); held = true; if (item.gear !== undefined || item.tooth !== undefined) throw new Error('Held contact has no sprocket tooth.') }
      else {
        choice(item.kind, ['sprocket'], 'Chain contact'); choice(item.gear, GEAR_IDS, 'Chain gear')
        const teeth = item.gear === 'T24' ? 24 : item.gear === 'T12' ? 12 : 18
        if (!Number.isInteger(number(item.tooth, 'Chain tooth', 0, teeth - 1))) throw new Error('Chain tooth must be an integer.')
        if (item.positionMetres !== undefined) throw new Error('Sprocket contact is computed from actual wheel datum, not a free contact point.')
        sprocket = true
      }
    }
    if (chain.attachment === 'held-off-sprockets' && (!held || sprocket) || chain.attachment === 'slack-on-sprockets' && !sprocket) throw new Error('Chain contact topology disagrees with its attachment state.')
    validateChainPath(chain as unknown as SourceChainAssembly)
    need(SOURCE_CHAIN_PART_PATHS)
    for (const contact of chain.contacts as SourceChainContact[]) if (contact.kind === 'sprocket') need([SOURCE_GEAR_PART_PATHS[contact.gear]])
  }
  if (record.measuringTool !== undefined) {
    const tool = object(record.measuringTool, ['attachment', 'stickPose', 'stopAtStickMetres', 'calibration', 'station', 'quaternion', 'barSide', 'barHeightMetres', 'clockRad'], 'Measuring tool')
    const attachment = choice(tool.attachment, ['held', 'withdrawn', 'on-rocker', 'bar-against-stop'], 'Measuring tool')
    object(tool, attachment === 'held' || attachment === 'withdrawn'
      ? ['attachment', 'stickPose', 'stopAtStickMetres', 'calibration']
      : attachment === 'on-rocker'
        ? ['attachment', 'station', 'quaternion', 'stopAtStickMetres', 'calibration']
        : ['attachment', 'station', 'barSide', 'barHeightMetres', 'clockRad', 'stopAtStickMetres', 'calibration'], 'Measuring tool variant')
    number(tool.stopAtStickMetres, 'Stop centre on real stick', 0, SOURCE_ASSEMBLY_DATUMS.stickLengthMetres)
    const calibration = object(tool.calibration, ['zeroAtStickMetres'], 'Tool contact zero')
    number(calibration.zeroAtStickMetres, 'Chosen contact zero', 0, SOURCE_ASSEMBLY_DATUMS.stickLengthMetres)
    if (attachment === 'held' || attachment === 'withdrawn') rigid(tool.stickPose, 'Stick pose')
    else {
      if (!Number.isInteger(number(tool.station, 'Physical station', 1, 20))) throw new Error('Physical station must be an integer.')
      if (attachment === 'on-rocker') vector(tool.quaternion, 4, 'Stick orientation gauge', true)
      else { choice(tool.barSide, ['local-x-min', 'local-x-max'], 'Bar side'); number(tool.barHeightMetres, 'Actual bar face height', 0, 0.8083000183105469); number(tool.clockRad, 'Two-contact clock gauge') }
      need([`${ROOT}/ch-channel/ch-rocker-arm-${tool.station}`])
      if (attachment === 'bar-against-stop') need([`${ROOT}/ch-channel/ch-amplitude-bar-${tool.station}`])
    }
    need([STICK, STOP])
  }
  if (record.pen !== undefined) {
    const pen = object(record.pen, ['rod', 'yawDeltaRad', 'vBlock', 'frame', 'marker', 'wire'], 'Pen assembly')
    axial(pen.rod, 'Pen rod'); number(pen.yawDeltaRad, 'Native rod-axis yaw', -Math.PI, Math.PI)
    const block = object(pen.vBlock, ['attachment', 'pose'], 'Pen V block'); choice(block.attachment, ['rod', 'held'], 'Pen V block')
    if (block.attachment === 'held') rigid(block.pose, 'Pen V block'); else if (block.pose !== undefined) throw new Error('Attached V block has no free pose.')
    if (block.attachment === 'held' && pen.yawDeltaRad !== 0) throw new Error('Detached V block uses its explicit pose, not an ignored rod-axis yaw.')
    member(pen.frame, 'Pen frame', 'v-block', 0.036); member(pen.marker, 'Pen marker', 'frame', 0.10999999940395355)
    const wire = object(pen.wire, ['attachment', 'pose'], 'Pen wire'); choice(wire.attachment, ['connected', 'released'], 'Pen wire')
    if (wire.attachment === 'released') rigid(wire.pose, 'Pen wire'); else if (wire.pose !== undefined) throw new Error('Connected wire has no free pose.')
    if ((pen.rod as SourceAxialAttachment).attachment !== 'installed' && wire.attachment !== 'released') throw new Error('Release the rod wire tie before withdrawing the square rod from its fixed hanger.')
    need([ROD, BLOCK, MARKER, WIRE, `${PEN}pn-pen-hanger-1`, `${PEN}vn-hanger-screw-1`]); need(FRAME_GROUP)
  }
  if (record.photograph !== undefined) {
    if (Object.keys(record).some(key => !['kind', 'provenance', 'photograph'].includes(key))) throw new Error('Photograph subject scope cannot masquerade as machine disassembly.')
    const photo = object(record.photograph, ['pair', 'displayPose', 'fourGearPoses'], 'Gear photograph')
    choice(photo.pair, ['T24-T12', 'T18-T18', 'T12-T24', 'four-gears'], 'Gear photograph'); rigid(photo.displayPose, 'Photo world gauge')
    if (photo.pair === 'four-gears') {
      const poses = object(photo.fourGearPoses, GEAR_IDS, 'Four native gear poses')
      for (const id of GEAR_IDS) rigid(poses[id], id)
    } else if (photo.fourGearPoses !== undefined) throw new Error('Measured pair views cannot contain unrelated four-gear poses.')
    need(NATIVE_PATHS); need(Object.values(SOURCE_GEAR_PART_PATHS))
  }
  if (!required.size) throw new Error('Source assembly must contain a bounded physical domain; use operating for no-op.')
  for (const path of required) if (!REST.has(path) && !Object.values(SOURCE_GEAR_PART_PATHS).includes(path)) throw new Error(`Source assembly references a missing released native part: ${path}.`)
  freeze(record)
  const physical = { ...record }
  delete physical.provenance
  const compiled = Object.freeze({ state: record as unknown as SourceAssemblyState, requiredPartPaths: Object.freeze([...required]), physicalKey: canonicalPhysicalKey(physical) })
  COMPILED_STATES.set(compiled.state, compiled)
  return compiled
}

function canonicalPhysicalKey(value: unknown, field = ''): string {
  if (!value || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) {
    if (field === 'quaternion') {
      const sign = (value[3] || value[2] || value[1] || value[0]) < 0 ? -1 : 1
      return JSON.stringify(value.map(component => sign * component))
    }
    return `[${value.map(item => canonicalPhysicalKey(item)).join(',')}]`
  }
  const record = value as Record<string, unknown>
  return `{${Object.keys(record).sort().map(key => `${JSON.stringify(key)}:${canonicalPhysicalKey(record[key], key)}`).join(',')}}`
}
/** Stable change-census contract; support evidence changes alone are not motion. */
export function sourceAssemblyPhysicalKey(compiled: CompiledSourceAssembly): string {
  return compiled.physicalKey
}

function validateChainPath(chain: SourceChainAssembly): void {
  const origin = chain.jointsMetres[0]!, normal = chain.planeNormal
  for (let i = 0; i < 68; i++) {
    const a = chain.jointsMetres[i]!, b = chain.jointsMetres[(i + 1) % 68]!
    if (Math.abs(Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) - CHORD_M) > CONTACT_EPS_M) throw new Error(`Native chain chord ${i}, including closure, must remain 6.35mm.`)
    if (Math.abs((a[0] - origin[0]) * normal[0] + (a[1] - origin[1]) * normal[1] + (a[2] - origin[2]) * normal[2]) > CONTACT_EPS_M) throw new Error('Native parallel chain hinges require a single rigidly posed plane.')
  }
}

type V3 = [number, number, number]
type Q4 = [number, number, number, number]
interface Delta { p: V3; q: Q4 }
interface MutableOverride extends PartOverride { worldPositionMetres: V3; worldQuaternion: Q4 }
export interface SourceAssemblyBuffer {
  /** Reused output; consumed immediately, never saved as source evidence. */
  readonly overrides: PartOverride[]
  readonly entries: Map<string, MutableOverride>
  readonly activeEntries: Set<MutableOverride>
  readonly baselineMatrices: Map<string, Float64Array>
  readonly baselineVisibility: Map<string, boolean>
  readonly loadedBaselinePaths: Set<string>
  readonly gearSeats: Readonly<Record<'upper' | 'crank', { readonly matrix: Float64Array; partPath: string | null }>>
  readonly deltas: readonly Delta[]
  readonly points: readonly V3[]
  readonly quaternions: readonly Q4[]
}
export function createSourceAssemblyBuffer(): SourceAssemblyBuffer {
  const paths = [...NATIVE_PATHS, SOURCE_GEAR_PART_PATHS['T18-upper'], SOURCE_GEAR_PART_PATHS['T18-crank']]
  return { overrides: [], entries: new Map<string, MutableOverride>(paths.map(partPath => [partPath, { partPath, worldPositionMetres: [0, 0, 0], worldQuaternion: [0, 0, 0, 1] }])),
    activeEntries: new Set(), baselineMatrices: new Map(paths.map(path => [path, new Float64Array(16)])), baselineVisibility: new Map(), loadedBaselinePaths: new Set(),
    gearSeats: { upper: { matrix: new Float64Array(16), partPath: null }, crank: { matrix: new Float64Array(16), partPath: null } },
    deltas: Array.from({ length: 8 }, () => ({ p: [0, 0, 0] as V3, q: [0, 0, 0, 1] as Q4 })),
    points: Array.from({ length: 7 }, () => [0, 0, 0] as V3), quaternions: Array.from({ length: 4 }, () => [0, 0, 0, 1] as Q4) }
}
function rest(path: string): readonly number[] {
  const matrix = REST.get(path)
  if (!matrix) throw new Error(`Missing exact native rest matrix: ${path}.`)
  return matrix
}
function baseline(out: SourceAssemblyBuffer, path: string): Float64Array {
  const matrix = out.baselineMatrices.get(path)
  if (!matrix || !out.loadedBaselinePaths.has(path)) throw new Error(`Source assembly baseline missing canonical part ${path}.`)
  return matrix
}
function point(out: V3, matrix: ArrayLike<number>, p: Point3): void {
  for (let row = 0; row < 3; row++) out[row] = matrix[row]! * p[0] + matrix[row + 4]! * p[1] + matrix[row + 8]! * p[2] + matrix[row + 12]!
}
function inversePoint(out: V3, m: ArrayLike<number>, p: Point3): void {
  const a = m[0]!, b = m[4]!, c = m[8]!, d = m[1]!, e = m[5]!, f = m[9]!, g = m[2]!, h = m[6]!, i = m[10]!
  const determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
  if (Math.abs(determinant) < 1e-12) throw new Error('Native datum frame is singular.')
  const x = p[0] - m[12]!, y = p[1] - m[13]!, z = p[2] - m[14]!
  out[0] = ((e * i - f * h) * x + (c * h - b * i) * y + (b * f - c * e) * z) / determinant
  out[1] = ((f * g - d * i) * x + (a * i - c * g) * y + (c * d - a * f) * z) / determinant
  out[2] = ((d * h - e * g) * x + (b * g - a * h) * y + (a * e - b * d) * z) / determinant
}
function rotate(out: V3, q: Quaternion4, p: Point3): void {
  const [x, y, z, w] = q, [a, b, c] = p
  const tx = 2 * (y * c - z * b), ty = 2 * (z * a - x * c), tz = 2 * (x * b - y * a)
  out[0] = a + w * tx + y * tz - z * ty; out[1] = b + w * ty + z * tx - x * tz; out[2] = c + w * tz + x * ty - y * tx
}
function multiply(out: Q4, a: Quaternion4, b: Quaternion4): void {
  const [x, y, z, w] = a, [u, v, t, s] = b
  out[0] = w * u + x * s + y * t - z * v; out[1] = w * v - x * t + y * s + z * u
  out[2] = w * t + x * v - y * u + z * s; out[3] = w * s - x * u - y * v - z * t
}
function quaternion(out: Q4, m: ArrayLike<number>): void {
  const sx = Math.hypot(m[0]!, m[1]!, m[2]!), sy = Math.hypot(m[4]!, m[5]!, m[6]!), sz = Math.hypot(m[8]!, m[9]!, m[10]!)
  if (sx === 0 || sy === 0 || sz === 0) throw new Error('Native rigid frame has zero scale.')
  const a = m[0]! / sx, b = m[4]! / sy, c = m[8]! / sz, d = m[1]! / sx, e = m[5]! / sy, f = m[9]! / sz, g = m[2]! / sx, h = m[6]! / sy, i = m[10]! / sz
  const trace = a + e + i
  if (trace > 0) { const s = 2 * Math.sqrt(trace + 1); out[0] = (h - f) / s; out[1] = (c - g) / s; out[2] = (d - b) / s; out[3] = s / 4 }
  else if (a > e && a > i) { const s = 2 * Math.sqrt(1 + a - e - i); out[0] = s / 4; out[1] = (b + d) / s; out[2] = (c + g) / s; out[3] = (h - f) / s }
  else if (e > i) { const s = 2 * Math.sqrt(1 + e - a - i); out[0] = (b + d) / s; out[1] = s / 4; out[2] = (f + h) / s; out[3] = (c - g) / s }
  else { const s = 2 * Math.sqrt(1 + i - a - e); out[0] = (c + g) / s; out[1] = (f + h) / s; out[2] = s / 4; out[3] = (d - b) / s }
  const length = Math.hypot(...out); for (let k = 0; k < 4; k++) out[k] = out[k]! / length
}
function direction(out: V3, m: ArrayLike<number>, local: Point3): void {
  for (let row = 0; row < 3; row++) out[row] = m[row]! * local[0] + m[row + 4]! * local[1] + m[row + 8]! * local[2]
  const length = Math.hypot(...out); if (!length) throw new Error('Native axis has zero length.')
  for (let row = 0; row < 3; row++) out[row] = out[row]! / length
}
function identity(delta: Delta): void { delta.p[0] = delta.p[1] = delta.p[2] = 0; delta.q[0] = delta.q[1] = delta.q[2] = 0; delta.q[3] = 1 }
function around(delta: Delta, origin: Point3, axis: Point3, angle: number, work: V3): void {
  const s = Math.sin(angle / 2); delta.q[0] = axis[0] * s; delta.q[1] = axis[1] * s; delta.q[2] = axis[2] * s; delta.q[3] = Math.cos(angle / 2)
  rotate(work, delta.q, origin); for (let i = 0; i < 3; i++) delta.p[i] = origin[i]! - work[i]!
}
function poseDelta(out: Delta, matrix: ArrayLike<number>, pose: SourceRigidPose, q: Q4, p: V3): void {
  quaternion(q, matrix); q[0] = -q[0]; q[1] = -q[1]; q[2] = -q[2]
  multiply(out.q, pose.quaternion, q)
  point(p, matrix, ZERO); rotate(p, out.q, p)
  for (let i = 0; i < 3; i++) out.p[i] = pose.positionMetres[i]! - p[i]!
}
function entry(out: SourceAssemblyBuffer, path: string): MutableOverride {
  const item = out.entries.get(path)
  if (!item) throw new Error(`Source assembly output has no canonical native body ${path}.`)
  if (!out.activeEntries.has(item)) { delete item.visibility; out.overrides.push(item); out.activeEntries.add(item) }
  return item
}
function transformed(out: SourceAssemblyBuffer, path: string, matrix: ArrayLike<number>, delta: Delta): void {
  const item = entry(out, path); point(item.worldPositionMetres, matrix, ZERO); rotate(item.worldPositionMetres, delta.q, item.worldPositionMetres)
  for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + delta.p[i]!
  quaternion(item.worldQuaternion, matrix); multiply(item.worldQuaternion, delta.q, item.worldQuaternion)
}
function group(out: SourceAssemblyBuffer, paths: readonly string[], delta: Delta): void {
  for (const path of paths) transformed(out, path, baseline(out, path), delta)
}
function axialDelta(out: Delta, state: SourceAxialAttachment, matrix: ArrayLike<number>, localAxis: Point3, sign: number, buffer: SourceAssemblyBuffer): void {
  identity(out)
  if (state.attachment === 'held') poseDelta(out, matrix, state.pose, buffer.quaternions[0]!, buffer.points[0]!)
  else if (state.attachment !== 'installed') { direction(buffer.points[0]!, matrix, localAxis); for (let i = 0; i < 3; i++) out.p[i] = sign * state.travelMetres * buffer.points[0]![i]! }
}
function distance(a: Point3, b: Point3): number { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) }
function mappedPoint(out: V3, matrix: ArrayLike<number>, local: Point3, delta: Delta): void {
  point(out, matrix, local); rotate(out, delta.q, out); for (let i = 0; i < 3; i++) out[i] = out[i]! + delta.p[i]!
}
function align(out: Q4, a: Point3, b: Point3): void {
  let r = 1 + a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  if (r < 1e-12) { r = 0; if (Math.abs(a[0]) > Math.abs(a[2])) { out[0] = -a[1]; out[1] = a[0]; out[2] = 0 } else { out[0] = 0; out[1] = -a[2]; out[2] = a[1] } }
  else { out[0] = a[1] * b[2] - a[2] * b[1]; out[1] = a[2] * b[0] - a[0] * b[2]; out[2] = a[0] * b[1] - a[1] * b[0] }
  out[3] = r; const length = Math.hypot(...out); for (let i = 0; i < 4; i++) out[i] = out[i]! / length
}

/** Pure constraint solve: only the supplied output/scratch buffer is mutated. */
export function solveSourceAssembly(compiled: CompiledSourceAssembly, context: SourceAssemblyContext, out: SourceAssemblyBuffer): readonly PartOverride[] {
  out.overrides.length = 0; out.activeEntries.clear()
  const state = compiled.state
  if (state.kind === 'operating') return EMPTY_OVERRIDES
  out.loadedBaselinePaths.clear()
  for (const path of compiled.requiredPartPaths) {
    const matrix = out.baselineMatrices.get(path)
    if (!matrix || !context.readWorldMatrix(path, matrix)) throw new Error(`Source assembly cannot silently omit canonical native body ${path}.`)
    for (let i = 0; i < 16; i++) if (!Number.isFinite(matrix[i])) throw new Error(`Nonfinite source assembly baseline for ${path}.`)
    const visibility = context.readVisibility(path, 'effective')
    if (visibility === null) throw new Error(`Source assembly baseline visibility missing canonical native body ${path}.`)
    out.baselineVisibility.set(path, visibility)
    out.loadedBaselinePaths.add(path)
  }
  if (state.gears || state.hanger || state.chain?.contacts.some(contact => contact.kind === 'sprocket')) {
    for (const seat of GEAR_SEATS) {
      const current = out.gearSeats[seat]
      current.partPath = context.readSeatedGearPartPath(seat)
      if (!current.partPath || !Object.values(SOURCE_GEAR_PART_PATHS).includes(current.partPath)
        || !context.readGearSeatWorldMatrix(seat, current.matrix)) throw new Error(`Missing genuine current normal ${seat} gear seat.`)
      for (const component of current.matrix) if (!Number.isFinite(component)) throw new Error(`Nonfinite current normal ${seat} gear seat.`)
    }
    if (state.gears && !state.chain) {
      for (const seat of GEAR_SEATS) {
        const member = GEAR_IDS.find(id => state.gears!.members[id].attachment.startsWith(seat))
        const placed = member === undefined ? undefined : state.gears.members[member]
        if (!member || !placed || SOURCE_GEAR_PART_PATHS[member] !== out.gearSeats[seat].partPath
          || placed.attachment !== seat || ('phaseRad' in placed && placed.phaseRad % (2 * Math.PI) !== 0)) throw new Error('Changing a native gear seat requires an explicit native chain state.')
      }
    }
  }
  const hanger = out.deltas[0]!, carrier = out.deltas[1]!, pin = out.deltas[2]!, rod = out.deltas[3]!, block = out.deltas[4]!, frame = out.deltas[5]!, workDelta = out.deltas[6]!, toolDelta = out.deltas[7]!
  const p = out.points, q = out.quaternions
  identity(hanger)
  if (state.hanger) {
    const pivot = baseline(out, `${PAPER}pd-transgear-pivot-spacer-1`)
    point(p[0]!, pivot, ZERO); direction(p[1]!, pivot, Z); around(hanger, p[0]!, p[1]!, state.hanger.swingRad, p[2]!)
    group(out, HANGER, hanger)
    point(p[0]!, baseline(out, RIVETS[0]!), ZERO); point(p[1]!, baseline(out, RIVETS[1]!), ZERO)
    for (let i = 0; i < 3; i++) p[2]![i] = p[1]![i]! - p[0]![i]!
    const length = Math.hypot(...p[2]!); for (let i = 0; i < 3; i++) p[2]![i] = p[2]![i]! / length
    around(workDelta, p[0]!, p[2]!, state.hanger.hookReleaseRad, p[3]!); transformed(out, HOOK, baseline(out, HOOK), workDelta)
    // Rivet centres stay fixed. This is a chosen rigid root-hinge display family,
    // not a claim that the actual spring strip bends as a rigid plate.
  }
  if (state.crank) {
    axialDelta(carrier, state.crank.carrier, baseline(out, HUB), Y, -1, out)
    axialDelta(pin, state.crank.pin, baseline(out, PIN), X, -1, out)
    group(out, CRANK_CARRIER, carrier); group(out, CRANK_PIN, pin)
    if (state.crank.keeper) {
      poseDelta(workDelta, baseline(out, KEEPER[0]!), state.crank.keeper.loopPose, q[0]!, p[0]!); transformed(out, KEEPER[0]!, baseline(out, KEEPER[0]!), workDelta)
      poseDelta(workDelta, baseline(out, KEEPER[1]!), state.crank.keeper.connectorPose, q[0]!, p[0]!); transformed(out, KEEPER[1]!, baseline(out, KEEPER[1]!), workDelta)
      const loop = entry(out, KEEPER[0]!), connector = entry(out, KEEPER[1]!)
      for (let i = 0; i < 2; i++) {
        rotate(p[0]!, loop.worldQuaternion, KEEPER_LOOP_LOCAL_ENDS[i]!); rotate(p[1]!, connector.worldQuaternion, KEEPER_CONNECTOR_LOCAL_ENDS[i]!)
        for (let k = 0; k < 3; k++) { p[0]![k] = p[0]![k]! + loop.worldPositionMetres[k]!; p[1]![k] = p[1]![k]! + connector.worldPositionMetres[k]! }
        if (distance(p[0]!, p[1]!) > CONTACT_EPS_M) throw new Error('Rigid keeper display must preserve both actual loop-link bead seats.')
      }
      // Only actual released keeper geometry is posed. Its internal bead drape
      // cannot change through rigid PartOverride; no hidden flexible mesh is added.
    }
  }
  if (state.retainingNut || state.hanger) {
    const matrix = baseline(out, NUT)
    const nut = state.retainingNut
    if (nut?.attachment === 'held') { poseDelta(workDelta, matrix, nut.pose, q[0]!, p[0]!); transformed(out, NUT, matrix, workDelta) }
    else {
      const turns = nut?.releaseTurns ?? 0
      point(p[0]!, matrix, ZERO); direction(p[1]!, matrix, Y); around(workDelta, p[0]!, p[1]!, turns * 2 * Math.PI, p[2]!)
      for (let i = 0; i < 3; i++) workDelta.p[i] = workDelta.p[i]! + p[1]![i]! * turns * THREAD_PITCH_M
      transformed(out, NUT, matrix, workDelta)
      if (state.hanger) {
        const item = entry(out, NUT); rotate(item.worldPositionMetres, hanger.q, item.worldPositionMetres)
        for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + hanger.p[i]!
        multiply(item.worldQuaternion, hanger.q, item.worldQuaternion)
      }
    }
  }
  if (state.gears) {
    for (const id of GEAR_IDS) {
      const gear = state.gears.members[id], path = SOURCE_GEAR_PART_PATHS[id], item = entry(out, path)
      if (gear.attachment === 'held' || gear.attachment === 'stored') {
        for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = gear.pose.positionMetres[i]!
        for (let i = 0; i < 4; i++) item.worldQuaternion[i] = gear.pose.quaternion[i]!
      } else {
        const upper = gear.attachment.startsWith('upper'), reference = out.gearSeats[upper ? 'upper' : 'crank'].matrix
        identity(workDelta)
        transformed(out, path, reference, workDelta)
        // Additional phase relative to this exact current NORMAL seat, never
        // accumulated from a preceding view or guessed from the shaft origin.
        direction(p[1]!, reference, Z)
        const s = Math.sin(gear.phaseRad / 2); q[0]![0] = p[1]![0] * s; q[0]![1] = p[1]![1] * s; q[0]![2] = p[1]![2] * s; q[0]![3] = Math.cos(gear.phaseRad / 2)
        multiply(item.worldQuaternion, q[0]!, item.worldQuaternion)
        const travel = 'travelMetres' in gear ? gear.travelMetres : 0
        for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! - p[1]![i]! * travel
        if (upper && state.hanger) { rotate(item.worldPositionMetres, hanger.q, item.worldPositionMetres); for (let i = 0; i < 3; i++) item.worldPositionMetres[i] = item.worldPositionMetres[i]! + hanger.p[i]!; multiply(item.worldQuaternion, hanger.q, item.worldQuaternion) }
      }
      item.visibility = 'visible'
    }
    identity(workDelta); transformed(out, SPARE, baseline(out, SPARE), workDelta); entry(out, SPARE).visibility = 'hidden'
  } else if (state.hanger) {
    // Installed current wheels follow the upper carrier; inactive wheel
    // visibility remains the operating solver's, never guessed here.
    const path = out.gearSeats.upper.partPath!
    transformed(out, path, baseline(out, path), hanger)
  }
  if (state.chain) solveChain(state.chain, state.gears, out)
  if (state.measuringTool) solveTool(state.measuringTool, out, toolDelta)
  if (state.pen) {
    const pen = state.pen, rodMatrix = baseline(out, ROD)
    axialDelta(rod, pen.rod, rodMatrix, Y, -1, out); transformed(out, ROD, rodMatrix, rod)
    mappedPoint(p[0]!, rodMatrix, ROD_AXIS_LOCAL, rod); direction(p[1]!, rodMatrix, Y); rotate(p[1]!, rod.q, p[1]!)
    around(workDelta, p[0]!, p[1]!, pen.yawDeltaRad, p[2]!)
    multiply(block.q, workDelta.q, rod.q); rotate(block.p, workDelta.q, rod.p); for (let i = 0; i < 3; i++) block.p[i] = block.p[i]! + workDelta.p[i]!
    if (pen.vBlock.attachment === 'held') poseDelta(block, baseline(out, BLOCK), pen.vBlock.pose, q[0]!, p[0]!)
    transformed(out, BLOCK, baseline(out, BLOCK), block)
    for (let i = 0; i < 3; i++) frame.p[i] = block.p[i]!
    for (let i = 0; i < 4; i++) frame.q[i] = block.q[i]!
    if (pen.frame.attachment === 'held') poseDelta(frame, baseline(out, FRAME), pen.frame.pose, q[0]!, p[0]!)
    else if (pen.frame.attachment === 'inserting') {
      direction(p[0]!, baseline(out, BLOCK), X); rotate(p[0]!, block.q, p[0]!)
      for (let i = 0; i < 3; i++) frame.p[i] = frame.p[i]! + p[0]![i]! * pen.frame.travelMetres
    }
    group(out, FRAME_GROUP, frame)
    if (pen.marker.attachment === 'held') { poseDelta(workDelta, baseline(out, MARKER), pen.marker.pose, q[0]!, p[0]!); transformed(out, MARKER, baseline(out, MARKER), workDelta) }
    else {
      transformed(out, MARKER, baseline(out, MARKER), frame)
      if (pen.marker.attachment === 'inserting') {
        const marker = entry(out, MARKER); direction(p[0]!, baseline(out, MARKER), Y); rotate(p[0]!, frame.q, p[0]!)
        for (let i = 0; i < 3; i++) marker.worldPositionMetres[i] = marker.worldPositionMetres[i]! + p[0]![i]! * pen.marker.travelMetres
      }
    }
    if (pen.wire.attachment === 'released') { poseDelta(workDelta, baseline(out, WIRE), pen.wire.pose, q[0]!, p[0]!); transformed(out, WIRE, baseline(out, WIRE), workDelta) }
  }
  if (state.photograph) solvePhotograph(state.photograph, out)
  for (const override of out.overrides) {
    for (const coordinate of override.worldPositionMetres!) if (!Number.isFinite(coordinate)) throw new Error(`Nonfinite solved native position: ${override.partPath}.`)
    const rotation = override.worldQuaternion!
    if (!rotation.every(Number.isFinite) || Math.abs(Math.hypot(...rotation) - 1) > 1e-8) throw new Error(`Invalid solved native rigid rotation: ${override.partPath}.`)
  }
  return out.overrides
}

function solveChain(chain: SourceChainAssembly, gears: SourceGearAssembly | undefined, out: SourceAssemblyBuffer): void {
  const p = out.points, q = out.quaternions
  for (const contact of chain.contacts) {
    const target = chain.jointsMetres[contact.joint]!
    if (contact.kind === 'held') { if (distance(target, contact.positionMetres) > CONTACT_EPS_M) throw new Error('Chain misses its explicit held contact.'); continue }
    const path = SOURCE_GEAR_PART_PATHS[contact.gear], current = out.entries.get(path)!, posed = out.activeEntries.has(current)
    const attachment = gears?.members[contact.gear].attachment
    const explicitlySeated = attachment !== undefined && attachment !== 'held' && attachment !== 'stored'
    if (!explicitlySeated && (!out.baselineVisibility.get(path)
      || !GEAR_SEATS.some(seat => out.gearSeats[seat].partPath === path))) throw new Error(`Native chain contact requires a genuinely seated visible ${contact.gear} wheel.`)
    const teeth = contact.gear === 'T24' ? 24 : contact.gear === 'T12' ? 12 : 18
    // Approved build_transgear_removable.py35..39: tooth on local+X;
    // the roller pocket following tooth k is at pi/N + k*2pi/N.
    const radius = CHORD_M / (2 * Math.sin(Math.PI / teeth)), angle = Math.PI / teeth + 2 * Math.PI * contact.tooth / teeth
    p[0]![0] = radius * Math.cos(angle); p[0]![1] = radius * Math.sin(angle); p[0]![2] = 0.00139999995008111
    if (posed) { rotate(p[1]!, current.worldQuaternion, p[0]!); for (let i = 0; i < 3; i++) p[1]![i] = p[1]![i]! + current.worldPositionMetres[i]! }
    else point(p[1]!, baseline(out, path), p[0]!)
    if (distance(target, p[1]!) > CONTACT_EPS_M) throw new Error(`Chain joint ${contact.joint} misses native ${contact.gear} roller-pocket contact.`)
    if (posed) rotate(p[2]!, current.worldQuaternion, Z); else direction(p[2]!, baseline(out, path), Z)
    if (Math.abs(Math.abs(p[2]![0] * chain.planeNormal[0] + p[2]![1] * chain.planeNormal[1] + p[2]![2] * chain.planeNormal[2]) - 1) > 1e-8) throw new Error('Wrapped chain hinge axes disagree with the native sprocket axle.')
  }
  // Native hinge0/hinge1 are exactly [0,0,0] and [6.35mm,0,0]
  // (inverse approved release matrices, max chord error4.34e-17m). Local +Z
  // is the pin axis. All 68 actual frames, including their outer/inner offsets,
  // are kept; rest-neighbour gaps are NOT reused as a loose closed path.
  for (let i = 0; i < 68; i++) {
    const path = SOURCE_CHAIN_PART_PATHS[i]!, a = chain.jointsMetres[i]!, b = chain.jointsMetres[(i + 1) % 68]!
    const chord = distance(a, b)
    for (let k = 0; k < 3; k++) p[0]![k] = (b[k]! - a[k]!) / chord
    align(q[0]!, X, p[0]!); rotate(p[1]!, q[0]!, Z)
    const normal = chain.planeNormal
    const cosine = p[1]![0] * normal[0] + p[1]![1] * normal[1] + p[1]![2] * normal[2]
    p[2]![0] = p[1]![1] * normal[2] - p[1]![2] * normal[1]; p[2]![1] = p[1]![2] * normal[0] - p[1]![0] * normal[2]; p[2]![2] = p[1]![0] * normal[1] - p[1]![1] * normal[0]
    const sine = p[0]![0] * p[2]![0] + p[0]![1] * p[2]![1] + p[0]![2] * p[2]![2], half = Math.atan2(sine, cosine) / 2, s = Math.sin(half)
    q[1]![0] = p[0]![0] * s; q[1]![1] = p[0]![1] * s; q[1]![2] = p[0]![2] * s; q[1]![3] = Math.cos(half); multiply(q[2]!, q[1]!, q[0]!)
    const item = entry(out, path)
    for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = a[k]!
    for (let k = 0; k < 4; k++) item.worldQuaternion[k] = q[2]![k]!
    item.visibility = 'visible'
    // Reconfirm the native end without extending/scaling its mesh.
    p[3]![0] = CHORD_M; p[3]![1] = p[3]![2] = 0; rotate(p[3]!, item.worldQuaternion, p[3]!)
    for (let k = 0; k < 3; k++) p[3]![k] = p[3]![k]! + a[k]!
    if (distance(p[3]!, b) > CONTACT_EPS_M) throw new Error('Rigid native chain link cannot meet supplied hinge path.')
  }
}

function solveTool(tool: SourceMeasuringTool, out: SourceAssemblyBuffer, delta: Delta): void {
  const p = out.points, q = out.quaternions, stick = baseline(out, STICK), stop = baseline(out, STOP)
  point(p[0]!, stop, ZERO); inversePoint(p[5]!, stick, p[0]!)
  const stopOriginX = p[5]![0]
  point(p[0]!, stop, SOURCE_ASSEMBLY_DATUMS.stopContactLocalMetres); inversePoint(p[5]!, stick, p[0]!)
  const stopContactX = p[5]![0], stopContactY = p[5]![1], stopContactZ = p[5]![2]
  // Actual native rest stop-to-stick translation .08590000123,.00399999321,
  // .00719999894m and orientation; rail slide uses stick local+X only.
  if (tool.attachment === 'held' || tool.attachment === 'withdrawn') poseDelta(delta, stick, tool.stickPose, q[0]!, p[0]!)
  else {
    const rockerPath = `${ROOT}/ch-channel/ch-rocker-arm-${tool.station}`
    // Contact on the actual central top-edge facet of the released native
    // rocker (the analytic R800 point is 59.25 micrometres below this facet).
    point(p[1]!, baseline(out, rockerPath), SOURCE_ASSEMBLY_DATUMS.rockerSupportLocalMetres)
    p[2]![0] = tool.calibration.zeroAtStickMetres; p[2]![1] = 0.004000000189989805; p[2]![2] = SOURCE_ASSEMBLY_DATUMS.stickUndersideLocalZMetres
    if (tool.attachment === 'on-rocker') for (let k = 0; k < 4; k++) q[2]![k] = tool.quaternion[k]!
    else {
      // Both contacts are on actual released surfaces; unconstrained clock is
      // explicit. Neither an amplitude nor a source-observed zero is invented.
      p[3]![0] = tool.barSide === 'local-x-min' ? 0 : 0.00634999992325902; p[3]![1] = tool.barHeightMetres; p[3]![2] = 0.00317499996162951
      point(p[4]!, baseline(out, `${ROOT}/ch-channel/ch-amplitude-bar-${tool.station}`), p[3]!)
      // Stop's -X contact face, above its slot, mapped into native stick frame.
      p[5]![0] = stopContactX + tool.stopAtStickMetres - stopOriginX - p[2]![0]
      p[5]![1] = stopContactY - p[2]![1]; p[5]![2] = stopContactZ - p[2]![2]
      const localLength = Math.hypot(...p[5]!), worldLength = distance(p[4]!, p[1]!)
      if (Math.abs(localLength - worldLength) > CONTACT_EPS_M || localLength < CONTACT_EPS_M) throw new Error('Chosen tool zero/stop does not close native rocker + bar contacts; choose a feasible zero/depth gauge, not an amplitude rescale.')
      for (let k = 0; k < 3; k++) { p[5]![k] = p[5]![k]! / localLength; p[6]![k] = (p[4]![k]! - p[1]![k]!) / worldLength }
      align(q[2]!, p[5]!, p[6]!)
      const s = Math.sin(tool.clockRad / 2); q[3]![0] = p[6]![0] * s; q[3]![1] = p[6]![1] * s; q[3]![2] = p[6]![2] * s; q[3]![3] = Math.cos(tool.clockRad / 2); multiply(q[2]!, q[3]!, q[2]!)
    }
    // Desired native stick world pose, with its chosen zero resting on rocker.
    rotate(p[3]!, q[2]!, p[2]!); for (let k = 0; k < 3; k++) p[3]![k] = p[1]![k]! - p[3]![k]!
    quaternion(q[0]!, stick); q[0]![0] *= -1; q[0]![1] *= -1; q[0]![2] *= -1; multiply(delta.q, q[2]!, q[0]!)
    point(p[0]!, stick, ZERO); rotate(p[0]!, delta.q, p[0]!); for (let k = 0; k < 3; k++) delta.p[k] = p[3]![k]! - p[0]![k]!
  }
  transformed(out, STICK, stick, delta); transformed(out, STOP, stop, delta)
  direction(p[0]!, stick, X); rotate(p[0]!, delta.q, p[0]!)
  const item = entry(out, STOP), slide = tool.stopAtStickMetres - stopOriginX
  for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = item.worldPositionMetres[k]! + p[0]![k]! * slide
  item.visibility = 'visible'; entry(out, STICK).visibility = 'visible'
}

function solvePhotograph(photo: SourceGearPhotograph, out: SourceAssemblyBuffer): void {
  const delta = out.deltas[6]!, p = out.points
  identity(delta)
  // Subject scope is genuine photograph composition only. Native capture still
  // enumerates every original and generated body with explicit visibility.
  for (const path of NATIVE_PATHS) { transformed(out, path, baseline(out, path), delta); entry(out, path).visibility = 'hidden' }
  for (const id of GEAR_IDS) { const path = SOURCE_GEAR_PART_PATHS[id]; transformed(out, path, baseline(out, path), delta); entry(out, path).visibility = 'hidden' }
  const pair = photo.pair === 'four-gears' ? null : SOURCE_GEAR_PHOTOGRAPHS[photo.pair]
  for (let i = 0; i < (pair ? 2 : 4); i++) {
    const id = pair ? pair.ids[i]! : GEAR_IDS[i]!, path = SOURCE_GEAR_PART_PATHS[id], item = entry(out, path)
    if (pair) {
      const centre = pair.centresSourcePixels[i]!
      p[0]![0] = (centre[0] - 320) / pair.pixelsPerMetre; p[0]![1] = (180 - (centre[1] - pair.rectSourcePixels[1])) / pair.pixelsPerMetre; p[0]![2] = -SOURCE_ASSEMBLY_DATUMS.gearFaceLocalZMetres
      rotate(item.worldPositionMetres, photo.displayPose.quaternion, p[0]!)
      for (let k = 0; k < 4; k++) item.worldQuaternion[k] = photo.displayPose.quaternion[k]!
    } else {
      const local = photo.fourGearPoses![id]; rotate(item.worldPositionMetres, photo.displayPose.quaternion, local.positionMetres); multiply(item.worldQuaternion, photo.displayPose.quaternion, local.quaternion)
    }
    for (let k = 0; k < 3; k++) item.worldPositionMetres[k] = item.worldPositionMetres[k]! + photo.displayPose.positionMetres[k]!
    item.visibility = 'visible'
    // A hidden assembly parent must never erase a selected child.
    let parent = path.slice(0, path.lastIndexOf('/'))
    while (parent !== ROOT && parent) { if (REST.has(parent)) entry(out, parent).visibility = 'visible'; parent = parent.slice(0, parent.lastIndexOf('/')) }
  }
}
