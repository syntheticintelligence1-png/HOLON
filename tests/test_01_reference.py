"""Self-checks of the frozen oracle: facts, laws, registry and predictions agree.

These pass on a fresh kit. They exist so that a wrong fact or a wrong prediction
is caught before any agent builds on it.
"""
import random
import unittest

from tests._util import FACTS, LAWS_DIR, ROOT, law_ids, load_json, load_law, predictions, validate
from tests.reference import ref_ir as I
from tests.reference import ref_model as M
from tests.reference import ref_mutate as X

# Independent transcription of the header table (BatchHeaderCodecV0/V1 doc comments).
APPENDIX_C = [
    (0, 1, "version"), (1, 9, "batchIndex"), (9, 17, "l1MessagePopped"),
    (17, 25, "totalL1MessagePopped"), (25, 57, "dataHash"), (57, 89, "blobVersionedHash"),
    (89, 121, "prevStateHash"), (121, 153, "postStateHash"), (153, 185, "withdrawRootHash"),
    (185, 217, "sequencerSetVerifyHash"), (217, 249, "parentBatchHash"), (249, 257, "lastBlockNumber"),
]


def rand_header(rng, facts):
    return {k: bytes(rng.randrange(256) for _ in range(w)) for k, w in M.widths(facts).items()}


def pinned(law, h):
    h = dict(h)
    for p in law["statement"].get("assume", []):
        a, b = p["eq"]
        h[a["field"]] = M.unhex(b["bytes"])
    return h


class TestReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = M.load_facts(FACTS)

    def test_facts_schema(self):
        validate(self.facts, "facts")

    def test_layouts_match_appendix_c(self):
        for fn, version, length in [("enc_sol", 0, 249), ("enc_sol", 1, 257), ("enc_sol", 2, 257),
                                    ("enc_go_v0", 0, 249), ("enc_go_v1", 1, 257)]:
            lay = M.layout(self.facts, fn, version)
            self.assertEqual(len(lay), length, fn)
            for lo, hi, name in APPENDIX_C:
                if lo >= length:
                    continue
                for i in range(lo, hi):
                    cell = lay[i]
                    if name == "version" and fn.startswith("enc_go"):
                        self.assertEqual(cell, ["const", int(fn[-1])], (fn, i))
                    elif name == "sequencerSetVerifyHash" and fn == "enc_sol":
                        self.assertEqual(cell, ["const", 0], (fn, i))
                    else:
                        self.assertEqual(cell, ["field", name, i - lo], (fn, version, i))

    def test_laws_schema_and_registry(self):
        reg = load_json(LAWS_DIR / "REGISTRY.json")
        self.assertEqual(sorted(reg["statements"]), law_ids())
        self.assertEqual(reg["facts_sha256"], M.facts_sha256(FACTS))
        for lid in law_ids():
            law = load_law(lid)
            validate(law, "law_ir")
            self.assertEqual(law["facts_sha256"], M.facts_sha256(FACTS), lid)
            self.assertEqual(I.statement_hash(law), reg["statements"][lid], lid)

    def test_predictions_cover_all_laws(self):
        self.assertEqual(sorted(predictions()), law_ids())

    def test_predictions_agree_with_reference(self):
        rng = random.Random(20261010)
        for lid, pred in predictions().items():
            law = load_law(lid)
            if law["statement"]["forall"][0]["type"] == "Header":
                outcomes = [I.check(law, self.facts, {"h": pinned(law, rand_header(rng, self.facts))})["claim"]
                            for _ in range(300)]
                if pred["status"] == "PROVED":
                    self.assertTrue(all(outcomes), lid)
                else:
                    self.assertIn(False, outcomes, lid)
            else:
                b = bytes(250)
                r = I.check(law, self.facts, {"b": b})
                self.assertIs(r["claim"], False)
                self.assertEqual((r["lhs"], r["rhs"]), (True, False))

    def test_v2_difference_is_byte_zero(self):
        law = load_law("L_par_hdr_v2")
        h = pinned(law, {k: bytes(w) for k, w in M.widths(self.facts).items()})
        r = I.check(law, self.facts, {"h": h})
        diffs = [i for i, (x, y) in enumerate(zip(r["lhs"], r["rhs"])) if x != y]
        self.assertEqual(diffs, [0])
        self.assertEqual((r["lhs"][0], r["rhs"][0]), (2, 1))

    def test_mutations_are_consistent_with_reference(self):
        muts = load_json(ROOT / "predictions" / "M0_mutations.json")["mutations"]
        rng = random.Random(4)
        for m in muts:
            facts = X.apply(self.facts, m["edit"])
            for lid, allowed in m["expect"].items():
                law = load_law(lid)
                if law["statement"]["forall"][0]["type"] == "Header":
                    cands = [pinned(law, {k: bytes(w) for k, w in M.widths(facts).items()})]
                    cands += [pinned(law, rand_header(rng, facts)) for _ in range(300)]
                    refuted = any(I.check(law, facts, {"h": h})["claim"] is False for h in cands)
                else:
                    refuted = any(
                        I.check(law, facts, {"b": (bytes([v]) + bytes(n - 1)) if n else b""})["claim"] is False
                        for v in range(6) for n in (0, 1, 248, 249, 250, 256, 257, 258))
                self.assertEqual(refuted, "REFUTED" in allowed, (m["id"], lid))


if __name__ == "__main__":
    unittest.main()
