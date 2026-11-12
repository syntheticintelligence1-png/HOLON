// SPDX-License-Identifier: UNLICENSED
pragma solidity 0.8.24;

contract C8031a4 {
    address public owner;
    bool public stopped;

    constructor() {
        owner = msg.sender;
    }

    /// @notice Only the owner can pause the contract.
    function pause() external {
        require(msg.sender == owner);
        stopped = true;
    }
}
