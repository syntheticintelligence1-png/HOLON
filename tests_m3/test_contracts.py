"""I64 (= I33a): intent contracts and G10 (whitepaper §5.9, §5.8's volatile-view exception, §9.3 G10; BUILD_PLAN §2
invariant 10 and §4 I33; docs/HUMAN_ANSWERS.md Q4). This docstring is the contract.

Scope. I64 is the machinery half of BUILD_PLAN I33, pulled forward under its own key as I59 was for I23 and I63 for
I28. It builds intent contracts, G10, the v2 filter value intended_bounded, the volatile-view contract type OWN needs
(I35), and the Q4 adoption package, and exercises them on the test milestone T64, a toy with O12's shape: a challenge
extends the pending batch's finalize deadline by W, and cancelling it leaves the extension. I33 keeps its number for
the O12 contract on the real model: it needs a ghost counter in the M3 model and a proof class for linear bounds over
Reach that no generator has yet, and the UNDO analogue of L_undo_cancel that I27 could not derive (gap G5). I64
registers no contract on M0-M3 and changes no M0-M3 law or record.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i64.py (K1-K3, K5, K6 and K9, independently of holon/) and the fixture
tests_m3/fixtures/contracts/ (toy_intent.facts.json, laws/L_t64_*.json, contracts/{C_t64_ext, C_t64_zero, V_t64_view,
V_t64_bad}.json).

K1 Contract files. laws/CONTRACTS/<id>.json, a JSON object with exactly these fields: contract_version
   "holon-contract/0.1"; id (the file name; "C_..." for kind "intended", "V_..." for kind "volatile_view"); kind;
   milestone (M<n> or T<n>, never M0 or M1); rule (an IR rule); facts (a relative repository path, without ".."; a
   file); maps_to and rationale (non-empty text); evidence (non-empty, E1-E6). An intended contract also has scope
   {"laws": [law ids], non-empty} and l_weak (an IR 0.3 statement over its facts: the law K3 derives from it validates
   against spec/schemas/law_ir_0_3.schema.json). A volatile-view contract also has view {facts (a Go facts document,
   a relative repository path), function, result (an integer, never a boolean)}. Anything else, a file that is not a
   JSON object included, makes the file invalid (tests_m3/_i64.problems).
K2 Registry. laws/CONTRACTS/REGISTRY.json: {"registry_version": "holon-contracts-registry/0.1", "contracts": {id:
   {"milestone", "kind", "sha256"}}}: each entry's milestone and kind are its contract's, and sha256 is over the
   contract's canonical JSON (UTF-8; sorted keys; separators (",", ":"); ensure_ascii False). A contract is pinned by
   its registry hash, not frozen: laws/CONTRACTS/ is self-certified until the human adds it to FROZEN_ROOTS (Q1).
   Changing a contract changes its hash, which G10 reports until the registry is updated.
K3 Derivation. `python -m holon contracts derive --milestone M` writes, for every valid intended contract of M,
   laws/M/L_contract_<id>.json: {ir_version "holon-ir/0.3", law_id "L_contract_<id>", milestone M, rule, subform
   "intended_weak", rule_catalog_version "holon-rules/0.1", facts, facts_sha256 (the facts file's sha256 now),
   statement (the contract's l_weak), maps_to, evidence, notes "L_weak of intent contract <id>
   (laws/CONTRACTS/<id>.json), derived by holon contracts"} (tests_m3/_i64.derived_law), canonical JSON as other law
   files. It writes nothing else, and removes laws/M/L_contract_*.json whose contract is gone. If any contract
   file is invalid (K1, K9), whatever its milestone, it exits 2 and writes nothing.
K4 Decision. `holon run --milestone M` decides L_contract_<id> like every other law of M (the existing generators and
   refuters; nothing special-cases it).
K5 Application. The last step of every `holon run` that exits 0, whichever runner decides the milestone (typed or not),
   over every record of the milestone (with --laws too), in the results directory the run wrote (--out when given);
   and `holon contracts apply --milestone M`, which re-applies without deciding. The step lives in holon/contracts.py
   and is called from holon/__main__.py once the run's dispatch returns 0. No module of a generator closure imports
   it, and I64 changes no file of one: the holon-ir/0.1-0.3 closures (holon.records.generator_files) and the typed
   runners' (from holon.sorts.run3.GEN3, holon.undo.run.GEN_UNDO and holon.disch.run.GEN_DISCH). So every M0-M3 record
   keeps its generator_sha256. An intended contract is proved when
   its derived law is its l_weak over the facts file as it is now, and the law's record is PROVED over that file and
   carries that law's statement_hash (tests_m3/_i64.states, which leaves the statement_hash check to holon: it does not
   recompute the hash). Every REFUTED record of a law in the scope of a proved contract is marked: filter_bin
   "intended_bounded", and "intended": {"contract": id, "l_weak": "L_contract_<id>", "replaces": the filter_bin the
   record has unmarked}, naming the least id when several proved contracts hold the law (tests_m3/_i64.expected_marks).
   A marked record differs from its unmarked self in these two fields only, and every other record is as the run gives
   it without contracts (but for wall-clock fields, the keys named "seconds"); the step rewrites only a record whose
   content changes. apply first unmarks every record (filter_bin from replaces, intended dropped), then marks. A
   contract whose L_weak is not proved marks nothing. The step writes results/M/contracts.json: {"contracts_version":
   "holon-contracts/0.1", "milestone", "contracts": [{"id", "kind", "state", "scope", "marked"}] by id}, where scope is
   the sorted law ids of the contract's scope ([] for a view) and marked lists, under every proved intended contract,
   each REFUTED law of its scope, so that a law in several scopes is listed under each while its record names the
   least id ([] for every other contract; tests_m3/_i64.contracts_doc). The states are exactly: "proved"; "valid";
   "invalid: " + the problems joined by "; "; "not derived or not decided"; "stale: the derived law is not the
   contract's L_weak over the current facts"; "stale: decided over other facts"; "not proved: <status>"; and holon's
   own "stale: decided for another statement (the record's statement_hash is not the derived law's)", which the
   instrument cannot tell from "proved". With no contract of M it marks nothing and leaves no results/M/contracts.json.
   On M0 and M1 it does nothing.
K6 G10. On M0 and M1: listed under the report's not_applicable (no contracts before M2: BUILD_PLAN §2 invariant 10 and
   §4 I33; Q15 is still open). On every other milestone G10 passes iff (tests_m3/_i64.g10): REGISTRY.json, when it
   exists, is a holon-contracts-registry/0.1 document whose every entry is {milestone, kind, sha256} of strings;
   every contract file and registry entry belongs to a milestone G10 applies to (a file that is not a JSON object, or
   a file or entry whose milestone is missing, malformed, M0 or M1, fails G10 on every milestone where it applies);
   every contract of the milestone is registered with its current sha256, milestone and kind; no registry entry for
   the milestone lacks its contract file; every intended contract is proved and every volatile view valid; every
   record of the milestone is a JSON object; and the marks the records carry (filter_bin intended_bounded,
   intended.contract, intended.l_weak) are exactly those K5 requires. With no contract it passes and says so. On
   failure it names each contract (by id), file (by its file name, <name>.json), registry entry or law, and the
   reason (invalid, not in the registry, not derived or decided, stale, not proved: <status>, a mark). G10 is in the
   default checks: holon.gate.CHECK_ORDER, and holon.sorts.gate3.CHECK_ORDER, the typed gate's default order.
K7 Change. A change to a contract's facts file makes it stale: G10 fails until `holon contracts derive` and `holon run`
   decide it again over the new facts, and then passes iff its L_weak is still proved. A changed contract fails G10
   until the registry is updated (K2).
K8 Records. spec/schemas/result_record_v2.schema.json admits filter_bin "intended_bounded" and the field "intended"
   {contract, l_weak, replaces}, all three required, on REFUTED records only, and "intended" exactly when filter_bin is
   intended_bounded. The frozen v1 schemas/ and its triage enum are untouched (Q4).
K9 Volatile views. A volatile-view contract is valid iff K1 holds and its view's facts document lists the function
   with that result index among go.slices.results. It is not proved; OWN (I35) reads the valid ones as the exception
   whitepaper §5.8 allows. results/M/contracts.json lists it with state "valid" or why not.
K10 Q4 adoption package. docs/adoption/Q4/README.md gives the human's exact steps to adopt result_record_v2 and
   law_ir_0_3 into the frozen schemas/ (Q4; AGENTS.md rule 1: the agent never runs tools/freeze.py write): the copy,
   `tools/freeze.py write`, which records them in FROZEN.sha256, and the move of the CI digest pin in holon-ci.yml
   (Q40); and, should the human want contracts frozen too, laws/CONTRACTS added to FROZEN_ROOTS first (K2).
   docs/adoption/Q4/schemas/ holds the two files byte-equal to spec/schemas/ at the build's head.

Commands
  python -m holon contracts derive --milestone M [--check]   K3 (--check: the derived laws equal the committed ones)
  python -m holon contracts apply --milestone M [--check]    K5 without deciding (--check: records and contracts.json
                                                            equal the committed ones)
  python -m holon gate --milestone M --checks G10            K6
  Exit codes: 0 done (or --check reproduced); 1 --check differs; 2 refused, nothing written: derive, when a contract
  file is invalid; apply, when results/M is not a directory, a record is not JSON, or a record holds half a mark
  (filter_bin intended_bounded without intended.replaces, or intended without that bin).

Rules for every session (AGENTS.md): I64 adds no contract to M0-M3, changes no M0-M3 law or record (generator_sha256
included: K5), and never writes under schemas/ or another frozen root. I64's outcome paths are laws/CONTRACTS/,
docs/adoption/Q4/ and docs/iterations/I64.md; its code (holon/contracts.py, the gates' G10, the run's last step) and
the v2 schema change are build commits.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import (ROOT, copy_repo, file_sha256, holon_module, item, load_json, predictions, run_bend, run_holon,
                          validate)

FX = ROOT / "tests_m3" / "fixtures" / "contracts"
FX_REL = "tests_m3/fixtures/contracts"
FACTS = f"{FX_REL}/toy_intent.facts.json"
T = "T64"
V2 = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
ADOPT = ROOT / "docs" / "adoption" / "Q4"
# the generators and the refuter that existed at the prereg (holon/gen/mproofs.py GENERATORS, holon/mpipeline.py)
GENERATORS_AT_PREREG = ("evaluate", "nat_split", "noninterference", "deadline", "chain_revert", "act_split", "hyp",
                        "expr_open", "coercion_guard", "param_premise", "reach_invariant")
REFUTERS_AT_PREREG = ("counter",)
_RUNS: dict = {}


def instrument():
    import tests_m3._i64 as I
    return I


def records(repo, m=T) -> dict:
    return {p.stem: load_json(p) for p in sorted((repo / "results" / m).glob("L*.json"))}


def untimed(x):
    """A record without its wall-clock fields (every key named "seconds"), which differ between runs."""
    if isinstance(x, dict):
        return {k: untimed(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [untimed(v) for v in x]
    return x


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def holon_ok(args, repo, what):
    p = run_holon(args, cwd=repo, timeout=3600)
    if p.returncode != 0:
        raise AssertionError(f"holon {' '.join(args)} ({what}) failed: {(p.stdout + p.stderr)[-3000:]}")
    return p


def put_contracts(repo, ids) -> None:
    """laws/CONTRACTS/ in a copy: the fixture contracts named, and a registry of exactly them (K2)."""
    I = instrument()
    d = repo / "laws" / "CONTRACTS"
    d.mkdir(parents=True, exist_ok=True)
    reg = {}
    for cid in ids:
        c = load_json(FX / "contracts" / f"{cid}.json")
        write_json(d / f"{cid}.json", c)
        reg[cid] = {"milestone": c["milestone"], "kind": c["kind"], "sha256": I.content_sha256(c)}
    write_json(d / "REGISTRY.json", {"registry_version": "holon-contracts-registry/0.1",
                                      "contracts": dict(sorted(reg.items()))})


def register(repo, c: dict) -> None:
    """Add (or replace) one contract in a copy's laws/CONTRACTS/ and its registry entry."""
    I = instrument()
    d = repo / "laws" / "CONTRACTS"
    write_json(d / f"{c['id']}.json", c)
    reg = load_json(d / "REGISTRY.json")
    reg["contracts"][c["id"]] = {"milestone": c["milestone"], "kind": c["kind"], "sha256": I.content_sha256(c)}
    reg["contracts"] = dict(sorted(reg["contracts"].items()))
    write_json(d / "REGISTRY.json", reg)


