"""I4 consumer replays: what real Morph Go code does with the bytes an on-chain replay produced.

Two library-level replays (provenance "library_api"), each a Go test run against a scratch copy of
the pinned Morph checkout (the checkout itself is never touched):

  L_tag_BVH  replay/M1/go/holon_consumer_test.go in common/batch. It feeds the 257-byte version-2
             header the real Rollup committed to BatchHeaderBytes (Version, BlobCommitHash) and
             recomputes, with the real aggregateBlobHashes, the aggregate a version-2 consumer
             expects in the blob field from the stored v1 versioned hash.
  L_fact_Z   replay/M1/go/holon_derivation_test.go in node/derivation. It hands the real
             (*BatchInfo).ParseBatch the two commits that produced the same committedBatches hash on
             chain (no blob vs one all-zero blob) with their blob sidecars and records each outcome.

Inputs reach the Go tests through holon_consumer.json, written beside the test and named by the
HOLON_CONSUMER environment variable. The Go side prints `HOLON <law> ...` lines; this module turns
them into a side object. The side's status and obstruction_observed are decided here, from the
values Go printed, never from a model or an oracle:

  passed   the real code ran on the replayed bytes and read them as the chain replay says;
  failed   the real code contradicts the chain replay's reading (a model defect);
  not_run  the input was malformed or the toolchain / build broke (observed says which).

Only a passed side may observe the obstruction. Side objects are deterministic: hex is lower-case
and 0x-prefixed, and no value carries a timestamp or an absolute path.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .oracles.zero_blob import compute as zero_versioned_hash

ROOT = Path(__file__).resolve().parents[1]
GO_SRC = ROOT / "replay" / "M1" / "go"
INPUT = "holon_consumer.json"
TIMEOUT = 3600
PROVENANCE = "library_api"
GO_VERSION_LINE = "go 1.24.0"
COMMIT_FIELDS = ("version", "last_block_number", "num_l1_messages", "prev_state_root", "post_state_root",
                 "withdraw_root", "blobs")
HASH_FIELDS = ("prev_state_root", "post_state_root", "withdraw_root")
NO_BUN_CONFIG = shutil.ignore_patterns(".env", ".env.*", "bunfig.toml")

TAG_OK = re.compile(r"^HOLON L_tag_BVH version=(\d+) blob_commit_hash=(0x[0-9a-f]{64}) aggregate=(0x[0-9a-f]{64}) "
                    r"differ=(true|false)$", re.M)
TAG_ERR = re.compile(r"^HOLON L_tag_BVH error (\w+): (\".*\")$", re.M)
FZ_VH = re.compile(r"^HOLON L_fact_Z zero_blob_vh (0x[0-9a-f]{64})$", re.M)
FZ_OUT = re.compile(r"^HOLON L_fact_Z (\w+) sidecar_blobs=(\d+) outcome=(\".*\")$", re.M)
FZ_ERR = re.compile(r"^HOLON L_fact_Z error (\w+): (\".*\")$", re.M)


# ---------------------------------------------------------------- helpers
def _hexbytes(h) -> bytes | None:
    """Bytes of a 0x-prefixed hex string, or None when it is not one."""
    if not isinstance(h, str) or not h.startswith(("0x", "0X")):
        return None
    try:
        return bytes.fromhex(h[2:])
    except ValueError:
        return None


def _hex(b: bytes) -> str:
    return "0x" + b.hex()


def _go_binary(go: str | None) -> str | None:
    if go:
        return go
    found = shutil.which("go")
    if found:
        return found
    return "/usr/local/go/bin/go" if Path("/usr/local/go/bin/go").is_file() else None


def _env(input_name: str) -> dict:
    """The environment of every go call: no inherited workspace or flags, the local toolchain only."""
    env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS", "HOLON_CONSUMER")}
    env.update({"GOTOOLCHAIN": "local", "HOLON_CONSUMER": input_name})
    return env


def _workspace(morph: Path, ws: Path, dirs: tuple[str, ...]) -> None:
    """A fresh scratch copy of the named morph module directories under one go.work.

    Bun configuration (.env*, bunfig.toml; e.g. node/ops-morph/.env) is never copied: the scratch
    lives inside the repo, where AGENTS.md rule 8 forbids it. Go does not read these files.
    """
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for d in dirs:
        shutil.copytree(morph / d, ws / d, symlinks=True, ignore=NO_BUN_CONFIG)
    (ws / "go.work").write_text(GO_VERSION_LINE + "\n\nuse (\n" + "".join(f"\t./{d}\n" for d in dirs) + ")\n")
    if (morph / "go.work.sum").is_file():
        shutil.copy(morph / "go.work.sum", ws / "go.work.sum")


def _scrub(text: str, paths: list[tuple[Path, str]]) -> str:
    """Replace absolute scratch / checkout / cache paths in Go output with stable placeholders."""
    for p, name in sorted(paths, key=lambda x: -len(str(x[0]))):
        text = text.replace(str(p), name)
    return text


def _tail(out: str, n: int = 3) -> str:
    skip = ("=== RUN", "--- ", "PASS", "FAIL", "ok ")
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith(skip)]
    return " | ".join(lines[-n:]) if lines else "(no output)"


def _go_run(go: str, morph: Path, ws: Path, module: str, pkg: str, test: str) -> tuple[str, str, str]:
    """Run one Go test in the scratch workspace: (scrubbed output, exit summary, command)."""
    env = _env(INPUT)
    gv = subprocess.run([go, "version"], capture_output=True, text=True, env=env, timeout=120).stdout.strip()
    gv = gv or "go version unknown"
    cmd = [go, "test", f"./{pkg}", "-run", f"^{test}$", "-v", "-count=1"]
    try:
        p = subprocess.run(cmd, cwd=ws / module, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        out, done = p.stdout + p.stderr, f"exit {p.returncode}"
    except subprocess.TimeoutExpired as e:
        part = e.stdout or b""
        out, done = (part.decode(errors="replace") if isinstance(part, bytes) else part), f"timed out after {TIMEOUT}s"
    cache = subprocess.run([go, "env", "GOMODCACHE", "GOCACHE"], capture_output=True, text=True, env=env, timeout=120)
    paths = [(ws, "<scratch>"), (morph, "<morph>")]
    paths += [(Path(c), n) for c, n in zip(cache.stdout.splitlines(), ("<gomodcache>", "<gocache>")) if c.strip()]
    shown = (f"(cd {module} && GOTOOLCHAIN=local HOLON_CONSUMER={INPUT} go test ./{pkg} -run '^{test}$' -v -count=1)"
             f"  # {done}; {gv}")
    return _scrub(out, paths), done, shown


# ---------------------------------------------------------------- L_tag_BVH
def tag_bvh_side(morph: Path, work: Path, header: str, stored_vh: str, go: str | None = None) -> dict:
    """The go_consumer side of L_tag_BVH: common/batch reads the committed version-2 header.

    `header` is the 257-byte header the real Rollup committed, `stored_vh` the v1 blob versioned
    hash stored for that batch index (both 0x hex). The scratch workspace is `work`/tag_bvh.
    """
    hb, vb = _hexbytes(header), _hexbytes(stored_vh)
    side = {"status": "not_run", "provenance": PROVENANCE, "obstruction_observed": False, "observed": "",
            "command": "", "input_header": _hex(hb) if hb is not None else header,
            "blob_commit_hash": None, "aggregate": None}
    if hb is None or vb is None or len(vb) != 32:
        side["observed"] = "not run: the input header / stored_vh is not 0x hex (stored_vh must be 32 bytes)"
        return side
    if len(hb) != 257:
        side["observed"] = f"not run: the input header is {len(hb)} bytes, not a 257-byte version-1/2 header"
        return side
    gobin = _go_binary(go)
    if gobin is None:
        side["observed"] = "not run: no go toolchain on PATH"
        return side
    morph, ws = Path(morph).resolve(), Path(work).resolve() / "tag_bvh"
    try:
        _workspace(morph, ws, ("bindings", "common"))
        shutil.copy(GO_SRC / "holon_consumer_test.go", ws / "common" / "batch")
        (ws / "common" / "batch" / INPUT).write_text(
            json.dumps({"header": _hex(hb), "stored_vh": _hex(vb)}, indent=2, sort_keys=True) + "\n")
        out, done, side["command"] = _go_run(gobin, morph, ws, "common", "batch", "TestHolonTagBVH")
    except (OSError, subprocess.SubprocessError) as e:
        side["observed"] = f"not run: the scratch workspace or go toolchain failed ({type(e).__name__})"
        return side

    oks, errs = TAG_OK.findall(out), TAG_ERR.findall(out)
    field, vh = _hex(hb[57:89]), _hex(vb)
    if len(oks) + len(errs) != 1:
        side["observed"] = (f"not run: go test printed {len(oks) + len(errs)} HOLON L_tag_BVH lines "
                            f"({done}): {_tail(out)}")
        return side
    if errs:
        stage, msg = errs[0][0], json.loads(errs[0][1])
        if stage == "input":
            side["observed"] = f"not run: the Go test could not read its input: {msg}"
        else:
            side["status"] = "failed"
            side["observed"] = (f"{stage}() returned an error on the committed 257-byte header (byte 0 = {hb[0]}): {msg}; "
                                f"the chain replay reads it as a version-2 header with blob field {field}")
        return side

    version, bch, agg, go_differ = int(oks[0][0]), oks[0][1], oks[0][2], oks[0][3] == "true"
    side["blob_commit_hash"], side["aggregate"] = bch, agg
    differ = agg != bch
    same_vh = "the stored v1 versioned hash" if field == vh else f"NOT the stored v1 versioned hash {vh}"
    if version != 2 or bch != field:
        side["status"] = "failed"
        side["observed"] = (f"BatchHeaderBytes reads version {version} and BlobCommitHash() {bch}, but the chain "
                            f"replay committed a version-2 header whose blob field header[57:89] is {field}")
    elif go_differ != differ:
        side["status"] = "failed"
        side["observed"] = f"Go's differ flag ({str(go_differ).lower()}) disagrees with its printed values ({bch} vs {agg})"
    else:
        side["status"] = "passed"
        # the obstruction: the field a version-2 consumer checks is the stored v1 versioned hash, and the
        # aggregate it recomputes from that hash differs from it
        side["obstruction_observed"] = differ and field == vh
        side["observed"] = (f"BatchHeaderBytes reads version 2 and BlobCommitHash() = header[57:89] = {bch} "
                            f"({same_vh}); aggregateBlobHashes([stored_vh]) = {agg}, which "
                            f"{'differs from' if differ else 'equals'} the field a version-2 consumer checks")
    return side


# ---------------------------------------------------------------- L_fact_Z
def _commit_input(label: str, c) -> tuple[dict | None, str]:
    """The commit fields the Go test reads, normalised; (None, why) when malformed."""
    if not isinstance(c, dict):
        return None, f"commit {label} is not an object"
    missing = [k for k in COMMIT_FIELDS if k not in c]
    if missing:
        return None, f"commit {label} lacks {', '.join(missing)}"
    out = {}
    for k in COMMIT_FIELDS:
        v = c[k]
        if k in HASH_FIELDS:
            b = _hexbytes(v)
            if b is None or len(b) != 32:
                return None, f"commit {label}: {k} is not a 0x-prefixed bytes32"
            out[k] = _hex(b)
        else:
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                return None, f"commit {label}: {k} is not a non-negative integer"
            out[k] = v
    return out, ""


def fact_z_side(morph: Path, work: Path, parent_header: str, commits: dict, go: str | None = None) -> dict:
    """The go_consumer side of L_fact_Z: node/derivation ParseBatch on the two equal-commitment commits.

    `parent_header` is the header the chain replay committed on (0x hex); `commits` maps each label
    ("c1", "c2") to {version, last_block_number, num_l1_messages, prev_state_root, post_state_root,
    withdraw_root, blobs}, where `blobs` is the number of all-zero blobs the commit carried. The
    scratch workspace is `work`/fact_z.
    """
    pb = _hexbytes(parent_header)
    labels = sorted(commits) if isinstance(commits, dict) else []
    side = {"status": "not_run", "provenance": PROVENANCE, "obstruction_observed": False, "observed": "",
            "command": "", "input_parent_header": _hex(pb) if pb is not None else parent_header,
            "sidecar_blobs": {}, "outcomes": {}, "zero_blob_vh": None}
    if pb is None:
        side["observed"] = "not run: the parent header is not 0x hex"
        return side
    if len(labels) < 2 or not all(isinstance(lb, str) and re.fullmatch(r"\w+", lb) for lb in labels):
        side["observed"] = "not run: need at least two commits with word labels (c1, c2)"
        return side
    norm = {}
    for lb in labels:
        c, why = _commit_input(lb, commits[lb])
        if c is None:
            side["observed"] = f"not run: {why}"
            return side
        norm[lb] = c
    gobin = _go_binary(go)
    if gobin is None:
        side["observed"] = "not run: no go toolchain on PATH"
        return side
    morph, ws = Path(morph).resolve(), Path(work).resolve() / "fact_z"
    try:
        _workspace(morph, ws, ("bindings", "common", "node"))
        shutil.copy(GO_SRC / "holon_derivation_test.go", ws / "node" / "derivation")
        (ws / "node" / "derivation" / INPUT).write_text(
            json.dumps({"parent_header": _hex(pb), "commits": norm}, indent=2, sort_keys=True) + "\n")
        out, done, side["command"] = _go_run(gobin, morph, ws, "node", "derivation", "TestHolonFactZ")
    except (OSError, subprocess.SubprocessError) as e:
        side["observed"] = f"not run: the scratch workspace or go toolchain failed ({type(e).__name__})"
        return side

    errs = FZ_ERR.findall(out)
    vhs = FZ_VH.findall(out)
    got = {}
    for lb, n, o in FZ_OUT.findall(out):
        if lb in got:
            got[lb] = None  # duplicated: ambiguous
        else:
            got[lb] = (int(n), json.loads(o))
    if len(vhs) == 1:
        side["zero_blob_vh"] = vhs[0]
    if errs:
        stage, msg = errs[0][0], json.loads(errs[0][1])
        side["observed"] = f"not run: the Go test could not build ParseBatch's input ({stage}): {msg}"
        return side
    if set(got) != set(labels) or any(v is None for v in got.values()) or len(vhs) != 1:
        side["observed"] = (f"not run: go test did not report ParseBatch on every commit "
                            f"({done}): {_tail(out)}")
        return side
    side["sidecar_blobs"] = {lb: got[lb][0] for lb in labels}
    side["outcomes"] = {lb: got[lb][1] for lb in labels}
    asked = {lb: norm[lb]["blobs"] for lb in labels}
    if side["sidecar_blobs"] != asked:
        side["observed"] = f"not run: the Go test built sidecars {side['sidecar_blobs']}, not the {asked} the commits carried"
        return side
    zvh = zero_versioned_hash()
    desc = "; ".join(f"{lb} ({asked[lb]} all-zero blob{'' if asked[lb] == 1 else 's'}) -> {side['outcomes'][lb]}"
                     for lb in labels)
    if any(asked.values()) and side["zero_blob_vh"] != zvh:
        side["status"] = "failed"
        side["observed"] = (f"the all-zero blob's KZG versioned hash in Go is {side['zero_blob_vh']}, not "
                            f"ZERO_VERSIONED_HASH {zvh}, so the blob commits are not the ones the chain replay "
                            f"committed; ParseBatch on the same parent header: {desc}")
        return side
    differ = len(set(side["outcomes"].values())) > 1
    side["status"] = "passed"
    side["obstruction_observed"] = differ
    eq = "=" if side["zero_blob_vh"] == zvh else "!="
    side["observed"] = (f"ParseBatch on the same parent header: {desc}; the all-zero blob's versioned hash is "
                        f"{side['zero_blob_vh']} ({eq} ZERO_VERSIONED_HASH); outcomes {'differ' if differ else 'agree'}")
    return side
