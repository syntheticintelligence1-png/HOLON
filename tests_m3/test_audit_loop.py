"""I87 (= I45a): the audit-loop machinery (BUILD_PLAN row I87; whitepaper §9.1, §9.2(6), §9.5, §12.3, L7, L19;
HUMAN_ANSWERS Q9), exercised on today's M3. This docstring is the contract. The policy is the sidecar
spec/M3/lib/audit_loop.json (k, the auditor types, the counted family, the high-priority severities, the degenerate
rules, the representative fill, the admission rule). Nothing in holon/ names a law, an action, a register or a target.

Rounds (holon/audit/rounds.py; `python -m holon audit round --milestone M [--root R] [--json]`, exit 0 iff every round
of M is valid). A round of milestone M is audit/rounds/<M>/round<n>.json, valid against
spec/schemas/audit_round.schema.json, which I87 extends with optional fields only, so every committed round of M0-M2
stays valid: round_version "holon-audit-round/0.2"; dry_run (bool); packet {path, sha256} (the hostile-review packet
its auditors were given); and per attack auditor_type (A1-A4) and run (bool; false: listed, not run). A round's
auditor types are the auditor_type of its attacks that ran.
  RD1 auditor.family is "same" or "different", relative to the builders' family; a same-family round and a dry run
      have counts_toward_convergence false (Q9);
  RD2 counts_toward_convergence is true only for a round that qualifies under CV1;
  RD3 the rounds of M are numbered 1..n without a gap, and each round's findings are exactly the union of its
      attacks' findings.
Schemas are read from the repository holon runs from; rounds, findings and the policy from the root.

Convergence (holon/audit/converge.py; `python -m holon audit converge --milestone M [--root R] [--out PATH]
[--check]` writes results/<M>/audit_status.json, valid against spec/schemas/audit_status.schema.json: JSON with sorted
keys, indent 1 and a final newline, no timestamps; it exits 0 whenever it wrote the document, problems included;
--check writes nothing and exits 0 iff the regeneration is byte-identical). The findings file is audit/<M>_findings.jsonl (M0 and M1: audit/findings.jsonl); the policy is
spec/<M>/lib/audit_loop.json of the root (k, auditor_types, counted_family, high_priority_severities).
  CV1 a round is counted iff counts_toward_convergence is true and it qualifies: auditor.family is the counted family
      ("different"), it is not a dry run, its auditor types hold every type of the policy (A1-A4), and its
      auditor.session differs from the session of every earlier round of M (a fresh context, L19);
  CV2 a round is clean iff every finding it lists is in the findings file with a severity that is not high-priority
      (an id the file does not hold is not clean);
  CV3 the streak: walking the rounds in order, a round that is not clean resets it to 0, whatever its family; a
      counted clean round adds 1; any other round leaves it unchanged;
  CV4 converged iff the rounds are valid (RD1-RD3), the streak is at least k, and no finding of M with a high-priority
      severity is open.
The document: {status_version "holon-audit-status/0.1", milestone, k, converged, streak, counted (the number of
counted rounds), rounds [{round, family, dry_run, counted, clean, why}], open_high [ids], problems [RD1-RD3 strings],
findings_file, policy {path, sha256}, why}.

The hostile-review packet (holon/audit/hostile.py, for M3 and later; M2 keeps I21's A2 instrument):
`python -m holon audit hostile --milestone M --round n [--target COMMIT] [--out PATH] [--check]` writes
audit/rounds/<M>/round<n>/packet.json (packet_version "holon-audit-packet/0.1"), what every auditor of the round is
given. Every input, the policy included, is read from the target commit's tree (git archive into a scratch
directory, as I21's instruments do); --check reads target_commit from the committed file, rebuilds and compares byte
for byte (canonical JSON: sorted keys, indent 2, a final newline). It holds milestone, round, target_commit, policy
{path, sha256}, inputs [{path, sha256}] (every file read, sorted by path), and
  laws      {law_id: {rule, subform, status, statement_hash, facts, premises (the record's), binders [[name, type,
            q]], kernels ["name:result"], filter_bin, triage, non_vacuity (its status), witness_sha256 (sha256 of the
            canonical JSON of the record's witness; null without one)}} for every law of laws/<M> at the target;
  auditors  {A1..A4: {name, what (the policy's), targets}}: A1 {facts document: [law ids]} of the decided (PROVED
            or REFUTED) laws; A2 [law ids] of the PAR laws of the policy's A2 subforms; A3 {registry_sha256,
            previous_target (the target_commit of round n-1 of M, null for round 1)}; A4 [law ids] of the premised
            laws (an assume premise or a Reach binder).

A4, vacuity and over-strength (holon/audit/vacuity.py, for M3 and later; M2 keeps I21's instrument):
`python -m holon audit vacuity --milestone M --round n [--target COMMIT] [--out PATH] [--check]` writes
audit/rounds/<M>/round<n>/a4.json (a4_version "holon-audit-a4/0.1"), every input read from the target commit's tree,
--check as the packet's. It reuses G11V's records (non_vacuity), holon.inhabit.premised, G11V's in-flight clause
(holon.versions.inhabit.clause) and the inhabitant generators and checker G11V's inhabitants come from; it never
re-implements a gate check. Every law of laws/<M> gets one class:
  V1 no_premises     no assume premise and no Reach binder;
  V2 not_decided     premised and UNKNOWN: the law claims nothing yet;
  V3 counter_witness premised and REFUTED: the accepted counter-law inhabits the premises; never degenerate;
  V4 vacuous         premised and PROVED with no usable inhabitant: non_vacuity.status is not "inhabited", or its
                     parent_statement_hash is not the record's statement_hash, or that is not the registry's, or it
                     has no witness, or its inhabitant file non_vacuity.law does not exist;
  V5 degenerate      premised, PROVED, inhabited, and a degenerate rule holds at the inhabitant (non_vacuity.witness):
       D1 (a law with a State or Reach binder) the inhabitant's state is the initial state: a {steps, ..} witness
          (the run ending with the law's own step) has at most one step; a {prefix, x, ..} witness has an empty
          prefix; a {runs: [..]} witness has every prefix empty; a witness of state binders {<binder>: {run}} has
          every run empty;
       D2 (a law with two state binders) its two runs are identical: a {prefix, x, ..} witness (one run, used for
          both); {runs: [r1, r2, ..]} with r1 == r2; the first two state binders' runs equal;
       D3 (a law with no State or Reach binder) every byte the premises leave free is zero: the premises' field
          equalities form classes, a pin "field == bytes" fixes its class, and every byte of every witness field
          (record binders) and of every Bytes binder whose class no pin fixes is 0;
  V6 unreadable      premised, PROVED, inhabited, but the witness has none of the shapes above;
  V7 ok              premised, PROVED, inhabited, readable, and no degenerate rule holds.
Each law's entry: {class, rule, subform, status, rules (the D-rules that hold, sorted), representative, why}.
Representatives (§12.3: "representative rather than degenerate"), for a degenerate inhabitant only:
  over a linked codec document: the witness of holon.gen.linked's own "counting" fill (the policy's linked_fill) with
  the law's premise classes applied (holon.gen.linked fills and apply_classes), written by the law's own inhabitant
  generator (holon.codecrun.inhabitant) beside a copy of the target's committed model, and checked as G11V's
  inhabitants are (holon.inhabit: bend2, then BendTT when enabled). {status "found" iff the checker accepts and no
  degenerate rule holds at it, else "not_found" with the checker's first line; fill, witness, kernels}.
  any other degenerate inhabitant: {status "not_searched", why} (I87 has no state-law representative search; the I45
  round's A4 auditor searches). A degenerate inhabitant without a found representative is a concern the round
  reports; it is never cleared by I87.
counts {class: n} over the seven classes; in_flight {ok, detail} of G11V's in-flight clause (null when the milestone
has no versions sidecar); oracles (holon/audit/oracles.py's report, below); canaries, A4's own sensitivity, each {kind,
what, detected}:
  unsatisfiable_premise  a scratch copy of the first (by law id) inhabited law over a linked codec document with a
                         one-byte pin, with one more premise pinning the same field to the next byte value (mod 256):
                         the inhabitant its generators give must not check, so the copy classifies vacuous;
  degenerate_state       the first (by law id) ok inhabitant with a {steps} witness cut to its last step: D1 holds;
  degenerate_pure        the first (by law id) found representative with every free byte set to zero: D3 holds;
  false_oracle           the first (by law id, then table order) oracle-table entry with the last hex digit of its
                         word changed: O3 reports a mismatch.

Oracles, A4's oracle half (holon/audit/oracles.py; `python -m holon audit oracles --milestone M [--root R] [--json]`):
  O1 hypotheses   every entry of the milestone's oracle sidecar (holon.gen.oracles), tested against the real oracle
                  by holon.oracle_check: {id: {status, ..}}; {} when the milestone has no sidecar;
  O2 parameters   every function-typed binder (type Fn<..>) of the milestone's laws: {name: {type, laws, constrained}},
                  constrained the number of those laws with a premise that mentions it (a cf or hyp premise, or an
                  application);
  O3 tables       every hash-table entry (a "hashes" object {keccak256 | sha256: [[key, word], ..]}, anywhere in a
                  record's witness, witnesses or non_vacuity witness, results/<M>/L*.json) against the real oracle on
                  the key's bytes (holon/keccak.py's Keccak-256; hashlib's SHA-256): {entries, oracles {name: n},
                  mismatches [{law, where, oracle, key}]}.

Rule gaps and the L7 admission rule (holon/audit/gaps.py; `python -m holon audit gaps [--root R] [--json]`, exit 0
iff the file is valid, whatever the verdicts). audit/rule_gaps.jsonl holds one JSON object per line, valid against
spec/schemas/rule_gap.schema.json:
  {"kind": "gap", "id": "RG-<M>-<nn>", "milestone", "finding" (an id of that milestone's findings file), "title",
   "outside" (why no rule of the catalog states it), "candidate" (a candidate rule's name, or null)}
  {"kind": "candidate", "name", "instances": [gap ids], "basis": {"argument", "obligation"},
   "approval": {"by", "signature"} or null}
  L7 a candidate is admitted iff (a) its instances are at least the policy's min_instances (2) gap lines naming it,
     every listed id is such a line, each names a finding of its milestone's findings file, and they name at least two
     distinct findings; (b) its basis has a non-empty argument and obligation; (c) human approval: approval.signature
     verifies (holon.statement_diff.verify_signature) over the candidate line without its approval field
     (holon.statement_diff.signed_payload's canonical JSON) against a key the human froze. The --json report:
     {"valid", "problems", "gaps": n, "candidates": {name: {"admitted", "fails": [a|b|c], "why"}}}. With no frozen key,
     (c) fails for every candidate, so nothing is admitted.

Coordinator (holon/coordinator.py; whitepaper §9.1: the human's one window into the system):
  `python -m holon coordinator status [--root R] [--out PATH] [--check]` renders docs/STATUS.md from every
  spec/M*/predictions.json with iteration keys, prompts/, docs/iterations/ and results/M*/audit_status.json, with no
  git, no clock and no environment; --check exits 0 iff the committed file is byte-identical. Every key appears in a
  row with its milestone, title (its first sentence, at most 120 characters), prompt path (or none), its counts of
  predictions, regressions and tests, and its report docs/iterations/<key>.md (or none); each milestone with an
  audit_status.json gets its convergence line.
  `python -m holon coordinator prompt --key I<n> [--root R] [--out PATH]` renders a session prompt from
  docs/BUILD_PLAN.md: the iteration's §4 section ("#### I<n>. ..." up to the next heading) when there is one, else its
  §3 map row, verbatim, under the standard preamble (read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md first; the
  prereg protocol). The default output is prompts/I<n>_<slug>.md; it refuses (exit 2) to write over any existing
  prompt of the key.
  `python -m holon coordinator audit-prompt --milestone M --round n --type A<k> [--root R] [--out PATH]` renders an
  auditor's prompt from audit/prompts/<A<k>>.md and the round's packet.

What I87 runs on today's M3 (the dry run, Q9): round 1 of M3, audit/rounds/M3/round1.json, labelled same-family and
dry_run, counts_toward_convergence false, its target a commit whose laws/M3, results/M3 and gen/M3 are the base's;
its packet and a4.json; its findings in audit/M3_findings.jsonl; results/M3/audit_status.json; audit/rule_gaps.jsonl;
docs/STATUS.md.
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

from tests_m3 import _i87 as I
from tests_m3._m3 import ROOT, holon_module, predictions, run_holon, validate

KEY = "I87"
M = "M3"
ROUND = ROOT / "audit" / "rounds" / M / "round1.json"
PACKET = ROOT / "audit" / "rounds" / M / "round1" / "packet.json"
A4 = ROOT / "audit" / "rounds" / M / "round1" / "a4.json"
STATUS = ROOT / "results" / M / "audit_status.json"
FINDINGS = ROOT / "audit" / f"{M}_findings.jsonl"
GAPS = ROOT / "audit" / "rule_gaps.jsonl"
STATUS_MD = ROOT / "docs" / "STATUS.md"
SCHEMAS = ROOT / "spec" / "schemas"
NEW_MODULES = ("holon/audit/rounds.py", "holon/audit/converge.py", "holon/audit/oracles.py", "holon/audit/gaps.py",
               "holon/coordinator.py")


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def _is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base --is-ancestor {a} {b}: {p.stderr.strip()}")
    return p.returncode == 0


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I87 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I87")


def own_commits() -> dict[str, list[str]]:
    """I87's own commits: the non-merge commits of `git log --first-parent <C_K>..<end>`, end the first commit adding
    docs/iterations/I87.md (HEAD before it exists), each with the paths it changes; along the first-parent line of the
    merge that brings the branch into the lead when there is one."""
    pre = prereg_commit()
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I87.md").split()
    end = added[0] if added else "HEAD"
    revs = [f"{pre}..{end}"]
    if added:
        for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{end}..HEAD").splitlines():
            c, *parents = line.split()
            if len(parents) > 1 and _is_ancestor(end, parents[1]) and not _is_ancestor(end, parents[0]):
                revs = [parents[1], f"^{parents[0]}", f"^{pre}"]
                break
    out: dict[str, list[str]] = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def load(p: Path):
    return json.loads(Path(p).read_text())


def jsonl(p: Path) -> list:
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


def target_tree() -> I.Tree:
    """The dry run's target, after checking that its laws/M3, results/M3 and gen/M3 are the base's."""
    t = load(A4)["target_commit"]
    for d in (f"laws/{M}", f"results/{M}", f"gen/{M}"):
        a = git("rev-parse", f"{t}:{d}").strip()
        b = git("rev-parse", f"{I.BASE}:{d}").strip()
        if a != b:
            raise AssertionError(f"the dry run's target {t[:12]} has another {d} than the base {I.BASE[:12]}")
    return I.Tree(t)


def scratch_root() -> Path:
    d = Path(tempfile.mkdtemp(prefix="i87-root-"))
    (d / "spec").mkdir()
    return d


# ====================================================================== A4: vacuity
class TestVacuity(unittest.TestCase):
    def test_p1_classes(self):
        """P1: over the base's 136 M3 laws: no_premises 40, not_decided 24, counter_witness 20, vacuous 0, degenerate
        40 (38 PAR codec inhabitants by D3, the FACT kernel inhabitant by D2, one DISCH revert inhabitant by D1),
        unreadable 0, ok 12; every class is the instrument's."""
        a4 = load(A4)
        tree = target_tree()
        got = {lid: {"class": e["class"], "rules": e["rules"]} for lid, e in a4["laws"].items()}
        self.assertEqual(got, I.classify_all(tree))
        self.assertEqual(len(got), 136)
        self.assertEqual(a4["counts"], I.EXPECTED_COUNTS)
        deg: dict = {}
        for lid, e in a4["laws"].items():
            if e["class"] == "degenerate":
                k = (e["rule"], e["subform"])
                deg.setdefault(k, {})
                deg[k][tuple(e["rules"])] = deg[k].get(tuple(e["rules"]), 0) + 1
        self.assertEqual(deg, I.EXPECTED_DEGENERATE)

    def test_p2_external_inhabitants(self):
        """P2: none of the PROVED external DISCH laws' inhabitants (their checked witnesses) sits at the initial
        state: each has at least two steps, and each classifies ok."""
        a4 = load(A4)
        tree = target_tree()
        rc = I.records_at(tree)
        ext = sorted(lid for lid, r in rc.items()
                     if r["rule"] == "DISCH" and r.get("subform") == "external" and r["status"] == "PROVED")
        self.assertEqual(len(ext), 6)
        for lid in ext:
            self.assertGreaterEqual(len(rc[lid]["non_vacuity"]["witness"]["steps"]), 2, lid)
            self.assertEqual((a4["laws"][lid]["class"], a4["laws"][lid]["rules"]), ("ok", []), lid)

    def test_p3_representatives(self):
        """P3: each of the 38 degenerate PAR codec inhabitants has a found representative (the counting fill, the
        premise classes applied, accepted by bend2 and BendTT through the law's own inhabitant generator); the two
        degenerate state-law inhabitants (FACT D2, DISCH D1) are not_searched."""
        a4 = load(A4)
        tree = target_tree()
        lw = I.laws_at(tree)
        n: dict = {}
        for lid, e in a4["laws"].items():
            if e["class"] != "degenerate":
                self.assertIsNone(e["representative"], lid)
                continue
            rep = e["representative"]
            n[rep["status"]] = n.get(rep["status"], 0) + 1
            if rep["status"] == "found":
                self.assertEqual(rep["fill"], "counting", lid)
                self.assertTrue(I.representative_ok(lw[lid], rep["witness"]), lid)
                self.assertEqual(rep["kernels"].get("bend2"), "ALL PROOFS CHECK", lid)
                self.assertEqual(rep["kernels"].get("bendtt"), "checked", lid)
            else:
                self.assertEqual(rep["status"], "not_searched", lid)
                self.assertIn(e["rule"], ("FACT", "DISCH"), lid)
        self.assertEqual({k: n.get(k, 0) for k in I.EXPECTED_REPRESENTATIVES}, I.EXPECTED_REPRESENTATIVES)

    def test_r6_canaries(self):
        """R6: A4's canaries (an unsatisfiable premise, a degenerate state and pure inhabitant, a false oracle answer)
        are all detected."""
        cs = load(A4)["canaries"]
        self.assertEqual(sorted(c["kind"] for c in cs),
                         ["degenerate_pure", "degenerate_state", "false_oracle", "unsatisfiable_premise"])
        for c in cs:
            self.assertIs(c["detected"], True, c)

    def test_r11_in_flight_and_hypotheses(self):
        """R11: A4 reports G11V's in-flight clause as G11V does (on the base: 0 of 8 MIG edges inhabited, I28's P5
        miss); the base's M3 has no oracle hypothesis, and no premise constrains an oracle parameter."""
        a4 = load(A4)
        self.assertIs(a4["in_flight"]["ok"], False)
        self.assertTrue(a4["in_flight"]["detail"].startswith("in-flight: 0 of 8 edges inhabited"), a4["in_flight"])
        o = a4["oracles"]
        self.assertEqual(o["hypotheses"], {})
        self.assertTrue(o["parameters"])
        self.assertEqual({k: v["constrained"] for k, v in o["parameters"].items()},
                         {k: 0 for k in o["parameters"]})

    def test_r5_regenerates(self):
        """R5: `holon audit vacuity --milestone M3 --round 1 --check` rebuilds a4.json from its target commit byte for
        byte (runs the checker)."""
        p = run_holon(["audit", "vacuity", "--milestone", M, "--round", "1", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])


