"""`holon refute --milestone M3` (I40): BMC over the extracted rollup document from the binding's deployment (reaches,
the width laws, the concretization targets, I21), the paths' replay on the real contract, and the final filter over
every REFUTED record (holon.filter.final_bin). The contract is the docstring of tests_m3/test_refute.py; the milestone
sidecar is spec/M3/lib/refute.json, its machine-readable transcription spec/M3/refute_env.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import bmc as BMC
from .smt import run as SR


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _int(x) -> int:
    return int(str(x), 0) if not isinstance(x, int) else x


def r0_families(doc: dict, init: dict) -> tuple[dict, dict]:
    """R0 per family, decoded from the deployment's captured slots and preimages (a mapping entry's slot is
    keccak256(key . slot)): ({family: value}, {"unknown_slots": [...]})."""
    from .keccak import keccak256
    st = {_int(k): _int(v) for k, v in (init.get("storage") or {}).items()}
    used = set()
    out = {}
    fams = [s for s in list(doc.get("inherited_storage") or []) + list(doc.get("storage") or [])
            if s.get("kind") != "array"]
    for f in fams:
        if f.get("kind") == "scalar":
            w = st.get(int(f["slot"]), 0)
            out[f["name"]] = (w >> (8 * int(f.get("offset") or 0))) & ((1 << int(f.get("width") or 256)) - 1)
            if int(f["slot"]) in st:
                used.add(int(f["slot"]))
    by_slot = {int(f["slot"]): f for f in fams if f.get("kind") == "mapping"}
    for pre in init.get("preimages") or []:
        b = bytes.fromhex(pre[2:])
        if len(b) != 64:
            continue
        key, slot = int.from_bytes(b[:32], "big"), int.from_bytes(b[32:], "big")
        f = by_slot.get(slot)
        if f is None:
            continue
        base = int.from_bytes(keccak256(b), "big")
        if f.get("fields"):
            rec = {}
            for fl in f["fields"]:
                s = base + int(fl["slot"])
                w = st.get(s, 0)
                rec[fl["name"]] = (w >> (8 * int(fl.get("offset") or 0))) & ((1 << int(fl.get("width") or 256)) - 1)
                if s in st:
                    used.add(s)
            out.setdefault(f["name"], {})[key] = rec
        else:
            w = st.get(base, 0)
            out.setdefault(f["name"], {})[key] = w & ((1 << int(f.get("width") or 256)) - 1)
            if base in st:
                used.add(base)
    return out, {"unknown_slots": sorted("0x%064x" % s for s in st if s not in used)}


def problem(root: Path, side: dict, env: dict):
    doc_rel = side["documents"][0]
    doc = load(root / doc_rel)
    m = BMC.Machine(doc, side["smt"]["byte_length_max"])
    init = load(root / side["deployment"]["capture"])
    r0, info = r0_families(doc, init)
    pr = side["bmc"]["principals"]
    principals = [("owner", _int(pr["owner"]))] + [(f"submitter{i}", _int(a)) for i, a in enumerate(pr["submitters"])] \
        + [("challenger", _int(pr["challenger"])), ("anyone", _int(pr["anyone"]))]
    imm = {k: _int(v) for k, v in (init.get("immutables") or {}).items()}
    p = BMC.Problem(m, r0, principals, int(side["deployment"]["deployed_at"]), int(side["bmc"]["H"]),
                    int(side["solver"]["rlimit_per_query"]), int(side["blob_count_max"]),
                    answers=env.get("answers") or {}, immutables=imm, this=_int(init["target"]))
    p.gas_limit = int(side.get("gas_limit") or 30000000)
    p.preimages = [bytes.fromhex(x[2:]) for x in init.get("preimages") or [] if len(x) > 2 + 128]
    st = {_int(k): _int(v) for k, v in (init.get("storage") or {}).items()}
    p.raw_slots = {_int(x): st[_int(x)] for x in info["unknown_slots"]}
    return p, info




# ------------------------------------------------------------------------------------------------ the questions
REFUTE = Path("results") / "M3" / "refute"
GENR = Path("gen") / "M3" / "refute"


def questions(root: Path, side: dict, env: dict) -> list[dict]:
    """Every BMC question of the milestone, in a fixed order: the concretization targets (K1), I21's EVM halves, the
    width laws' stores, then the unfalsified reaches (Q5)."""
    qs = []
    for tid in sorted((env.get("targets") or {})):
        t = {k: v for k, v in env["targets"][tid].items() if k != "prose"}
        qs.append({"id": f"target:{tid}", "target": t})
    for fid in sorted((env.get("i21") or {})):
        t = {k: v for k, v in env["i21"][fid].items() if k != "prose"}
        qs.append({"id": f"i21:{fid}", "target": t})
    dv = load(root / "laws" / "M2" / "DERIVATION.json")
    for u in side["unknowns"]:
        e = next((x for x in dv["laws"] if x["law_id"] == u["law_id"]), None)
        if e is not None and e.get("subform") == "width" and u["facts"] == side["documents"][0]:
            b = e["basis"]
            qs.append({"id": f"width:{u['record']}", "target": {"kind": "store", "span": b["span"],
                                                               "width": int(b["width"])}})
    for rid in side["unfalsified_reaches"]:
        qs.append({"id": f"reach:{rid}", "target": {"kind": "check", "action": rid.split("#")[0], "check": rid}})
    for v, t in sorted(cc_targets(root, env).items()):
        qs.append({"id": f"cc:v{v}", "target": t})
    return qs


def cc_plans(root: Path, env: dict) -> list[dict]:
    """Rule K3's records (a codec witness whose claim calls the Solidity encoder env["commit_class"] names): per record
    the witness's version, the cells where the two sides differ, and the Solidity side's bytes there."""
    cc = env.get("commit_class")
    if not cc:
        return []
    sides = i4_sides(root)
    out = []
    for key, rec in sorted(records(root).items()):
        if rec.get("status") != "REFUTED" or witness_kind(rec) != "codec":
            continue
        law = law_of(root, key)
        ss = dict(sides.get(key) or {})
        if kind_of(rec, law, ss) != "commit_class":
            continue
        claim = ((law.get("statement") or {}).get("claim") or {}).get("eq") or []
        i = next((j for j, c in enumerate(claim) if isinstance(c, dict) and c.get("call") == cc["encoder"]["function"]),
                 None)
        if i is None:
            continue
        var = ((claim[i].get("args") or [{}])[0] or {}).get("var")
        w = (rec.get("witness") or {}).get(var) or {}
        if cc["witness_field"] not in w:
            continue
        v = int(str(w[cc["witness_field"]]), 0)
        a = bytes.fromhex(rec["difference"]["lhs"][2:])
        b = bytes.fromhex(rec["difference"]["rhs"][2:])
        sol = a if i == 0 else b
        cells = [j for j in range(max(len(a), len(b))) if j >= len(a) or j >= len(b) or a[j] != b[j]]
        out.append({"record": key, "version": v, "cells": cells, "sol": "0x" + sol.hex()})
    return out


def cc_targets(root: Path, env: dict) -> dict:
    """{version: the BMC step target of a commit at that version from R0, observing the encoder's sink}."""
    cc = env.get("commit_class")
    plans = cc_plans(root, env)
    if not plans:
        return {}
    enc = load(root / cc["encoder"]["document"])["functions"][cc["encoder"]["function"]]
    out = {}
    for v in sorted({p["version"] for p in plans}):
        lay = (enc.get("layouts") or {}).get(str(v))
        observe = {"fn": (enc.get("sink") or {}).get("op"), "byte0": v}
        if lay is not None:
            observe["lengths"] = [len(lay)]
        out[v] = {"kind": "step", "actions": list(cc["actions"]), "cond": ["==", cc["version_param"], v],
                  "observe": observe}
    return out


def qfile(qid: str) -> str:
    import hashlib
    return hashlib.sha256(qid.encode()).hexdigest()[:16]


def run_question(root: Path, side: dict, env: dict, q: dict, log=print, out_root: Path | None = None) -> dict:
    """One BMC question; its query files go under out_root (the repository root, or a scratch root for --check), named
    relative to it, so a recomputation names them exactly as the committed result does."""
    out_root = Path(out_root or root)
    p, _info = problem(root, side, env)
    name = qfile(q["id"])
    r = BMC.search(p, q["target"], side["solver"], out_root / GENR / "smt" / "bmc", name, log=log)
    r["queries"] = [str(Path(x).resolve().relative_to(out_root.resolve())) for x in r["queries"]]
    r["id"] = q["id"]
    r["target"] = q["target"]
    return r


def bmc_stage(root: Path, side: dict, env: dict, only_ids: list | None = None, jobs: int = 1, log=print,
              out_root: Path | None = None, redo: bool = False) -> dict:
    """Run (or resume) every BMC question: each result cached as <out_root>/gen/M3/refute/bmc/<question>.json. A
    question the crash watchdog aborts, or whose solver crashes, gets no file (no verdict; it stays not run). redo:
    run the questions that already have a file too. Returns {question id: result or None}."""
    from concurrent.futures import ThreadPoolExecutor
    from .smt.run import SolverCrash, WatchdogAbort
    out_root = Path(out_root or root)
    out = out_root / GENR / "bmc"
    out.mkdir(parents=True, exist_ok=True)
    qs = [q for q in questions(root, side, env) if not only_ids or q["id"] in only_ids]
    if only_ids:
        qs.sort(key=lambda q: only_ids.index(q["id"]))
    todo = [q for q in qs if redo or not (out / f"{qfile(q['id'])}.json").is_file()]

    def one(q):
        try:
            r = run_question(root, side, env, q, log=log, out_root=out_root)
        except (WatchdogAbort, SolverCrash) as x:
            log(f"{q['id']}: no verdict ({x}); nothing recorded")
            return q["id"], None
        except Exception as x:  # noqa: BLE001  (an encoder failure is an unknown with its reason, never a verdict)
            r = {"id": q["id"], "target": q["target"], "verdict": "unknown", "length": None, "path": None,
                 "largest_k": 0, "queries": [], "approx": [], "reason": f"encoder error: {type(x).__name__}: {x}"}
        (out / f"{qfile(q['id'])}.json").write_text(dumps(r), encoding="utf-8")
        log(f"{q['id']}: {r['verdict']} (largest_k {r['largest_k']})")
        return q["id"], r
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        return dict(ex.map(one, todo))


