"""I48 instrument, fixed at the I48 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m4/test_eval_corpus.py: rules C0-C7 (the corpus), N0-N3 (the renaming) and K0-K4
(the controls). This module writes those rules out a second time, independently of holon/, so that the tests can decide
what holon, the collecting agents and the labelling agents must have written:

- select(candidates, protocol): rule C4, the corpus selection (round robin) as a function of spec/eval/candidates.json;
- kappa(a, b, categories): rule C6, Cohen's kappa with observed and chance agreement, the confusion table and Cohen's
  large-sample standard error; final_label(a, b, adjudicated): rule C5;
- render_prompt(role, entry, diff, labels), cap_diff(diff), parse_response(text), label_ok(obj), attempt_outcome(cli)
  and retry_follows(outcomes): rule C5's prompts, the label a response gives, the outcome of one attempt and the retry
  rule over a prompt's attempts;
- controls(plan) and expected_documents(control, plan): rules K1-K2, the controls and their exact documents;
- initial, step, observer, run_trace, enumerate_machine, shortest, houdini_constants, cti: rules K3-K4, an
  explicit-state interpreter of the small holon-facts/0.2 subset the controls use, independent of holon's generators;
- prefilter, names_repo, ghsa_items_from, geth_items_from, folder_items_from, snapshot_rule, named_commits,
  description_ok (pure, over synthetic or snapshot inputs) and ghsa_index, geth_items, folder_items, index_items,
  index_docs, named_fix (over the pinned snapshots): rule C2's index item lists, fix commits and descriptions;
- repo_cache, ensure_commit, on_branch, advisory_snapshot, commit_info, fix_diff, changed_old_lines
  (old_lines_from_diff), sparse_checkout: rules C2-C3 and the inputs of N3 and P4, from clones of the public
  repositories in the instrument's own cache (never holon's);
- go_ast, go_comments, map_go_ast, go_facts (tests_m4/fixtures/goast/main.go), sol_ast, sol_lex, sol_tokens,
  map_sol_ast, sol_facts, words, upper_initial, new_names, reserved: rules N1-N3.

Inputs only: the frozen sidecars spec/M4/lib/*.json and *.md, the pins below (SOLC_SHA256, GO_VERSION; config/holon.json
may only name a candidate path of solc), and public git repositories. Nothing here imports holon/.
"""
from __future__ import annotations

import atexit
import fnmatch
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import unicodedata
import urllib.parse
from collections import Counter, deque
from datetime import datetime, timezone
from itertools import product
from pathlib import Path, PurePosixPath

from tests_m4 import _m4

ROOT = _m4.ROOT
LIB = ROOT / "spec" / "M4" / "lib"
PROTOCOL = LIB / "corpus_protocol.json"
RULE_SHEET = LIB / "rule_sheet.json"
CONTROLS_PLAN = LIB / "controls_plan.json"
RESERVED = LIB / "rename_reserved.json"
LABELLER_PROMPT = LIB / "labeller_prompt.md"
ADJUDICATOR_PROMPT = LIB / "adjudicator_prompt.md"
EVAL = ROOT / "spec" / "eval"
CACHE = Path.home() / ".holon" / "eval" / "instrument-repos"   # the instrument's own clones (never holon's cache)

