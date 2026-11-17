#!/usr/bin/env node
/**
 * Put the CAD model at public/models/ha-harmonic-analyzer.glb, deduplicated and
 * Meshopt-compressed (lossless) by optimize-model.mjs.
 *
 *   npm run fetch-model              # gltf/ha-harmonic-analyzer.glb from the release zip below
 *   npm run fetch-model -- raw.glb   # a local export, e.g. ../cad/out/gltf/ha-harmonic-analyzer.glb
 *
 * Only the GLB member of the multi-GB release zip is downloaded, by HTTP range
 * requests. Move to a newer release by changing MODEL_RELEASE; update
 * src/bindings.ts if part names changed and regenerate src/mechanics-data.ts.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { inflateRawSync } from 'node:zlib'
import { optimizeModel } from './optimize-model.mjs'

export const MODEL_RELEASE = 'v49'
const ZIP_URL = `https://github.com/pedropaulovc/harmonic-analyzer/releases/download/${MODEL_RELEASE}/harmonic-analyzer-${MODEL_RELEASE}.zip`
const MEMBER = 'gltf/ha-harmonic-analyzer.glb'
export const MODEL_PATH = fileURLToPath(new URL('../public/models/ha-harmonic-analyzer.glb', import.meta.url))

async function range(spec) {
  const response = await fetch(ZIP_URL, { headers: { Range: `bytes=${spec}` }, signal: AbortSignal.timeout(600_000) })
  if (response.status !== 206) throw new Error(`${ZIP_URL}: range ${spec} returned HTTP ${response.status}`)
  return { bytes: Buffer.from(await response.arrayBuffer()), total: Number(response.headers.get('content-range')?.split('/')[1]) }
}

/** Read one member of a remote zip (zip64 aware) without downloading the archive. */
export async function downloadReleaseGlb() {
  const { total } = await range('0-0')
  const { bytes: tail } = await range(`${Math.max(0, total - 65557)}-${total - 1}`)
  const eocd = tail.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]))
  if (eocd < 0) throw new Error('Release zip has no end-of-central-directory record')
  let directorySize = tail.readUInt32LE(eocd + 12)
  let directoryOffset = tail.readUInt32LE(eocd + 16)
  if (directoryOffset === 0xffffffff && tail.readUInt32LE(eocd - 20) === 0x07064b50) {
    const { bytes: zip64 } = await range(`${Number(tail.readBigUInt64LE(eocd - 12))}-${Number(tail.readBigUInt64LE(eocd - 12)) + 55}`)
    directorySize = Number(zip64.readBigUInt64LE(40))
    directoryOffset = Number(zip64.readBigUInt64LE(48))
  }
  const { bytes: directory } = await range(`${directoryOffset}-${directoryOffset + directorySize - 1}`)
  for (let at = 0; at < directory.length && directory.readUInt32LE(at) === 0x02014b50;) {
    const nameLength = directory.readUInt16LE(at + 28), extraLength = directory.readUInt16LE(at + 30)
    const name = directory.toString('utf8', at + 46, at + 46 + nameLength)
    if (name === MEMBER) {
      const method = directory.readUInt16LE(at + 10)
      const sizes = [directory.readUInt32LE(at + 24), directory.readUInt32LE(at + 20), directory.readUInt32LE(at + 42)]
      // Zip64 extra field: 64-bit values for whichever of size/compressed/offset overflowed, in that order.
      for (let extra = at + 46 + nameLength; extra < at + 46 + nameLength + extraLength; extra += 4 + directory.readUInt16LE(extra + 2)) {
        if (directory.readUInt16LE(extra) !== 1) continue
        let field = extra + 4
        for (let i = 0; i < 3; i++) if (sizes[i] === 0xffffffff) { sizes[i] = Number(directory.readBigUInt64LE(field)); field += 8 }
      }
      const [size, compressedSize, headerOffset] = sizes
      const { bytes: header } = await range(`${headerOffset}-${headerOffset + 29}`)
      const start = headerOffset + 30 + header.readUInt16LE(26) + header.readUInt16LE(28)
      console.log(`Downloading ${MEMBER} from ${MODEL_RELEASE} (${(compressedSize / 1e6).toFixed(0)} MB of a ${(total / 1e9).toFixed(1)} GB zip)…`)
      const { bytes: data } = await range(`${start}-${start + compressedSize - 1}`)
      const glb = method === 0 ? data : method === 8 ? inflateRawSync(data) : null
      if (!glb || glb.length !== size) throw new Error(`Unsupported or corrupt zip member ${MEMBER} (method ${method})`)
      return glb
    }
    at += 46 + nameLength + extraLength + directory.readUInt16LE(at + 32)
  }
  throw new Error(`${MEMBER} is not in ${ZIP_URL}`)
}

export async function fetchModel(source) {
  const raw = source ? await readFile(source) : await downloadReleaseGlb()
  const { optimizedBytes } = await optimizeModel(raw)
  await mkdir(new URL('../public/models/', import.meta.url), { recursive: true })
  await writeFile(MODEL_PATH, optimizedBytes)
  console.log(`${MODEL_PATH}: ${(optimizedBytes.length / 1e6).toFixed(1)} MB (raw ${(raw.length / 1e6).toFixed(1)} MB)`)
  return MODEL_PATH
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await fetchModel(process.argv[2])
}
