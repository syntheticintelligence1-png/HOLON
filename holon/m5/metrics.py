"""L6, L9 and L10 computed from records (spec/M5/preregistration.json definitions; I54's computation stub).

Each function takes one inputs document (the form tests_m5/_i54.py's fixtures have) and returns the metric's report:
every proportion as {numerator, denominator, value, wilson95}, every threshold judged by definitions.common (meets or
misses only when measured), and an overall verdict. A record that fails a validity rule is scored as UNKNOWN and listed
with the rules it failed; a population member with no record, or with more than one, is UNKNOWN.

  l6(inputs)   inputs: population (finding ids), expect ({id: {classes: {class: trusted}, witness_length,
               value_flows_sha256}}), records (game records), controls (game control documents), corpus_truth
               ({id: rational|irrational|undocumented} or None), corpus_expect
  l9(inputs)   inputs: records (result records), classification, modules, observation_sets, sensitivity,
               base_dependent (law ids), pinned_parameters ({module id: parameters})
  l10(inputs)  inputs: census, atomized, laws (intent laws), controls (intent control documents)
"""
from __future__ import annotations

import hashlib
import json
import re

from .common import checked, overall, proportion, size_label, verdict

DECIDED = ("rational", "irrational", "irrational_bounded")
K, SLICE_MIN_N, SLICE_ACCURACY, MIN_N = 8, 30, 0.95, 5


