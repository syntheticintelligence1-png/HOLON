// SPDX-License-Identifier: MIT
// HOLON I20 refinement harness for the extracted rollup document (holon/replay_fragments.py; binding
// replay/M2/fragments.json). It is the generic step harness (HolonStepBase) on the real Rollup, with the deployment and
// the abstract-row translation of the M1 trace harness (replay/M1/solidity/HolonTraceReplay.t.sol), both copied
// unchanged into a scratch copy of morph's contracts/ tree.
//
// holonDeploy: HolonTraceReplayTest.deploy (the real Rollup and L1MessageQueueWithGasPriceOracle behind proxies, the
// submitter and verifier stand-ins, initialize, the delay period, a challenger, the genesis batch), init = [F, W, D, t0,
// r0]. An abstract row is the M1 harness's step encoding (holon.mreplay.encode_step): ops 1-8 become calls on the Rollup,
// built exactly as HolonTraceReplayTest.step builds them, run and recorded by the generic executor; ops 9-11 (a queued
// message, a wait, the legacy reinitialisation) are environment steps. After a successful commit the header the harness
// rebuilt is kept for later steps, as the M1 harness does; a rebuilt header whose hash differs from the stored one is
// noted (X <tid> <id> harness-mismatch).
pragma solidity =0.8.24;

import {HolonStepBase} from "./HolonStepBase.sol";
import {HolonTraceReplayTest} from "./HolonTraceReplay.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";

contract HolonExtractedStepTest is HolonStepBase, HolonTraceReplayTest {
    function holonDeploy(uint256 tid, uint256[] memory init) internal override returns (address) {
        require(init.length == 5, "init: [F, W, D, t0, r0]");
        deploy(tid, init[0], init[1], init[2], init[3], init[4]);
        return address(rollup);
    }

    function blobsOf(uint256[] memory s) internal pure returns (bytes32[] memory bh) {
        uint256 nb = s[8];
        bh = new bytes32[](nb);
        if (nb > 0) bh[0] = blobEnc(s[9]);
        if (nb > 1) bh[1] = blobEnc(s[10]);
    }

    function holonAbstract(uint256 tid, uint256[] memory s) internal view override returns (bool, HolonCall memory c) {
        uint256 op = s[0];
        if (op == 0 || op > 8) return (false, c);
        c.caller = who2addr(s[1]);
        c.to = address(rollup);
        c.blobs = new bytes32[](0);
        if (op <= 3) {
            c.blobs = blobsOf(s);
            if (op == 1) {
                c.data = abi.encodeCall(Rollup.commitBatch, (commitInput(tid, s, 0)));
            } else if (op == 2) {
                c.data = abi.encodeCall(Rollup.commitState, (commitInput(tid, s, 0)));
            } else {
                bytes memory nh = newHeader(tid, s, 0, expectedBlob(s, 0));
                c.data = abi.encodeCall(Rollup.commitBatchWithProof, (commitInput(tid, s, 0), nh, proofBytes(s[11])));
            }
        } else if (op == 4) {
            c.data = abi.encodeCall(Rollup.revertBatch, (headerFor(tid, s[2]), s[3]));
        } else if (op == 5) {
            c.data = abi.encodeCall(Rollup.challengeState, (uint64(s[2]), keccak256(headerFor(tid, s[2]))));
            c.value = s[3];
        } else if (op == 6) {
            c.data = abi.encodeCall(Rollup.proveState, (headerFor(tid, s[2]), proofBytes(s[3])));
        } else if (op == 7) {
            c.data = abi.encodeCall(Rollup.finalizeBatch, (headerFor(tid, s[2])));
        } else {
            c.data = abi.encodeCall(Rollup.setPause, (s[2] == 1));
        }
        return (true, c);
    }

    function holonAbstractEnv(uint256, uint256, uint256[] memory s) internal override {
        uint256 op = s[0];
        if (op == 9) {
            HV.prank(MESSENGER);
            queue.appendCrossDomainMessage(address(0x7a), 1_000_000, "");
        } else if (op == 10) {
            HV.warp(block.timestamp + s[1]);
        } else if (op == 11) {
            legacyEta2(s[1]);
        } else {
            revert("HolonExtractedStep: unknown abstract op");
        }
    }

    function holonAfter(uint256 tid, uint256 id, uint256[] memory s, bool ok) internal override {
        if (!ok || s[0] > 3) return;
        uint256 idx = s[3] + 1;
        bytes memory h = newHeader(tid, s, 0, rollup.batchBlobVersionedHashes(idx));
        hdrs[tid][idx] = h;
        if (keccak256(h) != rollup.committedBatches(idx)) {
            holonLine(string.concat("X ", pre(tid, id), "harness-mismatch"));
        }
    }
}

/// Last-step mode (holon.replay_fragments.locate_panics): one trace, its last step alone in test_last.
contract HolonExtractedLastTest is HolonExtractedStepTest {
    function setUp() public {
        holonSetUpLast();
    }

    function test_last() public {
        holonRunLast();
    }
}
