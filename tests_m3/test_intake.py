"""I41: the untrusted prover intake (whitepaper §9.1 "Provers (untrusted: tactic generators, agents) -> PROOF/", §9.2(3),
§9.4 "Provers have no write access to LAWS/", §10.4 "Agents ... fill the remaining goals. The only thing they can produce
that matters is a proof file the kernel accepts", §12 L14; BUILD_PLAN I41). The human answered Q14c yes, through an
intake: Bend checks every agent proof, and the intake never trusts one (docs/HUMAN_ANSWERS.md). This docstring is the
contract.

Inbox (the only thing an agent writes)
  proofs/inbox/<law_id>/ holds exactly two regular files, and nothing else (no symlink, no subdirectory):
    PROOF.bend       the proof, written for the path the separated layout gives it,
                     holon.mpipeline.layout(<M>, gen/<M>, <law_id>)[1] / "PROOF.bend" (gen/<M>/proofs/<law_id>/PROOF.bend
                     from M2 on). It imports the model as `import ../../model/<model>.bend as M`, imports its own law
                     exactly as holon.mpipeline.law_import_problem requires (`import ../../laws/<law_id>/LAWS.bend as
                     Laws`), may import ../../core/PROOF.bend, and fills the law with `def Laws.<law name>(..)`, where
                     <law name> is holon.gen.mlaws.law_name(<law_id>).
    submission.json  {"law_id": "<law_id>", "prover": "agent:<session>", "statement_hash": "sha256:<64 hex>"}, exactly
                     these keys. law_id is the directory name. <session> matches [A-Za-z0-9][A-Za-z0-9_.-]{0,63}.
  An agent never writes laws/, gen/ or results/. The intake reads nothing else an agent could have written.

Eligibility
  A law is eligible iff its generators returned UNKNOWN: its committed record results/<M>/<law_id>.json has status
  UNKNOWN, or status PROVED with a prover "agent:..." (an agent proof accepted earlier). At this prereg's base f8fa447
  there are 34 records (M0 8, M1 16, M2 10) and exactly two are eligible, both M2 SORT-site laws over the rollup model:
  L_sort_site_def_lci_356891e4 and L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17. Each is
  forall s: Reach, a: Act, agg. site_ok(a, s) == true; coercion_guard does not apply, reach_invariant refuses it ("needs
  exactly one forall Reach binder and no premises"), and the SORT-site search found no witness. The real-law tests pick
  laws from the committed records at run time, so a later re-derivation (I20) that renames them breaks nothing.

Decision (holon/intake.py)
  A submission passes these checks in this order. The first one that fails refuses it, and that is its reason.
  holon.intake.REASONS is exactly this tuple:
    bad_submission          the directory or submission.json is not as above (an extra file such as a LAWS.bend, a
                            missing file, a symlink, a key missing or extra, a law_id other than the directory name, a
                            prover that is not agent:<session>, "generator" included);
    unknown_law             no milestone has both laws/<M>/<law_id>.json and a committed record for it;
    statement_mismatch      statement_hash is not the record's statement_hash (the frozen statement);
    not_unknown             the law is not eligible: its generators PROVED or REFUTED it;
    escape_hatch            holon.bend.escape_hatches(PROOF.bend) is non-empty: ?TODO, ?name, @unsafe, def f?(..),
                            import "./x.c", comments included; "hatches" lists the classes found
                            (hole, unsafe, unsafe_sugar, foreign_import);
    declares_law            PROOF.bend declares a law, comments removed as Bend removes them (G3's rule for files under
                            proofs/, holon.gate.laws_in_proofs);
    missing_expected_law    PROOF.bend does not import its own law file at the layout path
                            (holon.mpipeline.law_import_problem). A file that imports no law, or another law, can check
                            and still prove nothing about this one (BEND_PRIMER 3.1, audit F-M2-07);
    law_file_changed        G1: a law file of the law's milestone differs from its regeneration (below);
    generated_file_changed  G1: the milestone's model or core library differs from its regeneration;
    kernel_rejected         a required kernel did not accept the proof against the regenerated law file;
    over_budget             bend2 did not finish within the budget (it is killed at the budget).
  No kernel runs on a submission refused by any of the first eight checks.

  Regeneration (G1, for the law's milestone M). Into a fresh temporary directory, with a fresh build directory (never
  the tree's build/), the intake regenerates from the frozen IR (laws/<M>/), the facts and the committed records:
    - the model gen/<M>/model/<model>.bend (holon.mpipeline.run_model: the instrumented model where DERIVATION.json
      holds SORT-site laws of the document);
    - the core library gen/<M>/core/{LAWS,PROOF}.bend (M2 and later; holon.gen.core.emit);
    - the law file of every law of M, as `holon run` writes it: the statement for a PROVED record, the counter-law for a
      REFUTED one (with the record's failing_conjunct), the statement for the submission's own law.
  "differs" lists, sorted and repo-relative, every one of these paths whose bytes in the tree differ from the
  regeneration: a law file present but different, a law file missing although its record names it, a model or core
  file different or missing. An UNKNOWN law has no law file in the tree, since holon run writes none, and its absence
  is no difference. The proof is checked only inside the regenerated directory, at its layout path. No kernel ever reads
  the tree's own law, model or core files.

  Kernels. holon.intake.required_kernels(M, root) -> ["bend2"] + ["bendtt"] when holon.bend.verdict_enabled()
  + ["lean4"] when M is in I9's Lean-covered set (holon.lean.applicable(M, root): holon-ir/0.1, i.e. M0). Each must
  accept the proof: bend2 exits 0 and says ALL PROOFS CHECK within the budget; bendtt is `bend PROOF.bend --verdict`;
  lean4 checks the Lean text holon.lean's emitters produce for the PROVED verdict. No M0 law is eligible today, so the
  lean4 branch is dormant.

  Budget. The per-file budget of G5: bend.budget_s_per_file in config/holon.json (120 s at f8fa447). `--budget-s S`
  lowers it for one CLI run: 0 < S <= the configured budget, otherwise exit 2 before anything is read. holon run always
  uses the configured budget.

CLI (writes nothing: no file under the repository changes; temporary directories only)
  python -m holon intake [--milestone M] [--root DIR] [--inbox DIR] [--law ID ...] [--budget-s S] [--json]
    Decides every submission under the inbox (default <root>/proofs/inbox) whose law belongs to M (to any milestone
    without --milestone). A submission whose law belongs to no milestone is decided (unknown_law) in every run. With
    --law, only the named submissions are decided, and a named one that is missing is a usage error. --json prints
      {"inbox": "<path>", "budget_s": S, "decisions": [<decision>, ...]}   (decisions sorted by law_id)
      <decision> = {"law_id", "milestone": M | null, "submission": "<dir, root-relative when inside root>",
                    "prover": "agent:<session>" | null, "proof_sha256": "<sha256 of PROOF.bend>" | null,
                    "verdict": "accepted" | "refused", "reason": null | <one of REASONS>, "detail": "<text>",
                    "hatches": [...], "differs": [...],
                    "kernels": {"bend2": r, "bendtt": r, "lean4": r}, "seconds": <bend2 wall seconds> | null}
      r is checked | failed | timeout | not_run (required, but an earlier check refused) | not_applicable (not required;
      lean4 when the submission names no milestone).
    Exit status 0 iff every decided submission was accepted (0 for an empty inbox), 1 otherwise, 2 on a usage error.
  python -m holon intake --list [--milestone M] [--root DIR] [--json]
    Prints {"eligible": {"<M>": [law ids, sorted]}} for every milestone (each laws/<X>/ with a REGISTRY.json, X matching
    ^[MT][0-9]+$), or for M alone.
  Everything but "seconds" is deterministic.

holon run (G1 reproduces it)
  For a state-machine milestone (holon-ir/0.2 and 0.3: M1, M2 and the test milestones), `holon run --milestone M`
  decides, after the generators and the refuter, every law they leave UNKNOWN that has a submission in
  <root>/proofs/inbox. The checks and the configured budget are the same, and the run's own outcome stands in for the
  committed record.
    accepted: the record becomes PROVED with prover "agent:<session>";
      artifacts.proof = gen/<M>/proofs/<law_id>/PROOF.bend, a byte-identical copy of the inbox file;
      artifacts.laws = gen/<M>/laws/<law_id>/LAWS.bend, the generators' law file; artifacts.law_name;
      checker {"exit_code": 0, "marker": "ALL PROOFS CHECK"}; kernel.verdict, kernels and independence_class as for
      every PROVED record (holon.records.kernels, holon.records.independence_class); scope from the statement;
      bound null; non_vacuity as for every PROVED law (the inhabitant search of holon.inhabit, written to
      gen/<M>/<law_id>/nonvac/{LAWS,PROOF}.bend, which G11V re-checks);
      attempts = the generators' attempts, unchanged, then
      {"kind": "intake", "submission": "proofs/inbox/<law_id>", "prover", "proof_sha256", "verdict": "accepted",
       "reason": null, "kernels": {...}, "seconds"}.
      The record differs from the generators' UNKNOWN record in exactly status, prover, artifacts, attempts, bound,
      checker, kernel, kernels, independence_class and non_vacuity (the fields in which a generator-PROVED record
      differs from an UNKNOWN one), and the run adds exactly four gen/ files: the law file, the proof copy and the two
      inhabitant files.
    refused: the record stays as the generators left it (UNKNOWN, prover "generator", no gen/ file for the law), with one
      more attempt {"kind": "intake", ..., "verdict": "refused", "reason": <REASON>, "detail": "<text>"}.
  A submission for a law the generators decided changes nothing in the run. No other record depends on the inbox. The
  exit status of holon run does not depend on the inbox (a refused submission is an attempt, not an error), so G1's
  regeneration of a tree whose inbox holds a refused proof yields the UNKNOWN record. M0 (holon/pipeline.py) reads no
  inbox; its records only gain the field below.

Records
  Every record gains "prover": "generator" | "agent:<session>". spec/schemas/result_record_v2.schema.json requires it,
  with pattern ^(generator|agent:[A-Za-z0-9][A-Za-z0-9_.-]{0,63})$. It has no pending value: I41 introduces and fills
  it (BUILD_PLAN I1). "agent:" appears only on a PROVED record, and G9 validates the field on every gate run.
  Regression: one commit introduces the field into every committed record under results/M0, results/M1 and results/M2.
  It is the first commit, oldest first, whose records carry "prover". It adds "prover": "generator" and changes nothing
  else, with one mechanical exception: generator_sha256 of the holon-ir/0.2 and 0.3 records (M1, M2) may change, since
  holon/records.py and the pipelines are in their generator set (holon.records.generator_files). M0's set contains
  neither, so the 8 M0 records change by the prover key alone. `seconds` is ignored, as in G1. summary.json and
  deps.json stay byte-identical.

Gate
  No new check. G3 scans the copied proof under gen/<M>/proofs/ (escape hatches, no law). G5 re-checks it within the
  budget, together with its law import. G7 re-checks it with BendTT, G11 checks its law file, and G9 validates prover.
  G1 rebuilds the record from the committed inbox. So every gate run re-decides every agent proof from scratch: a
  committed agent-proved record whose inbox file no longer passes the intake fails G1 (I41-P3's negative control).

Fixture (tests_m3/fixtures/intake/)
  toy_intake.facts.json and ledger.json are a copy of the I8 toy reach machine: x is copied from y, y is only ever
  cleared, and both start at 0. laws/ holds three holon-ir/0.3 laws of the test milestone T41. The tests write them into
  laws/T41/ of a copy of the repository, with facts_sha256 filled and a REGISTRY.json, and run
  `holon run --milestone T41 --no-registry` and `holon metrics --milestone T41`. They then fill the registry's statement
  hashes from the records, so that the gate's G1 (which runs holon run with the registry) can regenerate T41:
    L_i41_x_any_act  forall s: Reach, a: Act. x_zero(s) == true. It is true, and it is the target. reach_invariant refuses
                     it with the same message as the two real UNKNOWN M2 laws, whose binders are s: Reach, a: Act, agg.
                     No other class applies and the refuter finds no witness, so the generators return UNKNOWN.
    L_i41_y          forall s: Reach. y_zero(s) == true: PROVED by reach_invariant.
    L_i41_flag       forall s: Reach. flag_down(s) == true: REFUTED (raise).
  proofs/valid/PROOF.bend      a hand-written Reach induction for L_i41_x_any_act (strengthening y == 0; a ignored).
  proofs/edits_law/LAWS.bend   the target's law file as an agent edits it: the generated header is kept, and the claim is
                               added as a premise h. proofs/edits_law/PROOF.bend proves that edited law.
  proofs/no_law/PROOF.bend     the same induction as a plain def ag_main; it imports no law.
  The tests derive further proofs from valid/PROOF.bend (variants() below): one per escape hatch, a declared law, a
  wrong strengthening (y == 1), and the valid proof plus a true but costly lemma (ag_walk(28) makes 2^28 calls).
  Disclosure: before this commit the drafter ran the current generators on the three laws (UNKNOWN, PROVED, REFUTED, as
  above). The drafter also ran Bend 2.0.36 on the fixture proofs in a scratch tree that holds the generated model and
  the law file the current emitter writes. valid/ and no_law/ say ALL PROOFS CHECK (valid/ also with --verdict).
  edits_law/ checks against its edited law file and fails against the generated one. The costly lemma checks in 24 s at
  depth 24, so depth 28 runs for minutes. None of this exercises the intake, which does not exist yet.
  The reviewer ran, in scratch copies: setup_fixture and gate_t41 at baseline (G1, G3, G5, G7, G9, G11 and G11V pass:
  "3 records identical", "2 proofs re-checked", "dual-kernel: 2 proofs", "3 records valid", "1 premised PROVED laws
  inhabited"); Bend on valid/ (exit 0) and the wrong variant (exit 1) against the generated law text; and a proof that
  imports a helper holding `@unsafe def ag_any(-A: Type) -> A` (Bend 2.0.36 refuses it: "2 defs rely on unsafe or
  foreign code", so the kernel itself catches unsafe code reached through an import; a long ../ path out of the tree
  to the same helper was refused as "not an import path of plain names"). Nothing here exercises the intake either.
  Why the positive case is a fixture law: a proof of either real UNKNOWN law needs a Reach induction across the 10
  actions of the 7044-line rollup model. That proof would be a research result of its own, and the positive prediction
  is meant to test the intake, not whether such a proof can be found. The fixture law is UNKNOWN for the same reason the
  real ones are (reach_invariant's one-binder rule). The real laws serve every negative control and the end-to-end path
  to the kernel (P8).

Rules
  - AGENTS.md is binding. The intake changes no statement, adds or drops no premise, special-cases no law id (no law id
    appears in holon/intake.py) and never imports tests/reference.
  - An agent proof is PROVED exactly when a generator proof would be: Bend accepted the proof file, and the expected law
    is in it. The intake trusts no file it did not regenerate.
  - No skips. A miss is a Surprise. TestProverField reads git history: without .git it fails, never skips.
  - Determinism: decisions (except seconds), records and gen/ files are byte-identical across runs.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests._util import ROOT, copy_repo, load_json, run_bend, run_holon  # noqa: F401  (frozen helpers)
from tests.reference import mini_schema

FX = ROOT / "tests_m3" / "fixtures" / "intake"
FACTS = "tests_m3/fixtures/intake/toy_intake.facts.json"
T = "T41"
TARGET, Y, FLAG = "L_i41_x_any_act", "L_i41_y", "L_i41_flag"
SESSION = "agent:fixture-i41"
MODEL = "toy_intake_facts.bend"
REASONS = ("bad_submission", "unknown_law", "statement_mismatch", "not_unknown", "escape_hatch", "declares_law",
           "missing_expected_law", "law_file_changed", "generated_file_changed", "kernel_rejected", "over_budget")
KERNELS = ("bend2", "bendtt", "lean4")
PROVER_PATTERN = r"^(generator|agent:[A-Za-z0-9][A-Za-z0-9_.-]{0,63})$"
FIXTURE_BUDGET_S = 10
SLOW_DEPTH = 28
REACH_REFUSAL = "unsupported: reach_invariant needs exactly one forall Reach binder and no premises"
TARGET_LAW = ("law l_i41_x_any_act:\n  for +s: M.HSt\n  for r_s: M.Reach<s>\n  for +a: M.HAct\n"
              "  {M.x_zero(s) == True{} : Bool}\n")
BASE_UNKNOWN_M2 = ("L_sort_site_def_lci_356891e4", "L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17")
ZERO_HASH = "sha256:" + "0" * 64


# ------------------------------------------------------------------ helpers (no tests_m3/_m3.py: they live here)
def holon_module(name: str):
    """Import a holon module inside a test, so a missing module fails that test (red), not the file."""
    return importlib.import_module(name)


def strip_seconds(x):
    if isinstance(x, dict):
        return {k: strip_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [strip_seconds(v) for v in x]
    return x


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def verdict_enabled() -> bool:
    return bool(holon_module("holon.bend").verdict_enabled())


def expected_kernels(result: str) -> dict:
    """The kernels entry of a decision for the fixture (holon-ir/0.3): bend2 and, when enabled, bendtt get result."""
    return {"bend2": result, "bendtt": result if verdict_enabled() else "not_applicable", "lean4": "not_applicable"}


def no_kernel_ran(d: dict) -> bool:
    k = d.get("kernels") or {}
    return k.get("bend2") == "not_run" and all(k.get(n) in ("not_run", "not_applicable") for n in KERNELS)


def files(root: Path, *subs: str) -> dict[str, bytes]:
    """Every file under root/<sub> (or the file root/<sub>), repo-relative, with its bytes; __pycache__ skipped."""
    out: dict[str, bytes] = {}
    for sub in subs:
        base = root / sub
        if base.is_file():
            out[sub] = base.read_bytes()
        elif base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def records(repo: Path, m: str = T) -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted((repo / "results" / m).glob("L*.json"))}


def run_t41(repo: Path) -> None:
    """holon run --milestone T41, then holon metrics (results/T41/metrics.json, which the gate's G1 compares)."""
    p = run_holon(["run", "--milestone", T, "--no-registry"], cwd=repo)
    if p.returncode != 0:
        raise AssertionError(f"holon run --milestone {T} failed: {(p.stdout + p.stderr)[-3000:]}")
    q = run_holon(["metrics", "--milestone", T], cwd=repo)
    if q.returncode != 0:
        raise AssertionError(f"holon metrics --milestone {T} failed: {(q.stdout + q.stderr)[-3000:]}")


def setup_fixture(repo: Path) -> dict[str, dict]:
    """laws/T41 in a copy of the repository (facts_sha256 filled, REGISTRY.json), then the generators' run; the records.
    The registry's statement hashes are then filled from the generators' records, so that the gate's G1 (which runs
    holon run with the registry) can regenerate T41: at baseline G1, G3, G5, G7, G9, G11 and G11V pass on this tree."""
    sha = hashlib.sha256((repo / FACTS).read_bytes()).hexdigest()
    d = repo / "laws" / T
    d.mkdir(parents=True)
    ids = []
    for p in sorted((FX / "laws").glob("L_*.json")):
        law = load_json(p)
        law["facts_sha256"] = sha
        (d / p.name).write_text(json.dumps(law, indent=2, sort_keys=True) + "\n")
        ids.append(law["law_id"])
    (d / "REGISTRY.json").write_text(json.dumps({"milestone": T, "facts": FACTS, "facts_sha256": sha,
                                                 "facts_files": {FACTS: sha}, "statements": {i: None for i in ids}},
                                                indent=2, sort_keys=True) + "\n")
    run_t41(repo)
    recs = records(repo)
    reg = load_json(d / "REGISTRY.json")
    reg["statements"] = {i: recs[i]["statement_hash"] for i in ids if i in recs}
    (d / "REGISTRY.json").write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    return recs


def gate_t41(repo: Path, report: Path, checks: str) -> tuple[dict, str]:
    """holon gate --milestone T41 --checks <checks>: (the report, the end of the log)."""
    g = run_holon(["gate", "--milestone", T, "--checks", checks, "--report", str(report)], cwd=repo)
    return (load_json(report) if report.exists() else {}), (g.stdout + g.stderr)[-3000:]


def submit(inbox: Path, law_id: str, proof: str, statement_hash: str, prover: str = SESSION,
           extra: dict | None = None, manifest: dict | None = None) -> Path:
    """Write one submission: inbox/<law_id>/{PROOF.bend, submission.json} (plus extra files)."""
    d = inbox / law_id
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "PROOF.bend").write_text(proof)
    sub = manifest if manifest is not None else {"law_id": law_id, "prover": prover, "statement_hash": statement_hash}
    (d / "submission.json").write_text(json.dumps(sub, indent=2, sort_keys=True) + "\n")
    for name, text in (extra or {}).items():
        (d / name).write_text(text)
    return d