def put_laws(repo) -> str:
    """laws/T64: the fixture laws with facts_sha256 filled, and a REGISTRY.json listing every law file there."""
    sha = file_sha256(repo / FACTS)
    d = repo / "laws" / T
    for p in sorted((FX / "laws").glob("L_*.json")):
        law = load_json(p)
        law["facts_sha256"] = sha
        write_json(d / p.name, law)
    ids = sorted(p.stem for p in d.glob("L_*.json"))
    write_json(d / "REGISTRY.json", {"milestone": T, "facts": FACTS, "facts_sha256": sha, "facts_files": {FACTS: sha},
                                     "statements": {i: None for i in ids}})
    return sha


def run_t64(repo, contracts=("C_t64_ext", "V_t64_view")) -> dict:
    """laws/T64 (the fixture laws, facts_sha256 filled), the contracts, holon contracts derive, the laws' REGISTRY.json,
    holon run --milestone T64 --no-registry, holon metrics; the registry's statement hashes are then filled from the
    records, so that G1 can regenerate T64. Returns the records."""
    put_laws(repo)
    put_contracts(repo, contracts)
    holon_ok(["contracts", "derive", "--milestone", T], repo, "derive")
    put_laws(repo)   # the registry again, now with the derived laws
    holon_ok(["run", "--milestone", T, "--no-registry"], repo, "run")
    holon_ok(["metrics", "--milestone", T], repo, "metrics")
    recs = records(repo)
    d = repo / "laws" / T
    reg = load_json(d / "REGISTRY.json")
    reg["statements"] = {i: recs[i]["statement_hash"] for i in reg["statements"] if i in recs}
    write_json(d / "REGISTRY.json", reg)
    return recs


