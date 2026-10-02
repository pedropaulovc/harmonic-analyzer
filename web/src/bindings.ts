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

const channel = 'harmonic-analyzer/channel/'
const drive = 'harmonic-analyzer/drive-train/'
const magnifier = 'harmonic-analyzer/magnifier/'
const summing = 'harmonic-analyzer/summing/'
const pen = 'harmonic-analyzer/pen/'
const paper = 'harmonic-analyzer/paper-drive/'

function family(id: string, group: string, name: string, motion: Motion): Binding {
  return { id, pattern: new RegExp(`^${group}${name}-(\\d+)$`), kind: 'indexed', motion, expected: 20 }
}

function group(id: string, path: string, names: string, motion: Motion, expected: number): Binding {
  return { id, pattern: new RegExp(`^${path}(?:${names})$`), kind: expected === 1 ? 'single' : 'group', motion, expected }
}

export const BINDINGS: readonly Binding[] = [
  // Pinned release build_drive_train_assembly:4225-4241 locks the anchor screw to the arm.
  group('crank', drive, '(?:crankshaft|crank-arm|crank-hub|crank-hub-pin|crank-pin|crank-pin-eye|crank-handle-pivot-screw|crank-pin-ring|crank-handle|crank-pinion|crank-pinion-pin|fillister-screw)-1', 'crank', 12),
  family('coneGears', drive, 'cone-gear', 'cone-spin'),
  group('coneShaft', drive, '(?:cone-gear-shaft|crank-drive-gear)-1', 'cone-spin', 2),
  // Source build_drive_train_assembly:4505-4555 carries post/fasteners;
  // :3772-3799 makes the lock knob and pivot screw base-bolted statics.
  group('conePlatform', drive, '(?:cone-swing-platform|cone-tip-block|cone-tip-bushing|cone-tip-pinch-screw|cone-tip-adjuster|cone-tip-shim|cone-pivot-post)-1|post-mount-screw-[12]', 'cone-swing', 9),
  family('cylinderGears', drive, 'cylinder-gear', 'cylinder'),
  family('connectingRods', channel, 'connecting-rod', 'rod'),
  family('rockerArms', channel, 'rocker-arm', 'rocker'),
  family('amplitudeBars', channel, 'amplitude-bar', 'bar'),
  family('channelLevers', channel, 'channel-lever', 'lever'),
  family('channelSprings', channel, 'channel-spring-installed-stretch00', 'channel-spring'),
  family('springSupports', channel, 'spring-hook', 'summing'),
  group('summingLever', summing, '(?:summing-lever|boss-hook)-1', 'summing', 2),
  group('gooseneck', summing, 'gooseneck-1', 'gooseneck', 1),
  group('counterSpring', summing, 'counter-spring-1', 'counter-spring', 1),
  group('magnifierLever', magnifier, '(?:magnifying-lever|magnifying-bracket)-1', 'magnifier-fixed', 2),
  group('magnifierClamp', magnifier, '(?:magnifying-clamp|thumb-screw)-1', 'magnifier-clamp', 2),
  group('magnifierRod', magnifier, 'magnifying-vertical-rod-1', 'magnifier-rod', 1),
  group('magnifyingWheel', magnifier, 'magnifying-wheel-1', 'wheel', 1),
  group('leverWire', magnifier, 'lever-wire-1', 'lever-wire', 1),
  group('penWire', pen, 'pen-wire-1', 'pen-wire', 1),
  group('pen', pen, '(?:pen-rod|pen-v-block|pen-frame|pen-marker|pen-set-screw)-1', 'pen', 5),
  // Pinned release build_paper_drive_assembly:1170-1458 locks all 33 native
  // carriage bodies to the platen, including guides, locks and screws 1..22.
  // Flat native siblings: screws 1/2 attach to clip 1, screws 3/4 to clip 2.
  group('platen', paper, '(?:platen|platen-rack|platen-paper)-1|(?:platen-clip|platen-guide)-[12]|guide-lock-[1-4]|fillister-screw-(?:[1-9]|1[0-9]|2[0-2])', 'platen', 33),
  group('alignmentPinionSwing', drive, 'pinion-bracket-[12]|alignment-pinion-1|pinion-arbor-1|pinion-strap-pin-[123]|pinion-handle-1|pinion-arbor-collar-1', 'pinion-swing', 9),
  group('alignmentPinionCam', drive, 'pinion-cam-[12]|pinion-lift-rod-1|pinion-cam-pin-[12]', 'pinion-cam', 5),
  group('alignmentPinionLever', drive, 'pinion-lever-1|pinion-lever-pin-1', 'pinion-lever', 2),
  group('paperGears', paper, '(?:transgear-pinion|transgear-feed-pinion|rack-pinion|transgear-knob-shaft|transgear-thumbnut)-1', 'paper-gear', 5),
  group('paperChain', paper, 'chain-(?:outer|inner)-link-(?:[1-9]|[12][0-9]|3[0-3])', 'chain-link', 66),
  group('paperSprockets', paper, 'transgear-removable-[123]', 'paper-gear', 3),
  group('magnifierFixture', magnifier, 'output-fixture-1', 'magnifier-fixture', 1),
]

/** Physical station number, not harmonic number (instance 1 is harmonic 20). */
export function instanceIndex(name: string, pattern: RegExp): number {
  const captured = name.match(pattern)?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}
