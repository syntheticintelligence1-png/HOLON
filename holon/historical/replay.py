"""`python -m holon historical replay`: the first per-edge replay of real on-chain inputs through the models.

    python -m holon historical replay [--milestone M2] [--index PATH] [--out PATH] [--morph PATH] [--work DIR]

Reads the index (results/M2/historical/index.json) and the snapshot it names, and writes
results/M2/historical/replay.json and results/M2/historical/disagreements.json (canonical JSON,
holon.ir.canonical_json, one line). Both are functions of the index, the snapshot, the frozen M0 header model,
the pinned morph checkout, the pinned solc and the pinned Go toolchain: byte-identical across runs.

What a commit is. Every transaction in the index that calls a commit function (commitBatch, commitState,
commitBatchWithProof) by its selector, under the pinned ABI or any signature of IRollup.sol in the pinned
checkout's history (holon.historical.abi), or that emitted a CommitBatch log while its selector names no
other known function. A transaction whose selector names another known function and that emitted a
CommitBatch log (importGenesisBatch) is listed under "genesis", not as a commit: the contract's linkage
reads its event as the genesis import.

For each commit (sorted by block, transaction index): status from the receipt ("success" iff status 0x1; a
missing receipt with a log of the transaction counts as success, since only successful transactions emit
logs, and is counted in summary.status_from_logs); function by selector; abi "decoded" iff the selector is a
pinned commit function's and the calldata decodes strictly under the pinned ABI; batch_index and batch_hash
from the transaction's CommitBatch log; the transaction's blob versioned hashes and, per blob, its source and
commitment_ok: the blob's KZG commitment hashes to the transaction's versioned hash
(0x01 || sha256(commitment)[1:]), null when unavailable. The commitment is the one computed from the blob's own
bytes by kzg4844.BlobToCommitment of the pinned checkout's go-ethereum (holon/historical/go/holon_kzg_test.go in
a scratch copy of common/batch); a commitment served with the blob (beacon sidecars) must equal it. Only for a
blob the fetch hashed but could not keep on disk is the served commitment used alone (verified at fetch time),
and if the Go harness cannot run every kept blob has commitment_ok false and kzg "not_run".

"parent" (decoded successful commits): batchDataInput.parentBatchHeader with
  - the per-header checks of holon.historical.checks (frozen M0 model);
  - batch_index and blob_versioned_hash: the header's fields at the facts' dec_go getter offsets;
  - linkage: keccak256(parent) against the batchHash of the latest CommitBatch event (genesis import included)
    with the header's batch index strictly before the transaction ("ok" | "mismatch" | "no_event");
  - go_decoder: the real Go decoders of the pinned checkout (common/batch BatchHeaderBytes.validate and the
    getters, through replay/M2/go/holon_codec_test.go as I16 runs it) compared with the model's dec_go and
    ok_go on the same bytes ("agree" | "disagree" | "not_run" when the harness could not run).

Supplementary, outside the preregistered fields (never read by the tests):
  - blobs[i].kzg: how commitment_ok was decided: "computed" (from the bytes), "served_differs" (a served
    commitment differs from the computed one: commitment_ok false), "error" (the bytes are not a canonical
    blob: commitment_ok false), "not_kept" (the served commitment, checked at fetch time), "not_run";
  - "legacy_parent": the same checks for a successful commit whose selector is a historical signature
    (decoded with that signature's ABI, "abi_origin" its IRollup.sol revision); "abi" stays "undecodable";
    its differing cells are given as inclusive runs, "diff_ranges" (as is "rebuild"'s), to keep the file small;
  - "rebuild": the encoder edge on real inputs. For a commit of batch k whose header H_k (the header that
    hashes to the commit's emitted batchHash) appears as a later commit's parent, the model's enc_sol is run
    on a Header built from the commit's own inputs: version, numL1Messages, lastBlockNumber, prevStateRoot,
    postStateRoot and withdrawalRoot from its calldata; batchIndex, totalL1MessagePopped and parentBatchHash
    from its parent header (dec_go and keccak256); sequencerSetVerifyHash zero; dataHash and
    blobVersionedHash copied from H_k (computed on chain from data the calldata does not carry, so their cells
    are not evidence). "ok" iff enc_sol(Header) == H_k, else "diff" with diff_cells.

Disagreements (disagreements.json): every distinct real header on which the model and the real code differ:
  - dec_go / ok_go: the model against the real Go decoders;
  - ok_sol: the model rejects a parent header that the chain accepted (the commit succeeded, so the deployed
    _loadBatchHeader did not revert; the deployed implementation at that block, which need not be the pinned
    commit's).
Each carries an id that is a function of (edge, input) (holon.refinement.disagreement_id over the header's hex),
its links ({} for a new one) and the class holon.refinement.classify computes from the links alone (never from a
label). No raw chain bytes enter the file: the input is named by its keccak256 and length (the bytes are in the
snapshot), a decoder's outputs by their sha256 and the getter positions that differ.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from .. import ir
from ..keccak import keccak256
from . import abi as A
from . import checks as CH
from . import net
from .fetch import default_index, sidecar
from .store import Snapshot

ROOT = Path(__file__).resolve().parents[2]
ZERO32 = "0x" + "00" * 32


def default_out(milestone: str = "M2", root: Path = ROOT) -> Path:
    return Path(root) / "results" / milestone / "historical" / "replay.json"


def _int(x) -> int:
    return int(x, 16) if isinstance(x, str) else int(x)


class Data:
    """The index's items, read back from the snapshot (every object re-hashed on read)."""

    def __init__(self, idx: dict):
        self.idx = idx
        self.snap = Snapshot(Path(idx["snapshot"]))
        self.logs, self.txs, self.receipts, self.blobs = [], {}, {}, {}
        for it in idx["items"]:
            k = it["kind"]
            if k == "log":
                self.logs.append(self.snap.read_json(it["sha256"]))
            elif k == "tx" and it["status"] == "ok":
                tx = self.snap.read_json(it["sha256"])
                tx["_data"] = bytes.fromhex(tx.pop("input")[2:])   # bytes: half the memory of the hex text
                self.txs[it["tx"]] = tx
            elif k == "receipt" and it["status"] == "ok":
                rc = self.snap.read_json(it["sha256"])
                self.receipts[it["tx"]] = {"status": rc["status"]}
            elif k == "blob":
                self.blobs.setdefault(it["tx"], {})[it["versioned_hash"]] = it
        self.logs.sort(key=lambda lg: (_int(lg["blockNumber"]), _int(lg["logIndex"])))


