"""S4 link-history frontend.

Extracts, from the morph checkout and the recorded on-chain deployment data:

* cross-language linking facts (``links.json``):
    - shared constants between the Solidity L1 contracts and the Go node
      (header lengths, header versions, ZERO_VERSIONED_HASH / EmptyVersionedHash,
      blob payload capacity, per-field wire offsets),
    - ABI bindings (the ABI JSON embedded in the generated Go bindings versus
      the ABI of the deployed implementation, reported by Sourcify),
    - event schemas for the in-scope contracts;
* deployment history (``migrations.json``, whitepaper 10.1 input for M3 NAT):
    - every ``Upgraded`` event of the Morph mainnet L1 Rollup proxy and the
      L1MessageQueueWithGasPriceOracle proxy, with block number, tx hash and
      log index,
    - the reinitializer call bundled with each upgrade (initialize/
      initialize2/initialize3/initialize4, decoded, with the reinitializer
      version),
    - verified-source details and storage-layout diffs between successive
      implementations.

Everything the extractors emit is a function of the pinned morph commit and
the recorded chain/sourcify inputs, so the committed JSON is byte-identical
across runs (sorted keys, sorted lists, no timestamps).
"""

__all__ = ["keccak", "abi", "layout", "consts", "gobind", "chain", "links", "migrations"]
