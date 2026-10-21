"""I63 (= I28a): deployment history, extracted from the code and cross-checked on chain (whitepaper §10.1 deployment
history, Def 4.3 S_k/A_k and the MIG edges, §3.5 naturality; BUILD_PLAN I28; docs/HUMAN_ANSWERS.md Q18: code-derived
history is the model, the on-chain timeline an independent check). This docstring is the contract; its sha256 is the
key's thresholds.contract_docstring_sha256.

Scope. I63 is the history half of BUILD_PLAN I28, pulled forward under its own key as I59 was for I23 (prereg keys are
plain numbers). It extracts the versions of the target contract from the target repository's tags, the reinitializers,
the storage-layout changes and the migration (MIG) edges between versions, and it cross-checks them against the proxy's
on-chain upgrade timeline. It states no law, changes no rule catalog and reads no law, record or fact document of any
milestone. The laws half keeps the key I28 (versioned machines step_k/run_k, PAR-init instances, O9, D4, the F12.5
version-transition obligation and G11V's in-flight inhabitants) and follows after I26's catalog (the roadmap split of
2026-10-21: catalog-bumping iterations go one at a time).

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl). The key's thresholds hold their sha256s, checked by TestInstrument:
  - spec/M3/lib/history.json, the sidecar: the target repository, head commit and pinned tags, the contract (source
    unit, name, build paths), the compiler configurations ("deployed": optimizer runs 200, I23's Surprise 1;
    "foundry": 999999; "hardhat": 10000; all cancun, bytecodeHash none) and the version configuration ("deployed"),
    the proxy, the event topics, the upgrade source (I59's index and its window), the RPC and the output paths;
  - spec/M3/lib/history_basis.json, computed at the prereg by tests_m3/_i63.py: every ref, its builds, the versions
    and the migration edges (H1-H6);
  - tests_m3/_i63.py itself (H1-H8, independently of holon/). The predictions are decided on its recomputation of H8
    from the committed receipts and code, never on holon's timeline.

Inputs. The target repository is config/holon.json extract.sources[<sidecar target.repo>] (a git repository; I63 reads
its tags and objects, never its working tree). The compiler is config replay.solc (sha256 replay.solc_sha256), the
Solidity dependencies <replay.sol_deps>/node_modules (tree sha256 replay.sol_deps_sha256: OpenZeppelin 4.9.3); a
mismatch refuses. The upgrade transactions are I59's: every log item of the sidecar's upgrades.path
(results/M2/historical/index.json, an LFS file whose content hash, the sha256 of its canonical JSON without the
index_sha256 field, is the sidecar's upgrades.index_sha256) whose topic is the sidecar's Upgraded topic, that is the
proxy's upgrades in I59's window (blocks upgrades.window.from_block to to_block).

H1 Refs. The sidecar's tags (every tag of the repository at the prereg whose commit's tree holds the contract's source
   unit, pinned to its commit): each must exist and peel to its pinned commit, and its tree must hold the unit, else
   refused (exit 2); ordered by the commit's committer time, then by tag name; then the sidecar's head commit as ref
   "head". Tags the sidecar does not pin are ignored. A ref names its commit and time.
H2 Builds. A ref is materialized from git (the commit's tree under the contract's build paths; no checkout) and
   compiled once per configuration: solc --standard-json, base path the materialized tree, include path the
   dependencies, settings {evmVersion, optimizer {enabled true, runs}, metadata {bytecodeHash}}, the contract's
   deployedBytecode (object, immutableReferences, linkReferences), its storageLayout, and every unit's AST. The code
   identity of a build is its runtime code with every immutable and link range zeroed, then without solc's trailing
   CBOR metadata (the last two bytes give the map's length n; it is removed when 2 + n fits and the map starts with a
   CBOR map head 0xa0..0xb7). A build records the identity's sha256, the code's length and the ranges (sorted). A ref
   that does not compile records the error and joins no version.
H3 Initializers. Every function of the contract's own ContractDefinition that carries the modifier `initializer`
   (version 1) or `reinitializer(k)`: {name, version, line}, by version then name. A reinitializer whose argument is
   not one integer literal makes its ref an extraction error.
H4 Layout. The version configuration's storageLayout, one entry per state variable: its declaring contract (the
   ContractDefinition whose state variable declaration has the entry's astId), label, slot, offset, size in bytes and
   type signature (label, encoding, size; key, value and base types; struct members with label, slot, offset and type,
   recursively), ordered by slot, offset, contract and label.
H5 Layout diff, from layout a to layout b. An entry is identified by (declaring contract, label).
   persisted: same slot, offset and type signature. moved: another slot or offset. retyped: same position, other type
   (kind "struct_extended" for a mapping whose struct value gains members after its old ones, recursively through
   mapping values; else "changed"). added / removed: only in b / only in a. gap_resized: a "__gap" array (an inplace
   array) whose position or size changed. overlap: an entry of b that is not persisted and whose byte span meets the
   span of an entry of a that is neither a __gap nor at the same position in b (a word-or-smaller entry spans its
   bytes; a larger one whole slots). compatible iff nothing is moved, every retyped entry is struct_extended and
   nothing overlaps. A rename is a removal plus an overlapping addition.
H6 Versions and MIG edges. A version is a maximal run of consecutive compiled refs whose code identity under the
   version configuration is equal: {id V1.., refs, commit and time of its first ref, code (every configuration's
   identity sha256, length, ranges), source_sha256 (the unit's text), layout, layout_sha256 (sha256 of
   json.dumps(layout, sort_keys=True), Python's default separators), reinitializers}. Code that returns to an earlier
   identity starts a new version (a deployment of it then matches two versions; no identity recurs in the basis). A
   MIG edge joins consecutive versions: {from, to, introduced (the reinitializers of `to` whose version exceeds every
   reinitializer version of `from`), layout (H5's diff), compatible, in_flight}. in_flight is what the new version
   reads of the old state: every entry of `to`'s layout that is not a __gap and whose byte span meets the span of an
   entry of `from`'s layout that is not a __gap, as {entry "<contract>.<label>", kind "unchanged" (persisted) |
   "retyped" (same contract, label and position, another type) | "reinterpreted" (any other entry), reads (the old
   entries it meets, sorted)}, sorted by entry. In the raw-storage view (holon.machine) an upgrade leaves storage as
   it is, and the MIG edge's migration is the introduced reinitializers' calls. Edges join consecutive versions only;
   a timeline that skips versions composes them (I28's work).
H7 On-chain snapshot. For every upgrade transaction (I59's Upgraded log items, by block then log index) holon reads,
   through the sidecar's RPC: the receipt, stored in I59's canonical form (holon.historical.store's receipt fields,
   lowercase hex, quantities without leading zeros, compact canonical JSON), so that its sha256 is I59's receipt item
   sha256 for that transaction; the implementation's runtime code at the latest block; the block's timestamp
   (informational). From the receipt, of the logs the proxy emitted (log address == the sidecar's proxy) in log-index
   order: the Upgraded log at the item's log index (topic 1: the new implementation), every Initialized log (data:
   the version, a uint8 in a word) and every AdminChanged log (data: the previous and the new admin, a word each);
   and the receipt's from and contractAddress. The match of a deployed code against the basis: every (version,
   configuration) whose build's identity sha256 equals the sha256 of the deployed code with that build's ranges
   zeroed and its CBOR metadata stripped, in version order, then by configuration name (tests_m3/_i63.match).
   Receipts are anchored by I59's hashes and the last implementation's code by I23's record (R1); the other
   implementations' code has no anchor in the repository, so the build's review reads it again from a second provider.
H8 Timeline. Per upgrade: the matches; its version (the one version every match names, null when none or more than
   one); its expected Initialized versions (the reinitializer versions of its version above the baseline, the larger
   of the top reinitializer version of the previous matched upgrade's version and the highest Initialized version
   logged by any earlier upgrade transaction, 0 when neither exists; null when its version is null); its Initialized
   versions as logged, sorted ascending; consistent iff expected is not null and the two are equal. A downgrade: a
   matched upgrade whose version precedes the version of an earlier matched upgrade; "after" names the highest such
   earlier version. Coverage debt, by block: every upgrade no build matches (reason "no version's build matches") and
   every upgrade that builds of several versions match (reason "builds of several versions match"), never smoothed
   over (Q18). Never deployed: every version that appears in no upgrade's matches.

Commands
  python -m holon history extract [--check]    write gen/M3/history/morph_rollup.json (H1-H6)
  python -m holon history fetch [--check]      write results/M3/history/onchain.json, receipts/<tx>.json and
                                               code/<implementation>.hex (H7; network); --check verifies the snapshot
                                               offline (receipts against I59's hashes, code files against
                                               onchain.json) and writes nothing
  python -m holon history timeline [--check]   write results/M3/history/timeline.json (H7's match, H8)
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input), nothing
  written; 3 an extraction or fetch error, nothing written. Outputs are canonical JSON (sorted keys, indent 1, a final
  newline) except the receipts (I59's compact canonical bytes, no newline), and byte-identical across runs; the
  snapshot is fetched once, then only checked.

Formats
  gen/M3/history/morph_rollup.json: {"history_version": "holon-history/0.1", "sidecar": {"path", "sha256"},
    "target", "contract", "version_config", "refs": [{ref, commit, time, error, builds}], "versions": [H6],
    "edges": [H6]}. Its refs, versions and edges equal the basis's.
  results/M3/history/onchain.json: {"onchain_version": "holon-onchain/0.1", "sidecar": {"path", "sha256"},
    "index": {"path", "sha256"}, "rpc": {"host", "methods"}, "proxy": {"address", "chain"}, "window",
    "upgrades": [{"block", "time", "tx", "log_index", "receipt_sha256", "implementation", "initialized" (in log
    order), "admin_changed": [{"previous", "new"}], "from", "contract_address", "code_sha256", "code_length"}]};
    addresses lower case and 0x-prefixed. results/M3/history/receipts/<tx>.json as H7;
    results/M3/history/code/<implementation>.hex (hex, no 0x, newline).
  results/M3/history/timeline.json: {"timeline_version": "holon-timeline/0.1", "history": {"path", "sha256"},
    "onchain": {"path", "sha256"}, "upgrades": [{"block", "tx", "implementation", "matches": [{version, config}],
    "version", "expected_initialized", "initialized", "consistent"}], "downgrades": [{"block", "version", "after"}],
    "coverage_debt": [{"block", "implementation", "reason"}], "never_deployed": [version ids]}.

Rules for every session (AGENTS.md): no law, record or fact document of any milestone is read or written by an I63
command; never edit spec/M2, laws, results/M0-M2, gen/M0-M2, replay/, holon/rules/ or a frozen file; holon/ never
imports tests_m3. I63's outcome paths are gen/M3/history/, results/M3/history/ and docs/iterations/I63.md.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import unittest

from tests_m3._m3 import ROOT, canonical_json, file_sha256, item, load_json, predictions, run_holon

SIDE = ROOT / "spec" / "M3" / "lib" / "history.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "history_basis.json"
HISTORY = ROOT / "gen" / "M3" / "history" / "morph_rollup.json"
ONCHAIN = ROOT / "results" / "M3" / "history" / "onchain.json"
RECEIPTS = ROOT / "results" / "M3" / "history" / "receipts"
CODE = ROOT / "results" / "M3" / "history" / "code"
TIMELINE = ROOT / "results" / "M3" / "history" / "timeline.json"
INDEX = ROOT / "results" / "M2" / "historical" / "index.json"
TRANS = ROOT / "results" / "M2" / "historical" / "trans.json"
ZERO = "0x" + "0" * 40
DECODED = ("implementation", "initialized", "admin_changed", "from", "contract_address")
_CACHE: dict = {}


def need(p):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i63 as I
    return I


def index_upgrades() -> list:
    """I59's Upgraded log items: [(block, log_index, tx)] by block then log index."""
    return instrument().upgrade_items(load_json(SIDE), load_json(INDEX))


