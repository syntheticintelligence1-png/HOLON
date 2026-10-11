"""P2: the generated Bend model, compiled and executed, agrees with the oracle."""
import hashlib
import random
import tempfile
import unittest
from pathlib import Path

from tests._util import FACTS, ROOT, run_bend
from tests.reference import ref_model as M

N = 40


def headers(rng, facts, versions):
    out = []
    for v in versions:
        out.append({k: bytes(w) for k, w in M.widths(facts).items()} | {"version": bytes([v])})
        out.append({k: b"\xff" * w for k, w in M.widths(facts).items()} | {"version": bytes([v])})
        for _ in range(N):
            h = {k: bytes(rng.randrange(256) for _ in range(w)) for k, w in M.widths(facts).items()}
            h["version"] = bytes([v])
            out.append(h)
    return out


def byte_strings(rng):
    out = [b""]
    for v in (0, 1, 2, 3, 255):
        for n in (1, 2, 248, 249, 250, 256, 257, 258):
            out.append(bytes([v]) + bytes(rng.randrange(256) for _ in range(n - 1)))
    return out


class TestModelEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon import model_eval
        cls.ev = model_eval
        cls.facts = M.load_facts(FACTS)
        cls.rng = random.Random(99)

    def _check(self, fn, inputs, as_json, ref):
        res = self.ev.eval_batch(fn, [as_json(x) for x in inputs], facts_path=str(FACTS))
        self.assertTrue(res["engine"].startswith("bend"), res["engine"])
        art = Path(res["artifact"])
        self.assertTrue(art.is_file(), art)
        self.assertEqual(hashlib.sha256(art.read_bytes()).hexdigest(), res["artifact_sha256"])
        self.assertTrue(str(res["source"]).endswith(".bend"))
        self.assertEqual(len(res["outputs"]), len(inputs))
        for x, got in zip(inputs, res["outputs"]):
            self.assertEqual(got, M.value_to_json(ref(x)), (fn, as_json(x)))
        return res

    def test_encoders(self):
        hs = headers(self.rng, self.facts, (0, 1, 2))
        self._check("enc_sol", hs, M.header_to_json, lambda h: M.encode(self.facts, "enc_sol", h))
        for fn in ("enc_go_v0", "enc_go_v1"):
            self._check(fn, hs, M.header_to_json, lambda h, fn=fn: M.encode(self.facts, fn, h))

    def test_predicates_and_decoder(self):
        bs = byte_strings(self.rng)
        bs += [M.encode(self.facts, "enc_sol", h) for h in headers(self.rng, self.facts, (0, 1, 2))[:30]]
        for fn in ("ok_sol", "ok_go"):
            self._check(fn, bs, M.hexb, lambda b, fn=fn: M.predicate(self.facts, fn, b))
        self._check("dec_go", bs, M.hexb, lambda b: M.decode(self.facts, "dec_go", b))

    def test_view(self):
        hs = headers(self.rng, self.facts, (0, 1, 2))
        self._check("view", hs, M.header_to_json, lambda h: M.view(self.facts, h))

    def test_artifact_is_the_compiled_source(self):
        res = self.ev.eval_batch("ok_go", ["0x00"], facts_path=str(FACTS))
        src = Path(res["source"])
        src = src if src.is_absolute() else ROOT / src
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "m.mjs"
            code, log = run_bend([src, "-o", out])
            self.assertEqual(code, 0, log)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), res["artifact_sha256"],
                             "the evaluated artifact is not the compilation of the reported model source")


if __name__ == "__main__":
    unittest.main()