def intake(root: Path, *args: str, cwd: Path | None = None) -> tuple[subprocess.CompletedProcess, dict | None]:
    p = run_holon(["intake", "--root", str(root), "--json", *args], cwd=cwd or root)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = None
    return p, out


def decision(test: unittest.TestCase, p: subprocess.CompletedProcess, out: dict | None, law_id: str) -> dict:
    test.assertIsNotNone(out, f"holon intake printed no JSON (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
    got = [d for d in out["decisions"] if d["law_id"] == law_id]
    test.assertEqual(len(got), 1, out)
    return got[0]


def variants(valid: str, depth: int = SLOW_DEPTH) -> dict[str, str]:
    """Proofs derived from proofs/valid/PROOF.bend by fixed text edits (each anchor occurs exactly once)."""
    last, law_def = "  ag_first(s, ag_reach(s, r_s))\n", "def Laws.l_i41_x_any_act(s, r_s, a):\n"
    assert valid.count(last) == 1 and valid.count(law_def) == 1 and valid.count("import Base\n") == 1
    loop = "def ag_loop{q}(+s: M.HSt) -> ag_goal(s):\n  ag_loop(s)\n\n"
    slow = ("\n# a true but costly lemma: ag_walk(n) makes 2^n calls before it reduces to True\n"
            "def ag_walk(+n: Nat) -> Bool:\n  match n:\n    case 0n:\n      True{}\n    case 1n+p:\n"
            "      Bool.and(ag_walk(p), ag_walk(p))\n\n"
            f"def ag_slow() -> {{ag_walk({depth}n) == True{{}} : Bool}}:\n  {{==}}\n")
    out = {
        "hole_todo": valid.replace(last, "  ?TODO\n"),
        "hole_name": valid.replace(last, "  ?goal\n"),
        "unsafe": valid.replace(law_def, "@unsafe " + loop.format(q="") + law_def).replace(last, "  ag_loop(s)\n"),
        "unsafe_sugar": valid.replace(law_def, loop.format(q="?") + law_def).replace(last, "  ag_loop(s)\n"),
        "foreign_import": valid.replace("import Base\n", "import Base\nimport \"./ag.c\"\n"),
        "declares_law": valid.replace(law_def, "law ag_extra:\n  {True{} == True{} : Bool}\n\ndef ag_extra():\n"
                                               "  {==}\n\n" + law_def),
        "wrong": valid.replace("{ag_y(s) == 0n : Nat}", "{ag_y(s) == 1n : Nat}"),
        "over_budget": valid + slow,
    }
    assert all(v != valid for v in out.values())
    return out


def kernel_alone(repo: Path, law_text: str, proof_text: str, law_id: str = TARGET) -> tuple[int, str]:
    """What Bend alone says of a proof in a scratch gen/T41 tree: the copy's generated model and core, the given law
    file and the proof, at the layout path. Shows that a refusal is the intake's, not the kernel's."""
    tmp = Path(tempfile.mkdtemp(prefix="holon-i41-kernel-"))
    try:
        g = tmp / "gen" / T
        (g / "model").mkdir(parents=True)
        shutil.copy(repo / "gen" / T / "model" / MODEL, g / "model" / MODEL)
        if (repo / "gen" / T / "core").is_dir():
            shutil.copytree(repo / "gen" / T / "core", g / "core")
        (g / "laws" / law_id).mkdir(parents=True)
        (g / "laws" / law_id / "LAWS.bend").write_text(law_text)
        (g / "proofs" / law_id).mkdir(parents=True)
        (g / "proofs" / law_id / "PROOF.bend").write_text(proof_text)
        return run_bend(["PROOF.bend"], cwd=g / "proofs" / law_id)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def real_wrong_proof(lid: str, body: str = "{==}") -> str:
    """A proof for a real M2 law that fills the law with `body`: it imports the model and its own law at the layout
    path, takes one parameter per emitted binder (a Reach binder emits two: s and r_s) and is wrong."""
    law = load_json(ROOT / "laws" / "M2" / f"{lid}.json")
    rec = load_json(ROOT / "results" / "M2" / f"{lid}.json")
    binders = law["statement"]["binders"]
    n = len(binders) + sum(1 for b in binders if b["type"] == "Reach")
    # amended (spec/M3/amendments.jsonl; I20's SORT-width records name no model): a record without artifacts.model is
    # a law holon run decides without a Bend model of its document, so the proof imports the model holon would name
    # after that document (holon.mpipeline.model_name), which the regenerated tree does not hold either
    model = (Path(rec["artifacts"]["model"]).name if rec["artifacts"].get("model")
             else re.sub(r"[^A-Za-z0-9_]", "_", Path(law["facts"]).stem) + ".bend")
    params = ", ".join(f"p{i}" for i in range(n))
    return (f"import Base\nimport ../../model/{model} as M\nimport ../../laws/{lid}/LAWS.bend as Laws\n\n"
            f"def Laws.{lid.lower()}({params}):\n  {body}\n")


def m2_outputs() -> dict[str, bytes]:
    """The tracked M2 files a decision could touch: gen/M2, laws/M2, the M2 records and summaries, the inbox."""
    out = files(ROOT, "gen/M2", "laws/M2", "proofs")
    for p in sorted((ROOT / "results" / "M2").glob("*.json")):
        out[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    return out


def git(*args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {p.stderr.strip()} (this test reads the history: it fails, "
                             "never skips, without .git)")
    return p.stdout


# ------------------------------------------------------------------ the contract itself
class TestContract(unittest.TestCase):
    def test_reasons_are_the_closed_vocabulary_in_check_order(self):
        """I41-R3: the reasons, in the order the checks run."""
        self.assertEqual(tuple(holon_module("holon.intake").REASONS), REASONS)

    def test_record_schema_requires_the_prover_field(self):
        """I41-R1/R3: the v2 record schema requires prover (no pending value), with the contract's pattern."""
        schema = load_json(ROOT / "spec" / "schemas" / "result_record_v2.schema.json")
        self.assertIn("prover", schema["required"])
        self.assertEqual(schema["properties"]["prover"].get("pattern"), PROVER_PATTERN)
        base = load_json(ROOT / "results" / "M0" / "L_par_hdr_v0.json")
        for value, ok in (("generator", True), (SESSION, True), ("agent:session_01MaUnkwdsvUVmLKnC1t3siH", True),
                          ("agent:", False), ("agent:-x", False), ("human", False), ("pending:I41", False),
                          ("Generator", False), (None, False)):
            rec = dict(base)
            rec.pop("prover", None)
            if value is not None:
                rec["prover"] = value
            with self.subTest(prover=value):
                errs = mini_schema.errors(rec, schema)
                self.assertEqual(errs == [], ok, errs)

    def test_required_kernels_follow_the_lean_covered_set(self):
        """I41-R3: bend2 always, bendtt when the verdict is enabled, lean4 only in I9's Lean-covered set (M0)."""
        rk = holon_module("holon.intake").required_kernels
        bt = ["bendtt"] if verdict_enabled() else []
        self.assertEqual(list(rk("M0", ROOT)), ["bend2"] + bt + ["lean4"])
        for m in ("M1", "M2"):
            with self.subTest(milestone=m):
                self.assertEqual(list(rk(m, ROOT)), ["bend2"] + bt)

    def test_the_budget_can_only_be_lowered(self):
        """I41-R3: --budget-s may lower the configured per-file budget, never raise it (exit 2 before anything else).
        Every run decides the same empty inbox, which exits 0 and reports the budget it used."""
        budget = float(load_json(ROOT / "config" / "holon.json")["bend"].get("budget_s_per_file", 120))
        empty = Path(tempfile.mkdtemp(prefix="holon-i41-empty-"))
        try:
            for ok in (f"{budget:g}", "10"):
                with self.subTest(budget=ok):
                    p = run_holon(["intake", "--root", str(ROOT), "--inbox", str(empty), "--json", "--budget-s", ok])
                    self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])
                    out = json.loads(p.stdout)
                    self.assertEqual((out["decisions"], float(out["budget_s"])), ([], float(ok)))
            p = run_holon(["intake", "--root", str(ROOT), "--inbox", str(empty), "--json"])
            self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])
            self.assertEqual(float(json.loads(p.stdout)["budget_s"]), budget)
            for bad in (f"{budget + 1:g}", "0", "-5"):
                with self.subTest(budget=bad):
                    q = run_holon(["intake", "--root", str(ROOT), "--inbox", str(empty), "--json", "--budget-s", bad])
                    self.assertEqual(q.returncode, 2, (q.stdout + q.stderr)[-2000:])
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_intake_names_no_law_and_reads_no_oracle(self):
        """I41-R3 (AGENTS rules 2 and 5): holon/intake.py special-cases no law id and never touches tests/reference."""
        holon_module("holon.intake")
        src = (ROOT / "holon" / "intake.py").read_text(encoding="utf-8")
        for bad in ("L_i41", "L_sort_site", "fixture-i41", "tests.reference", "tests/reference", "L_par_hdr",
                    "L_undo"):
            with self.subTest(text=bad):
                self.assertNotIn(bad, src)
        self.assertIsNone(re.search(r"(?i)\bmorph", src), "holon/intake.py names the Morph target")


