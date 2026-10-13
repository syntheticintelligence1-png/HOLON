"""I19: Solidity frontend II, storage families, transitions, cost terms and principal predicates (whitepaper §10.1
Solidity, §7.7 step 5; BUILD_PLAN I19). This docstring is the contract for this module and for
tests_m2/test_coverage.py. The frozen instruments are spec/M2/lib/extract_rollup.json (what to extract),
spec/M2/lib/link.json (the cross-language roles) and tests_m2/fixtures/extract_transitions/ (the planted toy).

I19 extends I17's frontend (holon/frontends/solidity). It reuses I17's compile (W1), spans (W2) and terms (W4),
documented in the docstring of tests_m2/test_extract_solidity_layout.py.

CLI
  python -m holon extract solidity --sidecar spec/M2/lib/extract_rollup.json [--out PATH] [--check]
    The sidecar has the I17 sidecar format, plus "transitions": {"contract", "commit_interfaces"}. A sidecar with
    "transitions" yields a transitions document; one with "edges" yields I17's layout document. G1 re-extracts
    every extraction sidecar, so G1 covers spec/M2/facts/morph_rollup.extracted.json.

Transitions document (holon-facts/0.3, frontend "solidity", kind "transitions"; spec/schemas/facts_0_3.schema.json
gains this branch). Canonical JSON (indent=2, sorted keys):
  {"facts_version": "holon-facts/0.3", "extraction": {"frontend": "solidity", "kind": "transitions", ...provenance},
   "target": {...}, "contract": "<name>",
   "constants": {"<NAME>": "<value as 0x-hex or decimal string>"}       every constant of the contract
   "storage": [{"name", "slot", "offset", "kind": "scalar"|"mapping"|"array",
                "key": "<type>" (mappings), "value": "<type>", "width": bits (scalars and mapping values of
                elementary type), "fields": [{"name", "type", "width"}] (struct values)}]
              Every state variable the contract declares itself, in declaration order. The slot and offset come from
              the compiler's storage layout (solc outputSelection "storageLayout"), not from counting. Constants and
              immutables are not storage.
   "actions": [ per external or public FunctionDefinition of the contract, sorted by name:
     {"name", "selector", "src",
      "modifiers": ["<name>", ...] in order,
      "principal": null | {"modifier": "<name>", "predicate": <term>},
          the first modifier whose require tests the caller (msg.sender or _msgSender()); its predicate is that
          require's condition. Caller-test terms are ["caller"], a storage read is ["storage", name], a mapping read
          ["map", <base>, <key>], and an external call ["call", "<Interface>.<function>", args...].
      "guards": [{"src", "kind": "modifier"|"require"|"revert", "reason": "<string literal>"|"<error name>"|null,
                  "expr": <term>}]
          every require/revert reached on the function's paths: modifiers inlined in order, internal and library
          calls inlined (I17's walk). Order: first reach in a depth-first walk of the body. One entry per span.
      "effects": [{"family": "<storage name>", "src"}]   storage writes reached, sorted by (src, family)
      "cost": {"terms": [{"loop": "<span of the loop statement>", "iters": <term>}]}
          one term per loop reached whose body writes no storage; a loop that writes storage is debt (test_coverage)
      "edges": [{"kind": "HASH"|"COMMIT", "fn": "keccak256"|"sha256"|"blobhash"|"<Interface>.<function>", "src"}]
          HASH: a keccak256 or sha256 call. COMMIT: blobhash, and an external call to an interface the sidecar's
          commit_interfaces names.
     }]}
  A reason is the require's string literal; a custom error's name for revert E(); null when there is none.

Rules
  - The frontend reads only the compiler's output (AST and storage layout) and the source bytes. It never reads a
    fact document, a law or a result (an audit hook checks this, as for I17).
  - holon/frontends/solidity/*.py holds no target vocabulary. Interface names come only from the sidecar.
  - The output is byte-identical across runs. A difference from the M1 hand-written facts is reported, never fixed
    in facts/ or spec/M1/facts/.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon

SIDE = ROOT / "spec" / "M2" / "lib" / "extract_rollup.json"
DOC = ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"
M1 = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
TOY = ROOT / "tests_m2" / "fixtures" / "extract_transitions" / "toy"
MODELLED = ("commitBatch", "commitState", "commitBatchWithProof", "revertBatch", "challengeState", "proveState",
            "finalizeBatch", "setPause")
R = "contracts/contracts/l1/rollup/Rollup.sol"


def doc() -> dict:
    if not DOC.is_file():
        raise AssertionError(f"{DOC.relative_to(ROOT)} is missing: python -m holon extract solidity --sidecar "
                             "spec/M2/lib/extract_rollup.json")
    return load_json(DOC)


def action(d: dict, name: str) -> dict:
    hits = [a for a in d["actions"] if a["name"] == name]
    if len(hits) != 1:
        raise AssertionError(f"action {name}: {len(hits)} entries")
    return hits[0]


def covers(span: str, src: str) -> bool:
    """span ('unit:lo-hi' or 'unit:n') holds the line of src ('unit:n')."""
    u, _, rng = span.rpartition(":")
    su, _, line = src.rpartition(":")
    if u != su or not line.isdigit():
        return False
    lo, _, hi = rng.partition("-")
    return int(lo) <= int(line) <= int(hi or lo)


def mentions(term, name: str) -> bool:
    if isinstance(term, list):
        return (len(term) >= 2 and term[0] == "storage" and term[1] == name) or any(mentions(t, name) for t in term)
    return False


class TestToy(unittest.TestCase):
    """Construction check: the planted contract, whose extraction is known by construction."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i19-"))
        cls.out = cls.tmp / "vault.extracted.json"
        cls.proc = run_holon(["extract", "solidity", "--sidecar", str(TOY / "extract_vault.json"),
                              "--source", str(TOY), "--out", str(cls.out)], timeout=600)
        cls.d = json.loads(cls.out.read_text()) if cls.out.is_file() else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.assertIsNotNone(self.d, self.proc.stdout[-1500:] + self.proc.stderr[-1500:])

    def test_storage_families(self):
        got = [(s["name"], s["slot"], s["kind"], s.get("value"), s.get("width")) for s in self.d["storage"]]
        self.assertEqual(got, [("owner", 0, "scalar", "address", 160), ("ext", 1, "scalar", "address", 160),
                               ("total", 2, "scalar", "uint256", 256), ("h", 3, "mapping", "bytes32", 256),
                               ("s", 4, "mapping", "struct Vault.S", None), ("paused", 5, "scalar", "bool", 8)])
        s = [x for x in self.d["storage"] if x["name"] == "s"][0]
        self.assertEqual([(f["name"], f["width"]) for f in s["fields"]], [("x", 64), ("y", 160)])

    def test_actions_guards_and_principals(self):
        self.assertEqual([a["name"] for a in self.d["actions"]], ["drain", "poke", "put", "setPaused"])
        put = action(self.d, "put")
        self.assertEqual([(g["src"], g["kind"], g["reason"]) for g in put["guards"]],
                         [("src/Vault.sol:23", "modifier", "not owner"), ("src/Vault.sol:33", "require", "paused"),
                          ("src/Vault.sol:34", "require", "k zero")])
        self.assertEqual([g["expr"] for g in put["guards"]],
                         [["==", ["caller"], ["storage", "owner"]], ["!", ["storage", "paused"]],
                          [">", ["param", "k"], 0]])
        self.assertEqual(put["principal"], {"modifier": "onlyOwner", "predicate": ["==", ["caller"], ["storage", "owner"]]})
        poke = action(self.d, "poke")
        self.assertEqual(poke["principal"], {"modifier": "onlyOk", "predicate": ["call", "IExt.ok", ["caller"]]})

    def test_effects_cost_and_edges(self):
        put = action(self.d, "put")
        self.assertEqual(put["effects"], [{"family": "total", "src": "src/Vault.sol:39"},
                                          {"family": "h", "src": "src/Vault.sol:40"}])
        self.assertEqual(put["cost"]["terms"], [{"loop": "src/Vault.sol:36-38", "iters": ["param", "n"]}])
        self.assertEqual(put["edges"], [{"kind": "HASH", "fn": "keccak256", "src": "src/Vault.sol:40"}])
        drain = action(self.d, "drain")
        self.assertEqual(drain["cost"]["terms"], [])          # its loop writes storage: debt, not a cost term
        self.assertEqual(drain["effects"], [{"family": "h", "src": "src/Vault.sol:53"}])

    def test_two_runs_are_byte_identical(self):
        out2 = self.tmp / "again.json"
        p = run_holon(["extract", "solidity", "--sidecar", str(TOY / "extract_vault.json"), "--source", str(TOY),
                       "--out", str(out2)], timeout=600)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertEqual(out2.read_bytes(), self.out.read_bytes())


