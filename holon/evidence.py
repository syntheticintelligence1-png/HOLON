"""What a replay side's logged evidence shows (BUILD_PLAN I4, after the I4 review).

The replay (holon.replay, holon.mreplay, holon.consumers) and the gate (G6) decide each side's
observation with these functions, from the values the side logged, never from the side's own flag:

  observed       the real code showed the side's part of the obstruction;
  not_observed   it did not, and the model predicted nothing concrete that the evidence contradicts;
  contradiction  the logged evidence contradicts a value the model's witness predicts (a header cell,
                 a commitment, a header's preimage, a Go reading of committed bytes): a model defect,
                 so the side is "failed";
  None           the evidence is not recomputable from the side (the Go and internal-harness M0
                 sides, whose harness compares the real output with the witness and passes exactly
                 when the half-obstruction shows).

Which sides a law claims and how each side ran (provenance) are derived here from the hashed IR (the
statement), never from law ids or unhashed labels such as `subform`.
"""
from __future__ import annotations

OBSERVED, NOT_OBSERVED, CONTRADICTION = "observed", "not_observed", "contradiction"
MODEL_ONLY = "model-only pending replay"


# ---------------------------------------------------------------- IR-derived facts
def claim_kind(law: dict) -> str | None:
    """The shape of a REFUTED law's claim, from its hashed statement."""
    st = law["statement"]
    eq = st["claim"].get("eq") if isinstance(st.get("claim"), dict) else None
    if not eq:
        return None
    if law.get("ir_version") == "holon-ir/0.1":
        return "codec" if any(x.get("call") == "enc_sol" for x in eq) else "harness"
    if all("obs" in x for x in eq):
        return "differ"
    if eq[0].get("fn") == "no_code":
        return "symptom"
    if "obsv" in eq[0]:
        return "accepted"
    if eq[0].get("fn") == "blobs_of":
        return "same_commitment"
    return None


# claims whose obstruction shows only where an off-chain reader consumes what the chain committed:
# a ghost-tag observer the chain never checks, and the blob sidecar behind a commitment
CONSUMER_KINDS = frozenset({"accepted", "same_commitment"})


def _has_key(obj, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_has_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, key) for v in obj)
    return False


def claimed_sides(law: dict, registry_facts_sha256: str | None) -> set[str]:
    """Keyed on the hashed facts_sha256, never on the (unhashed) facts path: a law over facts other
    than the registry's rollup machine (the Go BatchData machine) is a Go side."""
    if law.get("ir_version") == "holon-ir/0.1":
        return {"go", "solidity"}
    if registry_facts_sha256 is not None and law.get("facts_sha256") != registry_facts_sha256:
        return {"go"}
    return {"solidity", "go_consumer"} if claim_kind(law) in CONSUMER_KINDS else {"solidity"}


def expected_provenance(law: dict, side: str) -> str:
    """How a side runs, from the IR: Go is a library call; an M0 Solidity side is a public schedule
    on the commit path when the claim calls enc_sol, an internal harness otherwise; an M1 trace is a
    public schedule unless the statement migrates legacy state (a `mig` node), which the harness
    can only reach by emulating the pre-upgrade storage."""
    if side in ("go", "go_consumer"):
        return "library_api"
    if law.get("ir_version") == "holon-ir/0.1":
        return "public_schedule" if claim_kind(law) == "codec" else "internal_harness"
    return "emulated_storage" if _has_key(law["statement"], "mig") else "public_schedule"


# ---------------------------------------------------------------- bytes
def hexb(h) -> bytes | None:
    if not isinstance(h, str) or not h.startswith("0x"):
        return None
    try:
        return bytes.fromhex(h[2:])
    except ValueError:
        return None


def _preimage_ok(header, committed) -> bool:
    from .keccak import keccak256
    hb, cb = hexb(header), hexb(committed)
    return hb is not None and cb is not None and keccak256(hb) == cb


def pins(law: dict) -> dict[str, bytes]:
    out = {}
    for prem in law["statement"].get("assume", []):
        a, b = prem["eq"]
        f, v = (a, b) if "field" in a else (b, a)
        out[f["field"]] = hexb(v["bytes"])
    return out


def cell(c: list, fields: dict[str, bytes]):
    if c[0] == "const":
        return c[1]
    if c[0] == "field" and fields.get(c[1]) is not None:
        return fields[c[1]][c[2]]
    return None


