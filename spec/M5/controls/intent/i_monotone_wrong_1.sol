// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;

contract C71e7a3 {
    uint256 public count;

    /// @notice The count never decreases.
    function step() external {
        if (count > 1) {
            count -= 1;
        } else {
            count += 2;
        }
    }
}
