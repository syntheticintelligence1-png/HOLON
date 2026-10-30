"""`holon derivation bend` (rules B1-B6) and `holon derivation bend-refine` (H1-H3, F1-F3); the contract is the
docstring of tests_m3/test_derivation_bend.py.

  bend         generates the consumer's Bend model (holon.derivation.bendgen) and its record model.json (the cut, the
               compiled functions, the templates, the type ids and layouts, the globals, the cones)
  bend-refine  runs the real blob layer on I85's 169 cases (a generated Go test beside I85's, offline: HypB's instance),
               checks it against I85's recorded decompressor answers and HypB on the canonical cases (hypb.json), then
               evaluates the compiled model on the 169 cases (node, holon/js/derivation_bend.mjs) with HypB's and
               HypT's instance answers and compares it with I85's replay report (refinement.json); --check re-evaluates
               from the recorded answers with no Go

Nothing here names a target: every function, field and path comes from the sidecars and the documents.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import OUT_GEN, DerivationError, Refused, dumps, load, ref
from . import bendgen as BG

DRIVER = Path(__file__).resolve().parents[1] / "js" / "derivation_bend.mjs"
BLOBLAYER_VERSION = "holon-derivation-bend-bloblayer/0.1"
HYPB_VERSION = "holon-derivation-bend-hypb/0.1"
REFINEMENT_VERSION = "holon-derivation-bend-refinement/0.1"
TEST_FILE = "holon_bloblayer_test.go"


# ====================================================================== the model (bend)
def layouts(C: BG.Compiler, roots: list) -> dict:
    out, todo = {}, list(roots)
    while todo:
        t = todo.pop()
        if t in out:
            continue
        if t == "math/big.Int":
            out[t] = {"kind": "big"}
            continue
        e = C.ty.entry(t)
        k = e.get("kind")
        if k == "basic":
            if e.get("boolean"):
                out[t] = {"kind": "bool"}
            elif e.get("string"):
                out[t] = {"kind": "string"}
            elif e.get("integer"):
                bits, uns = C.int_info(t)
                out[t] = {"kind": "int", "int": [bits, uns]}
            else:
                out[t] = {"kind": "basic"}
        elif k == "struct":
            fs = [[f["name"], f["type"]] for f in e.get("fields") or []]
            out[t] = {"kind": "struct", "fields": fs}
            todo += [ft for _n, ft in fs]
        elif k in ("array", "slice"):
            out[t] = {"kind": k, "elem": e["elem"], "byte": bool(C.ty.is_byte(e["elem"]))}
            if k == "array":
                out[t]["len"] = int(e["len"])
            todo.append(e["elem"])
        elif k == "pointer":
            out[t] = {"kind": "pointer", "elem": e["elem"]}
            todo.append(e["elem"])
        else:
            out[t] = {"kind": k or "other"}
    return dict(sorted(out.items()))


def cones(side: dict, info: dict, fns: dict) -> dict:
    out = {}
    for lid, terms in sorted(side["laws"].items()):
        obs: dict = {}
        for term in terms:
            for k, v in side["observables"][term].items():
                obs.setdefault(k, set())
                obs[k] |= set(v if isinstance(v, list) else [v])
        out[lid] = {"terms": terms, "functions": info["functions"], "blocks": fns,
                    "observables": {k: sorted(v, key=str) for k, v in sorted(obs.items())}}
    return out


def build_model(root: Path, side: dict, side_rel: str) -> dict:
    doc_rel = side["inputs"]["document"]
    section = load(root / doc_rel)["consumer"]
    try:
        text, info, C = BG.generate(section, side)
    except BG.Unsupported as e:
        raise Refused(f"unsupported: {e}")
    entry = section["entry"]
    recv_t = C.ty.pointee(C.raw[entry]["params"][0]["type"])
    batch_t = C.raw[entry]["params"][1]["type"]
    fns = {}
    for f in info["order"]:
        fg_blocks = sorted(b["index"] for b in C.raw[f]["blocks"])
        if f == entry:
            gone = set(info["cut"]["blocks"]) | {info["cut"]["boundary_block"]}
            fg_blocks = [b for b in fg_blocks if b not in gone]
        fns[f] = fg_blocks
    m_rel = side["outputs"]["model"]
    rec = {"model_version": BG.MODEL_VERSION, "sidecar": ref(root, side_rel), "document": ref(root, doc_rel),
           "model": {"path": m_rel, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()},
           "cut": info["cut"], "functions": info["functions"], "order": info["order"],
           "templates": info["templates"], "type_ids": info["type_ids"], "globals": info["globals"],
           "fuel": info["fuel"], "entry": {"function": entry, "receiver_type": recv_t, "batch_type": batch_t},
           "layouts": layouts(C, [recv_t, batch_t] + sorted(set(info["type_ids"].values()))),
           "cones": cones(side, info, fns), "unsupported": []}
    return {m_rel: text, side["outputs"]["model_info"]: dumps(rec)}


# ====================================================================== the compiled model and node
def cache_dir() -> Path:
    return Path(os.environ.get("HOLON_CACHE") or (Path.home() / ".holon" / "cache")) / "derivation_bend"


def compile_model(root: Path, model_rel: str) -> Path:
    """The model compiled to an ES module by the local Bend, cached by the model's sha256 (outside the repository)."""
    from .. import bend
    text = (root / model_rel).read_text(encoding="utf-8")
    d = cache_dir() / hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    mjs = d / "consumer.mjs"
    if mjs.is_file():
        return mjs
    d.mkdir(parents=True, exist_ok=True)
    (d / "consumer.bend").write_text(text, encoding="utf-8")
    r = bend.run(["consumer.bend", "-o", "consumer.part.mjs"], cwd=d, timeout=1800)
    if r.code != 0 or not (d / "consumer.part.mjs").is_file():
        raise DerivationError(f"bend could not compile the model: {r.out[-1500:]}")
    os.replace(d / "consumer.part.mjs", mjs)
    return mjs


