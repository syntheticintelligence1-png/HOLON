# across-protocol/contracts: a transition-system analysis by claim-key decomposition

| | |
|---|---|
| Target | `across-protocol/contracts` @ `b1c4e86225420df5cb8d03042526622aca80fe61` (2026-10-21, package 5.0.27) |
| Core analyzed in full | `HubPool.sol`, `SpokePool.sol`, `MerkleLib.sol`, every `*_SpokePool.sol`, `HubPoolStore.sol`, `Universal_Adapter.sol`, `Ethereum_Adapter.sol`, `BondToken.sol`, `SP1Helios.sol`, `programs/svm-spoke` |
| Live parameters | Ethereum mainnet, block 26259843 (read with `cast` and Blockscout) |
| Artifacts | `model/` (abstract models, exhaustive BFS, code-site audit), `replay/` (Foundry replays on the unmodified contracts) |

Line references are `file:line` at the target commit. `HubPool` = `contracts/hub-pool/HubPool.sol`, `SpokePool` = `contracts/spoke-pools/SpokePool.sol`, `svm/` = `programs/svm-spoke/src/`.

## Summary

1. **Core safety under production conditions.** Production conditions means the live parameters at block 26259843 plus the operational conventions stated in §4. Under them, no counterexample was found for these core safety invariants:
   - fill-once on EVM (F1);
   - refund-once (R1), given bundle validity, and on Universal/Tron chains also A_exec and A_inst;
   - LP equity, rate monotonicity and donation neutrality (L1, L5, L6);
   - window disjointness (H1);
   - principal authority on native-bridge spokes (A1).

   Each has a computed **minimal assumption set** (§6, §8). F1 (EVM), L5, L6 and H1 need **none**.
2. **One refinement gap is realized live: L7 (G7).** LP-fee smearing starts at the last pool interaction rather than at fee allocation. With the live `liveness = 1800 s`, at least 0.27% of each bundle's LP fees, and up to 100%, become claimable in the block they are allocated. Replay: T02.
3. **Conditional counterexamples, all replayed on the unmodified contracts.** Each needs a specific assumption to fail; §4 says who enforces each one.

   | Invariant broken | Failing assumption(s) | Replay |
   |---|---|---|
   | R1 (double refund) | bundle validity (A_V1) | T03 |
   | R1 (double refund), Universal/Tron | caller uniformity (A_exec) | T04 |
   | R1 (double refund), Universal/Tron | single instance per chain (A_inst) | T06 |
   | R2 (deletion not enforced), Universal/Tron | none: fails under all knob subsets | T05 |
   | C1 (admin reorder), Universal | FIFO delivery (A_fifo) | T07 |
   | A1 (upgrade by callee), Polygon/Universal/Tron | closed callees (A_closed) | T08 |
   | H3 (dispute becomes free cancel), with UMA's deployed oracle code | proposer whitelist, same-block timing, UMA parameters (A_wl, A_hblk, A_ff, A_ooOK) | T09 |
   | L2/L4 (unbacked reserves, exit blocked at 0% utilization) | `protocolFeeCapturePct = 0` (A_pct0) | T01 |
   | H4 (permanent hub stop) | both A_bondNotPooled and A_pct0 | T10 |
4. **Key-scope asymmetry.** One duplicated root pays its slow-fill leaf once and its refund leaf twice (T03). Slow fills are keyed by relay hash (scope: spoke); refunds are keyed by `(rootBundleId, leafId)` (scope: root copy). The Universal store's nonce dedup **removes** the dependence of R1 on A_V1 and **adds** A_exec and A_inst. This shift came out of the minimal-set computation.
5. **SVM spoke versus EVM spoke.** These are two implementations of one abstract spoke. Divergences:
   - fill-key resurrection via `close_fill_pda`, safe only under A_clk;
   - unsafe-deposit ids not bound to the depositor's authorization;
   - executor-chosen refund deferral;
   - a second admin principal (the local owner) that can relay roots without the HubPool.

   These are derived from code and checked in the model. They were not executed: no Solana toolchain was available in this environment.

## 0. Method and evidence levels

Each claim is backed by one or more of three checks. The three checks fail in different ways.

1. **Code-site audit** (`model/sites.py` → `model/sites.md`). It lists every site that writes guarded state or consumes a replay key, for example every write to `fillStatuses`, `liquidReserves`, `utilizedReserves`, `undistributedLpFees` and `unclaimedAccumulatedProtocolFees`, and every `bondToken` transfer. It exits non-zero if the code has a site the abstract model does not represent. Every check passes at `b1c4e86`.
2. **Layered abstract models** (`model/layers.py`, `model/engine.py` → `model/results.{md,json}`). The models are eight finite projections of the system. Each environmental assumption is an explicit knob. The engine searches every reachable state breadth-first, so each counterexample it reports is a shortest one. It checks all 2^k knob subsets, which yields the minimal assumption sets under which each invariant holds. The output is deterministic: actions are explored in sorted order, and there are no timestamps or random seeds.
3. **Concrete replay** (`replay/`, Foundry 1.7.1, solc 0.8.30, via-IR as in the repository). Each abstract counterexample that has an EVM realization runs on the **unmodified** contracts. Only external infrastructure is substituted:
   - UMA Finder, Store, whitelists and DVM are stubs, with ABIs that match the deployed contracts.
   - The SP1 zk verifier is Succinct's upstream mock.
   - The SkinnyOptimisticOracle is the verbatim Etherscan-verified mainnet source (sha256 in `replay/uma.sha256`).
   - `SP1Helios` is the repository's own contract.

   A canary (`C11`) must fail, and does, to show that the fuzz campaign `T11` is not vacuous.

| Label | Meaning |
|---|---|
| **REFUTED/C** | Counterexample executed on the real contracts (`replay/test/T*.t.sol`, all PASS) |
| **REFUTED/A** | Counterexample in the abstract model only. These are the SVM items: no Solana toolchain was available in this environment. |
| **HOLDS/M** | No counterexample in the exhaustive abstract model, plus an inductive argument over the audited write sites |
| **HOLDS/M+F** | HOLDS/M, plus a stateful fuzz campaign on the real code, plus a non-vacuity canary |

"Holds" is relative to the stated assumption set and to the model's abstraction function (§5.3). It is not a proof about the bytecode.

## 1. State space

### 1.1 The decomposition: claim keys, scopes and binding maps

Most outflows of value in the protocol consume a **key** in some **key space**. A key is only meaningful relative to the **scope** that stores its consumed bit, meaning the storage instance that holds it. For each economic **obligation** `o` (a deposit, a refund entitlement, a slow-fill entitlement, a bond, an admin intent), the **binding map** `β(o) ⊆ K × Σ` is the set of (key, scope) pairs whose consumption discharges `o`.

**Safety schema.** For every obligation `o`, `payouts(o) ≤ |{(k, σ) ∈ β(o) : k consumed in σ}|`. Hence `payouts(o) ≤ 1` and only valid obligations pay if all three conditions hold:

- **(S1) No resurrection:** every consumed set is monotone.
- **(S2) No duplication:** `|β(o)| ≤ 1` for every reachable `o`.
- **(S3) Sound attestation:** `β(o) ≠ ∅` only for valid `o`.

**Liveness dual:**

- **(Λ1) No collision:** distinct obligations get distinct, consumable keys.
- **(Λ2)** Channels eventually deliver.

**Ledgers** are handled by place-invariants (P-invariants) over integer state. **Authority** is a predicate over call frames. **Channels** are characterized by order, loss and replay scope.

Every counterexample in §6 fits one cell of this table:

| Class | Formal shape | Instances (§6) |
|---|---|---|
| Duplication | `∃o. \|β(o)\| ≥ 2` (one obligation, several scopes or keys) | R1 native via duplicate groupIndex-0 leaves or re-proposal; R1 Universal via dual store or a second instance |
| Resurrection | a consumed key returns to unconsumed | F1 on SVM (`close_fill_pda` plus a non-monotone clock) |
| Collision | `∃o≠o'. β(o) ∩ β(o') ≠ ∅` | H3 (UMA request id per block); unsafe-deposit id reuse (documented) |
| Revocation failure | `β(o)` survives the issuer's revocation | R2 Universal (deleted bundle still importable) |
| Ambient authority | authority predicate not bound to the principal of the frame | A1 on Polygon, Universal and Tron |
| Order | channel not FIFO | C1 on Universal and CCTP→SVM |
| P-invariant break | a transition changes a conserved sum | L2, L4, H4 |

Key spaces present in the code:

| Key space | Key | Scope (where the consumed bit lives) | Consumption / guard | Code |
|---|---|---|---|---|
| `K_fill` (EVM) | `relayHash = keccak(abi.encode(relayData, chainId()))` | one SpokePool proxy | `fillStatuses[h]`: U→R iff U; ¬F→F | `SpokePool:122, 1171-1172, 1739-1740, 1375-1377` |
| `K_fill` (SVM) | Borsh(relay_data with message replaced by its hash) ‖ chain_id | PDA `["fills", h]` | status; **account closable** after the deadline | `svm/instructions/fill.rs:68-83, 216-226`; `svm/utils/merkle_proof_utils.rs` `get_relay_hash` |
| `K_ref` (EVM) | `(rootBundleId, leafId)` | SpokePool proxy, `rootBundles[i].claimedBitmap` | `MerkleLib.setClaimed` | `SpokePool:1550-1558` |
| `K_ref` (SVM) | `(root_bundle_id, leaf_id)` | PDA `["root_bundle", seed, id]` | `set_claimed` | `svm/instructions/bundle.rs:124-128` |
| `K_hub` | `(proposal instance, leafId ∈ [0,255])` | `rootBundleProposal.claimedBitMap` (reset by delete) | `setClaimed1D` | `HubPool:625, 650, 573` |
| `K_msg` (Universal, Tron) | HubPoolStore nonce | Universal_SpokePool **instance** (`executedMessages`) | 1 bit per nonce | `Universal_SpokePool.sol:151-154`; `HubPoolStore.sol:55-79` |
| `K_msg` (SVM) | CCTP (source domain, nonce) | Circle MessageTransmitter | used-nonce set; **no order** | `svm/instructions/handle_receive_message.rs:46-53` |
| `K_oo` | `(requester, identifier, timestamp, ancillaryData)` | UMA SkinnyOptimisticOracle | `"Request already initialized"` | mainnet SkinnyOO source l.2913-2914; HubPool passes `(identifier, now, "")` at `HubPool:747-750` |
| `K_claim` | `(token, relayer)` | `relayerRefund` mapping (EVM), `ClaimAccount` PDA (SVM) | zeroed / closed on claim | `SpokePool:1324-1331`; `svm/instructions/refund_claims.rs:92-122` |
| `K_dlg` (SVM) | delegate PDA `["delegate", keccak(Borsh(params))]` | SPL delegation on the depositor's ATA | consumed by `transfer_checked` | `svm/utils/delegate_utils.rs:10-23`; `svm/instructions/deposit.rs:112-120` |

