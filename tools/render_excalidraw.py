#!/usr/bin/env python3
"""
CVE Taint-Graph renderer — emits an Excalidraw (.excalidraw) scene.

PER-CVE EDIT POINTS (only these two data blocks change per CVE):
  * `spine` : source->sink nodes. Each = (id, border_color, bg_color, role,
              "file:line", code_lines, stroke_w). code_lines is a list of lines;
              each line is a list of (segment, is_taint) tuples. Set is_taint=1
              on the tainted token(s) to get the red text + pink highlight.
  * `isl`   : the auth-gated / unreachable sink island (fn, "file:line", exec_line).
Everything else (schema, theme, layout math) is fixed — see cve-taint-graph.md.

Usage:  python render_excalidraw.py <out.excalidraw>
Open:   drag the file onto https://excalidraw.com  (or the VS Code "Excalidraw" ext)
"""

import json,random,sys
random.seed(32483)
def nz(): return random.randint(1,2_000_000_000)
els=[]
CW=8.4; LH=20; FS=14
DARK="#343a40"; TAINT="#e03131"; HL="#ffc9c9"; BLUE="#1971c2"; GREY="#868e96"
SRC="#e8590c"; SINKC="#e03131"; AUTHC="#2b8a3e"
def base(t,id,x,y,w,h,stroke,bg,**kw):
    return {"type":t,"id":id,"x":x,"y":y,"width":w,"height":h,"angle":0,"strokeColor":stroke,
       "backgroundColor":bg,"fillStyle":kw.get("fill","solid"),"strokeWidth":kw.get("sw",2),
       "strokeStyle":kw.get("ss","solid"),"roughness":kw.get("rough",1),"opacity":kw.get("op",100),
       "groupIds":[],"frameId":None,"roundness":kw.get("round",{"type":3}),"seed":nz(),"version":1,
       "versionNonce":nz(),"isDeleted":False,"boundElements":kw.get("be",[]),"updated":1,
       "link":None,"locked":False}
def text(id,x,y,w,txt,color,fs=FS,align="left",container=None):
    els.append({"type":"text","id":id,"x":x,"y":y,"width":w,"height":fs*1.25,"angle":0,
        "strokeColor":color,"backgroundColor":"transparent","fillStyle":"solid","strokeWidth":2,
        "strokeStyle":"solid","roughness":1,"opacity":100,"groupIds":[],"frameId":None,"roundness":None,
        "seed":nz(),"version":1,"versionNonce":nz(),"isDeleted":False,"boundElements":[],"updated":1,
        "link":None,"locked":False,"fontSize":fs,"fontFamily":3,"text":txt,"textAlign":align,
        "verticalAlign":"top","containerId":container,"originalText":txt,"lineHeight":1.25})
OW=500
def node(id,x,y,role,loc,lines,border,bg,sw=2):
    code_h=len(lines)*LH+16; oh=56+code_h+14
    els.append(base("rectangle",id,x,y,OW,oh,border,bg,sw=sw))
    text(id+"_r",x+16,y+12,OW-32,role,border if border in (SRC,SINKC) else "#495057",fs=12)
    text(id+"_l",x+16,y+30,OW-32,loc,BLUE,fs=12)
    cx,cy=x+16,y+54; cw=OW-32
    els.append(base("rectangle",id+"_box",cx,cy,cw,code_h,"#ced4da","#f8f9fa",sw=1))
    for i,segs in enumerate(lines):
        col=0; ly=cy+8+i*LH
        for seg,taint in segs:
            sx=cx+10+col*CW
            if taint:
                els.append(base("rectangle",id+f"_h{i}_{col}",sx-2,ly-1,len(seg)*CW+4,LH-3,"transparent",HL,sw=1,op=55,round={"type":0}))
            text(id+f"_t{i}_{col}",sx,ly,len(seg)*CW+6,seg,TAINT if taint else DARK)
            col+=len(seg)
    return y,oh
def arrow(id,sid,did,x,y1,y2,color,label):
    a=base("arrow",id,x,y1,0,y2-y1,color,"transparent",sw=2,round={"type":2})
    a.update({"points":[[0,0],[0,y2-y1]],"lastCommittedPoint":None,
        "startBinding":{"elementId":sid,"focus":0,"gap":6},
        "endBinding":{"elementId":did,"focus":0,"gap":6},
        "startArrowhead":None,"endArrowhead":"arrow"}); els.append(a)
    w=len(label)*CW+14; lx=x-w/2; ly=(y1+y2)/2
    els.append(base("rectangle",id+"_bg",lx-5,ly-13,w+10,26,"transparent","#ffffff",sw=1,round={"type":1}))  # label backing
    text(id+"_lab",lx,ly-9,w,label,color,fs=13,align="center")