def node_eval(mjs: Path, payload: dict, stack_mb: int = 2048) -> dict:
    """Run the driver on a payload in one node process, its stack raised (holon.bend's launcher pattern)."""
    from .. import bend
    node = bend.config().get("node", "node")
    node = shutil.which(node) or node
    launcher = [sys.executable, "-I", "-S", "-c", bend._STACK_LAUNCHER, str(stack_mb * 1024 * 1024)]
    p = subprocess.run(launcher + [node, f"--stack-size={stack_mb * 1000}", str(DRIVER)],
                       input=json.dumps({"module": str(mjs), **payload}), capture_output=True, text=True,
                       timeout=7200)
    if p.returncode != 0:
        raise DerivationError(f"the model's evaluation failed: {p.stderr[-2000:]}")
    return json.loads(p.stdout)["results"]


# ====================================================================== rendering an outcome
def _bytes_text(xs) -> str:
    return bytes(int(x) & 255 for x in xs).decode("utf-8", "surrogateescape")


class Render:
    def __init__(self, info: dict):
        self.t = info["templates"]
        self.tid = info["type_ids"]
        self.lay = info["layouts"]

    def int_of(self, v: dict, t: str | None) -> int:
        x = (int(v["h"]) << 32) | int(v["l"])
        info = (self.lay.get(t) or {}).get("int") if t else None
        if info and not info[1] and x >> 63:
            x -= 1 << 64
        return x

    def arg(self, verb: str, a) -> str:
        if a is None or a.get("$") == "VNil":
            return "<nil>" if verb in "vs" else f"%!{verb}(<nil>)"
        if a["$"] in ("VE", "VEs"):
            return self.text(a)
        if a["$"] == "VF":
            t = self.tid.get(str(a["t"]))
            v = a["v"]
            if v.get("$") == "VI":
                n = self.int_of(v, t)
                if verb in "vd":
                    return str(n)
                if verb == "x":
                    return format(n, "x") if n >= 0 else "-" + format(-n, "x")
            if v.get("$") in ("VE", "VEs", "VNil"):
                return self.arg(verb, v)
            if v.get("$") == "VStr":
                return _bytes_text(v["bs"])
            if v.get("$") == "VB":
                return "true" if v["b"] else "false"
        raise DerivationError(f"cannot render %{verb} of {str(a)[:120]}")

    def text(self, e) -> str:
        if e.get("$") == "VEs":
            return _bytes_text(e["s"])
        if e.get("$") != "VE":
            raise DerivationError(f"not an error value: {str(e)[:120]}")
        tpl = self.t[int(e["t"])]
        if tpl["kind"] == "literal":
            return tpl["text"]
        fmt, args, out, i, ai = tpl["text"], e.get("a") or [], [], 0, 0
        while i < len(fmt):
            c = fmt[i]
            if c != "%":
                out.append(c)
                i += 1
                continue
            i += 1
            verb = fmt[i] if i < len(fmt) else ""
            i += 1
            if verb == "%":
                out.append("%")
                continue
            if ai >= len(args):
                out.append(f"%!{verb}(MISSING)")
                continue
            out.append(self.arg(verb, args[ai]))
            ai += 1
        return "".join(out)

    def outcome(self, r: dict) -> dict:
        o = {"status": None, "error": None, "panic": None, "info": None}
        if r["out"] == "ORet":
            v = r["v"]
            if v is None or v.get("$") == "VNil":
                o["status"] = "ok"
            else:
                o["status"], o["error"] = "error", self.text(v)
        elif r["out"] == "OPan":
            o["status"], o["panic"] = "panic", self.text(r["v"])
        elif r["out"] == "OFuel":
            o["status"] = "fuel"
        else:
            o["status"], o["reason"] = "unsupported", str(r.get("v"))[:300]
        if r.get("unanswered"):
            o["status"] = "unanswered"
        return o