### 1.2 HubPool (Ethereum), persistent state (`HubPool:47-100`, `HubPoolInterface.sol:53-93`)

| Variable | Type / domain | Initial | Mutated by |
|---|---|---|---|
| `rootBundleProposal` | `(poolRebalanceRoot, relayerRefundRoot, slowRelayRoot : bytes32, claimedBitMap : 2^[0,255], proposer : address, unclaimedPoolRebalanceLeafCount : uint8, challengePeriodEndTimestamp : uint32)` | all zero | propose, execute, dispute, cancel, emergency delete |
| `pooledTokens[t]` | `(lpToken : address, isEnabled : bool, lastLpFeeUpdate : uint32, utilizedReserves U : int256, liquidReserves L : uint256, undistributedLpFees F : uint256)` | zero | enable/disable, add/remove liquidity, execute, sync, accrual, haircut |
| `poolRebalanceRoutes[keccak(t, chainId)]` | address | 0 | owner |
| `crossChainContracts[chainId]` | `(adapter, spokePool)` | 0 | owner |
| `unclaimedAccumulatedProtocolFees[t]` (P) | uint256 | 0 | execute (+), claim (:= 0) |
| `paused` | bool | false | owner |
| `protocolFeeCaptureAddress`, `protocolFeeCapturePct` | address, uint256 ≤ 1e18 | owner, 0 | owner. **Live: pct = 0.** |
| `bondToken`, `bondAmount` | IERC20, uint256 | 0, 0 | owner, only while idle. **Live: ABT `0xee1D…02ea`, 0.45e18.** |
| `liveness` | uint32 > 600 | 7200 | owner, at any time. **Live: 1800.** |
| `identifier` | bytes32 | "ACROSS-V2" | owner, only while idle |
| `lpFeeRatePerSecond` | uint256 | 1.5e12 | not settable. **Live: 1.5e12** (full release after 1/1.5e-6 s ≈ 7.72 d) |
| `owner` (Ownable) | address | deployer | **Live:** `0xB524…3715`, a 171-byte proxy (Safe) |
| immutables | `weth, lpTokenFactory, finder, timer` | — | — |
| *external state read as state* | `balanceOf(HubPool)` per token (B); LP `totalSupply` (S); UMA `Store.finalFee`, OO request map, Finder entries | — | tokens, bridges, UMA governance |

Live instance at block 26259843: a proposal with `unclaimedPoolRebalanceLeafCount = 17` and `challengePeriodEndTimestamp = 1792814519`. UMA final fee for ABT is 0.055e18 < `bondAmount`. Finder → SkinnyOptimisticOracle `0xeE3A…c24`.

### 1.3 SpokePool, EVM base and variants, persistent state (`SpokePool:61-129`, variants)

| Variable | Type / domain | Initial | Mutated by |
|---|---|---|---|
| `crossDomainAdmin`, `withdrawalRecipient` | address ≠ 0 | init args | admin |
| `numberOfDeposits` | uint32, checked `++` (reverts at 2^32 − 1) | `_initialDepositId` | `deposit` |
| `pausedDeposits`, `pausedFills` | bool | false | admin |
| `rootBundles[]` | list of `(slowRelayRoot, relayerRefundRoot, claimedBitmap : ℕ → 2^256)` | [] | `relayRootBundle` (push), `emergencyDeleteRootBundle` (zeroes roots, **keeps** the bitmap) |
| `fillStatuses[h]` | {0=Unfilled, 1=RequestedSlowFill, 2=Filled} | 0 | `requestSlowFill`, `_fillRelay` |
| `relayerRefund[token][addr]` | uint256 | 0 | refund execution (+ on failed transfer), `claimRelayerRefund` (:= 0) |
| `oftMessengers[token]` | address | 0 | admin |
| ERC1967 implementation slot | address | impl | `upgradeTo*` via `_authorizeUpgrade` (onlyAdmin) |
| Arbitrum | `l2GatewayRouter, whitelistedTokens` | | admin |
| Ovm/OP/Lisk/Cher | `l1Gas, tokenBridges, remoteL1Tokens, l2Eth` | | admin |
| Polygon | `fxChild, polygonTokenBridger, callValidated : bool` | | admin; `callValidated` is set only inside `processMessageFromRoot` |
| Universal/Tron | `executedMessages[nonce] : bool, _adminCallValidated : bool, owner` | | `executeMessage`, `adminExecuteMessage` |
| immutables | `wrappedNativeToken, depositQuoteTimeBuffer, fillDeadlineBuffer, gateway`, OFT/CCTP params; Universal: `helios, hubPoolStore, ADMIN_UPDATE_BUFFER` | — | — |
| *external state* | token balances of the spoke (Σ); Gateway transient context (V5) | | |

### 1.4 HubPoolStore (Ethereum) and SP1Helios (destination), persistent state

| Variable | Type | Mutated by |
|---|---|---|
| `HubPoolStore.relayMessageCallData[nonce]` | bytes32 = `keccak(abi.encode(target, data))`, write-once | HubPool only (`HubPoolStore.sol:55-79`) |
| `HubPoolStore.dataUuid` | uint256 counter (admin nonces 0, 1, …) | owner-originated relays |
| `SP1Helios.storageValues[keccak(head, contract, slot)]` | bytes32, kept forever | `update`, which requires `STATE_UPDATER_ROLE` (`SP1Helios.sol` `update`) |

### 1.5 SVM spoke, persistent accounts (`svm/state/*.rs`)

| Account (seeds) | Fields | Lifecycle |
|---|---|---|
| `State ["state", seed]` | `paused_deposits, paused_fills, owner, seed, number_of_deposits:u32, chain_id:u64, current_time:u32 (test builds only), remote_domain, cross_domain_admin, root_bundle_id:u32, deposit_quote_time_buffer, fill_deadline_buffer` | `initialize` (once) |
| `RootBundle ["root_bundle", seed, id]` | `relayer_refund_root, slow_relay_root, claimed_bitmap: Vec<u8>` (realloc grows) | created by `relay_root_bundle`, **closed** by `emergency_delete_root_bundle` |
| `FillStatusAccount ["fills", h]` | `status, relayer, fill_deadline` | `init_if_needed` by fill / slow-fill request; **closed** by `close_fill_pda` |
| `ClaimAccount ["claim_account", mint, addr]` | `amount, initializer` | init by anyone; closed on claim |
| `TransferLiability ["transfer_liability", mint]` | `pending_to_hub_pool:u64` | + on refund leaf, − on `bridge_tokens_to_hub_pool` |
| `instruction_params ["instruction_params", signer]` | raw buffer | written over several transactions, consumed and closed by the target instruction |
| vault ATA (authority = State); SPL delegations to delegate PDAs | token amounts | deposits, fills, refunds, bridging |

### 1.6 Transient state

These values are non-default only within one transaction or call frame:

- reentrancy flags (`Lockable` in HubPool, `ReentrancyGuardUpgradeable` in SpokePool);
- `callValidated` on Polygon and `_adminCallValidated` on Universal and Tron. Both are storage-backed but restored before the admin frame returns;
- the bond-token allowance to the OO (`zeroOptimisticOracleApproval`, `HubPool:185-188`);
- Gateway execution context (`IGateway.currentStepId/currentSubmitter/currentExecutor`, EIP-1153 transient storage on the Gateway);
- `msg.value` routed to OFT/Linea fees;
- in-memory `V3RelayExecutionParams`.

### 1.7 Environment and ghost state (not stored by the contracts, needed to state the specification)

- **Per-chain clocks** `now_c`.
- **Cross-domain message queues** `Q_c` per destination. Per channel: order, loss and replay scope (§4).
- **Bridge token queues** (L1→L2 sends, L2→L1 returns): `Out` = tokens on spokes owed to the hub, `Arr` = in flight.
- **Bundle validity predicate `V`**, the off-chain UMIP rule, evaluated by disputers.
- **UMA DVM.**
- **Permissioned Helios updater:** which slots get proven, and when.
- **Ghost obligations Ω** with binding maps `β` (§1.1).

## 2. Actions

Every on-chain action is an **atomic** transaction step. A failed guard aborts the step, so a revert is an absent transition. Cross-chain effects are **separate, interleaved** actions: message delivery, bridge arrival, light-client update. "Ext" marks steps that call an untrusted or external contract mid-step, where reentrancy and callbacks are possible.

### 2.1 HubPool

