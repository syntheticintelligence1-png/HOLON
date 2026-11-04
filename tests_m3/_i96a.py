"""I96a's instrument (the contract is the docstring of tests_m3/test_r0_i96a.py). It imports nothing from holon/ or
tools/, and runs `python -m holon` only as a subprocess.

    field_diff(authored, derived) -> [{"field", "path", "authored", "derived"}]: every values or keys path whose
        entries differ, then proxy_slots when the sorted lists differ. An absent entry is None.
    r0_sha(r0) -> the sha256 of r0's canonical form: values, keys, proxy_slots and derived_from, with sorted keys and
        no spaces.
    r0_row(blind_sidecar, lead_sidecar) -> {"blind", "lead", "equal", "model_sidecar": {"blind", "lead", "equal"}}:
        the scorer row of the derived inputs.
    analysis_diff(blind_closure, blind_conjuncts, lead_closure, lead_conjuncts) -> {part: [models]}: the models
        whose closure.json part (r0, classes, permission, dead, closure) or conjuncts.json part (kinds, checks, basis)
        differs. The part "models" lists the models present on one side only.
    moved(laws) -> [law ids]: the laws of {law: {"before", "after"}} whose status changed.
    identifiers(root, base) -> set: the names in <base>'s DISCH documents of at least 4 characters: contract,
        storage declarations and their members, and actions.
    literals(root, base) -> set: <base>'s deployment records' non-zero slots, words, target and the halves of their
        64-byte preimages, as lowercase hex without leading zeros and as decimal, of at least 6 characters.
    step_properties(root) -> dict: B2 on a copy of the tree. Two runs are byte-identical, and no other member
        changes. It also records --check's exit after one byte of r0 changes, and without the deployment records.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests_m3._i46 import STATUS_WORDS  # noqa: F401  (B4)

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M3/lib/disch.json"
OUT = "audit/i96a"
R0_FIELDS = ("values", "keys", "proxy_slots", "derived_from")
CLOSURE_PARTS = ("r0", "classes", "permission", "dead", "closure")
CONJUNCT_PARTS = ("kinds", "checks", "basis")
SKIP = {".git", "cache", "build", "node_modules", "gen", "results"}


def _fields(r0: dict | None) -> dict:
    r0 = r0 or {}
    return {"values": r0.get("values") or {}, "keys": r0.get("keys") or {},
            "proxy_slots": sorted(r0.get("proxy_slots") or [])}


def field_diff(authored: dict | None, derived: dict | None) -> list[dict]:
    a, d = _fields(authored), _fields(derived)
    out = []
    for field in ("values", "keys"):
        for p in sorted(set(a[field]) | set(d[field])):
            if a[field].get(p) != d[field].get(p):
                out.append({"field": field, "path": p, "authored": a[field].get(p), "derived": d[field].get(p)})
    if a["proxy_slots"] != d["proxy_slots"]:
        out.append({"field": "proxy_slots", "path": "", "authored": a["proxy_slots"], "derived": d["proxy_slots"]})
    return out


def r0_sha(r0: dict | None) -> str:
    canon = {k: (r0 or {}).get(k) for k in R0_FIELDS}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def r0_row(blind: dict, lead: dict) -> dict:
    b, l_ = r0_sha(blind.get("r0")), r0_sha(lead.get("r0"))
    mb, ml = blind.get("model_sidecar"), lead.get("model_sidecar")
    return {"blind": b, "lead": l_, "equal": b == l_, "model_sidecar": {"blind": mb, "lead": ml, "equal": mb == ml}}


def analysis_diff(blind_closure: dict, blind_conjuncts: dict, lead_closure: dict, lead_conjuncts: dict) -> dict:
    out: dict = {}
    for b, l_, parts in ((blind_closure, lead_closure, CLOSURE_PARTS), (blind_conjuncts, lead_conjuncts,
                                                                        CONJUNCT_PARTS)):
        bm, lm = b.get("models") or {}, l_.get("models") or {}
        one = sorted(set(bm) ^ set(lm))
        if one:
            out["models"] = sorted(set(out.get("models", [])) | set(one))
        for m in sorted(set(bm) & set(lm)):
            for part in parts:
                if bm[m].get(part) != lm[m].get(part):
                    out.setdefault(part, []).append(m)
    return out


def moved(laws: dict) -> list[str]:
    return sorted(l_ for l_, v in laws.items() if v.get("before") != v.get("after"))


def _git_json(root, commit: str, rel: str):
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{rel}"], capture_output=True, check=True)
    return json.loads(r.stdout)


def sidecar_at(root, commit: str) -> dict:
    return _git_json(root, commit, SIDECAR)


def _documents(root, base: str) -> list[tuple[str, dict]]:
    return [(d, _git_json(root, base, d)) for d in sidecar_at(root, base)["documents"]]


def identifiers(root, base: str) -> set:
    out: set = set()
    for _rel, doc in _documents(root, base):
        out.add(str(doc.get("contract") or ""))
        for d in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
            out.add(d["name"])
            out.update(f["name"] for f in d.get("fields") or [])
        out.update(str(a.get("name") or "") for a in doc.get("actions") or [])
    return {w for w in out if len(w) >= 4 and w != "__gap"}


def literals(root, base: str) -> set:
    out: set = set()
    for rel, _doc in _documents(root, base):
        stem = Path(rel).name[:-len(".json")]
        dep = _git_json(root, base, f"gen/M3/binding/{stem}.json")["deployment"]
        words = [int(w, 16) for w in list(dep["storage"]) + list(dep["storage"].values()) + [dep["target"]]]
        words += [int(p[2:][i:i + 64], 16) for p in dep["preimages"] if len(p) == 130 for i in (0, 64)]
        for n in words:
            if n:
                out.update({format(n, "x"), str(n)})
    return {x for x in out if len(x) >= 6}


def _run(root: Path, *args) -> int:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", "disch-r0", "--milestone", "M3", *args], cwd=root, env=env,
                          capture_output=True, text=True, timeout=900).returncode


def step_properties(root=ROOT) -> dict:
    root = Path(root)
    with tempfile.TemporaryDirectory() as tmp:
        w = Path(tmp) / "w"
        shutil.copytree(root, w, ignore=lambda d, names: [n for n in names if Path(d) == root and n in SKIP])
        shutil.copytree(root / "gen" / "M3" / "binding", w / "gen" / "M3" / "binding")
        sc = w / SIDECAR
        before = json.loads(sc.read_text(encoding="utf-8"))
        _run(w)
        one = sc.read_bytes()
        _run(w)
        two = sc.read_bytes()
        after = json.loads(two)
        others = all(before.get(k) == after.get(k) for k in set(before) | set(after) if k not in ("r0", "model_sidecar"))
        text = two.decode("utf-8")
        i = text.index('"values"', text.index('\n  "r0": {'))
        j = next(k for k in range(i, len(text)) if text[k].isdigit())
        sc.write_text(text[:j] + str((int(text[j]) + 1) % 10) + text[j + 1:], encoding="utf-8")
        changed = _run(w, "--check")
        sc.write_bytes(two)
        shutil.rmtree(w / "gen" / "M3" / "binding")
        missing = _run(w, "--check")
        return {"byte_identical": one == two, "other_members_unchanged": others,
                "check_after_byte_change": changed, "check_without_record": missing}
