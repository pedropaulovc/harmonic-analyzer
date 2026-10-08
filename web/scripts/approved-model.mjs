import { readFile } from 'node:fs/promises'
import { validateModelRepresentation } from '../model-representation.mjs'

// Authority is the reviewed, tracked record compiled into the browser, never
// downloaded public metadata or mechanics-data's claim about its own source.
const approved = validateModelRepresentation(JSON.parse(await readFile(new URL('../content/model-representation.json', import.meta.url), 'utf8')))
Object.freeze(approved.pipeline.steps)
for (const field of ['source', 'identity', 'representation', 'pipeline', 'equivalence']) Object.freeze(approved[field])
export const APPROVED_MODEL_REPRESENTATION = Object.freeze(approved)
export const LIVE_MODEL_SOURCE = APPROVED_MODEL_REPRESENTATION.source
