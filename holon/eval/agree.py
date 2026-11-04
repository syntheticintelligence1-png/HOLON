"""python -m holon eval agree [--root DIR] [--check] (I48 rules C5-C6): labels, final labels and agreement.

Reads spec/eval/labels/a.json, b.json and adjudicator.json (each validated against labels.schema.json) and
spec/eval/corpus.json, and writes into corpus.json:
  - per entry, labels {a, b, adjudicated} (the raw labels; adjudicated null when a and b agree) and label: a's primary
    when a and b agree, else the adjudicated primary;
  - agreement: Cohen's kappa over the a and b primaries and the rule sheet's nine categories: n, the observed agreement
    p_o, the chance agreement p_e from the two marginals, kappa = (p_o - p_e) / (1 - p_e), Cohen's large-sample
    standard error se = sqrt(p_o (1 - p_o) / n) / (1 - p_e), ci95 = kappa -+ 1.96 se, and the confusion matrix
    (a's category -> b's category -> count, every category present); kappa, se and ci95 are null when kappa is
    undefined (no entry, or p_e = 1);
  - labellers: the three labellers' names, the family and the protocol's model tags (never a model name).

Refused (exit 2) when a label file is missing or invalid, when a or b does not label every entry exactly once in corpus
order, when the adjudicator's entries are not exactly the disagreements, when the three labellers are not three, or
when an entry lacks a label the final label needs. --check writes nothing and exits 1 when corpus.json differs.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from . import common
from .common import Refused, dumps

LABELS = Path("spec") / "eval" / "labels"
CORPUS = Path("spec") / "eval" / "corpus.json"
ROLES = ("a", "b", "adjudicator")


def kappa(a: list[str], b: list[str], categories: list[str]) -> dict:
    if len(a) != len(b):
        raise ValueError("the two labellings differ in length")
    n = len(a)
    confusion = {x: {y: 0 for y in categories} for x in categories}
    for x, y in zip(a, b):
        confusion[x][y] += 1
    if n == 0:
        return {"n": 0, "p_o": 0.0, "p_e": 0.0, "kappa": None, "se": None, "ci95": None, "confusion": confusion}
    p_o = sum(confusion[c][c] for c in categories) / n
    p_e = sum(a.count(c) * b.count(c) for c in categories) / (n * n)
    if p_e == 1.0:
        return {"n": n, "p_o": p_o, "p_e": p_e, "kappa": None, "se": None, "ci95": None, "confusion": confusion}
    k = (p_o - p_e) / (1.0 - p_e)
    se = math.sqrt(p_o * (1.0 - p_o) / n) / (1.0 - p_e)
    return {"n": n, "p_o": p_o, "p_e": p_e, "kappa": k, "se": se, "ci95": [k - 1.96 * se, k + 1.96 * se],
            "confusion": confusion}


def _read_labels(root: Path) -> dict:
    from holon.schema import errors
    schema = common.load_json(common.LIB / "labels.schema.json")
    out = {}
    for who in ROLES:
        p = root / LABELS / f"{who}.json"
        if not p.exists():
            raise Refused(f"{p.relative_to(root)} is missing")
        doc = common.load_json(p)
        errs = errors(doc, schema)
        if errs:
            raise Refused(f"{p.relative_to(root)} does not validate: " + "; ".join(errs[:10]))
        if doc["role"] != who:
            raise Refused(f"{p.relative_to(root)} holds role {doc['role']!r}")
        out[who] = doc
    return out


def build(corpus: dict, raw: dict, proto: dict, categories: list[str]) -> dict:
    ids = [e["id"] for e in corpus["entries"]]
    for who in ("a", "b"):
        got = [x["entry"] for x in raw[who]["labels"]]
        if got != ids:
            raise Refused(f"labeller {who} does not label every entry exactly once in corpus order")
    a = {x["entry"]: x["label"] for x in raw["a"]["labels"]}
    b = {x["entry"]: x["label"] for x in raw["b"]["labels"]}
    disagree = [i for i in ids if a[i] and b[i] and a[i]["primary"] != b[i]["primary"]]
    adj_ids = [x["entry"] for x in raw["adjudicator"]["labels"]]
    if adj_ids != disagree:
        raise Refused("the adjudicator's entries are not exactly the disagreements of a and b, in corpus order")
    adj = {x["entry"]: x["label"] for x in raw["adjudicator"]["labels"]}
    names = [raw[w]["labeller"] for w in ROLES]
    if len(set(names)) != 3:
        raise Refused("a, b and the adjudicator are not three different labellers")
    missing = [i for i in ids if a[i] is None or b[i] is None or (i in adj and adj[i] is None)]
    if missing:
        raise Refused(f"entries without the labels the final label needs: {missing}")
    families = {raw[w]["family"] for w in ROLES}
    if len(families) != 1:
        raise Refused("the three labellers name different families")
    entries = []
    for e in corpus["entries"]:
        i = e["id"]
        pa, pb = a[i]["primary"], b[i]["primary"]
        entries.append(dict(e, labels={"a": a[i], "b": b[i], "adjudicated": adj.get(i)},
                            label=pa if pa == pb else adj[i]["primary"]))
    out = dict(corpus, entries=entries)
    out["agreement"] = kappa([a[i]["primary"] for i in ids], [b[i]["primary"] for i in ids], categories)
    out["labellers"] = {"a": names[0], "b": names[1], "adjudicator": names[2], "family": families.pop(),
                        "model_tags": dict(proto["labelling_invocation"]["roles"])}
    return out


def cli_agree(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval agree")
    ap.add_argument("--root", type=Path, default=common.ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if not (root / CORPUS).exists():
        raise Refused(f"{CORPUS} is missing under {root}")
    proto = common.protocol()
    categories = common.load_json(common.LIB / "rule_sheet.json")["categories"]
    corpus = build(common.load_json(root / CORPUS), _read_labels(root), proto, categories)
    from holon.schema import errors
    errs = errors(corpus, common.load_json(common.LIB / "corpus.schema.json"))
    if errs:
        print("corpus.json does not validate: " + "; ".join(errs[:10]), file=sys.stderr)
        return 1
    differs = common.write_or_check(root / CORPUS, dumps(corpus), a.check)
    if a.check:
        if differs:
            print(f"differs: {CORPUS.as_posix()}", file=sys.stderr)
        return 1 if differs else 0
    k = corpus["agreement"]["kappa"]
    print(f"{'wrote' if differs else 'unchanged'}: {CORPUS.as_posix()} ({len(corpus['entries'])} entries, "
          f"kappa {'undefined' if k is None else f'{k:.3f}'})")
    return 0
