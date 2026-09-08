# Measuring-stick note-fit native evidence

The [recipe evidence](../../pipeline/measuring-stick-note-fit.md) describes the
failure, correction and acceptance limits. These files preserve the actual
logs; no source model or drawing artifact is included here.

- `failed-4013.txt`: complete failed native command log, before any note extent
  measurement. SHA-256 `fb93c555b67075cfdc730b952a5099881f9dc79a5638dd687301ac92856ccfd4`.
- `passed-f52.txt`: complete successful command log (one command line only).
  SHA-256 `e0efb9351a22ce9ea1476f2526abb8150d791e57d5b4caab6fb2429c3c9caf95`.
- `passed-f52-traces.jsonl`: all 22 original raw records for trace
  `0xee7bead1a5acf1bf430bdd8774ee9549`, including task, build, note fit and export.
  SHA-256 `9fa4233fdeb3970e53691edbfffd39a39a8ffa9dfe3356f519b4b14da7d910da`.
- `passed-f52-logs.jsonl`: all 14 original raw log records for that trace.
  SHA-256 `0fb91b1667470443f058671f5b69f2c31cf50c5a8b29108a38e76a57c7d3a996`.
- `source-guards-and-noop.jsonl`: exact selected tool-result text for baseline
  hashes (`fe07bc`), hashes after the failed run (`744351`), successful-run
  hashes before the no-op (`039889`), and no-op completion (`869c25`).
  SHA-256 `a925d77cd61221e52a20ff5205f29ceace1fe0d68ca710c42823d32d86384ecf`.
- `source-guards-and-noop-inputs.jsonl`: corresponding historical tool inputs,
  mapped to those chunk IDs. These are evidence, not commands to rerun.
  SHA-256 `0c4c024c62de69a21c855fd2c0c3b2a37a3036ec0113a0f48786409168dc1fa6`.

The raw records were selected by their exact trace ID from
`C:/src/ha-foundations-integration/cad/out/reports/telemetry/`, retaining each
original JSONL record byte for byte and its original order. Unrelated traces
were not copied. Both command logs were byte-verified against the completed
`cad/out/logs/drawing-measuring_stick.log` before the next run could overwrite it.
The live bank and producer artifacts were not modified.

The four tool receipts were extracted from the owning agent's retained session
using only those exact chunk IDs. Their result text and command strings are
unchanged. Session metadata, conversation text and unrelated tool outputs were
omitted; the whole session was not copied or published. The no-op result records
both tasks skipped, exit 0 and unchanged trace/log byte counts. The initial and
final native source/token hashes match; updated drawing/PDF/PNG hashes are
recorded separately from source immutability.

Scoped `.gitattributes` rules disable newline conversion for these raw receipts,
including the Windows command logs, and identify CR as part of those logs' line
endings for whitespace checks. This preserves their byte hashes in Git.

This is targeted native save/print evidence, not a cold-reopen or full-stack
acceptance claim.
