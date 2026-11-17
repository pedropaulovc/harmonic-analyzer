---
name: gate-test-enrollment
description: check:recipe runs every test file a bare pytest collects, minus dedicated-gate files and dodo._UNGATED; there is no enrollment step
metadata:
  type: project
---

`check:recipe` selects its tests by collection (`dodo._collected_tests`):
every `test_*.py` under pyproject's `testpaths`, honouring `norecursedirs`,
except the files a dedicated `check:*` gate owns (`dodo._GATE_TESTS`) and the
files listed in `dodo._UNGATED` with a reason. A new test file is gated by
existing; there is nothing to enroll.

Why it changed (#2884): until 2026-11 the gate ran a hand-kept allowlist plus a
`test_*_drawing.py` glob, and a file missing from both ran in NO gate while
check:recipe stayed green (PR #416: 14 assertions dead since the file was
written). `test_check_gate_enrollment.py` policed the allowlist; collection
removes the failure mode instead.

**How to apply:** to keep a test file out of every gate (it needs a local
tool no build dependency tracks, say), add it to `dodo._UNGATED` with a
one-line reason. To move a file into a dedicated gate, add it to
`_GATE_TESTS`; check:recipe drops it automatically.