def bmc_check(root: Path, side: dict, env: dict, only_ids: list | None = None, jobs: int = 1, log=print) -> list:
    """--check for BMC: every question decided again from scratch in a scratch root; each result file and each query
    file it names must be byte-identical to the committed one, and every question must have a committed result.
    Returns the differences."""
    import tempfile
    import shutil
    diff = []
    tmp = Path(tempfile.mkdtemp(prefix="holon-refute-check-"))
    try:
        got = bmc_stage(root, side, env, only_ids, jobs, log, out_root=tmp, redo=True)
        for qid, r in sorted(got.items()):
            name = f"{qfile(qid)}.json"
            a, b = root / GENR / "bmc" / name, tmp / GENR / "bmc" / name
            if not a.is_file():
                diff.append(f"bmc/{name} ({qid}): no committed result")
                continue
            if r is None or not b.is_file():
                diff.append(f"bmc/{name} ({qid}): no verdict on recomputation")
                continue
            if a.read_bytes() != b.read_bytes():
                diff.append(f"bmc/{name} ({qid}): result differs")
                continue
            for qf in r.get("queries") or []:
                if not same_query(root / qf, tmp / qf):
                    diff.append(f"{qf}: query file differs")
        if not only_ids:
            named = {f"{qfile(q['id'])}.json" for q in questions(root, side, env)}
            for f in sorted((root / GENR / "bmc").glob("*")):
                if f.name not in named:
                    diff.append(f"bmc/{f.name}: no question has this result")
            want = {str(Path(qf)) for qid in got for qf in (cached(root, qid) or {}).get("queries") or []}
            for f in sorted((root / GENR / "smt" / "bmc").rglob("*")):
                if f.is_file() and str(f.relative_to(root)) not in want:
                    diff.append(f"{f.relative_to(root)}: no committed result names this query file")
        return diff
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def same_query(a: Path, b: Path) -> bool:
    """Two query files hold the same query: equal bytes, or for .gz equal decompressed text (gzip's bytes depend on
    the zlib build, the query does not)."""
    if not a.is_file() or not b.is_file():
        return False
    if a.suffix == ".gz":
        import gzip
        return gzip.decompress(a.read_bytes()) == gzip.decompress(b.read_bytes())
    return a.read_bytes() == b.read_bytes()


def cached(root: Path, qid: str) -> dict | None:
    """A cached BMC result; a no_path verdict is labelled with the environment it is relative to (the answer model's
    label in refute_env.json, docs/HUMAN_ANSWERS.md Q28): never 'unreachable'."""
    p = root / GENR / "bmc" / f"{qfile(qid)}.json"
    if not p.is_file():
        return None
    r = load(p)
    if r.get("verdict") == "no_path":
        ep = root / "spec" / "M3" / "refute_env.json"
        label = ((load(ep).get("environment") or {}).get("label") if ep.is_file() else None) or "this environment"
        r = dict(r, reason=f"no path in {label}, not 'unreachable': {r['reason']}")
    return r


# ------------------------------------------------------------------------------------------------ records and sides
RECORD_DIRS = ("M0", "M1", "M2", "M2/extracted_m1", "M3")
NOT_BUILT = "not run: this engine is not built in the I40 build (docs/iterations/I40.md, Not done)"


def records(root: Path) -> dict:
    out = {}
    for d in RECORD_DIRS:
        for p in sorted((root / "results" / d).glob("L*.json")):
            out[f"{d}/{p.stem}"] = load(p)
    return out


def i4_sides(root: Path) -> dict:
    """The replay sides of every record with an entry in replay/<M>/report.json (M0 entries hold sides directly)."""
    from .filter import sides as sides_of
    out = {}
    for m in ("M0", "M1", "M2"):
        p = root / "replay" / m / "report.json"
        if not p.is_file():
            continue
        for lid, entry in (load(p).get("laws") or {}).items():
            out[f"{m}/{lid}"] = {k: v for k, v in sides_of(entry).items() if isinstance(v, dict)}
    return out


def law_of(root: Path, key: str) -> dict:
    d, _, lid = key.rpartition("/")
    m = "M1" if d == "M2/extracted_m1" else d
    p = root / "laws" / m / f"{lid}.json"
    return load(p) if p.is_file() else {}


def _has_key(o, k: str) -> bool:
    if isinstance(o, dict):
        return k in o or any(_has_key(v, k) for v in o.values())
    if isinstance(o, list):
        return any(_has_key(v, k) for v in o)
    return False


def witness_kind(rec: dict) -> str:
    """codec (two encodings differ), domain (a byte string and two definedness verdicts) or trace."""
    diff = rec.get("difference")
    w = rec.get("witness") if isinstance(rec.get("witness"), dict) else {}
    if isinstance(diff, dict) and isinstance(diff.get("lhs"), str) and isinstance(diff.get("rhs"), str):
        return "codec"
    if (isinstance(diff, dict) and isinstance(diff.get("lhs"), bool) and isinstance(diff.get("rhs"), bool)
            and len(w) == 1 and isinstance(next(iter(w.values())), str)):
        return "domain"
    return "trace"


def kind_of(rec: dict, law: dict, ss: dict) -> str:
    """Rules K1-K4: bmc (a blocking side, a migration in the statement, or a definedness witness), go_only (every
    side a Go library call), commit_class (a codec witness), direct (a schedule of public calls)."""
    provs = [s.get("provenance") for s in ss.values()]
    wk = witness_kind(rec)
    if any(p in ("internal_harness", "emulated_storage") for p in provs) or _has_key(law.get("statement"), "mig") \
            or wk == "domain":
        return "bmc"
    if provs and all(p == "library_api" for p in provs):
        return "go_only"
    if wk == "codec":
        return "commit_class"
    return "direct"


def trace_length(rec: dict) -> int | None:
    """The number of steps of a record's witness schedule: its longest list of steps."""
    best = None

    def walk(x):
        nonlocal best
        if isinstance(x, list) and x and all(isinstance(y, dict) and ("op" in y or "action" in y) for y in x):
            best = max(best or 0, len(x))
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(rec.get("witness"))
    return best


def target_of(env: dict, key: str, rec: dict, law: dict) -> str | None:
    """The concretization target of a K1 record: the target whose kind matches the witness (a definedness witness
    loads a byte string: a load target; otherwise a state target)."""
    wk = witness_kind(rec)
    for tid, t in sorted((env.get("targets") or {}).items()):
        if (wk == "domain") == (t.get("kind") == "load"):
            return tid
    return None


