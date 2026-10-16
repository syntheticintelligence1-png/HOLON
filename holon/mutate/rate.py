"""results/M2/mutation_i61/summary.json from the records (instrument reporting, threshold; the contract's summary
format). `python -m holon mutate rate [--check]`."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from . import common as C
from . import decide as D

VERSION = "holon-mutation/0.3"


def rate(num: int, den: int) -> dict:
    return {"num": num, "den": den, "value": num / den if den else None}


def language(m: dict) -> str:
    return "solidity" if m["file"].endswith(".sol") else "go"


def summary(inst: dict, records: dict, adjudication: dict, refs: dict, commit: str) -> dict:
    """records: {id: record} of every catalog mutant; refs: {"review", "adjudication", "gate": {"path", "sha256"},
    "instrument": {...}}."""
    ms = {m["id"]: m for m in inst["mutants"]}
    verdicts = adjudication["verdicts"]
    eq = {i for i, v in verdicts.items() if v["equivalent"]}
    dup = {i for i, v in verdicts.items() if v.get("duplicate_of")}
    killed = {i for i, r in records.items() if r["outcome"] == "killed"}
    err = {i for i, r in records.items() if r["outcome"] == "error"}
    k1 = {i for i, r in records.items() if any(x["how"] == "K1" for x in r["kill"]["by"])}
    strata = {"A": sorted(i for i in records if ms[i]["stratum"] == "A"),
              "B": sorted(i for i in records if ms[i]["stratum"] == "B")}
    out = {"version": VERSION, "iteration": inst["iteration"], "milestone": inst["milestone"],
           "pipeline_commit": commit, "instrument": refs["instrument"], "mutants_sha256": inst["mutants_sha256"],
           "review": refs["review"], "adjudication": refs["adjudication"], "gate": refs["gate"],
           "threshold": inst["threshold"]["kill_rate_non_equivalent"], "threshold_stratum": inst["threshold"]["stratum"],
           "seed": inst["seed"], "strata": {}, "non_error": {}, "by_language": {}, "per_site": {}, "k1_only": {},
           "plan_literal": {}, "new_law_kills": {}, "k2_model_tied": {}, "detection": {}, "unpredicted_rate": {},
           "masked_rate": {}, "dedup": {}, "by_operator": {}, "by_family": {}}
    for st, members in (("A", strata["A"]), ("B", strata["B"]), ("all", sorted(records))):
        s = set(members)
        ne = s - eq
        e = {"mutants": len(s), "killed": len(killed & s), "killed_k1": len(k1 & s), "equivalent": len(eq & s),
             "killed_equivalent": len(killed & eq & s), "errors": len(err & s),
             "rate_all": rate(len(killed & s), len(s)), "rate_non_equivalent": rate(len(killed & ne), len(ne)),
             "meets_threshold": None}
        if st == inst["threshold"]["stratum"]:
            e["meets_threshold"] = 5 * len(killed & ne) >= 4 * len(ne)
        out["strata"][st] = e
        if st == "all":
            continue
        out["non_error"][st] = {"rate_all": rate(len(killed & (s - err)), len(s - err)),
                                "rate_non_equivalent": rate(len(killed & (ne - err)), len(ne - err))}
        langs = {}
        for lang in ("solidity", "go"):
            lm = {i for i in s if language(ms[i]) == lang}
            if lm:
                lne = lm - eq
                langs[lang] = {"mutants": len(lm), "killed": len(killed & lm), "errors": len(err & lm),
                               "equivalent": len(eq & lm), "rate_all": rate(len(killed & lm), len(lm)),
                               "rate_non_equivalent": rate(len(killed & lne), len(lne))}
        out["by_language"][st] = langs
        sites = defaultdict(set)
        for i in s:
            sites[(ms[i]["file"], ms[i]["offset"], ms[i]["operator"])].add(i)
        ks = {k for k, v in sites.items() if v & killed}
        es = {k for k, v in sites.items() if v <= eq}
        nes = set(sites) - es
        out["per_site"][st] = {"sites": len(sites), "killed": len(ks), "equivalent": len(es),
                               "rate_non_equivalent": rate(len(ks & nes), len(nes))}
        out["k1_only"][st] = rate(len(k1 & ne), len(ne))
        out["plan_literal"][st] = rate(sum(1 for i in s if D.plan_literal(records[i])), len(s))
        out["new_law_kills"][st] = sum(1 for i in s if records[i]["kill"]["by"] and all(
            records[i]["laws"][x["law"]]["baseline"] == "absent" for x in records[i]["kill"]["by"]))
        tied = untied = 0
        for i in sorted(s & killed):
            k2 = [records[i]["laws"][x["law"]] for x in records[i]["kill"]["by"] if x["how"] == "K2"]
            if any(x["falsifier"]["model_tied"] for x in k2):
                tied += 1
            elif k2:
                untied += 1
        out["k2_model_tied"][st] = {"tied": tied, "untied": untied}
        det = {i for i in s if records[i]["outcome"] == "killed" or records[i]["kill"]["unpredicted"]
               or records[i]["masked_obstructions"]}
        out["detection"][st] = rate(len(det), len(s))
        out["unpredicted_rate"][st] = rate(sum(1 for i in s if records[i]["kill"]["unpredicted"]), len(s))
        out["masked_rate"][st] = rate(sum(1 for i in s if records[i]["masked_obstructions"]), len(s))
        dd, dne = s - dup, ne - dup
        out["dedup"][st] = {"rate_all": rate(len(killed & dd), len(dd)),
                            "rate_non_equivalent": rate(len(killed & dne), len(dne))}
        ops = defaultdict(Counter)
        for i in sorted(s):
            o = ops[ms[i]["operator"]]
            r = records[i]
            o["mutants"] += 1
            o["killed"] += i in killed
            o["killed_k1"] += i in k1
            o["equivalent"] += i in eq
            o["errors"] += i in err
            o["unpredicted"] += bool(r["kill"]["unpredicted"])
            o["masked"] += bool(r["masked_obstructions"])
            o["proof_lost_unwitnessed"] += bool(r["proof_lost_unwitnessed"])
        keys = ("mutants", "killed", "killed_k1", "equivalent", "errors", "unpredicted", "masked",
                "proof_lost_unwitnessed")
        out["by_operator"][st] = {op: {k: c[k] for k in keys} for op, c in sorted(ops.items())}
        fams = defaultdict(lambda: {"predicted": 0, "killed": 0})
        for i in sorted(s):
            laws = records[i]["laws"]
            for f in sorted({e_["family"] for e_ in laws.values() if e_["predicted"]}):
                fams[f]["predicted"] += 1
            for f in sorted({laws[x["law"]]["family"] for x in records[i]["kill"]["by"]}):
                fams[f]["killed"] += 1
        out["by_family"][st] = {f: v for f, v in sorted(fams.items())}
    codec = {i for i in strata["B"] if ms[i]["function"] in inst["in_scope"]["files"][ms[i]["file"]].get(
        "codec_functions", [])}
    cne = codec - eq
    out["B_codec_functions"] = {"mutants": len(codec), "killed": len(killed & codec), "equivalent": len(eq & codec),
                                "rate_all": rate(len(killed & codec), len(codec)),
                                "rate_non_equivalent": rate(len(killed & cne), len(cne))}
    fl, rc = [], []
    for i in sorted(eq):
        why, reach = D.contradictions(records[i])
        if why:
            fl.append({"id": i, "why": ", ".join(why)})
            if reach:
                rc.append({"id": i, "why": ", ".join(why)})
    out["contradicted"] = {"function_level": fl, "reachable": rc}
    out["rate_non_equivalent_reversed"] = {}
    for key, lst in (("function_level", fl), ("reachable", rc)):
        rev = {x["id"] for x in lst}
        ne_rev = {i for i in (set(records) - eq) | rev if ms[i]["stratum"] == "A"}
        out["rate_non_equivalent_reversed"][key] = rate(len(killed & ne_rev), len(ne_rev))
    agree = defaultdict(Counter)
    survivors = []
    for i in sorted(records):
        r = records[i]
        if r["outcome"] == "killed":
            continue
        cls = (r["class"], r["gap_stage"], r["rule_gap_kind"])
        survivors.append({"id": i, "class": r["class"], "gap_stage": r["gap_stage"],
                          "rule_gap_kind": r["rule_gap_kind"], "structural": ms[i]["structural"]["class"],
                          "why": D.survivor_why(r, cls)})
        agree[ms[i]["structural"]["class"]]["/".join(v for v in cls if v)] += 1
    out["structural_agreement"] = {k: dict(sorted(v.items())) for k, v in sorted(agree.items())}
    out["survivors"] = survivors
    out["unpredicted"] = [{"id": i, "law": x["law"], "how": x["how"]} for i in sorted(records)
                          for x in records[i]["kill"]["unpredicted"]]
    out["recomputed_only"] = [{"id": i, "law": x["law"], "how": x["how"]} for i in sorted(records)
                              for x in records[i]["recomputed_only"]]
    for key in ("masked_obstructions", "proof_lost_unwitnessed"):
        out[key] = [{"id": i, "law": law} for i in sorted(records) for law in records[i][key]]
    out["errors"] = sorted(i for i in records if records[i]["outcome"] == "error")
    out["extraction_defects"] = sorted(i for i in records if records[i]["extraction_defect_detected"] is True)
    out["corpus_detected"] = sorted(i for i in records if records[i]["corpus_detected"] is True)
    return out


def metric(summary: dict, source=None) -> dict:
    """results/M2/metrics.json "mutation_adequacy" (reporting.metric; I22-R6's name and shape); source the summary's
    repo-relative path (default this key's)."""
    a = summary["strata"][summary["threshold_stratum"]]
    return {"source": Path(source or C.SUMMARY).as_posix(), "threshold": summary["threshold"], "rate_all": a["rate_all"],
            "rate_non_equivalent": a["rate_non_equivalent"], "meets_threshold": a["meets_threshold"]}
