"""M2 S2: the translated Bend agrees with the generated M0 model on the
M0 sample set (acceptance 2).

The M0 sample set is the one tests/test_20_model_eval.py uses: headers() with
rng seed 99 over versions {0,1,2} plus byte_strings() and 30 real encodings.
"""
import json
import os
import random
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from holon import model_eval, facts as F  # noqa: E402
from tests.reference import ref_model as M  # noqa: E402
from tests.test_20_model_eval import headers, byte_strings  # noqa: E402

BEND_SRC = ROOT / "gen" / "M2" / "sol_layout" / "morph_header.bend"
MJS = ROOT / "build" / "m2_sol_layout_morph_header.mjs"
HAND = ROOT / "facts" / "morph_header.json"


def _path():
    extra = [str(Path.home() / ".holon" / "bin"), str(Path.home() / ".local" / "node22" / "bin")]
    os.environ["PATH"] = os.pathsep.join(extra + [os.environ.get("PATH", "")])


def _compile():
    if not MJS.exists() or MJS.stat().st_mtime < BEND_SRC.stat().st_mtime:
        from holon import bend
        MJS.parent.mkdir(parents=True, exist_ok=True)
        r = bend.run([str(BEND_SRC), "-o", str(MJS)], cwd=BEND_SRC.parent)
        if r.code != 0 or not MJS.exists():
            raise AssertionError(f"bend failed to compile {BEND_SRC}: {r.out[:2000]}")


class _Jobs:
    def __init__(self, artifact):
        self.artifact = str(artifact)
        self.driver = model_eval.DRIVER
        self.node = model_eval.bend.config().get("node", "node")

    def __call__(self, fn, arg_t, inputs):
        jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": v}} for v in inputs]
        p = subprocess.run([self.node, str(self.driver)], input=json.dumps({"module": self.artifact, "jobs": jobs}),
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            raise AssertionError(p.stderr[-2000:])
        return [r[0] for r in json.loads(p.stdout)["results"]]


class TestTranslatedBend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _path()
        _compile()
        cls.facts = M.load_facts(HAND)
        rng = random.Random(99)
        cls.hs = headers(rng, cls.facts, (0, 1, 2))
        cls.bs = byte_strings(rng) + [M.encode(cls.facts, "enc_sol", h) for h in cls.hs[:30]]
        cls.mine = _Jobs(MJS)
        cls.model = model_eval.CompiledModel.build(str(HAND))

    def _model_jobs(self, fn, arg_t, inputs):
        jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}],
                 "env": {"x": model_eval.value_in(arg_t, v, self.model.facts)}} for v in inputs]
        return [r[0] for r in self.model.run_jobs(jobs)]

    def test_enc_sol_agrees(self):
        hexs = [M.header_to_json(h) for h in self.hs]
        hj = [model_eval.header_in(self.facts, h) for h in hexs]
        mine = self.mine("enc_sol", "Header", hj)
        want = self._model_jobs("enc_sol", "Header", hexs)
        self.assertEqual(mine, want)

    def test_ok_sol_agrees(self):
        hexs = [M.hexb(b) for b in self.bs]
        bj = [model_eval.bytes_in(h) for h in hexs]
        mine = self.mine("ok_sol", "Bytes", bj)
        want = self._model_jobs("ok_sol", "Bytes", hexs)
        self.assertEqual(mine, want)

    def test_view_agrees(self):
        hexs = [M.header_to_json(h) for h in self.hs]
        hj = [model_eval.header_in(self.facts, h) for h in hexs]
        mine = self.mine("view", "Header", hj)
        want = self._model_jobs("view", "Header", hexs)
        self.assertEqual(mine, want)

    def test_dec_sol_roundtrip(self):
        """dec_sol_fields(enc_sol(h)) == view(h), and dec_sol(b) is None iff !ok_sol(b)."""
        hexs = [M.header_to_json(h) for h in self.hs]
        hj = [model_eval.header_in(self.facts, h) for h in hexs]
        encs = self.mine("enc_sol", "Header", hj)
        views = self.mine("view", "Header", hj)
        decs = self.mine("dec_sol_fields", "Bytes", encs)
        # Rollup encodes sequencerSetVerifyHash as constant 0 (constant call arg),
        # so decode∘encode yields zeros in that slot, not the header's field.
        ext = json.loads((ROOT / "spec" / "M2" / "extracted" / "header_layouts.json").read_text())
        getters = ext["functions"]["dec_sol"]["getters"]
        for h, v, d in zip(hj, views, decs):
            vv = list(v)
            ver = h["$hdr"]["version_0"]
            for i, g in enumerate(g for g in getters if F.when_ok(g.get("when"), ver)):
                if g["name"] == "sequencerSetVerifyHash":
                    vv[i] = [0] * g["width"]
            self.assertEqual(d, vv)
        bj = [model_eval.bytes_in(M.hexb(b)) for b in self.bs]
        oks = self.mine("ok_sol", "Bytes", bj)
        decs = self.mine("dec_sol", "Bytes", bj)
        for b, ok, d in zip(self.bs, oks, decs):
            self.assertEqual(d is None, not ok, (b.hex()[:20], ok, d))

    def test_no_escape_hatches(self):
        from holon import bend
        bad = bend.escape_hatches(BEND_SRC.read_text())
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