def write_record(p: Path, rec: dict) -> None:
    """Write a record in the formatting its file already has (indent 2, keys sorted; ASCII escaping as found)."""
    old = p.read_text(encoding="utf-8")
    for ea in (False, True):
        if json.dumps(json.loads(old), indent=2, sort_keys=True, ensure_ascii=ea) + "\n" == old:
            p.write_text(json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=ea) + "\n", encoding="utf-8")
            return
    p.write_text(json.dumps(rec, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def concretize(root: Path, side: dict, env: dict, write: bool = True) -> dict:
    """Q4 and the final filter: every REFUTED record at HEAD gets its concretization (K1-K4) and its final bin
    (holon.filter.final_bin over its I4 sides, each side an emitted test replaced taking the test's result)."""
    from . import filter as FL
    recs = records(root)
    sides = i4_sides(root)
    rep_p = root / "replay" / "M3" / "refute" / "report.json"
    rep = load(rep_p) if rep_p.is_file() else {"records": {}}
    H, rl = int(side["bmc"]["H"]), int(side["solver"]["rlimit_per_query"])
    cc_version = {pl["record"]: pl["version"] for pl in cc_plans(root, env)}
    out, filt, stale = {}, {}, []
    for key, rec in sorted(recs.items()):
        if rec.get("status") != "REFUTED":
            continue
        law = law_of(root, key)
        ss = dict(sides.get(key) or {})
        if not ss and key.startswith("M2/extracted_m1/"):
            ss = dict(sides.get("M1/" + key.rpartition("/")[2]) or {})
        from .rules import par_init as PI
        versioned = law.get("rule") == PI.RULE and law.get("subform") == PI.SUBFORM
        if not ss and versioned:
            # I28 (PI6): a PAR-init record's side is its run of the versions replay report (V9)
            from .versions.replay import side as versions_side
            vs = versions_side(root, key.rpartition("/")[0], key.rpartition("/")[2], rec.get("witness"))
            ss = {"solidity": vs} if vs else {}
        kind = kind_of(rec, law, ss)
        gen = ((rep.get("records") or {}).get(key) or {}).get("sides") or {}
        final_sides = {**ss, **gen}
        conc = {"kind": kind, "result": None, "length": None, "bound": None, "target": None,
                "tests": sorted({t for g in gen.values() for t in (g.get("tests") or [g.get("test")]) if t}),
                "sides": {k: {"status": v.get("status"), "provenance": v.get("provenance"),
                              "obstruction_observed": v.get("obstruction_observed")} for k, v in sorted(final_sides.items())},
                "reason": None}
        path = None
        if kind == "go_only":
            conc["reason"] = "node-level public path needs I39"
        elif kind == "commit_class":
            v = cc_version.get(key)
            r = cached(root, f"cc:v{v}") if v is not None else None
            if r is not None:
                r = confirmed(root, "cc", f"v{v}", r)
            conc.update(bound={"H": H, "rlimit": rl})
            m0 = [k for k, v in sorted(ss.items()) if v.get("provenance") == "public_schedule"
                  and v.get("status") == "passed"]
            if (r is None or r["verdict"] != "path") and m0:
                # the record's own replay is the M0 commit-path rule's commit (holon.mreplay.m0_commit_sides): a
                # public commit of the witness's version from the deployment's initial state
                conc.update(result="path", length=1,
                            reason=f"a commit at version {v} from R0 by the M0 commit-path rule (its I4 side {m0[0]}, "
                                   f"holon.mreplay.m0_commit_sides); BMC: "
                                   f"{r['reason'] if r is not None else 'not run'}")
            elif r is None:
                conc.update(result="unknown", reason="BMC on the witness's commit was not run within the I40 build's "
                                                      "time box")
            else:
                conc.update(result=r["verdict"], length=r["length"],
                            reason=f"a commit at version {v} from R0 (rule K3, the M0 commit-path rule): {r['reason']}")
                path = r["path"] if r["verdict"] == "path" else None
        elif kind == "direct":
            conc.update(result="path", length=(len((rec.get("witness") or {}).get("trace") or []) or None) if versioned
                        else trace_length(rec),
                        reason=("the witness is a schedule of public calls; its emitted tests are its side"
                                if gen else "the witness is a schedule of public calls (its replay is the record's side)"))
        else:
            tid = target_of(env, key, rec, law)
            conc.update(target=tid, bound={"H": H, "rlimit": rl})
            r = cached(root, f"target:{tid}") if tid else None
            if r is not None:
                r = confirmed(root, "target", tid, r)
            if r is None:
                conc.update(result="unknown", reason="BMC on the target was not run within the I40 build's time box")
            else:
                conc.update(result=r["verdict"], length=r["length"], reason=r["reason"])
                path = r["path"] if r["verdict"] == "path" else None
        if kind == "direct" and not final_sides:
            # no side in the sides format (no I4 side, no emitted test): its own replay lives in its iteration's report,
            # which this build does not read as a side, so F3 cannot hold (docs/iterations/I40.md, Questions)
            conc["reason"] = ("the witness is a schedule of public calls, but it has no side in the sides format (no I4 "
                              "side, no emitted test; its own replay report is not read as one): F3 cannot hold")
        ck = clock(path, rec)
        if ck and ck["label"]:
            conc["reason"] = f"{conc['reason']}; {ck['label']}: block.timestamp up to {ck['max_timestamp']}"
        fb = FL.final_bin(final_sides, conc)
        out[key] = dict(conc, path=path, clock=ck)
        before = (side["records"].get(key) or {}).get("filter_bin") if key in side["records"] else None
        filt[key] = {"before": before, "after": fb, "kind": kind, "result": conc["result"]}
        if rec.get("filter_bin") == "intended_bounded" and isinstance(rec.get("intended"), dict):
            # a record an intent contract marks (I65 = I33b, tests_m3/test_o12.py rule O6): the final rule's bin is
            # the one the mark replaces, and the mark stays (holon.contracts owns it)
            new = dict(rec, intended=dict(rec["intended"], replaces=fb), concretization=conc)
        else:
            new = dict(rec, filter_bin=fb, concretization=conc)
        if new != rec:
            stale.append(key)
            if write:
                d, _, lid = key.rpartition("/")
                write_record(root / "results" / d / f"{lid}.json", new)
    return {"concretization": {"document": "concretization", "H": H, "records": out},
            "filter": {"document": "filter", "rule": FL.FINAL_RULE, "records": filt}, "stale": stale}


def with_calls(root: Path, kind: str, ident: str, path):
    """A path with each step's env.calls the real deployment's answers (the replay's), as I30's witness format holds
    them; unchanged when the path has not been replayed."""
    rp = root / REPLAY
    if not path or not rp.is_file():
        return path
    e = (load(rp).get({"reach": "reaches", "i21": "i21", "target": "targets", "cc": "commit_class"}[kind]) or {}).get(ident)
    if not e or len(e.get("calls") or []) != len(path):
        return path
    out = []
    for st, cs in zip(path, e["calls"]):
        env = dict(st["env"], calls=[{"fn": None, "to": c["to"], "data": c["data"], "ok": c["ok"], "ret": c["ret"]}
                                     for c in cs])
        out.append(dict(st, env=env))
    return out


_SELECTORS: dict = {}


def selectors(root: Path, side: dict) -> dict:
    """selector (0x + 8 hex) -> (function name, its ABI), over the extracted document's member ABIs."""
    from .machine import load_extracted
    k = (str(root), side["documents"][0])
    if k not in _SELECTORS:
        members = load_extracted(side["documents"][0], root).info.get("members") or {}
        by_sel = {}
        for fn, abis in sorted(members.items()):
            for abi in abis or []:
                if abi.get("selector"):
                    by_sel.setdefault(abi["selector"].lower(), (fn, abi))
        _SELECTORS[k] = by_sel
    return _SELECTORS[k]


def call_failed(root: Path, side: dict, calls: list, fn: str) -> bool:
    """Whether a step's real external calls include a call to fn (named by its selector) that failed."""
    by_sel = selectors(root, side)
    for c in calls or []:
        data = c["data"][2:] if c["data"].startswith("0x") else c["data"]
        hit = by_sel.get("0x" + data[:8].lower())
        if hit is not None and hit[0] == fn and not c["ok"]:
            return True
    return False


def answer_mismatch(root: Path, side: dict, env: dict, path: list[dict], real_calls: list) -> str | None:
    """env_mismatch (the contract's E-BMC): None when every external call the real contract made along a BMC path
    answers as the answer table (spec/M3/refute_env.json "answers") says, else the first call that does not, named.
    The table is evaluated concretely: a call is named by its selector in the extracted document's member ABIs and
    its arguments decoded from its calldata; a call with no answer in the table is BMC's free choice (a fresh answer)
    and agrees with any real answer; a ghost written by a call (its "ghost" entries) is read by the later steps' calls
    (BMC applies a step's ghost writes at the step's end). Only a return's first word is compared (the table answers
    one word), and the table's code-length answers are not compared (the harness records calls, not extcodesize)."""
    from .extracted_eval import abi_decode
    answers = env.get("answers") or {}
    by_sel = selectors(root, side)
    ghost: dict = {}

    def word(x) -> int:
        if isinstance(x, bool):
            return int(x)
        if isinstance(x, int):
            return x
        if isinstance(x, str):
            return int(x, 16) if x.lower().startswith("0x") else int(x)
        raise ValueError(f"not a word: {x!r}")

    def ev(t, ctx):
        if not isinstance(t, list):
            return word(t)
        op = t[0]
        if op == "arg":
            return ctx["args"][int(t[1])]
        if op == "receiver":
            return ctx["receiver"]
        if op == "env":
            return ctx["env"][t[1]]
        if op == "ghost":
            return ghost.get((t[1], ev(t[2], ctx)), 0)
        if op == "len":
            return len(ev(t[1], ctx))
        if op == "byte":
            b, i = ev(t[1], ctx), ev(t[2], ctx)
            return b[i] if i < len(b) else 0
        if op == "!":
            return int(not ev(t[1], ctx))
        if op == "&&":
            return int(all(ev(x, ctx) for x in t[1:]))
        if op == "||":
            return int(any(ev(x, ctx) for x in t[1:]))
        a, b = ev(t[1], ctx), ev(t[2], ctx)
        return int({"==": a == b, "!=": a != b, "<=": a <= b, "<": a < b, ">": a > b, ">=": a >= b}[op])

    for i, (st, calls) in enumerate(zip(path, real_calls)):
        stenv = {"block.timestamp": int(str(st["env"]["block.timestamp"]), 0)}
        writes = []
        for c in calls or []:
            data = bytes.fromhex(c["data"][2:]) if c["data"].startswith("0x") else bytes.fromhex(c["data"])
            to = int(c["to"], 16)
            if not data:
                fn, args = "address.call", []
            else:
                hit = by_sel.get("0x" + data[:4].hex())
                if hit is None:
                    continue                      # not an interface call the table answers
                fn, abi = hit
                args = abi_decode(data[4:], abi.get("inputs") or [])
                args = [bytes.fromhex(a[2:]) if isinstance(a, str) and a.startswith("0x") and
                        p.get("type") in ("bytes", "string") else
                        (int(a, 16) if isinstance(a, str) and a.startswith("0x") else
                         (a if isinstance(a, (bytes, bytearray)) else word(a)))
                        for a, p in zip(args, abi.get("inputs") or [])]
            spec = answers.get(fn)
            if spec is None:
                continue                          # BMC's fresh answer: any real answer agrees
            ctx = {"args": args, "receiver": to, "env": stenv}
            want_ok = bool(ev(spec.get("ok", 1), ctx))
            got_ok = bool(c["ok"])
            if want_ok != got_ok:
                return f"step {i} {st['action']}: {fn} answered ok={got_ok}, the answer table says ok={want_ok}"
            if want_ok and spec.get("ret") is not None:
                ret = c.get("ret") or "0x"
                got = int(ret[2:66] or "0", 16) if ret.startswith("0x") else int(ret[:64] or "0", 16)
                want = ev(spec["ret"], ctx)
                if got != want:
                    return f"step {i} {st['action']}: {fn} returned {got}, the answer table says {want}"
            if want_ok:
                for g in spec.get("ghost") or []:
                    writes.append(((g["name"], ev(g["key"], ctx)), ev(g["value"], ctx)))
        for k, v in writes:
            ghost[k] = v
    return None


def confirmed(root: Path, kind: str, ident: str, r: dict) -> dict:
    """A cached BMC result with its replay applied: a path the real contract does not reproduce (outcomes differing
    from the model's) is a candidate of the encoding's over-approximation, and the verdict is unknown with that
    reason (never path, never no_path); a path not yet replayed stays a candidate (unknown)."""
    if r["verdict"] != "path":
        return r
    rp = root / REPLAY
    e = (load(rp).get({"reach": "reaches", "i21": "i21", "target": "targets", "cc": "commit_class"}[kind]) or {}).get(ident) \
        if rp.is_file() else None
    if e is None:
        return dict(r, verdict="unknown", length=None, path=None,
                    reason=f"a candidate path of length {r['length']} (k = {r['largest_k']}) not replayed yet")
    if e.get("calls_agree") is False:
        return dict(r, verdict="unknown", length=None, path=None,
                    reason=f"env_mismatch: {e.get('env_mismatch') or 'an external call answered otherwise than the answer table'}")
    if e.get("status") != "passed":
        return dict(r, verdict="unknown", length=None, path=None, largest_k=max(0, r["largest_k"] - 1),
                    reason=f"spurious candidate: the encoding's path of length {r['length']} (over-approximations: "
                           f"{len(r.get('approx') or [])}) replays as {' / '.join(e.get('outcomes') or [])} on the real "
                           f"contract, not {' / '.join(e.get('expected') or [])}; k <= {r['largest_k'] - 1} decided")
    return r


CLOCK_REALISTIC = 1 << 64     # R7: a path whose block.timestamp exceeds this is labelled (the sidecar has no bound)


def clock(path, rec: dict | None = None) -> dict | None:
    """The largest block.timestamp a path needs, or a record's witness sets (any "block.timestamp" in it), and a label
    when no realistic chain reaches it (the sidecar's environment has no clock bound; the label changes no verdict
    and no bin)."""
    ts = [int(str(st["env"]["block.timestamp"]), 0) for st in path or []]

    def walk(x):
        if isinstance(x, dict):
            for k, v in sorted(x.items()):
                if k == "block.timestamp" and isinstance(v, (int, str)) and not isinstance(v, bool):
                    ts.append(int(str(v), 0))
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk((rec or {}).get("witness"))
    if not ts:
        return None
    t = max(ts)
    return {"max_timestamp": t, "label": "unrealistic clock (> 2^64)" if t > CLOCK_REALISTIC else None}


def reach_docs(root: Path, side: dict) -> dict:
    H = int(side["bmc"]["H"])
    reaches = {}
    for rid in side["unfalsified_reaches"]:
        r = cached(root, f"reach:{rid}")
        if r is not None:
            r = confirmed(root, "reach", rid, r)
        if r is None:
            reaches[rid] = {"verdict": "unknown", "length": None, "path": None, "largest_k": 0,
                            "reason": "not run: no verdict recorded (the search did not run to completion in this "
                                      "build); not a conclusion"}
        else:
            reaches[rid] = {"verdict": r["verdict"], "length": r["length"],
                            "path": with_calls(root, "reach", rid, r["path"]),
                            "largest_k": r["largest_k"], "reason": r["reason"], "clock": clock(r["path"])}
    return {"document": "reaches", "source": "results/M2/refinement/extracted.json", "H": H, "reaches": reaches}


def i21_doc(root: Path, side: dict) -> dict:
    f = {}
    for fid in sorted(k for k in side["i21"] if k not in ("doc", "out_of_scope")):
        r = cached(root, f"i21:{fid}")
        if r is not None:
            r = confirmed(root, "i21", fid, r)
        evm = ({"verdict": "unknown", "length": None, "path": None, "largest_k": 0,
                "reason": "not run: no verdict recorded (the search did not run to completion in this build)"} if r is None else
               {"verdict": r["verdict"], "length": r["length"], "path": with_calls(root, "i21", fid, r["path"]),
                "largest_k": r["largest_k"], "reason": r["reason"], "clock": clock(r["path"])})
        x = {"evm": evm}
        if side["i21"][fid].get("go"):
            x["go"] = {"verdict": "out_of_scope", "reason": side["i21"][fid]["go"]}
        f[fid] = x
    return {"document": "i21", "findings": f, "out_of_scope": side["i21"]["out_of_scope"]}


def unknowns_doc(root: Path, side: dict, codec: dict | None = None, fuzzed: dict | None = None) -> dict:
    rl = int(side["solver"]["rlimit_per_query"])
    fz = side["fuzz"]
    laws = {}
    dv = load(root / "laws" / "M2" / "DERIVATION.json")
    for u in side["unknowns"]:
        rec = records(root).get(u["record"]) or {}
        atts = []
        e = next((x for x in dv["laws"] if x["law_id"] == u["law_id"]), None)
        if u["facts"] in side["documents"] and e is not None and e.get("subform") == "width":
            r = cached(root, f"width:{u['record']}")
            if r is None:
                atts.append({"engine": "bmc", "bound": {"H": int(side["bmc"]["H"])}, "budget": {"rlimit": rl},
                             "result": "not_run", "candidates": 0, "accepted": 0, "discarded": [],
                             "reason": "not run: no verdict recorded (the search did not run to completion in this build)",
                             "length": None, "largest_k": 0})
            else:
                atts.append({"engine": "bmc", "bound": {"H": int(side["bmc"]["H"])}, "budget": {"rlimit": rl},
                             "result": r["verdict"], "candidates": 0 if r["verdict"] != "path" else 1, "accepted": 0,
                             "discarded": [] if r["verdict"] != "path" else [{"witness": {"steps": r["path"]},
                                                                              "checker": {"exit_code": None,
                                                                                          "marker": "not checked"}}],
                             "reason": r["reason"], "length": r["length"], "largest_k": r["largest_k"]})
        elif u["facts"].startswith("spec/M1/") and u["record"].startswith("M2/extracted_m1/"):
            atts.append({"engine": "none", "bound": None, "budget": None, "result": "not_run", "candidates": 0,
                         "accepted": 0, "discarded": [], "reason": "a law that reads a hand-written ghost is not run on "
                                                                   "the view (lead decision A3)"})
        else:
            bound = {"steps": int(side["smt"]["hand_trace_bound"])} if u["facts"].startswith("spec/") \
                else {"byte_length_max": int(side["smt"]["byte_length_max"])}
            cx = ((codec or {}).get("laws") or {}).get(u["record"])
            if cx is not None and cx.get("solver") in ("sat", "unsat", "unknown") and cx.get("query"):
                cand = cx.get("candidate")
                atts.append({"engine": "smt", "bound": bound, "budget": {"rlimit": rl}, "result": cx["solver"],
                             "candidates": 1 if cand else 0, "accepted": 1 if cand and cand["accepted"] else 0,
                             "discarded": [] if not cand or cand["accepted"] else
                             [{"witness": cand["witness"], "checker": cand["checker"]}],
                             "reason": f"the law's negation over its component model ({cx['query']}): {cx['solver']}"})
            else:
                # an engine this build does not have for the law's model: no attempt of that engine (engine none,
                # naming the engine the contract plans)
                atts.append({"engine": "none", "planned": "smt", "bound": None, "budget": None, "result": "not_run",
                             "candidates": 0, "accepted": 0, "discarded": [], "reason": NOT_BUILT})
            fa = (fuzzed or {}).get(u["record"])
            atts.append(fa if fa is not None else
                        {"engine": "none", "planned": "fuzz", "bound": None, "budget": None, "result": "not_run",
                         "candidates": 0, "accepted": 0, "discarded": [], "reason": NOT_BUILT})
        laws[u["record"]] = {"status": rec.get("status"), "attempts": atts}
    return {"document": "unknowns", "laws": laws}


def refind_doc(side: dict) -> dict:
    s = side["solver"]
    return {"document": "refind", "solver": {"name": s["name"], "version": s["version"], "random_seed": s["random_seed"],
                                             "rlimit": s["rlimit_per_query"]},
            "classes": {c["id"]: {"record": c["record"], "law_id": c["law_id"], "entry": c["entry"], "kind": c["kind"],
                                  "query": None, "result": "unknown", "bound": None, "candidates": [], "refound": False,
                                  "reason": NOT_BUILT} for c in side["classes"]}}


def codec_doc(side: dict) -> dict:
    return {"document": "codec", "laws": {x["record"]: {"status": x["status"], "solver": "unknown", "query": None,
                                                        "candidate": None, "reason": NOT_BUILT}
                                          for x in side["codec_laws"]}}


def fuzz_doc(side: dict) -> dict:
    return {"document": "fuzz", "seed": side["fuzz"]["seed"], "laws": {}}


def fuzz_stage(root: Path, side: dict, log=print) -> dict:
    """E-FUZZ on every UNKNOWN record whose law is over a linked codec component (the compiled component model is
    the evaluator; holon.fuzz): per record the attempt as unknowns.json states it; a candidate counts only through
    its counter-law (Bend and BendTT)."""
    import hashlib
    from . import bend, fuzz as FZ
    from .gen import linked as L
    fz = side["fuzz"]
    n, seed = int(fz["candidates_per_law"]), int(fz["seed"])
    out = {}
    cms = {}
    for u in side["unknowns"]:
        law = law_of(root, u["record"])
        if not law.get("facts"):
            continue
        raw = (root / law["facts"]).read_bytes()
        doc = json.loads(raw)
        if doc.get("linked_version") is None:
            continue
        if law["facts"] not in cms:
            cms[law["facts"]] = L.CompiledModel.build(doc, hashlib.sha256(raw).hexdigest(), doc["role"], bend.config(root))
        r = FZ.linked_fuzz(cms[law["facts"]], law, n, seed, int(side["smt"]["byte_length_max"]))
        acc, disc = 0, []
        for i, w in enumerate(r["found"]):
            if i >= 8:
                disc.append({"witness": w, "checker": {"exit_code": None, "marker": "not checked: beyond the first 8 "
                                                                               "candidates of the law"}})
                continue
            chk = check_counter(law, doc, w, root / GENR / "fuzz" / law["law_id"] / f"c{i}", root)
            if chk["accepted"]:
                acc += 1
            else:
                disc.append({"witness": w, "checker": chk["checker"]})
        out[u["record"]] = {"engine": "fuzz", "bound": {"candidates": n, "seed": seed}, "budget": {"candidates": n},
                            "result": "found" if acc else "none", "candidates": acc + len(disc), "accepted": acc,
                            "discarded": disc,
                            "reason": (f"{r['tried']} candidates evaluated on the compiled component model: "
                                       f"{len(r['found'])} separate the claim's sides")}
        log(f"fuzz {u['record']}: {out[u['record']]['result']} ({len(r['found'])} of {r['tried']})")
    return out


def main(a, root: Path) -> int:
    side = load(root / (a.sidecar or "spec/M3/lib/refute.json"))
    env = load(root / "spec" / "M3" / "refute_env.json")
    why = SR.pin_check(side["solver"])
    if why:
        print(f"holon refute: the pinned solver is not installed as pinned: {why}")
        return 2
    stages = [x.strip() for x in (a.only or "layouts,smt,fuzz,bmc,emit,replay,filter").split(",") if x.strip()]
    outd = root / REFUTE
    files = {}
    texts = {}
    if "layouts" in stages:
        from .smt import layouts as LY
        hdr = load(root / "spec" / "M2" / "facts" / "morph_header.extracted.json")
        res = {}
        for fn in sorted(hdr["functions"]):
            q = LY.query(hdr, fn, int(side["solver"]["rlimit_per_query"]), int(side["smt"]["byte_length_max"]))
            text = q.text()
            texts[GENR / "smt" / "layouts" / f"{fn}.smt2"] = text
            sess = SR.Session(side["solver"])
            try:
                res[fn] = {"query": str(GENR / "smt" / "layouts" / f"{fn}.smt2"), "result": sess.check(text),
                           "claim": "exactly one path of the document applies to every input (unsat)"}
            finally:
                sess.close()
        files["layouts.json"] = {"document": "layouts", "source": "spec/M2/facts/morph_header.extracted.json",
                                 "functions": res}
    ids = [x for x in (getattr(a, "questions", None) or "").split("|") if x] or None
    if ids:
        known = {q["id"] for q in questions(root, side, env)}
        bad = [x for x in ids if x not in known]
        if bad:
            print(f"holon refute: no such question: {' | '.join(bad)}")
            return 2
    jobs = int(getattr(a, "jobs", None) or 1)
    diff = []
    if "bmc" in stages and not a.check:
        bmc_stage(root, side, env, ids, jobs=jobs)
    if "bmc" in stages and a.check:
        diff += bmc_check(root, side, env, ids, jobs=jobs)
    if "smt" in stages:
        if not a.check:
            import shutil
            shutil.rmtree(root / GENR / "codec", ignore_errors=True)   # the stage writes every file it keeps
        cdoc, refound, ctexts = codec_stage(root, side)
        texts.update(ctexts)
        rdoc = refind_doc(side)
        rdoc["classes"].update(refound)
        files["refind.json"] = rdoc
        files["codec.json"] = cdoc if cdoc is not None else codec_doc(side)
    fuzzed = None
    if "fuzz" in stages:
        fuzzed = fuzz_stage(root, side)
        fd = fuzz_doc(side)
        fd["laws"] = {k: {"tried": int(side["fuzz"]["candidates_per_law"]), "accepted": v["accepted"]}
                      for k, v in sorted(fuzzed.items())}
        files["fuzz.json"] = fd
    if "emit" in stages:
        for rp, text in emit_tests(root, side, env).items():
            texts[rp] = text
        if not a.check:
            import shutil
            shutil.rmtree(root / TESTS, ignore_errors=True)
    if "replay" in stages:
        rep = dumps(replay_stage(root, side, env))
        if a.check:
            if not (root / REPLAY).is_file() or (root / REPLAY).read_text(encoding="utf-8") != rep:
                diff.append(str(REPLAY))
        else:
            (root / REPLAY).parent.mkdir(parents=True, exist_ok=True)
            (root / REPLAY).write_text(rep, encoding="utf-8")
    if "bmc" in stages:
        files["reaches.json"] = reach_docs(root, side)
        files["i21.json"] = i21_doc(root, side)
    if {"bmc", "smt", "fuzz"} & set(stages):
        cpath = root / REFUTE / "codec.json"
        codec_now = files.get("codec.json") or (load(cpath) if cpath.is_file() else None)
        if fuzzed is None:
            up = root / REFUTE / "unknowns.json"
            prev = load(up)["laws"] if up.is_file() else {}
            fuzzed = {k: a for k, v in prev.items() for a in v["attempts"] if a["engine"] == "fuzz"
                      and a["result"] != "not_run"}
        files["unknowns.json"] = unknowns_doc(root, side, codec_now, fuzzed)
    if "filter" in stages:
        docs = concretize(root, side, env, write=not a.check)
        files["concretization.json"] = docs["concretization"]
        files["filter.json"] = docs["filter"]
        if a.check:
            diff += [f"{k}: the record's concretization or filter_bin is not the recomputed one" for k in docs["stale"]]
    for rp, text in sorted(texts.items()):
        p = root / rp
        if a.check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                diff.append(str(rp))
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    for n, d in sorted(files.items()):
        p = outd / n
        text = dumps(d)
        if a.check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                diff.append(n)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    if a.check and diff:
        print(f"holon refute --check: differs: {', '.join(diff)}")
        return 1
    print(f"holon refute --milestone M3: {', '.join(sorted(files))}")
    return 0


# ------------------------------------------------------------------------------------------------ the real side
class RealRollup:
    """The binding's step harness on the real contract (holon.replay_fragments), one project per run: each path's
    steps as call steps from the binding's deployment; per path the outcomes and the calls the real code made."""

    def __init__(self, root: Path, side: dict):
        self.root, self.side = root, side
        self.work = None

    def setup(self):
        import argparse
        import tempfile
        from .fragments_corpus import binding_init
        from .replay import check_checkout, morph_path, toolchain
        from .replay_fragments import forge_build, harness_project, load_binding
        if self.work is not None:
            return
        self.binding = load_binding(self.root / self.side["binding"])
        checkout = morph_path(argparse.Namespace(), self.root)
        doc = load(self.root / self.side["documents"][0])
        check_checkout(checkout, (doc.get("target") or {}).get("commit"))
        self.tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), self.root)
        self.work = Path(tempfile.mkdtemp(prefix="holon-refute-m3-"))
        self.proj = harness_project(self.binding, self.work, self.root, checkout, self.tc)
        forge_build(self.proj, self.tc)
        self.init = binding_init(self.binding, self.root)

    def run(self, paths: list[list[dict]]) -> list[dict]:
        from .replay_fragments import Step, run_harness
        from .refute3 import revert_key
        self.setup()
        traces = [[Step(kind="call", caller=s["env"]["caller"], value=int(s["env"].get("msg.value", 0)),
                        timestamp=int(s["env"]["block.timestamp"]), blobs=list(s["env"].get("blobhash") or []),
                        to=None, data=s["calldata"]) for s in pth] for pth in paths]
        runs = run_harness(self.proj, self.tc, self.binding, traces, [], self.init, tag="refute")
        out = []
        for tr in runs:
            execs = [e for e in tr.execs if e.id != "d"]
            out.append({"outcomes": ["ok" if e.ok else "rev " + revert_key(bytes.fromhex(e.ret[2:])) for e in execs],
                        "calls": [[{"to": c[0], "data": c[1], "ok": bool(c[2]), "ret": c[3]} for c in e.calls]
                                  for e in execs]})
        return out

    def close(self):
        import shutil
        if self.work is not None:
            shutil.rmtree(self.work, ignore_errors=True)
            self.work = None


