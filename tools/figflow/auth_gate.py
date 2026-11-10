#!/usr/bin/env python3
"""
figflow auth-gate-flow: show a FastAPI Depends() *authorization* flow, not output.

A route snippet only *defines* the endpoint, so there is nothing to trace until a
request is driven through it. This module:
  1. infers the POST path + the valid token from the snippet (AST),
  2. drives TWO real requests via TestClient (valid / invalid) under sys.settrace,
  3. colors each code line by ROLE (gate=GREEN, block=RED, route/DI=BLUE,
     endpoint/sink=ORANGE, module=GRAY), and draws the Depends injection arrow,
  4. renders the gate decision as two branches (PASS->sink / BLOCKED->401) with a
     terminal per branch — so "the sink is reachable ONLY via the gate's PASS edge".

Run (needs fastapi + httpx):
  uv run --with fastapi --with httpx python auth_gate.py \
      --code examples/fastapi_depends.py --out figflow-out/authgate --fmt both
"""
from __future__ import annotations
import ast, io, sys, re, contextlib, argparse, pathlib, json
import figflow as ff
from render import (to_svg, to_excalidraw, BG, INK, FAINT, MONO, HAND, CODE_X, CODE_TOP,
                    emit_title, emit_legend, emit_timeline, emit_terminal, emit_code)

PAL = ff.PAL
GRAY, GREEN, RED, BLUE, ORANGE = PAL["GRAY"], PAL["GREEN"], PAL["RED"], PAL["BLUE"], PAL["ORANGE"]
GUARD = re.compile(r"raise\s|HTTPException|Blocked|!=|Unauthorized|401")

# ---- infer path / token / gate / endpoint from the snippet ------------------
def analyze(code):
    tree = ast.parse(code)
    funcs = {f.name: (f.lineno, f.end_lineno) for f in ast.walk(tree)
             if isinstance(f, ast.FunctionDef)}
    path = gate = endpoint = token = None
    dep_line = None
    for f in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for d in f.decorator_list:                       # @app.post("/x")
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) \
               and d.func.attr in ("post", "get", "put", "delete") and d.args:
                endpoint = f.name
                path = getattr(d.args[0], "value", None)
        for a in f.args.args + f.args.kwonlyargs:         # Depends(verify_token)
            pass
        for default in f.args.defaults + f.args.kw_defaults:
            if isinstance(default, ast.Call) and getattr(default.func, "id", "") == "Depends":
                gate = getattr(default.args[0], "id", None) if default.args else None
                dep_line = default.lineno
    # valid token = the string literal the gate compares against
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            for c in [n.left, *n.comparators]:
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and "token" in (c.value.lower() + "token"):
                    if c.value not in ("Authorization",):
                        token = c.value
    gate_line = funcs.get(gate, (None,))[0]
    return {"path": path or "/", "token": token or "Bearer valid-jwt-token",
            "gate": gate, "endpoint": endpoint, "funcs": funcs,
            "dep_line": dep_line, "gate_line": gate_line}

# ---- drive one request -> (stdout, status) ----------------------------------
# The branch timeline is built from captured stdout (the execution evidence),
# not sys.settrace: TestClient runs the app in a worker thread, where a
# main-thread tracer never fires, whereas redirect_stdout is process-wide.
def run_request(code, fname, path, headers, payload):
    g = {}
    exec(compile(code, fname, "exec"), g)                 # define app
    from fastapi.testclient import TestClient
    client = TestClient(g["app"], raise_server_exceptions=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = client.post(path, json=payload, headers=headers)
    return buf.getvalue().splitlines(), r.status_code

# ---- role color per source line ---------------------------------------------
def role_color(info, lineno, text):
    g0, g1 = info["funcs"].get(info["gate"], (0, 0))
    e0, e1 = info["funcs"].get(info["endpoint"], (0, 0))
    t = text.strip()
    if t.startswith("@") and ("post" in t or "get" in t or "router" in t or "app." in t):
        return BLUE
    if g0 <= lineno <= g1:
        return RED if GUARD.search(t) else GREEN
    if e0 <= lineno <= e1:
        return ORANGE
    return GRAY

# ---- build shapes -----------------------------------------------------------
def _stdout_color(line):
    return RED if GUARD.search(line) else (ORANGE if "Endpoint" in line else GREEN)

def build(code, info, passr, blockr):
    """Flat ROLE-colored code (no scope boxes — the story is a gate branch, not
    nesting) + Depends injection arrow, then two branch timelines + terminals,
    all drawn with render.py's SHARED chrome so the theme matches scope-flow."""
    S = []
    emit_title(S, "FastAPI Depends — authorization flow")
    src = code.split("\n")
    ln_y, code_bottom = emit_code(S, src, lambda i, t: role_color(info, i + 1, t))  # flat, no boxes
    di, gi = (info["dep_line"] or 0) - 1, (info["gate_line"] or 0) - 1
    if di in ln_y and gi in ln_y:                                   # Depends -> verify_token
        gx = CODE_X - 16
        S.append(("arrow", gx, ln_y[di] + 4, gx, ln_y[gi] + 4, BLUE, 2.0, "4 3"))

    emit_legend(S, 720, 92, "color -> role",
                [(GRAY, "module / caller"), (BLUE, "route + Depends (DI)"),
                 (GREEN, "gate: verify_token"), (RED, "block -> 401"), (ORANGE, "endpoint / sink")])

    col_top = max(code_bottom + 70, 400)

    def branch(cx, header, hc, stdout, status, final):
        S.append(("text", cx, col_top - 26, header, hc, 15, HAND, "start"))
        steps = [("Request: POST " + info["path"], GRAY, 0),
                 ("FastAPI resolves Depends() first", BLUE, 0)]
        steps += [(l, _stdout_color(l), 0) for l in stdout]
        steps.append((final, hc, 0))
        _, bottom = emit_timeline(S, cx, col_top, steps)
        tl = [(l, _stdout_color(l)) for l in (stdout or ["(no output)"])]
        return emit_terminal(S, cx, bottom + 18, 440, hc, tl, status=f"HTTP {status}")

    b1 = branch(70, "PASS  (valid token)", GREEN, *passr, "200 success -> caller")
    b2 = branch(560, "BLOCKED  (invalid token)", RED, *blockr, "401 -> caller; sink never runs")
    bottom = max(b1, b2)
    S.append(("text", 70, bottom + 34,
              "KEY: the ORANGE sink runs ONLY on the GREEN gate's PASS edge; a bad token raises at the gate and the endpoint body never executes.",
              INK, 13, HAND, "start"))
    return S, 1060, bottom + 60

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--out", default="figflow-out/authgate")
    ap.add_argument("--fmt", choices=["svg", "excalidraw", "both"], default="both")
    a = ap.parse_args()
    code = pathlib.Path(a.code).read_text()
    info = analyze(code)
    fname = "<authgate>"
    payload = {"flow_id": "demo-flow-001"}
    passr = run_request(code, fname, info["path"],
                        {"Authorization": info["token"]}, payload)
    blockr = run_request(code, fname, info["path"],
                         {"Authorization": "nope"}, payload)
    S, W, H = build(code, info, passr, blockr)
    base = pathlib.Path(a.out); base.parent.mkdir(parents=True, exist_ok=True)
    if a.fmt in ("svg", "both"):
        p = base.with_suffix(".svg"); p.write_text(to_svg(S, W, H)); print(p)
    if a.fmt in ("excalidraw", "both"):
        p = base.with_suffix(".excalidraw"); p.write_text(json.dumps(to_excalidraw(S, W, H), indent=1)); print(p)

if __name__ == "__main__":
    main()
