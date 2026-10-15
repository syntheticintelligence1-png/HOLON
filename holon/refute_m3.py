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
    return qs


def qfile(qid: str) -> str:
    import hashlib
    return hashlib.sha256(qid.encode()).hexdigest()[:16]


def run_question(root: Path, side: dict, env: dict, q: dict, log=print) -> dict:
    p, _info = problem(root, side, env)
    name = qfile(q["id"])
    r = BMC.search(p, q["target"], side["solver"], root / GENR / "smt" / "bmc", name, log=log)
    r["queries"] = [str(Path(x).resolve().relative_to(root.resolve())) for x in r["queries"]]
    r["id"] = q["id"]
    r["target"] = q["target"]
    return r


def bmc_stage(root: Path, side: dict, env: dict, only_ids: list | None = None, jobs: int = 1, log=print) -> None:
    """Run (or resume) every BMC question: each result cached as gen/M3/refute/bmc/<question>.json."""
    from concurrent.futures import ThreadPoolExecutor
    out = root / GENR / "bmc"
    out.mkdir(parents=True, exist_ok=True)
    qs = [q for q in questions(root, side, env) if not only_ids or q["id"] in only_ids]
    if only_ids:
        qs.sort(key=lambda q: only_ids.index(q["id"]))
    todo = [q for q in qs if not (out / f"{qfile(q['id'])}.json").is_file()]

    def one(q):
        try:
            r = run_question(root, side, env, q, log=log)
        except Exception as x:  # noqa: BLE001  (an encoder failure is an unknown with its reason, never a verdict)
            r = {"id": q["id"], "target": q["target"], "verdict": "unknown", "length": None, "path": None,
                 "largest_k": 0, "queries": [], "approx": [], "reason": f"encoder error: {type(x).__name__}: {x}"}
        (out / f"{qfile(q['id'])}.json").write_text(dumps(r), encoding="utf-8")
        log(f"{q['id']}: {r['verdict']} (largest_k {r['largest_k']})")
        return r
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        list(ex.map(one, todo))


def cached(root: Path, qid: str) -> dict | None:
    p = root / GENR / "bmc" / f"{qfile(qid)}.json"
    return load(p) if p.is_file() else None


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
    out, filt = {}, {}
    for key, rec in sorted(recs.items()):
        if rec.get("status") != "REFUTED":
            continue
        law = law_of(root, key)
        ss = dict(sides.get(key) or {})
        if not ss and key.startswith("M2/extracted_m1/"):
            ss = dict(sides.get("M1/" + key.rpartition("/")[2]) or {})
        kind = kind_of(rec, law, ss)
        gen = ((rep.get("records") or {}).get(key) or {}).get("sides") or {}
        final_sides = {**ss, **gen}
        conc = {"kind": kind, "result": None, "length": None, "bound": None, "target": None,
                "tests": sorted({g["test"] for g in gen.values() if g.get("test")}),
                "sides": {k: {"status": v.get("status"), "provenance": v.get("provenance"),
                              "obstruction_observed": v.get("obstruction_observed")} for k, v in sorted(final_sides.items())},
                "reason": None}
        path = None
        if kind == "go_only":
            conc["reason"] = "node-level public path needs I39"
        elif kind == "commit_class":
            conc.update(result="path", length=1, reason="a commit of the witness's version from R0 (the M0 commit-path "
                                                          "rule): the replay's public_schedule side, when there is one")
        elif kind == "direct":
            conc.update(result="path", length=trace_length(rec),
                        reason="the witness is a schedule of public calls (its replay is the record's side)")
        else:
            tid = target_of(env, key, rec, law)
            conc.update(target=tid, bound={"H": H, "rlimit": rl})
            r = cached(root, f"target:{tid}") if tid else None
            if r is None:
                conc.update(result="unknown", reason="BMC on the target was not run within the I40 build's time box")
            else:
                conc.update(result=r["verdict"], length=r["length"], reason=r["reason"])
                path = r["path"] if r["verdict"] == "path" else None
        fb = FL.final_bin(final_sides, conc)
        out[key] = dict(conc, path=path)
        before = (side["records"].get(key) or {}).get("filter_bin") if key in side["records"] else None
        filt[key] = {"before": before, "after": fb, "kind": kind, "result": conc["result"]}
        if write:
            new = dict(rec, filter_bin=fb, concretization=conc)
            if new != rec:
                d, _, lid = key.rpartition("/")
                write_record(root / "results" / d / f"{lid}.json", new)
    return {"concretization": {"document": "concretization", "H": H, "records": out},
            "filter": {"document": "filter", "rule": FL.FINAL_RULE, "records": filt}}


def reach_docs(root: Path, side: dict) -> dict:
    H = int(side["bmc"]["H"])
    reaches = {}
    for rid in side["unfalsified_reaches"]:
        r = cached(root, f"reach:{rid}")
        if r is None:
            reaches[rid] = {"verdict": "unknown", "length": None, "path": None, "largest_k": 0,
                            "reason": "not run: the I40 build's time box ended before this reach's search"}
        else:
            reaches[rid] = {"verdict": r["verdict"], "length": r["length"], "path": r["path"],
                            "largest_k": r["largest_k"], "reason": r["reason"]}
    return {"document": "reaches", "source": "results/M2/refinement/extracted.json", "H": H, "reaches": reaches}


