"""`holon termsize`: the term-size measures of the I30 laws (I30; the contract is the docstring of
tests_m3/test_sort_types.py, the termsize CLI paragraph, and spec/M3/lib/term_size.json, which defines both measures).

  python -m holon termsize --milestone M3 [--root DIR] [--out PATH]

writes <out, default gen/<M>/sorts/term_size.json>:
  {"document": "term_size", "milestone", "sidecar_sha256", "laws": {law_id: {"status", "law_terms", "files": {path:
   terms}, "cone_chars": int | null}}, "ratio": {"site", "typed_law", "typed_laws_file", "baseline_laws_file",
   "typed_cone_chars", "baseline_cone_chars", "value"}}
and the baseline it measures against: the untyped model (`holon model --untyped`) under gen/<M>/sorts/untyped/models/
and the baseline law, I15's site form of the sidecar's ratio site over it,
gen/<M>/sorts/untyped/laws/<I15's law id>/LAWS.bend (the law, or its counter-law when the typed law is REFUTED: the two
files state the same site's obligation in one form each).

law_terms(L) = terms(the `law` blocks of L's LAWS.bend) + the largest terms(f) over the PROOF.bend files that discharge
L (every PROOF.bend under gen/<M>/proofs/<id>/ and gen/<M>/<id>/nonvac/PROOF.bend when it exists); an UNKNOWN law
counts its statement only. cone_chars(L) is I12-P1's measure over the one model module its law file imports as M.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUBFORMS = ("as_member", "realize", "reinterpret")


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Measure:
    def __init__(self, side: dict):
        self.side = side
        self.ph = side["placeholder"]
        self.lit = re.compile(side["literal_list"])
        self.tok = re.compile(side["tokenizer"])

    @staticmethod
    def strip(text: str) -> str:
        keep = []
        for line in text.splitlines():
            s = line.lstrip()
            if s.startswith("#") or s.startswith("import "):
                continue
            keep.append(line.split("#", 1)[0])
        return "\n".join(keep)

    def terms(self, text: str) -> int:
        t, prev = self.strip(text), None
        while prev != t:
            prev, t = t, self.lit.sub(self.ph, t)
        return len(self.tok.findall(t)) + t.count(self.ph)

    def law_blocks(self, text: str) -> str:
        parts = re.split(r"(?m)^(?=\S)", self.strip(text))
        return "".join(p for p in parts if p.startswith("law "))


def cone_chars(laws_file: Path) -> int:
    from .. import bindings as B
    text = laws_file.read_text(encoding="utf-8")
    imports = re.findall(r"^import\s+(\S+)(?:\s+as\s+(\S+))?\s*$", text, re.M)
    others = [(p, a) for p, a in imports if p != "Base"]
    model = (laws_file.parent / others[0][0]).resolve()
    entries = B.kernel_entries(model)
    cone = B.kernel_cone(text, entries)
    stmt = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    return sum(len(entries[d]) for d in cone) + len(stmt)


def baseline(milestone: str, root: Path, typed_law_file: Path, site: dict) -> tuple[Path, Path]:
    """The untyped model and I15's site-form law of the ratio site over it (the typed law's form: law or
    counter-law)."""
    from ..gen.mlaws import law_name
    from .model3 import documents_of, generate, importable, init_of, model_name, write_model_file
    from .proofs3 import HEADER, rel_import
    from .sites import ghost_x, law_id as site_law_id
    udir = root / "gen" / milestone / "sorts" / "untyped"
    doc_rel = next(d for d in documents_of(milestone, root, None) if model_name(d) == site["model"])
    init = init_of(milestone, root, None, doc_rel)
    text, mm = generate(milestone, root, doc_rel, typed=False, init=init)
    mp = write_model_file(udir / "models", model_name(doc_rel), text)
    plain = udir / "models" / importable(model_name(doc_rel))
    lid = site_law_id(site["id"])
    x = ghost_x(lid)
    counter = bool(re.search(r"(?m)^law cl_", typed_law_file.read_text(encoding="utf-8")))
    hashes = mm.hashes
    tb = [("kh" if h == "keccak256" else "sh") for h in hashes]
    kw, q = ("exs", "") if counter else ("for", "+")
    lp = udir / "laws" / lid / "LAWS.bend"
    lp.parent.mkdir(parents=True, exist_ok=True)
    lines = [HEADER, f"# the untyped baseline of {site['id']}: I15's site form (the minuend is at least the subtrahend "
             "at every hit) over the untyped model", "import Base", f"import {rel_import(lp.parent, plain)} as M", "",
             f"law {law_name(lid, counter)}:"]
    lines += [f"  {kw} {q}{n}: List<&2, M.HKB>" for n in tb]
    lines += [f"  {kw} {q}s: M.HSt", f"  {kw} r_s: M.Reach<{''.join(n + ', ' for n in tb)}s>", f"  {kw} {q}a: M.HAct",
              f"  {{M.site_{x}(a, s{''.join(', ' + n for n in tb)}) {'!=' if counter else '=='} True{{}} : Bool}}"]
    lp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mp, lp


def compute(milestone: str, root: Path) -> dict:
    root = Path(root)
    side_p = root / "spec" / milestone / "lib" / "term_size.json"
    side = json.loads(side_p.read_text(encoding="utf-8"))
    ms = Measure(side)
    dv = json.loads((root / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    laws = {}
    gen = root / "gen" / milestone
    for e in sorted(dv["laws"], key=lambda e: e["law_id"]):
        if e.get("rule") != "SORT" or e.get("subform") not in SUBFORMS:
            continue
        lid = e["law_id"]
        rp = root / "results" / milestone / f"{lid}.json"
        status = json.loads(rp.read_text())["status"] if rp.is_file() else "UNKNOWN"
        files = {}
        if status in ("PROVED", "REFUTED"):
            for q in sorted((gen / "proofs" / lid).rglob("PROOF.bend")):
                files[q.relative_to(root).as_posix()] = ms.terms(q.read_text(encoding="utf-8"))
            nv = gen / lid / "nonvac" / "PROOF.bend"
            if nv.is_file():
                files[nv.relative_to(root).as_posix()] = ms.terms(nv.read_text(encoding="utf-8"))
        lf = gen / "laws" / lid / "LAWS.bend"
        lt = ms.terms(ms.law_blocks(lf.read_text(encoding="utf-8"))) if lf.is_file() else 0
        laws[lid] = {"status": status, "law_terms": lt + (max(files.values()) if files else 0), "files": files,
                     "cone_chars": cone_chars(lf) if lf.is_file() else None}
    ratio = None
    sid = side.get("ratio_site")
    asg = json.loads((gen / "sorts" / "assignment.json").read_text(encoding="utf-8"))
    site = next((s for s in asg.get("sites") or [] if s.get("id") == sid), None)
    typed = next((e for e in dv["laws"] if e.get("subform") == "realize" and (e.get("basis") or {}).get("site_id") == sid),
                 None)
    if site is not None and typed is not None:
        tl = gen / "laws" / typed["law_id"] / "LAWS.bend"
        _mp, bl = baseline(milestone, root, tl, site)
        tc, bc = cone_chars(tl), cone_chars(bl)
        ratio = {"site": sid, "typed_law": typed["law_id"], "typed_laws_file": tl.relative_to(root).as_posix(),
                 "baseline_laws_file": bl.relative_to(root).as_posix(), "typed_cone_chars": tc,
                 "baseline_cone_chars": bc, "value": round(tc / bc, 4) if bc else None}
    return {"document": "term_size", "milestone": milestone,
            "sidecar_sha256": hashlib.sha256(side_p.read_bytes()).hexdigest(), "laws": laws, "ratio": ratio}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon termsize")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        doc = compute(a.milestone, root)
    except (OSError, ValueError, KeyError) as e:
        print(f"holon termsize: {e}", file=sys.stderr)
        return 1
    out = Path(a.out) if a.out else root / "gen" / a.milestone / "sorts" / "term_size.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumps(doc), encoding="utf-8")
    for lid, x in sorted(doc["laws"].items()):
        print(f"holon termsize: {lid}: {x['status']}, {x['law_terms']} terms, cone {x['cone_chars']}")
    if doc["ratio"]:
        r = doc["ratio"]
        print(f"holon termsize: ratio {r['value']} ({r['typed_cone_chars']} typed / {r['baseline_cone_chars']} untyped)")
    return 0
