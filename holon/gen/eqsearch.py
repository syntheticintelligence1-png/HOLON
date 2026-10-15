"""The lemma search of holon.gen.equivalence (F33): fast, and never a stand-in for the final check.

holon.gen.equivalence decides a binding change with one PROOF.bend that holds a lemma q_<f> : {P.o__f(x) == P.f(x)}
for every changed definition f the roots reach, checked whole, once, by bend2 and by BendTT (--verdict). This module
only FINDS those lemmas. Nothing it decides is a verdict: a lemma it reports proven is a text that bend2 accepted in a
smaller file, and the caller's final whole-file check in both kernels is the only thing that counts.

How a lemma is found (F31/F32's classes, in a fixed order, CLASSES):
  * Every changed definition has a level (0 when it reaches no other changed definition, else one more than the
    highest level of those it reaches) and is worked on in (level, name) order.
  * A candidate is the text a class generates for f. It is a function of f's obligation alone: the generator is
    given only the changed definitions f reaches (all proven by then), and Gen's fresh-name counter is reset per
    candidate. So the same obligation gives the same text in any law, any run, any order.
  * The chosen proof of f is the first class, in CLASSES order, whose candidate bend2 accepts. Whether a candidate is
    accepted depends only on its text and the lemmas it uses, so batching, parallel checks and the cache below cannot
    change which text is chosen: the final PROOF.bend is byte-identical whatever the history.
  * Candidates are checked in batches (up to `batch` definitions, 256 by default: a check costs about the sum of the
    lemmas it holds, and every check must hold the proven lemmas its batch uses, so a few large batches beat many
    small ones once the proven lemmas are costly in (level, name) order) in a small file: Base, the
    core block, the lemma libraries, the proven lemmas the batch uses (transitively) and the batch, importing a SLICE
    of the pair module (the items the file reaches, closed under reference; the full pair module when a slice misses
    a name). bend2 checks a file in order and stops at the first error, so a failing batch still proves every lemma
    before the failing one; the failing candidate's class is marked failed (the kernel's message kept) and f moves on
    to its next class. At most `workers` (2) batch files are checked at once: the second batch includes the first
    one's lemmas it uses, so its verdict is exact either way.
  * Proven lemmas are cached by their obligation key: the sha256 of the generator's own source, the core and library
    text, f, and the text of every pair-module item q_<f>'s statement reaches (closed under reference). Two pair modules
    built from the same two models (the three laws of one model pair) give the same key for the same definition, so a
    lemma found for one law is found for the others. The cache lives in memory and, when a path is given, in an
    append-only JSON-lines file (resumable after a crash; holon.gen.equivalence.default_cache: ~/.holon/cache/eqv/
    <model pair hash>/<checker, kernel and generator hash>.jsonl, outside the repository). A cached text is used
    without a per-candidate check; it is still checked in the final whole file, and a cached text the final check
    refuses is evicted and searched again (reject).

Target-agnostic: no law ids, no target or definition names.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# the classes, in the order a candidate is tried. The first class bend2 accepts is the proof (deterministic). Ordered
# by observed success on real cones (F31: congruence proved 189 of 203 changed definitions, normalize 10, the other
# classes one each; eqprove, F32, only what nothing else proves), so a definition costs one candidate most of the time.
CLASSES = ("congruence", "congruence-old", "normalize", "congruence-x", "congruence-old-x", "congruence-core",
           "eqprove")

_DEF = re.compile(r"^def ([A-Za-z_][\w.]*)\(", re.M)
_PREF = re.compile(r"(?<![\w.])P\.([A-Za-z_]\w*)")
_IDENT = re.compile(r"(?<![\w.$])([A-Za-z_][A-Za-z0-9_]*)(?![\w])")
_SRC_LINE = re.compile(r"^\s*\d*\s*[>]?\|")


def clean_message(msg: str) -> str:
    """A kernel message without the source excerpt (its line numbers depend on the file the candidate sat in)."""
    return "\n".join(ln for ln in msg.splitlines() if not _SRC_LINE.match(ln)).strip()


def generator_sha256() -> str:
    """sha256 of the class order and of the source of the modules that produce candidate texts (the search itself, this
    module, decides only which candidates are checked, never their text)."""
    from . import eqlib, eqprove, eqterms, equivalence
    from ..sorts import prelude3_lemmas
    h = hashlib.sha256(repr(CLASSES).encode())
    for m in (equivalence, eqprove, eqterms, eqlib, prelude3_lemmas):
        h.update(b"\0")
        h.update(Path(m.__file__).read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- the pair module's source graph
class SourceGraph:
    """The pair module's items, which item each name (definition, datatype, constructor) belongs to, and which items
    each item's text refers to."""

    def __init__(self, text: str):
        from .equivalence import parse_items
        self.header, self.items = parse_items(text)
        self.owner: dict = {}
        for i, it in enumerate(self.items):
            self.owner[it.name] = i
            for c, _ in it.ctors:
                self.owner[c] = i
        self.refs = []
        for i, it in enumerate(self.items):
            self.refs.append(sorted({self.owner[t] for t in _IDENT.findall(it.text) if t in self.owner} - {i}))
        self.text = text

    def closure(self, names) -> set:
        seen, todo = set(), [self.owner[n] for n in names if n in self.owner]
        while todo:
            i = todo.pop()
            if i not in seen:
                seen.add(i)
                todo.extend(self.refs[i])
        return seen

    def slice(self, file_text: str) -> str:
        """The pair module cut down to the items file_text reaches through P.<name>, closed under reference (in the
        module's order)."""
        keep = self.closure(set(_PREF.findall(file_text)))
        parts = ["\n".join(self.header)]
        for i, it in enumerate(self.items):
            if i in keep:
                parts.append(it.text.rstrip("\n"))
        return "\n\n".join(parts) + "\n"

    def key_text(self, names) -> str:
        return "\n".join(self.items[i].text for i in sorted(self.closure(names), key=lambda i: self.items[i].name))