def cone_view(info, side: dict):
    """The receiver dump projected on the refinement's fields (rule F2), integers as integers."""
    if info is None:
        return None
    rf = side["refinement"]

    def num(x):
        return int(x) if isinstance(x, str) and x.lstrip("-").isdigit() else x
    out = {f: num(info.get(f)) for f in rf["fields"]}
    bf = rf["blocks"]["field"]
    bs = info.get(bf)
    out[bf] = None if bs is None else [{m: num((b or {}).get(m)) for m in rf["blocks"]["members"]} for b in bs]
    return out


# ====================================================================== the cases
def i85_side(root: Path, side: dict) -> dict:
    from . import sidecar as side85
    return side85(root, side["inputs"]["product_sidecar"])


def case_list(root: Path, side: dict, s85: dict) -> list:
    """[(id, batch JSON with the blobs as hex)] in I85's order (holon.derivation.refine.cases)."""
    from .refine import cases
    corpus = load(root / side["inputs"]["corpus"])
    product = load(root / f"{OUT_GEN}/product.json")
    return [(cid, batch) for cid, _src, batch in cases(s85, corpus, product)]


def with_field(batch: dict, path: list, value):
    import copy
    b = copy.deepcopy(batch)
    cur = b
    for name in path[:-1]:
        cur = cur.setdefault(name, {})
    cur[path[-1]] = value
    return b


def get_field(batch: dict, path: list):
    cur = batch
    for name in path:
        cur = (cur or {}).get(name)
    return cur


# ====================================================================== HypB's instance: the real blob layer (H1)
GO_BLOBLAYER = '''// GENERATED by holon.derivation.bendrun from a sidecar and a consumer document; do not edit.
package {pkg}

import (
\t"crypto/sha256"
\t"encoding/hex"
\t"encoding/json"
\t"fmt"
\t"os"
\t"strings"
\t"testing"

\tholonbl0 "{rpath}"
\tholonbl1 "{dpath}"
\tholonbl2 "{tpath}"
)

func holonBLRetrieve(b *holonbl2.{tname}) (out []byte, err error, p any) {{
\tdefer func() {{
\t\tif r := recover(); r != nil {{
\t\t\tp = r
\t\t}}
\t}}()
\tout, err = holonbl0.{rname}(b)
\treturn
}}

func holonBLDecompress(b []byte) (out []byte, err error, p any) {{
\tdefer func() {{
\t\tif r := recover(); r != nil {{
\t\t\tp = r
\t\t}}
\t}}()
\tout, err = holonbl1.{dname}(b)
\treturn
}}

func TestHolonBlobLayer(t *testing.T) {{
\traw, err := os.ReadFile(os.Getenv("{var}_IN"))
\tif err != nil {{
\t\tt.Skip("no input")
\t}}
\tvar in struct {{
\t\tCases []struct {{
\t\t\tID    string   `json:"id"`
\t\t\tBlobs []string `json:"blobs"`
\t\t}} `json:"cases"`
\t}}
\tif err := json.Unmarshal(raw, &in); err != nil {{
\t\tt.Fatal(err)
\t}}
\tout := map[string]any{{}}
\tfor _, c := range in.Cases {{
\t\tr := map[string]any{{"arg_sha256": nil}}
\t\tvar cat []byte
\t\tfailed := false
\t\tfor _, h := range c.Blobs {{
\t\t\tif !strings.HasPrefix(h, "0x") {{
\t\t\t\tt.Fatalf("a blob that is not 0x hex")
\t\t\t}}
\t\t\tbs, err := hex.DecodeString(h[2:])
\t\t\tif err != nil {{
\t\t\t\tt.Fatal(err)
\t\t\t}}
\t\t\tvar blob holonbl2.{tname}
\t\t\tif len(bs) != len(blob) {{
\t\t\t\tt.Fatalf("a blob of %d bytes", len(bs))
\t\t\t}}
\t\t\tcopy(blob[:], bs)
\t\t\tdata, e, p := holonBLRetrieve(&blob)
\t\t\tif p != nil {{
\t\t\t\tr["kind"], r["panic"] = "PlPanic", fmt.Sprint(p)
\t\t\t\tfailed = true
\t\t\t\tbreak
\t\t\t}}
\t\t\tif e != nil {{
\t\t\t\tr["kind"], r["error"] = "PlRet", e.Error()
\t\t\t\tfailed = true
\t\t\t\tbreak
\t\t\t}}
\t\t\tcat = append(cat, data...)
\t\t}}
\t\tif !failed {{
\t\t\tsum := sha256.Sum256(cat)
\t\t\tr["arg_sha256"] = hex.EncodeToString(sum[:])
\t\t\td, e, p := holonBLDecompress(cat)
\t\t\tswitch {{
\t\t\tcase p != nil:
\t\t\t\tr["kind"], r["panic"] = "PlPanic", fmt.Sprint(p)
\t\t\tcase e != nil:
\t\t\t\tr["kind"], r["error"] = "PlDErr", e.Error()
\t\t\tdefault:
\t\t\t\tr["kind"], r["nil"], r["bytes"] = "PlOk", d == nil, "0x"+hex.EncodeToString(d)
\t\t\t}}
\t\t}}
\t\tout[c.ID] = r
\t}}
\tb, _ := json.Marshal(out)
\tif err := os.WriteFile(os.Getenv("{var}_OUT"), b, 0o644); err != nil {{
\t\tt.Fatal(err)
\t}}
}}
'''


