// SPDX-License-Identifier: MIT
// HOLON I69 bundle harness (holon/bundle/harness.py; rules C1-C4 of the I69 contract). The generic multi-target step
// harness (HolonBundleBase) on the real bundle: the Rollup, the cross-domain messenger, the message queue and the
// Submitter behind OpenZeppelin TransparentUpgradeableProxy contracts with the admin 0xAD, the real Whitelist and I20's
// verifier stand-in, deployed as the bundle sidecar's deployment section says (spec/M3/lib/bundle.json), with the
// abstract-row helpers of the M1 trace harness (replay/M1/solidity/HolonTraceReplay.t.sol, copied unchanged).
//
// holonDeploy returns the members in the sidecar's order: rollup, messenger, queue, whitelist, submitter. init is
// [F, W, D, t0, r0]. Abstract rows are the M1 harness's encoding (holon.mreplay.encode_step): ops 1-8 are calls on the
// Rollup, built as I20's HolonExtractedStep builds them; op 9 (a sent message) is the messenger's
// sendMessage(address,uint256,bytes,uint256)(0x7a, 0, empty, 1000000) by the row's actor with no value; ops 10 (a
// wait) and 11 (the legacy reinitialisation) are environment steps.
pragma solidity =0.8.24;

import {HolonBundleBase} from "./HolonBundleBase.sol";
import {HolonTraceReplayTest, HolonVerifierOracle} from "./HolonTraceReplay.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {Submitter} from "../contracts/l1/rollup/Submitter.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {L1CrossDomainMessenger} from "../contracts/l1/L1CrossDomainMessenger.sol";
import {Whitelist} from "../contracts/libraries/common/Whitelist.sol";
import {EmptyContract} from "../contracts/misc/EmptyContract.sol";
import {TransparentUpgradeableProxy, ITransparentUpgradeableProxy} from
    "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

contract HolonBundleTest is HolonBundleBase, HolonTraceReplayTest {
    L1CrossDomainMessenger internal messenger;
    Submitter internal submitter;
    Whitelist internal whitelist;

    function proxyOver(address impl) internal returns (address) {
        return address(new TransparentUpgradeableProxy(impl, PROXY_ADMIN, ""));
    }

    function holonDeploy(uint256 tid, uint256[] memory init) internal override returns (address[] memory ms) {
        require(init.length == 5, "init: [F, W, D, t0, r0]");
        HV.warp(EPOCH + init[3]);
        whitelist = new Whitelist(address(this));
        HolonVerifierOracle ver = new HolonVerifierOracle();
        holonLine(string.concat("N ", dec(tid), " verifier ", ha(address(ver))));
        holonLine(string.concat("N ", dec(tid), " harness ", ha(address(this))));
        holonLine(string.concat("N ", dec(tid), " admin ", ha(PROXY_ADMIN)));
        rollup = Rollup(payable(proxyOver(address(new Rollup(53077)))));
        submitter = Submitter(payable(proxyOver(address(new Submitter()))));
        messenger = L1CrossDomainMessenger(payable(proxyOver(address(new EmptyContract()))));
        queue = L1MessageQueueWithGasPriceOracle(proxyOver(address(new L1MessageQueueWithGasPriceOracle(
            address(messenger), address(rollup), who2addr(8)))));
        L1CrossDomainMessenger mimpl = new L1CrossDomainMessenger();
        HV.prank(PROXY_ADMIN);
        ITransparentUpgradeableProxy(address(messenger)).upgradeTo(address(mimpl));
        queue.initialize(10_000_000, address(whitelist));
        messenger.initialize(who2addr(6), address(rollup), address(queue));
        submitter.initialize(address(this), address(rollup), 1 ether, 1, 20);
        rollup.initialize(address(submitter), address(queue), address(ver), init[0], init[1], 70);
        rollup.updateRollupDelayPeriod(init[2]);
        rollup.addChallenger(who2addr(4));
        for (uint256 w = 2; w <= 9; w++) HV.deal(who2addr(w), 100 ether);
        submitter.addSubmitter(who2addr(2));
        submitter.addSubmitter(who2addr(3));
        HV.prank(who2addr(2));
        submitter.stake{value: 1 ether}(who2addr(2));
        HV.prank(who2addr(3));
        submitter.stake{value: 1 ether}(who2addr(3));
        bytes memory g = hdr(0, 0, bytes32(uint256(1)), ZVH, bytes32(init[4]));
        rollup.importGenesisBatch(g);
        hdrs[tid][0] = g;
        ms = new address[](5);
        ms[0] = address(rollup);
        ms[1] = address(messenger);
        ms[2] = address(queue);
        ms[3] = address(whitelist);
        ms[4] = address(submitter);
    }

    function blobsOf(uint256[] memory s) internal pure returns (bytes32[] memory bh) {
        uint256 nb = s[8];
        bh = new bytes32[](nb);
        if (nb > 0) bh[0] = blobEnc(s[9]);
        if (nb > 1) bh[1] = blobEnc(s[10]);
    }

    function holonAbstract(uint256 tid, uint256, uint256[] memory s) internal override returns (bool, HolonCall memory c) {
        uint256 op = s[0];
        if (op == 0 || op > 9) return (false, c);
        c.caller = who2addr(s[1]);
        c.to = address(rollup);
        if (op <= 3) {
            HV.blobhashes(blobsOf(s));
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
        } else {
            c.to = address(messenger);
            c.data = abi.encodeWithSignature("sendMessage(address,uint256,bytes,uint256)", address(0x7a), uint256(0),
                                             bytes(""), uint256(1_000_000));
        }
        return (true, c);
    }

    function holonAbstractEnv(uint256, uint256, uint256[] memory s) internal override {
        uint256 op = s[0];
        if (op == 10) {
            HV.warp(block.timestamp + s[1]);
        } else if (op == 11) {
            legacyEta2(s[1]);
        } else {
            revert("HolonBundle: unknown abstract op");
        }
    }

    function holonAfter(uint256 tid, uint256, uint256[] memory s, bool ok) internal override {
        bytes32[] memory none = new bytes32[](0);
        HV.blobhashes(none);
        if (!ok || s[0] > 3) return;
        uint256 idx = s[3] + 1;
        hdrs[tid][idx] = newHeader(tid, s, 0, rollup.batchBlobVersionedHashes(idx));
    }
}