def blob_source(it: dict | None, side: dict) -> str:
    if not it or it["status"] != "ok":
        return "unavailable"
    h = it.get("source")
    if h == net.host(side["sources"]["beacon"]):
        return "beacon"
    if h == net.host(side["sources"]["blob_archive"]):
        return "blob_archive"
    return "unavailable"


def versioned_hash(commitment_hex: str) -> str:
    return "0x01" + hashlib.sha256(bytes.fromhex(commitment_hex[2:])).hexdigest()[2:]


# ---------------------------------------------------------------- the Go decoders
def run_go_decoders(headers: list[bytes], morph: Path, work: Path | None, model: CH.HeaderModel) -> tuple[dict, str]:
    """{header hex: (real dec_go, real ok_go)} from the pinned checkout's common/batch, and the error text ('' on
    success). Uses the I16 binding and harness unchanged (holon.refinement.go_jobs / run_go)."""
    from .. import refinement as R
    if not headers:
        return {}, ""
    hexes = ["0x" + h.hex() for h in headers]
    bind = R.binding(ROOT)
    jobs = R.go_jobs(model.facts, bind, ["dec_go", "ok_go"], {"dec_go": hexes, "ok_go": hexes})
    tmp = None
    if work is None:
        tmp = work = Path(tempfile.mkdtemp(prefix="holon-hist-go-"))
    try:
        out = R.run_go(ROOT, morph, work, bind, jobs)
    except (R.RefineError, OSError) as e:
        return {}, str(e)[-1500:]
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    dec, ok = out.get("dec_go") or [], out.get("ok_go") or []
    if len(dec) != len(hexes) or len(ok) != len(hexes):
        return {}, f"Go harness returned {len(dec)}/{len(ok)} outputs for {len(hexes)} headers"
    return {h: (d, o) for h, d, o in zip(hexes, dec, ok)}, ""


