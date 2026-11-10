# Langflow teardowns

Visual AI-workflow builder. Flagship target for the **main track** (deterministic sinks).
Each row is one teardown; the **Class** column is the recurrence axis (L3) — sort by it to
see which sink keeps coming back across CVEs.

| CVE | Class | Source → Sink | Severity | Fixed in | Status |
|-----|-------|---------------|:--------:|----------|--------|
| [CVE-2025-3248](CVE-2025-3248/) | `exec` | unauth `POST /validate/code` → `exec(compile(user_code))` | 9.8 | 1.3.0 (auth) + GHSA-2wcq-pvw2-xh7v (sink removed) | ✅ analysed · reproduced |

> **Class legend.** `exec` = unsandboxed code execution · `authz` = missing/incorrect authorization (IDOR) · `file` = path traversal / arbitrary file op · `deser` = unsafe deserialization.

## Why these cluster

The `exec` class recurs because Langflow's product surface *is* user-authored component
code — the dangerous capability is a feature, so every endpoint that touches that code is a
candidate sink. The lens predicts: wherever user code reaches `compile`/`exec`/`import`
without a policy gate **and** the route lacks `CurrentActiveUser`, the class reappears.
CVE-2025-3248 is the clean L0 instance; later CVEs in the same family are the recurrence test.

## Per-teardown layout

Each `CVE-*/` folder holds, at one level:

- `README.md` — the evaluator-facing writeup (badges, 5-line summary, taint path, repro, patch)
- `ANALYSIS.md` — the detailed entry→sink walkthrough
- `cve-*-dataflow.svg` — dataflow + call graph (renders inline on GitHub)
- `cve-*.yaml` — the Semgrep taint rule used for the differential
- `scan-<vulnerable>.txt` / `scan-<patched>.txt` / `*.findings.json` — raw scanner output
