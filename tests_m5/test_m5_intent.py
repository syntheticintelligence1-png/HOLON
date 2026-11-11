"""I55: the intent lane (BUILD_PLAN §4 I55; whitepaper §5.10, §5.4 route (i), §11.3 O10, §12 row L10). This docstring
is the contract that tests_m5/test_m5_intent.py checks.

The design is thresholds.design of the key I55 (spec/M5/predictions/I55.json), immutable under the prereg audit. L10 is
measured by I54's definition (spec/M5/preregistration.json definitions.L10); I55 restates and moves none of its
thresholds. Instruments fixed at the prereg, pinned by sha256 in PINNED: tests_m5/_i55.py (the closure, span, input,
trivially-true and route checks, written apart from holon/intent), spec/M5/lib/intent.schema.json,
spec/M5/lib/intent_review_prompt.md and prompts/I55_intent_lane.md. The census and the twelve control files are pinned
by the key (census_sha256, controls_sha256), so truth cannot follow the outputs (I54 common.truth_pinning).

Rules (tests below; the key's design holds the full text)
  N1 The instruments are the preregistered ones; the key pins the census and the controls at their current bytes.
  A1 `python -m holon intent atomize --check` exits 0: results/M5/intent/atoms.json is the atomizer's output; it is an
     atoms_document; its scope equals the census's scope (the same rule, computed by the lane, never read from the
     census) and its scope_commit is the key's.
  A2 Every atom's pieces are exact substrings of its file at its commit (a control: its pinned bytes) and rebuild its
     text; lines are the pieces' range; decl is the documented line; ids are unique.
  A3 (the lead's G2(a)) The atomizer never reads the census: its static closure holds no holon.m5 module and no file
     naming the census (I1a); under an audit hook its run opens, passes and writes nothing naming l10_census (I1b);
     with the census file deleted (a git worktree of HEAD) it writes the same bytes (I1c).
  A4 I2: compile and run never read a control's .json or the census (audit hook); no module of holon/intent names
     'right' or 'wrong' (a control's file stem carries its truth; the lane uses an id only as an opaque label).
  C1 `python -m holon intent compile --check` exits 0: laws/INTENT/ (each an intent_law naming exactly one atom
     clause, its id L_intent_<that atom's id>), laws/INTENT/REGISTRY.json (statement hashes) and
     results/M5/intent/compile.json (one compile_entry per atom, target and control) are the compiler's output.
  C2 Every generated .bend file under gen/M5/intent/ is free of escape hatches (holon.bend.escape_hatches and the
     G3 patterns), and every LAWS.bend states exactly its law.
  R1 Every law has exactly one record (spec/M5/lib/intent.schema.json#/$defs/record); a PROVED or REFUTED record's
     proof file re-checks with Bend now (ALL PROOFS CHECK, exit 0) and states its law (law_id lower-cased, or cl_ +
     it); an UNKNOWN record has a bound and attempts. REFUTED records carry the witness.
  R2 `python -m holon intent run --check` exits 0: a fresh run into a temporary directory gives the same records and
     generated files byte for byte (determinism).
  V1 spec/M5/intent/reviews.json is a reviews document: reviewer other than compiler, the pinned prompt's sha256, the
     requests' sha256; each record's review is what it gives (absent when missing).
  V2 results/M5/intent/review_requests.json holds exactly one request per law, the fields of design V, and no control
     id or truth word.
  M1 results/M5/intent/l10_inputs.json equals tests_m5/_i55.l10_inputs; results/M5/intent/l10.json's l10 equals
     holon.m5.metrics.l10 and tests_m5/_i54.l10 on it; its trivially_true equals tests_m5/_i55.trivially_true;
     corpus_recall is not_measured; `python -m holon intent metrics --check` exits 0.
  M2 results/M5/intent/obstructions.json lists exactly the records with status REFUTED passing W1 and W2.
  Y1 results/M5/intent/sym_route_i.json equals tests_m5/_i55.route_i.

Predictions (I55-P1..P11; outcomes recorded nowhere before the build): the clause count; precision; recall; the
controls' atoms and laws; control_recall; the right controls' statuses and false_obstruction; trivially-true control
laws; the target's matches, laws and coverage; O10's doc-drift candidates; the review rate and the overall verdict;
route (i). A miss is a Surprise, never a reason to edit anything.

Gaps preregistered
  E-I1 Same author. The atomizer, the compiler, the model generator and this instrument are written by one session.
       The independent parts are the census (I54), the controls' truth (I54) and the reviewer.
  E-I2 The templates are the control families' phrasing. Three templates match the three control families' sentences
       (E-G2: constructed truth is public); their binding rules are generic, and the target's clauses are what show
       how far they reach (P8).
  E-I3 The model is the lane's own. It is generated from the factory's extracted transitions document, but the lane's
       model generator is new; a wrong model can make a wrong REFUTED. The controls bound this (false_obstruction),
       and no witness is replayed on the real code in I55.
  E-I4 The reviewer is of the builder's family (one fresh session), disclosed in the reviews file.
  E-I5 The builder read the census before the prereg (it is I54's committed output) to name P9's candidates; the
       atomizer's code never reads it (A3).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m5 import _i54 as I54
from tests_m5 import _i55 as I
from tests_m5._m5 import ROOT, dumps, file_sha256, holon_module, load_json, predictions, validate

KEY = "I55"
PINNED = {
    "prompts/I55_intent_lane.md": "f5dc0292e5d1c20e0d13fbce829cb4066b38682fec440173b0d4b43375ac80c2",
    "spec/M5/lib/intent.schema.json": "26d12c7f306120723445d004bd16a6284e1c4ecfeeefb5df49b864ebbf6ea104",
    "spec/M5/lib/intent_review_prompt.md": "7635edd86a9bf9222af93e7b110f15f02e6931f21d1dd749d3aacd3b26af1d04",
    "tests_m5/_i55.py": "b93bc8ba30d013fb29f0b21c4ec68312bff5212de3288c0e9565d9403de44720",
}
OUT = ROOT / "results" / "M5" / "intent"
LAWS = ROOT / "laws" / "INTENT"
GEN = ROOT / "gen" / "M5" / "intent"


def key() -> dict:
    return predictions(KEY)


def design() -> dict:
    return key()["thresholds"]["design"]


def schema() -> dict:
    return load_json(ROOT / "spec" / "M5" / "lib" / "intent.schema.json")


def sub(name: str) -> dict:
    s = schema()
    return {"$defs": s["$defs"], **s["$defs"][name]}


def holon(*args: str, cwd: Path = ROOT, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


HOOK = r'''
import json, runpy, subprocess, sys
log = []
def hook(ev, args):
    if ev == "open":
        log.append(["open", str(args[0])])
    elif ev == "subprocess.Popen":
        log.append(["exec", [str(a) for a in (args[1] if isinstance(args[1], (list, tuple)) else [args[1]])]])
sys.addaudithook(hook)
_comm = subprocess.Popen.communicate
def communicate(self, input=None, *a, **k):
    if input is not None:
        log.append(["stdin", input if isinstance(input, str) else bytes(input).decode("utf-8", "replace")])
    return _comm(self, input, *a, **k)
subprocess.Popen.communicate = communicate
out = sys.argv[1]
sys.argv = ["holon"] + sys.argv[2:]
code = 0
try:
    runpy.run_module("holon", run_name="__main__", alter_sys=True)
except SystemExit as e:
    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
finally:
    with open(out, "w") as f:
        json.dump({"code": code, "log": log}, f)
'''


def audited(*args: str, cwd: Path = ROOT) -> dict:
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / "log.json"
        subprocess.run([sys.executable, "-c", HOOK, str(log), *args], cwd=cwd, capture_output=True, text=True,
                       timeout=3600)
        return load_json(log)


def mentions(log: list, pat: str) -> list:
    rx = re.compile(pat)
    return [e for e in log if rx.search(json.dumps(e[1]))]


def atoms_doc() -> dict:
    return load_json(OUT / "atoms.json")


def records() -> list[dict]:
    return I.records(ROOT)


def by_control() -> dict:
    return {r["control"]: r for r in records() if r["control"] is not None}


def truth() -> dict:
    return {c["id"]: c["truth"]["obstruction"] for c in I.control_documents(ROOT)}


def git(*args, cwd=ROOT) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True).stdout


class TestPreregistration(unittest.TestCase):
    def test_instruments_are_the_preregistered_ones(self):  # N1
        for p, h in sorted(PINNED.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        th = key()["thresholds"]
        self.assertEqual(sorted(PINNED), sorted(th["instruments"]))
        self.assertEqual(th["census_sha256"], file_sha256(ROOT / I.CENSUS))
        ctl = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / I.CONTROLS).glob("i_*"))
        self.assertEqual(len(ctl), 24)
        self.assertEqual(th["controls_sha256"], {p: file_sha256(ROOT / p) for p in ctl})
        self.assertEqual(th["scope_commit"], I.SCOPE_COMMIT)
        self.assertTrue({"A4_normative", "I1_independence", "TT_trivially_true", "V_review", "L1_inputs"} <= set(design()))


class TestAtomizer(unittest.TestCase):
    def test_atomize_check(self):  # A1
        r = holon("intent", "atomize", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = atoms_doc()
        self.assertEqual(validate(d, sub("atoms_document")), [])
        self.assertEqual(d["scope_commit"], I.SCOPE_COMMIT)
        census = load_json(ROOT / I.CENSUS)
        self.assertEqual(d["scope"], census["repos"])
        self.assertTrue(d["atoms"] and all(a["control"] is None for a in d["atoms"]))
        self.assertTrue(all(a["control"] is not None and a["commit"] is None for a in d["controls"]))

    def test_spans_are_exact(self):  # A2
        d = atoms_doc()
        src = load_json(ROOT / "config" / "holon.json")["extract"]["sources"]
        ids = [a["id"] for a in d["atoms"] + d["controls"]]
        self.assertEqual(len(ids), len(set(ids)))
        cache = {}
        for a in d["atoms"] + d["controls"]:
            k = (a["repo"], a["commit"], a["file"])
            if k not in cache:
                if a["commit"] is None:
                    cache[k] = (ROOT / a["file"]).read_text(encoding="utf-8").split("\n")
                else:
                    cache[k] = git("show", f"{a['commit']}:{a['file']}", cwd=Path(src[a["repo"]])).decode(
                        "utf-8").split("\n")
            self.assertEqual(I.span_problems(a, cache[k]), [], a["id"])

    def test_atomizer_never_reads_the_census(self):  # A3 (G2(a))
        self.assertEqual(I.closure_problems("holon.intent.atomize"), [])
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "atoms.json"
            got = audited("intent", "atomize", "--out", str(out))
            self.assertEqual(got["code"], 0)
            self.assertEqual(mentions(got["log"], "l10_census"), [])
            self.assertEqual(out.read_bytes(), (OUT / "atoms.json").read_bytes())
        with tempfile.TemporaryDirectory() as d:
            wt = Path(d) / "wt"
            git("worktree", "add", "--detach", str(wt), "HEAD")
            try:
                (wt / I.CENSUS).unlink()
                out = Path(d) / "atoms.json"
                r = holon("intent", "atomize", "--root", str(wt), "--out", str(out), cwd=wt)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(out.read_bytes(), (OUT / "atoms.json").read_bytes())
            finally:
                git("worktree", "remove", "--force", str(wt))

    def test_compile_and_run_are_truth_blind(self):  # A4 (I2)
        # a control's file stem carries its truth (_right_ / _wrong_): the lane's code may treat an id only as an
        # opaque label, so no module of holon/intent names either word
        mods = sorted((ROOT / "holon" / "intent").rglob("*.py"))
        self.assertTrue(mods)
        for f in mods:
            self.assertIsNone(re.search(r"(?i)(?<![a-z])(wrong|right)(?![a-z])", f.read_text(encoding="utf-8")), f)
        with tempfile.TemporaryDirectory() as d:
            for cmd in (["intent", "compile", "--check"], ["intent", "run", "--check", "--tmp", d]):
                got = audited(*cmd)
                self.assertEqual(got["code"], 0, cmd)
                self.assertEqual(mentions(got["log"], r"controls/intent/i_[a-z_0-9]+\.json|l10_census"), [], cmd)


class TestCompile(unittest.TestCase):
    def test_compile_check(self):  # C1
        r = holon("intent", "compile", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = atoms_doc()
        atoms = {a["id"]: a for a in d["atoms"] + d["controls"]}
        entries = load_json(OUT / "compile.json")["entries"]
        self.assertEqual(sorted(e["atom"] for e in entries), sorted(atoms))
        for e in entries:
            self.assertEqual(validate(e, sub("compile_entry")), [], e["atom"])
        reg = load_json(LAWS / "REGISTRY.json")
        laws = {p.stem: load_json(p) for p in sorted(LAWS.glob("L_intent_*.json"))}
        self.assertEqual(sorted(reg), sorted(laws))
        compiled = sorted(e["law_id"] for e in entries if e["outcome"] == "compiled")
        self.assertEqual(compiled, sorted(laws))
        ir = holon_module("holon.intent.ir")
        for lid, lw in laws.items():
            self.assertEqual(validate(lw, sub("intent_law")), [], lid)
            self.assertEqual(len(lw["clauses"]), 1, lid)
            self.assertEqual(lid, "L_intent_" + lw["clauses"][0])
            self.assertIn(lw["clauses"][0], atoms)
            self.assertEqual(lw["control"], atoms[lw["clauses"][0]]["control"])
            self.assertEqual(I.term_problems(lw["statement"]["holds"], {b["name"] for b in lw["statement"]["binders"]}),
                             [], lid)
            self.assertEqual(reg[lid], ir.statement_hash(lw), lid)

    def test_generated_bend_is_clean(self):  # C2
        bend = holon_module("holon.bend")
        files = sorted(GEN.rglob("*.bend"))
        self.assertTrue(files)
        pats = [r"@unsafe", r"def\s+[A-Za-z0-9_.]+\?\s*\(", r"\?[A-Za-z_]", r'import\s+"']
        for f in files:
            t = f.read_text(encoding="utf-8")
            self.assertEqual(bend.escape_hatches(t), [], f)
            for p in pats:
                self.assertIsNone(re.search(p, t), (f, p))
            if f.name == "LAWS.bend":
                names = re.findall(r"(?<![\w.])law\s+([A-Za-z0-9_.]+)\s*:", t)
                lid = f.parent.name
                self.assertIn(names, ([lid.lower()], ["cl_" + lid.lower()]), f)


class TestRun(unittest.TestCase):
    def test_records(self):  # R1
        laws = sorted(p.stem for p in LAWS.glob("L_intent_*.json"))
        recs = records()
        self.assertTrue(laws)
        self.assertEqual(sorted(r["law_id"] for r in recs), laws)
        bend = holon_module("holon.bend")
        for r in recs:
            self.assertEqual(validate(r, sub("record")), [], r["law_id"])
            if r["status"] in ("PROVED", "REFUTED"):
                want = r["law_id"].lower() if r["status"] == "PROVED" else "cl_" + r["law_id"].lower()
                self.assertEqual(r["evidence"], {"law": want, "marker": I54.CHECKED, "law_present": True})
                proof = ROOT / r["paths"]["proof"]
                laws_text = (proof.parent / "LAWS.bend").read_text(encoding="utf-8")
                self.assertEqual(re.findall(r"(?<![\w.])law\s+([A-Za-z0-9_.]+)\s*:", laws_text), [want])
                run = bend.check(proof)
                self.assertTrue(run.ok, (r["law_id"], run.out[:500]))
            else:
                self.assertTrue(r["bound"] and r["attempts"], r["law_id"])
            if r["status"] == "REFUTED":
                self.assertIsInstance(r["witness"], dict)

    def test_run_is_deterministic(self):  # R2
        with tempfile.TemporaryDirectory() as d:
            r = holon("intent", "run", "--check", "--tmp", d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestReview(unittest.TestCase):
    def test_reviews(self):  # V1
        rv = load_json(ROOT / "spec" / "M5" / "intent" / "reviews.json")
        self.assertEqual(validate(rv, sub("reviews")), [])
        self.assertNotEqual(rv["reviewer"], rv["compiler"])
        self.assertEqual(rv["compiler"], I.COMPILER)
        self.assertEqual(rv["prompt_sha256"], file_sha256(ROOT / "spec" / "M5" / "lib" / "intent_review_prompt.md"))
        same = rv["requests_sha256"] == file_sha256(OUT / "review_requests.json")
        for r in records():
            v = rv["verdicts"].get(r["law_id"]) if same else None
            self.assertEqual(r["review"], {"reviewer": rv["reviewer"], "compiler": rv["compiler"],
                                           "verdict": v["verdict"] if v else "absent"}, r["law_id"])

    def test_requests(self):  # V2
        req = load_json(OUT / "review_requests.json")["requests"]
        self.assertEqual(sorted(q["law_id"] for q in req), sorted(r["law_id"] for r in records()))
        text = json.dumps(req)
        for c in sorted(truth()):
            self.assertNotIn(c, text)
        for w in ("obstruction", "truth", "_right_", "_wrong_"):
            self.assertNotIn(w, text)
        for q in req:
            self.assertEqual(validate(q, sub("review_request")), [], q["law_id"])


class TestMetrics(unittest.TestCase):
    def test_l10(self):  # M1
        r = holon("intent", "metrics", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        inp = load_json(OUT / "l10_inputs.json")
        self.assertEqual(inp, I.l10_inputs(ROOT))
        out = load_json(OUT / "l10.json")
        self.assertEqual(out["l10"], holon_module("holon.m5.metrics").l10(inp))
        self.assertEqual(out["l10"], I54.l10(inp))
        self.assertEqual(out["trivially_true"], I.trivially_true(ROOT))
        self.assertEqual(out["corpus_recall"]["label"], "not_measured")
        self.assertEqual(out["census_sha256"], key()["thresholds"]["census_sha256"])

    def test_obstructions(self):  # M2
        ob = load_json(OUT / "obstructions.json")
        want = sorted(r["law_id"] for r in records() if r["status"] == "REFUTED" and I._w1(r) and I._w2(r))
        self.assertEqual(sorted(ob["controls"] + ob["target"]), want)
        for r in records():
            self.assertEqual(r["obstruction"], r["law_id"] in want, r["law_id"])

    def test_route_i(self):  # Y1
        self.assertEqual(load_json(OUT / "sym_route_i.json"), I.route_i(ROOT))


class TestPredictions(unittest.TestCase):
    def l10(self):
        return load_json(OUT / "l10.json")["l10"]

    def test_p1_clause_count(self):
        lo, hi = 80, 110
        self.assertTrue(lo <= len(atoms_doc()["atoms"]) <= hi, len(atoms_doc()["atoms"]))

    def test_p2_precision(self):
        l = self.l10()
        self.assertGreaterEqual(l["precision"]["value"], 0.8)
        self.assertEqual(l["thresholds"]["precision"], "meets")

    def test_p3_recall(self):
        self.assertGreaterEqual(self.l10()["recall"]["value"], 0.9)

    def test_p4_controls_compile(self):
        d = atoms_doc()
        per = {}
        for a in d["controls"]:
            per.setdefault(a["control"], []).append(a)
        self.assertEqual(sorted(per), sorted(truth()))
        self.assertTrue(all(len(v) == 1 for v in per.values()))
        laws = [load_json(p) for p in LAWS.glob("L_intent_*.json")]
        ctl = [lw for lw in laws if lw["control"] is not None]
        self.assertEqual(sorted(lw["control"] for lw in ctl), sorted(truth()))
        fam = {}
        for lw in ctl:
            fam[lw["template"]] = fam.get(lw["template"], 0) + 1
        self.assertEqual(fam, {"bound": 4, "access": 4, "monotone": 4})

    def test_p5_control_recall(self):
        bc = by_control()
        for c, ob in sorted(truth().items()):
            if ob:
                self.assertEqual(bc[c]["status"], "REFUTED", c)
                self.assertEqual(bc[c]["review"]["verdict"], "faithful", c)
        l = self.l10()
        self.assertEqual((l["control_recall"]["numerator"], l["control_recall"]["denominator"]), (6, 6))
        self.assertEqual(l["thresholds"]["control_recall"], "meets")

    def test_p6_right_controls(self):
        bc = by_control()
        for c in ("i_access_right_1", "i_access_right_2"):
            self.assertEqual((bc[c]["status"], bc[c]["proof_class"]), ("PROVED", "bool_cases"), c)
        for c in ("i_bound_right_1", "i_bound_right_2", "i_monotone_right_1", "i_monotone_right_2"):
            self.assertEqual(bc[c]["status"], "UNKNOWN", c)
        l = self.l10()
        self.assertEqual(l["false_obstruction"], [])
        self.assertEqual(l["thresholds"]["false_obstruction"], "meets")

    def test_p7_trivially_true_controls(self):
        t = load_json(OUT / "l10.json")["trivially_true"]["controls"]
        self.assertEqual((t["numerator"], t["denominator"]), (0, 2))

    def test_p8_target(self):
        entries = load_json(OUT / "compile.json")["entries"]
        tgt = [e for e in entries if e["control"] is None]
        matched = [e for e in tgt if e["template"] is not None]
        self.assertTrue(1 <= len(matched) <= 5, len(matched))
        self.assertEqual([e for e in tgt if e["outcome"] == "compiled"], [])
        l = self.l10()
        self.assertEqual((l["coverage"]["numerator"], l["coverage"]["denominator"]), (0, 82))
        self.assertEqual(l["thresholds"]["coverage"], "misses")
        self.assertEqual(l["compiled_coverage"]["numerator"], 0)
        self.assertEqual(load_json(OUT / "l10.json")["trivially_true"]["covering"]["denominator"], 0)
        self.assertEqual(load_json(OUT / "obstructions.json")["target"], [])

    def test_p9_o10(self):
        d = atoms_doc()
        entries = {e["atom"]: e for e in load_json(OUT / "compile.json")["entries"]}
        want = {("contracts/contracts/l1/rollup/Rollup.sol", "only an active submitter"): "decl_not_function",
                ("node/derivation/tag_advance.go", "finalized never moves backwards"): "not_solidity",
                ("contracts/contracts/l1/rollup/Rollup.sol", "at most one blob is allowed"): "no_template"}
        for (f, phrase), outcome in sorted(want.items()):
            hits = [a for a in d["atoms"] if a["file"] == f and phrase in a["text"].lower()]
            self.assertEqual(len(hits), 1, (f, phrase))
            self.assertEqual(entries[hits[0]["id"]]["outcome"], outcome, (f, phrase))
        self.assertEqual(load_json(OUT / "obstructions.json")["target"], [])

    def test_p10_review_overall(self):
        l = self.l10()
        self.assertGreaterEqual(l["review"]["value"], 0.9)
        self.assertEqual(l["thresholds"]["review"], "meets")
        self.assertEqual(l["overall"], "misses")

    def test_p11_route_i(self):
        self.assertEqual(sum(s["promoted"] for s in load_json(OUT / "sym_route_i.json")["splits"]), 0)


class TestRegressions(unittest.TestCase):
    def test_i54_outputs(self):  # R1
        for p, h in sorted(key()["regressions"][0]["expected"].items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)

    def test_no_earlier_milestone_changes(self):  # R2
        base = key()["thresholds"]["base_commit"]
        paths = ["results/M0", "results/M1", "results/M2", "results/M3", "results/M4", "gen/M0", "gen/M1", "gen/M2",
                 "gen/M3", "gen/M4", "laws/M0", "laws/M1", "laws/M2", "laws/M3", "laws/CONTRACTS", "laws/T32",
                 "replay", "spec/M1", "spec/M2", "spec/M3", "spec/M4", "spec/M5/controls", "spec/M5/lib/inputs.schema.json",
                 "spec/M5/lib/environment_classes.json", "spec/M5/lib/truth_protocol.json", "spec/M5/lib/truth_prompt.md",
                 "tests_m5/_i54.py", "tests_m5/_m5.py", "tests_m5/test_m5_definitions.py", "FROZEN.sha256"]
        # I55's own commits are HEAD's first-parent chain from the base. A non-merge commit on it may change none of
        # the paths; a merge (the lead's branch or #134's, merged in) may bring only its second parent's bytes.
        chain = git("rev-list", "--first-parent", "--parents", f"{base}..HEAD").decode().split("\n")
        bad = []
        for line in filter(None, chain):
            c, *parents = line.split()
            changed = git("diff", "--name-only", parents[0], c, "--", *paths).decode().split()
            if len(parents) == 1:
                bad += [f"{c[:8]}: {f}" for f in changed]
            else:
                bad += [f"{c[:8]} (merge): {f}" for f in changed
                        if git("rev-parse", f"{c}:{f}") != git("rev-parse", f"{parents[1]}:{f}")]
        self.assertEqual(bad, [])
        fz = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertIn("FROZEN OK", fz.stdout)


if __name__ == "__main__":
    unittest.main()
