// SPDX-License-Identifier: MIT
// HOLON I84 base of Bundle II's law harnesses (tests_m3/test_bundle2_laws.py rules LD1, K2, D5, FP4, LD5; the sidecar
// spec/M3/lib/bundle2_laws.json). It is I80's deployment (replay/M3/bundle2/HolonBundle2Step.t.sol b2Deploy: I20's
// Rollup deployment with the real router as the Rollup's verifier and the stand-ins Z1 and Z2) with the router's
// constructor versions taken from HOLON_VERSIONS (the sidecar's deployment.router.versions, each mapped to Z1), and
// I20's commit row (replay/M1/solidity/HolonTraceReplay.t.sol: commitInput, newHeader), both inherited unchanged.
//
// Environment: HOLON_INIT_F, _W, _D, _T0, _R0 (I20's deployment parameters [F, W, D, t0, r0]) and HOLON_VERSIONS (a
// comma-separated list).
pragma solidity =0.8.24;

import {console} from "forge-std/Test.sol";
import {HolonTraceReplayTest, HolonSubmitterOracle} from "./HolonTraceReplay.t.sol";
import {HolonZkStandIn} from "./HolonBundle2Step.t.sol";
import {Rollup} from "../contracts/l1/rollup/Rollup.sol";
import {MultipleVersionRollupVerifier} from "../contracts/l1/rollup/MultipleVersionRollupVerifier.sol";
import {L1MessageQueueWithGasPriceOracle} from "../contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol";
import {TransparentUpgradeableProxy} from "@openzeppelin/contracts/proxy/transparent/TransparentUpgradeableProxy.sol";

/// The cheatcodes this harness needs beyond I20's HolonVm (the pinned forge 1.5.1 serves them all).
interface HolonLawsVm {
    struct Gas {
        uint64 gasLimit;
        uint64 gasTotalUsed;
        uint64 gasMemoryUsed;
        int64 gasRefunded;
        uint64 gasRemaining;
    }

    function lastCallGas() external view returns (Gas memory);
    function envOr(string calldata name, uint256 defaultValue) external view returns (uint256);
    function envUint(string calldata name, string calldata delim) external view returns (uint256[] memory);
    function pauseGasMetering() external;
    function resumeGasMetering() external;
}

abstract contract HolonBundle2LawsBase is HolonTraceReplayTest {
    HolonLawsVm internal constant LV = HolonLawsVm(address(uint160(uint256(keccak256("hevm cheat code")))));
    MultipleVersionRollupVerifier internal router;
    HolonZkStandIn internal z1;
    HolonZkStandIn internal z2;

    function lawsInit() internal view returns (uint256[] memory init) {
        init = new uint256[](5);
        init[0] = HV.envUint("HOLON_INIT_F");
        init[1] = HV.envUint("HOLON_INIT_W");
        init[2] = HV.envUint("HOLON_INIT_D");
        init[3] = HV.envUint("HOLON_INIT_T0");
        init[4] = HV.envUint("HOLON_INIT_R0");
    }

    /// I80's deployment (HolonBundle2StepTest.b2Deploy's steps, in its order) with the router constructed with
    /// `versions`, each mapped to the stand-in Z1.
    function lawsDeploy(uint256 tid, uint256[] memory init, uint256[] memory versions) internal {
        HV.warp(EPOCH + init[3]);
        sub = new HolonSubmitterOracle();
        sub.setActive(who2addr(2), true);
        sub.setActive(who2addr(3), true);
        z1 = new HolonZkStandIn(1);
        z2 = new HolonZkStandIn(2);
        address[] memory zs = new address[](versions.length);
        for (uint256 i = 0; i < versions.length; i++) zs[i] = address(z1);
        router = new MultipleVersionRollupVerifier(versions, zs);
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
    }

    /// I20's commit row [1, who, version, parent, n, lbn, prev, post, nblobs, blob0, blob1, proof] through
    /// commitBatch (op 1) by `who`; on success the harness records the committed header as I20's harness does.
    function commitRow(uint256 tid, uint256[] memory s) internal returns (bool ok, bytes memory ret) {
        setBlobs(s, 0);
        bytes memory cd = abi.encodeCall(Rollup.commitBatch, (commitInput(tid, s, 0)));
        (ok, ret) = callAs(s[1], cd, 0);
        if (ok) hdrs[tid][s[3] + 1] = newHeader(tid, s, 0, rollup.batchBlobVersionedHashes(s[3] + 1));
    }

    function row(uint256 who, uint256 v, uint256 parent, uint256 n, uint256 lbn, uint256 prev, uint256 post)
        internal pure returns (uint256[] memory s)
    {
        s = new uint256[](13);
        s[0] = 1;
        s[1] = who;
        s[2] = v;
        s[3] = parent;
        s[4] = n;
        s[5] = lbn;
        s[6] = prev;
        s[7] = post;
    }

    function hex0x(bytes memory b) internal pure returns (string memory) {
        return HV.toString(b);
    }
}