def code_of(impl: str) -> bytes:
    return bytes.fromhex((CODE / f"{impl.lower()}.hex").read_text().strip())


def snap() -> list:
    """The instrument's decoding of the committed snapshot (receipts checked against I59's hashes), computed once."""
    if "snap" not in _CACHE:
        _CACHE["snap"] = instrument().snapshot(ROOT)
    return _CACHE["snap"]


def recomputed() -> dict:
    """The instrument's H8 over the committed snapshot and the frozen basis, computed once."""
    if "timeline" not in _CACHE:
        _CACHE["timeline"] = instrument().timeline(ROOT, need(BASIS))
    return _CACHE["timeline"]


class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are."""

    def test_the_key_pins_the_instruments(self):
        """The key's thresholds pin the sidecar, the basis and this contract by sha256, and the sidecar's and the
        basis's numbers are the key's."""
        th = predictions("I63")["thresholds"]
        side, b = load_json(SIDE), need(BASIS)
        self.assertEqual(file_sha256(SIDE), th["history_sidecar_sha256"])
        self.assertEqual(file_sha256(BASIS), th["history_basis_sha256"])
        doc = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(doc.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        self.assertEqual((len(side["tags"]), len(b["refs"]), len(b["versions"]), len(b["edges"])),
                         (th["tags"], th["refs"], th["versions"], th["mig_edges"]))
        self.assertEqual([f"{e['from']}->{e['to']}" for e in b["edges"] if not e["compatible"]],
                         th["incompatible_edges"])
        self.assertEqual({k: c["optimizer_runs"] for k, c in side["compiler_configs"].items()}, th["compiler_configs"])
        self.assertEqual((side["version_config"], side["proxy"]["address"], side["upgrades"]["count"],
                          side["rpc"]["url"]), (th["version_config"], th["proxy"], th["upgrades"], th["rpc"]))

    def test_the_sidecar_and_the_basis_agree(self):
        b = need(BASIS)
        self.assertEqual(b["sidecar_sha256"], file_sha256(SIDE))
        self.assertEqual(b["basis_version"], "holon-history-basis/0.2")
        self.assertEqual(b["version_config"], load_json(SIDE)["version_config"])

    def test_the_index_is_i59s(self):
        """The upgrade source is I59's index (LFS content, not a pointer: git lfs pull --include
        results/M2/historical/index.json): its recomputed content hash (sha256 of its canonical JSON without
        index_sha256) is the sidecar's upgrades.index_sha256, and it holds the sidecar's count of Upgraded items."""
        self.assertGreater(INDEX.stat().st_size, 1000, "results/M2/historical/index.json is an LFS pointer")
        doc = load_json(INDEX)
        declared = doc.pop("index_sha256")
        want = load_json(SIDE)["upgrades"]["index_sha256"]
        self.assertEqual((hashlib.sha256(canonical_json(doc)).hexdigest(), declared), (want, want))
        self.assertEqual(len(index_upgrades()), load_json(SIDE)["upgrades"]["count"])

    def test_the_refs_recompute(self):
        """H1 recomputed from the repository equals the basis's refs (ref, commit, time)."""
        I = instrument()
        side, cfg = load_json(SIDE), load_json(ROOT / "config" / "holon.json")
        repo = cfg["extract"]["sources"][side["target"]["repo"]]
        got = [{k: r[k] for k in ("ref", "commit", "time")} for r in I.refs(side, repo)]
        self.assertEqual(got, [{k: r[k] for k in ("ref", "commit", "time")} for r in need(BASIS)["refs"]])

    def test_the_basis_recomputes(self):
        """H1-H6, recomputed from the repository by the instrument, equal the frozen basis (every ref built under
        every configuration)."""
        I = instrument()
        self.assertEqual(I.basis(), need(BASIS))