# ------------------------------------------------------------------ the fixture, one CLI decision at a time
class TestFixtureIntake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.I = holon_module("holon.intake")   # red until I41 exists: nothing below runs without it
        cls.repo = copy_repo()
        cls.base = setup_fixture(cls.repo)
        cls.gen0 = files(cls.repo, f"gen/{T}")
        cls.inbox = cls.repo / "proofs" / "inbox"
        cls.valid = (FX / "proofs" / "valid" / "PROOF.bend").read_text()
        cls.var = variants(cls.valid)
        cls.hash = cls.base[TARGET]["statement_hash"] if TARGET in cls.base else ZERO_HASH

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def fresh(self) -> None:
        """An empty inbox, and gen/T41 exactly as the generators' run left it."""
        shutil.rmtree(self.inbox, ignore_errors=True)
        shutil.rmtree(self.repo / "gen" / T, ignore_errors=True)
        for rel, b in self.gen0.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_bytes(b)

    def decide(self, *args: str) -> tuple[subprocess.CompletedProcess, dict | None]:
        return intake(self.repo, "--milestone", T, *args)

    def refused(self, law_id: str, reason: str, *args: str) -> dict:
        p, out = self.decide(*args)
        d = decision(self, p, out, law_id)
        self.assertEqual((d["verdict"], d["reason"]), ("refused", reason), d)
        self.assertEqual(p.returncode, 1, d)
        return d

    def test_fixture_preconditions(self):
        """Construction: the generators leave the target UNKNOWN for reach_invariant's one-binder rule and find no
        witness; L_i41_y is PROVED and L_i41_flag REFUTED; the target has no law file; every record names its prover."""
        self.assertEqual({k: r["status"] for k, r in self.base.items()},
                         {TARGET: "UNKNOWN", Y: "PROVED", FLAG: "REFUTED"})
        att = self.base[TARGET]["attempts"]
        self.assertIn(REACH_REFUSAL, [a.get("error") for a in att if a.get("generator") == "reach_invariant"])
        self.assertTrue(any(a.get("kind") == "refute" and a.get("hit") is False for a in att), att)
        self.assertIsNone(self.base[TARGET]["artifacts"]["laws"])
        self.assertFalse((self.repo / "gen" / T / "laws" / TARGET).exists())
        for k, r in self.base.items():
            with self.subTest(law=k):
                self.assertEqual(r.get("prover"), "generator")

    def test_a_proof_that_edits_its_law_file_is_refused_by_g1(self):
        """I41-P1 (plan): the agent writes edits_law/LAWS.bend over the target's law file and submits a proof of that
        edited law. Bend alone accepts the pair; the intake refuses it by G1 (law_file_changed), naming exactly that
        file, before any kernel runs, and leaves the edit where it is (it writes nothing)."""
        self.fresh()
        edited = (FX / "proofs" / "edits_law" / "LAWS.bend").read_text()
        proof = (FX / "proofs" / "edits_law" / "PROOF.bend").read_text()
        code, out = kernel_alone(self.repo, edited, proof)
        self.assertEqual(code, 0, out[-1500:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-1500:])
        lf = self.repo / "gen" / T / "laws" / TARGET / "LAWS.bend"
        lf.parent.mkdir(parents=True, exist_ok=True)
        lf.write_text(edited)
        submit(self.inbox, TARGET, proof, self.hash)
        d = self.refused(TARGET, "law_file_changed")
        self.assertEqual(d["differs"], [f"gen/{T}/laws/{TARGET}/LAWS.bend"])
        self.assertTrue(no_kernel_ran(d), d)
        self.assertEqual(d["prover"], SESSION)
        self.assertEqual(lf.read_text(), edited)

    def test_a_valid_agent_proof_is_accepted(self):
        """I41-P2 (plan), the decision: the hand-written induction for the UNKNOWN target is accepted, every required
        kernel checked it (bend2, and bendtt when enabled), G1 found nothing changed, and the CLI wrote nothing."""
        self.assertTrue(verdict_enabled(), "I41-P2 claims bendtt checked: BendTT must be available")
        self.fresh()
        submit(self.inbox, TARGET, self.valid, self.hash)
        before = files(self.repo, "laws", f"gen/{T}", f"results/{T}")
        p, out = self.decide()
        d = decision(self, p, out, TARGET)
        self.assertEqual(p.returncode, 0, d)
        self.assertEqual((d["verdict"], d["reason"]), ("accepted", None), d)
        self.assertEqual((d["milestone"], d["prover"]), (T, SESSION))
        self.assertEqual(d["proof_sha256"], sha256(self.valid.encode()))
        self.assertEqual((d["hatches"], d["differs"]), ([], []))
        self.assertEqual(d["kernels"], expected_kernels("checked"))
        self.assertEqual(files(self.repo, "laws", f"gen/{T}", f"results/{T}"), before)

    def test_proofs_for_proved_or_refuted_fixture_laws_are_refused(self):
        """I41-P4, fixture half: an agent resubmits the generators' own proof of L_i41_y (PROVED; Bend accepts it) and
        the counter-law proof of L_i41_flag (REFUTED). Both are refused not_unknown before any kernel runs."""
        self.fresh()
        for lid in (Y, FLAG):
            text = (self.repo / self.base[lid]["artifacts"]["proof"]).read_text()
            submit(self.inbox, lid, text, self.base[lid]["statement_hash"])
        p, out = self.decide()
        self.assertEqual(p.returncode, 1, (p.stdout + p.stderr)[-2000:])
        for lid in (Y, FLAG):
            with self.subTest(law=lid):
                d = decision(self, p, out, lid)
                self.assertEqual((d["verdict"], d["reason"]), ("refused", "not_unknown"), d)
                self.assertTrue(no_kernel_ran(d), d)

    def test_escape_hatches_are_refused_before_any_kernel(self):
        """I41-P5, fixture half: ?TODO, ?name, @unsafe, def f?(..) and a foreign import, each added to the valid proof,
        are refused escape_hatch naming exactly that class, before G1 and before any kernel."""
        for name, cls_ in (("hole_todo", "hole"), ("hole_name", "hole"), ("unsafe", "unsafe"),
                           ("unsafe_sugar", "unsafe_sugar"), ("foreign_import", "foreign_import")):
            with self.subTest(variant=name):
                self.fresh()
                submit(self.inbox, TARGET, self.var[name], self.hash)
                d = self.refused(TARGET, "escape_hatch")
                self.assertEqual(d["hatches"], [cls_])
                self.assertEqual(d["differs"], [])
                self.assertTrue(no_kernel_ran(d), d)

    def test_a_proof_that_checks_but_lacks_its_law_is_refused(self):
        """I41-P6: no_law/PROOF.bend carries the whole induction as a plain def and imports no law. Bend says ALL
        PROOFS CHECK on it; the intake refuses it missing_expected_law, before any kernel."""
        self.fresh()
        proof = (FX / "proofs" / "no_law" / "PROOF.bend").read_text()
        code, out = kernel_alone(self.repo, (FX / "proofs" / "edits_law" / "LAWS.bend").read_text(), proof)
        self.assertEqual(code, 0, out[-1500:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-1500:])
        submit(self.inbox, TARGET, proof, self.hash)
        d = self.refused(TARGET, "missing_expected_law")
        self.assertTrue(no_kernel_ran(d), d)

    def test_an_over_budget_proof_is_refused(self):
        """I41-P7: the valid proof plus ag_slow (ag_walk(28): 2^28 calls) under --budget-s 10 is refused over_budget,
        bend2 killed at the budget (timeout); under the same budget the valid proof alone is accepted."""
        self.fresh()
        submit(self.inbox, TARGET, self.var["over_budget"], self.hash)
        t0 = time.monotonic()
        d = self.refused(TARGET, "over_budget", "--budget-s", str(FIXTURE_BUDGET_S))
        elapsed = time.monotonic() - t0
        self.assertEqual(d["kernels"]["bend2"], "timeout", d)
        self.assertNotIn(d["kernels"].get("bendtt"), ("checked", "failed"), d)
        self.assertIsNotNone(d["seconds"], d)
        self.assertGreaterEqual(d["seconds"], FIXTURE_BUDGET_S, d)
        # unkilled, ag_walk(28) runs for about 6 minutes (24 s at depth 24, times 16); the intake's G1 regeneration of
        # T41 takes seconds, so 120 s of slack separates "killed at the budget" from "waited for bend2"
        self.assertLess(elapsed, FIXTURE_BUDGET_S + 120, "the intake must kill bend2 at the budget")
        self.fresh()
        submit(self.inbox, TARGET, self.valid, self.hash)
        p, out = self.decide("--budget-s", str(FIXTURE_BUDGET_S))
        d = decision(self, p, out, TARGET)
        self.assertEqual((d["verdict"], d["reason"]), ("accepted", None), d)

    def test_malformed_submissions_are_refused(self):
        """I41-R3: bad_submission (a LAWS.bend shipped beside the proof, prover "generator", a law_id that is not the
        directory, no submission.json), unknown_law and statement_mismatch, each before any kernel."""
        cases = [
            ("extra law file", TARGET, "bad_submission",
             lambda: submit(self.inbox, TARGET, self.valid, self.hash,
                            extra={"LAWS.bend": (FX / "proofs" / "edits_law" / "LAWS.bend").read_text()})),
            ("generator label", TARGET, "bad_submission",
             lambda: submit(self.inbox, TARGET, self.valid, self.hash, prover="generator")),
            ("law id mismatch", TARGET, "bad_submission",
             lambda: submit(self.inbox, TARGET, self.valid, self.hash,
                            manifest={"law_id": Y, "prover": SESSION, "statement_hash": self.hash})),
            ("no manifest", TARGET, "bad_submission",
             lambda: (submit(self.inbox, TARGET, self.valid, self.hash) / "submission.json").unlink()),
            ("unknown law", "L_i41_nope", "unknown_law",
             lambda: submit(self.inbox, "L_i41_nope", self.valid, self.hash)),
            ("stale statement", TARGET, "statement_mismatch",
             lambda: submit(self.inbox, TARGET, self.valid, ZERO_HASH)),
        ]
        for name, lid, reason, make in cases:
            with self.subTest(case=name):
                self.fresh()
                make()
                d = self.refused(lid, reason)
                self.assertTrue(no_kernel_ran(d), d)

    def test_a_proof_declaring_a_law_is_refused(self):
        """I41-R3: a proof that declares a law of its own (G3, prover separation) is refused declares_law."""
        self.fresh()
        submit(self.inbox, TARGET, self.var["declares_law"], self.hash)
        d = self.refused(TARGET, "declares_law")
        self.assertTrue(no_kernel_ran(d), d)

    def test_a_proof_of_another_law_is_refused(self):
        """I41-R3: the generators' proof of L_i41_y, submitted for the target, imports another law: missing_expected_law."""
        self.fresh()
        submit(self.inbox, TARGET, (self.repo / self.base[Y]["artifacts"]["proof"]).read_text(), self.hash)
        d = self.refused(TARGET, "missing_expected_law")
        self.assertTrue(no_kernel_ran(d), d)

    def test_edits_to_another_law_file_or_the_model_are_refused(self):
        """I41-R3: G1 covers every law file and the model, not only the target's: a comment added to L_i41_y's law
        file, that law file deleted, or a comment added to the model each refuse even the valid proof."""
        def touch(rel: str) -> None:
            f = self.repo / rel
            f.write_text(f.read_text() + "\n# edited\n")

        def delete(rel: str) -> None:
            (self.repo / rel).unlink()
        y_law = f"gen/{T}/laws/{Y}/LAWS.bend"
        model = f"gen/{T}/model/{MODEL}"
        for name, edit, rel, reason in (("law comment", touch, y_law, "law_file_changed"),
                                        ("law deleted", delete, y_law, "law_file_changed"),
                                        ("model comment", touch, model, "generated_file_changed")):
            with self.subTest(case=name):
                self.fresh()
                edit(rel)
                submit(self.inbox, TARGET, self.valid, self.hash)
                d = self.refused(TARGET, reason)
                self.assertEqual(d["differs"], [rel])
                self.assertTrue(no_kernel_ran(d), d)

    def test_a_wrong_proof_is_refused_by_the_kernel(self):
        """I41-R3: the valid proof with the strengthening y == 1 passes every check before the kernels, and bend2
        rejects it: kernel_rejected, G1 clean."""
        self.fresh()
        submit(self.inbox, TARGET, self.var["wrong"], self.hash)
        d = self.refused(TARGET, "kernel_rejected")
        self.assertEqual(d["kernels"]["bend2"], "failed", d)
        self.assertEqual((d["hatches"], d["differs"]), ([], []))

    def test_the_cli_writes_nothing_and_is_deterministic(self):
        """I41-R3: two runs over the same inbox print the same decisions (seconds aside) and change no file."""
        self.fresh()
        submit(self.inbox, TARGET, self.valid, self.hash)
        submit(self.inbox, Y, (self.repo / self.base[Y]["artifacts"]["proof"]).read_text(),
               self.base[Y]["statement_hash"])
        snap = ("laws", "gen", "results", "spec", "proofs", "build", "config", "docs", "holon", "tests_m3")
        before = files(self.repo, *snap)
        p1, o1 = self.decide()
        p2, o2 = self.decide()
        self.assertIsNotNone(o1, (p1.stdout + p1.stderr)[-2000:])
        self.assertEqual([d["law_id"] for d in o1["decisions"]], sorted([TARGET, Y]))
        self.assertEqual(canonical(strip_seconds(o1)), canonical(strip_seconds(o2)))
        self.assertEqual((p1.returncode, p2.returncode), (1, 1))
        self.assertEqual(files(self.repo, *snap), before)

    def test_law_selects_the_submissions_decided(self):
        """I41-R3: --law decides only the named submissions; a named submission that is missing is a usage error."""
        self.fresh()
        submit(self.inbox, TARGET, self.var["hole_todo"], self.hash)
        submit(self.inbox, Y, (self.repo / self.base[Y]["artifacts"]["proof"]).read_text(),
               self.base[Y]["statement_hash"])
        p, out = self.decide("--law", Y)
        self.assertIsNotNone(out, (p.stdout + p.stderr)[-2000:])
        self.assertEqual([(d["law_id"], d["reason"]) for d in out["decisions"]], [(Y, "not_unknown")])
        self.assertEqual(p.returncode, 1)
        q, _ = self.decide("--law", "L_i41_nope")
        self.assertEqual(q.returncode, 2, (q.stdout + q.stderr)[-2000:])

    def test_the_first_failing_check_decides(self):
        """I41-R3: the checks run in REASONS order, and the first failing one is the reason. Each submission below fails
        two checks; the earlier one wins, and no kernel runs."""
        lf = f"gen/{T}/laws/{TARGET}/LAWS.bend"
        edited = (FX / "proofs" / "edits_law" / "LAWS.bend").read_text()
        no_law = (FX / "proofs" / "no_law" / "PROOF.bend").read_text()
        y_proof = lambda: (self.repo / self.base[Y]["artifacts"]["proof"]).read_text()  # noqa: E731
        cases = [
            # statement_mismatch (3) before not_unknown (4)
            ("stale hash on a decided law", Y, "statement_mismatch", None,
             lambda: submit(self.inbox, Y, y_proof(), ZERO_HASH)),
            # not_unknown (4) before escape_hatch (5)
            ("hole in a proof of a decided law", Y, "not_unknown", None,
             lambda: submit(self.inbox, Y, y_proof().replace("import Base\n", "import Base\n# ?TODO\n", 1),
                            self.base[Y]["statement_hash"])),
            # escape_hatch (5) before law_file_changed (8)
            ("hole and an edited law file", TARGET, "escape_hatch", edited,
             lambda: submit(self.inbox, TARGET, self.var["hole_todo"], self.hash)),
            # missing_expected_law (7) before law_file_changed (8)
            ("no law imported and an edited law file", TARGET, "missing_expected_law", edited,
             lambda: submit(self.inbox, TARGET, no_law, self.hash)),
        ]
        for name, lid, reason, law_text, make in cases:
            with self.subTest(case=name):
                self.fresh()
                if law_text is not None:
                    (self.repo / lf).parent.mkdir(parents=True, exist_ok=True)
                    (self.repo / lf).write_text(law_text)
                make()
                d = self.refused(lid, reason)
                self.assertTrue(no_kernel_ran(d), d)

    def test_list_names_the_unknown_laws(self):
        """I41-R3: --list gives the eligible laws: in T41 the target alone."""
        self.fresh()
        p, out = intake(self.repo, "--list", "--milestone", T)
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])
        self.assertEqual(out, {"eligible": {T: [TARGET]}})


