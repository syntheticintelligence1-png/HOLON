"""python -m holon eval agree [--root DIR] [--check] (I48 rules C5-C6): final labels and the inter-rater agreement.

Re-derived clean-room in F37 from the I48 contract (rules C5, C6 and C7 of the I48 test module's docstring), the
protocol's "agreement" text (spec/M4/lib/corpus_protocol.json), spec/M4/lib/corpus.schema.json and the textbook
definition of Cohen's kappa (J. Cohen, "A coefficient of agreement for nominal scales", 1960), without reading the
test instrument or the previous bodies of this module.

Inputs: spec/eval/corpus.json (written by holon eval select) and the three label files spec/eval/labels/a.json,
b.json and adjudicator.json (written by holon eval label). Output: spec/eval/corpus.json with, per entry, its labels
{a, b, adjudicated} (the raw labels; adjudicated null when the adjudicator did not label the entry) and its final label,
plus the labellers record and the agreement over the a and b primary labels. With --check nothing is written and the
exit status is 1 when the file would change.

Final label of an entry: the common primary when a and b name the same primary, else the adjudicator's primary
(None when a disagreement has no adjudicated label, or a or b has no label; the corpus schema then rejects the file).

Agreement (Cohen's kappa over the categories of the rule sheet, the a labels as rows and the b labels as columns):
  n         the number of entries with both an a and a b label;
  confusion {row category: {column category: count}} over every pair of categories (zeros included);
  p_o       observed agreement, the diagonal's share of n;
  p_e       chance agreement from the two labellers' marginals, sum over categories of (row total)(column total) / n^2;
  kappa     (p_o - p_e) / (1 - p_e), undefined (None) when n = 0 or p_e = 1;
  se        Cohen's large-sample standard error sqrt(p_o (1 - p_o) / (n (1 - p_e)^2)), None when kappa is None;
  ci95      [kappa - 1.96 se, kappa + 1.96 se], None when kappa is None.
With n = 0 neither share is defined; the schema requires numbers, so p_o and p_e are then 0.0.
Each statistic is computed exactly (fractions; 50-digit decimals for the root and the interval) and rounded once to
the nearest float.
"""
from __future__ import annotations

import argparse
import decimal
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from . import common
from .common import Refused, dumps

LABELS = Path("spec") / "eval" / "labels"
CORPUS = Path("spec") / "eval" / "corpus.json"
ROLES = ("a", "b", "adjudicator")
Z95 = "1.96"   # the two-sided 95% normal quantile as Cohen (1960) tabulates it


def kappa(a: list[str], b: list[str], categories: list[str]) -> dict:
    """Cohen's kappa of two raters' paired nominal labels a[i], b[i] over the given categories."""
    if len(a) != len(b):
        raise ValueError(f"the two label lists differ in length ({len(a)} and {len(b)})")
    cats = list(categories)
    if len(set(cats)) != len(cats):
        raise ValueError("the categories repeat a name")
    outside = sorted({x for x in list(a) + list(b) if x not in cats}, key=str)
    if outside:
        raise ValueError(f"labels outside the categories: {outside}")
    table = {r: {c: 0 for c in cats} for r in cats}
    for r, c in zip(a, b):
        table[r][c] += 1
    n = len(a)
    agree_count = sum(table[k][k] for k in cats)
    row_total = {k: sum(table[k].values()) for k in cats}
    col_total = {k: sum(table[r][k] for r in cats) for k in cats}
    if n == 0:
        return {"n": 0, "p_o": 0.0, "p_e": 0.0, "kappa": None, "se": None, "ci95": None, "confusion": table}
    # Exact rational arithmetic, each reported statistic rounded once to the nearest float (the square root and
    # the interval through 50-digit decimals), so no result depends on an evaluation order.
    p_o = Fraction(agree_count, n)
    p_e = Fraction(sum(row_total[k] * col_total[k] for k in cats), n * n)
    if p_e >= 1:
        return {"n": n, "p_o": float(p_o), "p_e": float(p_e), "kappa": None, "se": None, "ci95": None,
                "confusion": table}
    k = (p_o - p_e) / (1 - p_e)
    with decimal.localcontext() as ctx:
        ctx.prec = 50
        var = p_o * (1 - p_o) / (n * (1 - p_e) ** 2)
        se = (Decimal(var.numerator) / Decimal(var.denominator)).sqrt()
        kd = Decimal(k.numerator) / Decimal(k.denominator)
        lo, hi = kd - Decimal(Z95) * se, kd + Decimal(Z95) * se
    return {"n": n, "p_o": float(p_o), "p_e": float(p_e), "kappa": float(k), "se": float(se),
            "ci95": [float(lo), float(hi)], "confusion": table}


