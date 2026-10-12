// SPDX-License-Identifier: MIT
// HOLON M3 NAT replay (Solidity side). Copied into a scratch copy of the pinned morph
// contracts/ tree and run with `forge test --match-contract HolonNatReplay -vv`.
//
// Deploys the REAL Rollup and the REAL Submitter behind TransparentUpgradeableProxies
// administered by a REAL OZ ProxyAdmin, plus the REAL L1MessageQueueWithGasPriceOracle.
// The pre-cutover registry is the same HolonSubmitterOracle stand-in the M1 harness uses
// (the pinned tree ships no legacy staking contract; it is not under test). The verifier
// is the M1 HolonVerifierOracle stand-in for the same reason. No vm.store, no mocks of
// the contracts under test. Logs:
//   HOLON <tag> <step> ok <detail> / HOLON <tag> <step> rev <reason>
pragma solidity =0.8.24;

import {Test, console} from "forge-std/Test.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {IRollup} from "../contracts/l1/rollup/IRollup.sol";
import {Submitter} from "../contracts/l1/rollup/Submitter.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {TransparentUpgradeableProxy, ITransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";
import {ProxyAdmin} from "@openzeppelin/contracts/proxy/transparent/ProxyAdmin.sol";

interface HolonVm {
    function warp(uint256) external;
    function prank(address) external;
    function deal(address, uint256) external;
    function toString(uint256) external pure returns (string memory);
    function toString(bytes memory) external pure returns (string memory);
}

/// Stand-in for the PRE-cutover registry (legacy staking): not under test.
contract HolonSubmitterOracle {
    mapping(address => bool) public active;
    function setActive(address a, bool v) external { active[a] = v; }
    function isActive(address s) external view returns (bool) { return active[s]; }
    function challengeDeposit() external pure returns (uint256) { return 1; }
    function slash(address s) external returns (uint256) { active[s] = false; return 0; }
}

/// Stand-in verifier: accepts proofs whose first byte is 0x01 (not under test).
contract HolonVerifierOracle {
    function verifyAggregateProof(uint256, uint256, bytes calldata proof, bytes32) external pure {
        require(proof.length > 0 && proof[0] == 0x01, "invalid proof");
    }
}

