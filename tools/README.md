# tools — taint-graph pipeline

Reusable tooling that turns a CVE's **entry → sink** data flow into a consistent diagram plus a
Semgrep differential. Built once for CVE-2025-3248, reusable for the next CVE by editing two data
blocks.

| File | Role |
|------|------|
| [`cve-taint-graph.md`](cve-taint-graph.md) | The method: 5-step workflow, data schema, theme spec, quality checks |
| [`taint-rule.example.yaml`](taint-rule.example.yaml) | Semgrep taint-rule template (source → sink) |
| [`render_excalidraw.py`](render_excalidraw.py) | Emits the editable `.excalidraw` diagram — edit only the `spine` / `isl` blocks per CVE |
| [`render_svg.py`](render_svg.py) | Emits a static `.svg` twin (renders inline on GitHub); keep its data blocks in sync with the Excalidraw one |

Quick use:

```bash
# scan the vulnerable tag (isolated worktree) with the custom rule + community rules
semgrep --config taint-rule.example.yaml --config p/python --config p/security-audit <src> --json -o findings.json
# render both diagram formats from the same spine/isl data
python render_excalidraw.py out.excalidraw
python render_svg.py out.svg
```
