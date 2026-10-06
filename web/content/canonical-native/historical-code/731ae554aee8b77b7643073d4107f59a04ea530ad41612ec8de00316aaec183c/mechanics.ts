/**
 * Quasistatic twenty-station mechanism, in the released CAD's machine frame.
 *
 * Equations: channel_kinematics.py and error_budget.py:212-294 (the contact is
 * fixed on the rocker during a run); spring_mount_geom.py (catalog inside-hook
 * lengths, loaded seats, initial tension); spring_force_model.py:78-112 (fixed
 * counter screw, migrating upper contact). No Motion-study lumped Z spring or
 * ideal Fourier output is used. All output coordinates are metres, angles are
 * machine-frame radians, loads are N, moments are N m. Private arithmetic is mm.
 *
 * createMechanismPose allocates once. solveMechanism reuses every pose/work
 * buffer. Renderer-owned wheel/pen closure consumes magnifierHookM; this module
 * does not substitute the CAD's rest-linearized yoke for an actual wire law.
 */
import { MECHANISM_DATA } from './mechanics-data'
import {
  CHANNELS, physicalChannelAngle, coneShaftAngle, paperTravelM,
  MAGNIFIER_RATIO_MIN, MAGNIFIER_RATIO_BUILT, MAGNIFIER_RATIO_MAX,
  type Gearing,
} from './kinematics'
import { createMagnifierPose, solveMagnifier, type MagnifierPose } from './magnifier'

export { MECHANISM_DATA } from './mechanics-data'

const C = MECHANISM_DATA.channel
const S = MECHANISM_DATA.spring
const K = MECHANISM_DATA.counter
const KNIFE = MECHANISM_DATA.summing.knifeMm
const M = MECHANISM_DATA.magnifier
const ITERATIONS = 48
const GOLDEN = (Math.sqrt(5) - 1) / 2
const COUNTER_SUPPORT_OMEGA = 2 * Math.PI * K.loopTurns
const COUNTER_SUPPORT_TUBE_MM = K.wireRadiusMm + K.screwRadiusMm
const COUNTER_SUPPORT_HALF_INTERVAL = Math.asin(COUNTER_SUPPORT_TUBE_MM / K.loopMeanRadiusMm) / COUNTER_SUPPORT_OMEGA

export interface MechanismInput {
  /** Full crank revolutions; source gearing, not an arbitrary animation clock. */
  crankTurns: number
  /** Physical station order 20..1; [-1,+1] maps to configured nominal ±88 mm, NOT stick 0..10. */
  amplitudes: Float64Array
  /** Exactly twenty physical cam phase offsets, radians. */
  phases: Float64Array
  gearing: Gearing
  /** Actual knife-to-clamp radius / 39.85 mm lower spring-anchor radius. */
  magnification: number
  setup: {
    /** Gooseneck origin height in metres; null calibrates to level at crank home. */
    counterHeightM: number | null
    /** Readout datum only: never rotates the physical spring system. */
    meanLineAngleRad: number
    /** Signed rack offset from the saved platen origin in metres. */
    platenOffsetM: number
    /** Actual output collar slide along the vertical rod; no automatic wire re-zero. */
    wireFixtureOffsetM: number
    /** Platform Ry swing away from the engaged frame, radians. */
    coneSwingRad: number
    /** Lift-rod eccentric cam Rz angle relative to eccentric-down park, radians. */
    pinionCamRad: number
    /**
     * Cylinder-bank crank-equivalent position held while the cone is out of mesh
     * (coneSwingRad !== 0). Ignored while engaged.
     */
    heldChannelTurns: number
    /**
     * Crank turns the bank lags the crank since the last re-engagement: engaged
     * bank drive is crankTurns - driveCrankOffsetTurns. Re-meshing after a
     * disengaged crank advance sets it to crankTurns - heldChannelTurns, so
     * physical per-channel phases stay untouched. Kinematic coupling only, not
     * tooth-contact dynamics. Interactive default 0; source footage must state it.
     */
    driveCrankOffsetTurns: number
  }
}

/** Reference JSON uses ordinary arrays, never typed-array numeric-key objects. */
export interface SerializedMechanismInput extends Omit<MechanismInput, 'amplitudes' | 'phases'> {
  amplitudes: number[]
  phases: number[]
}

/**
 * Counter level calibration cache for the bank described by work.stations and
 * work.phases. 'stale' MUST be set before either cache array changes.
 */
type CounterCalibration = 'stale' | 'level-at-home'

