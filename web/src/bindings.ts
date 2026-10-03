/**
 * Qualified native component names are the articulation authority. GLTFLoader
 * makes duplicate short names unique; scene.ts uses the original userData.name
 * at each hierarchy level, never a glTF node index or a mesh-array position.
 * Source: SOLIDWORKSGLTF release 37 / 1268c23d4a8fc741147c5e09d8d1e45247a71945.
 */
export type Motion =
  | 'crank' | 'cone-spin' | 'cone-swing' | 'cylinder' | 'rod' | 'rocker'
  | 'bar' | 'lever' | 'channel-spring' | 'summing' | 'counter-spring'
  | 'gooseneck' | 'magnifier-fixed' | 'magnifier-clamp' | 'magnifier-rod' | 'magnifier-fixture'
  | 'wheel' | 'lever-wire' | 'pen-wire' | 'pen' | 'platen'
  | 'pinion-swing' | 'pinion-cam' | 'pinion-lever' | 'paper-gear' | 'chain-link'

export interface Binding {
  id: string
  /** Matched against the complete original CAD component path. */
  pattern: RegExp
  kind: 'single' | 'indexed' | 'group'
  motion: Motion
  /** Exact expected component count; partial resolution remains unverified. */
  expected: number
}

const channel = 'ha-harmonic-analyzer/ch-channel/'
const drive = 'ha-harmonic-analyzer/dt-drive-train/'
const magnifier = 'ha-harmonic-analyzer/mg-magnifier/'
const summing = 'ha-harmonic-analyzer/sm-summing/'
const pen = 'ha-harmonic-analyzer/pn-pen/'
const paper = 'ha-harmonic-analyzer/pd-paper-drive/'

function family(id: string, group: string, name: string, motion: Motion): Binding {
  return { id, pattern: new RegExp(`^${group}${name}-(\\d+)$`), kind: 'indexed', motion, expected: 20 }
}

function group(id: string, path: string, names: string, motion: Motion, expected: number): Binding {
  return { id, pattern: new RegExp(`^${path}(?:${names})$`), kind: expected === 1 ? 'single' : 'group', motion, expected }
}

export const BINDINGS: readonly Binding[] = [
  // Pinned release build_drive_train_assembly:4225-4241 locks the anchor screw to the arm.
  group('crank', drive, '(?:dt-crankshaft|dt-crank-arm|dt-crank-hub|vn-crank-hub-pin|dt-crank-pin|dt-crank-pin-eye|dt-crank-handle-pivot-screw|dt-crank-pin-ring|dt-crank-handle|dt-crank-pinion|dt-crank-pinion-pin|vn-fillister-screw)-1', 'crank', 12),
  family('coneGears', drive, 'dt-cone-gear', 'cone-spin'),
  group('coneShaft', drive, '(?:dt-cone-gear-shaft|dt-crank-drive-gear)-1', 'cone-spin', 2),
  // Source build_drive_train_assembly:4505-4555 carries post/fasteners;
  // :3772-3799 makes the lock knob and pivot screw base-bolted statics.
  group('conePlatform', drive, '(?:dt-cone-swing-platform|dt-cone-tip-block|dt-cone-tip-bushing|vn-cone-tip-pinch-screw|vn-cone-tip-adjuster|dt-cone-tip-shim|dt-cone-pivot-post)-1|vn-post-mount-screw-[12]', 'cone-swing', 9),
  family('cylinderGears', drive, 'dt-cylinder-gear', 'cylinder'),
  family('connectingRods', channel, 'ch-connecting-rod', 'rod'),
  family('rockerArms', channel, 'ch-rocker-arm', 'rocker'),
  family('amplitudeBars', channel, 'ch-amplitude-bar', 'bar'),
  family('channelLevers', channel, 'ch-channel-lever', 'lever'),
  family('channelSprings', channel, 'vn-channel-spring-installed-stretch00', 'channel-spring'),
  family('springSupports', channel, 'vn-spring-hook', 'summing'),
  group('summingLever', summing, '(?:sm-summing-lever|vn-boss-hook)-1', 'summing', 2),
  group('gooseneck', summing, 'sm-gooseneck-1', 'gooseneck', 1),
  group('counterSpring', summing, 'vn-counter-spring-1', 'counter-spring', 1),
  group('magnifierLever', magnifier, '(?:mg-magnifying-lever|mg-magnifying-bracket)-1', 'magnifier-fixed', 2),
  group('magnifierClamp', magnifier, '(?:mg-magnifying-clamp|vn-thumb-screw)-1', 'magnifier-clamp', 2),
  group('magnifierRod', magnifier, 'mg-magnifying-vertical-rod-1', 'magnifier-rod', 1),
  group('magnifyingWheel', magnifier, 'mg-magnifying-wheel-1', 'wheel', 1),
  group('leverWire', magnifier, 'mg-lever-wire-1', 'lever-wire', 1),
  group('penWire', pen, 'pn-pen-wire-1', 'pen-wire', 1),
  group('pen', pen, '(?:pn-pen-rod|pn-pen-v-block|pn-pen-frame|pn-pen-marker|vn-pen-set-screw)-1', 'pen', 5),
  // Pinned release build_paper_drive_assembly:1170-1458 locks all 33 native
  // carriage bodies to the platen, including guides, locks and screws 1..22.
  // Flat native siblings: screws 1/2 attach to clip 1, screws 3/4 to clip 2.
  group('platen', paper, '(?:pd-platen|pd-platen-rack|pd-platen-paper)-1|(?:pd-platen-clip|pd-platen-guide)-[12]|pd-guide-lock-[1-4]|vn-fillister-screw-(?:[1-9]|1[0-9]|2[0-2])', 'platen', 33),
  group('alignmentPinionSwing', drive, 'dt-pinion-bracket-[12]|dt-alignment-pinion-1|dt-pinion-arbor-1|vn-pinion-strap-pin-[123]|dt-pinion-handle-1|dt-pinion-arbor-collar-1', 'pinion-swing', 9),
  group('alignmentPinionCam', drive, 'dt-pinion-cam-[12]|dt-pinion-lift-rod-1|dt-pinion-cam-pin-[12]', 'pinion-cam', 5),
  group('alignmentPinionLever', drive, 'dt-pinion-lever-1|dt-pinion-lever-pin-1', 'pinion-lever', 2),
  group('paperGears', paper, '(?:pd-transgear-pinion|pd-transgear-feed-pinion|pd-rack-pinion|pd-transgear-knob-shaft|pd-transgear-thumbnut)-1', 'paper-gear', 5),
  group('paperChain', paper, 'vn-chain-(?:outer|inner)-link-(?:[1-9]|[12][0-9]|3[0-3])', 'chain-link', 66),
  group('paperSprockets', paper, 'pd-transgear-removable-[123]', 'paper-gear', 3),
  group('magnifierFixture', magnifier, 'mg-output-fixture-1', 'magnifier-fixture', 1),
]

/** Physical station number, not harmonic number (instance 1 is harmonic 20). */
export function instanceIndex(name: string, pattern: RegExp): number {
  const captured = name.match(pattern)?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}
