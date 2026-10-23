"""`python -m holon profile --milestone T32 [--root DIR]`: discharge profiles (BUILD_PLAN I32; the contract is the
docstring of tests_m3/test_disch_profile.py).

Reads the sidecar spec/M3/lib/disch_profile.json (its milestone, facts, obligation, candidates, schedule, bounds and
abstraction horizon; never edited here), then for its obligation:

1. builds the facts' machine (holon.mpipeline.CompiledMachine, as M1 builds it) and writes its model text to
   gen/<M>/model/<model>.bend;
2. compiles lhs (holon.gen.profile.lhs_module) to JS for the persistent search;
3. asks holon/js/profile.mjs for the outcomes, frontier, persistent frontier, alphabets, each frontier point's game
   (priority list and table, or the adversary's answers), the robust frontier, the dominance check and the time
   abstraction (holon.analysis.abstraction.engine_request);
4. writes the profile document gen/<M>/profile/<ob>.json and module gen/<M>/profile/<ob>.bend
   (holon.rules.disch_profile, holon.gen.profile);
5. writes every law (laws/<M>/<id>.json, REGISTRY.json) and its Bend files gen/<M>/<id>/LAWS.bend and PROOF.bend: the
   law with its witness, or, for a frontier point the adversary wins, the counter-law cl_<name> with the answers;
6. runs bend on every PROOF.bend: ALL PROOFS CHECK makes the law PROVED (REFUTED for a counter-law); anything else
   leaves it UNKNOWN with what was tried; writes results/<M>/<id>.json and results/<M>/summary.json;
7. writes gen/M3/disch/classification.json (classification(): I31's DISCH basis classified).

Two runs write the same bytes, records equal up to keys named seconds.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from . import bend, records
from . import facts as F
from .analysis import abstraction as A
from .gen import profile as G
from .rules import disch_profile as R

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = Path("spec") / "M3" / "lib" / "disch_profile.json"
ENGINE = Path(__file__).resolve().parent / "js" / "profile.mjs"
GEN_PROFILE = ["holon/profile.py", "holon/rules/disch_profile.py", "holon/gen/profile.py",
               "holon/analysis/abstraction.py", "holon/js/profile.mjs"]


def dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def generator_files(root: Path) -> list[str]:
    """GEN_PROFILE and every holon module they import, transitively, and the facts' search hints."""
    seen, todo = set(), list(GEN_PROFILE)
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen.add(rel)
        if rel.endswith(".py"):
            todo.extend(sorted(records._holon_imports(rel, root) - seen))
    return sorted(seen)


def generator_sha256(root: Path, extra: list[str]) -> str:
    import hashlib
    h = hashlib.sha256()
    for rel in sorted(set(generator_files(root)) | set(extra)):
        h.update(rel.encode() + b"\0" + (root / rel).read_bytes() + b"\0")
    return h.hexdigest()


def classification(root: Path) -> dict:
    """The M3 classification of I31's DISCH basis (spec/M3/lib/disch_profile.json classes.doc): for every basis
    element of gen/M3/disch/conjuncts.json and every class it names, from results/M3's L_disch_* records:
    blk PROVED and some ext law of another class Y PROVED -> external-dependent by those Y; blk PROVED and none ->
    non-dischargeable; blk REFUTED -> dischargeable (M3 has no cost model, so no profile); otherwise undecided."""
    doc = json.loads((root / "gen" / "M3" / "disch" / "conjuncts.json").read_text())
    status = {p.stem: json.loads(p.read_text()).get("status")
              for p in sorted((root / "results" / "M3").glob("L_disch_*.json"))}
    entries = []
    for _model, md in sorted(doc["models"].items()):
        for b in md["basis"]:
            tag = b["tag"]
            pre = f"L_disch_ext_{tag}_"
            for cls in sorted(b["classes"]):
                blk = f"L_disch_blk_{tag}_{cls}"
                by = sorted(k[len(pre):] for k, v in status.items()
                            if k.startswith(pre) and v == "PROVED" and k != pre + cls)
                st = status.get(blk)
                if st == "PROVED":
                    c = "external-dependent" if by else "non-dischargeable"
                elif st == "REFUTED":
                    c, by = "dischargeable", []
                else:
                    c, by = "undecided", []
                entries.append({"tag": tag, "class": cls, "disch_class": c, "by": by, "blk": blk, "blk_status": st})
    entries.sort(key=lambda e: (e["tag"], e["class"]))
    return {"classification_version": "holon-disch-classes/0.1", "milestone": "M3",
            "doc": ("I32: the class of every I31 DISCH basis element and principal class, from I31's decided laws "
                    "(spec/M3/lib/disch_profile.json classes.doc). M3 has no cost model, so a dischargeable entry "
                    "carries no profile; the delay guard's M3 profile follows I36's extraction of the message queue."),
            "entries": entries}


