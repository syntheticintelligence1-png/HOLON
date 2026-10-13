"""I23: historical inputs and the M2 exit evaluation (BUILD_PLAN I23; whitepaper §8.7 source 4, Def 4.7 rho(e), §12.1
"Behaviour", §13 "refinement disagreement rate", §15.2 M2 exit (a)). This docstring is the contract.

Replay the real on-chain inputs I59 acquired through the models' edges: the header carrier's six edges (the frozen M0
header model) over every real parent header, and the extracted rollup model (I20) over every transaction of the
deployed implementation's live period. Record the agreement volume and every classified disagreement in refinement
records, link them to the M0/M2 laws whose cones use those edges, and evaluate M2 exit (a): zero unexplained replay
disagreements over a historical window. The exit report is honest either way.

Dependencies. The build starts after I20 is merged. It runs, unchanged:
  - I20's extracted rollup model: spec/M2/facts/morph_rollup.extracted.json compiled by I20's machine.py (raw storage
    families, inherited storage included; the raw model is authoritative), stepped with the semantics and observables of
    I20's contract (tests_m2/test_extracted_refinement.py, clause 7);
  - the frozen M0 header model (facts/morph_header.json), on the native or .mjs engine as results/M2/native.json says;
  - I16's harnesses and binding (replay/M2/implementations.json, replay/M2/go/holon_codec_test.go,
    replay/M2/solidity/HolonCodec.t.sol) on the pinned toolchain and checkout;
  - I59's holon.historical (abi, checks, store) and its snapshot.
A defect found in any of them is a Surprise. Its fix is an extraction_defect (a fix commit plus a green rerun record of
the edge, I16), never an edit of an output.

Frozen inputs (the prereg commit; the instrument's sha256 is pinned below as INSTRUMENT_SHA256)
  spec/M2/lib/historical_exit.json  the instrument. It fixes:
      windows.codec  I59's whole window [19426587, 26179508]: every real parent header;
      windows.trans  [26031670, 26179508]: from the block after the proxy's last Upgraded event (26031669,
                     implementation 0x213ce22b487b71ac68a1b5b12d2b93d1af30ea1d) to I59's window end. A transaction
                     before it ran other code and is never stepped through the extracted model;
      implementation the proxy, the last upgrade, the pinned source and the two compiler configurations the pinned
                     checkout declares (hardhat.config.ts, foundry.toml);
      in_scope       3414 transactions in 3414 blocks: 1695 commitBatch (batches 60478..62172, all version 2,
                     1693 with one blob and 2 with two, 33 loading 40 L1 messages at queue indices 27654..27693) and
                     1719 finalizeBatch (batches 60299..62017, 179 of them committed before the window), one sender;
                     the queue's 37 DequeueTransaction logs (indices 27647..27690, 44 messages);
      codec_corpus   62172 real parent headers: v0_249 17277, v0_281 2954, v1_257 34101, v2_257 7840; 59218 decodable;
      premise_inhabitants  the M0 laws' premise inhabitants among them;
      supplement     what may be fetched (only what I59 lacks), from where, and the blob fallback rule;
      storage_rule   how the model's state is threaded from the window's start and compared with the chain (pre,
                     post, final), and the residual it leaves;
      call_logs      the external calls whose arguments a log of their callee records;
      expected_classes  I16's mechanical criteria, the expected count of each class per window (all 0) and the target of
                     0 unexplained;
      synthetic_smoke  the six fixtures of node/derivation/testdata/rollup_calldata_fixtures.json.
    Its "computation" field says how each value was computed from I59's committed outputs and snapshot. BUILD_PLAN names
    spec/M2/preregistration.json; a prereg commit may only add files under spec/M2/lib/ (holon/audit/prereg.py).
  I59's outputs results/M2/historical/{index,replay,disagreements}.json: read, never rewritten (sha256 in the
  instrument).
  The I59 snapshot (index.json "snapshot", outside the repo): read, never refetched.

CLI. Every output is canonical JSON (holon.ir.canonical_json: sorted keys, no timestamps) and byte-identical across
runs.
  python -m holon historical fetch-state [--milestone M2] [--snapshot DIR] [--out PATH] [--offline]
      The supplementary acquisition, only of the instrument's supplement.kinds, from its supplement.sources, into the
      snapshot (content-addressed as I59's), indexed in results/M2/historical/supplement.json:
        {"window": <windows.trans: from_block, to_block, to_block_hash>, "snapshot": "<absolute dir>",
         "items": [{"kind", "block", "key", "sha256", "source": "<host only>", "status": "ok" | "unavailable",
                    "topic": "<topic0>" (log_other only)}],
         "pages": {"log_other": [[lo, hi], ...]}, "counts": {"<kind>": n},
         "supplement_sha256": sha256 of the canonical document without it}
      kind is header, storage, call, call_after, code, log_other, tx_other or receipt_other (the instrument's
      supplement.kinds say what each fetches and at which blocks). key: header "<block>"; storage "<address>:<slot>";
      call and call_after "<to>:<sha256 of the calldata>:<from>"; code "<address>"; log_other "<tx>:<log index>";
      tx_other and receipt_other "<tx>". block is the block the value was read at (storage: b - 1, b,
      trans.from_block - 1 or trans.to_block; call: b - 1; call_after: b). A code item's snapshot object is the
      runtime code's raw bytes, so its sha256 is the code's. Every in-scope block has its header item, every call item
      its call_after item. Items are sorted by (block, kind, key). pages lists the eth_getLogs ranges of
      log_other, which cover the trans window exactly. Nothing I59 indexed is stored again: a log_other item's topic is
      outside the instrument's five (a page may also return logs of the five topics; each must be byte-identical to
      I59's indexed log and is not stored again), and no transaction, receipt or blob I59 indexed is requested.
      --offline rewrites the index from the snapshot's state without the network. No secret appears in any output.
  python -m holon historical codec [--milestone M2]
      The header carrier's edges on the codec corpus (I59's parent and legacy_parent headers, from the snapshot):
        dec_go, ok_go, ok_sol  taken from I59's replay.json (the real Go decoders; the pinned Solidity
                               _loadBatchHeader), never re-run;
        enc_sol                the model's enc_sol against the real build block (I16 binding, op build) on dec_go(h) of
                               every decodable header;
        enc_go_v0, enc_go_v1   the model against the real BatchHeaderV0.Bytes / BatchHeaderV1.Bytes (I16 binding) on
                               dec_go(h): enc_go_v0 for version-0 headers, enc_go_v1 for versions 1 and 2.
      results/M2/historical/codec.json:
        {"window": <windows.codec>, "replay": {"path": "results/M2/historical/replay.json", "sha256"},
         "corpus": {"parents", "by_class": {...}, "decodable", "inputs_sha256"},
         "edges": {"<edge>": {"compared", "agree", "disagreements", "source": "i59" | "i23", "implementation",
                              "record": "results/M2/refinement/historical/<edge>.json"}},
         "reencode": {"v0_249" | "v1_257" | "v2_257": {"n", "exact", "diff_cells": {"<comma-joined cells>": n}}},
         "disagreements": [{"id", "edge", "class", "links"}], "unexplained": n,
         "blob_fallback": {"needed": n, "run": n}}
      reencode compares the real Go encoder of the header's version (V0 for version 0, V1 for versions 1 and 2) on
      dec_go(h) with the chain's bytes h, cell by cell. It is a cross-edge comparison (an encoder against the bytes
      another implementation wrote), never a refinement disagreement.
  python -m holon historical trans [--milestone M2]
      Every in-scope transaction, in chain order, stepped through the extracted model:
        env      caller = tx.from, this = the proxy, msg.value, msg.data.length, tx.origin and blobhash from the
                 snapshot's transaction; block.* from the supplement's header;
        calls    every external call the step makes is answered by the supplement's call item for (block - 1, callee,
                 calldata, from = the proxy): its success and return data (eth_call at the parent block). Its call_after
                 item (eth_call at block) is a stability check only: never an answer;
        storage  the instrument's storage_rule. The model's state is threaded through the whole window from one
                 initial state: a slot the replay has not yet touched holds the chain's value at
                 trans.from_block - 1 (never the chain's at the step's parent block, which would heal a missed write).
                 No slot is ever assumed zero and no answer is guessed: a value the supplement lacks makes the step
                 "unsupported", which is a status disagreement (I20's rule), never a skip.
      Observables, each compared with the chain:
        status   the model's ok | revert | unsupported against the receipt's status;
        events   the model's events against the receipt's logs emitted by the proxy (topics and data, in order);
        storage  pre: on every slot the step reads or writes, the model's value before the step against the chain at
                 block - 1; post: on the same slots, the model's value after the step against the chain at block;
                 final (once, after the last step): on every slot the replay touched, the model's value against the
                 chain at trans.to_block. A differing final slot is a storage disagreement of the last step that wrote
                 it on the model (or of the first step that read it, if none did);
        calls    each call of a function in the instrument's call_logs against the logs of its callee (call_logs.rule).
      revert is not applicable (every in-scope transaction succeeded; failed transactions are in no index).
      results/M2/historical/trans.json:
        {"window": <windows.trans>, "facts": "spec/M2/facts/morph_rollup.extracted.json", "facts_sha256",
         "model_sha256": sha256 of gen/M2/extracted/model.bend,
         "implementation": {"address", "upgrade_block", "proxy_slot", "code_sha256",
                            "pinned_build": {"matched_config": "hardhat" | "foundry" | null, "equal_masked": bool,
                                             "immutables_masked": n}},
         "observables": ["calls", "events", "status", "storage"], "not_applicable": {"revert": "<why>"},
         "complete": {"other_rollup_logs": n, "extra_transactions": n},
         "steps": [{"tx", "block", "tx_index", "action", "batch_index",
                    "status": {"model": "ok" | "revert" | "unsupported", "chain": "ok" | "revert"},
                    "events": {"model": n, "chain": n, "agree": bool,
                               "logs": [{"topics": ["0x<64 lowercase hex>", ...], "data": "0x<lowercase hex>"}]},
                    "storage": {"compared": n, "differ": n},
                    "calls": [{"fn": "<Interface>.<function>", "to": "0x<40 lowercase hex>", "args": [int, ...]}],
                    "sites": ["<path>:<line>", ...]}],
         "by_action": {"<action>": {"steps", "ok", "revert", "unsupported", "events_agree", "storage_compared",
                                    "storage_differ"}},
         "storage": {"compared": n, "differ": n, "final": {"compared": n, "differ": n}},
         "calls_by_fn": {"<Interface>.<function>": n},
         "call_stability": {"answers": n, "differ_at_b": n},
         "call_logs": {"<fn>": {"logs": n, "calls": n, "matched": n}},
         "disagreements": [{"id", "edge", "tx", "observable", "class", "links"}], "unexplained": n}
      steps holds every in-scope transaction (the instrument's in_scope.rule: I59's index items in the window, plus any
      transaction the supplement's log_other items belong to, counted in complete.extra_transactions), sorted by
      (block, tx_index). events.logs are the logs the MODEL emitted (the proxy's events), in order, as the model
      computed them; the tests compare them with the receipts in the I59 snapshot, independently of "agree".
      storage.compared/differ count a step's pre and post comparisons; storage at the top level sums them and adds the
      final comparison. calls lists the step's external calls in order, positional arguments as integers.
      call_stability counts the answers and those whose call_after answer differs (a diagnostic of the b - 1 answer
      source, never a disagreement by itself). batch_index is the commit's new batch or the finalized batch. sites
      lists the distinct source lines ("<path>:<line>", a library's own path for inlined library code) of every check,
      panic record, write and width-site store of the action's program that the step evaluated (a record in an untaken
      branch is not evaluated). code_sha256 is the sha256 of the
      runtime code bytes, which is the supplement's code item for the implementation address. pinned_build compares
      eth_getCode of the implementation at to_block with the pinned solc's deployedBytecode of the instrument's source under each
      compiler configuration, every immutableReferences range masked on both sides.
  python -m holon historical laws [--milestone M2]
      results/M2/historical/laws.json: {"laws": {"<M>/<law id>": {"status", "edges": {"<edge>": {"compared", "agree",
        "disagreements"}}, "premise_inhabitants": n | null, "realized": n | null, "site": "<path>:<lines>" | null,
        "reached": n | null, "why": "<when a field is null>"}}}
      One entry per law of laws/M0 and per record results/M2/L_*.json.
        M0 laws: edges are the header edges the statement calls (enc_sol, enc_go_v0, enc_go_v1, dec_go, ok_sol, ok_go);
          premise_inhabitants counts the real parent headers h with ok_go(h) whose dec_go(h) satisfies the law's
          assume (Header laws), or every real parent header (Bytes laws); realized counts, for a REFUTED law, the
          inhabitants on which its claim is false on the model; null otherwise.
        M2 laws: edges are the trans edges of the stepped actions (commitBatch, finalizeBatch) that the record's cone
          names: a cone entry one of whose "_"-separated tokens is the action's name exactly (Dec_commitBatch names
          commitBatch; Dec_commitBatchWithProof does not); premise_inhabitants is null; the law's span is the record's
          "site" (its "<path>:<lines>" part), or for a width law (I20) its width_site.span; site is that span when it
          is source of code the trans replay runs (Rollup.sol and the libraries it inlines, e.g.
          BatchHeaderCodecV0.sol), else null with a "why" (a facts definition, or another contract's code); reached
          counts the steps whose sites hold a line of that span; realized counts the reached steps at which the
          site's obstruction occurs (a Panic or revert attributed to the span, or for a width site a value outside the
          field's width at the store).
        Each edge's evidence is its historical record's compared, agree and disagreements.
  python -m holon historical smoke [--milestone M2]
      results/M2/historical/synthetic_smoke.json: {"label": "synthetic_smoke", "counted": false,
        "source": {"path", "commit", "sha256"}, "fixtures": [{"name", "selector", "abi": "pinned" | "history",
        "decoded_equals_expected": bool, "parent": {"length", "ok_sol", "ok_go"}}]}
      Each fixture's calldata is decoded by holon.historical.abi (the pinned ABI or a signature from the checkout's
      history) and compared with its "expected" (withdrawRoot is batchDataInput.withdrawalRoot); its parent header goes
      through holon.historical.header_checks. Synthetic inputs never enter a window, a record, a metric or the exit.
  Refinement records (Def 4.7 rho(e)): results/M2/refinement/historical/<edge>.json for dec_go, ok_go, ok_sol, enc_sol,
      enc_go_v0, enc_go_v1 (written by codec) and for each action stepped (written by trans):
        {"record_version": "holon-refinement/0.1", "kind": "historical", "milestone": "M2", "edge", "diagram_edge",
         "facts", "facts_sha256", "corpus": {"source": "historical", "window": {...}, "inputs": n, "inputs_sha256"},
         "compared", "agree", "disagreements", "disagreement_ids": [...], "fixes": [...],
         "implementation": {...}}
      facts is facts/morph_header.json for a codec edge and spec/M2/facts/morph_rollup.extracted.json for a trans edge
      (facts_sha256 its bytes' sha256). diagram_edge is CODEC.<edge> (the domain edges: null) or TRANS.<action>.
      implementation is rho(e)'s reference to the implementation code: for a codec edge {"harness", "lang",
      "target"} as I16's binding (replay/M2/implementations.json) gives them; for a trans edge {"address",
      "code_sha256", "source", "commit"}
      (the implementation, its runtime code's sha256, the pinned source path and checkout commit). compared counts
      inputs: headers for a codec edge, steps for a trans edge (a step with any differing observable, or unsupported,
      is one disagreement); compared = agree + disagreements. A disagreement's id is
      holon.refinement.disagreement_id("historical.<edge>", <input>) (the input: a header's keccak, a transaction hash);
      each new one is appended to spec/M2/disagreements.json as unexplained with no links and with "milestone": "M2"
      (I16), and its class is what holon.refinement.classify computes from its links.
      holon.refinement.check_disagreements (GREF) reads these records too (today it reads results/M2/refinement/*.json only, not the historical/ directory):
      an id a historical record lists without an entry, or a record whose counts do not add up, is a GREF failure.
  python -m holon metrics --milestone M2  (I16) adds refinement.historical: {"compared", "disagreements", "unexplained",
      "windows": {"codec": [from, to], "trans": [from, to]}}: the sums over the historical records, and the entries of
      spec/M2/disagreements.json they list that classify unexplained. refinement.compared and refinement.disagreements
      include them; refinement_disagreement_rate is disagreements / compared.
  python -m holon historical exit [--milestone M2] [--check]
      results/M2/m2_exit.json and docs/M2_EXIT.md, functions of results/M2/metrics.json, the instrument, the historical
      refinement records and the diagrams under gen/M2/diagram/ only:
        {"milestone": "M2",
         "exit_a": {"criterion", "status": "met" | "not_met",
                    "windows": {"codec" | "trans": {"from_block", "to_block", "to_block_hash"}}, "compared",
                    "disagreements", "unexplained", "substitute": false, "metrics": "results/M2/metrics.json",
                    "coverage": {"replayed": ["<facts>#<edge id>", ...], "not_replayed": {"<facts>#<edge id>": "<why>"}}},
         "exit_b": {"criterion", "status": "met" | "not_met" | "pending", "threshold": 0.8,
                    "rate_non_equivalent": <the metric's rate_non_equivalent> | null,
                    "source": "results/M2/metrics.json mutation_adequacy" | null},
         "closed": bool}
      exit_a is met iff refinement.historical.compared > 0, refinement.historical.unexplained == 0 and
      refinement.unexplained == 0. coverage says honestly which edges the window replayed (§12.1: a certificate is
      relative to its refinement evidence): replayed lists "<record facts>#<record diagram_edge>" of every historical
      record with a diagram_edge, sorted; not_replayed maps every other edge of kind CODEC, CONS or TRANS of every
      diagram under gen/M2/diagram/ ("<diagram facts>#<edge id>") to why it was not replayed on historical inputs (for
      example: no in-scope transaction calls the action; a hand abstraction whose extracted counterpart was replayed;
      the consumer is the L2 node's derivation). exit_b is read from metrics' mutation_adequacy (I22-R6, or the key
      that replaces I22), "pending" while that metric is not_applicable; I23 never computes it. closed iff both are
      met. docs/M2_EXIT.md is rendered from these files, holds the lines "M2 exit (a): <STATUS>" and
      "M2 exit (b): <STATUS>" (MET, NOT MET, PENDING) and names every not_replayed edge with its why. --check rebuilds
      both in memory and exits 1 if either differs from the committed bytes.
  tools/fetch_historical.py  for the human, where RPC is allowed: runs historical fetch, then fetch-state (--help
      exits 0 and names both).
  tools/historical_bigquery.sql  the BigQuery alternative over bigquery-public-data.crypto_ethereum (logs and
      transactions of the proxy for the five topics over the codec window); not run without credentials (Q5).

Rules
  - AGENTS.md is binding. Never edit facts/, laws/, spec/M1/facts/, spec/M2/facts/, I59's outputs, I20's outputs or
    the pinned checkout.
  - The chain and the real code are the only real sides. tests/reference is never imported from holon/.
  - A disagreement is classified by holon.refinement links only, never by a label or by prose. An unsupported step is
    a disagreement. A cross-edge difference (a REFUTED law realized on real inputs) is reported in laws.json and is
    never a refinement disagreement; nothing else is.
  - The windows never move. Synthetic inputs are never counted.
  - No skips: a missing snapshot, network, toolchain or I20 output is a failure with a clear message. The tests read
    the I59 snapshot themselves (index.json "snapshot", or HOLON_HISTORICAL_DIR) to check the model's events, status
    and queue calls against the receipts, independently of the outputs' own "agree" flags.
  - No secret in any output, and none printed: a test that finds one names the file, never the value.
  - Predictions are never tuned; a miss is a Surprise reported with its evidence.

Scope (whitepaper §8.7 source 4, stated so the exit report cannot overclaim)
  - "Every past commit's calldata, and its blobs where archived": every commit's parent header (the codec window) and,
    for the deployed implementation's live period, every commit and finalize transaction (the trans window). The
    60477 commits before the last upgrade ran other code: their headers are replayed, their transitions are not.
  - "compared with the stored commitments": the CommitBatch/FinalizeBatch logs (P4, P5), the stored batch hashes and
    roots (P6), I59's parent linkage and KZG checks (regressions).
  - "and the node's derivations": the L2 consumer path is I21-P13's (auditor A2 runs the node's UnPackData and
    ParseBatch on I59's 62172 commits); I23 does not duplicate it, and coverage lists CONS.blobs_of as not_replayed.
"""
import functools
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon

