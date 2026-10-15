"""I43 part A: theory core II (whitepaper §6 Thm 6.6 and Thm 6.7; §5.3, §5.4, §10.3 steps 4-5, §10.8; BUILD_PLAN I43;
docs/HUMAN_ANSWERS.md Q14b). This docstring is the contract that tests_m3/test_theory_core2.py checks. Part B (Lean for
the promoted set, Q8) is the contract of tests_m3/test_lean_promoted.py.

Instruments fixed at the prereg: tests_m3/_i43.py (CORE2_LAWS_TEXT, LEAN2_TEXT, the contract's own Lean reading and
its own Lean check, all written independently of holon/: the toolchain resolution with its version and fingerprint
pin, the banned words, the axiom parser and the sentinel) and the frozen sidecar spec/M3/lib/theory_core2.json
(tests_m3/_i43.py::theory2_doc).

Disclosure. A read-only design survey run before this prereg (nothing of it is committed) checked, with hand proofs,
the six Bend laws core_eqv_comp, core_eqv_inv, core_eqv_trace, core_nat_paste, core_nat_vcomp and core_nat_trace in the
form frozen here (bend and bend --verdict) and eleven Lean theorems (all of the first draft's twelve but thm_6_7_obs;
Lean 4.34.0, no axioms). The other statements were written for this prereg: core_eqv_id, core_eqv_word,
core_eqv_pow, core_nat_obs and the five inhabitation laws (Bend, 9) and thm_6_6_id_on, thm_6_6_comp_on and
thm_6_7_obs (Lean, 3). All of them were proved before this commit all the same: the independent review of the first
draft proved its 14 Bend laws and 12 Lean theorems in a scratch clone, the drafter proved core_eqv_id, thm_6_6_id_on and
thm_6_6_comp_on in scratch before adding them at the first review fold, and the second review proved all 15 and 14 in
minutes. Nothing of it is committed. So part A predicts nothing (review 2, m8): every check of this contract is a
construction check, the core II's outcome regression I43-R12 (the first drafts scored it as I43-P1 and I43-P2).

What the plan asks and what the tree holds
  BUILD_PLAN I43: "the core forms of Thm 6.6 and 6.7 used by I29 and I34 (Lemma 6.12 already landed in I25)";
  prediction "the core laws are PROVED". Q14b: "Thm 6.4, 6.6 and 6.7 may be proved once, by hand, in Lean, and
  kernel-checked". I42 (docs/iterations/I42.md, merged into this prereg's base 7fd9755 at 512e6f3) built
  theory core I the same way: textbook theorems in Lean, per-step bundle laws in Bend (Bend 2 makes every function
  value affine: bend/notes/p_ir03_fn_verdict), the Bend forms an instance applies by building its bundles from
  top-level lemmas. Thm 6.6 (whitepaper §6): Stab(T_a) is a subgroup, or a submonoid for partial actions; SYM checks
  equivariance per generator and per action (§8.4, §10.3 step 4, §10.8): the families tau (time, tau_d = tau_1^d),
  iota, pi (products of transpositions) and mu. Thm 6.7: (a) pasting, (b) vertical composition, (c) entry points x
  in-flight types suffice, plus reachable migration sequences (§5.3 a-c, §10.3 step 5); NAT (a) compares
  observations.
    result                              Lean theorem (textbook form)    Bend law (the form an instance applies)
    Thm 6.6 id / comp / inv             thm_6_6_id, _comp, _inv         core_eqv_id, core_eqv_comp, core_eqv_inv
                                                                        (pointwise)
    Thm 6.6 generators suffice (word)   thm_6_6_word                    core_eqv_word (WordTo, EqvWord)
    Thm 6.6 powers                      thm_6_6_pow                     core_eqv_pow (IterTo, EqvPow)
    Thm 6.6 partial actions: submonoid  thm_6_6_id_on, _comp_on         (Bend's laws are pointwise: partial already)
    Thm 6.6 on traces / partial         thm_6_6_run, thm_6_6_run_on     core_eqv_trace (MapA, EqvAlong, RunA)
    Thm 6.7 (a) / (b) / (c)             thm_6_7_a, _b, _c               core_nat_paste, core_nat_vcomp, core_nat_trace
    Thm 6.7 migration sequences         thm_6_7_seq                     (Lean only; an instance chains core_nat_vcomp)
    Thm 6.7 (c) up to an observation    thm_6_7_obs                     core_nat_obs (SqObs: square under ob and a
                                                                        congruence step per step)
    non-vacuity (L21)                   (definitional in Lean)          core_eqv_inhabited, core_word_inhabited,
                                                                        core_pow_inhabited, core_sq_inhabited,
                                                                        core_sqobs_inhabited

Gaps preregistered
  TC-G1 The affine form (I42's reading, I42 Question 2): every Bend law takes one hypothesis per step, word letter or
        iteration, packed in a bundle a proof consumes once; Lean states the textbook form with hypotheses quantified
        once. The Bend word applies its letters head first (WordTo, like RunA); Lean's wordS/wordA apply the head last.
        No law relates the two orders; each is internally consistent.
  TC-G2 Hand proofs (Q14b's reading): Q14b names Thm 6.6 and 6.7 in Lean; I43 also hand-writes, once and
        generically, the Bend core II proofs (their per-step forms), as I42 did for core I (I42 gap T-G7 and Question
        1). Both are emitted as fixed text by holon/gen/theory2.py.
  TC-G3 Placement (stated deviations): outcome path gen/M3/theory2/, never gen/M3/theory/ (which holon basis owns and
        I42's tests pin), never holon.gen.core's catalog (a holon-ir/0.3 closure root emitted into gen/M2/core and
        gen/M3/core). holon/gen/theory2.py is imported by no module of the holon-ir/0.1-0.3 generator closures.
  TC-G4 No instance applies the new laws here: I29 (NAT) and I34 (SYM) instantiate them by application (the design
        survey checked a toy instance of core_nat_trace; nothing of it is committed).
  TC-G5 No gate integration (as I42 gap T-G6): G3's Bend scan covers gen/M3/theory2/*.bend; TheoryII.lean is checked
        by this contract (rule C2), not by Lean G7, which scans the law files of gen/<M>/lean.
  TC-G6 core_nat_obs states the square under ob from any u with ob(eta(x)) == ob(u) (the general form an induction
        needs); its congruence step is stated at the two states the step meets, not for all pairs: an instance that
        has the noninterference step lemma for all pairs applies it at those two.
  TC-G7 The submonoid of partial actions (review m2): Lean states it as thm_6_6_id_on and thm_6_6_comp_on (the
        symmetries on D that keep D, closed under composition, with the identity); Bend has no domain notion, its
        laws being pointwise, so core_eqv_id is the pointwise identity (a transform fixing the action and the two
        states the step meets) and core_eqv_comp the pointwise composition.

CLI (every JSON file: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic, no timestamps)
  python -m holon theory2 --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]
    Writes under <out, default <root>/gen/M3/theory2>: core/LAWS.bend and core/PROOF.bend (rule C1),
    lean/TheoryII.lean (rule C2); with --kernels it also checks both proof files and the Lean file and writes
    report.json (rule C4). It owns <out>/core, <out>/lean and <out>/report.json: any other file under core/ and lean/ is
    removed, report.json is written only with --kernels, nothing else under <out> is touched. Exit 0 written; 1
    (--check) a file differs from a fresh build (report.json compared only with --kernels), nothing written; 2 refused
    (a missing checker, a milestone other than M3), the message starting "holon theory2: refused:", nothing written.
    The output never depends on spec/M3/lib/theory_core2.json (part B's TestCode runs --check without it).

Rules (holon/gen/theory2.py; tests_m3/_i43.py writes C1 and C2 out again)
  C1 The Bend core II. <out>/core/LAWS.bend is exactly tests_m3/_i43.py::CORE2_LAWS_TEXT: the definitions (RunA, MapA,
     WordTo, IterTo, EqvAlong, EqvWord, EqvPow, Sq, SqObs) and the 15 laws of CORE2_LAWS. <out>/core/PROOF.bend imports
     ./LAWS.bend (and Base), fills every law with a def of the same name, declares no law, has no escape hatch
     (?TODO, ?name, @unsafe, def f?(..), a foreign import) and no string or char literal. bend and bend --verdict each
     accept it (ALL PROOFS CHECK) within bend.budget_s_per_file seconds (120, wall clock on an otherwise idle
     machine).
  C2 The Lean core II. <out>/lean/TheoryII.lean starts with the definitions block of tests_m3/_i43.py::LEAN2_TEXT (up
     to and including the line "-- holon:theorems"; no namespace, autoImplicit off) and obeys
     tests_m3/_i43.py::core_file_violations, read comment-free by tests_m3/_i43.py::lean_code (an escaped identifier
     «...» kept whole). In the whole file: no # anywhere, no word of _i43.LEAN_BANNED (sorry, sorryAx, axiom,
     native_decide, macro, macro_rules, syntax, elab, notation, attribute, instance, IO, Process, Lean, ...), and no
     indented line that starts with a command keyword (_i43.INDENTED_COMMAND: theorem, def, instance, axiom,
     namespace, end, open, set_option not followed by in, ...). After the marker: no escaped identifier, no "@[" and
     no string literal; every line that starts in column 0 starts with "theorem ", "def ", "example ", "|",
     "termination_by", "decreasing_by" or "set_option maxRecDepth|maxHeartbeats <n> [in]"; none of the words
     instance, attribute, deriving, variable, include, omit, universe, open, export, namespace, section, end, local,
     scoped, private, protected, noncomputable, mutual, class, abbrev, structure, inductive appears (I42's amended
     rule T2). Each theorem of LEAN2_THEOREMS (14) is declared exactly once with exactly LEAN2_TEXT's statement (from
     "theorem <name>" to ":=", comments removed, whitespace normalized), and its type elaborated in the file (`#check
     @<name>` under pp.all) equals its type elaborated from the frozen statements. The instrument's Lean check accepts
     the file (tests_m3/_i43.py::lean_check: the pinned lean, Lean 4.34.0 with its fingerprint frozen in the instrument
     and resolved by it, runs the file followed by a sentinel theorem with a fresh random name and `#print axioms` for
     the 14 theorems and the sentinel; exit code 0, no error, no "declaration uses sorry", the audit lines end with
     exactly the 14 theorems and the sentinel, axioms within {propext, Quot.sound}), within lean.budget_s_per_file
     seconds (120). The frozen texts name no sidecar (review 2, B2): the emitter holds them verbatim, and part B's
     TestCode forbids any holon/ file to name spec/M3/lib/theory_core2.json or lean_promoted.json.
  C3 Generic code. holon/gen/theory2.py names no target, fixture or law, imports neither tests nor tests_m3 (no
     instrument) and enters no generator closure (rule TC-G3).
  C4 The report. <out>/report.json (only with --kernels; no timings): {"report_version": "holon-theory2/0.1",
     "files": {"core/PROOF.bend": {"sha256", "bend": "checked"|"rejected", "verdict": "checked"|"rejected"|"not_run",
     "laws": [the laws the file fills]}, "lean/TheoryII.lean": {"sha256", "lean": holon's own Lean result, "axioms",
     "theorems": [the audited theorems]}}}. A proof file counts as checked only if it fills every law of its LAWS.bend.
  C5 Untouched outputs. No commit that writes gen/M3/theory2/ or holon/gen/theory2.py, nor any other I43 outcome
     commit (one that changes gen/M1/lean, gen/M2/lean, gen/M2/extracted/m1/lean, gen/M3/lean or
     holon/gen/lean_*.py), changes a file under gen/M3/theory/ (I42's outputs, owned by holon basis). The base 7fd9755
     holds I42's outputs (I42 merged at 512e6f3; the prereg 84c185f's base fbd14d3 held none, review m1), so C5 checks
     them. holon basis already refuses at 7fd9755 (stale PAR law files); after I43's PAR regeneration the lead, not
     the I43 build, regenerates I42's outputs and sidecar in a commit that writes nothing else.

Rules for the build
  - AGENTS.md is binding. The statements are frozen in the sidecar; a statement that turns out false or unprovable is
    a MISS, reported with the kernel's output, never edited. No law is added to laws/, no record changes for part A.
  - No skips. A test that needs bend or Lean fails, naming what is missing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests_m3 import _i24x as X
from tests_m3 import _i43 as T
from tests_m3._m3 import ROOT, canonical_json, copy_repo, file_sha256, holon_module, load_json, run_bend, run_holon

SIDECAR = ROOT / T.THEORY2_SIDECAR
OUT = ROOT / T.THEORY2_OUT
BUDGET_S = 120
OK, FAIL = "ALL PROOFS CHECK", "SOME PROOFS FAIL"
ESCAPES = (re.compile(r"@unsafe"), re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M), re.compile(r"\?[A-Za-z_]\w*"),
           re.compile(r"^\s*import\s+\"", re.M))
MODULE = "holon/gen/theory2.py"
I42_OUT = "gen/M3/theory/"
I43_OUTPUTS = ("gen/M3/theory2/", "gen/M1/lean/", "gen/M2/lean/", "gen/M2/extracted/m1/lean/", "gen/M3/lean/", MODULE)


def side() -> dict:
    return load_json(SIDECAR)


def need(p: Path) -> Path:
    p = Path(p)
    if not p.exists():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing (I43 builds it)")
    return p


def law_blocks(text: str) -> dict[str, str]:
    """law NAME: blocks of a Bend file, each as its lines with trailing whitespace stripped (comments removed)."""
    lines = [re.sub(r"#.*$", "", ln).rstrip() for ln in text.splitlines()]
    out, cur = {}, None
    for ln in lines:
        m = re.match(r"^law\s+(\w+)\s*:\s*$", ln)
        if m:
            cur = m.group(1)
            out[cur] = [ln]
        elif cur is not None and ln.startswith((" ", "\t")) and ln.strip():
            out[cur].append(ln)
        elif ln.strip():
            cur = None
    return {k: "\n".join(v) for k, v in out.items()}


def no_escape(test: unittest.TestCase, text: str, what: str) -> None:
    for rx in ESCAPES:
        test.assertIsNone(rx.search(text), f"{what}: escape hatch {rx.pattern}")


def timed_bend(test: unittest.TestCase, proof: Path, verdict: bool = False) -> float:
    """Check one PROOF.bend with bend (or bend --verdict) from its own directory; returns the wall-clock seconds."""
    t0 = time.monotonic()
    if verdict:
        bend = holon_module("holon.bend")
        test.assertTrue(bend.verdict_available(), "bend --verdict needs Lean (BEND_NOTES 1); it is never skipped")
        r = bend.check_verdict(proof)
        code, out = r.code, r.out
    else:
        code, out = run_bend([proof.name], cwd=proof.parent, timeout=900)
    secs = time.monotonic() - t0
    test.assertEqual(code, 0, f"{proof}{' --verdict' if verdict else ''}: {out[-3000:]}")
    test.assertIn(OK, out, f"{proof}: {out[-3000:]}")
    return secs


def lean_run(text: str, timeout: int = 600) -> str:
    """Elaborate one Lean text with the pinned lean the instrument resolves (tests_m3/_i43.py::run_lean)."""
    return T.run_lean(text, timeout)["out"]


def pp_types(test: unittest.TestCase, out: str, names: list[str]) -> dict[str, str]:
    """`#check @<name>` outputs under pp.all, whitespace normalized, by name."""
    test.assertEqual(T.lean_errors(out), [], out[-3000:])
    got = {}
    for n in names:
        m = re.search(rf"(?ms)^@?{re.escape(n)} :(.*?)(?=^@?[\w.]+ :|^\S+:\d+:\d+: |^'|\Z)", out)
        test.assertIsNotNone(m, f"#check @{n}: {out[-2000:]}")
        got[n] = " ".join(m.group(1).split())
    return got


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()} (the real checkout's history is needed)")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds key I43 (holon.audit.prereg's C_K)."""
    for c in git("rev-list", "--reverse", "--topo-order", "HEAD", "--", "spec/M3/predictions.json").split():
        blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:spec/M3/predictions.json"], capture_output=True,
                              text=True)
        if blob.returncode == 0 and '"I43"' in blob.stdout:
            return c
    raise AssertionError("no commit introduces key I43 in spec/M3/predictions.json")


