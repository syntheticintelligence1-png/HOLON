// SPDX-License-Identifier: MIT
// HOLON I70 cutover harness (holon/cutover/harness.py; rules L2-L4 of the I70 contract, tests_m3/test_cutover_slash.py).
// The generic multi-target step harness (HolonBundleBase, I69's) on the real cutover bundle: the Rollup proxy over the
// V10 implementation (built from V10's commit, creation code from the input), migrated to the V11 implementation by the
// admin's upgradeToAndCall(initialize4); the legacy registry L1Staking (built from v0.6.1, creation code from the input)
// behind its own proxy; the head's messenger, queue, Whitelist and Submitter as I69's harness deploys them. Every proxy
// is an OpenZeppelin 4.9.3 TransparentUpgradeableProxy with the admin 0xAD. The verifier is an account with no code:
// the corpus calls it nowhere (every challenge in it times out), so a call to it would revert, never pass.
//
// holonDeploy returns the members in the cutover sidecar's order: rollup, messenger, queue, whitelist, submitter,
// l1staking. init is [t0, chainId, F, W, D, r0, stakingValue, challengeDeposit, lockBlocks, rewardPercentage, gasAdd,
// gasRemove, minimumStake, newChallengeDeposit, newRewardPercentage]. The input's codes are [V10, V11, L1Staking];
// trace 0 prints their runtime codes (R lines: a, b, registry), whose immutables the deployment record reads.
// Abstract rows: [1, who, version, parent, n, lbn, prev, post, nblobs, b1, b2, proof] a commit at the proxy's current
// version (V10: commitBatch(BatchDataInput, BatchSignatureInput) with an empty signature input; V11: commitBatch(input));
// [5, who, k, deposit] challengeState; [6, who, k, proof] proveState; [22, who] claimReward(who); [10, seconds] a wait;
// [11, blocks] a roll of the block number.
pragma solidity =0.8.24;

import {HolonBundleBase} from "./HolonBundleBase.sol";
import {HolonTraceReplayTest} from "./HolonTraceReplay.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {IRollup} from "../contracts/l1/rollup/IRollup.sol";
import {Submitter} from "../contracts/l1/rollup/Submitter.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {L1CrossDomainMessenger} from "../contracts/l1/L1CrossDomainMessenger.sol";
import {Whitelist} from "../contracts/libraries/common/Whitelist.sol";
import {EmptyContract} from "../contracts/misc/EmptyContract.sol";
import {TransparentUpgradeableProxy, ITransparentUpgradeableProxy} from
    "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

interface HolonLegacyRegistry {
    function initialize(address, uint256, uint256, uint256, uint256, uint256, uint256) external;
}

interface HolonRollVm {
    function roll(uint256) external;
}

interface HolonV10Rollup {
    function initialize(address, address, address, uint256, uint256, uint256) external;
    function initialize3(uint256) external;
}