def checked_by(doc: dict, status: dict[str, str]) -> dict:
    """What Bend checked of the profile document's claims, and what only the engine found. A frontier point is
    kernel-checked achievable when its §8.4 law is PROVED (its strategy wins every schedule, the empty one too); the
    frontier's minimality is the dominance law's; a persistent point is kernel-checked when its law is PROVED, but no
    law shows that the persistent frontier has no other point; the robust frontier beyond the PROVED point laws is
    the engine's."""
    ob = doc["obligation"]
    k = lambda p: f"{p[0]}_{p[1]}"  # noqa: E731
    pts = [(x["cost"], x["delay"]) for x in doc["frontier"]]
    dom = status.get(f"L_dp_{ob}_dominance")
    out = {"frontier": {}, "persistent": {}, "robust_frontier": {}}
    for c, d in pts:
        s = status.get(f"L_dp_{ob}_point_{c}_{d}")
        out["frontier"][k((c, d))] = ("kernel: its §8.4 law is PROVED" if s == "PROVED"
                                      else f"engine only (its §8.4 law is {s})")
    out["frontier_minimality"] = "kernel: the dominance law is PROVED" if dom == "PROVED" else f"not checked ({dom})"
    for x in doc["persistent"]["frontier"]:
        s = status.get(f"L_dp_{ob}_persistent_{x['cost']}_{x['delay']}")
        out["persistent"][k((x["cost"], x["delay"]))] = "kernel: its law is PROVED" if s == "PROVED" else f"not checked ({s})"
    out["persistent_minimality"] = "engine only"
    for x in doc["robust_frontier"]:
        s = status.get(f"L_dp_{ob}_point_{x['cost']}_{x['delay']}")
        out["robust_frontier"][k((x["cost"], x["delay"]))] = ("kernel: its §8.4 law is PROVED" if s == "PROVED"
                                                              else "engine only (no law)")
    out["class"] = "from the frontier as checked above"
    return out


