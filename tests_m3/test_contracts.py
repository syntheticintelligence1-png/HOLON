"""I64 (= I33a): intent contracts and G10 (whitepaper §5.9, §5.8's volatile-view exception, §9.3 G10; BUILD_PLAN I33;
docs/HUMAN_ANSWERS.md Q4 and Q15). This docstring is the contract.

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
   milestone (M<n> or T<n>, never M0 or M1: Q15); rule (an IR rule); facts (a repository path); maps_to and rationale
   (non-empty text); evidence (non-empty, E1-E6). An intended contract also has scope {"laws": [law ids], non-empty}
   and l_weak (an IR 0.3 statement over its facts). A volatile-view contract also has view {facts (a Go facts
   document), function, result}. Anything else makes the file invalid.
K2 Registry. laws/CONTRACTS/REGISTRY.json: {"registry_version": "holon-contracts-registry/0.1", "contracts": {id:
   {"milestone", "kind", "sha256"}}}, sha256 over the contract's canonical JSON (sorted keys, separators (",", ":")).
   A contract is frozen: changing it changes its hash, which G10 reports until the registry is updated.
K3 Derivation. `python -m holon contracts derive --milestone M` writes, for every valid intended contract of M,
   laws/M/L_contract_<id>.json: {ir_version "holon-ir/0.3", law_id "L_contract_<id>", milestone M, rule, subform
   "intended_weak", rule_catalog_version "holon-rules/0.1", facts, facts_sha256 (the facts file's sha256 now),
   statement (the contract's l_weak), maps_to, evidence, notes} (tests_m3/_i64.derived_law), canonical JSON as other
   law files. It writes nothing else, and removes laws/M/L_contract_*.json whose contract is gone. If any contract
   file is invalid (K1, K9), it exits 2 and writes nothing.
K4 Decision. `holon run --milestone M` decides L_contract_<id> like every other law of M (the existing generators and
   refuters; nothing special-cases it).
K5 Application. The last step of `holon run --milestone M` (and `holon contracts apply --milestone M`, which re-applies
   without deciding): an intended contract is proved when its derived law is its l_weak over the facts file as it is now
   and its record is PROVED over that file and carries that law's statement_hash (tests_m3/_i64.states, which leaves the
   statement_hash check to holon: it does not recompute the hash). Every REFUTED record of a law in the scope of a
   proved contract is marked: filter_bin "intended_bounded", and "intended": {"contract": id, "l_weak":
   "L_contract_<id>", "replaces": the filter_bin the record has unmarked}, naming the least id when several proved
   contracts hold the law (tests_m3/_i64.expected_marks). A marked record differs from its unmarked self in these two
   fields only, and every other record is as the run gives it without contracts (but for wall-clock fields, the keys
   named "seconds"). apply first unmarks every record (filter_bin from replaces, intended dropped), then marks. A
   contract whose L_weak is not proved marks nothing. The step writes results/M/contracts.json: {"contracts_version":
   "holon-contracts/0.1", "milestone", "contracts": [{"id", "kind", "state", "scope", "marked": [law ids]}] by id}
   (tests_m3/_i64.contracts_doc). With no contract of M it marks nothing and leaves no results/M/contracts.json.
K6 G10. On M0 and M1: listed under the report's not_applicable (no contracts before M2; Q15). On every other milestone
   G10 passes iff every contract of the milestone is in the registry with its current sha256, every intended contract is
   proved and every volatile view valid, and the marks the records carry (filter_bin intended_bounded,
   intended.contract, intended.l_weak) are exactly those K5 requires (tests_m3/_i64.g10). With no contract it passes and
   says so. On failure it names each contract and the reason (invalid, not in the registry, not derived or decided,
   stale, not proved: <status>). G10 is in the gate's default checks.
K7 Change. A change to a contract's facts file makes it stale: G10 fails until `holon contracts derive` and `holon run`
   decide it again over the new facts, and then passes iff its L_weak is still proved. A changed contract fails G10
   until the registry is updated (K2).
K8 Records. spec/schemas/result_record_v2.schema.json admits filter_bin "intended_bounded" and the field "intended"
   {contract, l_weak, replaces} on REFUTED records. The frozen v1 schemas/ and its triage enum are untouched (Q4).
K9 Volatile views. A volatile-view contract is valid iff K1 holds and its view's facts document lists the function
   with that result index among go.slices.results. It is not proved; OWN (I35) reads the valid ones as the exception
   whitepaper §5.8 allows. results/M/contracts.json lists it with state "valid" or why not.
K10 Q4 adoption package. docs/adoption/Q4/README.md gives the human's exact steps to adopt result_record_v2 and
   law_ir_0_3 into the frozen schemas/ (Q4; AGENTS.md rule 1: the agent never runs tools/freeze.py write), including
   the CI digest pin of holon-ci.yml (Q40). docs/adoption/Q4/schemas/ holds the two files byte-equal to spec/schemas/
   at the build's head.

Commands
  python -m holon contracts derive --milestone M [--check]   K3 (--check: the derived laws equal the committed ones)
  python -m holon contracts apply --milestone M [--check]    K5 without deciding (--check: records and contracts.json
                                                            equal the committed ones)
  python -m holon gate --milestone M --checks G10            K6
  Exit codes: 0 done (or --check reproduced); 1 --check differs; 2 refused (derive: an invalid contract; either: a
  missing input), nothing written.

Rules for every session (AGENTS.md): I64 adds no contract to M0-M3, changes no M0-M3 law or record, and never writes
under schemas/ or another frozen root. I64's outcome paths are laws/CONTRACTS/, docs/adoption/Q4/ and
docs/iterations/I64.md; its code (holon/contracts.py, the gates' G10, the run's last step) and the v2 schema change are
build commits.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, copy_repo, file_sha256, item, load_json, predictions, run_holon, validate

FX = ROOT / "tests_m3" / "fixtures" / "contracts"
FX_REL = "tests_m3/fixtures/contracts"
FACTS = f"{FX_REL}/toy_intent.facts.json"
T = "T64"
V2 = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
ADOPT = ROOT / "docs" / "adoption" / "Q4"
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


def holon_ok(args, repo, what):
    p = run_holon(args, cwd=repo, timeout=3600)
    if p.returncode != 0:
        raise AssertionError(f"holon {' '.join(args)} ({what}) failed: {(p.stdout + p.stderr)[-3000:]}")
    return p


def put_contracts(repo, ids) -> None:
    """laws/CONTRACTS/ in a copy: the fixture contracts named, and a registry of their hashes (K2)."""
    I = instrument()
    d = repo / "laws" / "CONTRACTS"
    d.mkdir(parents=True, exist_ok=True)
    reg = {}
    for cid in ids:
        c = load_json(FX / "contracts" / f"{cid}.json")
        (d / f"{cid}.json").write_text(json.dumps(c, indent=2, sort_keys=True) + "\n")
        reg[cid] = {"milestone": c["milestone"], "kind": c["kind"], "sha256": I.content_sha256(c)}
    doc = {"registry_version": "holon-contracts-registry/0.1", "contracts": dict(sorted(reg.items()))}
    (d / "REGISTRY.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def run_t64(repo, contracts=("C_t64_ext", "V_t64_view")) -> dict:
    """laws/T64 (the fixture laws, facts_sha256 filled, REGISTRY.json), the contracts, holon contracts derive, holon run
    --milestone T64 --no-registry, holon metrics; the registry's statement hashes are then filled from the records, so
    that G1 can regenerate T64. Returns the records."""
    sha = file_sha256(repo / FACTS)
    d = repo / "laws" / T
    d.mkdir(parents=True, exist_ok=True)
    for p in sorted((FX / "laws").glob("L_*.json")):
        law = load_json(p)
        law["facts_sha256"] = sha
        (d / p.name).write_text(json.dumps(law, indent=2, sort_keys=True) + "\n")
    put_contracts(repo, contracts)
    holon_ok(["contracts", "derive", "--milestone", T], repo, "derive")
    ids = sorted(p.stem for p in d.glob("L_*.json"))
    (d / "REGISTRY.json").write_text(json.dumps({"milestone": T, "facts": FACTS, "facts_sha256": sha,
                                                 "facts_files": {FACTS: sha}, "statements": {i: None for i in ids}},
                                                indent=2, sort_keys=True) + "\n")
    holon_ok(["run", "--milestone", T, "--no-registry"], repo, "run")
    holon_ok(["metrics", "--milestone", T], repo, "metrics")
    recs = records(repo)
    reg = load_json(d / "REGISTRY.json")
    reg["statements"] = {i: recs[i]["statement_hash"] for i in ids if i in recs}
    (d / "REGISTRY.json").write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    return recs


def baseline():
    """One copy of the repository with T64 run under C_t64_ext and V_t64_view (cached for the module)."""
    if "base" not in _RUNS:
        repo = copy_repo()
        _RUNS["base"] = (repo, run_t64(repo))
    return _RUNS["base"]


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
        contracts only."""
        repo, _ = baseline()
        I = instrument()
        c = load_json(FX / "contracts" / "C_t64_ext.json")
        self.assertEqual(load_json(repo / "laws" / T / "L_contract_C_t64_ext.json"), I.derived_law(c, repo))
        self.assertEqual(sorted(p.name for p in (repo / "laws" / T).glob("L_contract_*.json")),
                         ["L_contract_C_t64_ext.json"])
        p = run_holon(["contracts", "derive", "--milestone", T, "--check"], cwd=repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_an_invalid_contract_is_refused(self):
        """K1, K9: V_t64_bad (its function is not in the Go document) makes derive exit 2 and write nothing."""
        repo = copy_repo()
        put_contracts(repo, ["C_t64_ext", "V_t64_bad"])
        p = run_holon(["contracts", "derive", "--milestone", T], cwd=repo)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertFalse((repo / "laws" / T / "L_contract_C_t64_ext.json").exists())
        shutil.rmtree(repo.parent, ignore_errors=True)


class TestPredictions(unittest.TestCase):
    """I64's predictions (spec/M3/predictions.json key I64), decided on runs in copies of the repository."""

    def test_p1_the_generators_decide_the_toy(self):
        """I64-P1: on T64 the obstruction L_t64_cancel is REFUTED, the control L_t64_flag is REFUTED, and C_t64_ext's
        L_weak (L_contract_C_t64_ext) is PROVED, all by the existing generators and refuters."""
        item("I64", "I64-P1")
        _, recs = baseline()
        self.assertEqual({k: recs[k]["status"] for k in ("L_t64_cancel", "L_t64_flag", "L_contract_C_t64_ext")},
                         {"L_t64_cancel": "REFUTED", "L_t64_flag": "REFUTED", "L_contract_C_t64_ext": "PROVED"})

    def test_p2_the_proved_contract_marks_its_scope_alone(self):
        """I64-P2: against a run with no contract (which writes no results/T64/contracts.json), L_t64_cancel's record
        is marked, filter_bin intended_bounded and intended {contract C_t64_ext, l_weak L_contract_C_t64_ext, replaces:
        its filter_bin there}, and is otherwise the same; L_t64_flag's record is the same; G10 passes on T64. Records
        are compared without their wall-clock fields."""
        item("I64", "I64-P2")
        repo, recs = baseline()
        bare = copy_repo()
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
        _, rep = gate(repo, T)
        self.assertEqual(g10_line(rep).get("status"), "PASS", rep)
        shutil.rmtree(bare.parent, ignore_errors=True)

    def test_p3_a_false_contract_marks_nothing_and_fails_g10(self):
        """I64-P3: with C_t64_zero (L_weak: no residue) in place of C_t64_ext, L_contract_C_t64_zero is REFUTED,
        L_t64_cancel is not marked, and G10 fails naming C_t64_zero."""
        item("I64", "I64-P3")
        repo = copy_repo()
        recs = run_t64(repo, contracts=("C_t64_zero",))
        self.assertEqual(recs["L_contract_C_t64_zero"]["status"], "REFUTED")
        self.assertNotEqual(recs["L_t64_cancel"].get("filter_bin"), "intended_bounded")
        _, rep = gate(repo, T)
        line = g10_line(rep)
        self.assertEqual(line.get("status"), "FAIL", rep)
        self.assertIn("C_t64_zero", line.get("detail", ""))
        shutil.rmtree(repo.parent, ignore_errors=True)

    def test_p4_a_facts_change_needs_a_new_proof(self):
        """I64-P4: (a) a change of the facts that leaves the toy's behaviour (the doc text of action raise) makes G10
        fail as stale; after holon contracts derive and holon run it passes again, with L_t64_cancel marked. (b) W
        changed from 3 to 4 makes G10 fail as stale; after derive and run, C_t64_ext's L_weak (+3) is REFUTED, nothing
        is marked, and G10 fails."""
        item("I64", "I64-P4")
        for variant, w, after in (("doc", 3, "PASS"), ("W", 4, "FAIL")):
            with self.subTest(change=variant):
                repo = copy_repo()
                run_t64(repo)
                f = load_json(repo / FACTS)
                if variant == "doc":
                    next(a for a in f["actions"] if a["name"] == "raise")["src"] = "toy: raise() (changed doc text)"
                else:
                    f["params"]["W"] = w
                (repo / FACTS).write_text(json.dumps(f, indent=1) + "\n")
                _, rep = gate(repo, T)
                line = g10_line(rep)
                self.assertEqual(line.get("status"), "FAIL", rep)
                self.assertIn("stale", line.get("detail", ""))
                recs = run_t64(repo)
                _, rep = gate(repo, T)
                self.assertEqual(g10_line(rep).get("status"), after, rep)
                marked = recs["L_t64_cancel"].get("filter_bin") == "intended_bounded"
                self.assertEqual(marked, after == "PASS")
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

    def test_g10_on_the_real_milestones(self):
        """M0, M1: not_applicable with a reason; M2, M3: PASS with no contract. G10 is in the default checks."""
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                _, rep = gate(ROOT, m)
                self.assertIn("G10", rep.get("not_applicable", {}), rep)
        for m in ("M2", "M3"):
            with self.subTest(milestone=m):
                _, rep = gate(ROOT, m)
                self.assertEqual(g10_line(rep).get("status"), "PASS", rep)
        src = (ROOT / "holon" / "gate.py").read_text()
        self.assertIn("G10", src)


class TestSchemaAndAdoption(unittest.TestCase):
    """K8, K10."""

    def test_v2_admits_intended_bounded(self):
        s = load_json(V2)
        self.assertIn("intended_bounded", s["properties"]["filter_bin"]["enum"])
        self.assertTrue((ROOT / "schemas").is_dir())
        p = subprocess.run([sys.executable, "tools/freeze.py", "check"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_q4_package(self):
        for name in ("result_record_v2.schema.json", "law_ir_0_3.schema.json"):
            with self.subTest(file=name):
                self.assertEqual((ADOPT / "schemas" / name).read_bytes(),
                                 (ROOT / "spec" / "schemas" / name).read_bytes())
        text = (ADOPT / "README.md").read_text()
        for word in ("tools/freeze.py write", "FROZEN.sha256", "holon-ci.yml", "schemas/"):
            self.assertIn(word, text)


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change."""

    def test_no_contract_on_the_real_milestones(self):
        """I64-R1 (part): no committed contract names M0-M3, and no M0-M3 record is marked intended_bounded."""
        item("I64", "I64-R1")
        I = instrument()
        for p in I.contract_files(ROOT):
            self.assertNotIn(load_json(p).get("milestone"), ("M0", "M1", "M2", "M3"), p.name)
        for m in ("M0", "M1", "M2", "M3"):
            for p in sorted((ROOT / "results" / m).glob("L*.json")):
                self.assertNotEqual(load_json(p).get("filter_bin"), "intended_bounded", p)

    def test_outcome_commits_touch_no_law_or_record(self):
        """I64-R2 (part): no commit that writes an I64 outcome path changes laws/M0-M3, results/M0-M3, gen/M0-M3,
        spec/M1, spec/M2, holon/rules/, replay/ or a frozen root. Needs the real checkout's history and at least one
        such commit: a missing .git, or no outcome commit yet, is a failure, never a skip."""
        item("I64", "I64-R2")

        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        outs = tuple(predictions("I64")["outcome_paths"])
        forbidden = ("laws/M0/", "laws/M1/", "laws/M2/", "laws/M3/", "results/M0/", "results/M1/", "results/M2/",
                     "results/M3/", "gen/M0/", "gen/M1/", "gen/M2/", "gen/M3/", "spec/M1/", "spec/M2/", "holon/rules/",
                     "replay/", "facts/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                     "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        commits, cur = [], None
        for line in git("log", "--no-merges", "--format=@%H", "--name-only", "HEAD").splitlines():
            if line.startswith("@"):
                cur = (line[1:], [])
                commits.append(cur)
            elif line.strip() and cur is not None:
                cur[1].append(line.strip())
        commits = [(c, names) for c, names in commits if any(n.startswith(outs) for n in names)]
        self.assertTrue(commits, "no commit writes an I64 outcome path")
        for c, names in commits:
            self.assertEqual([n for n in names if n.startswith(forbidden)], [], f"commit {c[:12]}")


if __name__ == "__main__":
    unittest.main()