interface Workspace {
  stations: Float64Array
  phases: Float64Array
  restContactX: Float64Array
  restContactY: Float64Array
  counterCalibration: CounterCalibration
  calibratedGooseneckMm: number
  counterUpperY: number
  counterLowerX: number
  counterLowerY: number
  counterUpperX: number
  counterLengthMm: number
  counterForceN: number
  counterMomentNmm: number
  counterVerticalN: number
  channelMomentNmm: number
  channelVerticalN: number
}

export interface MechanismPose {
  crankAngleRad: number
  coneShaftAngleRad: number
  /** Global Rz rotation about the actual knife ridge, not the part origin. */
  summingAngleRad: number
  summingReadoutAngleRad: number
  equilibriumResidualNm: number
  channelMomentNm: number
  counterMomentNm: number
  knifeVerticalLoadN: number
  /** Signed physical feed magnitude; renderer uses the CAD rack axis. */
  platenTravelM: number
  channelAnglesRad: Float64Array
  rockerAnglesRad: Float64Array
  rodAnglesRad: Float64Array
  barAnglesRad: Float64Array
  leverAnglesRad: Float64Array
  amplitudeStationsM: Float64Array
  /** Packed XYZ, index 3*j, CAD machine frame metres. */
  camCentersM: Float64Array
  rodPinsM: Float64Array
  barFeetM: Float64Array
  barOriginsM: Float64Array
  barPinsM: Float64Array
  barContactsM: Float64Array
  springHoleM: Float64Array
  springLowerM: Float64Array
  springUpperM: Float64Array
  /** Catalog inside-hook length, NOT eye-centre distance or coil-body length. */
  springLengthsM: Float64Array
  springForcesN: Float64Array
  magnifierClampM: Float64Array
  magnifierHookM: Float64Array
  magnifierFixtureM: Float64Array
  magnifier: MagnifierPose
  counter: {
    lengthM: number
    forceN: number
    lowerM: Float64Array
    upperM: Float64Array
    gooseneckHeightM: number
  }
  setup: {
    coneSwingRad: number
    coneSwingPivotM: Float64Array
    pinionCamRad: number
    pinionSwingRad: number
    pinionLeverRad: number
    pinionPivotM: Float64Array
    pinionCentreM: Float64Array
    pinionCamCentreM: Float64Array
    pinionLiftAxisM: Float64Array
  }
  /** Internal stable scratch: callers must not mutate it. */
  readonly _work: Workspace
}

export function createMechanismInput(): MechanismInput {
  return {
    crankTurns: 0,
    amplitudes: new Float64Array(CHANNELS),
    phases: new Float64Array(CHANNELS),
    gearing: 'small-large',
    magnification: MAGNIFIER_RATIO_BUILT,
    setup: {
      counterHeightM: null, meanLineAngleRad: 0, platenOffsetM: 0,
      wireFixtureOffsetM: 0,
      coneSwingRad: 0, pinionCamRad: 0, heldChannelTurns: 0, driveCrankOffsetTurns: 0,
    },
  }
}

export function createMechanismPose(): MechanismPose {
  const work: Workspace = {
    stations: new Float64Array(CHANNELS).fill(NaN),
    phases: new Float64Array(CHANNELS).fill(NaN),
    restContactX: new Float64Array(CHANNELS), restContactY: new Float64Array(CHANNELS),
    counterCalibration: 'stale',
    calibratedGooseneckMm: K.referenceGooseneckYMm,
    counterUpperY: 0, counterLowerX: 0, counterLowerY: 0, counterUpperX: 0,
    counterLengthMm: 0, counterForceN: 0, counterMomentNmm: 0, counterVerticalN: 0,
    channelMomentNmm: 0, channelVerticalN: 0,
  }
  return {
    crankAngleRad: 0, coneShaftAngleRad: 0, summingAngleRad: 0, summingReadoutAngleRad: 0,
    equilibriumResidualNm: 0, channelMomentNm: 0, counterMomentNm: 0,
    knifeVerticalLoadN: 0, platenTravelM: 0,
    channelAnglesRad: new Float64Array(CHANNELS), rockerAnglesRad: new Float64Array(CHANNELS),
    rodAnglesRad: new Float64Array(CHANNELS), barAnglesRad: new Float64Array(CHANNELS),
    leverAnglesRad: new Float64Array(CHANNELS), amplitudeStationsM: new Float64Array(CHANNELS),
    camCentersM: new Float64Array(CHANNELS * 3), rodPinsM: new Float64Array(CHANNELS * 3),
    barFeetM: new Float64Array(CHANNELS * 3), barPinsM: new Float64Array(CHANNELS * 3),
    barOriginsM: new Float64Array(CHANNELS * 3),
    barContactsM: new Float64Array(CHANNELS * 3), springHoleM: new Float64Array(CHANNELS * 3),
    springLowerM: new Float64Array(CHANNELS * 3), springUpperM: new Float64Array(CHANNELS * 3),
    springLengthsM: new Float64Array(CHANNELS), springForcesN: new Float64Array(CHANNELS),
    magnifierClampM: new Float64Array(3), magnifierHookM: new Float64Array(3),
    magnifierFixtureM: new Float64Array(3), magnifier: createMagnifierPose(),
    counter: { lengthM: 0, forceN: 0, lowerM: new Float64Array(3), upperM: new Float64Array(3), gooseneckHeightM: 0 },
    setup: {
      coneSwingRad: 0, coneSwingPivotM: new Float64Array(3), pinionCamRad: 0,
      pinionSwingRad: 0, pinionLeverRad: 0, pinionPivotM: new Float64Array(3),
      pinionCentreM: new Float64Array(3), pinionCamCentreM: new Float64Array(3), pinionLiftAxisM: new Float64Array(3),
    },
    _work: work,
  }
}