# ------------------------------------------------------------------ the fixture through holon run and the gate
class TestFixtureRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.I = holon_module("holon.intake")   # red until I41 exists
        cls.repo = copy_repo()
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i41-run-"))
        repo, inbox = cls.repo, cls.repo / "proofs" / "inbox"
        cls.base = setup_fixture(repo)
        cls.gen0 = files(repo, f"gen/{T}")
        cls.valid = (FX / "proofs" / "valid" / "PROOF.bend").read_text()
        cls.wrong = variants(cls.valid)["wrong"]
        h = cls.base[TARGET]["statement_hash"]
        # 1. a submission the intake refuses (the wrong strengthening), decided inside holon run
        submit(inbox, TARGET, cls.wrong, h)
        run_t41(repo)
        cls.recs_refused, cls.gen_refused = records(repo), files(repo, f"gen/{T}")
        # 2. the valid submission
        shutil.rmtree(inbox)
        submit(inbox, TARGET, cls.valid, h)
        run_t41(repo)
        cls.recs, cls.gen = records(repo), files(repo, f"gen/{T}")
        cls.summary = load_json(repo / "results" / T / "summary.json")
        # 3. the gate re-decides it from scratch: G1 regenerates T41 from the committed inbox, the rest re-check it
        cls.gate, cls.gate_log = gate_t41(repo, cls.tmp / "gate.json", "G1,G3,G5,G7,G9,G11,G11V")
        # 4. once more, for determinism
        run_t41(repo)
        cls.recs2, cls.gen2 = records(repo), files(repo, f"gen/{T}")
        # 5. the inbox file replaced by the wrong proof, the records and gen/T41 left as the accepted run wrote them:
        #    G1 must now fail on the target, because it re-decides the submission instead of trusting the record
        (inbox / TARGET / "PROOF.bend").write_text(cls.wrong)
        cls.gate_neg, cls.gate_neg_log = gate_t41(repo, cls.tmp / "gate_neg.json", "G1")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_a_refused_submission_changes_only_the_targets_attempts(self):
        """I41-P9 (§10.4: only a proof the kernel accepts matters): with the wrong proof in the inbox, holon run leaves
        the target UNKNOWN with prover generator, adds one intake attempt (refused, kernel_rejected) after the
        generators' attempts, and changes no other field, no other record and no file under gen/T41."""
        r, b = strip_seconds(self.recs_refused[TARGET]), strip_seconds(self.base[TARGET])
        self.assertEqual((r["status"], r["prover"]), ("UNKNOWN", "generator"))
        self.assertEqual(r["attempts"][:-1], b["attempts"])
        last = r["attempts"][-1]
        self.assertEqual({k: last.get(k) for k in ("kind", "verdict", "reason", "prover", "submission",
                                                   "proof_sha256")},
                         {"kind": "intake", "verdict": "refused", "reason": "kernel_rejected", "prover": SESSION,
                          "submission": f"proofs/inbox/{TARGET}", "proof_sha256": sha256(self.wrong.encode())})
        self.assertEqual({k: v for k, v in r.items() if k != "attempts"}, {k: v for k, v in b.items() if k != "attempts"})
        for lid in (Y, FLAG):
            with self.subTest(law=lid):
                self.assertEqual(strip_seconds(self.recs_refused[lid]), strip_seconds(self.base[lid]))
        self.assertEqual(self.gen_refused, self.gen0)

    def test_the_accepted_proof_is_labelled_in_its_record(self):
        """I41-P2 (plan), the record: after holon run the target is PROVED, labelled agent:fixture-i41; its PROOF.bend
        is the inbox file byte for byte, its LAWS.bend the generators' statement (same statement hash); the generators'
        attempts are kept and the intake's is last; the other records and every earlier gen/T41 file are unchanged."""
        self.assertTrue(verdict_enabled(), "I41-P2 claims bendtt checked: BendTT must be available")
        r, b = self.recs[TARGET], self.base[TARGET]
        self.assertEqual((r["status"], r["prover"]), ("PROVED", SESSION))
        # exactly the fields in which a generator's PROVED record differs from an UNKNOWN one (compare L_i41_y), and prover
        changed = sorted(k for k in set(r) | set(b)
                         if canonical(strip_seconds(r.get(k))) != canonical(strip_seconds(b.get(k))))
        self.assertEqual(changed, ["artifacts", "attempts", "bound", "checker", "independence_class", "kernel", "kernels",
                                   "non_vacuity", "prover", "status"])
        self.assertIsNone(r["bound"])
        self.assertEqual(r["kernel"]["verdict"], "checked")
        nv = r["non_vacuity"]
        self.assertEqual((nv.get("status"), nv.get("law"), nv.get("reachable"), nv.get("parent_statement_hash")),
                         ("inhabited", f"gen/{T}/{TARGET}/nonvac/LAWS.bend", True, b["statement_hash"]))
        self.assertEqual(r["statement_hash"], b["statement_hash"])
        proof_rel, laws_rel = f"gen/{T}/proofs/{TARGET}/PROOF.bend", f"gen/{T}/laws/{TARGET}/LAWS.bend"
        self.assertEqual(r["artifacts"]["proof"], proof_rel)
        self.assertEqual(r["artifacts"]["laws"], laws_rel)
        self.assertEqual(r["artifacts"]["law_name"], "l_i41_x_any_act")
        self.assertEqual(self.gen.get(proof_rel), self.valid.encode())
        law_text = self.gen.get(laws_rel, b"").decode()
        self.assertIn(TARGET_LAW, law_text)
        self.assertIn(b["statement_hash"], law_text)
        self.assertEqual(len(re.findall(r"(?m)^law\s", law_text)), 1, law_text)
        self.assertEqual((r["checker"].get("exit_code"), r["checker"].get("marker")), (0, "ALL PROOFS CHECK"))
        ks = {k["name"]: k["result"] for k in r["kernels"]}
        self.assertEqual(ks, {"bend2": "checked", "bendtt": "checked"})
        self.assertEqual(r["independence_class"], "I1-shared")
        self.assertEqual((r["scope"], r["scope_v2"]["kind"]), ("unbounded", "unbounded"))
        self.assertEqual(strip_seconds(r["attempts"][:-1]), strip_seconds(b["attempts"]))
        last = r["attempts"][-1]
        self.assertEqual({k: last.get(k) for k in ("kind", "verdict", "reason", "prover", "submission",
                                                   "proof_sha256", "kernels")},
                         {"kind": "intake", "verdict": "accepted", "reason": None, "prover": SESSION,
                          "submission": f"proofs/inbox/{TARGET}", "proof_sha256": sha256(self.valid.encode()),
                          "kernels": expected_kernels("checked")})
        for lid in (Y, FLAG):
            with self.subTest(law=lid):
                self.assertEqual(strip_seconds(self.recs[lid]), strip_seconds(self.base[lid]))
                self.assertEqual(self.recs[lid]["prover"], "generator")
        self.assertEqual(self.summary, {FLAG: "REFUTED", TARGET: "PROVED", Y: "PROVED"})
        for rel, data in self.gen0.items():
            with self.subTest(file=rel):
                self.assertEqual(self.gen.get(rel), data)
        new = sorted(set(self.gen) - set(self.gen0))
        self.assertEqual(new, sorted([proof_rel, laws_rel, f"gen/{T}/{TARGET}/nonvac/LAWS.bend",
                                      f"gen/{T}/{TARGET}/nonvac/PROOF.bend"]))

    def test_the_gate_rechecks_the_agent_proof(self):
        """I41-P3: on the accepted tree G1, G3, G5, G7, G9, G11 and G11V pass (at baseline they pass with 2 proofs, 3
        records and 1 premised PROVED law inhabited). G1 regenerates the agent-proved record from the committed inbox
        and finds the 3 records identical; G5 and G7 re-check 3 proofs from scratch (the 2 generator proofs and the
        agent's); G9 validates the 3 records, prover included; G11V inhabits 2 premised PROVED laws (L_i41_y and the
        target)."""
        self.assertTrue(verdict_enabled(), "I41-P3 claims G7 re-checks with BendTT: BendTT must be available")
        checks = self.gate.get("checks") or {}
        for g in ("G1", "G3", "G5", "G7", "G9", "G11", "G11V"):
            with self.subTest(check=g):
                self.assertTrue((checks.get(g) or {}).get("passed"), f"{checks.get(g)} | {self.gate_log}")
        self.assertRegex(checks["G1"]["detail"], r"(?<!\d)3 records identical")
        self.assertRegex(checks["G5"]["detail"], r"(?<!\d)3 proofs re-checked from scratch")
        self.assertRegex(checks["G7"]["detail"], r"dual-kernel: 3 proofs")
        self.assertRegex(checks["G9"]["detail"], r"(?<!\d)3 records valid")
        self.assertRegex(checks["G11V"]["detail"], r"(?<!\d)2 premised PROVED laws inhabited")

    def test_g1_redecides_the_committed_inbox(self):
        """I41-P3 (negative control): with the inbox file replaced by the wrong proof, and the accepted records and
        gen/T41 left in place, G1 fails and names the target among the records that differ. The gate re-decides the
        submission from the inbox; it never trusts the committed record."""
        g1 = (self.gate_neg.get("checks") or {}).get("G1") or {}
        self.assertIs(g1.get("passed"), False, f"{g1} | {self.gate_neg_log}")
        self.assertRegex(g1.get("detail", ""), r"records differ: \[[^\]]*'" + TARGET + "'", self.gate_neg_log)

    def test_rerun_is_byte_identical(self):
        """I41-R3 (AGENTS rule 7): a second holon run over the same inbox writes the same records (seconds aside) and
        the same gen/T41 files."""
        self.assertEqual(canonical(strip_seconds(self.recs2)), canonical(strip_seconds(self.recs)))
        self.assertEqual(self.gen2, self.gen)