KZG_HARNESS = Path(__file__).resolve().parent / "go" / "holon_kzg_test.go"


def run_kzg(paths: list[str], morph: Path, work: Path | None) -> tuple[list[str], str]:
    """One line per blob file: its KZG commitment ("0x" + hex) or "error: ..", from kzg4844.BlobToCommitment of the
    pinned checkout's go-ethereum, run by holon/historical/go/holon_kzg_test.go in a scratch copy of common/batch
    (the workspace the I16 codec harness uses). Returns ([], error text) when the harness cannot run."""
    import os
    import subprocess
    if not paths:
        return [], ""
    tmp = None
    if work is None:
        tmp = work = Path(tempfile.mkdtemp(prefix="holon-hist-kzg-"))
    ws = Path(work) / "kzg"
    try:
        shutil.rmtree(ws, ignore_errors=True)
        ws.mkdir(parents=True)
        for d in ("bindings", "common"):
            shutil.copytree(morph / d, ws / d, symlinks=True)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(KZG_HARNESS, ws / "common" / "batch" / KZG_HARNESS.name)
        (ws / "in.txt").write_text("".join(f"{p}\n" for p in paths))
        p = subprocess.run(["go", "test", "./batch", "-run", "^TestHolonKzg$", "-count=1", "-v", "-timeout", "6h"],
                           cwd=ws / "common", capture_output=True, text=True, timeout=6 * 3600,
                           env={**os.environ, "HOLON_KZG_IN": str(ws / "in.txt"), "HOLON_KZG_OUT": str(ws / "out.txt")})
        if p.returncode != 0 or not (ws / "out.txt").exists():
            return [], f"kzg harness failed (exit {p.returncode}): {(p.stdout + p.stderr)[-1500:]}"
        out = (ws / "out.txt").read_text().splitlines()
        if len(out) != len(paths):
            return [], f"kzg harness wrote {len(out)} lines for {len(paths)} blobs"
        return out, ""
    except (OSError, subprocess.SubprocessError) as e:
        return [], f"kzg harness: {type(e).__name__}: {e}"[-1500:]
    finally:
        shutil.rmtree(ws, ignore_errors=True)
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- replay
def replay(index_path: Path, milestone: str = "M2", morph: Path | None = None, work: Path | None = None) -> tuple[dict, dict]:
    from ..replay import check_checkout, morph_path, replay_config
    side = sidecar(milestone)
    idx = json.loads(Path(index_path).read_text())
    d = Data(idx)
    events_by_topic = {t.lower(): sig.split("(")[0] for sig, t in side["events"].items()}
    commit_topic = side["events"]["CommitBatch(uint256,bytes32)"].lower()
    revert_topic = side["events"]["RevertBatch(uint256,bytes32)"].lower()
    upgrade_topic = side["events"]["Upgraded(address)"].lower()
    address = side["contracts"]["Rollup"]["address"].lower()

    # ------------------------------------------------ the pinned ABI, the model
    morph = Path(morph) if morph else morph_path(argparse.Namespace(morph=None), ROOT)
    model = CH.model(ROOT)
    morph_sha = check_checkout(morph, model.facts["target"]["commit"])
    cfg = replay_config(ROOT)
    solc = cfg.get("solc")
    if not solc or not Path(solc).exists() or A.solc_sha256(solc) != cfg.get("solc_sha256"):
        raise SystemExit(f"historical replay: the pinned solc ({solc}) is missing or differs from replay.solc_sha256")
    pabi = A.PinnedAbi(morph, morph_sha, solc)
    commit_sels = pabi.commit_selectors()

    # ------------------------------------------------ events
    events = {name: 0 for name in events_by_topic.values()}
    logs_by_tx: dict[str, list[dict]] = {}
    commit_events: dict[int, list[tuple[tuple, str]]] = {}
    last_upgrade = None
    for lg in d.logs:
        t0 = lg["topics"][0].lower()
        events[events_by_topic[t0]] += 1
        logs_by_tx.setdefault(lg["transactionHash"].lower(), []).append(lg)
        pos = (_int(lg["blockNumber"]), _int(lg["transactionIndex"]), _int(lg["logIndex"]))
        if t0 == commit_topic:
            commit_events.setdefault(int(lg["topics"][1], 16), []).append((pos, lg["topics"][2].lower()))
        if t0 == upgrade_topic:
            last_upgrade = pos[0] if last_upgrade is None else max(last_upgrade, pos[0])
    for k in commit_events:
        commit_events[k].sort()

    def latest_hash(k: int, before: tuple) -> str | None:
        evs = commit_events.get(k) or []
        i = bisect.bisect_left(evs, (before, ""))
        return evs[i - 1][1] if i > 0 else None

    # ------------------------------------------------ commits
    commits, genesis, parents, legacy = [], [], {}, {}
    kzg_todo: list[tuple[int, int, str, str | None]] = []
    status_from_logs = 0
    order = sorted(d.txs.values(), key=lambda t: (_int(t["blockNumber"]), _int(t["transactionIndex"])))
    for tx in order:
        h = tx["hash"].lower()
        tlogs = logs_by_tx.get(h, [])
        clogs = [lg for lg in tlogs if lg["topics"][0].lower() == commit_topic]
        data = tx["_data"]
        sel = "0x" + data[:4].hex() if len(data) >= 4 else None
        to = (tx.get("to") or "").lower()
        nm = pabi.names.get(sel) if to == address else None
        name = nm["name"] if nm else None
        if name not in A.COMMIT_FUNCTIONS:
            if not clogs:
                continue
            if name is not None:  # a known non-commit function that emitted CommitBatch: the genesis import
                genesis.append({"tx": h, "block": _int(tx["blockNumber"]), "function": name,
                                "batch_index": int(clogs[0]["topics"][1], 16), "batch_hash": clogs[0]["topics"][2].lower()})
                continue
        rc = d.receipts.get(h)
        if rc is not None:
            status = "success" if _int(rc["status"]) == 1 else "failed"
        else:
            status = "success" if tlogs else "failed"
            status_from_logs += 1 if tlogs else 0
        dec, legacy_dec, legacy_origin = None, None, None
        if sel in commit_sels and to == address:
            try:
                dec = A.decode(pabi.pinned[sel], data)
            except A.AbiError:
                dec = None
        elif sel in pabi.legacy and to == address:
            fn, origin = pabi.legacy[sel]
            try:
                legacy_dec, legacy_origin = A.decode(fn, data), origin
            except A.AbiError:
                legacy_dec = None
        bvh = [x.lower() for x in tx.get("blobVersionedHashes") or []]
        blobs = []
        for vh in bvh:
            it = d.blobs.get(h, {}).get(vh)
            src = blob_source(it, side)
            b = {"versioned_hash": vh, "source": src, "commitment_ok": None, "kzg": None}
            if src != "unavailable":
                if it.get("kept") is False:
                    served = it.get("commitment")
                    b["kzg"], b["commitment_ok"] = "not_kept", bool(served) and versioned_hash(served) == vh
                else:
                    gz = d.snap.path(it["sha256"], True)
                    kzg_todo.append((len(commits), len(blobs), str(gz if gz.exists() else d.snap.path(it["sha256"])),
                                     it["commitment"]))
            blobs.append(b)
        c = {"tx": h, "block": _int(tx["blockNumber"]), "tx_index": _int(tx["transactionIndex"]), "status": status,
             "function": name if name in A.COMMIT_FUNCTIONS else "other",
             "abi": "decoded" if dec is not None else "undecodable",
             "batch_index": int(clogs[0]["topics"][1], 16) if clogs else None,
             "batch_hash": clogs[0]["topics"][2].lower() if clogs else None,
             "tx_blob_versioned_hashes": bvh, "blobs": blobs, "parent": None}
        if len(clogs) > 1:
            c["commit_logs"] = len(clogs)
        commits.append(c)
        if status == "success":
            first = lambda v: next(iter(v.values()))  # noqa: E731 - the BatchDataInput struct is the first parameter
            if dec is not None:
                parents[len(commits) - 1] = (first(dec), "pinned")
            elif legacy_dec is not None and isinstance(first(legacy_dec), dict) and "parentBatchHeader" in first(legacy_dec):
                legacy[len(commits) - 1] = (first(legacy_dec), legacy_origin)

    # ------------------------------------------------ blob bytes against their commitments (kzg4844, pinned go-ethereum)
    kzg_out, kzg_err = run_kzg([p for _, _, p, _ in kzg_todo], morph, work)
    for n, (ci, bi, _, served) in enumerate(kzg_todo):
        b = commits[ci]["blobs"][bi]
        r = kzg_out[n] if kzg_out else None
        if r is None:
            b["kzg"], b["commitment_ok"] = "not_run", False
        elif not r.startswith("0x"):
            b["kzg"], b["commitment_ok"] = "error", False
        elif served is not None and served.lower() != r:
            b["kzg"], b["commitment_ok"] = "served_differs", False
        else:
            b["kzg"], b["commitment_ok"] = "computed", versioned_hash(r) == b["versioned_hash"]

    # ------------------------------------------------ header checks (model) and Go decoders on every distinct header
    allh = {}
    for i, (inp, _) in list(parents.items()) + list(legacy.items()):
        allh.setdefault(bytes(inp["parentBatchHeader"]), None)
    hlist = list(allh)
    checked = {}
    for k in range(0, len(hlist), 4000):
        for hb, row in zip(hlist[k:k + 4000], model.check(hlist[k:k + 4000])):
            checked[hb] = row
    go_real, go_err = run_go_decoders(hlist, morph, work, model)
    by_keccak = {row["keccak"]: hb for hb, row in checked.items()}

    def parent_entry(c: dict, hb: bytes) -> dict:
        row = checked[hb]
        bi = model.field(hb, "batchIndex")
        k = int.from_bytes(bi, "big") if bi is not None else None
        ev = latest_hash(k, (c["block"], c["tx_index"], -1)) if k is not None else None
        bv = model.field(hb, "blobVersionedHash")
        real = go_real.get("0x" + hb.hex())
        if real is None:
            go = "not_run"
        else:
            go = "agree" if (real[0] == row["dec_go"] and real[1] == row["ok_go"]) else "disagree"
        return {"length": row["length"], "version": row["version"], "batch_index": k, "keccak": row["keccak"],
                "linkage": "no_event" if ev is None else ("ok" if ev == row["keccak"] else "mismatch"),
                "ok_sol": row["ok_sol"], "ok_go": row["ok_go"], "roundtrip": row["roundtrip"],
                "diff_cells": row["diff_cells"], "ssvh_zero": row["ssvh_zero"],
                "blob_versioned_hash": "0x" + bv.hex() if bv is not None else None, "go_decoder": go}

    for i, (inp, _) in parents.items():
        commits[i]["parent"] = parent_entry(commits[i], bytes(inp["parentBatchHeader"]))
    for i, (inp, origin) in legacy.items():
        lp = parent_entry(commits[i], bytes(inp["parentBatchHeader"]))
        lp["diff_ranges"] = ranges(lp.pop("diff_cells"))
        commits[i]["legacy_parent"] = {**lp, "abi_origin": origin}

    # ------------------------------------------------ rebuild: enc_sol on the commit's own inputs
    rebuild_jobs, rebuild_of = [], {}
    for i, (inp, _) in list(parents.items()) + list(legacy.items()):
        c = commits[i]
        need = ("version", "numL1Messages", "lastBlockNumber", "prevStateRoot", "postStateRoot", "withdrawalRoot")
        if not all(n in inp for n in need):
            c["rebuild"] = {"status": "not_applicable"}
            continue
        hk = by_keccak.get(c["batch_hash"]) if c["batch_hash"] else None
        ph = bytes(inp["parentBatchHeader"])
        prow = checked[ph]
        if hk is None or prow["dec_go"] is None:
            c["rebuild"] = {"status": "no_header" if hk is None else "parent_outside_dec_go"}
            continue
        pf = dict(zip(model.present(ph[0]), prow["dec_go"]))
        kf = dict(zip(model.present(hk[0]), checked[hk]["dec_go"] or [])) if checked[hk]["dec_go"] else None
        if kf is None:
            c["rebuild"] = {"status": "header_outside_dec_go"}
            continue
        w = model.widths
        hx = lambda v, n: "0x" + int(v).to_bytes(n, "big").hex()  # noqa: E731
        try:
            obj = {
                "version": hx(inp["version"], w["version"]),
                "batchIndex": hx(int(pf["batchIndex"], 16) + 1, w["batchIndex"]),
                "l1MessagePopped": hx(inp["numL1Messages"], w["l1MessagePopped"]),
                "totalL1MessagePopped": hx(int(pf["totalL1MessagePopped"], 16) + inp["numL1Messages"], w["totalL1MessagePopped"]),
                "dataHash": kf["dataHash"], "blobVersionedHash": kf["blobVersionedHash"],
                "prevStateHash": inp["prevStateRoot"], "postStateHash": inp["postStateRoot"],
                "withdrawRootHash": inp["withdrawalRoot"], "sequencerSetVerifyHash": ZERO32,
                "parentBatchHash": prow["keccak"],
                "lastBlockNumber": hx(inp["lastBlockNumber"], w["lastBlockNumber"]),
            }
        except (OverflowError, KeyError, ValueError):
            c["rebuild"] = {"status": "not_applicable"}
            continue
        from ..model_eval import header_in
        rebuild_of[i] = (len(rebuild_jobs), hk)
        rebuild_jobs.append({"terms": [{"call": "enc_sol", "args": [{"var": "h"}]}], "env": {"h": header_in(model.facts, obj)}})
    encs = []
    for k in range(0, len(rebuild_jobs), 4000):
        encs += model.model.run_jobs(rebuild_jobs[k:k + 4000])
    for i, (j, hk) in rebuild_of.items():
        (enc,) = encs[j]
        if isinstance(enc, dict):
            commits[i]["rebuild"] = {"status": "model_error"}
            continue
        n = max(len(enc), len(hk))
        diff = [x for x in range(n) if x >= len(enc) or x >= len(hk) or enc[x] != hk[x]]
        commits[i]["rebuild"] = {"status": "ok"} if not diff else {"status": "diff", "diff_ranges": ranges(diff)}

    # ------------------------------------------------ reverts
    reverts = []
    for lg in d.logs:
        if lg["topics"][0].lower() != revert_topic:
            continue
        k = int(lg["topics"][1], 16)
        pos = (_int(lg["blockNumber"]), _int(lg["transactionIndex"]), _int(lg["logIndex"]))
        evs = commit_events.get(k) or []
        j = bisect.bisect_right(evs, (pos, "\xff"))
        reverts.append({"batch_index": k, "block": pos[0], "tx": lg["transactionHash"].lower(),
                        "batch_hash": lg["topics"][2].lower(), "recommitted_block": evs[j][0][0] if j < len(evs) else None})
    reverts.sort(key=lambda r: (r["block"], r["batch_index"]))

    # ------------------------------------------------ disagreements
    dis = disagreements(commits, checked, go_real, by_keccak)
    rep = {"window": idx["window"], "index_sha256": idx["index_sha256"], "events": events,
           "last_upgrade_block": last_upgrade, "commits": commits, "genesis": genesis, "reverts": reverts,
           "abi": pabi.describe(), "morph_commit": morph_sha, "model_engine": model.engine,
           "facts": model.facts_rel, "go_harness_error": go_err or None, "kzg_harness_error": kzg_err or None,
           "summary": summary(commits, reverts, genesis, last_upgrade, status_from_logs, dis, go_err)}
    return rep, dis