def call_check(m: BMC.Machine, q: dict) -> str | None:
    """The external function a check target bubbles (a "call" check: the revert of a failed call), else None."""
    t = q["target"]
    if t["kind"] != "check":
        return None
    c = next(x for x in m.progs[t["action"]].checks() if x.id == t["check"])
    return ((c.entry or {}).get("fn") or c.reason) if c.kind == "call" else None


def outcomes_agree(got: list, exp: list) -> bool:
    """The real outcomes are the model's: equal, where "rev *" (a bubbled call's revert) is any revert."""
    return len(got) == len(exp) and all(g == e or (e == "rev *" and g.startswith("rev ")) for g, e in zip(got, exp))


def expected_outcomes(m: BMC.Machine, q: dict, path: list[dict]) -> list[str]:
    """What the BMC model claims of a path: every step ok but the last; a check target's last step reverts with that
    check's revert key (its reason, or its Panic code); a call check's revert data is the callee's own ("rev *", any
    revert; the replay also requires that the step's recorded call to that function failed)."""
    t = q["target"]
    if t["kind"] != "check":
        return ["ok"] * len(path)
    prog = m.progs[t["action"]]
    c = next(x for x in prog.checks() if x.id == t["check"])
    if c.kind == "call":
        key = "*"
    elif c.kind == "panic" and c.code is not None:
        key = f"panic:0x{int(c.code):02x}"
    else:
        key = c.reason if isinstance(c.reason, str) else str(c.reason)
    return ["ok"] * (len(path) - 1) + [f"rev {key}"]


