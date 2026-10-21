"""I63 (= I28a): deployment history, extracted from the code and cross-checked on chain (whitepaper §10.1 deployment
history, Def 4.3 S_k/A_k and the MIG edges, §3.5 naturality; BUILD_PLAN I28; docs/HUMAN_ANSWERS.md Q18: code-derived
history is the model, the on-chain timeline an independent check). This docstring is the contract.

Scope. I63 is the history half of BUILD_PLAN I28, pulled forward under its own key as I59 was for I23 (prereg keys are
plain numbers). It extracts the versions of the target contract from the target repository's tags, the reinitializers,
the storage-layout changes and the migration (MIG) edges between versions, and it cross-checks them against the proxy's
on-chain upgrade timeline. It states no law, changes no rule catalog and reads no law, record or fact document of any
milestone. The laws half keeps the key I28 (versioned machines step_k/run_k, PAR-init instances, O9, D4, the F12.5
version-transition obligation and G11V's in-flight inhabitants) and follows after I26's catalog (the roadmap split of
2026-10-21: catalog-bumping iterations go one at a time).

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl):
  - spec/M3/lib/history.json, the sidecar: the target repository and head commit, the contract (source unit, name,
    build paths), the compiler configurations ("deployed": optimizer runs 200, I23's Surprise 1; "foundry": 999999;
    "hardhat": 10000; all cancun, bytecodeHash none) and the version configuration ("deployed"), the proxy, the event
    topics, the upgrade source (I59's index) and the RPC;
  - spec/M3/lib/history_basis.json, computed at the prereg by tests_m3/_i63.py, which writes rules H1-H6 a second time,
    independently of holon/: every ref, its builds, the versions and the migration edges;
  - tests_m3/_i63.py itself (rules H1-H7, independently of holon/).

Inputs. The target repository is config/holon.json extract.sources[<sidecar target.repo>] (a git repository; I63 reads
its tags and objects, never its working tree). The compiler is config replay.solc (its sha256 replay.solc_sha256), the
Solidity dependencies <replay.sol_deps>/node_modules. The upgrade transactions are I59's: every log item of
results/M2/historical/index.json (an LFS file; its sha256 is the sidecar's upgrades.index_sha256) whose topic is the
sidecar's Upgraded topic.

H1 Refs. Every tag of the repository whose commit's tree holds the contract's source unit, ordered by the commit's
   committer time, then by tag name; then the sidecar's head commit as ref "head". A ref names its commit and time.
H2 Builds. A ref is materialized from git (the commit's tree under the contract's build paths; no checkout) and
   compiled once per configuration: solc --standard-json, base path the materialized tree, include path the
   dependencies, settings {evmVersion, optimizer {enabled true, runs}, metadata {bytecodeHash}}, the contract's
   deployedBytecode (object, immutableReferences, linkReferences), its storageLayout, and every unit's AST. The code
   identity of a build is its runtime code with every immutable and link range zeroed, then without solc's trailing
   CBOR metadata (the last two bytes give the map's length n; it is removed when 2 + n fits and the map starts with a
   CBOR map head 0xa0..0xb7). A build records the identity's sha256, the code's length and the ranges. A ref that does
   not compile records the error and joins no version.
H3 Initializers. Every function of the contract's own ContractDefinition that carries the modifier `initializer`
   (version 1) or `reinitializer(k)` with one integer literal k: {name, version, line}, by version then name.
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
   nothing overlaps.
H6 Versions and MIG edges. A version is a maximal run of consecutive compiled refs whose code identity under the
   version configuration is equal: {id V1.., refs, commit and time of its first ref, code (every configuration's
   identity sha256, length, ranges), source_sha256 (the unit's text), layout, layout_sha256, reinitializers}. A MIG edge
   joins consecutive versions: {from, to, introduced (the reinitializers of `to` whose version exceeds every
   reinitializer version of `from`), layout (H5's diff), compatible, in_flight (the persisted entries as
   "<contract>.<label>", sorted)}. In the raw-storage view (holon.machine), an upgrade leaves storage as it is and the
   MIG edge's migration is the introduced reinitializers' calls, made by the proxy admin in the upgrade transaction
   (OpenZeppelin's upgradeAndCall); in_flight is what the new version reads of the old state.
H7 On-chain snapshot. For every upgrade transaction (I59's Upgraded log items, by block then log index) holon reads,
   through the sidecar's RPC: the receipt, and of its logs those the proxy emitted: Upgraded (topic 1: the new
   implementation), Initialized (data: the version, a uint8 in a word) and AdminChanged (data: the previous and the new
   admin, a word each); the implementation's runtime code at the latest block; the block's timestamp. The match of a deployed code against the basis: every (version,
   configuration) whose build's identity sha256 equals the sha256 of the deployed code with that build's ranges zeroed
   and its CBOR metadata stripped (tests_m3/_i63.match).
H8 Timeline. Per upgrade: the matches; its version (the one version every match names, null when none or more than
   one); its expected Initialized versions (the versions of the reinitializers its version introduces over the
   version of the previous matched upgrade, every reinitializer of its version for the first upgrade); its
   Initialized versions as logged; consistent iff the two are equal. A downgrade: a matched upgrade whose version
   precedes the version of an earlier matched upgrade. Coverage debt: every unmatched upgrade (never smoothed over:
   Q18). Never deployed: every version no upgrade matches.

Commands
  python -m holon history extract [--check]    write gen/M3/history/morph_rollup.json (H1-H6)
  python -m holon history fetch [--check]      write results/M3/history/onchain.json and
                                               results/M3/history/code/<implementation>.hex (H7; network);
                                               --check verifies the snapshot's hashes offline and writes nothing
  python -m holon history timeline [--check]   write results/M3/history/timeline.json (H7's match, H8)
  Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input), nothing
  written; 3 an extraction or fetch error, nothing written. Outputs are canonical JSON (sorted keys, indent 1, a final
  newline) and byte-identical across runs; the snapshot is the one fetched file, written once and then only checked.

Formats
  gen/M3/history/morph_rollup.json: {"history_version": "holon-history/0.1", "sidecar": {"path", "sha256"},
    "target", "contract", "version_config", "refs": [{ref, commit, time, error, builds}], "versions": [H6],
    "edges": [H6]}. Its refs, versions and edges equal the basis's.
  results/M3/history/onchain.json: {"onchain_version": "holon-onchain/0.1", "sidecar": {"path", "sha256"},
    "index": {"path", "sha256"}, "rpc", "proxy", "upgrades": [{"block", "time", "tx", "log_index", "implementation",
    "code_sha256", "code_length", "initialized": [k..], "admin_changed": [{"previous", "new"}]}]}, logs in log-index
    order; every address is lower case and 0x-prefixed, every hash 0x-prefixed except the sha256s; the code of every
    implementation is results/M3/history/code/<implementation>.hex (hex, no 0x, newline).
  results/M3/history/timeline.json: {"timeline_version": "holon-timeline/0.1", "history": {"path", "sha256"},
    "onchain": {"path", "sha256"}, "upgrades": [{"block", "tx", "implementation", "matches": [{version, config}],
    "version", "expected_initialized", "initialized", "consistent"}], "downgrades": [{"block", "version", "after"}],
    "coverage_debt": [{"block", "implementation", "reason"}], "never_deployed": [version ids]}.

Rules for every session (AGENTS.md): no law, record or fact document of any milestone is read or written by an I63
command; never edit spec/M2, laws, results/M0-M2, gen/M0-M2, replay/, holon/rules/ or a frozen file; I63's outcome
paths are gen/M3/history/ and results/M3/history/.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import unittest

from tests_m3._m3 import ROOT, file_sha256, item, load_json, run_holon

SIDE = ROOT / "spec" / "M3" / "lib" / "history.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "history_basis.json"
HISTORY = ROOT / "gen" / "M3" / "history" / "morph_rollup.json"
ONCHAIN = ROOT / "results" / "M3" / "history" / "onchain.json"
CODE = ROOT / "results" / "M3" / "history" / "code"
TIMELINE = ROOT / "results" / "M3" / "history" / "timeline.json"
INDEX = ROOT / "results" / "M2" / "historical" / "index.json"


def need(p):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def instrument():
    import tests_m3._i63 as I
    return I


def index_upgrades() -> list:
    """I59's Upgraded log items: [(block, log_index, tx)] by block then log index."""
    side = load_json(SIDE)
    idx = load_json(INDEX)
    topic = side["events"]["Upgraded"]
    return sorted((it["block"], it["log_index"], it["tx"]) for it in idx["items"]
                  if it.get("kind") == "log" and it.get("topic") == topic)