/** Bar closure for a prescribed rocker contact, machine XY relative to pivot. */
function barGap(beta: number, contactX: number, contactY: number): number {
  const s = Math.sin(beta)
  const c = Math.cos(beta)
  const tx = contactX - C.contactOffsetMm[0] * c + C.contactOffsetMm[1] * s + C.barLengthMm * s
  const ty = contactY - C.contactOffsetMm[0] * s - C.contactOffsetMm[1] * c + C.barLengthMm * c
  return Math.hypot(tx + C.pivotMm[0] - C.fulcrumMm[0], ty + C.pivotMm[1] - C.fulcrumMm[1]) - C.leverBarArmMm
}

function solveBarBeta(contactX: number, contactY: number): number {
  // Authored channel_kinematics bracket selects the lifting-side branch.
  let lo = -0.3
  let hi = 0.2
  let flo = barGap(lo, contactX, contactY)
  if (flo * barGap(hi, contactX, contactY) > 0) throw new RangeError('Amplitude-bar loop has no bracketed physical closure')
  for (let n = 0; n < ITERATIONS; n++) {
    const mid = (lo + hi) / 2
    const f = barGap(mid, contactX, contactY)
    if ((f < 0) === (flo < 0)) { lo = mid; flo = f } else hi = mid
  }
  return (lo + hi) / 2
}

function prepareStation(station: number, index: number, work: Workspace): void {
  let lo = -0.3
  let hi = 0.2
  const dx = C.contactOffsetMm[0]
  const dy = C.contactOffsetMm[1]
  const xlo = station + dx * Math.cos(lo) - dy * Math.sin(lo)
  const ylo = C.arcCentreYMm - Math.sqrt(C.arcRadiusMm * C.arcRadiusMm - xlo * xlo)
  let flo = barGap(lo, xlo, ylo)
  const xhi = station + dx * Math.cos(hi) - dy * Math.sin(hi)
  const yhi = C.arcCentreYMm - Math.sqrt(C.arcRadiusMm * C.arcRadiusMm - xhi * xhi)
  if (flo * barGap(hi, xhi, yhi) > 0) throw new RangeError('Amplitude foot runs off the physical rocker closure')
  for (let n = 0; n < ITERATIONS; n++) {
    const mid = (lo + hi) / 2
    const x = station + dx * Math.cos(mid) - dy * Math.sin(mid)
    const y = C.arcCentreYMm - Math.sqrt(C.arcRadiusMm * C.arcRadiusMm - x * x)
    const f = barGap(mid, x, y)
    if ((f < 0) === (flo < 0)) { lo = mid; flo = f } else hi = mid
  }
  const beta = (lo + hi) / 2
  const x = station + dx * Math.cos(beta) - dy * Math.sin(beta)
  work.restContactX[index] = x
  work.restContactY[index] = C.arcCentreYMm - Math.sqrt(C.arcRadiusMm * C.arcRadiusMm - x * x)
}