def disagreements(commits: list[dict], checked: dict, go_real: dict, by_keccak: dict) -> dict:
    from .. import refinement as R
    found: dict[str, dict] = {}

    def add(edge, hb, model_v, real_v, real_source, tx):
        # no raw chain bytes in the repo: the input is named by its keccak256 (it is in the snapshot), and a
        # decoder's outputs (slices of the header) by their sha256, with the getter positions whose values differ
        x = "0x" + hb.hex()
        did = R.disagreement_id(edge, x)
        e = found.get(did)
        if e is None:
            vals = {"model": model_v, "real": real_v}
            if edge == "dec_go":
                m, r = list(model_v or []), list(real_v or [])
                vals = {"model_sha256": R.sha256_json(model_v), "real_sha256": R.sha256_json(real_v),
                        "model_none": model_v is None, "real_none": real_v is None,
                        "differing_positions": [i for i in range(max(len(m), len(r)))
                                                if i >= len(m) or i >= len(r) or m[i] != r[i]]}
            e = found[did] = {"id": did, "edge": edge, "milestone": "M0",
                              "input": {"keccak": "0x" + keccak256(hb).hex(), "length": len(hb)}, **vals,
                              "real_source": real_source, "txs": [], "count": 0, "links": {}}
        e["count"] += 1
        if len(e["txs"]) < 5:
            e["txs"].append(tx)

    compared = {"dec_go": 0, "ok_go": 0, "ok_sol": 0}
    for c in commits:
        for key in ("parent", "legacy_parent"):
            p = c.get(key)
            if not p:
                continue
            hb = by_keccak[p["keccak"]]
            row = checked[hb]
            real = go_real.get("0x" + hb.hex())
            if real is not None:
                compared["dec_go"] += 1
                compared["ok_go"] += 1
                if real[0] != row["dec_go"]:
                    add("dec_go", hb, row["dec_go"], real[0], "Go common/batch at the pinned commit", c["tx"])
                if real[1] != row["ok_go"]:
                    add("ok_go", hb, row["ok_go"], real[1], "Go common/batch at the pinned commit", c["tx"])
            if c["status"] == "success":
                compared["ok_sol"] += 1
                if row["ok_sol"] is not True:
                    add("ok_sol", hb, row["ok_sol"], True,
                        "chain: the commit succeeded, so the deployed _loadBatchHeader accepted it", c["tx"])
    entries = sorted(found.values(), key=lambda e: e["id"])
    for e in entries:
        e["class"] = R.classify(e, ROOT)
    by_edge, by_class = {}, {}
    for e in entries:
        by_edge[e["edge"]] = by_edge.get(e["edge"], 0) + 1
        by_class[e["class"]] = by_class.get(e["class"], 0) + 1
    return {"doc": "I59 historical replay: disagreements between the frozen M0 header model and the real code on real "
                   "on-chain parent headers (holon.historical.replay). dec_go / ok_go against the real Go decoders "
                   "of the pinned checkout; ok_sol against the chain's acceptance of the header in a successful "
                   "commit. Ids are holon.refinement.disagreement_id(edge, input); class is "
                   "holon.refinement.classify(entry) computed from links only ({} for a new entry: unexplained).",
            "compared": compared, "by_edge": dict(sorted(by_edge.items())), "by_class": dict(sorted(by_class.items())),
            "disagreements": entries}


