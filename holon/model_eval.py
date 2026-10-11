"""Evaluate the compiled Bend model from Python (M0_SPEC section 5, BEND_PRIMER 5.6).

The model is generated into build/, compiled with the pinned Bend to an ES
module, and executed in node with batched jobs. Python only formats inputs and
outputs; every value is computed by the compiled model.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from . import facts as facts_mod
from .facts import ROOT, load_facts
from .gen_model import bend_model

MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"


def config(root=None) -> dict:
    p = (Path(root) if root else ROOT) / "config" / "holon.json"
    return json.loads(p.read_text())


def bend_cmd(cfg=None) -> list:
    env = os.environ.get("HOLON_BEND_CMD")
    if env:
        return shlex.split(env)
    return list((cfg or config())["bend"]["cmd"])


def run_bend(args, cwd=None, timeout=None, cfg=None) -> tuple[int, str, float]:
    """Run the pinned Bend; returns (exit_code, combined output, seconds)."""
    import time
    cfg = cfg or config()
    cmd = bend_cmd(cfg) + [str(a) for a in args]
    t = timeout or int(cfg["bend"].get("timeout_s", 180))
    t0 = time.monotonic()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)
    return p.returncode, p.stdout + p.stderr, time.monotonic() - t0


def bend_version(cfg=None) -> str:
    code, out, _ = run_bend(["version"], cfg=cfg)
    if code != 0:
        raise RuntimeError(f"bend version failed: {out}")
    return out.strip().split()[-1]


def first_marker(out: str) -> str:
    line = out.strip().splitlines()[0] if out.strip() else ""
    if MARK_OK in line:
        return MARK_OK
    if MARK_FAIL in line:
        return MARK_FAIL
    return line


RUNNER_JS = """\
import M from "./model.mjs";
import {readFileSync, writeFileSync} from "fs";
const WIDTHS = __WIDTHS__;
function toList(a){return a.reduceRight((t,x)=>({$:"Con",head:x,tail:t}),{$:"Nil"});}
function fromList(l){const o=[];while(l&&l.$==="Con"){o.push(l.head);l=l.tail;}return o;}
function hexB(a){return "0x"+a.map(x=>x.toString(16).padStart(2,"0")).join("");}
function unhex(s){const a=[];for(let i=2;i<s.length;i+=2)a.push(parseInt(s.slice(i,i+2),16));return a;}
function inVal(ty,v){
  if(ty==="Bytes")return toList(unhex(v));
  if(ty==="Header"){const o={$:"Hdr"};for(const f in WIDTHS){const bs=unhex(v[f]);for(let k=0;k<WIDTHS[f];k++)o[f+"_"+k]=bs[k];}return o;}
  throw new Error("bad binder type "+ty);
}
function outVal(v){
  if(v===true||v===false)return v;
  if(v&&v.$==="True")return true;
  if(v&&v.$==="False")return false;
  if(v&&v.$==="None")return null;
  if(v&&v.$==="Some")return outVal(v.value);
  if(v&&v.$==="Con"){const a=fromList(v);if(a.length&&a[0]&&a[0].$==="Con")return a.map(x=>hexB(fromList(x)));return hexB(a);}
  if(v&&v.$==="Nil")return "0x";
  if(typeof v==="bigint")return Number(v);
  throw new Error("cannot encode "+JSON.stringify(v));
}
function ev(t,env){
  if("var" in t)return env[t.var];
  if("bytes" in t)return toList(unhex(t.bytes));
  if("field" in t){const r=ev(t.of,env);const a=[];for(let k=0;k<WIDTHS[t.field];k++)a.push(r[t.field+"_"+k]);return toList(a);}
  if("call" in t)return M[t.call](...t.args.map(x=>ev(x,env)));
  if("some" in t)return {$:"Some",value:ev(t.some,env)};
  throw new Error("bad term "+JSON.stringify(t));
}
const jobs=JSON.parse(readFileSync(process.argv[2],"utf8"));
const outs=jobs.map(j=>{
  if(j.call){return {out:outVal(M[j.call](inVal(j.arg_type,j.arg)))};}
  const env={};for(const k in j.binders)env[k]=inVal(j.binders[k].type,j.binders[k].value);
  if(j.eq){const l=ev(j.eq[0],env),r=ev(j.eq[1],env);const lj=outVal(l),rj=outVal(r);return {lhs:lj,rhs:rj,eq:JSON.stringify(lj)===JSON.stringify(rj)};}
  return {out:outVal(ev(j.term,env))};
});
writeFileSync(process.argv[3],JSON.stringify(outs));
"""

_cache: dict = {}
_sm_cache: dict = {}


def compile_model(facts_path=None, root=None) -> dict:
    """Generate the model into build/, compile it, return artifact info."""
    root = Path(root) if root else ROOT
    facts_path = Path(facts_path) if facts_path else root / facts_mod.DEFAULT_FACTS
    fsha = hashlib.sha256(facts_path.read_bytes()).hexdigest()
    key = (str(facts_path.resolve()), fsha)
    if key in _cache:
        return _cache[key]
    cfg = config(root)
    facts = load_facts(facts_path)
    bdir = root / "build" / "model" / fsha[:16]
    bdir.mkdir(parents=True, exist_ok=True)
    src = bdir / "morph_header.bend"
    src.write_text(bend_model(facts))
    art = bdir / "model.mjs"
    code, out, _ = run_bend([src, "-o", art], cfg=cfg)
    if code != 0 or not art.exists():
        raise RuntimeError(f"bend -o failed: {out[:2000]}")
    widths = facts_mod.widths(facts)
    (bdir / "runner.mjs").write_text(RUNNER_JS.replace("__WIDTHS__", json.dumps(widths)))
    info = {
        "engine": f"bend {bend_version(cfg)}",
        "source": str(src),
        "artifact": str(art),
        "artifact_sha256": hashlib.sha256(art.read_bytes()).hexdigest(),
        "dir": str(bdir),
        "node": cfg.get("node", "node"),
    }
    _cache[key] = info
    return info


SM_RUNNER_JS = """\
import M from "./sm_model.mjs";
import {readFileSync, writeFileSync} from "fs";
const SCALARS = __SCALARS__;
const ARRAYS = __ARRAYS__;
function toList(a){return a.reduceRight((t,x)=>({$:"Con",head:x,tail:t}),{$:"Nil"});}
function fromList(l){const o=[];while(l&&l.$==="Con"){o.push(Number(l.head));l=l.tail;}return o;}
function stateCount(l){let n=0;while(l&&l.$==="Con"){n++;l=l.tail;}return n;}
function inState(s){const o={$:"State"};for(const k of SCALARS)o[k]=BigInt(s[k]);for(const k of ARRAYS)o[k]=toList(s[k].map(BigInt));return o;}
function outState(s){const o={};for(const k of SCALARS)o[k]=Number(s[k]);for(const k of ARRAYS)o[k]=fromList(s[k]);return o;}
function outOutcome(o){if(o.$==="Ok")return {tag:"Ok",state:outState(o.state)};if(o.$==="Revert")return {tag:"Revert",id:Number(o.tag)};if(o.$==="Bound")return {tag:"Bound"};throw new Error("bad outcome "+JSON.stringify(o));}
const jobs=JSON.parse(readFileSync(process.argv[2],"utf8"));
const outs=jobs.map(j=>{
  if(j.op==="init")return {state:outState(M.init_state())};
  if(j.op==="reach")return {count:stateCount(M.reach_k(BigInt(j.depth)))};
  const s=inState(j.state);
  if(j.op==="check")return {value:M[j.fn](s)};
  if(j.op==="check_assignment")return {value:M[j.fn](s,BigInt(j.index))};
  if(j.op==="step")return outOutcome(M[j.action](s,...j.params.map(BigInt)));
  throw new Error("bad op "+j.op);
});
writeFileSync(process.argv[3],JSON.stringify(outs));
"""


def compile_sm_model(source: str, state_fields: dict, root=None, cache_key="sm") -> dict:
    """Compile a generated state-machine/check module and prepare its Node runner."""
    root = Path(root) if root else ROOT
    key = (cache_key, hashlib.sha256(source.encode()).hexdigest())
    if key in _sm_cache:
        return _sm_cache[key]
    cfg = config(root)
    bdir = root / "build" / "sm_model" / key[1][:16]
    bdir.mkdir(parents=True, exist_ok=True)
    src, art = bdir / "sm_model.bend", bdir / "sm_model.mjs"
    src.write_text(source)
    code, out, _ = run_bend([src, "-o", art], cfg=cfg)
    if code != 0 or not art.exists():
        raise RuntimeError(f"Bend state-machine compile failed: {out[:4000]}")
    scalars = [name for name, kind in state_fields if kind == "scalar"]
    arrays = [name for name, kind in state_fields if kind == "array"]
    runner = SM_RUNNER_JS.replace("__SCALARS__", json.dumps(scalars)).replace("__ARRAYS__", json.dumps(arrays))
    (bdir / "runner.mjs").write_text(runner)
    info = {"dir": str(bdir), "artifact": str(art), "node": cfg.get("node", "node")}
    _sm_cache[key] = info
    return info


def eval_sm_jobs(model: dict, jobs: list) -> list:
    d = Path(model["dir"])
    jf, of = d / "jobs.json", d / "out.json"
    jf.write_text(json.dumps(jobs))
    p = subprocess.run([model["node"], "--stack-size=65500", str(d / "runner.mjs"),
                        str(jf), str(of)],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"state-machine model eval failed: {p.stderr[-2000:]}")
    return json.loads(of.read_text())


def _run_jobs(model: dict, jobs: list) -> list:
    d = Path(model["dir"])
    jf, of = d / "jobs.json", d / "out.json"
    jf.write_text(json.dumps(jobs))
    p = subprocess.run([model["node"], str(d / "runner.mjs"), str(jf), str(of)],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError(f"model eval failed: {p.stderr[-2000:]}")
    return json.loads(of.read_text())


def eval_batch(fn: str, inputs: list, facts_path=None, root=None) -> dict:
    """Evaluate facts function fn on canonical-JSON inputs via the compiled model."""
    root = Path(root) if root else ROOT
    facts_path = facts_path or root / facts_mod.DEFAULT_FACTS
    model = compile_model(facts_path, root=root)
    facts = load_facts(facts_path)
    arg_type = facts["functions"][fn]["from"]
    jobs = [{"call": fn, "arg_type": arg_type, "arg": x} for x in inputs]
    outs = _run_jobs(model, jobs)
    return {"engine": model["engine"], "source": model["source"],
            "artifact": model["artifact"], "artifact_sha256": model["artifact_sha256"],
            "outputs": [o["out"] for o in outs]}


def eval_claim(law: dict, witnesses: list, facts_path=None, root=None) -> list:
    """Evaluate a law's claim on candidate binder assignments (canonical JSON).

    witnesses: list of {binder_name: canonical JSON value}. Returns one
    {"lhs","rhs","eq"} per witness, in order.
    """
    root = Path(root) if root else ROOT
    facts_path = facts_path or root / facts_mod.DEFAULT_FACTS
    model = compile_model(facts_path, root=root)
    btypes = {b["name"]: b["type"] for b in law["statement"]["forall"]}
    jobs = [{"eq": law["statement"]["claim"]["eq"],
             "binders": {k: {"type": btypes[k], "value": v} for k, v in w.items()}}
            for w in witnesses]
    return _run_jobs(model, jobs)
