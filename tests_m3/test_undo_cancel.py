"""I71: UNDO's third sub-form, cancel (I33's catalog key; BUILD_PLAN row I71; I27's gap G5). This docstring is the
contract.

Why. I27's back-test maps M1's L_undo_cancel (challengeState undone by setPause(true): pausing cancels an open
challenge) to the extracted pair (challengeState, setPause), which I27's rules U3 and U4 do not detect: setPause writes
inChallenge back to 0 only under the condition `_status && inChallenge`, so there is no U3 restore, and its guards read
only _owner and _paused, so there is no U4 criterion. The back-test reports gaps == ["L_undo_cancel"]
(docs/iterations/I27.md, gap G5), and the O12 intent contract on M3 (I33) has no scope law. I71 adds a third UNDO
sub-form, cancel: two rules computed apart from U3 and U4 (U3' and U4'), the residues of a cancellation, and one law
per cancellation whose template compares every trace's observations after x;y with its observations after y alone
(M1's own reading of L_undo_cancel), decided by refutation on I30's typed model and replayed on the real contract.

Instrument fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i71.py (rules C1-C3 and C6's law, written a second time, independently of
holon/, on top of I27's instrument in tests_m3/test_undo.py; and the planted variants of rule C1's edge cases).

Scope and inputs. Milestone M3; the documents of the UNDO sidecar (spec/M3/lib/undo.json, I27's, unchanged), i.e.
spec/M2/facts/morph_rollup.extracted.json; the mutant tests_m3/fixtures/undo/mutant/rollup_mutant.extracted.json and
the toy documents of tests_m3/fixtures as planted documents. I27's rules U1-U6 and D1-D3, its pairs, rejected pairs,
residues, residue bases, laws and records are unchanged, and so are spec/M3/lib/undo.json and undo_basis.json.

C1 Cancel restore (U3'). ā cancel-restores a's write w (writes[i]) of the register (F, k_a) when w is whole, fresh,
   final, has cond 1 and its value is an integer literal v; a pins (F, k_a) (U2, the same key term) to a literal c != v
   at a guard reach before w; and ā has a write w' (writes[j]) of F, whole, final in ā and in no loop (no "loop"
   field), whose value is the integer literal c, at a key matching k_a (U1: both scalar, or both keyed with matching
   keys), every top-level conjunct of whose cond is a parameter of ā (["param", p]) or its negation (["!", ["param",
   p]]), or a reading of the register at w''s own key (R = ["storage", F], or ["map", ["storage", F], k_b]) holding
   v: R itself, ["!=", R, 0] or ["!=", 0, R] when F's value type is bool and v = 1; ["!", R], ["==", R, 0] or
   ["==", 0, R] when v = 0; ["==", R, v] or ["==", v, R] otherwise. Record {"family", "a_write": "writes[i]",
   "undo_write": "writes[j]", "how": "cancel", "pin": "guards[g]", "cond": w''s cond}; distinct, sorted by canonical
   JSON.
C2 Criterion cond (U4'). Some restore's cond has a conjunct that reads the register (the second kind of C1). A
   candidate (a, ā) (distinct actions, neither of mutability view or pure, at least one C1 restore) is a cancellation
   with criteria ["cond"] when C2 holds, and is rejected with reason "no_criterion" otherwise. Cancellations are
   computed apart from U3 and U4: a pair may also be a cancellation, and a cancellation adds nothing to I27's pairs,
   rejected pairs or residues.
C3 Residues and static class. The residues of a cancellation are U5's: the families of a's final writes that ā does
   not cancel-restore and that are not identity writes, sorted. Each residue family's static class is I27's D1-D3 with
   no cursor and no zero family (dead iff no live reader); a cancellation is dead iff each of its residues is dead (with
   none, dead). No residue basis and no residue law come from a cancellation (U6 bases come from pairs only).
C4 The analysis document. `holon undo --milestone M3` (and --facts) writes in gen/M3/undo/<model>.json, beside I27's
   keys, "cancellations": [{"a", "undo", "criteria", "restores", "residues", "class"}] and "rejected_cancellations":
   [{"a", "undo", "restores", "reason"}], each sorted by (a, undo); undo_version stays holon-undo/0.1 (the document
   gains two keys; I27's keys keep their content). Deterministic.
C5 The catalog. holon/rules/__init__.py: CATALOGS gains the catalog version after I28's holon-rules/1.6, i.e.
   holon-rules/1.7 (the next free version at merge; whoever merges second takes the next one and regenerates): every
   rule and producer of holon-rules/1.6, the same objects, plus UNDO's sub-form cancel, holon.rules.undo.CANCEL, a
   producer of its own: holon.rules.undo.PRODUCERS stays {pair, residue} (I27's, I31's and I26's checks that a later
   M3 catalog holds every producer of theirs as the same object keep holding). catalog_version("M3") is holon-rules/1.7
   (and every later M<k>); every earlier catalog version and M2's are unchanged. Every other M3 law file changes in
   rule_catalog_version alone, each change a catalog_rederivation line of laws/STATEMENT_DIFF.jsonl
   (`python -m holon.statement_diff recatalog --milestone M3 --append`), and spec/bindings/M3.json rebinds them.
C6 The law (L3). One law per cancellation: law id "L_undo_cancel_<contract>_<a>_<undo>"; undo id
   "<model>:cancel:<a>:<undo>"; basis {"kind": "undo_cancel", "model", "contract", "a", "undo", "criteria",
   "restores", "residues"}; holon-ir/0.3, rule UNDO, subform cancel, the document as facts; binders (s, Reach), (x,
   Act), (y, Act), (t, Trace), then the hash binders exactly as I30's laws over the document have them; assume [];
   claim {"eq": [{"undo": <undo id>, "on": [{"var": b} for each binder]}, {"bool": true}]}; scope unbounded; no
   "evidence", no "predicted". Its ref undo:<id> hashes canonical {"template": "holon.rules.undo/cancel",
   "template_version": 1, "subform": "cancel", "basis"}, recomputed from the document. DERIVATION entry: {"law_id",
   "rule": "UNDO", "subform": "cancel", "facts", "basis", "static": {"class", "residues": {family: class}},
   "statement_hash"}. spec/schemas/law_ir_0_3.schema.json's undo id pattern admits cancel (pair|residue|cancel), with
   its description, and docs/adoption/Q4/schemas/ follows it byte for byte (I64's K10).
C7 The template (holon.undo.trace). undo_<x> of a cancel law: with s1 = after(s, x), s2 = after(s1, y) and
   s3 = after(s, y): if NZ, x is a call of a, y a call of ā, x succeeds from s, y succeeds from s1 and from s, and
   every register the cancellation restores (its family at a's write key, evaluated on s and x) holds in s2 its value
   in s, then obs(t, s2) == obs(t, s3); otherwise true. uhit_<x>: the premises alone. The restore and observation
   helpers are I27's (obs, ux_rs_<x>, the registers' helpers).
C8 Deciding (holon run --milestone M3). The UNDO search (I27's budget, spec/M3/lib/undo.json unchanged) looks for x;y
   at prefixes as for a pair (y's acceptance is uhit_<x>, which includes y succeeding from s) and compares the
   continuations t from s2 and from s3; a witness {"prefix", "x", "y", "t", "hashes"} gives a counter-law that bend2
   and BendTT must check, and is accepted only when x and y succeed on the deployment in the run with x and y succeeds
   there in the run without x. No proof generator is built for the cancel sub-form: a cancel law without an accepted
   counter-law is UNKNOWN, its record naming that. The record is I27's (undo field with subform cancel, nz premises,
   witness, coverage), the filter stage (I40) gives it its bin.
   Replay (replay/M3/undo/report.json): the run with x is prefix + [x, y] + t, the run without x is prefix + [y] + t;
   "t_at" = len(prefix) + 2 and "t_at_without" = len(prefix) + 1; diverges_at indexes t; calls_agree; passed as for a
   pair. G6 binds the record to its entry by those runs.
C9 The back-test. holon.rules.undo.backtest: a pair spec of the frozen map has as analogue the pair law L1 gives, else
   the cancel law of the same (a, ā); a residue spec as before. The map (spec/M3/lib/undo.json) is unchanged.
C10 Regenerated, never hand-written, by this recipe, on I71's branch after I28's build is on the lead and merged in
   (the lead's lines first in every append-only log): holon derive --milestone M3 (holon-rules/1.7);
   python -m holon.statement_diff recatalog --milestone M3 --append; holon bind --milestone M3; holon undo --milestone
   M3; holon run --milestone M3 --laws L_undo_cancel_Rollup_challengeState_setPause; holon replay --milestone M3 (or
   the run's own report); holon undo --milestone M3 --classify --backtest; every other M3 record but I27's eight UNDO
   records (stale since I26, left as I26 and I28 left them) re-made by holon run under holon-rules/1.7 with its status
   unchanged (long runs on CI runners); holon refute --milestone M3 --only filter; holon metrics --milestone M3; and the
   M1, M2 and T32 records in generator_sha256 and seconds alone (holon run --milestone M1 and M2, holon profile
   --milestone T32), since holon/rules is in the holon-ir/0.2 and 0.3 closures.
C11 Earlier tests. At the prereg commit, I27's tests that count the UNDO laws are narrowed to I27's sub-forms (pair
   and residue), each with an amendment line: undo_laws and undo_records (helpers of tests_m3/test_undo.py) list
   the laws and records whose id is not an L_undo_cancel_ id; I27-P8's classification check compares the
   classification's I27 laws with I27's predictions (the whole classification still has no disagreement); I27-P9's
   back-test check reads L_undo_cancel's row as I27's gap row or as this key's analogue. Every other earlier test is
   unchanged; one that fails on I71's outcomes is a miss, reported.

Questions preregistered (also in the key): the template's premise "y succeeds from s" (M1's statement has none); no
proof generator for cancel laws; the catalog bump's re-make of every M3 record; U3' requires every conjunct of the
restoring condition to be a parameter (or its negation) or the register's own reading.

Rules (AGENTS.md is binding): generate, never hand-write; no target, family, action or law id under holon/; never tune
to a prediction; witnesses come from the compiled model; the real contract decides replay; no skips.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # frozen helpers
from tests.reference import mini_schema
from tests_m3 import _i71 as I
from tests_m3 import test_undo as U27

KEY = "I71"
M3 = "M3"
DOC_REL = U27.DOC_REL
MODEL = U27.MODEL
CONTRACT = U27.CONTRACT
MUTANT_REL = U27.MUTANT_REL
LAW = "L_undo_cancel_Rollup_challengeState_setPause"
UNDO_ID = f"{MODEL}:cancel:challengeState:setPause"
INSTRUMENT = "tests_m3/_i71.py"
SCHEMA = "spec/schemas/law_ir_0_3.schema.json"
Q4_SCHEMA = "docs/adoption/Q4/schemas/law_ir_0_3.schema.json"
UNDO_PATTERN = "^[A-Za-z0-9_.]+:(pair|residue|cancel):[A-Za-z0-9_]+:[A-Za-z0-9_]+$"
TOYS = ["tests_m3/fixtures/disch/a/toygate.extracted.json", "tests_m3/fixtures/disch/b/toygate.extracted.json",
        "tests_m3/fixtures/refute/a/toylock.extracted.json", "tests_m3/fixtures/refute/b/toylock.extracted.json",
        "tests_m3/fixtures/sort_types/toyclock.extracted.json", "tests_m3/fixtures/sort_types/toytypes.extracted.json",
        "tests_m3/fixtures/undo/drop/toyundo.extracted.json", "tests_m3/fixtures/undo/toyundo.extracted.json"]
OWN_PATHS = ("laws/M3/", "results/M3/", "gen/M3/", "replay/M3/", "spec/bindings/", "laws/STATEMENT_DIFF.jsonl",
             "results/M1/", "results/M2/", "results/T32/", "holon/", "docs/", "spec/schemas/law_ir_0_3.schema.json",
             "spec/M3/amendments.jsonl", "tests_m3/", "prompts/")
GEN3 = ROOT / "gen" / M3
LAWS3 = ROOT / "laws" / M3
RESULTS3 = ROOT / "results" / M3
ANALYSIS = GEN3 / "undo" / f"{MODEL}.json"
REPLAY3 = ROOT / "replay" / M3 / "undo" / "report.json"


def git(*args) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key() -> dict:
    return load_json(ROOT / "spec" / M3 / "predictions.json")["iterations"][KEY]


def holon_module(name: str):
    import importlib
    return importlib.import_module(name)


def need(p: Path) -> dict:
    if not Path(p).is_file():
        raise AssertionError(f"{Path(p).relative_to(ROOT)} does not exist: no build")
    return load_json(p)


def built() -> None:
    """The build exists: the UNDO analysis document has the cancellations key."""
    if "cancellations" not in need(ANALYSIS):
        raise AssertionError(f"{ANALYSIS.relative_to(ROOT)} has no cancellations: no build")


def bare(entries: list) -> list:
    """The instrument's cancellation entries as the analysis document holds them (without residue_classes)."""
    return [{k: v for k, v in x.items() if k != "residue_classes"} for x in entries]


