"""Rules A1-A6: the registry's history from its pinned tags, the on-chain fetch and the timeline.

  history   A1-A2: the registry contract (acquisition.registry) built at every pinned tag that holds it, under every
            compiler configuration, grouped into versions by the version configuration, with layouts,
            reinitializers, MIG edges and every build's immutable ranges by name (holon.frontends.solidity.history's
            H2-H6, a head ref left out: the unit is absent at the head)
  fetch     A3: the one network step (acquisition.rpc.url), over [window.from_block, the fetch block]: each proxy's
            Upgraded, AdminChanged and Initialized logs, the receipts of its Upgraded logs (I59's canonical form), the
            code of every implementation, its EIP-1967 implementation slot; a proxy whose address the sidecar does not
            give is the low 20 bytes of an immutable word of another proxy's last implementation in the window
            (acquisition.proxies.<p>.immutable); the word at a member's storage family slot (the acquisition entry
            with a "slot_of") and the code of the address it names. --check verifies the snapshot offline.
  timeline  A4-A6: every upgrade rebuilt from its raw log, confirmed by its receipt, matched (H7's identity) against
            the registry's versions and the members' head builds, with the matched build's immutable words.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from . import BundleError, Ctx, Refused, render, sha256_bytes, write_or_check

ONCHAIN_VERSION = "holon-bundle-onchain/0.1"
TIMELINE_VERSION = "holon-bundle-timeline/0.1"


# ------------------------------------------------------------------------------------------------------ builds
def _toolchain(ctx: Ctx):
    from ..frontends.solidity import history as H
    hctx = type("C", (), {"cfg": ctx.cfg})()
    try:
        return H._toolchain(hctx)
    except Exception as e:  # noqa: BLE001  (the history module's Refused)
        raise Refused(str(e)) from e


def compile_build(solc: str, deps: Path, tree: Path, unit: str, name: str, conf: dict) -> dict:
    """One configuration's build: runtime code, all immutable and link ranges, the immutable ranges by the immutable's
    name, the storage layout, the unit's AST and text, and every state variable's declaring contract."""
    try:
        text = (tree / unit).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise BundleError(f"{unit}: {e}") from e
    sel = {unit: {name: ["evm.deployedBytecode.object", "evm.deployedBytecode.immutableReferences",
                         "evm.deployedBytecode.linkReferences", "storageLayout"]}, "*": {"": ["ast"]}}
    settings = {"evmVersion": conf["evm_version"], "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]}, "outputSelection": sel}
    req = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}}, "settings": settings})
    p = subprocess.run([solc, "--standard-json", "--base-path", ".", "--include-path", str(deps)], input=req,
                       capture_output=True, text=True, cwd=str(tree), timeout=7200)
    try:
        out = json.loads(p.stdout)
    except ValueError as e:
        raise BundleError(f"solc gave no JSON (exit {p.returncode}): {p.stderr.strip()[:300]}") from e
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise BundleError("; ".join((e.get("formattedMessage") or e.get("message", ""))[:300] for e in errs[:3]))
    c = out["contracts"][unit][name]
    dep = c["evm"]["deployedBytecode"]
    imm_names, owner = {}, {}
    for src in out.get("sources", {}).values():
        stack = [src["ast"]]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                if n.get("nodeType") == "VariableDeclaration" and n.get("mutability") == "immutable":
                    imm_names[str(n["id"])] = n["name"]
                if n.get("nodeType") == "ContractDefinition":
                    for v in n.get("nodes", []):
                        if v.get("nodeType") == "VariableDeclaration" and v.get("stateVariable"):
                            owner[v["id"]] = n["name"]
                stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
            elif isinstance(n, list):
                stack.extend(n)
    by_name = {}
    for aid, rs in (dep.get("immutableReferences") or {}).items():
        by_name.setdefault(imm_names.get(str(aid), f"ast:{aid}"), []).extend(
            [[int(r["start"]), int(r["length"])] for r in rs])
    lnk = [[int(r["start"]), int(r["length"])] for f in (dep.get("linkReferences") or {}).values()
           for rs in f.values() for r in rs]
    ranges = sorted([x for v in by_name.values() for x in v] + lnk)
    return {"code": bytes.fromhex(dep["object"]), "ranges": ranges,
            "immutables": {k: sorted(v) for k, v in sorted(by_name.items())}, "layout": c["storageLayout"],
            "ast": out["sources"][unit]["ast"], "text": text, "owner": owner}


def ident(b: dict) -> dict:
    from ..frontends.solidity.history import identity
    return {"sha256": sha256_bytes(identity(b["code"], b["ranges"])), "length": len(b["code"]), "ranges": b["ranges"],
            "immutables": b["immutables"]}


def _git(repo: str, *args: str, binary: bool = False):
    import os
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    p = subprocess.run(["git", "-C", repo, "-c", "protocol.allow=never", *args], capture_output=True, timeout=1200,
                       env=env, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise Refused(f"git {' '.join(args[:3])}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode()


def _materialize(repo: str, commit: str, dest: Path, paths: list) -> None:
    import io
    import tarfile
    blob = _git(repo, "archive", "--format=tar", commit, "--", *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(dest, filter="data")


def registry_refs(ctx: Ctx) -> list:
    """A1: the pinned tags, each at its pin and holding the unit (else Refused), by committer time then name."""
    reg = ctx.side["acquisition"]["registry"]
    repo = ctx.source_repo()
    unit = reg["contract"]["source"]
    out = []
    for tag, pin in sorted(reg["tags"].items()):
        got = _git(repo, "rev-parse", "--verify", "-q", f"{tag}^{{commit}}").strip()
        if got != pin:
            raise Refused(f"tag {tag} is not at its pinned commit {pin} (found {got})")
        if unit not in _git(repo, "ls-tree", "--name-only", pin, "--", unit).split():
            raise Refused(f"tag {tag}: its tree has no {unit}")
        out.append({"ref": tag, "commit": pin, "time": int(_git(repo, "log", "-1", "--format=%ct", pin).strip())})
    out.sort(key=lambda r: (r["time"], r["ref"]))
    return out


def history(ctx: Ctx, log=print) -> dict:
    """A2: the registry's history document (I63's format; refs, versions and edges)."""
    from ..frontends.solidity import history as H
    solc, deps = _toolchain(ctx)
    acq = ctx.side["acquisition"]
    reg = acq["registry"]
    unit, name = reg["contract"]["source"], reg["contract"]["name"]
    confs, vconf = acq["compiler_configs"], acq["version_config"]
    repo = ctx.source_repo()
    rows = []
    with tempfile.TemporaryDirectory(prefix="holon-bundle-history-") as td:
        for r in registry_refs(ctx):
            tree = Path(td) / r["commit"]
            if not tree.is_dir():
                tree.mkdir()
                _materialize(repo, r["commit"], tree, reg["contract"]["build_paths"])
            row = {"ref": r["ref"], "commit": r["commit"], "time": r["time"], "builds": {}, "error": None}
            try:
                main = None
                for cname in sorted(confs):
                    b = compile_build(solc, deps, tree, unit, name, confs[cname])
                    row["builds"][cname] = ident(b)
                    if cname == vconf:
                        main = b
                row["layout"] = H.layout(main["layout"], main["owner"])
                row["reinitializers"] = H.initializers(main["ast"], name, main["text"])
                row["source_sha256"] = sha256_bytes(main["text"].encode("utf-8"))
            except (BundleError, Exception) as e:  # noqa: BLE001  (a build's error is the ref's, as H2's)
                if isinstance(e, Refused):
                    raise
                row["error"] = str(e)[:500]
            rows.append(row)
            log(f"{r['ref']}: {row['error'] or row['builds'][vconf]['sha256'][:12]}")
    versions = []
    for row in rows:
        if row["error"] is not None:
            continue
        key = row["builds"][vconf]["sha256"]
        if versions and versions[-1]["code"][vconf]["sha256"] == key:
            versions[-1]["refs"].append(row["ref"])
            continue
        versions.append({"id": f"V{len(versions) + 1}", "refs": [row["ref"]], "commit": row["commit"],
                         "time": row["time"], "code": row["builds"], "source_sha256": row["source_sha256"],
                         "layout": row["layout"],
                         "layout_sha256": sha256_bytes(json.dumps(row["layout"], sort_keys=True).encode()),
                         "reinitializers": row["reinitializers"]})
    edges = []
    for old, new in zip(versions, versions[1:]):
        top = max([x["version"] for x in old["reinitializers"]] or [0])
        d = H.diff_layouts(old["layout"], new["layout"])
        edges.append({"from": old["id"], "to": new["id"],
                      "introduced": [x for x in new["reinitializers"] if x["version"] > top], "layout": d,
                      "compatible": d["compatible"], "in_flight": H.reads_of_old(old["layout"], new["layout"], d)})
    return {"history_version": H.HISTORY_VERSION, "sidecar": ctx.ref(ctx.side_rel), "target": ctx.side["target"],
            "contract": reg["contract"], "version_config": vconf,
            "refs": [{"ref": w["ref"], "commit": w["commit"], "time": w["time"], "error": w["error"],
                      "builds": w["builds"]} for w in rows],
            "versions": versions, "edges": edges}


def member_builds(ctx: Ctx, log=print) -> dict:
    """{member: {config: identity}} of the acquisition's members at the target's head, every configuration."""
    solc, deps = _toolchain(ctx)
    acq = ctx.side["acquisition"]
    repo = ctx.source_repo()
    out = {}
    with tempfile.TemporaryDirectory(prefix="holon-bundle-heads-") as td:
        tree = Path(td) / "head"
        tree.mkdir()
        _materialize(repo, ctx.side["target"]["head"], tree, ["contracts"])
        for m, c in sorted(acq["members"].items()):
            out[m] = {cname: ident(compile_build(solc, deps, tree, c["source"], c["name"], conf))
                      for cname, conf in sorted(acq["compiler_configs"].items())}
            log(f"head build of {m}: done")
    return out


def main_history(ctx: Ctx, check: bool, log) -> int:
    doc = history(ctx, log)
    return write_or_check(ctx, {ctx.out("history"): render(doc)}, check, log=log)


# ------------------------------------------------------------------------------------------------------ A4-A5
def _low20(word: str) -> str:
    w = word.lower()[2:] if word.startswith("0x") else word.lower()
    if len(w) != 64 or int(w[:24] or "0", 16) != 0:
        raise BundleError(f"{word} is not an address word")
    return "0x" + w[-40:]


def decode(receipt: dict, proxy: str, events: dict) -> dict:
    """A4: the proxy's logs in a receipt, by log index: Upgraded implementations, Initialized versions, AdminChanged
    pairs; the receipt's from and contractAddress."""
    ev = {k: v.lower() for k, v in events.items()}
    up, ini, adm = [], [], []
    for lg in sorted(receipt.get("logs") or [], key=lambda x: int(x["logIndex"], 16)):
        if (lg.get("address") or "").lower() != proxy.lower() or not lg.get("topics"):
            continue
        t0 = lg["topics"][0].lower()
        data = lg["data"][2:]
        words = [data[i:i + 64] for i in range(0, len(data), 64)]
        if t0 == ev["Upgraded"]:
            up.append("0x" + lg["topics"][1][-40:].lower())
        elif t0 == ev["Initialized"]:
            ini.append(int(words[0], 16))
        elif t0 == ev["AdminChanged"]:
            adm.append({"previous": "0x" + words[0][-40:].lower(), "new": "0x" + words[1][-40:].lower()})
    return {"upgraded": up, "initialized": ini, "admin_changed": adm, "from": (receipt.get("from") or "").lower(),
            "contract_address": (receipt.get("contractAddress") or "").lower() or None}


