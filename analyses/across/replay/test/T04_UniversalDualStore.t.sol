// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { UniversalWorld } from "./util/UniversalWorld.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { SpokePoolInterface } from "across/interfaces/SpokePoolInterface.sol";
import { Universal_SpokePool } from "across/spoke-pools/Universal_SpokePool.sol";

// beta_root via the Universal channel: Universal_Adapter.relayMessage (Universal_Adapter.sol:53-69, isAdminSender at :66) chooses the
// HubPoolStore key space from msg.sender of the OUTER HubPool call: owner -> admin nonce dataUuid++ with
// target = spoke; anyone else -> nonce = challengePeriodEndTimestamp with target = 0 (HubPoolStore.sol:55-70).
// Universal_SpokePool.executeMessage accepts target in {0, this} and dedups per nonce only
// (Universal_SpokePool.sol:126-164; target check :145, replay bit :151-154). If one bundle's groupIndex-0 leaves are executed by callers of both
// classes, the same relayRootBundle payload lands under two nonces that BOTH resolve on the owner-executed spoke.
contract T04_UniversalDualStore is UniversalWorld {
    Universal_SpokePool spokeX;
    address executor = makeAddr("dataworkerExecutor");
    address relayer = makeAddr("relayer");

    function setUp() public {
        _setUpUniversal();
        spokeX = _newSpoke();
        fixture.hubPool.setCrossChainContracts(X, address(uAdapter), address(spokeX));
        fixture.hubPool.setCrossChainContracts(Y, address(uAdapter), makeAddr("spokeY"));
        dai.mint(address(spokeX), 500 ether);
    }

    function test_ownerAndNonOwnerExecution_duplicateRootOnSpoke() public {
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));
        HubPoolInterface.PoolRebalanceLeaf memory lx = _prLeaf(X, 0, 0, address(dai), 0, 0);
        HubPoolInterface.PoolRebalanceLeaf memory ly = _prLeaf(Y, 0, 1, address(dai), 0, 0);
        bytes32 hx = _prHash(lx);
        bytes32 hy = _prHash(ly);
        _propose(2, _hashPair(hx, hy), rrRoot, bytes32(0)); // a VALID bundle: one groupIndex-0 leaf per chain
        (, , , , , , uint32 end) = fixture.hubPool.rootBundleProposal();
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);

        _exec(lx, _one(hy)); // executed by the HubPool owner (this test contract)
        vm.prank(executor);
        _exec(ly, _one(hx)); // executed by an ordinary caller

        bytes memory data = abi.encodeWithSignature("relayRootBundle(bytes32,bytes32)", rrRoot, bytes32(0));
        assertEq(store.relayMessageCallData(0), keccak256(abi.encode(address(spokeX), data)), "admin-nonce copy");
        assertEq(store.relayMessageCallData(end), keccak256(abi.encode(address(0), data)), "timestamp-nonce copy");

        uint256 h = _prove(_n2(0, end));
        spokeX.executeMessage(0, abi.encode(address(spokeX), data), h);
        spokeX.executeMessage(end, abi.encode(address(0), data), h);

        spokeX.executeRelayerRefundLeaf(0, rr, new bytes32[](0));
        spokeX.executeRelayerRefundLeaf(1, rr, new bytes32[](0));
        emit log_named_uint("relayer received on spokeX", dai.balanceOf(relayer));
        assertEq(dai.balanceOf(relayer), 200 ether, "one entitlement, two payouts");
    }

    function test_uniformCallerClass_singleRoot() public {
        // Control: same bundle, both leaves executed by non-owners -> one stored copy (dedup on nonce = end).
        SpokePoolInterface.RelayerRefundLeaf memory rr = _refundLeaf(block.chainid, address(dai), relayer, 100 ether, 0);
        bytes32 rrRoot = keccak256(abi.encode(rr));
        HubPoolInterface.PoolRebalanceLeaf memory lx = _prLeaf(X, 0, 0, address(dai), 0, 0);
        HubPoolInterface.PoolRebalanceLeaf memory ly = _prLeaf(Y, 0, 1, address(dai), 0, 0);
        bytes32 hx = _prHash(lx);
        bytes32 hy = _prHash(ly);
        _propose(2, _hashPair(hx, hy), rrRoot, bytes32(0));
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        vm.startPrank(executor);
        _exec(lx, _one(hy));
        _exec(ly, _one(hx));
        vm.stopPrank();
        assertEq(store.relayMessageCallData(0), bytes32(0), "no admin-nonce copy");
    }
}
