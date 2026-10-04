#!/usr/bin/env node
// Parent-only current choice transaction; original source observations are never
// written. Verification reruns the raw factory, not a receipt-carried pass flag.
import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { resolve, relative } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { parseNativeRawGLB, CURRENT_NATIVE_RAW_SHA256, canonicalJson } from './native-model-byte-proof.mjs'
import { freezeIntroSilverHeadWitnesses } from './native-mesh-feature-witness.mjs'

const ROOT = fileURLToPath(new URL('../../', import.meta.url))
const RAW_DEFAULT = fileURLToPath(new URL('../.vite/model-source/60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c.glb', import.meta.url))
const SOURCE_DEFAULT = fileURLToPath(new URL('../.vite/verification-output/v39-source-feature-20261003/intro809-source-inspection.json', import.meta.url))
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex')
function fileRecord(path, bytes) { return { path: relative(ROOT, resolve(path)), sha256: sha256(bytes), byteLength: bytes.byteLength } }

export async function createIntroHeadFeatureChoices({ rawGLBPath = RAW_DEFAULT, sourceInspectionPath = SOURCE_DEFAULT } = {}) {
  const [raw, sourceBytes] = await Promise.all([readFile(rawGLBPath), readFile(sourceInspectionPath)])
  const rawSHA256 = sha256(raw)
  if (rawSHA256 !== CURRENT_NATIVE_RAW_SHA256) throw new Error('Current Intro choices require actual original approved raw v39 bytes')
  const nativeModel = { ...parseNativeRawGLB(raw), rawSHA256 }
  const sourceInspection = JSON.parse(sourceBytes.toString('utf8'))
  const rows = freezeIntroSilverHeadWitnesses(nativeModel, sourceInspection)
  const producerFiles = []
  for (const path of ['web/scripts/generate-intro-head-feature-choices.mjs', 'web/scripts/native-mesh-feature-witness.mjs', 'web/scripts/native-model-byte-proof.mjs']) producerFiles.push(fileRecord(resolve(ROOT, path), await readFile(resolve(ROOT, path))))
  const choices = rows.map(row => ({
    anchorId: row.witness.anchorId, state: 'chosen-unmeasured',
    partPath: row.witness.partPath, partLocalMetres: row.feature.localPointMetres,
    frozenWitness: row.witness, sourceBinding: row.sourceBinding,
    correspondenceChoice: row.correspondenceChoice,
    geometryEvidenceSHA256: row.geometryEvidenceSHA256, geometryEvidence: row.geometryEvidence,
  }))
  return { schemaVersion: 1, kind: 'current-intro-raw-head-feature-choices',
    videoId: 'NAsM30MAHLg', sourceSha256: sourceInspection.sourceSha256,
    modelRawSHA256: rawSHA256, modelSourceCommit: '81539e53f5146c06a77541415bd79da673806d96',
    rawInput: fileRecord(rawGLBPath, raw), primarySourceInspection: fileRecord(sourceInspectionPath, sourceBytes),
    producerFiles, choices,
    qualification: 'Four actual raw indexed slot-floor points are current chosen-unmeasured native correspondences to unchanged original silver-head FIT pixels. No source depth interpretation, current pose/camera, first-surface, GPU, CHECK or stage acceptance is transferred.' }
}

export async function verifyIntroHeadFeatureChoices(path) {
  const bytes = await readFile(path), supplied = JSON.parse(bytes.toString('utf8'))
  if (supplied?.rawInput?.path === undefined || supplied?.primarySourceInspection?.path === undefined) throw new Error('Current Intro choice input paths are missing')
  // Paths locate inputs only. Approved raw SHA and all original source facts are
  // independently required by the factory, including the exact source BGR8 PTS.
  const expected = await createIntroHeadFeatureChoices({ rawGLBPath: resolve(ROOT, supplied.rawInput.path), sourceInspectionPath: resolve(ROOT, supplied.primarySourceInspection.path) })
  if (canonicalJson(supplied) !== canonicalJson(expected)) throw new Error('Current Intro head choices differ from freshly recomputed original raw/source feature evidence')
  return { packet: expected, path: relative(ROOT, resolve(path)), sha256: sha256(bytes) }
}

async function main() {
  const { values } = parseArgs({ options: {
    'raw-glb': { type: 'string', default: RAW_DEFAULT },
    'source-inspection': { type: 'string', default: SOURCE_DEFAULT },
    output: { type: 'string' }, verify: { type: 'string' },
  } })
  if (Boolean(values.output) === Boolean(values.verify)) throw new Error('Specify exactly one of --output or --verify')
  if (values.verify) {
    console.log(JSON.stringify(await verifyIntroHeadFeatureChoices(values.verify)))
    return
  }
  const packet = await createIntroHeadFeatureChoices({ rawGLBPath: values['raw-glb'], sourceInspectionPath: values['source-inspection'] })
  await writeFile(values.output, JSON.stringify(packet, null, 2) + '\n')
  console.log(JSON.stringify({ output: values.output, kind: packet.kind, choiceCount: packet.choices.length, state: 'chosen-unmeasured' }))
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) await main()
