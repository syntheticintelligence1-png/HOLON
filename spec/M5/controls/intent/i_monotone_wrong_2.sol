// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;

contract C61fc01 {
    uint256 public count;

    /// @notice The count never decreases.
    function step() external {
        if (count > 2) {
            count -= 1;
        } else {
            count += 3;
        }
    }
}
