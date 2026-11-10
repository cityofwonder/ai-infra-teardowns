#!/usr/bin/env python3
"""
figflow deterministic renderer: FlowIR -> abstract shapes -> SVG and/or .excalidraw.

Exact text straight from the IR (no diffusion garbling). ONE shared theme (constants
+ emit_* component helpers) is used by every figure-type so they never drift:
  - emit_title / emit_legend / emit_timeline / emit_terminal are shared chrome,
  - the code panel differs on purpose (scope-flow = tinted concentric scope boxes to
    show nesting; auth-gate = flat, ROLE-colored, since its story is a branch, not
    nesting), everything else is pixel-identical.
One layout() builds shapes; to_svg / to_excalidraw emit them, so SVG and the editable
Excalidraw file also never drift.

  python render.py                          # demo -> figflow-out/figure.{svg,excalidraw}
  python render.py --code x.py --intent "scope" --fmt both
"""
from __future__ import annotations
import re, html, json, argparse, pathlib, random
import figflow as ff

PAL = ff.PAL
BG = "#1E1E1E"; INK = "#CED4DA"; FAINT = "#868E96"; PANEL = "#0d0d0d"
MONO = "mono"; HAND = "hand"
# ---- SHARED THEME (every figure-type uses these) ----
CW = 8.6; LH = 26; FS = 15; TITLE_FS = 28
BADGE_R = 13; STEP_H = 52; INDENT = 60
CODE_X = 64; CODE_TOP = 86
SETUP = re.compile(r"^\s*(@|def |async def |class )")

