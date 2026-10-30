"""I34: rule SYM on M3, the typed extracted Rollup (whitepaper §5.4 SYM: symmetry splits (revised), §8.3 SYM generator,
§8.4 the SYM law schema, Appendix E's SYM row; BUILD_PLAN §4 I34; docs/CASESTUDY.md O19, O20, O21, D6). This docstring
is the contract.

Scope. SYM is the last of the eight shape rules without a law on extracted code: M1 has one hand-written ω reorder law
(L_sym_omega, O19). I34 states SYM over the typed Rollup model (holon.sorts.model3 with I30's nominal sorts and I68's
structural store): the families its sorts admit, one equivariance law per (family, action), ω reorder pairs, the
Rollup's sentinel sites, and splits that become obstructions only through route (i) or (ii). O21 (τ, `enq = 0` in the
queue's getFirstUnfinalizedMessageEnqueueTime, from a migrated legacy-queue state) and the messenger's sentinels need
the queue model's enqueue actions (I69's model debt), a migrated legacy-queue state (η_enq, in no M3 machine) and
sorts over the bundle documents, none of which exist: they move to I34b (BUILD_PLAN row "= I34b"), unweakened. I34
lands after I68 (the structural store, whose key words π permutes) and I33 (its Word lemmas and typed terms), and its
build merges them.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i34.py (J1's families from the facts and the typed model's text, J3's law ids,
J5's eligible pairs, J7's sentinel sites, J8's splits; independently of holon/).

J1 Families. A family is admitted on a model when its sort or role exists there:
   - τ (time translation) over the Time-sorted words: the storage keys the typed model reads as T_Time (on the Rollup,
     batchDataStore's originTimestamp and finalizeTimestamp, challenges' startTime), block.timestamp, and every
     external call answer the model reads as T_Time (IL1MessageQueue.getFirstUnfinalizedMessageEnqueueTime);
   - π (principal permutation within a role) over each role: a principal predicate that reads storage names a role
     (onlyChallenger: challenger, a mapping lookup, kind "set"; onlyOwner: owner, an equality with a scalar, kind
     "singleton"), and so does an address register some action writes with the caller (the submitter role:
     batchDataStore[k].submitter, written with the caller by commitBatch and commitState, kind "set": one value per
     key); a role's members are the addresses its predicate admits in s and the values its registers hold in s, so a
     register that holds address(0) makes address(0) an implicit member (whitepaper §5.4's π instance, O20). A
     singleton role has at most one member, so a π law over it would have unsatisfiable premises (G11V): π is stated
     over the set roles alone, and families.json lists the singleton roles apart;
   - ι (index translation) and μ (unit scaling) need an Idx or an Amt sort, which no M3 model has (I30's sorts are Time,
     Dur, SDur and two digest sorts): both are vacuous on M3, reported with that reason, with no law;
   - ω (reordering), over pairs of actions (J5).
   results/M3/sym/families.json lists each family: admitted or vacuous (with the reason), its Time words or roles.
J2 Generators (g_S on states, g_In on acts; whitepaper §8.3). τ_δ adds the Nat δ to every Time word of J1 (storage
   words at their structural keys, the act's block.timestamp, its Time-sorted arguments and call answers); Dur, SDur and
   every other word are unchanged. π_{a,b} swaps the address words a and b of one role: every structural key word of an
   address-keyed family (isChallenger, batchChallengeReward), every address-typed word equal to a or b (challenges[k]
   .challenger, batchDataStore[k].submitter, _owner), and the act's caller and address arguments. A generator is a
   pure function in the law's section (B2-style statement helpers), never a hand-written table.
J3 Laws (rule SYM; holon-ir/0.3; facts spec/M2/facts/morph_rollup.extracted.json). The term {"sym": ID, "on": [..]}
   (additive in spec/schemas/law_ir_0_3.schema.json, docs/adoption/Q4/ byte-equal; holon.ir.render_term sym_ok[ID](..);
   refs sym:<ID>, the sha256 of the canonical {template, template_version, subform, basis} recomputed from the facts and
   the sort solution) is the law's claim:
   - tau: L_sym_tau_<Contract>_<action>, binders s: Reach, x: Act, d: Nat; premises is[action](x) and fits64(s, x, d)
     (every Time word of s and x plus d is below 2^64); claim sym_ok[ID](s, x, d) == true: step(τ_d s, τ_d x) equals
     τ_d step(s, x) on the storage, the outcome (success or the revert code) and the logs' Time words;
   - pi: L_sym_pi_<Contract>_<action>_<role>, binders s: Reach, x: Act, a: Word, b: Word; premises is[action](x),
     a != b, both members of the role in s (J1); claim sym_ok[ID](s, x, a, b) == true: step(π s, π x) = π step(s, x);
   - omega: L_sym_omega_<Contract>_<a>_<b> (a < b by name), binders s: Reach, x: Act, y: Act; premises is[a](x),
     is[b](y), ok(x, s), ok(y, step(x, s)), ok(y, s), ok(x, step(y, s)) (both orders execute); claim: the two orders'
     storage agrees on every sink-reaching key (J5);
   - sentinel: L_sym_sentinel_<Contract>_<register>_<site>, binders s: Reach, x: Act; premises is[A](x), ok(x, s) and,
     when the site's value reads block.timestamp, block_timestamp(x) >= 1 (on chain no block has timestamp 0; the model
     draws it freely; a law premise, never an axiom, disclosed in the record); claim: the value the site writes is not
     the register's sentinel constant (J7).
   One tau law per action whose statements read or write a Time word, one pi law per (action, set role) where the
   action reads or writes the role's words or is gated by its predicate; no law for a vacuous family or a singleton
   role. τ_d is EVM-faithful: every key of a Time family is translated, a key absent from the store reading d.
J4 Catalog. The lowest catalog version holding SYM holds every rule and producer of the version below it as the same
   objects and adds SYM's four producers (holon.rules.sym: tau, pi, omega, sentinel); M3 derives with it (the next free
   version after the lead's at the build: holon-rules/1.9 is I35's at the prereg); M2 keeps holon-rules/1.0. The bump
   moves every M3 statement hash: catalog_rederivation lines (holon.statement_diff recatalog), bind, and every M3
   record re-made on runners.
J5 ω pairs (whitepaper §5.4's three conditions). An ordered pair of actions (a, b) of the Rollup is eligible when both
   change state, neither is an initializer (a one-shot step of a version, facts modifiers initializer or
   reinitializer, has no reordering within a deployment), they belong to different principal classes (facts
   principal.modifier, null being "anyone"), and some key both write or
   one writes and the other reads reaches a sink (a key a guard of another action or a view's return reads: the
   facts' guards and returns, transitively). Its law is stated; a pair where one order disables the other from some
   reachable state (the second step's checks fail in one order alone) is classified race_disabling in
   results/M3/sym/races.json, with the witness, and is not an ω law's counterexample. The O19 analogue is the pair
   (challengeState, commitBatchWithProof): the commit's finalize time is extended by the challenge in one order alone.
J6 Decision. PROVED: the action's statement chain evaluated on s and on g s over I68's store, g pushed through each
   statement by commutation lemmas (τ commutes with Time + Dur, Time - Time, comparisons of two Time words and the
   checked additions under fits64; π commutes with address equality on words other than a and b and with keyed maps
   under the key swap), with I68's SK frames and I33's Word lemmas; a comparison of a Time word against a constant does
   not commute, and the law is refuted or stays UNKNOWN naming the site. The sentinel laws are proved by a Reach
   induction where the value needs an invariant (I68's S10 shape: the invariant at s0, one step lemma per action).
   REFUTED: a reachable prefix s with x (and d, or a and b, or y) where the sides differ, replayed on the real Rollup:
   tau and pi run x from s and from g s and compare g of the first with the second (two direct tests); omega runs both
   orders. Every proof and counter-law is Bend-accepted; BendTT gives the verdict.
J7 Sentinels (whitepaper §5.4: translation splits localize sentinel conflation, constants compared against Time- or
   Idx-sorted registers). A sentinel register is a Time-sorted register compared against a constant in a guard or a
   view of the facts; no M3 model has an Idx sort, so index sentinels are not admitted on M3. On the Rollup:
   batchDataStore[k].originTimestamp > 0 (batchExist, Rollup.sol:704, inlined at :478 and :630). One sentinel law per
   write site of the register whose value is not the literal sentinel: originTimestamp = block.timestamp in
   commitBatch, commitState, commitBatchWithProof (Rollup.sol:366-371) and importGenesisBatch (:242). A reset to the
   sentinel (revertBatch's delete) is the intended "absent" and has no law. D6's revertReqIndex = 0 is an index
   sentinel (not admitted: no Idx sort; the human's Question Q-S4), and its lastIndex = 0 and messageSendTimestamp > 0
   are the messenger's (I34b).
J8 Splits and promotion (whitepaper §5.4 v2). For each admitted family and role, results/M3/sym/<family>.json lists
   A_eq (PROVED), A_break (REFUTED, each with its witness and the sentinel or principal site it localizes) and
   A_unknown. A split is an obstruction only by route (i) (E1-E4 evidence or an intent contract marking the family as
   intended: I64's machinery, K5) or route (ii) (an auditor adjudicates both "the minority deviates" and "the majority
   deviates"); until then each REFUTED tau or pi law's record has filter_bin "split_pending" (additive in
   result_record_v2) and the split an adjudication request audit/sym_adjudications/<family>_<role or "time">.json
   ({"split", "eq", "break", "hypotheses": ["minority deviates", "majority deviates"], "answer": null}), answered in
   I45. omega and sentinel laws are not splits: their REFUTED records get the filter's usual bins.
J9 Evidence, records, bindings. GEVID enforces on every SYM law (the computed levels over I72's adopted documents); each
   record is a v1 and v2 record over the structural typed model (A-keccak-structural in its model assumptions); spec/
   bindings/M3.json binds every SYM law; G11V needs a checked inhabitant of every premised law; Lean not_run
   (unsupported_form) for the sym term.
J10 Earlier tests amended in this prereg: none. One that fails on I34's outcomes is a miss, reported; the catalog bump's
   statement-hash moves are covered by the earlier keys' m3_catalog() helpers, which admit a later catalog that keeps
   their producers.
J11 Rules. I34 adds SYM laws and no other; changes no other law but in rule_catalog_version (J4); writes no frozen root;
   names no law id, action, register or contract of the target in holon/ (AGENTS rule 2: families, roles, sites and
   pairs come from the facts, the sort solution and the typed model); its outcome paths are laws/M3/L_sym_,
   results/M3/L_sym_, results/M3/sym/, gen/M3/sym/, gen/M3/laws/L_sym_, gen/M3/proofs/L_sym_, audit/sym_adjudications/
   and docs/iterations/I34.md.
J12 I34b. The BUILD_PLAN row "= I34b" (the next free key of the lead's lane) carries O21 and the messenger's sentinels,
   with the prerequisites J1's scope names; this key predicts nothing about them.

Commands
  python -m holon sym --milestone M3 [--check]         J1, J5, J7, J8 (families, pairs, sites, splits, requests)
  python -m holon derive --milestone M3                J3, J4
  python -m holon run --milestone M3 [--laws ID,..]    J6
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, load_json, predictions, validate

M = "M3"
FACTS = "spec/M2/facts/morph_rollup.extracted.json"
SYMDIR = ROOT / "results" / M / "sym"
LAW_IR = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
O20 = "L_sym_pi_Rollup_commitBatchWithProof_submitter"
O20_EQ = ("L_sym_pi_Rollup_commitBatch_submitter", "L_sym_pi_Rollup_commitState_submitter")
O19 = "L_sym_omega_Rollup_challengeState_commitBatchWithProof"
OUTCOME_PATHS = ("laws/M3/L_sym_", "results/M3/L_sym_", "results/M3/sym/", "gen/M3/sym/", "gen/M3/laws/L_sym_",
                 "gen/M3/proofs/L_sym_", "audit/sym_adjudications/", "docs/iterations/I34.md")


def instrument():
    import tests_m3._i34 as I
    return I


def laws_m3() -> dict:
    return {p.stem: load_json(p) for p in sorted((ROOT / "laws" / M).glob("L_sym_*.json"))}


def record(lid: str) -> dict:
    return load_json(ROOT / "results" / M / f"{lid}.json")


def decided_by(rec: dict) -> list:
    return [a for a in rec.get("attempts") or [] if a.get("kind") in ("proof", "counter-law") and "error" not in a
            and a.get("exit_code") == 0]


class TestInstrument(unittest.TestCase):

    def test_the_key_pins_the_instrument(self):
        k = predictions("I34")
        th = k["thresholds"]
        self.assertEqual(th["instrument_sha256"], file_sha256(ROOT / "tests_m3" / "_i34.py"))
        import hashlib
        doc = (ROOT / "tests_m3" / "test_sym.py").read_text(encoding="utf-8").split('"""')[1]
        self.assertEqual(th["contract_docstring_sha256"], hashlib.sha256(doc.encode("utf-8")).hexdigest())
        self.assertEqual(tuple(k["outcome_paths"]), OUTCOME_PATHS)

    def test_the_instrument_reads_the_facts(self):
        """J1, J5 from the facts alone: the roles and the eligible pairs (the O19 analogue among them) the key pins; and,
        once the typed model is I68's structural one (its header names the structural store), J1's Time words, J7's
        sentinel sites and J3's law ids the key pins, computed on I68's model at the prereg."""
        I = instrument()
        facts = load_json(ROOT / FACTS)
        th = predictions("I34")["thresholds"]
        self.assertEqual(I.roles(facts), th["roles"])
        pairs = I.eligible_pairs(facts)
        self.assertIn(("challengeState", "commitBatchWithProof"), pairs)
        self.assertEqual([list(p) for p in pairs], th["omega_pairs"])
        model = (ROOT / I.MODEL).read_text(encoding="utf-8")
        if "structural keys (A-keccak-structural)" in model.split("\n", 6)[3]:
            self.assertEqual(I.time_words(ROOT), th["time_words"])
            self.assertEqual(I.sentinel_sites(facts, ROOT), th["sentinel_sites"])
            self.assertEqual(I.expected_law_ids(ROOT), th["law_ids"])


