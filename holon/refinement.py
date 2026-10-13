"""Per-edge refinement records and mechanical disagreement classes (whitepaper §8.6, §8.7, Def 4.7 rho(e);
BUILD_PLAN I16).

    python -m holon refine --milestone M0 [--edges E1,E2] [--out DIR] [--morph PATH] [--work DIR] [--fix C ..]

Each refined model edge is compared with ITS OWN implementation, never with another edge. The refined
edges are the CODEC edges of the milestone's diagram (gen/M2/diagram/<facts>.json) plus the domain
predicates of its interface carriers; replay/M2/implementations.json binds each to the real function
and the harness that calls it. For each edge:
  1. its corpus (holon.corpus): seeded grammar samples, sort-boundary values, REFUTED witnesses;
  2. the model side on the native C model (holon.model_native) when results/M2/native.json says
     native, else on the .mjs model (holon.model_eval) after the recorded fallback;
  3. the real side through the harness on the pinned toolchain and morph checkout (holon.replay
     toolchain() and check_checkout());
  4. <out>/<edge>.json: counts by source, the inputs digest, model and real output digests, domain
     counts, the disagreements (ids into spec/M2/disagreements.json), the --fix commits and the pins.
A record is a function of the facts, the laws, the records, the binding, the harnesses, the pinned
toolchain and the commit: byte-identical across runs, whatever --edges, --out, --work or --morph.

Without --edges the run also writes cross_edge.json (PAR differences between edges: never refinement
disagreements) and appends each new disagreement to spec/M2/disagreements.json as "unexplained", with no
links, under an id that is a function of (edge, input).

Classes are computed from an entry's links only; its label is never read (classify). check_disagreements
lists every entry whose computed class is unexplained or differs from its label, and every disagreement id
a refinement record lists without an entry. The gate check GREF passes iff that list is empty; it reads no
git (whether a fix commit exists is left to `holon audit`). A step refinement record (holon.replay_fragments,
I20: "disagreements" is a list of {id, class, links}) is checked the same way: every id has an entry, every
listed class is what the entry's links establish, and its "unexplained" count adds up.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import corpus as C
from . import facts as F
from . import ir

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ("extraction_defect", "real_defect", "oracle_mismatch", "unexplained")
LINK_KINDS = {"extraction_defect": {"fix_commit", "rerun"}, "real_defect": {"law"}, "oracle_mismatch": {"hypothesis"}}
RECORD_VERSION = "holon-refinement/0.1"
BINDING = Path("replay") / "M2" / "implementations.json"
DISAGREEMENTS = Path("spec") / "M2" / "disagreements.json"
REF_DIR = Path("results") / "M2" / "refinement"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PIN_KEYS = ("forge_sha256", "solc_sha256", "sol_deps_sha256", "go_version")


class RefineError(RuntimeError):
    pass


def _load(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return None


def sha256_json(obj) -> str:
    return hashlib.sha256(ir.canonical_json(obj)).hexdigest()


# ---------------------------------------------------------------- mechanical classes
def _extraction(entry: dict, links: dict, root: Path) -> bool:
    commit, rerun = links["fix_commit"], links["rerun"]
    if not (isinstance(commit, str) and HEX40.match(commit) and isinstance(rerun, str)):
        return False
    parts = rerun.split("/")
    if (rerun.startswith("/") or "\\" in rerun or any(p in ("", ".", "..") for p in parts)
            or parts[:3] != ["results", "M2", "refinement"] or len(parts) < 4):
        return False
    rec = _load(root / rerun)
    return (isinstance(rec, dict) and rec.get("edge") == entry.get("edge") and rec.get("disagreements") == 0
            and commit in (rec.get("fixes") or []))


def _real(entry: dict, links: dict, root: Path) -> bool:
    law = links["law"]
    m = re.fullmatch(r"(M[0-9]+)/(L_[A-Za-z0-9_]+)", law) if isinstance(law, str) else None
    if m is None:
        return False
    ms, lid = m.groups()
    rec = _load(root / "results" / ms / f"{lid}.json")
    rep = _load(root / "replay" / ms / "report.json")
    if not (isinstance(rec, dict) and isinstance(rep, dict)):
        return False
    if (rec.get("status") != "REFUTED" or (rec.get("replay") or {}).get("status") != "passed"
            or entry.get("edge") not in (rec.get("cone") or [])):
        return False
    if (rep.get("witness_sha256") or {}).get(lid) != sha256_json(rec.get("witness")):
        return False
    lr = (rep.get("laws") or {}).get(lid)
    sides = lr.get("sides") if isinstance(lr, dict) and "sides" in lr else lr
    return (isinstance(sides, dict) and bool(sides)
            and all(isinstance(v, dict) and v.get("obstruction_observed") is True for v in sides.values()))


def _oracle(entry: dict, links: dict, root: Path) -> bool:
    hyp = _load(root / "results" / "M2" / "hypotheses.json")
    h = hyp.get(links["hypothesis"]) if isinstance(hyp, dict) and isinstance(links["hypothesis"], str) else None
    return isinstance(h, dict) and h.get("status") == "failed"


CHECKS = (("extraction_defect", _extraction), ("real_defect", _real), ("oracle_mismatch", _oracle))


def classify(entry: dict, root: Path | str = ROOT) -> str:
    """The class an entry's links give, computed from the links and the files under root only. The
    label (entry["class"]) is never read. links must hold exactly the keys of one kind."""
    links = entry.get("links") if isinstance(entry, dict) else None
    if not isinstance(links, dict):
        return "unexplained"
    for cls, ok in CHECKS:
        if set(links) == LINK_KINDS[cls]:
            return cls if ok(entry, links, Path(root)) else "unexplained"
    return "unexplained"


def check_disagreements(root: Path | str = ROOT) -> list[str]:
    """Every problem GREF reports: an entry that classifies to unexplained or to a class other than its
    label, a malformed or duplicate entry, a disagreements file that is missing, and a disagreement id
    that a refinement record lists without an entry (or a record whose counts do not add up)."""
    root = Path(root)
    out: list[str] = []
    doc = _load(root / DISAGREEMENTS)
    if not isinstance(doc, dict) or not isinstance(doc.get("disagreements"), list):
        return [f"{DISAGREEMENTS.as_posix()} is missing or holds no 'disagreements' list"]
    ids: set = set()
    for i, e in enumerate(doc["disagreements"]):
        if not isinstance(e, dict) or not isinstance(e.get("id"), str):
            out.append(f"entry #{i}: not an object with a string id")
            continue
        if e["id"] in ids:
            out.append(f"{e['id']}: listed twice")
        ids.add(e["id"])
        got = classify(e, root)
        if got == "unexplained":
            out.append(f"{e['id']}: unexplained (links {json.dumps(e.get('links'), sort_keys=True)} establish no class; "
                       f"label {e.get('class')!r})")
        elif got != e.get("class"):
            out.append(f"{e['id']}: labelled {e.get('class')!r} but its links establish {got!r}")
    entries = {e["id"]: e for e in doc["disagreements"] if isinstance(e, dict) and isinstance(e.get("id"), str)}
    for f in sorted((root / REF_DIR).glob("*.json")):
        rec = _load(f)
        if not isinstance(rec, dict):
            out.append(f"{f.name}: not a refinement record")
            continue
        if isinstance(rec.get("disagreements"), list):   # the extracted model's step refinement (I20)
            out += _check_step_record(f.name, rec, entries, root)
            continue
        dids = rec.get("disagreement_ids")
        if not isinstance(dids, list):
            out.append(f"{f.name}: no disagreement_ids list")
            continue
        for did in dids:
            if did not in ids:
                out.append(f"{did}: listed by {f.name} but has no entry in {DISAGREEMENTS.as_posix()}")
        n = rec.get("disagreements")
        # an id is a function of (edge, input): a corpus input listed twice disagrees twice under one id
        if not isinstance(n, int) or isinstance(n, bool) or (n > 0) != bool(dids) or len(set(dids)) > n:
            out.append(f"{f.name}: counts {n!r} disagreements but lists {len(set(dids))} distinct ids")
        if isinstance(rec.get("compared"), int) and rec.get("agree", 0) + (rec.get("disagreements") or 0) != rec["compared"]:
            out.append(f"{f.name}: agree + disagreements != compared")
    return out


def _check_step_record(name: str, rec: dict, entries: dict, root: Path) -> list[str]:
    """A step refinement record (holon.replay_fragments; I20): "disagreements" lists {id, class, links}. Every id has
    an entry, every listed class is what the entry's links establish, and "unexplained" counts the unexplained ones."""
    out = []
    n_unexplained = 0
    for i, d in enumerate(rec["disagreements"]):
        if not isinstance(d, dict) or not isinstance(d.get("id"), str):
            out.append(f"{name}: disagreement #{i} is not an object with a string id")
            continue
        e = entries.get(d["id"])
        if e is None:
            out.append(f"{d['id']}: listed by {name} but has no entry in {DISAGREEMENTS.as_posix()}")
            continue
        got = classify(e, root)
        n_unexplained += got == "unexplained"
        if d.get("class") != got:
            out.append(f"{d['id']}: {name} lists class {d.get('class')!r} but the entry's links establish {got!r}")
    if rec.get("unexplained") != n_unexplained:
        out.append(f"{name}: counts {rec.get('unexplained')!r} unexplained disagreements, its entries give {n_unexplained}")
    return out