def theory2(args: list, cwd: Path | None = None, timeout: int = 3600):
    return run_holon(["theory2", *[str(a) for a in args]], cwd=cwd, timeout=timeout)


def tree_files(d: Path, skip=("report.json",)) -> dict[str, bytes]:
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*"))
            if p.is_file() and p.name not in skip}


# ---------------------------------------------------------------------------------------------- the prereg's inputs
class TestPreregInstruments(unittest.TestCase):
    """Construction checks of the instruments fixed at the prereg (I43-R2; they hold before and after the build)."""

    def test_sidecar_is_the_computation(self):
        """Construction (I43-R2): spec/M3/lib/theory_core2.json is tests_m3/_i43.py::theory2_doc (pure texts)."""
        self.assertEqual(canonical_json(T.theory2_doc()), canonical_json(side()))

    def test_core2_statements_are_well_typed_open_laws(self):
        """Construction (rule C1): the frozen Bend core II text type-checks under the pinned bend as 15 open laws (bend
        reports exactly 15 TODOs and no other error). No proof is attempted here."""
        tmp = Path(tempfile.mkdtemp(prefix="i43_core2_"))
        try:
            (tmp / "LAWS.bend").write_text(side()["core"]["laws_text"])
            (tmp / "PROOF.bend").write_text("import Base\nimport ./LAWS.bend as Laws\n")
            code, out = run_bend(["PROOF.bend"], cwd=tmp)
            self.assertNotEqual(code, 0)
            self.assertIn(FAIL, out)
            self.assertRegex(out, rf"Error: {len(T.CORE2_LAWS)} TODOs found", out[-2000:])
            self.assertNotIn("- expected", out)
            self.assertEqual(list(law_blocks(side()["core"]["laws_text"])), T.CORE2_LAWS)
            self.assertEqual(len(T.CORE2_LAWS), 15)
            self.assertEqual((len(T.CORE2_PROBED), len(T.CORE2_UNPROBED)), (6, 9))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_lean2_statements_are_well_typed(self):
        """Construction (rule C2): the frozen Lean text, each proof a placeholder, passes the instrument's Lean check
        with placeholders allowed (exit 0, no error, the sentinel reached, the axiom audit printing all 14 theorems by
        their bare names) and has exactly one "declaration uses `sorry`" warning per theorem (14). The placeholder
        never enters a committed file. The definitions block obeys the core file rule (no #, no banned word)."""
        text = side()["lean"]["text"]
        r = T.lean_check(text, T.LEAN2_THEOREMS, allow_sorry=True, allowed=T.ALLOWED_AXIOMS + ("sorryAx",))
        self.assertEqual(r["problems"], [], r["out"][-3000:])
        self.assertEqual(len(T.LEAN_SORRY.findall(r["out"])), len(T.LEAN2_THEOREMS), r["out"][-3000:])
        self.assertEqual(re.findall(r"(?m)^theorem\s+([A-Za-z_][A-Za-z0-9_.]*)", T.lean_code(text)), T.LEAN2_THEOREMS)
        self.assertEqual(len(T.LEAN2_THEOREMS), 14)
        self.assertEqual((len(T.LEAN2_PROBED), len(T.LEAN2_UNPROBED)), (11, 3))
        for name in T.LEAN2_THEOREMS:
            self.assertIsNotNone(T.lean_statement(text, name), name)
        self.assertEqual(T.core_file_violations(T.lean_definitions(text)), [])


