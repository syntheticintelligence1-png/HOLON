// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./util/Base.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { Mock_Adapter } from "across/chain-adapters/Mock_Adapter.sol";
import { IERC20 } from "@openzeppelin/contracts-v4/token/ERC20/IERC20.sol";

// INV L4 (backing): liquidReserves(t) <= balanceOf(HubPool, t) - [t == bondToken && activeRequest] * bondAmount.
// Abstract trace (BFS depth 4 after setup): setProtocolFeeCapture(pct>0) ; executeRootBundle(lpFee=f, netSend=0) ;
// claimProtocolFeesCaptured ; removeLiquidity(all).
contract T01_LedgerBacking is ReplayBase {
    MintableERC20 dai;
    address lp = makeAddr("lp");
    address feeSink = makeAddr("feeSink");
    uint256 constant X = 777;

    function setUp() public {
        createHubPoolFixture();
        dai = fixture.dai;
        Mock_Adapter adapter = new Mock_Adapter();
        fixture.hubPool.setCrossChainContracts(X, address(adapter), makeAddr("spokeX"));
        enableToken(X, address(dai), fixture.l2Dai);
        dai.mint(lp, 1000 ether);
        vm.startPrank(lp);
        dai.approve(address(fixture.hubPool), type(uint256).max);
        fixture.hubPool.addLiquidity(address(dai), 1000 ether);
        vm.stopPrank();
    }

    function test_backingInvariantViolated_andLpExitReverts_atZeroUtilization() public {
        // s0 -> s1: owner sets a non-zero protocol fee share (here 100% to make the effect exact).
        fixture.hubPool.setProtocolFeeCapture(feeSink, 1e18);

        // s1 -> s2: a valid single-leaf bundle that only attributes LP fees (no tokens move on L1).
        HubPoolInterface.PoolRebalanceLeaf memory leaf = _prLeaf(X, 1, 0, address(dai), 0, 10 ether);
        _propose(1, _prHash(leaf), bytes32(0), bytes32(0));
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(leaf, new bytes32[](0));

        // s2 -> s3: the protocol fee is paid out of L1 balance before the fee tokens have been bridged back.
        fixture.hubPool.claimProtocolFeesCaptured(address(dai));

        (uint256 L, int256 U, uint256 F) = _pooled(address(dai));
        uint256 B = dai.balanceOf(address(fixture.hubPool));
        emit log_named_uint("liquidReserves L", L);
        emit log_named_uint("balance B", B);
        emit log_named_int("utilizedReserves U", U);
        emit log_named_uint("undistributedLpFees F", F);
        assertEq(L, 1000 ether);
        assertEq(B, 990 ether);
        assertGt(L, B, "INV L4 violated: L > B");
        assertEq(fixture.hubPool.liquidityUtilizationCurrent(address(dai)), 0, "reported utilization is 0");

        // s3 -> revert: the LP's full exit passes the accounting guard (L -= x) and fails at the token transfer.
        (address lpToken, , , , , ) = fixture.hubPool.pooledTokens(address(dai));
        uint256 shares = IERC20(lpToken).balanceOf(lp);
        vm.prank(lp);
        vm.expectRevert(); // ERC20: transfer amount exceeds balance
        fixture.hubPool.removeLiquidity(address(dai), shares, false);
    }
}