def ranges(xs: list[int]) -> str:
    out, i = [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(str(xs[i]) if i == j else f"{xs[i]}..{xs[j]}")
        i = j + 1
    return ", ".join(out)


def m0_expected_cells(law: dict, witness: dict, hfacts: dict) -> tuple[dict[int, int | None], str, int]:
    """The cells an M0 commit-path side observes: where the model's enc_sol and the claim's Go
    encoder differ on the witness, mapped to what enc_sol writes there under the law's pins.
    Returns (cells, go encoder, witness version)."""
    from . import layout as L
    fields = {k: hexb(v) for k, v in witness["h"].items()}
    version = fields["version"][0]
    go_fn = next(x["call"] for x in law["statement"]["claim"]["eq"] if x["call"] != "enc_sol")
    sol, go = L.layout(hfacts, "enc_sol", version), L.layout(hfacts, go_fn, version)
    diff = [i for i, (a, b) in enumerate(zip(sol, go)) if cell(a, fields) != cell(b, fields)]
    p = pins(law)
    return {i: cell(sol[i], p) for i in diff}, go_fn, version


# ---------------------------------------------------------------- verdicts per side kind
def m0_commit_trace(rfacts: dict, version: int) -> list[dict]:
    """The commit-path trace of an M0 codec witness: from s0, an active sequencer commits batch 1 at
    the witness's version, with one blob (version 2 requires at least one)."""
    init = rfacts["initial"]
    prev = init["fsr"][0]
    return [{"op": "commitBatch", "who": init["active"][0], "ver": version, "parent": 0, "n": 0, "lbn": 1,
             "prev": prev, "post": prev + 10, "blobs": [17]}]


def m0_commit(side: dict, law: dict, witness: dict, hfacts: dict, rfacts: dict | None = None) -> tuple[str, str]:
    expect, go_fn, version = m0_expected_cells(law, witness, hfacts)
    if rfacts is not None and side.get("trace") != m0_commit_trace(rfacts, version):
        return CONTRADICTION, "the replayed trace is not the commit-path trace the witness's version gives"
    hb = hexb(side.get("header"))
    if hb is None:
        return NOT_OBSERVED, "no committed header logged"
    if not _preimage_ok(side.get("header"), side.get("committed_hash")):
        return CONTRADICTION, "keccak256(header) != the committedBatches value read on chain"
    tr = side.get("trace") or [{}]
    if tr[-1].get("ver") != version:
        return CONTRADICTION, f"the trace commits at version {tr[-1].get('ver')}, the witness pins {version}"
    cells = sorted(expect)
    if any(expect[i] is not None and (i >= len(hb) or hb[i] != expect[i]) for i in cells):
        return CONTRADICTION, f"committed header bytes {ranges(cells)} are not what the model's enc_sol writes"
    if cells and all(expect[i] is not None for i in cells):
        return OBSERVED, f"committed header bytes {ranges(cells)} are what the model's enc_sol writes ({go_fn} differs)"
    return NOT_OBSERVED, "the model's enc_sol writes no pinned value at the differing cells"


def ghost_tag(side: dict) -> tuple[str, str]:
    h, v1 = hexb(side.get("header")), hexb(side.get("v1_header"))
    vh = hexb(side.get("stored_vh"))
    if h is None or v1 is None or vh is None:
        return NOT_OBSERVED, "the ghost-tagged header and the header that stored the hash were not both logged"
    if not _preimage_ok(side.get("header"), side.get("committed_hash")) or \
            not _preimage_ok(side.get("v1_header"), side.get("v1_committed_hash")):
        return CONTRADICTION, "a logged header is not the preimage of the committedBatches value read on chain"
    if len(h) >= 89 and len(v1) >= 89 and h[0] >= 2 and v1[0] < 2 and h[57:89] == v1[57:89] == vh:
        return OBSERVED, (f"the version-{h[0]} header carries at [57:89] the blob hash the version-{v1[0]} commit stored")
    return CONTRADICTION, "the committed headers do not carry the ghost tag the witness predicts"


def same_commitment(side: dict) -> tuple[str, str]:
    ch = side.get("committed_hash") or {}
    if not isinstance(ch, dict) or not ch.get("c1") or not ch.get("c2"):
        return NOT_OBSERVED, "a commit did not succeed on chain"
    if side.get("parent_header") is not None and \
            not _preimage_ok(side.get("parent_header"), side.get("parent_committed_hash")):
        return CONTRADICTION, "the logged parent header is not the preimage of committedBatches(parent)"
    if ch["c1"] == ch["c2"]:
        return OBSERVED, "committedBatches is equal after the two commits"
    return CONTRADICTION, "committedBatches differs although the witness predicts equal commitments"


def differ(entry: dict) -> tuple[str, str]:
    ts = {t.get("label"): t for t in entry.get("traces", [])}
    a, b = ts.get("lhs"), ts.get("rhs")
    if not a or not b or not isinstance(a.get("split"), int) or not isinstance(b.get("split"), int):
        return NOT_OBSERVED, "the two traces or their split points are missing"
    if a["real"][a["split"]:] != b["real"][b["split"]:]:
        return OBSERVED, "the continuations' real outcomes differ"
    return NOT_OBSERVED, "the continuations' real outcomes agree"


def symptom(entry: dict, law: dict, rfacts: dict) -> tuple[str, str]:
    ts = entry.get("traces") or []
    if len(ts) != 1 or not ts[0].get("real"):
        return NOT_OBSERVED, "no trace"
    want = "rev " + rfacts["reasons"][str(law["statement"]["claim"]["eq"][0]["args"][1]["nat"])]
    last = ts[0]["real"][-1]
    return (OBSERVED, f"the last step reverts with {want[4:]!r}") if last == want else \
        (NOT_OBSERVED, f"the last step gives {last!r}, not {want!r}")


def own_go(side: dict) -> tuple[str, str]:
    return (OBSERVED, "the held view changed across Append") if "changed=true" in str(side.get("observed", "")) \
        else (NOT_OBSERVED, "the held view did not change")


def tag_consumer(side: dict, sol: dict) -> tuple[str, str]:
    """Go read both committed headers: the v2 one through BlobCommitHash (BlobHashesHash) and the v1
    one through BlobCommitHash (BlobVersionedHash). Observed when Go returns, for the v2 header, the
    hash a version-1 commit stored, and the aggregate a v2 consumer would expect over that hash differs.
    The inequality itself is HOLON's comparison: no Morph consumer decision is exercised."""
    h, v1 = hexb(sol.get("header")), hexb(sol.get("v1_header"))
    if h is None or v1 is None:
        return NOT_OBSERVED, "the chain replay logged no headers to compare with"
    if side.get("input_header") != sol.get("header") or side.get("input_v1_header") != sol.get("v1_header"):
        return CONTRADICTION, "the consumer did not read the headers the chain replay committed"
    if (side.get("version") != h[0] or side.get("v1_version") != v1[0]
            or hexb(side.get("blob_commit_hash")) != h[57:89] or hexb(side.get("v1_blob_commit_hash")) != v1[57:89]):
        return CONTRADICTION, "Go reads the committed headers differently from the chain replay"
    from .keccak import keccak256
    vh = hexb(side.get("input_stored_vh"))
    if side.get("input_stored_vh") != sol.get("stored_vh") or vh is None or \
            hexb(side.get("aggregate")) != keccak256(vh):
        return CONTRADICTION, "the aggregate is not keccak256 of the stored hash the chain replay logged"
    if side["version"] >= 2 > side["v1_version"] and side["blob_commit_hash"] == side["v1_blob_commit_hash"] \
            and side.get("aggregate") and side["aggregate"] != side["blob_commit_hash"]:
        return OBSERVED, "Go returns the v1-stored hash for the v2 header, and the v2 aggregate over it differs"
    return NOT_OBSERVED, "Go does not return a v1-stored hash where the v2 aggregate is expected"


def outcome_class(outcome: str) -> str:
    if outcome == "ok":
        return "accepted"
    if str(outcome).startswith("panic"):
        return "panic"
    return "rejected"


def fact_consumer(side: dict, sol: dict) -> tuple[str, str]:
    """Derivation's verdict on the two equal-commitment batches. Observed only when the outcome
    classes differ (accepted, rejected, panic): two rejections with different messages are the same
    derivation behaviour (log the error and stop at that batch), not a divergence."""
    ph = hexb(sol.get("parent_header"))
    if ph is None or len(ph) < 9 or not isinstance(sol.get("parent_index"), int):
        return CONTRADICTION, "the chain replay logged no parent header and index to feed the consumer"
    if side.get("input_parent_header") != sol.get("parent_header"):
        return CONTRADICTION, "the consumer was not fed the parent header the chain replay committed on"
    if not (side.get("parent_index") == sol.get("parent_index") == int.from_bytes(ph[1:9], "big")):
        return CONTRADICTION, "Go, the chain replay and the parent header bytes disagree on the parent's batch index"
    outs = side.get("outcomes") or {}
    if set(outs) != {"c1", "c2"}:
        return NOT_OBSERVED, "ParseBatch did not report both batches"
    oc = {k: outcome_class(v) for k, v in outs.items()}
    if side.get("outcome_class") != oc:
        return CONTRADICTION, "the recorded outcome classes are not the classes of the logged outcomes"
    if oc["c1"] != oc["c2"]:
        return OBSERVED, f"derivation outcome classes differ: {oc['c1']} vs {oc['c2']}"
    return NOT_OBSERVED, (f"derivation {oc['c1']} both batches (messages: {side.get('outcomes', {}).get('c1')!r} vs "
                          f"{side.get('outcomes', {}).get('c2')!r}); no divergence in what derivation does")


def verdict(law: dict, side_name: str, side: dict, entry: dict, witness: dict | None,
            hfacts: dict | None, rfacts: dict | None) -> tuple[str | None, str]:
    """The observation a side's logged evidence supports (see the module docstring)."""
    kind = claim_kind(law)
    if law.get("ir_version") == "holon-ir/0.1":
        if side_name == "solidity" and kind == "codec":
            return m0_commit(side, law, witness, hfacts, rfacts)
        return None, "the harness passes exactly when the half-obstruction shows"
    if side_name == "go":
        return own_go(side)
    sides = entry.get("sides") or {}
    if side_name == "go_consumer":
        sol = sides.get("solidity") or {}
        if kind == "accepted":
            return tag_consumer(side, sol)
        if kind == "same_commitment":
            return fact_consumer(side, sol)
        return None, "no consumer rule"
    if kind == "differ":
        return differ(entry)
    if kind == "symptom":
        return symptom(entry, law, rfacts)
    if kind == "accepted":
        return ghost_tag(side)
    if kind == "same_commitment":
        return same_commitment(side)
    return None, "no rule for this claim"