def tint(hexc, bg=BG, t=0.16):
    h = lambda c: (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    (r1, g1, b1), (r2, g2, b2) = h(hexc), h(bg)
    return "#%02x%02x%02x" % (round(r1*t+r2*(1-t)), round(g1*t+g2*(1-t)), round(b1*t+b2*(1-t)))

# ---- abstract shapes ---------------------------------------------------------
# ("rect", x,y,w,h, stroke, fill, sw, dash) · ("text", x,y,s,color,fs,font,anchor)
# ("circle", cx,cy,r,stroke,fill)           · ("arrow", x1,y1,x2,y2,color,sw,dash)

# ---- SHARED component emitters (append shapes to S) --------------------------
def emit_title(S, text):
    S.append(("text", 40, 50, text, INK, TITLE_FS, HAND, "start"))

def emit_legend(S, x, y, title, rows):               # rows=[(color,label)]
    S.append(("rect", x - 14, y - 24, 300, 24 + 22 * len(rows), FAINT, "#161616", 1.5, None))
    S.append(("text", x, y - 8, title, FAINT, 12, HAND, "start"))
    for j, (c, name) in enumerate(rows):
        yy = y + 14 + j * 22
        S.append(("circle", x + 8, yy - 4, 7, c, c))
        S.append(("text", x + 24, yy, name, c, 13, HAND, "start"))

def emit_timeline(S, x0, top, steps, step_h=STEP_H):  # steps=[(text,color,indent)]
    pos = []
    for i, (text, color, indent) in enumerate(steps):
        cy = top + i * step_h; cx = x0 + indent * INDENT
        if i:
            S.append(("arrow", pos[-1][0], pos[-1][1] + BADGE_R, cx, cy - BADGE_R, steps[i-1][1], 2.4, None))
        S.append(("circle", cx, cy, BADGE_R, color, BG))
        S.append(("text", cx, cy + 5, str(i + 1), color, 13, HAND, "middle"))
        S.append(("text", cx + 24, cy + 5, text, color, 14, MONO, "start"))
        pos.append((cx, cy))
    return pos, top + len(steps) * step_h

def emit_terminal(S, x, y, w, hc, lines, status=None):  # lines=[(text,color)]
    th = 46 + len(lines) * 22 + 14
    S.append(("rect", x, y, w, th, hc or FAINT, PANEL, 2, None))
    for d, c in enumerate(["#FF5F56", "#FFBD2E", "#27C93F"]):
        S.append(("circle", x + 20 + d * 20, y + 20, 6, c, c))
    if status:
        S.append(("text", x + w - 92, y + 22, status, hc or INK, 12, HAND, "start"))
    for d, (text, c) in enumerate(lines):
        S.append(("text", x + 18, y + 52 + d * 22, text, c, 13, MONO, "start"))
    return y + th

def emit_code(S, src_lines, color_of, top=CODE_TOP, box_specs=None):
    """Draw code lines; optional box_specs=[(inset,first_i,last_i,color)] -> tinted
    concentric scope boxes behind (scope-flow). Returns (line_y map, bottom_y)."""
    ln_y, r = {}, 0
    for i, t in enumerate(src_lines):
        if t.strip():
            ln_y[i] = top + r * LH; r += 1
    tx = CODE_X + (18 if box_specs else 0)
    if box_specs:
        for inset, fi, li, color in box_specs:
            y0 = ln_y[fi] - 24; y1 = ln_y[li] + 14
            w = max(len(src_lines[k]) for k in range(fi, li + 1) if src_lines[k].strip())
            S.append(("rect", CODE_X + inset, y0, w * CW + 64 - 2 * inset, y1 - y0, color, tint(color), 2.5, None))
    for i, t in enumerate(src_lines):
        if i in ln_y:
            S.append(("text", tx, ln_y[i] + 4, t.rstrip(), color_of(i, t), FS, MONO, "start"))
    return ln_y, top + r * LH

# ---- scope-flow layout -------------------------------------------------------
def _indent(ir, sid):
    s = ir.scope(sid)
    return 2 if s.kind == "target" else (0 if s.kind == "module" else min(s.depth + 1, 3))

def filtered_steps(ir):
    start = next((i for i, st in enumerate(ir.steps)
                  if ir.scope(st.scope_id).kind == "module" and not SETUP.match(st.action)), 0)
    kept = [st for st in ir.steps[start:] if not SETUP.match(st.action)]
    out = [(st.action, ir.scope(st.scope_id).color, _indent(ir, st.scope_id)) for st in kept]
    out.append(("Return: value is passed back to caller", PAL["GRAY"], 0))
    return out, [st.action.lstrip().startswith("print") for st in kept] + [False], \
           [st.scope_id for st in kept] + ["module"]

def layout(ir: ff.FlowIR):
    S = []
    emit_title(S, f"{ir.concept} — execution flow")
    src = [cl.text for cl in ir.lines]
    color_of = lambda i, t: (PAL["RED"] if ir.lines[i].role in ("BLOCK", "GUARD") else ir.scope(ir.lines[i].scope_id).color)
    # scope boxes: concentric per lexical func/target scope
    box = []
    for s in sorted((x for x in ir.scopes if x.kind in ("func", "target")), key=lambda s: s.depth):
        idx = [i for i, cl in enumerate(ir.lines) if cl.scope_id == s.id]
        if idx:
            box.append((s.depth * 28, idx[0], idx[-1], s.color))
    ln_y, code_bottom = emit_code(S, src, color_of, box_specs=box)

    emit_legend(S, 720, 86, "color -> scope", [(s.color, f"{ff.HEX2NAME[s.color]} - {s.name}") for s in ir.scopes])

    steps, is_print, sids = filtered_steps(ir)
    t_top = max(code_bottom + 56, 380)
    pos, _ = emit_timeline(S, 120, t_top, steps)
    term_x, term_w = 660, 360
    ty = t_top - 10
    tlines = [(l, PAL["ORANGE"] if "Hello" in l else PAL["GREEN"]) for l in (ir.stdout or ["(no output)"])]
    emit_terminal(S, term_x, ty, term_w, FAINT, tlines)
    for k, printed in enumerate(is_print):
        if printed:
            cx, cy = pos[k]
            x1 = min(cx + 28 + len(steps[k][0]) * 8.4, term_x - 16)
            S.append(("arrow", x1, cy, term_x - 4, ty + 40, ir.scope(sids[k]).color, 2, None))
    W = 1060
    H = max(t_top + len(steps) * STEP_H + 30, ty + 46 + len(tlines) * 22 + 44)
    return S, W, H

# ---- SVG emitter -------------------------------------------------------------
def to_svg(S, W, H):
    FONTS = {MONO: "ui-monospace,Menlo,Consolas,monospace", HAND: "Segoe Print,Comic Sans MS,sans-serif"}
    O, marks = [], set()
    for sh in S:
        if sh[0] == "rect":
            _, x, y, w, h, st, fl, sw, dash = sh
            d = f' stroke-dasharray="{dash}"' if dash else ""
            O.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="10" fill="{fl}" stroke="{st}" stroke-width="{sw}"{d}/>')
        elif sh[0] == "text":
            _, x, y, s, c, fs, font, anc = sh
            w = "700" if font == HAND and fs >= 20 else "400"
            O.append(f'<text x="{x:.0f}" y="{y:.0f}" font-family="{FONTS[font]}" font-size="{fs}" fill="{c}" text-anchor="{anc}" font-weight="{w}">{html.escape(s)}</text>')
        elif sh[0] == "circle":
            _, cx, cy, r, st, fl = sh
            O.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r}" fill="{fl}" stroke="{st}" stroke-width="2"/>')
        elif sh[0] == "arrow":
            _, x1, y1, x2, y2, c, sw, dash = sh
            marks.add(c); d = f' stroke-dasharray="{dash}"' if dash else ""
            O.append(f'<path d="M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}" fill="none" stroke="{c}" stroke-width="{sw}"{d} marker-end="url(#a{c.strip("#")})"/>')
    defs = "".join(f'<marker id="a{c.strip("#")}" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="{c}"/></marker>' for c in marks)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}">'
            f'<defs>{defs}</defs><rect width="{W}" height="{H:.0f}" fill="{BG}"/>' + "".join(O) + "</svg>")