def code_of(impl: str) -> bytes:
    return bytes.fromhex((CODE / f"{impl.lower()}.hex").read_text().strip())


class TestInstrument(unittest.TestCase):
    """The frozen inputs are what they say they are."""

    def test_the_sidecar_and_the_basis_agree(self):
        b = need(BASIS)
        self.assertEqual(b["sidecar_sha256"], file_sha256(SIDE))
        self.assertEqual(b["basis_version"], "holon-history-basis/0.1")
        self.assertEqual(b["version_config"], load_json(SIDE)["version_config"])

    def test_the_index_is_i59s(self):
        """The upgrade source is I59's index at the sha256 the sidecar names (LFS content, not a pointer: git lfs pull
        --include results/M2/historical/index.json)."""
        self.assertGreater(INDEX.stat().st_size, 1000, "results/M2/historical/index.json is an LFS pointer")
        self.assertEqual(load_json(INDEX)["index_sha256"], load_json(SIDE)["upgrades"]["index_sha256"])
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
        """holon.frontends.solidity.history names no Morph contract, function, slot or address: every such name comes
        from the sidecar."""
        src = (ROOT / "holon" / "frontends" / "solidity" / "history.py").read_text()
        for word in ("Rollup", "initialize2", "initialize3", "initialize4", "importGenesisBatch", "morph",
                     "0x759894", "0x213ce2", "tenderly", "999999"):
            self.assertNotIn(word, src, word)