INSTRUMENT = ROOT / "spec" / "M2" / "lib" / "historical_exit.json"
INSTRUMENT_SHA256 = "7c43d9782ffa24cfbf0357b6af31017688eba985ba6b265b508614d01d154f1b"
HIST = ROOT / "results" / "M2" / "historical"
RECS = ROOT / "results" / "M2" / "refinement" / "historical"
CODEC_EDGES = ("dec_go", "enc_go_v0", "enc_go_v1", "enc_sol", "ok_go", "ok_sol")
TRANS_ACTIONS = ("commitBatch", "finalizeBatch")
POP = "IL1MessageQueue.popCrossDomainMessage"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def need(p: Path) -> dict:
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing: run the I23 pipeline (historical fetch-state, codec, "
                             f"trans, laws, smoke; holon metrics; historical exit)")
    return load_json(p)


def inst() -> dict:
    return load_json(INSTRUMENT)


def metrics() -> dict:
    met = need(ROOT / "results" / "M2" / "metrics.json")
    if "historical" not in met.get("refinement", {}):
        raise AssertionError("results/M2/metrics.json has no refinement.historical: holon metrics does not read the "
                             "historical refinement records yet")
    return met


def lfs(p: Path) -> dict:
    if p.stat().st_size < 1024 and p.read_bytes().startswith(b"version https://git-lfs"):
        raise AssertionError(f"{p.relative_to(ROOT)} is a Git LFS pointer: run git lfs pull")
    return load_json(p)