def i21_doc(root: Path, side: dict) -> dict:
    f = {}
    for fid in sorted(k for k in side["i21"] if k not in ("doc", "out_of_scope")):
        r = cached(root, f"i21:{fid}")
        evm = ({"verdict": "unknown", "length": None, "path": None, "largest_k": 0,
                "reason": "not run: the I40 build's time box"} if r is None else
               {"verdict": r["verdict"], "length": r["length"], "path": r["path"], "largest_k": r["largest_k"],
                "reason": r["reason"]})
        x = {"evm": evm}
        if side["i21"][fid].get("go"):
            x["go"] = {"verdict": "out_of_scope", "reason": side["i21"][fid]["go"]}
        f[fid] = x
    return {"document": "i21", "findings": f, "out_of_scope": side["i21"]["out_of_scope"]}


def unknowns_doc(root: Path, side: dict) -> dict:
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
                             "reason": "not run: the I40 build's time box", "length": None, "largest_k": 0})
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
            atts.append({"engine": "smt", "bound": bound, "budget": {"rlimit": rl}, "result": "not_run",
                         "candidates": 0, "accepted": 0, "discarded": [], "reason": NOT_BUILT})
            atts.append({"engine": "fuzz", "bound": {"candidates": int(fz["candidates_per_law"]), "seed": int(fz["seed"])},
                         "budget": {"candidates": int(fz["candidates_per_law"])}, "result": "not_run", "candidates": 0,
                         "accepted": 0, "discarded": [], "reason": NOT_BUILT})
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
    if "bmc" in stages and not a.check:
        import os
        ids = [x for x in (os.environ.get("HOLON_REFUTE_QUESTIONS") or "").split("|") if x]
        if os.environ.get("HOLON_REFUTE_GUARD_S"):
            BMC.GUARD_S = float(os.environ["HOLON_REFUTE_GUARD_S"])
        if os.environ.get("HOLON_REFUTE_MEMORY_MB"):
            BMC.MEMORY_MB = int(os.environ["HOLON_REFUTE_MEMORY_MB"])
        bmc_stage(root, side, env, ids or None, jobs=int(os.environ.get("HOLON_REFUTE_JOBS") or 1))
    if "bmc" in stages:
        files["reaches.json"] = reach_docs(root, side)
        files["i21.json"] = i21_doc(root, side)
        files["unknowns.json"] = unknowns_doc(root, side)
    if "smt" in stages:
        files["refind.json"] = refind_doc(side)
        files["codec.json"] = codec_doc(side)
    if "fuzz" in stages:
        files["fuzz.json"] = fuzz_doc(side)
    if "emit" in stages:
        for rp, text in emit_tests(root, side, env).items():
            texts[rp] = text
        if not a.check:
            import shutil
            shutil.rmtree(root / TESTS, ignore_errors=True)
    if "replay" in stages and not a.check:
        rep = replay_stage(root, side, env)
        (root / REPLAY).parent.mkdir(parents=True, exist_ok=True)
        (root / REPLAY).write_text(dumps(rep), encoding="utf-8")
    if "filter" in stages:
        docs = concretize(root, side, env, write=not a.check)
        files["concretization.json"] = docs["concretization"]
        files["filter.json"] = docs["filter"]
    diff = []
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


def expected_outcomes(m: BMC.Machine, q: dict, path: list[dict]) -> list[str]:
    """What the BMC model claims of a path: every step ok but the last; a check target's last step reverts with that
    check's revert key (its reason, or its Panic code)."""
    t = q["target"]
    if t["kind"] != "check":
        return ["ok"] * len(path)
    prog = m.progs[t["action"]]
    c = next(x for x in prog.checks() if x.id == t["check"])
    if c.kind == "panic" and c.code is not None:
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
        if r is not None and r["verdict"] == "path" and r.get("path"):
            out.append((q["id"], q, r))
    return out


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
    manifest.sort(key=lambda x: x["path"])
    files[TESTS / "manifest.json"] = dumps({"tests": manifest})
    return files


def replay_stage(root: Path, side: dict, env: dict) -> dict:
    """Every BMC path replayed on the real contract through the binding's step harness: outcomes, the calls the
    real code made, and whether they agree with the path's model (calls_agree: the real run's outcomes are the model's,
    every step with the answers the real dependencies gave; see docs/iterations/I40.md)."""
    m = BMC.Machine(load(root / side["documents"][0]), side["smt"]["byte_length_max"])
    items = bmc_paths(root, side, env)
    rep = {"toolchain": None, "morph_commit": (load(root / side["documents"][0]).get("target") or {}).get("commit"),
           "records": {}, "reaches": {}, "i21": {}, "targets": {}, "toys": {}}
    if not items:
        return rep
    rr = RealRollup(root, side)
    try:
        res = rr.run([r["path"] for _qid, _q, r in items])
        rep["toolchain"] = {"forge": rr.tc.get("forge"), "solc": rr.tc.get("solc")}
    finally:
        rr.close()
    for (qid, q, r), x in zip(items, res):
        exp = expected_outcomes(m, q, r["path"])
        agree = x["outcomes"] == exp
        entry = {"status": "passed" if agree else "failed", "outcomes": x["outcomes"], "expected": exp,
                 "calls": x["calls"], "calls_agree": agree,
                 "test": str(TESTS / "foundry" / qid.split(":", 1)[0] / f"{test_name(qid)}.t.sol")}
        kind, _, ident = qid.partition(":")
        {"reach": rep["reaches"], "i21": rep["i21"], "target": rep["targets"], "width": rep["targets"]}[kind][ident] = entry
    return rep
