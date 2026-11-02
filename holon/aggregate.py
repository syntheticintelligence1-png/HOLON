"""Per-key prereg sources and the aggregates generated from them (PV2A): `python -m holon aggregate --milestone M
[--milestone M ...] [--check | --split]`.

Two keys preregistered on parallel branches used to touch the same two files. Each key now has its own sources:

  spec/<M>/predictions/<key>.json    the key's value in the "iterations" object of spec/<M>/predictions.json
  spec/<M>/predictions/_index.json   {"milestone", "doc", "order"}: the aggregate's other two fields, and the order of the
                                     keys split from it at PV2A
  spec/<M>/amendments/<key>.jsonl    the lines of spec/<M>/amendments.jsonl whose "iteration" is the key, verbatim and in
                                     their order there
  spec/<M>/amendments/_index.json    {"order"}: the "iteration" of every line split from it at PV2A, in its order

and this module writes the aggregates from them, which the prereg audit (holon.audit.prereg) and every test read as
before:

  spec/<M>/predictions.json   {"milestone", "doc", "iterations"}: the keys of _index's order first, then every other key
                              in natural order (I2 < I10 < I10b); indent 2, UTF-8, a final newline
  spec/<M>/amendments.jsonl   one line per _index entry (that key's next line), then every other line, by key in natural
                              order and each key's in file order

so both are byte-identical to the files as they were before PV2A for the keys and lines they held then, and a later
key's prereg commit (C_K) adds its own source files and regenerates the aggregate in the same commit (the prereg audit
counts spec/<M>/predictions/ and spec/<M>/amendments/ as prereg inputs). No later key needs to touch an _index file.

  --check   exit 1, naming each problem, unless every aggregate is what the sources give
  --split   first absorb what an aggregate holds and no source does (a key, or a line, that a branch older than PV2A
            wrote into the aggregate itself), then write; a key whose source and aggregate values differ is a conflict,
            and nothing is written

regenerate(milestone, root) is the same as --split, for a tool that lands a branch (the lead's `holon land`); check()
returns the problems. Deterministic: sorted iteration, no timestamps. No generator closure imports this module.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = "_index.json"
KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
FIELDS = ("milestone", "doc", "iterations")   # the aggregate's top-level keys, in their order


class AggregateError(ValueError):
    """Sources that give no aggregate, or an aggregate that conflicts with its sources (nothing is written)."""


def natural(k: str) -> list:
    """holon.audit.prereg's key order."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", k)]


def paths(milestone: str, root: Path) -> dict:
    base = Path(root) / "spec" / milestone
    return {"predictions": base / "predictions.json", "pdir": base / "predictions",
            "amendments": base / "amendments.jsonl", "adir": base / "amendments"}


