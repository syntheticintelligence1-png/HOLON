"""I96b's instrument (the contract is the docstring of tests_m3/test_hints_i96b.py). It imports nothing from holon/ or
tools/; it reuses I96a's instrument for the target-agnostic words and runs git only as a subprocess.

    REFINEMENT        the two derived files, results/M3/sorts/refinement/{hints,keys}.json.
    refinement_rows(blind_root, lead_root) -> [{"file", "blind", "lead", "equal", "diff"}]: the sha256 of each file on
        both sides (None when absent) and, when they differ, json_diff of the two documents.
    json_diff(a, b, limit) -> [{"path", "blind", "lead"}]: the first `limit` paths (sorted) where two JSON documents
        differ, leaves shortened to 80 characters; a list compares element by element, then by length.
    record_words(root) -> (words, law_ids): I95's H1 words of every JSON file under results/ (hex strings: 32-byte
        chunks, selectors and shorter ones; integers), counted from 4 significant bytes (8 hex digits, no leading
        zeros), and every law id (L_...) the files name.
    leak_hits(text, words, law_ids, checkout, commit) -> {"hits", "code", "law_ids"}: the words that occur in a text,
        as hex among its hex characters or as decimal, split by whether the target's code at the commit holds them
        (git grep in the checkout); and the law ids it names.
    moves(i95_breakdown, blind_statuses, lead_statuses) -> {law: {"i95_blind", "lead", "blind"}} for I95's 28
        disagreements.
    pack_commit(root, lead_ref) -> the oldest first-parent commit of lead_ref whose tree holds holon/refinement.py.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from tests_m3 import _i96a as A  # noqa: F401  (B1: identifiers and literals)

ROOT = Path(__file__).resolve().parents[1]
OUT = "audit/blind/I96"
PROTOCOL = "spec/M3/lib/blind_rerun_i96.json"
REFINEMENT = ("results/M3/sorts/refinement/hints.json", "results/M3/sorts/refinement/keys.json")
MARKER = "holon/refinement.py"


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def json_diff(a, b, limit: int = 20, path: str = "") -> list[dict]:
    out: list[dict] = []

    def short(x):
        s = json.dumps(x, sort_keys=True)
        return s if len(s) <= 80 else s[:77] + "..."

    def walk(x, y, p):
        if len(out) >= limit:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x or k not in y:
                    out.append({"path": f"{p}/{k}", "blind": short(x.get(k)), "lead": short(y.get(k))})
                elif x[k] != y[k]:
                    walk(x[k], y[k], f"{p}/{k}")
        elif isinstance(x, list) and isinstance(y, list):
            for i, (u, v) in enumerate(zip(x, y)):
                if u != v:
                    walk(u, v, f"{p}[{i}]")
            if len(x) != len(y):
                out.append({"path": f"{p}#length", "blind": len(x), "lead": len(y)})
        elif x != y:
            out.append({"path": p or "/", "blind": short(x), "lead": short(y)})

    walk(a, b, path)
    return out[:limit]


def refinement_rows(blind_root, lead_root) -> list[dict]:
    rows = []
    for rel in REFINEMENT:
        b, l_ = Path(blind_root) / rel, Path(lead_root) / rel
        sb, sl = _sha(b), _sha(l_)
        row = {"file": rel, "blind": sb, "lead": sl, "equal": sb is not None and sb == sl, "diff": []}
        if sb and sl and sb != sl:
            row["diff"] = json_diff(json.loads(b.read_text(encoding="utf-8")), json.loads(l_.read_text(encoding="utf-8")))
        rows.append(row)
    return rows


def _words(x, out: set, ids: set) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            _words(k, out, ids)
            _words(v, out, ids)
    elif isinstance(x, list):
        for v in x:
            _words(v, out, ids)
    elif isinstance(x, bool) or x is None:
        return
    elif isinstance(x, int):
        if x >= 1 << 28:
            out.add(format(x, "x"))
    elif isinstance(x, str):
        if re.fullmatch(r"0x[0-9a-fA-F]+", x):
            h = x[2:].lower()
            if len(h) > 64:
                sel = (len(h) - 8) % 64 == 0
                body = h[8:] if sel else h
                for i in range(0, len(body), 64):
                    out.add(body[i:i + 64].lstrip("0"))
                if sel:
                    out.add(h[:8].lstrip("0"))
            else:
                out.add(h.lstrip("0"))
        ids.update(re.findall(r"\bL_[A-Za-z0-9_]+", x))


def record_words(root=ROOT) -> tuple[set, set]:
    words, ids = set(), set()
    for p in sorted((Path(root) / "results").rglob("*.json")):
        try:
            _words(json.loads(p.read_text(encoding="utf-8")), words, ids)
        except (ValueError, UnicodeDecodeError):
            continue
    return {w for w in words if len(w) >= 8}, ids


def leak_hits(text: str, words: set, law_ids: set, checkout, commit: str) -> dict:
    low = text.lower()
    hexchars = re.sub(r"[^0-9a-f]", "", low)
    hits, code = [], []
    for w in sorted(words):
        if w in hexchars or str(int(w, 16)) in low:
            g = subprocess.run(["git", "-C", str(checkout), "grep", "-q", "-i", "-E", f"0*{w}|{int(w, 16)}", commit, "--"],
                               capture_output=True)
            (code if g.returncode == 0 else hits).append(w)
    return {"hits": hits, "code": code, "law_ids": sorted(i for i in law_ids if i.lower() in low)}


def moves(i95_breakdown: dict, blind: dict, lead: dict) -> dict:
    return {x["law_id"]: {"i95_blind": x["blind"], "lead": lead.get(x["law_id"]), "blind": blind.get(x["law_id"])}
            for x in i95_breakdown["disagreements"]}


def pack_commit(root, lead_ref: str) -> str | None:
    revs = subprocess.run(["git", "-C", str(root), "rev-list", "--first-parent", "--reverse", lead_ref],
                          capture_output=True, text=True, check=True).stdout.split()
    for c in revs:
        if subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{c}:{MARKER}"], capture_output=True).returncode == 0:
            return c
    return None
