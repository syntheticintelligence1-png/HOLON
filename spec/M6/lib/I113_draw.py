"""I113's draw (docs/BUILD_PLAN.md §3 row I113, HUMAN_ANSWERS Q54 (b)-(c), Q55 (2), Q86 (2)): commit-reveal selection of
fresh sealed targets, second draw. I106_draw.py generalized in a new file: the same seed, order, draw, pin rule and
canonical form, over I113's candidates, for spec/heldout3/.

Standard library only. Deterministic: no clock, no randomness, no network. Every input is an argument or a file.

Byte conventions
  salt       32 bytes, written as 64 lowercase hex characters (spec/heldout3/salt.txt after the reveal: those 64
             characters and one final newline). salt_sha256 = sha256(the 32 raw bytes), lowercase hex.
  blockhash  the beacon block's hash, 32 bytes, written as "0x" and 64 lowercase hex characters.
  seed       sha256(salt bytes || blockhash bytes): the 32 raw salt bytes followed by the 32 raw hash bytes (64 bytes
             in all, no separator, no hex text), lowercase hex.

The draw (2 without replacement)
  Each candidate c of spec/M6/lib/I113_candidates.json gets the key sha256(seed bytes || utf8(c.id)). The order is
  the candidates sorted by that key (hex, ascending), ties by id. The drawn targets are the first 2 of the order
  whose repository answers `git ls-remote` (the resolvable rule): a candidate whose repository does not answer is
  skipped, recorded as skipped with the reason, and the next one is taken. The candidate file's own order plays no
  part.

The pin rule (HUMAN_ANSWERS Q55 (2); from `git ls-remote <repo>` output only, no clone, no dates)
  A release tag is a ref refs/tags/<name> whose <name> matches ^v?(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$
  (strict MAJOR.MINOR.PATCH, an optional leading v, no prerelease or build suffix, no path prefix). If there is at
  least one, the pin is the release tag with the greatest (MAJOR, MINOR, PATCH), ties by the smaller ref name; its
  commit is the peeled object (the refs/tags/<name>^{} line) when present, else the ref's object. Otherwise the pin
  is the default branch: the symref target of HEAD (`git ls-remote --symref <repo> HEAD`) and its commit.
  The listing is taken once per drawn target, soon after T; "latest release at T" is approximated by the greatest
  version present then (ls-remote carries no dates). A release tag pushed between T and the listing is a residual
  risk, disclosed by recording the listing's UTC time in target.json.

target.json is canonical JSON: json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) and one final newline.
target_sha256 = sha256 of exactly those bytes.

Usage
  python3 spec/M6/lib/I113_draw.py order   --salt-file F --blockhash 0x..           print the full order as JSON
  python3 spec/M6/lib/I113_draw.py pin     --ls-remote F [--symref F2]              print the pin of one listing
  python3 spec/M6/lib/I113_draw.py seal    --salt-file F --block-number N --blockhash 0x.. --block-timestamp S
                                           --beacon-source TEXT --listings DIR --out target.json
      DIR holds, per candidate id taken in order, <id>.tags (ls-remote output), <id>.head (ls-remote --symref HEAD
      output), <id>.time (the listing's UTC time, ISO 8601), or <id>.unreachable (the reason) for a skipped one.
  python3 spec/M6/lib/I113_draw.py verify  --target spec/heldout3/target.json --salt spec/heldout3/salt.txt
                                           --commitment spec/heldout3/commitment.json
      recompute the seed, the order, the draw and both hashes; exit 0 iff all agree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = HERE / "I113_candidates.json"
K = 2
RELEASE = re.compile(r"^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HASH = re.compile(r"^0x[0-9a-f]{64}$")


class DrawError(ValueError):
    pass


def salt_bytes(text: str) -> bytes:
    s = text.strip()
    if not HEX64.match(s):
        raise DrawError("salt must be 64 lowercase hex characters")
    return bytes.fromhex(s)


def hash_bytes(blockhash: str) -> bytes:
    if not HASH.match(blockhash):
        raise DrawError("blockhash must be 0x and 64 lowercase hex characters")
    return bytes.fromhex(blockhash[2:])


def salt_sha256(salt: bytes) -> str:
    return hashlib.sha256(salt).hexdigest()


def seed(salt: bytes, blockhash: str) -> str:
    if len(salt) != 32:
        raise DrawError("salt must be 32 bytes")
    return hashlib.sha256(salt + hash_bytes(blockhash)).hexdigest()


def load_candidates(path: Path = CANDIDATES) -> list[dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    cands = doc["candidates"]
    ids = [c["id"] for c in cands]
    if len(set(ids)) != len(ids):
        raise DrawError("duplicate candidate id")
    return cands


def order(seed_hex: str, cands: list[dict]) -> list[dict]:
    sb = bytes.fromhex(seed_hex)
    keyed = [(hashlib.sha256(sb + c["id"].encode("utf-8")).hexdigest(), c["id"], c) for c in cands]
    keyed.sort(key=lambda t: (t[0], t[1]))
    return [dict(c, draw_key=k) for k, _, c in keyed]


def parse_listing(text: str) -> list[tuple[str, str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise DrawError(f"bad ls-remote line: {line!r}")
        rows.append((parts[0].strip(), parts[1].strip()))
    return rows


def pin(tags_text: str, head_text: str | None) -> dict:
    refs = {}
    for obj, ref in parse_listing(tags_text):
        if not obj.startswith("ref:"):
            refs[ref] = obj
    best = None
    for ref, obj in refs.items():
        if not ref.startswith("refs/tags/") or ref.endswith("^{}"):
            continue
        name = ref[len("refs/tags/"):]
        m = RELEASE.match(name)
        if not m:
            continue
        ver = tuple(int(x) for x in m.groups())
        cand = (ver, ref)
        if best is None or ver > best[0] or (ver == best[0] and ref < best[1]):
            best = cand
    if best is not None:
        ref = best[1]
        commit = refs.get(ref + "^{}", refs[ref])
        return {"kind": "tag", "ref": ref, "tag": ref[len("refs/tags/"):], "commit": commit}
    if head_text is None:
        raise DrawError("no release tag and no HEAD listing")
    branch, commit = None, None
    for obj, ref in parse_listing(head_text):
        if ref != "HEAD":
            continue
        if obj.startswith("ref: "):
            branch = obj[len("ref: "):]
        else:
            commit = obj
    if not branch or not commit:
        raise DrawError("HEAD listing lacks the symref or its commit")
    return {"kind": "branch", "ref": branch, "branch": branch[len("refs/heads/"):], "commit": commit}


def canonical(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")


def seal(salt: bytes, block: dict, listings: Path, cands: list[dict]) -> dict:
    s = seed(salt, block["hash"])
    targets, skipped = [], []
    for c in order(s, cands):
        if len(targets) == K:
            break
        cid = c["id"]
        un = listings / f"{cid}.unreachable"
        if un.exists():
            skipped.append({"id": cid, "reason": un.read_text(encoding="utf-8").strip()})
            continue
        tags = (listings / f"{cid}.tags").read_text(encoding="utf-8")
        headp = listings / f"{cid}.head"
        head = headp.read_text(encoding="utf-8") if headp.exists() else None
        targets.append({
            "id": cid,
            "name": c["name"],
            "repo": c["repo"],
            "draw_key": c["draw_key"],
            "pin": pin(tags, head),
            "listed_at_utc": (listings / f"{cid}.time").read_text(encoding="utf-8").strip(),
        })
    if len(targets) != K:
        raise DrawError("fewer than 2 resolvable candidates")
    return {
        "schema": "holon-heldout3-target/0.1",
        "iteration": "I113",
        "beacon": block,
        "seed": {"rule": "sha256(salt bytes || blockhash bytes)", "seed": s, "salt_sha256": salt_sha256(salt)},
        "draw": {"k": K, "order": [c["id"] for c in order(s, cands)], "skipped": skipped},
        "targets": targets,
    }


def verify(target_path: Path, salt_path: Path, commitment_path: Path, cands: list[dict]) -> list[str]:
    probs = []
    raw = Path(target_path).read_bytes()
    doc = json.loads(raw)
    com = json.loads(Path(commitment_path).read_text(encoding="utf-8"))
    salt_text = Path(salt_path).read_text(encoding="ascii")
    if salt_text != salt_text.strip() + "\n":
        probs.append("salt.txt is not 64 hex characters and one newline")
    salt = salt_bytes(salt_text)
    if canonical(doc) != raw:
        probs.append("target.json is not canonical")
    if hashlib.sha256(raw).hexdigest() != com["target_sha256"]:
        probs.append("sha256(target.json) differs from the commitment")
    if salt_sha256(salt) != com["salt_sha256"]:
        probs.append("sha256(salt) differs from the commitment")
    for k in ("number", "hash"):
        if doc["beacon"][k] != com["beacon"][k]:
            probs.append(f"beacon {k} differs between target.json and the commitment")
    s = seed(salt, doc["beacon"]["hash"])
    if doc["seed"]["seed"] != s:
        probs.append("seed differs from sha256(salt || blockhash)")
    o = order(s, cands)
    if doc["draw"]["order"] != [c["id"] for c in o]:
        probs.append("order differs from the recomputed order")
    skipped = {x["id"] for x in doc["draw"]["skipped"]}
    expect = [c["id"] for c in o if c["id"] not in skipped][:K]
    if [t["id"] for t in doc["targets"]] != expect:
        probs.append("targets differ from the first 2 resolvable candidates of the order")
    by_id = {c["id"]: c for c in cands}
    for t in doc["targets"]:
        c = by_id.get(t["id"])
        if c is None or c["repo"] != t["repo"] or c["name"] != t["name"]:
            probs.append(f"target {t['id']} differs from its candidate entry")
    return probs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="I113_draw.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("order")
    o.add_argument("--salt-file", required=True)
    o.add_argument("--blockhash", required=True)
    p = sub.add_parser("pin")
    p.add_argument("--ls-remote", required=True)
    p.add_argument("--symref")
    s = sub.add_parser("seal")
    s.add_argument("--salt-file", required=True)
    s.add_argument("--block-number", type=int, required=True)
    s.add_argument("--blockhash", required=True)
    s.add_argument("--block-timestamp", type=int, required=True)
    s.add_argument("--beacon-source", required=True)
    s.add_argument("--listings", required=True)
    s.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--target", required=True)
    v.add_argument("--salt", required=True)
    v.add_argument("--commitment", required=True)
    a = ap.parse_args(argv)
    cands = load_candidates()
    if a.cmd == "order":
        salt = salt_bytes(Path(a.salt_file).read_text(encoding="ascii"))
        print(json.dumps([c["id"] for c in order(seed(salt, a.blockhash), cands)]))
    elif a.cmd == "pin":
        head = Path(a.symref).read_text(encoding="utf-8") if a.symref else None
        print(json.dumps(pin(Path(a.ls_remote).read_text(encoding="utf-8"), head), sort_keys=True))
    elif a.cmd == "seal":
        salt = salt_bytes(Path(a.salt_file).read_text(encoding="ascii"))
        block = {"number": a.block_number, "hash": a.blockhash, "timestamp": a.block_timestamp,
                 "source": a.beacon_source}
        raw = canonical(seal(salt, block, Path(a.listings), cands))
        Path(a.out).write_bytes(raw)
        print(hashlib.sha256(raw).hexdigest())
    else:
        probs = verify(Path(a.target), Path(a.salt), Path(a.commitment), cands)
        for x in probs:
            print("FAIL", x)
        print("VERIFY OK" if not probs else "VERIFY FAILED")
        return 1 if probs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