def ranges(cells: list[int]) -> list[list[int]]:
    """Sorted cell indices as inclusive [first, last] runs (the supplementary fields' compact diff_cells)."""
    out: list[list[int]] = []
    for c in cells:
        if out and c == out[-1][1] + 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def _cells(p: dict) -> list[int]:
    if "diff_cells" in p:
        return p["diff_cells"]
    return [i for a, b in p.get("diff_ranges", []) for i in range(a, b + 1)]


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        k = json.dumps(x) if not isinstance(x, str) else x
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def summary(commits, reverts, genesis, last_upgrade, status_from_logs, dis, go_err) -> dict:
    ok = [c for c in commits if c["status"] == "success"]
    dec = [c for c in ok if c["abi"] == "decoded" and c["parent"]]
    leg = [c for c in ok if c.get("legacy_parent")]
    blobs = [b for c in ok for b in c["blobs"]]
    got = [b for b in blobs if b["source"] != "unavailable"]
    ks = sorted({c["batch_index"] for c in ok if c["batch_index"] is not None})

    def headers(rows, key):
        ps = [c[key] for c in rows]
        nz = [p["batch_index"] for p in ps if not p["ssvh_zero"]]
        z = [p["batch_index"] for p in ps if p["ssvh_zero"]]
        return {"n": len(ps),
                "linkage": _count(p["linkage"] for p in ps),
                "length": _count(str(p["length"]) for p in ps),
                "version": _count(str(p["version"]) for p in ps),
                "ok_sol_false": sum(1 for p in ps if not p["ok_sol"]),
                "ok_go_false": sum(1 for p in ps if not p["ok_go"]),
                "roundtrip": _count(p["roundtrip"] for p in ps),
                "diff_cells_outside_ssvh": sum(1 for p in ps if any(i not in range(185, 217) for i in _cells(p))),
                "ssvh_nonzero": len(nz), "ssvh_nonzero_max_batch_index": max(nz) if nz else None,
                "ssvh_zero_min_batch_index": min(z) if z else None,
                "go_decoder": _count(p["go_decoder"] for p in ps)}

    after = [c for c in ok if c["block"] > (last_upgrade or 0) and c["function"] != "other"]
    return {
        "commits": len(commits), "success": len(ok), "failed": len(commits) - len(ok),
        "status_from_logs": status_from_logs,
        "function": _count(c["function"] for c in commits),
        "abi": _count(c["abi"] for c in ok),
        "decoded_with_parent": len(dec), "legacy_with_parent": len(leg),
        "parents": headers(dec, "parent"), "legacy_parents": headers(leg, "legacy_parent"),
        "rebuild": _count((c.get("rebuild") or {}).get("status", "none") for c in ok if c.get("parent") or c.get("legacy_parent")),
        "rebuild_pinned": _count((c.get("rebuild") or {}).get("status", "none") for c in dec),
        "blobs": {"total": len(blobs), "retrieved": len(got), "by_source": _count(b["source"] for b in blobs),
                  "commitment_not_ok": sum(1 for b in got if b["commitment_ok"] is not True),
                  "kzg": _count(str(b.get("kzg")) for b in got),
                  "retrievable_fraction": (len(got) / len(blobs)) if blobs else None},
        "batch_indices": {"min": ks[0] if ks else None, "max": ks[-1] if ks else None, "distinct": len(ks),
                          "gaps": (ks[-1] - ks[0] + 1 - len(ks)) if ks else None},
        "reverts": len(reverts), "reverts_not_recommitted": sum(1 for r in reverts if r["recommitted_block"] is None),
        "genesis_imports": len(genesis),
        "after_last_upgrade": {"commits": len(after), "undecodable": sum(1 for c in after if c["abi"] != "decoded")},
        "disagreements": {"total": len(dis["disagreements"]), "by_edge": dis["by_edge"], "by_class": dis["by_class"]},
        "go_harness": "ran" if not go_err else "failed",
    }


