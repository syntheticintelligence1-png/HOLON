"""python -m holon eval candidates --from DIR [--check] [--root ROOT] (rule C2; I48): assemble spec/eval/candidates.json
from the collectors' files.

DIR holds one file per system, DIR/<system>.json:
  {"system", "collector", "stopped": "eighth_eligible" | "exhausted",
   "indexes": [{"index", "snapshot", "items", "examined"}, ...],          (candidates.schema.json $defs index, no system)
   "candidates": [{"index", "item", "published", "title", "description", "sources", "repo", "fix_commit",
                   "excluded_by", "reason", "exclusion_note", "duplicate_of"}, ...]}   (examination order)
duplicate_of names a candidate of the same system as "<system>:<NNN>", its 1-based position in that system's list.

The assembly gives every candidate its id and rank, derives the git facts (holon.eval.gitfacts) of every candidate
whose reason is not excluded_repo or other_repo and whose fix commit is given, and recomputes the mechanical criteria
in the protocol's order (excluded repository, other repository, commit found, frontend reach): a collector's reason
that disagrees with them is an error naming the candidate (exit 1, nothing written). The judged reasons
(no_public_writeup, not_functional, duplicate) are the collector's. A mechanical index's item list must be the one
holon eval index derives at the pin, and a mechanical candidate's fix commit and description its item's. entry is null
(the selection, holon eval select, fills it). The document is validated against candidates.schema.json before it is
written. --check writes nothing and passes when the file is the fresh assembly, or the fresh assembly with holon eval
select's selection applied.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import common, gitfacts
from . import index as ix

VERSION = "holon-eval-candidates/0.1"
MECHANICAL = ("excluded_repo", "other_repo", "commit_not_found", "not_in_frontend_reach")
JUDGED = ("no_public_writeup", "not_functional", "duplicate")
INPUT_KEYS = ("index", "item", "published", "title", "description", "sources", "repo", "fix_commit", "excluded_by",
              "reason", "exclusion_note", "duplicate_of")


class Problems(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def schema_errors(doc: dict, schema_path: Path) -> list[str]:
    """holon.schema's validator, plus the two keywords it does not read that candidates.schema.json uses (minimum on
    the integers, maxLength on the description)."""
    from holon import schema as hs
    errs = list(hs.errors(doc, common.load_json(schema_path)))
    for r in doc.get("indexes", []):
        if isinstance(r.get("examined"), int) and r["examined"] < 0:
            errs.append(f"{r.get('index')}: examined below 0")
        for it in r.get("items", []):
            if isinstance(it.get("findings"), int) and it["findings"] < 0:
                errs.append(f"{it.get('item')}: findings below 0")
    for s in doc.get("systems", []):
        if isinstance(s.get("examined"), int) and s["examined"] < 0:
            errs.append(f"{s.get('id')}: examined below 0")
    for c in doc.get("candidates", []):
        if isinstance(c.get("rank"), int) and c["rank"] < 1:
            errs.append(f"{c.get('id')}: rank below 1")
        for k in ("source_lines", "frontend_lines"):
            if isinstance(c.get(k), int) and c[k] < 0:
                errs.append(f"{c.get('id')}: {k} below 0")
        if isinstance(c.get("description"), str) and len(c["description"]) > 2000:
            errs.append(f"{c.get('id')}: description longer than 2000 characters")
    return errs


def _texts(c: dict) -> list[str]:
    return [t for t in (c.get("title"), c.get("description")) if isinstance(t, str)]


def mechanical_reason(c: dict, system: dict, item_rec: dict | None, mech: bool, proto: dict,
                      facts_of) -> tuple[str | None, dict | None]:
    """The first failing mechanical criterion of a candidate (or None) and, when its fix commit was looked up in the
    system's repository, the git facts."""
    if mech and item_rec is not None and item_rec.get("excluded_by") is not None:
        return "excluded_repo", None
    locs = [u for u in (c.get("repo"), c.get("item")) if isinstance(u, str)]
    if ix.first_pattern(locs, proto) is not None or ix.first_subject(_texts(c), proto) is not None:
        return "excluded_repo", None
    if c.get("repo") not in system["repos"]:
        return "other_repo", None
    if c.get("fix_commit") is None:
        return "commit_not_found", None
    facts = facts_of(c["repo"], c["fix_commit"])
    if not facts["found"]:
        return "commit_not_found", facts
    if not facts["reach"]:
        return "not_in_frontend_reach", facts
    return None, facts


