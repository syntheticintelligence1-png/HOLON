"""What the I23 commands read: the instrument, I59's sidecar, index and snapshot, the extracted model, and the in-scope
transactions of the trans window (the instrument's in_scope.rule).

    Window(milestone, root, snapshot=None)
      .inst          spec/<M>/lib/historical_exit.json (the frozen instrument)
      .side          spec/<M>/lib/historical.json (I59's sidecar: events, sources' limits, the window)
      .idx           results/<M>/historical/index.json (I59's index; a Git LFS pointer is an error)
      .snap          the I59 snapshot (index "snapshot", or HOLON_HISTORICAL_DIR, or --snapshot), objects re-hashed
                     on read; a missing snapshot is an error, never a skip
      .trans         the trans window {from_block, to_block, to_block_hash}
      .proxy         the instrument's implementation.proxy
      .five          I59's five topics (lowercase)
      .index_txs()   [(block, tx)] of I59's index items of kind tx inside the trans window
      .index_logs()  {(tx, log index): sha256} of I59's index log items inside the trans window
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import stepper as S
from .fetch import sidecar
from .store import Snapshot, StoreError

ROOT = Path(__file__).resolve().parents[2]


class ContextError(RuntimeError):
    pass


def load_index(path: Path) -> dict:
    if not path.is_file():
        raise ContextError(f"{path} is missing: I59's index is an input of I23 (python -m holon historical fetch)")
    if path.stat().st_size < 1024 and path.read_bytes().startswith(b"version https://git-lfs"):
        raise ContextError(f"{path} is a Git LFS pointer: run git lfs pull")
    return json.loads(path.read_text())


class Window:
    def __init__(self, milestone: str = "M2", root: Path = ROOT, snapshot: str | None = None, index: dict | None = None):
        self.milestone, self.root = milestone, Path(root)
        self.inst = S.instrument(milestone, self.root)
        self.side = sidecar(milestone, self.root)
        self.idx = index if index is not None else load_index(self.root / "results" / milestone / "historical" /
                                                              "index.json")
        d = snapshot or os.environ.get("HOLON_HISTORICAL_DIR") or self.idx.get("snapshot")
        if not d or not (Path(os.path.expanduser(d)) / "objects").is_dir():
            raise ContextError(f"the I59 snapshot {d!r} is missing (its objects/ directory): restore it or set "
                               "HOLON_HISTORICAL_DIR; holon historical fetch --offline cannot recreate it")
        try:
            self.snap = Snapshot(Path(os.path.expanduser(d)).resolve())
        except StoreError as e:
            raise ContextError(str(e)) from None
        self.trans = dict(self.inst["windows"]["trans"])
        self.codec = dict(self.inst["windows"]["codec"])
        self.proxy = self.inst["implementation"]["proxy"].lower()
        self.five = sorted(v.lower() for v in self.side["events"].values())

    def window(self, which: str = "trans") -> dict:
        w = self.inst["windows"][which]
        return {k: w[k] for k in ("from_block", "to_block", "to_block_hash")}

    def inside(self, block: int) -> bool:
        return self.trans["from_block"] <= block <= self.trans["to_block"]

    def index_items(self, kind: str) -> list[dict]:
        return [x for x in self.idx["items"] if x["kind"] == kind and self.inside(x["block"])]

    def index_txs(self) -> list[tuple[int, str]]:
        return sorted({(x["block"], x["tx"]) for x in self.index_items("tx")})

    def index_logs(self) -> dict:
        return {(x["tx"], x["log_index"]): x["sha256"] for x in self.index_items("log")}

    def obj(self, sha: str):
        return self.snap.read_json(sha)