def final_label(a: str | None, b: str | None, adjudicated: str | None) -> str | None:
    """The entry's final primary label (rule C5): the shared one, else the adjudicator's."""
    if a is None or b is None:
        return None
    return a if a == b else adjudicated


def _read_labels(root: Path) -> dict:
    """{role: the role's label file} for a, b and the adjudicator; a missing or malformed file is refused."""
    out = {}
    for role in ROLES:
        p = root / LABELS / f"{role}.json"
        if not p.is_file():
            raise Refused(f"{LABELS / (role + '.json')} is missing: run holon eval label --role {role} first")
        doc = common.load_json(p)
        if not isinstance(doc, dict) or not isinstance(doc.get("labels"), list):
            raise Refused(f"{LABELS / (role + '.json')} holds no label list")
        if doc.get("role") != role:
            raise Refused(f"{LABELS / (role + '.json')} names role {doc.get('role')!r}, not {role!r}")
        out[role] = doc
    return out


def _by_entry(doc: dict, role: str) -> dict:
    seen: dict = {}
    for x in doc["labels"]:
        if x["entry"] in seen:
            raise Refused(f"labeller {role} labels {x['entry']} twice")
        seen[x["entry"]] = x["label"]
    return seen


def build(corpus: dict, raw: dict, proto: dict, categories: list[str]) -> dict:
    """The corpus document with every entry's labels and final label, the labellers and the agreement (C5-C6)."""
    ids = [e["id"] for e in corpus["entries"]]
    lab = {role: _by_entry(raw[role], role) for role in ROLES}
    for role in ("a", "b"):
        order = [x["entry"] for x in raw[role]["labels"]]
        if order != ids:
            raise Refused(f"labeller {role} does not label every corpus entry once, in corpus order")
    owed = [i for i in ids if lab["a"][i] is not None and lab["b"][i] is not None
            and lab["a"][i]["primary"] != lab["b"][i]["primary"]]
    if [x["entry"] for x in raw["adjudicator"]["labels"]] != owed:
        raise Refused("the adjudicator does not label exactly the entries where a and b disagree, in corpus order")
    names = [raw[role].get("labeller") for role in ROLES]
    if len(set(names)) != len(ROLES):
        raise Refused("a, b and the adjudicator are not three different labellers")
    families = {raw[role].get("family") for role in ROLES}
    if len(families) != 1:
        raise Refused(f"the label files name different families: {sorted(map(str, families))}")
    out = dict(corpus)
    entries = []
    for e in corpus["entries"]:
        la, lb = lab["a"][e["id"]], lab["b"][e["id"]]
        ladj = lab["adjudicator"].get(e["id"])
        ent = dict(e)
        ent["labels"] = {"a": la, "b": lb, "adjudicated": ladj}
        ent["label"] = final_label(la["primary"] if la else None, lb["primary"] if lb else None,
                                   ladj["primary"] if ladj else None)
        entries.append(ent)
    out["entries"] = entries
    both = [(lab["a"][i]["primary"], lab["b"][i]["primary"]) for i in ids
            if lab["a"][i] is not None and lab["b"][i] is not None]
    out["agreement"] = kappa([p for p, _ in both], [q for _, q in both], categories)
    out["labellers"] = {"a": names[0], "b": names[1], "adjudicator": names[2], "family": families.pop(),
                        "model_tags": dict(proto["labelling_invocation"]["roles"])}
    return out


def cli_agree(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval agree")
    ap.add_argument("--root", type=Path, default=common.ROOT)
    ap.add_argument("--check", action="store_true", help="exit 1 when spec/eval/corpus.json would change")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not (root / CORPUS).is_file():
        raise Refused(f"{CORPUS} is missing under {root}: run holon eval select first")
    corpus = common.load_json(root / CORPUS)
    categories = common.load_json(common.LIB / "rule_sheet.json")["categories"]
    doc = build(corpus, _read_labels(root), common.protocol(), categories)
    from holon.schema import errors
    errs = errors(doc, common.load_json(common.LIB / "corpus.schema.json"))
    if errs:
        print("the corpus does not validate: " + "; ".join(errs[:10]), file=sys.stderr)
        return 1
    differs = common.write_or_check(root / CORPUS, dumps(doc), args.check)
    ag = doc["agreement"]
    shown = "undefined" if ag["kappa"] is None else f"{ag['kappa']:.3f}"
    if args.check:
        print(f"{CORPUS}: {'differs from a fresh build' if differs else 'up to date'} (kappa {shown}, n {ag['n']})")
        return 1 if differs else 0
    print(f"{'wrote' if differs else 'unchanged'} {CORPUS}: kappa {shown} over n {ag['n']}")
    return 0
