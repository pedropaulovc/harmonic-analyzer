/**
 * Source-backed drive ratios and Fourier sampling utilities.
 *
 * Physical joint closures and all twenty loaded springs live in mechanics.ts;
 * the wire/wheel/pen closure lives in magnifier.ts. Released native geometry
 * and these equations are validated together by the source-data exporter.
 *
 * Source of the ratios: Michelson & Stratton, "A New Harmonic Analyzer" (1898),
 * and the gear train as modelled in `cad/config/machine/gear_train.yaml`.
 *
 *   "The analyzer's gears are sized such that a single full turn of the crank
 *    rotates the first gear of the cylindrical set through 1/80th of a full
 *    rotation, the second 2/80ths, the third 3/80ths, etc."
 *
 * So for cylinder gear k (k = 1..20), after `turns` full crank revolutions:
 *
 *     theta_k = turns * k * 2*PI / 80  =  turns * k * PI / 40
 *
 * Two crank turns therefore advance gear k by k*PI/20 — which is exactly the
 * argument of the k-th cosine in the machine's sum. That identity is why
 * reading the output every two turns performs Fourier *analysis*.
 */

/** Number of channels in this machine. The 80-element variant used 80. */
export const CHANNELS = 20

/** Crank revolutions per unit advance of the Fourier argument x. */
export const TURNS_PER_X_UNIT = 80 / (2 * Math.PI)

/**
 * Angle of harmonic `k` (1-based), not GLB instance k, after crank turns.
 */
export function channelAngle(turns: number, k: number): number {
  return (turns * k * Math.PI) / 40
}

/**
 * Physical CAD station index j (0-based) runs harmonic 20..1, NOT 1..20.
 * Source: cad/config/channels.yaml harmonic_n = cone_teeth/6 = 20-index.
 */
export function physicalChannelAngle(turns: number, index: number): number {
  return channelAngle(turns, CHANNELS - index)
}

/**
 * The Fourier argument x corresponding to a crank position.
 * x advances by PI/20 every two turns, so one full period (2*PI) takes 80 turns.
 */
export function fourierArgument(turns: number): number {
  return (turns * Math.PI) / 40
}

/**
 * The three translational-gearing options. The operator swaps two removable
 * gears (small/medium/large) to set how far the paper travels per crank turn,
 * which is the horizontal scale of the plot.
 */
export type Gearing = 'small-large' | 'medium-medium' | 'large-small'

/**
 * Actual translational drive. Source: cad/scripts/paper_drive_geom.py and
 * build_kinematic_probe.py signed end-to-end gate.
 * T12:T24 chain, T12:T120 disc reduction, DP30 T12 rack pinion (PD 10.16 mm).
 * T18:T18 doubles the fine feed; reversing the T12:T24 pair quadruples it.
 */
export const PAPER_FEED_FINE_M_PER_TURN = (0.5 * (12 / 120) * Math.PI * 10.16) / 1000
export const PAPER_FEED_MULTIPLIER: Readonly<Record<Gearing, number>> = {
  'small-large': 1,
  'medium-medium': 2,
  'large-small': 4,
}

/**
 * Signed global-X rack displacement. Crank angle is global +Z; the same-sense
 * chain feeds an external 12:120 mesh, so +crank turns feed the platen toward -X.
 * Source signed oracle: build_kinematic_probe.py FEED_SIGN=+1, GEAR_SENSE=-1.
 */
export function paperTravelM(turns: number, gearing: Gearing): number {
  return -turns * PAPER_FEED_FINE_M_PER_TURN * PAPER_FEED_MULTIPLIER[gearing]
}

/** Source crossed external 16T:64T mesh: +crank Z drives -cone inclined axis. */
export function coneShaftAngle(turns: number): number {
  return -turns * 2 * Math.PI * (16 / 64)
}

/**
 * The real magnifying clamp radius divided by the 39.85 mm spring-anchor arm.
 * Source: magnifying_lever_geom.clamp_radius_band(12): 66/165/209 mm.
 * These geometric limits supersede a nominal "up to four" animation scale.
 */
export const MAGNIFIER_RATIO_MIN = 66 / 39.85
export const MAGNIFIER_RATIO_BUILT = 165 / 39.85
export const MAGNIFIER_RATIO_MAX = 209 / 39.85

/**
 * Sample a coefficient set from a function, the way an operator does it:
 * the function is sampled at twenty discrete points and each sample becomes
 * one amplitude-bar position.
 */
export function sampleToAmplitudes(f: (x: number) => number, scale = 10): number[] {
  const out: number[] = []
  for (let k = 1; k <= CHANNELS; k++) {
    out.push(scale * f((k * Math.PI) / CHANNELS))
  }
  return out
}

/** Coefficients for a square wave: odd harmonics falling as 1/n. */
export function squareWave(scale = 10): number[] {
  return Array.from({ length: CHANNELS }, (_, i) => {
    const n = i + 1
    return n % 2 === 1 ? scale / n : 0
  })
}