function solveChannel(theta: number, index: number, pose: MechanismPose): void {
  const work = pose._work
  const lobe = theta - C.camHomeRad
  const cx = C.camShaftMm[0] - C.eccentricityMm * Math.sin(lobe)
  const cy = C.camShaftMm[1] + C.eccentricityMm * Math.cos(lobe)
  const ax = cx - C.pivotMm[0]
  const ay = cy - C.pivotMm[1]
  const d = Math.hypot(ax, ay)
  const radius2 = C.rodPinMm[0] * C.rodPinMm[0] + C.rodPinMm[1] * C.rodPinMm[1]
  const a = (radius2 - C.rodLengthMm * C.rodLengthMm + d * d) / (2 * d)
  const h2 = radius2 - a * a
  if (h2 < 0 || d === 0) throw new RangeError('Cam/rod/rocker triangle cannot close')
  const h = Math.sqrt(h2)
  const px = (a * ax + h * ay) / d
  const py = (a * ay - h * ax) / d
  let rocker = Math.atan2(py, px) - Math.atan2(C.rodPinMm[1], C.rodPinMm[0])
  if (rocker > Math.PI) rocker -= 2 * Math.PI
  else if (rocker < -Math.PI) rocker += 2 * Math.PI
  const rs = Math.sin(rocker)
  const rc = Math.cos(rocker)
  const kx = work.restContactX[index]! * rc - work.restContactY[index]! * rs
  const ky = work.restContactX[index]! * rs + work.restContactY[index]! * rc
  const beta = solveBarBeta(kx, ky)
  const bs = Math.sin(beta)
  const bc = Math.cos(beta)
  const footX = C.pivotMm[0] + kx - C.contactOffsetMm[0] * bc + C.contactOffsetMm[1] * bs
  const footY = C.pivotMm[1] + ky - C.contactOffsetMm[0] * bs - C.contactOffsetMm[1] * bc
  const topX = footX + C.barLengthMm * bs
  const topY = footY + C.barLengthMm * bc
  const phi = Math.atan2(topY - C.fulcrumMm[1], C.fulcrumMm[0] - topX)
  const holeX = C.fulcrumMm[0] - C.leverSpringArmMm * Math.cos(phi)
  const holeY = C.fulcrumMm[1] + C.leverSpringArmMm * Math.sin(phi)
  const z = C.stationZ0Mm + C.stationPitchMm * index
  const midZ = z + C.midplaneOffsetMm
  const p = index * 3
  pose.channelAnglesRad[index] = theta
  pose.rockerAnglesRad[index] = rocker
  pose.rodAnglesRad[index] = -Math.atan2(C.pivotMm[0] + px - cx, C.pivotMm[1] + py - cy)
  pose.barAnglesRad[index] = -beta
  pose.leverAnglesRad[index] = -phi
  pose.camCentersM[p] = cx / 1000; pose.camCentersM[p + 1] = cy / 1000; pose.camCentersM[p + 2] = (z + C.rodDepthOffsetMm) / 1000
  pose.rodPinsM[p] = (C.pivotMm[0] + px) / 1000; pose.rodPinsM[p + 1] = (C.pivotMm[1] + py) / 1000; pose.rodPinsM[p + 2] = midZ / 1000
  pose.barContactsM[p] = (C.pivotMm[0] + kx) / 1000; pose.barContactsM[p + 1] = (C.pivotMm[1] + ky) / 1000; pose.barContactsM[p + 2] = midZ / 1000
  pose.barFeetM[p] = footX / 1000; pose.barFeetM[p + 1] = footY / 1000; pose.barFeetM[p + 2] = midZ / 1000
  pose.barOriginsM[p] = (footX + C.barWidthMm / 2 * bc) / 1000
  pose.barOriginsM[p + 1] = (footY - C.barWidthMm / 2 * bs) / 1000
  pose.barOriginsM[p + 2] = (midZ - C.barWidthMm / 2) / 1000
  pose.barPinsM[p] = topX / 1000; pose.barPinsM[p + 1] = topY / 1000; pose.barPinsM[p + 2] = midZ / 1000
  pose.springHoleM[p] = holeX / 1000; pose.springHoleM[p + 1] = holeY / 1000; pose.springHoleM[p + 2] = midZ / 1000
}

/** Exact two-loop circular-wire support seed from spring_mount_geom.py:218-238. */
function counterSupportOffset(ux: number, uy: number): number {
  const halfInterval = COUNTER_SUPPORT_HALF_INTERVAL
  let minimum = Infinity
  for (let loop = 0; loop < 2; loop++) {
    const centre = (loop === 0 ? 1 : 5) / (4 * K.loopTurns)
    let lo = centre - halfInterval
    let hi = centre + halfInterval
    let left = hi - GOLDEN * (hi - lo)
    let right = lo + GOLDEN * (hi - lo)
    let fl = supportLimit(left, ux, uy)
    let fr = supportLimit(right, ux, uy)
    for (let n = 0; n < ITERATIONS; n++) {
      if (fl < fr) {
        hi = right; right = left; fr = fl
        left = hi - GOLDEN * (hi - lo); fl = supportLimit(left, ux, uy)
      } else {
        lo = left; left = right; fl = fr
        right = lo + GOLDEN * (hi - lo); fr = supportLimit(right, ux, uy)
      }
    }
    minimum = Math.min(minimum, fl, fr)
  }
  return minimum
}