class TestFamilies(unittest.TestCase):
    """J1, J3: the families, the laws and the schema."""

    def test_families_document(self):
        doc = load_json(SYMDIR / "families.json")
        fam = {f["family"]: f for f in doc["families"]}
        self.assertEqual(sorted(fam), ["iota", "mu", "omega", "pi", "tau"])
        for v in ("iota", "mu"):
            self.assertEqual(fam[v]["status"], "vacuous")
            self.assertTrue(fam[v]["reason"])
        for a in ("tau", "pi", "omega"):
            self.assertEqual(fam[a]["status"], "admitted")
        I = instrument()
        self.assertEqual(sorted(fam["tau"]["time_words"]), I.time_words(ROOT))
        self.assertEqual(sorted(fam["pi"]["roles"]), I.set_roles(load_json(ROOT / FACTS)))
        self.assertEqual(sorted(fam["pi"]["singleton_roles"]),
                         sorted(r for r, k in I.roles(load_json(ROOT / FACTS)) if k == "singleton"))

    def test_law_ids_and_ir(self):
        I = instrument()
        ls = laws_m3()
        self.assertEqual(sorted(ls), I.expected_law_ids(ROOT))
        refs = [e.get("$ref") for e in load_json(LAW_IR)["$defs"]["term"]["oneOf"]]
        self.assertIn("#/$defs/t_sym", refs)
        self.assertEqual((ROOT / "docs/adoption/Q4/schemas/law_ir_0_3.schema.json").read_bytes(), LAW_IR.read_bytes())
        for lid, law in ls.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(law, LAW_IR), [])
                self.assertEqual((law["rule"], law["facts"], law["milestone"]), ("SYM", FACTS, M))
                self.assertIn(law["subform"], ("tau", "pi", "omega", "sentinel"))