# ---------------------------------------------------------------- what is refined, against what
def binding(root: Path = ROOT) -> dict:
    b = _load(Path(root) / BINDING)
    if not isinstance(b, dict):
        raise RefineError(f"{BINDING.as_posix()} is missing or unreadable")
    return b


def diagram_path(facts_rel: str, root: Path = ROOT) -> Path:
    return Path(root) / "gen" / "M2" / "diagram" / f"{Path(facts_rel).stem}.json"


def refined_edges(facts_rel: str, root: Path = ROOT) -> list[tuple[str, str, str | None]]:
    """(model function, kind, diagram edge id) for every CODEC edge of the facts' diagram and every domain
    predicate of its interface carriers, sorted by function name."""
    d = _load(diagram_path(facts_rel, root))
    if not isinstance(d, dict):
        raise RefineError(f"no diagram for {facts_rel}: run `holon diagram` (I11)")
    out = {e["model_fn"]: ("codec", e["id"]) for e in d["edges"] if e.get("kind") == "CODEC" and e.get("model_fn")}
    for c in d.get("carriers", []):
        if c.get("interface"):
            for p in c.get("domains") or []:
                out.setdefault(p, ("domain", None))
    return [(e, k, i) for e, (k, i) in sorted(out.items())]


def model_engine(root: Path = ROOT) -> str:
    from .model_native import load_record
    rec = load_record(root)
    if not isinstance(rec, dict) or rec.get("status") not in ("native", "fallback"):
        raise RefineError("results/M2/native.json is missing: run `holon native --milestone M0` first")
    return "native" if rec["status"] == "native" else "mjs"


