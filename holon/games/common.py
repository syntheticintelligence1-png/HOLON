"""Shared helpers of holon.games: file format, hashes, the sidecar and its documents."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = "spec/M5/lib/games_M3.json"
FLOWS_PIN = "spec/M5/lib/games_M3_flows.json"
ETH = "eth"


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load(root: Path, rel: str) -> dict:
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


class Target:
    """The game sidecar and the documents it names (definitions G-C1..G-C3)."""

    def __init__(self, root: Path = ROOT, sidecar: str = SIDECAR):
        self.root = Path(root)
        self.sc = load(self.root, sidecar)
        self.docs = {}
        for d in self.sc["documents"]:
            if sha256_file(self.root / d["path"]) != d["sha256"]:
                raise ValueError(f"{d['path']}: sha256 differs from the sidecar's pin")
            self.docs[d["member"]] = load(self.root, d["path"])
        run = self.sc["run"]
        if sha256_file(self.root / run["init"]) != run["init_sha256"]:
            raise ValueError(f"{run['init']}: sha256 differs from the sidecar's pin")
        self.member_caller = set(self.sc["member_caller"])
        self.trusted = {c["id"]: c["trusted"] for c in self.sc["classes"]}

    def group(self, member: str, action: dict) -> str:
        """G-C1."""
        p = action.get("principal")
        return "anyone" if not p else f"{member}.{p['modifier']}"

    def klass(self, member: str, action: dict) -> str | None:
        g = self.group(member, action)
        return None if g in self.member_caller else g

    def classes(self) -> list[str]:
        """G-C2: every group but the member-caller ones; checked against the sidecar's list."""
        gs = {self.group(m, a) for m in self.docs for a in self.docs[m]["actions"]}
        out = sorted(g for g in gs if g not in self.member_caller)
        if out != sorted(self.trusted):
            raise ValueError(f"the documents' classes {out} are not the sidecar's {sorted(self.trusted)}")
        return out

    def action(self, member: str, name: str) -> dict | None:
        return next((a for a in self.docs[member]["actions"] if a["name"] == name), None)