def window(w: dict) -> dict:
    return {k: w[k] for k in ("from_block", "to_block", "to_block_hash")}


@functools.lru_cache(maxsize=None)
def index() -> dict:
    return lfs(HIST / "index.json")


def snap_obj(sha: str):
    """An object of the I59 snapshot (its name is the sha256 of its bytes), re-hashed on read."""
    d = Path(os.environ.get("HOLON_HISTORICAL_DIR") or index()["snapshot"])
    p = d / "objects" / sha[:2] / sha
    if not p.is_file():
        raise AssertionError(f"the I59 snapshot has no object {sha} under {d}: restore the snapshot (holon historical "
                             f"fetch --offline cannot recreate it) or set HOLON_HISTORICAL_DIR")
    b = p.read_bytes()
    if sha256(b) != sha:
        raise AssertionError(f"snapshot object {sha} does not hash to its name")
    return json.loads(b)


@functools.lru_cache(maxsize=None)
def window_objects(kind: str) -> dict:
    """{tx hash: object} of the I59 index's items of one kind (tx, receipt) inside the trans window."""
    t = inst()["windows"]["trans"]
    return {x["tx"]: snap_obj(x["sha256"]) for x in index()["items"]
            if x["kind"] == kind and t["from_block"] <= x["block"] <= t["to_block"]}


def proxy_logs(receipt: dict) -> list:
    proxy = inst()["implementation"]["proxy"].lower()
    return [{"topics": [t.lower() for t in lg["topics"]], "data": lg["data"].lower()}
            for lg in receipt["logs"] if lg["address"].lower() == proxy]


def words(data: str) -> list:
    h = data[2:]
    return [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]


def statement_calls(node) -> set:
    if isinstance(node, dict):
        out = {node["call"]} if isinstance(node.get("call"), str) else set()
        for v in node.values():
            out |= statement_calls(v)
        return out
    if isinstance(node, list):
        return set().union(*(statement_calls(v) for v in node)) if node else set()
    return set()


def secret_values() -> list:
    """Secret values that must never appear in an output: the environment's and ~/.holon/secrets/*.env's (values of
    8 characters or more). Never printed."""
    vals = [v for k, v in os.environ.items() if k in ("ETH_RPC_URL", "ETHERSCAN_API_KEY") and v]
    for p in sorted((Path.home() / ".holon" / "secrets").glob("*.env")):
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                v = line.split("=", 1)[1].strip().strip("'\"")
                if len(v) >= 8:
                    vals.append(v)
    return vals