function supportLimit(t: number, ux: number, uy: number): number {
  const theta = Math.PI / 2 - COUNTER_SUPPORT_OMEGA * t
  const z = -K.loopHalfRiseMm + K.loopRiseMm * t
  const radial = K.loopMeanRadiusMm * Math.sin(theta)
  return uy * K.loopMeanRadiusMm * Math.cos(theta) + ux * z - Math.sqrt(Math.max(0, COUNTER_SUPPORT_TUBE_MM * COUNTER_SUPPORT_TUBE_MM - radial * radial))
}

const COUNTER_VERTICAL_SUPPORT_OFFSET_MM = counterSupportOffset(0, 1)

function counterMoment(angle: number, gooseneckMm: number, work: Workspace): void {
  const c = Math.cos(angle)
  const s = Math.sin(angle)
  const rx = K.anchorMm[0] - KNIFE[0]
  const ry = K.anchorMm[1] - KNIFE[1]
  const x = rx * c - ry * s
  const y = rx * s + ry * c
  const anchorX = KNIFE[0] + x
  const anchorY = KNIFE[1] + y
  const dx = K.upperEyeXMm - anchorX
  const screwY = gooseneckMm + K.gooseneckArmYMm
  let upperY = screwY - COUNTER_VERTICAL_SUPPORT_OFFSET_MM
  let converged = false
  for (let n = 0; n < 12; n++) {
    const dy = upperY - anchorY
    const span = Math.hypot(dx, dy)
    const next = screwY - counterSupportOffset(dx / span, dy / span)
    if (Math.abs(next - upperY) < 1e-11) { upperY = next; converged = true; break }
    upperY = next
  }
  if (!converged) throw new RangeError('Counter-spring upper contact did not converge')
  const dy = upperY - anchorY
  const span = Math.hypot(dx, dy)
  const ux = dx / span
  const uy = dy / span
  const length = span - K.lowerSeatOffsetMm + K.insideDiameterMm
  const force = K.initialTensionN + K.rateNPerMm * (length - K.freeLengthMm)
  work.counterUpperY = upperY
  work.counterUpperX = K.upperEyeXMm
  work.counterLowerX = anchorX + ux * K.lowerSeatOffsetMm
  work.counterLowerY = anchorY + uy * K.lowerSeatOffsetMm
  work.counterLengthMm = length
  work.counterForceN = force
  work.counterMomentNmm = force * (x * uy - y * ux)
  work.counterVerticalN = force * uy
}

function channelMoment(angle: number, pose: MechanismPose, writePose: boolean): void {
  const work = pose._work
  const c = Math.cos(angle)
  const s = Math.sin(angle)
  const rx = S.anchorMm[0] - KNIFE[0]
  const ry = S.anchorMm[1] - KNIFE[1]
  const x = rx * c - ry * s
  const y = rx * s + ry * c
  const anchorX = KNIFE[0] + x
  const anchorY = KNIFE[1] + y
  let total = 0
  let vertical = 0
  for (let j = 0; j < CHANNELS; j++) {
    const p = j * 3
    const hx = pose.springHoleM[p]! * 1000
    const hy = pose.springHoleM[p + 1]! * 1000
    const dx = hx - anchorX
    const dy = hy - anchorY
    const span = Math.hypot(dx, dy)
    const ux = dx / span
    const uy = dy / span
    const length = span - S.lowerSeatOffsetMm - S.upperSeatDropMm + S.insideDiameterMm
    const force = S.initialTensionN + S.rateNPerMm * (length - S.freeLengthMm)
    total += force * (x * uy - y * ux)
    vertical += force * uy
    if (writePose) {
      if (length < S.freeLengthMm - 1e-6 || length > S.maximumLengthMm + 1e-6 || force > S.maximumForceN + 1e-6) {
        throw new RangeError(`Channel ${j + 1} spring exceeds its catalog extension/load branch`)
      }
      pose.springLengthsM[j] = length / 1000
      pose.springForcesN[j] = force
      pose.springLowerM[p] = (anchorX + ux * S.lowerSeatOffsetMm) / 1000
      pose.springLowerM[p + 1] = (anchorY + uy * S.lowerSeatOffsetMm) / 1000
      pose.springLowerM[p + 2] = pose.springHoleM[p + 2]!
      pose.springUpperM[p] = (hx - ux * S.upperSeatDropMm) / 1000
      pose.springUpperM[p + 1] = (hy - uy * S.upperSeatDropMm) / 1000
      pose.springUpperM[p + 2] = pose.springHoleM[p + 2]!
    }
  }
  work.channelMomentNmm = total
  work.channelVerticalN = vertical
}

