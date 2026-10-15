"""Shared helpers for Milestone M4 preregistered tests."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREDICTIONS = ROOT / "spec" / "M4" / "predictions.json"
SIDECAR = ROOT / "spec" / "M4" / "lib" / "corpus_controls.json"
CORPUS_MANIFEST = ROOT / "spec" / "eval" / "corpus_manifest.json"
EXCERPTS_DIR = ROOT / "spec" / "eval" / "excerpts"
CONTROLS_DIR = ROOT / "spec" / "eval" / "controls"
GEN_CONTROLS_DIR = ROOT / "gen" / "M4" / "controls"
RESULTS_CONTROLS_DIR = ROOT / "results" / "M4" / "controls"
RESULTS_I48 = ROOT / "results" / "eval" / "I48_corpus_controls.json"
HELDOUT_SEAL = ROOT / "spec" / "heldout" / "target.json"
GIT_CACHE_DIR = Path("/tmp/holon-corpus-cache")
GIT_CACHE_REPOS = {
    "morph": "morph.git",
    "arbitrum-nitro": "nitro-contracts.git",
    "optimism": "optimism.git",
    "taiko": "taiko-mono.git",
}


def load_predictions() -> dict:
    return json.loads(PREDICTIONS.read_text(encoding="utf-8"))


def iteration(it_id: str) -> dict:
    doc = load_predictions()
    return doc["iterations"][it_id]


def load_sidecar() -> dict:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def check_frozen() -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "freeze.py"), "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())
