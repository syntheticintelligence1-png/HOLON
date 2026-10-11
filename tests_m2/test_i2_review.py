"""I2 follow-up: checks added after the adversarial review of I2 (not part of the I2 preregistration)."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon

EMIT_PATCH = '''

# --- planted by tests_m2/test_i2_review.py: the emitter adds a premise to one law ---
_holon_orig_emit = {target}
def _holon_patched_emit(*a, **k):
    e = _holon_orig_emit(*a, **k)
    law = a[{law_arg}] if len(a) > {law_arg} else k["law"]
    if law["law_id"] == "{lid}":
        e.text = e.text.replace("law {name}:\\n", "law {name}:\\n  for hz: {{True{{}} == True{{}} : Bool}}\\n")
        e.text = e.text.replace("law cl_{name}:\\n", "law cl_{name}:\\n  exs hz: {{True{{}} == True{{}} : Bool}}\\n")
    return e
{target} = _holon_patched_emit
'''


def gate(repo: Path, m: str, checks: str):
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


def named_laws(detail: str) -> list[str]:
    return sorted(set(re.findall(r"\bL_[A-Za-z0-9_]+", detail)))


class TestEmitterIsBound(unittest.TestCase):
    def planted(self, module: str, target: str, law_arg: int, m: str, lid: str) -> dict:
        repo = copy_repo()
        try:
            f = repo / module
            f.write_text(f.read_text() + EMIT_PATCH.format(target=target, law_arg=law_arg, lid=lid, name=lid.lower()))
            p, rep = gate(repo, m, "G2")
            self.assertIsNotNone(rep, p.stdout[-1500:] + p.stderr[-1500:])
            return rep["checks"]["G2"]
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_emitter_adding_a_premise_fails_g2_m1(self):
        g2 = self.planted("holon/gen/mlaws.py", "Emitter.emit", 1, "M1", "L_undo_CSR")
        self.assertFalse(g2["passed"])
        self.assertIn("emitted statement", g2["detail"])
        self.assertEqual(named_laws(g2["detail"]), ["L_undo_CSR"])

    def test_emitter_adding_a_premise_fails_g2_m0(self):
        g2 = self.planted("holon/gen/laws.py", "emit", 0, "M0", "L_par_hdr_v0")
        self.assertFalse(g2["passed"])
        self.assertIn("emitted statement", g2["detail"])
        self.assertEqual(named_laws(g2["detail"]), ["L_par_hdr_v0"])

    def test_checked_laws_file_must_be_the_bound_emission(self):
        repo = copy_repo()
        try:
            f = repo / "gen" / "M1" / "L_undo_CSR" / "LAWS.bend"
            f.write_text(f.read_text().replace("law l_undo_csr:\n", "law l_undo_csr:\n  for hz: {True{} == True{} : Bool}\n"))
            p, rep = gate(repo, "M1", "G2")
            g2 = rep["checks"]["G2"]
            self.assertFalse(g2["passed"])
            self.assertIn("checked LAWS.bend", g2["detail"])
            self.assertEqual(named_laws(g2["detail"]), ["L_undo_CSR"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestKernelGraphEdges(unittest.TestCase):
    def setUp(self):
        self.B = holon_module("holon.bindings")
        self.dir = Path(tempfile.mkdtemp(prefix="holon-i2r-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def model(self, text: str) -> dict:
        f = self.dir / "m.bend"
        f.write_text("import Base\n\n" + text)
        return self.B.kernel_entries(f)

    def test_dotted_root_is_the_definition_not_the_type(self):
        src = "type Box is Data:\n  Box{v: Nat}\n\ndef Box.ok(b: Box) -> Bool:\n  True{}\n"
        e = self.model(src)
        cone = self.B.kernel_cone("{M.Box.ok(b) == True{} : Bool}", e)
        self.assertIn("Box.ok", cone)
        e2 = self.model(src.replace("  True{}\n", "  False{}\n"))
        self.assertNotEqual(e["Box.ok"], e2["Box.ok"])

    def test_unresolved_root_and_empty_cone_are_errors(self):
        e = self.model("def f(n: Nat) -> Nat:\n  n\n")
        with self.assertRaises(self.B.BindingError):
            self.B.kernel_cone("{M.nope(1n) == 1n : Nat}", e)
        with self.assertRaises(self.B.BindingError):
            self.B.kernel_cone("{1n == 1n : Nat}", e)

    def test_definition_named_like_a_kernel_local_is_an_error(self):
        with self.assertRaises(self.B.BindingError):
            self.model("def x0(n: Nat) -> Nat:\n  n\n")

    def test_universe_levels_are_not_constructor_tags(self):
        idx = load_json(ROOT / "gen" / "M1" / "model" / "morph_rollup.defs.json")["defs"]
        for name in ("Bool", "Nat", "Unit", "Empty"):
            if name in idx:
                with self.subTest(datatype=name):
                    self.assertNotIn("List", idx[name]["refs"])


class TestDepsByModel(unittest.TestCase):
    def test_same_named_definitions_are_kept_apart(self):
        d = load_json(ROOT / "results" / "M1" / "deps.json")["dependents_by_model"]
        self.assertEqual(d["morph_batchdata"]["s0"], ["L_own_txspayload"])
        self.assertNotIn("L_own_txspayload", d["morph_rollup"]["s0"])
        self.assertNotIn("L_own_txspayload", d["morph_rollup"]["step"])


class TestBindLog(unittest.TestCase):
    def test_creation_is_logged(self):
        repo = copy_repo()
        try:
            (repo / "spec" / "bindings" / "M1.json").unlink()
            p = run_holon(["bind", "--milestone", "M1"], cwd=repo)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            last = json.loads((repo / "spec" / "bindings" / "changes.jsonl").read_text().strip().splitlines()[-1])
            self.assertTrue(last["created"])
            self.assertEqual(len(last["laws"]), 16)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_g1_names_a_deps_mismatch(self):
        repo = copy_repo()
        try:
            f = repo / "results" / "M0" / "deps.json"
            d = load_json(f)
            d["dependents"]["enc_sol"] = []
            f.write_text(json.dumps(d))
            p, rep = gate(repo, "M0", "G1")
            self.assertFalse(rep["checks"]["G1"]["passed"])
            self.assertIn("deps.json identical: False", rep["checks"]["G1"]["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