# ------------------------------------------------------------------ the real M2 laws (read-only, --inbox outside the tree)
class TestRealM2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.I = holon_module("holon.intake")   # red until I41 exists
        cls.recs = records(ROOT, "M2")
        cls.unknown = sorted(k for k, r in cls.recs.items() if r["status"] == "UNKNOWN")
        cls.decided = sorted(k for k, r in cls.recs.items() if r["status"] in ("PROVED", "REFUTED")
                             and not str(r.get("prover", "")).startswith("agent:"))
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i41-m2-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def decide(self, subs: dict[str, tuple[str, str]]) -> tuple[subprocess.CompletedProcess, dict | None]:
        """Decide {law_id: (proof, statement_hash)} from a fresh inbox outside the tree; the tree must not change."""
        inbox = self.tmp / f"inbox{len(list(self.tmp.iterdir()))}"
        for lid, (proof, h) in subs.items():
            submit(inbox, lid, proof, h)
        before = m2_outputs()
        p, out = intake(ROOT, "--milestone", "M2", "--inbox", str(inbox), cwd=ROOT)
        self.assertEqual(m2_outputs(), before, "holon intake changed a file of the tree")
        return p, out

    def test_proofs_for_decided_m2_laws_are_refused(self):
        """I41-P4, real half: every M2 law the generators decided (at f8fa447: 8, 6 PROVED and 2 REFUTED, among them
        L_sort_site_rollup_441_b4cd5068 and L_sort_site_rollup_363_1fc7f88a), resubmitted with its own committed
        proof, is refused not_unknown before any kernel."""
        st = {self.recs[k]["status"] for k in self.decided}
        self.assertEqual(st, {"PROVED", "REFUTED"}, self.decided)
        subs = {k: ((ROOT / self.recs[k]["artifacts"]["proof"]).read_text(), self.recs[k]["statement_hash"])
                for k in self.decided}
        p, out = self.decide(subs)
        self.assertEqual(p.returncode, 1, (p.stdout + p.stderr)[-2000:])
        for k in self.decided:
            with self.subTest(law=k):
                d = decision(self, p, out, k)
                self.assertEqual((d["verdict"], d["reason"], d["milestone"]), ("refused", "not_unknown", "M2"), d)
                self.assertTrue(no_kernel_ran(d), d)

    def test_a_hole_in_a_proof_for_a_real_unknown_law_is_refused(self):
        """I41-P5, real half: for every UNKNOWN M2 law (at f8fa447 the two of BASE_UNKNOWN_M2) a proof whose body is
        ?TODO is refused escape_hatch: the law is eligible, and the textual G3 scan refuses before any kernel."""
        self.assertTrue(self.unknown, "no UNKNOWN M2 record")
        subs = {k: (real_wrong_proof(k, "?TODO"), self.recs[k]["statement_hash"]) for k in self.unknown}
        p, out = self.decide(subs)
        for k in self.unknown:
            with self.subTest(law=k):
                d = decision(self, p, out, k)
                self.assertEqual((d["verdict"], d["reason"], d["hatches"]), ("refused", "escape_hatch", ["hole"]), d)
                self.assertTrue(no_kernel_ran(d), d)

    def test_a_wrong_proof_for_a_real_unknown_law_reaches_the_kernel(self):
        """I41-P8: for every UNKNOWN M2 law, a proof filled with {==} passes every check before the kernels (eligible,
        statement hash, G3, its own law imported, G1 over gen/M2: the regenerated model, core and law files equal the
        committed ones) and bend2 rejects it: kernel_rejected. The tree does not change."""
        self.assertTrue(self.unknown, "no UNKNOWN M2 record")
        subs = {k: (real_wrong_proof(k), self.recs[k]["statement_hash"]) for k in self.unknown}
        p, out = self.decide(subs)
        self.assertEqual(p.returncode, 1, (p.stdout + p.stderr)[-2000:])
        for k in self.unknown:
            with self.subTest(law=k):
                d = decision(self, p, out, k)
                self.assertEqual((d["verdict"], d["reason"]), ("refused", "kernel_rejected"), d)
                self.assertEqual((d["hatches"], d["differs"]), ([], []), d)
                self.assertEqual(d["kernels"]["bend2"], "failed", d)

    def test_a_stale_statement_hash_is_refused(self):
        """I41-R3: a submission for a real UNKNOWN law that names another statement hash is refused statement_mismatch."""
        self.assertTrue(self.unknown, "no UNKNOWN M2 record")
        p, out = self.decide({k: (real_wrong_proof(k), ZERO_HASH) for k in self.unknown})
        for k in self.unknown:
            with self.subTest(law=k):
                d = decision(self, p, out, k)
                self.assertEqual((d["verdict"], d["reason"]), ("refused", "statement_mismatch"), d)
                self.assertTrue(no_kernel_ran(d), d)

    def test_list_names_exactly_the_unknown_m2_records(self):
        """I41-R3: --list over the committed tree: M0 and M1 have no eligible law, and M2's eligible laws are its UNKNOWN
        records (with any agent-proved one); at f8fa447 exactly BASE_UNKNOWN_M2."""
        p = run_holon(["intake", "--root", str(ROOT), "--list", "--json"])
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])
        el = json.loads(p.stdout)["eligible"]
        agent = sorted(k for k, r in self.recs.items() if str(r.get("prover", "")).startswith("agent:"))
        self.assertEqual((el.get("M0"), el.get("M1")), ([], []))
        self.assertEqual(el.get("M2"), sorted(self.unknown + agent))
        for k in BASE_UNKNOWN_M2:
            if self.recs.get(k, {}).get("status") == "UNKNOWN":
                self.assertIn(k, el["M2"])