def build_engine(engine: str, facts_path: Path):
    if engine == "native":
        from .model_native import NativeModel
        return NativeModel.build(facts_path)
    from .model_eval import CompiledModel
    return CompiledModel.build(facts_path)


def evaluate(model, facts: dict, fn: str, inputs: list) -> list:
    """Canonical outputs of fact function fn on each input, evaluated by the compiled model."""
    from .model_eval import ModelError, value_in, value_out
    arg_t, res_t = F.fn_types(facts, fn)
    jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": value_in(arg_t, x, facts)}} for x in inputs]
    out = []
    for (v,) in model.run_jobs(jobs) if jobs else []:
        try:
            out.append(value_out(res_t, v))
        except ModelError as e:
            out.append({"error": str(e)[:200]})
        except ValueError:
            out.append({"undefined": True})
    return out


# ---------------------------------------------------------------- the real side
def _run(cmd: list[str], cwd: Path, env: dict, timeout: int = 3600) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def go_command() -> str:
    return "(cd common && HOLON_CODEC_IN=… HOLON_CODEC_OUT=… go test ./batch -run ^TestHolonCodec$ -count=1 -v)  # exit 0"


def sol_command() -> str:
    return ("HOLON_CODEC_IN=holon_codec_in.txt HOLON_CODEC_OUT=holon_codec_out.txt forge test --match-contract "
            "HolonCodec --offline --use <solc 0.8.24> -vv  # exit 0")