| Action | Guard (pre) | Effect (post) | Shared state / Ext | Code |
|---|---|---|---|---|
| `proposeRootBundle(bebn, n, prR, rrR, slR)` | ¬paused ∧ count = 0 ∧ n > 0 ∧ bond transfer succeeds. With ABT, the bond transfer requires `proposers[msg.sender]`. | proposal := (roots, bitmap 0, proposer, n, end = now + liveness); bond += bondAmount | Ext: `bondToken.transferFrom` | `HubPool:560-594`; `BondToken.sol:74-79` |
| `executeRootBundle(leaf, proof)` | ¬paused ∧ now > end ∧ bit[leafId] = 0 ∧ proof ∈ prR ∧ adapter has code ∧ spoke ≠ 0 ∧ ∀i: route(t_i, chain) ≠ 0 ∧ count > 0 | bit := 1; count −= 1; ∀i with netSend_i > 0: adapter.relayTokens (delegatecall), U += n_i, L −= n_i (checked); fees: F += lp_i, U += lp_i, P += p_i; if groupIndex = 0: adapter.relayMessage(spoke, relayRootBundle(rrR, slR)); if count = 0: refund bond | Ext: delegatecall to adapter (bridge calls); Universal: HubPoolStore write | `HubPool:612-707, 866-918, 995-1011` |
| `disputeRootBundle()` | now ≤ end. The proposal is not required to exist: with end = 0 the guard fails. | if finalFee ≥ bondAmount ∨ OO request reverts: **cancel** (bond → proposer, delete). Otherwise: OO request + proposal (proposer bond → OO), delete, pull disputer bond, `disputePriceFor` | Ext: UMA OO (try/catch) | `HubPool:715-796, 846-850` |
| `emergencyDeleteProposal()` | owner | delete; if count > 0: refund bond | Ext: bond transfer | `HubPool:229-240` |
| `addLiquidity(t, x)` | ¬paused ∧ isEnabled ∧ msg.value rule | r := rate (accrue + sync if S > 0); mint ⌊x·1e18/r⌋; L += x; pull x | Ext: token | `HubPool:449-465, 920-940` |
| `removeLiquidity(t, s, eth)` | ¬paused | r := rate; y := ⌊s·r/1e18⌋; burn s; L −= y (checked); send y | Ext: token / ETH | `HubPool:476-496` |
| `sync(t)`; inside rate/utilization | — | if B_sansBond > L: U −= (B_sansBond − L); L := B_sansBond | reads balance | `HubPool:958-971` |
| accrual (inside rate) | S > 0 | F −= min(F·r·Δt/1e18, F); lastLpFeeUpdate := now | | `HubPool:943-956` |
| `claimProtocolFeesCaptured(t)` | — | send P to the capture address; P := 0. **L unchanged.** | Ext: token | `HubPool:802-807` |
| `haircutReserves(t, h)` | owner | U −= h | | `HubPool:427-431` |
| `relaySpokePoolAdminFunction(c, data)`, `setDepositRoute` | owner | adapter.relayMessage(spoke_c, data) | Ext: delegatecall; Universal: store write with admin nonce | `HubPool:249-254, 372-388, 1013-1030` |
| `set*` admin setters | owner. `setBond` and `setIdentifier` also require count = 0. | parameter := value | | `HubPool:218-416` |

### 2.2 SpokePool (EVM base)

| Action | Guard (pre) | Effect (post) | Shared state / Ext | Code |
|---|---|---|---|---|
| `deposit` / `depositV3` / `depositNow` | ¬pausedDeposits ∧ depositor is an EVM address ∧ outputToken ≠ 0 ∧ quoteTime ∈ [now − buffer, now] ∧ fillDeadline ≤ now + buffer ∧ (exclusivity > 0 ⇒ exclusiveRelayer ≠ 0) | id := numberOfDeposits++; pull inputAmount from msg.sender (or wrap msg.value); emit `FundsDeposited` (exclusivity deadline = param or now + param) | Ext: token | `SpokePool:533-564, 611-639, 744-771, 1383-1463` |
| `unsafeDeposit(..., nonce)` | same | id := keccak(msg.sender, depositor, nonce) | Ext | `SpokePool:675-712, 1363-1369` |
| `speedUpDeposit` | valid EIP-712 / 1271 signature by depositor over (id, originChainId, Δ). The domain has **no** verifyingContract. | emit only | Ext: 1271 staticcall | `SpokePool:853-882, 1560-1607`; `EIP712CrossChainUpgradeable.sol` |
| `fillRelay` (+ `fillV3Relay`, ERC-7683 `fill`) | ¬pausedFills ∧ ¬V5(message) ∧ (now ≤ exclDeadline ⇒ filler = exclusiveRelayer) ∧ now ≤ fillDeadline ∧ status ≠ F | status := F; emit `FilledRelay`(type = FastFill or ReplacedSlowFill); pull outputAmount from msg.sender to recipient (unwrap WETH for EOA/7702); if message ≠ ε ∧ recipient has code: callback | Ext: token, recipient callback | `SpokePool:986-1025, 1197-1219, 1707-1744, 1791-1826` |
| `fillRelayWithUpdatedDeposit` | as `fillRelay`, plus a valid depositor signature | as above, using the updated amount, recipient and message | Ext | `SpokePool:1108-1140` |
| `requestSlowFill` | ¬pausedFills ∧ ¬V5 ∧ now > exclDeadline ∧ now ≤ fillDeadline ∧ status = U | status := R | | `SpokePool:1157-1188` |
| `executeSlowRelayLeaf(sf, id, proof)` | ¬V5 ∧ proof ∈ rootBundles[id].slowRelayRoot ∧ now ≤ fillDeadline ∧ status ≠ F. **Not gated by `pausedFills`.** | status := F; pay updatedOutputAmount from spoke reserves; callback | Ext | `SpokePool:1242-1266` |
| `executeRelayerRefundLeaf(id, leaf, proof)` (payable) | leaf.chainId = chainId ∧ proof ∈ rootBundles[id].rrRoot ∧ bit[id][leafId] = 0 ∧ cumulative refunds ≤ start balance | bit := 1; per refund: transfer, or on failure `relayerRefund += amount`; if amountToReturn > 0: bridge to hub | Ext: tokens, bridge, OFT fee refund to msg.sender | `SpokePool:1276-1315, 1465-1511, 1550-1558` |
| `claimRelayerRefund(token, to)` | `relayerRefund[token][msg.sender]` > 0 | := 0; transfer | Ext | `SpokePool:1324-1331` |
| `executeAcrossV5` / `adapterExecuteAcrossV5` | msg.sender = gateway (executor mode) or = `gateway.currentExecutor()` (adapter mode) ∧ msg.value = 0 ∧ recipient, outputToken and witness match the committed input ∧ outputAmount ≥ floor ∧ exclusivity vs `currentSubmitter` ∧ ¬pausedFills | `_fillRelay` with payer = submitter or executor | Ext: Gateway reads, token, callback | `SpokePool:1041-1088, 1677-1697` |
| admin: `relayRootBundle`, `emergencyDeleteRootBundle`, pauses, `set*`, `executeExternalCall`, `upgradeTo*` | `_requireAdminSender()` (variant-specific, §2.4) ∧ nonReentrant. **`_authorizeUpgrade` is the only onlyAdmin path without nonReentrant.** | push root / zero roots / set flag / arbitrary `target.call` / switch implementation | Ext: `executeExternalCall` | `SpokePool:325-427` |

### 2.3 Messaging and delivery (interleaved environment actions)

| Action | Guard | Effect | Code |
|---|---|---|---|
| native bridge delivery to spoke c | a queued message exists | calls the spoke as the aliased or relayed admin | adapters; `*_SpokePool._requireAdminSender` |
| `HubPoolStore.storeRelayMessageCalldata` | msg.sender = HubPool | admin (owner-originated) → `[dataUuid++] := H(target, data)`; otherwise → `[challengePeriodEndTimestamp] := H(0, data)`. Write-once per nonce. | `HubPoolStore.sol:55-79`; `Universal_Adapter.sol:53-69` (`isAdminSender = msg.sender == owner()` at :66) |
| `SP1Helios.update` | `STATE_UPDATER_ROLE` ∧ proof verifies | records the proven storage slots at the new head, keeps them forever | `SP1Helios.sol` `update` |
| `Universal_SpokePool.executeMessage(n, m, head)` (anyone) | `H(m) = helios.getStorageSlot(head, store, slot(n))` ∧ target ∈ {0, this} ∧ ¬executed[n] ∧ ¬_adminCallValidated | executed[n] := 1; `_adminCallValidated := true`; delegatecall(self, data); reset | `Universal_SpokePool.sol:62-70, 126-164, 185-190` |
| `Universal_SpokePool.adminExecuteMessage(m)` | local owner ∧ Helios head older than `ADMIN_UPDATE_BUFFER` | as above, with no store binding | `Universal_SpokePool.sol:166-172` |
| `Polygon_SpokePool.processMessageFromRoot` | msg.sender = fxChild ∧ rootSender = crossDomainAdmin ∧ ¬callValidated | `callValidated := true`; delegatecall(self, data); reset | `Polygon_SpokePool.sol:63-74, 155-174, 291-293` |
| SVM `handle_receive_message` (CCTP) | CCTP authority PDA signer ∧ remote_domain ∧ sender = cross_domain_admin | translate the selector to an SVM instruction and self-invoke as `self_authority` | `svm/instructions/handle_receive_message.rs:14-114` |

### 2.4 Admin authority predicate per spoke (from the audit, `model/sites.md`)

| Spoke | `_requireAdminSender` | Class |
|---|---|---|
| Arbitrum, ZkSync, Lens | `msg.sender == alias(crossDomainAdmin)` | principal |
| Ovm, OP, Lisk, Cher | `crossChainSender(MESSENGER) == crossDomainAdmin`, which requires msg.sender = messenger | principal |
| Linea | `msg.sender == messageService ∧ sender() == crossDomainAdmin` | principal |
| Ethereum | `onlyOwner` | principal |
| **Polygon** | `callValidated` | **flag (temporal)** |
| **Universal, Tron** | `_adminCallValidated` | **flag (temporal)** |
| SVM | `signer ∈ {state.owner, self_authority PDA}` (`svm/constraints.rs:13-15`) | principal, with **two principals** |

### 2.5 SVM spoke (differences from §2.2 only)

| Action | Difference | Code |
|---|---|---|
| `fill_relay` | exclusivity is skipped when `exclusive_relayer == default`; the status PDA is created with `init_if_needed` | `svm/instructions/fill.rs:90-179` |
| `close_fill_pda` | signer = recorded relayer ∧ now > fill_deadline. **Deletes the PDA (status → absent).** | `fill.rs:203-226` |
| `execute_slow_relay_leaf` | the status PDA must exist (no `init`); deadline and ¬Filled are checked | `slow_fill.rs:226-309` |
| `execute_relayer_refund_leaf{,_deferred}` | **the caller chooses** transfer or accrual to ClaimAccounts; `amount_to_return` accrues to `pending_to_hub_pool`, bridged later by anyone | `bundle.rs:101-175`; `lib.rs:510-527` |
| `deposit` / `unsafe_deposit` | the signer need not be the depositor: funds move from the depositor's ATA through a delegate PDA seeded by the hash of the deposit parameters. **The seed excludes `(signer, deposit_nonce)`**, while `unsafe` id = H(signer, depositor, nonce). | `deposit.rs:22-68, 252-305`; `delegate_utils.rs:10-23` |
| admin (`relay_root_bundle`, pauses, `set_cross_domain_admin`, delete) | callable by the **local owner** or by the CCTP self-authority | `admin.rs:135-202`; `constraints.rs:13-15` |

## 3. Specification extracted