X=120; y=70; pos={}
spine=[
 ("n1",SRC,"#fff5f5","SOURCE · HTTP body (unauthenticated)","api/v1/validate.py:12-15",
   [[('@router.post("/code")   ',0),('# no auth dep',0)],
    [('async def post_validate_code(',0),('code',1),(': Code):',0)],
    [('    errors = validate_code(',0),('code.code',1),(')',0)]],2.5),
 ("n2",DARK,"#ffffff","taint enters · parse to AST","utils/validate.py:24,30",
   [[('def validate_code(',0),('code',1),('):',0)],[('    ...',0)],
    [('    tree = ast.parse(',0),('code',1),(')',0)]],2),
 ("n3",DARK,"#ffffff","select function definitions","utils/validate.py:53-54",
   [[('    for ',0),('node',1),(' in ',0),('tree',1),('.body:',0)],
    [('        if isinstance(',0),('node',1),(', ast.FunctionDef):',0)]],2),
 ("n4",DARK,"#ffffff","compile the definition","utils/validate.py:55",
   [[('        ',0),('code_obj',1),(' = compile(',0)],
    [('            ast.Module([',0),('node',1),(']), "<string>", "exec")',0)]],2),
 ("n5",SINKC,"#fff5f5","SINK · arbitrary code execution (RCE)","utils/validate.py:57",
   [[('            exec(',0),('code_obj',1),(')',0)]],2.5),
]
for nid,bd,bg,role,loc,lines,sw in spine:
    yy,hh=node(nid,X,y,role,loc,lines,bd,bg,sw); pos[nid]=(yy,hh); y=yy+hh+70
for s,d,lab,col in [("n1","n2","code.code  →  code",SRC),("n2","n3","tree  (AST)",TAINT),
       ("n3","n4","node  (FunctionDef)",TAINT),("n4","n5","code_obj",TAINT)]:
    arrow("a_"+s+d,s,d,X+OW/2,pos[s][0]+pos[s][1],pos[d][0],col,lab)

# ---- island v3: clearer meaning ----
IX=700; IW=380; iy=150
CONT_H=4*94+96
els.append(base("rectangle","island",IX-20,iy-96,IW+40,CONT_H,GREY,"#f1f3f5",sw=1.5,ss="dashed",fill="solid",op=55))
text("island_h1",IX-8,iy-88,IW+20,"AUTH-GATED exec() SINKS  ·  NOT this CVE",AUTHC,fs=13)
text("island_h2",IX-8,iy-66,IW+20,"same exec() calls, but reached only via",GREY,fs=11)
text("island_h3",IX-8,iy-50,IW+20,"authenticated component execution — the",GREY,fs=11)
text("island_h4",IX-8,iy-34,IW+20,"/validate/code endpoint never calls these.",GREY,fs=11)
isl=[("execute_function()","utils/validate.py:113","exec(code_obj, ...)"),
     ("eval_function()","utils/validate.py:71","exec(function_string, ...)"),
     ("create_class()","utils/validate.py:262-268","exec(class_code / function_code)"),
     ("compile_class_code()","utils/validate.py:312","exec(compiled_class, ...)")]
yy=iy
for i,(fn,loc,ex) in enumerate(isl):
    els.append(base("rectangle",f"i{i}",IX,yy,IW,80,GREY,"#ffffff",sw=1.2,op=95))
    text(f"i{i}_f",IX+14,yy+12,IW-120,fn,"#495057",fs=13)
    # "auth" tag pill, right aligned
    tagw=92; tx=IX+IW-tagw-12
    els.append(base("rectangle",f"i{i}_tag",tx,yy+10,tagw,22,AUTHC,"#ebfbee",sw=1,round={"type":3}))
    text(f"i{i}_tagt",tx,yy+13,tagw,"🔒 needs auth",AUTHC,fs=11,align="center")
    text(f"i{i}_l",IX+14,yy+34,IW-28,loc,GREY,fs=11)
    text(f"i{i}_x",IX+14,yy+52,IW-28,ex,"#868e96",fs=12)
    yy+=94

doc={"type":"excalidraw","version":2,"source":"langflow-study CVE pipeline v3",
     "elements":els,"appState":{"gridSize":None,"viewBackgroundColor":"#ffffff"},"files":{}}
json.dump(doc,open(sys.argv[1],"w"),indent=1)
print("elements:",len(els))