# The pins of the parsers the instrument runs (MJ2): fixed here, never read from config/holon.json.
SOLC_SHA256 = "fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f"   # solc 0.8.24, linux-amd64
GO_VERSION = "go version go1.24.7 linux/amd64"
DIFF_CAP = 60000   # rule C5: the most characters of fix diff a prompt holds (whole lines)
LABEL_KEYS = ("justification", "primary", "secondary", "subform")
ADVISORY_DB = "https://github.com/github/advisory-database"
ADVISORY_DIRS = ("advisories/github-reviewed/", "advisories/unreviewed/")
# Per-process caches, filled at run time (test_instruments_are_the_preregistered_ones compares every other constant).
RUNTIME_STATE = ("_ADB", "_GOAST", "_REACH")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dumps(obj) -> str:
    """The repo's JSON file format (CLI rule): json.dumps(obj, indent=2, sort_keys=True) + newline."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------------------------- rule C4: selection
def system_of(protocol: dict, sid: str) -> dict:
    return next(s for s in protocol["systems"] if s["id"] == sid)


def _newest_first(c: dict) -> tuple:
    return (tuple(-int(x) for x in re.findall(r"\d+", c["fix_date"])), c["fix_commit"], c["id"])


def select(candidates: list[dict], protocol: dict) -> list[tuple[str, str | None, str | None]]:
    """Rule C4 over the candidates' eligibility. Returns (candidate id, entry id or None, reason): first the included
    candidates in inclusion order, then the other eligible ones (system order, newest fix first), then the ineligible
    ones in id order with their own reason.

    Round robin: rounds visit the systems in the protocol's order; in each round every system with fewer than
    max_per_system entries includes its newest eligible candidate not yet included (fix_date newest first, then
    fix_commit, then id), until n entries are included or no system has one left. Included candidates get c01, c02, ...
    in inclusion order. An eligible candidate left out is cap_reached when its system has max_per_system entries, else
    past_n."""
    order = [s["id"] for s in protocol["systems"]]
    stray = sorted({c["system"] for c in candidates if c["eligible"]} - set(order))
    if stray:
        raise ValueError(f"eligible candidates of systems outside the protocol: {stray}")
    queues = {sid: sorted((c for c in candidates if c["eligible"] and c["system"] == sid), key=_newest_first)
              for sid in order}
    per, out, n, progress = Counter(), [], 0, True
    while n < protocol["n"] and progress:
        progress = False
        for sid in order:
            if n >= protocol["n"]:
                break
            if queues[sid] and per[sid] < protocol["max_per_system"]:
                c = queues[sid].pop(0)
                n += 1
                per[sid] += 1
                out.append((c["id"], f"c{n:02d}", None))
                progress = True
    for sid in order:
        for c in queues[sid]:
            out.append((c["id"], None, "cap_reached" if per[sid] >= protocol["max_per_system"] else "past_n"))
    for c in sorted((c for c in candidates if not c["eligible"]), key=lambda c: c["id"]):
        out.append((c["id"], None, c["reason"]))
    return out


# ---------------------------------------------------------------------------------------------- rules C5, C6
def final_label(a: str, b: str, adjudicated: str | None) -> str:
    return a if a == b else adjudicated


def kappa(a: list[str], b: list[str], categories: list[str]) -> dict:
    """Cohen's kappa of two labellings of the same items over the given categories, with Cohen's (1960) large-sample
    standard error sqrt(p_o (1 - p_o) / n) / (1 - p_e) and its 95% interval kappa +- 1.96 se (data; no test asserts
    them). kappa, se and ci95 are None when kappa is undefined (no item, or chance agreement 1)."""
    if len(a) != len(b):
        raise ValueError("the two labellings differ in length")
    n = len(a)
    conf = {x: {y: 0 for y in categories} for x in categories}
    for x, y in zip(a, b):
        conf[x][y] += 1
    if n == 0:
        return {"n": 0, "p_o": 0.0, "p_e": 0.0, "kappa": None, "se": None, "ci95": None, "confusion": conf}
    p_o = sum(conf[x][x] for x in categories) / n
    ma, mb = Counter(a), Counter(b)
    p_e = sum(ma[x] * mb[x] for x in categories) / (n * n)
    if p_e == 1.0:
        return {"n": n, "p_o": p_o, "p_e": p_e, "kappa": None, "se": None, "ci95": None, "confusion": conf}
    k = (p_o - p_e) / (1.0 - p_e)
    se = math.sqrt(p_o * (1.0 - p_o) / n) / (1.0 - p_e)
    return {"n": n, "p_o": p_o, "p_e": p_e, "kappa": k, "se": se, "ci95": [k - 1.96 * se, k + 1.96 * se],
            "confusion": conf}


_SLOT = re.compile(r"\{\{([A-Z_]+)\}\}")


def cap_diff(diff: str) -> str:
    """Rule C5's size cap (MINOR 8): the diff itself when it holds at most DIFF_CAP characters; else its longest prefix
    of whole lines (each with its newline; the last line of a diff without a final newline is a line too) of at most
    DIFF_CAP characters, followed by the line "[diff truncated by the protocol: <k> of <m> lines shown]" and a newline
    (k the lines kept, m the diff's lines)."""
    if len(diff) <= DIFF_CAP:
        return diff
    parts = diff.split("\n")
    lines = [x + "\n" for x in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    k, size = 0, 0
    while k < len(lines) and size + len(lines[k]) <= DIFF_CAP:
        size += len(lines[k])
        k += 1
    return "".join(lines[:k]) + f"[diff truncated by the protocol: {k} of {len(lines)} lines shown]\n"


def render_prompt(role: str, entry: dict, diff: str, labels: dict | None = None) -> str:
    """Rule C5: the exact prompt a labeller (role a or b) or the adjudicator reads for one entry. The frozen template
    (spec/M4/lib/labeller_prompt.md, or adjudicator_prompt.md) with each {{SLOT}} replaced in one pass over the
    template (an inserted value is never scanned again): RULE_SHEET the rule sheet's text, ENTRY the entry id, TITLE,
    DESCRIPTION, SOURCES (one "- <kind>: <url>" line per source, in order), DIFF (cap_diff of fix_diff over the
    entry's diff_files), and for the adjudicator LABEL_A and LABEL_B (json.dumps(label, indent=2, sort_keys=True,
    ensure_ascii=False))."""
    tpl = (ADJUDICATOR_PROMPT if role == "adjudicator" else LABELLER_PROMPT).read_text(encoding="utf-8")
    vals = {"RULE_SHEET": RULE_SHEET.read_text(encoding="utf-8"), "ENTRY": entry["id"], "TITLE": entry["title"],
            "DESCRIPTION": entry["description"],
            "SOURCES": "\n".join(f"- {s['kind']}: {s['url']}" for s in entry["sources"]), "DIFF": cap_diff(diff)}
    if role == "adjudicator":
        for k in ("a", "b"):
            vals[f"LABEL_{k.upper()}"] = json.dumps(labels[k], indent=2, sort_keys=True, ensure_ascii=False)
    return _SLOT.sub(lambda m: vals[m.group(1)], tpl)


def prompt_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_response(text: str) -> dict:
    """The label a verbatim response gives: the JSON object of the whole response (surrounding whitespace aside), or of
    the text between a first line ``` (or ```json) and a last line ```."""
    t = text.strip()
    lines = t.split("\n")
    if len(lines) >= 2 and lines[0].strip() in ("```", "```json") and lines[-1].strip() == "```":
        t = "\n".join(lines[1:-1])
    obj = json.loads(t)
    if not isinstance(obj, dict):
        raise ValueError("the response is not a JSON object")
    return obj


def label_ok(obj) -> bool:
    """A label as spec/M4/lib/labels.schema.json's label object: exactly the keys primary, secondary, subform and
    justification; primary one of the rule sheet's nine categories, secondary one of them or null, subform a string,
    justification a string holding a non-space character."""
    cats = _m4.load_json(RULE_SHEET)["categories"]
    return (isinstance(obj, dict) and sorted(obj) == list(LABEL_KEYS)
            and isinstance(obj["primary"], str) and obj["primary"] in cats
            and (obj["secondary"] is None or (isinstance(obj["secondary"], str) and obj["secondary"] in cats))
            and isinstance(obj["subform"], str)
            and isinstance(obj["justification"], str) and re.search(r"\S", obj["justification"]) is not None)


def attempt_outcome(cli: dict) -> str:
    """Rule C5's retry rule, one attempt: cli is the CLI's JSON output reduced to is_error, num_turns, result,
    session_id and subtype (a key the output lacks is null; every key is null when the output is not one JSON
    object). The outcome is ok iff is_error is false, num_turns is the integer 1, and result parses (parse_response)
    to a label_ok object; else the first failing of cli_error (is_error is not false), turns (num_turns is not 1),
    unparsable (result is not a string, or parse_response raises) and invalid (the object is not label_ok)."""
    if not isinstance(cli, dict) or cli.get("is_error") is not False:
        return "cli_error"
    n = cli.get("num_turns")
    if type(n) is not int or n != 1:
        return "turns"
    r = cli.get("result")
    if not isinstance(r, str):
        return "unparsable"
    try:
        obj = parse_response(r)
    except (ValueError, RecursionError):
        return "unparsable"
    return "ok" if label_ok(obj) else "invalid"


def retry_follows(outcomes: list[str]) -> bool:
    """Rule C5's retry rule over one prompt's attempts, in order (MINOR 1). A cli_error attempt does not count toward
    the two model-output attempts: it is run again after a 60 s wait, at most 5 cli_error attempts per prompt. The
    attempts stop at the first ok one, at the second counted (turns, unparsable or invalid) one, or at the fifth
    cli_error one, and only there; the label is the last attempt's when it is ok, else null."""
    counted = cli = 0
    for i, o in enumerate(outcomes):
        last = i == len(outcomes) - 1
        if o == "ok":
            return last
        if o == "cli_error":
            cli += 1
            stop = cli == 5
        elif o in ("turns", "unparsable", "invalid"):
            counted += 1
            stop = counted == 2
        else:
            return False
        if stop != last:
            return False
    return bool(outcomes)


# ---------------------------------------------------------------------------------------------- rules K1-K2: controls
def controls(plan: dict) -> list[dict]:
    """The controls the plan fixes, in plan order (family order, then size), with the plan's budget rule (K4)."""
    b = plan["budgets"]
    out = []
    for fam in plan["families"]:
        for size in fam["sizes"]:
            f = fam["family"]
            if f == "depth":
                witness = [{"op": "inc"}] * size + [{"op": "fire"}]
                within = size + 1 <= b["prefixDepth"]
            elif f == "value":
                witness = [{"op": "fire", "d": size}]
                within = size in b["nat_input_domain"]
            elif f == "relational":
                witness, within = None, False
            elif f == "constant":
                witness, within = None, True
            else:
                raise ValueError(f)
            if fam["truth"]:
                expected = "PROVED" if within else "UNKNOWN"
            else:
                expected = "REFUTED" if within else "UNKNOWN"
            cid = f"{f}_{size}"
            out.append({"id": cid, "family": f, "size": size, "truth": fam["truth"],
                        "facts": f"spec/eval/controls/{cid}.facts.json", "law": f"spec/eval/controls/{cid}.law.json",
                        "law_id": f"L_i48_{f}_{size}", "witness": witness, "within_budget": within,
                        "expected": expected})
    return out


def _act(name: str, src: str, inputs=(), guards=(), effects=None) -> dict:
    return {"name": name, "src": src, "principal": "anyone", "inputs": [list(x) for x in inputs],
            "guards": [{"require": g, "reason": 1} for g in guards], "effects": effects or {}}


def _obs(body, doc: str) -> dict:
    return {"params": [["s", "State"]], "type": "Bool", "body": body, "doc": doc}


def expected_documents(control: dict, plan: dict) -> tuple[dict, dict]:
    """Rule K2: the exact facts and law documents of one control (spec/eval/controls/<id>.facts.json and .law.json, each
    written as dumps(doc)). The facts carry no search key (no domains, no budget) and the policy is the generic one;
    the law is rule SORT with no subform (the generic Reach path: no rule-specific routing such as SORT/width's
    decided_without_bend), catalog holon-rules/1.0, milestone the plan's, no premise, claim <observer>(s) == true over
    one binder s: Reach, scope unbounded, and facts_sha256 the facts file's sha256."""
    f, n, cid = control["family"], control["size"], control["id"]
    fam = next(x for x in plan["families"] if x["family"] == f)
    log = ["log", "List<Obs>", "observations"]
    if f == "depth":
        state = [["c", "Nat", "counter"], ["flag", "Bool", "raised once c >= SIZE"], log]
        init = {"c": 0, "flag": False}
        actions = [_act("inc", "control: inc()", effects={"c": ["+", "c", 1]}),
                   _act("fire", "control: fire()", guards=[[">=", "c", n]], effects={"flag": True})]
        obs = {"flag_down": _obs(["!", "flag"], "planted false invariant: the flag stays down")}
    elif f == "value":
        state = [["flag", "Bool", "raised by fire(SIZE)"], log]
        init = {"flag": False}
        actions = [_act("fire", "control: fire(d)", inputs=[("d", "Nat")], guards=[["==", "d", n]],
                        effects={"flag": True})]
        obs = {"flag_down": _obs(["!", "flag"], "planted false invariant: the flag stays down")}
    elif f == "relational":
        cs = [f"c_{i}" for i in range(1, n + 1)]
        state = [["a", "Nat", "copied from some c_i"], ["b", "Nat", "bumped up to 3"]] \
            + [[c, "Nat", "bumped with b"] for c in cs] + [log]
        init = dict({"a": 0, "b": 0}, **{c: 0 for c in cs})
        actions = [_act("bump", "control: bump()", guards=[["<", "b", 3]],
                        effects=dict({"b": ["+", "b", 1]}, **{c: ["+", c, 1] for c in cs}))] \
            + [_act(f"copy_{i}", f"control: copy_{i}()", effects={"a": c}) for i, c in enumerate(cs, 1)]
        obs = {"a_le_b": _obs(["<=", "a", "b"], "planted true invariant; its strengthening is relational (b == c_i)")}
    elif f == "constant":
        ys = [f"y_{i}" for i in range(1, n + 1)]
        state = [["x", "Nat", "copied from y_1"]] + [[y, "Nat", "shifted from the next y, the last one cleared"]
                                                       for y in ys] + [log]
        init = dict({"x": 0}, **{y: 0 for y in ys})
        actions = [_act("copy", "control: copy()", effects={"x": "y_1"})] \
            + [_act(f"shift_{i}", f"control: shift_{i}()", effects={ys[i - 1]: ys[i]}) for i in range(1, n)] \
            + [_act("clear", "control: clear()", effects={ys[-1]: 0})]
        obs = {"x_zero": _obs(["==", "x", 0], "planted true invariant; its strengthening is field constants")}
    else:
        raise ValueError(f)
    facts = {
        "facts_version": "holon-facts/0.2",
        "target": {"repo": "holon/eval-controls", "commit": "0" * 40,
                   "scope": f"I48 control {cid}: {fam['machine']}"},
        "extraction": {"method": "generated from spec/M4/lib/controls_plan.json (I48 rule K2)", "date": "2026-10-15"},
        "abstractions": [f"A planted obligation of the {f} family, size {n}, for UNKNOWN calibration (L15); "
                         "not a real target."],
        "params": {}, "types": {}, "state": state, "ghost_state": [],
        "initial": dict({"doc": "every register zero, flags down"}, **init, log=[]),
        "principals": {}, "reasons": {"1": "the guard does not hold"}, "defs": {},
        "actions": actions, "observers": obs, "policy": "generic",
        "coverage": {"modelled": [a["name"] for a in actions], "debt": []},
    }
    (oname,) = obs
    law = {
        "ir_version": "holon-ir/0.3", "law_id": control["law_id"], "milestone": plan["milestone"], "rule": "SORT",
        "rule_catalog_version": "holon-rules/1.0", "facts": control["facts"],
        "facts_sha256": hashlib.sha256(dumps(facts).encode("utf-8")).hexdigest(),
        "notes": f"I48 control {cid} ({'true' if control['truth'] else 'false'}; expected {control['expected']}). "
                 f"{fam['law']}",
        "statement": {"binders": [{"q": "forall", "name": "s", "type": "Reach"}], "assume": [],
                      "claim": {"eq": [{"obsv": oname, "of": {"var": "s"}}, {"bool": True}]},
                      "scope": {"kind": "unbounded"}},
    }
    return facts, law


# ---------------------------------------------------------------------------------------------- rules K3-K4
class Unsupported(Exception):
    pass


def _ev(e, s: dict, inp: dict):
    """The holon-facts/0.2 expression subset the controls use: names, literals, + - on Nat, comparisons, and/or/not."""
    if isinstance(e, bool) or isinstance(e, int):
        return e
    if isinstance(e, str):
        if e in inp:
            return inp[e]
        if e in s:
            return s[e]
        raise Unsupported(f"unknown name {e!r}")
    if isinstance(e, list) and e:
        op, *xs = e
        v = [_ev(x, s, inp) for x in xs]
        if op == "+":
            return v[0] + v[1]
        if op == "-":
            return max(v[0] - v[1], 0)
        if op == "==":
            return v[0] == v[1]
        if op == "!=":
            return v[0] != v[1]
        if op == "<":
            return v[0] < v[1]
        if op == "<=":
            return v[0] <= v[1]
        if op == ">":
            return v[0] > v[1]
        if op == ">=":
            return v[0] >= v[1]
        if op in ("and", "&&"):
            return all(v)
        if op in ("or", "||"):
            return any(v)
        if op in ("not", "!"):
            return not v[0]
    raise Unsupported(f"expression {e!r}")


def _guard_ok(a: dict, s: dict, inp: dict) -> bool:
    for g in a.get("guards", []):
        if not _ev(g["require"], s, inp):
            return False
    return True


def step(facts: dict, s: dict, act: dict) -> dict | None:
    """One action on a state (registers only; the log is not modelled): None when the action reverts."""
    a = next((x for x in facts["actions"] if x["name"] == act["op"]), None)
    if a is None:
        raise Unsupported(f"no action {act['op']!r}")
    inp = {n: act[n] for n, _ in a["inputs"]}
    if not _guard_ok(a, s, inp):
        return None
    new = dict(s)
    for reg, e in a["effects"].items():   # simultaneous assignment
        new[reg] = _ev(e, s, inp)
    return new


def initial(facts: dict) -> dict:
    return {r[0]: facts["initial"][r[0]] for r in facts["state"] if r[0] != "log"}


def _generic(t: str) -> list:
    """The generic policy's values for an input without a search domain (holon/js/policy_gen.mjs)."""
    return [False, True] if t == "Bool" else [0, 1]


def _actions(facts: dict, inputs: dict) -> list[dict]:
    out = []
    for a in facts["actions"]:
        combos = [{"op": a["name"]}]
        for n, t in a["inputs"]:
            combos = [dict(x, **{n: v}) for x in combos for v in inputs.get(a["name"], {}).get(n, _generic(t))]
        out += combos
    return out


def _key(s: dict) -> str:
    return json.dumps(s, sort_keys=True)


def enumerate_machine(facts: dict, inputs: dict, max_states: int = 100000) -> list[dict]:
    """Every reachable state (breadth-first), actions with inputs from `inputs` (action -> input -> [values]), else the
    generic policy's. Raises when more than max_states states are reachable (the state space is not the finite one the
    control claims)."""
    s0 = initial(facts)
    seen = {_key(s0)}
    q, out = deque([s0]), [s0]
    acts = _actions(facts, inputs)
    while q:
        s = q.popleft()
        for act in acts:
            t = step(facts, s, act)
            if t is None:
                continue
            k = _key(t)
            if k not in seen:
                seen.add(k)
                out.append(t)
                q.append(t)
                if len(out) > max_states:
                    raise ValueError(f"more than {max_states} reachable states")
    return out


def observer(facts: dict, name: str, s: dict):
    return _ev(facts["observers"][name]["body"], s, {})


def run_trace(facts: dict, trace: list[dict]) -> dict | None:
    s = initial(facts)
    for act in trace:
        s = step(facts, s, act)
        if s is None:
            return None
    return s


def shortest(facts: dict, obs: str, inputs: dict, cap: int) -> int | None:
    """The length of a shortest trace (breadth-first, at most cap actions, inputs as in enumerate_machine) to a state
    where the observer is false; None when there is none within cap."""
    s0 = initial(facts)
    q, seen = deque([(s0, 0)]), {_key(s0)}
    acts = _actions(facts, inputs)
    while q:
        s, d = q.popleft()
        if not observer(facts, obs, s):
            return d
        if d >= cap:
            continue
        for act in acts:
            t = step(facts, s, act)
            if t is not None and _key(t) not in seen:
                seen.add(_key(t))
                q.append((t, d + 1))
    return None


def houdini_constants(facts: dict, depth: int, max_states: int) -> dict:
    """What holon/js/houdini.mjs proposes, recomputed: the Nat and Bool registers that hold one value on every state of
    the breadth-first exploration from s0 (depth levels of the generic policy's actions, at most max_states states),
    with that value."""
    s0 = initial(facts)
    seen, frontier = {_key(s0): s0}, [s0]
    acts = _actions(facts, {})
    for _ in range(depth):
        if len(seen) >= max_states:
            break
        nxt = []
        for s in frontier:
            for act in acts:
                t = step(facts, s, act)
                if t is None or _key(t) in seen:
                    continue
                seen[_key(t)] = t
                nxt.append(t)
                if len(seen) >= max_states:
                    break
            if len(seen) >= max_states:
                break
        frontier = nxt
    out = {}
    for name, ty, *_ in facts["state"]:
        if name != "log" and ty in ("Nat", "Bool") and len({_key({"v": s[name]}) for s in seen.values()}) == 1:
            out[name] = s0[name]
    return out


def cti(facts: dict, obs: str, extra: dict, box: int = 4):
    """A counterexample to induction in the box (every Nat register in 0..box-1, every Bool either value): a state where
    the observer and the extra register constants hold, and one action (generic inputs) to a state where one of them
    fails. Returns (state, action), or None when the box holds none."""
    regs = [(r[0], r[1]) for r in facts["state"] if r[0] != "log"]
    acts = _actions(facts, {})
    for vals in product(*[[False, True] if t == "Bool" else range(box) for _, t in regs]):
        s = dict(zip([r for r, _ in regs], vals))
        if not observer(facts, obs, s) or any(s[k] != v for k, v in extra.items()):
            continue
        for act in acts:
            t = step(facts, s, act)
            if t is not None and (not observer(facts, obs, t) or any(t[k] != v for k, v in extra.items())):
                return s, act
    return None


# ---------------------------------------------------------------------------------------------- rules C2-C3: git
_GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "TZ": "UTC", "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0",
            "GIT_LITERAL_PATHSPECS": "1"}   # a path with * or [ in its name names that file only
_REACH: dict[str, set] = {}


def _env() -> dict:
    return {**os.environ, **_GIT_ENV}


def _no_excluded_redirect(stderr: str) -> None:
    """MINOR 10: git reports an HTTP redirect (a transferred repository) as "redirecting to <url>" (not with --quiet,
    so the instrument's clones and fetches use --no-progress instead); a redirect to a URL under an excluded_repos
    pattern is a failure (the tool must refuse it too)."""
    for m in re.finditer(r"redirecting to (\S+)", stderr or ""):
        if excluded(m.group(1)):
            raise AssertionError(f"git was redirected to {m.group(1)}, an excluded repository: refused")


def git(d: Path, *args: str, check: bool = True, text: bool = True, timeout: int = 3600):
    p = subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=text, timeout=timeout, env=_env())
    err = p.stderr if text else p.stderr.decode(errors="replace")
    _no_excluded_redirect(err)
    if check and p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {d}: {err.strip()[:500]}")
    return p.stdout


