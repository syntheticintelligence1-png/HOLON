"""`holon derivation refine` (rules G3, G4, C4, C5): every planted, random and product case on the consumer model and on
the real code, compared.

The model runs each case from a zero receiver (holon.derivation.interp); an oracle call with no recorded answer stops
the case, and after a pass the oracle (the generated Go test's TestHolonOracle) answers every pending query at once,
until no case is pending. The real code runs every case once (TestHolonReplay). With --check, nothing runs in Go: the
model is re-run from results/M3/derivation/environment.json's answers and the real sides are the committed replay
report's, and every output must reproduce byte for byte.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import OUT_GEN, OUT_REPLAY, OUT_RES, DerivationError, Refused, dumps, load, ref
from .corpus import blob, blobs_hex
from .interp import Interp, NeedAnswer, arg_key

REFINEMENT_VERSION = "holon-derivation-refinement/0.1"
STEPS_VERSION = "holon-derivation-steps/0.1"
REPORT_VERSION = "holon-derivation-replay/0.1"
OBS = ("status", "error", "panic", "info")
MAX_ROUNDS = 8


def _with_blobs(batch: dict, field: list, blobs: list) -> dict:
    b = copy.deepcopy(batch)
    cur = b
    for name in field[:-1]:
        cur = cur.setdefault(name, {})
    cur[field[-1]] = blobs
    return b


def cases(side: dict, corpus: dict, product: dict) -> list:
    """[(id, source, batch JSON)]: the corpus's planted and random cases, then every committed product batch (rule
    K4), each with its blobs (rule C2)."""
    field = side["product"]["blobs_field"]
    out = [(c["id"], c["source"], _with_blobs(c["batch"], field, blobs_hex(c))) for c in corpus["cases"]]
    data = {tr["id"]: {c["k"]: c for c in tr["commits"]} for tr in corpus["product"]}
    for tr in product["traces"]:
        for c in tr["commits"]:
            if c["status"] != "ok":
                continue
            d = data[tr["id"]][c["k"]]["data"]
            blobs = ["0x" + blob(x, j, []).hex() for j, x in enumerate(d)]
            out.append((f"{tr['id']}/{c['k']}", "product", _with_blobs(c["batch"], field, blobs)))
    return out


def evaluate(section: dict, environment: dict, todo: list, answers: dict, ask) -> dict:
    """{id: model outcome}, asking ask(queries) -> answers for the oracle queries the cases need."""
    done: dict = {}
    pending = list(todo)
    for _ in range(MAX_ROUNDS):
        queries: dict = {}
        nxt = []
        for cid, src, batch in pending:
            try:
                done[cid] = Interp(section, environment, answers).run(batch)
            except NeedAnswer as q:
                queries[(q.fid, arg_key(q.arg))] = (q.fid, q.arg)
                nxt.append((cid, src, batch))
        if not queries:
            return done
        got = ask(sorted(queries.values(), key=lambda fa: (fa[0], arg_key(fa[1]))))
        for (fid, arg), a in got:
            answers.setdefault(fid, {})[arg_key(arg)] = a
        pending = nxt
    raise DerivationError(f"oracle answers still missing after {MAX_ROUNDS} rounds")


def agree(model: dict, real: dict) -> bool:
    return model.get("status") != "unsupported" and all(model.get(k) == real.get(k) for k in OBS)


def records(side_rel: str, root: Path, todo: list, model: dict, real: dict, answers: dict, go_version: str,
            command: str, commit: str) -> dict:
    steps, dis, by_source, sites, panics, unsup, bad = [], [], {}, {}, {}, [], []
    n_agree = 0
    for cid, src, _b in todo:
        m, r = model[cid], real[cid]
        a = agree(m, r)
        steps.append({"id": cid, "source": src, "model": m, "real": r, "agree": a})
        by_source[src] = by_source.get(src, 0) + 1
        if m.get("status") == "unsupported":
            unsup.append(cid)
        if a:
            n_agree += 1
            if m.get("site"):
                s = ":".join(m["site"].split(":")[:2])
                sites[s] = sites.get(s, 0) + 1
            if m.get("status") == "panic":
                panics[m["panic"]] = panics.get(m["panic"], 0) + 1
        else:
            bad.append(cid)
            dis.append({"id": cid, "model": m, "real": r})
    ref_rec = {"refinement_version": REFINEMENT_VERSION, "corpus": ref(root, f"{OUT_GEN}/corpus.json"),
               "product": ref(root, f"{OUT_GEN}/product.json"), "sidecar": ref(root, side_rel),
               "cases": by_source, "agree": n_agree, "disagreements": bad, "unsupported": unsup, "sites": sites,
               "panics": panics, "toolchain": {"go": go_version}}
    report = {"report_version": REPORT_VERSION, "morph_commit": commit, "go_version": go_version,
              "command": command, "cases": {cid: real[cid] for cid, _s, _b in todo}}
    return {f"{OUT_RES}/steps.json": dumps({"steps_version": STEPS_VERSION, "steps": steps}),
            f"{OUT_RES}/refinement.json": dumps(ref_rec),
            f"{OUT_RES}/disagreements.json": dumps({"disagreements": dis}),
            f"{OUT_RES}/environment.json": dumps({"answers": answers}),
            f"{OUT_REPLAY}/report.json": dumps(report)}


def run(root: Path, side: dict, side_rel: str, check: bool = False) -> dict:
    for rel in (side["extract"]["output"], f"{OUT_GEN}/corpus.json", f"{OUT_GEN}/product.json"):
        if not (root / rel).is_file():
            raise Refused(f"{rel} is missing")
    section = load(root / side["extract"]["output"])["consumer"]
    corpus = load(root / f"{OUT_GEN}/corpus.json")
    product = load(root / f"{OUT_GEN}/product.json")
    if corpus["sidecar"]["sha256"] != ref(root, side_rel)["sha256"]:
        raise Refused("the corpus names another sidecar")
    if product["document"]["sha256"] != ref(root, side["extract"]["output"])["sha256"]:
        raise Refused("the product names another document")
    environment = side["extract"].get("environment") or {}
    todo = cases(side, corpus, product)
    if check:
        rep = load(root / f"{OUT_REPLAY}/report.json")
        answers = load(root / f"{OUT_RES}/environment.json")["answers"]

        def no_go(queries):
            raise DerivationError(f"refine --check: no recorded answer for {queries[0][0]}")
        model = evaluate(section, environment, todo, copy.deepcopy(answers), no_go)
        real = rep["cases"]
        if sorted(real) != sorted(cid for cid, _s, _b in todo):
            raise DerivationError("the replay report's cases are not the corpus's")
        return records(side_rel, root, todo, model, real, answers, rep["go_version"], rep["command"],
                       rep["morph_commit"])
    from .goside import Workspace
    with Workspace(root, side, section) as ws:
        answers: dict = {}

        def ask(queries):
            out = ws.run("TestHolonOracle", "HOLON_DERIV_ORACLE",
                         {"queries": [{"fn": f, "arg": "0x" + a.hex()} for f, a in queries]})
            if len(out) != len(queries):
                raise DerivationError("the oracle answered a different number of queries")
            for (f, _a), o in zip(queries, out):
                if "unsupported" in o:
                    raise DerivationError(f"the oracle cannot answer {f}: {o['unsupported']}")
            return list(zip(queries, out))
        model = evaluate(section, environment, todo, answers, ask)
        real = ws.run("TestHolonReplay", "HOLON_DERIV_REPLAY", {"cases": [{"id": c, "batch": b} for c, _s, b in todo]})
        for cid, r in real.items():
            if r.get("status") == "input":
                raise DerivationError(f"{cid}: the replay could not build the batch: {r.get('error')}")
        return records(side_rel, root, todo, model, real, answers, ws.go_version, ws.command("TestHolonReplay"),
                       side["target"]["commit"])
