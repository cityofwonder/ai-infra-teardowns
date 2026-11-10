#!/usr/bin/env python3
"""
figflow — natural-language -> themed execution-flow figure (Excalidraw-style, dark).

Pipeline (deterministic core first; LLM + image backend are pluggable stages):

    NL intent ─▶ Orchestrator.pick()  ─▶ figure-type (palette + skeleton + focus)
    code      ─▶ extract()            ─▶ FlowIR  (scopes, code lines, timeline, stdout)
    FlowIR+ft ─▶ render_prompt()      ─▶ the filled theme prompt (text)
    prompt    ─▶ backend_gemini()     ─▶ N candidate PNGs   [needs API key]

The deterministic core gets scopes from the AST, and the timeline + exact stdout
from ACTUALLY RUNNING the snippet under sys.settrace — no LLM guessing. The LLM is
reserved for semantic ROLE labels / prose and is a no-op here.
"""
from __future__ import annotations
import ast, io, sys, re, contextlib, textwrap
from dataclasses import dataclass, field

# ---------------------------------------------------------------- palette
PAL = {  # name -> hex, all readable on #1E1E1E
    "BLUE":  "#4DABF7", "GREEN": "#69DB7C", "ORANGE": "#FFA94D",
    "GRAY":  "#CED4DA", "GRAY2": "#868E96", "RED":    "#FF6B6B",
}
HEX2NAME = {v: k for k, v in PAL.items()}
DEPTH_COLOR = {0: "BLUE", 1: "GREEN", 2: "ORANGE"}   # outer->inner; >=2 clamps to ORANGE

# ---------------------------------------------------------------- IR
@dataclass
class Scope:
    id: str; name: str; color: str; depth: int; kind: str   # module|func|target
@dataclass
class CodeLine:
    text: str; lineno: int; scope_id: str; role: str | None = None   # role overrides color
@dataclass
class Step:
    n: int; scope_id: str; action: str; kind: str   # kind: call|line|return
@dataclass
class FlowIR:
    concept: str
    scopes: list[Scope] = field(default_factory=list)
    lines:  list[CodeLine] = field(default_factory=list)
    steps:  list[Step] = field(default_factory=list)
    stdout: list[str] = field(default_factory=list)
    def scope(self, sid): return next(s for s in self.scopes if s.id == sid)

# ---------------------------------------------------------------- static ROLE patterns
ROLE_PATTERNS = [            # (regex, role, color-override)  — first match wins per line
    (re.compile(r"\braise\s+HTTPException"), "BLOCK", "RED"),
    (re.compile(r"!=|==.*token|Invalid"),    "GUARD", "RED"),
    (re.compile(r"\bexec\s*\("),             "SINK",  "ORANGE"),
    (re.compile(r"Depends\s*\("),            "INJECT", None),
]
def role_of(src: str):
    for rx, role, col in ROLE_PATTERNS:
        if rx.search(src):
            return role, col
    return None, None

# ---------------------------------------------------------------- AST: scopes + decorated targets
def _parents(tree):
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._parent = parent
    return tree

def extract_scopes(code: str) -> tuple[list[Scope], dict[int, str]]:
    tree = _parents(ast.parse(code))
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    scopes = [Scope("module", "module / caller", PAL["GRAY"], -1, "module")]
    # names of funcs so we can detect "decorated by one of our funcs" -> target
    fnames = {f.name for f in funcs}
    for f in funcs:
        depth = 0; p = getattr(f, "_parent", None)
        while p is not None:
            if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)): depth += 1
            p = getattr(p, "_parent", None)
        decorated_by_ours = any(
            (isinstance(d, ast.Name) and d.id in fnames) for d in f.decorator_list)
        kind = "target" if decorated_by_ours else "func"
        color = PAL["ORANGE"] if kind == "target" else PAL[DEPTH_COLOR.get(min(depth, 2), "ORANGE")]
        scopes.append(Scope(f.name, f.name, color, depth, kind))
    # line -> innermost scope id (smallest enclosing func range; else module)
    line2scope = {}
    total = code.count("\n") + 1
    for ln in range(1, total + 1):
        best = None
        for f in funcs:
            if f.lineno <= ln <= (f.end_lineno or f.lineno):
                if best is None or (f.end_lineno - f.lineno) < (best.end_lineno - best.lineno):
                    best = f
        line2scope[ln] = best.name if best else "module"
    return scopes, line2scope

# ---------------------------------------------------------------- run under trace -> timeline + stdout
def trace_run(code: str, fname="<snippet>"):
    compiled = compile(code, fname, "exec")
    order: list[int] = []
    def tracer(frame, event, arg):
        if frame.f_code.co_filename == fname and event == "line":
            order.append(frame.f_lineno)
        return tracer
    buf = io.StringIO(); old = sys.gettrace()
    sys.settrace(tracer)
    try:
        with contextlib.redirect_stdout(buf):
            exec(compiled, {})
    finally:
        sys.settrace(old)
    return order, buf.getvalue().splitlines()

# ---------------------------------------------------------------- build FlowIR
def extract(code: str, concept: str) -> FlowIR:
    code = textwrap.dedent(code).strip("\n")
    scopes, line2scope = extract_scopes(code)
    ir = FlowIR(concept=concept, scopes=scopes)
    src_lines = code.split("\n")
    for i, text in enumerate(src_lines, start=1):
        if not text.strip():
            continue
        role, _ = role_of(text)
        ir.lines.append(CodeLine(text=text, lineno=i, scope_id=line2scope[i], role=role))
    order, stdout = trace_run(code)
    ir.stdout = stdout
    # collapse consecutive same-line repeats, build steps with scope-weaving + call/return
    prev_scope = None; n = 0
    for ln in order:
        sid = line2scope.get(ln, "module")
        kind = "line"
        if prev_scope is not None and sid != prev_scope:
            kind = "call"          # scope changed -> entered/left a scope on this step
        n += 1
        ir.steps.append(Step(n=n, scope_id=sid, action=src_lines[ln-1].strip(), kind=kind))
        prev_scope = sid
    return ir