# ------------------------------------------------------------------------------------------------ emit and replay
TESTS = Path("gen") / "M3" / "tests"
REPLAY = Path("replay") / "M3" / "refute" / "report.json"


def bmc_paths(root: Path, side: dict, env: dict) -> list[tuple[str, dict, dict]]:
    """(question id, question, cached result) of every BMC question whose verdict is path."""
    out = []
    for q in questions(root, side, env):
        r = cached(root, q["id"])
        if r is not None and r["verdict"] == "path" and r.get("path") and not q["id"].startswith("cc:"):
            out.append((q["id"], q, r))
    return out


def cc_items(root: Path, env: dict) -> list[dict]:
    """Rule K3's emitted Foundry tests: per commit_class record with a BMC commit path at its version, the path and
    the model's stored headers that show the obstruction (the Solidity side's bytes at every cell where the sides
    differ); the test asserts the commit succeeds and stores the hash of one of them."""
    out = []
    for pl in cc_plans(root, env):
        qid = f"cc:v{pl['version']}"
        r = cached(root, qid)
        if r is None or r["verdict"] != "path" or not r.get("path"):
            continue
        sol = bytes.fromhex(pl["sol"][2:])
        inputs = set()

        def strings(x):
            if isinstance(x, dict):
                for v in x.values():
                    strings(v)
            elif isinstance(x, list):
                for v in x:
                    strings(v)
            elif isinstance(x, str) and x.startswith("0x"):
                inputs.add(x.lower())
        strings([st["args"] for st in r["path"]])
        cands = []
        for h in r.get("observed") or []:
            if h.lower() in inputs:      # a byte string the path passed in, not one the step built
                continue
            b = bytes.fromhex(h[2:])
            if len(b) == len(sol) and all(b[j] == sol[j] for j in pl["cells"]):
                cands.append(h)
        d, _, lid = pl["record"].rpartition("/")
        from .gen.foundry import sanitize
        out.append(dict(pl, qid=qid, path=r["path"], stored=cands, name=sanitize(f"{d}_{lid}"),
                        test=str(TESTS / "foundry" / d.replace("/", "_") / f"{lid}.t.sol")))
    return out


