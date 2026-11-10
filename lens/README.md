# lens — the trust-model checklist (the "engine")

The single, fixed analysis lens applied to every teardown: **source → mediation → sink**.
Holding it constant is what makes failure attributable — if it stops predicting at some rung, the
unknown introduced at that rung is the reason (see the ladder in the [root README](../README.md)).

Checklist (per target):

1. **Source** — where does untrusted input enter? (HTTP body / query / header / tool description / file)
2. **Mediation** — what *should* gate it? (authN, authZ, sandbox, allow-list, deserialization guard) — and is it present on *this* route?
3. **Sink** — what dangerous capability does it reach? (`exec`/`eval`, file op, authz decision, deserialization)
4. **Observable effect** — the oracle that proves it fired (crash / file written / command output / ASR for the semantic track).

> Status: described here and exercised in [CVE-2025-3248](../langflow/CVE-2025-3248/); to be
> promoted to a standalone fill-in checklist once it has run on 2–3 more targets.