def assemble(src: Path, proto: dict | None = None, facts_of=None, index_of=None) -> dict:
    """The candidates document from the collector files under src (raises Problems naming every disagreement)."""
    proto = proto or common.protocol()
    facts_of = facts_of or gitfacts.commit_facts
    index_of = index_of or ix.system_index
    problems: list[str] = []
    collectors, systems, indexes, cands = [], [], [], []
    for system in proto["systems"]:
        sid = system["id"]
        path = Path(src) / f"{sid}.json"
        if not path.exists():
            raise common.Refused(f"{path} is missing (one collector file per system)")
        f = common.load_json(path)
        if f.get("system") != sid:
            problems.append(f"{path}: system is {f.get('system')!r}, not {sid!r}")
        collectors.append({"system": sid, "agent": f.get("collector"), "family": "same"})
        kinds = {x["id"]: x["enumeration"] for x in system["indexes"]}
        recs = {r.get("index"): r for r in f.get("indexes", [])}
        if [r.get("index") for r in f.get("indexes", [])] != [x["id"] for x in system["indexes"]]:
            problems.append(f"{sid}: the index records are not the protocol's indexes in order")
        mech_index = None
        for x in system["indexes"]:
            r = recs.get(x["id"], {})
            indexes.append({"system": sid, "index": x["id"], "snapshot": r.get("snapshot"),
                            "items": r.get("items", []), "examined": r.get("examined", 0)})
            if kinds[x["id"]] in ("ghsa", "geth"):
                mech_index = mech_index or index_of(sid, proto)
                derived = next(y for y in mech_index["indexes"] if y["index"] == x["id"])
                if r.get("items") != derived["items"]:
                    problems.append(f"{x['id']}: the item list is not holon eval index's at the pin")
                if r.get("snapshot") != derived["snapshot"]:
                    problems.append(f"{x['id']}: the snapshot is not the pin")
            elif kinds[x["id"]] == "folder":
                pin = proto["snapshots"]["pins"][x["snapshot"]]
                if r.get("snapshot") != ix.git_snapshot(pin):
                    problems.append(f"{x['id']}: the snapshot is not the pin")
        opened = {}
        if mech_index is not None:
            for y in mech_index["indexes"]:
                for o in y.get("opened", []):
                    opened[(y["index"], o["item"])] = o
        mine = f.get("candidates", [])
        ids = {f"{sid}:{k:03d}" for k in range(1, len(mine) + 1)}
        eligible = 0
        for rank, c in enumerate(mine, 1):
            cid = f"{sid}:{rank:03d}"
            missing = [k for k in INPUT_KEYS if k not in c]
            if missing:
                problems.append(f"{cid}: missing {', '.join(missing)}")
                continue
            kind = kinds.get(c["index"])
            if kind is None:
                problems.append(f"{cid}: index {c['index']!r} is not one of {sid}'s")
                continue
            r = recs.get(c["index"], {})
            items = r.get("items", [])
            urls = [it.get("item") for it in items]
            item_rec = items[urls.index(c["item"])] if c["item"] in urls else None
            if item_rec is None or urls.index(c["item"]) >= r.get("examined", 0):
                problems.append(f"{cid}: {c['item']} is not an examined item of {c['index']}")
            elif c["published"] != item_rec.get("published"):
                problems.append(f"{cid}: published is not its item's")
            mech = kind in ("ghsa", "geth")
            want, facts = mechanical_reason(c, system, item_rec, mech, proto, facts_of)
            got = c["reason"]
            if want is not None and got != want:
                problems.append(f"{cid}: reason {got!r}, but the mechanical criteria give {want!r}")
            if want is None and got is not None and got not in JUDGED:
                problems.append(f"{cid}: reason {got!r}, but every mechanical criterion holds")
            if got == "excluded_repo":
                if not c["excluded_by"]:
                    problems.append(f"{cid}: excluded_repo without excluded_by")
                if c["fix_commit"] is not None:
                    problems.append(f"{cid}: excluded_repo with a fix commit")
            elif c["excluded_by"] is not None:
                problems.append(f"{cid}: excluded_by on a {got!r} candidate")
            if got == "other_repo" and c["fix_commit"] is not None and not facts_of(c["repo"], c["fix_commit"])["found"]:
                problems.append(f"{cid}: {c['repo']}@{c['fix_commit']} is not reachable from a branch or tag")
            if got == "duplicate" and c["duplicate_of"] not in ids:
                problems.append(f"{cid}: duplicate_of {c['duplicate_of']!r} is not a candidate of {sid}")
            if got != "duplicate" and c["duplicate_of"] is not None:
                problems.append(f"{cid}: duplicate_of on a {got!r} candidate")
            if mech and want != "excluded_repo":
                o = opened.get((c["index"], c["item"]))
                if o is None:
                    problems.append(f"{cid}: {c['item']} is not an opened item of {c['index']}")
                else:
                    if o["named_fix"] is not None and (c["repo"], c["fix_commit"]) != \
                            (o["named_fix"]["repo"], o["named_fix"]["commit"]):
                        problems.append(f"{cid}: the fix commit is not the earliest reachable commit its item names")
                    if c["title"] != item_rec["title"]:
                        problems.append(f"{cid}: the title is not its item's")
                    d = c["description"]
                    if not (isinstance(d, str) and d == ix.collapse(d) and 0 < len(d) <= 2000 and d in o["text"]):
                        problems.append(f"{cid}: the description is not a verbatim excerpt of its item")
            given = facts if (facts and facts.get("found") and got not in ("excluded_repo", "other_repo")) else None
            out = {k: c[k] for k in INPUT_KEYS}
            out.update(id=cid, system=sid, rank=rank, entry=None, eligible=got is None,
                       prefix_commit=given["prefix_commit"] if given else None,
                       fix_date=given["fix_date"] if given else None,
                       files=given["files"] if given else [],
                       source_lines=given["source_lines"] if given else None,
                       frontend_lines=given["frontend_lines"] if given else None)
            eligible += got is None
            cands.append(out)
        stopped = f.get("stopped")
        if eligible > proto["max_per_system"]:
            problems.append(f"{sid}: {eligible} eligible candidates, above max_per_system")
        if stopped == "eighth_eligible" and not (eligible == proto["max_per_system"] and mine
                                                 and mine[-1].get("reason") is None):
            problems.append(f"{sid}: stopped at the 8th eligible, but the last candidate is not the 8th eligible")
        if stopped == "exhausted" and eligible >= proto["max_per_system"]:
            problems.append(f"{sid}: exhausted with {eligible} eligible candidates (the stop rule was missed)")
        systems.append({"id": sid, "examined": len(mine), "stopped": stopped})
    doc = {"candidates_version": VERSION, "protocol_sha256": common.sha256_file(common.LIB / "corpus_protocol.json"),
           "collectors": collectors, "systems": systems, "indexes": indexes, "candidates": cands}
    problems += schema_errors(doc, common.LIB / "candidates.schema.json")
    if problems:
        raise Problems(problems)
    return doc


def cli_candidates(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval candidates")
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--root", default=str(common.ROOT))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.src)
    if not src.is_dir():
        raise common.Refused(f"{src} is not a directory")
    try:
        doc = assemble(src)
    except Problems as e:
        for p in e.problems:
            print(f"holon eval candidates: {p}", file=sys.stderr)
        return 1
    target = Path(a.root) / "spec" / "eval" / "candidates.json"
    differs = common.write_or_check(target, common.dumps(doc), a.check)
    if a.check and differs:
        # After holon eval select the file holds the selection (entry, and reason past_n or cap_reached for the
        # eligible candidates left out): compare with the fresh assembly with select's own selection applied.
        from .select import build
        selected, _ = build(doc, common.protocol())
        differs = common.write_or_check(target, common.dumps(selected), True)
    if a.check and differs:
        print(f"holon eval candidates: {target} differs from a fresh assembly", file=sys.stderr)
        return 1
    counts = ", ".join(f"{s['id']} {s['examined']}" for s in doc["systems"])
    print(f"holon eval candidates: {'checked' if a.check else 'wrote'} {target} ({counts} candidates)",
          file=sys.stderr)
    return 0