RULE_REPLAYS = ("sorts", "disch", "undo")      # replay/M3/<rule>/report.json written by each rule's own replay


def _outcome(obs) -> str:
    """An outcome string of a rule replay's model column: a string already, or an observation {"status", "ret"}."""
    if isinstance(obs, str):
        return obs
    if obs.get("status") == "ok":
        return "ok"
    from .refute3 import revert_key
    ret = obs.get("ret") or "0x"
    return "rev " + revert_key(bytes.fromhex(ret[2:] if ret.startswith("0x") else ret))


def direct_items(root: Path) -> list[dict]:
    """Rule K4's emitted tests for the direct REFUTED records of M3 that have no I4 side: each schedule the record's
    rule replayed (replay/M3/<rule>/report.json: a SORT entry point's trace, a DISCH trace, an UNDO pair's runs with
    and without x;y) as a Foundry test from its calldata, asserting the model's outcome at every step (the replay
    report's model column, never the real one). Generic: the schedules are read from the reports' shapes."""
    from .gen.foundry import sanitize
    recs = records(root)
    sides = i4_sides(root)
    out = []
    for rule in RULE_REPLAYS:
        rp = root / "replay" / "M3" / rule / "report.json"
        if not rp.is_file():
            continue
        laws = load(rp).get("laws") or {}
        for lid, e in sorted(laws.items()):
            key = f"M3/{lid}"
            rec = recs.get(key)
            if not rec or rec.get("status") != "REFUTED" or sides.get(key):
                continue
            runs = []
            if isinstance(e.get("entries"), dict):
                for entry, x in sorted(e["entries"].items()):
                    runs.append((entry, x["trace"], [_outcome(o) for o in x["model"]]))
            elif isinstance(e.get("with"), dict) and isinstance(e.get("without"), dict):
                for part in ("with", "without"):
                    runs.append((part, e[part]["trace"], [_outcome(o) for o in e[part]["model"]]))
            elif isinstance(e.get("trace"), list):
                runs.append((None, e["trace"], [_outcome(o) for o in e["model"]]))
            for part, trace, exp in runs:
                stem = lid if part is None else f"{lid}__{part}"
                out.append({"record": key, "rule": rule, "part": part, "trace": trace, "expected": exp,
                            "stem": stem, "name": sanitize(f"M3_{stem}"),
                            "test": str(TESTS / "foundry" / "M3" / f"{stem}.t.sol"), "replay": e, "slots_at": None})
    dw = disch_words(root, [it["record"] for it in out if it["rule"] == "disch"])
    for it in out:
        if it["rule"] == "disch":
            it["slots_at"] = dw.get(it["record"])
    return out


_DISCH_WORDS: dict = {}


def disch_words(root: Path, keys: list[str]) -> dict:
    """For direct DISCH records: the storage words the law's B and c read, on the model's states before and after the
    witness's last step: {record: {-1 or step index: [(slot, word)]}}. The slots are the ones holon.disch.run's
    replay_one dumps from the real contract to evaluate B and c (the same reading, done here on the model's states
    only, never on the real run's); the emitted test asserts the real contract's words equal the model's there, so the
    obstruction (B held before the last step, then c discharged, as the counter-law evaluates on these words) is in
    what the test asserts."""
    keys = sorted(keys)
    ck = (str(root), tuple(keys))
    if ck in _DISCH_WORDS:
        return _DISCH_WORDS[ck]
    out = {}
    if keys:
        from . import extracted_eval as EV
        from .disch import run as DR
        from .sorts import run3 as R3
        recs = records(root)
        r = DR.Run("M3", root, None, None, None, None, log=lambda *a, **k: None)
        try:
            for key in keys:
                lid = key.rpartition("/")[2]
                d = r.doc_of(r.ctx.derivation[lid])
                law = r.law_of(d, lid)
                w = recs[key]["witness"]
                steps = [R3.step_of_json(x) for x in w["steps"]]
                t = int(w["t"])
                b = next(x for x in d.an["basis"] if x["tag"] == law["tag"])
                scope = b["check"].split("#")[0]
                mm = d.model_f()
                g = mm.s0()
                states = [mm.state(g)]
                for st in steps:
                    _c, g, _calls = mm.run_step(g, st, save=True)
                    states.append(mm.state(g))
                now = int(steps[-1].env.get("block.timestamp") or 0)

                def reads(state, term, ts):
                    class Rec(dict):
                        def get(self, k, default=None):
                            self.seen.add(k)
                            return super().get(k, default)
                    rr = Rec(state)
                    rr.seen = set()
                    try:
                        e = EV.Eval(d.doc, {}, scope, {}, {"block.timestamp": ts})
                        e.state = rr
                        e.truth(term)
                    except Exception:  # noqa: BLE001  (a term the evaluator cannot read names no slot)
                        pass
                    return rr.seen
                slots = sorted(reads(states[-2], b["blocked"], t) | reads(states[-1], b["blocked"], now)
                               | reads(states[-1], b["check_expr"], now))

                def word(x) -> int:
                    return int(str(x), 0) if x is not None else 0
                n = len(steps)
                out[key] = {n - 2: [(int(sl), word(states[-2].get(sl))) for sl in slots],
                            n - 1: [(int(sl), word(states[-1].get(sl))) for sl in slots]}
        finally:
            r.close()
    _DISCH_WORDS[ck] = out
    return out


def direct_side(items: list[dict], tests_out: dict) -> dict:
    """The record side of a direct record's emitted tests: passed iff every test passed (every step's outcome the
    model's); the obstruction observed iff the tests passed and the obstruction the rule claims is in what they
    assert, or was evaluated by the rule's own replay on the same deployment and calls (named in "basis")."""
    rule, e = items[0]["rule"], items[0]["replay"]
    res = [tests_out.get(it["stem"]) or {} for it in items]
    passed = bool(res) and all(r.get("passed") for r in res)
    rule_ok = e.get("status") == "passed" if "entries" not in e else \
        all(x.get("status") == "passed" for x in e["entries"].values())
    if rule == "sorts":
        obs = passed and rule_ok and all(x.get("obstruction_observed") is True for x in e["entries"].values())
        basis = ("the emitted tests assert every step's outcome, the realization's panic included; its site is the rule "
                 "replay's panic_site (replay/M3/sorts/report.json)" if obs else
                 "the obstruction is not in what the tests assert (a ghost tag, or the rule replay did not observe it)")
    elif rule == "disch":
        obs = (passed and rule_ok and e.get("blocked_before") is True and e.get("discharged_after") is True
               and all(any((it.get("slots_at") or {}).values()) for it in items))
        basis = ("the emitted test asserts every step's outcome and, before and after the last step, the real "
                 "contract's words at every slot B and c read equal the model's, on which B held before and c after "
                 "(the counter-law's evaluation); the rule's replay evaluated B and c on the real words of the same "
                 "deployment and calls (replay/M3/disch/report.json)")
    else:
        w = [it for it in items if it["part"] == "with"][0]["expected"]
        wo = [it for it in items if it["part"] == "without"][0]["expected"]
        pre, t_at = len(wo) - (len(w) - int(e["t_at"])), int(e["t_at"])
        dm = next((i for i in range(len(w) - t_at) if w[t_at + i] != wo[pre + i]), None)
        obs = passed and rule_ok and dm is not None and dm == e.get("diverges_at")
        basis = (f"the two emitted runs (with and without x;y) diverge at t[{dm}] in the outcomes they assert"
                 if dm is not None else "the runs diverge only in logs or calls, which the tests do not assert")
    return {"status": "passed" if passed else "failed", "provenance": "public_schedule", "obstruction_observed": obs,
            "test": items[0]["test"], "tests": [it["test"] for it in items],
            "outcomes": [r.get("outcomes") or [] for r in res], "expected": [it["expected"] for it in items],
            "emitted_test_passed": passed, "basis": basis}


def test_name(qid: str) -> str:
    from .gen.foundry import sanitize
    return sanitize(qid.split(":", 1)[0] + "_" + qfile(qid))