# ====================================================================== A4: oracles
class TestOracles(unittest.TestCase):
    def test_p4_tables(self):
        """P4: every hash-table entry of every M3 record's witness and inhabitant at the base equals the real oracle
        (Keccak-256, SHA-256) on its key: entries > 0, no mismatch; holon's count is the instrument's."""
        o = load(A4)["oracles"]["tables"]
        n, bad = I.table_mismatches(I.records_at(target_tree()))
        self.assertGreater(n, 0)
        self.assertEqual(bad, [])
        self.assertEqual((o["entries"], o["mismatches"]), (n, []))

    def test_cli(self):
        """`holon audit oracles --milestone M3 --json` prints the same report on the working tree's M3 as the
        instrument's table count there."""
        p = run_holon(["audit", "oracles", "--milestone", M, "--json"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        o = json.loads(p.stdout)
        recs = {q.stem: load(q) for q in sorted((ROOT / "results" / M).glob("L*.json"))}
        n, bad = I.table_mismatches(recs)
        self.assertEqual((o["tables"]["entries"], len(o["tables"]["mismatches"])), (n, len(bad)))


# ====================================================================== rounds and convergence
def write_scratch(root: Path, m: str, rounds: list, findings: list) -> None:
    (root / "audit" / "rounds" / m).mkdir(parents=True, exist_ok=True)
    for r in rounds:
        (root / "audit" / "rounds" / m / f"round{r['round']}.json").write_text(json.dumps(r, indent=2) + "\n")
    (root / "audit" / f"{m}_findings.jsonl").write_text("".join(json.dumps(f) + "\n" for f in findings))
    (root / "spec" / m / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / I.POLICY_REL, root / "spec" / m / "lib" / "audit_loop.json")


class TestConverge(unittest.TestCase):
    def test_r1_rule_on_fixtures(self):
        """R1: on every synthetic scenario (same-family rounds, repeated sessions, missing auditor types, dry runs,
        resets by a high finding of any family, open high findings, unknown finding ids, numbering gaps), holon's
        validity, convergence, streak, counted rounds and per-round verdicts are the instrument's."""
        pol = I.policy()
        for name, rounds, findings in I.converge_fixtures():
            with self.subTest(scenario=name):
                want = I.converge(rounds, findings, pol)
                root = scratch_root()
                try:
                    write_scratch(root, "M9", rounds, findings)
                    out = root / "status.json"
                    p = run_holon(["audit", "converge", "--milestone", "M9", "--root", str(root), "--out", str(out)])
                    self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                    got = load(out)
                    self.assertEqual((not got["problems"], got["converged"], got["streak"], got["counted"]),
                                     (want["valid"], want["converged"], want["streak"], want["counted"]))
                    self.assertEqual({r["round"]: (r["counted"], r["clean"]) for r in got["rounds"]}, want["rounds"])
                    self.assertEqual(got["open_high"], want["open_high"])
                    self.assertEqual(validate(got, SCHEMAS / "audit_status.schema.json"), [])
                finally:
                    shutil.rmtree(root, ignore_errors=True)
        verdicts = [I.converge(r, f, pol) for _n, r, f in I.converge_fixtures()]
        self.assertEqual(sum(v["converged"] for v in verdicts), 4)
        self.assertEqual(sum(not v["valid"] for v in verdicts), 5)

    def test_r2_status_document(self):
        """R2: results/M3/audit_status.json: not converged, k 3, streak 0, no counted round; valid; `holon audit
        converge --milestone M3 --check` passes; the instrument agrees."""
        st = load(STATUS)
        self.assertEqual(validate(st, SCHEMAS / "audit_status.schema.json"), [])
        self.assertEqual((st["converged"], st["k"], st["streak"], st["counted"]), (False, 3, 0, 0))
        rounds = [load(p) for p in sorted((ROOT / "audit" / "rounds" / M).glob("round*.json"))]
        want = I.converge(rounds, jsonl(FINDINGS), I.policy())
        self.assertEqual((st["converged"], st["streak"], st["counted"]), (want["converged"], want["streak"],
                                                                           want["counted"]))
        p = run_holon(["audit", "converge", "--milestone", M, "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


class TestRounds(unittest.TestCase):
    def test_r3_round_files(self):
        """R3: round 1 of M3 is valid against the extended schema, labelled same-family, a dry run, not counted, with
        its packet's sha256; every committed round of M0-M3 is valid; `holon audit round` passes on M0-M3."""
        r = load(ROUND)
        schema = SCHEMAS / "audit_round.schema.json"
        self.assertEqual(validate(r, schema), [])
        self.assertEqual((r["round_version"], r["auditor"]["family"], r["dry_run"],
                          r["auditor"]["counts_toward_convergence"]), ("holon-audit-round/0.2", "same", True, False))
        self.assertEqual(r["packet"], {"path": "audit/rounds/M3/round1/packet.json",
                                       "sha256": hashlib.sha256(PACKET.read_bytes()).hexdigest()})
        self.assertEqual(r["target_commit"], load(PACKET)["target_commit"])
        self.assertEqual(r["target_commit"], load(A4)["target_commit"])
        ids = {f["id"] for f in jsonl(FINDINGS)}
        self.assertLessEqual(set(r["findings"]), ids)
        for m in ("M0", "M1", "M2", "M3"):
            for p in sorted((ROOT / "audit" / "rounds" / m).glob("round*.json")):
                self.assertEqual(validate(load(p), schema), [], p)
            q = run_holon(["audit", "round", "--milestone", m])
            self.assertEqual(q.returncode, 0, m + ": " + q.stdout[-1500:] + q.stderr[-1500:])


# ====================================================================== the packet
class TestPacket(unittest.TestCase):
    def test_r4_packet(self):
        """R4: `holon audit hostile --milestone M3 --round 1 --check` rebuilds the packet from its target commit byte
        for byte, two runs write the same bytes, and the packet's laws and auditor targets are the instrument's
        reading of the target."""
        p = run_holon(["audit", "hostile", "--milestone", M, "--round", "1", "--check"], timeout=1800)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        pk = load(PACKET)
        with tempfile.TemporaryDirectory() as d:
            outs = [Path(d) / "a.json", Path(d) / "b.json"]
            for out in outs:
                q = run_holon(["audit", "hostile", "--milestone", M, "--round", "1", "--target", pk["target_commit"],
                               "--out", str(out)], timeout=1800)
                self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])
            self.assertEqual(outs[0].read_bytes(), outs[1].read_bytes())
            self.assertEqual(outs[0].read_bytes(), PACKET.read_bytes())
        tree = target_tree()
        lw, rc, pol = I.laws_at(tree), I.records_at(tree), I.policy()
        self.assertEqual(sorted(pk["laws"]), sorted(lw))
        for lid, e in pk["laws"].items():
            r = rc[lid]
            self.assertEqual((e["status"], e["statement_hash"], e["rule"]), (r["status"], r["statement_hash"],
                                                                               r["rule"]), lid)
        a2 = sorted(lid for lid, law in lw.items() if rc[lid]["rule"] == "PAR"
                    and rc[lid].get("subform") in pol["auditor_types"]["A2"]["subforms"]["PAR"])
        self.assertEqual(pk["auditors"]["A2"]["targets"], a2)
        self.assertEqual(pk["auditors"]["A4"]["targets"], sorted(lid for lid, law in lw.items() if I.premised(law)))
        decided = {lid for lid, r in rc.items() if r["status"] in ("PROVED", "REFUTED")}
        self.assertEqual(sorted(x for v in pk["auditors"]["A1"]["targets"].values() for x in v), sorted(decided))
        self.assertIsNone(pk["auditors"]["A3"]["targets"]["previous_target"])


# ====================================================================== rule gaps and L7
class TestGaps(unittest.TestCase):
    def run_gaps(self, root: Path) -> dict:
        p = run_holon(["audit", "gaps", "--root", str(root), "--json"])
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        return json.loads(p.stdout)

    def scratch(self, lines: list, findings: list) -> Path:
        root = scratch_root()
        (root / "audit").mkdir()
        (root / "audit" / "rule_gaps.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines))
        (root / "audit" / "M9_findings.jsonl").write_text("".join(json.dumps(f) + "\n" for f in findings))
        (root / "spec" / "M3" / "lib").mkdir(parents=True)
        shutil.copy(ROOT / I.POLICY_REL, root / "spec" / "M3" / "lib" / "audit_loop.json")
        return root

    def test_r7_admission(self):
        """R7: the committed audit/rule_gaps.jsonl is valid and admits nothing. On the synthetic fixtures, holon's
        verdicts are the instrument's: one instance, two instances on one finding, instances on findings no findings
        file holds, an empty basis, no approval and an unverifiable signature are refused; a candidate signed by the
        human's frozen key is refused where no key is frozen and admitted where it is."""
        rep = self.run_gaps(ROOT)
        self.assertTrue(rep["valid"], rep)
        self.assertFalse(any(c["admitted"] for c in rep["candidates"].values()))
        for x in jsonl(GAPS):
            self.assertEqual(validate(x, SCHEMAS / "rule_gap.schema.json"), [], x)
        lines, findings = I.gap_fixtures()
        fids = {"M9": {f["id"] for f in findings}}
        keyroot = scratch_root()
        try:
            pub, home = I.make_frozen_root(keyroot)
            signed = I.signed_fixture(lines, home)
            for frozen in (False, True):
                with self.subTest(frozen_key=frozen):
                    root = self.scratch(signed, findings)
                    try:
                        if frozen:
                            for rel in ("keys/human.asc", "tools/freeze.py", "FROZEN.sha256"):
                                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(keyroot / rel, root / rel)
                        got = self.run_gaps(root)
                        want = I.admission(signed, fids, pub if frozen else None)
                        self.assertTrue(got["valid"], got)
                        self.assertEqual({k: (v["admitted"], v["fails"]) for k, v in got["candidates"].items()},
                                         {k: (v["admitted"], v["fails"]) for k, v in want.items()})
                        self.assertEqual(sorted(k for k, v in want.items() if v["admitted"]),
                                         ["SIGNED"] if frozen else [])
                    finally:
                        shutil.rmtree(root, ignore_errors=True)
            bad = self.scratch([{"kind": "gap", "id": "RG-M9-01"}], findings)
            try:
                p = run_holon(["audit", "gaps", "--root", str(bad), "--json"])
                self.assertNotEqual(p.returncode, 0, "an invalid rule-gap line must fail")
            finally:
                shutil.rmtree(bad, ignore_errors=True)
        finally:
            shutil.rmtree(keyroot, ignore_errors=True)


# ====================================================================== the coordinator
class TestCoordinator(unittest.TestCase):
    def test_r8_status(self):
        """R8: `holon coordinator status --check` passes on docs/STATUS.md, two renders are byte-identical, and every
        key of every spec/M*/predictions.json appears in it with its milestone."""
        p = run_holon(["coordinator", "status", "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        with tempfile.TemporaryDirectory() as d:
            outs = [Path(d) / "a.md", Path(d) / "b.md"]
            for out in outs:
                q = run_holon(["coordinator", "status", "--out", str(out)])
                self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])
            self.assertEqual(outs[0].read_bytes(), outs[1].read_bytes())
        text = STATUS_MD.read_text()
        for pf in sorted((ROOT / "spec").glob("M*/predictions.json")):
            doc = load(pf)
            for key in (doc.get("iterations") or {}):
                self.assertRegex(text, rf"(?m)^\| {key} \| {doc['milestone']} \|", key)

    def test_r8_prompts(self):
        """R8: `holon coordinator prompt` renders I45's prompt with its §4 section verbatim, deterministically, and
        refuses to write over I87's existing prompt."""
        plan = (ROOT / "docs" / "BUILD_PLAN.md").read_text()
        sec = re.search(r"(?ms)^#### I45\. .*?(?=^#{2,4} )", plan).group(0).strip()
        with tempfile.TemporaryDirectory() as d:
            outs = [Path(d) / "a.md", Path(d) / "b.md"]
            for out in outs:
                q = run_holon(["coordinator", "prompt", "--key", "I45", "--out", str(out)])
                self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])
            self.assertEqual(outs[0].read_bytes(), outs[1].read_bytes())
            text = outs[0].read_text()
            self.assertIn(sec, text)
            self.assertIn("AGENTS.md", text)
        before = {p.name: p.read_bytes() for p in (ROOT / "prompts").glob("I87_*.md")}
        q = run_holon(["coordinator", "prompt", "--key", "I87"])
        self.assertEqual(q.returncode, 2, q.stdout[-1500:] + q.stderr[-1500:])
        self.assertEqual({p.name: p.read_bytes() for p in (ROOT / "prompts").glob("I87_*.md")}, before)


# ====================================================================== construction honesty
class TestHonesty(unittest.TestCase):
    def test_r9_no_target_vocabulary(self):
        """R9: I87's new modules name no law, action, register or target, and import no test code."""
        bad = ["L_par_", "L_undo_", "L_fact_", "L_disch_", "L_sort_", "L_pinit", "Rollup", "commitBatch",
               "revertBatch", "importGenesisBatch", "batchBlobVersionedHashes", "contracts/", "morph", "Morph",
               "onlyOwner", "onlyActiveSubmitter", "onlyChallenger", "SequencerSetVerifyHash", "header_length"]
        for rel in NEW_MODULES:
            text = (ROOT / rel).read_text()
            for b in bad:
                self.assertNotIn(b, text, f"{rel} holds {b!r}")
            self.assertIsNone(re.search(r"(?m)^\s*(from|import)\s+tests", text), f"{rel} imports test code")

    def test_r10_nothing_else_changes(self):
        """R10: no own commit of I87 changes a law, a record, a generated or a replay file, other than
        results/M3/audit_status.json, and none touches a frozen root."""
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "docs/M0_SPEC.md",
                  "docs/BEND_PRIMER.md", "AGENTS.md", "tools/freeze.py", "FROZEN.sha256")
        for c, paths in own_commits().items():
            for p in paths:
                if p.split("/")[0] in ("laws", "results", "gen", "replay"):
                    self.assertEqual(p, "results/M3/audit_status.json", f"{c[:12]} changes {p}")
                self.assertFalse(p.startswith(frozen), f"{c[:12]} changes the frozen {p}")
        self.assertEqual(predictions(KEY)["tests"], ["tests_m3/test_audit_loop.py"])

    def test_r12_instruments_are_the_prereg(self):
        """R12: the instrument, the policy sidecar and this contract are the bytes the key's thresholds name."""
        t = predictions(KEY)["thresholds"]
        self.assertEqual(hashlib.sha256((ROOT / "tests_m3" / "_i87.py").read_bytes()).hexdigest(),
                         t["instrument_sha256"])
        self.assertEqual(hashlib.sha256((ROOT / I.POLICY_REL).read_bytes()).hexdigest(), t["sidecar"]["sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), t["contract_docstring_sha256"])


if __name__ == "__main__":
    unittest.main()