def holon_analyse(d: dict, model: str) -> dict:
    return holon_module("holon.rules.undo").analyse(d, model)


# ------------------------------------------------------------------------------------------------ own commits
def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    c = git("log", "--format=%H", "-1", "--grep", f"^{KEY} prereg").strip()
    if not c:
        raise AssertionError(f"no {KEY} prereg commit in HEAD's history")
    return c


def _merge() -> str | None:
    """M: the oldest merge on R..HEAD's ancestry path (R the oldest commit adding docs/iterations/I71.md) whose second
    parent reaches R and whose first parent does not; None before I71 is merged."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                f"docs/iterations/{KEY}.md").split()
    if not added:
        return None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return c
    return None


def end_commit() -> str:
    m = _merge()
    return git("rev-parse", f"{m}^2" if m else "HEAD").strip()


def own_commits() -> dict[str, list[str]]:
    """I71's own non-merge commits after its prereg, each with the paths it changes against its first parent: along
    the first-parent line of M^2 back to the lead once merged, else prereg..HEAD. Another key's commits merged into
    I71's branch are never I71's."""
    pre, m = prereg_commit(), _merge()
    if m is not None:
        first, second = git("rev-parse", f"{m}^1", f"{m}^2").split()
        revs = [second, f"^{first}", f"^{pre}"]
    else:
        revs = [f"{pre}..HEAD"]
    out = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def at(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def _unseconded(x):
    if isinstance(x, dict):
        return {k: _unseconded(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_unseconded(v) for v in x]
    return x


def _unstamped(rec: dict) -> dict:
    return {k: v for k, v in _unseconded(rec).items() if k != "generator_sha256"}


def cancel_runs(w: dict) -> tuple[list, list]:
    """(the run with x, the run without x) of a cancel witness (rule C8)."""
    pre, t = list(w.get("prefix") or []), list(w.get("t") or [])
    return pre + [w["x"], w["y"]] + t, pre + [w["y"]] + t


def _truthy(v) -> bool:
    """A witness's bool argument: true, a nonzero number, or such a number's text."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, str):
        t = v.strip().lower()
        return t == "true" or (t not in ("", "false") and _int(t) != 0)
    return False