class TestPredictions(unittest.TestCase):

    def test_p1_o20_the_pi_split_over_the_submitter_role(self):
        """I34-P1 (O20): L_sym_pi_Rollup_commitBatchWithProof_submitter is REFUTED (the commit writes address(0), an
        implicit member of the submitter role, where the other commits write the caller), Bend-checked and replayed in
        two worlds on the real Rollup; commitBatch's and commitState's submitter laws are PROVED; results/M3/sym/pi.json
        reports the submitter split with break exactly [commitBatchWithProof] and commitBatch and commitState in eq."""
        r = record(O20)
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertTrue(decided_by(r))
        self.assertEqual((r.get("replay") or {}).get("status"), "passed")
        for lid in O20_EQ:
            self.assertEqual(record(lid)["status"], "PROVED", lid)
        sp = {s["role"]: s for s in load_json(SYMDIR / "pi.json")["splits"]}["submitter"]
        self.assertEqual(sp["break"], ["commitBatchWithProof"])
        self.assertTrue({"commitBatch", "commitState"} <= set(sp["eq"]), sp)

    def test_p2_o19_analogue_reorder_refuted(self):
        """I34-P2 (the O19 analogue, BUILD_PLAN's regression, counted here as the key's ω claim):
        L_sym_omega_Rollup_challengeState_commitBatchWithProof is REFUTED, both orders executed from a reachable prefix
        and replayed on the real Rollup."""
        r = record(O19)
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertTrue(decided_by(r))
        self.assertEqual((r.get("replay") or {}).get("status"), "passed")

    def test_p3_d6_rollup_sentinels_proved(self):
        """I34-P3 (D6, the Rollup's Time sentinel): every sentinel law (J7: the four originTimestamp write sites) is PROVED
        in both kernels (bend accepted, BendTT checked), each premised law with a checked inhabitant."""
        I = instrument()
        ids = [l for l in I.expected_law_ids(ROOT) if l.startswith("L_sym_sentinel_")]
        self.assertTrue(ids)
        for lid in ids:
            r = record(lid)
            with self.subTest(law=lid):
                self.assertEqual(r["status"], "PROVED", r.get("attempts"))
                self.assertEqual((r.get("kernel") or {}).get("verdict"), "checked")
                self.assertEqual((r.get("non_vacuity") or {}).get("status"), "inhabited")

    def test_p4_no_split_is_promoted_without_a_route(self):
        """I34-P4: every REFUTED tau or pi record carries filter_bin split_pending unless a route promotes it (route (i): a
        proved intent contract marking the family; route (ii): an answered adjudication), and every split with a
        REFUTED member has its adjudication request (J8)."""
        reqs = {p.stem: load_json(p) for p in sorted((ROOT / "audit" / "sym_adjudications").glob("*.json"))}
        for lid in laws_m3():
            r = record(lid)
            if r["status"] == "REFUTED" and r.get("subform") in ("tau", "pi"):
                with self.subTest(law=lid):
                    if r.get("filter_bin") != "split_pending":
                        self.assertIn(r.get("filter_bin"), ("intended_bounded",) if r.get("intended") else ())
        for fam in ("tau", "pi"):
            for sp in load_json(SYMDIR / f"{fam}.json")["splits"]:
                if sp["break"]:
                    key = f"{fam}_{sp.get('role') or 'time'}"
                    self.assertIn(key, reqs)
                    self.assertEqual(reqs[key]["hypotheses"], ["minority deviates", "majority deviates"])

    def test_p5_tau_splits_localize_sentinels(self):
        """I34-P5: every REFUTED tau law's record names, in its sym block, the sentinel site its witness crosses (a
        comparison of a Time word against a constant), and each such site is one of the instrument's sentinel sites or
        a Time comparison the instrument lists (tests_m3/_i34.time_constant_compares)."""
        I = instrument()
        sites = set(I.time_constant_compares(load_json(ROOT / FACTS)))
        for lid, law in laws_m3().items():
            if law["subform"] != "tau":
                continue
            r = record(lid)
            if r["status"] == "REFUTED":
                with self.subTest(law=lid):
                    self.assertIn((r.get("sym") or {}).get("site"), sites)

    def test_p6_races_are_classified_apart(self):
        """I34-P6 (recorded, not counted: which pairs race is not known at the prereg): results/M3/sym/races.json lists
        each race_disabling pair with its witness, and no race is an ω law's counterexample."""
        races = load_json(SYMDIR / "races.json")["races"]
        omega_refuted = {lid for lid, l in laws_m3().items() if l["subform"] == "omega" and record(lid)["status"] ==
                         "REFUTED"}
        for rc in races:
            self.assertIn("witness", rc)
            self.assertNotIn(rc.get("law_id"), omega_refuted)


