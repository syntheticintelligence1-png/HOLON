"""Registry of cross-language constants for the link frontend.

Each entry names one constant that the M0 wire codec or the M1 Rollup model
depends on, with a mechanical extractor per language: (repo-relative file,
regex). The extractor captures the literal, the extractor compares it to the
expected value, and the link is only emitted as `linked` when every side that
exists agrees. One-sided constants are recorded with their side and reason —
never approximated into a shared value.
"""

import re

# Each extractor: {"file": repo-relative path, "pattern": regex with one group
# capturing the literal (and a `symbol` group when the pattern names it)}.
REGISTRY = [
    {
        "id": "batch_header_v0_length",
        "doc": "byte length of a v0 batch header (fact: enc.len)",
        "value": 249,
        "go": [
            {"file": "common/batch/batch_header.go",
             "pattern": r"expectedLengthV0\s*=\s*(\d+)", "symbol": "expectedLengthV0"},
        ],
        "solidity": [
            {"file": "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
             "pattern": r"BATCH_HEADER_LENGTH\s*=\s*(\d+)", "symbol": "BATCH_HEADER_LENGTH"},
        ],
    },
    {
        "id": "batch_header_v1_length",
        "doc": "byte length of a v1 batch header (adds lastBlockNumber)",
        "value": 257,
        "go": [
            {"file": "common/batch/batch_header.go",
             "pattern": r"expectedLengthV1\s*=\s*(\d+)", "symbol": "expectedLengthV1"},
        ],
        "solidity": [
            {"file": "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol",
             "pattern": r"BATCH_HEADER_LENGTH\s*=\s*(\d+)", "symbol": "BATCH_HEADER_LENGTH"},
        ],
    },
    {
        "id": "batch_header_v2_length",
        "doc": "byte length of a v2 batch header (reuses the v1 wire format; "
               "the 32-byte field at offset 57 becomes an aggregate hash)",
        "value": 257,
        "go": [
            {"file": "common/batch/batch_header.go",
             "pattern": r"expectedLengthV2\s*=\s*(\d+)", "symbol": "expectedLengthV2"},
        ],
        "solidity": [
            {"file": "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol",
             "pattern": r"BATCH_HEADER_LENGTH\s*=\s*(\d+)", "symbol": "BATCH_HEADER_LENGTH"},
        ],
        "note": "v2 has no dedicated codec library; the contract decodes v2 "
                "headers through the v1 codec (257 bytes) and interprets "
                "offset 57 differently",
    },
    {
        "id": "batch_header_max_version",
        "doc": "largest batch header version accepted on-chain",
        "value": 2,
        "go": [
            {"file": "common/batch/batch_header.go",
             "pattern": r"BatchHeaderVersion2\s*=\s*(\d+)", "symbol": "BatchHeaderVersion2"},
        ],
        "solidity": [
            {"file": "contracts/contracts/l1/rollup/Rollup.sol",
             "pattern": r"batchDataInput\.version\s*<=\s*(\d+)", "symbol": "version<=2 check"},
        ],
    },
    {
        "id": "zero_versioned_hash",
        "doc": "versioned hash of the all-zero blob: 0x01 || sha256(0xc0 || 0^47)[1:]",
        "value": "0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014",
        "go": [
            {"file": "common/blob/payload.go",
             "pattern": r"EmptyVersionedHash\s*=\s*common\.HexToHash\(\"(0x[0-9a-fA-F]+)\"\)",
             "symbol": "EmptyVersionedHash"},
        ],
        "solidity": [
            {"file": "contracts/contracts/l1/rollup/Rollup.sol",
             "pattern": r"ZERO_VERSIONED_HASH\s*=\s*(0x[0-9a-fA-F]+)", "symbol": "ZERO_VERSIONED_HASH"},
        ],
    },
    {
        "id": "blob_payload_bytes",
        "doc": "EIP-4844 blob payload capacity: 4096 field elements x 31 bytes",
        "value": 126976,
        "expression": "4096 * 31",
        "go": [
            {"file": "common/batch/blob.go",
             "pattern": r"MaxBlobBytesSize\s*=\s*(4096\s*\*\s*31)", "symbol": "MaxBlobBytesSize"},
            {"file": "common/blob/payload.go",
             "pattern": r"MaxBlobBytesSize\s*=\s*(4096\s*\*\s*31)", "symbol": "MaxBlobBytesSize"},
        ],
        "solidity": [],
        "side": "go",
        "reason": "payload capacity is only meaningful off-chain; on-chain the "
                  "contract sees blobhash commitments, not blob bytes",
    },
    {
        "id": "replay_protocol_max_blobs",
        "doc": "per-transaction blob ceiling used when re-sealing replayed batches",
        "value": 6,
        "go": [
            {"file": "common/batch/batch_cache.go",
             "pattern": r"replayProtocolMaxBlobs\s*=\s*(\d+)", "symbol": "replayProtocolMaxBlobs"},
        ],
        "solidity": [],
        "side": "go",
        "reason": "replay-time protocol cap; the contract bounds blobs per commit "
                  "through calldata/blobhash presence, not this constant",
    },
    {
        "id": "sequencer_set_verify_hash_write",
        "doc": "the contract writes a constant zero into the sequencerSetVerifyHash "
               "field at offset 185 (fact: enc_sol zero-write; the M0 equality law "
               "was refuted because Go copies the producer's field)",
        "value": "0x" + "00" * 32,
        "go": [
            {"file": "common/batch/batch_header.go",
             "pattern": r"copy\(batchBytes\[185:\],\s*b\.SequencerSetVerifyHash\[:\]\)",
             "symbol": "SequencerSetVerifyHash copy",
             "literal": "0x" + "00" * 32, "literal_doc": "field copied verbatim; "
             "producers must supply zero for the encodings to agree"},
        ],
        "solidity": [
            {"file": "contracts/contracts/l1/rollup/Rollup.sol",
             "pattern": r"storeSequencerSetVerifyHash\(_batchPtr,\s*bytes32\(0\)\)",
             "symbol": "bytes32(0) write", "literal": "0x" + "00" * 32},
        ],
        "linked": "asymmetric",
        "note": "Solidity emits the constant bytes32(0); Go copies the header field. "
                "The agreement condition (producer writes zero) is an M0 refutation "
                "witness, recorded here as an asymmetric link rather than an equality.",
    },
]


