"""Targets (I47): what the factory knows about a system under analysis lives in targets/<name>/target.json.

A target description (holon-target/0.1, spec/M4/lib/target.schema.json) holds everything about a target that is not a
law, a fact document or a committed outcome: its identity names, its upstream (url, pinned commit, the watched ref
prefix and the refs seen at the pin), where its checkout is configured, how its documents are extracted, how it is run,
where its dependency index is and where drift writes. holon/ itself names no target: every module that needs a
target-specific value reads it here, by key.

The development target is the one whose checkout says "development": true (checkout.development). A module that serves only the development
target's pinned milestones (the replay adapters, the historical tooling, the mutation runner) reads its vocabulary
(checkout.vocab, `vocab`) from it: report keys, document names and paths, the checkout's config key, the adapters' entry points.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-target/0.1"


class TargetError(ValueError):
    pass


def targets_dir(root: Path | str | None = None) -> Path:
    return Path(root or ROOT) / "targets"


def names(root: Path | str | None = None) -> list[str]:
    return sorted(p.parent.name for p in targets_dir(root).glob("*/target.json"))


@lru_cache(maxsize=None)
def _load(path: str) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("target_version") != VERSION:
        raise TargetError(f"{path}: target_version {d.get('target_version')!r} is not {VERSION}")
    if d.get("name") != Path(path).parent.name:
        raise TargetError(f"{path}: name {d.get('name')!r} is not its directory's")
    return d


def load(name: str, root: Path | str | None = None) -> dict:
    p = targets_dir(root) / name / "target.json"
    if not p.is_file():
        raise TargetError(f"no target {name!r}: {p} does not exist (targets: {', '.join(names(root)) or 'none'})")
    return _load(str(p.resolve()))


def development(root: Path | str | None = None) -> dict:
    devs = [load(n, root) for n in names(root) if (load(n, root).get("checkout") or {}).get("development")]
    if len(devs) != 1:
        raise TargetError(f"exactly one target must be the development target, found {len(devs)}")
    return devs[0]


def vocab(key: str, root: Path | str | None = None):
    """A value of the development target's vocabulary (targets/<dev>/target.json checkout.vocab)."""
    v = development(root)["checkout"].get("vocab") or {}
    if key not in v:
        raise TargetError(f"the development target's vocab has no {key!r}")
    return v[key]


def config_value(cfg: dict, keys: list[str]):
    x = cfg
    for k in keys:
        x = x[k]
    return x


def checkout_key(root: Path | str | None = None) -> list[str]:
    """The config/holon.json key path of the development target's checkout (e.g. ["replay", "<name>"])."""
    return list(development(root)["checkout"]["config"])


def checkout_path(cfg: dict, root: Path | str | None = None) -> Path:
    return Path(config_value(cfg, checkout_key(root)))


def checkout_flag(root: Path | str | None = None, default: str = "--checkout") -> str:
    """The command-line flag of the replay adapters' checkout option (their argparse dest is the flag's name). A tree
    with no development target (a toy target's scratch root) has no such checkout: the flag is then `default`."""
    try:
        return development(root)["checkout"]["flag"]
    except TargetError:
        return default


def adapter(name: str, root: Path | str | None = None):
    """An entry point of the development target's replay adapters: vocab "adapters" maps a role to "module:function",
    resolved inside the holon package."""
    import importlib
    spec = vocab("adapters", root)[name]
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(f"holon.{mod}"), fn)
