# prompts — research method transcripts

For reproducibility and transparency about how each teardown was produced: the prompts and
decision points used to drive the analysis (not the findings themselves — those live in each
`<platform>/CVE-*/`).

Keep one file per reusable prompt or per notable session. Strip anything private (hostnames,
emails, tokens) before committing.

- `cve-taint-graph.prompt.md` — *(to add)* the prompt that drives the [tools](../tools/) pipeline:
  given a CVE tag + endpoint, recover source → sink and emit the diagram.
