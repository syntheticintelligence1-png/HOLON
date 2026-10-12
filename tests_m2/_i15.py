"""I15 helpers: the instruments fixed at the I15 prereg (BUILD_PLAN §0.1, "instruments are inputs").

Nothing here imports holon/. The contract these helpers read is stated in full in the docstring of
tests_m2/test_sort_sites.py. The tests use them to decide what I15's outputs must say, independently of the
code that writes them:

- `law_id(site_id)` is the law-id rule (a deterministic function of the rule, the subform and the basis element,
  BUILD_PLAN §2.3), written out here;
- `hit_points(facts, site)` and `def_entry_points(facts)` recompute, from the facts, an I13 site and the sidecar
  spec/M2/lib/sort_sites.json, the site's hit points and entry points under the rules fixed at the prereg (R8, R9 of
  the contract), so that DERIVATION.json is checked against an independent reading of the facts;
- `expected_obstructions(facts, assignment, model)` recomputes the coherence obstructions (rule R11);
- `run_site_instrument(traces)` replays model traces on the REAL Rollup at the pinned commit through a byte copy of
  the M1 trace harness taken at this prereg (tests_m2/fixtures/sort_sites/HolonTraceReplay.t.sol.txt, from
  replay/M1/solidity/HolonTraceReplay.t.sol), driven by tests_m2/fixtures/sort_sites/HolonSiteInstrument.t.sol.txt,
  and locates a Panic of the last step at a source line with solc's runtime source map, read from a Foundry debugger
  dump (`forge test --debug --dump`). It is independent of holon's replay (holon/mreplay.py) and of whatever I15
  adds to it.

Locating a Panic (written out so that "Panic 0x11 at Rollup.sol:363" is decided mechanically):
  in the dump of the last step, the FIRST debug-arena node (execution order) whose last step is REVERT (0xfd) with
  revert data Panic(uint256) (selector 0x4e487b71, 36 bytes) is the frame that raised it; its code is the artifact of
  the contract the dump identifies at the node's address (for a DELEGATECALL the implementation); the panic's site is
  the source position of the LAST instruction of that node, before the REVERT, that solc's runtime source map
  (pc -> instruction index -> source map entry) assigns to a user source file (generated Yul utility code has no
  source file and is skipped). The result is (code, contract, source path in the scratch project, line, text).
Probe (toy contracts, not Morph; scratch notes of the prereg): with optimizer_runs 999999, evm cancun and a proxy
delegatecall, the rule names the subtraction `proofWindow + challenges[batchChallenged].startTime - block.timestamp`
and tells it apart from another checked subtraction of the same function.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests._util import config
from tests_m2._i16 import file_sha256, morph_checkout, tree_sha256
from tests_m2._m2 import ROOT, load_json

FIX = ROOT / "tests_m2" / "fixtures" / "sort_sites"
SITE_INSTRUMENT = FIX / "HolonSiteInstrument.t.sol.txt"
# a byte copy of the M1 trace harness (replay/M1/solidity/HolonTraceReplay.t.sol, gate-checked since M1) taken at the
# I15 prereg, so that the instrument does not move if holon's harness is edited later
M1_HARNESS = FIX / "HolonTraceReplay.t.sol.txt"
M1_HARNESS_SHA256 = "3e651a254861603f30c9614ee85ccaa85b6b012d3c2bf88e2aa8813b26959853"
ROLLUP_FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
ASSIGNMENT = ROOT / "gen" / "M2" / "sorts" / "assignment.json"
SIDECAR = ROOT / "spec" / "M2" / "lib" / "sort_sites.json"
MUTATIONS = ROOT / "spec" / "M1" / "mutations.json"
LAWS2 = ROOT / "laws" / "M2"
GEN2 = ROOT / "gen" / "M2"
RESULTS2 = ROOT / "results" / "M2"
REPLAY2 = ROOT / "replay" / "M2" / "report.json"
OBSTRUCTIONS = GEN2 / "sorts" / "obstructions.json"
RULE_CATALOG_VERSION = "holon-rules/1.0"
DERIVE_VERSION = "holon-derive/0.1"
PANIC_SELECTOR = bytes.fromhex("4e487b71")
REVERT = 0xFD
GHOST_MARKER = "# ---- ghost: SORT-site instrumentation (holon.sorts.sites)"
# the Reach block holon.gen.machine.Machine.gen_reach emits for a model that threads no oracle table (I8)
REACH_BLOCK = ("# the reachable states: s0, and one step from a reachable state (I8)\n"
               "type Reach<-s: HSt> is Type:\n"
               "  R0{e: {s == s0() : HSt}}\n"
               "  RStep{a: HAct, p: HSt, r: Reach<p>, e: {s == step(a, p) : HSt}}\n")


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


# ------------------------------------------------------------------ honesty (generic code)
# generic words generic code may quote although a fact document also uses them as a name (record and IR keys)
GENERIC_WORDS = {"status", "value", "count", "next", "len", "append", "view", "off", "cap", "ctx", "proof", "site",
                 "sites", "expr", "kind", "via", "at", "action", "hits", "guards", "effects", "body", "bool", "nth"}


def target_names() -> set[str]:
    """Every name the M2 fact documents and their libraries give, derived (never hand-listed; audit F-M2-14): of the
    0.2 documents the actions, their inputs and lets, the state fields, the record types and their fields, the
    definitions, observers, migrations and params; of the 0.1 document the functions, types and Header fields; and
    every library builtin."""
    names: set[str] = set()
    for rel in ("spec/M1/facts/morph_rollup.json", "spec/M1/facts/morph_batchdata.json"):
        f = load_json(ROOT / rel)
        names |= set(f.get("observers", {})) | set(f.get("defs", {})) | set(f.get("migrations", {}))
        names |= set(f.get("params", {}) if isinstance(f.get("params"), dict) else [])
        names |= {s[0] for s in f.get("state", [])}
        for t, ty in (f.get("types") or {}).items():
            names.add(t)
            for fld in (ty.get("fields", []) if isinstance(ty, dict) else []):
                names.add(fld[0] if isinstance(fld, list) else fld.get("name"))
        for a in f["actions"]:
            names.add(a["name"])
            names |= {x for x, *_ in a.get("inputs", [])}
            names |= {g["let"] for g in a.get("guards", []) if "let" in g}
    for lib in sorted((ROOT / "spec").glob("**/*.lib.json")):
        names |= set(load_json(lib).get("builtins", {}))
    h = load_json(ROOT / "facts" / "morph_header.json")
    names |= set(h["functions"]) | set(h.get("types", {})) | {fld["name"] for fld in h["types"]["Header"]["fields"]}
    return {n for n in names if isinstance(n, str) and n}


def compound_target_names() -> set[str]:
    """Names generic code must not hold anywhere, docstrings included: 5+ characters with an underscore or an
    uppercase letter after the first (a capitalized plain word such as `Entry` is caught only when quoted)."""
    return {n for n in target_names() if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}


def quoted_target_names() -> set[str]:
    """Names (3+ characters) generic code must never hold as a string literal ("win", "lfi", "qpend", ...)."""
    return {n for n in target_names() if len(n) >= 3} - GENERIC_WORDS


# ------------------------------------------------------------------ law ids (rule R7)
_SPAN = re.compile(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def law_id(site_id: str) -> str:
    """L_sort_site_<where>_<x8> for an I13 site id "<model>:<span>:<x8>" (x8: the site id's last 8 hex digits).
    <where> is, for a source span "<path>:<lo>[-<hi>]", slug(stem of the file) + "_<lo>" [+ "_<hi>"]; for a
    definition span "<model>:<def>", "def_" + slug(<def>)."""
    head, x8 = site_id.rsplit(":", 1)
    model, span = head.split(":", 1)
    m = _SPAN.match(span)
    if m:
        where = slug(Path(m["path"]).stem) + f"_{m['lo']}" + (f"_{m['hi']}" if m["hi"] else "")
    else:
        assert span.startswith(model + ":"), site_id
        where = "def_" + slug(span.split(":", 1)[1])
    return f"L_sort_site_{where}_{x8}"


# ------------------------------------------------------------------ facts walking (rules R8-R10)
def guard_exprs(a: dict) -> list[tuple[str, object]]:
    """(where, expression) of every guard (require or let) of an action, then of every effect."""
    out = [(f"guards[{i}]", g.get("require", g.get("expr"))) for i, g in enumerate(a.get("guards", []))]
    out += [(f"effects.{k}", e) for k, e in sorted(a.get("effects", {}).items())]
    return out


def calls(e, out: list) -> list:
    """Every ["call", name, ..] node of a DSL expression (outermost first)."""
    if isinstance(e, list) and e:
        if e[0] == "call":
            out.append(e)
            kids = e[2:]
        elif e[0] == "get":
            kids = [e[1]]
        elif e[0] == "mk":
            kids = list(e[2].values())
        elif e[0] == "with":
            kids = [e[2], *e[3].values()]
        elif e[0] == "list":
            kids = e[2:]
        else:
            kids = e[1:]
        for k in kids:
            calls(k, out)
    return out


def def_reach(facts: dict) -> dict[str, set]:
    """For each non-ghost def, the non-ghost defs its evaluation can call (itself included), transitively."""
    defs = {n: d for n, d in facts.get("defs", {}).items() if not d.get("ghost")}
    direct = {n: {c[1] for c in calls(d["body"], []) if c[1] in defs} for n, d in defs.items()}
    out = {}
    for n in defs:
        seen, todo = set(), [n]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo.extend(direct[x] - seen)
        out[n] = seen
    return out


def def_entry_points(facts: dict) -> dict[str, list[str]]:
    """Def name -> the actions whose guards or effects call it, directly or through non-ghost defs (rule R9).
    A call of a ghost def, and anything inside a ghost def, reaches nothing."""
    reach = def_reach(facts)
    out: dict[str, set] = {n: set() for n in reach}
    for a in facts["actions"]:
        for _, e in guard_exprs(a):
            for c in calls(e, []):
                if c[1] in reach:
                    for d in reach[c[1]]:
                        out[d].add(a["name"])
    return {n: sorted(v) for n, v in out.items()}


def realization_reasons() -> set[str]:
    return set(load_json(SIDECAR)["realization_check_reasons"])


def span_of(text) -> str | None:
    if not isinstance(text, str):
        return None
    m = re.match(r"^(\S+?:\d+(?:-\d+)?)", text)
    return m.group(1) if m else None


def hit_points(facts: dict, site: dict) -> list[dict]:
    """The expected hit points of an I13 site (rules R8-R10): [{"action", "at", "kind"}], sorted."""
    reasons = {str(k): v for k, v in facts.get("reasons", {}).items()}
    real = realization_reasons()
    acts = {a["name"]: a for a in facts["actions"]}
    out = []
    occ = site["occurrences"]
    if all(o["where"].startswith("defs.") for o in occ):     # a definition site: every call reaching the def
        d = occ[0]["action"]
        reach = def_reach(facts)
        for a in facts["actions"]:
            for where, e in guard_exprs(a):
                if any(c[1] in reach and d in reach[c[1]] for c in calls(e, [])):
                    out.append({"action": a["name"], "at": where, "kind": "call"})
        return sorted(out, key=lambda h: (h["action"], h["at"]))
    for o in occ:
        a = acts[o["action"]]
        at = o["where"].split(".")[0] if o["where"].startswith("guards[") else o["where"]
        hit = {"action": a["name"], "at": at, "kind": "occurrence"}
        for i, g in enumerate(a.get("guards", [])):
            if f"guards[{i}]" == at:
                break
            if "require" in g and span_of(g.get("src")) == site["span"] and reasons.get(str(g.get("reason"))) in real:
                hit = {"action": a["name"], "at": f"guards[{i}]", "kind": "realization_check"}
                break
        out.append(hit)
    return sorted(out, key=lambda h: (h["action"], h["at"]))


# ------------------------------------------------------------------ coherence obstructions (rule R11)
def _neg_disjuncts(e) -> list[tuple[object, object]]:
    """(kappa, rho) for a require ["||", d1, d2, ..] with a disjunct ["!", kappa]: rho is the disjunction of the
    other disjuncts (the single one itself when there is one)."""
    if not (isinstance(e, list) and e and e[0] == "||"):
        return []
    ds = e[1:]
    out = []
    for i, d in enumerate(ds):
        if isinstance(d, list) and d and d[0] == "!":
            rest = ds[:i] + ds[i + 1:]
            out.append((d[1], rest[0] if len(rest) == 1 else ["||", *rest]))
    return out


def _vars(e, out: set) -> set:
    if isinstance(e, str):
        out.add(e)
    elif isinstance(e, list) and e:
        if e[0] == "call":
            for x in e[2:]:
                _vars(x, out)
        elif e[0] == "get":
            _vars(e[1], out)
        elif e[0] == "mk":
            for x in e[2].values():
                _vars(x, out)
        elif e[0] == "with":
            _vars(e[2], out)
            for x in e[3].values():
                _vars(x, out)
        elif e[0] == "list":
            for x in e[2:]:
                _vars(x, out)
        else:
            for x in e[1:]:
                _vars(x, out)
    return out


def expected_obstructions(facts: dict, assignment: dict, model: str) -> list[dict]:
    """[{"action", "guard", "at", "registers": [sorted vars]}] for one model (rule R11), sorted."""
    prov = assignment["models"][model].get("provenance", {})
    inputs_of = {a["name"]: {n for n, _ in a["inputs"]} for a in facts["actions"]}
    state = {f for f, *_ in facts["state"]}
    out = []
    for a in facts["actions"]:
        lets = {}
        for i, g in enumerate(a.get("guards", [])):
            if "let" in g:
                lets[g["let"]] = (i, g["expr"])
                continue
            for kappa, rho in _neg_disjuncts(g["require"]):
                if not (_vars(rho, set()) & inputs_of[a["name"]]):
                    continue
                # registers kappa reads, with the facts entry (let or this guard) that reads each directly
                found: dict[str, set] = {}

                def walk(e, at):
                    for v in sorted(_vars(e, set())):
                        if v in lets and v not in inputs_of[a["name"]]:
                            j, ex = lets[v]
                            walk(ex, f"guards[{j}]")
                        elif v in state and v in prov and a["name"] not in prov[v]["writers"]:
                            found.setdefault(at, set()).add(v)
                walk(kappa, f"guards[{i}]")
                for at, regs in found.items():
                    out.append({"action": a["name"], "guard": f"guards[{i}]", "at": at, "registers": sorted(regs)})
    return sorted(out, key=lambda o: (o["action"], o["guard"], o["at"]))


# ------------------------------------------------------------------ the replay instrument
OPS = {"commitBatch": 1, "commitState": 2, "commitBatchWithProof": 3, "revertBatch": 4, "challengeState": 5,
       "proveState": 6, "finalizeBatch": 7, "setPause": 8, "sendMessage": 9, "wait": 10}
WIDTH = 13


def encode_step(a: dict) -> list[int]:
    """One step in the M1 harness's encoding (replay/M1/solidity/HolonTraceReplay.t.sol, `step`): op, then the
    action's inputs in the harness's order, zero-padded to 13 words."""
    op = a["op"]
    w = [OPS[op]] + [0] * (WIDTH - 1)
    if op in ("commitBatch", "commitState", "commitBatchWithProof"):
        bl = list(a["blobs"])
        w[1:12] = [a["who"], a["ver"], a["parent"], a["n"], a["lbn"], a["prev"], a["post"], len(bl),
                   bl[0] if bl else 0, bl[1] if len(bl) > 1 else 0, a.get("proof", 0)]
    elif op in ("revertBatch",):
        w[1:4] = [a["who"], a["idx"], a["count"]]
    elif op == "challengeState":
        w[1:4] = [a["who"], a["idx"], a["value"]]
    elif op == "proveState":
        w[1:4] = [a["who"], a["idx"], a["proof"]]
    elif op == "finalizeBatch":
        w[1:3] = [a["who"], a["idx"]]
    elif op == "setPause":
        w[1:3] = [a["who"], 1 if a["status"] else 0]
    elif op == "sendMessage":
        w[1] = a["who"]
    elif op == "wait":
        w[1] = a["dt"]
    return w


def trace_data(facts: dict, trace: list[dict]) -> list[int]:
    init = facts["initial"]
    data = [init["F"], init["W"], init["D"], init["t"], init["fsr"][0], 1, len(trace)]
    for a in trace:
        data += encode_step(a)
    return data


LINE = re.compile(r"HOLON (\d+) (\d+) (ok|rev) ?(.*)")


def locate_panic(dump: dict) -> dict | None:
    """The Panic the last step raised, located as the module docstring states, or None when it raised none."""
    src = dump["contracts"]["sources"]
    ident = {k.lower(): v for k, v in dump["contracts"]["identified_contracts"].items()}
    for node in dump["debug_arena"]:
        steps = node.get("steps") or []
        if not steps or steps[-1]["op"] != REVERT:
            continue
        last = steps[-1]
        off, size = int(last["stack"][-1], 16), int(last["stack"][-2], 16)
        mem = bytes.fromhex(last["memory"][2:]) if last.get("memory") else b""
        data = mem[off:off + size]
        if len(data) != 36 or data[:4] != PANIC_SELECTOR:
            continue
        name = ident.get(node["address"].lower())
        found = []
        for art in src["artifacts_by_name"].get(name) or []:
            files = src["sources_by_id"][art["build_id"]]
            smap, pcic = art["source_map_runtime"], art["pc_ic_map_runtime"]
            loc = None
            for s in steps[:-1]:
                ic = pcic.get(str(s["pc"]))
                if ic is None or ic >= len(smap):
                    continue
                e = smap[ic]
                f = files.get(str(e["index"])) if e.get("index") is not None else None
                if f is None:
                    continue
                text = f["source"]
                loc = {"path": f["path"], "line": text[:e["offset"]].count("\n") + 1,
                       "text": text[e["offset"]:e["offset"] + e["length"]]}
            if loc is not None:
                found.append(loc)
        uniq = {(x["path"], x["line"]) for x in found}
        if len(uniq) != 1:
            raise AssertionError(f"panic in {name} at {node['address']}: the source map gives {sorted(uniq)}")
        return {"code": int.from_bytes(data[4:], "big"), "contract": name, "kind": node.get("kind"), **found[0]}
    return None


def _check_toolchain() -> dict:
    cfg = config().get("replay") or {}
    for name, pin in (("forge", "forge_sha256"), ("solc", "solc_sha256")):
        path = cfg.get(name)
        if not path or not Path(path).is_file():
            raise AssertionError(f"config/holon.json replay.{name} is not a file: {path!r}")
        if file_sha256(path) != cfg.get(pin):
            raise AssertionError(f"{path} does not match the pinned replay.{pin}")
    nm = Path(cfg.get("sol_deps") or "/nonexistent") / "node_modules"
    if not nm.is_dir() or tree_sha256(nm) != cfg.get("sol_deps_sha256"):
        raise AssertionError(f"{nm} does not match the pinned replay.sol_deps_sha256")
    return cfg


def run_site_instrument(traces: list[list[dict]], facts: dict | None = None) -> list[dict]:
    """For each trace (a list of actions as the M1 witnesses spell them), on the real code at the pinned commit:
    {"outcomes": ["ok" | "rev <reason>", ..] one per step, "panic": locate_panic(...) of the last step}.
    The toolchain is pinned (config replay): a missing or different forge, solc or dependency tree is a failure,
    never a skip."""
    cfg = _check_toolchain()
    if file_sha256(M1_HARNESS) != M1_HARNESS_SHA256:
        raise AssertionError(f"{M1_HARNESS} is not the harness copied at the I15 prereg")
    morph = morph_checkout()
    facts = facts or load_json(ROLLUP_FACTS)
    proj = Path(tempfile.mkdtemp(prefix="holon-i15-sol-"))
    try:
        shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(morph / "contracts" / f, proj / f)
        nm = Path(cfg["sol_deps"]) / "node_modules"
        shutil.copytree(nm, proj / "node_modules", symlinks=False, ignore=shutil.ignore_patterns(".git"))
        (proj / "test").mkdir()
        shutil.copy(M1_HARNESS, proj / "test" / "HolonTraceReplay.t.sol")
        shutil.copy(SITE_INSTRUMENT, proj / "test" / "HolonSiteInstrument.t.sol")
        base = [cfg["forge"], "test", "--match-contract", "HolonSiteInstrumentTest", "--match-test", "test_last_step",
                "--offline", "--use", cfg["solc"]]
        out = []
        for k, tr in enumerate(traces):
            tf = proj / f"holon_site_trace_{k}.json"
            tf.write_text(json.dumps({"data": trace_data(facts, tr)}))
            env = {**os.environ, "HOLON_SITE_TRACE": tf.name}
            p = subprocess.run(base + ["-vv"], cwd=proj, env=env, capture_output=True, text=True, timeout=3000)
            if p.returncode != 0:
                raise AssertionError(f"site instrument failed on trace {k} (exit {p.returncode}): "
                                     f"{(p.stdout + p.stderr)[-2000:]}")
            got = {}
            for m in LINE.finditer(p.stdout):
                got[int(m.group(2))] = "ok" if m.group(3) == "ok" else "rev " + m.group(4).strip()
            outcomes = [got.get(i, "missing") for i in range(len(tr))]
            dump = proj / f"holon_site_dump_{k}.json"
            q = subprocess.run(base + ["--debug", "--dump", str(dump)], cwd=proj, env=env, capture_output=True,
                               text=True, timeout=3000)
            if q.returncode != 0 or not dump.exists():
                raise AssertionError(f"site instrument debugger dump failed on trace {k} (exit {q.returncode}): "
                                     f"{(q.stdout + q.stderr)[-2000:]}")
            panic = locate_panic(json.loads(dump.read_text()))
            dump.unlink()
            out.append({"outcomes": outcomes, "panic": panic})
        return out
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def witness_trace(w: dict) -> list[dict]:
    """The concrete trace of a SORT-site witness {"s": {"run": prefix}, "a": action}: the prefix, then the action."""
    return list(w["s"]["run"]) + [dict(w["a"])]