def go_jobs(facts: dict, bind: dict, edges: list[str], inputs: dict[str, list]) -> list[dict]:
    jobs = []
    for e in edges:
        b = bind["edges"][e]
        job = {"edge": e, "op": b["op"], "getters": [], "headers": [], "bytes": []}
        if C.input_sort(facts, e) == "Header":
            fields = b.get("fields") or {}
            unknown = sorted(set(fields) - set(F.widths(facts)))
            if unknown:
                raise RefineError(f"{e}: binding fields not in the facts: {unknown}")
            job["headers"] = [{g: x[f] for f, g in fields.items()} for x in inputs[e]]
        else:
            job["bytes"] = list(inputs[e])
        if b["op"] == "decode":
            getters = [g["name"] for g in facts["functions"][e]["getters"]]
            missing = [g for g in getters if g not in (b.get("getters") or {})]
            if missing:
                raise RefineError(f"{e}: binding has no Go method for getters {missing}")
            job["getters"] = [b["getters"][g] for g in getters]
        jobs.append(job)
    return jobs


def run_go(root: Path, morph: Path, work: Path, bind: dict, jobs: list[dict]) -> dict[str, list]:
    h = bind["harnesses"]["go"]
    ws = work / "go"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for d in h["copy_trees"]:
        shutil.copytree(morph / d, ws / d, symlinks=True)
    (ws / "go.work").write_text("go 1.24.0\n\nuse (\n" + "".join(f"\t./{d}\n" for d in h["copy_trees"]) + ")\n")
    shutil.copy(root / h["path"], ws / h["package"] / h["file"])
    (ws / "in.json").write_text(json.dumps(jobs))
    code, out = _run(["go", "test", "./batch", "-run", f"^{h['test']}$", "-count=1", "-v"], ws / "common",
                     {"HOLON_CODEC_IN": str(ws / "in.json"), "HOLON_CODEC_OUT": str(ws / "out.json")})
    if code != 0 or not (ws / "out.json").exists():
        raise RefineError(f"Go harness failed (exit {code}): {out[-2000:]}")
    return json.loads((ws / "out.json").read_text())["outputs"]


def _abi_word(value_hex: str, typ: str) -> bytes:
    b = bytes.fromhex(value_hex[2:])
    if typ == "bytes32":
        if len(b) != 32:
            raise RefineError(f"bytes32 value of {len(b)} bytes")
        return b
    m = re.fullmatch(r"uint(\d+)", typ)
    if not m or len(b) * 8 > int(m.group(1)):
        raise RefineError(f"value of {len(b)} bytes for {typ}")
    return bytes(32 - len(b)) + b


def sol_items(facts: dict, bind: dict, edges: list[str], inputs: dict[str, list]) -> list[str]:
    ops = {"build": 1, "load": 2}
    items = []
    for e in edges:
        b = bind["edges"][e]
        if b["op"] not in ops:
            raise RefineError(f"{e}: unknown Solidity harness op {b['op']}")
        for x in inputs[e]:
            if b["op"] == "build":
                payload = b"".join(_abi_word(x[f], t) for f, t in b["abi"])
            else:
                payload = bytes.fromhex(x[2:])
            items.append("0x" + (bytes([ops[b["op"]]]) + payload).hex())
    return items


def run_solidity(root: Path, morph: Path, work: Path, bind: dict, tc: dict, items: list[str]) -> list[str]:
    from .replay import _sol_deps
    h = bind["harnesses"]["solidity"]
    proj = work / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(proj / "contracts", ignore_errors=True)
    shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
    for d in ("mock", "test"):  # as replay_solidity: the repo's mocks and tests pull extra dependencies
        shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
    for f in ("foundry.toml", "remappings.txt"):
        shutil.copy(morph / "contracts" / f, proj / f)
    _sol_deps(proj, Path(tc["sol_deps"]))
    shutil.rmtree(proj / "test", ignore_errors=True)
    (proj / "test").mkdir()
    shutil.copy(root / h["path"], proj / h["file"])
    (proj / "holon_codec_in.txt").write_text("\n".join(items + ["0x"]) + "\n")
    (proj / "holon_codec_out.txt").unlink(missing_ok=True)
    cmd = [tc["forge"], "test", "--match-contract", h["contract"], "--offline", "--use", tc["solc"], "-vv"]
    code, out = _run(cmd, proj, {"HOLON_CODEC_IN": "holon_codec_in.txt", "HOLON_CODEC_OUT": "holon_codec_out.txt"},
                     timeout=6000)
    got = (proj / "holon_codec_out.txt").read_text().splitlines() if (proj / "holon_codec_out.txt").exists() else []
    if code != 0 or len(got) != len(items) + 1 or got[-1] != f"done {len(items)}":
        raise RefineError(f"Solidity harness failed (exit {code}, {len(got)} lines for {len(items)} items): {out[-2000:]}")
    return got[:-1]


