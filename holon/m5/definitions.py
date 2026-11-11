"""spec/M5/preregistration.json (I54): the L6, L9 and L10 definitions as I55-I58 read them.

  python -m holon m5 prereg [--root DIR] [--check]

renders {"key": "I54", "definitions": the key's thresholds.definitions, "base": {"commit", "l6_findings",
"l9_dependent"}, "instruments": {path: sha256}} from spec/M5/predictions/I54.json. The base populations are read
from the key's base commit through git, so a later change of results/ never moves them:
- l6_findings is F(M3): the M3 records with status REFUTED and a filter_bin outside model_defect, known_limitation and
  intended_bounded;
- l9_dependent is every M2 and M3 record with an environment premise under spec/M5/lib/environment_classes.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .common import ROOT, dumps, git_blobs, git_list, sha256_bytes

KEY = "I54"
NOT_FINDINGS = ("model_defect", "known_limitation", "intended_bounded")


def key(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / "spec" / "M5" / "predictions" / f"{KEY}.json").read_text(encoding="utf-8"))


def base_commit(root: Path = ROOT) -> str:
    return key(root)["thresholds"]["base_commit"]


def classification(root: Path = ROOT) -> dict:
    return json.loads((Path(root) / "spec" / "M5" / "lib" / "environment_classes.json").read_text(encoding="utf-8"))


def records_at(root: Path, commit: str, milestones: tuple[str, ...]) -> list[dict]:
    paths = []
    for m in milestones:
        paths += [p for p in git_list(root, commit, f"results/{m}/") if re.fullmatch(rf"results/{m}/L_[^/]+\.json", p)]
    got = git_blobs(root, commit, sorted(paths))
    return [json.loads(got[p]) for p in sorted(got) if got[p] is not None]


def findings(records: list[dict]) -> list[str]:
    return sorted(r["law_id"] for r in records
                  if r.get("status") == "REFUTED" and r.get("filter_bin") not in NOT_FINDINGS)


def render(root: Path = ROOT) -> str:
    from .metrics import environment_premises
    root = Path(root)
    k = key(root)
    th = k["thresholds"]
    c = th["base_commit"]
    cls = classification(root)
    dependent = sorted(r["law_id"] for r in records_at(root, c, ("M2", "M3")) if environment_premises(r, cls))
    doc = {"key": KEY, "definitions": th["definitions"],
           "base": {"commit": c, "l6_findings": findings(records_at(root, c, ("M3",))), "l9_dependent": dependent},
           "instruments": {p: sha256_bytes((root / p).read_bytes()) for p in th["instruments"]}}
    return dumps(doc)


def path(root: Path = ROOT) -> Path:
    return Path(root) / "spec" / "M5" / "preregistration.json"


def load(root: Path = ROOT) -> dict:
    return json.loads(path(root).read_text(encoding="utf-8"))


def write(root: Path = ROOT, check: bool = False) -> list[str]:
    text, p = render(root), path(root)
    have = p.read_text(encoding="utf-8") if p.is_file() else None
    if check:
        return [] if have == text else [f"{p.relative_to(root)}: differs from the key (python -m holon m5 prereg)"]
    if have != text:
        p.write_text(text, encoding="utf-8")
        return [p.relative_to(root).as_posix()]
    return []