class TestInstrument(unittest.TestCase):
    """Construction checks: the instrument is the preregistered one, its values follow from I59's committed
    outputs."""

    @classmethod
    def setUpClass(cls):
        cls.i = inst()
        cls.replay = lfs(HIST / "replay.json")

    def test_the_instrument_is_the_frozen_one(self):
        self.assertEqual(sha256(INSTRUMENT.read_bytes()), INSTRUMENT_SHA256)
        self.assertEqual(self.i["instrument_version"], "holon-historical-exit/0.1")

    def test_i59_outputs_are_unchanged(self):
        for rel, v in self.i["inputs"]["i59_outputs"].items():
            with self.subTest(file=rel):
                self.assertEqual(sha256((ROOT / rel).read_bytes()), v["sha256"])
        for k in ("historical", "historical_target"):
            x = self.i["inputs"][k]
            self.assertEqual(sha256((ROOT / x["path"]).read_bytes()), x["sha256"])

    def test_windows_follow_i59(self):
        side = load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")
        self.assertEqual(window(self.i["windows"]["codec"]), window(side["window"]))
        t = self.i["windows"]["trans"]
        self.assertEqual(t["from_block"], self.replay["last_upgrade_block"] + 1)
        self.assertEqual((t["to_block"], t["to_block_hash"]),
                         (side["window"]["to_block"], side["window"]["to_block_hash"]))
        self.assertEqual(self.i["implementation"]["last_upgrade"]["block"], self.replay["last_upgrade_block"])
        self.assertEqual(self.i["implementation"]["proxy"], side["contracts"]["Rollup"]["address"])

    def test_in_scope_counts_follow_the_index(self):
        idx = lfs(HIST / "index.json")
        side = load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")
        topics = {k.split("(")[0]: v for k, v in side["events"].items()}
        t = self.i["windows"]["trans"]
        inside = [x for x in idx["items"] if t["from_block"] <= x["block"] <= t["to_block"]]
        txs = [x for x in inside if x["kind"] == "tx"]
        s = self.i["in_scope"]
        self.assertEqual(len(txs), s["transactions"])
        self.assertEqual(len({x["block"] for x in txs}), s["blocks"])
        logs = [x["topic"] for x in inside if x["kind"] == "log"]
        self.assertEqual({n: logs.count(topics[n]) for n in s["rollup_logs"]}, s["rollup_logs"])
        self.assertEqual(len(logs), sum(s["rollup_logs"].values()))
        self.assertEqual({v["action"]: v["n"] for v in s["selectors"].values()},
                         {"commitBatch": s["rollup_logs"]["CommitBatch"],
                          "finalizeBatch": s["rollup_logs"]["FinalizeBatch"]})
        self.assertEqual(sum(v["n"] for v in s["selectors"].values()), s["transactions"])
        self.assertEqual(logs.count(topics["Upgraded"]), 0)
        commits = [c for c in self.replay["commits"] if t["from_block"] <= c["block"] <= t["to_block"]]
        self.assertEqual(len(commits), s["selectors"]["0x41f756da"]["n"])
        ks = sorted(c["batch_index"] for c in commits)
        self.assertEqual([ks[0], ks[-1]], s["commit_batches"])
        self.assertEqual(ks, list(range(ks[0], ks[-1] + 1)))
        self.assertEqual(s["transactions"], 3414)

    def test_codec_corpus_and_premise_inhabitants_follow_the_replay(self):
        by_class, inh = {}, {}
        for c in self.replay["commits"]:
            p = c.get("parent") or c.get("legacy_parent")
            if not p:
                continue
            k = f"v{p['version']}_{p['length']}"
            by_class[k] = by_class.get(k, 0) + 1
            if p["ok_go"]:
                inh[(p["version"], p["ssvh_zero"])] = inh.get((p["version"], p["ssvh_zero"]), 0) + 1
        cc = self.i["codec_corpus"]
        self.assertEqual(by_class, cc["by_class"])
        self.assertEqual(sum(by_class.values()), cc["parents"])
        self.assertEqual(cc["decodable"], cc["parents"] - by_class["v0_281"])
        self.assertEqual(cc["enc_go_v1_inputs"], by_class["v1_257"] + by_class["v2_257"])
        pi = self.i["premise_inhabitants"]["laws"]
        for v, laws in ((0, ("L_par_hdr_v0", "L_rt_go_v0")), (1, ("L_par_hdr_v1", "L_rt_go_v1")),
                        (2, ("L_par_hdr_v2", "L_rt_go_v2"))):
            for law in laws:
                self.assertEqual(pi[law], inh.get((v, True), 0), law)
        self.assertEqual(pi["L_par_hdr_ssvh"], inh.get((1, True), 0) + inh.get((1, False), 0))
        self.assertEqual(pi["L_dom_hdr"], cc["parents"])
        self.assertEqual(sorted(pi), sorted(p.stem for p in (ROOT / "laws" / "M0").glob("L_*.json")))
        self.assertEqual((pi["L_par_hdr_v0"], pi["L_par_hdr_v1"], pi["L_par_hdr_v2"], pi["L_par_hdr_ssvh"]),
                         (1, 0, 1694, 34101))

    def test_in_scope_inputs_follow_the_snapshot(self):
        """Construction: the instrument's in_scope input facts are recomputed from the I59 snapshot's own transaction and
        receipt objects (selectors, sender, versions, blobs, L1 messages, batch indices, the queue's logs)."""
        s = self.i["in_scope"]
        side = load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")
        topic = {k.split("(")[0]: v.lower() for k, v in side["events"].items()}
        txs, rcs = window_objects("tx"), window_objects("receipt")
        self.assertEqual(len(txs), s["transactions"])
        self.assertEqual(set(txs), set(rcs))
        sel = {}
        for o in txs.values():
            sel[o["input"][:10]] = sel.get(o["input"][:10], 0) + 1
        self.assertEqual(sel, {k: v["n"] for k, v in s["selectors"].items()})
        self.assertEqual({o["from"].lower() for o in txs.values()}, {s["sender"]})
        self.assertEqual({o["to"].lower() for o in txs.values()}, {self.i["implementation"]["proxy"]})
        blobs, versions, loaded = {}, {}, []
        for o in txs.values():
            if o["input"][:10] != "0x41f756da":
                continue
            n = str(len(o.get("blobVersionedHashes") or []))
            blobs[n] = blobs.get(n, 0) + 1
            body = bytes.fromhex(o["input"][10:])
            t = body[int.from_bytes(body[:32], "big"):]
            w = [int.from_bytes(t[32 * i:32 * i + 32], "big") for i in range(4)]
            versions[str(w[0])] = versions.get(str(w[0]), 0) + 1
            plen = int.from_bytes(t[w[1]:w[1] + 32], "big")
            parent = t[w[1] + 32:w[1] + 32 + plen]
            total = int.from_bytes(parent[17:25], "big")
            loaded += [list(range(total, total + w[3]))] if w[3] else []
        self.assertEqual(blobs, s["commit_blob_counts"])
        self.assertEqual(versions, s["commit_versions"])
        self.assertEqual(len(loaded), s["commits_with_l1_messages"])
        flat = [q for xs in loaded for q in xs]
        self.assertEqual(len(flat), s["l1_messages_loaded"])
        self.assertEqual(flat, list(range(s["l1_queue_indices_loaded"][0], s["l1_queue_indices_loaded"][1] + 1)))
        proxy = self.i["implementation"]["proxy"]
        commits, finals, deq, other = [], [], [], set()
        for r in rcs.values():
            self.assertEqual(int(r["status"], 16), 1)
            for lg in r["logs"]:
                a, t0 = lg["address"].lower(), lg["topics"][0].lower()
                if a == proxy and t0 == topic["CommitBatch"]:
                    commits.append(int(lg["topics"][1], 16))
                elif a == proxy and t0 == topic["FinalizeBatch"]:
                    finals.append(int(lg["topics"][1], 16))
                elif a == s["queue"]["address"] and t0 == s["queue"]["topic0"]:
                    deq.append(tuple(words(lg["data"])[:2]))
                else:
                    other.add(a)
        self.assertEqual(sorted(other), s["other_log_emitters"])
        self.assertEqual(sorted(commits), list(range(s["commit_batches"][0], s["commit_batches"][1] + 1)))
        self.assertEqual(sorted(finals), list(range(s["finalize_batches"][0], s["finalize_batches"][1] + 1)))
        self.assertEqual(sum(1 for k in finals if k < s["commit_batches"][0]),
                         s["finalizes_of_batches_committed_before_the_window"])
        deq.sort()
        self.assertEqual(len(deq), s["queue"]["logs"])
        self.assertEqual(sum(c for _, c in deq), s["queue"]["messages"])
        self.assertEqual([deq[0][0], deq[-1][0] + deq[-1][1] - 1], s["queue"]["dequeued"])
        self.assertTrue(all(deq[i][0] + deq[i][1] == deq[i + 1][0] for i in range(len(deq) - 1)), deq[:5])


