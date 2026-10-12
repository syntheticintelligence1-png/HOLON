"""Helpers for the M2/1 audit-fix tests (audit/M2_round1.md): toy holon-ir/0.3 milestones in throwaway copies.

A milestone is written into a copy of the repository (tests._util.copy_repo, no .git): its laws, with facts_sha256
set, and a REGISTRY.json whose statement hashes are holon.gen.refs.law_hash (refs into the facts, the target
library and the oracle sidecar), so `holon run` checks it without --no-registry and the gate's G2 can pass.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json  # noqa: F401

FIX = ROOT / "tests_m2" / "fixtures" / "ir03"
TOY = "tests_m2/fixtures/toy_queue/toy_queue.facts.json"
ORACLE_TOY = "tests_m2/fixtures/oracles/facts/toy_oracle.facts.json"


def fixture(lid: str) -> dict:
    return load_json(FIX / f"{lid}.json")


def law03(lid: str, statement: dict, facts: str = TOY, rule: str = "SORT", **extra) -> dict:
    return {"ir_version": "holon-ir/0.3", "law_id": lid, "milestone": "T1", "rule": rule,
            "rule_catalog_version": "holon-rules/0.1", "facts": facts, "facts_sha256": "",
            "statement": copy.deepcopy(statement), **extra}


def write_milestone(repo: Path, m: str, laws: list[dict]) -> dict:
    """laws/<m>/ in repo: each law (milestone m, facts_sha256 of its facts) and REGISTRY.json. Returns the laws."""
    R = holon_module("holon.gen.refs")
    O = holon_module("holon.gen.oracles")
    d = repo / "laws" / m
    d.mkdir(parents=True, exist_ok=True)
    stm, files, out = {}, {}, {}
    for law in laws:
        law = copy.deepcopy(law)
        fp = repo / law["facts"]
        sha = hashlib.sha256(fp.read_bytes()).hexdigest()
        law["facts_sha256"], law["milestone"] = sha, m
        files[law["facts"]] = sha
        write_json(d / f"{law['law_id']}.json", law)
        stm[law["law_id"]] = R.law_hash(law, load_json(fp), oracles=O.Oracles.for_facts(fp), root=repo)
        out[law["law_id"]] = law
    first = laws[0]["facts"]
    write_json(d / "REGISTRY.json", {"milestone": m, "facts": first, "facts_sha256": files[first], "facts_files": files,
                                     "statements": stm})
    return out


def holon(repo: Path, *args: str, timeout: int = 1800) -> subprocess.CompletedProcess:
    return run_holon(list(args), cwd=repo, timeout=timeout)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
               GIT_AUTHOR_DATE="2026-01-01T00:00:00Z", GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)


def git_init(repo: Path) -> None:
    for a in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "seed"]):
        p = git(repo, *a)
        if p.returncode != 0:
            raise AssertionError(f"git {a}: {p.stderr}")


def commit_all(repo: Path, msg: str) -> str:
    for a in (["add", "-A"], ["commit", "-q", "--allow-empty", "-m", msg]):
        p = git(repo, *a)
        if p.returncode != 0:
            raise AssertionError(f"git {a}: {p.stderr}")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def cleanup(repo: Path) -> None:
    shutil.rmtree(Path(repo).parent, ignore_errors=True)
