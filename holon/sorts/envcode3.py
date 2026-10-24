"""The runtime code of a typed milestone's deployment: the environment's code table of the M3 model (F40).

  deployment_code(root, binding_rel, doc_rel) -> {"0x<address>": "0x<runtime code>"}

holon.sorts.deploy3's capture records, after the binding's harness deployed the target, the target's and its
implementation's runtime code (its lines K and Q); its deployment() keeps neither in the initial state. This module
runs the same capture (deploy3.run_capture, unchanged) and keeps exactly those two: the code at the target's address
and at its implementation's, each when it is not empty. holon.sorts.run3 adds the table to the model's init as
init["code"], and holon.sorts.search3 gives it to the environment of every step whose action reads an account's code
(Rollup's initialize reads this contract's code, initialize4 its new submitter's): the world a step runs in holds the
code the deployment put there, where before it held none (an empty code table: every account without code, the target
included).

The result is cached outside the repository (~/.holon/cache/m3code/), keyed by deploy3's own deployment key (the
binding, its harness files, the document, the checkout commit, the deployment parameters, deploy3's text) and this
module's text. deploy3 stays as it is: it is in the holon-ir/0.2 and 0.3 generator closures, this module only in
I30's (holon.sorts.run3).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from . import deploy3


def _cache() -> Path:
    return deploy3._cache().parent / "m3code"


def codes(cap: dict) -> dict:
    """{address: runtime code} of the capture's target and implementation, the ones it recorded with code."""
    out = {}
    for a, c in ((cap.get("target"), cap.get("code")), (cap.get("impl"), cap.get("impl_code"))):
        if a and isinstance(c, str) and len(c) > 2:
            out[a.lower()] = c.lower()
    return dict(sorted(out.items()))


def deployment_code(root: Path, binding_rel: str, doc_rel: str) -> dict:
    from ..fragments_corpus import binding_init
    from ..replay_fragments import load_binding
    root = Path(root)
    binding = load_binding(root / binding_rel)
    doc = json.loads((root / doc_rel).read_text(encoding="utf-8"))
    init = binding_init(binding, root)
    commit = (doc.get("target") or {}).get("commit")
    h = hashlib.sha256(deploy3._key(root, binding_rel, binding, doc_rel, init, commit).encode())
    h.update(Path(__file__).read_bytes())
    cp = _cache() / f"{h.hexdigest()}.json"
    if cp.is_file():
        try:
            return json.loads(cp.read_text())
        except ValueError:
            pass
    work = Path(tempfile.mkdtemp(prefix="holon-m3-code-"))
    try:
        cap, _proj = deploy3.run_capture(root, binding_rel, binding, doc, init, work)
        res = codes(cap)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(res, indent=2, sort_keys=True))
    return res


def with_code(init: dict, root: Path, doc_rel: str) -> dict:
    """The model's init with its deployment's code table (init itself when it has no binding)."""
    if not init.get("binding"):
        return init
    return {**init, "code": deployment_code(root, init["binding"], doc_rel)}