# ---------------------------------------------------------------------------------------------- R12: the Bend core II
class TestCore(unittest.TestCase):
    """I43-R12 (construction; every statement was proved before the prereg, by the reviews and the drafter)."""

    def test_core_laws_are_the_frozen_text(self):
        """I43-R12 (statements): gen/M3/theory2/core/LAWS.bend is exactly the frozen text (rule C1)."""
        self.assertEqual(need(OUT / "core" / "LAWS.bend").read_text(), side()["core"]["laws_text"])

    def test_core_proof_fills_every_law(self):
        """I43-R12 (shape): core/PROOF.bend imports ./LAWS.bend, declares no law, fills each of the 15 laws with a def
        of the same name, and has no escape hatch and no string or char literal."""
        pt = need(OUT / "core" / "PROOF.bend").read_text()
        m = re.search(r"(?m)^import \./LAWS\.bend as (\w+)$", pt)
        self.assertIsNotNone(m, "core/PROOF.bend must import ./LAWS.bend")
        alias = m.group(1)
        self.assertEqual(law_blocks(pt), {})
        for name in T.CORE2_LAWS:
            self.assertRegex(pt, rf"(?m)^def {alias}\.{name}\(", name)
        no_escape(self, (OUT / "core" / "LAWS.bend").read_text() + pt, "core II")
        self.assertNotIn('"', pt)
        self.assertNotIn("'", pt)
        imports = [ln.strip() for ln in pt.splitlines() if ln.startswith("import")]
        self.assertEqual(sorted(imports), sorted(["import Base", f"import ./LAWS.bend as {alias}"]))

    def test_core_checks_under_bend_within_budget(self):
        """I43-R12: bend accepts gen/M3/theory2/core/PROOF.bend (ALL PROOFS CHECK) within 120 s."""
        self.assertLessEqual(timed_bend(self, need(OUT / "core" / "PROOF.bend")), BUDGET_S)

    def test_core_checks_under_verdict_within_budget(self):
        """I43-R12: bend --verdict (BendTT) accepts gen/M3/theory2/core/PROOF.bend within 120 s."""
        self.assertLessEqual(timed_bend(self, need(OUT / "core" / "PROOF.bend"), verdict=True), BUDGET_S)


