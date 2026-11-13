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
  python tools/i121_redecide.py reset-slot --slot DIR --archive-dir A [--label L]
      archive every changed, added or deleted path of a sandbox slot (git status against its HEAD) to
      A/<label>-<n>.tgz with its status listing, and only then reset the slot to HEAD (F-M6-13: a started job's
      partial output is never deleted, Q80); refuses to reset when the archive cannot be written
  python tools/i121_redecide.py summary --vault V --out results/M6/I121/redecide.json
  python tools/i121_redecide.py planted --vault V   (the planted flip, before summary)
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


# ---------------------------------------------------------------------------------------------------------- reset-slot
def archive_then_reset(slot: Path, archive_dir: Path, label: str) -> Path | None:
    """F-M6-13 (I121): a slot's working state is archived before it is reset. Returns the archive written (None when
    the slot was clean). Raises when the archive cannot be written or read back; then nothing is reset."""
    import tarfile
    slot, archive_dir = Path(slot).resolve(), Path(archive_dir).resolve()
    st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=slot, capture_output=True,
                        text=True, check=True).stdout
    out = None
    if st.strip():
        archive_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        while (archive_dir / f"{label}-{n}.tgz").exists():
            n += 1
        out = archive_dir / f"{label}-{n}.tgz"
        (archive_dir / f"{label}-{n}.status.txt").write_text(st)
        with tarfile.open(out, "w:gz") as tf:
            for ln in st.splitlines():
                rel = ln[3:].split(" -> ")[-1]
                if (slot / rel).exists():
                    tf.add(slot / rel, arcname=rel)
        with tarfile.open(out) as tf:   # read back before anything is deleted
            tf.getnames()
    subprocess.run(["git", "reset", "-q", "--hard", "HEAD"], cwd=slot, check=True)
    subprocess.run(["git", "clean", "-qfd"], cwd=slot, check=True)
    return out


PLANTED = ("tests_m6/fixtures/i121/planted_flip_before.facts.json", "tests_m6/fixtures/i121/planted_flip_after.facts.json")


def cmd_planted(a) -> int:
    """The re-decision's planted flip (I121-P2, HUMAN_ANSWERS Q96 (1)): a synthetic law (I24's round-trip fixture, its
    encoder storing b as zero, then the same fixture with the defect removed) whose committed status differs from the
    checker's on the new inputs. In a scratch worktree of HEAD, test milestone T121: derive and run on the old facts (the
    committed record, committed_before); put the new facts at the same path, derive, and re-make into the same results
    directory (committed_after, as the channel writes it); and decide afresh into a separate directory (checker). The
    vault's summary_inputs.json gains planted.flip, with no law id."""
    import shutil
    import tempfile
    v = Path(a.vault).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="i121-planted-"))
    wt = tmp / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(wt), "HEAD"], cwd=ROOT, check=True)
    try:
        for rel in PLANTED:   # the fixtures as on disk (they may be new in the working tree)
            shutil.copy(ROOT / rel, wt / rel)
        rel = "tests_m6/fixtures/i121/planted_flip.facts.json"

        def holon(*args):
            p = subprocess.run([sys.executable, "-m", "holon", *args], cwd=wt, capture_output=True, text=True,
                               timeout=3600)
            if p.returncode != 0:
                raise SystemExit(f"i121_redecide planted: holon {args[0]} failed: {(p.stdout + p.stderr)[-1500:]}")

        def derive(src: str, tag: str) -> dict:
            shutil.copy(wt / src, wt / rel)
            holon("sorts", "--facts", rel, "--out", str(tmp / f"sorts_{tag}"))
            shutil.rmtree(wt / "laws" / "T121", ignore_errors=True)
            holon("derive", "--milestone", "T121", "--facts", rel, "--assignment",
                  str(tmp / f"sorts_{tag}" / "assignment.json"), "--out", str(wt / "laws" / "T121"),
                  "--obstructions", str(tmp / f"obs_{tag}.json"))
            return {p.stem: json.loads(p.read_text()) for p in sorted((wt / "laws" / "T121").glob("L*.json"))}

        def run(out: str) -> dict:
            holon("run", "--milestone", "T121", "--no-registry", "--out", str(tmp / out), "--gen-dir",
                  str(tmp / f"gen_{out}"))
            return {p.stem: json.loads(p.read_text())["status"] for p in sorted((tmp / out).glob("L*.json"))}

        old = derive(PLANTED[0], "before")
        before = run("committed")
        new = derive(PLANTED[1], "after")
        after = run("committed")        # the re-make writes over the committed record
        checker = run("fresh")          # decided afresh on the new inputs, in its own directory
        flips = sorted(k for k in new if k in old and before.get(k) != checker.get(k))
        if len(flips) != 1:
            print(f"i121_redecide planted: expected exactly one planted flip, got {len(flips)}", file=sys.stderr)
            return 2
        k = flips[0]
        changed = sorted(x for x in set(old[k]) | set(new[k]) if old[k].get(x) != new[k].get(x))
        flip = {"fixture": list(PLANTED), "milestone": "T121", "committed_before": before[k], "checker": checker[k],
                "committed_after": after[k], "law_keys_changed": changed}
        p = v / "summary_inputs.json"
        s = json.loads(p.read_text())
        s["planted"] = {"flip": flip}
        p.write_text(json.dumps(s, indent=1, sort_keys=True))
        print(f"i121_redecide planted: committed {before[k]} -> re-made {after[k]}, checker {checker[k]} "
              f"(law keys changed: {changed})")
        return 0
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def cmd_reset_slot(a) -> int:
    out = archive_then_reset(Path(a.slot), Path(a.archive_dir), a.label)
    print(f"i121_redecide reset-slot: {a.slot}: " + (f"archived to {out}, then reset" if out else "clean, reset"))
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
    sp = sub.add_parser("reset-slot")
    sp.add_argument("--slot", required=True)
    sp.add_argument("--archive-dir", required=True)
    sp.add_argument("--label", default="slot")
    sp = sub.add_parser("planted")
    sp.add_argument("--vault", required=True)
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
    return {"models": cmd_models, "affected": cmd_affected, "compare": cmd_compare, "summary": cmd_summary,
            "reset-slot": cmd_reset_slot, "planted": cmd_planted}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
