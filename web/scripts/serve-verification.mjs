#!/usr/bin/env node
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { serveDist } from './verify-server.mjs'

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const args = process.argv.slice(2)
if (args.includes('--help')) {
  console.log('Usage: node web/scripts/serve-verification.mjs [--port 5957]\nServes the existing dist plus private unchanged original MP4s from HARMONIC_REFERENCE_ROOT (default web/.vite/reference-root). Open ?video=<slug>&referenceMedia=1 for real local original playback. No footage is copied into public/dist.')
} else {
  if (args.length && (args.length !== 2 || args[0] !== '--port')) throw new Error('Expected --port <number>')
  const port = args.length ? Number(args[1]) : 5957
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port must be an integer from 1 to 65535')
  const server = await serveDist(resolve(webRoot, 'dist'), { port, referenceRoot: resolve(process.env.HARMONIC_REFERENCE_ROOT ?? resolve(webRoot, '.vite/reference-root')), base: process.env.SIMULATOR_BASE })
  console.log(`Original-media preview ready: ${server.url}`)
  const stop = async () => { await server.close() }
  process.once('SIGINT', stop)
  process.once('SIGTERM', stop)
}