class TestHistory(unittest.TestCase):
    """holon history extract writes H1-H6 exactly as the instrument computes them."""

    def test_extract_reproduces(self):
        p = run_holon(["history", "extract", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_the_history_is_the_basis(self):
        h, b = need(HISTORY), need(BASIS)
        self.assertEqual(h["history_version"], "holon-history/0.1")
        self.assertEqual(h["sidecar"], {"path": "spec/M3/lib/history.json", "sha256": file_sha256(SIDE)})
        for k in ("target", "contract", "version_config", "refs", "versions", "edges"):
            with self.subTest(field=k):
                self.assertEqual(h[k], b[k])

    def test_the_module_is_generic(self):
        """holon.frontends.solidity.history names no Morph contract, function, address, host or configuration (case
        insensitive): every such name comes from the sidecar. No file of holon/ imports tests_m3 or names the
        instrument."""
        src = (ROOT / "holon" / "frontends" / "solidity" / "history.py").read_text()
        for word in ("Rollup", "initialize2", "initialize3", "initialize4", "importGenesisBatch", "morph",
                     "0x759894", "0x213ce2", "tenderly", "999999"):
            self.assertIsNone(re.search(re.escape(word), src, re.I), word)
        for p in sorted((ROOT / "holon").rglob("*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertIsNone(re.search(r"^\s*(from|import)\s+tests_m3\b", text, re.M))
                self.assertNotIn("_i63", text)


class TestOnchain(unittest.TestCase):
    """H7's snapshot: every upgrade of I59's index, read on chain, its receipts I59's."""

    def test_fetch_check_reproduces_offline(self):
        p = run_holon(["history", "fetch", "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_the_snapshot_covers_every_upgrade(self):
        o, side = need(ONCHAIN), load_json(SIDE)
        self.assertEqual(o["onchain_version"], "holon-onchain/0.1")
        self.assertEqual(o["sidecar"], {"path": "spec/M3/lib/history.json", "sha256": file_sha256(SIDE)})
        self.assertEqual(o["index"], {"path": side["upgrades"]["path"], "sha256": side["upgrades"]["index_sha256"]})
        self.assertEqual([(u["block"], u["log_index"], u["tx"]) for u in o["upgrades"]], index_upgrades())
        for u in o["upgrades"]:
            with self.subTest(block=u["block"]):
                code = code_of(u["implementation"])
                self.assertTrue(len(code) > 0)
                self.assertEqual((u["code_sha256"], u["code_length"]), (hashlib.sha256(code).hexdigest(), len(code)))

    def test_the_receipts_are_i59s(self):
        """Every upgrade's committed receipt is I59's: its sha256 is I59's receipt item sha256 for that transaction,
        and the snapshot's receipt_sha256."""
        hashes = instrument().receipt_hashes(load_json(INDEX))
        for u in need(ONCHAIN)["upgrades"]:
            with self.subTest(tx=u["tx"]):
                raw = (RECEIPTS / f"{u['tx']}.json").read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), hashes[u["tx"]])
                self.assertEqual(u["receipt_sha256"], hashes[u["tx"]])

    def test_the_snapshot_reads_the_receipts(self):
        """The snapshot's implementation, Initialized versions, AdminChanged logs, sender and contractAddress are the
        instrument's decoding of the committed receipts."""
        ups = need(ONCHAIN)["upgrades"]
        self.assertEqual(len(ups), len(snap()))
        for u, s in zip(ups, snap()):
            with self.subTest(block=u["block"]):
                self.assertEqual({k: u[k] for k in DECODED}, {k: s[k] for k in DECODED})


class TestTimeline(unittest.TestCase):
    """H8: holon's timeline is the instrument's recomputation."""

    def test_timeline_reproduces(self):
        p = run_holon(["history", "timeline", "--check"], timeout=1200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_the_timeline_is_the_instruments(self):
        t = need(TIMELINE)
        self.assertEqual(t["timeline_version"], "holon-timeline/0.1")
        self.assertEqual(t["history"], {"path": "gen/M3/history/morph_rollup.json", "sha256": file_sha256(HISTORY)})
        self.assertEqual(t["onchain"], {"path": "results/M3/history/onchain.json", "sha256": file_sha256(ONCHAIN)})
        e = recomputed()
        for k in ("upgrades", "downgrades", "coverage_debt", "never_deployed"):
            with self.subTest(field=k):
                self.assertEqual(t[k], e[k])


class TestPredictions(unittest.TestCase):
    """I63's predictions (spec/M3/predictions.json key I63), decided on the instrument's recomputation."""

    def ups(self) -> list:
        u = recomputed()["upgrades"]
        self.assertEqual(len(u), load_json(SIDE)["upgrades"]["count"])
        return u

    def version_of_ref(self, ref: str) -> str:
        return next(v["id"] for v in need(BASIS)["versions"] if ref in v["refs"])

    def test_p1_the_first_upgrade_is_the_proxys_creation(self):
        """I63-P1: the first upgrade (block 20996846) is in the proxy's creation transaction (its receipt's
        contractAddress is the proxy) and sets an implementation no version matches (coverage debt, "no version's
        build matches"); its transaction logs no Initialized and exactly one AdminChanged, from the zero address to the
        transaction's sender."""
        item("I63", "I63-P1")
        first, dec = self.ups()[0], snap()[0]
        self.assertEqual(first["block"], 20996846)
        self.assertEqual(dec["contract_address"], load_json(SIDE)["proxy"]["address"])
        self.assertEqual(first["matches"], [])
        self.assertIn({"block": first["block"], "implementation": first["implementation"],
                       "reason": "no version's build matches"}, recomputed()["coverage_debt"])
        self.assertEqual(dec["initialized"], [])
        self.assertEqual(dec["admin_changed"], [{"previous": ZERO, "new": dec["from"]}])

    def test_p2_the_middle_upgrades_match_one_tagged_version(self):
        """I63-P2: each upgrade from the second to the eleventh matches exactly one version, and only under the
        "deployed" configuration (optimizer runs 200), never under the checkout's declared foundry or hardhat
        configuration."""
        item("I63", "I63-P2")
        for u in self.ups()[1:-1]:
            with self.subTest(block=u["block"]):
                self.assertEqual(len({m["version"] for m in u["matches"]}), 1, u["matches"])
                self.assertEqual({m["config"] for m in u["matches"]}, {"deployed"})

    def test_p3_mainnet_starts_on_the_v040_line(self):
        """I63-P3: the first matched upgrade deploys the version of ref v0.4.0, and the versions of v0.2.0-beta and
        v0.2.1 appear in no match (so the V2->V3 edge never runs on this proxy)."""
        item("I63", "I63-P3")
        first = next(u for u in self.ups() if u["version"] is not None)
        self.assertEqual(first["version"], self.version_of_ref("v0.4.0"))
        for ref in ("v0.2.0-beta", "v0.2.1"):
            with self.subTest(ref=ref):
                self.assertIn(self.version_of_ref(ref), recomputed()["never_deployed"])

    def test_p4_no_downgrade(self):
        """I63-P4: at least two upgrades are matched, and no matched upgrade's version precedes the version of an
        earlier matched upgrade."""
        item("I63", "I63-P4")
        self.assertGreaterEqual(len([u for u in self.ups() if u["version"] is not None]), 2)
        self.assertEqual(recomputed()["downgrades"], [])

    def test_p5_reinitializers_run_inside_their_upgrades(self):
        """I63-P5: before the last upgrade, at least one upgrade is matched and every matched upgrade is consistent
        (H8), and the upgrade transactions log each of the Initialized versions 1, 2 and 3 (initialize, initialize2,
        initialize3)."""
        item("I63", "I63-P5")
        ups = self.ups()[:-1]
        matched = [u for u in ups if u["version"] is not None]
        self.assertTrue(matched)
        for u in matched:
            with self.subTest(block=u["block"]):
                self.assertTrue(u["consistent"], (u["expected_initialized"], u["initialized"]))
        self.assertLessEqual({1, 2, 3}, {k for u in ups for k in u["initialized"]})


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change."""

    def test_the_last_upgrade_is_i23s(self):
        """I63-R1: the last upgrade sets I23's implementation (decoded from its receipt, which is I59's), whose runtime
        code hashes to I23's code_sha256 (results/M2/historical/trans.json: block 26031669, 0x213ce22b...,
        53ec0662...), and it matches the head's version under the "deployed" configuration alone (I23's Surprise 1,
        restated through H7)."""
        item("I63", "I63-R1")
        imp = load_json(TRANS)["implementation"]
        last = recomputed()["upgrades"][-1]
        self.assertEqual((last["block"], last["implementation"]), (imp["upgrade_block"], imp["address"]))
        self.assertEqual((last["block"], last["implementation"]),
                         (26031669, "0x213ce22b487b71ac68a1b5b12d2b93d1af30ea1d"))
        self.assertEqual(hashlib.sha256(code_of(last["implementation"])).hexdigest(), imp["code_sha256"])
        head = next(v["id"] for v in need(BASIS)["versions"] if "head" in v["refs"])
        self.assertEqual(last["matches"], [{"config": "deployed", "version": head}])

    def test_outcome_commits_touch_no_law_record_or_catalog(self):
        """I63-R2 (part): no commit that writes an I63 outcome path changes a law, a record, a rule catalog, the I63
        instruments, an earlier milestone's spec or output, another M3 output, replay/ or a frozen root. Needs the real
        checkout's history and at least one such commit: a missing .git, or no outcome commit yet, is a failure, never
        a skip."""
        item("I63", "I63-R2")

        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        outs = tuple(predictions("I63")["outcome_paths"])
        forbidden = ("laws/", "replay/", "holon/rules/", "spec/M1/", "spec/M2/", "spec/M3/lib/history", "gen/M0/",
                     "gen/M1/", "gen/M2/", "results/M0/", "results/M1/", "results/M2/", "facts/", "predictions/",
                     "schemas/", "tests/", "bend/probes/", "AGENTS.md", "tools/freeze.py", "docs/M0_SPEC.md",
                     "docs/BEND_PRIMER.md", "FROZEN.sha256")
        commits, cur = [], None
        for line in git("log", "--no-merges", "--format=@%H", "--name-only", "HEAD").splitlines():
            if line.startswith("@"):
                cur = (line[1:], [])
                commits.append(cur)
            elif line.strip() and cur is not None:
                cur[1].append(line.strip())
        commits = [(c, names) for c, names in commits if any(n.startswith(outs) for n in names)]
        self.assertTrue(commits, "no commit writes an I63 outcome path")
        for c, names in commits:
            bad = [n for n in names if n.startswith(forbidden)
                   or (n.startswith(("gen/M3/", "results/M3/")) and not n.startswith(outs))]
            self.assertEqual(bad, [], f"commit {c[:12]}")


if __name__ == "__main__":
    unittest.main()