/** Source setup: slide the counter until the current bank is level at crank home. */
function calibrateCounter(pose: MechanismPose): void {
  const work = pose._work
  channelMoment(0, pose, false)
  const wanted = work.channelMomentNmm
  let lo: number = K.freeLengthMm
  let hi: number = Math.min(K.maximumLengthMm, K.freeLengthMm + (K.maximumForceN - K.initialTensionN) / K.rateNPerMm)
  const rx = K.anchorMm[0] - KNIFE[0]
  const ry = K.anchorMm[1] - KNIFE[1]
  const sideX = K.upperEyeXMm - K.anchorMm[0]
  for (let n = 0; n <= ITERATIONS; n++) {
    const length = n === 0 ? lo : n === 1 ? hi : (lo + hi) / 2
    const span = length - K.insideDiameterMm + K.lowerSeatOffsetMm
    const ux = sideX / span
    const uy = Math.sqrt(1 - ux * ux)
    const force = K.initialTensionN + K.rateNPerMm * (length - K.freeLengthMm)
    const magnitude = -force * (rx * uy - ry * ux)
    if (n === 0 && wanted < magnitude) throw new RangeError('Counter preload exceeds the bank moment at the free-length bound')
    if (n === 1 && wanted > magnitude) throw new RangeError('Counter cannot balance all twenty stations within its catalog maximum load')
    if (n >= 2) {
      if (magnitude < wanted) lo = length; else hi = length
    }
  }
  const span = (lo + hi) / 2 - K.insideDiameterMm + K.lowerSeatOffsetMm
  const ux = sideX / span
  const uy = Math.sqrt(1 - ux * ux)
  const eyeY = K.anchorMm[1] + uy * span
  work.calibratedGooseneckMm = eyeY + counterSupportOffset(ux, uy) - K.gooseneckArmYMm
}

