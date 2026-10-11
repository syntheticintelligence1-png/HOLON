"""Statement-equivalence test: Bend and Lean statements agree on the model.

For every PROVED and REFUTED law in M0 and M1, evaluate every premise and
every claim of the frozen statement on both engines at the same sampled
assignments — the recorded model witness when one exists, plus deterministic
zero/empty samples — and assert the booleans agree. The Lean side is an
emitted `#eval` file generated from the same IR terms (`#eval` is eval-only;
it never appears in a checked proof file).
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from holon import facts as F
from holon import ir
from holon.lean import equiv
from holon.lean import laws02
from holon.lean import machine as machine_gen
from holon.lean import runner

REPO = Path(__file__).resolve().parents[2]


def _tools_ok():
    lean = shutil.which("lean") or Path.home() / ".elan/bin/lean"
    return Path(lean).exists() and shutil.which("node") and shutil.which("bend")


@unittest.skipUnless(_tools_ok(), "lean/node/bend not available")
class TestStatementEquivalence(unittest.TestCase):
    """bend model vs emitted lean model, same law statement, same samples."""

    @classmethod
    def setUpClass(cls):
        cls.models = runner._models("M0") | runner._models("M1")
        cls.tmp = Path(tempfile.mkdtemp(prefix="s8-equiv-"))
        cls.machines = {}

    def _law_eval(self, law: dict, milestone: str, rec: dict) -> tuple[list, list]:
        """(lean bools, bend bools) over the same samples in the same order."""
        model_text, kind, facts, _ = self.models[REPO / law["facts"]]
        witness = rec.get("witness")
        if kind == "codec":
            zero = {b["name"]: ("0x00" if b["type"] == "Bytes"
                                else {f["name"]: "0x" + "00" * f["width"]
                                      for f in F.header_fields(facts)})
                    for b in law["statement"]["forall"]}
            samples = ([witness] if witness else []) + [zero]
            text, n = equiv.codec_eval_lem(facts, law, model_text, samples)
            p = self.tmp / f"{law['law_id']}_equiv.lean"
            p.write_text(text)
            lean = equiv.run_lean_eval(p, n * len(samples))
            bend = equiv.codec_bend_bools(REPO / law["facts"], law, samples)
            return lean, bend
        m = machine_gen.LMachine(facts)
        e = laws02.LEmit(m)
        _, defs, _, _ = e.emit(law, rec["status"] == "REFUTED", witness)
        defs = e.view_defs() + defs
        samples = equiv.samples_for(law, m, witness)
        self.assertTrue(samples, f"{law['law_id']}: no evaluable sample")
        text, n = equiv.machine_eval_lem(e, law, model_text, defs, samples)
        p = self.tmp / f"{law['law_id']}_equiv.lean"
        p.write_text(text)
        lean = equiv.run_lean_eval(p, n * len(samples))
        fp = REPO / law["facts"]
        if fp not in self.machines:
            from holon import mpipeline
            self.machines[fp] = mpipeline.CompiledMachine.build(fp)
        bend = []
        for w in samples:
            r = self.machines[fp].evaluate(law, w)
            bend += r["premises"] + r["claims"]
        return lean, bend

    def test_laws_agree(self):
        problems = []
        seen = 0
        for milestone in ("M0", "M1"):
            for law in ir.load_laws_any(milestone, REPO):
                rec_p = REPO / "results" / milestone / f"{law['law_id']}.json"
                if not rec_p.exists():
                    continue
                rec = json.loads(rec_p.read_text())
                if rec.get("status") not in ("PROVED", "REFUTED"):
                    continue
                try:
                    lean, bend = self._law_eval(law, milestone, rec)
                except Exception as e:
                    problems.append(f"{law['law_id']}: eval error {e}")
                    continue
                seen += 1
                if lean != bend:
                    problems.append(f"{law['law_id']}: lean {lean} != bend {bend}")
        self.assertTrue(seen, "no laws evaluated")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
