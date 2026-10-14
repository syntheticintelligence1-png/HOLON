"""I42 tests: Theory core I (whiskering, domain locality, spanning-tree basis sufficiency).

Verifies:
1. Preregistration instruments (`tests_m3/_i42.py` and `spec/M3/lib/theory_core_i.json`):
   - deterministic reproduction of `spec/M3/lib/theory_core_i.json` from frozen inputs;
   - input SHA-256 integrity;
   - spanning-tree cycle-basis decomposition of `gen/M2/diagram/morph_header.json` (rank 2)
     and `gen/M3/diagram/header_length.json` (rank 4);
   - prototype verification of the 12 `THEORY_CORE_I` laws and 7 negative canaries under
     both `bend` (`holon.bend.check`) and `bend --verdict` (`holon.bend.check_verdict`).
2. Build outputs (Step 2):
   - `THEORY_CORE_I` (12 polymorphic laws) in `holon/gen/core.py` and emitted into
     `gen/M3/core/{LAWS,PROOF}.bend` while preserving `gen/M2/core/{LAWS,PROOF}.bend` untouched;
   - `gen/M3/basis/header/{LAWS,PROOF}.bend` (3 spanning-tree basis laws for M2 `header`);
   - `gen/M3/basis/header_length/{LAWS,PROOF}.bend` (5 spanning-tree basis laws for M3 `header_length`);
   - `gen/M3/basis/congruence/{LAWS,PROOF}.bend` (34 congruence-derived round-trip laws:
     2 M0 + 32 M3, proved via `core_whisker_post` without `match` or record unpacking,
     strictly shorter than the 34 baseline `open_refl` proofs);
   - 7 negative canaries rejected by both `bend` and `bend --verdict`;
   - `results/M3/basis.json` deterministic verification sidecar.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from holon import bend
from tests_m3 import _i42
from tests_m3._m3 import ROOT, canonical_json, file_sha256 as sha256_file, holon_module, load_json

SPEC_PATH = ROOT / "spec/M3/lib/theory_core_i.json"
M2_CORE_DIR = ROOT / "gen/M2/core"
M3_CORE_DIR = ROOT / "gen/M3/core"
BASIS_DIR = ROOT / "gen/M3/basis"
RESULTS_PATH = ROOT / "results/M3/basis.json"


def _assert_no_escape_hatches(tc: unittest.TestCase, path: Path) -> str:
    tc.assertTrue(path.is_file(), f"missing generated file: {path}")
    txt = path.read_text()
    tc.assertNotIn("?TODO", txt, f"escape hatch ?TODO in {path}")
    tc.assertNotIn("@unsafe", txt, f"escape hatch @unsafe in {path}")
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("#"):
            continue
        tc.assertNotIn("?", s, f"hole ? in non-comment line of {path}: {s}")
    return txt


def _assert_bend_proved(tc: unittest.TestCase, laws_path: Path, proof_path: Path) -> None:
    _assert_no_escape_hatches(tc, laws_path)
    _assert_no_escape_hatches(tc, proof_path)
    r_unproved = bend.check_verdict(laws_path)
    tc.assertFalse(
        r_unproved.ok,
        f"LAWS.bend alone must fail bend --verdict (laws without proofs): {laws_path}",
    )
    r_chk = bend.check(proof_path)
    tc.assertTrue(
        r_chk.ok,
        f"bend check failed on {proof_path}: {r_chk.first_line}\n{r_chk.out}",
    )
    r_vrd = bend.check_verdict(proof_path)
    tc.assertTrue(
        r_vrd.ok,
        f"bend --verdict failed on {proof_path}: {r_vrd.first_line}\n{r_vrd.out}",
    )
    tc.assertEqual(r_vrd.first_line, "ALL PROOFS CHECK")


class TestPreregInstruments(unittest.TestCase):
    """Preregistration instrument checks (must pass at Step 1 before Step 2 build)."""

    def test_spec_sidecar_matches_independent_instrument(self) -> None:
        self.assertTrue(SPEC_PATH.is_file(), f"missing {SPEC_PATH}")
        committed = load_json(SPEC_PATH)
        recomputed = _i42.theory_core_i_doc(ROOT)
        self.assertEqual(
            canonical_json(committed),
            canonical_json(recomputed),
            "spec/M3/lib/theory_core_i.json drifted from tests_m3._i42.theory_core_i_doc(ROOT)",
        )

    def test_inputs_sha256_match(self) -> None:
        doc = load_json(SPEC_PATH)
        inputs = doc["inputs"]
        self.assertEqual(len(inputs), len(_i42.INPUT_PATHS))
        for item in inputs:
            p = ROOT / item["path"]
            self.assertTrue(p.is_file(), f"missing input file {p}")
            self.assertEqual(sha256_file(p), item["sha256"], f"sha256 mismatch on {p}")

    def test_diagram_cycle_basis_counts(self) -> None:
        doc = load_json(SPEC_PATH)
        hdr = doc["basis_families"]["header"]["diagram"]
        self.assertEqual((hdr["E"], hdr["V"], hdr["kappa"], hdr["rank"]), (4, 3, 1, 2))
        self.assertEqual(hdr["non_tree_edges"], ["CODEC.enc_go_v1", "CODEC.enc_sol"])
        self.assertEqual(len(doc["basis_families"]["header"]["laws"]), 3)

        hl = doc["basis_families"]["header_length"]["diagram"]
        self.assertEqual((hl["E"], hl["V"], hl["kappa"], hl["rank"]), (20, 17, 1, 4))
        self.assertEqual(
            hl["non_tree_edges"],
            [
                "CODEC.BatchHeaderBytes_BlobHashesHash",
                "CODEC.BatchHeaderBytes_BlobVersionedHash",
                "CODEC.BatchHeaderV1_Bytes",
                "CODEC.load_sol",
            ],
        )
        self.assertEqual(len(doc["basis_families"]["header_length"]["laws"]), 5)

    def test_congruence_inventory_and_line_reduction(self) -> None:
        doc = load_json(SPEC_PATH)
        cong = doc["congruence"]
        self.assertEqual(cong["total"], 34)
        self.assertEqual(cong["m0_count"], 2)
        self.assertEqual(cong["m3_count"], 32)
        self.assertEqual(len(cong["laws"]), 34)
        self.assertLess(cong["congruence_def_lines"], cong["baseline_def_lines"])
        self.assertLess(cong["congruence_file_lines"], cong["baseline_total_lines"])
        for entry in cong["laws"]:
            self.assertEqual(entry["predicted_status"], "PROVED")
            self.assertEqual(entry["core_lemma"], "core_whisker_post")
            expected_def = 2 if entry["milestone"] == "M0" else 3
            self.assertEqual(entry["congruence_def_lines"], expected_def)

    def test_prototype_theory_core_i_laws_and_canaries(self) -> None:
        self.assertEqual(len(_i42.THEORY_CORE_I_SPECS), 12)
        by_grp: dict[str, int] = {}
        for s in _i42.THEORY_CORE_I_SPECS:
            by_grp[s["group"]] = by_grp.get(s["group"], 0) + 1
            self.assertGreaterEqual(
                len(s["hyps"]),
                1,
                f"{s['law_id']} must take at least one 2-cell hypothesis (no reflexivity tautologies)",
            )
            for h_name, _h_ty in s["hyps"]:
                self.assertIn(
                    f"{h_name}(",
                    s["proof"],
                    f"{s['law_id']} proof must use hypothesis {h_name}",
                )
        self.assertEqual(
            by_grp,
            {
                "whisker": 3,
                "pasting": 4,
                "domain_locality": 3,
                "basis_sufficiency": 2,
            },
        )
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            laws_p = td_p / "LAWS.bend"
            proof_p = td_p / "PROOF.bend"
            laws_p.write_text(_i42.render_theory_core_i_laws())
            proof_p.write_text(_i42.render_theory_core_i_proofs())
            _assert_bend_proved(self, laws_p, proof_p)

        self.assertEqual(len(_i42.CANARY_SPECS), 7)
        groups = {c["group"] for c in _i42.CANARY_SPECS}
        self.assertEqual(
            groups,
            {"theory_core_i", "header", "header_length", "congruence"},
        )
        with tempfile.TemporaryDirectory(dir=ROOT / "gen/M3/laws") as td:
            td_p = Path(td)
            for c in _i42.CANARY_SPECS:
                cid = c["canary_id"]
                laws_p = td_p / "LAWS.bend"
                proof_p = td_p / "PROOF.bend"
                laws_p.write_text(c["laws_bend"])
                proof_p.write_text(c["proof_bend"])
                r_chk = bend.check(proof_p)
                r_vrd = bend.check_verdict(proof_p)
                self.assertFalse(
                    r_chk.ok,
                    f"canary {cid} unexpectedly passed bend check",
                )
                self.assertFalse(
                    r_vrd.ok,
                    f"canary {cid} unexpectedly passed bend --verdict",
                )
                for label, res in (("bend", r_chk), ("bend --verdict", r_vrd)):
                    self.assertNotIn("no such file", res.out, f"{cid} ({label}): broken import")
                    self.assertNotIn("ParseError", res.out, f"{cid} ({label}): syntax error")
                    self.assertNotIn("expected : a defined name", res.out, f"{cid} ({label}): undefined symbol")
                    self.assertIn("- expected :", res.out, f"{cid} ({label}): missing expected type in error")
                    self.assertIn("- observed :", res.out, f"{cid} ({label}): missing observed type in error")


class TestTheoryCoreIBuild(unittest.TestCase):
    """Step 2 verification of `THEORY_CORE_I` in `holon.gen.core` and `gen/M3/core` (preserving `gen/M2/core`)."""

    def test_theory_core_i_registered_in_holon_gen_core(self) -> None:
        core = holon_module("holon.gen.core")
        self.assertTrue(
            hasattr(core, "THEORY_CORE_I"),
            "holon.gen.core is missing THEORY_CORE_I",
        )
        names = [entry[0] for entry in core.THEORY_CORE_I]
        expected_names = [s["law_id"] for s in _i42.THEORY_CORE_I_SPECS]
        self.assertEqual(names, expected_names)

    def test_m3_core_includes_theory_core_i_and_m2_core_untouched(self) -> None:
        expected_names = [s["law_id"] for s in _i42.THEORY_CORE_I_SPECS]
        laws_p = M3_CORE_DIR / "LAWS.bend"
        proof_p = M3_CORE_DIR / "PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        for name in expected_names:
            self.assertIn(f"law {name}:", laws_txt, f"missing {name} in {laws_p}")
            self.assertIn(f"def Laws.{name}(", proof_txt, f"missing {name} in {proof_p}")
        _assert_bend_proved(self, laws_p, proof_p)

        # AGENTS.md: gen/M0-M2 must never be edited in M3; gen/M2/core keeps its 20 M2 Nat/Bool lemmas.
        m2_laws_txt = _assert_no_escape_hatches(self, M2_CORE_DIR / "LAWS.bend")
        m2_proof_txt = _assert_no_escape_hatches(self, M2_CORE_DIR / "PROOF.bend")
        for name in expected_names:
            self.assertNotIn(
                f"law {name}:",
                m2_laws_txt,
                f"gen/M2/core/LAWS.bend must not be modified in M3 (found {name})",
            )
            self.assertNotIn(
                f"def Laws.{name}(",
                m2_proof_txt,
                f"gen/M2/core/PROOF.bend must not be modified in M3 (found {name})",
            )


class TestBasisSufficiency(unittest.TestCase):
    """Step 2 verification of `gen/M3/basis/header` and `gen/M3/basis/header_length`."""

    def test_header_basis_sufficiency(self) -> None:
        laws_p = BASIS_DIR / "header/LAWS.bend"
        proof_p = BASIS_DIR / "header/PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        self.assertIn("import ../../core/LAWS.bend as C", proof_txt)
        self.assertIn("import ../../core/PROOF.bend as CP", proof_txt)
        self.assertIn("RT0.l_rt_go_v0", proof_txt)
        for spec in _i42.HEADER_BASIS_LAWS:
            lid = spec["law_id"]
            self.assertIn(f"law {lid}:", laws_txt)
            self.assertIn(f"def Laws.{lid}(", proof_txt)
            self.assertIn(f"C.{spec['core_lemma']}(", proof_txt)
        _assert_bend_proved(self, laws_p, proof_p)

    def test_header_length_basis_sufficiency(self) -> None:
        laws_p = BASIS_DIR / "header_length/LAWS.bend"
        proof_p = BASIS_DIR / "header_length/PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        self.assertIn("import ../../core/LAWS.bend as C", proof_txt)
        self.assertIn("import ../../core/PROOF.bend as CP", proof_txt)
        self.assertIn("Laws.basis_hl_gen_blob_hashes_hash", proof_txt)
        for spec in _i42.HEADER_LENGTH_BASIS_LAWS:
            lid = spec["law_id"]
            self.assertIn(f"law {lid}:", laws_txt)
            self.assertIn(f"def Laws.{lid}(", proof_txt)
            self.assertIn(f"C.{spec['core_lemma']}(", proof_txt)
        _assert_bend_proved(self, laws_p, proof_p)


class TestCongruenceProofs(unittest.TestCase):
    """Step 2 verification of `gen/M3/basis/congruence` (34 congruence-derived round-trip laws)."""

    def test_congruence_proofs_check_and_beat_open_refl_line_count(self) -> None:
        laws_p = BASIS_DIR / "congruence/LAWS.bend"
        proof_p = BASIS_DIR / "congruence/PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        entries = _i42.congruence_entries(ROOT)
        self.assertEqual(len(entries), 34)
        for e in entries:
            lid = e["law_id"]
            self.assertIn(f"law {lid}:", laws_txt)
            self.assertIn(f"def Laws.{lid}(", proof_txt)
        self.assertNotIn("match ", proof_txt)
        self.assertEqual(proof_txt.count("C.core_whisker_post("), 34)

        _, _, cong_def_lines = _i42._line_counts(proof_p)
        base_def_lines = sum(e["baseline_def_lines"] for e in entries)
        base_total_lines = sum(e["baseline_total_lines"] for e in entries)
        cong_total_lines = len(proof_txt.splitlines())
        self.assertEqual(cong_def_lines, 100)
        self.assertLess(cong_def_lines, base_def_lines)
        self.assertLess(cong_total_lines, base_total_lines)

        _assert_bend_proved(self, laws_p, proof_p)


class TestNegativeCanaries(unittest.TestCase):
    """Step 2 verification that all 7 negative canaries fail `bend` and `bend --verdict` under `gen/M3/basis`."""

    def test_negative_canaries_rejected_under_basis_dir(self) -> None:
        self.assertTrue(BASIS_DIR.is_dir(), f"missing {BASIS_DIR}")
        self.assertTrue((M3_CORE_DIR / "PROOF.bend").is_file(), f"missing {M3_CORE_DIR / 'PROOF.bend'}")
        with tempfile.TemporaryDirectory(dir=BASIS_DIR) as td:
            td_p = Path(td)
            for c in _i42.CANARY_SPECS:
                cid = c["canary_id"]
                laws_p = td_p / "LAWS.bend"
                proof_p = td_p / "PROOF.bend"
                laws_p.write_text(c["laws_bend"])
                proof_p.write_text(c["proof_bend"])
                r_chk = bend.check(proof_p)
                r_vrd = bend.check_verdict(proof_p)
                self.assertFalse(
                    r_chk.ok,
                    f"canary {cid} unexpectedly passed bend check",
                )
                self.assertFalse(
                    r_vrd.ok,
                    f"canary {cid} unexpectedly passed bend --verdict",
                )
                for label, res in (("bend", r_chk), ("bend --verdict", r_vrd)):
                    self.assertNotIn("no such file", res.out, f"{cid} ({label}): broken import")
                    self.assertNotIn("ParseError", res.out, f"{cid} ({label}): syntax error")
                    self.assertNotIn("expected : a defined name", res.out, f"{cid} ({label}): undefined symbol")
                    self.assertIn("- expected :", res.out, f"{cid} ({label}): missing expected type in error")
                    self.assertIn("- observed :", res.out, f"{cid} ({label}): missing observed type in error")


class TestResultsSidecar(unittest.TestCase):
    """Step 2 verification of `results/M3/basis.json`."""

    def test_results_basis_json(self) -> None:
        self.assertTrue(RESULTS_PATH.is_file(), f"missing {RESULTS_PATH}")
        res = load_json(RESULTS_PATH)
        spec = load_json(SPEC_PATH)
        self.assertEqual(res["summary"], spec["summary"])
        self.assertEqual(res["summary"]["theory_core_i_laws"], 12)
        self.assertEqual(res["summary"]["header_basis_laws"], 3)
        self.assertEqual(res["summary"]["header_length_basis_laws"], 5)
        self.assertEqual(res["summary"]["congruence_laws"], 34)
        self.assertEqual(res["summary"]["total_proved_laws"], 54)
        self.assertEqual(res["summary"]["canaries_refuted"], 7)

        for group_key, expected_cnt in (
            ("theory_core_i", 12),
            ("header", 3),
            ("header_length", 5),
            ("congruence", 34),
        ):
            grp = res["groups"][group_key]
            self.assertEqual(grp["law_count"], expected_cnt)
            self.assertTrue(grp["bend_check_ok"])
            self.assertTrue(grp["bend_verdict_ok"])
            self.assertFalse(grp["laws_only_verdict_ok"])
            self.assertEqual(len(grp["laws"]), expected_cnt)
            for item in grp["laws"]:
                self.assertEqual(item["status"], "PROVED")

        canaries = res["canaries"]
        self.assertEqual(len(canaries), 7)
        for c in canaries:
            self.assertEqual(c["status"], "REFUTED")
            self.assertFalse(c["bend_check_ok"])
            self.assertFalse(c["bend_verdict_ok"])

        lc = res["congruence_line_comparison"]
        self.assertEqual(lc["law_count"], 34)
        self.assertLess(lc["congruence_def_lines"], lc["baseline_def_lines"])
        self.assertLess(lc["congruence_proof_lines"], lc["baseline_total_lines"])


if __name__ == "__main__":
    unittest.main()