Sources: `require`/`revert` guards, NatSpec comments, the in-code statements of the off-chain rules (UMIP), and the protocol's implicit contract. Each invariant is a predicate over the state of §1. Inductive invariants are written `□P`. Step properties are written `□(P → ○Q)` or as a predicate on transitions `(s, a, s')`.

### 3.1 Destination relay layer (key space `K_fill`)

- **F1 fill-once.** For every scope σ and relay hash h: `payouts_σ(h) ≤ 1`, over the whole life of σ, fast and slow fills combined. Source: `SpokePool:956` ("Cannot fill more than once"), `1227-1229`.
- **F2 deadline.** A payout for h occurs only at `now ≤ fillDeadline(h)` (`SpokePool:1715`; `svm fill.rs:116`, `slow_fill.rs:249`).
- **F3 exclusivity.** If `now ≤ exclusivityDeadline(h)`, a fast fill is by `exclusiveRelayer(h)`, and no slow fill can be requested (`SpokePool:1161-1167, 1648-1658`).
- **F4 V5 quarantine.** A relay whose message starts with `V5_MAGIC_PREFIX` reaches Filled only through `_fillV5`, with `message = prefix ‖ gateway.currentStepId()` (`SpokePool:311-318, 1661-1697`; `V5SpokePoolInterface.sol:6-21`).

### 3.2 Root and refund layer (key spaces `K_ref`, `K_msg`, `K_hub`)

- **R1 refund-once.** For every refund entitlement e in a root and every chain c: `Σ_{σ scopes on c} payouts_σ(e) ≤ 1`. The in-code statement of the rule is `HubPoolInterface.sol:29-32`: "the data worker should ensure that only one leaf for a specific chainId should have a groupIndex equal to 0".
- **R2 root authorization and revocation.** A spoke on chain c receives the roots of bundle b only if the HubPool executed a groupIndex-0 leaf of b for c. Emergency deletion before that execution revokes the delivery (`HubPool:224-228`: deletion exists to stop a bad bundle "that gets through liveness").
- **R3 hub leaf-once.** Within a proposal, each leafId executes at most once and the number of executions is at most `n` (`HubPool:625, 653`).

### 3.3 LP ledger (per l1Token; `N := L + U − F`, `S := lpToken.totalSupply`, `B := balanceOf(HubPool) − [bond held]`)

- **L1 equity.** `□(S > 0 → N ≥ 0)`. The comment at `HubPool:933-935` claims "LiquidReserves + utilizedReserves will always be larger than undistributedLpFees".
- **L2 backing.** `□(L ≤ B)`, so the accounting guard `L −= x` (`HubPool:486-487, 904`) is physically backed.
- **L3 solvency.** `□(N ≤ B + Out + Arr − P)`: LP equity never exceeds the assets that exist.
- **L4 exit at zero utilization.** `□(S > 0 ∧ U ≤ 0 → removeLiquidity(all) is enabled)`. Utilization is defined at `HubPool:976-992`.
- **L5 rate monotonicity.** For every step except `haircutReserves`, with `S > 0` before and after: `rate' ≥ rate` (`HubPool:929-932`).
- **L6 donation neutrality.** Token transfers into the HubPool and `sync` leave N unchanged (`HubPool:961-970`).
- **L7 fee smear.** Fees allocated at `t_a` are released at rate `lpFeeRatePerSecond` over `[t_a, ∞)` (`HubPool:90-93`).

### 3.4 Attestation layer (proposal, dispute, bond)

- **H1 window disjointness.** No state has both `dispute` and `execute` enabled. `now ≤ end` (`HubPool:717`) and `now > end` (`HubPool:622`) are complementary.
- **H2 bond custody.** `□(bond held by HubPool ⇔ count > 0)`. `_sync` relies on this through `_activeRequest()` (`HubPool:963-964`).
- **H3 dispute escalates.** A proposal in liveness is removed only by (a) a DVM escalation with the disputer's bond escrowed, (b) execution, or (c) the owner (`HubPool:709-714`: "Caller stakes a bond to dispute").
- **H4 hub liveness.** While `count > 0`, the last leaf and `emergencyDeleteProposal` are executable: the bond can always be refunded.

### 3.5 Authority layer

- **A1 principal authority.** An `onlyAdmin` effect occurs only in a call frame whose principal is the cross-domain admin. On Polygon the in-code statement is `Polygon_SpokePool.sol:286-289`: "This prevents calling the admin functions from any other method besides `processMessageFromRoot`".
- **A2 target binding (Universal).** An admin message executes only on the spoke it was addressed to. The store explicitly does **not** guarantee this if spokes on different chains share an address (`HubPoolStore.sol:15-17`).

### 3.6 Channel layer

- **C1 last writer wins.** After all admin messages issued to a spoke have been delivered, the spoke's state equals the effect of the last-issued message.
- **C2 delivery.** Every executed groupIndex-0 leaf eventually yields exactly one root bundle on its spoke.

### 3.7 Origin and deposit layer

- **D1 id uniqueness.** Within one spoke instance, safe deposit ids are pairwise distinct (`numberOfDeposits++`, `SpokePool:557`). Across instances on one chain this needs `_initialDepositId` (`SpokePool:267-269`).
- **D2 unsafe id binding.** The deposit that consumes a depositor's funds carries the id `H(sender, depositor, nonce)` that the depositor chose (`SpokePool:644-653`).
- **D3 speed-up binding.** A depositor signature applies to exactly one deposit. The EIP-712 domain is `(name, version, originChainId)`, with **no verifyingContract** (`EIP712CrossChainUpgradeable.sol:23, 55-57`). So the signature binds `(depositor, depositId, originChainId)` across all spokes, which `SpokePool:646-653, 834-837` documents as a hazard for reused ids.

### 3.8 Liveness obligations (recorded, not model-checked)

- **Lv1.** Every valid bundle is fully executed. Needs: a keeper, adapter funds (`loadEthForL2Calls`), routes set, ¬paused, and H4.
- **Lv2.** Every deposit is filled before its deadline or refunded after it. Needs relayers or slow fills, plus the UMIP's expired-deposit refunds.
- **Lv3.** Every executed refund either transfers or becomes claimable, and every claim succeeds. Needs balance ≥ outstanding claims; this is not reserved on-chain (`SpokePool:1486-1500`).

## 4. Environmental assumptions