def match(entries: dict, code: bytes) -> list:
    """A5: every [key, config] of {key: {config: identity}} whose identity the code has under that build's ranges."""
    from ..frontends.solidity.history import identity
    hits = []
    for key in sorted(entries):
        for cname in sorted(entries[key]):
            b = entries[key][cname]
            if sha256_bytes(identity(code, b["ranges"])) == b["sha256"]:
                hits.append([key, cname])
    return hits


def immutable_words(code: bytes, build: dict) -> dict:
    return {k: sorted({"0x" + code[s:s + n].hex() for s, n in rs}) for k, rs in build["immutables"].items()}


def _registry_entries(ctx: Ctx) -> dict:
    h = ctx.load(ctx.out("history"))
    return {v["id"]: v["code"] for v in h["versions"]}


def _member_slot(ctx: Ctx, member: str, family: str) -> int:
    doc = ctx.load(ctx.document_rel(ctx.member(member)))
    hits = [s["slot"] for s in doc["storage"] if s["name"] == family]
    if len(hits) != 1:
        raise Refused(f"{member}'s document has {len(hits)} storage families {family}")
    return int(hits[0])


# ------------------------------------------------------------------------------------------------------ A3 fetch
def slot_entry(acq: dict) -> str:
    """The name of the acquisition entry read from a member's storage slot (its "slot_of")."""
    keys = [k for k, v in acq.items() if isinstance(v, dict) and "slot_of" in v]
    if len(keys) != 1:
        raise Refused(f"the acquisition has {len(keys)} entries with a slot_of")
    return keys[0]