def real_outputs(root: Path, facts: dict, bind: dict, edges: list[str], inputs: dict[str, list], morph: Path,
                 work: Path, tc: dict) -> dict[str, list]:
    out: dict[str, list] = {}
    go = [e for e in edges if bind["edges"][e]["lang"] == "go"]
    sol = [e for e in edges if bind["edges"][e]["lang"] == "solidity"]
    if go:
        res = run_go(root, morph, work, bind, go_jobs(facts, bind, go, inputs))
        for e in go:
            out[e] = res[e]
    if sol:
        lines = run_solidity(root, morph, work, bind, tc, sol_items(facts, bind, sol, inputs))
        i = 0
        for e in sol:
            vals = lines[i:i + len(inputs[e])]
            i += len(inputs[e])
            if bind["edges"][e]["op"] == "load":
                if not set(vals) <= {"true", "false"}:
                    raise RefineError(f"{e}: the harness wrote non-boolean outputs {sorted(set(vals))[:3]}")
                out[e] = [v == "true" for v in vals]
            else:
                if not all(re.fullmatch(r"0x(?:[0-9a-f]{2})*", v) for v in vals):
                    raise RefineError(f"{e}: the harness wrote non-hex outputs")
                out[e] = vals
    for e in edges:
        if len(out.get(e, [])) != len(inputs[e]):
            raise RefineError(f"{e}: {len(out.get(e, []))} real outputs for {len(inputs[e])} inputs")
    return out


# ---------------------------------------------------------------- records
def disagreement_id(edge: str, x) -> str:
    return f"D-{edge}-{sha256_json([edge, x])[:16]}"


def domain_counts(model, facts: dict, edge: str, inputs: list, model_out: list) -> dict | None:
    f = facts["functions"][edge]
    if f["kind"] == "predicate":
        vals = model_out
    elif f["kind"] == "decoder" and f.get("guard"):
        vals = evaluate(model, facts, f["guard"], inputs)
    else:
        return None
    n_in = sum(1 for v in vals if v is True)
    return {"in": n_in, "out": len(vals) - n_in}


def edge_record(edge: str, kind: str, diagram_edge: str | None, facts_rel: str, facts_sha: str, model_sha: str,
                engine: str, native_status: str, bind: dict, items: list[dict], model_out: list, real_out: list,
                domain: dict | None, fixes: list[str], morph_sha: str, tc: dict) -> tuple[dict, list[dict]]:
    b = bind["edges"][edge]
    lang = b["lang"]
    dis, ids = [], []
    for it, mv, rv in zip(items, model_out, real_out):
        if ir.canonical_json(mv) != ir.canonical_json(rv):
            did = disagreement_id(edge, it["input"])
            if did not in ids:
                ids.append(did)
                dis.append({"id": did, "edge": edge, "milestone": "M0", "input": it["input"], "model": mv,
                            "real": rv, "source": it["source"]})
    n_dis = sum(1 for mv, rv in zip(model_out, real_out) if ir.canonical_json(mv) != ir.canonical_json(rv))
    rec = {
        "record_version": RECORD_VERSION,
        "edge": edge, "milestone": "M0", "kind": kind, "diagram_edge": diagram_edge,
        "facts": facts_rel, "facts_sha256": facts_sha, "model_sha256": model_sha,
        "implementation": {"lang": lang, "harness": bind["harnesses"][lang]["path"], "target": b["target"]},
        "model_engine": engine, "native": native_status,
        "corpus": {"seed": C.SEED, **C.counts(items), "inputs_sha256": sha256_json([it["input"] for it in items])},
        "compared": len(items), "agree": len(items) - n_dis, "disagreements": n_dis, "disagreement_ids": ids,
        "outputs_sha256": {"model": sha256_json(model_out), "real": sha256_json(real_out)},
        "fixes": sorted(set(fixes)),
        "morph_commit": morph_sha, "toolchain": {k: tc[k] for k in PIN_KEYS},
        "command": go_command() if lang == "go" else sol_command(),
    }
    if domain is not None:
        rec["domain"] = domain
    return rec, dis


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------- cross-edge PAR differences
def claim_calls(law: dict) -> set[str]:
    return {t["call"] for t in law["statement"]["claim"]["eq"] if "call" in t}


