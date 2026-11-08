# ai-infra-teardowns

Understanding AI-infrastructure vulnerabilities by reproducing known ones from the ground up, then hunting for new ones in the same stack.

## Why this project

A fresh vulnerability hides its cause; a patched one does not. The fix commit removes the bug but records exactly what it was - the patch is the answer key. This project uses that: I study CVEs whose root cause is already settled by their patch, prove my analysis method recovers that ground truth, and only then turn the same method on targets where the answer is still unknown.

The goal is not a polished tool or a pile of exploits. It is to understand the *phenomenon* - why a vulnerability class keeps recurring across the AI-infra stack. I build the minimum reproduction each CVE needs, nothing more.

## Approach: one lens, a ladder of unknowns

Every teardown applies the same lens - a trust model: source -> mediation -> sink. Holding the lens fixed makes failure attributable: if it stops predicting at some rung, the unknown introduced at that rung is the reason.

Two tracks share the lens. They leak different things - deterministic control-flow vs. probabilistic model-obedience - but share one structure: untrusted input -> missing mediation -> dangerous sink -> observable effect.

### Main track - deterministic sinks (exec / file / authz / deserialization)

| Rung | What | What I learn |
|------|------|--------------|
| L0 | trust-model lens + checklist, applied to a solved CVE | Is my analysis method correct? |
| L1 | fix-commit diff teardown | Which mediation was missing? |
| L2 | isolated-VM reproduction (pinned version, snapshot) | Does the sink actually fire? |
| L3 | cluster generalization -> taxonomy | Why does the class recur? |
| L4 | same lens on an under-researched peer | Can I find a new one? |

### Parallel track - semantic sinks (prompt / tool poisoning)

| Rung | What | What I learn |
|------|------|--------------|
| L1 | description/metadata injection reaching model context | Controlled obedience |
| L2 | ASR harness (fixed model, temp=0, N trials) | Reproducibility under non-determinism |
| L3 | cross-framework measurement | Pattern vs. instance |
| L4 | under-tested agent surface | A novel injection channel |

The two tracks need different oracles - a binary crash/exec for the main track, an attack-success-rate for the semantic one - but the same source->sink lens drives target selection in both.

## Current status

- [x] L0 - trust-model lens defined (source -> mediation -> sink)
- [ ] L1 - Langflow flagship fix-diffs (cluster A: unsandboxed exec done; authz/IDOR, file-ops pending)
- [ ] L2 - isolated-VM reproduction, per-CVE snapshots
- [ ] L3 - Langflow recurrence taxonomy
- [ ] L4 - peer-framework hunt (Dify / n8n / MCP servers)

## L0 worked example: Langflow unsandboxed `exec` (done)

Before trusting the lens on an unknown target, it has to recover a root cause I can check against the patch.

Target: Langflow's code-validation endpoint, where a user-supplied component code field reaches `exec()` with no sandbox (the CVE-2025-3248 family).

Method: read the fix commit first (the answer key), map it onto source -> mediation -> sink, predict why the class should recur, then check the prediction against later CVEs in the same family.

**What this layer answers**
- Does the lens recover the patched root cause from the diff alone?
- Does it predict recurrence? (It does: the same `exec` sink reappears in later CVEs; an early patch that only added an auth check left the sink in place under default auto-login.)
- Intentional failure test: if I read only the CVE *text* and not the diff, do I misattribute the fix? (Yes - the first patch reads as an auth fix, but the sink survived until a later commit removed it. Reading the diff is what separates the real fix from the cosmetic one.)

**Evidence**
<!-- TODO: add after reproduction -->
- fix-diff excerpt: auth-only patch vs. sink-removal commit
- reproduction log: define-time `exec` via default-argument evaluation

## Repository layout

<!-- fill in as it grows -->

    lens/                 shared trust-model checklist (the "engine")
    harness/              ASR harness for the semantic track
    teardowns/
      langflow/
        a-exec/           trust-model map, fix-diff notes, poc, repro log
        b-authz/
        c-file/
      dify/
      mcp/

## How to run

<!-- TODO: per target - pinned version, VM snapshot id, make target -->

Each target runs in its own isolated VM snapshot, against a version pinned to just before its fix. Never against a public instance.

## Notes format

Each teardown is documented in five lines:
Root cause / Source->Sink / Broken mediation / What the patch fixed / What's left.

## Scope & disclosure

Targets run only as local, isolated instances. This repo holds reproductions of already-patched, public CVEs. For any *new* finding, nothing is published here until coordinated disclosure with the maintainer is complete (private report -> advisory/CVE -> patch).

## References

- OWASP - LLM Top 10 and MCP Top 10 (vulnerability-class taxonomy)
- MCPTox - benchmark for tool-poisoning attacks on real MCP servers
- CISA KEV catalog - which AI-infra CVEs are actually exploited in the wild
- Simon Willison - the "lethal trifecta" framing for agent data exfiltration
- VulnCheck / Cloud Security Alliance - AI-infra exploitation-window notes# ai-infra-teardowns