**Enforced-by** values: **code** (a check in the target), **conv.** (operational convention), **ext.** (a third party or another protocol's governance), **luck** (nothing enforces it).

| ID | Assumption | Enforced by | Evidence / current value | Needed by |
|---|---|---|---|---|
| A_V | Proposed bundles satisfy the UMIP validity predicate V, including: one groupIndex-0 leaf per chain (**A_V1**); a root is never re-proposed after its leaves were executed (**A_V2**); fees in `bundleLpFees` are backed by real fee tokens (**A_feesBacked**); leaf counts and array lengths are consistent | **ext.**: ≥1 honest disputer within liveness, DVM correctness, proposer whitelist | liveness = 1800 s live; ABT proposer whitelist (`BondToken.sol:74-79`) | R1, L3, Lv1 |
| A_wl | Only whitelisted proposers can post a bond | **code** (ABT `transferFrom`) + **conv.** (bondToken = ABT) | bondToken = ABT `0xee1D…02ea` | H3 |
| A_hblk | A whitelisted proposer never lands a proposal in a block after a dispute of its own previous proposal | **conv.** (bot timing) | — | H3 |
| A_ff | `finalFee(bondToken) < bondAmount` | **ext.** (UMA governance) | 0.055e18 < 0.45e18 | H3 |
| A_ooOK | `ACROSS-V2` and the bond token stay whitelisted in UMA, so the OO request does not revert | **ext.** | true at block 26259843 | H3 |
| A_pct0 | `protocolFeeCapturePct = 0` | **conv.** (owner) | 0 | L2, L4, H4 |
| A_bondNotPooled | bondToken is not an LP-enabled pooled token | **conv.** (owner) | ABT is not pooled | H4 |
| A_noHaircut | `haircutReserves` is used only to book real losses ≤ N | **conv.** (owner) | — | L1, L4 |
| A_exec | Root-bundle leaves for Universal-adapter chains are never executed by the HubPool owner | **luck** (nothing distinguishes the caller class except the store key) | the owner is a Safe; keeper executes normally | R1 (Universal) |
| A_inst | At most one Universal_SpokePool instance per chain ever reads the shared HubPoolStore through the same light client | **conv.** | per-chain redeploys are anticipated (`_initialDepositId`) | R1 (Universal) |
| A_addr | Universal spokes on different chains have different addresses | **conv.**, acknowledged in `HubPoolStore.sol:15-17` | verified: the 8 Universal-adapter chains (56, 143, 999, 9745, 4217, 43114, 5042, 4663) and TRON (`0xc148…cd80`) have pairwise-distinct spoke addresses in `broadcast/deployed-addresses.json` | A2 |
| A_closed | Targets of `executeExternalCall` relayed to Polygon, Universal or Tron spokes never yield control to third parties | **conv.** (admin) | — | A1 |
| A_fifo | A channel delivers admin messages in issue order | **Not enforced by any spoke**: no spoke checks a sequence number, so order is whatever the channel delivers. Universal/Tron (any proven nonce, by anyone) and CCTP→SVM (used-nonce set only) impose no order. Arbitrum, OP and Polygon are ordered only while automatic delivery succeeds; manual redemption or replay of a failed message can reorder. | `Universal_SpokePool.sol:126-164`; `handle_receive_message.rs:46-85` | C1 |
| A_clk | Destination clocks are non-decreasing across transactions | **ext.** (chain runtime) | the SVM program never checks it | F1 (SVM) |
| A_atomicAuth | An SVM depositor's delegate approval and its `unsafe_deposit` are in one transaction | **conv.** (client) | — | D2 (SVM) |
| A_tok | Route tokens are standard ERC-20/SPL: no fee-on-transfer, no rebasing, no blocking hooks | **conv.** (admin whitelists routes) | `HubPool:811-815` warns about this | all ledgers |
| A_gw | `IGateway` getters reflect the live execution, `stepId` commits to the user's path, and `currentSubmitter` is the `execute()` caller | **ext.** (Gateway, outside this repository) | `IGateway.sol` docs | F4, V5 binding |
| A_helios | The Helios updater proves only genuine L1 storage, and the SP1 program and verifier are sound | **ext.** | `SP1Helios.update` role-gated | R2, C1, A2 |
| A_t | uint32 timestamps do not overflow | **luck/conv.** until 2106 | `HubPool:35-38` | all time guards |
| A_skew | Origin and destination clocks agree to within the exclusivity margins | **luck** | `SpokePool:1407-1417` (offset uses the origin's `block.timestamp`, checked against the destination's) | F3 |

## 5. The abstract transition system M = (S, S0, Act, →)

### 5.1 Global system

`S = S_hub × S_store × Π_{c∈Chains} Π_{σ∈Inst(c)} S_spoke(σ) × S_helios × Π_c Q_c × S_env`

- `S_hub`, `S_spoke`, `S_store` and `S_helios` are the persistent variables of §1.2–§1.5.
- `Q_c` is the multiset of messages in flight to chain c.
- `S_env = (now_c)_c × Out × Arr × UMA × Ω`.

`S0`: HubPool, store and spokes in their post-initialization values. All queues are empty, `Ω = ∅`, and the parameters are free within their domains. The live instance fixes them as in §1.2.

`Act = Act_hub ∪ Act_spoke ∪ Act_msg ∪ Act_env`, with the guarded commands of §2. `Act_env` contains:

- `tick_c`, which advances `now_c`. Its inverse exists only when A_clk is relaxed.
- `deliver_c(m)` and `lose_c(m)`. The latter applies only on lossy channels: Arbitrum retryables expire after 7 days unless redeemed.
- `arrive(n)` (bridge), `helios.update(slots)`, the UMA governance moves (`finalFee`, whitelists), the DVM verdict, and the proposer and disputer choices.

`s →a s'` iff the guard of `a` holds in `s` and `s'` is its effect. Every on-chain `a` is atomic. Interleaving happens only between actions.

### 5.2 Projections (the eight layer models)

Each projection `α_X : S → S_X` keeps the variables listed. It replaces everything else by environment moves that can produce any effect the dropped variables can have on the kept ones. Each projection is therefore intended as an over-approximation of M restricted to its invariants. Two caveats:

- The transitions are checked against the kept variables' write sites by the audit (§5.3).
- The choice of environment moves is argued here, not mechanically proved.

All variables are bounded, so all eight models are explored exhaustively.

| Layer | Kept variables (abstract domain) | Knobs (assumptions) | Exhaustive state count* |
|---|---|---|---|
| `F_fill[EVM\|SVM]` | status of one relay hash ∈ {U,R,F,absent}, `now ∈ 0..3` (deadline 1, exclusivity 0), slow leaf published, payout count | A_clk | 17 / 23 |
| `R_root[native\|universal]` | proposal (leaves, executed), proposal count, store entries (kind, nonce, target), admin-nonce counter, bridge queues, spoke instances (copies, imported nonces, paid), payouts for entitlements eX, eY, whether Y's leaf was executed | A_V1, A_V2, A_exec, A_inst | 24 / 48 |
| `L_ledger` | L, U, F, B, S, P, Out, Arr, pct, with exact Solidity floor arithmetic (1e18 ↦ 100), totals ≤ 4 | A_pct0, A_noHaircut, A_feesBacked | 1,742 |
| `H_proposal` | proposal kind {honest, attacker}, phase, count, bonds held, block index, OO request set {(block, kind)}, UMA flags, honest removals without a disputer bond | A_wl, A_hblk, A_ff, A_ooOK | 27 |
| `B_bond_vs_reserves` | L, B (incl. bond iff pooled), active, count, P, pct | A_bondNotPooled, A_pct0 | 18 |
| `A_authority[principal\|flag]` | frame stage {idle, admin, callee}, flag, who upgraded | A_closed | 4 / 4 |
| `C_channel` | delivered sequence of {m0: pause=false, m1: pause=true}, value | A_fifo | 3 |
| `D_unsafe_id[EVM\|SVM]` | authorized, deposited id ∈ {expected, other}, prefill | A_atomicAuth | 4 / 4 |

\* With every knob enforced. Relaxed runs explore up to about 2.0M states (ledger, no knobs).

### 5.3 Grounding of the projections

`model/sites.py` checks that the abstract transitions cover every concrete write site of the kept variables. The audit passes at `b1c4e86`, and `model/sites.md` lists every site:

- **`fillStatuses`:** written only at `SpokePool:1172` (U→R, guarded by `= U`) and `SpokePool:1740` (→F, guarded by `≠ F`).
- **Payout calls:** `_fillRelay` is called only from `fillRelay`, `fillRelayWithUpdatedDeposit`, `executeSlowRelayLeaf` (via `_fillRelayV3`) and `_fillV5`. The three V3 entrypoints and `requestSlowFill` all carry `nonV5Fill`.
- **Pooled-token ledger:** `liquidReserves`, `utilizedReserves`, `undistributedLpFees` and `unclaimedAccumulatedProtocolFees` are written only in `addLiquidity`, `removeLiquidity`, `_sendTokensToChainAndUpdatePooledTokenTrackers`, `_sync`, `_allocateLpAndProtocolFees`, `_updateAccumulatedLpFees`, `haircutReserves` and `claimProtocolFeesCaptured`. Each is one `L_ledger` transition.
- **Bond movements:** `bondToken` moves only at `HubPool:233, 583, 695, 791, 847`, plus the OO pull inside `requestAndProposePriceFor`. Each is one `H_proposal` transition.
- **Root creation:** `rootBundles.push` occurs only in `relayRootBundle`. HubPool emits the relay payload only in `executeRootBundle` (`HubPool:683`).
- **Upgrade authority:** `_authorizeUpgrade` is the only `onlyAdmin` function in `SpokePool` without `nonReentrant`. This is the sink of A1's counterexample.

## 6. Results per invariant

Traces are sequences of `(state, action, resulting state)`. Only the fields that change are shown; the full states are in `model/results.md`. Breadth-first search guarantees each trace is a **shortest** counterexample in its layer. Concrete replays add only setup steps: deployment, funding and approvals.

### 6.1 F1 fill-once

**EVM: HOLDS/M+F, minimal assumption set ∅.**

*Proof.* By the audit, `fillStatuses` is written only at `SpokePool:1172`, which requires U and writes R, and at `SpokePool:1740`, which requires ≠F and writes F. No site writes from F, so F is absorbing. Every payout (`_transferTokensToRecipient`, `SpokePool:1743`) follows the `1740` write in the same atomic step. Hence `payouts(h) ≤ #(¬F → F) ≤ 1`. The argument uses no fact about time, roots or callers.

*Evidence.*
- Model: 17 states.
- `T11_FillOnceInvariant` exercises one relay hash on `Ethereum_SpokePool`: 512 runs × depth 40 = 20,480 calls to fill, request, relay the same slow root any number of times, execute the slow leaf against any copy, and warp time **backwards and forwards**. There were no violations.
- Canary `C11` (`invariant_noPayoutEver`) fails after one call, so the campaign reaches payouts.

*Scope caveat.* The guard is per spoke instance. A second SpokePool proxy on the same chain has its own `fillStatuses`. A relay hash filled on it is not refunded by the UMIP, so the extra payout is borne by the relayer, not the protocol.

**SVM: HOLDS/M under {A_clk}; REFUTED/A without it.** Shortest counterexample, 6 steps (relay with fillDeadline = 1):

1. `(absent, t=0, pay=0)` —`fill_relay`→ `(F, 0, 1)`
2. `(F, 0, 1)` —`tick`→ `(F, 1, 1)`
3. `(F, 1, 1)` —`tick`→ `(F, 2, 1)`
4. `(F, 2, 1)` —`close_fill_pda` [t > deadline, `fill.rs:216-226`]→ `(absent, 2, 1)`
5. `(absent, 2, 1)` —`clockBack`→ `(absent, 1, 1)`
6. `(absent, 1, 1)` —`fill_relay` [`init_if_needed` recreates the PDA, `fill.rs:68-83`]→ `(F, 1, 2)` ✗

Required assumption: A_clk. The pair "close requires now > deadline" and "fill requires now ≤ deadline" separates closing from re-filling only if time does not decrease. **Refinement gap:** on EVM, Filled is absorbing; on SVM the key is *resurrectable*. State-based observers (dataworker or explorer) also lose the Filled fact after the close.

### 6.2 F2 deadline, F3 exclusivity, F4 V5 quarantine

- **F2: HOLDS (audit).** Every payout path passes the deadline check: `SpokePool:1715` for all EVM paths, `fill.rs:116` and `slow_fill.rs:249` on SVM.
- **F3: HOLDS on EVM under A_clk.**
  - Fast fills call `_requireExclusiveFiller`: `fillRelay` and `fillRelayWithUpdatedDeposit` at `SpokePool:991, 1117`; `_fillV5` against `currentSubmitter` at `SpokePool:1685`.
  - Slow-fill requests are rejected inside the window (`SpokePool:1165`). Any slow leaf is therefore executed after a request made past the window.
  - **Gap (A_skew):** the offset form adds the *origin* `block.timestamp` and is compared against the *destination* clock (`SpokePool:1418-1422` vs `1655`). The absolute end of exclusivity shifts by the clock skew between the chains.
  - **EVM/SVM divergence:** SVM ignores exclusivity when `exclusive_relayer = default` (`fill.rs:108-113`). EVM then blocks every filler until the deadline (`SpokePool:1655`). This is unobservable for deposits made by either Across spoke, since both reject exclusivity without a relayer (`SpokePool:1426`, `deposit.rs:106-108`).
- **F4: HOLDS (audit) under A_gw.**
  - All V3 settlement entrypoints carry `nonV5Fill`, and `_fillV5` checks `keccak(message) = keccak(prefix ‖ currentStepId)` (`SpokePool:1679-1683`).
  - **Dead keys:** a V5-tagged message of length ≠ 64, or one bound to a step never executed, is unfillable by every path, including slow fills. Such a deposit relies entirely on the expired-deposit refund (Lv2).

### 6.3 R1 refund-once and R2 root authorization

**Native-bridge chains.**

R1: HOLDS/M under the minimal set **{A_V1, A_V2}** (24 states). The knobs A_exec and A_inst are irrelevant.

*Relax A_V1: REFUTED/C (T03).* Shortest abstract trace, 7 steps:

1. `∅` —`propose[two groupIndex-0 leaves for X]`→ `leaves={X0, X0b, Y0}`
2. —`executeRootBundle[X0]`→ `pendX = 1`
3. —`bridge.deliver(relayRootBundle → X)`→ `x.copies = 1`
4. —`executeRelayerRefundLeaf[x, id 0]`→ `payX = 1`
5. —`executeRootBundle[X0b]`→ `pendX = 1`
6. —`bridge.deliver`→ `x.copies = 2`
7. —`executeRelayerRefundLeaf[x, id 1]`→ `payX = 2` ✗

Concrete replay `T03.test_twoGroupZeroLeaves_doubleRefund` (HubPool + `Ethereum_Adapter` + `Ethereum_SpokePool`, end to end): a 100 DAI entitlement is paid 200 DAI, out of other users' deposits held by the spoke. A third execution reverts, because the guard is `(rootBundleId, leafId)`, not the leaf.

*Relax A_V2: REFUTED/A*, 9 steps:

1. propose
2. execute X0
3. deliver
4. `emergencyDeleteProposal`
5. pay
6. propose[same roots again]
7. execute X0
8. deliver
9. pay ✗

The mechanism is the same as T03, a second root copy.

*Key-scope asymmetry* (`T03.test_keyScopeAsymmetry_slowFillOnce_refundTwice`, REFUTED/C). In one duplicated root:
- the slow-fill leaf pays **once**: its key is the relay hash, scoped to the spoke, and the second execution reverts `RelayFilled`;
- the refund leaf pays **twice**: its key is `(rootBundleId, leafId)`, scoped to the root copy.

So A_V1 protects refunds only; slow fills are protected by construction.

R2: HOLDS/M under the minimal set **∅**. The only producer of a root on Y is Y's own leaf.

**Universal-adapter chains (HubPoolStore + SP1Helios). `Tron_SpokePool` inherits `Universal_SpokePool`, so the same mechanism applies by inheritance; it was not replayed on TRON.**

R1: HOLDS/M under the minimal set **{A_V2, A_exec, A_inst}** (48 states).

*A_V1 is not required.* Non-owner executions of any number of groupIndex-0 leaves map to the single nonce `challengePeriodEndTimestamp`, and `_storeData` keeps the first write (`HubPoolStore.sol:72-79`). The store's design removes the dependence on A_V1 and introduces A_exec and A_inst.

*Relax A_exec: REFUTED/C (T04).* Shortest abstract trace, 7 steps:

1. `∅` —`propose[valid]`→ `leaves={X0, Y0}`
2. —`executeRootBundle[X0 by nonOwner]`→ `store={(ts, 1, target 0)}`
3. —`executeMessage[y, ts:1]`→ `y.copies = 1` (early import, see R2)
4. —`executeRelayerRefundLeaf[y, 0]`→ `payY = 1`
5. —`executeRootBundle[Y0 by owner]`→ `store += (adm, 0, target Y)`
6. —`executeMessage[y, adm:0]`→ `y.copies = 2`
7. —`executeRelayerRefundLeaf[y, 1]`→ `payY = 2` ✗

Concrete replay `T04.test_ownerAndNonOwnerExecution_duplicateRootOnSpoke`, using the real HubPool, `Universal_Adapter`, `HubPoolStore`, `SP1Helios` and `Universal_SpokePool`. The owner executes X's leaf and an ordinary caller executes Y's leaf. The store then holds `H(spokeX, data)` at nonce 0 **and** `H(0, data)` at nonce `end`. Spoke X imports both and pays 200 for 100. Control `test_uniformCallerClass_singleRoot`: with uniform non-owner callers, exactly one copy is stored.

*Relax A_inst: REFUTED/C (T06).* Shortest abstract trace, 7 steps:

1. deploy a second instance on X
2. propose
3. execute X0 (ts nonce)
4. inst1 imports
5. inst2 imports
6. inst1 pays
7. inst2 pays ✗

Concrete replay `T06`: 30 days after the original execution, a fresh `Universal_SpokePool` proxy with the same immutables imports the historical root with **no new L1 action and no new light-client update**. `SP1Helios.storageValues` keeps proven slots forever, and `executedMessages` is per instance. The historical refund is paid again.

*Relax A_V2: REFUTED/A*, 9 steps (new ts nonce for the re-proposal).

R2: **REFUTED under every assumption set** (no knob subset makes it hold).

The shortest trace, 4 steps: propose → execute X0 (ts nonce, target 0) → Y imports → Y pays, with Y's leaf never executed.

The harmful instance is revocation failure: concrete replay `T05`. The bundle is deleted with `emergencyDeleteProposal` after X's leaf, and Y's pool-rebalance leaf then reverts. Spoke Y still imports the roots and pays 100.

*Refinement gap:* on native chains, deletion before execution revokes delivery; on Universal chains it cannot.

### 6.4 R3 hub leaf-once

**HOLDS (audit).** Per proposal: `isClaimed1D` / `setClaimed1D` (`HubPool:625, 650`), and the checked decrement `--unclaimedPoolRebalanceLeafCount` (`HubPool:653`) bounds executions by `n`.

- *Liveness note:* a tree with fewer than `n` leaves leaves the hub stuck until `emergencyDeleteProposal`, which returns the bond to the proposer (`HubPool:232-233`). A tree with more than `n` leaves strands the extra leaves.

### 6.5 LP ledger (one non-bond l1Token; `L_ledger`, 1,742 states with all knobs, 2.0M with none)

| Invariant | Minimal assumption sets | Shortest counterexample per relaxation | Concrete |
|---|---|---|---|
| L1 equity `S>0 → N≥0` | {A_noHaircut} | 4 steps: `addLiquidity(2)` → `haircutReserves(1)` ×3 ⇒ `N = −1, S = 2`. Then `uint256(N)` wraps and `·1e18` overflows (`HubPool:936-939`), so every rate-dependent action reverts. | — (an owner power) |
| L2 backing `L ≤ B` | {A_pct0} | 4 steps, below | **T01** |
| L3 solvency `N ≤ B+Out+Arr−P` | {A_feesBacked} | 2 steps: `executeRootBundle(netSend 0, fees 2, unbacked)` → `accrueLpFees(1)` ⇒ `N = 1 > 0 = assets` (phantom equity) | — (attestation dependence) |
| L4 exit at zero utilization | {A_noHaircut, A_pct0} | A_pct0: the L2 trace, then `removeLiquidity(all)` is disabled while `U = 0`. A_noHaircut: the L1 trace. | **T01** |
| L5 rate monotonicity | ∅ | — | — |
| L6 donation neutrality | ∅ | — | — |

**L2 / L4 trace** (`L_ledger`, relax A_pct0):

1. `(L0 U0 F0 B0 S0 P0 Out0)` —`addLiquidity(2)`→ `(L2 B2 S2)`
2. —`setProtocolFeeCapture(100%)`→ `pct=100`
3. —`executeRootBundle(netSend=0, bundleLpFees=2)`→ `(P2 Out2)`
4. —`claimProtocolFeesCaptured`→ `(B0 P0)` ⇒ `L=2 > B=0` ✗

**REFUTED/C (T01, real HubPool).** After the claim: `liquidReserves = 1000e18`, `balanceOf = 990e18`, `utilizedReserves = 0`, and `liquidityUtilizationCurrent() = 0`. The LP's full `removeLiquidity` passes the accounting guard `L −= x` and reverts at the token transfer.

*Mechanism:* `claimProtocolFeesCaptured` lowers B and leaves L unchanged (`HubPool:802-807`). The protocol share of fees is paid out of LP liquidity before the fee tokens return from the spokes. `_sync` only ever raises L (`HubPool:965`), so the deficit persists until later arrivals exceed it. Not realized live: `protocolFeeCapturePct = 0` at block 26259843.

**Proofs for L5 and L6** (by audited write site):

- **L5.** `addLiquidity` mints `⌊x·1e18/r⌋`, rounding against the minter, so `r' ≥ r`. `removeLiquidity` pays `⌊s·r/1e18⌋`, rounding against the redeemer, so `r' ≥ r`. `_sync`, sends and fee allocation each preserve N and S. Accrual raises N. Claims touch neither N nor S.
- **L6.** `_sync` sets `L' = B` and `U' = U − (B − L)`, so `L' + U' = L + U`, and F is untouched. A donation therefore never moves the exchange rate. This is a positive result: the share-inflation ("first depositor") manipulation has no lever on this pool. The donated amount stays as negative U, as the comment at `HubPool:933-935` intends.

**L7 fee smear: REFUTED/C (T02, refinement gap).**

- *Specification* (`HubPool:90-93`): fees allocated at `t_a` are released at rate `r` from `t_a` on.
- *Implementation:* `_allocateLpAndProtocolFees` raises F without first accruing (`HubPool:1004-1007`). The next `_updateAccumulatedLpFees` releases `min(F·r·(t − lastLpFeeUpdate), F)`, and `lastLpFeeUpdate` can be earlier than `t_a`.
- *Observable trace:*
  1. `exchangeRateCurrent` gives 1.0.
  2. 8 days pass with no LP interaction.
  3. `executeRootBundle(bundleLpFees = 100)`.
  4. `exchangeRateCurrent` in the same block gives **1.1**: 100% released at allocation.
- *Control:* with an interaction just before the proposal, the rate reads 1.00108, i.e. only `(liveness + 1)·r` released.
- *Bounds:* the fraction released at allocation is `min(1, r·(t_a − lastLpFeeUpdate))`. Live, with `r = 1.5e-6 s⁻¹` and liveness 1800 s, that is at least 0.27% whenever no LP touches the pool during liveness, and 100% after 7.72 idle days.

### 6.6 Attestation layer (`H_proposal`, 27 states; `B_bond_vs_reserves`, 18 states)

**H1 window disjointness: HOLDS (∅).** `executeRootBundle` requires `now > end` (`HubPool:622`). `disputeRootBundle` requires `now ≤ end` (`HubPool:717`). The two predicates are complementary.

**H2 bond custody: HOLDS (∅)** while the bond token is not pooled. Bond movements happen only at `HubPool:233, 583, 695, 791, 847` and in the OO's pull. Each coincides with the corresponding change of `count > 0`.

**H3 dispute escalates.** Minimal assumption set **{A_ff, A_hblk, A_ooOK, A_wl}**. Each relaxation independently yields a counterexample:

| Relaxed | Shortest trace | Concrete (T09, verbatim mainnet `SkinnyOptimisticOracle`) |
|---|---|---|
| A_ff | `finalFee ≥ bondAmount` → `propose[honest]` → `dispute` ⇒ `_cancelBundle` (`HubPool:737-740`) | `test_finalFeeAtLeastBond_anyoneCancelsForFree`: a caller holding **no** bond token removes the proposal |
| A_ooOK | de-whitelist the identifier or collateral → `propose[honest]` → `dispute` ⇒ cancel (`HubPool:767-770`) | covered by the same catch path |
| A_wl | `propose[attacker]` → `dispute` (escalates; OO id `(hub, ACROSS-V2, t, "")`) → `propose[honest]` in the same block → `dispute` ⇒ OO reverts "Request already initialized" ⇒ cancel | `test_sameBlockCollision_…`: no DVM request is made, the disputer's balance is unchanged, and the proposer is refunded but unrewarded. Control `test_nextBlock_disputeEscalates_control`: one block later the dispute escalates and escrows the bond. |
| A_hblk | `propose[honest]` → `dispute` → `propose[honest]` in the same block → `dispute` ⇒ cancel | same mechanism |

The A_wl relaxation does not occur in production. `test_abtWhitelist_blocksTheCollisionPrefix` shows that, with the real `BondToken` as bond token, the attacker's prefix proposal reverts with `Transfer not permitted`. What remains is A_hblk, a timing convention of the whitelisted proposers. Live: A_ff holds (0.055 < 0.45 ABT) and A_ooOK holds.

**H4 hub liveness: HOLDS under {A_bondNotPooled} ∨ {A_pct0}.** These are two minimal sets, so the assumption is **disjunctive**. A violation requires relaxing both.

Shortest abstract trace, 4 steps:

1. `propose` (bond enters B)
2. `setProtocolFeeCapture(100%)`
3. fee leaf on the bond token
4. `claimProtocolFeesCaptured` ⇒ `B = 0 < bondAmount` ✗

**REFUTED/C (T10)**, on the send-path variant: a *valid* `netSend = 93 ≤ liquidReserves = 100` drains the hub below `bondAmount`. Then all of the following revert:

- the last leaf (bond refund, `HubPool:694-695`);
- `emergencyDeleteProposal` (`HubPool:232-233`);
- `exchangeRateCurrent` (`_sync` computes `balance − bondAmount` and underflows, `HubPool:964`);
- `proposeRootBundle` ("Proposal has unclaimed leaves").

The hub stays stopped until a third party transfers in the shortfall. Live: bondToken = ABT (not pooled) and pct = 0, so not realized.

### 6.7 A1 principal authority (`A_authority`, 4 + 4 states)

- **Principal spokes** (Arbitrum, ZkSync, Lens, Ovm/OP/Lisk/Cher, Linea, Ethereum): HOLDS (∅).
- **Flag spokes** (Polygon, Universal, Tron): HOLDS only under **{A_closed}**.

Shortest trace, 3 steps:

1. `adminMessage.begin` (flag := true)
2. `admin.executeExternalCall(T)` yields control
3. `T.upgradeTo(evil)` ⇒ authorized ✗

The sink is `_authorizeUpgrade` (`SpokePool:325`), the only `onlyAdmin` path not guarded by `nonReentrant`; `executeExternalCall` holds the reentrancy lock.

**REFUTED/C (T08).**

- An admin message whose intent is a 1-unit transfer of a hook-bearing token (ERC-1363 shape) to a receiver is enough for the receiver to call `upgradeTo` on the spoke during the callback.
- On **Polygon** (`processMessageFromRoot`) and **Universal** (`executeMessage` after a real `relaySpokePoolAdminFunction` → `HubPoolStore` → `SP1Helios` path), the upgrade succeeds and the attacker sweeps 500 DAI.
- Control on **Arbitrum**: the identical message succeeds and the callee's `upgradeTo` reverts, because `msg.sender ≠ alias(admin)`.

*Refinement gap:* the specification at `Polygon_SpokePool.sol:286-289` says admin functions are callable only via `processMessageFromRoot`. The implementation grants authority to every frame inside its dynamic extent.

**A2 target binding: HOLDS under A_addr.** This is documented at `HubPoolStore.sol:15-17` and verified for the current deployments (§4).

### 6.8 C1 last-writer-wins (`C_channel`, 3 states)

HOLDS only under **{A_fifo}**. Shortest trace, 2 steps:

1. `deliver(m1: pauseDeposits(true))`
2. `deliver(m0: pauseDeposits(false))` ⇒ final `paused = false`, although the owner's last instruction was `true` ✗

**REFUTED/C (T07, Universal).** The owner issues unpause (nonce 0) and then pause (nonce 1). An arbitrary account executes nonce 1 and then nonce 0, and the final state is unpaused.

**SVM: REFUTED/A.** `handle_receive_message` translates `pauseDeposits`, `pauseFills`, `setCrossDomainAdmin`, `relayRootBundle` and `emergencyDeleteRootBundle` with no sequence number (`handle_receive_message.rs:55-85`). The program imposes no order; CCTP's receiver tracks which nonces were used, not their order.

Corollary: spoke `rootBundleId`s follow delivery order, not the hub's proposal order. This is observable but does not by itself break safety.

### 6.9 Origin and deposit layer

- **D1: HOLDS per instance.** `numberOfDeposits++` is checked uint32 arithmetic. At `2^32 − 1`, `deposit` becomes permanently unavailable while `unsafeDeposit` keeps working (a liveness note). Across instances on one chain, D1 needs the `_initialDepositId` convention.
- **D2 (EVM): HOLDS (∅).** Funds are always pulled from `msg.sender` (`SpokePool:1441-1445`), and `msg.sender` is a component of the unsafe id (`SpokePool:1363-1369`).
- **D2 (SVM): HOLDS under {A_atomicAuth}; REFUTED/A without it.** Shortest trace, 2 steps:
  1. depositor approves the delegate PDA (seed = Borsh hash of the deposit parameters, **without `(signer, deposit_nonce)`**: `delegate_utils.rs:10-23`, `deposit.rs:270-285`);
  2. any account calls `deposit(...)` or `unsafe_deposit(..., other nonce)` with the depositor's ATA. The depositor need not sign (`deposit.rs:40-45`). This emits `FundsDeposited` with an id the depositor did not choose ✗.

  *Observable consequence:* a relayer that pre-filled the precomputed relay hash, which is the stated use of unsafe deposits (`SpokePool:641-646`), holds a fill that matches no deposit and is not refunded. The real deposit remains fillable.
- **D3:** holds iff D1 holds across instances and no unsafe nonce is reused. Both are documented hazards (`SpokePool:646-653, 834-837`).

### 6.10 SVM-only observations (REFUTED/A or trust-base expansions; derived from code, not executed)

- **Executor-chosen deferral.** Any executor can choose `execute_relayer_refund_leaf_deferred` (`lib.rs:520-527`) and route a whole leaf into ClaimAccounts, provided it pre-creates them. On EVM, deferral happens only when a transfer fails (`SpokePool:1491-1500`).
- **Two-principal admin.** `state.owner` can call `relay_root_bundle` directly (`constraints.rs:13-15`, `admin.rs:159-174`). SVM refund safety therefore also assumes the local owner key, outside the optimistic-oracle path.
- **Deferred bridging.** `amount_to_return` accrues to `pending_to_hub_pool` and is bridged later by anyone (`bundle.rs:150-152`, `token_bridge.rs`). Neither this liability nor ClaimAccount liabilities are reserved against later refunds: the vault check at `bundle.rs:139-142` uses the gross balance. The same holds on EVM for `relayerRefund` (`SpokePool:1477-1489`). Lv3 depends on the dataworker counting deferred amounts as paid.

## 7. Refinement gaps as observable traces

Notation: `Impl ⊄ Spec` means the implementation allows a trace the specification forbids. `Spec ⊄ Impl` means the specification allows a trace the implementation forbids. Event names are those emitted by the code.

| # | Direction | Observable trace | Spec source | Evidence |
|---|---|---|---|---|
| G1 | Impl ⊄ Spec | `ProposeRootBundle(n=2)` · `RootBundleExecuted(leafId=0, chain=X, groupIndex=0)` · `RootBundleExecuted(leafId=1, chain=X, groupIndex=0)` · on X: `RelayedRootBundle(k, rr, sr)` · `RelayedRootBundle(k+1, rr, sr)` · `ExecutedRelayerRefundRoot(rootBundleId=k, leafId=0)` · `ExecutedRelayerRefundRoot(k+1, 0)`: one entitlement, two payments | one groupIndex-0 leaf per chain (`HubPoolInterface.sol:29-32`), off-chain only | T03 |
| G2 | Impl ⊄ Spec | `StoredCallData(target=spokeX, nonce=0)` (owner executed X's leaf) · `StoredCallData(target=0, nonce=end)` (another caller executed Y's leaf) · on X: `RelayedCallData(0)`, `RelayedRootBundle(k)`, `RelayedCallData(end)`, `RelayedRootBundle(k+1)` (same roots) · two `ExecutedRelayerRefundRoot` for one leaf | "all relayRootBundle calldata for this bundle gets stored to the same slot" (`HubPoolStore.sol:64-68`) | T04 |
| G3 | Impl ⊄ Spec | `EmergencyRootBundleDeleted` after X's leaf · on Y (whose leaf never executed): `RelayedCallData(end)` · `RelayedRootBundle` · `ExecutedRelayerRefundRoot` | deletion stops a bad bundle (`HubPool:224-228`) | T05 |
| G4 | Impl ⊄ Spec | spoke instance 2 on chain X, deployed later: `RelayedCallData(end)` for a historical nonce, with no new `StoredCallData` and no new `HeadUpdate` · `ExecutedRelayerRefundRoot` repeating a historical payment | replay protection "to prevent replay attacks" (`Universal_SpokePool.sol:38-40`) is per instance | T06 |
| G5 | Impl ⊄ Spec | owner: `SpokePoolAdminFunctionTriggered(pauseDeposits(false))`, then `(pauseDeposits(true))` · spoke: `RelayedCallData(1)` `PausedDeposits(true)` · `RelayedCallData(0)` `PausedDeposits(false)`; end state unpaused | last admin instruction governs (C1) | T07 |
| G6 | Impl ⊄ Spec | admin `executeExternalCall(token.transferAndCall(receiver))` · inside it: `Upgraded(evil)` emitted by the spoke proxy, called by `receiver` | "prevents calling the admin functions from any other method besides processMessageFromRoot" (`Polygon_SpokePool.sol:286-289`) | T08 (Polygon, Universal; Arbitrum control) |
| G7 | Impl ⊄ Spec | `RootBundleExecuted(bundleLpFees=f)` · `exchangeRateCurrent` in the same block rises by `f/S` | gradual smear (`HubPool:90-93`) | T02 |
| G8 | Impl ⊄ Spec | `ProtocolFeesCapturedClaimed(p)` · `liquidityUtilizationCurrent()=0` · `removeLiquidity(all)` reverts | utilization measures what is not withdrawable (`HubPool:507-528`) | T01 |
| G9 | Impl ⊄ Spec | `ProposeRootBundle` · `RootBundleDisputed` · `ProposeRootBundle`, all in one block · `RootBundleCanceled` with no second `DisputePrice` at the OO | a dispute stakes a bond and escalates (`HubPool:709-714`) | T09 |
| G10 | Impl ⊄ Spec | composed relaxation (pooled bond token, pct > 0): `RootBundleExecuted` leaves the hub with less than `bondAmount`; every later execute, delete and propose reverts | `emergencyDeleteProposal` exists so the contract is never "indefinitely blocked" (`HubPool:225-228`) | T10 |
| G11 | Impl ⊄ Spec (SVM vs EVM) | SVM: `FilledRelay(h)` · `close_fill_pda` · (clock decrease) · `FilledRelay(h)` | Filled is absorbing on EVM (F1) | model `F_fill[SVM]` |
| G12 | Impl ⊄ Spec (SVM vs EVM) | depositor's delegate approval · `FundsDeposited(depositId = id′ ≠ H(depositor, depositor, nonce))` submitted by a third party | unsafe id binds the chosen nonce (`SpokePool:644-660`) | model `D_unsafe_id[SVM]` |
| G13 | Impl ⊄ Spec (SVM) | `RelayedRootBundle` signed by `state.owner` with no HubPool execution | roots originate from HubPool `executeRootBundle` (`SpokePool:366-374`) | code (`constraints.rs:13-15`) |
| G14 | Impl ⊄ Spec (SVM) | any executor: `ExecutedRelayerRefundRoot(deferred_refunds=true)` with all transfers routable | EVM: deferral only on failed transfer (`SpokePool:1493-1500`) | code |
| G15 | Spec ⊄ Impl | deposit with a V5-tagged message whose length ≠ 64, or bound to an unexecuted step: `fillRelay`, `requestSlowFill` and `executeSlowRelayLeaf` revert `V5FillOnly`, and `_fillV5` reverts `V5CommitmentMismatch`. Only the expiry refund is enabled. | every deposit is fillable before its deadline (Lv2) | audit (§6.2) |
| G16 | Spec ⊄ Impl | Polygon: `executeRelayerRefundLeaf(amountToReturn>0)` from an EIP-7702-delegated EOA reverts `NotEOA` (`Polygon_SpokePool.sol:222-235`; `msg.sender.code.length > 0`) | anyone can execute a leaf | code |
| G17 | Spec ⊄ Impl | after `2^32 − 1` safe deposits on one instance, `deposit` reverts (checked `numberOfDeposits++`) | deposits always enabled unless paused | code (`SpokePool:557`) |
| G18 | Impl ⊄ Spec | the exclusivity window ends at `originBlockTime + offset`, judged on destination time; clock skew shifts it | exclusivity for `offset` seconds after the deposit | code (`SpokePool:1418-1422, 1655`) |

## 8. Structured findings

| Invariant | Status (labels in §0) | Counterexample / proof | Required assumptions (minimal) | Relaxation → counterexample | Refinement gap | Realized live? |
|---|---|---|---|---|---|---|
| F1 fill-once (EVM) | HOLDS/M+F | proof by write sites; T11 + C11 | ∅ | — (per-instance scope only) | — | — |
| F1 fill-once (SVM) | HOLDS/M | 6-step trace (§6.1) | {A_clk} | clock decrease → double fill | G11 | no (A_clk assumed) |
| F2 deadline | HOLDS (audit) | all payout paths check | A_t | uint32 wrap (2106) | — | — |
| F3 exclusivity | HOLDS (audit) | `_requireExclusiveFiller`, `1165` | A_clk, A_skew | clock skew shifts the window | G18 | depends on skew |
| F4 V5 quarantine | HOLDS (audit) | all V3 paths carry `nonV5Fill` | A_gw | — | G15 (dead keys) | — |
| R1 refund-once (native) | HOLDS/M; REFUTED/C when relaxed | 7- and 9-step traces | {A_V1, A_V2} | duplicate groupIndex-0 leaf; re-propose after delete | G1 | no (V enforced by disputers) |
| R1 refund-once (Universal, Tron) | HOLDS/M; REFUTED/C when relaxed | 7-, 7- and 9-step traces | {A_V2, A_exec, A_inst} (A_V1 not needed) | owner executes one leaf; second instance; re-propose | G2, G4 | A_exec: not prevented by code |
| R2 root authorization (native) | HOLDS/M | — | ∅ | — | — | — |
| R2 root authorization (Universal, Tron) | **REFUTED/C under all assumptions** | 4 steps; T05 | none | — | G3 | by design; harmful only with delete |
| R3 hub leaf-once | HOLDS (audit) | bitmap + checked decrement | ∅ | — | — | — |
| L1 equity | HOLDS/M | 4 steps when relaxed | {A_noHaircut} | haircut > N ⇒ rate reverts | — | owner power |
| L2 backing | HOLDS/M; REFUTED/C when relaxed | 4 steps; T01 | {A_pct0} | pct > 0 + claim before return | G8 | no (pct = 0) |
| L3 solvency | HOLDS/M | 2 steps when relaxed | {A_feesBacked} ⊂ A_V | unbacked `bundleLpFees` | — | no |
| L4 exit at zero utilization | HOLDS/M; REFUTED/C when relaxed | T01 | {A_noHaircut, A_pct0} | as L1, L2 | G8 | no |
| L5 rate monotone | HOLDS/M + proof | — | ∅ (haircut excluded) | — | — | — |
| L6 donation neutral | HOLDS/M + proof | — | ∅ | — | — | — |
| L7 smear from allocation | **REFUTED/C** | T02 | — | — | G7 | **yes** (≥ 0.27% per bundle at liveness 1800 s, up to 100%) |
| H1 window disjointness | HOLDS (proof) | complementary guards | ∅ | — | — | — |
| H2 bond custody | HOLDS/M + audit | — | ∅ (non-pooled bond) | see H4 | — | — |
| H3 dispute escalates | HOLDS/M; REFUTED/C when relaxed | 3/3/4/4 steps; T09 with the real UMA OO | {A_ff, A_hblk, A_ooOK, A_wl} | finalFee ≥ bond; UMA de-whitelist; same-block re-proposal; permissionless proposer | G9 | no (ABT whitelist, 0.055 < 0.45) |
| H4 hub liveness | HOLDS/M under either set; REFUTED/C when both relaxed | 4 steps; T10 | {A_bondNotPooled} ∨ {A_pct0} | both relaxed ⇒ permanent stop | G10 | no |
| A1 principal authority | principal spokes: HOLDS/M; flag spokes: REFUTED/C when relaxed | 3 steps; T08 | flag spokes: {A_closed} | admin `executeExternalCall` to a control-yielding target | G6 | Polygon, Universal, Tron if A_closed fails |
| A2 target binding | HOLDS (documented) | — | {A_addr} | equal spoke addresses on two chains | — | verified distinct |
| C1 last writer wins | HOLDS/M; REFUTED/C when relaxed | 2 steps; T07 | {A_fifo} | any two pending admin messages | G5 | Universal, Tron, SVM: no ordering by code |
| D1 id uniqueness | HOLDS per instance | checked `++` | `_initialDepositId` across instances | reused counter | G17 | — |
| D2 unsafe id binding (EVM) | HOLDS/M | — | ∅ | — | — | — |
| D2 unsafe id binding (SVM) | HOLDS/M; REFUTED/A when relaxed | 2 steps | {A_atomicAuth} | separate approve and deposit transactions | G12 | client-dependent |
| D3 speed-up binding | HOLDS under D1 ∧ no nonce reuse | — | as stated | reused id | — (documented) | — |

## 9. What the abstraction omits

- **Periphery and mint-burn systems.** `SpokePoolPeriphery`, `SwapAndBridge`, `MulticallHandler`, `HyperCoreFlowExecutor`, sponsored CCTP/OFT peripheries, counterfactual deposits, ERC-7683 settlers beyond `SpokePool.fill`, and the SVM `multicall-handler` and `sponsored-cctp-src-periphery` programs. They are clients of the deposit and fill interfaces. Their properties do not affect the key spaces above, except as additional `msg.sender` / `depositor` sources.
- **Adapter internals.** Adapters are modeled only by their channel properties: order, loss, replay scope. Bridge token semantics (`relayTokens`), gas payment, and per-bridge failure modes are environment. Arbitrum retryable expiry (7 days) is recorded under C2 and not modeled.
- **UMA beyond the request-id rule and fee payments.** The DVM vote and settlement are not modeled; A_V is taken as the attestation contract.
- **The Across V5 Gateway**, which lives outside this repository: summarized by A_gw.
- **Multi-token and multi-chain amounts.** The ledger layer is one token; root layers are two chains and one entitlement per chain. The properties concerned are per-key or per-token, so a single representative suffices (data-independence of the guards). Interactions across tokens, such as one bundle mixing a pooled bond token, are covered only where stated (H4).
- **Gas, the 63/64 rule, and gas griefing.** Not modeled. One case was checked by hand: forcing the OO call in `disputeRootBundle` to run out of gas so the catch path cancels is infeasible. To make the try-call run out of gas, the caller must forward less than `C_try ≈ 2×10^5` gas, which leaves it at most `C_try/63 ≈ 3.2×10^3` gas. `_cancelBundle` needs `C_catch ≈ 6×10^4`.
- **Hash collisions and second preimages** are excluded, i.e. keccak is collision-resistant. Merkle leaves are `keccak(abi.encode(struct))` of dynamic structs, always longer than 64 bytes, so leaf/node confusion is excluded by length. SVM leaves carry a 64-zero-byte prefix (`bundle.rs:79-99`, `slow_fill.rs:120-136`), so EVM and SVM leaves are domain-separated.
- **Concrete clocks, reorgs, and upgrades of the spokes themselves**, beyond A1.

## 10. Reproduction

```
cd analyses/across
python3 model/run.py model                                    # ~5 min, writes model/results.{json,md}
python3 model/sites.py <across checkout @ b1c4e86> model/sites.md
replay/setup.sh                                               # pinned checkout, deps, Foundry 1.7.1; T09 needs ETHERSCAN_API_KEY
replay/run.sh                                                 # 19 replay tests PASS, canary C11 FAILS
```

Recorded results at the target commit:

- `replay/run.sh`: **19 tests passed, 0 failed** across 11 replay suites; canary C11 failed as required.
- `model/run.py`: 20 (layer, invariant) entries, all explorations exhaustive.
- `model/sites.py`: all checks OK.