# ---------------------------------------------------------------- figure-types (theme registry)
SKELETON = """TITLE: {concept} execution-flow diagram, hand-drawn Excalidraw style, dark theme

GLOBAL STYLE (fixed):
- Hand-drawn Excalidraw look: rounded rects, wobbly strokes, hand-drawn font for
  labels, monospace for code. Background #1E1E1E. COLOR = SCOPE (outline, code text,
  step badges AND arrows share one color per scope; never reuse a color).
- Terminal traffic-light dots: #FF5F56 / #FFBD2E / #27C93F. Legend top-right.

LEGEND (color -> scope):
{legend}

TOP HALF — NESTED CODE (nesting depth must be visually obvious; concentric boxes):
{code_block}

BOTTOM HALF — EXECUTION TIMELINE (top-to-bottom = time; badge colored by the scope
running at that instant; solid=call/enter, thin gray=return/value back):
{timeline}

TERMINAL (verbatim stdout, in order):
{terminal}

VISIBILITY RULES: all colors readable on #1E1E1E; strictly one color per scope;
align each timeline step near the code line it runs; keep arrows from crossing."""

FIGURE_TYPES = {
    "scope-flow": {"focus": "nesting + call/return weaving between scopes"},
    "auth-gate-flow": {"focus": "a gate (Depends) that branches PASS->sink / FAIL->401; add RED block path + dashed BLUE injection arrow"},
}

def render_prompt(ir: FlowIR, figure_type: str = "scope-flow") -> str:
    ft = FIGURE_TYPES[figure_type]
    legend = "\n".join(f"  {HEX2NAME[s.color]:6} -> {s.name}"
                       for s in ir.scopes if s.kind != "module" or True)
    cb = []
    for cl in ir.lines:
        sc = ir.scope(cl.scope_id)
        cname = HEX2NAME[sc.color]
        if cl.role in ("BLOCK", "GUARD"): cname = "RED"
        tag = f"  # {cl.role}" if cl.role else ""
        cb.append(f"  {cname:6} {cl.text}{tag}")
    code_block = "\n".join(cb)
    tl = []
    for st in ir.steps:
        cname = HEX2NAME[ir.scope(st.scope_id).color]
        marker = "->" if st.kind == "call" else "  "
        tl.append(f"  {st.n:>2} ({cname}) {marker} {st.action}")
    timeline = "\n".join(tl)
    terminal = "\n".join(f"    {l}" for l in ir.stdout) or "    (no stdout)"
    return SKELETON.format(concept=ir.concept, legend=legend,
                           code_block=code_block, timeline=timeline, terminal=terminal) \
        + f"\n\nFOCUS: {ft['focus']}"

# ---------------------------------------------------------------- orchestrator
INTENT_MAP = [
    (re.compile(r"\b(auth|depends|gate|인가|인증|token)\b", re.I), "auth-gate-flow"),
    (re.compile(r"\b(decorat|scope|wrapper|nest|스코프|중첩)\b", re.I), "scope-flow"),
]
def pick_figure_type(nl: str) -> str:
    for rx, ft in INTENT_MAP:
        if rx.search(nl): return ft
    return "scope-flow"

def run(nl: str, code: str, concept: str | None = None):
    ft = pick_figure_type(nl)
    ir = extract(code, concept or ft)
    prompt = render_prompt(ir, ft)
    return {"figure_type": ft, "ir": ir, "prompt": prompt}

# ---------------------------------------------------------------- Gemini image backend (pluggable)
def backend_gemini(prompt: str, out_dir: str, n: int = 3,
                   model: str = "gemini-2.5-flash-image", api_key: str | None = None):
    """Generate N candidate PNGs with Gemini native image generation.

    Requires `pip install google-genai` and GEMINI_API_KEY.
    - response_modalities MUST include both TEXT and IMAGE (image-only is unsupported).
    - `model` id drifts (gemini-2.5-flash-image / -preview / gemini-3.x-flash-image);
      verify the current one for your account. Pass --model to override.
    """
    import os, pathlib
    from google import genai                         # google-genai SDK
    from google.genai import types
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
    paths = []
    for i in range(n):
        resp = client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
        for part in resp.candidates[0].content.parts:
            data = getattr(getattr(part, "inline_data", None), "data", None)
            if data:
                p = pathlib.Path(out_dir) / f"figure_{i+1}.png"
                p.write_bytes(data); paths.append(str(p))
    return paths

# ---------------------------------------------------------------- demo
if __name__ == "__main__":
    DECORATOR = '''
    def logger_decorator(func):
        def wrapper(*args, **kwargs):
            print(f"[{func.__name__}] Function Execution...")
            result = func(*args, **kwargs)
            print(f"[{func.__name__}] ... is Finished!")
            return result
        return wrapper

    @logger_decorator
    def say_hello(name):
        print(f"Hello, {name}!")

    say_hello("cityofwonder")
    '''
    out = run("decorator scope wrapper 중첩", DECORATOR, concept="Python decorator")
    print("figure_type:", out["figure_type"])
    print("=" * 70)
    print(out["prompt"])