def excluded(url: str | None, protocol: dict | None = None) -> bool:
    """url (a repository or any URL) lies under an excluded_repos pattern (case-insensitive); None is not excluded."""
    if url is None:
        return False
    p = protocol or _m4.load_json(PROTOCOL)
    return any(x["pattern"].lower() in url.lower() for x in p["excluded_repos"])


def _gh(url: str) -> tuple[str, str]:
    m = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?", url or "")
    if not m:
        raise AssertionError(f"not a GitHub repository URL: {url}")
    return m.group(1), m.group(2)


def _clone(url: str, d: Path, filt: str) -> Path:
    """A bare clone of url with the given object filter at d (created when missing). An excluded repository (the sealed
    and the development target) is never cloned."""
    if excluded(url):
        raise AssertionError(f"{url} is an excluded repository (protocol excluded_repos): never cloned")
    if not (d / "HEAD").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = d.with_name(d.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        p = subprocess.run(["git", "clone", "--bare", f"--filter={filt}", "--no-progress", url, str(tmp)],
                           capture_output=True, text=True, timeout=7200, env=_env())
        try:
            _no_excluded_redirect(p.stderr)
        except AssertionError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        if p.returncode != 0:
            raise AssertionError(f"git clone {url}: {p.stderr.strip()[:500]} (the instrument needs the network)")
        tmp.rename(d)
    return d


def repo_cache(url: str) -> Path:
    """A partial bare clone (blobs fetched on demand) of a public GitHub repository in the instrument's own cache,
    created when missing. An excluded repository (the sealed and the development target) is never cloned."""
    owner, name = _gh(url)
    return _clone(url, CACHE / f"{owner}__{name}.git", "blob:none")


def _refetch(d: Path) -> None:
    filt = git(d, "config", "--get", "remote.origin.partialclonefilter", check=False).strip()
    git(d, "fetch", "--no-progress", "--prune", *([f"--filter={filt}"] if filt else []), "origin",
        "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", timeout=7200)


def _reachable(d: Path, refresh: bool) -> set:
    if refresh or str(d) not in _REACH:
        if refresh:
            _refetch(d)
        _REACH[str(d)] = set(git(d, "rev-list", "--branches", "--tags").split())
    return _REACH[str(d)]


def ensure_commit(d: Path, sha: str) -> bool:
    """sha is a commit reachable from a branch or tag of the public repository (refs/heads, refs/tags of the bare
    clone), decided from `git rev-list --branches --tags` alone: no object is ever fetched by sha, so a commit only a
    pull-request ref holds is never accepted. The branches and tags are fetched again once when sha is not there."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        return False
    return sha in _reachable(d, False) or sha in _reachable(d, True)


def _branch_reach(d: Path, branch: str, refresh: bool) -> set:
    key = f"{d}#{branch}"
    if refresh or key not in _REACH:
        if refresh:
            _refetch(d)
        p = subprocess.run(["git", "-C", str(d), "rev-list", f"refs/heads/{branch}", "--"], capture_output=True,
                           text=True, env=_env())
        _REACH[key] = set(p.stdout.split()) if p.returncode == 0 else set()
    return _REACH[key]


def on_branch(d: Path, sha: str, branch: str) -> bool:
    """sha is a commit reachable from the named branch of the repository (refs/heads/<branch> of the bare clone),
    decided from `git rev-list refs/heads/<branch>` alone (no object is fetched by sha); the branches are fetched
    again once when sha is not there."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        return False
    return sha in _branch_reach(d, branch, False) or sha in _branch_reach(d, branch, True)


def advisory_snapshot(commit: str, branch: str = "main") -> Path:
    """The GitHub Advisory Database at commit, for rule C2's GHSA indexes. commit must be reachable from the branch,
    decided on a commit-graph clone (git clone --bare --filter=tree:0) in the instrument's cache; only then is commit
    fetched by sha, depth 1, into a separate bare repository of the cache (refs/snapshots/<commit>). No other object
    is ever fetched by sha."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit or ""):
        raise AssertionError(f"not a commit sha: {commit!r}")
    g = _clone(ADVISORY_DB, CACHE / "github__advisory-database.graph.git", "tree:0")
    if not on_branch(g, commit, branch):
        raise AssertionError(f"{commit} is not reachable from the advisory database's branch {branch}")
    d = CACHE / "github__advisory-database.snapshots.git"
    if not (d / "HEAD").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = d.with_name(d.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        subprocess.run(["git", "init", "--bare", "--quiet", str(tmp)], check=True, capture_output=True, env=_env())
        tmp.rename(d)
    if subprocess.run(["git", "-C", str(d), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True,
                      env=_env()).returncode != 0:
        git(d, "fetch", "--no-progress", "--depth", "1", "--no-tags", ADVISORY_DB, f"+{commit}:refs/snapshots/{commit}",
            timeout=7200)
    return d


def snapshot_rule(graph: dict, head: str, cutoff: str) -> str | None:
    """The protocol's snapshot rule (M1) on a commit graph {sha: {"date": committer date, "parents": [sha, ...]}}: the
    newest first-parent commit of the branch whose committer date (UTC) is before the cutoff, i.e. the first commit,
    walking first parents from the branch head, whose committer date is before the cutoff (None when there is none).
    A second parent is never walked."""
    cut, c, seen = utc(cutoff), head, set()
    while c is not None and c not in seen:
        seen.add(c)
        node = graph[c]
        if utc(node["date"]) < cut:
            return c
        c = node["parents"][0] if node["parents"] else None
    return None


def is_test_path(path: str, protocol: dict) -> bool:
    """A test file (rule C2c): a directory component in test_dirs, or a basename matching test_file_globs."""
    parts = PurePosixPath(path).parts
    return any(x in protocol["test_dirs"] for x in parts[:-1]) or \
        any(fnmatch.fnmatchcase(parts[-1], g) for g in protocol["test_file_globs"])


def _has_ext(path: str, exts) -> bool:
    return any(path.endswith(e) for e in exts)


def language_of(path: str, protocol: dict) -> str:
    for lang, exts in protocol["frontend_extensions"].items():
        if _has_ext(path, exts):
            return lang
    raise ValueError(path)


def blob(d: Path, rev: str, path: str) -> bytes:
    return git(d, "cat-file", "blob", f"{rev}:{path}", text=False, timeout=1800)


def _exists(d: Path, rev: str, path: str) -> bool:
    """rev:path names a blob; decided from the trees alone (no blob is fetched)."""
    p = subprocess.run(["git", "-C", str(d), "ls-tree", "-z", rev, "--", path], capture_output=True, env=_env())
    if p.returncode != 0:
        raise AssertionError(f"git ls-tree {rev} {path}: {p.stderr.decode(errors='replace')[:300]}")
    want = path.encode("utf-8", errors="surrogateescape")
    return any(e.split(b"\t", 1)[0].split(b" ")[1] == b"blob" and e.split(b"\t", 1)[1] == want
               for e in p.stdout.split(b"\0") if e)


def is_generated(d: Path, parent: str, fix: str, path: str, protocol: dict) -> bool:
    """Rule C2c: generated or vendored: a directory component in generated_dirs, a basename matching generated_globs, or
    a Go file holding a line that matches generated_go_marker (read at the fix, else at the pre-fix commit)."""
    parts = PurePosixPath(path).parts
    if any(x in protocol["generated_dirs"] for x in parts[:-1]) or \
            any(fnmatch.fnmatchcase(parts[-1], g) for g in protocol["generated_globs"]):
        return True
    if path.endswith(".go"):
        rev = fix if _exists(d, fix, path) else parent
        text = blob(d, rev, path).decode("utf-8", errors="replace")
        return re.search(protocol["generated_go_marker"], text, re.M) is not None
    return False


def commit_info(url: str, fix: str, protocol: dict) -> dict:
    """What rules C2b-C2c derive from git for a fix commit: found (reachable from a branch or tag), prefix_commit (its
    first parent), fix_date (its committer date, UTC), source_lines (added plus deleted lines, git numstat, of its
    changed non-test, non-generated source files of any language), frontend_lines (the same over its .go and .sol
    files), files (its changed non-test, non-generated .go and .sol files that exist in the pre-fix tree, sorted),
    diff_files (every changed non-generated source file, tests included, sorted: what a labeller's diff shows) and
    reach (files is not empty and 2 * frontend_lines >= source_lines)."""
    d = repo_cache(url)
    if not ensure_commit(d, fix):
        return {"found": False}
    parents = git(d, "rev-list", "--parents", "-n", "1", fix).split()[1:]
    if not parents:
        return {"found": False}
    parent = parents[0]
    date = git(d, "show", "-s", "--format=%cd", "--date=format-local:%Y-%m-%dT%H:%M:%SZ", fix).strip()
    raw = git(d, "diff-tree", "-z", "-r", "--no-renames", "--numstat", parent, fix)
    changed = []
    for item in raw.split("\0"):
        if item:
            a, dl, path = item.split("\t", 2)
            changed.append((path, (0 if a == "-" else int(a)) + (0 if dl == "-" else int(dl))))
    src = [(p, k) for p, k in changed if _has_ext(p, protocol["source_extensions"])
           and not is_generated(d, parent, fix, p, protocol)]
    exts = [e for xs in protocol["frontend_extensions"].values() for e in xs]
    nontest = [(p, k) for p, k in src if not is_test_path(p, protocol)]
    front = [(p, k) for p, k in nontest if _has_ext(p, exts)]
    files = sorted(p for p, _ in front if _exists(d, parent, p))
    source_lines, frontend_lines = sum(k for _, k in nontest), sum(k for _, k in front)
    return {"found": True, "prefix_commit": parent, "fix_date": date, "files": files,
            "source_lines": source_lines, "frontend_lines": frontend_lines, "diff_files": sorted(p for p, _ in src),
            "reach": bool(files) and 2 * frontend_lines >= source_lines}


_DIFF = ["-c", "core.quotePath=true", "-c", "diff.suppressBlankEmpty=false", "diff", "--no-color", "--no-renames",
         "--no-ext-diff", "--no-textconv", "--diff-algorithm=myers", "--indent-heuristic", "--no-relative",
         "--inter-hunk-context=0", "--src-prefix=a/", "--dst-prefix=b/"]


def fix_diff(url: str, prefix: str, fix: str, files: list[str]) -> str:
    """The diff a labeller reads (rule C5): git diff -U5 from the pre-fix to the fix commit over the given files (the
    entry's diff_files), every option a git configuration could change fixed on the command line."""
    out = git(repo_cache(url), *_DIFF, "-U5", prefix, fix, "--", *files, text=False)
    return out.decode("utf-8", errors="replace")


def old_lines_from_diff(text: str) -> list[int]:
    """The pre-fix line numbers a -U0 diff deletes or changes: the old side of every hunk header @@ -a[,b] +c[,d] @@
    (b omitted means 1), lines a .. a+b-1; a hunk with an old count of 0 (a pure insertion) contributes nothing."""
    lines = set()
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", text, re.M):
        start, count = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
        lines.update(range(start, start + count))
    return sorted(lines)


def changed_old_lines(url: str, prefix: str, fix: str, path: str) -> list[int]:
    """The pre-fix lines of path that the fix deletes or changes (old_lines_from_diff of git diff -U0)."""
    out = git(repo_cache(url), *_DIFF, "-U0", prefix, fix, "--", path, text=False).decode("utf-8", errors="replace")
    return old_lines_from_diff(out)


def sparse_checkout(url: str, sha: str, files: list[str], dest: Path) -> Path:
    """A worktree of the repository at sha holding, for rule N1, every file (any extension, test files included)
    directly inside each directory that holds a .go file of the set (patterns /<dir>/* and !/<dir>/*/), and every .sol
    file of the tree."""
    d = repo_cache(url)
    if not ensure_commit(d, sha):
        raise AssertionError(f"{url}@{sha} is not reachable from a branch or tag")
    git(d, "worktree", "add", "--no-checkout", "--detach", str(dest), sha)
    pats = []
    for parent in sorted({PurePosixPath(f).parent.as_posix() for f in files if f.endswith(".go")}):
        base = "" if parent == "." else "/" + parent
        pats += [f"{base}/*", f"!{base}/*/"]
    if any(f.endswith(".sol") for f in files):
        pats.append("*.sol")
    git(dest, "sparse-checkout", "set", "--no-cone", *pats)
    git(dest, "checkout", "--quiet", sha)
    return dest


def drop_worktree(url: str, dest: Path) -> None:
    subprocess.run(["git", "-C", str(repo_cache(url)), "worktree", "remove", "--force", str(dest)],
                   capture_output=True, env=_env())


# ---------------------------------------------------------------------------------------------- rule C2: index items
_ADB: dict = {}   # (commit, protocol digest) -> {"items": {system id: GHSA items}, "docs": {system id: {item: JSON}}}


def utc(ts: str) -> datetime:
    """An RFC 3339 timestamp or a YYYY-MM-DD date as a UTC instant (a date: its midnight; no offset: UTC)."""
    try:
        t = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        raise AssertionError(f"not a date or timestamp: {ts!r}") from None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def published_of(doc) -> datetime | None:
    """An index entry's published field as a UTC instant, or None when it has none that parses (MINOR 11: such an
    entry is not an item)."""
    try:
        return utc(doc.get("published")) if isinstance(doc, dict) else None
    except AssertionError:
        return None


def string_values(obj) -> list[str]:
    """Every string value of a JSON document (object keys aside), at any depth."""
    out, todo = [], [obj]
    while todo:
        x = todo.pop()
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            todo.extend(x.values())
        elif isinstance(x, list):
            todo.extend(x)
    return out


def pattern_in(texts, protocol: dict) -> str | None:
    """The first excluded_repos pattern (protocol order) found case-insensitively in one of the texts (None aside)."""
    low = [t.lower() for t in texts if isinstance(t, str)]
    return next((x["pattern"] for x in protocol["excluded_repos"] if any(x["pattern"].lower() in t for t in low)),
                None)


def subject_in(texts, protocol: dict) -> str | None:
    """The first excluded subject (protocol order) found in one of the texts as a whole word: case-insensitive, dots
    and dashes literal, \\b on both sides (None aside)."""
    ts = [t for t in texts if isinstance(t, str)]
    for s in protocol["excluded_subjects"]["subjects"]:
        r = re.compile(r"\b" + re.escape(s) + r"\b", re.I)
        if any(r.search(t) for t in ts):
            return s
    return None


def prefilter(obj, protocol: dict) -> dict | None:
    """Rule C2's pre-filter of a mechanical index item, applied before any agent sees it: {"pattern": P} for the first
    excluded_repos pattern found case-insensitively in any string value of the item's JSON, else {"subject": S} for
    the first excluded subject found there as a whole word, else None."""
    vals = string_values(obj)
    p = pattern_in(vals, protocol)
    if p is not None:
        return {"pattern": p}
    s = subject_in(vals, protocol)
    return {"subject": s} if s is not None else None


def gh_slug(url: str) -> str:
    """github.com/<owner>/<repo> of a repository URL, lowercased."""
    owner, name = _gh(url)
    return f"github.com/{owner}/{name}".lower()


def names_repo(text: str, slug: str) -> bool:
    """text, lowercased, contains slug (github.com/<owner>/<repo>, lowercased) with a left boundary (the start of the
    text, or a character outside [A-Za-z0-9.-], before github.com) and, after it, the end of the text, one of
    / ? # @, or .git followed by the end or one of / ? # @ (MINOR 3)."""
    t = text.lower()
    i = t.find(slug)
    while i >= 0:
        j = i + len(slug)
        left = i == 0 or not re.fullmatch(r"[a-z0-9.-]", t[i - 1])
        right = j == len(t) or t[j] in "/?#@" or (t.startswith(".git", j) and (j + 4 == len(t) or t[j + 4] in "/?#@"))
        if left and right:
            return True
        i = t.find(slug, i + 1)
    return False


def _list(x) -> list:
    return x if isinstance(x, list) else []


def _ghsa_rows(advisories, repos: list[str], protocol: dict) -> list[tuple[dict, dict]]:
    slugs = [gh_slug(r) for r in repos]
    cutoff = utc(protocol["cutoff"])
    rows = []
    for path, obj in advisories:
        if not (path.startswith(ADVISORY_DIRS) and path.endswith(".json")) or not isinstance(obj, dict) \
                or "withdrawn" in obj:
            continue
        names = [a["package"]["name"] for a in _list(obj.get("affected"))
                 if isinstance(a, dict) and isinstance(a.get("package"), dict)
                 and isinstance(a["package"].get("name"), str)]
        urls = [r["url"] for r in _list(obj.get("references")) if isinstance(r, dict) and isinstance(r.get("url"), str)]
        if not any(names_repo(x, s) for x in names + urls for s in slugs):
            continue
        t = published_of(obj)
        if t is None or t >= cutoff:
            continue
        gid, summary, ex = obj["id"], obj.get("summary"), prefilter(obj, protocol)
        title = None if ex else (summary if isinstance(summary, str) and summary.strip() else gid)
        rows.append((t, gid, {"item": f"https://github.com/advisories/{gid}", "published": t.date().isoformat(),
                              "title": title, "excluded_by": ex}, obj))
    rows.sort(key=lambda r: r[1])
    rows.sort(key=lambda r: r[0], reverse=True)   # stable: ties keep the id order
    return [(r[2], r[3]) for r in rows]


def ghsa_items_from(advisories, repos: list[str], protocol: dict) -> list[dict]:
    """Rule C2's GHSA index of one system, from (path, parsed advisory JSON) pairs of the advisory database: every
    advisory under advisories/github-reviewed/ or advisories/unreviewed/ (a .json file) without a withdrawn field whose
    affected[].package.name or references[].url names one of the repos (names_repo of gh_slug), with a published field
    that parses (published_of), published (UTC) before the protocol's cutoff; newest published first, then GHSA id
    ascending. Each item is {"item": https://github.com/advisories/<id>, "published": the UTC date, "title": the
    summary verbatim (the id when it holds no non-space character), "excluded_by": prefilter}; a pre-filtered item's
    title is null (never read)."""
    return [item for item, _ in _ghsa_rows(advisories, repos, protocol)]


def _geth_rows(data: bytes, protocol: dict, list_url: str) -> list[tuple[dict, dict]]:
    cutoff = utc(protocol["cutoff"])
    entries = json.loads(data)
    uids = [e.get("uid") if isinstance(e, dict) else None for e in entries]
    by_uid = all(isinstance(u, str) and u.strip() for u in uids) and len(set(uids)) == len(uids)
    rows = []
    for i, e in enumerate(entries, 1):
        t = published_of(e)
        if t is None or t >= cutoff:
            continue
        ex = prefilter(e, protocol)
        if ex is None and not (isinstance(e.get("name"), str) and e["name"].strip()):
            raise AssertionError(f"entry {i} of the geth list has no name")
        tag = urllib.parse.quote(e["uid"], safe="") if by_uid else str(i)
        rows.append((t, i, {"item": f"{list_url}#{tag}", "published": t.date().isoformat(),
                            "title": None if ex else e["name"], "excluded_by": ex}, e))
    rows.sort(key=lambda r: r[0], reverse=True)   # stable: ties keep the list order
    return [(r[2], r[3]) for r in rows]


def geth_items_from(data: bytes, protocol: dict, list_url: str) -> list[dict]:
    """Rule C2's geth vulnerabilities index, from the list's bytes (B2): every entry with a published field that parses,
    published (UTC) before the protocol's cutoff, newest first, then list order. Each item is {"item": list_url + "#"
    + the entry's uid (percent-encoded) when every entry of the list has a distinct uid holding a non-space character,
    else list_url + "#" + the entry's 1-based position in the list, "published": the UTC date, "title": the entry's
    name verbatim, "excluded_by": prefilter of the entry}; a pre-filtered item's title is null (never read)."""
    return [item for item, _ in _geth_rows(data, protocol, list_url)]


def report_url(repo: str, commit: str, path: str) -> str:
    """An in-repo report's item URL: <repo>/blob/<commit>/<path>, the path percent-encoded (urllib.parse.quote, "/"
    kept)."""
    return f"{repo.rstrip('/')}/blob/{commit}/{urllib.parse.quote(path, safe='/')}"


def folder_items_from(paths: list[str], repo: str, commit: str, folder: str) -> list[str]:
    """Rule C2's in-repo audit index: every file under folder/ (any depth) whose extension is .pdf or .md
    (case-insensitive), other than a README.md (case-insensitive basename), as report_url, sorted."""
    pre = folder.strip("/") + "/"
    keep = [x for x in paths if x.startswith(pre) and x.lower().endswith((".pdf", ".md"))
            and PurePosixPath(x).name.lower() != "readme.md"]
    return sorted(report_url(repo, commit, x) for x in keep)


def pin_of(protocol: dict, index: dict) -> dict:
    """The snapshot pin of a git index (the protocol's snapshots.pins, M1)."""
    return protocol["snapshots"]["pins"][index["snapshot"]]


def _ghsa_scan(pin: dict, protocol: dict) -> dict:
    key = (pin["commit"], hashlib.sha256(dumps(protocol).encode("utf-8")).hexdigest())
    if key in _ADB:
        return _ADB[key]
    d = advisory_snapshot(pin["commit"], pin["branch"])
    slugs = sorted({gh_slug(r).encode() for s in protocol["systems"] for r in s["repos"]})
    found = []
    p = subprocess.Popen(["git", "-C", str(d), "archive", "--format=tar", pin["commit"], "--",
                          *[x.rstrip("/") for x in ADVISORY_DIRS]], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, env=_env())
    with tarfile.open(fileobj=p.stdout, mode="r|") as tf:
        for m in tf:
            if not m.isfile() or not m.name.endswith(".json"):
                continue
            data = tf.extractfile(m).read()
            low = data.lower()
            if any(s in low for s in slugs) or b"\\/" in data or b"\\u" in low:
                found.append((m.name, json.loads(data)))
    if p.wait() != 0:
        raise AssertionError(f"git archive {pin['commit']} of the advisory database failed")
    rows = {s["id"]: _ghsa_rows(found, s["repos"], protocol) for s in protocol["systems"]}
    _ADB[key] = {"items": {k: [i for i, _ in v] for k, v in rows.items()},
                 "docs": {k: {i["item"]: doc for i, doc in v} for k, v in rows.items()}}
    return _ADB[key]


def ghsa_index(pin: dict, protocol: dict) -> dict[str, list[dict]]:
    """Every system's GHSA items at the advisory-database pin (ghsa_items_from over advisory_snapshot, read in one
    streamed git archive; cached per process). A file is parsed when its bytes, lowercased, hold a repository slug of
    the protocol, an escaped slash or a \\u escape (else no string value of it can name a repository)."""
    return _ghsa_scan(pin, protocol)["items"]


def _geth_list(pin: dict) -> bytes:
    d = repo_cache(pin["repo"])
    if not on_branch(d, pin["commit"], pin["branch"]):
        raise AssertionError(f"{pin['repo']}@{pin['commit']} is not reachable from its branch {pin['branch']}")
    data = blob(d, pin["commit"], pin["path"])
    if hashlib.sha256(data).hexdigest() != pin["sha256"]:
        raise AssertionError(f"{pin['path']} at {pin['commit']} does not have the pinned sha256")
    return data


def geth_items(pin: dict, protocol: dict, list_url: str) -> list[dict]:
    """The geth index's items at its pin: the list file at the pinned commit of its branch (reachable from it), with
    the pinned sha256."""
    return geth_items_from(_geth_list(pin), protocol, list_url)


def folder_items(pin: dict) -> list[str]:
    """An in-repo audit index's report URLs at its pin (a commit reachable from the pinned branch)."""
    d = repo_cache(pin["repo"])
    if not on_branch(d, pin["commit"], pin["branch"]):
        raise AssertionError(f"{pin['repo']}@{pin['commit']} is not reachable from its branch {pin['branch']}")
    names = git(d, "ls-tree", "-r", "-z", "--name-only", pin["commit"], "--", pin["path"]).split("\0")
    return folder_items_from([x for x in names if x], pin["repo"], pin["commit"], pin["path"])


def index_items(system: dict, index: dict, protocol: dict) -> list[dict]:
    """The items of a mechanical index (enumeration ghsa or geth) at its pinned snapshot."""
    if index["enumeration"] == "ghsa":
        return ghsa_index(pin_of(protocol, index), protocol)[system["id"]]
    if index["enumeration"] == "geth":
        return geth_items(pin_of(protocol, index), protocol, index["url"])
    raise ValueError(f"{index['id']} is not a mechanical index")


def index_docs(system: dict, index: dict, protocol: dict) -> dict[str, dict]:
    """The JSON document of every item of a mechanical index at its pinned snapshot: {item: the advisory or the list
    entry}."""
    if index["enumeration"] == "ghsa":
        return _ghsa_scan(pin_of(protocol, index), protocol)["docs"][system["id"]]
    if index["enumeration"] == "geth":
        return {i["item"]: e for i, e in _geth_rows(_geth_list(pin_of(protocol, index)), protocol, index["url"])}
    raise ValueError(f"{index['id']} is not a mechanical index")


def items_order(items: list[dict]) -> list[dict]:
    """An audit index's items in examination order: published newest first, then item."""
    return sorted(sorted(items, key=lambda x: x["item"]), key=lambda x: x["published"], reverse=True)


_COMMIT_URL = re.compile(r"(?<![A-Za-z0-9.-])github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/commit/([0-9a-f]{40})"
                         r"(?![0-9a-z])", re.I)


def named_commits(doc, repos: list[str]) -> list[tuple[str, str]]:
    """M3: the commits a mechanical item names in one of the repos: every github.com/<owner>/<repo>/commit/<40 hex>
    (owner/repo case-insensitive, one of repos; left boundary as names_repo, no hex digit or letter after the sha) in
    the item's references[].url (GHSA) or links[] (geth), as (the repo as the protocol writes it, the sha lowercased),
    sorted and without duplicates."""
    slugs = {gh_slug(r): r for r in repos}
    urls = [r["url"] for r in _list(doc.get("references")) if isinstance(r, dict) and isinstance(r.get("url"), str)] \
        + [u for u in _list(doc.get("links")) if isinstance(u, str)]
    out = set()
    for u in urls:
        for m in _COMMIT_URL.finditer(u):
            r = slugs.get(f"github.com/{m.group(1)}/{m.group(2)}".lower())
            if r is not None:
                out.add((r, m.group(3).lower()))
    return sorted(out)


def named_fix(doc, repos: list[str]) -> tuple[str, str] | None:
    """M3, the fix-commit rule made exact for the mechanical indexes: among named_commits(doc, repos), those reachable
    from a branch or tag of their repository (ensure_commit); the earliest of them by committer date (ties: the sha),
    as (repo, sha); None when no named commit is reachable."""
    found = []
    for repo, sha in named_commits(doc, repos):
        d = repo_cache(repo)
        if ensure_commit(d, sha):
            found.append((int(git(d, "show", "-s", "--format=%ct", sha).strip()), sha, repo))
    if not found:
        return None
    _, sha, repo = min(found)
    return repo, sha


def collapse(text: str) -> str:
    """Runs of whitespace collapsed to one space, and none at either end."""
    return " ".join(text.split())


def description_source(doc: dict, enumeration: str) -> str:
    """The collapsed text a mechanical item's description is excerpted from (M3): the advisory's details (its summary
    when the details are blank) for ghsa, the entry's description (its summary when blank) for geth."""
    field = "details" if enumeration == "ghsa" else "description"
    text = doc.get(field) if isinstance(doc.get(field), str) else ""
    if not text.strip():
        text = doc.get("summary") if isinstance(doc.get("summary"), str) else ""
    return collapse(text)


def description_ok(desc: str, doc: dict, enumeration: str) -> bool:
    """A mechanical candidate's description is a verbatim excerpt (M3): collapsed, non-empty, at most 2000 characters,
    and a substring of description_source."""
    return isinstance(desc, str) and desc == collapse(desc) and 0 < len(desc) <= 2000 \
        and desc in description_source(doc, enumeration)


# ---------------------------------------------------------------------------------------------- rule N1
def tree_files(root: Path) -> list[str]:
    """Every file under root (posix paths relative to it), .git aside."""
    return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


_WORD = re.compile(rb"[A-Za-z0-9_$]+")
_UWORD = re.compile(r"[\w$]+")   # \w holds every Unicode letter and decimal digit (and more: split below)


def _word_char(c: str) -> bool:
    cat = unicodedata.category(c)
    return c in "_$" or cat[0] == "L" or cat == "Nd"


def words(data: bytes) -> set[str]:
    """Rule N1's words (MJ1, Unicode-aware like Go identifiers): the maximal runs of [A-Za-z0-9_$] in the bytes, and
    the maximal runs of characters that are _, $, a Unicode letter (category L*) or a decimal digit (Nd) in the UTF-8
    decoding of the bytes (errors replaced); the union of both kinds."""
    out = {w.decode("ascii") for w in _WORD.findall(data)}
    if data.isascii():
        return out   # both kinds coincide on ASCII text
    for run in _UWORD.findall(data.decode("utf-8", errors="replace")):
        if run.isascii():
            out.add(run)
            continue
        cur = []
        for c in run:
            if _word_char(c):
                cur.append(c)
            elif cur:
                out.add("".join(cur))
                cur = []
        if cur:
            out.add("".join(cur))
    return out


def upper_initial(name: str) -> bool:
    """The name's first character is an upper-case letter (Unicode category Lu, as Go's unicode.IsUpper): a Go name is
    then exported (rule N1 (c)), and its new name starts with V."""
    return bool(name) and unicodedata.category(name[0]) == "Lu"


def new_names(seed: str, olds, tree_words: set[str]) -> dict:
    """Rule N1's new names: for each old name in sorted order, v (V when upper_initial(old)) followed by the first 10
    hex digits of sha256(seed + ":" + old), lengthened one hex digit at a time until it is no word of the tree and no
    new name already given."""
    out, taken = {}, set()
    for old in sorted(olds):
        h = hashlib.sha256(f"{seed}:{old}".encode("utf-8")).hexdigest()
        pre = "V" if upper_initial(old) else "v"
        c = next((pre + h[:k] for k in range(10, len(h) + 1)
                  if pre + h[:k] not in tree_words and pre + h[:k] not in taken), None)
        if c is None:
            raise ValueError(f"no free name for {old}")
        out[old] = c
        taken.add(c)
    return out


def reserved(langs, package_names=(), cgo_names=()) -> tuple[set, list]:
    """Rule N1 (b): the reserved names and patterns of the given languages (spec/M4/lib/rename_reserved.json), with the
    package-clause names of the set's Go files and, for its Go files that import "C", every name X of a selector
    expression C.X (go_facts' cgo)."""
    r = _m4.load_json(RESERVED)
    names, pats = set(), []
    for lang in sorted(langs):
        names |= set(r[lang]["names"])
        pats += r[lang]["patterns"]
    if "go" in langs and r["go"]["package_clause_names"]:
        names |= set(package_names)
    if "go" in langs and r["go"]["cgo_selector_names"]:
        names |= set(cgo_names)
    return names, pats


def is_reserved(name: str, names: set, pats: list) -> bool:
    return name in names or any(re.fullmatch(p, name) for p in pats)


def replaced_by(comment: str) -> str:
    """Rule N1: what a removed comment becomes: nothing for a line comment, a newline for a block comment holding one,
    else one space (Go: a general comment acts like a newline or a space; Solidity: comments are whitespace)."""
    if comment.startswith("//"):
        return ""
    return "\n" if "\n" in comment else " "


# ---------------------------------------------------------------------------------------------- rule N3: Go
GOAST_SRC = ROOT / "tests_m4" / "fixtures" / "goast" / "main.go"
_GOAST: list[Path] = []


def goast_bin() -> Path:
    """The instrument's Go AST printer (tests_m4/fixtures/goast/main.go: go/parser, standard library only), built once
    per process in a temporary module removed at exit, with the pinned go (GO_VERSION)."""
    if _GOAST and _GOAST[0].exists():
        return _GOAST[0]
    go = shutil.which("go")
    if go is None:
        raise AssertionError(f"go is missing (the Go isomorphism check needs {GO_VERSION!r})")
    env = {**os.environ, "GOFLAGS": "-mod=mod", "GO111MODULE": "on", "GOTOOLCHAIN": "local", "GOWORK": "off",
           "GOPROXY": "off", "CGO_ENABLED": "0"}
    got = subprocess.run([go, "version"], capture_output=True, text=True, env=env).stdout.strip()
    if got != GO_VERSION:
        raise AssertionError(f"go is {got!r}; the instrument pins {GO_VERSION!r}")
    d = Path(tempfile.mkdtemp(prefix="i48_goast_"))
    atexit.register(shutil.rmtree, d, True)
    (d / "main.go").write_bytes(GOAST_SRC.read_bytes())
    for cmd in (["mod", "init", "goast"], ["build", "-o", "goast", "."]):
        p = subprocess.run([go, *cmd], cwd=d, capture_output=True, text=True, env=env, timeout=600)
        if p.returncode != 0:
            raise AssertionError(f"go {' '.join(cmd)}: {p.stderr.strip()[:500]}")
    _GOAST[:] = [d / "goast"]
    return _GOAST[0]


def _goast(args: list[str]) -> str | None:
    p = subprocess.run([str(goast_bin()), *args], capture_output=True, timeout=600)
    if p.returncode == 1:
        return None
    if p.returncode != 0:
        raise AssertionError(f"goast {' '.join(args)}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout.decode("utf-8", errors="replace")


def go_ast(path: Path) -> list[str] | None:
    """The printer's lines for one Go file (None when it does not parse)."""
    out = _goast([str(path)])
    return None if out is None else out.splitlines()


def go_comments(path: Path) -> list[tuple[int, str, bool]] | None:
    """Every comment of one Go file in file order: (byte offset, text, kept), kept for a directive or a comment of the
    cgo preamble (None when the file does not parse)."""
    out = _goast(["-comments", str(path)])
    if out is None:
        return None
    res = []
    for line in out.splitlines():
        m = re.fullmatch(r"Comment (\d+) (kept|removed) (\".*\")", line)
        res.append((int(m.group(1)), go_unquote(m.group(3)), m.group(2) == "kept"))
    return res


_IDENT_LINE = re.compile(r"^(\d+) Ident Name=(\S+)( Decl)?$")


def map_go_ast(lines: list[str], idmap: dict) -> list[str]:
    out = []
    for x in lines:
        m = _IDENT_LINE.match(x)
        out.append(f"{m.group(1)} Ident Name={idmap.get(m.group(2), m.group(2))}{m.group(3) or ''}" if m else x)
    return out


_GO_ESC = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"'}


def go_unquote(q: str) -> str:
    """The value of a Go string or rune literal (interpreted, raw, or %q's output)."""
    if q.startswith("`"):
        return q[1:-1].replace("\r", "")
    body, out, i = q[1:-1], [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        e = body[i + 1]
        if e in _GO_ESC:
            out.append(_GO_ESC[e])
            i += 2
        elif e in "xuU":
            w = {"x": 2, "u": 4, "U": 8}[e]
            out.append(chr(int(body[i + 2:i + 2 + w], 16)))
            i += 2 + w
        elif e in "01234567":
            out.append(chr(int(body[i + 1:i + 4], 8)))
            i += 4
        else:
            raise ValueError(f"bad escape in {q!r}")
    return "".join(out)


_SEL_LINE = re.compile(r"^(\d+) SelectorExpr$")
_IMPORT_LINE = re.compile(r"^(\d+) ImportSpec\b")
_STRING_LINE = re.compile(r"^(\d+) BasicLit Kind=STRING Value=(\".*\")$")


def go_facts(lines: list[str]) -> dict:
    """What rule N1 reads from the printer's lines: the package-clause name, the identifiers (every Ident), the declared
    ones (Decl), the words of the values of the string and rune literals, the words of the kept comments, and cgo: when
    the file imports "C" (an ImportSpec whose path literal is "C"), every name X of a selector expression C.X (a
    SelectorExpr line followed by the lines of its two Ident children, C and X, one level deeper), else nothing."""
    idents, decls, strs, kept, pkg, sel, imports_c = set(), set(), set(), set(), None, set(), False
    for i, x in enumerate(lines):
        m = _SEL_LINE.match(x)
        if m and i + 2 < len(lines):
            a, b = _IDENT_LINE.match(lines[i + 1]), _IDENT_LINE.match(lines[i + 2])
            d = int(m.group(1)) + 1
            if a and b and int(a.group(1)) == d and int(b.group(1)) == d and a.group(2) == "C":
                sel.add(b.group(2))
        m = _IMPORT_LINE.match(x)
        if m:
            for y in lines[i + 1:i + 3]:
                k = _STRING_LINE.match(y)
                if k and int(k.group(1)) == int(m.group(1)) + 1 and go_unquote(go_unquote(k.group(2))) == "C":
                    imports_c = True
        m = _IDENT_LINE.match(x)
        if m:
            idents.add(m.group(2))
            if m.group(3):
                decls.add(m.group(2))
            if pkg is None and m.group(1) == "1":
                pkg = m.group(2)
            continue
        m = re.match(r"^\d+ BasicLit Kind=(STRING|CHAR) Value=(\".*\")$", x)
        if m:
            strs |= words(go_unquote(go_unquote(m.group(2))).encode("utf-8", errors="replace"))
            continue
        m = re.match(r"^(?:Directive at=\d+|CgoPreamble) (\".*\")$", x)
        if m:
            kept |= words(go_unquote(m.group(1)).encode("utf-8", errors="replace"))
    return {"package": pkg, "idents": idents, "decls": decls, "string_words": strs, "kept_words": kept,
            "cgo": sel if imports_c else set()}


# ---------------------------------------------------------------------------------------------- rule N3: Solidity
def solc_bin() -> Path:
    """The pinned solc 0.8.24 (sha256 SOLC_SHA256): the first existing of $HOLON_SOLC, config/holon.json's replay.solc
    (a candidate path only) and ~/.holon/solc-0.8.24 (tools/setup_env.sh --solc). Missing or wrong bytes: a failure,
    never a skip."""
    cfg = _m4.load_json(ROOT / "config" / "holon.json").get("replay", {})
    for c in (os.environ.get("HOLON_SOLC"), cfg.get("solc"), str(Path.home() / ".holon" / "solc-0.8.24")):
        if c and Path(c).exists():
            if sha256_file(Path(c)) != SOLC_SHA256:
                raise AssertionError(f"{c} is not the pinned solc (its sha256 is not SOLC_SHA256)")
            return Path(c)
    raise AssertionError("the pinned solc 0.8.24 is missing: run tools/setup_env.sh --solc (or set HOLON_SOLC)")


_SOL_OPS = sorted([">>>=", "<<=", ">>=", ">>>", "**", "==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=",
                   "/=", "%=", "|=", "&=", "^=", "<<", ">>", "=>", "->", ":="], key=len, reverse=True)
_SOL_NUM = re.compile(r"0[xX][0-9a-fA-F_]*|(?:[0-9][0-9_]*(?:\.[0-9][0-9_]*)?|\.[0-9][0-9_]*)(?:[eE]-?[0-9_]+)?")
_SOL_ID = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


def _sol_string_end(src: str, i: int) -> int:
    """The end of the string literal whose opening quote is at i (escapes skipped; an unterminated one ends before the
    newline or at the end of the text)."""
    q, j = src[i], i + 1
    while j < len(src) and src[j] not in (q, "\n"):
        j += 2 if src[j] == "\\" else 1
    return j + 1 if j < len(src) and src[j] == q else min(j, len(src))


def sol_lex(src: str) -> list[tuple[str, str, int, int]]:
    """An independent Solidity lexer (neither solc's nor the renaming tool's): (kind, text, start, end), kind id, num,
    str (a string or unicode string literal, one token), hex (a hex literal, one token), op, or comment (// to the end
    of the line, or /* to */). Whitespace is skipped; any other character is a one-character op."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n\f\v":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
        else:
            j = None
        if j is not None:
            out.append(("comment", src[i:j], i, j))
            i = j
            continue
        if c in "\"'":
            j = _sol_string_end(src, i)
            out.append(("str", src[i:j], i, j))
            i = j
            continue
        m = _SOL_ID.match(src, i)
        if m:
            j = m.end()
            if m.group(0) in ("hex", "unicode") and j < n and src[j] in "\"'":
                k = _sol_string_end(src, j)
                out.append(("hex" if m.group(0) == "hex" else "str", src[i:k], i, k))
                i = k
                continue
            out.append(("id", m.group(0), i, j))
            i = j
            continue
        m = _SOL_NUM.match(src, i)
        if m and m.end() > i:
            out.append(("num", m.group(0), i, m.end()))
            i = m.end()
            continue
        op = next((o for o in _SOL_OPS if src.startswith(o, i)), c)
        out.append(("op", op, i, i + len(op)))
        i += len(op)
    return out


def sol_kept(comment: str) -> bool:
    """Rule N1: a Solidity comment kept verbatim (it holds an @solidity or @custom: NatSpec tag)."""
    return "@solidity" in comment or "@custom:" in comment


def sol_tokens(src: str, idmap: dict | None = None) -> list[tuple[str, str]]:
    """The token stream rule N3 compares: (kind, text) of every token, kept comments in place and every other comment
    skipped; identifiers renamed through idmap when given."""
    m = idmap or {}
    return [(k, m.get(t, t) if k == "id" else t) for k, t, _, _ in sol_lex(src) if k != "comment" or sol_kept(t)]


def sol_neutralise(src: str) -> str:
    """The text solc parses (rule N3): every `pragma solidity <expr>;` rewritten to `pragma solidity >=0.0.0;` (solc
    0.8.24 exits 1 on an unsatisfied version pragma even with --stop-after parsing)."""
    toks = sol_lex(src)
    out, last = [], 0
    for i, (k, t, s, _) in enumerate(toks):
        if k == "id" and t == "pragma" and s >= last and i + 1 < len(toks) and toks[i + 1][:2] == ("id", "solidity"):
            end = next((x for x in toks[i + 2:] if x[:2] == ("op", ";")), None)
            if end is not None:
                out += [src[last:s], "pragma solidity >=0.0.0;"]
                last = end[3]
    out.append(src[last:])
    return "".join(out)


_SOL_DROP = {"src", "nativeSrc", "id", "nameLocation", "nameLocations", "memberLocation", "keyNameLocation",
             "valueNameLocation", "documentation", "license", "referencedDeclaration", "scope",
             "overloadedDeclarations", "assignments", "absolutePath", "exportedSymbols", "nodes_order",
             "contractDependencies", "usedErrors", "usedEvents", "linearizedBaseContracts", "baseFunctions",
             "externalReferences"}


def _sol_text(path: Path) -> str:
    return Path(path).read_bytes().decode("utf-8", errors="surrogateescape")


def sol_ast(path: Path):
    """The parse-only AST of one Solidity file from the pinned solc (None when it does not parse), parsed from a
    temporary copy with its version pragmas neutralised (sol_neutralise); source locations, node ids, comments and
    references dropped (_SOL_DROP)."""
    exe = solc_bin()
    tmp = Path(tempfile.mkdtemp(prefix="i48_sol_"))
    try:
        (tmp / "Input.sol").write_bytes(sol_neutralise(_sol_text(path)).encode("utf-8", errors="surrogateescape"))
        p = subprocess.run([str(exe), "--stop-after", "parsing", "--ast-compact-json", "Input.sol"], cwd=tmp,
                           capture_output=True, text=True, timeout=600)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    i = p.stdout.find("{")
    if p.returncode != 0 or i < 0:
        return None
    tree = json.loads(p.stdout[i:p.stdout.rfind("}") + 1])

    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in sorted(x.items()) if k not in _SOL_DROP}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return strip(tree)


_SOL_NAMED = {"name", "memberName", "functionName", "eventName", "errorName", "local", "unitAlias", "names", "keyName",
              "valueName"}


def map_sol_ast(tree, idmap: dict):
    """The AST with every name-bearing string field renamed through the map (names, member names, import aliases,
    named-argument names, named mapping keys and values, dotted paths of identifiers)."""
    def m(x, key=None):
        if isinstance(x, dict):
            return {k: m(v, k) for k, v in x.items()}
        if isinstance(x, list):
            return [m(v, key) for v in x]
        if isinstance(x, str) and key in _SOL_NAMED:
            return ".".join(idmap.get(part, part) for part in x.split("."))
        return x
    return m(tree)


_SOL_DECL = {"ContractDefinition", "FunctionDefinition", "ModifierDefinition", "VariableDeclaration",
             "StructDefinition", "EnumDefinition", "EnumValue", "UserDefinedValueTypeDefinition", "EventDefinition",
             "ErrorDefinition", "YulTypedName", "YulFunctionDefinition"}


def sol_facts(tree) -> dict:
    """What rule N1 reads from a parse-only AST: the declared names (contracts, interfaces, libraries, functions,
    modifiers, variables and parameters, structs and members, enums and values, user-defined value types, events,
    errors, import aliases, Yul variables and functions), the ABI-visible names (public or external functions, public
    state variables, events, errors) and the names of functions and modifiers declared override. A parse-only AST
    marks no variable as a state variable (stateVariable is set by analysis), so a public variable is any variable
    declared public (only state variables can be)."""
    decl, abi, over = set(), set(), set()

    def walk(x):
        if isinstance(x, dict):
            t, name = x.get("nodeType"), x.get("name")
            if t in _SOL_DECL and isinstance(name, str) and name:
                decl.add(name)
            if t == "ImportDirective":
                decl.update(a["local"] for a in x.get("symbolAliases") or [] if a.get("local"))
                if x.get("unitAlias"):
                    decl.add(x["unitAlias"])
            if (t == "FunctionDefinition" and x.get("visibility") in ("public", "external") and name) or \
                    (t == "VariableDeclaration" and x.get("visibility") == "public") or \
                    t in ("EventDefinition", "ErrorDefinition"):
                abi.add(name)
            if t in ("FunctionDefinition", "ModifierDefinition") and x.get("overrides") is not None and name:
                over.add(name)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(tree)
    return {"decls": decl, "abi": abi, "override": over}


_SOL_ESC = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "'": "'", '"': '"', "\n": ""}


def sol_unquote(lit: str) -> str:
    """The value of a Solidity string or unicode string literal."""
    body = lit[len("unicode"):] if lit.startswith("unicode") else lit
    body = body[1:-1] if len(body) >= 2 and body[-1] == body[0] else body[1:]
    out, i = [], 0
    while i < len(body):
        if body[i] != "\\" or i + 1 >= len(body):
            out.append(body[i])
            i += 1
            continue
        e = body[i + 1]
        if e in "xu":
            w = 2 if e == "x" else 4
            try:
                out.append(chr(int(body[i + 2:i + 2 + w], 16)))
                i += 2 + w
                continue
            except ValueError:
                pass
        out.append(_SOL_ESC.get(e, e))
        i += 2
    return "".join(out)


def sol_facts_text(src: str) -> dict:
    """What rule N1 reads from a Solidity file's text: its identifier tokens, the words of the values of its string and
    unicode string literals (hex literals aside), the words of its kept comments, and its comments (offset, text,
    kept), offsets in bytes of the UTF-8 text."""
    ids, strs, kept, comments = set(), set(), set(), []
    for k, t, s, _ in sol_lex(src):
        if k == "id":
            ids.add(t)
        elif k == "str":
            strs |= words(sol_unquote(t).encode("utf-8", errors="surrogateescape"))
        elif k == "comment":
            off = len(src[:s].encode("utf-8", errors="surrogateescape"))
            comments.append((off, t, sol_kept(t)))
            if sol_kept(t):
                kept |= words(t.encode("utf-8", errors="surrogateescape"))
    return {"idents": ids, "string_words": strs, "kept_words": kept, "comments": comments}


# ---------------------------------------------------------------------------------------------- rules N1-N3: one entry
def n1_facts(root: Path, files: list[str], protocol: dict) -> dict:
    """What rule N1 reads from a checkout (the --root the tool saw) and the set of files: the languages; the reserved
    names (with the package-clause names and the cgo selector names of the set's Go files); the tree's words; the words
    that block a name: those of the files outside the set (Go: every file of a directory holding a .go file of the set;
    Solidity: every .sol file) and, rule N1 (e), those of every .sol file of the set that the pinned solc cannot parse
    (unparsed); and per set file its identifiers, declared names, ABI-visible and override names, string-literal words
    and kept-comment words. expected is N1's renamed set, exact for every set; a declared name holding a dot is never in
    it."""
    root = Path(root)
    langs = sorted({language_of(f, protocol) for f in files})
    per, pkgs, cgo, unparsed = {}, set(), set(), []
    for f in files:
        if f.endswith(".go"):
            lines = go_ast(root / f)
            if lines is None:
                raise AssertionError(f"{f} does not parse with go/parser")
            g = go_facts(lines)
            pkgs.add(g["package"])
            cgo |= g["cgo"]
            per[f] = {"idents": g["idents"], "decls": g["decls"], "abi": set(), "override": set(),
                      "strings": g["string_words"], "kept": g["kept_words"]}
        else:
            t = sol_facts_text(_sol_text(root / f))
            tree = sol_ast(root / f)
            if tree is None:
                unparsed.append(f)
            a = sol_facts(tree) if tree is not None else {"decls": set(), "abi": set(), "override": set()}
            per[f] = {"idents": t["idents"], "decls": a["decls"], "abi": a["abi"], "override": a["override"],
                      "strings": t["string_words"], "kept": t["kept_words"]}
    names, pats = reserved(langs, pkgs, cgo)
    everything = tree_files(root)
    go_dirs = {PurePosixPath(f).parent.as_posix() for f in files if f.endswith(".go")}
    others = [x for x in everything if x not in files and (PurePosixPath(x).parent.as_posix() in go_dirs
                                                           or ("solidity" in langs and x.endswith(".sol")))]
    blocked = set().union(*[words((root / x).read_bytes()) for x in others + unparsed])
    tree_words = set().union(*[words((root / x).read_bytes()) for x in everything])
    union = lambda k: set().union(*[v[k] for v in per.values()])
    idents, declared = union("idents"), union("decls")
    off = union("abi") | union("override") | union("strings") | union("kept") | blocked

    def ok(x: str) -> bool:   # MINOR 4: a dotted name (a pre-0.7 Yul identifier) is never renamed
        return not is_reserved(x, names, pats) and x not in off and "." not in x \
            and not ("go" in langs and upper_initial(x))
    return {"langs": langs, "reserved": (names, pats), "tree_words": tree_words, "per": per,
            "unparsed": sorted(unparsed), "expected": {x for x in declared if ok(x)},
            "candidates": len({x for x in idents if not is_reserved(x, names, pats)})}


def _comment_key(c: dict) -> tuple:
    """A map comment as rule N3 compares it: a Go comment's text without carriage returns (go/scanner strips them from
    the printer's comment text; the map keeps the original bytes), a Solidity comment's text as it is."""
    t = c.get("text", "")
    return (c.get("path", ""), c.get("offset", -1), t.replace("\r", "") if c.get("path", "").endswith(".go") else t,
            c.get("replaced_by"))


def check_renaming(src: Path, out: Path, back: Path, files: list[str], seed: str, m: dict, protocol: dict,
                   old_lines: dict) -> dict:
    """Rules N0-N3 on one entry: src the checkout the tool renamed (--root), out its renamed files, back the unrenamed
    ones, m the map, old_lines {path: changed_old_lines}. Returns roundtrip and iso (one bool per file), problems (each
    rule N0/N1 violation, named), and the data: renamed, candidates, on_changed_lines, files_by_ast, files_by_tokens."""
    src, out, back = Path(src), Path(out), Path(back)
    nf = n1_facts(src, files, protocol)
    ids = m.get("identifiers", {})
    problems = []
    if m.get("map_version") != "holon-rename/0.1" or m.get("seed") != seed:
        problems.append("N0: map_version or seed")
    want_files = [{"path": f, "language": language_of(f, protocol), "sha256": sha256_file(src / f),
                   "renamed_sha256": sha256_file(out / f) if (out / f).exists() else None} for f in sorted(files)]
    if sorted(m.get("files", []), key=lambda x: x.get("path", "")) != want_files:
        problems.append("N0: files (path, language, sha256, renamed_sha256)")
    if list(ids) != sorted(ids):
        problems.append("N0: identifiers not sorted")
    names, pats = nf["reserved"]
    bad = sorted(x for x in ids if is_reserved(x, names, pats))
    if bad:
        problems.append(f"N1 (b): reserved names renamed: {bad[:10]}")
    if set(ids) != nf["expected"]:
        problems.append(f"N1: renamed set differs: extra {sorted(set(ids) - nf['expected'])[:10]}, "
                        f"missing {sorted(nf['expected'] - set(ids))[:10]}")
    if ids != new_names(seed, ids, nf["tree_words"]):
        problems.append("N1: new names are not new_names(seed, renamed, words of the tree)")
    want_comments = []
    for f in sorted(files):
        if f.endswith(".go"):
            cs = go_comments(src / f) or []
        else:
            cs = sol_facts_text(_sol_text(src / f))["comments"]
        want_comments += [{"path": f, "offset": o, "text": t, "replaced_by": replaced_by(t)} for o, t, k in cs if not k]
        kept = [t for _, t, k in cs if k]
        if f.endswith(".go"):
            got = go_comments(out / f)
            got = None if got is None else [t for _, t, _ in got]
        else:
            got = [t for _, t, _ in sol_facts_text(_sol_text(out / f))["comments"]] if (out / f).exists() else None
        if got != kept:
            problems.append(f"N1: {f}: the renamed file's comments are not exactly the original's kept ones")
    mc = m.get("comments", [])
    if sorted(map(_comment_key, mc)) != sorted(map(_comment_key, want_comments)):
        problems.append("N0: comments (path, offset, text, replaced_by) are not the original's removed comments")
    for c in mc:   # MINOR 7: the map's text is the original's bytes at its offset
        f, o, t = c.get("path"), c.get("offset"), c.get("text")
        if f in files and isinstance(o, int) and isinstance(t, str):
            raw = t.encode("utf-8", errors="surrogateescape")
            if (src / f).read_bytes()[o:o + len(raw)] != raw:
                problems.append(f"N0: {f}: the map's comment at {o} is not the original's bytes")
    res = {"roundtrip": [], "iso": [], "problems": problems, "renamed": len(ids), "candidates": nf["candidates"],
           "files_by_ast": 0, "files_by_tokens": 0}
    hit = set()
    for f in files:
        data = (src / f).read_bytes()
        res["roundtrip"].append((back / f).exists() and (back / f).read_bytes() == data)
        lines = data.split(b"\n")
        for n in old_lines.get(f, []):
            if 1 <= n <= len(lines):
                hit |= words(lines[n - 1]) & set(ids)
        if not (out / f).exists():
            res["iso"].append(False)
            continue
        if f.endswith(".go"):
            a, b = go_ast(src / f), go_ast(out / f)
            res["iso"].append(a is not None and b is not None and map_go_ast(a, ids) == b)
            res["files_by_ast"] += 1
        else:
            ta, tb = sol_tokens(_sol_text(src / f), ids), sol_tokens(_sol_text(out / f))
            a, b = sol_ast(src / f), sol_ast(out / f)
            res["iso"].append(ta == tb and (a is None) == (b is None) and (a is None or map_sol_ast(a, ids) == b))
            res["files_by_ast" if a is not None else "files_by_tokens"] += 1
    res["on_changed_lines"] = len(hit)
    return res
