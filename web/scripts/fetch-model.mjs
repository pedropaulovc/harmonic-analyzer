#!/usr/bin/env node
/**
 * Copy the exported machine GLB into web/public/models/.
 *
 * The GLB is a CAD build artefact (`cad/out/gltf/`, gitignored, produced by
 * `doit export` on the SolidWorks seat), so it is never committed here either —
 * web/public/models/ is gitignored. This script is the one supported way to get
 * it in place, so the path the simulator loads is the same for everyone.
 *
 *   npm run fetch-model                 # from cad/out/gltf
 *   npm run fetch-model -- <path.glb>   # from an explicit file
 */

import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const WEB = resolve(HERE, '..')
const REPO = resolve(WEB, '..')
const SRC_DIR = join(REPO, 'cad', 'out', 'gltf')
const DEST_DIR = join(WEB, 'public', 'models')
const DEST = join(DEST_DIR, 'harmonic-analyzer.glb')

const explicit = process.argv[2]

function pick() {
  if (explicit) {
    if (!existsSync(explicit)) fail(`no such file: ${explicit}`)
    return resolve(explicit)
  }
  if (!existsSync(SRC_DIR)) {
    fail(
      `${SRC_DIR} not found.\n` +
        `Run \`uv run python -m doit export\` on the SolidWorks seat, or download a\n` +
        `release bundle with \`gh release download\` and pass the .glb explicitly.`,
    )
  }
  const candidates = readdirSync(SRC_DIR).filter((f) => f.endsWith('.glb'))
  if (candidates.length === 0) fail(`no .glb files in ${SRC_DIR}`)
  const preferred = candidates.find((f) => f.includes('harmonic-analyzer')) ?? candidates[0]
  return join(SRC_DIR, preferred)
}

function fail(msg) {
  console.error(`xx ${msg}`)
  process.exit(1)
}

const src = pick()
mkdirSync(DEST_DIR, { recursive: true })
copyFileSync(src, DEST)
const mb = (statSync(DEST).size / 1024 / 1024).toFixed(1)
console.log(`   OK  ${src} -> public/models/harmonic-analyzer.glb (${mb} MB)`)