# ------------------------------------------------------------------ L6
def flows_sha256(control: dict) -> str:
    return hashlib.sha256(json.dumps(control["actions"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def finding_verdict(classes: list[dict]) -> str:
    unt = [c["verdict"] for c in classes if not c["trusted"]]
    if "rational" in unt:
        return "rational"
    if unt and set(unt) == {"irrational"}:
        return "irrational"
    if unt and set(unt) <= {"irrational", "irrational_bounded"}:
        return "irrational_bounded"
    return "UNKNOWN"


def game_rules(rec: dict, exp: dict) -> list[str]:
    """The validity rules (definitions.L6.validity) a game record fails, in the order V1, V2|V3, V4, V5, V6, V8, V7."""
    failed = []
    if not checked(rec.get("evidence")):
        failed.append("V1")
    classes = rec.get("classes") or []
    ids = sorted(c["class"] for c in classes)
    if ids != sorted(exp["classes"]):
        failed.append("V2")
    elif any(exp["classes"][c["class"]] != c["trusted"] for c in classes):
        failed.append("V3")
    wl = exp["witness_length"]
    if rec.get("witness_length") != wl or rec.get("horizon", -1) < wl:
        failed.append("V4")
    if rec.get("witness_in_space") is not True:
        failed.append("V5")
    if rec.get("verdict") != (finding_verdict(classes) if classes else "UNKNOWN"):
        failed.append("V6")
    if rec.get("value_flows_sha256") != exp["value_flows_sha256"]:
        failed.append("V8")
    h = rec.get("horizon", 0)
    for c in classes:
        if c["verdict"] != "rational":
            continue
        sl = c.get("strategy_length")
        if c.get("payoff") != "nonneg" or not sl or not 1 <= sl <= h:
            failed.append("V7")
            break
    return failed


def score(records: list[dict], ids: list[str], expect: dict) -> tuple[dict, dict]:
    groups: dict[str, list] = {}
    for r in records:
        groups.setdefault(r["finding"], []).append(r)
    verdicts, invalid = {}, {}
    for i in ids:
        g = groups.get(i, [])
        if len(g) > 1:
            verdicts[i], invalid[i] = "UNKNOWN", ["one_record"]
        elif not g:
            verdicts[i] = "UNKNOWN"
        else:
            failed = game_rules(g[0], expect[i])
            verdicts[i] = "UNKNOWN" if failed else g[0]["verdict"]
            if failed:
                invalid[i] = failed
    return verdicts, invalid


def accuracy(verdicts: dict, truth: dict) -> dict:
    items = sorted(truth)
    as_truth = lambda v: "irrational" if v == "irrational_bounded" else v  # noqa: E731
    got = {i: verdicts.get(i, "UNKNOWN") for i in items}
    decided = [i for i in items if got[i] in DECIDED]
    right_decided = sum(as_truth(got[i]) == truth[i] for i in decided)
    right = sum(as_truth(got[i]) == truth[i] for i in items)
    freq: dict[str, int] = {}
    for i in items:
        freq[truth[i]] = freq.get(truth[i], 0) + 1
    majority = max(freq.values(), default=0)
    return {"items": len(items), "decided_accuracy": proportion(right_decided, len(decided)),
            "strict_accuracy": proportion(right, len(items)), "majority_baseline": majority,
            "strict_correct": right, "beats_majority": right > majority,
            "false_rational": [i for i in items if truth[i] == "irrational" and got[i] == "rational"],
            "false_irrational": [i for i in items if truth[i] == "rational"
                                 and got[i] in ("irrational", "irrational_bounded")],
            "decided_on_unknown": [i for i in items if truth[i] == "UNKNOWN" and got[i] in DECIDED]}


def l6(inputs: dict) -> dict:
    pop = sorted(inputs["population"])
    recs = inputs["records"]
    v, inv = score([r for r in recs if r["kind"] == "target"], pop, inputs["expect"])
    controls = {c["id"]: c for c in inputs["controls"]}
    cexp = {i: {"classes": {a["id"]: a["trusted"] for a in c["actors"]}, "witness_length": len(c["witness"]),
                "value_flows_sha256": flows_sha256(c)} for i, c in controls.items()}
    cv, cinv = score([r for r in recs if r["kind"] == "control"], sorted(controls), cexp)
    ctl = accuracy(cv, {i: c["truth"]["verdict"] for i, c in controls.items()})
    ctl["invalid"] = dict(sorted(cinv.items()))
    if inputs.get("corpus_truth") is None:
        corpus = {"label": "not_measured", "reason": "no corpus truth file"}
    else:
        truth = {i: t for i, t in inputs["corpus_truth"].items() if t in ("rational", "irrational")}
        kv, kinv = score([r for r in recs if r["kind"] == "corpus"], sorted(truth), inputs["corpus_expect"])
        corpus = accuracy(kv, truth)
        corpus["invalid"] = dict(sorted(kinv.items()))
    n_ctl = size_label(ctl["items"])
    th = {
        "decided": verdict(proportion(sum(v[i] in DECIDED for i in pop), len(pop))["value"], ">=", 0.5,
                           size_label(len(pop))),
        "controls_decided_accuracy": verdict(ctl["decided_accuracy"]["value"], ">=", 0.8,
                                             size_label(ctl["decided_accuracy"]["denominator"])),
        "controls_strict_accuracy": verdict(ctl["strict_accuracy"]["value"], ">=", 0.75, n_ctl),
        "controls_beats_majority": verdict(ctl["strict_correct"], ">", ctl["majority_baseline"], n_ctl),
        "false_rational": verdict(len(ctl["false_rational"]) + len(corpus.get("false_rational", [])), "==", 0,
                                  n_ctl),
        "false_irrational": verdict(len(ctl["false_irrational"]), "==", 0, n_ctl),
        "corpus_decided_accuracy": (verdict(corpus["decided_accuracy"]["value"], ">=", 0.8,
                                            size_label(corpus["decided_accuracy"]["denominator"]))
                                    if "decided_accuracy" in corpus else "not_measured"),
    }
    return {"population": len(pop),
            "decided": proportion(sum(v[i] in DECIDED for i in pop), len(pop)),
            "decided_unbounded": proportion(sum(v[i] in ("rational", "irrational") for i in pop), len(pop)),
            "verdicts": {k: sum(v[i] == k for i in pop) for k in DECIDED + ("UNKNOWN",)},
            "invalid": dict(sorted(inv.items())), "controls": ctl, "corpus": corpus, "thresholds": th,
            "overall": overall(th)}


# ------------------------------------------------------------------ L9
def _entry(cls: dict, aid: str):
    if aid in cls["ids"]:
        return cls["ids"][aid]
    for p in cls["id_patterns"]:
        if re.search(p["pattern"], aid):
            return p
    return None


def environment_premises(rec: dict, cls: dict) -> list[tuple]:
    """E(r): sorted (category, form, id) triples (definitions.L9.environment_premises)."""
    found = set()
    for a in list(rec.get("ledger_assumptions") or []) + list(rec.get("model_assumptions") or []):
        aid = a if isinstance(a, str) else json.dumps(a, sort_keys=True)
        e = _entry(cls, aid)
        if e is None:
            found.add(("unclassified", "axiom", aid))
        elif e["environment"]:
            found.update((c, e["form"], aid) for c in e["categories"])
    for prem in rec.get("premises") or []:
        if not isinstance(prem, str):
            continue
        for prefix, e in cls["premise_prefixes"].items():
            if prem.startswith(prefix) and e["environment"]:
                found.update((c, e["form"], prem) for c in e["categories"])
    for p in (rec.get("environment") or {}).get("premises", []):
        found.add((p["category"], p["form"], "module:" + str(p.get("module")) if p["form"] == "module" else p["id"]))
    return sorted(found)


def predict(family: str, params: dict, o: dict):
    """A module family's prediction for one observation (definitions.L9.module_families); None: not scored."""
    if family == "window":
        return o["q"] - o["t"] <= params["W"]
    if family == "finality_depth":
        return True if o["head"] - o["t"] >= params["d"] else None
    if family == "availability":
        return bool(o["committed"])
    return None


def module_report(m: dict, sets: dict, pinned: dict) -> dict:
    params = set(m["parameters"])
    producers = set(m.get("producers") or [])
    admissible, r1 = [], True
    for name in m["observations"]:
        s = sets.get(name)
        if s is None or params & set(s["reads"]) or s["producer"] in producers:
            r1 = False
        else:
            admissible.append(name)
    scored_obs = []
    for name in sorted(admissible):
        for pos, o in enumerate(sets[name]["items"]):
            p = predict(m["family"], m["parameters"], o)
            if p is not None:
                scored_obs.append((o["t"], name, pos, p, bool(o["observed"])))
    scored_obs.sort()
    n = len(scored_obs)
    width = n // K
    slices = []
    for k in range(K):
        part = scored_obs[k * width:(n if k == K - 1 else (k + 1) * width)]
        slices.append({"n": len(part), "accuracy": proportion(sum(x[3] == x[4] for x in part), len(part))["value"]})
    held = slices[1:] if m["provenance"] == "fit_slice_0" else slices
    accs = [s["accuracy"] for s in held if s["accuracy"] is not None]
    rules = {"R1": r1,
             "R2": m["provenance"] in ("premise", "fit_slice_0") and n >= K,
             "R3": all(s["n"] >= SLICE_MIN_N for s in held),
             "R4": all(s["accuracy"] is not None and s["accuracy"] >= SLICE_ACCURACY for s in held),
             "R5": sum(x[4] for x in scored_obs) >= MIN_N and sum(not x[4] for x in scored_obs) >= MIN_N,
             "R6": pinned.get(m["id"], None) == m["parameters"] and m["id"] in pinned}
    return {"admissible": sorted(admissible), "slices": slices, "worst": min(accs) if accs else None,
            "rules": rules, "validated": all(rules.values()), "category": m["category"]}


def l9(inputs: dict) -> dict:
    cls = inputs["classification"]
    sets = {s["set"]: s for s in inputs["observation_sets"]}
    pinned = inputs.get("pinned_parameters") or {}
    mods = {m["id"]: module_report(m, sets, pinned) for m in inputs["modules"]}

    def modelled(c, f, i):
        if f != "module" or not i.startswith("module:"):
            return False
        mr = mods.get(i[len("module:"):])
        return bool(mr and mr["validated"] and mr["category"] == c)

    dependent, covered, cats, uncl = [], set(), {}, set()
    for r in sorted(inputs["records"], key=lambda r: r["law_id"]):
        E = environment_premises(r, cls)
        if not E:
            continue
        lid = r["law_id"]
        dependent.append(lid)
        ok = all(modelled(*e) for e in E)
        if ok:
            covered.add(lid)
        for c, f, i in E:
            slot = cats.setdefault(c, {"dependent": set(), "covered": set(), "forms": {}})
            slot["dependent"].add(lid)
            slot["forms"][f] = slot["forms"].get(f, 0) + 1
            if ok:
                slot["covered"].add(lid)
            if c == "unclassified":
                uncl.add(i)
    base = sorted(inputs["base_dependent"])
    dropped = sorted(set(base) - set(dependent))
    headline = set(dependent) | set(dropped)
    new = [i for i in dependent if i not in set(base)]
    sens = {"counted": [], "unreplayed": [], "to_unknown": []}
    for p in sorted(inputs["sensitivity"], key=lambda p: (p["law"], p["module"])):
        if p["status_axiom"] == p["status_module"]:
            continue
        if p["status_module"] == "UNKNOWN":
            sens["to_unknown"].append(p["law"])
        elif p["replay"] == "passed" and checked(p.get("evidence")):
            sens["counted"].append(p["law"])
        else:
            sens["unreplayed"].append(p["law"])
    vcats = sorted({m["category"] for m in mods.values() if m["validated"]})
    cov = proportion(len(covered), len(headline))
    bcov = proportion(sum(i in covered for i in base), len(base))
    changed = sens["counted"] or sens["unreplayed"]
    th = {"coverage": verdict(cov["value"], ">=", 0.25, size_label(len(headline))),
          "base_coverage": verdict(bcov["value"], ">=", 0.1, size_label(len(base))),
          "validated_categories": "meets" if vcats == ["da", "fetcher", "l1_chain"] else "misses",
          "sensitivity_unreplayed": verdict(len(sens["unreplayed"]), "==", 0,
                                            "measured" if changed else "not_measured")}
    return {"coverage": cov, "base_coverage": bcov,
            "new_coverage": proportion(sum(i in covered for i in new), len(new)), "base_dropped": dropped,
            "by_category": {c: {"dependent": len(s["dependent"]), "covered": len(s["covered"]),
                                "forms": dict(sorted(s["forms"].items()))} for c, s in sorted(cats.items())},
            "unclassified": sorted(uncl), "modules": dict(sorted(mods.items())), "validated_categories": vcats,
            "sensitivity": dict(sens, count=len(sens["counted"])), "thresholds": th, "overall": overall(th)}


# ------------------------------------------------------------------ L10
def _overlap(a: dict, b: dict) -> bool:
    return a["file"] == b["file"] and max(a["lines"][0], b["lines"][0]) <= min(a["lines"][1], b["lines"][1])


def l10(inputs: dict) -> dict:
    census = inputs["census"]
    atoms = {a["id"]: a for a in inputs["atomized"]}
    laws = inputs["laws"]
    seen: dict[str, int] = {}
    for lw in laws:
        seen[lw["law"]] = seen.get(lw["law"], 0) + 1
    w1 = lambda lw: lw["status"] in ("PROVED", "REFUTED") and checked(lw["evidence"])  # noqa: E731
    w2 = lambda lw: lw["review"]["verdict"] == "faithful" and lw["review"]["reviewer"] != lw["review"]["compiler"]  # noqa: E731,E501
    w3 = lambda lw: bool(lw["clauses"]) and all(c in atoms for c in lw["clauses"])  # noqa: E731
    sole = [lw for lw in laws if seen[lw["law"]] == 1]
    valid = [lw for lw in sole if w1(lw) and w2(lw) and w3(lw)]
    compiled = [lw for lw in sole if w3(lw)]

    def n_covered(ls):
        spans = [atoms[a] for lw in ls for a in lw["clauses"]]
        return sum(any(_overlap(s, c) for s in spans) for c in census)

    wrong = [c["id"] for c in inputs["controls"] if c["truth"]["obstruction"]]
    right = [c["id"] for c in inputs["controls"] if not c["truth"]["obstruction"]]

    def obstruction(cid):
        mine = [lw for lw in laws if lw.get("control") == cid]
        return len(mine) == 1 and mine[0]["status"] == "REFUTED" and w1(mine[0]) and w2(mine[0])

    false = sorted(c for c in right if obstruction(c))
    out = {"census": len(census),
           "coverage": proportion(n_covered(valid), len(census)),
           "compiled_coverage": proportion(n_covered(compiled), len(census)),
           "precision": proportion(sum(any(_overlap(a, c) for c in census) for a in atoms.values()), len(atoms)),
           "recall": proportion(sum(any(_overlap(a, c) for a in atoms.values()) for c in census), len(census)),
           "review": proportion(sum(w2(lw) for lw in laws), len(laws)),
           "control_recall": proportion(sum(obstruction(c) for c in wrong), len(wrong)),
           "false_obstruction": false}
    th = {"coverage": verdict(out["coverage"]["value"], ">=", 0.3, size_label(len(census))),
          "precision": verdict(out["precision"]["value"], ">=", 0.8, size_label(len(atoms))),
          "review": verdict(out["review"]["value"], ">=", 0.9, size_label(len(laws))),
          "control_recall": verdict(out["control_recall"]["value"], ">=", 0.75, size_label(len(wrong))),
          "false_obstruction": verdict(len(false), "==", 0, size_label(len(right)))}
    out["thresholds"], out["overall"] = th, overall(th)
    return out
