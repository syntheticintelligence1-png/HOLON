"""python -m holon eval verify [--root DIR] [--cache DIR] (rule C3; I48): re-derive every candidate's git facts and the
index snapshots from holon's own partial clones and check them against spec/eval/candidates.json.

- Every git index record's snapshot is its pin (reachable from the pinned branch; the geth list's file with the
  pinned sha256); a mechanical index's items are holon eval index's at the pin, a folder's items its reports there.
- A mechanical candidate that was opened has its item's verbatim description and, when its item names a reachable
  commit of the system's repositories, that named fix as repo and fix commit.
- A candidate whose fix commit is given in one of its system's repositories: reachable from a branch or tag (else
  reason commit_not_found and no facts), with the file's prefix_commit, fix_date, files, source_lines and
  frontend_lines, and reason not_in_frontend_reach exactly when the reach fails. A system candidate without a fix
  commit is commit_not_found. An other_repo candidate's given fix commit is reachable in its GitHub repository.
  excluded_repo and other_repo candidates carry no other git facts.
Exit 0 when everything agrees, 1 naming each mismatch.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import common, gitfacts
from . import index as ix

FACT_KEYS = ("prefix_commit", "fix_date", "files", "source_lines", "frontend_lines")
NO_FACTS = {"prefix_commit": None, "fix_date": None, "files": [], "source_lines": None, "frontend_lines": None}


def check_indexes(doc: dict, proto: dict) -> list[str]:
    out = []
    recs = {(r["system"], r["index"]): r for r in doc.get("indexes", [])}
    for s in proto["systems"]:
        derived = None
        for x in s["indexes"]:
            r = recs.get((s["id"], x["id"]))
            if r is None:
                out.append(f"{x['id']}: no index record")
                continue
            kind = x["enumeration"]
            if kind == "page":
                continue
            pin = proto["snapshots"]["pins"][x["snapshot"]]
            if r["snapshot"] != ix.git_snapshot(pin):
                out.append(f"{x['id']}: the snapshot is not the pin")
            if kind in ("ghsa", "geth"):
                derived = derived or ix.system_index(s["id"], proto)
                mine = next(y for y in derived["indexes"] if y["index"] == x["id"])
                if r["items"] != mine["items"]:
                    out.append(f"{x['id']}: the items are not the index's at the pin")
            elif kind == "folder":
                want = [y["item"] for y in ix.folder_listing(pin)]
                if sorted(it["item"] for it in r["items"]) != want:
                    out.append(f"{x['id']}: the items are not the folder's reports at the pin")
                if any(it["published"] > pin["committer_date"][:10] for it in r["items"]):
                    out.append(f"{x['id']}: an item is dated after the pin")
    return out


def check_candidates(doc: dict, proto: dict) -> list[str]:
    out = []
    systems = {s["id"]: s for s in proto["systems"]}
    kinds = {x["id"]: x["enumeration"] for s in proto["systems"] for x in s["indexes"]}
    opened: dict = {}
    for c in doc.get("candidates", []):
        cid, sysd, reason = c["id"], systems.get(c["system"]), c["reason"]
        if sysd is None:
            out.append(f"{cid}: system {c['system']!r} is not the protocol's")
            continue
        facts = {k: c.get(k) for k in FACT_KEYS}
        if kinds.get(c["index"]) in ("ghsa", "geth"):
            if c["system"] not in opened:
                opened[c["system"]] = {(y["index"], o["item"]): o for y in ix.system_index(c["system"], proto)["indexes"]
                                       for o in y.get("opened", [])}
            o = opened[c["system"]].get((c["index"], c["item"]))
            if o is not None:
                d = c.get("description")
                if d is not None and not (d == ix.collapse(d) and 0 < len(d) <= 2000 and d in o["text"]):
                    out.append(f"{cid}: the description is not a verbatim excerpt of its item")
                nf = o["named_fix"]
                if nf is not None and (c["repo"], c["fix_commit"]) != (nf["repo"], nf["commit"]):
                    out.append(f"{cid}: the fix commit is not its item's named fix")
        if reason in ("excluded_repo", "other_repo"):
            if facts != NO_FACTS:
                out.append(f"{cid}: carries git facts, but its reason is {reason}")
            if reason == "other_repo":
                if c["repo"] in sysd["repos"] or common.excluded(c["repo"]):
                    out.append(f"{cid}: other_repo, but its repository is the system's or excluded")
                elif c["fix_commit"] is not None and not gitfacts.commit_facts(c["repo"], c["fix_commit"])["found"]:
                    out.append(f"{cid}: {c['repo']}@{c['fix_commit']} is not reachable from a branch or tag")
            continue
        if c["repo"] not in sysd["repos"]:
            out.append(f"{cid}: repository {c['repo']!r} is not one of {c['system']}'s")
            continue
        if c["fix_commit"] is None:
            if reason != "commit_not_found":
                out.append(f"{cid}: no fix commit, but reason {reason!r}")
            continue
        info = gitfacts.commit_facts(c["repo"], c["fix_commit"])
        if not info["found"]:
            if reason != "commit_not_found":
                out.append(f"{cid}: {c['fix_commit']} is not reachable from a branch or tag, but reason {reason!r}")
            if facts != NO_FACTS:
                out.append(f"{cid}: an unreachable fix commit with git facts")
            continue
        if reason == "commit_not_found":
            out.append(f"{cid}: commit_not_found, but {c['fix_commit']} is reachable")
        for k in FACT_KEYS:
            if facts[k] != info[k]:
                out.append(f"{cid}: {k} differs from git")
        if (reason == "not_in_frontend_reach") != (not info["reach"]):
            out.append(f"{cid}: reason {reason!r}, but the frontend reach is {info['reach']}")
    return out


def cli_verify(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval verify")
    ap.add_argument("--root", default=str(common.ROOT))
    ap.add_argument("--cache")
    a = ap.parse_args(argv)
    if a.cache:
        common.REPOS = Path(a.cache).resolve()
    path = Path(a.root) / "spec" / "eval" / "candidates.json"
    if not path.exists():
        raise common.Refused(f"{path} is missing")
    doc, proto = common.load_json(path), common.protocol()
    problems = []
    if doc.get("protocol_sha256") != common.sha256_file(common.LIB / "corpus_protocol.json"):
        problems.append("protocol_sha256 is not the protocol's")
    problems += check_indexes(doc, proto) + check_candidates(doc, proto)
    for p in problems:
        print(f"holon eval verify: {p}", file=sys.stderr)
    n = sum(1 for c in doc.get("candidates", []) if c.get("fix_commit"))
    print(f"holon eval verify: {len(problems)} mismatches over {len(doc.get('candidates', []))} candidates "
          f"({n} with a fix commit)", file=sys.stderr)
    return 1 if problems else 0