def _extract_from_file(repo, rel, spec):
    path = repo / rel
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    rx = re.compile(spec["pattern"])
    for lineno, line in enumerate(text.splitlines(), 1):
        m = rx.search(line)
        if m:
            if "literal" in spec:
                value = spec["literal"]
            elif m.groups():
                lit = m.group(1)
                value = lit if lit.startswith("0x") or "*" in lit or not lit.isdigit() else int(lit)
            else:
                value = None
            return {"file": rel, "line": lineno, "symbol": spec.get("symbol", ""),
                    "code": line.strip(), "value": value}
    return None


def _norm(value):
    if isinstance(value, str) and "*" in value:
        return eval(value)  # noqa: S307 - trusted literal "4096 * 31" from registry
    if isinstance(value, str) and value.startswith("0x"):
        return value.lower()
    return value


def extract_constants(repo):
    """Run the registry against the morph checkout.

    Returns a list of constant records; `linked` is True only when every side
    present in the registry produced the expected value. A side listed in the
    registry whose extractor finds nothing produces a `missing` marker which
    callers surface as coverage debt.
    """
    out = []
    for c in REGISTRY:
        sides = {}
        missing = []
        for lang in ("go", "solidity"):
            cites = []
            for spec in c.get(lang, []):
                hit = _extract_from_file(repo, spec["file"], spec)
                if hit is None:
                    missing.append({"lang": lang, "file": spec["file"], "symbol": spec.get("symbol")})
                else:
                    cites.append(hit)
            sides[lang] = cites
        if "side" in c:  # declared one-sided
            linked = "one_sided"
        elif c.get("linked"):
            linked = c["linked"]
        else:
            linked = bool(sides["go"] and sides["solidity"]) and not missing
        agreed = all(_norm(s["value"]) == _norm(c["value"]) for lang in ("go", "solidity")
                     for s in sides[lang] if s.get("value") is not None) if linked is True else None
        if linked is True and not agreed:
            linked = "value_mismatch"
        rec = {
            "id": c["id"],
            "doc": c["doc"],
            "value": c["value"],
            "linked": linked,
            "go": sides["go"],
            "solidity": sides["solidity"],
        }
        if "expression" in c:
            rec["expression"] = c["expression"]
        if "note" in c:
            rec["note"] = c["note"]
        if "reason" in c:
            rec["reason"] = c["reason"]
        if missing:
            rec["missing"] = missing
        out.append(rec)
    return out