# ---------------------------------------------------------------- the cache
class LemmaCache:
    """Proven lemma texts by obligation key, and failed candidates by (key, class, text sha256). In memory, and in an
    append-only JSON-lines file when path is given (loaded on creation: a crashed run resumes)."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.ok: dict = {}
        self.bad: dict = {}
        self.lock = threading.Lock()
        if self.path and self.path.is_file():
            for raw in self.path.read_text().splitlines():
                try:
                    x = json.loads(raw)
                except ValueError:
                    continue   # a line cut by a crash
                if not isinstance(x, dict):
                    continue
                if x.get("ok") and isinstance(x.get("key"), str):
                    self.ok[x["key"]] = {"def": x.get("def"), "class": x.get("class"), "text": x.get("text"),
                                         "attempts": x.get("attempts") or []}
                elif x.get("bad") and isinstance(x.get("key"), str):
                    self.bad[(x["key"], x.get("class"), x.get("sha"))] = x.get("message", "")
                elif x.get("evict") and isinstance(x.get("key"), str):
                    self.ok.pop(x["key"], None)

    def _append(self, rec: dict):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            fh.flush()

    def get(self, key: str):
        return self.ok.get(key)

    def put(self, key: str, f: str, cls: str, text: str, attempts: list):
        with self.lock:
            if self.ok.get(key, {}).get("text") == text:
                return
            self.ok[key] = {"def": f, "class": cls, "text": text, "attempts": list(attempts)}
            self._append({"ok": True, "key": key, "def": f, "class": cls, "text": text, "attempts": list(attempts)})

    def failed(self, key: str, cls: str, text: str):
        return self.bad.get((key, cls, _sha(text)))

    def mark_failed(self, key: str, cls: str, text: str, message: str):
        with self.lock:
            k = (key, cls, _sha(text))
            if k in self.bad:
                return
            self.bad[k] = message
            self._append({"bad": True, "key": key, "class": cls, "sha": _sha(text), "message": message})

    def evict(self, key: str):
        with self.lock:
            if self.ok.pop(key, None) is not None:
                self._append({"evict": True, "key": key})


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


_CACHES: dict = {}


def cache_at(path: Path | None) -> LemmaCache:
    """One LemmaCache per path in a process (the three laws of one model pair share it)."""
    k = str(path) if path else None
    if k is None:
        return LemmaCache(None)
    if k not in _CACHES:
        _CACHES[k] = LemmaCache(Path(k))
    return _CACHES[k]


# ---------------------------------------------------------------- the search
class Search:
    """Find a lemma for every changed definition (see the module docstring). run() fills .proven {f: {class, text}}
    and .failed {f: why}; .attempts {f: [messages]}; .stats."""

    def __init__(self, pm, gen, libs, changed: list, deps: dict, cfg, tmp: Path, head: str, lemma_prefix: str,
                 prefix: str, alias: str, cache: LemmaCache | None = None, workers: int = 2, batch: int = 256,
                 engine=None, progress=None):
        self.pm, self.gen, self.libs, self.cfg, self.tmp = pm, gen, libs, cfg, Path(tmp)
        self.changed, self.deps = list(changed), deps
        self.head = head                       # Base import, pair import, core block, libraries
        self.L, self.PREFIX, self.ALIAS = lemma_prefix, prefix, alias
        self.cache = cache or LemmaCache(None)
        self.workers = max(1, min(2, int(workers)))
        self.batch = max(1, int(batch))
        self.engine = engine                   # f, cone -> (label, text); raises Unsupported
        self.progress = progress or (lambda msg: None)
        self.level: dict = {}
        self._levels()
        self.order = sorted(changed, key=lambda f: (self.level[f], f))
        self.cone = self._cones()
        self.src = SourceGraph(pm.text)
        self.head_sha = _sha(head)
        self.gen_sha = generator_sha256()
        self.keys: dict = {}
        self.cur: dict = {}                    # f -> (class index, class label, text) of the current candidate
        self.next_cls: dict = {f: 0 for f in changed}
        self.proven: dict = {}
        self.failed: dict = {}
        self.attempts: dict = {f: [] for f in changed}
        self.full_pair = False
        self.last_seconds = 0.0
        self.jobs = 0
        self.stats = {"checks": 0, "check_seconds": 0.0, "cache_hits": 0, "cache_failed_skips": 0, "candidates": 0,
                      "failed_candidates": 0, "timeouts": 0, "slice_misses": 0, "by_class": {}}

    # -- structure
    def _levels(self):
        memo = self.level

        def lv(f, stack=()):
            if f in memo:
                return memo[f]
            if f in stack:
                raise RuntimeError(f"a cycle among changed definitions through {f}")
            memo[f] = 0 if not self.deps[f] else 1 + max(lv(g, stack + (f,)) for g in self.deps[f])
            return memo[f]
        for f in sorted(self.changed):
            lv(f)

    def _cones(self) -> dict:
        cone: dict = {}
        for f in sorted(self.changed, key=lambda g: (self.level[g], g)):
            s = set(self.deps[f])
            for g in self.deps[f]:
                s |= cone[g]
            cone[f] = s
        return cone

    def key(self, f: str) -> str:
        if f not in self.keys:
            names = [f] + ([self.PREFIX + f] if (self.PREFIX + f) in self.src.owner else [])
            h = hashlib.sha256()
            for part in (self.gen_sha, self.head_sha, f, self.src.key_text(names)):
                h.update(part.encode())
                h.update(b"\0")
            self.keys[f] = h.hexdigest()
        return self.keys[f]

    # -- candidates
    def _make(self, f: str, cls: str):
        """(label, text) of class cls for f, None when the class does not apply; raises Unsupported with a reason."""
        from .equivalence import Unsupported
        gen, L = self.gen, self.L
        lemmas = {g: L + g for g in sorted(self.cone[f])}
        lemmas[f] = L + f
        gen.fresh = 0
        if cls == "eqprove":
            if self.engine is None:
                return None
            return self.engine(f, sorted(self.cone[f]))
        if cls == "normalize":
            r = gen.normalize(f, L + f)
        elif cls == "congruence":
            r = gen.congruence(f, L + f, lemmas, "new")
        elif cls == "congruence-old":
            r = gen.congruence(f, L + f, lemmas, "old")
        elif cls == "congruence-x":
            r = gen.congruence(f, L + f, lemmas, "new", expand=True)
        elif cls == "congruence-old-x":
            r = gen.congruence(f, L + f, lemmas, "old", expand=True)
        elif cls == "congruence-core":
            r = gen.congruence(f, L + f, lemmas, "new", core=True)
        else:
            raise Unsupported(f"unknown class {cls}")
        if r is None:
            return None
        if isinstance(r, tuple):
            text, ih = r
            label = (("induction" if ih else "congruence") + (" (old tree)" if "old" in cls else "")
                     + (" (wildcards split)" if cls.endswith("-x") else "")
                     + (" with Base identities" if cls.endswith("-core") else ""))
            return label, text
        return cls, r

    def current(self, f: str):
        """f's current candidate (class index, label, text), materialized; None when every class is used up."""
        from .equivalence import Unsupported
        if f in self.cur:
            return self.cur[f]
        k = self.key(f)
        while self.next_cls[f] < len(CLASSES):
            i = self.next_cls[f]
            cls = CLASSES[i]
            self.next_cls[f] = i + 1
            try:
                r = self._make(f, cls)
            except Unsupported as e:
                self.attempts[f].append(f"{cls}: not applicable: {e}")
                continue
            except RecursionError as e:
                self.attempts[f].append(f"{cls}: not applicable: {e}")
                continue
            if r is None:
                continue
            label, text = r
            why = self.cache.failed(k, cls, text)
            if why is not None:   # this very candidate was refused before (same obligation, same text)
                self.stats["cache_failed_skips"] += 1
                self.attempts[f].append(f"{label}: {why}")
                continue
            self.stats["candidates"] += 1
            self.cur[f] = (i, label, text)
            return self.cur[f]
        return None

    def _reject_current(self, f: str, message: str):
        i, label, text = self.cur.pop(f)
        msg = clean_message(message)
        self.attempts[f].append(f"{label}: {msg}")
        self.stats["failed_candidates"] += 1
        self.cache.mark_failed(self.key(f), CLASSES[i], text, msg)

    def _prove(self, f: str, label: str, text: str, cached: bool = False):
        self.proven[f] = {"class": label, "text": text}
        self.cur.pop(f, None)
        per_class = self.stats["by_class"]
        per_class[label] = per_class.get(label, 0) + 1
        if not cached:
            self.cache.put(self.key(f), f, label, text, self.attempts[f])

    def owner_of(self, loc: str):
        """The proven lemma a failing definition of the final file belongs to (q_<f> or a helper q_<f>__<x>)."""
        best = None
        for f in self.proven:
            if loc == self.L + f or loc.startswith(self.L + f + "__"):
                if best is None or len(f) > len(best):
                    best = f
        return best

    def reject(self, f: str, message: str):
        """The final check refused f's lemma (a cached text, or a check that disagreed): evict it and search again."""
        p = self.proven.pop(f, None)
        if p is None:
            return
        self.cache.evict(self.key(f))
        msg = clean_message(message)
        # find which class the text came from, so the same candidate is not tried again
        for i, cls in enumerate(CLASSES):
            self.cache.mark_failed(self.key(f), cls, p["text"], msg)
        # start f's classes again (a cached text skipped them); candidates refused before are skipped by the cache
        self.attempts[f] = [f"{p['class']}: refused by the final check: {msg}"]
        self.next_cls[f] = 0
        self.cur.pop(f, None)

    # -- the loop
    def _absorb_cache(self):
        for f in self.order:
            if f in self.proven or f in self.failed:
                continue
            if not all(g in self.proven for g in self.deps[f]):
                continue
            hit = self.cache.get(self.key(f))
            if hit and isinstance(hit.get("text"), str):
                self.attempts[f] = list(hit.get("attempts") or [])
                self._prove(f, hit["class"], hit["text"], cached=True)
                self.stats["cache_hits"] += 1

    def _eligible(self, limit: int) -> list:
        out, pend = [], set()
        for f in self.order:
            if f in self.proven or f in self.failed:
                continue
            if not all(g in self.proven or g in pend for g in self.deps[f]):
                continue
            if self.current(f) is None:
                self.failed[f] = "every class failed"
                continue
            out.append(f)
            pend.add(f)
            if len(out) >= limit:
                break
        return out

    def _needed(self, pool: dict, texts) -> set:
        from .equivalence import _LEMMA_REF
        need, todo = set(), list(texts)
        while todo:
            for m in _LEMMA_REF.finditer(todo.pop()):
                t = m.group(1)
                for g in [t] + [t[:i] for i in range(len(t)) if t.startswith("__", i)]:
                    if g in pool and g not in need:
                        need.add(g)
                        todo.append(pool[g])
        return need

    def _file(self, chunk: list, spec: dict):
        """(blocks [(f, text, kind)], lemma file text) for a batch; spec: an earlier batch's candidate texts."""
        texts = {f: self.cur[f][2] for f in chunk}
        pool = {g: p["text"] for g, p in self.proven.items()}
        pool.update(spec)
        need = self._needed(pool, texts.values())
        blocks = [(g, pool[g], "spec" if g in spec else "proven") for g in self.order if g in need]
        blocks += [(f, texts[f], "cand") for f in chunk]
        return blocks, self.head + "\n" + "\n".join(b[1] for b in blocks)

    def _check(self, text: str, job: int):
        from .equivalence import _run
        d = self.tmp / f"s{job}"
        d.mkdir(parents=True, exist_ok=True)
        pair = self.pm.text if self.full_pair else self.src.slice(text)
        (d / "pair.bend").write_text(pair)
        (d / "LEMMAS.bend").write_text(text)
        r = _run(d, "LEMMAS.bend", self.cfg)
        for p in d.iterdir():
            p.unlink()
        d.rmdir()
        return r

    def _owner(self, loc: str, blocks: list):
        """Index of the block a failing definition belongs to, or None."""
        best = None
        for j, (f, text, _) in enumerate(blocks):
            if loc == self.L + f or loc.startswith(self.L + f + "__") or loc in _DEF.findall(text):
                if best is None or len(f) > len(blocks[best][0]):
                    best = j
        return best

    def _apply(self, blocks: list, r) -> str | None:
        """Learn from one checked batch file; returns a reason when the failure is not attributable."""
        self.stats["checks"] += 1
        self.stats["check_seconds"] += r.seconds
        self.last_seconds = r.seconds
        if r.ok:
            for f, text, kind in blocks:
                if kind != "proven" and f not in self.proven and f in self.cur and self.cur[f][2] == text:
                    self._prove(f, self.cur[f][1], text)
            return None
        if "[timeout]" in r.out:
            self.stats["timeouts"] += 1
            return None if self.stats["timeouts"] <= 6 else "bend timed out on lemma files repeatedly"
        j = self._owner(r.location or "", blocks)
        if j is None:
            if "a defined name" in r.out and not self.full_pair:
                self.stats["slice_misses"] += 1
                self.full_pair = True
                self.progress("a pair-module slice missed a name: checking against the whole pair module from here")
                return None
            j = self._bisect(blocks)   # no location (a stack overflow): the shortest failing prefix names the block
            if j is None:
                from .equivalence import kernel_message
                return f"lemma check failed outside the lemmas: {kernel_message(r.out)}"
            self.progress(f"a check failed without a location; bisection names {blocks[j][0]} ({blocks[j][2]})")
        for f, text, kind in blocks[:j]:   # bend2 checks in order: everything before the failure passed
            if kind != "proven" and f not in self.proven and f in self.cur and self.cur[f][2] == text:
                self._prove(f, self.cur[f][1], text)
        f, text, kind = blocks[j]
        if kind == "proven":
            self.reject(f, r.out)
        elif f in self.cur and self.cur[f][2] == text and f not in self.proven:
            self._reject_current(f, r.out)
        return None

    def _bisect(self, blocks: list):
        """Index of the first block whose prefix fails (blocks are in dependency order, so every prefix is a file of its
        own), None when the whole file passes alone or the head fails without any block."""
        def fails(k):
            self.jobs += 1
            r = self._check(self.head + "\n" + "\n".join(b[1] for b in blocks[:k]), self.jobs)
            self.stats["checks"] += 1
            self.stats["check_seconds"] += r.seconds
            self.stats["bisect_checks"] = self.stats.get("bisect_checks", 0) + 1
            return not r.ok
        if not fails(len(blocks)) or fails(0):
            return None
        lo, hi = 0, len(blocks)   # prefix lo passes, prefix hi fails
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if fails(mid):
                hi = mid
            else:
                lo = mid
        return hi - 1

    def run(self, deadline: float | None = None) -> str | None:
        """Search until every changed definition is proven, failed or blocked. Returns a reason when it had to stop
        (an unattributable failure, or the deadline), else None."""
        t0 = time.monotonic()
        last = 0.0
        pool = ThreadPoolExecutor(max_workers=self.workers) if self.workers > 1 else None
        try:
            while True:
                self._absorb_cache()
                # small batches while checks are cheap (a failure re-checks less), `batch` once they cost more
                size = self.batch if self.last_seconds > 20 else min(self.batch, 48)
                elig = self._eligible(size * self.workers)
                now = time.monotonic()
                if now - last > 30 or not elig or self.stats["check_seconds"] > 600:
                    last = now
                    self.progress(f"search: {len(self.proven)} proven, {len(self.failed)} failed, "
                                  f"{len(self.changed) - len(self.proven) - len(self.failed)} left of "
                                  f"{len(self.changed)}; {self.stats['checks']} checks "
                                  f"({self.stats['check_seconds']:.0f} s), {self.stats['failed_candidates']} failed "
                                  f"candidates, {self.stats['cache_hits']} cache hits; {now - t0:.0f} s")
                if not elig:
                    return None
                if deadline is not None and now > deadline:
                    return "time box"
                chunks = [elig[i:i + size] for i in range(0, len(elig), size)][:self.workers]
                files, spec = [], {}
                for c in chunks:
                    files.append(self._file(c, spec))
                    spec = {**spec, **{f: self.cur[f][2] for f in c}}
                ids = []
                for _ in files:
                    self.jobs += 1
                    ids.append(self.jobs)
                if pool is not None and len(files) > 1:
                    rs = list(pool.map(lambda x: self._check(x[0][1], x[1]), zip(files, ids)))
                else:
                    rs = [self._check(t, i) for (_, t), i in zip(files, ids)]
                for (blocks, _), r in zip(files, rs):
                    why = self._apply(blocks, r)
                    if why:
                        return why
        finally:
            if pool is not None:
                pool.shutdown(wait=True)

    def ordered(self) -> list:
        """The proven lemmas in proof order ((level, name): every lemma after the lemmas it uses)."""
        return [f for f in self.order if f in self.proven]


def default_workers() -> int:
    try:
        return max(1, min(2, int(os.environ.get("HOLON_EQV_WORKERS", "2"))))
    except ValueError:
        return 2


def default_batch() -> int:
    try:
        return max(1, int(os.environ.get("HOLON_EQV_BATCH", "256")))
    except ValueError:
        return 256