# ---------------------------------------------------------------------------------------------- R12: the Lean core II
class TestLean(unittest.TestCase):
    """I43-R12 (construction; every statement was proved before the prereg, by the reviews and the drafter)."""

    def test_lean_definitions_and_statements_are_frozen(self):
        """I43-R12 (statements, rule C2): TheoryII.lean starts with the frozen definitions block and obeys
        tests_m3/_i43.py::core_file_violations (no #, no banned word, after the marker no escaped identifier,
        attribute or string, only the allowed column-0 lines and none of the words that change how a statement
        elaborates); each frozen theorem is declared once, with exactly its frozen statement."""
        src = need(OUT / "lean" / "TheoryII.lean").read_text()
        defs = T.lean_definitions(side()["lean"]["text"])
        self.assertTrue(src.startswith(defs), "TheoryII.lean must start with the frozen definitions")
        self.assertEqual(T.core_file_violations(src), [])
        for name in T.LEAN2_THEOREMS:
            with self.subTest(theorem=name):
                got = T.lean_statement(src, name)
                self.assertIsNotNone(got, f"theorem {name} is not declared exactly once")
                self.assertEqual(got, T.lean_statement(side()["lean"]["text"], name))

    def test_lean_elaborated_types_are_the_frozen_ones(self):
        """I43-R12 (rule C2): each frozen theorem's elaborated type in TheoryII.lean (`#check @<name>` under pp.all)
        equals its type elaborated from the frozen statements, so nothing in the file changes what a statement
        means."""
        def types(text: str) -> dict[str, str]:
            out = lean_run(text.rstrip("\n") + "\n\nset_option pp.all true\n"
                           + "".join(f"#check @{n}\n" for n in T.LEAN2_THEOREMS))
            return pp_types(self, out, T.LEAN2_THEOREMS)

        want = types(side()["lean"]["text"])
        have = types(need(OUT / "lean" / "TheoryII.lean").read_text())
        for n in T.LEAN2_THEOREMS:
            with self.subTest(theorem=n):
                self.assertEqual(have[n], want[n])

    def test_lean_core_checks(self):
        """I43-R12: the instrument's Lean check (tests_m3/_i43.py::lean_check, the pinned toolchain resolved and
        fingerprinted by the instrument) accepts TheoryII.lean: exit 0, no error, no sorry, the sentinel reached, every
        frozen theorem audited with axioms within {propext, Quot.sound}, within 120 s (wall clock)."""
        src = need(OUT / "lean" / "TheoryII.lean").read_text()
        r = T.lean_check(src, T.LEAN2_THEOREMS)
        self.assertEqual(r["problems"], [], r["out"][-4000:])
        self.assertLessEqual(r["seconds"], BUDGET_S)