/** Mutate the stable pose; errors describe a real unclosed or overtravelled mechanism. */
export function solveMechanism(input: MechanismInput, pose: MechanismPose): void {
  if (!Number.isFinite(input.crankTurns) || input.amplitudes.length !== CHANNELS || input.phases.length !== CHANNELS) {
    throw new RangeError('Mechanism input needs a finite crank position and exactly twenty amplitudes/phases')
  }
  if (!Number.isFinite(input.magnification) || input.magnification < MAGNIFIER_RATIO_MIN || input.magnification > MAGNIFIER_RATIO_MAX) {
    throw new RangeError('Magnifier clamp is outside its physical rod/collar travel')
  }
  if (!Number.isFinite(input.setup.meanLineAngleRad) || !Number.isFinite(input.setup.platenOffsetM)
      || !Number.isFinite(input.setup.heldChannelTurns) || !Number.isFinite(input.setup.driveCrankOffsetTurns)) {
    throw new RangeError('Setup coordinates must be finite')
  }
  // Validate every channel before touching the persistent station/phase cache,
  // so a rejected input cannot leave a half-updated bank behind a valid calibration.
  for (let j = 0; j < CHANNELS; j++) {
    const amplitude = input.amplitudes[j]!
    if (!Number.isFinite(amplitude) || amplitude < -1 || amplitude > 1 || !Number.isFinite(input.phases[j]!)) {
      throw new RangeError(`Channel ${j + 1} needs a coefficient in [-1,+1] and a finite phase`)
    }
  }
  const work = pose._work
  for (let j = 0; j < CHANNELS; j++) {
    const station = input.amplitudes[j]! * C.maximumStationMm
    const phase = input.phases[j]!
    pose.amplitudeStationsM[j] = station / 1000
    if (station !== work.stations[j]) {
      work.counterCalibration = 'stale'
      prepareStation(station, j, work)
      work.stations[j] = station
    }
    if (phase !== work.phases[j]) {
      work.counterCalibration = 'stale'
      work.phases[j] = phase
    }
  }
  if (input.setup.counterHeightM === null && work.counterCalibration === 'stale') {
    for (let j = 0; j < CHANNELS; j++) solveChannel(input.phases[j]!, j, pose)
    calibrateCounter(pose)
    work.counterCalibration = 'level-at-home'
  }
  const driveTurns = input.setup.coneSwingRad === 0
    ? input.crankTurns - input.setup.driveCrankOffsetTurns
    : input.setup.heldChannelTurns
  for (let j = 0; j < CHANNELS; j++) solveChannel(physicalChannelAngle(driveTurns, j) + input.phases[j]!, j, pose)
  const gooseY = input.setup.counterHeightM === null ? work.calibratedGooseneckMm : input.setup.counterHeightM * 1000
  if (!Number.isFinite(gooseY)) throw new RangeError('Counter setting must be a finite gooseneck height')
  // Find the stable root around the saved level frame. Expanding the bracket is
  // necessary for legitimate signed bank settings; no scalar gain replaces it.
  let lo = -0.01
  let hi = 0.01
  channelMoment(lo, pose, false); counterMoment(lo, gooseY, work)
  let flo = work.channelMomentNmm + work.counterMomentNmm
  channelMoment(hi, pose, false); counterMoment(hi, gooseY, work)
  let fhi = work.channelMomentNmm + work.counterMomentNmm
  for (let n = 0; flo * fhi > 0 && n < 5; n++) {
    lo *= 2; hi *= 2
    channelMoment(lo, pose, false); counterMoment(lo, gooseY, work); flo = work.channelMomentNmm + work.counterMomentNmm
    channelMoment(hi, pose, false); counterMoment(hi, gooseY, work); fhi = work.channelMomentNmm + work.counterMomentNmm
  }
  if (!(flo >= 0 && fhi <= 0)) throw new RangeError('No stable knife-contact equilibrium is bracketed for this counter setting')
  for (let n = 0; n < ITERATIONS; n++) {
    const mid = (lo + hi) / 2
    channelMoment(mid, pose, false); counterMoment(mid, gooseY, work)
    const residual = work.channelMomentNmm + work.counterMomentNmm
    if (residual > 0) lo = mid; else hi = mid
  }
  const angle = (lo + hi) / 2
  channelMoment(angle, pose, true); counterMoment(angle, gooseY, work)
  if (work.counterLengthMm < K.freeLengthMm || work.counterLengthMm > K.maximumLengthMm || work.counterForceN > K.maximumForceN + 1e-6) {
    throw new RangeError('Counter spring exceeds its catalog extension/load branch')
  }
  pose.crankAngleRad = input.crankTurns * 2 * Math.PI
  pose.coneShaftAngleRad = coneShaftAngle(input.crankTurns)
  pose.summingAngleRad = angle
  pose.summingReadoutAngleRad = angle - input.setup.meanLineAngleRad
  pose.channelMomentNm = work.channelMomentNmm / 1000
  pose.counterMomentNm = work.counterMomentNmm / 1000
  pose.equilibriumResidualNm = (work.channelMomentNmm + work.counterMomentNmm) / 1000
  pose.knifeVerticalLoadN = work.channelVerticalN + work.counterVerticalN
  pose.platenTravelM = input.setup.platenOffsetM + paperTravelM(input.crankTurns, input.gearing)
  pose.counter.lengthM = work.counterLengthMm / 1000
  pose.counter.forceN = work.counterForceN
  pose.counter.gooseneckHeightM = gooseY / 1000
  pose.counter.lowerM[0] = work.counterLowerX / 1000; pose.counter.lowerM[1] = work.counterLowerY / 1000; pose.counter.lowerM[2] = KNIFE[2] / 1000
  pose.counter.upperM[0] = work.counterUpperX / 1000; pose.counter.upperM[1] = work.counterUpperY / 1000; pose.counter.upperM[2] = KNIFE[2] / 1000
  const radius = input.magnification * MECHANISM_DATA.summing.anchorArmMm
  const clampX = KNIFE[0] + radius
  const clampY = M.clampRestMm[1]
  const hookX = M.hookMm[0] + radius - M.clampRadiusBandMm[1]
  const fixtureOffset = input.setup.wireFixtureOffsetM
  if (!Number.isFinite(fixtureOffset) || fixtureOffset < M.fixtureOffsetRangeM[0] || fixtureOffset > M.fixtureOffsetRangeM[1]) {
    throw new RangeError('Output fixture must remain fully engaged on the cylindrical vertical rod below the clamp')
  }
  const hookY = M.hookMm[1] + fixtureOffset * 1000
  const s = Math.sin(angle)
  const c = Math.cos(angle)
  pose.magnifierClampM[0] = (KNIFE[0] + (clampX - KNIFE[0]) * c - (clampY - KNIFE[1]) * s) / 1000
  pose.magnifierClampM[1] = (KNIFE[1] + (clampX - KNIFE[0]) * s + (clampY - KNIFE[1]) * c) / 1000
  pose.magnifierClampM[2] = M.clampRestMm[2] / 1000
  pose.magnifierHookM[0] = (KNIFE[0] + (hookX - KNIFE[0]) * c - (hookY - KNIFE[1]) * s) / 1000
  pose.magnifierHookM[1] = (KNIFE[1] + (hookX - KNIFE[0]) * s + (hookY - KNIFE[1]) * c) / 1000
  pose.magnifierHookM[2] = M.hookMm[2] / 1000
  const fixtureX = M.fixtureRestMm[0] + radius - M.clampRadiusBandMm[1]
  const fixtureY = M.fixtureRestMm[1] + fixtureOffset * 1000
  pose.magnifierFixtureM[0] = (KNIFE[0] + (fixtureX - KNIFE[0]) * c - (fixtureY - KNIFE[1]) * s) / 1000
  pose.magnifierFixtureM[1] = (KNIFE[1] + (fixtureX - KNIFE[0]) * s + (fixtureY - KNIFE[1]) * c) / 1000
  pose.magnifierFixtureM[2] = M.fixtureRestMm[2] / 1000
  solveMagnifier(pose, pose.magnifier)
  solveSetup(input, pose)
}