def go_test_text(section: dict, side: dict) -> str:
    from .goside import split_func, split_type
    bl = side["boundary"]["blob_layer"]
    rpath, rname = split_func(bl["retrieve"])
    dpath, dname = split_func(bl["decompress"])
    fn = section["functions"].get(bl["retrieve"])
    if fn is None or len(fn.get("params") or []) != 1 or not fn["params"][0]["type"].startswith("*"):
        raise Refused("the retrieve function's parameter is not one pointer")
    tpath, tname = split_type(fn["params"][0]["type"][1:])
    return GO_BLOBLAYER.format(pkg=section["package"]["name"], rpath=rpath, rname=rname, dpath=dpath, dname=dname,
                               tpath=tpath, tname=tname, var=side["go"]["env"])


def run_blob_layer(root: Path, side: dict, s85: dict, cases: list) -> dict:
    from .goside import Workspace
    section = load(root / side["inputs"]["document"])["consumer"]
    text = go_test_text(section, side)
    bf = s85["product"]["blobs_field"]
    with Workspace(root, s85, section) as ws:
        (ws.parent / "src" / section["package"]["dir"] / TEST_FILE).write_text(text, encoding="utf-8")
        out = ws.run(side["go"]["test"], side["go"]["env"],
                     {"cases": [{"id": cid, "blobs": get_field(b, bf) or []} for cid, b in cases]})
        return {"report_version": BLOBLAYER_VERSION, "target_commit": s85["target"]["commit"],
                "go_version": ws.go_version, "command": ws.command(side["go"]["test"]),
                "cases": {cid: out[cid] for cid, _b in cases}}


# ====================================================================== HypB's check (H2)
def canonical(s85: dict) -> dict:
    from .corpus import expand
    out = {}
    for c in s85["corpus"]["planted"] + s85["corpus"]["random"]:
        p = c.get("payload")
        if p and "raw" in p and c.get("blobs", 0) >= 1 and not c.get("set"):
            out[c["id"]] = expand(p["raw"])
    for tr in s85["corpus"]["product"]:
        for k, cm in enumerate(tr["commits"], start=1):
            p = cm.get("payload")
            if p and "raw" in p and cm.get("blobs", 0) >= 1 and not cm.get("set"):
                out[f"{tr['id']}/{k}"] = expand(p["raw"])
    return out