def _int(v) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    s = str(v)
    return int(s, 16) if s.startswith("0x") else int(s)


# ================================================================================================ prereg
class TestPrereg(unittest.TestCase):
    """Constructions on the instrument and the documents (they hold at the prereg commit)."""

    def test_key_pins_the_instrument_and_the_contract(self):
        """The key's thresholds pin the instrument file and this docstring; every prediction is counted."""
        k = key()
        th = k["thresholds"]
        self.assertEqual(th["instrument"], INSTRUMENT)
        self.assertEqual(th["instrument_sha256"], file_sha256(ROOT / INSTRUMENT))
        self.assertEqual(th["contract_docstring_sha256"], hashlib.sha256(__doc__.encode("utf-8")).hexdigest())
        self.assertEqual(th["counted_predictions"], [p["id"] for p in k["predictions"]])
        self.assertEqual(k["tests"], ["tests_m3/test_undo_cancel.py"])

    def test_the_instrument_on_the_documents(self):
        """C1-C3 and C6 on the committed documents: the key's pinned cancellation on the Rollup and on the mutant, none
        on the toys, and the pinned law."""
        th = key()["thresholds"]
        roll = I.cancellations(I.load(ROOT / DOC_REL))
        self.assertEqual(roll, th["rollup"])
        self.assertEqual(I.cancellations(I.load(ROOT / MUTANT_REL)), th["rollup"])
        for rel in TOYS:
            with self.subTest(toy=rel):
                self.assertEqual(I.cancellations(I.load(ROOT / rel)), {"cancellations": [], "rejected": []})
        laws = I.cancel_laws(I.load(ROOT / DOC_REL), MODEL)
        self.assertEqual(sorted(laws), [LAW])
        self.assertEqual(laws[LAW]["undo_id"], UNDO_ID)
        self.assertEqual(laws[LAW], th["law"])
        self.assertEqual(I.undo_ref(laws[LAW]["basis"]), th["law_ref"])

    def test_the_planted_variants(self):
        """C1's edge cases: each planted variant of the Rollup document gets the cancellations and rejected candidates
        _i71.PLANTED names."""
        d = I.load(ROOT / DOC_REL)
        for kind, (_what, canc, rej) in I.PLANTED.items():
            with self.subTest(kind=kind):
                r = I.cancellations(I.planted(d, kind))
                self.assertEqual([(x["a"], x["undo"]) for x in r["cancellations"]], canc)
                self.assertEqual([(x["a"], x["undo"]) for x in r["rejected"]], rej)

    def test_cancellations_are_not_i27s_candidates(self):
        """C2: on the Rollup, no cancellation is one of I27's pairs or rejected pairs (U3/U4 do not see it: gap G5), and
        I27's analysis (its own instrument) is what undo_basis.json records."""
        an = U27.analyse(ROOT / DOC_REL)
        ab = {(p["a"], p["undo"]) for p in an["pairs"] + an["rejected"]}
        for x in I.cancellations(I.load(ROOT / DOC_REL))["cancellations"]:
            self.assertNotIn((x["a"], x["undo"]), ab)
        exp = U27.doc_basis()
        self.assertEqual((an["pairs"], an["rejected"], an["residues"]), (exp["pairs"], exp["rejected"], exp["residues"]))