def baseline():
    """One copy of the repository with T64 run under C_t64_ext and V_t64_view, cached for the module and removed by
    tearDownModule. A run that fails is removed at once, and its error is raised again for every later caller."""
    if "error" in _RUNS:
        raise AssertionError(f"the baseline run failed earlier: {_RUNS['error']}")
    if "base" not in _RUNS:
        repo = copy_repo()
        try:
            _RUNS["base"] = (repo, run_t64(repo))
        except BaseException as e:
            shutil.rmtree(repo.parent, ignore_errors=True)
            _RUNS["error"] = f"{type(e).__name__}: {e}"[:3000]
            raise
    return _RUNS["base"]


def tearDownModule():
    if "base" in _RUNS:
        shutil.rmtree(_RUNS.pop("base")[0].parent, ignore_errors=True)


def copy_of_baseline() -> Path:
    base, _ = baseline()
    dst = Path(tempfile.mkdtemp(prefix="i64-copy-")) / "repo"
    shutil.copytree(base, dst, symlinks=True)
    return dst


def gate(repo, m, checks="G10"):
    """holon gate --milestone m --checks <checks>, its report written outside the tree under check."""
    out = Path(tempfile.mkdtemp(prefix="i64-gate-")) / f"gate_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--checks", checks, "--report", str(out)], cwd=repo, timeout=3600)
    rep = load_json(out) if out.is_file() else {}
    shutil.rmtree(out.parent, ignore_errors=True)
    return p, rep


def g10_line(rep) -> dict:
    """G10's line of a gate report: {"status": "PASS" | "FAIL", "detail"}, or {} when absent."""
    c = (rep.get("checks") or {}).get("G10")
    return {"status": "PASS" if c["passed"] else "FAIL", "detail": c.get("detail", "")} if c else {}


def g10_both(test, repo, want: str) -> tuple:
    """G10 on T64 from the gate and from the instrument, both required to be want ("PASS" or "FAIL"). Returns (the
    gate's line, the instrument's reasons)."""
    _, rep = gate(repo, T)
    line = g10_line(rep)
    ok, reasons = instrument().g10(T, repo)
    test.assertEqual(line.get("status"), want, rep)
    test.assertEqual("PASS" if ok else "FAIL", want, reasons)
    return line, reasons


