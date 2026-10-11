// SPDX-License-Identifier: MIT
pragma solidity =0.8.24;

import {Test, console2} from "forge-std/Test.sol";
import {ERC1967Proxy} from "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {Submitter} from "../contracts/l1/rollup/Submitter.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {IRollup} from "../contracts/l1/rollup/IRollup.sol";

contract AcceptAllVerifier {
    function verifyAggregateProof(uint256, uint256, bytes calldata, bytes32) external view {}
}

contract AllowAllWhitelist {
    function isSenderAllowed(address) external view returns (bool) {
        return true;
    }
}

// Real L1 message queue (constructor args are plain addresses; the messenger is
// impersonated with vm.prank to enqueue).
contract HolonM1Replay is Test {
    bytes32 internal constant ZERO_VERSIONED_HASH =
        0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014;

    // Facts config: D=3, F=2, P=2, genesis at now=1.
    uint64 internal constant CHAIN_ID = 53077;
    address internal constant MESSENGER = address(0xA1CE);
    address internal constant GATEWAY = address(0x6A7E);
    address internal constant SUBMITTER = address(0x5E9);
    address internal constant CHALLENGER = address(0xC4A11);

    Rollup internal rollup; // proxy
    Submitter internal submitter; // proxy
    L1MessageQueueWithGasPriceOracle internal queue;
    bytes internal genesisHeader; // V0, index 0
    bytes32 internal prevRoot = bytes32(uint256(0xbeef));
    bytes32 internal withdrawRoot = bytes32(uint256(0x77aa));

    // ---------- header codec (matches contract field layout) ----------
    function mkV0Header(
        uint64 index, uint64 popped, uint64 total, bytes32 dataHash,
        bytes32 blobVH, bytes32 prev, bytes32 post, bytes32 wr,
        bytes32 ssvh, bytes32 parentHash
    ) internal pure returns (bytes memory h) {
        h = abi.encodePacked(
            uint8(0), index, popped, total, dataHash, blobVH, prev, post, wr, ssvh, parentHash
        );
        require(h.length == 249, "v0 header length");
    }

    function mkV1Header(
        uint8 version, uint64 index, uint64 popped, uint64 total, bytes32 dataHash,
        bytes32 blobVH, bytes32 prev, bytes32 post, bytes32 wr,
        bytes32 ssvh, bytes32 parentHash, uint64 lastBlock
    ) internal pure returns (bytes memory h) {
        h = abi.encodePacked(
            version, index, popped, total, dataHash, blobVH, prev, post, wr, ssvh,
            parentHash, lastBlock
        );
        require(h.length == 257, "v1 header length");
    }

    // dataHash the contract computes for a batch: keccak(lastBlock||numL1||msg hashes)
    function dataHashOf(uint64 lastBlock, uint16 numL1, uint64 startIndex) internal view returns (bytes32) {
        bytes memory packed = abi.encodePacked(bytes8(lastBlock), bytes2(numL1));
        for (uint16 i = 0; i < numL1; i++) {
            packed = abi.encodePacked(packed, queue.getCrossDomainMessage(startIndex + i));
        }
        return keccak256(packed);
    }

    // header bytes for the batch the contract would have committed
    function committedHeader(
        uint8 version, uint64 index, uint16 numL1, uint64 total, bytes32 blobVH,
        bytes32 prev, bytes32 post, bytes memory parentHeader, uint64 lastBlock
    ) internal view returns (bytes memory) {
        return mkV1Header(
            version, index, uint64(numL1), total, dataHashOf(lastBlock, numL1, total - numL1),
            blobVH, prev, post, withdrawRoot, bytes32(0), keccak256(parentHeader), lastBlock
        );
    }

    function batchDataInput(uint8 version, bytes memory parent, uint16 numL1, bytes32 prev, bytes32 post)
        internal view returns (IRollup.BatchDataInput memory)
    {
        return IRollup.BatchDataInput({
            version: version,
            parentBatchHeader: parent,
            lastBlockNumber: uint64(1000 + rollup.lastCommittedBatchIndex()),
            numL1Messages: numL1,
            prevStateRoot: prev,
            postStateRoot: post,
            withdrawalRoot: withdrawRoot
        });
    }

    function setUp() public {
        vm.warp(1); // model init now=1
        vm.deal(SUBMITTER, 10 ether);

        // Rollup proxy first (queue needs the address for its immutable).
        Rollup impl = new Rollup(CHAIN_ID);
        rollup = Rollup(payable(new ERC1967Proxy(address(impl), "")));

        L1MessageQueueWithGasPriceOracle qImpl =
            new L1MessageQueueWithGasPriceOracle(MESSENGER, address(rollup), GATEWAY);
        queue = L1MessageQueueWithGasPriceOracle(
            address(
                new ERC1967Proxy(
                    address(qImpl),
                    abi.encodeCall(L1MessageQueueWithGasPriceOracle.initialize,
                        (30_000_000, address(new AllowAllWhitelist())))
                )
            )
        );

        Submitter sImpl = new Submitter();
        submitter = Submitter(
            payable(
                new ERC1967Proxy(
                    address(sImpl),
                    abi.encodeCall(Submitter.initialize,
                        (address(this), address(rollup), 1 wei, 1 wei, 50))
                )
            )
        );
        submitter.addSubmitter(SUBMITTER);
        vm.prank(SUBMITTER);
        submitter.stake{value: 1 ether}(SUBMITTER);
        assertTrue(submitter.isActive(SUBMITTER));

        rollup.initialize(address(submitter), address(queue),
            address(new AcceptAllVerifier()), 2, 2, 1);
        rollup.initialize3(3); // rollupDelayPeriod = D = 3
        rollup.addChallenger(CHALLENGER);

        genesisHeader = mkV0Header(
            0, 0, 0, bytes32(uint256(0xda7a)), ZERO_VERSIONED_HASH,
            bytes32(0), prevRoot, withdrawRoot, bytes32(0), bytes32(0)
        );
        rollup.importGenesisBatch(genesisHeader);
        assertEq(rollup.lastCommittedBatchIndex(), 0);
        assertEq(rollup.lastFinalizedBatchIndex(), 0);
    }

    // ---------- L_undo_commit_revert + L_undo_enabled ----------
    // Model witness: commitBatch(0,1) then revertBatch(1,1) leaves residue.
    function test_undo_commit_revert_and_enabled() public {
        bytes32 post1 = bytes32(uint256(0x1001));
        IRollup.BatchDataInput memory di = batchDataInput(1, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di);
        bytes memory h1 = committedHeader(1, 1, 0, 0, ZERO_VERSIONED_HASH, prevRoot, post1, genesisHeader, 1000);
        assertEq(rollup.committedBatches(1), keccak256(h1));

        vm.prank(address(this));
        rollup.revertBatch(h1, 1);
        assertEq(rollup.lastCommittedBatchIndex(), 0);
        assertEq(rollup.committedBatches(1), bytes32(0));
        // Claim failure: blob hash + batch data + state root residue remains.
        assertTrue(rollup.batchBlobVersionedHashes(1) != bytes32(0), "blob hash residue");
        (uint256 origin, uint256 finTs,,) = rollup.batchDataStore(1);
        assertTrue(origin != 0 && finTs != 0, "batchDataStore residue");
        assertEq(rollup.committedStateRoots(1), post1, "state root residue");

        // L_undo_enabled: commitBatch now reverts; commitState works.
        IRollup.BatchDataInput memory di2 = batchDataInput(1, genesisHeader, 0, prevRoot, bytes32(uint256(0x2002)));
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("commitBatch requires no stored blob hash"));
        rollup.commitBatch(di2);

        vm.prank(SUBMITTER);
        rollup.commitState(di2);
        assertEq(rollup.lastCommittedBatchIndex(), 1);
        console2.log("OBSERVED undo_enabled: commitBatch reverted, commitState recommitted batch 1");
    }

    // ---------- L_undo_pause ----------
    // Model witness: commit x2, challenge(1), pause, unpause leaves +proofWindow.
    function test_undo_pause() public {
        bytes32 post1 = bytes32(uint256(0x1001));
        bytes32 post2 = bytes32(uint256(0x1002));
        IRollup.BatchDataInput memory di = batchDataInput(1, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di);
        bytes memory h1 = committedHeader(1, 1, 0, 0, ZERO_VERSIONED_HASH, prevRoot, post1, genesisHeader, 1000);
        IRollup.BatchDataInput memory di2 = batchDataInput(1, h1, 0, post1, post2);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di2);
        bytes memory h2 = committedHeader(1, 2, 0, 0, ZERO_VERSIONED_HASH, post1, post2, h1, 1001);
        assertEq(rollup.committedBatches(2), keccak256(h2));

        (, uint256 finBefore,,) = rollup.batchDataStore(2);
        assertEq(finBefore, 3, "batch2 fin_ts = now(1) + F(2)");

        bytes32 hash1 = rollup.committedBatches(1);
        vm.deal(CHALLENGER, 1 ether);
        vm.prank(CHALLENGER);
        rollup.challengeState{value: 1 wei}(1, hash1);
        (, uint256 finAfterChal,,) = rollup.batchDataStore(2);
        assertEq(finAfterChal, 5, "batch2 fin_ts +proofWindow");

        rollup.setPause(true);
        assertFalse(rollup.inChallenge());
        rollup.setPause(false);
        (, uint256 finAfterUnpause,,) = rollup.batchDataStore(2);
        assertEq(finAfterUnpause, 5, "pause left +proofWindow residue on batch2");

        // Extra observation (the "repeat" part of the prediction): the batch
        // can be challenged again and batch 2 extended a second time.
        vm.prank(CHALLENGER);
        rollup.challengeState{value: 1 wei}(1, hash1);
        (, uint256 finAgain,,) = rollup.batchDataStore(2);
        assertEq(finAgain, 7, "batch2 extended a second time after re-challenge");
        console2.log("OBSERVED undo_pause: fin_ts residue 5, re-challenge -> 7");
    }

    // ---------- L_disch_nonowner ----------
    // Model trace: commitBatch(0,1) -> challengeState(1) -> tick(2) -> proveState(1)
    function test_disch_nonowner() public {
        bytes32 post1 = bytes32(uint256(0x1001));
        IRollup.BatchDataInput memory di = batchDataInput(1, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di);
        bytes memory h1 = committedHeader(1, 1, 0, 0, ZERO_VERSIONED_HASH, prevRoot, post1, genesisHeader, 1000);

        vm.deal(CHALLENGER, 1 ether);
        bytes32 bh1 = rollup.committedBatches(1);
        vm.prank(CHALLENGER);
        rollup.challengeState{value: 1 wei}(1, bh1);

        vm.warp(3); // start(1) + P(2) <= now(3): challenger wins by timeout
        vm.prank(SUBMITTER);
        rollup.proveState(h1, hex"01");
        assertEq(rollup.revertReqIndex(), 1);
        assertFalse(submitter.isActive(SUBMITTER), "submitter slashed");

        // Every nonReqRevert transition now reverts "pending revert request".
        bytes memory h2 = new bytes(0);
        IRollup.BatchDataInput memory di2 = batchDataInput(1, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("only active submitter allowed")); // slashed submitter blocked first
        rollup.commitBatch(di2);
        // A re-registered active submitter is then stopped by nonReqRevert:
        submitter.addSubmitter(SUBMITTER);
        vm.prank(SUBMITTER);
        submitter.stake{value: 1 ether}(SUBMITTER);
        assertTrue(submitter.isActive(SUBMITTER));
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("pending revert request"));
        rollup.commitBatch(di2);
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("pending revert request"));
        rollup.commitState(di2);
        vm.expectRevert(bytes("pending revert request"));
        rollup.commitBatchWithProof(di2, h2, hex"01");
        bytes32 bh1b = rollup.committedBatches(1);
        vm.prank(CHALLENGER);
        vm.expectRevert(bytes("pending revert request"));
        rollup.challengeState{value: 1 wei}(1, bh1b);
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("pending revert request"));
        rollup.proveState(h1, hex"01");
        vm.expectRevert(bytes("pending revert request"));
        rollup.finalizeBatch(h1);

        // Only the owner (revertBatch) clears it.
        rollup.revertBatch(h1, 1);
        assertEq(rollup.revertReqIndex(), 0);
        console2.log("OBSERVED disch_nonowner: all non-owner paths reverted; owner revertBatch cleared");
    }

    // ---------- L_disch_timeout ----------
    // Model trace: commitBatch(0,1) -> challengeState(1) -> tick(1) -> tick(2)
    function test_disch_timeout() public {
        bytes32 post1 = bytes32(uint256(0x1001));
        IRollup.BatchDataInput memory di = batchDataInput(1, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di);
        bytes memory h1 = committedHeader(1, 1, 0, 0, ZERO_VERSIONED_HASH, prevRoot, post1, genesisHeader, 1000);

        vm.deal(CHALLENGER, 1 ether);
        bytes32 bh1 = rollup.committedBatches(1);
        vm.prank(CHALLENGER);
        rollup.challengeState{value: 1 wei}(1, bh1);

        vm.warp(5); // start(1)+P(2) < now(5): challenge timed out, still inChallenge
        assertTrue(rollup.inChallenge());

        // commitBatch underflows proveRemainingTime = P + start - now.
        IRollup.BatchDataInput memory di2 = batchDataInput(1, h1, 0, post1, post1);
        vm.prank(SUBMITTER);
        vm.expectRevert(abi.encodeWithSignature("Panic(uint256)", 0x11));
        rollup.commitBatch(di2);

        // commitBatchWithProof reaches _commitBatchWithBatchData (rollupDelay
        // holds: origin[1]=1 + D=3 < 4) and panics the same way.
        vm.expectRevert(abi.encodeWithSignature("Panic(uint256)", 0x11));
        rollup.commitBatchWithProof(di2, h1, hex"01");

        vm.prank(CHALLENGER);
        vm.expectRevert(bytes("already in challenge"));
        rollup.challengeState{value: 1 wei}(1, bh1);

        // Owner pause clears the challenge with no slash.
        rollup.setPause(true);
        assertFalse(rollup.inChallenge());
        assertTrue(submitter.isActive(SUBMITTER), "submitter not slashed by pause");
        console2.log("OBSERVED disch_timeout: Panic(0x11) on both commit paths; setPause cleared");
    }

    // ---------- L_nat_delay_frontier ----------
    // Model trace: enqueue() -> commitBatch(1,1) -> tick(2) -> tick(2)
    function test_nat_delay_frontier() public {
        vm.prank(MESSENGER);
        queue.appendCrossDomainMessage(address(0xBEEF), 250_000, hex"");
        assertEq(queue.nextCrossDomainMessageIndex(), 1);

        bytes32 post1 = bytes32(uint256(0x1001));
        IRollup.BatchDataInput memory di = batchDataInput(1, genesisHeader, 1, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di); // pops msg 0
        bytes memory h1 = committedHeader(1, 1, 1, 1, ZERO_VERSIONED_HASH, prevRoot, post1, genesisHeader, 1000);
        assertEq(rollup.committedBatches(1), keccak256(h1));

        vm.warp(5); // enqueueTime=1 + D=3 < now=5
        bytes32 post2 = bytes32(uint256(0x1002));
        IRollup.BatchDataInput memory di2 = batchDataInput(1, h1, 0, post1, post2);
        vm.prank(SUBMITTER);
        vm.expectRevert(bytes("l1msg delay"));
        rollup.commitBatch(di2);

        // Permissionless finalizeBatch of batch 1 (fin_ts=3 < 5) pops the
        // message and lifts the delay guard: delay, not freeze.
        rollup.finalizeBatch(h1);
        assertEq(rollup.lastFinalizedBatchIndex(), 1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di2);
        assertEq(rollup.lastCommittedBatchIndex(), 2);
        console2.log("OBSERVED nat_delay_frontier: l1msg delay then lifted by finalize");
    }

    // ---------- M0 closure: real commitBatch at version 2 ----------
    function test_v2_composed_header() public {
        bytes32[] memory blobs = new bytes32[](1);
        blobs[0] = bytes32(uint256(0xB10B));
        vm.blobhashes(blobs);

        bytes32 post1 = bytes32(uint256(0x1001));
        IRollup.BatchDataInput memory di = batchDataInput(2, genesisHeader, 0, prevRoot, post1);
        vm.prank(SUBMITTER);
        rollup.commitBatch(di);
        assertEq(rollup.lastCommittedBatchIndex(), 1);

        bytes32 agg = keccak256(abi.encodePacked(blobs[0]));
        bytes memory h1 = committedHeader(2, 1, 0, 0, agg, prevRoot, post1, genesisHeader, 1000);
        assertEq(uint8(h1[0]), 2, "byte0 == 2");
        bytes32 ssvh;
        assembly { ssvh := mload(add(add(h1, 32), 185)) }
        assertEq(ssvh, bytes32(0), "ssvh == 0");
        assertEq(rollup.committedBatches(1), keccak256(h1), "header bytes hash == committed hash");
        assertEq(rollup.batchBlobVersionedHashes(1), agg, "aggregated blob hash stored");
        console2.log("OBSERVED v2 closure: byte0=2, ssvh=0, committed hash matches constructed header");
        emit log_named_bytes("V2_HEADER", h1);
    }
}
