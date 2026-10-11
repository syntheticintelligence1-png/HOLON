"""CLI for the S4 link-history frontend.

    python -m holon.frontends.link fetch --cache <dir> [--rpc <url>] [--morph <dir>]
        Record on-chain inputs (logs, txs, code, slots), sourcify sources/ABIs
        and solc storage layouts into the cache dir.

    python -m holon.frontends.link extract --cache <dir> --morph <dir> [--out <repo>]
        Emit spec/M2/extracted/links.json, spec/M2/extracted/migrations.json,
        spec/M2/coverage/link.json and spec/M2/manifests/link.json.

    python -m holon.frontends.link extract --fixtures <dir> --out <dir>
        Same, from committed fixtures (no network; morph checkout not required
        for the chain-derived outputs).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from . import chain, links, migrations


def _j(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_j(obj))


def build_record(rpc):
    """Pull the full input set through an RpcRecorder and return the canonical
    record extract consumes."""
    rec = {"logs": {}, "txs": {}, "codes": {}, "slots": {}, "impl_meta": {}}
    impls = set()
    for px in chain.PROXIES:
        addr = px["address"].lower()
        for topic in (chain.UPGRADED_TOPIC, chain.ADMIN_CHANGED_TOPIC):
            logs = rpc.get_logs(addr, topic)
            rec["logs"][f"{addr}|{topic}"] = sorted(
                logs, key=lambda l: (int(l["blockNumber"], 16), int(l["logIndex"], 16)))
            for l in logs:
                h = l["transactionHash"]
                if h not in rec["txs"]:
                    rec["txs"][h] = rpc.get_tx(h)
                if topic == chain.UPGRADED_TOPIC:
                    impls.add("0x" + l["topics"][1][-40:])
        rec["slots"][f"{addr}|{chain.IMPL_SLOT}"] = "0x" + rpc.get_storage(addr, chain.IMPL_SLOT)[-40:]
        rec["slots"][f"{addr}|{chain.ADMIN_SLOT}"] = "0x" + rpc.get_storage(addr, chain.ADMIN_SLOT)[-40:]
    for impl in sorted(impls):
        rec["codes"][impl] = rpc.get_code(impl)
    # PA owner (which contract the admin wrapper is)
    try:
        rec["slots"][f"{chain.PROXIES[0]['address']}|proxyadmin_owner"] = \
            "0x" + rpc.eth_call(migrations.PROXY_ADMIN, "0x8da5cb5b")[-40:]
    except Exception:
        pass
    return rec


def _repo_source_hashes(repo, candidates):
    """sha256 of source files at the pinned commit and known tags.

    Returns {"<tag>:<repo_rel_path>": "0x..."} (tag "pin" = working tree)."""
    out = {}
    for tag, path in candidates:
        try:
            if tag == "pin":
                p = repo / path
                if p.exists():
                    out[f"{tag}:{path}"] = "0x" + hashlib.sha256(p.read_bytes()).hexdigest()
            else:
                r = subprocess.run(["git", "-C", str(repo), "show", f"{tag}:{path}"],
                                   capture_output=True, timeout=60)
                if r.returncode == 0:
                    out[f"{tag}:{path}"] = "0x" + hashlib.sha256(r.stdout).hexdigest()
        except (OSError, subprocess.TimeoutExpired):
            continue
    return out


def _repo_rel(impl_src):
    """sourcify path (contracts/l1/x.sol) -> repo path (contracts/contracts/l1/x.sol)."""
    if impl_src.startswith("contracts/") and not impl_src.startswith("contracts/contracts/"):
        return "contracts/" + impl_src
    return impl_src


def cmd_fetch(args):
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    rpc = chain.RpcRecorder(args.rpc)
    rec = build_record(rpc)
    (cache / "chain_record.json").write_text(_j(rpc.record))

    # sourcify + layouts per impl
    sdir = cache / "sourcify"
    ldir = cache / "layouts"
    ldir.mkdir(parents=True, exist_ok=True)
    impls = sorted(rec["codes"])
    tag_candidates = [
        ("pin", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("pin", "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol"),
        ("v0.6.3", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("v0.6.3", "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol"),
        ("v0.6.2", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("v0.6.2", "contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol"),
        ("v0.5.0", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("v0.4.0", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("v0.3.0", "contracts/contracts/l1/rollup/Rollup.sol"),
        ("v0.2.1", "contracts/contracts/l1/rollup/Rollup.sol"),
    ]
    repo_hashes = _repo_source_hashes(Path(args.morph), tag_candidates) if args.morph else {}

    for impl in impls:
        meta_path = sdir / impl / "_meta.json"
        if not (meta_path.exists() and (sdir / impl / "abi.json").exists()):
            res = chain.sourcify_fetch(impl, sdir)
            if not res.get("verified"):
                continue
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        target = meta.get("compilationTarget") or next(
            (rel for rel in meta.get("files", [])
             if rel.endswith("/" + (meta.get("name") or "\0") + ".sol")), None)
        # repo pin / tag match on the main source file
        impl_src = None
        for rel in meta.get("files", []):
            if rel.endswith("/" + (meta.get("name") or "") + ".sol"):
                impl_src = rel
                break
        if impl_src is None:
            for rel in meta.get("files", []):
                if rel.endswith(".sol") and "rollup" in rel.lower():
                    impl_src = rel
        if impl_src:
            src_hash = "0x" + hashlib.sha256((sdir / impl / impl_src).read_bytes()).hexdigest()
            meta_out = {"repo_pin_match": False, "repo_tag": None,
                        "source_file": impl_src}
            repo_path = _repo_rel(impl_src)
            if repo_hashes.get(f"pin:{repo_path}") == src_hash:
                meta_out["repo_pin_match"] = True
            for tag in ("v0.6.3", "v0.6.2", "v0.5.0", "v0.4.0", "v0.3.0", "v0.2.1"):
                if repo_hashes.get(f"{tag}:{repo_path}") == src_hash:
                    meta_out["repo_tag"] = tag
                    break
            rec["impl_meta"][impl] = meta_out
        # storage layout via solc
        if target and not (ldir / f"{impl}.json").exists():
            lay = chain.solc_layout(sdir / impl, target, meta.get("name"), args.solc)
            if "error" not in lay:
                from .layout import normalize_layout
                (ldir / f"{impl}.json").write_text(_j(normalize_layout(lay)))
                err = ldir / f"{impl}.error.txt"
                if err.exists():
                    err.unlink()
            else:
                (ldir / f"{impl}.error.txt").write_text(lay["error"])
    _write(cache / "record.json", rec)
    print(f"fetched {len(rec['txs'])} txs, {len(rec['codes'])} impls -> {cache}")


def cmd_extract(args):
    cache = Path(args.cache) if args.cache else Path(args.fixtures)
    record = json.loads((cache / "record.json").read_text())
    sdir = cache / "sourcify"
    ldir = cache / "layouts"

    # attach deployed ABIs to proxies for links
    proxies = []
    for px in chain.PROXIES:
        addr = px["address"].lower()
        cur_impl = record["slots"].get(f"{addr}|{chain.IMPL_SLOT}")
        p = dict(px)
        p["current_impl"] = cur_impl
        af = sdir / (cur_impl or "") / "abi.json"
        if af.exists():
            p["impl_abi"] = json.loads(af.read_text())
        proxies.append(p)

    out_repo = Path(args.out)
    links_doc = None
    if args.morph:
        links_doc = links.build_links(Path(args.morph), sdir, proxies)
    mig_doc = migrations.build_migrations(record, sdir, ldir, proxies)

    if links_doc is not None:
        links_doc["target"]["commit"] = args.commit
        _write(out_repo / "spec/M2/extracted/links.json", links_doc)
    _write(out_repo / "spec/M2/extracted/migrations.json", mig_doc)

    cov = {"frontend": "link", "target_commit": args.commit,
           "items": sorted(mig_doc.get("coverage", []), key=lambda i: i["element"])}
    # the ProxyAdmin-owner wrapper batches calls behind an opaque selector
    cov["items"].append({
        "element": f"chain:{migrations.ADMIN_OWNER} selector 0x134008d3",
        "kind": "unresolved_selector",
        "reason": "ProxyAdmin-owner aggregate/forwarder contract; embedded "
                  "upgrade calls are recovered by selector scan, but the "
                  "wrapper's own function signature is unidentified",
    })
    # links-side coverage: constants the registry could not recover
    if links_doc is not None:
        for c in links_doc["constants"]:
            for m in c.get("missing", []):
                cov["items"].append({"element": f"{m['file']} constant {c['id']}",
                                     "kind": "unextracted_constant",
                                     "reason": f"extractor found no match for {m.get('symbol')}"})
        for f in links_doc["wire_layout"]:
            if not f["linked"]:
                cov["items"].append({"element": f"batch_header field {f['name']}@{f['offset']}",
                                     "kind": "unlinked_offset",
                                     "reason": "offset not recovered on one or both encoders"})
        for b in links_doc["abi_bindings"]:
            for sig in (b.get("events") or {}).get("deployed_only", []):
                cov["items"].append({"element": f"{b['go_file']} event {sig}",
                                     "kind": "missing_event_binding",
                                     "reason": "event present in deployed ABI, absent from Go binding"})
            for sig in (b.get("functions") or {}).get("deployed_only", []):
                cov["items"].append({"element": f"{b['go_file']} function {sig}",
                                     "kind": "missing_function_binding",
                                     "reason": "function present in deployed ABI, absent from Go binding"})
    cov["items"] = sorted(cov["items"], key=lambda i: i["element"])
    _write(out_repo / "spec/M2/coverage/link.json", cov)

    manifest = {
        "schema": "holon.link.manifest/v1",
        "target": {"repo": "morph-l2/morph", "commit": args.commit},
        "inputs": {
            "record_sha256": "0x" + hashlib.sha256(
                json.dumps(record, sort_keys=True).encode()).hexdigest(),
            "sourcify": sorted(
                ({"impl": impl.name, "abi_sha256": "0x" + hashlib.sha256(
                    (impl / "abi.json").read_bytes()).hexdigest()}
                 for impl in sdir.iterdir() if (impl / "abi.json").exists()),
                key=lambda e: e["impl"])
            if sdir.exists() else [],
            "layouts": sorted(
                ({"impl": lf.stem, "sha256": "0x" + hashlib.sha256(lf.read_bytes()).hexdigest()}
                 for lf in ldir.glob("*.json")),
                key=lambda e: e["impl"]) if ldir.exists() else [],
        },
        "outputs": ["spec/M2/extracted/links.json", "spec/M2/extracted/migrations.json",
                    "spec/M2/coverage/link.json"],
    }
    _write(out_repo / "spec/M2/manifests/link.json", manifest)
    print(f"wrote links.json, migrations.json, coverage/link.json, manifests/link.json -> {out_repo}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="holon.frontends.link")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--cache", required=True)
    f.add_argument("--rpc", default="https://gateway.tenderly.co/public/mainnet")
    f.add_argument("--morph", default=os.environ.get("HOLON_MORPH", str(Path.home() / ".holon/morph")))
    f.add_argument("--solc", default=os.environ.get("HOLON_SOLC", str(Path.home() / ".holon/solc-0.8.24")))
    f.set_defaults(fn=cmd_fetch)
    e = sub.add_parser("extract")
    e.add_argument("--cache")
    e.add_argument("--fixtures")
    e.add_argument("--morph", default=os.environ.get("HOLON_MORPH", str(Path.home() / ".holon/morph")))
    e.add_argument("--out", default=".")
    e.add_argument("--commit", default="3e44e795586af3e11285b603ab642c67823add51")
    e.set_defaults(fn=cmd_extract)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