def emit_tests(root: Path, side: dict, env: dict) -> dict:
    """gen/M3/tests/: a Foundry test per BMC path (the binding's deployment, then the path's calls from their
    calldata) and the manifest."""
    from .fragments_corpus import binding_init
    from .gen import foundry as FG
    from .replay_fragments import load_binding
    binding = load_binding(root / side["binding"])
    m = BMC.Machine(load(root / side["documents"][0]), side["smt"]["byte_length_max"])
    files, manifest = {}, []
    hc = binding["harness"]["contract"]
    hfile = next(f for f in binding["harness"]["files"] if Path(f).name.startswith(hc.replace("Test", "")) or
                 hc in Path(root / f).read_text())
    deploy = {"kind": "harness", "import": f"./{Path(hfile).name}", "contract": hc,
              "init": binding_init(binding, root)}
    for qid, q, r in bmc_paths(root, side, env):
        name = test_name(qid)
        exp = expected_outcomes(m, q, r["path"])
        rel = TESTS / "foundry" / qid.split(":", 1)[0] / f"{name}.t.sol"
        files[rel] = FG.test_text(name, r["path"], exp, deploy, note=f"BMC path of {qid}")
        manifest.append({"path": str(rel), "kind": "foundry", "record": qid, "side": "solidity",
                         "steps": len(r["path"])})
    for it in cc_items(root, env):
        files[Path(it["test"])] = FG.test_text(it["name"], it["path"], ["ok"] * len(it["path"]), deploy,
                                               note=f"rule K3 for {it['record']}: a commit at version {it['version']} "
                                                    f"from R0 ({it['qid']})", stored=it["stored"])
        manifest.append({"path": it["test"], "kind": "foundry", "record": it["record"], "side": "solidity",
                         "steps": len(it["path"])})
    for it in direct_items(root):
        files[Path(it["test"])] = FG.test_text(it["name"], it["trace"], it["expected"], deploy,
                                               slots_at=it["slots_at"],
                                               note=f"rule K4 for {it['record']}"
                                                    f"{'' if it['part'] is None else ' (' + it['part'] + ')'}: the "
                                                    f"schedule its rule replayed, the model's outcomes")
        manifest.append({"path": it["test"], "kind": "foundry", "record": it["record"], "side": "solidity",
                         "steps": len(it["trace"])})
    import argparse
    from .replay import morph_path
    plans = go_plans(root)
    for rp, text in go_texts(root, plans, morph_path(argparse.Namespace(), root)).items():
        files[Path(rp)] = text
    for pl in plans:
        manifest.append({"path": pl["path"], "kind": "go", "record": pl["record"], "side": "go", "steps": 1})
    manifest.sort(key=lambda x: x["path"])
    files[TESTS / "manifest.json"] = dumps({"tests": manifest})
    return files


def _go_target(root: Path, doc: dict, fn: dict, checkout: Path | None = None):
    """(package dir, receiver type, method, {witness field: Go field path}) of a Go encoder of a codec document, or
    None when the extraction names no method of the witness's record type (a free function, or a method of another
    type taking the record otherwise)."""
    import re
    from .gen import gotest as GT
    if "carriers" in doc:                      # a linked component: the Go document names the method
        mo = GT.method_of(fn.get("source") or "")
        car = (doc.get("carriers") or {}).get(fn.get("from")) or {}
        if mo is None or car.get("type") != f"{mo[0]}.{mo[1]}" or car.get("kind") != "record":
            return None
        gdoc = load(root / fn["document"])
        pk = next((p for p in (gdoc.get("go") or {}).get("packages") or [] if p.get("path") == mo[0]), None)
        if pk is None:
            return None
        return pk["dir"], mo[1], mo[2], None
    src = fn.get("source") or []
    if len(src) != 1 or not re.fullmatch(r"\w+\.\w+", str(src[0].get("fn") or "")):
        return None
    t, mname = src[0]["fn"].split(".")
    ty = (doc.get("types") or {}).get(fn.get("from")) or {}
    fmap = {}
    for f in ty.get("fields") or []:
        g = str(f.get("go") or "").split(" ")[0]
        if re.fullmatch(r"[A-Z]\w*", g):
            fmap[f["name"]] = g
    return str(Path(src[0]["file"]).parent), t, mname, fmap


def go_plans(root: Path) -> list[dict]:
    """A Go test per Go library side of a REFUTED codec record whose Go encoder is a method of the witness's record:
    the record built from the witness, the method called, its bytes asserted equal to the model's Go side
    (the record's difference: lhs for the claim's first argument)."""
    from .gen import gotest as GT
    out = []
    for key, rec in sorted(records(root).items()):
        if rec.get("status") != "REFUTED" or witness_kind(rec) != "codec":
            continue
        law = law_of(root, key)
        claim = ((law.get("statement") or {}).get("claim") or {}).get("eq")
        if not (isinstance(claim, list) and len(claim) == 2) or not law.get("facts"):
            continue
        doc = load(root / law["facts"])
        for i, c in enumerate(claim):
            if not isinstance(c, dict) or "call" not in c or len(c.get("args") or []) != 1:
                continue
            fn = (doc.get("functions") or {}).get(c["call"]) or {}
            if not str(fn.get("lang") or "").startswith("go"):
                continue
            tgt = _go_target(root, doc, fn)
            var = (c["args"][0] or {}).get("var")
            w = (rec.get("witness") or {}).get(var)
            if tgt is None or not isinstance(w, dict):
                continue
            pdir, recv, meth, fmap = tgt
            fields = {(fmap or {}).get(k, k if fmap is None else None): v for k, v in w.items()}
            fields = {k: v for k, v in fields.items() if k}
            fields = {k: fields[k] for k in sorted(fields)}
            d, _, lid = key.rpartition("/")
            name = GT.sanitize(f"{d}_{lid}")
            out.append({"record": key, "law_id": lid, "name": name, "pkg_dir": pdir, "recv": recv, "method": meth,
                        "fields": fields, "want": rec["difference"]["lhs" if i == 0 else "rhs"],
                        "other": rec["difference"]["rhs" if i == 0 else "lhs"],
                        "path": str(TESTS / "go" / d.replace("/", "_") / f"{lid}_test.go")})
    return out


def go_texts(root: Path, plans: list[dict], checkout: Path) -> dict:
    from .gen import gotest as GT
    out = {}
    for p in plans:
        out[p["path"]] = GT.test_text(GT.package_name(checkout, p["pkg_dir"]), p["name"], p["recv"], p["method"],
                                      p["fields"], p["want"],
                                      note=f"{p['record']}: the Go side of the witness ({p['recv']}.{p['method']})")
    return out


