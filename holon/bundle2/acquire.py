"""holon bundle2 acquire (rules A1-A3 of the contract): acquisition notes from committed records and the target
repository's git objects; nothing is read from the network.

  anchor  the UpdateVerifier logs of the sidecar's anchor receipt (an earlier key's committed receipt): the emitter, the
          old and new verifier and the block, and the receipt's sha256
  tags    the blobs of every member's units (the sidecar's acquisition.units) at every pinned tag (checked at its pin)
          and at the head, from tree listings (git ls-tree; lazy fetching disabled, no blob read)
  builds  every non-adopted member's head build under every compiler configuration of the sidecar: the code identity
          (immutable and link ranges zeroed, the CBOR metadata dropped: holon.frontends.solidity.history.identity), its
          length and ranges
  to_read the sidecar's list of what remains to be read on chain
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import BundleError, Ctx, Refused, Writer, file_sha, render, sha256_bytes

ACQ_VERSION = "holon-bundle2-acquisition/0.1"


def _git(repo: str, *args: str, binary: bool = False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", LC_ALL="C")
    p = subprocess.run(["git", "-C", repo, "-c", "protocol.allow=never", "-c", "gc.auto=0", "-c",
                        "maintenance.auto=false", *args], capture_output=True, env=env, stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode()


def anchor(ctx: Ctx) -> dict:
    from ..keccak import keccak256
    a = ctx.side["acquisition"]["anchor"]
    p = ctx.root / a["receipt"]
    if not p.is_file():
        raise Refused(f"{a['receipt']} is missing")
    rc = json.loads(p.read_text())
    rc = rc.get("receipt", rc)
    t0 = "0x" + keccak256(a["event"].encode()).hex()
    logs = []
    for lg in rc.get("logs") or []:
        tp = lg.get("topics") or []
        if tp and tp[0].lower() == t0:
            logs.append({"block": int(lg["blockNumber"], 16), "emitter": lg["address"].lower(),
                         "new": "0x" + tp[2][-40:].lower(), "old": "0x" + tp[1][-40:].lower()})
    return {"logs": logs, "receipt": a["receipt"], "receipt_sha256": file_sha(p)}


def tags(ctx: Ctx) -> dict:
    repo = ctx.source()
    acq = ctx.side["acquisition"]
    refs = {}
    for t, c in sorted(acq["tags"].items()):
        got = _git(repo, "rev-parse", "--verify", "-q", f"{t}^{{commit}}").strip()
        if got != c:
            raise Refused(f"tag {t} is at {got}, not its pin {c}")
        refs[t] = c
    refs["head"] = ctx.side["target"]["head"]
    out = {}
    for ref, c in sorted(refs.items()):
        out[ref] = {}
        for m, units in sorted(acq["units"].items()):
            have = {}
            for ln in _git(repo, "ls-tree", c, "--", *units).splitlines():
                if ln.strip():
                    meta, path = ln.split("\t", 1)
                    have[path] = meta.split()[2]
            out[ref][m] = {u: have.get(u) for u in units}
    return out


def builds(ctx: Ctx) -> dict:
    import io
    import tarfile
    from ..frontends.solidity import history as Hh
    from ..replay import tree_sha256
    cfg = ctx.cfg.get("replay") or {}
    solc = cfg.get("solc")
    nm = Path(cfg.get("sol_deps") or "") / "node_modules"
    if not solc or file_sha(Path(solc)) != cfg.get("solc_sha256"):
        raise Refused("the pinned solc (config replay.solc, replay.solc_sha256) is missing or differs")
    if not nm.is_dir() or tree_sha256(nm) != cfg.get("sol_deps_sha256"):
        raise Refused("the pinned Solidity dependencies (config replay.sol_deps_sha256) are missing or differ")
    out = {}
    with tempfile.TemporaryDirectory(prefix="holon-bundle2-acq-") as td:
        tree = Path(td) / "head"
        tree.mkdir()
        data = _git(ctx.source(), "archive", "--format=tar", ctx.side["target"]["head"], "--", "contracts",
                    binary=True)
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            tf.extractall(tree, filter="data")
        for m in sorted([x for x in ctx.members() if not x.get("adopted")] + ctx.extracted_only(),
                        key=lambda x: x["name"]):

            class _C:
                side = {"contract": {"source": m["source"], "name": m["contract"]}}
            out[m["name"]] = {}
            for cname, conf in sorted(ctx.side["acquisition"]["compiler_configs"].items()):
                try:
                    b = Hh.compile_ref(_C, solc, nm, tree, conf)
                except Exception as e:   # noqa: BLE001: a failed build is an error of the command
                    raise BundleError(f"{m['name']} under {cname}: {e}")
                out[m["name"]][cname] = {"length": len(b["code"]), "ranges": b["ranges"],
                                         "sha256": sha256_bytes(Hh.identity(b["code"], b["ranges"]))}
    return out


def run(ctx: Ctx, check: bool) -> int:
    doc = {"acquisition_version": ACQ_VERSION, "sidecar": {"path": ctx.side_rel, "sha256": ctx.side_sha},
           "anchor": anchor(ctx), "tags": tags(ctx), "builds": builds(ctx),
           "to_read": list(ctx.side["acquisition"].get("to_read") or [])}
    w = Writer(check)
    w.put(ctx.path("acquisition"), render(doc))
    return w.finish("acquire")
