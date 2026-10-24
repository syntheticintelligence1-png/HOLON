// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { UniversalWorld } from "./util/UniversalWorld.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { SpokePoolInterface } from "across/interfaces/SpokePoolInterface.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";

// Replay protection for Universal messages is executedMessages[nonce] in the spoke INSTANCE's storage, while the
// message itself is a target-0, write-once L1 slot that SP1Helios keeps verified forever (storageValues mapping).
// A second Universal_SpokePool instance on the same chain (redeployment reusing helios + hubPoolStore) can import
// every historical root bundle, making every historical refund leaf for this chain payable again.
contract T06_UniversalInstanceReplay is UniversalWorld {
    Universal_SpokePool s1;
    address relayer = makeAddr("relayer");

    function setUp() public {
        _setUpUniversal();
        s1 = _newSpoke();
        fixture.hubPool.setCrossChainContracts(X, address(uAdapter), address(s1));
        dai.mint(address(s1), 500 ether);
    }

    function test_redeployedInstance_replaysHistoricalRoots() public {
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));
        HubPoolInterface.PoolRebalanceLeaf memory lx = _prLeaf(X, 0, 0, address(dai), 0, 0);
        _propose(1, _prHash(lx), rrRoot, bytes32(0));
        (, , , , , , uint32 end) = fixture.hubPool.rootBundleProposal();
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        vm.prank(makeAddr("executor"));
        _exec(lx, new bytes32[](0));
        bytes memory data = abi.encodeWithSignature("relayRootBundle(bytes32,bytes32)", rrRoot, bytes32(0));
        uint256 h = _prove(_n1(end));
        s1.executeMessage(end, abi.encode(address(0), data), h);
        s1.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        assertEq(dai.balanceOf(relayer), 100 ether);

        // Time passes; the chain's spoke is redeployed as a new proxy (same immutables) and funded.
        vm.warp(block.timestamp + 30 days);
        Universal_SpokePool s2 = _newSpoke();
        dai.mint(address(s2), 500 ether);
        // No new L1 action and no new light-client update: the proven slot at head h is still readable.
        s2.executeMessage(end, abi.encode(address(0), data), h);
        s2.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        emit log_named_uint("relayer total", dai.balanceOf(relayer));
        assertEq(dai.balanceOf(relayer), 200 ether, "historical refund paid again by the new instance");
    }
}