# ---------------------------------------------------------------------------------------------- C4: the report
class TestReport(unittest.TestCase):
    def test_report_binds_every_kernel_result(self):
        """Construction (rule C4): gen/M3/theory2/report.json lists core/PROOF.bend (bend and verdict checked, the 15
        laws filled) and lean/TheoryII.lean (lean checked, axioms within {propext, Quot.sound}, every frozen theorem
        audited) with the sha256 of the committed files."""
        rep = load_json(need(OUT / "report.json"))
        self.assertEqual(rep["report_version"], T.THEORY2_VERSION)
        self.assertEqual(sorted(rep["files"]), ["core/PROOF.bend", "lean/TheoryII.lean"])
        core, lean = rep["files"]["core/PROOF.bend"], rep["files"]["lean/TheoryII.lean"]
        self.assertEqual(core["sha256"], file_sha256(OUT / "core" / "PROOF.bend"))
        self.assertEqual((core["bend"], core["verdict"]), ("checked", "checked"))
        self.assertEqual(sorted(core["laws"]), sorted(T.CORE2_LAWS))
        self.assertEqual(lean["sha256"], file_sha256(OUT / "lean" / "TheoryII.lean"))
        self.assertEqual(lean["lean"], "checked")
        self.assertLessEqual(set(lean["axioms"]), {"propext", "Quot.sound"})
        self.assertLessEqual(set(T.LEAN2_THEOREMS), set(lean["theorems"]))


