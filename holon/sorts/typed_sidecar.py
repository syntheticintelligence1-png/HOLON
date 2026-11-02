"""The typed-sorts sidecar of a milestone (I30; the contract is the docstring of tests_m3/test_sort_types.py).

From M3 on (and for test milestones T<n> with n >= 30) the sorts pass, typing, derivation and the model read the
transitions documents the sidecar names (holon-sort-types/0.1: spec/<M>/lib/sort_types.json, or --sidecar for a test
milestone), its seeds file, its binding (the deployment whose storage is Reach's initial state; null: the zero
storage) and its search budget. No hand-written fact document is read for these milestones (docs/HUMAN_ANSWERS.md,
Q19).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

VERSION = "holon-sort-types/0.1"


class SidecarError(ValueError):
    pass


def typed(milestone: str | None) -> bool:
    """Is the milestone typed by I30's rules (M<k>, k >= 3; T<n>, n >= 30)?"""
    m = re.fullmatch(r"([MT])(\d+)", str(milestone or ""))
    if not m:
        return False
    k = int(m.group(2))
    return k >= 3 if m.group(1) == "M" else k >= 30


@dataclass
class Sidecar:
    path: Path
    rel: str
    doc: dict
    root: Path

    @property
    def documents(self) -> list[Path]:
        return [self.root / d for d in self.doc.get("documents") or []]

    @property
    def seeds(self) -> Path:
        return self.root / self.doc["seeds"]

    @property
    def binding(self) -> str | None:
        return self.doc.get("binding")

    @property
    def search(self) -> dict:
        return dict(self.doc.get("search") or {})

    def source(self, doc_rel: str) -> str | None:
        """The source tree a planted document's extraction names (repo-relative), or None."""
        return (self.doc.get("sources") or {}).get(doc_rel)


def rel_of(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        raise SidecarError(f"{p} is not inside the root {root}") from None


def default_path(milestone: str, root: Path) -> Path:
    return Path(root) / "spec" / milestone / "lib" / "sort_types.json"


def load(milestone: str, root: Path, sidecar: str | None = None) -> Sidecar:
    root = Path(root).resolve()
    if sidecar:
        p = Path(sidecar)
        p = p if p.is_absolute() else root / p
    else:
        if not str(milestone).startswith("M"):
            raise SidecarError(f"test milestone {milestone} needs --sidecar")
        p = default_path(milestone, root)
    if not p.is_file():
        raise SidecarError(f"the typed-sorts sidecar {p} does not exist")
    doc = json.loads(p.read_text(encoding="utf-8"))
    if doc.get("sort_types_version") != VERSION:
        raise SidecarError(f"{p}: sort_types_version {doc.get('sort_types_version')!r} (want {VERSION})")
    for k in ("documents", "seeds"):
        if k not in doc:
            raise SidecarError(f"{p}: no {k!r}")
    return Sidecar(p, rel_of(p, root), doc, root)
