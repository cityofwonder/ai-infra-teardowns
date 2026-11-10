#!/usr/bin/env python3
"""
CVE Taint-Graph — SVG renderer (GitHub-embeddable twin of render_excalidraw.py).

Same `spine` / `isl` data model as render_excalidraw.py, but emits a static .svg
so the diagram renders inline in a GitHub README (Excalidraw files do not).
Edit the two data blocks to match render_excalidraw.py; keep them in sync.

Usage:  python render_svg.py <out.svg>
"""
import sys, html

# ---- theme (mirrors render_excalidraw.py) ----
DARK="#343a40"; TAINT="#e03131"; HL="#ffc9c9"; BLUE="#1971c2"; GREY="#868e96"
SRC="#e8590c"; SINKC="#e03131"; AUTHC="#2b8a3e"
CW=8.4; LH=20; FS=14; OW=500; MONO="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# ---- PER-CVE data (keep in sync with render_excalidraw.py) ----
spine=[
 ("SOURCE · HTTP body (unauthenticated)","api/v1/validate.py:12-15",
   [[('@router.post("/code")   ',0),('# no auth dep',0)],
    [('async def post_validate_code(',0),('code',1),(': Code):',0)],
    [('    errors = validate_code(',0),('code.code',1),(')',0)]],SRC,"#fff5f5",2.5),
 ("taint enters · parse to AST","utils/validate.py:24,30",
   [[('def validate_code(',0),('code',1),('):',0)],[('    ...',0)],
    [('    tree = ast.parse(',0),('code',1),(')',0)]],DARK,"#ffffff",1.5),
 ("select function definitions","utils/validate.py:53-54",
   [[('    for ',0),('node',1),(' in ',0),('tree',1),('.body:',0)],
    [('        if isinstance(',0),('node',1),(', ast.FunctionDef):',0)]],DARK,"#ffffff",1.5),
 ("compile the definition","utils/validate.py:55",
   [[('        ',0),('code_obj',1),(' = compile(',0)],
    [('            ast.Module([',0),('node',1),(']), "<string>", "exec")',0)]],DARK,"#ffffff",1.5),
 ("SINK · arbitrary code execution (RCE)","utils/validate.py:57",
   [[('            exec(',0),('code_obj',1),(')',0)]],SINKC,"#fff5f5",2.5),
]
edges=["code.code  →  code","tree  (AST)","node  (FunctionDef)","code_obj"]
isl=[("execute_function()","utils/validate.py:113","exec(code_obj, ...)"),
     ("eval_function()","utils/validate.py:71","exec(function_string, ...)"),
     ("create_class()","utils/validate.py:262-268","exec(class_code / function_code)"),
     ("compile_class_code()","utils/validate.py:312","exec(compiled_class, ...)")]

def esc(s): return html.escape(s, quote=True)
out=[]
def rect(x,y,w,h,stroke,fill,sw=1.5,dash=None,rx=8,op=1.0):
    d=f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"{d}/>')
def txt(x,y,s,color,fs=FS,anchor="start",weight=400):
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" font-size="{fs}" '
               f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')

X=120; y=70; centers=[]
for role,loc,lines,border,bg,sw in spine:
    code_h=len(lines)*LH+16; oh=56+code_h+14
    rect(X,y,OW,oh,border,bg,sw=sw)
    txt(X+16,y+26,role, border if border in (SRC,SINKC) else "#495057", fs=12, weight=600)
    txt(X+16,y+42,loc,BLUE,fs=12)
    cx,cy=X+16,y+54; cw=OW-32
    rect(cx,cy,cw,code_h,"#ced4da","#f8f9fa",sw=1,rx=4)
    for i,segs in enumerate(lines):
        col=0; ly=cy+8+i*LH
        for seg,taint in segs:
            sx=cx+10+col*CW
            if taint:
                rect(sx-2,ly,len(seg)*CW+4,LH-4,"none",HL,sw=0,rx=2,op=0.6)
            txt(sx,ly+14,seg,TAINT if taint else DARK,fs=FS)
            col+=len(seg)
    centers.append((y,oh)); y=y+oh+70

# edges between spine nodes
for i,lab in enumerate(edges):
    y1=centers[i][0]+centers[i][1]; y2=centers[i+1][0]; mx=X+OW/2
    col=SRC if i==0 else TAINT
    out.append(f'<line x1="{mx}" y1="{y1}" x2="{mx}" y2="{y2-10}" stroke="{col}" stroke-width="2"/>')
    out.append(f'<path d="M{mx-5},{y2-10} L{mx+5},{y2-10} L{mx},{y2-1} Z" fill="{col}"/>')
    w=len(lab)*CW+14; ly=(y1+y2)/2
    rect(mx-w/2-5,ly-13,w+10,26,"#e9ecef","#ffffff",sw=1,rx=6)
    txt(mx,ly+4,lab,col,fs=13,anchor="middle",weight=600)

# island
IX=700; IW=380; iy=150
cont_h=4*94+96
rect(IX-20,iy-96,IW+40,cont_h,GREY,"#f1f3f5",sw=1.5,dash="6 5",op=0.7)
txt(IX-8,iy-74,"AUTH-GATED exec() SINKS  ·  NOT this CVE",AUTHC,fs=13,weight=600)
txt(IX-8,iy-54,"same exec() calls, but reached only via",GREY,fs=11)
txt(IX-8,iy-39,"authenticated component execution — the",GREY,fs=11)
txt(IX-8,iy-24,"/validate/code endpoint never calls these.",GREY,fs=11)
yy=iy
for fn,loc,ex in isl:
    rect(IX,yy,IW,80,GREY,"#ffffff",sw=1.2,rx=8)
    txt(IX+14,yy+26,fn,"#495057",fs=13,weight=600)
    tagw=104; tx=IX+IW-tagw-12
    rect(tx,yy+10,tagw,22,AUTHC,"#ebfbee",sw=1,rx=8)
    txt(tx+tagw/2,yy+25,"[needs auth]",AUTHC,fs=11,anchor="middle",weight=600)
    txt(IX+14,yy+48,loc,GREY,fs=11)
    txt(IX+14,yy+66,ex,"#868e96",fs=12)
    yy+=94

W=IX+IW+40; H=max(y, yy)+30
svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="{MONO}">\n'
     f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n' + "\n".join(out) + "\n</svg>\n")
open(sys.argv[1],"w").write(svg)
print("svg:",sys.argv[1],f"{W}x{H}")
