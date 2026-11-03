"""python -m holon eval select [--root DIR] [--check] (I48 rule C4): the round-robin selection.

The selection is a function of spec/eval/candidates.json alone (with the frozen protocol's systems, n and
max_per_system):
  - each system's eligible candidates are queued newest fix first (fix_date descending; ties by fix_commit, then id);
  - rounds visit the systems in the protocol's order; in a round every system holding fewer than max_per_system
    entries includes the head of its queue, until n entries are included or no system can include one;
  - included candidates get entry ids c01, c02, ... in inclusion order and reason null; an eligible candidate left out
    gets reason cap_reached when its system holds max_per_system entries, else past_n; an ineligible candidate keeps
    its own reason and entry null.

It writes the selection (entry, reason) into spec/eval/candidates.json and the included candidates, in inclusion order,
into spec/eval/corpus.json's entries: the candidate's system, repo, title, description, sources, fix_commit,
prefix_commit, fix_date and files, the system's kind and the languages of the files (sorted). corpus.json names the
sha256 of the protocol, the rule sheet and the candidates.json just written. Labels (rules C5-C6) are holon eval
agree's: an existing corpus.json's labels, label, agreement and labellers are kept when the selection is unchanged,
and a run that would change a labelled selection is refused (a selection is never re-run after labelling).

--check writes nothing and exits 1 when candidates.json or the selection's part of corpus.json differs from a fresh
selection.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import common
from .common import Refused, dumps, sha256_bytes, sha256_file

CANDIDATES = Path("spec") / "eval" / "candidates.json"
CORPUS = Path("spec") / "eval" / "corpus.json"
CORPUS_VERSION = "holon-eval-corpus/0.1"
ENTRY_FIELDS = ("system", "repo", "title", "description", "sources", "fix_commit", "prefix_commit", "fix_date",
                "files")
LABEL_FIELDS = ("labels", "label")
CORPUS_LABEL_KEYS = ("agreement", "labellers")


def _queue(cands: list[dict]) -> list[dict]:
    """Newest fix first; ties by fix_commit, then id (two stable sorts)."""
    q = sorted(cands, key=lambda c: (c["fix_commit"], c["id"]))
    return sorted(q, key=lambda c: c["fix_date"], reverse=True)


def selection(cands: list[dict], proto: dict) -> dict[str, tuple[str | None, str | None]]:
    """candidate id -> (entry id or None, reason)."""
    order = [s["id"] for s in proto["systems"]]
    outside = sorted({c["system"] for c in cands if c["eligible"]} - set(order))
    if outside:
        raise Refused(f"eligible candidates of systems outside the protocol: {outside}")
    queues = {s: _queue([c for c in cands if c["eligible"] and c["system"] == s]) for s in order}
    taken = {s: 0 for s in order}
    out: dict[str, tuple[str | None, str | None]] = {}
    count = 0
    while count < proto["n"]:
        took = False
        for s in order:
            if count >= proto["n"]:
                break
            if queues[s] and taken[s] < proto["max_per_system"]:
                c = queues[s].pop(0)
                count += 1
                taken[s] += 1
                out[c["id"]] = (f"c{count:02d}", None)
                took = True
        if not took:
            break
    for s in order:
        for c in queues[s]:
            out[c["id"]] = (None, "cap_reached" if taken[s] >= proto["max_per_system"] else "past_n")
    for c in cands:
        if not c["eligible"]:
            out[c["id"]] = (None, c["reason"])
    return out


def _language(path: str, proto: dict) -> str:
    for lang, exts in sorted(proto["frontend_extensions"].items()):
        if any(path.endswith(e) for e in exts):
            return lang
    raise Refused(f"{path}: no frontend language")


def build(cdoc: dict, proto: dict) -> tuple[dict, list[dict]]:
    """(the candidates document with the selection, the corpus entries without labels)."""
    ids = [c["id"] for c in cdoc["candidates"]]
    if len(set(ids)) != len(ids):
        raise Refused("candidates.json holds a candidate id twice")
    sel = selection(cdoc["candidates"], proto)
    kinds = {s["id"]: s["kind"] for s in proto["systems"]}
    new = dict(cdoc, candidates=[])
    entries = []
    for c in cdoc["candidates"]:
        entry, reason = sel[c["id"]]
        new["candidates"].append(dict(c, entry=entry, reason=reason))
        if entry:
            e = {"id": entry, "candidate": c["id"], "kind": kinds[c["system"]],
                 "languages": sorted({_language(f, proto) for f in c["files"]})}
            e.update({k: c[k] for k in ENTRY_FIELDS})
            entries.append(e)
    entries.sort(key=lambda e: e["id"])
    return new, entries


def _selection_view(corpus: dict) -> dict:
    """The part of corpus.json the selection owns."""
    return {k: v for k, v in corpus.items() if k not in CORPUS_LABEL_KEYS} | \
        {"entries": [{k: v for k, v in e.items() if k not in LABEL_FIELDS} for e in corpus.get("entries", [])]}


def cli_select(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval select")
    ap.add_argument("--root", type=Path, default=common.ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if not (root / CANDIDATES).exists():
        raise Refused(f"{CANDIDATES} is missing under {root}")
    proto = common.protocol()
    cdoc = common.load_json(root / CANDIDATES)
    new_c, entries = build(cdoc, proto)
    from holon.schema import errors
    errs = errors(new_c, common.load_json(common.LIB / "candidates.schema.json"))
    if errs:
        print("candidates.json with the selection does not validate: " + "; ".join(errs[:20]), file=sys.stderr)
        return 1
    c_text = dumps(new_c)
    corpus = {"corpus_version": CORPUS_VERSION, "protocol_sha256": sha256_file(common.LIB / "corpus_protocol.json"),
              "rule_sheet_sha256": sha256_file(common.LIB / "rule_sheet.json"),
              "candidates_sha256": sha256_bytes(c_text.encode("utf-8")), "entries": entries}
    old = common.load_json(root / CORPUS) if (root / CORPUS).exists() else None
    if a.check:
        differs = []
        if (root / CANDIDATES).read_bytes() != c_text.encode("utf-8"):
            differs.append(CANDIDATES.as_posix())
        if old is None or _selection_view(old) != _selection_view(corpus):
            differs.append(CORPUS.as_posix())
        for p in differs:
            print(f"differs from a fresh selection: {p}", file=sys.stderr)
        return 1 if differs else 0
    if old is not None:
        labelled = any(k in old for k in CORPUS_LABEL_KEYS) or \
            any(k in e for e in old.get("entries", []) for k in LABEL_FIELDS)
        same = [(e["id"], e["candidate"]) for e in old.get("entries", [])] == \
            [(e["id"], e["candidate"]) for e in entries]
        if labelled and not same:
            raise Refused("corpus.json is labelled and this selection differs from it: a selection is never re-run "
                          "after labelling")
        if labelled:
            olds = {e["id"]: e for e in old["entries"]}
            for e in entries:
                e.update({k: olds[e["id"]][k] for k in LABEL_FIELDS if k in olds[e["id"]]})
            corpus.update({k: old[k] for k in CORPUS_LABEL_KEYS if k in old})
    for p, text in ((CANDIDATES, c_text), (CORPUS, dumps(corpus))):
        if common.write_or_check(root / p, text, False):
            print(f"wrote: {p.as_posix()}")
    print(f"selected {len(entries)} entries from {len({e['system'] for e in entries})} systems")
    return 0