function solveSetup(input: MechanismInput, pose: MechanismPose): void {
  const setup = MECHANISM_DATA.setup
  const cone = input.setup.coneSwingRad
  const cam = input.setup.pinionCamRad
  if (!Number.isFinite(cone) || cone < 0 || cone > setup.coneDisengageRad + 1e-12
      || !Number.isFinite(cam) || cam > 0 || cam < setup.pinionEngageCamRad - 1e-12) {
    throw new RangeError('Cone swing or alignment-pinion cam is outside its source-backed setup travel')
  }
  const camX = setup.pinionLiftMm[0] + setup.pinionEccentricityMm * Math.sin(cam)
  const camY = setup.pinionLiftMm[1] - setup.pinionEccentricityMm * Math.cos(cam)
  let lo: number = 0
  let hi: number = setup.pinionEngageSwingRad
  const parkedGap = pinionContactGap(0, camX, camY)
  if (parkedGap < 0) {
    for (let n = 0; n < ITERATIONS; n++) {
      const mid = (lo + hi) / 2
      if (pinionContactGap(mid, camX, camY) < 0) lo = mid; else hi = mid
    }
  } else hi = 0
  const swing = (lo + hi) / 2
  const c = Math.cos(swing)
  const s = Math.sin(swing)
  const dx = setup.pinionParkedMm[0] - setup.pinionPivotMm[0]
  const dy = setup.pinionParkedMm[1] - setup.pinionPivotMm[1]
  pose.setup.coneSwingRad = cone
  pose.setup.pinionCamRad = cam
  pose.setup.pinionSwingRad = swing
  pose.setup.pinionLeverRad = setup.pinionParkedLeverRad + cam
  for (let a = 0; a < 3; a++) {
    pose.setup.coneSwingPivotM[a] = setup.conePivotMm[a]! / 1000
    pose.setup.pinionPivotM[a] = setup.pinionPivotMm[a]! / 1000
    pose.setup.pinionLiftAxisM[a] = setup.pinionLiftMm[a]! / 1000
  }
  pose.setup.pinionCentreM[0] = (setup.pinionPivotMm[0] + dx * c - dy * s) / 1000
  pose.setup.pinionCentreM[1] = (setup.pinionPivotMm[1] + dx * s + dy * c) / 1000
  pose.setup.pinionCentreM[2] = setup.pinionParkedMm[2] / 1000
  pose.setup.pinionCamCentreM[0] = camX / 1000
  pose.setup.pinionCamCentreM[1] = camY / 1000
  pose.setup.pinionCamCentreM[2] = setup.pinionLiftMm[2] / 1000
}

function pinionContactGap(swing: number, camX: number, camY: number): number {
  const setup = MECHANISM_DATA.setup
  const c = Math.cos(swing)
  const s = Math.sin(swing)
  const dx = setup.followerCentreMm[0] - setup.pinionPivotMm[0]
  const dy = setup.followerCentreMm[1] - setup.pinionPivotMm[1]
  const x = setup.pinionPivotMm[0] + dx * c - dy * s
  const y = setup.pinionPivotMm[1] + dx * s + dy * c
  const nx = setup.followerNormal[0] * c - setup.followerNormal[1] * s
  const ny = setup.followerNormal[0] * s + setup.followerNormal[1] * c
  return Math.abs((camX - x) * ny - (camY - y) * nx) - setup.pinionContactRadiiMm
}