def _proxy_order(acq: dict) -> list:
    """Proxies with an address first (sorted), then those derived from another proxy's immutable word."""
    direct = sorted(p for p, x in acq["proxies"].items() if x.get("address"))
    derived = sorted(p for p, x in acq["proxies"].items() if not x.get("address"))
    return direct + derived


def _logs(rpc, address: str, topics: list, lo: int, hi: int, log=print) -> list:
    from ..historical.net import SourceError, TransientError
    out, a, step = [], lo, 1000000
    while a <= hi:
        b = min(hi, a + step - 1)
        try:
            got = rpc.call("eth_getLogs", [{"address": address, "topics": [topics], "fromBlock": hex(a),
                                            "toBlock": hex(b)}])
        except (SourceError, TransientError) as e:
            if step <= 500:
                raise BundleError(f"eth_getLogs {address} [{a}, {b}]: {e}") from e
            step //= 4
            continue
        out.extend(got or [])
        a = b + 1
        step = min(step * 2, 4000000)
    return out


def fetch(ctx: Ctx, log=print) -> tuple:
    """A3: (snapshot document, {tx: canonical receipt bytes}, {address: code bytes})."""
    from ..historical.net import Http, Rpc, SourceError, TransientError, host
    from ..historical.store import canon_bytes
    acq = ctx.side["acquisition"]
    events = acq["events"]
    topics = sorted(v.lower() for v in events.values())
    lo, hi = acq["window"]["from_block"], acq["window"]["to_block"]
    url = acq["rpc"]["url"]
    rpc = Rpc(Http(), url)
    builds = member_builds(ctx, log)
    try:
        fb = int(rpc.call("eth_blockNumber", []), 16)
        if fb < hi:
            raise BundleError(f"the latest block {fb} is before the window's end {hi}")
        proxies, receipts, codes = {}, {}, {}

        def code_at(addr: str) -> bytes:
            if addr not in codes:
                codes[addr] = bytes.fromhex((rpc.call("eth_getCode", [addr, hex(fb)]) or "0x")[2:])
            return codes[addr]
        for pname in _proxy_order(acq):
            spec = acq["proxies"][pname]
            addr = (spec.get("address") or "").lower()
            if not addr:
                src = spec["immutable"]
                ups = [u for u in proxies[src["member"]]["upgrades"] if u["block"] <= hi]
                if not ups:
                    raise BundleError(f"{src['member']} has no upgrade in the window")
                code = codes[ups[-1]["implementation"]]
                hits = match({src["member"]: builds[src["member"]]}, code)
                if len(hits) != 1:
                    raise BundleError(f"{src['member']}'s last implementation matches {hits}: no {src['name']} word")
                words = immutable_words(code, builds[src["member"]][hits[0][1]]).get(src["name"]) or []
                if len(words) != 1:
                    raise BundleError(f"{src['member']}'s last implementation: {len(words)} {src['name']} words")
                addr = _low20(words[0])
            raw = _logs(rpc, addr, topics, lo, fb, log)
            rows = sorted(({"block": int(x["blockNumber"], 16), "tx": x["transactionHash"].lower(),
                            "log_index": int(x["logIndex"], 16), "topics": [t.lower() for t in x["topics"]],
                            "data": x["data"].lower()} for x in raw if x["address"].lower() == addr),
                          key=lambda r: (r["block"], r["log_index"]))
            ups = []
            for r in rows:
                if r["topics"][0] != events["Upgraded"].lower():
                    continue
                if r["tx"] not in receipts:
                    rc = rpc.call("eth_getTransactionReceipt", [r["tx"]])
                    if not isinstance(rc, dict):
                        raise BundleError(f"{r['tx']}: no receipt")
                    receipts[r["tx"]] = canon_bytes(rc, "receipt")
                impl = _low20(r["topics"][1])
                code = code_at(impl)
                ups.append({"block": r["block"], "tx": r["tx"], "log_index": r["log_index"],
                            "receipt_sha256": sha256_bytes(receipts[r["tx"]]), "implementation": impl,
                            "code_sha256": sha256_bytes(code), "code_length": len(code)})
            slot = acq["eip1967"]["implementation_slot"].lower()
            word = rpc.call("eth_getStorageAt", [addr, slot, hex(fb)]).lower()
            proxies[pname] = {"address": addr, "logs": rows, "upgrades": ups,
                              "implementation_slot": {"slot": slot, "block": fb, "word": word}}
            log(f"{pname} {addr}: {len(rows)} logs, {len(ups)} upgrades")
        wkey = slot_entry(acq)
        so = acq[wkey]["slot_of"]
        wslot = _member_slot(ctx, so["member"], so["family"])
        wproxy = proxies[so["member"]]["address"]
        wword = rpc.call("eth_getStorageAt", [wproxy, hex(wslot), hex(fb)]).lower()
        waddr = _low20(wword)
        wcode = code_at(waddr)
        wl = {"proxy": wproxy, "slot": wslot, "block": fb, "word": wword, "address": waddr,
              "code_sha256": sha256_bytes(wcode), "code_length": len(wcode)}
    except (SourceError, TransientError, KeyError, ValueError, IndexError, TypeError) as e:
        raise BundleError(f"fetch: {e}") from e
    for a, c in codes.items():
        if not c:
            raise BundleError(f"{a} has no code at block {fb}")
    doc = {"onchain_version": ONCHAIN_VERSION, "sidecar": ctx.ref(ctx.side_rel),
           "rpc": {"host": host(url), "methods": acq["rpc"]["methods"]}, "fetch_block": fb, "window": [lo, hi],
           "proxies": proxies, wkey: wl}
    return doc, receipts, codes