# ------------------------------------------------------------------ records: prover on every record
class TestProverField(unittest.TestCase):
    def test_every_record_carries_a_prover(self):
        """I41-R1: every committed record under results/M*/ names its prover; agent:<session> only on a PROVED record whose
        proof is the inbox file byte for byte."""
        recs = sorted(ROOT.glob("results/M[0-9]*/L*.json"))
        self.assertGreaterEqual(len(recs), 34)
        for f in recs:
            r = load_json(f)
            with self.subTest(record=f.relative_to(ROOT).as_posix()):
                self.assertRegex(str(r.get("prover")), PROVER_PATTERN)
                if r["prover"].startswith("agent:"):
                    self.assertEqual(r["status"], "PROVED")
                    self.assertEqual((ROOT / r["artifacts"]["proof"]).read_bytes(),
                                     (ROOT / "proofs" / "inbox" / r["law_id"] / "PROOF.bend").read_bytes())

    def test_the_prover_commit_adds_only_the_prover_field(self):
        """I41-R1: in the first commit (oldest first) whose records carry "prover", every record under results/M0, M1
        and M2 gains "prover": "generator" and nothing else, except generator_sha256 in M1 and M2 (seconds ignored);
        the set of records and summary.json and deps.json are unchanged; and that commit descends from the commit that
        introduced key I41 into spec/M3/predictions.json. Its first parent must have been regenerated by its own
        generators (G1 holds there), as every merged base is."""
        paths = ("results/M0", "results/M1", "results/M2")
        revs = git("log", "--topo-order", "--reverse", "--format=%H", "-S", '"prover":', "HEAD", "--", *paths).split()
        self.assertTrue(revs, 'no commit introduces "prover" into the records under results/M0..M2 (I41 has not landed)')
        c = revs[0]
        parent = git("rev-parse", f"{c}^1").strip()
        pre = git("log", "--topo-order", "--reverse", "--format=%H", "-S", '"I41":', "HEAD", "--",
                  "spec/M3/predictions.json").split()
        self.assertTrue(pre, "no commit introduces key I41 into spec/M3/predictions.json")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        anc = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", pre[0], c], env=env)
        self.assertEqual(anc.returncode, 0, f"the prover commit {c[:12]} does not descend from the I41 prereg "
                                            f"commit {pre[0][:12]}")
        rx = re.compile(r"^results/M[012]/L[^/]*\.json$")

        def at(rev: str) -> dict[str, dict]:
            names = [n for n in git("ls-tree", "-r", "--name-only", rev, "--", *paths).splitlines() if rx.match(n)]
            return {n: json.loads(git("show", f"{rev}:{n}")) for n in names}
        old, new = at(parent), at(c)
        self.assertEqual(sorted(new), sorted(old))
        self.assertGreaterEqual(len(new), 34)
        for n in sorted(new):
            with self.subTest(record=n):
                a, b = strip_seconds(old[n]), strip_seconds(new[n])
                self.assertNotIn("prover", a)
                self.assertEqual(b.pop("prover", None), "generator")
                if not n.startswith("results/M0/"):
                    a.pop("generator_sha256", None)
                    b.pop("generator_sha256", None)
                self.assertEqual(canonical(b), canonical(a))
        for m in ("M0", "M1", "M2"):
            for f in ("summary.json", "deps.json"):
                with self.subTest(file=f"results/{m}/{f}"):
                    self.assertEqual(git("show", f"{c}:results/{m}/{f}"), git("show", f"{parent}:results/{m}/{f}"))


if __name__ == "__main__":
    unittest.main()
