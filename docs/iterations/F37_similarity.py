"""F37 similarity measurement (run only after the clean-room implementation is committed).

For each (holon file, holon function, instrument function) pair: difflib.SequenceMatcher ratio over
(1) the Python token streams (NAME/OP/NUMBER/STRING tokens; comments, docstrings, NEWLINE/INDENT dropped) and
(2) the raw source text of the function. Old = holon file at BASE commit, new = holon file at HEAD.
Usage: python similarity.py REPO BASE HEAD
"""
import ast
import difflib
import io
import subprocess
import sys
import tokenize

REPO, BASE, HEAD = sys.argv[1:4]
INSTR = "tests_m4/_i48.py"
PAIRS = [("holon/eval/agree.py", "kappa", "kappa"),
         ("holon/eval/agree.py", "final_label", "final_label"),
         ("holon/eval/agree.py", "build", "final_label"),
         ("holon/eval/label.py", "parse_response", "parse_response")]


def blob(rev, path):
    return subprocess.run(["git", "-C", REPO, "show", f"{rev}:{path}"], capture_output=True, text=True).stdout


def funcs(src):
    out = {}
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            seg = ast.get_source_segment(src, node)
            doc = ast.get_docstring(node, clean=False)
            out.setdefault(node.name, (seg, doc))
    return out


def toks(seg, doc):
    res = []
    for t in tokenize.generate_tokens(io.StringIO(seg).readline):
        if t.type in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
            res.append(t.string)
        elif t.type == tokenize.STRING:
            if doc is not None and t.string.strip("\"'rbuf") .strip() == doc.strip():
                continue
            res.append(t.string)
    return res


instr = funcs(blob(HEAD, INSTR))
rows = []
for path, hf, inf in PAIRS:
    for tag, rev in (("old", BASE), ("new", HEAD)):
        h = funcs(blob(rev, path))
        if hf not in h or inf not in instr:
            rows.append((path, hf, inf, tag, None, None))
            continue
        a, b = h[hf], instr[inf]
        tr = difflib.SequenceMatcher(None, toks(*a), toks(*b), autojunk=False).ratio()
        sr = difflib.SequenceMatcher(None, a[0], b[0], autojunk=False).ratio()
        rows.append((path, hf, inf, tag, round(tr, 3), round(sr, 3)))
print("file\tholon_func\tinstrument_func\tversion\ttoken_ratio\ttext_ratio")
for r in rows:
    print("\t".join(str(x) for x in r))