def snapshot_files(ctx: Ctx, doc: dict, receipts: dict, codes: dict) -> dict:
    files = {ctx.out("onchain"): render(doc)}
    for tx, b in receipts.items():
        files[f"{ctx.out('receipts')}/{tx}.json"] = b
    for a, c in codes.items():
        files[f"{ctx.out('code')}/{a}.hex"] = (c.hex() + "\n").encode()
    return files


def check_snapshot(ctx: Ctx) -> list:
    """fetch --check, offline: the snapshot's files and fields agree with each other and with the sidecar."""
    bad = []
    try:
        doc = ctx.load(ctx.out("onchain"))
    except (OSError, ValueError) as e:
        return [f"{ctx.out('onchain')}: {e}"]
    acq = ctx.side["acquisition"]
    if doc.get("sidecar") != ctx.ref(ctx.side_rel):
        bad.append("the snapshot's sidecar is not the current sidecar")
    if doc.get("window") != [acq["window"]["from_block"], acq["window"]["to_block"]]:
        bad.append("the snapshot's window is not the sidecar's")
    rdir, cdir = ctx.path(ctx.out("receipts")), ctx.path(ctx.out("code"))
    want_r, want_c = set(), set()
    for pname, px in sorted(doc.get("proxies", {}).items()):
        if acq["proxies"][pname].get("address") and px["address"] != acq["proxies"][pname]["address"].lower():
            bad.append(f"{pname}: the address is not the sidecar's")
        ups = [r for r in px["logs"] if r["topics"][0] == acq["events"]["Upgraded"].lower()]
        if [(u["block"], u["tx"], u["log_index"]) for u in px["upgrades"]] != \
                [(r["block"], r["tx"], r["log_index"]) for r in ups]:
            bad.append(f"{pname}: the upgrades are not the Upgraded logs")
        for u in px["upgrades"]:
            rp, cp = rdir / f"{u['tx']}.json", cdir / f"{u['implementation']}.hex"
            want_r.add(rp.name)
            want_c.add(cp.name)
            if not rp.is_file() or sha256_bytes(rp.read_bytes()) != u["receipt_sha256"]:
                bad.append(f"receipt {u['tx']} is missing or not the snapshot's")
            if not cp.is_file() or sha256_bytes(bytes.fromhex(cp.read_text().strip())) != u["code_sha256"]:
                bad.append(f"code {u['implementation']} is missing or not the snapshot's")
    wl = doc.get(slot_entry(acq)) or {}
    cp = cdir / f"{wl.get('address')}.hex"
    want_c.add(cp.name)
    if not cp.is_file() or sha256_bytes(bytes.fromhex(cp.read_text().strip())) != wl.get("code_sha256"):
        bad.append("the slot entry's code is missing or not the snapshot's")
    for d, want in ((rdir, want_r), (cdir, want_c)):
        extra = sorted(p.name for p in d.glob("*") if p.name not in want) if d.is_dir() else []
        if extra:
            bad.append(f"{d.relative_to(ctx.root)}: files the snapshot does not name: {extra[:5]}")
    return bad


