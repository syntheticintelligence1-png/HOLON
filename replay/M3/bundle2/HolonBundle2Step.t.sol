// SPDX-License-Identifier: MIT
// HOLON I80 refinement harness of Bundle II (holon/bundle2/harness.py; rules C1-C2 of
// tests_m3/test_bundle2_extraction.py; the sidecar spec/M3/lib/bundle2.json). It is the generic multi-member step base
// (HolonBundle2Base) on the real Rollup and the real verifier router, with I20's deployment and abstract-row translation
// (replay/M1/solidity/HolonTraceReplay.t.sol, inherited unchanged, and the translation of
// replay/M2/solidity/HolonExtractedStep.t.sol, copied below), except that the Rollup's verifier is the real router.
//
// b2Deploy: HolonTraceReplayTest.deploy's steps with the router (members, in the sidecar's order: [the Rollup proxy, the
// router]): the router is deployed by this contract (its owner) with the versions 0, 1 and 2 all mapped to the stand-in
// Z1, and initialized with the Rollup proxy; Z1 and Z2 are IZkEvmVerifier stand-ins that accept a proof whose first
// byte is 1 (Z1) or 2 (Z2), I20's verifier rule. init = [F, W, D, t0, r0].
// Abstract rows: ops 1-11 are I20's (ops 1-8 calls on the Rollup, 9-11 environment steps); ops 12-21 are I80's (the
// sidecar's corpus.rows).
pragma solidity =0.8.24;

import {HolonBundle2Base} from "./HolonBundle2Base.sol";
import {HolonTraceReplayTest, HolonSubmitterOracle} from "./HolonTraceReplay.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {MultipleVersionRollupVerifier} from "../contracts/l1/rollup/MultipleVersionRollupVerifier.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

/// Stand-in for the circuit (IZkEvmVerifier.verifyBatch): accepts iff the proof's first byte is k.
contract HolonZkStandIn {
    uint8 public immutable k;

    constructor(uint8 k_) {
        k = k_;
    }

    function verifyBatch(bytes calldata proof, bytes32) external view {
        require(proof.length > 0 && uint8(proof[0]) == k, "invalid proof");
    }
}