# ---- Excalidraw emitter (hand-drawn look, editable) -------------------------
def to_excalidraw(S, W, H):
    random.seed(7); nz = lambda: random.randint(1, 2_000_000_000)
    FF = {MONO: 3, HAND: 1}
    els = []
    def common(**kw): return {"angle": 0, "fillStyle": "solid", "strokeWidth": kw.get("sw", 2),
        "strokeStyle": "solid", "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
        "roundness": kw.get("round", {"type": 3}), "seed": nz(), "version": 1, "versionNonce": nz(),
        "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False}
    for sh in S:
        if sh[0] == "rect":
            _, x, y, w, h, st, fl, sw, dash = sh
            els.append({"type": "rectangle", "id": f"r{len(els)}", "x": x, "y": y, "width": w, "height": h,
                        "strokeColor": st, "backgroundColor": fl, **common(sw=sw)})
        elif sh[0] == "circle":
            _, cx, cy, r, st, fl = sh
            els.append({"type": "ellipse", "id": f"c{len(els)}", "x": cx - r, "y": cy - r, "width": 2*r,
                        "height": 2*r, "strokeColor": st, "backgroundColor": fl, **common()})
        elif sh[0] == "text":
            _, x, y, s, c, fs, font, anc = sh
            w = max(len(s) * fs * 0.6, 10); x0 = x - (w/2 if anc == "middle" else 0)
            els.append({"type": "text", "id": f"t{len(els)}", "x": x0, "y": y - fs, "width": w,
                        "height": fs * 1.25, "strokeColor": c, "backgroundColor": "transparent",
                        "fontSize": fs, "fontFamily": FF[font], "text": s, "originalText": s,
                        "textAlign": "center" if anc == "middle" else "left", "verticalAlign": "top",
                        "containerId": None, "lineHeight": 1.25, **common(round=None)})
        elif sh[0] == "arrow":
            _, x1, y1, x2, y2, c, sw, dash = sh
            els.append({"type": "arrow", "id": f"a{len(els)}", "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1,
                        "strokeColor": c, "backgroundColor": "transparent", "points": [[0, 0], [x2 - x1, y2 - y1]],
                        "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
                        "startArrowhead": None, "endArrowhead": "arrow",
                        "strokeStyle": "dashed" if dash else "solid", **common(sw=sw, round={"type": 2})})
    return {"type": "excalidraw", "version": 2, "source": "figflow",
            "elements": els, "appState": {"gridSize": None, "viewBackgroundColor": BG}, "files": {}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code"); ap.add_argument("--intent", default="scope flow")
    ap.add_argument("--concept"); ap.add_argument("--out", default="figflow-out/figure")
    ap.add_argument("--fmt", choices=["svg", "excalidraw", "both"], default="both")
    a = ap.parse_args()
    code = pathlib.Path(a.code).read_text() if a.code else None
    if code is None:
        from run import DEMO as code
    out = ff.run(a.intent, code, concept=a.concept)
    S, W, H = layout(out["ir"])
    base = pathlib.Path(a.out); base.parent.mkdir(parents=True, exist_ok=True)
    if a.fmt in ("svg", "both"):
        p = base.with_suffix(".svg"); p.write_text(to_svg(S, W, H)); print(p)
    if a.fmt in ("excalidraw", "both"):
        p = base.with_suffix(".excalidraw"); p.write_text(json.dumps(to_excalidraw(S, W, H), indent=1)); print(p)

if __name__ == "__main__":
    main()
