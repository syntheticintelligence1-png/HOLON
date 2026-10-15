"""I43: Theory core II (equivariance, 2-cell pasting) and Lean 4 promotion for the promoted set.

Contract (`docs/BUILD_PLAN.md` I43, `whitepaper.md` sections 6.1-6.2, 6.4, 8.8, Q14c):
1. `holon/gen/core.py` defines `THEORY_CORE_II` (10 polymorphic Bend 2 laws across
   2 groups: 5 `equivariance` laws `core_equivar_compose`, `core_equivar_whisker`,
   `core_equivar_obs`, `core_equivar_pred`, `core_equivar_homotopy`; and 5
   `pasting` laws `core_paste_grid_2x2`, `core_paste_h_3`, `core_paste_v_obs`,
   `core_paste_square_trans`, `core_paste_whisker_interchange`), and emits them
   into `gen/M3/core/{LAWS,PROOF}.bend` (bringing `gen/M3/core` to
   `31 + 12 + 10 = 53` laws while keeping `gen/M2/core/{LAWS,PROOF}.bend`
   untouched at 31 laws).
2. `holon/gen/basis.py` emits:
   - `gen/M3/basis/equivariance/{LAWS,PROOF}.bend` (4 concrete equivariance laws
     over `gen/M1/model/morph_rollup.bend`: `basis_equivar_mig_legacy_wait`,
     `basis_equivar_mig_legacy_send_msg`, `basis_equivar_mig_eta2_wait`, and
     `basis_equivar_mig_compose_wait` proved via `C.core_equivar_whisker`).
   - `gen/M3/basis/pasting/{LAWS,PROOF}.bend` (4 concrete pasting laws over
     `gen/M1/model/morph_rollup.bend`: `basis_paste_lci_mig_legacy`,
     `basis_paste_lci_mig_eta2`, `basis_paste_lci_mig_chain`, and
     `basis_paste_tags_mig_chain` proved via `C.core_paste_v_obs`).
   - Preserves `gen/M3/basis/{header,header_length,congruence}` and
     `results/M3/basis.json` from I42 byte-for-byte.
3. `holon/lean.py` generates the Lean 4.34.0 Lake project in `gen/M3/lean/`
   (`lean-toolchain`, `lakefile.toml` with `globs = ["Holon.*"]`, `Holon.lean`,
   `Holon/...` with no `import` statements so `holon.lean.forbidden(txt)` is
   empty, and `report.json`) and writes the deterministic promotion sidecar
   `results/M3/lean.json`:
   - All 92 `PROVED` laws across M0..M3 (`5` M0 + `8` M1 + `6` M2 + `73` M3)
     are verified by Lean 4.34.0 and promoted to `independence_class: "I2"` with
     a checked `lean4` kernel entry (`role: "second-independent"`, axioms within
     `{"Quot.sound", "propext"}`, zero `sorry`/`admit`/`axiom`/`native_decide`/
     `unsafe` and `holon.lean.forbidden(txt) == []`).
   - All 10 `THEORY_CORE_II` laws and 8 concrete `equivariance`/`pasting` basis
     laws are verified in both Bend (`bend` + `bend --verdict`) and Lean 4.34.0.
   - All 5 negative canaries across `theory_core_ii`, `equivariance`,
     `pasting`, and `lean` are `REFUTED` (4 under `bend` and `bend --verdict`,
     and `canary_lean_flipped_claim` semantically rejected by
     `holon.lean.check_text`).
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from holon import bend
from tests_m2 import test_target_agnostic_exhaustive as _tae
from tests_m3 import _i43
from tests_m3._m3 import ROOT, SPEC3, canonical_json, holon_module, load_json


SPEC_PATH = SPEC3 / "lib/theory_core_ii.json"
M3_CORE_DIR = ROOT / "gen/M3/core"
M2_CORE_DIR = ROOT / "gen/M2/core"
BASIS_DIR = ROOT / "gen/M3/basis"
M3_LEAN_DIR = ROOT / "gen/M3/lean"
M0_LEAN_DIR = ROOT / "gen/M0/lean"
RESULTS_LEAN_PATH = ROOT / "results/M3/lean.json"

ESCAPE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\?TODO\b"),
    re.compile(r"@unsafe\b"),
    re.compile(r"\bdef\s+[A-Za-z0-9_.]+\?\s*\("),
    re.compile(r'^\s*import\s+"[^"]+\.c"', re.MULTILINE),
)

LEAN_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsorry\b"),
    re.compile(r"\badmit\b"),
    re.compile(r"^\s*axiom\s+", re.MULTILINE),
    re.compile(r"\bnative_decide\b"),
    re.compile(r"^\s*unsafe\s+", re.MULTILINE),
)


def _assert_no_escape_hatches(tc: unittest.TestCase, path: Path) -> str:
    tc.assertTrue(path.is_file(), f"missing Bend file: {path}")
    txt = path.read_text()
    for pat in ESCAPE_PATTERNS:
        tc.assertIsNone(
            pat.search(txt),
            f"escape hatch {pat.pattern!r} found in {path}",
        )
    return txt


def _assert_bend_proved(
    tc: unittest.TestCase, laws_path: Path, proof_path: Path
) -> None:
    r_chk = bend.check(proof_path)
    tc.assertTrue(
        r_chk.ok,
        f"bend check failed on {proof_path}:\n{r_chk.out}",
    )
    r_vrd = bend.check_verdict(proof_path)
    tc.assertTrue(
        r_vrd.ok,
        f"bend --verdict failed on {proof_path}:\n{r_vrd.out}",
    )
    r_laws_only = bend.check_verdict(laws_path)
    tc.assertFalse(
        r_laws_only.ok,
        f"LAWS.bend alone unexpectedly passed bend --verdict: {laws_path}",
    )


class TestPreregSidecar(unittest.TestCase):
    """Step 1 preregistration invariants for `spec/M3/lib/theory_core_ii.json` and `tests_m3/_i43.py`."""

    def test_sidecar_is_byte_identical_to_i43_recomputation(self) -> None:
        self.assertTrue(SPEC_PATH.is_file(), f"missing {SPEC_PATH}")
        committed = load_json(SPEC_PATH)
        recomputed = _i43.theory_core_ii_doc(ROOT)
        self.assertEqual(canonical_json(committed), canonical_json(recomputed))
        self.assertEqual(
            SPEC_PATH.read_text(),
            json.dumps(recomputed, indent=2, sort_keys=True) + "\n",
        )

    def test_inputs_sha256_match(self) -> None:
        doc = load_json(SPEC_PATH)
        for entry in doc["inputs"]:
            p = ROOT / entry["path"]
            self.assertTrue(p.is_file(), f"missing input {p}")
            self.assertEqual(
                _i43._sha256(p),
                entry["sha256"],
                f"hash mismatch for {entry['path']}",
            )

    def test_i43_module_does_not_import_target_generators(self) -> None:
        src = Path(_i43.__file__).read_text()
        tree = ast.parse(src)
        forbidden = {
            "holon.gen.basis",
            "holon.gen.core",
            "holon.gen.mproofs",
            "holon.lean",
            "holon.gen.lean_model",
            "holon.gen.lean_laws",
            "holon.gen.lean_proofs",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name, forbidden)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                self.assertNotIn(mod, forbidden)
                for alias in node.names:
                    self.assertNotIn(f"{mod}.{alias.name}", forbidden)

    def test_prereg_promoted_set_counts(self) -> None:
        doc = _i43.theory_core_ii_doc(ROOT)
        s = doc["summary"]
        self.assertEqual(s["m2_core_laws"], 31)
        self.assertEqual(s["theory_core_i_laws"], 12)
        self.assertEqual(s["theory_core_ii_laws"], 10)
        self.assertEqual(s["m3_core_total_laws"], 53)
        self.assertEqual(s["equivariance_basis_laws"], 4)
        self.assertEqual(s["pasting_basis_laws"], 4)
        self.assertEqual(s["total_new_bend_laws"], 18)
        self.assertEqual(s["promoted_m0_laws"], 5)
        self.assertEqual(s["promoted_m1_laws"], 8)
        self.assertEqual(s["promoted_m2_laws"], 6)
        self.assertEqual(s["promoted_m3_laws"], 73)
        self.assertEqual(s["total_promoted_i2_laws"], 92)
        self.assertEqual(s["canaries_refuted"], 5)
        for ms in ("M0", "M1", "M2", "M3"):
            for item in doc["lean_promotion"]["milestones"][ms]:
                self.assertTrue(
                    item.get("bend_generator"),
                    f"missing bend_generator for {ms} {item['law_id']}",
                )

    def test_prereg_theory_core_ii_basis_and_canaries_check_in_bend(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            (td_p / "M1/model").mkdir(parents=True)
            (td_p / "M3/core").mkdir(parents=True)
            (td_p / "M3/basis/equivariance").mkdir(parents=True)
            (td_p / "M3/basis/pasting").mkdir(parents=True)

            shutil.copy(
                ROOT / "gen/M1/model/morph_rollup.bend",
                td_p / "M1/model/morph_rollup.bend",
            )
            core_laws_p = td_p / "M3/core/LAWS.bend"
            core_proof_p = td_p / "M3/core/PROOF.bend"
            core_laws_p.write_text(_i43.render_theory_core_ii_laws())
            core_proof_p.write_text(_i43.render_theory_core_ii_proofs())
            _assert_bend_proved(self, core_laws_p, core_proof_p)

            eq_laws_p = td_p / "M3/basis/equivariance/LAWS.bend"
            eq_proof_p = td_p / "M3/basis/equivariance/PROOF.bend"
            eq_laws_p.write_text(_i43.equivariance_laws_bend())
            eq_proof_p.write_text(_i43.equivariance_proof_bend())
            _assert_bend_proved(self, eq_laws_p, eq_proof_p)

            paste_laws_p = td_p / "M3/basis/pasting/LAWS.bend"
            paste_proof_p = td_p / "M3/basis/pasting/PROOF.bend"
            paste_laws_p.write_text(_i43.pasting_laws_bend())
            paste_proof_p.write_text(_i43.pasting_proof_bend())
            _assert_bend_proved(self, paste_laws_p, paste_proof_p)

            self.assertEqual(len(_i43.CANARY_SPECS), 5)
            groups = {c["group"] for c in _i43.CANARY_SPECS}
            self.assertEqual(
                groups,
                {"theory_core_ii", "equivariance", "pasting", "lean"},
            )
            canary_dir = td_p / "M3/basis/canary"
            canary_dir.mkdir(parents=True)
            bend_canaries = [c for c in _i43.CANARY_SPECS if c["group"] != "lean"]
            self.assertEqual(len(bend_canaries), 4)
            for c in bend_canaries:
                cid = c["canary_id"]
                c_laws_p = canary_dir / "LAWS.bend"
                c_proof_p = canary_dir / "PROOF.bend"
                c_laws_p.write_text(c["laws_bend"])
                c_proof_p.write_text(c["proof_bend"])
                r_chk = bend.check(c_proof_p)
                r_vrd = bend.check_verdict(c_proof_p)
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

            lean = holon_module("holon.lean")
            lean_res = lean.check_text(_i43.canary_lean_source(), td_p / "lean_canary")
            self.assertEqual(
                lean_res["result"],
                "rejected",
                f"canary_lean_flipped_claim unexpectedly got {lean_res['result']}:\n{lean_res['out']}",
            )
            self.assertTrue(
                lean.semantic_rejection(lean_res["out"]),
                f"canary_lean_flipped_claim was not semantically rejected:\n{lean_res['out']}",
            )


class TestTheoryCoreIIBuild(unittest.TestCase):
    """Step 2 verification of `THEORY_CORE_II` in `holon.gen.core` and `gen/M3/core` (preserving `gen/M2/core`)."""

    def test_theory_core_ii_registered_in_holon_gen_core(self) -> None:
        core = holon_module("holon.gen.core")
        self.assertTrue(
            hasattr(core, "THEORY_CORE_II"),
            "holon.gen.core is missing THEORY_CORE_II",
        )
        names = [entry[0] for entry in core.THEORY_CORE_II]
        expected_names = [s["law_id"] for s in _i43.THEORY_CORE_II_SPECS]
        self.assertIn("core_equivar_homotopy", expected_names)
        self.assertNotIn("core_equivar_defect_zero", expected_names)
        self.assertEqual(names, expected_names)
        for s in _i43.THEORY_CORE_II_SPECS:
            lid = s["law_id"]
            for _, h_ty in s["hyps"]:
                self.assertNotEqual(
                    s["claim"],
                    h_ty,
                    f"{lid}: claim must not equal a hypothesis type verbatim",
                )
            for h_name, _ in s["hyps"]:
                self.assertIsNotNone(
                    re.search(rf"\b{re.escape(h_name)}\b", s["proof"]),
                    f"{lid}: hypothesis {h_name!r} not used in proof",
                )
            self.assertTrue(
                any(tok in s["proof"] for tok in ("%", "finally", "rewrite", "{==}")),
                f"{lid}: proof must use at least one equality rewrite",
            )

    def test_core_emit_reproduces_m3_core_files(self) -> None:
        core = holon_module("holon.gen.core")
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            m3_gen = td_p / "M3"
            m2_gen = td_p / "M2"
            emitted_m3 = core.emit(m3_gen)
            emitted_m2 = core.emit(m2_gen)
            self.assertEqual(len(emitted_m3), 53)
            self.assertEqual(len(emitted_m2), 31)
            for s in _i43.THEORY_CORE_II_SPECS:
                self.assertIn(s["law_id"], emitted_m3)
                self.assertNotIn(s["law_id"], emitted_m2)
            self.assertEqual(
                (m3_gen / "core/LAWS.bend").read_text(),
                (M3_CORE_DIR / "LAWS.bend").read_text(),
            )
            self.assertEqual(
                (m3_gen / "core/PROOF.bend").read_text(),
                (M3_CORE_DIR / "PROOF.bend").read_text(),
            )
            self.assertEqual(
                (m2_gen / "core/LAWS.bend").read_text(),
                (M2_CORE_DIR / "LAWS.bend").read_text(),
            )
            self.assertEqual(
                (m2_gen / "core/PROOF.bend").read_text(),
                (M2_CORE_DIR / "PROOF.bend").read_text(),
            )

    def test_holon_generators_remain_target_agnostic(self) -> None:
        ids = _tae.identifiers()
        pat = re.compile(
            r"(?<![\w$])("
            + "|".join(sorted(map(re.escape, ids), key=len, reverse=True))
            + r")(?![\w$])"
        )
        target_files = [
            ROOT / "holon/gen/core.py",
            ROOT / "holon/gen/basis.py",
            ROOT / "holon/lean.py",
            *sorted((ROOT / "holon/gen").glob("lean_*.py")),
        ]
        for f in target_files:
            rel = f.relative_to(ROOT).as_posix()
            text = f.read_text(encoding="utf-8")
            code = _tae.code_py(text)
            with self.subTest(file=rel):
                self.assertEqual(
                    sorted(set(pat.findall(code))),
                    sorted(_tae.ALLOWLIST.get(rel, [])),
                )

    def test_m3_core_includes_theory_core_ii_and_m2_core_untouched(self) -> None:
        expected_names = [s["law_id"] for s in _i43.THEORY_CORE_II_SPECS]
        laws_p = M3_CORE_DIR / "LAWS.bend"
        proof_p = M3_CORE_DIR / "PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        for name in expected_names:
            self.assertIn(f"law {name}:", laws_txt, f"missing {name} in {laws_p}")
            self.assertIn(f"def Laws.{name}(", proof_txt, f"missing {name} in {proof_p}")
        law_decls = re.findall(r"^law\s+(core_\w+):", laws_txt, re.MULTILINE)
        self.assertEqual(len(law_decls), 53)
        _assert_bend_proved(self, laws_p, proof_p)

        # AGENTS.md: gen/M0-M2 must never be edited in M3; gen/M2/core keeps its 31 CATALOG lemmas.
        m2_laws_txt = _assert_no_escape_hatches(self, M2_CORE_DIR / "LAWS.bend")
        m2_proof_txt = _assert_no_escape_hatches(self, M2_CORE_DIR / "PROOF.bend")
        m2_law_decls = re.findall(r"^law\s+(core_\w+):", m2_laws_txt, re.MULTILINE)
        self.assertEqual(len(m2_law_decls), 31)
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


class TestEquivarianceAndPastingBasis(unittest.TestCase):
    """Step 2 verification of `gen/M3/basis/equivariance` and `gen/M3/basis/pasting`."""

    def test_equivariance_basis_checks(self) -> None:
        laws_p = BASIS_DIR / "equivariance/LAWS.bend"
        proof_p = BASIS_DIR / "equivariance/PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        self.assertIn("import ../../core/LAWS.bend as C", proof_txt)
        self.assertIn("import ../../core/PROOF.bend as CP", proof_txt)
        self.assertIn("import ../../../M1/model/morph_rollup.bend as M", proof_txt)
        for spec in _i43.EQUIVARIANCE_BASIS_LAWS:
            lid = spec["law_id"]
            self.assertIn(f"law {lid}:", laws_txt)
            self.assertIn(f"def Laws.{lid}(", proof_txt)
            if spec["core_lemma"]:
                self.assertIn(f"C.{spec['core_lemma']}(", proof_txt)
        _assert_bend_proved(self, laws_p, proof_p)

    def test_pasting_basis_checks(self) -> None:
        laws_p = BASIS_DIR / "pasting/LAWS.bend"
        proof_p = BASIS_DIR / "pasting/PROOF.bend"
        laws_txt = _assert_no_escape_hatches(self, laws_p)
        proof_txt = _assert_no_escape_hatches(self, proof_p)
        self.assertIn("import ../../core/LAWS.bend as C", proof_txt)
        self.assertIn("import ../../core/PROOF.bend as CP", proof_txt)
        self.assertIn("import ../../../M1/model/morph_rollup.bend as M", proof_txt)
        for spec in _i43.PASTING_BASIS_LAWS:
            lid = spec["law_id"]
            self.assertIn(f"law {lid}:", laws_txt)
            self.assertIn(f"def Laws.{lid}(", proof_txt)
            if spec["core_lemma"]:
                self.assertIn(f"C.{spec['core_lemma']}(", proof_txt)
        _assert_bend_proved(self, laws_p, proof_p)


class TestNegativeCanaries(unittest.TestCase):
    """Step 2 verification that all 5 negative canaries fail (`bend` / `bend --verdict` and `holon.lean.check_text`)."""

    def test_negative_canaries_rejected_under_basis_dir(self) -> None:
        self.assertTrue((BASIS_DIR / "equivariance/PROOF.bend").is_file(), "missing gen/M3/basis/equivariance/PROOF.bend")
        self.assertTrue((BASIS_DIR / "pasting/PROOF.bend").is_file(), "missing gen/M3/basis/pasting/PROOF.bend")
        self.assertEqual(len(_i43.CANARY_SPECS), 5)
        with tempfile.TemporaryDirectory(dir=BASIS_DIR) as td:
            td_p = Path(td)
            bend_canaries = [c for c in _i43.CANARY_SPECS if c["group"] != "lean"]
            self.assertEqual(len(bend_canaries), 4)
            for c in bend_canaries:
                cid = c["canary_id"]
                laws_p = td_p / "LAWS.bend"
                proof_p = td_p / "PROOF.bend"
                laws_p.write_text(c["laws_bend"])
                proof_p.write_text(c["proof_bend"])
                r_chk = bend.check(proof_p)
                r_vrd = bend.check_verdict(proof_p)
                self.assertFalse(r_chk.ok, f"canary {cid} unexpectedly passed bend check")
                self.assertFalse(r_vrd.ok, f"canary {cid} unexpectedly passed bend --verdict")

            lean = holon_module("holon.lean")
            lean_res = lean.check_text(_i43.canary_lean_source(), td_p / "lean_canary")
            self.assertEqual(
                lean_res["result"],
                "rejected",
                f"canary_lean_flipped_claim unexpectedly got {lean_res['result']}:\n{lean_res['out']}",
            )
            self.assertTrue(
                lean.semantic_rejection(lean_res["out"]),
                f"canary_lean_flipped_claim was not semantically rejected:\n{lean_res['out']}",
            )


class TestLeanPromotion(unittest.TestCase):
    """Step 2 verification of `gen/M3/lean/` and `results/M3/lean.json`."""

    def test_m3_lean_project_exists_and_has_no_escape_hatches(self) -> None:
        lean = holon_module("holon.lean")
        self.assertTrue(M3_LEAN_DIR.is_dir(), f"missing {M3_LEAN_DIR}")
        tc_file = M3_LEAN_DIR / "lean-toolchain"
        lake_file = M3_LEAN_DIR / "lakefile.toml"
        root_lean = M3_LEAN_DIR / "Holon.lean"
        report_file = M3_LEAN_DIR / "report.json"
        for f in (tc_file, lake_file, root_lean, report_file):
            self.assertTrue(f.is_file(), f"missing {f}")
        self.assertEqual(
            tc_file.read_text().strip(),
            f"leanprover/lean4:v{_i43.LEAN_TOOLCHAIN_VERSION}",
        )
        lake_txt = lake_file.read_text()
        self.assertIn('globs = ["Holon.*"]', lake_txt)
        rep = load_json(report_file)
        self.assertEqual(rep.get("lean_version"), _i43.LEAN_TOOLCHAIN_VERSION)
        self.assertEqual(rep.get("allowed_axioms"), sorted(_i43.ALLOWED_AXIOMS))
        self.assertTrue(rep.get("laws"), "gen/M3/lean/report.json must have non-empty laws")
        lean_files = sorted(M3_LEAN_DIR.rglob("*.lean")) + sorted(M0_LEAN_DIR.rglob("*.lean"))
        self.assertGreaterEqual(len(lean_files), 90)
        for lf in lean_files:
            txt = lf.read_text()
            self.assertEqual(
                lean.forbidden(txt),
                [],
                f"forbidden Lean tokens in {lf}: {lean.forbidden(txt)}",
            )
            for pat in LEAN_FORBIDDEN_PATTERNS:
                self.assertIsNone(
                    pat.search(txt),
                    f"forbidden Lean pattern {pat.pattern!r} in {lf}",
                )

    def test_results_m3_lean_json_and_i2_promotion(self) -> None:
        lean = holon_module("holon.lean")
        self.assertTrue(RESULTS_LEAN_PATH.is_file(), f"missing {RESULTS_LEAN_PATH}")
        res = load_json(RESULTS_LEAN_PATH)
        spec = load_json(SPEC_PATH)
        self.assertEqual(res["summary"], spec["summary"])
        self.assertEqual(res["lean_toolchain_version"], _i43.LEAN_TOOLCHAIN_VERSION)
        self.assertEqual(res["allowed_axioms"], list(_i43.ALLOWED_AXIOMS))
        self.assertTrue(res["lake_build_ok"])

        for group_key, expected_cnt in (
            ("theory_core_ii", 10),
            ("equivariance", 4),
            ("pasting", 4),
        ):
            grp = res["groups"][group_key]
            self.assertEqual(grp["law_count"], expected_cnt)
            self.assertTrue(grp["bend_check_ok"])
            self.assertTrue(grp["bend_verdict_ok"])
            self.assertFalse(grp["laws_only_verdict_ok"])
            self.assertTrue(grp["lean_check_ok"])
            self.assertEqual(len(grp["laws"]), expected_cnt)
            for item in grp["laws"]:
                self.assertEqual(item["status"], "PROVED")
                self.assertTrue(set(item["axioms"]).issubset(set(_i43.ALLOWED_AXIOMS)))

        promoted = res["promoted_laws"]
        self.assertEqual(promoted["total_promoted_laws"], 92)
        self.assertEqual(
            promoted["counts_by_milestone"],
            {"M0": 5, "M1": 8, "M2": 6, "M3": 73},
        )
        expected_by_ms = spec["lean_promotion"]["milestones"]
        for ms in ("M0", "M1", "M2", "M3"):
            got_ms = promoted["milestones"][ms]
            exp_ms = expected_by_ms[ms]
            self.assertEqual(len(got_ms), len(exp_ms))
            self.assertEqual(
                [x["law_id"] for x in got_ms],
                [x["law_id"] for x in exp_ms],
            )
            for item, exp_item in zip(got_ms, exp_ms):
                self.assertEqual(item["status"], "PROVED")
                self.assertEqual(item["statement_hash"], exp_item["statement_hash"])
                self.assertEqual(item["independence_class"], "I2")
                k = item["lean4_kernel"]
                self.assertEqual(k["name"], "lean4")
                self.assertEqual(k["version"], _i43.LEAN_TOOLCHAIN_VERSION)
                self.assertEqual(k["role"], "second-independent")
                self.assertEqual(k["result"], "checked")
                self.assertTrue(
                    set(k["axioms"]).issubset(set(_i43.ALLOWED_AXIOMS)),
                    f"disallowed axioms for {item['law_id']}: {k['axioms']}",
                )
                lean_src = ROOT / k["source"]
                self.assertTrue(lean_src.is_file(), f"missing Lean source {lean_src}")
                self.assertEqual(
                    k.get("source_sha256"),
                    _i43._sha256(lean_src),
                    f"source_sha256 mismatch for {item['law_id']}",
                )
                lean_txt = lean_src.read_text()
                self.assertIn(exp_item["statement_hash"], lean_txt)
                self.assertIn(f"theorem {exp_item['lean_theorem']}", lean_txt)
                self.assertIn(f"#print axioms {exp_item['lean_theorem']}", lean_txt)

        canaries = res["canaries"]
        self.assertEqual(len(canaries), 5)
        for c in canaries:
            self.assertEqual(c["status"], "REFUTED")
            if c.get("group") == "lean" or c.get("canary_id") == "canary_lean_flipped_claim":
                self.assertFalse(c["lean_check_ok"])
                self.assertTrue(c["semantic_rejection"])
            else:
                self.assertFalse(c["bend_check_ok"])
                self.assertFalse(c["bend_verdict_ok"])

        b = lean.toolchain_bin()
        with tempfile.TemporaryDirectory() as td:
            proj_copy = Path(td) / "lean"
            shutil.copytree(
                M3_LEAN_DIR,
                proj_copy,
                ignore=shutil.ignore_patterns(".lake"),
            )
            proc = subprocess.run(
                [str(b / "lake"), "build", "--no-cache", "--log-level=info"],
                cwd=proj_copy,
                env=lean._env(b),
                capture_output=True,
                text=True,
                timeout=300,
            )
            out = proc.stdout + proc.stderr
            self.assertEqual(
                proc.returncode,
                0,
                f"lake build --no-cache failed:\n{out}",
            )
            ax = lean.parse_axioms(out)
            expected_theorems = [
                *(s["law_id"] for s in _i43.THEORY_CORE_II_SPECS),
                *(s["law_id"] for s in _i43.EQUIVARIANCE_BASIS_LAWS),
                *(s["law_id"] for s in _i43.PASTING_BASIS_LAWS),
                *(
                    exp_item["lean_theorem"]
                    for ms in ("M1", "M2", "M3")
                    for exp_item in expected_by_ms[ms]
                ),
            ]
            for thm in expected_theorems:
                self.assertIn(thm, ax, f"missing #print axioms output for {thm}")
                self.assertTrue(
                    set(ax[thm]).issubset(lean.ALLOWED_AXIOMS),
                    f"disallowed axioms for {thm}: {ax[thm]}",
                )

            core_lean = (M3_LEAN_DIR / "Holon/Core.lean").read_text()
            mut_core_lean = core_lean.replace(
                "((f (s1 (s2 a)))) ((t1 (t2 (f a))))",
                "((f (s1 (s2 a)))) ((t2 (t1 (f a))))",
                1,
            )
            self.assertNotEqual(mut_core_lean, core_lean)
            mut_res = lean.check_text(mut_core_lean, Path(td))
            self.assertEqual(
                mut_res["result"],
                "rejected",
                f"mutated Core.lean unexpectedly checked:\n{mut_res['out']}",
            )
            self.assertTrue(
                lean.semantic_rejection(mut_res["out"]),
                f"mutated Core.lean was not semantically rejected:\n{mut_res['out']}",
            )


if __name__ == "__main__":
    unittest.main()