contract HolonCutoverTest is HolonBundleBase, HolonTraceReplayTest {
    bytes32 internal constant IMPL_SLOT = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;
    bytes4 internal constant V10_COMMIT =
        bytes4(keccak256("commitBatch((uint8,bytes,uint64,uint16,bytes32,bytes32,bytes32),(uint256,bytes,bytes))"));

    struct LegacySignature {
        uint256 signedSequencersBitmap;
        bytes sequencerSets;
        bytes signature;
    }

    L1CrossDomainMessenger internal messenger;
    Submitter internal submitter;
    Whitelist internal whitelist;
    address internal registry;
    address internal v10;
    address internal v11;

    function proxyOver(address impl) internal returns (address) {
        return address(new TransparentUpgradeableProxy(impl, PROXY_ADMIN, ""));
    }

    function createFrom(bytes memory code) internal returns (address a) {
        assembly {
            a := create(0, add(code, 0x20), mload(code))
        }
        require(a != address(0), "HolonCutover: a creation failed");
    }

    function holonDeploy(uint256 tid, uint256[] memory init) internal override returns (address[] memory ms) {
        require(init.length == 15, "init: 15 values");
        bytes[] memory codes = BV.parseJsonBytesArray(BV.readFile(BV.envString("HOLON_STEPS_IN")), ".codes");
        require(codes.length == 3, "codes: [V10, V11, L1Staking]");
        HV.warp(EPOCH + init[0]);
        whitelist = new Whitelist(address(this));
        address empty = address(new EmptyContract());
        rollup = Rollup(payable(proxyOver(empty)));
        messenger = L1CrossDomainMessenger(payable(proxyOver(empty)));
        registry = proxyOver(empty);
        queue = L1MessageQueueWithGasPriceOracle(proxyOver(address(new L1MessageQueueWithGasPriceOracle(
            address(messenger), address(rollup), who2addr(8)))));
        L1CrossDomainMessenger mimpl = new L1CrossDomainMessenger();
        HV.prank(PROXY_ADMIN);
        ITransparentUpgradeableProxy(address(messenger)).upgradeTo(address(mimpl));
        queue.initialize(10_000_000, address(whitelist));
        messenger.initialize(who2addr(6), address(rollup), address(queue));
        v10 = createFrom(abi.encodePacked(codes[0], abi.encode(uint64(init[1]))));
        v11 = createFrom(abi.encodePacked(codes[1], abi.encode(uint64(init[1]))));
        address stk = createFrom(abi.encodePacked(codes[2], abi.encode(address(messenger))));
        HV.prank(PROXY_ADMIN);
        ITransparentUpgradeableProxy(address(rollup)).upgradeTo(v10);
        HV.prank(PROXY_ADMIN);
        ITransparentUpgradeableProxy(registry).upgradeTo(stk);
        submitter = Submitter(payable(proxyOver(address(new Submitter()))));
        HolonLegacyRegistry(registry).initialize(address(rollup), init[6], init[7], init[8], init[9], init[10],
                                                 init[11]);
        HolonV10Rollup(address(rollup)).initialize(registry, address(queue), address(0xFEE1), init[2], init[3], 70);
        HolonV10Rollup(address(rollup)).initialize3(init[4]);
        submitter.initialize(address(this), address(rollup), init[12], init[13], init[14]);
        address[] memory wl = new address[](1);
        wl[0] = registry;
        whitelist.updateWhitelistStatus(wl, true);
        rollup.addChallenger(who2addr(4));
        for (uint256 w = 2; w <= 9; w++) HV.deal(who2addr(w), 100 ether);
        bytes memory g = hdr(0, 0, bytes32(uint256(1)), ZVH, bytes32(init[5]));
        rollup.importGenesisBatch(g);
        hdrs[tid][0] = g;
        holonLine(string.concat("N ", dec(tid), " harness ", ha(address(this))));
        holonLine(string.concat("N ", dec(tid), " admin ", ha(PROXY_ADMIN)));
        holonLine(string.concat("N ", dec(tid), " v10 ", ha(v10)));
        holonLine(string.concat("N ", dec(tid), " v11 ", ha(v11)));
        holonLine(string.concat("N ", dec(tid), " verifier ", ha(address(0xFEE1))));
        if (tid == 0) {
            holonLine(string.concat("R ", dec(tid), " a ", hx(v10.code)));
            holonLine(string.concat("R ", dec(tid), " b ", hx(v11.code)));
            holonLine(string.concat("R ", dec(tid), " registry ", hx(stk.code)));
        }
        ms = new address[](6);
        ms[0] = address(rollup);
        ms[1] = address(messenger);
        ms[2] = address(queue);
        ms[3] = address(whitelist);
        ms[4] = address(submitter);
        ms[5] = registry;
    }

    function atNew() internal view returns (bool) {
        return address(uint160(uint256(BV.load(address(rollup), IMPL_SLOT)))) == v11;
    }

    function holonAbstract(uint256 tid, uint256, uint256[] memory s) internal override returns (bool, HolonCall memory c) {
        uint256 op = s[0];
        if (op == 10 || op == 11) return (false, c);
        c.caller = who2addr(s[1]);
        c.to = address(rollup);
        if (op == 1) {
            IRollup.BatchDataInput memory input = commitInput(tid, s, 0);
            if (atNew()) {
                c.data = abi.encodeCall(Rollup.commitBatch, (input));
            } else {
                LegacySignature memory sig = LegacySignature(0, legacySets(), "");
                c.data = abi.encodeWithSelector(V10_COMMIT, input, sig);
            }
        } else if (op == 5) {
            c.data = abi.encodeCall(Rollup.challengeState, (uint64(s[2]), keccak256(headerFor(tid, s[2]))));
            c.value = s[3];
        } else if (op == 6) {
            c.data = abi.encodeCall(Rollup.proveState, (headerFor(tid, s[2]), proofBytes(s[3])));
        } else if (op == 22) {
            c.data = abi.encodeCall(Rollup.claimReward, (who2addr(s[1])));
        } else {
            revert("HolonCutover: unknown abstract op");
        }
        return (true, c);
    }

    function holonAbstractEnv(uint256, uint256, uint256[] memory s) internal override {
        if (s[0] == 10) {
            HV.warp(block.timestamp + s[1]);
        } else if (s[0] == 11) {
            HolonRollVm(address(BV)).roll(block.number + s[1]);
        } else {
            revert("HolonCutover: unknown environment op");
        }
    }

    // the legacy commit's sequencer sets: an empty set at every height, the encoding its decoder takes
    function legacySets() internal pure returns (bytes memory) {
        return abi.encode(uint256(0), new address[](0), uint256(0), new address[](0), uint256(0), new address[](0));
    }

    function holonAfter(uint256 tid, uint256, uint256[] memory s, bool ok) internal override {
        if (!ok || s[0] != 1) return;
        uint256 idx = s[3] + 1;
        bytes memory h = newHeader(tid, s, 0, rollup.batchBlobVersionedHashes(idx));
        if (!atNew()) {
            // the legacy commit stores keccak256(sequencerSets) as the header's sequencer-set verify hash (bytes
            // 185..216), where the head's stores zero
            bytes32 v = keccak256(legacySets());
            for (uint256 i = 0; i < 32; i++) h[185 + i] = v[i];
        }
        hdrs[tid][idx] = h;
    }
}