contract HolonBundle2StepTest is HolonBundle2Base, HolonTraceReplayTest {
    MultipleVersionRollupVerifier internal router;
    HolonZkStandIn internal z1;
    HolonZkStandIn internal z2;

    function b2Deploy(uint256 tid, uint256[] memory init) internal override returns (address[] memory m) {
        require(init.length == 5, "init: [F, W, D, t0, r0]");
        HV.warp(EPOCH + init[3]);
        sub = new HolonSubmitterOracle();
        sub.setActive(who2addr(2), true);
        sub.setActive(who2addr(3), true);
        z1 = new HolonZkStandIn(1);
        z2 = new HolonZkStandIn(2);
        uint256[] memory vs = new uint256[](3);
        address[] memory zs = new address[](3);
        for (uint256 i = 0; i < 3; i++) {
            vs[i] = i;
            zs[i] = address(z1);
        }
        router = new MultipleVersionRollupVerifier(vs, zs);
        Rollup impl = new Rollup(53077);
        rollup = Rollup(payable(address(new TransparentUpgradeableProxy(address(impl), PROXY_ADMIN, ""))));
        L1MessageQueueWithGasPriceOracle qimpl = new L1MessageQueueWithGasPriceOracle(MESSENGER, address(rollup), address(0xE7));
        queue = L1MessageQueueWithGasPriceOracle(address(new TransparentUpgradeableProxy(address(qimpl), PROXY_ADMIN, "")));
        queue.initialize(10_000_000, address(0));
        rollup.initialize(address(sub), address(queue), address(router), init[0], init[1], 70);
        router.initialize(address(rollup));
        rollup.updateRollupDelayPeriod(init[2]);
        rollup.addChallenger(who2addr(4));
        for (uint256 w = 2; w <= 5; w++) HV.deal(who2addr(w), 100 ether);
        bytes memory g = hdr(0, 0, bytes32(uint256(1)), ZVH, bytes32(init[4]));
        rollup.importGenesisBatch(g);
        hdrs[tid][0] = g;
        m = new address[](2);
        m[0] = address(rollup);
        m[1] = address(router);
    }

    function blobsOf(uint256[] memory s) internal pure returns (bytes32[] memory bh) {
        uint256 nb = s[8];
        bh = new bytes32[](nb);
        if (nb > 0) bh[0] = blobEnc(s[9]);
        if (nb > 1) bh[1] = blobEnc(s[10]);
    }

    function asel(uint256 k) internal view returns (address) {
        if (k == 1) return address(rollup);
        if (k == 2) return who2addr(5);
        if (k == 3) return address(router);
        return address(0);
    }

    function vsel(uint256 k) internal view returns (address) {
        if (k == 1) return address(z1);
        if (k == 2) return address(z2);
        if (k == 3) return who2addr(5);
        return address(0);
    }

    function b2Abstract(uint256 tid, uint256[] memory s)
        internal view override returns (bool, B2Call memory c, B2Poke[] memory pokes)
    {
        uint256 op = s[0];
        pokes = new B2Poke[](0);
        if (op == 0 || (op > 8 && op < 12) || op > 21) return (false, c, pokes);
        c.caller = who2addr(s[1]);
        c.to = address(rollup);
        c.blobs = new bytes32[](0);
        if (op <= 3) {
            // I20's translation (replay/M2/solidity/HolonExtractedStep.t.sol holonAbstract), copied
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
        } else if (op == 8) {
            c.data = abi.encodeCall(Rollup.setPause, (s[2] == 1));
        } else if (op == 12) {
            // I80's rows (spec/M3/lib/bundle2.json corpus.rows)
            c.data = abi.encodeCall(Rollup.proveCommittedBatchState, (headerFor(tid, s[2]), proofBytes(s[3])));
        } else {
            c.to = address(router);
            if (op == 13) {
                c.data = abi.encodeCall(MultipleVersionRollupVerifier.updateVerifier, (s[2], uint64(s[3]), vsel(s[4])));
            } else if (op == 14) {
                c.data = abi.encodeCall(MultipleVersionRollupVerifier.getVerifier, (s[2], s[3]));
            } else if (op == 15) {
                c.data = abi.encodeCall(MultipleVersionRollupVerifier.verifyAggregateProof,
                                        (s[2], s[3], proofBytes(s[4]), bytes32(s[5])));
            } else if (op == 16) {
                c.data = abi.encodeCall(MultipleVersionRollupVerifier.legacyVerifiersLength, (s[2]));
            } else if (op == 17 || op == 21) {
                c.data = abi.encodeCall(MultipleVersionRollupVerifier.initialize, (asel(s[2])));
                if (op == 21) {
                    pokes = new B2Poke[](1);
                    pokes[0] = B2Poke(address(router), bytes32(s[3]), bytes32(0));
                }
            } else if (op == 18) {
                c.data = abi.encodeWithSignature("transferOwnership(address)", asel(s[2]));
            } else if (op == 19) {
                c.data = abi.encodeWithSignature("renounceOwnership()");
            } else {
                c.data = abi.encodeWithSignature("owner()");
            }
        }
        return (true, c, pokes);
    }

    function b2AbstractEnv(uint256, uint256, uint256[] memory s) internal override {
        // I20's environment steps (replay/M2/solidity/HolonExtractedStep.t.sol holonAbstractEnv), copied
        uint256 op = s[0];
        if (op == 9) {
            HV.prank(MESSENGER);
            queue.appendCrossDomainMessage(address(0x7a), 1_000_000, "");
        } else if (op == 10) {
            HV.warp(block.timestamp + s[1]);
        } else if (op == 11) {
            legacyEta2(s[1]);
        } else {
            revert("HolonBundle2Step: unknown abstract op");
        }
    }

    function b2After(uint256 tid, uint256 id, uint256[] memory s, bool ok) internal override {
        // I20's bookkeeping (replay/M2/solidity/HolonExtractedStep.t.sol holonAfter), copied
        if (!ok || s[0] > 3) return;
        uint256 idx = s[3] + 1;
        bytes memory h = newHeader(tid, s, 0, rollup.batchBlobVersionedHashes(idx));
        hdrs[tid][idx] = h;
        if (keccak256(h) != rollup.committedBatches(idx)) {
            b2Line(string.concat("X ", b2pre(tid, id), "harness-mismatch"));
        }
    }
}
