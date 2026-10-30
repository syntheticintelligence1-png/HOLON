"""I24 outcomes: the planted fixtures decided as test milestone T24, the M3 Morph PAR laws decided by holon run, the
back-test against M0 across documents and the partial M3 gate. The contract is the docstring of
tests_m3/test_derive_par.py; the instruments are tests_m3/_i24.py, tests_m3/_i24x.py, tests_m3/fixtures/ and the
sidecars spec/M3/lib/par_basis.json and spec/M3/lib/backtest_map.json.

Witness formats read here (those of I12/I15 records and rule X9): a codec law's witness is {binder: {field: "0x.."}}
(a record) or {binder: "0x.."} (bytes); a machine law's is {"s": {"run": [action, ..]}, "a": action, ..}, an action
being {"op": name, <input>: value, ..}.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i24 as I
from tests_m3 import _i24x as X
from tests_m3._m3 import (ROOT, SCHEMAS, copy_repo, file_sha256, holon_module, laws, load_json, records, run_bend,
                          run_holon, validate)
from tests_m3.test_derive_par import (CODEC_DOC, COMPONENT, FIXTURE_LAWS, FIXTURES, LINKED_FX, LINKED_LAWS,
                                      fixture_assignment, write_codecs)

V1 = ROOT / "schemas" / "result_record.schema.json"
V2 = SCHEMAS / "result_record_v2.schema.json"
LAWS3 = ROOT / "laws" / "M3"
BACKTEST = ROOT / "results" / "M3" / "backtest.json"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "par_basis.json"
MAP = ROOT / "spec" / "M3" / "lib" / "backtest_map.json"

# I24-P3: the facts fixtures' outcomes
FIXTURE_STATUS = {
    "L_par_rt_enc_rt_sol_dec_rt_v0": "REFUTED", "L_par_rt_enc_rt_sol_dec_rt_v0_pinned": "PROVED",
    "L_par_cc_enc_cc_go_enc_cc_sol_v0": "REFUTED", "L_par_cc_enc_cc_go_enc_cc_sol_v0_pinned": "PROVED",
    "L_par_rt_enc_cc_go_dec_cc_v0": "PROVED", "L_par_rt_enc_cc_sol_dec_cc_v0": "REFUTED",
    "L_par_rt_enc_cc_sol_dec_cc_v0_pinned": "PROVED",
    "L_par_br_enc_br_fast_enc_br_slow_v1": "REFUTED",
    "L_par_weak_enc_wk_go_enc_wk_sol_v0": "REFUTED",
    "L_par_dom_ok_dm_go_ok_dm_sol": "REFUTED",
    "L_par_tot_dec_tt": "REFUTED",
    "L_par_cy_dec_cy_sol": "REFUTED",
    "L_par_rc_reput_put_enc_held": "REFUTED",
    "L_par_cs_feed_post_dig_com1": "PROVED", "L_par_cs_feed_post_dig_com2": "REFUTED",
    "L_par_init_pop_g0": "REFUTED", "L_par_init_sync_g0": "PROVED",
}
# I24-P3: the linked fixture's outcomes (getter B rejects length 9 at version 2; RecV1.Bytes writes 0xff at byte 6
# where enc_x writes 0; RecV0.Bytes writes C where enc_x writes zeros; at version 2 Root decodes length 9 and RootNew
# length 11 only; Solidity's loader accepts length >= 7 at version 0, Go's predicate exactly 7)
LINKED_STATUS = {**{lid: "PROVED" for lid in LINKED_LAWS["round_trip"]},
                 "L_par_rt_enc_x_HdrBytes_B_v2": "REFUTED", "L_par_rt_Cache_makeV2_HdrBytes_B_v2": "REFUTED",
                 "L_par_cc_RecV0_Bytes_enc_x_v0": "REFUTED", "L_par_cc_RecV0_Bytes_enc_x_v0_pinned": "PROVED",
                 "L_par_cc_RecV1_Bytes_enc_x_v1": "REFUTED", "L_par_cc_RecV1_Bytes_enc_x_v1_pinned": "REFUTED",
                 "L_par_cc_Cache_makeV2_enc_x_v2": "REFUTED", "L_par_cc_Cache_makeV2_enc_x_v2_pinned": "REFUTED",
                 "L_par_weak_HdrBytes_Root_HdrBytes_RootNew_v2": "REFUTED",
                 "L_par_dom_HdrBytes_validate_ok_load_x": "REFUTED"}
# I24-P6: the back-test across documents
PAIRS = {"L_dom_hdr": ("L_par_dom_BatchHeaderBytes_validate_ok_load_sol", "witness"),
         "L_par_hdr_ssvh": ("L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1", "bridges"),
         "L_par_hdr_v0": ("L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned", "bridges"),
         "L_par_hdr_v1": ("L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned", "bridges")}
RULE_GAPS = ["L_par_hdr_v2", "L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2"]
PATCH = "BatchCache_createBatchHeaderWithSequencerSetHash"


def _bytes(x) -> bytes:
    return bytes.fromhex(x[2:]) if isinstance(x, str) and x.startswith("0x") else b""


def _field(w: dict, suffix: str) -> bytes:
    """A record witness's field by its name or its last path segment."""
    hits = [v for k, v in w.items() if k == suffix or k.rsplit(".", 1)[-1] == suffix]
    if len(hits) != 1:
        raise AssertionError(f"{suffix} is not one field of the witness {sorted(w)}")
    return _bytes(hits[0])


