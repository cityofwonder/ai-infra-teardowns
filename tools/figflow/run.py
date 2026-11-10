#!/usr/bin/env python3
"""
figflow CLI — code -> themed execution-flow prompt (-> optional Gemini PNGs).

  # 1) prompt only (no SDK/key needed) — inspect what will be sent to Gemini
  python run.py --code snippet.py --intent "decorator scope" --prompt-only

  # 2) generate N candidate PNGs (needs: pip install google-genai + GEMINI_API_KEY)
  GEMINI_API_KEY=... python run.py --code snippet.py --intent "auth gate" \
      --generate -n 3 --out ./out --model gemini-2.5-flash-image

With no --code, runs the built-in decorator demo.
"""
import argparse, sys, pathlib
import figflow as ff

DEMO = '''
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", help="path to a runnable .py snippet (default: demo)")
    ap.add_argument("--intent", default="scope flow", help="natural-language intent -> figure-type")
    ap.add_argument("--concept", help="title concept (default: figure-type)")
    ap.add_argument("--prompt-only", action="store_true", help="print the prompt, do not call Gemini")
    ap.add_argument("--generate", action="store_true", help="call Gemini and save PNGs")
    ap.add_argument("-n", type=int, default=3, help="number of candidate images")
    ap.add_argument("--out", default="./figflow-out", help="output dir for PNGs")
    ap.add_argument("--model", default="gemini-2.5-flash-image")
    args = ap.parse_args()

    code = pathlib.Path(args.code).read_text() if args.code else DEMO
    out = ff.run(args.intent, code, concept=args.concept)
    sys.stderr.write(f"[figflow] figure_type = {out['figure_type']}\n")

    if args.generate and not args.prompt_only:
        paths = ff.backend_gemini(out["prompt"], args.out, n=args.n, model=args.model)
        if paths:
            print("\n".join(paths))
        else:
            sys.stderr.write("[figflow] no image parts returned — check model id / quota\n")
            sys.exit(2)
    else:
        print(out["prompt"])

if __name__ == "__main__":
    main()
