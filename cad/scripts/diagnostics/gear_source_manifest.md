# Six source-authored gear inputs

The real cache-disabled producer builds passed at frozen root
`7f07043420ed110d0ee7dc267df2fb571af8af5d`, adapter
`25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`, on 2026-09-07 with SolidWorks PID
31860. The six targets were serialized by the ordinary machine-global seat lock:

```powershell
$env:HARMONIC_SW_AUTOSTART = '0'
$env:HARMONIC_REMOTE_CACHE_MODE = 'off'
uv run --no-sync python -m doit -a -n 4 part:crank_drive_gear part:crank_pinion part:cylinder_gear part:rack_pinion part:transgear_feed_pinion part:transgear_pinion
```

All six `task part:*` spans ended OK and the parent exited zero. Durations below
exclude time waiting for the seat. Each exact `.execution` token equals its saved
SLDPRT SHA-256; these are producer results, not source hashes adopted after a
drawing changed them.

| Target | Bytes | Task seconds | Trace ID |
| --- | ---: | ---: | --- |
| crank_drive_gear | 1410620 | 100.942181 | `0x7eaeb442a071e1e9334d6f86d6b2f0de` |
| crank_pinion | 241977 | 53.941978 | `0xb23323376b8b3d3dda0a7593247b1e9a` |
| cylinder_gear | 846238 | 157.276698 | `0x0752824939db7302af9f88f282cdd696` |
| rack_pinion | 752453 | 98.826999 | `0x714db0b72240c20596b7781c32e2ecc0` |
| transgear_feed_pinion | 158792 | 40.410009 | `0xd70a2047d45e727748ca8d6731592cda` |
| transgear_pinion | 159949 | 39.573981 | `0x3bee657c7be3e10e3ed8002c260211a1` |

| Target | Actual source and execution SHA-256 |
| --- | --- |
| crank_drive_gear | `a5a2e0882336d622a7e93fae4d326cb059e7d91758e536488fcc6bf6de4ce93f` |
| crank_pinion | `1b3a9dc571e1256459a10dd7e2d0815d35d41c284bf8665a9546751ac242ef24` |
| cylinder_gear | `b436e33215ced1c3791cfd4095f49b376258edc1d4896f86656cd1b569a966f9` |
| rack_pinion | `6591e6a5abf67a5a541ae8d4ee9542795bf37b5bfcb18121ee4636e963096fa7` |
| transgear_feed_pinion | `93bc3466e0066f267d66223fc6ac2eed020ebdc10b665981f6685f1947f33d74` |
| transgear_pinion | `989b42c133984a367517dfeb43f96bdf4201a2c899c4b2c9801d8ab7cb41e6c0` |

Prior parts and their matching tokens were copied before rebuilding to
`cad/out/reports/gears-before-callout-rebuild-e73a384f172347a294f0a02de01dd9b9/`.
Nothing was deleted. Their original pins remain in
`fleet_callout_preflight.md` and the historical test inventory. The explicit new
mapping changes only these six input hashes; dimension manifests and entity/view
roles remain unchanged. Replay rejects historical or unknown bytes and never
repins them automatically.

This proves native source production, not drawing acceptance or a speedup.
Source immutability, complete callout import, annotation attachments, layout,
saved-drawing cold reopen and printed inspection remain required for each gear.