class TestRegressions(unittest.TestCase):

    def test_r1_catalog_keeps_every_producer(self):
        """I34-R1 (J4): M3's catalog holds every rule and producer of the version below the lowest one holding SYM, as the
        same objects, and SYM's four producers; M2 keeps holon-rules/1.0."""
        from holon import rules as RU
        cv = RU.catalog_version(M)
        cat = RU.CATALOGS[cv]
        self.assertEqual(sorted(cat["SYM"]), ["omega", "pi", "sentinel", "tau"])
        versions = sorted(RU.CATALOGS, key=lambda v: [int(x) for x in v.split("/")[1].split(".")])
        first = next(v for v in versions if "SYM" in RU.CATALOGS[v])
        below = versions[versions.index(first) - 1]
        for rule, subs in RU.CATALOGS[below].items():
            for sub, prod in subs.items():
                self.assertIs(RU.CATALOGS[first][rule][sub], prod, (rule, sub))
        self.assertEqual(RU.catalog_version("M2"), "holon-rules/1.0")

    def test_r2_holon_names_no_target_id(self):
        """I34-R2 (J11): no file of holon/ that I34 adds or changes names a law id of I34 or a target action or register
        it states SYM over."""
        pat = re.compile(r"L_sym_(tau|pi|omega|sentinel)_|commitBatchWithProof_submitter|revertReqIndex")
        for p in sorted((ROOT / "holon").rglob("*.py")):
            if "sym" in p.name:
                self.assertIsNone(pat.search(p.read_text(encoding="utf-8")), p)


if __name__ == "__main__":
    unittest.main()