# ================================================================================================ the build
class TestAnalysis(unittest.TestCase):
    def test_p1_the_cancellations(self):
        """I71-P1: holon undo writes the instrument's cancellations (C1-C4): on the Rollup exactly (challengeState,
        setPause), restoring inChallenge (writes[3] -> writes[3], pin guards[3], cond [&&, [param _status], [storage
        inChallenge]]), criteria [cond], residues [batchChallenged, batchDataStore, challenges], class live, and no
        rejected candidate; the same on the mutant; none on the toys; on every planted variant holon's analysis gives
        the instrument's cancellations and rejected candidates; two runs are byte-identical and equal the committed
        document."""
        built()
        an = need(ANALYSIS)
        exp = I.cancellations(I.load(ROOT / DOC_REL))
        self.assertEqual(an["cancellations"], bare(exp["cancellations"]))
        self.assertEqual(an["rejected_cancellations"], exp["rejected"])
        self.assertEqual([(x["a"], x["undo"], x["criteria"], x["residues"], x["class"]) for x in an["cancellations"]],
                         [("challengeState", "setPause", ["cond"], ["batchChallenged", "batchDataStore", "challenges"],
                           "live")])
        self.assertEqual(an["undo_version"], "holon-undo/0.1")
        d = I.load(ROOT / DOC_REL)
        for kind in I.PLANTED:
            with self.subTest(kind=kind):
                pd = I.planted(d, kind)
                got = holon_analyse(pd, MODEL)
                want = I.cancellations(pd)
                self.assertEqual(got["cancellations"], bare(want["cancellations"]))
                self.assertEqual(got["rejected_cancellations"], want["rejected"])
        tmp = Path(tempfile.mkdtemp(prefix="holon-i71-undo-"))
        try:
            U27.run_ok(self, ["undo", "--milestone", M3, "--out", str(tmp / "a")])
            U27.run_ok(self, ["undo", "--milestone", M3, "--out", str(tmp / "b")])
            a = (tmp / "a" / f"{MODEL}.json").read_bytes()
            self.assertEqual(a, (tmp / "b" / f"{MODEL}.json").read_bytes())
            self.assertEqual(a, ANALYSIS.read_bytes())
            U27.run_ok(self, ["undo", "--milestone", M3, "--facts", MUTANT_REL, "--out", str(tmp / "c")])
            mut = load_json(tmp / "c" / "rollup_mutant.extracted.json")
            self.assertEqual(mut["cancellations"], bare(I.cancellations(I.load(ROOT / MUTANT_REL))["cancellations"]))
            for n, rel in enumerate(TOYS):   # one run each: two toys may share a file name
                U27.run_ok(self, ["undo", "--milestone", M3, "--facts", rel, "--out", str(tmp / f"t{n}")])
                doc = load_json(tmp / f"t{n}" / Path(rel).name)
                self.assertEqual((doc["cancellations"], doc["rejected_cancellations"]), ([], []), rel)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestDerivation(unittest.TestCase):
    def test_p2_the_cancel_law(self):
        """I71-P2: holon derive --milestone M3 under M3's catalog (C5) emits exactly one law of sub-form cancel,
        L_undo_cancel_Rollup_challengeState_setPause, as C6 states it with the instrument's basis, undo id, static class
        and ref; its binders are (s, Reach), (x, Act), (y, Act), (t, Trace) and I30's hash binders; every other law file
        an own commit changes differs from its parent's only in rule_catalog_version, and each such change is named by a
        catalog_rederivation line of laws/STATEMENT_DIFF.jsonl into M3's catalog."""
        built()
        rules = holon_module("holon.rules")
        refs = holon_module("holon.gen.refs")
        cv = rules.catalog_version(M3)
        exp = I.cancel_laws(I.load(ROOT / DOC_REL), MODEL)
        cancel = sorted(p.stem for p in LAWS3.glob("L_undo_*.json") if load_json(p).get("subform") == "cancel")
        self.assertEqual(cancel, [LAW])
        law = need(LAWS3 / f"{LAW}.json")
        self.assertEqual((law["ir_version"], law["rule"], law["subform"], law["milestone"], law["rule_catalog_version"],
                          law["facts"], law["facts_sha256"]),
                         ("holon-ir/0.3", "UNDO", "cancel", M3, cv, DOC_REL, file_sha256(ROOT / DOC_REL)))
        self.assertNotIn("evidence", law)
        self.assertNotIn("predicted", law)
        st = law["statement"]
        names = [(b["name"], b["type"]) for b in st["binders"]]
        self.assertEqual(names[:4], [("s", "Reach"), ("x", "Act"), ("y", "Act"), ("t", "Trace")])
        self.assertEqual(st["binders"][4:], U27.hash_binders_of_sort_laws())
        self.assertEqual(st["assume"], [])
        self.assertEqual(st["claim"], {"eq": [{"undo": UNDO_ID, "on": [{"var": b["name"]} for b in st["binders"]]},
                                              {"bool": True}]})
        self.assertEqual(st["scope"], {"kind": "unbounded"})
        der = {e["law_id"]: e for e in need(LAWS3 / "DERIVATION.json")["laws"]}
        e = der[LAW]
        self.assertEqual((e["rule"], e["subform"], e["facts"]), ("UNDO", "cancel", DOC_REL))
        self.assertEqual(e["basis"], exp[LAW]["basis"])
        self.assertEqual(e["static"], exp[LAW]["static"])
        self.assertEqual(refs.refs(law, load_json(ROOT / DOC_REL)).get(f"undo:{UNDO_ID}"), I.undo_ref(e["basis"]))
        reg = need(LAWS3 / "REGISTRY.json")
        self.assertEqual(e["statement_hash"], reg["statements"][LAW])
        log = [json.loads(x) for x in (ROOT / "laws" / "STATEMENT_DIFF.jsonl").read_text().splitlines() if x.strip()]
        rederived = {(x.get("law_id"), x.get("new_catalog")) for x in log if x.get("kind") == "catalog_rederivation"}
        moved = 0
        for c, paths in own_commits().items():
            for p in paths:
                if not (p.startswith("laws/M3/L") and p.endswith(".json")) or p == f"laws/M3/{LAW}.json":
                    continue
                old, new = at(c + "^", p), at(c, p)
                if old is None or new is None:
                    self.fail(f"{c[:12]}: {p} is added or deleted by an own commit")
                with self.subTest(commit=c[:12], law=p):
                    self.assertEqual({k: v for k, v in new.items() if k != "rule_catalog_version"},
                                     {k: v for k, v in old.items() if k != "rule_catalog_version"})
                    if old.get("rule_catalog_version") != new.get("rule_catalog_version"):
                        moved += 1
                        self.assertIn((p.rsplit("/", 1)[1][:-5], new["rule_catalog_version"]), rederived)
        self.assertGreater(moved, 0, "no own commit moved a law's catalog version")


class TestOutcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        built()
        cls.rec = need(RESULTS3 / f"{LAW}.json")

    def _witness(self):
        r = self.rec
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        w = r.get("witness") or {}
        for k in ("prefix", "x", "y", "t", "hashes"):
            self.assertIn(k, w)
        return w

    def test_p3_refuted_and_replayed(self):
        """I71-P3: the cancel law is REFUTED: its counter-law gen/M3/proofs/<id>/witness/PROOF.bend checked by bend2 (ALL
        PROOFS CHECK) and BendTT (verdict checked); the witness's x is a call of challengeState and y a call of
        setPause with _status true; its replay entry passed with calls_agree, its runs those of C8; and both runs,
        replayed here independently of holon on the real Rollup (I27's harness copies, the binding's deployment), give
        the replay report's real observations, the continuation's observations differing first at diverges_at."""
        w = self._witness()
        self.assertEqual(self.rec["checker"]["marker"], "ALL PROOFS CHECK")
        self.assertEqual(self.rec["kernel"]["verdict"], "checked")
        self.assertEqual((w["x"]["action"], w["y"]["action"]), ("challengeState", "setPause"))
        self.assertTrue(_truthy(w["y"]["args"].get("_status")), w["y"]["args"])
        rep = (need(REPLAY3).get("laws") or {}).get(LAW)
        self.assertIsNotNone(rep, f"replay/M3/undo/report.json has no entry {LAW}")
        self.assertEqual((rep["status"], rep["calls_agree"]), ("passed", True), rep)
        with_run, without = cancel_runs(w)
        pre = len(w["prefix"])
        self.assertEqual(rep["with"]["trace"], with_run)
        self.assertEqual(rep["without"]["trace"], without)
        self.assertEqual((rep["t_at"], rep["t_at_without"]), (pre + 2, pre + 1))
        self.assertEqual(rep["with"]["model"], rep["with"]["real"])
        self.assertEqual(rep["without"]["model"], rep["without"]["real"])
        real = U27.realized([with_run, without], "rollup")
        self.assertEqual(real[0], rep["with"]["real"])
        self.assertEqual(real[1], rep["without"]["real"])
        i = rep["diverges_at"]
        self.assertEqual(real[0][pre + 2:pre + 2 + i], real[1][pre + 1:pre + 1 + i])
        self.assertNotEqual(real[0][pre + 2 + i], real[1][pre + 1 + i])

    def test_p4_the_refund_channel(self):
        """I71-P4: the divergence is the refund: x's msg.value is at least 1 (the deposit), and the divergent step of t
        is a call of claimReward that succeeds in the run with x and y and reverts in the run with y alone."""
        w = self._witness()
        self.assertGreaterEqual(_int(w["x"]["env"].get("msg.value") or 0), 1)
        rep = need(REPLAY3)["laws"][LAW]
        i = rep["diverges_at"]
        self.assertEqual(w["t"][i]["action"], "claimReward")
        pre = len(w["prefix"])
        self.assertEqual((rep["with"]["real"][pre + 2 + i]["status"], rep["without"]["real"][pre + 1 + i]["status"]),
                         ("ok", "revert"))

    def test_p5_the_backtest_closes_g5(self):
        """I71-P5: results/M3/undo/backtest.json pairs all four M1 UNDO laws: L_undo_cancel's analogue is the cancel law,
        REFUTED as M1's (same_status true), and gaps is []; the other three rows are as at the prereg commit."""
        bt = need(RESULTS3 / "undo" / "backtest.json")
        self.assertEqual(bt["gaps"], [])
        rows = {x["m1_law"]: x for x in bt["rows"]}
        c = rows["L_undo_cancel"]
        self.assertEqual((c["analogue"], c["analogue_status"], c["m1_status"], c["same_status"]),
                         (LAW, "REFUTED", "REFUTED", True))
        before = {x["m1_law"]: x for x in at(prereg_commit(), "results/M3/undo/backtest.json")["rows"]}
        for m1 in ("L_undo_BD", "L_undo_BVH", "L_undo_CSR"):
            self.assertEqual(rows[m1], before[m1], m1)

    def test_p6_the_classification_agrees(self):
        """I71-P6: results/M3/undo/classification.json lists the cancel law with static live (C3) and kernel live, agreeing,
        blocking nothing; its disagreements are those at the prereg commit (I27's UNKNOWN laws), the cancel law not
        among them."""
        c = need(RESULTS3 / "undo" / "classification.json")
        x = c["laws"][LAW]
        self.assertEqual((x["subform"], x["static"], x["kernel"], x["agree"], x["blocks"]),
                         ("cancel", "live", "live", True, []))
        self.assertEqual(c["disagreements"], at(prereg_commit(), "results/M3/undo/classification.json")["disagreements"])
        self.assertIs((self.rec.get("undo") or {}).get("agree"), True)

    def test_the_record_and_its_files(self):
        """Construction (C6, C8): the record is valid under v1 and v2, carries the registry's statement hash, the undo
        field (subform cancel, the undo id), the nz premise per hash binder, the witness, coverage and the filter
        stage's fields; Bend run here on a copy of gen/M3 accepts the counter-law, which imports the law file, which
        declares exactly one law naming undo_<x>; no escape hatch in either."""
        r = self.rec
        self.assertEqual(mini_schema.errors(r, load_json(ROOT / "schemas" / "result_record.schema.json")), [])
        self.assertEqual(mini_schema.errors(r, load_json(ROOT / "spec" / "schemas" / "result_record_v2.schema.json")),
                         [])
        self.assertEqual(r["statement_hash"], need(LAWS3 / "REGISTRY.json")["statements"][LAW])
        self.assertEqual((r["undo"]["subform"], r["undo"]["undo_id"]), ("cancel", UNDO_ID))
        law = need(LAWS3 / f"{LAW}.json")
        hb = [b["name"] for b in law["statement"]["binders"] if b["type"].startswith("Fn<")]
        self.assertEqual(r["premises"], [f"nz:{h}" for h in hb])
        self.assertIn("coverage", r)
        self.assertIn("filter_bin", r)
        self.assertIn("concretization", r)
        hatch = re.compile(r"\?[A-Za-z_]|@unsafe|def\s+\w+\?|import\s+\"[^\"]*\.c\"")
        work = Path(tempfile.mkdtemp(prefix="holon-i71-bend-"))
        try:
            shutil.copytree(GEN3, work / "M3")
            law_f = work / "M3" / "laws" / LAW / "LAWS.bend"
            proof_f = work / "M3" / "proofs" / LAW / "witness" / "PROOF.bend"
            lt, pt = law_f.read_text(), proof_f.read_text()
            self.assertEqual(len(re.findall(r"(?m)^law\s+\w+", lt)), 1)
            self.assertRegex(lt, r"\bundo_" + re.escape(LAW[len("L_undo_"):]) + r"\(")
            imp = os.path.relpath(law_f, proof_f.parent)
            self.assertRegex(pt, r"(?m)^import\s+(\./)?" + re.escape(imp) + r"\s")
            for t in (lt, pt):
                self.assertIsNone(hatch.search(re.sub(r"#[^\n]*", "", t)))
            code, out = run_bend([proof_f.name], cwd=proof_f.parent, timeout=3600)
            self.assertEqual(code, 0, out[-2000:])
            self.assertIn("ALL PROOFS CHECK", out)
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ================================================================================================ regressions
class TestRegressions(unittest.TestCase):
    def test_r1_the_catalog(self):
        """I71-R1 (C5): the lowest catalog version holding UNDO/cancel holds every rule and producer of the version
        below it, the same objects, and adds only UNDO's cancel, holon.rules.undo.CANCEL; undo.PRODUCERS is {pair,
        residue}; M3 derives with that catalog or a later one keeping its producers; M2 keeps holon-rules/1.0; the
        version below it holds I28's PAR/init_chain."""
        rules = holon_module("holon.rules")
        undo = holon_module("holon.rules.undo")
        num = lambda v: int(re.fullmatch(r"holon-rules/1\.(\d+)", v).group(1))  # noqa: E731
        vs = sorted((v for v in rules.CATALOGS if re.fullmatch(r"holon-rules/1\.\d+", v)), key=num)
        mine = [v for v in vs if "cancel" in (rules.CATALOGS[v].get("UNDO") or {})]
        self.assertTrue(mine, "no catalog holds UNDO/cancel: no build")
        prev = [v for v in vs if num(v) < num(mine[0])][-1]
        cat, before = rules.CATALOGS[mine[0]], rules.CATALOGS[prev]
        for rule, subs in before.items():
            for sub, prod in subs.items():
                self.assertIs(cat[rule][sub], prod, f"{rule}/{sub}")
        self.assertEqual({r: sorted(set(cat[r]) - set(before.get(r) or {})) for r in cat
                          if set(cat[r]) - set(before.get(r) or {})}, {"UNDO": ["cancel"]})
        self.assertIs(cat["UNDO"]["cancel"], undo.CANCEL)
        self.assertEqual(sorted(undo.PRODUCERS), ["pair", "residue"])
        self.assertIn("init_chain", before.get("PAR") or {})
        v = rules.catalog_version(M3)
        for rule, subs in cat.items():
            for sub, prod in subs.items():
                self.assertIs((rules.CATALOGS[v].get(rule) or {}).get(sub), prod, f"M3's {v}: {rule}/{sub}")
        self.assertEqual(rules.catalog_version("M2"), "holon-rules/1.0")

    def test_r2_other_m3_statuses_are_kept(self):
        """I71-R2: every M3 record an own commit changes, but the cancel law's (which an own commit adds), keeps the status
        of its version at the commit's first parent, and no own commit deletes a record or adds another; at the end
        commit every M3 record but I27's eight UNDO records (stale since I26: rule C10) carries the registry's statement
        hash (the catalog bump's re-make is complete)."""
        reg = at(end_commit(), "laws/M3/REGISTRY.json")["statements"]
        names = [n for n in git("ls-tree", "--name-only", f"{end_commit()}:results/M3").split()
                 if n.startswith("L") and n.endswith(".json")]
        stale = sorted(n[:-5] for n in names if (at(end_commit(), f"results/M3/{n}") or {}).get("statement_hash")
                       != reg.get(n[:-5]))
        self.assertEqual([x for x in stale if not re.fullmatch(r"L_undo_(pair|res)_.*", x)], [])
        n = 0
        for c, paths in own_commits().items():
            for p in paths:
                if not (re.fullmatch(r"results/M3/L[^/]*\.json", p)):
                    continue
                old, new = at(c + "^", p), at(c, p)
                if p == f"results/M3/{LAW}.json":
                    continue
                with self.subTest(commit=c[:12], record=p):
                    self.assertIsNotNone(old, "added by an own commit")
                    self.assertIsNotNone(new, "deleted by an own commit")
                    self.assertEqual(new["status"], old["status"])
                    n += 1
        self.assertGreater(n, 0, "no own commit re-made an M3 record")

    def test_r3_earlier_milestones_change_in_stamps_only(self):
        """I71-R3: own commits change the records under results/M1, results/M2 and results/T32 in generator_sha256 and keys
        named seconds alone, and change nothing under laws/M0-M2, gen/M0-M2, results/M0, replay/M0-M2, facts/, the
        fact documents (spec/M*/facts/) or a frozen root; every changed path is one C10 names."""
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py")
        never = ("laws/M0/", "laws/M1/", "laws/M2/", "gen/M0/", "gen/M1/", "gen/M2/", "results/M0/", "replay/M0/",
                 "replay/M1/", "replay/M2/")
        # amended (spec/M3/amendments.jsonl, iteration I71): I82's report outputs, which a key moving M3 statuses
        # regenerates (holon report --milestone M3), are admitted beside C10's paths, and nothing else
        allowed = OWN_PATHS + ("docs/M3_COMPARISON.md", "spec/M3/appendixA_map.json")
        for c, paths in own_commits().items():
            for p in paths:
                with self.subTest(commit=c[:12], path=p):
                    self.assertFalse(p.startswith(frozen))
                    self.assertFalse(p.startswith(never))
                    self.assertIsNone(re.match(r"spec/M\d+/facts/", p))
                    self.assertTrue(p.startswith(allowed), "a path C10 does not name")
                    if re.fullmatch(r"results/(M1|M2|T32)/(.+/)?L[^/]*\.json", p):
                        old, new = at(c + "^", p), at(c, p)
                        self.assertIsNotNone(old)
                        self.assertIsNotNone(new)
                        self.assertEqual(_unstamped(new), _unstamped(old))

    def test_r4_i27s_analysis_is_unchanged(self):
        """I71-R4: own commits leave I27's keys of every gen/M3/undo/*.json (pairs, rejected, residues and the header
        fields) as at the commit's first parent; the analysis document gains only cancellations and
        rejected_cancellations."""
        new_keys = {"cancellations", "rejected_cancellations"}
        for c, paths in own_commits().items():
            for p in paths:
                if not re.fullmatch(r"gen/M3/undo/[^/]+\.json", p):
                    continue
                old, new = at(c + "^", p), at(c, p)
                with self.subTest(commit=c[:12], path=p):
                    self.assertIsNotNone(old)
                    self.assertIsNotNone(new)
                    self.assertLessEqual(set(new) - set(old), new_keys)
                    self.assertEqual({k: v for k, v in new.items() if k not in new_keys | {"inputs"}},
                                     {k: v for k, v in old.items() if k not in new_keys | {"inputs"}})

    def test_r5_new_code_names_no_target(self):
        """I71-R5 (AGENTS rules 2 and 4): the holon/ files own commits change add no action, family or contract name of
        the Rollup document (longer than four characters), no law id and no target file name."""
        d = I.load(ROOT / DOC_REL)
        names = {a["name"] for a in d["actions"]} | {f["name"] for f in d["storage"] + d.get("inherited_storage", [])}
        names |= {d["contract"], "Rollup.sol", LAW}
        names = {n for n in names if len(n) > 4}
        for c, paths in own_commits().items():
            for p in paths:
                if not (p.startswith("holon/") and p.endswith((".py", ".mjs"))):
                    continue
                diff = git("show", "--format=", "--unified=0", c, "--", p)
                added = "\n".join(x[1:] for x in diff.splitlines() if x.startswith("+") and not x.startswith("+++"))
                with self.subTest(commit=c[:12], path=p):
                    self.assertEqual(sorted(n for n in names if re.search(r"\b" + re.escape(n) + r"\b", added)), [])

    def test_r6_the_schema_admits_cancel(self):
        """I71-R6 (C6): spec/schemas/law_ir_0_3.schema.json's undo id pattern is pair|residue|cancel; the schema differs
        from its version at the parent of the own commit that changes it only in that pattern and the description of
        t_undo; docs/adoption/Q4/schemas/law_ir_0_3.schema.json is byte-equal to it; the cancel law validates."""
        s = load_json(ROOT / SCHEMA)
        self.assertEqual(s["$defs"]["t_undo"]["properties"]["undo"]["pattern"], UNDO_PATTERN)
        self.assertEqual((ROOT / Q4_SCHEMA).read_bytes(), (ROOT / SCHEMA).read_bytes())
        hits = [c for c, paths in own_commits().items() if SCHEMA in paths]
        self.assertTrue(hits, "no own commit changes the law IR schema: no build")
        for c in hits:
            old, new = at(c + "^", SCHEMA), at(c, SCHEMA)
            for x in (old, new):
                x["$defs"]["t_undo"].pop("description", None)
                x["$defs"]["t_undo"]["properties"]["undo"].pop("pattern", None)
            self.assertEqual(new, old, c[:12])
        law = need(LAWS3 / f"{LAW}.json")
        self.assertEqual(mini_schema.errors(law, s), [])


if __name__ == "__main__":
    unittest.main()