def cross_edge(model, facts: dict, laws: list[dict], edges: list[str], corpora: dict[str, list],
               outputs: dict[str, list]) -> dict:
    """PAR differences between refined edges of the same type: for each sorted pair (a, b), the inputs of
    corpus(a) then corpus(b), without repeats, in both domains, on which the model's a and b differ;
    grouped by the first law (law-id order) whose claim compares exactly {a, b} and whose premises the
    input satisfies (premises evaluated on the model), else by law null."""
    from .gen import laws as LG
    from .model_eval import value_in
    types = {e: F.fn_types(facts, e) for e in edges}
    pairs = [[a, b] for a, b in itertools.combinations(sorted(edges), 2) if types[a] == types[b]]
    diffs, compared = [], {}
    for a, b in pairs:
        seen, xs = set(), []
        for e in (a, b):
            for it in corpora[e]:
                k = ir.canonical_json(it["input"])
                if k in seen:
                    continue
                seen.add(k)
                x = it["input"]
                if C.input_sort(facts, a) == "Header" and not (C.in_domain(facts, a, x) and C.in_domain(facts, b, x)):
                    continue
                xs.append(x)
        known = {e: {ir.canonical_json(it["input"]): v for it, v in zip(corpora[e], outputs[e])} for e in (a, b)}
        va = [known[a].get(ir.canonical_json(x)) for x in xs]
        vb = [known[b].get(ir.canonical_json(x)) for x in xs]
        for e, vs in ((a, va), (b, vb)):
            todo = [i for i, v in enumerate(vs) if v is None]
            for i, v in zip(todo, evaluate(model, facts, e, [xs[i] for i in todo])):
                vs[i] = v
        compared[f"{a},{b}"] = len(xs)
        hits = [x for x, p, q in zip(xs, va, vb) if ir.canonical_json(p) != ir.canonical_json(q)]
        cands = [l for l in laws if claim_calls(l) == {a, b} and len(l["statement"]["forall"]) == 1
                 and l["statement"]["forall"][0]["type"] == C.input_sort(facts, a)]
        sat = {}  # law id -> [premises hold on hit i], evaluated by the model in one batch per law
        for l in cands:
            prem = l["statement"].get("assume", [])
            if not prem:
                sat[l["law_id"]] = [True] * len(hits)
                continue
            v = l["statement"]["forall"][0]
            t = LG.binder_types(l)[v["name"]]
            terms = [s for p in prem for s in p["eq"]]
            res = model.run_jobs([{"terms": terms, "env": {v["name"]: value_in(t, x, facts)}} for x in hits]) if hits else []
            sat[l["law_id"]] = [all(not (isinstance(vals[2 * i], dict) and "error" in vals[2 * i])
                                    and ir.canonical_json(vals[2 * i]) == ir.canonical_json(vals[2 * i + 1])
                                    for i in range(len(prem))) for vals in res]
        groups: dict = {}
        for k, x in enumerate(hits):
            law = next((l["law_id"] for l in cands if sat[l["law_id"]][k]), None)
            g = groups.setdefault(law, {"edges": [a, b], "kind": "PAR", "law": law, "count": 0, "example": x})
            g["count"] += 1
        diffs += [groups[k] for k in sorted(groups, key=lambda k: (k is None, k or ""))]
    return {"milestone": "M0", "pairs": pairs, "inputs_compared": compared, "differences": diffs,
            "note": "PAR differences between two model edges of the same type, over corpus(a) then corpus(b) "
                    "restricted to both domains; never counted as refinement disagreements (each edge is "
                    "compared with its own implementation in results/M2/refinement/)"}


# ---------------------------------------------------------------- driver
def append_disagreements(root: Path, new: list[dict]) -> Path:
    p = root / DISAGREEMENTS
    doc = _load(p) if p.exists() else None
    if not isinstance(doc, dict) or not isinstance(doc.get("disagreements"), list):
        doc = {"disagreements": []}
    doc.setdefault("doc", "Refinement disagreements (BUILD_PLAN I16). holon refine appends each new one as "
                          "'unexplained' with no links; a class is established by links only (holon.refinement."
                          "classify): {fix_commit, rerun}, {law} or {hypothesis}. GREF fails on any entry whose "
                          "links establish no class or another class than its label.")
    have = {e.get("id") for e in doc["disagreements"] if isinstance(e, dict)}
    for d in new:
        if d["id"] not in have:
            doc["disagreements"].append({**{k: v for k, v in d.items() if k != "source"},
                                         "class": "unexplained", "links": {}})
            have.add(d["id"])
    write_json(p, doc)
    return p


