"""I54's instrument: the L6, L9 and L10 definitions written out a second time, independently of holon/.

It holds, for tests_m5/test_m5_definitions.py:
- the control documents (game controls and intent controls) exactly as holon.m5.controls must write them, and an
  explicit-state interpreter that computes each game control's truth from its document alone (rule K2);
- the census rule of definitions.L10.census over a file's text (rule C1);
- a reference computation of every L6, L9 and L10 measure from records (rules M6, M9, M10);
- fixtures: records built here, deterministically, for the honest and the gaming cases (rule F1).

It imports nothing from holon/ or tools/. Numbers it relies on (MIN_N, K, ...) are checked against the key by the test.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import re

MIN_N = 5
K = 8
SLICE_MIN_N = 30
SLICE_ACCURACY = 0.95
CHECKED = "ALL PROOFS CHECK"
DECIDED6 = ("rational", "irrational", "irrational_bounded")
CATEGORIES = ("l1_chain", "da", "fetcher")
GAME_FAMILIES = ("free_trigger", "profit", "recoup", "deep", "trusted_only", "costly", "incomparable")
INTENT_FAMILIES = ("bound", "access", "monotone")
INSTANCES = (1, 2)
SEMANTICS = ("single deviator: one class acts, the others take no action; each action at most once per schedule; "
             "holdings start at 0; payoff at the schedule's end")


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def tok(family: str, n: int, role: str) -> str:
    return hashlib.sha256(f"{family}/{n}/{role}".encode()).hexdigest()[:6]


# ------------------------------------------------------------------ proportions and labels
def wilson(k: int, n: int):
    if n == 0:
        return None
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def prop(k: int, n: int) -> dict:
    return {"numerator": k, "denominator": n, "value": (round(k / n, 6) if n else None), "wilson95": wilson(k, n)}


def label(n: int, absent: bool = False) -> str:
    if absent or n == 0:
        return "not_measured"
    return "measured" if n >= MIN_N else "insufficient_n"


def judge(value, op: str, target, lab: str) -> str:
    if lab != "measured":
        return lab
    ok = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "==": lambda a, b: a == b}[op](value, target)
    return "meets" if ok else "misses"


def overall(th: dict) -> str:
    """definitions.common.overall: meets iff every threshold meets; misses iff some threshold misses; else not_judged."""
    vs = list(th.values())
    if vs and all(v == "meets" for v in vs):
        return "meets"
    return "misses" if "misses" in vs else "not_judged"


def flows_sha256(control: dict) -> str:
    """V8's expected value_flows_sha256 of a game control: sha256 of the canonical JSON of its actions."""
    return hashlib.sha256(json.dumps(control["actions"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ------------------------------------------------------------------ game controls (definitions.controls)
def _game(family: str, n: int) -> dict:
    o, u = "a" + tok(family, n, "trusted"), "a" + tok(family, n, "untrusted")
    s0, s1 = "s" + tok(family, n, "asset0"), "s" + tok(family, n, "asset1")
    v = "v" + tok(family, n, "var")
    act = lambda role: "f" + tok(family, n, role)  # noqa: E731
    actors = [{"id": o, "trusted": True}, {"id": u, "trusted": False}]
    assets, horizon = [s0], 2
    if family == "free_trigger":
        actions = [{"id": act("poke"), "by": [u], "guard": [], "effect": [["add", v, n]], "flows": {}}]
        bad, witness = [["ge", v, 1]], [{"action": act("poke"), "caller": u}]
    elif family == "profit":
        actions = [{"id": act("claim"), "by": sorted([o, u]), "guard": [["eq", v, 0]], "effect": [["set", v, 1]],
                    "flows": {"caller": {s0: n}}}]
        bad, witness = [["ge", v, 1]], [{"action": act("claim"), "caller": u}]
    elif family == "recoup":
        actions = [{"id": act("deposit"), "by": [u], "guard": [["eq", v, 0]], "effect": [["set", v, 1]],
                    "flows": {"caller": {s0: -n}}},
                   {"id": act("trigger"), "by": [u], "guard": [["eq", v, 1]], "effect": [["set", v, 2]], "flows": {}},
                   {"id": act("withdraw"), "by": [u], "guard": [["eq", v, 2]], "effect": [["set", v, 3]],
                    "flows": {"caller": {s0: n}}}]
        bad, horizon = [["ge", v, 2]], 3
        witness = [{"action": act("deposit"), "caller": u}, {"action": act("trigger"), "caller": u}]
    elif family == "deep":
        horizon = 1 + n
        actions = [{"id": act("force"), "by": [o], "guard": [], "effect": [["set", v, horizon + 1]], "flows": {}}]
        actions += [{"id": act(f"step{i}"), "by": [u], "guard": [["eq", v, i]], "effect": [["set", v, i + 1]],
                     "flows": {}} for i in range(horizon + 1)]
        bad, witness = [["ge", v, horizon + 1]], [{"action": act("force"), "caller": o}]
    elif family == "trusted_only":
        actions = [{"id": act("set"), "by": [o], "guard": [], "effect": [["set", v, n]], "flows": {}},
                   {"id": act("ping"), "by": [u], "guard": [], "effect": [], "flows": {}}]
        bad, witness = [["ge", v, 1]], [{"action": act("set"), "caller": o}]
    elif family == "costly":
        actions = [{"id": act("challenge"), "by": [u], "guard": [["eq", v, 0]], "effect": [["set", v, 1]],
                    "flows": {"caller": {s0: -n}}},
                   {"id": act("refund"), "by": [o], "guard": [["eq", v, 1]], "effect": [["set", v, 2]],
                    "flows": {u: {s0: n}}}]
        bad, witness = [["ge", v, 1]], [{"action": act("challenge"), "caller": u}]
    elif family == "incomparable":
        assets = [s0, s1]
        actions = [{"id": act("swap"), "by": [u], "guard": [], "effect": [["set", v, 1]],
                    "flows": {"caller": {s0: n, s1: -n}}}]
        bad, witness = [["ge", v, 1]], [{"action": act("swap"), "caller": u}]
    else:
        raise ValueError(family)
    doc = {"id": f"g_{family}_{n}", "family": family, "semantics": SEMANTICS, "actors": actors, "assets": assets,
           "vars": {v: 0}, "actions": actions, "bad": bad, "horizon": horizon, "witness": witness}
    doc["truth"] = game_truth(doc)
    return doc


def game_controls() -> list[dict]:
    return [_game(f, n) for f in GAME_FAMILIES for n in INSTANCES]


def _holds(conds, vs) -> bool:
    for op, var, k in conds:
        x = vs[var]
        if not {"ge": x >= k, "eq": x == k, "lt": x < k}[op]:
            return False
    return True


def _sign(vec) -> str:
    neg, pos = any(x < 0 for x in vec), any(x > 0 for x in vec)
    if not neg:
        return "nonneg"
    return "negative" if not pos else "incomparable"


def game_truth(doc: dict) -> dict:
    """Explicit-state enumeration of every schedule of every class (single deviator; each action at most once)."""
    acts = doc["actions"]
    out, depth = {}, None
    for a in doc["actors"]:
        x = a["id"]
        mine = [c for c in acts if x in c["by"]]
        pays, best = [], None
        for r in range(1, len(mine) + 1):
            for seq in itertools.permutations(mine, r):
                vs = dict(doc["vars"])
                hold = {aid["id"]: {s: 0 for s in doc["assets"]} for aid in doc["actors"]}
                ok, trig = True, False
                for c in seq:
                    if not _holds(c["guard"], vs):
                        ok = False
                        break
                    for op, var, k in c["effect"]:
                        vs[var] = vs[var] + k if op == "add" else k
                    for who, d in c["flows"].items():
                        who = x if who == "caller" else who
                        for s, q in d.items():
                            hold[who][s] += q
                    trig = trig or _holds(doc["bad"], vs)
                if not ok or not trig:
                    continue
                p = _sign([hold[x][s] for s in doc["assets"]])
                pays.append(p)
                if p == "nonneg":
                    best = r if best is None else min(best, r)
        if "nonneg" in pays:
            cv = "rational"
        elif all(p == "negative" for p in pays):
            cv = "irrational"
        else:
            cv = "UNKNOWN"
        out[x] = cv
        if not a["trusted"] and best is not None:
            depth = best if depth is None else min(depth, best)
    unt = [a["id"] for a in doc["actors"] if not a["trusted"]]
    if any(out[x] == "rational" for x in unt):
        verdict = "rational"
    elif all(out[x] == "irrational" for x in unt):
        verdict = "irrational"
    else:
        verdict = "UNKNOWN"
    return {"verdict": verdict, "classes": out, "depth": depth}


# ------------------------------------------------------------------ intent controls
def _intent(family: str, wrong: bool, n: int) -> dict:
    kind = "wrong" if wrong else "right"
    name = "C" + tok(f"{family}_{kind}", n, "contract")
    head = "// SPDX-License-Identifier: UNLICENSED\npragma solidity 0.8.24;\n\n"
    if family == "bound":
        b = n
        c = b + n if wrong else b
        clause = f"@notice The fee charged is at most {b} percent of the amount."
        body = (f"contract {name} {{\n    /// {clause}\n    function fee(uint256 amount) external pure returns (uint256) {{\n"
                f"        return (amount * {c}) / 100;\n    }}\n}}\n")
        why = f"rate {c} percent against the documented bound {b}"
    elif family == "access":
        clause = "@notice Only the owner can pause the contract."
        check = "" if wrong else "        require(msg.sender == owner);\n"
        body = (f"contract {name} {{\n    address public owner;\n    bool public stopped;\n\n"
                f"    constructor() {{\n        owner = msg.sender;\n    }}\n\n    /// {clause}\n"
                f"    function pause() external {{\n{check}        stopped = true;\n    }}\n}}\n")
        why = "pause has no owner check" if wrong else "pause checks the owner"
    elif family == "monotone":
        clause = "@notice The count never decreases."
        step = (f"        if (count > {n}) {{\n            count -= 1;\n        }} else {{\n            count += {n + 1};\n"
                f"        }}\n") if wrong else f"        count += {n};\n"
        body = (f"contract {name} {{\n    uint256 public count;\n\n    /// {clause}\n    function step() external {{\n"
                f"{step}    }}\n}}\n")
        why = "step decreases the count once it exceeds the threshold" if wrong else "step only adds"
    else:
        raise ValueError(family)
    return {"id": f"i_{family}_{kind}_{n}", "family": family, "file": f"{name}.sol", "source": head + body,
            "clause": clause, "truth": {"obstruction": wrong, "why": why}}


def intent_controls() -> list[dict]:
    return [_intent(f, w, n) for f in INTENT_FAMILIES for w in (True, False) for n in INSTANCES]


# ------------------------------------------------------------------ census (definitions.L10.census)
MARKERS = ("must not", "can not", "at most", "at least", "not allowed", "must", "shall", "should", "only", "cannot",
           "never", "always", "revert", "reverts", "reverted", "require", "requires", "required", "ensure", "ensures",
           "guarantee", "guarantees", "exactly", "invariant", "forbidden")
_TAG = re.compile(r"^@[A-Za-z][A-Za-z:-]*")
_GO_DECL = re.compile(r"^\s*(func|type|var|const)\b")


def _normative(s: str) -> bool:
    low = s.lower()
    for m in MARKERS:
        if re.search(r"(?<![a-z])" + re.escape(m) + r"(?![a-z])", low):
            return True
    return False


def _comments(path: str, text: str):
    """[(first line, last line, [cleaned lines])] of a file's doc comments."""
    lines = text.split("\n")
    out = []
    if path.endswith(".sol"):
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("///"):
                j = i
                while j < len(lines) and lines[j].strip().startswith("///"):
                    j += 1
                out.append((i + 1, j, [ln.strip()[3:].strip() for ln in lines[i:j]]))
                i = j
            elif s.startswith("/**"):
                j = i
                while "*/" not in lines[j][(lines[j].index("/**") + 3) if j == i else 0:] and j + 1 < len(lines):
                    j += 1
                body = []
                for k in range(i, j + 1):
                    t = lines[k].strip()
                    if k == i:
                        t = t[t.index("/**") + 3:]
                    if "*/" in t:
                        t = t[:t.index("*/")]
                    t = t.strip()
                    if t.startswith("*"):
                        t = t[1:]
                    body.append(t.strip())
                out.append((i + 1, j + 1, body))
                i = j + 1
            else:
                i += 1
    elif path.endswith(".go"):
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith("//"):
                j = i
                while j < len(lines) and lines[j].strip().startswith("//"):
                    j += 1
                if j < len(lines) and _GO_DECL.match(lines[j]):
                    out.append((i + 1, j, [ln.strip()[2:].strip() for ln in lines[i:j]]))
                i = j
            else:
                i += 1
    return out


def _sentences(seg: str) -> list[str]:
    parts, cur = [], ""
    for idx, ch in enumerate(seg):
        cur += ch
        if ch in ".;!?" and (idx + 1 == len(seg) or seg[idx + 1].isspace()):
            parts.append(cur.strip())
            cur = ""
    if cur.strip():
        parts.append(cur.strip())
    return [p for p in parts if p]


def census_of(path: str, text: str) -> list[dict]:
    out = []
    for first, last, body in _comments(path, text):
        segs, cur = [], []
        for ln in body:
            if not ln or _TAG.match(ln):
                if cur:
                    segs.append(cur)
                cur = [ln] if ln else []
            else:
                cur.append(ln)
        if cur:
            segs.append(cur)
        for seg in segs:
            joined = re.sub(r"\s+", " ", " ".join(seg)).strip()
            m = _TAG.match(joined)
            tag = m.group(0) if m else None   # the segment's tag, on each of its sentences
            for s in _sentences(joined):
                if _normative(s):
                    cid = hashlib.sha256(f"{path}:{first}:{s}".encode()).hexdigest()[:16]
                    out.append({"id": cid, "file": path, "lines": [first, last], "text": s, "tag": tag})
    return out


SPAN = re.compile(r"([A-Za-z0-9_./-]+\.(?:sol|go)):\d+")


def scope_paths(fact_texts: list[str]) -> list[str]:
    return sorted({m for t in fact_texts for m in SPAN.findall(t)})


# ------------------------------------------------------------------ L6 reference
def _checked(ev) -> bool:
    return isinstance(ev, dict) and ev.get("marker") == CHECKED and ev.get("law_present") is True


def _finding_verdict(classes) -> str:
    unt = [c["verdict"] for c in classes if not c["trusted"]]
    if any(v == "rational" for v in unt):
        return "rational"
    if unt and all(v == "irrational" for v in unt):
        return "irrational"
    if unt and all(v in ("irrational", "irrational_bounded") for v in unt):
        return "irrational_bounded"
    return "UNKNOWN"


def validate_game(rec: dict, expect: dict) -> list[str]:
    """expect: {"classes": {id: trusted}, "witness_length": n, "value_flows_sha256": h}. The rules V1-V8 it fails."""
    bad = []
    if not _checked(rec.get("evidence")):
        bad.append("V1")
    cls = rec.get("classes") or []
    if sorted(c["class"] for c in cls) != sorted(expect["classes"]):
        bad.append("V2")
    elif any(c["trusted"] != expect["classes"][c["class"]] for c in cls):
        bad.append("V3")
    if rec.get("witness_length") != expect["witness_length"] or rec.get("horizon", -1) < expect["witness_length"]:
        bad.append("V4")
    if rec.get("witness_in_space") is not True:
        bad.append("V5")
    want = _finding_verdict(cls) if cls else "UNKNOWN"
    if rec.get("verdict") != want:
        bad.append("V6")
    if rec.get("value_flows_sha256") != expect["value_flows_sha256"]:
        bad.append("V8")
    for c in cls:
        if c["verdict"] == "rational" and (c.get("payoff") != "nonneg" or not c.get("strategy_length")
                                           or not 1 <= c["strategy_length"] <= rec.get("horizon", 0)):
            bad.append("V7")
            break
    return bad


def scored(records: list[dict], ids: list[str], expect: dict) -> tuple[dict, dict]:
    """({id: validated verdict}, {id: [rules]}) over the population ids."""
    by = {}
    for r in records:
        by.setdefault(r["finding"], []).append(r)
    out, invalid = {}, {}
    for i in ids:
        rs = by.get(i, [])
        if len(rs) != 1:
            out[i] = "UNKNOWN"
            if len(rs) > 1:
                invalid[i] = ["one_record"]
            continue
        rules = validate_game(rs[0], expect[i])
        if rules:
            invalid[i] = rules
            out[i] = "UNKNOWN"
        else:
            out[i] = rs[0]["verdict"]
    return out, invalid


def _acc(verdicts: dict, truth: dict) -> dict:
    items = sorted(truth)
    norm = lambda v: "irrational" if v == "irrational_bounded" else v  # noqa: E731
    dec = [i for i in items if verdicts.get(i, "UNKNOWN") in DECIDED6]
    cd = sum(1 for i in dec if norm(verdicts[i]) == truth[i])
    cs = sum(1 for i in items if norm(verdicts.get(i, "UNKNOWN")) == truth[i])
    counts = {}
    for i in items:
        counts[truth[i]] = counts.get(truth[i], 0) + 1
    maj = max(counts.values()) if counts else 0
    return {
        "items": len(items),
        "decided_accuracy": prop(cd, len(dec)),
        "strict_accuracy": prop(cs, len(items)),
        "majority_baseline": maj,
        "strict_correct": cs,
        "beats_majority": cs > maj,
        "false_rational": sorted(i for i in items if truth[i] == "irrational" and verdicts.get(i) == "rational"),
        "false_irrational": sorted(i for i in items if truth[i] == "rational"
                                   and verdicts.get(i) in ("irrational", "irrational_bounded")),
        "decided_on_unknown": sorted(i for i in items if truth[i] == "UNKNOWN" and verdicts.get(i) in DECIDED6),
    }


def l6(inputs: dict) -> dict:
    """inputs: {"population": [ids], "expect": {id: expect}, "records": [game records],
    "controls": [control docs], "corpus_truth": {id: truth} or None, "corpus_expect": {id: expect}}."""
    pop = sorted(inputs["population"])
    v, inv = scored([r for r in inputs["records"] if r["kind"] == "target"], pop, inputs["expect"])
    dec = [i for i in pop if v[i] in DECIDED6]
    decu = [i for i in pop if v[i] in ("rational", "irrational")]
    ctl = {c["id"]: c for c in inputs["controls"]}
    cexp = {cid: {"classes": {a["id"]: a["trusted"] for a in c["actors"]}, "witness_length": len(c["witness"]),
                  "value_flows_sha256": flows_sha256(c)} for cid, c in ctl.items()}
    cv, cinv = scored([r for r in inputs["records"] if r["kind"] == "control"], sorted(ctl), cexp)
    out = {
        "population": len(pop),
        "decided": prop(len(dec), len(pop)),
        "decided_unbounded": prop(len(decu), len(pop)),
        "verdicts": {k: sum(1 for i in pop if v[i] == k) for k in DECIDED6 + ("UNKNOWN",)},
        "invalid": {i: inv[i] for i in sorted(inv)},
        "controls": dict(_acc(cv, {cid: c["truth"]["verdict"] for cid, c in ctl.items()}),
                         invalid={i: cinv[i] for i in sorted(cinv)}),
    }
    ct = inputs.get("corpus_truth")
    if ct is None:
        out["corpus"] = {"label": "not_measured", "reason": "no corpus truth file"}
    else:
        items = sorted(i for i, t in ct.items() if t in ("rational", "irrational"))
        kv, kinv = scored([r for r in inputs["records"] if r["kind"] == "corpus"], items, inputs["corpus_expect"])
        out["corpus"] = dict(_acc(kv, {i: ct[i] for i in items}), invalid={i: kinv[i] for i in sorted(kinv)})
    c = out["controls"]
    lab_pop = label(len(pop))
    th = {
        "decided": judge(out["decided"]["value"], ">=", 0.5, lab_pop),
        "controls_decided_accuracy": judge(c["decided_accuracy"]["value"], ">=", 0.8,
                                           label(c["decided_accuracy"]["denominator"])),
        "controls_strict_accuracy": judge(c["strict_accuracy"]["value"], ">=", 0.75, label(c["items"])),
        "controls_beats_majority": judge(c["strict_correct"], ">", c["majority_baseline"], label(c["items"])),
        "false_rational": judge(len(c["false_rational"]) + len(out["corpus"].get("false_rational", [])), "==", 0,
                                label(c["items"])),
        "false_irrational": judge(len(c["false_irrational"]), "==", 0, label(c["items"])),
    }
    if "decided_accuracy" in out["corpus"]:
        d = out["corpus"]["decided_accuracy"]
        th["corpus_decided_accuracy"] = judge(d["value"], ">=", 0.8, label(d["denominator"]))
    else:
        th["corpus_decided_accuracy"] = "not_measured"
    out["thresholds"] = th
    out["overall"] = overall(th)
    return out


# ------------------------------------------------------------------ L9 reference
def env_premises(rec: dict, cls: dict) -> list[tuple]:
    """[(category, form, id)] of a record (definitions.L9.environment_premises)."""
    out = set()
    ids = list(rec.get("ledger_assumptions") or []) + list(rec.get("model_assumptions") or [])
    for i in ids:
        i = i if isinstance(i, str) else json.dumps(i, sort_keys=True)
        e = cls["ids"].get(i)
        if e is None:
            e = next((p for p in cls["id_patterns"] if re.search(p["pattern"], i)), None)
        if e is None:
            out.add(("unclassified", "axiom", i))
        elif e["environment"]:
            for c in e["categories"]:
                out.add((c, e["form"], i))
    for p in rec.get("premises") or []:
        for pre, e in cls["premise_prefixes"].items():
            if isinstance(p, str) and p.startswith(pre) and e["environment"]:
                for c in e["categories"]:
                    out.add((c, e["form"], p))
    for p in (rec.get("environment") or {}).get("premises", []):
        out.add((p["category"], p["form"], p["id"] if p["form"] != "module" else "module:" + str(p.get("module"))))
    return sorted(out)


def _predict(fam: str, params: dict, o: dict):
    if fam == "window":
        return (o["q"] - o["t"]) <= params["W"]
    if fam == "finality_depth":
        return True if o["head"] - o["t"] >= params["d"] else None
    if fam == "availability":
        return bool(o["committed"])
    return None


def validate_module(m: dict, sets: dict, pinned: dict) -> dict:
    pnames = set(m["parameters"])
    adm, rules = [], {}
    r1 = True
    for s in m["observations"]:
        os_ = sets.get(s)
        if os_ is None or set(os_["reads"]) & pnames or os_["producer"] in set(m.get("producers") or []):
            r1 = False
        else:
            adm.append(s)
    obs = []
    for s in sorted(adm):
        for pos, o in enumerate(sets[s]["items"]):
            p = _predict(m["family"], m["parameters"], o)
            if p is not None:
                obs.append((o["t"], s, pos, p, bool(o["observed"])))
    obs.sort()
    n = len(obs)
    size = n // K
    slices = []
    for k in range(K):
        lo = k * size
        hi = n if k == K - 1 else (k + 1) * size
        part = obs[lo:hi]
        slices.append({"n": len(part), "accuracy": prop(sum(1 for x in part if x[3] == x[4]), len(part))["value"]})
    held = slices[1:] if m["provenance"] == "fit_slice_0" else slices
    rules["R1"] = r1
    rules["R2"] = m["provenance"] in ("premise", "fit_slice_0") and n >= K
    rules["R3"] = all(s["n"] >= SLICE_MIN_N for s in held)
    rules["R4"] = all(s["accuracy"] is not None and s["accuracy"] >= SLICE_ACCURACY for s in held)
    rules["R5"] = sum(1 for x in obs if x[4]) >= MIN_N and sum(1 for x in obs if not x[4]) >= MIN_N
    rules["R6"] = m["id"] in pinned and pinned[m["id"]] == m["parameters"]
    worst = min((s["accuracy"] for s in held if s["accuracy"] is not None), default=None)
    return {"admissible": sorted(adm), "slices": slices, "worst": worst, "rules": rules,
            "validated": all(rules.values())}


def l9(inputs: dict) -> dict:
    """inputs: {"records": [result records], "classification": doc, "modules": [module records],
    "observation_sets": [sets], "sensitivity": [pairs], "base_dependent": [law ids]}."""
    cls = inputs["classification"]
    sets = {s["set"]: s for s in inputs["observation_sets"]}
    pinned = inputs.get("pinned_parameters") or {}
    mods = {m["id"]: dict(validate_module(m, sets, pinned), category=m["category"]) for m in inputs["modules"]}
    dep, cov, cats = [], [], {}
    unclassified = set()
    for r in sorted(inputs["records"], key=lambda r: r["law_id"]):
        E = env_premises(r, cls)
        if not E:
            continue
        dep.append(r["law_id"])
        ok = all(f == "module" and i.startswith("module:") and mods.get(i[7:], {}).get("validated")
                 and mods[i[7:]]["category"] == c for c, f, i in E)
        if ok:
            cov.append(r["law_id"])
        for c, f, i in E:
            cats.setdefault(c, {"dependent": set(), "covered": set(), "forms": {}})
            cats[c]["dependent"].add(r["law_id"])
            cats[c]["forms"][f] = cats[c]["forms"].get(f, 0) + 1
            if ok:
                cats[c]["covered"].add(r["law_id"])
            if c == "unclassified":
                unclassified.add(i)
    base = sorted(inputs["base_dependent"])
    base_cov = [i for i in base if i in set(cov)]
    dropped = sorted(set(base) - set(dep))
    head = sorted(set(dep) | set(dropped))
    new = [i for i in dep if i not in set(base)]
    sens = {"counted": [], "unreplayed": [], "to_unknown": []}
    for p in sorted(inputs["sensitivity"], key=lambda p: (p["law"], p["module"])):
        if p["status_axiom"] == p["status_module"]:
            continue
        if p["status_module"] == "UNKNOWN":
            sens["to_unknown"].append(p["law"])
        elif _checked(p.get("evidence")) and p["replay"] == "passed":
            sens["counted"].append(p["law"])
        else:
            sens["unreplayed"].append(p["law"])
    validated_cats = sorted({m["category"] for m in mods.values() if m["validated"]})
    out = {
        "coverage": prop(len(cov), len(head)),
        "base_coverage": prop(len(base_cov), len(base)),
        "new_coverage": prop(sum(1 for i in new if i in set(cov)), len(new)),
        "base_dropped": dropped,
        "by_category": {c: {"dependent": len(v["dependent"]), "covered": len(v["covered"]),
                            "forms": dict(sorted(v["forms"].items()))} for c, v in sorted(cats.items())},
        "unclassified": sorted(unclassified),
        "modules": {k: mods[k] for k in sorted(mods)},
        "validated_categories": validated_cats,
        "sensitivity": dict(sens, count=len(sens["counted"])),
    }
    out["thresholds"] = {
        "coverage": judge(out["coverage"]["value"], ">=", 0.25, label(len(head))),
        "base_coverage": judge(out["base_coverage"]["value"], ">=", 0.1, label(len(base))),
        "validated_categories": "meets" if validated_cats == ["da", "fetcher", "l1_chain"] else "misses",
        "sensitivity_unreplayed": judge(len(sens["unreplayed"]), "==", 0,
                                        "measured" if sens["counted"] or sens["unreplayed"] else "not_measured"),
    }
    out["overall"] = overall(out["thresholds"])
    return out


# ------------------------------------------------------------------ L10 reference
def _meets(a, b) -> bool:
    return a["file"] == b["file"] and a["lines"][0] <= b["lines"][1] and b["lines"][0] <= a["lines"][1]


def l10(inputs: dict) -> dict:
    """inputs: {"census": [clauses], "atomized": [atom clauses], "laws": [intent laws], "controls": [intent controls]}."""
    census, atoms = inputs["census"], {a["id"]: a for a in inputs["atomized"]}
    laws = inputs["laws"]
    count = {}
    for lw in laws:
        count[lw["law"]] = count.get(lw["law"], 0) + 1

    def w1(lw):
        return lw["status"] in ("PROVED", "REFUTED") and _checked(lw["evidence"])

    def w2(lw):
        rv = lw["review"]
        return rv["verdict"] == "faithful" and rv["reviewer"] != rv["compiler"]

    def w3(lw):
        return bool(lw["clauses"]) and all(c in atoms for c in lw["clauses"])

    good = [lw for lw in laws if count[lw["law"]] == 1 and w1(lw) and w2(lw) and w3(lw)]
    comp = [lw for lw in laws if count[lw["law"]] == 1 and w3(lw)]

    def covered(ls):
        return [c for c in census if any(_meets(atoms[a], c) for lw in ls for a in lw["clauses"])]

    cov, ccov = covered(good), covered(comp)
    prec = [a for a in atoms.values() if any(_meets(a, c) for c in census)]
    rec = [c for c in census if any(_meets(a, c) for a in atoms.values())]
    rev = [lw for lw in laws if w2(lw)]
    ctl = inputs["controls"]
    wrong = [c["id"] for c in ctl if c["truth"]["obstruction"]]
    right = [c["id"] for c in ctl if not c["truth"]["obstruction"]]

    def obstructed(cid):
        ls = [lw for lw in laws if lw.get("control") == cid]
        return len(ls) == 1 and ls[0]["status"] == "REFUTED" and w1(ls[0]) and w2(ls[0])

    hit = [c for c in wrong if obstructed(c)]
    false = sorted(c for c in right if obstructed(c))
    out = {
        "census": len(census),
        "coverage": prop(len(cov), len(census)),
        "compiled_coverage": prop(len(ccov), len(census)),
        "precision": prop(len(prec), len(atoms)),
        "recall": prop(len(rec), len(census)),
        "review": prop(len(rev), len(laws)),
        "control_recall": prop(len(hit), len(wrong)),
        "false_obstruction": false,
    }
    out["thresholds"] = {
        "coverage": judge(out["coverage"]["value"], ">=", 0.3, label(len(census))),
        "precision": judge(out["precision"]["value"], ">=", 0.8, label(len(atoms))),
        "review": judge(out["review"]["value"], ">=", 0.9, label(len(laws))),
        "control_recall": judge(out["control_recall"]["value"], ">=", 0.75, label(len(wrong))),
        "false_obstruction": judge(len(false), "==", 0, label(len(right))),
    }
    out["overall"] = overall(out["thresholds"])
    return out


# ------------------------------------------------------------------ fixtures (rule F1)
def _ev(ok: bool = True) -> dict:
    return {"law": "fixture", "marker": CHECKED if ok else "PROOF FAILED", "law_present": ok}


SHA0 = "0" * 64


def _grec(fid, kind, verdict, classes, horizon=4, wl=2, space=True, ok=True) -> dict:
    return {"finding": fid, "kind": kind, "verdict": verdict, "classes": classes, "horizon": horizon,
            "witness_length": wl, "witness_in_space": space, "evidence": _ev(ok), "value_flows_sha256": SHA0}


def _cls(cid, trusted, verdict, payoff=None, length=None) -> dict:
    return {"class": cid, "trusted": trusted, "verdict": verdict, "payoff": payoff, "strategy_length": length}


def engine_records(controls: list[dict], engine: str) -> list[dict]:
    """Game records an engine would write for the controls. engines: honest (the truth), rational (every finding
    rational), irrational (every finding irrational), bounded (search up to the horizon only, then
    irrational_bounded), trigger_payoff (payoff read when the predicate first holds, not at the end)."""
    out = []
    for c in controls:
        t = c["truth"]
        cl = []
        for a in c["actors"]:
            tv = t["classes"][a["id"]]
            if engine == "honest":
                v = tv
            elif engine == "rational":
                v = "rational"
            elif engine == "irrational":
                v = "irrational"
            elif engine == "bounded":
                v = tv if (tv != "rational" or a["trusted"] or (t["depth"] or 0) <= c["horizon"]) else \
                    "irrational_bounded"
            elif engine == "trigger_payoff":
                v = "irrational" if (c["family"] == "recoup" and not a["trusted"]) else tv
            else:
                raise ValueError(engine)
            pay = {"rational": "nonneg", "irrational": "negative", "irrational_bounded": "negative"}.get(v)
            cl.append(_cls(a["id"], a["trusted"], v, pay, 1 if v == "rational" else None))
        r = _grec(c["id"], "control", _finding_verdict(cl), cl, horizon=c["horizon"], wl=len(c["witness"]))
        r["value_flows_sha256"] = flows_sha256(c)
        out.append(r)
    return out


def fixture_l6(engine: str = "honest") -> dict:
    """Eight target findings f1..f8 (classes cA trusted, cB untrusted, witness length 2), one per validity case,
    plus the game controls with an engine's records, and a corpus truth of four items."""
    expect = {f"f{i}": {"classes": {"cA": True, "cB": False}, "witness_length": 2, "value_flows_sha256": SHA0}
              for i in range(1, 10)}
    R = lambda v, p=None, n=None: [_cls("cA", True, "rational", "nonneg", 1), _cls("cB", False, v, p, n)]  # noqa
    recs = [
        _grec("f1", "target", "rational", R("rational", "nonneg", 2)),
        _grec("f2", "target", "irrational", R("irrational", "negative")),
        _grec("f3", "target", "irrational_bounded", R("irrational_bounded", "negative")),
        _grec("f4", "target", "rational", R("rational", "nonneg", 2), ok=False),          # V1
        _grec("f5", "target", "rational", R("rational", "nonneg", 1), horizon=1),         # V4
        _grec("f6", "target", "irrational", R("irrational", "negative")),                 # one_record
        _grec("f6", "target", "rational", R("rational", "nonneg", 2)),
        _grec("f7", "target", "rational", R("irrational", "negative")),                   # V6
        dict(_grec("f8", "target", "rational", R("rational", "nonneg", 2)), value_flows_sha256="1" * 64),  # V8
        # f9: no record
    ]
    controls = game_controls()
    recs += engine_records(controls, engine)
    corpus_expect = {f"c{i}": {"classes": {"cA": True, "cB": False}, "witness_length": 1, "value_flows_sha256": SHA0}
                     for i in range(1, 5)}
    corpus_truth = {"c1": "rational", "c2": "rational", "c3": "irrational", "c4": "undocumented"}
    recs += [_grec("c1", "corpus", "rational", R("rational", "nonneg", 1), wl=1),
             _grec("c2", "corpus", "irrational", R("irrational", "negative"), wl=1),
             _grec("c3", "corpus", "rational", R("rational", "nonneg", 1), wl=1)]
    return {"population": sorted(expect), "expect": expect, "records": recs, "controls": controls,
            "corpus_truth": corpus_truth, "corpus_expect": corpus_expect}


def fixture_l9(classification: dict, variant: str = "honest") -> dict:
    """Records r1..r6, an observation history for a window module, and sensitivity pairs. variants: honest;
    circular (the observations read the module's own parameter: R1); one_class (a history of one observed class: R5);
    unpinned (the module's parameter differs from the one the measuring key pinned, as a fit to the evaluation data
    would: R6); drop (r2 loses its environment premise: it stays in both coverage denominators, uncovered)."""
    recs = [
        {"law_id": "r1", "ledger_assumptions": ["A-env"], "premises": []},
        {"law_id": "r2", "ledger_assumptions": [], "premises": ["env:block.timestamp >= 1"]},
        {"law_id": "r3", "ledger_assumptions": ["A-reach", "oracle-verifier"], "premises": ["cf:keccak256"]},
        {"law_id": "r4", "ledger_assumptions": ["A-new-thing"], "premises": []},
        {"law_id": "r5", "ledger_assumptions": [], "premises": [],
         "environment": {"premises": [{"id": "m_win", "category": "da", "form": "module", "module": "m_win"}]}},
        {"law_id": "r6", "ledger_assumptions": [], "premises": [],
         "environment": {"premises": [{"id": "m_win", "category": "da", "form": "module", "module": "m_win"},
                                      {"id": "fetch", "category": "fetcher", "form": "axiom"}]}},
    ]
    if variant == "drop":
        recs[1] = {"law_id": "r2", "ledger_assumptions": [], "premises": []}
    W = 100
    items = []
    for i in range(320):
        t = 1000 + 7 * i
        q = t + (60 if i % 2 == 0 else 160)
        obs = (q - t) <= W
        if variant == "one_class":
            q, obs = t + 60, True
        if i % 53 == 0 and variant != "one_class":
            obs = not obs                                   # a few real exceptions
        items.append({"t": t, "q": q, "observed": obs})
    sets = [{"set": "probes", "producer": "probe-tool", "reads": ["W"] if variant == "circular" else [],
             "items": items}]
    mod = {"id": "m_win", "family": "window", "category": "da", "parameters": {"W": W}, "provenance": "premise",
           "citation": "fixture", "producers": ["engine"], "observations": ["probes"]}
    sens = [
        {"law": "r1", "module": "m_win", "status_axiom": "REFUTED", "status_module": "PROVED", "replay": "passed",
         "evidence": _ev()},
        {"law": "r2", "module": "m_win", "status_axiom": "PROVED", "status_module": "REFUTED", "replay": "absent",
         "evidence": _ev()},
        {"law": "r3", "module": "m_win", "status_axiom": "PROVED", "status_module": "UNKNOWN", "replay": "absent",
         "evidence": _ev(False)},
        {"law": "r5", "module": "m_win", "status_axiom": "UNKNOWN", "status_module": "UNKNOWN", "replay": "absent",
         "evidence": _ev(False)},
    ]
    pinned = {"m_win": {"W": W if variant != "unpinned" else W + 1}}
    return {"records": recs, "classification": classification, "modules": [mod], "observation_sets": sets,
            "sensitivity": sens, "base_dependent": ["r1", "r2"], "pinned_parameters": pinned}


def fixture_l10(variant: str = "honest") -> dict:
    """The census of the intent controls' sources plus one extra file, atomized clauses and intent laws.
    variants: honest; few_atoms (the atomizer emits one clause only: the census denominator does not move);
    self_review (the compiler reviews its own laws); weak (every control law PROVED: a weak transcription)."""
    controls = intent_controls()
    census = []
    for c in controls:
        census += census_of(c["file"], c["source"])
    extra = ("pragma solidity 0.8.24;\n/// @notice Anyone may call this.\n/// @dev Reverts when the amount is zero.\n"
             "contract X {\n}\n")
    census += census_of("X.sol", extra)
    atoms = [{"id": "a_" + c["id"], "file": c["file"], "lines": c["lines"], "text": c["text"]} for c in census]
    if variant == "few_atoms":
        atoms = atoms[:1]
    laws = []
    for c in controls:
        ok_atoms = [a["id"] for a in atoms if a["file"] == c["file"]]
        if not ok_atoms:
            continue
        status = "REFUTED" if c["truth"]["obstruction"] else "PROVED"
        if variant == "weak":
            status = "PROVED"
        reviewer = "compiler-1" if variant == "self_review" else "reviewer-1"
        laws.append({"law": "L_intent_" + c["id"], "clauses": ok_atoms, "status": status, "evidence": _ev(),
                     "control": c["id"], "review": {"reviewer": reviewer, "compiler": "compiler-1",
                                                    "verdict": "faithful"}})
    return {"census": census, "atomized": atoms, "laws": laws, "controls": controls}


def fixture_l6_clean() -> dict:
    """Every validity rule passes, the honest engine on the controls, and five correct corpus items: overall meets."""
    expect = {f"f{i}": {"classes": {"cA": True, "cB": False}, "witness_length": 2, "value_flows_sha256": SHA0}
              for i in range(1, 7)}
    R = lambda v, p=None, n=None: [_cls("cA", True, "irrational", "negative"), _cls("cB", False, v, p, n)]  # noqa
    recs = [_grec(f"f{i}", "target", "rational", R("rational", "nonneg", 2)) for i in (1, 2, 3)]
    recs += [_grec(f"f{i}", "target", "irrational", R("irrational", "negative")) for i in (4, 5)]
    recs += engine_records(game_controls(), "honest")
    corpus_expect = {f"c{i}": {"classes": {"cA": True, "cB": False}, "witness_length": 1, "value_flows_sha256": SHA0}
                     for i in range(1, 6)}
    corpus_truth = {"c1": "rational", "c2": "rational", "c3": "irrational", "c4": "irrational", "c5": "rational"}
    for i, t in sorted(corpus_truth.items()):
        recs.append(_grec(i, "corpus", t, R(t, "nonneg" if t == "rational" else "negative",
                                            1 if t == "rational" else None), wl=1))
    return {"population": sorted(expect), "expect": expect, "records": recs, "controls": game_controls(),
            "corpus_truth": corpus_truth, "corpus_expect": corpus_expect}


def _history(fam: str, n: int = 400) -> list[dict]:
    items = []
    for i in range(n):
        t = 1000 + 7 * i
        flip = i % 61 == 0
        if fam == "window":
            q = t + (60 if i % 2 == 0 else 160)
            items.append({"t": t, "q": q, "observed": ((q - t) <= 100) != flip})
        elif fam == "finality_depth":
            head = t + (70 if i % 5 else 10)               # every fifth block is too recent to be scored
            items.append({"t": t, "head": head, "observed": i % 41 != 0})
        else:
            c = i % 2 == 0
            items.append({"t": t, "committed": c, "observed": c != flip})
    return items


def fixture_l9_clean(classification: dict) -> dict:
    """Three validated modules (da window, l1_chain finality depth, fetcher availability), ten records of which six
    are base laws; five records are covered (two of them base laws), and one sensitivity change is replayed."""
    fams = {"m_da": ("window", "da", {"W": 100}), "m_l1": ("finality_depth", "l1_chain", {"d": 64}),
            "m_fe": ("availability", "fetcher", {})}
    mods, sets, pinned = [], [], {}
    for mid, (fam, cat, prm) in sorted(fams.items()):
        sets.append({"set": "h_" + mid, "producer": "probe-tool", "reads": [], "items": _history(fam)})
        mods.append({"id": mid, "family": fam, "category": cat, "parameters": prm, "provenance": "premise",
                     "citation": "fixture", "producers": ["engine"], "observations": ["h_" + mid]})
        pinned[mid] = prm
    mp = lambda mid, cat: {"id": mid, "category": cat, "form": "module", "module": mid}  # noqa: E731
    recs = []
    for i in range(1, 11):
        if i in (1, 2, 7, 8, 9, 10):
            env = {"premises": [mp("m_da", "da"), mp("m_l1", "l1_chain")] if i % 2 else [mp("m_fe", "fetcher")]}
            recs.append({"law_id": f"r{i}", "ledger_assumptions": ["A-reach"], "premises": [], "environment": env})
        else:
            recs.append({"law_id": f"r{i}", "ledger_assumptions": ["A-env"], "premises": []})
    sens = [{"law": "r1", "module": "m_da", "status_axiom": "REFUTED", "status_module": "PROVED", "replay": "passed",
             "evidence": _ev()}]
    return {"records": recs, "classification": classification, "modules": mods, "observation_sets": sets,
            "sensitivity": sens, "base_dependent": ["r1", "r2", "r3", "r4", "r5", "r6"], "pinned_parameters": pinned}