def par_records() -> dict:
    """The records of the PAR laws but those of sub-form init_chain (amended at the I28 prereg, spec/M3/amendments.jsonl:
    I28 adds a PAR law of the sub-form init_chain over the versioned document, which I24's outcome checks never
    covered), those over a Go-op document (amended at the I67 prereg: I67's laws over gen/M3/goops/) and those of the
    sub-form push (amended at I86's build: I86's PAR law over a bundle member's document)."""
    ls = laws("M3")
    return {k: v for k, v in records("M3").items()
            if ls.get(k, {}).get("rule") == "PAR" and ls.get(k, {}).get("subform") not in ("init_chain", "push")
            and not str(ls.get(k, {}).get("facts") or "").startswith("gen/M3/goops/")}


# ---------------------------------------------------------------------------------------------- fixtures (run)
class TestFixtureOutcomes(unittest.TestCase):
    """I24-P3: every sub-form generator produces its fixture law, and each fixture law decides as designed. The ten
    facts fixtures and the linked fixture are derived as test milestone T24 under catalog holon-rules/1.1 and run with
    holon run, in a copy."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        tmp = cls.repo.parent
        rels = list(FIXTURES.values())
        asg = fixture_assignment(tmp, rels, cwd=cls.repo)
        c = write_codecs(cls.repo, "T24", LINKED_FX["adoption"], LINKED_FX["link"])
        args = ["derive", "--milestone", "T24", "--catalog", "holon-rules/1.1", "--assignment", str(asg),
                "--root", str(cls.repo), "--out", str(cls.repo / "laws" / "T24"), "--obstructions",
                str(tmp / "obstructions.json"), "--codec", f"gen/T24/codec/{LINKED_FX['role']}.json"]
        for r in rels:
            args += ["--facts", r]
        a = run_holon(args, cwd=cls.repo) if c.returncode == 0 else c
        b = run_holon(["run", "--milestone", "T24", "--out", str(tmp / "results"), "--gen-dir", str(tmp / "gen")],
                      cwd=cls.repo, timeout=3600) if a.returncode == 0 else a
        cls.log = "\n".join(x.stdout[-3000:] + x.stderr[-3000:] for x in (c, a, b))
        cls.codes = (c.returncode, a.returncode, b.returncode)
        cls.recs = {p.stem: load_json(p) for p in sorted((tmp / "results").glob("L*.json"))}
        cls.asg = load_json(asg) if asg.exists() else {}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def _check(self, want: dict) -> dict:
        self.assertEqual(self.codes, (0, 0, 0), self.log)
        got = {lid: self.recs[lid]["status"] for lid in want if lid in self.recs}
        self.assertEqual(got, want, self.log[-2000:])
        for lid, st in want.items():
            r = self.recs[lid]
            self.assertEqual(validate(r, V1), [], lid)
            self.assertEqual(validate(r, V2), [], lid)
            self.assertEqual(r["checker"]["marker"], "ALL PROOFS CHECK", f"{lid}: the proof or counter-law checks")
            law = load_json(self.repo / "laws" / "T24" / f"{lid}.json")
            if st == "REFUTED" and law["statement"]["binders"]:
                self.assertTrue(isinstance(r["witness"], dict) and r["witness"], f"{lid}: no witness")
            if st == "PROVED" and r.get("premises"):
                self.assertEqual(r["non_vacuity"]["status"], "inhabited", f"{lid}: {r['non_vacuity']}")
        return {lid: self.recs[lid] for lid in want}

    def _fixture(self, fx: str) -> dict:
        return self._check({lid: FIXTURE_STATUS[lid] for lid in FIXTURE_LAWS[fx]})

    def test_round_trip_fixture(self):
        """The Solidity-style encoder stores b as zero: the full round trip is REFUTED by a header with b != 0, the
        pinned one (b = 0x0000) PROVED."""
        r = self._fixture("round_trip")
        self.assertNotEqual(_bytes(r["L_par_rt_enc_rt_sol_dec_rt_v0"]["witness"]["h"]["b"]), b"\x00\x00")

    def test_cross_component_fixture(self):
        """The Go encoder writes b, the Solidity one zeros: the full agreement is REFUTED by b != 0, the pinned one
        PROVED; the Go round trip is PROVED (the constant version byte is the version premise)."""
        r = self._fixture("cross_component")
        self.assertNotEqual(_bytes(r["L_par_cc_enc_cc_go_enc_cc_sol_v0"]["witness"]["h"]["b"]), b"\x00\x00")

    def test_branch_fixture(self):
        """The fast path omits b: REFUTED by b != 0."""
        r = self._fixture("branch")
        self.assertNotEqual(_bytes(r["L_par_br_enc_br_fast_enc_br_slow_v1"]["witness"]["h"]["b"]), b"\x00\x00")

    def test_weak_fixture(self):
        """The two encoders swap a and b: REFUTED by a != b, and, its only evidence being E6, an intent question
        (law_evidence over the fixture's evidence set: levels [E6], evidence_triage intent_question)."""
        r = self._fixture("weak")
        w = r["L_par_weak_enc_wk_go_enc_wk_sol_v0"]["witness"]["h"]
        self.assertNotEqual(_bytes(w["a"]), _bytes(w["b"]))
        EV = holon_module("holon.diagram.evidence")
        ev = I.evidence_of([ROOT / FIXTURES["weak"]], self.asg)
        law = load_json(self.repo / "laws" / "T24" / "L_par_weak_enc_wk_go_enc_wk_sol_v0.json")
        le = EV.law_evidence(law, ev)
        self.assertEqual((le["levels"], EV.evidence_triage("REFUTED", le["max"])), (["E6"], "intent_question"))

    def test_domain_fixture(self):
        """Go requires length 5 at version 0, Solidity length >= 5: REFUTED by a byte string of version 0 and length
        > 5."""
        r = self._fixture("domain")
        b = _bytes(r["L_par_dom_ok_dm_go_ok_dm_sol"]["witness"]["b"])
        self.assertTrue(len(b) > 5 and b[0] == 0, b.hex())

    def test_totality_fixture(self):
        """The decoder's validity check fails on some byte string of R^ext: REFUTED (the O4 class)."""
        self._fixture("totality")

    def test_cycle_fixture(self):
        """The Solidity decoder reads b one byte early; no evidence atom relates the two decoders, the fundamental cycle
        does: REFUTED."""
        r = self._fixture("cycle")
        b = _bytes(r["L_par_cy_dec_cy_sol"]["witness"]["b"])
        self.assertTrue(len(b) == 5 and b[0] == 0 and b[2:4] != b[3:5], b.hex())

    def test_recompute_fixture(self):
        """reput keeps a held value: REFUTED from a state where held != 0 and differs from enc(v) of the reput's own
        input (K = 7). (put stores the very enc(v) call reput recomputes: that candidate is reflexive and gives no law,
        rule P0.)"""
        r = self._fixture("recompute")
        w = r["L_par_rc_reput_put_enc_held"]["witness"]
        self.assertEqual(w["a"]["op"], "reput")
        held = 0
        for x in w["s"]["run"]:
            held = x["v"] + 7 if (x["op"] == "put" or held == 0) else held
        self.assertTrue(held != 0 and held != w["a"]["v"] + 7, w)

    def test_consumer_fixture(self):
        """com1 commits dig(data): PROVED; com2 keeps its value when keep is set: REFUTED through post with keep."""
        r = self._fixture("consumer")
        w = r["L_par_cs_feed_post_dig_com2"]["witness"]
        self.assertEqual((w["a"]["op"], w["a"]["keep"]), ("post", True))

    def test_init_fixture(self):
        """S0 sets pend = 3, tot = 0, a = b = 1: pend == tot (pop) is REFUTED at S0, a == b (sync) PROVED; fin's
        equation mentions its input (no law)."""
        self._fixture("init")

    def test_linked_fixture(self):
        """The linked fixture (rules X1-X9): 18 round trips PROVED and 2 REFUTED (Go getter B rejects the 9-byte
        version-2 header); RecV0 against enc_x REFUTED by C != 0 and PROVED pinned (C = 0x0000); RecV1 and the patch
        against enc_x REFUTED even pinned (byte 6: 0xff against 0); the PAR-weak law of Root and RootNew, scoped to their
        one common version 2 by the tag premise HdrBytes_Version(b) = Some(0x02) (rule X8c), REFUTED by a version-2
        byte string of length 9 or 11 (Root decodes length 9 there, RootNew length 11) and an intent question (E6
        only); the domain law REFUTED by a version-0 byte string of length >= 8."""
        r = self._check(LINKED_STATUS)
        self.assertNotEqual(_field(r["L_par_cc_RecV0_Bytes_enc_x_v0"]["witness"]["h"], "C"), b"\x00\x00")
        w = r["L_par_cc_RecV1_Bytes_enc_x_v1_pinned"]["witness"]
        self.assertNotEqual(_field(w["k"], "a"), b"\x00\x00", "the witness reaches enc_x's store (a != 0, rule X9)")
        b = _bytes(r["L_par_weak_HdrBytes_Root_HdrBytes_RootNew_v2"]["witness"]["b"])
        self.assertTrue(b and b[0] == 2 and len(b) in (9, 11), b.hex())
        b = _bytes(r["L_par_dom_HdrBytes_validate_ok_load_x"]["witness"]["b"])
        self.assertTrue(len(b) >= 8 and b[0] == 0, b.hex())
        self.assertEqual(r["L_par_weak_HdrBytes_Root_HdrBytes_RootNew_v2"]["evidence_triage"], "intent_question")


# ---------------------------------------------------------------------------------------------- Morph outcomes
class TestMorphOutcomes(unittest.TestCase):
    def test_round_trips_are_proved(self):
        """I24-P4 (round trips): all 70 round-trip laws are PROVED: every BatchHeaderBytes getter accepts the length and
        version byte each encoder writes (249 at version 0, 257 at 1 and 2) and reads the field it recovers."""
        recs = par_records()
        sc = load_json(SIDECAR)["components"][COMPONENT]["laws"]
        rts = sorted(l for l, x in sc.items() if x["subform"] == "round_trip")
        self.assertEqual(len(rts), 70)
        self.assertEqual({l: recs[l]["status"] for l in rts if l in recs}, {l: "PROVED" for l in rts})

    def test_cross_component_laws(self):
        """I24-P4 (cross-component): the three unpinned laws are REFUTED, each by a Go header whose
        SequencerSetVerifyHash is nonzero (enc_sol writes 32 zero bytes at 185..216) and a Solidity header of the law's
        version that enc_sol stores (prevStateHash and postStateHash nonzero, rule X9); the three pinned laws are PROVED,
        among them the version-2 law of the patch (the V1 layout with byte 0 patched to 2): the extraction's version-2
        Go encoding agrees with enc_sol, where M0's L_par_hdr_v2 (hand enc_go_v1, writing 1) is REFUTED (O2)."""
        recs = par_records()
        for enc, v in (("BatchHeaderV0_Bytes", 0), ("BatchHeaderV1_Bytes", 1), (PATCH, 2)):
            full, pinned = f"L_par_cc_{enc}_enc_sol_v{v}", f"L_par_cc_{enc}_enc_sol_v{v}_pinned"
            with self.subTest(law=full):
                self.assertEqual((recs[full]["status"], recs[pinned]["status"]), ("REFUTED", "PROVED"))
                w = recs[full]["witness"]
                self.assertNotEqual(_field(w["h"], "SequencerSetVerifyHash"), bytes(32))
                self.assertEqual(_field(w["k"], "version"), bytes([v]))
                self.assertNotEqual(_field(w["k"], "prevStateHash"), bytes(32))
                self.assertNotEqual(_field(w["k"], "postStateHash"), bytes(32))
                self.assertEqual(recs[pinned]["non_vacuity"]["status"], "inhabited")

    def test_byte_string_laws(self):
        """I24-P5: L_par_dom_BatchHeaderBytes_validate_ok_load_sol is REFUTED by a byte string whose byte 0 is 0 and
        whose length exceeds 249 (O1: Solidity accepts length >= 249 at version 0, Go exactly 249). The three PAR-weak
        laws, each scoped to a common version by the tag premise (rule X8c), are UNKNOWN: at that version both getters
        accept exactly the same (length, tag) pairs and read the same bytes 57..88 (BlobCommitHash and BlobHashesHash at
        version 2: length 257; BlobCommitHash and BlobVersionedHash at version 0: length 249, at version 1: length 257),
        so no probe refutes them, and a byte-string law has no proof route (gap G6). Their records say so: status
        UNKNOWN, a non-empty bound, no witness. (Unscoped, both pairs would be REFUTED by a header of a version outside
        one getter's label; that is the widening rule X8c rules out.)"""
        recs = par_records()
        b = _bytes(recs["L_par_dom_BatchHeaderBytes_validate_ok_load_sol"]["witness"]["b"])
        self.assertTrue(b and b[0] == 0 and len(b) > 249, (len(b), b[:1].hex()))
        self.assertEqual(recs["L_par_dom_BatchHeaderBytes_validate_ok_load_sol"]["status"], "REFUTED")
        weak = "L_par_weak_BatchHeaderBytes_BlobCommitHash_BatchHeaderBytes_Blob"
        for lid in (f"{weak}HashesHash_v2", f"{weak}VersionedHash_v0", f"{weak}VersionedHash_v1"):
            with self.subTest(law=lid):
                r = recs[lid]
                self.assertEqual(r["status"], "UNKNOWN")
                self.assertTrue(isinstance(r.get("bound"), str) and r["bound"].strip(), "UNKNOWN names its bound")
                self.assertFalse(r.get("witness"), "an UNKNOWN law has no witness")

    def test_evidence_triage_of_the_m3_records(self):
        """I24-P7: every M3 PAR record carries the status, levels and triage spec/M3/lib/par_basis.json lists (levels
        as law_evidence computes them over gen/M3/evidence.json: round trips [E1, E2], cross-component [E1], PAR-weak
        [E6], domain coherence []): 73 PROVED, 4 REFUTED, 3 UNKNOWN; the REFUTED laws are 4 findings (the 3 unpinned
        cross-component laws and the domain law) and there is no intent question (the E6-only laws are UNKNOWN, I24-P5);
        evidence_triage counts none 76, finding 4."""
        recs = par_records()
        sc = load_json(SIDECAR)["components"][COMPONENT]["laws"]
        self.assertEqual(sorted(recs), sorted(sc))
        for lid, r in recs.items():
            with self.subTest(law=lid):
                self.assertEqual((r["status"], r["evidence_levels"], r["evidence_triage"]),
                                 (sc[lid]["status"], sc[lid]["levels"], sc[lid]["triage"]))
        tri, st = {}, {}
        for x in sc.values():
            tri[x["triage"]] = tri.get(x["triage"], 0) + 1
            st[x["status"]] = st.get(x["status"], 0) + 1
        self.assertEqual(tri, {"none": 76, "finding": 4})
        self.assertEqual(st, {"PROVED": 73, "REFUTED": 4, "UNKNOWN": 3})
        self.assertEqual(sorted({tuple(x["levels"]) for x in sc.values() if x["subform"] == "weak"}), [("E6",)])


# ---------------------------------------------------------------------------------------------- back-test
class TestBacktest(unittest.TestCase):
    def test_backtest_table(self):
        """I24-P6: rules B1-B5 pair 4 of the 8 M0 laws with M3 laws and accept each pairing: L_par_hdr_v0, L_par_hdr_v1
        and L_par_hdr_ssvh by bridges (the hand encoders equal their extracted images, Bend-checked), L_dom_hdr by
        witness transfer (both REFUTED; the M3 witness refutes the M0 law on the hand model; its predicate bridges are
        UNKNOWN over unbounded byte strings). L_par_hdr_v2, L_rt_go_v0, L_rt_go_v1 and L_rt_go_v2 are open rule gaps
        (G5). The table is complete and its exit_blockers are exactly the four rule gaps."""
        bt = load_json(BACKTEST)
        self.assertEqual((bt["document"], bt["milestone"], bt["against"]), ("backtest", "M3", "M0"))
        self.assertEqual(bt["map"], {"path": "spec/M3/lib/backtest_map.json", "sha256": file_sha256(MAP)})
        rows = {r["old"]: r for r in bt["rows"]}
        self.assertEqual(sorted(rows), sorted(laws("M0")))
        exp = {r["old"]: r for r in X.backtest_expected(ROOT)["rows"]}
        for old, (new, acc) in PAIRS.items():
            with self.subTest(m0=old):
                r = rows[old]
                self.assertEqual((r["new"], r["acceptance"], r["implication"], r["gap"]), (new, acc, "accepted", None))
                self.assertEqual(sorted((b["fn"], b["image"], b["status"]) for b in r["bridges"]),
                                 sorted(tuple(b) for b in exp[old]["bridges"]))
        gaps = {g["law"]: g for g in bt["gaps"]}
        self.assertEqual(sorted(gaps), RULE_GAPS)
        want = {g["law"]: g for g in X.backtest_expected(ROOT)["gaps"]}
        for law in RULE_GAPS:
            with self.subTest(gap=law):
                g = gaps[law]
                self.assertEqual((g["id"], g["milestone"], g["kind"], g["status"]), (f"gap:M0:{law}", "M0", "rule", "open"))
                self.assertTrue(g["reason"].strip())
                self.assertEqual(g["candidates"], want[law]["candidates"])
                self.assertEqual((rows[law]["new"], rows[law]["gap"]), (None, f"gap:M0:{law}"))
        self.assertEqual(gaps["L_par_hdr_v2"]["candidates"],
                         ["L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1", "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned"])
        self.assertTrue(bt["complete"])
        self.assertEqual(bt["exit_blockers"], [f"gap:M0:{law}" for law in RULE_GAPS],
                         "M3 exit cannot be claimed with a gap open")

    def test_matched_m0_outcomes_are_identical(self):
        """I24-R3: every paired M3 law has its M0 law's status (L_par_hdr_v0, L_par_hdr_v1 PROVED; L_par_hdr_ssvh,
        L_dom_hdr REFUTED)."""
        r0, r3 = records("M0"), records("M3")
        for old, (new, _) in PAIRS.items():
            with self.subTest(m0=old):
                self.assertEqual(r3[new]["status"], r0[old]["status"])
        for r in load_json(BACKTEST)["rows"]:
            if r["new"]:
                self.assertEqual((r["old_status"], r["new_status"], r["same_status"]),
                                 (r0[r["old"]]["status"], r3[r["new"]]["status"], True))

    def test_bridges_and_witness_transfers_check(self):
        """Construction (B3, B4): every PROVED bridge's law and proof, and every witness transfer's counter-law, under
        gen/M3/backtest/ is accepted by Bend and states the expected law (no escape hatch)."""
        bt = load_json(BACKTEST)
        n = 0
        for r in bt["rows"]:
            dirs = [b["law"] for b in r["bridges"] if b["status"] == "PROVED"]
            if r["acceptance"] == "witness":
                dirs.append(f"W_{r['old']}")
            for d in dirs:
                n += 1
                with self.subTest(dir=d):
                    base = ROOT / "gen" / "M3" / "backtest" / d
                    text = (base / "LAWS.bend").read_text() + (base / "PROOF.bend").read_text()
                    for hatch in ("?TODO", "@unsafe", "import \"", "def f?"):
                        self.assertNotIn(hatch, text)
                    code, out = run_bend([str(base / "PROOF.bend")], cwd=base)
                    self.assertEqual((code, "ALL PROOFS CHECK" in out), (0, True), out[-2000:])
        self.assertEqual(n, 7, "6 encoder bridges and 1 witness transfer")

    def test_backtest_cli_reproduces_the_table(self):
        """Construction: python -m holon backtest --milestone M3 rewrites results/M3/backtest.json byte for byte."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-backtest-"))
        try:
            p = run_holon(["backtest", "--milestone", "M3", "--out", str(tmp / "backtest.json")])
            self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertEqual((tmp / "backtest.json").read_bytes(), BACKTEST.read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- M3 records, gate
class TestM3Construction(unittest.TestCase):
    def test_every_m3_law_has_a_valid_record(self):
        # the PAR laws but those of sub-form init_chain (amended at the I28 prereg, spec/M3/amendments.jsonl, as par_records)
        # and those over a Go-op document (amended at the I67 prereg, as par_records), and those of the sub-form push
        # (amended at I86's build, as par_records)
        ls = {k: v for k, v in laws("M3").items() if v.get("rule") == "PAR"
              and v.get("subform") not in ("init_chain", "push")
              and not str(v.get("facts") or "").startswith("gen/M3/goops/")}
        recs = par_records()
        reg = load_json(LAWS3 / "REGISTRY.json")
        self.assertTrue(ls, "laws/M3 holds no PAR law")
        self.assertEqual(sorted(recs), sorted(ls))
        for lid, r in recs.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(r, V1), [])
                self.assertEqual(validate(r, V2), [])
                self.assertEqual(r["statement_hash"], reg["statements"][lid])
                self.assertIn(r["status"], ("PROVED", "REFUTED", "UNKNOWN"))
                if r["status"] in ("PROVED", "REFUTED"):
                    self.assertEqual(r["checker"]["marker"], "ALL PROOFS CHECK")

    def test_proved_premised_laws_are_not_vacuous(self):
        """Construction (G11V, §12.3 L21): every PROVED M3 PAR law with premises has an inhabitant of its premises: the
        35 enc_sol round trips (premise version = v) and the 3 pinned cross-component laws."""
        n = 0
        for lid, r in par_records().items():
            if r["status"] == "PROVED" and r.get("premises"):
                n += 1
                with self.subTest(law=lid):
                    self.assertEqual(r["non_vacuity"]["status"], "inhabited", r["non_vacuity"])
                    self.assertEqual(r["non_vacuity"]["parent_statement_hash"], r["statement_hash"])
        self.assertEqual(n, 38)

    def test_statement_refs_follow_the_functions_named(self):
        """Construction (statement hashes over a linked codec document): editing a layout cell of BatchHeaderV1_Bytes
        restales exactly the 14 laws naming it (its 12 round trips and 2 cross-component laws, not the patch's); editing
        its "source" restales none."""
        R = holon_module("holon.gen.refs")
        doc = load_json(ROOT / CODEC_DOC)
        ls = {lid: law for lid, law in laws("M3").items() if law.get("facts") == CODEC_DOC and law.get("rule") == "PAR"}
        self.assertEqual(len(ls), 80)
        base = {lid: R.law_hash(law, doc) for lid, law in ls.items()}
        d2 = json.loads(json.dumps(doc))
        d2["functions"]["BatchHeaderV1_Bytes"]["source"] = "(edited).Text"
        self.assertEqual({lid: R.law_hash(law, d2) for lid, law in ls.items()}, base, "provenance is not hashed")
        d3 = json.loads(json.dumps(doc))
        lay = d3["functions"]["BatchHeaderV1_Bytes"]["layouts"]["1"]
        lay[100] = ["const", 7]
        changed = sorted(lid for lid, law in ls.items() if R.law_hash(law, d3) != base[lid])
        self.assertEqual(len(changed), 14)
        self.assertTrue(all("BatchHeaderV1_Bytes" in lid for lid in changed), changed)

    def test_partial_gate_m3_passes(self):
        """Construction: holon gate --milestone M3 --checks G2,G3,G5,G9,G11,GEVID passes on a copy of the tree."""
        repo = copy_repo()
        try:
            rep = repo.parent / "gate_report.json"
            p = run_holon(["gate", "--milestone", "M3", "--root", str(repo), "--report", str(rep),
                           "--checks", "G2,G3,G5,G9,G11,GEVID"], cwd=repo, timeout=3600)
            report = load_json(rep) if rep.exists() else {}
            self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
            for c in ("G2", "G3", "G5", "G9", "G11", "GEVID"):
                self.assertTrue(report["checks"][c]["passed"], f"{c}: {report['checks'][c]}")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)
