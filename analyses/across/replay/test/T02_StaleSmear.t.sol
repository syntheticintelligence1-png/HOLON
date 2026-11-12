// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./util/Base.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { Mock_Adapter } from "across/chain-adapters/Mock_Adapter.sol";

// Spec (HubPool.sol:90-93): fees allocated by a bundle are smeared to LPs at lpFeeRatePerSecond.
// Gap: _allocateLpAndProtocolFees (HubPool.sol:1004-1007) raises undistributedLpFees without first accruing
// against lastLpFeeUpdate, so the next _updateAccumulatedLpFees applies (now - lastLpFeeUpdate) -- time that
// elapsed BEFORE the fees existed -- to the new fees.
contract T02_StaleSmear is ReplayBase {
    MintableERC20 dai;
    uint256 constant X = 777;

    function setUp() public {
        createHubPoolFixture();
        dai = fixture.dai;
        Mock_Adapter adapter = new Mock_Adapter();
        fixture.hubPool.setCrossChainContracts(X, address(adapter), makeAddr("spokeX"));
        enableToken(X, address(dai), fixture.l2Dai);
        addLiquidity(dai, 1000 ether);
    }

    function _bundleWithFees(uint256 fee) internal {
        HubPoolInterface.PoolRebalanceLeaf memory leaf = _prLeaf(X, 1, 0, address(dai), 0, fee);
        _propose(1, _prHash(leaf), bytes32(0), bytes32(0));
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(leaf, new bytes32[](0));
    }

    function test_idlePool_feesReleasedInstantly() public {
        uint256 r0 = fixture.hubPool.exchangeRateCurrent(address(dai)); // refreshes lastLpFeeUpdate
        vm.warp(block.timestamp + 8 days); // no LP interaction (> 1/lpFeeRatePerSecond ~ 7.72 days)
        _bundleWithFees(100 ether);
        uint256 r1 = fixture.hubPool.exchangeRateCurrent(address(dai)); // same block as execution
        emit log_named_uint("rate before", r0);
        emit log_named_uint("rate 0s after fee allocation (idle 8d before)", r1);
        assertEq(r1, 1.1e18, "100% of the new fees distributed at t = allocation time");
    }

    function test_activePool_feesSmeared() public {
        vm.warp(block.timestamp + 8 days);
        fixture.hubPool.exchangeRateCurrent(address(dai)); // an interaction right before the bundle
        _bundleWithFees(100 ether);
        // HubPool did not accrue between the refresh and allocation except over liveness+1 seconds.
        uint256 r1 = fixture.hubPool.exchangeRateCurrent(address(dai));
        emit log_named_uint("rate 0s after fee allocation (refreshed before)", r1);
        assertLt(r1, 1.002e18, "only ~liveness*rate of the fees released");
    }
}