def go_sides(root: Path) -> dict:
    """Run every emitted Go test in a scratch workspace of the pinned checkout: {record: {"go": side}}."""
    import argparse
    import shutil
    import tempfile
    from .gen import gotest as GT
    from .replay import morph_path
    checkout = morph_path(argparse.Namespace(), root)
    plans = go_plans(root)
    if not plans:
        return {}
    texts = go_texts(root, plans, checkout)
    go = shutil.which("go") or "/usr/local/go/bin/go"
    work = Path(tempfile.mkdtemp(prefix="holon-refute-go-"))
    out = {}
    try:
        for pdir in sorted({p["pkg_dir"] for p in plans}):
            ws = work / "ws"
            mod = GT.workspace(checkout, ws, pdir)
            mine = [p for p in plans if p["pkg_dir"] == pdir]
            for p in mine:
                (ws / pdir / f"holon_{p['name']}_test.go").write_text(texts[p["path"]])
            rel = str(Path(pdir).relative_to(mod))
            for p in mine:
                r = GT.run(go, ws, mod, rel, p["name"])
                passed = bool(r["passed"])
                out.setdefault(p["record"], {})["go"] = {
                    "status": "passed" if passed else "failed", "provenance": "library_api",
                    "obstruction_observed": passed and (r["out"] or "").lower() != str(p["other"]).lower(),
                    "test": p["path"], "outcomes": [r["out"]], "calls_agree": passed, "command": r["command"],
                    "observed": f"{p['recv']}.{p['method']}() = {r['out']}" if r["out"] else r["tail"][-300:]}
            shutil.rmtree(ws, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


def replay_stage(root: Path, side: dict, env: dict) -> dict:
    """Every BMC path replayed on the real contract through the binding's step harness: outcomes, the calls the
    real code made, and whether they agree with the path's model (calls_agree: the real run's outcomes are the model's,
    every step with the answers the real dependencies gave; see docs/iterations/I40.md)."""
    m = BMC.Machine(load(root / side["documents"][0]), side["smt"]["byte_length_max"])
    items = bmc_paths(root, side, env)
    ccs = cc_items(root, env)
    rep = {"toolchain": None, "morph_commit": (load(root / side["documents"][0]).get("target") or {}).get("commit"),
           "records": {}, "reaches": {}, "i21": {}, "targets": {}, "commit_class": {}, "toys": {}}
    for key, ss in sorted(go_sides(root).items()):
        rep["records"].setdefault(key, {"sides": {}})["sides"].update(ss)
    dits = direct_items(root)
    if not items and not ccs and not dits:
        return rep
    rr = RealRollup(root, side)
    try:
        res = rr.run([r["path"] for _qid, _q, r in items] + [it["path"] for it in ccs]) if (items or ccs) else []
        rep["toolchain"] = {k: Path(str(rr.tc[k])).name if rr.tc.get(k) else None for k in ("forge", "solc")}
        # the emitted tests, run in the same project (their outcome is the test's own assertion)
        from .refute3 import run_tests
        emitted = {}
        names = {str(it["test"]): it["name"] for it in ccs}
        for rp, text in emit_tests(root, side, env).items():
            if str(rp).endswith(".t.sol"):
                emitted[names.get(str(rp), Path(rp).name[:-len(".t.sol")])] = text
        tests_out = run_tests(rr.proj, rr.tc, emitted) if emitted else {}
    finally:
        rr.close()
    groups: dict = {}
    for it in dits:
        groups.setdefault(it["record"], []).append(it)
    for key, its in sorted(groups.items()):
        rep["records"].setdefault(key, {"sides": {}})["sides"]["solidity"] = direct_side(its, tests_out)
    for it, x in zip(ccs, res[len(items):]):
        t = tests_out.get(it["name"]) or {}
        mism = answer_mismatch(root, side, env, it["path"], x["calls"])
        agree = x["outcomes"] == ["ok"] * len(it["path"])
        passed = bool(t.get("passed")) and agree and mism is None
        # an env_mismatch discards the commit path (the contract's E-BMC): no side, never a failed one
        sstat = "not_run" if mism is not None else "passed" if passed else "failed"
        rep["commit_class"][f"v{it['version']}"] = {"status": "passed" if agree else "failed",
                                                    "outcomes": x["outcomes"], "expected": ["ok"] * len(it["path"]),
                                                    "calls": x["calls"], "calls_agree": mism is None,
                                                    "env_mismatch": mism}
        rep["records"].setdefault(it["record"], {"sides": {}})["sides"]["solidity"] = {
            "status": sstat, "provenance": "public_schedule",
            "obstruction_observed": passed and bool(it["stored"]), "test": it["test"], "outcomes": x["outcomes"],
            "calls_agree": mism is None, "emitted_test_passed": bool(t.get("passed")),
            "observed": (f"a commit at version {it['version']} from R0: {' / '.join(x['outcomes'])}; the model's header "
                         f"with the Solidity side's bytes at cells {it['cells'][0]}..{it['cells'][-1]} "
                         f"({len(it['stored'])} candidate(s)) is "
                         f"{'stored' if t.get('passed') else 'not stored (or the test failed)'} on the real contract")}
    for (qid, q, r), x in zip(items, res[:len(items)]):
        exp = expected_outcomes(m, q, r["path"])
        agree = outcomes_agree(x["outcomes"], exp)
        fn = call_check(m, q)
        if agree and fn is not None:
            agree = call_failed(root, side, (x["calls"] or [[]])[-1], fn)
        mism = answer_mismatch(root, side, env, r["path"], x["calls"])
        t = tests_out.get(test_name(qid)) or {}
        entry = {"status": "passed" if agree else "failed", "outcomes": x["outcomes"], "expected": exp,
                 "calls": x["calls"], "calls_agree": mism is None, "env_mismatch": mism,
                 "emitted_test_passed": bool(t.get("passed")),
                 "test": str(TESTS / "foundry" / qid.split(":", 1)[0] / f"{test_name(qid)}.t.sol")}
        kind, _, ident = qid.partition(":")
        {"reach": rep["reaches"], "i21": rep["i21"], "target": rep["targets"], "width": rep["targets"]}[kind][ident] = entry
    return rep


# ------------------------------------------------------------------------------------------------ Q2 and Q1 (codec)
def codec_model_import(where: Path, root: Path, law: dict) -> str:
    import os
    return os.path.relpath((root / "gen" / "M3" / "model" / f"{Path(law['facts']).stem}.bend").resolve(),
                           where.resolve()).replace(os.sep, "/")


def check_counter(law: dict, doc: dict, wit: dict, where: Path, root: Path, laws_file: Path | None = None) -> dict:
    """A codec candidate's counter-law (holon.gen.linked's generator at the witness), checked by Bend and BendTT:
    {"counter_law", "checker", "verdict", "accepted", "reason"}."""
    import os
    from .gen import linked as L
    from .sorts.run3 import check_file
    where.mkdir(parents=True, exist_ok=True)
    try:
        if doc.get("facts_version") == "holon-facts/0.1":
            from . import ir
            from .gen import laws as LG, proofs as PG
            mi = os.path.relpath((root / law["_model"]).resolve(), where.resolve()).replace(os.sep, "/")
            em2 = LG.emit(law, doc, mi, counter=True, header_note=ir.statement_hash(law))
            text = PG.counter(em2, doc, mi, wit)
        else:
            mi = codec_model_import(where, root, law)
            reg = load(root / "laws" / "M3" / "REGISTRY.json")
            note = (reg.get("statements") or {}).get(law["law_id"], "")
            em2 = L.emit(law, doc, mi, counter=True, note=note)
            text = L.counter(em2, doc, mi, wit)
    except Exception as x:  # noqa: BLE001  (an inexpressible candidate is discarded with the reason)
        return {"counter_law": None, "checker": {"exit_code": None, "marker": f"inexpressible: {x}"},
                "verdict": {"kernel": "BendTT", "marker": "not_run"}, "accepted": False, "reason": f"inexpressible: {x}"}
    if laws_file is None:
        (where / "LAWS.bend").write_text(em2.text, encoding="utf-8")
    else:
        rel = os.path.relpath(laws_file.resolve(), where.resolve()).replace(os.sep, "/")
        text = text.replace("import ./LAWS.bend as Laws", f"import {rel} as Laws")
    p = where / "PROOF.bend"
    p.write_text(text, encoding="utf-8")
    checker, verdict = check_file(p)
    checker = {k: v for k, v in checker.items() if k != "seconds"}
    ok = checker.get("marker") == "ALL PROOFS CHECK" and verdict == "checked"
    return {"counter_law": str(p.relative_to(root)), "checker": checker,
            "verdict": {"kernel": "BendTT", "marker": "ALL PROOFS CHECK" if verdict == "checked" else verdict},
            "accepted": ok, "reason": None if ok else f"bend2 {checker.get('marker')}, BendTT {verdict}"}


def engine(doc: dict):
    """The solver encoding of a codec document: a linked component (holon.smt.codec) or a holon-facts/0.1 document
    (holon.smt.facts01); None for any other."""
    if doc.get("linked_version") is not None:
        from .smt import codec
        return codec
    if doc.get("facts_version") == "holon-facts/0.1":
        from .smt import facts01
        return facts01
    return None


def codec_stage(root: Path, side: dict, log=print) -> tuple[dict, dict]:
    """Q2 over every codec law of a linked component (the M3 PAR laws), and Q1's codec and domain classes over the
    same models: (codec.json, {class id: refind row})."""
    from .smt import codec as C
    rl = int(side["solver"]["rlimit_per_query"])
    ml = int(side["smt"]["byte_length_max"])
    laws, texts = {}, {}
    for x in side["codec_laws"]:
        d, _, lid = x["record"].rpartition("/")
        law = law_of(root, x["record"])
        doc = load(root / law["facts"]) if law.get("facts") else {}
        E_ = engine(doc)
        if E_ is None:
            laws[x["record"]] = {"status": x["status"], "solver": "unknown", "query": None, "candidate": None,
                                 "reason": f"not run: no encoder for the document {law.get('facts')}"}
            continue
        law = dict(law, _model=records(root)[x["record"]]["artifacts"]["model"])
        q, dec = E_.law_query(doc, law, rl, ml)
        qp = GENR / "smt" / "codec" / f"{lid}.smt2"
        text = q.text()
        texts[qp] = text
        sess = SR.Session(side["solver"])
        try:
            res = sess.check(text)
            cand = None
            if res == "sat":
                wit = E_.decode(sess, dec)
                cand = {"witness": wit, **check_counter(law, doc, wit, root / GENR / "codec" / d.replace("/", "_") /
                                                        lid, root)}
            elif res == "unknown":
                cand = None
        finally:
            sess.close()
        laws[x["record"]] = {"status": x["status"], "solver": res, "query": str(qp), "candidate": cand}
        log(f"codec {lid}: {res}{'' if not cand else ' accepted' if cand['accepted'] else ' discarded'}")
    refind = {}
    for c in side["classes"]:
        if c["kind"] not in ("codec", "domain"):
            continue
        law = law_of(root, c["record"])
        doc = load(root / law["facts"]) if law.get("facts") else {}
        E_ = engine(doc)
        if E_ is None:
            continue
        rec = records(root)[c["record"]]
        law = dict(law, _model=rec["artifacts"]["model"])
        q, dec = E_.law_query(doc, law, rl, ml, template=c["signature"])
        qp = GENR / "smt" / "refind" / f"{c['id']}.smt2"
        text = q.text()
        texts[qp] = text
        sess = SR.Session(side["solver"])
        cands = []
        try:
            res = sess.check(text)
            if res == "sat":
                wit = E_.decode(sess, dec)
                lhs, rhs = E_.side_values(sess, dec)
                if c["kind"] == "codec":
                    ba, bb = bytes.fromhex(lhs[2:]), bytes.fromhex(rhs[2:])
                    sig = {"diff_positions": [i for i in range(max(len(ba), len(bb)))
                                              if i >= len(ba) or i >= len(bb) or ba[i] != bb[i]],
                           "lengths": [len(ba), len(bb)]}
                else:
                    bb = bytes.fromhex(next(v for v in wit.values() if isinstance(v, str))[2:])
                    sig = {"version_byte": bb[0] if bb else None, "length": len(bb), "lhs": lhs, "rhs": rhs}
                laws_file = root / rec["artifacts"]["laws"]
                chk = check_counter(law, doc, wit, root / GENR / "refind" / c["id"], root, laws_file=laws_file)
                cands.append({"witness": wit, "signature": sig, **chk})
        finally:
            sess.close()
        refind[c["id"]] = {"record": c["record"], "law_id": c["law_id"], "entry": c["entry"], "kind": c["kind"],
                           "query": str(qp), "result": res, "bound": {"byte_length_max": ml},
                           "candidates": cands, "refound": bool(cands and cands[0]["accepted"])}
        log(f"refind {c['id']} {c['record']}: {res}, refound {refind[c['id']]['refound']}")
    return {"document": "codec", "laws": laws}, refind, texts