class TestSupplement(unittest.TestCase):
    """Construction checks on the supplementary acquisition (only what I59 lacks)."""

    KINDS = {"header", "storage", "call", "call_after", "code", "log_other", "tx_other", "receipt_other"}

    @classmethod
    def setUpClass(cls):
        cls.i = inst()
        cls.s = need(HIST / "supplement.json")

    def test_supplement_covers_the_trans_window_without_refetching(self):
        s, t = self.s, self.i["windows"]["trans"]
        self.assertEqual(s["window"], window(t))
        self.assertLessEqual({x["kind"] for x in s["items"]}, self.KINDS)
        self.assertTrue(s["items"])
        self.assertEqual(s["counts"], {k: sum(1 for x in s["items"] if x["kind"] == k)
                                       for k in sorted({x["kind"] for x in s["items"]})})
        self.assertTrue(all(t["from_block"] - 1 <= x["block"] <= t["to_block"] for x in s["items"]))
        self.assertEqual(s["items"], sorted(s["items"], key=lambda x: (x["block"], x["kind"], x["key"])))
        blocks = {x["block"] for x in index()["items"] if x["kind"] == "tx" and t["from_block"] <= x["block"] <= t["to_block"]}
        blocks |= {x["block"] for x in s["items"] if x["kind"] == "tx_other"}
        self.assertEqual({x["block"] for x in s["items"] if x["kind"] == "header"}, blocks)
        self.assertEqual(sorted((x["block"] + 1, x["key"]) for x in s["items"] if x["kind"] == "call"),
                         sorted((x["block"], x["key"]) for x in s["items"] if x["kind"] == "call_after"))
        self.assertTrue(all(x["block"] + 1 in blocks for x in s["items"] if x["kind"] == "call"))
        storage = [x for x in s["items"] if x["kind"] == "storage"]
        self.assertTrue([x for x in storage if x["block"] == t["from_block"] - 1], "no initial storage values")
        self.assertTrue([x for x in storage if x["block"] == t["to_block"]], "no final storage values")
        impl = self.i["implementation"]["last_upgrade"]["implementation"]
        self.assertEqual([x["block"] for x in s["items"] if x["kind"] == "code" and x["key"] == impl], [t["to_block"]])
        self.assertEqual([x["key"] for x in s["items"] if x["status"] != "ok"], [])
        snap = Path(s["snapshot"]).resolve()
        self.assertFalse(str(snap).startswith(str(ROOT.resolve()) + os.sep), snap)
        idx_tx = {x["tx"] for x in lfs(HIST / "index.json")["items"] if t["from_block"] <= x["block"] <= t["to_block"]}
        self.assertEqual([x["key"] for x in s["items"]
                          if x["kind"] in ("tx_other", "receipt_other") and x["key"] in idx_tx], [])
        five = {v.lower() for v in load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")["events"].values()}
        self.assertEqual([x["key"] for x in s["items"] if x["kind"] == "log_other" and x["topic"].lower() in five], [])
        self.assertEqual([x["kind"] for x in s["items"] if x["kind"] != "log_other" and "topic" in x], [])
        pages = sorted(s["pages"]["log_other"])
        self.assertEqual(pages[0][0], t["from_block"])
        self.assertEqual(pages[-1][1], t["to_block"])
        self.assertTrue(all(pages[i][1] + 1 == pages[i + 1][0] for i in range(len(pages) - 1)), pages[:5])
        body = {k: v for k, v in s.items() if k != "supplement_sha256"}
        self.assertEqual(s["supplement_sha256"], sha256(holon_module("holon.ir").canonical_json(body)))

    def test_no_secret_in_any_output(self):
        secrets = secret_values()
        files = [HIST / f for f in ("supplement.json", "codec.json", "trans.json", "laws.json", "synthetic_smoke.json")]
        files += [ROOT / "results" / "M2" / "m2_exit.json", ROOT / "docs" / "M2_EXIT.md"] + sorted(RECS.glob("*.json"))
        for p in files:
            text = p.read_text(encoding="utf-8") if p.is_file() else ""
            with self.subTest(file=str(p.relative_to(ROOT))):
                self.assertTrue(text, f"{p.relative_to(ROOT)} is missing")
                self.assertFalse("apikey=" in text.lower(), f"{p.relative_to(ROOT)} holds an apikey= parameter")
                hits = sum(1 for s in secrets if s in text)
                # never assertIn/assertNotIn on a secret: their failure message would print it
                self.assertEqual(hits, 0, f"{p.relative_to(ROOT)} holds {hits} secret value(s) (not printed)")

    def test_offline_reindex_is_byte_identical(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i23-"))
        try:
            outs = []
            for n in (1, 2):
                p = run_holon(["historical", "fetch-state", "--offline", "--out", str(tmp / f"s{n}.json")],
                              timeout=1800)
                self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                outs.append((tmp / f"s{n}.json").read_bytes())
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(outs[0], (HIST / "supplement.json").read_bytes())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestImplementation(unittest.TestCase):
    def test_the_deployed_implementation_is_the_pinned_build(self):
        """I23-P1: the runtime code at the last Upgraded event's implementation, which the proxy's EIP-1967 slot holds
        at to_block, equals the pinned solc build of Rollup.sol at 3e44e795 under one of the checkout's two declared
        compiler configurations, immutables masked."""
        i = inst()
        im = need(HIST / "trans.json")["implementation"]
        self.assertEqual(im["address"], i["implementation"]["last_upgrade"]["implementation"])
        self.assertEqual(im["upgrade_block"], i["implementation"]["last_upgrade"]["block"])
        self.assertEqual(int(im["proxy_slot"], 16), int(im["address"], 16))
        self.assertIn(im["pinned_build"]["matched_config"], i["implementation"]["compiler_configs"])
        self.assertIs(im["pinned_build"]["equal_masked"], True)
        code = [x for x in need(HIST / "supplement.json")["items"]
                if x["kind"] == "code" and x["key"] == im["address"]]
        self.assertEqual([x["sha256"] for x in code], [im["code_sha256"]])


class TestTrans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = inst()
        cls.t = need(HIST / "trans.json")
        cls.steps = cls.t["steps"]
        cls.by = {a: [s for s in cls.steps if s["action"] == a] for a in TRANS_ACTIONS}

    def test_every_in_scope_transaction_is_replayed(self):
        """I23-P2: the trans window holds no other Rollup log, and all 3414 in-scope transactions (1695 commitBatch,
        1719 finalizeBatch) are stepped, none unsupported, with 3467 answered external calls: isActive and
        getFirstUnfinalizedMessageEnqueueTime once per commit, getCrossDomainMessage 40 times, popCrossDomainMessage 37
        times."""
        s = self.i["in_scope"]
        self.assertEqual(self.t["complete"], {"other_rollup_logs": 0, "extra_transactions": 0})
        self.assertEqual(len(self.steps), s["transactions"])
        self.assertEqual(len({x["tx"] for x in self.steps}), s["transactions"])
        self.assertEqual({a: len(v) for a, v in self.by.items()}, {"commitBatch": 1695, "finalizeBatch": 1719})
        self.assertEqual([x["tx"] for x in self.steps if x["status"]["model"] == "unsupported"], [])
        self.assertEqual(sum(v["unsupported"] for v in self.t["by_action"].values()), 0)
        self.assertEqual(self.t["calls_by_fn"], {"ISubmitter.isActive": 1695,
                                                 "IL1MessageQueue.getFirstUnfinalizedMessageEnqueueTime": 1695,
                                                 "IL1MessageQueue.getCrossDomainMessage": 40, POP: 37})
        sup = need(HIST / "supplement.json")
        self.assertEqual(self.t["complete"]["other_rollup_logs"], sum(1 for x in sup["items"] if x["kind"] == "log_other"))
        # each commit loads exactly its calldata's L1 messages, at the queue indices its parent header implies
        txs = window_objects("tx")
        for x in self.by["commitBatch"]:
            body = bytes.fromhex(txs[x["tx"]]["input"][10:])
            t = body[int.from_bytes(body[:32], "big"):]
            off, n = int.from_bytes(t[32:64], "big"), int.from_bytes(t[96:128], "big")
            parent = t[off + 32:off + 32 + int.from_bytes(t[off:off + 32], "big")]
            total = int.from_bytes(parent[17:25], "big")
            got = [c["args"] for c in x["calls"] if c["fn"] == "IL1MessageQueue.getCrossDomainMessage"]
            self.assertEqual(got, [[q] for q in range(total, total + n)], x["tx"])

    def test_status_agrees_on_every_transaction(self):
        """I23-P3: the model's status is ok on all 3414, as on chain, including the 179 finalizes of batches
        60299..60477 that the legacy implementation committed."""
        self.assertEqual(len(self.steps), 3414)
        self.assertEqual([x["tx"] for x in self.steps if x["status"] != {"model": "ok", "chain": "ok"}], [])
        rcs = window_objects("receipt")
        self.assertEqual([x["tx"] for x in self.steps if int(rcs[x["tx"]]["status"], 16) != 1], [])
        legacy = [x for x in self.by["finalizeBatch"] if x["batch_index"] < self.i["in_scope"]["commit_batches"][0]]
        self.assertEqual(len(legacy), self.i["in_scope"]["finalizes_of_batches_committed_before_the_window"])
        self.assertEqual(sorted(x["batch_index"] for x in legacy), list(range(60299, 60478)))

    def test_commit_events_agree(self):
        """I23-P4: for all 1695 commits the model emits exactly the receipt's proxy log CommitBatch(k, h); h is the
        model's own batch hash (dataHash over lastBlockNumber, numL1Messages and the 40 L1 message hashes, the
        version-2 blob hash over the transaction's blobs)."""
        c = self.by["commitBatch"]
        self.assertEqual(len(c), 1695)
        self.assertEqual(sorted(x["batch_index"] for x in c), list(range(60478, 62173)))
        self._events_are_the_receipts(c, "CommitBatch")

    def test_finalize_events_agree(self):
        """I23-P5: for all 1719 finalizes the model emits exactly the receipt's proxy log
        FinalizeBatch(k, batchHash, stateRoot, withdrawRoot)."""
        f = self.by["finalizeBatch"]
        self.assertEqual(len(f), 1719)
        self.assertEqual(sorted(x["batch_index"] for x in f), list(range(60299, 62018)))
        self._events_are_the_receipts(f, "FinalizeBatch")

    def _events_are_the_receipts(self, steps, event):
        """The model's own logs (events.logs) against the receipts of the I59 snapshot, read here, not the output's
        agree flag: exactly one proxy log, of the action's event, for the step's batch, equal in topics and data."""
        side = load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")
        t0 = next(v.lower() for k, v in side["events"].items() if k.split("(")[0] == event)
        rcs = window_objects("receipt")
        bad = []
        for x in steps:
            chain = proxy_logs(rcs[x["tx"]])
            model = [{"topics": [t.lower() for t in lg["topics"]], "data": lg["data"].lower()}
                     for lg in x["events"]["logs"]]
            if (model != chain or len(chain) != 1 or chain[0]["topics"][0] != t0
                    or int(chain[0]["topics"][1], 16) != x["batch_index"]
                    or {k: x["events"][k] for k in ("model", "chain", "agree")} != {"model": 1, "chain": 1, "agree": True}):
                bad.append(x["tx"])
        self.assertEqual(bad, [])

    def test_storage_agrees(self):
        """I23-P6: 0 storage differences with the model's state threaded from the window's start (instrument
        storage_rule): before and after each step on every slot it reads or writes, and at the window's end on every slot
        the replay touched, the model's value is the chain's."""
        st = self.t["storage"]
        fin = st["final"]
        self.assertEqual(st["compared"], sum(x["storage"]["compared"] for x in self.steps) + fin["compared"])
        self.assertEqual(st["differ"], sum(x["storage"]["differ"] for x in self.steps) + fin["differ"])
        for a in TRANS_ACTIONS:
            with self.subTest(action=a):
                self.assertGreater(self.t["by_action"][a]["storage_compared"], 0)
                # pre and post: at least one slot each, so at least two comparisons per step
                self.assertEqual([x["tx"] for x in self.by[a] if x["storage"]["compared"] < 2], [])
        self.assertGreater(fin["compared"], 0)
        self.assertEqual((st["differ"], fin["differ"]), (0, 0))
        self.assertEqual([x["tx"] for x in self.steps if x["storage"]["differ"]], [])

    def test_queue_pops_agree_with_the_dequeue_logs(self):
        """I23-P7: exactly 37 finalizes call popCrossDomainMessage, once each, and every call's (startIndex, count) is
        the DequeueTransaction log of the queue in the same transaction: indices 27647..27690, 44 messages."""
        pops = [(x["tx"], c) for x in self.by["finalizeBatch"] for c in x["calls"] if c["fn"] == POP]
        self.assertEqual(len(pops), 37)
        self.assertEqual(len({tx for tx, _ in pops}), 37)
        q = self.i["in_scope"]["queue"]
        self.assertTrue(all(c["to"] == q["address"] for _, c in pops))
        args = sorted(tuple(c["args"]) for _, c in pops)
        self.assertEqual((args[0][0], args[-1][0] + args[-1][1] - 1), tuple(q["dequeued"]))
        self.assertEqual(sum(n for _, n in args), q["messages"])
        self.assertEqual(self.t["call_logs"][POP], {"logs": 37, "calls": 37, "matched": 37})
        # every step's pop calls against the queue's DequeueTransaction logs in its receipt, read from the snapshot
        rcs = window_objects("receipt")
        for x in self.steps:
            logs = [words(lg["data"])[:2] for lg in rcs[x["tx"]]["logs"]
                    if lg["address"].lower() == q["address"] and lg["topics"][0].lower() == q["topic0"]]
            calls = [list(c["args"]) for c in x["calls"] if c["fn"] == POP]
            self.assertEqual(calls, logs, x["tx"])

    def test_trans_record_is_well_formed(self):
        """Construction: inputs, observables, order and counts."""
        t = self.t
        self.assertEqual(t["window"], window(self.i["windows"]["trans"]))
        self.assertEqual(t["facts"], "spec/M2/facts/morph_rollup.extracted.json")
        self.assertEqual(t["facts_sha256"], sha256((ROOT / t["facts"]).read_bytes()))
        self.assertEqual(t["model_sha256"], sha256((ROOT / "gen" / "M2" / "extracted" / "model.bend").read_bytes()))
        self.assertEqual(t["observables"], ["calls", "events", "status", "storage"])
        self.assertTrue(t["not_applicable"]["revert"].strip())
        self.assertEqual(self.steps, sorted(self.steps, key=lambda x: (x["block"], x["tx_index"])))
        tw = self.i["windows"]["trans"]
        self.assertTrue(all(tw["from_block"] <= x["block"] <= tw["to_block"] for x in self.steps))
        idx_tx = {x["tx"] for x in lfs(HIST / "index.json")["items"]
                  if x["kind"] == "tx" and tw["from_block"] <= x["block"] <= tw["to_block"]}
        steps_tx = {x["tx"] for x in self.steps}
        self.assertLessEqual(idx_tx, steps_tx)
        self.assertEqual(len(steps_tx - idx_tx), t["complete"]["extra_transactions"])
        self.assertTrue(all(c["to"].startswith("0x") and len(c["to"]) == 42 and c["to"] == c["to"].lower()
                            for x in self.steps for c in x["calls"]))
        for a, v in t["by_action"].items():
            with self.subTest(action=a):
                ss = [x for x in self.steps if x["action"] == a]
                self.assertEqual(v["steps"], len(ss))
                self.assertEqual(v["ok"] + v["revert"] + v["unsupported"], v["steps"])
                self.assertEqual(v["events_agree"], sum(1 for x in ss if x["events"]["agree"]))
                self.assertEqual(v["storage_compared"], sum(x["storage"]["compared"] for x in ss))
        self.assertEqual(sum(t["calls_by_fn"].values()), sum(len(x["calls"]) for x in self.steps))
        cs = t["call_stability"]
        self.assertEqual(cs["answers"], sum(len(x["calls"]) for x in self.steps))
        self.assertTrue(0 <= cs["differ_at_b"] <= cs["answers"])
        self.assertTrue(all(x["events"]["model"] == len(x["events"]["logs"]) for x in self.steps))
        self.assertEqual(t["unexplained"], sum(1 for d in t["disagreements"] if d["class"] == "unexplained"))


class TestCodec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = inst()
        cls.c = need(HIST / "codec.json")

    def test_encoders_agree_with_their_implementations_on_real_headers(self):
        """I23-P8: on dec_go of the 59218 decodable real headers the real encoders agree with the model: the build block
        with enc_sol on all 59218, BatchHeaderV0.Bytes with enc_go_v0 on 17277, BatchHeaderV1.Bytes with enc_go_v1 on
        41941. 0 disagreements."""
        want = {"enc_sol": 59218, "enc_go_v0": 17277, "enc_go_v1": 41941}
        for e, n in want.items():
            with self.subTest(edge=e):
                x = self.c["edges"][e]
                self.assertEqual((x["compared"], x["agree"], x["disagreements"], x["source"]), (n, n, 0, "i23"))

    def test_go_reencoding_reproduces_legacy_headers_and_realizes_l_par_hdr_v2(self):
        """I23-P9: the real Go encoders reproduce the chain's bytes of all 17277 249-byte version-0 and all 34101
        version-1 headers; on all 7840 version-2 headers they differ from the chain in exactly cell 0 (Go writes version
        1): L_par_hdr_v2's obstruction on real bytes."""
        self.assertEqual(self.c["reencode"], {
            "v0_249": {"n": 17277, "exact": 17277, "diff_cells": {}},
            "v1_257": {"n": 34101, "exact": 34101, "diff_cells": {}},
            "v2_257": {"n": 7840, "exact": 0, "diff_cells": {"0": 7840}}})

    def test_decoder_and_domain_edges_are_i59s(self):
        """Regression: dec_go, ok_go and ok_sol are I59's comparisons on all 62172 parents, 0 disagreements."""
        rep = lfs(HIST / "replay.json")
        self.assertEqual(self.c["replay"], {"path": "results/M2/historical/replay.json",
                                            "sha256": sha256((HIST / "replay.json").read_bytes())})
        self.assertEqual(self.c["window"], window(self.i["windows"]["codec"]))
        cc = self.i["codec_corpus"]
        self.assertEqual({k: self.c["corpus"][k] for k in ("parents", "by_class", "decodable")},
                         {k: cc[k] for k in ("parents", "by_class", "decodable")})
        self.assertEqual(rep["summary"]["disagreements"]["total"], 0)
        for e in ("dec_go", "ok_go", "ok_sol"):
            with self.subTest(edge=e):
                x = self.c["edges"][e]
                self.assertEqual((x["compared"], x["agree"], x["disagreements"], x["source"]), (62172, 62172, 0, "i59"))

    def test_blob_fallback_is_not_needed(self):
        """Regression: I59 retrieved all 62192 blobs, so the L2 reconstruction fallback runs on none."""
        self.assertEqual(self.i["supplement"]["blob_fallback"]["needed"], 0)
        self.assertEqual(self.c["blob_fallback"], {"needed": 0, "run": 0})


class TestLaws(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = inst()
        cls.L = need(HIST / "laws.json")["laws"]

    def _one(self, prefix):
        hits = [k for k in self.L if k.startswith(prefix)]
        self.assertEqual(len(hits), 1, (prefix, sorted(self.L)))
        return self.L[hits[0]]

    def test_refuted_m0_laws_are_realized_on_real_headers(self):
        """I23-P10: L_par_hdr_ssvh is realized by all 34101 version-1 headers (enc_sol and enc_go_v1 differ in the
        sequencerSetVerifyHash cells) and L_par_hdr_v2 by all 1694 headers inhabiting its premise; no PROVED or UNKNOWN
        M0 law has a realization count."""
        self.assertEqual(self.L["M0/L_par_hdr_ssvh"]["realized"], 34101)
        self.assertEqual(self.L["M0/L_par_hdr_v2"]["realized"], 1694)
        for k, v in self.L.items():
            if k.startswith("M0/") and v["status"] != "REFUTED":
                with self.subTest(law=k):
                    self.assertIsNone(v["realized"])

    def test_l_dom_hdr_realizations_are_i59s(self):
        """Regression: L_dom_hdr is realized by I59's 2954 281-byte version-0 headers (ok_sol true, ok_go false)."""
        self.assertEqual(self.L["M0/L_dom_hdr"]["realized"], 2954)

    def test_refuted_m2_site_laws_are_not_realized(self):
        """I23-P11: no real step realizes an M2 site or width obstruction. The :363 site (proveRemainingTime) is reached
        by none of the 1695 commits (inChallenge is false before each), the :636 site by all 1719 finalizes, and each
        width site of I20-P2/P3 (the totalL1MessagePopped and batchIndex stores) by all 1695 commits."""
        s363 = self._one("M2/L_sort_site_rollup_363_")
        s636 = self._one("M2/L_sort_site_rollup_636_")
        self.assertEqual((s363["reached"], s363["realized"]), (0, 0))
        self.assertEqual((s636["reached"], s636["realized"]), (1719, 0))
        widths = {}
        for p in sorted((ROOT / "results" / "M2").glob("L_sort_width_*.json")):
            r = load_json(p)
            f = (r.get("width_site") or {}).get("field")
            if f in ("totalL1MessagePopped", "batchIndex"):
                widths[f] = self.L["M2/" + r["law_id"]]
        self.assertEqual(sorted(widths), ["batchIndex", "totalL1MessagePopped"])
        for f, v in widths.items():
            with self.subTest(width=f):
                self.assertEqual((v["reached"], v["realized"]), (1695, 0))
        self.assertEqual([k for k, v in self.L.items() if k.startswith("M2/") and v["realized"]], [])

    def test_premise_inhabitants_and_edge_evidence(self):
        """Construction: one entry per law with its record's status; the M0 premise inhabitants are the instrument's;
        each law's edge evidence is its edges' historical refinement records; null fields follow the contract."""
        m0 = sorted(p.stem for p in (ROOT / "laws" / "M0").glob("L_*.json"))
        m2 = sorted(p.stem for p in (ROOT / "results" / "M2").glob("L_*.json"))
        self.assertEqual(sorted(self.L), sorted(["M0/" + x for x in m0] + ["M2/" + x for x in m2]))
        for law, n in self.i["premise_inhabitants"]["laws"].items():
            with self.subTest(law=law):
                self.assertEqual(self.L["M0/" + law]["premise_inhabitants"], n)
        recs = {p.stem: load_json(p) for p in sorted(RECS.glob("*.json"))}
        for k, v in self.L.items():
            with self.subTest(law=k):
                ms, lid = k.split("/", 1)
                rec = load_json(ROOT / "results" / ms / f"{lid}.json")
                self.assertEqual(v["status"], rec["status"])
                if ms == "M0":
                    want = statement_calls(load_json(ROOT / "laws" / "M0" / f"{lid}.json")["statement"]) & set(CODEC_EDGES)
                    self.assertTrue(want)
                else:
                    want = {a for a in TRANS_ACTIONS if any(a in str(c).split("_") for c in rec.get("cone") or [])}
                self.assertEqual(sorted(v["edges"]), sorted(want))
                for e, x in v["edges"].items():
                    self.assertEqual(x, {f: recs[e][f] for f in ("compared", "agree", "disagreements")})
                if ms == "M0":
                    self.assertIsInstance(v["premise_inhabitants"], int)
                    self.assertEqual((v["site"], v["reached"]), (None, None))
                    self.assertEqual(v["realized"] is None, v["status"] != "REFUTED")
                else:
                    self.assertIsNone(v["premise_inhabitants"])
                    if v["site"] is None:
                        self.assertEqual((v["reached"], v["realized"]), (None, None))
                        self.assertTrue(str(v.get("why", "")).strip())
                    else:
                        span = ((rec.get("width_site") or {}).get("span")
                                or ":".join(str(rec.get("site") or "").split(":")[1:3]))
                        self.assertEqual(v["site"], span)
                        self.assertTrue(span.split(":")[0].endswith(".sol"), span)
                        self.assertIsInstance(v["reached"], int)
                        self.assertIsInstance(v["realized"], int)
                        self.assertLessEqual(v["realized"], v["reached"])


class TestRefinementRecords(unittest.TestCase):
    def test_historical_records_are_well_formed_and_add_up(self):
        """Construction (Def 4.7 rho(e)): one record per historical edge; counts add up; every listed id has an entry
        in spec/M2/disagreements.json and GREF passes."""
        i = inst()
        dis = {e["id"]: e for e in load_json(ROOT / "spec" / "M2" / "disagreements.json")["disagreements"]}
        names = sorted(p.stem for p in RECS.glob("*.json"))
        self.assertEqual(names, sorted(CODEC_EDGES + TRANS_ACTIONS))
        for name in names:
            r = load_json(RECS / f"{name}.json")
            with self.subTest(edge=name):
                self.assertEqual((r["record_version"], r["kind"], r["milestone"], r["edge"]),
                                 ("holon-refinement/0.1", "historical", "M2", name))
                w = i["windows"]["trans" if name in TRANS_ACTIONS else "codec"]
                self.assertEqual(r["corpus"]["window"], window(w))
                self.assertEqual(r["corpus"]["source"], "historical")
                self.assertEqual(r["compared"], r["agree"] + r["disagreements"])
                self.assertEqual(len(r["disagreement_ids"]), r["disagreements"])
                self.assertTrue(all(d in dis for d in r["disagreement_ids"]))
                self.assertTrue(all(d.startswith(f"D-historical.{name}-") for d in r["disagreement_ids"]))
                self.assertEqual(r["diagram_edge"], f"TRANS.{name}" if name in TRANS_ACTIONS
                                 else (None if name in ("ok_go", "ok_sol") else f"CODEC.{name}"))
                facts = "spec/M2/facts/morph_rollup.extracted.json" if name in TRANS_ACTIONS else "facts/morph_header.json"
                self.assertEqual((r["facts"], r["facts_sha256"]), (facts, sha256((ROOT / facts).read_bytes())))
                im = r["implementation"]
                if name in TRANS_ACTIONS:
                    pin = i["implementation"]
                    self.assertEqual((im["address"], im["source"], im["commit"]),
                                     (pin["last_upgrade"]["implementation"], pin["pinned"]["source"],
                                      pin["pinned"]["commit"]))
                    self.assertEqual(im["code_sha256"], need(HIST / "trans.json")["implementation"]["code_sha256"])
                else:
                    b = load_json(ROOT / "replay" / "M2" / "implementations.json")
                    self.assertEqual((im["lang"], im["target"]), (b["edges"][name]["lang"], b["edges"][name]["target"]))
                    self.assertEqual(im["harness"], b["harnesses"][b["edges"][name]["lang"]]["path"])
        self.assertEqual(holon_module("holon.refinement").check_disagreements(ROOT), [])

    def test_gref_reads_the_historical_records(self):
        """Construction: GREF is not vacuous on the historical records. In a scratch root holding only the disagreements
        file and the historical records, a record that lists an id with no entry must be reported."""
        names = sorted(p.name for p in RECS.glob("*.json"))
        self.assertIn("commitBatch.json", names)
        tmp = Path(tempfile.mkdtemp(prefix="holon-i23-gref-"))
        try:
            dst = tmp / RECS.relative_to(ROOT)
            dst.mkdir(parents=True)
            for n in names:
                shutil.copyfile(RECS / n, dst / n)
            (tmp / "spec" / "M2").mkdir(parents=True)
            shutil.copyfile(ROOT / "spec" / "M2" / "disagreements.json", tmp / "spec" / "M2" / "disagreements.json")
            r = load_json(dst / "commitBatch.json")
            bogus = "D-historical.commitBatch-00000000deadbeef"
            r["disagreement_ids"] = list(r["disagreement_ids"]) + [bogus]
            r["disagreements"] += 1
            r["agree"] -= 1
            (dst / "commitBatch.json").write_text(json.dumps(r, sort_keys=True))
            problems = holon_module("holon.refinement").check_disagreements(tmp)
            self.assertTrue(any(bogus in p for p in problems), problems)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = inst()

    def test_no_historical_disagreement(self):
        """I23-P12: no historical disagreement of any class in either window: codec.json and trans.json list none,
        every historical record counts 0, and spec/M2/disagreements.json holds no historical entry."""
        c, t = need(HIST / "codec.json"), need(HIST / "trans.json")
        self.assertEqual((c["disagreements"], c["unexplained"]), ([], 0))
        self.assertEqual((t["disagreements"], t["unexplained"]), ([], 0))
        recs = [load_json(p) for p in sorted(RECS.glob("*.json"))]
        self.assertEqual(len(recs), len(CODEC_EDGES) + len(TRANS_ACTIONS))
        self.assertEqual([r["edge"] for r in recs if r["disagreements"]], [])
        dis = load_json(ROOT / "spec" / "M2" / "disagreements.json")["disagreements"]
        self.assertEqual([e["id"] for e in dis if str(e.get("id", "")).startswith("D-historical.")], [])

    def test_m2_exit_a_is_met(self):
        """I23-P13: M2 exit (a) is met: refinement.historical reports both windows with unexplained 0, the whole
        refinement has unexplained 0, and results/M2/m2_exit.json records exit (a) as met over [19426587, 26179508]
        (codec) and [26031670, 26179508] (transitions)."""
        m = metrics()["refinement"]
        h = m["historical"]
        w = self.i["windows"]
        self.assertEqual(h["windows"], {"codec": [w["codec"]["from_block"], w["codec"]["to_block"]],
                                        "trans": [w["trans"]["from_block"], w["trans"]["to_block"]]})
        self.assertGreater(h["compared"], 0)
        self.assertEqual((h["unexplained"], m["unexplained"]), (0, 0))
        # both windows contribute, and the unexplained count is recomputed here from the records' ids and their entries
        recs = [load_json(p) for p in sorted(RECS.glob("*.json"))]
        self.assertGreater(sum(r["compared"] for r in recs if r["edge"] in CODEC_EDGES), 0)
        self.assertGreater(sum(r["compared"] for r in recs if r["edge"] in TRANS_ACTIONS), 0)
        dis = {x["id"]: x for x in load_json(ROOT / "spec" / "M2" / "disagreements.json")["disagreements"]}
        classify = holon_module("holon.refinement").classify
        ids = [d for r in recs for d in r["disagreement_ids"]]
        self.assertEqual([d for d in ids if d not in dis or classify(dis[d], ROOT) == "unexplained"], [])
        self.assertEqual([d for d in ids if dis[d].get("milestone") != "M2"], [])
        e = need(ROOT / "results" / "M2" / "m2_exit.json")["exit_a"]
        self.assertEqual(e["status"], "met")
        self.assertIs(e["substitute"], False)
        self.assertEqual({k: window(v) for k, v in e["windows"].items()},
                         {"codec": window(w["codec"]), "trans": window(w["trans"])})
        self.assertEqual((e["compared"], e["unexplained"]), (h["compared"], 0))

    def test_metrics_report_the_historical_refinement(self):
        """Regression and construction (§13 'refinement disagreement rate'): refinement.historical is the sum over the
        historical records, included in the totals."""
        met = metrics()
        m, h = met["refinement"], met["refinement"]["historical"]
        recs = [load_json(p) for p in sorted(RECS.glob("*.json"))]
        self.assertTrue(recs)
        self.assertEqual(h["compared"], sum(r["compared"] for r in recs))
        self.assertEqual(h["disagreements"], sum(r["disagreements"] for r in recs))
        self.assertGreaterEqual(m["compared"], h["compared"])
        self.assertGreaterEqual(m["disagreements"], h["disagreements"])
        self.assertEqual(met["refinement_disagreement_rate"], m["disagreements"] / m["compared"])
        c, t = need(HIST / "codec.json"), need(HIST / "trans.json")
        self.assertEqual(h["compared"], sum(x["compared"] for x in c["edges"].values())
                         + sum(r["compared"] for r in recs if r["edge"] in TRANS_ACTIONS))
        self.assertEqual(sum(r["compared"] for r in recs if r["edge"] in TRANS_ACTIONS), len(t["steps"]))

    def test_exit_document_is_generated_and_reproduced(self):
        """Construction: m2_exit.json and docs/M2_EXIT.md are generated (metrics.json, the instrument, the records and the
        diagrams); exit (b) is read from the mutation_adequacy metric (pending while it is not applicable); --check
        reproduces both."""
        met = need(ROOT / "results" / "M2" / "metrics.json")
        x = need(ROOT / "results" / "M2" / "m2_exit.json")
        b = x["exit_b"]
        if "mutation_adequacy" in met.get("not_applicable", {}):
            self.assertEqual((b["status"], b["source"], b["rate_non_equivalent"]), ("pending", None, None))
        else:
            ma = met["mutation_adequacy"]
            self.assertEqual(b["status"], "met" if ma["meets_threshold"] else "not_met")
            self.assertEqual(b["rate_non_equivalent"], ma["rate_non_equivalent"])
        self.assertEqual(b["threshold"], 0.8)
        self.assertIs(x["closed"], x["exit_a"]["status"] == "met" and b["status"] == "met")
        self.assertIs(x["exit_a"]["substitute"], False)
        md = ROOT / "docs" / "M2_EXIT.md"
        doc = md.read_text(encoding="utf-8") if md.is_file() else ""
        label = {"met": "MET", "not_met": "NOT MET", "pending": "PENDING"}
        self.assertIn(f"M2 exit (a): {label[x['exit_a']['status']]}", doc)
        self.assertIn(f"M2 exit (b): {label[b['status']]}", doc)
        p = run_holon(["historical", "exit", "--milestone", "M2", "--check"], timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])

    def test_exit_reports_which_edges_were_replayed(self):
        """Construction (§12.1: a certificate is relative to its refinement evidence; §8.7 source 4): exit_a.coverage
        lists the edges the historical window replayed and maps every other CODEC, CONS or TRANS edge of the M2
        diagrams to why it was not, and docs/M2_EXIT.md names each of them."""
        cov = need(ROOT / "results" / "M2" / "m2_exit.json")["exit_a"]["coverage"]
        recs = [load_json(p) for p in sorted(RECS.glob("*.json"))]
        replayed = sorted({f"{r['facts']}#{r['diagram_edge']}" for r in recs if r["diagram_edge"]})
        self.assertEqual(cov["replayed"], replayed)
        self.assertEqual(len(replayed), 6)
        edges = set()
        for p in sorted((ROOT / "gen" / "M2" / "diagram").glob("*.json")):
            d = load_json(p)
            edges |= {f"{d['facts']}#{e['id']}" for e in d["edges"] if e.get("kind") in ("CODEC", "CONS", "TRANS")}
        self.assertTrue(edges)
        self.assertEqual(sorted(cov["not_replayed"]), sorted(edges - set(replayed)))
        self.assertEqual([k for k, why in cov["not_replayed"].items() if not str(why).strip()], [])
        md = ROOT / "docs" / "M2_EXIT.md"
        doc = md.read_text(encoding="utf-8") if md.is_file() else ""
        self.assertEqual([k for k in cov["not_replayed"] if k not in doc], [])


class TestSmoke(unittest.TestCase):
    def test_the_six_fixtures_are_synthetic_smoke_and_never_counted(self):
        """Construction (BUILD_PLAN I23: the 6 morph fixtures, labelled synthetic_smoke)."""
        i = inst()["synthetic_smoke"]
        s = need(HIST / "synthetic_smoke.json")
        self.assertEqual((s["label"], s["counted"]), ("synthetic_smoke", False))
        self.assertEqual(s["source"], {"path": i["path"], "commit": i["commit"], "sha256": i["sha256"]})
        self.assertEqual([f["name"] for f in s["fixtures"]], i["names"])
        for f in s["fixtures"]:
            with self.subTest(fixture=f["name"]):
                self.assertIs(f["decoded_equals_expected"], True)
                self.assertEqual(f["parent"], {"length": 3, "ok_sol": False, "ok_go": False})
        pinned = ("0x41f756da", "0x1544ba3a")
        self.assertEqual({f["abi"] for f in s["fixtures"] if f["selector"] in pinned}, {"pinned"})
        self.assertEqual({f["abi"] for f in s["fixtures"] if f["selector"] not in pinned}, {"history"})


class TestTools(unittest.TestCase):
    def test_fetch_tool_and_bigquery_alternative_exist(self):
        """Construction (BUILD_PLAN I23 deliverables): the fetch tool for the human and the BigQuery alternative."""
        tool = ROOT / "tools" / "fetch_historical.py"
        self.assertTrue(tool.is_file(), "tools/fetch_historical.py is missing")
        p = subprocess.run([sys.executable, str(tool), "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        self.assertIn("fetch-state", p.stdout)
        self.assertIn("fetch", p.stdout.replace("fetch-state", ""))
        sql = ROOT / "tools" / "historical_bigquery.sql"
        self.assertTrue(sql.is_file(), "tools/historical_bigquery.sql is missing")
        text = sql.read_text().lower()
        side = load_json(ROOT / "spec" / "M2" / "lib" / "historical.json")
        self.assertIn("bigquery-public-data.crypto_ethereum", text)
        self.assertIn(side["contracts"]["Rollup"]["address"], text)
        for t in side["events"].values():
            self.assertIn(t.lower(), text)
        for b in (side["window"]["from_block"], side["window"]["to_block"]):
            self.assertIn(str(b), text)


class TestDeterminism(unittest.TestCase):
    def test_outputs_are_byte_identical_across_runs(self):
        """Construction: in a throwaway copy, two runs of codec, trans, laws, smoke, metrics and exit write the same
        bytes, equal to the committed files."""
        paths = ["results/M2/historical/codec.json", "results/M2/historical/trans.json",
                 "results/M2/historical/laws.json", "results/M2/historical/synthetic_smoke.json",
                 "results/M2/metrics.json", "results/M2/m2_exit.json", "docs/M2_EXIT.md",
                 "spec/M2/disagreements.json"]
        paths += [f"results/M2/refinement/historical/{e}.json" for e in sorted(CODEC_EDGES + TRANS_ACTIONS)]
        repo = copy_repo()
        try:
            outs = []
            for _ in range(2):
                for args in (["historical", "codec", "--milestone", "M2"], ["historical", "trans", "--milestone", "M2"],
                             ["historical", "laws", "--milestone", "M2"], ["historical", "smoke", "--milestone", "M2"],
                             ["metrics", "--milestone", "M2"], ["historical", "exit", "--milestone", "M2"]):
                    p = run_holon(args, cwd=repo, timeout=3600)
                    self.assertEqual(p.returncode, 0, (args, p.stdout[-1000:], p.stderr[-1500:]))
                outs.append({x: (repo / x).read_bytes() for x in paths})
            self.assertEqual(outs[0], outs[1])
            self.assertEqual(outs[0], {x: (ROOT / x).read_bytes() for x in paths})
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