class TestMorph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = doc()
        cls.m1 = load_json(M1)

    def test_storage_families_are_the_24_declared_at_slots_151_to_174(self):
        """I19-P1 (the slot range is stated in BUILD_PLAN I19; the names, kinds, types and widths are scored)."""
        want = [("submitterContract", "scalar", "address", 160), ("finalizationPeriodSeconds", "scalar", "uint256", 256),
                ("proofWindow", "scalar", "uint256", 256), ("__maxNumTxInChunk", "scalar", "uint256", 256),
                ("messageQueue", "scalar", "address", 160), ("verifier", "scalar", "address", 160),
                ("lastFinalizedBatchIndex", "scalar", "uint256", 256), ("lastCommittedBatchIndex", "scalar", "uint256", 256),
                ("isChallenger", "mapping", "bool", 8), ("finalizedStateRoots", "mapping", "bytes32", 256),
                ("committedBatches", "mapping", "bytes32", 256), ("batchDataStore", "mapping", "struct IRollup.BatchData", None),
                ("withdrawalRoots", "mapping", "bool", 8), ("challenges", "mapping", "struct IRollup.BatchChallenge", None),
                ("batchChallengeReward", "mapping", "uint256", 256), ("inChallenge", "scalar", "bool", 8),
                ("batchChallenged", "scalar", "uint256", 256), ("revertReqIndex", "scalar", "uint256", 256),
                ("proofRewardPercent", "scalar", "uint256", 256), ("proveRemaining", "scalar", "uint256", 256),
                ("committedStateRoots", "mapping", "bytes32", 256), ("rollupDelayPeriod", "scalar", "uint256", 256),
                ("batchBlobVersionedHashes", "mapping", "bytes32", 256), ("legacyCutoverBatchIndex", "scalar", "uint256", 256)]
        got = [(s["name"], s["kind"], s.get("value"), s.get("width")) for s in self.d["storage"]]
        self.assertEqual(got, want)
        self.assertEqual([s["slot"] for s in self.d["storage"]], list(range(151, 175)))
        st = {s["name"]: s for s in self.d["storage"]}
        self.assertEqual([(f["name"], f["width"]) for f in st["challenges"]["fields"]],
                         [("batchIndex", 64), ("challenger", 160), ("challengeDeposit", 256), ("startTime", 256),
                          ("challengeSuccess", 8), ("finished", 8)])
        self.assertEqual([(f["name"], f["width"]) for f in st["batchDataStore"]["fields"]],
                         [("originTimestamp", 256), ("finalizeTimestamp", 256), ("blockNumber", 256), ("submitter", 160)])

    def test_modelled_guards_are_found_in_order_and_only_the_out_of_contract_ones_are_missing(self):
        """I19-P2: every M1 require of the 8 modelled actions whose span lies in the extraction's closure is matched by
        span to an extracted guard of the same action, in the same relative order. The unmatched M1 guards are
        exactly the 2 'oracle:' verifier rules (commitBatchWithProof, proveState) and the 4 inside
        L1MessageQueueWithGasPriceOracle.sol (commitBatch, commitState, commitBatchWithProof, finalizeBatch)."""
        unmatched = []
        for name in MODELLED:
            ext = action(self.d, name)["guards"]
            ma = [x for x in self.m1["actions"] if x["name"] == name][0]
            pos = []
            for g in ma["guards"]:
                if "require" not in g:
                    continue
                idx = [i for i, e in enumerate(ext) if covers(e["src"], g.get("src") or "")]
                if idx:
                    pos.append(idx[0])
                else:
                    unmatched.append((name, (g.get("src") or "").split(":")[0].rsplit("/", 1)[-1]))
            with self.subTest(action=name):
                self.assertEqual(pos, sorted(pos), "matched guards out of order")
        self.assertEqual(sorted(unmatched), sorted([
            ("commitBatchWithProof", "oracle"), ("proveState", "oracle"),
            ("commitBatch", "L1MessageQueueWithGasPriceOracle.sol"), ("commitState", "L1MessageQueueWithGasPriceOracle.sol"),
            ("commitBatchWithProof", "L1MessageQueueWithGasPriceOracle.sol"), ("finalizeBatch", "L1MessageQueueWithGasPriceOracle.sol")]))

    def test_committed_batches_checks_read_the_raw_family(self):
        """I19-P3: the M1 guards the facts annotate as committedBatches abstractions (:311 in the three commits,
        :436 in revertBatch) match extracted guards whose expression reads the committedBatches family (an
        abstraction difference: the model encodes them over LCI)."""
        for name, line in (("commitBatch", 311), ("commitState", 311), ("commitBatchWithProof", 311), ("revertBatch", 436)):
            with self.subTest(action=name):
                g = [e for e in action(self.d, name)["guards"] if covers(e["src"], f"{R}:{line}")]
                self.assertTrue(g and mentions(g[0]["expr"], "committedBatches"), g)

    def test_principal_predicates(self):
        """I19-P4: onlyOwner, the active-submitter check and the challenger check are extracted as principal
        predicates; finalizeBatch and commitBatchWithProof have none (anyone)."""
        own = action(self.d, "revertBatch")["principal"]
        self.assertEqual(own["modifier"], "onlyOwner")
        self.assertTrue(mentions(own["predicate"], "_owner") and "caller" in json.dumps(own["predicate"]))
        self.assertEqual(action(self.d, "setPause")["principal"]["modifier"], "onlyOwner")
        for name in ("commitBatch", "commitState", "proveState"):
            with self.subTest(action=name):
                p = action(self.d, name)["principal"]
                self.assertEqual(p, {"modifier": "onlyActiveSubmitter",
                                     "predicate": ["call", "ISubmitter.isActive", ["caller"]]})
        self.assertEqual(action(self.d, "challengeState")["principal"],
                         {"modifier": "onlyChallenger", "predicate": ["map", ["storage", "isChallenger"], ["caller"]]})
        for name in ("finalizeBatch", "commitBatchWithProof"):
            with self.subTest(action=name):
                self.assertIsNone(action(self.d, name)["principal"])

    def test_loop_bounds_become_cost_terms(self):
        """I19-P5: the three commits each have exactly one cost term, the L1-message-hash loop at Rollup.sol:936,
        whose iteration count is the input's numL1Messages; finalizeBatch has exactly one, the loop at :744."""
        for name in ("commitBatch", "commitState", "commitBatchWithProof"):
            with self.subTest(action=name):
                t = action(self.d, name)["cost"]["terms"]
                self.assertEqual(len(t), 1, t)
                self.assertTrue(t[0]["loop"].startswith(f"{R}:936"), t)
                self.assertIn("numL1Messages", json.dumps(t[0]["iters"]))
        t = action(self.d, "finalizeBatch")["cost"]["terms"]
        self.assertEqual(len(t), 1, t)
        self.assertTrue(t[0]["loop"].startswith(f"{R}:744"), t)

    def test_hash_and_commit_edges(self):
        """I19-P6: commitBatch has a COMMIT edge blobhash and a HASH edge at the header hash
        (BatchHeaderCodecV0.sol:242); commitState has a COMMIT edge blobhash (its no-blob check); proveState and
        commitBatchWithProof have a COMMIT edge IRollupVerifier.verifyAggregateProof."""
        def fns(name, kind):
            return {e["fn"] for e in action(self.d, name)["edges"] if e["kind"] == kind}
        self.assertIn("blobhash", fns("commitBatch", "COMMIT"))
        self.assertIn("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:242",
                      {e["src"] for e in action(self.d, "commitBatch")["edges"] if e["kind"] == "HASH"})
        self.assertIn("blobhash", fns("commitState", "COMMIT"))
        for name in ("proveState", "commitBatchWithProof"):
            with self.subTest(action=name):
                self.assertIn("IRollupVerifier.verifyAggregateProof", fns(name, "COMMIT"))

    def test_extraction_is_deterministic_and_matches_the_committed_file(self):
        """Construction: --check against the committed document."""
        p = run_holon(["extract", "solidity", "--sidecar", str(SIDE), "--check"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
