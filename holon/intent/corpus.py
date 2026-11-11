"""I55's lane on the corpus (key I55b design C0-C5): L10's corpus_recall.

  python -m holon intent corpus [--root DIR] [--check]          results/M5/intent/corpus/atoms.json, compile.json
  python -m holon intent corpus-score [--root DIR] [--check]    results/M5/intent/corpus/l10_corpus.json

The run stage reads the key I55b (its scored entries), spec/eval/corpus.json, spec/M5/lib/intent_corpus_sources.json
and the checkouts it names, and runs I55's atomizer and compiler, unchanged, on each scored entry's files at its
prefix_commit. It never reads spec/M5/truth/. Only the score stage reads the truth file, at the sha256 the key pins.
A corpus law compiles into laws/INTENT/corpus/, never into I55's set; it is an obstruction only once decided and
reviewed (I55 design V); an unreviewed law produces no finding.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .atomize import atoms_of
from .common import ROOT, dumps, git, sha256_file, write_or_check

KEY = "I55b"
OUT = "results/M5/intent/corpus"
SOURCES = "spec/M5/lib/intent_corpus_sources.json"
CORPUS = "spec/eval/corpus.json"
TRUTH = "spec/M5/truth/corpus.json"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def key(root: Path) -> dict:
    return _load(root / "spec" / "M5" / "predictions" / f"{KEY}.json")["thresholds"]


def run_files(root: Path, write: bool) -> tuple[dict, list]:
    from .compile import Compiler, _Fail
    th = key(root)
    src = _load(root / SOURCES)
    corpus = {e["id"]: e for e in _load(root / CORPUS)["entries"]}
    entries, compile_entries = {}, []
    comp = Compiler(root, write=False, srcmap=src)
    for eid in th["scored"]:
        e = corpus[eid]
        co = Path(src[e["repo"]])
        atoms = []
        for f in sorted(e["files"]):
            text = git(["show", f"{e['prefix_commit']}:{f}"], co).decode("utf-8")
            atoms += atoms_of(e["repo"], e["prefix_commit"], f, text)
        atoms.sort(key=lambda a: (a["file"], a["lines"], a["id"]))
        entries[eid] = {"repo": e["repo"], "prefix_commit": e["prefix_commit"], "files": sorted(e["files"]),
                        "atoms": atoms}
        for a in atoms:
            try:
                tname, got = comp.compile(a)
            except _Fail as x:
                tname, got = None, x
            if isinstance(got, _Fail):
                compile_entries.append({"atom": a["id"], "control": None, "template": tname, "outcome": got.outcome,
                                        "law_id": None, "detail": got.detail})
            else:
                compile_entries.append({"atom": a["id"], "control": None, "template": tname, "outcome": "compiled",
                                        "law_id": got["law_id"], "detail": f"{got['contract']}: {', '.join(got['actions'])}"})
                # a compiled corpus law is recorded, not decided here: it needs the runner and a review (design C3)
    files = {root / OUT / "atoms.json": dumps({"entries": entries}),
             root / OUT / "compile.json": dumps({"compiler": "holon.intent.compile", "entries": compile_entries})}
    return files, comp.problems


def score(root: Path) -> dict:
    th = key(root)
    tp = root / TRUTH
    if sha256_file(tp) != th["truth_sha256"]:
        raise RuntimeError(f"{TRUTH} is not at the sha256 the key pins")
    from ..m5.common import proportion, size_label
    truth = _load(tp)["entries"]
    atoms = _load(root / OUT / "atoms.json")["entries"]
    comp = _load(root / OUT / "compile.json")["entries"]
    recdir = root / OUT / "records"
    recs = [_load(p) for p in sorted(recdir.glob("L_intent_*.json"))] if recdir.is_dir() else []
    out = {}
    for eid in th["scored"]:
        ids = {a["id"] for a in atoms[eid]["atoms"]}
        compiled = sorted(e["law_id"] for e in comp if e["atom"] in ids and e["outcome"] == "compiled")
        obs = sorted(r["law_id"] for r in recs if set(r["clauses"]) & ids and r["obstruction"])
        out[eid] = {"l10": truth[eid]["l10"], "atoms": len(ids), "compiled": compiled, "obstructions": obs}
    yes = [e for e in th["scored"] if out[e]["l10"] == "yes"]
    hit = [e for e in yes if out[e]["obstructions"]]
    return {"truth_sha256": th["truth_sha256"], "corpus_sha256": sha256_file(root / CORPUS), "entries": out,
            "corpus_recall": proportion(len(hit), len(yes)), "label": size_label(len(yes))}


def _main(argv, which) -> int:
    ap = argparse.ArgumentParser(prog=f"holon intent {which}")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = a.root.resolve()
    if which == "corpus":
        files, probs = run_files(root, write=not a.check)
    else:
        files, probs = {root / OUT / "l10_corpus.json": dumps(score(root))}, []
    got = probs + write_or_check(files, a.check)
    if a.check:
        for g in got:
            print(f"intent {which}: differs: {g}")
        print(f"intent {which}: {'CHECK OK' if not got else 'CHECK FAILED'}")
        return 1 if got else 0
    print(f"intent {which}: {len(got)} file(s) written")
    return 0


def main(argv: list[str]) -> int:
    return _main(argv, "corpus")


def main_score(argv: list[str]) -> int:
    return _main(argv, "corpus-score")
