"""I111: withhold the run's per-law outputs under gen/ (Q56, I104's rule), which holon_run.withhold does not cover.

    python tools/i111_withhold_gen.py --vault DIR [--out results/M6/I111/holon]

holon_run.withhold removes each entry's laws/ and records/ (kept in --vault) but not the per-law files `holon run`
writes under gen/<M>/ (gen/laws/<law id>/ and the DISCH section models that name law ids). This removes from the
committed output every file under <id>/gen/ whose path or text names a law id the entry derived (the ids are read from
the vault's <id>/laws/, never from the committed tree), keeps a copy in the vault, and writes <id>/gen_withheld.json:
{"files": n, "sha256": I107's canonical bundle hash over the removed files}. No path or id is written. In
<out>/corpus.json, every such law id inside a stage's detail text (the run stage's error output) is replaced by
"<law id withheld>"; nothing else in the file changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--out", default="results/M6/I111/holon")
    a = ap.parse_args()
    vault, out = Path(a.vault).resolve(), (ROOT / a.out).resolve()
    for e in sorted(p for p in vault.iterdir() if p.is_dir()):
        ids = sorted(p.stem for p in (e / "laws").glob("L*.json"))
        g = out / e.name / "gen"
        if not ids or not g.is_dir():
            continue
        gone = []
        for p in sorted(g.rglob("*")):
            if p.is_file():
                rel = p.relative_to(out / e.name).as_posix()
                text = p.read_text(encoding="utf-8", errors="ignore")
                if any(i in rel or i in text for i in ids):
                    gone.append((rel, hashlib.sha256(p.read_bytes()).hexdigest()))
        if not gone:
            continue
        for rel, _h in gone:
            dst = vault / e.name / "withheld_gen" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out / e.name / rel, dst)
            (out / e.name / rel).unlink()
        for d in sorted((p for p in g.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(d.iterdir()):
                d.rmdir()
        lines = "".join(f"{h}  {rel}\n" for rel, h in sorted(gone, key=lambda x: x[0].encode()))
        (out / e.name / "gen_withheld.json").write_text(json.dumps(
            {"files": len(gone), "sha256": hashlib.sha256(lines.encode()).hexdigest()}, indent=2, sort_keys=True) + "\n")
        print(f"{e.name}: {len(gone)} files withheld")
    cp = out / "corpus.json"
    if cp.is_file():
        doc = json.loads(cp.read_text(encoding="utf-8"))
        n = 0
        for row in doc["rows"]:
            e = vault / row["id"]
            ids = sorted((p.stem for p in (e / "laws").glob("L*.json")), key=lambda s: -len(s)) if e.is_dir() else []
            for st in (row.get("stages") or {}).values():
                d = st.get("detail") or ""
                for i in ids:
                    if i in d:
                        d = d.replace(i, "<law id withheld>")
                        n += 1
                st["detail"] = d if st.get("detail") is not None else None
        cp.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"corpus.json: {n} law ids redacted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
