"""I121 (M6): the re-decision instrument (spec/M6/predictions/I121.json; HUMAN_ANSWERS Q96, Q97 (2)).

It runs in the builder's sandbox only: a git worktree of the branch outside the repository (--wt), never a CI re-make.
Every per-law output (law ids, statuses, the re-decided records) goes to the vault (--vault, outside the repository);
the repository gets aggregates only (results/M6/I121/redecide.json, written by `summary`).

  python tools/i121_redecide.py models  --wt WT --milestone M3
      write gen/<M>/model/<stem>.bend for every linked codec, Go-op and Go count document of the milestone, as
      holon.codecrun.Models writes them during `holon run` (the generators' text, nothing else), so that `holon land
      regen`'s lossy step reads current models
  python tools/i121_redecide.py affected --wt WT --base REV --vault V --milestone M3
      the affected set on WT against the committed records at REV: the laws whose law file, decision inputs or
      trace changed, by case ((a) unchanged law file, (b) facts_sha256 only, (c) id renumbered), written to the vault
  python tools/i121_redecide.py compare --wt WT --base REV --vault V --milestone M3
      after the re-make: each affected law's re-decided status on WT against its committed status at REV, in the vault
  python tools/i121_redecide.py summary --vault V --out results/M6/I121/redecide.json
      the aggregates: per milestone and channel counts, verdicts changed (PROVED and REFUTED together), and one sha256
      bundle commitment of the vault's re-decided set (I107's canonical form)

Nothing here reads a sealed input or names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-i121-redecide/0.1"
MILESTONES = ("M0", "M1", "M2", "M3")


def dumps(x) -> str:
    return json.dumps(x, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def git(wt: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=wt, capture_output=True, text=True, check=True).stdout


def blob(wt: Path, rev: str, rel: str) -> bytes | None:
    p = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=wt, capture_output=True)
    return p.stdout if p.returncode == 0 else None


def jload(b: bytes | None):
    try:
        return json.loads(b) if b is not None else None
    except ValueError:
        return None


# ---------------------------------------------------------------------------------------------------------- models
def cmd_models(a) -> int:
    wt = Path(a.wt).resolve()
    sys.path.insert(0, str(wt))
    from holon.diagram import goops as GO
    from holon.diagram import gocount as GC
    from holon.gen import gocount as GN
    from holon.gen import goloop as GG
    from holon.gen import linked as GL
    m = a.milestone
    gen = wt / "gen" / m
    n = 0
    for p in sorted((gen / "codec").glob("*.json")) + sorted((gen / "goops").glob("*.json")):
        raw = p.read_bytes()
        doc = json.loads(raw)
        sha = hashlib.sha256(raw).hexdigest()
        if isinstance(doc.get("linked_version"), str):
            stem, text = doc["role"], GL.generate(doc, sha)
        elif GO.is_goops(doc):
            stem, text = doc["component"], GG.generate(doc, sha)
        elif doc.get("gocount_version") == GC.GOCOUNT_VERSION:
            stem, text = doc["component"], GN.generate(doc, sha)
        else:
            continue
        out = gen / "model" / f"{stem}.bend"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.is_file() or out.read_text(encoding="utf-8") != text:
            out.write_text(text)
            n += 1
    print(f"i121_redecide models: {m}: {n} model file(s) rewritten")
    return 0


# ---------------------------------------------------------------------------------------------------------- affected
def law_files(wt: Path, rev: str | None, m: str) -> dict[str, dict]:
    out = {}
    if rev is None:
        for p in sorted((wt / "laws" / m).glob("L_*.json")):
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        return out
    for rel in git(wt, "ls-tree", "--name-only", f"{rev}:laws/{m}").split():
        if rel.startswith("L_") and rel.endswith(".json"):
            out[rel[:-5]] = jload(blob(wt, rev, f"laws/{m}/{rel}"))
    return out


def status_of(rec) -> str | None:
    return rec.get("status") if isinstance(rec, dict) else None


def cmd_affected(a) -> int:
    """The affected set: every law of the milestone at base whose law file differs on the tree, or which a re-made
    input reads (holon land dirty on the tree, minus the laws whose only dirty reason is config/holon.json, F-M6-03,
    a known state that re-makes nothing), and every law new on the tree. Written to the vault."""
    wt, v, m = Path(a.wt).resolve(), Path(a.vault).resolve(), a.milestone
    v.mkdir(parents=True, exist_ok=True)
    old, new = law_files(wt, a.base, m), law_files(wt, None, m)
    rows = {}
    for lid in sorted(set(old) | set(new)):
        o, n = old.get(lid), new.get(lid)
        if o is None:
            rows[lid] = {"case": "c_new"}
        elif n is None:
            rows[lid] = {"case": "c_retired"}
        elif o != n:
            keys = sorted(k for k in set(o) | set(n) if o.get(k) != n.get(k))
            rows[lid] = {"case": "b_facts" if keys == ["facts_sha256"] else "statement", "keys": keys}
    p = subprocess.run([sys.executable, "-m", "holon", "land", "dirty", "--milestone", m], cwd=wt, capture_output=True,
                       text=True)
    (v / f"dirty_{m}.txt").write_text(p.stdout + p.stderr)
    for ln in p.stdout.splitlines():
        s = ln.strip()
        if not s.startswith("L_") or ":" not in s:
            continue
        lid, why = s.split(":", 1)
        reads = [x for x in why.split(";") if "changed" in x]
        only_cfg = all("config/holon.json" in x for x in reads) and reads
        if lid not in rows and not only_cfg and lid in old:
            rows[lid] = {"case": "a_inputs", "why": why.strip()[:500]}
        elif lid in rows:
            rows[lid]["dirty"] = why.strip()[:500]
    for lid, r in rows.items():
        rec = jload(blob(wt, a.base, f"results/{m}/{lid}.json"))
        r["committed_status"] = status_of(rec)
    (v / f"affected_{m}.json").write_text(dumps(rows))
    by: dict = {}
    for r in rows.values():
        by[r["case"]] = by.get(r["case"], 0) + 1
    print(f"i121_redecide affected: {m}: {len(rows)} laws ({', '.join(f'{k} {c}' for k, c in sorted(by.items()))})")
    return 0


# ---------------------------------------------------------------------------------------------------------- compare
def cmd_compare(a) -> int:
    wt, v, m = Path(a.wt).resolve(), Path(a.vault).resolve(), a.milestone
    rows = json.loads((v / f"affected_{m}.json").read_text(encoding="utf-8"))
    for lid, r in rows.items():
        p = wt / "results" / m / f"{lid}.json"
        rec = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
        r["redecided_status"] = status_of(rec)
        if isinstance(rec, dict):
            law = wt / "laws" / m / f"{lid}.json"
            r["record_facts_sha256_is_laws"] = (law.is_file() and rec.get("facts_sha256") ==
                                                json.loads(law.read_text(encoding="utf-8")).get("facts_sha256"))
        r["changed"] = (r["case"] not in ("c_new", "c_retired") and r.get("committed_status") is not None
                        and r["redecided_status"] != r["committed_status"])
    (v / f"compare_{m}.json").write_text(dumps(rows))
    n = sum(1 for r in rows.values() if r["changed"])
    print(f"i121_redecide compare: {m}: {len(rows)} laws, {n} verdicts changed (PROVED and REFUTED together)")
    return 0


# ---------------------------------------------------------------------------------------------------------- summary
def bundle_sha(files: list[Path], base: Path) -> str:
    """I107's canonical bundle form: sorted paths, one '<sha256>  <path>' line per file, then the sha256 of that."""
    lines = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(base).as_posix()}\n"
                    for p in sorted(files, key=lambda q: q.relative_to(base).as_posix()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def cmd_summary(a) -> int:
    v = Path(a.vault).resolve()
    s = json.loads((v / "summary_inputs.json").read_text(encoding="utf-8"))
    files = [p for p in sorted((v / "bundle").rglob("*")) if p.is_file()]
    out = {"redecide_version": VERSION, **s, "bundle_sha256": bundle_sha(files, v / "bundle"),
           "bundle_files": len(files)}
    text = dumps(out)
    import re
    if re.search(r"\bL_[A-Za-z0-9_]+", text):
        print("i121_redecide summary: refused: a law id would be committed", file=sys.stderr)
        return 2
    Path(a.out).write_text(text)
    print(f"i121_redecide summary: {a.out} (bundle {out['bundle_sha256'][:12]}.., {len(files)} files)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="i121_redecide")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("models", "affected", "compare", "summary"):
        sp = sub.add_parser(name)
        if name != "summary":
            sp.add_argument("--wt", required=True)
            sp.add_argument("--milestone", required=True)
        if name in ("affected", "compare", "summary"):
            sp.add_argument("--vault", required=True)
        if name in ("affected", "compare"):
            sp.add_argument("--base", default="HEAD")
        if name == "summary":
            sp.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"models": cmd_models, "affected": cmd_affected, "compare": cmd_compare, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