def dump(obj) -> str:
    """The aggregate's form (and each key source's): indent 2, non-ASCII kept, a final newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _key(k, where: str) -> str:
    if not isinstance(k, str) or not KEY.match(k):
        raise AggregateError(f"{where}: {k!r} is not a key a file can be named after ({KEY.pattern})")
    return k


def _lines(text: str, where: str) -> list[tuple[str, str]]:
    """(iteration, line) for every non-empty line of an amendments text, the line verbatim."""
    out = []
    for i, ln in enumerate(text.split("\n"), 1):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except ValueError as e:
            raise AggregateError(f"{where} line {i} is not JSON: {e}") from None
        if not isinstance(obj, dict):
            raise AggregateError(f"{where} line {i} is not a JSON object")
        out.append((_key(obj.get("iteration"), f"{where} line {i}"), ln))
    return out


def read_sources(milestone: str, root: Path) -> dict:
    """{"index", "keys": {key: value}, "aindex", "lines": {key: [line]}}; an absent directory gives None there."""
    p = paths(milestone, root)
    out = {"index": None, "keys": None, "aindex": None, "lines": None}
    if p["pdir"].is_dir():
        ip = p["pdir"] / INDEX
        if not ip.is_file():
            raise AggregateError(f"{ip.relative_to(root)} is missing")
        out["index"] = json.loads(ip.read_text(encoding="utf-8"))
        out["keys"] = {_key(f.stem, str(f.relative_to(root))): json.loads(f.read_text(encoding="utf-8"))
                       for f in sorted(p["pdir"].glob("*.json")) if f.name != INDEX}
    if p["adir"].is_dir():
        ip = p["adir"] / INDEX
        if not ip.is_file():
            raise AggregateError(f"{ip.relative_to(root)} is missing")
        out["aindex"] = json.loads(ip.read_text(encoding="utf-8"))
        out["lines"] = {}
        for f in sorted(p["adir"].glob("*.jsonl")):
            k = _key(f.stem, str(f.relative_to(root)))
            got = _lines(f.read_text(encoding="utf-8"), str(f.relative_to(root)))
            bad = sorted({it for it, _ in got if it != k})
            if bad:
                raise AggregateError(f"{f.relative_to(root)} holds lines of {bad}: a key's file holds its own lines only")
            out["lines"][k] = [ln for _, ln in got]
    return out


def render(milestone: str, root: Path) -> dict[str, str]:
    """{repo path: text} of each aggregate whose sources exist."""
    root = Path(root)
    p, s = paths(milestone, root), read_sources(milestone, root)
    out = {}
    if s["keys"] is not None:
        ix = s["index"]
        order = [_key(k, INDEX) for k in ix.get("order") or []]
        if len(set(order)) != len(order):
            raise AggregateError(f"spec/{milestone}/predictions/{INDEX} lists a key twice")
        missing = [k for k in order if k not in s["keys"]]
        if missing:
            raise AggregateError(f"spec/{milestone}/predictions/{INDEX} orders keys without a source: {missing}")
        keys = order + sorted((k for k in s["keys"] if k not in set(order)), key=natural)
        doc = {"milestone": ix.get("milestone"), "doc": ix.get("doc"), "iterations": {k: s["keys"][k] for k in keys}}
        out[p["predictions"].relative_to(root).as_posix()] = dump(doc)
    if s["lines"] is not None:
        order = [_key(k, INDEX) for k in s["aindex"].get("order") or []]
        nxt = {k: 0 for k in s["lines"]}
        lines = []
        for k in order:
            if nxt.get(k, 0) >= len(s["lines"].get(k, [])):
                raise AggregateError(f"spec/{milestone}/amendments/{INDEX} orders more lines of {k} than its file holds")
            lines.append(s["lines"][k][nxt[k]])
            nxt[k] += 1
        for k in sorted(s["lines"], key=natural):
            lines += s["lines"][k][nxt[k]:]
        out[p["amendments"].relative_to(root).as_posix()] = "".join(ln + "\n" for ln in lines)
    return out


def check(milestone: str, root: Path = ROOT) -> list[str]:
    """Every way the aggregates differ from what their sources give (an aggregate without sources is not checked)."""
    root = Path(root)
    try:
        want = render(milestone, root)
    except (AggregateError, OSError, ValueError) as e:
        return [f"spec/{milestone}: {e}"]
    probs = []
    for rel, text in sorted(want.items()):
        f = root / rel
        if not f.is_file():
            probs.append(f"{rel} is missing (python -m holon aggregate --milestone {milestone})")
        elif f.read_text(encoding="utf-8") != text:
            probs.append(f"{rel} is not what its per-key sources give (python -m holon aggregate --milestone "
                         f"{milestone} --split absorbs what only the aggregate holds, then writes it)")
    return probs


def write(milestone: str, root: Path = ROOT) -> list[str]:
    """Write each aggregate its sources give; the repo paths that changed."""
    root = Path(root)
    done = []
    for rel, text in sorted(render(milestone, root).items()):
        f = root / rel
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            f.write_text(text, encoding="utf-8")
            done.append(rel)
    return done


def split(milestone: str, root: Path = ROOT) -> list[str]:
    """Absorb into the sources what an aggregate holds and no source does; the repo paths written. With no source
    directory yet (the split at PV2A), every key and line, and the _index files that keep the aggregates' order."""
    root = Path(root)
    p, s = paths(milestone, root), read_sources(milestone, root)
    done = []

    def put(f: Path, text: str):
        if not f.is_file() or f.read_text(encoding="utf-8") != text:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
            done.append(f.relative_to(root).as_posix())
    if p["predictions"].is_file():
        doc = json.loads(p["predictions"].read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or tuple(doc) != FIELDS or not isinstance(doc.get("iterations"), dict):
            raise AggregateError(f"spec/{milestone}/predictions.json is not {{{', '.join(FIELDS)}}}: no per-key form")
        its = doc["iterations"]
        for k in its:
            _key(k, f"spec/{milestone}/predictions.json")
        if s["keys"] is None:
            ix = {"milestone": doc["milestone"], "doc": doc["doc"], "order": list(its)}
            s["keys"] = {}
        else:
            ix = s["index"]
            if (ix.get("milestone"), ix.get("doc")) != (doc["milestone"], doc["doc"]):
                raise AggregateError(f"spec/{milestone}/predictions.json's milestone or doc is not {INDEX}'s: a conflict")
        bad = sorted((k for k in its if k in s["keys"] and s["keys"][k] != its[k]), key=natural)
        if bad:
            raise AggregateError(f"spec/{milestone}: the aggregate and the sources give {bad} different values: a "
                                 "conflict (a prereg key is never edited; holon audit prereg tells which is the "
                                 "committed one)")
        put(p["pdir"] / INDEX, dump(ix))
        for k in its:
            if k not in s["keys"]:
                put(p["pdir"] / f"{k}.json", dump(its[k]))
    if p["amendments"].is_file():
        got = _lines(p["amendments"].read_text(encoding="utf-8"), f"spec/{milestone}/amendments.jsonl")
        if s["lines"] is None:
            put(p["adir"] / INDEX, dump({"order": [k for k, _ in got]}))
            s["lines"] = {}
        else:
            put(p["adir"] / INDEX, dump(s["aindex"]))
        add: dict[str, list[str]] = {}
        have = {k: list(v) for k, v in s["lines"].items()}
        for k, ln in got:   # a line the key's file does not hold (as many times as the aggregate does)
            if ln in have.get(k, []):
                have[k].remove(ln)
            else:
                add.setdefault(k, []).append(ln)
        for k in sorted(add, key=natural):
            put(p["adir"] / f"{k}.jsonl", "".join(ln + "\n" for ln in s["lines"].get(k, []) + add[k]))
    return done


def regenerate(milestone: str, root: Path = ROOT) -> list[str]:
    """split, then write: what a landing tool runs after merging (the repo paths written)."""
    return split(milestone, root) + write(milestone, root)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon aggregate")
    ap.add_argument("--milestone", action="append", required=True)
    ap.add_argument("--root", default=str(ROOT))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--split", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    bad = 0
    for m in a.milestone:
        if a.check:
            probs = check(m, root)
            for x in probs:
                print(f"aggregate: {x}")
            bad += len(probs)
            if not probs:
                print(f"aggregate: spec/{m}: AGGREGATES OK")
            continue
        try:
            done = regenerate(m, root) if a.split else write(m, root)
        except (AggregateError, OSError, ValueError) as e:
            print(f"aggregate: spec/{m}: refused, nothing written: {e}", file=sys.stderr)
            return 1
        print(f"aggregate: spec/{m}: {len(done)} file(s) written" + "".join(f"\n  {x}" for x in done))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