# ---------------------------------------------------------------------------------------------- R3: the CLI
class TestCLI(unittest.TestCase):
    def test_two_runs_are_byte_identical_and_equal_the_committed_files(self):
        """Construction (I43-R3): holon theory2 --milestone M3 --out DIR (no kernels) writes, twice, byte-identical
        files equal to gen/M3/theory2/ (report.json aside) and leaves a file outside core/ and lean/ alone; --check on
        the committed tree exits 0."""
        need(OUT / "core" / "LAWS.bend")
        tmp = Path(tempfile.mkdtemp(prefix="i43_cli_"))
        try:
            outs = []
            for n in (1, 2):
                o = tmp / f"out{n}"
                o.mkdir()
                (o / "keep.txt").write_text("not holon's\n")
                p = theory2(["--milestone", "M3", "--out", o])
                self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
                self.assertEqual((o / "keep.txt").read_text(), "not holon's\n")
                outs.append(tree_files(o, skip=("report.json", "keep.txt")))
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(outs[0], tree_files(OUT))
            self.assertEqual(sorted(outs[0]), ["core/LAWS.bend", "core/PROOF.bend", "lean/TheoryII.lean"])
            p = theory2(["--milestone", "M3", "--check"])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_check_detects_an_edited_file(self):
        """Construction (I43-R3): in a copy whose core/PROOF.bend has one extra comment line, holon theory2 --check
        exits 1 and writes nothing."""
        need(OUT / "core" / "PROOF.bend")
        repo = copy_repo()
        try:
            f = repo / T.THEORY2_OUT / "core" / "PROOF.bend"
            f.write_text(f.read_text() + "# edited\n")
            before = f.read_bytes()
            p = theory2(["--milestone", "M3", "--root", repo, "--check"], cwd=repo)
            self.assertEqual(p.returncode, 1, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual(f.read_bytes(), before)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- C3, C5: honesty
class TestHonesty(unittest.TestCase):
    def test_generic_code(self):
        """Construction (I43-R4, rule C3): holon/gen/theory2.py names no identifier of the M3 components or of the
        linked fixtures, no law id and no target source file, imports neither tests nor tests_m3; no module of the
        holon-ir/0.1-0.3 generator closures imports it."""
        f = ROOT / MODULE
        self.assertTrue(f.exists(), f"{MODULE} is missing")
        text = f.read_text(encoding="utf-8")
        names = X.target_names(ROOT)
        compound = {n for n in names if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}
        quoted = {n for n in names if len(n) >= 3} - X.GENERIC_WORDS
        self.assertEqual(sorted(n for n in compound
                                if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text)), [])
        self.assertEqual(sorted(n for n in quoted if re.search(rf"[\"']{re.escape(n)}[\"']", text)), [])
        self.assertNotRegex(text, r"\bL_(par|sort|disch|undo|fact|nat|sym|own|tag)_\w+")
        self.assertNotRegex(text, r"(?i)\bmorph\b|Rollup\.sol|header_length", "no target name or source file")
        self.assertNotRegex(text, r"(?m)^\s*(from|import)\s+tests(_m\d)?\b", "the instruments are not holon's")
        records = holon_module("holon.records")
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            self.assertNotIn(MODULE, records.generator_files(v, ROOT), f"{MODULE} entered the {v} generator closure")

    def test_i42_outputs_are_untouched(self):
        """I43-R8 (rule C5): some commit after the I43 prereg writes gen/M3/theory2/, and no commit (merges aside) after
        the prereg that changes an I43 output (gen/M3/theory2/, gen/<M>/lean/ for M1-M3, holon/gen/theory2.py), a Lean
        emitter (holon/gen/lean_*.py), holon/lean.py or any of the key's outcome paths changes a file under
        gen/M3/theory/ (the third review: holon/lean.py and the outcome paths added). Needs the real checkout's history:
        a missing .git is a failure, never a skip. The base 7fd9755 holds I42's outputs (merged at 512e6f3), so it
        checks them (review m1)."""
        c0 = prereg_commit()
        outcome = json.loads((ROOT / "spec/M3/predictions.json").read_text(encoding="utf-8"))["iterations"]["I43"]
        mine = set(git("rev-list", "--no-merges", f"{c0}..HEAD", "--", *I43_OUTPUTS, "holon/gen/lean_*.py",
                       "holon/lean.py", *outcome["outcome_paths"]).split())
        self.assertTrue(git("rev-list", f"{c0}..HEAD", "--", "gen/M3/theory2").split(),
                        "no commit after the I43 prereg writes gen/M3/theory2/ (I43 builds it)")
        for c in sorted(mine):
            touched = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c).split()
            self.assertEqual([f for f in touched if f.startswith(I42_OUT)], [], c)


if __name__ == "__main__":
    unittest.main()