def run(milestone: str, root: Path = ROOT, log=print) -> int:
    from .gen.machine import Machine
    from .mpipeline import CompiledMachine, model_name

    root = Path(root)
    side = json.loads((root / SIDECAR).read_text())
    if milestone != side["milestone"]:
        log(f"holon profile: the sidecar {SIDECAR} is for {side['milestone']}, not {milestone}")
        return 2
    fp = root / side["facts"]
    facts = F.load(fp)
    fsha = F.sha256_file(fp)
    machine = Machine(facts, fp)
    ob = A.obligation(side, machine)
    cfg = bend.config(root)
    gen = root / "gen" / milestone
    out_laws = root / "laws" / milestone
    out_res = root / "results" / milestone
    for d in (gen, out_laws, out_res):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    # 1. the machine model, as M1 builds it
    cm = CompiledMachine.build(fp, cfg)
    mname = model_name(fp)
    (gen / "model").mkdir()
    model_text = Path(cm.source).read_text()
    (gen / "model" / f"{mname}.bend").write_text(model_text)
    model_defs = set(records.model_defs(model_text))
    if "ob_lhs" in model_defs:
        log("holon profile: the model already defines ob_lhs")
        return 1
    model_import = f"../model/{mname}.bend"

    # 2. the search's module: the model with lhs appended in its namespace, compiled to JS in the build dir
    kdir = bend.build_dir(root) / "profile" / fsha[:16]
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / f"{mname}.bend").write_text(model_text.rstrip("\n") + "\n\n" + G.lhs_inline(machine, ob.target, ob.reason, ob.src))
    r = bend.run([f"{mname}.bend", "-o", f"{mname}.mjs"], cwd=kdir, cfg=cfg)
    if r.code != 0:
        log(f"holon profile: the model with lhs does not compile: {r.out[-2000:]}")
        return 1
    search_module = kdir / f"{mname}.mjs"

    # 3. the engine
    bounds = {"moves": int(side["search"]["strategy_moves"]), "dominance_moves": int(side["dominance"]["strategy_moves"]),
              "persistent_moves": int(side["persistent"]["strategy_moves"]), "horizon": int(side["abstraction"]["horizon_s"])}
    hints = root / side["candidates"]["source"]
    req = A.engine_request(ob, search_module, hints, facts, bounds, {"module": str(search_module), "fn": "ob_lhs"})
    p = subprocess.run(["node", str(ENGINE)], input=json.dumps(req), capture_output=True, text=True, timeout=7200)
    if p.returncode != 0:
        log(f"holon profile: the engine failed: {p.stderr[-3000:]}")
        return 1
    eng = json.loads(p.stdout)
    if not eng.get("sstar_ok"):
        log("holon profile: the obligation's prefix fails on the model")
        return 1

    # 4. the document and module
    pairs = A.pairs(eng["deadlines"], bounds["horizon"])
    doc = R.document(ob, side, fsha, eng, bounds, pairs)
    (gen / "profile").mkdir()
    (gen / "profile" / f"{ob.id}.json").write_text(dump(doc))
    (gen / "profile" / f"{ob.id}.bend").write_text(G.profile_module(machine, model_defs, model_import, doc))
    profile_import = f"../profile/{ob.id}.bend"

    # 5. the laws and their Bend files; 6. the checks, then the records (each record says what Bend checked)
    gsha = generator_sha256(root, [side["candidates"]["source"]])
    key = lambda m: json.dumps(m, sort_keys=True)  # noqa: E731
    axd_ix = {key(m): i for i, m in enumerate(doc["dominance"]["alphabet"])}
    decided, registry = [], []
    for law in R.laws(doc):
        lid = law["law_id"]
        st = law["statement"]
        sh = R.statement_hash(st)
        (out_laws / f"{lid}.json").write_text(dump(law))
        registry.append({"law_id": lid, "statement_hash": sh})
        name = lid.lower()
        header = f"# law_id: {lid}   statement_hash: {sh}"
        counter, witness_lit, binders, claim, rec_witness, proof_witness, why = False, None, [], "", None, None, None
        if law["subform"] == "profile_point":
            pt = next(x for x in doc["points"] if x["cost"] == st["cost"] and x["delay"] == st["delay"])
            ax = f"P.ax_{pt['cost']}_{pt['delay']}()"
            if pt.get("policy") is not None:
                binders = ["exs ix: List<&2, Nat>"]
                claim = f"{{P.robust(ix, {ax}, {G.nat(pt['cost'])}, {G.nat(pt['delay'])}) == True{{}} : Bool}}"
                witness_lit = G.nats(pt["policy"])
                rec_witness = doc["tables"][f"{pt['cost']}_{pt['delay']}"]
                proof_witness = {"policy": pt["policy"], "alphabet": f"ax_{pt['cost']}_{pt['delay']}"}
            elif pt.get("adversary"):
                counter = True
                binders = ["exs e: List<&2, P.Ans>"]
                claim = f"{{P.beaten(e, {ax}, {G.nat(pt['cost'])}, {G.nat(pt['delay'])}) == True{{}} : Bool}}"
                witness_lit = "[" + ", ".join(f"P.Ans{{{G.nats(a['xhist'])}, {G.nats(a['events'])}}}"
                                              for a in pt["adversary"]) + "]" if pt["adversary"] else "Nil{}"
                rec_witness = {"adversary": pt["adversary"]}
                proof_witness = {"adversary": pt["adversary"], "alphabet": f"ax_{pt['cost']}_{pt['delay']}"}
            else:
                why = pt.get("why") or "the engine found neither a priority list nor the adversary's answers"
        elif law["subform"] == "profile_dominance":
            claim = "{P.dominance() == True{} : Bool}"
        elif law["subform"] == "profile_persistent":
            f = next(x for x in doc["persistent"]["frontier"] if x["cost"] == st["cost"] and x["delay"] == st["delay"])
            ix = [axd_ix.get(key(m)) for m in f["strategy"]]
            if None in ix:
                why = "a move of the persistent strategy lies outside X's alphabet"
            else:
                binders = ["exs ix: List<&2, Nat>"]
                claim = (f"{{P.persistent_ok(ix, P.axd(), {G.nat(st['moves'])}, {G.nat(f['cost'])}, "
                         f"{G.nat(f['delay'])}) == True{{}} : Bool}}")
                witness_lit = G.nats(ix)
                rec_witness = f["strategy"]
                proof_witness = {"strategy": ix, "alphabet": "axd"}
        elif law["subform"] == "profile_abstraction":
            claim = "{P.abstraction() == True{} : Bool}"
        lname = ("cl_" if counter else "") + name
        d = gen / lid
        d.mkdir()
        if claim:
            (d / "LAWS.bend").write_text(G.law_text(header, model_import, profile_import, lname, binders, claim))
            (d / "PROOF.bend").write_text(G.proof_text(model_import, profile_import, lname, witness_lit))
            chk = bend.run(["PROOF.bend"], cwd=d, cfg=cfg, timeout=7200)
            ok = chk.ok
            checker = {"exit_code": chk.code, "marker": chk.marker, "seconds": round(chk.seconds, 3)}
        else:
            ok, checker = False, {"exit_code": None, "marker": "not_run", "seconds": 0.0}
        status = ("REFUTED" if counter else "PROVED") if ok else "UNKNOWN"
        decided.append((law, sh, lname, status, ok, checker, counter, rec_witness, proof_witness, why))
        log(f"  {lid}: {status} ({checker['marker']})")
    st_of = {law["law_id"]: status for law, _sh, _n, status, *_ in decided}
    checked = checked_by(doc, st_of)
    summary = {"PROVED": 0, "REFUTED": 0, "UNKNOWN": 0}
    for law, sh, lname, status, ok, checker, counter, rec_witness, proof_witness, why in decided:
        lid = law["law_id"]
        st = law["statement"]
        summary[status] += 1
        pt_info = None
        if law["subform"] == "profile_point":
            pt = next(x for x in doc["points"] if x["cost"] == st["cost"] and x["delay"] == st["delay"])
            pt_info = {"robust": pt["robust"], "game_alphabet": len(pt["alphabet"]),
                       "policy": pt.get("policy"), "why": pt.get("why")}
        rec = {
            "law_id": lid, "milestone": milestone, "rule": "DISCH", "subform": law["subform"],
            "statement_hash": sh, "facts_sha256": fsha, "status": status, "checker": checker,
            "kernels": [{"kernel": "bend2", "result": "checked" if ok else "failed"},
                        {"kernel": "bendtt", "result": "not_run"}],
            "artifacts": {"law_name": lname, "laws": f"gen/{milestone}/{lid}/LAWS.bend",
                          "proof": f"gen/{milestone}/{lid}/PROOF.bend", "model": f"gen/{milestone}/model/{mname}.bend",
                          "profile": f"gen/{milestone}/profile/{ob.id}.bend"},
            "attempts": [{"kind": "profile-search", "engine": "holon/js/profile.mjs", "outcomes": len(doc["outcomes"]),
                          "game": pt_info},
                         {"kind": "counter-law" if counter else "proof", "generator": "evaluate", **checker}]
                        + ([{"kind": "not attempted", "why": why}] if why else []),
            "witness": rec_witness,
            "proof_witness": proof_witness,
            "scope": {"kind": "bounded", "H": ob.H, "moves": st.get("moves", bounds["moves"]), "exact": A.EXACT},
            "disch_class": doc["class"],
            "disch_profile": {"frontier": [[x["cost"], x["delay"]] for x in doc["frontier"]],
                              "persistent": [[x["cost"], x["delay"]] for x in doc["persistent"]["frontier"]],
                              "persistent_class": doc["persistent"]["class"],
                              "robust_frontier": [[x["cost"], x["delay"]] for x in doc["robust_frontier"]],
                              "H": ob.H, "exact": A.EXACT, "checked": checked,
                              "cost_model": facts.get("disch", {}).get("cost")},
            "generator_sha256": gsha,
        }
        (out_res / f"{lid}.json").write_text(dump(rec))
    (out_laws / "REGISTRY.json").write_text(dump({"milestone": milestone, "laws": sorted(registry, key=lambda e: e["law_id"])}))
    (out_res / "summary.json").write_text(dump({"milestone": milestone, "statuses": summary, "laws": len(registry),
                                                "class": doc["class"], "persistent_class": doc["persistent"]["class"],
                                                "checked": checked}))

    # 7. the M3 classification
    (root / "gen" / "M3" / "disch").mkdir(parents=True, exist_ok=True)
    (root / "gen" / "M3" / "disch" / "classification.json").write_text(dump(classification(root)))
    log(f"holon profile --milestone {milestone}: {summary}")
    return 0


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="holon profile", description="discharge profiles (DISCH II, I32)")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    return run(a.milestone, Path(a.root))