def refine(args) -> int:
    from .replay import check_checkout, morph_path, toolchain
    from .model_native import load_record
    root = ROOT
    if args.milestone != "M0":
        raise RefineError("refine covers the M0 codec diagram (the M1 corpus lives in replay/M1/report.json)")
    reg = ir.load_registry(args.milestone, root)
    facts_rel = reg["facts"]
    facts_path = root / facts_rel
    facts = F.load(facts_path)
    fixes = list(args.fix or [])
    bad = [c for c in fixes if not HEX40.match(c)]
    if bad:
        raise RefineError(f"--fix takes 40-character lowercase hex commits: {bad}")
    all_edges = refined_edges(facts_rel, root)
    names = [e for e, _, _ in all_edges]
    want = [e.strip() for e in args.edges.split(",") if e.strip()] if args.edges else names
    unknown = sorted(set(want) - set(names))
    if unknown:
        raise RefineError(f"not refined edges of {facts_rel}: {unknown} (refined: {names})")
    bind = binding(root)
    missing = sorted(set(names) - set(bind.get("edges", {})))
    if missing:
        raise RefineError(f"{BINDING.as_posix()} binds no implementation for {missing}")
    if load_record(root) is None:
        from .model_native import record, write_record
        write_record(record(args.milestone, root), root / "results" / "M2" / "native.json")
    engine = model_engine(root)
    native_status = "native" if engine == "native" else "fallback (results/M2/native.json)"
    morph = morph_path(args, root)
    morph_sha = check_checkout(morph, facts["target"]["commit"])
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False, morph=str(morph)), root)
    model = build_engine(engine, facts_path)
    from .gen import model as G
    model_sha = hashlib.sha256(G.generate(facts, F.sha256_file(facts_path)).encode()).hexdigest()
    run_edges = [e for e in names if e in want]
    corpora = {e: C.corpus(e, facts_path, args.milestone, root) for e in (names if not args.edges else run_edges)}
    inputs = {e: [it["input"] for it in corpora[e]] for e in corpora}
    outputs = {e: evaluate(model, facts, e, inputs[e]) for e in corpora}
    tmp = None
    if args.work:
        work = Path(args.work).resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        tmp = work = Path(tempfile.mkdtemp(prefix="holon-refine-"))
    try:
        real = real_outputs(root, facts, bind, run_edges, inputs, morph, work, tc)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    out_dir = Path(args.out).resolve() if args.out else root / REF_DIR
    meta = {e: (k, i) for e, k, i in all_edges}
    new_dis = []
    for e in run_edges:
        dom = domain_counts(model, facts, e, inputs[e], outputs[e])
        rec, dis = edge_record(e, meta[e][0], meta[e][1], facts_rel, reg["facts_sha256"], model_sha, engine,
                               native_status, bind, corpora[e], outputs[e], real[e], dom, fixes, morph_sha, tc)
        write_json(out_dir / f"{e}.json", rec)
        new_dis += dis
        print(f"{e:10s} compared {rec['compared']:5d}  agree {rec['agree']:5d}  disagreements {rec['disagreements']}  "
              f"engine {engine}  model {rec['outputs_sha256']['model'][:12]}  real {rec['outputs_sha256']['real'][:12]}")
    if not args.edges:
        laws = sorted(ir.load_laws_any(args.milestone, root), key=lambda l: l["law_id"])
        xe = cross_edge(model, facts, laws, names, corpora, outputs)
        write_json((Path(args.out).resolve() if args.out else root / "results" / "M2") / "cross_edge.json", xe)
        for d in xe["differences"]:
            print(f"cross-edge {'/'.join(d['edges'])}: {d['count']} PAR differences, law {d['law']}")
        p = append_disagreements(root, new_dis)
        print(f"wrote {p.relative_to(root)} ({len(new_dis)} disagreements this run)")
    return 0 if not new_dis else 1


def main_refine(args) -> int:
    try:
        return refine(args)
    except RefineError as e:
        print(f"refine: {e}", file=sys.stderr)
        return 2