def hypb_record(root: Path, side: dict, side_rel: str, s85: dict, bl: dict) -> dict:
    env = load(root / side["inputs"]["environment"])["answers"]
    dec = [f for f, k in s85["extract"]["environment"].items() if k.get("kind") == "oracle"
           and f not in (side["boundary"]["decoder"]["function"],)]
    if len(dec) != 1:
        raise Refused("the product sidecar names other than one decompressor oracle")
    rec_answers = env.get(dec[0]) or {}
    canon = canonical(s85)
    cases, tot = {}, {"cases": 0, "recorded_agree": 0, "recorded_disagree": 0, "recorded_absent": 0,
                      "recorded_differs": 0, "canonical": len(canon), "hypb_holds": 0, "hypb_fails": 0}
    for cid, a in bl["cases"].items():
        tot["cases"] += 1
        rec = None
        if a.get("arg_sha256") is not None:
            r = rec_answers.get(a["arg_sha256"])
            rec = r is not None and ((a["kind"] == "PlOk" and r.get("bytes") == a.get("bytes"))
                                     or (a["kind"] == "PlDErr" and "error" in r and r["error"] in (a.get("error") or "")))
            tot["recorded_agree" if rec else "recorded_disagree"] += 1
            if not rec:      # H2 counts an absent answer as a disagreement; the two kinds are told apart here
                tot["recorded_absent" if r is None else "recorded_differs"] += 1
        hb = None
        if cid in canon:
            hb = a.get("kind") == "PlOk" and a.get("bytes") == "0x" + canon[cid].hex()
            tot["hypb_holds" if hb else "hypb_fails"] += 1
        cases[cid] = {"canonical": cid in canon, "kind": a.get("kind"), "recorded": rec, "hypb": hb}
    return {"hypb_version": HYPB_VERSION, "sidecar": ref(root, side_rel),
            "blob_layer": ref(root, side["outputs"]["blob_layer"]), "cases": dict(sorted(cases.items())),
            "totals": tot}


# ====================================================================== the refinement (F1-F3)
def refinement(root: Path, side: dict, side_rel: str, s85: dict, cases: list, bl: dict, info: dict) -> dict:
    env = load(root / side["inputs"]["environment"])["answers"]
    dt_answers = env.get(side["boundary"]["decoder"]["function"]) or {}
    real = load(root / side["inputs"]["replay"])["cases"]
    bf = s85["product"]["blobs_field"]
    payload_cases = []
    for cid, b in cases:
        blobs = get_field(b, bf) or []
        payload_cases.append({"id": cid, "batch": with_field(b, bf, [None] * len(blobs)),
                              "pl": bl["cases"][cid]})
    mjs = compile_model(root, side["outputs"]["model"])
    res = node_eval(mjs, {"layouts": info["layouts"], "batch_type": info["entry"]["batch_type"],
                          "recv_type": info["entry"]["receiver_type"], "nglobals": len(info["globals"]),
                          "dt": dt_answers, "cases": payload_cases})
    R = Render(info)
    out_cases, tot = {}, {"cases": 0, "agree": 0, "disagree": 0, "unsupported": 0, "fuel": 0, "unanswered": 0}
    for cid, _b in cases:
        o = R.outcome(res[cid])
        o["info"] = cone_view(res[cid].get("recv"), side)
        r = real[cid]
        agree = (o["status"] == r["status"] and o["error"] == r["error"] and o["panic"] == r["panic"]
                 and o["info"] == cone_view(r.get("info"), side))
        tot["cases"] += 1
        tot["agree" if agree else "disagree"] += 1
        for k in ("unsupported", "fuel", "unanswered"):
            if o["status"] == k:
                tot[k] += 1
        out_cases[cid] = {"model": {k: o.get(k) for k in ("status", "error", "panic", "info")}, "agree": agree}
        if o.get("reason"):
            out_cases[cid]["reason"] = o["reason"]
    return {"refinement_version": REFINEMENT_VERSION, "sidecar": ref(root, side_rel),
            "model": {"path": side["outputs"]["model"], "sha256": info["model"]["sha256"]},
            "blob_layer": ref(root, side["outputs"]["blob_layer"]), "cases": dict(sorted(out_cases.items())),
            "totals": tot}


def run_refine(root: Path, side: dict, side_rel: str, check: bool = False) -> dict:
    s85 = i85_side(root, side)
    info_rel = side["outputs"]["model_info"]
    if not (root / info_rel).is_file() or not (root / side["outputs"]["model"]).is_file():
        raise Refused("the model is missing (run holon derivation bend first)")
    info = load(root / info_rel)
    if info["model"]["sha256"] != hashlib.sha256((root / side["outputs"]["model"]).read_bytes()).hexdigest():
        raise Refused("model.json names another model")
    cases = case_list(root, side, s85)
    bl_rel = side["outputs"]["blob_layer"]
    if check:
        bl = load(root / bl_rel)
        bl_text = dumps(bl)
    else:
        bl = run_blob_layer(root, side, s85, cases)
        bl_text = dumps(bl)
        (root / bl_rel).parent.mkdir(parents=True, exist_ok=True)
        (root / bl_rel).write_text(bl_text, encoding="utf-8")
    outs = {bl_rel: bl_text,
            side["outputs"]["hypb"]: dumps(hypb_record(root, side, side_rel, s85, bl)),
            side["outputs"]["refinement"]: dumps(refinement(root, side, side_rel, s85, cases, bl, info))}
    return outs
