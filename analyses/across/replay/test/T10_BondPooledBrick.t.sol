// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./util/Base.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { Mock_Adapter } from "across/chain-adapters/Mock_Adapter.sol";

// Composition of two individually-benign relaxations:
//   R_bond : bondToken is also an LP-enabled pooled token (fixture default: WETH; production: ABT, not pooled);
//   R_fee  : protocolFeeCapturePct > 0 (production: 0 at block 26259843).
// INV H2 (bond custody): activeRequest => balance(bondToken) >= bondAmount + liquidReserves(bondToken).
// _sync (HubPool.sol:963-964) relies on it; executeRootBundle only checks liquidReserves (HubPool.sol:904).
// After an early protocol-fee claim (T01), liquidReserves > balanceSansBond, so a VALID netSend <= liquidReserves
// consumes bond collateral; the final leaf's bond refund then reverts, and so does emergencyDeleteProposal.
contract T10_BondPooledBrick is ReplayBase {
    uint256 constant X = 777;
    address lp = makeAddr("lp");

    function setUp() public {
        createHubPoolFixture(); // bondToken = WETH, bondAmount = 6 ether
        Mock_Adapter adapter = new Mock_Adapter();
        fixture.hubPool.setCrossChainContracts(X, address(adapter), makeAddr("spokeX"));
        enableToken(X, address(fixture.weth), fixture.l2Weth); // R_bond
        vm.deal(lp, 100 ether);
        vm.startPrank(lp);
        fixture.weth.deposit{ value: 100 ether }();
        fixture.weth.approve(address(fixture.hubPool), type(uint256).max);
        fixture.hubPool.addLiquidity(address(fixture.weth), 100 ether);
        vm.stopPrank();
        fixture.hubPool.setProtocolFeeCapture(makeAddr("feeSink"), 1e18); // R_fee
    }

    function test_validBundle_bricksHub() public {
        address w = address(fixture.weth);
        // Bundle 1: attributes 10 WETH of fees; then the protocol fee is claimed out of LP liquidity.
        HubPoolInterface.PoolRebalanceLeaf memory f = _prLeaf(X, 1, 0, w, 0, 10 ether);
        _propose(1, _prHash(f), bytes32(0), bytes32(0));
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(f, new bytes32[](0));
        fixture.hubPool.claimProtocolFeesCaptured(w);
        (uint256 L, , ) = _pooled(w);
        assertEq(L, 100 ether);
        assertEq(fixture.weth.balanceOf(address(fixture.hubPool)), 90 ether);

        // Bundle 2 (valid w.r.t. on-chain view: netSend 93 <= liquidReserves 100), two leaves.
        HubPoolInterface.PoolRebalanceLeaf memory a = _prLeaf(X, 0, 0, w, 93 ether, 0);
        HubPoolInterface.PoolRebalanceLeaf memory b = _prLeaf(X, 1, 1, w, 0, 0);
        bytes32 ha = _prHash(a);
        bytes32 hb = _prHash(b);
        _propose(2, _hashPair(ha, hb), bytes32(0), bytes32(0)); // bond 6 WETH enters: balance 96
        vm.warp(block.timestamp + fixture.hubPool.liveness() + 1);
        _exec(a, _one(hb)); // balance 3 < bondAmount 6
        assertLt(fixture.weth.balanceOf(address(fixture.hubPool)), fixture.hubPool.bondAmount());

        vm.expectRevert();
        _exec(b, _one(ha)); // last leaf cannot refund the bond
        vm.expectRevert();
        fixture.hubPool.emergencyDeleteProposal(); // owner escape hatch also refunds the bond -> reverts
        vm.expectRevert();
        fixture.hubPool.exchangeRateCurrent(w); // _sync: balance - bondAmount underflows -> LP ops DoS
        uint256[] memory bebn = new uint256[](1);
        vm.expectRevert(bytes("Proposal has unclaimed leaves"));
        fixture.hubPool.proposeRootBundle(bebn, 1, keccak256("next"), bytes32(0), bytes32(0));
    }
}