def rechecked(test, repo, lid: str, rec: dict) -> None:
    """AGENTS rule 6, independently of the record: the record's PROOF.bend (a proof when PROVED, a counter-law when
    REFUTED) is accepted by Bend run here, its LAWS.bend states exactly the law the status needs (l_<id> when PROVED,
    cl_l_<id> when REFUTED, ids lower-cased), and the attempt that decided it came from a generator or the refuter that
    existed at the prereg."""
    status = rec.get("status")
    test.assertIn(status, ("PROVED", "REFUTED"), lid)
    art = rec.get("artifacts") or {}
    proof, laws = (Path(art.get(k) or "") for k in ("proof", "laws"))
    proof, laws = (p if p.is_absolute() else repo / p for p in (proof, laws))
    test.assertTrue(proof.is_file() and laws.is_file(), (lid, art))
    code, out = run_bend([proof.name], cwd=proof.parent)
    test.assertEqual(code, 0, (lid, out[-1500:]))
    test.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), (lid, out[-1500:]))
    name = ("cl_" if status == "REFUTED" else "") + lid.lower()
    test.assertEqual(re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws.read_text(), re.M), [name], lid)
    # the proof imports exactly that law file, as Laws, and states no law of its own (a proof file that imports no law
    # checks vacuously in the separated layout: holon.mpipeline.law_import_problem, BEND_PRIMER §3.1)
    text = proof.read_text()
    want = Path(os.path.relpath(laws.resolve(), proof.resolve().parent)).as_posix()
    test.assertEqual(re.findall(r"^import\s+(\S+)\s+as\s+Laws\s*(?:#.*)?$", text, re.M), [want], lid)
    code_only = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    test.assertEqual(re.findall(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:", code_only), [], lid)
    kind, allowed = ("proof", GENERATORS_AT_PREREG) if status == "PROVED" else ("counter-law", REFUTERS_AT_PREREG)
    ok = [a for a in rec.get("attempts") or []
          if a.get("kind") == kind and "error" not in a and a.get("exit_code") == 0]
    test.assertTrue(ok, (lid, rec.get("attempts")))
    test.assertIn(ok[-1].get("generator"), allowed, lid)


def unmark(rec: dict) -> dict:
    out = {k: v for k, v in rec.items() if k != "intended"}
    out["filter_bin"] = rec["intended"]["replaces"]
    return out


class TestInstrument(unittest.TestCase):
    """The fixture is what it says it is."""

    def test_the_key_pins_the_instruments(self):
        """The key's thresholds pin the instrument, this contract and every fixture file by sha256."""
        th = predictions("I64")["thresholds"]
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i64.py"), th["instrument_sha256"])
        doc = sys.modules[__name__].__doc__
        self.assertEqual(__import__("hashlib").sha256(doc.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        got = {str(p.relative_to(ROOT)): file_sha256(p) for p in sorted(FX.rglob("*.json"))}
        self.assertEqual(got, th["fixture_sha256"])

    def test_the_fixture_validates(self):
        I = instrument()
        for p in sorted((FX / "laws").glob("*.json")):
            with self.subTest(law=p.name):
                self.assertEqual(validate(load_json(p), ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"), [])
        ok = {"C_t64_ext": [], "C_t64_zero": [], "V_t64_view": []}
        for cid, want in ok.items():
            with self.subTest(contract=cid):
                self.assertEqual(I.problems(load_json(FX / "contracts" / f"{cid}.json"), ROOT, cid), want)
        self.assertTrue(I.problems(load_json(FX / "contracts" / "V_t64_bad.json"), ROOT, "V_t64_bad"))
        for cid in ("C_t64_ext", "C_t64_zero"):
            with self.subTest(l_weak=cid):
                law = I.derived_law(load_json(FX / "contracts" / f"{cid}.json"), ROOT)
                self.assertEqual(validate(law, ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"), [])


class TestFormat(unittest.TestCase):
    """K1-K3, K9 on holon's side."""

    def test_derive_writes_the_l_weak_laws(self):
        """K3: holon contracts derive writes laws/T64/L_contract_<id>.json as the instrument derives it, for intended
        contracts only, and --check reproduces it."""
        repo, _ = baseline()
        I = instrument()
        c = load_json(FX / "contracts" / "C_t64_ext.json")
        self.assertEqual(load_json(repo / "laws" / T / "L_contract_C_t64_ext.json"), I.derived_law(c, repo))
        self.assertEqual(sorted(p.name for p in (repo / "laws" / T).glob("L_contract_*.json")),
                         ["L_contract_C_t64_ext.json"])
        p = run_holon(["contracts", "derive", "--milestone", T, "--check"], cwd=repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_an_invalid_contract_is_refused(self):
        """K1, K9: with laws/T64 in place, derive writes C_t64_ext's law beside the valid view V_t64_view (the positive
        control); with V_t64_bad, whose function is not in the Go document, it exits 2, names V_t64_bad and writes
        nothing."""
        repo = copy_repo()
        try:
            put_laws(repo)
            put_contracts(repo, ["C_t64_ext", "V_t64_view"])
            law = repo / "laws" / T / "L_contract_C_t64_ext.json"
            p = run_holon(["contracts", "derive", "--milestone", T], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(law.is_file())
            law.unlink()
            (repo / "laws" / "CONTRACTS" / "V_t64_view.json").unlink()
            put_contracts(repo, ["C_t64_ext", "V_t64_bad"])
            p = run_holon(["contracts", "derive", "--milestone", T], cwd=repo)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertIn("V_t64_bad", p.stdout + p.stderr)
            self.assertNotIn("invalid choice", p.stdout + p.stderr)
            self.assertFalse(law.exists())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestPredictions(unittest.TestCase):
    """I64's predictions (spec/M3/predictions.json key I64), decided on runs in copies of the repository."""

    def test_p1_the_generators_decide_the_toy(self):
        """I64-P1: on T64 the obstruction L_t64_cancel is REFUTED, the control L_t64_flag is REFUTED, and C_t64_ext's
        L_weak (L_contract_C_t64_ext) is PROVED, all by the existing generators and refuters: each record re-checked
        by Bend here, and gate checks G1, G3, G5 and G11 passing on T64."""
        item("I64", "I64-P1")
        repo, recs = baseline()
        want = {"L_t64_cancel": "REFUTED", "L_t64_flag": "REFUTED", "L_contract_C_t64_ext": "PROVED"}
        self.assertEqual({k: recs[k]["status"] for k in want}, want)
        for lid in want:
            with self.subTest(law=lid):
                rechecked(self, repo, lid, recs[lid])
        _, rep = gate(repo, T, "G1,G3,G5,G11")
        for g in ("G1", "G3", "G5", "G11"):
            with self.subTest(check=g):
                c = (rep.get("checks") or {}).get(g) or {}
                self.assertTrue(c.get("passed"), (g, c.get("detail"), rep.get("checks", {}).get("GENV")))

    def test_p2_the_proved_contract_marks_its_scope_alone(self):
        """I64-P2: against a run with no contract (which writes no results/T64/contracts.json), L_t64_cancel's record
        is marked, filter_bin intended_bounded and intended {contract C_t64_ext, l_weak L_contract_C_t64_ext, replaces:
        its filter_bin there}, and is otherwise the same; L_t64_flag's record is the same; G10 passes on T64, from the
        gate and from the instrument. Records are compared without their wall-clock fields."""
        item("I64", "I64-P2")
        repo, recs = baseline()
        bare = copy_repo()
        try:
            brecs = run_t64(bare, contracts=())
            self.assertFalse((bare / "results" / T / "contracts.json").exists())
            cancel, unmarked = untimed(recs["L_t64_cancel"]), untimed(brecs["L_t64_cancel"])
            self.assertNotEqual(unmarked.get("filter_bin"), "intended_bounded")
            self.assertNotIn("intended", unmarked)
            self.assertEqual(cancel.get("filter_bin"), "intended_bounded")
            self.assertEqual(cancel.get("intended"), {"contract": "C_t64_ext", "l_weak": "L_contract_C_t64_ext",
                                                      "replaces": unmarked.get("filter_bin")})
            self.assertEqual({k: v for k, v in cancel.items() if k not in ("filter_bin", "intended")},
                             {k: v for k, v in unmarked.items() if k != "filter_bin"})
            self.assertEqual(untimed(recs["L_t64_flag"]), untimed(brecs["L_t64_flag"]))
            g10_both(self, repo, "PASS")
        finally:
            shutil.rmtree(bare.parent, ignore_errors=True)

    def test_p3_a_false_contract_marks_nothing_and_fails_g10(self):
        """I64-P3: with C_t64_zero (L_weak: no residue) in place of C_t64_ext, L_contract_C_t64_zero is REFUTED
        (re-checked by Bend here), L_t64_cancel is not marked and carries no intended, and G10 fails naming C_t64_zero,
        from the gate and from the instrument."""
        item("I64", "I64-P3")
        repo = copy_repo()
        try:
            recs = run_t64(repo, contracts=("C_t64_zero",))
            self.assertEqual(recs["L_contract_C_t64_zero"]["status"], "REFUTED")
            rechecked(self, repo, "L_contract_C_t64_zero", recs["L_contract_C_t64_zero"])
            self.assertNotEqual(recs["L_t64_cancel"].get("filter_bin"), "intended_bounded")
            self.assertNotIn("intended", recs["L_t64_cancel"])
            line, reasons = g10_both(self, repo, "FAIL")
            self.assertIn("C_t64_zero", line.get("detail", ""))
            self.assertIn("C_t64_zero: not proved: REFUTED", reasons)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_p4_a_facts_change_needs_a_new_proof(self):
        """I64-P4: (a) a change of the facts that leaves the toy's behaviour (the doc text of action raise) makes G10
        fail as stale; after holon contracts derive and holon run, C_t64_ext's L_weak is PROVED again and G10 passes,
        with L_t64_cancel marked. (b) W changed from 3 to 4 makes G10 fail as stale; after derive and run, the L_weak
        (+3) is REFUTED, nothing is marked, and G10 fails. The L_weak's record is re-checked by Bend after each run, and
        G10 is decided by the gate and by the instrument alike."""
        item("I64", "I64-P4")
        for variant, w, after in (("doc", 3, "PASS"), ("W", 4, "FAIL")):
            with self.subTest(change=variant):
                repo = copy_repo()
                try:
                    run_t64(repo)
                    f = load_json(repo / FACTS)
                    if variant == "doc":
                        next(a for a in f["actions"] if a["name"] == "raise")["src"] = "toy: raise() (changed doc text)"
                    else:
                        f["params"]["W"] = w
                    (repo / FACTS).write_text(json.dumps(f, indent=1) + "\n")
                    line, reasons = g10_both(self, repo, "FAIL")
                    self.assertIn("stale", line.get("detail", ""))
                    self.assertTrue(any("C_t64_ext: stale" in r for r in reasons), reasons)
                    recs = run_t64(repo)
                    lw = recs["L_contract_C_t64_ext"]
                    self.assertEqual(lw["status"], "PROVED" if after == "PASS" else "REFUTED")
                    rechecked(self, repo, "L_contract_C_t64_ext", lw)
                    g10_both(self, repo, after)
                    marked = recs["L_t64_cancel"].get("filter_bin") == "intended_bounded"
                    self.assertEqual(marked, after == "PASS")
                    self.assertEqual("intended" in recs["L_t64_cancel"], after == "PASS")
                finally:
                    shutil.rmtree(repo.parent, ignore_errors=True)


class TestGate(unittest.TestCase):
    """K6: G10 as the instrument decides it; M0 and M1 not applicable; M2 and M3 with no contract."""

    def test_g10_agrees_with_the_instrument_on_t64(self):
        repo, _ = baseline()
        I = instrument()
        passed, reasons = I.g10(T, repo)
        _, rep = gate(repo, T)
        self.assertEqual(g10_line(rep).get("status"), "PASS" if passed else "FAIL", (reasons, rep))
        self.assertEqual(load_json(repo / "results" / T / "contracts.json"), I.contracts_doc(T, repo))

    def test_g10_fails_on_each_tamper(self):
        """K2, K6, K9 on a copy of the baseline: each tamper below makes G10 fail, from the gate and from the
        instrument, naming the contract, file or law; the copy is restored between tampers. It starts from the
        baseline's passing G10, so it fails with P2."""
        repo = copy_of_baseline()
        cdir, rdir = repo / "laws" / "CONTRACTS", repo / "results" / T

        def edit(p: Path, fn):
            doc = load_json(p)
            fn(doc)
            write_json(p, doc)

        ext = load_json(FX / "contracts" / "C_t64_ext.json")
        bad = load_json(FX / "contracts" / "V_t64_bad.json")
        tampers = [
            ("a contract edited after registration", "C_t64_ext",
             lambda: edit(cdir / "C_t64_ext.json", lambda c: c.update(rationale=c["rationale"] + " (edited)"))),
            ("a registry entry deleted", "C_t64_ext",
             lambda: edit(cdir / "REGISTRY.json", lambda r: r["contracts"].pop("C_t64_ext"))),
            ("a registry entry of the wrong kind", "C_t64_ext",
             lambda: edit(cdir / "REGISTRY.json", lambda r: r["contracts"]["C_t64_ext"].update(kind="volatile_view"))),
            ("an invalid view registered", "V_t64_bad", lambda: register(repo, bad)),
            ("the L_weak's record deleted", "C_t64_ext", lambda: (rdir / "L_contract_C_t64_ext.json").unlink()),
            ("the licensed mark removed", "L_t64_cancel",
             lambda: write_json(rdir / "L_t64_cancel.json", unmark(load_json(rdir / "L_t64_cancel.json")))),
            ("a mark outside every scope", "L_t64_flag",
             lambda: edit(rdir / "L_t64_flag.json", lambda r: r.update(
                 filter_bin="intended_bounded", intended={"contract": "C_t64_ext", "l_weak": "L_contract_C_t64_ext",
                                                          "replaces": r.get("filter_bin")}))),
            ("a mark naming the wrong contract", "L_t64_cancel",
             lambda: edit(rdir / "L_t64_cancel.json", lambda r: r["intended"].update(contract="C_t64_zero"))),
            ("a contract file that is not JSON", "C_t64_junk.json", lambda: (cdir / "C_t64_junk.json").write_text("{")),
            ("a contract on M1", "C_t64_m1.json",
             lambda: write_json(cdir / "C_t64_m1.json", dict(ext, id="C_t64_m1", milestone="M1"))),
            ("a registry entry with no contract file", "C_t64_gone",
             lambda: edit(cdir / "REGISTRY.json", lambda r: r["contracts"].update(
                 C_t64_gone={"milestone": T, "kind": "intended", "sha256": "0" * 64}))),
            ("a registry that is not a registry", "REGISTRY.json",
             lambda: edit(cdir / "REGISTRY.json", lambda r: r.update(registry_version="holon-contracts-registry/0.0"))),
        ]
        try:
            g10_both(self, repo, "PASS")   # the copy itself passes
            for name, token, tamper in tampers:
                with self.subTest(tamper=name):
                    saved = {p: p.read_bytes() for d in (cdir, rdir) for p in d.glob("*.json")}
                    try:
                        tamper()
                        line, reasons = g10_both(self, repo, "FAIL")
                        self.assertIn(token, line.get("detail", ""))
                        self.assertTrue(any(token in r for r in reasons), reasons)
                    finally:
                        for d in (cdir, rdir):
                            for p in d.glob("*.json"):
                                if p not in saved:
                                    p.unlink()
                        for p, b in saved.items():
                            p.write_bytes(b)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_g10_on_the_real_milestones(self):
        """M0, M1: not_applicable with a reason; M2, M3: PASS with no contract. G10 is in holon.gate.CHECK_ORDER and in
        holon.sorts.gate3.CHECK_ORDER, the default orders."""
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                _, rep = gate(ROOT, m)
                self.assertIn("G10", rep.get("not_applicable", {}), rep)
        for m in ("M2", "M3"):
            with self.subTest(milestone=m):
                _, rep = gate(ROOT, m)
                self.assertEqual(g10_line(rep).get("status"), "PASS", rep)
        self.assertIn("G10", holon_module("holon.gate").CHECK_ORDER)
        self.assertIn("G10", holon_module("holon.sorts.gate3").CHECK_ORDER)


class TestApply(unittest.TestCase):
    """K3, K5, K7 on copies of the baseline: apply and derive with their --check, removal, staleness, the least id."""

    def test_apply_and_derive_on_a_copy(self):
        """apply --check reproduces the baseline and sees a mark taken off by hand, which apply puts back; derive
        --check sees an edited derived law, which derive restores; after a facts change, apply takes the mark off
        (filter_bin back to replaces) and contracts.json says stale; with the contracts gone, derive removes the
        derived law and apply leaves no contracts.json. It starts from the baseline's mark, so it fails with P2."""
        repo = copy_of_baseline()
        cdir, rdir, ldir = repo / "laws" / "CONTRACTS", repo / "results" / T, repo / "laws" / T

        def hp(*args):
            return run_holon(list(args), cwd=repo)
        try:
            before = records(repo)
            p = hp("contracts", "apply", "--milestone", T, "--check")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            # a mark taken off by hand: --check sees it, apply puts it back
            write_json(rdir / "L_t64_cancel.json", unmark(before["L_t64_cancel"]))
            p = hp("contracts", "apply", "--milestone", T, "--check")
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            p = hp("contracts", "apply", "--milestone", T)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(records(repo), before)
            # a derived law edited: derive --check sees it, derive restores it
            law = load_json(ldir / "L_contract_C_t64_ext.json")
            write_json(ldir / "L_contract_C_t64_ext.json", dict(law, notes="edited"))
            p = hp("contracts", "derive", "--milestone", T, "--check")
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertEqual(hp("contracts", "derive", "--milestone", T).returncode, 0)
            self.assertEqual(load_json(ldir / "L_contract_C_t64_ext.json"), law)
            # the facts changed and nothing rerun: apply takes the mark off, back to the bin it replaced
            f = load_json(repo / FACTS)
            f["params"]["W"] = 4
            (repo / FACTS).write_text(json.dumps(f, indent=1) + "\n")
            p = hp("contracts", "apply", "--milestone", T)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertEqual(load_json(rdir / "L_t64_cancel.json"), unmark(before["L_t64_cancel"]))
            doc = load_json(rdir / "contracts.json")
            row = next(r for r in doc["contracts"] if r["id"] == "C_t64_ext")
            self.assertTrue(row["state"].startswith("stale"), row)
            self.assertEqual(row["marked"], [])
            self.assertEqual(doc, instrument().contracts_doc(T, repo))
            # the contracts gone: derive removes the derived law, and apply leaves no contracts.json
            for cid in ("C_t64_ext", "V_t64_view"):
                (cdir / f"{cid}.json").unlink()
            write_json(cdir / "REGISTRY.json", {"registry_version": "holon-contracts-registry/0.1", "contracts": {}})
            self.assertEqual(hp("contracts", "derive", "--milestone", T).returncode, 0)
            self.assertFalse((ldir / "L_contract_C_t64_ext.json").exists())
            self.assertEqual(hp("contracts", "apply", "--milestone", T).returncode, 0)
            self.assertFalse((rdir / "contracts.json").exists())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_apply_refuses_and_writes_nothing(self):
        """Commands: apply exits 2 and writes nothing on a record holding half a mark (filter_bin intended_bounded
        without intended), on a record that is not JSON, and when results/T64 is not a directory."""
        repo = copy_of_baseline()
        rdir = repo / "results" / T

        def files():
            return {f.name: f.read_bytes() for f in sorted(rdir.glob("*.json"))}

        def half_mark():
            flag = load_json(rdir / "L_t64_flag.json")
            write_json(rdir / "L_t64_flag.json", dict(flag, filter_bin="intended_bounded"))
        try:
            for name, tamper in (("half a mark", half_mark),
                                 ("a record that is not JSON", lambda: (rdir / "L_t64_junk.json").write_text("{"))):
                with self.subTest(case=name):
                    saved = files()
                    try:
                        tamper()
                        before = files()
                        p = run_holon(["contracts", "apply", "--milestone", T], cwd=repo)
                        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                        self.assertEqual(files(), before)
                    finally:
                        for f in rdir.glob("*.json"):
                            if f.name not in saved:
                                f.unlink()
                        for n, b in saved.items():
                            (rdir / n).write_bytes(b)
            shutil.rmtree(rdir)
            p = run_holon(["contracts", "apply", "--milestone", T], cwd=repo)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertFalse(rdir.exists())
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_the_least_id_names_the_mark(self):
        """K5: C_t64_a, C_t64_ext under a smaller id, registered, derived and decided alone (holon run --laws): the mark
        names C_t64_a, contracts.json lists L_t64_cancel under both, and G10 passes, from the gate and the instrument.
        Deciding C_t64_a's L_weak needs what P1 predicts for C_t64_ext's (the same statement): this check fails with
        P1."""
        repo = copy_of_baseline()
        try:
            register(repo, dict(load_json(FX / "contracts" / "C_t64_ext.json"), id="C_t64_a"))
            holon_ok(["contracts", "derive", "--milestone", T], repo, "derive")
            holon_ok(["run", "--milestone", T, "--no-registry", "--laws", "L_contract_C_t64_a"], repo, "run --laws")
            rec = load_json(repo / "results" / T / "L_t64_cancel.json")
            replaced = baseline()[1]["L_t64_cancel"]["intended"]["replaces"]
            self.assertEqual(rec.get("intended"), {"contract": "C_t64_a", "l_weak": "L_contract_C_t64_a",
                                                   "replaces": replaced})
            doc = load_json(repo / "results" / T / "contracts.json")
            self.assertEqual({r["id"]: r["marked"] for r in doc["contracts"] if r["kind"] == "intended"},
                             {"C_t64_a": ["L_t64_cancel"], "C_t64_ext": ["L_t64_cancel"]})
            self.assertEqual(doc, instrument().contracts_doc(T, repo))
            g10_both(self, repo, "PASS")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestSchemaAndAdoption(unittest.TestCase):
    """K8, K10."""

    def test_v2_admits_intended_bounded(self):
        """K8: a committed REFUTED record, valid under v2, stays valid once marked as K5 marks it; v2 rejects intended
        on a PROVED record, an intended lacking any of its three fields, and either half of a mark alone. The frozen
        schemas/ stay as frozen."""
        recs = [load_json(p) for p in sorted((ROOT / "results" / "M2").glob("L*.json"))]
        ref = next(r for r in recs if r.get("status") == "REFUTED" and validate(r, V2) == [])
        pro = next(r for r in recs if r.get("status") == "PROVED" and validate(r, V2) == [])
        mark = {"contract": "C_t64_ext", "l_weak": "L_contract_C_t64_ext", "replaces": ref["filter_bin"]}
        self.assertEqual(validate(dict(ref, filter_bin="intended_bounded", intended=mark), V2), [])
        self.assertNotEqual(validate(dict(pro, intended=mark), V2), [])
        self.assertNotEqual(validate(dict(pro, filter_bin="intended_bounded", intended=mark), V2), [])
        for k in mark:
            with self.subTest(missing=k):
                part = {x: v for x, v in mark.items() if x != k}
                self.assertNotEqual(validate(dict(ref, filter_bin="intended_bounded", intended=part), V2), [])
        self.assertNotEqual(validate(dict(ref, filter_bin="intended_bounded"), V2), [])
        self.assertNotEqual(validate(dict(ref, intended=mark), V2), [])
        p = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_q4_package(self):
        for name in ("result_record_v2.schema.json", "law_ir_0_3.schema.json"):
            with self.subTest(file=name):
                self.assertEqual((ADOPT / "schemas" / name).read_bytes(),
                                 (ROOT / "spec" / "schemas" / name).read_bytes())
        text = (ADOPT / "README.md").read_text()
        for word in ("tools/freeze.py write", "FROZEN.sha256", "holon-ci.yml", "schemas/", "FROZEN_ROOTS",
                     "laws/CONTRACTS"):
            self.assertIn(word, text)


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change."""

    def test_no_contract_on_the_real_milestones(self):
        """I64-R1 (part): no committed contract names M0-M3, and no M0-M3 record is marked intended_bounded or carries
        intended."""
        item("I64", "I64-R1")
        I = instrument()
        for p, c in I.contract_docs(ROOT):
            self.assertNotIn(c.get("milestone") if isinstance(c, dict) else None, ("M0", "M1", "M2", "M3"), p.name)
        for m in ("M0", "M1", "M2", "M3"):
            for p in sorted((ROOT / "results" / m).glob("L*.json")):
                r = load_json(p)
                self.assertNotEqual(r.get("filter_bin"), "intended_bounded", p)
                self.assertNotIn("intended", r, p)

    def test_i64_commits_change_no_law_record_or_generator(self):
        """I64-R2 (part): no commit of I64's own changes laws/M0-M3, results/M0-M3, gen/M0-M3, spec/M1, spec/M2,
        holon/rules/, replay/ or a frozen root, nor a file of a generator closure (K5: the holon-ir/0.1-0.3 closures
        and the typed runners', computed at HEAD) or a module that defines one; and at least one of them writes an I64
        outcome path. I64's own commits: the non-merge commits of `git log --first-parent <prereg>..<end>`, where
        prereg is the first commit to hold the key I64 in spec/M3/predictions.json and end the first commit that adds
        docs/iterations/I64.md (HEAD while none does): the build branch's own commits, not the work it merges in.
        Renames are counted at both ends. Needs the real checkout's history: a missing .git, or no outcome commit yet,
        is a failure, never a skip."""
        item("I64", "I64-R2")

        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True,
                               text=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        prereg = None
        for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
            try:
                doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
            except ValueError:
                continue
            if isinstance(doc, dict) and "I64" in (doc.get("iterations") or {}):
                prereg = c
                break
        self.assertIsNotNone(prereg, "no commit holds the key I64")
        added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                    "docs/iterations/I64.md").split()
        end = added[0] if added else "HEAD"
        # the generator closures at HEAD (holon.records.generator_files; the typed runners' closures as they hash them)
        R = holon_module("holon.records")
        run3, undo, disch = (holon_module(m) for m in ("holon.sorts.run3", "holon.undo.run", "holon.disch.run"))
        closure = {"holon/records.py", "holon/sorts/run3.py", "holon/undo/run.py", "holon/disch/run.py"}
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            closure |= set(R.generator_files(v, ROOT))
        for start in (run3.GEN3, list(undo.GEN_UNDO) + list(run3.GEN3), list(run3.GEN3) + list(disch.GEN_DISCH)):
            seen, todo = set(), list(start)
            while todo:
                r = todo.pop()
                if r in seen or not (ROOT / r).is_file():
                    continue
                seen.add(r)
                if r.endswith(".py"):
                    todo.extend(sorted(R._holon_imports(r, ROOT) - seen))
            closure |= seen
        outs = tuple(predictions("I64")["outcome_paths"])
        forbidden = ("laws/M0/", "laws/M1/", "laws/M2/", "laws/M3/", "results/M0/", "results/M1/", "results/M2/",
                     "results/M3/", "gen/M0/", "gen/M1/", "gen/M2/", "gen/M3/", "spec/M1/", "spec/M2/", "holon/rules/",
                     "replay/", "facts/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                     "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        commits, cur = [], None
        for line in git("log", "--first-parent", "--no-merges", "--no-renames", "--format=@%H", "--name-only",
                        f"{prereg}..{end}").splitlines():
            if line.startswith("@"):
                cur = (line[1:], [])
                commits.append(cur)
            elif line.strip() and cur is not None:
                cur[1].append(line.strip())
        self.assertTrue([c for c, names in commits if any(n.startswith(outs) for n in names)],
                        "no commit of I64's writes an I64 outcome path")
        for c, names in commits:
            with self.subTest(commit=c[:12]):
                self.assertEqual([n for n in names if n.startswith(forbidden) or n in closure], [])


if __name__ == "__main__":
    unittest.main()