def main_fetch(ctx: Ctx, check: bool, log) -> int:
    if check:
        bad = check_snapshot(ctx)
        for b in bad:
            log(b)
        log("the snapshot is consistent" if not bad else f"{len(bad)} differences")
        return 0 if not bad else 1
    if not ctx.path(ctx.out("history")).is_file():
        raise Refused(f"{ctx.out('history')} is missing (holon bundle history first)")
    doc, receipts, codes = fetch(ctx, log)
    files = snapshot_files(ctx, doc, receipts, codes)
    return write_or_check(ctx, files, False, owned=[ctx.out("receipts"), ctx.out("code")], log=log)


# ------------------------------------------------------------------------------------------------------ A6 timeline
def timeline(ctx: Ctx, builds: dict, log=print) -> dict:
    """A6 over the committed snapshot (the format of the bundle contract's timeline)."""
    acq = ctx.side["acquisition"]
    snap = ctx.load(ctx.out("onchain"))
    lo, hi = acq["window"]["from_block"], acq["window"]["to_block"]
    fb = snap["fetch_block"]
    reg = _registry_entries(ctx)
    out = {"fetch_block": fb, "window": [lo, hi], "proxies": {}}
    for pname in _proxy_order(acq):
        px = snap["proxies"][pname]
        ups, after = [], []
        for r in sorted((r for r in px["logs"] if r["topics"][0] == acq["events"]["Upgraded"].lower()),
                        key=lambda r: (r["block"], r["log_index"])):
            impl = _low20(r["topics"][1])
            rc = json.loads(ctx.path(f"{ctx.out('receipts')}/{r['tx']}.json").read_bytes())
            dec = decode(rc, px["address"], acq["events"])
            code = bytes.fromhex(ctx.path(f"{ctx.out('code')}/{impl}.hex").read_text().strip())
            # a proxy that is no acquisition member is the registry's: its implementations match the versions
            entries = reg if pname not in acq["members"] else ({pname: builds[pname]} if pname in builds else {})
            hits = match(entries, code)
            imm = immutable_words(code, entries[hits[0][0]][hits[0][1]]) if len(hits) == 1 else {}
            u = {"block": r["block"], "tx": r["tx"], "log_index": r["log_index"], "implementation": impl,
                 "decoded": dec, "matches": hits, "immutables": imm}
            (ups if r["block"] <= hi else after).append(u)
        last = (ups + after)[-1]["implementation"] if ups + after else None
        out["proxies"][pname] = {"address": px["address"], "upgrades": ups, "after_window": after, "current": last}
    wkey_out = slot_entry(acq)
    wl = snap[wkey_out]
    wcode = bytes.fromhex(ctx.path(f"{ctx.out('code')}/{wl['address']}.hex").read_text().strip())
    # the member the slot's word names: the acquisition member without a proxy
    plain = [k for k in sorted(acq["members"]) if k not in acq["proxies"]]
    wkey = plain[0] if len(plain) == 1 else None
    out[wkey_out] = {"address": wl["address"],
                        "matches": match({wkey: builds[wkey]}, wcode) if wkey else []}
    return out


def main_timeline(ctx: Ctx, check: bool, log) -> int:
    bad = check_snapshot(ctx)
    if bad:
        raise Refused(f"the snapshot is not consistent: {bad[:3]}")
    doc = timeline(ctx, member_builds(ctx, log), log)
    return write_or_check(ctx, {ctx.out("timeline"): render(doc)}, check, log=log)
