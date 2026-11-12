// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;

contract Ce8b53f {
    uint256 public count;

    /// @notice The count never decreases.
    function step() external {
        count += 1;
    }
}
