"""I9 follow-up (not preregistered): the Lean model and the compiled Bend model compute the same values.

Agreement on the 8 verdicts says little about the models on other inputs. Here every fact function is run on
seeded sample inputs (headers at versions 0, 1, 2, 3 and 255; byte strings of lengths around 249 and 257) by
the compiled Bend model (`bend model.bend -o model.mjs`, run in node; holon.model_eval), and each output is
then stated about the Lean model as a theorem proved by `decide` on closed terms. An undefined Bend byte
(outside 0..255) must be an undefined Lean cell (`none`). One Lean file, checked like the law files.
"""
import hashlib
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json

FACTS = ROOT / "facts" / "morph_header.json"
SEED = 20261012


def lean_cells(xs: list[int]) -> str:
    return "[" + ", ".join(f"some 0x{x:02x}" if 0 <= x <= 255 else "none" for x in xs) + "]"


def lean_value(ty: str, v) -> str:
    if ty == "Bytes":
        return f"({lean_cells(v)} : Model.Bytes)"
    if ty == "Bool":
        return "true" if v else "false"
    if ty == "Fields":
        return "([" + ", ".join(lean_cells(x) for x in v) + "] : Model.Fields)"
    if ty == "MaybeFields":
        return "(none : Option Model.Fields)" if v is None else \
            "(some [" + ", ".join(lean_cells(x) for x in v["$some"]) + "] : Option Model.Fields)"
    raise ValueError(ty)


class TestLeanAndBendModelsAgree(unittest.TestCase):
    def test_sample_outputs_agree(self):
        ME = holon_module("holon.model_eval")
        F = holon_module("holon.facts")
        L = holon_module("holon.lean")
        LM = holon_module("holon.gen.lean_model")
        facts = load_json(FACTS)
        fsha = hashlib.sha256(FACTS.read_bytes()).hexdigest()
        widths = F.widths(facts)
        rnd = random.Random(SEED)
        headers = []
        for v in (0, 1, 2, 3, 255, 1):
            h = {n: "0x" + bytes(rnd.randrange(256) for _ in range(w)).hex() for n, w in widths.items()}
            h["version"] = f"0x{v:02x}"
            headers.append(h)
        headers[-1] = {n: "0x" + "ff" * w for n, w in widths.items()} | {"version": "0x01"}
        strings = [b""]
        for v, n in ((0, 249), (0, 250), (0, 248), (1, 257), (1, 249), (2, 257), (2, 256), (3, 257), (255, 1)):
            strings.append(bytes([v]) + bytes(rnd.randrange(256) for _ in range(n - 1)))
        tmp = Path(tempfile.mkdtemp(prefix="holon-lean-diff-"))
        try:
            m = ME.CompiledModel.build(FACTS, source=tmp / "eval" / "morph_header.bend")
            fns = sorted(facts["functions"])
            jobs, plan = [], []
            for i, h in enumerate(headers):
                for fn in fns:
                    if F.fn_types(facts, fn)[0] == "Header":
                        jobs.append({"terms": [{"call": fn, "args": [{"var": "x"}]}],
                                     "env": {"x": ME.header_in(facts, h)}})
                        plan.append((fn, f"hdr{i}"))
            for i, s in enumerate(strings):
                for fn in fns:
                    if F.fn_types(facts, fn)[0] == "Bytes":
                        jobs.append({"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": list(s)}})
                        plan.append((fn, f"str{i}"))
            outs = m.run_jobs(jobs)
            lines = ["set_option maxRecDepth 20000", "", LM.emit_model(facts, fsha)]
            for i, h in enumerate(headers):
                cells = ", ".join(f"{n}_{k} := 0x{b:02x}" for n in widths for k, b in enumerate(bytes.fromhex(h[n][2:])))
                lines += [f"noncomputable def hdr{i} : Model.Hdr := {{ {cells} }}", ""]
            for i, s in enumerate(strings):
                lines += [f"def str{i} : Model.Bytes := {lean_cells(list(s))}", ""]
            n = 0
            for (fn, arg), (v,) in zip(plan, outs):
                if isinstance(v, dict) and "error" in v:
                    self.fail(f"Bend model evaluation of {fn}({arg}) failed: {v['error']}")
                ty = F.fn_types(facts, fn)[1]
                lines += [f"theorem agree_{n} : Model.{fn} {arg} = {lean_value(ty, v)} := by decide", ""]
                n += 1
            src = "\n".join(lines) + "\n"
            r = L.check_text(src, tmp / "lean")
            self.assertEqual(r["result"], "checked", L._first_error(r["out"], 20))
            self.assertEqual(len(r["theorems"]), n)
            self.assertGreaterEqual(n, 50)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
