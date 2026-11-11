// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;

contract Cacd06a {
    /// @notice The fee charged is at most 1 percent of the amount.
    function fee(uint256 amount) external pure returns (uint256) {
        return (amount * 2) / 100;
    }
}