class TestOnchain(unittest.TestCase):
    """H7's snapshot: every upgrade of I59's index, read on chain."""

    def test_fetch_check_reproduces_offline(self):
        p = run_holon(["history", "fetch", "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_the_snapshot_covers_every_upgrade(self):
        o = need(ONCHAIN)
        self.assertEqual(o["onchain_version"], "holon-onchain/0.1")
        self.assertEqual(o["sidecar"], {"path": "spec/M3/lib/history.json", "sha256": file_sha256(SIDE)})
        self.assertEqual(o["index"]["sha256"], load_json(SIDE)["upgrades"]["index_sha256"])
        self.assertEqual([(u["block"], u["log_index"], u["tx"]) for u in o["upgrades"]], index_upgrades())
        for u in o["upgrades"]:
            with self.subTest(block=u["block"]):
                code = code_of(u["implementation"])
                self.assertTrue(len(code) > 0)
                self.assertEqual((u["code_sha256"], u["code_length"]), (hashlib.sha256(code).hexdigest(), len(code)))
                self.assertTrue(all(isinstance(k, int) and 1 <= k <= 255 for k in u["initialized"]))



class TestTimeline(unittest.TestCase):
    """H8, recomputed by the instrument from the snapshot and the basis."""

    def expected(self) -> dict:
        I = instrument()
        b, o = need(BASIS), need(ONCHAIN)
        order = {v["id"]: i for i, v in enumerate(b["versions"])}
        reinit = {v["id"]: v["reinitializers"] for v in b["versions"]}
        ups, prev, seen = [], None, []
        for u in o["upgrades"]:
            m = I.match(b, code_of(u["implementation"]))
            vs = sorted({x["version"] for x in m})
            ver = vs[0] if len(vs) == 1 else None
            exp = None
            if ver is not None:
                top = max((x["version"] for x in reinit[prev]), default=0) if prev else 0
                exp = sorted(x["version"] for x in reinit[ver] if x["version"] > top) if prev else \
                    sorted(x["version"] for x in reinit[ver])
            ups.append({"block": u["block"], "tx": u["tx"], "implementation": u["implementation"], "matches": m,
                        "version": ver, "expected_initialized": exp, "initialized": sorted(u["initialized"]),
                        "consistent": exp is not None and exp == sorted(u["initialized"])})
            if ver is not None:
                seen.append((u["block"], ver))
                prev = ver
        downs = []
        for i, (blk, ver) in enumerate(seen):
            later_than = [v for _, v in seen[:i] if order[v] > order[ver]]
            if later_than:
                downs.append({"block": blk, "version": ver, "after": max(later_than, key=lambda v: order[v])})
        debt = [{"block": u["block"], "implementation": u["implementation"], "reason": "no version's build matches"}
                for u in ups if not u["matches"]] + \
               [{"block": u["block"], "implementation": u["implementation"],
                 "reason": "builds of several versions match"} for u in ups if u["matches"] and u["version"] is None]
        never = [v["id"] for v in b["versions"] if v["id"] not in {u["version"] for u in ups}]
        return {"upgrades": ups, "downgrades": downs, "coverage_debt": sorted(debt, key=lambda d: d["block"]),
                "never_deployed": never}

    def test_timeline_reproduces(self):
        p = run_holon(["history", "timeline", "--check"], timeout=1200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_the_timeline_is_the_instruments(self):
        t = need(TIMELINE)
        self.assertEqual(t["timeline_version"], "holon-timeline/0.1")
        self.assertEqual(t["history"], {"path": "gen/M3/history/morph_rollup.json", "sha256": file_sha256(HISTORY)})
        self.assertEqual(t["onchain"], {"path": "results/M3/history/onchain.json", "sha256": file_sha256(ONCHAIN)})
        e = self.expected()
        for k in ("upgrades", "downgrades", "coverage_debt", "never_deployed"):
            with self.subTest(field=k):
                self.assertEqual(t[k], e[k])


class TestPredictions(unittest.TestCase):
    """I63's predictions (spec/M3/predictions.json key I63), decided on the committed outputs."""

    def timeline(self) -> dict:
        return need(TIMELINE)

    def version_of_ref(self, ref: str) -> str:
        return next(v["id"] for v in need(BASIS)["versions"] if ref in v["refs"])

    def test_p1_the_first_upgrade_is_the_placeholder(self):
        """I63-P1: the first Upgraded log is the proxy's creation over a placeholder implementation: it matches no
        version (coverage debt), its transaction logs no Initialized and one AdminChanged from the zero address."""
        item("I63", "I63-P1")
        first_t, first_o = self.timeline()["upgrades"][0], need(ONCHAIN)["upgrades"][0]
        self.assertEqual(first_t["matches"], [])
        self.assertEqual([d["block"] for d in self.timeline()["coverage_debt"]][:1], [first_t["block"]])
        self.assertEqual(first_o["initialized"], [])
        self.assertEqual([a["previous"] for a in first_o["admin_changed"]], ["0x" + "0" * 40])

    def test_p2_every_later_upgrade_matches_one_tagged_version(self):
        """I63-P2: every upgrade after the first matches exactly one version, and only under the "deployed"
        configuration (optimizer runs 200), never under the checkout's declared foundry or hardhat configuration; the
        coverage debt is the first upgrade alone."""
        item("I63", "I63-P2")
        ups = self.timeline()["upgrades"]
        for u in ups[1:]:
            with self.subTest(block=u["block"]):
                self.assertEqual(len({m["version"] for m in u["matches"]}), 1, u["matches"])
                self.assertEqual({m["config"] for m in u["matches"]}, {"deployed"})
        self.assertEqual([d["block"] for d in self.timeline()["coverage_debt"]], [ups[0]["block"]])

    def test_p3_mainnet_starts_on_the_v040_line(self):
        """I63-P3: the first matched upgrade deploys the version of ref v0.4.0, and the versions of v0.2.0-beta and
        v0.2.1 are never deployed (so the V2->V3 edge never runs on this proxy)."""
        item("I63", "I63-P3")
        t = self.timeline()
        first = next(u for u in t["upgrades"] if u["version"] is not None)
        self.assertEqual(first["version"], self.version_of_ref("v0.4.0"))
        for ref in ("v0.2.0-beta", "v0.2.1"):
            with self.subTest(ref=ref):
                self.assertIn(self.version_of_ref(ref), t["never_deployed"])

    def test_p4_no_downgrade(self):
        """I63-P4: no matched upgrade's version precedes an earlier matched upgrade's version."""
        item("I63", "I63-P4")
        self.assertEqual(self.timeline()["downgrades"], [])

    def test_p5_every_reinitializer_runs_in_its_upgrade(self):
        """I63-P5: every matched upgrade is consistent (H8): the Initialized versions its own transaction logs are
        exactly the versions of the reinitializers its version introduces (every reinitializer of the first matched
        version), so no reinitializer was left callable after its upgrade's transaction."""
        item("I63", "I63-P5")
        for u in self.timeline()["upgrades"]:
            if u["version"] is None:
                continue
            with self.subTest(block=u["block"]):
                self.assertTrue(u["consistent"], (u["expected_initialized"], u["initialized"]))


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change."""

    def test_the_last_upgrade_is_i23s(self):
        """I63-R1: the last upgrade (block 26031669) sets I23's implementation 0x213ce22b..., whose runtime code hashes
        to I23's 53ec0662... (results/M2/historical/trans.json), and it matches the head's version under the "deployed"
        configuration alone (I23's Surprise 1, restated through H7)."""
        item("I63", "I63-R1")
        last = need(ONCHAIN)["upgrades"][-1]
        self.assertEqual((last["block"], last["implementation"]),
                         (26031669, "0x213ce22b487b71ac68a1b5b12d2b93d1af30ea1d"))
        self.assertEqual(last["code_sha256"], "53ec06626d3eedd585816d6258540daeffcf87b4ca9f8e575aebe49e1d79972e")
        head = next(v["id"] for v in need(BASIS)["versions"] if "head" in v["refs"])
        self.assertEqual(need(TIMELINE)["upgrades"][-1]["matches"], [{"config": "deployed", "version": head}])

    def test_outcome_commits_touch_no_law_record_or_catalog(self):
        """I63-R2 (part): no commit that writes an I63 outcome path changes a law, a record, a rule catalog, an earlier
        milestone's spec or output, another M3 output, replay/ or a frozen root. Needs the real checkout's history and
        at least one such commit: a missing .git, or no outcome commit yet, is a failure, never a skip."""
        item("I63", "I63-R2")

        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        outs = tuple(load_json(ROOT / "spec" / "M3" / "predictions.json")["iterations"]["I63"]["outcome_paths"])
        forbidden = ("laws/", "replay/", "holon/rules/", "spec/M1/", "spec/M2/", "gen/M0/", "gen/M1/", "gen/M2/",
                     "results/M0/", "results/M1/", "results/M2/", "facts/", "predictions/", "schemas/", "tests/",
                     "bend/probes/", "AGENTS.md", "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md",
                     "FROZEN.sha256")
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