def write(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(obj) + b"\n")
    tmp.replace(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical replay")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--index")
    ap.add_argument("--out")
    ap.add_argument("--disagreements", help="default: disagreements.json next to --out")
    ap.add_argument("--morph", help="morph checkout at the facts' commit (default: config replay.morph)")
    ap.add_argument("--work", help="scratch directory for the Go harness (default: a temporary directory)")
    a = ap.parse_args(argv)
    index = Path(a.index) if a.index else default_index(a.milestone)
    if not index.is_file():
        print(f"historical replay: no index at {index}: run python -m holon historical fetch first", file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else default_out(a.milestone)
    rep, dis = replay(index, a.milestone, Path(a.morph) if a.morph else None, Path(a.work) if a.work else None)
    write(rep, out)
    dpath = Path(a.disagreements) if a.disagreements else out.with_name("disagreements.json")
    write(dis, dpath)
    s = rep["summary"]
    print(json.dumps({k: s[k] for k in ("commits", "success", "decoded_with_parent", "legacy_with_parent", "blobs",
                                        "batch_indices", "reverts", "disagreements", "go_harness")}, sort_keys=True))
    print(f"wrote {out} and {dpath}")
    return 0 if rep["go_harness_error"] is None and rep["kzg_harness_error"] is None else 1
