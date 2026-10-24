// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { UniversalWorld } from "./util/UniversalWorld.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { SpokePoolInterface } from "across/interfaces/SpokePoolInterface.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";

// Spec of emergencyDeleteProposal (HubPool.sol:224-240): stop a bad bundle that passed liveness. On native-bridge
// chains, chains whose groupIndex-0 leaf was not yet executed never receive the roots. On Universal chains the
// first executed leaf publishes a target-0 copy readable by EVERY Universal spoke, so deletion cannot revoke it.
contract T05_UniversalDeleteLeak is UniversalWorld {
    Universal_SpokePool spokeX;
    Universal_SpokePool spokeY;
    address relayer = makeAddr("relayer");

    function setUp() public {
        _setUpUniversal();
        spokeX = _newSpoke();
        spokeY = _newSpoke();
        fixture.hubPool.setCrossChainContracts(X, address(uAdapter), address(spokeX));
        fixture.hubPool.setCrossChainContracts(Y, address(uAdapter), address(spokeY));
        dai.mint(address(spokeY), 500 ether);
    }

    function test_deletedBundle_rootsStillImportableOnUnexecutedChain() public {
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));
        HubPoolInterface.PoolRebalanceLeaf memory lx = _prLeaf(X, 0, 0, address(dai), 0, 0);
        HubPoolInterface.PoolRebalanceLeaf memory ly = _prLeaf(Y, 0, 1, address(dai), 0, 0);
        bytes32 hx = _prHash(lx);
        bytes32 hy = _prHash(ly);
        _propose(2, _hashPair(hx, hy), rrRoot, bytes32(0));
        (, , , , , , uint32 end) = fixture.hubPool.rootBundleProposal();
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);

        vm.prank(makeAddr("executor"));
        _exec(lx, _one(hy)); // only chain X's leaf is executed
        fixture.hubPool.emergencyDeleteProposal(); // admin revokes the bundle; Y's leaf can no longer be executed
        vm.expectRevert();
        _exec(ly, _one(hx));

        bytes memory data = abi.encodeWithSignature("relayRootBundle(bytes32,bytes32)", rrRoot, bytes32(0));
        uint256 h = _prove(_n1(end));
        spokeY.executeMessage(end, abi.encode(address(0), data), h); // anyone can relay
        (, bytes32 r) = spokeY.rootBundles(0);
        assertEq(r, rrRoot, "deleted bundle's roots reached chain Y");
        spokeY.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        assertEq(dai.balanceOf(relayer), 100 ether, "payout from a bundle the admin deleted before Y executed");
    }
}
