// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import { HubPoolTestBase } from "across-test/utils/HubPoolTestBase.sol";
import { HubPool } from "across/hub-pool/HubPool.sol";
import { HubPoolInterface } from "across/interfaces/HubPoolInterface.sol";
import { SpokePoolInterface } from "across/interfaces/SpokePoolInterface.sol";
import { MintableERC20 } from "across/test/MockERC20.sol";
import { Mock_Adapter } from "across/chain-adapters/Mock_Adapter.sol";

// Shared helpers for the replay suite: leaf builders and a 2-leaf merkle tree (OZ commutative hashing).
abstract contract ReplayBase is HubPoolTestBase {
    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encodePacked(a, b)) : keccak256(abi.encodePacked(b, a));
    }

    function _prLeaf(
        uint256 chainId,
        uint256 groupIndex,
        uint8 leafId,
        address l1Token,
        int256 netSend,
        uint256 lpFee
    ) internal pure returns (HubPoolInterface.PoolRebalanceLeaf memory leaf) {
        uint256[] memory fees = new uint256[](1);
        fees[0] = lpFee;
        int256[] memory sends = new int256[](1);
        sends[0] = netSend;
        int256[] memory running = new int256[](1);
        running[0] = 0;
        address[] memory toks = new address[](1);
        toks[0] = l1Token;
        leaf = HubPoolInterface.PoolRebalanceLeaf({
            chainId: chainId,
            groupIndex: groupIndex,
            bundleLpFees: fees,
            netSendAmounts: sends,
            runningBalances: running,
            leafId: leafId,
            l1Tokens: toks
        });
    }

    function _prHash(HubPoolInterface.PoolRebalanceLeaf memory leaf) internal pure returns (bytes32) {
        return keccak256(abi.encode(leaf));
    }

    function _refundLeaf(
        uint256 chainId,
        address l2Token,
        address to,
        uint256 amount,
        uint32 leafId
    ) internal pure returns (SpokePoolInterface.RelayerRefundLeaf memory leaf) {
        uint256[] memory amounts = new uint256[](1);
        amounts[0] = amount;
        address[] memory addrs = new address[](1);
        addrs[0] = to;
        leaf = SpokePoolInterface.RelayerRefundLeaf({
            amountToReturn: 0,
            chainId: chainId,
            refundAmounts: amounts,
            leafId: leafId,
            l2TokenAddress: l2Token,
            refundAddresses: addrs
        });
    }

    function _one(bytes32 x) internal pure returns (bytes32[] memory p) {
        p = new bytes32[](1);
        p[0] = x;
    }

    function _propose(uint8 leafCount, bytes32 prRoot, bytes32 rrRoot, bytes32 slowRoot) internal {
        uint256[] memory bebn = new uint256[](1);
        bebn[0] = block.number;
        fixture.hubPool.proposeRootBundle(bebn, leafCount, prRoot, rrRoot, slowRoot);
    }

    function _exec(HubPoolInterface.PoolRebalanceLeaf memory leaf, bytes32[] memory proof) internal {
        fixture.hubPool.executeRootBundle(
            leaf.chainId,
            leaf.groupIndex,
            leaf.bundleLpFees,
            leaf.netSendAmounts,
            leaf.runningBalances,
            leaf.leafId,
            leaf.l1Tokens,
            proof
        );
    }

    function _pooled(address l1Token) internal view returns (uint256 liquid, int256 utilized, uint256 undistributed) {
        (, , , int256 u, uint256 l, uint256 f) = fixture.hubPool.pooledTokens(l1Token);
        return (l, u, f);
    }
}