contract HolonNatReplayTest is Test {
    HolonVm internal constant HV = HolonVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    uint256 internal constant EPOCH = 1_700_000_000;
    bytes32 internal constant ZVH = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014;
    address internal constant MESSENGER = address(0xBEEF);
    address internal constant BOB = address(0xB0B);    // legacy submitter (model's 2)
    address internal constant CAROL = address(0xCA);   // new-registry submitter (model's 7)
    address internal constant CHAL = address(0xC4);    // challenger
    uint256 internal constant MIN_STAKE = 1 ether;
    uint256 internal constant CD = 0.1 ether;
    uint256 internal constant REWARD_PCT = 50;
    uint256 internal constant PROOF_WINDOW = 10;

    Rollup internal impl;
    Rollup internal rollup;
    L1MessageQueueWithGasPriceOracle internal queue;
    ProxyAdmin internal admin;
    HolonSubmitterOracle internal legacy;
    Submitter internal submitter;
    bytes internal genesis;

    function enc(uint256 v, uint256 idx, bytes32 dh, bytes32 blob, bytes32 prev, bytes32 post, bytes32 parent)
        internal pure returns (bytes memory h)
    {
        h = abi.encodePacked(uint8(v), uint64(idx), uint64(0), uint64(0), dh, blob, prev, post);
        h = abi.encodePacked(h, bytes32(0), bytes32(0), parent);
    }

    function dataHash0(uint256 lbn) internal pure returns (bytes32) {
        return keccak256(abi.encodePacked(uint64(lbn), uint16(0)));
    }

    function deploy() internal {
        HV.warp(EPOCH);
        legacy = new HolonSubmitterOracle();
        legacy.setActive(BOB, true);
        HolonVerifierOracle ver = new HolonVerifierOracle();
        admin = new ProxyAdmin();
        impl = new Rollup(53077);
        rollup = Rollup(payable(address(new TransparentUpgradeableProxy(address(impl), address(admin), ""))));
        L1MessageQueueWithGasPriceOracle qimpl =
            new L1MessageQueueWithGasPriceOracle(MESSENGER, address(rollup), address(0xE7));
        queue = L1MessageQueueWithGasPriceOracle(address(new TransparentUpgradeableProxy(address(qimpl), address(admin), "")));
        queue.initialize(10_000_000, address(0));
        rollup.initialize(address(legacy), address(queue), address(ver), 40, PROOF_WINDOW, 70);
        rollup.updateRollupDelayPeriod(20);
        rollup.addChallenger(CHAL);
        genesis = enc(0, 0, bytes32(uint256(1)), ZVH, bytes32(0), bytes32(uint256(100)), bytes32(0));
        rollup.importGenesisBatch(genesis);
        // new registry: real Submitter behind a proxy, Carol registered and staked
        Submitter simpl = new Submitter();
        submitter = Submitter(payable(address(new TransparentUpgradeableProxy(address(simpl), address(admin), ""))));
        submitter.initialize(address(this), address(rollup), MIN_STAKE, CD, REWARD_PCT);
        submitter.addSubmitter(CAROL);
        submitter.stake{value: MIN_STAKE}(CAROL);
        HV.deal(BOB, 10 ether);
        HV.deal(CAROL, 10 ether);
        HV.deal(CHAL, 10 ether);
    }

    function commit(address who) internal returns (bytes memory h1) {
        HV.prank(who);
        (bool ok, bytes memory ret) = address(rollup).call(abi.encodeCall(
            Rollup.commitBatch,
            (IRollup.BatchDataInput(0, genesis, 1, 0, bytes32(uint256(100)), bytes32(uint256(110)), bytes32(0)))));
        require(ok, string(abi.encodePacked("commit: ", reason(ret))));
        h1 = enc(0, 1, dataHash0(1), ZVH, bytes32(uint256(100)), bytes32(uint256(110)), keccak256(genesis));
        require(keccak256(h1) == rollup.committedBatches(1), "harness: header mismatch");
    }

    function cutover() internal {
        uint256 exp = rollup.lastCommittedBatchIndex();
        admin.upgradeAndCall(
            ITransparentUpgradeableProxy(payable(address(rollup))),
            address(impl),
            abi.encodeCall(Rollup.initialize4, (address(submitter), exp)));
        require(rollup.submitterContract() == address(submitter), "cutover did not swap");
        require(rollup.legacyCutoverBatchIndex() == exp, "lcb not recorded");
    }

    function challenge(bytes memory h1) internal {
        HV.prank(CHAL);
        (bool ok, bytes memory ret) = address(rollup).call{value: CD}(
            abi.encodeCall(Rollup.challengeState, (uint64(1), keccak256(h1))));
        require(ok, string(abi.encodePacked("challenge: ", reason(ret))));
    }

    function tryProve(address who, bytes memory h1) internal returns (string memory st) {
        HV.prank(who);
        (bool ok, bytes memory ret) = address(rollup).call(
            abi.encodeCall(Rollup.proveState, (h1, bytes(""))));
        st = ok ? "ok" : reason(ret);
    }

    function reason(bytes memory data) internal pure returns (string memory) {
        if (data.length >= 4 && bytes4(data) == 0x08c379a0) {
            bytes memory rest = new bytes(data.length - 4);
            for (uint256 i = 0; i < rest.length; i++) rest[i] = data[i + 4];
            return abi.decode(rest, (string));
        }
        return string.concat("raw:", HV.toString(data));
    }

    /// O13: after the cutover, the legacy submitter can no longer defend.
    function test_L_nat_defend_legacy_blocked() public {
        deploy();
        bytes memory h1 = commit(BOB);
        cutover();
        challenge(h1);
        string memory st = tryProve(BOB, h1);
        console.log("HOLON defend 1 proveState(Bob)", st);
        require(keccak256(bytes(st)) == keccak256(bytes("only active submitter allowed")), st);
        // control: Carol passes onlyActiveSubmitter; her proof fails inside
        // _verifyProof (verifier oracle), i.e. past the submitter check
        st = tryProve(CAROL, h1);
        console.log("HOLON defend 2 proveState(Carol)", st);
        require(keccak256(bytes(st)) == keccak256(bytes("Invalid batch proof")), st);
    }

    /// O14: after the cutover, slashing the legacy committer is a no-op on the new
    /// registry; a native (post-cutover) committer is slashed for real.
    function test_L_nat_slash_legacy_misses() public {
        deploy();
        bytes memory h1 = commit(BOB);
        cutover();
        challenge(h1);
        HV.warp(block.timestamp + PROOF_WINDOW + 1);
        uint256 bobBefore = submitter.stakeOf(BOB);
        string memory st = tryProve(CAROL, h1);
        console.log("HOLON slash 1 proveState-timeout(Carol)", st);
        require(keccak256(bytes(st)) == keccak256("ok"), st);
        uint256 reward = rollup.batchChallengeReward(CHAL);
        console.log("HOLON slash 2 challengerReward", HV.toString(reward));
        require(submitter.stakeOf(BOB) == 0 && bobBefore == 0, "Bob stake changed in new registry");
        require(reward == CD, "challenger reward is not deposit-only");
        require(submitter.isActive(CAROL), "Carol lost active status");

        // native control: challengerWin sets revertReqIndex, so a fresh deployment is
        // needed for a post-cutover commit (nonReqRevert blocks everything after a win)
        deploy();
        cutover();  // exp = lastCommittedBatchIndex = 0
        bytes memory h2 = commit(CAROL);
        HV.prank(CHAL);
        (bool ok, bytes memory ret) = address(rollup).call{value: CD}(
            abi.encodeCall(Rollup.challengeState, (uint64(1), keccak256(h2))));
        require(ok, string(abi.encodePacked("challenge2: ", reason(ret))));
        HV.warp(block.timestamp + PROOF_WINDOW + 1);
        st = tryProve(CAROL, h2);
        console.log("HOLON slash 3 proveState-timeout-native", st);
        require(keccak256(bytes(st)) == keccak256("ok"), st);
        uint256 reward2 = rollup.batchChallengeReward(CHAL);
        console.log("HOLON slash 4 challengerReward2", HV.toString(reward2));
        console.log("HOLON slash 5 carolStake", HV.toString(submitter.stakeOf(CAROL)));
        require(!submitter.isActive(CAROL), "Carol still active after native slash");
        require(submitter.stakeOf(CAROL) == 0, "Carol stake not slashed");
        require(reward2 == CD + (MIN_STAKE * REWARD_PCT) / 100, "native slash reward wrong");
    }
}
